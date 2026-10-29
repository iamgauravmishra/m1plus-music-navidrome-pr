#!/usr/bin/env python3
"""Build the M1+ Pod page assets (ui/*.bin) from tools/pod_pages.py.

These are new AWTK UI files, not edits of stock ones, so they are added to the rootfs (fwtool
repack --allow-added lists them). Each page is a window with a stock-styled navigation bar (title,
Back, Now Playing) over a column of touch-friendly row buttons; the hello page shows a label
instead. Row widget names are pod_row0, pod_row1, ... so patch/m1pod.c can bind them by name.

Layout follows q2-pod's iPod menu (docs/ipod.md) adapted to 320x480 touch, inside the 450 px a
normal window gets under the 30 px status bar: a 50 px navbar over a stock-structured scrolling
list of 52 px rows (400 px visible, so seven and a half rows show and the rest scroll into view).
Cover Flow's page has its own layout.

Usage: pod_ui.py WORKDIR   (writes ui/*.bin into WORKDIR/rootfs; prints the files)
"""
import argparse, os, stat, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
from awtk_ui import Widget
import pod_i18n, pod_pages

UI = 'release/assets/default/raw/ui'   # relative to a rootfs dir
SCREEN_W, SCREEN_H = 320, 480
# A normal window gets the screen under the 30 px system_bar: 450 px. 68 stock pages end exactly at
# y=450 (systemset/sysset_page.bin: navbar 0-50, list 50-450); only fullscreen windows
# (screensaver_page, fullscreen=true) use all 480.
CLIENT_H = 450
NAVBAR_H = 50
ROW_H = 52        # every row page uses full-height rows and scrolls when they do not fit
UI_MODE = 0o744         # stock ui/*.bin mode
UI_MTIME = 1750924035   # a stock ui/*.bin mtime (2025-06-26); fixed so added assets build deterministically


def styled(w, states, prop, value):
    for st in states: w.set(f'style:{st}:{prop}', value)


def _offsets():
    import re
    out = {}
    for line in open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'patch', 'offsets.inc')):
        m = re.match(r'#define (\w+) (-?(?:0x[0-9a-fA-F]+|\d+))u?\s*(?:/\*.*)?$', line.strip())
        if m: out[m.group(1)] = int(m.group(2), 0)
    return out


OFFSETS = _offsets()


# The navbar toggle of the Pod pages (Albums grid, Artists), flush left of Now Playing (x 260): a plain white glyph
# showing the view a tap switches to (the Albums page swaps the glyph with its mode, as the Artists page does).
NAV_VIEW_X, NAV_VIEW_W = 214, 46     # patch/offsets.inc NAV_VIEW_X, NAV_VIEW_W: main's slots (docs/modules/navbar.md); the glass capsule's pieces are cut to them (docs/modules/navbar.md)
NAV_VIEW_ICON = {'list': 'pod_nav_list', 'grid': 'pod_nav_grid',
                 'artist': 'pod_nav_albumartist'}   # images added by tools/mod_icons.py (glass pieces); artist: built in Artist mode, so the Album Artist glyph
TOGGLE_NAME = {'list': 'btn_albumview', 'grid': 'btn_albumview', 'artist': 'btn_artisttype'}
# The Albums page's Cover Flow button, flush left of the toggle: the capsule's left cap.
NAV_CF_W = NAV_VIEW_W
NAV_CF_X = NAV_VIEW_X - NAV_CF_W     # 168; patch/offsets.inc NAV_CF_X, NAV_CF_W
NAV_CF_ICON = 'pod_nav_coverflow'
NAV_BACK_X, NAV_BACK_W = 7, 44       # Back: the glass disc ah_nav_back (42 px) centred in a 44 x 50 button: x 8 .. 50, y 4 .. 46 (img_btn_style, so the shared navbar_btnreturn_style and the stock pages are untouched)
NAV_TITLE_X = 58                     # the title starts 8 px after the disc
NAV_PLAY_X, NAV_PLAY_W = 260, 60     # Now Playing: main's button; its image is the disc ah_nav_np alone (glyph centre 290) or a capsule's right cap ah_nav_play (same glyph, the glass ends at x 311)
NAV_TITLE_END = NAV_PLAY_X            # a title with no toggle ends before Now Playing's button (its disc starts at 269)


NAV_ALL_ICON = 'pod_nav_allalbums'
NB_FADE_NAME, NB_FADE_H = 'img_nb_fade', 20     # the soft fade under the bar (tools/mod_icons.py NB_FADE; mod_ipodrows.NB_FADE_NAME)


def nav_fade(shown=True):
    """The fade over the first rows of the list under the bar: an insensitive image (never takes a touch), right after the list.
    shown=False (the cover pages, whose first row would be darkened at rest): built hidden, the page's code shows it while the list is scrolled."""
    w = Widget('image', 0, NAVBAR_H, SCREEN_W, NB_FADE_H, [('name', NB_FADE_NAME), ('image', 'nb_fade'), ('draw_type', 'default'),
                                                           ('clickable', 'false'), ('sensitive', 'false')])
    if not shown: w.set('visible', 'false')
    return w


