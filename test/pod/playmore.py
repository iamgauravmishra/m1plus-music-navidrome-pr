"""Now Playing's More menu (patch/playmore.c, docs/modules/playmore.md): the stock playmore_dialog as a bottom sheet with two pages.

The dialog is built from the built asset (ui/dialog/playmore_dialog.bin) as real widget structs under demo's own window
code (the pulldown test's machine): widget_move / _resize / _set_visible / _set_sensitive / _restack, the list_view layouter
(children_layouter_list_view, run by window_manager_check_and_layout), widget_find_target and the pointer path run for real;
only leaves are mocked. The stock init (dialog_playmore_dialog_init, which widget_foreach-es the stock row binder 0x478b44 over
the tree, binds the to-background and tap-above handlers and pins the sheet at y 130) is run as far as its binding goes: the
binder is called for every widget and the two handlers are registered as the stock init does, so the stock handlers are in `m.bound`
(and every registration in `m.reg`, in order) before the hook runs, exactly as on the device, and must be there unchanged afterwards;
the stock to-background (0x4789f0) and tap-above (0x478abc) handlers run as the real stock code."""
import importlib.util, os, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import awtk_strings, awtk_style
from awtk_text import Ttf, StbText

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join('rootfs', 'release', 'assets', 'default', 'raw')
KILL = '/mnt/mmc/m1pod-off'
DIALOG_Y, ROW_H, SCREEN_H, SHEET_H = 130, O['PM_ROW_H'], O['PM_SCREEN_H'], O['PM_PAGE_N'] * O['PM_ROW_H']
SHEET_Y = SCREEN_H - SHEET_H                     # 280: the sheet sits on the bottom of the screen
BINDER, SPEED_INIT = 0x478b44, 0x478fd0          # the stock widget_foreach visitor (binds a row or badge by name) and the speed badge images
STOCK_BG, STOCK_UP = 0x4789f0, 0x478abc          # the stock to-background handler (moves the dialog to y 130) and tap-above-closes handler
STOCK_CLICK = {'listitem0': 0x478f58, 'listitem2': 0x4798f0, 'listitem3': 0x4796cc, 'listitem4': 0x4795cc, 'listitem5': 0x4793ac,
               'listitem6': 0x4791f4, 'img_1x': 0x479bf4, 'img_1_25x': 0x479b20, 'img_1_5x': 0x479a4c, 'img_2x': 0x479978}
STOCK_NAMES = ['listitem0', 'listitem1', 'listitem2', 'listitem3', 'listitem4', 'listitem5', 'listitem6']
GO_ALBUM, GO_ARTIST, ADD, MORE, BACK, SPEED, AB, DELETE, SEARCH = 4, 5, 2, 7, 8, 1, 0, 6, 3   # row indices (listitemN, 7 = pod_more, 8 = pod_back)
ROWS = STOCK_NAMES + ['pod_more', 'pod_back']
PAGE1, PAGE2 = [GO_ALBUM, GO_ARTIST, ADD, MORE], [BACK, SPEED, AB, DELETE]
HIDDEN1, HIDDEN2 = sorted(set(range(9)) - set(PAGE1)), sorted(set(range(9)) - set(PAGE2))
VT = {'dialog': LI_VT, 'list_view': LV_VT, 'scroll_view': SV_VT, 'list_item': LI_VT, 'image': IMG_VT}
PM_TEXTS = {'More': None, 'Speed': None, 'Files below 48 kHz only': None}   # the keys the payload sets (the label each is for is in the checks)


def sibling(name):
    """test/pod/<name>.py as test/patch.py loaded it, or loaded here when this module runs alone."""
    key = f'podtest_{name}'
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, os.path.join(HERE, name + '.py'))
        mod = importlib.util.module_from_spec(spec); sys.modules[key] = mod; spec.loader.exec_module(mod)
    return sys.modules[key]


pulldown = sibling('pulldown')


