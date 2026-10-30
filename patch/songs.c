/* M1+ Music Songs: the library as one list, in the Apple Music manner.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * One page, ui/m1plus_songs.bin (docs/modules/songs.md has the whole design): the glass navbar (Back, the small title, Search, Sort, Select, Now Playing) over a
 * stock list, list_view > scroll_view (songs_scrollview) whose ONE child, view_grid, is the content view of the Albums page (patch/albums.c): it paints the rows,
 * the section headers, the pinned header and the select marks itself in its own EVT_AFTER_PAINT, with no widget per song; the stock scroll_view does the scrolling.
 * The content view's only children are the large title and the Play / Shuffle pills (real flat buttons that scroll with it). Beside the list, as widgets of the
 * window: the A-Z rail (outside the scroll_view, so a touch on it never starts a drag) and the letter bubble, the sort card, and the select mode's bar.
 *
 *   data      loadLocalClassList(0xf001) (what allmusic_page_init runs: getAllMusic into *pdeq_showlist, in the stock sort order, sort_flag). The 20,000 songs of a big
 *             library are NOT copied: the page keeps one 8 byte entry per song (the cover key, the section letter) and reads the title and the artist from the stock
 *             list while painting. The stock list is replaced by the next stock query (another page's), so every use first checks that it is still the list this index
 *             was made from (sg_valid: the pointer, the size, the first record) and the page reads it again when its window comes back to the front (or, if it is
 *             on top, from a timer, when a paint finds it gone). The library's albums (cc_albums, loaded first: it is a stock query too) answer the cover lookup of a song
 *             whose own artist + album has no cache file.
 *   sections  with the stock Title order (sort_flag 0) the songs are grouped by the Initial the scan stored (REC_INITIAL: '*' digits, 'A'..'Z', '#'; digits and symbols
 *             are one section, "#"), the stock order kept: the labelling with the most songs under their own letter (sg_sections), strays stay where they are; the rail
 *             is a compact index (the letters of the sections, or every k-th with dots between when they would be more than SG_RAIL_ITEMS items) that a finger maps
 *             onto every section; any other order is a plain list and has no rail.
 *   tiles     the Albums list's ring (patch/grid.c, GRID_TILES 52 px covers), one per song, decoded one per 16 ms tick when the scroll_view is still. The covers are
 *             the Cover Flow cache; the background build (patch/covercache.c) makes the ones of the songs around the first in view that have none.
 *   touch     a tap on a row plays it as the stock Songs row does (loadSongList, then playing_page); in select mode it toggles the row's mark. The rail grabs the
 *             touch: DOWN, MOVE, UP set the scroll_view's offset to the section's header (a coasting list is stopped first) and show the bubble.
 *   select    the page's own multi-select: marks in a bitset, "N Selected", Select All, and the bar. Add to playlist and Delete run the stock code on the stock
 *             selection vector, which the page fills from its bitset at that moment (select_recordinit, set_selectindex): Delete is batch_delete_file (class 0xf001,
 *             *pdeq_showlist, the vector) after the stock confirm dialog; Add opens the stock playlist picker (playlist_page with the add context), which adds the
 *             selection to the playlist that is tapped and closes itself.
 *   sort      the sort card sets sort_flag as the stock sort dialog's row handler does (the flag and [SYSSET] SORTSELECT), then reads the list again.
 *   lists     the same page shows the other stock song lists, each in the stock order of its query (docs/modules/songs.md "The other lists"): Favourites, Recently
 *             Added, Recently Played, Most Played, Hi-Res (the menu rows, songs_open_list) and a playlist (the Playlists page, songs_open_playlist: its id goes into
 *             classinfo[1] before every query and play, as the stock row tap leaves it). A list is what the stock allmusic_page shows for its class: no sort (Search
 *             moves to Sort's slot, the capsule is three pieces), so no sections and no rail; its title is the menu row's text or the playlist's name, cut with an
 *             ellipsis; play, Shuffle (that list, the stock Shuffle mode) and the stock Delete (batch_delete_file with the list's class: the stock removes the
 *             song from that list's table, and the file too when asked) use its class; it is read again whenever the page comes back to the front (a play changes
 *             Recently Played and Most Played, Now Playing's star the Favourites).
 *             A genre's songs (songs_open_genre, from the Genres page, class 0xff09) are such a list too: the genre's name is in classinfo + 0x30d (and classinfo[0],
 *             the Unknown Genre byte) for every query and play, as the stock row tap leaves it; the stock navbar has no Search there, so the capsule is Select | Now
 *             Playing (Select the left cap).
 *             An artist's songs (Cover Flow's artist page, songs_open_artist) is the same page on class 0xff11: its whole state is the 0x390 byte browsing
 *             record loadAlbumList(0xf004) and loadAlbumdetailList(0xff01, the All songs row) build, which the page snapshots and puts back before every query
 *             and play; the artist is the title and the grey line of a row is its album.
 *   count     the content view's label sg_foot under the last row: "25 songs", on every list.
 * No hook; everything runs from the page's widgets and timers.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "scroll.h"
#include "covercache.h"
#include "common.h"
#include "grid.h"
#include "i18n.h"

extern int pod_home_open(int id);   /* patch/m1plus.c: a stock Home destination through the dispatcher */
extern void pod_toast(const char *text);   /* patch/shuffle.c: the stock message box */
extern void pod_set_in_order(void);   /* patch/shuffle.c: Shuffle and Repeat one become List play */
extern void pod_set_mode(int mode);   /* patch/shuffle.c: the stock play mode */
extern unsigned pod_rand(unsigned n); /* patch/shuffle.c: 0 .. n - 1 */

#define ROW LIST_ROW_H
#define SG_W 320                       /* the content's width: the list_view's (the scroll_view clips at 310) */
#define SG_TAP_PX SC_DRAG_PX
#define SG_AHEAD 2                     /* rows loaded beyond the view in the scroll direction */
#if GRID_TILES < (GRID_VIEW_H / LIST_ROW_H) + 2 + 2 + 2
#error GRID_TILES cannot hold the visible rows, the next two and the history
#endif
#if SG_RAIL_ITEMS * SG_RAIL_PITCH > GRID_VIEW_H - SG_BAR_H
#error the rail cannot hold SG_RAIL_ITEMS items in select mode
#endif

#define B(w, off) (*(unsigned char *)((char *)(w) + (off)))
#define I(w, off) (*(int *)((char *)(w) + (off)))
#define P(w, off) (*(void **)((char *)(w) + (off)))

typedef grid_tile_t tile_t;

typedef struct {
    unsigned key;          /* cc_album_key of the song: its cover's cache file */
    unsigned char letter;  /* the section letter: 'A'..'Z' or '#' */
    unsigned char pad[3];
} song_t;

static struct {
    void *win, *view, *sv, *status, *title, *back, *np;
    void *fade;                   /* the navbar's fade (img_nb_fade, optional): shown only while the list is scrolled */
    void *btn_search, *btn_sort, *btn_select, *btn_selall, *btn_play, *btn_shuffle, *btn_add, *btn_del;
    void *st_title, *st_sub, *st_hdr, *st_rail, *st_rail_on;   /* hidden labels whose styles are the text styles */
    void *rail, *bubble, *bubble_letter, *bar, *scrim, *card, *tick[SG_SORT_ROWS];
    void *list;                   /* the stock list the index is of (*pdeq_showlist when valid) */
    void *first;                  /* its first record: with the size, tells a list another query replaced */
    unsigned count;
    song_t *idx;                  /* count entries */
    unsigned char *sel;           /* the select mode's bitset: (count + 7) / 8 bytes */
    unsigned nsel;
    int select;                   /* select mode */
    int sort;                     /* sort_flag as the page last read it */
    int nsec;                     /* 0: a plain list; else the sections */
    unsigned sec_start[SG_MAX_SEC];       /* the first song of each section */
    unsigned char sec_letter[SG_MAX_SEC];
    void *albums;                 /* the library's albums (cc_albums), for the cover lookup */
    int albums_tried;
    void *disc;                   /* the rail's disc (SG_RAIL_DISC px, alpha) and the select marks (SG_MARK px): bitmaps */
    void *mark[2];                /* unselect, selected */
    int press;                    /* the row under the finger, + 1 */
    int seen, dir, noscroll;
    int down, down_x, down_y;     /* the row a press began on, + 1, and where */
    int title_on;                 /* the small title is shown */
    int title_fits;               /* the small title's text fits its room (the glass capsule starts 64 px after it): a language where it does not has none */
    int menu;                     /* the sort card is open */
    int picker;                   /* the stock playlist picker is open over this page */
    int grab, rail_on, rail_i;    /* a finger holds the rail (the grab); it has set a letter (the disc and the bubble show); the letter's section */
    unsigned more_timer, stale_timer, build_timer;
    int own, done, build_at;      /* the cover build: this page holds the worker's set; its done counter at the last poll; the song it was made around */
    char title_save[0x200];       /* nagvation_title across the picker */
    int cls;                      /* the class listed: CLASS_ALL_SONGS (the library: sort, sections, rail) or another stock song list */
    int pl_id;                    /* CLASS_PLAYLIST_SONGS: the playlist, classinfo[1] for every query and play; CLASS_GENRE_SONGS: 1 for the Unknown Genre row (classinfo + 0xc) */
    const char *key;              /* the title's key (TR), or 0: the title is name */
    char name[0x100];             /* a playlist's name */
    unsigned char ci[CLASSINFO_SIZE];   /* CLASS_ARTIST_SONGS: the browsing record of the artist (CLASSINFO, as the two stock queries left it), put back before every query and play */
    void *big;                    /* the large title (sg_title) */
    void *foot;                   /* the song count under the last row (sg_foot, a label in the content view) */
    grid_t g;                     /* the tile ring (LAST: test/pod/songs.py reads the fields above by index) */
} sg __attribute__((section(".scratch")));

static int sg_on_stale(const void *unused);

static void sg_show(void *w, int on) {
    if (!w) return;
    widget_set_visible(w, on, 0);
    widget_set_sensitive(w, on);
}

static int sg_abs(int v) { return v < 0 ? -v : v; }
static int sg_off(void) { return sg.sv ? I(sg.sv, SC_YOFF) : 0; }
static void sg_redraw(void) { widget_invalidate_force(sg.sv, (void *)0); }
static void sg_redraw_rail(void) { widget_invalidate_force(sg.rail, (void *)0); }

