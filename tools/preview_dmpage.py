#!/usr/bin/env python3
"""Previews of the Daily Mix page (docs/modules/dailymix.md "The page"): the page as patch/dailymix.c paints it, at the top and scrolled into the songs, three palettes (warm,
cool, grey), the language with the widest lines, songs without a cover, a pressed row. Approximate, not AWTK; sample data; every number is tools/pod_dailymix.py DP_* and
patch/offsets.inc LIST_*, the art and the tint the model's (pod_dailymix.page_art, which the test compares with the compiled code pixel for pixel).

  uv run python -I tools/preview_dmpage.py WORKDIR [OUTDIR]       (WORKDIR: the built release tree, work/mod-release; default OUTDIR out/dailymix-page)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image, ImageDraw
import preview, preview_icons as PI, preview_dailymix as PD, pod_dailymix as D, pod_i18n

O = PI.offsets()
SONGS = [('Everything In Its Right Place', 'Radiohead', (190, 90, 120), True), ('Hyperballad', 'Björk', (70, 110, 190), False), ('Sour Times', 'Portishead', (150, 120, 70), False),
         ('Alone in Kyoto', 'Air', None, True), ('Teardrop', 'Massive Attack', (60, 140, 150), False), ('Windowlicker', 'Aphex Twin', (110, 90, 130), False),
         ('Rimsky-Korsakov: Scheherazade, Op. 35: III. The Young Prince and the Young Princess', 'Saint Petersburg Philharmonic Orchestra', (200, 150, 60), False),
         ('Kid A', 'Radiohead', (60, 140, 150), True), ('Roads', 'Portishead', (150, 120, 70), False), ('Possibly Maybe', 'Björk', (70, 110, 190), False)]
PALS = {'warm': [(230, 120, 40), (200, 60, 50), (240, 190, 80)], 'cool': [(40, 90, 200), (60, 170, 190), (110, 80, 200)], 'grey': [(128, 128, 128), (60, 60, 60), (200, 200, 200)]}
SEED = 20261028


def mix(c, a):
    """colour c with alpha a (0..255) over nothing: an RGBA white fill as the page blends it."""
    return (255, 255, 255, a)


def page_image(s, tones, seed=SEED, loc='en_US', off=0, songs=SONGS, pressed=None, updated='Updated today', covers=True):
    """The window (320 x 450) under the 30 px status bar, scrolled `off` px, as a 320 x 480 image."""
    rows, tint = D.page_art(tones, seed)
    grey, acc = D.page_colours(tint)
    n = len(songs)
    h = D.DP_ROWS_Y + n * O['LIST_ROW_H'] + D.DP_BOTTOM
    c = Image.new('RGBA', (D.DP_W, max(h, D.DP_VIEW_H)), tint + (255,))
    c.paste(D.to_image(rows), (0, 0))
    tr = lambda k: D.tr(loc, k) if k in D.TEXT else pod_i18n.TEXT[k][loc]
    def line(text, y, px, rgb, box_h=None, cx=160, room=D.DP_TEXT_W):
        text = s.clip(text, px, room)
        s.text(c, cx, y + (box_h or px) / 2, text, px, rgb, anchor='m')
    line(tr('Daily Mix'), D.DP_TITLE_Y, D.DP_TITLE_PX, (255, 255, 255))
    line(tr('Made for You'), D.DP_SUB_Y, D.DP_SUB_PX, (255, 255, 255))
    line(updated, D.DP_UPD_Y, D.DP_UPD_PX, acc)
    # the buttons: the album page's disc and the white pill with its dark glyph and text as a centred pair
    disc = s.img('ah_shuffle'); c.alpha_composite(disc, (D.DP_SHUF_X + (D.DP_SHUF_W - disc.width) // 2, D.DP_BTN_Y + (D.DP_BTN_H - disc.height) // 2))
    add = s.img('dp_add'); c.alpha_composite(add, (D.DP_ADD_X + (D.DP_ADD_W - add.width) // 2, D.DP_BTN_Y + (D.DP_BTN_H - add.height) // 2))   # saves the mix as a playlist
    pill = s.img('dp_pill'); c.alpha_composite(pill, (D.DP_PLAY_X, D.DP_BTN_Y + (D.DP_BTN_H - D.DP_PILL_H) // 2))
    word = tr('Play')
    tw = min(s.font.width(word, 18), D.DP_PLAY_W - 2 * (D.DP_PILL_GLYPH + D.DP_PILL_GAP))
    gx = D.DP_PLAY_X + (D.DP_PLAY_W - (D.DP_PILL_GLYPH + D.DP_PILL_GAP + tw)) // 2
    c.alpha_composite(s.img('dp_play'), (gx, D.DP_BTN_Y + (D.DP_BTN_H - D.DP_PILL_GLYPH) // 2))
    s.text(c, gx + D.DP_PILL_GLYPH + D.DP_PILL_GAP, D.DP_BTN_Y + D.DP_BTN_H / 2, s.clip(word, 18, tw + 4), 18, (0x14, 0x14, 0x14))
    # the description: at most two lines, the second ending in an ellipsis when the text is longer
    text = tr('Songs you love and some to rediscover, made fresh every day.')
    lines = D.wrap(lambda t: s.font.width(t, D.DP_DESC_PX), text, D.DP_TEXT_W, 16) or [text]
    if len(lines) > D.DP_DESC_LINES: lines = [lines[0], text[len(lines[0]):].lstrip()]
    for i, t in enumerate(lines[:D.DP_DESC_LINES]):
        s.text(c, D.DP_TEXT_X, D.DP_DESC_Y + i * D.DP_DESC_PITCH + D.DP_DESC_PITCH / 2, s.clip(t, D.DP_DESC_PX, D.DP_TEXT_W), D.DP_DESC_PX, grey)
    # the songs
    ov = Image.new('RGBA', c.size, (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
    for r, (title, artist, rgb, fav) in enumerate(songs):
        y = D.DP_ROWS_Y + r * O['LIST_ROW_H']
        if pressed == r: od.rectangle((0, y, D.DP_W - 1, y + O['LIST_ROW_H'] - 2), fill=(255, 255, 255, 0x33))
        od.rectangle((O['LIST_TEXT_X'], y + O['LIST_ROW_H'] - 1, D.DP_W - 1, y + O['LIST_ROW_H'] - 1), fill=(255, 255, 255, 0x22))
    c.alpha_composite(ov)
    for r, (title, artist, rgb, fav) in enumerate(songs):
        y = D.DP_ROWS_Y + r * O['LIST_ROW_H']
        c.alpha_composite(PI.rounded(PI.sample_cover(rgb if covers else None, O['LIST_ART']), O['LIST_R']), (O['LIST_ART_X'], y + O['LIST_ART_Y']))
        for text, ty, th, px, rgb_ in ((title, O['LIST_TITLE_Y'], O['LIST_TITLE_H'], 21, (255, 255, 255)), (artist, O['LIST_SUB_Y'], O['LIST_SUB_H'], 18, grey)):
            top = y + ty - off
            if top >= 0 and top + th <= D.DP_VIEW_H:     # a line not wholly in the view is not drawn (patch/grid.c grid_text)
                s.text(c, O['LIST_TEXT_X'], y + ty + th / 2, s.clip(text, px, O['LIST_TEXT_W']), px, rgb_)
    win = c.crop((0, off, D.DP_W, off + D.DP_VIEW_H))
    # the fixed back disc over the list
    back = s.img('dp_back'); win.alpha_composite(back, (D.DP_BACK_X + (D.DP_BACK_BTN - back.width) // 2, D.DP_BACK_Y + (D.DP_BACK_BTN - back.height) // 2))
    out = Image.new('RGBA', (320, 480), (0, 0, 0, 255))
    PI.status_bar(s, out, 0)
    out.alpha_composite(win, (0, 30))
    return out.convert('RGB')


def widest(sides):
    """The locale with the widest of the page's single lines (title, subtitle, Updated with a date, the pill's text), and the table."""
    tab = []
    for loc in D.LOCALES:
        s = sides[loc]; tr = lambda k: pod_i18n.TEXT[k][loc]
        tab.append((loc, s.font.width(tr('Daily Mix'), D.DP_TITLE_PX), s.font.width(tr('Made for You'), D.DP_SUB_PX), s.font.width(tr('Updated %s').replace('%s', '2026-10-26'), D.DP_UPD_PX),
                    s.font.width(tr('Play'), 18), len(D.wrap(lambda t: s.font.width(t, D.DP_DESC_PX), tr('Songs you love and some to rediscover, made fresh every day.'), D.DP_TEXT_W, 16) or [0, 0, 0])))
    return tab


def main():
    work = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(preview.build.ROOT, 'out', 'dailymix-page')
    os.makedirs(out, exist_ok=True)
    save = lambda name, im: (im.save(os.path.join(out, name)), print('wrote', os.path.join(out, name), im.size))
    sides = {loc: PD.side(work, loc) for loc in D.LOCALES}
    s = sides['en_US']
    off_rows = D.DP_ROWS_Y - 60
    for name, tones in PALS.items():
        save(f'top-{name}.png', page_image(s, tones))
        save(f'rows-{name}.png', page_image(s, tones, off=off_rows))
    save('rows-end.png', page_image(s, PALS['warm'], off=D.DP_ROWS_Y + len(SONGS) * O['LIST_ROW_H'] + D.DP_BOTTOM - D.DP_VIEW_H))
    save('pressed.png', page_image(s, PALS['cool'], off=off_rows, pressed=2))
    save('no-cover.png', page_image(s, PALS['grey'], off=off_rows, covers=False))
    save('palettes.png', PD.labelled([(n, page_image(s, t)) for n, t in PALS.items()] + [(n + ' (scrolled)', page_image(s, t, off=off_rows)) for n, t in PALS.items()], 3))
    tab = widest(sides)
    for r in tab: print('  %-6s title %3d  sub %3d  updated %3d  play %3d  description lines %d' % r)
    loc = max(tab, key=lambda r: max(r[1:5]) + 40 * r[5])[0]
    print('widest:', loc)
    save('longest.png', PD.labelled([(loc + ' (the widest lines)', page_image(sides[loc], PALS['warm'], loc=loc, updated=pod_i18n.TEXT['Updated %s'][loc].replace('%s', '2026-10-26'))),
                                      (loc + ' (scrolled)', page_image(sides[loc], PALS['warm'], loc=loc, off=off_rows, updated=pod_i18n.TEXT['Updated yesterday'][loc]))], 2))
    save('languages.png', PD.labelled([(l, page_image(sides[l], PALS['cool'], loc=l, updated=pod_i18n.TEXT['Updated yesterday'][l])) for l in D.LOCALES], 4))
    # the contrast table, as the test measures it
    for name, tones in PALS.items():
        rows, tint = D.page_art(tones, SEED); grey, acc = D.page_colours(tint)
        print('  %-5s tint %s  white %.2f  grey %.2f  accent %.2f' % (name, tint, D.contrast((255, 255, 255), tint), D.contrast(grey, tint), D.contrast(acc, tint)))


if __name__ == '__main__':
    main()
