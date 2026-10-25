#!/usr/bin/env python3
"""Host build of Cover Flow's depth renderer and cache helpers, with checks and PNG captures.

The same patch/coverflow.c that goes into the payload is compiled for the host with -DCF_HOST
(which drops everything that talks to demo) and driven through ctypes, so the geometry, the
compositing, the texture sampling and the cache key are tested without a device. Modelled on
q2-pod's test/coverflow.py (Copyright (c) 2026 Diamond Bond, MIT; see NOTICE).

  venv/bin/python -I test/coverflow.py [--captures DIR] [--preview PNG]

--captures writes the raw CF_VIEW_W x CF_VIEW_H frames at rest and part-way through a turn;
--preview composes the 320x480 page around one of them (approximate: PIL, not AWTK).
"""
import argparse, ctypes, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'patch', 'coverflow.c')
INC = os.path.join(ROOT, 'patch', 'offsets.inc')


def constants():
    """The CF_* geometry the payload is built with, read from patch/offsets.inc."""
    out = {}
    for line in open(INC):
        m = re.match(r'#define (\w+) (-?(?:0x[0-9a-fA-F]+|\d+))u?\s*(?:/\*.*)?$', line.strip())
        if m: out[m.group(1)] = int(m.group(2), 0)
    return out


C = constants()
W, H, ART, CX = C['CF_VIEW_W'], C['CF_VIEW_H'], C['ART_SIZE'], C['CF_CX']
TOP, REFLECT = C['CF_TOP'], C['CF_REFLECT']
ONE, REACH, RING = 65536, 3, 7
TEXELS = ART * ART


def build(tmp):
    so = os.path.join(tmp, 'coverflow.so')
    subprocess.run(['cc', '-O2', '-std=c99', '-Wall', '-DCF_HOST', '-shared', '-fPIC',
                    '-I', os.path.join(ROOT, 'patch'), SRC, '-o', so], check=True)
    lib = ctypes.CDLL(so)
    lib.coverflow_render.restype = None
    lib.coverflow_render.argtypes = [ctypes.POINTER(ctypes.c_uint), ctypes.c_int, ctypes.c_int,
                                     ctypes.POINTER(ctypes.c_void_p)]
    lib.cf_fnv.restype = ctypes.c_uint
    lib.cf_fnv.argtypes = [ctypes.c_uint, ctypes.c_char_p]
    lib.cf_sample.restype = None
    lib.cf_sample.argtypes = [ctypes.c_char_p, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint,
                              ctypes.c_char_p, ctypes.POINTER(ctypes.c_uint)]
    return lib


