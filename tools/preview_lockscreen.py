#!/usr/bin/env python3
"""Approximate PIL mock-up of the 320x480 lock screen (ui/screensaver_page.bin); not pixel-exact AWTK.

  preview_lockscreen.py RAW_DIR OUT.png LABEL=UI.bin[,pct=N][,charging][,idle][,raw=DIR] ...  [--wallpaper]

RAW_DIR is rootfs/release/assets/default/raw (images/, fonts/default.ttf, styles/); raw=DIR overrides it
for one panel (e.g. a "before" tree). Text is sized like AWTK's stb font backend (font_size = ascender -
descender) and placed by its middle/left/right rules. Button icons come from the page theme
(styles/screensaver_page.bin, then default.bin) like AWTK's window theme lookup.
App-driven content is sample data: the cover is a synthetic picture, title/artist sample strings;
`idle` draws the nothing-queued state (the app hides view_bottomview). The wallpaper is app-driven too;
by default a plain gradient stands in for it (--wallpaper uses the stock image, handy locally, not for
committing).
"""
import argparse, datetime, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui, awtk_style

W, H = 320, 480
NOW = datetime.datetime(2026, 10, 19, 9, 41, 7)
MONTHS = 'Jan Feb Mar Apr May Jun Jul Aug Sept Oct Nov Dec'.split()             # demo's MMM table
WDAYS = 'Sunday Monday Tuesday Wednesday Thursday Friday Saturday'.split()    # demo: W = full English name

def fmt_time(fmt, t):
    """digit_clock formatting as implemented by the M1 Plus AWTK build (see mod_lockscreen.py)."""
    out, i = '', 0
    while i < len(fmt):
        c = fmt[i]; n = 1
        while i + n < len(fmt) and fmt[i + n] == c: n += 1
        h12 = t.hour % 12 or 12
        v = {'Y': (t.year % 100 if n == 2 else t.year), 'M': t.month, 'D': t.day, 'h': t.hour, 'H': t.hour,
             'm': t.minute, 's': t.second, 'T': t.minute, 'w': (t.weekday() + 1) % 7}.get(c)
        if c == 'H' and n == 2: out += f'{h12:02d}'
        elif c == 'T' and n == 2: out += f'{t.minute:02d} ' + ('AM' if t.hour < 12 else 'PM')
        elif c == 'M' and n == 3: out += MONTHS[t.month - 1]
        elif c == 'W': out += WDAYS[(t.weekday() + 1) % 7]
        elif v is not None: out += f'{v:02d}' if n == 2 and c != 'w' else str(v)
        else: out += c * n
        i += n
    return out

TITLE, ARTIST = 'Harvest Moon', 'Neil Young'

class Theme:
    """Button styles from the page theme (styles/screensaver_page.bin), then default.bin."""
    def __init__(self, raw):
        self.sets = [awtk_style.parse(open(p, 'rb').read()).items for p in
                     (os.path.join(raw, 'styles', f) for f in ('screensaver_page.bin', 'default.bin')) if os.path.exists(p)]
    def get(self, wtype, style, state, prop):
        for items in self.sets:
            hit = [it for it in items if it.widget == wtype and it.style == style and it.state == state]
            if hit: return hit[0].get(prop)          # the first theme that defines the style wins (as AWTK)
        return None

