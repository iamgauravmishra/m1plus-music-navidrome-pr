#!/usr/bin/env python3
"""The Vinyl page's art (docs/modules/vinyl.md): the drawing code of the approved mock (frames J1 / J2 of tools/preview_vinyl.py), shared by the preview
(`design`, the full mock frame), the build (`images()`: the installed pictures; tools/mod_icons.py puts them in the tree and assets/icons/png keeps the
generated files) and test/pod/vinyl.py (the numbers, the reference model of what the payload composes).

The page is PORTRAIT, 320 x 480, fullscreen (no status bar): a turntable seen from above. The record lies off the left edge (centre REC_C, radius REC_R), its label
is the playing track's cover (LAB_R), a tonearm turns about PIVOT on a raised pill plate, three round keys sit at the bottom right, the text is the page's own
AWTK labels (TEXT). Neutral greys only.

Layers (the page composes them at run time, patch/vinyl.c; every one drawn at K x and reduced, deterministic):
  vinyl_base   320 x 480, opaque: the plinth (a gentle vertical grey gradient with film grain on the background only), the arm's plate and base, the record (grooves and
               a weak static sheen: the light does not turn with the record, so the grooves are static and only the label turns), its shadow, the keys at rest, the close
               chevron. No label, no spindle, no arm, no text.
  vinyl_lid    LID_RECT, RGBA: what lies on the turning label and does not turn: the pressed step at its edge, a soft paper gloss, the white rim, the spindle.
  vinyl_arm    the tonearm pointing +x (counterweight, tube, headshell, cartridge), ARM_SIZE, RGBA, the pivot at ARM_PIVOT (a pixel corner); the page turns it about PIVOT.
  vinyl_armsh  its shadow in the same frame: the arm's alpha blurred, ARM_SHADOW's alpha in A (RGB black); the page draws it ARM_SHADOW's (dx, dy) down-right of the arm.
  vinyl_cap    CAP_RECT, RGBA: the round gimbal cap over the pivot (round, so it does not turn) with its shadow.
  vinyl_keys   KEY_SHEET: opaque cells of the key band (BAND_Y) in each look: the play key at rest and pressed, with the play or the pause glyph, and the previous / next keys
               pressed (their rest look is in vinyl_base).
  vinyl_label  LAB_PX square, opaque: the label of a track without a cover (a light grey paper label).
  vinyl_rec    REC_BOX, RGBA: for a coloured record (Settings > Now Playing > Record): RGB the plinth with the record's shadow and no record (no grain on the disc), A the record
               map t (0 where the base stays as it is). The page composes the ring once into its own copy of the base, by tables on t (docs/modules/vinyl.md "Record colours").
"""
import math, os, random
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

W, H, K = 320, 480, 3

# ---- the layout (1x px). patch/offsets.inc VN_* hold the same numbers (test/pod/vinyl.py checks them) -------------------------------------------------
REC_C, REC_R, LAB_R = (96, 196), 162, 76     # the record's centre and radius, the label's radius (about half the record)
LAB_PX = 2 * LAB_R                           # the label picture (the cover reduced to it): its centre is LAB_R, LAB_R (a pixel corner)
LAB_IN = 77                                  # the page draws the turning label inside this radius (the white rim, LAB_R .. LAB_R + 1.6, covers its edge)
PIVOT, ARM_L, ARM_BEND, BASE_R = (276, 70), 246, 24, 15
ARM_C = dict(tube=(0xB8, 0xBB, 0xC0), shell=(0x24, 0x24, 0x26), weight=(0x1E, 0x1E, 0x20), cart=(0x2C, 0x2C, 0x2E), screw=(0x6A, 0x6A, 0x6E), base=(0x30, 0x30, 0x33))
ARM_SHADOW = (5, 7, 3, 150)                  # the arm's shadow: dx, dy, blur, alpha
BG = 0x46                                    # the plinth's grey (the middle of its gradient)
GRAIN = (6, 1.0)                             # film grain amplitude and clump size (1 px), on the background only
SHEEN = 0.22                                 # the record's static sheen (weak: a dark record)
REC_SHADOW = (4, 9, 120)                     # the record's shadow: dy, blur, alpha
GAPS = (104, 121, 138)                       # the smooth gaps between tracks (radius)
TH0 = math.radians(-35)                      # the sheen's lobes
PLATE = (PIVOT[0] - 26, PIVOT[1] - 40, PIVOT[0] + 26, PIVOT[1] + 40)   # the arm's raised pill plate, radius 26, centred on the pivot
KEYS = (('prev', 200, 15), ('play', 246, 19), ('next', 292, 15))       # the round keys: centre x, radius; all at KEY_Y
KEY_Y = 449
BAND_Y = (420, 478)                          # the key band's rows (y0, y1 exclusive)
KEY_COLS = {'prev': (170, 223), 'play': (223, 269), 'next': (269, 318)}   # each key's columns in the band (its cell, its touch area with BAND_Y .. 480)
CHEVRON = (16, 11)
CLOSE_RECT = (0, 0, 52, 44)                  # the close chevron's touch area (x0, y0, x1, y1 exclusive)
LID_RECT = (16, 116, 176, 276)               # vinyl_lid on the screen
CAP_RECT = (262, 56, 294, 88)                # vinyl_cap on the screen
TAP_PX = 14                                  # a touch that travels less than this is a tap (the record)
# the key sheet: (name, state) -> (x in the sheet, width); 58 rows (BAND_Y). The play key: 0 play glyph, 1 pause glyph, + 2 pressed.
KEY_CELLS = {('play', 0): 0, ('play', 1): 46, ('play', 2): 92, ('play', 3): 138, ('prev', 2): 184, ('next', 2): 237}
KEY_SHEET = (286, BAND_Y[1] - BAND_Y[0])

# the text: AWTK labels of the page (tools/pod_ui.py build_vinyl_page): x, the line's vertical middle, px, colour, the label's width
TEXT = {
    'title':  dict(x=16, y=392, px=22, rgb=(0xF4, 0xF4, 0xF6), w=280, bold=True),   # bold: a twin label 1 px right (the mock draws it twice)
    'artist': dict(x=16, y=416, px=15, rgb=(0xC8, 0xC8, 0xCE), w=280),
    'times':  dict(x=16, y=449, px=12, rgb=(0xB4, 0xB4, 0xBA), w=140),
    'status': dict(x=34, y=12, px=10, rgb=(0xBC, 0xBC, 0xC2), w=200),   # (the mock's #ACACB2 is 4.2:1 on the plinth: lifted to 4.5:1 at its lightest, the top)
}


# ---- themes (mocks only: the installed pictures are the Graphite look; docs/modules/vinyl.md) --------------------------------------------------------
# T holds what a theme changes beyond the module numbers above (use() also sets BG, ARM_C, ARM_SHADOW, REC_SHADOW, GRAIN). Graphite is the approved look.
GRAPHITE = dict(
    grad=[(BG + 6, BG + 6, BG + 8), (BG - 4, BG - 4, BG - 2), (BG + 1, BG + 1, BG + 3)],
    plate=(BG + 12, BG + 12, BG + 15), plate_sh=150, plate_hi=40, base_ring=0.0,
    key=(0x2E, 0x2E, 0x31), key_down=(0x24, 0x24, 0x26), key_sh=200, key_hi=(60, 25), key_lo=140,
    glyph=(0xEE, 0xEE, 0xF0), glyph_down=(0xC4, 0xC4, 0xC8), chevron=(0xB4, 0xB4, 0xBA, 255), text={},
    arm=dict(ARM_C), arm_shadow=ARM_SHADOW, rec_shadow=REC_SHADOW, grain=GRAIN, rim=(0xF4, 0xF4, 0xF4))
