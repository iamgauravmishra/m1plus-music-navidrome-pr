/* M1+ Music Playlists: the stock playlists as a grid, each one a 2x2 mosaic of its albums' covers.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * One page, ui/m1plus_playlists.bin: the navbar (Back, "Playlists", a "..." button, Now Playing) over a stock list, list_view > scroll_view
 * (playlists_scrollview), the structure of the Albums page (patch/albums.c, docs/modules/albums.md), whose ONE child is a custom view, view_grid,
 * that paints the cells itself in its own EVT_AFTER_PAINT through the shared grid (patch/grid.c). The stock scroll_view does the scrolling.
 * A cell is a GRID_COVER px tile, the playlist's name under it and "N tracks" under that. docs/modules/playlists.md has the whole design.
 *
 *   data      the playlists come from the stock query (loadLocalClassList(CLASS_PLAYLISTS), copied: what the stock Playlists page lists) when
 *             the page opens and again whenever its window comes back to the front (a playlist may have been edited in the stock songs
 *             page, or one created, imported or deleted), so nothing is cached across visits. Per playlist the loader reads its songs
 *             (loadLocalClassList(CLASS_PLAYLIST_SONGS) with classinfo[1] = the playlist) ONE playlist a tick: the track count, and from the
 *             first PL_SCAN songs the first four distinct albums that have a Cover Flow cache file (the key is the cc_album_key of the song:
 *             its artist and album as the playlist stored them; when that file does not exist the album of that name in the library is looked
 *             up, whose record carries the artist the cache key was made from).
 *   tiles     the grid's ring (GRID_TILES). The tile of a playlist with 2..4 albums is composed by grid_mosaic from the 168 px cache files
 *             box-reduced to a quadrant, one source per tick; one album is that cover full size; none is the stock placeholder disc. Paint never
 *             decodes, and neither does the loader while the scroll_view drags or flings.
 *   modes     the navbar toggle (btn_albumview) switches the grid and the list (LIST_ROW_H rows, 52 px mosaics, patch/grid.c grid_list_paint) in place;
 *             the choice is saved in PLAYLISTS_FILE.
 *   touch     a tap on a cell or row opens the playlist in our Songs page (patch/songs.c, class 0xff13), or the stock songs page (allmusic_page) as the stock
 *             Playlists page does when ours does not open.
 *   menu      the "..." button opens a popup card of this page (hidden, insensitive widgets shown by the payload): New playlist, Import,
 *             Export (the stock code), Delete playlists (select mode on this page: marks, a bar with the Delete pill, the stock delete handler's sequence on the stock
 *             selection vector; the stock Playlists page only where the page cannot). No hook.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "scroll.h"
#include "covercache.h"
#include "common.h"
#include "grid.h"
#include "i18n.h"
#include "keyboard.h"
#include "picker.h"

extern int pod_home_open(int id); /* patch/m1plus.c: a stock Home destination through the dispatcher */
extern int
songs_open_playlist(int id,
                    const char *name); /* patch/songs.c: our Songs page on a playlist; -1 when it did not open */

#define CELL_H GRID_CELL_H
#define PITCH GRID_PITCH
#define PL_W 320
#define PL_TAP_PX SC_DRAG_PX
#define PL_AHEAD (pl.list ? 2 : 1)
#define HOME_PLAYLIST 14
#define PL_PICK_MS 400 /* the picker's add after a New playlist: the keyboard page's close is over */
#if GRID_TILES < GRID_COLS * ((GRID_VIEW_H + CELL_H) / PITCH + 2 + 1) + 2
#error GRID_TILES cannot hold the visible cells, the next row and the history
#endif
#if GRID_TILES < (GRID_VIEW_H / LIST_ROW_H) + 2 + 2 + 2
#error GRID_TILES cannot hold the visible rows, the next two and the history
#endif

#define B(w, off) (*(unsigned char *)((char *)(w) + (off)))
#define I(w, off) (*(int *)((char *)(w) + (off)))
#define P(w, off) (*(void **)((char *)(w) + (off)))

#define PL_SIG 9 /* pl_dbsig: three files, three words each */
#define PL_DB "/mnt/data/database.db"

typedef grid_tile_t tile_t;

typedef struct {
    unsigned key[4]; /* the first distinct albums of the playlist that have a cache file */
    int nk, songs;
    int scanned; /* 0 not read, 1 read, PL_SCAN_MISS read and an album had a key but no cache file (its file may appear: read again when the page returns) */
} info_t;
#define PL_SCAN_MISS 2

static struct {
    void *win, *view, *sv, *status, *btn_more, *scrim, *card, *btn; /* btn: the view toggle */
    void *title, *back, *np, *btn_selall, *bar,
        *del; /* the navbar's title, Back and Now Playing; the select mode's Select All text, bar and Delete pill (the last three optional: no select mode without them) */
    void *mark[2]; /* the select marks (unselect, selected): bitmaps */
    unsigned char *sel; /* the select mode's bitset: (count + 7) / 8 bytes */
    unsigned nsel;
    int select; /* select mode (Delete Playlists in the menu) */
    void *st_ltitle, *st_lsub; /* the hidden labels whose styles are the list mode's two text styles */
    int list; /* 1 list mode, 0 grid */
    int press; /* list: the row under the finger, + 1 */
    void *pls; /* our copy of the stock playlist rows */
    unsigned count;
    info_t *info; /* count entries */
    void *albums; /* the library's albums (cc_albums), loaded at the first scan, for the album-name lookup */
    int albums_tried;
    unsigned *tmp; /* one quadrant (side / 2 squared words) for grid_mosaic */
    int seen, dir, noscroll;
    int down, down_x, down_y;
    int menu; /* the popup card is open */
    unsigned more_timer;
    void *items[PL_MENU_ROWS],
        *labels[PL_MENU_ROWS]; /* the menu's row buttons and their labels (a label may be missing: no fit) */
    void *fade; /* the navbar's fade (img_nb_fade, optional): shown only while the list is scrolled */
    unsigned sig[PL_SIG]; /* the database's state (pl_dbsig) when the playlists were last read */
    int have_sig;
    int bg; /* another window is in front: the loader does not run (pl_on_bg) */
    grid_t g; /* LAST (test/pod/playlists.py reads the fields above by index) */
} pl __attribute__((section(".scratch")));

static void pl_show(void *w, int on) {
    if (!w) return;
    widget_set_visible(w, on, 0);
    widget_set_sensitive(w, on);
}

static int pl_rows(void) { return ((int)pl.count + GRID_COLS - 1) / GRID_COLS; }
static int pl_rows_h(void) {
    return pl.list ? (int)pl.count * LIST_ROW_H : pl_rows() ? GRID_ROW_GAP + pl_rows() * PITCH : 0;
} /* the cells' or rows' height */
static int pl_pad(void) {
    return pl.select ? SG_BAR_H : 0;
} /* the select bar covers the window's last SG_BAR_H rows: the list scrolls clear of it */
static int pl_content(void) { return pl_rows_h() ? pl_rows_h() + pl_pad() : 0; }
static int pl_max_scroll(void) {
    int m = pl_content() - GRID_VIEW_H;
    return m > 0 ? m : 0;
}
static int pl_off(void) { return pl.sv ? I(pl.sv, SC_YOFF) : 0; }

