#!/usr/bin/env python3
"""PIL mock-up of the stock album page (albuminfo_page) as the release restyles it (docs/ui.md) from a
built tree (approximate, not AWTK; sample data): the header item (centred cover with rounded corners,
title, artist, "year . N tracks", the round Shuffle and the Play all pill) scrolling with the stock
rows, laid out with the AH_* numbers of patch/offsets.inc, the tree's own ui/m1pod_cover.bin navbar
(its title transparent, as the page theme makes it) and default.ttf rasterized the stb_truetype way
(tools/preview_font.py); the cover is rendered by the cover thread at 160 px and drawn 1:1, its corners
the corners painted as the payload does (pod_corners) in black or the tint, Shuffle and the play glyph the tree's own images.

Panels: an album (year and tracks), a long title (an hscroll_label shows it from its left margin
when it starts to scroll), the All albums card (the placeholder disc), a CJK title, and the album
scrolled up so the header leaves. The track rows show the number in its own #AAAAAA column before the white title
(rows_track_number). Two more panels show the Composers / Artists list (class_page): no placeholder icon, the name at the
12 px margin, the playing row's wave before the chevron (rows_track_icon).

Usage: venv/bin/python -I tools/preview_album.py WORKDIR OUT.png
"""
import argparse, os, re, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
from awtk_ui import Widget
import preview_font   # noqa: F401  (redirects the painters' text to stb_raster, the tree's font)
import preview_all, pod_ui, pod_i18n, mod_ipodrows
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'test'))

W, BAR, NAVBAR, LIST_H = 320, 30, pod_ui.NAVBAR_H, pod_ui.CLIENT_H - pod_ui.NAVBAR_H
ART_SIZE = 160   # the previews' source art: the cover thread's file, drawn 1:1


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


def corner_alpha(x, y, r=10):
    """patch/common.c pod_corner_fill: the coverage 0..255 of the area outside a quarter circle, 8 x 8 samples a pixel."""
    c = 2 * 8 * r
    n = sum((2 * (x * 8 + i) + 1 - c) ** 2 + (2 * (y * 8 + j) + 1 - c) ** 2 > c * c for i in range(8) for j in range(8))
    return (n * 255 + 32) // 64


