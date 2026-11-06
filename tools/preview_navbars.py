#!/usr/bin/env python3
"""PIL mock-up of the glass navbars (docs/modules/navbars.md): today's look (a tree built before the change, or the stock tree) against the finished tree, at rest
and scrolled so rows pass under the fade. Approximate, not AWTK; sample rows.

Drawn from the trees' own files: the pages' ui/*.bin (geometry, images), the themes' default.bin (the Back button's margin_left / x_offset and the title
label's margin_left, read the way tools/mod_ipodrows.py pill_layout reads the icon rule: icon_at left centres the icon in a square as high as the button,
from margin_left, shifted by x_offset), the images, default.ttf rasterized the stb way (tools/preview_font.py). The Songs pages' buttons are code-built:
their rectangles are the builder's (stock immediates, or the pinned ones in patch/offsets.inc) and their images the page theme's.

Usage: uv run python -I tools/preview_navbars.py OLD_WORKDIR NEW_WORKDIR OUT.png      (workdirs: a stock tree or a built one: WORK/rootfs/release/assets/default/raw)
"""
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
import cdefs
from awtk_ui import Widget
import preview_font   # noqa: F401  (redirects the painters' text to stb_raster, the tree's font)
import preview_layout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAWREL = 'rootfs/release/assets/default/raw'
W, BAR, H = 320, 30, 450


C = cdefs.defines(os.path.join(ROOT, 'patch', 'offsets.inc'))
SONGS = [('All Blues', 'Miles Davis'), ('Blue in Green', 'Miles Davis'), ('Freddie Freeloader', 'Miles Davis'), ("Moanin'", 'Art Blakey'),
         ('My Favorite Things', 'John Coltrane'), ('Naima', 'John Coltrane'), ('Take Five', 'The Dave Brubeck Quartet'), ('So What', 'Miles Davis'),
         ('Giant Steps', 'John Coltrane'), ('Round Midnight', 'Thelonious Monk')]
SETTINGS = ['Wi-Fi', 'Bluetooth', 'Display', 'Sound', 'Theme', 'Language', 'Date & time', 'Storage', 'Screensaver', 'About']
ARTISTS = ['A Tribe Called Quest', 'Art Blakey', 'Bill Evans', 'Charles Mingus', 'Dave Brubeck', 'Herbie Hancock', 'John Coltrane', 'Miles Davis', 'Nina Simone']


