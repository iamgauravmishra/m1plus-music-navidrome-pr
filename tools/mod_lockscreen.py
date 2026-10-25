#!/usr/bin/env python3
"""Lock screen mod for the Shanling M1 Plus (ui/screensaver_page.bin, asset-only, no binary patch).

Stock lock screen: wallpaper (img_screensaver), a 70 px clock left of a battery gauge, a 50 px date,
and the now-playing strip (view_bottomview). Default result of this mod:
  - clock as large as fits the 320 px width (138 px for "hh:mm"), centred
  - date 24 px, centred under the clock (or hidden)
  - battery percentage "86%" next to the state icon, centred under the date. pgbar_battery is the
    widget the app feeds with the battery level on this page too (demo: screensaver refresh does
    widget_lookup("pgbar_battery") + progress_bar_set_value), so mod_battery's show_text trick applies.
  - wallpaper, now-playing strip, play/next buttons, swipe hint: unchanged

What the app touches on this page, by name (demo, screensaver_page_init and its handlers):
img_screensaver (wallpaper image), view_timeinfo (shown/hidden by the "show time" screensaver
setting), app_gesture (swipe), btn_play, btn_next, img_battery (image set to screens_battery /
screens_charge / screens_lowbattery), pgbar_battery (value), view_bottomview (shown/hidden),
view_scrlabel_title, view_scrlabel_artist, view_img_icon. Nothing looks up dclock_time or dclock_date,
and nothing rewrites their format: the stock 12/24 h setting only changes the status bar clock
(bar_dclock: "hh:mm" or "HH:TT"), so the stock lock screen clock is always 24 h. Names are kept,
app-driven widgets are only moved/restyled.

Digit_clock format tokens in this AWTK build (wstr_format_date_time in demo, Shanling-modified):
  Y 2026   YY 26   M 1..12  MM 01..12  MMM month name   D / DD day   w weekday 0..6   W weekday name
  h / hh hour 0..23 (00..23)   H hour 0..23 unpadded   HH hour 01..12
  m / mm minute   s / ss second   T minute   TT minute + " AM"/" PM" (so "HH:TT" shows "05:30 PM")
  anything else is copied literally.

--layout cover (docs/lockscreen2.md, the look-lock2 variant): iPhone-style. Small date over an ~88 px
clock at the top, and the now-playing block (view_bottomview) becomes an opaque dark card with the
cover at 254 x 254 (the size demo writes /tmp/coverpic.jpg at, so it is drawn 1:1), rounded by a
corner mask image (ls_artmask.png, in the card's colour), title and artist under it, play/next to
their right. No battery percentage: a small gauge top right (--battery icon) or none. The app hides
view_bottomview (visible and enable off) when nothing is queued; the page is then date + clock on
the wallpaper. The layout does not depend on what an earlier run of this tool did to the page, so it
can run last in a build (after a font step): every property it relies on is set absolutely, and
pgbar_battery gets its stock gauge props back.

Fonts: the clock / date sizing reads fonts/default.ttf from OUT_WORKDIR, i.e. whatever font the tree
being built has at that point (a font step must run before this tool for its metrics to count). The
fit uses the widest digit, so a font with proportional digits still fits; with the stock font
(tabular digits) the result is unchanged. Widths are measured as AWTK lays text out (StbText below:
advances truncated, +1 px after every glyph), not as summed advances: the stock "hh:mm" at 138 px is
297 px wide on the device, not the 295 the sum gives. The classic layout's sizes for the stock font
are unchanged (138 px clock with the 11 px default margin, the "100%" box 46 px, already as wide as
AWTK draws it).

Usage: mod_lockscreen.py SRC_WORKDIR OUT_WORKDIR [options]
  SRC_WORKDIR is what `fwtool.py unpack` produced (or another mod's output); OUT_WORKDIR is cloned from
  it and modified. OUT_WORKDIR == SRC_WORKDIR edits in place (used to stack on the battery mod).
"""
import argparse, math, os, stat, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
from mod_battery import clone_workdir, edit_ui, style_as_text

