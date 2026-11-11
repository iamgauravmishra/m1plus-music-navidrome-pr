"""The lock screen (ui/screensaver_page.bin; asset-only, except that the cover size constant in demo
changes). Layout and rules: docs/ui.md ("Lock screen").

Stock lock screen: wallpaper (img_screensaver), a 70 px clock left of a battery gauge, a 50 px date,
and the now-playing strip (view_bottomview). The result: date over a 68 px clock, centred at the top
(widest-case sized, measured as AWTK lays text out); a small battery gauge right on the date line
(tools/battery_art.py, the status bar's drawing); the now-playing block becomes a translucent card
(the glass image lk_card, 288 x 334, radius 18) centred, with the cover square at 264 x 264, title and
artist under it, play/next to their right; the swipe hint at 65 %. demo writes the cover at 264
(four pinned addiu immediates in parseplaycover_thd, 254 -> 264), so it is drawn 1:1 here and on Now Playing. The play and
next glyphs are the Now Playing look's off-white np_* images (mod_nowplaying must run first). The
app hides view_bottomview (visible and enable off) when nothing is queued; the page is then date +
clock on the wallpaper. Every property the layout relies on is set absolutely, so it does not depend
on earlier edits of the page.

What the app touches on this page, by name (demo, screensaver_page_init and its handlers):
img_screensaver (wallpaper image), view_timeinfo (shown/hidden by the "show time" screensaver
setting), app_gesture (swipe), btn_play, btn_next, img_battery (image set to screens_battery /
screens_charge / screens_lowbattery), pgbar_battery (value), view_bottomview (shown/hidden),
view_scrlabel_title, view_scrlabel_artist, view_img_icon. Nothing looks up dclock_time or dclock_date.
Names are kept, app-driven widgets are only moved/restyled.

Digit_clock format tokens in this AWTK build (wstr_format_date_time in demo, Shanling-modified):
  Y 2026   YY 26   M 1..12  MM 01..12  MMM month name   D / DD day   w weekday 0..6   W weekday name
  (MMM and W: short and in the UI language in the build, see patch_date_names)
  h / hh hour 0..23 (00..23)   H hour 0..23 unpadded   HH hour 01..12
  m / mm minute   s / ss second   T minute   TT minute + " AM"/" PM" (so "HH:TT" shows "05:30 PM")
  anything else is copied literally.

Fonts: the clock / date sizing reads fonts/default.ttf from OUT_WORKDIR, i.e. whatever font the tree
being built has at that point (the font step runs before this one). Widths are measured as AWTK lays
text out (tools/awtk_text.py), not as summed advances.

Usage: mod_lockscreen.py SRC_WORKDIR OUT_WORKDIR
  (OUT_WORKDIR == SRC_WORKDIR edits in place; OUT_WORKDIR is otherwise cloned from SRC_WORKDIR.)
"""
import os, stat, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
import battery_art
import cdefs
import statusbar
import pod_i18n
from awtk_text import MONTHS, WEEKDAYS, Ttf, awtk_width, fit_size, worst_case_text
from modlib import clone_workdir, edit_ui, png_bytes, sha256

from awtk_ui import RAW
UI = f'{RAW}/ui/screensaver_page.bin'
FONT = f'{RAW}/fonts/default.ttf'
PAGE_STYLE = f'{RAW}/styles/screensaver_page.bin'     # the page's window theme (default asset theme)
IMAGES = f'{RAW}/images/xx'
ASSETS = 'rootfs/release/assets'
SCREEN_W, SCREEN_H = 320, 480
STATES = ('normal', 'disable', 'focused')      # stock sets every text style for all three
BTN_STATES = ('normal', 'disable', 'focused', 'over', 'pressed')

