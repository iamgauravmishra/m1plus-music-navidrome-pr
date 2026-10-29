#!/usr/bin/env python3
"""Render the M1+ boot splash: assets/boot-logo.svg -> assets/boot-logo.jpg + assets/boot-logo180.jpg.

The stock splash (images/xx/logo.jpg) is an upright 320x480 baseline JPEG, 4:4:4 YCbCr, and
logo180.jpg is the same picture turned 180 degrees (S11logo_display_shell shows it when the screen
is rotated, ROTATEMODE=1). display_logo draws it 1:1 without scaling, so the output matches exactly.
The SVG is rasterised by librsvg at 4x and box-filtered down to 320x480 (no ringing on the black),
both JPEGs are encoded from that one raster, then checked with mod_boot.jpeg_size.

  boot_logo.py                      regenerate the two JPEGs (needs rsvg-convert and Pillow)
  boot_logo.py --preview WORKDIR    also write a PNG: stock splash, new splash, and a text sample in
                                    the stock vs the quote-fixed default.ttf, to /tmp/boot-preview.png
                                    (WORKDIR = an unpacked stock tree, e.g. work/stock)

Run with the repo venv: venv/bin/python -I tools/boot_logo.py  (brew install librsvg for rsvg-convert).
The JPEGs are committed; the firmware build only copies them (tools/mod_boot.py).
"""
import argparse, io, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import mod_boot

ROOT = mod_boot.ROOT
SVG = os.path.join(ROOT, 'assets', 'boot-logo.svg')
OUT = os.path.join(ROOT, 'assets', 'boot-logo.jpg'), os.path.join(ROOT, 'assets', 'boot-logo180.jpg')
W, H = mod_boot.LOGO_SIZE
SS = 4

def render():
    png = subprocess.run(['rsvg-convert', '-w', str(W * SS), '-h', str(H * SS), SVG], check=True, capture_output=True).stdout
    im = Image.open(io.BytesIO(png)).convert('RGB')
    return im.resize((W, H), Image.BOX)

def encode(im):
    b = io.BytesIO()
    im.save(b, 'JPEG', quality=92, subsampling=0, optimize=True, progressive=False)
    return b.getvalue()

def preview(work, logo):
    stock = Image.open(os.path.join(work, mod_boot.IMAGES, 'logo.jpg')).convert('RGB')
    font = open(os.path.join(work, mod_boot.FONT), 'rb').read()
    fixed, _, _ = mod_boot.fix_quotes(font)
    sample = ['Paul’s Boutique', '“Heroes”', 'Don’t Stop Me Now']
    gap, panel_w = 16, 320
    canvas = Image.new('RGB', (3 * panel_w + 4 * gap, H + 2 * gap + 24), (40, 40, 40))
    d = ImageDraw.Draw(canvas)
    label = ImageFont.truetype(io.BytesIO(font), 15)
    for i, (im, cap) in enumerate(((stock, 'stock logo.jpg'), (logo, 'M1+ boot-logo.jpg'))):
        x = gap + i * (panel_w + gap); canvas.paste(im, (x, gap + 24)); d.text((x, gap), cap, font=label, fill=(220, 220, 220))
    x = gap + 2 * (panel_w + gap); y = gap + 24
    d.text((x, gap), 'track titles, 22 px', font=label, fill=(220, 220, 220))
    d.rectangle((x, y, x + panel_w - 1, y + H - 1), fill=(0, 0, 0))
    for name, data in (('stock default.ttf', font), ('quotes fixed', fixed)):
        f = ImageFont.truetype(io.BytesIO(data), 22)
        d.text((x + 12, y + 16), name, font=label, fill=(150, 150, 150)); y += 40
        for s in sample: d.text((x + 12, y), s, font=f, fill=(255, 255, 255)); y += 34
        y += 24
    out = '/tmp/boot-preview.png'
    canvas.quantize(128).save(out, optimize=True); print('->', out)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--preview', metavar='WORKDIR')
    a = ap.parse_args()
    im = render()
    for path, pic in zip(OUT, (im, im.transpose(Image.Transpose.ROTATE_180))):
        data = encode(pic)
        assert mod_boot.jpeg_size(data) == (W, H)
        open(path, 'wb').write(data)
        print(f'-> {os.path.relpath(path, ROOT)} ({len(data)} bytes, sha256 {mod_boot.sha256(data)[:16]})')
    if a.preview: preview(a.preview, Image.open(OUT[0]).convert('RGB'))

if __name__ == '__main__': main()
