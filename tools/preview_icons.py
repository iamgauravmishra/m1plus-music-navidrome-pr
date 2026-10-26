#!/usr/bin/env python3
"""out/preview/icons.png: the icon set before (the stock tree) and after (the release tree), 1:1 device pixels, with a
3x zoom strip. Markers on the "after" side: blue C = custom Tabler-style SVG, orange K = stock image kept.

  preview_icons.py BEFORE_TREE AFTER_TREE OUT.png        (unpacked work trees; venv python)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import mod_icons as M
import awtk_strings
from stb_raster import StbFont

RAW = 'rootfs/release/assets/default/raw'
W, BAR = 320, 30
WHITE = (255, 255, 255)
ANN = ImageFont.load_default(13); ANN_B = ImageFont.load_default(16)

class Side:
    def __init__(self, tree, after, locale='en_US'):
        self.tree = tree; self.d = os.path.join(tree, RAW, 'images/xx'); self.after = after
        self.font = StbFont(os.path.join(tree, RAW, 'fonts/default.ttf'))
        self.strings = dict(awtk_strings.load(os.path.join(tree, RAW, 'strings', locale + '.bin')))   # the language shown (a strings table name)
    def shown(self, w):
        """The text of an asset widget as the app shows it: its tr_text key through the language's table (the key itself
        when the table lacks it, as locale_info_tr does), else its text."""
        k = w.get('tr_text')
        return self.strings.get(k, k) if k is not None else w.get('text')
    def clip(self, text, px, room):
        """An hscroll_label that is not scrolling: the text cut with an ellipsis where it passes its box."""
        while self.font.width(text, px) > room and len(text) > 1: text = text[:-2] + '…' if text.endswith('…') else text[:-1] + '…'
        return text
    def img(self, n): return Image.open(os.path.join(self.d, n + '.png')).convert('RGBA')
    def text(self, im, x, y_mid, s, px, rgb=WHITE, anchor='l'):
        w = self.font.width(s, px)
        if anchor == 'm': x -= w // 2
        elif anchor == 'r': x -= w
        self.font.draw(im, int(x), int(y_mid - px / 2), s, px, rgb + (255,))
    def mark(self, im, name, x, y):
        """C / K marker for custom / kept-stock icons (after side only)."""
        if not self.after: return
        kind = KIND.get(name)
        if kind:
            ImageDraw.Draw(im).text((x, y), kind, fill=(90, 170, 255) if kind == 'C' else (255, 150, 40), font=ANN)

def kinds():
    k = {}
    for n, _, g in M.HOME + M.SETTINGS + M.LISTS:
        if g is None: k[n] = 'K'
        elif M.is_custom(g): k[n] = 'C'; k[n + '_down'] = 'C'
    k['m1pod'] = 'C'
    for n, g in list(M.PULLDOWN.items()) + list(M.STATUS.items()):
        if M.is_custom(g): k[n] = 'C'
    return k
KIND = kinds()

def status_bar(s, im, y0=0, bg=(0, 0, 0), vol='50', pct='86%'):
    ImageDraw.Draw(im).rectangle((0, y0, W - 1, y0 + BAR - 1), fill=bg)
    x = 10
    for n in ('bar_play', 'bar_vol3'):
        ic = s.img(n); im.alpha_composite(ic, (x, y0 + (BAR - ic.height) // 2)); x += ic.width + 4
    s.text(im, x, y0 + BAR / 2, vol, 16); s.text(im, 149, y0 + BAR / 2, '12:59 PM', 18, anchor='m')
    im.alpha_composite(s.img('bar_btcon'), (173, y0 + 5)); im.alpha_composite(s.img('bar_wifi3'), (224, y0 + 7))
    s.text(im, 292, y0 + BAR / 2, pct, 16, anchor='r'); im.alpha_composite(s.img('bar_power'), (296, y0 + 8))

def home(s, page):
    """A Home page (English: ids 1..17, 6 per page). The sixth slot of page 3 is the M1 Pod icon patch/home.c adds
    (after side); the stock side shows the HiFi store there (zh_CN only), the way the old preview did."""
    im = Image.new('RGBA', (W, 330), (0, 0, 0, 255)); status_bar(s, im)
    tiles = [t for t in M.HOME if t[0] != 'hifimusic'] + [('m1pod' if s.after else 'hifimusic', 'M1 Pod', None)]
    for i, (n, label, g) in enumerate(tiles[page * 6:(page + 1) * 6]):
        cx, cy = 60 + (i % 3) * 100, BAR + 24 + (i // 3) * 140
        if n == 'hifimusic': label = 'HiFi (zh_CN)'
        im.alpha_composite(s.img(n), (cx - 33, cy)); s.mark(im, n, cx - 33, cy)
        px = 18
        while s.font.width(label, px) > 98 and px > 12: px -= 1
        s.text(im, cx, cy + 86, label, px, anchor='m')
    return im

def settings(s):
    cell = 45; im = Image.new('RGBA', (W, 7 * cell + 6), (0, 0, 0, 255))
    for k, (n, _, g) in enumerate(M.SETTINGS):
        x, y = (k % 7) * 45 + 4, (k // 7) * cell + 4
        im.alpha_composite(s.img(n), (x, y)); s.mark(im, n, x + 30, y - 3)
    return im

def pulldown(s):
    im = Image.new('RGBA', (W, 290), (0x14, 0x14, 0x14, 255)); status_bar(s, im, bg=(0x14, 0x14, 0x14), vol='100')
    tiles = [('drop_wifiopen', 'Wi-Fi'), ('drop_bt', 'Bluetooth'), ('drop_keylockopen', 'Key lock'), ('drop_eqopen', 'EQ'),
             ('drop_usbaudio', 'USB audio'), ('drop_usbdac', 'USB DAC'), ('drop_usbstorage', 'USB storage'),
             ('drop_playset', 'Play set'), ('drop_syssetdown', 'Settings (off)'), ('drop_wifi', 'Wi-Fi (off)'),
             ('drop_keylock', 'Lock (off)'), ('drop_btopen', 'BT (on)')]
    for k, (n, label) in enumerate(tiles):
        x, y = 12 + (k % 4) * 76, 40 + (k // 4) * 78
        im.alpha_composite(s.img(n), (x, y)); s.mark(im, n.replace('open', ''), x + 38, y)
        s.text(im, x + 25, y + 62, label, 12, anchor='m')
    for n, x in (('drop_lighticon0', 30), ('drop_lighticon1', 270)):
        im.alpha_composite(s.img(n), (x, 262))
    return im

def lists(s):
    im = Image.new('RGBA', (W, 70), (0, 0, 0, 255)); x = 6
    for n in ('icon_folder', 'icon_playlist', 'icon_artist', 'icon_genre', 'icon_composer', 'icon_cdalbum'):
        im.alpha_composite(s.img(n), (x, 6)); s.mark(im, n, x + 26, 2); x += 42
    x = 6
    for n in M.COVERS[:1]:
        im.alpha_composite(s.img(n), (258, 6)); x += 70
    return im

def title_px(tree):
    """The navbar title size: the tree's navbar_label_white style (22 stock, 20 since V2.1jA)."""
    import awtk_style
    th = awtk_style.parse(open(os.path.join(tree, RAW, 'styles/default.bin'), 'rb').read())
    return th.find('label', 'navbar_label_white', 'normal')[0].get('font_size')

