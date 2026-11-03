"""Time zones (patch/timezones.c, tools/timezones.py, docs/modules/timezones.md): the select_timezone hook, the saved-index clamp, the picker's row count, order and labels.

The payload functions run in Unicorn against the built demo; stock's setenv("TZ") wrapper, the row builder and select_timezone's body are mocked. Stock's words are checked
against the stock demo, and a changed pinned word must refuse the build."""
import os, struct
import paths
import timezones as tz
from unicorn.mips_const import UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_V0, UC_MIPS_REG_PC, UC_MIPS_REG_RA
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

KILL = '/mnt/mmc/m1plus-off'
SET_TZ, ROW = pod.FUNCTIONS['toolsSetTimeZone'][2], pod.FUNCTIONS['timezone_listitem_layout'][2]
STOCK_RESUME = tz.SELECT + 12
STOCK_ZONES = ('Pacific/Kwajalein', 'Pacific/Midway', 'Pacific/Honolulu', 'America/Anchorage', 'America/Tijuana', 'America/Denver', 'America/Mexico_City', 'America/New_York',
               'Canada/Atlantic', 'America/St_Johns', 'America/Argentina/Buenos_Aires', 'Atlantic/Azores', 'Europe/London', 'Europe/Amsterdam', 'Europe/Bucharest', 'Asia/Kuwait',
               'Asia/Tehran', 'Asia/Muscat', 'Asia/Kabul', 'Asia/Karachi', 'Asia/Almaty', 'Asia/Bangkok', 'Asia/Shanghai', 'Asia/Tokyo', 'Australia/Adelaide', 'Australia/Sydney',
               'Pacific/Fiji')   # select_timezone's 27 names, as read from the stock demo (0x74a714..)
CORRECTED = {0: '<-12>12', 4: 'America/Los_Angeles', 6: 'CST6', 8: 'America/Halifax', 16: '<+0330>-3:30', 20: 'Asia/Dhaka', 26: '<+12>-12'}


class TZM(Machine):
    """tz_select, tz_row and tz_label with stock's setenv wrapper, the row builder and select_timezone's body mocked."""
    COUNT = True

    def __init__(self):
        super().__init__()
        self.handlers[PSYMS['stock_timezone_trampoline']] = 'tz_stock'
        self.rows = []

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address)
        if name == 'toolsSetTimeZone':
            self.calls.append(('set_tz', self.read_cstr(u.reg_read(UC_MIPS_REG_A0)))); ret = 7
        elif name == 'timezone_listitem_layout':
            self.calls.append(('row', u.reg_read(UC_MIPS_REG_A0), u.reg_read(UC_MIPS_REG_A1))); ret = 0x5150
        elif name == 'tz_stock':
            self.calls.append(('stock_select',)); ret = 99
        else:
            return super()._hook(u, address, size, _)
        u.reg_write(UC_MIPS_REG_V0, ret); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    def select(self, index):
        self.setword(pod.DATA['TIME_ZONE'][0], index)
        v = self.call(PSYMS['tz_select'], count=2000)
        return v, [c for c in self.calls if c[0] in ('set_tz', 'stock_select')]

    def label(self, index):
        buf = self.alloc(0x80); self.u.mem_write(buf, b'\xaa' * 0x80)
        self.call(PSYMS['tz_label'], a0=buf, a1=index, count=4000)
        return bytes(self.u.mem_read(buf, 0x80))


