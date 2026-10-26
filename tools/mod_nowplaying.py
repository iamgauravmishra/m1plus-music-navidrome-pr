#!/usr/bin/env python3
"""iPod-style Now Playing for the Shanling M1 Plus (asset-only: ui + page theme + new images, no code).

Restyles the stock Now Playing page the way q2-pod (MIT) does on the Q2 (docs/ipod.md "Now Playing",
changelog 1.1.7), re-fitted to the M1 Plus's 320x450 portrait window:

  0   [<] 5/10           [heart] [...]         top row, 44 px touch targets: Back, index, heart (btn_fav), More
 44   +------------------------+
      |   cover 216 x 216      |                    slide page 1: rounded art (corner mask),
 262  Title                                          title 22 px white,
 288  Artist                                         artist 18 px #CCCCCC,
 310  Album                                          album 18 px #BBBBBB (left-aligned, cover width)
 342  ----------------------------                   thin 4 px line (#1C1C1C track, off-white fill, no thumb)
      0:15          . o .            6:20            in the stock 30 px seek target; times 14 px grey, page dots
 392  [mode] [<<]   [ > ]   [>>]    [queue]         58 px transport row (touchscreen), Tabler glyphs
 450

The Hi-Res tag (img_hr) is not shown: demo only toggles its visibility, so it is kept (every widget the app
looks up stays) at 0x0, insensitive.

Files (the mod touches nothing shared; every image is new and referenced only from these two files):
  ui/playing_page.bin      geometry and inline styles; every widget keeps its name and parent chain
                           except label_album, which moves from the info page into the album line
  styles/playing_page.bin  the page's own theme (searched before default.bin, see docs/ui.md):
                           mode/fav icons -> np_*, plus page-local btn_imgplay_style / btn_imgpause_style
                           and lyric line styles, so default.bin is never edited
  images/xx/np_*.png       Tabler glyphs (tools/mod_icons.py draws them; this step copies the committed PNGs)
                           and the corner mask (drawn here)

What demo drives here, by name (dis.py xref, docs/ui.md): scrlabel_title, scrlabel_artist,
img_playcover, label_index ("%d/%d"), label_info, label_album/genre/year/size/location ("%s:%s"),
label_playtime, label_playlen, slider_play, img_repeata/b (moved by code to x = 12 + pos*296/len,
y = 364, so the slider keeps x 12 w 296 and its bar centre at y 357), img_hr, img_mqa, btn_fav/more/
playmode/prev/play/next/queue/return, image_wait, slide_view, slide_indicator, view_lrc, scroll_lrc,
label_lyricmsg, view_local/view_dlna, app_gesture.

The album: stock has no album-only widget; label_album is filled with "%s:%s" (getFormatString("album")
+ ":" + album), e.g. "Album:Abbey Road". It is moved into a non-scrolling scroll_view (scroll_view clips
its children, a plain view does not) and offset left so that the "Album:" prefix lies left of the clip
edge and the line shows the album name only. The offset is computed the way demo lays text out (see
album_clip: stb advances truncated, +1 px after every glyph, hscroll_label margin_left 2), from the
fonts/default.ttf of the tree being edited, so it follows whatever font an earlier step installed; the
colon's ink is checked to end left of the edge and the album's first letter to keep all its ink. In
other UI languages the prefix differs ("专辑", "Альбом"...), so a part of it may show or the name's first
letters may be clipped (ALBUM_PREFIX is the English word).

Usage: mod_nowplaying.py SRC_WORKDIR OUT_WORKDIR
  OUT_WORKDIR == SRC_WORKDIR edits in place.
"""
import math, os, shutil, stat, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui, awtk_style, mod_icons
from modlib import clone_workdir, edit_ui
from awtk_text import Ttf, StbText, f32, STB_SPACING, STB_MISSING   # the shared AWTK text model

