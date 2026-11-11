#!/usr/bin/env python3
"""The preset page's model (patch/peqpage.c, docs/modules/peq.md "Preset page"): the response of a preset's bands at 48 kHz, the graph card's pixels and the band rows' texts, in Python.

tools/preview_peqpage.py draws the page from it and test/pod/peq.py checks the payload against it (the response there is the test's own RBJ model, so the two agree only if the payload does):
the graph's bitmap pixel by pixel, the curve against peq_response, every string. A band is (enabled, type, frequency, gain, q): enabled 1 both sides, 2 left, 3 right, 0 off (kept in the record, never played: the page leaves it out); type 0 peak, 1 low shelf,
2 high shelf (patch/peq.h).
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pod_settings as ST
import tenband_model as TBM

RATE = 48000
W, H, CARD_X, CARD_R = 300, ST.GRAPH_H, ST.CM, ST.CARD_R
PX0, PW, PY0, PH, DECADE = 36, 249, 9, 138, 83     # patch/offsets.inc GR_*
GRID_X = (58, 141, 224)                            # 100 Hz, 1 kHz, 10 kHz: DECADE * log10(f / 20), rounded
GREY_CARD, GREY_GRID, GREY_ZERO, GREY_INK = 28, 48, 62, 242
MINUS, DOT = '−', ' · '


def design(t, f, g, q, rate=RATE):
    """patch/peq.c peq_compile: one RBJ biquad (b0, b1, b2, a1, a2)."""
    a, w = 10 ** (g / 40), 2 * math.pi * f / rate
    c, alpha = math.cos(w), math.sin(w) / (2 * q)
    r = 2 * math.sqrt(a) * alpha
    if t == 0: b0, b1, b2, a0, a1, a2 = 1 + alpha * a, -2 * c, 1 - alpha * a, 1 + alpha / a, -2 * c, 1 - alpha / a
    elif t == 1:
        b0, b1, b2 = a * ((a + 1) - (a - 1) * c + r), 2 * a * ((a - 1) - (a + 1) * c), a * ((a + 1) - (a - 1) * c - r)
        a0, a1, a2 = (a + 1) + (a - 1) * c + r, -2 * ((a - 1) + (a + 1) * c), (a + 1) + (a - 1) * c - r
    else:
        b0, b1, b2 = a * ((a + 1) + (a - 1) * c + r), -2 * a * ((a - 1) + (a + 1) * c), a * ((a + 1) + (a - 1) * c - r)
        a0, a1, a2 = (a + 1) - (a - 1) * c + r, 2 * ((a - 1) - (a + 1) * c), (a + 1) - (a - 1) * c - r
    return b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0


def left_db(bands, f):
    """10 log10 |H|^2 of the left channel (no preamp, no balance) at f: peq_response. A band of gain 0 is the identity (the engine skips it)."""
    w = 2 * math.pi * f / RATE
    z1, z2 = complex(math.cos(w), -math.sin(w)), complex(math.cos(2 * w), -math.sin(2 * w))
    p = 1.0
    for e, t, fc, g, q in bands:
        if not e or not g or fc >= RATE / 2 or e == 3: continue
        b0, b1, b2, a1, a2 = design(t, fc, g, q)
        p *= abs((b0 + b1 * z1 + b2 * z2) / (1 + a1 * z1 + a2 * z2)) ** 2
    return 10 * math.log10(p)


def curve(bands):
    """(dB per column, range): one frequency per pixel column, 20 Hz * 10^((c + 0.5) / DECADE); the range 12, 18 or 24 dB, the first that holds the curve."""
    db = [left_db(bands, 20 * 10 ** ((c + 0.5) / DECADE)) for c in range(PW)]
    top = max(abs(v) for v in db)
    return db, 12 if top <= 12 else 18 if top <= 18 else 24


def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v


def render(db, rng):
    """The graph card's bitmap as rows of (alpha, grey, blue) a pixel: patch/peqpage.c pg_render (the card, its rounded corners in the alpha, the grid, the faint fill down to 0 dB, a 1.5 px white line)."""
    y0, half = PY0 + PH // 2 + 0.5, PH / 2
    yc = [clamp(y0 - v * half / rng, PY0 + 0.5, PY0 + PH - 0.5) for v in db]
    out = []
    for y in range(H):
        row = []
        for x in range(W):
            v, a = float(GREY_CARD), 1.0
            col = x - PX0
            if (x < CARD_R or x >= W - CARD_R) and (y < CARD_R or y >= H - CARD_R):
                dx = x + 0.5 - (CARD_R if x < CARD_R else W - CARD_R)
                dy = y + 0.5 - (CARD_R if y < CARD_R else H - CARD_R)
                a = clamp(CARD_R - math.sqrt(dx * dx + dy * dy) + 0.5, 0, 1)
            if PY0 <= y < PY0 + PH and 0 <= col < PW:
                if y in (PY0, PY0 + PH - 1): v = GREY_GRID
                if y == PY0 + PH // 2: v = GREY_ZERO
                if col in GRID_X: v = GREY_GRID
                lo, hi = (yc[col], y0) if yc[col] < y0 else (y0, yc[col])
                ov = clamp(min(hi, y + 1) - max(lo, y), 0, 1)
                v += (GREY_INK - v) * 0.14 * ov
                s = ((yc[col + 1] if col + 1 < PW else yc[col]) - (yc[col - 1] if col else yc[col])) / (2 if col and col + 1 < PW else 1)
                d = abs(y + 0.5 - yc[col]) / math.sqrt(1 + s * s)
                v += (GREY_INK - v) * clamp(1.25 - d, 0, 1)
            row.append((int(a * 255 + 0.5), int(v + 0.5), TBM.card_blue(v)))
        out.append(row)
    return out