T = dict(GRAPHITE)
THEME_NAMES = ('graphite', 'white')
THEMES = {
    'graphite': {},
    # a matte off-white plinth (minimal, light), a black record, grey keys, dark text
    'white': dict(
        grad=[(0xF0, 0xF0, 0xEF), (0xE4, 0xE4, 0xE4), (0xEA, 0xEA, 0xEA)], grain=(3, 1.0),
        plate=(0xF4, 0xF4, 0xF4), plate_sh=70, plate_hi=0, rec_shadow=(5, 10, 85),
        key=(0x6A, 0x6A, 0x6E), key_down=(0x58, 0x58, 0x5C), key_sh=100, key_hi=(80, 40), key_lo=80,
        glyph=(0xFC, 0xFC, 0xFC), glyph_down=(0xD0, 0xD0, 0xD4), chevron=(0x58, 0x58, 0x5C, 255), rim=(0xFF, 0xFF, 0xFF),
        text=dict(title=(0x1C, 0x1C, 0x1E), artist=(0x44, 0x44, 0x48), times=(0x56, 0x56, 0x5A), status=(0x56, 0x56, 0x5A)),
        arm=dict(tube=(0x90, 0x90, 0x92), shell=(0x26, 0x26, 0x28), weight=(0x22, 0x22, 0x24), cart=(0x2C, 0x2C, 0x2E), screw=(0xA0, 0xA0, 0xA6), base=(0xA8, 0xA8, 0xAC)),
        arm_shadow=(4, 6, 3, 80)),
}


def use(name):
    """Select a theme (mock only): sets T and the module numbers, drops the caches of what depends on them."""
    global T, BG, ARM_C, ARM_SHADOW, REC_SHADOW, GRAIN
    T = dict(GRAPHITE, **THEMES[name])
    BG, ARM_C, ARM_SHADOW, REC_SHADOW, GRAIN = T.get('bg', 0x46), T['arm'], T['arm_shadow'], T['rec_shadow'], T['grain']
    _ARM.clear(); _ARMCROP.clear(); _SCENE.clear()


def label_box(name):
    """(x, y, w, h) of a text label: the line's middle at TEXT y (text_align_v middle), px + 4 high."""
    t = TEXT[name]; h = t['px'] + 4
    return (t['x'], t['y'] - h // 2, t['w'], h)


def S(v): return int(round(v * K))
def mix(a, b, t): return tuple(int(x + (y - x) * t) for x, y in zip(a, b))
def clamp(v): return max(0, min(255, int(v)))
def scale(c, f): return tuple(clamp(v * f) for v in c)


def noise_img(w, h, seed, lo=0, hi=255):
    r = random.Random(seed)
    return Image.frombytes('L', (w, h), bytes(r.randrange(lo, hi + 1) for _ in range(w * h)))


def disc_mask(size, cx, cy, r):
    m = Image.new('L', size, 0); ImageDraw.Draw(m).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255); return m


def ring_mask(size, cx, cy, r0, r1):
    return ImageChops.subtract(disc_mask(size, cx, cy, r1), disc_mask(size, cx, cy, r0))