/* The navbar's fade (an insensitive image, built hidden) is for rows passing under the bar: shown while the list is scrolled, hidden at rest, where the
 * first row would be darkened by it. It is never a touch target. No fade widget = nothing happens. */
static void pl_fade(void) {
    if (!pl.fade) return;
    widget_set_visible(pl.fade, pl_off() > 0, 0);
    widget_set_sensitive(pl.fade, 0);
}
static void pl_redraw(void) { widget_invalidate_force(pl.sv, (void *)0); }
static int pl_abs(int v) { return v < 0 ? -v : v; }

/* Pick mode (the Add to Playlist picker, patch/picker.c; docs/modules/picker.md): "New playlist" is row 0, the playlists follow. When the picker opens over
 * our own Songs page of a playlist, the Playlists page below it has a state, kept aside here and put back when the picker goes. */
static struct {
    int on, id;
    unsigned timer;
    void *stash;
    void *star; /* the Favourites row's glyph: a 24 px white star, alpha bitmap */
} pick __attribute__((section(".scratch")));
static int pl_v(void) { return pick.on ? 2 : 0; } /* the rows before the playlists: New playlist, Favourites */
static void *pl_rec(int i) { return deque_at(pl.pls, (unsigned)(i - pl_v())); }
/* The playlist's id: REC_DISC, what the stock row handler hands to classinfo[1] (@0x53d5f4) */
static int pl_id(int i) { return I(pl_rec(i), REC_DISC); }

/* A text with its %d: "8 tracks", "3 Selected" (the number put where the player's language has its %d), as the album page's meta line */
static unsigned pl_fmt(char *out, unsigned size, const char *f, int n) {
    char digits[12];
    unsigned o = 0, d = 0, i;
    for (i = (unsigned)(n < 0 ? 0 : n); d == 0 || i; i /= 10) digits[d++] = (char)('0' + i % 10);
    while (*f && o + 1 < size) {
        if (f[0] == '%' && f[1] == 'd') {
            while (d && o + 1 < size) out[o++] = digits[--d];
            f += 2;
        } else
            out[o++] = *f++;
    }
    out[o] = 0;
    return o;
}

/* ---------------------------------------------------------------------------
 * The window: the rows that touch the view and the ones about to
 */
static int pl_row_of(int s) { return s > GRID_ROW_GAP + CELL_H ? (s - GRID_ROW_GAP - CELL_H) / PITCH + 1 : 0; }

/* The rows (grid rows, or list rows = playlists) that touch the view: [*r0, *r1], inside [0, n - 1] also while a drag pulls the list past an end (overscroll). */
static void pl_span(int *r0, int *r1) {
    int n = pl.list ? (int)pl.count : pl_rows(), s = pl_off();
    if (pl.list)
        *r0 = s / LIST_ROW_H, *r1 = (s + GRID_VIEW_H - 1) / LIST_ROW_H;
    else
        *r0 = pl_row_of(s), *r1 = (s + GRID_VIEW_H - GRID_ROW_GAP + PITCH - 1) / PITCH - 1;
    if (*r0 < 0) *r0 = 0;
    if (*r1 > n - 1) *r1 = n - 1;
}

static void pl_window(int *lo, int *hi) {
    int per = pl.list ? 1 : GRID_COLS, n = pl.list ? (int)pl.count : pl_rows(), r0, r1;
    pl_span(&r0, &r1);
    if (pl.dir < 0)
        r0 -= PL_AHEAD;
    else
        r1 += PL_AHEAD;
    if (r0 < 0) r0 = 0;
    if (r1 > n - 1) r1 = n - 1;
    *lo = r0 * per;
    *hi = (r1 + 1) * per - 1;
    if (*hi > (int)pl.count - 1) *hi = (int)pl.count - 1;
}

/* The top of playlist a's cell or row in the window, and its height. */
static int pl_top(int a) { return (pl.list ? a * LIST_ROW_H : GRID_ROW_GAP + a / GRID_COLS * PITCH) - pl_off(); }
static int pl_height(void) { return pl.list ? LIST_ROW_H : CELL_H; }

static tile_t *pl_find(int a) { return grid_find(&pl.g, a); }

/* The tile's texts: the name and the count (blank until the playlist has been read). */
static void pl_texts(tile_t *t, int a) {
    info_t *in = &pl.info[a];
    char sub[48];
    sub[0] = 0;
    if (a < pl_v()) {
        grid_set(t, TR(a ? "Favorites" : "playlist_create"), sub, 0);
        return;
    }
    if (in->scanned) pl_fmt(sub, sizeof sub, TR(in->songs == 1 ? "%d track" : "%d tracks"), in->songs);
    grid_set(t, cc_str(pl_rec(a), REC_TITLE), sub, 0);
}

/* The tile's texts and mosaic keys from the playlist's scan (the count shows once the playlist has been read). */
static void pl_prep(tile_t *t, int a) {
    info_t *in = &pl.info[a];
    grid_free_art(t);
    t->fit = 0, t->art = 0, t->qi = 0;
    t->mid = a < pl_v();
    t->nq = in->nk > 1 && !pl.tmp ? 1 : in->nk;
    memcpy(t->qkey, in->key, sizeof t->qkey);
    if (in->scanned && !in->nk) t->art = 2; /* no album with a cover: the placeholder */
    pl_texts(t, a);
}

/* The texts are cut to a width that the select mode changes (the list's rows make room for the mark): every tile's are made again from the playlist. */
static void pl_retext(void) {
    int i;
    for (i = 0; pl.g.tiles && pl.pls && i < pl.g.n; ++i) {
        tile_t *t = &pl.g.tiles[i];
        if (t->album && t->album - 1 < (int)pl.count) pl_texts(t, t->album - 1), t->fit = 0;
    }
}

static tile_t *pl_tile(int a) {
    int lo, hi, fresh;
    tile_t *t;
    pl_window(&lo, &hi);
    t = grid_tile(&pl.g, a, lo, hi, &fresh);
    if (fresh) pl_prep(t, a);
    return t;
}

static tile_t *pl_tile_of(void *ctx, int a) {
    (void)ctx;
    return pl_tile(a);
}

/* ---------------------------------------------------------------------------
 * Paint (the cell paint is the grid's)
 */
static int pl_is_sel(int i) { return pl.sel && (pl.sel[i >> 3] >> (i & 7) & 1); }

/* The select mark of playlist a: the list's rows have a column left of the cover (the cover and the texts move right by SG_SEL_COL, as the Songs page's); a grid cell
 * has it at the bottom right of its cover (SG_MARK px, 6 px in). Drawn only when wholly inside the window. */
static void pl_mark(void *canvas, int a, int x, int y) {
    int src[4], dst[4];
    if (y < 0 || y + SG_MARK > GRID_VIEW_H) return;
    src[0] = src[1] = 0, src[2] = src[3] = SG_MARK;
    dst[0] = x, dst[1] = y, dst[2] = dst[3] = SG_MARK;
    canvas_draw_image(canvas, pl.mark[pl_is_sel(a)], src, dst);
}

