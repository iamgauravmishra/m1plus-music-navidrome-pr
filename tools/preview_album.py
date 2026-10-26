#!/usr/bin/env python3
"""PIL mock-up of the stock album page (albuminfo_page) as the release restyles it (docs/ui.md) from a
built tree (approximate, not AWTK; sample data): the header item (cover, title, artist, "year . N
tracks", Play all and Shuffle) scrolling with the stock rows, laid out with the AH_* numbers of
patch/offsets.inc, the tree's own ui/m1pod_cover.bin navbar and default.ttf rasterized the
stb_truetype way (tools/preview_font.py); the cover is rendered by the cover thread at 120 px and
drawn 1:1.

Panels: an album (year and tracks), a long title (an hscroll_label shows it from its left margin
when it starts to scroll), the same album scrolled up so the header leaves, and the All albums card.

Usage: venv/bin/python -I tools/preview_album.py WORKDIR OUT.png
"""
import argparse, os, re, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
from awtk_ui import Widget
import preview_font   # noqa: F401  (redirects the painters' text to stb_raster, the tree's font)
import preview_all, pod_ui
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'test'))

W, BAR, NAVBAR, LIST_H = 320, 30, pod_ui.NAVBAR_H, pod_ui.CLIENT_H - pod_ui.NAVBAR_H
ART_SIZE = 168   # the previews' source art (a Cover Flow cache file's size); the header cover is 120


def constants():
    out = {}
    for line in open(os.path.join(ROOT, 'patch', 'offsets.inc')):
        m = re.match(r'#define (\w+) (-?(?:0x[0-9a-fA-F]+|\d+))u?\s*(?:/\*.*)?$', line.strip())
        if m: out[m.group(1)] = int(m.group(2), 0)
    return out


C = constants()
TRACKS = ['So What', 'Freddie Freeloader', 'Blue in Green', 'All Blues', 'Flamenco Sketches', 'Flamenco Sketches (Alternate Take)',
          'So What (Studio Chatter)', 'Freddie Freeloader (Alternate Take)']


