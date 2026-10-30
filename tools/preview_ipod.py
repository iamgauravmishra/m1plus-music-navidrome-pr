#!/usr/bin/env python3
"""out/preview/ipod-mock.png: a "virtual iPod Classic" laid out on the M1 Plus screen (320 x 480), 1:1 device pixels, frames side by side.
Look only: no firmware or device code. Approximate PIL mock-up, not AWTK; sample data.

Geometry: a fullscreen window (320 x 480 over the stock status bar, as the lock screen's screensaver_page; docs/ui.md):
  iPod screen 240 (320 x 240 = the iPod Classic's 4:3, exact width; its 24 px title bar carries play state, clock and battery)
  | click wheel region 240: wheel 220 px across (ring) with a 90 px centre button, MENU / |<< / >>| / >|| on the ring.
  The comparison frame (last) is a normal window under the 30 px stock status bar: wheel region 210, wheel 190 px.

Frames: 1 main menu (6G split screen, classic blue selection), 2 submenu (Albums), 3 Now Playing, 4 Cover Flow,
5 the main menu in this project's dark look with a dark wheel, 6 frame 1 under the stock status bar.
The wheel is drawn at 4x and reduced; all text is drawn 1:1 with the tree's own font (StbFont, preview_icons.Side).

  preview_ipod.py WORKDIR [OUT.png]     (unpacked release work tree; venv python; default out/preview/ipod-mock.png)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from PIL import Image, ImageDraw
import build, preview_icons as PI

W, BAR, H = 320, 30, 480
MENU = ['Cover Flow', 'Albums', 'Artists', 'Songs', 'Playlists', 'Shuffle Songs', 'Settings', 'Now Playing']
ALBUMS = [('Kind of Blue', (70, 110, 190)), ('Blue in Green', (50, 90, 170)), ('Homogenic', (190, 90, 120)), ('Dummy', (150, 120, 70)),
          ('Kid A', (60, 140, 150)), ('Mezzanine', (110, 90, 130)), ('OK Computer', (110, 130, 150)), ('Pet Sounds', (200, 170, 110))]

class Theme:
    def __init__(self, dark):
        self.dark = dark
        self.bg = (0, 0, 0) if dark else (255, 255, 255)
        self.fg = (255, 255, 255) if dark else (0, 0, 0)
        self.sub = (0x99,) * 3 if dark else (0x66,) * 3
        self.line = (0x2A,) * 3 if dark else (0xDD,) * 3
        self.body = (0x0C,) * 3 if dark else (0xC6, 0xC9, 0xCE)
        self.ring = ((0x34,) * 3, (0x22,) * 3) if dark else ((0xFA,) * 3, (0xDC,) * 3)
        self.hub = ((0x1A,) * 3, (0x0A,) * 3) if dark else ((0xEE,) * 3, (0xCF,) * 3)
        self.label = (0xC8,) * 3 if dark else (0x86,) * 3

def vgrad(im, box, top, bot):
    d = ImageDraw.Draw(im); x0, y0, x1, y1 = box
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0 - 1)
        d.line((x0, y, x1 - 1, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)) + (255,))

def chevron(im, x, ymid, rgb, h=4):
    d = ImageDraw.Draw(im); d.line((x, ymid - h, x + h, ymid, x, ymid + h), fill=rgb + (255,), width=2)

def battery(im, x, y, rgb, fill=0.8):
    d = ImageDraw.Draw(im)
    d.rectangle((x, y, x + 20, y + 9), outline=rgb + (255,)); d.rectangle((x + 21, y + 3, x + 22, y + 6), fill=rgb + (255,))
    d.rectangle((x + 2, y + 2, x + 2 + int(16 * fill), y + 7), fill=(0x4C, 0xB8, 0x4C, 255))

def play_glyph(im, x, ymid, rgb, h=5):
    ImageDraw.Draw(im).polygon([(x, ymid - h), (x, ymid + h), (x + h + 1, ymid)], fill=rgb + (255,))

def title_bar(s, im, th, title, h=24, right=None, clock=False):
    if th.dark:
        ImageDraw.Draw(im).rectangle((0, 0, W - 1, h - 1), fill=(0, 0, 0, 255)); ImageDraw.Draw(im).line((0, h - 1, W, h - 1), fill=(0x2A,) * 3 + (255,))
    else:
        vgrad(im, (0, 0, W, h), (0xF4, 0xF5, 0xF7), (0xB4, 0xB8, 0xC0)); ImageDraw.Draw(im).line((0, h - 1, W, h - 1), fill=(0x80, 0x84, 0x8C, 255))
    s.text(im, W // 2, h / 2, title, 16, th.fg, 'm')
    play_glyph(im, 8, h // 2, th.fg)
    if clock: s.text(im, 20, h / 2, '12:59', 14, th.fg)   # fullscreen: the bar stands in for the stock status bar's clock
    battery(im, W - 32, h // 2 - 5, th.fg)
    if right: s.text(im, W - 38, h / 2, right, 13, th.sub, 'r')

def selection(im, y, h, th, x1=W):
    if th.dark: ImageDraw.Draw(im).rectangle((0, y, x1 - 1, y + h - 1), fill=(0x2C, 0x2C, 0x2E, 255))
    else: vgrad(im, (0, y, x1, y + h), (0x5F, 0xB1, 0xF7), (0x0C, 0x62, 0xD2))

def rows(s, im, th, items, y0, rh, sel, x1=W, px=17, chev=True, tag=None):
    d = ImageDraw.Draw(im)
    for i, t in enumerate(items):
        y = y0 + i * rh
        fg = th.fg
        if i == sel: selection(im, y, rh, th, x1); fg = (255, 255, 255)
        elif th.dark: d.line((14, y + rh - 1, x1 - 1, y + rh - 1), fill=th.line + (255,))
        s.text(im, 10, y + rh / 2, s.clip(t, px, x1 - 34), px, fg)
        if chev: chevron(im, x1 - 14, y + rh // 2, fg)

def cover(rgb, size, r=0):
    c = PI.sample_cover(rgb, size)
    return c

def reflect(im, c, x, y, fade=0.35, hmax=None):
    f = c.transpose(Image.FLIP_TOP_BOTTOM); h = hmax or f.height // 3
    f = f.crop((0, 0, f.width, h)); a = Image.new('L', f.size)
    for yy in range(h): ImageDraw.Draw(a).line((0, yy, f.width, yy), fill=int(255 * fade * (1 - yy / h)))
    f.putalpha(a); im.alpha_composite(f, (x, y))

def screen_main(s, th, sh, clock=True):
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); title_bar(s, im, th, 'M1+ Music', clock=clock)
    rh = (sh - 24) // len(MENU)
    rows(s, im, th, MENU, 24, rh, 1, x1=172, px=17 if rh >= 24 else 16, chev=True)
    # the 6G split screen: the selected row's art on the right
    x0 = 172; ImageDraw.Draw(im).rectangle((x0, 24, W, sh), fill=((0x10,) * 3 if th.dark else (0xF2, 0xF3, 0xF5)) + (255,))
    ImageDraw.Draw(im).line((x0, 24, x0, sh), fill=th.line + (255,))
    size = min(112, sh - 24 - 52)
    cx = x0 + (W - x0 - size) // 2
    for dx, rgb in ((-30, (110, 90, 130)), (30, (150, 120, 70))):   # the neighbours peeking out behind
        small = cover(rgb, size - 34); im.alpha_composite(small, (cx + 17 + dx, 24 + 14 + 17))
    big = cover((70, 110, 190), size); im.alpha_composite(big, (cx, 24 + 14)); reflect(im, big, cx, 24 + 14 + size, 0.3, 22)
    return im

def screen_albums(s, th, sh):
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); title_bar(s, im, th, 'Albums', clock=True)
    rh = (sh - 24) // 8
    rows(s, im, th, [a for a, _ in ALBUMS], 24, rh, 2, px=17 if rh >= 24 else 16)
    return im

def screen_now(s, th, sh):
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); title_bar(s, im, th, 'Now Playing', clock=True)
    size = 112; im.alpha_composite(cover((70, 110, 190), size), (12, 36))
    tx = 12 + size + 12
    s.text(im, tx, 50, s.clip('So What', 18, W - tx - 8), 18, th.fg)
    s.text(im, tx, 76, s.clip('Miles Davis', 16, W - tx - 8), 16, th.sub)
    s.text(im, tx, 100, s.clip('Kind of Blue', 16, W - tx - 8), 16, th.sub)
    s.text(im, tx, 132, '1 of 12', 14, th.sub)
    py = sh - 52; d = ImageDraw.Draw(im)
    d.rounded_rectangle((12, py, W - 13, py + 9), 4, fill=(th.line if th.dark else (0xD4, 0xD6, 0xDA)) + (255,))
    fw = int((W - 25) * 0.34)
    if th.dark: d.rounded_rectangle((12, py, 12 + fw, py + 9), 4, fill=(255, 255, 255, 255))
    else: vgrad(im, (12, py, 12 + fw, py + 10), (0x5F, 0xB1, 0xF7), (0x0C, 0x62, 0xD2))
    s.text(im, 12, py + 24, '1:47', 14, th.sub); s.text(im, W - 12, py + 24, '-3:25', 14, th.sub, 'r')
    return im

def screen_cf(s, th, sh):
    im = Image.new('RGBA', (W, sh), (0, 0, 0, 255))
    order = [-3, -2, -1, 3, 2, 1, 0]
    for k in order:
        rgb = ALBUMS[(k + 3) % len(ALBUMS)][1]
        if k == 0:
            c = cover(rgb, 104); x, y = (W - 104) // 2, 30; im.alpha_composite(c, (x, y)); reflect(im, c, x, y + 104, 0.4, 34)
        else:
            c = cover(rgb, 88).resize((34, 88), Image.LANCZOS)
            sq = Image.new('RGBA', (34, 88)); sq.paste(c)
            # a flat-perspective trapezoid: the outer edge is shorter
            dst = sq.transform((34, 88), Image.QUAD, (0, -6, 0, 94, 34, 88, 34, 0) if k < 0 else (0, 0, 0, 88, 34, 94, 34, -6), Image.BICUBIC)
            x = W // 2 + (1 if k > 0 else -1) * (52 + (abs(k) - 1) * 32) - (34 if k < 0 else 0)
            im.alpha_composite(dst, (x, 36)); reflect(im, dst, x, 36 + 88, 0.25, 22)
    s.text(im, W // 2, sh - 46, 'Kind of Blue', 18, (255, 255, 255), 'm')
    s.text(im, W // 2, sh - 24, 'Miles Davis', 15, (0xAA,) * 3, 'm')
    return im

def wheel(s, th, region_h, diam):
    """The click wheel on the body colour: ring + hub drawn at 4x and reduced, labels at 1x."""
    k = 4; im = Image.new('RGBA', (W * k, region_h * k), th.body + (255,))
    d = ImageDraw.Draw(im); cx, cy, r = W * k // 2, region_h * k // 2, diam * k // 2
    ring = Image.new('RGBA', im.size, (0, 0, 0, 0))
    for y in range(cy - r, cy + r):   # vertical gradient clipped to the disc
        t = (y - (cy - r)) / (2 * r)
        ImageDraw.Draw(ring).line((0, y, im.width, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(*th.ring)) + (255,))
    m = Image.new('L', im.size, 0); ImageDraw.Draw(m).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    d.ellipse((cx - r - k, cy - r - k, cx + r + k, cy + r + k), fill=((0, 0, 0) if th.dark else (0xA8, 0xAB, 0xB0)) + (255,))
    im.paste(ring, (0, 0), m)
    hr = int(r * 0.41); hub = Image.new('RGBA', im.size, (0, 0, 0, 0))
    for y in range(cy - hr, cy + hr):
        t = (y - (cy - hr)) / (2 * hr)
        ImageDraw.Draw(hub).line((0, y, im.width, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(*th.hub)) + (255,))
    hm = Image.new('L', im.size, 0); ImageDraw.Draw(hm).ellipse((cx - hr, cy - hr, cx + hr, cy + hr), fill=255)
    d.ellipse((cx - hr - k, cy - hr - k, cx + hr + k, cy + hr + k), fill=((0x40,) * 3 if th.dark else (0xB0,) * 3) + (255,))
    im.paste(hub, (0, 0), hm)
    # glyphs on the ring, drawn at 4x
    lab = th.label + (255,); rm = int((r + hr) / 2); g = 5 * k
    for sx in (-1, 1):   # |<<  and  >>|: two triangles pointing along sx, then the bar
        x = cx + sx * rm
        for xc in (x - sx * 3 * k, x + sx * 3 * k - sx * 6 * k * 0):
            d.polygon([(xc - sx * 3 * k, cy - g), (xc - sx * 3 * k, cy + g), (xc + sx * 3 * k, cy)], fill=lab)
        bx = x + sx * 8 * k
        d.rectangle((min(bx, bx + sx * 2 * k), cy - g, max(bx, bx + sx * 2 * k), cy + g), fill=lab)
    by = cy + rm   # play / pause
    d.polygon([(cx - 8 * k, by - 5 * k), (cx - 8 * k, by + 5 * k), (cx - 1 * k, by)], fill=lab)
    d.rectangle((cx + 2 * k, by - 5 * k, cx + 4 * k, by + 5 * k), fill=lab); d.rectangle((cx + 6 * k, by - 5 * k, cx + 8 * k, by + 5 * k), fill=lab)
    out = im.resize((W, region_h), Image.LANCZOS)
    s.text(out, W // 2, region_h / 2 - rm / k, 'MENU', 14, th.label, 'm')
    return out

def frame(s, th, screen, sh, bar=False):
    """bar=False: a fullscreen window (like the lock screen, screensaver_page) over the stock status bar."""
    top = BAR if bar else 0
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    if bar: PI.status_bar(s, im)
    im.alpha_composite(screen, (0, top))
    reg = H - top - sh
    im.alpha_composite(wheel(s, th, reg, min(reg - 20, 220)), (0, top + sh))
    return im

def main():
    work = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'ipod-mock.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    s = PI.Side(work, True)
    L, D = Theme(False), Theme(True)
    frames = [('1 Main menu (fullscreen, no status bar)', frame(s, L, screen_main(s, L, 240), 240)),
              ('2 Submenu: Albums', frame(s, L, screen_albums(s, L, 240), 240)),
              ('3 Now Playing', frame(s, L, screen_now(s, L, 240), 240)),
              ('4 Cover Flow', frame(s, L, screen_cf(s, L, 240), 240)),
              ('5 Main menu, project dark look', frame(s, D, screen_main(s, D, 240), 240)),
              ('6 For comparison: under the stock status bar', frame(s, L, screen_main(s, L, 240, clock=False), 240, bar=True))]
    pad, lab = 12, 22
    sheet = Image.new('RGB', (pad + len(frames) * (W + pad), lab + H + 2 * pad), (0x2A,) * 3); d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(frames):
        x = pad + i * (W + pad)
        d.text((x, pad - 2), t, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, pad + lab))
    PI.save_compact(sheet, out, 256); print('wrote', out, sheet.size)

if __name__ == '__main__':
    main()
