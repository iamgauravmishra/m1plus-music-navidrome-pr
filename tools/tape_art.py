#!/usr/bin/env python3
"""The Tape page's art (docs/modules/tape.md): the drawing code of the approved mock, shared by tools/preview_tape.py (the full mock frames) and by the
build (the installed images, `images()`; tools/mod_icons.py puts them in the tree and assets/icons/png keeps the generated files).

The page is LANDSCAPE, 480 x 320 (W x H); the panel is portrait 320 x 480, so the landscape picture is turned 90 degrees clockwise onto the framebuffer:
landscape pixel (x, y) is the framebuffer pixel (column 319 - y, row x) (`rot`). The images are made in landscape and turned once here; patch/tape.c
works in framebuffer pixels (offsets.inc TP_*; test/pod/tape.py checks the numbers).

Layers (the page composes them at run time, patch/tape.c). Shared by every theme: tape_top, tape_screw, tape_tex. One a theme (<name>_<theme>, THEME_NAMES): tape_shell, tape_hubs, tape_marks.
  tape_shell_*  320 x 480, opaque (RGBA, alpha 255): the whole cassette (shell, screws, label paper and band, ruled lines, the panel, the holes, the clear window, the
                direction arrow) but no text, no marks, no tape, no gear rings, no hubs, no scale.
  tape_tex      320 x 480 (RGBA): the grain's amplitude (green) and the knurl's strength (red) the page lays on the shell when it opens (`finish`): tape_shell_* is smooth.
  tape_top      the window overlay (TOP_RECT, turned: 74 x 280, RGBA): the holes' gear rings and lips, the clear window's scale and bevel. Drawn over the tape packs.
  tape_hubs_*   the reel hub turned in 5 degree steps (6 teeth: 12 frames), each HUB_PX x HUB_PX turned with the picture, stacked: HUB_PX x 12 * HUB_PX, RGBA, in the theme's hub colour.
  tape_marks_*  the label's printed marks, MARK_PX x MARK_PX each, stacked: play, pause, repeat. RGBA, in the theme's band ink.
  tape_screw    the close screw pressed (the top left one), MARK_PX x MARK_PX: darker, its slot turned 45 degrees.
Text is not in any image: the page draws it with the device font (the glyph alpha blended in turned, as Cover Flow's landscape captions).
Shapes are drawn at K x and reduced. Deterministic (fixed seeds).
"""
import math, os
from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H, K = 480, 320, 3            # landscape screen; supersampling factor of the shape layer
CASS = (5, 10, 475, 310)         # the cassette
LABEL = (37, 37, 443, 220)       # centred on x 240 like the cassette, the panel, the window and the reels: 32 px of shell each side
PANEL = (84, 106, 396, 188)      # the black inner panel
CLEAR = (180, 112, 300, 182)     # the clear window between the reel holes
BG = (0x11, 0x11, 0x12)
GOLD = (0xD9, 0xB2, 0x5E)
TOP_RECT = (100, 110, 380, 184)  # the window overlay's rectangle (landscape): holes with their rings, the clear window
MARK_PX = 26                     # a printed mark's cell
PLAY_AT, REPEAT_AT = (423, 128), (423, 166)   # the marks' centres on the band
ARROW_AT = (179, 206)
SCREW_AT = (24, 25)              # the top left screw (landscape): the close button; its pressed look is tape_screw
CLOSE_RECT = (0, 0, 50, 50)      # its touch area (landscape, x0, y0, x1, y1 exclusive): 50 x 50 around the screw
PRESSED = dict(dim=0.4, turn=45)
SCREWS = ((24, 25), (456, 25), (24, 295), (456, 295), (240, 257))   # four corners and the bottom centre
SCREW_TURN = {(456, 25): 52, (24, 295): -28, (456, 295): 17, (240, 257): 71}   # each screw's slot angle (degrees); the close screw stays at 0, its pressed look turns it 45

# ---- the tape ----------------------------------------------------------------------------------------------------------
HUB_R, HOLE_R, PACK_MIN, PACK_MAX = 14, 28, 16, 66   # px: hub, reel hole, empty-reel and full-reel tape pack
HUB_PX = 30                                          # the hub sprite's cell (2 * HUB_R + 2)
REEL_CX, REEL_CY = (132, 348), 147                   # supply (left), take-up (right)
TEETH, SPRITES = 6, 24                               # the ring has 6 teeth (60 degrees), the drive 3 spokes (120): the picture repeats every 120 degrees, 24 frames of 5

THEMES = {   # the user's choice (Settings > Now Playing > Theme, saved as the index in THEME_NAMES); more themes can be added as data
    'normal': dict(shell=(0x3A, 0x3D, 0x42), paper=((0xF3, 0xF1, 0xE8), (0xE6, 0xE3, 0xD7)), ink=(0x1B, 0x1F, 0x2A), sub=(0x4A, 0x52, 0x62),
                   band=(0x3C, 0x78, 0xBE), band_ink=(255, 255, 255), print=(0x3C, 0x78, 0xBE), hub=(0xE9, 0xE7, 0xDF),
                   model='TYPE I NORMAL', rule_a=0.20, tone_mix=0.30),
    'chrome': dict(shell=(0x24, 0x27, 0x2C), paper=((0xDF, 0xE2, 0xE6), (0xC4, 0xC8, 0xCE)), ink=(0x12, 0x14, 0x18), sub=(0x3A, 0x3E, 0x48),
                   band=(0xC0, 0x3A, 0x3A), band_ink=(255, 255, 255), print=(0xC0, 0x3A, 0x3A), hub=(0xD6, 0xDA, 0xDF),
                   model='TYPE II CHROME', rule_a=0.25, tone_mix=0.30),
    'metal': dict(shell=(0x1E, 0x18, 0x12), paper=((0x26, 0x20, 0x18), (0x16, 0x12, 0x0D)), ink=GOLD, sub=(0xA8, 0x88, 0x48),
                  band=(0x2A, 0x24, 0x1A), band_ink=GOLD, print=GOLD, hub=(0xDD, 0xD6, 0xC4),
                  model='TYPE IV METAL', rule_a=0.30, tone_mix=0.0),
}

