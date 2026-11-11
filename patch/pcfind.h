/* Search inside one show (docs/modules/podcasts.md "Search inside a show"): the entry points of patch/pcfind.c and the page's geometry, which tools/pod_ui.py build_pcfind_page repeats
 * (test/pod/pcfind.py compares them).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

/* The Show page's search button: the page m1plus_pcfind over the Show page, our keyboard embedded, the show's episodes matched by title as the field changes. 0 once it is up; -1 when it could not
 * open (a Search page exists, no memory, the asset is not ours): the button does nothing. */
int pcfind_open(void);
/* The same page again with the text and the scroll the last one had (Back from the episode page that a result opened); the keyboard is down. -1 as pcfind_open, or when there is nothing kept. */
int pcfind_reopen(void);
/* The kept text and scroll are dropped (the episode page was left some other way, the show was left). */
void pcfind_forget(void);

#define PF_FIELD_X \
    12 /* the field, its magnifier, text and clear button are the Search page's (patch/search.h SE_FIELD_*, SE_TEXT_*) */
/* the results list: under the field, to the window's bottom (the keyboard covers its lower part) */
#define PF_LIST_Y 52
#define PF_LIST_H 398
#define PF_ROW_H 60 /* a result: the title (one line) and the grey line (the date, Downloaded) */
#define PF_TITLE_Y 7
#define PF_SUB_Y 33
#define PF_TEXT_X 16
#define PF_TEXT_END 304
#define PF_SEP_END 310 /* the hairline from PF_TEXT_X to here, under every row */
#define PF_BOTTOM 12 /* air under the last row (the pad's height instead while the keyboard is up) */
#define PF_TILES 16 /* the rows' texts kept: the rows in view, two beyond and the history */
#define PF_QMAX 64
