#!/usr/bin/env python3
"""CJK region sheet: the font step's CJK through each cmap the payload can select, drawn like the device draws text.

Each column is a 320 x 480 black page of mixed CJK lines at the UI's sizes (16 to 22 px), white titles and
grey secondary lines, rasterized from a font made by mod_font.merge (stb_raster: no hinting, truncated
advances, +1 px per glyph). The stock font is first cut down to the sample's code points so it merges in
seconds; the glyphs and maps are the ones the build would write. Columns: the default map (every UI language
without a regional map), then the regional maps of mod_font.REGIONS (zh_CN, ja_JP, zh_HK), which differ in
the ideographs and punctuation of their region and in the full-width dash and centred ellipsis.
(The CJK weight, SHS_WEIGHT Medium, was picked from a sheet of Regular, Medium and an emboldened Regular.)
Writes OUT.png (1x), OUT@2x.png (nearest) and OUT-zoom.png (4x crop of the same lines in every column).

Usage: uv run python -I tools/preview/preview_cjk.py STOCK_WORKDIR [OUT.png]
"""
import argparse, io, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mod_font, paths
from stb_raster import StbFont

W, H, HEAD = 320, 480, 26
LINES = [(22, '#FFFFFF', '七里香 (Live)'), (16, '#8E8E93', '周杰伦 Jay Chou · 2004'),
         (18, '#FFFFFF', '「晴天」《叶惠美》，2003。'), (16, '#8E8E93', '你好！今天听什么？（随机播放）'),
         (20, '#FFFFFF', '他说——等一下……'), (16, '#FFFFFF', '设置、音乐库、正在播放：86%'),
         (18, '#FFFFFF', '直 骨 角 写 浅 曜 今 次'), (16, '#8E8E93', '東京、さくら。宇多田ヒカル！'),
         (18, '#FFFFFF', '說 為 這 着 黃 遠 青 冬'), (16, '#8E8E93', '周杰倫《葉惠美》，晴天。'),
         (21, '#FFFFFF', '鬱 齉 薑 曦 魔 題 歌 編 爆'), (16, '#8E8E93', '방탄소년단 봄날 ㅋㅋ ①②③')]
ZOOM_LINES = (4, 10)         # lines drawn in the 4x crop (index range)
LABELS = {None: 'default (en, ...)', 'sc': 'zh_CN', 'jp': 'ja_JP', 'tc': 'zh_HK (TC)'}

def cut(stock, text):
    """The stock font cut to the sample's code points (plus Inter's, so merge maps every Latin one)."""
    from fontTools.ttLib import TTFont
    from fontTools import subset
    f = TTFont(io.BytesIO(stock), recalcTimestamp=False)
    o = subset.Options(); o.notdef_outline = True; o.glyph_names = True; o.hinting = False
    o.layout_features = []; o.name_IDs = ['*']; o.recalc_bounds = True
    s = subset.Subsetter(o); s.populate(unicodes=sorted({ord(c) for c in text})); s.subset(f)
    out = io.BytesIO(); f.save(out)
    return out.getvalue()

def page(font, label):
    im = Image.new('RGBA', (W, H + HEAD), (0, 0, 0, 255))
    ImageDraw.Draw(im).rectangle((0, 0, W, HEAD - 1), fill=(40, 40, 40, 255))
    font.draw(im, 8, 4, label, 16, (255, 255, 255, 255))
    y, ys = HEAD + 8, []
    for px, col, s in LINES:
        ys.append(y)
        font.draw(im, 12, y, s, px, tuple(int(col[i:i + 2], 16) for i in (1, 3, 5)) + (255,))
        y += px + 14
    return im, ys

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stock'); ap.add_argument('out', nargs='?', default=os.path.join(paths.OUT, 'peek', 'cjk_regions.png'))
    a = ap.parse_args()
    stock = open(os.path.join(a.stock, mod_font.FONT), 'rb').read()
    inter = mod_font.track(open(os.path.join(mod_font.ROOT, mod_font.INTER_ASSET), 'rb').read(), mod_font.INTER_TRACKING)
    small = cut(stock, ''.join(s for _, _, s in LINES) + ''.join(LABELS.values()))
    font, _ = mod_font.merge(small, inter, mod_font.shs_faces(paths.SHS_ZIP), log=lambda *_: None)
    pages = []
    for r, label in LABELS.items():
        f = StbFont(font)
        if r: f.cmap = mod_font.cmap_subtable(font, (1, mod_font.REGIONS[r][0]))   # as the payload sets index_map
        pages.append(page(f, label))
    sheet = Image.new('RGB', (len(pages) * (W + 8) - 8, H + HEAD), (90, 90, 90))
    for i, (im, _) in enumerate(pages): sheet.paste(im.convert('RGB'), (i * (W + 8), 0))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    base = os.path.splitext(a.out)[0]
    sheet.save(a.out); sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(base + '@2x.png')
    ys = pages[0][1]; top, bot = ys[ZOOM_LINES[0]] - 4, ys[ZOOM_LINES[1]] - 6
    zoom = Image.new('RGB', (len(pages) * (W * 2 + 6) - 6, (bot - top) * 2), (90, 90, 90))
    for i, (im, _) in enumerate(pages):
        zoom.paste(im.crop((0, top, W, bot)).resize((W * 2, (bot - top) * 2), Image.NEAREST).convert('RGB'),
                   (i * (W * 2 + 6), 0))
    zoom.save(base + '-zoom.png')
    print(f'{a.out}, {base}@2x.png, {base}-zoom.png')

if __name__ == '__main__': main()
