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

Usage: pod_ui.py WORKDIR --stage A|B|C   (writes ui/*.bin into WORKDIR/rootfs; prints the files)
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


def build_cover_page(page):
    """Cover Flow's page: the covers frame, the album and artist captions under it, a hint, and
    the first-run cache build's progress label and Cancel button. patch/coverflow.c fills
    view_covers with a stock slide_menu and view_tracks with the album's track list; the geometry
    here must match the CF_* constants in patch/offsets.inc."""
    root = Widget('window', 0, 0, 0, 0, [('name', page.name)])
    styled(root, ('normal', 'disable', 'focused'), 'bg_color', '#000000')
    root.children.append(navbar(page.title))
    frame = Widget('view', 0, NAVBAR_H + 6, SCREEN_W, 230, [('name', 'view_covers')])
    styled(frame, ('normal',), 'bg_color', '#000000')
    root.children.append(frame)
    root.children.append(label('label_album', 10, 300, SCREEN_W - 20, 32, '', 22, '#FFFFFF'))
    root.children.append(label('label_artist', 10, 334, SCREEN_W - 20, 26, '', 18, '#AAAAAA'))
    root.children.append(label('label_hint', 10, 392, SCREEN_W - 20, 24,
                               'Tap the centre cover to open the album', 15, '#888888'))
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
    tracks = Widget('view', 0, NAVBAR_H, SCREEN_W, CLIENT_H - NAVBAR_H, [('name', 'view_tracks')])
    styled(tracks, ('normal',), 'bg_color', '#000000')
    root.children.append(hidden(tracks))
    return root


def build_page(page):
    if page.kind == 'cover':
        return build_cover_page(page)
    root = Widget('window', 0, 0, 0, 0, [('name', page.name)])
    styled(root, ('normal', 'disable', 'focused'), 'bg_color', '#000000')
    root.children.append(navbar(page.title))
    if page.info is not None:
        lab = Widget('label', 20, NAVBAR_H + 40, SCREEN_W - 40, 140, [
            ('name', 'label_info'), ('text', page.info), ('line_wrap', 'true')])
        styled(lab, ('normal',), 'text_color', '#FFFFFF')
        styled(lab, ('normal',), 'font_size', '24')
        styled(lab, ('normal',), 'text_align_h', 'center')
        styled(lab, ('normal',), 'text_align_v', 'top')
        root.children.append(lab)
    rows = len(page.rows)
    if not rows: return root
    # The structure and properties of systemset/sysset_page.bin's list, the stock scrolling list:
    # list_view (default_item_height, black in every state) > scroll_view (310 wide, the speed
    # scales) + scroll_bar_m (10 px, max 1000) at the right.
    list_h = CLIENT_H - NAVBAR_H
    h = ROW_H
    scroll = rows * h > list_h
    sv_w = SCREEN_W - 10 if scroll else SCREEN_W
    lv = Widget('list_view', 0, NAVBAR_H, SCREEN_W, list_h, [
        ('name', 'pod_listview'), ('default_item_height', str(h))])
    for st in ('normal', 'disable', 'focused'):
        lv.set(f'style:{st}:bg_color', '#000000')
    for st in ('normal', 'disable', 'focused'):
        lv.set(f'style:{st}:border_color', '#00000000')
    lv.set('style:normal:border_width', '0')
    sv = Widget('scroll_view', 0, 0, sv_w, list_h, [
        ('name', 'pod_scrollview'), ('yspeed_scale', '1'), ('xspeed_scale', '1')])
    for i, r in enumerate(page.rows):
        chevron = r.action != pod_pages.ACT_PLAYER
        sv.children.append(row_item(f'pod_row{i}', i * h, r.label, chevron, h, sv_w))
    lv.children = [sv]
    if scroll:   # stock's scroll bar, only when there is something to scroll
        lv.children.append(Widget('scroll_bar_m', sv_w, 0, 10, list_h,
                                  [('name', 'scroll_bar_m'), ('max', '1000')]))
    root.children.append(lv)
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
    ap.add_argument('workdir'); ap.add_argument('--stage', required=True, choices=sorted(pod_pages.STAGES))
    a = ap.parse_args()
    pages = pod_pages.STAGES[a.stage]
    rootfs = os.path.join(a.workdir, 'rootfs') if os.path.isdir(os.path.join(a.workdir, 'rootfs')) else a.workdir
    for rel, n in write_assets(rootfs, pages):
        print(f'wrote {rel} ({n} bytes)')


if __name__ == '__main__': main()
