#!/usr/bin/env python3
"""out/preview/stock-pages.png: PIL mock-up of the stock pages the release restyles (docs/ui.md),
drawn from one finished tree. Approximate, not AWTK; sample data.

  Albums (stock list) -> the album page            the stock Albums rows, then albuminfo_page
  Cover Flow on an artist -> the same album page   the All albums card opens the same stock page
  a playlist's songs                               the Songs page (allmusic_page) with the q2-pod rows
  the queue (Now Playing list)                     playerjumpinfo_page: the playing row carries the red disc

Usage: venv/bin/python -I tools/preview_stock.py WORKDIR OUT.png
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preview_font   # noqa: F401  (redirects the painters' text to stb_raster, the tree's font)
import preview_album as PA
import preview_cover as PC
import preview_lists as PL
from preview_lockscreen import Painter

W, H, BAR = PL.W, PL.H, PL.BAR
ALBUMS = [('Kind of Blue', 'Miles Davis', 'sky'), ('Bitches Brew', 'Miles Davis', 'design'), ('Blue Train', 'John Coltrane', 'disc'),
          ('Time Out', 'The Dave Brubeck Quartet', 'sky'), ('Mingus Ah Um', 'Charles Mingus', 'design'),
          ('Head Hunters', 'Herbie Hancock', 'disc'), ('Take Five', 'Paul Desmond', 'sky')]
SONGS = [('Kind of Blue', 'So What', 'Miles Davis'), ('Time Out', 'Take Five', 'The Dave Brubeck Quartet'),
         ('Blue Train', 'Blue Train', 'John Coltrane'), ('Mingus Ah Um', 'Goodbye Pork Pie Hat', 'Charles Mingus'),
         ('Head Hunters', 'Chameleon', 'Herbie Hancock'), ('Kind of Blue', 'Blue in Green', 'Miles Davis'),
         ('Bitches Brew', 'Pharaoh\'s Dance', 'Miles Davis')]
QUEUE = [('So What', 'Miles Davis'), ('Freddie Freeloader', 'Miles Davis'), ('Blue in Green', 'Miles Davis'),
         ('All Blues', 'Miles Davis'), ('Flamenco Sketches', 'Miles Davis'), ('So What (Alternate Take)', 'Miles Davis'),
         ('Freddie Freeloader (Alt.)', 'Miles Davis')]


def albums_list(p, s):
    """The stock Albums page: 64 px list_items, a 52 px cover at (4,4), title and artist from x 60."""
    pg = PL.Page(p, s); pg.navbar('Albums')
    for i, (album, artist, kind) in enumerate(ALBUMS):
        y = BAR + 50 + i * 64
        pg.rect(0, y, 310, 60, s.color('list_item', 'list_item_style', 'bg_color', 'pressed' if i == 0 else 'normal'))
        pg.rect(0, y + 60, 310, 1, '#222222')
        pg.im.paste(PA.art(kind).resize((52, 52), Image.LANCZOS).convert('RGBA'), (4, y + 4))
        pg.label(album, 60, y + 7, 238, 24, 'hscroll_label', 'srlabel_item_white_style')
        pg.label(artist, 60, y + 33, 238, 20, 'hscroll_label', 'srlabel_item_gray18_style')
        pg.icon(s.str('button', 'btn_rightarrow_style', 'icon'), 285, y, 13, 60)
    return pg.im


def playlist_detail(p, s):
    """A playlist's songs: the Songs page (allmusic_page, class 0xff13): 64 px rows, a 40 px icon,
    title and artist; the stock page has no header and no Play all."""
    pg = PL.Page(p, s); pg.navbar('Road Trip')
    for i, (album, title, artist) in enumerate(SONGS):
        y = BAR + 50 + i * 64
        pg.table_row(y, 60, pressed=(i == 4))
        pg.icon('albumcover_s', 12, y, 40, 60)
        pg.label(title, 60, y + 7, 238, 24, 'hscroll_label', 'srlabel_item_white_style')
        pg.label(artist, 60, y + 33, 238, 20, 'hscroll_label', 'srlabel_item_gray18_style')
    return pg.im


def queue(p, s):
    """The queue (Now Playing list, playerjumpinfo_page): the navbar title the page builds in
    srlabel_leftwhite22_style (20 px in this page's theme), the playing row's red disc."""
    pg = PL.Page(p, s); pg.navbar('Kind of Blue', search=False)
    for i, (title, artist) in enumerate(QUEUE):
        y = BAR + 50 + i * 64
        pg.table_row(y, 60, pressed=(i == 5))
        pg.icon('icon_playing' if i == 2 else 'albumcover_s', 12, y, 40, 60)
        pg.label(title, 60, y + 7, 238, 24, 'hscroll_label', 'srlabel_item_white_style')
        pg.label(artist, 60, y + 33, 238, 20, 'hscroll_label', 'srlabel_item_gray18_style')
    return pg.im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work'); ap.add_argument('out')
    a = ap.parse_args()
    raw = os.path.join(a.work, 'rootfs/release/assets/default/raw')
    p = Painter(raw, False)
    st = lambda page: PL.Styles(a.work, 'default', page)
    shelf = [((200, 60, 60), 0), ((60, 160, 200), 0), ((230, 190, 70), 0), ((90, 90, 220), 1),
             ((120, 200, 120), 0), ((200, 120, 200), 0), ((210, 140, 60), 0)]
    scoped = [None] * 3 + shelf[3:]
    panels = [('1. Albums (stock list): tap Kind of Blue', albums_list(p, st('album_page'))),
              ('2. the album page', PA.page(a.work, 'Albums', 'Kind of Blue', 'Miles Davis', '1959 · 8 tracks', PA.art('sky'), 8)),
              ('3. Cover Flow on Miles Davis: tap the card', PC.page(a.work, 'All albums', 'Miles Davis', 'Miles Davis', scoped)),
              ('4. the same album page (All albums)', PA.page(a.work, 'Albums', 'All albums', 'Miles Davis', '24 tracks', PA.art('disc'), 8)),
              ('5. a playlist (Songs page, q2-pod rows)', playlist_detail(p, st('allmusic_page'))),
              ('6. the queue (Now Playing list)', queue(p, st('playerjumpinfo_page')))]
    pad, top = 12, 20
    cols = 3
    out = Image.new('RGB', (cols * (W + pad) + pad, 2 * (H + top + pad) + pad + 16), (40, 40, 40))
    d = ImageDraw.Draw(out)
    for i, (cap, im) in enumerate(panels):
        x, y = pad + (i % cols) * (W + pad), pad + (i // cols) * (H + top + pad)
        assert im.size == (W, H), (cap, im.size)
        out.paste(im.convert('RGB'), (x, y + top)); d.text((x, y + 4), cap, fill=(230, 230, 230))
    d.text((pad, out.height - 16), 'approximate PIL mock-ups (not AWTK); the album page is one stock page for the Albums list, '
           'Cover Flow, Artists and the All albums card; sample data', fill=(160, 160, 160))
    out.quantize(colors=192).save(a.out, optimize=True); print('wrote', a.out, out.size)


if __name__ == '__main__': main()
