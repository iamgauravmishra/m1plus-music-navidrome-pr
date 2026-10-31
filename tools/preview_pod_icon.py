#!/usr/bin/env python3
"""out/mocks/pod_icon.png: candidate glyphs for the Pod row (Extras > Pod, now Lucide 'circle'), Lucide style
(24 grid, 2 px stroke at 24 px, round caps), drawn by mod_icons' own renderer: 8x zoom, 1:1, and on the
Extras page of the built release tree in place of pod_ic_ipod.

  preview_pod_icon.py [TREE] [OUT.png]       (default work/mod-release, out/mocks/pod_icon.png)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import mod_icons as M
import preview_icons as P

# Body: Lucide smartphone (rect 5,2 14x20 rx2); the rest is ours.
BODY = '<rect width="14" height="20" x="5" y="2" rx="2"/>'
CANDIDATES = [
    ('A  smartphone + wheel', BODY + '<circle cx="12" cy="15" r="3"/>'),
    ('B  + screen line', BODY + '<path d="M9 6h6"/><circle cx="12" cy="15" r="3"/>'),
    ('C  + screen box', BODY + '<rect width="8" height="5" x="8" y="5" rx="1"/><circle cx="12" cy="16" r="2.5"/>'),
    ('D  split body', BODY + '<path d="M5 11h14"/><circle cx="12" cy="16" r="2.5"/>'),
    ('E  wheel + hub', BODY + '<circle cx="12" cy="15" r="3.5"/><path d="M12 15h.01"/>'),
    ('F  screen + hub', BODY + '<rect width="8" height="5" x="8" y="5" rx="1"/><circle cx="12" cy="16" r="2.5"/><path d="M12 16h.01"/>'),
    ('G  nano (wide wheel)', '<rect width="12" height="20" x="6" y="2" rx="2"/><path d="M9 6h6"/><circle cx="12" cy="15" r="3.5"/>'),
    ('H  filled (reference)', None),
]
# the reference picture: a solid body, the screen and the wheel ring knocked out (even-odd)
FILLED = ('<path fill-rule="evenodd" fill="#FFFFFF" stroke="none" d="M7 2h10a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z'
          'M7.5 4.5v6.5h9v-6.5Z M12 12.6a3.6 3.6 0 1 0 0 7.2a3.6 3.6 0 1 0 0-7.2Z M12 14.3a1.9 1.9 0 1 1 0 3.8a1.9 1.9 0 1 1 0-3.8Z"/>')

def svg(body, px, dx, dy):
    sw = M.BARE_SW * 24 / px
    tx, ty = dx * 24 / px, dy * 24 / px
    g = (f'fill="none" stroke="#FFFFFF" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 24 24">'
            f'<g transform="translate({tx:.4f} {ty:.4f})" {g}>{body}</g></svg>')

def render(body, px=24):
    """As mod_icons.render: the sub-pixel offset with the crispest edges."""
    best = None
    for dx in (0, 0.25, 0.5, -0.25):
        for dy in (0, 0.25, 0.5, -0.25):
            im = M._rsvg(svg(body, px, dx, dy), px)
            c = M._crisp(im) - 0.002 * (abs(dx) + abs(dy))
            if best is None or c > best[0]: best = (c, im)
    return best[1]

class Side(P.Side):
    def __init__(self, tree, glyph):
        super().__init__(tree, True); self.glyph = glyph
    def img(self, n): return self.glyph if n == 'pod_ic_ipod' else super().img(n)

def main():
    tree = sys.argv[1] if len(sys.argv) > 1 else os.path.join(M.ROOT, 'work', 'mod-release')
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(M.ROOT, 'out', 'mocks', 'pod_icon.png')
    font = ImageFont.load_default(15); small = ImageFont.load_default(12)
    glyphs = [(name, render(body if body else FILLED)) for name, body in CANDIDATES]
    CELL, PAD = 24 * 8, 16
    cols = 4
    rows = (len(glyphs) + cols - 1) // cols
    cell_h = CELL + 24 + 40 + 20
    # the Extras page with candidate A to find the Pod row
    import awtk_ui
    root = awtk_ui.parse(open(os.path.join(tree, P.RAW, 'ui', 'm1plus_extras.bin'), 'rb').read())
    items = [w for w in root.walk() if w.type == 'list_item']
    pod_i = next(i for i, w in enumerate(items) if any(c.get('image') == 'pod_ic_ipod' for c in w.children))
    first = max(0, pod_i - 2)
    strip_h = 50 + 5 * 52
    W = PAD + cols * (P.W + PAD)
    sheet = Image.new('RGBA', (W, 40 + rows * cell_h + 30 + 2 * (strip_h + 30)), (0x2A,) * 3 + (255,))
    d = ImageDraw.Draw(sheet)
    d.text((PAD, 10), 'Pod row glyph candidates: Lucide style, 24 px, 2 px stroke (BARE_SW), 8x zoom with the 1:1 glyph on black', fill=(255,) * 3, font=font)
    for k, (name, g) in enumerate(glyphs):
        x0 = PAD + (k % cols) * (P.W + PAD); y0 = 40 + (k // cols) * cell_h
        d.text((x0, y0), name, fill=(0xCC,) * 3, font=font)
        z = Image.new('RGBA', (24, 24), (0, 0, 0, 255)); z.alpha_composite(g)
        z = z.resize((CELL, CELL), Image.NEAREST)
        sheet.alpha_composite(z, (x0, y0 + 22))
        one = Image.new('RGBA', (60, 60), (0, 0, 0, 255)); one.alpha_composite(g, (18, 18))
        sheet.alpha_composite(one, (x0 + CELL + 12, y0 + 22))
        two = Image.new('RGBA', (60, 60), (0, 0, 0, 255)); two.alpha_composite(g.resize((48, 48), Image.NEAREST), (6, 6))
        sheet.alpha_composite(two, (x0 + CELL + 12, y0 + 22 + 70))
        d.text((x0 + CELL + 12, y0 + 22 + 134), '1:1 / 2x', fill=(0x99,) * 3, font=small)
    y = 40 + rows * cell_h + 10
    d.text((PAD, y), 'On the Extras page (1:1, the built release tree; the Pod row in place)', fill=(255,) * 3, font=font); y += 24
    for k, (name, g) in enumerate(glyphs):
        x0 = PAD + (k % cols) * (P.W + PAD); yy = y + (k // cols) * (strip_h + 30)
        page = P.pod_page(Side(tree, g), 'm1plus_extras', 5, first=first)
        sheet.alpha_composite(page.crop((0, 0, P.W, strip_h)), (x0, yy + 18))
        d.text((x0, yy), name, fill=(0xCC,) * 3, font=small)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    sheet.convert('RGB').save(out); print('wrote', out)

if __name__ == '__main__': main()
