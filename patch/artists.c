/* M1+ Pod Artists: the stock Local Music artists as an M1+ Pod list; a tap opens Cover Flow on that
 * artist's albums.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * The artist-to-Cover-Flow flow follows q2-pod (Copyright (c) 2026 Diamond Bond, MIT,
 * https://github.com/DiamondBond/q2-pod; see NOTICE): its Artists list hands an artist's albums to
 * coverflow_artist. On the M1 Plus the list is our own page instead of a hooked stock one.
 *
 * The list is the stock Artists list, sorted as the album Artist order is (ar_sort below):
 * loadLocalClassList(0xf004), which runs
 * GetAllAlbumArtist or getAllArtist as the stock Artists page's own artist/album-artist switch
 * (the artist_type global) says, each row named by REC_TITLE as the stock rows are. The rows are
 * built as stock builds its scrolling rows (systemset_sysset_page_init @0x4adb7c): list_item themed
 * "list_item_style", an hscroll_label themed "srlabel_leftwhite21_style", the "right_arrow" image,
 * inside the asset's stock list_view > scroll_view (+ scroll_bar_m).
 *
 * A navbar button (the Albums toggle's slot, NAV_VIEW_X) switches Artist and Album Artist: it makes the
 * same change the stock Artists page's own switch handler does (@0x535770): artist_type flipped,
 * [PLAYSET] ARTISTTYPE saved with write_int_config, and the stock page's reload flag (0xa06d20) raised so
 * a later stock Artists page rebuilds; the stock handler's toast and style swap are its own page's. The
 * title reads "Artists" or "Album Artists" and the button shows the other mode's glyph, the one a tap
 * switches to. The list is then queried again. Everything stock reads artist_type for (this list, an
 * artist's albums in Cover Flow and the album page) follows. Without the button or the title the page
 * still lists in the current mode.
 *
 * No stock function is hooked. The page is opened from the M1+ Pod menu's Artists row and
 * everything here runs from its own widgets; nothing of it outlives the window.
 */
#include "offsets.inc"
#include "stock.h"
#include "covercache.h"
#include "common.h"

extern int coverflow_artist(void *artists, unsigned index); /* patch/coverflow.c */

#define ROW_H 52          /* tools/pod_ui.py ROW_H: the menu's rows */
#define ROW_TEXT_X 24
#define CHEVRON_W 44      /* the right_arrow image's column, as the menu rows' */
#define MAX_ARTISTS 2000  /* one list_item (+ label, image) each: bounded */

static struct {
    void *win, *view, *list, *status;
    void *title, *toggle; /* label_title and btn_artisttype; either may be missing */
    void *artists; /* our copy of the stock artist rows */
    unsigned *order;  /* stock row at each display position; NULL = stock order */
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

/* The stock row shown at display position i. */
static unsigned ar_stock(unsigned i) { return ar.order ? ar.order[i] : i; }

static int ar_on_artist(void *ctx, void *e) {
    unsigned i = (unsigned)(long)ctx;
    (void)e;
    if (ar.artists && i < ar.count) coverflow_artist(ar.artists, ar_stock(i));
    return RET_OK;
}

/* The display order. Names are compared as the album Artist order does (cc_name_cmp: ASCII case aside, a leading
 * "The " dropped; ties keep the stock order). Only a row whose name starts with an ASCII byte takes part: a name
 * in another script (CJK, Cyrillic, ...) and the "Unknown Artist" row (id -1) stay exactly where stock put them, so
 * stock's own placement of those groups (and of their order among themselves) is untouched, wherever it puts them.
 * The runs of consecutive sortable rows between those fixed ones are sorted, each on its own. The stock rows are
 * never reordered: order[] is the stock row number at each position, NULL (stock order) when there is no memory. */
static void **ar_rec __attribute__((section(".scratch")));

static int ar_sortable(void *r) { return *(int *)((char *)r + REC_ID) != -1 && (unsigned char)ar_name(r)[0] < 0x80; }

static int ar_cmp(unsigned a, unsigned b) {
    int d = cc_name_cmp(ar_name(ar_rec[a]), ar_name(ar_rec[b]));
    return d ? d : a < b ? -1 : a > b;
}

static void ar_sort(void) {
    unsigned i, s;
    ar.order = (unsigned *)0;
    if (ar.count < 2) return;
    ar.order = calloc(ar.count, sizeof *ar.order);
    ar_rec = calloc(ar.count, sizeof *ar_rec);
    if (!ar.order || !ar_rec) {
        free(ar.order);
        free(ar_rec);
        ar.order = (unsigned *)0;
        ar_rec = (void **)0;
        return;
    }
    for (i = 0; i < ar.count; ++i) ar.order[i] = i, ar_rec[i] = deque_at(ar.artists, i);
    for (i = 0; i < ar.count;) {
        for (s = i; i < ar.count && ar_sortable(ar_rec[i]); ++i) {}
        if (i - s > 1) cc_heapsort(ar.order + s, i - s, ar_cmp);
        if (i == s) ++i;   /* a fixed row */
    }
    free(ar_rec);
    ar_rec = (void **)0;
}

/* The title names the mode artist_type selects; the button shows the glyph of the other one. */
static void ar_mode_show(void) {
    int album = *(volatile int *)ARTIST_TYPE == 1;
    const char *icon = album ? "pod_nav_artist" : "pod_nav_albumartist";
    if (ar.title) widget_set_tr_text(ar.title, album ? "Album Artists" : "Artists");
    if (ar.toggle) {
        widget_set_prop_str(ar.toggle, "style:normal:icon", icon);
        widget_set_prop_str(ar.toggle, "style:over:icon", icon);
        widget_set_prop_str(ar.toggle, "style:pressed:icon", album ? "pod_nav_artist_down" : "pod_nav_albumartist_down");
        widget_invalidate_force(ar.toggle, (void *)0);
    }
}

static int ar_on_destroy(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (ar.artists) deque_destroy(ar.artists);
    free(ar.order);
    memset(&ar, 0, sizeof ar);
    return RET_OK;
}

/* One row per artist, in the display order (ar_sort), each a stock-built list row (see the header). */
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
            widget_set_text_utf8(label, ar_name(deque_at(ar.artists, ar_stock(i))));
        }
        img = image_create(row, w - CHEVRON_W, 0, CHEVRON_W - 4, ROW_H);
        if (img) {
            image_base_set_image(img, "right_arrow");
            widget_set_prop_str(img, "draw_type", "icon"); /* the string form the assets use */
        }
        widget_on(row, EVT_CLICK, ar_on_artist, (void *)(long)i);
    }
}

