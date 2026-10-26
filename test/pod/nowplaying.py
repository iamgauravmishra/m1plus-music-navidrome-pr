"""Now Playing: the playing_page_init hook and its timer (the tint, the remaining time, the rounded corners), the tone
formula and its contrast, the A-B marker immediates, and the geometry of the built page assets."""
import os, random, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import awtk_style, mod_icons, mod_lockscreen, mod_nowplaying as mn

KILL = '/mnt/mmc/m1pod-off'
INIT = pod.PLAYING_INIT                   # playing_page_init
COVER_SRC = pod.DATA['COVER_SRC'][0]
WIN = 0x24000000
EVT_DESTROY, EVT_AFTER_PAINT = O['EVT_DESTROY'], O['EVT_AFTER_PAINT']


class NowMachine(Machine):
    """Machine plus what the Now Playing code calls: the style API, the player's position, files read through stdio,
    the stock init the hook wraps."""
    def __init__(self):
        super().__init__()
        self.handlers[INIT + 12] = 'stock_playing_resume'
        self.styles = []          # (widget, "normal:bg_color", uint32)
        self.style_ret = 0
        self.pt = (30, 200, 1)    # get_playtimeandlength: pos, len, return value
        self.blobs = {}           # path -> bytes (fopen / fread / fclose)
        self.pos = {}
        self.stock_ret = 0
        self.opened = []

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address, '')
        a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        ret = None
        if name == 'stock_playing_resume':
            self.calls.append(('stock_playing_init', a0, a1)); ret = self.stock_ret
        elif name == 'widget_set_style':
            v = self.word(a2 + 8); self.calls.append(('widget_set_style', a0, self.read_cstr(a1), v))
            if self.style_ret == 0: self.styles.append((a0, self.read_cstr(a1), v))
            ret = self.style_ret
        elif name == 'value_set_uint32':
            self.setword(a0, 7); self.setword(a0 + 8, a1); ret = a0
        elif name == 'get_playtimeandlength':
            pos, ln, r = self.pt
            self.setword(a0, pos); self.setword(a1, ln); self.calls.append(('get_playtimeandlength',)); ret = r
        elif name == 'fopen' and self.read_cstr(a0) in self.blobs:
            path = self.read_cstr(a0); h = self.alloc(4); self.pos[h] = 0; self.fh = (h, path)
            self.opened.append(path); self.calls.append(('fopen', path, self.read_cstr(a1))); ret = h
        elif name == 'fread' and a3 in self.pos:
            data = self.blobs[self.fh[1]]; n = min(a1 * a2, len(data) - self.pos[a3])
            if n: self.u.mem_write(a0, data[self.pos[a3]:self.pos[a3] + n])
            self.pos[a3] += n; ret = n // a1
        elif name == 'fclose' and a0 in self.pos:
            ret = 0
        if ret is not None:
            self.icount += 1
            u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        return super()._hook(u, address, size, _)

    def page(self, labels=True, art=True):
        """The widgets of the page the hook looks up."""
        for n in (('np_remaining', 'label_playlen') if labels else ()) + (('img_playcover',) if art else ()): self.widget(n)
        return self.widgets

    def src(self, v): self.setword(COVER_SRC, v)

    def init(self, win=WIN, count=6000000):
        self.calls = []; self.icount = 0
        ret = self.call(INIT, a0=win, a1=0x55, count=count)
        return ret

    def tick(self, count=6000000): self.call(PSYMS['np_tick'], count=count); return self.calls

    def jpeg(self, path, data=b'cover-bytes' * 40, pix=None, size=(4, 4)):
        """A cover file: its bytes for the key, and what the stock loader decodes it to (RGBA8888)."""
        self.blobs[path] = data; self.present.add(path)
        w, h = size
        self.images['file://' + path] = (w, h, pix if pix is not None else bytes([200, 40, 40, 255]) * (w * h))
        self.load_image = 0

    def set_texts(self): return [(c[1], c[2]) for c in self.calls if c[0] == 'widget_set_text_utf8']
    def visible(self, name): return self.props.get((self.widgets[name], 'visible'))


def lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def contrast(fg, bg):
    a, b = sorted((lum(fg), lum(bg)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def run(ctx):
    expect = ctx.expect
    raw = os.path.join(WORK, 'rootfs', 'release/assets/default/raw')
    stock = open(os.path.join(paths.find_stock() or os.path.join(os.path.dirname(WORK), 'stock'), 'rootfs', pod.DEMO), 'rb').read()
    built = open(DEMO, 'rb').read()
    word = lambda b, a: struct.unpack_from('<I', b, pod.fileoff(b, a))[0]

    # ------------------------------------------------------------------ the hook is installed as pinned
    hook = MANIFEST['hook_playing']
    expect(hook['addr'] == INIT == 0x53d1e4 and hook['target'] == PSYMS['m1pod_playing_init'], 'the manifest records the Now Playing hook and its target')
    expect(pod.PLAYING_INIT_PROLOGUE == (0x3c1c004c, 0x279c6cec, 0x0399e021) and tuple(word(stock, INIT + 4 * i) for i in range(3)) == pod.PLAYING_INIT_PROLOGUE,
           'stock has the three PIC prologue words the hook pins (playing_page_init)')
    expect((word(built, INIT), word(built, INIT + 4), word(built, INIT + 8)) == (pod.j(PSYMS['m1pod_playing_init']), 0, pod.PLAYING_INIT_PROLOGUE[2]),
           'the built demo has `j m1pod_playing_init; nop` over the first two prologue words')
    expect(0x4c0000 + 0x6cec + INIT == pod.GP, 'the prologue computes $gp = 0xa03ed0')
    gp = struct.unpack_from('<4I', open(os.path.join(BUILD, 'patch.bin'), 'rb').read(), PSYMS['stock_playing_init_trampoline'] - pod.BASE)
    expect(gp == (0x3c1c0000 | pod.GP >> 16, 0x379c0000 | pod.GP & 0xffff, pod.j(INIT + 12), 0), 'the trampoline restores $gp and resumes at the 4th instruction')
    expect((COVER_SRC, O['COVER_SRC_BUSY'], O['COVER_SRC_EMBEDDED'], O['COVER_SRC_FOLDER'], O['COVER_SRC_CACHE'], O['RET_REPEAT']) == (0x97cad8, 1, 2, 3, 5, 8),
           'the cover source type word and its values, the repeat answer')

    # ------------------------------------------------------------------ A-B markers (five pinned immediates)
    edits = mn.marker_edits()
    expect(len(edits) == 5 and all(word(stock, a) == o and word(built, a) == n for a, (o, n) in edits.items()),
           'the five marker immediates are stock words in stock and the new ones in the build')
    sl = mn.SLIDER
    expect({a: n & 0xffff for a, (_, n) in edits.items()} == {mn.MARKER_X_SCALE: sl[2], mn.MARKER_X_OFFSET: sl[0], **{a: sl[1] + sl[3] // 2 + 7 for a in mn.MARKER_Y}},
           f'markers run x {sl[0]} + pos * {sl[2]} / len at y {sl[1] + sl[3] // 2 + 7} (bar centre + 7, as stock 357 + 7 = 364)')
    expect(all((word(built, a) >> 16) == (o >> 16) for a, (o, _) in edits.items()), 'only the 16-bit immediates change')
    expect(all(word(stock, a) == w and word(built, a) == w for a, w in mn.MARKER_PINS.items()), 'the two functions\' prologues and their call sites are pinned and untouched')

    # ------------------------------------------------------------------ installed hook: stock first, then ours
    m = NowMachine(); m.page(); m.src(0)
    ret = m.init()
    names = m.names()
    expect(ret == 0 and m.calls[0] == ('stock_playing_init', WIN, 0x55), f'the stock init runs first, with its arguments, and its result is returned ({names[:3]})')
    destroy = [c for c in m.calls if c[0] == 'widget_on' and c[2] == EVT_DESTROY]
    expect(len(destroy) == 1 and destroy[0][1] == WIN and destroy[0][3] == PSYMS['np_on_destroy'] and destroy[0][4] == WIN,
           'EVT_DESTROY is registered once on the window with the window as its context')
    expect(m.timers == [(PSYMS['np_tick'], O['NP_TICK_MS'])] and O['NP_TICK_MS'] == 500, 'one page timer, 500 ms, created once')
    paint = [c for c in m.calls if c[0] == 'widget_on' and c[2] == EVT_AFTER_PAINT]
    expect(len(paint) == 1 and paint[0][1] == m.widgets['img_playcover'] and paint[0][3] == PSYMS['np_on_art_paint'], 'the cover widget paints its corners')
    # the timer's first run is part of the init: no cover (type 0) -> the neutral tone, once
    expect(m.styles == [(WIN, 'normal:bg_color', O['NP_NEUTRAL'])], f'no cover file: the neutral tone ({[hex(x[2]) for x in m.styles]})')

    # destroy: the timer goes, nothing runs afterwards
    m.calls = []
    m.call(PSYMS['np_on_destroy'], a0=WIN, a1=0)
    expect(('timer_remove', 0x777) in m.calls, 'EVT_DESTROY removes the timer')
    m.calls = []; r = m.call(PSYMS['np_tick'], count=200000)
    expect(r == 0 and not m.calls, 'a late timer callback does nothing and ends itself')
    m.call(PSYMS['np_on_destroy'], a0=WIN, a1=0)
    expect(m.calls == [], 'a second destroy does nothing')
    m.call(PSYMS['np_on_art_paint'], a0=0, a1=0, count=100000)
    expect(m.fills == [], 'no paint after destroy')

    # a second page before the first one's destroy: the old timer goes, one new
    m = NowMachine(); m.page(); m.src(0)
    m.init(); m.init(win=WIN + 0x100)
    expect(sum(c[0] == 'timer_remove' for c in m.calls) == 1 and sum(c[0] == 'timer_add' for c in m.calls) == 1,
           'a page built over a live one replaces the old timer')
    m.calls = []; m.call(PSYMS['np_on_destroy'], a0=WIN, a1=0)
    expect(m.calls == [], 'the earlier page\'s destroy leaves the new one alone')
    m.call(PSYMS['np_on_destroy'], a0=WIN + 0x100, a1=0)
    expect(('timer_remove', 0x777) in m.calls, 'the new page\'s destroy removes its timer')

    # ------------------------------------------------------------------ fall back to stock
    m = NowMachine(); m.page(); m.present.add(KILL)
    ret = m.init()
    expect(ret == 0 and m.names() == ['stock_playing_init', 'access'] and not m.timers and not m.styles, f'the kill switch: stock only ({m.names()})')
    m = NowMachine(); m.page(); m.stock_ret = 0x10
    ret = m.init()
    expect(ret == 0x10 and not m.timers and 'access' not in m.names(), 'a failed stock init is returned and nothing starts')
    m = NowMachine(); m.page()
    ret = m.init(win=0)
    expect(not m.timers and not m.styles, 'no window: nothing starts')
    m = NowMachine(); m.page(); m.timer_fail = True
    ret = m.init()
    expect(ret == 0 and not m.timers and not m.styles and not any(c[0] == 'widget_on' and c[2] == EVT_AFTER_PAINT for c in m.calls),
           'no timer: the page stays stock (no style, no corner painter)')
    m.calls = []; m.call(PSYMS['np_on_destroy'], a0=WIN, a1=0); expect(m.calls == [], 'and its destroy handler has nothing to undo')
    # a widget of the asset missing: that part is off, the rest works
    m = NowMachine(); m.page(labels=False); m.src(0); m.pt = (10, 100, 1)
    m.init(); m.tick()
    expect(m.timers and m.styles and not m.set_texts(), 'without the labels: the tint still runs, the time does not')
    m = NowMachine(); m.page(art=False); m.src(0)
    m.init()
    expect(m.timers and not any(c[0] == 'widget_on' and c[2] == EVT_AFTER_PAINT for c in m.calls), 'without the cover widget: no corner painter')
    m = NowMachine(); m.page(); m.src(0); m.style_ret = 0x10
    m.init()
    expect(not any(c[0] == 'widget_invalidate_force' for c in m.calls), 'a style call that fails invalidates nothing')

    # ------------------------------------------------------------------ remaining time
    # Machine.call sets a0..a2 only; the fourth argument is written by hand
    def fmt(pos, ln):
        mm = NowMachine(); out = mm.alloc(32)
        mm.calls = []; mm.u.reg_write(UC_MIPS_REG_SP, STACK); mm.u.reg_write(UC_MIPS_REG_RA, RET); mm.u.reg_write(UC_MIPS_REG_T9, PSYMS['np_format_remaining'])
        for r, v in ((UC_MIPS_REG_A0, out), (UC_MIPS_REG_A1, 32), (UC_MIPS_REG_A2, pos), (UC_MIPS_REG_A3, ln)): mm.u.reg_write(r, v & 0xffffffff)
        mm.u.emu_start(PSYMS['np_format_remaining'], RET, count=100000)
        return mm.read_cstr(out)
    cases = {(0, 0): '-00:00', (0, 1): '-00:01', (0, 59): '-00:59', (0, 60): '-01:00', (0, 3599): '-59:59', (0, 3600): '-01:00:00',
             (0, 3723): '-01:02:03', (100, 100): '-00:00', (130, 100): '-00:00', (30, 200): '-02:50',
             (3599, 7200): '-01:00:01', (-5, 10): '-00:15'}
    got = {k: fmt(*k) for k in cases}
    expect(got == cases, f'-mm:ss from 0:00 to over an hour, a position past the end: {[(k, got[k], v) for k, v in cases.items() if got[k] != v]}')
    m = NowMachine(); m.page(); m.src(0); m.pt = (30, 200, 1)
    m.init()
    expect(m.set_texts() == [(m.widgets['np_remaining'], '-02:50')], f'the label shows the time left ({m.set_texts()})')
    expect(m.visible('np_remaining') == 1 and m.visible('label_playlen') == 0, 'np_remaining shows and the stock total hides')
    m.tick(); expect(not m.set_texts(), 'an unchanged time is not set again')
    m.pt = (31, 200, 1); m.tick(); expect(m.set_texts() == [(m.widgets['np_remaining'], '-02:49')], 'the next second is')
    m.pt = (500, 200, 1); m.tick(); expect(m.set_texts() == [(m.widgets['np_remaining'], '-00:00')], 'a position past the length reads -00:00')
    m.pt = (0, 0, 1); m.tick(); expect(m.visible('np_remaining') == 0 and m.visible('label_playlen') == 1, 'a length of 0: stock\'s total shows again')
    m.pt = (10, 100, 1); m.tick(); expect(m.visible('np_remaining') == 1 and m.visible('label_playlen') == 0, 'and the remaining time comes back')
    m.pt = (10, 100, -1); m.tick(); expect(m.visible('np_remaining') == 0 and m.visible('label_playlen') == 1, 'a failed query: stock\'s total')
    m.pt = (10, 100, 1); m.tick(); m.pt = (11, -5, 1); m.tick()
    expect(m.visible('label_playlen') == 1, 'a negative length: stock\'s total')
    m.pt = (10, 100, 1)
    expect(m.props.get((m.widgets['label_playlen'], 'sensitive')) is None, 'sensitivity is the asset\'s (both labels insensitive), only visibility is toggled')

    # ------------------------------------------------------------------ the tone
    mm = NowMachine()
    def c_tone(r, g, b):
        mm.u.reg_write(UC_MIPS_REG_SP, STACK); mm.u.reg_write(UC_MIPS_REG_RA, RET)
        for reg, v in ((UC_MIPS_REG_A0, r), (UC_MIPS_REG_A1, g), (UC_MIPS_REG_A2, b)): mm.u.reg_write(reg, v)
        mm.u.emu_start(PSYMS['np_tone'], RET, count=100000)
        v = mm.u.reg_read(UC_MIPS_REG_V0)
        return v >> 24, (v & 255, v >> 8 & 255, v >> 16 & 255)
    rng = random.Random(7)
    grid = [(r, g, b) for r in range(0, 256, 51) for g in range(0, 256, 51) for b in range(0, 256, 51)]
    grid += [(rng.randrange(256), rng.randrange(256), rng.randrange(256)) for _ in range(150)] + [(1, 0, 0), (0, 0, 1), (255, 254, 255)]
    bad = [(c, c_tone(*c)[1], mn.tone(*c)) for c in grid if c_tone(*c) != (255, mn.tone(*c))]
    expect(not bad, f'np_tone equals tools/mod_nowplaying.py tone on {len(grid)} colours ({bad[:2]})')
    expect(c_tone(0, 0, 0) == (255, mn.NP_NEUTRAL) and mn.tone(0, 0, 0) == mn.NP_NEUTRAL, 'black is the neutral tone')
    expect(all(max(mn.tone(*c)) <= mn.NP_V_MAX and max(mn.tone(*c)) >= mn.NP_V_MIN for c in grid if any(c)), 'the brightest channel of a tone stays between NP_V_MIN and NP_V_MAX (darkened)')
    expect(all(len(set(mn.tone(v, v, v))) == 1 for v in range(0, 256, 5)), 'a grey stays grey')
    red = mn.tone(200, 60, 60); expect(red[0] > red[1] == red[2] and red[1] > 0, f'a red cover stays red ({red})')
    expect(mn.tone(250, 250, 250)[0] > mn.tone(120, 120, 120)[0] > mn.tone(10, 10, 10)[0], 'brighter covers give brighter tones')
    expect((mn.NP_V_MIN, mn.NP_V_MAX, mn.NP_SAT_NUM, mn.NP_SAT_DEN) == tuple(O[k] for k in ('NP_V_MIN', 'NP_V_MAX', 'NP_SAT_NUM', 'NP_SAT_DEN'))
           and O['NP_NEUTRAL'] == 0xff000000 | mn.NP_NEUTRAL[0] | mn.NP_NEUTRAL[1] << 8 | mn.NP_NEUTRAL[2] << 16
           and mn.BG == '#%02X%02X%02X' % mn.NP_NEUTRAL, 'the Python tone and the payload share their constants, and the asset\'s window colour is the neutral tone')
    expect((mn.TINT_ALPHA[0], mn.TINT_ALPHA[1], mn.H, mn.ART, mn.ART_Y, mn.ART_R) == tuple(O[k] for k in ('NP_ALPHA_TOP', 'NP_ALPHA_BOTTOM', 'NP_WIN_H', 'NP_ART', 'NP_ART_Y', 'NP_ART_R')),
           'the gradient and the art constants are the payload\'s')
    # the contrast floor: white title and #AAAAAA lines over the toned window under the gradient, worst case over the colour grid
    rows = {'title': ((255, 255, 255), mn.TITLE_Y + mn.TITLE_H // 2), 'artist': ((170, 170, 170), mn.ARTIST_Y + mn.ARTIST_H // 2),
            'times': ((170, 170, 170), mn.TIMES_Y + mn.TIMES_H // 2), 'index': ((170, 170, 170), mn.TIMES_Y)}
    worst = {}
    for c in grid + [(255, 255, 255)]:
        t = mn.tone(*c)
        for n, (fg, y) in rows.items():
            keep = 255 - mn.tint_alpha(y)
            worst[n] = min(worst.get(n, 99), contrast(fg, tuple(v * keep // 255 for v in t)))
    expect(all(v >= 4.5 for v in worst.values()), f'text keeps 4.5:1 on the darkest and the brightest tone under the gradient ({ {k: round(v, 2) for k, v in worst.items()} })')

    # ------------------------------------------------------------------ the cover: decode, average, change, corrupt, missing
    P2, P3 = '/tmp/coverpic.jpg', '/tmp/externpic.jpg'
    half = bytes([255, 0, 0, 255]) * 8 + bytes([0, 0, 255, 255]) * 8
    m = NowMachine(); m.page(); m.jpeg(P2, pix=half, size=(4, 4)); m.src(2)
    m.init()
    avg = (127, 0, 127)       # (255*8 // 16, 0, 255*8 // 16): the box average of the 4x4 cover
    expect(m.styles == [(WIN, 'normal:bg_color', 0xff000000 | mn.tone(*avg)[0] | mn.tone(*avg)[1] << 8 | mn.tone(*avg)[2] << 16)],
           f'a red/blue cover tints with the tone of its average colour ({[hex(s[2]) for s in m.styles]})')
    expect(m.loads == ['file://' + P2], 'the cover is decoded once, from the file of source type 2')
    expect(('widget_invalidate_force', WIN) in m.calls, 'the window is repainted')
    m.calls = []; m.tick()
    expect(m.loads == ['file://' + P2] and not m.styles[1:], 'an unchanged cover is not decoded again')
    m.blobs[P2] = b'another' * 50; m.images['file://' + P2] = (2, 2, bytes([0, 200, 0, 255]) * 4); m.tick()
    expect(len(m.styles) == 2 and m.styles[1][2] & 0xffffff == (lambda t: t[0] | t[1] << 8 | t[2] << 16)(mn.tone(0, 200, 0)), 'a changed file tints again')
    m.src(3); m.jpeg(P3, data=b'folder' * 20, pix=bytes([90, 90, 90, 255]) * 4, size=(2, 2)); m.tick()
    expect(len(m.styles) == 3 and 'file://' + P3 in m.loads, 'source type 3 reads /tmp/externpic.jpg')
    m.src(5); m.blobs[P3] = b'cached' * 20; m.tick()
    expect(len(m.styles) == 4, 'source type 5 does too')
    m.src(1); m.blobs[P3] = b'being written'; n = len(m.styles); m.tick()
    expect(len(m.styles) == n and not any(c[0] == 'fopen' for c in m.calls), 'type 1 (demo is replacing the file): the colour stays, nothing is read')
    m.src(4); m.tick()
    expect(m.styles[-1] == (WIN, 'normal:bg_color', O['NP_NEUTRAL']), 'a source with no JPEG file (4: random cover) is the neutral tone')
    n = len(m.styles); m.tick(); expect(len(m.styles) == n, 'and only once')
    # a file that vanished or cannot be decoded keeps the colour
    m = NowMachine(); m.page(); m.src(2); m.init()
    m.styles.clear()                          # a type 2 source, no file: not readable, no decode
    n = len(m.styles); m.tick()
    expect(len(m.styles) == n and not m.loads, 'a type 2 source whose file is missing: the colour stays, no decode')
    m.jpeg(P2, data=b'corrupt' * 30); m.load_image = 1
    m.tick(); expect(not m.styles and len(m.loads) == 1, 'a file the loader refuses keeps the colour')
    m.tick(); expect(len(m.loads) == 1, 'and is not retried until it changes')
    m.blobs[P2] = b'fixed' * 30; m.load_image = 0; m.tick()
    expect(len(m.styles) == 1, 'a changed file is tried again')
    m = NowMachine(); m.page(); m.src(2); m.jpeg(P2, pix=bytes(4 * 4 * 4), size=(4, 4)); m.init()
    expect(m.styles == [(WIN, 'normal:bg_color', O['NP_NEUTRAL'])], 'an all-black cover is the neutral tone')
    # the whole file is hashed, bounded
    m = NowMachine(); m.page(); m.src(2); big = bytes(range(256)) * 4096; m.jpeg(P2, data=big)
    k = m.call(PSYMS['np_file_key'], a0=m.cstr(P2), count=20000000)
    expect(k != 0, 'a 1 MB file hashes (at most NP_HASH_MAX bytes read)')
    m.blobs['/tmp/x'] = b''; m.present.add('/tmp/x')
    expect(m.call(PSYMS['np_file_key'], a0=m.cstr('/tmp/x'), count=100000) == 0 and m.call(PSYMS['np_file_key'], a0=m.cstr('/tmp/none'), count=100000) == 0,
           'an empty or missing file has no key')

    # ------------------------------------------------------------------ the corners: the same numbers as the model, the colour the window has there
    cov = mn.corner_alpha()
    expect(len(cov) == 144 and cov[0] == 255 and cov[-1] == 0 and cov[11 * 12 + 0] <= 2 and sum(1 for v in cov if v) >= 30, 'the corner table: a full pixel at the corner, nothing at the arc\'s inside')
    m = NowMachine(); m.page(); m.src(2); m.jpeg(P2, pix=half, size=(4, 4)); m.init()
    ev = m.alloc(0x40); m.u.mem_write(ev, bytes(0x40)); canvas = 0x7000a000; m.setword(ev + O['EVENT_PAINT_CANVAS'], canvas)
    m.fills = []; m.call(PSYMS['np_on_art_paint'], a0=0, a1=ev, count=2000000)
    t = mn.tone(*avg); color = t[0] | t[1] << 8 | t[2] << 16
    want = {}
    A = mn.ART
    for k in range(4):
        for y in range(mn.ART_R):
            ly = A - 1 - y if k & 2 else y
            keep = 255 - mn.tint_alpha(mn.ART_Y + ly)
            shade = (t[0] * keep // 255) | (t[1] * keep // 255) << 8 | (t[2] * keep // 255) << 16
            for x in range(mn.ART_R):
                a = cov[y * mn.ART_R + x]
                if a: want[(A - 1 - x if k & 1 else x, ly)] = shade | a << 24
    got = {(f[1], f[2]): f[0] for f in m.fills if (f[3], f[4]) == (1, 1)}
    expect(got == want and len(m.fills) == len(want), f'the four corners are painted pixel by pixel in the window\'s colour under the gradient ({len(m.fills)} pixels)')
    m.fills = []; m.call(PSYMS['np_on_art_paint'], a0=0, a1=0, count=100000)
    expect(not m.fills, 'no canvas: nothing')
    # the colour the corners use is the one the style call set
    expect(m.styles[-1][2] & 0xffffff == color, 'the corners use the colour of the last style call')

    # ------------------------------------------------------------------ the built assets
    ui = awtk_ui.parse(open(os.path.join(raw, 'ui', 'playing_page.bin'), 'rb').read())
    f = ui.find
    rect = lambda n: (f(n).x, f(n).y, f(n).w, f(n).h)
    expect(rect('img_playcover') == (28, 28, 264, 264) and mn.ART == mod_lockscreen.COVER_SIZE == 264, 'the cover is 264 px at 28, 28: the size demo writes, so it is drawn 1:1')
    imm = [word(built, a) & 0xffff for a in mod_lockscreen.COVER_IMM]
    expect(imm == [264] * 4 and all(word(stock, a) in (0x240700fe, 0x240600fe) for a in mod_lockscreen.COVER_IMM), 'demo writes the cover file at 264 px (the four pinned words)')
    expect(rect('btn_return') == (100, 0, 120, 44) and f('btn_return').get('style') == 'img_btn_style' and f('btn_return').get('style:normal:bg_image') == 'np_grabber',
           'Back is the grabber: 120x44, the pill in its image')
    expect(rect('slide_indicator') == (145, 296, 30, 4) and f('slide_indicator').get('size') == '4', 'micro dots: 4 px, centred under the art')
    expect(rect('scrlabel_title') == (28, 304, 176, 26) and rect('scrlabel_artist') == (28, 330, 176, 22), 'title and artist in the 28 px text column left of the buttons')
    expect(rect('btn_fav') == (204, 306, 44, 44) and rect('btn_more') == (248, 306, 44, 44), 'heart and More: 44x44 targets, 4 px apart, right edge on the 28 px margin')
    expect(rect('slider_play') == (28, 354, 264, 30) and f('slider_play').get('bar_size') == '6' and f('slider_play').get('style:normal:icon') == '', 'progress: the stock 30 px target, a 6 px bar, no thumb')
    expect(rect('label_playtime')[:2] == (28, 384) and rect('np_remaining') == rect('label_playlen') and rect('label_playlen')[0] + rect('label_playlen')[2] == 292,
           'times under the bar on the margins; the remaining time sits on the total')
    expect(all(f(n).get(f'style:{s}:font_size') == '12' for n in ('label_playtime', 'label_playlen', 'np_remaining') for s in ('normal', 'disable', 'focused')), 'times are 12 px in every state')
    expect(f('view_buttons').y == 400 and f('view_buttons').y + f('view_buttons').h == 450, 'the transport row is 400..450')
    expect(f('np_remaining').get('visible') == 'false' and all(f(n).get('sensitive') == 'false' for n in ('np_remaining', 'label_playlen', 'label_playtime', 'img_np_tint')),
           'np_remaining starts hidden; the labels and the gradient are insensitive')
    for n in ('label_index', 'img_hr'):
        expect(rect(n)[2:] == (0, 0) and f(n).get('visible') == 'false' and f(n).get('sensitive') == 'false', f'{n} is kept, hidden and insensitive at 0x0')
    expect(f('label_album') in f('view_info').children and 'label_album' not in [c.name for c in f('view').children], 'the album line is on the info page, not under the art')
    expect(f('label_info') in f('view_info').children, 'the quality line is on the info page, not between the times')
    expect(f('img_np_tint') is ui.find('view_local').children[0] and rect('img_np_tint') == (0, 0, 320, 450), 'the gradient is the first child of view_local, window sized')
    hidden = [w.name or w.type for w in ui.walk() if w.get('visible') == 'false' and w.get('sensitive') != 'false' and w.name != 'view_dlna' and w.name != 'img_mqa']
    expect(not hidden, f'every hidden widget is also insensitive ({hidden})')
    expect(len(mn.check_touch(ui)) == len(mn.PROBES), 'check_touch: every control\'s centre reaches it, the art and the title rows reach the slide_view')
    expect(all(min(rect(n)[2:]) >= 44 for n in mn.PROBES if n != 'slider_play') and rect('slider_play')[3] == 30, 'touch targets are 44 px or the stock 30 px seek bar')
    lyr = f('view_lrc')
    expect(lyr.y >= 44 and lyr.y + lyr.h <= mn.DOTS[1] and f('view_info').children and all(c.y + c.h <= mn.DOTS[1] for c in f('view_info').children if c.name), 'lyrics and info end above the dots')
    expect(f('view').y + f('slide_view').h <= f('view_buttons').y and f('slide_view').h == mn.SLIDE_H, 'the slide pages end above the transport row')
    # vertical rhythm
    art_end = 28 + 264
    expect(mn.DOTS[1] - art_end == 4 and 304 - (mn.DOTS[1] + mn.DOTS[3]) == 4 and 330 + 22 <= 354 and 354 + 30 == 384 and 384 + 16 == 400, 'art, dots, title, artist, bar, times and the transport row follow each other without overlap')
    # images
    xx = os.path.join(raw, 'images', 'xx')
    from PIL import Image
    t = Image.open(os.path.join(xx, 'np_tint.png')).convert('RGBA')
    expect(t.size == (320, 450) and {t.getpixel((0, y))[:3] for y in (0, 225, 449)} == {(0, 0, 0)} and (t.getpixel((7, 0))[3], t.getpixel((7, 449))[3]) == mn.TINT_ALPHA
           and all(t.getpixel((x, y))[3] == mn.tint_alpha(y) for y in range(0, 450, 17) for x in (0, 319)), 'np_tint.png: black, alpha 38 at the top to 235 at the bottom, rows as tint_alpha')
    expect(os.path.getsize(os.path.join(xx, 'np_tint.png')) < 6000, f'np_tint.png is small ({os.path.getsize(os.path.join(xx, "np_tint.png"))} bytes)')
    expect(not os.path.exists(os.path.join(xx, 'np_artmask.png')) and 'img_np_artmask' not in [w.name for w in ui.walk()], 'there is no static corner mask: the payload paints the corners (square without it)')
    def img(n): return Image.open(os.path.join(xx, n + '.png')).convert('RGBA')
    sizes = {n: img(n).size for n in ('np_grabber', 'np_play', 'np_pause', 'np_next', 'np_prev', 'np_fav', 'np_unfav', 'np_more', 'np_random', 'np_playqueue')}
    expect(sizes['np_grabber'] == (120, 44) and sizes['np_fav'] == sizes['np_unfav'] == sizes['np_more'] == (44, 44) and sizes['np_play'] == sizes['np_pause'] == (44, 44) and sizes['np_next'] == sizes['np_prev'] == (36, 36),
           f'glyph canvases: grabber 120x44, disc glyphs 44x44, transport as before ({sizes})')
    g = img('np_grabber'); bb = g.getchannel('A').point(lambda v: 255 if v > 40 else 0).getbbox()
    expect(bb == (42, 11, 78, 16) and 108 <= g.getpixel((60, 13))[3] <= 110, f'the grabber pill is 36x5 at x 42, y 11 of the button, white at 43 % ({bb})')
    for n in ('np_fav', 'np_unfav', 'np_more'):
        im = img(n); dbb = im.getchannel('A').point(lambda v: 255 if v > 2 else 0).getbbox()
        expect(dbb == (4, 4, 40, 40) and im.getpixel((8, 22))[3] == 26 and im.getpixel((8, 22))[:3] == (255, 255, 255), f'{n}: a 36 px disc, white at #1A, in the 44 px target ({dbb})')
    pb = img('np_play').getchannel('A').point(lambda v: 255 if v > 128 else 0).getbbox()
    nb = img('np_next').getchannel('A').point(lambda v: 255 if v > 128 else 0).getbbox()
    qb = img('np_pause').getchannel('A').point(lambda v: 255 if v > 128 else 0).getbbox()
    near = lambda b, w, h: abs(b[2] - b[0] - w) <= 1 and abs(b[3] - b[1] - h) <= 1
    expect(near(pb, 27, 32) and near(qb, 26, 32) and near(nb, 32, 18), f'big solid transport: play 27x32, pause 26x32, skip 32x18 ({pb}, {qb}, {nb})')
    mid = img('np_random'); mb = mid.getchannel('A').point(lambda v: 255 if v > 128 else 0).getbbox()
    expect(max(mb[2] - mb[0], mb[3] - mb[1]) <= 22 and max(c for c in mid.getdata() if c[3] > 200)[:3] == mod_icons.NP_MID, 'the mode and queue glyphs are smaller (22 px) and dimmer (#AAAAAA)')
    expect(max(c for c in img('np_order').getdata() if c[3] > 200)[:3] == mod_icons.NP_OFF, 'repeat-off is dimmer still')
    # the style swaps the app does still land on glyphs: every page-theme icon exists
    th = awtk_style.parse(open(os.path.join(raw, 'styles', 'playing_page.bin'), 'rb').read())
    icons = {s.get('icon') for s in th.items if s.widget == 'button' and (s.get('icon') or '').startswith('np_')}
    expect(icons <= set(mod_icons.np_names()) and {'np_fav', 'np_unfav', 'np_play', 'np_pause', 'np_random', 'np_cycle', 'np_cycle1', 'np_order'} <= icons,
           f'the page theme\'s np_ button icons exist as images ({sorted(icons)})')
    expect(f('btn_fav').get('style') == 'btn_imgunfav_style' and f('btn_fav').get('style:pressed:icon') == 'np_unfav_down', 'btn_fav keeps its stock style (the app swaps it) with the pressed glyph')
    expect(f('btn_playmode').get('style') == 'btn_imgrandom_style', 'btn_playmode keeps its stock style (the app swaps it)')
