#!/usr/bin/env python3
"""Compile the M1+ Music payload, install its hook into demo, and add the page assets.

Runs on a workdir that already has the battery, lock screen and space mods applied (so demo's
.pdr is zeroed); it patches that demo and writes the new ui/*.bin. The injection mirrors q2-pod
(tools/build.py, Copyright (c) 2026 Diamond Bond, MIT; see NOTICE), reduced to the one hook this
project needs:

  * payload compiled non-PIC (clang --target=mipsel-linux-gnu -march=mips32r2 -mabi=32 -mfp64
    -mno-abicalls -fno-pic -G0 -Oz), linked at 0xb00000 by patch/link.ld, objcopy'd to patch.bin;
  * appended to demo through its final PT_NULL program header, rewritten to a PT_LOAD (RWX) at
    0xb00000; the payload keeps no .bss, so memsz == filesz and nothing else moves;
  * the Home icon click dispatcher's 3-word PIC prologue (checked) is overwritten with `j
    m1plus_home_click; nop`; a trampoline restores $gp (0xa03ed0) and resumes the stock function at
    its 4th instruction, so the payload can still call it (open a stock Home destination, or fall
    through for every non-entry tap);
  * stock functions are reached through absolute-address macros, libc only through demo's own GOT
    slots -- both pinned.

A second hook, home_page_init, runs the boot guard (patch/home.c); a third, albuminfo_listitem0_layout,
restyles the album page's header (patch/albuminfo.c), a fourth, playing_page_init, tints Now Playing
and shows the remaining time (patch/nowplaying.c). The library rows are pinned
call-site and immediate edits (patch/rows.json). Every patched word and the input demo are pinned
by value/SHA before anything is written.

Usage: pod.py WORKDIR
"""
import argparse, hashlib, json, os, pathlib, stat, struct, subprocess, sys
from elftools.elf.elffile import ELFFile   # before tools/ joins sys.path: our dis.py shadows stdlib dis
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import pod_pages, pod_ui

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATCH = os.path.join(ROOT, 'patch')
DEMO = 'release/bin/demo'

# Toolchain: Homebrew LLVM/LLD (Apple clang has no MIPS target). Override with $LLVM_BIN / $LLD_BIN.
LLVM = os.environ.get('LLVM_BIN', '/opt/homebrew/opt/llvm/bin')
LLD = os.environ.get('LLD_BIN', '/opt/homebrew/opt/lld/bin')
CLANG = os.path.join(LLVM, 'clang')
OBJCOPY = os.path.join(LLVM, 'llvm-objcopy')
LD = os.path.join(LLD, 'ld.lld')

# compiled in this order, linked with --gc-sections (docs/architecture.md)
SOURCES = ['m1plus.c', 'common.c', 'menu.c', 'covercache.c', 'coverflow.c', 'albums.c', 'artists.c', 'shuffle.c', 'albuminfo.c', 'nowplaying.c', 'minibar.c', 'grid.c', 'recent.c', 'dailymix.c', 'rows.c', 'shot.c', 'home.c',
           'scroll.c', 'playmore.c', 'playlists.c', 'songs.c']

FLAGS = ['--target=mipsel-linux-gnu', '-march=mips32r2', '-mabi=32', '-mfp64',
         '-mno-abicalls', '-fno-pic', '-G0', '-ffreestanding', '-fno-builtin',
         '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
         '-Oz', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
         '-ffunction-sections', '-fdata-sections']

# Stock V2.1 demo after mod_space zeroes its .pdr (what this step receives). demo is unchanged by
# the battery/lockscreen asset mods.
ZEROED_DEMO_SHA = 'cdd2e97e85076e8ed4f7ce7b34b7b8065ab041477ddeb2b00dc78aa541c37a7b'

BASE = 0xb00000            # payload load address (stock LOAD ends at va 0xa10fc8)
GP = 0xa03ed0             # demo's $gp (DT_PLTGOT + 0x7ff0); every PIC prologue resolves this

# The one hook: the Home icon click dispatcher (unnamed in .dynsym). It runs only from a Home icon
# tap (widget_on EVT_CLICK, home_page_init). (stock address, replacement payload symbol).
HOME_CLICK = 0x533b80
HOME_CLICK_PROLOGUE = (0x3c1c004d, 0x279c0350, 0x0399e021)  # lui/addiu $gp; addu $gp,$gp,$t9

# The second hook (the boot guard): home_page_init, run once when the Home window
# is created at start-up. m1plus_home_init runs the stock function to completion, then the boot guard.
HOME_INIT = 0x534cd4
HOME_INIT_PROLOGUE = (0x3c1c004d, 0x279cf1fc, 0x0399e021)

# The third hook (patch/albuminfo.c): albuminfo_listitem0_layout, which builds the album page's
# header item. It is called only from the album page's list builder (albuminfo_page_init and its
# to-foreground rebuild), never at boot; m1plus_albuminfo_header runs the stock function first.
ALBUMINFO_HEADER = 0x526264
ALBUMINFO_HEADER_PROLOGUE = (0x3c1c004e, 0x279cdc6c, 0x0399e021)

# The fourth hook (patch/nowplaying.c): playing_page_init, the Now Playing page's init (called by the navigator's
# page-init dispatcher only when the page is built, never at boot). m1plus_playing_init runs the stock function
# first, then starts the page-scoped tint and remaining-time timer.
PLAYING_INIT = 0x53d1e4
PLAYING_INIT_PROLOGUE = (0x3c1c004c, 0x279c6cec, 0x0399e021)