RAW = 'rootfs/release/assets/default/raw'
UI = f'{RAW}/ui/playing_page.bin'
STYLE = f'{RAW}/styles/playing_page.bin'
IMAGES = f'{RAW}/images/xx'
FONT = f'{RAW}/fonts/default.ttf'
DEFAULT_STYLE = f'{RAW}/styles/default.bin'
IMG_MODE, IMG_MTIME = 0o755, 1750924035     # most stock images are 755; a stock asset mtime, fixed for determinism

W, H = 320, 450                  # normal window under the 30 px status bar
STATES = ('normal', 'disable', 'focused')
BTN_STATES = ('normal', 'disable', 'focused', 'over', 'pressed')
BG = '#000000'                   # page black, as the status bar and q2-pod's Now Playing
FG = '#EEEEEC'                   # q2-pod MINIMAL_FILL: glyphs, progress fill, selected dot / lyric
DOWN = '#8C8C8C'                 # q2-pod SUDO_MUTED: pressed glyphs
TITLE_RGB, ARTIST_RGB, ALBUM_RGB, GREY = '#FFFFFF', '#CCCCCC', '#BBBBBB', '#AAAAAA'   # q2-pod NP_*
TITLE_PX, META_PX, TIMES_PX, INDEX_PX = 22, 18, 14, 16                                 # q2-pod NP_*_PX
TRACK = '#1C1C1C'                # progress track (q2-pod MINIMAL_TRACK)
DOT_OFF = '#555555'              # q2-pod inactive page dot

TOP = 44                         # top row and its touch targets
SLIDE_Y, SLIDE_H = TOP, 298      # slide pages 44..342
ART, ART_Y = 216, 2              # cover, page coords (the size before the Hi-Res tag and the foot buttons came and went)
ART_X = (W - ART) // 2           # 52; the text column uses the cover's edges
ART_R = 10                       # rounded corners (q2-pod NP_ART_RADIUS is 12 at 166 px; Apple's ~4.5%)
TITLE_Y, TITLE_H = ART_Y + ART + 6, 26
ARTIST_Y, META_H = TITLE_Y + TITLE_H, 22
ALBUM_Y = ARTIST_Y + META_H
MORE_W, FAV_W = 52, 52                                       # the top row's More and heart (btn_fav, left of More)
assert ALBUM_Y + META_H <= SLIDE_H
SLIDER = (12, 342, 296, 30)      # stock: the A-B markers are positioned by code for x 12 w 296, y 364
TIMES_Y, TIMES_H = 374, 18
ROW_Y = 392                      # transport row 392..450
ROW_H = H - ROW_Y
# transport slots: x, w (sum 320 incl. 4 px edges); the image_wait spinner centres on play
SLOTS = {'btn_playmode': (4, 56), 'btn_prev': (64, 60), 'btn_play': (124, 72), 'btn_next': (196, 60), 'btn_queue': (260, 56)}

# ---------------------------------------------------------------------------------------------- images

# PIL is imported where it is used, so build.py (plain python3) can import added_rels() without pillow
def art_mask(size, r):
    """Black corners outside a rounded rect, transparent inside: rounds whatever cover the app draws."""
    from PIL import Image, ImageChops, ImageDraw
    ss = 8
    big = Image.new('L', (size * ss, size * ss), 0)
    ImageDraw.Draw(big).rounded_rectangle([0, 0, size * ss - 1, size * ss - 1], radius=r * ss, fill=255)
    inside = big.resize((size, size), Image.LANCZOS)
    im = Image.new('RGBA', (size, size), BG); im.putalpha(ImageChops.invert(inside)); return im

def write_images(rootfs_xx):
    """The Tabler glyphs (committed PNGs of mod_icons.py) and the corner mask, as new files; returns the names."""
    for name in NP_IMAGES:
        p = os.path.join(rootfs_xx, name + '.png')
        assert not os.path.exists(p), p
        if name == 'np_artmask': art_mask(ART, ART_R).save(p, optimize=True)     # PIL PNG output has no timestamp
        else: shutil.copyfile(os.path.join(mod_icons.PNG, name + '.png'), p)
        os.chmod(p, IMG_MODE); os.utime(p, (IMG_MTIME, IMG_MTIME))
    return list(NP_IMAGES)

