/* M1 Pod Artists: the stock Local Music artists as an M1 Pod list; a tap opens Cover Flow on that
 * artist's albums.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * The artist-to-Cover-Flow flow follows q2-pod (Copyright (c) 2026 Diamond Bond, MIT,
 * https://github.com/DiamondBond/q2-pod; see NOTICE): its Artists list hands an artist's albums to
 * coverflow_artist. On the M1 Plus the list is our own page instead of a hooked stock one.
 *
 * The list is exactly the stock Artists list: loadLocalClassList(0xf004), which runs
 * GetAllAlbumArtist or getAllArtist as the stock Artists page's own artist/album-artist switch
 * (the artist_type global) says, each row named by REC_TITLE as the stock rows are. The rows are
 * built as stock builds its scrolling rows (systemset_sysset_page_init @0x4adb7c): list_item themed
 * "list_item_style", an hscroll_label themed "srlabel_leftwhite21_style", the "right_arrow" image,
 * inside the asset's stock list_view > scroll_view (+ scroll_bar_m).
 *
 * No stock function is hooked. The page is opened from the M1 Pod menu's Artists row and
 * everything here runs from its own widgets; nothing of it outlives the window.
 */
#include "offsets.inc"
#include "stock.h"

extern int coverflow_artist(void *artists, unsigned index); /* patch/coverflow.c */

#define ROW_H 52          /* tools/pod_ui.py ROW_H: the menu's rows */
#define ROW_TEXT_X 24
#define CHEVRON_W 44      /* the right_arrow image's column, as the menu rows' */
#define MAX_ARTISTS 2000  /* one list_item (+ label, image) each: bounded */

static struct {
    void *win, *view, *list, *status;
    void *artists; /* our copy of the stock artist rows */
    unsigned count;
} ar __attribute__((section(".scratch")));

/* Hidden and out of the hit test together (this AWTK's widget_find_target ignores visible). */
static void ar_show(void *w, int on) {
    if (!w) return;
    widget_set_visible(w, on, 0);
    widget_set_sensitive(w, on);
}

static const char *ar_name(void *r) {
    const char *s = r ? *(const char **)((char *)r + REC_TITLE) : (const char *)0;
    return s ? s : "";
}

static int ar_on_artist(void *ctx, void *e) {
    unsigned i = (unsigned)(long)ctx;
    (void)e;
    if (ar.artists && i < ar.count) coverflow_artist(ar.artists, i);
    return RET_OK;
}

static int ar_on_back(void *ctx, void *e) {
    (void)ctx; (void)e;
    navigator_back();
    return RET_OK;
}

static int ar_on_player(void *ctx, void *e) {
    (void)ctx; (void)e;
    on_backtoplayer_onclick((void *)0, (void *)0);
    return RET_OK;
}

static int ar_on_destroy(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (ar.artists) deque_destroy(ar.artists);
    memset(&ar, 0, sizeof ar);
    return RET_OK;
}

static void ar_bind(const char *name, int (*fn)(void *, void *)) {
    void *w = widget_lookup(ar.win, name, 1);
    if (w) widget_on(w, EVT_CLICK, fn, (void *)0);
}

/* One row per artist, in the stock order, each a stock-built list row (see the header). */
static void ar_build_rows(void) {
    int w = widget_get_prop_int(ar.view, "w", SCREEN_W);
    unsigned i;
    widget_set_prop_int(ar.view, "virtual_h", (int)ar.count * ROW_H);
    for (i = 0; i < ar.count; ++i) {
        void *row = list_item_create(ar.view, 0, (int)i * ROW_H, w, ROW_H), *label, *img;
        if (!row) break;
        widget_use_style(row, "list_item_style");
        label = hscroll_label_create(row, ROW_TEXT_X, 0, w - ROW_TEXT_X - CHEVRON_W, ROW_H);
        if (label) {
            widget_use_style(label, "srlabel_leftwhite21_style");
            hscroll_label_set_only_parent_focus(label, 1);
            hscroll_label_set_ellipses(label, 1);
            widget_set_text_utf8(label, ar_name(deque_at(ar.artists, i)));
        }
        img = image_create(row, w - CHEVRON_W, 0, CHEVRON_W - 4, ROW_H);
        if (img) {
            image_base_set_image(img, "right_arrow");
            widget_set_prop_str(img, "draw_type", "icon"); /* the string form the assets use */
        }
        widget_on(row, EVT_CLICK, ar_on_artist, (void *)(long)i);
    }
}

/* The M1 Pod menu's Artists row. 0 once the page is up, -1 if it could not open. */
int artists_open(void) {
    void *list;
    if (ar.win) return -1;
    memset(&ar, 0, sizeof ar);
    ar.win = window_open("m1pod_artists");
    if (!ar.win) return -1;
    widget_on(ar.win, EVT_DESTROY, ar_on_destroy, (void *)0);
    ar_bind("btn_return", ar_on_back);
    ar_bind("btn_backtoplayer", ar_on_player);
    ar.list = widget_lookup(ar.win, "pod_listview", 1);
    ar.view = widget_lookup(ar.win, "pod_scrollview", 1);
    ar.status = widget_lookup(ar.win, "label_status", 1);
    if (!ar.list || !ar.view || !ar.status) {
        navigator_back(); /* an asset that is not ours */
        return -1;
    }
    ar_show(ar.status, 0);
    /* The stock Artists query, copied so Cover Flow's own queries cannot pull it away. */
    list = loadLocalClassList(CLASS_ARTISTS) > 0 ? *(void **)PDEQ_SHOWLIST : (void *)0;
    if (list && deque_size(list) && (ar.artists = _create_deque("stSongInfo"))) {
        deque_init(ar.artists);
        deque_assign(ar.artists, list);
        ar.count = deque_size(ar.artists);
        if (ar.count > MAX_ARTISTS) ar.count = MAX_ARTISTS;
    }
    if (!ar.count) {
        ar_show(ar.list, 0);
        ar_show(ar.status, 1);
        widget_set_text_utf8(ar.status, "Update Local Music first");
        return 0;
    }
    ar_build_rows();
    return 0;
}
