#!/usr/bin/env python3
"""Draw text the way this firmware's AWTK does: stb_truetype, no hinting, no kerning. docs/ui.md

AWTK's stb backend (font_stb_* in demo; docs/ui.md, docs/ui.md, docs/firmware.md 3b):
  scale     font_size / (hhea ascender - descender)            (stbtt_ScaleForPixelHeight)
  cmap      the last Unicode record stb accepts (platform 0, or 3/1, 3/10); format 4 is looked up
            with mod_boot.stb_lookup, a line-for-line port of stbtt_FindGlyphIndex
  outline   glyf, read as stbtt_GetGlyphShape does (integer midpoints between off-curve points)
  box       floor/ceil of the glyf header box times scale (stbtt_GetGlyphBitmapBox, no subpixel shift)
  coverage  curves flattened to 0.35 px, then the exact signed area per pixel, |sum| clamped to 1
            (stb's v2 rasterizer; here the equivalent accumulation-buffer form)
  layout    integer pen; each glyph advances trunc(advance * scale) + 1 px: the glyph function at
            0x680438 truncates, and canvas_measure_text (0x6446c8) and canvas_draw_text (0x6454d4)
            both add 1 per glyph; baseline trunc(ascender * scale) below the line top (font_get_vmetrics)

Pure Python (Pillow only for the bitmaps), so previews need no FreeType and see exactly the font
file the build produced. Not a pixel-exact AWTK: blending and text alignment are simplified.

  StbFont(path).draw(im, x, top, text, px, rgba)   draw one line, top-left of the line box at x, top
  StbFont(path).width(text, px)                    advance width in px, as AWTK measures it (+1 px per glyph)
"""
import math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mod_boot import tables, stb_lookup
from awtk_text import f32

