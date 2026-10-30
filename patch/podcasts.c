/* M1+ Music Podcasts: the shows on the card and their episodes, one page with two levels.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * Resume, played marks and speed per show follow q2-pod (Copyright (c) 2026 Diamond Bond, MIT, https://github.com/DiamondBond/q2-pod; see NOTICE); the data is patch/pcmodel.c's.
 *
 * ui/m1plus_podcasts.bin is the Albums page's structure (docs/modules/albums.md): the navbar over a stock list, list_view > scroll_view, whose ONE child, view_grid, paints
 * the rows itself in its EVT_AFTER_PAINT (no widget per row), so a show of hundreds of episodes costs a tile ring. The window is opened by the Extras item Podcasts and has two
 * levels, switched in place (the Pod's way: no second window; the navbar's Back goes up a level before it leaves the page):
 *
 *   Shows      a row per folder of /mnt/mmc/Podcasts: the cover (cover.jpg / folder.jpg, a PC_ROW_H list row's LIST_ART px cover), the show's name, "N episodes".
 *   Show       a header (the PC_HDR_ART px cover, the name, the episode count and the show's speed: a tap on the speed cycles 1x 1.25x 1.5x 2x and is kept), then a row per
 *              downloaded episode, newest first: the unplayed dot, the title, a grey line "date - N min left" / "date - N min" / "date - Played". A tap on the dot toggles
 *              played; a tap on the row plays this episode and the ones after it in the list's order (from the first second, or from the saved place: pc_note jumps there).
 *
 * Playing builds stSongInfo records of our own for the show's files (the library may not have scanned them) and starts them as the stock Folders page does: class 1, the
 * queue handed to playing_page (start_player copies it). Cover pictures are decoded one per 16 ms tick (pc_cover_ok first: a picture that is too large for the stock decoder is
 * refused). The page's 1 s timer calls pc_note, like the other pages that already look at the playing track. No hook.
 */
#include "offsets.inc"
#include "stock.h"
#include "covercache.h"
#include "common.h"
#include "grid.h"
#include "azlist.h"
#include "i18n.h"
#include "podcasts.h"

extern void pod_toast(const char *text);   /* patch/shuffle.c: the stock message box */
extern void pod_set_in_order(void);        /* patch/shuffle.c: Shuffle and Repeat one become List play */

#define I(w, off) (*(int *)((char *)(w) + (off)))
#define B(w, off) (*(unsigned char *)((char *)(w) + (off)))
#define P(w, off) (*(void **)((char *)(w) + (off)))

#define PG_W 320
#define PG_LOAD_MS 16
#define PG_TICK_MS 1000
#define PG_TAP_PX SC_DRAG_PX
#define PG_DOT_X 12
#define PG_TEXT_X 34
#define PG_TEXT_W 274            /* to the 12 px right margin */
#define PG_BOTTOM 12
#define PG_HDR_TEXT_X 124
#define PG_HDR_TEXT_W 184
#define PG_SPEED_Y 82            /* the speed text's top in the header; its touch area is PG_SPEED_H high from there */
#define PG_SPEED_H 34
#define PG_DOT_RGB 0xff840au     /* #0A84FF as the RGBA bitmap word's colour bytes (r, g, b order in a little-endian word: 0xBBGGRR) */
#define PG_REC_SIZE 0x58

enum { L_SHOWS = 0, L_EPS = 1 };

static struct {
    void *win, *view, *sv, *status, *title, *fade;
    void *st_title, *st_sub, *st_dim, *st_acc;   /* hidden labels whose styles are the row title, the grey line, a played title and the speed */
    char root[PC_FILE + 20];
    pc_show_t *shows;
    int nshows;
    pc_ep_t *eps;                 /* the downloaded episodes of the show open, newest first */
    int neps;
    int level, sel, show_off;     /* the level, the show open, the Shows list's offset to come back to */
    int press, down, down_x, down_y;   /* the row under the finger + 1; the row a press began on + 1 (0 none; a header hit is -1) and where */
    int fg, noscroll;
    unsigned rev;                 /* pc_rev() the rows were made at */
    unsigned timer, load_timer;
    void *dot;                    /* the unplayed dot's bitmap */
    grid_tile_t spd;              /* the speed text of the Show header */
    grid_t g;                     /* the tiles: a show's cover and texts, an episode's texts (ckey = its state + 1) */
    grid_t hg;                    /* the Show header's cover (one tile) and its name and count */
} pg __attribute__((section(".scratch")));

