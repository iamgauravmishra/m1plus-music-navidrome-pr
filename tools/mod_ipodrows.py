#!/usr/bin/env python3
"""iPod-style library rows, the asset half (V2.1gB, docs/architecture.md). The code half is the payload
feature 'rows' (patch/rows.c, the pinned demo edits in patch/rows.json, tools/pod.py).

After q2-pod's restyle of the stock list pages (patch/ipod.json, tools/ipod.py; Copyright (c) 2026
Diamond Bond, MIT; see NOTICE): every library row is PITCH = 64 px, its body BODY = 60 px (the
Folders page already is, and its offset maths divides by 64 with a shift, so 64 it is everywhere),
titles 21 px in 24 px boxes, the grey second line 18 px. demo's row constructors make the rows
(patched in demo); what an asset decides is the pitch the lists step by, and the jump list's row
template, which its table clones without any row constructor:

  ui/localclass_page.bin     localclass_table_client row_height 60 -> 64
  ui/allmusic_page.bin       music_table_client row_height 60 -> 64; the template row (rebuilt by
                             code, kept consistent) table_row h 60 -> 64, btn_table_row h 56 -> 60;
                             navigationbar_view y 0 -> 3, h 50 -> 47 (the builder's 44 px buttons
                             centred in the 50 px bar, as the Pod pages' navbar)
  ui/playerjumpinfo_page.bin row_height 60 -> 64; template table_row 310x64, btn_table_row 310x60,
                             view_info w 238, scrlabel_name (0,7,238,24), view_artist at y 33 h 20,
                             scrlabel_artist w 213 (the jump list's rebind sizes view_info 238x60)
  ui/album_page.bin          album_listview default_item_height 60 -> 64
  ui/playlist_page.bin       playlist_listview default_item_height 60 -> 64 (its rows are created
                             0 high, so this is their pitch)
  ui/playset/equalizer_page.bin, ui/systemset/specfolder_page.bin (both themes)
                             Now Playing (and the folder picker's select-all button) onto the Pod
                             navbar's slots, docs/modules/navbar.md

and page themes (both asset themes, derived from the tree's styles as tools/mod_lists.py does; run
after it): srlabel_item_white_style and srlabel_item_gold20_style at 21 px on the pages whose title
boxes are 24 px now (Songs and the other song lists, the jump list, Albums, the album page, Playlists,
Search). Folders and Artists have them from the lists step. The grey line stays stock's
srlabel_item_gray18_style (#AAAAAA, 18 px). styles/default.bin is not touched (shared with every
page), nor the stock layout strings in demo.

Usage: mod_ipodrows.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_style, awtk_ui
import mod_lists
from modlib import clone_workdir, edit_ui

PITCH, BODY = 64, 60
TINT_NAME, TINT_H = 'img_ah_tint', 450      # the album page's tint gradient (the window is 450 px high): patch/offsets.inc AH_WIN_H
NAV_H = 44             # the shared navbar builder's button height: patch/offsets.inc AH_NAV_H
NAV_BAND = (0, 0, 320, 50)   # the album page's floating controls band (patch/offsets.inc AH_NAV_BAND_H): the full width, the stock builders' buttons sit in it at main's slots
STOCK_PITCH, STOCK_BODY = 60, 56
TEXT_W = 238           # x 60 .. 298 in a 310 px row (12 px margins, a 40 px icon + 8)
TITLE = (0, 7, TEXT_W, 24)
SUB_Y, SUB_H = 33, 20
ARTIST_W = TEXT_W - 25  # after the 20 px MQA badge + 5
TITLE_PAGES = ('allmusic_page', 'playerjumpinfo_page', 'album_page', 'albuminfo_page', 'playlist_page', 'search_page')


def one(root, name, kind):
    ws = [w for w in root.walk() if w.name == name]
    assert len(ws) == 1 and ws[0].type == kind, f'{name}: expected one {kind}'
    return ws[0]


def row_height(root, name):
    tc = one(root, name, 'table_client')
    assert tc.get('row_height') == str(STOCK_PITCH), f'{name}: row_height {tc.get("row_height")}'
    tc.set('row_height', str(PITCH))


def item_height(root, name):
    lv = one(root, name, 'list_view')
    assert lv.get('default_item_height') == str(STOCK_PITCH), f'{name}: default_item_height {lv.get("default_item_height")}'
    lv.set('default_item_height', str(PITCH))


def template_row(root):
    row, btn = one(root, 'table_row', 'table_row'), one(root, 'btn_table_row', 'button')
    assert row.h == STOCK_PITCH and btn.h == STOCK_BODY, 'unexpected template row'
    row.h, btn.h = PITCH, BODY
    lay = row.get('self_layout')
    if lay is not None:
        assert lay == f'default(w=100%,h={STOCK_PITCH})', lay
        row.set('self_layout', f'default(w=100%,h={PITCH})')
    return row, btn


def edit_allmusic(root):
    row_height(root, 'music_table_client')
    template_row(root)
    # the shared navbar builder makes NAV_H high buttons at y 0 (patch/rows.json AH_NAV_H); this page keeps its 50 px bar,
    # so the bar's view starts (50 - NAV_H) / 2 down: glyphs and title centre at y 25 as on the Pod pages, the bottom line stays at 50
    nav = one(root, 'navigationbar_view', 'view')
    assert (nav.x, nav.y, nav.w, nav.h) == (0, 0, 320, 50), 'unexpected allmusic_page navbar'
    nav.y = (50 - NAV_H) // 2
    nav.h = 50 - nav.y


def edit_jumplist(root):
    row_height(root, 'music_table_client')
    template_row(root)
    info, name = one(root, 'view_info', 'view'), one(root, 'scrlabel_name', 'hscroll_label')
    va, artist = one(root, 'view_artist', 'view'), one(root, 'scrlabel_artist', 'hscroll_label')
    assert (info.w, (name.x, name.y, name.w, name.h)) == (200, (0, 10, 200, 20)), 'unexpected jump list text'
    assert va.get('self_layout') == 'default(x=0,y=30,w=100%,h=26)' and artist.w == 175, 'unexpected jump list artist line'
    info.w = TEXT_W
    name.x, name.y, name.w, name.h = TITLE
    va.set('self_layout', f'default(x=0,y={SUB_Y},w=100%,h={SUB_H})'); va.y, va.h = SUB_Y, SUB_H
    artist.w = ARTIST_W


def edit_albuminfo(root):
    """The album page's tint (patch/albuminfo.c): ah_tint, a window sized black gradient, is the window's first child (under the
    list and the controls); the list_view and its scroll_view are transparent, so the window's colour (black, or the cover's tone
    once the payload sets it) shows through the header. The stock rows keep their own black. Nothing is renamed or removed.
    The floating controls (patch/offsets.inc AH_NAV_*): the navbar view is a band over the page's top (NAV_BAND, the
    buttons' glass discs drawn by the page theme, the buttons placed by the builders' main-pinned slots, patch/rows.json), LAST in the window so it
    paints and hit-tests over the list, which now starts at the window's top and scrolls under it."""
    assert root.type == 'window' and [c.name for c in root.children] == ['navigationbar_view', 'albuminfo_listview'], 'unexpected albuminfo_page'
    lv, sv = one(root, 'albuminfo_listview', 'list_view'), one(root, 'albuminfo_scrollview', 'scroll_view')
    for w in (lv, sv):
        for st in ('normal', 'disable', 'focused'): w.set(f'style:{st}:bg_color', '#00000000')
    tint = awtk_ui.Widget('image', 0, 0, 320, TINT_H, [('name', TINT_NAME), ('image', 'ah_tint'), ('draw_type', 'default'),
                                                       ('clickable', 'false'), ('sensitive', 'false')])
    nav, bar = one(root, 'navigationbar_view', 'view'), one(root, 'scroll_bar_m', 'scroll_bar_m')
    assert (nav.h, lv.y, lv.h, sv.h, bar.h) == (50, 50, 400, 400, 400), 'unexpected albuminfo_page geometry'
    nav.x, nav.y, nav.w, nav.h = NAV_BAND
    lv.y = 0
    lv.h = sv.h = bar.h = TINT_H
    root.children = [tint, lv, nav]


