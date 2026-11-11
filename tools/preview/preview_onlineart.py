#!/usr/bin/env python3
"""Preview of the Find Cover & Lyrics page (patch/onlineart.c, docs/modules/onlineart.md); a PIL drawing on the page's own built asset, not pixel-exact AWTK.

  preview_onlineart.py WORKDIR OUT.png [--lang CODE]

WORKDIR is a built tree (work/mod-release). What the asset defines is walked by tools/preview/preview_nowplaying.py's painter (the same widget model the other previews use): the stock navbar, the state
block (the glyph image, the title, the explanation, the Try Again pill: their boxes, fonts and colours from ui/m1plus_onlineart.bin, stacked and centred by tools/pod_ui.py oa_es_layout, the
payload's rule), the lyrics header and the confirmation's labels and pills. What the payload paints itself (the chip row, the thumbnails, the candidate rows and badges, the lyrics lines) is drawn
here from the same numbers (tools/pod_search.py for the Search page's frame; the lyrics lines are wrapped by tools/pod_wrap.py, the payload's algorithm, at the 17 px text style and 288 px). Every state:
loading, Covers (one current, scrolled), the confirmation (Use / Replace / a failure), Lyrics (one saved), the lyrics detail with a long English line and a long CJK line wrapped (Save / Replace), and
each empty or failed state. The covers and lyrics are invented samples. Strings are the built tables'.
"""
import argparse, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import awtk_ui, awtk_strings
import pod_search as PS
import pod_ui
import pod_wrap
import preview_nowplaying as NP

W, H, BAR, NAVBAR = 320, 450, 30, 50
TILE, GAP, X0, Y0, PITCH = 88, 12, 16, 8, 98
LIST_Y, LIST_H, ROW_H = PS.SE_LIST_Y, PS.SE_LIST_H, PS.SE_ROW_H
LY_PITCH, LY_GAP, LY_W, LY_PX = 24, 12, 288, 17
COLORS = [(0xC2, 0x4A, 0x3C), (0x3C, 0x6E, 0xC2), (0x6E, 0xA8, 0x4A), (0xB8, 0x8A, 0x2E), (0x8A, 0x4A, 0xB8), (0x2E, 0x9A, 0x9A), (0x9A, 0x5A, 0x3C)]
ROWS = [('Sample Song', 'Sample Band · Sample Album (Remastered) · 4:19', True), ('Sample Song', 'Sample Band · Sample Album · 4:21', True), ('Sample Song (Live)', 'Sample Band · Live in Paris · 4:35', False),
        ('Sample Song', 'Another Band · Cover Versions · 3:58', False)]
LONG_EN = 'This is a long English test line that goes on and on, far past the width of the screen, to show that a lyric line wraps onto as many lines as it needs and is never cut'
LONG_CJK = '示例歌词第一行是一句很长的测试文字，用来检查没有空格的长句子会在字符之间换行，而不是被省略号截断。'
LYRICS_EN = ['Line one of the sample song', 'Line two of the sample song', '', LONG_EN, 'Line four of the sample song']
LYRICS_CJK = ['示例歌词第一行', '示例歌词第二行', '', LONG_CJK, '示例歌词最后一行']
STATES = [
    ('loading', dict(tab=0, block='searching')),
    ('Covers, one current', dict(tab=0, covers=7, current=1)),
    ('Covers, scrolled (12)', dict(tab=0, covers=12, scroll=40)),
    ('Cover: Use This Cover', dict(mode=1, pill='Use This Cover', big=True)),
    ('Cover: Replace Cover', dict(mode=1, pill='Replace Cover', big=True)),
    ('Cover: failure', dict(mode=1, hint="Can't connect")),
    ('Lyrics', dict(tab=1, rows=4)),
    ('Lyrics, one saved', dict(tab=1, rows=4, saved=1)),
    ('Lyrics detail: long English line', dict(mode=2, pill='Save Lyrics', lyrics=LYRICS_EN)),
    ('Lyrics detail: long CJK line', dict(mode=2, pill='Replace Lyrics', lyrics=LYRICS_CJK)),
    ('lyrics busy', dict(tab=1, block='lyrics busy')),
    ('covers busy', dict(tab=0, block='covers busy')),
    ('no lyrics', dict(tab=1, block='no lyrics')),
    ('no covers', dict(tab=0, block='no covers')),
    ('no Wi-Fi', dict(tab=0, block='no Wi-Fi')),
    ('no connection', dict(tab=1, block='no connection')),
    ('server error', dict(tab=0, block='server error')),
    ('certificate', dict(tab=0, block='certificate')),
    ('no date', dict(tab=0, block='no date')),
    ('no card', dict(tab=1, block='no card')),
    ('no certificates', dict(tab=0, block='no certificates')),
    ('no memory', dict(tab=0, block='no memory')),
]


