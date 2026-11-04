#!/usr/bin/env python3
"""Stock UI font beside the font-inter one, on real screens, drawn like the device draws text.

Two finished trees (e.g. one built without the font step and the release) side by side: status bar + System Settings,
Songs, Now Playing, the lock screen, and a list of mixed-script titles (English, Chinese, Japanese,
Korean, Russian, Greek, Vietnamese, Thai, curly quotes, digits), plus a 3x zoom of part of the titles.
The panels come from the looks' own preview painters (preview_theme, preview_lists,
preview_nowplaying, preview_lockscreen); only their text is redirected to tools/stb_raster.py, which
rasterizes each tree's default.ttf as AWTK's stb_truetype backend does (no hinting, truncated
advances, font_size = ascender - descender). Layout and blending stay approximate (not AWTK).

Usage: uv run python -I tools/preview_font.py STOCK_WORKDIR NEW_WORKDIR OUT.png [--labels "A|B"]
"""
import argparse, os, sys
from PIL import Image, ImageColor, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
import preview_theme, preview_lists, preview_nowplaying, preview_lockscreen
from stb_raster import StbFont

from awtk_ui import RAW
W, H = 320, 480
TITLES = [('Paul’s “Boutique” — Live', 'Beastie Boys'), ('七里香', '周杰伦 Jay Chou'),
          ('First Love (Remastered)', '宇多田ヒカル · Utada Hikaru'), ('봄날 Spring Day', '방탄소년단 BTS'),
          ('Группа крови', 'Кино · Виктор Цой'), ('Ελλάδα, Ωδή', 'Μίκης Θεοδωράκης'),
          ('Tiến Quân Ca', 'Văn Cao · Việt Nam'), ('ไม่บอกเธอ', 'Bedroom Audio (Thai)'),
          ('01:23 / 04:56  1/12  86%', '0123456789 tabular')]

_fonts = {}
def stb(path):
    if path not in _fonts: _fonts[path] = StbFont(path)
    return _fonts[path]

class Face:
    """The bits of a PIL FreeTypeFont the preview painters use, answered the AWTK way."""
    def __init__(self, path, px): self.f, self.px = stb(path), int(round(px))
    def getlength(self, s): return self.f.width(s, self.px)
    def getmetrics(self): b = self.f.baseline(self.px); return b, self.px - b

_text = ImageDraw.ImageDraw.text
def text(self, xy, s, fill=None, font=None, anchor=None, *a, **k):
    if not isinstance(font, Face): return _text(self, xy, s, fill, font, anchor, *a, **k)
    anchor = anchor or 'la'; px = font.px; w = font.getlength(s)
    x = xy[0] - {'l': 0, 'm': w / 2, 'r': w}[anchor[0]]
    top = xy[1] - {'a': 0, 's': font.f.baseline(px), 'm': px / 2, 'd': px}[anchor[1]]
    rgba = ImageColor.getrgb(fill) if isinstance(fill, str) else tuple(fill)
    font.f.draw(self._image, round(x), round(top), s, px, rgba + (255,) * (4 - len(rgba)))
ImageDraw.ImageDraw.text = text
preview_theme.Tree.font = lambda self, px: Face(self.ttf, px)
preview_lockscreen.Painter.font = lambda self, px: Face(self.font_path, px)
preview_nowplaying.Painter.font = lambda self, px: Face(self.font_path, px)
preview_nowplaying.SAMPLE.update({'scrlabel_title': '七里香 (Live)', 'scrlabel_artist': '周杰伦 Jay Chou',
                                  'label_album': 'Album:Common Jasmin Orange'})

def titles(work):
    f = os.path.join(work, RAW, 'fonts', 'default.ttf')
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    d.text((W // 2, 15), 'Mixed titles', font=Face(f, 18), fill='#FFFFFF', anchor='mm')
    for i, (t, a) in enumerate(TITLES):
        y = 34 + i * 49
        d.text((14, y + 4), t, font=Face(f, 21), fill='#FFFFFF')
        d.text((14, y + 27), a, font=Face(f, 18), fill='#AAAAAA')
        d.line([(14, y + 48), (W, y + 48)], fill='#333333')
    return im

def shots(work):
    raw = os.path.join(work, RAW)
    np_root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'playing_page.bin'), 'rb').read())
    lock = awtk_ui.parse(open(os.path.join(raw, 'ui', 'screensaver_page.bin'), 'rb').read())
    return [preview_theme.settings(preview_theme.Tree(work)), preview_lists.panels(work)[1],
            preview_nowplaying.Painter(raw).render(np_root, 0), preview_lockscreen.Painter(raw, False).render(lock, 86, False, False),
            titles(work)]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stock'); ap.add_argument('new'); ap.add_argument('out')
    ap.add_argument('--labels', default='stock font|Inter + Source Han Sans')
    a = ap.parse_args()
    labels = a.labels.split('|')
    rows = [shots(a.stock), shots(a.new)]
    names = ['status bar, settings', 'Songs', 'Now Playing', 'lock screen', 'mixed titles']
    pad, top, Z = 10, 20, 3
    zoom = (8, 30, 218, 230)                                     # part of the titles panel, 3x
    zw, zh = (zoom[2] - zoom[0]) * Z, (zoom[3] - zoom[1]) * Z
    out = Image.new('RGB', (5 * (W + pad) + pad, 2 * (H + top) + top + zh + 26), (40, 40, 40)); d = ImageDraw.Draw(out)
    for r, ims in enumerate(rows):
        for c, im in enumerate(ims):
            assert im.size == (W, H), (names[c], im.size)
            x, y = pad + c * (W + pad), r * (H + top) + top
            out.paste(im.convert('RGB'), (x, y)); d.text((x, y - 15), f'{labels[r]}: {names[c]}', fill=(230, 230, 230))
    y = 2 * (H + top) + top
    for r, ims in enumerate(rows):
        x = pad + r * (zw + pad)
        out.paste(ims[4].crop(zoom).resize((zw, zh), Image.NEAREST).convert('RGB'), (x, y))
        d.text((x, y - 15), f'{labels[r]}: titles, 3x', fill=(230, 230, 230))
    d.text((2 * (zw + pad) + pad, y), 'Text: tools/stb_raster.py, the stb_truetype way (no hinting,\n'
           'truncated advances, font_size = ascender - descender).\nPanels: the looks\' PIL painters, approximate layout.\n'
           'Sample data; lock screen wallpaper replaced by a gradient.', fill=(200, 200, 200))
    out.quantize(colors=192).save(a.out, optimize=True); print('wrote', a.out)

if __name__ == '__main__': main()
