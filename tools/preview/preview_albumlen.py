#!/usr/bin/env python3
"""Previews of the album footer (docs/modules/album-page.md "Album length"): out/preview/album-footer.png is the page scrolled to its end in English, Chinese and Japanese (the count line), then the no-footer case
(rows and footer at the payload's own numbers, patch/offsets.inc AH_* AB_*), out/preview/album-length.png the footer line in every language (a typical album, one track,
the widest case: 999 tracks, 24 hours, 59 minutes) against the room it has, drawn with the built font and the tree's strings tables. Approximate, not AWTK; sample data.

  uv run python -I tools/preview/preview_albumlen.py WORKDIR [OUT.png]     (WORKDIR: a built tree, e.g. out/dev/<tag>/tree; default out/preview/album-length.png)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw
import preview_icons as PI, pod_i18n

O = PI.offsets()
GREY, RULE, FOOT = (0x9C, 0x9C, 0x9C), (0x30, 0x30, 0x30), (0xAA, 0xAA, 0xAA)
TEXT_W = 320 - O['AB_NUM_X'] - O['AB_FOOT_R']   # the footer's room from the number column's left edge


def duration(b, sec):
    """dur_text (patch/durations.c): minutes rounded, at least one; hours and minutes by their own key per language."""
    m = max(1, (sec + 30) // 60)
    h, m = divmod(m, 60)
    one = lambda n, k1, k2: b[k1 if n == 1 else k2].replace('%d', str(n))
    if not h: return one(m, '%d minute', '%d minutes')
    if not m: return one(h, '%d hour', '%d hours')
    key = ('%d hour' if h == 1 else '%d hours') + ', ' + ('%d minute' if m == 1 else '%d minutes')
    return b[key].replace('%d', str(h), 1).replace('%d', str(m), 1)


def footer(b, n, sec):
    return b['%d track, %s' if n == 1 else '%d tracks, %s'].replace('%d', str(n)).replace('%s', duration(b, sec))


TRACKS = ['So What', 'Freddie Freeloader', 'Blue in Green', 'All Blues', 'Flamenco Sketches', 'Flamenco Sketches (Alt)', 'So What (Alt)', 'Blue in Green (Alt)']


def page(s, n=8, sec=2745, scroll=None, playing=2):
    """The album page's list scrolled to its end (patch/albumpage.c: rows from AH_HDR_H, LIST_ROW_H high; the footer AB_FOOT_GAP under the last one at x AB_NUM_X: the
    count with the duration, only when known, AB_FOOT_PAD under it), under the 30 px status bar."""
    row, hdr, win = O['LIST_ROW_H'], O['AH_HDR_H'], O['AH_WIN_H']
    lines = [footer(s.strings, n, sec)] if sec else []
    foot_h = O['AB_FOOT_GAP'] + len(lines) * O['AB_FOOT_TEXT_H'] + O['AB_FOOT_PAD'] if lines else 0
    content = hdr + n * row + foot_h
    off = max(0, content - win) if scroll is None else scroll
    im = Image.new('RGBA', (320, 30 + win), (0x24, 0x24, 0x28, 255))
    d = ImageDraw.Draw(im)
    for i in range(n):
        y = 30 + hdr + i * row - off
        if y + row < 30 or y > 30 + win: continue
        d.rectangle((0, y + row - 1, 309, y + row - 1), fill=(0x3A, 0x3A, 0x3E))
        if i == playing:   # the playing track: the wave (ah_wave) in place of the number, the title stays white
            im.alpha_composite(s.img('ah_wave'), (O['AB_NUM_X'] + O['ROW_NUM_W'] - O['AB_WAVE'], y + O['AB_WAVE_Y']))
        else:
            s.text(im, O['AB_NUM_X'] + O['ROW_NUM_W'], y + O['AB_TEXT_Y'] + O['AB_TEXT_H'] / 2, str(i + 1), 21, (0xAA, 0xAA, 0xAA), 'r')
        s.text(im, O['AB_NUM_X'] + O['ROW_NUM_W'] + O['AB_NUM_GAP'], y + O['AB_TEXT_Y'] + O['AB_TEXT_H'] / 2, TRACKS[i % len(TRACKS)], 21)
    fy = 30 + hdr + n * row + O['AB_FOOT_GAP'] - off
    for k, line in enumerate(lines):
        s.text(im, O['AB_NUM_X'], fy + k * O['AB_FOOT_TEXT_H'] + O['AB_FOOT_TEXT_H'] / 2, line, O['AB_FOOT_PX'], FOOT)
    d.rectangle((0, 0, 319, 29), fill=(0, 0, 0))
    return im


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    tree = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(HERE)), 'out', 'preview', 'album-length.png')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    samples = [(2002, 13, 49 * 60 + 12, 'typical'), (1959, 1, 90, 'one track'), (2999, 999, 24 * 3600 + 59 * 60, 'widest')]
    im = Image.new('RGBA', (3 * 330, 13 * 60 + 10), (0, 0, 0, 255))
    d = ImageDraw.Draw(im)
    worst = 0
    for i, loc in enumerate(pod_i18n.LOCALES):
        s = PI.Side(tree, True, loc)
        b = s.strings
        for j, (year, n, sec, what) in enumerate(samples):
            x0, y0 = j * 330 + 5, 5 + i * 60
            line = footer(b, n, sec)
            w = s.font.width(line, 15)
            worst = max(worst, w)
            s.text(im, x0 + O['AB_NUM_X'], y0 + 16, line, 15, FOOT)
            d.rectangle((x0 + O['AB_NUM_X'], y0 + 30, x0 + O['AB_NUM_X'] + TEXT_W - 1, y0 + 30), fill=RULE)
            d.rectangle((x0 + O['AB_NUM_X'], y0 + 30, x0 + O['AB_NUM_X'] + min(w, TEXT_W) - 1, y0 + 30), fill=(0x60, 0x60, 0x60) if w <= TEXT_W else (0xC0, 0x30, 0x30))
            s.text(im, x0, y0 + 42, f'{loc}  {what}  {w} px', 11, (0x60, 0x60, 0x60))
    im.convert('RGB').save(out)
    pg = os.path.join(os.path.dirname(out), 'album-footer.png')
    sheet = Image.new('RGBA', (3 * 330, 2 * 490), (0, 0, 0, 255))
    cases = [('en_US', 13, 3480), ('zh_CN', 13, 3480), ('ja_JP', 13, 5040), ('en_US', 8, 0)]   # the count line in three languages, and no footer (duration unknown)
    for j, (loc, n, sec) in enumerate(cases):
        sheet.alpha_composite(page(PI.Side(tree, True, loc), n, sec), ((j % 3) * 330 + 5, (j // 3) * 490 + 5))
    sheet.convert('RGB').save(pg)
    print(pg)
    print(f'{out}: widest line {worst} px of {TEXT_W}')


if __name__ == '__main__': main()
