#!/usr/bin/env python3
"""Anti-aliasing comparison sheet: coverage gamma (columns) x x-height snap (rows), tools/stb_raster.py text.

Gamma maps each glyph coverage through tools/textgamma.py's lut(g) before blending (g 1.00 is stock; the build uses
textgamma.GAMMA).
Snap scales the outline's y > 0 by round(xh)/xh for lowercase a-z, xh = x-height in px; the bitmap box
grows to hold the outline. An approximation: ascenders scale too. Each cell is a 320 px panel at 1:1;
below the grid, a 3x nearest-neighbour zoom of the 18 px and 16 px lines of each cell.

Usage: uv run python -I tools/preview_aa.py [FONT] [OUT]
"""
import argparse, os, sys
from PIL import Image, ImageColor, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from stb_raster import StbFont
import textgamma

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = os.path.join(ROOT, 'work/mod-release/rootfs/release/assets/default/raw/fonts/default.ttf')
GAMMAS, SNAPS = [1.0, 1.25, 1.45, 1.8], [False, True]
CELL_W, CELL_H, PAD, GAP, LABEL_H = 320, 236, 16, 16, 20
STRIP_TOP, STRIP_H = 196, 30
ZOOM_X, ZOOM_W, ZOOM_H = 12, 106, 106
LINES = [(34, 'Recently Added', 6, '#FFFFFF'), (21, 'Paul’s Boutique', 46, '#FFFFFF'),
         (18, 'Beastie Boys · minimum rhythm', 74, '#FFFFFF'), (16, 'The quick brown fox jumps over', 98, '#FFFFFF'),
         (13, '12 songs, 48 minutes', 120, '#8E8E93'), (16, 'Settings Files', 146, '#8E8E93'),
         (18, '七里香 周杰伦 宇多田ヒカル', 170, '#FFFFFF')]

class AAFont(StbFont):
    """StbFont with the two candidate fixes. One instance per (gamma, snap), so caches never mix."""
    def __init__(self, data, gamma, snap):
        self.f = 1.0                                   # y scale of the glyph being rasterized
        super().__init__(data)
        self.lut = textgamma.lut(gamma)
        self.snap = snap
        self.lower = {self.glyph(c) for c in 'abcdefghijklmnopqrstuvwxyz'}
        self.xh_units = super().box(self.glyph('x'))[3]
        self.gcache = {}

    def xh_px(self, px): return self.xh_units * self.scale(px)

    def box(self, g):
        b = super().box(g)
        if b is None: return b
        return (b[0], b[1], b[2], b[3] * max(self.f, 1.0))

    def shape(self, g, depth=0):
        v = super().shape(g, depth)
        if depth or self.f == 1.0: return v           # composites are scaled once, at the top level
        f = self.f
        return [(t, x, y * f if y > 0 else y, cx, cy * f if cy > 0 else cy) for t, x, y, cx, cy in v]

    def bitmap(self, g, px):
        if (g, px) not in self.gcache:
            xh = self.xh_px(px)
            self.f = round(xh) / xh if self.snap and g in self.lower else 1.0
            x0, y0, w, h, rows = super().bitmap(g, px)
            self.gcache[(g, px)] = (x0, y0, w, h, [[self.lut[v] for v in r] for r in rows])
        return self.gcache[(g, px)]

def rgba(hex_, a=255): return ImageColor.getrgb(hex_) + (a,)

def cell(sheet, font, x, y):
    d = ImageDraw.Draw(sheet)
    d.rectangle([x - 1, y - 1, x + CELL_W, y + CELL_H], outline=(68, 68, 68, 255))
    d.rectangle([x, y, x + CELL_W - 1, y + CELL_H - 1], fill=(0, 0, 0, 255))
    for px, text, top, col in LINES:
        assert font.width(text, px) <= CELL_W - 28, (text, px)
        font.draw(sheet, x + 14, y + top, text, px, rgba(col))
    d.rectangle([x, y + STRIP_TOP, x + CELL_W - 1, y + STRIP_TOP + STRIP_H - 1], fill=(242, 242, 242, 255))
    font.draw(sheet, x + 14, y + STRIP_TOP + 7, 'Dark on light text', 16, (0, 0, 0, 255))

def zoom(sheet, x, y):
    """3x nearest-neighbour of the 18 px line (rows 74..92) and the 16 px line (rows 98..114) of a cell."""
    out = Image.new('RGBA', (ZOOM_W * 3, ZOOM_H), (0, 0, 0, 255))
    for top, px, dy in ((74, 18, 0), (98, 16, 58)):
        crop = sheet.crop((x + ZOOM_X, y + top, x + ZOOM_X + ZOOM_W, y + top + px))
        out.paste(crop.resize((ZOOM_W * 3, px * 3), Image.NEAREST), (0, dy))
    return out

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('font', nargs='?', default=FONT)
    ap.add_argument('out', nargs='?', default=os.path.join(ROOT, 'out/preview/aa_sheet.png'))
    a = ap.parse_args()
    data = open(a.font, 'rb').read()
    fonts = {(g, s): AAFont(data, g, s) for s in SNAPS for g in GAMMAS}
    label_font = AAFont(data, 1.0, False)
    for px in (13, 16, 18, 21, 34):
        print(f'{px:>2} px: xh {label_font.xh_units} units, {label_font.xh_px(px):.2f} px, '
              f'snap x{round(label_font.xh_px(px)) / label_font.xh_px(px):.4f}')

    W = PAD * 2 + 4 * CELL_W + 3 * GAP
    top_grid = PAD + LABEL_H + 4
    grid_h = 2 * (LABEL_H + CELL_H) + GAP
    zoom_top = top_grid + grid_h + GAP + 2 * LABEL_H
    H = zoom_top + 2 * (LABEL_H + ZOOM_H) + GAP + PAD
    sheet = Image.new('RGBA', (W, H), (32, 32, 32, 255))
    label = lambda s, x, y: label_font.draw(sheet, x, y, s, 13, rgba('#BBBBBB'))
    label('Anti-aliasing: coverage gamma (columns) x x-height snap (rows); text as the device draws it',
          PAD, PAD)
    label('3x zoom, nearest neighbour: 18 px line (top) and 16 px line (bottom)', PAD, top_grid + grid_h + GAP)

    def name(g, s): return f'g {g:.2f} · {"snap" if s else "no snap"}'
    for r, s in enumerate(SNAPS):
        for c, g in enumerate(GAMMAS):
            x = PAD + c * (CELL_W + GAP)
            y = top_grid + r * (LABEL_H + CELL_H + GAP) + LABEL_H
            label(name(g, s), x, y - LABEL_H)
            cell(sheet, fonts[(g, s)], x, y)
            zy = zoom_top + r * (LABEL_H + ZOOM_H + GAP)
            label(name(g, s), x, zy - LABEL_H)
            sheet.paste(zoom(sheet, x, y), (x + ZOOM_X, zy))

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    sheet.convert('RGB').save(a.out, optimize=True)
    print('wrote', a.out)

if __name__ == '__main__': main()