static void pg_show(void *w, int on) {
    if (!w) return;
    widget_set_visible(w, on, 0);
    widget_set_sensitive(w, on);
}

static int pg_abs(int v) { return v < 0 ? -v : v; }
static int pg_off(void) { return pg.sv ? I(pg.sv, SC_YOFF) : 0; }
static void pg_redraw(void) { widget_invalidate_force(pg.sv, (void *)0); }

static int pg_count(void) { return pg.level == L_SHOWS ? pg.nshows : pg.neps; }
static int pg_top(void) { return pg.level == L_SHOWS ? 0 : PC_HDR_H; }
static int pg_content(void) { return pg_count() ? pg_top() + pg_count() * PC_ROW_H + (pg.level == L_EPS ? PG_BOTTOM : 0) : pg.level == L_EPS ? PC_HDR_H : 0; }

static void pg_size(void) {
    int h = pg_content();
    widget_resize(pg.view, PG_W, h > 0 ? h : 1);
    widget_set_prop_int(pg.sv, "virtual_h", h > 0 ? h : 1);
}

/* The rows [*r0, *r1] that touch the view (r1 < r0 for none); inside [0, count - 1] also while the list is pulled past an end. */
static void pg_span(int *r0, int *r1) {
    int n = pg_count(), s = pg_off() - pg_top();
    *r0 = s / PC_ROW_H;
    *r1 = (s + GRID_VIEW_H - 1) / PC_ROW_H;
    if (s < 0) *r0 = 0;
    if (*r0 < 0) *r0 = 0;
    if (*r1 > n - 1) *r1 = n - 1;
}

/* ---------------------------------------------------------------------------
 * Texts and tiles
 */
static void pg_sub_of(const pc_ep_t *e, unsigned *state, char *out, unsigned size) {
    static const char sep[] = " \xc2\xb7 ";   /* " · " */
    char date[48], tail[40];
    unsigned pos, len, total, mins = 0, o = 0, k;
    int s = pc_state(e->hash, &pos, &len);
    total = len ? len : e->dur;
    tail[0] = 0;
    date[0] = 0;
    if (e->pub) pc_when(e->pub, (unsigned)time((long *)0), date, sizeof date);   /* the date is made again whenever the tiles are (the page opens, comes back to the front) */
    if (s == PC_DONE) {
        const char *t = TR("Played");
        for (k = 0; t[k] && k + 1 < sizeof tail; ++k) tail[k] = t[k];
        tail[k] = 0;
    } else if (s == PC_PROGRESS && total > pos) {
        mins = (total - pos + 59) / 60;
        pc_fmt(tail, sizeof tail, TR("%d min left"), mins);
    } else if (total) {
        mins = (total + 59) / 60;
        pc_fmt(tail, sizeof tail, TR("%d min"), mins);
    }
    for (k = 0; date[k] && o + 1 < size; ++k) out[o++] = date[k];
    if (date[0] && tail[0])
        for (k = 0; sep[k] && o + 1 < size; ++k) out[o++] = sep[k];
    for (k = 0; tail[k] && o + 1 < size; ++k) out[o++] = tail[k];
    out[o] = 0;
    *state = (unsigned)s;
}

