/* M1 Pod Albums: the library's albums as a grid of covers or as a list, two modes of one page.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * One page, ui/m1pod_albums.bin: the navbar (Back, "Albums", the mode toggle, Now Playing) over ONE custom
 * view, view_grid, that paints the albums itself in its own EVT_AFTER_PAINT, as Cover Flow paints its frame,
 * and takes its own pointer events. There is no widget per album: a library of any size costs the album deque
 * (the stock list, copied as Cover Flow copies it) and a small ring of decoded covers.
 *
 *   grid mode  GRID_COLS columns of GRID_COVER px covers, GRID_GAP px apart, a one-line title under each
 *              (patch/offsets.inc); row r starts GRID_GAP + r * GRID_PITCH px down the content.
 *   list mode  LIST_ROW_H px rows: a LIST_ART px cover, the album and the artist (two sizes and colours, taken
 *              from two hidden labels of the page, label_row_title and label_row_sub, with
 *              widget_prepare_text_style), a hairline under each row, the row under the finger filled LIST_PRESS.
 *   both       the content scrolls inside a GRID_VIEW_H view, clamped to [0, content - view]. Only what
 *              intersects the view is drawn: a cover with canvas_draw_image (clipped by hand to the view) and
 *              text with canvas_draw_text_in_rect, only when it lies wholly inside the view.
 *   tiles      GRID_TILES entries, least recently drawn replaced. A tile is the album's cover reduced from the
 *              Cover Flow cache file (168 px, box filter) to the mode's cover size, decoded the first time its
 *              cell shows, at most AL_LOADS per frame (a fling shows placeholders and fills in on a 16 ms
 *              timer); its texts are converted to wide chars, and cut to their width with an ellipsis (measured
 *              with the canvas' own font, in the text's own style) the first time they are drawn.
 *              Memory: GRID_TILES bitmaps of at most GRID_COVER^2 * 4 (34 KB) plus one for the placeholder.
 *   art        only what Cover Flow already cached (patch/covercache.c); a missing or empty cache file shows the
 *              stock placeholder disc (p_default), and nothing here builds the cache.
 *   touch      a vertical drag scrolls (12 px slop), a release flings (a 16 ms timer, velocity decaying by
 *              1/16 a tick), a tap on a cell or row opens the stock album page as Cover Flow does (cc_open_album).
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

extern int pod_home_open(int id); /* patch/m1pod.c: a stock Home destination through the dispatcher */

#define O_RDONLY 0
#define CELL_H (GRID_COVER + GRID_TITLE_GAP + GRID_TITLE_H)
#define PITCH (CELL_H + GRID_GAP)       /* row to row */
#define COL_PITCH (GRID_COVER + GRID_GAP)
#define AL_LOADS 2                      /* covers decoded per frame */
#define AL_MORE_MS 16
#define AL_TITLE 48                     /* wide chars kept per text, the NUL included */
#define AL_SLOP 12                      /* px: within this a release is a tap */
#define AL_MAX_FLING 48                 /* px per tick */
#define PLACEHOLDER "p_default"         /* the stock 254 px disc, as Cover Flow's */
#define ELLIPSIS 0x2026
#define AL_GREY 0xff2b2b2bu
#define FIT_TITLE 1
#define FIT_ARTIST 2
/* the most cells a frame can touch: (view + cell) / pitch + 1 rows of GRID_COLS; the ring must hold them all */
#if GRID_TILES < GRID_COLS * ((GRID_VIEW_H + CELL_H) / PITCH + 2)
#error GRID_TILES cannot hold the visible cells
#endif
#if GRID_TILES < (GRID_VIEW_H / LIST_ROW_H) + 2
#error GRID_TILES cannot hold the visible rows
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
    int dragging, moved, stopped, down_x, down_y, base, y0, t0, y1, t1, fling;
    unsigned fling_timer, more_timer;
} al __attribute__((section(".scratch")));

