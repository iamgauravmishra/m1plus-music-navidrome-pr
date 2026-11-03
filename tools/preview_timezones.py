#!/usr/bin/env python3
"""The time zone picker's rows, stock 64 px / 21 px text beside the build's 48 px / 18 px (docs/modules/timezones.md). PIL mock-up of the
auto-time-off page from a tree's own styles/default.bin; approximate, not AWTK.

Usage: preview_timezones.py WORKDIR OUT.png
"""
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import preview_theme as T, timezones as TZ

def page(t, rows_h, px, label_y, tick_y, title):
    im = Image.new('RGBA', (T.W, T.H), (0, 0, 0, 255)); dr = ImageDraw.Draw(im)
    T.status_bar(im, t); T.navbar(im, t, 'Date & Time')
    style = f'srlabel_leftwhite{px}_style'; col = t.style('hscroll_label', style, 'normal', 'text_color')
    y = T.BAR + T.NAV
    T.row_bg(dr, t, 'list_item', 'list_item_style', y, 64); T.text(dr, t, (12, y + 32), 'Auto time', 21, col); y += 64
    T.row_bg(dr, t, 'list_item', 'list_item_style', y, 46); T.text(dr, t, (12, y + 23), 'Time zone', 16, (0x8c, 0x8c, 0x8c, 255)); y += 46
    for k, i in enumerate(TZ.ORDER[:20]):
        if y + rows_h > T.H: break
        T.row_bg(dr, t, 'list_item', 'list_item_style', y, rows_h, pressed=(k == 3))
        T.text(dr, t, (12, y + label_y + 10.5), TZ.TIMEZONES[i][0], px, col)
        if i == TZ.DEFAULT: T.paste(im, t.img('check_checked_n'), 282, y + tick_y)
        y += rows_h
    T.text(dr, t, (160, 6), title, 12, (255, 255, 255, 255), 'mm')
    return im

def main(work, out):
    t = T.Tree(work)
    a = page(t, 64, 21, 20, 17, 'stock'); b = page(t, TZ.ROW_H, 18, TZ.LABEL_Y_NEW, TZ.TICK_Y_NEW, 'build')
    im = Image.new('RGBA', (T.W * 2 + 10, T.H), (40, 40, 40, 255)); im.paste(a, (0, 0)); im.paste(b, (T.W + 10, 0)); im.save(out)

if __name__ == '__main__':
    main(*sys.argv[1:3])