/* The picker's New playlist row: a dark rounded square over the placeholder disc and a plus (two 2 px bars, as Lucide's plus at this size) in the art box. Only when
 * wholly inside the window (a row half under the navbar shows the disc, as the marks are drawn). */
static void pl_plus(void *canvas, int y) {
    int i, x = LIST_ART_X, c = LIST_ART_X + LIST_ART / 2, cy = y + LIST_ART / 2;
    if (y < 0 || y + LIST_ART > GRID_VIEW_H) return;
    canvas_set_fill_color(canvas, 0xff2c2c2eu);
    for (i = 0; i < 2; ++i) { /* the corners of a LIST_R 4 arc: the first line starts 2 px in, the second 1 */
        canvas_fill_rect(canvas, x + 2 - i, y + i, LIST_ART - 2 * (2 - i), 1);
        canvas_fill_rect(canvas, x + 2 - i, y + LIST_ART - 1 - i, LIST_ART - 2 * (2 - i), 1);
    }
    canvas_fill_rect(canvas, x, y + 2, LIST_ART, LIST_ART - 4);
    canvas_set_fill_color(canvas, 0xffffffffu);
    canvas_fill_rect(canvas, c - 10, cy - 1, 20, 2);
    canvas_fill_rect(canvas, c - 1, cy - 10, 2, 20);
}

/* The Favourites row's glyph: the star of the Favorites icon (the filled five-point star, outer radius 10.5 px), 4 x 4 samples a pixel into the alpha of a white bitmap
 * (the cross and the chevron are made the same way). Coordinates are eighths of a pixel; the unit vectors are thousandths. */
#define PL_STAR 24
static void *pl_make_star(void) {
    static const int ox[5] = {0, 951, 588, -588, -951}, oy[5] = {-1000, -309, 809, 809, -309};
    static const int ix[5] = {588, 951, 0, -951, -588}, iy[5] = {-809, 309, 1000, 309, -809};
    int vx[10], vy[10], x, y, i, j, k, n;
    unsigned *px;
    void *b = bitmap_create_ex(PL_STAR, PL_STAR, PL_STAR * 4, BITMAP_RGBA8888);
    if (!b) return b;
    px = (unsigned *)bitmap_lock_buffer_for_write(b);
    if (!px || bitmap_get_line_length(b) != PL_STAR * 4) {
        if (px) bitmap_unlock_buffer(b);
        bitmap_destroy(b);
        return (void *)0;
    }
    for (k = 0; k < 5; ++k) { /* centre (12, 12.5) px: a star's visual centre is a little below its circle's */
        vx[2 * k] = 96 + 84 * ox[k] / 1000, vy[2 * k] = 100 + 84 * oy[k] / 1000;
        vx[2 * k + 1] = 96 + 38 * ix[k] / 1000, vy[2 * k + 1] = 100 + 38 * iy[k] / 1000;
    }
    for (y = 0; y < PL_STAR; ++y)
        for (x = 0; x < PL_STAR; ++x) {
            for (n = 0, i = 0; i < 4; ++i)
                for (j = 0; j < 4; ++j) {
                    int sx = x * 8 + 2 * j + 1, sy = y * 8 + 2 * i + 1, in = 0;
                    for (k = 0; k < 10; ++k) { /* even-odd: the edges a ray to +x crosses */
                        int a = k, c = (k + 1) % 10;
                        if ((vy[a] > sy) != (vy[c] > sy) &&
                            ((sx - vx[a]) * (vy[c] - vy[a]) < (vx[c] - vx[a]) * (sy - vy[a])) == (vy[c] > vy[a]))
                            in ^= 1;
                    }
                    n += in;
                }
            px[y * PL_STAR + x] = (unsigned)(n * 255 / 16) << 24 | 0xffffffu;
        }
    bitmap_unlock_buffer(b);
    return b;
}

/* The picker's Favourites row: the New playlist row's dark rounded square with the star centred in the art box. */
static void pl_star(void *canvas, int y) {
    int i, x = LIST_ART_X, src[4], dst[4];
    if (y < 0 || y + LIST_ART > GRID_VIEW_H) return;
    canvas_set_fill_color(canvas, 0xff2c2c2eu);
    for (i = 0; i < 2; ++i) {
        canvas_fill_rect(canvas, x + 2 - i, y + i, LIST_ART - 2 * (2 - i), 1);
        canvas_fill_rect(canvas, x + 2 - i, y + LIST_ART - 1 - i, LIST_ART - 2 * (2 - i), 1);
    }
    canvas_fill_rect(canvas, x, y + 2, LIST_ART, LIST_ART - 4);
    if (!pick.star) return;
    src[0] = src[1] = 0, src[2] = src[3] = PL_STAR;
    dst[0] = x + (LIST_ART - PL_STAR) / 2, dst[1] = y + (LIST_ART - PL_STAR) / 2, dst[2] = dst[3] = PL_STAR;
    canvas_draw_image(canvas, pick.star, src, dst);
}

static int pl_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int off = pl_off(), r0, r1, last, a;
    (void)ctx;
    if (!canvas || !pl.view || !pl.g.tiles || !pl.count) return RET_OK;
    I(canvas, CANVAS_OY) += off;
    pl_span(&r0, &r1);
    if (r1 >= r0 && pl.list) {
        grid_list_paint(canvas, &pl.g, pl.st_ltitle, pl.st_lsub, r0, r1, off, GRID_VIEW_H, pl.select ? 0 : pl.press,
                        pl.select ? SG_SEL_COL : 0, pl_tile_of, (void *)0);
        if (pl_v() && r0 == 0) pl_plus(canvas, LIST_ART_Y - off);
        if (pl_v() && r0 <= 1 && r1 >= 1) pl_star(canvas, LIST_ROW_H + LIST_ART_Y - off);
        for (a = r0; pl.select && pl.mark[0] && a <= r1; ++a)
            pl_mark(canvas, a, LIST_ART_X + (SG_SEL_COL - 6 - SG_MARK) / 2,
                    a * LIST_ROW_H - off + (LIST_ROW_H - SG_MARK) / 2);
    } else if (r1 >= r0) {
        last = (r1 + 1) * GRID_COLS;
        if (last > (int)pl.count) last = (int)pl.count;
        grid_paint(canvas, &pl.g, r0 * GRID_COLS, last, GRID_ROW_GAP - off, GRID_VIEW_H, pl_tile_of, (void *)0);
        for (a = r0 * GRID_COLS; pl.select && pl.mark[0] && a < last; ++a)
            pl_mark(canvas, a, grid_cell_x(a) + GRID_COVER - SG_MARK - 6,
                    grid_cell_y(a, GRID_ROW_GAP - off) + GRID_COVER - SG_MARK - 6);
    }
    I(canvas, CANVAS_OY) -= off;
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * Reading a playlist: its track count and the albums for its mosaic
 */

/* Reads playlist i's songs: how many, and from the first PL_SCAN the first four distinct albums that have a cover. The stock query leaves them
 * in *pdeq_showlist, which the next query replaces (the library lookup is therefore loaded first). */
