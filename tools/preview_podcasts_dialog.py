#!/usr/bin/env python3
"""Approximate PIL mock-up of the Podcasts refresh dialog (patch/podcasts.c pg_dlg_*, docs/modules/podcasts.md "Feeds"): the page behind the scrim (drawn as the Feeds level of before round 2 of the revamp: the Shows page is tools/preview_podcasts_revamp.py's) and the glass card, at three
moments (a show under way, Cancel pressed and the worker not yet stopped, the longest title language). Not pixel-exact AWTK.

  preview_podcasts_dialog.py WORKDIR OUT.png [--lang CODE]

WORKDIR is a built tree (work/mod-release). The card, the texts and the bar are ui/m1plus_podcasts.bin's own widgets (positions, sizes, colours and fonts read from the tree), the glass
stretched as patch3_x does, as preview_icons.playlists_grid draws the Playlists menu; the rows behind are stand-ins.
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preview_icons as PI

SHOWS = [('Alpha Show', 'Up to date · 1h ago'), ('The Headlines', 'Never refreshed'), ('WSJ Minute Briefing', '3 new · Just now'), ('Sub Two', 'No Wi-Fi')]


def rgba(c): return PI.card_rgba(c)


def page(s):
    im = Image.new('RGBA', (320, 450), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    s.text(im, 36, 25, 'Feeds', 22)
    s.text(im, 16, 50 + 32, 'Refresh All', 21, (0x0A, 0x84, 0xFF))
    for i, (name, sub) in enumerate(SHOWS):
        y = 50 + (i + 1) * 64
        d.ellipse((12, y + 6, 12 + 52, y + 6 + 52), fill=(0x30, 0x30, 0x34))
        s.text(im, 74, y + 20, name, 21)
        s.text(im, 74, y + 44, sub, 18, (0xAA, 0xAA, 0xAA))
        d.rectangle((74, y + 63, 319, y + 63), fill=(0x22, 0x22, 0x22))
    return im


def dialog(s, name, count, frac, cancelling=False, cancel_pressed=False):
    """The page behind the scrim and the card: name (ellipsised in the 240 px), count line, the bar filled to frac."""
    root = __import__('awtk_ui').parse(open(os.path.join(s.tree, PI.RAW, 'ui', 'm1plus_podcasts.bin'), 'rb').read())
    im = page(s)
    im.alpha_composite(Image.new('RGBA', im.size, rgba(root.find('pod_pd_scrim').get('style:normal:bg_color'))))
    card = root.find('pod_pd_card')
    g = s.img(card.get('style:normal:bg_image')); t = g.width // 3
    glass = Image.new('RGBA', (card.w, g.height))
    glass.paste(g.crop((0, 0, t, g.height)), (0, 0)); glass.paste(g.crop((g.width - t, 0, g.width, g.height)), (card.w - t, 0))
    glass.paste(g.crop((t, 0, g.width - t, g.height)).resize((card.w - 2 * t, g.height)), (t, 0))
    im.alpha_composite(glass, (card.x, card.y))
    kids = {c.name: c for c in card.children}
    def put(widget, text, rgb_prop='style:normal:text_color'):
        w = kids[widget]; px = int(w.get('style:normal:font_size'))
        text = s.clip(text, px, w.w)
        s.text(im, card.x + w.x + w.w / 2, card.y + w.y + w.h / 2, text, px, rgba(w.get(rgb_prop))[:3], 'm')
    put('pod_pd_title', s.shown(kids['pod_pd_title']))
    put('pod_pd_name', name)
    tr, fl = kids['pod_pd_track'], kids['pod_pd_fill']
    def bar(w, rgb):
        layer = Image.new('RGBA', (w, tr.h), rgb)
        mask = Image.new('L', (w * 4, tr.h * 4), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, w * 4 - 1, tr.h * 4 - 1), radius=tr.h * 2, fill=255)
        layer.putalpha(mask.resize((w, tr.h), Image.LANCZOS).point(lambda v, a=rgb[3]: v * a // 255))
        im.alpha_composite(layer, (card.x + tr.x, card.y + tr.y))
    bar(tr.w, rgba(tr.get('style:normal:bg_color')))
    bar(max(1, int(tr.w * frac)), rgba(fl.get('style:normal:bg_color')))
    put('pod_pd_count', count)
    c = kids['pod_pd_cancel']
    cy = card.y + c.y
    if cancel_pressed: im.alpha_composite(Image.new('RGBA', (c.w, c.h), rgba(c.get('style:pressed:bg_color'))), (card.x, cy))
    im.alpha_composite(Image.new('RGBA', (c.w, 1), rgba(c.get('style:normal:border_color'))), (card.x, cy))
    px = int(c.get('style:normal:font_size')); rgb = rgba(c.get('style:normal:text_color'))[:3] if not cancelling else (0x66, 0x66, 0x66)
    s.text(im, card.x + c.w / 2, cy + c.h / 2, s.shown(c), px, rgb, 'm')
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir'); ap.add_argument('out'); ap.add_argument('--lang', default='en_US')
    a = ap.parse_args()
    s = PI.Side(a.workdir, True, a.lang)
    fmt = lambda a_, b_: s.strings.get('%d of %d', '%d of %d').replace('%d', str(a_), 1).replace('%d', str(b_), 1)
    panels = [('Show 2 of 4, a third in', dialog(s, 'The Headlines', fmt(2, 4), (1000 + 330) / 4000)),
              ('Cancel pressed', dialog(s, 'WSJ Minute Briefing', fmt(3, 4), (2000 + 500) / 4000, cancel_pressed=True)),
              ('Cancelling, a long name', dialog(s, 'All-In with Chamath, Jason, Sacks & Friedberg', s.strings.get('Cancelling…', 'Cancelling…'), (2000 + 900) / 4000, cancelling=True))]
    pad, lab = 12, 20
    sheet = Image.new('RGB', (len(panels) * (320 + pad) + pad, 450 + lab + 2 * pad), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sheet)
    for i, (title, im) in enumerate(panels):
        x = pad + i * (320 + pad)
        d.text((x, pad), title, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, pad + lab))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    PI.save_compact(sheet, a.out)
    print('wrote', a.out, sheet.size)


if __name__ == '__main__': main()