def page(work, title, album, artist, meta, cover, n, scroll=0, bg=None, C=C):
    """The stock albuminfo_page as the release leaves it: the restyled header item (AH_* numbers of
    patch/offsets.inc: cover, title, artist, year line, Play all and Shuffle) over the stock rows. bg (a function of the row
    below the status bar -> (r, g, b)) is the tint mock-up of tools/preview_album_tint.py: every pure black pixel of the page
    takes it, and so do the corner masks (text edges keep their dark blend: approximate)."""
    raw = os.path.join(work, preview_all.RAW)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1pod_cover.bin'), 'rb').read())
    nav = next(w for w in root.walk() if w.name == 'navigationbar_view')
    for w in root.walk():
        if w.name == 'label_title': w.set('text', ''); w.set('name', 'label_title_preview')   # transparent on this page (page theme)
    NAV = C['AH_NAV_H']   # the album page's navbar is shorter than the other pages' (ui/albuminfo_page.bin, rows.json): its buttons are as high
    nav.h = NAV
    for w in nav.children: w.h = NAV
    root.children = [nav]
    LW = 310   # the list_view's scroll_view (a 10 px scroll bar at the right)
    list_h = pod_ui.CLIENT_H - NAV
    sv = Widget('scroll_view', 0, NAV, LW, list_h)

    def line(y, h, text, size, colour, long=False):
        w = Widget('hscroll_label', C['AH_TEXT_X'], y - scroll, C['AH_TEXT_W'], h,
                   [('text', text), ('ellipses', 'true')])
        for k, v in (('font_size', str(size)), ('text_color', colour), ('text_align_h', 'center')): w.set(f'style:normal:{k}', v)
        return w
    hdr = Widget('list_item', 0, -scroll, LW, C['AH_HDR_H'], [('style', 'list_item_notpress_style')])
    sv.children.append(hdr)
    sv.children += [line(C['AH_TITLE_Y'], C['AH_TITLE_H'], album, 22, '#FFFFFF'),
                    line(C['AH_ARTIST_Y'], C['AH_ARTIST_H'], artist, 18, '#AAAAAA'),
                    line(C['AH_META_Y'], C['AH_META_H'], meta, 15, '#9C9C9C')]
    for i in range(n):   # the stock rows, 64 px apart: the number in its own #AAAAAA label (right aligned, ROW_NUM_W column), the title 19 px white
        y = C['AH_HDR_H'] + i * 64 - scroll
        row = Widget('list_item', 0, y, LW, 64, [('style', 'list_item_style')])
        num = Widget('label', 12, 0, C['ROW_NUM_W'], 60, [('text', str(i + 1)), ('sensitive', 'false')])
        for k, v in (('font_size', '19'), ('text_color', '#AAAAAA'), ('text_align_h', 'right')): num.set(f'style:normal:{k}', v)
        tx = 12 + C['ROW_NUM_W'] + 8
        lab = Widget('hscroll_label', tx, 0, LW - 12 - tx, 60,
                     [('style', 'srlabel_leftwhite21_style'), ('text', TRACKS[i % len(TRACKS)]),
                      ('only_parent_focus', 'true'), ('ellipses', 'true')])
        lab.set('style:normal:font_size', '19')   # the page theme's TRACK_PX
        row.children = [num, lab]; sv.children.append(row)
    root.children.append(sv)
    painter = preview_all.MenuPainter(raw)
    im = painter.render(root, 0)
    if bg:
        px = im.load()
        for y in range(BAR, im.height):
            c = bg(y - BAR) + (255,)
            for x in range(W):
                if px[x, y][:3] == (0, 0, 0): px[x, y] = c
    oy = BAR + NAV - scroll
    clip = (0, BAR + NAV, W, BAR + NAV + list_h)
    layer = Image.new('RGBA', im.size)
    ld = ImageDraw.Draw(layer)
    S, R = C['AH_ART'], C['AH_CORNER']
    img = os.path.join(raw, 'images', 'xx')
    if cover is None: cover = Image.open(os.path.join(img, 'albumcover_info.png'))   # no cover: the 160 px placeholder
    box = Image.new('RGBA', (S, S), (0, 0, 0, 255) if not bg else bg(oy + C['AH_ART_Y'] + S // 2 - BAR) + (255,))
    c = cover.convert('RGBA'); box.alpha_composite(c.resize((min(S, c.width),) * 2, Image.LANCZOS) if c.width != S else c,
                                                   ((S - min(S, c.width)) // 2,) * 2)   # rendered at 160 px: drawn 1:1, centred when smaller
    for k, (cx, cy) in (('tl', (0, 0)), ('tr', (S - R, 0)), ('bl', (0, S - R)), ('br', (S - R, S - R))):
        mask = Image.new('RGBA', (R, R))   # what pod_corners paints: the window's colour on that row at the 8 x 8 sampled coverage
        for my in range(R):
            col = bg(oy + C['AH_ART_Y'] + cy + my - BAR) if bg else (0, 0, 0)
            for mx in range(R): mask.putpixel((mx, my), col + (corner_alpha(mx if k[1] == 'l' else R - 1 - mx, my if k[0] == 't' else R - 1 - my),))
        box.alpha_composite(mask, (cx, cy))
    layer.paste(box, (C['AH_ART_X'], oy + C['AH_ART_Y']))
    y = oy + C['AH_BTN_Y']
    disc = Image.open(os.path.join(img, 'ah_shuffle.png')).convert('RGBA')   # drawn centred in its touch rectangle
    layer.alpha_composite(disc, (C['AH_SHUF_X'] + (C['AH_SHUF_W'] - disc.width) // 2, y + (C['AH_BTN_H'] - disc.height) // 2))
    layer.alpha_composite(pill(painter, img, 'Play all'), (C['AH_PLAY_X'], y))
    im.alpha_composite(layer.crop(clip), clip[:2])
    return im


def pill(painter, img, text):
    """The Play all button (AH_PLAY_W x AH_BTN_H touch rectangle) with the AH_PILL_H pill image centred in it and the glyph and text where AWTK puts them for the page style
    (icon_at left, margins, spacer: mod_ipodrows.pill_layout, from widget_calc_icon_text_rect @0x666f04)."""
    w, h = C['AH_PLAY_W'], C['AH_BTN_H']
    out = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    bg = Image.open(os.path.join(img, 'ah_pill.png')).convert('RGBA'); out.alpha_composite(bg, ((w - bg.width) // 2, (h - bg.height) // 2))
    glyph = Image.open(os.path.join(img, 'ah_play.png')).convert('RGBA')
    f, st = painter.font(18), painter.stb(18)
    layout, tw = st.layout(text)
    gx, tx, _ = mod_ipodrows.pill_layout(tw, w, h)
    out.alpha_composite(glyph, (gx, (h - glyph.height) // 2))
    d = ImageDraw.Draw(out); top = (h - 18) // 2
    for ch, pen in layout:
        d.text((tx + pen, top + f.getmetrics()[0]), ch, font=f, fill='#141414', anchor='ls')
    return out


def pills(work, path):
    """The pill in every language (the strip next to the page previews)."""
    raw = os.path.join(work, preview_all.RAW)
    painter = preview_all.MenuPainter(raw); img = os.path.join(raw, 'images', 'xx')
    langs = pod_i18n.LOCALES
    out = Image.new('RGB', (2 * 214 + 20, 12 + len(langs) // 2 * 60 + 60), (0, 0, 0)); d = ImageDraw.Draw(out)
    for i, loc in enumerate(langs):
        x, y = 10 + (i % 2) * 214, 10 + (i // 2) * 60
        p = pill(painter, img, pod_i18n.TEXT['Play all'][loc]); out.paste(p, (x, y), p)
        d.text((x, y + 46), loc, fill=(160, 160, 160))
    out.save(path); print('wrote', path)


COMPOSERS = ['Antonio Vivaldi', 'Claude Debussy', 'Dmitri Shostakovich', 'Johann Sebastian Bach', 'Ludwig van Beethoven',
             'Wolfgang Amadeus Mozart', 'Sergei Rachmaninoff', 'Pyotr Ilyich Tchaikovsky']


def class_page(work, title, names, playing=None):
    """The stock Artists / Genres / Composers page (localclass_page) as the release leaves it: the class placeholder
    (icon_artist / icon_genre / icon_composer) is hidden, the name starts at the 12 px margin and runs to the chevron
    (265 px); the playing row (gold name) has the wave marker before the chevron (name 217 px)."""
    raw = os.path.join(work, preview_all.RAW)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1pod_cover.bin'), 'rb').read())
    nav = next(w for w in root.walk() if w.name == 'navigationbar_view')
    for w in root.walk():
        if w.name == 'label_title': w.set('text', title)
    root.children = [nav]
    LW = 310
    sv = Widget('scroll_view', 0, NAVBAR, LW, LIST_H)
    for i, name in enumerate(names):
        row = Widget('list_item', 0, i * 64, LW, 64, [('style', 'list_item_style')])
        here = i == playing
        w = 217 if here else 265
        lab = Widget('hscroll_label', 12, 0, w, 60, [('style', 'srlabel_item_gold20_style' if here else 'srlabel_leftwhite21_style'),
                                                      ('text', name), ('ellipses', 'true')])
        row.children = [lab]
        if here: row.children.append(Widget('image', 237, 20, 40, 20, [('image', 'np_row_playing'), ('draw_type', 'center')]))
        row.children.append(Widget('image', 285, 0, 13, 60, [('image', 'right_arrow'), ('draw_type', 'icon')]))
        sv.children.append(row)
    root.children.append(sv)
    return preview_all.MenuPainter(raw).render(root, 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work'); ap.add_argument('out')
    a = ap.parse_args()
    long_title = 'The Rise and Fall of Ziggy Stardust and the Spiders from Mars'
    shots = [('an album', page(a.work, 'Cover Flow', 'Kind of Blue', 'Miles Davis', '1959 · 8 tracks', art('sky'), 8)),
             ('a long title', page(a.work, 'Cover Flow', long_title, 'David Bowie with the Spiders from Mars', '1972 · 8 tracks',
                                   art('design'), 8)),
             ('All albums card (placeholder disc)', page(a.work, 'Miles Davis', 'All albums', 'Miles Davis', '24 tracks', None, 8)),
             ('a CJK title', page(a.work, 'Cover Flow', '七里香 (Live) 周杰伦演唱会纪念专辑', '周杰伦 Jay Chou', '2004 · 10 首', art('design'), 8)),
             ('scrolled', page(a.work, 'Cover Flow', 'Kind of Blue', 'Miles Davis', '1959 · 8 tracks', art('sky'), 8, scroll=150)),
             ('Composers (no placeholder icon)', class_page(a.work, 'Composers', COMPOSERS)),
             ('Artists, one playing', class_page(a.work, 'Artists', COMPOSERS, playing=3))]
    pad, top = 12, 20
    out = Image.new('RGB', (len(shots) * (W + pad) + pad, 480 + top + 2 * pad + 16), (40, 40, 40))
    d = ImageDraw.Draw(out)
    for i, (cap, im) in enumerate(shots):
        x = pad + i * (W + pad)
        out.paste(im.convert('RGB'), (x, pad + top)); d.text((x, pad + 4), cap, fill=(230, 230, 230))
    d.text((pad, out.height - 18), 'approximate PIL mock-ups (not AWTK); cover rendered at 160 px by the stock cover thread, drawn 1:1; sample data; no durations (not in the database)',
           fill=(160, 160, 160))
    out.quantize(colors=192).save(a.out, optimize=True); print('wrote', a.out)
    pills(a.work, os.path.splitext(a.out)[0] + '-pill.png')


if __name__ == '__main__': main()
