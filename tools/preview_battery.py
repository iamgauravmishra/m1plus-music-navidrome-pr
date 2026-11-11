#!/usr/bin/env python3
"""out/preview/battery.png: the status bar's and the lock screen's battery from a built tree,
states empty / half / full / charging / low at 8x, with the app's progress-bar fill drawn UNDER the
image exactly where the tree's ui files put it. Also asserts the fill rectangle lies inside the
outline's inner edge for every level (the alignment check).

  preview_battery.py TREE OUT.png          (an unpacked work tree of a full-icons build; venv python)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import awtk_ui, battery_art as B

from awtk_ui import RAW
Z = 8
ANN = ImageFont.load_default(13)

def geometry(tree, ui, img_name, pg_name):
    root = awtk_ui.parse(open(os.path.join(tree, RAW, 'ui', ui), 'rb').read())
    img, pg = root.find(img_name), root.find(pg_name)
    fill = (pg.x - img.x, pg.y - img.y, pg.w, pg.h)
    return img, pg, fill

def draw(tree, spec, imgs, fill, bg, level):
    """Level 0..100 -> the pgbar fill width as AWTK's progress bar draws it (inside its box)."""
    w, h = spec.canvas
    im = Image.new('RGBA', (w, h), bg)
    fx, fy, fw, fh = fill
    n = round(fw * level / 100)
    if n: ImageDraw.Draw(im).rectangle((fx, fy, fx + n - 1, fy + fh - 1), fill=(255, 255, 255, 255))
    im.alpha_composite(Image.open(imgs).convert('RGBA'))
    return im

def check_fill(spec, png_path, fill):
    """The fill box must be inside the outline's inner edge, and the image's pixels there empty (transparent)."""
    assert tuple(fill) == tuple(spec.fill), (fill, spec.fill)
    gap = B.fill_gap(spec); assert gap >= 0, gap
    a = Image.open(png_path).convert('RGBA'); fx, fy, fw, fh = fill
    for y in range(fy, fy + fh):
        for x in range(fx, fx + fw):
            assert a.getpixel((x, y))[3] < 16 or png_path.endswith(('charge.png', 'bar_charge.png')), (x, y, a.getpixel((x, y)))
    return gap

def main():
    tree, out = sys.argv[1:3]
    xx = os.path.join(tree, RAW, 'images/xx')
    sets = [('Status bar (bar_power / bar_charge / bar_lowpower, black bar)', B.STATUS, 'system_bar.bin', 'img_battery', 'pgbar_battery',
             {'normal': 'bar_power', 'charge': 'bar_charge', 'low': 'bar_lowpower'}, (0, 0, 0, 255)),
            ('Lock screen (screens_battery / screens_charge / screens_lowbattery, over the card)', B.STATUS, 'screensaver_page.bin', 'img_battery', 'pgbar_battery',
             {'normal': 'screens_battery', 'charge': 'screens_charge', 'low': 'screens_lowbattery'}, (0x40, 0x3A, 0x38, 255))]
    cols = [('empty', 'normal', 0), ('half', 'normal', 50), ('full', 'normal', 100), ('charging 50%', 'charge', 50),
            ('charging 100%', 'charge', 100), ('low (0%)', 'low', 0)]
    rows = []
    for title, spec, ui, iname, pname, files, bg in sets:
        img, pg, fill = geometry(tree, ui, iname, pname)
        assert (img.w, img.h) == spec.canvas, (img.w, img.h, spec.canvas)
        gaps = {st: check_fill(spec, os.path.join(xx, f + '.png'), fill) for st, f in files.items()}
        print(f'{title.split(" (")[0]}: image {img.w}x{img.h} at ({img.x},{img.y}), pgbar fill box {fill} inside the image; '
              f'gap to the outline\'s inner edge {gaps["normal"]} px; checked on all three state images')
        rows.append((title, [(lab, draw(tree, spec, os.path.join(xx, files[st] + '.png'), fill, bg, lv)) for lab, st, lv in cols]))
    cw = 34 * Z + 20
    sh = Image.new('RGB', (len(cols) * cw + 20, 2 * (12 * Z + 70) + 30), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sh)
    d.text((10, 6), 'One battery design, 8x nearest-neighbour; the white fill is the app\'s progress bar drawn under the image.', fill=(255, 255, 255), font=ANN)
    y = 30
    for title, ims in rows:
        d.text((10, y), title, fill=(0xAA,) * 3, font=ANN); y += 22
        for i, (lab, im) in enumerate(ims):
            x = 10 + i * cw
            sh.paste(im.resize((im.width * Z, im.height * Z), Image.NEAREST).convert('RGB'), (x, y))
            d.text((x, y + im.height * Z + 4), lab, fill=(255, 255, 255), font=ANN)
        y += 12 * Z + 46
    sh.crop((0, 0, sh.width, y)).save(out); print('wrote', out)

if __name__ == '__main__': main()
