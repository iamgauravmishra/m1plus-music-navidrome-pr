/* M1+ Pod Albums: the library's albums as a grid of covers or as a list, two modes of one page.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * One page, ui/m1pod_albums.bin: the navbar (Back, "Albums", the mode toggle, Now Playing) over ONE custom
 * view, view_grid, that paints the albums itself in its own EVT_AFTER_PAINT, as Cover Flow paints its frame,
 * and takes its own pointer events. There is no widget per album: a library of any size costs the album deque
 * (the stock list, copied as Cover Flow copies it) and a small ring of decoded covers.
 *
 *   grid mode  GRID_COLS (2) columns of GRID_COVER (144) px covers, GRID_GAP px apart, a one-line album and a
 *              one-line artist under each (two text styles taken from the hidden labels label_grid_title and
 *              label_grid_sub); (patch/offsets.inc); row r starts GRID_ROW_GAP + r * PITCH px down the content.
 *   list mode  LIST_ROW_H px rows: a LIST_ART px cover, the album and the artist (two sizes and colours, taken
 *              from two hidden labels of the page, label_row_title and label_row_sub, with
 *              widget_prepare_text_style), a hairline under each row, the row under the finger filled LIST_PRESS.
 *   both       the content scrolls inside a GRID_VIEW_H view, clamped to [0, content - view]. Only what
 *              intersects the view is drawn: a cover with canvas_draw_image (clipped by hand to the view) and
 *              text with canvas_draw_text_in_rect, only when it lies wholly inside the view.
 *   tiles      GRID_TILES (12) entries. A tile is the album's cover reduced from the Cover Flow cache file (168 px,
 *              box filter) to the mode's cover size (the finished bitmap is kept, not the JPEG). PAINT NEVER DECODES:
 *              it draws the resident tiles and the placeholder for the rest. A page-owned timer (al_on_load, armed
 *              when the view moves or a mode starts, ended when nothing is left to load, removed with the page)
 *              decodes ONE cover per 16 ms tick: the missing cell nearest the middle of the view first (the cells in
 *              view before any other), then the next AL_AHEAD rows in the scroll direction. A tile in that window
 *              is never replaced; the rest of the ring (at least two tiles) is the history, least recently used
 *              replaced, so a reversal finds what it just left. Texts are converted to wide chars with the tile's
 *              record and cut to their width with an ellipsis (measured with the canvas' own font, in the text's own
 *              style) the first time they are drawn.
 *              Memory: GRID_TILES (12) bitmaps of at most GRID_COVER^2 * 4 (81 KB) plus one for the placeholder
 *              = 1.08 MB, whatever the library; a decode also holds the 168 px source (113 KB) for its duration.
 *   art        the cover cache (patch/covercache.c); a missing or empty cache file shows the stock placeholder disc
 *              (p_default). Missing files are built in the background by the shared worker (see "The background cache
 *              build" below); the tiles that found no file try again as the worker advances.
 *   touch      a vertical drag scrolls from AL_DRAG (5 px) of travel, counted from there so the content does not
 *              jump; within AL_SLOP (12 px) on both axes and without a drag a release is a tap. A release flings:
 *              the velocity decays per millisecond and the fling follows time_now_ms, so a late timer covers the
 *              same distance. A tap on a cell or row opens the stock album page as Cover Flow does (cc_open_album).
 *              Coordinates go through widget_to_local, so the page's offset on the screen does not matter.
 *
 * The mode toggle: the navbar button switches in place (no window opens or closes): the tiles are dropped, the
 * scroll keeps the first album in view, the button shows the glyph of the other mode, and the choice is persisted
 * (ALBUMS_FILE, written as the Start-in setting is). The menu's Albums row opens the page in the saved mode; if
 * the page cannot open it falls back to the stock Albums list through the Home dispatcher. No stock function is
 * hooked; everything runs from this page's widgets and timers.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "covercache.h"
#include "common.h"

extern int coverflow_open(void); /* patch/coverflow.c: the menu's Cover Flow row, opened over this page */
extern int pod_home_open(int id);/* patch/m1pod.c: a stock Home destination through the dispatcher */