static void pl_scan(int i) {
    info_t *in = &pl.info[i];
    int n, miss;
    void *list;
    if (i < pl_v()) { /* the picker's New playlist and Favourites rows have nothing to read */
        in->scanned = 1;
        return;
    }
    if (!pl.albums_tried) {
        pl.albums_tried = 1;
        pl.albums = cc_albums();
    }
    *(int *)(CLASSINFO + 4) = pl_id(i);
    loadLocalClassList(CLASS_PLAYLIST_SONGS);
    list = *(void **)PDEQ_SHOWLIST;
    n = list ? (int)deque_size(list) : 0;
    in->songs = n;
    in->nk = grid_mosaic_keys(list, pl.albums, in->key,
                              &miss); /* patch/grid.c: shared with the Songs page's playlist header */
    in->scanned = miss ? PL_SCAN_MISS : 1;
    picker_restore(); /* (the picker keeps the browsing record of the page it is over) */
}

/* ---------------------------------------------------------------------------
 * The loader: one step a tick on the page's own timer (a scan of one playlist, or one source of one mosaic)
 */
static int pl_next_load(void) {
    int lo, hi, a, best = -1, bd = 0x7fffffff;
    if (!pl.g.tiles || !pl.count) return -1;
    pl_window(&lo, &hi);
    for (a = lo; a <= hi; ++a) {
        tile_t *t = pl_find(a);
        int top, d;
        if (pl.info[a].scanned && t && t->art) continue;
        top = pl_top(a);
        d = pl_abs(top + pl_height() / 2 - GRID_VIEW_H / 2);
        if (top >= GRID_VIEW_H || top + pl_height() <= 0) d += 100000;
        if (d < bd) bd = d, best = a;
    }
    return best;
}

static int pl_on_load(const void *unused);

/* The scroll_view is moving: a finger drags it, or its scroll animator (the fling) runs. Nothing is read or decoded meanwhile. */
static int pl_moving(void) { return grid_moving(pl.sv); }

static void pl_kick(void) {
    if (!pl.more_timer && pl.view && !pl.bg && (pl.noscroll || pl_next_load() >= 0))
        pl.more_timer = timer_add(pl_on_load, (void *)0, PL_MORE_MS);
}

static void pl_dir(void) {
    int s = pl_off();
    if (s != pl.seen) pl.dir = s > pl.seen ? 1 : -1;
    pl.seen = s;
}

/* The tile's finished picture is made of the albums the scan found, in the same order: pl_prep would compose it again unchanged. */
static int pl_same_art(const tile_t *t, const info_t *in) {
    int i;
    if (t->art != 1 || t->nq != (in->nk > 1 && !pl.tmp ? 1 : in->nk)) return 0;
    for (i = 0; i < t->nq; ++i)
        if (t->qkey[i] != in->key[i]) return 0;
    return 1;
}

static int pl_on_load(const void *unused) {
    int a;
    (void)unused;
    pl.more_timer = 0;
    if (!pl.view) return RET_OK;
    pl_dir();
    if (pl_moving()) {
        pl_kick();
        return RET_OK;
    }
    a = pl_next_load();
    if (a >= 0) {
        tile_t *t = pl_tile(a);
        int top = pl_top(a);
        if (!pl.info[a].scanned) {
            unsigned ck = t->ckey;
            pl_scan(a);
            if (pl_same_art(t, &pl.info[a])) { /* read again (PL_SCAN_MISS), the same albums: the mosaic stays */
                pl_texts(t, a);
                t->ckey = ck, t->fit = 0;
            } else
                pl_prep(t, a);
        } else if (!t->art)
            grid_mosaic(&pl.g, t, pl.tmp);
        if (top < GRID_VIEW_H && top + pl_height() > 0) pl_redraw();
    }
    pl_kick();
    return RET_OK;
}