NAV_NP = (260, 0, 60, 50)   # the Pod navbar's btn_backtoplayer (tools/pod_ui.py navbar())


def edit_equalizer(root):
    """Settings > Equalizer: Now Playing (270, 50 wide) onto the Pod navbar's slot (docs/modules/navbar.md)."""
    np_ = one(root, 'btn_backtoplayer', 'button')
    assert (np_.x, np_.y, np_.w, np_.h) == (270, 0, 50, 50), 'unexpected equalizer_page Now Playing'
    np_.x, np_.y, np_.w, np_.h = NAV_NP


def edit_specfolder(root):
    """Settings > Update music > a folder picker: Now Playing (279, 41 wide, img_btn_style) onto the Pod navbar's slot and the
    select-all button (229, 38 wide) onto the Pod navbar's NAV_VIEW_X slot (214, 46 wide), as the code-built multi-select
    buttons (an icon_at 5 glyph measured on the device lands on the Pod toggle's columns there)."""
    np_, all_ = one(root, 'btn_backtoplayer', 'button'), one(root, 'navigation_btn_allchoice', 'button')
    assert (np_.x, np_.y, np_.w, np_.h) == (279, 0, 41, 50), 'unexpected specfolder_page Now Playing'
    assert (all_.x, all_.y, all_.w, all_.h) == (229, 0, 38, 50), 'unexpected specfolder_page select-all button'
    np_.x, np_.y, np_.w, np_.h = NAV_NP
    all_.x, all_.w = 214, 46
    title = one(root, 'label_title', 'label')
    if title.x == 90:   # theme1 centres the title; the Pod navbar's is at 36, 14, left aligned
        assert (title.y, title.w, title.h) == (14, 129, 22), 'unexpected specfolder_page title'
        title.x, title.w = 36, 180