def art(kind):
    """A cover as the Cover Flow cache would hold it (ART_SIZE square): the wallpaper's centre, a
    two-tone design, or the placeholder disc."""
    if kind == 'sky':
        im = Image.open(os.path.join(ROOT, 'assets', 'starry-night-320x480.png')).convert('RGB').crop((0, 90, 320, 410))
        return im.resize((ART_SIZE, ART_SIZE), Image.LANCZOS)
    im = Image.new('RGB', (ART_SIZE, ART_SIZE)); d = ImageDraw.Draw(im)
    if kind == 'disc':
        d.rectangle([0, 0, ART_SIZE, ART_SIZE], fill=(34, 34, 34))
        c = ART_SIZE / 2
        d.ellipse([c - 70, c - 70, c + 70, c + 70], fill=(46, 46, 46)); d.ellipse([c - 60, c - 60, c + 60, c + 60], fill=(70, 70, 70))
        d.ellipse([c - 20, c - 20, c + 20, c + 20], fill=(34, 34, 34))
    else:
        for y in range(ART_SIZE): d.line([(0, y), (ART_SIZE, y)], fill=(200 - y // 2, 90 + y // 4, 60 + y // 2))
        d.ellipse([34, 30, 134, 130], outline=(255, 240, 210), width=5); d.rectangle([20, 140, 148, 148], fill=(30, 20, 40))
    return im


def page(work, title, album, artist, meta, cover, n, scroll=0):
    """The stock albuminfo_page as the release leaves it: the restyled header item (AH_* numbers of
    patch/offsets.inc: cover, title, artist, year line, Play all and Shuffle) over the stock rows."""
    raw = os.path.join(work, preview_all.RAW)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1pod_cover.bin'), 'rb').read())
    nav = next(w for w in root.walk() if w.name == 'navigationbar_view')
    for w in root.walk():
        if w.name == 'label_title': w.set('text', title); w.set('name', 'label_title_preview')
    root.children = [nav]
    LW = 310   # the list_view's scroll_view (a 10 px scroll bar at the right)
    sv = Widget('scroll_view', 0, NAVBAR, LW, LIST_H)

    def line(y, h, text, size, colour):
        w = Widget('hscroll_label', C['AH_TEXT_X'], y - scroll, C['AH_TEXT_W'], h,
                   [('text', text), ('ellipses', 'true')])
        for k, v in (('font_size', str(size)), ('text_color', colour), ('text_align_h', 'left')): w.set(f'style:normal:{k}', v)
        return w
    hdr = Widget('list_item', 0, -scroll, LW, C['AH_HDR_H'], [('style', 'list_item_notpress_style')])
    sv.children.append(hdr)
    sv.children += [line(C['AH_TITLE_Y'], C['AH_TITLE_H'], album, 21, '#FFFFFF'),
                    line(C['AH_ARTIST_Y'], C['AH_ARTIST_H'], artist, 18, '#AAAAAA'),
                    line(C['AH_META_Y'], C['AH_META_H'], meta, 15, '#9C9C9C')]
    for i in range(n):   # the stock rows: "N  title" in 21 px white from x 12, 64 px apart
        y = C['AH_HDR_H'] + i * 64 - scroll
        row = Widget('list_item', 0, y, LW, 64, [('style', 'list_item_style')])
        lab = Widget('hscroll_label', 12, 0, LW - 24, 60,
                     [('style', 'srlabel_leftwhite21_style'), ('text', f'{i + 1}  {TRACKS[i % len(TRACKS)]}'),
                      ('only_parent_focus', 'true'), ('ellipses', 'true')])
        row.children = [lab]; sv.children.append(row)
    root.children.append(sv)
    painter = preview_all.MenuPainter(raw)
    im = painter.render(root, 0)
    oy = BAR + NAVBAR - scroll
    clip = (0, BAR + NAVBAR, W, BAR + NAVBAR + LIST_H)
    layer = Image.new('RGBA', im.size)
    ld = ImageDraw.Draw(layer)
    layer.paste(cover.resize((C['AH_ART'],) * 2, Image.LANCZOS).convert('RGBA'), (C['AH_PAD'], oy + C['AH_ART_Y']))   # rendered at 120 px: drawn 1:1
    for label, x in (('Play all', C['AH_PAD']), ('Shuffle', C['AH_SHUFFLE_X'])):
        y = oy + C['AH_BTN_Y']
        ld.rectangle([x, y, x + C['AH_BTN_W'] - 1, y + C['AH_BTN_H'] - 1], fill='#1E1E1E', outline='#3A3A3A')
        f, st = painter.font(20), painter.stb(20)
        tw = st.layout(label)[1]; top = y + (C['AH_BTN_H'] - 20) // 2
        for ch, pen in st.layout(label)[0]:
            ld.text((x + (C['AH_BTN_W'] - tw) // 2 + pen, top + f.getmetrics()[0]), ch, font=f, fill='#FFFFFF', anchor='ls')
    im.alpha_composite(layer.crop(clip), clip[:2])
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work'); ap.add_argument('out')
    a = ap.parse_args()
    long_title = 'The Rise and Fall of Ziggy Stardust and the Spiders from Mars'
    shots = [('an album', page(a.work, 'Cover Flow', 'Kind of Blue', 'Miles Davis', '1959 · 8 tracks', art('sky'), 8)),
             ('a long title', page(a.work, 'Cover Flow', long_title, 'David Bowie with the Spiders from Mars', '1972 · 8 tracks',
                                   art('design'), 8)),
             ('scrolled', page(a.work, 'Cover Flow', 'Kind of Blue', 'Miles Davis', '1959 · 8 tracks', art('sky'), 8, scroll=150)),
             ('All albums', page(a.work, 'Miles Davis', 'All albums', 'Miles Davis', '24 tracks', art('disc'), 8))]
    pad, top = 12, 20
    out = Image.new('RGB', (len(shots) * (W + pad) + pad, 480 + top + 2 * pad + 16), (40, 40, 40))
    d = ImageDraw.Draw(out)
    for i, (cap, im) in enumerate(shots):
        x = pad + i * (W + pad)
        out.paste(im.convert('RGB'), (x, pad + top)); d.text((x, pad + 4), cap, fill=(230, 230, 230))
    d.text((pad, out.height - 18), 'approximate PIL mock-ups (not AWTK); cover rendered at 120 px by the stock cover thread, drawn 1:1; sample data; no durations (not in the database)',
           fill=(160, 160, 160))
    out.quantize(colors=192).save(a.out, optimize=True); print('wrote', a.out)


if __name__ == '__main__': main()
