/* Battery Percentage (patch/battery.c, docs/modules/battery.md "The percentage"): constants the payload and test/pod/battery.py share.
 * The test parses the #defines in this file, so a change cannot leave the mocks behind.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#define BP_FILE \
    "/mnt/data/m1plus-battpct" /* "1" = on, anything else or missing = off (Settings > Home Screen > Status Bar) */
#define BP_TMP "/mnt/data/m1plus-battpct.tmp"
#define BP_GAUGE \
    "/sys/class/power_supply/battery/capacity" /* the AXP2101 fuel gauge: an integer 0..100 and a newline */
#define BP_LABEL "pod_pct" /* the hidden label tools/pod_ui.py adds to the system bar's right group */
#define BP_LABEL_DD "pod_pct_dd" /* its twin in the pull-down's own bar (view_sysbar of dropdown_dialog.bin) */

/* widget_t fields the label's fit reads and writes (pinned by BATTERY_PINS in tools/pod.py against widget_resize and widget_set_visible) */
#define BP_W_W 8 /* widget->w */
#define BP_W_H 0xc /* widget->h */
#define BP_W_PARENT 0x44 /* widget->parent */
