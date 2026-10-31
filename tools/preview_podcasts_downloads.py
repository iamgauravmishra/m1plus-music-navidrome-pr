#!/usr/bin/env python3
"""Approximate PIL mock-up of the Podcasts page's Feeds, Show and Downloads levels (patch/podcasts.c, docs/modules/podcasts.md "Downloads", "The ... menu"): open, the Downloads level, a Show level without the dot column (an unplayed, a played and two episodes that are not on the card), the Show level's "..." menu, and select mode (the rows
slid right by the mark column; on the Downloads level too). Not pixel-exact AWTK.

  preview_podcasts_downloads.py WORKDIR OUT.png [--lang CODE]

WORKDIR is a built tree (work/mod-release). Row geometry, the marks, the bar, the navbar pieces are the payload's constants
and the asset's; the covers and names are stand-ins.
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preview_icons as PI
import preview_songs as PS

O = PI.offsets()
W, H, NAV = 320, 450, 50
ROW, GREY, DIM = O['PC_ROW_H'], (0xAA, 0xAA, 0xAA), (0x8E, 0x8E, 0x93)
SEL, MARK, BAR_H = O['SG_SEL_COL'], O['SG_MARK'], O['SG_BAR_H']
TEXT_X, TEXT_W = 16, 292     # patch/podcasts.c PG_TEXT_X / PG_TEXT_W: an episode's texts, no cover, no dot


def tr(s, key): return s.strings.get(key, key)


def navbar(s, im, title, cap=None, select=None):
    """The glass navbar: Back (or the x), the title (or N Selected), the capsule's left cap (the "..." button) and Now Playing (the right cap with a cap, else the disc)."""
    d = ImageDraw.Draw(im); d.rectangle((0, 0, W - 1, NAV - 1), fill=(0, 0, 0))
    if select is not None:
        PS.glass(s, im, 'ah_nav_close', 7, 44)
        s.text(im, O['NAV_TITLE_X'], 25, tr(s, '%d Selected').replace('%d', str(select)), PI.title_px(s.tree))
        sa = tr(s, 'Select All'); s.text(im, O['SG_SELALL_X'] + 104 - 8 - s.font.width(sa, 18), 25, sa, 18)
        return
    PS.glass(s, im, 'ah_nav_back', 7, 44)
    s.text(im, O['NAV_TITLE_X'], 25, s.clip(title, PI.title_px(s.tree), O['NAV_VIEW_X'] - O['NAV_TITLE_X']), PI.title_px(s.tree))
    if cap: PS.glass(s, im, cap, O['NAV_VIEW_X'])
    PS.glass(s, im, 'ah_nav_play' if cap else 'ah_nav_np', 260, 60)


def bar(s, im):
    d = ImageDraw.Draw(im); d.rectangle((0, H - BAR_H, W - 1, H - 1), fill=(0, 0, 0)); d.rectangle((0, H - BAR_H, W - 1, H - BAR_H), fill=PS.HAIR)
    PS.pill(s, im, O['SG_PILL_X0'], H - BAR_H + (BAR_H - O['SG_PILL_H']) // 2, tr(s, 'Delete'), s.img('sg_trash'), w=O['PL_BAR_PILL_W'])


def list_row(s, im, r, name, sub, rgb, shift=0, mark=None):
    y = NAV + r * ROW
    d = ImageDraw.Draw(im)
    d.rectangle((O['LIST_TEXT_X'] + shift, y + ROW - 1, W - 1, y + ROW - 1), fill=PS.HAIR)
    im.alpha_composite(PI.sample_cover(rgb, O['LIST_ART']), (O['LIST_ART_X'] + shift, y + O['LIST_ART_Y']))
    room = O['LIST_TEXT_W'] - shift
    s.text(im, O['LIST_TEXT_X'] + shift, y + O['LIST_TITLE_Y'] + O['LIST_TITLE_H'] / 2, s.clip(name, 21, room), 21)
    s.text(im, O['LIST_TEXT_X'] + shift, y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] / 2, s.clip(sub, 18, room), 18, GREY)
    if mark is not None: im.alpha_composite(s.img('selected' if mark else 'unselect'), (O['LIST_ART_X'] + (shift - 6 - MARK) // 2, y + (ROW - MARK) // 2))


def feeds(s):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255)); navbar(s, im, tr(s, 'Feeds'))
    rows = [(tr(s, 'Refresh All'), '1h ago', None), (tr(s, 'Downloads') + ' (3)', tr(s, 'Downloading') + ' 42%', None), (tr(s, 'Import shows'), 'Podcasts/subscriptions.txt', None),
            ('All-In with Chamath, Jason, Sacks & Friedberg', 'Up to date · 1h ago', (0x8E, 0x44, 0x44)), ('The Headlines', '3 new · Just now', (0x44, 0x66, 0x99)), ('WSJ Minute Briefing', 'Up to date · 2d ago', (0x55, 0x88, 0x66))]
    for r, (name, sub, rgb) in enumerate(rows):
        y = NAV + r * ROW; d = ImageDraw.Draw(im)
        x = O['LIST_TEXT_X'] if rgb else 16
        d.rectangle((x, y + ROW - 1, W - 1, y + ROW - 1), fill=PS.HAIR)
        if rgb: im.alpha_composite(PI.sample_cover(rgb, O['LIST_ART']), (O['LIST_ART_X'], y + O['LIST_ART_Y']))
        s.text(im, x, y + O['LIST_TITLE_Y'] + O['LIST_TITLE_H'] / 2, s.clip(name, 21, W - 12 - x), 21, (0x0A, 0x84, 0xFF) if name in (tr(s, 'Refresh All'), tr(s, 'Import shows')) else (255, 255, 255))
        s.text(im, x, y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] / 2, s.clip(sub, 18, W - 12 - x), 18, GREY)
    return im


