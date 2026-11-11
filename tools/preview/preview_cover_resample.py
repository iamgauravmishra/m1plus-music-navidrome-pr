#!/usr/bin/env python3
"""Side-by-side of the cover resampling: stock's today against ours (docs/modules/coverflow.md "Cover resampling").

  uv run python -I tools/preview/preview_cover_resample.py [--image FILE | --m4a FILE | --card] [--out out/peek/cover-resample.png]

Left column, stock today: the decoded picture (stock decodes it at DCT scale 1/2, 1/4 or 1/8 over 1024 px, cc_stock_dims) resized to 168 by the four-tap bilinear of 0x5dc020 (corner
pixels mapped exactly, weights over (dw-1)(dh-1)), then the OLD cc_box (every touched source pixel at full weight) to 144 px. Right column, new: the same DCT scaling, then the exact area
average (patch/covercache.c ar_push, compiled for the host with -DCF_HOST) to 168, then the new cc_box to 144. Each row shows the 168 px cover, the 144 px tile and a 3x nearest zoom of the
detail crop of each. --image: any picture; --m4a: the embedded art of an m4a (the covr atom); --card (default without the others): a generated test card (zone plate, fine text, ruling).
The picture used is never written next to the output unless it is the generated card.
"""
import argparse, ctypes, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
CC = os.path.join(ROOT, 'patch', 'covercache.c')
AR_EMIT = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.POINTER(ctypes.c_ubyte))
SIZE, TILE = 168, 144


def host_lib(tmp):
    so = os.path.join(tmp, 'cc.so')
    subprocess.run(['cc', '-O2', '-std=c99', '-Wall', '-DCF_HOST', '-shared', '-fPIC', '-I', os.path.join(ROOT, 'patch'), CC, '-o', so], check=True)
    lib = ctypes.CDLL(so)
    lib.ar_init.argtypes = [ctypes.c_void_p] + [ctypes.c_uint] * 4
    lib.ar_push.argtypes = [ctypes.c_void_p, ctypes.c_char_p] + [ctypes.c_uint] * 5 + [AR_EMIT, ctypes.c_void_p]
    lib.cc_box.argtypes = [ctypes.c_char_p] + [ctypes.c_uint] * 3 + [ctypes.c_char_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_uint)]
    lib.cc_stock_dims.argtypes = [ctypes.c_uint] * 3 + [ctypes.POINTER(ctypes.c_uint)] * 2
    lib.cc_stock_fit.argtypes = [ctypes.c_uint] * 3 + [ctypes.POINTER(ctypes.c_uint)] * 2
    return lib


def dct_scale(im, lib):
    """What stock's loader hands the resize: the picture whole up to 1024 x 1024, else libjpeg's 1/d scaling (a box reduce here: the same size, sides rounded up)."""
    w, h = ctypes.c_uint(), ctypes.c_uint()
    lib.cc_stock_dims(im.width, im.height, 3, ctypes.byref(w), ctypes.byref(h))
    d = im.width // w.value if w.value else 1
    d = max(1, round(im.width / w.value))
    return im if d == 1 else im.reduce(d)


def fit(lib, im):
    tw, th = ctypes.c_uint(), ctypes.c_uint()
    return (tw.value, th.value) if lib.cc_stock_fit(im.width, im.height, SIZE, ctypes.byref(tw), ctypes.byref(th)) else im.size