def run(ctx):
    expect = ctx.expect
    stock_demo = open(os.path.join(paths.find_stock(paths.ZIP), 'rootfs', pod.DEMO), 'rb').read()
    built = open(DEMO, 'rb').read()
    w = lambda b, a: struct.unpack_from('<I', b, pod.fileoff(b, a))[0]
    n = tz.COUNT

    # 1. The table: stock's 27 indices stay, the additions follow, corrections are q2-pod's, every name exists in the stock rootfs.
    expect(n == 43 and tz.STOCK_COUNT == 27 and tz.DEFAULT == 22 and tz.TIMEZONES[tz.DEFAULT][1] == 'Asia/Shanghai', 'the table has 43 zones; stock\'s 27 come first and the default index 22 is Shanghai')
    expect(all(tz.TIMEZONES[i][1] == z for i, z in enumerate(STOCK_ZONES) if i not in CORRECTED), 'every stock index that was right keeps its zone')
    expect(all(tz.TIMEZONES[i][1] == z for i, z in CORRECTED.items()), 'the seven corrected rows (GMT-12, Los Angeles, Mexico City, Halifax, Tehran, Dhaka, Fiji) carry q2-pod\'s TZ values')
    zi = os.path.join(paths.find_stock(paths.ZIP), 'rootfs', 'usr', 'share', 'zoneinfo')
    expect(all(os.path.isfile(os.path.join(zi, name)) for name in tz.ZONEINFO_NAMES), 'every zone name exists in the stock rootfs zoneinfo')
    expect(any(z == 'Asia/Kolkata' and l.startswith('GMT+5:30') for l, z in tz.TIMEZONES), 'GMT+5:30 India (Asia/Kolkata) is in the table')
    expect(sorted(tz.ORDER) == list(range(n)) and [tz.offset_minutes(tz.TIMEZONES[i][0]) for i in tz.ORDER] == sorted(tz.offset_minutes(l) for l, _ in tz.TIMEZONES),
           'the rows are a permutation of the indices, west to east')
    expect(len({l for l, _ in tz.TIMEZONES}) == n and all(0 < len(l) <= tz.MAX_LABEL for l, _ in tz.TIMEZONES), 'labels are distinct and short')

    # 2. The build: hook, clamp, counts, call sites; every pinned word stock's in the stock demo and unchanged in the build but the edits.
    jal_to = lambda word: word >> 26 == 3 and (word & 0x3ffffff) << 2
    edits = tz.edits(0, 0)
    edited = {a for a, *_ in edits}
    expect(tuple(w(stock_demo, tz.SELECT + 4 * i) for i in range(3)) == tz.SELECT_PROLOGUE and w(built, tz.SELECT) == ((2 << 26) | (PSYMS['tz_select'] >> 2)) and w(built, tz.SELECT + 4) == 0,
           'select_timezone\'s prologue is stock\'s in the stock demo and `j tz_select; nop` in the build')
    expect(all(w(stock_demo, a) == old for a, old, _ in tz.PINS) and all(w(stock_demo, a) == old for a, old, _, _ in edits), 'every pinned word is stock\'s in the stock demo')
    expect(all(w(built, a) == old for a, old, _ in tz.PINS if a not in edited), 'every pinned word that is not an edit is unchanged in the build')
    expect(w(built, tz.BOOT_CLAMP) == 0x2c430000 | n and w(built, tz.ROWS_COUNT) == 0x24020000 | (n + 2) and w(built, tz.CLICK_LIMIT) == 0x2c430000 | (n + 3),
           'config_init keeps a saved index below 43; the page builds 2 + 43 rows; the click limit follows')
    expect(jal_to(w(built, tz.ROW_CALL)) == PSYMS['tz_row'] and jal_to(w(built, tz.LABEL_CALL)) == PSYMS['tz_label'] and w(built, tz.LABEL_SLOT) == tz.MOVE_A1_S4,
           'the page builder calls tz_row, the row builder calls tz_label(buf, index)')
    expect(w(built, tz.ROW_CALL + 4) == 0x00408025 and w(built, tz.LABEL_CALL - 4) == 0x8f99f324, 'the delay slot of the row call and the GOT load before the label call are stock\'s')
    # Rows: 48 px tall zone rows (the header 0x2e and the switch row 0x40 stay), label in the stock 18 px white style, label and tick centred.
    sty = lambda b, a: b[pod.fileoff(b, a):pod.fileoff(b, a) + 26].split(b'\0')[0]
    expect(w(built, tz.ROW_HEIGHT) == 0x24020030 and w(built, 0x4a251c) == 0x2402002e and w(built, 0x4a24bc) == w(stock_demo, 0x4a24bc),
           'zone rows are 48 px; the header (0x2e) and the switch row words are stock\'s')
    expect(sty(stock_demo, 0x740000 + tz.STYLE18_LO) == b'srlabel_leftwhite18_style' and sty(built, 0x740000 + tz.STYLE18_LO) == b'srlabel_leftwhite18_style'
           and sty(built, 0x747628) == b'srlabel_leftwhite21_style' and w(built, tz.LABEL_STYLE) == 0x24a55f2c, 'the label style word points at srlabel_leftwhite18_style (the stock 18 px white left label)')
    expect(w(built, tz.LABEL_Y) == 0x2406000d and w(built, tz.TICK_Y) == 0x2406000b and (tz.ROW_H - 21) // 2 == tz.LABEL_Y_NEW and (tz.ROW_H - 26) // 2 == tz.TICK_Y_NEW
           and all(w(built, a) == w(stock_demo, a) for a in (0x4a2250, 0x4a2258, 0x4a2264, 0x4a22fc, 0x4a2304, 0x4a2310)), 'label y 13 and tick y 11; x, width and height words are stock\'s')
    expect(MANIFEST['hook_timezone'] == {'addr': tz.SELECT, 'target': PSYMS['tz_select']} and MANIFEST['timezone_row']['target'] == PSYMS['tz_row']
           and MANIFEST['timezone_label']['target'] == PSYMS['tz_label'], 'the manifest records the three entry points')
    expect(pod.FUNCTIONS['toolsSetTimeZone'][2] == 0x5e3288 and pod.DATA['TIME_ZONE'][0] == 0xa05ab4 and ROW == 0x4a21c8, 'stock\'s setenv wrapper, time_zone and the row builder are the pinned addresses')

    # 3. tz_select: our TZ for every saved index; the kill switch or an unknown index runs stock's function.
    m = TZM()
    for i, (_, name) in enumerate(tz.TIMEZONES):
        v, c = m.select(i)
        expect(v == 7 and c == [('set_tz', name)], f'index {i}: setenv("TZ", {name!r}) and its result returned (got {c})')
    expect(m.icount < 200, f'a mapping costs a few instructions ({m.icount})')
    for i in (n, n + 1, 100, 0xffffffff, 0x80000000):
        v, c = m.select(i)
        expect(v == 99 and c == [('stock_select',)], f'index {i:#x} (out of range): stock\'s function')
    m.present.add(KILL)
    for i in (0, 22, 26, 27, 39, 42):
        v, c = m.select(i)
        expect(v == 99 and c == [('stock_select',)], f'index {i} with {KILL}: stock\'s function')
    expect(('access', KILL) in m.calls, 'the kill switch is tested with access()')
    expect(PSYMS['stock_timezone_trampoline'] and True, 'the trampoline symbol exists')

    # 4. tz_row: row 2 + p builds the zone ORDER[p] (stock numbers its rows zone + 2); any other row is passed through.
    for p in range(n):
        m.call(PSYMS['tz_row'], a0=0x1234, a1=2 + p, count=500)
        expect(m.calls == [('row', 0x1234, tz.ORDER[p] + 2)], f'row {2 + p} shows zone {tz.ORDER[p]}')
    seen = []
    for p in range(n):
        m.call(PSYMS['tz_row'], a0=1, a1=2 + p, count=500); seen.append(m.calls[0][2] - 2)
    expect(sorted(seen) == list(range(n)), 'every zone is shown exactly once')
    for row in (0, 1, 2 + n, 99):
        m.call(PSYMS['tz_row'], a0=5, a1=row, count=500)
        expect(m.calls == [('row', 5, row)], f'row {row} is not a zone row: passed through')
    expect(m.call(PSYMS['tz_row'], a0=5, a1=2, count=500) == 0x5150, 'the builder\'s result is returned')

    # 5. tz_label: the label text of the zone, NUL ended in the 0x80 byte buffer; an unknown index gives an empty text.
    for i, (label, _) in enumerate(tz.TIMEZONES):
        b = m.label(i)
        expect(b[:len(label) + 1] == label.encode() + b'\0', f'label {i}: {label!r}')
    expect(m.label(n)[0] == 0 and m.label(0xffffffff)[0] == 0, 'an index past the table gives an empty label')
    expect(any(b'GMT+5:30 Kolkata' == m.label(i).split(b'\0')[0] for i in range(n)), 'the picker lists GMT+5:30 Kolkata')

    # 6. A changed pinned word refuses the build, and nothing is written.
    for a, _, what in (tz.PINS[0], tz.PINS[10], tz.PINS[-1]) + tuple((a, o, w_) for a, o, _, w_ in edits[:2]):
        img = bytearray(stock_demo)
        struct.pack_into('<I', img, pod.fileoff(img, a), w(stock_demo, a) ^ 0x100)
        before = bytes(img)
        try:
            pod.patch_timezones(img, PSYMS, len(open(os.path.join(BUILD, 'patch.bin'), 'rb').read()))
            refused = False
        except (SystemExit, AssertionError, ValueError):
            refused = True
        expect(refused and bytes(img) == before, f'a changed word at {a:#x} refuses the build and leaves the image alone')
    img = bytearray(stock_demo); struct.pack_into('<I', img, pod.fileoff(img, tz.SELECT), 0)
    try:
        pod.patch_timezones(img, PSYMS, 10 ** 6); refused = False
    except (SystemExit, AssertionError, ValueError):
        refused = True
    expect(refused, 'a changed select_timezone prologue refuses the build')