#define CELL_H (GRID_COVER + GRID_TITLE_GAP + GRID_TITLE_H + GRID_SUB_H)
#define PITCH (CELL_H + GRID_ROW_GAP)   /* row to row */
#define COL_PITCH (GRID_COVER + GRID_GAP)
#define AL_MORE_MS 16                   /* the loader's and the fling's tick */
#define AL_TITLE 48                     /* wide chars kept per text, the NUL included */
#define AL_SLOP 12                      /* px: with no drag, a release within this on both axes is a tap */
#define AL_DRAG 5                       /* px of vertical travel that start a drag; the content follows from there */
#define AL_MAX_FLING (3 << 16)          /* Q16 px per ms (48 px per 16 ms tick, as before) */
#define AL_DECAY 248                    /* the fling loses 1/248 of its speed a ms: (247/248)^16 = 15/16 a 16 ms tick */
#define AL_FLING_MIN 2048               /* Q16 px per ms (1/32): below this it has stopped */
#define AL_AHEAD (al.list ? 2 : 1)      /* rows loaded beyond the view in the scroll direction */
#define PLACEHOLDER "p_default"         /* the stock 254 px disc, as Cover Flow's */
#define AL_GREY 0xff2b2b2bu
#define FIT_TITLE 1
#define FIT_ARTIST 2
/* the most cells a frame can touch: (view + cell) / pitch + 1 rows of GRID_COLS; the ring must hold them, the next
 * row in the scroll direction and leave two tiles of history */
#if GRID_TILES < GRID_COLS * ((GRID_VIEW_H + CELL_H) / PITCH + 2 + 1) + 2
#error GRID_TILES cannot hold the visible cells, the next row and the history
#endif
#if GRID_TILES < (GRID_VIEW_H / LIST_ROW_H) + 2 + 2 + 2
#error GRID_TILES cannot hold the visible rows, the next two and the history
#endif

typedef struct {
    int album;     /* album + 1; 0 = free */
    unsigned stamp;
    void *bmp;     /* the cover, side x side RGBA, once decoded */
    int art;       /* 0 not tried, 1 bmp is the cover, 2 no cache file / no picture: the placeholder */
    int fit;       /* FIT_*: which texts have been cut to their width */
    int tw, aw;    /* title / artist length, in wide chars */
    unsigned title[AL_TITLE], artist[AL_TITLE];
} tile_t;

static struct {
    void *win, *view, *status, *btn;
    void *st_title, *st_sub;      /* hidden labels whose styles are the list's two text styles */
    void *st_gtitle, *st_gsub;    /* and the grid's two */
    void *albums;                 /* our copy of the stock album rows */
    unsigned *order;              /* display order as stock row numbers (cc_album_order, Settings > Cover Flow > Sort); NULL = stock order */
    unsigned count;
    tile_t *tiles;                /* GRID_TILES, heap */
    void *placeholder;            /* bitmap of the disc */
    unsigned clock;
    int list;                     /* 1 list mode, 0 grid */
    int side;                     /* the mode's cover size */
    int press;                    /* list: the row under the finger, + 1 */
    int scroll;                   /* px down the content */
    int dir;                      /* the way the content last went: 1 down the list, -1 back up */
    /* touch: the finger is down; a drag has started (from origin); the greatest excursion on either axis; the press
     * stopped a fling; the scroll the press found; the last two samples for the release's velocity */
    int dragging, active, reach, stopped, down_x, down_y, origin, base, y0, t0, y1, t1;
    /* the fling: velocity (Q16 px per ms), the sub-pixel remainder (Q16), the time of the last tick */
    int fv, facc;
    unsigned fling_t;
    unsigned fling_timer, more_timer; /* more_timer: the loader's */
    /* the background cache build (the shared worker, patch/covercache.c): build_timer is the one-shot start, then the poll;
     * own = this page holds the worker's job set; seen = the worker's done counter at the last poll */
    unsigned build_timer;
    int own, seen;
} al __attribute__((section(".scratch")));

/* Hidden and out of the hit test together (this AWTK's widget_find_target ignores visible). */
static void al_show(void *w, int on) {
    if (!w) return;
    widget_set_visible(w, on, 0);
    widget_set_sensitive(w, on);
}

static int al_rows(void) { return ((int)al.count + GRID_COLS - 1) / GRID_COLS; }
static int al_content(void) {
    return al.list ? (int)al.count * LIST_ROW_H : al_rows() ? GRID_ROW_GAP + al_rows() * PITCH : 0;
}
static int al_max_scroll(void) {
    int m = al_content() - GRID_VIEW_H;
    return m > 0 ? m : 0;
}

/* The persisted mode: "1" the grid, "0" the list, anything else ALBUMS_DEFAULT_GRID. */
static int al_use_grid(void) {
    char c = 0;
    int fd = open(ALBUMS_FILE, O_RDONLY, 0), n;
    if (fd < 0) return ALBUMS_DEFAULT_GRID;
    n = read(fd, &c, 1);
    close(fd);
    return n == 1 && c == '1' ? 1 : n == 1 && c == '0' ? 0 : ALBUMS_DEFAULT_GRID;
}

/* ---------------------------------------------------------------------------
 * Tiles
 */
static void al_free_art(tile_t *t) {
    if (t->bmp) bitmap_destroy(t->bmp);
    t->bmp = (void *)0;
}

/* A side x side RGBA bitmap, opaque, its pixels locked in *px for the caller to fill (then
 * bitmap_unlock_buffer); NULL if it cannot be made. */
