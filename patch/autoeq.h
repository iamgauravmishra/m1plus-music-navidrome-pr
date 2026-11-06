/* M1+ Music AutoEq download page (patch/autoeq.c, docs/modules/peq.md "AutoEq download").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

/* The Equalizer page's "Download from AutoEq": its own search window (Radio's search top: the glass Back, the field, our keyboard embedded) over the AutoEq index on the card, and a download of a result's ParametricEQ.txt into
 * the card's EQ folder. 0 once the page is up; -1 when a Search page or another keyboard exists or the window will not open (nothing happens then). */
int autoeq_open(void);

/* patch/peq_ui.c: the preset file of the card's EQ folder, selected as a tap on its row does (parsed, the record saved, the player told). 1 when it plays now; else the message box said why. */
int peq_select(const char *file);
