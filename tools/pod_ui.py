#!/usr/bin/env python3
"""Build the M1 Pod page assets (ui/*.bin) from tools/pod_pages.py.

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
import pod_pages

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


def navbar(title):
    nb = Widget('view', 0, 0, SCREEN_W, NAVBAR_H, [('name', 'navigationbar_view')])
    lbl = Widget('label', 36, 14, 248, 22, [('name', 'label_title'), ('style', 'navbar_label_white'),
                                            ('length', '31'), ('text', title)])
    ret = Widget('button', 0, 0, 80, NAVBAR_H, [
        ('name', 'btn_return'), ('enable', 'true'), ('style', 'navbar_btnreturn_style'),
        ('style:over:icon', 'return'), ('style:normal:icon', 'return'), ('style:pressed:icon', 'return_down')])
    player = Widget('button', 260, 0, 60, NAVBAR_H, [
        ('name', 'btn_backtoplayer'), ('enable', 'true'), ('style', 'img_btn_style'),
        ('style:pressed:icon', 'back_to_player_down'), ('style:normal:icon', 'back_to_player'),
        ('style:over:icon', 'back_to_player')])
    nb.children = [lbl, ret, player]
    return nb


def row_item(name, y, label, chevron, h=ROW_H, w=SCREEN_W):
    """A row built like stock's scrolling rows (systemset_sysset_page_init @0x4adb7c): a list_item
    themed "list_item_style" holding an hscroll_label themed "srlabel_leftwhite21_style" (white,
    21 px, left; scrolls only while its row has focus, ellipsis) and, for navigating rows, the
    stock "right_arrow" image. Stock's own widget and theme styles, so the look matches the
    settings lists in every state and drags reach the scroll_view as in every stock list."""
    item = Widget('list_item', 0, y, w, h, [('name', name), ('style', 'list_item_style')])
    text_w = w - 24 - (44 if chevron else 12)
    item.children.append(Widget('hscroll_label', 24, 0, text_w, h, [
        ('style', 'srlabel_leftwhite21_style'), ('text', label), ('only_parent_focus', 'true'),
        ('ellipses', 'true'), ('yoyo', 'true'), ('loop', 'true')]))
    if chevron:
        item.children.append(Widget('image', w - 44, 0, 40, h, [
            ('image', 'right_arrow'), ('draw_type', 'icon')]))
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
    root.children.append(navbar(page.title))
    fy, ay, ah, ry, rh = cover_layout()
    frame = Widget('view', 0, fy, SCREEN_W, COVER_FRAME_H, [('name', 'view_covers')])
    styled(frame, ('normal',), 'bg_color', '#000000')
    root.children.append(frame)
    root.children.append(scroll_caption('label_album', ay, ah, 22, '#FFFFFF'))
    root.children.append(scroll_caption('label_artist', ry, rh, 18, '#AAAAAA'))
    status = label('label_status', 10, 210, SCREEN_W - 20, 30, '', 20, '#FFFFFF')
    root.children.append(hidden(status))
    cancel = Widget('button', 100, 260, 120, 46, [('name', 'btn_cancel'), ('enable', 'true'),
                                                  ('text', 'Cancel')])
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
        chevron = r.action not in (pod_pages.ACT_PLAYER, pod_pages.ACT_SHUFFLE, pod_pages.ACT_STARTUP)   # rows that play or toggle: no chevron
        sv.children.append(row_item(f'pod_row{i}', i * ROW_H, r.label, chevron, ROW_H, sv_w))
    lv.children = [sv]
    if scroll:   # stock's scroll bar, only when there is something to scroll
        lv.children.append(Widget('scroll_bar_m', sv_w, 0, 10, list_h,
                                  [('name', 'scroll_bar_m'), ('max', '1000')]))
    return lv


def build_list_page(page):
    """A page whose rows the payload builds at runtime (patch/artists.c): the navbar over an
    empty stock list (with its scroll bar: the rows usually overflow), and a hidden message line
    for an empty library."""
    root = Widget('window', 0, 0, 0, 0, [('name', page.name)])
    styled(root, ('normal', 'disable', 'focused'), 'bg_color', '#000000')
    root.children.append(navbar(page.title))
    root.children.append(stock_list([], True))
    root.children.append(hidden(label('label_status', 10, 210, SCREEN_W - 20, 30, '', 20, '#FFFFFF')))
    return root


def build_page(page):
    if page.kind == 'cover':
        return build_cover_page(page)
    if page.kind == 'list':
        return build_list_page(page)
    root = Widget('window', 0, 0, 0, 0, [('name', page.name)])
    styled(root, ('normal', 'disable', 'focused'), 'bg_color', '#000000')
    root.children.append(navbar(page.title))
    root.children.append(stock_list(page.rows, len(page.rows) * ROW_H > CLIENT_H - NAVBAR_H))
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
