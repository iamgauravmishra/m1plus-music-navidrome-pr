#!/usr/bin/env python3
"""One battery design for the status bar and the lock screen (V2.1hA, docs/ui.md).

The app swaps one image between three states and feeds a progress bar the level, drawn UNDER the
image (stock child order), so the image is the outline only and the fill lands inside it:

  normal    white outline, the level is the progress bar's white fill
  charging  green #34C759 outline + a green bolt with a black keyline in the middle
  low       red #FF1448 outline (the app's low icon, capacity 0)

Same drawing at both sizes (stroke 1.5 px like the Tabler status icons, rounded body corners, a 2 px
rounded nub), only the canvas and the body rectangle differ; each widget keeps its stock geometry:

  STATUS  18 x 11 canvas, body 16 x 11, fill (pgbar_battery) 12 x 7 at (2, 2)   bar_power/charge/lowpower
  LOCK    34 x 12 canvas, body 22 x 12 at x 9, fill 16 x 6 at (12, 3)            screens_battery/charge/lowbattery

`fill_gap` checks the fill rectangle stays inside the outline's inner edge. Output is a plain zlib
RGBA PNG (the bytes do not depend on an image library's version; supersampling is integer box
reduction). Used by mod_battery.py and mod_lockscreen.py.
"""
import struct, zlib

WHITE, CHARGE, LOW = (255, 255, 255), (0x34, 0xC7, 0x59), (0xFF, 0x14, 0x48)
STROKE = 1.5
SS = 8

class Spec:
    def __init__(self, canvas, body, nub, radius, fill, bolt_h):
        self.canvas, self.body, self.nub, self.radius, self.fill, self.bolt_h = canvas, body, nub, radius, fill, bolt_h

STATUS = Spec((18, 11), (0, 0, 16, 11), (16, 3, 2, 5), 2.5, (2, 2, 12, 7), 7.0)
LOCK = Spec((34, 12), (9, 0, 22, 12), (31, 4, 2, 4), 3.0, (12, 3, 16, 6), 8.0)
STATES = {'normal': (WHITE, False), 'charge': (CHARGE, True), 'low': (LOW, False)}

BOLT = ((0.62, 0.0), (0.0, 0.58), (0.42, 0.58), (0.30, 1.0), (1.0, 0.38), (0.55, 0.38))   # unit box, y down

def fill_gap(spec):
    """Distance between the outline's inner edge and the fill rectangle (>= 0 on every side)."""
    bx, by, bw, bh = spec.body; fx, fy, fw, fh = spec.fill
    return min(fx - (bx + STROKE), fy - (by + STROKE), (bx + bw - STROKE) - (fx + fw), (by + bh - STROKE) - (fy + fh))

def mask(spec, bolt):
    from PIL import Image, ImageDraw
    w, h = spec.canvas; s = SS
    S = lambda *v: [round(x * s) for x in v]
    m = Image.new('L', (w * s, h * s), 0); d = ImageDraw.Draw(m)
    bx, by, bw, bh = spec.body
    d.rounded_rectangle(S(bx, by, bx + bw - 1 / s, by + bh - 1 / s), radius=spec.radius * s, fill=255)
    d.rounded_rectangle(S(bx + STROKE, by + STROKE, bx + bw - STROKE - 1 / s, by + bh - STROKE - 1 / s),
                        radius=max(spec.radius - STROKE, 0.5) * s, fill=0)
    nx, ny, nw, nh = spec.nub                                              # starts at the body's right edge
    d.rounded_rectangle(S(nx, ny, nx + nw - 1 / s, ny + nh - 1 / s), radius=nw / 2 * s, fill=255)
    d.rectangle(S(nx, ny, nx + nw / 2, ny + nh - 1 / s), fill=255)         # square where it meets the body
    if bolt:
        from PIL import ImageFilter
        cx, cy = bx + bw / 2, by + bh / 2; bh_ = spec.bolt_h; bw_ = bh_ * 0.7
        pts = [tuple(S(cx - bw_ / 2 + u * bw_, cy - bh_ / 2 + v * bh_)) for u, v in BOLT]
        core = Image.new('L', m.size, 0); ImageDraw.Draw(core).polygon(pts, fill=255)
        key = core.filter(ImageFilter.MaxFilter(5))          # ~0.5 px black keyline
        return m.reduce(s), key.reduce(s), core.reduce(s)
    return m.reduce(s), None, None

def render(spec, state):
    """-> (width, height, RGBA bytes row-major)."""
    from PIL import Image
    rgb, bolt = STATES[state]
    outline, key, bolt_m = mask(spec, bolt)
    w, h = spec.canvas
    im = Image.new('RGBA', (w, h), rgb + (0,)); im.putalpha(outline)
    if bolt:
        k = Image.new('RGBA', (w, h), (0, 0, 0, 255)); k.putalpha(key)
        g = Image.new('RGBA', (w, h), rgb + (255,)); g.putalpha(bolt_m)
        im.alpha_composite(k); im.alpha_composite(g)
    return im

def png(spec, state):
    im = render(spec, state); w, h = im.size
    raw = b''.join(b'\0' + im.crop((0, y, w, y + 1)).tobytes() for y in range(h))
    chunk = lambda t, d: struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))

if __name__ == '__main__':
    for sp, n in ((STATUS, 'status'), (LOCK, 'lock')):
        print(n, 'fill gap', fill_gap(sp), {s: len(png(sp, s)) for s in STATES})
