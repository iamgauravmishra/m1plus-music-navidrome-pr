"""The virtual iPod Classic (patch/ipod.c, tools/pod_ui.py build_ipod_page, tools/mod_icons.py ipod_wheel, docs/modules/ipod.md): the menu item, the asset (a fullscreen
320 x 480 window, the screen view and the wheel's touch view, the hit test with demo's own widget_find_target, the wheel picture), the wheel's angle math against math.atan2,
the page's open / destroy / background / foreground, the paint of the main menu, the lists, the title bar and Now Playing, the wheel (one row per 15 degrees, reversal hysteresis, the chord dead zone, tiers on long lists, the hard stop at the ends, the centre
button, the four ring sectors, the taps that are not taps, the touch outside the circle), the navigation (Albums -> an album's tracks -> play, Artists, Songs,
Playlists, the existing Cover Flow page), the main menu's cover pane (q2-pod's pan: the playing album's cover or a random one, one decode and none in paint, a 1:1 copy moving a whole pixel at a time, the timer's fast and slow interval), Shuffle Songs on the page's own
Now Playing, the Settings list (Shuffle, Repeat, About, Customize), the stock calls (loadAlbumdetailList, start_player, the quick clicks), a stock list replaced under the page,
and the texts in all 13 languages."""
import math, os, re, struct
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import mod_icons
from awtk_text import Ttf, StbText
from unicorn.mips_const import UC_MIPS_REG_F0

UI = os.path.join('rootfs', 'release/assets/default/raw/ui/m1plus_ipod.bin')
EVT_DOWN, EVT_MOVE, EVT_UP, EVT_ABORT = O['EVT_POINTER_DOWN'], O['EVT_POINTER_MOVE'], O['EVT_POINTER_UP'], O['EVT_POINTER_ABORT']
EVT_BG, EVT_FG, EVT_DESTROY, EVT_PAINT = O['EVT_WINDOW_TO_BG'], O['EVT_WINDOW_TO_FG'], O['EVT_DESTROY'], O['EVT_AFTER_PAINT']
WIN = 0x24100000
SHOWLIST, PLAYLIST, CLASSINFO, G_CLASS, SYSBAR = (pod.DATA[k][0] for k in ('PDEQ_SHOWLIST', 'PDEQ_PLAYLIST', 'CLASSINFO', 'G_CLASS_TYPE', 'SYSTEM_BAR'))
FORCE = pod.DATA['FORCE_REFRESH'][0]
WX, WY, WD, RING, HUB = O['IP_WHEEL_X'], O['IP_WHEEL_Y'], O['IP_WHEEL_D'], O['IP_RING_R'], O['IP_HUB_R']
CX, CY = WX + WD // 2, WY + WD // 2        # the wheel's centre in the window
STEP_DEG = O['IP_STEP'] / 16
ROWS, ROWH, BARH = O['IP_ROWS'], O['IP_ROW_H'], O['IP_BAR_H']
STYLES = ('label_ip_row', 'label_ip_sel', 'label_ip_title', 'label_ip_small', 'label_ip_np1', 'label_ip_np2', 'label_ip_time')
MAIN_KEYS = ['Cover Flow', 'Albums', 'Artists', 'Songs', 'Playlists', 'Shuffle Songs', 'cdrippersettings', 'Now Playing']
TRAPS = ('coverflow_open', 'pod_open_settings')
SET_KEYS = ['Shuffle', 'Repeat', 'About', 'Customize']
PANE = (O['IP_PANE_X'], BARH, O['IP_PANE_W'], O['IP_SCREEN_H'] - BARH)   # the cover pane: the cover fills it edge to edge


def sel_colour(rgb): return 0xff000000 | rgb


def ip_lerp(a, b, i, n):
    """patch/ipod.c ip_lerp: the colour a .. b (r | g << 8 | b << 16) at i of n - 1, C's truncating division."""
    def ch(k):
        x, y = a >> k & 255, b >> k & 255; q = (y - x) * i; d = n - 1 if n > 1 else 1
        return x + (abs(q) // d) * (1 if q >= 0 else -1)
    return ch(0) | ch(8) << 8 | ch(16) << 16


class IM(Machine):
    """The machine plus what the page calls that the shared mocks do not know: the player's status and quick clicks, the album track query, the playing time, a string
    property, and the payload's other pages (Cover Flow, Settings, Shuffle: trapped at their entry, the page's own calls are the evidence)."""
    def __init__(self):
        super().__init__()
        self.status, self.cmds, self.pt, self.battery_img = 3, [], None, 'bar_power'
        self.album_tracks, self.opened = {}, []
        self.window = WIN
        self.top_main = WIN
        self.load_image = 0
        self.canvas = self.alloc(0x80)
        for w in STYLES + ('ipod_screen', 'ipod_wheel', 'pgbar_battery', 'img_battery'): Machine.widget(self, w)
        self.setword(SYSBAR, self.alloc(0x80))
        self.props[(self.widgets['pgbar_battery'], 'value')] = 80
        # the wheel as a widget struct (demo's own widget_to_local walks x, y and the parent): window (0, 0) > wheel (WX, WY)
        win, wheel = self.alloc(0x80), self.widgets['ipod_wheel']
        for off, v in ((0, 0), (4, 0), (8, 320), (0xc, 480), (0x44, 0)): self.setword(win + off, v)
        for off, v in ((0, WX), (4, WY), (8, WD), (0xc, WD), (0x44, win)): self.setword(wheel + off, v)
        self.images = {'p_default': (24, 24, bytes((0x40, 0x40, 0x40, 255)) * 576)}
        for n in TRAPS: self.handlers[PSYMS[n]] = n
        for n in ('mclGetPlayStatus', 'playpause_quick_click', 'next_quick_click', 'prev_quick_click', 'loadAlbumdetailList', 'get_playtimeandlength'):
            self.handlers[pod.FUNCTIONS[n][2]] = n
        self.stock_songlist = True
        self.wall = 1800000000 + 4 * 3600 + 59 * 60   # 12:59 UTC (1800000000 is 08:00)
        self.strings = {'cdrippersettings': 'Settings'}   # the stock key the Settings row uses (the shipped table says Settings)
        self.present.add('/mnt/mmc/m/1.flac')

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address, '')
        a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        ret = None
        if name in TRAPS: self.calls.append((name,)); self.opened.append(name); ret = 0
        elif name == 'mclGetPlayStatus': ret = self.status
        elif name == 'playpause_quick_click':
            self.calls.append(('playpause_quick_click',)); self.cmds.append(('playpause',)); self.status = 2 if self.status != 2 else 3; ret = 1
        elif name in ('next_quick_click', 'prev_quick_click'):
            self.calls.append((name, a1)); self.cmds.append((name[:4], self.word(a0 + 8), a1)); ret = 1
        elif name == 'get_playtimeandlength':
            if self.pt: self.setword(a0, self.pt[0]); self.setword(a1, self.pt[1])
            ret = 1 if self.pt else 0
        elif name == 'loadAlbumdetailList':
            rec = a1
            album = self.read_cstr(self.word(rec + O['REC_ALBUM']))
            tracks = list(self.album_tracks.get(album, []))
            self.calls.append(('loadAlbumdetailList', a0, album))
            self.setword(SHOWLIST, self.new_deque(tracks))
            self.setword(CLASSINFO, 0xff10 if a0 == O['CLASS_ALBUMS'] else 0xff11)
            ret = len(tracks)
        elif name == 'widget_get_prop_str':
            prop = self.read_cstr(a1)
            ret = self.cstr(self.battery_img) if prop == 'image' else a2
        if ret is None: return super()._hook(u, address, size, _)
        u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff)
        u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    # ---- the world
    def song(self, title, artist='Artist', album='Album', rid=1, path='/mnt/mmc/m/1.flac', name='1.flac', cd=0):
        r = self.record(album=album, artist=artist, path=path, title=title, name=name, rid=rid)
        self.setword(r + O['REC_DISC'], cd)
        return r

    def open(self):
        self.calls = []
        ret = self.call(PSYMS['ipod_open'], count=3000000)
        return ret & 0xffffffff

    def paint(self):
        """One EVT_AFTER_PAINT on the screen view: (texts, fills, blits) of that frame."""
        ev = self.alloc(0x40); self.u.mem_write(ev, bytes(0x40)); self.setword(ev + O['EVENT_PAINT_CANVAS'], self.canvas)
        self.texts, self.fills, self.blits, self.text_styles = [], [], [], []
        self.call(PSYMS['ip_on_paint'], a0=0, a1=ev, count=8000000)
        return list(self.texts), list(self.fills), list(self.blits)

    def ptr(self, kind, x, y, t=0, count=4000000):
        """A pointer event at window point (x, y) to the wheel's handler."""
        e = self.alloc(0x30); self.u.mem_write(e, bytes(0x30))
        self.setword(e, {'down': EVT_DOWN, 'move': EVT_MOVE, 'up': EVT_UP, 'abort': EVT_ABORT}[kind]); self.setword(e + 8, t); self.setword(e + 0x18, x); self.setword(e + 0x1c, y)
        self.call(PSYMS['ip_on_wheel'], a0=0, a1=e, count=count)

    def polar(self, deg, r):
        """The window point at `deg` clockwise from 12 o'clock and radius r from the wheel's centre."""
        return CX + round(r * math.sin(math.radians(deg))), CY - round(r * math.cos(math.radians(deg)))

    def tap(self, x, y):
        self.ptr('down', x, y, 1000); calls = list(self.calls)
        self.ptr('up', x, y, 1080); self.calls = calls + self.calls

    def turn(self, a0, a1, r=80, step=6, dt=100):
        """A finger turning from angle a0 to a1 (degrees, either direction) at radius r, a sample every `step` degrees; the calls of the whole drag."""
        calls = []
        n = max(1, round(abs(a1 - a0) / step))
        x, y = self.polar(a0, r); self.ptr('down', x, y, 1000); calls += self.calls
        for i in range(1, n + 1):
            x, y = self.polar(a0 + (a1 - a0) * i / n, r); self.ptr('move', x, y, 1000 + dt * i); calls += self.calls
        self.ptr('up', x, y, 2000); self.calls = calls + self.calls

    def sel(self):
        """(level kind, sel, top) of the front level, read from the state struct by the painted frame: the selected row's text."""
        texts, fills, _ = self.paint()
        return texts, fills


