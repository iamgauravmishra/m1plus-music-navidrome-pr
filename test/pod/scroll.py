"""List gestures (patch/scroll.c): demo's own stock scroll_view, list_item and widget pointer-dispatch code (the window
manager's entry points widget_on_pointer_down / _move / _up and everything below them: hit testing, grab, the abort), executed
under Unicorn on a tree of real widget structs (list_view > scroll_view > list_item rows), with only the leaves mocked (timers,
animators, the emitter, widget states). Every scenario runs twice: with the slot of g_scroll_view_vtable zeroed, which is the
stock app (the failing gestures reproduce), and with the payload's hook in it (they are fixed); the gestures that must keep
working are checked in both."""
import struct
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

SLOT = pod.SCROLL_SLOT
CLICK = O['EVT_CLICK']
ROW_H, ROWS, SV_W, SV_H = 64, 20, 310, 450
KILL_SD, KILL_FLASH = '/mnt/mmc/m1pod-off', '/mnt/data/m1pod-off'



class SM(StockEventMachine):
    """The machine: demo's code and data, the payload, and the gesture mocks. log holds what the last pointer event caused."""
    EXTRA = ("widget_animator_destroy",)

    def __init__(self, hooked):
        super().__init__()
        self.u.mem_write(SLOT, struct.pack("<I", PSYMS["m1pod_scroll_event"] if hooked else 0))

    def build(self, yslide=1, xslide=0, snap=0, button=False):
        """root > list_view > scroll_view > ROWS list_item rows; row 0 also holds a switch image and, with button, an up-arrow button."""
        self.root = self.widget(LV_VT, 0, 0, 320, SV_H)
        self.lv = self.widget(LV_VT, 0, 0, 320, SV_H, self.root)
        self.sv = sv = self.widget(SV_VT, 0, 0, SV_W, SV_H, self.lv)
        self.kids(self.root, [self.lv]); self.kids(self.lv, [sv])
        self.rows = [self.widget(LI_VT, 0, i * ROW_H, SV_W, ROW_H, sv, emitter=True) for i in range(ROWS)]
        self.kids(sv, self.rows)
        self.switch = self.widget(IMG_VT, 240, 12, 40, 40, self.rows[0])
        kids = [self.switch]
        self.button = None
        if button:
            self.button = self.widget(BTN_VT, 180, 0, 40, ROW_H, self.rows[0], emitter=True); kids.append(self.button)
        self.kids(self.rows[0], kids)
        for off, v in ((0x78, SV_W), (0x7c, ROWS * ROW_H), (0xec, 0x611450)): self.setword(sv + off, v)   # virtual size; scroll_view_create's clamp hook
        self.u.mem_write(sv + 0x90, bytes([xslide, yslide, snap]))
        speed = self.word(0x759814); self.setword(sv + 0x88, speed); self.setword(sv + 0x8c, speed)   # the speed scales scroll_view_create stores

    # ---- the window manager's pointer events
    def play(self, steps):
        """steps: (d|m|u, x, y[, ms since the last event]); returns the rows that got a click, in order."""
        out = []
        for s in steps:
            self.pointer(s[0], s[1], s[2], *s[3:])
            out += self.clicks()
        return out

    def clicks(self): return [e[1] for e in self.log if e[0] == 'emit' and e[2] == CLICK]
    def yoff(self): return struct.unpack('<i', self.u.mem_read(self.sv + 0x84, 4))[0]
    def wa(self): return self.word(self.sv + 0xe8)
    def row_at(self, y): return self.rows[(y + self.yoff()) // ROW_H]
    def row_flags(self, row): return tuple(self.u.mem_read(row + 0x7c, 3))     # list_item: cancelled, pressed, down


def machine(hooked, steps=(), **build):
    m = SM(hooked); m.build(**build); m.clicked = m.play(steps)
    return m


FLICK = [('d', 100, 300, 0), ('m', 100, 270), ('m', 100, 200), ('u', 100, 150)]   # a quick swipe up that leaves a fling running
TAP = [('d', 100, 200, 0), ('u', 100, 200, 60)]


def run(ctx):
    expect = ctx.expect
    # -- the data word and everything the payload relies on
    d = open(DEMO, 'rb').read(); image = bytearray(d)
    expect(struct.unpack_from('<I', d, pod.fileoff(image, SLOT))[0] == PSYMS['m1pod_scroll_event'] and 0xb00000 <= PSYMS['m1pod_scroll_event'] < 0xb00000 + MANIFEST['payload_len'],
           'the built demo has m1pod_scroll_event in the on_event_before_children slot of g_scroll_view_vtable')
    expect(MANIFEST['scroll_edit'] == [hex(SLOT), '0x0', hex(PSYMS['m1pod_scroll_event'])], 'the manifest records the one data word')
    for a, old, what in pod.SCROLL_PINS:   # every pinned word is still the stock word, but the slot itself
        got = struct.unpack_from('<I', d, pod.fileoff(image, a))[0]
        expect(got == (PSYMS['m1pod_scroll_event'] if a == SLOT else old), f'pinned {a:#x} ({what})')

    # -- 1. a swipe never plays a song --------------------------------------------------------------------------------
    holes = [   # the stock app clicks the row under the press in every one of these; each row cancels itself only on a MOVE of 11 px or more
        ('a MOVE of 5 px, UP 62 px away', [('d', 100, 200, 0), ('m', 100, 205), ('u', 100, 262)]),
        ('UP 80 px away, no MOVE at all', [('d', 100, 200, 0), ('u', 100, 280, 40)]),
        ('UP 12 px away, no MOVE', [('d', 100, 200, 0), ('u', 100, 212, 60)]),
        ('MOVEs of 2 px (8 px in all), UP 24 px away', [('d', 100, 200, 0)] + [('m', 100, 200 + 2 * i) for i in range(1, 5)] + [('u', 100, 224)]),
        ('a quick flick: MOVE 9 px, UP 100 px away', [('d', 100, 300, 0), ('m', 100, 291), ('u', 100, 200, 16)]),
        ('a MOVE of 9 px, UP 10 px from the press', [('d', 100, 200, 0), ('m', 100, 209), ('u', 100, 210, 40)]),
    ]
    for name, steps in holes:
        stock, hooked = machine(False, steps), machine(True, steps)
        expect(len(stock.clicked) == 1, f'STOCK {name}: the row under the press gets a click ({len(stock.clicked)})')
        expect(hooked.clicked == [], f'HOOKED {name}: no click ({len(hooked.clicked)})')
        row = hooked.rows[steps[0][2] // ROW_H]
        expect(hooked.row_flags(row) == (0, 0, 0) and hooked.states.get(row) in (None, 'normal'), f'HOOKED {name}: the row dropped its press ({hooked.row_flags(row)})')
        expect(stock.yoff() == hooked.yoff() and (stock.wa() != 0) == (hooked.wa() != 0), f'{name}: the scroll (offset, fling) is the stock one')
    # the quick flick still flings, with and without the hook
    stock, hooked = machine(False, FLICK), machine(True, FLICK)
    expect(stock.wa() != 0 and hooked.wa() != 0 and stock.yoff() == hooked.yoff() and stock.clicked == hooked.clicked == [], 'a flick starts the same scroll animation and is no click')

    # drag out and back near the start: a MOVE past the threshold cancels in stock (the row and the scroll_view); the hook adds nothing
    for name, steps in (('out 40 px and back to 3 px', [('d', 100, 200, 0), ('m', 100, 240), ('m', 100, 203), ('u', 100, 203)]),
                        ('a MOVE sampled 62 px out and the next one back', [('d', 100, 200, 0), ('m', 100, 202), ('m', 100, 262), ('m', 100, 202), ('u', 100, 203)])):
        stock, hooked = machine(False, steps), machine(True, steps)
        expect(stock.clicked == [] and hooked.clicked == [], f'{name}: no click, with and without the hook')

    # a genuine tap, a little shaky, or a long press, still clicks the row under the finger (both)
    for name, steps in (('tap', TAP), ('tap with 3 px of jitter', [('d', 100, 200, 0), ('m', 102, 202), ('u', 103, 203, 70)]),
                        ('9 px of movement', [('d', 100, 200, 0), ('u', 100, 209, 70)]), ('a long press, held still', [('d', 100, 200, 0), ('u', 100, 200, 1500)])):
        stock, hooked = machine(False, steps), machine(True, steps)
        expect(stock.clicked == [stock.rows[3]] and hooked.clicked == [hooked.rows[3]], f'{name}: one click on the pressed row, with and without the hook')
    # the 30 ms press highlight timer is still armed by a DOWN on an idle list
    h = machine(True); h.pointer('d', 100, 200)
    expect(h.row_flags(h.rows[3]) == (0, 1, 1) and h.word(h.sv + 0x4c) == h.rows[3] and h.word(h.rows[3] + 0x78) == 0x777,
           'a DOWN on an idle list presses the row, grabs and arms the highlight timer, as stock')

    # a slow drag scrolls and ends without a click, as before
    SLOW = [('d', 100, 300, 0)] + [('m', 100, 300 - 6 * i) for i in range(1, 25)] + [('u', 100, 150, 400)]
    stock, hooked = machine(False, SLOW), machine(True, SLOW)
    expect(stock.yoff() > 100 and stock.yoff() == hooked.yoff() and stock.clicked == hooked.clicked == [],
           f'a slow drag scrolls the list ({stock.yoff()} / {hooked.yoff()} px) with no click, with and without the hook')

    # what the hook leaves alone: a horizontal drag in a vertical list (a slider in a row), a list that cannot scroll, a page-snapping scroll_view
    for name, steps, kw in (('a horizontal drag of 75 px in a vertical list', [('d', 100, 200, 0), ('m', 130, 201), ('u', 175, 201, 60)], {}),
                            ('a swipe on a list that cannot scroll', [('d', 100, 200, 0), ('u', 100, 280, 40)], dict(yslide=0)),
                            ('a swipe on a page-snapping scroll_view', [('d', 100, 200, 0), ('u', 100, 280, 40)], dict(snap=1))):
        stock, hooked = machine(False, steps, **kw), machine(True, steps, **kw)
        expect(len(stock.clicked) == 1 and len(hooked.clicked) == 1, f'{name}: as stock')

    # -- 2. a touch on a coasting list stops it and presses nothing ---------------------------------------------------
    for hooked in (False, True):
        tag = 'HOOKED' if hooked else 'STOCK'
        m = machine(hooked, FLICK)
        wa = m.wa()
        expect(wa != 0 and m.word(wa + 0x28) == 1, f'{tag}: the fling leaves a running scroll animator')
        row = m.row_at(200)
        m.pointer('d', 100, 200, 100)
        down = list(m.log)
        m.pointer('u', 100, 200, 60)
        if not hooked:
            expect(m.clicks() == [row], 'STOCK: a tap on the coasting list clicks the row under the finger')
            expect(m.wa() == wa and not any(e[0] == 'anim_destroy' for e in down), 'STOCK: the touch does not stop the coast')
        else:
            expect(m.clicks() == [], f'HOOKED: a tap on the coasting list clicks nothing ({len(m.clicks())})')
            expect(m.wa() == 0 and ('anim_destroy', wa) in down and m.word(wa + 0x28) == 0, 'HOOKED: the animator is destroyed and the scroll_view forgets it')
            expect(('simple', m.sv, 0x14f) in down and ('simple', m.sv, 0x151) in down, 'HOOKED: the stock end-of-scroll events are sent')
            expect(m.row_flags(row) == (0, 0, 0) and m.states.get(row) in (None, 'normal') and m.word(m.sv + 0x4c) == 0, 'HOOKED: the row was never pressed')
            y = m.yoff()
            expect(m.play(TAP) == [m.row_at(200)] and m.yoff() == y, 'HOOKED: the next plain tap clicks the row, and the list stays')
    # a drag that starts on a coasting list scrolls it from there (stock: the list ignores the finger until the animation ends)
    for hooked in (False, True):
        m = machine(hooked, FLICK)
        before = m.yoff()
        m.play([('d', 100, 300, 100)] + [('m', 100, 300 - 8 * i) for i in range(1, 12)] + [('u', 100, 212, 400)])
        moved = abs(m.yoff() - before)
        if hooked: expect(moved > 0 and m.wa() == 0 and m.clicks() == [], f'HOOKED: a drag that starts on the coasting list scrolls it ({moved} px)')
        else: expect(moved == 0, f'STOCK: the finger cannot move the coasting list ({moved} px)')
    # a coast that is not a live animator of the list is left to stock (a stale pointer is never destroyed)
    m = machine(True, FLICK); an = m.wa(); m.setword(an + 0x28, 4)   # finished
    m.play(TAP)
    expect(not any(e[0] == 'anim_destroy' for e in m.log) and m.wa() == an, 'an animator that is not running is left to stock')

    # -- 3. the other widgets in a row: the up-arrow button and the switch image of the Main Menu rows ---------------------
    for hooked in (False, True):
        tag = 'HOOKED' if hooked else 'STOCK'
        m = machine(hooked, [('d', 200, 30, 0), ('u', 200, 30, 60)], button=True)
        expect(m.clicked[:1] == [m.button], f'{tag}: a tap on the up-arrow button clicks the button first ({len(m.clicked)} clicks)')
        m = machine(hooked, [('d', 255, 30, 0), ('u', 255, 30, 60)], button=True)
        expect(m.clicked == [m.rows[0]], f'{tag}: a tap on the switch image clicks its row')
        m = machine(hooked, [('d', 100, 30, 0), ('u', 100, 30, 60)], button=True)
        expect(m.clicked == [m.rows[0]], f'{tag}: a tap on the row text clicks its row')
    tap = [('d', 200, 30, 0), ('u', 200, 30, 60)]
    expect(machine(False, tap, button=True).clicked == machine(True, tap, button=True).clicked, 'a tap on the arrow: the same clicks with and without the hook')
    for name, steps in (('arrow', [('d', 200, 30, 0), ('u', 200, 100, 60)]), ('switch', [('d', 255, 30, 0), ('m', 255, 36), ('u', 255, 100, 40)])):
        stock, hooked = machine(False, steps, button=True), machine(True, steps, button=True)
        expect(stock.clicked and hooked.clicked == [], f'a swipe that starts on the {name} (UP 70 px away): stock clicks {len(stock.clicked)}, the hook none')

    # -- 4. the kill switch, the syscalls and the cost ------------------------------------------------------------------
    for kill in (KILL_SD, KILL_FLASH):
        m = SM(True); m.build(); m.present.add(kill)
        expect(len(m.play([('d', 100, 200, 0), ('u', 100, 280, 40)])) == 1, f'kill switch {kill}: a late-drag release is stock (the row clicks)')
        m = SM(True); m.build(); m.present.add(kill); m.play(FLICK)
        expect(m.play(TAP) == [m.row_at(200)] and m.wa() != 0, f'kill switch {kill}: a touch on a coasting list is stock (the row clicks, the coast runs)')
    m = SM(True); m.build()
    seen = []
    def probe(steps):
        for s in steps:
            m.pointer(s[0], s[1], s[2], *s[3:])
            seen.extend(c for c in m.calls if c[0] == 'access')
    probe(TAP + [('d', 100, 200, 100)] + [('m', 100, 200 + i) for i in range(1, 8)] + [('u', 100, 207, 60)] + SLOW)
    expect(seen == [], 'taps, short touches and a normal drag: the kill switch is never read')
    probe([('d', 100, 200, 0), ('u', 100, 280, 40)])
    expect(seen == [('access', KILL_SD), ('access', KILL_FLASH)], f'the first late-drag release reads the kill switch, both files, once: {seen}')
    probe([('d', 100, 200, 0), ('u', 100, 280, 40)] + [('d', 100, 200, 100), ('u', 100, 270, 40)])
    expect(len(seen) == 2, 'and never again')
    # instructions of the hook itself (called directly, on a fresh list)
    c = SM(True); c.build()
    e = c.alloc(0x30); c.u.mem_write(e, bytes(0x30))
    cost = {}
    for kind in ('m', 'd', 'u'):
        c.setword(e, POINTER_EVT[kind]); c.call(PSYMS['m1pod_scroll_event'], a0=c.sv, a1=e, count=1000); cost[kind] = c.icount
        expect(c.calls == [], f'an idle {kind} event: the hook calls nothing')
    expect(cost['m'] <= 16 and cost['d'] <= 40 and cost['u'] <= 20, f'hook cost per event, instructions: MOVE {cost["m"]}, idle DOWN {cost["d"]}, idle UP {cost["u"]}')
    print(f'  hook cost per event (instructions, incl. call/return): MOVE {cost["m"]}, idle DOWN {cost["d"]}, idle UP {cost["u"]}')
