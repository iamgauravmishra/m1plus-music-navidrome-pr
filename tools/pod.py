#!/usr/bin/env python3
"""Compile the M1+ Music payload, install its hook into demo, and add the page assets.

Runs on a workdir that already has the battery, lock screen and space mods applied (so demo's
.pdr is zeroed); it patches that demo and writes the new ui/*.bin. The injection follows q2-pod's
design (its tools/build.py), reduced to the one hook this project needs:

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

A second hook, home_page_init, runs the boot guard (patch/home.c); a third, playing_page_init, tints Now Playing
and shows the remaining time (patch/nowplaying.c). The library rows are pinned
call-site and immediate edits (patch/rows.json). Every patched word and the input demo are pinned
by value/SHA before anything is written.

Usage: pod.py WORKDIR
"""
import argparse, concurrent.futures, hashlib, json, os, pathlib, re, stat, struct, subprocess, sys
from elftools.elf.elffile import ELFFile
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import pod_pages, pod_ui
from build import TAG, about   # the About row of the iPod page shows about(tag) (patch/m1plus.c M1PLUS_TAG)

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
SOURCES = ['m1plus.c', 'common.c', 'menu.c', 'covercache.c', 'coverflow.c', 'albums.c', 'artists.c', 'shuffle.c', 'nowplaying.c', 'minibar.c', 'grid.c', 'recent.c', 'dailymix.c', 'homecover.c', 'covlist.c', 'setfiles.c', 'rows.c', 'shot.c', 'home.c', 'fontregion.c',
           'scroll.c', 'playmore.c', 'playlists.c', 'azlist.c', 'songops.c', 'songs.c', 'albumpage.c', 'queuepage.c', 'ipod.c', 'ipod_cf.c', 'ipod_theme.c', 'ipod_render.c', 'pcmodel.c', 'pcfeed.c', 'pcjson.c', 'pcopml.c', 'pcpng.c', 'pccover.c', 'pcwrap.c', 'pcnotes.c', 'pcdetail.c', 'pcnet.c', 'podcasts.c', 'tape.c', 'vinyl.c', 'onlineart.c', 'keyboard.c', 'search.c', 'battery.c', 'lyrics.c', 'picker.c', 'folders.c']

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

