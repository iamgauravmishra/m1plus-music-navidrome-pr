"""Podcast cover art from a PNG (patch/pcpng.c, patch/pccover.c pv_shrink_png; docs/modules/podcasts.md "Cover art"): the streaming PNG decoder (chunks, inflate with stored, fixed and dynamic blocks,
the five filters, every colour type and depth, transparency over white) feeding the area average and the libjpeg encoder, compared with PIL's resize of the same picture, and every kind of damaged
file (it must fail cleanly, with no output file and every libjpeg object destroyed). The compiled payload runs under Unicorn; libjpeg is the PIL mock of test/pod/pcnet.py."""
import importlib.util, io, os, random, struct, sys, zlib
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

HERE = os.path.dirname(os.path.abspath(__file__))


def sibling(name):
    mod = sys.modules.get(f'podtest_{name}')
    if mod is None:
        spec = importlib.util.spec_from_file_location(f'podtest_{name}', os.path.join(HERE, name + '.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f'podtest_{name}'] = mod
        spec.loader.exec_module(mod)
    return mod


PCN = sibling('pcnet')
DIR = '/mnt/mmc/Podcasts/S'
SRC, DST = f'{DIR}/.cover.src', f'{DIR}/.cover.tmp'
SIG = b'\x89PNG\r\n\x1a\n'
CH = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}


def chunk(t, data): return struct.pack('>I', len(data)) + t + data + struct.pack('>I', zlib.crc32(t + data))


def png(w, h, ctype, depth, raw, plte=None, trns=None, interlace=0, mode='dynamic', split=0, extra=()):
    """A PNG from raw scanlines (each already with its filter byte): zlib in the given mode (dynamic, fixed, stored), the data in IDAT chunks of `split` bytes (0: one)."""
    co = {'dynamic': zlib.compressobj(9), 'fixed': zlib.compressobj(9, zlib.DEFLATED, 15, 9, zlib.Z_FIXED), 'stored': zlib.compressobj(0)}[mode]
    z = co.compress(raw) + co.flush()
    out = SIG + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, depth, ctype, 0, 0, interlace))
    for t, d in extra: out += chunk(t, d)
    if plte: out += chunk(b'PLTE', plte)
    if trns: out += chunk(b'tRNS', trns)
    parts = [z] if not split else [z[i:i + split] for i in range(0, len(z), split)]
    for i, p in enumerate(parts):
        out += chunk(b'IDAT', p)
        if split and i == 0: out += chunk(b'IDAT', b'')   # an empty IDAT chunk between two others
    return out + chunk(b'IEND', b'')


def pack_row(vals, depth):
    if depth == 16: return b''.join(struct.pack('>H', v) for v in vals)
    if depth == 8: return bytes(vals)
    out, acc, n = bytearray(), 0, 0
    for v in vals:
        acc = acc << depth | v; n += depth
        if n == 8: out.append(acc); acc = n = 0
    if n: out.append(acc << (8 - n))
    return bytes(out)


def filt(row, prev, bpp, t):
    out = bytearray([t])
    for i, x in enumerate(row):
        a = row[i - bpp] if i >= bpp else 0
        b = prev[i]; c = prev[i - bpp] if i >= bpp else 0
        if t == 0: p = 0
        elif t == 1: p = a
        elif t == 2: p = b
        elif t == 3: p = (a + b) >> 1
        else:
            pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
            p = a if pa <= pb and pa <= pc else b if pb <= pc else c
        out.append((x - p) & 255)
    return bytes(out)


def s8(v, d): return v if d == 8 else v >> 8 if d == 16 else v * 255 // ((1 << d) - 1)


