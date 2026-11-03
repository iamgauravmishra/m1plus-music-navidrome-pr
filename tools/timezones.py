"""Time zones: the picker's zones, their TZ values and the pinned words (docs/modules/timezones.md).

Ported from q2-pod (tools/build.py TIMEZONES, TIMEZONE_ORDER, timezone_offset). Stock's saved indices
0-26 (`[SYSSET] TIMEZONE`) keep their place; q2-pod's additions follow as 27 and up. Stock's rows
whose zone was wrong or out of date take q2-pod's corrected TZ value (GMT-12, Mexico City, Tehran,
GMT+6, Fiji). The picker lists the zones west to east; the saved index is unchanged by that order.
"""
import re

# (label, TZ) for the saved index = position. Labels fit the picker's 260 px row; the offset in the
# label is the standard one. POSIX rules stand in where the rootfs tzdata is out of date.
TIMEZONES = (
    ('GMT-12 Baker Island', '<-12>12'), ('GMT-11 Midway', 'Pacific/Midway'),
    ('GMT-10 Honolulu', 'Pacific/Honolulu'), ('GMT-9 Anchorage', 'America/Anchorage'),
    ('GMT-8 Los Angeles', 'America/Los_Angeles'), ('GMT-7 Denver', 'America/Denver'),
    ('GMT-6 Mexico City', 'CST6'), ('GMT-5 New York', 'America/New_York'),
    ('GMT-4 Halifax', 'America/Halifax'), ("GMT-3:30 St. John's", 'America/St_Johns'),
    ('GMT-3 Buenos Aires', 'America/Argentina/Buenos_Aires'), ('GMT-1 Azores', 'Atlantic/Azores'),
    ('GMT+0 London', 'Europe/London'), ('GMT+1 Amsterdam', 'Europe/Amsterdam'),
    ('GMT+2 Bucharest', 'Europe/Bucharest'), ('GMT+3 Kuwait', 'Asia/Kuwait'),
    ('GMT+3:30 Tehran', '<+0330>-3:30'), ('GMT+4 Muscat', 'Asia/Muscat'),
    ('GMT+4:30 Kabul', 'Asia/Kabul'), ('GMT+5 Karachi', 'Asia/Karachi'),
    ('GMT+6 Dhaka', 'Asia/Dhaka'), ('GMT+7 Bangkok', 'Asia/Bangkok'),
    ('GMT+8 Shanghai', 'Asia/Shanghai'), ('GMT+9 Tokyo', 'Asia/Tokyo'),
    ('GMT+9:30 Adelaide', 'Australia/Adelaide'), ('GMT+10 Sydney', 'Australia/Sydney'),
    ('GMT+12 Fiji', '<+12>-12'),
    # q2-pod's additions
    ('GMT-9:30 Marquesas', 'Pacific/Marquesas'), ('GMT-2 South Georgia', 'Atlantic/South_Georgia'),
    ('GMT+5:30 Colombo', 'Asia/Colombo'), ('GMT+5:45 Kathmandu', 'Asia/Kathmandu'),
    ('GMT+6:30 Yangon', 'Asia/Yangon'), ('GMT+8:45 Eucla', 'Australia/Eucla'),
    ('GMT+10:30 L. Howe', 'Australia/Lord_Howe'), ('GMT+11 Noumea', 'Pacific/Noumea'),
    ('GMT+12:45 Chatham', 'Pacific/Chatham'), ('GMT+13 Tongatapu', 'Pacific/Tongatapu'),
    ('GMT+14 Kiritimati', 'Pacific/Kiritimati'),
    ('GMT-6 Chicago', 'America/Chicago'), ('GMT-7 Phoenix', 'America/Phoenix'),
    ('GMT+5:30 Kolkata', 'Asia/Kolkata'), ('GMT+10 Brisbane', 'Australia/Brisbane'),
    ('GMT+12 Auckland', 'Pacific/Auckland'),
)
STOCK_COUNT = 27     # stock's saved indices 0-26
DEFAULT = 22         # config_init's default (Shanghai), also the stock fallback for an index it does not know
COUNT = len(TIMEZONES)
MAX_LABEL = 31       # the label is copied into the row builder's 0x80 byte buffer; kept short for the row


def offset_minutes(label):
    sign, h, m = re.match(r'GMT([+-])(\d+)(?::(\d+))?', label).groups()
    return (1 if sign == '+' else -1) * (int(h) * 60 + int(m or 0))