/* The text of a record: its title, else its file name. */
static const char *sg_name(void *rec) {
    const char *t = cc_str(rec, REC_TITLE);
    return *t ? t : cc_str(rec, REC_NAME);
}

/* ---------------------------------------------------------------------------
 * The stock list and its index
 */

/* The section rank of a record, in the order the stock Title sort puts them (toolsQueryDbTable's title comparator 0x5e0dac: digits and most symbols before the
 * letters): 0 "#" (the Initial '*', a title that starts with a digit, or '#', anything else), 1..26 'A'..'Z'. From the Initial the scan stored; 0 (never written: a
 * database older than the column) takes the title's first character. */
#define SG_RANKS 27
#if SG_MAX_SEC < SG_RANKS
#error a section per rank does not fit
#endif
static unsigned char sg_rank(void *rec) {
    int c = B(rec, REC_INITIAL);
    if (!c) c = (unsigned char)*sg_name(rec);
    if (c >= 'a' && c <= 'z') c -= 32;
    return c >= 'A' && c <= 'Z' ? (unsigned char)(c - 'A' + 1) : 0;
}

/* The letter a section of rank r shows. */
static unsigned char sg_rank_letter(int r) { return r > 0 ? (unsigned char)('A' + r - 1) : '#'; }

/* The index is of the stock list `list` as long as that list is still in *pdeq_showlist, as big, and starts with the same record. */
static int sg_valid(void) {
    void *cur = *(void **)PDEQ_SHOWLIST;
    return sg.list && cur == sg.list && deque_size(cur) == sg.count && (!sg.count || deque_at(cur, 0) == sg.first);
}

static int sg_lib(void) { return sg.cls == CLASS_ALL_SONGS; }   /* the library: the only list with the sort card, sections and the rail */
static int sg_genre(void) { return sg.cls == CLASS_GENRE_SONGS; }   /* a genre's songs: the stock navbar has no Search there */
static int sg_search_x(void) { return sg_lib() ? NAV_SEARCH_X : sg_genre() ? NAV_VIEW_X : NAV_CF_X; }   /* the capsule's first piece: a list's Search takes Sort's slot; a genre's has none (Select, the left cap, is first) */

/* What a genre's stock row tap leaves in the browsing record (@0x535c4c): classinfo[0] = 0xff09, the name (0x80 bytes, cut as snprintf cuts it) at + 0x30d, the byte + 0xc. */
static void sg_genre_info(const char *name, int unknown) {
    unsigned char *ci = (unsigned char *)CLASSINFO;
    unsigned i;
    *(int *)ci = CLASS_GENRE_SONGS;
    memset(ci + CLASSINFO_GENRE, 0, CLASSINFO_GENRE_SIZE);
    for (i = 0; name[i] && i < CLASSINFO_GENRE_SIZE - 1; ++i) ci[CLASSINFO_GENRE + i] = (unsigned char)name[i];
    ci[CLASSINFO_GENRE_UNKNOWN] = unknown != 0;
}

/* The browsing record as the class listed needs it (another page's query may have changed it): a playlist's id in classinfo[1], a genre's name, an artist's whole
 * record. */
static void sg_classinfo(void) {
    if (sg.cls == CLASS_PLAYLIST_SONGS) *(int *)(CLASSINFO + CLASSINFO_ARG) = sg.pl_id;
    else if (sg_genre()) sg_genre_info(sg.name, sg.pl_id);
    else if (sg.cls == CLASS_ARTIST_SONGS) memcpy((void *)CLASSINFO, sg.ci, CLASSINFO_SIZE);
}

/* The stock query of the class listed (into *pdeq_showlist), the browsing record put back first. */
static int sg_query(void) {
    sg_classinfo();
    return loadLocalClassList(sg.cls);
}

/* Content geometry. The rows (and the headers, in Title order) start at SG_TOP; section s's header is at sg_hdr_y(s), its songs follow. */
static int sg_hdr_y(int s) { return SG_TOP + s * SG_HDR_H + (int)sg.sec_start[s] * ROW; }

/* The section holding song i (the last one that starts at or before it), -1 in a plain list. */
static int sg_sec_of(int i) {
    int s = sg.nsec - 1;
    while (s > 0 && (int)sg.sec_start[s] > i) --s;
    return s;
}

static int sg_row_y(int i) { return SG_TOP + (sg.nsec ? (sg_sec_of(i) + 1) * SG_HDR_H : 0) + i * ROW; }
static int sg_pad(void) { return sg.select ? SG_BAR_H : 0; }   /* the bar covers the window's last SG_BAR_H rows: the list scrolls clear of it */
static int sg_rows_end(void) { return SG_TOP + sg.nsec * SG_HDR_H + (int)sg.count * ROW; }   /* the content y under the last row: the song count */
static int sg_content(void) { return sg_rows_end() + SG_FOOT_H + sg_pad(); }
static int sg_max_scroll(void) {
    int m = sg_content() - GRID_VIEW_H;
    return m > 0 ? m : 0;
}

/* The first song whose row ends below content y (the one in y's row, or the first after a header or the title block). */
static int sg_row_from(int y) {
    int s, i;
    if (!sg.count) return 0;
    if (y < SG_TOP) return 0;
    if (!sg.nsec) i = (y - SG_TOP) / ROW;
    else {
        s = sg.nsec - 1;
        while (s > 0 && sg_hdr_y(s) > y) --s;
        i = y < sg_hdr_y(s) + SG_HDR_H ? (int)sg.sec_start[s] : (int)sg.sec_start[s] + (y - sg_hdr_y(s) - SG_HDR_H) / ROW;
    }
    return i > (int)sg.count - 1 ? (int)sg.count - 1 : i;
}

/* The song under content point y: its row, or -1 for the title block, a header and the air below the last row. */
static int sg_at(int y) {
    int i;
    if (y < SG_TOP || !sg.count) return -1;
    i = sg_row_from(y);
    return y >= sg_row_y(i) && y < sg_row_y(i) + ROW ? i : -1;
}

/* The songs [*r0, *r1] that touch the view (r1 < r0 for none), inside [0, count - 1] also while a drag pulls the list past an end. */
static void sg_span(int *r0, int *r1) {
    int s = sg_off(), n = (int)sg.count;
    *r0 = sg_row_from(s < 0 ? 0 : s);
    *r1 = sg_row_from(s + GRID_VIEW_H - 1);
    if (n && sg_row_y(*r1) > s + GRID_VIEW_H - 1) --*r1;   /* the last pixel is in a header: the song after it is not in view */
    if (n && sg_row_y(*r0) + ROW <= s) ++*r0;
    if (*r1 > n - 1) *r1 = n - 1;
    if (*r0 < 0) *r0 = 0;
}

/* The songs the tiles are kept for: those in view and SG_AHEAD rows beyond them in the scroll direction. */
static void sg_window(int *lo, int *hi) {
    int r0, r1;
    sg_span(&r0, &r1);
    if (sg.dir < 0) r0 -= SG_AHEAD;
    else r1 += SG_AHEAD;
    if (r0 < 0) r0 = 0;
    if (r1 > (int)sg.count - 1) r1 = (int)sg.count - 1;
    *lo = r0, *hi = r1;
}

/* The select mode moves the row's content right by one column. */
static int sg_tx(void) { return LIST_TEXT_X + (sg.select ? SG_SEL_COL : 0); }
static int sg_art_x(void) { return LIST_ART_X + (sg.select ? SG_SEL_COL : 0); }

static int sg_is_sel(int i) { return sg.sel && (sg.sel[i >> 3] >> (i & 7) & 1); }

/* The tile of song a, made from the stock record (the caller has checked sg_valid). */
static void sg_prep(tile_t *t, int a) {
    void *rec = deque_at(sg.list, (unsigned)a);
    grid_set(t, sg_name(rec), cc_str(rec, sg.cls == CLASS_ARTIST_SONGS ? REC_ALBUM : REC_ARTIST), sg.idx[a].key);   /* an artist's list: the artist is the title, the album the grey line */
}

static tile_t *sg_tile(int a) {
    int lo, hi, fresh;
    tile_t *t;
    sg_window(&lo, &hi);
    t = grid_tile(&sg.g, a, lo, hi, &fresh);
    if (fresh) sg_prep(t, a);
    return t;
}

/* The texts are cut to a width that the select mode changes: every tile's are made again from the record. */
static void sg_retext(void) {
    int i;
    for (i = 0; sg.g.tiles && sg.list && i < sg.g.n; ++i) {
        tile_t *t = &sg.g.tiles[i];
        if (t->album && t->album - 1 < (int)sg.count) sg_prep(t, t->album - 1), t->fit = 0;
    }
}

/* ---------------------------------------------------------------------------
 * Paint: the rows, the headers and the pinned header, in one EVT_AFTER_PAINT of the content view. Coordinates are the window's (its top is 0): the scroll_view has
 * moved the canvas up by yoffset, which the paint adds back (CANVAS_OY) for its duration, as the Albums page does.
 */
static void sg_fill(void *canvas, int x, int y0, int y1, int w, unsigned c) {
    if (y0 < 0) y0 = 0;
    if (y1 > GRID_VIEW_H) y1 = GRID_VIEW_H;
    if (y1 <= y0) return;
    canvas_set_fill_color(canvas, c);
    canvas_fill_rect(canvas, x, y0, w, y1 - y0);
}

/* The pinned header's backing: the page's black over the rows scrolling under it (the headers in the flow have no band, as the Recently Played shelf's).
 * (The letter is drawn with the text passes.) */
static void sg_band(void *canvas, int y) {
    sg_fill(canvas, 0, y, y + SG_HDR_H, SG_W, SG_HDR_BG);
}

/* The header letter of section s with its top at window y (only when it lies wholly inside the window, as every text). */
static void sg_letter_text(void *canvas, int s, int y) {
    unsigned w[2];
    int rect[4];
    if (y < 0 || y + SG_HDR_H > GRID_VIEW_H) return;
    w[0] = sg.sec_letter[s], w[1] = 0;
    rect[0] = SG_HDR_X, rect[1] = y, rect[2] = 100, rect[3] = SG_HDR_H - 1;
    canvas_draw_text_in_rect(canvas, w, 1, rect);
}

