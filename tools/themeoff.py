"""Force the default asset theme and hide stock's Theme row (docs/modules/theme.md "theme1 is off").

Stock keeps the theme in `config.ini [SYSSET] THEME` (0 default, 1 theme1; the RAM word 0xa05a98), read by
`config_init` (0x4e5030, atoi, anything >= 2 becomes 0) and applied by `awtk_configinit` (0x4ccb5c:
`widget_set_theme(wm, flag ? "theme1" : "default")`). Three pinned word edits in demo, no payload code and no
boot hook:

- the clamp in `config_init`: `sltiu v1, v0, 2` becomes `sltiu v1, v0, 1`, so a stored 1 is read as 0 too (the
  file is left as it is; every boot reads it through this clamp, kill switch or not);
- the row table of the stock System page (`systemset_sysset_page_init` 0x4ada7c and its click dispatcher 0x4ad7b0 both
  index `0x97c8c0`, identity 0..15 in stock; entry 10 is `sset_theme` -> `systemset/theme_page`): entry 10 is moved to
  the end, so entries 0..14 skip it;
- the row count (15, or 16 when the language is 3) becomes one less.

Nothing else opens `systemset/theme_page`, so the picker has no entry point left.
"""
import struct

CLAMP = 0x4e63d8
TABLE = 0x97c8c0       # 16 words, row -> page index
COUNT = 0x4adb1c       # addiu v0, v0, 0xf: the rows (+1 for language 3)
THEME_ROW = 10         # the page index of Theme in the jump table at 0x748ae0 and the label table at 0x97c988
STOCK_TABLE = tuple(range(16))
NEW_TABLE = tuple(i for i in range(16) if i != THEME_ROW) + (THEME_ROW,)

# (address, stock word, new word, what)
EDITS = ((CLAMP, 0x2c430002, 0x2c430001, 'config_init: sltiu v1, v0, 2 -> 1: THEME 1 reads as 0'),
         (COUNT, 0x2442000f, 0x2442000e, 'systemset_sysset_page_init: row count 15 -> 14 (16 -> 15)')) + tuple(
    (TABLE + 4 * i, STOCK_TABLE[i], NEW_TABLE[i], f'row table[{i}]') for i in range(16) if STOCK_TABLE[i] != NEW_TABLE[i])
# stock words around the edits that must stay (the instruction the clamp feeds, the count's setup, the table's end and the label table)
PINS = ((CLAMP + 4, 0x0003100a, 'config_init: movz v0, zero, v1'), (CLAMP - 4, 0x8fbc0018, 'config_init: lw gp'),
        (COUNT - 4, 0x2c420001, 'sysset init: sltiu v0, v0, 1 (language 3)'), (COUNT - 8, 0x38420003, 'sysset init: xori v0, v0, 3'),
        (TABLE + 64, 0, 'row table: the next word (16 entries only)'))


def _word(patched, fileoff, a):
    return struct.unpack_from('<I', patched, fileoff(patched, a))[0]


def apply(patched, fileoff):
    """Check every stock word, then write the new ones into the bytearray `patched`; a mismatch changes nothing."""
    for a, old, _, what in EDITS:
        got = _word(patched, fileoff, a)
        if got != old: raise ValueError(f'{a:#x} ({what}): {got:#010x} != pinned {old:#010x}')
    for a, old, what in PINS:
        got = _word(patched, fileoff, a)
        if got != old: raise ValueError(f'{a:#x} ({what}): {got:#010x} != pinned {old:#010x}')
    for a, _, new, _ in EDITS:
        struct.pack_into('<I', patched, fileoff(patched, a), new)
