"""AWTK text metrics from a TrueType file: the model the look steps size and fit text with.

Ttf reads just enough TrueType to measure text the way AWTK's stb backend does; StbText adds the
layout rules of this AWTK build (advances truncated, +1 px after every glyph). Used by mod_lockscreen,
mod_nowplaying, mod_pulldown, mod_font and the previews. docs/ui.md ("Text width").
"""
import math, struct

DIGITS = '0123456789'

class Ttf:
    """Just enough TrueType to measure text the way AWTK's stb backend does: font_size px equals
    hhea ascender - descender (stbtt_ScaleForPixelHeight), advances from hmtx, digit ink from glyf."""
    def __init__(self, path):
        d = self.d = open(path, 'rb').read()
        n = struct.unpack_from('>H', d, 4)[0]
        self.t = {d[12 + 16 * i:16 + 16 * i].decode('latin-1'): struct.unpack_from('>I', d, 20 + 16 * i)[0] for i in range(n)}
        h = self.t['hhea']
        self.asc, self.desc = struct.unpack_from('>hh', d, h + 4)
        self.nhm = struct.unpack_from('>H', d, h + 34)[0]
        self.units = self.asc - self.desc
        self.loca_long = struct.unpack_from('>h', d, self.t['head'] + 50)[0]
        c = self.t['cmap']; subs = {}
        for i in range(struct.unpack_from('>H', d, c + 2)[0]):
            pid, eid, off = struct.unpack_from('>HHI', d, c + 4 + 8 * i); subs[(pid, eid)] = c + off
        self.cmap = next(subs[k] for k in ((3, 10), (0, 4), (3, 1), (0, 3)) if k in subs)
        self._glyphs = {}      # ch -> glyph index (the cmap is immutable, and measuring asks for the same few characters over and over)
    def glyph(self, ch):
        g = self._glyphs.get(ch)
        if g is None: g = self._glyphs[ch] = self._lookup(ch)
        return g
    def _lookup(self, ch):
        d, o, cp = self.d, self.cmap, ord(ch)
        fmt = struct.unpack_from('>H', d, o)[0]
        if fmt == 12:
            for i in range(struct.unpack_from('>I', d, o + 12)[0]):
                s, e, g = struct.unpack_from('>III', d, o + 16 + 12 * i)
                if s <= cp <= e: return g + cp - s
            return 0
        assert fmt == 4, f'cmap format {fmt}'
        seg = struct.unpack_from('>H', d, o + 6)[0] // 2
        ends = o + 14; starts = ends + 2 * seg + 2; deltas = starts + 2 * seg; ranges = deltas + 2 * seg
        for i in range(seg):
            if cp > struct.unpack_from('>H', d, ends + 2 * i)[0]: continue
            s = struct.unpack_from('>H', d, starts + 2 * i)[0]
            if cp < s: return 0
            delta = struct.unpack_from('>h', d, deltas + 2 * i)[0]; ro = struct.unpack_from('>H', d, ranges + 2 * i)[0]
            if ro == 0: return (cp + delta) & 0xffff
            g = struct.unpack_from('>H', d, ranges + 2 * i + ro + 2 * (cp - s))[0]
            return (g + delta) & 0xffff if g else 0
        return 0
    def advance(self, ch):
        return struct.unpack_from('>H', self.d, self.t['hmtx'] + 4 * min(self.glyph(ch), self.nhm - 1))[0]
    def ink(self, ch):
        """(yMin, yMax) of a glyph in font units."""
        g, l = self.glyph(ch), self.t['loca']
        off = struct.unpack_from('>I', self.d, l + 4 * g)[0] if self.loca_long else 2 * struct.unpack_from('>H', self.d, l + 2 * g)[0]
        g = self.t['glyf'] + off      # numberOfContours, xMin, yMin, xMax, yMax
        return struct.unpack_from('>h', self.d, g + 4)[0], struct.unpack_from('>h', self.d, g + 8)[0]
    def width(self, text, px):
        return sum(self.advance(c) for c in text) * px / self.units
    def digit_ink(self, px):
        """Top and bottom of digit ink, in px below the top of an AWTK text line of size px."""
        lo = min(self.ink(c)[0] for c in '0123456789'); hi = max(self.ink(c)[1] for c in '0123456789')
        return (self.asc - hi) * px / self.units, (self.asc - lo) * px / self.units

