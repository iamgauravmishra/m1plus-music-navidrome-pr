#!/usr/bin/env python3
"""PIL mock-up of the theme mod next to its base: status bar, System settings list, Home and a
track list, drawn from each tree's own styles/default.bin, system_bar.bin, home_page.bin and
images. Approximate (not AWTK): fonts use AWTK's size rule, layouts are simplified.

Usage: preview_theme.py BASE_WORKDIR MOD_WORKDIR OUT.png [--labels "stock|theme"]
"""
import argparse, os, struct, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_style, awtk_ui

RAW = 'rootfs/release/assets/default/raw'
W, H, BAR, NAV = 320, 480, 30, 50

def rgba(s):
    h = s.lstrip('#'); h = h + 'FF' if len(h) == 6 else h
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4, 6))

class Tree:
    def __init__(self, root):
        self.raw = os.path.join(root, RAW)
        self.th = awtk_style.parse(open(f'{self.raw}/styles/default.bin', 'rb').read())
        self.bar = awtk_ui.parse(open(f'{self.raw}/ui/system_bar.bin', 'rb').read())
        self.home = awtk_ui.parse(open(f'{self.raw}/ui/home_page.bin', 'rb').read())
        ttf = f'{self.raw}/fonts/default.ttf'; d = open(ttf, 'rb').read()
        n = struct.unpack_from('>H', d, 4)[0]
        t = {d[12 + 16 * i:16 + 16 * i]: struct.unpack_from('>I', d, 20 + 16 * i)[0] for i in range(n)}
        em = struct.unpack_from('>H', d, t[b'head'] + 18)[0]
        asc, desc = struct.unpack_from('>hh', d, t[b'hhea'] + 4)
        self.ttf, self.k, self.fonts = ttf, em / (asc - desc), {}
    def font(self, px):     # AWTK (stb) font_size = ascender - descender in px
        if px not in self.fonts: self.fonts[px] = ImageFont.truetype(self.ttf, round(px * self.k))
        return self.fonts[px]
    def img(self, name):
        p = f'{self.raw}/images/xx/{name}.png'
        return Image.open(p).convert('RGBA') if os.path.exists(p) else None
    def style(self, widget, style, state, key):
        it = self.th.find(widget, style, state) or self.th.find(widget, style, 'normal')
        v = it[0].color(key) if it else None
        return rgba(v) if v else None

def text(dr, t, xy, s, px, col, anchor='lm'):
    dr.text(xy, s, font=t.font(px), fill=col, anchor=anchor)

def paste(im, ic, x, y):
    if ic: im.alpha_composite(ic, (int(x), int(y)))

def status_bar(im, t, pct=86):
    dr = ImageDraw.Draw(im); b = t.bar
    dr.rectangle((0, 0, W - 1, BAR - 1), fill=rgba(b.get('style:normal:bg_color', '#000000')))
    left = b.find('view_bar_left'); lay = left.get('children_layout')
    x = int(lay.split('x=')[1].split(',')[0]); gap = int(lay.split('s=')[1].rstrip(')'))
    vol = b.find('label_volume'); vpx = int(vol.get('style:normal:font_size'))
    for name in ('bar_play', 'bar_vol3'):
        ic = t.img(name); paste(im, ic, x, (BAR - ic.height) // 2); x += ic.width + gap
    text(dr, t, (x, BAR / 2), '50', vpx, (255, 255, 255, 255))
    c = b.find('bar_dclock'); text(dr, t, (c.x + c.w / 2, BAR / 2), '12:59 PM', int(c.get('style:normal:font_size')), (255, 255, 255, 255), 'mm')
    right = b.find('view_bar_right'); s = int(right.get('children_layout').split('s=')[1].rstrip(')'))
    x = right.x + right.w
    for name, img in (('img_wifi', 'bar_wifi3'), ('img_btclass', 'bar_btcon')):
        ic = t.img(img); w = right.find(name).w; x -= w; paste(im, ic, x + w - ic.width, (BAR - ic.height) // 2); x -= s
    pg, bat = b.find('pgbar_battery'), b.find('img_battery')
    paste(im, t.img('bar_power'), bat.x, bat.y)
    text(dr, t, (pg.x + pg.w, pg.y + pg.h / 2), f'{pct}%', int(pg.get('style:normal:font_size')), (255, 255, 255, 255), 'rm')

def navbar(im, t, title):
    dr = ImageDraw.Draw(im)
    paste(im, t.img('return'), 14, BAR + 14)
    text(dr, t, (36, BAR + 25), title, 22, t.style('label', 'navbar_label_white', 'normal', 'text_color'))
    paste(im, t.img('back_to_player'), 278, BAR + 13)

def row_bg(dr, t, widget, style, y, h, pressed=False):
    st = 'pressed' if pressed else 'normal'
    dr.rectangle((0, y, W - 1, y + h - 1), fill=t.style(widget, style, st, 'bg_color'))
    it = (t.th.find(widget, style, st) or t.th.find(widget, style, 'normal'))[0]
    bw, bc = it.get('border_width', 0), t.style(widget, style, st, 'border_color')
    if bc and bc[3] and bw and it.get('border', 15) & 8:          # 8 = bottom
        dr.rectangle((0, y + h - bw, W - 1, y + h - 1), fill=bc)

def settings(t):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255)); dr = ImageDraw.Draw(im)
    status_bar(im, t); navbar(im, t, 'System Settings')
    rows = [('sset_about', 'About'), ('sset_display', 'Display'), ('system_language', 'Language'),
            ('system_time', 'Date & Time'), ('sset_screenlock', 'Screen lock'), ('sset_theme', 'Theme'),
            ('sset_powermanager', 'Power')]
    col = t.style('hscroll_label', 'srlabel_leftwhite21_style', 'normal', 'text_color')
    for i, (ic, label) in enumerate(rows):
        y = BAR + NAV + i * 64
        row_bg(dr, t, 'list_item', 'list_item_style', y, 64, pressed=(i == 1))
        paste(im, t.img(ic), 12, y + 12)
        text(dr, t, (64, y + 32), label, 21, col)
        paste(im, t.img('right_arrow'), 292, y + 21)
    return im

