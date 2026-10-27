#!/usr/bin/env python3
"""The album page header's visual rhythm: where the ink of each text line really is (tools/stb_raster.py, the stb_truetype
rasterizer the device uses, on the tree's default.ttf) and the gaps between the lines. Shared by tools/preview_album_header.py
and test/pod/albuminfo.py.

An AWTK label draws its line box (font_size high) centred in the widget; the baseline is `StbFont.baseline(px)` below the line box
top. The ink the eye measures a gap from: the top of the capitals / digits (CAP, from "H" and "0") above the baseline, and the
baseline itself (descenders hang below it and are not counted: a gap is read between the lines' bodies). A pixel counts as ink from
coverage INK_MIN (half).

Usage: venv/bin/python -I tools/ah_ink.py WORKDIR     (prints the measured numbers of each line size, and the header's gaps)
"""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stb_raster import StbFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_REL = 'rootfs/release/assets/default/raw/fonts/default.ttf'
INK_MIN = 128


def constants():
    out = {}
    for line in open(os.path.join(ROOT, 'patch', 'offsets.inc')):
        m = re.match(r'#define (\w+) (-?(?:0x[0-9a-fA-F]+|\d+))u?\s*(?:/\*.*)?$', line.strip())
        if m: out[m.group(1)] = int(m.group(2), 0)
    return out


def font(work):
    return StbFont(os.path.join(work, FONT_REL))


def ink_rows(f, px, text):
    """(top, bottom): the first and last row with ink (coverage >= INK_MIN) of `text`, relative to the baseline (negative above)."""
    top, bot = None, None
    for ch in text:
        x0, y0, w, h, rows = f.bitmap(f.glyph(ch), px)
        for i, row in enumerate(rows):
            if max(row, default=0) >= INK_MIN:
                top = y0 + i if top is None else min(top, y0 + i)
                bot = y0 + i + 1 if bot is None else max(bot, y0 + i + 1)
    return top, bot


def cap(f, px):
    """Rows of the capitals and digits above the baseline (the ink top of "H0")."""
    return -ink_rows(f, px, 'H0')[0]


def baseline(f, px, y, h):
    """Row (item coordinates) of the baseline of a label at y, h: the line box is centred in the widget."""
    return y + (h - px) // 2 + f.baseline(px)


def cap_top(f, px, y, h):
    return baseline(f, px, y, h) - cap(f, px)


VARIANTS = [('A', 14, 7), ('B', 16, 9)]   # (name, outer gap, text gap): A tighter text block, B airier (tools/preview_album_header.py)
LINE_PAD = 0   # a label is its font size plus this high: the line box (descenders included) fits, and the rects do not overlap
BOTTOM = 8     # the touch rectangles end this far above the first track row


def layout(f, outer, gap, art_y=6, art=160, btn_h=44, pill_h=40):
    """The header's AH_* rects for these ink gaps: `outer` from the cover's bottom to the title's capitals and from the year line's
    baseline to the pill's top, `gap` from the title's baseline to the artist's capitals and from the artist's baseline to the
    year line's digits. Returns {AH_TITLE_Y.. AH_HDR_H}."""
    import mod_ipodrows as M
    out, base = {}, art_y + art
    prev_base, prev_gap = base, outer
    for key, px in (('TITLE', M.TITLE_PX), ('ARTIST', M.ARTIST_PX), ('META', M.META_PX)):
        h = px + LINE_PAD
        want_cap_top = prev_base + prev_gap
        y = want_cap_top + cap(f, px) - f.baseline(px) - (h - px) // 2
        out[f'AH_{key}_Y'], out[f'AH_{key}_H'] = y, h
        prev_base, prev_gap = baseline(f, px, y, h), gap
    out['AH_BTN_Y'] = prev_base + outer - (btn_h - pill_h) // 2
    out['AH_HDR_H'] = out['AH_BTN_Y'] + btn_h + BOTTOM
    return out


def gaps(f, c):
    """The header's vertical gaps from the AH_* numbers in c, in px of ink: cover bottom -> title cap top, title baseline ->
    artist cap top, artist baseline -> year-line digit top, year-line baseline -> the buttons' drawn top (the pill)."""
    import mod_ipodrows
    tp, ap, mp = mod_ipodrows.TITLE_PX, mod_ipodrows.ARTIST_PX, mod_ipodrows.META_PX
    t_top, t_base = cap_top(f, tp, c['AH_TITLE_Y'], c['AH_TITLE_H']), baseline(f, tp, c['AH_TITLE_Y'], c['AH_TITLE_H'])
    a_top, a_base = cap_top(f, ap, c['AH_ARTIST_Y'], c['AH_ARTIST_H']), baseline(f, ap, c['AH_ARTIST_Y'], c['AH_ARTIST_H'])
    m_top, m_base = cap_top(f, mp, c['AH_META_Y'], c['AH_META_H']), baseline(f, mp, c['AH_META_Y'], c['AH_META_H'])
    pill_top = c['AH_BTN_Y'] + (c['AH_BTN_H'] - c['AH_PILL_H']) // 2
    return {'cover-title': t_top - (c['AH_ART_Y'] + c['AH_ART']), 'title-artist': a_top - t_base,
            'artist-year': m_top - a_base, 'year-buttons': pill_top - m_base}


def main():
    if len(sys.argv) != 2: sys.exit(__doc__)
    f = font(sys.argv[1]); c = constants()
    for px in (22, 18, 15):
        print(f'{px} px: baseline {f.baseline(px)} below the line box top, cap height {cap(f, px)}, x-height {-ink_rows(f, px, "x")[0]}, '
              f'descender {ink_rows(f, px, "gjpqy")[1]}, "Kind of Blue" ink {ink_rows(f, px, "Kind of Blue")}')
    print('gaps (ink), the patch/offsets.inc numbers:', gaps(f, c))
    for name, outer, gap in VARIANTS:
        lay = layout(f, outer, gap); print(f'variant {name} (outer {outer}, text {gap}):', lay, gaps(f, {**c, **lay}))


if __name__ == '__main__': main()
