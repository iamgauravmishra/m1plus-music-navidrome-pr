#!/usr/bin/env python3
"""The 10-Band editor's model (patch/tenband.c, docs/modules/peq.md "10-Band EQ"): the slider card's geometry, the touch maths, the card / thumb / pill bitmaps and the texts, in Python.

tools/preview_tenband.py draws the page from it and test/pod/peq.py checks the payload against it (the bitmaps pixel by pixel, the touch maths and the texts). The numbers are patch/offsets.inc TB_*."""
import math

MINUS = '−'
# patch/offsets.inc TB_* (tools/pod_ui.py asserts the same values; test/pod/peq.py compares them with the file)
W, H, CARD_X, R, COLS, COL_W, X0, Y0, SPAN, PX_DB, TRACK_W = 300, 170, 10, 12, 10, 29, 5, 40, 96, 4, 4
THUMB_W, THUMB_H, VAL_Y, VAL_H, FREQ_Y, FREQ_H, PILL_W, PILL_H, LABEL_W, LABEL_PX = 24, 13, 10, 18, 145, 18, 34, 18, 36, 11
STEP_MAX = 24
GREY_CARD, GREY_TRACK, GREY_THUMB, GREY_LINE = 28, 62, 242, 196


def center_x(c): return X0 + c * COL_W + COL_W // 2


def col(x):
    """The column under a card-relative x, clamped (patch/tenband.c tenband_col)."""
    c = -1 if x < X0 else (x - X0) // COL_W
    return max(0, min(COLS - 1, c))


def step(y):
    """The half-decibel step of a card-relative y, truncated toward zero, clamped (tenband_step)."""
    h = Y0 + SPAN // 2 - y
    s = int(h / (PX_DB // 2))
    return max(-STEP_MAX, min(STEP_MAX, s))


def y_of_step(s):
    """The card-relative y where the finger is for a step (the thumb's centre)."""
    return Y0 + SPAN // 2 - s * (PX_DB // 2)


def thumb_y(g):
    """The top of the thumb of gain g (tenband.c tb_thumb_y: the centre rounded away from zero)."""
    return Y0 + SPAN // 2 - int(g * PX_DB + (-0.5 if g < 0 else 0.5)) - THUMB_H // 2


def clamp(v, lo, hi): return lo if v < lo else hi if v > hi else v


def cover(x, y, w, h, r):
    dx, dy = x + 0.5 - w / 2.0, y + 0.5 - h / 2.0
    dx, dy = max(abs(dx) - (w / 2.0 - r), 0), max(abs(dy) - (h / 2.0 - r), 0)
    return clamp(r + 0.5 - math.sqrt(dx * dx + dy * dy), 0, 1)


def px(grey, alpha): return (int(alpha * 255 + 0.5), int(grey + 0.5))   # (alpha, grey)


def card_blue(grey):
    """patch/peqpage.h tb_cpx: the card's blue, 2 above the card grey, on that exact grey only (tracks, hairlines and lines stay neutral)."""
    g = int(grey + 0.5)
    return g + 2 * (g == GREY_CARD)


def cpx(grey, alpha): return px(grey, alpha) + (card_blue(grey),)   # (alpha, grey, blue): a pixel of a card (the surface #1C1C1E)


def card_px(x, y):
    v = float(GREY_CARD)
    for c in range(COLS):
        cx = center_x(c) + 0.5
        dx, r = x + 0.5 - cx, TRACK_W / 2.0
        if dx < -r - 1 or dx > r + 1: continue
        py = clamp(y + 0.5, Y0, Y0 + SPAN)
        d = math.sqrt(dx * dx + (y + 0.5 - py) ** 2)
        v += (GREY_TRACK - v) * clamp(r + 0.5 - d, 0, 1)
    return cpx(v, cover(x, y, W, H, R))


def thumb_px(x, y):
    v = GREY_LINE if y == THUMB_H // 2 and 6 <= x < THUMB_W - 6 else GREY_THUMB
    return px(v, cover(x, y, THUMB_W, THUMB_H, 5.5))


def apx(acc, grey, ref, alpha):
    """patch/peqpage.h tb_apx: (alpha, r, g, b) of the accent acc scaled by grey / ref."""
    return (int(alpha * 255 + 0.5),) + tuple(int(c * grey / ref + 0.5) for c in acc)


def thumb_px_acc(x, y, acc):
    """The thumb under an accent (tb_thumb_px with tb_accent): the accent, its line a darker one; (alpha, r, g, b)."""
    v = GREY_LINE if y == THUMB_H // 2 and 6 <= x < THUMB_W - 6 else GREY_THUMB
    return apx(acc, v, GREY_THUMB, cover(x, y, THUMB_W, THUMB_H, 5.5))


def cmix(grey, a8, acc, k):
    """patch/peqpage.h tb_cmix: the card pixel of grey `grey` a fraction k of the way to the accent; (alpha, r, g, b)."""
    g = int(grey + 0.5)
    base = (g, g, g + 2 * (g == GREY_CARD))
    return (a8,) + tuple(int(b + (c - b) * k + 0.5) for b, c in zip(base, acc))


def pill_px(x, y): return px(GREY_THUMB, cover(x, y, PILL_W, PILL_H, PILL_H / 2.0))


def bitmap(fn, w, h): return [[fn(x, y) for x in range(w)] for y in range(h)]


def gain_text(g):
    """The slider's value, no unit: +4.5, -2.5 (U+2212), 0, +12."""
    g10 = int(g * 10 + (-0.5 if g < 0 else 0.5))
    a = abs(g10)
    if not g10: return '0'
    sign = MINUS if g10 < 0 else '+'
    return f'{sign}{a // 10}.{a % 10}' if a % 10 else f'{sign}{a // 10}'


def cut_text(cut):
    """A fixed preamp: 0 dB, -3 dB (the value form "%d dB", U+2212 before a cut)."""
    return f'{MINUS if cut > 0 else ""}{cut} dB'
