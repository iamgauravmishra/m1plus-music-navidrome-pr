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

Usage: mod_lockscreen.py SRC_WORKDIR OUT_WORKDIR [options]
  SRC_WORKDIR is what `fwtool.py unpack` produced (or another mod's output); OUT_WORKDIR is cloned from
  it and modified. OUT_WORKDIR == SRC_WORKDIR edits in place (used to stack on the battery mod).
"""
import argparse, math, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
from mod_battery import clone_workdir, edit_ui, style_as_text

UI = 'rootfs/release/assets/default/raw/ui/screensaver_page.bin'
FONT = 'rootfs/release/assets/default/raw/fonts/default.ttf'
SCREEN_W, SCREEN_H = 320, 480
STATES = ('normal', 'disable', 'focused')      # stock sets every text style for all three
GAP = 14                                       # px between the ink of stacked rows
ICON_GAP = 6                                   # px between percentage text and battery icon

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

def worst_case_text(fmt):
    """Widest string a digit_clock format can produce (digits as '0'; the stock font has tabular digits)."""
    out, i = '', 0
    while i < len(fmt):
        c = fmt[i]; n = 1
        while i + n < len(fmt) and fmt[i + n] == c: n += 1
        if c in 'YMDhHmsT' or c == 'w':
            if c == 'Y': out += '00' if n == 2 else '0000'
            elif c == 'M' and n == 3: out += 'WWW'      # month name: generous
            elif c == 'T' and n == 2: out += '00 PM'
            elif c == 'w': out += '0'
            else: out += '00'
        elif c == 'W': out += 'WWW'
        else: out += c * n
        i += n
    return out

def apply(root, ttf, o):
    view, clock, date = root.find('view_timeinfo'), root.find('dclock_time'), root.find('dclock_date')
    img, pg, strip, slide = root.find('img_battery'), root.find('pgbar_battery'), root.find('view_bottomview'), root.find('img_slide')
    assert all(w is not None for w in (view, clock, date, img, pg, strip, slide)), 'unexpected screensaver_page layout'
    assert clock.type == date.type == 'digit_clock' and pg.type == 'progress_bar' and img.type == 'image'
    assert img in view.children and pg in view.children and clock in view.children, 'battery/clock moved out of view_timeinfo?'

    # clock: largest size whose widest possible text fits the width minus margins
    fmt = o.clock_format or clock.get('format')
    sample = worst_case_text(fmt)
    fit = int((SCREEN_W - 2 * o.clock_margin) * ttf.units / sum(ttf.advance(c) for c in sample))
    size = o.clock_size or fit
    if size > fit: raise SystemExit(f'--clock-size {size}: "{fmt}" would need {ttf.width(sample, size):.0f} px, max size is {fit}')
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
    text_w = math.ceil(ttf.width('100%', o.battery_size)) + 2
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
    return dict(clock_size=size, clock_format=fmt, clock_px=round(ttf.width(sample, size)))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--clock-format', help='digit_clock format for the clock (default: keep stock "hh:mm"; "HH:TT" = 12 h with AM/PM, fixed: the app does not switch it)')
    ap.add_argument('--clock-size', type=int, help='clock font size in px (default: largest that fits)')
    ap.add_argument('--clock-margin', type=int, default=12, help='min left/right margin for the auto clock size (default 12)')
    ap.add_argument('--date-size', type=int, default=24, help='date font size in px (stock 50, default 24)')
    ap.add_argument('--date-format', help='digit_clock format for the date (default: keep stock "Y-MM-DD")')
    ap.add_argument('--no-date', action='store_true', help='hide the date')
    ap.add_argument('--battery', choices=['icon+percent', 'percent', 'icon'], default='icon+percent',
                    help='icon+percent: "86%%" left of the state icon (default); percent: text only; icon: stock gauge')
    ap.add_argument('--battery-size', type=int, default=20, help='percentage font size in px (default 20)')
    ap.add_argument('--strip-y', type=int, help='move the now-playing strip to this y (stock 362)')
    a = ap.parse_args()
    clone_workdir(a.src, a.out)
    ttf = Ttf(os.path.join(a.out, FONT))
    info = {}
    old, new, root = edit_ui(os.path.join(a.out, UI), lambda root: info.update(apply(root, ttf, a)))
    print(f'lockscreen: {UI} {len(old)} -> {len(new)} bytes; clock "{info["clock_format"]}" {info["clock_size"]} px '
          f'(widest text {info["clock_px"]} of {SCREEN_W} px), date {"hidden" if a.no_date else str(a.date_size) + " px"}, battery {a.battery}')
    awtk_ui.dump(root.find('view_timeinfo'))
    w = root.find('view_bottomview'); print(f"view_bottomview xywh=({w.x},{w.y},{w.w},{w.h})")

if __name__ == '__main__': main()
