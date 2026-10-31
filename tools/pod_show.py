#!/usr/bin/env python3
"""The Podcasts Show page's layout model (patch/podcasts.c, docs/modules/podcasts.md "The Show page"): the PS_* numbers of patch/offsets.inc, the line breaking of tools/pod_wrap.py
and the glyph advances of the font (tools/awtk_text.py: the glyph's width and 1 px each). test/pod/pcshow.py checks the payload against it and tools/preview_podcasts_revamp.py draws
from it, so the preview, the tests and the device share one set of numbers.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pod_ui, pod_wrap
from awtk_text import Ttf, StbText

O = pod_ui.OFFSETS
PX = {name: px for name, px, _, _ in pod_ui.PS_STYLES}          # the text styles' sizes: label_ps_name 22 ...
SEP = ' · '                                                 # the " · " between the two halves of a line


class Font:
    """Widths in the font of a tree (default.ttf), per size."""
    def __init__(self, path):
        self.ttf, self._st = Ttf(path), {}

    def width(self, text, px):
        st = self._st.get(px)
        if st is None: st = self._st[px] = StbText(self.ttf, px)
        return round(st.layout(text)[1]) if text else 0


def lines(font, text, style, room, maxl):
    """The lines of text in a style label (label_ps_*), room px wide, at most maxl."""
    return pod_wrap.wrap_font(font, text, PX[style], room, maxl) if text else []


def meta(category, author):
    return SEP.join(p for p in (category, author) if p)


def header(font, title, desc='', category='', author='', has_latest=True):
    """The Show header's layout (patch/podcasts.c pg_hdr_make): the wrapped texts and the blocks' tops, content y from the list's top."""
    o, h = O, {}
    y = o['PS_ART'] + o['PS_NAME_GAP']
    h['name'] = lines(font, title, 'label_ps_name', o['PS_NAME_W'], o['PS_NAME_LINES'])
    h['y_name'] = y
    y += len(h['name']) * o['PS_NAME_PITCH']
    h['collapse'] = y - o['PS_COLLAPSE_BACK']
    gap = o['PS_LATEST_GAP']
    h['has_latest'] = has_latest
    if has_latest:
        y += o['PS_LATEST_GAP']; h['y_latest'] = y; y += o['PS_LATEST_H']; gap = o['PS_DESC_GAP']
    h['desc'] = lines(font, desc, 'label_ps_sec', o['PS_DESC_W'], o['PS_DESC_LINES'])
    if h['desc']:
        y += gap; h['y_desc'] = y; y += len(h['desc']) * o['PS_DESC_PITCH']; gap = o['PS_META_GAP']
    h['meta'] = lines(font, meta(category, author), 'label_ps_meta', o['PS_DESC_W'], 1)
    if h['meta']:
        y += gap; h['y_meta'] = y; y += o['PS_META_PITCH']
    y += o['PS_HEAD_GAP']
    h['y_head'] = y
    h['h'] = y + o['PS_HEAD_H']
    return h


def pill_width(font, label):
    """A cell's state pill: pad, the 16 px glyph, gap, the label, pad."""
    o = O
    return o['PS_PILL_PADL'] + o['PA_G_PX'] + o['PS_PILL_GAP'] + font.width(label, PX['label_ps_pill']) + o['PS_PILL_PADR']


def latest_label(font, label, white):
    """The Latest Episode pill's label as the payload keeps it: cut with an ellipsis to fit PS_LATEST_MAX."""
    o = O
    style = 'label_ps_latest' if white else 'label_ps_latestw'
    room = o['PS_LATEST_MAX'] - o['PS_LATEST_PADL'] - o['PS_LATEST_GLYPH'] - o['PS_LATEST_GAPG'] - o['PS_LATEST_PADR']
    got = lines(font, label, style, room, 1)
    return got[0] if got else ''


def latest_width(font, label, white):
    o = O
    return o['PS_LATEST_PADL'] + o['PS_LATEST_GLYPH'] + o['PS_LATEST_GAPG'] + font.width(latest_label(font, label, white), PX['label_ps_latest' if white else 'label_ps_latestw']) + o['PS_LATEST_PADR']


def cell(font, title, desc, sx=0):
    """A cell's wrapped title and description (two lines each at most, PS_CELL_W less the select column sx)."""
    room = O['PS_CELL_W'] - sx
    return lines(font, title, 'label_ps_ctitle', room, 2), lines(font, desc, 'label_ps_cdesc', room, 2)


def content_height(h_hdr, n, select=False):
    """The content's height: the header, n cells and the air under the last (PG_BOTTOM 20), and the select bar's room."""
    return h_hdr + n * O['PS_CELL_H'] + 20 + (O['SG_BAR_H'] if select and n else 0)


def font_path(work):
    return os.path.join(work, 'rootfs', 'release', 'assets', 'default', 'raw', 'fonts', 'default.ttf')