def navbar(title, toggle=None, coverflow=False, allalbums=False, more=False):
    nb = Widget('view', 0, 0, SCREEN_W, NAVBAR_H, [('name', 'navigationbar_view')])
    # a title runs under a toggle's button no further than the button's left edge
    right = NAV_CF_X if coverflow or more else NAV_VIEW_X if toggle else NAV_TITLE_END
    lbl = Widget('label', NAV_TITLE_X, 14, right - NAV_TITLE_X, 22,
                 [('name', 'label_title'), ('style', 'navbar_label_white'), ('length', '31'), pod_i18n.text_prop(title)])
    ret = Widget('button', NAV_BACK_X, 0, NAV_BACK_W, NAVBAR_H, [
        ('name', 'btn_return'), ('enable', 'true'), ('style', 'img_btn_style'),
        ('style:over:icon', 'ah_nav_back'), ('style:normal:icon', 'ah_nav_back'), ('style:pressed:icon', 'ah_nav_back_down')])
    img = 'ah_nav_play' if toggle or coverflow or more else 'ah_nav_np'   # a toggle / button makes Now Playing the capsule's right cap; else a disc
    player = Widget('button', NAV_PLAY_X, 0, NAV_PLAY_W, NAVBAR_H, [
        ('name', 'btn_backtoplayer'), ('enable', 'true'), ('style', 'img_btn_style'),
        ('style:pressed:icon', img + '_down'), ('style:normal:icon', img), ('style:over:icon', img)])
    nb.children = [lbl, ret, player]
    if toggle:
        icon = NAV_VIEW_ICON[toggle]
        nb.children.append(Widget('button', NAV_VIEW_X, 0, NAV_VIEW_W, NAVBAR_H, [
            ('name', TOGGLE_NAME[toggle]), ('enable', 'true'), ('style', 'img_btn_style'),
            ('style:pressed:icon', icon + '_down'), ('style:normal:icon', icon), ('style:over:icon', icon)]))
    if coverflow:
        nb.children.append(Widget('button', NAV_CF_X, 0, NAV_CF_W, NAVBAR_H, [
            ('name', 'btn_coverflow'), ('enable', 'true'), ('style', 'img_btn_style'),
            ('style:pressed:icon', NAV_CF_ICON + '_down'), ('style:normal:icon', NAV_CF_ICON), ('style:over:icon', NAV_CF_ICON)]))
    if more:   # the Playlists page's "..." menu button, in the Cover Flow button's place
        nb.children.append(Widget('button', NAV_CF_X, 0, NAV_CF_W, NAVBAR_H, [
            ('name', 'btn_more'), ('enable', 'true'), ('style', 'img_btn_style'),
            ('style:pressed:icon', 'pod_nav_more_down'), ('style:normal:icon', 'pod_nav_more'), ('style:over:icon', 'pod_nav_more')]))
    if allalbums:   # Cover Flow's artist page (patch/coverflow.c shows it, and shortens the title, only there)
        nb.children.append(hidden(Widget('button', NAV_VIEW_X, 0, NAV_VIEW_W, NAVBAR_H, [
            ('name', 'btn_allalbums'), ('enable', 'true'), ('style', 'img_btn_style'),
            ('style:pressed:icon', NAV_ALL_ICON + '_down'), ('style:normal:icon', NAV_ALL_ICON), ('style:over:icon', NAV_ALL_ICON)])))
    return nb


SWITCH_W, SWITCH_H, SWITCH_MARGIN = 57, 28, 12   # the stock on/off switch image (sset_on / sset_off) and its right margin
UP_W = 50                                        # the Main Menu page's up arrow button, left of the switch


def switch_x(w): return w - SWITCH_MARGIN - SWITCH_W


def switch_image(name, w, h, on):
    """The stock on/off switch (systemset/powermanager_page.bin's img_switch*: an image of sset_on / sset_off, the
    themed toggle art). Insensitive: the row takes the tap. The payload swaps the image at run time."""
    return Widget('image', switch_x(w), (h - SWITCH_H) // 2, SWITCH_W, SWITCH_H, [
        ('name', name), ('image', 'sset_on' if on else 'sset_off'), ('draw_type', 'default'), ('sensitive', 'false')])


VALUE_W, VALUE_PX = 110, 19                      # a value row's grey value (Settings > Cover Flow > Sort): right aligned, 12 px margin


def value_x(w): return w - SWITCH_MARGIN - VALUE_W


def value_label(name, w, h, english):
    """The value at the right of a value row, #AAAAAA like the library rows' second line. Insensitive: the row takes the tap.
    The payload sets it with widget_set_tr_text, so it follows the language."""
    lab = Widget('label', value_x(w), 0, VALUE_W, h, [('name', name), pod_i18n.text_prop(english), ('sensitive', 'false')])
    styled(lab, ('normal',), 'text_color', '#AAAAAA')
    styled(lab, ('normal',), 'font_size', str(VALUE_PX))
    styled(lab, ('normal',), 'text_align_h', 'right')
    styled(lab, ('normal',), 'text_align_v', 'middle')
    return lab


