#!/usr/bin/env python3
"""Approximate PIL mock-up of Get Info (patch/songinfo.c, docs/modules/songinfo.md): the stock navbar from the page's built asset, the 96 px cover (a stand-in gradient, corners 8 px) with the title, artist and
album beside it, then the label / value pairs, laid out with the payload's own constants and the project's text model (the wrapper pod_wrap, the font of the built tree). Not pixel-exact AWTK.

  preview_songinfo.py WORKDIR OUT.png [--lang CODE]
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui, awtk_strings
import pod_wrap
import preview_nowplaying as NP

W, H, BAR = 320, 450, 30
X, TOP, COVER, TX, TW, WIDTH = 16, 16, 96, 124, 180, 288
PITCH = {'head': 26, 'sub': 20, 'key': 18, 'val': 22}
PX = {'head': 22, 'sub': 16, 'key': 14, 'val': 18}
RGB = {'head': '#FFFFFF', 'sub': '#8E8E93', 'key': '#8E8E93', 'val': '#FFFFFF'}
HEAD_GAP, PAIR_GAP, VIEW = 16, 10, 400

SAMPLES = [
    ('FLAC', dict(title='Blue in Green', artist='Miles Davis', album='Kind of Blue', pairs=[
        ('Format', 'FLAC'), ('Sample Rate / Bit Depth', '44.1 kHz / 16-bit'), ('Bitrate', '863 kbps'), ('Duration', '5:37'), ('Size', '36.4 MB'),
        ('Path', '/mnt/mmc/Music/Miles Davis/Kind of Blue/03 Blue in Green.flac')]), 0),
    ('MP3 (no bit depth)', dict(title='Wish You Were Here (2011 Remastered Version)', artist='Pink Floyd', album='Wish You Were Here', pairs=[
        ('Format', 'MP3'), ('Sample Rate', '44.1 kHz'), ('Bitrate', '256 kbps'), ('Duration', '5:34'), ('Size', '10.7 MB'),
        ('Path', '/mnt/mmc/Music/Pink Floyd/Wish You Were Here/01 Wish You Were Here.mp3')]), 0),
    ('header unreadable', dict(title='Untitled', artist='', album='', pairs=[
        ('Format', 'M4A'), ('Bitrate', '165 kbps'), ('Duration', '3:12'), ('Size', '3.9 MB'), ('Path', '/mnt/mmc/Music/untitled.m4a')]), 0),
    ('FLAC, scrolled', dict(title='Blue in Green', artist='Miles Davis', album='Kind of Blue', pairs=[
        ('Format', 'FLAC'), ('Sample Rate / Bit Depth', '96 kHz / 24-bit'), ('Bitrate', '2910 kbps'), ('Duration', '1:02:05'), ('Size', '1.23 GB'),
        ('Path', '/mnt/mmc/Music/A Very Long Folder Name/Another Quite Long Folder Name/Yet Another Folder/01 A Track With A Long File Name.flac')]), 60),
]


class Page:
    def __init__(self, work, lang):
        raw = os.path.join(work, 'rootfs/release/assets', 'default', 'raw')
        self.strings = dict(awtk_strings.load(os.path.join(raw, 'strings', lang + '.bin')))
        self.tree = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1plus_songinfo.bin'), 'rb').read())
        self.p = NP.Painter(raw)

    def tr(self, s): return self.strings.get(s, s)

    def lines(self, kind, text, room, maxl):
        st = self.p.stb(PX[kind])
        return pod_wrap.wrap(text, [st.layout(c)[1] for c in text], room, maxl, st.layout('…')[1])

    def text(self, d, kind, s, x, y):
        f, st = self.p.font(PX[kind]), self.p.stb(PX[kind])
        for ch, pen in st.layout(s)[0]: d.text((x + pen, y + (PITCH[kind] - PX[kind]) // 2 + f.getmetrics()[0]), ch, font=f, fill=RGB[kind], anchor='ls')

    def cover(self):
        c = Image.new('RGBA', (COVER, COVER))
        px = c.load()
        for y in range(COVER):
            for x in range(COVER): px[x, y] = (150 - y // 2, 60 + x // 3, 70 + y // 3, 255)
        m = Image.new('L', (COVER, COVER), 0)
        ImageDraw.Draw(m).rounded_rectangle([0, 0, COVER - 1, COVER - 1], radius=8, fill=255)
        c.putalpha(m)
        return c

    def panel(self, s, off):
        win = Image.new('RGBA', (W, H), (0, 0, 0, 255))
        nav = [c for c in self.tree.children if c.name == 'navigationbar_view']
        saved = self.tree.children; self.tree.children = nav
        self.p.sample = {'label_title': self.tr('Get Info')}
        self.p.walk(win, self.tree, 0, 0, (0, 0, W, H), 0, self.tree)
        self.tree.children = saved
        view = Image.new('RGBA', (W, VIEW), (0, 0, 0, 255))
        d = ImageDraw.Draw(view)
        head = self.lines('head', s['title'], TW, 2)
        sub = [ln for t in (s['artist'], s['album']) if t for ln in self.lines('sub', t, TW, 1)]
        block = len(head) * PITCH['head'] + len(sub) * PITCH['sub']
        y0 = TOP + (COVER - block) // 2 - off
        view.alpha_composite(self.cover(), (X, TOP - off)) if TOP - off + COVER > 0 else None
        for i, ln in enumerate(head): self.text(d, 'head', ln, TX, y0 + i * PITCH['head'])
        for i, ln in enumerate(sub): self.text(d, 'sub', ln, TX, y0 + len(head) * PITCH['head'] + i * PITCH['sub'])
        y = TOP + COVER + HEAD_GAP - off
        for key, val in s['pairs']:
            ks = self.tr(key) if key not in ('Sample Rate / Bit Depth',) else self.tr('Sample Rate') + ' / ' + self.tr('Bit Depth')
            vals = self.lines('val', val, WIDTH, 40)
            for kind, lines in (('key', self.lines('key', ks, WIDTH, 1)), ('val', vals)):
                for ln in lines:
                    if 0 <= y and y + PITCH[kind] <= VIEW: self.text(d, kind, ln, X, y)   # (a text is drawn only when wholly in the view)
                    y += PITCH[kind]
            y += PAIR_GAP
        win.alpha_composite(view, (0, 50))
        full = Image.new('RGBA', (W, BAR + H), (0, 0, 0, 255)); full.alpha_composite(win, (0, BAR))
        ImageDraw.Draw(full).text((W // 2, 21), '9:41', font=self.p.font(16), fill='#FFFFFF', anchor='ms')
        return full


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work'); ap.add_argument('out'); ap.add_argument('--lang', default='en_US')
    a = ap.parse_args()
    page = Page(a.work, a.lang)
    pad, top = 10, 18
    out = Image.new('RGB', (len(SAMPLES) * (W + pad) + pad, BAR + H + top + 8), (40, 40, 40)); d = ImageDraw.Draw(out)
    for i, (label, s, off) in enumerate(SAMPLES):
        x = pad + i * (W + pad)
        d.text((x, 2), label, fill='#AAAAAA')
        out.paste(page.panel(s, off).convert('RGB'), (x, top))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    out.save(a.out)
    print('wrote', a.out, out.size)


if __name__ == '__main__': main()
