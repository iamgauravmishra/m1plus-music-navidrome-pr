#!/usr/bin/env python3
"""The Settings pages' layout model (tools/pod_pages.py cards pages, docs/modules/settings.md "Cards"): iOS-style grouped cards in the stock list.

tools/pod_ui.py builds the widget trees from these numbers, tools/preview_settings.py draws the design from them and test/pod/settings.py checks the built
trees against them (with demo's own layouter), so the mock, the tests and the device share one set of numbers.

The stock list_view layouter ignores a child's y: it stacks every visible child of the scroll_view in child order, from y 0, setting x (0) and the width and summing the heights
into virtual_h. So the page is a column of full-width items, each as high as the model says: a CM spacer, then rows (ROW_H), headers (HDR_H), notes (NOTE_H) and gaps (GAP_H) in
the order of the page's layout, then an END_H spacer. There are no card views: a card is drawn by its rows, each of which has a picture as its background (single / top / middle /
bottom piece, ROW_W x ROW_H, tools/mod_icons.py card_piece) with the card's x CM .. CM + CARD_W, its corners (CARD_R, only where the piece needs them) and its fill baked in and
transparent outside (the pressed pieces are lit). A hairline (CARD_HAIR_RGB) is a child of the row from the label to the card's right edge, on every row but a card's last. Coordinates
below are row relative (x 0 is the list's left edge, so a card starts at CM). The 20 px glyph (GLYPH_PX in a 24 px image) is centred in a 20 px column PAD from the card's edge, the label
starts LABEL_GAP after the column (a picker row has no glyph: PAD). On the right, the ink of the chevron, the switch and the check ends PAD from the card's edge; a value is grey, 8 px
left of the chevron. A header is secondary grey and a note smaller grey text; their labels start at HDR_X, the left of the glyph column's ink.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pod_pages

ROW_H = 52                   # tools/pod_ui.py ROW_H
CM, CARD_W, CARD_R = 10, 300, 12
CARD_RGB, CARD_HAIR_RGB, PRESSED_RGB = '#1C1C1C', '#333333', '#2C2C2E'   # PRESSED_RGB: a tapped row (the Songs sort card's pressed grey)
PAD, GLYPH_PX, ICON_PX, LABEL_GAP = 14, 20, 24, 14
HDR_H, HDR_PX, HDR_LABEL_Y, HDR_LABEL_H = 40, 18, 14, 22
NOTE_H, NOTE_PX, NOTE_LABEL_Y, NOTE_LABEL_H = 34, 15, 6, 22
GAP_H, END_H = 20, 10        # the space between two cards without a header or note; the list's bottom padding
GREY = '#AAAAAA'             # headers, notes and values
VALUE_PX, VALUE_GAP, VALUE_W, VALUE_MAX, VALUE_LABEL_GAP = 18, 8, 100, 140, 6   # a value: its size, the gap to the chevron, its box at rest (right aligned), the most the payload gives it (it takes the room its text needs: patch/m1plus.c value_fit), the gap to the label
INFO_PX, INFO_W, INFO_MAX = 16, 100, 190   # an About row's value: 16 px grey, its box at rest (right aligned, ink at RIGHT), the most the payload gives it (it takes the room its text needs; the label gets the rest)
SWITCH_W, SWITCH_H = 57, 28  # the stock switch images sset_on / sset_off (their ink fills the image)
CHEV_W, CHEV_H, CHEV_RGB, CHEV_STROKE = 9, 15, (0x77,) * 3, 2   # the chevron image pod_chev: Lucide chevron-right fitted to 9 x 15
CHECK_PX = 20                # the picker's check image pod_check
LIST_W = 310                 # the items' width in the asset (the scroll_view's; the layouter sets it)
ROW_W = 320                  # the pieces' width: the list_view's (the layouter gives a child that width, or the scroll_view's 310: the piece is drawn from the left edge either way)
ICON_X = CM + PAD + GLYPH_PX // 2 - ICON_PX // 2      # the 24 px image of a row's glyph: row relative
ICON_Y = (ROW_H - ICON_PX) // 2
TEXT_X = CM + PAD + GLYPH_PX + LABEL_GAP              # a row's label with a glyph; CM + PAD without
RIGHT = CM + CARD_W - PAD                             # the right ink edge of the chevron, the switch and the check, row relative
HDR_X = CM + PAD                                      # a header's and a note's label: the left of the row glyphs' ink
HDR_W = CARD_W - PAD - 4   # the text starts at the card's text; the label runs to 4 px short of the scroll bar strip (the hscroll_label insets its text 2 px each side)


TOP, END = 'top', 'end'      # the spacers the page starts and ends with (CM and END_H high)


def item_h(item):
    """The height of a layout item: Hdr, Note, GAP, Row or TOP / END."""
    return (HDR_H if isinstance(item, pod_pages.Hdr) else NOTE_H if isinstance(item, pod_pages.Note) else GAP_H if item is pod_pages.GAP
            else CM if item == TOP else END_H if item == END else ROW_H)


def layout(items):
    """(placed, end): placed = [(item, y)] for [TOP] + items + [END], the stacked column the list_view layouter makes; end = virtual_h."""
    y, placed = 0, []
    for it in [TOP] + list(items) + [END]:
        placed.append((it, y))
        y += item_h(it)
    return placed, y


def pieces(items):
    """The background piece of each row, in row order: 'single', 'top', 'mid' or 'bot' (a card is a run of rows between the other items)."""
    kinds = [isinstance(it, pod_pages.Row) for it in items]
    rows = [i for i, k in enumerate(kinds) if k]
    out = []
    for i in rows:
        up = i > 0 and kinds[i - 1]
        down = i + 1 < len(kinds) and kinds[i + 1]
        out.append('mid' if up and down else 'bot' if up else 'top' if down else 'single')
    return out


def piece_images(piece):
    """(normal, pressed) image names of a piece: pod_cd_<piece>, pod_cd_<piece>_down."""
    return f'pod_cd_{piece}', f'pod_cd_{piece}_down'


_ink = {}


def ink(name):
    """(left, top, right, bottom) of the ink of an image of ours inside its canvas: the chevron and the check, drawn by tools/mod_icons.py."""
    if name not in _ink:
        import mod_icons as M
        im = {'chev': lambda: M.glyph_fit('chevron-right', CHEV_W, CHEV_H, CHEV_RGB, 0, CHEV_STROKE), 'check': lambda: M.glyph_fit('check', CHECK_PX, CHECK_PX)}[name]()
        _ink[name] = im.getchannel('A').getbbox()
    return _ink[name]


def accessory(kind):
    """(x, y, w, h) of a row's right accessory, card relative, so that its ink ends at RIGHT and is centred in the row: 'chevron', 'check' or 'switch'."""
    if kind == 'switch': return RIGHT - SWITCH_W, (ROW_H - SWITCH_H) // 2, SWITCH_W, SWITCH_H
    name, w, h = ('chev', CHEV_W, CHEV_H) if kind == 'chevron' else ('check', CHECK_PX, CHECK_PX)
    b = ink(name)
    return RIGHT - b[2], (ROW_H - (b[3] - b[1])) // 2 - b[1], w, h


def chevron_left():
    """The left edge of the chevron's ink, card relative."""
    b = ink('chev')
    return RIGHT - (b[2] - b[0])


def label_box(kind, has_icon):
    """(x, w) of a row's label, card relative: from TEXT_X (PAD without a glyph) to the accessory, the value's box or the right ink edge."""
    x = TEXT_X if has_icon else CM + PAD
    if kind == 'info': return x, info_box()[0] - VALUE_LABEL_GAP - x
    if kind in ('link', 'value'): right = chevron_left() - VALUE_GAP
    elif kind == 'switch': right = accessory('switch')[0] - 8
    elif kind == 'check': right = accessory('check')[0] - 8
    else: right = RIGHT
    if kind == 'value': right = value_box()[0] - VALUE_LABEL_GAP
    return x, right - x


def info_box():
    """(x, w) of an About row's value box (right aligned text, no chevron): it ends at the right ink edge."""
    return RIGHT - INFO_W, INFO_W


def value_box():
    """(x, w) of a value's box (right aligned text), card relative: it ends VALUE_GAP before the chevron's ink."""
    right = chevron_left() - VALUE_GAP
    return right - VALUE_W, VALUE_W
