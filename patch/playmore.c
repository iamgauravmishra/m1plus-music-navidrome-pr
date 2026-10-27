/* M1+ Pod Now Playing More menu: the stock playmore_dialog (the sheet Now Playing's More button opens: ui/dialog/
 * playmore_dialog.bin, seven list_item rows listitem0..6) as an iOS style bottom sheet with two pages.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * The sheet is PM_PAGE_N rows (4 x 50 = 200 px) high on both pages and sits on the bottom of the screen (y = 480 - 200); the page
 * above it is dimmed by the asset's own dialog highlight (highlight="default(alpha=..)", the AWTK dialog highlighter the window
 * manager sets up when the dialog opens). Page 1 (when it opens): Look up album (listitem4), Look up artist (5), Add to playlist
 * (2) and "More" (pod_more, a row the asset adds, hidden until now; a chevron at its right). A tap on More switches to page 2:
 * a header row "< More" (pod_back, also the asset's; a tap returns to page 1), Playback speed (1), A-B repeat (0) and Delete (6,
 * its label red in the asset). Online search (3) is never shown. A switch only hides one row set and shows the other: the
 * sheet never resizes. A tap above the sheet closes it: that is the stock handler's (pointer y < dialog y), which works
 * unchanged with the new y.
 *
 * One hook, dialog_playmore_dialog_init (0x479cc4): run when the dialog is built (a tap on Now Playing's More button, never
 * at boot or in the main loop). m1pod_playmore_init runs the stock init to completion (it binds every row's handler and the
 * speed / A-B widgets, which keep their stock handlers: we move rows, we do not replace behaviour; it also pins the sheet at
 * y 130) and then, unless the kill switch /mnt/mmc/m1pod-off exists and every widget of the asset is there, arranges page 1
 * and anchors the sheet. Everything fallible (the widget lookups, the handlers, the labels' texts) is done before the first
 * row moves, so any failure leaves the stock seven rows (pod_more and pod_back stay hidden and insensitive in the asset).
 *
 * The stock to-background handler (0x4789f0, bound by the stock init to EVT_WINDOW_TO_BG) moves the dialog back to y 130 when
 * another dialog (the Delete confirm) opens over it; our handler, bound after it, puts the sheet back on the bottom.
 *
 * Hidden rows are visible=false and sensitive=false (a hidden widget would still take touches) and are stacked after the
 * shown ones (widget_restack): the stock list_view layouter re-stacks the visible children in child order at every relayout
 * (docs/modules/home-guard.md "The stock list code under the menu's hand-placed rows"), so the order survives it.
 */
#include "offsets.inc"
#include "stock.h"
#include "i18n.h"
#include "home.h"
#include "common.h"

#define PM_ROWS 9     /* listitem0..6, then pod_more, pod_back */
#define PM_MORE 7
#define PM_BACK 8

/* what each page shows, top to bottom, as indices into pm.row[] */
static const unsigned char pm_page[2][PM_PAGE_N] = {
    {4, 5, 2, PM_MORE},   /* Look up album, Look up artist, Add to playlist, More */
    {PM_BACK, 1, 0, 6},   /* the back header, Playback speed, A-B repeat, Delete */
};

static struct {
    void *dlg, *lv, *sv, *bar;        /* the dialog, its list_view, scroll_view and scroll bar */
    void *row[PM_ROWS];
    int page;                         /* 0: the first page, 1: the More page */
} pm __attribute__((section(".scratch")));

static void pm_show(void *w, int on) {
    widget_set_visible(w, on, 0);
    widget_set_sensitive(w, on);
}

/* The rows as pm.page says: the shown ones at y = position x PM_ROW_H, the others hidden and parked under the sheet; the
 * children stacked in that order; the sheet PM_PAGE_N rows high on the bottom of the screen. */
static void pm_arrange(void) {
    unsigned char used[PM_ROWS];
    unsigned i, k = 0;
    int h = PM_PAGE_N * PM_ROW_H;
    memset(used, 0, sizeof used);
    widget_invalidate_force(pm.dlg, (void *)0);
    for (i = 0; i < PM_ROWS; i++) {
        widget_resize(pm.row[i], PM_SV_W, PM_ROW_H); /* the asset has Go to artist and Delete 60 px high: the layouter keeps a row's own height */
        widget_set_state(pm.row[i], "normal");       /* the row that was tapped is hidden by its own click */
    }
    for (i = 0; i < PM_PAGE_N; i++) {
        void *r = pm.row[pm_page[pm.page][i]];
        used[pm_page[pm.page][i]] = 1;
        widget_move(r, 0, (int)i * PM_ROW_H);
        pm_show(r, 1);
    }
    for (i = 0; i < PM_ROWS; i++) { /* parked under the shown rows: nothing it could shadow if a hit test did look at it */
        if (used[i]) continue;
        widget_move(pm.row[i], 0, h);
        pm_show(pm.row[i], 0);
    }
    for (i = 0; i < PM_PAGE_N; i++) widget_restack(pm.row[pm_page[pm.page][i]], k++);
    for (i = 0; i < PM_ROWS; i++) if (!used[i]) widget_restack(pm.row[i], k++);
    widget_resize(pm.dlg, PM_DIALOG_W, h);
    widget_move(pm.dlg, 0, PM_SCREEN_H - h);
    widget_resize(pm.lv, PM_DIALOG_W, h);
    widget_resize(pm.sv, PM_SV_W, h);
    widget_resize(pm.bar, PM_BAR_W, h);
    widget_set_prop_int(pm.sv, "virtual_h", h);
    widget_set_prop_int(pm.sv, "yoffset", 0);
    widget_invalidate_force(pm.dlg, (void *)0);
}

