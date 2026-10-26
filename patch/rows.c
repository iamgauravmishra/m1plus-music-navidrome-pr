/* M1 Pod rows: the stock library rows (Songs, Folders, Artists/Genres/Composers, Albums, album
 * tracks, Playlists, Search) fitted to iPod-style rows.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * compact_set_row_layout / compact_row_layout are q2-pod's (patch/navigation.c, Copyright (c) 2026
 * Diamond Bond, MIT, https://github.com/DiamondBond/q2-pod; see NOTICE), ported to this demo's
 * ABI (patch/offsets.inc) and rows (docs/architecture.md).
 *
 * How it is reached: tools/pod.py rewrites each ordinary row constructor's own call
 * `jalr $t9` (widget_set_children_layout(row, "default(...)")) into `jal compact_set_row_layout`
 * (patch/rows.json row_layout_calls). Those constructors run only while a library page builds its
 * rows (page init, its table's create-row callback, its scroll and return handlers), never on the
 * boot path; this is a call-site patch, not a hook: no stock prologue changes and the stock
 * function is still what runs first.
 *
 * compact_set_row_layout calls the stock widget_set_children_layout, then (unless the kill switch
 * is present, the layouter is not the stock default one, or its vtable is not the one pinned)
 * points the row's layouter at a copy of the default vtable whose layout slot is
 * compact_row_layout. That runs whenever AWTK lays the row out; before and after the stock
 * default layout it:
 *   - gives the row's text (the first hscroll_label child, or the first child holding one) the row
 *     width minus the margins (the left one, and at least ROW_RIGHT on the right) and every other
 *     visible child's width + spacing, and stretches the text container's lines to it;
 *   - makes the row's labels scroll only while focused (stock scrolled every long title at once);
 *   - lays list_item rows out ROW_SEPARATOR px shorter, so their children sit on the visible body
 *     above list_item_style's separator (a direct height write around the stock call: resizing the
 *     children afterwards would make every layout pass change sizes and relayout the window again);
 *   - on x=0 rows (Albums, Search albums) moves the ROW_ART cover to ROW_ART_INSET;
 *   - inside the second line's own view (Songs: view_artist) stretches its label to the view's end.
 * Anything unexpected (no row, no text, too many children) is left to the stock layout alone, which
 * always runs.
 */
#include "offsets.inc"
#include "stock.h"

#define KILL_FILE "/mnt/mmc/m1pod-off"
#define F_OK 0

typedef int (*layout_fn)(void *, void *);

#define I(w, off) (*(int *)((char *)(w) + (off)))
#define B(w, off) (*(unsigned char *)((char *)(w) + (off)))
#define P(w, off) (*(void **)((char *)(w) + (off)))

static unsigned row_vtable[LAYOUT_VTABLE_WORDS] __attribute__((section(".scratch")));

static int is_type(void *w, const char *type) {
    const char *t = w ? widget_get_type(w) : (const char *)0;
    return t && strcmp(t, type) == 0;
}

/* The first hscroll_label in the row, or in one of its children (then *text is that child). */
static void *find_title(void *row, unsigned count, void **text) {
    unsigned i, j, n;
    for (i = 0; i < count; i++) {
        void *child = widget_get_child(row, i);
        if (!child) continue;
        if (is_type(child, "hscroll_label")) { *text = child; return child; }
        n = widget_count_children(child);
        for (j = 0; j < n && j < ROW_MAX_CHILDREN; j++) {
            void *label = widget_get_child(child, j);
            if (is_type(label, "hscroll_label")) { *text = child; return label; }
        }
    }
    return (void *)0;
}

static void fit(void *w, int width) {
    if (width < 0) width = 0;
    widget_resize(w, width, I(w, W_H));
}

