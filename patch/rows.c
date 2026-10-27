/* M1+ Pod rows: the stock library rows (Songs, Folders, Artists/Genres/Composers, Albums, album
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
 * rows_track_icon (below) hides the repeated format disc of the track rows (docs/architecture.md section 6);
 * rows_track_number (below) shows the album detail track number in a grey label of its own.
 * Anything unexpected (no row, no text, too many children) is left to the stock layout alone, which
 * always runs.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "common.h"


typedef int (*layout_fn)(void *, void *);

#define I(w, off) (*(int *)((char *)(w) + (off)))
#define B(w, off) (*(unsigned char *)((char *)(w) + (off)))
#define P(w, off) (*(void **)((char *)(w) + (off)))

static unsigned row_vtable[LAYOUT_VTABLE_WORDS] __attribute__((section(".scratch")));

/* The first hscroll_label in the row, or in one of its children (then *text is that child). */
static void *find_title(void *row, unsigned count, void **text) {
    unsigned i, j, n;
    for (i = 0; i < count; i++) {
        void *child = widget_get_child(row, i);
        if (!child) continue;
        if (pod_is_type(child, "hscroll_label")) { *text = child; return child; }
        n = widget_count_children(child);
        for (j = 0; j < n && j < ROW_MAX_CHILDREN; j++) {
            void *label = widget_get_child(child, j);
            if (pod_is_type(label, "hscroll_label")) { *text = child; return label; }
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
                if (pod_is_type(line, "hscroll_label")) {
                    fit(line, (width < 0 ? 0 : width) - I(line, W_X));
                    hscroll_label_set_only_focus(line, 1);
                } else if (pod_is_type(line, "view")) {
                    fit(line, (width < 0 ? 0 : width) - I(line, W_X));
                }
            }
        }
    }
    list_item = pod_is_type(row, "list_item") && I(row, W_H) > 2 * ROW_SEPARATOR;
    if (list_item) { h = I(row, W_H); I(row, W_H) = h - ROW_SEPARATOR; }
    ret = stock(layout, row);
    if (list_item) I(row, W_H) = h;
    if (margin == 0) {   /* x=0 rows: the cover (the first visible child) gets its inset */
        for (i = 0; i < count; i++) {
            void *child = widget_get_child(row, i);
            if (!child || !widget_get_visible(child)) continue;
            if (pod_is_type(child, "image") && I(child, W_W) == ROW_ART && I(child, W_X) == 0)
                widget_move(child, ROW_ART_INSET, I(child, W_Y));
            break;
        }
    }
    if (title && text != title) {   /* a line's own view (laid out by now): its last label to its end */
        n = widget_count_children(text);
        for (j = 0; j < n && j < ROW_MAX_CHILDREN; j++) {
            void *view = widget_get_child(text, j), *last = (void *)0;
            unsigned k, m;
            if (!pod_is_type(view, "view")) continue;
            m = widget_count_children(view);
            for (k = 0; k < m && k < ROW_MAX_CHILDREN; k++) {
                void *c = widget_get_child(view, k);
                if (pod_is_type(c, "hscroll_label")) last = c;
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
    if (access(KILL_SD, F_OK) == 0) return ret;   /* kill switch: the stock layout */
    if (!row_vtable[0]) {
        memcpy(row_vtable, (const void *)DEFAULT_LAYOUT_VTABLE, sizeof row_vtable);
        row_vtable[LAYOUT_SLOT] = (unsigned)compact_row_layout;
    }
    P(layout, LAYOUT_VTABLE) = row_vtable;
    return ret;
}

/* Replaces image_base_set_image(img_icon, name) in the Songs-family rebind (0x5284e0: Songs, Hi-Res,
 * Favourites, Recent, Most played, Recently added, a playlist's songs) and in the queue's rebind
 * (0x53935c) and in the Artists / Genres / Composers rebind (0x5367b0, localclass_on_prepare_row, whose names are
 * icon_artist, icon_genre, icon_composer: one placeholder per page, hidden like the format discs; its playing
 * marker goes before the row's chevron button), patch/rows.json icon_calls. The stock call runs first, so the name is set as before.
 * Those rows show the track's file-format disc (icon_flac, icon_mp3 ...: one picture for every row
 * of a library in one format) or, on the playing row, the red icon_playing disc. A track row shows
 * no disc at the left: the placeholder is hidden (visible and sensitive off), and the row's
 * layout, which skips a hidden child, gives the title its place, so every title starts at the same
 * margin. The playing row's placeholder instead becomes its marker (np_row_playing, a small wave)
 * moved last in the row's flow: the layout narrows the title by its width, the wave sits at the
 * right end. Rebinding a recycled row sets either state again. Rows that name a place, not a
 * track (folder, playlist, card, USB), keep their icon. Kill switch: stock behaviour. */
static int is_place_icon(const char *name) {
    return strcmp(name, "icon_folder") == 0 || strcmp(name, "icon_playlist") == 0 ||
           strcmp(name, "icon_tf") == 0 || strcmp(name, "icon_otg") == 0;
}

/* Replaces the text setter call (label, the text "N title") in the album detail track row's label builder
 * (0x524b50, called once per row by albumdeinfo_listitem_layout 0x526394; patch/rows.json text_calls).
 * Stock formats "%d %s" (track position + 1, then the title) into one hscroll_label. Apple Music style, the
 * number is secondary: the title label gets the text after the number, and the row gets one small
 * right-aligned label (ROW_NUM_STYLE: #AAAAAA, ROW_NUM_W wide, insensitive) for the number, restacked just
 * before the title, so the flow is [check box] number title: the row fit narrows the title by the
 * number's width + spacing, the ellipsis and the playing row's gold title stay the title's. A row that
 * already has the number label (a rebuilt or recycled row) reuses it. Anything unexpected (no leading
 * number and a space, the kill switch, no label) sets the whole text as stock does. */
__attribute__((used, retain)) void rows_track_number(void *title, const char *text) {
    const char *p = text;
    char digits[8];
    void *row, *num = (void *)0;
    unsigned n, i, at = 0, len;
    int width;
    if (!title || !text || access(KILL_SD, F_OK) == 0) { widget_set_text_utf8(title, text); return; }
    while (*p >= '0' && *p <= '9') p++;
    len = (unsigned)(p - text);
    row = P(title, W_PARENT);
    if (!len || len > 3 || *p != ' ' || !row) { widget_set_text_utf8(title, text); return; }
    n = widget_count_children(row);
    for (i = 0; i < n && i < ROW_MAX_CHILDREN; i++) {
        void *c = widget_get_child(row, i);
        if (c == title) at = i;
        else if (pod_is_type(c, "label")) num = c;
    }
    width = len > 2 ? ROW_NUM_W3 : ROW_NUM_W;
    if (!num) {
        num = label_create(row, 0, 0, width, I(title, W_H));
        if (!num) { widget_set_text_utf8(title, text); return; }
        widget_use_style(num, ROW_NUM_STYLE);
        widget_set_sensitive(num, 0);
        widget_restack(num, at);   /* last child now: before the title */
    } else {
        widget_resize(num, width, I(num, W_H));   /* a recycled row: this number's column (no-op when unchanged) */
    }
    memcpy(digits, text, len);
    digits[len] = 0;
    widget_set_text_utf8(num, digits);
    widget_set_text_utf8(title, p + 1);
}

__attribute__((used, retain)) void rows_track_icon(void *img, const char *name) {
    int show, playing, moved = 0;
    void *row;
    unsigned n, end;
    image_base_set_image(img, name);
    if (!img || !name || access(KILL_SD, F_OK) == 0) return;
    playing = strcmp(name, "icon_playing") == 0;
    show = playing || is_place_icon(name);
    row = P(img, W_PARENT);
    n = row ? widget_count_children(row) : 0;
    /* where the marker sits: last in the flow, but before a chevron button the row ends with (Artists, Genres, Composers) */
    end = n > 2 && pod_is_type(widget_get_child(row, n - 1), "button") ? n - 2 : n - 1;
    if (playing && n > 1) {
        /* The playing row's marker: not the red disc at the left but a small wave at the right end, so every title starts
         * at the same margin. The same widget, last in the row's flow (after the text, which the layout narrows by its
         * width), showing a 40 x 20 image whose wave sits at its right end, drawn centred. */
        image_base_set_image(img, ROW_MARKER_IMAGE);
        image_set_draw_type(img, IMAGE_DRAW_CENTER);
        if (widget_get_child(row, end) != img) { widget_restack(img, end); moved = 1; }
    } else if (!show && n > 1 && widget_get_child(row, end) == img) {
        widget_restack(img, end - 1);   /* back before the text (the flow is: check box, icon, text) */
        moved = 1;
    }
    if (!widget_get_visible(img) == !show) {   /* already as wanted: no relayout (unless the flow changed) */
        if (moved) widget_set_need_relayout_children(row);
        return;
    }
    widget_set_visible(img, show, 0);
    widget_set_sensitive(img, show);
}