# Stock functions the payload calls, by absolute address (pinned). (return, args, address)
FUNCTIONS = {
    'widget_lookup':           ('void *', 'void *, const char *, int', 0x666a74),
    'widget_on':               ('int', 'void *, int, void *, void *', 0x666d20),
    'widget_set_text_utf8':    ('int', 'void *, const char *', 0x66f720),
    'navigator_back':          ('int', 'void', 0x4d20dc),
    'on_backtoplayer_onclick': ('int', 'void *, void *', 0x4cd58c),
    'window_open':             ('void *', 'const char *', 0x679fd4),
    # Cover Flow (patch/coverflow.c): widgets, the stock slide_menu, images and bitmaps
    'widget_set_visible':      ('int', 'void *, int, int', 0x66c394),
    'widget_set_prop_int':     ('int', 'void *, const char *, int', 0x66ff3c),
    'widget_get_prop_int':     ('int', 'void *, const char *, int', 0x6686f8),
    'widget_get_prop_str':     ('const char *', 'void *, const char *, const char *', 0x6685e0),
    'widget_set_prop_str':     ('int', 'void *, const char *, const char *', 0x66f8a8),
    'widget_set_sensitive':    ('int', 'void *, int', 0x666b9c),
    'widget_set_opacity':      ('int', 'void *, int', 0x669140),   # (the Regenerate Daily Mix row, dimmed: opacity byte +0x34, widget_paint's global alpha)
    'widget_use_style':        ('int', 'void *, const char *', 0x66aa64),
    'hscroll_label_create':    ('void *', 'void *, int, int, int, int', 0x60a700),
    'hscroll_label_set_only_parent_focus': ('int', 'void *, int', 0x6092e8),
    'hscroll_label_set_ellipses': ('int', 'void *, int', 0x609380),
    'widget_grab':             ('int', 'void *, void *', 0x668958),
    'widget_ungrab':           ('int', 'void *, void *', 0x6689f4),
    'widget_count_children':   ('unsigned', 'void *', 0x669f00),
    'widget_get_child':        ('void *', 'void *, unsigned', 0x669f20),
    'widget_destroy_children': ('int', 'void *', 0x67050c),
    'widget_invalidate_force': ('int', 'void *, void *', 0x6691d0),
    'widget_factory':          ('void *', 'void', 0x674218),
    'widget_factory_create_widget': ('void *', 'void *, const char *, void *, int, int, int, int', 0x6744b4),
    'image_create':            ('void *', 'void *, int, int, int, int', 0x62d8d4),
    'image_set_draw_type':     ('int', 'void *, int', 0x62d964),
    'image_base_set_image':    ('int', 'void *, const char *', 0x654910),
    'widget_load_image':       ('int', 'void *, const char *, void *', 0x66b0d8),
    'widget_unload_image':     ('int', 'void *, void *', 0x66b888),
    'bitmap_create_ex':        ('void *', 'unsigned, unsigned, unsigned, unsigned', 0x64005c),
    'bitmap_destroy':          ('int', 'void *', 0x63fdb4),
    'bitmap_lock_buffer_for_read':  ('const unsigned char *', 'void *', 0x640738),
    'bitmap_lock_buffer_for_write': ('unsigned char *', 'void *', 0x6407b0),
    'bitmap_unlock_buffer':    ('int', 'void *', 0x640828),
    'bitmap_get_line_length':  ('unsigned', 'void *', 0x640264),
    'canvas_draw_image':       ('int', 'void *, void *, const void *, const void *', 0x6455d4),
    # the Albums grid (patch/albums.c): its pointer position and the canvas text calls (draw_text_in_rect draws at the
    # canvas' current font, colour and alignment, widget_prepare_text_style sets them from the widget's style)
    'widget_to_local':         ('int', 'void *, void *', 0x669b88),
    'widget_set_state':        ('int', 'void *, const char *', 0x66962c),   # the Main Menu page's pressed arrow (patch/menu.c)
    'widget_prepare_text_style': ('int', 'void *, void *', 0x66a214),
    'canvas_draw_text_in_rect': ('int', 'void *, const unsigned *, unsigned, const void *', 0x6496a0),
    'canvas_measure_text':     ('float', 'void *, const unsigned *, unsigned', 0x644544),   # float_t in $f0
    # the Albums list rows' highlight and hairline: color_t is one word (lcd_set_fill_color stores $a1 at lcd+0xbc), r,g,b,a bytes;
    # canvas_fill_rect @0x644e4c takes h on the stack and clips to the canvas' clip rect
    'canvas_set_fill_color':   ('int', 'void *, unsigned', 0x644220),
    'canvas_fill_rect':        ('int', 'void *, int, int, int, int', 0x644e4c),
    # Cover Flow landscape (patch/coverflow.c): the page's font, as canvas_draw_text @0x645348 calls it. font_get_vmetrics
    # returns its 8 byte struct (ascent s16 first) through a hidden pointer in $a0
    'font_get_glyph':          ('int', 'void *, unsigned, unsigned, void *', 0x6508b0),
    'font_get_vmetrics':       ('void', 'void *, void *, unsigned', 0x650918),
    'tk_utf8_to_utf16_ex':     ('unsigned *', 'const char *, unsigned, unsigned *, unsigned', 0x70eb24),   # wchar_t is 32 bit
    'slide_menu_set_value':    ('int', 'void *, int', 0x61399c),
    'list_item_create':        ('void *', 'void *, int, int, int, int', 0x60bec8),
    'label_create':            ('void *', 'void *, int, int, int, int', 0x62ee90),
    'timer_add':               ('unsigned', 'int (*)(const void *), void *, unsigned', 0x663530),
    'timer_remove':            ('int', 'unsigned', 0x66360c),
    # Cover Flow data: the stock library queries and the art extractors
    'loadLocalClassList':      ('int', 'int', 0x4ee504),
    'loadAlbumList':           ('int', 'int, void *', 0x4ee8d8),   # Artists: an artist's albums (album_page_init)
    'loadAlbumdetailList':     ('int', 'int, void *', 0x4eea98),   # an album row (a RECORD pointer, not an index) to its songs: loadLocalClassList(0xff11) for the All songs row
    'loadSongList':            ('int', 'void *, const char *, int, int', 0x4e2ce0),
    'navigator_to_with_context': ('int', 'const char *, const void *', 0x4d1d48),
    'toolsGetAlbumCover':      ('int', 'const char *, const char *, int, int', 0x5eaee0),
    'toolsGetExternCover':     ('int', 'const char *, const char *, int, int', 0x5eafec),
    # Shuffle (patch/shuffle.c, docs/architecture.md): the stock play mode as the Play settings page
    # sets it (@0x49fc78), the random seed, and the message box
    'mclGetPlayMode':          ('int', 'void', 0x5d3628),
    'mclSetPlayMode':          ('int', 'int', 0x5d278c),
    'notifyPlayMode':          ('int', 'void', 0x50ee04),
    'dmrSendPlayMode':         ('int', 'int', 0x4f10f0),
    'write_int_config':        ('int', 'int, const char *, const char *', 0x4d6a2c),
    'toolsRandnum':            ('int', 'int', 0x5e0c58),
    'time_now_ms':             ('unsigned', 'void', 0x70cf58),   # uint64_t; o32 LE returns the low word in $v0
    # Home (patch/home.c): the window stack, to open the menu only when the stock Home is the topmost
    # normal window and fully opened
    'window_manager':          ('void *', 'void', 0x6774b4),
    'window_manager_get_top_main_window': ('void *', 'void *', 0x6774f0),
    'widget_is_window_opened': ('int', 'void *', 0x66aa04),
    # Library rows (patch/rows.c, docs/architecture.md): the row constructors' own layout call, and what
    # the row fit reads and resizes
    'widget_set_children_layout': ('int', 'void *, const char *', 0x656f7c),
    'widget_get_type':         ('const char *', 'void *', 0x66a794),
    'widget_get_visible':      ('int', 'void *', 0x672948),
    'widget_resize':           ('int', 'void *, int, int', 0x66d13c),
    'widget_move':             ('int', 'void *, int, int', 0x66cfc0),
    'hscroll_label_set_only_focus': ('int', 'void *, int', 0x60929c),
    # The M1+ Music icon on the Home grid (patch/home.c): what the stock icon builder 0x533d8c calls per icon
    # (view_create, image_create, widget_set_prop_bool "clickable", widget_use_style, widget_set_name, widget_on,
    # label_create, label_set_line_wrap), plus the page/indicator calls of the page builder 0x534064
    'view_create':             ('void *', 'void *, int, int, int, int', 0x6346f0),
    'widget_set_prop_bool':    ('int', 'void *, const char *, int', 0x670170),
    'widget_set_name':         ('int', 'void *, const char *', 0x6668d0),
    'label_set_line_wrap':     ('int', 'void *, int', 0x62e068),
    'slide_indicator_set_max': ('int', 'void *, unsigned', 0x616b70),
    'widget_destroy':          ('int', 'void *', 0x66e544),
    'window_close':            ('int', 'void *', 0x675b70),   # "Shanling Home" closes the menu under the Settings page
    # The album view (patch/albuminfo.c, patch/coverflow.c): the header's new widgets, the stock Play all
    # sequence, and the cover-task list the stock album page builds before albuminfo_page opens
    'button_create':           ('void *', 'void *, int, int, int, int', 0x622adc),
    'start_player':            ('int', 'void *, int, int, int', 0x4e4648),
    'albumcoverinfo_init':     ('void', 'void *', 0x4dcf9c),
    'batchadd_albumcover_task': ('void', 'int, int', 0x4dccac),   # local_albumsmallcover_task: ends with albumcover_taskstate = 1
}
# Now Playing (patch/nowplaying.c): the window's bg_color through the style API (widget_set_style(widget, "normal:bg_color",
# &value_t) is AWTK's widget_set_style_color: it makes the style mutable, stores the value and invalidates), the uint32
# value_t it takes, and the player's position and length in seconds (what the page's own timer shows, @0x53a8fc)
FUNCTIONS.update({
    'widget_set_style':        ('int', 'void *, const char *, const void *', 0x66c448),
    'value_set_uint32':        ('void *', 'void *, unsigned', 0x711858),
    # The album page's Play all pill (patch/albuminfo.c ah_centre_pill): the translated text (a wchar_t string) and its width
    # in the widget's own style, as widget_measure_text @0x66c7e0 gets it (widget_get_canvas, widget_prepare_text_style,
    # canvas_measure_text @0x644544; 0 when there is no canvas or no text)
    'widget_get_text':         ('const unsigned *', 'void *', 0x667ea4),
    'widget_measure_text':     ('float', 'void *, const unsigned *', 0x66c7e0),
    'get_playtimeandlength':   ('int', 'int *, int *', 0x4e015c),
    # Cover Flow opens on the playing album (patch/covercache.c cc_playing): the playing track's index in the play
    # queue, the call get_playtimeandlength and the lock screen refresh make (@0x4e0198, @0x53f718); -1 for none
    'mclGetPlayPos':           ('int', 'void', 0x5d4290),
})
# Localisation (patch/i18n.h): the stock translation. locale_info() is the app's locale, locale_info_tr(locale, key) the
# table lookup (the key itself when absent), widget_set_tr_text(widget, key) stores the key on the widget (the window
# manager re-translates it when the language changes) and sets the translated text
FUNCTIONS.update({
    'locale_info':             ('void *', 'void', 0x6588b0),
    'locale_info_tr':          ('const char *', 'void *, const char *', 0x658db4),
    'widget_set_tr_text':      ('int', 'void *, const char *', 0x66f994),
})
# Now Playing's info page (patch/nowplaying.c np_info): the label text is read back (the buffer is zero-filled, then
# at most size - 1 bytes of the text are copied) and rewritten with the stock setter
FUNCTIONS.update({
    'widget_get_text_utf8':    ('int', 'void *, char *, unsigned', 0x667d84),
})
# The track rows' playing marker (patch/rows.c rows_track_icon): widget_restack(widget, index) moves a child within its
# parent's children (clamps the index to the last; reads the parent @0x66a014; no relayout of its own)
FUNCTIONS.update({
    'widget_restack':          ('int', 'void *, unsigned', 0x669fc4),
    # what widget_set_visible calls with the parent after a change (@0x66c424): the restack changes the flow even when the
    # icon's visibility does not
    'widget_set_need_relayout_children': ('int', 'void *', 0x66c338),
})
# The album page's Play all and Shuffle open Now Playing the way a track row does (the row handler @0x52569c, loop
# @0x525904..0x5259d8; patch/albuminfo.c ah_open_player): the window stack calls, and widget_off_by_func to take the stock
# Play all handler (@0x525d48, which stays on the page) off the button
FUNCTIONS.update({
    'navigator_window_is_exist':  ('int', 'const char *', 0x4d2040),
    'navigator_close':         ('int', 'const char *', 0x4d2118),   # closes the named page (Now Playing's Look up album / artist, patch/playmore.c)
    'window_manager_get_top_window': ('void *', 'void *', 0x6775c4),
    'widget_off_by_func':      ('int', 'void *, int, void *, void *', 0x666ec0),
    # the album page's tint (patch/albuminfo.c): the page window the header's item is in
    'widget_get_window':       ('void *', 'void *', 0x66a9a8),
})
# (rows_track_number also uses label_create, widget_use_style, widget_set_sensitive and widget_set_text_utf8, above)
# The mini player bar (patch/minibar.c, docs/modules/minibar.md): the calls the stock transport buttons make, and the play state
# they read. The lock screen's btn_play / btn_next handlers (strcmp-bound to 0x53f964 / 0x53f900 by name @0x53f3d4 / @0x53f410) are
# `playpause_quick_click()` / `next_quick_click(e, 0)` followed by the page's own refresh (0x53f520); Now Playing's next button
# (@0x53c16c: `next_quick_click(e, 0)`) and the hardware keys (on_wm_keyup_fun @0x4cda78 / @0x4cdba4) call the same two. Both do
# their own checks (queue, network source, "not found" toast) and tell the other listeners (notifyPlayStatus, dmr, Bluetooth).
# next_quick_click reads e->time (event_t u64 @8: `lw a1, 8(a0); lw a2, 0xc(a0)` @0x4ccf2c) and ignores a click within 1000 ms of the
# last one it took (the global 0xa05a40). mclGetPlayStatus is `lw v0, status`: 2 = playing (the lock screen refresh @0x53f82c shows
# btn_imgpause1_style for 2 and btn_imgplay1_style for anything else), mclSetPause stores 3 (@0x5d2658), mclSetResume 2 (@0x5d26c8).
FUNCTIONS.update({
    'playpause_quick_click':   ('int', 'void', 0x4cd150),
    'next_quick_click':        ('int', 'void *, int', 0x4ccf00),
    'mclGetPlayStatus':        ('int', 'void', 0x5d3640),
})
# The Playlists page (patch/playlists.c, docs/modules/playlists.md): the stock playlist creation, and the click handlers of the stock Playlists
# page's Import and Export rows (static, unnamed; ret_t (ctx, event), neither reads its arguments: each asks with the stock confirm dialog,
# runs importPlayList / exportPlayList and tells the result in the stock message box).
FUNCTIONS.update({
    'createPlayListItem':      ('int', 'void *, const char *', 0x4eeca8),   # (the stock list, name or NULL): the new id, -1 full, -2 name exists
    # The Daily Mix page's Add disc (patch/dailymix.c dp_save, docs/modules/dailymix.md): the playlist-table calls of the stock batch add (batch_add_file @0x4da7dc, class
    # 0xf001 -> 0xf00b: @0x4db34c..0x4db3d0), made per song in the mix's order. All three are thin wrappers over toolsGetMaxId / toolsCheckExist / toolsInsertDbTable on
    # "playlist" in /mnt/data/database.db.
    'checkPlayListExist':      ('int', 'void *, int', 0x4ee1a8),            # (song record, playlist id): 1 = that song is already in it
    'getPlayListMaxId':        ('int', 'void', 0x4ee184),                   # the largest id in the table (the new song row's id is max(100, that) + 1)
    'addPlayList':             ('int', 'void *', 0x4ee1cc),                 # (song record: id REC_ID, playlist id REC_DISC): inserts the row, 1 = done
})
# The Songs page (patch/songs.c, docs/modules/songs.md): the stock multi-select's selection vector (`*0xa045e0`, a vector<int> indexed by the row of
# *pdeq_showlist, 1 = selected: select_recordinit(n) clears it and pushes n zeros, set_selectindex(i) toggles v[i] and returns 1) and the stock batch
# delete (batch_delete_file(class, list, selection, 0, delete_file): the generic loop for 0xf001, deleteMusicFromMusicDb per selected row, remove_file when
# the flag is set, and `*0xa05a5a = 1` at the end). All of them touch no widget (docs/modules/songs.md has the evidence).
FUNCTIONS.update({
    'select_recordinit':       ('void', 'int', 0x4da3b0),
    'set_selectindex':         ('int', 'int', 0x4da434),
    'batch_delete_file':       ('int', 'int, void *, void *, int, int', 0x4e1408),
})
SONGS_PINS = (   # (address, stock word, what it proves): prologues are `lui $gp, hi; addiu $gp, $gp, lo; addu $gp, $gp, $t9`
    (0x4da3b0, 0x3c1c0053, 'select_recordinit prologue'), (0x4da3b4, 0x279c9b20, 'select_recordinit prologue'), (0x4da3b8, 0x0399e021, 'select_recordinit prologue'),
    (0x4da3bc, 0x0480001b, 'select_recordinit: bltz a0 (a negative count does nothing)'),
    (0x4da3a0, 0x8f82ac50, 'clear_selectrecord: lw v0, GOT 0xa045e0 (SEL_VEC: the selection vector\'s pointer)'), (0x4da3ac, 0x8c440000, 'clear_selectrecord: a0 = *SEL_VEC, vector_clear(a0)'),
    (0x4da434, 0x3c1c0053, 'set_selectindex prologue'), (0x4da438, 0x279c9a9c, 'set_selectindex prologue'), (0x4da43c, 0x0399e021, 'set_selectindex prologue'),
    (0x4e1408, 0x3c1c0052, 'batch_delete_file prologue'), (0x4e140c, 0x279c2ac8, 'batch_delete_file prologue'), (0x4e1410, 0x0399e021, 'batch_delete_file prologue'),
    (0x4e1418, 0x3402f00c, 'batch_delete_file: class < 0xf00c (the jump tables\' range)'),
    (0x4d1d80, 0x3c1c0053, 'navigator_to prologue'), (0x4d1d90, 0x1000ffed, 'navigator_to: b navigator_to_with_context (0x4d1d48)'), (0x4d1d94, 0x00002825, 'navigator_to: with a1 = 0 (the delay slot)'),
    (0x52704c, 0x3c1c004e, 'the Songs page\'s search click handler prologue'), (0x52705c, 0x8f848020, 'search handler: lw a0, GOT page'),
    (0x527070, 0x24849e00, 'search handler: a0 = "search_page" (navigator_to("search_page"), no context, nothing set first)'),
    (0x527014, 0x3c1c004e, 'the Songs page\'s sort click handler prologue'), (0x527038, 0x24849db0, 'sort handler: a0 = "dialog/sortselect_dialog" (navigator_to, no context)'),
    (0x47d1a8, 0x24c64f90, 'sortselect row handler 0x47d114: a2 = "SORTSELECT"'), (0x47d1ac, 0x24a54540, 'sortselect row handler: a1 = "SYSSET"'),
    (0x47d1b0, 0x8c640000, 'sortselect row handler: a0 = sortMenu[i] (0x97c770: 0 1 2 3 4)'), (0x47d1b4, 0x0320f809, 'sortselect row handler: jalr write_int_config'),
    (0x47d1b8, 0xae640000, 'sortselect row handler: sw a0, (s3) in the delay slot: sort_flag (0xa059d4) = the choice'),
)
PLAYLIST_IMPORT, PLAYLIST_EXPORT = 0x53dedc, 0x53dd34
PLAYLIST_PINS = (   # (address, stock word, what it proves)
    (PLAYLIST_IMPORT, 0x3c1c004c, 'import click handler prologue'), (PLAYLIST_IMPORT + 4, 0x279c5ff4, 'import click handler prologue'),
    (PLAYLIST_IMPORT + 8, 0x0399e021, 'import click handler prologue'),
    (PLAYLIST_EXPORT, 0x3c1c004c, 'export click handler prologue'), (PLAYLIST_EXPORT + 4, 0x279c619c, 'export click handler prologue'),
    (PLAYLIST_EXPORT + 8, 0x0399e021, 'export click handler prologue'),
    (0x53df64, 0x8f99c2a4, 'import: lw importPlayList from the GOT'), (0x53df6c, 0x0320f809, 'import: jalr importPlayList'),
    (0x53ddc4, 0x8f99c2a0, 'export: lw exportPlayList from the GOT'), (0x53dde8, 0x0320f809, 'export: jalr exportPlayList'),
    (0x4eeca8, 0x3c1c0051, 'createPlayListItem prologue'), (0x4eecac, 0x279c5228, 'createPlayListItem prologue'), (0x4eecb0, 0x0399e021, 'createPlayListItem prologue'),
    (0x4ee184, 0x3c1c0051, 'getPlayListMaxId prologue'), (0x4ee188, 0x279c5d4c, 'getPlayListMaxId prologue'), (0x4ee18c, 0x0399e021, 'getPlayListMaxId prologue'),
    (0x4ee1a8, 0x3c1c0051, 'checkPlayListExist prologue'), (0x4ee1ac, 0x279c5d28, 'checkPlayListExist prologue'), (0x4ee1b0, 0x0399e021, 'checkPlayListExist prologue'),
    (0x4ee1cc, 0x3c1c0051, 'addPlayList prologue'), (0x4ee1d0, 0x279c5d04, 'addPlayList prologue'), (0x4ee1d4, 0x0399e021, 'addPlayList prologue'),
    (0x4db34c, 0x04114b96, 'batch_add_file (class 0xf00b): bal checkPlayListExist(rec, playlist id)'), (0x4db360, 0x04114b88, 'batch_add_file: bal getPlayListMaxId'),
    (0x4db380, 0x24030064, 'batch_add_file: v1 = 100'), (0x4db384, 0x2a640064, 'batch_add_file: slti a0, max, 100'), (0x4db38c, 0x0264180a, 'batch_add_file: movz v1, max, a0 (max(100, max))'),
    (0x4db3a4, 0xac430000, 'batch_add_file: rec.id (REC_ID) = max(100, max) + 1'), (0x4db3c0, 0xac430040, 'batch_add_file: rec.cd_num (REC_DISC) = the playlist id'),
    (0x4db3d0, 0x8f99b810, 'batch_add_file: lw addPlayList from the GOT (the delay slot of the jump to 0x4daff8)'), (0x4daff8, 0x0320f809, 'batch_add_file: jalr addPlayList(rec)'),
)
# Stock data the payload reads or writes, by absolute address. Exported objects are checked
# against .dynsym; the two unnamed ones carry the code that proves them.
DATA = {
    'PDEQ_SHOWLIST':      (0xa045d8, 'pdeq_showlist'),   # deque_t * of the loaded list
    'PARSE_COVER_MUTEX':  (0xa04588, 'parse_cover_mutex'),  # the lock every stock art caller holds
    # g_class_type: albuminfo_page_init stores classinfo[0] (0xff10) there @0x5268ec, and the row
    # handler passes it to loadSongList and playing_page @0x5275a4.
    'G_CLASS_TYPE':       (0x97cad4, None),
    # the stock browsing record loadAlbumdetailList fills (@0x4eeac8); its first word is the class.
    'CLASSINFO':          (0xa0c768, None),
    # the stock Artists page's artist / album artist switch (handler @0x535770): toggles the word, saves
    # [PLAYSET] ARTISTTYPE and sets the byte (the stock page's list-reload flag, read @0x535fe8)
    'ARTIST_TYPE':        (0xa05a14, None),
    'ARTIST_RELOAD':      (0xa06d20, None),
    # set to 1 by the stock Play all handler (@0x525e64) after start_player; the Shuffle button does the same
    'FORCE_REFRESH':      (0xa05a63, 'force_refreshflag'),
    # songerinfoflag: the album row handler @0x52569c opens Now Playing through its pop loop only when this byte is set
    # (read @0x5258c8; also referenced by album_page_init @0x52511c, airplay_page_init and the msginfo dialog)
    'SONGER_FLAG':        (0xa04737, 'songerinfoflag'),
    # the cover source type: parseplaycover_thd sets 1 (busy), 2 / 3 / 5 (a /tmp JPEG), the Now Playing cover loader
    # @0x53a5d8 reads it (`lw s1, 0x97cad8; lw v1, (s1); bne v1, 2 ...`, @0x53a6a8)
    'COVER_SRC':          (0x97cad8, None),
    # the play queue: a deque_t * (stSongInfo rows, the queue start_player copied). Every reader pairs it with
    # mclGetPlayPos: get_playtimeandlength `lw s1, 0xa0394c; deque_size(*s1)` then `deque_at(*s1, pos)` (@0x4e01cc..0x4e0268),
    # the lock screen refresh (@0x53f73c, "queued" = 0 <= pos < size), the queue drawer (@0x47a8f0)
    'PLAY_QUEUE':         (0xa0394c, None),
    # the menu's list (patch/menu.c mn_plain_paint): g_scroll_view_vtable is a widget's vtable word (+0x70) when it is a scroll_view;
    # 0x60c164 is the paint-children hook list_view_on_add_child (0x60cc08) stores in a scroll_view (@0x60cd04..0x60cd10,
    # `addiu v1, v1, -0x3e9c`; its prologue `lui gp, 0x3f; addiu gp, gp, 0x7d6c`, test/pod/pulldown.py pins both words)
    'SV_VTABLE':          (0x97a298, 'g_scroll_view_vtable'),
    'LV_PAINT_HOOK':      (0x60c164, None),
    # the Playlists page (patch/playlists.c): the stock playlist list (loadLocalClassList(0xf00b) assigns it, @0x4ee63c), the title the
    # Songs page shows (allmusic_page_init strcpy's it @0x528a74; the Playlists row handler snprintf's the name into it @0x53d5b8) and
    # navigation_status (0 = normal, 1 = the multi-select mode of the lists: the stock export reads it @0x53ddc0)
    'PDEQ_PLAYLIST':      (0xa045d0, 'pdeq_playlist'),
    'NAV_TITLE':          (0xa0533c, 'nagvation_title'),
    'NAVIGATION_STATUS':  (0xa05a24, 'navigation_status'),
    # the Songs page (patch/songs.c): sort_flag, the list order of class 0xf001 (0 alphabetical, 1 file name, 2 file format, 3 newest first, 4 oldest first;
    # getAllMusic dispatches on it, config_init reads it from [SYSSET] SORTSELECT, the sort dialog's row handler @0x47d114 stores it and writes the key)
    'SORT_FLAG':          (0xa059d4, 'sort_flag'),
    # the stock multi-select's selection: a pointer to a vector<int> (created once at start-up, ~0x50bb34) indexed by the row of *pdeq_showlist, 1 = selected
    'SEL_VEC':            (0xa045e0, None),
}
LIBC = {
    'atoi': ('int', 'const char *'), 'access': ('int', 'const char *, int'),
    # the Daily Mix's day number (patch/dailymix.c dm_today): the wall clock and its local calendar fields (struct tm: seconds, minutes, hours, mday, mon, year first)
    'time': ('long', 'long *'), 'localtime': ('const int *', 'const long *'),
    # Home (patch/home.c): the marker, the setting and the opt-in log
    'open': ('int', 'const char *, int, int'), 'read': ('int', 'int, void *, unsigned'),
    'write': ('int', 'int, const void *, unsigned'), 'close': ('int', 'int'), 'fsync': ('int', 'int'),
    # Cover Flow: the thumbnail cache, its one worker thread and the album/track deques
    'memset': ('void *', 'void *, int, unsigned'), 'memcpy': ('void *', 'void *, const void *, unsigned'),
    'strcmp': ('int', 'const char *, const char *'), 'strdup': ('char *', 'const char *'),
    'snprintf': ('int', 'char *, unsigned, const char *, ...'),
    'calloc': ('void *', 'unsigned, unsigned'), 'free': ('void', 'void *'),
    'fopen': ('void *', 'const char *, const char *'), 'fclose': ('int', 'void *'),
    'fread': ('unsigned', 'void *, unsigned, unsigned, void *'),
    'fwrite': ('unsigned', 'const void *, unsigned, unsigned, void *'),
    'fseek': ('int', 'void *, long, int'), 'ftell': ('long', 'void *'),
    'rename': ('int', 'const char *, const char *'), 'unlink': ('int', 'const char *'),
    'mkdir': ('int', 'const char *, unsigned'), 'statfs': ('int', 'const char *, void *'),
    'pthread_create': ('int', 'unsigned long *, const void *, void *(*)(void *), void *'),
    'pthread_join': ('int', 'unsigned long, void **'),
    'pthread_mutex_lock': ('int', 'void *'), 'pthread_mutex_unlock': ('int', 'void *'),
    '_create_deque': ('void *', 'const char *'), 'deque_init': ('void', 'void *'),
    'deque_assign': ('void', 'void *, const void *'), 'deque_size': ('unsigned', 'const void *'),
    'deque_at': ('void *', 'const void *, unsigned'), 'deque_destroy': ('void', 'void *'),
    # Artists and the artist-scoped Cover Flow (patch/artists.c, patch/coverflow.c)
    'strcasecmp': ('int', 'const char *, const char *'), '_deque_push_back': ('void', 'void *, const void *'),
    # Screenshot (patch/shot.c): the frame buffer, as stock's lcd_linux_fb_create calls them (ioctl 0x4600 / 0x4602, mmap)
    'ioctl': ('int', 'int, unsigned, void *'), 'mmap': ('void *', 'void *, unsigned, int, int, int, int'),
    'munmap': ('int', 'void *, unsigned'),
}


