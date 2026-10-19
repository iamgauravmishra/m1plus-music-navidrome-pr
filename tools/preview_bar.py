#!/usr/bin/env python3
"""Rough mock of the 320x30 status bar for stock and the two battery variants (not pixel-exact AWTK)."""
import sys, os
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
IMG = sys.argv[1]; FONT = sys.argv[2]; OUT = sys.argv[3]; bars = sys.argv[4:]
SCALE = 3
def icon(name):
    for d in ('xx', 'x1', 'x2', 'x3'):
        p = os.path.join(IMG, d, name + '.png')
        if os.path.exists(p): return Image.open(p).convert('RGBA')
def render(binpath, pct=86, bt=True, wifi=True, charging=False):
    root = awtk_ui.parse(open(binpath, 'rb').read())
    im = Image.new('RGBA', (320, 30), (0, 0, 0, 255)); dr = ImageDraw.Draw(im)
    def place(ic, x, y=None):
        y = (30 - ic.height) // 2 if y is None else y
        im.alpha_composite(ic, (x, y))
    # left group: play icon, volume icon, volume number, then the clock
    place(icon('bar_play'), 14); place(icon('bar_vol3'), 14 + 14 + 4)
    f20 = ImageFont.truetype(FONT, 20); dr.text((14 + 14 + 4 + 24 + 4, 15), '50', font=f20, fill='white', anchor='lm')
    dr.text((108 + 45, 15), '12:34', font=f20, fill='white', anchor='mm')
    right = root.find('view_bar_right'); x = right.x + right.w
    for name, on in (('img_wifi', wifi), ('img_synclink', False), ('img_btclass', bt)):
        if not on: continue
        w = right.find(name); ic = icon(w.get('image')); x -= ic.width; place(ic, x); x -= 5
    pg = root.find('pgbar_battery'); img = root.find('img_battery')
    if img.get('visible', 'true') != 'false' and img.x >= 0:
        place(icon('bar_charge' if charging else 'bar_power'), img.x, img.y)
    if pg.get('show_text') == 'true':
        f = ImageFont.truetype(FONT, int(pg.get('style:normal:font_size', '18')))
        txt = pg.get('format', '%d%%') % pct
        al = pg.get('style:normal:text_align_h', 'center')
        ax = pg.x + pg.w if al == 'right' else pg.x if al == 'left' else pg.x + pg.w // 2
        dr.text((ax, pg.y + pg.h / 2), txt, font=f, fill='white', anchor={'right': 'rm', 'left': 'lm'}.get(al, 'mm'))
    else:  # stock: vertical fill inside the icon outline
        fh = int(pg.h * pct / 100); dr.rectangle([pg.x, pg.y + pg.h - fh, pg.x + pg.w - 1, pg.y + pg.h - 1], fill='white')
    return im
rows = []
for b in bars:
    for pct, bt, wifi in ((86, False, False), (100, True, True), (9, True, False)):
        rows.append((os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(b)))))))) + f'  {pct}% bt={bt} wifi={wifi}', render(b, pct, bt, wifi)))
H = 30 * SCALE + 14; out = Image.new('RGB', (320 * SCALE, H * len(rows)), (40, 40, 40)); d = ImageDraw.Draw(out)
for i, (label, im) in enumerate(rows):
    out.paste(im.resize((320 * SCALE, 30 * SCALE), Image.NEAREST), (0, i * H + 14)); d.text((4, i * H + 1), label, fill=(200, 200, 200))
out.save(OUT); print('wrote', OUT)