# ---- the text, landscape (x, the line's vertical middle, px, colour key, anchor) and the rectangle each field may touch -------------------------
# The rectangle is what the page restores from the shell before it draws the field again and clips the glyphs to (ruled lines inside it are restored with it); the
# rectangles of the fields on the label do not overlap, so a field redrawn never wipes a neighbour's glyphs (a descender may reach the line below its own).
TEXT = {
    'title':  dict(x=47,  y=49,  px=22, colour='ink',        anchor='l', room=388, rect=(43, 37, 439, 62)),
    'artist': dict(x=47,  y=70,  px=16, colour='ink',        anchor='l', room=388, rect=(43, 62, 439, 83)),
    'album':  dict(x=47,  y=89,  px=13, colour='sub',        anchor='l', room=190, rect=(43, 83, 243, 99)),
    'times':  dict(x=435, y=89,  px=12, colour='sub',        anchor='r', room=100, rect=(325, 83, 439, 99)),
    'big':    dict(x=65,  y=146, px=54, colour='band_ink',   anchor='m', room=400, rect=(39, 112, 97, 182), bold=True),
    'model':  dict(x=47,  y=206, px=12, colour='print',      anchor='l', room=130, rect=(41, 195, 175, 218)),   # the fine print: type and grade, small, in the print's mid tone
    'status': dict(x=435, y=206, px=12, colour='sub',        anchor='r', room=212, rect=(219, 195, 441, 219)),
}
STATUS_W = 212   # the room right of the direction arrow on the strip below the band

def S(v): return int(round(v * K))

def box(b): return tuple(S(v) for v in b)

def mix(a, b, t): return tuple(int(x + (y - x) * t) for x, y in zip(a, b))

def vgrad(size, top, bot):
    """A vertical gradient image (size in supersampled px)."""
    g = Image.new('RGBA', size); d = ImageDraw.Draw(g)
    for y in range(size[1]): d.line((0, y, size[0], y), fill=mix(top, bot, y / max(1, size[1] - 1)) + (255,))
    return g

# ---- masks, bevels, texture -------------------------------------------------------------------------------------------------
def rr_mask(size, b, r):
    m = Image.new('L', size, 0); x0, y0, x1, y1 = box(b)
    ImageDraw.Draw(m).rounded_rectangle((x0, y0, x1 - 1, y1 - 1), S(r), fill=255); return m

def poly_mask(size, pts):
    m = Image.new('L', size, 0); ImageDraw.Draw(m).polygon([(S(x), S(y)) for x, y in pts], fill=255); return m