def downloads(s, select=None):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    if select is None: navbar(s, im, tr(s, 'Downloads'), 'pod_nav_selectl')
    else: navbar(s, im, '', None, len(select))
    rows = [('Chamath, Jason: The Real Reason Markets Moved', tr(s, 'Downloading') + ' 42%', (0x8E, 0x44, 0x44), False), ('Amazon, Intel Earnings Add Fuel', tr(s, 'Waiting'), (0x55, 0x88, 0x66), True),
            ('Intensifying Tech Selloff Drags Down Nasdaq', tr(s, 'Failed') + ': ' + tr(s, 'Card is full'), (0x55, 0x88, 0x66), True), ('The Headlines for Friday', tr(s, 'Paused'), (0x44, 0x66, 0x99), True)]
    shift = SEL if select is not None else 0
    for r, (name, sub, rgb, can) in enumerate(rows):
        list_row(s, im, r, name, sub, rgb, shift, (r in select) if select is not None and can else None)
    if select is not None: bar(s, im)
    return im


def show(s, select=None):
    """A Show level: a header, then an unplayed episode (bright title), a played one and two that are not on the card (grey; the size ends the line) at x 16, or 46 in select mode."""
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    if select is None: navbar(s, im, 'All-In with Chamath...', 'pod_nav_selectl')
    else: navbar(s, im, '', None, len(select))
    d = ImageDraw.Draw(im)
    im.alpha_composite(PI.sample_cover((0x8E, 0x44, 0x44), 96), (16, NAV + 16))
    s.text(im, 124, NAV + 22 + 14, 'All-In with Chamath...', 21); s.text(im, 124, NAV + 50 + 9, '4 episodes', 18, GREY)
    y0 = NAV + O['PC_HDR_H']
    rows = [('Ep 5: Markets, Moved', '1h ago · 61 min', 'bright', 0), ('Ep 4: The Real Reason', '3d ago · Played', 'dim', 1), ('Ep 3: Not downloaded yet', '4d ago · 58 min · 48 MB', 'dim', None), ('Ep 2: Not downloaded', '5d ago · 41 min · 30 MB', 'dim', None)]
    sx = SEL if select is not None else 0
    for r, (name, sub, look, mk) in enumerate(rows):
        y = y0 + r * ROW
        if y + ROW > H - (BAR_H if select is not None else 0): break
        d.rectangle((TEXT_X + sx, y + ROW - 1, W - 1, y + ROW - 1), fill=PS.HAIR)
        if select is not None and mk is not None: im.alpha_composite(s.img('selected' if mk in select else 'unselect'), (TEXT_X + (SEL - 6 - MARK) // 2, y + (ROW - MARK) // 2))
        s.text(im, TEXT_X + sx, y + O['LIST_TITLE_Y'] + O['LIST_TITLE_H'] / 2, s.clip(name, 21, TEXT_W - sx), 21, (255, 255, 255) if look == 'bright' else DIM)
        s.text(im, TEXT_X + sx, y + O['LIST_SUB_Y'] + O['LIST_SUB_H'] / 2, s.clip(sub, 18, TEXT_W - sx), 18, GREY)
    if select is not None: bar(s, im)
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir'); ap.add_argument('out'); ap.add_argument('--lang', default='en_US')
    a = ap.parse_args()
    s = PI.Side(a.workdir, True, a.lang)
    panels = [('Feeds', feeds(s)), ('Downloads', downloads(s)), ('Downloads: select mode', downloads(s, select={1, 3})), ('A show: no dot column', show(s)), ('A show: select mode (rows slide)', show(s, select={0}))]
    pad, lab, per = 12, 20, 3
    rows_n = (len(panels) + per - 1) // per
    sheet = Image.new('RGB', (per * (W + pad) + pad, rows_n * (H + lab + pad) + pad), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sheet)
    for i, (title, im) in enumerate(panels):
        x, y = pad + (i % per) * (W + pad), pad + (i // per) * (H + lab + pad)
        d.text((x, y), title, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, y + lab))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    PI.save_compact(sheet, a.out)
    print('wrote', a.out, sheet.size)


if __name__ == '__main__': main()
