#!/usr/bin/env python3
"""out/preview/locale-<table>.png: the M1+ Music menu (as Home), Extras, Customize, Shuffle and Main Menu pages in other
languages, drawn from a finished tree's own ui files, strings tables and font (docs/ui.md "Localisation").
Approximate (PIL, not AWTK): labels that do not fit are cut with an ellipsis, as an idle hscroll_label shows them.

Usage: venv/bin/python -I tools/preview_locales.py WORKDIR [TABLE ...]     (default: zh_CN ja_JP ge_DE ru_RU; TABLE is a
strings table name such as ru_RU; output in out/preview/, gitignored)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw
import build, preview, preview_icons as PI
import pod_pages as P

DEFAULT = ['zh_CN', 'ja_JP', 'ge_DE', 'ru_RU']


def sheet(work, table):
    s = PI.Side(work, True, table); s.mark = lambda *a: None
    panels = [('M1+ Music menu (Home)', preview.menu_page(s, None, home=True)),
              ('Extras', preview.extras_page(s, None)),
              ('Customize', PI.pod_page(s, 'm1plus_customize', 8).convert('RGB')),
              ('Customize > Home Screen', PI.pod_page(s, 'm1plus_homeset', 2, switches={'pod_switch0': True}).convert('RGB')),
              ('Customize > Cover Flow', PI.pod_page(s, 'm1plus_cfset', 2, switches={'pod_switch0': False}).convert('RGB')),
              ('Shuffle', PI.pod_page(s, 'm1plus_shuffle', 3).convert('RGB')),
              ('Main Menu', preview.mainmenu_page(s, None))]
    pad, lab = 12, 20
    wid = sum(im.width for _, im in panels) + pad * (len(panels) + 1)
    hei = max(im.height for _, im in panels) + 44 + pad
    out = Image.new('RGB', (wid, hei), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(out)
    d.text((pad, 4), f'{build.TAG} in {table} (1:1 device pixels; approximate, labels cut with an ellipsis where they do not fit)', fill=(255, 255, 255), font=PI.ANN)
    x = pad
    for title, im in panels:
        d.text((x, 24), title, fill=(0xAA,) * 3, font=PI.ANN); out.paste(im, (x, 44)); x += im.width + pad
    return out


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    work, tables = sys.argv[1], sys.argv[2:] or DEFAULT
    os.makedirs(os.path.join(build.ROOT, 'out', 'preview'), exist_ok=True)
    for t in tables:
        out = os.path.join(build.ROOT, 'out', 'preview', f'locale-{t}.png')
        im = sheet(work, t); PI.save_compact(im, out); print('wrote', out, im.size)


if __name__ == '__main__': main()