# the layout
CLOCK_SIZE, CLOCK_MARGIN, DATE_SIZE, DATE_FORMAT = 68, 11, 20, 'W, MMM D'
TOP = 12                                       # y of the date ink
COVER_SIZE, PAD = 264, 12                      # art size (= what demo writes, and Now Playing's art) and card edge to cover
CARD_IMAGE = 'lk_card'                         # the glass image of the card (tools/mod_icons.py glass_image, GLASS_CARD: 288 x 334, r 18)
SLIDE_PCT = 65                                 # swipe hint size in % of the stock 48 x 22
TITLE_PX, ARTIST_PX = 20, 16                   # stock sizes of the strip's labels
TITLE_RGB, ARTIST_RGB = '#FFFFFF', '#DDDDDD'
BTN_W = 48                                     # play / next touch targets, side by side right of title / artist
COVER_SRC = 254                                # the size demo writes the cover at, stock
# pgbar_battery as shipped (stock screensaver_page.bin): the gauge fill inside screens_battery
STOCK_PGBAR = [('name', 'pgbar_battery'), ('style:normal:round_radius', '0'), ('style:disable:round_radius', '0'),
    ('style:focused:round_radius', '0'), ('style:normal:border_color', '#00000000'), ('style:normal:border', 'all'),
    ('style:disable:border', 'all'), ('style:focused:border', 'all'), ('style:normal:bg_color', '#00000000'),
    ('style:normal:fg_color', '#FFFFFF'), ('style:disable:bg_color', '#00000000'), ('style:focused:bg_color', '#00000000'),
    ('style:disable:fg_color', '#FFFFFF'), ('style:focused:fg_color', '#FFFFFF'), ('style:normal:text_color', '#444444'),
    ('style:disable:text_color', '#444444'), ('style:focused:text_color', '#444444'), ('value', '100')]
STOCK_IMG_SIZE = (40, 23)                     # img_battery w h
STOCK_SLIDE = (136, 448, 48, 22)              # img_slide (screens_rightslide.png, 48 x 22)
GLYPHS = {'btn_imgpause1_style': ('np_pause', 'np_pause_down'), 'btn_imgplay1_style': ('np_play', 'np_play_down')}
NEXT_GLYPH = ('np_next', 'np_next_down')

# The mini player layout (payload hook 24, patch/lockscreen.c): the numbers are patch/offsets.inc's (LK_*, and the Home bar's MB_*), read here so the C and the
# preview / tests cannot drift. Card in window coordinates, the other widgets in the card; apply_mini() is the layout the hook gives the same tree at run time.
_C = cdefs.defines(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'patch', 'offsets.inc'), strings=True)
DATE_WIDGET = _C['LK_DATE_NAME']
MINI_GLASS = 'mb_glass'
MINI_RECT = {'view_bottomview': (_C['LK_MINI_X'], _C['LK_MINI_Y'], _C['MB_W'], _C['MB_H']),
             'view_img_icon': (_C['MB_ART_X'], _C['MB_ART_Y'], _C['MB_ART'], _C['MB_ART']),
             'view_scrlabel_title': (_C['MB_TEXT_X'], _C['MB_TITLE_Y'], _C['MB_TEXT_W'], _C['MB_TITLE_H']),
             'view_scrlabel_artist': (_C['MB_TEXT_X'], _C['MB_ARTIST_Y'], _C['MB_TEXT_W'], _C['MB_ARTIST_H']),
             'btn_play': (_C['MB_PLAY_X'], 0, _C['MB_BTN_W'], _C['MB_H']),
             'btn_next': (_C['MB_NEXT_X'], 0, _C['MB_BTN_W'], _C['MB_H'])}
MINI_TITLE_PX, MINI_ARTIST_PX, MINI_ARTIST_RGB = _C['LK_TITLE_PX'], _C['LK_ARTIST_PX'], _C['LK_ARTIST_RGB']