# ---- List gestures (patch/scroll.c, docs/architecture.md "List gestures") --------------------------------------------
# Not a code hook: widget_on_event_before_children (0x666c34) calls vtable[0x98] of a widget with every pointer event
# before its children see it, and g_scroll_view_vtable's slot is zero in stock (a no-op). The build writes
# m1plus_scroll_event into that one data word. The stock functions and fields the payload relies on are pinned below.
SCROLL_VTABLE = 0x97a298            # g_scroll_view_vtable (.dynsym)
SCROLL_SLOT = SCROLL_VTABLE + 0x98  # on_event_before_children: 0 in stock
SCROLL_DONE = 0x6101b8              # scroll_view's EVT_ANIM_END handler (static): wa = 0, the scroll end events; ret_t (ctx = widget, event)
FUNCTIONS.update({
    'widget_dispatch':         ('int', 'void *, void *', 0x66cec8),
    'widget_dispatch_event_to_target_recursive': ('int', 'void *, void *', 0x66e08c),
    'widget_animator_destroy': ('int', 'void *', 0x6735ac),
})
# (address, stock word, what it proves). Vtable words are data, the rest instructions.
SCROLL_PINS = (
    (SCROLL_VTABLE, 0x118, 'scroll_view_t size'), (SCROLL_VTABLE + 0x14, 0x97c0d8, 'parent vtable (widget)'),
    (SCROLL_VTABLE + 0x1c, 0x6113c4, 'create = scroll_view_create'), (SCROLL_VTABLE + 0x94, 0x610724, 'on_event = scroll_view_on_event'),
    (SCROLL_SLOT, 0, 'on_event_before_children is empty'), (SCROLL_SLOT + 4, 0, 'the next slot is empty'),
    (0x666c44, 0x8c820070, 'widget_on_event_before_children: lw v0, 0x70(a0) (vt)'),
    (0x666c50, 0x8c590098, 'widget_on_event_before_children: lw t9, 0x98(vt)'), (0x666c5c, 0x03200008, 'widget_on_event_before_children: jr t9'),
    (0x67131c, 0x0411d645, 'widget_on_pointer_down: bal widget_on_event_before_children'),
    (0x671324, 0x10510041, 'widget_on_pointer_down: RET_STOP ends the DOWN'),
    (0x67169c, 0x0411d565, 'widget_on_pointer_move: bal widget_on_event_before_children'),
    (0x671924, 0x0411d4c3, 'widget_on_pointer_up: bal widget_on_event_before_children (before the children @0x671990)'),
    (0x66cf2c, 0x8c590094, 'widget_dispatch: lw t9, 0x94(vt) (on_event)'),
    (0x66e0bc, 0x8c90004c, 'widget_dispatch_event_to_target_recursive starts at the grab widget'),
    (0x66e0c8, 0x8c900048, 'and then at the target'),
    (0x610724, 0x3c1c003f, 'scroll_view_on_event prologue'), (0x610728, 0x279c37ac, 'scroll_view_on_event prologue'),
    (0x61072c, 0x0399e021, 'scroll_view_on_event prologue'),
    (0x61083c, 0xa61200a0, 'on_event DOWN: sh 1, 0xa0 (pressed = 1, dragged = 0)'),
    (0x61086c, 0xae020098, 'on_event DOWN: down x'), (0x61087c, 0xae02009c, 'on_event DOWN: down y'),
    (0x6108c4, 0x920200a0, 'on_event UP: lbu pressed'), (0x610c34, 0xa20200a1, 'on_event MOVE: sb dragged = 1'),
    (0x610680, 0x90830090, 'is_dragged: xslidable'), (0x610688, 0x90820091, 'is_dragged: yslidable'),
    (0x610694, 0x8c820098, 'is_dragged: down x'), (0x61069c, 0x8c85009c, 'is_dragged: down y'),
    (0x6106cc, 0x90820092, 'is_dragged: snap_to_page'), (0x6106e0, 0x2863000a, 'is_dragged: threshold 10'),
    (0x610548, 0xae0400e8, 'scroll_view_scroll_to: wa = the new animator'),
    (0x6101b8, 0x3c1c003f, 'scroll end handler prologue'), (0x6101bc, 0x279c3d18, 'scroll end handler prologue'),
    (0x6101c0, 0x0399e021, 'scroll end handler prologue'), (0x610208, 0xae2000e8, 'scroll end handler: wa = 0'),
    (0x673114, 0x8e020028, 'widget_animator_start: lw state'), (0x673118, 0x24030001, 'widget_animator_start: 1 = running'),
    (0x673258, 0x8e040004, 'widget_animator_stop: lw widget (@4)'),
    (0x6735d0, 0x8c830048, 'widget_animator_destroy: lw destroy flag (@0x48)'),
)


