#!/usr/bin/env python3
"""Mock-up of the tinted album page (patch/albuminfo.c, docs/modules/album-page.md): four real covers (red, blue, grey, bright),
then the All albums card and a page with no cover (the placeholder disc), which stay plain black.

The window colour is the tone of the cover's average colour (mod_nowplaying.tone, the one the payload computes) under the black
gradient image ah_tint (mod_icons.ah_tint_alpha, alpha 64 at the first row of the window to 200 at the end of the header, held below:
the deep tint the transparent track rows show). Everything else is the approximate PIL page of tools/preview_album.py, its pure black
replaced by that colour per row (so text edges keep a dark blend: approximate), the corners painted as pod_corners does; the rows' hairlines
and the pressed row's band are redrawn as the album page's translucent white (rows_look). Every page is shown scrolled 150 px (the header's
lower part and four rows, the second pressed); the status bar sheet (BAR.png) has its own page.

Usage: uv run python -I tools/preview_album_tint.py WORKDIR OUT.png [BAR.png]
With BAR.png also the status bar sheet: the bar in the page's top-edge colour over the red and bright pages, at rest and scrolled.
"""
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preview_album as PA
import mod_nowplaying as NP
import mod_icons
import mod_ipodrows

ART = PA.ART_SIZE
COVERS = [('red', (190, 50, 55)), ('blue', (40, 80, 190)), ('grey', (120, 120, 124)), ('bright', (240, 225, 150))]


