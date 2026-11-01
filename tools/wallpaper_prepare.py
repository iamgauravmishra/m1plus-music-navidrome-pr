#!/usr/bin/env python3
"""Draw the default lock screen wallpaper: a soft bokeh field (assets/bokeh-320x480.png).

  wallpaper_prepare.py OUT.png

Drawn, not sourced: a vertical gradient from teal (top) through light blue and periwinkle to deep blue
(GRADIENT stops), then soft discs of cyan, blue and lavender light (DISCS: centre and radius as
fractions of the screen, colour, opacity), each a filled circle whose edge is blurred by 15 % of its
radius, larger and fainter at the upper right, small and brighter lower down. The 320 x 480 RGB picture
is reduced to an 8-bit palette (256 colours, median cut, no dithering) and then compressed losslessly
by primage (github.com/imfing/primage: OxiPNG, level 6), which keeps the palette. The result is about
7 KB (the stock picture is 398 KB). AWTK's loader (stb_image) expands it like any other PNG. The build
only copies the committed file, pinned by SHA-256 in mod_wallpaper.py; primage is needed only here.
"""
import argparse, os, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFilter

W, H = 320, 480
COLOURS = 256
# (y as a fraction of the height, colour): indigo at the top, through aqua, to deep sea green
GRADIENT = [(0.0, (62, 78, 150)), (0.22, (92, 118, 186)), (0.48, (112, 166, 196)), (0.75, (78, 146, 160)),
            (1.0, (30, 78, 104))]
# ((cx, cy, r) as fractions of the width, height and width, colour, opacity): large faint discs behind
# the clock, small bright ones along the card's sides and in the strip under it
DISCS = [((0.18, 0.08, 0.26), (170, 160, 235), 0.22), ((0.62, 0.15, 0.16), (150, 190, 240), 0.20),
         ((0.92, 0.04, 0.09), (200, 200, 250), 0.40), ((0.03, 0.40, 0.07), (150, 230, 210), 0.45),
         ((0.97, 0.52, 0.10), (170, 160, 235), 0.35), ((0.05, 0.78, 0.12), (120, 210, 200), 0.30),
         ((0.60, 0.95, 0.07), (160, 235, 215), 0.50), ((0.88, 0.90, 0.13), (130, 180, 230), 0.30),
         ((0.32, 0.97, 0.05), (200, 240, 230), 0.45)]


def lerp(a, b, t): return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def draw():
    im = Image.new('RGB', (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / (H - 1)
        for (t0, c0), (t1, c1) in zip(GRADIENT, GRADIENT[1:]):
            if t0 <= t <= t1:
                d.line([(0, y), (W, y)], fill=lerp(c0, c1, (t - t0) / (t1 - t0)))
                break
    for (cx, cy, r), col, a in DISCS:
        rr = r * W
        mask = Image.new('L', (W, H), 0)
        ImageDraw.Draw(mask).ellipse([cx * W - rr, cy * H - rr, cx * W + rr, cy * H + rr], fill=round(255 * a))
        im = Image.composite(Image.new('RGB', (W, H), col), im, mask.filter(ImageFilter.GaussianBlur(rr * 0.15)))
    return im


def prepare(out):
    primage = shutil.which('primage')
    if not primage: sys.exit('primage not found (brew install --cask primage)')
    q = draw().quantize(colors=COLOURS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    with tempfile.TemporaryDirectory() as t:
        tmp = os.path.join(t, 'wallpaper.png')
        q.save(tmp, 'PNG', optimize=True)
        subprocess.run([primage, '--format', 'png', '--png-level', '6', '--overwrite', '-o', out, tmp], check=True)
    print(f'-> {out} ({os.path.getsize(out)} bytes, {W}x{H}, {COLOURS} colours)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('out')
    prepare(ap.parse_args().out)


if __name__ == '__main__': main()
