#!/usr/bin/env python3
"""Look at and measure images (PNG / JPG / BMP: previews, device screenshots) without inline scripts.
Every command that makes an image writes it to out/peek/ and prints the absolute path (open it with
the Read tool). Zoom is nearest-neighbour, so pixels stay pixels.

  peek.py info IMG...                         size and mode
  peek.py crop IMG X Y W H [--zoom N]         a region, optionally enlarged
  peek.py zoom IMG N                          the whole image times N
  peek.py side A B [C...] [--zoom N] [--gap PX]   images next to each other (heights padded)
  peek.py diff A B [--amp N]                  per-pixel difference (amplified, default 4x); prints the
                                              number of differing pixels and their bounding box
  peek.py bbox IMG [--bg #RRGGBB] [--tol N] [--box X Y W H]
                                              bounding box "x y w h" of the pixels that are not the
                                              background (default: transparent pixels if the file has an
                                              alpha channel, else the colour of the top-left pixel)
  peek.py runs IMG --axis x|y [--bg #RRGGBB] [--tol N] [--box X Y W H]
                                              spans "from..to (length)" of non-background pixels along an
                                              axis (column or row occupancy: finds gaps, row heights, text lines)
  peek.py px IMG X Y [W H]                    pixel values (RGB hex), W x H at most 16 x 16
"""
import argparse, os, sys
from PIL import Image, ImageChops

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

def load(p):
    """RGB; transparency is composited over black (the UI's background)."""
    im = Image.open(p)
    if im.mode in ('RGBA', 'LA', 'P') and (im.mode != 'P' or 'transparency' in im.info):
        im = im.convert('RGBA'); base = Image.new('RGBA', im.size, (0, 0, 0, 255)); base.alpha_composite(im); im = base
    return im.convert('RGB')

def alpha_of(p):
    """The alpha channel as 'L' if the file has one, else None."""
    im = Image.open(p)
    return im.convert('RGBA').getchannel('A') if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info) else None

def out_path(name):
    d = os.path.join(paths.OUT, 'peek'); os.makedirs(d, exist_ok=True)
    return os.path.join(d, name)

def save(im, name):
    p = out_path(name); im.save(p); print(os.path.abspath(p)); return p

def stem(p): return os.path.splitext(os.path.basename(p))[0]

def zoomed(im, n): return im.resize((im.width * n, im.height * n), Image.NEAREST) if n > 1 else im

def colour(s):
    s = s.lstrip('#'); return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))

def mask(path, bg, tol, box):
    """The non-background pixels (255) inside box as an 'L' image, and the box origin. Background: --bg,
    else transparency when the file has an alpha channel, else the colour of the top-left pixel."""
    im = load(path); x, y, w, h = box or (0, 0, im.width, im.height)
    al = alpha_of(path) if not bg else None
    if al is not None: return al.crop((x, y, x + w, y + h)).point(lambda v: 255 if v > tol else 0), (x, y)
    im = im.crop((x, y, x + w, y + h))
    solid = Image.new('RGB', im.size, colour(bg) if bg else im.getpixel((0, 0)))
    return ImageChops.difference(im, solid).convert('L').point(lambda v: 255 if v > tol else 0), (x, y)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['info', 'crop', 'zoom', 'side', 'diff', 'bbox', 'runs', 'px'])
    ap.add_argument('args', nargs='+')
    ap.add_argument('--zoom', type=int, default=1); ap.add_argument('--gap', type=int, default=8)
    ap.add_argument('--amp', type=int, default=4); ap.add_argument('--bg'); ap.add_argument('--tol', type=int, default=0)
    ap.add_argument('--box', type=int, nargs=4, metavar=('X', 'Y', 'W', 'H')); ap.add_argument('--axis', choices=['x', 'y'])
    a = ap.parse_args(); A = a.args
    if a.cmd == 'info':
        for p in A: im = Image.open(p); print(f'{os.path.abspath(p)}: {im.width}x{im.height} {im.mode}')
    elif a.cmd == 'crop':
        x, y, w, h = map(int, A[1:5])
        save(zoomed(load(A[0]).crop((x, y, x + w, y + h)), a.zoom), f'{stem(A[0])}-crop-{x}-{y}-{w}x{h}-z{a.zoom}.png')
    elif a.cmd == 'zoom':
        n = int(A[1]); save(zoomed(load(A[0]), n), f'{stem(A[0])}-z{n}.png')
    elif a.cmd == 'side':
        ims = [zoomed(load(p), a.zoom) for p in A]
        W = sum(i.width for i in ims) + a.gap * (len(ims) - 1); H = max(i.height for i in ims)
        sheet = Image.new('RGB', (W, H), (255, 0, 255)); x = 0
        for i in ims: sheet.paste(i, (x, 0)); x += i.width + a.gap
        save(sheet, 'side-' + '-'.join(stem(p) for p in A)[:100] + f'-z{a.zoom}.png')
    elif a.cmd == 'diff':
        x, y = load(A[0]), load(A[1])
        if x.size != y.size: sys.exit(f'sizes differ: {x.size} vs {y.size}')
        d = ImageChops.difference(x, y); box = d.getbbox()
        n = sum(d.convert('L').histogram()[1:])
        print(f'{n} differing pixels' + (f', bounding box x={box[0]} y={box[1]} w={box[2] - box[0]} h={box[3] - box[1]}' if box else ''))
        save(d.point(lambda v: min(255, v * a.amp)), f'diff-{stem(A[0])}-{stem(A[1])}.png')
        sys.exit(1 if n else 0)
    elif a.cmd in ('bbox', 'runs'):
        m, (ox, oy) = mask(A[0], a.bg, a.tol, a.box)
        if a.cmd == 'bbox':
            b = m.getbbox()
            print('empty' if not b else f'{b[0] + ox} {b[1] + oy} {b[2] - b[0]} {b[3] - b[1]}')
        else:
            if not a.axis: ap.error('runs needs --axis x|y')
            w, h = m.size; px = m.load()
            occ = [any(px[i, j] for j in range(h)) for i in range(w)] if a.axis == 'x' else [any(px[i, j] for i in range(w)) for j in range(h)]
            off = ox if a.axis == 'x' else oy; i = 0
            while i < len(occ):
                if occ[i]:
                    j = i
                    while j + 1 < len(occ) and occ[j + 1]: j += 1
                    print(f'{i + off}..{j + off} ({j - i + 1})'); i = j + 1
                else: i += 1
    elif a.cmd == 'px':
        im = load(A[0]); x, y = int(A[1]), int(A[2]); w = min(int(A[3]), 16) if len(A) > 3 else 1; h = min(int(A[4]), 16) if len(A) > 4 else 1
        for j in range(y, y + h): print(f'{j:4}: ' + ' '.join('%02x%02x%02x' % im.getpixel((i, j)) for i in range(x, x + w)))

if __name__ == '__main__': main()