def machine(albums=(), artists=(), songs=(), playlists=()):
    m = IM()
    m.class_lists[O['CLASS_ALBUMS']] = [m.record(album=a, artist=ar, path=f'/mnt/mmc/m/{a}.flac', title=a, rid=100 + i) for i, (a, ar) in enumerate(albums)]
    m.class_lists[O['CLASS_ARTISTS']] = [m.record(title=a, artist=a, album=a, path='', rid=200 + i) for i, a in enumerate(artists)]
    m.class_lists[O['CLASS_ALL_SONGS']] = [m.song(t, rid=300 + i, path=f'/mnt/mmc/m/{i}.flac', name=f'{i}.flac') for i, t in enumerate(songs)]
    m.playlists = [m.record(title=n, album='', artist='', path='', rid=400 + i) for i, n in enumerate(playlists)]
    for i, r in enumerate(m.playlists): m.setword(r + O['REC_DISC'], 7 + i)   # a playlist's id
    for a, tracks in {a: [m.song(f'{a} {k}', album=a, rid=500 + k, path=f'/mnt/mmc/m/{a}-{k}.flac', name=f'{a}-{k}.flac') for k in range(3)] for a, _ in albums}.items():
        m.album_tracks[a] = tracks
        for r in tracks: m.present.add(m.read_cstr(m.word(r + O['REC_PATH'])))
    return m


def opened(m, **kw):
    m2 = machine(**kw) if kw else m
    assert m2.open() == 0
    m2.timers = []
    return m2


def texts_of(frame): return [t for t, _ in frame[0]]
def rows_of(texts): return [t for t, r in sorted(texts, key=lambda tr: tr[1][1]) if r[0] == 10 and BARH <= r[1] < 240]   # the list rows, top to bottom (the selected row is drawn last)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------
def angle_tests(ctx):
    """ip_angle against math.atan2 (clockwise from 12 o'clock, sixteenths of a degree) at every degree and a few radii, ip_turn's wrap."""
    expect = ctx.expect
    m = IM()
    worst, bad = 0, []
    for r in (5, 18, 45, 80, 110):
        for d in range(0, 360):
            dx, dy = round(r * math.sin(math.radians(d))), -round(r * math.cos(math.radians(d)))
            if not dx and not dy: continue
            want = (math.degrees(math.atan2(dx, -dy)) % 360) * 16
            got = m.call(PSYMS['ip_angle'], a0=dx, a1=dy)
            err = abs((got - want + 2880) % 5760 - 2880)
            worst = max(worst, err / 16)
            if err > 24: bad.append((dx, dy, got / 16, want / 16))   # 1.5 degrees: the point's own rounding to whole pixels at r = 5
    expect(not bad, f'ip_angle follows atan2 at 1,800 points ({bad[:3]})')
    big = [(r, d) for r in (80, 110) for d in range(0, 360)]
    errs = [abs((m.call(PSYMS['ip_angle'], a0=round(r * math.sin(math.radians(d)) * 100), a1=-round(r * math.cos(math.radians(d)) * 100)) - d * 16 + 2880) % 5760 - 2880) for r, d in big]
    expect(max(errs) <= 6, f'on large coordinates (no pixel rounding) the error is under 0.4 degree ({max(errs) / 16:.3f})')
    expect([m.call(PSYMS['ip_angle'], a0=x, a1=y) for x, y in ((0, -10), (10, 0), (0, 10), (-10, 0), (0, 0))] == [0, 1440, 2880, 4320, 0],
           'the four axes are 0, 90, 180 and 270 degrees, the centre is 0')
    turn = lambda a, b: struct.unpack('<i', struct.pack('<I', m.call(PSYMS['ip_turn'], a0=a, a1=b)))[0]
    expect((turn(100, 200), turn(200, 100), turn(5700, 60), turn(60, 5700), turn(0, 2879), turn(0, 2881)) == (100, -100, 120, -120, 2879, -2879),
           'ip_turn takes the shorter way round, across 12 o\'clock too')
    expect(O['IP_STEP'] == 240 and STEP_DEG == 15.0, 'one wheel step is 15 degrees, 24 to a turn (the real wheel is about 15-20)')


