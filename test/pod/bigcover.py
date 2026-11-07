"""The timed cover page (patch/bigcover.c, docs/modules/bigcover.md): the hook on bigcover_page_init, the 320 px cover job on the shared worker, the picture fitted into the page's own
bitmap and drawn from the cover widget's EVT_AFTER_PAINT.

The hook and the timer run the real compiled payload under the harness machine; the stock init is mocked at its resume point and the shared worker (cc_build_*) is mocked at the payload
function boundary (its own tests are test/pod/coverart.py), so each case scripts what the worker makes. The fit (cc_decode_fit -> cc_fit) runs for real on the images widget_load_image serves."""
import os, struct
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

INIT = pod.BIGCOVER_INIT
COVER_SRC = pod.DATA['COVER_SRC'][0]
PARSED = pod.DATA['COVER_PARSED'][0]   # savecover_path: the path stock's parser last finished a cover for
WIN = 0x24000000
TMP = '/tmp/m1plus-bigcover.jpg'
URL = 'file://' + TMP
EVT_DESTROY, EVT_AFTER_PAINT = O['EVT_DESTROY'], O['EVT_AFTER_PAINT']
KILL = '/mnt/mmc/m1plus-off'
BG = 0xff141414
T1, T2 = '/mnt/mmc/Music/a/1.flac', '/mnt/mmc/Music/b/2.flac'
WORKER = ('cc_build_open', 'cc_build_add_aspect', 'cc_build_start', 'cc_build_done', 'cc_build_total', 'cc_build_stop', 'cc_build_busy')


def rgba(w, h, f):
    """w x h RGBA bytes, f(x, y) -> (r, g, b)."""
    return b''.join(bytes(f(x, y)) + b'\xff' for y in range(h) for x in range(w))


def pattern(x, y): return ((x * 7 + y * 3) & 255, (x * 5 + y * 11) & 255, (x ^ y) & 255)


def word_of(rgb): return 0xff000000 | rgb[0] | rgb[1] << 8 | rgb[2] << 16