NAVBAR_UI_EDITS = {   # edited in both themes (each has its own file)
    'playset/equalizer_page.bin': edit_equalizer,
    'systemset/specfolder_page.bin': edit_specfolder,
}


def build_navbar_ui(work):
    report = []
    for rel, fn in NAVBAR_UI_EDITS.items():
        for theme in mod_lists.THEMES:
            path = os.path.join(work, mod_lists.RAW.format(theme=theme), 'ui', rel)
            old, new, root = edit_ui(path, fn)
            names = lambda d: [(w.type, w.name) for w in awtk_ui.parse(d).walk()]
            assert names(old) == names(new), f'{rel}: a widget was added, removed or renamed'
            report.append(f'{theme}/ui/{rel}: {len(old)} -> {len(new)} bytes')
    return report


UI_EDITS = {
    'albuminfo_page.bin': edit_albuminfo,
    'localclass_page.bin': lambda r: row_height(r, 'localclass_table_client'),
    'allmusic_page.bin': edit_allmusic,
    'playerjumpinfo_page.bin': edit_jumplist,
    'album_page.bin': lambda r: item_height(r, 'album_listview'),
    'playlist_page.bin': lambda r: item_height(r, 'playlist_listview'),
}


def build_ui(work):
    report = []
    for rel, fn in UI_EDITS.items():
        path = os.path.join(work, mod_lists.RAW.format(theme='default'), 'ui', rel)
        assert not os.path.exists(os.path.join(work, mod_lists.RAW.format(theme='theme1'), 'ui', rel)), f'theme1 has its own {rel}'
        old, new, root = edit_ui(path, fn)
        names = lambda d: [(w.type, w.name) for w in awtk_ui.parse(d).walk()]
        want = names(old) + ([('image', TINT_NAME)] if rel == 'albuminfo_page.bin' else [])
        assert sorted(names(new), key=str) == sorted(want, key=str), f'{rel}: a widget was added, removed or renamed'
        report.append(f'ui/{rel}: {len(old)} -> {len(new)} bytes')
    return report


