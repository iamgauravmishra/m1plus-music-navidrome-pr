#!/usr/bin/env python3
"""docs/queue-preview.png: PIL mock-up of the queue drawer (ui/dialog/playqueue_dialog.bin: the 240x450 panel that
slides in from the right over Now Playing) from built trees, before and after (docs/ui.md). Approximate, not AWTK;
sample data. The rows are cloned from the template as the app does (queue_table_row, row_height apart, the
playing row with srlabel_item_gold20_style, the others srlabel_item_white_style, set by the row bind @0x47a19c).

Usage: venv/bin/python -I tools/preview_queue.py OUT.png LABEL=RAW_DIR [LABEL=RAW_DIR ...]
RAW_DIR is a tree's rootfs/release/assets/default/raw.
"""
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui, awtk_style
import preview_font   # noqa: F401  (redirects the painters' text to stb_raster, the tree's font)
import preview_nowplaying as PN

W, H, BAR = PN.W, PN.H, PN.BAR
TRACKS = ['Money', 'Us and Them', 'Time', 'Breathe (In the Air)', 'Any Colour You Like', 'The Great Gig in the Sky',
          'Brain Damage', 'Eclipse', 'On the Run', 'Speak to Me']
PLAYING, MODE, BUTTON = 2, ('p_random', 'Shuffle'), 'Clear'


class QueueTheme(PN.Theme):
    def __init__(self, raw):
        self.sets = []
        for f in ('playqueue_dialog.bin', 'default.bin'):       # the window's theme first, then the global one
            p = os.path.join(raw, 'styles', f)
            if os.path.exists(p): self.sets.append(awtk_style.parse(open(p, 'rb').read()).items)


class QueuePainter(PN.Painter):
    def __init__(self, raw):
        super().__init__(raw)
        self.theme = QueueTheme(raw)

    def drawer(self, dlg, shot):
        """The drawer over `shot` (a Now Playing window image with its status bar), dimmed, as the dialog slides in."""
        im = shot.copy(); dim = Image.new('RGBA', im.size, (0, 0, 0, 120)); im.alpha_composite(dim)
        d = dlg
        x0, y0 = 80, BAR                                    # the animation ends at x 80, y 30
        layer = Image.new('RGBA', im.size)
        ImageDraw.Draw(layer).rectangle([x0, y0, x0 + d.w - 1, y0 + d.h - 1], fill=d.get('style:normal:bg_color', '#000000'))
        bc = d.get('style:normal:border_color')
        if bc and d.get('style:normal:border') == 'left': ImageDraw.Draw(layer).line([(x0, y0), (x0, y0 + d.h - 1)], fill=bc)
        head = d.find('list_item')                          # the play-mode header, 64 px
        hb = head.get('style:normal:border_color')
        if head.get('style:normal:border') == 'bottom' and hb:
            ImageDraw.Draw(layer).line([(x0, y0 + head.h - 1), (x0 + d.w - 1, y0 + head.h - 1)], fill=hb)
        icon = self.image(MODE[0]); img = d.find('img_playmode'); lab = d.find('label_playmode')
        if icon: layer.alpha_composite(icon, (x0 + img.x + (img.w - icon.width) // 2, y0 + img.y + (img.h - icon.height) // 2))
        self.text(layer, (x0 + lab.x, y0 + lab.y, lab.w, lab.h), MODE[1], lab)
        tv, cl, row, btn, name = (d.find(n) for n in ('table_view', 'queue_table_client', 'queue_table_row', 'btn_table_row', 'scrlabel_name'))
        rh = int(cl.get('row_height', '64'))
        top, bottom = y0 + tv.y, y0 + d.h - 128 + tv.y      # the table: y 64, h = 450 - 128
        for i, t in enumerate(TRACKS):
            ry = top + i * rh
            if ry >= bottom: break
            bgs = btn.get('style:normal:bg_color', '#141414')
            clipbox = (x0, ry, x0 + 230, min(ry + btn.h, bottom))
            ImageDraw.Draw(layer).rectangle([clipbox[0], clipbox[1], clipbox[2] - 1, clipbox[3] - 1], fill=bgs)
            lw = awtk_ui.Widget(name.type, name.x, name.y, name.w, name.h, list(name.props))
            lw.props = [(k, v) for k, v in lw.props if not k.startswith('style:') or 'align' in k]
            lw.props = [(k, v) for k, v in lw.props if k != 'style'] + [('style', 'srlabel_item_gold20_style' if i == PLAYING else 'srlabel_item_white_style')]
            sub = Image.new('RGBA', im.size)
            self.text(sub, (x0 + lw.x, ry + lw.y, lw.w, lw.h), t, lw)
            layer.alpha_composite(sub.crop(clipbox), clipbox[:2])
        b = d.find('button')
        r = (x0 + b.x, y0 + b.y, b.w, b.h)
        ImageDraw.Draw(layer).rectangle([r[0], r[1], r[0] + r[2] - 1, r[1] + r[3] - 1], fill=b.get('style:normal:bg_color', '#131313'))
        self.text(layer, r, BUTTON, b)
        im.alpha_composite(layer)
        return im


def main():
    out, specs = sys.argv[1], sys.argv[2:]
    if not specs: sys.exit(__doc__)
    pad, top = 10, 18
    shots = []
    for spec in specs:
        label, raw = spec.split('=', 1)
        p = QueuePainter(raw)
        p.sample = dict(PN.SAMPLE, scrlabel_title='Money', scrlabel_artist='Pink Floyd', label_album='Album:The Dark Side of the Moon')
        np_root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'playing_page.bin'), 'rb').read())
        np_painter = PN.Painter(raw); np_painter.sample = p.sample
        base = np_painter.render(np_root, 0)
        dlg = awtk_ui.parse(open(os.path.join(raw, 'ui', 'dialog', 'playqueue_dialog.bin'), 'rb').read())
        shots.append((label, p.drawer(dlg.find('playqueue_dialog'), base)))
    im = Image.new('RGB', (len(shots) * (W + pad) + pad, BAR + H + top + 18), (40, 40, 40)); d = ImageDraw.Draw(im)
    for i, (label, s) in enumerate(shots):
        x = pad + i * (W + pad); im.paste(s.convert('RGB'), (x, top)); d.text((x, 3), label, fill=(220, 220, 220))
    d.text((pad, BAR + H + top + 3), 'approximate PIL mock-up, not AWTK; sample queue (the third row is playing), the drawer slid in, Now Playing dimmed',
           fill=(160, 160, 160))
    im.save(out, optimize=True); print('wrote', out)


if __name__ == '__main__': main()
