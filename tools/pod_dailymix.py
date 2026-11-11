#!/usr/bin/env python3
"""The Daily Mix hero card of the menu's Home instance (docs/modules/dailymix.md): geometry, the art generator and the text fitting. The device
code is patch/dailymix.c; tools/pod_ui.py builds the widgets from these DM_* numbers (patch/offsets.inc carries the same ones, test/pod/dailymix.py
asserts it), tools/preview/preview_dailymix.py draws the card, test/pod/dailymix.py checks it and runs the compiled code against this file. The texts are in
tools/pod_i18n.py (`TEXT` here is those five keys).

The art is a pure function of (tones, seed): 2 to 4 RGB tones -> a 296 x 220 RGB image, integer arithmetic only (patch/dailymix.c mirrors it line by
line and the test compares the pixels): vivid tones over a dark base, large soft blobs (compact quadratic falloff, no exp), a vertical scrim just
strong enough that the text on it reaches DM_CONTRAST, RGB565 quantisation with a 4 x 4 ordered dither.
"""
import argparse

# ---- geometry (section-local px; the section is a child of the Home list's 310 px scroll view, above the Recently Played shelf) -------------
DM_W_VIEW = 310                       # the scroll view's width (SH_W)
DM_X, DM_W, DM_H, DM_R = 12, 296, 220, 12     # the card: the shelf's two covers span x 12..308 (GRID_MARGIN, 2 x 144 + GRID_GAP 8)
DM_BUSY_PX, DM_BUSY_GAP = 16, 6                                  # the busy mark pod_dm_busy: the sync glyph's 16 px canvas (about 14 px of ink, near the list chevron's 16 px height), 6 px clear of the header text
DM_BUSY_X = 293 - DM_BUSY_PX // 2                                  # 285: centred on the list chevron's ink (pod_ui CHEV_X 288, 10 px glyph: x 288..298) above it
DM_HEAD_TOP, DM_HEAD_H, DM_HEAD_PX, DM_HEAD_X = 17, 22, 20, 10     # the shelf's header (SH_HEAD_*), but narrower: it stops before the busy mark
DM_HEAD_W = DM_BUSY_X - DM_BUSY_GAP - DM_HEAD_X                    # 269 (the shelf's is 300)
DM_BUSY_Y = DM_HEAD_TOP + (DM_HEAD_H - DM_BUSY_PX) // 2              # 20: the canvas centred on the header's text line
DM_TOP = DM_HEAD_TOP + DM_HEAD_H + 5          # 44: the card's top (SH_TOP)
DM_BOTTOM = 8                                 # air under the card; the Recently Played header's ink is 20 px into its section, so 28 px between card and header ink
DM_SEC_H = DM_TOP + DM_H + DM_BOTTOM          # 272
DM_PAD = 18                                   # text inset from the card's left edge
DM_TITLE_PX, DM_TITLE_PITCH = 36, 38          # the two title lines (label boxes DM_TITLE_PITCH high, text middle-aligned)
DM_SUB_PX, DM_SUB_PITCH, DM_SUB_LINES = 16, 20, 2
DM_BOT_PAD = 16                               # bottom of the artist lines' box to the card's bottom
DM_SUB_Y = DM_H - DM_BOT_PAD - DM_SUB_LINES * DM_SUB_PITCH          # 164
DM_TITLE_GAP = 4
DM_TITLE_Y2 = DM_SUB_Y - DM_TITLE_GAP - DM_TITLE_PITCH               # 122: the second (bottom) title line's box
DM_TITLE_Y1 = DM_TITLE_Y2 - DM_TITLE_PITCH                           # 84
DM_DISC, DM_DISC_PAD = 48, 14                                        # the glass play disc (touch target = the disc, 48 >= 44), 14 px from the right and bottom edges
DM_DISC_X, DM_DISC_Y = DM_W - DM_DISC_PAD - DM_DISC, DM_H - DM_DISC_PAD - DM_DISC     # 234, 158
DM_SUB_W = DM_DISC_X - 12 - DM_PAD            # 204: the artist lines stay 12 px clear of the disc
DM_TITLE_W = DM_W - 2 * DM_PAD                # 260
DM_PLAY_GLYPH = 22
DM_MAX_NAMES = 3                              # "Radiohead, Björk, Air and more": at most three names (Apple's), fewer when they do not fit
TITLE_RGB, SUB_RGB = (255, 255, 255), (0xEB, 0xEB, 0xEB)
DM_CONTRAST = 4.5                             # WCAG AA for normal text; the generator aims at DM_AIM so dither and rounding cannot take it below
DM_AIM = 4.7
ZONE_Y = DM_TITLE_Y1                          # the rows from here down carry text: the scrim is at full strength from here
RAMP = 110                                    # the scrim fades in over the RAMP rows above ZONE_Y (a long ramp: no visible edge)
L_MIN, L_MAX, L_MAX_GREY = 30, 56, 66         # HLS lightness bounds of a prepared tone, in percent