# The album view (patch/albuminfo.c): the styles its hook applies to the stock header. They are new
# names in the page theme only, so a header the hook leaves alone keeps stock's btn_imgplayall_style and
# text styles. Title, artist and the year line are centred (an hscroll_label shows its text centred when
# it fits and scrolls it, with ellipses, when it does not, as the Cover Flow captions do).
ALBUM_VIEW = 'albuminfo_page'
PLAY_STYLE, SHUF_STYLE = 'btn_ahplay_style', 'btn_ahshuf_style'
TITLE_STYLE, ARTIST_STYLE, META_STYLE = 'srlabel_ahtitle_style', 'srlabel_ahartist_style', 'srlabel_ahmeta_style'
HEAD_STYLE, HEAD_SRC = 'list_item_ahhead_style', 'list_item_notpress_style'
ROW_STYLE, ROW_PRESSED, ROW_HAIR = 'list_item_style', '#FFFFFF33', '#FFFFFF22'   # the track rows on this page: transparent, pressed 20 % white, hairline 13 % white
TITLE_PX, ARTIST_PX, META_PX = 22, 18, 15
TITLE_COLOR, ARTIST_COLOR, META_COLOR = '#FFFFFF', '#AAAAAA', '#9C9C9C'   # the design's #8C8C8C is 3.8:1 on the page's #333333 pressed row: mod_theme --scan wants 4.5
PLAY_INK, PLAY_PX = '#FFFFFF', 18          # the pill's fill is its bg_image (PLAY_BG_IMAGE): the mini bar's glass (mod_icons.glass_image), pressed one lighter
PLAY_BG_IMAGE, PLAY_BG_IMAGE_DOWN, IMAGE_CENTER = 'ah_pill', 'ah_pill_down', 2   # bg_image_draw_type: DEFAULT 0, ICON 1, CENTER 2 (centred at its own size)
TRACK_PX = 19                                                # the track rows' title and number on this page (the other pages keep 21)
PLAY_ICON, SHUF_ICON, SHUF_ICON_DOWN = 'ah_play', 'ah_shuffle', 'ah_shuffle_down'   # tools/mod_icons.py ALBUM
CENTER, RIGHT = 1, 3                                         # text_align_h: left 2, centre 1, right 3
NUM_STYLE, NUM_COLOR = 'srlabel_tracknum_style', '#AAAAAA'   # patch/offsets.inc ROW_NUM_STYLE; the secondary grey (as the artist line)
# The pill's icon and text are laid out by widget_draw_icon_text (@0x67235c) and widget_calc_icon_text_rect (@0x666f04):
# icon_at 0 = auto, which is TOP when icon height + font size < the height left by the margins (16 + 18 < 44: the
# glyph above the text); 1 left, 2 right, 3 top, 4 bottom, 5 centre. With "left" the icon is centred in a square
# as high as the (margined) rect and the text goes in what is right of that square plus the spacer. DEVICE FINDING
# (V2.1nF screenshot): the text is drawn LEFT aligned at the start of that rect, not centred in it (text_align_h is read
# with the default 2 = left at @0x672588; V2.1nC assumed centred, so its negative spacer pulled the text onto the glyph).
# The glyph is centred in the 44 px square, so it ends 14 px before the square's end: spacer = gap - 14 puts the text
# `gap` px after the glyph's image. margin_left is set per page build by the hook (patch/albuminfo.c ah_centre_pill, from the
# measured text); the style carries the margin for an English text, which is also the fallback.
PLAY_ICON_AT, PLAY_ALIGN = 1, 2                              # icon_at left; text_align_h left (left 2, centre 1, right 3)
PLAY_GLYPH_W, PLAY_GLYPH_VIS = 16, 15                        # ah_play.png: the image, its opaque columns
PLAY_GAP, PLAY_MARGIN_L, PLAY_MARGIN_R = 8, 37, 0           # patch/offsets.inc AH_PILL_GAP, AH_PILL_MARGIN
PLAY_SPACER = PLAY_GAP - (44 - PLAY_GLYPH_W) // 2            # -6