/* The tile of row a at the current level; a new tile gets its texts. */
static grid_tile_t *pg_tile(int a) {
    int lo, hi, fresh;
    grid_tile_t *t;
    pg_span(&lo, &hi);
    lo -= 2, hi += 2;
    if (lo < 0) lo = 0;
    if (pg.level == L_SHOWS) lo = 0, hi = pg.nshows - 1;
    t = grid_tile(&pg.g, a, lo, hi, &fresh);
    if (fresh) {
        char sub[80];
        if (pg.level == L_SHOWS) {
            const pc_show_t *s = &pg.shows[a];
            pc_fmt(sub, sizeof sub, TR(s->count == 1 ? "%d episode" : "%d episodes"), s->count);
            grid_set(t, s->title, sub, 0);
        } else {
            unsigned state;
            pg_sub_of(&pg.eps[a], &state, sub, sizeof sub);
            grid_set(t, pg.eps[a].title, sub, 0);
            t->ckey = state + 1;
        }
    }
    return t;
}

static grid_tile_t *pg_tile_of(void *ctx, int a) {
    (void)ctx;
    return pg_tile(a);
}

/* The Show header's texts: the name, the episode count; and the speed's. */
static void pg_header_texts(void) {
    const pc_show_t *s = &pg.shows[pg.sel];
    static const char *const name[PC_SPEEDS] = {"1x", "1.25x", "1.5x", "2x"};
    char count[40];
    int mode = pc_speed_get(s->hash);
    grid_tile_t *t = &pg.hg.tiles[0];
    pc_fmt(count, sizeof count, TR(pg.neps == 1 ? "%d episode" : "%d episodes"), (unsigned)pg.neps);
    grid_set(t, s->title, count, 0);   /* (the cover in the tile stays) */
    t->fit = 0, t->tw = t->aw = 0;
    memset(&pg.spd, 0, sizeof pg.spd);
    grid_set(&pg.spd, name[mode], "", 0);
}

/* ---------------------------------------------------------------------------
 * Paint
 */
static void pg_paint_shows(void *canvas) {
    int r0, r1;
    pg_span(&r0, &r1);
    if (r1 < r0) return;
    grid_list_paint(canvas, &pg.g, pg.st_title, pg.st_sub, r0, r1, pg_off(), GRID_VIEW_H, pg.press, 0, pg_tile_of, (void *)0);
}

static void pg_paint_eps(void *canvas) {
    int r0, r1, r, off = pg_off(), pass;
    grid_tile_t *h = &pg.hg.tiles[0];
    if (off < PC_HDR_H) {   /* the header: cover, name, count, speed */
        grid_blit(canvas, &pg.hg, h, 16, 16 - off, GRID_VIEW_H);
        widget_prepare_text_style(pg.st_title, canvas);
        grid_text(canvas, h, 0, PG_HDR_TEXT_X, 22 - off, PG_HDR_TEXT_W, LIST_TITLE_H, GRID_VIEW_H);
        widget_prepare_text_style(pg.st_sub, canvas);
        grid_text(canvas, h, 1, PG_HDR_TEXT_X, 50 - off, PG_HDR_TEXT_W, LIST_SUB_H, GRID_VIEW_H);
        widget_prepare_text_style(pg.st_acc, canvas);
        grid_text(canvas, &pg.spd, 0, PG_HDR_TEXT_X, PG_SPEED_Y + (PG_SPEED_H - LIST_SUB_H) / 2 - off, PG_HDR_TEXT_W, LIST_SUB_H, GRID_VIEW_H);
    }
    pg_span(&r0, &r1);
    if (r1 < r0) return;
    for (r = r0; r <= r1; ++r) {
        grid_tile_t *t = pg_tile(r);
        int y = PC_HDR_H + r * PC_ROW_H - off;
        if (pg.press == r + 1) az_fill(canvas, 0, y, y + PC_ROW_H - 1, PG_W, LIST_PRESS);
        az_fill(canvas, PG_TEXT_X, y + PC_ROW_H - 1, y + PC_ROW_H, PG_W - PG_TEXT_X, LIST_HAIR);
        if (pg.dot && t->ckey != PC_DONE + 1) {   /* the unplayed dot (a started episode too) */
            int src[4], dst[4], top = y + (PC_ROW_H - PC_DOT) / 2;
            if (top >= 0 && top + PC_DOT <= GRID_VIEW_H) {
                src[0] = src[1] = 0, src[2] = src[3] = PC_DOT;
                dst[0] = PG_DOT_X, dst[1] = top, dst[2] = dst[3] = PC_DOT;
                canvas_draw_image(canvas, pg.dot, src, dst);
            }
        }
    }
    for (pass = 0; pass < 3; ++pass) {   /* titles, played titles, grey lines: one text style at a time */
        widget_prepare_text_style(pass == 0 ? pg.st_title : pass == 1 ? pg.st_dim : pg.st_sub, canvas);
        for (r = r0; r <= r1; ++r) {
            grid_tile_t *t = pg_tile(r);
            int y = PC_HDR_H + r * PC_ROW_H - off, played = t->ckey == PC_DONE + 1;
            if (pass == 2) grid_text(canvas, t, 1, PG_TEXT_X, y + LIST_SUB_Y, PG_TEXT_W, LIST_SUB_H, GRID_VIEW_H);
            else if ((pass == 1) == played) grid_text(canvas, t, 0, PG_TEXT_X, y + LIST_TITLE_Y, PG_TEXT_W, LIST_TITLE_H, GRID_VIEW_H);
        }
    }
}