static void *al_bitmap(unsigned **px) {
    void *b = bitmap_create_ex(al.side, al.side, al.side * 4, BITMAP_RGBA8888);
    unsigned *d = b ? (unsigned *)bitmap_lock_buffer_for_write(b) : (unsigned *)0;
    if (b && (!d || bitmap_get_line_length(b) != (unsigned)al.side * 4)) {
        if (d) bitmap_unlock_buffer(b);
        bitmap_destroy(b);
        return (void *)0;
    }
    if (b) *(unsigned short *)((char *)b + BITMAP_FLAGS) |= 1; /* OPAQUE: every pixel is */
    *px = d;
    return b;
}

static int al_width(void *canvas, const unsigned *s, unsigned n) {
    float w = canvas_measure_text(canvas, s, n);
    return (int)(w + 0.999f);
}

/* The wide string s (NUL-terminated), cut with an ellipsis to maxw px: the longest prefix whose width with the
 * ellipsis fits (the widths grow with the prefix, so a binary search). The canvas has the text's style. Its length. */
static int al_fit(void *canvas, unsigned *s, int maxw) {
    unsigned len = 0, lo, hi;
    while (s[len]) len++;
    if (len && al_width(canvas, s, len) > maxw) {
        lo = 0, hi = len - 1; /* the prefix kept; the last char never fits with the ellipsis after it */
        while (lo < hi) {
            unsigned mid = (lo + hi + 1) / 2, keep = s[mid];
            s[mid] = ELLIPSIS;
            if (al_width(canvas, s, mid + 1) <= maxw) lo = mid;
            else hi = mid - 1;
            s[mid] = keep;
        }
        s[lo] = ELLIPSIS;
        s[lo + 1] = 0;
        len = lo + 1;
    }
    return (int)len;
}

static void al_wide(unsigned *dst, const char *s) {
    unsigned n = 0;
    while (s[n] && n < 255) n++;
    tk_utf8_to_utf16_ex(s, n, dst, AL_TITLE);
}

/* The first grid row that touches the view, or the row of scroll offset s. */
static int al_row_of(int s) {
    return s > GRID_ROW_GAP + CELL_H ? (s - GRID_ROW_GAP - CELL_H) / PITCH + 1 : 0;
}

/* The rows (grid rows, or list rows = albums) that touch the view: [*r0, *r1], r1 < 0 for none. */
static void al_span(int *r0, int *r1) {
    int n = al.list ? (int)al.count : al_rows();
    if (al.list) *r0 = al.scroll / LIST_ROW_H, *r1 = (al.scroll + GRID_VIEW_H - 1) / LIST_ROW_H;
    else *r0 = al_row_of(al.scroll), *r1 = (al.scroll + GRID_VIEW_H - GRID_ROW_GAP + PITCH - 1) / PITCH - 1;
    if (*r1 > n - 1) *r1 = n - 1;
}

/* The albums [*lo, *hi] the tiles are kept for: those in view and AL_AHEAD rows beyond them in the scroll direction. */
static void al_window(int *lo, int *hi) {
    int per = al.list ? 1 : GRID_COLS, n = al.list ? (int)al.count : al_rows(), r0, r1;
    al_span(&r0, &r1);
    if (al.dir < 0) r0 -= AL_AHEAD;
    else r1 += AL_AHEAD;
    if (r0 < 0) r0 = 0;
    if (r1 > n - 1) r1 = n - 1;
    *lo = r0 * per;
    *hi = (r1 + 1) * per - 1;
    if (*hi > (int)al.count - 1) *hi = (int)al.count - 1;
}

/* The tile that holds album a, or NULL. */
static tile_t *al_find(int a) {
    int i;
    for (i = 0; i < GRID_TILES; ++i)
        if (al.tiles[i].album == a + 1) return &al.tiles[i];
    return (tile_t *)0;
}

/* The tile of album a: the one it has, else a free one, else the least recently used one outside the window (the
 * window is never replaced: it holds the cells in view and the ones about to be). */
static tile_t *al_tile(int a) {
    tile_t *t = al.tiles, *victim = (tile_t *)0, *any = al.tiles;
    void *rec;
    int i, lo, hi;
    al_window(&lo, &hi);
    for (i = 0; i < GRID_TILES; ++i, ++t) {
        if (t->album == a + 1) {
            t->stamp = ++al.clock;
            return t;
        }
        if (!t->album) {
            if (!victim || victim->album) victim = t;
        } else {
            if (t->stamp < any->stamp || !any->album) any = t;
            if ((t->album - 1 < lo || t->album - 1 > hi) && (!victim || (victim->album && t->stamp < victim->stamp))) victim = t;
        }
    }
    t = victim ? victim : any;
    al_free_art(t);
    memset(t, 0, sizeof *t);
    t->album = a + 1;
    t->stamp = ++al.clock;
    rec = cc_row(al.albums, al.order, (unsigned)a);
    al_wide(t->title, cc_str(rec, REC_ALBUM));
    al_wide(t->artist, cc_str(rec, REC_ARTIST));
    return t;
}

