#!/usr/bin/env python3
"""Approximate PIL mock-up of the library list pages, stock beside tools/mod_lists.py (not AWTK).

  preview_lists.py STOCK_WORKDIR MOD_WORKDIR OUT.png [--theme default|theme1]

The rows of these pages are built by demo's code, not by their ui/*.bin, so the page models below
copy the code's geometry (docs/ui.md: folder_create_tablerow, music_create_tablerow, the
navbar builders, search_page.bin) and take every colour, size and icon from the workdir's style
files the way this AWTK resolves them: the window's own theme (styles/<page>.bin) first, then
styles/default.bin. Text is sized like AWTK's stb backend (font_size = ascender - descender).
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui, awtk_style
from mod_lists import hexcol
from preview_lockscreen import Painter

W, H, BAR = 320, 480, 30
FOLDERS = ['Albums', 'Classical', 'Jazz', 'Live Recordings', 'Podcasts', 'Rock', 'Soundtracks']
SONGS = [('All Blues', 'Miles Davis'), ('Blue in Green', 'Miles Davis'), ('Freddie Freeloader', 'Miles Davis'),
         ('Moanin\'', 'Art Blakey'), ('My Favorite Things', 'John Coltrane'), ('Naima', 'John Coltrane'),
         ('Take Five', 'The Dave Brubeck Quartet')]

class Styles:
    """Style lookup as demo's AWTK does it: window theme, then default theme; state, then normal."""
    def __init__(self, work, theme, page):
        def load(t, name):
            p = os.path.join(work, 'rootfs/release/assets', t, 'raw/styles', name + '.bin')
            return {(s.widget, s.style, s.state): s for s in awtk_style.parse(open(p, 'rb').read()).items} if os.path.exists(p) else None
        self.win = load(theme, page) or (load('default', page) if theme != 'default' else None) or {}
        self.base = load(theme, 'default')
    def get(self, wt, name, state='normal'):
        for st in (state, 'normal'):
            for th in (self.win, self.base):
                s = th.get((wt, name, st))
                if s: return {k: v for k, _, v in s.props}
        return {}
    def color(self, wt, name, prop, state='normal', default=None):
        v = self.get(wt, name, state).get(prop)
        return hexcol(v) if v is not None else default
    def num(self, wt, name, prop, state='normal', default=0):
        v = self.get(wt, name, state).get(prop)
        return v if v is not None else default
    def str(self, wt, name, prop, state='normal'):
        v = self.get(wt, name, state).get(prop)
        return v if v is not None else ''

def rgba(c):
    c = c.lstrip('#'); return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4)) + ((int(c[6:8], 16),) if len(c) == 8 else (255,))