def pill_margin(text_w, w=180, h=44):
    """margin_left that centres glyph + gap + text in the pill (the hook's formula), or None when it does not fit."""
    m = (w - (PLAY_GLYPH_W + PLAY_GAP + text_w)) // 2 - (h - PLAY_GLYPH_W) // 2
    return m if text_w > 0 and m >= 0 else None


def pill_layout(text_w, w=180, h=44, margin_left=None):
    """Where AWTK draws the pill's glyph and text (x of the glyph's image, x of the text's pen, the text rect
    (x, w)), from the style numbers above and the measured text width; margin_left as the hook sets it (the style's
    when the text cannot be measured)."""
    m = pill_margin(text_w, w, h)
    ir_x = PLAY_MARGIN_L if margin_left is None and m is None else (m if margin_left is None else margin_left)
    ir_w = w - ir_x - PLAY_MARGIN_R
    sq = h                                                    # the icon square: ir.h x ir.h at ir.x
    icon_x = ir_x + sq // 2 - PLAY_GLYPH_W // 2               # canvas_draw_icon_in_rect: centred on the square
    rx, rw = ir_x + sq + PLAY_SPACER, ir_w - sq - PLAY_SPACER
    return icon_x, rx, (rx, rw)                               # the text is left aligned: its pen starts at the rect
# The navbar buttons' styles the stock builders (0x526a3c, 0x524e4c) name, and the glass disc (rest, pressed, icon_at, x_offset) each shows on this page
# (a page theme only: the artist's albums page shares the builders but not this theme). Every image is as wide as the button main's pins make it
# (tools/mod_icons.py AH_NAV_PIECES), centred in it (icon_at 5), so the glyph centres are the Pod navbar's: search 191, multi-select 237, Now Playing 290
# (60 px at 262: disc 269 .. 311), the select mode's add / delete / cancel in the stock 60 px buttons at 116 / 191 / 268 (146, 221, 290) and the all /
# unselect toggle in its 50 px one (29). Back keeps its stock rule, icon_at left in a button-high square: x_offset +4 (stock -6) puts the 42 px
# disc at x 8 .. 50 whether the builder made Back at (0, 50 high) or (3, 44 high): square centre x + h / 2 is 25 in both.
NAV_STYLES = {'navbar_btnreturn_style': ('ah_nav_back', 'ah_nav_back_down', 1, 4),
              'search_style': ('ah_nav_search', 'ah_nav_search_down', 5, 0),
              'navbar_btnmulselect_style': ('ah_nav_multi', 'ah_nav_multi_down', 5, 0),
              'navbar_btnbackplayer_style': ('ah_nav_npa', 'ah_nav_npa_down', 5, 0),
              'navbar_btnunselect_style': ('ah_nav_unsel', 'ah_nav_unsel_down', 5, 0),
              'navbar_btnselected_style': ('ah_nav_sel', None, 5, 0),
              'navbar_btnadd_style': ('ah_nav_add', 'ah_nav_add_down', 5, 0),
              'navbar_btndel_style': ('ah_nav_del', 'ah_nav_del_down', 5, 0),
              'navbar_btncancel_style': ('ah_nav_cancel', 'ah_nav_cancel_down', 5, 0)}
NAVBAR_TITLES = ('navbar_label_white', 'navbar_leftlabel_white', 'navbar_centerlabel_white', 'navbar_rightlabel_white')