class BC(Machine):
    """Machine plus the page, the playing queue and a scripted shared worker."""
    FIRE_WIN = WIN

    def __init__(self, tracks=(T1,), src=2):
        super().__init__()
        self.handlers[INIT + 12] = 'stock_bigcover_resume'
        for n in WORKER: self.handlers[PSYMS[n]] = n
        self.init_ret = 0
        self.img = self.widget('img_playcover')
        self.recs = [self.record(path=p, album=f'Album {i}') for i, p in enumerate(tracks)]
        self.play(self.recs, 0)
        self.paths = list(tracks)
        self.setword(COVER_SRC, src)
        self.parse(tracks[0] if tracks else '')
        self.window = WIN
        self.held = self.other_held = self.orphan = False   # this page holds the set / another page does / a cancelled worker is still out
        self.job = None            # (track, dst, px) of the set we hold
        self.done = self.total = 0
        self.add_ret, self.start_ret = 1, 1
        self.log = []              # every call of every m.call(), in order
        self.clock = 1000

    # -- the scripted worker
    def _hook(self, u, address, size, _):
        name = self.handlers.get(address)
        if name == 'stock_bigcover_resume':
            self.calls.append(('stock_bigcover_resume', u.reg_read(UC_MIPS_REG_A0), u.reg_read(UC_MIPS_REG_A1)))
            u.reg_write(UC_MIPS_REG_V0, self.init_ret & 0xffffffff); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA)); return
        if name not in WORKER: return super()._hook(u, address, size, _)
        a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        ret = 0
        if name == 'cc_build_busy': ret = int(self.held or self.other_held or self.orphan)
        elif name == 'cc_build_open':
            self.calls.append((name, a0, a1))
            if not (self.held or self.other_held or self.orphan): self.held, self.job, self.done, self.total, ret = True, None, 0, 0, 1
        elif name == 'cc_build_add_aspect':
            self.calls.append((name, self.read_cstr(a0), self.read_cstr(a1), a2, a3))
            ret = self.add_ret
            if ret == 1: self.job, self.total = (self.read_cstr(a0), self.read_cstr(a1), a2), 1
        elif name == 'cc_build_start': self.calls.append((name,)); ret = self.start_ret
        elif name == 'cc_build_done': ret = self.done
        elif name == 'cc_build_total': ret = self.total
        elif name == 'cc_build_stop':
            self.calls.append((name,)); self.held, self.job, self.done, self.total = False, None, 0, 0
        u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    def call(self, *a, **k):
        r = super().call(*a, **k); self.log += self.calls; return r

    def count(self, name): return sum(1 for c in self.log if c[0] == name)
    def all(self, name): return [c for c in self.log if c[0] == name]

    # -- the page
    def open(self, win=WIN):
        return self.call(PSYMS['m1plus_bigcover_init'], a0=win, a1=0, count=3000000)

    def tick(self, ms=250):
        self.clock += ms
        cb, _ = self.timers[-1]
        return self.call(cb, a0=0, count=6000000)

    def finish(self, w=320, h=320, pix=None):
        """The worker made the art (a w x h file) and is done."""
        self.present.add(TMP); self.images[URL] = (w, h, pix if pix is not None else rgba(w, h, pattern)); self.load_image = 0
        self.done = self.total

    def finish_none(self): self.done = self.total   # done, no file (no art, a picture under 320 px)

    def paint(self):
        """The cover widget's EVT_AFTER_PAINT with a canvas; the blits it made."""
        fn, ctx = self.bound[(self.img, EVT_AFTER_PAINT)]
        e = self.alloc(0x40); self.u.mem_write(e, bytes(0x40)); self.setword(e + O['EVENT_PAINT_CANVAS'], 0x5000)
        self.blits = []
        self.call(fn, a0=ctx, a1=e, count=2000000)
        return list(self.blits)

    def destroy(self, win=WIN):
        fn, ctx = self.bound[(win, EVT_DESTROY)]
        return self.call(fn, a0=ctx, a1=0, count=3000000)

    def pixels(self, bmp):
        data, w, h = self.bitmaps[bmp]
        return struct.unpack(f'<{w * h}I', bytes(self.u.mem_read(data, w * h * 4)))

    def bmp(self):
        return next(iter(self.bitmaps), None)

    def parse(self, path):
        """Stock's parser finished the cover of path (its path buffer)."""
        self.u.mem_write(PARSED, path.encode()[:0x3ff] + bytes(0x400 - min(len(path.encode()), 0x3ff)))

    def switch(self, pos, parsed=True):
        """The player moves to track pos; the parser has caught up with it unless parsed is False (its source and path buffer are still the last track's)."""
        self.play_pos = pos
        if parsed: self.parse(self.paths[pos])