# The picker's rows, west to east: the saved index each row shows.
ORDER = tuple(sorted(range(COUNT), key=lambda i: (offset_minutes(TIMEZONES[i][0]), TIMEZONES[i][0])))

# Where the zoneinfo names must exist in the rootfs (a TZ that starts with '<' is a POSIX rule).
ZONEINFO_NAMES = tuple(tz for _, tz in TIMEZONES if not tz.startswith('<') and '/' in tz)

# Code addresses (docs/modules/addresses.md "Time zones").
SELECT = 0x4d6b2c                       # select_timezone: g_time_zone -> setenv("TZ"); hooked prologue
SELECT_PROLOGUE = (0x3c1c0053, 0x279cd3a4, 0x0399e021)
BOOT_CLAMP = 0x4e65dc                   # config_init: sltiu v1, v0, 0x1b (a saved index above 26 becomes 22)
ROWS_COUNT = 0x4a246c                   # autosynctime page: addiu v0, zero, 0x1d (rows 0..28: switch, header, 27 zones)
ROW_CALL = 0x4a25a8                     # bal timezone_listitem_layout(item, row)
LABEL_CALL = 0x4a2248                   # timezone_listitem_layout: jalr strcpy(buf, pointers[row - 2])
LABEL_SLOT = 0x4a224c                   # its delay slot: lw a1, 0x80(v0)
CLICK_LIMIT = 0x4a2604                  # timezone_select: sltiu v1, v0, 0x1e (row number < 30)

ROW_HEIGHT = 0x4a2518                   # page builder: addiu v0, zero, 0x40 (delay slot of bne s2, 1: zone rows only; the header's is 0x4a251c, the switch's 0x4a24bc)
LABEL_STYLE = 0x4a22a4                  # row builder: addiu a1, a1, 0x7628 (widget_use_style "srlabel_leftwhite21_style"; GOT page 0x740000)
LABEL_Y = 0x4a225c                      # row builder: addiu a2, zero, 0x14 (hscroll_label_create y; x 12, w 260, h 21 stay)
TICK_Y = 0x4a2308                       # row builder: addiu a2, zero, 0x11 (image_create y; x 282, 26 x 26 stay)
ROW_H = 48
STYLE18_LO = 0x5f2c                     # "srlabel_leftwhite18_style" at 0x745f2c (stock uses it at 0x487434 and 9 more sites)
LABEL_Y_NEW = 13                        # (48 - 21) / 2 rounded down
TICK_Y_NEW = 11                         # (48 - 26) / 2

JALR_T9 = 0x0320f809
MOVE_A1_S4 = 0x02802825                 # or a1, s4, zero: the zone index the row builder computed (row - 2)


def edits(jal_row, jal_label):
    """(address, stock word, new word, what) for every non-hook word. jal_* are the encoded jal words."""
    return (
        (BOOT_CLAMP, 0x2c43001b, 0x2c430000 | COUNT, 'config_init: a saved index below the count is kept'),
        (ROWS_COUNT, 0x2402001d, 0x24020000 | (COUNT + 2), 'timezone page: rows 0 and 1, then one a zone'),
        (CLICK_LIMIT, 0x2c43001e, 0x2c430000 | (COUNT + 3), 'timezone_select: row numbers below count + 3 (stock: 27 + 3)'),
        (ROW_CALL, 0x0411ff07, jal_row, 'page builder: jal tz_row instead of bal timezone_listitem_layout'),
        (LABEL_CALL, JALR_T9, jal_label, 'row builder: jal tz_label(buf, index) instead of strcpy'),
        (LABEL_SLOT, 0x8c450080, MOVE_A1_S4, 'row builder: a1 = the zone index (its delay slot)'),
        (ROW_HEIGHT, 0x24020040, 0x24020000 | ROW_H, 'page builder: zone rows 48 px tall (stock 64); the delay slot of the bne that skips the header row'),
        (LABEL_STYLE, 0x24a57628, 0x24a50000 | STYLE18_LO, 'row builder: label style srlabel_leftwhite18_style (0x745f2c; stock leftwhite21 0x747628)'),
        (LABEL_Y, 0x24060014, 0x24060000 | LABEL_Y_NEW, 'row builder: label y 13 (stock 20): centred in the 48 px row'),
        (TICK_Y, 0x24060011, 0x24060000 | TICK_Y_NEW, 'row builder: tick y 11 (stock 17): centred in the 48 px row'),
    )