class PM(pulldown.SM):
    """The More dialog's tree from the built asset, under the window manager `wm`. tr_fail: the keys widget_set_tr_text fails for;
    bind_fail: the widget_on of the payload's that fails ('pod_more' / 'pod_back' click, 'bg' to-background, 'destroy')."""
    EXTRA = pulldown.SM.EXTRA + ('stock_playmore_resume',)

    def __init__(self, theme='default', ui=None):
        super().__init__(True)
        self.handlers[pod.PLAYMORE_INIT + 12] = 'stock_playmore_resume'
        self.tr_fail, self.bind_fail = set(), None
        self.init_ret = 0
        self.reg = []                  # every widget_on, in order: (widget, event, handler, ctx)
        self.nodes = {}
        tree = awtk_ui.parse(open(os.path.join(WORK, 'rootfs/release/assets', theme, 'raw/ui/dialog/playmore_dialog.bin'), 'rb').read()) if ui is None else ui
        self.dialog = self.root = self.win = self.make(tree, 0)
        self.wm = self.widget(LI_VT, 0, 0, 320, 480)
        self.kids(self.wm, [self.dialog]); self.setword(self.dialog + 0x44, self.wm)
        self.sv, self.lv = self.nodes['playmore_scrollview'], self.nodes['playmore_listview']
        self.bar = self.nodes['scroll_bar_m']
        for off, v in ((0x78, 310), (0x7c, 0), (0xec, 0x611450), (0xf0, pulldown.LV_HOOK), (0xf4, pulldown.PAINT_HOOK)): self.setword(self.sv + off, v)   # what list_view_on_add_child leaves
        self.u.mem_write(self.sv + 0x90, bytes([0, 1, 0]))
        speed = self.word(0x759814); self.setword(self.sv + 0x88, speed); self.setword(self.sv + 0x8c, speed)
        for off, v in ((0x7c, ROW_H), (0x84, self.sv)): self.setword(self.lv + off, v)   # list_view: default_item_height 50, its scroll_view
        lay = self.alloc(0x1c); self.u.mem_write(lay, bytes(0x1c)); self.setword(lay + 0xc, pulldown.LAYOUTER_VT); self.u.mem_write(lay + 0x1a, bytes([4]))
        self.setword(self.sv + 0x64, lay)
        self.rows = [self.nodes[n] for n in ROWS]
        self.widgets = dict(self.nodes)
        self.setword(pod.GP - 0xa94, PSYMS['pod_lib_strcmp'])   # the GOT slot of strcmp, for the stock binder (the base machine's strcmp mock)

    def make(self, w, parent):
        a = self.widget(VT.get(w.type, LI_VT), w.x, w.y, w.w, w.h, parent, emitter=w.type in ('list_item', 'image'))
        flags = 1 | (0 if w.get('visible') == 'false' else 4) | (0 if w.get('sensitive') == 'false' else 8)
        self.setword(a + 0x24, flags)
        if w.name:
            self.nodes[w.name] = a; self.setword(a + 0x10, self.cstr(w.name))
        if w.children:
            self.kids(a, [self.make(c, a) for c in w.children])
        return a

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address)
        a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        if name == 'widget_set_tr_text' and self.read_cstr(a1) in self.tr_fail:
            self.calls.append(('widget_set_tr_text', a0, self.read_cstr(a1))); u.reg_write(UC_MIPS_REG_V0, 1); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA)); return
        if name == 'widget_on':
            self.reg.append((a0, a1, a2, a3))
            fails = {'pod_more': (self.nodes['pod_more'], O['EVT_CLICK']), 'pod_back': (self.nodes['pod_back'], O['EVT_CLICK']),
                     'bg': (self.dialog, O['EVT_WINDOW_TO_BG']), 'destroy': (self.dialog, O['EVT_DESTROY'])}
            if self.bind_fail and (a0, a1) == fails[self.bind_fail] and a2 != STOCK_BG:
                self.reg.pop(); self.calls.append(('widget_on', a0, a1, a2, 0)); u.reg_write(UC_MIPS_REG_V0, 0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA)); return
        super()._hook(u, address, size, _)

    def leaf(self, name, a0, a1, a2, a3, sp):
        if name == 'stock_playmore_resume':
            self.calls.append(('stock_playmore_resume', a0, a1)); return self.init_ret
        return super().leaf(name, a0, a1, a2, a3, sp)

    # ---- what the stock init did: bind every row and badge (the widget_foreach visitor, run per widget), the speed badge images,
    # the to-background and tap-above handlers on the dialog (widget_on @0x479ce8 / 0x479d5c), the sheet at y 130 (widget_move @0x479d20)
    def stock_init(self):
        self.stock_calls, self.reg = [], []
        self.reg += [(self.dialog, O['EVT_WINDOW_TO_BG'], STOCK_BG, self.dialog)]
        for n, w in self.nodes.items():
            self.call(BINDER, a0=self.dialog, a1=w, count=200000); self.stock_calls += self.calls
        self.call(SPEED_INIT, a0=self.dialog, count=400000); self.stock_calls += self.calls
        self.reg += [(self.dialog, O['EVT_POINTER_UP'], STOCK_UP, self.dialog)]
        for w, e, fn, ctx in self.reg: self.bound[(w, e)] = (fn, ctx)
        self.stock_bound = dict(self.bound)
        self.stock_reg = list(self.reg)
        self.setword(self.dialog + 4, DIALOG_Y)       # widget_move(dialog, 0, 130)
        self.sync()

    def open(self, **kw):
        """The dialog opens: the stock init, then the payload's hook (which runs it again as its first step)."""
        self.stock_init()
        ret = self.call(PSYMS['m1pod_playmore_init'], a0=self.dialog, a1=0, count=4000000)
        self.sync()
        return ret

    def sync(self):
        """The props the mocked widget_get_prop_int answers, from the widget structs (real widget_resize / move write those)."""
        for n, w in self.nodes.items():
            for k, o in (('x', 0), ('y', 4), ('w', 8), ('h', 0xc)): self.props[(w, k)] = self.s32(w + o)

    def stock_kept(self):
        """Every handler the stock init registered is still registered, first and in order (`bound` keeps only the latest per event, ours for the to-background one)."""
        return self.stock_reg == self.reg[:len(self.stock_reg)] and all(self.bound[k] == v for k, v in self.stock_bound.items() if k[1] != O['EVT_WINDOW_TO_BG'])
    def handlers_of(self, w, e): return [(fn, ctx) for ww, ee, fn, ctx in self.reg if (ww, ee) == (w, e)]
    def added(self): return [(self.name(w), e) for w, e, fn, ctx in self.reg[len(self.stock_reg):]]

    # ---- reading the dialog
    def name(self, w): return self.read_cstr(self.word(w + 0x10)) if w else ''
    def flags(self, w): return struct.unpack('<H', self.u.mem_read(w + 0x24, 2))[0]
    def shown_row(self, i): return bool(self.flags(self.rows[i]) & F_VISIBLE)
    def live(self, i): return (self.flags(self.rows[i]) & (F_VISIBLE | F_SENSITIVE)) == F_VISIBLE | F_SENSITIVE
    def dead(self, i): return (self.flags(self.rows[i]) & (F_VISIBLE | F_SENSITIVE)) == 0
    def shown(self): return [i for _, i in sorted((self.s32(r + 4), i) for i, r in enumerate(self.rows) if self.shown_row(i))]
    def stacked(self):
        arr = self.word(self.sv + 0x58); elms = self.word(arr + 8)
        return [self.rows.index(self.word(elms + 4 * i)) if self.word(elms + 4 * i) in self.rows else -1 for i in range(self.word(arr))]
    def ys(self): return [self.s32(self.rows[i] + 4) for i in self.shown()]
    def hs(self): return [self.s32(self.rows[i] + 0xc) for i in self.shown()]
    def size(self, w): return (self.s32(w + 8), self.s32(w + 0xc))
    def top(self): return self.s32(self.dialog + 4)
    def vh(self): return self.s32(self.sv + 0x7c)
    def hit(self, x, y):
        """The widgets the stock hit test descends through for a touch at the screen point (x, y), by demo's own widget_find_target; a hit on
        a widget the pointer path would not take (not enabled and sensitive) ends the list with a '!'."""
        w, path = self.wm, []
        while True:
            t = self.call(FIND_TARGET, a0=w, a1=x, a2=y, count=200000)
            if not t: return path
            if (self.flags(t) & 9) != 9: return path + [self.name(t) + '!']
            w = t; path.append(self.name(t))
    def row_y(self, i): return self.top() + self.ys()[self.shown().index(i)]
    def tap_row(self, i, x=160): return self.hit(x, self.row_y(i) + ROW_H // 2)
    def click_row(self, i):
        """A tap on a row of the sheet: the stock list_item turns the touch into a click; the payload's handler runs with the context it was given."""
        y = self.row_y(i) + ROW_H // 2
        self.touch_at('d', 160, y, 0); self.touch_at('u', 160, y, 60)
        clicks = [e[1] for e in self.log if e[0] == 'emit' and e[2] == O['EVT_CLICK']]
        assert clicks == [self.rows[i]], clicks
        fn, ctx = self.bound[(self.rows[i], O['EVT_CLICK'])]
        self.call(fn, a0=ctx, a1=0, count=4000000)
        self.sync()
    def click_more(self): self.click_row(MORE)
    def click_back(self): self.click_row(BACK)
    def touch_at(self, kind, x, y, dt):
        self.t += dt
        e = self.alloc(0x30); self.u.mem_write(e, bytes(0x30))
        self.setword(e, EVT_OF[kind]); self.setword(e + 4, 0x30); self.setword(e + 8, self.t); self.setword(e + 0x18, x); self.setword(e + 0x1c, y)
        self.u.mem_write(e + 0x24, bytes([0 if kind == 'u' else 1]))
        self.log = []
        self.call(pulldown.ON[kind], a0=self.wm, a1=e, count=4000000)
    def relayout_all(self):
        self.mark(); self.relayout()
        self.sync()
    def event(self, w, kind, y=0):
        """Every handler registered for (w, kind), in registration order, as the emitter runs them; the moved state is synced after each."""
        e = self.alloc(0x30); self.u.mem_write(e, bytes(0x30)); self.setword(e, kind); self.setword(e + 0x1c, y)
        out = []
        for fn, ctx in self.handlers_of(w, kind):
            self.call(fn, a0=ctx, a1=e, count=400000); self.sync(); out.append((fn, self.top(), [c for c in self.calls if c[0] == 'window_close']))
        return out


EVT_OF = {'d': O['EVT_POINTER_DOWN'], 'm': O['EVT_POINTER_MOVE'], 'u': O['EVT_POINTER_UP']}


def run(ctx):
    expect = ctx.expect
    d = open(DEMO, 'rb').read(); image = bytearray(d)
    word = lambda a: struct.unpack_from('<I', d, pod.fileoff(image, a))[0]

    # -- 0. the hook and what it relies on -----------------------------------------------------------------------------------
    w0, w1, w2, w3 = (word(pod.PLAYMORE_INIT + 4 * i) for i in range(4))
    expect(w0 == pod.j(PSYMS['m1pod_playmore_init']) and w1 == 0 and w2 == pod.PLAYMORE_INIT_PROLOGUE[2] and w3 == 0x10800059 == pod.PLAYMORE_PINS[0][1],
           'dialog_playmore_dialog_init starts with j m1pod_playmore_init; nop; the trampoline resumes at its beqz a0')
    expect(pod.PLAYMORE_INIT == 0x479cc4 and MANIFEST['hook_playmore']['addr'] == pod.PLAYMORE_INIT and MANIFEST['hook_playmore']['target'] == PSYMS['m1pod_playmore_init'],
           'the manifest records the hook')
    gp = []
    m = PM(); m.u.hook_add(UC_HOOK_CODE, lambda u, a, s, _: gp.append(u.reg_read(UC_MIPS_REG_GP)), begin=pod.PLAYMORE_INIT + 12, end=pod.PLAYMORE_INIT + 12)
    m.open()
    expect(gp == [pod.GP], f'the trampoline restores $gp before the stock body ({[hex(g) for g in gp]})')
    expect(all(word(a) == old for a, old, _ in pod.PLAYMORE_PINS[1:]), 'every pinned stock word of the dialog init, its dispatcher and its two handlers is as pinned')
    pins = {a: old for a, old, _ in pod.PLAYMORE_PINS}
    expect(pins.get(0x479ce0) == 0x2405012c and pins.get(0x478a1c) == 0x24060082 and pins.get(0x479d10) == 0x24060082 and pins.get(0x478ac8) == 0x8c830004,
           'the stock to-background bind (0x12c), its widget_move(dialog, 0, 130), the init\'s widget_move and the tap-above read of dialog->y are pinned')
    # the dim: the window manager sets the highlighter up from the dialog's "highlight" property when the dialog opens (0x6901c4 reads it, the
    # "default" highlighter is registered at tk init, 0x68e8bc)
    expect(word(0x6901c4) == 0x24a59a1c and word(0x68e8bc) == 0x24a5a988 and d[pod.fileoff(image, 0x749a1c):][:10] == b'highlight\0' and d[pod.fileoff(image, 0x74a988):][:8] == b'default\0',
           'the stock window manager reads the dialog\'s "highlight" property when it opens and registers the "default" highlighter')
    expect(m.calls[0] == ('stock_playmore_resume', m.dialog, 0), 'the stock init runs first, with its arguments')

    # -- 1. page 1: the order, visibility, sensitivity, geometry ----------------------------------------------------------------
    m = PM(); m.stock_init()
    stock_bound = dict(m.stock_bound)
    expect(set(STOCK_CLICK) <= {n for n, w in m.nodes.items() if (w, O['EVT_CLICK']) in stock_bound}
           and all(stock_bound[(m.nodes[n], O['EVT_CLICK'])][0] == fn for n, fn in STOCK_CLICK.items()),
           'the stock init binds listitem0, 2, 3, 4, 5, 6 and the four speed badges to the stock handlers (the reference for the checks below)')
    keys = {m.name(c[1]): c[2] for c in m.stock_calls if c[0] == 'widget_set_tr_text'}
    expect(keys.get('scrlabel4') == 'player_albuminfo' and keys.get('scrlabel5') == 'player_songerinfo' and keys.get('scrlabel6') == 'player_delete'
           and keys.get('scrlabel1') == 'player_multiple' and keys.get('scrlabel0') == 'player_abrepeat' and keys.get('label1_msg') == 'player_msgmul',
           'the stock binder gives the rows their stock texts')
    expect(m.shown() == [0, 1, 2, 3, 4, 5, 6] and m.stacked()[:7] == list(range(7)) and all(m.dead(i) for i in (MORE, BACK)) and not m.shown_row(MORE) and not m.shown_row(BACK),
           'before the hook: the stock seven rows in asset order, pod_more and pod_back hidden and insensitive')
    m.relayout_all()
    expect(m.shown() == list(range(7)) and m.hs() == [50, 50, 50, 50, 50, 60, 60] and m.ys() == [0, 50, 100, 150, 200, 250, 310] and m.vh() == 370,
           f'the stock list_view layouter keeps the asset\'s own 60 px for Go to artist and Delete: 370 px of rows in the 350 px sheet ({m.ys()} {m.hs()} {m.vh()})')
    m = PM(); ret = m.open()
    expect(ret == 0, 'the hook returns the stock result')
    expect(m.shown() == PAGE1, f'page 1: Look up album, Look up artist, Add to playlist, More ({m.shown()})')
    expect(m.ys() == [0, 50, 100, 150], f'page 1: the rows at 0, 50, 100, 150 ({m.ys()})')
    expect(all(m.live(i) for i in PAGE1) and all(m.dead(i) for i in HIDDEN1), 'page 1: the shown rows are visible and sensitive, the other five neither (visible=false and sensitive=false)')
    expect(m.stacked()[:4] == PAGE1 and sorted(m.stacked()[4:]) == HIDDEN1, f'page 1: the children are stacked shown rows first, hidden last ({m.stacked()})')
    expect(set(m.hs()) == {ROW_H}, f'page 1: every shown row is {ROW_H} high, Look up artist too ({m.hs()})')
    expect(m.size(m.dialog) == (320, 200) and m.size(m.lv) == (320, 200) and m.size(m.sv) == (310, 200) and m.size(m.bar) == (10, 200) and m.vh() == 200 and m.yoff() == 0,
           f'page 1: the sheet is 4 rows tall ({m.size(m.dialog)}, virtual_h {m.vh()})')
    expect(m.top() == SHEET_Y == 280 and m.top() + m.size(m.dialog)[1] == SCREEN_H and m.s32(m.dialog) == 0,
           f'page 1: the sheet sits on the bottom of the screen: y {m.top()} + {m.size(m.dialog)[1]} = {m.top() + m.size(m.dialog)[1]}')
    expect(('widget_set_tr_text', m.nodes['pod_more_label'], 'More') in m.calls and ('widget_set_tr_text', m.nodes['pod_back_label'], 'More') in m.calls,
           'the More row and the back header read "More" (translated by key)')
    expect(('widget_set_tr_text', m.nodes['scrlabel1'], 'Speed') in m.calls and ('widget_set_tr_text', m.nodes['label1_msg'], 'Files below 48 kHz only') in m.calls,
           'the Playback speed label reads "Speed" and the note under it its short text')
    expect(not any(c[0] == 'image_base_set_image' for c in m.calls), 'the More chevron is a fixed image: nothing sets it')
    names = [c[1] for c in m.calls if c[0] == 'widget_lookup']
    expect(all(n in names for n in ('listitem0', 'listitem6', 'pod_more', 'pod_back', 'pod_more_label', 'pod_back_label', 'scrlabel1', 'label1_msg')), 'the rows and labels are found by their names')
    fixed = dict(m.bound)
    expect(m.stock_kept(),
           'every stock handler is still bound to the same function and context after the hook, and still first in the order')
    expect(sorted(m.added()) == sorted([('pod_more', O['EVT_CLICK']), ('pod_back', O['EVT_CLICK']), ('playmore_dialog', O['EVT_DESTROY']), ('playmore_dialog', O['EVT_WINDOW_TO_BG'])]),
           f'the hook adds the More click, the back click, the destroy and the to-background handlers and nothing else ({m.added()})')
    expect(not any(c[0] in ('widget_off_by_func',) for c in m.calls), 'no stock handler is taken off')

    # -- 2. hit tests on page 1: a touch reaches the row that is drawn there, a hidden row never takes it -----------------------
    m = PM(); m.open(); m.relayout_all()
    for pos, i in enumerate(PAGE1):
        path = m.tap_row(i)
        expect(path[:3] == ['playmore_dialog', 'playmore_listview', 'playmore_scrollview'] and path[3] == ROWS[i], f'page 1: a tap on row {pos} lands on {ROWS[i]} ({path})')
    above = m.hit(160, SHEET_Y - 1)
    expect(not any(n.startswith(('listitem', 'pod_')) for n in above) and m.hit(160, SHEET_Y)[-1] == 'listitem4' and m.hit(160, SCREEN_H - 1)[-1] == 'pod_more',
           f'page 1: the sheet starts at y {SHEET_Y} and reaches the bottom edge; one pixel above it there is no row to hit ({above})')
    for i in HIDDEN1:
        r = m.rows[i]
        expect(m.s32(r + 4) >= 200 and m.dead(i), f'page 1: the hidden {ROWS[i]} is parked below its page, invisible and insensitive ({m.s32(r + 4)})')
    for y in range(SHEET_Y + 2, SCREEN_H, 7):
        h = m.hit(160, y)
        expect(not h[-1].endswith('!'), f'page 1: a touch at y {y} never lands on an insensitive widget ({h})')
    # the speed badges and the A-B switch are not reachable on page 1
    for x in (166, 206, 246, 286, 270):
        for pos in range(4):
            expect(not any(n.startswith('img_') for n in m.hit(x, SHEET_Y + 25 + 50 * pos)), f'page 1: no speed badge or switch at x {x}, row {pos}')

    # -- 3. page 2 and back ---------------------------------------------------------------------------------------------------------
    m = PM(); m.open(); m.relayout_all()
    m.click_more()
    expect(m.shown() == PAGE2, f'page 2: the back header, Playback speed, A-B repeat, Delete ({m.shown()})')
    expect(m.ys() == [0, 50, 100, 150] and set(m.hs()) == {ROW_H}, f'page 2: the rows at 0, 50, 100, 150, {ROW_H} high ({m.ys()} {m.hs()})')
    expect(all(m.live(i) for i in PAGE2) and all(m.dead(i) for i in HIDDEN2), 'page 2: four rows live, the other five (Online search included) neither visible nor sensitive')
    expect(m.stacked()[:4] == PAGE2 and sorted(m.stacked()[4:]) == HIDDEN2, f'page 2: stacked in that order, the hidden rows last ({m.stacked()})')
    expect(m.size(m.dialog) == (320, 200) and m.size(m.lv) == (320, 200) and m.size(m.sv) == (310, 200) and m.size(m.bar) == (10, 200) and m.vh() == 200,
           f'page 2: the sheet has not resized ({m.size(m.dialog)})')
    expect(m.top() == SHEET_Y and m.top() + m.size(m.dialog)[1] == SCREEN_H, 'page 2: the sheet is still on the bottom of the screen')
    expect(all(m.s32(m.rows[i] + 4) >= 200 for i in HIDDEN2), 'page 2: the hidden rows are parked below the sheet')
    m.relayout_all()
    expect(m.shown() == PAGE2 and m.ys() == [0, 50, 100, 150] and set(m.hs()) == {ROW_H} and m.vh() == 200 and m.yoff() == 0 and m.stacked()[:4] == PAGE2,
           f'page 2: a relayout keeps the order, the rows {ROW_H} high and the height ({m.shown()}, {m.hs()})')
    m.relayout_all(); m.mark(); m.relayout_all()
    expect(m.shown() == PAGE2 and m.stacked()[:4] == PAGE2, 'page 2: further relayouts change nothing')
    for pos, i in enumerate(PAGE2):
        path = m.tap_row(i)
        expect(path[3] == ROWS[i], f'page 2: a tap on row {pos} lands on {ROWS[i]} ({path})')
    badges = [m.hit(x, SHEET_Y + 50 + 25)[-1] for x in (166, 206, 246, 286)]
    expect(badges == ['img_1x', 'img_1_25x', 'img_1_5x', 'img_2x'], f'page 2: the four speed badges are the touch targets in the Playback speed row ({badges})')
    ab_path = m.hit(270, SHEET_Y + 100 + 25)
    expect(ab_path[-1] == 'img_switch' or ab_path[-1] == 'listitem0', f'page 2: the A-B repeat row takes the touch ({ab_path})')
    for pos in range(4):   # the page 1 rows are not reachable on page 2
        expect(not any(n in ('listitem2', 'listitem4', 'listitem5', 'pod_more') for n in m.hit(160, SHEET_Y + 25 + 50 * pos)), f'page 2: row {pos} does not reach a page 1 row')
    expect(all(not m.hit(160, y)[-1].endswith('!') for y in range(SHEET_Y + 2, SCREEN_H, 7)), 'page 2: no touch lands on a hidden widget')
    expect(m.stock_kept(), 'page 2: the stock handlers are still bound')
    expect(m.bound[(m.rows[DELETE], O['EVT_CLICK'])][0] == STOCK_CLICK['listitem6'], 'page 2: Delete is bound to the stock delete handler (it asks for confirmation)')
    m.click_back()
    expect(m.shown() == PAGE1 and m.size(m.dialog) == (320, 200) and m.top() == SHEET_Y and m.vh() == 200 and all(m.dead(i) for i in HIDDEN1),
           f'the back header returns to page 1: four rows, the sheet where it was ({m.shown()}, {m.size(m.dialog)}, y {m.top()})')
    expect(m.stacked()[:4] == PAGE1 and all(m.states.get(m.rows[i]) == 'normal' for i in (MORE, BACK)), 'page 1 again: stacked in order, the tapped rows back in their normal state')
    m.relayout_all()
    expect(m.shown() == PAGE1 and m.ys() == [0, 50, 100, 150] and m.stacked()[:4] == PAGE1, 'page 1 again: a relayout keeps the order')
    for _ in range(3): m.click_more(); m.click_back()
    expect(m.shown() == PAGE1 and m.vh() == 200 and m.top() == SHEET_Y, 'switching pages repeatedly ends where it began')
    m.click_more(); m.mark(); m.relayout(); m.sync()
    expect(m.shown() == PAGE2 and m.stacked()[:4] == PAGE2, 'a relayout while on page 2 (the Delete confirm opening over the dialog) keeps the rows, stacked in y order for the list_view paint hook')

    # -- 4. tap above the sheet closes it (the stock handler, on the new y); a tap on the sheet does not -----------------------------
    def up(m, y):
        e = m.alloc(0x30); m.u.mem_write(e, bytes(0x30)); m.setword(e, O['EVT_POINTER_UP']); m.setword(e + 0x1c, y)
        fn, c = m.bound[(m.dialog, O['EVT_POINTER_UP'])]
        m.call(fn, a0=c, a1=e, count=200000)
        return [x for x in m.calls if x[0] == 'window_close']
    for page in (1, 2):
        m = PM(); m.open()
        if page == 2: m.click_more()
        expect(m.bound[(m.dialog, O['EVT_POINTER_UP'])] == (STOCK_UP, m.dialog), f'page {page}: the tap handler is still the stock one')
        expect(up(m, SHEET_Y - 1) == [('window_close', m.dialog)] and up(m, 0) == [('window_close', m.dialog)] and up(m, 130) == [('window_close', m.dialog)],
               f'page {page}: a tap above the sheet (y < {SHEET_Y}) closes the dialog')
        expect(up(m, SHEET_Y) == [] and up(m, SHEET_Y + 20) == [] and up(m, SCREEN_H - 1) == [], f'page {page}: a tap on the sheet does not')

    # -- 5. another dialog opens over the sheet: the stock handler moves it to y 130, ours puts it back ------------------------------
    for page in (1, 2):
        m = PM(); m.open()
        if page == 2: m.click_more()
        order = m.handlers_of(m.dialog, O['EVT_WINDOW_TO_BG'])
        expect([fn for fn, _ in order][0] == STOCK_BG and len(order) == 2, f'page {page}: the stock to-background handler is first, ours second ({[hex(f) for f, _ in order]})')
        ran = m.event(m.dialog, O['EVT_WINDOW_TO_BG'])
        stock_alone = PM(); stock_alone.stock_init(); stock_alone.event(stock_alone.dialog, O['EVT_WINDOW_TO_BG'])
        expect(stock_alone.top() == DIALOG_Y and stock_alone.reg == stock_alone.stock_reg, f'page {page}: the stock handler alone moves the dialog to y {DIALOG_Y} (what the hook has to undo)')
        expect(m.top() == SHEET_Y and m.size(m.dialog) == (320, 200), f'page {page}: after both, the sheet is on the bottom again ({m.top()})')
        expect(m.shown() == (PAGE2 if page == 2 else PAGE1), f'page {page}: the rows have not moved')
        m.relayout_all()
        expect(m.top() == SHEET_Y and m.shown() == (PAGE2 if page == 2 else PAGE1), f'page {page}: and a relayout keeps it')

    # -- 6. the end of the dialog, and a new one --------------------------------------------------------------------------------
    m = PM(); m.open(); m.click_more()
    fn, c = m.bound[(m.dialog, O['EVT_DESTROY'])]
    m.call(fn, a0=c, a1=0, count=200000)
    m.sync(); before = m.shown(); top = m.top()
    for w, e in ((m.rows[MORE], O['EVT_CLICK']), (m.rows[BACK], O['EVT_CLICK']), (m.dialog, O['EVT_WINDOW_TO_BG'])):
        fnm, cm = m.handlers_of(w, e)[-1]
        m.call(fnm, a0=cm, a1=0, count=400000)
        expect(m.shown() == before and m.top() == top and not any(c_[0] in ('widget_move', 'widget_resize') for c_ in m.calls), f'after the destroy the {m.name(w)} handler ({e:#x}) finds no dialog of ours and touches nothing')
    m2 = PM(); m2.open(); m2.click_more(); m2.open()
    expect(m2.shown() == PAGE1 and m2.size(m2.dialog) == (320, 200) and m2.top() == SHEET_Y, 'a dialog opened again starts on page 1')
    stale = PM(); stale.open(); stale.click_more()
    other = stale.alloc(0x80); stale.call(fn, a0=other, a1=0, count=200000)
    stale.click_back()
    expect(stale.shown() == PAGE1, 'the destroy of another dialog leaves the state alone')

    # -- 7. kill switch and failures: the stock menu ------------------------------------------------------------------------------
    def untouched(m, what, inert=True):
        moves = [c for c in m.calls if c[0] in ('widget_move', 'widget_resize', 'widget_restack', 'widget_set_visible', 'widget_set_sensitive', 'image_base_set_image')]
        expect(m.shown() == list(range(7)) and m.stacked()[:7] == list(range(7)) and all(m.dead(i) for i in (MORE, BACK)) and m.size(m.dialog) == (320, 350) and m.top() == DIALOG_Y and not moves,
               f'{what}: the stock menu, nothing moved ({m.shown()}, {m.size(m.dialog)}, y {m.top()}, {moves[:2]})')
        expect(m.stock_kept(), f'{what}: the stock handlers are bound')
        if inert:   # whatever handler the failed start left behind does nothing
            for w, e, fn, c in m.reg[len(m.stock_reg):]:
                m.call(fn, a0=c, a1=0, count=400000)
                expect(not any(x[0] in ('widget_move', 'widget_resize', 'widget_set_visible') for x in m.calls) and m.top() == DIALOG_Y, f'{what}: its leftover {m.name(w)} handler {e:#x} calls nothing')
    m = PM(); m.present.add(KILL); ret = m.open()
    untouched(m, 'kill switch'); expect(ret == 0 and ('access', KILL) in m.calls and not any(c[0] == 'widget_lookup' for c in m.calls) and m.reg == m.stock_reg, 'kill switch: nothing but the file check after the stock init')
    m = PM(); m.init_ret = 0x10; ret = m.open()
    untouched(m, 'stock init failed'); expect(ret == 0x10 and m.names() == ['stock_playmore_resume'], 'a failed stock init: its result, nothing else')
    m = PM(); m.call(PSYMS['m1pod_playmore_init'], a0=0, a1=0, count=200000)
    expect(m.names() == ['stock_playmore_resume'], 'no dialog: nothing but the stock init')
    for missing in ('pod_more', 'pod_back', 'pod_more_label', 'pod_back_label', 'scrlabel1', 'label1_msg', 'playmore_listview', 'playmore_scrollview', 'scroll_bar_m', 'listitem3'):
        m = PM(); del m.widgets[missing]; m.open(); untouched(m, f'no {missing}')
    m = PM(); m.setword(m.rows[SEARCH] + 0x44, m.lv); m.open(); untouched(m, 'a row outside the scroll_view')
    m = PM(); m.kids(m.sv, m.rows[:7]); m.open(); untouched(m, 'seven rows in the scroll_view (an asset without pod_more)')
    m = PM(); m.kids(m.sv, m.rows[:8]); m.open(); untouched(m, 'eight rows in the scroll_view (an asset without pod_back)')
    m = PM(); m.kids(m.sv, m.rows + [m.alloc(0x80)]); m.open(); untouched(m, 'ten children in the scroll_view')
    for key in PM_TEXTS:
        m = PM(); m.tr_fail = {key}; m.open(); untouched(m, f'the text {key!r} cannot be set')
    for which in ('pod_more', 'pod_back', 'bg', 'destroy'):
        m = PM(); m.bind_fail = which; m.open(); untouched(m, f'the {which} handler cannot be bound')
    m = PM(); m.bind_fail = 'pod_back'; m.open()
    fn, c = m.bound[(m.dialog, O['EVT_DESTROY'])]      # the destroy handler a failed start left behind does nothing
    m.call(fn, a0=c, a1=0, count=200000)
    expect(m.names() == [], 'a failed start leaves nothing to clean up: its destroy handler calls nothing')

    # -- 8. the texts in every language, and the room they have ------------------------------------------------------------------------
    stock_raw = os.path.join(paths.find_stock(paths.ZIP), RAW)
    built = {f[:-4]: dict(awtk_strings.load(os.path.join(WORK, RAW, 'strings', f))) for f in sorted(os.listdir(os.path.join(WORK, RAW, 'strings')))}
    font = Ttf(os.path.join(WORK, RAW, 'fonts', 'default.ttf'))
    th = awtk_style.parse(open(os.path.join(WORK, RAW, 'styles', 'default.bin'), 'rb').read())
    row_px = th.find('hscroll_label', 'srlabel_item_white_style', 'normal')[0].get('font_size')
    tree = awtk_ui.parse(open(os.path.join(WORK, RAW, 'ui/dialog/playmore_dialog.bin'), 'rb').read())
    more_l, back_l, more_c, back_c = (tree.find(n) for n in ('pod_more_label', 'pod_back_label', 'pod_more_chev', 'pod_back_chev'))
    speed_l, note_l, badges = tree.find('scrlabel1'), tree.find('label1_msg'), [tree.find(n) for n in ('img_1x', 'img_1_25x', 'img_1_5x', 'img_2x')]
    note_px = int(note_l.get('style:normal:font_size'))
    over = {'more': [], 'speed': [], 'note': []}
    for loc in pod_i18n.ALL_TABLES:
        for key in PM_TEXTS:
            expect(built[loc][key] == pod_i18n.TEXT[key][pod_i18n.table_for(loc)], f'{loc}: {key!r} is in the table as {pod_i18n.TEXT[key][pod_i18n.table_for(loc)]!r}')
        if loc in pod_i18n.LOCALES:
            w = StbText(font, row_px).layout(built[loc]['More'])[1]
            if more_l.x + w > more_c.x - 8: over['more'].append((loc, w))
            w = StbText(font, row_px).layout(built[loc]['Speed'])[1]
            if speed_l.x + w > speed_l.x + speed_l.w: over['speed'].append((loc, w))
            w = StbText(font, note_px).layout(built[loc]['Files below 48 kHz only'])[1]
            if note_l.x + w > note_l.x + note_l.w: over['note'].append((loc, w))
        m = PM(); m.set_language(loc); m.open()
        for key, label in (('More', 'pod_more_label'), ('More', 'pod_back_label'), ('Speed', 'scrlabel1'), ('Files below 48 kHz only', 'label1_msg')):
            want = pod_i18n.TEXT[key][pod_i18n.table_for(loc)].encode('utf-8').decode('latin-1')
            expect(('widget_set_tr_text', m.nodes[label], key) in m.calls and ('widget_set_text_utf8', m.nodes[label], want) in m.calls, f'{loc}: {label} reads {want!r}')
    expect(not over['more'] and row_px == 20, f'"More" fits between the label x {more_l.x} and the chevron at x {more_c.x} in all 13 languages at {row_px} px ({over["more"]})')
    wide = lambda key, px: max((StbText(font, px).layout(built[l][key])[1], l) for l in pod_i18n.LOCALES)
    expect(not over['speed'] and wide('Speed', row_px)[0] > 40, f'"Speed" fits the {speed_l.w} px label in all 13 languages at {row_px} px (widest {wide("Speed", row_px)}; over: {over["speed"]})')
    expect(not over['note'] and wide('Files below 48 kHz only', note_px)[0] > 80, f'the note fits its {note_l.w} px at {note_px} px in all 13 languages (widest {wide("Files below 48 kHz only", note_px)}; over: {over["note"]})')
    expect(more_l.w == 200 and more_l.x + more_l.w <= more_c.x and back_l.x >= back_c.x + back_c.w, 'the More label ends before its chevron; the back label starts after its chevron')
    expect(speed_l.x + speed_l.w <= badges[0].x and note_l.y >= speed_l.y + speed_l.h and note_l.y >= 8 + 20, 'the speed label ends before the first badge, the note sits under the label and the 20 px badge pictures')
    expect(all(a.x + a.w <= b.x for a, b in zip(badges, badges[1:])) and badges[-1].x + badges[-1].w <= 310 and note_l.x + note_l.w <= 310 and all(b.w == 36 and b.h == 50 and b.y == 0 for b in badges),
           'the four badges (36 px, 50 px high) do not overlap and end inside the 310 px row; the note too')

    # -- 9. the assets, both themes ---------------------------------------------------------------------------------------------------
    stock_ui = awtk_ui.parse(open(os.path.join(stock_raw, 'ui/dialog/playmore_dialog.bin'), 'rb').read())
    speed_names = ('scrlabel1', 'label1_msg', 'img_1x', 'img_1_25x', 'img_1_5x', 'img_2x')
    for theme in ('default', 'theme1'):
        built_ui = awtk_ui.parse(open(os.path.join(WORK, 'rootfs/release/assets', theme, 'raw/ui/dialog/playmore_dialog.bin'), 'rb').read())
        stock_t = stock_ui if theme == 'default' else awtk_ui.parse(open(os.path.join(stock_raw, '..', '..', theme, 'raw/ui/dialog/playmore_dialog.bin'), 'rb').read())
        geo = lambda t: [(w.type, w.name, w.x, w.y, w.w, w.h) for w in t.walk() if not w.name.startswith(('pod_more', 'pod_back')) and w.name not in speed_names]
        expect(geo(built_ui) == geo(stock_t), f'{theme}: every stock widget but the speed row\'s keeps its type, name and rectangle (the M1+ Pod ones are added)')
        expect([(w.type, w.name) for w in built_ui.walk() if w.name in speed_names] == [(w.type, w.name) for w in stock_t.walk() if w.name in speed_names],
               f'{theme}: the speed row\'s widgets keep their type and name')
        expect([(built_ui.find(n).x, built_ui.find(n).y, built_ui.find(n).w, built_ui.find(n).h) for n in speed_names] ==
               [(48, 8, 96, 20), (48, 31, 262, 14), (148, 0, 36, 50), (188, 0, 36, 50), (228, 0, 36, 50), (268, 0, 36, 50)], f'{theme}: the speed row\'s rectangles')
        sv = built_ui.find('playmore_scrollview')
        expect([c.name for c in sv.children] == STOCK_NAMES + ['pod_more', 'pod_back'], f'{theme}: pod_more and pod_back are the eighth and ninth children of the scroll_view, after the seven stock rows')
        hl = built_ui.get('highlight')
        expect(hl is not None and hl.startswith('default(alpha=') and hl.endswith(')') and 40 <= int(hl[len('default(alpha='):-1]) <= 200, f'{theme}: the dialog dims the page under it with the "default" highlighter ({hl!r})')
        imgs = {f[:-4] for f in os.listdir(os.path.join(WORK, 'rootfs/release/assets/default/raw/images/xx'))}
        for name, kids in (('pod_more', ['pod_more_icon', 'pod_more_label', 'pod_more_chev']), ('pod_back', ['pod_back_chev', 'pod_back_label'])):
            row = built_ui.find(name)
            expect(row.type == 'list_item' and row.get('visible') == 'false' and row.get('sensitive') == 'false', f'{theme}: {name} starts hidden and insensitive')
            expect([c.name for c in row.children] == kids and all(c.get('sensitive') == 'false' for c in row.children if c.type == 'image'), f'{theme}: {name}\'s children are {kids}, the pictures insensitive')
            expect({c.get('image') for c in row.children if c.type == 'image'} <= imgs, f'{theme}: the images {name} uses exist')
        expect(built_ui.find('pod_more_chev').get('image') == 'right_arrow' and built_ui.find('pod_back_chev').get('image') == 'return', f'{theme}: the stock chevrons: right_arrow (grey) for More, return for the back header')
        ref = built_ui.find('listitem2')
        expect([(k, v) for k, v in built_ui.find('pod_more').props if k.startswith('style')] == [(k, v) for k, v in ref.props if k.startswith('style')], f'{theme}: pod_more is styled as the Add to playlist row')
        diff = [k for k, v in built_ui.find('pod_back').props if k.startswith('style') and (k, v) not in [(a, b) for a, b in ref.props]]
        expect(diff == ['style:normal:border'] or all(k == 'style:normal:border' for k in diff), f'{theme}: pod_back is styled as the Add to playlist row, but for its hairline ({diff})')
        lab = built_ui.find('scrlabel6')
        reds = {lab.get(f'style:{s}:text_color') for s in ('normal', 'pressed', 'over', 'disable', 'focused')}
        expect(reds == {'#FF5A4F'}, f'{theme}: the Delete label is red in every state ({reds})')
        lum = lambda c: sum(k * (v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4) for k, v in zip((0.2126, 0.7152, 0.0722), (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))))
        contrast = lambda a, b: (max(lum(a), lum(b)) + 0.05) / (min(lum(a), lum(b)) + 0.05)
        expect(contrast('#FF5A4F', '#000000') >= 4.5 and contrast('#FF5A4F', built_ui.find('listitem6').get('style:pressed:bg_color')) >= 4.5,
               f'{theme}: the red keeps 4.5:1 on the black sheet ({contrast("#FF5A4F", "#000000"):.2f}) and on the pressed row ({contrast("#FF5A4F", built_ui.find("listitem6").get("style:pressed:bg_color")):.2f})')
        expect(built_ui.find('listitem4').get('style:normal:border') == 'none' and built_ui.find('pod_back').get('style:normal:border') == 'none' and built_ui.find('listitem0').get('style:normal:border') == 'top'
               and all(built_ui.find(n).get('style:normal:border') == 'top' for n in ('listitem1', 'listitem2', 'listitem3', 'listitem5', 'listitem6', 'pod_more')),
               f'{theme}: the hairlines follow the new order (the first row of each page has none, A-B repeat has one)')
        expect(built_ui.type == 'dialog' and (built_ui.x, built_ui.y, built_ui.w, built_ui.h) == (0, 130, 320, 350),
               f'{theme}: the dialog is the stock 320 x 350 sheet at y 130 (the kill switch shows the stock menu)')