def hook_tests(ctx):
    expect = ctx.expect
    import paths
    stock = open(os.path.join(paths.find_stock(paths.ZIP), 'rootfs', pod.DEMO), 'rb').read()
    built = open(DEMO, 'rb').read()
    word = lambda b, a: struct.unpack_from('<I', b, pod.fileoff(b, a))[0]

    # -- 0. the hook, its pins and the stock paths that reach the page
    expect(PARSED == 0xa04c3c and COVER_SRC == 0x97cad8, 'the cover source word and the parser\'s path buffer (savecover_path, checked against .dynsym by pod.DATA)')
    expect(INIT == 0x529a24 and pod.BIGCOVER_INIT_PROLOGUE == (0x3c1c004e, 0x279ca4ac, 0x0399e021)
           and tuple(word(stock, INIT + 4 * i) for i in range(3)) == pod.BIGCOVER_INIT_PROLOGUE, 'stock has the three PIC prologue words the hook pins (bigcover_page_init)')
    expect(0x4e0000 - 0x5b54 + INIT == pod.GP, 'the prologue computes $gp = 0xa03ed0')
    expect((word(built, INIT), word(built, INIT + 4), word(built, INIT + 8), word(built, INIT + 12)) == (pod.j(PSYMS['m1plus_bigcover_init']), 0, pod.BIGCOVER_INIT_PROLOGUE[2], 0x10800046),
           'the build has `j m1plus_bigcover_init; nop` over the first two prologue words; the trampoline resumes at stock\'s beqz a0')
    tramp = struct.unpack_from('<4I', open(os.path.join(BUILD, 'patch.bin'), 'rb').read(), PSYMS['stock_bigcover_init_trampoline'] - pod.BASE)
    expect(tramp == (0x3c1c0000 | pod.GP >> 16, 0x379c0000 | pod.GP & 0xffff, pod.j(INIT + 12), 0), 'the trampoline restores $gp and resumes at the 4th instruction')
    expect(MANIFEST['hook_bigcover'] == {'addr': INIT, 'target': PSYMS['m1plus_bigcover_init']}, 'the manifest records the hook')
    expect(all(word(stock, a) == old and word(built, a) == old for a, old, _ in pod.BIGCOVER_PINS[1:]),
           'the pinned stock words (the page-init dispatcher\'s compare and call, the timed open) are stock\'s in stock and in the build: only the init\'s prologue is hooked')
    expect(stock[pod.fileoff(stock, 0x749f50):][:14] == b'bigcover_page\0', 'the name the dispatcher compares with, and the timed open passes')
    expect([a for a, _, _ in pod.BIGCOVER_PINS] == [0x529a30, 0x4d10c8, 0x4d10cc, 0x4d10d8, 0x4d10e0, 0x53d0ec, 0x53d0f0], 'the pins: init resume, dispatcher, timed open')
    expect('bigcover.c' in pod.SOURCES and INIT not in range(pod.PLAYING_INIT - 12, pod.PLAYING_INIT + 12), 'in the payload sources, a hook of its own')
    expect(PSYMS['m1plus_bigcover_init'] >= pod.BASE and 'cc_decode_fit' in PSYMS and 'cc_fit' in PSYMS, 'the hook and the fit are in the payload')

    # -- 1. the page the stock way: kill switch, a failed or null init, a page without the cover widget, no timer, no bind
    gp = []
    m = BC(); m.u.hook_add(UC_HOOK_CODE, lambda u, a, s, _: gp.append(u.reg_read(UC_MIPS_REG_GP)), begin=INIT + 12, end=INIT + 12)
    r = m.open()
    expect(gp == [pod.GP] and r == 0 and m.calls[0] == ('stock_bigcover_resume', WIN, 0), f'the trampoline restores $gp, the stock init runs first with its arguments ({[hex(g) for g in gp]})')
    expect(m.timers == [(m.timers[0][0], 250)] and (WIN, EVT_DESTROY) in m.bound and (m.img, EVT_AFTER_PAINT) in m.bound, 'a page timer of 250 ms, the destroy and the cover widget\'s paint are bound')
    m = BC(); m.present.add(KILL); r = m.open()
    expect(r == 0 and m.timers == [] and not m.bound and not [c for c in m.calls if c[0] in ('widget_lookup', 'cc_build_open')], 'the kill switch: the stock init only, nothing looked up, bound or asked of the worker')
    m = BC(); m.init_ret = 0x10; r = m.open()
    expect(r == 0x10 and m.timers == [] and not m.bound, 'a stock init that fails: its result is returned, nothing is started')
    m = BC(); r = m.open(win=0)
    expect(r == 0 and m.timers == [] and not m.bound and not [c for c in m.calls if c[0] == 'widget_lookup'], 'a null window: the stock result, nothing started')
    m = BC(); del m.widgets['img_playcover']; r = m.open()
    expect(r == 0 and m.timers == [] and not m.bound and m.count('cc_build_open') == 0, 'a page without img_playcover stays stock')
    m = BC(); m.widget_on_fail = {EVT_DESTROY}; m.open()
    expect(m.timers == [] and m.count('cc_build_open') == 0, 'no destroy handler: no timer, no job')
    m = BC(); m.timer_fail = True; m.open()
    expect(m.count('timer_add') == 1 and m.count('cc_build_open') == 0 and m.count('bitmap_create_ex') == 0, 'no timer: nothing is started')
    m = BC(); m.widget_on_fail = {EVT_AFTER_PAINT}; m.open()
    expect(m.count('timer_remove') == 1 and m.count('cc_build_open') == 0, 'no paint handler: the timer goes again, no job')
    expect(m.call(m.timers[-1][0], a0=0) == 0 and m.count('cc_build_open') == 0, 'and its late tick ends (RET_OK) doing nothing')