# The small battery gauge: the app sets img_battery's image to screens_battery / screens_charge /
# screens_lowbattery (by name, 0x53f5f0..0x53f694, nowhere else in demo or the other ui files) and
# feeds pgbar_battery the level; pgbar_battery is drawn over the image (stock child order). So the
# three images are the status bar's own (tools/battery_art.py STATUS: the same outline, size and fill as the
# Home page's bar) with the fill box inside the outline, the image's right edge where the bar's is (x 310).
# pgbar_battery is moved before img_battery, so the fill is drawn under the image as in the status bar (the
# charging bolt stays whole). pod_pct_lk is the Battery Percentage's label (patch/battery.c bp_lock): hidden,
# the status bar label's size and colour, its text's right edge 4 px before the outline.
GAUGE_W, GAUGE_H = battery_art.STATUS.canvas
GAUGE_FILL = battery_art.STATUS.fill         # pgbar_battery inside the image: x, y, w, h
GAUGE_RIGHT = 310                            # the status bar outline's right edge
PCT_WIDGET, PCT_GAP, PCT_H = 'pod_pct_lk', 4, 16   # patch/battery.h BP_LABEL_LK
GAUGE_STATE = {'screens_battery': 'normal', 'screens_charge': 'charge', 'screens_lowbattery': 'low'}
SLIDE_IMAGE = 'screens_rightslide'           # only this page uses it
STOCK_IMAGE_SHA = {
    'default/raw/images/xx/screens_battery.png': 'ca8987a66727a419a3be2e61496edf28d94bfd4f1fd59e132a2e268977e214cc',
    'default/raw/images/xx/screens_charge.png': '7374f01d1fb13750085b2cc5f504f984face7a9b7b2b916379c14c5187dd88d9',
    'default/raw/images/xx/screens_lowbattery.png': '6d1a31498d081d8f18072836c1df193a661b2c260caaac67d8218ee6d75c45d4',
    'default/raw/images/xx/screens_rightslide.png': '7bacd75515db88fa2aab2af04b8440a5da11d75ff57c9bbaf3441338b910c28a'}

# The cover size demo writes. parseplaycover_thd (0x4ded84) runs once per new track
# (it polls a start flag every 100 ms and skips a path it already did) and writes
# toolsGetAlbumCover(track, "/tmp/coverpic.jpg", 254, 254) / toolsGetExternCover(track,
# "/tmp/externpic.jpg", 254, 254): fitted inside w x h (aspect kept, never upscaled), JPEG quality 90.
# The four `addiu a3/a2, zero, 0xfe` are the only place the size lives for local tracks; the 23 words
# around them (the two calls, their GOT loads and the file names) and the two GOT slots are pinned.
DEMO = 'rootfs/release/bin/demo'
COVER_CODE_VA = 0x4df1d4
COVER_CODE = bytes.fromhex('88b0e5261800bc8ffe000724fe0006242520a0027cb8998f09f8200301001724080057141800bc8f'
                           '0200022468f3998f78b8848f09f820030000c2aed9ff00101800bc8f80b8998ffe000724fe000624'
                           '5cb0052609f820032520a002')
COVER_IMM = (0x4df1dc, 0x4df1e0, 0x4df21c, 0x4df220)          # addiu a3 / a2, zero, size (x2)
COVER_GOT = {0x9ff74c: 0x5eaee0, 0x9ff750: 0x5eafec}         # toolsGetAlbumCover, toolsGetExternCover

def va_to_off(b, va):
    phoff = struct.unpack_from('<I', b, 28)[0]; size, num = struct.unpack_from('<HH', b, 42)
    for i in range(num):
        t, o, v, _, f = struct.unpack_from('<5I', b, phoff + i * size)
        if t == 1 and v <= va < v + f: return o + va - v
    raise ValueError(f'unmapped address {va:#x}')

