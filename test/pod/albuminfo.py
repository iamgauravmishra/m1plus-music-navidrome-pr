"""The album view: the stock albuminfo_page restyled by the hook on its header builder, Shuffle, the
year line, the cover size, hit tests; Cover Flow's first album and its last-album memory."""
import os, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import importlib.util
import pod_i18n
import mod_ipodrows, mod_icons
from awtk_text import Ttf, StbText


def _rows_module():
    """test/pod/rows.py (RowMachine: demo's own widget constructors mocked into a model in emulated memory),
    as test/patch.py loaded it, or loaded here when this module runs alone."""
    if 'podtest_rows' not in sys.modules:
        spec = importlib.util.spec_from_file_location('podtest_rows', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.py'))
        mod = importlib.util.module_from_spec(spec); sys.modules['podtest_rows'] = mod; spec.loader.exec_module(mod)
    return sys.modules['podtest_rows']


RowMachine = _rows_module().RowMachine

HEADER_BUILDER = pod.ALBUMINFO_HEADER             # albuminfo_listitem0_layout
KILL = '/mnt/mmc/m1plus-off'
HDR_ART = 0x4dd670                                # the cover thread's flag-1 size word
STOCK_HEADER = {'cover': (0, 0, 100, 100), 'title': (108, 7, 200, 24), 'artist': (108, 33, 200, 20),
                'button': (108, 62, 90, 28)}      # what the stock builder makes (@0x526264, 0x524990, 0x524a64), the title boxes as rows.json sets them


class AlbumMachine(RowMachine):
    """RowMachine (demo's real widget constructors mocked into a model in emulated memory) plus what
    the album view's code calls: bound handlers, failing creates, destroys."""
    def __init__(self):
        super().__init__()
        self.bound = {}           # widget -> {event: (handler, ctx)}
        self.create_fail = set()  # widget kinds whose create returns NULL
        self.destroyed = []
        self.handlers[pod.FUNCTIONS['widget_destroy'][2]] = 'row:widget_destroy'
        self.styled = []          # widget_set_style calls (widget, "state:name", uint32)
        self.measure = None       # text -> width in px (the font's own: StbText); None: widget_measure_text fails (returns 0)
        self.measured = []
        self.bar, self.bar_fail, self.on_fail = 0, False, set()   # the status bar's handle (0: none), its style call refused, events whose widget_on is refused
        for n in ('widget_get_text', 'widget_measure_text', 'widget_set_style', 'value_set_uint32'):
            self.handlers[pod.FUNCTIONS[n][2]] = n

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address, '')
        a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        if name == 'widget_get_text':    # the widget's wide text: one 32 bit word a char, NUL terminated (0 for no text)
            t = self.texts.get(a0)
            ret = 0
            if t is not None:
                t = t.encode('latin-1').decode('utf-8')
                ret = self.alloc(4 * len(t) + 4); self.u.mem_write(ret, struct.pack(f'<{len(t) + 1}I', *map(ord, t), 0))
            u.reg_write(UC_MIPS_REG_V0, ret); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        if name == 'widget_measure_text':   # a float in $f0
            n = 0
            while self.word(a1 + 4 * n): n += 1
            t = ''.join(chr(c) for c in struct.unpack(f'<{n}I', self.u.mem_read(a1, 4 * n))) if n else ''
            w = float(self.measure(t)) if self.measure and t else 0.0
            self.measured.append((a0, t, w))
            u.reg_write(UC_MIPS_REG_F0, struct.unpack('<I', struct.pack('<f', w))[0]); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        if name == 'widget_set_style':
            if a0 == self.bar and self.bar_fail:   # the style call is refused: nothing recorded as set
                self.calls.append(('widget_set_style_failed', a0))
                u.reg_write(UC_MIPS_REG_V0, 0x10); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
                return
            self.styled.append((a0, self.read_cstr(a1), self.word(a2 + 8)))
            u.reg_write(UC_MIPS_REG_V0, 0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        if name == 'value_set_uint32':
            self.setword(a0, 7); self.setword(a0 + 8, a1)
            u.reg_write(UC_MIPS_REG_V0, a0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        if name == 'widget_get_prop_str' and self.read_cstr(a1) == 'image' and a0 in self.images_set:
            u.reg_write(UC_MIPS_REG_V0, self.cstr(self.images_set[a0])); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        if name == 'widget_off_by_func':   # emitter_off_by_func: removes the (event, handler, context) binding
            self.calls.append(('widget_off_by_func', a0, a1, a2, a3))
            if self.bound.get(a0, {}).get(a1) == (a2, a3): del self.bound[a0][a1]
            u.reg_write(UC_MIPS_REG_V0, 0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        if name == 'row:widget_on':
            refused = a1 in self.on_fail
            if not refused: self.bound.setdefault(a0, {})[a1] = (a2, a3)
            u.reg_write(UC_MIPS_REG_V0, 0 if refused else 1); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))   # the handler id: non-zero
            return
        elif name == 'row:widget_destroy':
            self.destroyed.append(a0)
            for kids in self.children.values():
                if a0 in kids: kids.remove(a0)
            u.reg_write(UC_MIPS_REG_V0, 0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        elif name in ('row:button_create', 'row:hscroll_label_create', 'row:image_create') and \
                name[len('row:'):-len('_create')] in self.create_fail:
            u.reg_write(UC_MIPS_REG_V0, 0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        return super()._hook(u, address, size, _)

    def header(self, tracks=6, year=1959, card=False, cls=None, window=True, album='Kind of Blue', artist='Miles Davis'):
        """A header item built by the patched stock builder (the hook runs, then restyles), with the
        stock list loaded as albuminfo_page_init leaves it: the album's tracks."""
        recs = [self.record(album='Kind of Blue', artist='Miles Davis', title=f'Track {i}', name=f'{i}.flac',
                            path=f'/mnt/mmc/m/{i}.flac', rid=100 + i) for i in range(tracks)]
        for r in recs:
            self.setword(r + O['REC_YEAR'], year)
            self.present.add(self.read_cstr(self.word(r + O['REC_PATH'])))
        self.tracks = recs
        self.setword(pod.DATA['PDEQ_SHOWLIST'][0], self.new_deque(recs))
        self.u.mem_write(pod.DATA['CLASSINFO'][0] + O['CLASSINFO_ALL_SONGS'], bytes([1 if card else 0]))
        self.setword(pod.DATA['G_CLASS_TYPE'][0], cls or O['CLASS_ALBUM_TRACKS'])
        ci = pod.DATA['CLASSINFO'][0]   # the names the stock loader leaves (loadAlbumdetailList): title +0xd, artist +0x10d (+0x20d for class 0xff14)
        self.u.mem_write(ci + O['CLASSINFO_ALBUM'], album.encode() + b'\0')
        self.u.mem_write(ci + (O['CLASSINFO_ARTIST_14'] if cls == O['CLASS_14'] else O['CLASSINFO_ARTIST']), artist.encode() + b'\0')
        parent = self.new_widget('scroll_view', 0, 0, 0, 310, 400)
        item = self.new_widget('list_item', parent, 0, 0, 0, 100)
        self.props[(item, 'w')] = 310
        self.sv = parent
        if window: self.page_window = self.new_widget('window', 0, 0, 0, 320, 450)
        self.call(HEADER_BUILDER, a0=item, count=2000000)
        art = self.kids(item)[0] if self.kids(item) else 0
        if art and self.wname.get(art) == 'img_albumcover_m': self.widgets['img_albumcover_m'] = art
        return item

    def with_bar(self):
        """The window manager with a navbar and a status bar among its children (the bar is found by its type)."""
        nav = self.alloc(0x80); self.bar = self.alloc(0x80)
        self.children[self.wm] = [nav, self.bar]; self.wtype[nav] = 'system_bar_bottom'; self.wtype[self.bar] = 'system_bar'
        return self

    def bar_styles(self): return [s[2] for s in self.styled if s[0] == self.bar]
    def fire(self, ev, win=None):
        fn, ctx = self.bound[win or self.page_window][ev]
        return self.call(fn, a0=ctx, a1=0, count=2000000)

    def real_cover(self, art, rgb, url='file:///tmp/abp/c1.jpg'):
        """The cover thread has rendered the file and the stock refresh timer has put it on the cover widget: a flat colour 160 px JPEG."""
        self.images_set[art] = url
        self.present.add(url[7:]); self.load_image = 0
        self.images[url] = (160, 160, bytes(rgb + (255,)) * 160 * 160)


class StackMachine(StockEventMachine):
    """Play all / Shuffle into Now Playing against a window stack. demo's own window_manager_get_top_window runs for real on
    a window manager struct laid out in emulated memory (children darray @0x58, a window's name @0x10 and flags @0x24, bit 4 =
    visible); navigator_back, window_close, navigator_window_is_exist and the navigator's open are the model: a window is
    removed at once, except one whose name is in anim (a close animation: it stays in the list, visible, until finish(), as
    window_close's pending close does, docs/modules/boot.md)."""
    MOCK = ('window_manager', 'navigator_window_is_exist', 'navigator_back', 'window_close', 'navigator_to_with_context')

    def __init__(self, stack, anim=(), songer=1, tracks=4, cls=0xff10):
        super().__init__()
        self.handlers.pop(pod.FUNCTIONS['window_manager_get_top_window'][2], None)   # stock's own
        self.wmw = self.alloc(0x100); self.u.mem_write(self.wmw, bytes(0x100))
        vt = self.alloc(0x40); self.u.mem_write(vt, bytes(0x40)); self.setword(self.wmw + 0x88, vt)   # the manager's own function table (no get_top_window slot: the default scan of the children runs)
        self.stack, self.anim, self.backs, self.closed, self.opened = [], set(anim), 0, [], []
        for name in stack: self.push(name)
        recs = [self.record(album='A', artist='B', title=f'T{i}', name=f'{i}.flac', path=f'/mnt/mmc/m/{i}.flac', rid=100 + i) for i in range(tracks)]
        for r in recs: self.present.add(self.read_cstr(self.word(r + O['REC_PATH'])))
        self.setword(pod.DATA['PDEQ_SHOWLIST'][0], self.new_deque(recs))
        self.setword(pod.DATA['G_CLASS_TYPE'][0], cls)
        self.u.mem_write(pod.DATA['SONGER_FLAG'][0], bytes([songer]))
        self.stock_songlist = True

    def push(self, name):
        w = self.alloc(0x40); self.u.mem_write(w, bytes(0x40))
        self.setword(w + O['WIDGET_NAME'], self.cstr(name)); self.u.mem_write(w + 0x24, struct.pack('<H', 0xd))
        self.stack.append((name, w)); self.sync()

    def sync(self):
        if self.stack: self.kids(self.wmw, [w for _, w in self.stack])
        else: self.setword(self.wmw + 0x58, 0)

    def names_(self): return [n for n, _ in self.stack]

    def top(self): return self.stack[-1] if self.stack else None

    def close(self, entry):
        self.closed.append(entry[0])
        if entry[0] not in self.anim: self.stack.remove(entry); self.sync()

    def finish(self):
        self.stack = [e for e in self.stack if e[0] not in self.anim or e[0] not in self.closed]; self.sync()

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address)
        if name not in self.MOCK: return super()._hook(u, address, size, _)
        a0 = u.reg_read(UC_MIPS_REG_A0)
        ret = 0
        if name == 'window_manager': ret = self.wmw
        elif name == 'navigator_window_is_exist': ret = int(self.read_cstr(a0) in self.names_())
        elif name == 'navigator_back':
            self.backs += 1
            if self.top(): self.close(self.top())
        elif name == 'window_close':
            ent = [e for e in self.stack if e[1] == a0]
            if ent: self.close(ent[0])
        else:   # the navigator opens a page: a new window on top; the harness records the queue and index
            page = self.read_cstr(a0)
            self.opened.append(page)
            super()._hook(u, address, size, _)
            self.push(page)
            return
        u.reg_write(UC_MIPS_REG_V0, ret); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))


def stack_tests(expect):
    """The stock "play from here" loop (row handler @0x52569c, loop @0x525904) against the window stack, with our pages."""
    play_all, shuffle = PSYMS['ah_on_play'], PSYMS['ah_on_shuffle']
    pages = ['home_page', 'm1plus_menu', 'playing_page', 'm1plus_cover', 'albuminfo_page']
    mm = StackMachine(pages)
    expect(mm.call(pod.FUNCTIONS['window_manager_get_top_window'][2], a0=mm.wmw, count=100000) == mm.top()[1],
           'the model runs demo\'s own window_manager_get_top_window: it finds the topmost visible window')
    for label, fn in (('Play all', play_all), ('Shuffle', shuffle)):
        m = StackMachine(pages); m.call(fn, count=60000000)
        expect(m.names_() == ['home_page', 'm1plus_menu', 'playing_page'] and m.backs == 2 and m.closed.count('playing_page') == 1
               and m.opened == ['playing_page'] and m.played and len(m.played[0]) == 4,
               f'{label} with a Now Playing under the pages: the pages above it are popped, the old Now Playing closed, a new one opened over the menu ({m.names_()}, {m.backs} back)')
        expect(m.top()[0] == 'playing_page' and 'start_player' not in m.names(), f'{label}: the player is started by the new Now Playing\'s init, not here')
        m = StackMachine(['home_page', 'm1plus_menu', 'm1plus_albums', 'albuminfo_page']); m.call(fn, count=60000000)
        expect(m.names_() == ['home_page', 'm1plus_menu', 'm1plus_albums', 'albuminfo_page', 'playing_page'] and m.backs == 0 and not m.closed,
               f'{label} with no Now Playing in the stack: nothing is popped, the page opens over the album page ({m.names_()})')
        m = StackMachine(pages, songer=0); m.call(fn, count=60000000)
        expect(m.names_() == pages + ['playing_page'] and m.backs == 0,
               f'{label} with songerinfoflag clear: the stock handler does not pop either, the page opens over the old one ({m.names_()})')
        m = StackMachine(['playing_page', 'home_page', 'm1plus_menu', 'albuminfo_page']); m.call(fn, count=60000000)
        expect(m.names_() == ['playing_page', 'home_page', 'playing_page'] and m.backs == 2,
               f'{label}: the pop stops at home_page ({m.names_()})')
    # a page with a close animation would never leave: stock's loop would spin; ours stops at AH_POP_MAX and opens anyway
    m = StackMachine(['home_page', 'playing_page', 'slide_page', 'albuminfo_page'], anim={'slide_page'}); m.call(play_all, count=80000000)
    expect(m.backs == O['AH_POP_MAX'] and m.names_()[-1] == 'playing_page' and 'slide_page' in m.names_(),
           f'a page still on screen after navigator_back (a close animation) cannot spin the loop: {m.backs} calls, then it opens ({m.names_()})')
    # none of the library or pod pages has a close animation (only the settings windows slide): every stock navigator_back above is synchronous
    import awtk_ui
    raw = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui')
    bad = []
    for f in sorted(os.listdir(raw)):
        if f.endswith('.bin'):
            root = awtk_ui.parse(open(os.path.join(raw, f), 'rb').read())
            if any('anim' in k for k, _ in root.props): bad.append(f)
    expect(len(os.listdir(raw)) > 20 and bad == ['kb_default_t9ext.bin', 'screensaver_page.bin'],
           f'no library, Cover Flow, menu or Now Playing page has an open/close animation; only the keyboard and the lock screen (neither in the pop path) slide ({bad})')


def tint_machine(rgb=None, scroll=0, card=False, tracks=6):
    """A header built in a page window (the album page's, with the stock list) and, with rgb, the real cover on its widget."""
    m = AlbumMachine(); item = m.header(card=card, tracks=tracks)
    art = m.kids(item)[0]
    if scroll: m.props[(m.sv, 'yoffset')] = scroll
    if rgb: m.real_cover(art, rgb)
    return m, item, art