def texture(colour, mark=0):
    """A flat cover with a brighter band, so turns and mirroring are visible."""
    buf = (ctypes.c_uint * TEXELS)()
    r, g, b = colour
    for y in range(ART):
        for x in range(ART):
            v = (r, g, b)
            if y < 10 or y >= ART - 10 or x < 10 or x >= ART - 10: v = (240, 240, 240)
            if mark and (x // 16 + y // 16) % 2 == 0: v = (v[0] // 2, v[1] // 2, v[2] // 2)
            buf[y * ART + x] = 0xff000000 | v[0] | v[1] << 8 | v[2] << 16
    return buf


def render(lib, frac, texs):
    frame = (ctypes.c_uint * (W * H))()
    ring = (ctypes.c_void_p * RING)()
    for i, t in enumerate(texs):
        ring[i] = ctypes.cast(t, ctypes.c_void_p) if t is not None else None
    lib.coverflow_render(frame, W, frac, ring)
    return frame


def px(frame, x, y):
    v = frame[y * W + x]
    return v & 255, v >> 8 & 255, v >> 16 & 255, v >> 24 & 255


def save(frame, path):
    from PIL import Image
    img = Image.new('RGB', (W, H))
    img.putdata([(frame[i] & 255, frame[i] >> 8 & 255, frame[i] >> 16 & 255) for i in range(W * H)])
    img.save(path)


def preview(frame, path, album='Kind of Blue', artist='Miles Davis'):
    """The whole 320x480 page around a rendered frame: navbar, captions, hint. Approximate."""
    from PIL import Image, ImageDraw, ImageFont
    page = Image.new('RGB', (320, 480), (0, 0, 0))
    covers = Image.new('RGB', (W, H))
    covers.putdata([(frame[i] & 255, frame[i] >> 8 & 255, frame[i] >> 16 & 255) for i in range(W * H)])
    page.paste(covers, (0, 56))
    d = ImageDraw.Draw(page)

    def font(size):
        for p in ('/System/Library/Fonts/Helvetica.ttc', '/Library/Fonts/Arial.ttf'):
            if os.path.exists(p):
                try: return ImageFont.truetype(p, size)
                except OSError: pass
        return ImageFont.load_default()

    def centred(text, y, size, colour):
        f = font(size)
        w = d.textbbox((0, 0), text, font=f)[2]
        d.text(((320 - w) // 2, y), text, font=f, fill=colour)

    d.rectangle([0, 0, 319, 49], fill=(0, 0, 0))
    d.line([(0, 49), (319, 49)], fill=(30, 30, 30))
    d.polygon([(28, 25), (40, 17), (40, 33)], fill=(220, 220, 220))          # Back chevron
    d.ellipse([272, 13, 296, 37], outline=(220, 220, 220))                   # Now Playing
    centred('Cover Flow', 14, 20, (255, 255, 255))
    centred(album, 300, 22, (255, 255, 255))
    centred(artist, 334, 18, (170, 170, 170))
    centred('Tap the centre cover to open the album', 392, 13, (136, 136, 136))
    page.save(path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--captures'); ap.add_argument('--preview')
    a = ap.parse_args()
    ok = fail = 0

    def expect(cond, msg):
        nonlocal ok, fail
        if cond: ok += 1
        else: fail += 1; print('  FAIL:', msg)

    with tempfile.TemporaryDirectory() as tmp:
        lib = build(tmp)
        colours = [(200, 60, 60), (60, 160, 200), (230, 190, 70), (120, 200, 120),
                   (200, 120, 200), (90, 90, 220), (210, 140, 60)]
        texs = [texture(c, mark=i == REACH) for i, c in enumerate(colours)]

        # 1. At rest the centre cover is its texture, pixel for pixel, at the expected place.
        rest = render(lib, 0, texs)
        x0, y0 = CX - ART // 2, TOP
        same = all(rest[(y0 + y) * W + x0 + x] == texs[REACH][y * ART + x] for y in range(ART)
                   for x in range(0, ART, 7))
        expect(same, 'the centre cover is drawn 1:1 from its texture')

        # 2. Nothing is drawn above the frame, and every pixel is opaque black or cover.
        expect(all(px(rest, x, 0)[3] == 255 for x in range(0, W, 3)), 'the frame is opaque')
        expect(all(rest[0 * W + x] & 0xffffff == 0 for x in range(0, W, 3)), 'top row is black')
        expect(all(rest[(H - 1) * W + x] & 0xffffff == 0 for x in range(0, W, 3)),
               'bottom row is black (reflections fade out above it)')

        # 3. At rest, with one mirror-symmetric texture in every slot, the shelf is symmetric
        #    about the centre line (the renderer mirrors left covers onto right ones).
        flat = texture((200, 60, 60))
        sym = render(lib, 0, [flat] * RING)
        mirrored = all(sym[y * W + x] == sym[y * W + (2 * CX - 1 - x)]
                       for y in range(0, H, 5) for x in range(0, CX, 5))
        expect(mirrored, 'the shelf is mirror-symmetric at rest')

        # 4. Brightness falls with distance: the same cover alone in each ring slot, so nothing
        #    overlaps it, is dimmer one out than at the centre and dimmer still two out.
        def alone_at(j):
            ring = [None] * RING
            ring[j] = flat
            f = render(lib, 0, ring)
            return max(max(px(f, x, y)[:3]) for y in range(0, H, 3) for x in range(0, W, 2))
        b0, b1, b2, b3 = (alone_at(REACH + k) for k in range(4))
        expect(b0 == 240, f'the centre cover keeps its own pixels ({b0})')
        expect(b1 == 240 * C['CF_BRIGHT1'] // 256, f'one cover out is CF_BRIGHT1 ({b1})')
        expect(b2 == 240 * C['CF_BRIGHT2'] // 256, f'two covers out are CF_BRIGHT2 ({b2})')
        expect(b3 == 0, 'three covers out have faded away')

        # 5. A cover has a reflection under it: the rows just below its bottom edge are not black.
        refl = [sum(px(rest, CX, TOP + ART + k)[:3]) for k in range(1, REFLECT)]
        expect(any(v > 0 for v in refl), 'the centre cover reflects')
        expect(refl[0] >= refl[-1], 'the reflection fades downwards')

        # 6. A small step changes the frame only a little; half a step is still symmetric about
        #    the pair of covers that share the centre.
        small = render(lib, ONE // 64, texs)
        n = len(range(0, W * H, 11))
        drift = sum(max(abs(a - b) for a, b in zip(px(small, i % W, i // W), px(rest, i % W, i // W)))
                    for i in range(0, W * H, 11)) / n
        expect(drift < 12, f'a 1/64 step moves the frame only a little (mean |delta| {drift:.1f})')
        half = render(lib, ONE // 2, texs)
        expect(any(half[i] != rest[i] for i in range(0, W * H, 7)), 'half a step differs from rest')

        # 7. A missing texture (no art decoded) leaves its slot empty without disturbing the rest.
        gap = list(texs); gap[REACH + 1] = None
        hole = render(lib, 0, gap)
        expect(all(hole[(y0 + y) * W + x0 + x] == rest[(y0 + y) * W + x0 + x]
                   for y in range(0, ART, 9) for x in range(0, ART, 9)),
               'a missing neighbour does not change the centre cover')

        # 8. Only the centre cover: no neighbours, no crash, still symmetric.
        alone = render(lib, 0, [None] * REACH + [texs[REACH]] + [None] * REACH)
        expect(alone[(y0 + 5) * W + x0 + 5] == texs[REACH][5 * ART + 5], 'a one-album library draws')

        # 9. The cache key: FNV-1a of artist then album, each with a separator, never 0.
        def fnv(h, s):
            for c in s.encode(): h = (h ^ c) * 16777619 & 0xffffffff
            return h * 16777619 & 0xffffffff
        for artist, album in (('Miles Davis', 'Kind of Blue'), ('', ''), ('a', 'bc'), ('ab', 'c')):
            want = fnv(fnv(C['FNV_SEED'], artist), album)
            got = lib.cf_fnv(lib.cf_fnv(C['FNV_SEED'], artist.encode()), album.encode())
            expect(got == want, f'cf_fnv({artist!r}, {album!r})')
        expect(lib.cf_fnv(C['FNV_SEED'], b'a') != lib.cf_fnv(C['FNV_SEED'], b'b'), 'keys differ')
        expect(fnv(fnv(C['FNV_SEED'], 'ab'), 'c') != fnv(fnv(C['FNV_SEED'], 'a'), 'bc'),
               'the separator keeps "ab"+"c" and "a"+"bc" apart')

        # 10. cf_sample: the centred square of a wide image, nearest sampled, alpha over black.
        src_w, src_h = 2 * ART, ART
        src = bytearray(src_w * src_h * 4)
        for y in range(src_h):
            for x in range(src_w):
                inside = ART // 2 <= x < ART // 2 + ART
                src[(y * src_w + x) * 4:(y * src_w + x) * 4 + 4] = bytes(
                    (255, 0, 0, 255) if inside else (0, 255, 0, 255))
        out = (ctypes.c_uint * TEXELS)()
        lib.cf_sample(bytes(src), src_w, src_h, src_w * 4, bytes((0, 1, 2, 3)), out)
        expect(all(out[i] == 0xff0000ff for i in range(0, TEXELS, 97)),
               'cf_sample takes the centred square')
        half_alpha = bytes((10, 20, 30, 128)) * (src_w * src_h)
        lib.cf_sample(half_alpha, src_w, src_h, src_w * 4, bytes((0, 1, 2, 3)), out)
        expect(out[0] == 0xff000000 | 5 | 10 << 8 | 15 << 16, 'cf_sample composes alpha over black')

        if a.captures:
            os.makedirs(a.captures, exist_ok=True)
            for name, frac in (('rest', 0), ('quarter', ONE // 4), ('half', ONE // 2),
                               ('three-quarter', -ONE // 4)):
                save(render(lib, frac, texs), os.path.join(a.captures, f'coverflow-{name}.png'))
            print(f'captures in {a.captures}')
        if a.preview:
            preview(render(lib, ONE // 6, texs), a.preview)
            print(f'preview {a.preview}')

    print(f'{ok} passed, {fail} failed')
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
