#!/usr/bin/env python3
"""Prepare the default lock screen wallpaper: Vincent van Gogh, The Starry Night (1889), public domain.

  wallpaper_prepare.py --fetch DIR          download the pinned scan into DIR (a new, empty directory)
  wallpaper_prepare.py SCAN.jpg OUT.png     portrait crop, tone, palette PNG (assets/starry-night-320x480.png)

Source: the Google Art Project scan on Wikimedia Commons,
  https://commons.wikimedia.org/wiki/File:Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg
fetched as its 1920 px thumbnail (Commons only serves a fixed list of thumbnail widths). The
painting is in the public domain (the artist died in 1890; a faithful photograph of a flat
public-domain work adds no new copyright, Commons PD-Art). The download is untrusted data: it is
checked against SHA_256 before anything opens it, and only Pillow decodes it. Run with `python -I`
and keep DIR out of the repo.

The picture, 1920 x 1520, is cropped to the 2:3 portrait of the 320 x 480 screen: the full height
and the 1013 px starting at x = 250, which holds the cypress (x 285-870) and the large swirl
(x 690-1230), resampled with Lanczos. The tone is 20 % darker (brightness 0.8) so the translucent
player card and the white clock (docs/ui.md) read well on its brightest parts, the moon
and stars. The result is an 8-bit palette PNG (256 colours, median cut), about 134 KB: AWTK's loader
(stb_image) expands it like any other PNG, and the rootfs headroom is untouched.
"""
import argparse, hashlib, os, sys, urllib.request
from PIL import Image, ImageEnhance

URL = ('https://upload.wikimedia.org/wikipedia/commons/thumb/e/ea/'
       'Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg/1920px-Van_Gogh_-_Starry_Night_-_Google_Art_Project.jpg')
SHA_256 = 'dbca2f16b195f6e83feb98d44c0d98eb0b39f560314efbedfedab9e45caa8a2f'
SIZE = (1920, 1520)
CROP_X = 250
BRIGHTNESS = 0.8
COLOURS = 256
OUT_SIZE = (320, 480)


def sha256(path):
    with open(path, 'rb') as f: return hashlib.sha256(f.read()).hexdigest()


def fetch(directory):
    os.makedirs(directory, exist_ok=True)
    if os.listdir(directory): sys.exit(f'{directory} is not empty: use a new, empty directory for the download')
    path = os.path.join(directory, 'starry-night-1920.jpg')
    req = urllib.request.Request(URL, headers={'User-Agent': 'm1plus-mod/1.0 (wallpaper fetch)'})
    with urllib.request.urlopen(req, timeout=120) as r, open(path, 'wb') as f: f.write(r.read())
    if sha256(path) != SHA_256:
        os.remove(path); sys.exit('download SHA-256 mismatch: not the pinned scan')
    print('->', path, SHA_256)


def prepare(src, out):
    if sha256(src) != SHA_256: sys.exit(f'{src}: SHA-256 is not the pinned scan ({SHA_256})')
    im = Image.open(src)
    if im.size != SIZE: sys.exit(f'unexpected size {im.size}')
    h = im.height; w = h * OUT_SIZE[0] // OUT_SIZE[1]
    im = im.convert('RGB').crop((CROP_X, 0, CROP_X + w, h)).resize(OUT_SIZE, Image.LANCZOS)
    im = ImageEnhance.Brightness(im).enhance(BRIGHTNESS)
    q = im.quantize(colors=COLOURS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    q.save(out, 'PNG', optimize=True)
    print(f'-> {out} ({os.path.getsize(out)} bytes, {OUT_SIZE[0]}x{OUT_SIZE[1]}, {COLOURS} colours)')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--fetch', metavar='DIR'); ap.add_argument('args', nargs='*')
    a = ap.parse_args()
    if a.fetch: fetch(a.fetch)
    elif len(a.args) == 2: prepare(*a.args)
    else: ap.error('give --fetch DIR, or SCAN.jpg OUT.png')


if __name__ == '__main__': main()
