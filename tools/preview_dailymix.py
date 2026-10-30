#!/usr/bin/env python3
"""Previews of the Daily Mix hero card (docs/modules/dailymix.md): the card at 1x and 2x, in the Home layout (rows, the new section, the Recently
Played shelf, the mini bar), six palettes, every language, and Customize > Home Screen with the proposed rows. Approximate, not AWTK; sample data.

  venv/bin/python -I tools/preview_dailymix.py WORKDIR [OUTDIR]       (WORKDIR: the built release tree, work/mod-release; default OUTDIR out/dailymix)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image, ImageDraw
import preview, preview_icons as PI, pod_dailymix as D, pod_ui as U, mod_icons as M, awtk_ui
from awtk_text import Ttf, awtk_width

RAW = awtk_ui.RAW
ARTISTS = ['Radiohead', 'Björk', 'Air', 'Portishead', 'Massive Attack']
SEED = 20261028          # the day number or a date hash on the device; any 32-bit value
PALETTES = [   # name -> the mix's top album tones (RGB)
    ('default', [(70, 110, 190), (190, 90, 120), (60, 140, 150)]),
    ('dark', [(30, 30, 45), (60, 40, 70), (20, 50, 60)]),
    ('warm', [(230, 120, 40), (200, 60, 50), (240, 190, 80)]),
    ('cool', [(40, 90, 200), (60, 170, 190), (110, 80, 200)]),
    ('pale / bright', [(240, 235, 225), (250, 225, 210), (225, 235, 245), (245, 245, 235)]),
    ('mono / grey', [(128, 128, 128), (60, 60, 60), (200, 200, 200)]),
]


def side(work, loc='en_US'):
    """A Side for `loc` whose string table also holds the proposed Daily Mix texts (the build does not have them yet)."""
    s = PI.Side(work, True, loc); s.mark = lambda *a: None
    s.strings.update({k: v[loc] for k, v in D.TEXT.items()})
    s.ttf = Ttf(os.path.join(work, RAW, 'fonts', 'default.ttf'))
    return s


def width(s, text, px): return awtk_width(s.ttf, text, px)


def disc(pressed=False):
    d = M.glass_image(D.DM_DISC, D.DM_DISC, D.DM_DISC // 2, pressed)
    g = M.glyph_fit('play:filled', D.DM_PLAY_GLYPH, D.DM_PLAY_GLYPH, (255, 255, 255), 0)
    d.alpha_composite(g, ((D.DM_DISC - g.width) // 2 + 1, (D.DM_DISC - g.height) // 2))   # +1: a triangle's weight sits left of its box centre
    return d


def card_image(s, tones, seed=SEED, loc='en_US', names=ARTISTS, pressed=False):
    """The card as the device paints it: the art (rounded corners DM_R blended into black), the title lines, the artist lines, the glass disc."""
    rows, a64 = D.art(tones, seed)
    im = D.to_image(rows).convert('RGBA')
    k = 4
    mask = Image.new('L', (D.DM_W * k, D.DM_H * k), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, D.DM_W * k - 1, D.DM_H * k - 1), radius=D.DM_R * k, fill=255)
    out = Image.new('RGBA', im.size, (0, 0, 0, 255)); out.paste(im, (0, 0), mask.resize(im.size, Image.LANCZOS))
    lines = D.title_lines(D.tr(loc, 'Daily Mix'))
    boxes = [D.DM_TITLE_Y1, D.DM_TITLE_Y2][-len(lines):]
    for line, by in zip(lines, boxes):
        s.text(out, D.DM_PAD, by + D.DM_TITLE_PITCH / 2, s.clip(line, D.DM_TITLE_PX, D.DM_TITLE_W), D.DM_TITLE_PX, D.TITLE_RGB)
    for i, line in enumerate(D.artist_lines(lambda t: width(s, t, D.DM_SUB_PX), names, loc)):
        s.text(out, D.DM_PAD, D.DM_SUB_Y + i * D.DM_SUB_PITCH + D.DM_SUB_PITCH / 2, line, D.DM_SUB_PX, D.SUB_RGB)
    out.alpha_composite(disc(pressed), (D.DM_DISC_X, D.DM_DISC_Y))
    return out


def section_image(s, tones, seed=SEED, loc='en_US', names=ARTISTS):
    """The Home list's new section (310 x DM_SEC_H): the header exactly as the Recently Played one, the card at (12, 44), DM_BOTTOM of air."""
    im = Image.new('RGBA', (D.DM_W_VIEW, D.DM_SEC_H), (0, 0, 0, 255))
    s.text(im, D.DM_HEAD_X + 2, D.DM_HEAD_TOP + D.DM_HEAD_H / 2, s.clip(D.tr(loc, 'Made for You'), D.DM_HEAD_PX, D.DM_HEAD_W - 4), D.DM_HEAD_PX)
    im.alpha_composite(card_image(s, tones, seed, loc, names), (D.DM_X, D.DM_TOP))
    return im