def row_item(name, y, label, chevron, h=ROW_H, w=SCREEN_W, switch=None, value=None):
    """A row built like stock's scrolling rows (systemset_sysset_page_init @0x4adb7c): a list_item
    themed "list_item_style" holding an hscroll_label themed "srlabel_leftwhite21_style" (white,
    21 px, left; scrolls only while its row has focus, ellipsis) and, for navigating rows, the
    stock "right_arrow" image. Stock's own widget and theme styles, so the look matches the
    settings lists in every state and drags reach the scroll_view as in every stock list."""
    item = Widget('list_item', 0, y, w, h, [('name', name), ('style', 'list_item_style')])
    text_w = (switch_x(w) if switch else value_x(w) if value else w - (44 if chevron else 12)) - 24
    item.children.append(Widget('hscroll_label', 24, 0, text_w, h, [
        ('style', 'srlabel_leftwhite21_style'), pod_i18n.text_prop(label), ('only_parent_focus', 'true'),
        ('ellipses', 'true'), ('yoyo', 'true'), ('loop', 'true')]))
    if chevron:
        item.children.append(Widget('image', w - 44, 0, 40, h, [
            ('image', 'right_arrow'), ('draw_type', 'icon')]))
    if switch:   # switch = (widget name, state)
        item.children.append(switch_image(switch[0], w, h, switch[1]))
    if value:    # value = (widget name, English text)
        item.children.append(value_label(value[0], w, h, value[1]))
    return item


def label(name, x, y, w, h, text, size, colour, align='center'):
    lab = Widget('label', x, y, w, h, [('name', name), ('text', text)])
    styled(lab, ('normal',), 'text_color', colour)
    styled(lab, ('normal',), 'font_size', str(size))
    styled(lab, ('normal',), 'text_align_h', align)
    return lab


def hidden(w):
    """Start hidden *and* insensitive. This demo's AWTK hit test (widget_find_target_default
    0x6747d4) checks only enable and sensitive, never visible, so a merely hidden widget still
    swallows every touch over its rectangle; patch/coverflow.c keeps the two in step at runtime."""
    w.set('visible', 'false')
    w.set('sensitive', 'false')
    return w


# Cover Flow's page layout (tests and previews read these): the shelf is 168 px covers in a 320x276
# frame (patch/offsets.inc), the captions hscroll_labels in 16 px side margins that scroll a long
# title back and forth (stock Now Playing's info lines: loop, yoyo, a 3 s lull at each end) and
# centre one that fits. The block is centred in the 400 px under the navbar: the art's top
# (COVER_Y + CF_TOP = 120) and the artist line's bottom (380) are 70 px from the body's edges; the
# album line starts 4 px below the reflections (CF_TOP + ART_SIZE + CF_REFLECT = 225).
COVER_FRAME_H = 276              # CF_VIEW_H
COVER_Y = NAVBAR_H + 39          # view_covers: 89..365
ALBUM_Y, ALBUM_H = COVER_Y + 229, 34      # 318..352
ARTIST_Y, ARTIST_H = ALBUM_Y + ALBUM_H, 28   # 352..380
CAPTION_X = 16                   # side margins of the scrolling captions
CAPTION_LULL = '3000'            # ms at each end, as playing_page.bin's label_album


def cover_layout():
    """(frame y, album y, album h, artist y, artist h) of the cover page."""
    return COVER_Y, ALBUM_Y, ALBUM_H, ARTIST_Y, ARTIST_H


def scroll_caption(name, y, h, size, colour):
    """A caption as stock Now Playing's info lines (playing_page.bin label_album): an hscroll_label,
    centred, white or grey in every state, that loops back and forth (yoyo) with a lull at each end
    when its text is wider than the box and shows it centred when it fits; ellipses for the frames
    it is not scrolling. Insensitive: it lies over the frame's black rows, whose touch layer takes
    the touch (this AWTK hit-tests insensitive widgets through, hidden ones not)."""
    w = Widget('hscroll_label', CAPTION_X, y, SCREEN_W - 2 * CAPTION_X, h, [('name', name), ('text', '')])
    for st in ('normal', 'disable', 'focused'):
        styled(w, (st,), 'font_size', str(size))
        styled(w, (st,), 'text_color', colour)
        styled(w, (st,), 'text_align_h', 'center')
    for k, v in (('yoyo', 'true'), ('loop', 'true'), ('lull', CAPTION_LULL), ('ellipses', 'true'),
                 ('sensitive', 'false')):
        w.set(k, v)
    return w


def build_cover_page(page):
    """Cover Flow's page: the covers frame, the scrolling album and artist captions under the
    covers, and the first-run cache build's progress label and Cancel button. patch/coverflow.c
    fills view_covers with a stock slide_menu; the frame's size must match the CF_* constants in
    patch/offsets.inc."""
    root = Widget('window', 0, 0, 0, 0, [('name', page.name)])
    styled(root, ('normal', 'disable', 'focused'), 'bg_color', '#000000')
    root.children.append(navbar(page.title, allalbums=True))
    fy, ay, ah, ry, rh = cover_layout()
    frame = Widget('view', 0, fy, SCREEN_W, COVER_FRAME_H, [('name', 'view_covers')])
    styled(frame, ('normal',), 'bg_color', '#000000')
    root.children.append(frame)
    root.children.append(scroll_caption('label_album', ay, ah, 22, '#FFFFFF'))
    root.children.append(scroll_caption('label_artist', ry, rh, 18, '#AAAAAA'))
    status = label('label_status', 10, 210, SCREEN_W - 20, 30, '', 20, '#FFFFFF')
    root.children.append(hidden(status))
    cancel = Widget('button', 100, 260, 120, 46, [('name', 'btn_cancel'), ('enable', 'true'),
                                                  pod_i18n.text_prop('Cancel')])
    for st in ('normal', 'over', 'focused', 'disable', 'selected'):
        styled(cancel, (st,), 'bg_color', '#1E1E1E')
        styled(cancel, (st,), 'text_color', '#FFFFFF')
        styled(cancel, (st,), 'font_size', '20')
        styled(cancel, (st,), 'border_color', '#3A3A3A')
        styled(cancel, (st,), 'border_width', '1')
    styled(cancel, ('pressed',), 'bg_color', '#2A2A2A')
    styled(cancel, ('pressed',), 'text_color', '#FFFFFF')
    styled(cancel, ('pressed',), 'font_size', '20')
    root.children.append(hidden(cancel))
    return root