def render_accent(db, rng, acc):
    """The same card under an accent (patch/peqpage.c pg_accent): a plot pixel above its grid / zero-line grey goes that far toward the accent, read back from the neutral pixel's grey. Rows of (alpha, r, g, b)."""
    out = [[(a, g, g, b) for a, g, b in row] for row in render(db, rng)]
    for y in range(PY0, PY0 + PH):
        for x in range(PW):
            a, g, _, _ = out[y][PX0 + x]
            v0 = GREY_CARD
            if y in (PY0, PY0 + PH - 1): v0 = GREY_GRID
            if y == PY0 + PH // 2: v0 = GREY_ZERO
            if x in GRID_X: v0 = GREY_GRID
            if g > v0: out[y][PX0 + x] = TBM.cmix(v0, a, acc, (g - v0) / (GREY_INK - v0))
    return out


def dec(v100):
    """pp_dec: hundredths as '12', '0.7', '0.89'."""
    w, f = divmod(v100, 100)
    return f'{w}' + (f'.{f // 10}' + (str(f % 10) if f % 10 else '') if f else '')


def freq_text(f):
    hz10 = int(f * 10 + 0.5)
    return dec(hz10 * 10) + ' Hz' if hz10 < 10000 else dec(int(f / 10 + 0.5)) + ' kHz'


def gain_text(g, plus=True):
    g10 = int(g * 10 + (-0.5 if g < 0 else 0.5))
    a = abs(g10)
    return (MINUS if g10 < 0 else '+' if g10 > 0 and plus else '') + f'{a // 10}.{a % 10} dB'


def line_text(band, kind=('Peak', 'Low shelf', 'High shelf')):
    e, t, f, g, q = band
    return kind[t] + DOT + 'Q ' + dec(int(q * 100 + 0.5)) + (DOT + 'L' if e == 2 else DOT + 'R' if e == 3 else '')


def band_rows(bands):
    """[(frequency, gain, grey line)] of the page's band rows, in the preset's order."""
    return [(freq_text(f), gain_text(g), line_text((e, t, f, g, q))) for e, t, f, g, q in bands if e]   # (an OFF filter the parser kept never plays: no row)