def job_tests(ctx):
    expect = ctx.expect

    # -- 2. the request: 320 px of the playing track's art into the page's own file, on the shared worker
    m = BC(); m.open()
    expect(m.all('cc_build_open') == [('cc_build_open', 1, 0)] and m.all('cc_build_add_aspect') == [('cc_build_add_aspect', T1, TMP, 320, 2)] and m.count('cc_build_start') == 1,
           'at open (source 2: the embedded art only): one job set, the playing track\'s file at 320 px into the page\'s temporary file, started')
    expect(m.held and m.count('bitmap_create_ex') == 0 and not m.blits, 'while it runs: the page holds the set, nothing decoded or drawn, stock\'s picture shows')
    m.tick(); m.tick()
    expect(m.count('cc_build_open') == 1 and m.count('cc_build_stop') == 0 and m.bmp() is None, 'a running job is polled, not restarted or stopped')
    fn, _ = m.bound[(m.img, EVT_AFTER_PAINT)]
    expect(m.paint() == [], 'the paint draws nothing until the picture is ready')

    # -- 3. a square 320 px result is shown 1:1
    m.finish(); m.tick()
    b = m.bmp()
    expect(m.count('cc_build_stop') == 1 and not m.held and b is not None and m.bitmaps[b][1:] == (320, 320), 'a finished job: the set is joined and freed, a 320 x 320 bitmap is made')
    expect(m.pixels(b) == tuple(word_of(pattern(x, y)) for y in range(320) for x in range(320)), 'every pixel of the 320 x 320 bitmap is the file\'s pixel: no scaling, no crop')
    expect(('unlink', TMP) in m.log and TMP not in m.present, 'the temporary file is removed once decoded')
    expect(('widget_invalidate_force', m.img) in m.log, 'the cover widget is repainted')
    bl = m.paint()
    expect(bl == [(b, (0, 0, 320, 320), (0, 0, 320, 320))], f'the paint draws the bitmap over the whole widget, source and destination 320 x 320 ({bl})')
    m.tick(); m.tick()
    expect(m.count('cc_build_open') == 1 and len(m.bitmaps) == 1, 'a track that has its picture asks for nothing more')

    # -- 4. non-square, small and big sources: the whole picture fitted over the page colour
    cases = [('landscape 320 x 240', 320, 240, 0, 40, 320, 240), ('portrait 240 x 320', 240, 320, 40, 0, 240, 320), ('wide 320 x 100', 320, 100, 0, 110, 320, 100)]
    for name, w, h, ox, oy, tw, th in cases:
        m = BC(); m.open(); m.finish(w, h); m.tick()
        px = m.pixels(m.bmp())
        inside = all(px[(oy + y) * 320 + ox + x] == word_of(pattern(x, y)) for y in range(th) for x in range(tw))
        around = all(px[y * 320 + x] == BG for y in range(320) for x in range(320) if not (ox <= x < ox + tw and oy <= y < oy + th))
        expect(inside and around, f'{name}: copied 1:1 centred at ({ox}, {oy}), #141414 around it')
    flat = lambda c: (lambda x, y: c)
    m = BC(); m.open(); m.finish(200, 200, rgba(200, 200, flat((10, 200, 90)))); m.tick()
    expect(set(m.pixels(m.bmp())) == {word_of((10, 200, 90))}, 'a 200 x 200 picture (the worker never makes one) is filtered up to 320 x 320 and keeps a flat colour exactly')
    m = BC(); m.open(); m.finish(480, 360, rgba(480, 360, flat((200, 20, 20)))); m.tick()
    px = m.pixels(m.bmp())
    expect(all(px[y * 320 + x] == word_of((200, 20, 20)) for y in range(40, 280) for x in range(320)) and all(px[y * 320 + x] == BG for y in (0, 39, 280, 319) for x in range(320)),
           'a 480 x 360 picture is filtered down to 320 x 240 at y 40, a flat colour exact, the bars #141414')
    m = BC(); m.open(); m.finish(100, 100, rgba(100, 100, lambda x, y: (255, 255, 255) if (x // 5 + y // 5) % 2 else (0, 0, 0))); m.tick()
    px = m.pixels(m.bmp())
    expect(all((p & 0xff) in (0, 255) for p in px[:320 * 3]) and len({p & 0xff for p in px[160 * 320:161 * 320]}) <= 3,
           'upscaling an edged picture does not invent a texture beyond the area filter\'s edge pixels')

    # -- 5. no art, a picture the worker keeps out, a file that does not decode, a decode that fails
    m = BC(); m.open(); m.finish_none(); m.tick()
    expect(m.count('cc_build_stop') == 1 and m.bmp() is None and m.paint() == [] and not m.held, 'no art (or under 320 px: the worker makes no file): the set is freed, stock\'s picture stays')
    m.tick(); m.tick(10000)
    expect(m.count('cc_build_open') == 1, 'and the track is not asked for again')
    m = BC(); m.open(); m.present.add(TMP); m.done = m.total; m.load_image = 1; m.tick()
    expect(m.paint() == [] and TMP not in m.present and m.count('cc_build_open') == 1, 'a corrupt file (the stock loader refuses it): removed, nothing drawn, no retry')
    m = BC(); m.bitmap_ok = False; m.open(); m.finish(); m.tick()
    expect(m.paint() == [] and TMP not in m.present and m.count('cc_build_open') == 1, 'no memory for the bitmap: the file is removed, nothing drawn')
    m = BC(); m.open(); m.finish(5000, 5000, b''); m.tick()
    expect(m.bmp() is not None and m.paint() == [] and TMP not in m.present, 'a picture over the decoder\'s limit is not drawn')

    # -- 6. the shared worker is busy, refuses, or hangs
    m = BC(); m.other_held = True; m.open()
    expect(m.count('cc_build_open') == 0 and m.count('cc_build_stop') == 0, 'another page holds the set: no open, and never a stop of its set')
    m.tick(); m.tick()
    m.other_held = False; m.tick()
    expect(m.count('cc_build_open') == 1 and m.count('cc_build_add_aspect') == 1 and m.held, 'the set is free two seconds later: the job starts then')
    m = BC(); m.other_held = True; m.open()
    for _ in range(30): m.tick()
    m.other_held = False; m.tick()
    expect(m.count('cc_build_open') == 0 and m.count('cc_build_stop') == 0 and m.bmp() is None, 'busy for 6 s: this track is given up, a later free worker is not used for it')
    m = BC(); m.orphan = True; m.open()
    expect(m.count('cc_build_open') == 0, 'a cancelled worker still out (the orphan): no open')
    m = BC(); m.add_ret = -1; m.open()
    expect(m.count('cc_build_stop') == 1 and m.count('cc_build_start') == 0 and not m.held, 'a job that cannot be added: the set is freed again, stock stays')
    m.tick(); m.tick()
    expect(m.count('cc_build_open') == 1, 'and it is not retried')
    m = BC(); m.start_ret = 0; m.open()
    expect(m.count('cc_build_stop') == 1 and not m.held and m.bmp() is None, 'a worker that does not start: the set is freed, stock stays')
    m = BC(); m.open()
    for _ in range(45): m.tick()
    expect(m.count('cc_build_stop') == 1 and not m.held and ('unlink', TMP) in m.log and m.count('cc_build_open') == 1, 'a job over 10 s is cancelled without waiting (cc_build_stop) and not asked for again')
    expect(m.bmp() is None and m.paint() == [], 'and nothing is drawn')

    # -- 7. what the page asks for only when there is a file to extract: the cover source, the track, the screen
    m = BC(src=1); m.open(); m.tick()
    expect(m.count('cc_build_open') == 0, 'demo is making its cover file (busy): wait')
    m.setword(COVER_SRC, 2); m.tick()
    expect(m.count('cc_build_open') == 1, 'then the job starts')
    m = BC(src=0); m.open()
    for _ in range(30): m.tick()
    m.setword(COVER_SRC, 2); m.tick()
    expect(m.count('cc_build_open') == 0, 'no cover source (no art, a stream): nothing is asked, and after 6 s it is given up')
    m = BC(src=3); m.open(); expect(m.count('cc_build_open') == 1 and m.all('cc_build_add_aspect') == [('cc_build_add_aspect', T1, TMP, 320, 3)], 'cover source 3 (a folder picture): the job starts and asks for the folder source only')
    # type 5 is the cached .downpic file: the worker knows nothing of it (embedded, then folder art), so the page keeps stock's picture and never shows other art
    m = BC(src=5); m.open()
    for _ in range(30): m.tick()
    expect(m.count('cc_build_open') == 0 and m.count('cc_build_add_aspect') == 0 and m.bmp() is None and m.paint() == [], 'cover source 5 (.downpic): no job, nothing drawn, stock\'s picture stays')
    m = BC(src=2); m.open(); m.setword(COVER_SRC, 5); m.finish(); m.tick()
    expect(m.bmp() is None and m.paint() == [] and TMP not in m.present, 'the source turns into a .downpic one while the job runs: its result is dropped, never drawn')
    m = BC(tracks=('http://radio.example/stream',)); m.open(); m.tick()
    expect(m.count('cc_build_open') == 0, 'a stream\'s URL is not a file: nothing is asked')
    m = BC(); m.play([], 0); m.open(); m.tick()
    expect(m.count('cc_build_open') == 0, 'nothing in the queue: nothing is asked')
    m = BC(); m.screen(False); m.open(); m.tick()
    expect(m.count('cc_build_open') == 0, 'screen off: no job')
    m.screen(True); m.tick()
    expect(m.count('cc_build_open') == 1, 'screen on again: the job starts')

    # -- 7b. the source belongs to the playing track: stock's parser writes it asynchronously, its path buffer says for which track
    m2 = BC(); m2.parse(''); m2.open()
    expect(m2.count('cc_build_open') == 0, 'the parser has not finished this track (its buffer is empty): no request with a source that may be the last track\'s')
    m2.parse(T1); m2.tick()
    expect(m2.all('cc_build_add_aspect') == [('cc_build_add_aspect', T1, TMP, 320, 2)], 'and when the parser has finished this track, the request goes with its source')
    m = BC(src=3); m.parse(T1 + 'x'); m.open()
    expect(m.count('cc_build_open') == 0, 'a path buffer that only starts like the track\'s path is not it')

    # a source that changes under a running job: the result is for another picture, dropped, asked again with the new source
    m = BC(src=3); m.open()
    expect(m.all('cc_build_add_aspect')[-1][4] == 3, 'the job starts for source 3')
    m.setword(COVER_SRC, 2); m.finish(); m.tick()
    expect(m.bmp() is None and m.paint() == [] and TMP not in m.present and m.count('cc_build_stop') == 1 and m.count('cc_build_add_aspect') == 1,
           'the source turned 2 mid-job: the finished result (made for 3) is dropped, never decoded or drawn')
    m.tick()
    expect(m.all('cc_build_add_aspect')[-1] == ('cc_build_add_aspect', T1, TMP, 320, 2) and m.held, 'and the next tick asks again with source 2')
    m.finish(); m.tick()
    expect(m.bmp() is not None and len(m.paint()) == 1, 'whose result is shown')
    m = BC(src=2); m.open(); m.setword(COVER_SRC, 1); m.finish(); m.tick()
    expect(m.bmp() is None and m.paint() == [] and m.count('cc_build_add_aspect') == 1, 'stock busy again (1) when the job ends: dropped, no request while it works')
    m.setword(COVER_SRC, 3); m.tick()
    expect(m.all('cc_build_add_aspect')[-1][4] == 3, 'and a request for 3 once stock is done')
    m = BC(src=2); m.open(); m.finish(); m.setword(COVER_SRC, 5); m.tick()
    for _ in range(30): m.tick()
    expect(m.bmp() is None and m.paint() == [] and m.count('cc_build_add_aspect') == 1, 'source 5 at the end: dropped for good, no new request')
    m = BC(src=2); m.open(); m.finish(); m.parse('/mnt/mmc/Music/c/3.flac'); m.tick()
    expect(m.bmp() is None and m.paint() == [], 'the parser\'s path no longer the track\'s when the job ends: dropped')
    # a picture on screen whose source then changes is taken off and made again
    m = BC(src=2); m.open(); m.finish(); m.tick()
    expect(len(m.paint()) == 1, 'a picture for source 2 is shown')
    m.setword(COVER_SRC, 3)
    expect(m.paint() == [], 'the source changed: the paint draws nothing before the next tick')
    m.tick()
    expect(m.all('cc_build_add_aspect')[-1][4] == 3 and m.paint() == [], 'the tick takes it off and asks for source 3 (the picture is gone meanwhile)')


def life_tests(ctx):
    expect = ctx.expect

    # -- 8. a track change
    m = BC(tracks=(T1, T2)); m.open(); m.finish(); m.tick()
    b = m.bmp()
    expect(len(m.paint()) == 1, 'track 1 shows its picture')
    m.switch(1)
    expect(m.paint() == [], 'the track changes: a paint before the next tick draws nothing (never the old picture)')
    m.tick()
    expect(m.all('cc_build_add_aspect')[-1] == ('cc_build_add_aspect', T2, TMP, 320, 2) and m.held and m.paint() == [], 'the tick asks for the new track\'s art and keeps stock\'s picture')
    expect(m.count('widget_invalidate_force') >= 2 and m.bmp() == b, 'the cover repaints without it; the bitmap is kept for the next picture')
    m.finish(320, 240, rgba(320, 240, lambda x, y: (1, 2, 3))); m.tick()
    expect(m.pixels(b)[40 * 320] == word_of((1, 2, 3)) and m.pixels(b)[0] == BG and len(m.paint()) == 1 and len(m.bitmaps) == 1, 'the new picture replaces it in the same bitmap')
    m.switch(0)
    expect(m.paint() == [], 'back to track 1: its picture is gone, not shown')

    m = BC(tracks=(T1, T2)); m.open()
    m.finish(); m.switch(1); m.tick()
    expect(m.paint() == [] and m.bmp() is None and ('cc_build_stop',) in m.log and m.all('cc_build_add_aspect')[-1][1] == T2 and TMP not in m.present,
           'a result that completes as the track changes is dropped (the tick sees the change first): not decoded, not drawn, the new track\'s job runs')
    m.finish(320, 320, rgba(320, 320, lambda x, y: (9, 9, 9))); m.tick()
    expect(len(m.paint()) == 1 and m.pixels(m.bmp())[5] == word_of((9, 9, 9)), 'and the new track\'s own result is shown')
    m = BC(tracks=(T1, T2)); m.open(); m.switch(1); m.tick()
    expect(m.count('cc_build_stop') == 1 and m.count('cc_build_open') == 2 and m.held and m.job[0] == T2, 'a track change during extraction: the old job is cancelled (no wait), the new one started')
    m.play([], 0); m.tick()
    expect(m.count('cc_build_stop') == 2 and not m.held, 'the queue emptied: the job is cancelled, none started')
    m = BC(tracks=(T1, T2)); m.open(); m.finish_none(); m.tick(); m.switch(1); m.tick()
    expect(m.count('cc_build_open') == 2, 'a track given up on does not stop the next one from being tried')

    # -- 8b. a track change with stock's parser still on the last track: its source (and path buffer) are stale for a while
    for a, b in ((3, 2), (2, 3)):
        m = BC(tracks=(T1, T2), src=a); m.open(); m.finish(); m.tick()
        m.switch(1, parsed=False); m.tick()
        expect(m.count('cc_build_add_aspect') == 1 and m.paint() == [] and not m.held, f'{a} -> {b}: the new track with the old source word visible: no request (the parser has not finished it), nothing drawn')
        m.setword(COVER_SRC, 1); m.tick(); m.tick()
        expect(m.count('cc_build_add_aspect') == 1, f'{a} -> {b}: the parser busy (1): still no request')
        m.setword(COVER_SRC, b); m.tick()
        expect(m.count('cc_build_add_aspect') == 1, f'{a} -> {b}: the source already changed but the path buffer still the old track\'s: no request')
        m.parse(T2); m.tick()
        expect(m.all('cc_build_add_aspect')[-1] == ('cc_build_add_aspect', T2, TMP, 320, b), f'{a} -> {b}: the parser done: the request for the new track with the new source')
    # a request that went out for the old track, finished as the track changed (parser still on the old one): dropped, nothing asked until the parser has the new track
    m = BC(tracks=(T1, T2), src=3); m.open(); m.finish(); m.switch(1, parsed=False); m.tick()
    expect(m.bmp() is None and m.paint() == [] and m.count('cc_build_add_aspect') == 1 and not m.held, 'a result made for the old track is dropped when the track changes')

    # -- 9. the page ends
    m = BC(); m.open(); m.destroy()
    expect(m.count('cc_build_stop') == 1 and not m.held and ('timer_remove', 0x777) in m.log and m.bmp() is None and ('unlink', TMP) in m.log,
           'destroy during extraction: the job is cancelled without waiting, the timer and the file go')
    expect(m.call(m.timers[-1][0], a0=0) == 0 and m.count('cc_build_open') == 1, 'a tick that still arrives ends and does nothing')
    expect(not [c for c in m.log if c[0] == 'widget_invalidate_force'], 'the widget is going: no repaint of it')
    m = BC(); m.open(); m.finish(); m.tick(); m.destroy()
    expect(m.count('bitmap_destroy') == 1 and not m.bitmaps and m.count('cc_build_stop') == 1, 'destroy with a picture: the bitmap is freed')
    m = BC(); m.open(); m.finish(); m.tick()
    n = m.count('cc_build_stop'); m.call(m.bound[(WIN, EVT_DESTROY)][0], a0=0x12345678, a1=0)
    expect(m.count('cc_build_stop') == n and m.bmp() is not None and m.count('timer_remove') == 0, 'the end of another window is ignored')
    m.destroy()
    expect(not m.bitmaps and m.count('timer_remove') == 1, 'the page\'s own end frees it')
    # a new page starts clean
    m = BC(); m.open(); m.destroy(); m.open()
    expect(m.count('cc_build_open') == 2 and m.held and len(m.timers) == 2, 'a second page opens normally after the first ended')

    # -- 10. open and close again and again; a page that never says it is gone
    m = BC()
    for i in range(6):
        m.open(); m.tick()
        if i % 2: m.finish(); m.tick(); m.paint()
        m.destroy()
        expect(not m.held and not m.bitmaps, f'cycle {i}: nothing held, no bitmap left')
    expect(m.count('timer_add') == m.count('timer_remove') == 6 and m.count('bitmap_create_ex') == m.count('bitmap_destroy') == 3 and m.count('cc_build_open') == m.count('cc_build_stop'),
           'six pages: every timer removed, every bitmap destroyed, every set stopped')
    m = BC(); m.open(); m.finish(); m.tick()
    old = m.bmp(); m.open()
    expect(m.count('timer_remove') == 1 and old not in m.bitmaps and m.held, 'a page that never ended: its timer and bitmap go when the next page opens')
    expect(m.count('timer_add') == 2 and m.count('bitmap_destroy') == 1 and m.held, 'the new page owns one timer and one job set')

    # -- 11. the page is stock under an orphan or a stalled worker; the step never loops
    m = BC(); m.open(); m.paint()
    n = len(m.log)
    for _ in range(3): m.tick()
    expect(len(m.all('cc_build_open')) == 1 and len(m.log) - n < 200, 'a tick is a few calls')
    m = BC(); m.open(); m.finish(); m.tick(); m.screen(False)
    expect(len(m.paint()) == 1, 'the picture stays while the screen sleeps (only new jobs wait for the screen)')


SECTIONS = [hook_tests, job_tests, life_tests]


def run(ctx):
    for section in SECTIONS: section(ctx)