def stock_list(rows, scroll):
    """The structure and properties of systemset/sysset_page.bin's list, the stock scrolling list:
    list_view (default_item_height, black in every state) > scroll_view (310 wide when a bar is
    there, the speed scales) + scroll_bar_m (10 px, max 1000) at the right."""
    list_h = CLIENT_H - NAVBAR_H
    sv_w = SCREEN_W - 10 if scroll else SCREEN_W
    lv = Widget('list_view', 0, NAVBAR_H, SCREEN_W, list_h, [
        ('name', 'pod_listview'), ('default_item_height', str(ROW_H))])
    for st in ('normal', 'disable', 'focused'):
        lv.set(f'style:{st}:bg_color', '#000000')
    for st in ('normal', 'disable', 'focused'):
        lv.set(f'style:{st}:border_color', '#00000000')
    lv.set('style:normal:border_width', '0')
    sv = Widget('scroll_view', 0, 0, sv_w, list_h, [
        ('name', 'pod_scrollview'), ('yspeed_scale', '1'), ('xspeed_scale', '1')])
    for i, r in enumerate(rows):
        chevron = r.action not in (pod_pages.ACT_PLAYER, pod_pages.ACT_SHUFFLE) + pod_pages.SWITCH_ACTIONS + pod_pages.VALUE_ACTIONS   # rows that play, switch or show a value: no chevron
        switch = (f'pod_switch{i}', False) if r.action in pod_pages.SWITCH_ACTIONS else None   # the payload sets the state at open
        value = (f'pod_value{i}', pod_pages.SORT_VALUES[0]) if r.action in pod_pages.VALUE_ACTIONS else None   # ... and the value
        sv.children.append(row_item(f'pod_row{i}', i * ROW_H, r.label, chevron, ROW_H, sv_w, switch, value))
    lv.children = [sv]
    if scroll:   # stock's scroll bar, only when there is something to scroll
        lv.children.append(Widget('scroll_bar_m', sv_w, 0, 10, list_h,
                                  [('name', 'scroll_bar_m'), ('max', '1000')]))
    return lv


def build_list_page(page):
    """A page whose rows the payload builds at runtime (patch/artists.c): the navbar with the
    Artist / Album Artist toggle, an empty stock list (with its scroll bar: the rows usually
    overflow), and a hidden message line for an empty library."""
    root = Widget('window', 0, 0, 0, 0, [('name', page.name)])
    styled(root, ('normal', 'disable', 'focused'), 'bg_color', '#000000')
    root.children.append(navbar(page.title, toggle='artist'))
    root.children.append(stock_list([], True))
    root.children.append(nav_fade())
    root.children.append(hidden(label('label_status', 10, 210, SCREEN_W - 20, 30, '', 20, '#FFFFFF')))
    return root


# The Albums page (patch/albums.c): a stock list (list_view > scroll_view) under the navbar whose one child, view_grid, paints the covers and titles itself.
# Its style carries the title text (16 px white, left, middle), which widget_prepare_text_style reads.
GRID_VIEW_H = CLIENT_H - NAVBAR_H     # patch/offsets.inc GRID_VIEW_H
GRID_TITLE_PX = 16
GRID_ALBUM_PX, GRID_ARTIST_PX = 18, 15   # the grid's album / artist text under each cover (white / #AAAAAA)
LIST_TITLE_PX, LIST_SUB_PX = 21, 18   # the list mode's album / artist text (the library rows': 21 px white, 18 px #AAAAAA)