def home(t):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255)); dr = ImageDraw.Draw(im)
    status_bar(im, t)
    items = [('tidal', 'TIDAL'), ('sset_updatemusic', 'Update Library'), ('mymusic', 'All Songs'),
             ('folder', 'Folders'), ('album', 'Albums'), ('songer', 'Artists')]
    for i, (ic, label) in enumerate(items):
        cx, cy = 60 + (i % 3) * 100, BAR + 30 + (i // 3) * 150
        paste(im, t.img(ic), cx - 33, cy); text(dr, t, (cx, cy + 90), label, 18, (255, 255, 255, 255), 'mm')
    h = t.home; dots = h.find('home_sindicator')
    for k in range(3):
        c = rgba(dots.get('style:normal:selected_fg_color') if k == 0 else dots.get('style:normal:fg_color'))
        x = W / 2 + (k - 1) * 14; dr.ellipse((x - 3, BAR + 364, x + 3, BAR + 370), fill=c)
    strip = h.find('home_bottomview'); y = BAR + 384
    dr.rectangle((0, y, W - 1, y + 65), fill=rgba(strip.get('style:normal:bg_color')))
    if strip.get('style:normal:border') == 'top':
        dr.rectangle((0, y, W - 1, y + int(strip.get('style:normal:border_width')) - 1), fill=rgba(strip.get('style:normal:border_color')))
    paste(im, t.img('defaultcover'), 0, y)
    ti, ar = h.find('home_scrlabel_title'), h.find('home_scrlabel_artist')
    text(dr, t, (ti.x, y + ti.y + ti.h / 2), 'Life is short, Play more.', 20, rgba(ti.get('style:normal:text_color')))
    text(dr, t, (ar.x, y + ar.y + ar.h / 2), 'Shanling', 16, rgba(ar.get('style:normal:text_color')))
    return im

def tracks(t):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255)); dr = ImageDraw.Draw(im)
    status_bar(im, t); navbar(im, t, 'Album')
    names = ['Intro', 'So What', 'Freddie Freeloader', 'Blue in Green', 'All Blues', 'Flamenco Sketches']
    for i, n in enumerate(names):
        y = BAR + NAV + i * 64
        row_bg(dr, t, 'button', 'btn_tablerow_style', y, 64, pressed=(i == 4))
        playing = i == 2
        st = 'srlabel_item_gold20_style' if playing else 'srlabel_item_white_style'
        if playing: paste(im, t.img('icon_playing'), 8, y + 12)
        text(dr, t, (56, y + 24), n, 20, t.style('hscroll_label', st, 'normal', 'text_color'))
        text(dr, t, (56, y + 46), 'Miles Davis', 16, t.style('hscroll_label', 'srlabel_leftgray16_style', 'normal', 'text_color'))
    # the lyric view's current line vs the others
    y = BAR + NAV + 6 * 64 + 4
    text(dr, t, (W / 2, y + 2), 'previous lyric line', 18, t.style('list_item', 'listitem_lyric_style', 'normal', 'text_color'), 'mt')
    return im

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('base'); ap.add_argument('mod'); ap.add_argument('out'); ap.add_argument('--labels', default='base|theme')
    a = ap.parse_args()
    labels = a.labels.split('|')
    trees = [Tree(a.base), Tree(a.mod)]
    pad, head = 12, 22
    out = Image.new('RGB', (3 * W + 4 * pad, 2 * (H + head) + 3 * pad), (48, 48, 48)); d = ImageDraw.Draw(out)
    for r, (t, lab) in enumerate(zip(trees, labels)):
        y = pad + r * (H + head + pad)
        for c, (fn, cap) in enumerate(((settings, 'settings (Display pressed)'), (home, 'Home'), (tracks, 'track list (playing, pressed)'))):
            x = pad + c * (W + pad)
            d.text((x, y + 4), f'{lab}: {cap}', fill=(230, 230, 230), font=trees[0].font(14))
            out.paste(fn(t).convert('RGB'), (x, y + head))
    out.save(a.out, optimize=True); print('wrote', a.out)

if __name__ == '__main__': main()
