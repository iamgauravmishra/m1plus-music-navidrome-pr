/* M1+ Music time zones: the saved index -> TZ mapping and the picker's rows (docs/modules/timezones.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE). After q2-pod's ringnav_timezone / ringnav_timezone_row (tools/build.py TIMEZONES).
 *
 * Stock keeps the saved zone as an index in [SYSSET] TIMEZONE (global time_zone 0xa05ab4) and maps it to a TZ name in select_timezone (0x4d6b2c), which config_init calls at
 * boot (0x4e65ec) and the picker's click handler calls after a tap. Three entry points, all pinned (tools/timezones.py):
 *  - tz_select replaces select_timezone's prologue (`j tz_select`): setenv("TZ") from our table for any saved index below TZ_COUNT; with the kill switch /mnt/mmc/m1plus-off, or any
 *    larger index, stock's own function runs (through the trampoline).
 *  - tz_row replaces the page builder's `bal timezone_listitem_layout`: row r of the list shows the zone ORDER[r - 2] (west to east), built by stock's row builder with that zone's
 *    row number, so the row's name, tick and the click's index decode stay stock's.
 *  - tz_label replaces the row builder's `strcpy(buf, keys[index])`: the row's text is our literal label. widget_set_tr_text finds no translation for it and shows it as is.
 * The kill switch is read once per call of tz_select (boot and a tap): one access().
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"

extern int stock_timezone_trampoline(void);

static const char *const tz_names[] = TIMEZONE_NAMES;
static const char *const tz_labels[] = TIMEZONE_LABELS;
static const unsigned char tz_order[] = TIMEZONE_ORDER;
#define TZ_COUNT (sizeof tz_names / sizeof *tz_names)

/* select_timezone(): no arguments, reads time_zone. */
int tz_select(void) {
    unsigned n = *(volatile unsigned *)TIME_ZONE;
    if (n >= TZ_COUNT || access(KILL_SD, F_OK) == 0) return stock_timezone_trampoline();
    return toolsSetTimeZone(tz_names[n]);
}

/* The page builder's call: row 2 + p is the p-th row down; stock builds the row of zone tz_order[p]. */
void *tz_row(void *item, int row) {
    unsigned p = (unsigned)row - 2;
    return timezone_listitem_layout(item, p < TZ_COUNT ? (int)tz_order[p] + 2 : row);
}

/* The row builder's strcpy(buf, key): buf is its 0x80 byte label buffer, index the zone (row - 2). */
void tz_label(char *buf, unsigned index) {
    const char *s = index < TZ_COUNT ? tz_labels[index] : "";
    unsigned i = 0;
    while (s[i] && i < 0x7f) buf[i] = s[i], i++;
    buf[i] = 0;
}