NP_IMAGES = sorted(mod_icons.np_names() + ['np_artmask'])

def added_rels(stock_rootfs=None):
    """Rootfs-relative paths of the added images (for fwtool --allow-added; all new in any tree)."""
    return [f'{IMAGES.removeprefix("rootfs/")}/{n}.png' for n in NP_IMAGES]

# ---------------------------------------------------------------------------------------------- ui

def each(w, states, prop, value):
    for st in states: w.set(f'style:{st}:{prop}', value)

def text_style(w, px, rgb, align):
    """Font, colour and alignment in every state: some labels on this page paint in the disable state
    (q2-pod found the same on the Q2), so a lone normal value would not apply."""
    each(w, STATES, 'font_size', str(px)); each(w, STATES, 'text_color', rgb); each(w, STATES, 'text_align_h', align)

def img_button(w, normal, pressed):
    for st in BTN_STATES: w.set(f'style:{st}:bg_image', pressed if st == 'pressed' else normal)

def move(w, x, y, ww, hh): w.x, w.y, w.w, w.h = x, y, ww, hh

def find(root, name):
    w = root.find(name); assert w is not None, f'playing_page: no widget {name!r}'; return w

def parent_of(root, child):
    for w in root.walk():
        if child in w.children: return w

def apply_ui(root, shift):
    names = [w.name for w in root.walk() if w.name]
    gesture, local = find(root, 'app_gesture'), find(root, 'view_local')
    svv, sv = find(root, 'slide_view_view'), find(root, 'slide_view')
    page1, lyr, info = (find(root, n) for n in ('view', 'view_lyrics', 'view_info'))
    assert sv.children == [page1, lyr, info] and parent_of(root, sv) is svv and parent_of(root, svv) is local, 'unexpected playing_page layout'

    root.set('style:normal:bg_color', BG)
    # the gesture/content area fills the 450 px window (stock: 438, centred)
    gesture.set('self_layout', f'default(x=c,y=m,w={W},h={H})'); move(gesture, 0, 0, W, H)
    move(local, 0, 0, W, H)

    # slide_view_view spans the top row down to the times row so the controls it parents (more, fav,
    # index, times, dots) stay inside it; later siblings (btn_return, slider, buttons) sit on top for touch
    move(svv, 0, 0, W, ROW_Y)
    sv.set('self_layout', f'default(x=0,y={SLIDE_Y},w=100%,h={SLIDE_H})'); move(sv, 0, SLIDE_Y, W, SLIDE_H)

    # ---- top row: Back, the index centred, heart, More; the play mode is the transport row's first slot
    ret = find(root, 'btn_return'); move(ret, 0, 0, 52, TOP)
    idx = find(root, 'label_index'); move(idx, 52, 0, W - 52 - MORE_W - FAV_W, TOP)
    text_style(idx, INDEX_PX, GREY, 'center'); each(idx, STATES, 'text_align_v', 'middle')
    fav = find(root, 'btn_fav'); move(fav, W - MORE_W - FAV_W, 0, FAV_W, TOP); fav.set('style:pressed:icon', 'np_unfav_down')
    more = find(root, 'btn_more'); move(more, W - MORE_W, 0, MORE_W, TOP); img_button(more, 'np_more', 'np_more_down')
    # the Hi-Res tag: demo only calls widget_set_visible on img_hr, so it stays in the tree, empty and insensitive
    hr = find(root, 'img_hr'); move(hr, 0, 0, 0, 0); hr.set('sensitive', 'false'); hr.set('visible', 'false')

    # ---- page 1: cover, mask, title / artist / album
    cover = find(root, 'img_playcover'); move(cover, ART_X, ART_Y, ART, ART)
    mask = awtk_ui.Widget('image', ART_X, ART_Y, ART, ART, [('name', 'img_np_artmask'), ('image', 'np_artmask'),
                          ('draw_type', 'default'), ('clickable', 'false'), ('sensitive', 'false')])
    title, artist = find(root, 'scrlabel_title'), find(root, 'scrlabel_artist')
    for w in (title, artist): parent_of(root, w).children.remove(w)
    move(title, ART_X, TITLE_Y, ART, TITLE_H); text_style(title, TITLE_PX, TITLE_RGB, 'left')
    move(artist, ART_X, ARTIST_Y, ART, META_H); text_style(artist, META_PX, ARTIST_RGB, 'left')
    album = find(root, 'label_album'); info.children.remove(album)
    text_style(album, META_PX, ALBUM_RGB, 'left')
    # a scroll_view clips its children; label_album sits `shift` px left of it so "Album:" is hidden
    clip = awtk_ui.Widget('scroll_view', ART_X, ALBUM_Y, ART, META_H, [('name', 'scroll_np_album'),
                          ('xslidable', 'false'), ('yslidable', 'false'), ('sensitive', 'false'), ('focusable', 'false')])
    move(album, -shift, 0, ART + shift, META_H); clip.children.append(album)
    page1.children += [mask, title, artist, clip]

    # ---- page 2: lyrics (stock 254 px column, taller); page 3: info (album moved out, lines re-spaced)
    lrc = find(root, 'view_lrc'); move(lrc, 33, 8, 254, SLIDE_H - 16)
    msg = find(root, 'label_lyricmsg'); move(msg, 0, (SLIDE_H - 28) // 2, W, 28); text_style(msg, META_PX, GREY, 'center')
    li = find(root, 'label_info'); move(li, 24, 24, W - 48, 24); text_style(li, META_PX, FG, 'center')
    y = 64
    for n in ('label_genre', 'label_year', 'label_size'):
        w = find(root, n); move(w, 24, y, W - 48, 24); text_style(w, META_PX, GREY, 'center'); y += 30
    loc = find(root, 'label_location'); move(loc, 24, y + 4, W - 48, SLIDE_H - y - 12); text_style(loc, 16, GREY, 'center')

    # ---- progress, times, page dots
    sl = find(root, 'slider_play'); move(sl, *SLIDER)
    each(sl, BTN_STATES, 'bg_color', TRACK); each(sl, BTN_STATES, 'fg_color', FG)
    each(sl, ('normal', 'pressed', 'over'), 'icon', '')   # no thumb: q2-pod's line is bare (drag works anywhere on the bar)
    pt, pl = find(root, 'label_playtime'), find(root, 'label_playlen')
    move(pt, SLIDER[0], TIMES_Y, 90, TIMES_H); text_style(pt, TIMES_PX, GREY, 'left')
    move(pl, SLIDER[0] + SLIDER[2] - 90, TIMES_Y, 90, TIMES_H); text_style(pl, TIMES_PX, GREY, 'right')
    dots = find(root, 'slide_indicator'); move(dots, (W - dots.w) // 2, TIMES_Y + (TIMES_H - dots.h) // 2, dots.w, dots.h)
    dots.set('style:normal:selected_fg_color', FG); dots.set('style:normal:fg_color', DOT_OFF)

    # ---- transport row
    vb = find(root, 'view_buttons'); move(vb, 0, ROW_Y, W, ROW_H)
    for n, (x, w) in SLOTS.items():
        b = find(root, n); b.set('self_layout', f'default(x={x},y=0,w={w},h=100%)'); move(b, x, 0, w, ROW_H)
    img_button(find(root, 'btn_prev'), 'np_prev', 'np_prev_down')
    img_button(find(root, 'btn_next'), 'np_next', 'np_next_down')
    img_button(find(root, 'btn_queue'), 'np_playqueue', 'np_playqueue_down')
    wait = find(root, 'image_wait'); x, w = SLOTS['btn_play']; move(wait, x + (w - 50) // 2, (ROW_H - 50) // 2, 50, 50)
    # decorative widgets on top of controls: this AWTK hit-tests hidden widgets too, so they must not take
    # touches (stock: the spinner covers the play button's centre, the A-B markers lie over the slider)
    for n in ('image_wait', 'img_repeata', 'img_repeatb'): find(root, n).set('sensitive', 'false')

    after = [w.name for w in root.walk() if w.name]
    assert sorted(set(names)) == sorted(set(after) - {'img_np_artmask', 'scroll_np_album'}), 'a widget name was lost'
    return root

# ---------------------------------------------------------------------------------------------- touch check

# view_dlna (full-size, last child) is shown/hidden *and* enabled/disabled by playing_choiceshowpage; in local
# playback it is disabled, so the model leaves it out as the device does.
RUNTIME_DISABLED = {'view_dlna'}
PROBES = ['btn_return', 'btn_more', 'btn_fav', 'slider_play', *SLOTS]

def _rect(w, parent_rect, dx=0):
    px, py, pw, ph = parent_rect
    sl = w.get('self_layout', '')
    ww = pw if 'w=100%' in sl else w.w
    hh = ph if 'h=100%' in sl else w.h
    return (px + w.x + dx, py + w.y, ww, hh)

def hit(w, rect, x, y):
    """demo's widget_find_target_default (docs/architecture.md): children from the top, the first with enable and
    sensitive set that contains the point; `visible` is not looked at."""
    for i, c in reversed(list(enumerate(w.children))):
        if c.get('sensitive') == 'false' or c.get('enable') == 'false' or c.name in RUNTIME_DISABLED: continue
        r = _rect(c, rect, i * rect[2] if w.type == 'slide_view' else 0)      # slide_view: page i at x = i * width
        if r[0] <= x < r[0] + r[2] and r[1] <= y < r[1] + r[3]:
            return hit(c, r, x, y)
    return w

def check_touch(root):
    """Every control's centre must reach that control; the cover must reach the slide_view (swipe)."""
    rects = {}
    def collect(w, rect):
        for i, c in enumerate(w.children):
            r = _rect(c, rect, i * rect[2] if w.type == 'slide_view' else 0); rects[c.name] = r; collect(c, r)
    collect(root, (0, 0, W, H))
    sv = find(root, 'slide_view')
    def under(t, anc): return t is anc or any(under(t, c) for c in anc.children) if t is not anc else True
    def inside(t, anc): return t is anc or any(inside(t, c) for c in anc.children)
    for n in PROBES:
        x, y, w, h = rects[n]; t = hit(root, (0, 0, W, H), x + w // 2, y + h // 2)
        assert inside(t, find(root, n)), f'touch at the centre of {n} lands on {t.name or t.type}'
        assert w >= 44 and h >= 30 and (n == 'slider_play' or h >= 44), f'{n}: touch target {w}x{h} too small'
    hr = find(root, 'img_hr'); assert hr.w == 0 and hr.h == 0 and hr.get('sensitive') == 'false', 'img_hr must stay out of the way'
    for x, y in ((W // 2, SLIDE_Y + ART_Y + ART // 2), (W // 2, SLIDE_Y + ALBUM_Y + 10)):
        t = hit(root, (0, 0, W, H), x, y)
        assert inside(t, sv), f'touch at ({x},{y}) on the cover page lands on {t.name or t.type}, not the slide_view'
    return [(n, rects[n]) for n in PROBES]

# ---------------------------------------------------------------------------------------------- page theme

ICONS = {'btn_imgrandom_style': 'np_random', 'btn_imgcycle_style': 'np_cycle', 'btn_imgcycle1_style': 'np_cycle1',
         'btn_imgorder_style': 'np_order', 'btn_imgfav_style': 'np_fav', 'btn_imgunfav_style': 'np_unfav'}
# play/pause: the app swaps btn_play between these default.bin styles; page-local copies win (the window
# theme is searched first) and leave default.bin, and every other page's play button, untouched.
PLAY = {'btn_imgplay_style': ('np_play', 'np_play_down'), 'btn_imgpause_style': ('np_pause', 'np_pause_down')}

def apply_style(th):
    for name, icon in ICONS.items():
        ss = th.find('button', name); assert len(ss) == 5, name
        for s in ss: s.set('icon', icon)
    template = th.find('button', 'btn_imgrandom_style')
    for name, (icon, down) in PLAY.items():
        assert not th.find(style=name), f'{name} already in the page theme'
        for t in template:
            s = awtk_style.Item('button', name, t.state, list(t.props))
            s.set('icon', down if t.state == 'pressed' else icon); th.items.append(s)
    # lyrics: other lines quiet grey, the current one off-white (stock: white / orange #FE7E40)
    for name, rgb in (('listitem_lyric_style', DOWN), ('listitem_sellyric_style', FG)):
        assert not th.find(style=name)
        for st in BTN_STATES:
            s = awtk_style.Item('list_item', name, st)
            s.set('text_align_h', 1, awtk_style.T_INT32)       # as default.bin (centre)
            s.set_color('bg_color', '#00000000'); s.set_color('border_color', '#00000000')
            s.set('font_size', 18); s.set_color('text_color', rgb); th.items.append(s)
    return th

def edit_style(path):
    old = open(path, 'rb').read()
    th = awtk_style.parse(old)
    assert awtk_style.serialize(th) == old, f'{path}: style round trip is not byte-exact'
    new = awtk_style.serialize(apply_style(th))
    mode = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, mode | 0o200); open(path, 'wb').write(new); os.chmod(path, mode)
    return old, new

# ---------------------------------------------------------------------------------------------- album prefix

# How demo lays a label's text out (disassembly of the stock demo, docs/ui.md "The album line"):
#   font    stb_truetype: scale = font_size / (hhea ascender - descender), float32 (stbtt_ScaleForPixelHeight
#           at 0x67cb9c); advance = trunc(advance * scale) (trunc.w.s at 0x680438 -> glyph_t.advance); glyph
#           box x0 = floor(xMin * scale), x1 = ceil(xMax * scale), the bitmap drawn at pen + x0
#   canvas  the lcd (lcd_mem, from lcd_linux_fb_create) has no draw_text / measure_text, so canvas_draw_text
#           (0x645348) and canvas_measure_text (0x644544) step the pen by advance + 1 after every glyph
#           (0x6454d4 / 0x6446c8); a glyph the font cannot give adds 4
#   label   hscroll_label paints from margin_left, default 2 (style_get_int(style, "margin_left", 2) at
#           0x609dac; margin_right likewise), and clips its text to [margin_left, w - margin_right]
HSCROLL_MARGIN = 2
ALBUM_SAFETY = 1           # clear columns wanted between the prefix's last ink column and the clip edge
# first characters an album may start with that must keep all their ink: printable ASCII, Latin-1 letters
FIRST_LETTERS = ''.join(map(chr, range(0x21, 0x7f))) + ''.join(chr(c) for c in range(0xc0, 0x100) if c not in (0xd7, 0xf7))

def style_int(raw_dir, wd, key, default):
    """An int style prop of playing_page widget wd, the same in every text state: inline, then the window
    theme, then default.bin (the first theme with the (type, style, state) item answers, as AWTK)."""
    themes = [awtk_style.parse(open(os.path.join(raw_dir, os.path.relpath(f, RAW)), 'rb').read()) for f in (STYLE, DEFAULT_STYLE)]
    vals = set()
    for st in STATES:
        v = wd.get(f'style:{st}:{key}')
        if v is None:
            for th in themes:
                items = [it for it in th.items if (it.widget, it.style, it.state) == (wd.type, wd.get('style', 'default'), st)]
                if items: v = items[0].get(key); break
        vals.add(default if v is None else int(v))
    assert len(vals) == 1, f'{wd.name}: {key} differs between states: {vals}'
    return vals.pop()

def album_clip(ttf, prefix, px, margin):
    """Offset of label_album inside scroll_np_album that hides `prefix` (e.g. "Album:").

    In clip coordinates the label starts at -shift and its text at -shift + margin. shift is the prefix's
    AWTK width, or more if needed to put every prefix ink column left of x 0 with ALBUM_SAFETY clear
    columns; the safety drops to 0 if it would cut the ink of a FIRST_LETTERS glyph. The prefix is always
    hidden; if that still cuts a first letter (a font with a wide colon or deep left overhangs), a warning
    names the letters."""
    st = StbText(ttf, px)
    missing = [c for c in prefix if not st.has(c)]
    assert not missing, f'album prefix {prefix!r}: no glyph for {missing} in default.ttf'
    pens, width = st.layout(prefix)
    ink = [(p + b[0], p + b[1]) for c, p in pens if (b := st.box(c))]
    ink_end = max(e for _, e in ink)                         # text coordinates, exclusive
    first = min((st.box(c)[0], c) for c in FIRST_LETTERS if st.has(c) and st.box(c))
    for safety in (ALBUM_SAFETY, 0):
        shift = max(width, margin + ink_end + safety)        # prefix ink ends at column -1 - safety
        album_pen = margin - shift + width                   # clip x of the album's first pen position
        if album_pen + first[0] >= 0: break
    cut = sorted(c for c in FIRST_LETTERS if st.has(c) and st.box(c) and album_pen + st.box(c)[0] < 0)
    if cut:      # hiding the prefix wins; say which first letters lose their leftmost column(s)
        print(f'WARNING: album prefix {prefix!r}: an album starting with {"".join(cut)!r} loses ink left of the clip', file=sys.stderr)
    assert margin - shift + ink_end <= 0
    return {'shift': shift, 'width': width, 'margin': margin, 'safety': safety, 'album_pen': album_pen,
            'prefix_ink': (margin - shift + ink[0][0], margin - shift + ink_end), 'first': first,
            'colon': (st.advance(prefix[-1]), st.box(prefix[-1])), 'cut': cut}

# ---------------------------------------------------------------------------------------------- main

ALBUM_PREFIX = 'Album'      # the English UI's "album" string; the app fills label_album with "Album:<name>"

def main():
    if len(sys.argv) != 3: sys.exit(__doc__)
    src, out = sys.argv[1:]
    clone_workdir(src, out)
    # measured with the font of the tree being edited (an earlier step may have replaced default.ttf)
    raw = os.path.join(out, RAW)
    album = find(awtk_ui.parse(open(os.path.join(out, UI), 'rb').read()), 'label_album')
    clip = album_clip(Ttf(os.path.join(out, FONT)), ALBUM_PREFIX + ':', META_PX,
                      style_int(raw, album, 'margin_left', HSCROLL_MARGIN))
    xx = os.path.join(out, IMAGES)
    clash = [n for n in added_rels() if os.path.exists(os.path.join(out, 'rootfs', n))]
    assert not clash, f'np_* images already present (tree already modded?): {clash}'
    old, new, root = edit_ui(os.path.join(out, UI), lambda r: check_touch(apply_ui(r, clip['shift'])))
    sold, snew = edit_style(os.path.join(out, STYLE))
    imgs = write_images(xx)
    size = sum(os.path.getsize(os.path.join(xx, n + '.png')) for n in imgs)
    print(f'nowplaying: {UI} {len(old)} -> {len(new)} bytes; {STYLE} {len(sold)} -> {len(snew)} bytes; '
          f'{len(imgs)} images added ({size} bytes)')
    c = clip
    print(f'  album prefix "{ALBUM_PREFIX}:" at {META_PX} px: AWTK width {c["width"]} px (advances + 1 each), '
          f'margin_left {c["margin"]}; label at x -{c["shift"]} in scroll_np_album: prefix ink x {c["prefix_ink"][0]}..'
          f'{c["prefix_ink"][1] - 1} (colon advance {c["colon"][0]}, box {c["colon"][1]}), album pen x {c["album_pen"]} '
          f'(safety {c["safety"]} px; widest left overhang {c["first"][1]!r} x0 {c["first"][0]})')

if __name__ == '__main__': main()
