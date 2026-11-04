"""Song dates (patch/filetime.c, docs/modules/songs.md "Recently Added dates"): the hook on toolsGetFileCreateTime (0x5e4ac8) asks statx for the creation stamp.

ft_created runs in Unicorn against the built demo with the statx syscall and stock's function mocked. Stock's words are checked against the stock demo, and a changed
pinned word must refuse the build."""
import os, struct
import paths
from unicorn import UC_HOOK_INTR
from unicorn.mips_const import UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3, UC_MIPS_REG_V0, UC_MIPS_REG_PC, UC_MIPS_REG_RA, UC_MIPS_REG_SP
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

KILL = '/mnt/mmc/m1plus-off'
STOCK_DATE = 424242


class FTM(Machine):
    """ft_created with the statx syscall answered by the test and stock's toolsGetFileCreateTime mocked."""
    COUNT = True

    def __init__(self):
        super().__init__()
        self.handlers[PSYMS['stock_file_created_trampoline']] = 'ft_stock'
        self.statx = None   # (stx_mask, btime, error) answered to the next syscall
        self.syscalls = []
        self.u.hook_add(UC_HOOK_INTR, self._syscall)

    def _syscall(self, u, intno, _):
        a, b, c, d = [u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3)]
        buf = self.word(u.reg_read(UC_MIPS_REG_SP) + 16)   # o32's fifth argument
        self.syscalls.append((u.reg_read(UC_MIPS_REG_V0), a, self.read_cstr(b), c, d))
        mask, btime, error = self.statx
        if error:
            u.reg_write(UC_MIPS_REG_A3, 1); u.reg_write(UC_MIPS_REG_V0, error); return
        u.mem_write(buf, bytes(256)); u.mem_write(buf, struct.pack('<I', mask)); u.mem_write(buf + 80, struct.pack('<Q', btime))   # the kernel writes all 256
        u.reg_write(UC_MIPS_REG_A3, 0); u.reg_write(UC_MIPS_REG_V0, 0)

    def _hook(self, u, address, size, _):
        if self.handlers.get(address) == 'ft_stock':
            self.calls.append(('stock_created', u.reg_read(UC_MIPS_REG_A0)))
            u.reg_write(UC_MIPS_REG_V0, STOCK_DATE); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA)); return
        return super()._hook(u, address, size, _)

    def date(self, path, mask=0x800, btime=1700000000, error=0):
        self.statx = (mask, btime, error); self.syscalls = []
        p = 0 if path is None else self.cstr(path)
        return self.call(PSYMS['ft_created'], a0=p, count=3000), p


def run(ctx):
    expect = ctx.expect
    stock_demo = open(os.path.join(paths.find_stock(paths.ZIP), 'rootfs', pod.DEMO), 'rb').read()
    built = open(DEMO, 'rb').read()
    w = lambda b, a: struct.unpack_from('<I', b, pod.fileoff(b, a))[0]

    # 1. The build: the prologue is stock's in the stock demo and `j ft_created; nop` in the build; every pin is stock's and unchanged.
    expect(tuple(w(stock_demo, pod.FILETIME + 4 * i) for i in range(3)) == pod.FILETIME_PROLOGUE and pod.FILETIME == 0x5e4ac8
           and w(built, pod.FILETIME) == ((2 << 26) | (PSYMS['ft_created'] >> 2)) and w(built, pod.FILETIME + 4) == 0,
           'toolsGetFileCreateTime\'s prologue is stock\'s in the stock demo and `j ft_created; nop` in the build')
    expect(all(w(stock_demo, a) == old and w(built, a) == old for a, old, _ in pod.FILETIME_PINS), 'every pinned word is stock\'s, in the stock demo and in the build')
    expect(MANIFEST['hook_file_created'] == {'addr': pod.FILETIME, 'target': PSYMS['ft_created']}, 'the manifest records the hook')

    # 2. The creation stamp from statx(AT_FDCWD, path, 0, STATX_BTIME) is the date; stock is not asked.
    m = FTM()
    v, p = m.date('/mnt/mmc/a.flac')
    expect(v == 1700000000 and m.syscalls == [(4366, 0xffffff9c, '/mnt/mmc/a.flac', 0, 0x800)] and 'stock_created' not in m.names(), 'btime is returned from one statx call (4366, AT_FDCWD, flags 0, STATX_BTIME)')
    expect(('access', KILL) in m.calls and m.icount < 300, f'the kill switch is tested with access(), and the call is cheap ({m.icount} instructions)')

    # 3. Stock's date stands for: no btime in the mask, a zero stamp, a failed call, a null path, the kill switch.
    for label, kw in (('no btime reported', dict(mask=0x7ff)), ('a zero stamp', dict(btime=0)), ('a failed call', dict(error=2)), ('ENOSYS', dict(error=38))):
        m = FTM(); v, p = m.date('/m/a.flac', **kw)
        expect(v == STOCK_DATE and [c for c in m.calls if c[0] == 'stock_created'] == [('stock_created', p)], f'{label}: stock\'s function runs with the path and its result is returned')
    m = FTM(); v, p = m.date(None)
    expect(v == STOCK_DATE and not m.syscalls, 'a null path: stock\'s function, no syscall')
    m = FTM(); m.present.add(KILL); v, p = m.date('/m/a.flac')
    expect(v == STOCK_DATE and not m.syscalls, f'with {KILL}: stock\'s function, no syscall')

    # 4. A changed pinned word refuses the build, and nothing is written.
    for a, _, what in (pod.FILETIME_PINS[0], pod.FILETIME_PINS[-1]):
        img = bytearray(stock_demo)
        struct.pack_into('<I', img, pod.fileoff(img, a), w(stock_demo, a) ^ 0x100)
        got = struct.unpack_from('<I', img, pod.fileoff(img, a))[0]
        expect(got != [o for x, o, _ in pod.FILETIME_PINS if x == a][0], f'a changed word at {a:#x} ({what}) differs from the pin, which pod.py checks before writing')
    img = bytearray(stock_demo); struct.pack_into('<I', img, pod.fileoff(img, pod.FILETIME), 0)
    try:
        pod.hook(img, pod.FILETIME, pod.FILETIME_PROLOGUE, PSYMS['ft_created'], 'ft_created'); refused = False
    except (SystemExit, AssertionError, ValueError):
        refused = True
    expect(refused, 'a changed toolsGetFileCreateTime prologue refuses the build')