def build_grid_page(page, toggle='list', coverflow=True, names=('albums_listview', 'albums_scrollview'), more=False):
    root = Widget('window', 0, 0, 0, 0, [('name', page.name)])
    styled(root, ('normal', 'disable', 'focused'), 'bg_color', '#000000')
    root.children.append(navbar(page.title, toggle=toggle, coverflow=coverflow, more=more))
    lv = stock_list([], True)   # the library lists' structure: list_view > scroll_view 310 wide + scroll_bar_m. The mobile bar is not decoration: the list_view layouter makes the scroll_view yslidable only for it (0x60b1c8), scroll_view_create leaves it 0
    lv.set('name', names[0])
    sv = lv.children[0]
    sv.set('name', names[1])
    grid = Widget('view', 0, 0, SCREEN_W, GRID_VIEW_H, [('name', 'view_grid')])   # the content: the payload sizes it to the whole library
    styled(grid, ('normal',), 'bg_color', '#000000')
    styled(grid, ('normal',), 'text_color', '#FFFFFF')
    styled(grid, ('normal',), 'font_size', str(GRID_TITLE_PX))
    styled(grid, ('normal',), 'text_align_h', 'left')
    styled(grid, ('normal',), 'text_align_v', 'middle')
    sv.children.append(grid)
    root.children.append(lv)
    root.children.append(nav_fade(shown=False))   # patch/albums.c / playlists.c show it while yoffset > 0
    root.children.append(hidden(label('label_status', 10, 210, SCREEN_W - 20, 30, '', 20, '#FFFFFF')))
    # The two modes' text styles (patch/albums.c reads them with widget_prepare_text_style; never shown)
    for name, px, colour in (('label_row_title', LIST_TITLE_PX, '#FFFFFF'), ('label_row_sub', LIST_SUB_PX, '#AAAAAA'),
                             ('label_grid_title', GRID_ALBUM_PX, '#FFFFFF'), ('label_grid_sub', GRID_ARTIST_PX, '#AAAAAA')):
        lab = hidden(label(name, 0, 0, 10, 10, '', px, colour, 'left'))
        styled(lab, ('normal',), 'text_align_v', 'middle')
        root.children.append(lab)
    return root


# The Playlists page (patch/playlists.c): the Albums grid's structure (a stock list holding the one content view that paints the cells) under a navbar
# with a "..." button at the toggle's place, and the popup menu: a full-window scrim (a tap outside closes it; it dims the page as Now Playing's
# More sheet's highlighter does) and a card under the button in that sheet's glass (pl_glass: tools/mod_icons.py, all four corners rounded, drawn
# patch3_x so the payload can narrow the card to the language: the image's middle third stretches, its gradient is vertical only) of PL_ROW_H rows
# filling it, each a button (transparent, the sheet's 6 % white pressed, its 13 % white hairline above every row but the first) with a 20 px glyph
# (tools/mod_icons.py PL_MENU_ICONS) and its label, as the sheet's rows. All of it starts hidden and insensitive; the payload shows the scrim and
# the card together.
STATES = ('normal', 'pressed', 'over', 'focused', 'disable', 'selected')
PL_CARD_RIGHT, PL_CARD_Y, PL_ROW_H, PL_CARD_R, PL_ICON_X, PL_TEXT_X, PL_TEXT_R, PL_CARD_MIN, PL_CARD_MAX = (OFFSETS[k] for k in (
    'PL_CARD_RIGHT', 'PL_CARD_Y', 'PL_ROW_H', 'PL_CARD_R', 'PL_ICON_X', 'PL_TEXT_X', 'PL_TEXT_R', 'PL_CARD_MIN', 'PL_CARD_MAX'))
PL_CARD_H = OFFSETS['PL_MENU_ROWS'] * PL_ROW_H
PL_LABEL_PX = 18
PL_GLASS = 'pl_glass'
PL_DIM = '#00000082'          # the sheet's highlight="default(alpha=130)" (tools/mod_lists.py edit_playmore)
PL_PRESSED, PL_HAIR = '#FFFFFF10', '#FFFFFF22'   # the sheet's rows (tools/mod_lists.py PM_PRESSED, PM_HAIR)


def playlist_menu():
    """(scrim, card): the popup menu of the Playlists page, the card at its widest (PL_CARD_MAX); the payload narrows it."""
    assert len(pod_pages.PLAYLIST_MENU) == OFFSETS['PL_MENU_ROWS']
    scrim = hidden(Widget('button', 0, 0, SCREEN_W, CLIENT_H, [('name', 'pl_scrim'), ('enable', 'true')]))
    for st in STATES:
        styled(scrim, (st,), 'bg_color', PL_DIM)
        styled(scrim, (st,), 'text_color', '#FFFFFF')
        styled(scrim, (st,), 'border_width', '0')
        styled(scrim, (st,), 'border_color', '#00000000')
    card = hidden(Widget('view', PL_CARD_RIGHT - PL_CARD_MAX, PL_CARD_Y, PL_CARD_MAX, PL_CARD_H, [('name', 'pl_card')]))
    for st in STATES:
        styled(card, (st,), 'bg_color', '#00000000')
        styled(card, (st,), 'bg_image', PL_GLASS)
        styled(card, (st,), 'bg_image_draw_type', 'patch3_x')
        styled(card, (st,), 'border_width', '0')
    from mod_icons import PL_MENU_ICONS, PL_MENU_PX as PL_ICON
    for i, (text, (icon, _)) in enumerate(zip(pod_pages.PLAYLIST_MENU, PL_MENU_ICONS)):
        item = Widget('button', 0, i * PL_ROW_H, PL_CARD_MAX, PL_ROW_H, [('name', f'pl_item{i}'), ('enable', 'true')])
        for st in STATES:
            styled(item, (st,), 'bg_color', PL_PRESSED if st == 'pressed' else '#00000000')
            styled(item, (st,), 'text_color', '#FFFFFF')
            styled(item, (st,), 'border', 'top' if i else 'none')
            styled(item, (st,), 'border_width', '1' if i else '0')
            styled(item, (st,), 'border_color', PL_HAIR if i else '#00000000')
        item.children.append(Widget('image', PL_ICON_X, (PL_ROW_H - PL_ICON) // 2, PL_ICON, PL_ICON, [
            ('name', f'pl_icon{i}'), ('draw_type', 'default'), ('image', icon), ('sensitive', 'false')]))
        lab = Widget('hscroll_label', PL_TEXT_X, 0, PL_CARD_MAX - PL_TEXT_X - PL_TEXT_R, PL_ROW_H, [
            ('name', f'pl_label{i}'), pod_i18n.text_prop(text), ('only_parent_focus', 'true'), ('ellipses', 'true'), ('sensitive', 'false')])
        for st in ('normal', 'disable', 'focused'):
            styled(lab, (st,), 'font_size', str(PL_LABEL_PX))
            styled(lab, (st,), 'text_color', '#FFFFFF')
            styled(lab, (st,), 'text_align_h', 'left')
            styled(lab, (st,), 'text_align_v', 'middle')
        item.children.append(lab)
        card.children.append(item)
    return scrim, card


