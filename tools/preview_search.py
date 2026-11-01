#!/usr/bin/env python3
"""Approximate PIL mock-up of the Search page (patch/search.c, docs/modules/search.md): the Apple Music search screen with our keyboard embedded. Not pixel-exact AWTK.

  preview_search.py WORKDIR OUT.png [--lang CODE]

WORKDIR is a built tree (work/mod-release): the font, the status bar art, the glyph images, ui/m1plus_search.bin (the field, the pad and every key's rectangle, colour and label come from it
and from ui/m1plus_keyboard.bin, which the keyboard preview draws) are read from it. The layout numbers are tools/pod_search.py's (the #defines of patch/search.h, which the builder, the
tests and the payload share): the field, the X, the chip row (each chip as wide as its text, scrolled 0), the row geometry, the thumbnails (a stand-in colour: the real ones are cover files
from the cache; round for an artist), the grey line, the chevron. Panels: Top Results with the keyboard up (typing), the Albums chip with the keyboard hidden, the empty state (the page as it
opens), and the Songs chip scrolled with a longer query. Besides the sheet, each panel is written beside OUT as <stem>-<name>.png.
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
import pod_keyboard as PK
import pod_search as PS
import preview_icons as PI
import preview_keyboard as PKV

W, H, SS, BAR = PKV.W, PKV.H, PKV.SS, PKV.BAR
WHITE, GREY = PKV.WHITE, PKV.GREY
D = PS.D


def rgb(c): return PKV.rgb(c)


class Tree:
    def __init__(self, s):
        self.s = s
        self.root = awtk_ui.parse(open(os.path.join(s.tree, PI.RAW, 'ui', 'm1plus_search.bin'), 'rb').read())
        self.field = self.root.find('kb_field')
        self.fill = lambda n, st='normal': rgb(self.root.find(n).get(f'style:{st}:bg_color'))

    def px(self, n, key='font_size'): return int(self.root.find(n).get(f'style:normal:{key}'))


# stand-in data: (kind, title, subtitle, colour). The thumbnails are flat colours; an artist's is round.
TOP = [('artist', 'Taylor Swift', 'Artist', (0x59, 0x4B, 0x4B)),
       ('album', 'The Life of a Showgirl: The Encore', 'Album · Taylor Swift', (0x8A, 0x2B, 0x3B)),
       ('album', 'folklore (deluxe version)', 'Album · Taylor Swift', (0x8E, 0x92, 0x93)),
       ('song', 'Taylor Swift Loves You', 'Song · The Kelleigh Bannen Show', (0x7A, 0x4A, 0x9A)),
       ('song', 'Cardigan', 'Song · Taylor Swift', (0x8E, 0x92, 0x93)),
       ('playlist', 'Taylor Mix', 'Playlist', (0x4A, 0x6A, 0x5A))]
ALBUMS = [('album', n, 'Album · ' + a, c) for n, a, c in (('Kind of Blue', 'Miles Davis', (0x2B, 0x5A, 0x8A)), ('Bitches Brew', 'Miles Davis', (0x8A, 0x6A, 0x2B)), ('Blue Train', 'John Coltrane', (0x2B, 0x7A, 0x9A)),
                                                         ('Blue in Green', 'Bill Evans', (0x4A, 0x4A, 0x6A)), ('Blue Hawaii', 'Elvis Presley', (0x9A, 0x4A, 0x6A)), ('Blue', 'Joni Mitchell', (0x2B, 0x4A, 0x8A)),
                                                         ('Blue Lines', 'Massive Attack', (0x5A, 0x5A, 0x5A)), ('Blue Album', 'Weezer', (0x2B, 0x6A, 0x9A)))]
SONGS = [('song', n, 'Song · ' + a, c) for n, a, c in (('Blue in Green', 'Miles Davis', (0x2B, 0x5A, 0x8A)), ('Blue Monk', 'Thelonious Monk', (0x8A, 0x5A, 0x2B)), ('Blue Train', 'John Coltrane', (0x2B, 0x7A, 0x9A)),
                                                       ('Blue Moon', 'Billie Holiday', (0x6A, 0x4A, 0x6A)), ('Blue Bossa', 'Joe Henderson', (0x4A, 0x7A, 0x5A)), ('Blue Suede Shoes', 'Elvis Presley', (0x9A, 0x4A, 0x4A)))]


def chip_texts(s): return [s.shown_key(k) if hasattr(s, 'shown_key') else k for k in PS.CHIPS]


def draw_top(s, t, im, text, hint, caret, selected_chip, sx=0):
    """The page's top: the field (magnifier, text or hint, clear disc, caret), the round X, the chips, the line."""
    f = t.field
    mag, clear, caret_n = t.root.find('kb_mag'), t.root.find('kb_clear'), t.root.find('kb_caret')
    def paint(d, k):
        d.rounded_rectangle(k(f.x, BAR + f.y, f.x + f.w, BAR + f.y + f.h), radius=D['SE_FIELD_R'] * SS, fill=t.fill('kb_field') + (255,))
    im.alpha_composite(PKV.layer(paint))
    im.alpha_composite(s.img(mag.get('image')), (f.x + mag.x + (mag.w - 16) // 2, BAR + f.y + mag.y))
    tx, ty = f.x + D['SE_TEXT_X'], BAR + f.y + f.h / 2
    px = PS.FIELD_PX
    if text:
        shown, w = text, s.font.width(text, px)
        while w > D['SE_TEXT_W'] and len(shown) > 1:
            shown = '…' + shown[2:] if shown[0] != '…' else '…' + shown[2:]
            w = s.font.width(shown, px)
        s.text(im, tx, ty, shown, px, rgb(t.root.find('kb_text').get('style:normal:text_color')))
        c = s.img(clear.get('style:normal:icon')); im.alpha_composite(c, (f.x + clear.x + (clear.w - c.width) // 2, int(ty - c.height / 2)))
        cx = tx + w + 1
    else:
        s.text(im, tx, ty, hint, px, rgb(t.root.find('kb_hint').get('style:normal:text_color')))
        cx = tx
    if caret:
        ImageDraw.Draw(im).rectangle((cx, BAR + f.y + caret_n.y, cx + caret_n.w - 1, BAR + f.y + caret_n.y + caret_n.h - 1), fill=rgb(caret_n.get('style:normal:bg_color')))
    close = t.root.find('btn_return')
    g = s.img(close.get('style:normal:icon'))
    im.alpha_composite(g, (close.x + (close.w - g.width) // 2, BAR + close.y + (close.h - g.height) // 2))
    # the chips
    texts = list(PS.CHIPS)
    lay = PS.chip_layout([s.font.width(x, D['SE_CHIP_PX']) for x in texts])
    for i, (x, w) in enumerate(lay):
        x -= sx   # the row scrolled sx px
        if x >= W or x + w <= 0: continue
        if i == selected_chip:
            def pill(d, k, x=x, w=w):
                d.rounded_rectangle(k(x, BAR + D['SE_CHIPS_Y'] + D['SE_CHIP_Y'], x + w, BAR + D['SE_CHIPS_Y'] + D['SE_CHIP_Y'] + D['SE_CHIP_H']), radius=D['SE_CHIP_R'] * SS, fill=rgb(PS.CHIP_ON_RGB) + (255,))
            im.alpha_composite(PKV.layer(pill))
        ink = rgb(PS.CHIP_ON_INK) if i == selected_chip else rgb(PS.CHIP_INK)
        tw = s.font.width(texts[i], D['SE_CHIP_PX'])
        s.text(im, x + (w - tw) / 2, BAR + D['SE_CHIPS_Y'] + D['SE_CHIP_Y'] + D['SE_CHIP_H'] / 2, texts[i], D['SE_CHIP_PX'], ink)
    def line(d, k): d.rectangle(k(0, BAR + D['SE_SEP_Y'], W, BAR + D['SE_SEP_Y'] + 1), fill=rgb(PS.SEP_RGB) + (255,))
    im.alpha_composite(PKV.layer(line))


def draw_rows(s, im, rows, bottom):
    """The results rows from the list's top, cut at window row `bottom` (what the keyboard leaves)."""
    top = BAR + D['SE_LIST_Y']
    def paint(d, k):
        for i, (kind, title, sub, col) in enumerate(rows):
            y = top + i * D['SE_ROW_H']
            if y + D['SE_ROW_H'] > BAR + bottom: break
            box = k(D['SE_ART_X'], y + D['SE_ART_Y'], D['SE_ART_X'] + D['SE_ART'], y + D['SE_ART_Y'] + D['SE_ART'])
            if kind == 'artist': d.ellipse(box, fill=col)
            else: d.rounded_rectangle(box, radius=D['SE_ART_R'] * SS, fill=col)
            if kind != 'song':
                cx, cy = D['SE_CHEV_X'] + 3, y + D['SE_ROW_H'] / 2
                d.line(k(cx, cy - 7, cx + 6, cy, cx, cy + 7), fill=rgb(PS.CHEV_RGB) + (255,), width=int(2 * SS), joint='curve')
            d.line(k(D['SE_TEXT_LEFT'], y + D['SE_ROW_H'] - 1, D['SE_SEP_END'], y + D['SE_ROW_H'] - 1), fill=(0x22, 0x22, 0x22, 255), width=SS)
    im.alpha_composite(PKV.layer(paint))
    for i, (kind, title, sub, col) in enumerate(rows):
        y = top + i * D['SE_ROW_H']
        if y + D['SE_ROW_H'] > BAR + bottom: break
        end = D['SE_END_PLAIN'] if kind == 'song' else D['SE_END_CHEV']
        s.text(im, D['SE_TEXT_LEFT'], y + O_TITLE_Y + 12, s.clip(title, 21, end - D['SE_TEXT_LEFT']), 21)
        s.text(im, D['SE_TEXT_LEFT'], y + O_SUB_Y + 10, s.clip(sub, 18, end - D['SE_TEXT_LEFT']), 18, rgb(PS.SUB_RGB))


O_TITLE_Y, O_SUB_Y = 7, 33   # offsets.inc LIST_TITLE_Y, LIST_SUB_Y
O_TITLE_H, O_SUB_H = 24, 20  # LIST_TITLE_H, LIST_SUB_H
RECENT = ('taylor swift', 'blue in green', 'miles davis', '周杰伦', 'a rather long search that does not fit its room')


def draw_recent(s, im, recents, bottom):
    """The empty state with a history: the header, then a row each (the query, an x), a hairline under every row (patch/search.c se_paint_recent)."""
    top = BAR + D['SE_LIST_Y']
    room = D['SE_REC_TEXT_END'] - D['SE_REC_TEXT_X']
    def paint(d, k):
        for i in range(len(recents)):
            y = top + D['SE_REC_HEAD_H'] + i * D['SE_REC_ROW_H']
            if y + D['SE_REC_ROW_H'] > BAR + bottom: break
            cx, cy, r = D['SE_REC_X_C'], y + D['SE_REC_ROW_H'] / 2, 4.5
            for a, b in (((-r, -r), (r, r)), ((r, -r), (-r, r))):
                d.line(k(cx + a[0], cy + a[1], cx + b[0], cy + b[1]), fill=rgb(PS.CHEV_RGB) + (255,), width=int(1.75 * SS))
            d.line(k(D['SE_REC_TEXT_X'], y + D['SE_REC_ROW_H'] - 1, D['SE_SEP_END'], y + D['SE_REC_ROW_H'] - 1), fill=(0x22, 0x22, 0x22, 255), width=SS)
    im.alpha_composite(PKV.layer(paint))
    s.text(im, D['SE_REC_TEXT_X'], top + D['SE_REC_HEAD_H'] - O_SUB_H - 6 + O_SUB_H / 2, s.clip(s.strings.get('Recently Searched', 'Recently Searched'), 18, room), 18, rgb(PS.SUB_RGB))
    for i, q in enumerate(recents):
        y = top + D['SE_REC_HEAD_H'] + i * D['SE_REC_ROW_H']
        if y + D['SE_REC_ROW_H'] > BAR + bottom: break
        s.text(im, D['SE_REC_TEXT_X'], y + (D['SE_REC_ROW_H'] - O_TITLE_H) / 2 + O_TITLE_H / 2, s.clip(q, 21, room), 21)


def screen(s, t, kb, text, rows, chip, keyboard=True, hint='Search', page='abc', held=None, sx=0, recents=()):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    PI.status_bar(s, im)
    bottom = D['SE_LIST_Y'] + D['SE_LIST_H'] if not keyboard else 450 - PK.KB_H
    draw_rows(s, im, rows, bottom)
    if recents: draw_recent(s, im, recents, bottom)
    draw_top(s, t, im, text, hint, keyboard, chip, sx)
    if keyboard: PKV.keyboard(kb, im, page, held)
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir'); ap.add_argument('out'); ap.add_argument('--lang', default='en_US')
    a = ap.parse_args()
    s = PI.Side(a.workdir, True, a.lang)
    t, kb = Tree(s), PKV.Page(s)
    panels = [('top', 'Top Results, keyboard up (typing "taylor")', screen(s, t, kb, 'taylor', TOP, 0, True, page='abc', held='r')),
              ('albums', 'Albums chip, keyboard hidden', screen(s, t, kb, 'blue', ALBUMS, 2, False)),
              ('empty', 'Empty state: the page as it opens', screen(s, t, kb, '', [], 0, True, page='ABC')),
              ('recent', 'Empty state with recent searches (keyboard hidden)', screen(s, t, kb, '', [], 0, False, recents=RECENT)),
              ('songs', 'Songs chip (the chip row scrolled)', screen(s, t, kb, 'blue', SONGS, 3, False, sx=120))]
    base, ext = os.path.splitext(a.out)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    pad, lab = 12, 20
    sheet = Image.new('RGB', (len(panels) * (W + pad) + pad, H + lab + 2 * pad), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sheet)
    for i, (name, title, im) in enumerate(panels):
        x = pad + i * (W + pad)
        d.text((x, pad), title, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, pad + lab))
        PI.save_compact(im.convert('RGB'), f'{base}-{name}{ext}', colors=256)
        print('wrote', f'{base}-{name}{ext}')
    PI.save_compact(sheet, a.out, colors=256)
    print('wrote', a.out, sheet.size)


if __name__ == '__main__': main()