class NavPainter(preview_layout.MenuPainter):
    """MenuPainter with the navbar's icon rule and the label margin, read from the tree's own theme."""
    def margin(self, wd, key, default):
        v = self.prop(wd, key)
        return default if v is None else int(v)

    def walk(self, im, wd, ox, oy, clip, page, root):
        nav = getattr(self, 'in_nav', False)
        if wd.name == 'navigationbar_view': self.in_nav = True
        try:
            if wd.type == 'button' and nav:
                self.button(im, wd, ox, oy); return
            if wd.type == 'label' and wd.name in ('label_title', 'label_timetitle'):
                sh = self.margin(wd, 'margin_left', 2) - 2     # text from margin_left (default 2): the unshifted painter draws at the label's x
                wd.x += sh; wd.w -= sh
                try: super().walk(im, wd, ox, oy, clip, page, root)
                finally: wd.x -= sh; wd.w += sh
                return
            if wd.type == 'list_item':   # preview_layout's row painter has no hairline inset: rows are drawn by rows()
                super().walk(im, wd, ox, oy, clip, page, root); return
            super().walk(im, wd, ox, oy, clip, page, root)
        finally:
            if wd.name == 'navigationbar_view': self.in_nav = False

    def button(self, im, wd, ox, oy):
        icon = self.prop(wd, 'icon') or wd.get('style:normal:icon')
        img = self.image(icon)
        if not img or wd.get('visible') == 'false': return
        x, y, w, h = ox + wd.x, oy + wd.y, wd.w, wd.h
        if self.prop(wd, 'icon_at') == 1 or wd.get('style') == 'navbar_btnreturn_style':   # left: centred in a square as high as the button, from margin_left, + x_offset
            ix = x + self.margin(wd, 'margin_left', 0) + (h - img.width) // 2 + (self.margin(wd, 'x_offset', 0))
        else: ix = x + (w - img.width) // 2
        im.alpha_composite(img, (ix, y + (h - img.height) // 2))


def tree(work): return os.path.join(work, RAWREL)


def status(im):
    d = ImageDraw.Draw(im)
    return d


def row_widgets(items, y0, scroll, two_line=True, pitch=64):
    out = []
    for i, it in enumerate(items):
        y = y0 + i * pitch - scroll
        title, sub = it if isinstance(it, tuple) else (it, None)
        row = Widget('list_item', 0, y, 310, pitch, [('style', 'list_item_style')])
        t = Widget('hscroll_label', 12, 6 if sub else 0, 270, 26 if sub else pitch - 2, [('text', title), ('style', 'srlabel_item_white_style')])
        row.children = [t]
        if sub: row.children.append(Widget('hscroll_label', 12, 32, 270, 22, [('text', sub), ('style', 'srlabel_item_gray18_style')]))
        out.append(row)
    return out


def hair(im, y):
    ImageDraw.Draw(im).rectangle([12, y, W - 1, y], fill=(34, 34, 34))


def page_panel(work, rel, rows, scroll=0, pitch=52, subs=False, extra=None):
    """A stock / Pod page's ui file with sample rows in its list: the tree's own navbar, fade and geometry."""
    raw = tree(work)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', rel), 'rb').read())
    lst = next((c for c in root.children if c.y == 50 and c.h >= 300 and c.type in ('list_view', 'table_view', 'scroll_view')), None)
    if lst is not None:
        sv = next((c for c in lst.walk() if c.type == 'scroll_view'), lst)
        sv.children = row_widgets(rows, 0, scroll, pitch=pitch)
        lst.children = [c for c in lst.children if c.type != 'scroll_bar_m'] if lst is not sv else lst.children
    if extra: extra(root)
    p = NavPainter(raw)
    im = p.render(root, 0)
    return im


def cf_bar(work):
    raw = tree(work)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1plus_cover.bin'), 'rb').read())
    for c in list(root.children):
        if c.name not in ('navigationbar_view',): root.children.remove(c)
    for w in root.walk():
        if w.name == 'label_title': w.set('text', 'Cover Flow')
    p = NavPainter(raw)
    return p.render(root, 0).crop((0, 0, W, BAR + 120))


def cf_artist_bar(work, title='Miles Davis'):
    """Cover Flow on an artist as patch/coverflow.c artist_nav leaves it: Songs shown (the capsule's left cap), Now Playing's icons the right cap, the title to 214."""
    raw = tree(work)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1plus_cover.bin'), 'rb').read())
    for c in list(root.children):
        if c.name not in ('navigationbar_view',): root.children.remove(c)
    names = {w.name for w in root.walk()}
    for w in root.walk():
        if w.name == 'label_title': w.set('text', title); w.w = 214 - w.x
        elif w.name == 'btn_songs': w.set('visible', 'true'); w.set('sensitive', 'true')
        elif w.name == 'btn_backtoplayer' and 'btn_songs' in names:
            for k in ('normal', 'over'): w.set(f'style:{k}:icon', 'ah_nav_play')
            w.set('style:pressed:icon', 'ah_nav_play_down')
    return NavPainter(raw).render(root, 0).crop((0, 0, W, BAR + 120))


def label(im, text):
    d = ImageDraw.Draw(im); d.text((6, 4), text, fill=(230, 230, 230))


def home_panel(work, ghost, scroll=0):
    """The menu as the Home instance (patch/home.c: navbar hidden, list from y 10, 430 high): with the fade left visible (ghost, V2.1oAB) or hidden with the bar."""
    raw = tree(work)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1plus_menu.bin'), 'rb').read())
    nb = next(c for c in root.children if c.name == 'navigationbar_view'); root.children.remove(nb)
    lst = next(c for c in root.children if c.name == 'pod_listview'); lst.y, lst.h = 10, 430
    for c in list(root.children):
        if c.name == 'img_nb_fade' and not ghost: root.children.remove(c)
        elif c.name == 'pod_minibar': root.children.remove(c)
    sv = next(c for c in lst.walk() if c.type == 'scroll_view'); sv.children = row_widgets(SETTINGS * 2, 0, scroll, pitch=52)
    return NavPainter(raw).render(root, 0)


def allmusic_panel(work, title='Favorites'):
    """A Songs-type page (allmusic_page) as main has it (docs/modules/navbar.md): the bar's view at y 3, the shared builder's 44 px buttons on the Pod navbar's slots
    (search 168, multi-select 214, 46 wide; Now Playing 262, 60 wide; Back x 3, title 20 px), the stock images. The same in both trees: this work does not touch it."""
    raw = tree(work)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'allmusic_page.bin'), 'rb').read())
    tv = next(c for c in root.children if c.name == 'table_view'); tv.children = row_widgets(SONGS, 0, 0, pitch=64)
    nav = next(c for c in root.children if c.name == 'navigationbar_view')
    def b(name, x, w, ic, dx=0): return Widget('button', x + dx, 0, w, 44, [('name', name), ('style', 'img_btn_style'), ('style:normal:icon', ic)])
    kids = [Widget('label', 36, 11, 147, 22, [('name', 'label_title'), ('text', title), ('style', 'navbar_label_white')])]
    kids.append(Widget('button', 3, 0, 80, 44, [('name', 'btn_return'), ('style', 'navbar_btnreturn_style'), ('style:normal:icon', 'return')]))
    kids += [b('btn_search', 168, 46, 'search'), b('btn_mulselect', 214, 46, 'mulselect'), b('btn_np', 262, 60, 'back_to_player', -2)]
    nav.children = kids
    return NavPainter(raw).render(root, 0)