def build_playlists_page(page):
    root = build_grid_page(page, toggle='list', coverflow=False, more=True, names=('playlists_listview', 'playlists_scrollview'))
    root.children.extend(playlist_menu())   # last: above the list and the navbar
    return root


def build_menucfg_page(page):
    """The Main Menu page (patch/menu.c): a row per menu item in the default order, each with an up arrow (a stock
    button with the stock chevron-up art, expansion_2, insensitive: a picture, the row decides by the tap position)
    and a switch. The payload orders the rows, sets the switches and hides the arrows of the hidden items and of the
    first shown one."""
    root = Widget('window', 0, 0, 0, 0, [('name', page.name)])
    styled(root, ('normal', 'disable', 'focused'), 'bg_color', '#000000')
    root.children.append(navbar(page.title))
    lv = stock_list([], True)
    sv = lv.children[0]
    for i, r in enumerate(pod_pages.ITEMS):
        row = row_item(f'pod_row{i}', i * ROW_H, r.label, False, ROW_H, sv.w, (f'pod_switch{i}', i in pod_pages.DEFAULT_MENU))
        row.children[0].w = switch_x(sv.w) - UP_W - row.children[0].x
        row.children.append(Widget('button', switch_x(sv.w) - UP_W, 0, UP_W, ROW_H, [
            ('name', f'pod_up{i}'), ('enable', 'true'), ('sensitive', 'false'), ('style', 'img_btn_style'),
            ('style:pressed:icon', 'expansion_2_down'), ('style:normal:icon', 'expansion_2'), ('style:over:icon', 'expansion_2')]))
        sv.children.append(row)
    # the 19th row, last: the menu's Extras row (shown right above Settings, as saved by the list's trailing 'x'); a switch only,
    # no up arrow and no pod_up widget: it is never reordered
    n = len(pod_pages.ITEMS)
    sv.children.append(row_item(f'pod_row{n}', n * ROW_H, 'Extras', False, ROW_H, sv.w, (f'pod_switch{n}', pod_pages.DEFAULT_EXTRAS)))
    root.children.append(lv)
    root.children.append(nav_fade())
    return root


# The mini player bar of the menu's Home instance (patch/minibar.c, docs/modules/minibar.md): a hidden, insensitive view holding a
# floating glass pill (a button: the tap target that opens Now Playing; its look is the pre-rendered translucent image mb_glass), the
# title and artist as non-scrolling hscroll_labels (ellipsis), and the play, pause (one shows) and next buttons with the bare white bar glyphs (mb_*, tools/mod_icons.py). patch/offsets.inc MB_* hold the same numbers (test/pod/minibar.py asserts it).
MB_X, MB_Y, MB_W, MB_H, MB_R, MB_GAP = 8, 384, 304, 56, 28, 8
MB_ART, MB_ART_X, MB_ART_Y, MB_ART_R = 36, 14, 10, 5
MB_TEXT_X, MB_TEXT_W = 60, 130
MB_TITLE_Y, MB_TITLE_H, MB_TITLE_PX = 7, 22, 17
MB_ARTIST_Y, MB_ARTIST_H, MB_ARTIST_PX = 29, 20, 16
MB_PLAY_X, MB_NEXT_X, MB_BTN_W = 194, 245, 48
MB_GLASS, MB_GLASS_DOWN = 'mb_glass', 'mb_glass_down'   # the pill's images (tools/mod_icons.py glass_image, MB_W x MB_H, alpha): normal and pressed (brighter)
MB_PAD = 64                                  # the list's bottom padding while the bar shows: the window's 440 less (MB_Y - MB_GAP), so the last row scrolls clear above the pill
MB_TITLE_RGB, MB_ARTIST_RGB = '#FFFFFF', '#D0D0D0'
MB_NAMES = ('pod_minibar', 'pod_mb_card', 'pod_mb_title', 'pod_mb_artist', 'pod_mb_play', 'pod_mb_pause', 'pod_mb_next')


