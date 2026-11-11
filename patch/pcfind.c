/* M1+ Podcasts: search inside one show (docs/modules/podcasts.md "Search inside a show").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * The Show page's search button opens ui/m1plus_pcfind.bin over the Show page: the Search page's field with our keyboard embedded (keyboard_attach) and one content view that paints the rows
 * (the library search's pattern: a title, a grey line, a hairline). The text is matched against the titles of the show's episodes, the list the Show page holds (pg.eps, read through
 * pg_find_*), by the library search's folding, terms and pinyin initials (search_titles_*, patch/search.c); results stay in the show's order. A tap opens the episode page on the Show page
 * (pg_find_pick) and closes this one; Back there opens it again (pcfind_reopen) with its text and scroll, the keyboard down. No hook, no thread; a 1 s timer and, while the Search All Episodes row loads, a 250 ms spinner timer.
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "grid.h"
#include "azlist.h"
#include "keyboard.h"
#include "search.h"
#include "i18n.h"
#include "podcasts.h"
#include "pcfind.h"

static struct {
    void *win, *view, *sv, *list, *status, *field, *st_title, *st_dim, *st_sub;
    char typed[PF_QMAX];
    unsigned short *rows; /* the episodes that match: indices into the Show page's list, in its order */
    int nrows, nterms, press, down, pressing, content;
    int more; /* the Search All Episodes row at the end of the results: 0 none, 1 a tap starts the job, 2 the job is on (pg_find_more) */
    char mline[96]; /* its text */
    unsigned timer; /* 1 s: the row's count, the job's end (pf_tick) */
    unsigned spin; /* the row's spinner (pf_spin_arm): 250 ms, only while the row is Loading…; 0 when none */
    m1_tap_t tap;
    grid_t g; /* the rows' texts (no pictures) */
} pf __attribute__((section(".scratch")));

static struct { /* what the page had when a result opened the episode page (it outlives the window) */
    int valid, off;
    unsigned show;
    char text[PF_QMAX];
} pf_keep __attribute__((section(".scratch")));

static void pf_redraw(void) { grid_sv_redraw(pf.sv); }

/* The rows the page paints: the results and the Search All Episodes row. */
static int pf_total(void) { return pf.nrows + (pf.more != 0); }

/* The Search All Episodes row's spinner while its job is on (pf.more == 2): the Wi-Fi page's frames (pf.g's, opened with the first) before the text, turned by a 250 ms timer that ends itself when the row is not busy
 * and is removed with the page (pf_on_destroy). The tick repaints only when the row is in view. */
static int pf_spin_tick(const void *timer) {
    int y;
    (void)timer;
    if (!pf.win || pf.more != 2) {
        pf.spin = 0;
        return RET_OK;
    }
    ++pf.g.spin_n;
    y = pf.nrows * PF_ROW_H - grid_sv_off(pf.sv);
    if (y < PF_LIST_H && y + PF_ROW_H > 0) pf_redraw();
    return RET_REPEAT;
}
static void pf_spin_arm(void) {
    if (pf.spin || !pf.win || pf.more != 2) return;
    grid_spin_open(&pf.g, "wf_spin", PS_SPIN_PX);
    pf.spin = timer_add(pf_spin_tick, (void *)0, PS_SPIN_MS);
}

/* The row's state is read again (the Show page's row: only while the field is not empty); 1 when its text or state changed. */
static int pf_more_get(void) {
    char l[sizeof pf.mline];
    int m = pf.nterms ? pg_find_more(l, sizeof l) : 0, ch;
    if (!m) l[0] = 0;
    ch = m != pf.more || strcmp(l, pf.mline);
    pf.more = m;
    memcpy(pf.mline, l, sizeof l);
    pf_spin_arm();
    return ch;
}

/* The content: the rows, then the air under them or the keyboard's height while it is up; the list or "No results" shows. */
static void pf_layout(void) {
    int pad = keyboard_shown() ? KB_H : PF_BOTTOM, h, off = grid_sv_off(pf.sv);
    pf.content = pf_total() * PF_ROW_H + pad;
    h = pf.content < PF_LIST_H ? PF_LIST_H : pf.content;
    widget_resize(pf.view, 320, h);
    widget_set_prop_int(pf.sv, "virtual_h", h);
    if (off > h - PF_LIST_H) widget_set_prop_int(pf.sv, "yoffset", h - PF_LIST_H);
    m1_show(pf.list, pf_total() != 0); /* (with no match the row stands alone at the top and "No results" under it) */
    m1_show(pf.status, pf.nrows == 0 && pf.nterms != 0);
    if (pf.nrows == 0 && pf.nterms != 0) widget_set_tr_text(pf.status, "No results");
}

