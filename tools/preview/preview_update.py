#!/usr/bin/env python3
"""Preview of the Software Update page (patch/update.c, docs/modules/update.md); a PIL drawing on the page's own built asset, not pixel-exact AWTK.

  preview_update.py WORKDIR OUT.png [--lang CODE]

WORKDIR is a built tree (work/mod-release). The asset's widgets (the stock navbar, the glyph image, the title, the explanation and the pills) are walked by tools/preview/preview_nowplaying.py's painter (the same widget
model the other previews use) at the places tools/pod_ui.py up_layout gives them, the payload's own rule. The download popup is the asset's scrim and card (the Podcasts refresh dialog's pieces: the glass is
approximated here by a flat card, its labels, bar and Cancel row at the asset's boxes, fonts and colours). Every state: idle, checking, up to date, a version available, the popup (0 %, 42 %, cancelling),
downloaded with Install and Check Again, and a few failures. Strings are the built tables'.
"""
import argparse, os, sys
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import awtk_ui, awtk_strings
import pod_ui
import pod_wrap
import preview_nowplaying as NP

W, H, BAR = 320, 450, 30
VERSION, TAG = '1.0.0', '1.0.1'
# state: ((glyph or None, title, explanation or None, pill or None, second pill or None), popup or None); popup: (percentage or None, the count line); %s is the version (put in as the payload does)
OFFER = ('pod_es_download', 'Version %s available' % TAG, 'Current version: %s' % VERSION, None, None)
STATES = [
    ('idle', (('pod_es_download', 'M1+ Music', 'Version %s' % VERSION, 'Check for Update', None), None)),
    ('checking', ((None, 'Checking…', None, None, None), None)),
    ('up to date', (('pod_es_check', 'Up to Date', 'You have the latest version.', 'Check for Update', None), None)),
    ('available', (OFFER[:3] + ('Download and Install', None), None)),
    ('available + notes', (OFFER[:3] + ('Download and Install', 'Release Notes'), None)),
    ('confirm dialog', ((None, '', None, None, None), 'confirm')),   # (the page's block is hidden while the dialog is up)
    ('popup 0 %', (OFFER, (0, '0%'))),
    ('popup 42 %', (OFFER, (42, '42%'))),
    ('popup cancelling', (OFFER, (42, 'Cancelling…'))),
    ('downloaded', (('pod_es_check', 'Update Downloaded', 'Version %s is ready to install.' % TAG, 'Install', 'Check Again'), None)),
    ('no Wi-Fi', (('pod_es_wifi', 'Connect to Wi-Fi first', 'Turn on Wi-Fi and try again.', 'Try Again', None), None)),
    ('cannot reach', (('pod_es_plug', "Can't reach GitHub", 'Check your Wi-Fi connection.', 'Try Again', None), None)),
    ('cannot check', (('pod_es_info', "Can't check for updates", 'GitHub did not name a release. Try again later.', 'Try Again', None), None)),
    ('card full', (('pod_es_card', 'Card is full', 'Free at least 110 MB on the card.', 'Try Again', None), None)),
    ('no match', (('pod_es_info', "Download doesn't match", 'The file was not the version offered. Nothing was changed.', 'Try Again', None), None)),
    ('cancelled', (('pod_es_download', 'Download cancelled', None, 'Download and Install', None), None)),
]
# the keys of the texts that carry the version: the translation has %s where the version goes
VERSIONED = {'Version %s': VERSION, 'Version %s available': TAG, 'Current version: %s': VERSION, 'Version %s is ready to install.': TAG, 'Downloading %s': TAG, 'Download %s (55 MB)? It replaces update.bin on the card.': TAG}


