# Time zones

The Settings > Date & Time zone picker lists 43 zones (stock: 27) west to east, and the saved
zone maps to a `TZ` value from our table. After q2-pod (`tools/build.py` `TIMEZONES`,
`TIMEZONE_ORDER`; `patch/navigation.c` `ringnav_timezone`). Table, order and pins:
`tools/timezones.py`; code: `patch/timezones.c`; build wiring: `tools/pod.py patch_timezones`.
Prompted by a user report that GMT+5:30 (India) was missing.

## Stock flow

- `[SYSSET] TIMEZONE` in `/mnt/data/config.ini` (default text `"22"`, Shanghai) is read by
  `config_init` `0x4e5030`, clamped (`atoi`; `sltiu 0x1b` at `0x4e65dc`: an index of 27 or more becomes
  22), stored in the global `time_zone` `0xa05ab4`, and `select_timezone` `0x4d6b2c` (no arguments) maps
  the index through a 27-way jump table to a zoneinfo name and calls `toolsSetTimeZone` `0x5e3288`
  (`setenv("TZ", name, 1)`; no `tzset`). Any index of 27 or more gives `Asia/Shanghai`.
- The picker is the "autosynctime" page: the page builder `0x4a2424` makes rows 0 (auto time switch),
  1 (header) and, only while auto time is off, rows 2..28, one per zone (`timezone_listitem_layout`
  `0x4a21c8`). A zone row is named `"%d"` (its row number), its tick image `image_choice<index>`
  (ticked when `index == time_zone`), and its text is `widget_set_tr_text` of an i18n key
  (`timezone_gmt-12` ... `timezone_gmt+12`, pointer array `0x97c810`, copied to the stack: 27 entries,
  room for no more). The stock text is `(GMT+06:00)Asia/Almaty` and so on, per language.
- The click handler `0x4a25b8` `atoi`s the row name (`< 30`), ignores 0 (switch) and 1, and for the rest
  stores `row - 2` in `time_zone`, writes the key, un-ticks the old row, ticks the new one and calls
  `select_timezone` (`0x4a27a4`).

## Table

Indices 0-26 are stock's, in stock's order, so a saved zone keeps its meaning. 27-42 are q2-pod's
additions (Marquesas, South Georgia, Colombo, Kathmandu, Yangon, Eucla, Lord Howe, Noumea, Chatham,
Tongatapu, Kiritimati, Chicago, Phoenix, **Kolkata**, Brisbane, Auckland). Stock rows whose zone was
wrong or has changed take q2-pod's values: index 0 `<-12>12` (stock: Kwajalein, which is +12), 4 Los
Angeles (stock Tijuana), 6 `CST6` (Mexico City dropped DST in 2022), 8 Halifax (stock `Canada/Atlantic`),
16 `<+0330>-3:30` (Tehran dropped DST in 2022), 20 Dhaka (stock Almaty, +5 since 2024), 26 `<+12>-12`
(Fiji suspended DST). Every zoneinfo name exists in the stock rootfs (`test/pod/timezones.py`); POSIX
rules stand in where its tzdata is out of date.

## Hooks (all pinned; `tools/timezones.py` `PINS`, `edits`)

| Site | Change |
|---|---|
| `select_timezone` `0x4d6b2c` prologue `(0x3c1c0053, 0x279cd3a4, 0x0399e021)` | `j tz_select; nop`; trampoline resumes at `0x4d6b38` |
| `0x4e65dc` `sltiu v1,v0,0x1b` | `sltiu v1,v0,43`: config_init keeps a saved index below 43 |
| `0x4a246c` `addiu v0,zero,0x1d` | `0x2d`: rows 0..44 |
| `0x4a2604` `sltiu v1,v0,0x1e` | `sltiu v1,v0,46`: the click limit, as stock's `27 + 3` |
| `0x4a25a8` `bal timezone_listitem_layout` | `jal tz_row` |
| `0x4a2248` / `0x4a224c` `jalr strcpy` / `lw a1,0x80(v0)` | `jal tz_label` / `move a1,s4` |
| `0x4a2518` `addiu v0,zero,0x40` | `0x30`: zone rows 48 px tall (the delay slot of the `bne` that skips the header row, so it reaches only zone rows; header `0x4a251c` 0x2e and switch row `0x4a24bc` 0x40 stay) |
| `0x4a22a4` `addiu a1,a1,0x7628` | `0x5f2c`: the label style `srlabel_leftwhite18_style` (`0x745f2c`, stock's 18 px white left hscroll_label, used by ten stock sites) instead of `srlabel_leftwhite21_style` |
| `0x4a225c` / `0x4a2308` `addiu a2,zero,0x14` / `0x11` | `0x0d` / `0x0b`: label y 13 and tick y 11, centred in 48 px |

- `tz_select` reads `time_zone`; for an index below 43 and no `/mnt/mmc/m1plus-off` it calls
  `toolsSetTimeZone(name)` and returns its result; otherwise stock's function runs
  (`stock_timezone_trampoline`). One `access()`, no other I/O or allocation. It runs at boot from
  `config_init` and after a tap in the picker. With the kill switch set, saved indices 27 and up map to
  Shanghai (stock's behaviour for them).
- `tz_row(item, row)` builds the row of zone `ORDER[row - 2]` by calling stock's builder with that
  zone's row number, so the row name, tick and the click decode stay stock's. The rows are therefore
  in west-to-east order (offset, then label) while the saved value stays the index.
- `tz_label(buf, index)` writes the zone's literal label (`GMT+5:30 Kolkata`, at most 31 characters)
  instead of an i18n key; the table has no entry for a literal, so `widget_set_tr_text` shows it as is.
  The stock (translated) labels are not used: they named the old zones. The labels are English in every
  language. The stack copy of the key array is still made and not read.
- The picker's row words and the kill switch: the row, count and label edits are static words, not
  hooks; the kill switch affects only `tz_select`.

## Rows

Zone rows are 48 px tall (stock 64) with 18 px text (stock 21), so a line is less busy and more zones fit.
Label box x 12, w 260, h 21 (y 13) and tick 26 x 26 at x 282 (y 11) keep stock's x, width and height, so the
width, ellipsis and scroll behaviour are unchanged. The page builder gives each row its height in
`list_item_create(..., h)`, and the list lays the items out by their own heights, so scrolling and tap
hit-testing follow. `list_item_style` is a flat colour with a 1 px bottom border (no image), so the
pressed and separator drawing is height independent. Only zone rows change: the auto time switch and
header rows, and every other page, keep their words. Preview: `tools/preview/preview_timezones.py WORKDIR OUT.png`
(stock 64 px beside the build). Device check: scroll, tap and the ticked row at 48 px.

## Limits

- Labels show the standard offset; a zone in daylight saving is not relabelled (q2-pod's
  `ringnav_timezone_row` shows the live `tm_gmtoff`; not ported).
- Like stock, no `tzset` follows `setenv`; `localtime` re-reads `TZ`, `localtime_r` does not.
- A device whose saved index is 27 or more (set by this build) boots on a stock build with Shanghai.
- Rows exist only while auto time is off, as stock.

## Validation

`test/pod/timezones.py` runs the three payload functions in Unicorn for every index and row, checks
the stock and built words, the manifest, the zoneinfo names, the order, and that a changed pinned word
refuses the build. `test/demo_diff.py` and `test/pod/rows.py` allow exactly these words. Untested on
hardware; see [device checks](device-checks.md) (TZ-01).
