#!/usr/bin/env python3
"""The album page header's vertical rhythm, two variants side by side (tools/ah_ink.py measures the ink, VARIANTS names them):
A the tighter text block, B the airier one, both under the 44 px navbar. Per variant: a real cover tinted, the black placeholder page,
a long title, a CJK title, at 1:1; below, the tinted pages' header at 2x. Every panel is the approximate PIL page of
tools/preview_album.py (AWTK is not run), the text rasterized the stb_truetype way from the tree's default.ttf. The captions give
each variant's vertical gaps in px of ink (capitals / digits to the neighbouring baseline or edge), as the test measures them.

Usage: venv/bin/python -I tools/preview_album_header.py WORKDIR OUT.png
"""
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preview_album as PA
import preview_album_tint as PT
import mod_nowplaying as NP
import ah_ink

LONG = ('The Rise and Fall of Ziggy Stardust and the Spiders from Mars', 'David Bowie with the Spiders from Mars', '1972 \xb7 11 tracks')
CJK = ('七里香 (Live) 周杰伦演唱会纪念专辑', '周杰伦 Jay Chou', '2004 \xb7 10 首')


def variant_constants(f, outer, gap, nav=None):
    c = dict(PA.C); c.update(ah_ink.layout(f, outer, gap))
    c['AH_TINT_ROWS'] = c['AH_NAV_H'] + c['AH_HDR_H']
    return c


def alpha(c, y):
    """patch/common.c pod_alpha with the variant's ramp (top 64 on window row 0, bottom 200 on the header's last row)."""
    top, bot, rows = c['AH_TINT_A_TOP'], c['AH_TINT_A_BOT'], c['AH_TINT_ROWS']
    return bot if y >= rows - 1 else top + ((bot - top) * y + (rows - 1) // 2) // (rows - 1)


def panels(work, c):
    out = []
    for name, art, (title, artist, meta) in (('real cover, tinted', PA.art('sky'), ('Kind of Blue', 'Miles Davis', '1959 \xb7 8 tracks')),
                                              ('placeholder, black', None, ('Kind of Blue', 'Miles Davis', '1959 \xb7 8 tracks')),
                                              ('long title', PT.cover((190, 50, 55)), LONG), ('CJK title', PT.cover((40, 80, 190)), CJK)):
        if art is None: bg = None
        else:
            tone = NP.tone(*PT.average(art)); bg = lambda y, t=tone: tuple(v * (255 - alpha(c, y)) // 255 for v in t)
        out.append((name, PA.page(work, '', title, artist, meta, art, 8, bg=bg, C=c).convert('RGB'), art is not None))
    return out


def main():
    if len(sys.argv) != 3: sys.exit(__doc__)
    work, path = sys.argv[1:3]
    f = ah_ink.font(work)
    pad, top, W, H = 12, 34, 320, 480
    rows = []
    for name, outer, gap in ah_ink.VARIANTS:
        c = variant_constants(f, outer, gap); g = ah_ink.gaps(f, c)
        cap = (f'{name}: vertical ink gaps cover-title {g["cover-title"]}, title-artist {g["title-artist"]}, artist-year {g["artist-year"]}, '
               f'year-buttons {g["year-buttons"]} px; header {c["AH_HDR_H"]} px, navbar {c["AH_NAV_H"]} px')
        rows.append((name, cap, c, panels(work, c)))
    zh = 350   # the 2x crop: window rows 0 .. zh (navbar, cover, the text block, the buttons), status bar excluded
    sheet = Image.new('RGB', (4 * (W + pad) + pad, 2 * (H + top) + top + 2 * (zh * 2 + 30) + 2 * pad + 20), (40, 40, 40)); d = ImageDraw.Draw(sheet)
    for r, (name, cap, c, ps) in enumerate(rows):
        y0 = pad + r * (H + top)
        d.text((pad, y0), cap, fill=(255, 255, 255))
        for i, (pn, im, _) in enumerate(ps):
            x = pad + i * (W + pad)
            d.text((x, y0 + 16), f'{name}: {pn}', fill=(200, 200, 200)); sheet.paste(im, (x, y0 + top))
    y0 = pad + 2 * (H + top) + 6
    for k, i in enumerate((0, 2)):   # the real cover and the long title, A beside B, 2x
        for r, (name, cap, c, ps) in enumerate(rows):
            im = ps[i][1].crop((0, PA.BAR, W, PA.BAR + zh)).resize((W * 2, zh * 2), Image.NEAREST)
            x, y = pad + r * (W * 2 + pad), y0 + 16 + k * (zh * 2 + 30)
            sheet.paste(im, (x, y)); d.text((x, y - 14), f'{name} 2x: {ps[i][0]}', fill=(200, 200, 200))
    sheet.crop((0, 0, sheet.width, y0 + 2 * (zh * 2 + 30) + pad)).save(path); print('wrote', path)


if __name__ == '__main__': main()