# ---- Now Playing's More dialog (patch/playmore.c, docs/modules/playmore.md) -------------------------------------------
# dialog_playmore_dialog_init, the init of dialog/playmore_dialog: called only by the navigator's dialog-init dispatcher
# (0x4d1244 .. 0x4d124c, behind the strcmp with "dialog/playmore_dialog"), when Now Playing's More button opens the dialog.
# m1plus_playmore_init runs the stock init to completion (it binds every row and pins the dialog at y 130), then re-orders
# the rows; any mismatch leaves the stock menu.
PLAYMORE_INIT = 0x479cc4
PLAYMORE_INIT_PROLOGUE = (0x3c1c0059, 0x279ca20c, 0x0399e021)
PLAYMORE_PINS = (   # (address, stock word, what it proves)
    (0x479cd0, 0x10800059, 'init: beqz a0 (the trampoline resumes here)'),
    (0x479d10, 0x24060082, 'init: widget_move(dialog, 0, 130): the sheet is pinned at y 130'),
    (0x4d1238, 0x24a59f78, 'dispatcher: "dialog/playmore_dialog" string'),
    (0x4d1244, 0x8f99b5d4, 'dispatcher: loads dialog_playmore_dialog_init from the GOT'),
    (0x4d124c, 0x0320f809, 'dispatcher: jalr t9'),
    (0x478ac8, 0x8c830004, 'tap handler: dialog->y'), (0x478acc, 0x8ca2001c, 'tap handler: pointer_event y (a tap above the sheet closes it)'),
    (0x479ce0, 0x2405012c, 'init: widget_on(dialog, EVT_WINDOW_TO_BG 0x12c, 0x4789f0): the stock to-background handler, on the dialog'),
    (0x478a1c, 0x24060082, 'to-background handler 0x4789f0: widget_move(dialog, 0, 130), which our handler undoes'),
    # why ours is bound on the list_view and not on the dialog: a handler bound later on the dialog would run before the stock one
    (0x6f466c, 0xac430020, 'emitter_on_with_tag: new->next = emitter->items'),
    (0x6f4670, 0xae020000, 'emitter_on_with_tag: emitter->items = new (a handler goes to the head: the newest runs first)'),
    (0x6f45a0, 0x00009825, 'emitter_dispatch: RET_OK after the last handler (the dialog\'s window event goes on to its children)'),
    (0x678870, 0x0411c0c3, 'window_manager_dispatch_window_event: bal widget_dispatch_recursive (the window event reaches the children)'),
    (0x668ae4, 0x0320f809, 'widget_foreach: visit(widget) first'),
    (0x668af0, 0x1440000b, 'widget_foreach: then its children, if the visit returned RET_OK (the dialog before its list_view)'),
    (0x60c53c, 0x1443fff6, 'list_view_on_event: RET_OK for an event it does not handle (0x12c reaches the list_view\'s emitter)'),
)


