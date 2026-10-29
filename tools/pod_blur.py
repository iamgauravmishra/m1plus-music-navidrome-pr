#!/usr/bin/env python3
"""Reference model of the mini player bar's backdrop blur (patch/minibar.c mb_blur; docs/modules/minibar.md, Step B), bit for bit.

The pixels of the bar's rectangle (MB_W x MB_H, RGB565 in any channel order: the three fields are treated alike) are reduced 2 x 2 to a
half-resolution plane of packed words (the three channel sums in 10-bit fields, R at bit 20, G at 10, B at 0), box-blurred with two passes of a
4-tap window along the rows then two along the columns (edges replicated, each pass sums four words and divides by four with one rounded shift and
one mask: no field can carry into the next), darkened by 1/8 and written back 2 x 2, only inside the pill (the rounded ends are left alone; the
glass image's own edge covers the border).

Usage: pod_blur.blur(get) -> {(x, y): pixel} where get(x, y) is the RGB565 pixel at bar-local (x, y) and the result holds the pixels the payload writes.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pod_ui

W, H, R = pod_ui.MB_W, pod_ui.MB_H, pod_ui.MB_R
HW, HH = W // 2, H // 2
MASK = 0x0FF3FCFF          # three 8-bit fields at 0, 10, 20
DARK = 0x01F07C1F           # three 5-bit fields: w >> 3 of the 8-bit fields
HALF = 0x00200802          # 2 in each field: the rounding of a >> 2 (without it every pass loses about 1.5 and the smaller fields, red and blue, fall behind green)


def isqrt(n):
    s = 0
    while (s + 1) * (s + 1) <= n: s += 1
    return s


def inset(y):
    """Columns at the left (and right) end of full row y that lie outside the pill's arc, rounded up (conservative)."""
    yy = y if y < R else 2 * R - 1 - y
    d2 = 2 * (R - yy) - 1
    return R - (isqrt(4 * R * R - d2 * d2) >> 1)


def first_block(hy):
    """The first half-resolution block of half row hy that is written: both its rows, one pixel of margin."""
    ins = max(inset(2 * hy), inset(2 * hy + 1)) + 1
    return (ins + 1) >> 1


def spread(p): return (p & 0xF800) << 9 | (p & 0x07E0) << 5 | (p & 0x1F)


def line(v, left):
    """One 4-tap pass over the list v (replicated edges): out[i] = (v[i-left] + .. + v[i-left+3]) / 4 per field."""
    n = len(v)
    pad = [v[min(max(j - left, 0), n - 1)] for j in range(n + 5)]
    return [((sum(pad[i:i + 4]) + HALF) >> 2) & MASK for i in range(n)]


def blur(get):
    pl = [[spread(get(2 * hx, 2 * hy)) + spread(get(2 * hx + 1, 2 * hy)) + spread(get(2 * hx, 2 * hy + 1)) + spread(get(2 * hx + 1, 2 * hy + 1))
           for hx in range(HW)] for hy in range(HH)]
    for left in (2, 1): pl = [line(r, left) for r in pl]
    for left in (2, 1):
        cols = [line([pl[hy][hx] for hy in range(HH)], left) for hx in range(HW)]
        pl = [[cols[hx][hy] for hx in range(HW)] for hy in range(HH)]
    out = {}
    for hy in range(HH):
        x0 = first_block(hy)
        for hx in range(x0, HW - x0):
            w = pl[hy][hx]; w = w - ((w >> 3) & DARK) + HALF
            px = ((w >> 22) & 0x1F) << 11 | ((w >> 12) & 0x3F) << 5 | ((w >> 2) & 0x1F)
            for dy in (0, 1):
                for dx in (0, 1): out[(2 * hx + dx, 2 * hy + dy)] = px
    return out