def asset_tests(ctx):
    expect = ctx.expect
    path = os.path.join(WORK, UI)
    tree = awtk_ui.parse(open(path, 'rb').read())
    expect(tree.name == 'm1plus_ipod_page' and tree.get('fullscreen') == 'true' and (tree.w, tree.h) == (0, 0),
           'the window is fullscreen (the lock screen\'s property: 480 px, the status bar not drawn)')
    expect(all(tree.get(f'style:{st}:bg_color') == '#C6C9CE' for st in ('normal', 'disable', 'focused')), 'its colour is the wheel body\'s')
    by = {w.name: w for w in tree.walk() if w.name}
    scr, wh, img = by['ipod_screen'], by['ipod_wheel'], by['ipod_wheel_img']
    expect((scr.x, scr.y, scr.w, scr.h) == (0, 0, 320, 240) == (0, 0, O['IP_W'], O['IP_SCREEN_H']) and scr.get('sensitive') == 'false',
           'the iPod screen: 320 x 240 on top (the 4:3 of the real one), insensitive (the payload paints it)')
    expect((wh.x, wh.y, wh.w, wh.h) == (50, 250, 220, 220) == (WX, WY, WD, WD) and wh.get('sensitive') != 'false' and wh.get('visible') != 'false',
           'the wheel\'s touch view: 220 x 220 at (50, 250), below the screen, inside the window (480)')
    expect((img.x, img.y, img.w, img.h) == (0, 0, 220, 220) and img.get('sensitive') == 'false' and img.get('image') == 'ipod_wheel' and img.get('draw_type') == 'default',
           'its picture is an insensitive image child (decorative overlays never take a touch)')
    expect(BARH + ROWS * ROWH == O['IP_SCREEN_H'] and ROWS == 8 and ROWH == 27 and BARH == 24, 'a 24 px title bar and eight 27 px rows fill the 240 px screen')
    expect(WY + WD <= 480 and WX + WD <= 320 and WY >= 240, 'the wheel is inside the lower 240 px')
    expect(mod_icons.IPOD_WHEEL_D == WD and mod_icons.IPOD_HUB_R == HUB == 45 and RING == WD // 2, 'the wheel picture\'s numbers are offsets.inc\'s: a 220 px ring, a 90 px centre button')
    # the style labels: hidden, insensitive, in the colour of what they sit on, the sizes of the mock
    want = {'label_ip_row': (17, '#000000'), 'label_ip_sel': (17, '#FFFFFF'), 'label_ip_title': (16, '#000000'),
            'label_ip_small': (14, '#666666'), 'label_ip_np1': (18, '#000000'), 'label_ip_np2': (16, '#666666'), 'label_ip_time': (14, '#666666')}
    expect(all(by[n].get('visible') == 'false' and by[n].get('sensitive') == 'false' and by[n].get('style:normal:font_size') == str(px)
               and by[n].get('style:normal:text_color') == col for n, (px, col) in want.items()), 'seven hidden, insensitive style labels: sizes and colours')
    expect({n: by[n].get('style:normal:text_align_h') for n in ('label_ip_title', 'label_ip_time', 'label_ip_row')} == {'label_ip_title': 'left', 'label_ip_time': 'right', 'label_ip_row': 'left'},
           'the title is left aligned (as the iPod\'s bar), the remaining time right aligned')
    expect(by['label_title'].get('tr_text') is None and by['label_title'].get('text') == 'Pod' and by['label_title'].get('visible') == 'false', 'label_title is the hidden brand text "iPod"')
    # demo's own hit test: the wheel takes touches, the screen and the picture never
    root = asset_tree(os.path.join(WORK, UI)); root.h = 480
    m = Machine()
    for x, y, what, want_last in ((CX, CY, 'the centre button', 'ipod_wheel'), (CX, WY + 8, 'the MENU label', 'ipod_wheel'), (CX - 90, CY, 'the previous label', 'ipod_wheel'),
                                  (CX + 90, CY, 'the next label', 'ipod_wheel'), (CX, CY + 90, 'the play / pause label', 'ipod_wheel'), (WX + 3, WY + 3, 'the square\'s corner', 'ipod_wheel'),
                                  (160, 100, 'the screen', 'm1plus_ipod_page'), (10, 245, 'beside the wheel', 'm1plus_ipod_page'), (300, 470, 'the window\'s corner', 'm1plus_ipod_page')):
        got = stock_target(m, root, x, y)
        expect(got[-1] == want_last and 'ipod_wheel_img' not in got and 'ipod_screen' not in got, f'a touch on {what} reaches {want_last} ({got})')
    # the wheel picture
    wp = asset_image('ipod_wheel')
    expect(wp.size == (220, 220) and wp.getpixel((0, 0))[3] == 0 and wp.getpixel((219, 219))[3] == 0 and wp.getpixel((110, 110))[3] == 255 and wp.getpixel((110, 3))[3] == 255,
           'the wheel image is 220 px: transparent corners, opaque ring and centre button')
    expect(open(os.path.join(mod_icons.PNG, 'ipod_wheel.png'), 'rb').read() == png_of(mod_icons.ipod_wheel()) and mod_icons.ipod_wheel().size == (220, 220),
           'the committed PNG is the generator\'s output')
    ring_px, hub_px = wp.getpixel((110, 40)), wp.getpixel((110, 100))
    expect(sum(ring_px[:3]) > sum(hub_px[:3]) - 120 and ring_px != hub_px, 'the centre button is drawn apart from the ring')


def menu_tests(ctx):
    expect, P = ctx.expect, pod_pages
    item = next(i for i, r in enumerate(P.ITEMS) if r.label == 'Pod')
    expect(item == 19 == len(P.ITEMS) - 2 and P.ITEMS[item].action == P.ACT_IPOD == 22 and P.ID_CHARS[item] == 'k' and item not in P.DEFAULT_MENU,
           'Pod is menu item 19 (saved as "k"), after Customize and before Podcasts, hidden by default like Now Playing: Customize > Main Menu shows it, the Extras page lists it')
    expect(P.EXTRAS_ORDER.index(item) == P.EXTRAS_GROUPS[0][1].index('Pod') and P.parse_menu_full(b'123456k\n') == ([1, 2, 3, 4, 5, 6, 19], []) and P.format_menu([1, 2, 19]) == '12k\n',
           'Extras lists it in the Play group, after Now Playing and Shuffle; the saved list carries it as k')
    expect(pod_i18n.key_for('Pod') is None and 'Pod' in pod_i18n.BRANDS, 'the label is the brand name "iPod", a plain text in every language (as M1+ Music and Tidal)')
    page = P.MENU
    rows0 = PSYMS['pod_rows_0']
    m = IM()
    m.widgets = {n: 0x30000000 + i for i, n in enumerate(['btn_return', 'btn_backtoplayer'])}
    m.windows['m1plus_ipod'] = WIN
    m.call(PSYMS['on_row'], a0=rows0 + 12 * item, count=5000000)
    expect(('window_open', 'm1plus_ipod') in m.calls and 'stock_resume' not in m.names(), 'the menu row opens m1plus_ipod')
    for page_ in (P.MENU, P.EXTRAS_PAGE): expect(page_.rows[item].label == 'Pod' and page_.rows[item].action == P.ACT_IPOD, f'{page_.key} has the row, same action')
    ui = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui')
    for key in ('m1plus_menu', 'm1plus_extras', 'm1plus_mainmenu'):
        t = awtk_ui.parse(open(os.path.join(ui, key + '.bin'), 'rb').read())
        row = t.find(f'pod_row{item}')
        lab = next(c for c in row.children if c.type == 'hscroll_label')
        expect(pod_i18n.shown_english(lab) == 'Pod' and row.find('pod_icon') is not None, f'{key}: row {item} reads iPod with its glyph')
    expect(asset_image('pod_ic_ipod').size == mod_icons.asset_size('pod_ic_ipod') if hasattr(mod_icons, 'asset_size') else asset_image('pod_ic_ipod').size[0] > 0, 'the row glyph is in the tree')


def open_tests(ctx):
    expect = ctx.expect
    m = machine(albums=[('Kind of Blue', 'Miles Davis')])
    m.windows['m1plus_ipod'] = 0
    expect(m.open() == 0xffffffff and 'timer_add' not in m.names() and 'widget_on' not in m.names(), 'a window that will not open: -1, nothing registered, no timer')
    m = machine()
    del m.widgets['ipod_wheel']
    expect(m.open() == 0xffffffff and 'navigator_back' in m.names() and m.timers == [], 'an asset that is not ours (no wheel): the window goes again, no timer')
    m = machine()
    expect(m.open() == 0, 'the page opens')
    c = m.calls
    on = {(a, e): (f, x) for _, a, e, f, x in (c_ for c_ in c if c_[0] == 'widget_on')}
    wheel, screen = m.widgets['ipod_wheel'], m.widgets['ipod_screen']
    expect(all((wheel, e) in on for e in (EVT_DOWN, EVT_MOVE, EVT_UP, EVT_ABORT)) and (screen, EVT_PAINT) in on and all((WIN, e) in on for e in (EVT_DESTROY, EVT_BG, EVT_FG)),
           'the wheel takes the four pointer events, the screen its own paint, the window its three events: nothing else is registered')
    expect(len(on) == 8 and [c_[0] for c_ in c].count('timer_add') == 1 and ('timer_add', PSYMS['ip_first'], O['IP_FIRST_MS']) in c, 'one page-scoped timer, a 50 ms one-shot')
    expect(not any(n in m.names() for n in ('widget_set_visible', 'widget_move', 'widget_resize', 'widget_destroy', 'widget_set_name')), 'it moves, hides and destroys nothing in the asset')
    expect(m.open() == 0 and m.names().count('window_open') == 0, 'opening again while it is up does nothing')
    # the timer
    m.calls = []; m.call(PSYMS['ip_first'], a0=0, count=40000000)
    expect(('timer_add', PSYMS['ip_tick'], O['IP_DRIFT_MS']) in m.calls, 'the one-shot starts the tick (the cover pane\'s pan on the main menu: IP_DRIFT_MS)')
    expect(any(c_[0] == 'bitmap_create_ex' and c_[1:] == (O['IP_ART'], O['IP_ART']) for c_ in m.calls), 'and makes the cover bitmap (the stock disc: nothing is playing)')
    # background / foreground / destroy
    m.calls = []; m.fire(EVT_BG, WIN)
    expect(('timer_remove', 0x777) in m.calls or m.timers is not None, 'to the background: the timer goes')
    m.calls = []; m.fire(EVT_FG, WIN)
    expect(('timer_add', PSYMS['ip_first'], O['IP_FIRST_MS']) in m.calls, 'to the foreground: it is armed again')
    m.calls = []; m.fire(EVT_DESTROY, WIN)
    expect(('timer_remove', 0x777) in m.calls and any(c_[0] == 'bitmap_destroy' for c_ in m.calls), 'destroy: the timer is removed and the cover bitmap freed')
    m.calls = []; m.timers = []
    expect(m.open() == 0 and ('window_open', 'm1plus_ipod') in m.calls, 'the state is clean: it opens again')
    fn, ctx = m.bound[(WIN, EVT_DESTROY)]
    m.calls = []; m.call(fn, a0=0x24100008, a1=0)   # the destroy of another window (an older page): the page is left alone
    expect('timer_remove' not in m.names() and 'bitmap_destroy' not in m.names(), 'a destroy of another window leaves the page alone')


def paint_tests(ctx):
    expect = ctx.expect
    m = machine(albums=[('Kind of Blue', 'Miles Davis'), ('Homogenic', 'Bjork')])
    m.open(); m.timers = []
    m.call(PSYMS['ip_first'], a0=0, count=40000000)
    texts, fills, blits = m.paint()
    names = [t for t, _ in texts]
    expect('M1+ Music' in names, f'the title bar: M1+ Music ({names})')
    rows = rows_of(texts)
    expect(rows == [m.tr(k) for k in MAIN_KEYS], f'the eight main menu rows in the iPod order, in the language of the player ({rows})')
    ys = sorted(r[1] for t, r in texts if t in rows)
    expect(ys == [BARH + i * ROWH for i in range(8)], 'on a 27 px pitch from the title bar')
    expect(all(r[2] == O['IP_SPLIT_X'] - 10 - 22 for t, r in texts if t in rows), 'in the list\'s width: the left pane of the split screen')
    expect(any(f[0] == 0xff000000 | O['IP_SEL_TOP'] and f[2] == BARH and f[3] == O['IP_SPLIT_X'] for f in fills), 'the first row is the selection: the classic blue gradient starts with its top colour')
    grad = [f for f in fills if f[2] >= BARH and f[3] == O['IP_SPLIT_X'] and f[4] == 1]
    expect(len(grad) == ROWH and grad[0][0] == 0xff000000 | O['IP_SEL_TOP'] and grad[-1][0] == 0xff000000 | O['IP_SEL_BOT'] and [g[2] for g in grad] == list(range(BARH, BARH + ROWH)),
           'a 27 line gradient from #5FB1F7 to #0C62D2 under the selected row')
    expect(not blits, 'the cover pane is plain until the timer has chosen and decoded covers (paint decodes nothing)')
    expect(any(f[1] == O['IP_SPLIT_X'] and f[3] == 1 for f in fills), 'a hairline divides the pane from the list')
    # the title bar, as the iPod's: the title on the left, no clock; the battery (the stock bar's own value), the play state next to it
    title = [r for t, r in texts if t == 'M1+ Music']
    expect(title and title[0][0] == 8 and title[0][0] + title[0][2] <= 320 - 32 - 14 - 8, f'the title on the left, clear of the play state ({title})')
    expect(not [t for t in names if ':' in t], f'no clock ({names})')
    batt = [f for f in fills if f[1] == 320 - 32 + 2 and f[2] == BARH // 2 - 5 + 2]
    expect(batt and batt[0][3] == 16 * 80 // 100 and batt[0][0] == 0xff000000 | 0x4cb84c, f'the battery: the status bar\'s 80 % as a 12 px green fill ({batt})')
    m.battery_img = 'bar_charge'; m.props[(m.widgets['pgbar_battery'], 'value')] = 100
    batt = [f for f in m.paint()[1] if f[1] == 320 - 32 + 2 and f[2] == BARH // 2 - 5 + 2]
    expect(batt and batt[0][3] == 16 and batt[0][0] == 0xff000000 | 0x59c734, 'charging: the fill is green and full')
    m.props[(m.widgets['pgbar_battery'], 'value')] = 20; m.battery_img = 'bar_power'
    batt = [f for f in m.paint()[1] if f[1] == 320 - 32 + 2 and f[2] == BARH // 2 - 5 + 2]
    expect(batt and batt[0][0] == 0xff000000 | 0x4814ff, 'at 20 % the fill is red')
    m.setword(SYSBAR, 0)
    expect(not [f for f in m.paint()[1] if f[1] == 320 - 30], 'with no status bar there is no fill (and no crash)')
    m.setword(SYSBAR, m.alloc(0x80))
    m.status = 2
    top = BARH // 2 - 5   # the battery's rows 7 .. 16: every glyph of the bar shares them (one centre line, shot-0014)
    gx = 320 - 32 - 14   # the play state's box, 8 px wide, 6 px left of the battery
    blue = [0xff000000 | ip_lerp(O['IP_SEL_TOP'], O['IP_SEL_BOT'], r, 10) for r in range(10)]
    in_box = lambda fills: [f for f in fills if gx <= f[1] < gx + 8 and f[2] < BARH and f[4] == 1]
    glyph = in_box(m.paint()[1])
    expect([(f[1], f[2], f[3]) for f in glyph] == [(gx + 3, top + r, min(r, 9 - r) + 1) for r in range(10)] and [f[0] for f in glyph] == blue,
           f'playing: a blue triangle (the selection\'s gradient) next to the battery, on its rows {top} .. {top + 9} ({glyph})')
    m.status = 3
    glyph = in_box(m.paint()[1])
    expect(sorted((f[1], f[2], f[3]) for f in glyph) == sorted((x, top + r, 3) for r in range(10) for x in (gx, gx + 5)) and {f[0] for f in glyph} == set(blue),
           'paused: two blue bars 3 px wide, on the battery\'s rows')
    m.status = 0
    expect(not in_box(m.paint()[1]), 'nothing played: no glyph')
    # chevrons: as the iPod, only the selected row has one (white, on the selection)
    chev = [f for f in m.paint()[1] if f[3] == 2 and f[4] == 1 and BARH <= f[2] < 240 and f[1] < O['IP_SPLIT_X']]
    expect(len(chev) == 9 and all(f[0] == 0xffffffff and BARH <= f[2] < BARH + ROWH for f in chev), f'one chevron, on the selected row ({len(chev)} fills)')
    # another language
    m.set_language('ru_RU')
    t2 = rows_of(m.paint()[0])
    expect(t2[:5] == [pod_i18n.TEXT[k]['ru_RU'] for k in MAIN_KEYS[:5]] and t2[1] != 'Albums', f'the rows follow Settings > Language ({t2[:3]})')


def wheel_tests(ctx):
    expect = ctx.expect
    m = machine(albums=[(f'Album {i}', 'A') for i in range(5)], songs=[f'Song {i:02d}' for i in range(30)])
    m.open(); m.timers = []
    def selected():
        texts, fills, _ = m.paint()
        ys = [f[2] for f in fills if f[4] == 1 and f[3] == (O['IP_SPLIT_X'] if not m.in_list else 320) and f[2] >= BARH]
        return min(ys) if ys else None
    m.in_list = False
    def row():
        y = selected()
        return None if y is None else (y - BARH) // ROWH
    expect(row() == 0, 'the first row is selected')
    # a drag of 60 degrees turns three steps, on every start angle
    for start in (0, 37, 90, 181, 270, 333):
        m = machine(albums=[('A', 'x')]); m.open(); m.timers = []; m.in_list = False
        m.turn(start, start + STEP_DEG * 3 + 4)
        expect(row() == 3, f'a 49 degree turn clockwise from {start}: three steps down ({row()})')
        m.turn(start, start - STEP_DEG * 2 - 4)
        expect(row() == 1, f'and a 34 degree turn back from there: two steps up ({row()})')
    m = machine(); m.open(); m.timers = []; m.in_list = False
    m.turn(10, 10 + STEP_DEG * 3 + 5)
    expect(row() == 3, 'three steps of 15 degrees: row 3')
    m.turn(100, 100 - STEP_DEG * 2 - 5)
    expect(row() == 1, 'two steps back: row 1')
    m.turn(100, 100 - STEP_DEG * 5 - 5)
    expect(row() == 0, 'the cursor stops at the first row (no wrap, as the iPod)')
    m.turn(200, 200 + STEP_DEG * 30)
    expect(row() == 7, 'and at the last (Now Playing, the eighth)')
    # a small turn is no step, a turn at the edge of the dead zone / outside
    m = machine(); m.open(); m.timers = []; m.in_list = False
    m.turn(30, 30 + 12, r=80)
    expect(row() == 0, 'a 12 degree wobble is no step')
    m.turn(30, 30 + 200, r=10)
    expect(row() == 0, 'a finger inside the dead zone (a touch that began on the centre button) turns nothing')
    m.turn(30, 30 + 54 + 1, r=HUB + 5)
    expect(row() == 3, 'a finger just outside the centre button turns the wheel (three steps)')
    m.turn(30, 30 + 54 + 1, r=RING - 3)
    expect(row() == 6, 'and one at the rim of the ring does too')
    # a drag that starts on the centre button turns nothing
    m = machine(); m.open(); m.timers = []; m.in_list = False
    m.turn(30, 30 + 100, r=30)
    expect(row() == 0, 'a drag that begins on the centre button turns nothing (and is no tap)')
    expect('start_player' not in m.names() and not m.opened and m.names().count('loadLocalClassList') == 0, 'and selects nothing')
    # a long list: the cursor leads the window
    m = machine(songs=[f'Song {i:02d}' for i in range(30)]); m.open(); m.timers = []
    m.in_list = False
    m.turn(0, STEP_DEG * 3 + 5)   # Songs (row 3)
    m.tap(CX, CY)
    m.in_list = True
    texts, fills, _ = m.paint()
    expect(rows_of(texts)[:2] == ['Song 00', 'Song 01'] and 'Songs' in [t for t, _ in texts], 'Songs: the library list, the title Songs')
    m.turn(0, STEP_DEG * 12 + 5)
    texts, fills, _ = m.paint()
    rows = rows_of(texts)
    expect(row() == 7 and rows[0] == 'Song 05' and rows[-1] == 'Song 12', f'twelve steps down: the cursor is on the 8th row, the list scrolled to keep it in view ({rows[0]}..{rows[-1]}, row {row()})')
    m.turn(0, -(STEP_DEG * 4 + 5))
    rows = rows_of(m.paint()[0])
    expect(row() == 3 and rows[0] == 'Song 05', 'four back: the cursor moves up inside the window, which stays')
    m.turn(0, -(STEP_DEG * 8 + 5))
    rows = rows_of(m.paint()[0])
    expect(row() == 0 and rows[0] == 'Song 00' or (rows[0] == 'Song 00' and row() == 0), f'past the top of the window: it scrolls up with the cursor ({rows[0]}, {row()})')


def tap_tests(ctx):
    expect = ctx.expect
    m = machine(albums=[('Kind of Blue', 'Miles Davis')]); m.open(); m.timers = []
    # MENU: the top sector, on the main menu closes the page
    for deg in (-40, -10, 0, 25, 44):
        m = machine(); m.open(); m.timers = []
        x, y = m.polar(deg, 85); m.tap(x, y)
        expect(m.names().count('navigator_back') == 1, f'a tap at {deg} degrees (top sector): MENU closes the page from the main menu')
    for deg, want in ((60, 'next'), (90, 'next'), (120, 'next'), (240, 'prev'), (270, 'prev'), (300, 'prev'), (150, 'playpause'), (180, 'playpause'), (210, 'playpause')):
        m = machine(); m.open(); m.timers = []
        x, y = m.polar(deg, 85); m.tap(x, y)
        got = m.cmds[0][0] if m.cmds else None
        expect(got == want and 'navigator_back' not in m.names(), f'a tap at {deg} degrees: {want} ({got})')
    # the quick clicks get the event time stock reads
    m = machine(); m.open(); m.timers = []
    x, y = m.polar(90, 85); m.tap(x, y)
    expect(m.cmds == [('next', 1080, 0)], f'next_quick_click gets the touch\'s own event (its time word is what stock compares) ({m.cmds})')
    x, y = m.polar(270, 85); m.tap(x, y)
    expect(m.cmds[-1] == ('prev', 1080, 0), 'previous is the same call')
    # outside the circle: the square's corners and the beyond-ring margin
    m = machine(); m.open(); m.timers = []
    for x, y in ((WX + 3, WY + 3), (WX + WD - 3, WY + 3), (WX + 3, WY + WD - 3), (WX + WD - 3, WY + WD - 3), (CX + 108, CY + 40)):
        m.tap(x, y)
        expect(not m.cmds and 'navigator_back' not in m.names() and not m.opened and 'widget_grab' not in m.names(), f'a touch at ({x}, {y}) outside the circle does nothing and takes no grab')
    # the grab: held for the touch, released at its end
    x, y = m.polar(90, 85)
    m.ptr('down', x, y, 5); expect(('widget_grab', WIN, m.widgets['ipod_wheel']) in m.calls, 'the touch is grabbed (moves and the release come to the wheel wherever they go)')
    m.ptr('up', x, y, 90); expect(('widget_ungrab', WIN, m.widgets['ipod_wheel']) in m.calls, 'and released at the end')
    m.cmds = []
    m.ptr('down', x, y, 5); m.ptr('abort', x, y, 6); expect(('widget_ungrab', WIN, m.widgets['ipod_wheel']) in m.calls and not m.cmds, 'an abort ends it and acts on nothing')
    m.ptr('up', x, y, 9)
    expect(not m.cmds, 'an up after the abort is nothing')
    # a tap that travels is not a tap
    m = machine(); m.open(); m.timers = []
    x, y = m.polar(90, 85)
    m.ptr('down', x, y, 5); m.ptr('move', x + 14, y, 20); m.ptr('up', x + 14, y, 40)
    expect(not m.cmds, 'a touch that travels 14 px and turns no step is no tap')
    m.ptr('down', x, y, 5); m.ptr('move', x + 6, y, 20); m.ptr('up', x + 6, y, 40)
    expect(m.cmds and m.cmds[-1][0] == 'next', 'a touch that wobbles 6 px is')
    # a tap after a turn is not a tap either (the turn already acted)
    m = machine(); m.open(); m.timers = []
    m.turn(0, 40, r=85)
    expect(not m.cmds and 'navigator_back' not in m.names(), 'a turn that ends in the top sector is not MENU')


def nav_tests(ctx):
    expect = ctx.expect
    m = machine(albums=[('Kind of Blue', 'Miles Davis'), ('Homogenic', 'Bjork')], artists=['Miles Davis', 'Bjork'], songs=['So What', 'Freddie'], playlists=['Road', 'Gym'])
    m.artist_albums = {'Miles Davis': [m.record(album='Kind of Blue', artist='Miles Davis', path='/mnt/mmc/m/Kind of Blue.flac', rid=900)]}
    m.album_tracks['Kind of Blue'] = m.album_tracks['Kind of Blue']
    m.open(); m.timers = []
    def centre(): m.tap(CX, CY)
    def step_to(n):
        m.turn(0, STEP_DEG * n + 5)
    def front():
        texts, fills, _ = m.paint()
        return rows_of(texts), [t for t, r in texts if r[0] != 10 or r[1] < BARH]
    # Albums
    step_to(1); centre()
    expect(('loadLocalClassList', O['CLASS_ALBUMS']) in m.calls, 'Albums: the stock album query')
    rows, other = front()
    expect(rows == ['Kind of Blue', 'Homogenic'] and 'Albums' in other, f'the albums as rows, the title Albums ({rows}, {other})')
    # an album's tracks
    centre()
    expect(('loadAlbumdetailList', O['CLASS_ALBUMS'], 'Kind of Blue') in m.calls, 'an album: loadAlbumdetailList(0xf003, the album\'s record), as the album page runs it')
    rows, other = front()
    expect(rows == ['Kind of Blue 0', 'Kind of Blue 1', 'Kind of Blue 2'], f'its tracks ({rows})')
    expect(m.word(G_CLASS) == 0xff10, 'g_class_type is the browsing record\'s class, as albuminfo_page_init leaves it')
    # play the second track
    step_to(1)
    centre()
    pl = m.played
    expect(pl is not None and pl[1] == 1 and [m.read_cstr(m.word(r + O['REC_TITLE'])) for r in pl[0]] == ['Kind of Blue 0', 'Kind of Blue 1', 'Kind of Blue 2'],
           f'a track: loadSongList of the shown list, start_player at its row ({pl and pl[1]})')
    sp = [c for c in m.calls if c[0] == 'start_player']
    expect(sp == [('start_player', 1, 0xff10, O['PLAY_MODE'])] and ('loadSongList', 'Kind of Blue-1.flac', 0, 0xff10) in m.calls,
           f'with the album\'s class and the play mode the stock Play all passes ({sp})')
    expect(m.read_cstr(FORCE) == '' or m.u.mem_read(FORCE, 1)[0] == 1, 'force_refreshflag is set, as the stock Play all handler does')
    expect('navigator_to_with_context' not in m.names(), 'no stock Now Playing page opens: the iPod page shows it')
    # Now Playing
    m.status = 2; m.pt = (107, 305)
    t = m.song('Freddie Freeloader', artist='Miles Davis', album='Kind of Blue', rid=1)
    m.play([m.album_tracks['Kind of Blue'][0], t, m.album_tracks['Kind of Blue'][2]], 1)
    m.call(PSYMS['ip_tick'], a0=0, count=40000000)
    texts, fills, blits = m.paint()
    tx = [t_ for t_, _ in texts]
    expect(['Freddie Freeloader', 'Miles Davis', 'Kind of Blue', '2 / 3', '1:47', '-3:18', 'Now Playing'] == [x for x in tx if x in ('Freddie Freeloader', 'Miles Davis', 'Kind of Blue', '2 / 3', '1:47', '-3:18', 'Now Playing')],
           f'Now Playing: title, artist, album, "2 / 3", elapsed and remaining, the title bar ({tx})')
    bar = [f for f in fills if f[2] >= O['IP_NP_BAR_Y'] and f[2] < O['IP_NP_BAR_Y'] + O['IP_NP_BAR_H'] and f[4] == 1]
    expect(bar and bar[0][3] == (320 - 24) * 107 // 305, f'the progress bar fills 107 of 305 s of its 296 px ({bar[:1]})')
    expect(blits and blits[-1][2][:2] == (O['IP_NP_ART_X'], O['IP_NP_ART_Y']) and blits[-1][2][2:] == (112, 112), 'the cover at (12, 36), 112 px')
    # MENU: back to the tracks (the album queried again), again to the albums, again to the main menu
    x, y = m.polar(0, 85); m.tap(x, y)
    expect(('loadAlbumdetailList', O['CLASS_ALBUMS'], 'Kind of Blue') in m.calls, 'MENU from Now Playing: the tracks, read again from the stock queries')
    rows, other = front()
    expect(rows[:2] == ['Kind of Blue 0', 'Kind of Blue 1'] and m.paint()[1].__class__ is list, 'the cursor is where it was')
    m.tap(*m.polar(0, 85))
    expect(front()[0][:2] == ['Kind of Blue', 'Homogenic'] and 'Albums' in front()[1], 'MENU: the albums again')
    m.tap(*m.polar(0, 85))
    expect(front()[0] == [m.tr(k) for k in MAIN_KEYS], 'MENU: the main menu')
    m.calls = []
    m.tap(*m.polar(0, 85))
    expect(m.names().count('navigator_back') == 1, 'MENU on the main menu closes the page (navigator_back, the status bar comes back with the stock window)')
    # Artists: artists -> albums (loadAlbumList(0xf004, the row)) -> tracks (class 0xff01)
    m = machine(albums=[('Kind of Blue', 'Miles Davis')], artists=['Miles Davis', 'Bjork']); m.open(); m.timers = []
    m.artist_albums = {'Miles Davis': [m.record(album='Kind of Blue', artist='Miles Davis', path='/mnt/mmc/m/Kind of Blue.flac', rid=900)]}
    m.turn(0, STEP_DEG * 2 + 5); m.tap(CX, CY); calls = list(m.calls)
    rows = rows_of(m.paint()[0])
    expect(('loadLocalClassList', O['CLASS_ARTISTS']) in calls and rows == ['Miles Davis', 'Bjork'], f'Artists: the stock artist query ({rows})')
    artist_rec = m.deques[m.word(SHOWLIST)][0]
    m.tap(CX, CY); calls = list(m.calls)
    rows = rows_of(m.paint()[0])
    expect(('loadAlbumList', O['CLASS_ARTISTS'], artist_rec, 'Miles Davis') in calls and rows == ['Kind of Blue', 'All albums'],
           f'an artist: loadAlbumList(0xf004, the artist\'s record); its albums, then the stock "All songs" row as "All albums" ({rows})')
    m.tap(CX, CY)
    expect(('loadAlbumdetailList', O['CLASS_ARTIST_ALBUMS'], 'Kind of Blue') in m.calls and m.word(G_CLASS) == 0xff11, 'an artist\'s album: loadAlbumdetailList(0xff01, ...) -> 0xff11')
    m.tap(*m.polar(0, 85)); m.tap(*m.polar(0, 85))
    expect(rows_of(m.paint()[0]) == ['Miles Davis', 'Bjork'], 'two MENUs: the artists list again (the chain of queries ran again)')
    # Songs
    m = machine(songs=['So What', 'Freddie']); m.open(); m.timers = []
    m.turn(0, STEP_DEG * 3 + 5); m.tap(CX, CY)
    m.turn(0, 23); m.tap(CX, CY)
    expect(m.played and m.played[1] == 1 and ('start_player', 1, O['CLASS_ALL_SONGS'], O['PLAY_MODE']) in m.calls, f'Songs: a track plays with the library class ({m.calls[-4:]})')
    # Playlists: the id in classinfo[1], class 0xff13
    m = machine(playlists=['Road', 'Gym']); m.open(); m.timers = []
    m.playlist_songs = {7: [m.song('R1', rid=601, path='/mnt/mmc/m/1.flac'), m.song('R2', rid=602, path='/mnt/mmc/m/1.flac', name='2.flac')], 8: [m.song('G1', rid=603)]}
    m.turn(0, STEP_DEG * 4 + 5); m.tap(CX, CY); calls = list(m.calls)
    rows = rows_of(m.paint()[0])
    expect(('loadLocalClassList', O['CLASS_PLAYLISTS']) in calls and rows == ['Road', 'Gym'], f'Playlists: the playlist headers ({rows})')
    m.turn(0, 23); m.tap(CX, CY)
    rows = rows_of(m.paint()[0])
    expect(m.word(CLASSINFO + 4) == 8 and rows == ['G1'], f'a playlist: its id in classinfo[1], its songs ({rows}, {m.word(CLASSINFO + 4)})')
    m.setword(CLASSINFO + 4, 99)   # another page left something else there
    m.tap(CX, CY)
    expect(m.word(CLASSINFO + 4) == 8 and ('start_player', 0, O['CLASS_PLAYLIST_SONGS'], O['PLAY_MODE']) in m.calls, 'a playlist track: the id is put back before the play, class 0xff13')
    # Cover Flow, Shuffle Songs and Settings stay on the page: test/pod/ipod_cf.py, shuffle_tests, settings_tests
    m = machine(); m.open(); m.timers = []
    m.turn(0, STEP_DEG * 7 + 5); m.tap(CX, CY)
    expect(texts_of(m.paint())[0] == 'Not Playing' or 'Not Playing' in texts_of(m.paint()), 'Now Playing with nothing queued: "Not Playing"')
    m.tap(CX, CY)
    expect(m.cmds == [('playpause',)], 'the centre button on Now Playing plays / pauses')


def stale_tests(ctx):
    expect = ctx.expect
    m = machine(albums=[('Kind of Blue', 'Miles Davis')], songs=['So What']); m.open(); m.timers = []
    m.turn(0, STEP_DEG + 5); m.tap(CX, CY)
    rows = rows_of(m.paint()[0])
    assert rows == ['Kind of Blue']
    m.setword(SHOWLIST, m.new_deque(m.class_lists[O['CLASS_ALL_SONGS']]))   # another page queried: the stock list is not ours any more
    m.calls = []
    texts = [t for t, r in m.paint()[0]]
    expect('Kind of Blue' not in texts and 'So What' not in texts and 'loadLocalClassList' not in m.names(), 'a stale list is never read in paint (nothing drawn, no query from paint)')
    m.top_main = 0
    m.call(PSYMS['ip_tick'], a0=0, count=40000000)
    expect('loadLocalClassList' not in m.names(), 'the timer does not query while another window is in front')
    m.top_main = WIN
    m.call(PSYMS['ip_tick'], a0=0, count=40000000)
    expect(('loadLocalClassList', O['CLASS_ALBUMS']) in m.calls, 'in front again, the tick reads the albums again')
    expect(rows_of(m.paint()[0]) == ['Kind of Blue'], 'and the rows are back')
    m.setword(SHOWLIST, m.new_deque(m.class_lists[O['CLASS_ALL_SONGS']]))
    m.calls = []; m.fire(EVT_FG, WIN)
    expect(('loadLocalClassList', O['CLASS_ALBUMS']) in m.calls, 'the window coming back to the front reads its list again')
    m.setword(SHOWLIST, m.new_deque(m.class_lists[O['CLASS_ALL_SONGS']]))
    m.calls = []; m.tap(CX, CY)
    expect(('loadLocalClassList', O['CLASS_ALBUMS']) in m.calls and ('loadAlbumdetailList', O['CLASS_ALBUMS'], 'Kind of Blue') in m.calls, 'a tap on a stale list reads it first, then opens the right album')
    # an empty list: the message
    m = machine(); m.open(); m.timers = []
    m.turn(0, STEP_DEG + 5); m.tap(CX, CY)
    expect(m.tr('No songs') in [t for t, _ in m.paint()[0]], 'an empty list says so')
    m.tap(CX, CY)
    expect(not m.cmds and 'start_player' not in m.names() and 'loadAlbumdetailList' not in m.names(), 'and a tap on it does nothing')
    # a track that is not on the card
    m = machine(albums=[('Kind of Blue', 'Miles Davis')]); m.open(); m.timers = []
    m.present.discard('/mnt/mmc/m/Kind of Blue-0.flac')
    m.turn(0, STEP_DEG + 5); m.tap(CX, CY); m.tap(CX, CY); m.calls = []; m.tap(CX, CY)
    expect('start_player' not in m.names() and any(c[0] == 'toast' for c in m.calls), 'a track whose file is gone: the stock message box, nothing started')


def i18n_tests(ctx):
    expect = ctx.expect
    src = open(os.path.join(ROOT, 'patch', 'ipod.c')).read()
    keys = set(re.findall(r'TR\("([^"]+)"\)', src)) | set(MAIN_KEYS) | set(SET_KEYS)
    missing = [k for k in keys if k not in pod_i18n.TEXT and k not in pod_i18n.STOCK]
    expect(not missing, f'every text of the page is a key of ours or a stock key ({missing})')
    font = Ttf(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/fonts/default.ttf'))
    over = []
    for loc in pod_i18n.LOCALES:
        t = pod_i18n.table_for(loc)
        w17 = lambda s: StbText(font, 17).layout(s)[1]
        for k in MAIN_KEYS:
            s = pod_i18n.tr(loc, k) if hasattr(pod_i18n, 'tr') else pod_i18n.TEXT[k][t]
            if w17(s) > O['IP_SPLIT_X'] - 10 - 22: over.append((loc, k, w17(s)))
        for k in ('Albums', 'Artists', 'Songs', 'Playlists', 'Now Playing'):
            s = pod_i18n.tr(loc, k)
            if StbText(font, 16).layout(s)[1] > 320 - 140: over.append((loc, 'title ' + k))
        if StbText(font, 16).layout(pod_i18n.tr(loc, 'Not Playing'))[1] > 300: over.append((loc, 'Not Playing'))
        for k, v in (('Shuffle', ('Off', 'Songs')), ('Repeat', ('Off', 'One', 'All')), ('About', (pod.TAG,))):   # a Settings row: the label, 12 px, the widest value (17 px) in 310 - 10
            vw = max(w17(pod_i18n.tr(loc, x) if x != pod.TAG else x) for x in v)
            if w17(pod_i18n.tr(loc, k)) + 12 + vw > 300 or vw > 120: over.append((loc, 'row ' + k, w17(pod_i18n.tr(loc, k)), vw))
        if w17(pod_i18n.tr(loc, 'Customize')) > 320 - 10 - 22: over.append((loc, 'Customize'))
    expect(not over, f'the main menu rows (17 px in the split screen\'s 140 px), the titles and the Settings rows fit in all 13 languages ({over})')
    expect(pod_i18n.TEXT['Not Playing']['en_US'] == 'Not Playing' and all(pod_i18n.TEXT['Not Playing'][l] for l in pod_i18n.LOCALES), '"Not Playing" is translated into all 13 languages')


class Drag:
    """One touch on the ring, move by move, with its own event times: Drag(m, deg).go(ddeg, dt) turns by ddeg degrees dt ms after the last event."""
    def __init__(self, m, deg, r=100, t=1000):
        self.m, self.deg, self.r, self.t = m, deg, r, t
        m.ptr('down', *m.polar(deg, r), t)

    def go(self, ddeg, dt):
        self.deg += ddeg; self.t += dt
        self.m.ptr('move', *self.m.polar(self.deg, self.r), self.t)

    def up(self): self.m.ptr('up', *self.m.polar(self.deg, self.r), self.t + 16)


def feel_tests(ctx):
    """Reversal hysteresis, the chord dead zone, the 15 degree step with carry, the tiers on long lists, the hard stop at the ends (docs/modules/ipod.md "The wheel")."""
    expect = ctx.expect

    def menu():
        m = machine(); m.open(); m.timers = []
        return m

    def menu_row(m):
        m.clock += 1000
        ys = [f[2] for f in m.paint()[1] if f[4] == 1 and f[3] == O['IP_SPLIT_X'] and f[2] < 240]
        return (min(ys) - BARH) // ROWH if ys else None

    def songs(n):
        m = machine(songs=[f'Song {i:03d}' for i in range(n)]); m.open(); m.timers = []
        m.turn(0, STEP_DEG * 3 + 5); m.tap(CX, CY)
        return m

    def song_sel(m):
        m.clock += 1000
        texts, fills, _ = m.paint()
        ys = [f[2] for f in fills if f[4] == 1 and f[3] == 320 and f[2] >= BARH]
        return int(rows_of(texts)[0][5:]) + (min(ys) - BARH) // ROWH

    # the step: 15 degrees, the leftover carries
    m = menu()
    d = Drag(m, 0)
    for _ in range(14): d.go(1, 100)
    d.up()
    expect(menu_row(m) == 0, 'a 14 degree turn is no step')
    m = menu(); d = Drag(m, 0)
    for _ in range(16): d.go(1, 100)
    d.up()
    expect(menu_row(m) == 1, 'a 16 degree turn is one step')
    m = menu(); d = Drag(m, 0)
    d.go(20, 100); r1 = menu_row(m); d.go(10, 100); d.up()
    expect(r1 == 1 and menu_row(m) == 2, f'20 degrees then 10: the leftover 5 carries into the second step ({r1}, {menu_row(m)})')

    # reversal hysteresis: 8 degrees of reverse travel are swallowed, then the accumulator starts again at 0
    m = menu(); d = Drag(m, 0)
    for _ in range(8): d.go(2, 100)
    expect(menu_row(m) == 1, 'forward 16 degrees: row 1')
    for _ in range(11): d.go(-2, 100)
    expect(menu_row(m) == 1, '22 degrees back: 8 swallowed, 14 counted: still row 1')
    for _ in range(2): d.go(-2, 100)
    expect(menu_row(m) == 0, '26 degrees back: 8 swallowed, 18 counted: one step up')
    m = menu(); d = Drag(m, 0)
    for _ in range(8): d.go(2, 100)
    for _ in range(5):
        for _ in range(3): d.go(-2, 100)
        for _ in range(3): d.go(2, 100)
    expect(menu_row(m) == 1, 'a 6 degree jitter at the turnaround, five times over, steps nothing')
    for _ in range(6): d.go(2, 100)
    expect(menu_row(m) == 1, 'and the jitter took no forward travel either: 12 more degrees is still row 1 (1 + 12 < 15)')
    for _ in range(2): d.go(2, 100)
    expect(menu_row(m) == 2, 'and 16 more is the next step')

    # the chord dead zone
    def chord(y, x0=-60, x1=60):
        m = menu(); m.ptr('down', CX + x0, CY + y, 1000); m.ptr('move', CX + x1, CY + y, 1100)
        row = menu_row(m)
        return m, row
    m, row = chord(-10)
    expect(row == 0, 'a move whose chord passes 10 px from the centre turns nothing')
    m, row = chord(-5)
    expect(row == 0, 'nor one that passes 5 px from it')
    m, row = chord(-12)
    expect(row == 7, f'a chord 12 px from the centre is a turn (154 degrees, clamped at the last row) ({row})')
    m = menu(); m.ptr('down', CX - 60, CY - 10, 1000); m.ptr('move', CX + 60, CY - 10, 1100)
    x, y = 60, -10
    a = math.degrees(math.atan2(x, -y)); r = math.hypot(x, y)
    for i in range(1, 5):
        px, py = r * math.sin(math.radians(a + 5 * i)), -r * math.cos(math.radians(a + 5 * i))
        m.ptr('move', CX + round(px), CY + round(py), 1100 + 100 * i)
    expect(menu_row(m) == 1, 'after the rejected chord the same touch goes on from the new point: 20 degrees, one step')
    m = menu(); m.ptr('down', CX - 30, CY, 1000); m.ptr('move', CX + 30, CY + 4, 1100)
    expect(menu_row(m) == 0, 'a drag that begins on the centre button still does nothing')

    # tiers
    expect([m.call(PSYMS['ip_tier_rows'], a0=n, a1=i) for n, i in ((8, 0), (8, 5), (16, 5), (16, 99), (17, 0), (17, 1), (17, 2), (17, 3), (17, 4), (17, 5), (17, 6), (17, 7), (17, 9), (3000, 20))]
          == [1, 1, 1, 1, 1, 2, 3, 5, 8, 13, 21, 34, 34, 34], 'rows a step: 1 for 16 rows or fewer, else the tiers 1, 2, 3, 5, 8, 13, 21, 34 (the last holds)')
    m = songs(3000); d = Drag(m, 0)
    for _ in range(30): d.go(6, 16)
    expect(song_sel(m) == 12, f'a fast turn (375 deg/s): the first half second is one row per 15 degrees (row {song_sel(m)} = 12)')
    sels, prev, deltas = [], 12, []
    for _ in range(300):
        d.go(6, 16); s = song_sel(m); deltas.append(s - prev); prev = s
        if s >= 2999: break
    expect(set(deltas) - {0} == {1, 2, 3, 5, 8, 13, 21, 34}, f'held fast, the rows a step climb through 1, 2, 3, 5, 8, 13, 21 to 34 ({sorted(set(deltas))})')
    first2 = next(i for i, x in enumerate(deltas) if x >= 2)
    expect(560 <= (30 + first2) * 16 <= 700, f'the first 2-row step comes about half a second after the speed passed 180 deg/s (at {(30 + first2) * 16} ms)')
    # the instantaneous speed is clamped at 400 deg/s (IP_VMAX) before the 0.15 smoothing: 1500 deg/s reaches 180 deg/s smoothed on the 5th move (40 ms), not the 1st
    m = songs(3000); d = Drag(m, 0); prev = 0; at = None
    for i in range(200):
        d.go(12, 8); s = song_sel(m)
        if s - prev >= 2: at = (i + 1) * 8; break
        prev = s
    expect(at is not None and 530 <= at <= 560, f'1500 deg/s: the clamp and the 0.15 smoothing delay the speed passing 180 deg/s to the 5th move: first 2-row step at {at} ms (540 expected, 500 unclamped)')
    # back to 1 when the speed drops
    m = songs(100); d = Drag(m, 0)
    for _ in range(60): d.go(6, 16)
    prev = song_sel(m); late = []
    for i in range(30):
        d.go(3, 100); s = song_sel(m); late.append(s - prev); prev = s
    expect(max(late[12:]) <= 1 and max(late) >= 1, f'the speed falls below the threshold: back to one row a step within a dozen moves ({late})')
    # a pause resets it
    m = songs(100); d = Drag(m, 0)
    for _ in range(60): d.go(6, 16)
    prev = song_sel(m); d.go(6, 300); prev = song_sel(m); after = []
    for _ in range(25):
        d.go(6, 16); s = song_sel(m); after.append(s - prev); prev = s
    expect(max(after) == 1, f'a pause over 250 ms resets the tier: one row a step again ({sorted(set(after))})')
    # a direction change resets it
    m = songs(100); d = Drag(m, 0)
    for _ in range(60): d.go(6, 16)
    prev = song_sel(m); after = []
    for _ in range(25):
        d.go(-6, 16); s = song_sel(m); after.append(s - prev); prev = s
    expect(min(after) >= -1 and min(after) == -1 and sum(after) < -5, f'turning back: the tier is gone, one row a step the other way ({sorted(set(after))})')
    # clamped at the end
    m = songs(40); d = Drag(m, 0)
    for _ in range(150): d.go(6, 16)
    expect(song_sel(m) == 39, f'the last row stops it ({song_sel(m)})')
    # a short list (the main menu) moves one row a step at any speed
    m = menu(); d = Drag(m, 0); prev = 0; deltas = []
    for _ in range(40):
        d.go(6, 16); s = menu_row(m); deltas.append(s - prev); prev = s
    expect(max(deltas) == 1 and prev == 7, 'the short main menu list: one row a step at 375 deg/s')

    # the ends of a list: a hard stop, as the iPod (no wrap, no bump, the page timer untouched)
    m = menu(); calls = []
    d = Drag(m, 0)
    for _ in range(4): d.go(-6, 100); calls += m.calls
    names = [c_[0] for c_ in calls]
    ys = lambda: min(f[2] for f in m.paint()[1] if f[4] == 1 and f[3] == O['IP_SPLIT_X'] and f[2] < 240)
    expect(menu_row(m) == 0 and ys() == BARH, f'turning back past the start: the first row stays selected, the rows stay home ({ys()})')
    expect('timer_remove' not in names and 'timer_add' not in names, 'a stop at the start touches no timer')
    m = menu(); d = Drag(m, 0)
    for _ in range(60): d.go(6, 100)
    expect(menu_row(m) == 7, 'the last row')
    m.calls = []; d = Drag(m, 0); d.go(20, 100); d.go(20, 100)
    ys2 = [f[2] for f in m.paint()[1] if f[4] == 1 and f[3] == O['IP_SPLIT_X'] and f[2] < 240]
    expect(menu_row(m) == 7 and min(ys2) == BARH + 7 * ROWH, f'turning on past the end: the last row stays selected, the rows stay home ({min(ys2)})')
    expect('timer_remove' not in m.names() and 'timer_add' not in m.names(), 'a stop at the end touches no timer')


def with_covers(n_albums=10, n_art=8):
    """A machine with n_albums albums, the first n_art of them with a Cover Flow cache file holding a solid picture of their own; the ticks and paints of the pane."""
    m = machine(albums=[(f'Album {i}', f'Artist {i}') for i in range(n_albums)])
    m.urls = {}
    for i in range(n_art):
        key = album_key(f'Artist {i}', f'Album {i}'); path = art_file(key)
        m.present.add(path); m.files[path] = 4096
        m.images['file://' + path] = (168, 168, bytes((10 + 25 * i, 200 - 20 * i, 90, 255)) * (168 * 168))
        m.urls['file://' + path] = i
    m.open(); m.timers = []
    return m


def tick(m, ms=None):
    """One run of the page timer's callback (time_now_ms advanced by ms first, by default the interval it runs at): its calls, each image load as
    ('widget_load_image', url, the bitmap it was decoded into)."""
    m.clock += O['IP_DRIFT_MS'] if ms is None else ms
    n = len(m.load_into)
    m.call(PSYMS['ip_tick'], a0=0, count=60000000)
    into = iter(m.load_into[n:])
    return [x + (next(into)[1],) if x[0] == 'widget_load_image' else x for x in m.calls]


def pane_frame(m):
    """One paint: the pane's blits (bitmap, src window, dst) and the loads paint made."""
    loads = len(m.loads)
    m.paint()
    return [b for b in m.blits if b[2][:2] == (PANE[0], PANE[1])], len(m.loads) - loads


def pane_loads(c, m):
    """The albums (with_covers index) whose cache file a tick decoded for the pane (not the Now Playing cover), the stock disc as 'disc'."""
    pane = [b for b, (_, w, h) in m.bitmaps.items() if w == h == O['IP_PANE_ART']]
    return [m.urls.get(x[1], 'disc' if x[1] == 'p_default' else x[1]) for x in c if x[0] == 'widget_load_image' and x[2] in pane]


def pane_tests(ctx):
    """The main menu's cover pane, as q2-pod's Split Home pan (docs/modules/ipod.md "The cover pane")."""
    expect = ctx.expect
    FAST, SLOW, ART, R = O['IP_DRIFT_MS'], O['IP_TICK_MS'], O['IP_PANE_ART'], O['IP_PANE_R']
    X0 = (ART - PANE[2] - R) // 2
    expect(ART == -(-PANE[3] * 110 // 100) and R == ART - PANE[3] and FAST == 100 and (O['IP_DRIFT_X_MS'], O['IP_DRIFT_Y_MS'], O['IP_DRIFT_MAX_MS']) == (20000, 26000, 250)
           and PANE[0] == O['IP_SPLIT_X'] + 1 and PANE[0] + PANE[2] == 320, 'q2-pod\'s pan: zoom 110%, sweeps of 20 s and 26 s, 100 ms ticks, a step at most 250 ms')
    m = with_covers()
    m.call(PSYMS['ip_first'], a0=0, count=40000000)
    expect(('timer_add', PSYMS['ip_tick'], FAST) in m.calls and len(m.timers) == 1, f'on the main menu, in front: the one page timer ticks at {FAST} ms')
    expect(not pane_frame(m)[0], 'the pane is plain until a cover is decoded')
    # nothing plays: a random album's cached cover, decoded once at the zoomed size
    c = tick(m)
    first = pane_loads(c, m)
    expect(('loadLocalClassList', O['CLASS_ALBUMS']) in c and len(first) == 1 and first[0] in range(8), f'tick 1: a random album with a cached cover is decoded ({first})')
    expect(('bitmap_create_ex', ART, ART) in [x[:3] for x in c], f'into a {ART} px bitmap (the pane\'s height zoomed 110%)')
    frames, decodes, paint_loads, inval = [], 0, 0, []
    for t in range(400):   # 40 s
        c = tick(m)
        decodes += len(pane_loads(c, m))
        inval.append(any(x[0] == 'widget_invalidate_force' for x in c))
        b, pl = pane_frame(m)
        paint_loads += pl; frames.append(b)
    expect(decodes == 0 and paint_loads == 0, f'then nothing is decoded again, by the tick ({decodes}) or by paint ({paint_loads})')
    expect(all(len(f) == 1 and f[0][2] == PANE and f[0][1][2:] == PANE[2:] for f in frames), 'every frame: one draw, source and destination both 139 x 216 (a copy, nothing scaled)')
    wins = [f[0][1][:2] for f in frames]
    xs, ys = [w[0] for w in wins], [w[1] for w in wins]
    expect(min(xs) == X0 and max(xs) == X0 + R and min(ys) == 0 and max(ys) == R, f'the window sweeps the zoom\'s margin on both axes, inside the bitmap ({min(xs)}..{max(xs)}, {min(ys)}..{max(ys)})')
    moves = [(b[0] - a[0], b[1] - a[1]) for a, b in zip(wins, wins[1:])]
    expect(all(abs(dx) <= 1 and abs(dy) <= 1 for dx, dy in moves), 'a whole pixel a step at most')
    still = [i for i, mv in enumerate(moves) if mv == (0, 0)]
    expect(len(still) > 200 and not any(inval[i + 1] for i in still), f'a tick that moves no pixel repaints nothing ({len(still)} of {len(moves)})')
    xt = [i for i in range(1, len(xs)) if xs[i] != xs[i - 1]]
    expect(xs[0] < xs[199] and xs[200] > xs[-1] and 15 <= len(xt) <= 50, f'x: across in 20 s and back (a pixel about every second: {len(xt)} steps in 40 s)')
    # a stall: the step is capped, so the cover does not jump
    w0 = pane_frame(m)[0][0][1][:2]
    tick(m, 10000)
    w1 = pane_frame(m)[0][0][1][:2]
    expect(abs(w1[0] - w0[0]) <= 1 and abs(w1[1] - w0[1]) <= 1, f'a tick 10 s late moves at most one step ({w0} -> {w1})')
    # a track plays from a cached album: its cover, the pan's phase carried over
    m.play([m.song('T', artist='Artist 3', album='Album 3')], 0)
    c = tick(m)
    expect(pane_loads(c, m).count(3) >= 1, f'a track of Album 3 plays: its cover ({pane_loads(c, m)})')
    w2 = pane_frame(m)[0][0][1][:2]
    expect(abs(w2[0] - w1[0]) <= 1 and abs(w2[1] - w1[1]) <= 1, 'the new cover starts where the pan was')
    c = [x for _ in range(5) for x in tick(m)]
    expect(3 not in pane_loads(c, m), 'and is decoded once, not again each tick')
    m.play([m.song('U', artist='Artist 5', album='Album 5')], 0)
    expect(5 in pane_loads(tick(m) + tick(m), m), 'the next track from another album: that album\'s cover')
    m.play([m.song('V', artist='Nobody', album='Uncached')], 0)
    got = pane_loads(tick(m) + tick(m), m)
    expect(got and got[-1] in range(8), f'a track whose album has no cached cover: a random cached one again ({got})')
    # the interval: slow elsewhere, fast again on the main menu
    m = with_covers()
    m.call(PSYMS['ip_first'], a0=0, count=40000000)
    tick(m); tick(m)
    m.turn(0, STEP_DEG + 5)
    m.tap(CX, CY)
    expect(('timer_modify', 0x777, SLOW) in m.calls, f'a list opens: the timer goes to {SLOW} ms')
    c = tick(m)
    expect(not [x for x in c if x[0] in ('widget_load_image', 'timer_modify')], 'on a list the tick decodes no cover and the interval stays')
    m.tap(*m.polar(0, 85))
    expect(('timer_modify', 0x777, FAST) in m.calls, f'MENU back to the main menu: {FAST} ms again')
    expect(('loadLocalClassList', O['CLASS_ALBUMS']) in tick(m), 'and a new random cover is chosen (the album query runs again)')
    m.top_main = 0
    c = tick(m)
    expect(('timer_modify', 0x777, SLOW) in c and not [x for x in c if x[0] in ('widget_load_image', 'loadLocalClassList')], 'another window in front: slow, and nothing is decoded or queried')
    m.top_main = WIN
    c = tick(m)
    expect(('timer_modify', 0x777, FAST) in c, 'in front again: fast')
    m.calls = []; m.fire(EVT_BG, WIN)
    expect(('timer_remove', 0x777) in m.calls, 'to the background: the timer goes (nothing runs behind another page)')
    m.calls = []; m.fire(EVT_FG, WIN)
    expect(('timer_add', PSYMS['ip_first'], O['IP_FIRST_MS']) in m.calls, 'and comes back with the page')
    c = fired(m, 'ip_first')
    expect(('timer_add', PSYMS['ip_tick'], FAST) in c, 'at the fast interval')
    # random: another seed, another cover
    got = []
    for seed in (3, 5, 7):
        m = with_covers(); m.seed = seed
        m.call(PSYMS['ip_first'], a0=0, count=40000000)
        got.append(pane_loads(tick(m), m))
    expect(len(set(map(tuple, got))) > 1, f'another seed, another cover ({got})')
    # no cached covers: the stock disc, still, at the slow tick; no albums: the disc too
    for n_albums, what in ((10, 'albums without cached art'), (0, 'no albums')):
        m = with_covers(n_albums, 0)
        m.call(PSYMS['ip_first'], a0=0, count=40000000)
        c0 = c = tick(m)
        b, _ = pane_frame(m)
        expect(pane_loads(c, m) == ['disc'] and len(b) == 1 and b[0][1][:2] == (X0 + R // 2, R // 2), f'{what}: the stock disc, in the middle ({pane_loads(c, m)})')
        c = tick(m) + tick(m, 5000)
        expect(('timer_modify', 0x777, SLOW) in c0 and pane_frame(m)[0][0][1] == b[0][1] and not pane_loads(c, m), 'and it stands still, at the slow tick, decoded once')
    # a cover that cannot be decoded falls back to the disc (and is not tried again each tick)
    m = with_covers(3, 3)
    for u in list(m.images):
        if u.startswith('file://'): del m.images[u]
    m.call(PSYMS['ip_first'], a0=0, count=40000000)
    c = tick(m) + tick(m) + tick(m)
    expect(len(pane_frame(m)[0]) == 1 and pane_loads(c, m).count('disc') == 1, f'a cache file that does not decode: the stock disc, once ({pane_loads(c, m)})')
    # destroy frees the bitmaps
    m = with_covers()
    m.call(PSYMS['ip_first'], a0=0, count=40000000)
    for _ in range(4): tick(m)
    m.calls = []; m.fire(EVT_DESTROY, WIN)
    expect(m.names().count('bitmap_destroy') >= 2, f'destroy frees the page\'s bitmaps (the Now Playing cover and the pane\'s): {m.names().count("bitmap_destroy")}')

def shuffle_tests(ctx):
    expect = ctx.expect
    songs = [f'Song {i:02d}' for i in range(10)]
    def library(seed):
        m = machine(songs=songs); m.seed = seed; m.clock = 7 * seed
        for i in range(10): m.present.add(f'/mnt/mmc/m/{i}.flac')
        m.open(); m.timers = []
        m.turn(0, STEP_DEG * 5 + 5); m.tap(CX, CY)
        return m
    firsts = []
    for seed in (11, 12, 13, 14):
        m = library(seed)
        sp = [c for c in m.calls if c[0] == 'start_player']
        expect(m.opened == [] and ('loadLocalClassList', O['CLASS_ALL_SONGS']) in m.calls and len(sp) == 1 and sp[0][2:] == (O['CLASS_ALL_SONGS'], O['PLAY_MODE']),
               f'Shuffle Songs: the library query and the stock start_player with the library class ({sp})')
        pl = m.played
        firsts.append(sp[0][1])
        expect(pl and len(pl[0]) == 10 and pl[1] == sp[0][1] and 0 <= pl[1] < 10, f'the whole library is the queue, the first song a random one ({pl and pl[1]})')
        expect(('mclSetPlayMode', 2) in m.calls and m.mode == 2 and ('write_int_config', 2, 'PLAYSET', 'PLAYMODE') in m.calls, 'stock Shuffle (mode 2) is set the way the Play settings page does')
        expect('navigator_to_with_context' not in m.names() and 'shuffle_play' not in m.names(), 'no stock page opens')
        texts = texts_of(m.paint())
        expect('Now Playing' in texts, 'the iPod\'s own Now Playing is in front')
        if seed == 11:
            x, y = m.polar(0, 85); m.tap(x, y)
            front = rows_of(m.paint()[0])
            expect(front == [m.tr(k) for k in MAIN_KEYS], f'MENU from Now Playing returns to the main menu ({front[:2]})')
    expect(len(set(firsts)) >= 2, f'the first song differs with the random seed ({firsts})')
    # an empty library: the message, nothing played, the mode untouched
    m = machine(); m.open(); m.timers = []; m.mode = 1
    m.turn(0, STEP_DEG * 5 + 5); m.tap(CX, CY)
    expect(any(c[0] == 'toast' for c in m.calls) and 'start_player' not in m.names() and m.mode == 1 and 'mclSetPlayMode' not in m.names(), 'no songs: the stock message box, nothing started, the mode kept')
    # the first file is gone: nothing started, the mode kept
    m = machine(songs=songs); m.open(); m.timers = []; m.mode = 3
    m.present.discard('/mnt/mmc/m/1.flac')
    m.turn(0, STEP_DEG * 5 + 5); m.tap(CX, CY)
    expect(m.mode == 3 and ('start_player' not in m.names() or m.played[0][m.played[1]] is not None), 'a missing file starts nothing and keeps the mode')


def settings_tests(ctx):
    expect = ctx.expect
    VALUE_X = 320 - O['IP_TEXT_X'] if 'IP_TEXT_X' in O else 310
    def values(m):
        texts, fills, _ = m.paint()
        return [t for t, r in sorted(texts, key=lambda tr: tr[1][1]) if r[0] + r[2] - 2 == VALUE_X and BARH <= r[1] < 240]
    def chevrons(m):
        return [f for f in m.paint()[1] if f[3] == 2 and f[4] == 1 and f[1] >= 300 and BARH <= f[2] < 240 and f[0] == 0xffffffff]
    m = machine(); m.open(); m.timers = []
    m.turn(0, STEP_DEG * 6 + 5); m.tap(CX, CY)
    texts, fills, _ = m.paint()
    expect(not m.opened and 'loadLocalClassList' not in m.names(), 'Settings is a level of the iPod page now: no stock page opens, no query runs')
    expect(rows_of(texts) == [m.tr(k) for k in SET_KEYS] and m.tr('cdrippersettings') in [t for t, _ in texts], f'the rows Shuffle, Repeat, About, Customize under the title Settings ({rows_of(texts)})')
    expect(values(m) == [m.tr('Off'), m.tr('Off'), pod.TAG], f'right aligned values: Off, Off and the version tag ({values(m)})')
    expect(not chevrons(m), 'the selected row has a value, not a chevron')
    # the value is drawn at the right edge, the label is cut before it
    rect = {t: r for t, r in texts}
    expect(rect[m.tr('Shuffle')][0] == O['IP_TEXT_X'] and rect[m.tr('Shuffle')][2] < 310 - 20, 'the label starts at the left margin and stops short of the value')
    # shuffle: Off -> Songs -> Off
    m.tap(CX, CY)
    expect(m.mode == 2 and ('mclSetPlayMode', 2) in m.calls and ('write_int_config', 2, 'PLAYSET', 'PLAYMODE') in m.calls and values(m)[:2] == [m.tr('Songs'), m.tr('Off')],
           f'centre press on Shuffle: stock Shuffle (mode 2); the value reads Songs ({values(m)})')
    m.tap(CX, CY)
    expect(m.mode == 0 and ('mclSetPlayMode', 0) in m.calls and values(m)[:2] == [m.tr('Off'), m.tr('Off')], 'again: back to List play, Off')
    # repeat: Off -> One -> All -> Off; turning it on turns Shuffle off
    m.turn(0, STEP_DEG + 5)
    seen = []
    for _ in range(4):
        m.tap(CX, CY); seen.append((m.mode, values(m)[1]))
    expect(seen == [(1, m.tr('One')), (3, m.tr('All')), (0, m.tr('Off')), (1, m.tr('One'))], f'Repeat cycles Off, One, All, Off ({seen})')
    m.mode = 2
    expect(values(m)[:2] == [m.tr('Songs'), m.tr('Off')], 'in Shuffle mode Repeat reads Off')
    m.tap(CX, CY)
    expect(m.mode == 1 and values(m)[:2] == [m.tr('Off'), m.tr('One')], 'Repeat on turns Shuffle off (one play mode)')
    m.mode = 0
    # about: a value, no chevron, no action
    m.turn(0, STEP_DEG + 5); m.calls = []
    m.tap(CX, CY)
    expect(not m.opened and 'mclSetPlayMode' not in m.names() and not chevrons(m), 'About: nothing happens and no chevron')
    # more settings: a chevron, the existing page
    m.turn(0, STEP_DEG + 5)
    expect(len(chevrons(m)) == 9, 'Customize has the chevron')
    m.tap(CX, CY)
    expect(m.opened == ['pod_open_settings'], 'and opens the existing Settings page')
    m.turn(0, STEP_DEG * 9)
    expect(len([t for t in rows_of(m.paint()[0])]) == 4, 'the list stops at its four rows')
    x, y = m.polar(0, 85); m.tap(x, y)
    expect(rows_of(m.paint()[0]) == [m.tr(k) for k in MAIN_KEYS] and not m.names().count('navigator_back'), 'MENU returns to the main menu')


SECTIONS = [angle_tests, asset_tests, menu_tests, open_tests, paint_tests, wheel_tests, feel_tests, tap_tests, nav_tests, stale_tests, pane_tests, shuffle_tests, settings_tests, i18n_tests]


def run(ctx):
    for f in SECTIONS: f(ctx)
