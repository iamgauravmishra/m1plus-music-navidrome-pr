#!/usr/bin/env python3
"""PIL mock-up of the M1 Pod Artists list and Cover Flow scoped to one artist (V2.1fR), from a built
tree (approximate, not AWTK; sample data):

  Artists          ui/m1pod_artists.bin with the rows patch/artists.c builds (list_item_style,
                   srlabel_leftwhite21_style, right_arrow), drawn by preview_all's menu painter
                   over the tree's theme
  an artist        the real depth renderer (test/coverflow.py's host build of patch/coverflow.c)
                   on the artist's shelf at its first album: nothing to the left (the shelf has
                   ends), titled with the artist
  All albums       the same shelf on its last card, the stock All songs row (placeholder art)

Usage: venv/bin/python -I tools/preview_artists.py WORKDIR OUT.png
"""
import argparse, os, sys, tempfile
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
from awtk_ui import Widget
import preview_all, pod_ui
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'test'))
import coverflow as hostcf  # noqa: E402

ARTISTS = ['ABBA', 'Bill Evans', 'Björk', 'Chet Baker', 'Daft Punk', 'Ella Fitzgerald', 'John Coltrane',
           'Miles Davis', 'Nina Simone', 'Unknown Artist']
ROW_H, TEXT_X, CHEVRON_W = 52, 24, 44   # patch/artists.c


def artists_page(work):
    """The asset with the rows artists.c adds to pod_scrollview (its geometry and styles)."""
    raw = os.path.join(work, preview_all.RAW)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1pod_artists.bin'), 'rb').read())
    sv = next(w for w in root.walk() if w.name == 'pod_scrollview')
    for i, name in enumerate(ARTISTS):
        row = Widget('list_item', 0, i * ROW_H, sv.w, ROW_H, [('style', 'list_item_style')])
        row.children = [Widget('hscroll_label', TEXT_X, 0, sv.w - TEXT_X - CHEVRON_W, ROW_H,
                               [('style', 'srlabel_leftwhite21_style'), ('text', name)]),
                        Widget('image', sv.w - CHEVRON_W, 0, CHEVRON_W - 4, ROW_H,
                               [('image', 'right_arrow'), ('draw_type', 'icon')])]
        sv.children.append(row)
    return preview_all.MenuPainter(raw).render(root, 0)


def shelf(work, lib, ring, album, artist, frac=0):
    """ui/m1pod_cover.bin as the scoped page leaves it (title, captions) with the rendered frame
    in view_covers; only the frame's rows above the captions are pasted (the rest is black)."""
    raw = os.path.join(work, preview_all.RAW)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1pod_cover.bin'), 'rb').read())
    for w in root.walk():   # renamed: the Now Playing painter has sample text for label_album
        text = {'label_title': 'Miles Davis', 'label_album': album, 'label_artist': artist}.get(w.name)
        if text is not None: w.set('text', text); w.set('name', w.name + '_preview')
    page = preview_all.MenuPainter(raw).render(root, 0)
    frame = hostcf.render(lib, frac, ring)
    covers = Image.new('RGB', (hostcf.W, hostcf.H))
    covers.putdata([(v & 255, v >> 8 & 255, v >> 16 & 255) for v in frame])
    top = 480 - pod_ui.CLIENT_H
    page.paste(covers.crop((0, 0, hostcf.W, pod_ui.ALBUM_Y - pod_ui.COVER_Y)).convert('RGBA'), (0, top + pod_ui.COVER_Y))
    return page


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work'); ap.add_argument('out')
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        lib = hostcf.build(tmp)
        kob, hits, brew = (hostcf.texture(c, mark=m) for c, m in
                           (((60, 160, 200), 1), ((230, 190, 70), 0), ((200, 120, 200), 0)))
        card = hostcf.placeholder()
        first = shelf(a.work, lib, [None] * 3 + [kob, hits, brew, card], 'Kind of Blue', 'Miles Davis', hostcf.ONE // 10)
        last = shelf(a.work, lib, [kob, hits, brew, card] + [None] * 3, 'All albums', 'Miles Davis')
        shots = [('Artists', artists_page(a.work)), ('an artist: first album', first), ('the All albums card', last)]
    W, H, pad, top = 320, 480, 12, 20
    out = Image.new('RGB', (len(shots) * (W + pad) + pad, H + top + 2 * pad + 16), (40, 40, 40))
    d = ImageDraw.Draw(out)
    for i, (cap, im) in enumerate(shots):
        x = pad + i * (W + pad)
        assert im.size == (W, H), (cap, im.size)
        out.paste(im.convert('RGB'), (x, pad + top)); d.text((x, pad + 4), f'V2.1fR: {cap}', fill=(230, 230, 230))
    d.text((pad, out.height - 18), 'approximate PIL mock-ups (not AWTK); the covers are the real renderer; sample data',
           fill=(160, 160, 160))
    out.quantize(colors=192).save(a.out, optimize=True); print('wrote', a.out)


if __name__ == '__main__': main()
