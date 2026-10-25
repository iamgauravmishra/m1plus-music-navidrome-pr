#!/usr/bin/env python3
"""Combined PIL mock-up of a look-all tree (V2.1fA), one panel per look, drawn by the looks' own
preview tools from the finished tree (approximate, not AWTK):

  boot splash      images/xx/logo.jpg as shipped (look-boot)
  Home             preview_theme.home (look-theme: status bar, Home strip, dots)
  System Settings  preview_theme.settings (look-theme: rows, icon discs, pressed row)
  Songs            preview_lists songs page (look-lists: window theme rows, index letter)
  Now Playing      preview_nowplaying (look-nowplaying)
  M1 Pod menu      ui/m1pod_menu.bin drawn with preview_nowplaying's painter over default.bin
                   (the payload's menu follows list_item_style, so it picks up the theme)

Usage: venv/bin/python -I tools/preview_all.py WORKDIR OUT.png [--label TEXT]
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_style, awtk_ui
import preview_theme, preview_lists, preview_nowplaying

RAW = 'rootfs/release/assets/default/raw'
W, H = 320, 480

class MenuPainter(preview_nowplaying.Painter):
    """preview_nowplaying's widget painter, with the global theme only and list_item tiles drawn."""
    def __init__(self, raw):
        super().__init__(raw)
        self.theme.sets = [awtk_style.parse(open(os.path.join(raw, 'styles', 'default.bin'), 'rb').read()).items]
    def prop(self, wd, prop, state='normal'):
        v = super().prop(wd, prop, state)
        if prop == 'text_align_h' and isinstance(v, int):     # theme enum: AWTK align_h_t
            v = {1: 'center', 2: 'left', 3: 'right'}.get(v, 'left')
        return v
    def walk(self, im, wd, ox, oy, clip, page, root):
        if wd.name == 'btn_return':        # navbar_btnreturn_style draws the arrow at the left edge, as preview_theme
            ic = self.image(self.prop(wd, 'icon'))
            if ic: im.alpha_composite(ic, (ox + wd.x + 14, oy + wd.y + (wd.h - ic.height) // 2))
            return
        if wd.type == 'list_item':
            x, y, w, h = ox + wd.x, oy + wd.y, wd.w, wd.h
            d = ImageDraw.Draw(im)
            bg = self.prop(wd, 'bg_color')
            if bg: d.rectangle([x, y, x + w - 1, y + h - 1], fill=bg)
            bw, bc, side = int(self.prop(wd, 'border_width') or 0), self.prop(wd, 'border_color'), self.prop(wd, 'border')
            if bw and bc and (side is None or int(side) & 8):          # 8 = bottom
                d.rectangle([x, y + h - bw, x + w - 1, y + h - 1], fill=bc)
        super().walk(im, wd, ox, oy, clip, page, root)

def menu(work):
    raw = os.path.join(work, RAW)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1pod_menu.bin'), 'rb').read())
    return MenuPainter(raw).render(root, 0)

def splash(work):
    return Image.open(os.path.join(work, RAW, 'images', 'xx', 'logo.jpg')).convert('RGBA')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work'); ap.add_argument('out'); ap.add_argument('--label', default='look-all (V2.1fA)')
    a = ap.parse_args()
    t = preview_theme.Tree(a.work)
    raw = os.path.join(a.work, RAW)
    np_root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'playing_page.bin'), 'rb').read())
    shots = [('boot splash', splash(a.work)), ('Home', preview_theme.home(t)),
             ('System Settings (Display pressed)', preview_theme.settings(t)),
             ('Songs (index letter)', preview_lists.panels(a.work, 'default')[1]),
             ('Now Playing', preview_nowplaying.Painter(raw).render(np_root, 0)), ('M1 Pod menu', menu(a.work))]
    pad, top, cols = 12, 20, 3
    rows = (len(shots) + cols - 1) // cols
    out = Image.new('RGB', (cols * (W + pad) + pad, rows * (H + top + pad) + pad + 16), (40, 40, 40))
    d = ImageDraw.Draw(out)
    for i, (cap, im) in enumerate(shots):
        x, y = pad + (i % cols) * (W + pad), pad + (i // cols) * (H + top + pad)
        assert im.size == (W, H), (cap, im.size)
        out.paste(im.convert('RGB'), (x, y + top)); d.text((x, y + 4), f'{a.label}: {cap}', fill=(230, 230, 230))
    d.text((pad, out.height - 18), 'approximate PIL mock-ups from the finished tree (not AWTK); sample data', fill=(160, 160, 160))
    out.quantize(colors=192).save(a.out, optimize=True); print('wrote', a.out)

if __name__ == '__main__': main()
