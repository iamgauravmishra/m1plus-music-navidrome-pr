"""Stock theme1 is off (tools/themeoff.py, docs/modules/theme.md): demo's own code under Unicorn, once with the stock
words written back (the app as it was: theme1 is read, the Theme row is listed) and once as built.

- config_init's clamp (0x4e63d8 sltiu, 0x4e63dc movz): the stored THEME word 0, 1, 2, 7, -1 and what the RAM flag gets;
- the System page's row count (0x4adb14..0x4adb20, from the language word) and the row table 0x97c8c0: which page index each
  row opens, and that Theme (index 10, label `sset_theme`, `systemset/theme_page`) is no row while every other page stays;
- the pinned words themselves, and that an already default setting (0) is untouched by the clamp."""
import struct
import themeoff
from harness import *   # noqa: F401,F403


def machine(stock):
    m = Machine()
    if stock:
        for a, old, _, _ in themeoff.EDITS: m.setword(a, old)
    return m


def clamp(m, stored):
    """The flag config_init keeps for a stored THEME value: sltiu v1, v0, 2 / movz v0, zero, v1 run from demo."""
    u = m.u
    u.reg_write(UC_MIPS_REG_V0, stored & 0xffffffff)
    u.emu_start(themeoff.CLAMP, themeoff.CLAMP + 8)
    return u.reg_read(UC_MIPS_REG_V0)


def rows(m, language):
    """The page index of each row the System page lists: the count the init computes (0x4adb14 xori .. 0x4adb20), then the table."""
    u = m.u
    u.reg_write(UC_MIPS_REG_V0, language)
    u.emu_start(themeoff.COUNT - 8, themeoff.COUNT + 4)   # xori v0, v0, 3 / sltiu v0, v0, 1 / addiu v0, v0, 0xf(e)
    n = u.reg_read(UC_MIPS_REG_V0)
    return [m.word(themeoff.TABLE + 4 * i) for i in range(n)]


def run(ctx):
    ex = ctx.expect
    stock, built = machine(True), machine(False)
    # the flag
    ex([clamp(stock, v) for v in (0, 1, 2, 7, -1)] == [0, 1, 0, 0, 0], 'stock reads THEME 1 as theme1 (the flag is 1), anything else as the default')
    ex([clamp(built, v) for v in (0, 1, 2, 7, -1)] == [0, 0, 0, 0, 0], 'built: a saved theme1 (THEME 1), a default or junk value all read as the default (flag 0)')
    # the Theme row
    for lang in (0, 1, 2, 3, 5):
        want = list(range(16 if lang == 3 else 15))
        ex(rows(stock, lang) == want, f'stock lists rows 0..{len(want) - 1} (language {lang}), Theme (page index 10) among them')
        got = rows(built, lang)
        ex(themeoff.THEME_ROW not in got and sorted(got + [themeoff.THEME_ROW]) == want and got == [i for i in want if i != themeoff.THEME_ROW],
           f'built (language {lang}): every other page in its stock order, Theme not listed ({got})')
    # the positions that mean something stay: the two switch rows are rows 6 and 7 (images img_carmode6 / img_doublewake7, kind 6 and 7)
    ex(built.word(themeoff.TABLE + 24) == 6 and built.word(themeoff.TABLE + 28) == 7, 'the car mode and double-tap switch rows keep their positions 6 and 7')
    # nothing reaches the picker: the table is the only source of a row index, and the dispatcher's jump for index 10 is the only code that names the page
    names = {0x4ad9fc: 'systemset/theme_page', 0x4d13d8: 'systemset/theme_page'}
    ex(all(built.word(a) == stock.word(a) for a in names), 'the stock literal sites are unchanged (the page stays in demo, unreachable)')
    # the edits are the only differences between the two machines' code and table
    diff = [a for a in range(0x4ad000, 0x4e7000, 4) if built.word(a) != stock.word(a)] + [a for a in range(themeoff.TABLE, themeoff.TABLE + 64, 4) if built.word(a) != stock.word(a)]
    ex(sorted(diff) == sorted(a for a, _, _, _ in themeoff.EDITS), f'only the pinned words differ from stock ({[hex(a) for a in diff]})')
    ex(all(built.word(a) == new for a, _, new, _ in themeoff.EDITS) and all(built.word(a) == w for a, w, _ in themeoff.PINS), 'the built demo holds every new word and every pinned neighbour')
    # apply() refuses a changed stock word and writes nothing
    img = bytearray(0x1000000)
    ident = lambda b, a: a
    for a, old, _, _ in themeoff.EDITS: struct.pack_into('<I', img, a, old)
    for a, w, _ in themeoff.PINS: struct.pack_into('<I', img, a, w)
    for a, _, _, what in themeoff.EDITS[:3]:
        bad = bytearray(img); bad[a] ^= 1; before = bytes(bad)
        try: themeoff.apply(bad, ident); refused = False
        except ValueError: refused = True
        ex(refused and bytes(bad) == before, f'themeoff refuses a changed stock word at {a:#x} and writes nothing')
    themeoff.apply(img, ident)
    ex(all(struct.unpack_from('<I', img, a)[0] == new for a, _, new, _ in themeoff.EDITS), 'apply writes every new word')