def settings_page(s, loc='en_US', daily=True):
    """Customize > Home Screen as the build has it: Boot to M1+ Music, Recent Albums, Daily Mix (a switch, shuffle glyph), Regenerate Daily Mix (an action
    row without a chevron, the Update Library refresh glyph) and Shanling Home. daily=False leaves the two Daily Mix rows out (the page before them)."""
    root = awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', 'm1plus_homeset.bin'), 'rb').read())
    sv = root.find('pod_scrollview')
    start, recent, sw_row, act_row, shan = sv.children
    sv.children = [start, recent, sw_row, act_row, shan] if daily else [start, recent, shan]
    for i, r in enumerate(sv.children): r.y = i * 52
    return PI.pod_page(s, 'm1plus_homeset', len(sv.children), switches={'pod_switch0': True, 'pod_switch1': True, 'pod_switch2': True}, root=root).convert('RGB')


def labelled(items, cols, gap=12, lab=18, bg=(0x2A, 0x2A, 0x2A)):
    """A contact sheet of (caption, image) in `cols` columns."""
    rows = [items[i:i + cols] for i in range(0, len(items), cols)]
    cw = max(im.width for _, im in items); w = cols * cw + (cols + 1) * gap
    h = gap + sum(max(im.height for _, im in r) + lab + gap for r in rows)
    sheet = Image.new('RGB', (w, h), bg); d = ImageDraw.Draw(sheet); y = gap
    for r in rows:
        for c, (cap, im) in enumerate(r):
            x = gap + c * (cw + gap); d.text((x, y), cap, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, y + lab))
        y += max(im.height for _, im in r) + lab + gap
    return sheet


def widths_table(s):
    """(loc, header px at 20, title line px at 36, settings row px at 21 for the switch label and the action label) for each locale."""
    out = []
    for loc in D.LOCALES:
        head = width(s, D.tr(loc, 'Made for You'), D.DM_HEAD_PX)
        tl = max(width(s, t, D.DM_TITLE_PX) for t in D.title_lines(D.tr(loc, 'Daily Mix')))
        sw = width(s, D.tr(loc, 'Daily Mix'), 21); act = width(s, D.tr(loc, 'Regenerate Daily Mix'), 21)
        out.append((loc, head, tl, sw, act))
    return out


def main():
    work = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(preview.build.ROOT, 'out', 'dailymix')
    os.makedirs(out, exist_ok=True)
    save = lambda name, im: (im.save(os.path.join(out, name)), print('wrote', os.path.join(out, name), im.size))
    s = side(work)
    tones = PALETTES[0][1]
    bar_args = ('Blue in Green (Remastered, Mono Version)', 'Miles Davis', (70, 110, 190))
    sec = section_image(s, tones)
    shelf = (preview.SHELF_ALBUMS,)
    # (a) the Home page with the card fully visible (clear of the mini bar), at the end, and at the top
    save('home-card-visible.png', preview.minibar_page(s, *bar_args, shelf=shelf, daily=sec, scroll=212))
    save('home-card-end.png', preview.minibar_page(s, *bar_args, shelf=shelf, daily=sec, scroll=None))
    save('home-card-to-shelf.png', preview.minibar_page(s, *bar_args, shelf=shelf, daily=sec, scroll=430))   # the card's foot and the Recently Played header: the gap between the sections
    save('home-top.png', preview.minibar_page(s, *bar_args, shelf=shelf, daily=sec, scroll=0))
    save('home-card-no-shelf.png', preview.minibar_page(s, *bar_args, daily=sec, scroll=None))
    # (b) the card alone
    card = card_image(s, tones)
    save('card-1x.png', card.convert('RGB'))
    save('card-2x.png', card.convert('RGB').resize((card.width * 2, card.height * 2), Image.NEAREST))
    save('section-1x.png', sec.convert('RGB'))
    # (c) palettes
    save('palettes.png', labelled([(n, card_image(s, t)) for n, t in PALETTES], 3))
    save('card-pressed.png', labelled([('normal', card), ('disc pressed', card_image(s, tones, pressed=True))], 2))
    # (d) Customize > Home Screen
    save('settings-home-screen.png', labelled([('without Daily Mix', settings_page(s, daily=False)), ('with Daily Mix', settings_page(s))], 2))
    # (e) every language, and the longest strings
    sides = {loc: side(work, loc) for loc in D.LOCALES}
    save('card-languages.png', labelled([(loc, section_image(sides[loc], tones, loc=loc)) for loc in D.LOCALES], 3))
    tab = widths_table(s)
    for name, col, room in (('header 20 px (label 296)', 1, 296), ('title line 36 px (260)', 2, D.DM_TITLE_W), ('switch row 21 px (195)', 3, 195), ('action row 21 px (220)', 4, 220)):
        loc, w = max(((r[0], r[col]) for r in tab), key=lambda r: r[1])
        print(f'longest {name}: {loc} {w} px of {room}')
    longest = {max(tab, key=lambda r: r[c])[0] for c in (1, 2, 3, 4)}
    save('settings-longest.png', labelled([(loc, settings_page(sides[loc], loc)) for loc in sorted(longest)], len(longest)))
    for r in tab: print('  %-6s header %3d  title %3d  switch %3d  action %3d' % r)
    for loc in D.LOCALES:
        print('  %-6s' % loc, D.artist_lines(lambda t: width(sides[loc], t, D.DM_SUB_PX), ARTISTS, loc))


if __name__ == '__main__':
    main()