def album_view_styles(page, base):
    """The header's styles: srlabel_ahtitle / ahartist / ahmeta (the stock white and grey lines, centred, 22 px
    white, 18 px #AAAAAA, 13 px #9C9C9C); btn_ahplay_style, the Play all pill (white fill, round_radius 22, 20 px
    dark text, the play glyph image, #BEBEBE pressed); btn_ahshuf_style, the round Shuffle (its disc and glyph
    are images, pressed one lighter; no fill, no text). The navbar title labels' text is transparent on this
    page (the design shows Back and Now Playing only; the label stays, so nothing that looks it up changes)."""
    for state in ('normal', 'pressed', 'over', 'focused', 'disable'):
        s = awtk_style.Item('button', PLAY_STYLE, state)
        s.set_color('bg_color', '#00000000')   # the fill is the image: the button is AH_BTN_H high for the touch, the pill AH_PILL_H
        s.set('bg_image', PLAY_BG_IMAGE_DOWN if state == 'pressed' else PLAY_BG_IMAGE, awtk_style.T_STRING)
        s.set('bg_image_draw_type', IMAGE_CENTER, awtk_style.T_UINT32)
        s.set_color('text_color', PLAY_INK)
        s.set('font_size', PLAY_PX, awtk_style.T_UINT32)
        s.set('icon', PLAY_ICON, awtk_style.T_STRING)
        s.set('icon_at', PLAY_ICON_AT, awtk_style.T_INT32)
        s.set('margin_left', PLAY_MARGIN_L, awtk_style.T_INT32)
        s.set('margin_right', PLAY_MARGIN_R, awtk_style.T_INT32)
        s.set('spacer', PLAY_SPACER, awtk_style.T_INT32)
        s.set('text_align_h', PLAY_ALIGN, awtk_style.T_INT32)
        page.put(s)
        s = awtk_style.Item('button', SHUF_STYLE, state)
        s.set_color('bg_color', '#00000000')
        s.set('icon', SHUF_ICON_DOWN if state == 'pressed' else SHUF_ICON, awtk_style.T_STRING)
        page.put(s)
    # the floating controls: the navbar buttons' own styles, overridden on this page only. Every state the glass piece (an icon: the piece
    # is one image, tools/mod_icons.py ah_nav_images), no fill, centred in the button; pressed = the lighter piece.
    for style, (rest, down, icon_at, x_offset) in NAV_STYLES.items():
        for state in ('normal', 'pressed', 'over', 'focused', 'disable'):
            s = awtk_style.Item('button', style, state)
            s.set_color('bg_color', '#00000000'); s.set_color('border_color', '#00000000'); s.set_color('text_color', '#FFFFFF')
            s.set('icon', down if state == 'pressed' and down else rest, awtk_style.T_STRING)
            s.set('icon_at', icon_at, awtk_style.T_INT32)
            if x_offset: s.set('x_offset', x_offset, awtk_style.T_INT32)
            page.put(s)
    # the track rows (the stock list_item_style, resolved in this page's theme first): transparent, so the deep tint under the
    # list shows; the pressed band and the 1 px hairline are translucent white, which over a black page is exactly today's
    # #333333 and #222222 (51 and 34 levels of 255)
    for s in base.states('list_item', ROW_STYLE):
        n = mod_lists.copy(s)
        n.set_color('bg_color', ROW_PRESSED if s.state == 'pressed' else '#00000000')
        n.set_color('border_color', ROW_HAIR)
        n.set('border_width', 1, awtk_style.T_UINT32)   # theme1's stock rows have a 4 px black gap there; here a hairline in both themes
        page.put(n)
    for s in base.states('list_item', HEAD_SRC):   # the header item: the stock notpress look, transparent (the window's colour and the tint show)
        n = mod_lists.copy(s, HEAD_STYLE)
        n.set_color('bg_color', '#00000000'); n.set_color('border_color', '#00000000')
        page.put(n)
    for name, src_name, px, color in ((TITLE_STYLE, 'srlabel_item_white_style', TITLE_PX, TITLE_COLOR),
                                      (ARTIST_STYLE, 'srlabel_item_gray18_style', ARTIST_PX, ARTIST_COLOR),
                                      (META_STYLE, 'srlabel_item_gray18_style', META_PX, META_COLOR)):
        src = base.states('hscroll_label', src_name)
        assert src, f'default.bin has no {src_name}'
        for s in src:
            n = mod_lists.copy(s, name)
            n.set('font_size', px, awtk_style.T_UINT32)
            n.set_color('text_color', color)
            n.set('text_align_h', CENTER, awtk_style.T_INT32)
            page.put(n)
    # the track rows' title (white, and the playing row's gold) and number, TRACK_PX like the number: the rows keep their 64 px
    for name in ('srlabel_item_white_style', 'srlabel_item_gold20_style'):
        for s in base.states('hscroll_label', name):
            n = mod_lists.copy(s); n.set('font_size', TRACK_PX, awtk_style.T_UINT32); page.put(n)
    # the track rows' number (patch/rows.c rows_track_number): a plain label, so type 'label'; the grey line's colour, the
    # title's size, right aligned in its fixed column (ROW_NUM_W). #AAAAAA is 5.44:1 on the #333333 pressed row.
    src = base.states('hscroll_label', 'srlabel_item_gray18_style')
    assert src, 'default.bin has no srlabel_item_gray18_style'
    for s in src:
        n = awtk_style.Item('label', NUM_STYLE, s.state, list(s.props))
        n.set('font_size', TRACK_PX, awtk_style.T_UINT32)
        n.set_color('text_color', NUM_COLOR)
        n.set('text_align_h', RIGHT, awtk_style.T_INT32)
        page.put(n)
    hidden = 0
    for name in NAVBAR_TITLES:
        for s in base.states('label', name):
            n = mod_lists.copy(s)
            n.set_color('text_color', '#00000000')
            page.put(n); hidden += 1
    assert hidden == 12, f'unexpected navbar title styles ({hidden})'