static int pg_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int off = pg_off();
    (void)ctx;
    if (!canvas || !pg.view || !pg.g.tiles) return RET_OK;
    I(canvas, CANVAS_OY) += off;
    if (pg.level == L_SHOWS && pg.nshows) pg_paint_shows(canvas);
    else if (pg.level == L_EPS && pg.hg.tiles) pg_paint_eps(canvas);
    I(canvas, CANVAS_OY) -= off;
    return RET_OK;
}

/* The unplayed dot: a disc of the accent colour, antialiased by 4 x 4 samples a pixel, in an RGBA bitmap. */
static void pg_make_dot(void) {
    unsigned *px;
    int x, y, i, j, n;
    void *b = bitmap_create_ex(PC_DOT, PC_DOT, PC_DOT * 4, BITMAP_RGBA8888);
    if (!b) return;
    px = (unsigned *)bitmap_lock_buffer_for_write(b);
    if (!px || bitmap_get_line_length(b) != PC_DOT * 4) {
        if (px) bitmap_unlock_buffer(b);
        bitmap_destroy(b);
        return;
    }
    for (y = 0; y < PC_DOT; ++y)
        for (x = 0; x < PC_DOT; ++x) {
            for (n = 0, i = 0; i < 4; ++i)
                for (j = 0; j < 4; ++j) {
                    int dx = x * 8 + 2 * j + 1 - PC_DOT * 4, dy = y * 8 + 2 * i + 1 - PC_DOT * 4;   /* eighths of a pixel from the centre */
                    if (dx * dx + dy * dy <= (PC_DOT * 4 - 4) * (PC_DOT * 4 - 4)) ++n;   /* the disc is 11 px across */
                }
            px[y * PC_DOT + x] = (unsigned)(n * 255 / 16) << 24 | PG_DOT_RGB;
        }
    bitmap_unlock_buffer(b);
    pg.dot = b;
}

/* ---------------------------------------------------------------------------
 * The loader: one cover a tick
 */
static int pg_on_load(const void *unused);

static void pg_kick(void) {
    if (pg.win && pg.fg && !pg.load_timer) pg.load_timer = timer_add(pg_on_load, (void *)0, PG_LOAD_MS);
}

/* The path of a show's cover picture as a file:// url. */
static const char *pg_cover_url(const pc_show_t *s, char *url, unsigned size) {
    char path[PC_FILE * 2 + 40];
    unsigned n = 0, k;
    if (!s->cover[0]) return (const char *)0;
    for (k = 0; pg.root[k] && n < sizeof path - 1; ++k) path[n++] = pg.root[k];
    path[n++] = '/';
    for (k = 0; s->dir[k] && n < sizeof path - 1; ++k) path[n++] = s->dir[k];
    path[n++] = '/';
    for (k = 0; s->cover[k] && n < sizeof path - 1; ++k) path[n++] = s->cover[k];
    path[n] = 0;
    if (!pc_cover_ok(path) || n + 8 > size) return (const char *)0;
    memcpy(url, "file://", 7);
    memcpy(url + 7, path, n + 1);
    return url;
}