def patch_playmore(image, ps, payload_len):
    target = ps['m1plus_playmore_init']
    check(BASE <= target < BASE + payload_len, 'playmore entry symbol outside payload')
    for a, old, what in PLAYMORE_PINS:
        got = struct.unpack_from('<I', image, fileoff(image, a))[0]
        check(got == old, f'{a:#x} ({what}): {got:#010x} != pinned {old:#010x}')
    hook(image, PLAYMORE_INIT, PLAYMORE_INIT_PROLOGUE, target, 'dialog_playmore_dialog_init')


def gen_scroll_h(out):
    (pathlib.Path(out) / 'scroll.h').write_text(
        '/* Generated by tools/pod.py; do not edit. */\n#pragma once\n'
        f'#define stock_scroll_done ((int (*)(void *, void *))0x{SCROLL_DONE:x}u)\n')


def sha(b): return hashlib.sha256(b).hexdigest()
def j(addr): return 0x08000000 | (addr >> 2)
def check(cond, msg):
    if not cond: raise ValueError(msg)


def segments(b):
    phoff = struct.unpack_from('<I', b, 28)[0]
    size, num = struct.unpack_from('<HH', b, 42)
    check(size == 32, 'unexpected program header size')
    return [(phoff + i * size, struct.unpack_from('<8I', b, phoff + i * size)) for i in range(num)]


