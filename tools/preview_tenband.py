#!/usr/bin/env python3
"""out/preview/tenband.png: the 10-Band editor, its Curve and Preamp pages (patch/tenband.c, docs/modules/peq.md "10-Band EQ"): the editor at rest (a Rock record), scrolled to Preamp and Reset, dragging
the 2 kHz slider to +5 dB (Custom), after Reset (Flat); the Curve page (first screen, scrolled to the end) and the Preamp page (first screen, scrolled to the end). Drawn from a finished tree's own ui files, strings
and font; the graph by tools/peq_graph.py and the slider card, thumbs and pill by tools/tenband_model.py (the models test/pod/peq.py checks the payload's bitmaps against). Approximate (PIL, not AWTK).

Usage: uv run python -I tools/preview_tenband.py WORKDIR [OUT.png]     (en_US; default out/preview/tenband.png)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw
import awtk_ui, build, peq_graph as G, preview_icons as PI, preview_settings as PS, tenband_model as TB, pod_pages as P

RAW, W, NAV, SCREEN = PI.RAW, PS.W, PS.NAV, PS.SCREEN
ROCK = [-2, 0, 2, 4, -2, -2, 0, 0, 4, 4]
GRAPHIC_F = (31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
GREY = (0x8A,) * 3
ACC = None   # an accent's (r, g, b): the thumbs and the graph's curve take it (tools/preview_accent.py sets it)


REGIONS = [('Sub bass · rumble', 'Mid bass · punch and warmth', 'Lower mids · body and fullness', 'Upper mids · shouty if too much', 'Treble · detail and sparkle', 'Air · openness')[i] for i in (0, 1, 1, 2, 2, 3, 3, 3, 4, 5)]   # by band


def tree(s, page): return awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', page.key + '.bin'), 'rb').read())


def paste_bitmap(im, model, w, h, x, y):
    px = Image.new('RGBA', (w, h))
    px.putdata([(p[1], p[1], p[-1], p[0]) for row in model for p in row])
    im.alpha_composite(px, (x, y))


def paste_rgba(im, model, w, h, x, y):
    px = Image.new('RGBA', (w, h))
    px.putdata([(p[1], p[2], p[3], p[0]) for row in model for p in row])
    im.alpha_composite(px, (x, y))


def content(s, root, values=None, shown=(), gains=None, drag=None, hdr_y=0):
    """The scroll_view's column as one image (W wide, no navbar): the rows by preview_settings.draw_row, the graph card and the slider card as the payload paints them. gains: the ten gains (None: no graph or sliders). The region line is a box of its own between them."""
    sv = next(w for w in root.walk() if w.name == 'pod_scrollview')
    kids = [c for c in sv.children if c.get('visible') != 'false']
    end = sum(c.h for c in kids)
    im = Image.new('RGBA', (W, end), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    y = 0
    for c in kids:
        if c.name == 'pod_graph':
            db, rng = G.curve([(1, 0, f, float(g), 1.41) for f, g in zip(GRAPHIC_F, gains)])
            if ACC: paste_rgba(im, G.render_accent(db, rng, ACC), G.W, G.H, G.CARD_X, y)
            else: paste_bitmap(im, G.render(db, rng), G.W, G.H, G.CARD_X, y)
            for t in c.children:
                al = t.get('style:normal:text_align_h')
                text = f'+{rng}' if t.name == 'pod_gr_top' else f'{G.MINUS}{rng}' if t.name == 'pod_gr_bot' else s.shown(t)
                s.text(im, t.x + (t.w if al == 'right' else t.w / 2 if al == 'center' else 0), y + t.y + t.h / 2, text, int(PS.style(t, 'font_size')), PS.rgb(PS.style(t, 'text_color')), {'right': 'r', 'center': 'm'}.get(al, 'l'))
        elif c.name == 'pod_regionbox' and drag is not None:   # the region line, written while a band is dragged (patch/tenband.c tb_region)
            t = c.children[0]
            s.text(im, t.x, y + t.y + t.h / 2, REGIONS[drag], int(PS.style(t, 'font_size')), PS.rgb(PS.style(t, 'text_color')), 'l')
        elif c.name == 'pod_sliders':
            paste_bitmap(im, TB.bitmap(TB.card_px, TB.W, TB.H), TB.W, TB.H, TB.CARD_X, y)
            for col in range(TB.COLS):
                at = (TB.CARD_X + TB.center_x(col) - TB.THUMB_W // 2, y + TB.thumb_y(gains[col]))
                if ACC: paste_rgba(im, TB.bitmap(lambda px, py: TB.thumb_px_acc(px, py, ACC), TB.THUMB_W, TB.THUMB_H), TB.THUMB_W, TB.THUMB_H, *at)
                else: paste_bitmap(im, TB.bitmap(TB.thumb_px, TB.THUMB_W, TB.THUMB_H), TB.THUMB_W, TB.THUMB_H, *at)
            if drag is not None:
                paste_bitmap(im, TB.bitmap(TB.pill_px, TB.PILL_W, TB.PILL_H), TB.PILL_W, TB.PILL_H, TB.CARD_X + TB.center_x(drag) - TB.PILL_W // 2, y + TB.VAL_Y)
            for col in range(TB.COLS):
                v, f = (next(t for t in c.children if t.name == f'pod_sl_{k}{col}') for k in 'vf')
                on = col == drag
                s.text(im, v.x + v.w / 2, y + v.y + v.h / 2, TB.gain_text(gains[col]), TB.LABEL_PX, (0, 0, 0) if on else GREY, 'm')
                s.text(im, f.x + f.w / 2, y + f.y + f.h / 2, s.shown(f), TB.LABEL_PX, (255, 255, 255) if on else GREY, 'm')
        elif c.type == 'list_item':
            PS.draw_row(s, im, d, c, y, values or {}, {}, set(shown))
        else:
            PS.draw_text_item(s, im, c, y)   # the grey notes (Preamp page, the editor's DSD note)
        y += c.h
    return im


def screen(s, title, col, off=0):
    """The screen: the navbar over the column scrolled off px (never past its end)."""
    off = max(0, min(off, col.height - (SCREEN - NAV))) if off >= 0 else max(0, col.height - (SCREEN - NAV))
    im = Image.new('RGBA', (W, SCREEN), (0, 0, 0, 255))
    im.paste(col.crop((0, off, W, off + SCREEN - NAV)), (0, NAV))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, W - 1, NAV - 1), fill=(0, 0, 0))
    tpx = PI.title_px(s.tree)
    s.text(im, tree(s, P.TENBAND_PAGE).find('label_title').x, NAV / 2, title, tpx, (255, 255, 255))
    for name, bx, bw in (('ah_nav_back', 7, 44), ('ah_nav_np', 260, 60)):
        g = s.img(name); im.alpha_composite(g, (bx + (bw - g.width) // 2, (NAV - g.height) // 2))
    return im.convert('RGB')


def editor(s, gains, curve, preamp, drag=None):
    root = tree(s, P.TENBAND_PAGE)
    return content(s, root, {'pod_value0': curve, 'pod_value1': preamp}, gains=gains, drag=drag)


def curve_page(s, checked):
    root = tree(s, P.TENCURVE_PAGE)
    return content(s, root, shown={f'pod_check{checked}'})


def preamp_page(s, checked, auto):
    root = tree(s, P.TENPREAMP_PAGE)
    for n in range(P.TENPREAMP_STEPS): root.find(f'pod_label{n + 1}').set('text', TB.cut_text(n))
    return content(s, root, {'pod_value0': auto}, shown={f'pod_check{checked}'})


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'tenband.png')
    s = PI.Side(sys.argv[1], True, 'en_US'); s.mark = lambda *a: None
    custom = ROCK[:6] + [5] + ROCK[7:]
    rest = editor(s, ROCK, 'Rock', 'Auto · −5.0 dB')
    panels = [('10-Band EQ: Rock', screen(s, '10-Band EQ', rest)),
              ('scrolled: Preamp and Reset', screen(s, '10-Band EQ', rest, -1)),
              ('dragging 2k to +5 (Custom)', screen(s, '10-Band EQ', editor(s, custom, 'Custom', 'Auto · −5.6 dB', drag=6))),
              ('after Reset: Flat', screen(s, '10-Band EQ', editor(s, [0] * 10, 'Flat', 'Auto · 0.0 dB'))),
              ('Curve', screen(s, 'Curve', curve_page(s, 2))),
              ('Curve, scrolled to the end', screen(s, 'Curve', curve_page(s, 9), -1)),
              ('Preamp', screen(s, 'Preamp', preamp_page(s, 0, '−5.0 dB'))),
              ('Preamp, scrolled to the end', screen(s, 'Preamp', preamp_page(s, 3, '−5.0 dB'), -1))]
    pad = 12
    wid = sum(im.width for _, im in panels[:4]) + pad * 5
    hei = 2 * (SCREEN + 44) + pad
    out = Image.new('RGB', (wid, hei), (0x2A,) * 3); d = ImageDraw.Draw(out)
    for i, (title, im) in enumerate(panels):
        x, y = pad + (i % 4) * (W + pad), (i // 4) * (SCREEN + 44)
        d.text((x, y + 24), title, fill=(0xAA,) * 3, font=PI.ANN); out.paste(im, (x, y + 44))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.save(out_path, optimize=True); print('wrote', out_path, out.size)


if __name__ == '__main__':
    main()
