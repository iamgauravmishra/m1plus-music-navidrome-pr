#!/usr/bin/env python3
"""PIL mock-up of the navbar fade (docs/modules/navbar.md, "The fade") before / after the at-rest fix: the pages' own bar (ui/*.bin without the fade widget), sample
content under it (cover squares at the Albums geometry, text rows), and the fade drawn from the formula: BEFORE = alpha 255 (1 - t)^2.2 on every page, always; AFTER = (1 - t)^3.6,
and on Albums (grid and list) only while the page is scrolled. Approximate, not AWTK.

Usage: uv run python -I tools/preview_fade.py WORKDIR OUT.png      (WORKDIR: a built tree; WORK/rootfs/release/assets/default/raw)"""
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
import preview_navbars as pn

W, BAR, H, FADE_H = pn.W, pn.BAR, pn.H, 20
C = pn.C
TOP = BAR + 50      # the window's y 50 on the screen


def fade(im, exp):
    for y in range(FADE_H):
        a = round(255 * (1 - (y + 0.5) / FADE_H) ** exp)
        row = im.crop((0, TOP + y, W, TOP + y + 1)).convert('RGBA')
        im.paste(Image.alpha_composite(row, Image.new('RGBA', (W, 1), (0, 0, 0, a))), (0, TOP + y))


def without_fade(root):
    root.children = [c for c in root.children if c.name != 'img_nb_fade']


def grid_content(im, scroll):
    d = ImageDraw.Draw(im)
    cols = [(200, 90, 60), (60, 140, 200), (120, 180, 90), (210, 170, 60)]
    gap, cover, m, rg = C['GRID_GAP'], C['GRID_COVER'], C['GRID_MARGIN'], C['GRID_ROW_GAP']
    for r in range(4):
        for c in range(2):
            x, y = m + c * (cover + gap), TOP + rg + r * (cover + 46 + rg) - scroll
            d.rectangle([x, y, x + cover - 1, y + cover - 1], fill=cols[(r * 2 + c) % 4])
            d.rectangle([x, y + cover + 6, x + 100, y + cover + 20], fill=(230, 230, 230))
            d.rectangle([x, y + cover + 26, x + 70, y + cover + 36], fill=(150, 150, 150))


def list_content(im, scroll):
    d = ImageDraw.Draw(im)
    cols = [(200, 90, 60), (60, 140, 200), (120, 180, 90), (210, 170, 60)]
    for r in range(8):
        y = TOP + r * C['LIST_ROW_H'] - scroll
        d.rectangle([C['LIST_ART_X'], y + C['LIST_ART_Y'], C['LIST_ART_X'] + C['LIST_ART'] - 1, y + C['LIST_ART_Y'] + C['LIST_ART'] - 1], fill=cols[r % 4])
        d.rectangle([C['LIST_TEXT_X'], y + 12, C['LIST_TEXT_X'] + 140, y + 26], fill=(230, 230, 230))
        d.rectangle([C['LIST_TEXT_X'], y + 34, C['LIST_TEXT_X'] + 90, y + 46], fill=(150, 150, 150))


def panel(work, rel, content, scroll, after, shown_at_rest):
    """The page's bar over `content` (a function drawing under it), then the fade."""
    raw = pn.tree(work)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', rel), 'rb').read())
    without_fade(root)
    lst = next((c for c in root.children if c.y == 50 and c.h >= 300 and c.type == 'list_view'), None)
    if lst is not None:
        sv = next((c for c in lst.walk() if c.type == 'scroll_view'), lst)
        sv.children = content if isinstance(content, list) else []
    im = pn.NavPainter(raw).render(root, 0).convert('RGBA')
    if callable(content): content(im, scroll)
    bar = pn.NavPainter(raw).render(root, 0).convert('RGBA').crop((0, 0, W, TOP))
    im.paste(bar, (0, 0))
    if shown_at_rest or scroll > 0: fade(im, 3.6 if after else 2.2)
    return im.convert('RGB')


def main():
    work, out = sys.argv[1:3]
    specs = [
        ('Albums grid, rest', 'm1plus_albums.bin', grid_content, 0, False),
        ('Albums grid, scrolled 40', 'm1plus_albums.bin', grid_content, 40, False),
        ('Albums list, rest', 'm1plus_albums.bin', list_content, 0, False),
        ('Albums list, scrolled 40', 'm1plus_albums.bin', list_content, 40, False),
        ('Extras, rest', 'm1plus_extras.bin', pn.row_widgets(pn.SETTINGS, 0, 0, pitch=52), 0, True),
        ('Extras, scrolled 150', 'm1plus_extras.bin', pn.row_widgets(pn.SETTINGS, 0, 150, pitch=52), 150, True),
        ('Artists, rest', 'm1plus_artists.bin', pn.row_widgets(pn.ARTISTS, 0, 0, pitch=52), 0, True),
    ]
    pad, top = 10, 20
    cell_h = TOP + 130
    img = Image.new('RGB', (len(specs) * (W + pad) + pad, 2 * (cell_h + top + pad) + pad), (40, 40, 40))
    d = ImageDraw.Draw(img)
    for r, (tag, after) in enumerate((('before', False), ('after', True))):
        for c, (cap, rel, content, sc, always) in enumerate(specs):
            # AFTER: the Albums pages show the fade only while scrolled; the text pages always (their rows clear it)
            im = panel(work, rel, content, sc, after, always or not after)
            x, y = pad + c * (W + pad), pad + r * (cell_h + top + pad)
            d.text((x, y + 4), f'{tag}: {cap}', fill=(230, 230, 230))
            img.paste(im.crop((0, 0, W, cell_h)), (x, y + top))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    img.save(out, optimize=True); print('wrote', out)


if __name__ == '__main__': main()
