#!/usr/bin/env python3
"""Pod screens at 1:1 device pixels, with sample data and the built wheel asset.

Frames: root, Music, Albums and Now Playing. Text uses the tree's font and the shared
StbFont metrics (preview_icons.Side); colours and geometry follow patch/ipod.c.

  preview_ipod.py WORKDIR [OUT.png]     (unpacked release work tree; venv python; default out/preview/ipod-mock.png)
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw
import build, cdefs, preview_icons as PI, pod_ui

W, BAR, H = 320, 30, 480
MENU = ['Music', 'Cover Flow', 'Shuffle Songs', 'Now Playing', 'Settings']
MUSIC = ['Cover Flow', 'Albums', 'Artists', 'Songs', 'Playlists', 'Shuffle Songs']
ALBUMS = [('Kind of Blue', (70, 110, 190)), ('Blue in Green', (50, 90, 170)), ('Homogenic', (190, 90, 120)), ('Dummy', (150, 120, 70)),
          ('Kid A', (60, 140, 150)), ('Mezzanine', (110, 90, 130)), ('OK Computer', (110, 130, 150)), ('Pet Sounds', (200, 170, 110))]

class Theme:
    def __init__(self, dark):
        self.dark = dark
        source = open(os.path.join(build.ROOT, 'patch', 'ipod_theme.c')).read()
        macros = dict(re.findall(r'#define (\w+) ([^\n]*)', source))
        literals = source.split('palettes[2] = {', 1)[1].split('};', 1)[0]
        for name, body in macros.items(): literals = literals.replace(name, body)
        words = [int(v, 16) for v in re.findall(r'0x([0-9a-f]+)u', literals)]
        assert len(words) == 38
        colors = [tuple((v >> k) & 255 for k in (0, 8, 16)) for v in words[19 * int(dark):19 * (int(dark) + 1)]]
        self.bg, self.fg, self.sub, self.np, self.body, self.pane, self.line = colors[:7]
        self.header, self.header_rule = colors[7:11], colors[11]
        self.progress_well, self.progress_edge = colors[12:14]
        self.battery_edge, self.battery_empty, self.mode = colors[14], colors[15:18], colors[18]
        self.ring = ((0x25, 0x25, 0x26), (0x1D, 0x1D, 0x1E)) if dark else ((0xF6,) * 3, (0xEE,) * 3)
        self.hub = ((0x36, 0x36, 0x38), (0x2A, 0x2A, 0x2C)) if dark else ((0xEE,) * 3, (0xCF,) * 3)
        self.label = (0xFF,) * 3 if dark else (0x9F, 0xA9, 0xB3)

def vgrad(im, box, top, bot):
    d = ImageDraw.Draw(im); x0, y0, x1, y1 = box
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0 - 1)
        d.line((x0, y, x1 - 1, y), fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bot)) + (255,))

def stops(im, box, points):
    d = ImageDraw.Draw(im); x0, y0, x1, y1 = box
    for y in range(y0, y1):
        p = (y - y0) * 100 // max(1, y1 - y0 - 1)
        i = next((i for i in range(1, len(points)) if p <= points[i][0]), len(points) - 1)
        a, b = points[i - 1], points[i]; n = max(1, b[0] - a[0]); k = p - a[0]
        rgb = tuple(v + int((w - v) * k / n) for v, w in zip(a[1], b[1]))
        d.line((x0, y, x1 - 1, y), fill=rgb + (255,))

def chevron(im, x, ymid, rgb, h=4):
    d = ImageDraw.Draw(im); d.line((x, ymid - h, x + h, ymid, x, ymid + h), fill=rgb + (255,), width=2)

def save_true(im, path):
    """True colour: a 256 colour median cut turned the battery's greens brown, so the Pod previews are not quantized."""
    im.convert('RGB').save(path, optimize=True)

def hexrgb(h): return ((h >> 16) & 255, (h >> 8) & 255, h & 255)
GREEN = [hexrgb(h) for h in (0xA4D08A, 0xDCF8C7, 0xC9ECB0, 0xA5E07F, 0xA1DE7D, 0x6BAB46, 0x4E932C, 0x539831, 0x5FA53E, 0x539831)]
RED = [hexrgb(h) for h in (0xD17F6B, 0xF0B2A8, 0xE89D90, 0xE87259, 0xE67357, 0xB74124, 0xA3300B, 0xA7340F, 0xB3421C, 0xA73410)]