/* The text is applied: every episode's title is matched, the rows are the ones that hold every term. */
static void pf_apply(void) {
    int i, n = pg_find_count();
    pf.nrows = 0;
    pf.nterms = search_titles_query(pf.typed);
    pf_more_get();
    if (pf.nterms)
        for (i = 0; i < n && pf.nrows < PC_LIST_MAX; ++i) {
            const pc_ep_t *e = pg_find_ep(i);
            if (e && search_titles_match(e->title)) pf.rows[pf.nrows++] = (unsigned short)i;
        }
    grid_drop(&pf.g);
    widget_set_prop_int(pf.sv, "yoffset", 0);
    pf_layout();
    pf_redraw();
}

static void pf_prep(grid_tile_t *t, int r) {
    const pc_ep_t *e;
    char sub[96], date[48];
    if (r >= pf.nrows) {
        grid_set(t, pf.mline, "", 0);
        return;
    }
    e = pg_find_ep(pf.rows[r]);
    if (!e) return;
    date[0] = 0;
    if (e->pub) pc_when(e->pub, (unsigned)time((long *)0), date, sizeof date);
    if (e->state == PC_LOCAL)
        snprintf(sub, sizeof sub, date[0] ? "%s \xc2\xb7 %s" : "%s%s", date, TR("Downloaded"));
    else
        snprintf(sub, sizeof sub, "%s", date);
    grid_set(t, e->title, sub, 0);
}

static void pf_span(int *r0, int *r1) {
    int off = grid_sv_off(pf.sv);
    *r0 = off < 0 ? 0 : off / PF_ROW_H;
    *r1 = (off + PF_LIST_H - 1) / PF_ROW_H;
    if (*r1 > pf_total() - 1) *r1 = pf_total() - 1;
}

static grid_tile_t *pf_tile(int r) {
    int r0, r1, fresh;
    grid_tile_t *t;
    pf_span(&r0, &r1);
    t = grid_tile(&pf.g, r, r0 - 2, r1 + 2, &fresh);
    if (fresh) pf_prep(t, r);
    return t;
}

static int pf_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int r0, r1, r, off = grid_sv_off(pf.sv), pass;
    (void)ctx;
    if (!canvas || !pf.view || !pf_total()) return RET_OK;
    pf_span(&r0, &r1);
    I(canvas, CANVAS_OY) += off;
    for (r = r0; r <= r1; ++r) {
        int y = r * PF_ROW_H - off;
        if (pf.press == r + 1) az_fill(canvas, 0, y, y + PF_ROW_H - 1, 320, LIST_PRESS);
        if (r == pf.nrows && pf.more == 2)
            grid_spin_draw(canvas, &pf.g, PF_TEXT_X, y + (PF_ROW_H - PS_SPIN_PX) / 2, PF_LIST_H);
        if (r < pf.nrows) az_fill(canvas, PF_TEXT_X, y + PF_ROW_H - 1, y + PF_ROW_H, PF_SEP_END - PF_TEXT_X, LIST_HAIR);
    }
    for (pass = 0; pass < 3;
         ++pass) { /* the titles, the played ones dimmed, then the grey lines: one text style at a time */
        widget_prepare_text_style(pass == 0 ? pf.st_title : pass == 1 ? pf.st_dim : pf.st_sub, canvas);
        for (r = r0; r <= r1; ++r) {
            int y = r * PF_ROW_H - off, more = r >= pf.nrows;
            int played =
                pass < 2 && (more ? pf.more == 2 : pg_find_played(pf.rows[r])); /* (the row dims while its job runs) */
            if (pass < 2 && played != pass) continue;
            if (more && pass == 2) continue;
            int sx = more && pf.more == 2 && pf.g.spin[0] ? PS_SPIN_PX + PS_SPIN_GAP
                                                          : 0; /* (the busy row's text after its spinner) */
            grid_text(canvas, pf_tile(r), pass == 2, PF_TEXT_X + sx,
                      y + (more        ? (PF_ROW_H - LIST_TITLE_H) / 2
                           : pass == 2 ? PF_SUB_Y
                                       : PF_TITLE_Y),
                      PF_TEXT_END - PF_TEXT_X - sx, pass == 2 ? LIST_SUB_H : LIST_TITLE_H, 0);
        }
    }
    I(canvas, CANVAS_OY) -= off;
    return RET_OK;
}