def minibar():
    bar = hidden(Widget('view', MB_X, MB_Y, MB_W, MB_H, [('name', 'pod_minibar')]))
    card = Widget('button', 0, 0, MB_W, MB_H, [('name', 'pod_mb_card'), ('enable', 'true')])
    for st in ('normal', 'pressed', 'over', 'focused', 'disable', 'selected'):
        styled(card, (st,), 'bg_color', '#00000000')   # the glass image is the whole look; nothing is filled or stroked under or over it
        styled(card, (st,), 'bg_image', MB_GLASS_DOWN if st == 'pressed' else MB_GLASS)
        styled(card, (st,), 'text_color', '#FFFFFF')   # the card has no text; every inline-styled button is dark with light text (test/pod/assets.py)
        styled(card, (st,), 'border_width', '0')
        styled(card, (st,), 'border_color', '#00000000')
    bar.children.append(card)
    for name, y, h, px, colour in (('pod_mb_title', MB_TITLE_Y, MB_TITLE_H, MB_TITLE_PX, MB_TITLE_RGB),
                                   ('pod_mb_artist', MB_ARTIST_Y, MB_ARTIST_H, MB_ARTIST_PX, MB_ARTIST_RGB)):
        lab = Widget('hscroll_label', MB_TEXT_X, y, MB_TEXT_W, h, [('name', name), ('text', ''), ('only_parent_focus', 'true'),
                                                                     ('ellipses', 'true'), ('sensitive', 'false')])
        for st in ('normal', 'disable', 'focused'):
            styled(lab, (st,), 'font_size', str(px))
            styled(lab, (st,), 'text_color', colour)
            styled(lab, (st,), 'text_align_h', 'left')
            styled(lab, (st,), 'text_align_v', 'middle')
        bar.children.append(lab)
    for name, x, icon, off in (('pod_mb_play', MB_PLAY_X, 'mb_play', False), ('pod_mb_pause', MB_PLAY_X, 'mb_pause', True),
                               ('pod_mb_next', MB_NEXT_X, 'mb_next', False)):
        btn = Widget('button', x, 0, MB_BTN_W, MB_H, [
            ('name', name), ('enable', 'true'), ('style', 'img_btn_style'),
            ('style:pressed:icon', icon + '_down'), ('style:normal:icon', icon), ('style:over:icon', icon)])
        bar.children.append(hidden(btn) if off else btn)
    return bar




# The Recently Played shelf of the menu's Home instance (patch/recent.c, docs/modules/recent.md): the Albums grid (patch/grid.c) in a view of its own, the child of
# the list's scroll view that follows the last shown row (Settings), a hidden and insensitive view the payload shows only when there is an album to show. The cell
# geometry is the Albums grid's: GRID_* are read from patch/offsets.inc, not copied. At its top a section header, the label pod_sh_head (the translation of
# "Recently Played", SH_HEAD_PX white, an hscroll_label that never scrolls and ends in an ellipsis, insensitive: a touch on it falls to the shelf, which has no cell
# there); the view then paints up to SH_TILES (GRID_COLS x SH_ROWS) covers and their two text lines itself (its own EVT_AFTER_PAINT) and takes the taps; the two hidden
# labels inside it only carry the text styles (widget_prepare_text_style: the grid's 18 px white album and 15 px #AAAAAA artist). The header's text lines up with the
# covers: the label starts 2 px before them and an hscroll_label insets its text 2 px. ceil(albums / 2) rows of covers, SH_H(n): the asset
# has the largest height (SH_HMAX), the payload sets the real one.
GRID_COLS, GRID_COVER, GRID_GAP, GRID_MARGIN, GRID_ROW_GAP, GRID_R = (OFFSETS[k] for k in ('GRID_COLS', 'GRID_COVER', 'GRID_GAP', 'GRID_MARGIN', 'GRID_ROW_GAP', 'GRID_R'))
GRID_TITLE_GAP, GRID_TITLE_H, GRID_SUB_H = (OFFSETS[k] for k in ('GRID_TITLE_GAP', 'GRID_TITLE_H', 'GRID_SUB_H'))
GRID_CELL_H = GRID_COVER + GRID_TITLE_GAP + GRID_TITLE_H + GRID_SUB_H      # 190
GRID_PITCH = GRID_CELL_H + GRID_ROW_GAP                                       # 200
SH_W, SH_ROWS = 310, 3
SH_TILES = GRID_COLS * SH_ROWS                    # 6: every album the file keeps (RC_MAX)
assert SH_TILES == OFFSETS['SH_TILES'] and SH_ROWS == OFFSETS['SH_ROWS'] == 3
SH_HEAD_X, SH_HEAD_W, SH_HEAD_TOP, SH_HEAD_H, SH_HEAD_PX, SH_HEAD_GAP = 10, 300, 17, 22, 20, 5   # the 20 px line's ink runs from 20 to 36 (the line box has slack): 20 px of air above, 8 below
SH_TOP = SH_HEAD_TOP + SH_HEAD_H + SH_HEAD_GAP     # 44: the first row of covers
SH_BOTTOM = 0                                      # the artist line's box ends the shelf: scrolled to the end it is MB_GAP above the pill, as the last row was
def SH_H(n): return SH_TOP + n * GRID_CELL_H + (n - 1) * GRID_ROW_GAP + SH_BOTTOM   # the shelf's height for n rows of covers: 234, 434, 634
SH_HMAX = SH_H(SH_ROWS)
SH_NAMES = ('pod_shelf', 'pod_sh_head', 'pod_sh_title', 'pod_sh_sub')
SH_TITLE_RGB, SH_SUB_RGB = '#FFFFFF', '#AAAAAA'
SH_TITLE_PX, SH_SUB_PX = GRID_ALBUM_PX, GRID_ARTIST_PX


