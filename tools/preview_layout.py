"""Shared theme-aware list/widget painter for the feature previews.

The combined preview entry point is tools/preview.py (make preview).
"""
import os, sys
from PIL import ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_style, preview_nowplaying
from awtk_ui import RAW as RAW  # re-exported: preview_cover uses preview_layout.RAW

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