/* The pinned header: the section the window's top is in, at the top; the next header, as it arrives, pushes it up. Returns its section (-1 for none)
 * and the y of its band (<= 0). */
static int sg_pinned(int *y) {
    int s = sg_off(), k = sg.nsec - 1;
    if (!sg.nsec) return -1;
    while (k >= 0 && sg_hdr_y(k) > s) --k;
    if (k < 0) return -1;
    *y = k + 1 < sg.nsec && sg_hdr_y(k + 1) - s < SG_HDR_H ? sg_hdr_y(k + 1) - s - SG_HDR_H : 0;
    return k;
}

static void sg_paint_rows(void *canvas) {
    int r0, r1, r, off = sg_off(), pin, py, s, tx = sg_tx(), room = SG_TEXT_END - tx, pass;
    sg_span(&r0, &r1);
    for (r = r0; r <= r1; ++r) {
        tile_t *t = sg_tile(r);
        int y = sg_row_y(r) - off;
        if (sg.press == r + 1 && !sg.select) sg_fill(canvas, 0, y, y + ROW - 1, SG_W, LIST_PRESS);
        if (sg.select && sg.mark[0]) {
            void *m = sg.mark[sg_is_sel(r)];
            int src[4], dst[4], top = y + (ROW - SG_MARK) / 2;
            if (top >= 0 && top + SG_MARK <= GRID_VIEW_H) {
                src[0] = 0, src[1] = 0, src[2] = SG_MARK, src[3] = SG_MARK;
                dst[0] = LIST_ART_X + (SG_SEL_COL - 6 - SG_MARK) / 2, dst[1] = top, dst[2] = SG_MARK, dst[3] = SG_MARK;
                canvas_draw_image(canvas, m, src, dst);
            }
        }
        grid_blit(canvas, &sg.g, t, sg_art_x(), y + LIST_ART_Y, GRID_VIEW_H);
        sg_fill(canvas, tx, y + ROW - 1, y + ROW, room, LIST_HAIR);
    }
    for (pass = 0; pass < 2; ++pass) {   /* titles, then artists: one text style at a time */
        widget_prepare_text_style(pass ? sg.st_sub : sg.st_title, canvas);
        for (r = r0; r <= r1; ++r)
            grid_text(canvas, sg_tile(r), pass, tx, sg_row_y(r) - off + (pass ? LIST_SUB_Y : LIST_TITLE_Y), room, pass ? LIST_SUB_H : LIST_TITLE_H, GRID_VIEW_H);
    }
    if (!sg.nsec) return;
    widget_prepare_text_style(sg.st_hdr, canvas);
    for (s = 0; s < sg.nsec; ++s) sg_letter_text(canvas, s, sg_hdr_y(s) - off);
    pin = sg_pinned(&py);   /* over everything: the pinned band and its letter */
    if (pin >= 0) {
        sg_band(canvas, py);
        sg_letter_text(canvas, pin, py);
    }
}

static int sg_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int off = sg_off();
    (void)ctx;
    if (!canvas || !sg.view || !sg.g.tiles || !sg.count) return RET_OK;
    if (!sg_valid()) {   /* another query replaced the stock list: nothing of it is read; the page reads it again when it is on top */
        if (!sg.stale_timer) sg.stale_timer = timer_add(sg_on_stale, (void *)0, 100);
        return RET_OK;
    }
    I(canvas, CANVAS_OY) += off;
    sg_paint_rows(canvas);
    I(canvas, CANVAS_OY) -= off;
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The loader: one cover per tick on the page's own timer, none while the scroll_view moves (the Albums page's, docs/modules/albums.md)
 */
static int sg_next_load(void) {
    int lo, hi, a, best = -1, bd = 0x7fffffff, s = sg_off();
    if (!sg.g.tiles || !sg.count || !sg_valid()) return -1;
    sg_window(&lo, &hi);
    for (a = lo; a <= hi; ++a) {
        tile_t *t = grid_find(&sg.g, a);
        int top = sg_row_y(a) - s, d;
        if (t && t->art) continue;
        d = sg_abs(top + ROW / 2 - GRID_VIEW_H / 2);
        if (top >= GRID_VIEW_H || top + ROW <= 0) d += 100000;   /* ahead of the view */
        if (d < bd) bd = d, best = a;
    }
    return best;
}

static int sg_on_load(const void *unused);

static int sg_moving(void) {
    void *wa;
    if (!sg.sv) return 0;
    if (B(sg.sv, SC_PRESSED) && B(sg.sv, SC_DRAGGED)) return 1;
    wa = P(sg.sv, SC_WA);
    return wa && I(wa, SC_AN_STATE) == SC_AN_RUNNING && P(wa, SC_AN_WIDGET) == sg.sv;
}

static void sg_kick(void) {
    if (!sg.more_timer && sg.view && (sg.noscroll || sg_next_load() >= 0)) sg.more_timer = timer_add(sg_on_load, (void *)0, SG_MORE_MS);
}

static void sg_dir(void) {
    int s = sg_off();
    if (s != sg.seen) sg.dir = s > sg.seen ? 1 : -1;
    sg.seen = s;
}

/* The cache key of the library's album called `album` that has a cover file: a song of a compilation carries its own artist, whose key the cache has no
 * file for (the library lists an album once, under the artist of one of its tracks, and the cache is keyed by that record). 0: none. */
static unsigned sg_album_key(const char *album) {
    unsigned n = sg.albums ? deque_size(sg.albums) : 0, j;
    char url[80];
    if (!*album) return 0;
    for (j = 0; j < n; ++j) {
        void *r = deque_at(sg.albums, j);
        if (!cc_nocase(cc_str(r, REC_ALBUM), album)) {
            unsigned k = cc_album_key(r);
            return cc_url(url, k) ? k : 0;
        }
    }
    return 0;
}

/* The cover of a tile: its own key's file, else the library album's; a tile with neither shows the placeholder. */
static void sg_art(tile_t *t) {
    char url[80];
    if (!cc_url(url, t->ckey) && t->album - 1 < (int)sg.count) {
        unsigned k = sg_album_key(cc_str(deque_at(sg.list, (unsigned)(t->album - 1)), REC_ALBUM));
        if (k) t->ckey = k;
    }
    grid_art(&sg.g, t);
}