/* Hidden and out of the hit test together (this AWTK's widget_find_target ignores visible). */
static void al_show(void *w, int on) {
    if (!w) return;
    widget_set_visible(w, on, 0);
    widget_set_sensitive(w, on);
}

static int al_rows(void) { return ((int)al.count + GRID_COLS - 1) / GRID_COLS; }
static int al_content(void) {
    return al.list ? (int)al.count * LIST_ROW_H : al_rows() ? GRID_GAP + al_rows() * PITCH : 0;
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

/* The tile of album a: the one it has, else the least recently used one made over. */
static tile_t *al_tile(int a) {
    tile_t *t = al.tiles, *victim = al.tiles;
    void *rec;
    int i;
    for (i = 0; i < GRID_TILES; ++i, ++t) {
        if (t->album == a + 1) {
            t->stamp = ++al.clock;
            return t;
        }
        if (!t->album || (victim->album && t->stamp < victim->stamp)) victim = t;
    }
    t = victim;
    al_free_art(t);
    memset(t, 0, sizeof *t);
    t->album = a + 1;
    t->stamp = ++al.clock;
    rec = cc_row(al.albums, al.order, (unsigned)a);
    al_wide(t->title, cc_str(rec, REC_ALBUM));
    if (al.list) al_wide(t->artist, cc_str(rec, REC_ARTIST));
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
static int al_on_more(const void *unused) {
    (void)unused;
    al.more_timer = 0;
    if (al.view) widget_invalidate_force(al.view, (void *)0);
    return RET_OK;
}

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

/* The tile of album a with its cover decoded if there is budget left this frame (*loads), else *pending. */
static tile_t *al_ready(int a, int *loads, int *pending) {
    tile_t *t = al_tile(a);
    if (!t->art) {
        if (*loads < AL_LOADS) ++*loads, al_art(t, a);
        else *pending = 1;
    }
    return t;
}

/* Grid cell with its cover's top at y. The title is drawn only when it lies wholly inside the view. */
static void al_cell(void *canvas, tile_t *t, int x, int y) {
    int title[4];
    al_blit(canvas, t, x, y);
    title[0] = x, title[1] = y + GRID_COVER + GRID_TITLE_GAP, title[2] = GRID_COVER, title[3] = GRID_TITLE_H;
    if (!(t->fit & FIT_TITLE)) t->tw = al_fit(canvas, t->title, GRID_COVER), t->fit |= FIT_TITLE;
    if (t->tw && title[1] >= 0 && title[1] + GRID_TITLE_H <= GRID_VIEW_H)
        canvas_draw_text_in_rect(canvas, t->title, (unsigned)t->tw, title);
}

static int al_paint_grid(void *canvas) {
    int rows = al_rows(), r, r0, r1, loads = 0, pending = 0;
    widget_prepare_text_style(al.view, canvas);   /* 16 px white, left, middle: the view's style */
    r0 = al.scroll > GRID_GAP + CELL_H ? (al.scroll - GRID_GAP - CELL_H) / PITCH + 1 : 0;
    r1 = (al.scroll + GRID_VIEW_H - GRID_GAP + PITCH - 1) / PITCH - 1;
    if (r1 > rows - 1) r1 = rows - 1;
    for (r = r0; r <= r1; ++r) {
        int c, y = GRID_GAP + r * PITCH - al.scroll;
        for (c = 0; c < GRID_COLS && r * GRID_COLS + c < (int)al.count; ++c) {
            int a = r * GRID_COLS + c;
            al_cell(canvas, al_ready(a, &loads, &pending), GRID_MARGIN + c * COL_PITCH, y);
        }
    }
    return pending;
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

static int al_paint_list(void *canvas) {
    int r0 = al.scroll / LIST_ROW_H, r1 = (al.scroll + GRID_VIEW_H - 1) / LIST_ROW_H, r, pass, loads = 0, pending = 0;
    if (r1 > (int)al.count - 1) r1 = (int)al.count - 1;
    for (r = r0; r <= r1; ++r) al_row(canvas, al_ready(r, &loads, &pending), r * LIST_ROW_H - al.scroll);
    for (pass = 0; pass < 2; ++pass) {   /* titles, then artists: one text style at a time */
        widget_prepare_text_style(pass ? al.st_sub : al.st_title, canvas);
        for (r = r0; r <= r1; ++r) {
            tile_t *t = al_tile(r);
            unsigned *s = pass ? t->artist : t->title;
            int *len = pass ? &t->aw : &t->tw, fit = pass ? FIT_ARTIST : FIT_TITLE;
            int rect[4];
            rect[0] = LIST_TEXT_X, rect[2] = LIST_TEXT_W;
            rect[1] = r * LIST_ROW_H - al.scroll + (pass ? LIST_SUB_Y : LIST_TITLE_Y);
            rect[3] = pass ? LIST_SUB_H : LIST_TITLE_H;
            if (!(t->fit & fit)) *len = al_fit(canvas, s, LIST_TEXT_W), t->fit |= fit;
            if (*len && rect[1] >= 0 && rect[1] + rect[3] <= GRID_VIEW_H)
                canvas_draw_text_in_rect(canvas, s, (unsigned)*len, rect);
        }
    }
    return pending;
}

/* The view's own EVT_AFTER_PAINT (over its black background): the visible cells or rows and nothing else. */
static int al_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int pending;
    (void)ctx;
    if (!canvas || !al.view || !al.tiles || !al.count) return RET_OK;
    pending = al.list ? al_paint_list(canvas) : al_paint_grid(canvas);
    if (pending && !al.more_timer) al.more_timer = timer_add(al_on_more, (void *)0, AL_MORE_MS);
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
    al.scroll = v;
    widget_invalidate_force(al.view, (void *)0);
}

static void al_fling_stop(void) {
    if (al.fling_timer) timer_remove(al.fling_timer);
    al.fling_timer = 0;
}

static int al_on_fling(const void *unused) {
    int before;
    (void)unused;
    al.fling_timer = 0;
    if (!al.view) return RET_OK;
    before = al.scroll;
    al_scroll_to(al.scroll + al.fling);
    al.fling = al.fling * 15 / 16;
    if (al.scroll != before && al.fling) al.fling_timer = timer_add(al_on_fling, (void *)0, AL_MORE_MS);
    return RET_OK;
}

/* The grid album under view point (x, y), or -1 for a gap, the margins and the empty tail of the last row. */
static int al_cell_at(int x, int y) {
    int cy = y + al.scroll - GRID_GAP, cx = x - GRID_MARGIN, row, col, a;
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
        al.dragging = 1, al.moved = 0;
        al.down_x = x, al.down_y = al.y0 = al.y1 = y, al.base = al.scroll;
        al.t0 = al.t1 = al_pe(e, EV_TIME);
        widget_grab(al.win, al.view); /* moves and the release come here wherever they go */
        if (al.list && !al.stopped) al_set_press(al_row_at(y) + 1);
    } else if ((type == EVT_POINTER_MOVE || type == EVT_POINTER_UP) && al.dragging) {
        /* a release is a position too: the last events of a gesture can be sparse. The excursion counts on both axes. */
        int dx = x - al.down_x, dy = y - al.down_y;
        if (dx > AL_SLOP || dx < -AL_SLOP || dy > AL_SLOP || dy < -AL_SLOP) al.moved = 1;
        if (al.moved) al_set_press(0), al_scroll_to(al.base - dy);
        if (type == EVT_POINTER_MOVE) {
            al.y0 = al.y1, al.t0 = al.t1, al.y1 = y, al.t1 = al_pe(e, EV_TIME);
        } else {
            int dt = al_pe(e, EV_TIME) - al.t0, v;
            al.dragging = 0;
            widget_ungrab(al.win, al.view);
            al_set_press(0);
            if (!al.moved) {
                int a = al.stopped ? -1 : al_item_at(al.down_x, al.down_y);
                if (a >= 0 && a == al_item_at(x, y)) cc_open_album((void *)0, (int)(al.order ? al.order[a] : (unsigned)a)); /* the stock row */
            } else if (dt > 0 && dt < 200) {
                v = -(y - al.y0) * AL_MORE_MS / dt;
                al.fling = v > AL_MAX_FLING ? AL_MAX_FLING : v < -AL_MAX_FLING ? -AL_MAX_FLING : v;
                if (al.fling) al.fling_timer = timer_add(al_on_fling, (void *)0, AL_MORE_MS);
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
static int al_on_back(void *ctx, void *e) {
    (void)ctx; (void)e;
    navigator_back();
    return RET_OK;
}

static int al_on_player(void *ctx, void *e) {
    (void)ctx; (void)e;
    on_backtoplayer_onclick((void *)0, (void *)0);
    return RET_OK;
}

static int al_on_destroy(void *ctx, void *e) {
    (void)ctx; (void)e;
    al_fling_stop();
    if (al.more_timer) timer_remove(al.more_timer);
    if (al.dragging) widget_ungrab(al.win, al.view);
    al_drop_tiles();
    free(al.tiles);
    if (al.albums) deque_destroy(al.albums);
    free(al.order);
    memset(&al, 0, sizeof al);
    return RET_OK;
}

static void al_bind(const char *name, int (*fn)(void *, void *)) {
    void *w = widget_lookup(al.win, name, 1);
    if (w) widget_on(w, EVT_CLICK, fn, (void *)0);
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
    int r;
    if (al.list) return al.scroll / LIST_ROW_H;
    r = al.scroll > GRID_GAP + CELL_H ? (al.scroll - GRID_GAP - CELL_H) / PITCH + 1 : 0;
    return r * GRID_COLS;
}

/* Switches the mode in place: nothing opens or closes. The first album in view stays at the top. */
static void al_set_mode(int list) {
    int first = al_first();
    al_fling_stop();
    if (al.more_timer) timer_remove(al.more_timer);
    al.more_timer = 0;
    al.list = list, al.side = list ? LIST_ART : GRID_COVER, al.press = 0;
    al_drop_tiles();
    if (al.tiles) al_make_placeholder();
    al.scroll = 0;
    al.scroll = al_clamp(list ? first * LIST_ROW_H : first / GRID_COLS * PITCH);
    al_glyph();
    widget_invalidate_force(al.view, (void *)0);
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
    al_bind("btn_return", al_on_back);
    al_bind("btn_backtoplayer", al_on_player);
    al_bind("btn_albumview", al_on_toggle);
    al.btn = widget_lookup(al.win, "btn_albumview", 1);
    al.view = widget_lookup(al.win, "view_grid", 1);
    al.status = widget_lookup(al.win, "label_status", 1);
    al.st_title = widget_lookup(al.win, "label_row_title", 1);
    al.st_sub = widget_lookup(al.win, "label_row_sub", 1);
    if (!al.view || !al.status || !al.st_title || !al.st_sub) {
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
    widget_on(al.view, EVT_POINTER_DOWN, al_on_pointer, (void *)0);
    widget_on(al.view, EVT_POINTER_MOVE, al_on_pointer, (void *)0);
    widget_on(al.view, EVT_POINTER_UP, al_on_pointer, (void *)0);
    widget_on(al.view, EVT_POINTER_ABORT, al_on_pointer, (void *)0);
    widget_on(al.view, EVT_AFTER_PAINT, al_on_paint, (void *)0);
    return 0;
}

/* The M1 Pod menu's Albums row: the mode used last (the grid on a first use). A window that will not open leaves
 * the stock Albums list, through the Home dispatcher. 0 once something is requested. */
int albums_open(void) {
    int r = al_open(!al_use_grid());
    if (r == -1 && !al.win) return pod_home_open(HOME_ALBUM);
    return r;
}