def fileoff(b, a):
    for _, (t, o, v, _, f, _, _, _) in segments(b):
        if t == 1 and v <= a < v + f: return o + a - v
    raise ValueError(f'unmapped address {a:#x}')


def dynsym(path):
    out = {}
    with open(path, 'rb') as f:
        elf = ELFFile(f)
        sec = elf.get_section_by_name('.dynsym')
        for s in sec.iter_symbols():
            if s['st_value'] and s.name: out.setdefault(s.name, s['st_value'])
    return out


def got_slots(path, names):
    """Absolute GOT slot address for each wanted imported libc function."""
    with open(path, 'rb') as f:
        elf = ELFFile(f)
        dynsymsec = elf.get_section_by_name('.dynsym'); got = elf.get_section_by_name('.got')
        tags = {t.entry.d_tag: t.entry.d_val for t in elf.get_section_by_name('.dynamic').iter_tags()}
        local, gotsym = tags['DT_MIPS_LOCAL_GOTNO'], tags['DT_MIPS_GOTSYM']
        n = dynsymsec.num_symbols()
        slot = {}
        for i in range(gotsym, n):
            nm = dynsymsec.get_symbol(i).name
            if nm in names: slot[nm] = got['sh_addr'] + 4 * (local + i - gotsym)
    missing = set(names) - set(slot)
    check(not missing, f'libc not imported by demo: {sorted(missing)}')
    return slot


def gen_stock_h(out, demo_path):
    syms = dynsym(demo_path)
    slots = got_slots(demo_path, LIBC)
    h = ['/* Generated by tools/pod.py from demo .dynsym; do not edit. */', '#pragma once']
    for name, (ret, args, addr) in FUNCTIONS.items():
        check(syms.get(name) == addr, f'{name}: address {syms.get(name)} != pinned {addr:#x}')
        h.append(f'#define {name} (({ret} (*)({args}))0x{addr:x}u)')
    for name, (ret, args) in LIBC.items():
        h.append(f'extern {ret} pod_lib_{name}({args});')
        h.append(f'#define {name} pod_lib_{name}')
    for name, (addr, sym) in DATA.items():
        if sym is not None:
            check(syms.get(sym) == addr, f'{sym}: address {syms.get(sym)} != pinned {addr:#x}')
        h.append(f'#define {name} 0x{addr:x}u')
    h.append(f'#define STOCK_HOME_CLICK 0x{HOME_CLICK:x}u')   # the icon click handler stock registers per icon
    h.append(f'#define POD_ENTRY_NAME "{pod_pages.HOME_ENTRY}"')   # the added icon's widget name (a decimal id, as stock's)
    h.append(f'#define stock_playlist_import ((int (*)(void *, void *))0x{PLAYLIST_IMPORT:x}u)')   # the stock Playlists page's Import / Export rows
    h.append(f'#define stock_playlist_export ((int (*)(void *, void *))0x{PLAYLIST_EXPORT:x}u)')
    h.append('extern int stock_home_click_trampoline(void *, void *);')
    h.append('extern void stock_albuminfo_header_trampoline(void *);')
    h.append('extern int stock_playing_init_trampoline(void *, void *);')
    h.append('extern int stock_playmore_init_trampoline(void *, void *);')
    h.append('extern int coverflow_open(void);')
    h.append('extern int coverflow_rebuild(void);')
    h.append('extern int coverflow_landscape(void);')
    h.append('extern int coverflow_landscape_toggle(void);')
    # the customisable menu (patch/menu.c): its item count, the default shown prefix and the row geometry
    h.append(f'#define POD_MENU_ITEMS {len(pod_pages.ITEMS)}')
    h.append(f'#define POD_MENU_DEFAULT {len(pod_pages.DEFAULT_MENU)}')   # the default menu: this many items ...
    h.append('#define POD_MENU_DEFAULT_IDS {' + ', '.join(str(i) for i in pod_pages.DEFAULT_MENU) + '}')   # ... these item ids, in order
    h.append(f'#define POD_MENU_FILE_MAX {pod_pages.MENU_FILE_MAX}')
    h.append(f'#define POD_MENU_ROWS {len(pod_pages.MENU.rows)}')
    h.append(f'#define POD_CUSTOMIZE_ID {pod_pages.CUSTOMIZE_ID}')
    h.append(f'#define POD_EXTRAS_ROWS {len(pod_pages.EXTRAS_PAGE.rows)}')
    h.append('#define POD_EXTRAS_ORDER {' + ', '.join(str(i) for i in pod_pages.EXTRAS_ORDER) + '}')   # the Extras page's rows (item ids) top to bottom
    h.append(f'#define POD_EXTRAS_GROUPS {len(pod_pages.EXTRAS_GROUPS)}')   # the Extras page's titled groups (section headers pod_hdr0 ..) ...
    h.append('#define POD_EXTRAS_GROUP {' + ', '.join(str(g) for g in pod_pages.EXTRAS_GROUP_OF) + '}')   # ... the group of each item id ...
    h.append(f'#define POD_EXTRAS_HDR_H {pod_pages.HDR_H}')   # ... and a header's height
    h.append(f'#define POD_ROW_H {pod_ui.ROW_H}')
    # the Songs rail's alignment, from the tree's own font (tools/pod_ui.py rail_metrics): twice the cap ink's centre within an item, and each letter's rect shift
    ink2, dx = pod_ui.rail_metrics(os.path.join(os.path.dirname(os.path.dirname(demo_path)), 'assets/default/raw/fonts/default.ttf'))
    h.append(f'#define SG_RAIL_INK2 {ink2}')
    h.append('#define SG_RAIL_DX {' + ', '.join(str(d) for d in dx) + '}   /* "#", A..Z */')
    h.append('extern int shuffle_play(int);')
    (out / 'stock.h').write_text('\n'.join(h) + '\n')
    # The page and row tables, included by patch/m1plus.c alone.
    h = ['/* Generated by tools/pod.py from tools/pod_pages.py; do not edit. */', '#pragma once']
    pages = pod_pages.PAGES
    for pi, page in enumerate(pages):
        if page.rows:
            h.append(f'static const struct pod_row pod_rows_{pi}[] = {{')
            for ri, r in enumerate(page.rows):
                h.append(f'    {{"pod_row{ri}", {r.action}, {r.arg}}},')
            h.append('};')
    h.append('static const struct pod_page POD_PAGES[] = {')
    for pi, page in enumerate(pages):
        rows = f'pod_rows_{pi}' if page.rows else '0'
        h.append(f'    {{"{page.key}", {rows}, {len(page.rows)}}},')
    h.append('};')
    h.append(f'#define POD_PAGE_COUNT {len(pages)}')
    h.append(f'#define POD_ENTRY_ID {pod_pages.HOME_ENTRY}')
    h.append('#define POD_ENTRY_PAGE 0')
    h.append('#define POD_MENU_PAGE 0')
    h.append(f'#define POD_CUSTOMIZE_PAGE {pod_pages.CUSTOMIZE_PAGE_INDEX}')
    h.append(f'#define POD_EXTRAS_PAGE {pod_pages.EXTRAS_PAGE_INDEX}')
    h.append(f'#define POD_MENUCFG_PAGE {pod_pages.MENUCFG_PAGE_INDEX}')
    h.append(f'#define POD_EXTRASCFG_PAGE {pod_pages.EXTRASCFG_PAGE_INDEX}')
    h.append(f'#define POD_DEVELOPER_PAGE {pod_pages.DEVELOPER_PAGE_INDEX}')
    (out / 'pages.h').write_text('\n'.join(h) + '\n')
    return slots