static int pf_at(void *e) {
    int pt[2];
    grid_ev_local(pf.view, e, pt);
    if (pt[1] >= 0 && pt[1] / PF_ROW_H == pf.nrows && pf.more == 1)
        return pf.nrows; /* (the row while its job runs is no target) */
    return pt[1] >= 0 && pt[1] / PF_ROW_H < pf.nrows ? pt[1] / PF_ROW_H : -1;
}

/* A tap on a result: the page's text and scroll are kept, the episode page opens on the Show page, this one closes. */
static void pf_pick(int r) {
    if (r == pf.nrows &&
        pf.more == 1) { /* Search All Episodes: the Show page's job starts; the row reads Loading… at once */
        pg_find_more_tap();
        if (pf_more_get()) grid_drop(&pf.g), pf_redraw();
        return;
    }
    if (r < 0 || r >= pf.nrows) return;
    snprintf(pf_keep.text, sizeof pf_keep.text, "%s", pf.typed);
    pf_keep.off = grid_sv_off(pf.sv);
    pf_keep.show = pg_find_show();
    pf_keep.valid = 1;
    if (!pg_find_pick(pf.rows[r])) {
        pf_keep.valid = 0;
        return;
    }
    navigator_back();
}

static int pf_on_down(void *ctx, void *e) {
    int a;
    (void)ctx;
    pf.down = 0;
    pf.pressing = 1;
    if (!e || !pf.view) return RET_OK;
    a = pf_at(e);
    pf.down = a + 1, m1_tap_at(&pf.tap, e);
    grid_set_press(&pf.press, a + 1, pf.sv);
    return RET_OK;
}

static int pf_on_up(void *ctx, void *e) {
    int a = pf.down - 1;
    (void)ctx;
    pf.down = pf.pressing = 0;
    grid_set_press(&pf.press, 0, pf.sv);
    if (a >= 0 && e && pf.view && m1_tap_near(&pf.tap, e) && pf_at(e) == a) pf_pick(a);
    return RET_OK;
}

static void pf_kb_hide(void) {
    keyboard_show(0);
    pf_layout();
    pf_redraw();
}

/* The scroll_view took the gesture as a drag: the keyboard goes away. */
static int pf_on_abort(void *ctx, void *e) {
    int drag = pf.pressing;
    (void)ctx;
    (void)e;
    pf.down = pf.pressing = 0;
    grid_set_press(&pf.press, 0, pf.sv);
    if (drag && keyboard_shown()) pf_kb_hide();
    return RET_OK;
}

/* A tap on the field brings the keyboard back. */
static int pf_on_field(void *ctx, void *e) {
    (void)ctx;
    if (e && *(int *)e == EVT_POINTER_UP && !keyboard_shown()) {
        keyboard_show(1);
        pf_layout();
        pf_redraw();
    }
    return RET_OK;
}

static void pf_on_text(
    const char *text) { /* the field's committed text changed: the rows follow at once (a title match is cheap) */
    if (!pf.win || !strcmp(text, pf.typed)) return;
    snprintf(pf.typed, sizeof pf.typed, "%s", text);
    pf_apply();
}

static void pf_on_go(void) { pf_kb_hide(); } /* the keyboard's action key: the pad goes down */

/* The pinyin engine's megabyte is held only when some title has a Chinese character (checked at open, and again when the list is read again: the archive's titles may have some). */
static void pf_hold(void) {
    int i, n = pg_find_count(), hz = 0;
    for (i = 0; i < n && !hz; ++i) {
        const pc_ep_t *e = pg_find_ep(i);
        hz = e && search_titles_hanzi(e->title);
    }
    if (hz) search_titles_hold();
}

/* 1 s, alive while the page is: the Show page's tick is stopped under this page, so the end of its See All job (the downloads' timer runs it) is picked up here. The list is read again by the Show page's
 * own function (a reload that brought the archive: the engine's hold rule is checked again, the query runs anew, the list starts at the top and the row is gone; any other: the same query, the scroll kept), or the
 * row's count and words are painted when they changed. */
