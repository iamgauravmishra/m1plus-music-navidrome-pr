#!/usr/bin/env python3
"""Approximate PIL mock-up of Radio's Now Playing page (ui/m1plus_radionp.bin); not pixel-exact AWTK.

  preview_radionp.py OUT.png RAW_DIR [LOGO.png]

RAW_DIR is a tree's rootfs/release/assets/default/raw. Draws three panels with the layout and text model of preview_nowplaying.py (the same Painter: awtk_text.StbText advances, built font,
inline styles): a station with a logo and an ICY title, a station without a logo, and a station connecting. The logo is LOGO.png, else a synthetic one; its window tone is the rule of
patch/radionp.c rn_tone (the mean of the pixels that are neither near-white ground nor near-black, then mod_nowplaying.tone). Station names and lines are sample data.
"""
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import awtk_ui
import preview_nowplaying as PN
from mod_nowplaying import tone

CARD_LOGO, CARD_GLYPH = (255, 255, 255), (0x2e, 0x2c, 0x2c)
CASES = (('logo + ICY title', True, 'BBC Radio 3', 'Miles Davis – So What', True, 'running'),
         ('no logo', False, 'Radio Paradise', 'United States · MP3 128k', True, 'running'),
         ('connecting', True, 'FIP', 'Connecting…', False, 'running'),
         ('stopped', True, 'FIP', 'Stopped', False, 'stopped'))


def synthetic_logo(n=192):
    im = Image.new('RGB', (n, n), 'white'); d = ImageDraw.Draw(im)
    d.ellipse([n * .12, n * .12, n * .88, n * .88], fill=(214, 64, 52))
    d.polygon([(n * .42, n * .3), (n * .72, n * .5), (n * .42, n * .7)], fill='white')
    return im


def logo_tone(im):
    px = list(im.convert('RGBA').getdata()); keep = [p for p in px if p[3] >= 128 and min(p[:3]) <= 232 and max(p[:3]) >= 24]
    if len(keep) < len(px) // 50 or not keep: return None
    return tone(*(sum(p[i] for p in keep) // len(keep) for i in range(3)))


class RadioPainter(PN.Painter):
    logo = None

    def walk(self, im, wd, ox, oy, clip, page, root):
        if wd.type == 'view' and wd.name == 'rn_art':
            r = (ox + wd.x, oy + wd.y, wd.w, wd.h); layer = Image.new('RGBA', im.size); d = ImageDraw.Draw(layer)
            col = self.prop(wd, 'bg_color') or '#00000000'
            if wd.name == 'rn_art':
                col = CARD_LOGO if self.logo else CARD_GLYPH
                d.rounded_rectangle([r[0], r[1], r[0] + r[2] - 1, r[1] + r[3] - 1], radius=int(self.prop(wd, 'round_radius') or 0), fill=col)
                if self.logo:
                    lg = self.logo.convert('RGBA').resize((r[2], r[3]), Image.LANCZOS); m = Image.new('L', lg.size, 0)
                    ImageDraw.Draw(m).rounded_rectangle([0, 0, r[2] - 1, r[3] - 1], radius=int(self.prop(wd, 'round_radius') or 0), fill=255); lg.putalpha(m); layer.alpha_composite(lg, r[:2])
            im.alpha_composite(layer)
        if wd.name == 'rn_art_ic' and self.logo: return
        super().walk(im, wd, ox, oy, clip, page, root)


def main():
    out, raw = sys.argv[1:3]
    logo = Image.open(sys.argv[3]).convert('RGB') if len(sys.argv) > 3 else synthetic_logo()
    shots = []
    for label, has_logo, name, line, _, state in CASES:
        root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'm1plus_radionp.bin'), 'rb').read())
        if state == 'running': root.find('rn_live').remove('visible')   # the LIVE divider shows while a station runs
        for st in ('normal', 'pressed'):   # running: the stop square, stopped: the play triangle (the asset's own)
            if state == 'running': root.find('btn_play').set(f'style:{st}:bg_image', 'rn_stop' + ('_down' if st == 'pressed' else ''))
        p = RadioPainter(raw); p.logo = logo if has_logo else None
        p.tint = logo_tone(logo) if has_logo else None
        p.sample = {'rn_title': name, 'rn_artist': line, 'rn_live_tx': 'LIVE'}
        shots.append((label, p.render(root, 0)))
    top, pad = 18, 10
    img = Image.new('RGB', (len(shots) * (PN.W + pad) + pad, PN.BAR + PN.H + top + 18), (40, 40, 40)); d = ImageDraw.Draw(img)
    for i, (label, im) in enumerate(shots):
        x = pad + i * (PN.W + pad); img.paste(im.convert('RGB'), (x, top)); d.text((x, 3), label, fill=(220, 220, 220))
    d.text((pad, PN.BAR + PN.H + top + 3), 'approximate PIL mock-up, not AWTK; sample station data', fill=(160, 160, 160))
    img.save(out, optimize=True); print('wrote', out)


if __name__ == '__main__': main()