class Page:
    def __init__(self, painter, styles):
        self.p, self.s = painter, styles
        self.im = Image.new('RGBA', (W, H), (0, 0, 0, 255)); self.d = ImageDraw.Draw(self.im)
        self.d.text((W // 2 - 14, 9), '9:41', fill=(255, 255, 255))           # stand-in status bar
    def rect(self, x, y, w, h, color, radius=0, outline=None):
        if not color or rgba(color)[3] == 0: color = None
        if color is None and outline is None: return
        layer = Image.new('RGBA', (W, H)); ImageDraw.Draw(layer).rounded_rectangle(
            [x, y, x + w - 1, y + h - 1], radius=radius, fill=rgba(color) if color else None,
            outline=rgba(outline) if outline else None)
        self.im.alpha_composite(layer)
    def icon(self, name, x, y, w, h, at='center'):
        img = self.p.icon(name) if name else None
        if img is None: return
        ix = x if at == 'left' else x + (w - img.width) // 2
        iy = y + (h - img.height) // 2
        cx, cy = max(x, ix), max(y, iy)        # drawn 1:1, clipped to the widget like AWTK
        crop = img.crop((cx - ix, cy - iy, min(x + w, ix + img.width) - ix, min(y + h, iy + img.height) - iy))
        self.im.alpha_composite(crop, (cx, cy))
    def text(self, s, x, y, w, h, px, color, align='left'):
        f = self.p.font(px); tw = f.getlength(s)
        while tw > w and len(s) > 1: s = s[:-2] + '…'; tw = f.getlength(s)
        tx = x if align == 'left' else x + (w - tw) / 2 if align == 'center' else x + w - tw
        top = y + (h - px) / 2
        layer = Image.new('RGBA', (W, H)); ImageDraw.Draw(layer).text((tx, top + f.getmetrics()[0]), s, font=f, fill=rgba(color), anchor='ls')
        self.im.alpha_composite(layer.crop((x, y, x + w, y + h)), (x, y))
    def label(self, s, x, y, w, h, wt, style, state='normal', default_px=18):
        px = self.s.num(wt, style, 'font_size', state, default_px)
        al = {1: 'center', 2: 'left', 3: 'right'}.get(self.s.num(wt, style, 'text_align_h', state, 2), 'left')
        self.text(s, x, y, w, h, px, self.s.color(wt, style, 'text_color', state, '#444444'), al)
    def navbar(self, title, line=True, search=True):
        y = BAR
        self.icon(self.s.str('button', 'navbar_btnreturn_style', 'icon'), 0, y, 40, 50)
        self.label(title, 36, y + 14, 153, 22, 'hscroll_label', 'srlabel_leftwhite22_style')
        # the builder's buttons on the Pod navbar's slots (patch/rows.json): 168 / 214 (46 wide), Now Playing 260 (60 wide)
        if search: self.icon(self.s.str('button', 'search_style', 'bg_image'), 168, y, 46, 50)
        self.icon(self.s.str('button', 'navbar_btnmulselect_style', 'icon'), 214, y, 46, 50)
        self.icon(self.s.str('button', 'navbar_btnbackplayer_style', 'icon'), 260, y, 60, 50)
        if line: self.rect(0, y + 49, W, 1, self.s.color('view', 'navigationbar_line_style', 'border_color', default='#666666'))
    def table_row(self, y, h, pressed=False):
        self.rect(0, y, 310, h, self.s.color('button', 'btn_tablerow_style', 'bg_color', 'pressed' if pressed else 'normal'))

def folder_page(p, s):
    pg = Page(p, s); pg.navbar('Music', line=False)
    for i, name in enumerate(FOLDERS):
        y = BAR + 50 + i * 64
        if y >= BAR + 450: break
        pg.table_row(y, 60, pressed=(i == 3))
        playing = i == 1
        pg.icon('icon_playing' if playing else 'icon_folder', 12, y, 40, 60)
        pg.label(name, 60, y, 200, 60, 'hscroll_label', 'srlabel_item_gold20_style' if playing else 'srlabel_item_white_style')
        pg.icon(s.str('button', 'btn_rightarrow_style', 'icon'), 268, y, 13, 60)
    return pg.im

def songs_page(p, s, ui):
    pg = Page(p, s); pg.navbar('All Songs')
    for i, (title, artist) in enumerate(SONGS):
        y = BAR + 50 + i * 60
        if y >= BAR + 450: break
        pg.table_row(y, 56, pressed=(i == 4))
        playing = i == 2
        pg.icon('icon_playing' if playing else 'albumcover_s', 12, y, 40, 56)
        pg.label(title, 60, y + 10, 200, 20, 'hscroll_label', 'srlabel_item_gold20_style' if playing else 'srlabel_item_white_style')
        if i == 5:   # a row whose data has not loaded yet keeps the creation style (gray26)
            pg.label(artist, 60, y + 30, 175, 26, 'hscroll_label', 'srlabel_item_gray26_style')
        else:
            pg.label(artist, 60, y + 30, 175, 26, 'hscroll_label', 'srlabel_item_gold18_style' if playing else 'srlabel_item_gray18_style')
    v = ui.find('view_letter'); lab = ui.find('label_letter')
    x, y = v.x, BAR + v.y
    img = v.get('style:normal:bg_image')
    if img: pg.icon(img, x, y, v.w, v.h)
    else: pg.rect(x, y, v.w, v.h, v.get('style:normal:bg_color'), int(v.get('style:normal:round_radius', '0')),
                  v.get('style:normal:border_color'))
    pg.text('M', x, y, v.w, v.h, int(lab.get('style:normal:font_size')), lab.get('style:normal:text_color'), 'center')
    return pg.im

def search_page(p, s, ui):
    pg = Page(p, s); y0 = BAR
    pg.icon(s.str('button', 'navbar_btnreturn_style', 'icon'), 0, y0, 40, 50)
    pg.icon('search_bg', 33, y0 + 6, 240, 38)
    pg.text('Search music, albums, artists', 48, y0 + 6, 210, 38, 18, '#AAAAAA')
    tabs = [('Songs', 0, 108, 'normal_of_active'), ('Artists', 214, 106, 'normal'), ('Albums', 108, 106, 'pressed')]
    for name, x, w, st in tabs:
        y = y0 + 50
        pg.rect(x, y, w, 44, s.color('tab_button', 'btn_tab_style', 'bg_color', st))
        b = s.num('tab_button', 'btn_tab_style', 'border', st, 0)
        if b & 8:
            bw = s.num('tab_button', 'btn_tab_style', 'border_width', st, 1)
            pg.rect(x, y + 44 - bw, w, bw, s.color('tab_button', 'btn_tab_style', 'border_color', st))
        pg.text(name, x, y, w, 44, s.num('tab_button', 'btn_tab_style', 'font_size', st, 18),
                s.color('tab_button', 'btn_tab_style', 'text_color', st, '#FFFFFF'), 'center')
    pg.rect(0, y0 + 94, W, 4, '#000000')
    for i, (title, artist) in enumerate(SONGS[:5]):
        y = y0 + 98 + i * 64
        pg.rect(0, y, 310, 60, s.color('list_item', 'list_item_style', 'bg_color'))
        pg.icon('albumcover_s', 12, y, 40, 60)
        pg.label(title, 60, y + 10, 200, 20, 'hscroll_label', 'srlabel_item_white_style')
        pg.label(artist, 60, y + 32, 200, 20, 'hscroll_label', 'srlabel_item_gray18_style')
    return pg.im

def panels(work, theme):
    raw = os.path.join(work, 'rootfs/release/assets/default/raw')
    p = Painter(raw, False)
    ui = awtk_ui.parse(open(os.path.join(raw, 'ui/allmusic_page.bin'), 'rb').read())
    return [folder_page(p, Styles(work, theme, 'folder_page')),
            songs_page(p, Styles(work, theme, 'allmusic_page'), ui),
            search_page(p, Styles(work, theme, 'search_page'), None)]

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stock'); ap.add_argument('mod'); ap.add_argument('out')
    ap.add_argument('--theme', default='default', choices=['default', 'theme1'])
    a = ap.parse_args()
    rows = [('stock', panels(a.stock, a.theme)), ('mod', panels(a.mod, a.theme))]
    names = ['Folders (pressed row 4)', 'Songs + index letter', 'Search tabs']
    pad, top = 10, 34
    out = Image.new('RGB', (3 * (W + pad) + pad, 2 * (H + top) + 22), (40, 40, 40)); d = ImageDraw.Draw(out)
    for r, (label, ims) in enumerate(rows):
        for c, im in enumerate(ims):
            x, y = pad + c * (W + pad), r * (H + top) + top
            out.paste(im.convert('RGB'), (x, y)); d.text((x, y - 16), f'{label}: {names[c]}', fill=(230, 230, 230))
    d.text((pad, out.height - 16), f'approximate PIL mock-up of code-built rows (not AWTK); theme {a.theme}; '
           'colours/sizes/icons read from each tree\'s styles', fill=(160, 160, 160))
    out.quantize(colors=128).save(a.out, optimize=True); print('wrote', a.out)   # a palette PNG keeps docs/ small

if __name__ == '__main__': main()