def paint_corners(m, art):
    """The cover's EVT_AFTER_PAINT as stock's widget_paint dispatches it: the fills (colour word, x, y, w, h) it made."""
    ev = m.alloc(0x40); m.u.mem_write(ev, bytes(0x40)); m.setword(ev + O['EVENT_PAINT_CANVAS'], 0x7000a000)
    m.fills = []
    m.call(PSYMS['ah_on_art_paint'], a0=art, a1=ev, count=2000000)
    return list(m.fills)


def tone_word(rgb):
    import mod_nowplaying as mn
    t = mn.tone(*rgb)
    return 0xff000000 | t[0] | t[1] << 8 | t[2] << 16


def tint_tests(expect):
    """The album page's cover tint (patch/albuminfo.c ah_*): on a real cover only, the corners in the colour behind them."""
    import mod_nowplaying as mn, mod_icons, awtk_style, awtk_ui
    from PIL import Image
    tick = PSYMS['ah_tick']
    styles = lambda m: [s for s in m.styled if s[1] == 'normal:bg_color']
    covers = {'red': (190, 50, 55), 'blue': (40, 80, 190), 'grey': (120, 120, 124), 'bright': (240, 225, 150), 'black': (0, 0, 0), 'white': (255, 255, 255)}

    # ---- on / off by art presence
    m, item, art = tint_machine()
    win = m.page_window
    timers = [c for c in m.calls if c[0] == 'timer_add']
    expect(len(timers) == 1 and timers[0][1] == PSYMS['ah_tick'] and timers[0][2] == O['AH_TICK_MS'] and m.bound.get(win, {}).get(O['EVT_DESTROY']) == (PSYMS['ah_on_destroy'], win),
           'a page with a header: one polling timer, and the window\'s destroy handler')
    expect(not styles(m) and m.call(tick, count=3000000) == O['RET_REPEAT'] and not styles(m), 'the placeholder disc: the page stays black, the timer goes on')
    expect(paint_corners(m, art) and all(f[0] & 0xffffff == 0 for f in m.fills), 'and its corners are painted black')
    m.real_cover(art, covers['red'])
    m.styled.clear()
    expect(m.call(tick, count=3000000) == 0 and styles(m) == [(win, 'normal:bg_color', tone_word(covers['red']))],
           f'a real cover: the window takes the tone of its average colour ({tone_word(covers["red"]):#x}) and the timer ends')
    expect(('widget_invalidate_force', win) in m.calls, 'and the window is repainted')
    m.styled.clear(); m.call(tick, count=3000000)
    expect(not styles(m), 'a later tick does nothing more')
    # every tone the payload makes is the model's (a flat cover's average is its colour)
    bad = []
    for name, rgb in covers.items():
        m2, i2, a2 = tint_machine(rgb); m2.styled.clear(); m2.call(tick, count=3000000)
        if styles(m2) != [(m2.page_window, 'normal:bg_color', tone_word(rgb))]: bad.append((name, styles(m2)))
    expect(not bad, f'the tone of a red, blue, grey, bright, black and white cover is mod_nowplaying.tone ({bad})')
    # the All albums card never tints, with or without a cover file; the page still has its round corners
    m, item, art = tint_machine(covers['red'], card=True)
    expect(not any(c[0] == 'timer_add' for c in m.calls) and m.bound.get(art, {}).get(O['EVT_AFTER_PAINT']) and not styles(m),
           'the All albums card: no timer, no tint, but its cover still paints its corners')
    # a file that is not there yet, an image that does not decode: still black, still polling
    m, item, art = tint_machine(covers['red']); m.present.discard('/tmp/abp/c1.jpg')
    expect(m.call(tick, count=3000000) == O['RET_REPEAT'] and not styles(m), 'a cover url whose file is not there (yet): nothing')
    m, item, art = tint_machine(covers['red']); m.load_image = 1
    expect(m.call(tick, count=3000000) == O['RET_REPEAT'] and not styles(m), 'a file that does not decode: nothing, polling goes on')
    # no timer: no tint (the page stays black); no window: no state at all, the corners are still painted
    m = AlbumMachine(); m.timer_fail = True; item = m.header(); art = m.kids(item)[0]
    expect(paint_corners(m, art) and all(f[0] & 0xffffff == 0 for f in m.fills), 'a refused timer: the page stays black, its corners are painted all the same')
    m = AlbumMachine()
    item = m.header(window=False); art = m.kids(item)[0]
    expect('timer_add' not in m.names() and not m.bound.get(0, {}) and paint_corners(m, art),
           'a header in no window: no timer, no tint, the corners painted')
    # the kill switch: the stock header, nothing of ours
    m = AlbumMachine(); m.present.add(KILL); item = m.header()
    expect('timer_add' not in m.names() and not m.bound.get(m.kids(item)[0], {}), 'the kill switch keeps the page stock: no timer, no paint hook')

    # ---- destroy: nothing runs after it
    m, item, art = tint_machine(); win = m.page_window
    m.call(PSYMS['ah_on_destroy'], a0=win + 4, a1=0, count=100000)
    expect(not any(c[0] == 'timer_remove' for c in m.calls), 'another window\'s destroy is not ours')
    m.call(PSYMS['ah_on_destroy'], a0=win, a1=0, count=100000)
    expect(('timer_remove', 0x777) in m.calls, 'the window\'s destroy removes the polling timer')
    m.real_cover(art, covers['red']); m.styled.clear()
    expect(m.call(tick, count=3000000) == 0 and not styles(m) and not [c for c in m.calls if c[0] in ('widget_lookup', 'widget_load_image')],
           'a tick after the destroy does nothing (no lookup, no decode, no style)')
    # a new page replaces an old one that never said it was gone: the old timer goes, a new one starts
    m, item, art = tint_machine()
    parent = m.new_widget('scroll_view', 0, 0, 0, 310, 400); it2 = m.new_widget('list_item', parent, 0, 0, 0, 100); m.props[(it2, 'w')] = 310
    m.page_window = m.new_widget('window', 0, 0, 0, 320, 450); m.sv = parent
    m.call(HEADER_BUILDER, a0=it2, count=2000000)
    expect(('timer_remove', 0x777) in m.calls and sum(1 for c in m.calls if c[0] == 'timer_add') >= 1, 'a second page: the first one\'s timer is removed and its own starts')
    # the same page's header built again (to-foreground): no second timer, the corners keep the colour
    m, item, art = tint_machine(covers['blue']); m.call(tick, count=3000000)
    it2 = m.new_widget('list_item', m.sv, 0, 0, 0, 100); m.props[(it2, 'w')] = 310; m.calls.clear()
    m.call(HEADER_BUILDER, a0=it2, count=2000000)
    art2 = m.kids(it2)[0]; m.widgets['img_albumcover_m'] = art2
    expect('timer_add' not in m.names() and m.bound.get(art2, {}).get(O['EVT_AFTER_PAINT']) == (PSYMS['ah_on_art_paint'], art2),
           'the header built again for the same tinted page: no new timer, its cover paints the corners')
    fills = paint_corners(m, art2)
    expect(fills and any(f[0] & 0xffffff for f in fills), 'and in the tint\'s colour')

    # ---- contrast: white title >= 4.5:1, grey artist and year >= 3:1, the navbar's white glyphs >= 3:1, over every tone at the header rows
    nav = 0   # the list starts at the window's top: the header's rows are window rows (the floating controls' glyphs sit on glass: test/pod/glassbtn.py)
    rows = {'title': ((255, 255, 255), 4.5, nav + O['AH_TITLE_Y'], nav + O['AH_TITLE_Y'] + O['AH_TITLE_H']),
            'artist': ((0xAA,) * 3, 3.0, nav + O['AH_ARTIST_Y'], nav + O['AH_ARTIST_Y'] + O['AH_ARTIST_H']),
            'year line': ((0x9C,) * 3, 3.0, nav + O['AH_META_Y'], nav + O['AH_META_Y'] + O['AH_META_H'])}
    grid = [(r, g, b) for r in range(0, 256, 51) for g in range(0, 256, 51) for b in range(0, 256, 51)] + [(255, 255, 255), (255, 240, 0), (0, 255, 255)]
    worst = {k: 99 for k in rows}
    for c in grid:
        t = mn.tone(*c)
        for k, (fg, need, y0, y1) in rows.items():
            for y in range(y0, y1):
                keep = 255 - mod_icons.ah_tint_alpha(y)
                worst[k] = min(worst[k], contrast(fg, tuple(v * keep // 255 for v in t)))
    print(f'  (album header worst contrast: { {k: round(v, 2) for k, v in worst.items()} })')
    expect(all(worst[k] >= rows[k][1] for k in rows), f'over every tone the header keeps its contrast: title >= 4.5, artist and year line >= 3 ({ {k: round(v, 2) for k, v in worst.items()} })')
    expect((mod_icons.AH_TINT[0], mod_icons.AH_TINT[1], mod_icons.AH_TINT[2], mod_icons.AH_TINT[3]) == (O['AH_TINT_A_TOP'], O['AH_TINT_A_BOT'], O['AH_TINT_ROWS'], O['AH_WIN_H'])
           and O['AH_TINT_ROWS'] == O['AH_HDR_H'], 'the gradient\'s numbers are the payload\'s: the header (the list starts at the window\'s top), alpha 64 to 200')

    # ---- corner pixels against the model on the gradient, scrolled and not
    R, S = O['AH_CORNER'], O['AH_ART']
    def cov_of(x, y):
        c = 2 * 8 * R
        n = sum((2 * (x * 8 + i) + 1 - c) ** 2 + (2 * (y * 8 + j) + 1 - c) ** 2 > c * c for i in range(8) for j in range(8))
        return (n * 255 + 32) // 64
    for name in ('red', 'bright', 'grey'):
        for scroll in (0, 37, 130):
            m, item, art = tint_machine(covers[name], scroll=scroll); m.call(tick, count=3000000)
            t = mn.tone(*covers[name]); want = {}
            for k in range(4):
                for y in range(R):
                    ly = S - 1 - y if k & 2 else y
                    keep = 255 - mod_icons.ah_tint_alpha(max(0, O['AH_ART_Y'] - scroll + ly))
                    shade = (t[0] * keep // 255) | (t[1] * keep // 255) << 8 | (t[2] * keep // 255) << 16
                    for x in range(R):
                        a = cov_of(x, y)
                        if a: want[(S - 1 - x if k & 1 else x, ly)] = shade | a << 24
            got = {(f[1], f[2]): f[0] for f in paint_corners(m, art) if (f[3], f[4]) == (1, 1)}
            expect(got == want and len(m.fills) == len(want), f'{name} cover, list scrolled {scroll} px: the corners are the window\'s colour on their own rows, pixel for pixel ({len(m.fills)} pixels)')
    m.fills = []; m.call(PSYMS['ah_on_art_paint'], a0=art, a1=0, count=100000)
    expect(not m.fills, 'no canvas: nothing is painted')

    # ---- the assets
    import os as _os
    raw = _os.path.join(WORK, 'rootfs', 'release/assets/default/raw')
    ui = awtk_ui.parse(open(_os.path.join(raw, 'ui', 'albuminfo_page.bin'), 'rb').read())
    t_img = ui.children[0]
    expect([c.name for c in ui.children] == ['img_ah_tint', 'albuminfo_listview', 'navigationbar_view'] and (t_img.x, t_img.y, t_img.w, t_img.h) == (0, 0, 320, O['AH_WIN_H'])
           and t_img.get('sensitive') == 'false' and t_img.get('image') == 'ah_tint',
           'the tint gradient is the window\'s first child, window sized and insensitive; the list is next and the navbar band LAST (over the list)')
    lv, sv = ui.find('albuminfo_listview'), ui.find('albuminfo_scrollview')
    expect(all(w.get(f'style:{s}:bg_color') == '#00000000' for w in (lv, sv) for s in ('normal', 'disable', 'focused')) and ui.get('style:normal:bg_color') == '#000000',
           'the list and its scroll view are transparent; the window itself stays black (the payload sets its colour)')
    nb, nsv = ui.find('navigationbar_view'), ui.find('albuminfo_scrollview')
    bar = ui.find('scroll_bar_m'); lh = O['AH_WIN_H']
    expect((nb.x, nb.y, nb.w, nb.h) == (0, 0, 320, O['AH_NAV_BAND_H']) == mod_ipodrows.NAV_BAND
           and lv.y == 0 and (lv.h, nsv.h, bar.h) == (lh, lh, lh),
           f'the navbar is a {nb.w}x{nb.h} band at ({nb.x}, {nb.y}); the list starts at the window\'s top and is {lv.h} high ({lv.y}+{lv.h}; scroll view {nsv.h}, scroll bar {bar.h})')
    expect(O['AH_NAV_TOP'] == 44 and O['AH_ART_Y'] == O['AH_NAV_TOP'] + 6 and O['AH_NAV_BAND_H'] == 50 and O['AH_NAV_H'] == mod_ipodrows.NAV_H == 44,
           'the header\'s top padding keeps the cover where it was (window row 50) and the band ends above it')
    import json as _json
    J = _json.load(open(_os.path.join(ROOT, 'patch', 'rows.json')))
    nav_sites = {int(a, 16): g['value'] for g in J['immediates'] for a, *_ in g['sites'] if 0x526a3c <= int(a, 16) < 0x527010}
    stock_demo_b = open(_os.path.join(paths.find_stock() or _os.path.join(_os.path.dirname(WORK), 'stock'), 'rootfs', pod.DEMO), 'rb').read()
    built_b = open(DEMO, 'rb').read()
    word = lambda b, a: struct.unpack_from('<I', b, pod.fileoff(b, a))[0]
    height_sites = [0x526aec, 0x526b68, 0x526d20, 0x526d7c, 0x526e40, 0x526f44, 0x526fa4]
    vw, cf, vx = O['NAV_VIEW_W'], O['NAV_CF_X'], O['NAV_VIEW_X']
    # the buttons on the Pod navbar's slots (tools/pod_ui.py navbar: 168 / 214, 46 wide; Now Playing 60 wide, 2 px right of 260 for its
    # navbar_btnbackplayer_style glyph; Back 3 px right for its icon square of AH_NAV_H; the multi-select glyph lands on the Pod toggle's at
    # 214 as it is; device shots): address -> (stock low half, built)
    slot_sites = {0x526d8c: (0x32, vw), 0x526de0: (0x32, vw), 0x526e48: (0x32, vw), 0x526f48: (0x32, vw), 0x526d98: (0x78, cf - vw),
                  0x526dec: (0xaa, cf), 0x526f54: (0xaa, cf), 0x526e54: (0xdc, vx), 0x526ea8: (0x10e, 262), 0x526e9c: (0x32, 60),
                  0x526f00: (0x2825, (50 - O['AH_NAV_H']) // 2)}
    expect(sorted(nav_sites) == sorted(height_sites + list(slot_sites))
           and all(word(built_b, a) & 0xffff == v for a, v in nav_sites.items())
           and all(word(stock_demo_b, a) & 0xffff in (0x32, 0xe, 0x10) for a in height_sites)
           and [nav_sites[a] for a in (0x526aec, 0x526d7c, 0x526e40, 0x526f44)] == [O['AH_NAV_H']] * 4
           and nav_sites[0x526d20] == nav_sites[0x526fa4] == (O['AH_NAV_H'] - 22) // 2 and nav_sites[0x526b68] == (O['AH_NAV_H'] - 20) // 2,
           'the navbar builder (0x526a3c): every button is AH_NAV_H high, the title labels centred in it (stock words checked, built words written)')
    expect(all(word(stock_demo_b, a) & 0xffff == s and nav_sites[a] == b for a, (s, b) in slot_sites.items())
           and word(stock_demo_b, 0x526f00) == 0x00002825 and word(built_b, 0x526f00) == 0x24050000 | nav_sites[0x526f00]
           and (cf, vx, vw) == (168, 214, 46),
           'the navbar builder\'s buttons sit on the Pod navbar\'s slots (122, 168, 214 x 46; Now Playing 262 x 60; Back x 3: move $a1, $zero -> addiu $a1, $zero, 3)')
    am = awtk_ui.parse(open(_os.path.join(raw, 'ui', 'allmusic_page.bin'), 'rb').read()).find('navigationbar_view')
    expect((am.x, am.y, am.w, am.y + am.h) == (0, (50 - O['AH_NAV_H']) // 2, 320, 50) and am.y + nav_sites[0x526fa4] == 14,
           f'allmusic_page (Songs, a playlist\'s songs): the 50 px bar\'s view starts at y {am.y}, so the builder\'s {O["AH_NAV_H"]} px buttons and title centre as the Pod navbar\'s (title y 14)')
    # the other stock pages' navbars (docs/modules/navbar.md): the same slots, built by their own code (folder 0x5312dc, localclass 0x535188,
    # the Playlists page 0x53d5f8, album_page 0x524e4c, search_page's init): address -> (stock word, built value)
    mul, srch, back = 0x240500e0, 0x2407003c, 0x2405010e
    other = {0x531558: (srch, 46), 0x531564: (mul, vx), 0x5315ac: (srch, 46), 0x5315b8: (0x240500b2, 168), 0x531620: (back, 262),
             0x535454: (srch, 46), 0x535460: (0x240500b7, 168), 0x5356d8: (srch, 46), 0x5356e4: (0x240500b7, 168),
             0x535554: (srch, 46), 0x535560: (mul, vx), 0x5355b4: (back, 262),
             0x53d81c: (srch, 46), 0x53d828: (mul, vx), 0x53d87c: (back, 262),
             0x52512c: (srch, 46), 0x525138: (mul, vx), 0x52518c: (back, 262),
             0x543764: (0x2407002f, 60), 0x543770: (0x24050111, 260)}
    np_w = [0x531614, 0x5355a8, 0x53d870, 0x525180]   # the Now Playing buttons there are 60 wide in stock
    got = {int(a, 16): g['value'] for g in J['immediates'] for a, *_ in g['sites'] if int(a, 16) in other}
    expect(got == {a: b for a, (s, b) in other.items()}
           and all(word(stock_demo_b, a) == s and word(built_b, a) == (s & 0xffff0000) | b for a, (s, b) in other.items())
           and all(word(stock_demo_b, a) == word(built_b, a) == srch for a in np_w),
           'Folders, Artists/Genres/Composers, the stock Playlists page, an artist\'s albums and Search: their navbar builders\' button x / w words are on the Pod navbar\'s slots')
    # the stock Now Playing (navbar_btnbackplayer_style) draws its glyph 2 px left of its centre, the multi-select glyph lands on the Pod
    # toggle's at 214 (device shots); img_btn_style / search_style buttons are centred: every right-hand glyph is on 191 / 237 / 290
    expect(vx + vw // 2 == 237 and 168 + 46 // 2 == cf + vw // 2 == 191 and 262 + 60 // 2 - 2 == 260 + 60 // 2 == 290 and vx + vw == 260,
           'the right-hand glyph centres are 191 (second slot), 237 (multi-select), 290 (Now Playing and Search\'s go button), as the Pod navbar\'s')
    import mod_lists
    th = lambda theme, page: mod_lists.parse(open(_os.path.join(WORK, 'rootfs', 'release/assets', theme, 'raw/styles', page + '.bin'), 'rb').read())
    pages = ('folder_page', 'localclass_page', 'allmusic_page', 'playerjumpinfo_page', 'playlist_page')
    expect(all(th(t, p).find('hscroll_label', 'srlabel_leftwhite22_style', s) is not None
               and th(t, p).find('hscroll_label', 'srlabel_leftwhite22_style', s).get('font_size') == 20
               for t in mod_lists.THEMES for p in pages for s in ('normal',)),
           'the navbar title style (srlabel_leftwhite22_style, 22 px in stock) is 20 px in the page theme of every page whose builder uses it (both themes)')
    stock_ui = _os.path.join(paths.find_stock() or _os.path.join(_os.path.dirname(WORK), 'stock'), 'rootfs', 'release/assets')
    geo = lambda root, n: (lambda w: (w.x, w.y, w.w, w.h))(root.find(n))
    ok = True
    for theme in mod_lists.THEMES:
        for rel, want in (('playset/equalizer_page.bin', {'btn_backtoplayer': ((270, 0, 50, 50), (260, 0, 60, 50))}),
                          ('systemset/specfolder_page.bin', {'btn_backtoplayer': ((279, 0, 41, 50), (260, 0, 60, 50)),
                                                             'navigation_btn_allchoice': ((229, 0, 38, 50), (vx, 0, vw, 50))})):
            s_ui = awtk_ui.parse(open(_os.path.join(stock_ui, theme, 'raw/ui', rel), 'rb').read())
            b_ui = awtk_ui.parse(open(_os.path.join(WORK, 'rootfs', 'release/assets', theme, 'raw/ui', rel), 'rb').read())
            ok &= all(geo(s_ui, n) == a and geo(b_ui, n) == b for n, (a, b) in want.items())
    expect(ok,
           'Settings > Equalizer and the folder picker (both themes): Now Playing (img_btn_style) at (260, 0, 60, 50); the picker\'s select-all on the 214 slot, 46 wide')
    tint_png = Image.open(_os.path.join(raw, 'images', 'xx', 'ah_tint.png')).convert('RGBA')
    expect(tint_png.size == (320, O['AH_WIN_H']) and all(tint_png.getpixel((x, y)) == (0, 0, 0, mod_icons.ah_tint_alpha(y)) for y in range(O['AH_WIN_H']) for x in (0, 319))
           and tint_png.getpixel((5, 0))[3] == O['AH_TINT_A_TOP'] and tint_png.getpixel((5, O['AH_TINT_ROWS'] - 1))[3] == O['AH_TINT_A_BOT'] == 200 and tint_png.getpixel((5, 449))[3] == 200
           and _os.path.getsize(_os.path.join(raw, 'images', 'xx', 'ah_tint.png')) < 3000, 'ah_tint.png: black, alpha 64 at the top rising to 200 (the deep tint) at the header\'s end and held below it, small')
    for theme in ('default', 'theme1'):
        th = awtk_style.parse(open(_os.path.join(WORK, 'rootfs', 'release/assets', theme, 'raw/styles/albuminfo_page.bin'), 'rb').read())
        head = [i for i in th.items if (i.widget, i.style) == ('list_item', 'list_item_ahhead_style')]
        expect(len(head) >= 3 and all(i.color('bg_color') == '#00000000' for i in head), f'{theme}: the header item\'s style is transparent')
        base = awtk_style.parse(open(_os.path.join(WORK, 'rootfs', 'release/assets', theme, 'raw/styles/default.bin'), 'rb').read())
        rows_ = [i for i in base.items if (i.widget, i.style, i.state) == ('list_item', 'list_item_style', 'normal')]
        nav = [i for i in th.items + base.items if (i.widget, i.style, i.state) == ('view', 'default', 'normal')]
        nav = [i for i in th.items + base.items if i.widget == 'view' and i.style == 'default' and i.color('bg_color') not in (None, '#00000000')]
        expect(not nav, f'{theme}: the navbar view has no style of its own and the theme gives plain views no opaque background, so it paints nothing and the gradient shows through ({[repr(i) for i in nav]})')
        expect(rows_ and rows_[0].color('bg_color').endswith('FF'),
               f'{theme}: every other page\'s rows (default.bin list_item_style) stay opaque ({rows_[0].color("bg_color") if rows_ else None})')
        # this page's own list_item_style (resolved in the window's theme first): transparent rows, translucent white pressed band and hairline
        mine = {i.state: i for i in th.items if (i.widget, i.style) == ('list_item', 'list_item_style')}
        ref = {i.state: i for i in base.items if (i.widget, i.style) == ('list_item', 'list_item_style')}
        expect(set(mine) == set(ref) == {'normal', 'pressed', 'over', 'focused', 'disable'}
               and all(mine[s].color('bg_color') == ('#FFFFFF33' if s == 'pressed' else '#00000000') for s in mine),
               f'{theme}: the album page\'s track rows are transparent, the pressed row a 20 % white band ({ {s: mine[s].color("bg_color") for s in mine} })')
        expect(all(mine[s].color('border_color') == '#FFFFFF22' and mine[s].get('border') == ref[s].get('border') == 8 and mine[s].get('border_width') == 1 for s in mine),
               f'{theme}: the hairline is a 1 px bottom border in 13 % white')
        keep = lambda i: [(k, v) for k, v, _ in i.props if k not in ('bg_color', 'border_color', 'border_width')]
        expect(all(keep(mine[s]) == keep(ref[s]) for s in mine), f'{theme}: nothing else of the row style changed')
        if theme == 'default': gold = base.find(widget='hscroll_label', style='srlabel_item_gold20_style', state='normal')[0].color('text_color')   # theme1's gold is an accent (audited apart by mod_theme)

    # ---- the deep tint under the track rows: contrast of the row text over every tone, rest, pressed, and scrolled up into the header's ramp
    H = O['AH_TINT_A_BOT']
    hexrgb = lambda s: tuple(int(s[k:k + 2], 16) for k in (1, 3, 5))
    ink = {'title': (255, 255, 255), 'track number': (0xAA,) * 3, 'playing row': hexrgb(gold)}
    need = {'title': 4.5, 'track number': 3.0, 'playing row': 4.5}
    def under(t, y): return tuple(v * (255 - mod_icons.ah_tint_alpha(y)) // 255 for v in t)
    def pressed_over(bg): return tuple(c + (255 - c) * 0x33 // 255 for c in bg)
    rest, press = {k: 99 for k in ink}, {k: 99 for k in ink}
    for c in grid:
        t = mn.tone(*c)
        for k, fg in ink.items():
            rest[k] = min(rest[k], contrast(fg, under(t, 449)))
            press[k] = min(press[k], contrast(fg, pressed_over(under(t, 449))))
    expect(mod_icons.ah_tint_alpha(O['AH_HDR_H']) == H == mod_icons.ah_tint_alpha(449),
           'the track rows start where the held alpha starts (window row 344) and it holds to the bottom')
    expect(all(rest[k] >= need[k] for k in ink), f'over every tone, at rest: title >= 4.5, playing row >= 4.5, track number >= 3 ({ {k: round(v, 2) for k, v in rest.items()} })')
    expect(all(press[k] >= need[k] for k in ink), f'and on the pressed row (20 % white over the deep tint): the same floors ({ {k: round(v, 2) for k, v in press.items()} })')
    print(f'  (album list at rest, held alpha {H}: {rest}; pressed: {press}; black page pressed track number {contrast((0xAA,) * 3, (0x33,) * 3):.2f}:1)')
    # a row scrolled up into the header's rows (the overlay is fixed in the window): the list shows from window row 0 (under the floating controls)
    sc = {k: (99, None) for k in ink}
    for c in grid:
        t = mn.tone(*c)
        for y in range(0, O['AH_HDR_H']):
            for k, fg in ink.items():
                v = contrast(fg, under(t, y))
                if v < sc[k][0]: sc[k] = (v, (c, y))
    print(f'  (album list, rows scrolled up under the list top: worst title {sc["title"][0]:.2f}:1, track number {sc["track number"][0]:.2f}:1, playing row {sc["playing row"][0]:.2f}:1 at window row 0-{O["AH_HDR_H"]})')
    expect(sc['title'][0] >= 3.0, f'a track title passing the brightest header rows keeps at least 3:1 (worst {sc["title"][0]:.2f}:1; it is not a resting place: it only passes)')
    # a black page (placeholder, All albums card, kill switch): the window is black under the black overlay; translucent white is today's grey
    blend = lambda a, base_=0: base_ + (255 - base_) * a // 255
    expect(blend(0x33) in (50, 51) and blend(0x22) in (33, 34), f'on a black page the pressed band is #{blend(0x33):02X}{blend(0x33):02X}{blend(0x33):02X} (was #333333) and the hairline #{blend(0x22):02X}{blend(0x22):02X}{blend(0x22):02X} (was #222222)')
    expect(contrast((0xAA,) * 3, (blend(0x33),) * 3) >= 5.0, f'the track number on a black page\'s pressed row keeps today\'s contrast ({contrast((0xAA,) * 3, (blend(0x33),) * 3):.2f}:1)')


class _Calls(list):
    """A call log that also keeps every write-like call it ever saw (the harness starts a new log per emulated call)."""
    def __init__(self, it=(), owner=None):
        super().__init__(it); self.owner = owner

    def append(self, c):
        if self.owner is not None:
            self.owner.seen.append(c)
            if (c[0] == 'fopen' and any(x in c[2] for x in 'wa+')) or (c[0] == 'open' and c[2] & 3) or c[0] in ('fwrite', 'write', 'rename', 'remove', 'unlink', 'mkdir'):
                self.owner.writes.append(c)
        super().append(c)


class WatchMachine(AlbumMachine):
    def __init__(self):
        self.seen, self.writes = [], []
        super().__init__()

    @property
    def calls(self): return self._calls

    @calls.setter
    def calls(self, v): self._calls = _Calls(v, self)


def bar_tests(expect):
    """The status bar takes the tinted album page's top-edge colour (patch/albuminfo.c ah_bar_*, patch/common.c pod_bar_*): the same
    suite as Now Playing's bar, applied to this page, plus the hand-over between the two pages."""
    import mod_nowplaying as mn, mod_icons
    tick = PSYMS['ah_tick']
    BLACK = O['NP_BAR_STOCK']
    BG, FG = O['EVT_WINDOW_TO_BG'], O['EVT_WINDOW_TO_FG']
    red, bright = (190, 50, 55), (240, 225, 150)
    def model(t):   # the tone under the overlay's row 0, darkened until white glyphs keep 4.5:1 (a color_t word)
        keep = 255 - mod_icons.ah_tint_alpha(0)
        r, g, b = (v * keep // 255 for v in t)
        while 2126 * r * r + 7152 * g * g + 722 * b * b > O['NP_BAR_LUM_MAX']: r, g, b = r * 15 >> 4, g * 15 >> 4, b * 15 >> 4
        return 0xff000000 | r | g << 8 | b << 16
    rgb_of = lambda w: (w & 255, w >> 8 & 255, w >> 16 & 255)
    def page(rgb=red, **kw):   # a tinted page in front, with a status bar
        m = AlbumMachine().with_bar(); item = m.header(**kw); art = m.kids(item)[0]
        if rgb: m.real_cover(art, rgb); m.call(tick, count=3000000)
        return m, item, art
    inval = lambda m: sum(c[0] == 'widget_invalidate_force' and c[1] == m.bar for c in m.calls)

    # the colour: the page's row 0 under the overlay, capped for the white glyphs, on every tone
    m = AlbumMachine()
    tones = sorted({mn.tone(r, g, b) for r in range(0, 256, 51) for g in range(0, 256, 51) for b in range(0, 256, 51)} | {mn.tone(255, 255, 255), mn.tone(255, 240, 0)})
    def c_bar(t):
        return m.call(PSYMS['pod_bar_color'], a0=t[0] | t[1] << 8 | t[2] << 16, count=100000)
    keep0 = lambda t: tuple(v * (255 - mod_icons.ah_tint_alpha(0)) // 255 for v in t)
    expect(all(c_bar(keep0(t)) == model(t) for t in tones), f'pod_bar_color equals the model on {len(tones)} tones: the overlay\'s row 0 over the tone, darkened to the luminance cap')
    wc = min(contrast((255, 255, 255), rgb_of(model(t))) for t in tones)
    expect(wc >= 4.5, f'the bar\'s white glyphs and clock keep 4.5:1 on every tone (worst {wc:.2f}:1)')
    seam = max(max(a - b for a, b in zip(keep0(t), rgb_of(model(t)))) for t in tones)
    undarkened = sum(1 for t in tones if rgb_of(model(t)) == keep0(t))
    steps = {t: max(a - b for a, b in zip(keep0(t), rgb_of(model(t)))) for t in tones}
    over = [t for t in tones if steps[t] > 12]
    worst_t = max(tones, key=steps.get)
    print(f'  (album bar: largest channel step page row 0 -> bar {seam} levels at tone {worst_t}; {undarkened} of {len(tones)} tones undarkened; {len(over)} tones above 12 levels: {over[:6]})')
    expect(seam <= 34, f'the seam between the bar and the page\'s row 0 stays at most 34 levels in a channel, the bright yellow end of the tone range (largest {seam}); a typical bright cover is 8')

    # a real cover: the bar takes the colour once, repainted, and the window its own; ticks leave it alone
    m, item, art = page(red); win = m.page_window
    t = mn.tone(*red)
    expect(m.bar_styles() == [model(t)] and inval(m) == 1 and [s for s in m.styled if s[0] == win] == [(win, 'normal:bg_color', tone_word(red))],
           f'a real cover: the bar gets the colour of the page\'s first row ({[hex(x) for x in m.bar_styles()]}) and is repainted, the window gets its tone')
    expect(all(s[1] == 'normal:bg_color' for s in m.styled) and m.children[m.wm][0] not in [s[0] for s in m.styled], 'only the child of type system_bar is styled (not the navbar)')
    m.call(tick, count=3000000); m.call(tick, count=3000000)
    expect(len(m.bar_styles()) == 1, 'ticks afterwards leave the bar alone')
    m, item, art = page(bright)
    expect(contrast((255, 255, 255), rgb_of(m.bar_styles()[0])) >= 4.5 and m.bar_styles()[0] != 0xff000000 | sum(v * 191 // 255 << s for v, s in zip(mn.tone(*bright), (0, 8, 16))),
           'a bright cover: the bar is darker than the page\'s first row, so the white glyphs stay readable')

    # the bar is the window's row 0 under the overlay, which is a child of the window (not of the list): it never depends on the scroll
    got = {}
    for scroll in (0, 150, 300):
        m = AlbumMachine().with_bar(); item = m.header(); art = m.kids(item)[0]
        m.props[(m.sv, 'yoffset')] = scroll; m.real_cover(art, red); m.call(tick, count=3000000); m.fire(BG); m.fire(FG)
        got[scroll] = m.bar_styles()
    expect(got[0] == got[150] == got[300] == [model(t), BLACK, model(t)], f'the bar colour is the same at list offsets 0, 150 and 300 (the overlay is fixed in the window: {[hex(x) for x in got[0]]})')

    # the tint at once from the cache (header build): the bar too, no timer
    m = AlbumMachine().with_bar(); key = fnv(fnv(O['FNV_SEED'], 'Miles Davis'), 'Kind of Blue') or 1
    cf = art_file(key); m.present.add(cf); m.files[cf] = 4096; m.load_image = 0
    m.images['file://' + cf] = (O['ART_SIZE'], O['ART_SIZE'], bytes(red + (255,)) * O['ART_SIZE'] ** 2); m.header()
    expect(m.bar_styles() == [model(t)] and not any(c[0] == 'timer_add' for c in m.calls), 'a tint from the cache or Cover Flow\'s file tints the bar at once, while the header builds')

    # black pages never touch the bar
    m, item, art = page(None); m.call(tick, count=3000000)
    expect(not m.bar_styles() and not inval(m), 'the placeholder disc: the page and the bar stay black')
    m.fire(BG); m.fire(FG)
    expect(not m.bar_styles(), 'and its window events leave the bar alone')
    m = AlbumMachine().with_bar(); item = m.header(card=True); m.real_cover(m.kids(item)[0], red); m.fire(BG); m.fire(FG)
    expect(not m.bar_styles(), 'the All albums card: black bar, even through window events')
    m = AlbumMachine().with_bar(); m.present.add(KILL); m.header()
    expect(not m.bar_styles() and not m.bound.get(m.page_window), 'the kill switch: the bar is never touched, no window event is registered')
    m = AlbumMachine().with_bar(); m.present.add(cf); m.files[cf] = 0; m.header(); m.fire(FG)
    expect(not m.bar_styles(), 'the no-art marker: a black bar')
    m = AlbumMachine().with_bar(); item = m.header(window=False)
    expect(not m.bar_styles() and not any(c[0] == 'timer_add' for c in m.calls), 'a header in no window: nothing')

    # TO_BACKGROUND: black and repainted, once; TO_FOREGROUND: the page's colour again
    m, item, art = page(red); win = m.page_window; m.styled.clear(); m.calls.clear()
    m.fire(BG)
    expect(m.bar_styles() == [BLACK] and inval(m) == 1, 'EVT_WINDOW_TO_BACKGROUND: the bar is black again and repainted')
    m.fire(BG)
    expect(m.bar_styles() == [BLACK], 'a second one does not set it again')
    m.fire(FG)
    expect(m.bar_styles() == [BLACK, model(t)], 'EVT_WINDOW_TO_FOREGROUND: the bar takes the page\'s colour again')
    m.fire(FG)
    expect(m.bar_styles() == [BLACK, model(t), model(t)], 'a repeated foreground event only sets the same colour again')
    # an event whose context is not the current window changes nothing
    n = len(m.bar_styles()); fn = m.bound[win][BG][0]; m.call(fn, a0=win + 4, a1=0, count=100000)
    expect(len(m.bar_styles()) == n, 'a window event of another page changes nothing')
    # a tint that arrives while the page is covered: the window colours, the bar waits for the foreground
    m, item, art = page(None); win = m.page_window; m.fire(BG)
    m.real_cover(art, red); m.call(tick, count=3000000)
    expect(not m.bar_styles() and [s for s in m.styled if s[0] == win], 'a cover that resolves while the page is covered tints the page, not the bar')
    m.fire(FG)
    expect(m.bar_styles() == [model(t)], 'and the bar follows when the page is in front again')

    # destroy
    m, item, art = page(red); win = m.page_window; m.styled.clear()
    m.call(PSYMS['ah_on_destroy'], a0=win + 4, a1=0, count=100000)
    expect(not m.bar_styles(), 'another window\'s destroy leaves the bar')
    m.call(PSYMS['ah_on_destroy'], a0=win, a1=0, count=100000)
    expect(m.bar_styles() == [BLACK], 'the page\'s destroy puts the stock black back')
    m.call(PSYMS['ah_on_destroy'], a0=win, a1=0, count=100000); m.call(PSYMS['ah_on_background'], a0=win, a1=0, count=100000) if 'ah_on_background' in PSYMS else None
    m.call(tick, count=3000000)
    expect(m.bar_styles() == [BLACK], 'after the destroy: a second destroy, a stray tick and a stray event never touch the bar')
    m, item, art = page(red); win = m.page_window; m.fire(BG); m.styled.clear(); m.call(PSYMS['ah_on_destroy'], a0=win, a1=0, count=100000)
    expect(not m.bar_styles(), 'a destroy of a page already backgrounded has nothing to restore')
    # a new page replaces an old one that never said it was gone: the bar is black first, then the new page's tone
    m, item, art = page(red); first = m.page_window; m.styled.clear()
    parent = m.new_widget('scroll_view', 0, 0, 0, 310, 400); it2 = m.new_widget('list_item', parent, 0, 0, 0, 100); m.props[(it2, 'w')] = 310
    m.page_window = m.new_widget('window', 0, 0, 0, 320, 450); m.sv = parent
    m.call(HEADER_BUILDER, a0=it2, count=2000000)
    expect(m.bar_styles() == [BLACK, model(t)], 'a replaced page: the bar goes black, then takes the new page\'s tone (here at once, from the tone cache)')
    m.call(PSYMS['ah_on_destroy'], a0=first, a1=0, count=100000)
    expect(m.bar_styles() == [BLACK, model(t)], 'and the old page\'s late destroy does not touch it')
    # the header built again for the same page (to-foreground): the events are not registered twice, the bar is not set again
    m, item, art = page(red); n = len(m.bar_styles()); bound = dict(m.bound[m.page_window])
    it2 = m.new_widget('list_item', m.sv, 0, 0, 0, 100); m.props[(it2, 'w')] = 310
    m.call(HEADER_BUILDER, a0=it2, count=2000000)
    expect(len(m.bar_styles()) == n and m.bound[m.page_window] == bound, 'the header built again for the same page: same handlers, the bar left as it is')

    # failures: nothing owed, nothing touched
    for ev in (BG, FG):
        m = AlbumMachine().with_bar(); m.on_fail = {ev}; item = m.header(); art = m.kids(item)[0]; m.real_cover(art, red); m.call(tick, count=3000000)
        expect(not m.bar_styles() and [s for s in m.styled if s[0] == m.page_window], f'event {ev:#x} refused: the page tints, the bar is never touched (it could not be restored)')
        m.call(PSYMS['ah_on_destroy'], a0=m.page_window, a1=0, count=100000); expect(not m.bar_styles(), 'and the destroy has nothing to restore')
    m = AlbumMachine().with_bar(); m.bar_fail = True; item = m.header(); art = m.kids(item)[0]; m.real_cover(art, red); m.call(tick, count=3000000)
    expect(not m.bar_styles() and inval(m) == 0 and [s for s in m.styled if s[0] == m.page_window], 'a failing bar style call: no repaint of the bar, the page still tints')
    m.bar_fail = False; m.styled.clear(); m.call(PSYMS['ah_on_destroy'], a0=m.page_window, a1=0, count=100000)
    expect(not m.bar_styles(), 'and nothing is restored at the end (the bar was never ours)')
    m = AlbumMachine(); item = m.header(); art = m.kids(item)[0]; m.real_cover(art, red); m.call(tick, count=3000000)
    expect([s for s in m.styled if s[0] == m.page_window] and not m.bar_styles(), 'a window manager without a status bar: the page tints, no bar call')
    m = AlbumMachine().with_bar(); m.wm = 0; item = m.header(); art = m.kids(item)[0]; m.real_cover(art, red); m.call(tick, count=3000000)
    expect(not m.bar_styles() and [s for s in m.styled if s[0] == m.page_window], 'no window manager: the same')

    # hand-over with Now Playing (both use pod_bar_tint / pod_bar_black; Now Playing's side is covered in nowplaying.py)
    NP = 0x24000000
    tint = lambda m, w, c: m.call(PSYMS['pod_bar_tint'], a0=w, a1=c, count=200000)
    black = lambda m, w: m.call(PSYMS['pod_bar_black'], a0=w, a1=0, count=200000)
    npc = 0x00205040
    m, item, art = page(red); win = m.page_window; m.styled.clear()
    expect(tint(m, NP, npc) == 1, 'Now Playing takes the bar (Play all)')
    m.fire(BG)
    expect(len(m.bar_styles()) == 1 and m.bar_styles()[0] != BLACK, 'the album page\'s background event arriving after that does not black the bar')
    black(m, NP)
    expect(m.bar_styles()[-1] == BLACK, 'Now Playing leaving puts black')
    m.fire(FG)
    expect(m.bar_styles()[-1] == model(t), 'Back: the album page\'s foreground event tints it again')
    # the other order: the album page is in front again before Now Playing has gone
    m, item, art = page(red); m.styled.clear()
    tint(m, NP, npc); m.fire(BG); m.fire(FG); k = len(m.bar_styles())
    black(m, NP)
    expect(len(m.bar_styles()) == k and m.bar_styles()[-1] == model(t), 'Back with Now Playing leaving late: its black does not undo the album page\'s colour')
    m.fire(BG)
    expect(m.bar_styles()[-1] == BLACK, 'and the album page, backgrounded, can still restore it')
    # Play all pops nothing here: a black page under Now Playing never owns the bar, so Now Playing's black is the last word
    m, item, art = page(None); m.styled.clear(); tint(m, NP, npc); m.fire(BG); black(m, NP)
    expect(m.bar_styles()[-1] == BLACK and len(m.bar_styles()) == 2, 'a black album page under Now Playing: Now Playing leaves, black')


def tone_cache_tests(expect):
    """The tone cache (patch/common.c) and the album page's use of it: the tint at once from the cache, else from Cover Flow's file of
    the album, else from the polled stock cover file; the "no art" marker; the LRU; no writes anywhere."""
    tick = PSYMS['ah_tick']
    styles = lambda m: [s for s in m.styled if s[1] == 'normal:bg_color']
    loads = lambda m: [c[1] for c in m.calls if c[0] == 'widget_load_image']
    timers = lambda m: [c for c in m.calls if c[0] == 'timer_add']
    AlbumMachine = WatchMachine   # (local) every machine here records its write-like calls
    key = fnv(fnv(O['FNV_SEED'], 'Miles Davis'), 'Kind of Blue') or 1
    cf = art_file(key); cfurl = 'file://' + cf
    red, blue = (190, 50, 55), (40, 80, 190)
    allm = []

    def cover_flow_file(m, rgb, size=4096):
        m.present.add(cf); m.files[cf] = size; m.load_image = 0
        m.images[cfurl] = (O['ART_SIZE'], O['ART_SIZE'], bytes(rgb + (255,)) * O['ART_SIZE'] ** 2)

    # a miss with Cover Flow's file: decoded once, no timer, inserted
    m = AlbumMachine(); allm.append(m); cover_flow_file(m, red); item = m.header(); win = m.page_window
    expect(styles(m) == [(win, 'normal:bg_color', tone_word(red))] and loads(m) == [cfurl] and not timers(m) and ('widget_invalidate_force', win) in m.calls,
           'tone cache miss, Cover Flow file present: the tint is set while the header builds, from one decode of that file, no timer')
    # the next page of the album (no file, no cover): a cache hit, no decode, no timer
    m.present.discard(cf); m.files.pop(cf); m.images.clear(); m.load_image = 1; m.styled.clear()
    item = m.header(); win = m.page_window
    expect(styles(m) == [(win, 'normal:bg_color', tone_word(red))] and not loads(m) and not timers(m),
           'the album again: a cache hit sets the tint at once, no decode, no timer')
    expect(paint_corners(m, m.kids(item)[0]) and any(f[0] & 0xffffff for f in m.fills), 'and the corners are painted in it')
    # a hit wins over a changed file (the cache is the answer for the album)
    cover_flow_file(m, blue); m.styled.clear(); item = m.header()
    expect(styles(m)[0][2] == tone_word(red) and not loads(m), 'a hit does not look at the file')

    # a miss without a file: polls the stock cover, inserts when it resolves
    m = AlbumMachine(); allm.append(m); item = m.header(); art = m.kids(item)[0]; win = m.page_window
    expect(len(timers(m)) == 1 and not styles(m) and not loads(m), 'a miss without a Cover Flow file: the poll starts, the page is black')
    m.real_cover(art, blue); m.styled.clear()
    expect(m.call(tick, count=3000000) == 0 and styles(m) == [(win, 'normal:bg_color', tone_word(blue))], 'the poll resolves the tint')
    m.call(PSYMS['ah_on_destroy'], a0=win, a1=0, count=100000)
    m.images.clear(); m.load_image = 1; m.styled.clear()
    item = m.header(); win = m.page_window
    expect(styles(m) == [(win, 'normal:bg_color', tone_word(blue))] and not loads(m) and not timers(m), 'and it was inserted: the next page of the album tints at once')

    # a Cover Flow file that does not decode: the poll
    m = AlbumMachine(); allm.append(m); cover_flow_file(m, red); m.load_image = 1; m.header()
    expect(len(timers(m)) == 1 and not styles(m), 'a Cover Flow file that does not decode: the poll takes over')

    # the empty "no art" marker: black, no poll, no decode; the same on a rebuilt header
    m = AlbumMachine(); allm.append(m); m.present.add(cf); m.files[cf] = 0; item = m.header(); art = m.kids(item)[0]
    expect(not timers(m) and not styles(m) and not loads(m) and paint_corners(m, art) and all(f[0] & 0xffffff == 0 for f in m.fills),
           'the no-art marker: the page stays black, no timer, no decode')

    # the All albums card and the kill switch: the cache is not consulted
    m = AlbumMachine(); allm.append(m); cover_flow_file(m, red); m.header(card=True)
    expect(not styles(m) and not loads(m) and not timers(m), 'the All albums card: black, no decode, no timer')
    m = AlbumMachine(); allm.append(m); cover_flow_file(m, red); m.present.add(KILL); m.header()
    expect(not styles(m) and not loads(m) and not timers(m), 'the kill switch: nothing of ours')

    # an album without a title is not keyed (every untagged album would share one tone): the poll
    m = AlbumMachine(); allm.append(m); m.header(album='')
    expect(len(timers(m)) == 1 and not styles(m), 'an empty album name has no cache key: the poll')

    # the artist is classinfo + 0x20d for class 0xff14 (the stock header's rule)
    m = AlbumMachine(); allm.append(m); cover_flow_file(m, red); m.header(cls=O['CLASS_14'])
    expect(len(styles(m)) == 1 and loads(m) == [cfurl], 'class 0xff14: the artist is read from +0x20d, the same key')

    # the cache: lookups, LRU, bounds
    m = AlbumMachine(); allm.append(m)
    out = m.alloc(4)
    get = lambda k: (m.call(PSYMS['pod_tone_get'], a0=k, a1=out, count=100000), m.word(out))[0] and m.word(out)
    put = lambda k, t: m.call(PSYMS['pod_tone_put'], a0=k, a1=t, count=100000)
    n = O['TONE_CACHE_N']
    expect(n == 64 and get(5) == 0, 'the cache holds 64 tones; empty at start')
    for k in range(1, n + 1): put(k, 0xff000000 | k)
    expect(all(get(k) == 0xff000000 | k for k in range(1, n + 1)), 'every one of 64 keys is found')
    put(n + 1, 0xff0000aa)
    expect(not get(1) and get(2) and get(n + 1) == 0xff0000aa, 'the 65th evicts the least recently used (key 1)')
    put(n + 2, 0xff0000bb)
    expect(not get(3) and get(2) == 0xff000002, 'a looked-up entry (key 2) is younger: the next eviction takes key 3')
    put(2, 0xff0000cc)
    expect(get(2) == 0xff0000cc and get(4) == 0xff000004, 'the same key again replaces in place, evicting nothing')
    put(0, 0xff0000dd)
    expect(not get(0) and get(4), 'key 0 is never stored or found')
    expect(sum(1 for k in range(0, 200) if get(k)) == n, 'never more than 64 entries')
    expect(len(range(n)) * 12 <= 768, 'a tone entry is 12 bytes: 768 bytes of .scratch')

    # nothing is written to the card by any of it
    writes = [c for mm in allm for c in mm.writes]
    expect(not writes and sum(len(mm.seen) for mm in allm) > 100, f'no tint or cache path opens anything for writing ({writes})')


# The page's navbar is built by TWO stock builders, both shared with stock pages (so neither is pinned for this page alone, docs/modules/navbar.md):
# 0x526a3c (the select-mode toggles' handlers; also allmusic_page, Songs and the other song lists) makes Back, search (not for class 0xff09),
# multi-select, Now Playing; 0x524e4c (the page's own build: albumdeinfo_listitem_layout's row loop @0x5265f4, the to-foreground handler @0x5267f0;
# also album_page_init, an artist's albums) makes Back and, unless `songerinfoflag` (0xa04737) is set, multi-select and Now Playing (never search): what
# a freshly opened page shows. Select mode (0xa05a24 == 1) makes unselect, add, delete, cancel in both. Their geometry is main's (the Pod navbar's
# slots, stock select mode); the page theme draws a glass piece centred in each button: discs, and multi-select | Now Playing as one capsule.
NAV_BUILDERS = {'page build 0x524e4c': 0x524e4c, 'toggle handlers 0x526a3c': 0x526a3c}
NAV_BUILDER = 0x526a3c
# The classes 0x526a3c can run with (g_class_type = classinfo[0] after loadAlbumdetailList, @0x5268ec) and the two sibling branches it has for other
# pages' classes (0xff09, 0xf001), which a page reached by an unexpected path would take.
NAV_CLASSES = {'Albums list / grid / Cover Flow 0xf003 -> 0xff10': 0xff10, 'artist album, All songs row 0xff01 -> 0xff11': 0xff11, 'class 0xff14': 0xff14,
               'raw 0xf003': 0xf003, 'raw 0xff01': 0xff01, 'sibling branch 0xff09': 0xff09}   # (0xf001, the Songs class' branch with search and sort, is never albuminfo's)
# the window x each style's glyph must land on: the Pod navbar's right-hand glyph columns (191 / 237 / 290), the select mode's buttons centred in their stock
# 60 px slots (add 116, delete 191; cancel's glass ends where Now Playing's does), the unselect toggle's disc where Back's is (8 .. 50: centre 29)
NAV_GLYPH_X = {'search_style': 191, 'navbar_btnmulselect_style': 237, 'navbar_btnbackplayer_style': 290, 'navbar_btnadd_style': 146,
               'navbar_btndel_style': 221, 'navbar_btncancel_style': 290, 'navbar_btnunselect_style': 29, 'navbar_btnselected_style': 29, 'navbar_btnreturn_style': 29}


def nav_builder_buttons(cls=0xff10, select=0, builder=NAV_BUILDER, songer=0):
    """Run a stock navbar builder in the emulator, its widget calls modelled: the widgets it makes, in order, as (type, style, x, y, w, h) in the band."""
    m = AlbumMachine()
    m.u.mem_write(0xa04737, bytes([songer]))
    for n, slot in pod.got_slots(DEMO, ('deque_size',)).items(): m.handlers[m.word(slot)] = n   # libcstl's, through demo's own stubs
    win = m.new_widget('window', 0, 0, 0, 320, 450)
    band = m.new_widget('view', win, *mod_ipodrows.NAV_BAND)
    m.wname[band] = 'navigationbar_view'; m.widgets['navigationbar_view'] = band
    m.setword(pod.DATA['PDEQ_SHOWLIST'][0], m.new_deque([m.record(album='A', artist='B', title='T', name='1.flac', path='/mnt/mmc/m/1.flac', rid=1)]))
    m.setword(pod.DATA['G_CLASS_TYPE'][0], cls)
    m.setword(0xa05a24, select)
    try: m.call(builder, a0=win, count=3000000)
    except Exception as e: raise AssertionError(f'builder died: pc {m.u.reg_read(UC_MIPS_REG_PC):#x} ra {m.u.reg_read(UC_MIPS_REG_RA):#x} {e} calls {m.calls[-6:]} styles {list(m.style.values())[-4:]}')
    out = []
    for c in m.kids(band):
        x, y, w, h = m.geo(c)
        out.append((m.wtype.get(c), m.style.get(c), x, y, w, h))
    return out


def nav_tests(expect):
    """Both builders run in the emulator for every select state, `songerinfoflag` and class; every button they make (main's geometry, which this page
    must not change: the builders are shared with stock pages) gets a glass piece from the page theme centred in the button with no rounding (as wide,
    or multi-select's 4 px wider), whose glyph lands on its target column (NAV_GLYPH_X); the piece fits the button's height and the band. Wherever
    multi-select and Now Playing are made, their glass is ONE capsule (mod_icons.AH_CAPSULE: multi-select's ends where Now Playing's starts), and
    search's disc ends before it."""
    cases = [(f'{bn}, normal, songerinfoflag {s}', dict(builder=b, songer=s)) for bn, b in NAV_BUILDERS.items() for s in (0, 1) if b == 0x524e4c or s == 0]
    cases += [(f'0x526a3c, class {label}', dict(cls=cls)) for label, cls in NAV_CLASSES.items()]
    cases += [(f'{bn}, select mode', dict(builder=b, select=1)) for bn, b in NAV_BUILDERS.items()]
    sets = {}
    band_h = mod_ipodrows.NAV_BAND[3]
    for label, kw in cases:
        bs = [b for b in nav_builder_buttons(**kw) if b[0] == 'button']
        bad, glass = [], {}
        for _, style, x, y, w, h in bs:
            if style not in mod_ipodrows.NAV_STYLES: bad.append((style, 'no glass style')); continue
            rest, down, icon_at, off = mod_ipodrows.NAV_STYLES[style]
            iw, x0, x1, cx, _g, _cap = {**mod_icons.AH_NAV_PIECES, 'ah_nav_sel': (50, 8, 50, 29, None, None)}[rest]
            if icon_at == 1:   # Back: icon_at left, the icon centred in a h x h square (x_offset +4: the Pod navbar's disc columns)
                gx = x + h // 2 + off
            else:   # canvas_draw_icon_in_rect: the image at its own size on the rect's centre
                left = x + w // 2 - iw // 2 if (w - iw) % 2 == 0 and iw - w in (0, 4) else None
                gx = None if left is None else left + cx
                if left is not None: glass[style] = (left + x0, left + x1)
            if gx != NAV_GLYPH_X[style] or h < mod_icons.GLASS_H or y + h > band_h or (iw is not None and icon_at != 1 and x + w // 2 - iw // 2 + x1 > 320):
                bad.append((style, x, y, w, h, gx))
        ms, np_, se = (glass.get(s) for s in ('navbar_btnmulselect_style', 'navbar_btnbackplayer_style', 'search_style'))
        if ms or np_:
            if not (ms and np_ and ms[1] == np_[0] and (ms[0], np_[1]) == mod_icons.AH_CAPSULE): bad.append(('capsule', ms, np_))
            if se and se[1] >= ms[0]: bad.append(('search over the capsule', se, ms))
        sets[label] = [b[1].replace('navbar_btn', '').replace('_style', '') for b in sorted(bs, key=lambda b: b[2]) if b[1] != 'navbar_btnreturn_style']
        expect(bool(bs) and not bad, f'navbar builder, {label}: buttons {sets[label]} each get a glass piece centred in the button, glyph on its column, multi-select | Now Playing one capsule {mod_icons.AH_CAPSULE}; off: {bad}')
    expect(sets['page build 0x524e4c, normal, songerinfoflag 0'] == ['mulselect', 'backplayer'] and sets['page build 0x524e4c, normal, songerinfoflag 1'] == []
           and all(len(sets[f'0x526a3c, class {l}']) == (2 if '0xff09' in l else 3) for l in NAV_CLASSES)
           and sets['toggle handlers 0x526a3c, select mode'] == sets['page build 0x524e4c, select mode'] == ['unselect', 'add', 'del', 'cancel'],
           'the sets: fresh page multi-select + Now Playing or none; toggle builder search (not 0xff09) + multi-select + Now Playing; select mode unselect, add, delete, cancel')


def album_tests(expect, page, cover_asset):
    # ------------------------------------------------------------------ the hook is installed as pinned
    built = open(DEMO, 'rb').read()
    w = lambda a: struct.unpack_from('<I', built, pod.fileoff(built, a))[0]
    hook = MANIFEST['hook_albuminfo']
    expect(hook['addr'] == HEADER_BUILDER == 0x526264 and hook['target'] == PSYMS['m1plus_albuminfo_header'],
           'the manifest records the album header hook and its target')
    expect(pod.ALBUMINFO_HEADER_PROLOGUE == (0x3c1c004e, 0x279cdc6c, 0x0399e021),
           'the hook pins the three PIC prologue words of albuminfo_listitem0_layout')
    expect((w(HEADER_BUILDER), w(HEADER_BUILDER + 4)) == (pod.j(PSYMS['m1plus_albuminfo_header']), 0)
           and w(HEADER_BUILDER + 8) == pod.ALBUMINFO_HEADER_PROLOGUE[2],
           'the built demo has `j m1plus_albuminfo_header; nop` over the first two prologue words')
    expect(w(HDR_ART) == 0x241300a0, f'the header cover is rendered at 160 px ({w(HDR_ART):#010x}; stock addiu s3, zero, 0x64)')
    expect(O['AH_ART'] == 160, 'and the header shows it 1:1 (AH_ART)')
    expect(w(HDR_ART) & 0xffff == O['AH_ART'], 'the cover word is AH_ART itself')
    # the page is reached by the album page's builders only: the hook's only callers in stock
    stock_demo = open(os.path.join(paths.find_stock() or os.path.join(os.path.dirname(WORK), 'stock'), 'rootfs', pod.DEMO), 'rb').read()
    sw = struct.unpack_from('<III', stock_demo, pod.fileoff(stock_demo, HEADER_BUILDER))
    expect(sw == pod.ALBUMINFO_HEADER_PROLOGUE, 'stock has the pinned prologue at the hook site')

    # ------------------------------------------------------------------ stock first, then ours
    m = AlbumMachine()
    item = m.header()
    kids = m.kids(item)
    expect(len(kids) == 6, f'the header holds the stock four widgets and the two added ({len(kids)})')
    art, title, artist, play, meta, shuf = kids
    order = [c[1] for c in m.calls if c[0] == 'create']
    expect(order == ['image', 'hscroll_label', 'hscroll_label', 'button', 'hscroll_label', 'button'],
           f'stock builds its header first (image, title, artist, button), then ours (the year line, Shuffle; the corners are painted, no widgets) ({order})')
    expect(m.wname.get(art) == 'img_albumcover_m', 'the cover keeps its stock name (the app looks it up)')
    draws = [c[2] for c in m.calls if c[0] == 'image_set_draw_type' and c[1] == art]
    expect(draws == [O['IMAGE_SCALE_AUTO'], O['IMAGE_DRAW_CENTER']], f'stock scales the cover (scale-auto), the hook draws it centred at its own size ({draws})')
    geo = m.geo
    A = O
    expect(geo(art) == (A['AH_ART_X'], A['AH_ART_Y'], A['AH_ART'], A['AH_ART']), f'cover {geo(art)}')
    expect(geo(title) == (A['AH_TEXT_X'], A['AH_TITLE_Y'], A['AH_TEXT_W'], A['AH_TITLE_H'])
           and geo(artist) == (A['AH_TEXT_X'], A['AH_ARTIST_Y'], A['AH_TEXT_W'], A['AH_ARTIST_H'])
           and geo(meta) == (A['AH_TEXT_X'], A['AH_META_Y'], A['AH_TEXT_W'], A['AH_META_H']),
           'title, artist and the year line centred under the cover')
    expect(geo(shuf) == (A['AH_SHUF_X'], A['AH_BTN_Y'], A['AH_SHUF_W'], A['AH_BTN_H'])
           and geo(play) == (A['AH_PLAY_X'], A['AH_BTN_Y'], A['AH_PLAY_W'], A['AH_BTN_H']),
           f'the round Shuffle then the Play all pill ({geo(shuf)}, {geo(play)})')
    R = A['AH_CORNER']; ax, ay, aw = A['AH_ART_X'], A['AH_ART_Y'], A['AH_ART']
    expect(geo(item)[2:] == (310, A['AH_HDR_H']),
           f'the header item is AH_HDR_H high at the list width ({geo(item)})')
    # the layout numbers: centred on the screen (x 160, the item starts at screen x 0), not on the item's 155
    mid2 = lambda x, w: 2 * x + w          # twice the centre
    expect(A['AH_MID'] == 160 and 2 * A['AH_MID'] == 320, 'the centre is the screen\'s')
    expect(all(mid2(*g) == 2 * A['AH_MID'] for g in ((ax, aw), (A['AH_TEXT_X'], A['AH_TEXT_W']),
                                                      (A['AH_SHUF_X'] + (A['AH_SHUF_W'] - A['AH_DISC']) // 2,
                                                       A['AH_PLAY_X'] + A['AH_PLAY_W'] - A['AH_SHUF_X'] - (A['AH_SHUF_W'] - A['AH_DISC']) // 2))),
           'cover, the three text lines and the button pair as drawn (the disc and the pill) are all centred on x 160')
    expect(A['AH_PLAY_X'] == A['AH_SHUF_X'] + (A['AH_SHUF_W'] + A['AH_DISC']) // 2 + A['AH_GAP']
           and A['AH_DISC'] == 38 and A['AH_PILL_H'] == 40 and A['AH_PLAY_W'] == 180 and A['AH_SHUF_X'] + A['AH_SHUF_W'] <= A['AH_PLAY_X'],
           'the pill follows the drawn disc with AH_GAP between; the disc is 38 px, the pill 180x40, their touch rectangles do not overlap')
    expect(A['AH_TEXT_X'] >= 0 and A['AH_TEXT_X'] + A['AH_TEXT_W'] <= 310 and A['AH_PLAY_X'] + A['AH_PLAY_W'] <= 310,
           'everything lies inside the 310 px item (nothing is clipped, the item is not widened)')
    expect(A['AH_ART_Y'] + A['AH_ART'] < A['AH_TITLE_Y'] and A['AH_TITLE_Y'] + A['AH_TITLE_H'] <= A['AH_ARTIST_Y']
           and A['AH_ARTIST_Y'] + A['AH_ARTIST_H'] <= A['AH_META_Y'] and A['AH_META_Y'] + A['AH_META_H'] <= A['AH_BTN_Y']
           and A['AH_BTN_Y'] + A['AH_BTN_H'] < A['AH_HDR_H'] and A['AH_ART_Y'] == A['AH_NAV_TOP'] + 6,
           'cover, the three lines, the buttons and the track rows follow one another without overlap')
    expect(A['AH_BTN_H'] >= 44 and A['AH_SHUF_W'] >= 44 and A['AH_PLAY_W'] >= 44 and A['AH_DISC'] < A['AH_SHUF_W'] and A['AH_PILL_H'] < A['AH_BTN_H'] and A['AH_CORNER'] == 10 and A['AH_ART_X'] + A['AH_ART'] // 2 == A['AH_MID'],
           'both touch rectangles are at least 44 px each way (the disc and the pill are drawn inside them); the corners are 10 px')
    expect(A['AH_TITLE_H'] >= 22 and A['AH_ARTIST_H'] >= 18 and A['AH_META_H'] >= 15,
           'every line box holds its font (22 / 18 / 15 px)')
    # the vertical rhythm, measured on the ink of the shipped font (tools/ah_ink.py): the two outer gaps are equal, the two text gaps are equal
    import ah_ink
    gp = ah_ink.gaps(ah_ink.font(WORK), O)
    expect(gp == {'cover-title': 16, 'title-artist': 9, 'artist-year': 9, 'year-buttons': 16},
           f'ink gaps: cover to title capitals, title baseline to artist capitals, artist baseline to year digits, year baseline to the pill {gp}')
    expect(gp['cover-title'] == gp['year-buttons'] and gp['title-artist'] == gp['artist-year'] and gp['title-artist'] < gp['cover-title'],
           'equal outer gaps, equal text gaps, the text block tighter than its frame')
    expect(O['AH_HDR_H'] == O['AH_BTN_Y'] + O['AH_BTN_H'] + ah_ink.BOTTOM and O['AH_TINT_ROWS'] == O['AH_HDR_H'],
           'the header ends 8 px under the touch rectangles; the gradient ramp ends with it')
    import mod_ipodrows
    expect(O['AH_NAV_H'] == 44 and mod_ipodrows.NAV_H == O['AH_NAV_H'] and mod_icons.GLASS_H <= 44, 'the shared builder\'s buttons are 44 px (>= the glass disc, >= the 44 px touch size)')
    # long titles: a title that fits is drawn centred; a longer one (Latin or CJK) is longer than the box and relies on the
    # label's ellipsis/scroll, which the stock builder sets and the test above keeps
    font = Ttf(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/fonts/default.ttf'))
    tw = lambda s, px: StbText(font, px).layout(s)[1]
    expect(tw('Kind of Blue', 22) < A['AH_TEXT_W'] and tw('Miles Davis', 18) < A['AH_TEXT_W'],
           'a normal title and artist fit the 286 px box and are centred')
    expect(tw('The Rise and Fall of Ziggy Stardust and the Spiders from Mars', 22) > A['AH_TEXT_W']
           and tw('周杰伦的第一张正式大型专辑重制版豪华纪念版', 22) > A['AH_TEXT_W'],
           'a long Latin title and a long CJK title are wider than the box: they scroll and end in an ellipsis (stock label flags)')
    expect(m.style.get(play) == 'btn_ahplay_style' and m.style.get(shuf) == 'btn_ahshuf_style' and m.style.get(meta) == 'srlabel_ahmeta_style'
           and m.style.get(title) == 'srlabel_ahtitle_style' and m.style.get(artist) == 'srlabel_ahartist_style',
           'the pill, the round button and the three lines have their own page styles')
    expect(m.texts.get(play) == 'Play all' and not m.texts.get(shuf), 'the pill reads Play all; Shuffle is a glyph, no text')
    expect(m.props.get((meta, 'sensitive')) == 0, 'the year line is decoration: a drag over it scrolls the list')
    expect(any(c[0] == 'hscroll_label_set_ellipses' and c[1] == meta for c in m.calls),
           'a long line ends in an ellipsis')
    expect(all(any(c[0] == 'hscroll_label_set_ellipses' and c[1] == t and c[2] == 1 for c in m.calls) for t in (title, artist)),
           'stock gives the title and the artist ellipses (a long one scrolls and ends in an ellipsis), kept')
    expect(m.bound.get(art, {}).get(O['EVT_AFTER_PAINT']) == (PSYMS['ah_on_art_paint'], art) and m.style.get(item) == 'list_item_ahhead_style',
           'the cover paints its own corners (after-paint); the header item is the transparent style')
    expect(('widget_off_by_func', play, O['EVT_CLICK'], O['AH_STOCK_PLAY'], item) in m.calls and m.bound.get(play, {}).get(O['EVT_CLICK'], (None,))[0] == PSYMS['ah_on_play'],
           'the stock Play all handler (it stays on the page) is taken off the stock button, ours is bound in its place')
    expect(m.bound.get(shuf, {}).get(O['EVT_CLICK'], (None,))[0] == PSYMS['ah_on_shuffle'],
           'Shuffle is bound to its handler on click')

    # ------------------------------------------------------------------ the year line
    for tracks, year, card, want in ((6, 1959, False, '1959 \xc2\xb7 6 tracks'), (1, 1959, False, '1959 \xc2\xb7 1 track'),
                                     (8, 0, False, '8 tracks'), (1, 0, False, '1 track'),
                                     (24, 1959, True, '24 tracks'), (3, 3999, False, '3 tracks')):
        m = AlbumMachine(); item = m.header(tracks=tracks, year=year, card=card)
        expect(m.texts.get(m.kids(item)[4]) == want, f'the year line for {tracks} tracks, year {year}, card {card}: {want!r} (got {m.texts.get(m.kids(item)[4])!r})')
    # the All albums card (class 0xff11, no year) gets the same header
    m = AlbumMachine(); item = m.header(tracks=24, year=1959, card=True, cls=0xff11)
    m0 = AlbumMachine(); item0 = m0.header()
    expect(len(m.kids(item)) == 6 and [m.geo(k) for k in m.kids(item)] == [m0.geo(k) for k in m0.kids(item0)]
           and m.geo(item) == m0.geo(item0), 'the All albums card has the album header: same widgets, same geometry, a count line without a year')
    # the first track that carries a year is the album's
    m = AlbumMachine(); m.header(tracks=4, year=0)
    for i, r in enumerate(m.tracks): m.setword(r + O['REC_YEAR'], 0 if i < 2 else 1971)
    parent = m.new_widget('scroll_view', 0, 0, 0, 310, 400)
    item = m.new_widget('list_item', parent, 0, 0, 0, 100)
    m.props[(item, 'w')] = 310
    m.call(HEADER_BUILDER, a0=item, count=2000000)
    expect(m.texts.get(m.kids(item)[4]) == '1971 \xc2\xb7 4 tracks', 'the first track with a year gives the album its year')

    # ------------------------------------------------------------------ failures leave stock alone
    # kill switch: the stock header exactly
    m = AlbumMachine(); m.present.add(KILL)
    item = m.header()
    kids = m.kids(item)
    got = [m.geo(k) for k in kids]
    expect(len(kids) == 4 and got == [STOCK_HEADER[k] for k in ('cover', 'title', 'artist', 'button')],
           f'with the kill switch the header is the stock one ({got})')
    expect(m.geo(item)[3] == 100 and m.style.get(kids[3]) == 'btn_imgplayall_style' and not m.texts.get(kids[3]),
           'stock size, stock Play all style, no text added')
    # not the header stock builds: nothing is moved, nothing is added
    def hand_built(kinds):
        mm = AlbumMachine()
        parent = mm.new_widget('scroll_view', 0, 0, 0, 310, 400)
        it = mm.new_widget('list_item', parent, 0, 0, 0, 100)
        mm.props[(it, 'w')] = 310
        for kind, g in zip(kinds, (STOCK_HEADER['cover'], STOCK_HEADER['title'], STOCK_HEADER['artist'], STOCK_HEADER['button'],
                                   (0, 0, 10, 10))):
            mm.new_widget(kind, it, *g)
        mm.setword(pod.DATA['PDEQ_SHOWLIST'][0], mm.new_deque([]))
        mm.call(PSYMS['ah_restyle'], a0=it, count=200000)
        return mm, it
    mm, it = hand_built(('image', 'hscroll_label', 'hscroll_label', 'button'))
    expect(len(mm.kids(it)) == 6, 'the stock shape is restyled (control)')
    for kinds, why in ((('image', 'hscroll_label', 'hscroll_label'), 'three children'),
                       (('image', 'hscroll_label', 'hscroll_label', 'button', 'view'), 'five children'),
                       (('image', 'hscroll_label', 'label', 'button'), 'the artist is not an hscroll_label'),
                       (('view', 'hscroll_label', 'hscroll_label', 'button'), 'the cover is not an image'),
                       (('image', 'hscroll_label', 'hscroll_label', 'image'), 'the button is not a button')):
        mm, it = hand_built(kinds)
        expect(len(mm.kids(it)) == len(kinds) and mm.geo(it)[3] == 100 and not mm.style
               and all(mm.geo(k) == g for k, g in zip(mm.kids(it), (STOCK_HEADER['cover'], STOCK_HEADER['title'],
                                                                      STOCK_HEADER['artist'], STOCK_HEADER['button'], (0, 0, 10, 10)))),
               f'{why}: untouched')
    mm = AlbumMachine(); mm.call(PSYMS['ah_restyle'], a0=0, count=200000)
    expect(not mm.calls, 'no item: nothing happens')
    for fail, made in (('button', 1), ('hscroll_label', 1)):   # the new widgets that were made before the check
        mm = AlbumMachine()
        parent = mm.new_widget('scroll_view', 0, 0, 0, 310, 400)
        it = mm.new_widget('list_item', parent, 0, 0, 0, 100)
        mm.props[(it, 'w')] = 310
        for kind, g in zip(('image', 'hscroll_label', 'hscroll_label', 'button'), STOCK_HEADER.values()):
            mm.new_widget(kind, it, *g)
        mm.setword(pod.DATA['PDEQ_SHOWLIST'][0], mm.new_deque([]))
        n_before = len(mm.kids(it))
        mm.create_fail = {fail}
        mm.call(PSYMS['ah_restyle'], a0=it, count=200000)
        expect(len(mm.kids(it)) == n_before and mm.geo(it)[3] == 100 and not mm.style
               and len(mm.destroyed) == made, f'a failing {fail} create: the {made} new widgets that were made are destroyed ({len(mm.destroyed)}), the header stays stock')
    # the stock functions' own results are what the hook returns through: the hook has no return value
    # (albuminfo_listitem0_layout is void); the trampoline resumes stock at the fourth word
    expect(PSYMS['stock_albuminfo_header_trampoline'] >= pod.BASE, 'the trampoline is in the payload')
    tr = [struct.unpack_from('<I', open(os.path.join(BUILD, 'patch.bin'), 'rb').read(), PSYMS['stock_albuminfo_header_trampoline'] - pod.BASE + 4 * i)[0]
          for i in range(4)]
    expect(tr[2] == pod.j(HEADER_BUILDER + 12) and tr[3] == 0, 'the trampoline jumps to the stock function past its 3-word prologue')

    # ------------------------------------------------------------------ Shuffle: the stock Play all sequence
    shuffle = PSYMS['ah_on_shuffle']

    def played(m): return [c for c in m.calls if c[0] == 'navigator_to_with_context' and c[1] == 'playing_page']   # (.., 'playing_page', index, class, mode)
    play_all = PSYMS['ah_on_play']
    m = AlbumMachine(); m.header(tracks=6)
    m.stock_songlist = True
    starts = set()
    for clock in range(1, 41):
        m.mode = 0; m.clock = clock * 7919; m.call(shuffle, count=60000000)
        sp = played(m); starts.add(sp[0][2])
    expect(len(starts) >= 4 and starts <= set(range(6)), f'the first track is drawn at random from the album ({sorted(starts)})')
    expect(sp[0][3:] == (O['CLASS_ALBUM_TRACKS'], O['PLAY_MODE']) and len(m.played[0]) == 6,
           'the whole album is queued with its class and the stock mode argument, as a track tap does')
    seq = [c[0] for c in m.calls if c[0] in ('access', 'loadSongList', 'mclSetPlayMode', 'navigator_to_with_context', 'deque_destroy')]
    expect(seq == ['access', 'loadSongList', 'mclSetPlayMode', 'navigator_to_with_context', 'deque_destroy'],
           f'access, resolve, mode, open Now Playing, free ({seq})')
    expect(m.mode == O['MODE_SHUFFLE'] and ('dmrSendPlayMode', O['MODE_SHUFFLE']) in m.calls and ('notifyPlayMode',) in m.calls
           and ('write_int_config', O['MODE_SHUFFLE'], 'PLAYSET', 'PLAYMODE') in m.calls,
           'Shuffle sets the stock play mode the way the Play settings page does')
    expect('start_player' not in m.names() and 'navigator_back' not in m.names() and 'window_close' not in m.names(),
           'Now Playing\'s init starts the player (as after a track tap); with songerinfoflag clear nothing is popped')
    expect(not any(n in m.names() for n in ('timer_add', 'pthread_create', 'window_open')), 'a start leaves no timer, thread or page behind')
    m.mode = O['MODE_SHUFFLE']; m.call(shuffle, count=60000000)
    expect(not any(c[0] in ('mclSetPlayMode', 'write_int_config') for c in m.calls) and played(m), 'already in Shuffle: nothing is written')
    # Play all: the album's first track in an in-order mode, the same way into Now Playing
    m = AlbumMachine(); m.header(tracks=6); m.stock_songlist = True; m.mode = 3
    m.call(play_all, count=60000000)
    expect(played(m) == [('navigator_to_with_context', 'playing_page', 0, O['CLASS_ALBUM_TRACKS'], O['PLAY_MODE'])] and len(m.played[0]) == 6
           and m.played[1] == 0 and m.mode == 3 and not any(c[0] in ('mclSetPlayMode', 'write_int_config', 'start_player') for c in m.calls),
           'Play all queues the album from its first track, opens Now Playing like a track tap and keeps Repeat all (nothing written)')
    expect([c[0] for c in m.calls if c[0] in ('access', 'loadSongList', 'navigator_to_with_context', 'deque_destroy')]
           == ['access', 'loadSongList', 'navigator_to_with_context', 'deque_destroy'], 'access, resolve, open, free')
    for before, after in ((0, 0), (1, 0), (2, 0), (3, 3)):
        m = AlbumMachine(); m.header(tracks=6); m.stock_songlist = True; m.mode = before
        m.call(play_all, count=60000000)
        wrote = before != after
        expect(played(m) and m.mode == after and (('write_int_config', after, 'PLAYSET', 'PLAYMODE') in m.calls) == wrote
               and (('dmrSendPlayMode', after) in m.calls) == wrote,
               f'Play all from mode {before}: mode {after} (Shuffle and Repeat one become List play, so Now Playing plays the album in order)')
    m = AlbumMachine(); m.header(tracks=6); m.stock_songlist = True; m.mode = 0
    m.call(shuffle, count=60000000); m.call(play_all, count=60000000)
    expect(m.mode == O['MODE_ORDER'] and played(m)[-1][2] == 0, 'Shuffle, then Play all: the album from its first track in List play, not still shuffled')
    m = AlbumMachine(); m.header(tracks=3); m.stock_songlist = True
    for p in list(m.present):
        if p.startswith('/mnt/mmc/m/'): m.present.discard(p)
    m.call(play_all, count=60000000)
    expect(not played(m) and ('toast', 'Storage unavailable', O['MSGINFO_KIND'], O['MSGINFO_MS']) in m.calls and 'navigator_back' not in m.names(),
           'Play all with the first track missing says so and stays on the page')
    m = AlbumMachine(); m.header(tracks=3); m.stock_songlist = True
    for t in m.tracks: m.setword(t + O['REC_TYPE'], 4)
    m.call(play_all, count=60000000)
    expect(not played(m) and 'deque_destroy' in m.names() and 'navigator_back' not in m.names(),
           'Play all on a queue that does not resolve starts nothing, pops nothing and frees the queue')
    m = AlbumMachine(); m.header(tracks=0); m.stock_songlist = True; m.call(play_all, count=60000000)
    expect(not played(m) and 'loadSongList' not in m.names(), 'Play all on an empty list does nothing')
    # a missing file, an empty list, a queue that does not resolve: nothing starts, nothing changes
    m = AlbumMachine(); m.header(tracks=3); m.stock_songlist = True
    for p in list(m.present):
        if p.startswith('/mnt/mmc/m/'): m.present.discard(p)
    m.mode = 0; m.call(shuffle, count=60000000)
    expect(not played(m) and m.mode == 0 and ('toast', 'Storage unavailable', O['MSGINFO_KIND'], O['MSGINFO_MS']) in m.calls,
           'a missing track starts nothing and says so')
    m = AlbumMachine(); m.header(tracks=0); m.stock_songlist = True
    m.call(shuffle, count=60000000)
    expect(not played(m) and 'loadSongList' not in m.names(), 'an empty list starts nothing')
    m = AlbumMachine(); m.header(tracks=3); m.stock_songlist = True
    for t in m.tracks: m.setword(t + O['REC_TYPE'], 4)   # loadSongList only takes songs: nothing to queue
    m.mode = 0; m.call(shuffle, count=60000000)
    expect(not played(m) and m.mode == 0 and 'mclSetPlayMode' not in m.names() and 'deque_destroy' in m.names(),
           'a queue that does not resolve starts nothing, changes nothing and is freed')
    # an artist's album and the All albums card: the page's class goes through (0xff11)
    m = AlbumMachine(); m.header(tracks=6, cls=0xff11); m.stock_songlist = True
    m.clock = 99991; m.call(shuffle, count=60000000)
    expect(played(m) and played(m)[0][3] == 0xff11 and any(c[0] == 'loadSongList' and c[3] == 0xff11 for c in m.calls),
           'an artist album and the All albums card queue with class 0xff11')
    stack_tests(expect)
    nav_tests(expect)
    tint_tests(expect)
    tone_cache_tests(expect)
    bar_tests(expect)

    # ------------------------------------------------------------------ hit tests (demo's widget_find_target)
    m = AlbumMachine(); item = m.header()
    art, title, artist, play, meta, shuf, *masks = m.kids(item)
    nm = {art: 'cover', title: 'title', artist: 'artist', play: 'btn_play', meta: 'meta', shuf: 'btn_shuffle', item: 'header'}
    nm.update({c: 'mask' for c in masks})
    def node_of(h):
        gx, gy, gw, gh = m.geo(h)
        flags = F_ENABLE | F_VISIBLE | (F_SENSITIVE if m.props.get((h, 'sensitive'), 1) not in (0,) else 0)
        n = Node(nm.get(h, f'w{h:x}'), gx, gy, gw, gh, flags)
        n.children = [node_of(c) for c in m.kids(h)]
        return n
    hdr = node_of(item)
    hdr.w = 310
    # the page as the window manager sees it: the built asset's order (tint, list, navbar band LAST) with the buttons the stock builder makes,
    # at the built (pinned) immediates, in its creation order (search, title label, multi-select, Now Playing, Back)
    sty = {'btn_cancel': 'btn_multi', 'navbar_btnreturn_style': 'btn_back', 'search_style': 'btn_search', 'navbar_btnmulselect_style': 'btn_multi', 'navbar_btnbackplayer_style': 'btn_nowplaying'}
    def nav_buttons(builder=0x526a3c, songer=0):   # the widgets a stock builder makes (emulated), in its creation order: the topmost last
        return [Node(sty.get(st, 'nav_title'), x, y, w, h) for _, st, x, y, w, h in nav_builder_buttons(builder=builder, songer=songer)]
    def page_window(scroll=0, rows=0, builder=0x526a3c, songer=0):
        h = node_of(item); h.w = 310; h.y = -scroll
        body = [h] + [Node(f'track{i}', 0, O['AH_HDR_H'] - scroll + 64 * i, 310, 64) for i in range(rows)]
        a = asset_tree(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/albuminfo_page.bin'))
        node(a, 'albuminfo_scrollview').children = body
        node(a, 'navigationbar_view').children = nav_buttons(builder, songer)
        return a
    window = page_window()
    expect([c.name for c in window.children] == ['img_ah_tint', 'albuminfo_listview', 'navigationbar_view'], 'the hit-test tree is the built asset\'s: the band is the top child')
    top = 0   # the list starts at the window's top: header rows are window rows
    by, bh, sx, sw, px, pw = O['AH_BTN_Y'], O['AH_BTN_H'], O['AH_SHUF_X'], O['AH_SHUF_W'], O['AH_PLAY_X'], O['AH_PLAY_W']
    ax, ay, aw = O['AH_ART_X'], O['AH_ART_Y'], O['AH_ART']
    for x, y, want in ((sx + sw // 2, by + bh // 2, 'btn_shuffle'), (px + pw // 2, by + bh // 2, 'btn_play'),
                       (sx + 1, by + 1, 'btn_shuffle'), (sx + sw - 2, by + bh - 2, 'btn_shuffle'),
                       (px + 1, by + 1, 'btn_play'), (px + pw - 2, by + bh - 2, 'btn_play'),
                       (ax + aw // 2, ay + aw // 2, 'cover'),
                       (ax + 2, ay + 2, 'cover'), (ax + aw - 3, ay + aw - 3, 'cover'),         # under a corner mask: the mask is insensitive, the cover takes it
                       (O['AH_MID'], O['AH_TITLE_Y'] + 5, 'title'), (O['AH_MID'], O['AH_ARTIST_Y'] + 5, 'artist'),
                       (O['AH_MID'], O['AH_META_Y'] + 5, 'header'),             # the year line lets the touch through to the header
                       (sx + sw + O['AH_GAP'] // 2, by + bh // 2, 'header'),    # the gap between the buttons
                       (sx - 4, by + bh // 2, 'header'), (px + pw + 4, by + bh // 2, 'header'),   # left and right of the pair
                       (O['AH_MID'], by - 3, 'header'),                         # above the buttons
                       (150, O['AH_HDR_H'] - 4, 'header')):
        got = stock_target(m, window, x, top + y)
        expect(got[-1] == want and 'albuminfo_scrollview' in got, f'a touch at ({x},{y}) lands on {want} ({got})')
    # the floating controls on main's slots (the stock builders' buttons, not moved by this page): each button's whole rectangle, the band's dead zone, the rows below
    NB, BAND_H = O['AH_NAV_H'], O['AH_NAV_BAND_H']
    title_w = max((c.w + c.x for c in node(window, 'navigationbar_view').children if c.name == 'nav_title'), default=0)   # the stock label's right edge (not pinned: shared with Hi-Res etc.)
    slots = {'btn_back': (3, 80), 'btn_search': (168, 46), 'btn_multi': (214, 46), 'btn_nowplaying': (262, 60)}
    bad = []
    for name, (bx, bw) in slots.items():
        lo = max(bx + 1, title_w + 1) if name == 'btn_search' else bx + 1   # the stock title label (created after search) lies over its left edge
        for dx, dy in ((lo, 1), (min(bx + bw - 2, 319), 1), (lo, NB - 2), (min(bx + bw - 2, 319), NB - 2), (min(bx + bw // 2, 319), NB // 2)):
            got = stock_target(m, window, dx, dy)
            if got[-1] != name: bad.append((name, dx, dy, got[-1]))
    expect(not bad, f'every corner and the centre of Back, search, multi-select and Now Playing (the toggle builder\'s, {NB} px high) lands on that button ({bad[:3]})')
    expect(title_w <= 168 + 46 - 1 and stock_target(m, window, 169, NB // 2)[-1] in ('btn_search', 'nav_title'),
           f'the stock title label (to x {title_w}, 147 wide, not pinned: shared with the Songs-type pages) lies over the first columns of search\'s slot only')
    for songer, want in ((0, {'btn_multi', 'btn_nowplaying', 'btn_back'}), (1, {'btn_back'})):   # a freshly opened page: the page's own builder 0x524e4c (50 px buttons)
        wf = page_window(0, 0, 0x524e4c, songer)
        got = {name: stock_target(m, wf, bx + bw // 2, 22)[-1] for name, (bx, bw) in slots.items()}
        expect({n for n, g in got.items() if g == n} == want, f'a fresh page (page builder, songerinfoflag {songer}): the buttons it makes are hit at their slots, the absent ones leave the band ({got})')
    gap_hits = {stock_target(m, window, x, yy)[-1] for x in range(88, 160, 9) for yy in (2, 40)}
    expect(gap_hits <= {'navigationbar_view', 'nav_title'}, f'the strip of the band between Back and the first button is the band\'s (or the stock title label\'s), nothing under it ({gap_hits})')
    expect(all(stock_target(m, window, x, BAND_H)[-1] == 'header' for x in (20, 60, 250, 300)),
           'right below the band the header (the list) takes touches again, under Back and the buttons too')
    for scroll in (150, 230, 300):   # scrolled: rows pass under the band; those just below it are still reached
        w2 = page_window(scroll, rows=3)
        rows_at = [(i, O['AH_HDR_H'] - scroll + 64 * i) for i in range(3)]
        hits = []
        for i, ry in rows_at:
            y = max(ry, BAND_H + 1) + 3
            if y < ry + 64 and y < CLIENT_H: hits.append((i, y, stock_target(m, w2, 200, y)[-1]))
        expect(hits and all(g == f'track{i}' for i, y, g in hits), f'scrolled {scroll}: the rows below the band take touches ({hits})')
        under = [(y, stock_target(m, w2, 30, y)[-1]) for y in range(0, NB, 9)]
        expect(all(g == 'btn_back' for y, g in under), f'scrolled {scroll}: Back keeps its touches over the rows that pass under it ({under})')
    # the fallback: the hook does not run (the kill switch /mnt/mmc/m1plus-off, or the header is not the stock shape). The asset, the page theme and the
    # builder's immediates are data, so the floating controls stay; the header is stock's (a 100 px item at the list's top: cover 100x100 at (0, 0),
    # title (108, 10, 200, 20), artist (108, 30, 200, 18), Play all (108, 62, 90, 28), albuminfo_listitem0_layout @0x526264, album_page_init+0x174 / +0x248)
    stock_hdr = Node('header', 0, 0, 310, 100, children=[Node('cover', 0, 0, 100, 100), Node('title', 108, 10, 200, 20), Node('artist', 108, 30, 200, 18),
                                                         Node('btn_playall', 108, 62, 90, 28)])
    fb = page_window(0, rows=2)
    sv_fb = node(fb, 'albuminfo_scrollview'); sv_fb.children = [stock_hdr] + [Node(f'track{i}', 0, 100 + 64 * i, 310, 64) for i in range(2)]
    got = {n: stock_target(m, fb, x, y)[-1] for n, (x, y) in {'back': (30, 22), 'capsule': (262 + 30, 22), 'playall': (150, 76),
                                                              'row0': (150, 130), 'cover': (60, 70)}.items()}
    expect(got == {'back': 'btn_back', 'capsule': 'btn_nowplaying', 'playall': 'btn_playall', 'row0': 'track0', 'cover': 'cover'},
           f'without the hook (stock header) Back and the capsule work, Play all (y 62 .. 90, below the band that ends at y {BAND_H}) and the rows are reached ({got})')
    expect(BAND_H <= 62, 'the stock Play all button lies wholly below the band; only the stock cover\'s and title\'s top rows lie under the pieces')
    expect(O['AH_SHUF_W'] >= 44 and O['AH_PLAY_W'] >= 44 and O['AH_BTN_H'] >= 44, 'both buttons are at least 44 px each way (docs/ui.md)')

    # ------------------------------------------------------------------ the cover size, the corner masks and the page theme
    import awtk_style
    from PIL import Image
    IMGS = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/images/xx')
    R = O['AH_CORNER']
    def cover_alpha(x, y):     # independent of tools/mod_icons.py: the 8 x 8 sampled area outside a quarter circle, centre at (R, R)
        c = 2 * 8 * R
        n = sum((2 * (x * 8 + i) + 1 - c) ** 2 + (2 * (y * 8 + j) + 1 - c) ** 2 > c * c for i in range(8) for j in range(8))
        return (n * 255 + 32) // 64
    # The corners are painted by the payload (pod_corners, from the cover's EVT_AFTER_PAINT) in the colour the window has behind
    # them: black on a black page, the tone under the gradient on a tinted one. Replay its fills over a cover and compare with
    # the model (independent of the C: the 8 x 8 sampled coverage, tools/mod_icons.py's gradient, tools/mod_nowplaying.py's tone).
    import random
    rnd = random.Random(7)
    S = O['AH_ART']
    def cover_alpha_of(x, y): return cover_alpha(x, y)
    def painted_over(m, art, cover):
        """cover (S x S RGB) under the fills the payload's paint made for it: the corner pixels blended as the canvas does."""
        fills = paint_corners(m, art)
        out = cover.copy()
        for colour, x, y, w, h in fills:
            assert (w, h) == (1, 1)
            a = colour >> 24; bg = (colour & 255, colour >> 8 & 255, colour >> 16 & 255)
            out.putpixel((x, y), tuple((b * a + c * (255 - a) + 127) // 255 for b, c in zip(bg, out.getpixel((x, y)))))
        return fills, out
    cov = Image.frombytes('RGB', (S, S), bytes(rnd.randrange(256) for _ in range(S * S * 3)))
    m, item, art = tint_machine()
    fills, got = painted_over(m, art, cov)
    expect(len(fills) == sum(1 for y in range(R) for x in range(R) if cover_alpha(x, y)) * 4 and all(c[0] & 0xffffff == 0 for c in fills),
           'on a black page the corners are painted pixel by pixel in black (every corner pixel with coverage, four times)')
    bad = 0
    for (x0, y0, fx, fy) in ((0, 0, 1, 1), (S - 1, 0, -1, 1), (0, S - 1, 1, -1), (S - 1, S - 1, -1, -1)):
        for y in range(R):
            for x in range(R):
                a = cover_alpha(x, y); p, q = x0 + fx * x, y0 + fy * y
                want = tuple((v * (255 - a) + 127) // 255 for v in cov.getpixel((p, q)))     # black over the cover at alpha a
                bad += any(abs(g - w) > 1 for g, w in zip(got.getpixel((p, q)), want))
    expect(not bad, f'the painted corners round the cover exactly as black at the coverage over it ({bad} pixels differ by more than 1)')
    expect(all(got.getpixel((x, y)) == cov.getpixel((x, y)) for y in range(R, S - R) for x in range(S)) and got.getpixel((0, 0)) == (0, 0, 0)
           and got.getpixel((S // 2, 0)) == cov.getpixel((S // 2, 0)), 'the rest of the cover is untouched; the outermost corner pixel is the page\'s colour')
    # a cover smaller than the box (a small embedded image; the thread never upscales) sits centred on the page's colour: nothing changes
    small = Image.frombytes('RGB', (100, 100), bytes(rnd.randrange(1, 256) for _ in range(100 * 100 * 3)))
    box = Image.new('RGB', (S, S)); box.paste(small, ((S - 100) // 2, (S - 100) // 2))
    expect(painted_over(m, art, box)[1] == box, 'a 100 px cover centred in the 160 px box is untouched by the black corners (square corners, on black)')
    # the placeholder (no cover yet, or none): the 160 px disc, rounded like a real cover
    ph = Image.open(os.path.join(IMGS, 'albumcover_info.png')); ph.load()
    expect(ph.size == (S, S) and ph.mode in ('RGB', 'RGBA'), f'the placeholder is a {S} px square, so it fills the box ({ph.size} {ph.mode})')
    rp = painted_over(m, art, ph.convert('RGB'))[1]
    expect(rp.getpixel((0, 0)) == (0, 0, 0) and rp.getpixel((S // 2, 0)) == ph.convert('RGB').getpixel((S // 2, 0)),
           'and its corners are round too')
    for n, body in (('ah_shuffle', 0x2A), ('ah_shuffle_down', 0x44)):
        im = Image.open(os.path.join(IMGS, n + '.png')).convert('RGBA')
        D = O['AH_DISC']
        expect(im.size == (D, D) and im.getpixel((0, 0))[3] == 0 and im.getpixel((D // 2, 2)) == (body, body, body, 255),
               f'{n}: a {D} px disc (transparent corners, #{body:02X} body) with the glyph on it')
    pg = Image.open(os.path.join(IMGS, 'ah_play.png')).convert('RGBA')
    vis = pg.getchannel('A').getbbox()
    G = O['AH_PILL_GLYPH']
    expect(pg.size == (G, G) and vis and vis[0] <= 1 and vis[2] >= G - 2 and vis[3] - vis[1] >= G - 2,
           f'the play glyph is a {G} px square image with no padding (the style places it; opaque box {vis})')
    for n, fill in (('ah_pill', 255), ('ah_pill_down', 0xBE)):
        im = Image.open(os.path.join(IMGS, n + '.png')).convert('RGBA'); W_, H_ = im.size
        expect((W_, H_) == (O['AH_PLAY_W'], O['AH_PILL_H']) and im.getpixel((0, 0))[3] == 0 and im.getpixel((W_ // 2, H_ // 2)) == (fill, fill, fill, 255)
               and im.getpixel((0, H_ // 2))[3] > 200 and im.getpixel((W_ - 1, H_ // 2))[3] > 200 and im.getpixel((W_ // 2, 0))[3] == 255 and im.getpixel((W_ // 2, H_ - 1))[3] == 255,
               f'{n}: a {W_}x{H_} stadium (round ends, transparent corners, #{fill:02X} fill)')
    def rel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    def cr(a, b):
        hi, lo = sorted((rel(a), rel(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)
    expect(cr(0x14, 255) >= 7 and cr(0x14, 0xBE) >= 7, f'the dark #141414 text and play glyph on the white pill ({cr(0x14, 255):.1f}:1) and the pressed #BEBEBE ({cr(0x14, 0xBE):.1f}:1) keep >= 7:1')
    expect(cr(255, 0x2A) >= 7 and cr(255, 0x44) >= 7, f'the white Shuffle glyph on the dark disc ({cr(255, 0x2A):.1f}:1) and the pressed one ({cr(255, 0x44):.1f}:1) keeps >= 7:1')

    for theme in ('default', 'theme1'):
        path = os.path.join(WORK, 'rootfs', 'release/assets', theme, 'raw/styles/albuminfo_page.bin')
        th = awtk_style.parse(open(path, 'rb').read())
        states = sorted(('normal', 'pressed', 'over', 'focused', 'disable'))
        play = {i.state: i for i in th.items if (i.widget, i.style) == ('button', 'btn_ahplay_style')}
        expect(sorted(play) == states, f'{theme}: the pill style has every state')
        bad = [s for s, i in play.items() if i.color('bg_color') != '#00000000' or i.get('bg_image') != ('ah_pill_down' if s == 'pressed' else 'ah_pill')
               or i.get('bg_image_draw_type') != O['IMAGE_DRAW_CENTER'] or i.color('text_color') != '#141414FF'
               or i.get('font_size') != 18 or i.has('round_radius') or i.get('icon') != 'ah_play']
        expect(not bad, f'{theme}: Play all is the 180x40 pill image (white, #BEBEBE pressed) drawn centred in the 44 px button, dark 18 px text and the play glyph ({bad})')
        # The glyph beside the text, not above it: AWTK's icon_at auto (0) puts the icon on top when icon height + font
        # size < the height inside the margins (16 + 18 < 44, widget_draw_icon_text @0x67235c), so the style says left (1).
        # widget_calc_icon_text_rect (@0x666f04) then makes an icon square (ir.h x ir.h at ir.x, the icon centred in it) and
        # a text rect from ir.x + ir.h + spacer to the right edge of ir. DEVICE FINDING (V2.1nF screenshot, docs/ui.md): the
        # text is LEFT aligned at the start of that rect (text_align_h defaults to 2 = left there, @0x672588), not centred in
        # it, so the style says text_align_h left, the spacer is the gap less the glyph's 14 px of padding in its square, and the
        # hook sets margin_left from the measured text. Modelled here from the numbers alone (independent of
        # tools/mod_ipodrows.py), with the shipped font, in every language.
        bad = [(s, k, i.get(k)) for s, i in play.items() for k, v in (('icon_at', 1), ('text_align_h', 2), ('margin_left', O['AH_PILL_MARGIN']), ('margin_right', 0), ('spacer', -6)) if i.get(k) != v]
        expect(not bad, f'{theme}: the pill says icon_at left, text left aligned, with its margins and spacer in every state ({bad[:3]})')
        i = play['normal']; ml, mr, sp = i.get('margin_left'), i.get('margin_right'), i.get('spacer')
        pw, ph = O['AH_PLAY_W'], O['AH_BTN_H']
        font = Ttf(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/fonts/default.ttf'))
        pill_pos = lambda ml_, tw: (ml_ + ph // 2 - G // 2, ml_ + ph + sp, (pw - ml_ - mr) - ph - sp)   # glyph image x, text pen x, text rect w
        bad = []
        for loc in pod_i18n.LOCALES:   # the style alone (the hook could not measure): English centred, every text still fits its rect
            tw = StbText(font, 18).layout(pod_i18n.TEXT['Play all'][loc])[1]
            gx, tx, rw = pill_pos(ml, tw)
            if not (tw <= rw and tx + tw <= pw - 8 and gx + vis[0] >= 16): bad.append((loc, tw, rw))
        expect(not bad, f'{theme}: with the style alone (no measuring) the text of all 13 languages fits its rect ({bad})')
        gx, tx, rw = pill_pos(ml, StbText(font, 18).layout('Play all')[1])
        expect(abs((tx - (gx + G)) - O['AH_PILL_GAP']) <= 1 and abs((gx + vis[0] + tx + StbText(font, 18).layout('Play all')[1]) / 2 - pw / 2) <= 2,
               f'{theme}: the style alone is the English pair centred with the {O["AH_PILL_GAP"]} px gap (glyph {gx}, text {tx})')
        if theme == 'default':   # the hook: margin_left from the measured text, in every language
            m = AlbumMachine(); m.measure = lambda t: StbText(font, 18).layout(t)[1]
            bad, margins = [], {}
            for loc in pod_i18n.LOCALES:
                m.set_language(loc); m.styled.clear(); m.measured.clear()
                item = m.header(); play_w = m.kids(item)[3]
                tw = StbText(font, 18).layout(pod_i18n.TEXT['Play all'][loc])[1]
                keys = [k for w_, k, v in m.styled if w_ == play_w]
                vals = {v for w_, k, v in m.styled if w_ == play_w}
                if (len(m.styled) != 5 or sorted(keys) != sorted(f'{s}:margin_left' for s in states) or len(vals) != 1
                        or [t for _, t, _ in m.measured] != [pod_i18n.TEXT['Play all'][loc]]):
                    bad.append((loc, 'calls', m.styled, m.measured)); continue
                gx, tx, rw = pill_pos(vals.pop(), tw); margins[loc] = tx - gx
                gap, centre = tx - (gx + G), (gx + vis[0] + tx + tw) / 2
                if not (abs(gap - O['AH_PILL_GAP']) <= 1 and abs(centre - pw / 2) <= 2 and tw <= rw and gx + vis[0] >= 8 and tx + tw <= pw - 8):
                    bad.append((loc, tw, gap, centre, rw))
            expect(not bad, f'the hook centres glyph + {O["AH_PILL_GAP"]} px gap + text in the pill in all 13 languages (gap 8 +-1, centre +-2, all of it inside; {bad})')
            expect(len(set(margins.values())) == 1, 'the glyph-to-text distance is the same in every language (only the margin moves)')
            m.styled.clear(); m.set_language(None); m.measure = None
            item = m.header(); play_w = m.kids(item)[3]
            expect(not m.styled and m.style[play_w] == 'btn_ahplay_style' and m.texts[play_w] == 'Play all',
                   'when the text cannot be measured the hook sets nothing: the style (English centred) stays')
            m.measure = lambda t: 400; m.styled.clear()
            item = m.header()
            expect(not m.styled, 'a width that cannot fit the pill leaves the style alone too')
            m.measure = lambda t: 52; m.styled.clear()
            item = m.header(); play_w = m.kids(item)[3]
            expect(m.bound.get(play_w, {}) == {O['EVT_CLICK']: (PSYMS['ah_on_play'], 0)} and all(w_ == play_w and k.endswith(':margin_left') for w_, k, v in m.styled)
                   and not any(c[0] == 'widget_set_name' and c[1] == play_w for c in m.calls) and ('widget_set_tr_text', play_w, 'Play all') in m.calls,
                   'the stock Play all button is the same widget: not renamed, only our handler bound (the stock one taken off), only its margin_left styled')
            expect({v for _, _, v in m.styled} == {(pw - (G + O['AH_PILL_GAP'] + 52)) // 2 - (44 - G) // 2}, f'the margin for a 52 px text is ({pw} - ({G} + 8 + 52)) / 2 - {(44 - G) // 2}')
        shuf = {i.state: i for i in th.items if (i.widget, i.style) == ('button', 'btn_ahshuf_style')}
        bad = [s for s, i in shuf.items() if i.get('icon') != ('ah_shuffle_down' if s == 'pressed' else 'ah_shuffle') or i.color('bg_color') != '#00000000']
        expect(sorted(shuf) == states and not bad, f'{theme}: Shuffle is its disc image (one lighter pressed) on no fill ({bad})')
        for style, px_, colour in (('srlabel_ahtitle_style', 22, '#FFFFFFFF'), ('srlabel_ahartist_style', 18, '#AAAAAAFF'), ('srlabel_ahmeta_style', 15, '#9C9C9CFF')):
            ss = [i for i in th.items if (i.widget, i.style) == ('hscroll_label', style)]
            expect(len(ss) == 3 and all(i.get('font_size') == px_ and i.color('text_color') == colour and i.get('text_align_h') == 1 for i in ss),
                   f'{theme}: {style} is {px_} px {colour}, centred')
        nav = [i for i in th.items if i.widget == 'label' and i.style in ('navbar_label_white', 'navbar_leftlabel_white', 'navbar_centerlabel_white', 'navbar_rightlabel_white')]
        expect(len(nav) == 12 and all(i.color('text_color') == '#00000000' for i in nav),
               f'{theme}: the navbar title (the label stays) is transparent on this page: the design shows Back and Now Playing only')
        stock = [i for i in th.items if (i.widget, i.style) == ('button', 'btn_imgplayall_style')]
        expect(len(stock) == 5 and all(i.get('icon') in ('playall', 'playall_down') for i in stock),
               f'{theme}: the stock Play all style is untouched (a header the hook leaves alone keeps it)')
        expect(not any(i.style in ('btn_albumbtn_style', 'srlabel_meta15_style') for i in th.items), f'{theme}: the old dark button and 15 px line styles are gone')

    # ------------------------------------------------------------------ Cover Flow
    # the artist's Cover Flow starts on its first album; the main one keeps its last album
    m = artists_machine(); m.load_image = 0; m.stock_songlist = True
    m.call(PSYMS['artists_open'], count=5000000)
    artists_tap(m, 0)
    expect(shelf_value(m) == 0,
           "the artist's Cover Flow starts on its first (leftmost) album, not the stock slide_menu's item 1")
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'Kind of Blue') in m.calls
           and ('widget_set_text_utf8', m.widgets['label_artist'], 'Miles Davis') in m.calls, 'and its captions are set')
    m.tap(O['CF_CX'], count=60000000)
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ARTIST_ALBUMS'], 0) in m.calls,
           "a tap on that album opens the stock album page with the artist page's class")
    # one album: the captions are there as soon as the page opens
    m = artists_machine(); m.call(PSYMS['artists_open'], count=5000000)
    artists_tap(m, 1)
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'Pastel Blues') in m.calls
           and ('widget_set_text_utf8', m.widgets['label_artist'], 'Nina Simone') in m.calls and shelf_value(m) == 0,
           'an artist with one album shows its captions on open')
    for last in (0, 2):
        m = cover_machine(albums=3)
        key = fnv(fnv(O['FNV_SEED'], f'Artist {last}'), f'Album {last}') or 1
        m.files['/mnt/mmc/.m1plus/covers/album'] = 4; m.saved_album = key
        m.call(PSYMS['coverflow_open'], count=5000000)
        expect(shelf_value(m) == last
               and ('widget_set_text_utf8', m.widgets['label_album'], f'Album {last}') in m.calls,
               f'the main Cover Flow reopens on its last album ({last})')
    m = cover_machine(albums=1); m.call(PSYMS['coverflow_open'], count=5000000)
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'Album 0') in m.calls, 'a library with one album shows its captions on open')
    tree = awtk_ui.parse(open(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1plus_cover.bin'), 'rb').read())
    expect('view_tracks' not in [x.name for x in tree.walk()], 'the Cover Flow asset has no track list view any more')


def run(ctx):
    album_tests(ctx.expect, ctx.page, ctx.cover_asset)