WORK_STOCK = None


def build_panels(work, new):
    sc = 150
    panels = [
        ('Menu (grid-icon instance)', page_panel(work, 'm1plus_menu.bin', SETTINGS)),
        ('Extras', page_panel(work, 'm1plus_extras.bin', SETTINGS)),
        ('Artists', page_panel(work, 'm1plus_artists.bin', ARTISTS)),
        ('Albums (grid page)', page_panel(work, 'm1plus_albums.bin', [])),
        ('Playlists', page_panel(work, 'm1plus_playlists.bin', ARTISTS)),
        ('Cover Flow bar', cf_bar(work)),
        ('Cover Flow, an artist', cf_artist_bar(work)),
        ('Extras, scrolled', page_panel(work, 'm1plus_extras.bin', SETTINGS, scroll=sc)),
        ('Home instance, scrolled', home_panel(work, ghost=False, scroll=sc)),
        ("Songs page (main's, unchanged)", allmusic_panel(work)),
    ]
    return panels


def main():
    global WORK_STOCK
    old, new, out = sys.argv[1:4]
    WORK_STOCK = old
    pad, top, cols = 10, 20, 5
    sets = [('main oC', build_panels(old, False)), ('glass', build_panels(new, True))]
    cell_h = BAR + H
    rows = 2 * 2   # (today, new) x two rows of five
    img = Image.new('RGB', (cols * (W + pad) + pad, rows * (cell_h + top + pad) + pad), (40, 40, 40))
    d = ImageDraw.Draw(img)
    for si, (tag, panels) in enumerate(sets):
        for i, (cap, im) in enumerate(panels):
            r, c = si * 2 + i // cols, i % cols
            x, y = pad + c * (W + pad), pad + r * (cell_h + top + pad)
            d.text((x, y + 4), f'{tag}: {cap}', fill=(230, 230, 230))
            img.paste(im.convert('RGB'), (x, y + top))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out, optimize=True); print('wrote', out)


if __name__ == '__main__': main()