def patch_cover_src(out, size):
    """demo writes /tmp/coverpic.jpg and /tmp/externpic.jpg at size x size instead of 254 x 254."""
    assert 66 <= size < 0x8000, size
    path = os.path.join(out, DEMO); b = bytearray(open(path, 'rb').read())
    off = va_to_off(b, COVER_CODE_VA)
    if b[off:off + len(COVER_CODE)] != COVER_CODE: raise SystemExit(f'{DEMO}: parseplaycover_thd cover call site is not the stock code')
    for va, want in COVER_GOT.items():
        got = struct.unpack_from('<I', b, va_to_off(b, va))[0]
        if got != want: raise SystemExit(f'{DEMO}: GOT {va:#x} = {got:#x}, expected {want:#x}')
    for va in COVER_IMM:
        o = va_to_off(b, va); w = struct.unpack_from('<I', b, o)[0]
        assert w in (0x240700fe, 0x240600fe), hex(w)
        struct.pack_into('<I', b, o, (w & 0xffff0000) | size)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, mode | 0o200); open(path, 'wb').write(b); os.chmod(path, mode)

# The date's names. demo's wstr_format_date_time (0x64e7b0, the digit_clock formatter; its only other caller is the unused file browser's "YY-MM-DD hh:mm:ss") writes MMM as
# locale_info_tr of the table 0x90497c's entry (stock's language files have no such keys, so English everywhere) and W by strcpy from one of two pointer tables in .data:
# 0x904960 ("星期日"..) when the locale's country is "CN" and its language "zh", 0x904944 ("Sunday"..) for every other language. Nothing else refers to the tables or loads
# their strings, and the lock screen's date is the only format with W or MMM. Two edits make the date the language's short one:
# - the English names are shortened where they are ("Sunday".. to "Sun".., "Sept" to "Sep"), which also makes them the keys of tools/pod_i18n.py (WEEKDAY_KEYS, MONTH_NAME_KEYS);
# - W takes the month's path. Its block begins at 0x64e934 (lw fp = wday; sltiu 7; beqz to the append; lw t9 in the delay slot, the same GOT word the month loads at
#   0x64ea90) and then clears a 32 byte buffer with six `sw zero` (0x64e944..0x64e958) before the locale test. Those six words become the month's own four (0x64ea94..0x64eaa0:
#   bal locale_info; nop; sll a2, fp, 2; addiu fp, s7, table) with the English weekday table, then `b 0x64eaa4; nop`, the month's tail: locale_info_tr of the entry,
#   tk_utf8_to_utf16 into the 32 character buffer, wstr_append. So every language's weekday is its language file's text of "Sun".. (English without one); the rest of the old
#   block (the locale test, the strcpy) and the zh_CN table are dead.
DATE_W_VA, DATE_M_VA, DATE_TAIL_VA = 0x64e934, 0x64ea90, 0x64eaa4
DATE_W_CODE = bytes.fromhex('10003e8e0700c22f670040105880998f9800a0af9c00a0afa000a0afa400a0afa800a0afac00a0af')   # 0x64e934..0x64e958, stock
DATE_M_CODE = bytes.fromhex('5880998f862711040000000080301e007c49fe261000bc8f252040002130de0064a8998fbf2811040000c58c200006241000bc8f252880022520400040d0998f'
                            '09f82003000000001000bc8f28da998f')                                              # 0x64ea90..0x64eadc, stock: the month's path
LOCALE_INFO_VA = 0x6588b0
STOCK_WEEKDAYS = 'Sunday Monday Tuesday Wednesday Thursday Friday Saturday'.split()
STOCK_MONTHS = 'Jan Feb Mar Apr May Jun Jul Aug Sept Oct Nov Dec'.split()
WEEKDAY_TABLE, MONTH_TABLE = 0x904944, 0x90497c
DATE_NAMES = (   # table, its strings' addresses, stock's strings, ours
    (WEEKDAY_TABLE, (0x75d0b8, 0x75d0c0, 0x75d0c8, 0x75d0d0, 0x75d0dc, 0x75d0e8, 0x75d0f0), STOCK_WEEKDAYS, WEEKDAYS),
    (MONTH_TABLE, (*range(0x75d150, 0x75d174, 4), 0x75d178, 0x75d17c, 0x75d180), STOCK_MONTHS, MONTHS),
)
assert tuple(WEEKDAYS) == pod_i18n.WEEKDAY_KEYS and tuple(MONTHS) == pod_i18n.MONTH_NAME_KEYS and DATE_FORMAT == pod_i18n.LOCK_DATE_KEY