class Page:
    def __init__(self, work, lang):
        raw = os.path.join(work, 'rootfs/release/assets', 'default', 'raw')
        strings = dict(awtk_strings.load(os.path.join(raw, 'strings', lang + '.bin')))
        self.strings = strings
        self.tree = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1plus_update.bin'), 'rb').read())
        self.p = NP.Painter(raw)
        self.raw = raw
        self.dialog = awtk_ui.parse(open(os.path.join(raw, 'ui', 'dialog', 'confirminfo_dialog.bin'), 'rb').read())
        from awtk_style import parse as style_parse
        th = style_parse(open(os.path.join(raw, 'styles', 'default.bin'), 'rb').read())
        it = th.find('label', 'label_centerwhite20_style', 'normal')[0]
        self.pad = (it.get('margin_left') or 0, it.get('margin_right') or 0)   # the message label's margins in the built tree

    def tr(self, s):
        """The text of an English state string in the page's language (the version put back where it goes)."""
        for key, v in VERSIONED.items():
            if s == key.replace('%s', v): return self.strings.get(key, key).replace('%s', v)
        return self.strings.get(s, s)

    def widget(self, win, name, text=None, y=None, **props):
        wd = self.tree.find(name)
        if y is not None: wd.y = y
        wd.set('visible', 'true')
        for k, v in props.items(): wd.set(k, v)
        if text is not None: self.p.sample[name] = text
        self.p.walk(win, wd, 0, 0, (0, 0, W, H), 0, self.tree)

    def pill(self, win, name, s, y):
        wd = self.tree.find(name)
        r = (wd.x, y, wd.w, wd.h)
        ImageDraw.Draw(win).rounded_rectangle([r[0], r[1], r[0] + r[2] - 1, r[1] + r[3] - 1], radius=int(wd.get('style:normal:round_radius')), fill=wd.get('style:normal:bg_color'))
        wd.set('style:normal:text_align_h', 'center')
        layer = Image.new('RGBA', win.size)
        self.p.text(layer, r, self.tr(s), wd)
        win.alpha_composite(layer)

    def popup(self, win, pct, count):
        """The download popup: the scrim, the card (a flat stand-in for its glass), the asset's labels, bar and Cancel row."""
        scrim = self.tree.find('up_pd_scrim').get('style:normal:bg_color')
        a = int(scrim[7:9], 16) if len(scrim) == 9 else 255
        win.alpha_composite(Image.new('RGBA', win.size, (0, 0, 0, a)))
        card = self.tree.find('up_pd_card'); kids = {c.name: c for c in card.children}
        d = ImageDraw.Draw(win)
        d.rounded_rectangle([card.x, card.y, card.x + card.w - 1, card.y + card.h - 1], radius=14, fill='#2C2C2E')
        for name, text in (('up_pd_title', self.tr('Downloading %s' % TAG)), ('up_pd_name', self.tr('This may take a few minutes.')), ('up_pd_count', self.tr(count))):
            wd = kids[name]; layer = Image.new('RGBA', win.size)
            self.p.text(layer, (card.x + wd.x, card.y + wd.y, wd.w, wd.h), text, wd)
            win.alpha_composite(layer)
        tr, fl = kids['up_pd_track'], kids['up_pd_fill']
        for wd, w in ((tr, tr.w), (fl, max(1, tr.w * (pct or 0) // 100))):
            col = wd.get('style:normal:bg_color'); layer = Image.new('RGBA', win.size)
            ImageDraw.Draw(layer).rounded_rectangle([card.x + wd.x, card.y + wd.y, card.x + wd.x + w - 1, card.y + wd.y + wd.h - 1], radius=wd.h // 2, fill=(255, 255, 255, 51) if wd is tr else col)
            win.alpha_composite(layer)
        c = kids['up_pd_cancel']
        d.rectangle([card.x, card.y + c.y, card.x + card.w - 1, card.y + c.y], fill='#444444')
        layer = Image.new('RGBA', win.size)
        wd_c = c; wd_c.set('style:normal:text_align_h', 'center')
        self.p.text(layer, (card.x + c.x, card.y + c.y, c.w, c.h), self.tr('Cancel'), wd_c)
        if count == 'Cancelling…': layer.putalpha(layer.getchannel('A').point(lambda v: v * 2 // 5))   # the Cancel row goes dead: dimmed
        win.alpha_composite(layer)

    def confirm(self, win):
        """The stock confirm dialog as built: its card (confirminfo_bg), the message label (260 x 80 at y 25 less the style's margins, 20 px, centred, wrapped at spaces) and the two buttons at the asset's boxes with Cancel / Download."""
        d = self.dialog; x0, y0 = (W - d.w) // 2, (H - d.h) // 2
        alpha = int(d.get('highlight').split('alpha=')[1].rstrip(')'))   # the dialog highlighter dims the window below
        win.alpha_composite(Image.new('RGBA', win.size, (0, 0, 0, alpha)))
        win.alpha_composite(Image.open(os.path.join(self.raw, 'images', 'xx', 'confirminfo_bg.png')).convert('RGBA'), (x0, y0))
        st = self.p.stb(20); f = self.p.font(20); dr = ImageDraw.Draw(win)
        s = self.tr('Download %s (55 MB)? It replaces update.bin on the card.').replace('%s', TAG)
        wmax = d.w - self.pad[0] - self.pad[1]
        lines = pod_wrap.wrap(s, [st.layout(c)[1] for c in s], wmax, 4, st.layout('…')[1])
        for i, ln in enumerate(lines):
            lx = x0 + self.pad[0] + (wmax - st.layout(ln)[1]) // 2
            for ch, pen in st.layout(ln)[0]: dr.text((lx + pen, y0 + 25 + i * 24 + f.getmetrics()[0]), ch, font=f, fill='#FFFFFF', anchor='ls')
        for name, label in (('btn_cancel', 'Cancel'), ('btn_enter', 'Download')):
            b = d.find(name); t = self.tr(label)
            tx = x0 + b.x + (b.w - st.layout(t)[1]) // 2
            for ch, pen in st.layout(t)[0]: dr.text((tx + pen, y0 + b.y + (b.h - 20) // 2 + f.getmetrics()[0]), ch, font=f, fill='#FFFFFF', anchor='ls')

    def panel(self, state):
        (glyph, title, text, pill, pill2), popup = state
        win = Image.new('RGBA', (W, H), (0, 0, 0, 255))
        nav = [c for c in self.tree.children if c.name == 'navigationbar_view']
        saved = self.tree.children; self.tree.children = nav
        self.p.sample = {'label_title': self.strings.get('Software Update', 'Software Update')}
        self.p.walk(win, self.tree, 0, 0, (0, 0, W, H), 0, self.tree)
        self.tree.children = saved
        ys = pod_ui.UP_YS   # the fixed places: the same in every state
        if glyph: self.widget(win, 'up_icon', y=ys[0], image=glyph)
        self.widget(win, 'up_title', self.tr(title), y=ys[1])
        if text:
            wd = self.tree.find('up_text'); px = int(wd.get('style:normal:font_size')); st = self.p.stb(px); s = self.tr(text)
            f = self.p.font(px); d = ImageDraw.Draw(win)
            for i, ln in enumerate(pod_wrap.wrap(s, [st.layout(c)[1] for c in s], wd.w, 3, st.layout('…')[1])):
                x0 = wd.x + (wd.w - st.layout(ln)[1]) // 2
                for ch, pen in st.layout(ln)[0]: d.text((x0 + pen, ys[2] + i * (px + 6) + f.getmetrics()[0]), ch, font=f, fill=wd.get('style:normal:text_color'), anchor='ls')
        if pill: self.pill(win, 'up_pill', pill, ys[3])
        if pill2: self.pill(win, 'up_pill2', pill2, ys[4])
        if popup == 'confirm': self.confirm(win)
        elif popup: self.popup(win, *popup)
        full = Image.new('RGBA', (W, BAR + H), (0, 0, 0, 255)); full.alpha_composite(win, (0, BAR))
        ImageDraw.Draw(full).text((W // 2, 21), '9:41', font=self.p.font(16), fill='#FFFFFF', anchor='ms')
        return full


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work'); ap.add_argument('out'); ap.add_argument('--lang', default='en_US')
    a = ap.parse_args()
    page = Page(a.work, a.lang)
    pad, top, per = 10, 18, 7
    rows = (len(STATES) + per - 1) // per
    out = Image.new('RGB', (per * (W + pad) + pad, rows * (BAR + H + top + 8) + 18), (40, 40, 40)); d = ImageDraw.Draw(out)
    for i, (label, st) in enumerate(STATES):
        x, y = pad + (i % per) * (W + pad), (i // per) * (BAR + H + top + 8)
        out.paste(page.panel(st).convert('RGB'), (x, y + top)); d.text((x, y + 3), label, fill=(220, 220, 220), font=ImageFont.load_default())
    d.text((pad, out.height - 14), 'PIL drawing on the built asset (widgets walked by the shared painter; the popup\'s glass is a flat stand-in), not AWTK', fill=(160, 160, 160))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    out.save(a.out, optimize=True); print('wrote', a.out)


if __name__ == '__main__': main()