def gen_asm(out, slots):
    # $gp-restoring trampoline that resumes the stock dispatcher past its 3-word PIC prologue.
    asm = ['.set noreorder', '.text',
           '.globl stock_home_click_trampoline', 'stock_home_click_trampoline:',
           f'lui $gp, {GP >> 16}', f'ori $gp, $gp, {GP & 0xffff}', f'j 0x{HOME_CLICK + 12:x}', 'nop']
    # the same for home_page_init
    asm += ['.globl stock_home_init_trampoline', 'stock_home_init_trampoline:',
            f'lui $gp, {GP >> 16}', f'ori $gp, $gp, {GP & 0xffff}', f'j 0x{HOME_INIT + 12:x}', 'nop']
    # and for the album page's header builder
    asm += ['.globl stock_albuminfo_header_trampoline', 'stock_albuminfo_header_trampoline:',
            f'lui $gp, {GP >> 16}', f'ori $gp, $gp, {GP & 0xffff}', f'j 0x{ALBUMINFO_HEADER + 12:x}', 'nop']
    # and for the Now Playing page's init
    asm += ['.globl stock_playing_init_trampoline', 'stock_playing_init_trampoline:',
            f'lui $gp, {GP >> 16}', f'ori $gp, $gp, {GP & 0xffff}', f'j 0x{PLAYING_INIT + 12:x}', 'nop']
    # and for the Now Playing More dialog's init
    asm += ['.globl stock_playmore_init_trampoline', 'stock_playmore_init_trampoline:',
            f'lui $gp, {GP >> 16}', f'ori $gp, $gp, {GP & 0xffff}', f'j 0x{PLAYMORE_INIT + 12:x}', 'nop']
    # libc GOT-slot stubs (load the resolved pointer from demo's own GOT, tail-call it).
    for name, addr in slots.items():
        asm += [f'.section .text.pod_lib_{name},"ax",@progbits', f'.globl pod_lib_{name}', f'pod_lib_{name}:',
                f'lui $t8, {addr >> 16}', f'ori $t8, $t8, {addr & 0xffff}', 'lw $t9, 0($t8)', 'jr $t9', 'nop']
    (out / 'pod_asm.S').write_text('\n'.join(asm) + '\n')


def run(*args): subprocess.run([str(a) for a in args], check=True)


def symbols_elf(path):
    out = {}
    text = subprocess.check_output([os.path.join(LLVM, 'llvm-readelf'), '-sW', str(path)], text=True)
    for line in text.splitlines():
        f = line.split()
        if len(f) >= 8 and f[0].endswith(':'):
            try: out[f[7]] = int(f[1], 16)
            except ValueError: pass
    return out


def compile_payload(out, demo_path):
    out = pathlib.Path(out)
    slots = gen_stock_h(out, demo_path)
    gen_scroll_h(out)
    gen_asm(out, slots)
    objs = []
    for src in SOURCES:
        obj = out / (src + '.o')
        run(CLANG, *FLAGS, '-I', out, '-I', PATCH, '-c', os.path.join(PATCH, src), '-o', obj)
        objs.append(obj)
    run(CLANG, *FLAGS, '-c', out / 'pod_asm.S', '-o', out / 'pod_asm.o')
    # compact_set_row_layout is reached only from the patched stock call sites, so keep it
    keep = ['--undefined=compact_set_row_layout', '--undefined=m1plus_home_init',
            '--undefined=stock_home_init_trampoline', '--undefined=m1plus_albuminfo_header',
            '--undefined=stock_albuminfo_header_trampoline', '--undefined=m1plus_playing_init',
            '--undefined=stock_playing_init_trampoline', '--undefined=m1plus_scroll_event',
            '--undefined=m1plus_playmore_init', '--undefined=stock_playmore_init_trampoline']
    run(LD, '-m', 'elf32ltsmip', '--gc-sections', '-T', os.path.join(PATCH, 'link.ld'),
        '-e', 'm1plus_home_click', '--undefined=m1plus_home_click', '--undefined=stock_home_click_trampoline',
        *keep, *objs, out / 'pod_asm.o', '-o', out / 'patch.elf')
    run(OBJCOPY, '-O', 'binary', out / 'patch.elf', out / 'patch.bin')
    ps = symbols_elf(out / 'patch.elf')
    payload = (out / 'patch.bin').read_bytes()
    # The payload is position-fixed and its segment is file-backed from end to end: writable state
    # lives in .scratch, which the compiler emits as zero-filled PROGBITS (so it is in patch.bin and
    # memsz == filesz); a non-empty .bss would need memory past the file image, so it is refused.
    scratch = 0
    with open(out / 'patch.elf', 'rb') as f:
        for sec in ELFFile(f).iter_sections():
            if sec.name in ('.bss', '.sbss') and sec['sh_size']:
                raise ValueError(f'payload has non-empty {sec.name}; put writable state in .scratch')
            if sec.name == '.scratch':
                scratch = sec['sh_size']
                check(sec['sh_type'] == 'SHT_PROGBITS', '.scratch must be file-backed (PROGBITS)')
                off = sec['sh_addr'] - BASE
                check(0 <= off and off + scratch <= len(payload), '.scratch outside the payload')
                check(not any(payload[off:off + scratch]), '.scratch must start zeroed')
    return ps, payload, scratch


def append_payload(image, payload, base):
    """Rewrite demo's final PT_NULL header into a file-backed PT_LOAD (RWX) mapping payload at base."""
    segs = segments(image)
    nulls = [(o, p) for o, p in segs if p[0] == 0]
    check(len(nulls) == 1 and nulls[0][0] == segs[-1][0], 'no final PT_NULL slot')
    check(all(p[2] + p[5] <= base for _, p in segs if p[0] == 1), 'payload mapping overlaps a LOAD segment')
    off = (len(image) + 0xffff) & ~0xffff
    image.extend(bytes(off - len(image)))
    image.extend(payload)
    struct.pack_into('<8I', image, nulls[0][0], 1, off, base, base, len(payload), len(payload), 7, 0x10000)
    return off


# The library rows (patch/rows.c): pinned call-site and immediate
# edits of the stock row constructors, listed in patch/rows.json. Not hooks: no prologue changes;
# the one hook stays HOME_CLICK.
ROWS_JSON = os.path.join(PATCH, 'rows.json')
JALR_T9 = 0x0320f809
ROW_LAYOUT_STRINGS = {0x745158: b'default(r=1,c=0,x=12,s=8)\0', 0x745360: b'default(r=1,c=0,x=0,s=8)\0'}
DEFAULT_LAYOUT_VTABLE, DEFAULT_LAYOUT_FN = 0x904924, 0x63a444   # patch/offsets.inc (patch/rows.c copies it)


def jal(addr, at):
    check((addr & 0xf0000000) == ((at + 4) & 0xf0000000) and addr % 4 == 0, f'{at:#x}: jal target out of range')
    return 0x0c000000 | ((addr >> 2) & 0x03ffffff)


def patch_rows(image, ps):
    """Apply patch/rows.json to image (bytearray) in place; every word checked first. Returns the
    list of changes [address, old, new, kind]."""
    J = json.load(open(ROWS_JSON))
    target = ps.get('compact_set_row_layout')
    check(target is not None, 'payload has no compact_set_row_layout')
    edits, seen = [], set()
    def at(a, old):
        check(a not in seen, f'{a:#x}: listed twice'); seen.add(a)
        got = struct.unpack_from('<I', image, fileoff(image, a))[0]
        check(got == old, f'{a:#x}: {got:#010x} != pinned {old:#010x}')
    for g in J['immediates']:
        v = g['value']; check(0 <= v < 0x8000, f'bad immediate {v}')
        for a, old, *_ in g['sites']:
            a, old = int(a, 16), int(old, 16)
            if old & 0xffff07ff in (0x21, 0x25):   # move rd, $zero (addu / or rd, $zero, $zero) -> addiu rd, $zero, imm
                new = 0x24000000 | ((old >> 11) & 31) << 16 | v
            else:
                check(old >> 26 == 9 and (old >> 21) & 31 == 0, f'{a:#x}: not addiu rt, $zero, imm nor move rd, $zero')
                new = (old & 0xffff0000) | v
            at(a, old); edits.append((a, old, new, 'immediate'))
    for a, old, *_ in J['row_layout_calls']['sites']:
        a, old = int(a, 16), int(old, 16)
        check(old == JALR_T9, f'{a:#x}: not jalr $t9'); at(a, old)
        edits.append((a, old, jal(target, a), 'call'))
    for a, old, *_ in J['nops']['sites']:
        a, old = int(a, 16), int(old, 16)
        check(old == JALR_T9, f'{a:#x}: not jalr $t9'); at(a, old)
        edits.append((a, old, 0, 'nop'))
    icon = ps.get('rows_track_icon')
    check(icon is not None, 'payload has no rows_track_icon')
    for a, old, *_ in J['icon_calls']['sites']:
        a, old = int(a, 16), int(old, 16)
        check(old == JALR_T9, f'{a:#x}: not jalr $t9'); at(a, old)
        edits.append((a, old, jal(icon, a), 'icon'))
    number = ps.get('rows_track_number')
    check(number is not None, 'payload has no rows_track_number')
    for a, old, *_ in J['text_calls']['sites']:
        a, old = int(a, 16), int(old, 16)
        check(old == JALR_T9, f'{a:#x}: not jalr $t9'); at(a, old)
        edits.append((a, old, jal(number, a), 'text'))
    for g in J['pinned']:
        for a, old, *_ in g['sites']:
            at(int(a, 16), int(old, 16))
    for a, text in ROW_LAYOUT_STRINGS.items():   # the shared layout strings stay as they are
        off = fileoff(image, a); check(bytes(image[off:off + len(text)]) == text, f'{a:#x}: layout string changed')
    off = fileoff(image, DEFAULT_LAYOUT_VTABLE + 8)
    check(struct.unpack_from('<I', image, off)[0] == DEFAULT_LAYOUT_FN, 'default layouter vtable slot 2 moved')
    for a, old, new, _ in edits:
        struct.pack_into('<I', image, fileoff(image, a), new)
    return [[hex(a), hex(old), hex(new), kind] for a, old, new, kind in edits]


