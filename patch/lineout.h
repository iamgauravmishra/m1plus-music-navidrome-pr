/* Line Out pill (patch/lineout.c, docs/modules/lineout.md): constants the payload and test/pod/lineout.py share.
 * The test parses the #defines in this file, so a change cannot leave the mocks behind.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#define LO_PILL \
    "pod_lo" /* the hidden amber pill image tools/statusbar.py puts after label_volume in view_bar_left (both bar copies) */
#define LO_W_PARENT 0x44 /* widget->parent (pinned by BATTERY_PINS against widget_set_visible) */
