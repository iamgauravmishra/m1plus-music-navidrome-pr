#!/usr/bin/env python3
"""out/preview/peqband.png: Preset editing (patch/peqpage.c, patch/peqband.c, docs/modules/peq.md "Preset editing"): the Preset page with its Edited card, the band page (band 4 of a preset: the ring on the curve, the
Peak / Low shelf / High shelf control, the three sliders), the same on a shelf, the save sheet over the Preset page, the Save As name entry and the Equalizer page after the save (the picker shows the saved preset's own name).
Drawn from a finished tree's own ui files, strings and font; the graph by tools/peq_graph.py, the control and the slider card as the payload's bitmaps are described (patch/peqband.c). Approximate (PIL, not AWTK).

Usage: uv run python -I tools/preview_peqband.py WORKDIR [OUT.png]     (en_US; default out/preview/peqband.png)
"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw
import awtk_ui, build, peq_graph as G, preview_icons as PI, preview_keyboard as PK, preview_peq as PQ, preview_peqpage as PP, preview_settings as PS, pod_pages as P, pod_settings as ST, pod_ui

RAW, W, NAV, SCREEN = PI.RAW, PS.W, PS.NAV, PS.SCREEN
BD = pod_ui.BD
O_BK = {k: pod_ui.OFFSETS[k] for k in ('BK_FIELD_X', 'BK_FIELD_W', 'BK_PAD', 'BK_CARET_GAP', 'BK_CARET_W', 'BK_CARET_H')}
SS = 4
ACC = None   # an accent's (r, g, b): the graph's curve and the sliders' fill take it (tools/preview_accent.py sets it)
HD600 = PP.HD600


def tree(s, page): return awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', page.key + '.bin'), 'rb').read())


def rounded(w, h, r, grey, alpha=255):
    big = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
    ImageDraw.Draw(big).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=r * SS, fill=(grey if isinstance(grey, tuple) else (grey,) * 3) + (alpha,))
    return big.resize((w, h), Image.LANCZOS)


def t_of(row, band):
    f, _, g, q = band[2], 0, band[3], band[4]
    return {0: math.log10(f / 20) / 3, 1: (g + 12) / 24, 2: math.log10(q / 0.1) / 2}[row]


def band_page(s, bands, k):
    """The band page of band k (0-based) as patch/peqband.c leaves it."""
    root = tree(s, P.PEQBAND_PAGE)
    sv = next(w for w in root.walk() if w.name == 'pod_scrollview')
    b = bands[k]
    end = sum(c.h for c in sv.children)
    im = Image.new('RGBA', (W, NAV + end), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    y = NAV
    for c in sv.children:
        if c.name == 'pod_graph':
            db, rng = G.curve(bands)
            px = Image.new('RGBA', (G.W, G.H))
            px.putdata([(p[1], p[2], p[3], p[0]) for row in G.render_accent(db, rng, ACC) for p in row] if ACC else [(v, v, b, a) for row in G.render(db, rng) for a, v, b in row])
            im.alpha_composite(px, (G.CARD_X, y))
            for t in c.children:
                al = t.get('style:normal:text_align_h')
                text = f'+{rng}' if t.name == 'pod_gr_top' else f'{G.MINUS}{rng}' if t.name == 'pod_gr_bot' else s.shown(t)
                s.text(im, t.x + (t.w if al == 'right' else t.w / 2 if al == 'center' else 0), y + t.y + t.h / 2, text, int(PS.style(t, 'font_size')), PS.rgb(PS.style(t, 'text_color')), {'right': 'r', 'center': 'm'}.get(al, 'l'))
            col = min(max(int(math.log10(b[2] / 20) * 83), 0), G.PW - 1)
            ry = min(max(G.PY0 + G.PH / 2 + 0.5 - db[col] * (G.PH / 2) / rng, G.PY0 + 0.5), G.PY0 + G.PH - 0.5)
            big = Image.new('RGBA', (16 * SS, 16 * SS), (0, 0, 0, 0)); bd = ImageDraw.Draw(big)
            bd.ellipse((0, 0, 16 * SS - 1, 16 * SS - 1), fill=(242, 242, 242, 255)); bd.ellipse((2.5 * SS, 2.5 * SS, 13.5 * SS, 13.5 * SS), fill=(0, 0, 0, 255))
            ring = big.resize((16, 16), Image.LANCZOS)
            im.alpha_composite(ring, (G.CARD_X + G.PX0 + col - 8, int(y + ry) - 8))
        elif c.name == 'pod_seg':
            im.alpha_composite(rounded(BD['BD_SEG_W'], BD['BD_SEG_H'], 10, (28, 28, 30)), (ST.CM, y + BD['BD_SEG_Y']))
            seg = BD['BD_SEG_W'] // 3
            im.alpha_composite(rounded(94, 34, 8, 229), (ST.CM + b[1] * seg + 3, y + BD['BD_SEG_Y'] + 3))
            for t in c.children:
                kk = int(t.name[-1])
                s.text(im, t.x + t.w / 2, y + t.y + t.h / 2, s.shown(t), pod_ui.BD_SEG_PX, (0, 0, 0) if kk == b[1] else (255, 255, 255), 'm')
        elif c.name == 'pod_hsl':
            im.alpha_composite(rounded(BD['BD_HSL_W'], BD['BD_HSL_H'], 12, (28, 28, 30)), (ST.CM, y))
            for r in range(3):
                cy = y + r * 50 + 38
                if r < 2: d.rectangle((ST.CM + 14, y + r * 50 + 49, ST.CM + 299, y + r * 50 + 49), fill=(51, 51, 51))
                d.rounded_rectangle((ST.CM + 14, cy - 2, ST.CM + 14 + 271, cy + 1), radius=2, fill=(62, 62, 62))
                n = round(t_of(r, b) * 272)
                if n > 0: d.rounded_rectangle((ST.CM + 14, cy - 2, ST.CM + 14 + n, cy + 1), radius=2, fill=ACC or (242, 242, 242))
                big = Image.new('RGBA', (22 * SS, 22 * SS), (0, 0, 0, 0)); ImageDraw.Draw(big).ellipse((0, 0, 22 * SS - 1, 22 * SS - 1), fill=(250, 250, 250, 255))
                im.alpha_composite(big.resize((22, 22), Image.LANCZOS), (ST.CM + 14 + n - 11, cy - 11))
            vals = (G.freq_text(b[2]), G.gain_text(b[3]), G.dec(round(b[4] * 100)))
            for t in c.children:
                kind, r = t.name[7], int(t.name[-1])
                text = s.shown(t) if kind == 'n' else vals[r]
                al = 'r' if kind == 'v' else 'l'
                s.text(im, t.x + (t.w if kind == 'v' else 0), y + t.y + t.h / 2, text, int(PS.style(t, 'font_size')), PS.rgb(PS.style(t, 'text_color')), al)
        elif c.name.startswith('pod_note'):
            PS.draw_text_item(s, im, c, y)
        y += c.h
    d.rectangle((0, 0, W - 1, NAV - 1), fill=(0, 0, 0))
    tpx = PI.title_px(s.tree)
    s.text(im, root.find('label_title').x, NAV / 2, f'Band {k + 1}', tpx, (255, 255, 255))
    g = s.img('ah_nav_back'); im.alpha_composite(g, (7 + (44 - g.width) // 2, (NAV - g.height) // 2))
    for name, bx, bw in (('pod_nav_bprev', 168, 46), ('pod_nav_bnext', 214, 46), ('ah_nav_play', 260, 60)):
        g = s.img(name); im.alpha_composite(g, (bx + (bw - g.width) // 2, (NAV - g.height) // 2))
    return im.convert('RGB')


def keypad(s, im, row, number, neg=False, khz=False):
    """The number keypad sheet (patch/peqband.c, tools/pod_ui.py band_keypad) over a screen: the dim, the bk_glass sheet and the asset's own widgets (positions, fills, radii); the unit, caret and number placed as the payload does."""
    root = tree(s, P.PEQBAND_PAGE)
    card = root.find('bk_card')
    im = im.convert('RGBA')
    im.alpha_composite(Image.new('RGBA', im.size, (0, 0, 0, 0x82)))
    im.alpha_composite(s.img('bk_glass'), (card.x, card.y))
    def at(w): return card.x + w.x, card.y + w.y
    def rr(x, y, w, h, r, fill):
        big = Image.new('RGBA', (w * SS, h * SS), (0, 0, 0, 0))
        ImageDraw.Draw(big).rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), radius=r * SS, fill=fill)
        im.alpha_composite(big.resize((w, h), Image.LANCZOS), (x, y))
    def fill(w, st='normal'): return PS.rgb(w.get(f'style:{st}:bg_color')) + (255,)
    g = root.find('bk_grab'); x, y = at(g); rr(x, y, g.w, g.h, g.h // 2, fill(g))
    for n, align in (('bk_cancel_t', 'l'), ('bk_done_t', 'r')):
        t = root.find(n); par = root.find(n[:-2]); x, y = at(par)
        s.text(im, x + (t.x if align == 'l' else t.x + t.w), y + par.h / 2, s.strings.get(s.shown(t), s.shown(t)), 17, (255, 255, 255), align)
    title = ('Frequency', 'Gain', 'Q')[row]
    t = root.find('bk_title'); x, y = at(t); s.text(im, x + t.w / 2, y + t.h / 2, s.strings.get(title, title), 17, (255, 255, 255), 'm')
    rng = ('20 Hz \u2013 20 kHz', '\u221224 \u2013 +24 dB', '0.1 \u2013 10')[row]
    t = root.find('bk_range'); x, y = at(t); s.text(im, x, y + t.h / 2, s.strings.get('Range', 'Range') + ' ' + rng, 14, PS.rgb(PS.style(t, 'text_color')), 'l')
    f = root.find('bk_field'); x, y = at(f); rr(x, y, f.w, f.h, 12, fill(f))
    unit = ('kHz' if khz else 'Hz', 'dB', '')[row]; uw = {'kHz': 34, 'Hz': 26, 'dB': 26, '': 0}[unit]
    ux = O_BK['BK_FIELD_X'] + O_BK['BK_FIELD_W'] - O_BK['BK_PAD'] - uw; cx = ux - (O_BK['BK_CARET_GAP'] if uw else 0) - O_BK['BK_CARET_W']
    s.text(im, card.x + ux, card.y + f.y + f.h / 2, unit, 17, (0x8E,) * 3, 'l')
    d = ImageDraw.Draw(im); ch = O_BK['BK_CARET_H']; d.rectangle((card.x + cx, card.y + f.y + (f.h - ch) // 2, card.x + cx + O_BK['BK_CARET_W'] - 1, card.y + f.y + (f.h - ch) // 2 + ch - 1), fill=(255, 255, 255, 255))
    s.text(im, card.x + cx - 2, card.y + f.y + f.h / 2, ('\u2212' if neg else '') + number, 38, (255, 255, 255), 'r')
    for w in card.children:
        if not w.name.startswith('bk_k') and w.name not in ('bk_dot', 'bk_del', 'bk_sign', 'bk_unitk'): continue
        if w.name == 'bk_unitk' and row != 0: continue
        x, y = at(w); dim = w.name == 'bk_sign' and row != 1
        rr(x, y, w.w, w.h, 9, fill(w))
        if w.name == 'bk_del':
            ic = s.img('qk_delete'); im.alpha_composite(ic, (x + (w.w - ic.width) // 2, y + (w.h - ic.height) // 2))
        else:
            text = 'kHz' if w.name == 'bk_unitk' and khz else 'Hz' if w.name == 'bk_unitk' else '\u2212' if w.name == 'bk_sign' else w.get('text')
            s.text(im, x + w.w / 2, y + w.h / 2, text, 17 if w.name == 'bk_unitk' else 22, (0x5A,) * 3 if dim else (255, 255, 255), 'm')
    return im.convert('RGB')


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    work = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'peqband.png')
    s = PI.Side(work, True, 'en_US'); s.mark = lambda *a: None
    edited = [tuple(b) for b in HD600]
    edited[3] = (1, 0, 2600, -4.1, 3.2)
    shelf = [tuple(b) for b in HD600]
    pg_edited = PP.peqpage(s, 'Sennheiser HD 600', edited, 'Auto · −6.0 dB')
    pg_edited_screen = pg_edited.crop((0, 0, pg_edited.width, SCREEN))
    band4 = band_page(s, edited, 3).crop((0, 0, W, SCREEN))
    keyboard = PK.screen(s, PK.Page(s), 'Sennheiser HD 600 (Edited)', 'abc', hint='', title='Save As')
    panels = [('Preset page, edited', pg_edited_screen),
              ('Band page: band 4, Peak', band4),
              ('Band page: band 1, Low shelf', band_page(s, shelf, 0).crop((0, 0, W, SCREEN))),
              ('Back with unsaved edits', PP.dialog(s, band4, 'Sennheiser HD 600')),
              ('Number keypad: Frequency 2.6 kHz', keypad(s, band4, 0, '2.6', khz=True)),
              ('Number keypad: Gain \u22124.1 dB', keypad(s, band4, 1, '4.1', neg=True)),
              ('Save As: name entry', keyboard.convert('RGB')),
              ('Equalizer page after the save', PQ.peq_page(s, ['AKG K371.txt', 'Sennheiser HD 600.txt', 'Sennheiser HD 600 (edited).txt', 'Sony WH-1000XM4 (ANC on).txt'], 4, True, curve='Custom'))]
    pad, lab = 12, 24
    wid = sum(im.width for _, im in panels) + pad * (len(panels) + 1)
    hei = max(im.height for _, im in panels) + lab + 2 * pad
    out = Image.new('RGB', (wid, hei), (0x2A,) * 3); d = ImageDraw.Draw(out)
    x = pad
    for title, im in panels:
        d.text((x, pad), title, fill=(0xAA,) * 3, font=PI.ANN); out.paste(im.convert('RGB'), (x, pad + lab)); x += im.width + pad
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.save(out_path, optimize=True); print('wrote', out_path, out.size)
    for i, (title, im) in enumerate(panels):
        p = out_path.replace('.png', f'-{i + 1}.png'); im.convert('RGB').save(p, optimize=True)


if __name__ == '__main__':
    main()
