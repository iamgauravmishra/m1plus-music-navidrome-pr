/* M1+ Music Presets page (patch/peqlib.c, docs/modules/peq.md "Presets page"): Download from AutoEq, then the card's preset files,
 * the AutoEq ones first and the others under On Card.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#include "peq.h"

/* patch/peq_ui.c: the .txt presets of PEQ_DIR, sorted by name, at most max of them into names (the first ones); *total (when not null)
 * counts every one. 0 while the card is out. */
int peq_list(char (*names)[PEQ_NAME], int max, int *total);

/* patch/peq_ui.c: Delete Preset's delete (after its confirm): the file is unlinked, and when it was the preset that plays the record
 * points at the 10-Band EQ and stock's Equalizer goes off. 0 when the file cannot be removed. */
int peq_delete(const char *file);

/* patch/m1plus.c: opens the Presets page from the Equalizer page's link (1 once it is opening). */
int peqlib_open(void);

/* patch/m1plus.c open_page: the page's window is up. Fills it from the card; a page that is not our asset is left as it is. */
void peqlib_opened(void *win);
