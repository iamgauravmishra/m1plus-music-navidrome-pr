#!/usr/bin/env python3
"""Preview of the overlay screens (tools/mod_overlays.py, docs/modules/overlays.md), drawn from the built tree's files.

  preview_overlays.py TREE OUT.png

Panels: the confirm and message dialogs over a dimmed page (the dialog highlight alpha 100) and the power-off splash. Not tracked (out/preview/).
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw, ImageFont

RAW = 'rootfs/release/assets/default/raw'
W, H = 320, 480
GAP, BG = 16, (40, 40, 40)


def load(tree, n): return Image.open(os.path.join(tree, RAW, 'images/xx', n + '.png')).convert('RGBA')


def page(tree, draw_body):
    """A black 320 x 480 screen with `draw_body(im, draw, font)`."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255)); d = ImageDraw.Draw(im)
    font = ImageFont.truetype(os.path.join(tree, RAW, 'fonts/default.ttf'), 20)
    draw_body(im, d, font); return im


def dialogs(tree):
    def body(confirm):
        def f(im, d, font):
            for y in range(0, H, 48):          # a page behind: rows of text-like bars
                d.rectangle((24, y + 14, 24 + 120 + (y * 7) % 90, y + 24), fill=(150, 150, 150, 255))
            im.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, 100)))   # the dialog highlight, alpha 100
            card = load(tree, 'confirminfo_bg' if confirm else 'msginfo_bg')
            x, y = (W - 260) // 2, (H - 180) // 2
            im.alpha_composite(card, (x, y)); d = ImageDraw.Draw(im)
            d.text((W // 2, y + 56), 'Delete Song?' if confirm else 'Library updated', font=font, fill='white', anchor='mm')
            if confirm:   # the Cancel button's right border at x 129 (card x) and the labels
                im.alpha_composite(Image.new('RGBA', (1, 48), (255, 255, 255, 0x22)), (x + 129, y + 131)); d = ImageDraw.Draw(im)
                d.text((x + 65, y + 155), 'No', font=font, fill='white', anchor='mm'); d.text((x + 195, y + 155), 'Yes', font=font, fill='white', anchor='mm')
        return f
    return [page(tree, body(True)), page(tree, body(False))]


def main():
    if len(sys.argv) != 3: sys.exit(__doc__)
    tree, out = sys.argv[1:]
    panels = dialogs(tree) + [page(tree, lambda im, d, f: im.alpha_composite(load(tree, 'shutdown')))]
    canvas = Image.new('RGB', (len(panels) * (W + GAP) + GAP, H + 2 * GAP), BG)
    for i, p in enumerate(panels): canvas.paste(p.convert('RGB'), (GAP + i * (W + GAP), GAP))
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    canvas.save(out); print('->', out)


if __name__ == '__main__': main()
