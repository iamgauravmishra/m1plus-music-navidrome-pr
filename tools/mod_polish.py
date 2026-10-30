#!/usr/bin/env python3
"""UI polish, asset-only (V2.1jA `polish`, docs/ui.md): the geometry fixes that are not images.

M1+ Music page titles: the pod pages (m1plus_menu / shuffle / settings / artists / cover) were built with a 248 px wide
`label_title` at x 36, which runs under the "back to player" button (x 260..320, bars icon at 278). Stock
titles are 200 px wide at the same x 36, y 14, h 22 (44 of 53 stock pages), so a long title (an artist
name on the Artists Cover Flow) is cut at the same place as everywhere else and never touches the icon.
x, y, height, style and alignment stay as stock; the title is left-aligned at x 36 on both instances of
the menu (Home with Back hidden, and the Tidal one).

Navbar titles: the theme styles `navbar_label_white` and `navbar_centerlabel_white` (every page's
`label_title`, stock and ours) go from 22 to 20 px, in all states and both themes; `navbar_leftlabel_white` /
`navbar_rightlabel_white` are already 20. Box, alignment (y 14, h 22, middle) and the Now Playing icon are
untouched, so the smaller text stays vertically centred.

Usage: mod_polish.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import os, stat, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_style
from modlib import clone_workdir, edit_ui

UI = 'rootfs/release/assets/default/raw/ui'
PAGES = ('m1plus_menu', 'm1plus_shuffle', 'm1plus_customize', 'm1plus_extras', 'm1plus_artists', 'm1plus_cover', 'm1plus_cfset', 'm1plus_homeset', 'm1plus_extrascfg', 'm1plus_developer')
TITLE_W = 200                     # the stock navbar title width
IMG_MTIME = 1750924035            # as the other added ui files (mod_icons.py)


def edit(root):
    t = root.find('label_title')
    assert t is not None and (t.x, t.y, t.h) == (58, 14, 22), 'unexpected title geometry (tools/pod_ui.py NAV_TITLE_X: 8 px after the glass Back disc)'
    assert t.w <= 248, f'unexpected title width {t.w}'
    t.w = min(t.w, TITLE_W)   # a page with a navbar toggle (Cover Flow) already ends its title at the toggle's left edge


STYLE_RAW = 'rootfs/release/assets/{theme}/raw/styles/default.bin'
TITLE_STYLES = ('navbar_label_white', 'navbar_centerlabel_white')
TITLE_OLD, TITLE_NEW = 22, 20


def title_styles(out):
    n = 0
    for theme in ('default', 'theme1'):
        p = os.path.join(out, STYLE_RAW.format(theme=theme))
        old = open(p, 'rb').read(); th = awtk_style.parse(old)
        assert awtk_style.serialize(th) == old, f'{p}: style round trip is not byte-exact'
        for it in th.items:
            if it.widget == 'label' and it.style in TITLE_STYLES:
                assert it.get('font_size') == TITLE_OLD, (it, it.get('font_size'))
                it.set('font_size', TITLE_NEW, awtk_style.T_INT32); n += 1
        mode = stat.S_IMODE(os.stat(p).st_mode)
        os.chmod(p, mode | 0o200); open(p, 'wb').write(awtk_style.serialize(th)); os.chmod(p, mode)
    assert n == 12, n
    print(f'polish: navbar title styles {TITLE_OLD} -> {TITLE_NEW} px ({n} style states, both themes)')


def apply(out):
    title_styles(out)
    n = 0
    for k in PAGES:
        p = os.path.join(out, UI, k + '.bin')
        if os.path.exists(p):
            edit_ui(p, edit); os.utime(p, (IMG_MTIME, IMG_MTIME)); n += 1
    print(f'polish: label_title {TITLE_W} px wide on {n} M1+ Music pages')


if __name__ == '__main__':
    clone_workdir(sys.argv[1], sys.argv[2]); apply(sys.argv[2])
