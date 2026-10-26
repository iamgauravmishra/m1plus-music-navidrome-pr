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
                             code, kept consistent) table_row h 60 -> 64, btn_table_row h 56 -> 60
  ui/playerjumpinfo_page.bin row_height 60 -> 64; template table_row 310x64, btn_table_row 310x60,
                             view_info w 238, scrlabel_name (0,7,238,24), view_artist at y 33 h 20,
                             scrlabel_artist w 213 (the jump list's rebind sizes view_info 238x60)
  ui/album_page.bin          album_listview default_item_height 60 -> 64
  ui/playlist_page.bin       playlist_listview default_item_height 60 -> 64 (its rows are created
                             0 high, so this is their pitch)

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


UI_EDITS = {
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
        assert names(old) == names(new), f'{rel}: a widget was added, removed or renamed'
        report.append(f'ui/{rel}: {len(old)} -> {len(new)} bytes')
    return report


# The album view (patch/albuminfo.c): the two styles its hook applies to the stock header. They are
# new names in the page theme only, so a header the hook leaves alone keeps stock's btn_imgplayall_style.
ALBUM_VIEW = 'albuminfo_page'
BUTTON_STYLE, META_STYLE = 'btn_albumbtn_style', 'srlabel_meta15_style'
BUTTON_BG, BUTTON_BORDER, BUTTON_PRESSED, BUTTON_PX = '#1E1E1E', '#3A3A3A', '#3A3A3A', 20
META_COLOR, META_PX = '#9C9C9C', 15


def album_view_styles(page, base):
    """btn_albumbtn_style: the dark Play all / Shuffle button (a dark fill with a hairline border,
    pressed lighter, 20 px white text, no icon); srlabel_meta15_style: the "year . N tracks" line, the
    stock grey line's alignment at 15 px #9C9C9C (4.5:1 on the pressed row the page audit tests)."""
    for state in ('normal', 'pressed', 'over', 'focused', 'disable'):
        s = awtk_style.Item('button', BUTTON_STYLE, state)
        s.set_color('bg_color', BUTTON_PRESSED if state == 'pressed' else BUTTON_BG)
        s.set_color('border_color', BUTTON_BORDER)
        s.set('border_width', 1, awtk_style.T_UINT32)
        s.set_color('text_color', '#FFFFFF')
        s.set('font_size', BUTTON_PX, awtk_style.T_UINT32)
        page.put(s)
    src = base.states('hscroll_label', 'srlabel_item_gray18_style')
    assert src, 'default.bin has no srlabel_item_gray18_style'
    for s in src:
        n = mod_lists.copy(s, META_STYLE)
        n.set('font_size', META_PX, awtk_style.T_UINT32)
        n.set_color('text_color', META_COLOR)
        page.put(n)


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
    for line in build_ui(a.out) + build_page_themes(a.out): print('rows:', line)


if __name__ == '__main__': main()