def fill_mask(im, m, rgb, a=255):
    """Paint rgb through the mask m (scaled by a)."""
    if a < 255: m = m.point(lambda v: v * a // 255)
    im.paste(Image.new('RGBA', im.size, rgb + (255,)), (0, 0), m)

def gradient_in(im, m, b, top, bot):
    g = Image.new('RGBA', im.size); x0, y0, x1, y1 = box(b); g.paste(vgrad((x1 - x0, y1 - y0), top, bot), (x0, y0)); im.paste(g, (0, 0), m)

def bevel(im, m, light, dark, w=1.6, raised=True, a=190):
    """A moulded edge from the light at the top left: the mask's top-left rim in `light`, its bottom-right rim in `dark` (swapped if recessed)."""
    o = S(w)
    lt = ImageChops.subtract(m, ImageChops.offset(m, o, o)); db = ImageChops.subtract(m, ImageChops.offset(m, -o, -o))
    if not raised: lt, db = db, lt
    fill_mask(im, lt, light, a); fill_mask(im, db, dark, a)

_FLAT = [None]
def noise(seed, amp):
    """Where a surface takes grain of amplitude amp (alpha, of 255; seed names the surface). The grain itself is not drawn here: it is noise no PNG packs (it was two thirds of
    each shell picture), so the page adds it at 1:1 when it opens (`finish`, patch/tape.c tp_finish) by the amplitude tape_tex holds. This layer is clear, or, while shell_parts
    measures that amplitude, a flat white or black of alpha amp (_FLAT)."""
    c = _FLAT[0]
    return Image.new('RGBA', (W * K, H * K), (0, 0, 0, 0) if c is None else (c, c, c, amp))

def overlay(im, layer, m):
    l = layer.copy(); l.putalpha(ImageChops.multiply(l.getchannel('A'), m)); im.alpha_composite(l)

def glow_shadow(im, m, dx, dy, blur, a):
    sh = Image.new('L', im.size, 0); sh.paste(ImageChops.offset(m, S(dx), S(dy)))
    sh = sh.filter(ImageFilter.GaussianBlur(S(blur))).point(lambda v: v * a // 255); fill_mask(im, sh, (0, 0, 0))

# ---- the reels ---------------------------------------------------------------------------------------------------------
def pack_radii(p):
    """(supply, take-up) pack radii at position fraction p; the tape area (r^2) is conserved."""
    p = min(1.0, max(0.0, p)); tot = PACK_MAX ** 2 + PACK_MIN ** 2
    take2 = PACK_MIN ** 2 + (PACK_MAX ** 2 - PACK_MIN ** 2) * p
    return math.sqrt(tot - take2), math.sqrt(take2)

def sprite_index(angle):
    """Which of the 24 pre-rendered frames shows a reel turned by `angle` degrees (the picture repeats every 120: the ring's 6 teeth every 60, the drive's 3 spokes every 120)."""
    return int((angle % (360 / 3)) // (360 / 3 / SPRITES)) % SPRITES

_SPRITES = {}
def hub_sprite(angle, rgb):
    """The hub (HUB_R px radius, supersampled RGBA) turned by `angle` degrees: a white translucent plastic ring with six teeth pointing inward round a dark opening,
    a pale disc in the middle with a dark 3-spoke drive and its pin. Quantised to the 5 degree frame sprite_index() gives (24 frames, a 120 degree cycle)."""
    i = sprite_index(angle)
    if (i, rgb) in _SPRITES: return _SPRITES[i, rgb]
    a0 = i * (360 / 3 / SPRITES); n = S(2 * HUB_R + 2); c = n / 2; R = S(HUB_R)
    im = Image.new('RGBA', (n, n), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.ellipse((c - R, c - R, c + R, c + R), fill=rgb + (236,), outline=mix(rgb, (0, 0, 0), 0.5) + (255,), width=1)
    d.arc((c - R + K, c - R + K, c + R - K, c + R - K), 200, 250, fill=(255, 255, 255, 190), width=K)   # the plastic's specular edge
    hole = R * 0.70
    d.ellipse((c - hole, c - hole, c + hole, c + hole), fill=(0x0B, 0x0B, 0x0C, 255))
    for k in range(TEETH):   # a tooth: a small rectangle from the ring inward
        a = math.radians(a0 + k * 360 / TEETH); ux, uy = math.cos(a), math.sin(a); vx, vy = -uy, ux
        r_out, r_in, hw = hole + K, R * 0.56, R * 0.07
        d.polygon([(c + ux * r_out + vx * hw, c + uy * r_out + vy * hw), (c + ux * r_out - vx * hw, c + uy * r_out - vy * hw),
                   (c + ux * r_in - vx * hw, c + uy * r_in - vy * hw), (c + ux * r_in + vx * hw, c + uy * r_in + vy * hw)], fill=rgb + (255,))
    disc = R * 0.46
    d.ellipse((c - disc, c - disc, c + disc, c + disc), fill=mix(rgb, (0, 0, 0), 0.12) + (215,))
    for k in range(3):   # the dark 3-spoke drive
        a = math.radians(a0 + 90 + k * 120); ux, uy = math.cos(a), math.sin(a); vx, vy = -uy, ux; hw = R * 0.095
        d.polygon([(c + vx * hw, c + vy * hw), (c + ux * disc * 0.92 + vx * hw, c + uy * disc * 0.92 + vy * hw),
                   (c + ux * disc * 0.92 - vx * hw, c + uy * disc * 0.92 - vy * hw), (c - vx * hw, c - vy * hw)], fill=(0x16, 0x16, 0x18, 255))
    d.ellipse((c - R * 0.13, c - R * 0.13, c + R * 0.13, c + R * 0.13), fill=(0x16, 0x16, 0x18, 255))
    im = lit_hub(im)
    _SPRITES[i, rgb] = im
    return im

def lit_hub(sp):
    """The hub lit from the top left (the light is static: applied to each frame after its turn) with a soft shadow under it on the tape."""
    sp = sp.copy(); n = sp.width; px = sp.load()
    for y in range(n):
        for x in range(n):
            r, g, b, a = px[x, y]
            if not a: continue
            f = 1.14 - 0.46 * (x + y) / (2 * (n - 1))
            px[x, y] = (min(255, int(r * f)), min(255, int(g * f)), min(255, int(b * f)), a)
    sh = ImageChops.offset(sp.getchannel('A'), K, int(1.5 * K)).filter(ImageFilter.GaussianBlur(K * 0.9)).point(lambda v: v * 170 // 255)
    out = Image.new('RGBA', sp.size, (0, 0, 0, 0)); out.putalpha(sh); out.alpha_composite(sp)
    return out

PK_BASE, PK_HI = (0x22, 0x15, 0x0E), (0x6C, 0x4F, 0x38)
PK_WIND = [round(32 + 32 * math.sin(2 * math.pi * i / 32)) for i in range(32)]   # the windings, one period per 2 px of distance (patch/tape.c pk_wind)

def pack_rgb(d, R, dx, dy):
    """The tape pack's colour at distance d from the reel's centre, pack radius R (both 1/16 px), the pixel at (dx, dy) half pixels from the centre: a smooth near-black brown with
    a static bow-tie sheen (|cos|^14 of the angle from the upper-left / lower-right axis, the lower right x 0.45), fine 2 px windings, a lighter ring just inside the edge and a dark
    edge. The device's integer arithmetic (patch/tape.c tp_pack) to the bit."""
    s = -dx - dy
    u = min(65535, (s * s << 15) // (dx * dx + dy * dy))
    u2 = u * u >> 16
    lobe = ((u2 * u2 >> 16) * u2 >> 16) * u >> 16
    if s < 0: lobe = lobe * 115 >> 8
    w = PK_WIND[d & 31]
    mb = 236 + (w * 13 >> 5)
    k = lobe * (179 + (w * 77 >> 6)) >> 8
    e = 115 if d > R - 16 else 287 if d > R - 35 else 256
    return tuple(min(255, ((b * mb >> 8) + ((h - b) * k >> 16)) * e >> 8) for b, h in zip(PK_BASE, PK_HI))

def packs(size, p):
    """Both tape packs (supersampled RGBA, not yet clipped): the device's pack_rgb at each 1:1 pixel's centre (one 1:1 pixel is K x K supersampled ones), its rim anti-aliased by the
    coverage of the pixel's distance as the page does."""
    im = Image.new('RGBA', size); rs, rt = pack_radii(p); x0, y0, x1, y1 = (v * K for v in TOP_RECT)
    sq = Image.new('RGBA', (x1 - x0, y1 - y0)); px = sq.load()
    for cx, r in ((REEL_CX[0], rs), (REEL_CX[1], rt)):
        R = math.isqrt(int(r * r * 256))
        for y in range(TOP_RECT[1], TOP_RECT[3]):
            dy = 2 * (y - REEL_CY) + 1
            for x in range(max(TOP_RECT[0], cx - 70), min(TOP_RECT[2], cx + 71)):
                dx = 2 * (x - cx) + 1; d = math.isqrt((dx * dx + dy * dy) << 6)
                if d > R + 8: continue
                cov = min(16, R + 8 - d); c = pack_rgb(d, R, dx, dy) + (cov * 255 // 16,)
                for j in range(K):
                    for i in range(K): px[(x - TOP_RECT[0]) * K + i, (y - TOP_RECT[1]) * K + j] = c
    im.paste(sq, (x0, y0)); return im

# ---- details: screws, holes, marks -------------------------------------------------------------------------------------------
def screw(im, x, y, dim=0.0, turn=0):
    """A recessed Phillips screw: a dark countersunk ring, a metal head, a cross slot, a specular highlight. dim (0 .. 1) darkens the head and turn (degrees) turns the slot:
    the pressed look of the screw that is the close button."""
    d = ImageDraw.Draw(im); R = 8.5; dk = lambda c: mix(c, (0, 0, 0), dim)
    d.ellipse((S(x - R), S(y - R), S(x + R), S(y + R)), fill=(0x06, 0x06, 0x07, 255))
    d.arc((S(x - R), S(y - R), S(x + R), S(y + R)), 20, 200, fill=(0xFF, 0xFF, 0xFF, 60), width=K)   # the lit lower-right lip
    r = 6.2
    for i in range(7):   # head: a radial-ish shading by stacked discs, lit from the top left
        t = i / 6; rr = r * (1 - 0.1 * i); o = -0.18 * i * 1.3
        d.ellipse((S(x - rr + o), S(y - rr + o), S(x + rr + o), S(y + rr + o)), fill=dk(mix((0x7C, 0x7E, 0x82), (0xCF, 0xD1, 0xD4), t)) + (255,))
    d.ellipse((S(x - r), S(y - r), S(x + r), S(y + r)), outline=(0x30, 0x31, 0x34, 255), width=1)
    for a in (35 + turn, 125 + turn):   # the cross slot, turned a little
        ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
        d.line((S(x - ca * 4.4), S(y - sa * 4.4), S(x + ca * 4.4), S(y + sa * 4.4)), fill=(0x1E, 0x1F, 0x22, 255), width=int(1.7 * K))
    d.ellipse((S(x - 3.6), S(y - 4.6), S(x - 1.8), S(y - 3.0)), fill=(255, 255, 255, int(230 * (1 - dim))))

def round_hole(im, x, y, r):
    """A hole with real depth: dark inside (an inner shadow on its upper left), a lit lower lip."""
    d = ImageDraw.Draw(im)
    d.ellipse((S(x - r - 1.5), S(y - r - 1.5), S(x + r + 1.5), S(y + r + 1.5)), fill=(0x00, 0x00, 0x00, 110))
    d.ellipse((S(x - r), S(y - r), S(x + r), S(y + r)), fill=(0x04, 0x04, 0x05, 255))
    d.arc((S(x - r), S(y - r), S(x + r), S(y + r)), 180, 300, fill=(0x00, 0x00, 0x00, 255), width=2 * K)
    d.ellipse((S(x - r * 0.5), S(y - r * 0.25), S(x + r * 0.25), S(y + r * 0.5)), fill=(0x16, 0x16, 0x18, 255))
    d.arc((S(x - r - 0.5), S(y - r - 0.5), S(x + r + 0.5), S(y + r + 0.5)), 20, 160, fill=(0xB4, 0xB4, 0xBC, 200), width=K)   # the lit lower lip

def square_hole(im, b):
    d = ImageDraw.Draw(im); x0, y0, x1, y1 = b
    d.rectangle(box((x0 - 1, y0 - 1, x1 + 1, y1 + 1)), fill=(0x00, 0x00, 0x00, 110)); d.rectangle(box(b), fill=(0x04, 0x04, 0x05, 255))
    d.rectangle(box((x0, y0, x1, y0 + 2)), fill=(0, 0, 0, 255)); d.rectangle(box((x0 + 2, y0 + 5, x1 - 1, y1 - 1)), fill=(0x16, 0x16, 0x18, 255))
    d.rectangle((S(x0 - 1), S(y1 + 1) - 1, S(x1 + 1), S(y1 + 1) + 1), fill=(0xB4, 0xB4, 0xBC, 190))   # the lit lower lip, one whole pixel

def repeat_glyph(im, cx, cy, rgb, w=2.4):
    """The auto-reverse arrows printed on the label (about 24 x 20 px)."""
    d = ImageDraw.Draw(im); c = rgb + (255,)
    top = [(cx - 11, cy + 1), (cx - 11, cy - 6), (cx + 5, cy - 6)]; bot = [(cx + 11, cy - 1), (cx + 11, cy + 6), (cx - 5, cy + 6)]
    for pts in (top, bot): d.line([(S(x), S(y)) for x, y in pts], fill=c, width=int(w * K), joint='curve')
    d.polygon([(S(cx + 3), S(cy - 11)), (S(cx + 3), S(cy - 1)), (S(cx + 11), S(cy - 6))], fill=c)
    d.polygon([(S(cx - 3), S(cy + 1)), (S(cx - 3), S(cy + 11)), (S(cx - 11), S(cy + 6))], fill=c)

def state_mark(im, cx, cy, playing, rgb):
    d = ImageDraw.Draw(im); c = rgb + (255,)
    if playing: d.polygon([(S(cx - 6), S(cy - 9)), (S(cx - 6), S(cy + 9)), (S(cx + 9), S(cy))], fill=c)
    else:
        for x in (cx - 8, cx + 2): d.rectangle((S(x), S(cy - 9), S(x + 6), S(cy + 9)), fill=c)

def vgrad3(size, c0, c1, c2):
    """A vertical gradient through three colours (size in supersampled px)."""
    g = Image.new('RGBA', size); d = ImageDraw.Draw(g)
    for y in range(size[1]):
        u = y / max(1, size[1] - 1); c = mix(c0, c1, u * 2) if u < 0.5 else mix(c1, c2, (u - 0.5) * 2)
        d.line((0, y, size[0], y), fill=c + (255,))
    return g

def foil(im, m, rgb, bounds):
    """Printed ink: the mask m filled with rgb over `bounds` (landscape box), a hint of light at the top and shade at the bottom (+10 % white to -12 % black) and the paper's grain; flat, not glossy; sharp edge."""
    x0, y0, x1, y1 = box(bounds)
    g = Image.new('RGBA', im.size); g.paste(vgrad3((x1 - x0, y1 - y0), mix(rgb, (255, 255, 255), 0.10), rgb, mix(rgb, (0, 0, 0), 0.12)), (x0, y0))
    g.alpha_composite(noise(7, 20))
    im.paste(g, (0, 0), m)

def arrow(im, x, y, rgb):
    """The tape direction arrow printed on the label (pointing right, 34 x 18): printed ink (foil())."""
    m = Image.new('L', im.size, 0)
    ImageDraw.Draw(m).polygon([(S(x), S(y - 4)), (S(x + 20), S(y - 4)), (S(x + 20), S(y - 9)), (S(x + 34), S(y)), (S(x + 20), S(y + 9)), (S(x + 20), S(y + 4)), (S(x), S(y + 4))], fill=255)
    foil(im, m, rgb, (x, y - 9, x + 34, y + 9))

# ---- the cassette ------------------------------------------------------------------------------------------------------------
def holes_mask(sz):
    hm = Image.new('L', sz, 0); hd = ImageDraw.Draw(hm)
    for cx in REEL_CX: hd.ellipse((S(cx - HOLE_R), S(REEL_CY - HOLE_R), S(cx + HOLE_R), S(REEL_CY + HOLE_R)), fill=255)
    return hm

def hline(d, x0, x1, y, rgb):
    """A 1 px line on whole pixels (landscape x0 .. x1, row y) in the supersampled image."""
    d.rectangle((S(x0), S(y), S(x1) - 1, S(y) + K - 1), fill=rgb + (255,))

def draw_base(im, t, tone=None):
    """Everything of the cassette that does not move or change with the track, at supersampled size: no packs, rings, hubs, scale, marks, text, and not the knurl or the grain (laid on at 1:1 by
    finish()). Returns the knurl's mask (supersampled L): where the shell is knurled. `tone` (a cover's tone) tints the band; the build has none."""
    d = ImageDraw.Draw(im); sz = im.size; shell = t['shell']
    light, dark = mix(shell, (255, 255, 255), 0.30), mix(shell, (0, 0, 0), 0.65)
    body = rr_mask(sz, CASS, 11)
    glow_shadow(im, body, 3, 6, 6, 190)                                           # the drop shadow on the surface
    gradient_in(im, body, CASS, mix(shell, (255, 255, 255), 0.07), mix(shell, (0, 0, 0), 0.20))   # a soft light from the top left
    overlay(im, noise(1, 14), body); bevel(im, body, light, dark, 1.8)
    bevel(im, body, (0x9A, 0x9A, 0xA0), (0, 0, 0), 0.8, a=120)   # a faint rim light, so a black shell separates from the surface
    d.rounded_rectangle(box((8, 13, 472, 307)), S(9), outline=mix(shell, (0, 0, 0), 0.45) + (255,), width=1)   # the moulded step: a smooth flat rim band lies inside it
    # the raised bottom section: its own shadow, a visible thickness edge (the part is 3 px proud), the same moulding
    tz = [(92, 236), (388, 236), (358, 310), (122, 310)]; tm = poly_mask(sz, tz)
    glow_shadow(im, tm, 1, 3, 2.5, 190)
    fill_mask(im, poly_mask(sz, [(x + 1.5, y + 3) for x, y in tz]), mix(shell, (0, 0, 0), 0.6))
    fill_mask(im, tm, mix(shell, (255, 255, 255), 0.05))
    overlay(im, noise(2, 14), tm); bevel(im, tm, light, dark, 1.8)
    for x in (150, 330): round_hole(im, x, 290, 9.5)
    for x in (192, 288): square_hole(im, (x - 5, 279, x + 5, 289))
    square_hole(im, (222, 272, 258, 298))
    # the label: set into the shell (a soft shadow round its edge), a raised frame, then the paper
    fr = rr_mask(sz, (LABEL[0] - 4, LABEL[1] - 4, LABEL[2] + 4, LABEL[3] + 4), 7)
    glow_shadow(im, fr, 0, 1.5, 3, 200)
    fill_mask(im, fr, mix(shell, (255, 255, 255), 0.04)); bevel(im, fr, light, dark, 1.6)
    lm = rr_mask(sz, LABEL, 4); gradient_in(im, lm, LABEL, *t['paper']); overlay(im, noise(3, 16), lm)
    lx0, ly0, lx1, ly1 = LABEL; band = mix(t['band'], tone, t['tone_mix']) if tone else t['band']   # the cover's tone tints the band
    d.rectangle(box((lx0, 100, lx1, 101)), fill=mix(band, (0, 0, 0), 0.25) + (255,))
    d.rectangle(box((lx0, 100 + 1, lx1, 191)), fill=band + (255,)); d.rectangle(box((lx0, 191, lx1, 192)), fill=mix(band, (0, 0, 0), 0.25) + (255,))
    if t['band_ink'] == GOLD:   # the metal label: gold ink hairlines on the band
        for y in (103, 188):
            hm = Image.new('L', sz, 0); ImageDraw.Draw(hm).rectangle(box((lx0, y, lx1, y + 1)), fill=255); foil(im, hm, GOLD, (lx0, y, lx1, y + 1))
    pap = t['paper'][1]; ruled = mix(pap, t['ink'], t['rule_a'])
    for y in (61, 80, 99): hline(d, lx0 + 6, lx1 - 6, y, ruled)
    # the inner panel with the reel holes and the clear window: the window is smoked glass (a dark gradient; its reflection and inner shadow are in tape_top)
    pm = rr_mask(sz, PANEL, 7); fill_mask(im, pm, (0x0A, 0x0A, 0x0C)); overlay(im, noise(4, 22), pm)
    bevel(im, pm, (0x70, 0x70, 0x74), (0x00, 0x00, 0x00), 1.4, raised=False, a=200)
    cm = rr_mask(sz, CLEAR, 4)
    gradient_in(im, cm, CLEAR, (0x3E, 0x40, 0x44), (0x14, 0x15, 0x18))
    fill_mask(im, holes_mask(sz), (0x0C, 0x0C, 0x0E))
    arrow(im, ARROW_AT[0], ARROW_AT[1], t['print'])
    # the screws: four corners and the bottom centre
    screws = SCREWS
    for x, y in screws: screw(im, x, y, turn=SCREW_TURN.get((x, y), 0))
    # where the shell is knurled: inside the flat rim band, on the raised section, not under the label, the screws or the holes
    km = rr_mask(sz, (14, 19, 466, 301), 5); km.paste(255, (0, 0), tm)
    kd = ImageDraw.Draw(km); kd.rectangle(box((LABEL[0] - 4, LABEL[1] - 4, LABEL[2] + 4, LABEL[3] + 4)), fill=0)
    for x, y in screws: kd.ellipse((S(x - 11), S(y - 11), S(x + 11), S(y + 11)), fill=0)
    for x in (150, 330): kd.ellipse((S(x - 11), S(290 - 11), S(x + 11), S(290 + 11)), fill=0)
    for b in ((187, 274, 197, 294), (283, 274, 293, 294), (217, 267, 263, 303)): kd.rectangle(box(b), fill=0)
    return km

def draw_packs(im, f):
    """The tape packs at the position f['pos'] / f['len'], clipped to the holes and the clear window."""
    sz = im.size; vis = ImageChops.lighter(holes_mask(sz), rr_mask(sz, CLEAR, 4))
    pk = packs(sz, f['pos'] / f['len']); pk.putalpha(ImageChops.multiply(pk.getchannel('A'), vis)); im.alpha_composite(pk)

def draw_top(im):
    """What lies over the tape: the holes' gear rings and lips (the lip casts a shadow on the tape; lit lower right, shaded upper left), the smoked window's reflection (fading
    top to bottom, soft edge), three hairline scratches, inner shadow and the printed scale with its shadow a pixel right and down."""
    d = ImageDraw.Draw(im); sz = im.size; R = HOLE_R; hm = holes_mask(sz); blur = ImageFilter.GaussianBlur
    for cx in REEL_CX:
        ring = (S(cx - R), S(REEL_CY - R), S(cx + R), S(REEL_CY + R))
        sh = Image.new('L', sz, 0); sd = ImageDraw.Draw(sh)   # the lip's shadow: the hole's disc minus itself moved down and right, blurred, only where the tape is
        sd.ellipse(ring, fill=255); sd.ellipse((S(cx - R + 3), S(REEL_CY - R + 4.5), S(cx + R + 3), S(REEL_CY + R + 4.5)), fill=0)
        fill_mask(im, ImageChops.multiply(sh.filter(blur(S(1.4))), hm), (0, 0, 0), 190)
        d.ellipse(ring, outline=(0x5E, 0x60, 0x66, 255), width=int(1.6 * K))
        d.arc(ring, 15, 100, fill=(0xA6, 0xA8, 0xAE, 255), width=int(1.6 * K))     # the lit lower-right lip
        d.arc(ring, 190, 280, fill=(0x2C, 0x2D, 0x31, 255), width=int(1.6 * K))    # the shaded upper-left lip
        d.ellipse((S(cx - HOLE_R - 2), S(REEL_CY - HOLE_R - 2), S(cx + HOLE_R + 2), S(REEL_CY + HOLE_R + 2)), outline=(0x1C, 0x1C, 0x1F, 255), width=K)
        for k in range(24):
            a = math.radians(k * 15); c, s_ = math.cos(a), math.sin(a)
            d.line((S(cx + c * (HOLE_R - 3.5)), S(REEL_CY + s_ * (HOLE_R - 3.5)), S(cx + c * (HOLE_R - 0.8)), S(REEL_CY + s_ * (HOLE_R - 0.8))), fill=(0x6A, 0x6C, 0x72, 255), width=K)
    C = CLEAR; cm = rr_mask(sz, C, 4)
    fade = Image.new('L', sz, 0); fade.paste(vgrad((S(C[2] - C[0]), S(C[3] - C[1])), (255,) * 3, (40,) * 3).convert('L'), (S(C[0]), S(C[1])))   # the reflection fades top to bottom
    for pts, a in (([(C[0] + 14, C[3]), (C[0] + 46, C[3]), (C[0] + 92, C[1]), (C[0] + 60, C[1])], 52),
                   ([(C[0] + 52, C[3]), (C[0] + 62, C[3]), (C[0] + 108, C[1]), (C[0] + 98, C[1])], 26)):   # a soft diagonal reflection
        refl = ImageChops.multiply(ImageChops.multiply(poly_mask(sz, pts).filter(blur(S(2.5))), cm), fade); fill_mask(im, refl, (255, 255, 255), a)
    scr = Image.new('L', sz, 0); sd = ImageDraw.Draw(scr)   # three hairline scratches on the window, one supersampled pixel wide
    for xa, ya, xb, yb, a in ((190, 124, 216, 121, 15), (232, 172, 262, 175, 12), (262, 131, 288, 136, 13)):
        sd.line((S(xa), S(ya), S(xb), S(yb)), fill=a * 3, width=1)
    fill_mask(im, ImageChops.multiply(scr, cm), (255, 255, 255))
    bevel(im, cm, (0x56, 0x58, 0x5E), (0x00, 0x00, 0x00), 2.4, raised=False, a=200)   # the inner shadow at the frame edge
    ym = (C[1] + C[3]) // 2   # the scale: a fine centre line with ticks, on whole pixels, printed on the window: its shadow falls a pixel right and down
    # (opaque colours: that is how the approved picture looks; layer() solves the alpha from a drawing on black and on white, and ImageDraw's alpha is not blended)
    for off, col in ((1, (0, 0, 0, 255)), (0, (0xD8, 0xDA, 0xDE, 255))):
        d.rectangle((S(C[0] + 6 + off), S(ym + off), S(C[2] - 6 + off) - 1, S(ym + off) + K - 1), fill=col)
        for x in range(C[0] + 12, C[2] - 8, 12):
            h = 8 if x == 240 else 4; d.rectangle((S(x + off), S(ym - h + off), S(x + off) + K - 1, S(ym + h + 1 + off) - 1), fill=col)

def draw_hubs(im, f, t):
    for cx, ang in zip(REEL_CX, (f['ang_s'], f['ang_t'])):
        sp = hub_sprite(ang, t['hub']); im.alpha_composite(sp, (S(cx) - sp.width // 2, S(REEL_CY) - sp.height // 2))

def draw_marks(im, f, t):
    """The printed play / pause mark and the repeat arrow."""
    pr = t['band_ink']
    state_mark(im, PLAY_AT[0], PLAY_AT[1], f['playing'], pr)
    if f['repeat']: repeat_glyph(im, REPEAT_AT[0], REPEAT_AT[1], pr)

def compose(f, t):
    """The mock's whole cassette, text and all but the text, as a landscape RGBA picture at 1:1: the knurled shell, the tape, what lies over it, the hubs and the marks (each layer
    reduced alone, so the preview shows what the device composes)."""
    im = static_land(t).convert('RGBA')
    for draw, rect in ((lambda b: draw_packs(b, f), TOP_RECT), (draw_top, TOP_RECT), (lambda b: draw_hubs(b, f, t), TOP_RECT), (lambda b: draw_marks(b, f, t), (407, 110, 439, 185))):
        im.alpha_composite(layer(draw, rect), rect[:2])
    return im

# ---- the installed images ----------------------------------------------------------------------------------------------------
def rot(im):
    """The landscape picture turned 90 degrees clockwise: the framebuffer's: landscape (x, y) -> (column H - 1 - y, row x)."""
    return im.transpose(Image.ROTATE_270)

def reduce(big, box_):
    return big.convert('RGB').crop(tuple(v * K for v in box_)).resize(((box_[2] - box_[0]), (box_[3] - box_[1])), Image.BOX)

def layer(draw, rect, size=None):
    """RGBA of what `draw(image)` paints over any background, inside the landscape rect: drawn on black and on white (supersampled), reduced, alpha and colour solved
    (C = a F + (1 - a) B). `draw` paints onto a W * K x H * K image."""
    ims = []
    for bg in (0, 255):
        big = Image.new('RGBA', (W * K, H * K), (bg, bg, bg, 255)); draw(big); ims.append(reduce(big, rect))
    out = Image.new('RGBA', ims[0].size); po = out.load(); pb, pw = ims[0].load(), ims[1].load()
    for y in range(out.height):
        for x in range(out.width):
            cb, cw = pb[x, y], pw[x, y]
            a = 255 - sum(cw[i] - cb[i] for i in range(3)) // 3
            a = max(0, min(255, a))
            po[x, y] = (0, 0, 0, 0) if a < 2 else tuple(max(0, min(255, round(cb[i] * 255 / a))) for i in range(3)) + (a,)
    return out

def flat_land(t, flat=None):
    """The static cassette before the knurl, the grain and the light, landscape RGB at 1:1 (shapes drawn at 3x and reduced), the knurl's mask and the masks the light needs.
    `flat` is noise()'s measuring colour."""
    _FLAT[0] = flat
    big = Image.new('RGBA', (W * K, H * K), BG + (255,)); km = draw_base(big, t); sz = big.size
    L = LABEL; lm = rr_mask(sz, L, 4); pm = rr_mask(sz, (PANEL[0] - 1, PANEL[1] - 1, PANEL[2] + 1, PANEL[3] + 1), 7); blur = ImageFilter.GaussianBlur
    paper = ImageChops.subtract(lm, pm)
    # the band is ink on paper: a little of the paper's grain, a soft top-to-bottom shade
    bm = Image.new('L', sz, 0); ImageDraw.Draw(bm).rectangle(box((L[0], 101, L[2], 191)), fill=255); bm = ImageChops.subtract(bm, pm)
    overlay(big, noise(5, 13), bm)
    sh = Image.new('RGBA', sz, (0, 0, 0, 0)); g = Image.new('RGBA', (S(L[2] - L[0]), S(90))); gd = ImageDraw.Draw(g)
    for y in range(g.height):
        u = y / (g.height - 1); gd.line((0, y, g.width, y), fill=(255, 255, 255, int(30 * (1 - 2 * u))) if u < 0.5 else (0, 0, 0, int(38 * (2 * u - 1))))
    sh.paste(g, (S(L[0]), S(101))); overlay(big, sh, bm)
    # the frame's shadow on the paper (top and left), the panel's cut edge in the paper
    fill_mask(big, ImageChops.multiply(ImageChops.subtract(lm, ImageChops.offset(lm, S(2.5), S(3.5))).filter(blur(S(1.6))), paper), (0, 0, 0), 105)
    edge = rr_mask(sz, (PANEL[0] - 2.5, PANEL[1] - 2.5, PANEL[2] + 2.5, PANEL[3] + 3.5), 9)
    fill_mask(big, ImageChops.multiply(ImageChops.subtract(edge, pm).filter(blur(S(0.8))), paper), (0, 0, 0), 55)
    im = big.resize((W, H), Image.LANCZOS).convert('RGB')
    _FLAT[0] = None
    r = lambda m: m.resize((W, H), Image.BOX)
    return im, r(km), r(rr_mask(sz, CASS, 11)), r(lm), r(pm), r(rr_mask(sz, (L[0] - 4, L[1] - 4, L[2] + 4, L[3] + 4), 7))

GAIN_ONE, GAIN_STEP = 128, 4   # tape_tex's red: the knurl's strength, 128 is the tile's own alpha; kept in steps of 4 (the map packs well, 3 % of contrast is not seen)
_PARTS = {}
def shell_parts(t):
    """(shell, gain, amp), landscape at 1:1: the smooth shell with its light (RGB: what tape_shell_<theme> holds), the knurl's strength (L, GAIN_ONE = 1) and the grain's amplitude
    (L, alpha of 255) at each pixel. The light: the shell's falls off from the top left with a faint diagonal sheen over shell and label; the knurl's contrast follows it (the gain).
    The amplitude is measured: the picture drawn with flat white and flat black in place of the grain differs from the clean one by exactly the grain's alpha there, whatever was
    drawn over it later. Deterministic; the light is deliberately not symmetric about x 240."""
    if id(t) in _PARTS: return _PARTS[id(t)][1:]
    im, km, body, lab, pan, frm = flat_land(t)
    wh, bl = flat_land(t, 255)[0], flat_land(t, 0)[0]
    amp = Image.new('L', (W, H), 0); gain = Image.new('L', (W, H), 0); out = im.copy()
    po, pi, pw, pk, pa, pg = out.load(), im.load(), wh.load(), bl.load(), amp.load(), gain.load()
    pm_, pb, pl, pp, pf = km.load(), body.load(), lab.load(), pan.load(), frm.load()
    for y in range(H):
        for x in range(W):
            c = pi[x, y]
            pa[x, y] = min(255, (sum(pw[x, y]) - sum(pk[x, y]) + 1) // 3)
            b = pb[x, y] / 255.0
            if not b: continue
            s = math.exp(-(((x - (150 + (H - y) * 0.7)) / 85.0) ** 2))   # a broad diagonal sheen
            if pf[x, y] < 128:   # the shell: a light falling off from the top left, the knurl catching it
                f = 1.18 - 0.46 * (0.30 * x / W + 0.70 * y / H) + 0.06 * s
                g = max(0.35, 0.70 + 0.55 * s + 1.0 * (f - 1.0)) / f   # (the knurl is laid on the lit pixel: its strength is told for that)
                pg[x, y] = min(255, int(pm_[x, y] / 255.0 * b * g * GAIN_ONE / GAIN_STEP + 0.5) * GAIN_STEP)
                v = tuple(int(max(0, min(255, c[i] * f))) for i in range(3))
            elif pl[x, y] > 128 and pp[x, y] < 128:   # the label: semi-gloss paper
                gl = 0.035 * s * 255
                v = tuple(int(min(255, c[i] + gl)) for i in range(3))
            else: continue
            po[x, y] = tuple(int(c[i] + (v[i] - c[i]) * b) for i in range(3))
    _PARTS[id(t)] = (t, out, gain, amp)
    return out, gain, amp

KNURL = ((78, 0), (58, 255), (64, 0), (14, 255))   # the knurl tile's (alpha, colour): the groove, the lit top and left edge, the shaded bottom and right edge, the square's face: a raised 3 x 3 square in a 4 x 4 cell on the pixel grid, never downsampled

def blend_to(c, a, white):
    """A channel c moved by alpha a (of 256) towards white or black: the page's arithmetic (patch/tape.c tp_finish)."""
    return c + ((255 - c) * a >> 8) if white else c - (c * a >> 8)

def finish(shell, tex):
    """The shell as the page shows it: the installed tape_shell picture (turned, 320 x 480) with the grain and the knurl laid on at 1:1 by tape_tex (red the knurl's strength, green
    the grain's amplitude), integer for integer what patch/tape.c tp_finish does once when the page opens. Pixel i = row * 320 + column of the turned picture: the grain is a hash of
    i (light or dark by its top bit, alpha |n - 128| * amplitude >> 7), then the knurl's 4 x 4 cell at the landscape place (row, 319 - column), its alpha times the strength >> 7."""
    out = shell.convert('RGB'); px = out.load(); tx = tex.load(); w, h = out.size
    for y in range(h):
        for x in range(w):
            g, a = tx[x, y][:2]
            if not (g or a): continue
            c = px[x, y]
            if a:
                n = ((y * w + x + 1) * 0x9E3779B1) & 0xFFFFFFFF; n ^= n >> 16; n = (n * 0x85EBCA6B) & 0xFFFFFFFF; n = (n ^ n >> 13) >> 8 & 255
                k = abs(n - 128) * a >> 7; c = tuple(blend_to(v, k, n >= 128) for v in c)
            if g:
                u, v_ = y & 3, ~x & 3
                ka, kc = KNURL[0 if u == 3 or v_ == 3 else 1 if u == 0 or v_ == 0 else 2 if u == 2 or v_ == 2 else 3]
                k = min(255, ka * g >> 7); c = tuple(blend_to(v, k, kc) for v in c)
            px[x, y] = c
    return out

_TEXIM = []
def tex_image():
    """tape_tex (turned, RGBA): red the knurl's strength, green the grain's amplitude, the same for every theme (the Normal theme's: the themes share the geometry; Metal's two foil
    hairlines take the band's grain)."""
    if not _TEXIM:
        _, gain, amp = shell_parts(THEMES['normal'])
        _TEXIM.append(rot(Image.merge('RGBA', (gain, amp, Image.new('L', (W, H), 0), Image.new('L', (W, H), 255)))))
    return _TEXIM[0]

def static_land(t):
    """The static cassette as the page shows it, landscape RGB at 1:1: the smooth lit shell with the grain and the knurl the page adds (finish)."""
    return finish(rot(shell_parts(t)[0]), tex_image()).transpose(Image.ROTATE_90)

def shell_image(name):
    return rot(shell_parts(THEMES[name])[0]).convert('RGBA')   # the smooth lit shell (the page adds grain and knurl: finish); RGBA with alpha 255 everywhere: the device's decoder gives 32 bit pixels for it (as for the other pictures)

def top_image():
    return rot(layer(draw_top, TOP_RECT))

def hubs_image(name):
    t = THEMES[name]
    sheet = Image.new('RGBA', (HUB_PX, SPRITES * HUB_PX), (0, 0, 0, 0))
    for i in range(SPRITES):
        def draw(big, i=i):
            sp = hub_sprite(i * 360 / 3 / SPRITES, t['hub']); big.alpha_composite(sp, (S(HUB_PX // 2) - sp.width // 2, S(HUB_PX // 2) - sp.height // 2))
        sheet.paste(rot(layer(draw, (0, 0, HUB_PX, HUB_PX))), (0, i * HUB_PX))
    return sheet

def marks_image(name):
    t = THEMES[name]
    sheet = Image.new('RGBA', (MARK_PX, 3 * MARK_PX), (0, 0, 0, 0)); c = MARK_PX // 2
    for i, draw in enumerate((lambda b: state_mark(b, c, c, True, t['band_ink']), lambda b: state_mark(b, c, c, False, t['band_ink']),
                              lambda b: repeat_glyph(b, c, c, t['band_ink']))):
        sheet.paste(rot(layer(draw, (0, 0, MARK_PX, MARK_PX))), (0, i * MARK_PX))
    return sheet

def screw_image():
    """The close screw pressed (theme independent: the shell's screws are the same in every theme)."""
    c = MARK_PX // 2
    return rot(layer(lambda b: screw(b, c, c, **PRESSED), (0, 0, MARK_PX, MARK_PX)))

THEME_NAMES = tuple(THEMES)     # the order of the saved value: 0 Normal, 1 Chrome, 2 Metal
SHARED = ('tape_top', 'tape_screw', 'tape_tex')                                                 # the same in every theme
PER_THEME = ('tape_shell', 'tape_hubs', 'tape_marks')                               # one picture a theme: <name>_<theme>
NAMES = SHARED + tuple(f'{n}_{t}' for t in THEME_NAMES for n in PER_THEME)

def images():
    """name -> PIL image of every installed Tape picture: the shared ones once, the shell, the hub frames and the marks (the band's ink) for each theme."""
    out = {'tape_top': top_image(), 'tape_screw': screw_image(), 'tape_tex': tex_image()}
    for t in THEME_NAMES: out.update({f'tape_shell_{t}': shell_image(t), f'tape_hubs_{t}': hubs_image(t), f'tape_marks_{t}': marks_image(t)})
    return out

def mark_rects():
    """The marks' rectangles on the landscape screen (x0, y0, x1, y1): the play / pause mark, the repeat arrow, the close screw."""
    c = MARK_PX // 2
    return [(PLAY_AT[0] - c, PLAY_AT[1] - c, PLAY_AT[0] - c + MARK_PX, PLAY_AT[1] - c + MARK_PX), (REPEAT_AT[0] - c, REPEAT_AT[1] - c, REPEAT_AT[0] - c + MARK_PX, REPEAT_AT[1] - c + MARK_PX),
            (SCREW_AT[0] - c, SCREW_AT[1] - c, SCREW_AT[0] - c + MARK_PX, SCREW_AT[1] - c + MARK_PX)]

# ---- text, shared by the mock and the checks ----------------------------------------------------------------------------------
def clock(sec): return '%d:%02d' % divmod(int(sec), 60)

def times_text(pos, length): return clock(pos) + '  -' + clock(length - pos)

def status_line(font, f):
    """'VOL 42 | MP3 320 | 21:07 | 60%': the status bar's volume, the playing format, the clock and the battery (a '+' before it while charging;
    the status bar gives 20 % steps). The largest size that fits (12, 11 px), dropping the clock first, then the format."""
    batt = '%s%d%%' % ('+' if f['charging'] else '', f['batt'])
    for px in (12, 11):
        for parts in ((f['fmt'], f['clock']), (f['fmt'],), ()):
            text = ' | '.join(['VOL %d' % f['vol']] + [p for p in parts if p] + [batt])
            if font.width(text, px) <= STATUS_W: return text, px
    return text, px

if __name__ == '__main__':
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else '.'
    for n, im in images().items(): im.save(os.path.join(out, n + '.png'), optimize=True); print(n, im.size)