static int pl_on_scroll(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (!pl.view) return RET_OK;
    pl_fade();
    pl_dir();
    pl_kick();
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The playlists: read when the page opens and each time it comes back to the front
 */
static void pl_size(void) {
    int h = pl_content();
    if (!h) h = GRID_VIEW_H; /* (the empty page hides the view) */
    widget_resize(pl.view, PL_W, h);
    widget_set_prop_int(pl.sv, "virtual_h", h);
}

/* The stock query again and the page rebuilt from it: tiles and scans dropped (they were of the old list) unless the list and the database are as they were. */
static void pl_select(int on);

/* The database's state: modification time (seconds, nanoseconds) and size of the file and of its WAL and journal (a write may land only in those). Every playlist's
 * songs are rows of that file, so an edit anywhere (the stock picker, our pages, the player's own writes) changes it. 0 when the file cannot be read (no signature:
 * nothing is kept). struct stat (MIPS o32): st_size at +0x30, st_mtime at +0x40, its nanoseconds at +0x44. */
static int pl_dbsig(unsigned sig[PL_SIG]) {
    static const char *const path[3] = {PL_DB, PL_DB "-wal", PL_DB "-journal"};
    unsigned st[40];
    int i;
    for (i = 0; i < 3; ++i) {
        memset(st, 0, sizeof st);
        if (__xstat(3, path[i], st) != 0)
            sig[3 * i] = sig[3 * i + 1] = sig[3 * i + 2] = 0xffffffffu;
        else
            sig[3 * i] = st[0x40 / 4], sig[3 * i + 1] = st[0x44 / 4], sig[3 * i + 2] = st[0x30 / 4];
        if (i == 0 && sig[0] == 0xffffffffu) return 0;
    }
    return 1;
}

static int pl_same_str(const char *a, const char *b) {
    while (*a && *a == *b) ++a, ++b;
    return *a == *b;
}

/* The freshly read list is the page's: as many rows, the same id and name in each (a rename, delete, add or reorder changes one). */
static int pl_same_list(void *old, unsigned oldn, void *fresh, unsigned n) {
    unsigned i;
    if (!old || !fresh || oldn != n) return 0;
    for (i = 0; i < n; ++i) {
        void *a = deque_at(old, i), *b = deque_at(fresh, i);
        if (I(a, REC_DISC) != I(b, REC_DISC) || !pl_same_str(cc_str(a, REC_TITLE), cc_str(b, REC_TITLE))) return 0;
    }
    return 1;
}

static void pl_load(void) {
    void *list, *old = pl.pls;
    unsigned oldn = pl.count;
    unsigned sig[PL_SIG];
    int have, keep, i;
    pl_select(0); /* a page read again is not in select mode (the marks were of the old list) */
    if (pl.more_timer) timer_remove(pl.more_timer);
    pl.more_timer = 0;
    have = pl_dbsig(sig);
    pl.pls = (void *)0;
    if (loadLocalClassList(CLASS_PLAYLISTS) > 0) {
        list = *(void **)PDEQ_PLAYLIST;
        if (list && deque_size(list)) pl.pls = cc_copy_list(list);
    }
    picker_restore();
    pl.count = (pl.pls ? deque_size(pl.pls) : 0) + (unsigned)pl_v();
    if (pl.count > PL_MAX + (unsigned)pl_v()) pl.count = PL_MAX + (unsigned)pl_v();
    /* Nothing changed (the same playlists, the database file untouched since the scans were made): the scans and the tiles stay (a visit to a playlist's songs page or a
     * dialog and back does not grey and recompose every mosaic). Any doubt, and everything is dropped. */
    keep = have && pl.have_sig && pl.info && pl.g.tiles && pl.count && oldn == pl.count &&
           pl_same_list(old, oldn - (unsigned)pl_v(), pl.pls, pl.count - (unsigned)pl_v());
    for (oldn = 0; keep && oldn < PL_SIG; ++oldn) keep = sig[oldn] == pl.sig[oldn];
    if (old) deque_destroy(old);
    /* The cover cache grows while another page is open (the Cover Flow build): a playlist whose scan found an album without a file is read again, and its
     * tile composed again, by the loader. Complete scans (every album had its file or none) stay: no query, no decode. */
    for (oldn = 0; keep && oldn < pl.count; ++oldn)
        if (pl.info[oldn].scanned == PL_SCAN_MISS) pl.info[oldn].scanned = 0;
    free(pl.sel);
    pl.sel = (unsigned char *)0, pl.nsel = 0;
    if (!keep) {
        grid_drop(&pl.g);
        free(pl.info);
        pl.info = pl.count ? calloc(pl.count, sizeof(info_t)) : (info_t *)0;
        if (pl.count && !pl.info) pl.count = 0;
        for (i = 0; pl.info && i < pl_v(); ++i) pl.info[i].scanned = 1; /* New playlist, Favourites: nothing to read */
        grid_placeholder(&pl.g);
    }
    pl.have_sig = have;
    memcpy(pl.sig, sig, sizeof pl.sig);
    pl.sel = pl.count ? calloc((pl.count + 7) / 8, 1)
                      : (unsigned char *)0; /* none: no select mode (the menu's Delete opens the stock page) */
    pl_show(pl.view, pl.count != 0);
    pl_show(pl.status, pl.count == 0);
    if (!pl.count) widget_set_tr_text(pl.status, "No playlists");
    pl_size();
    pl.dir = 1;
    pl.seen = pl_off();
    pl_redraw();
    pl_kick();
}

/* ---------------------------------------------------------------------------
 * Touch: a tap on a cell opens the playlist in the stock songs page
 */
static int pl_cell_at(int x, int y) {
    int a;
    if (y < 0 || y >= pl_rows_h()) return -1;
    if (!pl.list) return grid_cell_at(x, y, GRID_ROW_GAP, (int)pl.count);
    a = y / LIST_ROW_H; /* a list row: any x */
    return a < (int)pl.count ? a : -1;
}

static void pl_set_press(int p) {
    if (pl.press == p) return;
    pl.press = p;
    pl_redraw();
}

static int pl_item_of(void *e) {
    int pt[2];
    pt[0] = I(e, PE_X), pt[1] = I(e, PE_Y);
    widget_to_local(pl.view, pt);
    return pl_cell_at(pt[0], pt[1]);
}

/* Our Songs page on the playlist (patch/songs.c songs_open_playlist: its name the title, its id in classinfo[1]); a page that does not open leaves the
 * stock Playlists page's row handler (@0x53d300, mode 0): the name for the page's title, the id into classinfo[1], then the stock Songs page with the
 * playlist class. Back returns here. */
static void pl_create(void);
static void pl_pick_add(int id);
static void pl_pick_later(int id);

static void pl_open(int i) {
    void *rec;
    if (pl_v()) { /* the picker: New playlist (row 0), Favourites (row 1), or the add to that playlist */
        if (i == 0)
            pl_create();
        else
            pl_pick_add(i == 1 ? PICKER_FAVOURITES : pl_id(i));
        return;
    }
    rec = pl_rec(i);
    if (songs_open_playlist(I(rec, REC_DISC), cc_str(rec, REC_TITLE)) != -1) return;
    snprintf((char *)NAV_TITLE, 0x200, "%s", cc_str(rec, REC_TITLE));
    *(int *)(CLASSINFO + 4) = I(rec, REC_DISC);
    navigator_to_with_context("allmusic_page", (const void *)CLASS_PLAYLIST_SONGS);
}

/* ---------------------------------------------------------------------------
 * Select mode (the menu's Delete Playlists), in the Songs page's manner (patch/songs.c, docs/modules/songs.md "Select"): the navbar's Back becomes the x, the title
 * "N Selected", Select All at the right, a mark on every cell or row, a bar below with the Delete pill. Delete runs the stock handler's sequence (@0x53dbcc) on the
 * stock selection vector, which the page fills from its own marks at that moment.
 */
static void pl_head(void) { /* the navbar's title: "N Selected" in select mode, else Playlists */
    char buf[64];
    if (!pl.title) return;
    if (!pl.select) {
        widget_set_tr_text(pl.title, pl_v() ? "Add to Playlist" : "Playlists");
        return;
    }
    pl_fmt(buf, sizeof buf, TR("%d Selected"), (int)pl.nsel);
    widget_set_text_utf8(pl.title, buf);
}

/* The select mode is there when the asset has its widgets, the marks decoded and the selection bitset exists. */
static int pl_select_ok(void) {
    return pl.btn_selall && pl.bar && pl.del && pl.mark[0] && pl.mark[1] && pl.sel && pl.count;
}

static void pl_select(int on) {
    int i, max;
    void *nav[3];
    if (on == pl.select) return;
    pl.select = on;
    pl.nsel = 0;
    if (pl.sel) memset(pl.sel, 0, (pl.count + 7) / 8);
    pl.press = pl.down = 0;
    nav[0] = pl.btn_more, nav[1] = pl.btn, nav[2] = pl.np;
    for (i = 0; i < 3; ++i) pl_show(nav[i], !on);
    pl_show(pl.btn_selall, on);
    pl_show(pl.bar, on);
    if (pl.title) widget_resize(pl.title, (on ? SG_SELALL_X : NAV_CF_X) - NAV_TITLE_X, 22);
    if (pl.back) {
        widget_set_prop_str(pl.back, "style:normal:icon", on ? "ah_nav_close" : "ah_nav_back");
        widget_set_prop_str(pl.back, "style:over:icon", on ? "ah_nav_close" : "ah_nav_back");
        widget_set_prop_str(pl.back, "style:pressed:icon", on ? "ah_nav_close_down" : "ah_nav_back_down");
    }
    pl_head();
    pl_retext();
    pl_size();
    max = pl_max_scroll();
    if (pl_off() > max) widget_set_prop_int(pl.sv, "yoffset", max);
    pl_fade();
    pl_redraw();
}

static void pl_toggle(int i) {
    if (i < 0 || i >= (int)pl.count || !pl.sel) return;
    pl.sel[i >> 3] ^= (unsigned char)(1 << (i & 7));
    pl.nsel += pl_is_sel(i) ? 1 : (unsigned)-1;
    pl_head();
    pl_redraw();
}

static int pl_on_selall(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (!pl.select || !pl.sel) return RET_OK;
    if (pl.nsel < pl.count) { /* all, unless all are: then none */
        unsigned i;
        memset(pl.sel, 0, (pl.count + 7) / 8);
        for (i = 0; i < pl.count; ++i) pl.sel[i >> 3] |= (unsigned char)(1 << (i & 7));
        pl.nsel = pl.count;
    } else {
        memset(pl.sel, 0, (pl.count + 7) / 8);
        pl.nsel = 0;
    }
    pl_head();
    pl_redraw();
    return RET_OK;
}

static int pl_on_back(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (pl.select)
        pl_select(0);
    else
        navigator_back();
    return RET_OK;
}

static int pl_on_down(void *ctx, void *e) {
    int a;
    (void)ctx;
    pl.down = 0;
    if (!e || !pl.view) return RET_OK;
    a = pl_item_of(e);
    pl.down = a + 1, pl.down_x = I(e, PE_X), pl.down_y = I(e, PE_Y);
    if (pl.list && !pl.select) pl_set_press(a + 1);
    return RET_OK;
}

static int pl_on_up(void *ctx, void *e) {
    int a = pl.down - 1;
    (void)ctx;
    pl.down = 0;
    if (pl.list) pl_set_press(0);
    if (a < 0 || !e || !pl.view) return RET_OK;
    if (pl_abs(I(e, PE_X) - pl.down_x) < PL_TAP_PX && pl_abs(I(e, PE_Y) - pl.down_y) < PL_TAP_PX &&
        pl_item_of(e) == a) {
        if (pl.select)
            pl_toggle(a);
        else
            pl_open(a);
    }
    return RET_OK;
}

static int pl_on_abort(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    pl.down = 0;
    if (pl.list) pl_set_press(0);
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The "..." menu: a popup card over the page. New playlist, Import and Export run the stock code and the page reads the playlists again;
 * Delete is select mode (above).
 */
/* The card as wide as the language needs: the widest label (widget_measure_text: the label's own font, its translated text), the glyph's
 * room before it (PL_TEXT_X) and PL_TEXT_R after it, PL_CARD_MIN..PL_CARD_MAX, the right edge kept at PL_CARD_RIGHT under the button; the rows and labels follow. The glass is drawn
 * patch3_x, so it stretches to any of these widths. A label that is missing or cannot be measured leaves the asset's width (PL_CARD_MAX, the
 * widest language's). Run at every open: the language may have changed while the page lay under another. */
static void pl_fit(void) {
    int i, w = 0;
    for (i = 0; i < PL_MENU_ROWS; ++i) {
        const unsigned *t = pl.labels[i] ? widget_get_text(pl.labels[i]) : 0;
        int tw = t && *t ? (int)(widget_measure_text(pl.labels[i], t) + 0.999f) : 0;
        if (tw <= 0) return;
        if (tw > w) w = tw;
    }
    w += PL_TEXT_X + PL_TEXT_R;
    if (w < PL_CARD_MIN) w = PL_CARD_MIN;
    if (w > PL_CARD_MAX) w = PL_CARD_MAX;
    widget_move(pl.card, PL_CARD_RIGHT - w, PL_CARD_Y);
    widget_resize(pl.card, w, PL_MENU_ROWS * PL_ROW_H);
    for (i = 0; i < PL_MENU_ROWS; ++i) {
        widget_resize(pl.items[i], w, PL_ROW_H);
        widget_resize(pl.labels[i], w - PL_TEXT_X - PL_TEXT_R, PL_ROW_H);
    }
}

static void pl_menu(int on) {
    if (on) pl_fit();
    pl.menu = on;
    pl_show(pl.scrim, on);
    pl_show(pl.card, on);
}

/* The stock one-line message box, as the stock Playlists page shows "full" and "exists" (@0x53e97c, @0x53e9f8). */
static void pl_toast(const char *text) {
    struct {
        int kind, ms;
        char text[MSGINFO_TEXT], text2[MSGINFO_TEXT];
    } info;
    unsigned i;
    memset(&info, 0, sizeof info);
    info.kind = MSGINFO_KIND;
    info.ms = MSGINFO_MS;
    for (i = 0; text[i] && i < sizeof info.text - 1; ++i) info.text[i] = text[i];
    navigator_to_with_context("dialog/msginfo_dialog", &info);
}

/* Done on our keyboard (patch/keyboard.c; not modal: it calls this after the keyboard page was told to close, the name trimmed, 1 to 63 bytes): the
 * stock create handler's tail (@0x53e8e4): the stock list is read first, createPlayListItem adds the playlist to the database (-1 full, -2 exists),
 * the stock message box for those two, and this page, which is in front again (or about to be: the other order only reads twice), reads its list again. */
static void pl_named(const char *name) {
    int r;
    loadLocalClassList(CLASS_PLAYLISTS);
    r = createPlayListItem(*(void **)PDEQ_PLAYLIST, name);
    picker_restore();
    if (r == -1)
        pl_toast(TR("msg_playlistfull"));
    else if (r == -2)
        pl_toast(TR("msg_playlistexist"));
    else if (
        r >= 0 && pl_v() &&
        pl.win) { /* the picker: the new playlist gets the songs, the page closes, once the keyboard page has gone (pl_pick_later) */
        pl_pick_later(r);
        return;
    }
    if (pl.win && pl.view) pl_load();
}

/* The picker's add (patch/picker.c: batch_add_file, the message), then the page closes as the stock picker's handler closes its window (window_close on the row's window). */
static void pl_pick_add(int id) {
    void *win = pl.win;
    picker_add(id);
    if (win) window_close(win);
}

/* The keyboard calls pl_named from its own click handler right after navigator_back, so its window is still going (its close animation, its widgets about to be destroyed
 * under the handler). The add, its message dialog and the picker's own window_close are three more window operations on top of that; they wait PL_PICK_MS on a timer of the
 * picker's page (removed with it), when the keyboard is gone and the picker is the front window. */
static int pl_pick_fire(const void *unused) {
    (void)unused;
    pick.timer = 0;
    if (pick.on && pl.win) pl_pick_add(pick.id);
    return RET_OK;
}

static void pl_pick_later(int id) {
    if (pick.timer) return;
    pick.id = id;
    pick.timer = timer_add(pl_pick_fire, (void *)0, PL_PICK_MS);
    if (!pick.timer) pl_pick_add(id); /* no timer: now */
}

static void pl_create(void) {
    keyboard_open(TR("playlist_create"), TR("msg_newplaylists"), (const char *)0, pl_named, (kb_cancel_fn)0, KB_DONE);
}

/* The stock confirm dialog of the stock delete handler (@0x53dc78: kind 1, the text at +8, msg_delplaylist): modal; 0xa (CONFIRM_YES) is Yes, anything else ends it (@0x53dcc0). */
static int pl_ask(const char *text) {
    struct {
        int kind, ms;
        char text[MSGINFO_TEXT], text2[MSGINFO_TEXT];
    } info;
    unsigned i;
    memset(&info, 0, sizeof info);
    info.kind = 1;
    for (i = 0; text[i] && i < sizeof info.text - 1; ++i) info.text[i] = text[i];
    return navigator_to_with_context("dialog/confirminfo_dialog", &info) == CONFIRM_YES;
}

/* The page's marks into the stock selection: a vector of ints as long as *pdeq_playlist, 1 for each selected row. The stock list is read first (another page's
 * query may have replaced it) and must be what the page shows (as many playlists, the same ids in the same order): else nothing is selected and the page reads again. */
static int pl_stock_selection(void) {
    void *list;
    unsigned i, n;
    if (loadLocalClassList(CLASS_PLAYLISTS) <= 0 || !*(void **)SEL_VEC) return 0;
    list = *(void **)PDEQ_PLAYLIST;
    n = list ? deque_size(list) : 0;
    if (!n || !pl.pls || n != deque_size(pl.pls)) return 0;
    for (i = 0; i < n; ++i)
        if (I(deque_at(list, i), REC_DISC) != pl_id((int)i)) return 0;
    select_recordinit((int)n);
    for (i = 0; i < pl.count && i < n; ++i)
        if (pl_is_sel((int)i)) set_selectindex((int)i);
    return 1;
}

/* Delete: the stock handler's sequence (@0x53dbcc): nothing selected is the message msg_delplaylistfailed; the confirm dialog (msg_delplaylist; Yes 0xa); then
 * batch_delete_file(0xf00b, *pdeq_playlist, the selection, 0, 0), which runs deletePlaylist and deleteAllMusicByPlaylist for each selected row; the message
 * msg_delplaylistsuccess. The stock page rebuilds its list afterwards: this page reads it again (pl_load ends select mode). */
static int pl_on_delete(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (!pl.select) return RET_OK;
    if (!pl.nsel) {
        pl_toast(TR("msg_delplaylistfailed"));
        return RET_OK;
    }
    if (!pl_ask(TR("msg_delplaylist"))) return RET_OK;
    if (pl_stock_selection()) {
        batch_delete_file(CLASS_PLAYLISTS, *(void **)PDEQ_PLAYLIST, *(void **)SEL_VEC, 0, 0);
        pl_toast(TR("msg_delplaylistsuccess"));
    }
    pl_load();
    return RET_OK;
}

static int pl_on_more(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (pl.view) pl_menu(!pl.menu);
    return RET_OK;
}

static int pl_on_scrim(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    pl_menu(0);
    return RET_OK;
}

enum { PL_NEW, PL_IMPORT, PL_EXPORT, PL_DELETE };

static int pl_on_item(void *ctx, void *e) {
    int which = (int)(long)ctx;
    (void)e;
    pl_menu(0);
    if (!pl.view) return RET_OK;
    *(int *)NAVIGATION_STATUS = 0; /* the stock pages' normal (not multi-select) mode: export all */
    if (which == PL_NEW) {
        pl_create(); /* the keyboard is not modal: pl_named reads the list when the name is in */
        return RET_OK;
    } else if (which == PL_IMPORT)
        stock_playlist_import((void *)0, (void *)0);
    else if (which == PL_EXPORT)
        stock_playlist_export((void *)0, (void *)0);
    else { /* Delete Playlists: select mode on this page (nothing to select with no playlist); where it cannot be (the asset or the marks lack it) the stock Playlists page, whose multi-select deletes */
        if (!pl.count) return RET_OK;
        if (!pl_select_ok())
            pod_home_open(HOME_PLAYLIST);
        else
            pl_select(1);
        return RET_OK;
    }
    pl_load();
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The page
 */
static int pl_on_fg(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    pl.bg = 0;
    if (pl.view && pl.g.tiles) pl_load();
    return RET_OK;
}

/* Behind another window (the stock songs page of a playlist, a dialog) the loader stops: a scan sets classinfo[1] and replaces *pdeq_showlist,
 * the list the songs page draws its rows from and plays. The to-foreground reads everything again and restarts it. */
static int pl_on_bg(void *ctx, void *e) {
    pl.bg = 1;
    if (pl.more_timer) timer_remove(pl.more_timer);
    pl.more_timer = 0;
    return pl_on_abort(ctx, e);
}

/* ---------------------------------------------------------------------------
 * The view toggle (the Albums page's, docs/modules/albums.md): the grid or the list, switched in place and saved
 */
static int pl_use_grid(void) { return set_read(PLAYLISTS_FILE, '1') != '0'; }

/* The toggle shows the glyph of the mode a tap switches to. */
static void pl_glyph(void) {
    const char *icon = pl.list ? "pod_nav_grid" : "pod_nav_list";
    if (!pl.btn) return;
    widget_set_prop_str(pl.btn, "style:normal:icon", icon);
    widget_set_prop_str(pl.btn, "style:over:icon", icon);
    widget_set_prop_str(pl.btn, "style:pressed:icon", pl.list ? "pod_nav_grid_down" : "pod_nav_list_down");
}

/* The covers of a mode: GRID_COVER px with GRID_R corners blended into black, or LIST_ART px with LIST_R corners cut in the alpha (a pressed row lies behind). */
static void pl_shape(int list) { grid_shape(&pl.g, list ? LIST_ART : GRID_COVER, list ? LIST_R : GRID_R, list); }

static int pl_first(void) {
    int a = pl.list ? pl_off() / LIST_ROW_H : pl_row_of(pl_off()) * GRID_COLS;
    if (a > (int)pl.count - 1) a = (int)pl.count - 1;
    return a < 0 ? 0 : a;
}

/* Switches the mode in place; the first playlist in view stays at the top. */
static void pl_set_mode(int list) {
    int first = pl_first(), max;
    void *wa = P(pl.sv, SC_WA);
    if (wa && I(wa, SC_AN_STATE) == SC_AN_RUNNING &&
        P(wa, SC_AN_WIDGET) == pl.sv) { /* a coasting list stops (patch/scroll.c sc_down) */
        widget_animator_destroy(wa);
        stock_scroll_done(pl.sv, (void *)0);
    }
    if (pl.more_timer) timer_remove(pl.more_timer);
    pl.more_timer = 0;
    pl.list = list, pl.press = 0, pl.down = 0, pl.dir = 1;
    grid_drop(&pl.g); /* the tiles were made for the other shape */
    pl_shape(list);
    if (pl.g.tiles) grid_placeholder(&pl.g);
    pl_size();
    max = pl_max_scroll();
    first = list ? first * LIST_ROW_H : first / GRID_COLS * PITCH;
    widget_set_prop_int(pl.sv, "yoffset", first > max ? max : first);
    pl.seen = pl_off();
    pl_fade();
    pl_glyph();
    pl_redraw();
    pl_kick();
}

static int pl_on_toggle(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (!pl.view || !pl.g.tiles) return RET_OK;
    pl_set_mode(!pl.list);
    home_write_atomic(PLAYLISTS_FILE, PLAYLISTS_TMP, pl.list ? "0\n" : "1\n");
    return RET_OK;
}

static int pl_on_destroy(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (pl.more_timer) timer_remove(pl.more_timer);
    grid_free(&pl.g);
    if (pl.pls) deque_destroy(pl.pls);
    if (pl.albums) deque_destroy(pl.albums);
    free(pl.info);
    free(pl.sel);
    free(pl.tmp);
    if (pl.mark[0]) bitmap_destroy(pl.mark[0]);
    if (pl.mark[1]) bitmap_destroy(pl.mark[1]);
    memset(&pl, 0, sizeof pl);
    if (pick.timer) timer_remove(pick.timer);
    pick.timer = 0;
    if (pick.star) bitmap_destroy(pick.star);
    pick.star = (void *)0;
    if (pick.on) { /* the picker's page: its copies freed, the page below it (if there was one) as it was */
        pick.on = 0;
        picker_release();
    }
    if (pick.stash) {
        memcpy(&pl, pick.stash, sizeof pl);
        free(pick.stash);
        pick.stash = (void *)0;
    }
    return RET_OK;
}

/* 0 once the page is up, -1 if the window could not open, -2 if the asset is not ours (the page is left again). */
static int pl_open_page(void) {
    static const char *const ITEMS[PL_MENU_ROWS] = {"pl_item0", "pl_item1", "pl_item2", "pl_item3"};
    static const char *const LABELS[PL_MENU_ROWS] = {"pl_label0", "pl_label1", "pl_label2", "pl_label3"};
    int i;
    if (pl.win) return -1;
    memset(&pl, 0, sizeof pl);
    pl.win = window_open("m1plus_playlists");
    if (!pl.win) return -1;
    widget_on(pl.win, EVT_DESTROY, pl_on_destroy, (void *)0);
    pl.back = pod_bind(pl.win, "btn_return", pl_on_back, (void *)0);
    pl.np = pod_bind(pl.win, "btn_backtoplayer", pod_on_player, (void *)0);
    pl.btn_selall = pod_bind(pl.win, "btn_selall", pl_on_selall, (void *)0); /* the select mode's widgets: optional */
    pl.del = pod_bind(pl.win, "pl_del", pl_on_delete, (void *)0);
    pl.bar = widget_lookup(pl.win, "pl_bar", 1);
    pl.title = widget_lookup(pl.win, "label_title", 1);
    pl.btn_more = pod_bind(pl.win, "btn_more", pl_on_more, (void *)0);
    pl.scrim = pod_bind(pl.win, "pl_scrim", pl_on_scrim, (void *)0);
    pl.card = widget_lookup(pl.win, "pl_card", 1);
    pl.view = widget_lookup(pl.win, "view_grid", 1);
    pl.sv = widget_lookup(pl.win, "playlists_scrollview", 1);
    pl.status = widget_lookup(pl.win, "label_status", 1);
    pl.fade = widget_lookup(pl.win, "img_nb_fade", 1); /* optional */
    pl.g.st_title = widget_lookup(pl.win, "label_grid_title", 1);
    pl.g.st_sub = widget_lookup(pl.win, "label_grid_sub", 1);
    pl.st_ltitle = widget_lookup(pl.win, "label_row_title", 1);
    pl.st_lsub = widget_lookup(pl.win, "label_row_sub", 1);
    pl.btn = pod_bind(pl.win, "btn_albumview", pl_on_toggle, (void *)0);
    if (!pl.btn_more || !pl.btn || !pl.scrim || !pl.card || !pl.view || !pl.sv || !pl.status || !pl.g.st_title ||
        !pl.g.st_sub || !pl.st_ltitle || !pl.st_lsub) {
        navigator_back(); /* an asset that is not ours */
        return -2;
    }
    for (i = 0; i < PL_MENU_ROWS; ++i) {
        if (!(pl.items[i] = pod_bind(pl.win, ITEMS[i], pl_on_item, (void *)(long)i))) {
            navigator_back();
            return -2;
        }
        pl.labels[i] = widget_lookup(pl.items[i], LABELS[i], 0);
    }
    pl_menu(0);
    if (pl.del) pod_centre_pill(pl.del, PL_BAR_PILL_W);
    pl.tmp = calloc((GRID_COVER / 2) * (GRID_COVER / 2),
                    4); /* one quadrant of a mosaic; without it a mosaic falls back to its first cover */
    { /* the stock grid, its two text styles are this page's hidden labels */
        void *st_title = pl.g.st_title, *st_sub = pl.g.st_sub;
        if (!grid_init(&pl.g, pl.win, GRID_TILES, GRID_COVER, GRID_R)) {
            grid_free(&pl.g);
            pl_show(pl.view, 0);
            pl_show(pl.status, 1);
            widget_set_tr_text(pl.status, "Not enough memory");
            return 0;
        }
        pl.g.st_title = st_title, pl.g.st_sub = st_sub;
    }
    pl.mark[0] = pod_make_mark(pl.win, "unselect");
    pl.mark[1] = pod_make_mark(pl.win, "selected");
    if (!pl.mark[0] || !pl.mark[1]) { /* the pair is all or none (no marks: no select mode) */
        if (pl.mark[0]) bitmap_destroy(pl.mark[0]);
        if (pl.mark[1]) bitmap_destroy(pl.mark[1]);
        pl.mark[0] = pl.mark[1] = (void *)0;
    }
    if (pl_v() && !pick.star) pick.star = pl_make_star();
    pl.list = pl_v() || !pl_use_grid(); /* the picker is always the list (the saved choice is the page's own) */
    pl_shape(pl.list);
    pl_glyph();
    if (pl_v()) { /* the picker: Back and the title only */
        pl_show(pl.btn_more, 0), pl_show(pl.btn, 0), pl_show(pl.np, 0);
        if (pl.title) widget_resize(pl.title, SG_SELALL_X - NAV_TITLE_X, 22);
        pl_head();
    }
    pl.noscroll = !widget_on(pl.sv, EVT_SCROLL, pl_on_scroll, (void *)0) ||
                  !widget_on(pl.sv, EVT_SCROLL_END, pl_on_scroll, (void *)0);
    widget_on(pl.win, EVT_WINDOW_TO_FG, pl_on_fg, (void *)0);
    widget_on(pl.win, EVT_WINDOW_TO_BG, pl_on_bg, (void *)0);
    widget_on(pl.view, EVT_POINTER_DOWN, pl_on_down, (void *)0);
    widget_on(pl.view, EVT_POINTER_UP, pl_on_up, (void *)0);
    widget_on(pl.view, EVT_POINTER_ABORT, pl_on_abort, (void *)0);
    widget_on(pl.view, EVT_AFTER_PAINT, pl_on_paint, (void *)0);
    pl_load();
    return 0;
}

/* The M1+ Music menu's Playlists row. A window that will not open leaves the stock Playlists page, through the Home dispatcher. 0 once something is requested. */
int playlists_open(void) {
    int r = pl_open_page();
    if (r == -1 && !pl.win) return pod_home_open(HOME_PLAYLIST);
    return r;
}

/* The Add to Playlist picker's page (patch/picker.c picker_open): this page in pick mode. Over our own Playlists page's Songs page the state of the Playlists page below
 * is kept aside first (pl is one struct) and put back by pl_on_destroy. 0 once the page is up; < 0 where it could not open (the caller falls back to the stock picker). */
int playlists_pick(void) {
    int r;
    if (pick.on) return -1;
    if (pl.win) {
        pick.stash = calloc(1, sizeof pl);
        if (!pick.stash) return -1;
        memcpy(pick.stash, &pl, sizeof pl);
        memset(&pl, 0, sizeof pl);
    }
    pick.on = 1;
    r = pl_open_page();
    if (r < 0) {
        pick.on = 0; /* (a page left again, -2, ends in pl_on_destroy, which puts the stash back) */
        if (r == -1 && pick.stash) {
            memcpy(&pl, pick.stash, sizeof pl);
            free(pick.stash);
            pick.stash = (void *)0;
        }
    }
    return r;
}