# ---------------------------------------------------------------------------------- AWTK's text layout
# The shared text model (tools/mod_nowplaying.py, tools/stb_raster.py and this tool measure with it;
# docs/ui.md "The album line"): stb_truetype scale = font_size / (ascender - descender)
# in float32; each glyph advances trunc(advance * scale) (glyph_t.advance) and demo's canvas adds 1 px
# after every glyph (canvas_measure_text 0x6446c8 / canvas_draw_text 0x6454d4: the lcd has no text
# functions of its own); a glyph the font cannot give adds 4. So a text is wider than its summed
# advances by up to one pixel per glyph.
STB_SPACING, STB_MISSING = 1, 4

def f32(x): return struct.unpack('<f', struct.pack('<f', x))[0]

class StbText:
    """Text metrics of one font size as this AWTK computes them, from a TrueType file (Ttf)."""
    def __init__(self, ttf, px):
        self.ttf, self.px = ttf, px
        self.scale = f32(px / ttf.units)          # (float)font_size / (float)(ascender - descender), div.s
    def has(self, ch): return self.ttf.glyph(ch) != 0
    def advance(self, ch):
        return int(f32(self.ttf.advance(ch) * self.scale)) if self.has(ch) else None
    def box(self, ch):
        """(x0, x1) of the glyph's bitmap relative to the pen, x1 exclusive; None for an empty glyph."""
        t, g = self.ttf, self.ttf.glyph(ch); loca = t.t['loca']
        if t.loca_long: a, b = struct.unpack_from('>II', t.d, loca + 4 * g)
        else: a, b = (2 * v for v in struct.unpack_from('>HH', t.d, loca + 2 * g))
        if a == b: return None
        xmin, _, xmax = struct.unpack_from('>hhh', t.d, t.t['glyf'] + a + 2)
        return math.floor(f32(xmin * self.scale)), math.ceil(f32(xmax * self.scale))
    def layout(self, text):
        """[(ch, pen)] from the text start, and the width AWTK measures (the pen after the last glyph)."""
        out, pen = [], 0
        for ch in text:
            out.append((ch, pen)); a = self.advance(ch)
            pen += STB_MISSING if a is None else a + STB_SPACING
        return out, pen

def awtk_width(ttf, text, px):
    """The width AWTK measures for text at font size px (StbText.layout)."""
    return StbText(ttf, px).layout(text)[1]

def fit_size(ttf, text, avail, start):
    """The largest font size <= start whose AWTK width of text is at most avail px."""
    size = start
    while size > 1 and awtk_width(ttf, text, size) > avail: size -= 1
    return size

MONTHS = 'Jan Feb Mar Apr May Jun Jul Aug Sept Oct Nov Dec'.split()     # demo's MMM table ("Sept")
WEEKDAYS = 'Sunday Monday Tuesday Wednesday Thursday Friday Saturday'.split()   # W (English UI; CN: 星期日..)

def worst_case_text(fmt, ttf=None):
    """Widest string a digit_clock format can produce. Digits are written as '0' (the stock font has
    tabular digits); with ttf given, as the font's widest digit, and W / MMM as the widest English
    weekday / month name of demo's tables."""
    d = max(DIGITS, key=ttf.advance) if ttf else '0'
    wide = lambda names: max(names, key=lambda s: sum(ttf.advance(c) for c in s)) if ttf else 'WWW'
    out, i = '', 0
    while i < len(fmt):
        c = fmt[i]; n = 1
        while i + n < len(fmt) and fmt[i + n] == c: n += 1
        if c in 'YMDhHmsT' or c == 'w':
            if c == 'Y': out += d * (2 if n == 2 else 4)
            elif c == 'M' and n == 3: out += wide(MONTHS)      # month name: generous without a font
            elif c == 'T' and n == 2: out += d * 2 + ' PM'
            elif c == 'w': out += d
            else: out += d * 2
        elif c == 'W': out += wide(WEEKDAYS)
        else: out += c * n
        i += n
    return out