def cover(rgb):
    """A 160 px cover of that general colour: a vertical shade, a ring and a dark base line, so it is not a flat swatch."""
    im = Image.new('RGB', (ART, ART)); d = ImageDraw.Draw(im)
    for y in range(ART):
        k = 1.1 - 0.5 * y / ART
        d.line([(0, y), (ART, y)], fill=tuple(min(255, int(v * k)) for v in rgb))
    d.ellipse([30, 24, 130, 124], outline=tuple(min(255, v + 70) for v in rgb), width=5)
    d.rectangle([20, 138, 140, 146], fill=tuple(v // 4 for v in rgb))
    return im


def average(im):
    return im.resize((1, 1), Image.BOX).getpixel((0, 0))


def bar_color(tone):
    """patch/common.c pod_bar_color of the page's window row 0 (the tone under the overlay's first alpha): darkened until the
    status bar's white glyphs keep 4.5:1. Returns (the bar's colour, the page's row 0 colour)."""
    row0 = tuple(v * (255 - mod_icons.ah_tint_alpha(0)) // 255 for v in tone); r, g, b = row0
    while 2126 * r * r + 7152 * g * g + 722 * b * b > PA.C['NP_BAR_LUM_MAX']: r, g, b = r * 15 >> 4, g * 15 >> 4, b * 15 >> 4
    return (r, g, b), row0


def bar_sheet(work, out):
    """The status bar over the tinted page, red and bright covers, list at rest and scrolled 130 px: the bar is the window's row 0
    (fixed: the overlay and the navbar do not scroll), so the seam is the same in both. Prints the largest channel step."""
    panels, steps = [], []
    for name, rgb in COVERS:
        if name not in ('red', 'bright'): continue
        c = cover(rgb); tone = NP.tone(*average(c)); bar, row0 = bar_color(tone)
        bg = lambda y, t=tone: tuple(v * (255 - mod_icons.ah_tint_alpha(y)) // 255 for v in t)
        step = max(a - b for a, b in zip(row0, bar)); steps.append((name, row0, bar, step))
        for scroll in (0, 130):
            im = PA.page(work, '', 'Kind of Blue', 'Miles Davis', '1959 \xb7 8 tracks', c, 8, scroll=scroll, bg=bg).convert('RGB')
            ImageDraw.Draw(im).rectangle([0, 0, 319, PA.BAR - 1], fill=bar)
            panels.append((f'{name}, list scrolled {scroll}: bar #%02X%02X%02X, row 0 #%02X%02X%02X' % (bar + row0), im))
    W, H, pad, top = 320, 480, 12, 20
    sheet = Image.new('RGB', (len(panels) * (W + pad) + pad, H + top + 2 * pad), (40, 40, 40)); d = ImageDraw.Draw(sheet)
    for i, (cap, im) in enumerate(panels):
        x = pad + i * (W + pad); d.text((x, pad + 2), cap, fill=(230, 230, 230), font=None); sheet.paste(im, (x, pad + top))
    sheet.save(out); print('wrote', out)
    for name, row0, bar, step in steps: print(f'  {name}: page row 0 {row0}, bar {bar}, largest channel step {step} levels')


def rows_look(im, bg, scroll, pressed, n=8):
    """The track rows as the album page's own list_item_style draws them (mod_ipodrows ROW_*): transparent, a 1 px bottom hairline in
    ROW_HAIR (white at 0x22/255 over what is behind), the row `pressed` also lightened by ROW_PRESSED (0x33/255 white under its text).
    PA.page painted the stock opaque rows with the window colour replacing their black; this redraws the hairlines and the band."""
    px = im.convert('RGB'); p = px.load(); a_h, a_p = int(mod_ipodrows.ROW_HAIR[7:9], 16), int(mod_ipodrows.ROW_PRESSED[7:9], 16)
    top = PA.BAR + PA.C['AH_HDR_H'] - scroll   # the list starts at the window's top
    for i in range(n):
        y0, y1 = top + i * 64, top + i * 64 + 63
        for y in range(max(y0, PA.BAR), min(y1 + 1, px.height)):
            for x in range(310):
                if i == pressed and y < y1: p[x, y] = tuple(v + (255 - v) * a_p // 255 for v in p[x, y])
                if y == y1: p[x, y] = tuple(v + (255 - v) * a_h // 255 for v in bg(y - PA.BAR))
    return px


def split_sheet(work, out):
    """The floating controls (docs/modules/album-page.md) over the tinted page: Back's glass disc and the capsule, at rest and with the track
    rows scrolled under them (no dissolve: the glass sits over sharp rows), on a red, a blue and a bright cover and on a black page."""
    panels = []
    for name, rgb, scroll, kind, pressed in (('red', COVERS[0][1], 0, 'back only', ()), ('red', COVERS[0][1], 0, 'two', ()), ('red', COVERS[0][1], 100, 'two', ('ah_nav_npa',)),
                                             ('blue', COVERS[1][1], 0, 'three', ()), ('blue', COVERS[1][1], 230, 'three', ('ah_nav_multi',)),
                                             ('bright', COVERS[3][1], 100, 'select mode', ())):
        c = cover(rgb); tone = NP.tone(*average(c))
        bg = lambda y, t=tone: tuple(v * (255 - mod_icons.ah_tint_alpha(y)) // 255 for v in t)
        im = rows_look(PA.page(work, '', 'Kind of Blue', 'Miles Davis', '1959 \xb7 8 tracks', c, 8, scroll=scroll, bg=bg, controls=False), bg, scroll, 1)
        im = im.convert('RGBA'); PA.controls_over(im, PA_IMG(work), kind, pressed)
        panels.append((f'{name}, {kind}' + (f', scrolled {scroll}' if scroll else ', at rest') + (', pressed piece' if pressed else ''), im))
    black = lambda y: (0, 0, 0)
    im = rows_look(PA.page(work, '', 'Kind of Blue', 'Miles Davis', '1959 \xb7 8 tracks', None, 8, scroll=100, controls=False), black, 100, 1).convert('RGBA')
    PA.controls_over(im, PA_IMG(work), 'three'); panels.append(('no cover (black), three, scrolled 100', im))
    W, H, pad, top = 320, 480, 12, 20
    sheet = Image.new('RGB', (len(panels) * (W + pad) + pad, H + top + 2 * pad), (40, 40, 40)); d = ImageDraw.Draw(sheet)
    for i, (cap, im) in enumerate(panels):
        x = pad + i * (W + pad); d.text((x, pad + 2), cap, fill=(230, 230, 230)); sheet.paste(im.convert('RGB'), (x, pad + top))
    sheet.save(out); print('wrote', out)


def PA_IMG(work):
    import preview_layout
    return os.path.join(work, preview_layout.RAW, 'images', 'xx')


def main():
    if len(sys.argv) not in (3, 4): sys.exit(__doc__)
    work, out = sys.argv[1:3]
    split_sheet(work, os.path.join(os.path.dirname(os.path.abspath(out)), 'album-split.png'))
    if len(sys.argv) == 4: bar_sheet(work, sys.argv[3])
    panels = []
    SCROLL = 150   # the header's lower part and four track rows, the second one pressed
    for name, rgb in COVERS:
        c = cover(rgb); tone = NP.tone(*average(c))
        bg = lambda y, t=tone: tuple(v * (255 - mod_icons.ah_tint_alpha(y)) // 255 for v in t)
        im = PA.page(work, '', 'Kind of Blue', 'Miles Davis', '1959 \xb7 8 tracks', c, 8, scroll=SCROLL, bg=bg)
        panels.append((f'{name}, tone #%02X%02X%02X, rows on the deep tint' % tone, rows_look(im, bg, SCROLL, 1)))
    c = cover(COVERS[3][1]); tone = NP.tone(*average(c))
    bg = lambda y, t=tone: tuple(v * (255 - mod_icons.ah_tint_alpha(y)) // 255 for v in t)
    panels.append(('bright, at rest', PA.page(work, '', 'Kind of Blue', 'Miles Davis', '1959 \xb7 8 tracks', c, 8, bg=bg)))
    black = lambda y: (0, 0, 0)
    im = PA.page(work, '', 'All albums', 'Miles Davis', '24 tracks', None, 8, scroll=SCROLL)
    panels.append(('All albums card: black rows', rows_look(im, black, SCROLL, 1)))
    im = PA.page(work, '', 'Kind of Blue', 'Miles Davis', '1959 \xb7 8 tracks', None, 8, scroll=SCROLL)
    panels.append(('no cover (placeholder): black rows', rows_look(im, black, SCROLL, 1)))
    W, H, pad, top = 320, 480, 12, 20
    sheet = Image.new('RGB', (len(panels) * (W + pad) + pad, H + top + 2 * pad), (40, 40, 40)); d = ImageDraw.Draw(sheet)
    for i, (cap, im) in enumerate(panels):
        x = pad + i * (W + pad)
        d.text((x, pad + 2), cap, fill=(230, 230, 230)); sheet.paste(im.convert('RGB'), (x, pad + top))
    sheet.save(out); print('wrote', out)


if __name__ == '__main__': main()