/* The cover from the cache file, reduced to the mode's size with the box filter. */
static void al_art(tile_t *t, int a) {
    char url[80];
    const char *file = cc_url(url, cc_album_key(cc_row(al.albums, al.order, (unsigned)a)));
    unsigned *px;
    void *b;
    t->art = 2;
    if (!file || !(b = al_bitmap(&px))) return;
    if (cc_decode(al.win, file, 1, (unsigned)al.side, 1, px)) t->bmp = b, t->art = 1;
    bitmap_unlock_buffer(b);
    if (!t->bmp) bitmap_destroy(b);
}

/* The placeholder disc: the theme's stock image reduced like a cover, else flat grey. */
static void al_make_placeholder(void) {
    unsigned *px;
    int i;
    al.placeholder = al_bitmap(&px);
    if (!al.placeholder) return;
    for (i = 0; i < al.side * al.side; ++i) px[i] = AL_GREY;
    cc_decode(al.win, PLACEHOLDER, 0, (unsigned)al.side, 1, px);
    bitmap_unlock_buffer(al.placeholder);
}

/* Every tile and the placeholder dropped (the covers of the other mode are another size). */
static void al_drop_tiles(void) {
    int i;
    for (i = 0; al.tiles && i < GRID_TILES; ++i) al_free_art(&al.tiles[i]);
    if (al.tiles) memset(al.tiles, 0, GRID_TILES * sizeof(tile_t));
    if (al.placeholder) bitmap_destroy(al.placeholder);
    al.placeholder = (void *)0;
}

/* ---------------------------------------------------------------------------
 * Paint
 */

/* A cover of the mode's size at (x, y) (view coordinates), cut to the view by hand. */
static void al_blit(void *canvas, tile_t *t, int x, int y) {
    void *bmp = t->art == 1 ? t->bmp : al.placeholder;
    int top = y < 0 ? -y : 0, bottom = y + al.side > GRID_VIEW_H ? GRID_VIEW_H - y : al.side;
    int src[4], dst[4];
    if (!bmp || bottom <= top) return;
    src[0] = 0, src[1] = top, src[2] = al.side, src[3] = bottom - top;
    dst[0] = x, dst[1] = y + top, dst[2] = al.side, dst[3] = bottom - top;
    canvas_draw_image(canvas, bmp, src, dst);
}

/* The tile's album (pass 0) or artist (pass 1) in rect (x, y, w, h), cut to w with an ellipsis the first time (the
 * canvas has the text's style), and drawn only when it lies wholly inside the view. */
static void al_text(void *canvas, tile_t *t, int pass, int x, int y, int w, int h) {
    unsigned *s = pass ? t->artist : t->title;
    int *len = pass ? &t->aw : &t->tw, fit = pass ? FIT_ARTIST : FIT_TITLE;
    int rect[4];
    rect[0] = x, rect[1] = y, rect[2] = w, rect[3] = h;
    if (!(t->fit & fit)) *len = al_fit(canvas, s, w), t->fit |= fit;
    if (*len && y >= 0 && y + h <= GRID_VIEW_H) canvas_draw_text_in_rect(canvas, s, (unsigned)*len, rect);
}

static void al_paint_grid(void *canvas) {
    int r, r0, r1, c, pass;
    al_span(&r0, &r1);
    for (r = r0; r <= r1; ++r)
        for (c = 0; c < GRID_COLS && r * GRID_COLS + c < (int)al.count; ++c)
            al_blit(canvas, al_tile(r * GRID_COLS + c), GRID_MARGIN + c * COL_PITCH,
                    GRID_ROW_GAP + r * PITCH - al.scroll);
    for (pass = 0; pass < 2; ++pass) {   /* albums, then artists: one text style at a time */
        widget_prepare_text_style(pass ? al.st_gsub : al.st_gtitle, canvas);
        for (r = r0; r <= r1; ++r)
            for (c = 0; c < GRID_COLS && r * GRID_COLS + c < (int)al.count; ++c)
                al_text(canvas, al_tile(r * GRID_COLS + c), pass, GRID_MARGIN + c * COL_PITCH,
                        GRID_ROW_GAP + r * PITCH - al.scroll + GRID_COVER + GRID_TITLE_GAP + (pass ? GRID_TITLE_H : 0),
                        GRID_COVER, pass ? GRID_SUB_H : GRID_TITLE_H);
    }
}