def date_samples(ttf):
    """locale -> the widest date its format and names can make (the payload sets the format's translation, patch/lockscreen.c lk_date)."""
    out = {}
    for loc in pod_i18n.LOCALES:
        fmt, days, months = pod_i18n.lock_date(loc)
        assert len(fmt.encode()) < 0x40, (loc, fmt)        # digit_clock formats nothing for a longer one (0x626b60)
        assert all(len(s.encode('utf-16-le')) // 2 < 0x20 for s in days + months), loc      # the formatter's 32 character buffer
        out[loc] = worst_case_text(fmt, ttf, days, months)
    return out

def date_w_words():
    """The six words that send W down the month's path (see above)."""
    bal = lambda pc, to: 0x04110000 | ((to - pc - 4) >> 2) & 0xffff
    b = lambda pc, to: 0x10000000 | ((to - pc - 4) >> 2) & 0xffff
    at = DATE_W_VA + 16
    return (bal(at, LOCALE_INFO_VA), 0, 0x001e3080, 0x26fe0000 | WEEKDAY_TABLE & 0xffff, b(at + 16, DATE_TAIL_VA), 0)

def patch_date_names(out):
    """demo's weekday and month names become the short English ones (in place, NUL padded), and the weekday is translated as the month is."""
    path = os.path.join(out, DEMO); b = bytearray(open(path, 'rb').read())
    for va, code in ((DATE_W_VA, DATE_W_CODE), (DATE_M_VA, DATE_M_CODE)):
        o = va_to_off(b, va)
        if b[o:o + len(code)] != code: raise SystemExit(f'{DEMO}: wstr_format_date_time is not the stock code at {va:#x}')
    m = struct.unpack_from('<5I', DATE_M_CODE)
    assert m[0] == struct.unpack_from('<I', DATE_W_CODE, 12)[0] and m[1] == 0x04110000 | ((LOCALE_INFO_VA - DATE_M_VA - 8) >> 2) and m[3] == 0x001e3080 \
        and m[4] == 0x26fe0000 | MONTH_TABLE & 0xffff and MONTH_TABLE >> 16 == WEEKDAY_TABLE >> 16, 'the month path is what the weekday copies'
    struct.pack_into('<6I', b, va_to_off(b, DATE_W_VA + 16), *date_w_words())
    for table, addrs, olds, news in DATE_NAMES:
        assert len(addrs) == len(olds) == len(news), hex(table)
        got = struct.unpack_from(f'<{len(addrs)}I', b, va_to_off(b, table))
        if got != tuple(addrs): raise SystemExit(f'{DEMO}: the name table {table:#x} is not stock\'s')
        for va, old, new in zip(addrs, olds, news):
            o, old, new = va_to_off(b, va), old.encode() + b'\0', new.encode()
            if b[o:o + len(old)] != old: raise SystemExit(f'{DEMO}: {va:#x} is not {old[:-1].decode()!r}')
            assert len(new) < len(old), (old, new)       # stock's has its NUL
            b[o:o + len(old)] = new.ljust(len(old), b'\0')
    mode = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, mode | 0o200); open(path, 'wb').write(b); os.chmod(path, mode)

def slide_image(stock_png, w, h):
    """The stock swipe hint, resampled (premultiplied) to w x h."""
    from PIL import Image
    return Image.open(stock_png).convert('RGBA').convert('RGBa').resize((w, h), Image.LANCZOS).convert('RGBA')