/* (Re)build the list from the stock query, with artist_type as it is: a copy of the stock rows, so Cover
 * Flow's own queries cannot pull it away. */
static void ar_load(void) {
    void *list;
    if (ar.artists) deque_destroy(ar.artists);
    ar.artists = (void *)0;
    free(ar.order);
    ar.order = (unsigned *)0;
    ar.count = 0;
    widget_destroy_children(ar.view);
    widget_set_prop_int(ar.view, "yoffset", 0);
    widget_set_prop_int(ar.view, "virtual_h", 0);
    list = loadLocalClassList(CLASS_ARTISTS) > 0 ? *(void **)PDEQ_SHOWLIST : (void *)0;
    if (list && deque_size(list) && (ar.artists = _create_deque("stSongInfo"))) {
        deque_init(ar.artists);
        deque_assign(ar.artists, list);
        ar.count = deque_size(ar.artists);
        if (ar.count > MAX_ARTISTS) ar.count = MAX_ARTISTS;
        ar_sort();
    }
    if (!ar.count) {
        ar_show(ar.list, 0);
        ar_show(ar.status, 1);
        widget_set_tr_text(ar.status, "Update Local Music first");
        return;
    }
    ar_show(ar.list, 1);
    ar_show(ar.status, 0);
    ar_build_rows();
}

/* The button: flip the stock setting the way the stock switch does, then list again. */
static int ar_on_toggle(void *ctx, void *e) {
    int type = *(volatile int *)ARTIST_TYPE != 1;
    (void)ctx; (void)e;
    *(volatile int *)ARTIST_TYPE = type;
    write_int_config(type, "PLAYSET", "ARTISTTYPE");
    *(volatile unsigned char *)ARTIST_RELOAD = 1;
    ar_mode_show();
    ar_load();
    return RET_OK;
}

/* The M1+ Pod menu's Artists row. 0 once the page is up, -1 if it could not open. */
int artists_open(void) {
    if (ar.win) return -1;
    memset(&ar, 0, sizeof ar);
    ar.win = window_open("m1pod_artists");
    if (!ar.win) return -1;
    widget_on(ar.win, EVT_DESTROY, ar_on_destroy, (void *)0);
    pod_bind(ar.win, "btn_return", pod_on_back, (void *)0);
    pod_bind(ar.win, "btn_backtoplayer", pod_on_player, (void *)0);
    ar.list = widget_lookup(ar.win, "pod_listview", 1);
    ar.view = widget_lookup(ar.win, "pod_scrollview", 1);
    ar.status = widget_lookup(ar.win, "label_status", 1);
    ar.title = widget_lookup(ar.win, "label_title", 1);
    ar.toggle = widget_lookup(ar.win, "btn_artisttype", 1);
    if (ar.toggle) widget_on(ar.toggle, EVT_CLICK, ar_on_toggle, (void *)0);
    if (!ar.list || !ar.view || !ar.status) {
        navigator_back(); /* an asset that is not ours */
        return -1;
    }
    ar_mode_show();
    ar_load();
    return 0;
}