static void pg_art(grid_t *g, grid_tile_t *t, const pc_show_t *s) {
    char url[PC_FILE * 2 + 60];
    grid_art_url(g, t, pg_cover_url(s, url, sizeof url));
}

/* The show (Shows level) whose cover is next: the rows in view first, then the others; -1 when every tile has been tried. */
static int pg_next_cover(void) {
    int r0, r1, a;
    pg_span(&r0, &r1);
    for (a = r0; a <= r1; ++a) {
        grid_tile_t *t = grid_find(&pg.g, a);
        if (!t || !t->art) return a;
    }
    for (a = 0; a < pg.nshows; ++a) {
        grid_tile_t *t = grid_find(&pg.g, a);
        if (!t || !t->art) return a;
    }
    return -1;
}

static int pg_on_load(const void *unused) {
    (void)unused;
    pg.load_timer = 0;
    if (!pg.win || !pg.fg || !pg.g.tiles) return RET_OK;
    if (pg.level == L_SHOWS) {
        int a = pg_next_cover();
        if (a >= 0) {
            grid_tile_t *t = pg_tile(a);
            if (!t->art) pg_art(&pg.g, t, &pg.shows[a]);
            pg_redraw();
            pg_kick();
        }
    } else if (pg.hg.tiles && !pg.hg.tiles[0].art) {
        pg_art(&pg.hg, &pg.hg.tiles[0], &pg.shows[pg.sel]);
        pg_redraw();
    }
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * Levels
 */
static void pg_title(const char *key, const char *text) {
    if (!pg.title) return;
    if (key) az_fit(pg.title, TR(key));
    else az_fit(pg.title, text);
}

static void pg_empty(const char *key) {
    pg_show(pg.view, 0);
    pg_show(pg.status, 1);
    widget_set_tr_text(pg.status, key);
}

static void pg_fade(void) {
    if (!pg.fade) return;
    widget_set_visible(pg.fade, pg_off() > 0, 0);
    widget_set_sensitive(pg.fade, 0);
}

static int pg_on_scroll(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (!pg.win) return RET_OK;
    pg_fade();
    pg_kick();
    return RET_OK;
}

static void pg_drop_tiles(void) {
    grid_drop(&pg.g);
    grid_drop(&pg.hg);
    pg.press = pg.down = 0;
}

/* The Shows level: the folders again (a show may have come or gone). */
static void pg_load_shows(void) {
    pg_drop_tiles();
    pg.level = L_SHOWS;
    pg.nshows = pc_scan_shows(pg.shows, PC_MAX_SHOWS);
    free(pg.eps);
    pg.eps = (pc_ep_t *)0;
    pg.neps = 0;
    pg_title("Podcasts", (const char *)0);
    pg_show(pg.view, 1);
    pg_show(pg.status, 0);
    if (!pg.nshows) pg_empty("No podcasts. Copy a folder for each show into Podcasts on the card.");
    grid_shape(&pg.g, LIST_ART, LIST_R, 1);
    grid_placeholder(&pg.g);
    pg_size();
    widget_set_prop_int(pg.sv, "yoffset", pg.show_off);
    pg_fade();
    pg_redraw();
    pg_kick();
}

/* The Show level: the downloaded episodes of show `i`, newest first. */
static void pg_open_show(int i) {
    pc_ep_t *all = calloc(PC_MAX_EPS, sizeof *all);
    int n, k, m = 0;
    if (!all) {
        pod_toast(TR("Not enough memory"));
        return;
    }
    n = pc_load_show(&pg.shows[i], all, PC_MAX_EPS);
    for (k = 0; k < n; ++k)
        if (all[k].state == PC_LOCAL) {
            if (m != k) memcpy(&all[m], &all[k], sizeof *all);
            ++m;
        }
    pg.show_off = pg_off();
    pg_drop_tiles();
    free(pg.eps);
    pg.eps = all, pg.neps = m, pg.sel = i, pg.level = L_EPS;
    pg.rev = pc_rev();
    pg_title((const char *)0, pg.shows[i].title);
    pg_show(pg.view, 1);
    pg_show(pg.status, 0);
    if (!m) pg_empty("No downloaded episodes");   /* (a show with a metadata file and no file yet: the subscribe phase's) */
    grid_shape(&pg.g, LIST_ART, LIST_R, 1);
    grid_shape(&pg.hg, PC_HDR_ART, 10, 0);
    grid_placeholder(&pg.hg);
    pg_header_texts();
    pg_size();
    widget_set_prop_int(pg.sv, "yoffset", 0);
    pg_fade();
    pg_redraw();
    pg_kick();
}

static int pg_on_back(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (pg.win && pg.level == L_EPS) pg_load_shows();
    else navigator_back();
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * Playing
 */
/* An stSongInfo of our own for episode e of the show open (strings duplicated; the deque copies them again and the caller frees these). */
static void pg_record(unsigned *rec, const pc_ep_t *e, const char *path) {
    const pc_show_t *s = &pg.shows[pg.sel];
    memset(rec, 0, PG_REC_SIZE);
    *(char **)((char *)rec + REC_NAME) = strdup(e->file);
    *(char **)((char *)rec + REC_PATH) = strdup(path);
    *(char **)((char *)rec + REC_TITLE) = strdup(e->title);
    *(char **)((char *)rec + REC_ALBUM) = strdup(s->title);
    *(char **)((char *)rec + REC_ARTIST) = strdup(s->title);
    *(int *)((char *)rec + REC_TYPE) = 8;
    *(int *)((char *)rec + REC_CLASS) = 1;
}

static void pg_record_free(unsigned *rec) {
    static const int field[] = {REC_NAME, REC_PATH, REC_TITLE, REC_ALBUM, REC_ARTIST};
    unsigned i;
    for (i = 0; i < sizeof field / sizeof *field; ++i) free(*(char **)((char *)rec + field[i]));
}

static int pg_path(const pc_ep_t *e, char *out, unsigned size) {
    unsigned n = 0, k;
    const char *parts[3];
    int p;
    parts[0] = pg.root, parts[1] = pg.shows[pg.sel].dir, parts[2] = e->file;
    for (p = 0; p < 3; ++p) {
        if (p) out[n++] = '/';
        for (k = 0; parts[p][k]; ++k) {
            if (n + 2 >= size) return 0;
            out[n++] = parts[p][k];
        }
    }
    out[n] = 0;
    return 1;
}

/* Episode `at` and the ones after it: the queue (the list's order, from the first row, so Previous goes back up the list), Now Playing. */
static void pg_play(int at) {
    void *queue;
    int i, ok = 0;
    char path[PC_FILE * 2 + 40];
    struct {
        void *dq;
        int idx, cls, mode;
    } context;
    if (at < 0 || at >= pg.neps || !pg_path(&pg.eps[at], path, sizeof path) || access(path, F_OK)) {
        pod_toast(TR("Storage unavailable"));
        return;
    }
    queue = _create_deque("stSongInfo");
    if (!queue) return;
    deque_init(queue);
    for (i = 0; i < pg.neps; ++i) {
        unsigned rec[PG_REC_SIZE / 4];
        char p[PC_FILE * 2 + 40];
        if (!pg_path(&pg.eps[i], p, sizeof p)) {
            if (i < at) --at;   /* a name that does not fit: skipped (the model refused such names; this is the belt) */
            continue;
        }
        pg_record(rec, &pg.eps[i], p);
        _deque_push_back(queue, rec);
        pg_record_free(rec);
        ++ok;
    }
    if (!ok) {
        deque_destroy(queue);
        pod_toast(TR("Storage unavailable"));
        return;
    }
    pc_restart(pg.eps[at < pg.neps ? at : 0].hash);
    pc_speed_apply(pg.shows[pg.sel].hash);
    pod_set_in_order();
    *(int *)G_CLASS_TYPE = 1;
    context.dq = queue, context.idx = at, context.cls = 1, context.mode = PLAY_MODE;
    navigator_to_with_context("playing_page", &context);   /* start_player copies the queue */
    deque_destroy(queue);
}

/* ---------------------------------------------------------------------------
 * Touch
 */
static int pg_item_of(void *e, int *x) {
    int pt[2], y;
    pt[0] = I(e, PE_X), pt[1] = I(e, PE_Y);
    widget_to_local(pg.view, pt);
    *x = pt[0];
    y = pt[1] - pg_top();
    if (pg.level == L_EPS && pt[1] < PC_HDR_H) return pt[0] >= PG_HDR_TEXT_X && pt[1] >= PG_SPEED_Y && pt[1] < PG_SPEED_Y + PG_SPEED_H ? -2 : -1;   /* the speed, or the header */
    if (y < 0) return -1;
    y /= PC_ROW_H;
    return y < pg_count() ? y : -1;
}

static void pg_set_press(int p) {
    if (pg.press == p) return;
    pg.press = p;
    pg_redraw();
}

static int pg_on_down(void *ctx, void *e) {
    int a, x;
    (void)ctx;
    pg.down = 0;
    if (!e || !pg.view) return RET_OK;
    a = pg_item_of(e, &x);
    pg.down = a == -1 ? 0 : a == -2 ? -2 : a + 1;
    pg.down_x = I(e, PE_X), pg.down_y = I(e, PE_Y);
    if (a >= 0 && !(pg.level == L_EPS && x < PG_TEXT_X)) pg_set_press(a + 1);   /* (the dot column is its own button: no row fill) */
    return RET_OK;
}

static void pg_toggle(int a) {
    unsigned pos, len;
    int s = pc_state(pg.eps[a].hash, &pos, &len);
    if (!pg.eps[a].hash) return;
    pc_mark(pg.eps[a].hash, s != PC_DONE);
    pg.rev = pc_rev();
    grid_drop(&pg.g);
    pg_redraw();
}

static void pg_speed_cycle(void) {
    const pc_show_t *s = &pg.shows[pg.sel];
    int mode = (pc_speed_get(s->hash) + 1) % PC_SPEEDS;
    if (!pc_speed_set(s->hash, mode)) pod_toast(TR("Storage unavailable"));
    pg_header_texts();
    pc_speed_apply(s->hash);   /* an episode of this show that plays: the decoder takes it at the next start; the stock page shows it */
    pg_redraw();
}

static int pg_on_up(void *ctx, void *e) {
    int a = pg.down, x, same;
    (void)ctx;
    pg.down = 0;
    pg_set_press(0);
    if (!a || !e || !pg.view) return RET_OK;
    if (pg_abs(I(e, PE_X) - pg.down_x) >= PG_TAP_PX || pg_abs(I(e, PE_Y) - pg.down_y) >= PG_TAP_PX) return RET_OK;
    same = pg_item_of(e, &x);
    if (a == -2) {
        if (same == -2) pg_speed_cycle();
    } else if (same == a - 1) {
        if (pg.level == L_SHOWS) pg_open_show(same);
        else if (x < PG_TEXT_X) pg_toggle(same);
        else pg_play(same);
    }
    return RET_OK;
}

static int pg_on_abort(void *ctx, void *e) {
    (void)ctx; (void)e;
    pg.down = 0;
    pg_set_press(0);
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The timer and the window's events
 */
static int pg_tick(const void *timer) {
    (void)timer;
    if (!pg.win || !pg.fg) {
        pg.timer = 0;
        return RET_OK;
    }
    pc_note(cc_playing());
    if (pod_screen_lit() && pg.level == L_EPS && pc_rev() != pg.rev) {   /* a place or a mark changed: the grey lines are made again */
        pg.rev = pc_rev();
        grid_drop(&pg.g);
        pg_redraw();
    }
    return RET_REPEAT;
}

static void pg_arm(void) {
    if (!pg.timer) pg.timer = timer_add(pg_tick, (void *)0, PG_TICK_MS);
}

static int pg_on_fg(void *ctx, void *e) {
    (void)ctx; (void)e;
    pg.fg = 1;
    pg_arm();
    if (pg.level == L_EPS) {   /* the grey lines are made again: a place may have changed, and "4h ago" is a time later */
        pg.rev = pc_rev();
        grid_drop(&pg.g);
        pg_redraw();
    }
    pg_kick();
    return RET_OK;
}

static int pg_on_bg(void *ctx, void *e) {
    (void)ctx; (void)e;
    pg.fg = 0;
    if (pg.timer) timer_remove(pg.timer);
    if (pg.load_timer) timer_remove(pg.load_timer);
    pg.timer = pg.load_timer = 0;
    pg.down = 0;
    pg.press = 0;
    pc_flush();
    return RET_OK;
}

static int pg_on_destroy(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (pg.timer) timer_remove(pg.timer);
    if (pg.load_timer) timer_remove(pg.load_timer);
    pc_flush();
    grid_free(&pg.g);
    grid_free(&pg.hg);
    if (pg.dot) bitmap_destroy(pg.dot);
    free(pg.shows);
    free(pg.eps);
    memset(&pg, 0, sizeof pg);
    return RET_OK;
}

/* The Extras item Podcasts. 0 once the page is up, -1 if it could not open. */
int podcasts_open(void) {
    if (pg.win) return -1;
    memset(&pg, 0, sizeof pg);
    pg.win = window_open("m1plus_podcasts");
    if (!pg.win) return -1;
    widget_on(pg.win, EVT_DESTROY, pg_on_destroy, (void *)0);
    pod_bind(pg.win, "btn_return", pg_on_back, (void *)0);
    pod_bind(pg.win, "btn_backtoplayer", pod_on_player, (void *)0);
    pg.view = widget_lookup(pg.win, "view_grid", 1);
    pg.sv = widget_lookup(pg.win, "podcasts_scrollview", 1);
    pg.status = widget_lookup(pg.win, "label_status", 1);
    pg.title = widget_lookup(pg.win, "label_title", 1);
    pg.fade = widget_lookup(pg.win, "img_nb_fade", 1);
    pg.st_title = widget_lookup(pg.win, "label_row_title", 1);
    pg.st_sub = widget_lookup(pg.win, "label_row_sub", 1);
    pg.st_dim = widget_lookup(pg.win, "label_row_dim", 1);
    pg.st_acc = widget_lookup(pg.win, "label_row_acc", 1);
    if (!pg.view || !pg.sv || !pg.status || !pg.title || !pg.st_title || !pg.st_sub || !pg.st_dim || !pg.st_acc) {
        navigator_back();   /* an asset that is not ours */
        return -1;
    }
    label_set_line_wrap(pg.status, 1);
    pg.shows = calloc(PC_MAX_SHOWS, sizeof *pg.shows);
    if (!pg.shows || !grid_init(&pg.g, pg.win, PC_TILES, LIST_ART, LIST_R) || !grid_init(&pg.hg, pg.win, 1, PC_HDR_ART, 10)) {
        pg_empty("Not enough memory");
        return 0;
    }
    pg.g.st_title = pg.st_title, pg.g.st_sub = pg.st_sub;
    pc_root(pg.root);
    pg_make_dot();
    pg.fg = 1;
    pg.noscroll = !widget_on(pg.sv, EVT_SCROLL, pg_on_scroll, (void *)0) || !widget_on(pg.sv, EVT_SCROLL_END, pg_on_scroll, (void *)0);
    widget_on(pg.win, EVT_WINDOW_TO_FG, pg_on_fg, (void *)0);
    widget_on(pg.win, EVT_WINDOW_TO_BG, pg_on_bg, (void *)0);
    widget_on(pg.view, EVT_POINTER_DOWN, pg_on_down, (void *)0);
    widget_on(pg.view, EVT_POINTER_UP, pg_on_up, (void *)0);
    widget_on(pg.view, EVT_POINTER_ABORT, pg_on_abort, (void *)0);
    widget_on(pg.view, EVT_AFTER_PAINT, pg_on_paint, (void *)0);
    pg_arm();
    pg_load_shows();
    return 0;
}