def cover(i, side=TILE, r=8):
    c = COLORS[i % len(COLORS)]
    im = Image.new('RGB', (side, side), c); d = ImageDraw.Draw(im)
    d.ellipse([side // 4, side // 4, side * 3 // 4, side * 3 // 4], fill=tuple(v // 2 for v in c))
    mask = Image.new('L', (side * 4, side * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, side * 4 - 1, side * 4 - 1], radius=r * 4, fill=255)
    out = Image.new('RGBA', (side, side)); out.paste(im, (0, 0), mask.resize((side, side), Image.LANCZOS)); return out


class Page:
    def __init__(self, work, lang):
        raw = os.path.join(work, 'rootfs/release/assets', 'default', 'raw')
        strings = dict(awtk_strings.load(os.path.join(raw, 'strings', lang + '.bin')))
        self.tr = lambda k: strings.get(k, k) if k else ''
        self.tree = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1plus_onlineart.bin'), 'rb').read())
        self.p = NP.Painter(raw)

    def text(self, d, x, y, w, h, s, px, fill, align='left'):
        st = self.p.stb(px); f = self.p.font(px)
        adv = lambda t: st.layout(t)[1]
        while s and adv(s) > w: s = s[:-2] + '…' if s[-1] != '…' else s[:-2] + '…'
        tw = adv(s); x0 = x if align == 'left' else x + (w - tw) // 2
        for ch, pen in st.layout(s)[0]: d.text((x0 + pen, y + (h - px) // 2 + f.getmetrics()[0]), ch, font=f, fill=fill, anchor='ls')

    def widget(self, win, name, text=None, y=None, oy=0, **props):
        """A widget of the asset, shown: walked by the painter at its own box (y: another window y), the text a sample."""
        wd = self.tree.find(name)
        if y is not None: wd.y = y
        wd.set('visible', 'true')
        for k, v in props.items(): wd.set(k, v)
        if text is not None: self.p.sample[name] = text
        self.p.walk(win, wd, 0, oy, (0, 0, W, H), 0, self.tree)

    def pill(self, win, name, s, y=None, oy=0):
        """A pill button of the asset: its fill and radius from the asset's style, its text in the style's font."""
        wd = self.tree.find(name)
        r = (wd.x, (wd.y if y is None else y) + oy, wd.w, wd.h)
        ImageDraw.Draw(win).rounded_rectangle([r[0], r[1], r[0] + r[2] - 1, r[1] + r[3] - 1], radius=int(wd.get('style:normal:round_radius')), fill=wd.get('style:normal:bg_color'))
        wd.set('style:normal:text_align_h', 'center')
        layer = Image.new('RGBA', win.size)
        self.p.text(layer, r, self.tr(s), wd)
        win.alpha_composite(layer)

    def chips(self, d, tab):
        x = PS.SE_CHIP_X
        for i, k in enumerate(('Covers', 'Lyrics')):
            t = self.tr(k); w = self.p.stb(16).layout(t)[1] + 2 * PS.SE_CHIP_PAD
            if i == tab: d.rounded_rectangle([x, 52, x + w - 1, 52 + PS.SE_CHIP_H - 1 + 2], radius=PS.SE_CHIP_R, fill=PS.CHIP_ON_RGB)
            self.text(d, x, 52 + PS.SE_CHIP_Y, w, PS.SE_CHIP_H, t, 16, PS.CHIP_ON_INK if i == tab else '#FFFFFF', 'center')
            x += w + PS.SE_CHIP_GAP

    def badge(self, d, right, y, s, on):
        t = self.tr(s); w = self.p.stb(12).layout(t)[1] + 14
        d.rounded_rectangle([right - w, y, right - 1, y + 17], radius=4, fill=PS.CHIP_ON_RGB if on else PS.SEP_RGB)
        self.text(d, right - w, y, w, 18, t, 12, PS.CHIP_ON_INK if on else PS.SUB_RGB, 'center')

    def block(self, win, key):
        """The state block: the asset's glyph, title, explanation and pill, placed as the payload places them."""
        if key == 'searching': glyph, title, text, pill = None, 'Searching…', None, False
        else: glyph, title, text, pill = pod_ui.OA_ES_STATES[key]
        ys = pod_ui.oa_es_layout(glyph, text, pill)
        if glyph: self.widget(win, 'oa_es_icon', y=ys[0], image=glyph)
        self.widget(win, 'oa_status', self.tr(title), y=ys[1])
        if text:   # the explanation: the label breaks at spaces (word_wrap), drawn here with the shared wrapper
            wd = self.tree.find('oa_es_text'); px = int(wd.get('style:normal:font_size')); st = self.p.stb(px); s = self.tr(text)
            for i, ln in enumerate(pod_wrap.wrap(s, [st.layout(c)[1] for c in s], wd.w, 3, st.layout('…')[1])):
                self.text(ImageDraw.Draw(win), wd.x, ys[2] + i * (px + 4), wd.w, px, ln, px, wd.get('style:normal:text_color'), 'center')
        if pill: self.pill(win, 'oa_es_retry', 'Try Again', y=ys[3])

    def lyric_lines(self, cd, lyrics):
        """The detail's lines as the payload lays them out: each text line wrapped to 288 px by the payload's algorithm (40 lines at most, so never an ellipsis), a blank line a 12 px gap."""
        st = self.p.stb(LY_PX); y = 8
        for ln in lyrics:
            if not ln: y += LY_GAP; continue
            for piece in pod_wrap.wrap(ln, [st.layout(c)[1] for c in ln], LY_W, 40, st.layout('…')[1]):
                self.text(cd, 16, y, LY_W, LY_PITCH, piece, LY_PX, '#FFFFFF'); y += LY_PITCH

    def panel(self, st):
        win = Image.new('RGBA', (W, H), (0, 0, 0, 255))
        nav = [c for c in self.tree.children if c.name == 'navigationbar_view']
        saved = self.tree.children; self.tree.children = nav
        self.p.sample = {'label_title': self.tr('Cover & Lyrics')}
        self.p.walk(win, self.tree, 0, 0, (0, 0, W, H), 0, self.tree)
        self.tree.children = saved
        d = ImageDraw.Draw(win)
        mode = st.get('mode', 0)
        if mode == 1:
            if st.get('big'): win.alpha_composite(cover(st.get('cover', 1), 240), (40, NAVBAR + 8))
            else: d.rounded_rectangle([40, NAVBAR + 8, 279, NAVBAR + 247], radius=8, fill='#2B2B2B')
            for n, s in (('oa_dc_name', 'Sample Album (Remastered)'), ('oa_dc_artist', 'Sample Band'), ('oa_dc_source', 'iTunes')):
                self.p.sample[n] = s
                self.p.walk(win, self.tree.find(n), 0, NAVBAR, (0, 0, W, H), 0, self.tree)
            if st.get('hint'):
                self.widget(win, 'oa_hint', self.tr(st['hint']), oy=NAVBAR)
            if st.get('pill'): self.pill(win, 'oa_save', st['pill'], oy=NAVBAR)
        else:
            if mode == 2:
                self.widget(win, 'oa_dh_title', 'Sample Song')
                self.widget(win, 'oa_dh_sub', 'Sample Band · Sample Album · 4:19')
            else:
                self.chips(d, st.get('tab', 0))
            d.rectangle([0, PS.SE_SEP_Y, W - 1, PS.SE_SEP_Y], fill=PS.SEP_RGB)
            off = st.get('scroll', 0)
            clip = Image.new('RGBA', (W, LIST_H), (0, 0, 0, 255)); cd = ImageDraw.Draw(clip)
            for i in range(st.get('covers', 0)):
                x, y = X0 + (i % 3) * (TILE + GAP), Y0 + (i // 3) * PITCH - off
                clip.alpha_composite(cover(i), (x, y))
                if i == st.get('current', -1):
                    cd.rectangle([x - 3, y - 3, x + TILE + 2, y + TILE + 2], outline='#FFFFFF', width=2)
            for r in range(st.get('rows', 0)):
                t, sub, syn = ROWS[r]; y = r * ROW_H
                self.text(cd, 16, y + 7, 288 - 70, 24, t, 21, '#FFFFFF')
                self.text(cd, 16, y + 33, 288, 20, sub, 18, '#AAAAAA')
                if r == st.get('saved', -1): self.badge(cd, 304, y + 10, 'Saved', True)
                elif syn: self.badge(cd, 304, y + 10, 'Synced', False)
                cd.rectangle([16, y + ROW_H - 1, 303, y + ROW_H - 1], fill='#222222')
            if mode == 2: self.lyric_lines(cd, st['lyrics'])
            win.alpha_composite(clip, (0, LIST_Y))
            if st.get('block'): self.block(win, st['block'])
            if mode == 2:
                ImageDraw.Draw(win).rectangle([0, LIST_Y + 300, W, LIST_Y + LIST_H], fill=(0, 0, 0))
                self.pill(win, 'oa_lsave', st['pill'])
        full = Image.new('RGBA', (W, BAR + H), (0, 0, 0, 255)); full.alpha_composite(win, (0, BAR))
        ImageDraw.Draw(full).text((W // 2, 21), '9:41', font=self.p.font(16), fill='#FFFFFF', anchor='ms')
        return full


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work'); ap.add_argument('out'); ap.add_argument('--lang', default='en_US')
    a = ap.parse_args()
    page = Page(a.work, a.lang)
    pad, top, per = 10, 18, 6
    rows = (len(STATES) + per - 1) // per
    out = Image.new('RGB', (per * (W + pad) + pad, rows * (BAR + H + top + 8) + 18), (40, 40, 40)); d = ImageDraw.Draw(out)
    for i, (label, st) in enumerate(STATES):
        x, y = pad + (i % per) * (W + pad), (i // per) * (BAR + H + top + 8)
        out.paste(page.panel(st).convert('RGB'), (x, y + top)); d.text((x, y + 3), label, fill=(220, 220, 220), font=ImageFont.load_default())
    d.text((pad, out.height - 14), 'PIL drawing on the built asset (widgets walked by the shared painter), not AWTK; invented sample covers and lyrics', fill=(160, 160, 160))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    out.save(a.out, optimize=True); print('wrote', a.out)


if __name__ == '__main__': main()