static int pf_tick(const void *timer) {
    int s;
    (void)timer;
    if (!pf.win) return RET_OK;
    s = pg_find_sync();
    if (s) {
        int off = grid_sv_off(pf.sv);
        pf_hold();
        pf_apply();
        if (s == 1 && off > 0)
            widget_set_prop_int(pf.sv, "yoffset",
                                off > pf.content - PF_LIST_H ? (pf.content > PF_LIST_H ? pf.content - PF_LIST_H : 0)
                                                             : off);
    } else if (pf_more_get()) {
        grid_drop(&pf.g);
        pf_layout();
        pf_redraw();
    }
    return RET_REPEAT;
}

static int pf_on_destroy(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    m1_timer_stop(&pf.timer);
    m1_timer_stop(&pf.spin);
    keyboard_detach();
    search_titles_close();
    grid_free(&pf.g);
    free(pf.rows);
    memset(&pf, 0, sizeof pf);
    return RET_OK;
}

static int pf_open(void) {
    int n = pg_find_count();
    if (pf.win || n <= 0 || search_titles_open() != 0) return -1;
    memset(&pf, 0, sizeof pf);
    pf.win = window_open("m1plus_pcfind");
    if (!pf.win) {
        search_titles_close();
        memset(&pf, 0, sizeof pf);
        return -1;
    }
    widget_on(pf.win, EVT_DESTROY, pf_on_destroy, (void *)0);
    m1_bind(pf.win, "pf_close", m1_on_back, (void *)0);
    pf.list = widget_lookup(pf.win, "pf_listview", 1);
    pf.sv = widget_lookup(pf.win, "pf_scrollview", 1);
    pf.view = widget_lookup(pf.win, "pf_view", 1);
    pf.status = widget_lookup(pf.win, "pf_status", 1);
    pf.field = widget_lookup(pf.win, "kb_field", 1);
    pf.st_title = widget_lookup(pf.win, "label_row_title", 1);
    pf.st_dim = widget_lookup(pf.win, "label_row_dim", 1);
    pf.st_sub = widget_lookup(pf.win, "label_row_sub", 1);
    pf.rows = calloc(PC_LIST_MAX, sizeof *pf.rows);
    if (!pf.rows || !pf.list || !pf.sv || !pf.view || !pf.status || !pf.field || !pf.st_title || !pf.st_dim ||
        !pf.st_sub || !grid_init(&pf.g, pf.win, PF_TILES, 8, 0) ||
        keyboard_attach(pf.win, TR("Search Episodes"), SE_TEXT_X, SE_TEXT_W, SE_CARET_Y, 0, pf_on_text, pf_on_go) !=
            0) {
        navigator_back(); /* an asset that is not ours, or no memory: the destroy handler frees what exists */
        return -1;
    }
    pf_hold(); /* the engine's megabyte only for a show with Chinese titles */
    widget_on(pf.view, EVT_POINTER_DOWN, pf_on_down, (void *)0);
    widget_on(pf.view, EVT_POINTER_UP, pf_on_up, (void *)0);
    widget_on(pf.view, EVT_POINTER_ABORT, pf_on_abort, (void *)0);
    widget_on(pf.view, EVT_AFTER_PAINT, pf_on_paint, (void *)0);
    widget_on(pf.field, EVT_POINTER_UP, pf_on_field, (void *)0);
    m1_show(pf.list, 0);
    m1_show(pf.status, 0);
    pf_layout();
    pf.timer = timer_add(pf_tick, (void *)0, 1000);
    return 0;
}

int pcfind_open(void) {
    pf_keep.valid = 0;
    return pf_open();
}

int pcfind_reopen(void) {
    int off;
    if (!pf_keep.valid || pf_keep.show != pg_find_show()) {
        pf_keep.valid = 0;
        return -1;
    }
    pf_keep.valid = 0;
    if (pf_open() != 0) return -1;
    off = pf_keep.off;
    keyboard_set_text(pf_keep.text); /* the field shows it (on_change applies it) */
    snprintf(pf.typed, sizeof pf.typed, "%s", pf_keep.text);
    pf_apply();
    keyboard_show(0);
    pf_layout();
    widget_set_prop_int(pf.sv, "yoffset",
                        off > pf.content - PF_LIST_H ? (pf.content > PF_LIST_H ? pf.content - PF_LIST_H : 0) : off);
    pf_redraw();
    return 0;
}

void pcfind_forget(void) { pf_keep.valid = 0; }