def style_rels():
    return [(t, p, f'release/assets/{t}/raw/styles/{p}.bin') for t in mod_lists.THEMES for p in TITLE_PAGES]


def added_rels(stock_rootfs):
    """Page themes this step adds that neither stock nor the lists step has (fwtool --allow-added)."""
    lists = set(mod_lists.added_rels(stock_rootfs))
    return [rel for _, _, rel in style_rels() if not os.path.exists(os.path.join(stock_rootfs, rel)) and rel not in lists]


def build_page_themes(work):
    """The 21 px title on TITLE_PAGES, in each theme's page file (its own, else default's)."""
    sources = {}
    for theme, page, rel in style_rels():
        own = mod_lists.read(os.path.join(work, 'rootfs', rel))
        sources[rel] = (own is not None, own if own is not None else
                        mod_lists.read(os.path.join(work, mod_lists.RAW.format(theme='default'), 'styles', f'{page}.bin')))
    report = []
    for theme, page, rel in style_rels():
        base_raw = mod_lists.read(os.path.join(work, mod_lists.RAW.format(theme=theme), 'styles', 'default.bin'))
        base = mod_lists.parse(base_raw)
        assert awtk_style.serialize(base.th) == base_raw, f'{theme}/default.bin: style round trip is not byte-exact'
        existed, old = sources[rel]
        th = mod_lists.parse(old) if old else mod_lists.Theme(awtk_style.Theme())
        if old: assert awtk_style.serialize(th.th) == old, f'{rel}: style round trip is not byte-exact'
        mod_lists.r_title(th, base, None)
        gray = base.find('hscroll_label', 'srlabel_item_gray18_style', 'normal')
        assert gray and gray.get('font_size') == 18, 'the grey line is not 18 px'
        if page == ALBUM_VIEW: album_view_styles(th, base)
        new = awtk_style.serialize(th.th)
        assert awtk_style.serialize(awtk_style.parse(new)) == new
        path = os.path.join(work, 'rootfs', rel)
        mtime = os.stat(path).st_mtime if existed else None
        mod_lists.write_file(path, new, existed)
        if mtime is not None:   # files the lists step added carry its fixed mtime: keep it (deterministic)
            os.utime(path, (mtime, mtime))
        report.append(f'{rel}: {"edited" if existed else "added"} {len(old) if existed else 0} -> {len(new)} bytes')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('out')
    a = ap.parse_args()
    clone_workdir(a.src, a.out)
    for line in build_ui(a.out) + build_navbar_ui(a.out) + build_page_themes(a.out): print('rows:', line)


if __name__ == '__main__': main()