# The third hook (patch/nowplaying.c): playing_page_init, the Now Playing page's init (called by the navigator's
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
    'hscroll_label_set_only_parent_focus': ('int', 'void *, int', 0x6092e8),
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
    'toolsQueryDbTable':       ('int', 'const char *, const char *, void *, int', 0x5ee77c),   # (db, sql, row callback, sort); hooked (pc_library_query), so a call goes through the Library filter
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
    'get_wifisignal':          ('int', 'void', 0x506cc8),        # Podcast network guard: -1 when not connected, else a level 2..5 (networkGetWifiSignal / ConnectStatus / PhysicStatus)
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
    # The album view (patch/covercache.c, patch/songops.c): the stock play sequence, and the cover-task list the stock
    # album page builds before albuminfo_page opens
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
    # The album page's Play all pill (patch/albumpage.c): the translated text (a wchar_t string) and its width
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
# Now Playing opens the way a track row does (the row handler @0x52569c, loop @0x525904..0x5259d8; patch/songops.c
# pod_open_player): the window stack calls
FUNCTIONS.update({
    'navigator_window_is_exist':  ('int', 'const char *', 0x4d2040),
    'navigator_close':         ('int', 'const char *', 0x4d2118),   # closes the named page (Now Playing's Look up album / artist, patch/playmore.c)
    'window_manager_get_top_window': ('void *', 'void *', 0x6775c4),
})
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
    # Saved episodes (patch/podcasts.c pg_save_toggle): the star button's own three calls (manage_myfav 0x4ef884: checkFavExist, then deleteMusicFromFav or addMyFav on the record),
    # on "myfav" in /mnt/data/database.db. A record of ours (name, path, title, album, artist) is enough: a NULL string is skipped by the insert.
    'checkFavExist':           ('int', 'void *', 0x4ee210),                 # (song record): 1 = a row with its filename, fileurl and cue times is in myfav
    'addMyFav':                ('int', 'void *', 0x4ee234),                 # (song record): inserts the row, 1
    'deleteMusicFromFav':      ('int', 'void *', 0x4ede88),                 # (song record): deletes the row (the same key), 1
})
# The Songs page (patch/songs.c, docs/modules/songs.md): the stock multi-select's selection vector (`*0xa045e0`, a vector<int> indexed by the row of
# *pdeq_showlist, 1 = selected: select_recordinit(n) clears it and pushes n zeros, set_selectindex(i) toggles v[i] and returns 1) and the stock batch
# delete (batch_delete_file(class, list, selection, 0, delete_file): the generic loop for 0xf001, deleteMusicFromMusicDb per selected row, remove_file when
# the flag is set, and `*0xa05a5a = 1` at the end). All of them touch no widget (docs/modules/songs.md has the evidence).
FUNCTIONS.update({
    'select_recordinit':       ('void', 'int', 0x4da3b0),
    'set_selectindex':         ('int', 'int', 0x4da434),
    'batch_delete_file':       ('int', 'int, void *, void *, int, int', 0x4e1408),
    # The album page's playing row (patch/albumpage.c): the stock row builder 0x524b50 asks is_playing(g_class_type, the record's CUE start, its file name, its url) for the gold title
    'is_playing':              ('int', 'int, int, const char *, const char *', 0x4d9d64),
    # Battery Percentage (patch/battery.c): stock's bucketed capacity, called first by the hook at show_sysbar_face's call site; it leaves the result in power_capacity (DATA POWER_CAPACITY)
    'get_battery_capacity':    ('int', 'void', 0x4e6dd8),
    # The Queue page (patch/queuepage.c): the queue drawer's row handler 0x479f60 plays row i with start_playqueue(i) (@0x47a0c8: airplay_stop, mclSetPlayPos, mclStartPlayer, notifyPlayStatus; it
    # is told apart from a stream by mclGetPlayType and the network state, @0x479ff4..0x47a028)
    'start_playqueue':         ('int', 'int', 0x4e47d0),
    'mclGetPlayType':          ('int', 'void', 0x5d3658),
    # Now Playing's mode button picture (@0x539888): widget_lookup(window, "btn_playmode"), then the style of mclGetPlayMode()'s mode (btn_imgorder / cycle1 / random / cycle). Stock runs it from the page init and
    # from the button's own click handler 0x53b5fc (mclSetPlayMode, write_int_config, this, notifyPlayMode, dmrSendPlayMode) and nowhere else, so a mode set by another page leaves the picture stale
    # until patch/nowplaying.c calls it again when the page is back in front.
})
NP_MODE_BUTTON = 0x539888   # not a symbol (the stock names there are the neighbouring page's): pinned by SONGS_PINS
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
    (0x4d9d64, 0x3c1c0053, 'is_playing prologue'), (0x4d9d68, 0x279ca16c, 'is_playing prologue'), (0x4d9d6c, 0x0399e021, 'is_playing prologue'),
    (0x524c40, 0x8c460008, 'album row builder 0x524b50: a2 = record + 8 (the file name), the 3rd argument of is_playing'), (0x524c44, 0x8c47000c, 'album row builder: a3 = record + 0xc (the url)'),
    (0x524c48, 0x8c450048, 'album row builder: a1 = record + 0x48 (the CUE start)'), (0x524c4c, 0x8f82ac00, 'album row builder: v0 = &g_class_type (GOT 0x97cad4)'),
    (0x524c54, 0x0320f809, 'album row builder: jalr is_playing'), (0x524c58, 0x8c440000, 'album row builder: a0 = g_class_type (the delay slot)'),
    # The Queue page (patch/queuepage.c): the queue drawer the Now Playing queue button opens (handler 0x53b14c: navigator_to("dialog/playqueue_dialog")), its row marker and its row handler
    (0x53b178, 0x0320f809, 'queue button handler 0x53b14c: jalr navigator_to'), (0x53b17c, 0x24849f90, 'queue button handler: a0 = "dialog/playqueue_dialog" (the delay slot)'),
    (0x47a014, 0x2602fffe, 'row handler 0x479f60: a stream while offline: the play type s0 - 2 < 2 ...'), (0x47a018, 0x2c420002, '... (types 2, 3)'),
    (0x47a020, 0x2602ff10, '... or s0 - 0xf0 < 2'), (0x47a024, 0x2c420002, '... (types 0xf0, 0xf1: the message, no play)'),
    (0x47a0c4, 0x8f99aa9c, 'row handler: t9 = start_playqueue'), (0x47a0c8, 0x0320f809, 'row handler: jalr start_playqueue'), (0x47a0cc, 0x02402025, 'row handler: a0 = the row (move a0, s2)'),
    (0x539888, 0x3c1c004d, 'Now Playing mode button picture prologue'), (0x53988c, 0x279ca648, 'mode button picture prologue'), (0x539890, 0x0399e021, 'mode button picture prologue'),
    (0x5398a8, 0x24a51cc8, 'mode button picture: a1 = "btn_playmode"'), (0x5398cc, 0x0320f809, 'mode button picture: jalr mclGetPlayMode'),
    (0x53b67c, 0x0411f882, 'mode button click handler 0x53b5fc: bal 0x539888 (after mclSetPlayMode and write_int_config)'), (0x53b680, 0x02202025, 'mode button click handler: a0 = the handler\'s own a0 (move a0, s1)'),
    (0x4e47d0, 0x3c1c0052, 'start_playqueue prologue'), (0x4e47d4, 0x279cf700, 'start_playqueue prologue'), (0x4e47d8, 0x0399e021, 'start_playqueue prologue'),
    (0x5d3658, 0x3c1c0043, 'mclGetPlayType prologue'), (0x5d365c, 0x279c0878, 'mclGetPlayType prologue'), (0x5d3660, 0x0399e021, 'mclGetPlayType prologue'),
    (0x5d4290, 0x3c1c0043, 'mclGetPlayPos prologue'), (0x5d4294, 0x279cfc40, 'mclGetPlayPos prologue'), (0x5d4298, 0x0399e021, 'mclGetPlayPos prologue'),
    (0x524c94, 0x8e220048, 'album row builder: a track whose CUE start (+0x48) ...'), (0x524c98, 0x1c400004, '... is > 0 shows its file name (bgtz)'),
    (0x524ca0, 0x8e22004c, 'album row builder: or whose CUE end (+0x4c)'), (0x524ca4, 0x1840001f, '... is > 0 (blez to the title path 0x524d24: record + 0x10, else the file name)'),
)
# The iPod page (patch/ipod.c, docs/modules/ipod.md): the previous-track twin of next_quick_click (same prologue, same 1 s guard on e->time, `prev_music` 0x4e428c in place of
# `next_music` 0x4e4338; the Now Playing button @0x53c1d8 and the hardware key @0x4cdb64 call it with (event, 0)), and the album track query loadAlbumdetailList(class, ROW RECORD)
# (@0x4eea98: its second argument is the album record of the shown list, `lw v0, (a1)` the id and `0x14(a1)` the name; class 0xf003 -> 0xff10, 0xff01 -> 0xff11, 0xff02 -> 0xff14).
# The page's one timer (docs/modules/ipod.md): timer_modify(id, ms) sets the timer's duration (`sw s1, 0x40(s0)`) and its start time, nothing else (fast while the main
# menu's cover pans or Cover Flow slides, 500 ms elsewhere).
FUNCTIONS.update({
    'prev_quick_click':        ('int', 'void *, int', 0x4cccb0),
    'loadAlbumdetailList':     ('int', 'int, void *', 0x4eea98),
    'timer_modify':            ('int', 'unsigned, unsigned', 0x663840),
})
IPOD_PINS = (   # (address, stock word, what it proves)
    (0x4cccb0, 0x3c1c0053, 'prev_quick_click prologue'), (0x4cccb4, 0x279c7220, 'prev_quick_click prologue'), (0x4cccb8, 0x0399e021, 'prev_quick_click prologue'),
    (0x4cccdc, 0x8c850008, 'prev_quick_click: lw a1, 8(a0): the event time (as next_quick_click @0x4ccf2c)'),
    (0x4cccf8, 0x284203e8, 'prev_quick_click: slti v0, v0, 1000: the 1 s guard'),
    (0x4eea98, 0x3c1c0051, 'loadAlbumdetailList prologue'), (0x4eea9c, 0x279c5438, 'loadAlbumdetailList prologue'), (0x4eeaa0, 0x0399e021, 'loadAlbumdetailList prologue'),
    (0x4eeaa8, 0x3402f003, 'loadAlbumdetailList: class 0xf003 (the Albums list)'), (0x4eeab8, 0x00a08825, 'loadAlbumdetailList: s1 = a1 (or s1, a1, zero), the album record'),
    (0x4eeacc, 0x8e220000, 'loadAlbumdetailList: lw v0, (s1): the record id'),
    (0x663840, 0x3c1c003a, 'timer_modify prologue'), (0x663844, 0x279c0690, 'timer_modify prologue'), (0x663848, 0x0399e021, 'timer_modify prologue'),
    (0x66389c, 0xae110040, 'timer_modify: sw s1, 0x40(s0): the timer\'s duration'),
)
# Podcasts (patch/pcmodel.c, docs/modules/podcasts.md "Addresses"): the stock seek and the stock speed.
# seek_time(sec) is the key path's seek commit (the Now Playing slider and the hardware keys call it; q2-pod's player_seek_time): it reads mclGetPlayStatus (1 = stopped: nothing
# happens) and mclGetPlayPos, adds the playing record's CUE start (`lw a0, 0x48(v0)`; 0 for a plain file), sends mclSetSeek (@0x4e0608), resumes a paused player
# (status 3: mclSetResume) and waits, at most 200 times 10 ms, until get_playtimeandlength is within a second of the target. mclSetPlaySpeed(mode) formats
# "{mcl-playspeed\%d}" with its argument (the string @0x756510, sprintf's third argument is `move a2, a0`) and sends it to hciplayer; the stock Multiple Speed page (4 handlers
# @0x4799xx..0x479cxx) stores 3, 2, 1 or 0 in playspeed_mode (0xa05acc), calls mclSetPlaySpeed with it, saves [PLAYSET] PLAYSPEED and restarts the player; config_mplayer
# (@0x4d869c) sends playspeed_mode at the player's set-up; config_init (@0x4e53e4) reads a stored value >= 4 as 0. The pages' images say the modes: 0 1x, 1 1.25x (p_1_25), 2 1.5x (p_1_5), 3 2x (p_2).
FUNCTIONS.update({
    'seek_time':               ('int', 'int', 0x4e0544),
    'mclSetPlaySpeed':         ('int', 'int', 0x5d281c),
    # Podcast downloads (patch/podcasts.c pg_awake_tick): stock's reset_poweroptions_timer(standby, auto_off, screen): a non-zero argument sets that countdown again (standby via setstandby_time, auto power-off via setsavepower_time, the screen's light via setlight_time); the page passes (1, 1, 0)
    'reset_poweroptions_timer': ('void', 'int, int, int', 0x4d7874),
})
# Settings (patch/m1plus.c, docs/modules/settings.md "Stock pages", "Stock state"): navigator_to opens the stock pages; the EQ preset's name is stock's table lookup (a tr key).
FUNCTIONS.update({
    'navigator_to':            ('int', 'const char *', 0x4d1d80),
    'get_equalizer_preset_name': ('int', 'int, char *', 0x49daec),
    # About (docs/modules/settings.md "About"): the card's capacity and free space (statfs, in G as floats), the connection state and the IP address, as the stock About page reads them
    'getDiskMemoryInfo':       ('int', 'const char *, float *, float *', 0x5b30e0),
    'networkGetConnectStatus': ('int', 'void', 0x5d7cac),
    'networkGetIPAddr':        ('int', 'int, char *', 0x5d753c),
})
SETTINGS_PINS = (   # (address, stock word, what it proves)
    # the stock pages: each is a plain navigator_to of the name (the string load is the word before the call's delay slot or the shared call), nothing else set first
    (0x4b1460, 0x0320f809, 'the Wi-Fi hub row (0x4b1448): jalr navigator_to'), (0x4b1464, 0x24848f1c, 'its delay slot: a0 = "systemset/wifi_page"'),
    (0x4b1428, 0x0320f809, 'the Bluetooth hub row (0x4b1410): jalr navigator_to'), (0x4b142c, 0x24848f00, 'its delay slot: a0 = "systemset/bluetooth_page"'),
    (0x4ad830, 0x0320f809, 'the Settings rows\' shared call: jalr navigator_to'), (0x4ada74, 0x24848ab4, 'Settings row 3: a0 = "systemset/display_page"'),
    (0x4ada38, 0x24848a68, 'Settings row 1: a0 = "systemset/fwupdate_page"'),
    (0x4a0068, 0x0320f809, 'the Play Settings rows\' shared call: jalr navigator_to'), (0x4a04a4, 0x248475a0, 'Play Settings row: a0 = "playset/playmode_page"'),
    (0x4a0218, 0x248474d4, 'Play Settings row: a0 = "playset/equalizer_page"'),
    # About: the stock page's values (the widget walk's callback inside what the symbol table calls on_sn_qrcode_onclick, @0x4a1240..0x4a170c; the init 0x4a170c-): the model and firmware version literals, the card
    # numbers (access /tmp/mmc_add, then getDiskMemoryInfo("/mnt/mmc", &cap 0xa03e74, &rem 0xa03e70)), the serial number and the Wi-Fi MAC strings, the IP address
    (0x4a145c, 0x24427718, 'about row 0: v0 = "Shanling M1 Plus" (the model literal)'), (0x4a14cc, 0x2442773c, 'about row 1: v0 = "V2.1" (the firmware version literal)'),
    (0x747718, 0x6e616853, 'the model literal reads "Shan.." (Shanling M1 Plus)'), (0x74773c, 0x312e3256, 'the version literal reads "V2.1"'),
    (0x4a1514, 0xc4403e74, 'about row 2: lwc1 f0, 0x3e74(v0): the card capacity'), (0x4a1634, 0xc4403e70, 'about row 4: lwc1 f0, 0x3e70(v0): the card free space'),
    (0x4a1754, 0x248477a4, 'about init: a0 = "/tmp/mmc_add" (access: the card is in)'), (0x4a177c, 0x24844bd0, 'about init: a0 = "/mnt/mmc" (getDiskMemoryInfo)'),
    (0x4a1778, 0x0320f809, 'about init: jalr getDiskMemoryInfo'), (0x4a1774, 0x26253e74, 'about init: a1 = &capacity (s1 + 0x3e74)'), (0x4a176c, 0x26463e70, 'about init: a2 = &free space (s2 + 0x3e70)'),
    (0x4a16dc, 0x0320f809, 'about row 6: jalr networkGetConnectStatus'), (0x4a16f4, 0x0320f809, 'about row 6: jalr networkGetIPAddr(0, buf), only while it says connected'),
    # EQ: the on/off byte and the preset's name (the toggle handler 0x49d750 and the name lookup)
    (0x49d774, 0x24c670d8, 'eq switch: a2 = "EQFLAG"'), (0x49d77c, 0x24a54264, 'eq switch: a1 = "PLAYSET"'), (0x49d788, 0x90620000, 'eq switch: lbu v0, (v1): equalizer_flag'),
    (0x49d78c, 0x38440001, 'eq switch: xori a0, v0, 1: the flag flipped, saved by write_int_config, stored back'),
    (0x49daec, 0x3c1c0056, 'get_equalizer_preset_name prologue'), (0x49daf0, 0x279c63e4, 'get_equalizer_preset_name prologue'), (0x49daf4, 0x0399e021, 'get_equalizer_preset_name prologue'),
    (0x49daf8, 0x2c83000c, 'get_equalizer_preset_name: sltiu v1, a0, 12: a preset 0..11, else it returns 0'),
    # the Play Mode's value: the keys the stock More dialog sets for mclGetPlayMode's 0, 1, 2, 3 (0x47a454, 0x47a4d4, 0x47a4e8, 0x47a500)
    (0x47a454, 0x24a54ce8, 'more dialog: mode 0 "playmode_listplay"'), (0x47a4d4, 0x24a54cfc, 'more dialog: mode 1 "playmode_repeattrack"'),
    (0x47a4e8, 0x24a54d14, 'more dialog: mode 2 "playmode_shuffle"'), (0x47a500, 0x24a54d28, 'more dialog: mode 3 "playmode_repeatall"'),
)
# Regional CJK forms (patch/fontregion.c, docs/modules/fonts.md "Regional forms"): the font manager, the live "default" font
# (one stb font object for every size: match compares the name only), its glyph cache, and the locale's change event
FUNCTIONS.update({
    'font_manager':            ('void *', 'void', 0x650ad0),
    'font_manager_get_font':   ('void *', 'void *, const char *, int', 0x650dc4),   # lookup, else load and add
    'font_manager_shrink_cache': ('int', 'void *, int', 0x6510b8),   # glyph_cache_shrink of every font; 0 keeps none
    'locale_info_on':          ('int', 'void *, int, void *, void *', 0x658ba8),   # emitter_on(locale + 0x10, 0x122, cb, ctx)
})
FONT_PINS = (   # (address, stock word, what it proves): the stb font layout patch/offsets.inc FONT_* names
    (0x67ef14, 0x240500d4, 'font_stb_create_ex: tk_calloc(1, 0xd4): the font object'),
    (0x67ef48, 0xafc20020, 'font_stb_create_ex: sw match (0x67d2d4) @+0x20'), (0x67ef60, 0xafc20024, 'font_stb_create_ex: sw get_glyph (0x680228) @+0x24'),
    (0x67f030, 0xafd7003c, 'font_stb_create_ex: sw s7 @+0x3c: stbtt_fontinfo data'), (0x67f038, 0xafd60040, 'font_stb_create_ex: sw s6 @+0x40: fontstart'),
    (0x67f74c, 0x02a21021, 'stbtt_InitFont: addu v0, s5, v0: cmap + the record\'s subtable offset'),
    (0x67f758, 0xafc20064, 'stbtt_InitFont: sw v0 @+0x64: index_map (the last record of platform 0 or 3/1, 3/10 wins)'),
    (0x67c3c0, 0x8c870004, 'stbtt_FindGlyphIndex: lw a3, 4(a0): data, read on every lookup'),
    (0x67c3c4, 0x8c88002c, 'stbtt_FindGlyphIndex: lw t0, 0x2c(a0): index_map (fontinfo +0x2c = font +0x64), read on every lookup'),
    (0x680300, 0x02c02025, 'font_stb_get_glyph: move a0, s6: the fontinfo it looks glyphs up in'),
    (0x658970, 0x26120003, 'locale_info_reload: addiu s2, s0, 3: the language at +3'), (0x658978, 0xafb00010, 'locale_info_reload: the country at +0, the second %s'),
    (0x658a7c, 0x24050122, 'locale_info_change: EVT_LOCALE_CHANGED 0x122'), (0x658bc8, 0x24050122, 'locale_info_on: emitter_on with 0x122'),
    (0x66d4bc, 0x2405014a, 'widget_set_theme: EVT_THEME_CHANGED 0x14a, dispatched on the window manager after font_manager_unload_all'),
    (0x74a988, 0x61666564, 'the stock font name "default" (main: system_info_set_default_font)'), (0x74a98c, 0x00746c75, '"default" (cont.)'),
)
ID3_SITE = 0x4dff4c   # get_id3info's jalr strcpy of the parsed path, replaced by jal pc_id3_path (docs/modules/podcasts.md "Tags"); q2-pod's ID3_PATH is the same site in its demo
PODCAST_PINS = (   # (address, stock word, what it proves)
    (0x4e0544, 0x3c1c0052, 'seek_time prologue'), (0x4e0548, 0x279c398c, 'seek_time prologue'), (0x4e054c, 0x0399e021, 'seek_time prologue'),
    (0x4e0560, 0x00808025, 'seek_time: move s0, a0: the target in seconds'),
    (0x4e05f0, 0x8c440048, 'seek_time: lw a0, 0x48(v0): the playing record\'s CUE start'),
    (0x4e05fc, 0x02048021, 'seek_time: addu s0, s0, a0 (delay slot): target + CUE start'),
    (0x4e0608, 0x0320f809, 'seek_time: jalr mclSetSeek'),
    (0x5d281c, 0x3c1c0043, 'mclSetPlaySpeed prologue'), (0x5d2820, 0x279c16b4, 'mclSetPlaySpeed prologue'), (0x5d2824, 0x0399e021, 'mclSetPlaySpeed prologue'),
    (0x4dfd58, 0x3c1c0052, 'get_id3info prologue'), (0x4dfd5c, 0x279c4178, 'get_id3info prologue'), (0x4dfd60, 0x0399e021, 'get_id3info prologue'),
    (0x4dfff8, 0x26250404, 'get_id3info: addiu a1, s1, 0x404: toolsGetMusicInfo(0, id3 + 0x404, path) fills album / artist / title from the tags'),
    (0x4e0000, 0x0320f809, 'get_id3info: jalr toolsGetMusicInfo'),
    (0x4dff40, 0x8f99f324, 'get_id3info: lw t9, GOT strcpy (the call site the tag hook replaces)'), (0x4dff44, 0x8f84aa64, 'get_id3info: lw a0, GOT playsong_id3info'),
    (0x4dff48, 0xae220400, 'get_id3info: sw v0, 0x400(s1): the CUE start into the struct'), (ID3_SITE, 0x0320f809, 'get_id3info: jalr strcpy(info, path): every fresh parse passes it, after toolsGetMusicInfo and the fallbacks of the fields'),
    (0x4dff50, 0x8e05000c, 'get_id3info: lw a1, 0xc(s0) (delay slot): the record\'s path; s0 = the record, s1 = the struct'), (0x4dff58, 0x8f99f524, 'get_id3info: lw t9, GOT memset: song_name / song_artist are built after the site'),
    (0x4dff74, 0x82220684, 'get_id3info: lb v0, 0x684(s1): an empty title takes the file name'), (0x4dffac, 0x82220504, 'get_id3info: lb v0, 0x504(s1): an empty artist takes "Unknown"'),
    (0x5d2830, 0x00803025, 'mclSetPlaySpeed: move a2, a0: the mode is the %d of "{mcl-playspeed\\%d}"'),
    # reset_poweroptions_timer(a0, a1, a2) 0x4d7874 (Podcast downloads keep the device awake with (1, 1, 0)): a0 -> setstandby_time (standby), a1 -> setsavepower_time (auto power-off), a2 -> setlight_time (the screen's light)
    (0x4d7874, 0x3c1c0053, 'reset_poweroptions_timer prologue'), (0x4d7878, 0x279cc65c, 'reset_poweroptions_timer prologue'), (0x4d787c, 0x0399e021, 'reset_poweroptions_timer prologue'),
    (0x4d788c, 0x00c08025, 'reset_poweroptions_timer: move s0, a2 (the screen argument)'), (0x4d7894, 0x00a08825, 'reset_poweroptions_timer: move s1, a1 (the auto power-off argument)'),
    (0x4d7898, 0x10800008, 'reset_poweroptions_timer: beqz a0: the standby countdown is set again only for a non-zero first argument'),
    (0x4d78a8, 0x0411ffe0, 'reset_poweroptions_timer: bal setstandby_time 0x4d782c'),
    (0x4d78bc, 0x12200007, 'reset_poweroptions_timer: beqz s1: auto power-off only for a non-zero second argument'),
    (0x4d78c8, 0x0411ffdc, 'reset_poweroptions_timer: bal setsavepower_time 0x4d783c'),
    (0x4d78dc, 0x12000009, 'reset_poweroptions_timer: beqz s0: the screen light only for a non-zero third argument'),
    (0x4d78ec, 0x0411ffc1, 'reset_poweroptions_timer: bal setlight_time 0x4d77f4'),
)
# Stock's Google Pinyin engine (ime_pinyin: MatrixSearch, DictTrie, SpellingTrie, NGram; docs/modules/keyboard.md "Pinyin engine (probe)"). The C entry points sit over one global
# MatrixSearch* (0xa0a360, created by im_open_decoder, NULL until then); its first byte is inited_, which search / get_candidate / get_candidate_num test. im_open_decoder(sys dict path,
# user dict path) replaces any object there (stock's own keyboard init calls it with /usr/dict_pinyin.dat, which the rootfs does not have, so the object it leaves is never initialised).
FUNCTIONS.update({
    'im_open_decoder':         ('int', 'const char *, const char *', 0x5c7350),
    'im_close_decoder':        ('void', 'void', 0x5c7534),
    'im_search':               ('unsigned', 'const char *, unsigned', 0x5c760c),
    'im_reset_search':         ('void', 'void', 0x5c76e8),
    'im_get_candidate':        ('unsigned short *', 'unsigned, unsigned short *, unsigned', 0x5c7754),
    'im_choose':               ('unsigned', 'unsigned', 0x5c77c0),
    'im_get_fixed_len':        ('unsigned', 'void', 0x5c7824),
    'im_get_spl_start_pos':    ('unsigned', 'const unsigned short **', 0x5c778c),
    # MatrixSearch::get_predicts(this, history (1..7 char16), out char16[n][8], n): the commonly following words (no C entry point of its own)
    '_ZN10ime_pinyin12MatrixSearch12get_predictsEPKtPA8_tj': ('unsigned', 'void *, const unsigned short *, unsigned short (*)[8], unsigned', 0x5c6834),
})
PINYIN_PINS = (   # (address, stock word, what it proves)
    (0x5c7350, 0x3c1c0044, 'im_open_decoder prologue'), (0x5c7354, 0x279ccb80, 'im_open_decoder prologue'), (0x5c7358, 0x0399e021, 'im_open_decoder prologue'),
    (0x5c7534, 0x3c1c0044, 'im_close_decoder prologue'), (0x5c7538, 0x279cc99c, 'im_close_decoder prologue'), (0x5c753c, 0x0399e021, 'im_close_decoder prologue'),
    (0x5c760c, 0x3c1c0044, 'im_search prologue'), (0x5c7610, 0x279cc8c4, 'im_search prologue'), (0x5c7614, 0x0399e021, 'im_search prologue'),
    (0x5c76e8, 0x3c1c0044, 'im_reset_search prologue'), (0x5c76ec, 0x279cc7e8, 'im_reset_search prologue'), (0x5c76f0, 0x0399e021, 'im_reset_search prologue'),
    (0x5c7754, 0x3c1c0044, 'im_get_candidate prologue'), (0x5c7758, 0x279cc77c, 'im_get_candidate prologue'), (0x5c775c, 0x0399e021, 'im_get_candidate prologue'),
    (0x5c7824, 0x3c1c0044, 'im_get_fixed_len prologue'), (0x5c7828, 0x279cc6ac, 'im_get_fixed_len prologue'), (0x5c782c, 0x0399e021, 'im_get_fixed_len prologue'),
    (0x5c778c, 0x3c1c0044, 'im_get_spl_start_pos prologue'), (0x5c7790, 0x279cc744, 'im_get_spl_start_pos prologue'), (0x5c7794, 0x0399e021, 'im_get_spl_start_pos prologue'),
    (0x5c77c0, 0x3c1c0044, 'im_choose prologue'), (0x5c77c4, 0x279cc710, 'im_choose prologue'), (0x5c77c8, 0x0399e021, 'im_choose prologue'),
    (0x5c6834, 0x3c1c0044, 'MatrixSearch::get_predicts prologue'), (0x5c6838, 0x279cd69c, 'MatrixSearch::get_predicts prologue'), (0x5c683c, 0x0399e021, 'MatrixSearch::get_predicts prologue'),
    (0x5bffd4, 0x3c1c0044, 'DictList::get_splids_for_hanzi prologue'), (0x5bffd8, 0x279c3efc, 'DictList::get_splids_for_hanzi prologue'), (0x5bffdc, 0x0399e021, 'DictList::get_splids_for_hanzi prologue'),
    (0x5c01a4, 0x3c1c0044, 'DictList::get_lemma_id prologue'), (0x5c01a8, 0x279c3d2c, 'DictList::get_lemma_id prologue'), (0x5c01ac, 0x0399e021, 'DictList::get_lemma_id prologue'),
    (0x5c922c, 0x3c1c0044, 'SpellingTrie::get_spelling_str prologue'), (0x5c9230, 0x279caca4, 'SpellingTrie::get_spelling_str prologue'), (0x5c9234, 0x0399e021, 'SpellingTrie::get_spelling_str prologue'),
    (0xa00410, 0x00a0a360, 'GOT word of the engine pointer: the global MatrixSearch* at 0xa0a360 every im_* function loads'),
    (0x5c7384, 0x8c440000, 'im_open_decoder: lw a0, (v0): an existing object is destroyed before the new one'), (0x5c7594, 0xae000000, 'im_close_decoder: sw zero, (s0): the pointer is cleared'),
    (0x5c5740, 0x90860000, 'MatrixSearch::search: lbu a2, (a0): the first byte of the object is tested (inited_)'), (0x5c5128, 0x90820000, 'MatrixSearch::get_candidate: lbu v0, (a0): inited_'),
    (0x5c3094, 0x90830000, 'MatrixSearch::get_candidate_num: lbu v1, (a0): inited_'),
    (0x5c2ed0, 0xa2020000, 'MatrixSearch::init: sb v0, (s0): inited_ = 1 once the system dictionary and the user dictionary step are done'),
    (0x5c2ff8, 0xa2020000, 'MatrixSearch::init_fd: sb v0, (s0): inited_ = 1'),
    (0x5c2e00, 0x14a0000a, 'MatrixSearch::init: bnez a1: a NULL system dictionary path fails'), (0x5c2e2c, 0x10c0fff6, 'MatrixSearch::init: beqz a2: a NULL user dictionary path fails'),
)
JPEG_PINS = (   # (address, stock word, what it proves): the libjpeg 7 layout patch/pccover.c writes by offset, as stock's own decoder (0x5dd5ec) and encoder (0x5de554) do, and the error exit it borrows
    (0x5dbfe0, 0x3c1c0042, 'libjpeg error_exit prologue'), (0x5dbfe4, 0x279c7ef0, 'libjpeg error_exit prologue'), (0x5dbfe8, 0x0399e021, 'libjpeg error_exit prologue'),
    (0x5dbffc, 0x8c900000, 'error_exit: lw s0, 0(a0): cinfo->err'), (0x5dc000, 0x8e190008, 'error_exit: lw t9, 8(s0): err->output_message'),
    (0x5dc014, 0x8f99f868, 'error_exit: lw t9, GOT longjmp'), (0x5dc01c, 0x26040088, 'error_exit: addiu a0, s0, 0x88 (delay slot): longjmp(the jmp_buf that follows the 0x88 byte error manager, 1)'),
    (0x5dd6ec, 0x240601d8, 'decoder: jpeg_CreateDecompress structsize 0x1d8'), (0x5dd6f0, 0x24050046, 'decoder: jpeg_CreateDecompress version 70'),
    (0x5dd768, 0xafa20048, 'decoder: scale_num = 1 at cinfo + 0x30 (cinfo at sp + 0x18)'), (0x5dd774, 0xafa2004c, 'decoder: scale_denom at cinfo + 0x34'),
    (0x5dd790, 0x8fb30088, 'decoder: lw output_width from cinfo + 0x70'), (0x5dd798, 0x8fb2008c, 'decoder: lw output_height from cinfo + 0x74'),
    (0x5dd794, 0x8fb4003c, 'decoder: lw s4, 0x3c(sp): num_components at cinfo + 0x24'),
    (0x5de5ac, 0x240601a8, 'encoder: jpeg_CreateCompress structsize 0x1a8'), (0x5de5b4, 0x24050046, 'encoder: jpeg_CreateCompress version 70'),
    (0x5de654, 0xafb10034, 'encoder: image_width at cinfo + 0x1c'), (0x5de65c, 0xafb60038, 'encoder: image_height at cinfo + 0x20'),
    (0x5de668, 0xafb5003c, 'encoder: input_components at cinfo + 0x24'), (0x5de660, 0xafa20040, 'encoder: in_color_space at cinfo + 0x28'),
)
COVER_PINS = (   # (address, stock word, what it proves): stock's cover extraction as patch/covercache.c art_embedded / art_folder and patch/pccover.c pv_cover reproduce it (docs/modules/coverflow.md "Cover resampling")
    (0x5de680, 0x2405005a, 'the JPEG writer 0x5de554: jpeg_set_quality(cinfo, 90, 1): CV_QUALITY'),
    (0x5eaf00, 0x3c060010, 'toolsGetAlbumCover: taglib_album_picture(track, dst, 0x100000, 0x600000): a2'), (0x5eaf0c, 0x3c070060, 'toolsGetAlbumCover: a3 = 0x600000'),
    (0x5eaf24, 0x24030002, 'toolsGetAlbumCover: the result 2 (a JPEG) goes to the JPEG resize 0x5e03cc'), (0x5eafa8, 0x24030001, 'toolsGetAlbumCover: the result 1 (a PNG) goes to the PNG resize 0x5dfe98'),
    (0x757838, 0x706d742f, 'the string "/tmp/.tmp_picture" (libtag_c save_picturefile writes it, toolsGetAlbumCover reads and removes it)'), (0x75783c, 0x6d742e2f, '"/tmp/.tmp_picture"'),
    (0x757840, 0x69705f70, '"/tmp/.tmp_picture"'), (0x757844, 0x72757463, '"/tmp/.tmp_picture"'), (0x757848, 0x00000065, '"/tmp/.tmp_picture"'),
    (0x5de8cc, 0x2a820003, 'the JPEG loader 0x5de714: under three components goes to the scaled decode'), (0x5de8d4, 0x2a620401, 'the JPEG loader: a width over 1024 goes to the scaled decode'),
    (0x5de8e0, 0x2a420401, 'the JPEG loader: a height over 1024 goes to the scaled decode'),
    (0x5de344, 0x2a020401, 'the PNG loader 0x5de1a8: a width over 1024 is refused'), (0x5de350, 0x2a420401, 'the PNG loader: a height over 1024 is refused'),
    (0x5e0184, 0x24080008, 'the resize 0x5e00bc after a refused full decode: t0 = 8'), (0x5e01a0, 0x28421001, 'the scale: the longer side up to 4096 keeps t0 = 1'), (0x5e01a8, 0x2464fc00, 'the scale: a0 = side - 1024'),
    (0x5e01ac, 0x2463f800, 'the scale: v1 = side - 2048'), (0x5e01b0, 0x24070004, 'the scale: 4'), (0x5e01b4, 0x2c630801, 'the scale: 2048..4096 takes 4'), (0x5e01c0, 0x24070002, 'the scale: 2'),
    (0x5e01c4, 0x2c840401, 'the scale: 1024..2048 takes 2'), (0x5e01c8, 0x0044380a, 'the scale: movz a3, v0, a0'),
    (0x5e01e8, 0x0047182a, 'the fit: slt v1, width, height (a portrait goes to 0x5e02bc)'), (0x5e01f4, 0x0202182a, 'the landscape fit: slt v1, requested width, width'),
    (0x5e01f8, 0x1060003d, 'the landscape fit: a width not over the request goes to 0x5e02f0'), (0x5e0210, 0x46010043, 'the landscape fit: div.s f1 = width / requested width'),
    (0x5e021c, 0x46010003, 'the landscape fit: div.s f0 = height / f1'), (0x5e0220, 0x4600000d, 'the landscape fit: trunc.w.s'),
    (0x5e02bc, 0x1060000c, 'the portrait fit: a height not over the request goes to 0x5e02f0'), (0x5e02c0, 0x0050182a, 'the portrait fit: slt v1, width, requested width (delay slot)'),
    (0x5e02d4, 0x46010043, 'the portrait fit: div.s f1 = height / requested height'), (0x5e02e0, 0x46010003, 'the portrait fit: div.s f0 = width / f1'), (0x5e02e4, 0x4600000d, 'the portrait fit: trunc.w.s'),
    (0x5e02f0, 0x1060ffcd, 'a side exactly the request goes to the resize with the plain request (t x t)'), (0x5e02f4, 0x00f1182a, 'the other side under the request is kept as it is'), (0x5e02f8, 0x1060ffcb, 'a side equal: the resize'),
    (0x5eb760, 0x3c030010, 'toolsGetExternCover: a PNG file of up to 0x100000 bytes (the size, not the pixels)'), (0x5eb7bc, 0x3c030060, 'toolsGetExternCover: a JPEG file of up to 0x600000 bytes'),
    (0x5eb198, 0x9044000a, 'toolsGetExternCover: lbu a0, 0xa(v0): d_type'), (0x5eb19c, 0x24030008, 'toolsGetExternCover: DT_REG only'),
    (0x5eb660, 0x8f99f27c, 'toolsGetExternCover: a name that matches moves to the front: GOT _deque_push_front'), (0x5eb680, 0x26310200, 'toolsGetExternCover: the next of the nine names, 0x200 bytes on'), (0x5eb684, 0x1635ffa7, 'toolsGetExternCover: nine names (the loop ends at 0x1220)'),
    (0x7585f0, 0x646c6f66, '"folder.png"'), (0x7585f4, 0x702e7265, '"folder.png"'), (0x7585f8, 0x0000676e, '"folder.png"'),
    (0x758bf0, 0x65766f63, '"cover.png"'), (0x758bf4, 0x6e702e72, '"cover.png"'), (0x758bf8, 0x00000067, '"cover.png"'),
)
TAPE_PINS = (   # (address, stock word, what it proves): the Tape page invalidates a rectangle of its view (patch/tape.c tp_flush) and reads a label's text (the status bar's volume)
    (0x6691f0, 0x1000feea, 'widget_invalidate_force: b widget_invalidate (0x668d9c) with the rectangle it was given (a1 untouched)'),
    (0x668de4, 0x14a00011, 'widget_invalidate: bnez a1: a rectangle that is given is used as it is, in the widget\'s own coordinates (NULL: 0, 0, w, h)'),
    (0x668e14, 0x24060010, 'widget_invalidate: the rectangle is 16 bytes (rect_init, copied with memcpy 0x10): four 32 bit words x, y, w, h'),
    (0x667d84, 0x3c1c003a, 'widget_get_text_utf8 prologue'), (0x667d88, 0x279cc14c, 'widget_get_text_utf8 prologue'), (0x667d8c, 0x0399e021, 'widget_get_text_utf8 prologue'),
)
FUNCTIONS['get_playtime'] = ('int', 'void', 0x4e02e4)   # the position the stock lyric timers compare "lrc_time" with (docs/modules/lyrics.md)
LYRICS_PINS = (   # (address, stock word, what it proves): the stock lyric rows patch/lyrics.c reads (docs/modules/lyrics.md)
    (0x4e02e4, 0x3c1c0052, 'get_playtime prologue'), (0x4e02e8, 0x279c3bec, 'get_playtime prologue'), (0x4e02ec, 0x0399e021, 'get_playtime prologue'),
    (0x751c3c, 0x6f726373, 'the string "scroll_lrc" (the list the stock timers fill)'), (0x751c40, 0x6c5f6c6c, '"scroll_lrc"'), (0x751c44, 0x00006372, '"scroll_lrc"'),
    (0x751c80, 0x5f63726c, 'the string "lrc_time" (the int property of every lyric row)'), (0x751c84, 0x656d6974, '"lrc_time"'),
    (0x5384bc, 0x24451c80, 'the online row builder 0x537fec: widget_set_prop(row, "lrc_time", time)'),
    (0x538654, 0x26941c80, 'the online lyric timer 0x537fec: s4 = "lrc_time", the property it reads from each row'),
    (0x5385cc, 0x0320f809, 'the online lyric timer: jalr mclGetPlayStatus'), (0x5385e0, 0x0320f809, 'the online lyric timer: jalr get_playtime when the status is not 1 (stopped is time 0)'),
    (0x5386a8, 0x0320f809, 'the online lyric timer: jalr widget_get_prop(row, "lrc_time")'),
    (0x536e3c, 0x90626d30, 'the stock lyric row click handler 0x536e1c: lbu v0, 0x6d30(v1): it flips the lyric display flag (and refreshes the page), it does not seek'), (0x536e50, 0xa0626d30, 'the row click handler: sb v0, 0x6d30(v1) (in the delay slot of the refresh call)'),
    (0x4e0544, 0x3c1c0052, 'seek_time prologue (the tap-to-seek call; also pinned by PODCAST_PINS)'),
    (0x62e9f8, 0x24a5add8, 'label paint (the line_wrap branch): a1 = "spacer" (0x75add8), the style int that sets the row pitch'), (0x62ea04, 0x9615000c, 'label paint: lhu s5, 0xc(canvas) = the font size'),
    (0x62ea24, 0x02a29821, 'label paint: row pitch s3 = font size + style "spacer" (default 2): LY_LINE_H = LY_FONT + the style\'s spacer'),
    (0x650ebc, 0x1440ffcf, 'font_manager_get_font: a font name that cannot be loaded is retried with the default font name (the fallback of np_lyric_style when lyrics.ttf is missing); no per-glyph fallback'),
)
# The library scan's folder walk (patch/common.c pod_scan_dir, docs/modules/payload.md hook 5): toolsLoadAllFile (0x5efd98) lists each folder with the function at 0x5ea364 (readdir
# loop, 0x5ea600); for a directory entry (d_type 4, name in s0) it skips "." with `strcmp(name, ".")` (0x5ea6a8), ".." and a list of system folders (lost+found, System Volume
# Information, RECYCLER, $RECYCLE.BIN, .LOST.DIR, .fseventsd, .Spotlight-V100, .Trashes); a zero result goes back to readdir (0x5ea600). Every other dot-folder is walked. The
# strcmp call is replaced by `jal pod_scan_dir` (q2-pod's SCAN_DIRS): the delay slot still loads a1 = ".", a0 = the name. Not on the boot path (tools/reach.py): the scan runs from
# the Update Local Music item and the other scan callers only.
# The Library query filter (patch/pcmodel.c pc_library_query / pc_sorted_query, docs/modules/payload.md hook 6): the two functions every songtable select goes through, hooked at their PIC prologues
# (q2-pod's toolsQueryDbTable / toolsQueryDbTableAndSort hooks). Both take (db, sql, row callback, sort) in a0..a3 and use no stack arguments.
QUERY_DB, QUERY_DB_PROLOGUE = 0x5ee77c, (0x3c1c0041, 0x279c5754, 0x0399e021)
QUERY_SORT, QUERY_SORT_PROLOGUE = 0x5ee9ac, (0x3c1c0041, 0x279c5524, 0x0399e021)
QUERY_PINS = (   # (address, stock word, what it proves): the first word after the prologue the trampolines resume at (the frame), and the sqlite3_exec calls that run the SQL
    (0x5ee788, 0x27bdff28, 'toolsQueryDbTable: addiu sp, sp, -0xd8 (the trampoline resumes here)'), (0x5ee7fc, 0x0320f809, 'toolsQueryDbTable: jalr sqlite3_exec(db, sql=a1, cb=a2)'),
    (0x5ee9b8, 0x27bdfe80, 'toolsQueryDbTableAndSort: addiu sp, sp, -0x180 (the trampoline resumes here)'), (0x5eea2c, 0x0320f809, 'toolsQueryDbTableAndSort: jalr sqlite3_exec(db, sql=a1, cb=a2)'),
    # The Daily Mix's own song query (patch/dailymix.c dm_rows, docs/modules/dailymix.md): stock's getAllMusic query (sort_first_alphabet 0x4ea0ac) with another SQL: the database path
    # string (0x745a34) and the song row callback (0x4e9058: a row of 18 columns, pushed into *tools_pdeq_directory) as it loads them, the call, and the callback's own prologue
    (0x4ea11c, 0x24c69058, 'sort_first_alphabet: a2 = the song row callback 0x4e9058'), (0x4ea120, 0x0320f809, 'sort_first_alphabet: jalr toolsQueryDbTable(db, sql, cb, 1)'),
    (0x4ea124, 0x24845a34, 'sort_first_alphabet: a0 = the database path string 0x745a34'),
    (0x4e9058, 0x3c1c0052, 'song row callback prologue'), (0x4e905c, 0x279cae78, 'song row callback prologue'), (0x4e9060, 0x0399e021, 'song row callback prologue'),
    (0x4e9068, 0x14a200d5, 'song row callback: bne a1, 0x12 (the column count): a row of any other width is skipped'),
    # The Favourites list and Saved (patch/pcmodel.c pq_filter, docs/modules/podcasts.md "Saved"): getAllFav runs sprintf(buf, "select * from %s", "myfav") and toolsQueryDbTable on it; the three myfav
    # wrappers the star button (manage_myfav 0x4ef884) uses are thin calls on the same table, keyed by filename / fileurl / the cue times of the record.
    (0x4ec45c, 0x3c1c0051, 'getAllFav prologue'), (0x4ec460, 0x279c7a74, 'getAllFav prologue'), (0x4ec464, 0x0399e021, 'getAllFav prologue'), (0x4ec4d0, 0x0320f809, 'getAllFav: jalr toolsQueryDbTable'),
    (0x4ee210, 0x3c1c0051, 'checkFavExist prologue'), (0x4ee214, 0x279c5cc0, 'checkFavExist prologue'), (0x4ee218, 0x0399e021, 'checkFavExist prologue'),
    (0x4ee234, 0x3c1c0051, 'addMyFav prologue'), (0x4ee238, 0x279c5c9c, 'addMyFav prologue'), (0x4ee23c, 0x0399e021, 'addMyFav prologue'),
    (0x4ede88, 0x3c1c0051, 'deleteMusicFromFav prologue'), (0x4ede8c, 0x279c6048, 'deleteMusicFromFav prologue'), (0x4ede90, 0x0399e021, 'deleteMusicFromFav prologue'),
)
SCAN_SITE = 0x5ea6a8
SCAN_PINS = (   # (address, stock word, what it proves)
    (0x5ea364, 0x3c1c0042, 'library folder lister prologue'), (0x5ea368, 0x279c9b6c, 'library folder lister prologue'), (0x5ea36c, 0x0399e021, 'library folder lister prologue'),
    (0x5ea69c, 0x8f85a708, 'folder lister: lw a1, GOT page 0x740000'), (0x5ea6a0, 0x02002025, 'folder lister: move a0, s0: the entry name'),
    (0x5ea6a4, 0x8f99f56c, 'folder lister: lw t9, GOT strcmp'), (SCAN_SITE, 0x0320f809, 'folder lister: jalr strcmp(name, ".")'),
    (0x5ea6ac, 0x24a53ed4, 'folder lister: addiu a1, a1, 0x3ed4 (delay slot): a1 = "."'), (0x5ea6b0, 0x1040ffd3, 'folder lister: beqz v0, 0x5ea600: a match goes back to readdir'),
)
# Battery Percentage (patch/battery.c bp_capacity, docs/modules/payload.md hook 8, docs/modules/battery.md "The percentage"): show_sysbar_face (0x544b48, the status bar's 1 s timer) calls
# get_battery_capacity (0x4e6dd8) at 0x5450f8 and drops the result; the capacity the fill uses is the global power_capacity (0xa059ec) the function leaves (the bucketed voltage, or the charging
# animation's +10), read at 0x545120 / 0x545154 / 0x54536c and by the pull-down's face (dropdown_showface 0x475c3c, on its own timer). The `jalr` becomes `jal bp_capacity` (the delay slot is a nop):
# stock's function first, then the gauge's percentage into power_capacity when Battery Percentage is on. Not reachable at boot (tools/reach.py).
BATTERY_SITE = 0x5450f8
BATTERY_PINS = (   # (address, stock word, what it proves)
    (0x544b48, 0x3c1c004c, 'show_sysbar_face prologue'), (0x544b4c, 0x279cf388, 'show_sysbar_face prologue'), (0x544b50, 0x0399e021, 'show_sysbar_face prologue'),
    (0x5450f0, 0x8fbc0010, 'show_sysbar_face: lw gp, 0x10(sp)'), (0x5450f4, 0x8f99be60, 'show_sysbar_face: lw t9, GOT get_battery_capacity'),
    (BATTERY_SITE, 0x0320f809, 'show_sysbar_face: jalr get_battery_capacity'), (0x5450fc, 0x00000000, 'show_sysbar_face: nop (the delay slot)'),
    (0x545100, 0x12600089, 'show_sysbar_face: beqz s3 (img_battery): the result is not read'), (0x545104, 0x8fbc0010, 'show_sysbar_face: lw gp, 0x10(sp) (the $gp is reloaded after the call)'),
    (0x545120, 0x8f90a9dc, 'show_sysbar_face: lw s0, GOT power_capacity'), (0x545154, 0x8e020000, 'show_sysbar_face: lw v0, (s0): the fill is power_capacity'),
    (0x54510c, 0x8f82a910, 'show_sysbar_face: lw v0, GOT 0xa059f8 (POWER_EXT)'), (0x545110, 0x24030001, 'show_sysbar_face: li v1, 1'), (0x54511c, 0x1443000d, 'show_sysbar_face: bne v0, v1: POWER_EXT != 1 goes to the low / normal test'),
    (0x545124, 0x8f83a964, 'show_sysbar_face: lw v1, GOT 0xa059f4 (POWER_USBSTATE)'), (0x545128, 0x8c640000, 'show_sysbar_face: lw a0, (v1)'),
    (0x54512c, 0x24030002, 'show_sysbar_face: li v1, 2'), (0x545130, 0x1483006c, 'show_sysbar_face: bne a0, v1: POWER_USBSTATE != 2 goes to the charging pictures'),
    (0x545134, 0x8f83a958, 'show_sysbar_face: lw v1, GOT 0xa05aa8 (POWER_FLAG)'), (0x545138, 0x80630000, 'show_sysbar_face: lb v1, (v1)'),
    (0x54513c, 0x1462006a, 'show_sysbar_face: bne v1, v0 (1): POWER_FLAG != 1 goes to the charging pictures'),
    (0x545144, 0x8f82a928, 'show_sysbar_face: lw v0, GOT 0x97cae8 (USBDAC_CHARGEFLAG)'), (0x545148, 0x8c420000, 'show_sysbar_face: lw v0, (v0)'),
    (0x54514c, 0x14400066,'show_sysbar_face: bnez v0: USBDAC_CHARGEFLAG != 0 goes to the charging pictures'),
    (0x545158, 0x1c40008b,'show_sysbar_face: bgtz v0: power_capacity > 0 is bar_power, else bar_lowpower'),
    (0x4e6dd8, 0x3c1c0052, 'get_battery_capacity prologue'), (0x4e6ddc, 0x279cd0f8, 'get_battery_capacity prologue'), (0x4e6de0, 0x0399e021, 'get_battery_capacity prologue'),
    (0x4e6e88, 0x8f90a9dc, 'get_battery_capacity: lw s0, GOT power_capacity (the global it leaves)'),
    (0x66d194, 0x8e020008, 'widget_resize: lw v0, 8(s0): widget_t.w'), (0x66d1a0, 0x8e03000c, 'widget_resize: lw v1, 0xc(s0): widget_t.h'),
    (0x66c428, 0x8e040044, 'widget_set_visible: lw a0, 0x44(s0): widget_t.parent, handed to widget_set_need_relayout_children'),
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
    # Delete (docs/modules/playlists.md "Delete"): the stock handler 0x53dbcc (mirrored by patch/playlists.c pl_on_delete) asks with the confirm dialog (Yes = 0xa), then calls
    # batch_delete_file(*0x97cad4 = 0xf00b, *pdeq_playlist, *0xa045e0, 0, 0); the class's case in batch_delete_file's jump table 0x74b7b0 (0xf00b is the ninth word) is the loop
    # that runs deletePlaylist and deleteAllMusicByPlaylist on the id (the record's first word) of every selected row
    (0x53dcc0, 0x2403000a, 'delete handler: v1 = 0xa, the confirm dialog\'s Yes'), (0x53dcc4, 0x1443ffe6, 'delete handler: bne v0, v1: anything but Yes ends it'),
    (0x53dcd0, 0x00003825, 'delete handler: a3 = 0'), (0x53dcd4, 0xafa00010, 'delete handler: delete_file (the 5th argument) = 0'),
    (0x53dcf0, 0x0320f809, 'delete handler: jalr batch_delete_file (a0 = the browsing class *0x97cad4)'),
    (0x74b7d0, 0xffade414, 'batch_delete_file jump table: the class 0xf00b word (+ gp 0xa03ed0 = 0x4e22e4, the playlist loop\'s test)'),
    (0x4e22b0, 0x04112f39, 'batch_delete_file, class 0xf00b loop: bal deletePlaylist 0x4edf98'), (0x4e22d4, 0x04112f41, 'batch_delete_file, class 0xf00b loop: bal deleteAllMusicByPlaylist 0x4edfdc'),
)
# The Add to Playlist picker (patch/picker.c, docs/modules/picker.md): batch_add_file(class, 0xf00b, list, selection, playlist id) as the stock picker's row handler 0x53d300 calls it
FUNCTIONS['batch_add_file'] = ('int', 'int, int, void *, void *, int', 0x4da7dc)
PICKER_PINS = (
    (0x4da7dc, 0x3c1c0053, 'batch_add_file prologue'), (0x4da7e0, 0x279c96f4, 'batch_add_file prologue'), (0x4da7e4, 0x0399e021, 'batch_add_file prologue'),
    (0x53d4b8, 0x3405f00b, 'picker row handler: a1 = 0xf00b (the playlist class), a0 = the context\'s class'), (0x53d4d4, 0x0320f809, 'picker row handler: jalr batch_add_file'),
    (0x53d4d8, 0xafa20010, 'picker row handler: the playlist id (REC_DISC of the row) is the 5th argument'),
    (0x5281c8, 0x3405f00a, 'stock Add button, Favourites: a1 = 0xf00a'), (0x5281cc, 0xafa00010, 'stock Add button, Favourites: the 5th argument is 0'),
    (0x5281d4, 0x8f99c0f4, 'stock Add button, Favourites: t9 = batch_add_file (GOT)'), (0x5281e8, 0x0320f809, 'stock Add button, Favourites: jalr batch_add_file'),
    (0x5281ec, 0x8c440000, 'stock Add button, Favourites: a0 = g_class_type'),
    (0x52822c, 0x24840e48, 'stock Add button, Favourites: msg_addfavsuccess'),
)
# Stock data the payload reads or writes, by absolute address. Exported objects are checked
# against .dynsym; the two unnamed ones carry the code that proves them.
DATA = {
    'BACKLIGHT_STATUS':   (0x97cae4, 'backlight_status'), # byte: 0 off, 1 lit (awake_screen)
    'PDEQ_SHOWLIST':      (0xa045d8, 'pdeq_showlist'),   # deque_t * of the loaded list
    'PDEQ_TOOLS_TMP':     (0xa03964, 'tools_pdeq_directory'),   # deque_t * the stock song row callback fills (toolsQueryDbTable clears it first; loadLocalClassList assigns it to the show list, then clears it)
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
    # the Pinyin engine's global MatrixSearch* (PINYIN_PINS): NULL until im_open_decoder, and its first byte is inited_
    'PY_ENGINE':          (0xa0a360, None),
    # the iPod page's battery (patch/ipod.c): the stock status bar window; the app keeps it (system_bar_init @0x545490); its pgbar_battery value and img_battery picture are what the real bar shows
    'SYSTEM_BAR':         (0xa06f90, 'system_bar'),
    # Battery Percentage (patch/battery.c): the capacity get_battery_capacity leaves (an int, 0..100), which show_sysbar_face and the pull-down's face draw the fill from
    'POWER_CAPACITY':     (0xa059ec, 'power_capacity'),
    # the four words show_sysbar_face tests (0x54510c..0x545148) to decide whether the low / normal picture is chosen (not the charging one); BATTERY_PINS
    'POWER_EXT':          (0xa059f8, None),
    'POWER_USBSTATE':     (0xa059f4, None),
    'POWER_FLAG':         (0xa05aa8, None),
    'USBDAC_CHARGEFLAG':  (0x97cae8, 'usbdac_chargeflag'),
    # Podcasts (patch/pcmodel.c): the stock speed mode, 0..3 (see the PODCAST_PINS note)
    'PLAYSPEED_MODE':     (0xa05acc, 'playspeed_mode'),
    # Podcasts: the id3 state get_id3info (0x4dfd58) fills from the file's tags; the title / artist the player pages and the lock screen read
    'PLAYSONG_ID3INFO':   (0xa0d88c, 'playsong_id3info'),
    'SONG_NAME':          (0xa0513c, 'song_name'),
    'SONG_ARTIST':        (0xa0503c, 'song_artist'),
    # Settings (patch/m1plus.c, docs/modules/settings.md "Stock state"): the state the top page shows at the right of Wi-Fi, Bluetooth, EQ and Language (one byte each, one int each; the stock
    # status bar and pull-down read the same words): wififlag (1 on; wifi_switch clears it and saves [SYSSET] WIFI), bluetoothflag, equalizer_flag (the byte on_eqswitch_onclick flips and saves as [PLAYSET] EQFLAG),
    # equalizer_mode (the preset, 1..11) and language (the language menu's index, 0 zh_CN .. 12 uk_UK, as switch_language numbers them)
    'WIFI_FLAG':          (0x97caf8, 'wififlag'),
    'BT_FLAG':            (0xa05ac0, 'bluetoothflag'),
    'EQ_FLAG':            (0xa05ac2, 'equalizer_flag'),
    'EQ_MODE':            (0x97cb00, 'equalizer_mode'),
    # About: the serial number (a string of 16 bytes) and the Wi-Fi MAC (32), and the stock literals the model and firmware rows show
    'PRODUCT_SN':         (0xa0553c, 'product_sncode'),
    'WIFI_MAC':           (0xa061a8, 'wifi_mac'),
    'ABOUT_MODEL':        (0x747718, None),
    'ABOUT_FW':           (0x74773c, None),
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
    'deque_at': ('void *', 'const void *, unsigned'), 'deque_destroy': ('void', 'void *'), 'deque_clear': ('void', 'void *'),
    # Artists and the artist-scoped Cover Flow (patch/artists.c, patch/coverflow.c)
    'strcasecmp': ('int', 'const char *, const char *'), '_deque_push_back': ('void', 'void *, const void *'),
    # Screenshot (patch/shot.c): the frame buffer, as stock's lcd_linux_fb_create calls them (ioctl 0x4600 / 0x4602, mmap)
    'ioctl': ('int', 'int, unsigned, void *'), 'mmap': ('void *', 'void *, unsigned, int, int, int, int'),
    'munmap': ('int', 'void *, unsigned'),
    # Podcasts (patch/pcmodel.c): the shows and episodes are found with opendir / readdir (struct dirent, 32-bit: d_name at +11), the files' dates with the stat stub's __xstat (version 3,
    # struct stat 144 bytes, st_mtime at +0x40; stock's own stat(), @0x741b20, is __xstat(3, ..)), the ring is moved in place
    'opendir': ('void *', 'const char *'), 'readdir': ('char *', 'void *'), 'closedir': ('int', 'void *'),
    '__xstat': ('int', 'int, const char *, void *'), 'memmove': ('void *', 'void *, const void *, unsigned'),
    # Podcast network (patch/pcnet.c): the libcurl easy interface, already imported by demo (stock's curl_init)
    'curl_global_init': ('int', 'long'), 'curl_easy_init': ('void *', 'void'), 'curl_easy_setopt': ('int', 'void *, int, ...'),
    'curl_easy_perform': ('int', 'void *'), 'curl_easy_getinfo': ('int', 'void *, int, ...'), 'curl_easy_cleanup': ('void', 'void *'),
    'pthread_detach': ('int', 'unsigned long'), 'sleep': ('unsigned', 'unsigned'),
    'lseek': ('long', 'int, long, int'),   # Podcast downloads (patch/pcnet.c): the size of a .part file, lseek(fd, 0, SEEK_END)
    # Podcast cover shrink (patch/pccover.c): demo's own libjpeg 7 (stock's picture decoder / encoder at 0x5dd5ec, 0x5de554 call the same ones), and _setjmp for its error exit (JPEG_PINS)
    'jpeg_std_error': ('void *', 'void *'), 'jpeg_CreateDecompress': ('void', 'void *, int, unsigned'), 'jpeg_stdio_src': ('void', 'void *, void *'),
    'jpeg_read_header': ('int', 'void *, int'), 'jpeg_start_decompress': ('int', 'void *'), 'jpeg_read_scanlines': ('unsigned', 'void *, unsigned char **, unsigned'),
    'jpeg_destroy_decompress': ('void', 'void *'), 'jpeg_CreateCompress': ('void', 'void *, int, unsigned'), 'jpeg_stdio_dest': ('void', 'void *, void *'),
    'jpeg_set_defaults': ('void', 'void *'), 'jpeg_set_quality': ('void', 'void *, int, int'), 'jpeg_start_compress': ('void', 'void *, int'),
    'jpeg_write_scanlines': ('unsigned', 'void *, unsigned char **, unsigned'), 'jpeg_finish_compress': ('void', 'void *'), 'jpeg_destroy_compress': ('void', 'void *'),
    '_setjmp': ('int', 'void *'),
    'rmdir': ('int', 'const char *'),   # Podcasts unsubscribe (patch/podcasts.c): the show folder left empty
    # Album cover extraction (patch/covercache.c art_embedded): libtag_c's taglib_album_picture(track, out, 0x100000, 0x600000), exactly as toolsGetAlbumCover calls it (the picture goes to /tmp/.tmp_picture; out is not used); 2 = JPEG, 1 = PNG, 0 = none
    'taglib_album_picture': ('int', 'const char *, char *, int, int'),
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


# ---- The Folders page (patch/folders.c, docs/modules/folders.md) -------------------------------------------------------
# The stock folder_page keeps its state in globals and four functions: layer (0xa0554c: 0 before the first enter, 1 the root list of storages, 2 and up the folders), the path (0xa05550),
# the title (0xa0533c, filled by getFormatString("folder") at the root and the folder's name below), the m3u path (0xa0483c, set while a playlist file is open) and the shown list
# (*pdeq_showlist, stSongInfo records: +8 name, +0xc url, +0x34 type 2 SD / 3 OTG / 4 folder / 1 playlist file / 8 audio file, +0x48 cue). Our page calls the stock functions on that state.
FUNCTIONS.update({
    'folder_enter':            ('int', 'int, int', 0x4db978),      # (record index, yoffset): -1 resets to the root list; 8 = an audio file (nothing changed), 1 = entered, -1 .. -4 = not entered
    'folder_back':             ('int', 'int *', 0x4dbecc),         # (yoffset out): 0 = left the root (state cleared), else one level up; *out is the offset the child was entered at (not written at the root)
    'folder_reload':           ('int', 'void', 0x4db7ec),          # the current level's list again
    'is_folderplaying':        ('int', 'const char *', 0x5329d8),  # the folder (record url) holds the song being played from a folder queue
})
DATA.update({
    'FOLDER_LAYER':       (0xa0554c, None),
    'FOLDER_TITLE':       (0xa0533c, None),
    'FOLDER_M3U':         (0xa0483c, None),
})
FOLDER_PINS = (   # (address, stock word, what it proves)
    (0x4db978, 0x3c1c0053, 'folder_enter prologue'), (0x4db97c, 0x279c8558, 'folder_enter prologue'), (0x4db980, 0x0399e021, 'folder_enter prologue'),
    (0x4db9b4, 0x04810002, 'folder_enter: bgez a0 (an index below 0 ...)'), (0x4db9bc, 0xae400000, '... clears the layer: the root list is loaded again'),
    (0x4dbbe8, 0x24020004, 'folder_enter: a record of type 4 (a folder) ...'), (0x4dbbec, 0x8e300034, '... type = record + 0x34'), (0x4dbbf0, 0x16020068, '... is entered (bne to the type 1 / 8 tests otherwise)'),
    (0x4dbd94, 0x16150049, 'folder_enter: type 1 (a playlist file) is parsed, any other type goes on'), (0x4dbd98, 0x3a020008, 'folder_enter: xori 8'),
    (0x4dbec0, 0x02a2800b, 'folder_enter: movn: the return value is 1 unless the type is 8, which returns 8 (an audio file: the caller plays it)'),
    (0x4dbecc, 0x3c1c0053, 'folder_back prologue'), (0x4dbed0, 0x279c8004, 'folder_back prologue'), (0x4dbed4, 0x0399e021, 'folder_back prologue'),
    (0x4dbedc, 0x8f83b81c, 'folder_back: v1 = &layer (GOT 0xa0554c, FOLDER_LAYER)'),
    (0x4dbefc, 0x2442ffff, 'folder_back: layer - 1'), (0x4dbf00, 0x1c40000c, 'folder_back: still above 0: one level up'), (0x4dbf14, 0x00001025, 'folder_back: otherwise clear_foldervariate, and 0 is returned (the page closes)'),
    (0x4dbf68, 0x8f84b828, 'folder_back: a0 = the title buffer (GOT 0xa0533c, FOLDER_TITLE)'), (0x4dbfc8, 0x24020001, 'folder_back: 1 is returned for the root list'),
    (0x4dbdbc, 0x8f84b820, 'folder_enter: a0 = the m3u path buffer (GOT 0xa0483c, FOLDER_M3U)'),
    (0x4db7ec, 0x3c1c0053, 'folder_reload prologue'), (0x4db7f0, 0x279c86e4, 'folder_reload prologue'), (0x4db7f4, 0x0399e021, 'folder_reload prologue'),
    (0x4db810, 0x28420002, 'folder_reload: layer < 2 loads the root list'),
    (0x5329d8, 0x3c1c004d, 'is_folderplaying prologue'), (0x5329dc, 0x279c14f8, 'is_folderplaying prologue'), (0x5329e0, 0x0399e021, 'is_folderplaying prologue'),
    (0x532b94, 0x8e020034, 'the stock folder row: type = record + 0x34'), (0x532b98, 0x2442fffe, '... - 2'), (0x532b9c, 0x2c420003, '... < 3 (types 2, 3, 4: a folder)'),
    (0x532ba8, 0x0411ff8b, 'the stock folder row: bal is_folderplaying'), (0x532bac, 0x8e04000c, '... with a0 = the record url (+0xc)'),
    (0x532c0c, 0x8e030034, 'the stock folder row: a type 8 record asks is_playing(1, ...)'), (0x532c10, 0x14620008, '(bne type, 8)'),
    # a marked folder in the stock Delete and Add (class 1, docs/modules/folders.md): both read the record's type and load the folder with toolsLoadDirectory
    (0x4e1560, 0x8c430034, 'batch_delete_file class 1 loop: type = record + 0x34'), (0x4e1564, 0x24020004, '... compared with 4 (a folder)'), (0x4e1568, 0x14620033, '(bne: any other type is a file row)'),
    (0x4e157c, 0x8f99b804, 'a folder is read with toolsLoadDirectory(url) (GOT), its type 8 files leave the library'),
    (0x4e12c8, 0x1443001f, 'remove_file: a regular file (S_IFREG) is removed'), (0x4e1348, 0x1443ffe5, 'remove_file: a directory (S_IFDIR) ...'), (0x4e1368, 0x24c6b294, '... runs system of the string at 0x74b294, rm -rf of the path'),
    (0x4db00c, 0x1262002a, 'batch_add_file class 1: a type 4 record (a folder) is expanded ...'), (0x4db0cc, 0x8f99b804, '... with toolsLoadDirectory(url)'),
    (0x4db114, 0x8c430034, '... and each type 8 record of it'), (0x4db11c, 0x14620080, '(bne type, 8: skipped) is added'),
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
    h.append('#define STOCK_DB_PATH ((const char *)0x745a34u)')   # "/mnt/data/database.db" (QUERY_PINS)
    h.append('#define STOCK_SONG_ROW ((void *)0x4e9058u)')       # the song row callback getAllMusic passes to toolsQueryDbTable (QUERY_PINS)
    h.append(f'#define STOCK_HOME_CLICK 0x{HOME_CLICK:x}u')   # the icon click handler stock registers per icon
    h.append(f'#define POD_ENTRY_NAME "{pod_pages.HOME_ENTRY}"')   # the added icon's widget name (a decimal id, as stock's)
    h.append(f'#define stock_np_mode_button ((int (*)(void *))0x{NP_MODE_BUTTON:x}u)')   # Now Playing's mode button picture (patch/nowplaying.c)
    h.append(f'#define stock_playlist_import ((int (*)(void *, void *))0x{PLAYLIST_IMPORT:x}u)')   # the stock Playlists page's Import / Export rows
    h.append(f'#define stock_playlist_export ((int (*)(void *, void *))0x{PLAYLIST_EXPORT:x}u)')
    # the engine's dictionary members (patch/search.c pinyin initials; not exported, pinned by PINYIN_PINS): DictList::get_lemma_id(this, char16 *, len), get_splids_for_hanzi(this, hanzi, half_splid, splids, max), SpellingTrie::get_spelling_str(this, id)
    h.append('#define py_lemma_id ((unsigned (*)(void *, const unsigned short *, unsigned))0x5c01a4u)')
    h.append('#define py_splids ((unsigned short (*)(void *, unsigned short, unsigned short, unsigned short *, unsigned short))0x5bffd4u)')
    h.append('#define py_spelling ((const char *(*)(void *, unsigned short))0x5c922cu)')
    h.append('extern int stock_home_click_trampoline(void *, void *);')
    h.append('extern int stock_playing_init_trampoline(void *, void *);')
    h.append('extern int stock_playmore_init_trampoline(void *, void *);')
    h.append('extern int stock_dbquery_trampoline(const char *, const char *, void *, int);')
    h.append('extern int stock_sorted_query_trampoline(const char *, const char *, void *, int);')
    h.append('extern int coverflow_open(void);')
    h.append('extern int coverflow_landscape(void);')
    h.append('extern int coverflow_landscape_toggle(void);')
    # the customisable menu (patch/menu.c): its item count, the default shown prefix and the row geometry
    h.append(f'#define POD_MENU_ITEMS {len(pod_pages.ITEMS)}')
    h.append(f'#define POD_MENU_DEFAULT {len(pod_pages.DEFAULT_MENU)}')   # the default menu: this many items ...
    h.append('#define POD_MENU_DEFAULT_IDS {' + ', '.join(str(i) for i in pod_pages.DEFAULT_MENU) + '}')   # ... these item ids, in order
    h.append(f'#define POD_MENU_FILE_MAX {pod_pages.MENU_FILE_MAX}')
    h.append(f'#define POD_MENU_ROWS {len(pod_pages.MENU.rows)}')
    h.append(f'#define POD_SETTINGS_ID {pod_pages.SETTINGS_ID}')
    h.append(f'#define POD_EXTRAS_ROWS {len(pod_pages.EXTRAS_PAGE.rows)}')
    h.append('#define POD_EXTRAS_ORDER {' + ', '.join(str(i) for i in pod_pages.EXTRAS_ORDER) + '}')   # the Extras page's rows (item ids) top to bottom
    h.append(f'#define POD_EXTRAS_GROUPS {len(pod_pages.EXTRAS_GROUPS)}')   # the Extras page's titled groups (section headers pod_hdr0 ..) ...
    h.append('#define POD_EXTRAS_GROUP {' + ', '.join(str(g) for g in pod_pages.EXTRAS_GROUP_OF) + '}')   # ... the group of each item id ...
    h.append(f'#define POD_EXTRAS_HDR_H {pod_pages.HDR_H}')   # ... and a header's height
    h.append(f'#define POD_ROW_H {pod_ui.ROW_H}')
    # the Songs rail's alignment, from the tree's own font (tools/pod_ui.py rail_metrics): twice the cap ink's centre within an item, and each letter's rect shift
    font_path = os.path.join(os.path.dirname(os.path.dirname(demo_path)), 'assets/default/raw/fonts/default.ttf')
    ink2, dx = pod_ui.rail_metrics(font_path)
    for n, w in zip((2, 3, 4), pod_ui.pct_widths(font_path)): h.append(f'#define BP_W{n} {w}')   # the status bar percentage label's width for a text of n characters ("5%", "87%", "100%"; patch/battery.c)
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
    h.append('static const struct pod_stock POD_STOCK[] = {')   # ACT_STOCK's pages: the name and the value the row shows (VK_*: 0 none, else 1 + the index in STOCK_VALUES)
    for name, value in pod_pages.STOCK_PAGES:
        h.append(f'    {{"{name}", {pod_pages.STOCK_VALUES.index(value) + 1 if value else 0}}},')
    h.append('};')
    import pod_settings as ST   # the value labels' fit (patch/m1plus.c value_fit): the right edge of a value's box and the room a value may take, the label's left edge and the gap between them
    h.append(f'#define POD_VALUE_RIGHT {ST.value_box()[0] + ST.VALUE_W}')
    h.append(f'#define POD_VALUE_MAX {ST.VALUE_MAX}')
    h.append(f'#define POD_VALUE_GAP {ST.VALUE_LABEL_GAP}')
    h.append(f'#define POD_LABEL_X {ST.TEXT_X}')
    h.append(f'#define POD_INFO_RIGHT {ST.RIGHT}')   # the About rows' value: its right edge, the most it takes, and the label's left edge
    h.append(f'#define POD_INFO_MAX {ST.INFO_MAX}')
    h.append(f'#define POD_INFO_LABEL_X {ST.CM + ST.PAD}')
    h.append('static const struct pod_page POD_PAGES[] = {')
    for pi, page in enumerate(pages):
        rows = f'pod_rows_{pi}' if page.rows else '0'
        h.append(f'    {{"{page.key}", {rows}, {len(page.rows)}}},')
    h.append('};')
    h.append(f'#define POD_PAGE_COUNT {len(pages)}')
    h.append(f'#define POD_ENTRY_ID {pod_pages.HOME_ENTRY}')
    h.append('#define POD_ENTRY_PAGE 0')
    h.append('#define POD_MENU_PAGE 0')
    h.append(f'#define POD_SETTINGS_PAGE {pod_pages.SETTINGS_PAGE_INDEX}')
    h.append(f'#define POD_EXTRAS_PAGE {pod_pages.EXTRAS_PAGE_INDEX}')
    h.append(f'#define POD_MENUCFG_PAGE {pod_pages.MENUCFG_PAGE_INDEX}')
    h.append(f'#define POD_EXTRASCFG_PAGE {pod_pages.EXTRASCFG_PAGE_INDEX}')
    h.append(f'#define POD_DEVELOPER_PAGE {pod_pages.DEVELOPER_PAGE_INDEX}')
    h.append(f'#define POD_CACHE_PAGE {pod_pages.CACHE_PAGE_INDEX}')
    h.append(f'#define POD_FILES_PAGE {pod_pages.FILES_PAGE_INDEX}')
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
    # and for the Now Playing page's init
    asm += ['.globl stock_playing_init_trampoline', 'stock_playing_init_trampoline:',
            f'lui $gp, {GP >> 16}', f'ori $gp, $gp, {GP & 0xffff}', f'j 0x{PLAYING_INIT + 12:x}', 'nop']
    # and for the Now Playing More dialog's init
    asm += ['.globl stock_playmore_init_trampoline', 'stock_playmore_init_trampoline:',
            f'lui $gp, {GP >> 16}', f'ori $gp, $gp, {GP & 0xffff}', f'j 0x{PLAYMORE_INIT + 12:x}', 'nop']
    # and for the two Library query functions
    for nm, at in (('dbquery', QUERY_DB), ('sorted_query', QUERY_SORT)):
        asm += [f'.globl stock_{nm}_trampoline', f'stock_{nm}_trampoline:',
                f'lui $gp, {GP >> 16}', f'ori $gp, $gp, {GP & 0xffff}', f'j 0x{at + 12:x}', 'nop']
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


def compile_payload(out, demo_path, tag=TAG):
    out = pathlib.Path(out)
    slots = gen_stock_h(out, demo_path)
    gen_scroll_h(out)
    gen_asm(out, slots)
    objs = [out / (src + '.o') for src in SOURCES]   # (SOURCES order: the link is byte-identical to a serial compile)

    def compile_one(src, obj):
        cmd = [str(a) for a in (CLANG, *FLAGS, f'-DM1PLUS_TAG="{about(tag)}"', '-I', out, '-I', PATCH, '-c', os.path.join(PATCH, src), '-o', obj)]
        return subprocess.run(cmd, stderr=subprocess.PIPE, text=True)

    with concurrent.futures.ThreadPoolExecutor(os.cpu_count() or 4) as pool:   # one clang a source; the sources do not depend on each other
        done = list(pool.map(compile_one, SOURCES, objs))
    for r in done:   # the first failing source in SOURCES order, its whole stderr
        if r.stderr: sys.stderr.write(r.stderr)
        if r.returncode: raise subprocess.CalledProcessError(r.returncode, r.args)
    run(CLANG, *FLAGS, '-c', out / 'pod_asm.S', '-o', out / 'pod_asm.o')
    # compact_set_row_layout is reached only from the patched stock call sites, so keep it
    keep = ['--undefined=compact_set_row_layout', '--undefined=m1plus_home_init',
            '--undefined=stock_home_init_trampoline', '--undefined=m1plus_playing_init',
            '--undefined=stock_playing_init_trampoline', '--undefined=m1plus_scroll_event',
            '--undefined=m1plus_playmore_init', '--undefined=stock_playmore_init_trampoline', '--undefined=pc_id3_path', '--undefined=pc_library_query', '--undefined=pc_sorted_query', '--undefined=stock_dbquery_trampoline', '--undefined=stock_sorted_query_trampoline',
            '--undefined=pod_scan_dir', '--undefined=bp_capacity', '--undefined=pf_items', '--undefined=pf_seen']   # (the last two: accessors of the parser the tests read; nothing in the payload calls them)
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
    target4 = ps['m1plus_playing_init']
    check(BASE <= target4 < BASE + len(payload), 'playing init entry symbol outside payload')
    hook(patched, PLAYING_INIT, PLAYING_INIT_PROLOGUE, target4, 'playing_page_init')
    patch_playmore(patched, ps, len(payload))
    for a, old, what in PLAYLIST_PINS + SONGS_PINS + IPOD_PINS + PODCAST_PINS + SETTINGS_PINS + PINYIN_PINS + JPEG_PINS + COVER_PINS + TAPE_PINS + LYRICS_PINS + SCAN_PINS + QUERY_PINS + FONT_PINS + BATTERY_PINS + PICKER_PINS + FOLDER_PINS:   # stock code the Playlists and Songs pages call: checked, not written
        got = struct.unpack_from('<I', patched, fileoff(patched, a))[0]
        check(got == old, f'{a:#x} ({what}): {got:#010x} != pinned {old:#010x}')
    target5 = ps['pc_id3_path']
    check(BASE <= target5 < BASE + len(payload), 'tag reader hook symbol outside payload')
    struct.pack_into('<I', patched, fileoff(patched, ID3_SITE), jal(target5, ID3_SITE))   # (the pins above checked the site's word and its neighbours)
    hook(patched, QUERY_DB, QUERY_DB_PROLOGUE, ps['pc_library_query'], 'toolsQueryDbTable')
    hook(patched, QUERY_SORT, QUERY_SORT_PROLOGUE, ps['pc_sorted_query'], 'toolsQueryDbTableAndSort')
    check(all(BASE <= ps[n] < BASE + len(payload) for n in ('pc_library_query', 'pc_sorted_query')), 'query hook symbol outside payload')
    target6 = ps['pod_scan_dir']
    check(BASE <= target6 < BASE + len(payload), 'scan hook symbol outside payload')
    struct.pack_into('<I', patched, fileoff(patched, SCAN_SITE), jal(target6, SCAN_SITE))
    target8 = ps['bp_capacity']
    check(BASE <= target8 < BASE + len(payload), 'battery hook symbol outside payload')
    struct.pack_into('<I', patched, fileoff(patched, BATTERY_SITE), jal(target8, BATTERY_SITE))   # (the pins above checked the site's word, its delay slot and its neighbours)
    check(dynsym(demo_path).get('playsong_id3info') == 0xa0d88c, 'playsong_id3info moved')
    edits = patch_rows(patched, ps)
    # no row edit may touch a PIC prologue (the hooks are the only ones) or a hook site
    check(all(not any(h <= int(a, 16) < h + 12 for h in (HOME_CLICK, HOME_INIT, PLAYING_INIT, PLAYMORE_INIT, QUERY_DB, QUERY_SORT)) and not ID3_SITE <= int(a, 16) < ID3_SITE + 4 and not SCAN_SITE <= int(a, 16) < SCAN_SITE + 4 and not BATTERY_SITE <= int(a, 16) < BATTERY_SITE + 4
              for a, *_ in edits), 'row edit on a hook')
    check(all(not (SCROLL_SLOT <= int(a, 16) < SCROLL_SLOT + 4 or a in {hex(p[0]) for p in SCROLL_PINS}) for a, *_ in edits),
          'row edit on a list gesture word')
    scroll = patch_scroll(patched, ps, len(payload), demo_path)
    seg_off = append_payload(patched, payload, BASE)
    return bytes(patched), seg_off, edits, scroll


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir')
    ap.add_argument('--tag', default=TAG)
    a = ap.parse_args()
    rootfs = os.path.join(a.workdir, 'rootfs')
    demo_path = os.path.join(rootfs, DEMO)
    raw = open(demo_path, 'rb').read()
    check(sha(raw) == ZEROED_DEMO_SHA, f'demo is not the .pdr-zeroed stock V2.1 binary (got {sha(raw)})')
    build = pathlib.Path(a.workdir) / 'podbuild'; build.mkdir(exist_ok=True)
    check(re.fullmatch(r'V2\.1(z[A-Z]+|-\d+\.\d+\.\d+)', a.tag) is not None and len(a.tag) <= 31, 'invalid build tag')
    ps, payload, scratch = compile_payload(build, demo_path, a.tag)
    patched, seg_off, edits, scroll = patch_demo(raw, payload, ps, demo_path)
    # keep demo's permission bits
    mode = stat.S_IMODE(os.stat(demo_path).st_mode)
    os.chmod(demo_path, mode | 0o200); open(demo_path, 'wb').write(patched); os.chmod(demo_path, mode)
    assets = pod_ui.write_assets(rootfs, pod_pages.PAGES)
    pod_ui.add_shot_indicator(rootfs)     # the hidden camera in ui/system_bar.bin (patch/shot.c)
    pod_ui.add_battery_label(rootfs)      # the hidden percentage in ui/system_bar.bin and both pull-downs (patch/battery.c)
    manifest = {
        'base': BASE, 'gp': GP, 'payload_len': len(payload),
        'payload_sha256': sha(payload), 'scratch_bytes': scratch, 'entry_symbol': ps['m1plus_home_click'],
        'segment_file_off': seg_off, 'hook': {'addr': HOME_CLICK, 'target': ps['m1plus_home_click']},
        'hook_init': {'addr': HOME_INIT, 'target': ps['m1plus_home_init']},
        'hook_playing': {'addr': PLAYING_INIT, 'target': ps['m1plus_playing_init']},
        'hook_playmore': {'addr': PLAYMORE_INIT, 'target': ps['m1plus_playmore_init']},
        'hook_id3': {'addr': ID3_SITE, 'target': ps['pc_id3_path']},
        'hook_query': {'addr': QUERY_DB, 'target': ps['pc_library_query']}, 'hook_sorted_query': {'addr': QUERY_SORT, 'target': ps['pc_sorted_query']},
        'hook_scan': {'addr': SCAN_SITE, 'target': ps['pod_scan_dir']},
        'hook_battery': {'addr': BATTERY_SITE, 'target': ps['bp_capacity']},
        'scroll_slot': {'addr': SCROLL_SLOT, 'target': ps['m1plus_scroll_event']}, 'scroll_edit': scroll,
        'zeroed_demo_sha256': ZEROED_DEMO_SHA, 'patched_demo_sha256': sha(patched),
        'assets': assets, 'entry_home_id': pod_pages.HOME_ENTRY,
        'row_edits': edits, 'row_fit': ps['compact_set_row_layout'],
    }
    (build / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    print(f'payload {len(payload)} bytes ({scratch} .scratch) @ {BASE:#x} (entry {ps["m1plus_home_click"]:#x}), '
          f'hook @ {HOME_CLICK:#x}, boot guard hook @ {HOME_INIT:#x} (home_page_init), '
          f'Now Playing init hook @ {PLAYING_INIT:#x}, '
          f'scroll_view before-children slot @ {SCROLL_SLOT:#x} -> {ps["m1plus_scroll_event"]:#x}')
    kinds = {k: sum(e[3] == k for e in edits) for k in ('immediate', 'call', 'nop')}
    print(f'  rows: {len(edits)} pinned edits ({kinds["immediate"]} immediates, {kinds["call"]} row-layout '
          f'calls -> compact_set_row_layout @ {ps["compact_set_row_layout"]:#x}, {kinds["nop"]} rebind resizes nopped)')
    for rel, n in assets: print(f'  asset {rel} ({n} bytes)')


if __name__ == '__main__': main()