static int compact_row_layout(void *layout, void *row) {
    layout_fn stock = (layout_fn)DEFAULT_LAYOUT_FN;
    void *text = (void *)0, *title;
    unsigned count, i, j, n;
    int margin, spacing, width, ret, h = 0, list_item;
    if (!layout || !row) return stock(layout, row);
    count = widget_count_children(row);
    if (!count || count > ROW_MAX_CHILDREN) return stock(layout, row);
    margin = B(layout, LAYOUT_X_MARGIN);
    spacing = B(layout, LAYOUT_SPACING);
    title = find_title(row, count, &text);
    if (title && widget_get_visible(text)) {
        width = I(row, W_W) - margin - (margin > ROW_RIGHT ? margin : ROW_RIGHT);
        for (i = 0; i < count; i++) {
            void *child = widget_get_child(row, i);
            if (child && child != text && widget_get_visible(child)) width -= I(child, W_W) + spacing;
        }
        fit(text, width);
        hscroll_label_set_only_focus(title, 1);
        if (text != title) {   /* a text container: its lines (labels and views) end where it does */
            n = widget_count_children(text);
            for (j = 0; j < n && j < ROW_MAX_CHILDREN; j++) {
                void *line = widget_get_child(text, j);
                if (is_type(line, "hscroll_label")) {
                    fit(line, (width < 0 ? 0 : width) - I(line, W_X));
                    hscroll_label_set_only_focus(line, 1);
                } else if (is_type(line, "view")) {
                    fit(line, (width < 0 ? 0 : width) - I(line, W_X));
                }
            }
        }
    }
    list_item = is_type(row, "list_item") && I(row, W_H) > 2 * ROW_SEPARATOR;
    if (list_item) { h = I(row, W_H); I(row, W_H) = h - ROW_SEPARATOR; }
    ret = stock(layout, row);
    if (list_item) I(row, W_H) = h;
    if (margin == 0) {   /* x=0 rows: the cover (the first visible child) gets its inset */
        for (i = 0; i < count; i++) {
            void *child = widget_get_child(row, i);
            if (!child || !widget_get_visible(child)) continue;
            if (is_type(child, "image") && I(child, W_W) == ROW_ART && I(child, W_X) == 0)
                widget_move(child, ROW_ART_INSET, I(child, W_Y));
            break;
        }
    }
    if (title && text != title) {   /* a line's own view (laid out by now): its last label to its end */
        n = widget_count_children(text);
        for (j = 0; j < n && j < ROW_MAX_CHILDREN; j++) {
            void *view = widget_get_child(text, j), *last = (void *)0;
            unsigned k, m;
            if (!is_type(view, "view")) continue;
            m = widget_count_children(view);
            for (k = 0; k < m && k < ROW_MAX_CHILDREN; k++) {
                void *c = widget_get_child(view, k);
                if (is_type(c, "hscroll_label")) last = c;
            }
            if (last) {
                fit(last, I(view, W_W) - I(last, W_X));
                hscroll_label_set_only_focus(last, 1);
            }
        }
    }
    return ret;
}

/* Replaces the row constructors' own widget_set_children_layout call (patch/rows.json). */
int compact_set_row_layout(void *row, const char *params) {
    int ret = widget_set_children_layout(row, params);
    void *layout;
    if (ret || !row) return ret;
    layout = P(row, W_CHILDREN_LAYOUT);
    if (!layout || P(layout, LAYOUT_VTABLE) != (void *)DEFAULT_LAYOUT_VTABLE) return ret;
    if (((const unsigned *)DEFAULT_LAYOUT_VTABLE)[LAYOUT_SLOT] != DEFAULT_LAYOUT_FN) return ret;
    if (access(KILL_FILE, F_OK) == 0) return ret;   /* kill switch: the stock layout */
    if (!row_vtable[0]) {
        memcpy(row_vtable, (const void *)DEFAULT_LAYOUT_VTABLE, sizeof row_vtable);
        row_vtable[LAYOUT_SLOT] = (unsigned)compact_row_layout;
    }
    P(layout, LAYOUT_VTABLE) = row_vtable;
    return ret;
}