static int pm_on_more(void *ctx, void *e) {
    (void)e;
    if (!pm.dlg || ctx != pm.dlg) return RET_OK;
    pm.page = 1;
    pm_arrange();
    return RET_OK;
}

static int pm_on_back(void *ctx, void *e) {
    (void)e;
    if (!pm.dlg || ctx != pm.dlg) return RET_OK;
    pm.page = 0;
    pm_arrange();
    return RET_OK;
}

/* Another dialog opened over the sheet: the stock handler (bound first) has just moved it to y 130. */
static int pm_on_bg(void *ctx, void *e) {
    (void)e;
    if (!pm.dlg || ctx != pm.dlg) return RET_OK;
    widget_move(ctx, 0, PM_SCREEN_H - PM_PAGE_N * PM_ROW_H);
    return RET_OK;
}

static int pm_on_destroy(void *ctx, void *e) {
    (void)e;
    if (pm.dlg && ctx == pm.dlg) memset(&pm, 0, sizeof pm); /* an earlier dialog's end: the new one keeps its state */
    return RET_OK;
}

static void pm_start(void *dlg) {
    static const char *const names[PM_ROWS] = {"listitem0", "listitem1", "listitem2", "listitem3", "listitem4", "listitem5", "listitem6", "pod_more", "pod_back"};
    void *more_label, *back_label, *speed_label, *note_label;
    unsigned i;
    if (access(KILL_SD, F_OK) == 0) return;
    if (pm.dlg) memset(&pm, 0, sizeof pm); /* an earlier dialog that never said it was gone */
    pm.dlg = dlg;
    pm.lv = widget_lookup(dlg, "playmore_listview", 1);
    pm.sv = widget_lookup(dlg, "playmore_scrollview", 1);
    pm.bar = widget_lookup(dlg, "scroll_bar_m", 1);
    more_label = widget_lookup(dlg, "pod_more_label", 1);
    back_label = widget_lookup(dlg, "pod_back_label", 1);
    speed_label = widget_lookup(dlg, "scrlabel1", 1);
    note_label = widget_lookup(dlg, "label1_msg", 1);
    if (!pm.lv || !pm.sv || !pm.bar || !more_label || !back_label || !speed_label || !note_label) goto fail;
    for (i = 0; i < PM_ROWS; i++) { /* exactly the asset: nine rows in the scroll_view */
        pm.row[i] = widget_lookup(dlg, names[i], 1);
        if (!pm.row[i] || *(void **)((char *)pm.row[i] + W_PARENT) != pm.sv) goto fail;
    }
    if (widget_count_children(pm.sv) != PM_ROWS) goto fail;
    if (widget_set_tr_text(more_label, "More") != RET_OK) goto fail;
    if (widget_set_tr_text(back_label, "More") != RET_OK) goto fail;
    if (widget_set_tr_text(speed_label, "Speed") != RET_OK) goto fail;   /* the stock "Multiple Speed" is wider than the room before the badges */
    if (widget_set_tr_text(note_label, "Files below 48 kHz only") != RET_OK) goto fail;
    if (!widget_on(dlg, EVT_DESTROY, pm_on_destroy, dlg)) goto fail;
    if (!widget_on(dlg, EVT_WINDOW_TO_BG, pm_on_bg, dlg)) goto fail;
    if (!widget_on(pm.row[PM_MORE], EVT_CLICK, pm_on_more, dlg)) goto fail;
    if (!widget_on(pm.row[PM_BACK], EVT_CLICK, pm_on_back, dlg)) goto fail;
    pm.page = 0;
    pm_arrange();
    return;
fail:
    memset(&pm, 0, sizeof pm); /* the stock rows are as the stock init left them; a handler that was bound finds no dialog of ours */
}

/* The hook (tools/pod.py PLAYMORE_INIT): stock first, then ours. */
int m1pod_playmore_init(void *dlg, void *ctx) {
    int ret = stock_playmore_init_trampoline(dlg, ctx);
    if (ret == RET_OK && dlg) pm_start(dlg);
    return ret;
}
