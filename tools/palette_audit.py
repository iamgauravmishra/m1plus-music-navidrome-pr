#!/usr/bin/env python3
"""Light Mode's and the accent's image audit (docs/modules/accent.md): which images of a built tree flip, which stay, and a contact sheet.

  palette_audit.py WORKDIR                      the table: how many images of each name prefix are kept, flipped as glyphs or flipped whole
  palette_audit.py WORKDIR --sheet SHEET.png    also the sheet of the images that flip: before (on black) and after (on LIGHT_PAPER)
      --kept                                  the sheet of the images that stay instead: on black, and as they are on LIGHT_PAPER (what would vanish)
      --only P1,P2                            only the images whose name starts with one of these prefixes

tools/palette.py decides; this only reports. Usage: uv run python -I tools/palette_audit.py WORKDIR [--sheet SHEET.png [--kept] [--only P1,P2]]
"""
import argparse, collections, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw
import palette
from awtk_ui import RAW


def audit(work):
    d = os.path.join(work, RAW, 'images', 'xx')
    out = {}
    for f in sorted(os.listdir(d)):
        if f.endswith('.png'):
            name = f[:-4]
            im = Image.open(os.path.join(d, f)).convert('RGBA')
            out[name] = (palette.image_flips(name, im), im)
    return out


def prefix(name):
    return name.split('_')[0] + '_' if '_' in name else name


def sheet(res, names, kept, path):
    cell, cols = 96, 10
    rows = (len(names) + cols - 1) // cols
    out = Image.new('RGB', (cols * cell * 2, max(rows, 1) * cell), (60, 60, 60))
    dr = ImageDraw.Draw(out)
    for i, n in enumerate(names):
        how, im = res[n]
        x, y = (i % cols) * cell * 2, (i // cols) * cell
        for k, (bg, pic) in enumerate((((0, 0, 0), im), ((palette.PAPER,) * 3, im if kept else palette.flip_image(n, im)))):
            tile = Image.new('RGBA', (cell, cell), bg + (255,))
            t = pic.copy(); t.thumbnail((cell - 4, cell - 14))
            tile.alpha_composite(t, ((cell - t.width) // 2, 2 + (cell - 14 - t.height) // 2))
            out.paste(tile.convert('RGB'), (x + k * cell, y))
        dr.text((x + 2, y + cell - 12), f'{n[:18]} {(how or "-")[0]}', fill=(200, 80, 80))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    out.save(path); print('wrote', path, out.size)


def accent_report(res):
    """The images the accent tints (palette.ACCENT_*): kind, size, opaque pixels, whether Light's lists would have flipped or kept it, and a name that is missing from the tree."""
    print('accent-tinted images (exact names; tinted instead of flipped):')
    for nm in palette.ACCENT_ALL:
        kind = palette.accent_kind(nm)
        if nm not in res:
            print(f'  {nm:24} {kind:7} MISSING from the tree')
            continue
        how, im = res[nm]
        opaque = sum(1 for p in im.getdata() if p[3])
        print(f'  {nm:24} {kind:7} {im.width}x{im.height} {opaque:6} px   Light: {how or "kept"}; Red: {palette.accent_pixel(kind, max(im.getdata(), key=lambda p: p[3]), "red")[:3]}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work'); ap.add_argument('--sheet'); ap.add_argument('--kept', action='store_true'); ap.add_argument('--only')
    a = ap.parse_args()
    res = audit(a.work)
    groups = collections.defaultdict(collections.Counter)
    for n, (how, _) in res.items(): groups[prefix(n)][how or 'kept'] += 1
    for p, c in sorted(groups.items(), key=lambda kv: -sum(kv[1].values())):
        print(f'{p:16} {dict(c)}')
    print('flipped:', sum(1 for h, _ in res.values() if h), 'of', len(res))
    accent_report(res)
    if a.sheet:
        only = tuple(a.only.split(',')) if a.only else ()
        names = [n for n, (h, _) in res.items() if bool(h) != a.kept and (not only or n.startswith(only))]
        sheet(res, names, a.kept, a.sheet)


if __name__ == '__main__':
    main()