def shadow(im, m, dx, dy, blur, a):
    sh = m.point(lambda v: v * a // 255).filter(ImageFilter.GaussianBlur(blur))
    layer = Image.new('RGBA', im.size, (0, 0, 0, 0)); layer.putalpha(ImageChops.offset(sh, dx, dy)); im.alpha_composite(layer)


def fill(im, m, rgb, a=255):
    layer = Image.new('RGBA', im.size, rgb + (0,)); layer.putalpha(m.point(lambda v: v * a // 255)); im.alpha_composite(layer)


def paste_rgb(im, src, m):
    layer = src.convert('RGBA'); layer.putalpha(m); im.alpha_composite(layer)


def stops(size, cols, horizontal=False):
    """A gradient through several colours, evenly spaced."""
    w, h = size; n = w if horizontal else h
    line = []
    for i in range(n):
        t = i / max(1, n - 1) * (len(cols) - 1); k = min(int(t), len(cols) - 2); line.append(mix(cols[k], cols[k + 1], t - k))
    im = Image.new('RGB', (n, 1)); im.putdata(line)
    return im.resize((w, h)) if horizontal else im.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT).resize((w, h))


def satin(size, base, seed):
    w, h = size
    n = noise_img(w, h, seed, 112, 144)
    return ImageOps.colorize(n, scale(base, 0.85), scale(base, 1.15), mid=base)


def radial_table(size, cx, cy, table, r_lo, r_hi, outside=0):
    """An L image whose value is table[int(r - r_lo)] at distance r from (cx, cy), `outside` elsewhere (per pixel, deterministic)."""
    w, h = size; out = bytearray(w * h); n = len(table)
    x0, x1 = max(0, int(cx - r_hi) - 1), min(w, int(cx + r_hi) + 2)
    y0, y1 = max(0, int(cy - r_hi) - 1), min(h, int(cy + r_hi) + 2)
    if outside: out[:] = bytes([outside]) * (w * h)
    for y in range(y0, y1):
        dy2 = (y - cy) ** 2; row = y * w
        for x in range(x0, x1):
            r = math.sqrt((x - cx) ** 2 + dy2) - r_lo
            if 0 <= r < n: out[row + x] = table[int(r)]
    return Image.frombytes('L', size, bytes(out))


def angular(size, cx, cy, r0, r1, th0, lobes=2, p=8.0, soft=0.25, fade=0.12):
    """The anisotropic sheen of a grooved disc: bright lobes at angle th0 (+ 180 for 2 lobes), computed at 1:1 (size is 1x), smooth; L."""
    w, h = size; out = bytearray(w * h)
    x0, x1 = max(0, int(cx - r1)), min(w, int(cx + r1) + 1)
    y0, y1 = max(0, int(cy - r1)), min(h, int(cy + r1) + 1)
    for y in range(y0, y1):
        for x in range(x0, x1):
            dx, dy = x - cx, y - cy; r = math.hypot(dx, dy)
            if r < r0 or r > r1: continue
            c = max(0.0, math.cos(lobes / 2 * 2 * (math.atan2(dy, dx) - th0)))
            v = c ** p + soft * c ** 1.5
            e = min(1.0, (r - r0) / ((r1 - r0) * fade + 1e-6), (r1 - r) / ((r1 - r0) * fade + 1e-6))
            out[y * w + x] = clamp(255 * min(1.0, v) * max(0.0, e))
    return Image.frombytes('L', size, bytes(out))


# ---- sample covers (the mock and the tests; the device shows the playing track's) --------------------------------------------------------------------------
def cover(kind, n=300):
    r = random.Random(kind)
    if kind == 'blue':     # a moody blue photo-like cover with a figure of light and a type block
        im = stops((n, n), [(0x0B, 0x1E, 0x3E), (0x1E, 0x4F, 0x8C), (0x0A, 0x16, 0x2C)])
        glow = Image.new('L', (n, n), 0); d = ImageDraw.Draw(glow)
        d.ellipse((n * 0.52, n * 0.18, n * 0.86, n * 0.70), fill=200); d.ellipse((n * 0.60, n * 0.06, n * 0.76, n * 0.24), fill=170)
        glow = glow.filter(ImageFilter.GaussianBlur(n / 14))
        im = Image.composite(Image.new('RGB', (n, n), (0xC8, 0xDC, 0xF0)), im, glow)
        d = ImageDraw.Draw(im)
        d.rectangle((n * 0.08, n * 0.08, n * 0.42, n * 0.13), fill=(0xF4, 0xF1, 0xE6)); d.rectangle((n * 0.08, n * 0.16, n * 0.30, n * 0.19), fill=(0x6F, 0xB7, 0xE8))
    elif kind == 'sunset':   # a retro sun with slices over a horizon
        im = stops((n, n), [(0xFF, 0xB0, 0x4A), (0xF0, 0x5A, 0x6E), (0x6A, 0x2A, 0x7E), (0x1C, 0x10, 0x30)])
        d = ImageDraw.Draw(im); cx, cy, rr = n / 2, n * 0.56, n * 0.27
        sun = Image.new('L', (n, n), 0); ds = ImageDraw.Draw(sun); ds.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=255)
        for i in range(6): y = cy + i * i * 1.3 + i * n * 0.025; ds.rectangle((0, y, n, y + 1 + i * n * 0.006), fill=0)
        im = Image.composite(stops((n, n), [(0xFF, 0xF2, 0xA8), (0xFF, 0x8A, 0x3C)]), im, sun)
        d = ImageDraw.Draw(im); d.rectangle((0, n * 0.80, n, n), fill=(0x14, 0x0C, 0x24))
        for i in range(8): d.line((n / 2, n * 0.80, n * (i - 3.5) * 0.5 + n / 2, n), fill=(0xE0, 0x58, 0xA8), width=max(1, n // 150))
        for i in range(5): y = n * 0.80 + (i + 1) ** 1.6 * n * 0.012; d.line((0, y, n, y), fill=(0xE0, 0x58, 0xA8), width=max(1, n // 150))
    else:                    # 'paper': cream, stacked ridge lines in black (a classic printed look)
        im = Image.new('RGB', (n, n), (0xEE, 0xE8, 0xD8)); d = ImageDraw.Draw(im)
        x0, x1 = n * 0.2, n * 0.8
        for k in range(34):
            y = n * 0.22 + k * n * 0.017; pts = []
            for i in range(41):
                x = x0 + (x1 - x0) * i / 40; c = 1 - abs(i - 20) / 20
                pts.append((x, y - max(0, c ** 2.2) * r.uniform(0, n * 0.06) - r.uniform(0, n * 0.004)))
            d.polygon(pts + [(x1, y + 4), (x0, y + 4)], fill=(0xEE, 0xE8, 0xD8)); d.line(pts, fill=(0x14, 0x14, 0x14), width=max(1, n // 200))
    return im


def fallback_label(n=LAB_PX * K):
    """The label of a track without a cover: light grey paper, a printed ring, two bars and a small side mark; neutral greys (the device turns it)."""
    base = (0xC4, 0xC4, 0xC8)
    im = Image.new('RGB', (n, n), base); d = ImageDraw.Draw(im)
    d.ellipse((n * 0.06, n * 0.06, n * 0.94, n * 0.94), outline=scale(base, 0.72), width=max(1, n // 80))
    d.ellipse((n * 0.30, n * 0.30, n * 0.70, n * 0.70), outline=scale(base, 0.82), width=max(1, n // 120))
    d.rectangle((n * 0.24, n * 0.20, n * 0.76, n * 0.25), fill=scale(base, 0.55))
    d.rectangle((n * 0.32, n * 0.75, n * 0.68, n * 0.78), fill=scale(base, 0.65))
    d.polygon([(n * 0.80, n * 0.47), (n * 0.87, n * 0.50), (n * 0.80, n * 0.53)], fill=scale(base, 0.5))
    return im.resize((n // K, n // K), Image.LANCZOS)


# ---- the record --------------------------------------------------------------------------------------------------------------
def groove_table(r_label, R, gaps, seed, lead=6, runout=10):
    """Groove brightness by radius (3x px from the label edge to the rim): fine random grooves, smooth gaps between tracks, a smooth lead-in and run-out, the rim bead."""
    r = random.Random(seed); n = S(R) - S(r_label); t = []
    for i in range(n):
        rad = (S(r_label) + i) / K
        if rad < r_label + runout: v = 128 + (14 if int(rad * 3) % 37 == 0 else 0)        # run-out: smooth, one locked groove
        elif rad > R - 1.3: v = 190 - int((rad - (R - 1.3)) * 60)                          # the rim bead
        elif rad > R - lead: v = 132                                                        # lead-in: smooth
        elif any(abs(rad - g) < 0.9 for g in gaps): v = 112                                # a gap between tracks
        else: v = 128 + r.randint(-26, 26)
        t.append(clamp(v))
    return t


def record(im, cx, cy, R, r_label, label_img, angle, th0, gaps, sheen, base=(0x0D, 0x0D, 0x0F), seed=7, style=None):
    """A black record at (cx, cy) radius R (1x units) into the 3x image `im`; the label (label_img turned by `angle`, PIL's sense) with its step and gloss
    and the spindle unless label_img is None (the page's base: the label is drawn at run time, the rest is vinyl_lid)."""
    size = im.size; C = (S(cx), S(cy))
    full = disc_mask(size, C[0], C[1], S(R))
    g = radial_table(size, C[0], C[1], groove_table(r_label, R, gaps, seed), S(r_label), S(R), 128)
    if style:
        paste_rgb(im, *styled_record(size, g, cx, cy, r_label, R, th0, full, style))
        return styled_label(im, cx, cy, r_label, label_img, angle, th0, C, size)
    lo, hi = scale(base, 0.6), mix(base, (90, 90, 96), 0.55)
    rec = ImageOps.colorize(g, lo, hi, mid=base)
    # the sheen: static, two lobes, grooved (the groove texture breaks it into fine rings)
    sm = angular((W, H), cx, cy, r_label + 3, R - 0.5, th0).resize(size, Image.BILINEAR)
    gc = g.point(lambda v: clamp(150 + (v - 128) * 4))
    m = ImageChops.multiply(sm, gc).point(lambda v: clamp(v * sheen))
    rec = Image.composite(Image.new('RGB', size, (240, 240, 246)), rec, m)
    wide = angular((W, H), cx, cy, r_label, R, th0 + 0.5, lobes=2, p=2, soft=0, fade=0.3).resize(size, Image.BILINEAR)   # a broad soft secondary glow
    rec = Image.composite(Image.new('RGB', size, (255, 255, 255)), rec, wide.point(lambda v: int(v * 40 * min(1.0, sheen) // 255)))
    paste_rgb(im, rec, full)
    if label_img is None: return
    lm = disc_mask(size, C[0], C[1], S(r_label))
    lab = label_img.resize((S(2 * r_label), S(2 * r_label)), Image.LANCZOS).rotate(angle, Image.BICUBIC)
    layer = Image.new('RGB', size); layer.paste(lab, (C[0] - S(r_label), C[1] - S(r_label)))
    paste_rgb(im, layer, lm)
    label_marks(im, cx, cy, r_label, th0)
    spindle(im, cx, cy)


def styled_label(im, cx, cy, r_label, label_img, angle, th0, C, size):
    if label_img is None: return
    lm = disc_mask(size, C[0], C[1], S(r_label))
    lab = label_img.resize((S(2 * r_label), S(2 * r_label)), Image.LANCZOS).rotate(angle, Image.BICUBIC)
    layer = Image.new('RGB', size); layer.paste(lab, (C[0] - S(r_label), C[1] - S(r_label)))
    paste_rgb(im, layer, lm)
    label_marks(im, cx, cy, r_label, th0)
    spindle(im, cx, cy)


def label_marks(im, cx, cy, r_label, th0):
    """The pressed step at the label's edge and a soft paper gloss: fixed (they do not turn with the label)."""
    size = im.size; C = (S(cx), S(cy))
    lm = disc_mask(size, C[0], C[1], S(r_label))
    fill(im, ring_mask(size, C[0], C[1], S(r_label - 0.8), S(r_label + 0.6)), (0, 0, 0), 120)
    lsh = angular((W, H), cx, cy, 0, r_label, th0 + 0.9, lobes=1, p=1.5, soft=0, fade=0.5).resize(size, Image.BILINEAR)
    fill(im, ImageChops.multiply(lsh, lm), (255, 255, 255), 45)


def spindle(im, cx, cy, r=4.2):
    size = im.size; C = (S(cx), S(cy))
    shadow(im, disc_mask(size, C[0], C[1], S(r)), S(1.2), S(1.6), S(1.2), 160)
    m = disc_mask(size, C[0], C[1], S(r))
    paste_rgb(im, stops(size, [(0xF4, 0xF4, 0xF6), (0x6A, 0x6C, 0x72)]), m)
    fill(im, disc_mask(size, C[0] - S(1.3), C[1] - S(1.4), S(1.4)), (255, 255, 255), 230)


def label_rim(im):
    size = im.size
    fill(im, ring_mask(size, S(REC_C[0]), S(REC_C[1]), S(LAB_R), S(LAB_R + 1.6)), T['rim'], 230)   # the label's white rim
    spindle(im, *REC_C)


def ramp_lut(stops_):
    """Piecewise linear (t, rgb, alpha) stops -> 256 entries of (r, g, b, a) floats."""
    out = []
    for t in range(256):
        k = 0
        while k < len(stops_) - 2 and t > stops_[k + 1][0]: k += 1
        (t0, c0, a0), (t1, c1, a1) = stops_[k], stops_[k + 1]
        u = min(1.0, max(0.0, (t - t0) / (t1 - t0)))
        out.append(tuple(c0[i] + (c1[i] - c0[i]) * u for i in range(3)) + (a0 + (a1 - a0) * u,))
    return out


LAST_T = [None]


def styled_record(size, g, cx, cy, r_label, R, th0, full, style):
    """A coloured / translucent record: ONE 8 bit map t (the grooves g with the static sheen screened in, both baked into a neutral luma) and a colour ramp on it
    (style['stops']: t, rgb, alpha). On the device the map is a gray picture and the ramp two 256 entry tables built when the track changes."""
    # smooth body (t = 128) + a faint groove micro-texture + the few rings that really show (track gaps, run-out, lead-in, a denser rolled rim ending a little darker,
    # a faint inner glow) + a gentle overall gradient; then the wedge sheen screened over it
    C = (S(cx), S(cy)); n = S(R) - S(r_label); tab = []
    for i in range(n):
        rad = (S(r_label) + i) / K; o = 0
        if rad < r_label + 10: o += 8                                                    # run-out: smooth and shinier
        if rad < r_label + 30: o += int(10 * (1 - (rad - r_label) / 30))                 # the faint inner glow
        if any(abs(rad - gp) < 1.0 for gp in GAPS): o += 9                               # a track gap: a thin glossier band
        if R - 6 < rad <= R - 1.3: o += 4                                                # lead-in
        if rad > R - 12: o -= int((rad - (R - 12)) / 12 * 9)                             # denser toward the rolled rim
        if rad > R - 1.3: o -= 12                                                        # the rim's edge: slightly darker, no bead (it read as a white outline)
        tab.append(clamp(128 + o))
    rings = radial_table(size, C[0], C[1], tab, S(r_label), S(R), 128)
    micro = g.point(lambda v: clamp(128 + (v - 128) * style.get('micro', 0.85)))
    grad = stops(size, [(136,) * 3, (120,) * 3]).convert('L')
    t = ImageChops.add(ImageChops.add(rings, micro, 1, -128), grad, 1, -128)
    sm = angular((W, H), cx, cy, r_label + 3, R - 0.5, th0, p=2.4, soft=0.30, fade=0.30).resize(size, Image.BILINEAR)
    wide = angular((W, H), cx, cy, r_label, R, th0 + 0.5, lobes=2, p=2, soft=0, fade=0.3).resize(size, Image.BILINEAR)
    m = ImageChops.add(sm.point(lambda v: clamp(v * style['sheen'])), wide.point(lambda v: int(v * style['glow'])))
    t = ImageChops.screen(t, m); LAST_T[0] = t
    lut = ramp_lut(style['stops'])
    rgb = Image.merge('RGB', tuple(t.point([clamp(round(e[i])) for e in lut]) for i in range(3)))
    a = t.point([clamp(round(e[3] * 255)) for e in lut])
    return rgb, ImageChops.multiply(a, full)


def cover_tint(cv, n=16):
    """The record's tint from a cover, integer arithmetic only (a C loop over a 16 x 16 grid of the 152 px cover): the mean of the pixels whose chroma (max - min) is at
    least the grid's mean chroma, weighted by chroma; then saturation clamped to [SMIN, SMAX] and value to [VMIN, VMAX] (0 .. 255) keeping the hue. Returns (r, g, b) or
    None for a (nearly) grey cover (mean chroma < 24): the record then stays black."""
    px = [cv.convert('RGB').resize((n, n), Image.BOX).getpixel((x, y)) for y in range(n) for x in range(n)]
    ch = [max(p) - min(p) for p in px]; mean = sum(ch) // len(ch)
    if mean < 24: return None
    sr = sg = sb = sw = 0
    for p, c in zip(px, ch):
        if c >= mean: sr += p[0] * c; sg += p[1] * c; sb += p[2] * c; sw += c
    r, g, b = sr // sw, sg // sw, sb // sw
    hi, lo = max(r, g, b), min(r, g, b)
    sat = (hi - lo) * 255 // max(1, hi)
    sat = max(TINT_SAT[0], min(TINT_SAT[1], sat)); val = max(TINT_VAL[0], min(TINT_VAL[1], hi))
    k = val * sat // 255                     # the new chroma; each channel keeps its place between min and max
    low = val - k; span = max(1, hi - lo)
    return tuple(low + (c - lo) * k // span for c in (r, g, b))


TINT_SAT, TINT_VAL = (170, 235), (125, 190)


def tint_style(rgb):
    """The ramp of a tinted record (the mock's, in floats): dark (0.30 x tint) in the grooves' troughs, the tint in the middle, lifted only a little towards white on the sheen (at most 0.28); opaque."""
    c = scale(rgb, 0.88)      # a little deeper than the label's colour, so the label does not merge into the record
    w = (255, 255, 255)
    return dict(micro=0.85, sheen=SHEEN_COVER, glow=GLOW_COVER, stops=[(0, scale(c, 0.30), 1.0), (118, c, 1.0), (190, mix(c, w, 0.10), 1.0), (235, mix(c, w, 0.20), 1.0), (255, mix(c, w, 0.28), 1.0)])


SHEEN_COVER, GLOW_COVER = 0.30, 0.06    # the coloured map's wedge sheen and glow (the black record's static sheen is SHEEN = 0.22)


def cover_tint_px(px, size=LAB_PX, n=16):
    """The payload's cover tint (patch/vinyl.c vn_tint, integer for integer): `px` the decoded cover, size x size (r, g, b) tuples; cell (i, j) of the n x n grid is the mean of the
    pixels [i size // n, (i + 1) size // n) x [j size // n, (j + 1) size // n). Then as cover_tint (the mock's float version): the chroma-weighted mean of the cells whose chroma
    is at least the grid's mean, saturation clamped to TINT_SAT, value to TINT_VAL. Returns (r, g, b), or None for a (nearly) grey cover."""
    cells = []
    for j in range(n):
        for i in range(n):
            xs = [(x, y) for y in range(j * size // n, (j + 1) * size // n) for x in range(i * size // n, (i + 1) * size // n)]
            cells.append(tuple(sum(px[y * size + x][c] for x, y in xs) // len(xs) for c in range(3)))
    ch = [max(p) - min(p) for p in cells]; mean = sum(ch) // len(ch)
    if mean < 24: return None
    sums = [0, 0, 0]; sw = 0
    for p, c in zip(cells, ch):
        if c >= mean:
            for k in range(3): sums[k] += p[k] * c
            sw += c
    rgb = [s // sw for s in sums]; hi, lo = max(rgb), min(rgb)
    sat = max(TINT_SAT[0], min(TINT_SAT[1], (hi - lo) * 255 // max(1, hi))); val = max(TINT_VAL[0], min(TINT_VAL[1], hi))
    k = val * sat // 255; low = val - k; span = max(1, hi - lo)
    return tuple(low + (c - lo) * k // span for c in rgb)


def tint_stops(rgb):
    """The tinted record's ramp as the payload builds it (the mock's tint_style in integers): the tint a little deeper (225 / 256) so the label does not merge into the record, dark
    (77 / 256) in the grooves' troughs, lifted a little towards white on the sheen (26, 51, 72 of 256). Five (t, (r, g, b)) stops."""
    c = [(v * 225) >> 8 for v in rgb]
    lift = lambda k: tuple(v + (((255 - v) * k) >> 8) for v in c)
    return [(0, tuple((v * 77) >> 8 for v in c)), (118, tuple(c)), (190, lift(26)), (235, lift(51)), (255, lift(72))]


# ---- the tonearm ------------------------------------------------------------------------------------------------------------
def cyl(w, h, c, spec=True):
    """A horizontal cylinder w x h (3x px): shaded across its height, light from above."""
    cols = [scale(c, 0.45), scale(c, 1.0), scale(c, 1.45) if spec else scale(c, 1.15), scale(c, 0.95), scale(c, 0.5)]
    return stops((w, h), cols)


def arm_sprite(t=None, Ls=ARM_L, bend=ARM_BEND):
    """The tonearm as one sprite, pivot at the centre (a pixel corner, n // 2), pointing +x (3x px). Returns (sprite RGBA, stylus angle offset deg, stylus distance 1x)."""
    t = t or ARM_C; tube_c, shell_c, cw_c = t['tube'], t['shell'], t['weight']
    b = math.radians(bend)
    Lt = Ls - 24 * math.cos(b)         # tube length so the stylus lands at Ls
    n = S(2 * Ls + 80); c = n // 2
    sp = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    stub = cyl(S(40), S(5), tube_c); sp.paste(stub, (c - S(40), c - S(2.5)))
    cw = cyl(S(26), S(22), cw_c, spec=True); d = ImageDraw.Draw(cw)
    for i in range(3, S(26), S(2)): d.line((i, 0, i, S(22)), fill=scale(cw_c, 0.7), width=1)   # knurled ring
    cw_m = Image.new('L', cw.size, 0); ImageDraw.Draw(cw_m).rounded_rectangle((0, 0, cw.width - 1, cw.height - 1), S(3), fill=255)
    sp.paste(cw, (c - S(62), c - S(11)), cw_m)
    tube = cyl(S(Lt), S(6), tube_c); tm = Image.new('L', tube.size, 0); ImageDraw.Draw(tm).rounded_rectangle((0, 0, tube.width - 1, tube.height - 1), S(3), fill=255)
    sp.paste(tube, (c, c - S(3)), tm)
    ex, ey = c + S(Lt), c
    du, dv = (math.cos(b), math.sin(b)), (-math.sin(b), math.cos(b))
    def P(u, v): return (ex + S(u * du[0] + v * dv[0]), ey + S(u * du[1] + v * dv[1]))
    def poly(pts, col_top, col_bot, edge=None):
        m = Image.new('L', sp.size, 0); ImageDraw.Draw(m).polygon([P(u, v) for u, v in pts], fill=255)
        bb = m.getbbox(); g = stops((bb[2] - bb[0], bb[3] - bb[1]), [col_top, col_bot])
        lay = Image.new('RGBA', sp.size, (0, 0, 0, 0)); lay.paste(g, bb[:2]); lay.putalpha(m); sp.alpha_composite(lay)
        if edge: ImageDraw.Draw(sp).line([P(u, v) for u, v in edge], fill=scale(col_top, 1.5), width=S(0.7))
    d = ImageDraw.Draw(sp)
    d.line([P(-4, 0), P(2, 0)], fill=scale(tube_c, 0.8), width=S(6))                                # the collar
    poly([(0, -5), (8, -8.5), (37, -8.5), (37, 8.5), (8, 8.5), (0, 5)], scale(shell_c, 1.5), scale(shell_c, 0.7), edge=[(8, -8.5), (37, -8.5)])
    poly([(12, -6), (33, -6), (33, 6), (12, 6)], scale(t['cart'], 1.6), scale(t['cart'], 0.6), edge=[(12, -6), (33, -6)])
    for u in (17, 28): d.ellipse(sum(((p[0] - S(1.1), p[1] - S(1.1), p[0] + S(1.1), p[1] + S(1.1)) for p in [P(u, -7.4)]), ()), fill=t['screw'])
    d.line([P(35, 6), P(45, 7), P(47, -1)], fill=scale(shell_c, 1.4), width=S(1.6))                 # finger lift
    sx, sy = P(24, 0); sx -= c; sy -= c
    return sp, math.degrees(math.atan2(sy, sx)), math.hypot(sx, sy) / K


def stylus_point(C, P, Ls, r, lower=True):
    dx, dy = C[0] - P[0], C[1] - P[1]; d = math.hypot(dx, dy)
    a = (Ls * Ls - r * r + d * d) / (2 * d); h = math.sqrt(max(0, Ls * Ls - a * a))
    mx, my = P[0] + a * dx / d, P[1] + a * dy / d
    p1, p2 = (mx + h * dy / d, my - h * dx / d), (mx - h * dy / d, my + h * dx / d)
    return max(p1, p2, key=lambda p: p[1]) if lower else min(p1, p2, key=lambda p: p[1])


_ARM = []
def arm():
    if not _ARM: _ARM.append(arm_sprite())
    return _ARM[0]


def groove_radius(p):
    """The stylus's radius on the record at track fraction p (0 .. 1): the outer groove to the inner one."""
    return REC_R - 7 - (REC_R - 7 - LAB_R - 12) * p


def arm_turn(playing, p=0.0):
    """The arm's turn in degrees (the sprite's +x direction to its stylus line; positive = clockwise on the screen): on the groove at fraction p while
    playing, parked straight down beside the record otherwise."""
    _, phi0, Lst = arm()
    if playing: S_ = stylus_point(REC_C, PIVOT, Lst, groove_radius(p), True)
    else:
        park = (PIVOT[0], PIVOT[1] + ARM_L)                  # a virtual 'record' whose edge is at the park point: aim the stylus there
        S_ = stylus_point((park[0], park[1] + 40), PIVOT, Lst, 40, True)
    return math.degrees(math.atan2(S_[1] - PIVOT[1], S_[0] - PIVOT[0])) - phi0


GROOVE_N = 32
def groove_table16():
    """patch/vinyl.c vn_groove: the arm's turn in 1/16 degree at p = i / GROOVE_N, i = 0 .. GROOVE_N (linearly interpolated by the page)."""
    return [round(arm_turn(True, i / GROOVE_N) * 16) for i in range(GROOVE_N + 1)]


def park16(): return round(arm_turn(False) * 16)


FG = [None]   # while set (an L image at 3x), the parts that are not background are added to it: the grain stays off them


def fg_add(m):
    if FG[0] is not None: FG[0] = ImageChops.lighter(FG[0], m)


def arm_base(im, t=None, P=PIVOT, base_r=BASE_R):
    t = t or ARM_C; size = im.size
    bm = disc_mask(size, S(P[0]), S(P[1]), S(base_r)); fg_add(bm)
    shadow(im, bm, S(3), S(4), S(4), 150)
    ring = radial_table(size, S(P[0]), S(P[1]), [128 + random.Random(i).randint(-30, 30) for i in range(S(base_r))], 0, S(base_r))
    paste_rgb(im, ImageOps.colorize(ring, scale(t['base'], 0.7), scale(t['base'], 1.3), mid=t['base']), bm)
    fill(im, ring_mask(size, S(P[0]), S(P[1]), S(base_r - 1), S(base_r)), (0, 0, 0), 120)
    fill(im, ring_mask(size, S(P[0]), S(P[1]), S(base_r - 6), S(base_r - 5)), (0, 0, 0), 90)


def arm_cap(im, t=None, P=PIVOT):
    """The gimbal cap (round, so it does not turn) and its shadow."""
    t = t or ARM_C; size = im.size
    cm = disc_mask(size, S(P[0]), S(P[1]), S(10))
    shadow(im, cm, S(2), S(3), S(2), 160)
    paste_rgb(im, stops(size, [scale(t['tube'], 1.5), t['tube'], scale(t['tube'], 0.55)]), cm)
    fill(im, disc_mask(size, S(P[0] - 3), S(P[1] - 3.5), S(3)), (255, 255, 255), 150)


def tonearm(im, turn):
    """The arm turned by `turn` degrees about the pivot with its shadow, then the cap (the base is arm_base, drawn before)."""
    size = im.size; P = PIVOT
    sp, _, _ = arm()
    rs = sp.rotate(-turn, Image.BICUBIC)
    a = rs.getchannel('A')
    off = (S(P[0]) - rs.width // 2, S(P[1]) - rs.height // 2)
    sh = Image.new('L', size, 0); sh.paste(a, off); fg_add(sh)
    dx, dy, blur, alpha = ARM_SHADOW
    shadow(im, sh, S(dx), S(dy), S(blur), alpha)
    im.alpha_composite(rs, off)
    arm_cap(im)


# ---- the keys ----------------------------------------------------------------------------------------------------------------
def icon(im, cx, cy, kind, u=1.0, c=(0xEE, 0xEE, 0xF0)):
    """A transport glyph drawn at 3x (cx, cy, u in 1x units): 'play', 'pause', 'prev', 'next'."""
    d = ImageDraw.Draw(im); P = lambda x, y: (S(cx + x * u), S(cy + y * u))
    if kind == 'play': d.polygon([P(-3.5, -6), P(-3.5, 6), P(6, 0)], fill=c)
    elif kind == 'pause':
        for x in (-4.5, 1.5): d.rounded_rectangle(P(x, -6) + P(x + 3, 6), S(0.6), fill=c)
    else:
        s_ = 1 if kind == 'next' else -1
        for k in (0, 1): d.polygon([P(s_ * (-6 + k * 6), -5), P(s_ * (-6 + k * 6), 5), P(s_ * (k * 6), 0)], fill=c)
        x0, x1 = sorted((S(cx + s_ * 6 * u), S(cx + s_ * 7.6 * u))); d.rectangle((x0, S(cy - 5 * u), x1, S(cy + 5 * u)), fill=c)


def round_key(im, cx, cy, r, down=False):
    """A round machined key: soft drop shadow, a fine concentric finish, a lit top rim; down = pressed in (smaller shadow, darker)."""
    size = im.size; m = disc_mask(size, S(cx), S(cy), S(r)); fg_add(m)
    shadow(im, m, 0, S(1 if down else 3), S(2 if down else 4), T['key_sh'])
    rings = radial_table(size, S(cx), S(cy), [128 + random.Random(i * 5).randint(-14, 14) for i in range(S(r))], 0, S(r))
    top = T['key'] if not down else T['key_down']
    paste_rgb(im, ImageOps.colorize(rings, scale(top, 0.8), scale(top, 1.25), mid=top), m)
    fill(im, ImageChops.subtract(m, ImageChops.offset(m, 0, S(1.2))), (255, 255, 255), T['key_hi'][0] if not down else T['key_hi'][1])
    fill(im, ImageChops.subtract(m, ImageChops.offset(m, 0, S(-1.2))), (0, 0, 0), T['key_lo'])


def transport(im, pause, pressed=None):
    """The three keys: previous, play / pause (larger: the pause glyph while playing), next; `pressed` the one drawn pressed in (its glyph 1 px lower, dimmer)."""
    for name, cx, r in KEYS:
        k = ('pause' if pause else 'play') if name == 'play' else name
        down = name == pressed
        round_key(im, cx, KEY_Y, r, down)
        icon(im, cx + (1 if k == 'play' else 0), KEY_Y + (1 if down else 0), k, 0.95 if r > 15 else 0.8, T['glyph_down'] if down else T['glyph'])


def chevron(im, x=CHEVRON[0], y=CHEVRON[1]):
    """The close chevron: 8 x 4 px, its middle on the status line's (y), in the times' grey so it sits in the plinth."""
    k, n = 3, 16   # drawn at 3x in an n px square around (x, y), reduced: antialiased
    big = Image.new('RGBA', (n * k, n * k), (0, 0, 0, 0)); h = n * k / 2
    ImageDraw.Draw(big).line((h - 4 * k, h - 2 * k, h, h + 2 * k, h + 4 * k, h - 2 * k), fill=T['chevron'], width=5, joint='curve')
    im.alpha_composite(big.resize((n, n), Image.LANCZOS), (x - n // 2, y - n // 2))


_NOISE = {}
def film_grain(im, amp, grain, seed=41):
    """Film grain at 1:1 over the whole frame: monochrome gaussian-like noise (sum of 3 uniforms), `grain` px clumps (made smaller and
    enlarged), soft-light blended so mid-greys carry it most and the blacks stay black."""
    w, h = im.size; key = (w, h, amp, grain, seed)
    if key not in _NOISE:
        gw, gh = max(2, int(w / grain)), max(2, int(h / grain)); r = random.Random(seed)
        n = Image.frombytes('L', (gw, gh), bytes(clamp(128 + (r.random() + r.random() + r.random() - 1.5) * amp * 2) for _ in range(gw * gh)))
        _NOISE[key] = Image.merge('RGB', ((n.resize((w, h), Image.BICUBIC) if grain > 1 else n),) * 3)
    return ImageChops.soft_light(im.convert('RGB'), _NOISE[key]).convert('RGBA')


# ---- the scene -------------------------------------------------------------------------------------------------------------------
def plinth(size):
    """The plinth, the arm's plate and the record's shadow (3x), the plate added to FG."""
    im = stops(size, T['grad']).convert('RGBA')
    pm = Image.new('L', size, 0); ImageDraw.Draw(pm).rounded_rectangle(tuple(S(v) for v in PLATE), S(26), fill=255); fg_add(pm)
    shadow(im, pm, 0, S(3), S(6), T['plate_sh']); paste_rgb(im, satin(size, T['plate'], 34), pm)
    fill(im, ImageChops.subtract(pm, ImageChops.offset(pm, 0, S(1.2))), (255, 255, 255), T['plate_hi'])
    sh = REC_SHADOW; shadow(im, disc_mask(size, S(REC_C[0]), S(REC_C[1]), S(REC_R)), 0, S(sh[0]), S(sh[1]), sh[2])
    return im


def finish(im):
    """3x -> 1x, the film grain on what is not in FG (the record, the plate, the arm's base, the keys stay clean)."""
    size = im.size
    out = im.resize((W, H), Image.LANCZOS)
    g = film_grain(out, *GRAIN)
    fg_add(disc_mask(size, S(REC_C[0]), S(REC_C[1]), S(REC_R)))
    return Image.composite(out, g, FG[0].resize((W, H), Image.BOX))


def design(s, f):
    """The approved mock (frames J1 / J2): the whole page at the state f (cover: a PIL image or a sample name, angle: the label's turn in PIL's
    sense, playing, pos, len, title, artist, and the status fields). s: a tools/preview_icons.Side (its font draws the text as AWTK)."""
    from tape_art import times_text
    size = (S(W), S(H)); cv = cover(f['cover']) if isinstance(f['cover'], str) else f['cover']
    FG[0] = Image.new('L', size, 0)
    try:
        im = plinth(size)
        record(im, REC_C[0], REC_C[1], REC_R, LAB_R, cv, f['angle'], TH0, GAPS, SHEEN, style=f.get('rec'))
        label_rim(im)
        arm_base(im)
        tonearm(im, arm_turn(f['playing'], f['pos'] / f['len'] if f['len'] else 0))
        transport(im, f['playing'])
        out = finish(im)
    finally:
        FG[0] = None
    chevron(out)
    text(s, out, f, status_text(f['vol'], f['fmt'], f['clock']), times_text(f['pos'], f['len']))
    return out


def text(s, out, f, status, times):
    """The page's four lines as the AWTK labels draw them (an hscroll_label that does not scroll: cut with an ellipsis to its width)."""
    t = TEXT['title']; title = s.clip(f['title'], t['px'], t['w'])
    for dx in ((0, 1) if t.get('bold') else (0,)): s.text(out, t['x'] + dx, t['y'], title, t['px'], T['text'].get('title', t['rgb']))
    for name, value in (('artist', f['artist']), ('times', times), ('status', status)):
        t = TEXT[name]; s.text(out, t['x'], t['y'], s.clip(value, t['px'], t['w']), t['px'], T['text'].get(name, t['rgb']))


def status_text(vol, fmt, clock):
    """patch/vinyl.c vn_status: 'VOL 42 | FLAC | 21:07' (no format: that part is left out). No battery: the status bar only has it in 20 % steps."""
    return ' | '.join(['VOL %d' % vol] + ([fmt] if fmt else []) + [clock])


# ---- the installed layers ------------------------------------------------------------------------------------------------------
_SCENE = {}
def scene_bare():
    """The plinth, plate, record (no label), the arm's base at 3x, and the FG mask so far (cached: every base / key image starts from it)."""
    if not _SCENE:
        size = (S(W), S(H)); FG[0] = Image.new('L', size, 0)
        try:
            im = plinth(size)
            record(im, REC_C[0], REC_C[1], REC_R, LAB_R, None, 0, TH0, GAPS, SHEEN)
            arm_base(im)
            _SCENE['im'], _SCENE['fg'] = im, FG[0]
        finally:
            FG[0] = None
    return _SCENE['im'].copy(), _SCENE['fg'].copy()


def base_frame(pause=False, pressed=None):
    """The page's background with the keys in one look (1x RGB): vinyl_base is (play glyph, nothing pressed); the key cells are crops of the others."""
    im, FG[0] = scene_bare()
    try:
        transport(im, pause, pressed)
        out = finish(im)
    finally:
        FG[0] = None
    chevron(out)
    return out.convert('RGB')


def layer(draw, rect):
    """A transparent layer: draw(im) on a 3x canvas of the whole screen, the rectangle cropped and reduced with premultiplied alpha (straight-alpha RGBA out)."""
    big = Image.new('RGBA', (S(W), S(H)), (0, 0, 0, 0)); draw(big)
    crop = big.crop(tuple(S(v) for v in rect))
    return crop.convert('RGBa').resize((rect[2] - rect[0], rect[3] - rect[1]), Image.LANCZOS).convert('RGBA')


def lid_image():
    return layer(lambda im: (label_marks(im, REC_C[0], REC_C[1], LAB_R, TH0), spindle(im, *REC_C), label_rim(im)), LID_RECT)


def cap_image():
    return layer(arm_cap, CAP_RECT)


_ARMCROP = []
def arm_crop():
    """(x0, y0, x1, y1) of the arm sprite's 3x canvas the page keeps: the arm and its shadow's reach, on 1x pixel boundaries (the pivot n // 2 is one)."""
    if not _ARMCROP:
        sp, _, _ = arm(); bb = sp.getchannel('A').getbbox(); mg = S(ARM_SHADOW[2] * 3 + 2)
        _ARMCROP.append(tuple((v - mg) // K * K if i < 2 else -(-(v + mg) // K) * K for i, v in enumerate(bb)))
    return _ARMCROP[0]


def arm_geometry():
    """(w, h, pivot x, pivot y) of vinyl_arm in 1x px (the pivot a pixel corner)."""
    x0, y0, x1, y1 = arm_crop(); c = arm()[0].width // 2
    assert c % K == 0 and x0 % K == 0 and y0 % K == 0
    return (x1 - x0) // K, (y1 - y0) // K, (c - x0) // K, (c - y0) // K


def arm_image():
    sp = arm()[0].crop(arm_crop()); w, h, _, _ = arm_geometry()
    return sp.convert('RGBa').resize((w, h), Image.LANCZOS).convert('RGBA')


def armsh_image():
    sp = arm()[0].crop(arm_crop()); w, h, _, _ = arm_geometry()
    _, _, blur, alpha = ARM_SHADOW
    a = sp.getchannel('A').point(lambda v: v * alpha // 255).filter(ImageFilter.GaussianBlur(S(blur))).resize((w, h), Image.BOX)
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0)); out.putalpha(a)
    return out


def keys_image():
    """vinyl_keys: KEY_CELLS cut from the band of the base in each look."""
    sheet = Image.new('RGBA', KEY_SHEET, (0, 0, 0, 255))
    y0, y1 = BAND_Y
    for (name, state), sx in KEY_CELLS.items():
        im = base_frame(pause=bool(state & 1) if name == 'play' else False, pressed=name if state & 2 else None)
        x0, x1 = KEY_COLS[name]
        sheet.paste(im.crop((x0, y0, x1, y1)).convert('RGBA'), (sx, 0))
    return sheet


def label_image():
    return fallback_label().convert('RGBA')


# ---- the Cover record (the Record setting; docs/modules/vinyl.md "Record colours") ---------------------------------------------------------------
REC_BOX = (0, REC_C[1] - REC_R, REC_C[0] + REC_R, REC_C[1] + REC_R)   # the record's box on the screen: (0, 34, 258, 358); the record runs off the left edge
RECORD_NAMES = ('black', 'cover')       # the saved index (Settings > Now Playing > Record); black is the installed base as it is
RECORD_STOPS_T = (0, 118, 190, 235, 255)   # the ramp's stops are at these map values
REC_EDGE_K = 15                         # the black record's grey at its rim (0 .. 255), as in vinyl_base just inside the edge: what the edge pixels of the coloured disc replace


def ramp_table(stops_):
    """The payload's 256 entry colour table of a ramp from 5 integer stops (t, (r, g, b)): piecewise linear, rounded half up."""
    out = []
    for t in range(256):
        k = 0
        while k < len(stops_) - 2 and t > stops_[k + 1][0]: k += 1
        (t0, c0), (t1, c1) = stops_[k], stops_[k + 1]; d = t1 - t0
        out.append(tuple((c0[i] * (t1 - t) + c1[i] * (t - t0) + d // 2) // d for i in range(3)))
    return out


def rec_in_map(x, y):
    """Is the screen pixel (x, y) one the record map holds: outside the label's circle (the label covers it) and where the record's rim covers it at all."""
    vx, vy = 2 * (x - REC_C[0]) + 1, 2 * (y - REC_C[1]) + 1; d2 = vx * vx + vy * vy
    return 4 * LAB_IN * LAB_IN < d2 < (2 * REC_R + 1) ** 2


def record_map():
    """vinyl_rec: L, REC_BOX, the record's one 8 bit map t (grooves, gaps, a darker rim and the weak static sheen baked into a luma; the colour ramp runs on it), 0 where the page leaves the base
    alone (rec_in_map false), else 1 .. 255. The page makes the pixels inside the rim by the ramp, and the rim's own pixels by adding the ramp's difference from the black record's rim
    (REC_EDGE_K) to the base's, by the disc's coverage: the base already holds the theme's plinth and the record's shadow there, so the picture carries no plinth."""
    size = (S(W), S(H)); C = (S(REC_C[0]), S(REC_C[1]))
    g = radial_table(size, C[0], C[1], groove_table(LAB_R, REC_R, GAPS, 7), S(LAB_R), S(REC_R), 128)
    styled_record(size, g, REC_C[0], REC_C[1], LAB_R, REC_R, TH0, disc_mask(size, C[0], C[1], S(REC_R)), tint_style((128, 128, 128)))
    x0, y0, x1, y1 = REC_BOX
    t = LAST_T[0].resize((W, H), Image.BOX).crop(REC_BOX); px = bytearray(t.tobytes())
    for y in range(y1 - y0):
        for x in range(x1 - x0):
            px[y * (x1 - x0) + x] = max(1, px[y * (x1 - x0) + x]) if rec_in_map(x + x0, y + y0) else 0
    return Image.frombytes('L', t.size, bytes(px))


def rec_image():
    """vinyl_rec as installed: RGBA with the map in R (G, B 0, A 255: the device's decoder gives 32 bit pixels for every picture the payload loads)."""
    m = record_map(); z = Image.new('L', m.size, 0)
    return Image.merge('RGBA', (m, z, z, Image.new('L', m.size, 255)))


THEMED = ('vinyl_base', 'vinyl_lid', 'vinyl_arm', 'vinyl_armsh', 'vinyl_cap', 'vinyl_keys')   # the pictures a plinth theme changes
SHARED = ('vinyl_label', 'vinyl_rec')                                                           # the same under every theme


def tname(name, theme='graphite'):
    """The installed picture of a layer under a theme: Graphite's keep their names (byte for byte what V2.1qD installed), the others' end in _<theme>."""
    return name if theme == 'graphite' else '%s_%s' % (name, theme)


NAMES = tuple(tname(n, t) for t in THEME_NAMES for n in THEMED) + SHARED


def text_rgb(field, theme='graphite'):
    """The colour of the page's text labels (title, artist, times, status) under a theme."""
    return THEMES[theme].get('text', {}).get(field, TEXT[field]['rgb'])


def window_bg(theme='graphite'):
    """The window's own background (the view hides it): the theme's plinth middle."""
    th = dict(GRAPHITE, **THEMES[theme])
    return (0x46, 0x46, 0x48) if theme == 'graphite' else th['grad'][2]   # (Graphite's is the page asset V2.1qD installed)


def images():
    """name -> PIL image of every installed Vinyl picture (RGBA: the device's decoder gives 32 bit pixels for every picture the payload loads)."""
    out = {}
    try:
        for th in THEME_NAMES:
            use(th)
            for n, im in zip(THEMED, (base_frame().convert('RGBA'), lid_image(), arm_image(), armsh_image(), cap_image(), keys_image())): out[tname(n, th)] = im
    finally:
        use('graphite')
    out['vinyl_label'], out['vinyl_rec'] = label_image(), rec_image()
    return out


if __name__ == '__main__':
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))   # (-I drops the script's directory)
    import png_pack
    for n, im in images().items(): open(os.path.join(out, n + '.png'), 'wb').write(png_pack.pack(im)); print(n, im.size)
    print('arm', arm_geometry(), 'groove', groove_table16(), 'park', park16(), 'text', {t: [text_rgb(f, t) for f in ('title', 'artist', 'times', 'status')] for t in THEME_NAMES})