def over_white(r, g, b, a):
    if a == 255: return (r, g, b)
    return tuple((v * a + 255 * (255 - a) + 127) // 255 for v in (r, g, b))


def picture(w, h, ctype, depth, filters=(0,), key=None):
    """(raw scanlines, expected RGB image, plte, trns) of a smooth picture with an alpha ramp: what the decoder must produce, by the same formulas."""
    from PIL import Image
    M = (1 << depth) - 1
    ncol = 1 << min(depth, 4) if ctype == 3 else 0
    plte = bytes(v for i in range(ncol) for v in (i * 255 // max(1, ncol - 1), 255 - i * 255 // max(1, ncol - 1), 90)) if ctype == 3 else None
    trns = bytes(255 - i * 255 // max(1, ncol - 1) if i % 2 else 255 for i in range(ncol)) if ctype == 3 else None
    if key is not None: trns = struct.pack('>H', key) if ctype == 0 else struct.pack('>HHH', *key)
    exp = Image.new('RGB', (w, h)); px = exp.load()
    raw, prev = b'', bytes((w * CH[ctype] * depth + 7) // 8)
    bpp = max(1, CH[ctype] * depth // 8)
    for y in range(h):
        vals = []
        for x in range(w):
            r, g, b, a = x * M // max(1, w - 1), y * M // max(1, h - 1), (x + y) * M // max(1, w + h - 2), M - y * M // max(1, h - 1)
            if ctype == 0:
                vals.append(r); gg = s8(r, depth); al = 0 if key is not None and r == key else 255; px[x, y] = over_white(gg, gg, gg, al)
            elif ctype == 2:
                vals += [r, g, b]; al = 0 if key is not None and (r, g, b) == tuple(key) else 255; px[x, y] = over_white(s8(r, depth), s8(g, depth), s8(b, depth), al)
            elif ctype == 3:
                i = x * ncol // w; vals.append(i); px[x, y] = over_white(plte[3 * i], plte[3 * i + 1], plte[3 * i + 2], trns[i])
            elif ctype == 4:
                vals += [r, a]; gg = s8(r, depth); px[x, y] = over_white(gg, gg, gg, s8(a, depth))
            else:
                vals += [r, g, b, a]; px[x, y] = over_white(s8(r, depth), s8(g, depth), s8(b, depth), s8(a, depth))
        row = pack_row(vals, depth)
        raw += filt(row, prev, bpp, filters[y % len(filters)]); prev = row
    return raw, exp, plte, trns


def shrink(m, data, dst=DST):
    """pv_shrink_png over data as the downloaded file: (result, the output JPEG or None)."""
    m.jinit(); m.jlog.clear()
    m.fs.pop(dst, None); m.fs[SRC] = data
    r = m.call(PSYMS['pv_shrink_png'], a0=m.cstr(SRC), a1=m.cstr(dst), count=1 << 40)
    r = r - (1 << 32) if r >= 1 << 31 else r
    return r, m.fs.get(dst)


def close_to(m, out, exp, tol_mean=3.0, tol_max=40):
    """The output decodes to the box-average resize of the expected picture, within a tolerance."""
    from PIL import Image, ImageChops
    got = Image.open(io.BytesIO(out)); got.load()
    w, h = exp.size; s = min(1.0, 192 / max(w, h))
    size = (max(1, int(w * s)), max(1, int(h * s)))
    ref = exp.resize(size, Image.BOX)
    if got.size != size: return False, f'size {got.size} != {size}'
    diff = ImageChops.difference(got.convert('RGB'), ref)
    px = [v for p in diff.getdata() for v in p]
    mean, mx = sum(px) / len(px), max(px)
    return mean <= tol_mean and mx <= tol_max, f'mean {mean:.2f} max {mx}'


def clean(m, label, expect):
    expect(DST not in m.fs and m.jlog.count('create_compress') == m.jlog.count('destroy_compress') and m.jlog.count('create_decompress') == 0, f'{label}: no output file, the encoder destroyed')


def run(ctx):
    expect = ctx.expect
    from PIL import Image
    m = PCN.machine()
    m.folder(DIR)

    # 1. Every colour type and depth, filters cycling over the rows, dynamic blocks
    for ctype, depths in ((0, (1, 2, 4, 8, 16)), (2, (8, 16)), (3, (1, 2, 4, 8)), (4, (8, 16)), (6, (8, 16))):
        for depth in depths:
            raw, exp, plte, trns = picture(230, 170, ctype, depth, filters=(0, 1, 2, 3, 4))
            r, out = shrink(m, png(230, 170, ctype, depth, raw, plte, trns))
            edgy = ctype == 3 or depth <= 2   # steps, not a ramp: a pixel at a step may fall on either side of PIL's box
            ok, why = close_to(m, out, exp, 5.0 if edgy else 3.0, 255 if edgy else 40) if out else (False, 'no output')
            expect(r == 1 and ok, f'colour type {ctype}, {depth} bit: decoded, composited over white and shrunk like PIL ({why})')

    # 2. The filters one at a time, the deflate modes, many IDAT chunks (and an empty one)
    for t in range(5):
        raw, exp, plte, trns = picture(150, 150, 2, 8, filters=(t,))
        r, out = shrink(m, png(150, 150, 2, 8, raw))
        ok, why = close_to(m, out, exp) if out else (False, 'no output')
        expect(r == 1 and ok, f'filter {t} on every row ({why})')
    raw, exp, plte, trns = picture(200, 120, 6, 8, filters=(4, 1, 3))
    for mode in ('dynamic', 'fixed', 'stored'):
        for split in (0, 777):
            r, out = shrink(m, png(200, 120, 6, 8, raw, mode=mode, split=split))
            ok, why = close_to(m, out, exp) if out else (False, 'no output')
            expect(r == 1 and ok, f'{mode} blocks, {"one IDAT chunk" if not split else "IDAT chunks of 777 bytes with an empty one between"} ({why})')
    r, out = shrink(m, png(200, 120, 6, 8, raw, extra=[(b'tEXt', b'Comment\0hello'), (b'gAMA', bytes(4))]))
    expect(r == 1 and out, 'ancillary chunks before the data are skipped')

    # 3. Transparency keys, small and not square pictures, odd sizes
    raw, exp, plte, trns = picture(64, 64, 0, 8, key=0)
    r, out = shrink(m, png(64, 64, 0, 8, raw, trns=trns))
    ok, why = close_to(m, out, exp) if out else (False, 'no output')
    expect(r == 1 and ok and exp.getpixel((0, 0)) == (255, 255, 255), f'a grey tRNS key makes that sample transparent (white) ({why})')
    raw, exp, plte, trns = picture(64, 64, 2, 16, key=(0, 0, 0))
    r, out = shrink(m, png(64, 64, 2, 16, raw, trns=trns))
    ok, why = close_to(m, out, exp) if out else (False, 'no output')
    expect(r == 1 and ok, f'an RGB tRNS key, 16 bit ({why})')
    for w, h in ((1, 1), (3, 200), (200, 3), (192, 192), (193, 100), (100, 80)):
        raw, exp, plte, trns = picture(w, h, 2, 8, filters=(4, 2))
        r, out = shrink(m, png(w, h, 2, 8, raw))
        got = Image.open(io.BytesIO(out)) if out else None
        s = min(1.0, 192 / max(w, h))
        expect(r == 1 and got and got.size == (max(1, int(w * s)), max(1, int(h * s))), f'{w} x {h}: fitted inside 192, never upscaled ({got.size if got else None})')

    # 4. The real shapes: 2000 x 2000 RGBA (the All-In cover) and 3000 x 3000 RGB, with PIL's own encoder
    def pil_png(w, h, mode):
        ax = Image.linear_gradient('L').rotate(90).resize((w, h))
        ay = Image.linear_gradient('L').resize((w, h))
        bands = [ax, ay, Image.blend(ax, ay, 0.5)] + ([ay.point(lambda v: 255 - v)] if mode == 'RGBA' else [])
        im = Image.merge(mode, bands)
        b = io.BytesIO(); im.save(b, 'PNG', optimize=True)
        return b.getvalue(), im
    data, im = pil_png(2000, 2000, 'RGBA')
    r, out = shrink(m, data)
    ref = Image.alpha_composite(Image.new('RGBA', im.size, 'white'), im).convert('RGB')
    ok, why = close_to(m, out, ref, 4.0, 40) if out else (False, 'no output')
    expect(r == 1 and ok, f'2000 x 2000 RGBA ({len(data) // 1024} kB): a 192 x 192 JPEG like PIL\'s ({why})')
    data, im = pil_png(3000, 3000, 'RGB')
    r, out = shrink(m, data)
    ok, why = close_to(m, out, im, 4.0, 40) if out else (False, 'no output')
    expect(r == 1 and ok and m.jlog.count('std_error') == 1, f'3000 x 3000 RGB ({len(data) // 1024} kB) ({why})')

    # 5. What is refused or damaged: nothing is left, nothing breaks
    raw, exp, plte, trns = picture(300, 300, 2, 8, filters=(0, 1, 2, 3, 4))
    good = png(300, 300, 2, 8, raw)
    r, out = shrink(m, good)
    expect(r == 1, 'the base picture of the damage tests decodes')
    r, out = shrink(m, png(300, 300, 2, 8, raw, interlace=1))
    expect(r == -1 and out is None, 'an interlaced PNG: -1 (the caller may keep a small one), nothing written')
    for label, data in (('a PNG cut half way', good[:len(good) // 2]), ('a PNG cut in the first chunk', good[:20]), ('no data chunk', good[:good.index(b'IDAT') - 4]),
                        ('a bad signature', b'\x89PNX' + good[4:]), ('a GIF', b'GIF89a' + bytes(100)), ('nothing', b''),
                        ('an unknown colour type', png(300, 300, 5, 8, raw)), ('a bad depth', png(300, 300, 2, 4, raw)), ('16 bit palette', png(300, 300, 3, 16, raw, plte=bytes(6))),
                        ('a palette PNG without a palette', png(300, 300, 3, 8, raw)), ('a 0 wide picture', png(0, 300, 2, 8, raw)), ('9000 px wide', png(9000, 10, 2, 8, raw)),
                        ('6000 x 6000 (over the pixel cap)', png(6000, 6000, 2, 8, raw)), ('a bad zlib header', good.replace(b'IDAT\x78', b'IDAT\x79', 1)),
                        ('a chunk longer than the file', good[:good.index(b'IDAT') - 4] + struct.pack('>I', 1 << 30) + good[good.index(b'IDAT'):]),
                        ('a huge chunk length', good[:good.index(b'IDAT') - 4] + struct.pack('>I', 0xffffffff) + good[good.index(b'IDAT'):])):
        r, out = shrink(m, data)
        expect(r == 0 and out is None, f'{label}: refused')
        clean(m, label, expect)
    r, out = shrink(m, png(300, 300, 2, 8, raw[:-901]))
    expect(r == 0 and out is None, 'one row short: refused'); clean(m, 'one row short', expect)
    r, out = shrink(m, png(300, 300, 2, 8, raw + raw[:901]))
    expect(r == 0 and out is None, 'one row too many: refused'); clean(m, 'one row too many', expect)
    bad = bytearray(raw); bad[901 * 7] = 9
    r, out = shrink(m, png(300, 300, 2, 8, bytes(bad)))
    expect(r == 0 and out is None, 'a filter byte of 9: refused'); clean(m, 'bad filter', expect)
    bomb = png(100, 100, 0, 8, bytes(1 + 100) * 100)
    z = zlib.compress(bytes(80 << 20), 9)
    bomb = bomb[:bomb.index(b'IDAT') - 4] + chunk(b'IDAT', z) + chunk(b'IEND', b'')
    r, out = shrink(m, bomb)
    expect(r == 0 and out is None and len(z) < 200000, 'a zlib bomb (80 MB from 80 kB) into a 100 x 100 picture: stopped at the header\'s size, refused'); clean(m, 'zlib bomb', expect)
    raw8, exp8, _, _ = picture(100, 100, 2, 8)
    z = zlib.compress(raw8)
    for label, zz in (('a block of type 3', bytes([z[0], z[1], 0x07]) + z[3:]), ('a stored block whose length check fails', bytes([z[0], z[1], 0x01, 5, 0, 0, 0]) + bytes(5)),
                      ('a distance beyond the output', bytes([0x78, 0x9c, 0x03, 0x02, 0x00])), ('an empty stream', bytes([0x78, 0x9c]))):
        data = good[:good.index(b'IDAT') - 4] + chunk(b'IDAT', zz) + chunk(b'IEND', b'')
        r, out = shrink(m, data)
        expect(r == 0 and out is None, f'{label}: refused'); clean(m, label, expect)

    # 6. Byte flips and cuts: whatever the damage, the decoder returns 0 or 1 and writes at most a complete JPEG
    rng = random.Random(20261030)
    raw, exp, plte, trns = picture(120, 90, 6, 8, filters=(0, 1, 2, 3, 4))
    base = png(120, 90, 6, 8, raw, split=500)
    flips = results = 0
    for i in range(300):
        d = bytearray(base)
        for _ in range(1 + i % 4): d[rng.randrange(8, len(d))] ^= 1 << rng.randrange(8)
        if i % 10 == 0: d = d[:rng.randrange(8, len(d))]
        r, out = shrink(m, bytes(d))
        flips += 1
        results += r in (0, 1) and ((out is not None) == (r == 1)) and m.jlog.count('create_compress') == m.jlog.count('destroy_compress')
    expect(flips == 300 and results == 300, f'300 random byte flips and cuts: never a crash, a result of 0 or 1, an output only for 1, the encoder always destroyed ({results} of {flips})')
    pal_raw, pal_exp, plte, trns = picture(100, 60, 3, 4, filters=(1, 4))
    base = png(100, 60, 3, 4, pal_raw, plte, trns, mode='fixed')
    results = 0
    for i in range(150):
        d = bytearray(base)
        for _ in range(1 + i % 3): d[rng.randrange(8, len(d))] ^= 1 << rng.randrange(8)
        r, out = shrink(m, bytes(d))
        results += r in (0, 1) and ((out is not None) == (r == 1))
    expect(results == 150, f'150 flips in a palette picture with fixed blocks ({results} of 150)')