/* Fills the rows [y0, y1) of the view with colour c (cut to the view by hand: the canvas does not clip to it). */
static void al_fill(void *canvas, int y0, int y1, unsigned c) {
    if (y0 < 0) y0 = 0;
    if (y1 > GRID_VIEW_H) y1 = GRID_VIEW_H;
    if (y1 <= y0) return;
    canvas_set_fill_color(canvas, c);
    canvas_fill_rect(canvas, 0, y0, 320, y1 - y0);
}

/* A list row whose top is at y: the pressed fill, the cover, the hairline. */
static void al_row(void *canvas, tile_t *t, int y) {
    if (al.press == t->album) al_fill(canvas, y, y + LIST_ROW_H - 1, LIST_PRESS);
    al_blit(canvas, t, LIST_ART_X, y + LIST_ART_Y);
    al_fill(canvas, y + LIST_ROW_H - 1, y + LIST_ROW_H, LIST_HAIR);
}

static void al_paint_list(void *canvas) {
    int r0, r1, r, pass;
    al_span(&r0, &r1);
    for (r = r0; r <= r1; ++r) al_row(canvas, al_tile(r), r * LIST_ROW_H - al.scroll);
    for (pass = 0; pass < 2; ++pass) {   /* titles, then artists: one text style at a time */
        widget_prepare_text_style(pass ? al.st_sub : al.st_title, canvas);
        for (r = r0; r <= r1; ++r)
            al_text(canvas, al_tile(r), pass, LIST_TEXT_X, r * LIST_ROW_H - al.scroll + (pass ? LIST_SUB_Y : LIST_TITLE_Y),
                    LIST_TEXT_W, pass ? LIST_SUB_H : LIST_TITLE_H);
    }
}

/* The view's own EVT_AFTER_PAINT (over its black background): the visible cells or rows and nothing else. It draws
 * what is resident and the placeholder for the rest; it decodes nothing and arms no timer (al_on_load does that). */
static int al_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    (void)ctx;
    if (!canvas || !al.view || !al.tiles || !al.count) return RET_OK;
    if (al.list) al_paint_list(canvas);
    else al_paint_grid(canvas);
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The loader: one cover per tick on the page's own timer
 */
static int al_abs(int v) { return v < 0 ? -v : v; }

/* The album to decode next, or -1: of the window's albums without a tile that was tried, the cell nearest the middle
 * of the view, the cells in view before the rest (the window is the view and the rows ahead). */
static int al_next_load(void) {
    int lo, hi, a, best = -1, bd = 0x7fffffff;
    if (!al.tiles || !al.count) return -1;
    al_window(&lo, &hi);
    for (a = lo; a <= hi; ++a) {
        tile_t *t = al_find(a);
        int top, h, d;
        if (t && t->art) continue;
        if (al.list) top = a * LIST_ROW_H - al.scroll, h = LIST_ROW_H;
        else top = GRID_ROW_GAP + a / GRID_COLS * PITCH - al.scroll, h = CELL_H;
        d = al_abs(top + h / 2 - GRID_VIEW_H / 2);
        if (top >= GRID_VIEW_H || top + h <= 0) d += 100000; /* ahead of the view */
        if (d < bd) bd = d, best = a;
    }
    return best;
}

static int al_on_load(const void *unused);
static int al_first(void);

/* Arms the loader if there is something to load and it is not running. */
static void al_kick(void) {
    if (!al.more_timer && al.view && al_next_load() >= 0) al.more_timer = timer_add(al_on_load, (void *)0, AL_MORE_MS);
}

