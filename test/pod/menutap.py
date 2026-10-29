"""Taps on the Main Menu page (patch/menu.c): demo's own widget pointer dispatch, list_item, button and scroll_view code,
executed under Unicorn on a tree of real widget structs laid out from the built asset (ui/m1pod_mainmenu.bin), with
the payload's click handlers bound by menu_custom_opened. Only the leaves are mocked (the emitter: an emitted event is
queued with a copy of its bytes and handed to the handlers the payload bound, after the stock event code returned;
timers, animators, widget states). One tap must do one thing: a tap on the up arrow zone moves the item up and does not
toggle it, a tap anywhere else on the row toggles it and moves nothing."""
import struct
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

VT = {'list_view': LV_VT, 'scroll_view': SV_VT, 'list_item': LI_VT, 'button': BTN_VT, 'image': IMG_VT, 'window': LV_VT}
CLICK = O['EVT_CLICK']
WIN_Y = 30                       # the window sits under the 30 px system bar: screen y = window y + 30
MENU_FILE = '/mnt/data/m1pod-menu'
F_VIS, F_SENS = 4, 8


class TapMachine(StockEventMachine):
    """The Main Menu page as real widget structs, the payload opened on it, stock pointer dispatch on top."""
    WIN_Y, DELIVER = WIN_Y, True

    def __init__(self, data=None):
        super().__init__()
        self.u.mem_write(0x97a330, struct.pack('<I', PSYMS['m1pod_scroll_event']))   # the list gesture hook, as built (patch/scroll.c)
        self.widgets = {}
        self.tree = asset_tree_raw()
        self.n = len(pod_pages.ITEMS)
        self.build()
        if data is not None: self.fs[MENU_FILE] = data
        self.on_open()

    def leaf(self, name, a0, a1, a2, a3, sp):
        if name == 'widget_dispatch_simple_event': return 0
        return super().leaf(name, a0, a1, a2, a3, sp)

    # ---- the widget tree, from the asset
    def widget(self, vt, node, parent=0, name=None, emitter=False):
        a = self.alloc(0x180); self.u.mem_write(a, bytes(0x180))
        flags = 0xd & ~(F_SENS if node.get('sensitive') == 'false' else 0)
        for off, v in ((0, node.x), (4, node.y), (8, node.w), (0xc, node.h), (0x24, flags), (0x44, parent), (0x70, vt)): self.setword(a + off, v)
        if emitter:
            em = self.alloc(0x20); self.owner[em] = a; self.setword(a + 0x5c, em)
        if node.name:
            self.widgets[node.name] = a
            self.props[(a, 'x')], self.props[(a, 'w')] = node.x, node.w   # widget_get_prop_int, as the payload reads the arrow's rectangle
        return a

    def build(self):
        t = self.tree
        win = self.widget(VT['window'], t, 0)
        self.setword(win + 4, WIN_Y); self.setword(win + 8, 320); self.setword(win + 0xc, 450)
        self.root = win
        lv_n = next(c for c in t.children if c.type == 'list_view')
        lv = self.widget(LV_VT, lv_n, win)
        sv_n = lv_n.children[0]
        self.sv = sv = self.widget(SV_VT, sv_n, lv)
        self.widgets['pod_scrollview'] = sv
        rows = []
        for r in sv_n.children:
            row = self.widget(LI_VT, r, sv, emitter=True)
            kids = []
            for c in r.children:
                kids.append(self.widget(VT[c.type] if c.type in VT else IMG_VT, c, row, emitter=c.type == 'button'))
            self.kids(row, kids)
            rows.append(row)
        self.kids(sv, rows)
        self.kids(lv, [sv]); self.kids(win, [lv])
        for off, v in ((0x78, sv_n.w), (0x7c, len(rows) * pod_ui.ROW_H), (0xec, 0x611450)): self.setword(sv + off, v)   # virtual size; scroll_view_create's clamp hook
        self.u.mem_write(sv + 0x90, bytes([0, 1, 0]))
        speed = self.word(0x759814); self.setword(sv + 0x88, speed); self.setword(sv + 0x8c, speed)
        for nm in ('btn_return', 'btn_backtoplayer'): self.widgets[nm] = self.alloc(0x80)
        self.props[(sv, 'h')] = lv_n.h
        self.window = win

    def on_open(self):
        on_row = PSYMS['on_row']; rows_s = PSYMS[f'pod_rows_{pod_pages.SETTINGS_PAGE_INDEX}']
        mm_i = next(i for i, r in enumerate(pod_pages.SETTINGS_PAGE.rows) if r.action == pod_pages.ACT_PAGE and r.arg == pod_pages.MENUCFG_PAGE_INDEX)
        self.call(on_row, a0=rows_s + 12 * mm_i, count=3000000)
        self.sync()

    # ---- what the payload's mocked widget calls changed, written back into the structs the stock code reads
    def sync(self):
        for nm, a in self.widgets.items():
            if (a, 'y') in self.props: self.setword(a + 4, self.props[(a, 'y')])
            f = self.word(a + 0x24)
            if (a, 'visible') in self.props: f = f & ~F_VIS | (F_VIS if self.props[(a, 'visible')] else 0)
            if (a, 'sensitive') in self.props: f = f & ~F_SENS | (F_SENS if self.props[(a, 'sensitive')] else 0)
            self.setword(a + 0x24, f)

    # ---- the window manager's pointer events (StockEventMachine.pointer); the emitted events reach the payload's handlers
    def handled(self): self.sync()

    def play(self, steps):
        self.fired = []
        for s in steps: self.pointer(s[0], s[1], s[2], *s[3:])

    def tap(self, x, y): self.play([('d', x, y, 0), ('u', x, y, 60)])
    def file(self): return self.fs.get(MENU_FILE)
    def clicked(self): return [n for n, e in self.fired if e == CLICK]
    def row_y(self, i): return self.props.get((self.widgets[f'pod_row{i}'], 'y'), self.word(self.widgets[f'pod_row{i}'] + 4))


