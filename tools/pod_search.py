#!/usr/bin/env python3
"""The Search page's layout model (patch/search.c, docs/modules/search.md): the Apple Music search screen on a 320 x 450 window.

The numbers are the #defines of patch/search.h (parsed here, so there is one copy): tools/pod_ui.py builds ui/m1plus_search.bin from them, tools/preview/preview_search.py draws the design from them
and test/pod/search.py checks the built tree and the payload against them. Colours are neutral: white and grey, no accent; the selected chip is a light grey pill with dark text.
"""
import os
import cdefs

HERE = os.path.dirname(os.path.abspath(__file__))
D = cdefs.defines(os.path.join(os.path.dirname(HERE), 'patch', 'search.h'))

globals().update(D)   # the layout numbers as module attributes (PS.SE_ROW_H ...)
from pod_roles import INK_RGB, SUB_RGB, CHEV_RGB, THUMB_RGB, RAISED_RGB, SURFACE_RGB, PLACEHOLDER_RGB   # noqa: F401 (SUB_RGB, CHEV_RGB: the rows' and the chevron's, read as PS.*)

FIELD_RGB, FIELD_INK, FIELD_HINT = SURFACE_RGB, INK_RGB, PLACEHOLDER_RGB   # the field is the keyboard's (tools/pod_keyboard.py KB_BG, KB_INK, KB_GREY)
FIELD_PX = 18
CHIP_RGB, CHIP_INK, CHIP_ON_INK, CHIP_ON_RGB = INK_RGB, INK_RGB, SURFACE_RGB, '#E5E5EA'   # the selected chip: a light grey pill with dark text
SEP_RGB = RAISED_RGB                                                                         # the line under the chips
TITLE_RGB, HAIR_RGB, PRESS_RGB = INK_RGB, '#222222', '#333334'       # the rows (the library lists' own: LIST_HAIR, LIST_PRESS of offsets.inc)
CHIPS = ('Top Results', 'Artists', 'Albums', 'Songs', 'Playlists')
KINDS = ('Artist', 'Album', 'Song', 'Playlist')


def chip_layout(widths):
    """[(x, w)] of the chips for the text widths `widths` (px): each as wide as its text plus the padding either side, D['SE_CHIP_GAP'] apart from D['SE_CHIP_X']; the row scrolls when the end passes 320."""
    out, x = [], D['SE_CHIP_X']
    for tw in widths:
        w = tw + 2 * D['SE_CHIP_PAD']
        out.append((x, w))
        x += w + D['SE_CHIP_GAP']
    return out


def chips_end(layout):
    """The scrollable width of the chip row: the last chip's right edge and SE_CHIP_X of air."""
    x, w = layout[-1]
    return x + w + D['SE_CHIP_X']


def row_y(i): return i * D['SE_ROW_H']


def content_h(rows, keyboard):
    """The content view's height: the rows and the air (SE_BOTTOM), or the pad's height while the keyboard is up (the list scrolls clear of it); at least the list's."""
    return max(rows * D['SE_ROW_H'] + (180 if keyboard else D['SE_BOTTOM']), D['SE_LIST_H'])