def replace_stock_images(out, images):
    """{rel under assets: PIL image}: overwrite stock images (pinned by SHA-256), mode kept."""
    sizes = {}
    for rel, im in images.items():
        p = os.path.join(out, ASSETS, rel); old = open(p, 'rb').read()
        if sha256(old) != STOCK_IMAGE_SHA[rel]: raise SystemExit(f'{rel}: not the stock image (applied twice?)')
        data = im if isinstance(im, bytes) else png_bytes(im); mode = stat.S_IMODE(os.stat(p).st_mode)
        os.chmod(p, mode | 0o200); open(p, 'wb').write(data); os.chmod(p, mode)
        sizes[rel] = (len(old), len(data))
    return sizes

def text_style(w, px, rgb, align, states=STATES):
    for st in states:
        w.set(f'style:{st}:font_size', str(px)); w.set(f'style:{st}:text_color', rgb)
        w.set(f'style:{st}:text_align_h', align); w.set(f'style:{st}:text_align_v', 'middle')

def text_box(ttf, px, ink_top, pad=8):
    """(y, h) of a middle-aligned digit_clock box of font px (h = px + pad) whose digit ink starts at ink_top."""
    h = px + pad; top, _ = ttf.digit_ink(px)
    return round(ink_top - top - (h - px) // 2), h

def hit(w, rect, x, y):
    """demo's widget_find_target_default (docs/architecture.md): children from the top, the first with
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

def apply_mini(root):
    """The mini player layout on a screensaver_page tree (a model of what patch/lockscreen.c does at run time; the cover rect is returned for check_touch)."""
    for n, (x, y, w, h) in MINI_RECT.items():
        wd = root.find(n); assert wd is not None, n
        wd.x, wd.y, wd.w, wd.h = x, y, w, h
    strip, title, artist = root.find('view_bottomview'), root.find('view_scrlabel_title'), root.find('view_scrlabel_artist')
    assert strip.x + strip.w <= SCREEN_W and strip.y + strip.h <= SCREEN_H and strip.y + strip.h < root.find('img_slide').y
    for st in STATES:
        strip.set(f'style:{st}:bg_image', MINI_GLASS)
        title.set(f'style:{st}:font_size', str(MINI_TITLE_PX)); artist.set(f'style:{st}:font_size', str(MINI_ARTIST_PX))
        artist.set(f'style:{st}:text_color', MINI_ARTIST_RGB)
    x, y, w, h = MINI_RECT['view_img_icon']
    cover_rect = (strip.x + x, strip.y + y, w, h)
    check_touch(root, cover_rect)
    return cover_rect

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

def apply(root, ttf):
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
        'view_bottomview children changed (applied twice?)'
    assert (slide.x, slide.y, slide.w, slide.h) == STOCK_SLIDE and (img.w, img.h) == STOCK_IMG_SIZE

    # --- the swipe hint: smaller (pre-scaled image, drawn 1:1), centred where the stock one is
    sw, sh = round(STOCK_SLIDE[2] * SLIDE_PCT / 100), round(STOCK_SLIDE[3] * SLIDE_PCT / 100)
    slide.x, slide.y = STOCK_SLIDE[0] + (STOCK_SLIDE[2] - sw) // 2, STOCK_SLIDE[1] + (STOCK_SLIDE[3] - sh) // 2
    slide.w, slide.h = sw, sh

    # --- the card: cover, then title / artist on the left and play / next on the right under it
    cs, pad = COVER_SIZE, PAD
    card_w = cs + 2 * pad
    title_h, artist_h = TITLE_PX + 4, ARTIST_PX + 4
    card_h = pad + cs + 6 + title_h + artist_h + 8
    card_x, card_y = (SCREEN_W - card_w) // 2, slide.y - 10 - card_h        # 10 px over the swipe hint
    strip.x, strip.y, strip.w, strip.h = card_x, card_y, card_w, card_h
    import mod_icons
    assert (card_w, card_h) == mod_icons.GLASS_CARD[:2], f'the card is {card_w}x{card_h}, the glass image {mod_icons.GLASS_CARD[:2]}'
    for st in STATES:       # the glass image is the whole look (translucent fill, rim, rounded corners): nothing is filled under it
        strip.set(f'style:{st}:bg_color', '#00000000')
        strip.set(f'style:{st}:bg_image', CARD_IMAGE)
    icon.x, icon.y, icon.w, icon.h = pad, pad, cs, cs          # draw_type scale_auto stays: the cover is drawn 1:1
    icon.set('sensitive', 'false')                             # decorative; a touch falls through to the card
    btn_top = pad + cs + 2
    nxt.x, nxt.y, nxt.w, nxt.h = pad + cs - BTN_W, btn_top, BTN_W, card_h - btn_top
    play.x, play.y, play.w, play.h = nxt.x - BTN_W, btn_top, BTN_W, card_h - btn_top
    text_w = play.x - 4 - pad
    ty = pad + cs + 6
    title.x, title.y, title.w, title.h = pad, ty, text_w, title_h
    artist.x, artist.y, artist.w, artist.h = pad, ty + title_h, text_w, artist_h
    text_style(title, TITLE_PX, TITLE_RGB, 'left'); text_style(artist, ARTIST_PX, ARTIST_RGB, 'left')
    for st in BTN_STATES: nxt.set(f'style:{st}:bg_image', NEXT_GLYPH[st == 'pressed'])

    # --- date (small) over the clock, both centred at the top; nothing app-driven moves them
    for w in (clock, date, img, pg): w.remove('visible'); w.remove('sensitive')
    date.set('format', DATE_FORMAT)
    dsample = max(date_samples(ttf).values(), key=lambda s: awtk_width(ttf, s, DATE_SIZE))      # the widest date of the 13 languages
    dw = awtk_width(ttf, dsample, DATE_SIZE)
    pct_w = awtk_width(ttf, '100%', statusbar.PCT_PX)
    side = SCREEN_W - (GAUGE_RIGHT - GAUGE_W - PCT_GAP - pct_w) + 4    # keep clear of the gauge and its percentage in the top right corner
    if dw > SCREEN_W - 2 * side: raise SystemExit(f'date size {DATE_SIZE}: "{dsample}" is {dw} px, more than {SCREEN_W - 2 * side}')
    d_top, d_bot = ttf.digit_ink(DATE_SIZE)
    date.y, date.h = text_box(ttf, DATE_SIZE, TOP)
    date.x, date.w = 0, SCREEN_W
    for st in STATES:
        date.set(f'style:{st}:font_size', str(DATE_SIZE)); date.set(f'style:{st}:text_align_h', 'center')
    date_ink_bot = TOP + d_bot - d_top

    fmt = clock.get('format')
    sample = worst_case_text(fmt, ttf)
    size = fit_size(ttf, sample, SCREEN_W - 2 * CLOCK_MARGIN, CLOCK_SIZE)
    if size < CLOCK_SIZE: print(f'note: clock {CLOCK_SIZE} px does not fit "{sample}", using {size}', file=sys.stderr)
    c_top, c_bot = ttf.digit_ink(size)
    ink_h = c_bot - c_top
    room = card_y - date_ink_bot                          # date ink bottom .. card top
    if ink_h + 2 * 10 > room: raise SystemExit(f'clock {size} px ({ink_h:.0f} px of ink) does not fit the {room:.0f} px over the card')
    ink_top = min(date_ink_bot + (room - ink_h) / 2, card_y - size + c_top)   # centred, box kept off the card
    clock.y, clock.h = text_box(ttf, size, ink_top, pad=0)    # tight: digits have no descenders
    clock.x, clock.w = 0, SCREEN_W
    for st in STATES:
        clock.set(f'style:{st}:font_size', str(size)); clock.set(f'style:{st}:text_align_h', 'center')

    # --- battery: the status bar's gauge, right on the date line, and the hidden percentage label left of it.
    pg.props = list(STOCK_PGBAR)
    fx, fy, fw, fh = GAUGE_FILL
    img.w, img.h = GAUGE_W, GAUGE_H
    img.x, img.y = GAUGE_RIGHT - GAUGE_W, round(TOP + (d_bot - d_top) / 2 - GAUGE_H / 2)
    pg.x, pg.y, pg.w, pg.h = img.x + fx, img.y + fy, fw, fh
    view.children.remove(pg); view.children.insert(view.children.index(img), pg)
    pct = awtk_ui.Widget('label', img.x - PCT_GAP - pct_w, img.y + GAUGE_H // 2 - PCT_H // 2, pct_w, PCT_H, [('name', PCT_WIDGET), ('text', '87%'), ('visible', 'false'), ('sensitive', 'false')])
    text_style(pct, statusbar.PCT_PX, '#FFFFFF', 'right')
    view.children.append(pct)
    view.x, view.y, view.w = 0, 0, SCREEN_W
    view.h = max(clock.y + clock.h, date.y + date.h, img.y + img.h)
    assert view.h <= card_y, f'time block (0..{view.h}) runs into the card at {card_y}'
    cover_rect = (card_x + pad, card_y + pad, cs, cs)
    check_touch(root, cover_rect)
    return dict(clock_size=size, clock_format=fmt, clock_px=awtk_width(ttf, sample, size), date_format=DATE_FORMAT,
                date_px=dw, card=(card_x, card_y, card_w, card_h), cover=cover_rect)

def main():
    if len(sys.argv) != 3: sys.exit(__doc__)
    src, out = sys.argv[1:]
    clone_workdir(src, out)
    ttf = Ttf(os.path.join(out, FONT))
    missing = [n for n in (*sum(GLYPHS.values(), ()), *NEXT_GLYPH, CARD_IMAGE) if not os.path.exists(os.path.join(out, IMAGES, n + '.png'))]
    if missing: raise SystemExit(f'{", ".join(missing)} missing (run mod_nowplaying.py first)')
    info = {}
    old, new, root = edit_ui(os.path.join(out, UI), lambda root: info.update(apply(root, ttf)))
    so, sn = edit_page_style(out)
    images = {f'default/raw/images/xx/{n}.png': battery_art.png(battery_art.STATUS, st) for n, st in GAUGE_STATE.items()}
    sl = root.find('img_slide')
    images[f'default/raw/images/xx/{SLIDE_IMAGE}.png'] = slide_image(os.path.join(out, ASSETS, 'default', 'raw/images/xx', SLIDE_IMAGE + '.png'), sl.w, sl.h)
    extra = f'; {PAGE_STYLE} {len(so)} -> {len(sn)} bytes'
    for rel, (n0, n1) in replace_stock_images(out, images).items(): extra += f'; {rel} {n0} -> {n1} bytes'
    patch_cover_src(out, COVER_SIZE)
    patch_date_names(out)
    extra += f'; {DEMO}: parseplaycover_thd writes the cover at {COVER_SIZE} x {COVER_SIZE} (4 immediates at ' \
             + ', '.join(f'{va:#x}' for va in COVER_IMM) + f', {COVER_SRC} -> {COVER_SIZE}); short weekday and month names (tables ' \
             + ', '.join(f'{t:#x}' for t, *_ in DATE_NAMES) + ')'
    print(f'lockscreen: {UI} {len(old)} -> {len(new)} bytes{extra}')
    print(f'  clock "{info["clock_format"]}" {info["clock_size"]} px (widest {info["clock_px"]} px), date "{info["date_format"]}" '
          f'{DATE_SIZE} px (widest {info["date_px"]} px), card {info["card"]}, cover {info["cover"]}')
    awtk_ui.dump(root.find('view_timeinfo'))
    w = root.find('view_bottomview'); print(f"view_bottomview xywh=({w.x},{w.y},{w.w},{w.h})")
    awtk_ui.dump(w); s = root.find('img_slide'); print(f"img_slide xywh=({s.x},{s.y},{s.w},{s.h})")

if __name__ == '__main__': main()