def hook(patched, addr, prologue_pinned, target, what):
    """Overwrite the 3-word PIC prologue at addr with `j target; nop`, after checking it and the
    $gp it computes."""
    off = fileoff(patched, addr)
    prologue = struct.unpack_from('<III', patched, off)
    check(prologue == prologue_pinned, f'{what} prologue mismatch: {[hex(x) for x in prologue]}')
    low = prologue_pinned[1] & 0xffff
    gp = ((prologue_pinned[0] & 0xffff) << 16) + (low if low < 0x8000 else low - 0x10000) + addr
    check(gp == GP, f'{what} GOT base {gp:#x} != {GP:#x}')
    struct.pack_into('<II', patched, off, j(target), 0)


def patch_scroll(image, ps, payload_len, demo_path):
    """List gestures: check every pinned word and the vtable symbol, then write m1plus_scroll_event into the (empty)
    on_event_before_children slot of g_scroll_view_vtable. Returns [slot address, old, new]."""
    target = ps['m1plus_scroll_event']
    check(BASE <= target < BASE + payload_len, 'scroll entry symbol outside payload')
    check(dynsym(demo_path).get('g_scroll_view_vtable') == SCROLL_VTABLE, 'g_scroll_view_vtable moved')
    for a, old, what in SCROLL_PINS:
        got = struct.unpack_from('<I', image, fileoff(image, a))[0]
        check(got == old, f'{a:#x} ({what}): {got:#010x} != pinned {old:#010x}')
    struct.pack_into('<I', image, fileoff(image, SCROLL_SLOT), target)
    return [hex(SCROLL_SLOT), '0x0', hex(target)]


def patch_demo(raw, payload, ps, demo_path):
    patched = bytearray(raw)
    target, target2 = ps['m1plus_home_click'], ps['m1plus_home_init']
    check(BASE <= target < BASE + len(payload), 'entry symbol outside payload')
    check(BASE <= target2 < BASE + len(payload), 'home init entry symbol outside payload')
    hook(patched, HOME_CLICK, HOME_CLICK_PROLOGUE, target, 'home click')
    hook(patched, HOME_INIT, HOME_INIT_PROLOGUE, target2, 'home_page_init')
    target3 = ps['m1plus_albuminfo_header']
    check(BASE <= target3 < BASE + len(payload), 'album header entry symbol outside payload')
    hook(patched, ALBUMINFO_HEADER, ALBUMINFO_HEADER_PROLOGUE, target3, 'albuminfo_listitem0_layout')
    target4 = ps['m1plus_playing_init']
    check(BASE <= target4 < BASE + len(payload), 'playing init entry symbol outside payload')
    hook(patched, PLAYING_INIT, PLAYING_INIT_PROLOGUE, target4, 'playing_page_init')
    patch_playmore(patched, ps, len(payload))
    for a, old, what in PLAYLIST_PINS + SONGS_PINS:   # stock code the Playlists and Songs pages call: checked, not written
        got = struct.unpack_from('<I', patched, fileoff(patched, a))[0]
        check(got == old, f'{a:#x} ({what}): {got:#010x} != pinned {old:#010x}')
    edits = patch_rows(patched, ps)
    # no row edit may touch a PIC prologue (the hooks are the only ones) or a hook site
    check(all(not any(h <= int(a, 16) < h + 12 for h in (HOME_CLICK, HOME_INIT, ALBUMINFO_HEADER, PLAYING_INIT, PLAYMORE_INIT))
              for a, *_ in edits), 'row edit on a hook')
    check(all(not (SCROLL_SLOT <= int(a, 16) < SCROLL_SLOT + 4 or a in {hex(p[0]) for p in SCROLL_PINS}) for a, *_ in edits),
          'row edit on a list gesture word')
    scroll = patch_scroll(patched, ps, len(payload), demo_path)
    seg_off = append_payload(patched, payload, BASE)
    return bytes(patched), seg_off, edits, scroll


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir')
    a = ap.parse_args()
    rootfs = os.path.join(a.workdir, 'rootfs')
    demo_path = os.path.join(rootfs, DEMO)
    raw = open(demo_path, 'rb').read()
    check(sha(raw) == ZEROED_DEMO_SHA, f'demo is not the .pdr-zeroed stock V2.1 binary (got {sha(raw)})')
    build = pathlib.Path(a.workdir) / 'podbuild'; build.mkdir(exist_ok=True)
    ps, payload, scratch = compile_payload(build, demo_path)
    patched, seg_off, edits, scroll = patch_demo(raw, payload, ps, demo_path)
    # keep demo's permission bits
    mode = stat.S_IMODE(os.stat(demo_path).st_mode)
    os.chmod(demo_path, mode | 0o200); open(demo_path, 'wb').write(patched); os.chmod(demo_path, mode)
    assets = pod_ui.write_assets(rootfs, pod_pages.PAGES)
    pod_ui.add_shot_indicator(rootfs)     # the hidden camera in ui/system_bar.bin (patch/shot.c)
    manifest = {
        'base': BASE, 'gp': GP, 'payload_len': len(payload),
        'payload_sha256': sha(payload), 'scratch_bytes': scratch, 'entry_symbol': ps['m1plus_home_click'],
        'segment_file_off': seg_off, 'hook': {'addr': HOME_CLICK, 'target': ps['m1plus_home_click']},
        'hook_init': {'addr': HOME_INIT, 'target': ps['m1plus_home_init']},
        'hook_albuminfo': {'addr': ALBUMINFO_HEADER, 'target': ps['m1plus_albuminfo_header']},
        'hook_playing': {'addr': PLAYING_INIT, 'target': ps['m1plus_playing_init']},
        'hook_playmore': {'addr': PLAYMORE_INIT, 'target': ps['m1plus_playmore_init']},
        'scroll_slot': {'addr': SCROLL_SLOT, 'target': ps['m1plus_scroll_event']}, 'scroll_edit': scroll,
        'zeroed_demo_sha256': ZEROED_DEMO_SHA, 'patched_demo_sha256': sha(patched),
        'assets': assets, 'entry_home_id': pod_pages.HOME_ENTRY,
        'row_edits': edits, 'row_fit': ps['compact_set_row_layout'],
    }
    (build / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    print(f'payload {len(payload)} bytes ({scratch} .scratch) @ {BASE:#x} (entry {ps["m1plus_home_click"]:#x}), '
          f'hook @ {HOME_CLICK:#x}, boot guard hook @ {HOME_INIT:#x} (home_page_init), '
          f'album header hook @ {ALBUMINFO_HEADER:#x}, Now Playing init hook @ {PLAYING_INIT:#x}, '
          f'scroll_view before-children slot @ {SCROLL_SLOT:#x} -> {ps["m1plus_scroll_event"]:#x}')
    kinds = {k: sum(e[3] == k for e in edits) for k in ('immediate', 'call', 'nop')}
    print(f'  rows: {len(edits)} pinned edits ({kinds["immediate"]} immediates, {kinds["call"]} row-layout '
          f'calls -> compact_set_row_layout @ {ps["compact_set_row_layout"]:#x}, {kinds["nop"]} rebind resizes nopped)')
    for rel, n in assets: print(f'  asset {rel} ({n} bytes)')


if __name__ == '__main__': main()