def battery(im, x, y, th, fill=0.8, red=False):
    """The reference's 24 x 12 battery and 3 x 5 nub: a three-stop empty well, a ten-row fill in two bands inside the 1 px outline."""
    d = ImageDraw.Draw(im)
    stops(im, (x + 1, y + 1, x + 23, y + 11), [(0, th.battery_empty[0]), (50, th.battery_empty[1]), (100, th.battery_empty[2])])
    w = int(22 * fill)
    for i, c in enumerate(RED if red else GREEN):
        if w > 0: d.line((x + 1, y + 1 + i, x + w, y + 1 + i), fill=c + (255,))
    d.rectangle((x, y, x + 23, y + 11), outline=th.battery_edge + (255,)); d.rectangle((x + 24, y + 3, x + 26, y + 7), fill=th.battery_edge + (255,))

def play_glyph(im, x, y, pause=False):
    """The 12 x 14 play (a triangle) or pause glyph in the selection's blue, a row at a time down its gradient."""
    d = ImageDraw.Draw(im)
    for r in range(14):
        c = tuple(int(a + (b - a) * r / 14) for a, b in zip((0x5F, 0xB1, 0xF7), (0x0C, 0x62, 0xD2))) + (255,)
        if pause: d.line((x + 1, y + r, x + 4, y + r), fill=c); d.line((x + 7, y + r, x + 10, y + r), fill=c)
        else: d.line((x + 1, y + r, x + (min(r, 13 - r) + 1) * 10 // 7, y + r), fill=c)

def title_bar(s, im, th, title, h=24, right=None, clock=False, width=W, state='playing', pct=0.8):
    stops(im, (0, 0, width, h - 1), list(zip((0, 42, 47, 100), th.header)))
    ImageDraw.Draw(im).line((0, h - 1, width - 1, h - 1), fill=th.header_rule + (255,))
    s.text(im, pod_ui.OFFSETS['IP_TEXT_X'], h / 2, s.clip(title, 16, width - 8 - 27 - 8 - 12 - 6 - 8), 16, th.fg)
    if state: play_glyph(im, width - 8 - 27 - 8 - 12, h // 2 - 7, state == 'paused')
    battery(im, width - 8 - 27, h // 2 - 6, th, pct, pct <= 0.2)

def selection(im, y, h, th, x1=W):
    stops(im, (0, y, x1, y + h), [(0, (62,171,227)), (25, (55,160,224)), (50, (44,151,220)), (75, (33,140,214)), (100, (21,132,211))])
    d = ImageDraw.Draw(im); d.line((0, y, x1 - 1, y), fill=(154, 221, 248, 255)); d.line((0, y + h - 1, x1 - 1, y + h - 1), fill=(21, 79, 129, 255))

def rows(s, im, th, items, y0, rh, sel, x1=W, px=16, chev=True, tag=None, x=8):
    for i, t in enumerate(items):
        y = y0 + i * rh
        fg = th.fg
        if i == sel: selection(im, y, rh, th, x1); fg = (255, 255, 255)
        s.text(im, x, y + rh / 2, s.clip(t, px, x1 - x - 22), px, fg)
        if chev and i == sel: chevron(im, x1 - 14, y + rh // 2, fg)

def cover(rgb, size, r=0):
    c = PI.sample_cover(rgb, size)
    return c

def reflect(im, c, x, y, fade=0.35, hmax=None):
    f = c.transpose(Image.FLIP_TOP_BOTTOM); h = hmax or f.height // 3
    f = f.crop((0, 0, f.width, h)); a = Image.new('L', f.size)
    for yy in range(h): ImageDraw.Draw(a).line((0, yy, f.width, yy), fill=int(255 * fade * (1 - yy / h)))
    f.putalpha(a); im.alpha_composite(f, (x, y))

SHADOW = [int(v) for v in re.search(r'ip_shadow_alpha\[IP_SHADOW_W\] = \{([^}]*)\}', open(os.path.join(build.ROOT, 'patch', 'ipod.c')).read())[1].split(',')]

def shadow_layer():
    """The menu's shadow on the pane's left edge (IP_SHADOW_W columns of black, the alpha table of patch/ipod.c), straight alpha."""
    layer = Image.new('RGBA', (len(SHADOW), 240), (0, 0, 0, 0))
    for x, a in enumerate(SHADOW):
        for y in range(240): layer.putpixel((x, y), (0, 0, 0, a))
    return layer

def screen_main(s, th, sh, clock=True, shadow=True, rgb=(70, 110, 190)):
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); title_bar(s, im, th, 'Pod', width=160)
    rows(s, im, th, MENU, 24, 30, 0, x1=160)
    art = cover(rgb, 264)
    im.alpha_composite(art.crop((52, 12, 212, 252)), (160, 0))   # the pane is flush against the menu: no rule, but the menu's shadow
    if shadow: im.alpha_composite(shadow_layer(), (160, 0))
    return im

def screen_albums(s, th, sh):
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); title_bar(s, im, th, 'Albums', clock=True)
    rich_rows(s, im, th, [(a, artist) for (a, _), artist in zip(ALBUMS[:4], ('Miles Davis', 'Miles Davis', 'Björk', 'Portishead'))], 2, True)
    return im

def placeholder(size):
    return Image.open(os.path.join(build.ROOT, 'assets', 'icons', 'png', 'ipod_placeholder.png')).convert('RGBA').resize((size, size), Image.BOX)

def rich_rows(s, im, th, items, sel, chev=False, covers=None):
    """Cover rows: the 54 px cover fills its 54 px row exactly (flush top and left), 18 px title over a 16 px subtitle from x 62. A cover of None is the placeholder."""
    for i, (title, sub) in enumerate(items):
        y = 24 + i * 54
        selected = i == sel
        if selected: selection(im, y, 54, th)
        fg = (255, 255, 255) if selected else th.fg
        rgb = (covers or [a[1] for a in ALBUMS])[i]
        im.alpha_composite(placeholder(54) if rgb is None else cover(rgb, 54), (0, y))
        s.text(im, 62, y + 19, s.clip(title, 18, 236), 18, fg)
        s.text(im, 62, y + 40, s.clip(sub, 16, 236), 16, fg if selected else th.sub)
        if selected and chev: chevron(im, 306, y + 27, fg)

def playing_mark(th):
    """The playing track's speaker as ip_mode_bitmap makes it: the built 28 px white volume-2 glyph reduced to 14 px with a box filter over black (the coverage), mixed from white to the
    title bar glyph's blue, a row at a time down its gradient."""
    g = Image.open(os.path.join(build.ROOT, 'assets', 'icons', 'png', 'ipod_playing.png')).convert('RGBA')
    cov = Image.alpha_composite(Image.new('RGBA', g.size, (0, 0, 0, 255)), g).convert('L').resize((14, 14), Image.BOX)
    out = Image.new('RGBA', (14, 14), th.bg + (255,))
    for r in range(14):
        ink = tuple(int(a + (b - a) * r / 14) for a, b in zip((0x5F, 0xB1, 0xF7), (0x0C, 0x62, 0xD2)))
        out.paste(Image.new('RGBA', (14, 1), ink + (255,)), (0, r), cov.crop((0, r, 14, r + 1)))
    return out

def plain_rows(s, im, th, items, sel, title):
    """A song list: 30 px text rows, seven visible, no cover."""
    title_bar(s, im, th, title)
    for i, t in enumerate(items[:7]):
        y = 24 + i * 30
        if i == sel: selection(im, y, 30, th)
        s.text(im, 8, y + 15, s.clip(t, 18, 290), 18, (255, 255, 255) if i == sel else th.fg)
        if i == 2 and sel != 2: im.alpha_composite(playing_mark(th), (320 - 8 - 14, y + 8))   # the playing track's speaker

def screen_songs(s, th, sh):
    im = Image.new('RGBA', (W, sh), th.bg + (255,))
    plain_rows(s, im, th, ['So What', 'Teardrop', 'Jóga', 'Everything in Its Right Place', 'Paranoid Android', 'Karma Police', 'Roygbiv'], 1, 'Songs')
    return im

def screen_artist(s, th, sh):
    """An artist's albums: the stock All Songs record first with the placeholder cover."""
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); title_bar(s, im, th, 'Miles Davis')
    rich_rows(s, im, th, [('All Songs', ''), ('Kind of Blue', 'Miles Davis'), ('Sketches of Spain', 'Miles Davis'), ('Bitches Brew', 'Miles Davis')], 0, True,
              [None, (70, 110, 190), (190, 150, 70), (80, 130, 90)])
    return im

def screen_album_songs(s, th, sh):
    """A one-album artist: its songs directly, titled with the album."""
    im = Image.new('RGBA', (W, sh), th.bg + (255,))
    plain_rows(s, im, th, ['Hunter', 'Joga', 'Unravel', 'Bachelorette', 'All Neon Like', '5 Years', 'Immature'], 0, 'Homogenic')
    return im

def screen_music(s, th, sh):
    im = screen_main(s, th, sh); ImageDraw.Draw(im).rectangle((0, 0, 159, sh - 1), fill=th.bg + (255,))
    title_bar(s, im, th, 'Music', width=160)
    rows(s, im, th, MUSIC, 24, 30, 1, x1=160)
    return im

def screen_settings(s, th, sh):
    im = screen_main(s, th, sh)
    ImageDraw.Draw(im).rectangle((0, 0, 159, sh - 1), fill=th.bg + (255,))
    title_bar(s, im, th, 'Settings', width=160)
    for i, (label, value) in enumerate((('Shuffle', 'Off'), ('Repeat', 'Off'), ('Appearance', 'Dark' if th.dark else 'Light'))):
        y = 24 + 30 * i; selected = i == 2; fg = (255,)*3 if selected else th.fg
        if selected: selection(im, y, 30, th, 160)
        vw = min(72, s.font.width(value, 16))
        s.text(im, 8, y + 15, s.clip(label, 18, 160 - 8 - 8 - vw - 12), 18, fg)
        s.text(im, 152, y + 15, value, 16, fg if selected else (0x0C, 0x62, 0xD2), 'r')
    return im

def mode_mark(th, name):
    """The play mode mark as ip_mode_bitmap makes it: the built 32 px white glyph (name: shuffle, repeat, repeat1) reduced to 16 px with a box filter over black, whose value is the
    coverage, then mixed from the screen's colour to the mark's."""
    g = Image.open(os.path.join(build.ROOT, 'assets', 'icons', 'png', f'ipod_mode_{name}.png')).convert('RGBA')
    cov = Image.alpha_composite(Image.new('RGBA', g.size, (0, 0, 0, 255)), g).convert('L').resize((16, 16), Image.BOX)
    out = Image.new('RGBA', (16, 16), th.bg + (255,)); out.paste(Image.new('RGBA', (16, 16), th.mode + (255,)), (0, 0), cov)
    return out

def screen_now(s, th, sh, shuffle=False, cjk=False):
    o = pod_ui.OFFSETS
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); title_bar(s, im, th, 'Now Playing')
    side = o["IP_ART"]
    # A synthetic textured sleeve; the cover is drawn flat, square and unscaled, its reflection as ip_reflect makes it.
    art = Image.new('RGB', (side, side)); p = art.load()
    for y in range(side):
        for x in range(side): p[x, y] = (30 + x * 170 // side, 40 + y * 150 // side, 110 + (x + y) * 80 // (2 * side))
    ImageDraw.Draw(art).rectangle((16, 18, 134, 48), fill=(228, 220, 183))
    ImageDraw.Draw(art).ellipse((26, 60, 124, 140), fill=(30, 46, 69))
    im.alpha_composite(art.convert('RGBA'), (o['IP_NP_ART_X'], o['IP_NP_ART_Y']))
    refl = Image.new('RGBA', (side, o['IP_NP_REFLECT']), th.bg + (255,))
    for y in range(o['IP_NP_REFLECT']):   # a mirror of the cover's last rows, 30 % fading out
        a = (o['IP_NP_REFLECT'] - y) * 77 // o['IP_NP_REFLECT']
        for x in range(side):
            refl.putpixel((x, y), tuple(b + (c - b) * a // 255 for b, c in zip(th.bg, art.getpixel((x, side - 1 - y)))) + (255,))
    im.alpha_composite(refl, (o['IP_NP_ART_X'], o['IP_NP_ART_Y'] + side))
    if shuffle: im.alpha_composite(mode_mark(th, shuffle if isinstance(shuffle, str) else 'shuffle'), (o['IP_MODE_X'], o['IP_MODE_Y']))
    tx = o['IP_NP_TEXT_X']; title, artist, album = ('麦芽糖', '周杰伦', '11月的萧邦') if cjk else ('Yellow', 'Coldplay', 'Parachutes')
    s.text(im, tx, 74, s.clip(title, 18, W - tx - 8), 18, th.fg)
    s.text(im, tx, 98, s.clip(artist, 16, W - tx - 8), 16, th.np)
    s.text(im, tx, 119, s.clip(album, 16, W - tx - 8), 16, th.np)
    s.text(im, tx, 142, '1 / 12', 14, th.sub)
    py, bh, tx0, tw = o['IP_NP_BAR_Y'], o['IP_NP_BAR_H'], o['IP_NP_TRACK_X'], o['IP_NP_TRACK_W']
    fw = int(tw * 0.34)
    blue = [(0, (134, 171, 255)), (20, (107, 153, 245)), (58, (61, 137, 235)), (58, (54, 152, 249)), (82, (55, 176, 255)), (100, (92, 187, 255))]
    bar = Image.new('RGBA', (tw, bh), (255, 255, 255, 255))
    for i in range(bh):   # the track: white, its top and bottom edges shaded in; the outline rows
        g = 255 - ((4 - i) * 10 if i < 4 else (i - 10) * 6 if i > 10 else 0)
        ImageDraw.Draw(bar).line((0, i, tw - 1, i), fill=(g, g, g, 255))
    d = ImageDraw.Draw(bar); d.rectangle((0, 0, tw - 1, bh - 1), outline=th.progress_edge + (255,))
    stops(bar, (0, 0, fw, bh), blue)
    im.alpha_composite(bar, (tx0, py))
    mirror = bar.transpose(Image.FLIP_TOP_BOTTOM).crop((0, 0, tw, o['IP_NP_BAR_REFLECT']))
    fade = Image.new('L', mirror.size)
    for i in range(mirror.height): ImageDraw.Draw(fade).line((0, i, tw, i), fill=(mirror.height - i) * 77 // mirror.height)
    mirror.putalpha(fade); im.alpha_composite(mirror, (tx0, py + bh))
    s.text(im, 8, py + 5, '01:47', 15, th.fg); s.text(im, W - 8, py + 5, '-03:25', 15, th.fg, 'r')
    return im

def screen_cf(s, th, sh):
    """An approximation of the Cover Flow screen (patch/ipod_cf.c; the real renderer is the host-built one of test/coverflow.py): the IPCF_* numbers place an IPCF_ART px centre cover at
    IPCF_TOP under the bar, trapezoid side covers at IPCF_X1 / IPCF_XS, the reflection IPCF_REFLECT rows, the two caption lines at IPCF_CAP_Y."""
    o = pod_ui.OFFSETS
    im = Image.new('RGBA', (W, sh), th.bg + (255,)); art, top, y0 = o['IPCF_ART'], o['IPCF_TOP'], o['IPCF_FRAME_Y']
    for k in (-3, -2, -1, 3, 2, 1, 0):
        rgb = ALBUMS[(k + 3) % len(ALBUMS)][1]
        if k == 0:
            c = cover(rgb, art); x, y = (W - art) // 2, y0 + top; im.alpha_composite(c, (x, y)); reflect(im, c, x, y + art, 0.4, o['IPCF_REFLECT'])
        else:
            n = abs(k); h = int(art * (0.80 - 0.07 * (n - 1))); w = int(art * 0.30)
            sq = cover(rgb, art).resize((w, h), Image.LANCZOS)
            dst = sq.transform((w, h), Image.QUAD, (0, -6, 0, h + 6, w, h, w, 0) if k < 0 else (0, 0, 0, h, w, h + 6, w, -6), Image.BICUBIC)
            cx = W // 2 + (1 if k > 0 else -1) * (o['IPCF_X1'] + (n - 1) * o['IPCF_XS'])
            x = cx - w // 2; y = y0 + top + (art - h) // 2
            im.alpha_composite(dst, (x, y)); reflect(im, dst, x, y + h, 0.25, o['IPCF_REFLECT'] * 2 // 3)
    s.text(im, W // 2, o['IPCF_CAP_Y'] + o['IPCF_CAP_H'] / 2, 'Kind of Blue', 18, th.fg, 'm')
    s.text(im, W // 2, o['IPCF_CAP_Y'] + o['IPCF_CAP_H'] * 1.5, 'Miles Davis', 18, th.fg, 'm')
    title_bar(s, im, th, 'Cover Flow')
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
    ImageDraw.Draw(im).rectangle((0, top + sh, W - 1, H - 1), fill=th.body + (255,))
    im.alpha_composite(s.img('ipod_wheel_dark' if th.dark else 'ipod_wheel'), (50, 250))
    return im

def main():
    work = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'ipod-mock.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    s = PI.Side(work, True)
    frames = []
    for dark in (False, True):
        th = Theme(dark); name = 'Dark' if dark else 'Light'
        pages = [('Main menu', screen_main(s, th, 240)), ('Music', screen_music(s, th, 240)),
                 ('Settings', screen_settings(s, th, 240)), ('Albums', screen_albums(s, th, 240)),
                 ('Songs', screen_songs(s, th, 240)), ('Now Playing', screen_now(s, th, 240, "repeat1" if dark else "shuffle", dark)), ("Cover Flow", screen_cf(s, th, 240))]
        frames += [(f'{name}: {label}', frame(s, th, page, 240)) for label, page in pages]
    pad, lab, cols = 12, 22, 7
    sheet = Image.new('RGB', (pad + cols * (W + pad), 2 * (lab + H + pad) + pad), (0x2A,) * 3); d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(frames):
        x, y = pad + (i % cols) * (W + pad), pad + (i // cols) * (lab + H + pad)
        d.text((x, y - 2), t, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, y + lab))
    save_true(sheet, out); print('wrote', out, sheet.size)
    # The same smoothstep slide and half-width clipping / split as ipod_render.c and ipod.c ip_paint_split.
    duration = cdefs.defines(os.path.join(build.ROOT, 'patch', 'ipod_render.c'), ['SLIDE_MS'])['SLIDE_MS']
    th = Theme(False)
    stem = os.path.splitext(out)[0]
    music, main_, now = screen_music(s, th, 240), screen_main(s, th, 240), screen_now(s, th, 240, "shuffle")
    main_ns = screen_main(s, th, 240, shadow=False)   # the halves of a split move apart: the shadow goes with the menu half
    def travel_at(ms, span):
        p = ms * 1024 // duration; return span * ((p * p // 1024) * (3072 - 2 * p) // 1024) // 1024
    def push_half(ms):   # Main -> Music: the menu half slides, the pane stays
        t = travel_at(ms, 160); page = main_.copy(); left = Image.new('RGBA', (160, 240), th.bg + (255,))
        left.alpha_composite(main_.crop((0, 0, 160, 240)), (-t, 0)); left.alpha_composite(music.crop((0, 0, 160, 240)), (160 - t, 0)); page.paste(left, (0, 0)); return page
    def split_open(ms):   # Main -> Now Playing: Now Playing stays, the menu half goes left and the pane right
        t = travel_at(ms, 160); page = now.copy()
        page.paste(main_ns.crop((160, 0, 320, 240)), (160 + t, 0)); page.paste(main_ns.crop((0, 0, 160, 240)), (-t, 0)); page.alpha_composite(shadow_layer(), (160 - t, 0)); return page
    def split_close(ms):   # Now Playing -> Main: the halves come back in over it
        t = travel_at(ms, 160); page = now.copy()
        page.paste(main_ns.crop((160, 0, 320, 240)), (160 + (160 - t), 0)); page.paste(main_ns.crop((0, 0, 160, 240)), (-(160 - t), 0)); page.alpha_composite(shadow_layer(), (t, 0)); return page
    def full_push(ms):   # Music -> Albums: 320 px
        t = travel_at(ms, 320); page = Image.new('RGBA', (W, 240), th.bg + (255,)); page.paste(music, (-t, 0)); page.paste(screen_albums(s, th, 240), (320 - t, 0)); return page
    steps = [0, duration // 4, duration // 2, duration * 3 // 4, duration]
    rows_ = [('Main > Music: the menu half slides (the pane stays)', push_half), ('Main > Now Playing: the split open', split_open),
             ('Now Playing > Main: the split closes', split_close), ('Music > Albums: the whole width', full_push)]
    strip = Image.new('RGB', (pad + 5 * (W + pad), len(rows_) * (240 + lab + pad) + pad), (42,) * 3)
    sd = ImageDraw.Draw(strip); animation = []
    for r, (label, fn) in enumerate(rows_):
        for i, ms in enumerate(steps):
            x, y = pad + i * (W + pad), pad + r * (240 + lab + pad)
            strip.paste(fn(ms).convert('RGB'), (x, y + lab)); sd.text((x, y), f'{label}  {ms} ms' if i == 0 else f'{ms} ms', fill=(210,) * 3)
    save_true(strip, stem + '-transitions.png')
    for fn in (split_open, push_half):
        animation += [frame(s, th, fn(ms), 240).convert('RGB') for ms in range(0, duration + 1, 40)]
    animation[0].save(stem + '-transition.gif', save_all=True, append_images=animation[1:], duration=40, loop=0)
    # The cover pane: a cover pans linearly for 7.5 s, the next fades in 6 s after it began over 1.5 s (smoothstep), both panning; whole-pixel windows of one scaled cover each.
    r_, x0 = pod_ui.OFFSETS['IP_PANE_R'], 40
    pan_, hold_, fade_ = (pod_ui.OFFSETS[k] for k in ('IP_PANE_PAN_MS', 'IP_PANE_HOLD_MS', 'IP_PANE_FADE_MS'))
    a_art, b_art = cover((70, 110, 190), 264), cover((190, 90, 120), 264)
    def window(art, pos):
        """The pane's 160 x 240 window at pos / 256 px: each pixel the linear mix of its source column and the next (a bilinear sample on an exact row), as ip_pane_frame."""
        return art.transform((160, 240), Image.AFFINE, (1, 0, x0 + pos / 256, 0, 1, 12), Image.BILINEAR)
    def pane_at(ms):
        pa = r_ * 256 * ms // pan_; pb = r_ * 256 - r_ * 256 * max(0, ms - hold_) // pan_   # 1/256 px, as ip_pane_pos
        wa = window(a_art, pa)
        if ms < hold_: return wa
        wb = window(b_art, pb); p = min(1023, (ms - hold_) * 1024 // fade_)
        return Image.blend(wa, wb, ((p * p // 1024) * (3072 - 2 * p) // 1024) / 1024)
    times = [0, 3000, 6000, 6375, 6750, 7125, 7500]
    pstrip = Image.new('RGB', (pad + len(times) * (W + pad), 240 + lab + 2 * pad), (42,) * 3); pd = ImageDraw.Draw(pstrip)
    for i, ms in enumerate(times):
        page = main_ns.copy(); page.paste(pane_at(ms), (160, 0)); page.alpha_composite(shadow_layer(), (160, 0)); x = pad + i * (W + pad)
        pstrip.paste(page.convert('RGB'), (x, pad + lab)); pd.text((x, pad), f'{ms / 1000:.2f} s', fill=(210,) * 3)
    save_true(pstrip, stem + '-pane.png')
    # The pan itself: 40 ms frames (3 s of it) as a GIF, and six consecutive frames of a detail, 6 x, each a fraction of a pixel on from the last.
    pan_frames = [frame(s, th, (lambda pg: (pg.paste(pane_at(ms), (160, 0)), pg.alpha_composite(shadow_layer(), (160, 0)), pg)[2])(main_ns.copy()), 240).convert('RGB') for ms in range(0, 3000, 40)]
    pan_frames[0].save(stem + '-pan.gif', save_all=True, append_images=pan_frames[1:], duration=40, loop=0)
    strip6 = Image.new('RGB', (6 * 8 + 6 * 360, 360 + 20), (42,) * 3)
    for i in range(6):
        win = pane_at(1000 + 40 * i).crop((14, 100, 74, 160)).resize((360, 360), Image.NEAREST)
        strip6.paste(win.convert('RGB'), (8 + i * 368, 10))
    save_true(strip6, stem + '-pan-frames.png')
    # The menu's shadow on a light cover and on the plain pane, 10 x: darkest at x 160, gone by x 170.
    edge = Image.new('RGB', (2 * 500 + 30, 600 + 20), (42,) * 3)
    for i, rgb in enumerate(((235, 220, 175), None)):
        page = screen_main(s, th, 240, rgb=rgb or (0, 0, 0))
        if rgb is None: page.paste(Image.new('RGBA', (160, 240), (0xF2, 0xF3, 0xF5, 255)), (160, 0)); page.alpha_composite(shadow_layer(), (160, 0))
        edge.paste(page.crop((140, 60, 190, 120)).resize((500, 600), Image.NEAREST).convert('RGB'), (10 + i * 510, 10))
    save_true(edge, stem + '-edge.png')
    # The reference's palette beside ours: title bar, selection, battery, Now Playing bar (the numbers of iPlayr's colour sets).
    ref = Image.new('RGBA', (W, 120), (255, 255, 255, 255))
    stops(ref, (0, 0, W, 25), list(zip((0, 42, 47, 100), [hexrgb(h) for h in (0xFDFDFD, 0xE7E7E7, 0xD8D8D8, 0xABABAB)])))
    stops(ref, (0, 40, W, 67), [(0, hexrgb(0x3EABE3)), (25, hexrgb(0x37A0E0)), (50, hexrgb(0x2C97DC)), (75, hexrgb(0x218CD6)), (100, hexrgb(0x1584D3))])
    battery(ref, 8, 6, th); battery(ref, 50, 6, th, 0.15, True); play_glyph(ref, 100, 5)
    for i in range(14): ImageDraw.Draw(ref).line((8, 80 + i, 8 + 150, 80 + i), fill=hexrgb(0x3698F9) + (255,))
    sheet2 = Image.new('RGB', (W, 240), (42,) * 3)
    ours = screen_main(s, th, 240).crop((0, 0, 160, 120)); sheet2.paste(ours.convert('RGB'), (0, 0)); sheet2.paste(ref.crop((0, 0, W, 120)).convert('RGB'), (0, 120))
    save_true(sheet2, stem + '-palette.png')
    # The battery at 100, 60 and 20 % (the title bar's right end, in both appearances' screen), 6 x.
    cells = []
    for pct in (1.0, 0.6, 0.2):
        bar = Image.new('RGBA', (70, 24), th.bg + (255,)); title_bar(s, bar, th, '', width=70, state='playing', pct=pct); cells.append(bar.resize((420, 144), Image.NEAREST))
    levels = Image.new('RGB', (3 * 420 + 4 * 8, 160), (42,) * 3)
    for i, c in enumerate(cells): levels.paste(c.convert('RGB'), (8 + i * 428, 8))
    save_true(levels, stem + '-battery.png')
    # An artist's albums (All Songs first, placeholder covers) and a one-album artist's song list, with the wheel.
    pair = Image.new('RGB', (pad + 2 * (W + pad), 240 + lab + 2 * pad), (42,) * 3); pdr = ImageDraw.Draw(pair)
    for i, (label, page) in enumerate((('Artist: All Songs first', screen_artist(s, th, 240)), ('One-album artist: its songs', screen_album_songs(s, th, 240)))):
        pair.paste(page.convert('RGB'), (pad + i * (W + pad), pad + lab)); pdr.text((pad + i * (W + pad), pad), label, fill=(210,) * 3)
    save_true(pair, stem + '-artists.png')
    # The three play mode marks on Now Playing's top right, light and dark appearance's screen alike, 6 x.
    marks = Image.new('RGB', (3 * 8 + 3 * 6 * 80, 6 * 32 + 16), (42,) * 3)
    for i, name in enumerate(('shuffle', 'repeat', 'repeat1')):
        crop = screen_now(s, th, 240, name).crop((240, 24, 320, 56)).resize((480, 192), Image.NEAREST)
        marks.paste(crop.convert('RGB'), (8 + i * 488, 8))
    save_true(marks, stem + '-marks.png')

if __name__ == '__main__':
    main()
