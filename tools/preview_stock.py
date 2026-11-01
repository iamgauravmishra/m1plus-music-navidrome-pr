#!/usr/bin/env python3
"""out/preview/stock-pages.png: PIL mock-up of the stock pages the release restyles (docs/ui.md),
drawn from one finished tree. Approximate, not AWTK; sample data.

  Albums (stock list)                              the stock Albums rows (their album page is our own, docs/modules/album-page.md)
  Cover Flow on an artist                          the All albums card opens our Songs page on the artist's songs
  a playlist's songs                              the Songs page (allmusic_page) with the q2-pod rows
  the queue (Now Playing list)                     playerjumpinfo_page: the playing row has the wave marker at the right end

Usage: uv run python -I tools/preview_stock.py WORKDIR OUT.png
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preview_font   # noqa: F401  (redirects the painters' text to stb_raster, the tree's font)
import preview_cover as PC
import preview_lists as PL
from preview_lockscreen import Painter

W, H, BAR = PL.W, PL.H, PL.BAR
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART_SIZE = 160   # the sample covers' size
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


def art(kind):
    """A sample cover: the wallpaper's centre, a two-tone design, or the placeholder disc."""
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


def albums_list(p, s):
    """The stock Albums page: 64 px list_items, a 52 px cover at (4,4), title and artist from x 60."""
    pg = PL.Page(p, s); pg.navbar('Albums')
    for i, (album, artist, kind) in enumerate(ALBUMS):
        y = BAR + 50 + i * 64
        pg.rect(0, y, 310, 60, s.color('list_item', 'list_item_style', 'bg_color', 'pressed' if i == 0 else 'normal'))
        pg.rect(0, y + 60, 310, 1, '#222222')
        pg.im.paste(art(kind).resize((52, 52), Image.LANCZOS).convert('RGBA'), (4, y + 4))
        pg.label(album, 60, y + 7, 238, 24, 'hscroll_label', 'srlabel_item_white_style')
        pg.label(artist, 60, y + 33, 238, 20, 'hscroll_label', 'srlabel_item_gray18_style')
        pg.icon(s.str('button', 'btn_rightarrow_style', 'icon'), 285, y, 13, 60)
    return pg.im


def track_rows(pg, rows, playing, pressed, hide):
    """The track rows of the Songs-family pages and the queue: every row shows the track's file-format disc (icon_flac:
    the same picture for a library in one format) and the playing row the red disc; with `hide` (patch/rows.c
    rows_track_icon) no row has a disc: every title starts at the 12 px margin, and the playing row has the wave marker
    (np_row_playing, 40 px widget at 258..298) after its text, which is 238 px wide."""
    for i, (title, artist) in enumerate(rows):
        y = BAR + 50 + i * 64
        pg.table_row(y, 60, pressed=(i == pressed))
        disc = i == playing
        if not hide: pg.icon('icon_playing' if disc else 'icon_flac', 12, y, 40, 60)
        x = 12 if hide else 60
        w = 238 if hide and disc else 298 - x
        if hide and disc: pg.icon('np_row_playing', 258, y, 40, 60)
        pg.label(title, x, y + 7, w, 24, 'hscroll_label', 'srlabel_item_white_style')
        pg.label(artist, x, y + 33, w, 20, 'hscroll_label', 'srlabel_item_gray18_style')


def playlist_detail(p, s, hide=True):
    """A playlist's songs: the Songs page (allmusic_page, class 0xff13): 64 px rows, title and artist; the stock page
    has no header and no Play all."""
    pg = PL.Page(p, s); pg.navbar('Road Trip')
    track_rows(pg, [(title, artist) for _, title, artist in SONGS], 2, 4, hide)
    return pg.im


def queue(p, s, hide=True):
    """The queue (Now Playing list, playerjumpinfo_page): the navbar title the page builds in
    srlabel_leftwhite22_style (20 px in this page's theme), the playing row's wave marker."""
    pg = PL.Page(p, s); pg.navbar('Kind of Blue', search=False)
    track_rows(pg, QUEUE, 2, 5, hide)
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
              ('2. Cover Flow on Miles Davis: tap the card', PC.page(a.work, 'All albums', 'Miles Davis', 'Miles Davis', scoped)),
              ('3. a playlist (Songs page, q2-pod rows)', playlist_detail(p, st('allmusic_page'))),
              ('4. the queue (Now Playing list)', queue(p, st('playerjumpinfo_page')))]
    pad, top = 12, 20
    cols = 2
    out = Image.new('RGB', (cols * (W + pad) + pad, 2 * (H + top + pad) + pad + 16), (40, 40, 40))
    d = ImageDraw.Draw(out)
    for i, (cap, im) in enumerate(panels):
        x, y = pad + (i % cols) * (W + pad), pad + (i // cols) * (H + top + pad)
        assert im.size == (W, H), (cap, im.size)
        out.paste(im.convert('RGB'), (x, y + top)); d.text((x, y + 4), cap, fill=(230, 230, 230))
    d.text((pad, out.height - 16), 'approximate PIL mock-ups (not AWTK); sample data', fill=(160, 160, 160))
    out.quantize(colors=192).save(a.out, optimize=True); print('wrote', a.out, out.size)


if __name__ == '__main__': main()