class StbFont:
    def __init__(self, path):
        """path: a font file, or the font's bytes."""
        d = self.d = path if isinstance(path, bytes) else open(path, 'rb').read()
        t = self.t = {k.decode('latin-1'): off for k, (_, _, off, _) in tables(d).items()}
        self.asc, self.desc = struct.unpack_from('>hh', d, t['hhea'] + 4)
        self.nhm = struct.unpack_from('>H', d, t['hhea'] + 34)[0]
        self.long_loca = struct.unpack_from('>h', d, t['head'] + 50)[0]
        self.nglyphs = struct.unpack_from('>H', d, t['maxp'] + 4)[0]
        c = t['cmap']; self.cmap = None
        for i in range(struct.unpack_from('>H', d, c + 2)[0]):      # stbtt_InitFont: the last match wins
            pid, eid, off = struct.unpack_from('>HHI', d, c + 4 + 8 * i)
            if pid == 0 or (pid == 3 and eid in (1, 10)): self.cmap = c + off
        assert self.cmap is not None and struct.unpack_from('>H', d, self.cmap)[0] == 4, 'need a Unicode format-4 cmap'
        self.cache = {}

    def scale(self, px): return px / (self.asc - self.desc)
    def glyph(self, ch): return stb_lookup(self.d, self.cmap, ord(ch))
    def advance(self, g):
        return struct.unpack_from('>H', self.d, self.t['hmtx'] + 4 * min(g, self.nhm - 1))[0]

    def _glyf(self, g):
        if g >= self.nglyphs: return None
        l = self.t['loca']
        if self.long_loca: a, b = struct.unpack_from('>II', self.d, l + 4 * g)
        else: a, b = (2 * x for x in struct.unpack_from('>HH', self.d, l + 2 * g))
        return self.t['glyf'] + a if b > a else None

    def box(self, g):
        o = self._glyf(g)
        return struct.unpack_from('>hhhh', self.d, o + 2) if o is not None else None

    def shape(self, g, depth=0):
        """stbtt_GetGlyphShape: [(type, x, y, cx, cy)], type 'm' move, 'l' line, 'q' quadratic."""
        d, o = self.d, self._glyf(g)
        if o is None: return []
        nc = struct.unpack_from('>h', d, o)[0]
        if nc > 0:
            ends = struct.unpack_from(f'>{nc}H', d, o + 10)
            ins = struct.unpack_from('>H', d, o + 10 + 2 * nc)[0]
            p = o + 12 + 2 * nc + ins; n = ends[-1] + 1
            flags = []
            while len(flags) < n:
                f = d[p]; p += 1; flags.append(f)
                if f & 8:
                    r = d[p]; p += 1; flags += [f] * r
            pts = []
            for axis, short, same in ((0, 2, 16), (1, 4, 32)):
                v, out = 0, []
                for f in flags[:n]:
                    if f & short:
                        dv = d[p]; p += 1; v += dv if f & same else -dv
                    elif not f & same:
                        v += struct.unpack_from('>h', d, p)[0]; p += 2
                    out.append(v)
                pts.append(out)
            xs, ys = pts
            verts = []; next_move = 0; j = 0; i = 0
            sx = sy = cx = cy = scx = scy = 0; was_off = start_off = False
            def close():
                if start_off:
                    if was_off: verts.append(('q', (cx + scx) >> 1, (cy + scy) >> 1, cx, cy))
                    verts.append(('q', sx, sy, scx, scy))
                else:
                    verts.append(('q', sx, sy, cx, cy) if was_off else ('l', sx, sy, 0, 0))
            while i < n:
                f, x, y = flags[i], xs[i], ys[i]
                if next_move == i:
                    if i: close()
                    start_off = not f & 1
                    if start_off:
                        scx, scy = x, y
                        if not flags[i + 1] & 1: sx, sy = (x + xs[i + 1]) >> 1, (y + ys[i + 1]) >> 1
                        else: sx, sy = xs[i + 1], ys[i + 1]; i += 1
                    else: sx, sy = x, y
                    verts.append(('m', sx, sy, 0, 0)); was_off = False
                    next_move = ends[j] + 1; j += 1
                elif not f & 1:
                    if was_off: verts.append(('q', (cx + x) >> 1, (cy + y) >> 1, cx, cy))
                    cx, cy, was_off = x, y, True
                else:
                    verts.append(('q', x, y, cx, cy) if was_off else ('l', x, y, 0, 0)); was_off = False
                i += 1
            close()
            return verts
        if nc < 0:                                     # composite, as stb does it (scale bug included)
            verts, p = [], o + 10
            assert depth < 8, 'composite too deep'
            while True:
                flags, gi = struct.unpack_from('>Hh', d, p); p += 4
                mtx = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
                if flags & 2:
                    if flags & 1: mtx[4], mtx[5] = struct.unpack_from('>hh', d, p); p += 4
                    else: mtx[4], mtx[5] = struct.unpack_from('>bb', d, p); p += 2
                else: p += 4 if flags & 1 else 2      # point matching: stb asserts (no-op in release), no offset
                if flags & 8: mtx[0] = mtx[3] = struct.unpack_from('>h', d, p)[0] / 16384; p += 2
                elif flags & 0x40: mtx[0], mtx[3] = (v / 16384 for v in struct.unpack_from('>hh', d, p)); p += 4
                elif flags & 0x80: mtx[:4] = (v / 16384 for v in struct.unpack_from('>hhhh', d, p)); p += 8
                m, n = math.hypot(mtx[0], mtx[1]), math.hypot(mtx[2], mtx[3])
                tx = lambda x, y: int(m * (mtx[0] * x + mtx[2] * y + mtx[4]))
                ty = lambda x, y: int(n * (mtx[1] * x + mtx[3] * y + mtx[5]))
                verts += [(t, tx(x, y), ty(x, y), tx(cx, cy), ty(cx, cy)) for t, x, y, cx, cy in self.shape(gi, depth + 1)]
                if not flags & 0x20: break
            return verts
        return []

    def bitmap(self, g, px):
        """(x0, y0, w, h, coverage rows) of glyph g at font_size px, y0 relative to the baseline."""
        key = (g, px)
        if key in self.cache: return self.cache[key]
        s = self.scale(px); b = self.box(g)
        if b is None: self.cache[key] = (0, 0, 0, 0, []); return self.cache[key]
        x0, y0 = math.floor(b[0] * s), math.floor(-b[3] * s)
        x1, y1 = math.ceil(b[2] * s), math.ceil(-b[1] * s)
        w, h = x1 - x0, y1 - y0
        flat2 = (0.35 / s) ** 2
        st = w + 3                                     # row stride: one guard column left, two right
        acc = [0.0] * (st * h + st)
        def line(ax, ay, bx, by):                      # font units -> bitmap pixels, then exact area
            ax, ay, bx, by = ax * s - x0, -ay * s - y0, bx * s - x0, -by * s - y0
            if abs(ay - by) < 1e-9: return
            dr = 1.0
            if ay > by: ax, ay, bx, by, dr = bx, by, ax, ay, -1.0
            dxdy = (bx - ax) / (by - ay); x = ax
            if ay < 0: x -= ay * dxdy
            for yy in range(max(0, int(ay)), min(h, math.ceil(by))):
                ls = yy * st + 1
                dy = min(yy + 1.0, by) - max(float(yy), ay)
                xn = x + dxdy * dy; dd = dy * dr
                lo, hi = (x, xn) if x < xn else (xn, x)
                lf = math.floor(lo); li = int(lf); hc = math.ceil(hi); hi_i = int(hc)
                if hi_i <= li + 1:
                    xm = 0.5 * (x + xn) - lf
                    acc[ls + li] += dd - dd * xm; acc[ls + li + 1] += dd * xm
                else:
                    r = 1.0 / (hi - lo); l0 = lo - lf
                    a0 = 0.5 * r * (1 - l0) * (1 - l0)
                    h1 = hi - hc + 1.0; am = 0.5 * r * h1 * h1
                    acc[ls + li] += dd * a0
                    if hi_i == li + 2: acc[ls + li + 1] += dd * (1 - a0 - am)
                    else:
                        a1 = r * (1.5 - l0)
                        acc[ls + li + 1] += dd * (a1 - a0)
                        for xi in range(li + 2, hi_i - 1): acc[ls + xi] += dd * r
                        a2 = a1 + (hi_i - li - 3) * r
                        acc[ls + hi_i - 1] += dd * (1 - a2 - am)
                    acc[ls + hi_i] += dd * am
                x = xn
        def curve(ax, ay, cx, cy, bx, by, n=0):        # stbtt__tesselate_curve
            mx, my = (ax + 2 * cx + bx) / 4, (ay + 2 * cy + by) / 4
            ex, ey = (ax + bx) / 2 - mx, (ay + by) / 2 - my
            if n <= 16 and ex * ex + ey * ey > flat2:
                curve(ax, ay, (ax + cx) / 2, (ay + cy) / 2, mx, my, n + 1)
                curve(mx, my, (cx + bx) / 2, (cy + by) / 2, bx, by, n + 1)
            else: line(ax, ay, bx, by)
        px_ = py_ = 0; sx_ = sy_ = 0
        for t, x, y, cx, cy in self.shape(g):
            if t == 'm':
                if (px_, py_) != (sx_, sy_): line(px_, py_, sx_, sy_)
                sx_, sy_ = x, y
            elif t == 'l': line(px_, py_, x, y)
            else: curve(px_, py_, cx, cy, x, y)
            px_, py_ = x, y
        if (px_, py_) != (sx_, sy_): line(px_, py_, sx_, sy_)
        rows = []
        for yy in range(h):                            # running sum per row; |area| clamped (stb v2)
            run, row, base = 0.0, [], yy * st
            run += acc[base]
            for xx in range(w):
                run += acc[base + 1 + xx]
                row.append(min(255, int(abs(run) * 255 + 0.5)))
            rows.append(row)
        self.cache[key] = (x0, y0, w, h, rows)
        return self.cache[key]

    def step(self, g, px):
        """Pen step of one glyph in px: trunc(advance * scale) + 1, as demo's canvas does, in the same
        float32 arithmetic as the build's text model (awtk_text.StbText)."""
        return int(f32(self.advance(g) * f32(px / (self.asc - self.desc)))) + 1

    def width(self, text, px):
        return sum(self.step(self.glyph(c), px) for c in text)

    def baseline(self, px): return int(self.asc * self.scale(px))

    def mask(self, text, px):
        """An 'L' image of one line (height px, AWTK line box) and its width."""
        from PIL import Image
        wd = self.width(text, px)
        im = Image.new('L', (max(1, wd + 4 * px), px + 2 * px), 0)
        base = px + self.baseline(px); x = 2 * px
        pix = im.load()
        for c in text:
            g = self.glyph(c)
            x0, y0, w, h, rows = self.bitmap(g, px)
            for yy in range(h):
                for xx in range(w):
                    v = rows[yy][xx]
                    if v:
                        X, Y = x + x0 + xx, base + y0 + yy
                        if 0 <= X < im.width and 0 <= Y < im.height: pix[X, Y] = min(255, pix[X, Y] + v)
            x += self.step(g, px)
        return im, 2 * px, px, wd                # image, x and y of the line box origin in it, width

    def draw(self, im, x, top, text, px, rgba):
        """Alpha-blend one line onto an RGBA image, line box top-left at (x, top)."""
        from PIL import Image
        m, ox, oy, _ = self.mask(text, px)
        a = rgba[3] if len(rgba) > 3 else 255
        if a != 255: m = m.point(lambda v: v * a // 255)
        layer = Image.new('RGBA', m.size, tuple(rgba[:3]) + (0,)); layer.putalpha(m)
        _paste(im, layer, int(x) - ox, int(top) - oy)

def _paste(im, layer, x, y):
    """alpha_composite clipped to the image (offsets may be negative or run past the edge)."""
    cx, cy = max(0, -x), max(0, -y)
    cw, ch = min(layer.width, im.width - x), min(layer.height, im.height - y)
    if cx >= cw or cy >= ch: return
    im.alpha_composite(layer.crop((cx, cy, cw, ch)), (x + cx, y + cy))