def asset_tree_raw():
    import awtk_ui
    return awtk_ui.parse(open(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui', 'm1pod_mainmenu.bin'), 'rb').read())


def run(ctx):
    expect, P = ctx.expect, pod_pages
    m = TapMachine()
    t = m.tree
    row0 = next(w for w in t.walk() if w.name == 'pod_row0')
    up0, sw0, lab0 = row0.find('pod_up0'), row0.find('pod_switch0'), next(c for c in row0.children if c.type == 'hscroll_label')
    ax, aw = up0.x, up0.w                                   # the arrow's zone: row-local x in [ax, ax + aw)
    mid = pod_ui.ROW_H // 2
    expect(aw >= 44 and up0.h == pod_ui.ROW_H, f'the arrow zone is the arrow\'s full touch target: x {ax}..{ax + aw - 1}, {aw} x {up0.h} px (at least 44 wide)')
    expect(ax + aw <= sw0.x and lab0.x + lab0.w <= ax, 'the label ends where the arrow zone starts, the zone ends where the switch starts')
    lv_y = t.find('pod_listview').y
    y_at = lambda i: lv_y + m.row_y(i) + mid   # window y of the middle of row i (the list is not scrolled)
    # the default list: items 1..6 shown (1 first, no arrow), 0 (Now Playing) and 7.. hidden
    expect(m.file() is None, 'a fresh page, the default list')
    print(f'  Main Menu arrow zone: row-local x {ax}..{ax + aw - 1}, switch x {sw0.x}..{sw0.x + sw0.w - 1}, label x {lab0.x}..{lab0.x + lab0.w - 1}')

    # 1. a tap on the arrow of item 3 (Artists): it moves up one place and does not toggle
    m = TapMachine()
    m.tap(ax + aw // 2, y_at(3))
    expect(m.clicked() == ['pod_row3'], f'the click is the row\'s alone, the arrow is no target ({m.clicked()})')
    expect(m.file() == b'132456x\n', f'a tap in the middle of the arrow moves the item up and nothing else ({m.file()!r}, clicks {m.clicked()})')
    for edge, what in ((ax, 'the first pixel'), (ax + aw - 1, 'the last pixel')):
        m = TapMachine(); m.tap(edge, y_at(3))
        expect(m.file() == b'132456x\n', f'a tap on {what} of the zone (x {edge}) moves up only ({m.file()!r})')
    # 2. everywhere else on the row: toggle only
    for x, what in ((ax - 1, 'one pixel left of the zone'), (ax + aw, 'one pixel right of the zone'), (lab0.x + 10, 'the label'),
                    (sw0.x + sw0.w // 2, 'the switch'), (4, 'the left edge'), (sw0.x + sw0.w + 5, 'the right margin')):
        m = TapMachine(); m.tap(x, y_at(3))
        expect(m.file() == b'12456x\n', f'a tap on {what} (x {x}) toggles the item off and moves nothing ({m.file()!r})')
    # 3. no arrow: the first shown row and a hidden row take the tap in the zone as a toggle
    m = TapMachine(); m.tap(ax + aw // 2, y_at(1))
    expect(m.file() == b'23456x\n', f'the first shown row has no arrow: a tap in the zone toggles it ({m.file()!r})')
    m = TapMachine(); m.tap(ax + aw // 2, y_at(7))
    expect(m.file() == b'1234567x\n', f'a hidden row: a tap in the zone toggles it on ({m.file()!r})')
    m = TapMachine(); m.tap(ax + aw // 2, y_at(0))
    expect(m.file() == b'1234560x\n', f'Now Playing, hidden by default: a tap in the zone shows it at the end ({m.file()!r})')
    # 4. one tap, one action, and the live re-arrange ran: the moved item is now where the item above was, the other moved down
    m = TapMachine(); m.tap(ax + aw // 2, y_at(3))
    expect(m.row_y(3) == 1 * pod_ui.ROW_H and m.row_y(2) == 2 * pod_ui.ROW_H, 'the page re-arranged at once after the arrow tap')
    y = y_at(3)    # item 3 now sits one row higher: its arrow zone is there, the item below it (2) now has an arrow too
    m.tap(ax + aw // 2, y)
    expect(m.file() == b'312456x\n', f'the click context is the item: the arrow of the item that moved moves that item again, to the top ({m.file()!r})')
    m.tap(ax + aw // 2, y_at(3))
    expect(m.file() == b'12456x\n', 'and now first, without an arrow: the same spot toggles it')
    # 5. a drag that starts on the arrow does nothing
    for name, steps in (('a swipe: moves of 25 and 50 px, the finger up 70 px away', [('d', ax + 10, y_at(3), 0), ('m', ax + 10, y_at(3) + 25), ('m', ax + 10, y_at(3) + 50), ('u', ax + 10, y_at(3) + 70, 40)]),
                        ('out and back', [('d', ax + 10, y_at(3), 0), ('m', ax + 10, y_at(3) + 40), ('m', ax + 10, y_at(3) + 2), ('u', ax + 10, y_at(3) + 2, 40)]),
                        ('a slow scroll',[('d', ax + 10, y_at(3), 0)] + [('m', ax + 10, y_at(3) + 6 * i) for i in range(1, 15)] + [('u', ax + 10, y_at(3) + 90, 300)])):
        m = TapMachine(); m.play(steps)
        expect(m.file() is None and not any(n.startswith('pod_row') and e == CLICK for n, e in m.fired), f'a drag on the arrow ({name}): no move, no toggle ({m.file()!r}, {m.clicked()})')
    # 5b. the pressed look: the arrow shows its _down art while the finger is down inside its zone, and goes back
    m = TapMachine(); up3 = m.widgets['pod_up3']
    m.play([('d', ax + 10, y_at(3), 0)])
    expect(m.states.get(up3) == 'pressed', 'a DOWN in the zone: the arrow shows pressed')
    m.play([('u', ax + 10, y_at(3), 60)])
    expect(m.states.get(up3) == 'normal' and m.file() == b'132456x\n', 'and the UP: normal again, the item moved')
    m = TapMachine(); up3 = m.widgets['pod_up3']
    m.tap(20, y_at(3))
    expect(up3 not in m.states, 'a DOWN outside the zone never touches the arrow')
    m = TapMachine(); up3 = m.widgets['pod_up3']
    m.tap(ax + 10, y_at(1))
    expect(m.widgets['pod_up1'] not in m.states, 'a row without an arrow never shows one pressed')
    for name, steps in (('a swipe', [('d', ax + 10, y_at(3), 0), ('m', ax + 10, y_at(3) + 25), ('m', ax + 10, y_at(3) + 50), ('u', ax + 10, y_at(3) + 70, 40)]),
                        ('a slow scroll', [('d', ax + 10, y_at(3), 0)] + [('m', ax + 10, y_at(3) + 6 * i) for i in range(1, 15)] + [('u', ax + 10, y_at(3) + 90, 300)])):
        m = TapMachine(); m.play(steps)
        expect(m.states.get(m.widgets['pod_up3']) in (None, 'normal'), f'{name} that starts on the arrow leaves no pressed look behind ({m.states.get(m.widgets["pod_up3"])})')
    # the next touch clears a pressed look that a lost UP left
    m = TapMachine(); m.play([('d', ax + 10, y_at(3), 0)]); m.states[m.widgets['pod_up3']] = 'pressed'
    m.queue = []; m.pointer('d', 20, y_at(5), 100)
    expect(m.states[m.widgets['pod_up3']] == 'normal', 'a new touch resets a stale pressed arrow')

    # 6. a failed save changes nothing, for either action
    for x in (ax + 5, 20):
        m = TapMachine(); m.fail.add(('write', MENU_FILE + '.tmp')); m.tap(x, y_at(3))
        expect(m.file() is None and m.row_y(3) == 2 * pod_ui.ROW_H, f'a failed save (tap at x {x}) is undone')
