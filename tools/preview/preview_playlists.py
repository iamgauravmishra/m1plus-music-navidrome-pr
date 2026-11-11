#!/usr/bin/env python3
"""Approximate PIL mock-up of the Playlists page (patch/playlists.c, docs/modules/playlists.md): the grid of mosaics and the same page with the
list-plus button's and the "..." cards open; sample playlists with 4, 2, 3, 1, 0 and 7 albums (the first four are used). Not pixel-exact AWTK.

  preview_playlists.py WORKDIR OUT.png [--lang CODE]

WORKDIR is a built tree (work/mod-release). The page is ui/m1plus_playlists.bin drawn by preview_icons.playlists_grid (the Albums grid's cell
model, the mosaic composed as grid_mosaic does, under the large title "Playlists" as pl_title lays it out); the covers are stand-in gradients.
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import preview_icons as PI


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir'); ap.add_argument('out'); ap.add_argument('--lang', default='en_US')
    a = ap.parse_args()
    s = PI.Side(a.workdir, True, a.lang)
    panels = [('Playlists: grid, list-plus | "..." | Now Playing', PI.playlists_grid(s)), ('Actions card open (Delete Playlists pressed)', PI.playlists_grid(s, menu='actions', pressed=3)),
              ('"..." card open, grid (Name pressed)', PI.playlists_grid(s, menu='more', pressed=2)), ('"..." card open, list mode', PI.playlists_grid(s, menu='more', list_mode=True, pressed=-1)),
              ('List mode, Name Z–A', PI.playlists_grid(s, list_mode=True, row_pressed=-1, order='za')), ('Card with Name Z–A ticked', PI.playlists_grid(s, menu='more', pressed=-1, order='za')),
              ('Delete Playlists: select mode (grid), two marked', PI.playlists_grid(s, select={1, 3})),
              ('Select mode in list mode (the rows 30 px to the right), one marked', PI.playlists_grid(s, list_mode=True, row_pressed=-1, select={2}))]
    pad, lab = 12, 20
    sheet = Image.new('RGB', (len(panels) * (320 + pad) + pad, 450 + lab + 2 * pad), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sheet)
    for i, (title, im) in enumerate(panels):
        x = pad + i * (320 + pad)
        d.text((x, pad), title, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, pad + lab))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    PI.save_compact(sheet, a.out)
    print('wrote', a.out, sheet.size)


if __name__ == '__main__': main()