def synthetic_cover(w, h):
    im = Image.new('RGBA', (w, h)); d = ImageDraw.Draw(im)
    for y in range(h): d.line([(0, y), (w, y)], fill=(20 + y * 60 // h, 30 + y * 20 // h, 70 + y * 90 // h))
    d.ellipse([w * .18, h * .2, w * .82, h * .84], outline=(240, 200, 120), width=max(2, w // 60))
    d.polygon([(w * .5, h * .3), (w * .72, h * .7), (w * .28, h * .7)], fill=(250, 250, 245))
    return im

class Painter:
    def __init__(self, raw, wallpaper):
        self.raw, self.wallpaper, self.theme = raw, wallpaper, Theme(raw)
        self.font_path = os.path.join(raw, 'fonts', 'default.ttf')
        a, d = ImageFont.truetype(self.font_path, 1000).getmetrics()
        self.k = 1000 / (a + d)                     # PIL size per AWTK font_size px
        self.fonts = {}
    def font(self, px):
        if px not in self.fonts: self.fonts[px] = ImageFont.truetype(self.font_path, px * self.k)
        return self.fonts[px]
    def icon(self, name):
        if not name: return None
        for d in ('xx', 'x1', 'x2', 'x3'):
            p = os.path.join(self.raw, 'images', d, name + '.png')
            if os.path.exists(p): return Image.open(p).convert('RGBA')
    def text(self, im, clip, r, s, wd):
        px = int(wd.get('style:normal:font_size', '18'))
        f = self.font(px); tw = f.getlength(s)
        ah, av = wd.get('style:normal:text_align_h', 'center'), wd.get('style:normal:text_align_v', 'middle')
        x = r[0] if ah == 'left' or tw > r[2] else r[0] + r[2] - tw if ah == 'right' else r[0] + (r[2] - tw) / 2
        top = r[1] if av == 'top' else r[1] + r[3] - px if av == 'bottom' else r[1] + (r[3] - px) // 2
        layer = Image.new('RGBA', (W, H)); ImageDraw.Draw(layer).text((x, top + f.getmetrics()[0]), s, font=f,
                                                                   fill=wd.get('style:normal:text_color', '#FFFFFF'), anchor='ls')
        im.alpha_composite(layer.crop(clip), clip[:2])
    def render(self, root, pct, charging, idle):
        if self.wallpaper:
            im = self.icon('screensaver_default').resize((W, H))
        else:
            im = Image.new('RGBA', (W, H))
            for y in range(H):
                ImageDraw.Draw(im).line([(0, y), (W, y)], fill=(30 + y // 12, 45 + y // 10, 90 + y // 8))
        self.walk(im, root, 0, 0, (0, 0, W, H), pct, charging, idle)
        return im
    def walk(self, im, wd, ox, oy, clip, pct, charging, idle):
        if wd.get('visible') == 'false' or idle and wd.name == 'view_bottomview': return
        r = (ox + wd.x, oy + wd.y, wd.w or W, wd.h or H)
        c = (max(clip[0], r[0]), max(clip[1], r[1]), min(clip[2], r[0] + r[2]), min(clip[3], r[1] + r[3]))
        if c[0] >= c[2] or c[1] >= c[3]: return
        dr = ImageDraw.Draw(im); t, name = wd.type, wd.name
        bg = wd.get('style:normal:bg_color')
        if t == 'view' and bg and len(bg) == 7:
            rad = int(wd.get('style:normal:round_radius', '0'))
            if rad: dr.rounded_rectangle([r[0], r[1], r[0] + r[2] - 1, r[1] + r[3] - 1], radius=rad, fill=bg)
            else: dr.rectangle([c[0], c[1], c[2] - 1, c[3] - 1], fill=bg)
        if t == 'image' and name != 'img_screensaver':
            img = synthetic_cover(254, 254) if name == 'view_img_icon' else \
                self.icon('screens_charge' if name == 'img_battery' and charging else wd.get('image'))
            if img:
                if wd.get('draw_type') == 'scale_auto': img = img.resize((r[2], r[3]), Image.LANCZOS)
                im.alpha_composite(img.crop((c[0] - r[0], c[1] - r[1], c[2] - r[0], c[3] - r[1])), c[:2])
        elif t == 'digit_clock':
            self.text(im, c, r, fmt_time(wd.get('format', 'hh:mm:ss'), NOW), wd)
        elif t == 'hscroll_label':
            self.text(im, c, r, {'view_scrlabel_title': TITLE, 'view_scrlabel_artist': ARTIST}.get(name, wd.get('text', '')), wd)
        elif t == 'progress_bar':
            if wd.get('show_text') == 'true': self.text(im, c, r, wd.get('format', '%d%%') % pct, wd)
            else: dr.rectangle([r[0], r[1], r[0] + r[2] * pct // 100 - 1, r[1] + r[3] - 1], fill=wd.get('style:normal:fg_color', '#FFFFFF'))
        elif t == 'button':
            img = self.icon(wd.get('style:normal:bg_image') or self.theme.get('button', wd.get('style', 'default'), 'normal', 'icon'))
            if img: im.alpha_composite(img, (r[0] + (r[2] - img.width) // 2, r[1] + (r[3] - img.height) // 2))
        for ch in wd.children: self.walk(im, ch, r[0], r[1], c, pct, charging, idle)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('raw'); ap.add_argument('out'); ap.add_argument('panels', nargs='+')
    ap.add_argument('--wallpaper', action='store_true')
    a = ap.parse_args()
    painters, shots = {}, []
    for spec in a.panels:
        label, rest = spec.split('=', 1); path, *opts = rest.split(',')
        pct = next((int(o[4:]) for o in opts if o.startswith('pct=')), 86); charging, idle = 'charging' in opts, 'idle' in opts
        raw = next((o[4:] for o in opts if o.startswith('raw=')), a.raw)
        p = painters.setdefault(raw, Painter(raw, a.wallpaper))
        state = 'nothing queued' if idle else f'{pct}%{", charging" if charging else ""}'
        shots.append((f'{label}  ({state})', p.render(awtk_ui.parse(open(path, 'rb').read()), pct, charging, idle)))
    top, pad = 18, 10
    out = Image.new('RGB', (len(shots) * (W + pad) + pad, H + top + 18), (40, 40, 40)); d = ImageDraw.Draw(out)
    for i, (label, im) in enumerate(shots):
        x = pad + i * (W + pad); out.paste(im.convert('RGB'), (x, top)); d.text((x, 3), label, fill=(220, 220, 220))
    d.text((pad, H + top + 3), f'approximate PIL mock-up, not AWTK; sample time {NOW:%Y-%m-%d %H:%M}, synthetic cover; wallpaper '
           + ('stock' if a.wallpaper else 'replaced by a gradient (app-driven)'), fill=(160, 160, 160))
    out.save(a.out, optimize=True); print('wrote', a.out)

if __name__ == '__main__': main()