RAW = 'rootfs/release/assets/default/raw'
UI = f'{RAW}/ui/screensaver_page.bin'
FONT = f'{RAW}/fonts/default.ttf'
PAGE_STYLE = f'{RAW}/styles/screensaver_page.bin'     # the page's window theme (default asset theme)
IMAGES = f'{RAW}/images/xx'
SCREEN_W, SCREEN_H = 320, 480
STATES = ('normal', 'disable', 'focused')      # stock sets every text style for all three
BTN_STATES = ('normal', 'disable', 'focused', 'over', 'pressed')
GAP = 14                                       # px between the ink of stacked rows
ICON_GAP = 6                                   # px between percentage text and battery icon
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
    def glyph(self, ch):
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
# docs/look-nowplaying.md "The album line"): stb_truetype scale = font_size / (ascender - descender)
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

def apply(root, ttf, o):
    view, clock, date = root.find('view_timeinfo'), root.find('dclock_time'), root.find('dclock_date')
    img, pg, strip, slide = root.find('img_battery'), root.find('pgbar_battery'), root.find('view_bottomview'), root.find('img_slide')
    assert all(w is not None for w in (view, clock, date, img, pg, strip, slide)), 'unexpected screensaver_page layout'
    assert clock.type == date.type == 'digit_clock' and pg.type == 'progress_bar' and img.type == 'image'
    assert img in view.children and pg in view.children and clock in view.children, 'battery/clock moved out of view_timeinfo?'

    # clock: largest size whose widest possible text, as AWTK lays it out, fits the width minus margins
    fmt = o.clock_format or clock.get('format')
    sample = worst_case_text(fmt, ttf)
    fit = fit_size(ttf, sample, SCREEN_W - 2 * o.clock_margin, 2 * SCREEN_W)
    size = o.clock_size or fit
    if size > fit: raise SystemExit(f'--clock-size {size}: "{fmt}" would need {awtk_width(ttf, sample, size)} px, max size is {fit}')
    clock.x, clock.y, clock.w, clock.h = 0, 0, SCREEN_W, size
    if o.clock_format: clock.set('format', o.clock_format)
    for st in STATES:
        clock.set(f'style:{st}:font_size', str(size))
        clock.set(f'style:{st}:text_align_h', 'center')
    ink_top, ink_bot = ttf.digit_ink(size)
    bottom = ink_bot                                  # running bottom of the ink stacked so far (view coords)

    # date: smaller, centred under the clock; or hidden (nothing in the app touches it)
    if o.no_date:
        date.set('visible', 'false'); date.x = -2 * SCREEN_W     # belt and braces: also off-screen
    else:
        dh = o.date_size + 8
        d_top, d_bot = ttf.digit_ink(o.date_size); d_top += (dh - o.date_size) // 2; d_bot += (dh - o.date_size) // 2
        date.x, date.y, date.w, date.h = 0, round(bottom + GAP - d_top), SCREEN_W, dh
        if o.date_format: date.set('format', o.date_format)
        for st in STATES: date.set(f'style:{st}:font_size', str(o.date_size))
        bottom = date.y + d_bot

    # battery row, centred under the date
    row_y = round(bottom + GAP)
    icon_dx, icon_dy = pg.x - img.x, pg.y - img.y                # stock gauge sits inside the icon
    text_w = max(math.ceil(ttf.width('100%', o.battery_size)) + 2, awtk_width(ttf, '100%', o.battery_size))
    text_h = max(img.h, o.battery_size + 8)
    text_y = row_y + (img.h - text_h) // 2
    if o.battery == 'icon+percent':                 # "86% [icon]", like the status bar icon+percent mod
        x0 = (SCREEN_W - (text_w + ICON_GAP + img.w)) // 2
        img.x, img.y = x0 + text_w + ICON_GAP, row_y
        style_as_text(pg, x0, text_w, o.battery_size, y=text_y, h=text_h, align='right', states=STATES)
    elif o.battery == 'percent':                    # text only; the app never touches img_battery's visibility
        img.set('visible', 'false'); img.x = -100
        style_as_text(pg, (SCREEN_W - text_w) // 2, text_w, o.battery_size, y=text_y, h=text_h, align='center', states=STATES)
    else:                                           # 'icon': stock gauge, just re-centred
        img.x, img.y = (SCREEN_W - img.w) // 2, row_y
        pg.x, pg.y = img.x + icon_dx, img.y + icon_dy
    row_bot = max(row_y + img.h, text_y + text_h)

    # now-playing strip stays put unless asked; the time block is centred in the free space beside it
    if o.strip_y is not None:
        if not 0 <= o.strip_y <= SCREEN_H - strip.h: raise SystemExit(f'--strip-y must be 0..{SCREEN_H - strip.h}')
        strip.y = o.strip_y
    lo, hi = (0, strip.y) if strip.y >= SCREEN_H // 2 else (strip.y + strip.h, slide.y)
    content = row_bot - ink_top
    view.x, view.w, view.h = 0, SCREEN_W, row_bot + 4
    view.y = max(0, lo + round((hi - lo - content) / 2 - ink_top))
    if view.y + view.h > hi or view.y + ink_top < lo:
        print(f'warning: time block ({view.y + round(ink_top)}..{view.y + row_bot}) overlaps the strip / swipe hint', file=sys.stderr)
    if not o.no_date:
        dw = awtk_width(ttf, worst_case_text(date.get('format'), ttf), o.date_size)
        if dw > SCREEN_W: raise SystemExit(f'--date-size {o.date_size}: the date is {dw} px wide, more than {SCREEN_W}')
    return dict(clock_size=size, clock_format=fmt, clock_px=awtk_width(ttf, sample, size))

# ------------------------------------------------------------------------------- --layout cover
# demo's lock screen cover loader (0x53f9b4) loads file:///tmp/coverpic.jpg (embedded art; folder /
# .downpic art goes to /tmp/externpic.jpg) into view_img_icon. parseplaycover_thd writes both files
# with toolsGetAlbumCover / toolsGetExternCover(src, dst, 254, 254): fitted into 254 x 254, aspect kept,
# never upscaled. Now Playing (img_playcover1) reads the same file. So 254 is the size to draw it at.
COVER_SRC = 254
CARD_RGB = '#131313'          # the stock now-playing strip colour; the corner mask is painted in it
CARD_PAD = 10                 # card edge to cover
TITLE_PX, ARTIST_PX = 20, 16  # stock sizes of the strip's labels
TITLE_RGB, ARTIST_RGB = '#FFFFFF', '#CCCCCC'
BTN_W = 48                    # play / next touch targets, side by side right of title / artist
MASK = 'ls_artmask'
IMG_MODE, IMG_MTIME = 0o755, 1750924035      # as mod_nowplaying's np_*.png: stock image mode, fixed mtime
# pgbar_battery as shipped (stock screensaver_page.bin): the gauge fill inside screens_battery
STOCK_PGBAR = [('name', 'pgbar_battery'), ('style:normal:round_radius', '0'), ('style:disable:round_radius', '0'),
    ('style:focused:round_radius', '0'), ('style:normal:border_color', '#00000000'), ('style:normal:border', 'all'),
    ('style:disable:border', 'all'), ('style:focused:border', 'all'), ('style:normal:bg_color', '#00000000'),
    ('style:normal:fg_color', '#FFFFFF'), ('style:disable:bg_color', '#00000000'), ('style:focused:bg_color', '#00000000'),
    ('style:disable:fg_color', '#FFFFFF'), ('style:focused:fg_color', '#FFFFFF'), ('style:normal:text_color', '#444444'),
    ('style:disable:text_color', '#444444'), ('style:focused:text_color', '#444444'), ('value', '100')]
STOCK_GAUGE = (40, 23, 2, 1, 33, 20)          # img_battery w h, pgbar offset inside it, pgbar w h
GLYPHS = {'btn_imgpause1_style': ('np_pause', 'np_pause_down'), 'btn_imgplay1_style': ('np_play', 'np_play_down')}
NEXT_GLYPH = ('np_next', 'np_next_down')

def text_style(w, px, rgb, align, states=STATES):
    for st in states:
        w.set(f'style:{st}:font_size', str(px)); w.set(f'style:{st}:text_color', rgb)
        w.set(f'style:{st}:text_align_h', align); w.set(f'style:{st}:text_align_v', 'middle')

def hide(w):
    """Off for good: AWTK here hit-tests invisible widgets, so also insensitive, and parked off-screen."""
    w.set('visible', 'false'); w.set('sensitive', 'false'); w.x = -2 * SCREEN_W

def text_box(ttf, px, ink_top, pad=8):
    """(y, h) of a middle-aligned digit_clock box of font px (h = px + pad) whose digit ink starts at ink_top."""
    h = px + pad; top, _ = ttf.digit_ink(px)
    return round(ink_top - top - (h - px) // 2), h

def hit(w, rect, x, y):
    """demo's widget_find_target_default (docs/coverflow.md): children from the top, the first with
    enable and sensitive set that contains the point; `visible` is not looked at."""
    for c in reversed(w.children):
        if c.get('sensitive') == 'false' or c.get('enable') == 'false': continue
        r = (rect[0] + c.x, rect[1] + c.y, c.w, c.h)
        if r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]: return hit(c, r, x, y)
    return w

def check_touch(root, cover_rect):
    """Play / next reachable at their centre and big enough; the cover area lands on the card (not a
    button), inside app_gesture, so a swipe there reaches the gesture as on the stock strip."""
    gesture, strip = root.find('app_gesture'), root.find('view_bottomview')
    inside = lambda t, anc: t is anc or any(inside(t, c) for c in anc.children)
    for n in ('btn_play', 'btn_next'):
        b = root.find(n); x, y = strip.x + b.x + b.w // 2, strip.y + b.y + b.h // 2
        t = hit(root, (0, 0, SCREEN_W, SCREEN_H), x, y)
        assert t is b, f'touch at the centre of {n} lands on {t.name or t.type}'
        assert b.w >= 44 and b.h >= 44, f'{n}: touch target {b.w}x{b.h} too small'
    cx, cy, cw, ch = cover_rect
    for x, y in ((cx + cw // 2, cy + ch // 2), (cx + 4, cy + 4), (cx + cw - 5, cy + ch - 5)):
        t = hit(root, (0, 0, SCREEN_W, SCREEN_H), x, y)
        assert t is strip and inside(t, gesture), f'touch on the cover at ({x},{y}) lands on {t.name or t.type}'

def apply_cover(root, ttf, o):
    view, clock, date = root.find('view_timeinfo'), root.find('dclock_time'), root.find('dclock_date')
    img, pg, strip, slide = root.find('img_battery'), root.find('pgbar_battery'), root.find('view_bottomview'), root.find('img_slide')
    icon, title, artist = root.find('view_img_icon'), root.find('view_scrlabel_title'), root.find('view_scrlabel_artist')
    play, nxt, gesture = root.find('btn_play'), root.find('btn_next'), root.find('app_gesture')
    assert all(w is not None for w in (view, clock, date, img, pg, strip, slide, icon, title, artist, play, nxt, gesture)), \
        'unexpected screensaver_page layout'
    assert clock.type == date.type == 'digit_clock' and pg.type == 'progress_bar' and img.type == 'image'
    assert [c.name for c in view.children] == ['dclock_time', 'dclock_date', 'img_battery', 'pgbar_battery']
    assert [c.name for c in gesture.children] == ['img_screensaver', 'view_timeinfo', 'img_slide', 'view_bottomview']
    assert [c.name for c in strip.children] == ['view_img_icon', 'view_scrlabel_title', 'view_scrlabel_artist', 'btn_play', 'btn_next'], \
        'view_bottomview children changed (cover layout applied twice?)'
    assert (slide.x, slide.y, slide.w, slide.h) == (136, 448, 48, 22) and (img.w, img.h) == STOCK_GAUGE[:2]
    if o.cover_size > COVER_SRC:
        print(f'warning: --cover-size {o.cover_size} upscales the {COVER_SRC} px cover demo writes', file=sys.stderr)

    # --- the card: cover, then title / artist on the left and play / next on the right under it
    cs, pad = o.cover_size, CARD_PAD
    card_w = cs + 2 * pad
    title_h, artist_h = TITLE_PX + 4, ARTIST_PX + 4
    card_h = pad + cs + 6 + title_h + artist_h + 8
    card_x, card_y = (SCREEN_W - card_w) // 2, slide.y - 10 - card_h        # 10 px over the swipe hint
    strip.x, strip.y, strip.w, strip.h = card_x, card_y, card_w, card_h
    for st in STATES:
        strip.set(f'style:{st}:bg_color', o.card)
        strip.set(f'style:{st}:round_radius', str(o.radius + pad))
    icon.x, icon.y, icon.w, icon.h = pad, pad, cs, cs          # draw_type scale_auto stays: 254 px is drawn 1:1
    icon.set('sensitive', 'false')                             # decorative; a touch falls through to the card
    btn_top = pad + cs + 2
    nxt.x, nxt.y, nxt.w, nxt.h = pad + cs - BTN_W, btn_top, BTN_W, card_h - btn_top
    play.x, play.y, play.w, play.h = nxt.x - BTN_W, btn_top, BTN_W, card_h - btn_top
    text_w = play.x - 4 - pad
    ty = pad + cs + 6
    title.x, title.y, title.w, title.h = pad, ty, text_w, title_h
    artist.x, artist.y, artist.w, artist.h = pad, ty + title_h, text_w, artist_h
    text_style(title, TITLE_PX, TITLE_RGB, 'left'); text_style(artist, ARTIST_PX, ARTIST_RGB, 'left')
    if o.glyphs == 'np':
        for st in BTN_STATES: nxt.set(f'style:{st}:bg_image', NEXT_GLYPH[st == 'pressed'])
    mask = awtk_ui.Widget('image', pad, pad, cs, cs, [('name', 'img_ls_artmask'), ('image', MASK), ('draw_type', 'default'),
                          ('clickable', 'false'), ('sensitive', 'false')])
    if o.radius: strip.children.insert(1, mask)                 # right above the cover, under the text and buttons

    # --- date (small) over the clock, both centred at the top; nothing app-driven moves them
    for w in (clock, date, img, pg): w.remove('visible'); w.remove('sensitive')
    dfmt = o.date_format or 'W, MMM D'
    date.set('format', dfmt)
    dsample = worst_case_text(dfmt, ttf)
    dw = awtk_width(ttf, dsample, o.date_size)
    side = 0 if o.battery == 'none' else 12 + img.w + 4      # keep clear of the gauge in the top right corner
    if dw > SCREEN_W - 2 * side: raise SystemExit(f'--date-size {o.date_size}: "{dsample}" is {dw} px, more than {SCREEN_W - 2 * side}')
    d_top, d_bot = ttf.digit_ink(o.date_size)
    date.y, date.h = text_box(ttf, o.date_size, o.top)
    date.x, date.w = 0, SCREEN_W
    for st in STATES:
        date.set(f'style:{st}:font_size', str(o.date_size)); date.set(f'style:{st}:text_align_h', 'center')
    date_ink_bot = o.top + d_bot - d_top

    fmt = o.clock_format or clock.get('format')
    sample = worst_case_text(fmt, ttf)
    size = fit_size(ttf, sample, SCREEN_W - 2 * o.clock_margin, o.clock_size)
    if size < o.clock_size: print(f'note: clock {o.clock_size} px does not fit "{sample}", using {size}', file=sys.stderr)
    c_top, c_bot = ttf.digit_ink(size)
    ink_h = c_bot - c_top
    room = card_y - date_ink_bot                          # date ink bottom .. card top
    if ink_h + 2 * 10 > room: raise SystemExit(f'clock {size} px ({ink_h:.0f} px of ink) does not fit the {room:.0f} px over the card')
    ink_top = min(date_ink_bot + (room - ink_h) / 2, card_y - size + c_top)   # centred, box kept off the card
    clock.y, clock.h = text_box(ttf, size, ink_top, pad=0)    # tight: digits have no descenders
    clock.x, clock.w = 0, SCREEN_W
    if o.clock_format: clock.set('format', o.clock_format)
    for st in STATES:
        clock.set(f'style:{st}:font_size', str(size)); clock.set(f'style:{st}:text_align_h', 'center')

    # --- battery: no percentage. The stock gauge (icon + fill), small, top right; or none.
    pg.props = list(STOCK_PGBAR)                            # undo the classic layout's text readout, if any
    gw, gh, ox, oy, pw, ph = STOCK_GAUGE
    if o.battery == 'icon':
        img.x, img.y = SCREEN_W - 12 - gw, round(o.top + (d_bot - d_top) / 2 - gh / 2)
        pg.x, pg.y, pg.w, pg.h = img.x + ox, img.y + oy, pw, ph
    else:
        hide(img); hide(pg)
    view.x, view.y, view.w = 0, 0, SCREEN_W
    view.h = max(clock.y + clock.h, date.y + date.h, img.y + img.h if o.battery == 'icon' else 0)
    assert view.h <= card_y, f'time block (0..{view.h}) runs into the card at {card_y}'
    cover_rect = (card_x + pad, card_y + pad, cs, cs)
    check_touch(root, cover_rect)
    return dict(clock_size=size, clock_format=fmt, clock_px=awtk_width(ttf, sample, size), date_format=dfmt,
                date_px=dw, card=(card_x, card_y, card_w, card_h), cover=cover_rect)

def art_mask(size, r, rgb):
    """Corners outside a rounded rect in the card colour, transparent inside (8x supersampled), so the
    app's square cover shows rounded on the card (as mod_nowplaying's np_artmask on Now Playing)."""
    from PIL import Image, ImageChops, ImageDraw
    s = 8; big = Image.new('L', (size * s, size * s), 0)
    ImageDraw.Draw(big).rounded_rectangle([0, 0, size * s - 1, size * s - 1], radius=r * s, fill=255)
    im = Image.new('RGBA', (size, size), rgb); im.putalpha(ImageChops.invert(big.resize((size, size), Image.LANCZOS)))
    return im

def write_mask(out, size, r, rgb):
    p = os.path.join(out, IMAGES, MASK + '.png')
    import io
    buf = io.BytesIO(); art_mask(size, r, rgb).save(buf, 'PNG', optimize=True)     # PIL writes no timestamp
    data = buf.getvalue()
    if os.path.exists(p): assert open(p, 'rb').read() == data, f'{p} exists with other content'
    else:
        open(p, 'wb').write(data); os.chmod(p, IMG_MODE); os.utime(p, (IMG_MTIME, IMG_MTIME))
    return len(data)

def edit_page_style(out):
    """The page theme's play / pause styles (the app swaps btn_play between them) point at the
    off-white np_* glyphs of the Now Playing look instead of the orange circles."""
    import awtk_style
    path = os.path.join(out, PAGE_STYLE)
    old = open(path, 'rb').read(); th = awtk_style.parse(old)
    assert awtk_style.serialize(th) == old, f'{path}: style round trip is not byte-exact'
    for name, (icon, down) in GLYPHS.items():
        items = th.find('button', name); assert len(items) == 5, name
        for it in items:
            assert it.get('icon') in (('pause1', 'pause1_down', 'play1', 'play1_down') + (icon, down)), (name, it.get('icon'))
            it.set('icon', down if it.state == 'pressed' else icon)
    new = awtk_style.serialize(th)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, mode | 0o200); open(path, 'wb').write(new); os.chmod(path, mode)
    return old, new

def added_rels(stock_rootfs=None):
    """Files --layout cover adds (fwtool --allow-added): the corner mask. build.py uses this tool as a
    look step only with --layout cover (look-lock2)."""
    return [f'{IMAGES.removeprefix("rootfs/")}/{MASK}.png']

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--layout', choices=['classic', 'cover'], default='classic',
                    help='classic: full-width clock, small date, battery row (default; V2.1cL/cLB/dE/eA); '
                         'cover: iPhone-style, date + clock at the top, a large rounded cover card (docs/lockscreen2.md)')
    ap.add_argument('--clock-format', help='digit_clock format for the clock (default: keep stock "hh:mm"; "HH:TT" = 12 h with AM/PM, fixed: the app does not switch it)')
    ap.add_argument('--clock-size', type=int, help='clock font size in px (classic default: largest that fits; cover default 88)')
    ap.add_argument('--clock-margin', type=int, default=11, help='min left/right margin for the auto clock size, '
                    'measured as AWTK lays the text out (default 11: "hh:mm" at 138 px is 297 px wide in the stock font)')
    ap.add_argument('--date-size', type=int, help='date font size in px (stock 50; default 24 classic, 20 cover)')
    ap.add_argument('--date-format', help='digit_clock format for the date (default: classic keeps stock "Y-MM-DD"; cover "W, MMM D" = "Monday, Oct 19")')
    ap.add_argument('--no-date', action='store_true', help='hide the date (classic)')
    ap.add_argument('--battery', choices=['icon+percent', 'percent', 'icon', 'none'],
                    help='icon+percent: "86%%" left of the state icon (classic default); percent: text only; '
                         'icon: stock gauge, no number (cover default, top right there); none: no battery (cover)')
    ap.add_argument('--battery-size', type=int, default=20, help='percentage font size in px (default 20)')
    ap.add_argument('--strip-y', type=int, help='move the now-playing strip to this y (stock 362; classic)')
    ap.add_argument('--cover-size', type=int, default=COVER_SRC, help=f'cover: art size in px (default {COVER_SRC}, the size demo writes the cover at: 1:1)')
    ap.add_argument('--radius', type=int, default=10, help='cover: art corner radius, 0 = square, no mask image (default 10)')
    ap.add_argument('--card', default=CARD_RGB, help=f'cover: opaque card colour under the art and text (default {CARD_RGB}, the stock strip)')
    ap.add_argument('--top', type=int, default=14, help='cover: y of the date ink (default 14)')
    ap.add_argument('--glyphs', choices=['stock', 'np'], default='stock',
                    help='cover: play/pause/next glyphs; np = the Now Playing look\'s off-white np_* (the tree must have them)')
    a = ap.parse_args()
    cover = a.layout == 'cover'
    if a.battery is None: a.battery = 'icon' if cover else 'icon+percent'
    if a.date_size is None: a.date_size = 20 if cover else 24
    if cover:
        if a.clock_size is None: a.clock_size = 88
        if a.battery not in ('icon', 'none'): ap.error('--layout cover shows no percentage: --battery icon or none')
        if a.no_date or a.strip_y is not None: ap.error('--no-date / --strip-y are classic-layout options')
        if not len(a.card) == 7 or not a.card.startswith('#'): ap.error('--card must be opaque #RRGGBB (the mask is painted in it)')
    elif a.battery == 'none' or a.glyphs != 'stock': ap.error('--battery none / --glyphs are cover-layout options')
    clone_workdir(a.src, a.out)
    ttf = Ttf(os.path.join(a.out, FONT))
    info = {}
    if cover:
        if a.glyphs == 'np':
            missing = [n for n in (*sum(GLYPHS.values(), ()), *NEXT_GLYPH) if not os.path.exists(os.path.join(a.out, IMAGES, n + '.png'))]
            if missing: raise SystemExit(f'--glyphs np: {", ".join(missing)} missing (run mod_nowplaying.py first)')
        old, new, root = edit_ui(os.path.join(a.out, UI), lambda root: info.update(apply_cover(root, ttf, a)))
        extra = ''
        if a.radius: extra += f'; {IMAGES}/{MASK}.png {write_mask(a.out, a.cover_size, a.radius, a.card)} bytes'
        if a.glyphs == 'np':
            so, sn = edit_page_style(a.out); extra += f'; {PAGE_STYLE} {len(so)} -> {len(sn)} bytes'
        print(f'lockscreen (cover): {UI} {len(old)} -> {len(new)} bytes{extra}')
        print(f'  clock "{info["clock_format"]}" {info["clock_size"]} px (widest {info["clock_px"]} px), date "{info["date_format"]}" '
              f'{a.date_size} px (widest {info["date_px"]} px), battery {a.battery}, card {info["card"]}, cover {info["cover"]}')
    else:
        old, new, root = edit_ui(os.path.join(a.out, UI), lambda root: info.update(apply(root, ttf, a)))
        print(f'lockscreen: {UI} {len(old)} -> {len(new)} bytes; clock "{info["clock_format"]}" {info["clock_size"]} px '
              f'(widest text {info["clock_px"]} of {SCREEN_W} px), date {"hidden" if a.no_date else str(a.date_size) + " px"}, battery {a.battery}')
    awtk_ui.dump(root.find('view_timeinfo'))
    w = root.find('view_bottomview'); print(f"view_bottomview xywh=({w.x},{w.y},{w.w},{w.h})")
    if cover: awtk_ui.dump(w)

if __name__ == '__main__': main()