# ---- the texts (tools/pod_i18n.py TEXT: key = the English text, one entry per locale; the card's five keys) ----------------------------------
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pod_i18n
from pod_mix import xorshift32
LOCALES = pod_i18n.LOCALES
TEXT = {k: pod_i18n.TEXT[k] for k in pod_i18n.DAILY_KEYS}


def tr(loc, key): return TEXT[key][loc]


# ---- the art generator --------------------------------------------------------------------------------------------------------------------
def tone_prep(rgb):
    """A cover's tone made card-ready, in integers (patch/dailymix.c dm_prep is this line by line). HLS with lightness l2 = max + min (0..510) and
    chroma d = max - min: a colourful tone (saturation d / min(l2, 510 - l2) above 0.10) gets at least 0.55 saturation and a lightness in
    [0.30, 0.56]; a grey one a lightness in [0.25, 0.66] and its saturation kept. Pale covers do not wash the card out, dark ones do not vanish,
    greys stay grey. The channels keep their place between min and max (the hue), so the new colour is min' + (c - min) * d' / d."""
    mx, mn = max(rgb), min(rgb)
    d, l2 = mx - mn, mx + mn
    den = min(l2, 510 - l2)
    colourful = d * 10 > den                       # d > 0 and saturation > 0.10 (den 0 only for pure black / white: d is 0 then)
    lo, hi = (L_MIN, L_MAX) if colourful else (25, L_MAX_GREY)
    l2n = min(max(l2, lo * 510 // 100), (hi * 510 + 99) // 100)     # 0.30 -> 153, 0.56 -> 286 (rounded up), 0.25 -> 127, 0.66 -> 337
    denn = min(l2n, 510 - l2n)
    if d == 0: return (l2n // 2,) * 3
    dn = d * denn // den
    if colourful: dn = max(dn, 55 * denn // 100)
    mnn = (l2n - dn) // 2
    return tuple(mnn + ((c - mn) * dn * 2 + d) // (2 * d) for c in rgb)


def lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


LIN = [lin(i) for i in range(256)]
LIN16 = [round(v * 65535) for v in LIN]       # the sRGB -> linear table of the device (patch/dailymix.c dm_lin), 16 bit; `pod_dailymix.py --c-table` prints it


def luminance(rgb): return 0.2126 * LIN[rgb[0]] + 0.7152 * LIN[rgb[1]] + 0.0722 * LIN[rgb[2]]


def lum16(rgb):
    """Relative luminance in 16 bit fixed point, integers only (what the art generator decides with)."""
    return (2126 * LIN16[rgb[0]] + 7152 * LIN16[rgb[1]] + 722 * LIN16[rgb[2]]) // 10000


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    if la < lb: la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def dim_limit(ink):
    """The brightest background luminance (16 bit) that keeps DM_AIM:1 under `ink`: (Li + 0.05) / (Lb + 0.05) >= 4.7  <=>  Lb <= (Li + 0.05) / 4.7 - 0.05."""
    return (lum16(ink) + 3277) * 10 // 47 - 3277


BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))


def blobs(tones, seed, w=DM_W, h=DM_H):
    """[(cx, cy, R, rgb, strength/256)] for the prepared tones: blob i sits in the i-th of n horizontal sectors, jittered by the seed's xorshift32
    stream (cx +-0.25 sector, cy 12..62 % of the height: the text sits in the lower half), radius 0.62..0.92 of the width."""
    n = len(tones)
    st = seed & 0xFFFFFFFF or 0x9E3779B9
    out = []
    for i, t in enumerate(tones):
        st = xorshift32(st); a = st
        st = xorshift32(st); b = st
        st = xorshift32(st); c = st
        cx = (2 * i + 1) * w // (2 * n) + ((a & 0xFFFF) - 0x8000) * (w // n) // (4 * 0x8000)
        cy = h * 12 // 100 + (b & 0xFFFF) * (h * 50 // 100) // 0x10000
        R = w * 62 // 100 + (c & 0xFFFF) * (w * 30 // 100) // 0x10000
        out.append((cx, cy, R, t, 240))
    return out


def field(tones, seed, w=DM_W, h=DM_H):
    """The blob field before the scrim: rows of (r, g, b). base = the darkest tone at half lightness (its hue kept); each blob over it with alpha
    = strength * (1 - d^2 / R^2)^2 (zero beyond R)."""
    prep = [tone_prep(t) for t in tones]
    dark = min(prep, key=lum16)
    base = tuple(dark[i] * 5 // 10 for i in range(3))
    bl = blobs(prep, seed, w, h)
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            r, g, b = base
            for cx, cy, R, t, k in bl:
                d2 = (x - cx) ** 2 + (y - cy) ** 2; R2 = R * R
                if d2 >= R2: continue
                q = 256 - 256 * d2 // R2               # 0..256
                a = k * (q * q >> 8) >> 8              # 0..k
                r += (t[0] - r) * a >> 8; g += (t[1] - g) * a >> 8; b += (t[2] - b) * a >> 8
            row.append((r, g, b))
        rows.append(row)
    return rows


def scrim_alpha(y, a64):
    """The scrim: 0 at ZONE_Y - RAMP, smoothstep up to a64/64 at ZONE_Y and below."""
    t = (y - (ZONE_Y - RAMP)) * 256 // RAMP
    t = 0 if t < 0 else 256 if t > 256 else t
    s = t * t * (768 - 2 * t) >> 16            # smoothstep t^2 (3 - 2t), 0..256
    return s * a64 // 64                       # 0..256 * a64/64 -> /256 alpha


def quantise_channel(c, t, bits):
    step = 256 >> bits
    v = min(255, max(0, c + (t * step - 15 * step // 2) // 16))
    q = v >> (8 - bits)
    return (q << (8 - bits)) | (q >> (2 * bits - 8))


# quantise_channel by Bayer value and channel value 0..511 (the page fade's half step can lift a channel past 255): quantise clamps into it,
# render_rows indexes directly (its scrim only darkens a 0..255 channel)
Q5, Q6 = ([[quantise_channel(c, t, bits) for c in range(512)] for t in range(16)] for bits in (5, 6))


def quantise(px, x, y):
    t = BAYER[y & 3][x & 3]
    return tuple(q[min(511, max(0, c))] for q, c in zip((Q5[t], Q6[t], Q5[t]), px))   # clamped as quantise_channel would


def render_rows(f, a64, w=DM_W, h=DM_H):
    rows = []
    for y in range(h):
        a = scrim_alpha(y, a64); bayer = BAYER[y & 3]; fy = f[y]; row = []
        for x in range(w):
            r, g, b = fy[x]; t = bayer[x & 3]
            row.append((Q5[t][r - (r * a >> 8)], Q6[t][g - (g * a >> 8)], Q5[t][b - (b * a >> 8)]))
        rows.append(row)
    return rows


def zone_contrast(rows, ink, y0=ZONE_Y):
    return min(contrast(ink, px) for row in rows[y0:] for px in row)


def zone_dim(rows, y0=ZONE_Y):
    """The brightest luminance (16 bit) in the text zone of rendered rows."""
    return max(lum16(px) for row in rows[y0:] for px in row)


def art(tones, seed, w=DM_W, h=DM_H):
    """(rows, scrim a64): the card's art as rows of (r, g, b) at RGB565 precision, and the scrim strength chosen (in 1/64). The strength is the least
    (at least 10/64) that gives the text zone DM_AIM:1 for the dimmer of the two inks, found from the brightest pixel then verified on every pixel.
    Integers only: the decisions use lum16 and dim_limit (patch/dailymix.c does the same, test/pod/dailymix.py compares the pixels)."""
    f = field(tones, seed, w, h)
    ink = min((TITLE_RGB, SUB_RGB), key=lum16)
    limit = dim_limit(ink)
    bright = max((px for row in f[ZONE_Y:] for px in row), key=lum16)
    a64 = 10
    while a64 < 52 and lum16(tuple(c - (c * (256 * a64 // 64) >> 8) for c in bright)) > limit: a64 += 1
    while True:
        rows = render_rows(f, a64, w, h)
        if zone_dim(rows) <= limit or a64 >= 56: return rows, a64
        a64 += 1


# ---- the card's rounded corners (patch/grid.c grid_round, patch/common.c m1_corner_fill) ----------------------------------------------------
def corner_cover(r):
    """The coverage (0..255) outside a quarter circle of radius r in the r x r corner square: each pixel sampled 8 x 8 (m1_corner_fill)."""
    c, tab = 2 * 8 * r, []
    for y in range(r):
        for x in range(r):
            n = sum((2 * (x * 8 + i) + 1 - c) ** 2 + (2 * (y * 8 + j) + 1 - c) ** 2 > c * c for i in range(8) for j in range(8))
            tab.append((n * 255 + 32) // 64)
    return tab


def div255(t): return (t + 1 + (t >> 8)) >> 8


def round_corners(rows, r=DM_R):
    """The four corners blended into black as the device does once per bitmap: each channel times (255 - coverage) / 255 (grid_round). In place."""
    tab, h, w = corner_cover(r), len(rows), len(rows[0])
    for k in range(4):
        for y in range(r):
            for x in range(r):
                a = 255 - tab[y * r + x]
                if a == 255: continue
                py, px = (h - 1 - y if k & 2 else y), (w - 1 - x if k & 1 else x)
                rows[py][px] = tuple(div255(v * a) for v in rows[py][px])
    return rows


def rgb565(px):
    """The RGB565 word of an art pixel (an 8 bit value that is already a 565 value expanded)."""
    return (px[0] >> 3) << 11 | (px[1] >> 2) << 5 | px[2] >> 3


def expand565(v):
    r, g, b = v >> 11 & 31, v >> 5 & 63, v & 31
    return (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2)


def to_image(rows):
    from PIL import Image
    h, w = len(rows), len(rows[0])
    im = Image.new('RGB', (w, h)); im.putdata([px for row in rows for px in row])
    return im


# ---- text ---------------------------------------------------------------------------------------------------------------------------------
def cjk(ch): o = ord(ch); return 0x2E80 <= o <= 0xFFEF or 0x0E00 <= o <= 0x0E7F or 0xAC00 <= o <= 0xD7AF


def atoms(text):
    """Break units: a run of non-space, non-CJK characters, or one CJK / Thai / Hangul character, each with the space (if any) that follows."""
    out, cur = [], ''
    for ch in text:
        if ch == ' ':
            out.append(cur + ' '); cur = ''
        elif cjk(ch):
            if cur: out.append(cur); cur = ''
            out.append(ch)
        else:
            cur += ch
    if cur: out.append(cur)
    return out


def wrap(width, text, room, max_lines):
    """Greedy wrap of `text` into lines of at most `room` px (width(text) is the AWTK width); None when more than max_lines would be needed
    or a unit is wider than the room."""
    lines, cur = [], ''
    for a in atoms(text):
        if width((cur + a).rstrip()) <= room: cur += a
        elif not cur or width(a.rstrip()) > room: return None
        else:
            lines.append(cur.rstrip()); cur = a
    if cur: lines.append(cur.rstrip())
    return lines if len(lines) <= max_lines else None


def ellipsize(width, text, room):
    while width(text) > room and len(text) > 1: text = text[:-2] + '…' if text.endswith('…') else text[:-1] + '…'
    return text


def join_names(loc, names):
    """The names joined by the locale's two-name template ('%s, %s'; '%s、%s' in Chinese and Japanese), one name after the other."""
    out = names[0]
    for n in names[1:]: out = tr(loc, '%s, %s') % (out, n)
    return out


def artist_lines(width, names, loc, room=DM_SUB_W, max_lines=DM_SUB_LINES):
    """The top-artists line as lines: the most names (in order) whose '<name, name, ...> and more' wraps into max_lines lines of `room` px; if not even
    one name does, the first name alone, cut with an ellipsis on the last line. The device tries n = 5 down to 1 (width of a candidate, wrap)."""
    tpl = tr(loc, '%s and more')
    for n in range(min(len(names), DM_MAX_NAMES), 0, -1):
        lines = wrap(width, tpl % join_names(loc, names[:n]), room, max_lines)
        if lines: return lines
    lines = wrap(width, tpl % names[0], room, 10_000) or [names[0]]
    lines = lines[:max_lines]
    lines[-1] = ellipsize(width, lines[-1] + '…', room)
    return lines


def title_lines(text):
    """The card title as the card shows it: split at the first space into two lines; a title with no space is one line, on the bottom line's box."""
    a, sp, b = text.partition(' ')
    return [a, b] if sp else [text]


# ---- the detail page (docs/modules/dailymix.md "The page"; patch/dailymix.c dp_*, patch/offsets.inc DP_*) -------------------------------------
# An Apple Music playlist page: full-bleed art from the window top (DP_ART_H high, its foot DP_FADE px fading into the page's solid tint), a glass back disc,
# the centred title lines, the Shuffle disc + white Play pill, a description, then the songs as 64 px rows. All numbers are window / content px (the content
# view is 320 wide and starts at the window top; the list is the whole 450 px window).
DP_W, DP_ART_H, DP_FADE, DP_HOLD = 320, 180, 60, 4                  # the art, the rows of its foot that fade into the tint, and the last rows that are the tint's own word
DP_VIEW_H = 450
DP_BACK_BTN, DP_BACK_X, DP_BACK_Y, DP_BACK_DISC = 44, 8, 8, 40       # the back button (touch) and the glass disc drawn centred in it
DP_TEXT_X, DP_TEXT_W = 16, 288                                       # the centred lines and the description: 16 px margins
DP_TITLE_PX, DP_SUB_PX, DP_UPD_PX, DP_DESC_PX = 24, 17, 14, 15
DP_OUTER, DP_GAP = 16, 9                                             # ink gaps (the album page's, docs/modules/album-page.md): outer 16, between text lines 9
DP_DESC_PITCH, DP_DESC_LINES, DP_DESC_BELOW = 20, 2, 14
DP_BTN_H, DP_PILL_H, DP_PLAY_W, DP_DISC, DP_BTN_GAP = 44, 40, 148, 40, 12   # the buttons: touch 44 high, drawn pill 148 x 40, discs 40, 12 apart (Shuffle | Play | Add, symmetric about x 160)
DP_SHUF_W = 44                                                       # the Shuffle touch rectangle (the disc 40 centred in it)
DP_PILL_GLYPH, DP_PILL_GAP = 16, 8                                   # the pill's play glyph and the gap to its text
DP_TITLE_Y, DP_SUB_Y, DP_UPD_Y, DP_BTN_Y, DP_DESC_Y = 193, 218, 239, 263, 317    # page_layout(font) on the shipped font (test/pod/dmpage.py asserts it); patch/offsets.inc has the same
DP_SHUF_X, DP_PLAY_X = 32, 86                                        # the Shuffle touch rectangle and the pill: 40 + 12 + 148 + 12 + 40 = 252 px centred on x 160 (drawn 34 .. 286)
DP_ADD_X, DP_ADD_W = 244, 44                                         # the Add disc's touch rectangle: the Shuffle one mirrored about x 160 (DP_SHUF_X + DP_ADD_X + DP_ADD_W = 320)
DP_ROWS_Y = DP_DESC_Y + DP_DESC_LINES * DP_DESC_PITCH + DP_DESC_BELOW    # 371: the first song's row (the description is two lines' high in every language, so the rows never move)
DP_PILL_INK = 0x141414                                               # the pill's text colour #141414 as r | g << 8 | b << 16 (the glyph is the album page's image ah_play, the same ink AH_PLAY_INK)
DP_BOTTOM = 16                                                       # air under the last row
DP_V_MIN = 48                                                        # the tint's brightest channel is at least this (never near black)
DP_LUM_MAX = 4588                                                    # ... and its luminance (16 bit, 0.07) at most: white text 8.7:1, the greys below 4.5:1
DP_GREY_K, DP_ACC_K = 184, 208                                       # the artist / description grey and the "Updated" accent: the tint + (255 - tint) * k / 256


def snap565(rgb):
    """An 8 bit colour as the 16 bit panel shows it (truncated to 565 and expanded): the tint is chosen on this grid so the art's last row and the window colour are the same word."""
    return expand565(rgb565(rgb))


def tint_of(avg):
    """The page's solid tint from the art's last row average (integers, patch/dailymix.c dp_tint): lifted to a brightest channel of DP_V_MIN, darkened by 15/16 steps until
    its luminance is at most DP_LUM_MAX, then snapped to 565."""
    v = max(avg)
    if v < DP_V_MIN: avg = (DP_V_MIN,) * 3 if v == 0 else tuple(DP_V_MIN * c // v for c in avg)
    while lum16(snap565(avg)) > DP_LUM_MAX: avg = tuple(c * 15 >> 4 for c in avg)      # (the snap can lift a channel by a few levels: the cap is checked on what the panel shows)
    return snap565(avg)


def pale(tint, k):
    """The tint lightened towards white by k / 256 (the grey of the artist and description lines, the accent of the Updated line)."""
    return tuple(c + ((255 - c) * k >> 8) for c in tint)


def page_colours(tint):
    """(grey, accent) over the tint."""
    return pale(tint, DP_GREY_K), pale(tint, DP_ACC_K)


def fade_alpha(y):
    """The fade into the tint on art row y (0..256): 0 above DP_ART_H - DP_FADE, a smoothstep reaching 256 DP_HOLD rows before the end (the last rows are the tint itself)."""
    t = (y - (DP_ART_H - DP_FADE) + 1) * 256 // (DP_FADE - DP_HOLD)
    t = 0 if t < 0 else 256 if t > 256 else t
    return t * t * (768 - 2 * t) >> 16


def page_art(tones, seed):
    """(rows of (r, g, b) at RGB565 precision, tint): DP_W x DP_ART_H art from the same blobs as the card (same seed, so the same layout scaled), no scrim and no text, the
    foot faded into the tint, which is made from the field's last row. Rows with the fade complete are the tint's own 565 word (no dither)."""
    f = field(tones, seed, DP_W, DP_ART_H)
    last = f[DP_ART_H - 1]
    tint = tint_of(tuple(sum(px[i] for px in last) // DP_W for i in range(3)))
    rows = []
    for y in range(DP_ART_H):
        s = fade_alpha(y)
        if s >= 256: rows.append([tint] * DP_W); continue
        rows.append([quantise(tuple(c + ((t - c) * s >> 8) + h for c, t, h in zip(f[y][x], tint, (4 * s + 128 >> 8, 2 * s + 128 >> 8, 4 * s + 128 >> 8))), x, y) for x in range(DP_W)])   # + up to half a step as the fade completes: the 565 floor would otherwise leave the faded rows darker than the tint
    return rows, tint


def page_layout(f):
    """The page's vertical numbers from the measured ink (tools/ah_ink.py, the album page's method: a gap runs from the capitals' top to the line above's baseline):
    {title, sub, upd: (y, h), btn_y, desc_y}. The label rects are their font size high (the line box centred in them), the buttons' touch rectangles DP_BTN_H high."""
    import ah_ink
    out, prev, gap = {}, DP_ART_H, DP_OUTER
    for key, px in (('title', DP_TITLE_PX), ('sub', DP_SUB_PX), ('upd', DP_UPD_PX)):
        want = prev + gap
        y = want + ah_ink.cap(f, px) - f.baseline(px) - 0
        out[key] = (y, px)
        prev, gap = ah_ink.baseline(f, px, y, px), DP_GAP
    out['btn_y'] = prev + DP_OUTER - (DP_BTN_H - DP_PILL_H) // 2
    pill_bottom = out['btn_y'] + (DP_BTN_H - DP_PILL_H) // 2 + DP_PILL_H
    out['desc_y'] = pill_bottom + DP_OUTER + ah_ink.cap(f, DP_DESC_PX) - f.baseline(DP_DESC_PX) - (DP_DESC_PITCH - DP_DESC_PX) // 2
    return out


def civil(days):
    """The (year, month, day) of a day number since 1970-01-01 (patch/dailymix.c dp_civil): Howard Hinnant's algorithm in integers."""
    z = days + 719468
    era = z // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    return y + (m <= 2), m, d


def c_table():
    """patch/dailymix.c's dm_lin as C source (16 values a line)."""
    rows = [', '.join(f'{v}' for v in LIN16[i:i + 16]) for i in range(0, 256, 16)]
    return 'static const unsigned short dm_lin[256] = {\n    ' + ',\n    '.join(rows) + '\n};'


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Daily Mix art generator helpers')
    ap.add_argument('--c-table', action='store_true', help='print the sRGB -> linear table patch/dailymix.c carries')
    ap.add_argument('--page-layout', metavar='WORKDIR', help='print the detail page\'s vertical numbers measured on the tree\'s font (patch/offsets.inc DP_*)')
    a = ap.parse_args()
    if a.c_table: print(c_table())
    if a.page_layout:
        import ah_ink
        print(page_layout(ah_ink.font(a.page_layout)))
