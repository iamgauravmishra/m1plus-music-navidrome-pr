#!/usr/bin/env python3
"""out/preview/peqpage.png: the preset page (patch/peqpage.c, docs/modules/peq.md "Preset page"): a preset's graph, preamp and bands, the long one (a boost past 12 dB: the +18 scale, a skipped-lines
note, a one-sided band; the Delete Preset card under the bands, in red) and a short one, and the Presets page whose rows open it. Drawn from a finished tree's own ui files, strings and font, the graph by tools/peq_graph.py (the model
test/pod/peq.py checks the payload's bitmap against). Approximate (PIL, not AWTK).

Usage: uv run python -I tools/preview/preview_peqpage.py WORKDIR [OUT.png]     (en_US; default out/preview/peqpage.png)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw
import awtk_ui, build, peq_graph as G, preview_icons as PI, preview_peq as PQ, preview_settings as PS, pod_pages as P, pod_settings as ST

RAW, W, NAV, SCREEN = PI.RAW, PS.W, PS.NAV, PS.SCREEN
HD600 = [(1, 1, 105, 4.8, 0.7), (1, 0, 190, -2.4, 0.89), (1, 0, 1100, 2.9, 1.1), (1, 0, 2500, 3.8, 1.7), (1, 0, 3400, -3.2, 3.4), (1, 0, 4500, -1.9, 2.5), (1, 0, 6100, 2.2, 5.3),
         (1, 0, 9200, -4.6, 4.9), (1, 2, 10000, -3.0, 0.7)]
LONG = [(1, 1, 80, 14.0, 0.7), (1, 0, 250, -3.5, 1.2), (2, 0, 1800, 6.0, 0.9), (3, 0, 1800, -2.0, 0.9), (1, 0, 3500, 4.0, 2.0), (1, 2, 8000, -6.5, 0.7), (1, 0, 12500, 3.25, 1.41), (1, 0, 16000, -1.5, 4.0)]


def peqpage(s, title, bands, preamp, skipped=0):
    """The page as patch/peqpage.c leaves it: the shown band rows named, their pieces and hairlines, the preamp, the note, the scale; the graph card's bitmap from the model."""
    root = awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', P.PEQP_PAGE.key + '.bin'), 'rb').read())
    sv = next(w for w in root.walk() if w.name == 'pod_scrollview')
    n = len(bands)
    db, rng = G.curve(bands)
    root.find('label_title').set('tr_text', title)   # (a key the table lacks shows as it is)
    root.find('pod_value0').set('text', preamp)
    for i, (f, g, line) in enumerate(G.band_rows(bands), 1):
        row = root.find(f'pod_row{i}')
        row.set('visible', 'true')
        root.find(f'pod_label{i}').set('text', f); root.find(f'pod_value{i}').set('text', g); root.find(f'pod_sub{i}').set('text', line)
        piece = ST.peqp_pieces(n)[i - 1]
        for st in ('normal', 'over', 'focused', 'disable'): row.set(f'style:{st}:bg_image', f'pod_cd_{piece}')
        row.set('style:pressed:bg_image', f'pod_cd_{piece}_down')
        if i == n: row.children = [c for c in row.children if c.name != 'pod_hair']
    if skipped:
        root.find('pod_note0').set('visible', 'true')
        root.find('pod_note0_t').set('tr_text', f'{skipped} lines not supported were skipped.' if skipped > 1 else '1 line not supported was skipped.')
    root.find('pod_gr_top').set('text', f'+{rng}'); root.find('pod_gr_bot').set('text', f'{G.MINUS}{rng}')
    kids = [c for c in sv.children if c.get('visible') != 'false']
    end = sum(c.h for c in kids)
    im = Image.new('RGBA', (W, NAV + end), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    y = NAV
    for c in kids:
        if c.name == 'pod_graph':
            px = Image.new('RGBA', (G.W, G.H))
            px.putdata([(v, v, b, a) for row in G.render(db, rng) for a, v, b in row])
            im.alpha_composite(px, (G.CARD_X, y))
            for t in c.children:
                s.text(im, t.x + (t.w if t.get('style:normal:text_align_h') == 'right' else t.w / 2 if t.get('style:normal:text_align_h') == 'center' else 0), y + t.y + t.h / 2, s.shown(t),
                       int(PS.style(t, 'font_size')), PS.rgb(PS.style(t, 'text_color')), {'right': 'r', 'center': 'm'}.get(t.get('style:normal:text_align_h'), 'l'))
        elif c.type == 'list_item':
            im.alpha_composite(s.img(c.get('style:normal:bg_image')), (0, y))
            for t in c.children:
                if t.name == 'pod_hair': d.rectangle((t.x, y + t.y, t.x + t.w - 1, y + t.y), fill=PS.rgb(PS.style(t, 'bg_color')))
                elif t.type == 'image' and t.name == 'pod_chevron':
                    im.alpha_composite(s.img(t.get('image')), (t.x, y + t.y))
                elif t.type == 'hscroll_label':
                    px = int(PS.style(t, 'font_size', 21))
                    al = PS.style(t, 'text_align_h', 'left')
                    col = PS.rgb(PS.style(t, 'text_color', '#FFFFFF'))
                    x = t.x + (t.w - 2 if al == 'right' else 0)
                    s.text(im, x, y + t.y + t.h / 2, s.clip(s.shown(t), px, t.w), px, col, 'r' if al == 'right' else 'l')
        else:
            for t in c.children:
                if t.type == 'hscroll_label': s.text(im, t.x, y + t.y + t.h / 2, s.clip(s.shown(t), int(PS.style(t, 'font_size')), t.w), int(PS.style(t, 'font_size')), PS.rgb(PS.style(t, 'text_color')))
                elif t.type == 'label':
                    s.text(im, t.x, y + t.y + ST.NOTE_LABEL_H / 2, s.shown(t), int(PS.style(t, 'font_size')), PS.rgb(PS.style(t, 'text_color')))
        y += c.h
    d.rectangle((0, 0, W - 1, NAV - 1), fill=(0, 0, 0))
    lt = root.find('label_title'); tpx = PI.title_px(s.tree)
    s.text(im, lt.x, NAV / 2, s.clip(s.shown(lt), tpx, lt.w), tpx, (255, 255, 255))
    for name, bx, bw in (('ah_nav_back', 7, 44), ('ah_nav_np', 260, 60)):
        g = s.img(name); im.alpha_composite(g, (bx + (bw - g.width) // 2, (NAV - g.height) // 2))
    return im.convert('RGB')


def dialog(s, im, name):
    """The unsaved-changes dialog over a screen (patch/peqband.c, tools/pod_ui.py peq_dialog): the dim, the pq_glass card (patch3_x: the image's middle third stretches) centred in the client, the title, the preset's name and four buttons."""
    import pod_ui
    im = im.convert('RGBA')
    im.alpha_composite(Image.new('RGBA', im.size, (0, 0, 0, 0x82)))
    w, h = pod_ui.PQD_W, pod_ui.PQD_H
    g = s.img('pq_glass'); t = g.width // 3
    card = Image.new('RGBA', (w, h)); card.paste(g.crop((0, 0, t, h)), (0, 0)); card.paste(g.crop((t, 0, g.width - t, h)).resize((w - 2 * t, h)), (t, 0)); card.paste(g.crop((g.width - t, 0, g.width, h)), (w - t, 0))
    x0, y0 = (W - w) // 2, (pod_ui.CLIENT_H - h) // 2
    im.alpha_composite(card, (x0, y0))
    s.text(im, W / 2, y0 + 14 + 15, s.strings.get('Save Changes?', 'Save Changes?'), 20, anchor='m')
    s.text(im, W / 2, y0 + 44 + 12, name, 16, (0xEB,) * 3, anchor='m')
    for k, key in enumerate(pod_ui.PQD_KEYS):
        y = y0 + pod_ui.PQD_HEAD + k * pod_ui.PQD_ROW_H
        im.alpha_composite(Image.new('RGBA', (w, 1), (255, 255, 255, 0x22)), (x0, y))
        s.text(im, W / 2, y + pod_ui.PQD_ROW_H / 2, s.strings.get(key, key), 18, anchor='m')
    return im.convert('RGB')


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    work = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'peqpage.png')
    s = PI.Side(work, True, 'en_US'); s.mark = lambda *a: None
    pages = [('Sennheiser HD 600: the first screen', peqpage(s, 'Sennheiser HD 600', HD600, 'Auto · −6.0 dB'), SCREEN),
             ('The whole page: with Delete Preset', peqpage(s, 'Sony WH-1000XM4 (ANC on)', LONG, '−3.5 dB', 3), None),
             ('Presets: a row opens the preset page', PQ.peqlib_page(s, PQ.LIB), None)]
    pad = 12
    shots = [(t, im.crop((0, 0, im.width, min(im.height, h or im.height)))) for t, im, h in pages]
    wid = sum(im.width for _, im in shots) + pad * (len(shots) + 1)
    hei = max(im.height for _, im in shots) + 44 + pad
    out = Image.new('RGB', (wid, hei), (0x2A,) * 3); d = ImageDraw.Draw(out)
    x = pad
    for title, im in shots:
        d.text((x, 24), title, fill=(0xAA,) * 3, font=PI.ANN); out.paste(im, (x, 44)); x += im.width + pad
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.save(out_path, optimize=True); print('wrote', out_path, out.size)


if __name__ == '__main__':
    main()