def bilinear(im, dw, dh):
    """0x5dc020: dest pixel (x, y) reads source x * (sw - 1) / (dw - 1), y * (sh - 1) / (dh - 1), four taps, weights over (dw - 1)(dh - 1), rounded."""
    sw, sh = im.size
    src = im.convert('RGB').load()
    out = Image.new('RGB', (dw, dh))
    px = out.load()
    nx, ny = max(dw - 1, 1), max(dh - 1, 1)
    for y in range(dh):
        num = y * (sh - 1)
        y0, fy = num // ny, num % ny
        y1 = min(y0 + 1, sh - 1)
        for x in range(dw):
            numx = x * (sw - 1)
            x0, fx = numx // nx, numx % nx
            x1 = min(x0 + 1, sw - 1)
            wy1, wy0, wx1, wx0 = fy, ny - fy, fx, nx - fx
            tot = nx * ny
            px[x, y] = tuple((src[x0, y0][k] * wx0 * wy0 + src[x1, y0][k] * wx1 * wy0 + src[x0, y1][k] * wx0 * wy1 + src[x1, y1][k] * wx1 * wy1 + tot // 2) // tot for k in range(3))
    return out


def old_box(im, size):
    """The cc_box before: the centred square, every source pixel the box touches (floor of its start to ceil of its end) at full weight."""
    w, h = im.size
    side = min(w, h)
    ox, oy = (w - side) // 2, (h - side) // 2
    src = im.convert('RGB').load()
    out = Image.new('RGB', (size, size))
    px = out.load()
    for y in range(size):
        y0, y1 = y * side // size, min(side, ((y + 1) * side + size - 1) // size)
        y1 = max(y1, y0 + 1)
        for x in range(size):
            x0, x1 = x * side // size, min(side, ((x + 1) * side + size - 1) // size)
            x1 = max(x1, x0 + 1)
            n = (x1 - x0) * (y1 - y0)
            acc = [0, 0, 0]
            for j in range(y0, y1):
                for i in range(x0, x1):
                    p = src[ox + i, oy + j]
                    for k in range(3): acc[k] += p[k]
            px[x, y] = tuple(v // n for v in acc)
    return out


def area(lib, im, tw, th):
    """patch/covercache.c ar_push over the picture's rows (the cover extraction's average)."""
    buf = ctypes.create_string_buffer(20000)
    assert lib.ar_init(buf, im.width, im.height, tw, th)
    rows = []
    cb = AR_EMIT(lambda _, p: rows.append(bytes(p[:tw * 3])))
    raw = im.convert('RGB').tobytes()
    for j in range(im.height): lib.ar_push(buf, raw[j * im.width * 3:(j + 1) * im.width * 3], 3, 0, 1, 2, 3, cb, None)
    return Image.frombytes('RGB', (tw, th), b''.join(rows))


def new_box(lib, im, size):
    rgba = im.convert('RGBA')
    out = (ctypes.c_uint * (size * size))()
    lib.cc_box(rgba.tobytes(), im.width, im.height, im.width * 4, bytes((0, 1, 2, 3)), size, out)
    res = Image.new('RGB', (size, size))
    res.putdata([(v & 255, v >> 8 & 255, v >> 16 & 255) for v in out])
    return res


def card(n=1600):
    """A generated test card: a zone plate (frequency rising with radius), fine text at several sizes, a line ruling and a chequer."""
    import math
    im = Image.new('RGB', (n, n), (235, 235, 235))
    px = im.load()
    c, r = n * 0.3, n * 0.27
    for y in range(int(n * 0.03), int(n * 0.57)):
        for x in range(int(n * 0.03), int(n * 0.57)):
            d2 = (x - c) ** 2 + (y - c) ** 2
            if d2 < r * r:
                v = int(127.5 + 127.5 * math.cos(d2 * math.pi / (n * 0.9)))
                px[x, y] = (v, v, v)
    dr = ImageDraw.Draw(im)
    for i, sz in enumerate((46, 34, 26, 20, 16, 13, 11)):
        try: f = ImageFont.load_default(size=sz)
        except TypeError: f = ImageFont.load_default()
        dr.text((int(n * 0.62), int(n * 0.03) + i * int(n * 0.08)), 'Fine print 0123456789', fill=(20, 20, 20), font=f)
    for i in range(60):
        x = int(n * 0.03) + i * 7
        dr.line([(x, int(n * 0.62)), (x, int(n * 0.78))], fill=(0, 0, 0), width=1 + (i // 20))
    for j in range(0, int(n * 0.2), 4):
        for i in range(0, int(n * 0.3), 4):
            if (i // 4 + j // 4) % 2: dr.rectangle([int(n * 0.62) + i, int(n * 0.62) + j, int(n * 0.62) + i + 3, int(n * 0.62) + j + 3], fill=(0, 0, 0))
    dr.rectangle([int(n * 0.03), int(n * 0.82), n - int(n * 0.03), n - int(n * 0.03)], fill=(200, 40, 40))
    for k in range(40):
        dr.line([(int(n * 0.05) + k * 37, int(n * 0.83)), (int(n * 0.05) + k * 37 + 60, n - int(n * 0.04))], fill=(255, 255, 255), width=1)
    return im


def m4a_art(path):
    data = open(path, 'rb').read()
    at = data.find(b'covr')
    d = data.find(b'data', at)
    if at < 0 or d < 0: sys.exit('no cover atom in ' + path)
    size = int.from_bytes(data[d - 4:d], 'big')   # the data atom: size, 'data', type (4), locale (4), the picture
    import io
    return Image.open(io.BytesIO(data[d + 12:d - 4 + size])).convert('RGB')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--image'); ap.add_argument('--m4a'); ap.add_argument('--card', action='store_true')
    ap.add_argument('--out', default=os.path.join(ROOT, 'out', 'peek', 'cover-resample.png'))
    ap.add_argument('--crop', default='', help='x,y,size of the detail crop of the 168 px cover (default: where the picture is busiest)')
    a = ap.parse_args()
    im = Image.open(a.image).convert('RGB') if a.image else m4a_art(a.m4a) if a.m4a else card()
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        lib = host_lib(tmp)
        dec = dct_scale(im, lib)
        tw, th = fit(lib, dec)
        old168 = bilinear(dec, tw, th)
        new168 = area(lib, dec, tw, th)
        old144, new144 = old_box(old168, TILE), new_box(lib, new168, TILE)
    print(f'source {im.size}, decoded by stock at {dec.size}, cover {tw} x {th}, tile {TILE}')
    if a.crop: cx, cy, cs = (int(v) for v in a.crop.split(','))
    else:
        cs = 48
        best = (-1, 0, 0)
        g = new168.convert('L').load()
        for y in range(0, th - cs + 1, 8):
            for x in range(0, tw - cs + 1, 8):
                v = sum(abs(g[x + i, y + j] - g[x + i + 1, y + j]) for j in range(0, cs, 2) for i in range(0, cs - 1, 2))
                if v > best[0]: best = (v, x, y)
        cx, cy = best[1], best[2]
    z = 3
    lab = ImageFont.load_default(size=13) if hasattr(ImageFont, 'load_default') else None
    pad, head = 10, 34
    colw = TILE * 0 + SIZE + pad + TILE + pad + cs * z
    W, H = pad + 2 * colw + 3 * pad, head + 20 + max(SIZE, cs * z) + pad
    sheet = Image.new('RGB', (W, H), (28, 28, 28))
    dr = ImageDraw.Draw(sheet)
    for col, (title, c168, c144) in enumerate((('(a) stock today: bilinear corners to 168, old cc_box to 144', old168, old144), ('(b) new: DCT scale + exact area average to 168, new cc_box to 144', new168, new144))):
        x0 = pad + col * (colw + 3 * pad)
        dr.text((x0, 8), title, fill=(235, 235, 235), font=lab)
        for j, (name, img, x) in enumerate((('168 cover', c168, x0), ('144 tile', c144, x0 + SIZE + pad), (f'detail of the cover, 3x nearest ({cx},{cy},{cs})', c168.crop((cx, cy, cx + cs, cy + cs)).resize((cs * z, cs * z), Image.NEAREST), x0 + SIZE + pad + TILE + pad))):
            sheet.paste(img, (x, head + 20))
            if j < 2: dr.text((x, head + 4), name, fill=(170, 170, 170), font=lab)
    sheet.save(a.out)
    print(a.out)


if __name__ == '__main__': main()
