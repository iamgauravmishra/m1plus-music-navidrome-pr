#!/usr/bin/env python3
"""Smallest lossless PNG of an RGBA picture, in pure Python (deterministic; no dependency beyond Pillow, which only checks the result).

  pack(im) -> bytes      the picture's PNG: IHDR, [PLTE, tRNS], IDAT, IEND, nothing else. Every candidate decodes to exactly the same RGBA pixels (asserted).

Candidates: 8 bit RGBA, and, when the picture has at most 256 colours, an 8 bit palette picture WITH a tRNS chunk (any alpha, all 255 included). The tRNS chunk keeps the
decoder's output at four channels per pixel: stb_image (AWTK's loader) expands a palette picture with tRNS to RGBA and one without to RGB, and the payload's loaders read four
bytes per pixel. Stock ships palette pictures with tRNS (the scover_wait* images), so the loader handles the format. For each candidate: the filter none, sub, up, average or Paeth on every row, the
per-row minimum-sum choice, or the per-row choice by trial compression; zlib level 9, the default and the filtered strategy; the smallest stream wins. Pictures of few colours
(film grain over a gradient, sprites) mostly want no filter at all: the deflate matches repeat whole pixels. Used for the Vinyl pictures only (tools/mod_icons.py --generate, tools/vinyl_art.py).
"""
import struct, zlib, io


SIG = b'\x89PNG\r\n\x1a\n'


def _chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))


def _filters(raw, w, h, bpp):
    """Per row the five filtered versions (none, sub, up, average, Paeth)."""
    rb = w * bpp; rows = [raw[y * rb:(y + 1) * rb] for y in range(h)]; zero = bytes(rb); out = []
    for y in range(h):
        r, u = rows[y], (rows[y - 1] if y else zero)
        sub = bytearray(r); up = bytearray(rb); avg = bytearray(rb); pae = bytearray(rb)
        for i in range(rb):
            a = r[i - bpp] if i >= bpp else 0; b = u[i]; c = u[i - bpp] if i >= bpp else 0
            up[i] = (r[i] - b) & 255
            avg[i] = (r[i] - ((a + b) >> 1)) & 255
            p = a + b - c; da = abs(p - a); db = abs(p - b); dc = abs(p - c)
            pae[i] = (r[i] - (a if da <= db and da <= dc else (b if db <= dc else c))) & 255
            if i >= bpp: sub[i] = (r[i] - a) & 255
        out.append([r, bytes(sub), bytes(up), bytes(avg), bytes(pae)])
    return out


def _cost(row): return sum(v if v < 128 else 256 - v for v in row)


def _deflate(raw, strategy):
    co = zlib.compressobj(9, zlib.DEFLATED, 15, 9, strategy)
    return co.compress(raw) + co.flush()


def _best_stream(raw, w, h, bpp):
    """The smallest zlib stream of the filtered scanlines of `raw` (w x h, bpp bytes per pixel)."""
    rows = _filters(raw, w, h, bpp); best = None
    fixed = [[k] * h for k in range(5)]
    minsum = [[min(range(5), key=lambda k: _cost(rs[k])) for rs in rows]]
    plans = fixed + minsum
    for strategy in (zlib.Z_DEFAULT_STRATEGY, zlib.Z_FILTERED):
        co = zlib.compressobj(9, zlib.DEFLATED, 15, 9, strategy); out = []; sel = []   # the greedy plan: each row's filter by trial on a copy of the compressor
        for rs in rows:
            sizes = []
            for k in range(5):
                c2 = co.copy(); sizes.append(len(c2.compress(bytes([k]) + rs[k]) + c2.flush(zlib.Z_SYNC_FLUSH)))
            k = min(range(5), key=sizes.__getitem__); sel.append(k); out.append(co.compress(bytes([k]) + rs[k]))
        out.append(co.flush()); s = b''.join(out)
        if best is None or len(s) < len(best): best = s
        for plan in plans if strategy == zlib.Z_DEFAULT_STRATEGY else plans[-1:]:
            s = _deflate(b''.join(bytes([k]) + rs[k] for k, rs in zip(plan, rows)), strategy)
            if len(s) < len(best): best = s
    return best


def _palette_orders(px):
    """The palettes to try: by first appearance, by frequency, sorted."""
    first = list(dict.fromkeys(px)); count = {}
    for p in px: count[p] = count.get(p, 0) + 1
    return [first, sorted(first, key=lambda p: (-count[p], p)), sorted(first)]


def pack(im):
    from PIL import Image
    assert im.mode == 'RGBA'
    w, h = im.size; raw = im.tobytes(); px = [raw[i:i + 4] for i in range(0, len(raw), 4)]
    ihdr = lambda ctype: struct.pack('>IIBBBBB', w, h, 8, ctype, 0, 0, 0)
    best = SIG + _chunk(b'IHDR', ihdr(6)) + _chunk(b'IDAT', _best_stream(raw, w, h, 4)) + _chunk(b'IEND', b'')
    if len(set(px)) <= 256:
        for pal in _palette_orders(px):
            idx = {c: i for i, c in enumerate(pal)}
            stream = _best_stream(bytes(idx[p] for p in px), w, h, 1)
            png = (SIG + _chunk(b'IHDR', ihdr(3)) + _chunk(b'PLTE', b''.join(c[:3] for c in pal))
                   + _chunk(b'tRNS', bytes(c[3] for c in pal)) + _chunk(b'IDAT', stream) + _chunk(b'IEND', b''))
            if len(png) < len(best): best = png
    back = Image.open(io.BytesIO(best)); back.load()
    assert back.convert('RGBA').tobytes() == raw and back.size == im.size, 'png_pack: the picture does not round trip'
    return best