def shelf():
    sh = hidden(Widget('view', 0, 0, SH_W, SH_HMAX, [('name', 'pod_shelf')]))
    styled(sh, ('normal', 'disable', 'focused', 'pressed', 'over', 'selected'), 'bg_color', '#000000')   # (no state of a plain view shows another colour)
    head = Widget('hscroll_label', SH_HEAD_X, SH_HEAD_TOP, SH_HEAD_W, SH_HEAD_H, [
        ('name', 'pod_sh_head'), pod_i18n.text_prop('Recently Played'), ('only_parent_focus', 'true'), ('ellipses', 'true'), ('sensitive', 'false')])
    for st in ('normal', 'disable', 'focused'):
        styled(head, (st,), 'font_size', str(SH_HEAD_PX))
        styled(head, (st,), 'text_color', SH_TITLE_RGB)
        styled(head, (st,), 'text_align_h', 'left')
        styled(head, (st,), 'text_align_v', 'middle')
    sh.children.append(head)
    for name, px, colour in (('pod_sh_title', SH_TITLE_PX, SH_TITLE_RGB), ('pod_sh_sub', SH_SUB_PX, SH_SUB_RGB)):
        lab = hidden(label(name, 0, 0, 10, 10, '', px, colour, 'left'))
        styled(lab, ('normal',), 'text_align_v', 'middle')
        sh.children.append(lab)
    return sh


def build_page(page):
    if page.kind == 'menucfg':
        return build_menucfg_page(page)
    if page.kind == 'grid':
        return build_grid_page(page)
    if page.kind == 'playlists':
        return build_playlists_page(page)
    if page.kind == 'cover':
        return build_cover_page(page)
    if page.kind == 'list':
        return build_list_page(page)
    root = Widget('window', 0, 0, 0, 0, [('name', page.name)])
    styled(root, ('normal', 'disable', 'focused'), 'bg_color', '#000000')
    root.children.append(navbar(page.title))
    lv = stock_list(page.rows, len(page.rows) * ROW_H > CLIENT_H - NAVBAR_H)
    root.children.append(lv)
    root.children.append(nav_fade())
    if page is pod_pages.MENU:   # the mini player bar (shown by the payload, on the Home instance only) and the list's padding under it
        sv = lv.children[0]
        assert sv.w == SH_W
        sv.children.append(shelf())   # after the rows (the payload moves it below the last shown row and shows it when there are albums to show)
        sv.children.append(hidden(Widget('view', 0, len(page.rows) * ROW_H, sv.w, MB_PAD, [('name', 'pod_pad')])))   # last child; the payload shows it with the bar
        root.children.append(minibar())
    return root


def write_assets(rootfs, pages):
    out = []
    for page in pages:
        root = build_page(page)
        data = awtk_ui.serialize(root)
        assert awtk_ui.parse(data).name == page.name, 'round-trip name mismatch'
        assert awtk_ui.serialize(awtk_ui.parse(data)) == data, 'asset does not round-trip byte-exact'
        rel = f'{UI}/{page.key}.bin'
        path = os.path.join(rootfs, rel)
        with open(path, 'wb') as f: f.write(data)
        os.chmod(path, UI_MODE)
        os.utime(path, (UI_MTIME, UI_MTIME))   # deterministic build: fixed mtime on added files
        out.append((rel, len(data)))
    return out


SYSTEM_BAR = f'{UI}/system_bar.bin'
SHOT_WIDGET = 'pod_shot'      # patch/shot.h SHOT_IND
SHOT_IMAGE, SHOT_W = 'pod_bar_shot', 16   # the 16 px camera tools/mod_icons.py adds to images/xx


def add_shot_indicator(rootfs):
    """The Screenshot countdown's camera: one hidden, insensitive image, the last child of the status bar's right-aligned
    icon group (view_bar_right, so after the Wi-Fi icon and next to the battery outline). The group's layouter skips
    an invisible child (widget_get_children_for_layout 0x657194, keep_invisible off), so while it is hidden the bar is
    laid out as stock; patch/shot.c shows it for the countdown, and the group then makes room for it: the icons to its
    left move 16 + 4 px left, the clock and the left group stay put."""
    def edit(root):
        right = root.find('view_bar_right')
        assert right is not None and root.find(SHOT_WIDGET) is None, 'unexpected system_bar layout'
        right.children.append(hidden(Widget('image', 0, 0, SHOT_W, 0, [('name', SHOT_WIDGET), ('image', SHOT_IMAGE), ('draw_type', 'center')])))
    from modlib import edit_ui
    edit_ui(os.path.join(rootfs, SYSTEM_BAR), edit)


def asset_rels(pages):
    return [f'{UI}/{p.key}.bin' for p in pages]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir')
    a = ap.parse_args()
    rootfs = os.path.join(a.workdir, 'rootfs') if os.path.isdir(os.path.join(a.workdir, 'rootfs')) else a.workdir
    for rel, n in write_assets(rootfs, pod_pages.PAGES):
        print(f'wrote {rel} ({n} bytes)')


if __name__ == '__main__': main()