static int sg_on_load(const void *unused) {
    int a;
    (void)unused;
    sg.more_timer = 0;
    if (!sg.view) return RET_OK;
    sg_dir();
    if (sg_moving()) {   /* nothing is decoded while it moves: look again next tick */
        sg_kick();
        return RET_OK;
    }
    a = sg_next_load();
    if (a >= 0) {
        tile_t *t = sg_tile(a);
        int top = sg_row_y(a) - sg_off();
        sg_art(t);
        if (top < GRID_VIEW_H && top + ROW > 0) sg_redraw();
    }
    sg_kick();
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The navbar's title: the large title is in the content; once it has scrolled away the navbar shows the small one
 */
static void sg_title_update(void) {
    int on = sg.noscroll || sg.select || (sg_off() > SG_COLLAPSE && sg.title_fits);
    if (on != sg.title_on) {
        sg.title_on = on;
        widget_set_visible(sg.title, on, 0);
    }
    /* The navbar's fade (an insensitive image, built hidden) is for rows passing under the bar: shown while the list is scrolled, hidden at rest, where
     * it would darken the large title (as the Albums and Playlists pages). Never a touch target. No fade widget = nothing happens. */
    if (sg.fade) {
        widget_set_visible(sg.fade, sg_off() > 0, 0);
        widget_set_sensitive(sg.fade, 0);
    }
}

/* The background cover build (the Albums page's, docs/modules/albums.md): the covers of the songs around the first one in view that have no cache file. */
#define SG_BUILD_START_MS 50
#define SG_BUILD_MS 500

static void sg_retry(void) {   /* every tile that showed the placeholder for want of a file tries again */
    int i, any = 0;
    for (i = 0; sg.g.tiles && i < GRID_TILES; ++i) {
        tile_t *t = &sg.g.tiles[i];
        if (t->album && t->art == 2) t->art = 0, any = 1;
    }
    if (any) sg_kick();
}

static void sg_build_end(void) {
    if (sg.build_timer) timer_remove(sg.build_timer);
    sg.build_timer = 0;
    if (sg.own) cc_build_stop();
    sg.own = 0;
}

static int sg_on_build(const void *unused) {
    int done;
    (void)unused;
    sg.build_timer = 0;
    if (!sg.view || !sg.own) return RET_OK;
    done = cc_build_done();
    if (done != sg.done) sg.done = done, sg_retry();
    if (done >= cc_build_total()) {
        sg_build_end();
        return RET_OK;
    }
    sg.build_timer = timer_add(sg_on_build, (void *)0, SG_BUILD_MS);
    if (!sg.build_timer) sg_build_end();
    return RET_OK;
}

static int sg_first(void) {
    int a = sg_row_from(sg_off() < 0 ? 0 : sg_off());
    return a < 0 ? 0 : a;
}

static int sg_on_build_start(const void *unused) {
    int c, lo, hi, i, seen_n = 0;
    unsigned seen[2 * SG_BUILD_N + 1];
    (void)unused;
    sg.build_timer = 0;
    if (!sg.view || !sg.count || sg.own || !sg_valid() || !cc_build_open(2 * SG_BUILD_N + 1, CC_MISSING)) return RET_OK;
    sg.own = 1;
    c = sg_first();
    sg.build_at = c;
    lo = c - SG_BUILD_N < 0 ? 0 : c - SG_BUILD_N, hi = c + SG_BUILD_N > (int)sg.count - 1 ? (int)sg.count - 1 : c + SG_BUILD_N;
    for (i = 0; i <= hi - lo; ++i) {   /* outward from the first in view: it, one after, one before, ... */
        int k, a;
        for (k = 0; k < 2; ++k) {
            unsigned key;
            int j;
            a = k ? c - i : c + i;
            if (a < lo || a > hi || (k && !i)) continue;
            key = sg.idx[a].key;
            for (j = 0; j < seen_n && seen[j] != key; ++j) {}
            if (j < seen_n) continue;
            seen[seen_n++] = key;
            if (cc_build_add(cc_str(deque_at(sg.list, (unsigned)a), REC_PATH), key) < 0) goto go;
        }
    }
go:
    if (!cc_build_start()) {   /* nothing missing, no card, no space, no thread: the set is already freed */
        sg.own = 0;
        return RET_OK;
    }
    sg.done = 0;
    sg.build_timer = timer_add(sg_on_build, (void *)0, SG_BUILD_MS);
    if (!sg.build_timer) sg_build_end();
    return RET_OK;
}

static void sg_build_later(void) {
    if (sg.view && sg.g.tiles && !sg.own && !sg.build_timer) sg.build_timer = timer_add(sg_on_build_start, (void *)0, SG_BUILD_START_MS);
}

/* The scroll_view's EVT_SCROLL (every change of its offset) and scroll end: the title, the direction, the loader and, when the page has gone far from where
 * the build looked, a new build. */
static int sg_on_scroll(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (!sg.view) return RET_OK;
    sg_dir();
    sg_title_update();
    sg_kick();
    if (sg_abs(sg_first() - sg.build_at) > SG_BUILD_MOVE && !sg_moving()) sg_build_later();
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * Reading the stock list
 */
static void sg_size(void) {
    int h = sg.count ? sg_content() : GRID_VIEW_H;
    widget_resize(sg.view, SG_W, h);
    widget_set_prop_int(sg.sv, "virtual_h", h);
}

/* "%d Selected" in the player's language, the number where the translation has its %d. */
static void sg_fmt(char *out, unsigned size, const char *f, int n) {
    char digits[12];
    unsigned o = 0, d = 0, i;
    for (i = (unsigned)(n < 0 ? 0 : n); d == 0 || i; i /= 10) digits[d++] = (char)('0' + i % 10);
    while (*f && o + 1 < size) {
        if (f[0] == '%' && f[1] == 'd') {
            while (d && o + 1 < size) out[o++] = digits[--d];
            f += 2;
        } else out[o++] = *f++;
    }
    out[o] = 0;
}

static int sg_tw(void *w, const unsigned *t) { return (int)(widget_measure_text(w, t) + 0.999f); }

/* The UTF-8 text on label w, cut with an ellipsis to the label's width, measured in its own style (grid_fit's rule: the longest prefix that fits with the
 * ellipsis after it, a binary search). At most SG_NAME_MAX wide chars are looked at. */
static void sg_fit(void *w, const char *text) {
    unsigned s[SG_NAME_MAX + 1], len = 0, lo, hi, i, o = 0, c;
    char out[4 * SG_NAME_MAX + 1];
    const unsigned *t;
    int room;
    if (!w) return;
    room = I(w, W_W);
    widget_set_text_utf8(w, text);
    t = widget_get_text(w);
    if (!t || sg_tw(w, t) <= room) return;
    while (t[len] && len < SG_NAME_MAX) s[len] = t[len], ++len;
    s[len] = 0;
    lo = 0, hi = len - 1;
    while (lo < hi) {
        unsigned mid = (lo + hi + 1) / 2, k0 = s[mid], k1 = s[mid + 1];
        s[mid] = ELLIPSIS, s[mid + 1] = 0;
        if (sg_tw(w, s) <= room) lo = mid;
        else hi = mid - 1;
        s[mid] = k0, s[mid + 1] = k1;
    }
    while (lo && s[lo - 1] == ' ') --lo;   /* no space before the ellipsis */
    s[lo] = ELLIPSIS, s[lo + 1] = 0;
    for (i = 0; s[i]; ++i) {   /* back to UTF-8 */
        c = s[i];
        if (c < 0x80) out[o++] = (char)c;
        else if (c < 0x800) out[o++] = (char)(0xc0 | c >> 6), out[o++] = (char)(0x80 | (c & 63));
        else if (c < 0x10000) out[o++] = (char)(0xe0 | c >> 12), out[o++] = (char)(0x80 | (c >> 6 & 63)), out[o++] = (char)(0x80 | (c & 63));
        else out[o++] = (char)(0xf0 | c >> 18), out[o++] = (char)(0x80 | (c >> 12 & 63)), out[o++] = (char)(0x80 | (c >> 6 & 63)), out[o++] = (char)(0x80 | (c & 63));
    }
    out[o] = 0;
    widget_set_text_utf8(w, out);
}

static const char *sg_name_text(void) { return sg.key ? TR(sg.key) : sg.name; }   /* a list's title */

/* The song count under the last row: "25 songs" (the key by n == 1, the number where the translation has its %d). */
static void sg_foot_text(void) {
    char buf[64];
    sg_fmt(buf, sizeof buf, TR(sg.count == 1 ? "%d song" : "%d songs"), (int)sg.count);
    widget_set_text_utf8(sg.foot, buf);
    widget_move(sg.foot, SG_HDR_X, sg_rows_end() + SG_FOOT_GAP);
}

static void sg_head(void) {   /* the navbar's title: "N Selected" in select mode, else "Songs" (in a language where it does not fit: none), else the list's, cut to fit */
    char buf[64];
    if (!sg.select) {
        const unsigned *t;
        if (!sg_lib()) {
            sg_fit(sg.title, sg_name_text());
            sg.title_fits = 1;
            return;
        }
        widget_set_tr_text(sg.title, "Songs");
        t = widget_get_text(sg.title);
        sg.title_fits = !t || sg_tw(sg.title, t) <= I(sg.title, W_W);   /* (no text, or no way to measure it: shown) */
        return;
    }
    sg_fmt(buf, sizeof buf, TR("%d Selected"), (int)sg.nsel);
    widget_set_text_utf8(sg.title, buf);
}

static int sg_rail_h(void) { return GRID_VIEW_H - sg_pad(); }

/* The rail's plan (the stock page's index shows A F K P U Z with two dots between: an image, search_icon.png): the letters it draws, as section numbers in sec[],
 * and how many (the return). At most SG_RAIL_ITEMS items fit: the sections' own letters when there are that few, else every k-th section (k from 2 up, until the
 * letters with a dot between each pair fit) with the first and the last always there (a multiple of k within half a step of the last gives way to it). A rail with
 * fewer letters than sections (the return < sg.nsec) has a dot between two letters: item 2j is letter j, item 2j + 1 a dot. */
static int sg_rail_plan(int *sec) {
    int n = sg.nsec, k, m, i;
    if (n <= SG_RAIL_ITEMS) {
        for (i = 0; i < n; ++i) sec[i] = i;
        return n;
    }
    for (k = 2;; ++k) {
        for (m = 0, i = 0; i < n - 1; i += k) sec[m++] = i;
        if (m > 1 && n - 1 - sec[m - 1] < (k + 1) / 2) --m;
        sec[m++] = n - 1;
        if (2 * m - 1 <= SG_RAIL_ITEMS) return m;
    }
}
static int sg_rail_span(int letters) { return (letters < sg.nsec ? 2 * letters - 1 : letters) * SG_RAIL_PITCH; }   /* the drawn height */

/* The rail widget is the drawn span plus SG_RAIL_PAD above and below, centred on the list the bar leaves (a touch further from the span reaches the rows, and the
 * wide column takes none of the rows' right edge or the pills outside it); inside it the span starts at SG_RAIL_PAD. There only when there are sections. */
static void sg_rail_fit(void) {
    int sec[SG_MAX_SEC], span;
    if (sg.nsec > 0) {
        span = sg_rail_span(sg_rail_plan(sec));
        widget_move(sg.rail, SG_RAIL_X, SG_LIST_Y + (sg_rail_h() - span) / 2 - SG_RAIL_PAD);
        widget_resize(sg.rail, SG_RAIL_W, span + 2 * SG_RAIL_PAD);
    }
    sg_show(sg.rail, sg.nsec > 0 && sg.count);
    sg_redraw_rail();
}

static void sg_ticks(void) {
    int i;
    for (i = 0; i < SG_SORT_ROWS; ++i) widget_set_visible(sg.tick[i], i == sg.sort, 0);
}

/* The sections of the stock Title order. It sorts by the whole title (toolsQueryDbTable's comparator) and the Initial is the scan's first surviving character, so the
 * two only roughly agree (a symbol that sorts after 'z', an accented letter, a dropped kana, a CJK title placed by its whole pinyin): the songs are not in runs of
 * equal letters (V2.1oGS made a section per run and fell back to a plain list over SG_MAX_SEC runs: on the device no headers, no rail). The list keeps the stock
 * order (the play queue), so the sections are the non-decreasing labelling of the songs that puts the most of them under their own letter: a stray stays in the
 * section around it and cannot open one early. One pass forward keeps m[r] = the most songs labelled correctly so far with a last label <= r and, per song, a
 * bit per rank that says the best for r came from a lower label; one pass back reads the labels off; a section starts where the label changes. 4 bytes per
 * song, for the duration of the call; no memory = a plain list. At most SG_RANKS sections. */
static void sg_sections(void) {
    unsigned *bits = calloc(sg.count, sizeof(unsigned)), i, b;
    int m[SG_RANKS], r, d, k, lab = SG_RANKS - 1, prev = -1;
    if (!bits) return;
    for (r = 0; r < SG_RANKS; ++r) m[r] = 0;
    for (i = 0; i < sg.count; ++i) {
        for (b = 0, k = sg.idx[i].letter, r = 0; r < SG_RANKS; ++r) {   /* m[r] still holds the previous song's value, m[r - 1] already this song's */
            d = m[r] + (r == k);
            if (r && m[r - 1] >= d) m[r] = m[r - 1], b |= 1u << r;      /* a tie takes the lower label: a section starts as late as it can */
            else m[r] = d;
        }
        bits[i] = b;
    }
    for (i = sg.count; i-- > 0;) {
        while (lab && (bits[i] >> lab & 1)) --lab;
        bits[i] = (unsigned)lab;
    }
    for (i = 0; i < sg.count; ++i)
        if ((int)bits[i] != prev) prev = (int)bits[i], sg.sec_start[sg.nsec] = i, sg.sec_letter[sg.nsec++] = sg_rank_letter(prev);
    free(bits);
}

/* The stock query again, and the page rebuilt from it: the index, the sections, the tiles. The library's albums are loaded first (once): both are stock queries
 * that replace *pdeq_showlist. */
static void sg_load(int keep) {
    unsigned i;
    int at = keep ? sg_off() : 0;
    void *list = (void *)0;
    if (sg.more_timer) timer_remove(sg.more_timer);
    sg.more_timer = 0;
    sg_build_end();
    grid_drop(&sg.g);
    free(sg.idx);
    free(sg.sel);
    sg.idx = (song_t *)0, sg.sel = (unsigned char *)0, sg.list = sg.first = (void *)0, sg.count = sg.nsel = 0, sg.nsec = 0, sg.press = sg.down = 0;
    if (!sg.albums_tried) {
        sg.albums_tried = 1;
        sg.albums = cc_albums();
    }
    sg.sort = sg_lib() ? *(int *)SORT_FLAG : 0;   /* (a list has the order of its query: sort_flag is the library's) */
    if (sg.sort < 0 || sg.sort >= SG_SORT_ROWS) sg.sort = 0;
    if (sg_query() > 0) list = *(void **)PDEQ_SHOWLIST;
    if (list) sg.count = deque_size(list);
    if (sg.count) {
        sg.idx = calloc(sg.count, sizeof(song_t));
        sg.sel = calloc((sg.count + 7) / 8, 1);
        if (!sg.idx || !sg.sel) {
            free(sg.idx);
            free(sg.sel);
            sg.idx = (song_t *)0, sg.sel = (unsigned char *)0, sg.count = 0;
        }
    }
    if (sg.count) {
        sg.list = list, sg.first = deque_at(list, 0);
        for (i = 0; i < sg.count; ++i) {
            void *rec = deque_at(list, i);
            sg.idx[i].key = cc_album_key(rec);
            sg.idx[i].letter = sg_rank(rec);
        }
        if (sg_lib() && sg.sort == 0) sg_sections();
    }
    grid_placeholder(&sg.g);
    sg_show(sg.view, sg.count != 0);
    sg_show(sg.status, sg.count == 0);
    if (!sg.count) widget_set_tr_text(sg.status, list ? "Not enough memory" : sg_lib() ? "Update Local Music first" : "No songs");
    sg_size();
    sg_foot_text();
    widget_set_prop_int(sg.sv, "yoffset", at < 0 ? 0 : at > sg_max_scroll() ? sg_max_scroll() : at);   /* a list read again keeps its place (or the last place there is) */
    sg.dir = 1;
    sg.seen = sg_off();
    sg.build_at = sg_first();
    sg_ticks();
    sg_rail_fit();
    sg_head();
    sg_title_update();
    sg_redraw();
    sg_kick();
    sg_build_later();
}

/* Another query replaced the stock list under a page that is on top (a paint found it): read it again. A page behind another reads it when it comes back. */
static int sg_on_stale(const void *unused) {
    (void)unused;
    sg.stale_timer = 0;
    if (sg.view && sg.g.tiles && !sg_valid() && pod_is_top(sg.win)) sg_load(1);
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * Playing: the stock Songs row's handler (@0x5275a4: loadSongList of the shown list, then Now Playing at the row), as Shuffle Songs does it (patch/shuffle.c)
 */
enum { SG_KEEP, SG_IN_ORDER, SG_SHUFFLE };   /* the play mode a start sets: a row tap keeps it (as stock), Play plays in order, a list's Shuffle shuffles */

/* Song `at` (-1: a random one) of the list and the list as the queue, in Now Playing. */
static void sg_play_at(int at, int how) {
    void *pick, *queue, *first;
    unsigned n, idx = 0;
    int found;
    struct {
        void *dq;
        int idx, cls, mode;
    } context;
    if (!sg_valid()) {
        sg_load(1);
        return;
    }
    if (at < 0 && sg.count) at = (int)pod_rand(sg.count);
    if (at < 0 || at >= (int)sg.count) return;
    pick = deque_at(sg.list, (unsigned)at);
    queue = _create_deque("stSongInfo");
    if (!queue) return;
    deque_init(queue);
    sg_classinfo();   /* loadSongList runs the class query again and keeps classinfo for the memory playback */
    found = loadSongList(queue, cc_str(pick, REC_NAME), I(pick, REC_CUE_START), sg.cls);
    n = deque_size(queue);
    if (n) {   /* loadSongList finds a song by file name and CUE start: a duplicate name (01.flac) would always start at the first, so the row's own index wins */
        if ((unsigned)at < n && !strcmp(cc_str(deque_at(queue, (unsigned)at), REC_PATH), cc_str(pick, REC_PATH))) idx = (unsigned)at;
        else if (found >= 0 && (unsigned)found < n) idx = (unsigned)found;
    }
    first = n ? deque_at(queue, idx) : (void *)0;
    if (!first || access(cc_str(first, REC_PATH), F_OK)) {
        deque_destroy(queue);
        pod_toast(TR(n ? "Storage unavailable" : "Update Local Music first"));
        return;
    }
    if (how == SG_IN_ORDER) pod_set_in_order();   /* Play: the list in order, even after a Shuffle; a row tap keeps the mode, as stock */
    else if (how == SG_SHUFFLE) pod_set_mode(MODE_SHUFFLE);
    *(int *)G_CLASS_TYPE = sg.cls;   /* as allmusic_page_init leaves it */
    context.dq = queue, context.idx = (int)idx, context.cls = sg.cls, context.mode = PLAY_MODE;
    navigator_to_with_context("playing_page", &context);   /* start_player copies the queue */
    deque_destroy(queue);
}

static int sg_on_play(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (sg.view && sg.count) sg_play_at(0, SG_IN_ORDER);
    return RET_OK;
}

/* Shuffle: the library through Shuffle Songs (patch/shuffle.c: the stock Shuffle mode from a random song; it reads the list again: this page reads it when it is
 * back); a list in the stock Shuffle mode from a random song of its own, as the album page's Shuffle. */
static int sg_on_shuffle(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (!sg.view || !sg.count) return RET_OK;
    if (sg_lib()) shuffle_play(0);
    else sg_play_at(-1, SG_SHUFFLE);
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The select mode
 */
static void sg_select(int on) {
    int i;
    void *nav[4];
    if (on == sg.select) return;
    sg.select = on;
    sg.nsel = 0;
    if (sg.sel) memset(sg.sel, 0, (sg.count + 7) / 8);
    sg.press = sg.down = 0;
    nav[0] = sg.btn_search, nav[1] = sg.btn_sort, nav[2] = sg.btn_select, nav[3] = sg.np;
    for (i = 0; i < 4; ++i) sg_show(nav[i], !on && (i != 1 || sg_lib()) && (i != 0 || !sg_genre()));   /* (a list has no Sort, a genre's songs no Search) */
    sg_show(sg.btn_selall, on);
    sg_show(sg.bar, on);
    widget_set_sensitive(sg.btn_play, !on);   /* the pills stay in the content, dim and dead (their disabled style) */
    widget_set_sensitive(sg.btn_shuffle, !on);
    widget_resize(sg.title, (on ? SG_SELALL_X : sg_search_x()) - NAV_TITLE_X, 22);
    widget_set_prop_str(sg.back, "style:normal:icon", on ? "ah_nav_close" : "ah_nav_back");
    widget_set_prop_str(sg.back, "style:over:icon", on ? "ah_nav_close" : "ah_nav_back");
    widget_set_prop_str(sg.back, "style:pressed:icon", on ? "ah_nav_close_down" : "ah_nav_back_down");
    sg.title_on = -1;
    sg_head();
    sg_title_update();
    sg_retext();
    sg_size();
    if (sg_off() > sg_max_scroll()) widget_set_prop_int(sg.sv, "yoffset", sg_max_scroll());
    sg_rail_fit();
    sg_redraw();
}

static void sg_count_changed(void) {
    sg_head();
    sg_redraw();
}

static void sg_toggle(int i) {
    if (i < 0 || i >= (int)sg.count || !sg.sel) return;
    sg.sel[i >> 3] ^= (unsigned char)(1 << (i & 7));
    sg.nsel += sg_is_sel(i) ? 1 : (unsigned)-1;
    sg_count_changed();
}

static int sg_on_selall(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (!sg.select || !sg.sel) return RET_OK;
    if (sg.nsel < sg.count) {   /* all, unless all are: then none */
        unsigned i;
        memset(sg.sel, 0, (sg.count + 7) / 8);
        for (i = 0; i < sg.count; ++i) sg.sel[i >> 3] |= (unsigned char)(1 << (i & 7));
        sg.nsel = sg.count;
    } else {
        memset(sg.sel, 0, (sg.count + 7) / 8);
        sg.nsel = 0;
    }
    sg_count_changed();
    return RET_OK;
}

/* The page's selection into the stock one: a vector of ints as long as the shown list, 1 for each selected row. */
static int sg_stock_selection(void) {
    unsigned i;
    if (!sg_valid() || !*(void **)SEL_VEC) return 0;
    select_recordinit((int)sg.count);
    for (i = 0; i < sg.count; ++i)
        if (sg_is_sel((int)i)) set_selectindex((int)i);
    return 1;
}

static void sg_ask(const char *text, int kind, int *answer) {   /* the stock confirm dialog: modal, the button pressed is the result */
    struct {
        int kind, ms;
        char text[MSGINFO_TEXT], text2[MSGINFO_TEXT];
    } info;
    unsigned i;
    memset(&info, 0, sizeof info);
    info.kind = kind;
    for (i = 0; text[i] && i < sizeof info.text - 1; ++i) info.text[i] = text[i];
    *answer = navigator_to_with_context("dialog/confirminfo_dialog", &info);
}

/* Delete: the stock handler's sequence (@0x527f48): nothing selected is a message; the confirm dialog (0xa: the library only, 0x14: the files too); then
 * batch_delete_file on the shown list and the selection; the message. The stock handler leaves the list as it was (the page rebuilds on its next show): this page reads it again.
 * The class is the list's, as the stock handler passes g_class_type: batch_delete_file removes the songs from the library (the generic loop: the library, Hi-Res,
 * Recently Added), from myfav, oftenplay, recentplay or the playlist (its jump tables @0x74b7b0, @0x74b7d4; docs/modules/addresses.md), and the files when asked. */
static int sg_on_delete(void *ctx, void *e) {
    int r;
    (void)ctx; (void)e;
    if (!sg.select) return RET_OK;
    if (!sg.nsel) {
        pod_toast(TR("msg_delsongfailed"));
        return RET_OK;
    }
    sg_ask(TR("msg_delsong"), CONFIRM_KIND_DELETE, &r);
    if (r != CONFIRM_DELETE_LIBRARY && r != CONFIRM_DELETE_FILE) return RET_OK;
    if (!sg_stock_selection()) {
        sg_select(0);
        sg_load(1);
        return RET_OK;
    }
    batch_delete_file(sg.cls, sg.list, *(void **)SEL_VEC, 0, r == CONFIRM_DELETE_FILE);
    pod_toast(TR("msg_delsongsuccess"));
    sg_select(0);
    sg_load(1);
    return RET_OK;
}

/* Add to playlist: the stock Add button's path (@0x5280c0) to its playlist picker: playlist_page with the add context; tapping a playlist there adds the
 * selection (batch_add_file on *pdeq_showlist and the vector) and closes the picker. The title the picker may overwrite and the browsing class it sets are put back
 * when this window comes to the front. */
static int sg_on_add(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (!sg.select) return RET_OK;
    if (!sg.nsel) {
        pod_toast(TR("msg_addfailed"));
        return RET_OK;
    }
    if (!sg_stock_selection()) {
        sg_select(0);
        sg_load(1);
        return RET_OK;
    }
    memcpy(sg.title_save, (void *)NAV_TITLE, sizeof sg.title_save);
    *(int *)NAVIGATION_STATUS = 0;   /* the picker's mode is a page that is not in multi-select (@0x53d300 tests navigation_status != 1) */
    sg.picker = 1;
    navigator_to_with_context("playlist_page", (const void *)(long)(PICKER_ADD | sg.cls));   /* batch_add_file takes the class from it, as from the stock button */
    return RET_OK;
}

static int sg_on_back(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (sg.select) sg_select(0);
    else navigator_back();
    return RET_OK;
}

static int sg_on_select(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (sg.view && sg.count && !sg.menu) sg_select(1);
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * Touch on the rows (the Albums list's: DOWN remembers, ABORT forgets, UP within the drag threshold on the same row acts)
 */
static int sg_item_of(void *e) {
    int pt[2];
    pt[0] = I(e, PE_X), pt[1] = I(e, PE_Y);
    widget_to_local(sg.view, pt);
    return sg_at(pt[1]);
}

static void sg_set_press(int p) {
    if (sg.press == p) return;
    sg.press = p;
    sg_redraw();
}

static int sg_on_down(void *ctx, void *e) {
    int a;
    (void)ctx;
    sg.down = 0;
    if (!e || !sg.view || !sg.count || !sg_valid()) return RET_OK;
    a = sg_item_of(e);
    sg.down = a + 1, sg.down_x = I(e, PE_X), sg.down_y = I(e, PE_Y);
    if (!sg.select) sg_set_press(a + 1);
    return RET_OK;
}

static int sg_on_up(void *ctx, void *e) {
    int a = sg.down - 1;
    (void)ctx;
    sg.down = 0;
    sg_set_press(0);
    if (a < 0 || !e || !sg.view) return RET_OK;
    if (sg_abs(I(e, PE_X) - sg.down_x) < SG_TAP_PX && sg_abs(I(e, PE_Y) - sg.down_y) < SG_TAP_PX && sg_item_of(e) == a) {
        if (sg.select) sg_toggle(a);
        else sg_play_at(a, SG_KEEP);
    }
    return RET_OK;
}

static int sg_on_abort(void *ctx, void *e) {
    (void)ctx; (void)e;
    sg.down = 0;
    sg_set_press(0);
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The rail
 */
static void sg_bubble(int i) {   /* the bubble shows section i's letter, or hides */
    char s[2];
    if (i < 0) {
        widget_set_visible(sg.bubble, 0, 0);
        return;
    }
    s[0] = (char)sg.sec_letter[i], s[1] = 0;
    widget_set_text_utf8(sg.bubble_letter, s);
    widget_set_visible(sg.bubble, 1, 0);
}

/* Section i's header at the window's top (clamped); a coasting list stops first. */
static void sg_jump(int i) {
    int v = i ? sg_hdr_y(i) : 0, max = sg_max_scroll();   /* (the first section: the top, the large title and the pills with it) */
    void *wa = P(sg.sv, SC_WA);
    if (wa && I(wa, SC_AN_STATE) == SC_AN_RUNNING && P(wa, SC_AN_WIDGET) == sg.sv) {   /* patch/scroll.c sc_down */
        widget_animator_destroy(wa);
        stock_scroll_done(sg.sv, (void *)0);
    }
    widget_set_prop_int(sg.sv, "yoffset", v > max ? max : v);
}

static void sg_rail_set(int i) {
    if (i == sg.rail_i && sg.rail_on) return;
    sg.rail_i = i;
    sg.rail_on = 1;
    sg_jump(i);
    sg_bubble(i);
    sg_redraw_rail();
}

static void sg_rail_end(void) {
    if (!sg.grab) return;
    sg.grab = sg.rail_on = 0;
    widget_ungrab(sg.win, sg.rail);
    sg_bubble(-1);
    sg_redraw_rail();
}

/* DOWN grabs the touch (the moves and the release come here wherever they go), every position sets the letter under it (above the first and below the last: those). */
static int sg_on_rail(void *ctx, void *e) {
    int type, pt[2], i, l, sec[SG_MAX_SEC];
    (void)ctx;
    if (!e || !sg.view || !sg.nsec) return RET_OK;
    type = I(e, 0);
    if (type == EVT_POINTER_UP || type == EVT_POINTER_ABORT) {
        sg_rail_end();
        return RET_OK;
    }
    if (type == EVT_POINTER_DOWN) {
        if (!sg.grab) widget_grab(sg.win, sg.rail);
        sg.grab = 1, sg.rail_on = 0;   /* a new touch: its first letter always sets */
    } else if (!sg.grab) return RET_OK;
    pt[0] = I(e, PE_X), pt[1] = I(e, PE_Y);
    widget_to_local(sg.rail, pt);
    l = sg_rail_plan(sec);   /* the drawn span, however many letters it shows, is split into the sections: every one is reachable */
    i = pt[1] < SG_RAIL_PAD ? 0 : (pt[1] - SG_RAIL_PAD) * sg.nsec / sg_rail_span(l);   /* (the span starts SG_RAIL_PAD down the widget) */
    if (i > sg.nsec - 1) i = sg.nsec - 1;
    sg_rail_set(i);
    return RET_OK;
}

/* Alignment (tools/pod_ui.py rail_metrics derives the two numbers from the tree's own font and pod.py writes them to stock.h):
 * vertically the 12 px text box of a 13 px item sits at its top and the baseline int(ascender * scale) lower, so the cap ink centre is SG_RAIL_INK2 / 2 below the
 * item's top; a dot goes where the midpoint of two letters' ink centres is (one item below the upper letter's centre: the letters are two items apart), so its top is
 * (INK2 - DOT) / 2 into its item, and the disc is centred on the same line. Horizontally canvas_draw_text_in_rect puts a text of measured width lw (the truncated
 * advances + 1 px per glyph) at rect.x + (rect.w - lw) / 2, integer: so the rect is SG_RAIL_TEXT_W wide, centred on the dots' x and moved by the letter's own
 * SG_RAIL_DX so the ink (not the advance) is centred on that x within half a pixel. */
static const signed char sg_rail_dx[27] = SG_RAIL_DX;   /* "#", A..Z */
#define SG_RAIL_DOT_Y ((SG_RAIL_INK2 - SG_RAIL_DOT) / 2)
#define SG_RAIL_DISC_Y (-((SG_RAIL_DISC - SG_RAIL_INK2 + 1) / 2))   /* floor((INK2 - DISC) / 2), negative: the disc starts above the item */

/* The rail (its own EVT_AFTER_PAINT, the rail's coordinates, the span from SG_RAIL_PAD): the plan's letters, a dot between two of them when the plan skips sections,
 * the touched letter (when it is a drawn one) on its disc with a black letter. */
static int sg_on_rail_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int j, k, l, y0 = SG_RAIL_PAD, step, dots, pass, rect[4], sec[SG_MAX_SEC];
    unsigned w[2];
    (void)ctx;
    if (!canvas || !sg.nsec || !sg.view) return RET_OK;
    l = sg_rail_plan(sec);
    dots = l < sg.nsec;
    step = dots ? 2 : 1;   /* the items a letter takes with the dot after it */
    if (dots) {
        int x = SG_RAIL_CX - SG_RAIL_X - SG_RAIL_DOT / 2;
        canvas_set_fill_color(canvas, SG_RAIL_DOT_RGB);
        for (j = 0; j + 1 < l; ++j) {   /* a dot of four pixels: the cross of two bars cuts its corners */
            int y = y0 + (step * j + 1) * SG_RAIL_PITCH + SG_RAIL_DOT_Y;
            canvas_fill_rect(canvas, x, y + 1, SG_RAIL_DOT, SG_RAIL_DOT - 2);
            canvas_fill_rect(canvas, x + 1, y, SG_RAIL_DOT - 2, SG_RAIL_DOT);
        }
    }
    if (sg.rail_on && sg.disc) {
        for (j = 0; j < l; ++j) {
            if (sec[j] == sg.rail_i) {
                int src[4], dst[4];
                src[0] = src[1] = 0, src[2] = src[3] = SG_RAIL_DISC;
                dst[0] = SG_RAIL_CX - SG_RAIL_X - SG_RAIL_DISC / 2, dst[1] = y0 + step * j * SG_RAIL_PITCH + SG_RAIL_DISC_Y, dst[2] = dst[3] = SG_RAIL_DISC;
                canvas_draw_image(canvas, sg.disc, src, dst);
            }
        }
    }
    for (pass = 0; pass < 2; ++pass) {   /* the others, then the touched one (black) */
        if (pass && !sg.rail_on) break;
        widget_prepare_text_style(pass ? sg.st_rail_on : sg.st_rail, canvas);
        for (j = 0; j < l; ++j) {
            if ((sec[j] == sg.rail_i && sg.rail_on) != pass) continue;
            w[0] = sg.sec_letter[sec[j]], w[1] = 0;
            k = w[0] >= 'A' && w[0] <= 'Z' ? (int)w[0] - 'A' + 1 : 0;
            rect[0] = SG_RAIL_CX - SG_RAIL_X - SG_RAIL_TEXT_W / 2 + sg_rail_dx[k], rect[1] = y0 + step * j * SG_RAIL_PITCH, rect[2] = SG_RAIL_TEXT_W, rect[3] = SG_RAIL_PITCH;
            canvas_draw_text_in_rect(canvas, w, 1, rect);
        }
    }
    return RET_OK;
}

/* The disc: SG_RAIL_DISC px, the accent colour, four corners of radius SG_RAIL_DISC / 2 cut in the alpha (a disc). */
static void sg_make_disc(void) {
    unsigned char tab[(SG_RAIL_DISC / 2) * (SG_RAIL_DISC / 2)];
    unsigned *px;
    unsigned x, y, k, r = SG_RAIL_DISC / 2;
    void *b = bitmap_create_ex(SG_RAIL_DISC, SG_RAIL_DISC, SG_RAIL_DISC * 4, BITMAP_RGBA8888);
    if (!b) return;
    px = (unsigned *)bitmap_lock_buffer_for_write(b);
    if (!px || bitmap_get_line_length(b) != SG_RAIL_DISC * 4) {
        if (px) bitmap_unlock_buffer(b);
        bitmap_destroy(b);
        return;
    }
    pod_corner_fill(tab, r);
    for (y = 0; y < SG_RAIL_DISC * SG_RAIL_DISC; ++y) px[y] = SG_ACCENT;
    for (k = 0; k < 4; ++k)
        for (y = 0; y < r; ++y)
            for (x = 0; x < r; ++x) {
                unsigned *p = px + (k & 2 ? 2 * r - 1 - y : y) * 2 * r + (k & 1 ? 2 * r - 1 - x : x);
                *p = (*p & 0xffffff) | (255u - tab[y * r + x]) << 24;
            }
    bitmap_unlock_buffer(b);
    sg.disc = b;
}

/* A select mark: the stock image (26 px) as a bitmap. */
static void *sg_make_mark(const char *name) {
    unsigned *px;
    void *b = bitmap_create_ex(SG_MARK, SG_MARK, SG_MARK * 4, BITMAP_RGBA8888);
    int ok;
    if (!b) return b;
    px = (unsigned *)bitmap_lock_buffer_for_write(b);
    if (!px || bitmap_get_line_length(b) != SG_MARK * 4) {
        if (px) bitmap_unlock_buffer(b);
        bitmap_destroy(b);
        return (void *)0;
    }
    ok = cc_decode(sg.win, name, 1, SG_MARK, 1, px);
    bitmap_unlock_buffer(b);
    if (!ok) {
        bitmap_destroy(b);
        return (void *)0;
    }
    *(unsigned short *)((char *)b + BITMAP_FLAGS) |= 1;   /* opaque: over black */
    return b;
}

/* ---------------------------------------------------------------------------
 * The sort card: the stock sort dialog's five labels under the Sort button; a row sets the stock order (@0x47d114: sort_flag and [SYSSET] SORTSELECT), the list is read again
 */
static void sg_menu(int on) {
    sg.menu = on;
    if (on) sg_ticks();
    sg_show(sg.scrim, on);
    sg_show(sg.card, on);
}

static int sg_on_sort(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (sg.view && !sg.select && sg_lib()) sg_menu(!sg.menu);
    return RET_OK;
}

static int sg_on_scrim(void *ctx, void *e) {
    (void)ctx; (void)e;
    sg_menu(0);
    return RET_OK;
}

static int sg_on_item(void *ctx, void *e) {
    int k = (int)(long)ctx;
    (void)e;
    sg_menu(0);
    if (!sg.view || k < 0 || k >= SG_SORT_ROWS || k == *(int *)SORT_FLAG) return RET_OK;
    *(int *)SORT_FLAG = k;
    write_int_config(k, "SYSSET", "SORTSELECT");
    sg_load(0);
    return RET_OK;
}

/* Search: the stock page (@0x52704c: navigator_to("search_page"), nothing set first). The list it leaves in *pdeq_showlist makes this page read it again when it is back. */
static int sg_on_search(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (sg.view && !sg.select && !sg.menu) navigator_to_with_context("search_page", (const void *)0);
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The pills: the glyph and the label centred as a pair SG_PILL_GAP apart (the album page's Play all, patch/albuminfo.c ah_centre_pill): AWTK puts the glyph in a
 * square as high as the button at margin_left and the text at the square's end plus the spacer.
 */
static void sg_centre_pill(void *btn, int pw) {
    static const char *const key[5] = {"normal:", "pressed:", "over:", "focused:", "disable:"};
    static const char *const prop[5] = {"margin_left", "icon_at", "margin_right", "spacer", "text_align_h"};
    const unsigned *text = widget_get_text(btn);
    float w = text && *text ? widget_measure_text(btn, text) : 0.0f;
    int tw = (int)(w + 0.999f), margin, i, j;
    unsigned v[4], val[5];   /* value_t: type at 0, the uint32 at 8 */
    char name[32];
    if (!text || !*text) return;   /* (a text that cannot be measured is taken as 0 px wide: the glyph is still put at the left, not above the text as the automatic icon position would) */
    if (tw > pw - (SG_PILL_H - SG_PILL_GLYPH) / 2 - SG_PILL_GLYPH - SG_PILL_GAP) {   /* too wide beside the glyph (ru "Перемешать"): the label steps down to
                                                                                      * SG_PILL_PX_SMALL, as an iOS button shrinks its title, and is measured again */
        for (i = 0; i < 5; ++i) {
            unsigned k = 0, m = 0;
            static const char fs[] = "font_size";
            while (key[i][k]) name[k] = key[i][k], ++k;
            while (fs[m]) name[k++] = fs[m++];
            name[k] = 0;
            memset(v, 0, sizeof v);
            value_set_uint32(v, SG_PILL_PX_SMALL);
            widget_set_style(btn, name, v);
        }
        w = widget_measure_text(btn, text);
        tw = (int)(w + 0.999f);
    }
    margin =(pw - (SG_PILL_GLYPH + SG_PILL_GAP + tw)) / 2 - (SG_PILL_H - SG_PILL_GLYPH) / 2;
    if (margin < 0) margin = 0;
    val[0] = (unsigned)margin, val[1] = 1, val[2] = 0, val[3] = (unsigned)(SG_PILL_GAP - (SG_PILL_H - SG_PILL_GLYPH) / 2), val[4] = 2;   /* icon_at left, text_align_h left */
    for (j = 0; j < 5; ++j) {
        memset(v, 0, sizeof v);
        value_set_uint32(v, val[j]);
        for (i = 0; i < 5; ++i) {
            unsigned k = 0, m = 0;
            while (key[i][k]) name[k] = key[i][k], ++k;
            while (prop[j][m]) name[k++] = prop[j][m++];
            name[k] = 0;
            widget_set_style(btn, name, v);
        }
    }
}

/* ---------------------------------------------------------------------------
 * The window
 */
static int sg_on_fg(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (!sg.view || !sg.g.tiles) return RET_OK;
    if (sg.picker) {   /* back from the stock playlist picker: its title and class put back, the add done (it changed the records it added), select mode over */
        sg.picker = 0;
        *(int *)G_CLASS_TYPE = sg.cls;
        memcpy((void *)NAV_TITLE, sg.title_save, sizeof sg.title_save);
        sg_select(0);
        sg_load(1);
    } else if (!sg_valid() || !sg_lib()) sg_load(1);   /* a list is read every time: playing changes Recently Played and Most Played, Now Playing's star the Favourites */
    sg_build_later();
    return RET_OK;
}

static int sg_on_bg(void *ctx, void *e) {
    sg_rail_end();
    return sg_on_abort(ctx, e);
}

static int sg_on_destroy(void *ctx, void *e) {
    int i;
    (void)ctx; (void)e;
    if (sg.more_timer) timer_remove(sg.more_timer);
    if (sg.stale_timer) timer_remove(sg.stale_timer);
    sg_build_end();
    grid_free(&sg.g);
    if (sg.albums) deque_destroy(sg.albums);
    if (sg.disc) bitmap_destroy(sg.disc);
    for (i = 0; i < 2; ++i)
        if (sg.mark[i]) bitmap_destroy(sg.mark[i]);
    free(sg.idx);
    free(sg.sel);
    memset(&sg, 0, sizeof sg);
    return RET_OK;
}

/* The page listing class cls (pl_id: a playlist's id; key: the title's key, or 0 for name). 0 once the page is up, -1 if the window could not open, -2 if the
 * asset is not ours (the page is left again). */
static int sg_open_page(int cls, int pl_id, const char *key, const char *name) {
    static const char *const ITEMS[SG_SORT_ROWS] = {"sg_item0", "sg_item1", "sg_item2", "sg_item3", "sg_item4"};
    static const char *const TICKS[SG_SORT_ROWS] = {"sg_tick0", "sg_tick1", "sg_tick2", "sg_tick3", "sg_tick4"};
    int i;
    if (sg.win) return -1;
    memset(&sg, 0, sizeof sg);
    sg.cls = cls, sg.pl_id = pl_id, sg.key = key;
    if (cls == CLASS_ARTIST_SONGS) memcpy(sg.ci, (void *)CLASSINFO, CLASSINFO_SIZE);   /* songs_open_artist ran the two queries just before */
    for (i = 0; name[i] && i < (int)sizeof sg.name - 1; ++i) sg.name[i] = name[i];
    if (name[i])   /* a name cut short is cut before a character, not inside one */
        while (i > 0 && ((unsigned char)name[i] & 0xc0) == 0x80) --i;
    sg.name[i] = 0;
    sg.win = window_open("m1plus_songs");
    if (!sg.win) return -1;
    widget_on(sg.win, EVT_DESTROY, sg_on_destroy, (void *)0);
    sg.back = pod_bind(sg.win, "btn_return", sg_on_back, (void *)0);
    sg.np = pod_bind(sg.win, "btn_backtoplayer", pod_on_player, (void *)0);
    sg.btn_search = pod_bind(sg.win, "btn_search", sg_on_search, (void *)0);
    sg.btn_sort = pod_bind(sg.win, "btn_sort", sg_on_sort, (void *)0);
    sg.btn_select = pod_bind(sg.win, "btn_select", sg_on_select, (void *)0);
    sg.btn_selall = pod_bind(sg.win, "btn_selall", sg_on_selall, (void *)0);
    sg.btn_play = pod_bind(sg.win, "btn_play", sg_on_play, (void *)0);
    sg.btn_shuffle = pod_bind(sg.win, "btn_shuffle", sg_on_shuffle, (void *)0);
    sg.btn_add = pod_bind(sg.win, "sg_add", sg_on_add, (void *)0);
    sg.btn_del = pod_bind(sg.win, "sg_del", sg_on_delete, (void *)0);
    sg.scrim = pod_bind(sg.win, "sg_scrim", sg_on_scrim, (void *)0);
    sg.card = widget_lookup(sg.win, "sg_card", 1);
    sg.title = widget_lookup(sg.win, "label_title", 1);
    sg.fade = widget_lookup(sg.win, "img_nb_fade", 1);   /* optional */
    sg.view = widget_lookup(sg.win, "view_grid", 1);
    sg.sv = widget_lookup(sg.win, "songs_scrollview", 1);
    sg.status = widget_lookup(sg.win, "label_status", 1);
    sg.st_title = widget_lookup(sg.win, "label_row_title", 1);
    sg.st_sub = widget_lookup(sg.win, "label_row_sub", 1);
    sg.st_hdr = widget_lookup(sg.win, "label_hdr", 1);
    sg.st_rail = widget_lookup(sg.win, "label_rail", 1);
    sg.st_rail_on = widget_lookup(sg.win, "label_rail_on", 1);
    sg.rail = widget_lookup(sg.win, "sg_rail", 1);
    sg.bubble = widget_lookup(sg.win, "sg_bubble", 1);
    sg.bubble_letter = widget_lookup(sg.win, "sg_bubble_letter", 1);
    sg.bar = widget_lookup(sg.win, "sg_bar", 1);
    sg.big = widget_lookup(sg.win, "sg_title", 1);   /* optional: the large title */
    sg.foot = widget_lookup(sg.win, "sg_foot", 1);
    if (!sg.foot || !sg.back || !sg.np || !sg.btn_search || !sg.btn_sort || !sg.btn_select || !sg.btn_selall || !sg.btn_play || !sg.btn_shuffle || !sg.btn_add || !sg.btn_del ||
        !sg.scrim || !sg.card || !sg.title || !sg.view || !sg.sv || !sg.status || !sg.st_title || !sg.st_sub || !sg.st_hdr || !sg.st_rail || !sg.st_rail_on ||
        !sg.rail || !sg.bubble || !sg.bubble_letter || !sg.bar) {
        navigator_back();   /* an asset that is not ours */
        return -2;
    }
    for (i = 0; i < SG_SORT_ROWS; ++i) {
        sg.tick[i] = widget_lookup(sg.win, TICKS[i], 1);
        if (!sg.tick[i] || !pod_bind(sg.win, ITEMS[i], sg_on_item, (void *)(long)i)) {
            navigator_back();
            return -2;
        }
    }
    sg_menu(0);
    if (!sg_lib()) {   /* a list: no Sort; Search (the capsule's left cap) moves to Sort's slot, beside Select, and the titles are the list's */
        sg_show(sg.btn_sort, 0);
        if (sg_genre()) {   /* a genre's songs: no Search either; Select is the capsule's left cap (its own glass piece) */
            sg_show(sg.btn_search, 0);
            widget_set_prop_str(sg.btn_select, "style:normal:icon", "pod_nav_selectl");
            widget_set_prop_str(sg.btn_select, "style:over:icon", "pod_nav_selectl");
            widget_set_prop_str(sg.btn_select, "style:pressed:icon", "pod_nav_selectl_down");
        } else widget_move(sg.btn_search, NAV_CF_X, 0);
        widget_resize(sg.title, sg_search_x() - NAV_TITLE_X, 22);
        sg_fit(sg.big, sg_name_text());
    }
    sg_centre_pill(sg.btn_play, SG_PILL_W);
    sg_centre_pill(sg.btn_shuffle, SG_PILL_W);
    sg_centre_pill(sg.btn_add, SG_BAR_PILL_W);
    sg_centre_pill(sg.btn_del, SG_BAR_PILL_W);
    sg_make_disc();
    sg.mark[0] = sg_make_mark("unselect");
    sg.mark[1] = sg_make_mark("selected");
    if (!sg.mark[0] || !sg.mark[1]) sg.mark[0] = sg.mark[1] = (void *)0;   /* (one that did not decode is freed with the other at destroy: the pair is all or none) */
    sg.noscroll = !widget_on(sg.sv, EVT_SCROLL, sg_on_scroll, (void *)0) || !widget_on(sg.sv, EVT_SCROLL_END, sg_on_scroll, (void *)0);
    if (sg.noscroll) widget_set_visible(sg.title, 1, 0);   /* the large title's collapse needs the scroll events: without them the navbar keeps its title */
    sg.title_on = sg.noscroll;
    widget_on(sg.win, EVT_WINDOW_TO_FG, sg_on_fg, (void *)0);
    widget_on(sg.win, EVT_WINDOW_TO_BG, sg_on_bg, (void *)0);
    widget_on(sg.view, EVT_POINTER_DOWN, sg_on_down, (void *)0);
    widget_on(sg.view, EVT_POINTER_UP, sg_on_up, (void *)0);
    widget_on(sg.view, EVT_POINTER_ABORT, sg_on_abort, (void *)0);
    widget_on(sg.view, EVT_AFTER_PAINT, sg_on_paint, (void *)0);
    widget_on(sg.rail, EVT_POINTER_DOWN, sg_on_rail, (void *)0);
    widget_on(sg.rail, EVT_POINTER_MOVE, sg_on_rail, (void *)0);
    widget_on(sg.rail, EVT_POINTER_UP, sg_on_rail, (void *)0);
    widget_on(sg.rail, EVT_POINTER_ABORT, sg_on_rail, (void *)0);
    widget_on(sg.rail, EVT_AFTER_PAINT, sg_on_rail_paint, (void *)0);
    if (!grid_init(&sg.g, sg.win, GRID_TILES, LIST_ART, 0)) {
        grid_free(&sg.g);
        sg_show(sg.view, 0);
        sg_show(sg.rail, 0);
        sg_show(sg.status, 1);
        widget_set_tr_text(sg.status, "Not enough memory");
        return 0;
    }
    grid_shape(&sg.g, LIST_ART, LIST_R, 1);   /* the Albums list's covers: LIST_ART px, LIST_R corners cut in the alpha */
    *(int *)G_CLASS_TYPE = sg.cls;   /* as allmusic_page_init leaves it (@0x5289e8) */
    sg_load(0);
    return 0;
}

static int sg_open(int cls, int pl_id, const char *key, const char *name, int home) {
    int r = sg_open_page(cls, pl_id, key, name);
    if (r == -1 && !sg.win && home >= 0) return pod_home_open(home);
    return r;
}

/* The M1+ Music menu's Songs row. A window that will not open leaves the stock Songs page, through the Home dispatcher. 0 once something is requested. */
int songs_open(void) { return sg_open(CLASS_ALL_SONGS, 0, (const char *)0, "", HOME_MYMUSIC); }

/* The lists the menu's rows open on this page (tools/pod_pages.py ACT_LIST, the row's argument is the stock Home tile): the tile, its class, the title's key (the row's text). */
static const struct { int home, cls; const char *key; } SG_LISTS[] = {
    {HOME_FAV, CLASS_FAV, "Favorites"}, {HOME_RECENTADD, CLASS_RECENTADD, "Recently Added"}, {HOME_RECENT, CLASS_RECENT, "Recently Played"},
    {HOME_MOST, CLASS_OFTEN, "Most Played"}, {HOME_HIRES, CLASS_HIRES, "hr"},
};

/* A list row of the menu. A window that will not open, or a tile that is not one of the lists, leaves the tile's stock page. */
int songs_open_list(int home) {
    unsigned i;
    for (i = 0; i < sizeof SG_LISTS / sizeof SG_LISTS[0]; ++i)
        if (SG_LISTS[i].home == home) return sg_open(SG_LISTS[i].cls, 0, SG_LISTS[i].key, "", home);
    return pod_home_open(home);
}

/* The Playlists page's tap on playlist `id` called `name`: -1 when the page did not open (the caller opens the stock songs page). */
int songs_open_playlist(int id, const char *name) { return sg_open(CLASS_PLAYLIST_SONGS, id, (const char *)0, name, -1); }

/* The Genres page's tap on the genre `name` (unknown: its Unknown Genre row): the genre's songs, titled with the name. A window that will not open leaves the stock row tap's
 * own sequence (@0x535c4c: the browsing record, then allmusic_page with 0xff09; the stock query sets the page's title), so the stock Songs page opens. */
int songs_open_genre(const char *name, int unknown) {
    int r = sg_open(CLASS_GENRE_SONGS, unknown != 0, (const char *)0, name, -1);
    if (r == -1 && !sg.win) {
        sg_genre_info(name, unknown);
        navigator_to_with_context("allmusic_page", (const void *)CLASS_GENRE_SONGS);
    }
    return r;
}

/* Cover Flow's artist page (`artist`: the Artists row, the name in REC_TITLE): every song of the artist, the way the stock All songs card gets them:
 * loadAlbumList(0xf004, artist) fills the browsing record and the albums, the last one the All songs row, and loadAlbumdetailList(0xff01, that row) turns
 * the record into class 0xff11's (the all-songs flag, the album text, classinfo[0]). The page keeps the record. -1 when the page did not open or the
 * artist has no All songs row (the caller opens the stock page). */
int songs_open_artist(void *artist) {
    void *list, *row;
    unsigned n;
    if (sg.win || !artist) return -1;
    loadAlbumList(CLASS_ARTISTS, artist);
    list = *(void **)PDEQ_SHOWLIST;
    n = list ? deque_size(list) : 0;
    row = n ? deque_at(list, n - 1) : (void *)0;
    if (!row || I(row, REC_ID) != ID_ALL_SONGS) return -1;
    loadAlbumdetailList(CLASS_ARTIST_ALBUMS, row);
    return sg_open(CLASS_ARTIST_SONGS, 0, (const char *)0, cc_str(artist, REC_TITLE), -1);
}