PINS = (   # (address, stock word, what it proves); the edited words are pinned through edits()
    (0x4d6b38, 0x27bdffa0, 'select_timezone: addiu sp, sp, -0x60 (the trampoline resumes here)'),
    (0x4d6b60, 0x8f82aeac, 'select_timezone: lw v0, GOT time_zone (0xa05ab4)'),
    (0x4d6b64, 0x8c420000, 'select_timezone: lw v0, (v0): the saved index'),
    (0x4d6b68, 0x2c43001b, 'select_timezone: sltiu v1, v0, 0x1b: stock knows 27 zones'),
    (0x4d6ba8, 0x8f99b744, 'select_timezone: lw t9, GOT toolsSetTimeZone'),
    (0x4d6bac, JALR_T9, 'select_timezone: jalr toolsSetTimeZone(name)'),
    (0x4e65d4, 0x24040016, 'config_init: a0 = 22, the default zone'),
    (0x4e65e0, 0x0043200b, 'config_init: movn a0, v0, v1'),
    (0x4e65e4, 0x8f82aeac, 'config_init: lw v0, GOT time_zone'),
    (0x4e65ec, 0x0411c14f, 'config_init: bal select_timezone'),
    (0x4a21c8, 0x3c1c0056, 'timezone_listitem_layout prologue'), (0x4a21cc, 0x279c1d08, 'timezone_listitem_layout prologue'),
    (0x4a21d0, 0x0399e021, 'timezone_listitem_layout prologue'),
    (0x4a220c, 0x2674fffe, 'timezone_listitem_layout: addiu s4, s3, -2: the zone index'),
    (0x4a2210, 0x8f85a888, 'timezone_listitem_layout: lw a1, GOT (the label pointer array 0x97c810, 27 entries)'),
    (0x4a2218, 0x24a5c810, 'timezone_listitem_layout: addiu a1, a1, -0x37f0 (0x97c810)'),
    (0x4a223c, 0x02202025, 'timezone_listitem_layout: move a0, s1 (the 0x80 byte label buffer)'),
    (0x4a2244, 0x8f99f324, 'timezone_listitem_layout: lw t9, GOT strcpy'),
    (0x4a2250, 0x24020015, 'timezone_listitem_layout: the hscroll_label setup follows'),
    (0x4a2374, 0x8f82aeac, 'timezone_listitem_layout: lw v0, GOT time_zone (the ticked row)'),
    (0x4a2378, 0x8c420000, 'timezone_listitem_layout: lw v0, (v0)'),
    (0x4a237c, 0x16820026, 'timezone_listitem_layout: bne s4, v0: the ticked row is index == time_zone'),
    (0x4a2424, 0x3c1c0056, 'page builder prologue'), (0x4a2428, 0x279c1aac, 'page builder prologue'), (0x4a242c, 0x0399e021, 'page builder prologue'),
    (0x4a2468, 0x90530000, 'page builder: lbu s3, (AUTOSYNCTIME flag)'),
    (0x4a2470, 0x8f99a860, 'page builder: lw t9, GOT widget_lookup'),
    (0x4a2474, 0x0073100a, 'page builder: movz v0, v1, s3: only the switch row while auto time is on'),
    (0x4a2598, 0x02402825, 'page builder: move a1, s2 (the row number)'),
    (0x4a259c, 0x8fbc0018, 'page builder: lw gp, 0x18(sp)'),
    (0x4a25a0, 0x00402025, 'page builder: move a0, v0 (the list item)'),
    (0x4a25a4, 0x8f99aeb8, 'page builder: lw t9, GOT timezone_listitem_layout'),
    (0x4a25ac, 0x00408025, 'page builder: move s0, v0 (delay slot)'),
    (0x4a25b8, 0x3c1c0056, 'timezone_select prologue'), (0x4a25bc, 0x279c1918, 'timezone_select prologue'), (0x4a25c0, 0x0399e021, 'timezone_select prologue'),
    (0x4a25f8, 0x8f99f314, 'timezone_select: lw t9, GOT atoi'),
    (0x4a2600, 0x8e040010, 'timezone_select: lw a0, 0x10(s0): the row widget name'),
    (0x4a2608, 0x10600015, 'timezone_select: beqz v1: a row number above the limit does nothing'),
    (0x4a269c, 0x2450fffe, 'timezone_select: addiu s0, v0, -2: the zone index'),
    (0x4a27a4, 0x8f99aec0, 'timezone_select: lw t9, GOT select_timezone'),
    (0x4a27a8, JALR_T9, 'timezone_select: jalr select_timezone'),
    (0x97c810, 0x747834, 'label key pointer array: first entry'),
)