static int al_on_load(const void *unused) {
    int a;
    (void)unused;
    al.more_timer = 0;
    if (!al.view) return RET_OK;
    a = al_next_load();
    if (a >= 0) {
        tile_t *t = al_tile(a);
        int top = al.list ? a * LIST_ROW_H - al.scroll : GRID_ROW_GAP + a / GRID_COLS * PITCH - al.scroll;
        al_art(t, a);
        if (top < GRID_VIEW_H && top + (al.list ? LIST_ROW_H : CELL_H) > 0) widget_invalidate_force(al.view, (void *)0);
    }
    al_kick();
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The background cache build. Albums with no cache file (neither a picture nor the "no art" marker) are built by the
 * shared worker thread (patch/covercache.c) while the page is up: no Preparing screen, the grid shows the placeholder
 * disc until a cover's file appears. The jobs are the albums nearest the first one in view first. A one-shot timer
 * starts it a moment after the page is up (the scan stats every album's file, so it is not part of opening); a poll
 * every AL_BUILD_MS then watches the worker's done counter and, when it advanced, lets the tiles that found no file try
 * again (al_retry); the loader (al_kick) decodes them one per tick as before. One worker at a time app-wide: when
 * Cover Flow (or another page) holds it, nothing is started. Cancelled and joined when the page goes (or Cover Flow opens).
 */
#define AL_BUILD_START_MS 50
#define AL_BUILD_MS 500

/* The tiles that were shown as the placeholder for want of a cache file, and whose file exists now, try again. */
static void al_retry(void) {
    char url[80];
    int i, any = 0;
    for (i = 0; al.tiles && i < GRID_TILES; ++i) {
        tile_t *t = &al.tiles[i];
        if (t->album && t->art == 2 && cc_url(url, cc_album_key(cc_row(al.albums, al.order, (unsigned)t->album - 1)))) t->art = 0, any = 1;
    }
    if (any) al_kick();
}

/* The page's build set released: a running worker is cancelled and joined (bounded by one album's art). */
static void al_build_end(void) {
    if (al.build_timer) timer_remove(al.build_timer);
    al.build_timer = 0;
    if (al.own) cc_build_stop();
    al.own = 0;
}

static int al_on_build(const void *unused) {
    int done;
    (void)unused;
    al.build_timer = 0;
    if (!al.view || !al.own) return RET_OK;
    done = cc_build_done();
    if (done != al.seen) al.seen = done, al_retry();
    if (done >= cc_build_total()) {
        al_build_end();
        return RET_OK;
    }
    al.build_timer = timer_add(al_on_build, (void *)0, AL_BUILD_MS);
    if (!al.build_timer) al_build_end(); /* no way to watch it: stop, the covers built so far stay */
    return RET_OK;
}

static int al_on_build_start(const void *unused) {
    (void)unused;
    al.build_timer = 0;
    if (!al.view || !al.count || al.own || !cc_build_open(al.count, CC_MISSING)) return RET_OK;
    al.own = 1;
    cc_build_near(al.albums, al.order, (unsigned)al_first());
    if (!cc_build_start()) { /* nothing missing, no card, no space, no thread: the set is already freed */
        al.own = 0;
        return RET_OK;
    }
    al.seen = 0;
    al.build_timer = timer_add(al_on_build, (void *)0, AL_BUILD_MS);
    if (!al.build_timer) al_build_end();
    return RET_OK;
}

/* Starts the build a moment from now unless one is going or already due. */
static void al_build_later(void) {
    if (al.view && al.tiles && !al.own && !al.build_timer) al.build_timer = timer_add(al_on_build_start, (void *)0, AL_BUILD_START_MS);
}

static int al_on_fg(void *ctx, void *e) {
    (void)ctx; (void)e;
    al_build_later();
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * Touch
 */
static int al_clamp(int v) {
    int max = al_max_scroll();
    return v < 0 ? 0 : v > max ? max : v;
}

static void al_scroll_to(int v) {
    v = al_clamp(v);
    if (v == al.scroll) return;
    al.dir = v > al.scroll ? 1 : -1;
    al.scroll = v;
    widget_invalidate_force(al.view, (void *)0);
    al_kick();
}

static void al_fling_stop(void) {
    if (al.fling_timer) timer_remove(al.fling_timer);
    al.fling_timer = 0;
    al.fv = al.facc = 0;
}

/* The fling follows the clock: the speed loses 1/AL_DECAY of itself every millisecond that passed since the last
 * tick (the same steps however the ticks fall), the distance is kept to 1/65536 px, and the content stops exactly at
 * an end. */
static int al_on_fling(const void *unused) {
    unsigned now = (unsigned)time_now_ms();
    int ms = (int)(now - al.fling_t), want, got;
    (void)unused;
    al.fling_timer = 0;
    if (!al.view) return RET_OK;
    if (ms < 0) ms = 0;
    al.fling_t = now;
    for (; ms > 0 && al.fv; --ms) {
        al.facc += al.fv;
        al.fv -= al.fv / AL_DECAY;
        if (al.fv < AL_FLING_MIN && al.fv > -AL_FLING_MIN) al.fv = 0;
    }
    want = al.scroll + (al.facc >> 16);
    al.facc &= 0xffff;
    got = al_clamp(want);
    al_scroll_to(got);
    if (got != want) al.fv = 0;            /* at an end: it stops there */
    if (al.fv) al.fling_timer = timer_add(al_on_fling, (void *)0, AL_MORE_MS);
    if (!al.fling_timer) al.fv = al.facc = 0;
    return RET_OK;
}

/* The grid album under view point (x, y), or -1 for a gap, the margins and the empty tail of the last row. */
static int al_cell_at(int x, int y) {
    int cy = y + al.scroll - GRID_ROW_GAP, cx = x - GRID_MARGIN, row, col, a;
    if (y < 0 || y >= GRID_VIEW_H || cy < 0 || cx < 0) return -1;
    row = cy / PITCH, col = cx / COL_PITCH;
    if (cy % PITCH >= CELL_H || cx % COL_PITCH >= GRID_COVER || col >= GRID_COLS) return -1;
    a = row * GRID_COLS + col;
    return a < (int)al.count ? a : -1;
}

/* The list album under view point y, or -1 below the last row. */
static int al_row_at(int y) {
    int a;
    if (y < 0 || y >= GRID_VIEW_H) return -1;
    a = (y + al.scroll) / LIST_ROW_H;
    return a < (int)al.count ? a : -1;
}

static int al_item_at(int x, int y) { return al.list ? al_row_at(y) : al_cell_at(x, y); }

static int al_pe(void *e, int field) { return *(int *)((char *)e + field); }

static void al_set_press(int p) {
    if (al.press == p) return;
    al.press = p;
    widget_invalidate_force(al.view, (void *)0);
}

static int al_on_pointer(void *ctx, void *e) {
    int type, pt[2], x, y;
    (void)ctx;
    if (!e || !al.view) return RET_OK;
    type = al_pe(e, 0);
    pt[0] = al_pe(e, PE_X), pt[1] = al_pe(e, PE_Y);
    widget_to_local(al.view, pt); /* screen to view: the window sits under the 30 px status bar */
    x = pt[0], y = pt[1];
    if (type == EVT_POINTER_DOWN) {
        al.stopped = al.fling_timer != 0;   /* this press stops a coasting fling: its release is not a tap */
        al_fling_stop();
        al.dragging = 1, al.active = 0, al.reach = 0;
        al.down_x = x, al.down_y = al.y0 = al.y1 = y, al.base = al.scroll;
        al.t0 = al.t1 = al_pe(e, EV_TIME);
        widget_grab(al.win, al.view); /* moves and the release come here wherever they go */
        if (al.list && !al.stopped) al_set_press(al_row_at(y) + 1);
    } else if ((type == EVT_POINTER_MOVE || type == EVT_POINTER_UP) && al.dragging) {
        /* a release is a position too: the last events of a gesture can be sparse. The excursion counts on both axes
         * (tap or not); the drag starts at AL_DRAG px of vertical travel and counts from there, so it does not jump. */
        int dx = x - al.down_x, dy = y - al.down_y;
        if (al_abs(dx) > al.reach) al.reach = al_abs(dx);
        if (al_abs(dy) > al.reach) al.reach = al_abs(dy);
        if (!al.active && al_abs(dy) >= AL_DRAG) al.active = 1, al.origin = al.down_y + (dy > 0 ? AL_DRAG : -AL_DRAG);
        if (al.active || al.reach > AL_SLOP) al_set_press(0);
        if (al.active) al_scroll_to(al.base - (y - al.origin));
        if (type == EVT_POINTER_MOVE) {
            al.y0 = al.y1, al.t0 = al.t1, al.y1 = y, al.t1 = al_pe(e, EV_TIME);
        } else {
            int dt = al_pe(e, EV_TIME) - al.t0, v;
            al.dragging = 0;
            widget_ungrab(al.win, al.view);
            al_set_press(0);
            if (!al.active && al.reach <= AL_SLOP) {
                int a = al.stopped ? -1 : al_item_at(al.down_x, al.down_y);
                if (a >= 0 && a == al_item_at(x, y)) cc_open_album((void *)0, (int)(al.order ? al.order[a] : (unsigned)a)); /* the stock row */
            } else if (al.active && dt > 0 && dt < 200) {
                v = -(y - al.y0) * 65536 / dt;     /* Q16 px per ms */
                al.fv = v > AL_MAX_FLING ? AL_MAX_FLING : v < -AL_MAX_FLING ? -AL_MAX_FLING : v;
                al.facc = 0, al.fling_t = (unsigned)time_now_ms();
                if (al.fv) al.fling_timer = timer_add(al_on_fling, (void *)0, AL_MORE_MS);
                if (!al.fling_timer) al.fv = 0;
            }
        }
    } else if (type == EVT_POINTER_ABORT && al.dragging) {
        al.dragging = 0;
        widget_ungrab(al.win, al.view);
        al_set_press(0);
    }
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The page and the toggle
 */
/* The navbar's Cover Flow button: the same open as the menu's row (the playing album, else the last), over this
 * page, so Back returns here. */
static int al_on_cover(void *ctx, void *e) {
    (void)ctx; (void)e;
    al_build_end();   /* one worker at a time: Cover Flow builds what is missing itself, with its Preparing screen */
    coverflow_open();
    return RET_OK;
}

static int al_on_destroy(void *ctx, void *e) {
    (void)ctx; (void)e;
    al_fling_stop();
    if (al.more_timer) timer_remove(al.more_timer);
    al_build_end();   /* the timer removed, the worker cancelled and joined */
    if (al.dragging) widget_ungrab(al.win, al.view);
    al_drop_tiles();
    free(al.tiles);
    if (al.albums) deque_destroy(al.albums);
    free(al.order);
    memset(&al, 0, sizeof al);
    return RET_OK;
}

/* The toggle shows the glyph of the mode a tap switches to. */
static void al_glyph(void) {
    const char *icon = al.list ? "pod_nav_grid" : "pod_nav_list";
    if (!al.btn) return;
    widget_set_prop_str(al.btn, "style:normal:icon", icon);
    widget_set_prop_str(al.btn, "style:over:icon", icon);
    widget_set_prop_str(al.btn, "style:pressed:icon", al.list ? "pod_nav_grid_down" : "pod_nav_list_down");
}

/* The first album in view: its row's first album in the grid, the top row in the list. */
static int al_first(void) {
    if (al.list) return al.scroll / LIST_ROW_H;
    return al_row_of(al.scroll) * GRID_COLS;
}

/* Switches the mode in place: nothing opens or closes. The first album in view stays at the top. */
static void al_set_mode(int list) {
    int first = al_first();
    al_fling_stop();
    if (al.more_timer) timer_remove(al.more_timer);
    al.more_timer = 0;
    al.list = list, al.side = list ? LIST_ART : GRID_COVER, al.press = 0, al.dir = 1;
    al_drop_tiles();
    if (al.tiles) al_make_placeholder();
    al.scroll = 0;
    al.scroll = al_clamp(list ? first * LIST_ROW_H : first / GRID_COLS * PITCH);
    al_glyph();
    widget_invalidate_force(al.view, (void *)0);
    al_kick();
}

/* The navbar toggle: the other mode, in place, and the choice saved. */
static int al_on_toggle(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (!al.view) return RET_OK;
    al_set_mode(!al.list);
    home_write_atomic(ALBUMS_FILE, ALBUMS_TMP, al.list ? "0\n" : "1\n");
    return RET_OK;
}

/* The page in the given mode. 0 once it is up, -1 if the window could not open, -2 if the asset is not ours (the
 * page is left again). */
static int al_open(int list) {
    if (al.win) return -1;
    memset(&al, 0, sizeof al);
    al.win = window_open("m1pod_albums");
    if (!al.win) return -1;
    al.list = list, al.side = list ? LIST_ART : GRID_COVER;
    widget_on(al.win, EVT_DESTROY, al_on_destroy, (void *)0);
    pod_bind(al.win, "btn_return", pod_on_back, (void *)0);
    pod_bind(al.win, "btn_backtoplayer", pod_on_player, (void *)0);
    pod_bind(al.win, "btn_albumview", al_on_toggle, (void *)0);
    pod_bind(al.win, "btn_coverflow", al_on_cover, (void *)0);
    al.btn = widget_lookup(al.win, "btn_albumview", 1);
    al.view = widget_lookup(al.win, "view_grid", 1);
    al.status = widget_lookup(al.win, "label_status", 1);
    al.st_title = widget_lookup(al.win, "label_row_title", 1);
    al.st_sub = widget_lookup(al.win, "label_row_sub", 1);
    al.st_gtitle = widget_lookup(al.win, "label_grid_title", 1);
    al.st_gsub = widget_lookup(al.win, "label_grid_sub", 1);
    if (!al.view || !al.status || !al.st_title || !al.st_sub || !al.st_gtitle || !al.st_gsub) {
        navigator_back(); /* an asset that is not ours */
        return -2;
    }
    al_glyph();
    al_show(al.status, 0);
    al.albums = cc_albums();
    al.count = al.albums ? deque_size(al.albums) : 0;
    al.order = cc_album_order(al.albums);
    al.tiles = al.count ? calloc(GRID_TILES, sizeof(tile_t)) : (tile_t *)0;
    if (!al.tiles) {
        al_show(al.view, 0);
        al_show(al.status, 1);
        widget_set_tr_text(al.status, al.count ? "Not enough memory" : "Update Local Music first");
        return 0;
    }
    al_make_placeholder();
    al.dir = 1;
    al_kick();
    al_build_later();
    widget_on(al.win, EVT_WINDOW_TO_FG, al_on_fg, (void *)0);   /* back in front (from Cover Flow, an album): build what is still missing */
    widget_on(al.view, EVT_POINTER_DOWN, al_on_pointer, (void *)0);
    widget_on(al.view, EVT_POINTER_MOVE, al_on_pointer, (void *)0);
    widget_on(al.view, EVT_POINTER_UP, al_on_pointer, (void *)0);
    widget_on(al.view, EVT_POINTER_ABORT, al_on_pointer, (void *)0);
    widget_on(al.view, EVT_AFTER_PAINT, al_on_paint, (void *)0);
    return 0;
}

/* The M1+ Pod menu's Albums row: the mode used last (the grid on a first use). A window that will not open leaves
 * the stock Albums list, through the Home dispatcher. 0 once something is requested. */
int albums_open(void) {
    int r = al_open(!al_use_grid());
    if (r == -1 && !al.win) return pod_home_open(HOME_ALBUM);
    return r;
}