def home_pad():
    """HOME_PAD of patch/offsets.inc: the Home instance's air above the first and below the last row."""
    import re
    m = re.search(r'#define HOME_PAD (\d+)', open(os.path.join(M.ROOT, 'patch', 'offsets.inc')).read())
    return int(m.group(1))

def pod_page(s, key, tree_rows=8, home=False, first=0, title=None, icon=None, order=None, switches=None, arrows=None, values=None):
    """A mock of an M1 Pod rows page from the tree's ui asset: navbar title, then each list_item row
    (icon image, label, chevron) on black with the 1 px #222222 hairline. home=True: the Home instance of the
    menu, no navbar at all (the payload hides it) and the list from y HOME_PAD to HOME_PAD above the 450 px window's bottom.
    title / icon: what the payload sets at run time (the Artists page's title and toggle glyph); the toggle button, if the
    asset has one (btn_artisttype), is drawn centred in its place.
    order: the row names top to bottom as patch/menu.c arranged them (hidden rows are left out; default: the asset's order);
    switches: {switch image name: on} (the Settings and Main Menu pages set them at run time); arrows: the up-arrow buttons shown;
    values: {value label name: text} (the Cover Flow settings page's Sort value, as the payload sets it)."""
    import awtk_ui
    root = awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', key + '.bin'), 'rb').read())
    pad = home_pad()
    top = pad if home else 50
    im = Image.new('RGBA', (W, 450 if home else 50 + tree_rows * 52), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    if not home:
        lt = next(w for w in root.walk() if w.name == 'label_title')
        title = title or s.shown(lt)
        s.text(im, 36, 25, s.clip(title, title_px(s.tree), lt.w), title_px(s.tree))
        im.alpha_composite(s.img('return'), (14, 14))
        im.alpha_composite(s.img('back_to_player'), (278, 13))
        tog = next((w for w in root.walk() if w.name == 'btn_artisttype'), None)
        if tog:
            ic = s.img(icon or tog.get('style:normal:icon'))
            im.alpha_composite(ic, (tog.x + (tog.w - ic.width) // 2, (tog.h - ic.height) // 2))
    items = [w for w in root.walk() if w.type == 'list_item']
    if order is not None: items = [next(w for w in items if w.name == n) for n in order]
    items = items[first:first + tree_rows]
    for k, r in enumerate(items):
        y = top + (k * 52 if order is not None else r.y - (items[0].y if first else 0))
        if y >= im.height: break
        d.rectangle((0, y + 51, W - 1, y + 51), fill=(0x22, 0x22, 0x22))
        for c in r.children:
            if c.type == 'hscroll_label': s.text(im, c.x, y + 26, s.clip(s.shown(c), 21, c.w), 21)
            elif c.type == 'image' and c.name.startswith('pod_switch'):
                on = (switches or {}).get(c.name, c.get('image') == 'sset_on')
                im.alpha_composite(s.img('sset_on' if on else 'sset_off'), (c.x, y + c.y))
            elif c.type == 'label' and c.name.startswith('pod_value'):   # a value row's grey value, right aligned (the payload sets its text by key)
                text = (values or {}).get(c.name) or s.shown(c)
                s.text(im, c.x + c.w, y + 26, text, int(c.get('style:normal:font_size')), (0xAA,) * 3, 'r')
            elif c.type == 'button':
                if arrows is None or c.name in arrows:
                    ic = s.img(c.get('style:normal:icon')); im.alpha_composite(ic, (c.x + (c.w - ic.width) // 2, y + (c.h - ic.height) // 2))
            elif c.type == 'image' and c.get('image') != 'right_arrow': im.alpha_composite(s.img(c.get('image')), (c.x, y + c.y))
            elif c.type == 'image': im.alpha_composite(s.img(c.get('image')), (c.x + 8, y + 16))
    if home: d.rectangle((0, 450 - pad, W - 1, 449), fill=(0, 0, 0))     # the list ends HOME_PAD above the screen edge
    return im

def offsets():
    """The numeric #defines of patch/offsets.inc (the Albums grid's geometry)."""
    import re
    return {m.group(1): int(m.group(2), 0) for m in re.finditer(r'^#define (\w+) (-?(?:0x[0-9a-fA-F]+|\d+))u?\b', open(os.path.join(M.ROOT, 'patch', 'offsets.inc')).read(), re.M)}

ALBUMS = [('Kind of Blue', 'Miles Davis', (70, 110, 190)), ('A Love Supreme', 'John Coltrane', (190, 140, 60)),
          ('Abbey Road', 'The Beatles', (90, 160, 110)), ('The Dark Side of the Moon', 'Pink Floyd', (60, 40, 110)),
          ('Rumours', 'Fleetwood Mac', (170, 90, 80)), ('Thriller', 'Michael Jackson', None),
          ('OK Computer', 'Radiohead', (110, 130, 150)), ('Blue', 'Joni Mitchell', (50, 90, 170)),
          ('Nevermind', 'Nirvana', (60, 150, 190)), ('Pet Sounds', 'The Beach Boys', (200, 170, 110)),
          ('日本語のアルバム名前', 'ユーミン', (150, 80, 140)), ('Low', 'David Bowie', (120, 120, 90))]

def sample_cover(rgb, size):
    """A stand-in cover: a diagonal gradient of rgb; None is the stock placeholder disc (no cache file)."""
    im = Image.new('RGB', (size, size)); d = ImageDraw.Draw(im)
    if rgb is None:
        d.rectangle((0, 0, size, size), fill=(0x2B,) * 3); c = size // 2
        d.ellipse((c - size * 0.42, c - size * 0.42, c + size * 0.42, c + size * 0.42), fill=(0x40,) * 3)
        d.ellipse((c - size * 0.12, c - size * 0.12, c + size * 0.12, c + size * 0.12), fill=(0x2B,) * 3)
        return im.convert('RGBA')
    for y in range(size):
        k = 0.55 + 0.45 * (1 - y / size)
        d.line((0, y, size, y), fill=tuple(int(v * k) for v in rgb))
    d.ellipse((size * 0.25, size * 0.25, size * 0.75, size * 0.75), outline=tuple(min(255, v + 70) for v in rgb), width=max(1, size // 30))
    return im.convert('RGBA')

def save_compact(im, path, colors=128):
    """A palette PNG (median cut, no dither): the previews are flat UI, and docs/ history keeps every regeneration."""
    im.convert('RGB').quantize(colors, Image.Quantize.MEDIANCUT).save(path, optimize=True)

def albums_navbar(s, im, to):
    """The Albums page's navbar (Back, title, Now Playing) with the mode toggle, flush left of Now Playing (NAV_VIEW_X),
    showing the glyph of the mode it switches to."""
    o = offsets()
    s.text(im, 36, 25, 'Albums', title_px(s.tree))
    im.alpha_composite(s.img('return'), (14, 14))
    im.alpha_composite(s.img('back_to_player'), (278, 13))
    n = 'pod_nav_' + to
    im.alpha_composite(s.img(n), (o['NAV_VIEW_X'] + (o['NAV_VIEW_W'] - s.img(n).width) // 2, (o['NAV_H'] - s.img(n).height) // 2))

def albums_grid(s, scroll=0):
    """ui/m1pod_albums.bin as patch/albums.c paints it: GRID_COLS covers a row, a one-line title (ellipsis) under each."""
    o = offsets(); W_, H_ = 320, 450
    im = Image.new('RGBA', (W_, H_), (0, 0, 0, 255)); albums_navbar(s, im, 'list')
    cover, gap, m, tg, th = o['GRID_COVER'], o['GRID_GAP'], o['GRID_MARGIN'], o['GRID_TITLE_GAP'], o['GRID_TITLE_H']
    pitch = cover + tg + th + gap
    for a, (title, _, rgb) in enumerate(ALBUMS * 2):
        x, top = m + (a % o['GRID_COLS']) * (cover + gap), 50 + gap + (a // o['GRID_COLS']) * pitch - scroll
        if top >= H_ or top + cover + tg + th <= 50: continue
        c = sample_cover(rgb, cover); y0, y1 = max(50, top), min(H_, top + cover)
        if y1 > y0: im.alpha_composite(c.crop((0, y0 - top, cover, y1 - top)), (x, y0))
        ty = top + cover + tg
        if ty >= 50 and ty + th <= H_:
            while s.font.width(title, 16) > cover and len(title) > 1:      # the ellipsis cut, as al_title
                title = title[:-2] + '…' if title.endswith('…') else title[:-1] + '…'
            s.text(im, x, ty + th / 2, title, 16)
    return im

def albums_list(s, pressed=1):
    """ui/m1pod_albums.bin in list mode as patch/albums.c paints it: LIST_ROW_H rows, a LIST_ART px cover, the album (21 px)
    and the artist (18 px, #AAAAAA) cut with an ellipsis at LIST_TEXT_W, a hairline under each row, row `pressed` held down."""
    o = offsets(); H_ = 450
    im = Image.new('RGBA', (W, H_), (0, 0, 0, 255)); d = ImageDraw.Draw(im); albums_navbar(s, im, 'grid')
    rh = o['LIST_ROW_H']
    def cut(text, px):
        while s.font.width(text, px) > o['LIST_TEXT_W'] and len(text) > 1:      # the ellipsis cut, as al_fit
            text = text[:-2] + '…' if text.endswith('…') else text[:-1] + '…'
        return text
    for r, (title, artist, rgb) in enumerate(ALBUMS * 2):
        y = 50 + r * rh
        if y >= H_: break
        if r == pressed: d.rectangle((0, y, W - 1, y + rh - 2), fill=(0x33, 0x33, 0x33))
        d.rectangle((0, y + rh - 1, W - 1, y + rh - 1), fill=(0x22, 0x22, 0x22))
        im.alpha_composite(sample_cover(rgb, o['LIST_ART']), (o['LIST_ART_X'], y + o['LIST_ART_Y']))
        if y + o['LIST_TITLE_Y'] + o['LIST_TITLE_H'] <= H_:     # a text not wholly in the view is not drawn
            s.text(im, o['LIST_TEXT_X'], y + o['LIST_TITLE_Y'] + o['LIST_TITLE_H'] / 2, cut(title, 21), 21)
        if y + o['LIST_SUB_Y'] + o['LIST_SUB_H'] <= H_:
            s.text(im, o['LIST_TEXT_X'], y + o['LIST_SUB_Y'] + o['LIST_SUB_H'] / 2, cut(artist, 18), 18, (0xAA, 0xAA, 0xAA))
    return im.crop((0, 0, W, H_))

def zoom_strip(s):
    names = ['bar_play', 'bar_pause', 'bar_vol0', 'bar_vol1', 'bar_vol2', 'bar_vol3', 'bar_vol4', 'bar_wifi1', 'bar_wifi2',
             'bar_wifi3', 'bar_wifi4', 'bar_bt', 'bar_btcon', 'bar_digital', 'bar_power']
    im = Image.new('RGBA', (len(names) * 28, 26), (0, 0, 0, 255)); x = 2
    for n in names:
        ic = s.img(n); ic = ic.crop((0, 0, min(ic.width, 26), ic.height)) if n.startswith('bar_bt') is False else ic
        if n in ('bar_bt', 'bar_btcon'): ic = ic.crop((ic.width - 24, 0, ic.width, ic.height))
        im.alpha_composite(ic, (x, (26 - ic.height) // 2)); x += 28
    return im.resize((im.width * 3, 78), Image.NEAREST)

def main():
    before, after, out = sys.argv[1:4]
    sides = [('stock', Side(before, False)), ('release (Tabler Icons)', Side(after, True))]
    sections = [('Home page 1', lambda s: home(s, 0)), ('Home page 2', lambda s: home(s, 1)), ('Home page 3 (after: with the M1 Pod icon)', lambda s: home(s, 2)),
                ('M1 Pod menu (opened from the grid icon)', lambda s: pod_page(s, 'm1pod_menu', 8)), ('M1 Pod > Settings page', lambda s: pod_page(s, 'm1pod_settings', 4)),
                ('M1 Pod > Shuffle page', lambda s: pod_page(s, 'm1pod_shuffle', 3)),
                ('Settings icons (46)', settings), ('Pull-down', pulldown), ('List placeholders', lists)]
    pad = 14
    heights = [330, 330, 330, 50 + 8 * 52, 50 + 4 * 52, 50 + 3 * 52, 7 * 45 + 6, 290, 70]
    sh = Image.new('RGBA', (2 * W + 3 * pad, 30 + sum(h + 26 for h in heights) + 3 * 78 // 3 + 96), (0x2A, 0x2A, 0x2A, 255))
    d = ImageDraw.Draw(sh)
    d.text((pad, 6), 'Icons before / after, 1:1 device pixels. Markers (after): blue C = custom Tabler-style SVG, orange K = stock image kept. Zoom strip: status icons at 3x.', fill=WHITE, font=ANN)
    y = 30
    for (title, fn), h in zip(sections, heights):
        d.text((pad, y), title, fill=(0xAA,) * 3, font=ANN_B); y += 22
        for i, (_, s) in enumerate(sides): sh.alpha_composite(fn(s), (pad + i * (W + pad), y))
        y += h + 4
    d.text((pad, y), 'Status bar icons 3x: ' + sides[0][0] + ' above, ' + sides[1][0] + ' below', fill=(0xAA,) * 3, font=ANN_B); y += 22
    for _, s in sides: sh.alpha_composite(zoom_strip(s), (pad, y)); y += 84
    save_compact(sh.crop((0, 0, sh.width, y)), out); print('wrote', out)

if __name__ == '__main__': main()
