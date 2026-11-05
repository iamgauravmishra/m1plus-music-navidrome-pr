#!/usr/bin/env python3
"""The Settings pages (iOS style grouped cards, docs/modules/settings.md "Cards"), drawn from the built tree's own ui assets: the cards, rows, glyphs, hairlines, headers and notes are the
widgets tools/pod_ui.py build_cards_page made from the numbers of tools/pod_settings.py (shared with the tests), with the font, images and navbar of the tree. A value takes the room its text
needs and the row's label gets the rest, as patch/m1plus.c value_fit does. Approximate (PIL, not AWTK); the sample state (values, switches, checks) is what a typical device shows.

  out/preview/settings-mock-3.png   Settings (first screen and whole list), Home Screen, Library, Album Order, Now Playing, Theme, Developer, Keyboards, About

Usage: uv run python -I tools/preview_settings.py WORKDIR [OUT.png]     (en_US; WORKDIR e.g. work/mod-release after a build)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw
import awtk_ui, build, palette, preview_icons as PI, pod_settings as ST

W, NAV, SCREEN = 320, 50, 450
RAW = PI.RAW

# What a typical device shows: widget name -> text (values), name -> on (switches), name -> shown (checks, the hidden card), per page key.
STATE = {
    'm1plus_settings': {'values': {'pod_value0': 'Off', 'pod_value1': 'Off', 'pod_value5': 'Repeat All', 'pod_value6': 'Off'}},
    'm1plus_appearance': {'values': {'pod_value0': 'Neutral'}},
    'm1plus_background': {'shown': {'pod_check1'}},
    'm1plus_accent': {'shown': {'pod_check0'}},
    'm1plus_homeset': {'switches': {'pod_switch0': True, 'pod_switch1': True}},
    'm1plus_library': {'values': {'pod_value1': 'Artist'}, 'switches': {'pod_switch2': False}},
    'm1plus_albumorder': {'shown': {'pod_check0'}},
    'm1plus_npset': {'values': {'pod_value0': 'Chrome'}},
    'm1plus_tapetheme': {'shown': {'pod_check1'}},
    'm1plus_developer': {'switches': {'pod_switch0': True}},
    'm1plus_about': {'values': {'pod_value0': 'V2.1pM', 'pod_value1': 'V2.1', 'pod_value2': 'Shanling M1 Plus', 'pod_value3': 'M1P2305A01234', 'pod_value4': '98:b3:ec:4a:7c:1e',
                                'pod_value5': '192.168.1.42', 'pod_value6': '119.25 GB', 'pod_value7': '87.41 GB'}},
    'm1plus_keyboards': {'switches': {'pod_switch0': True, 'pod_switch1': False}},
    'm1plus_cache': {'values': {'pod_value0': '840', 'pod_value1': '812', 'pod_value2': '9', 'pod_value3': '19', 'pod_value4': '3', 'pod_value5': '14.2 MB', 'pod_value6': 'Idle'}},
}


def rgb(css):
    css = css.lstrip('#')
    return tuple(int(css[i:i + 2], 16) for i in (0, 2, 4))


def style(w, prop, default=None):
    return w.get(f'style:normal:{prop}') or default


def draw_page(s, key, full=False, state=None, lit=False, pal=None, pressed=None):
    """A cards page of the tree as the payload leaves it: the widgets of ui/<key>.bin, the sample state applied. lit: in Light Mode (docs/modules/accent.md): every colour of the styles and every
    image as the hooks of patch/palette.c give it (tools/palette.py is their model); the page's layout is the same.
    pal: an optional palette object (tools/preview_accent.py: .ink(rgb), .image(side, name), .base): every colour and image goes through the model of tools/palette.py as the hooks
    of patch/palette.c give it (an accent's tints, the pressed card piece, the row glyphs in the accent); None draws today's colours.
    pressed: the label text of the one row drawn in its pressed state (needs pal)."""
    ink = (lambda c: palette.flip(c)) if lit else (lambda c: c)
    img = lambda n: palette.flip_image(n, s.img(n)) if lit else s.img(n)
    if pal: ink, img = pal.ink, (lambda n: pal.image(s, n))
    root = awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', key + '.bin'), 'rb').read())
    st = STATE.get(key, {}) if state is None else state
    values, switches, shown = st.get('values', {}), st.get('switches', {}), st.get('shown', set())
    sv = next(w for w in root.walk() if w.name == 'pod_scrollview')
    hidden = st.get('hidden', set())
    kids = [c for c in sv.children if c.name not in hidden and c.get('visible') != 'false']   # the list_view layouter stacks the visible children (it ignores their y)
    end = sum(c.h for c in kids)
    base = ink((0, 0, 0))
    im = Image.new('RGBA', (W, max(SCREEN, NAV + end) if full else SCREEN), base + (255,)); d = ImageDraw.Draw(im)
    y = NAV
    for c in kids:
        if c.type == 'list_item':
            lab = next(t for t in c.children if t.name.startswith('pod_label'))
            draw_row(s, im, d, c, y, values, switches, shown, ink, img, pal, pal is not None and pressed is not None and s.shown(lab) == pressed)
        for t in c.children:   # a header or a note: its grey label
            if c.type == 'view' and t.type == 'hscroll_label':
                px = int(style(t, 'font_size'))
                s.text(im, t.x, y + t.y + t.h / 2, s.clip(s.shown(t), px, t.w), px, ink(rgb(style(t, 'text_color'))))
        y += c.h
    d.rectangle((0, 0, W - 1, NAV - 1), fill=base)   # the list is under the navbar: it clips at its top
    lt = next(w for w in root.walk() if w.name == 'label_title'); tpx = PI.title_px(s.tree)
    s.text(im, lt.x, NAV / 2, s.clip(s.shown(lt), tpx, lt.w), tpx, ink((255, 255, 255)))
    for name, bx, bw in (('ah_nav_back', 7, 44), ('ah_nav_np', 260, 60)):   # the glass navbar: Back (7, 0, 44, 50), Now Playing's round glass (260, 0, 60, 50)
        g = img(name); im.alpha_composite(g, (bx + (bw - g.width) // 2, (NAV - g.height) // 2))
    if full and im.height > SCREEN:
        for x in range(0, W, 8): d.line((x, SCREEN, x + 3, SCREEN), fill=(0xFF, 0x50, 0x50))
    return im


def draw_row(s, im, d, row, y, values, switches, shown, ink=lambda c: c, img=None, pal=None, pressed=False):
    img = img or s.img
    piece = img(row.get('style:normal:bg_image') + ('_down' if pressed else ''))   # the row's piece of its card (the pressed twin when pressed)
    im.alpha_composite(piece, (0, y))
    label = next(c for c in row.children if c.name.startswith('pod_label'))
    val = next((c for c in row.children if c.name.startswith('pod_value')), None)
    lab_w = label.w
    if val:   # the payload's value_fit: the text sets its room, the label gets the rest
        text = values.get(val.name) or s.shown(val)
        info = row.get('sensitive') == 'false'   # an About row: 16 px, no chevron, the value ends at the right ink edge
        px, mx = (int(style(val, 'font_size', ST.INFO_PX)), ST.INFO_MAX) if info else (ST.VALUE_PX, ST.VALUE_MAX)   # (an info row's own size: About's 16, the Cover Cache page's 18)
        vw = min(s.font.width(text, px) + 6, mx) if text else 8
        right = val.x + (ST.INFO_W if info else ST.VALUE_W)
        s.text(im, right - 2, y + row.h / 2, text, px, ink(rgb(ST.GREY)), 'r')
        lab_w = right - vw - ST.VALUE_LABEL_GAP - label.x
    for c in row.children:
        if c.type == 'image':
            if c.name.startswith('pod_check') and c.name not in shown: continue
            name = c.get('image')
            if c.name.startswith('pod_switch'): name = 'sset_on' if switches.get(c.name) else 'sset_off'
            g = img(name)
            im.alpha_composite(g, (c.x, y + c.y))
        elif c.name == 'pod_hair':
            d.rectangle((c.x, y + c.y, c.x + c.w - 1, y + c.y), fill=ink(rgb(style(c, 'bg_color'))))
    s.text(im, label.x, y + row.h / 2, s.clip(s.shown(label), 21, lab_w), 21, ink((255, 255, 255)))


def draw_covlist(s, title, albums):
    """The plain list of patch/covlist.c (the Albums list mode's rows without the cover: title 21 px white and artist 18 px grey from x 16, a hairline under each, rows 64 px) under the plain navbar."""
    root = awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', 'm1plus_covlist.bin'), 'rb').read())
    im = Image.new('RGBA', (W, SCREEN), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    if albums:
        for i, (al, ar) in enumerate(albums):
            y = NAV + i * 64
            s.text(im, 16, y + 7 + 12, s.clip(al, 21, 288), 21)
            s.text(im, 16, y + 33 + 10, s.clip(ar, 18, 288), 18, rgb('#AAAAAA'))
            d.rectangle((0, y + 63, W - 1, y + 63), fill=(0x22, 0x22, 0x22))
    else:
        s.text(im, W // 2, 225, s.shown(type('L', (), {'get': lambda self, k: {'tr_text': 'No albums'}.get(k)})()), 20, (255, 255, 255), 'm')
    d.rectangle((0, 0, W - 1, NAV - 1), fill=(0, 0, 0))
    lt = next(w for w in root.walk() if w.name == 'label_title'); tpx = PI.title_px(s.tree)
    s.text(im, lt.x, NAV / 2, title, tpx)
    for name, bx, bw in (('ah_nav_back', 7, 44), ('ah_nav_np', 260, 60)):
        g = s.img(name); im.alpha_composite(g, (bx + (bw - g.width) // 2, (NAV - g.height) // 2))
    return im


def sheet(panels, path):
    pad = 14
    wid = sum(im.width for _, im in panels) + pad * (len(panels) + 1)
    hei = max(im.height for _, im in panels) + 44 + pad
    out = Image.new('RGB', (wid, hei), (0x2A,) * 3); d = ImageDraw.Draw(out)
    x = pad
    for title, im in panels:
        d.text((x, 22), title, fill=(0xCC,) * 3, font=PI.ANN); out.paste(im.convert('RGB'), (x, 44)); x += im.width + pad
    os.makedirs(os.path.dirname(path), exist_ok=True)
    out.save(path, optimize=True); print('wrote', path, out.size)


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    s = PI.Side(sys.argv[1], True, 'en_US'); s.mark = lambda *a: None
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'settings-mock-3.png')
    sheet([('Settings, first screen', draw_page(s, 'm1plus_settings')),
           ('Settings, whole list (red = screen bottom)', draw_page(s, 'm1plus_settings', full=True)),
           ('Settings > Home Screen', draw_page(s, 'm1plus_homeset')),
           ('Settings > Library', draw_page(s, 'm1plus_library')),
           ('Settings > Library > Album Order', draw_page(s, 'm1plus_albumorder')),
           ('Settings > Now Playing', draw_page(s, 'm1plus_npset')),
           ('Settings > Now Playing > Theme', draw_page(s, 'm1plus_tapetheme')),
           ('Settings > Developer', draw_page(s, 'm1plus_developer')),
           ('Settings > Developer > Cache', draw_page(s, 'm1plus_cache')),
           ('Cache > Missing',draw_covlist(s, 'Missing Covers', [('Kind of Blue', 'Miles Davis'), ('Music Has the Right to Children', 'Boards of Canada'), ('Homogenic', 'Björk'), ('Selected Ambient Works 85-92', 'Aphex Twin'), ('Dummy', 'Portishead'), ('Blue in Green (Remastered, Mono Version)', 'Miles Davis'), ('Mezzanine', 'Massive Attack')])),
           ('Cache > No art', draw_covlist(s, 'No Art', [('Pastel Blues', 'Nina Simone'), ('Kid A', 'Radiohead')])),
           ('Cache > empty',draw_covlist(s, 'No Art', [])),
           ('Settings > Keyboards', draw_page(s, 'm1plus_keyboards')),
           ('Settings > About (first screen)', draw_page(s, 'm1plus_about')),
           ('Settings > Appearance', draw_page(s, 'm1plus_appearance')),
           ('Settings > Appearance > Accent', draw_page(s, 'm1plus_accent')),
           ('Settings > Appearance > Background', draw_page(s, 'm1plus_background')),
           ], out)
    # Light Mode (docs/modules/accent.md): the same pages with the hooks' colours and images (tools/palette.py); the Settings page with Light Mode On, and the picker
    lit = os.path.join(os.path.dirname(out), 'settings-light.png')
    sheet([('Light Mode: Settings, first screen', draw_page(s, 'm1plus_settings', lit=True)),
           ('Settings, whole list', draw_page(s, 'm1plus_settings', full=True, lit=True)),
           ('Settings > Appearance > Background', draw_page(s, 'm1plus_background', lit=True)),
           ('Settings > Home Screen', draw_page(s, 'm1plus_homeset', lit=True)),
           ('Settings > Library', draw_page(s, 'm1plus_library', lit=True)),
           ('Settings > Keyboards', draw_page(s, 'm1plus_keyboards', lit=True)),
           ('Settings > About (first screen)', draw_page(s, 'm1plus_about', lit=True)),
           ], lit)


if __name__ == '__main__':
    main()
