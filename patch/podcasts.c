/* M1+ Music Podcasts: the shows on the card and their episodes, one page with two levels.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * Resume, played marks and speed per show follow q2-pod; the data is patch/pcmodel.c's.
 *
 * ui/m1plus_podcasts.bin is the Albums page's structure (docs/modules/albums.md): the navbar over a stock list, list_view > scroll_view, whose ONE child, view_grid, paints
 * the rows itself in its EVT_AFTER_PAINT (no widget per row), so a show of hundreds of episodes costs a tile ring. The window is opened by the Extras item Podcasts and has two
 * levels, switched in place (the Pod's way: no second window; the navbar's Back goes up a level before it leaves the page):
 *
 *   Shows      a row per folder of /mnt/mmc/Podcasts: the cover (cover.jpg / folder.jpg, a PC_ROW_H list row's LIST_ART px cover), the show's name, "N episodes".
 *   Show       a header (the PC_HDR_ART px cover, the name, the episode count and the show's speed: a tap on the speed cycles 1x 1.25x 1.5x 2x and is kept), then a row per
 *              downloaded episode, newest first: the title (bright when unplayed, grey when played or not on the card), a grey line "date - N min left" / "date - N min" / "date - Played".
 *              A tap on the row plays this episode and the ones after it in the list's order (from the first second, or from the saved place: pc_note jumps there).
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
#include "pcnet.h"

extern void pod_toast(const char *text); /* patch/shuffle.c: the stock message box */
extern void pod_set_in_order(void); /* patch/shuffle.c: Shuffle and Repeat one become List play */

#define I(w, off) (*(int *)((char *)(w) + (off)))
#define B(w, off) (*(unsigned char *)((char *)(w) + (off)))
#define P(w, off) (*(void **)((char *)(w) + (off)))

#define PG_W 320
#define PG_LOAD_MS 16
#define PG_TICK_MS 1000
#define PG_TAP_PX SC_DRAG_PX
#define PG_TEXT_X \
    16 /* an episode's texts start here (no cover, no dot: unplayed is a bright title), as the Feeds level's rows without a cover */
#define PG_TEXT_W 292 /* to the 12 px right margin */
#define PG_BOTTOM 12
#define PG_HDR_TEXT_X 124
#define PG_HDR_TEXT_W 184
#define PG_SPEED_Y 82 /* the speed text's top in the header; its touch area is PG_SPEED_H high from there */
#define PG_SPEED_H 34
#define PG_REC_SIZE 0x58
#define PG_ACT_X 16 /* the action rows (Refresh All, Import) of the Feeds level: no cover, the text from here */
#define PG_REMOTE_KEY 9 /* a tile's ckey for an episode that is not on the card (the others: pc_state + 1) */
#define PG_ROW_REFRESH -1 /* pg.rows[] entries of the Feeds level that are no show */
#define PG_ROW_IMPORT -2
#define PG_ROW_DOWNLOADS -3 /* shown while a download is queued or running; a tap on it does nothing */
#define PG_AWAKE_MS 1000 /* the downloads' timer */

enum { L_SHOWS = 0, L_EPS = 1, L_FEEDS = 2, L_DLS = 3 };

#define PG_DL_MAX PC_MAX_SHOWS /* rows of the Downloads level (the tile ring holds that many) */
#define PG_PICK_BYTES ((PC_MAX_EPS + 7) / 8) /* the select mode's bitsets */

struct pg_dl { /* a row of the Downloads level */
    char dir[PC_FILE], file[PC_FILE], title[PC_TITLE];
    unsigned key;
};

static struct {
    void *win, *view, *sv, *status, *title, *fade;
    void *st_title, *st_sub, *st_dim, *st_acc,
        *st_act; /* hidden labels whose styles are the row title, the grey line, a played title, the speed and an action row's title */
    void *dlg_scrim, *dlg_card, *dlg_name, *dlg_count, *dlg_fill,
        *dlg_cancel; /* the refresh dialog (hidden widgets of the asset) */
    void *btn_feeds,
        *np; /* the navbar's Feeds button (the Shows level only) and Now Playing (the capsule's right cap, a disc where Feeds is not) */
    char root[PC_FILE + 20];
    pc_show_t *shows;
    int nshows; /* every folder the model found (shows with files, subscriptions without) */
    int rows
        [PC_MAX_SHOWS +
         3]; /* the rows of the Shows / Feeds level: an index into shows, or PG_ROW_REFRESH / PG_ROW_IMPORT / PG_ROW_DOWNLOADS */
    int nrows;
    int from_feeds; /* the Show level was opened from Feeds: Back goes there, and the episodes not on the card are listed (greyed) */
    unsigned gen; /* pn_gen() the Feeds rows were made at */
    pc_ep_t *eps; /* the downloaded episodes of the show open, newest first */
    int neps;
    int level, sel, show_off,
        feeds_off; /* the level, the show open (an index into shows), the Shows and Feeds lists' offsets to come back to */
    int press, down, down_x,
        down_y; /* the row under the finger + 1; the row a press began on + 1 (0 none; a header hit is -1) and where */
    int fg, noscroll;
    unsigned rev; /* pc_rev() the rows were made at */
    unsigned timer, load_timer, dlg_timer,
        awake; /* awake: the downloads' timer (keeps the device awake, starts the queue again): scoped to the window, in front or not */
    int rpend; /* a refresh waits for the downloads to pause: 1 + only_new */
    int has_dl; /* the Feeds level has its Downloads row */
    unsigned dgen; /* pn_dl_gen() the Show level's lines were made at */
    void *back, *btn_select, *btn_selall, *bar, *del,
        *mark
            [2]; /* select mode: the navbar's Back (its x), Select, Select All, the bottom bar and its Delete pill, the unselect / selected marks */
    int select; /* select mode (the Show and Downloads levels: marks, Select All, a Delete bar) */
    unsigned npick, ncan; /* rows marked, rows that can be */
    unsigned char pick[PG_PICK_BYTES], can[PG_PICK_BYTES]; /* the marks, and the rows that may be marked */
    struct pg_dl *dls; /* the Downloads level's rows (pg.rows[a] is the show of row a, for its cover) */
    int dl_off; /* the Feeds level's offset is feeds_off; this one is kept while the rows are made again */
    int dlg; /* the refresh dialog is up */
    unsigned dlg_name_hash; /* pc_hash of the feed whose name the dialog shows */
    unsigned dlg_px,
        dlg_done; /* what the dialog last drew: the fill's width, and the "n of m" it showed (so a tick without news changes nothing) */
    grid_tile_t spd; /* the speed text of the Show header */
    grid_t g; /* the tiles: a show's cover and texts, an episode's texts (ckey = its state + 1) */
    grid_t hg; /* the Show header's cover (one tile) and its name and count */
} pg __attribute__((section(".scratch")));

static void pg_show(void *w, int on) {
    if (!w) return;
    widget_set_visible(w, on, 0);
    widget_set_sensitive(w, on);
}

static int pg_abs(int v) { return v < 0 ? -v : v; }
static int pg_off(void) { return pg.sv ? I(pg.sv, SC_YOFF) : 0; }
static void pg_redraw(void) { widget_invalidate_force(pg.sv, (void *)0); }
static void pg_awake_arm(void); /* the downloads' timer, armed when something is queued */

static int pg_count(void) { return pg.level == L_EPS ? pg.neps : pg.nrows; }
static int pg_top(void) { return pg.level == L_EPS ? PC_HDR_H : 0; }
static int pg_content(void) {
    return (pg_count()          ? pg_top() + pg_count() * PC_ROW_H + (pg.level == L_EPS ? PG_BOTTOM : 0)
            : pg.level == L_EPS ? PC_HDR_H
                                : 0) +
           (pg.select && pg_count() ? SG_BAR_H : 0); /* (the select mode's bar covers the last rows' place) */
}

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
static void pg_cat(char *out, unsigned size, const char *s);

/* An episode's grey line: the date, then a tail: Played, N min left, or its length; one that is not on the card ends with its size ("· 48 MB", when the feed gave one), which a played
 * episode's line (it ends with Played) never has: the two grey titles are told apart by it. */
static void pg_sub_of(const pc_ep_t *e, unsigned *state, char *out, unsigned size) {
    static const char sep[] = " \xc2\xb7 "; /* " · " */
    char date[48], tail[72];
    unsigned pos, len, total, mins = 0, o = 0, k;
    int s = pc_state(e->hash, &pos, &len);
    total = len ? len : e->dur;
    tail[0] = 0;
    date[0] = 0;
    if (e->pub)
        pc_when(
            e->pub, (unsigned)time((long *)0), date,
            sizeof date); /* the date is made again whenever the tiles are (the page opens, comes back to the front) */
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
    if (e->state != PC_LOCAL && e->length) {
        char sz[24];
        pc_fmt(sz, sizeof sz, TR("%d MB"), (e->length + 1048575) >> 20);
        if (tail[0]) pg_cat(tail, sizeof tail, sep);
        pg_cat(tail, sizeof tail, sz);
    }
    for (k = 0; date[k] && o + 1 < size; ++k) out[o++] = date[k];
    if (date[0] && tail[0])
        for (k = 0; sep[k] && o + 1 < size; ++k) out[o++] = sep[k];
    for (k = 0; tail[k] && o + 1 < size; ++k) out[o++] = tail[k];
    out[o] = 0;
    *state = (unsigned)s;
}

/* The words of a feed's state, for its grey line: what the worker found this session, else when it was last refreshed. */
static const char *pg_status_word(int code) {
    switch (code) {
    case PN_NOWIFI:
        return TR("No Wi-Fi");
    case PN_NOCLOCK:
        return TR("Set the date first");
    case PN_NOCERT:
        return TR("Certificates missing");
    case PN_CERT:
        return TR("Certificate problem");
    case PN_NET:
        return TR("Can't connect");
    case PN_GONE:
        return TR("Feed not found");
    case PN_HTTP:
        return TR("Server error");
    case PN_NOTFEED:
        return TR("Not a podcast feed");
    case PN_STORAGE:
        return TR("Storage unavailable");
    default:
        return TR("Not enough memory");
    }
}

static void pg_cat(char *out, unsigned size, const char *s) {
    unsigned o = 0, k;
    while (out[o]) ++o;
    for (k = 0; s[k] && o + 1 < size; ++k) out[o++] = s[k];
    out[o] = 0;
}

/* The words of a download that failed: for an episode a 404 is "Not found" (a missing feed is another thing). */
static const char *pg_dl_word(int code) {
    switch (code) {
    case PN_GONE:
        return TR("Not found");
    case PN_CARDFULL:
        return TR("Card is full");
    case PN_NOTAUDIO:
        return TR("Not audio");
    case PN_QFULL:
        return TR("Queue is full");
    default:
        return pg_status_word(code);
    }
}

/* "Downloading 42%" when the length is known, else "Downloading 12 MB". */
static void pg_dl_progress(char *out, unsigned size, unsigned got, unsigned total) {
    char num[24];
    out[0] = 0;
    pg_cat(out, size, TR("Downloading"));
    if (total) {
        unsigned pct = (got >> 10) * 100 / ((total >> 10) ? (total >> 10) : 1);
        pc_fmt(num, sizeof num, " %d%", pct > 100 ? 100 : pct);
    } else
        pc_fmt(num, sizeof num, " %d MB", got >> 20);
    pg_cat(out, size, num);
}

/* The state line of an episode that is not on the card, when it has one: Waiting, Downloading 42%, Failed: <why>, or Paused (a .part from before). 0 when it is a plain remote episode (its date line). */
static int pg_dl_line(unsigned key, int part, char *out, unsigned size) {
    int code = 0, st;
    unsigned got = 0, total = 0;
    out[0] = 0;
    st = key ? pn_dl_state(key, &code, &got, &total) : PN_DL_NONE;
    if (st == PN_DL_ACTIVE)
        pg_dl_progress(out, size, got, total);
    else if (st == PN_DL_WAIT)
        pg_cat(out, size, TR("Waiting"));
    else if (st == PN_DL_FAILED) {
        pg_cat(out, size, TR("Failed"));
        pg_cat(out, size, ": ");
        pg_cat(out, size, pg_dl_word(code));
    } else if (part)
        pg_cat(out, size, TR("Paused"));
    return out[0] != 0;
}

static int pg_dl_sub(const pc_ep_t *e, char *out, unsigned size) {
    return pg_dl_line(e->file[0] ? pn_dl_key(pg.shows[pg.sel].dir, e->file) : 0, e->state == PC_PART, out, size);
}

/* The texts of row a of the Feeds level into out (title) and sub. */
static void pg_feed_texts(int a, char *title, unsigned tsize, char *sub, unsigned ssize) {
    int row = pg.rows[a];
    unsigned now = (unsigned)time((long *)0);
    title[0] = sub[0] = 0;
    if (row == PG_ROW_REFRESH) {
        unsigned last = 0;
        int i, done, total;
        for (i = 0; i < pg.nrows; ++i)
            if (pg.rows[i] >= 0 && pg.shows[pg.rows[i]].checked > last) last = pg.shows[pg.rows[i]].checked;
        pg_cat(title, tsize, TR("Refresh All"));
        if (pg.rpend)
            pg_cat(sub, ssize, TR("Waiting")); /* the downloads are pausing: the refresh starts when they have */
        else if (pn_busy()) {
            char num[28];
            pn_progress(&done, &total);
            pg_cat(sub, ssize, TR("Refreshing"));
            pc_fmt(num, sizeof num, " %d/", (unsigned)done);
            pg_cat(sub, ssize, num);
            pc_fmt(num, sizeof num, "%d", (unsigned)total);
            pg_cat(sub, ssize, num);
        } else if (last)
            pc_when(last, now, sub, ssize);
        else
            pg_cat(sub, ssize, TR("Never refreshed"));
    } else if (row == PG_ROW_DOWNLOADS) { /* "Downloads (3)" and the one being fetched: its percent, or Waiting */
        char num[16];
        unsigned got = 0, total = 0;
        pg_cat(title, tsize, TR("Downloads"));
        pc_fmt(num, sizeof num, " (%d)", (unsigned)pn_dl_count());
        pg_cat(title, tsize, num);
        if (pn_dl_current(&got, &total))
            pg_dl_progress(sub, ssize, got, total);
        else
            pg_cat(sub, ssize, TR("Waiting"));
    } else if (row == PG_ROW_IMPORT) {
        pg_cat(title, tsize, TR("Import shows"));
        pg_cat(sub, ssize, "Podcasts/" PN_IMPORT_FILE);
    } else {
        const pc_show_t *s = &pg.shows[row];
        unsigned feed = pc_hash(s->feed), fresh = 0;
        int code = 0, known = pn_status(feed, &code, &fresh);
        pg_cat(title, tsize, s->title);
        if (pn_busy() && pn_current() == feed)
            pg_cat(sub, ssize, TR("Refreshing"));
        else if (known && code != PN_OK)
            pg_cat(sub, ssize, pg_status_word(code));
        else {
            if (known && fresh)
                pc_fmt(sub, ssize, TR("%d new"), fresh);
            else if (s->checked || known)
                pg_cat(sub, ssize, TR("Up to date"));
            else
                pg_cat(sub, ssize, TR("Never refreshed"));
            if (s->checked) {
                char when[48];
                pc_when(s->checked, now, when, sizeof when);
                pg_cat(sub, ssize, " \xc2\xb7 "); /* " · " */
                pg_cat(sub, ssize, when);
            }
        }
    }
}

/* The tile of row a at the current level; a new tile gets its texts. */
static grid_tile_t *pg_tile(int a) {
    int lo, hi, fresh;
    grid_tile_t *t;
    pg_span(&lo, &hi);
    lo -= 2, hi += 2;
    if (lo < 0) lo = 0;
    if (pg.level != L_EPS) lo = 0, hi = pg.nrows - 1;
    t = grid_tile(&pg.g, a, lo, hi, &fresh);
    if (fresh) {
        char sub[80];
        if (pg.level == L_SHOWS) {
            const pc_show_t *s = &pg.shows[pg.rows[a]];
            pc_fmt(sub, sizeof sub, TR(s->count == 1 ? "%d episode" : "%d episodes"), s->count);
            grid_set(t, s->title, sub, 0);
        } else if (pg.level == L_FEEDS) {
            char title[PC_TITLE + 8];
            pg_feed_texts(a, title, sizeof title, sub, sizeof sub);
            grid_set(t, title, sub, 0);
            if (pg.rows[a] < 0) t->art = 2; /* an action row has no cover to load */
        } else if (pg.level == L_DLS) { /* the episode and its state line, the show's cover */
            pg_dl_line(pg.dls[a].key, 1, sub, sizeof sub);
            grid_set(t, pg.dls[a].title, sub, 0);
        } else {
            unsigned state;
            if (pg.eps[a].state == PC_LOCAL || !pg_dl_sub(&pg.eps[a], sub, sizeof sub))
                pg_sub_of(&pg.eps[a], &state, sub, sizeof sub);
            else
                state = PC_NEW;
            grid_set(t, pg.eps[a].title, sub, 0);
            t->ckey = pg.eps[a].state == PC_LOCAL ? state + 1 : PG_REMOTE_KEY;
        }
    }
    return t;
}

/* The grey lines of the Feeds rows made again (a refresh moved on): the covers stay. */
static void pg_feed_retext(void) {
    int a;
    for (a = 0; a < pg.nrows; ++a) {
        grid_tile_t *t = grid_find(&pg.g, a);
        char title[PC_TITLE + 8], sub[80];
        if (!t) continue;
        pg_feed_texts(a, title, sizeof title, sub, sizeof sub);
        grid_set(t, title, sub, 0);
        t->fit = 0, t->tw = t->aw = 0;
    }
}

/* The state lines of the Downloads rows made again (a step of progress): the covers stay. */
static void pg_dls_retext(void) {
    int a;
    for (a = 0; a < pg.nrows; ++a) {
        grid_tile_t *t = grid_find(&pg.g, a);
        char sub[80];
        if (!t) continue;
        pg_dl_line(pg.dls[a].key, 1, sub, sizeof sub);
        grid_set(t, pg.dls[a].title, sub, 0);
        t->fit = 0, t->tw = t->aw = 0;
    }
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
    grid_set(t, s->title, count, 0); /* (the cover in the tile stays) */
    t->fit = 0, t->tw = t->aw = 0;
    memset(&pg.spd, 0, sizeof pg.spd);
    grid_set(&pg.spd, name[mode], "", 0);
}

/* ---------------------------------------------------------------------------
 * Paint
 */
static int pg_is_pick(int i) { return pg.pick[i >> 3] >> (i & 7) & 1; }
static int pg_can_pick(int i) { return pg.can[i >> 3] >> (i & 7) & 1; }

/* The select mark of a row that can be marked, wholly inside the window (as the Playlists page's). */
static void pg_mark(void *canvas, int i, int x, int y) {
    int src[4], dst[4];
    if (!pg.mark[0] || !pg_can_pick(i) || y < 0 || y + SG_MARK > GRID_VIEW_H) return;
    src[0] = src[1] = 0, src[2] = src[3] = SG_MARK;
    dst[0] = x, dst[1] = y, dst[2] = dst[3] = SG_MARK;
    canvas_draw_image(canvas, pg.mark[pg_is_pick(i)], src, dst);
}

/* The Shows and Downloads levels: the list rows of the stock Albums list mode. In select mode (Downloads) a mark column opens left of the covers. */
static void pg_paint_shows(void *canvas) {
    int r0, r1, r;
    pg_span(&r0, &r1);
    if (r1 < r0) return;
    grid_list_paint(canvas, &pg.g, pg.st_title, pg.st_sub, r0, r1, pg_off(), GRID_VIEW_H, pg.select ? 0 : pg.press,
                    pg.select ? SG_SEL_COL : 0, pg_tile_of, (void *)0);
    for (r = r0; pg.select && r <= r1; ++r)
        pg_mark(canvas, r, LIST_ART_X + (SG_SEL_COL - 6 - SG_MARK) / 2,
                r * PC_ROW_H - pg_off() + (PC_ROW_H - SG_MARK) / 2);
}

static void pg_paint_eps(void *canvas) {
    int r0, r1, r, off = pg_off(), pass, sx = pg.select ? SG_SEL_COL : 0;
    grid_tile_t *h = &pg.hg.tiles[0];
    if (off < PC_HDR_H) { /* the header: cover, name, count, speed */
        grid_blit(canvas, &pg.hg, h, 16, 16 - off, GRID_VIEW_H);
        widget_prepare_text_style(pg.st_title, canvas);
        grid_text(canvas, h, 0, PG_HDR_TEXT_X, 22 - off, PG_HDR_TEXT_W, LIST_TITLE_H, GRID_VIEW_H);
        widget_prepare_text_style(pg.st_sub, canvas);
        grid_text(canvas, h, 1, PG_HDR_TEXT_X, 50 - off, PG_HDR_TEXT_W, LIST_SUB_H, GRID_VIEW_H);
        widget_prepare_text_style(pg.st_acc, canvas);
        grid_text(canvas, &pg.spd, 0, PG_HDR_TEXT_X, PG_SPEED_Y + (PG_SPEED_H - LIST_SUB_H) / 2 - off, PG_HDR_TEXT_W,
                  LIST_SUB_H, GRID_VIEW_H);
    }
    pg_span(&r0, &r1);
    if (r1 < r0) return;
    for (r = r0; r <= r1; ++r) {
        grid_tile_t *t = pg_tile(r);
        int y = PC_HDR_H + r * PC_ROW_H - off;
        if (pg.press == r + 1 && !pg.select) az_fill(canvas, 0, y, y + PC_ROW_H - 1, PG_W, LIST_PRESS);
        az_fill(canvas, PG_TEXT_X + sx, y + PC_ROW_H - 1, y + PC_ROW_H, PG_W - PG_TEXT_X - sx, LIST_HAIR);
        if (pg.select) /* select mode: the mark column opens left of the texts (as the Playlists page's rows) */
            pg_mark(canvas, r, PG_TEXT_X + (SG_SEL_COL - 6 - SG_MARK) / 2, y + (PC_ROW_H - SG_MARK) / 2);
        (void)t;
    }
    for (pass = 0; pass < 3; ++pass) { /* titles, played titles, grey lines: one text style at a time */
        widget_prepare_text_style(pass == 0 ? pg.st_title : pass == 1 ? pg.st_dim : pg.st_sub, canvas);
        for (r = r0; r <= r1; ++r) {
            grid_tile_t *t = pg_tile(r);
            int y = PC_HDR_H + r * PC_ROW_H - off,
                played = t->ckey == PC_DONE + 1 ||
                         t->ckey == PG_REMOTE_KEY; /* (a title not on the card is as grey as a played one) */
            if (pass == 2)
                grid_text(canvas, t, 1, PG_TEXT_X + sx, y + LIST_SUB_Y, PG_TEXT_W - sx, LIST_SUB_H, GRID_VIEW_H);
            else if ((pass == 1) == played)
                grid_text(canvas, t, 0, PG_TEXT_X + sx, y + LIST_TITLE_Y, PG_TEXT_W - sx, LIST_TITLE_H, GRID_VIEW_H);
        }
    }
}

/* The Feeds level: the action rows (Refresh All, Import: the title in the action colour from PG_ACT_X, no cover) and a row per subscription (cover, name, state). */
static void pg_paint_feeds(void *canvas) {
    int r0, r1, r, pass, off = pg_off();
    pg_span(&r0, &r1);
    if (r1 < r0) return;
    for (r = r0; r <= r1; ++r) {
        grid_tile_t *t = pg_tile(r);
        int y = r * PC_ROW_H - off, show = pg.rows[r] >= 0, x = show ? LIST_TEXT_X : PG_ACT_X;
        if (pg.press == r + 1) az_fill(canvas, 0, y, y + PC_ROW_H - 1, PG_W, LIST_PRESS);
        if (show) grid_blit(canvas, &pg.g, t, LIST_ART_X, y + LIST_ART_Y, GRID_VIEW_H);
        az_fill(canvas, x, y + PC_ROW_H - 1, y + PC_ROW_H, PG_W - x, LIST_HAIR);
    }
    for (pass = 0; pass < 3; ++pass) { /* feed names, action titles, grey lines: one text style at a time */
        widget_prepare_text_style(pass == 0 ? pg.st_title : pass == 1 ? pg.st_act : pg.st_sub, canvas);
        for (r = r0; r <= r1; ++r) {
            grid_tile_t *t = pg_tile(r);
            int y = r * PC_ROW_H - off, show = pg.rows[r] >= 0, x = show ? LIST_TEXT_X : PG_ACT_X, w = PG_W - 12 - x,
                plain =
                    show ||
                    pg.rows[r] ==
                        PG_ROW_DOWNLOADS; /* (the Downloads row is a report, not an action: the plain title style) */
            if (pass == 2)
                grid_text(canvas, t, 1, x, y + LIST_SUB_Y, w, LIST_SUB_H, GRID_VIEW_H);
            else if ((pass == 0) == plain)
                grid_text(canvas, t, 0, x, y + LIST_TITLE_Y, w, LIST_TITLE_H, GRID_VIEW_H);
        }
    }
}

static int pg_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int off = pg_off();
    (void)ctx;
    if (!canvas || !pg.view || !pg.g.tiles) return RET_OK;
    I(canvas, CANVAS_OY) += off;
    if ((pg.level == L_SHOWS || pg.level == L_DLS) && pg.nrows)
        pg_paint_shows(canvas);
    else if (pg.level == L_FEEDS && pg.nrows)
        pg_paint_feeds(canvas);
    else if (pg.level == L_EPS && pg.hg.tiles)
        pg_paint_eps(canvas);
    I(canvas, CANVAS_OY) -= off;
    return RET_OK;
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
        if (pg.rows[a] >= 0 && (!t || !t->art)) return a;
    }
    for (a = 0; a < pg.nrows; ++a) {
        grid_tile_t *t = grid_find(&pg.g, a);
        if (pg.rows[a] >= 0 && (!t || !t->art)) return a;
    }
    return -1;
}

static int pg_on_load(const void *unused) {
    (void)unused;
    pg.load_timer = 0;
    if (!pg.win || !pg.fg || !pg.g.tiles) return RET_OK;
    if (pg.level != L_EPS) {
        int a = pg_next_cover();
        if (a >= 0) {
            grid_tile_t *t = pg_tile(a);
            if (!t->art) pg_art(&pg.g, t, &pg.shows[pg.rows[a]]);
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
    if (key)
        az_fit(pg.title, TR(key));
    else
        az_fit(pg.title, text);
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
    (void)ctx;
    (void)e;
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

/* Whether row a can be marked in select mode. Show level: an episode with a file, or a .part that no download holds (a paused one: deleting it takes the paused download away); a remote
 * row cannot. Downloads level: every row but the one running (it is paused with a tap first). */
static int pg_pickable(int a) {
    int code, st;
    unsigned got, total;
    if (pg.level == L_DLS) return a < pg.nrows && pn_dl_state(pg.dls[a].key, &code, &got, &total) != PN_DL_ACTIVE;
    if (pg.level != L_EPS || a >= pg.neps) return 0;
    if (pg.eps[a].state == PC_LOCAL) return 1;
    if (pg.eps[a].state != PC_PART || !pg.eps[a].file[0]) return 0;
    st = pn_dl_state(pn_dl_key(pg.shows[pg.sel].dir, pg.eps[a].file), &code, &got, &total);
    return st == PN_DL_NONE || st == PN_DL_FAILED;
}

/* How many rows can be marked; with fill the bitset of them is made. */
static unsigned pg_sel_scan(int fill) {
    int i, n = pg_count();
    unsigned c = 0;
    if (fill) memset(pg.can, 0, sizeof pg.can);
    for (i = 0; i < n && i < PC_MAX_EPS; ++i)
        if (pg_pickable(i)) {
            ++c;
            if (fill) pg.can[i >> 3] |= (unsigned char)(1 << (i & 7));
        }
    return c;
}

static void pg_select(int on);

/* The navbar's right end. Shows level: the Feeds button, the capsule's left cap. Show and Downloads levels: the Select button (the same cap) when a row can be marked. Elsewhere both are hidden (and out
 * of the hit test) and Now Playing is the glass disc; with a cap beside it Now Playing is the capsule's right cap. */
static void pg_nav(void) {
    int shows = pg.level == L_SHOWS,
        sel =
            !pg.select && (pg.level == L_EPS || pg.level == L_DLS) && pg.btn_select && pg.mark[0] && pg_sel_scan(0) > 0,
        cap = shows || sel;
    const char *img = cap ? "ah_nav_play" : "ah_nav_np";
    pg_show(pg.btn_feeds, shows);
    pg_show(pg.btn_select, sel);
    if (pg.np) {
        widget_set_prop_str(pg.np, "style:normal:icon", img);
        widget_set_prop_str(pg.np, "style:over:icon", img);
        widget_set_prop_str(pg.np, "style:pressed:icon", cap ? "ah_nav_play_down" : "ah_nav_np_down");
    }
}

/* The model's folders again (a show may have come, gone or been renamed), and the Shows level's rows: the shows with a file on the card. */
static void pg_scan(void) {
    int i;
    pg.nshows = pc_scan_shows(pg.shows, PC_MAX_SHOWS);
    pg.nrows = 0;
    for (i = 0; i < pg.nshows; ++i)
        if (pg.shows[i].count) pg.rows[pg.nrows++] = i;
}

/* The Shows level: what is on the card (a subscription with nothing downloaded is in Feeds, not here). */
static void pg_load_shows(void) {
    int i, feeds = 0;
    if (pg.select) pg_select(0);
    pg_drop_tiles();
    pg.level = L_SHOWS;
    pg.from_feeds = 0;
    pg_scan();
    for (i = 0; i < pg.nshows; ++i) feeds += pg.shows[i].feed[0] != 0;
    free(pg.eps);
    pg.eps = (pc_ep_t *)0;
    pg.neps = 0;
    pg_title("Podcasts", (const char *)0);
    pg_nav();
    pg_show(pg.view, 1);
    pg_show(pg.status, 0);
    // clang-format off: a translation key stays on one line (test/pod/i18n.py reads the source)
    if (!pg.nrows)
        pg_empty(feeds ? "Nothing downloaded yet. Open Feeds, at the top right."
                       : "No podcasts. Copy a folder for each show into Podcasts on the card, or subscribe in Feeds, at the top right.");
    // clang-format on
    grid_shape(&pg.g, LIST_ART, LIST_R, 1);
    grid_placeholder(&pg.g);
    pg_size();
    widget_set_prop_int(pg.sv, "yoffset", pg.show_off);
    pg_fade();
    pg_redraw();
    pg_kick();
}

/* The Feeds level: Refresh All, Import (when subscriptions.txt is there), and a row per subscription with its state. */
static void pg_load_feeds(void) {
    int i, feeds = 0, off = pg.level == L_FEEDS ? pg_off() : pg.feeds_off;
    char path[PC_FILE * 2 + 40];
    if (pg.select) pg_select(0);
    pg_drop_tiles();
    pg.level = L_FEEDS;
    pg.from_feeds = 0;
    pg_scan();
    pg.nrows = 0;
    for (i = 0; i < pg.nshows; ++i) feeds += pg.shows[i].feed[0] != 0;
    if (feeds) pg.rows[pg.nrows++] = PG_ROW_REFRESH;
    pg.has_dl = pn_dl_count() > 0;
    if (pg.has_dl) pg.rows[pg.nrows++] = PG_ROW_DOWNLOADS;
    for (i = 0; pg.root[i] && i + 1 < (int)sizeof path; ++i) path[i] = pg.root[i];
    path[i] = 0;
    if (i + (int)sizeof("/" PN_IMPORT_FILE) <= (int)sizeof path) {
        memcpy(path + i, "/" PN_IMPORT_FILE, sizeof("/" PN_IMPORT_FILE));
        if (access(path, F_OK) == 0) pg.rows[pg.nrows++] = PG_ROW_IMPORT;
    }
    for (i = 0; i < pg.nshows; ++i)
        if (pg.shows[i].feed[0]) pg.rows[pg.nrows++] = i;
    free(pg.eps);
    pg.eps = (pc_ep_t *)0;
    pg.neps = 0;
    pg.gen = pn_gen(), pg.dgen = pn_dl_gen();
    pg_title("Feeds", (const char *)0);
    pg_nav();
    pg_show(pg.view, 1);
    pg_show(pg.status, 0);
    // clang-format off: a translation key stays on one line (test/pod/i18n.py reads the source)
    if (!pg.nrows)
        pg_empty("No subscriptions. List one feed address per line in subscriptions.txt in Podcasts on the card, then open Feeds again.");
    // clang-format on
    grid_shape(&pg.g, LIST_ART, LIST_R, 1);
    grid_placeholder(&pg.g);
    pg_size();
    widget_set_prop_int(pg.sv, "yoffset", off);
    pg_fade();
    pg_redraw();
    pg_kick();
}

/* The index in shows of the show folder dir, -1 when there is none. */
static int pg_show_of(const char *dir) {
    int i;
    for (i = 0; i < pg.nshows; ++i)
        if (!strcmp(pg.shows[i].dir, dir)) return i;
    return -1;
}

static void pg_dl_row(int n, int si, const char *dir, const char *file, const char *title, unsigned key) {
    struct pg_dl *d = &pg.dls[n];
    d->dir[0] = d->file[0] = d->title[0] = 0;
    pg_cat(d->dir, sizeof d->dir, dir);
    pg_cat(d->file, sizeof d->file, file);
    pg_cat(d->title, sizeof d->title, title);
    d->key = key;
    pg.rows[n] = si;
}

/* The Downloads level's rows (at most PG_DL_MAX): what the worker holds, in the order it was asked (queued, running, waiting), then the failed ones, then the paused ones the card
 * has and the worker does not (a .part of an episode its show's .episodes lists: after a reboot, the user's unfinished downloads). Titles come from the shows' .episodes; the scan reads
 * the shows with a feed (and the ones the worker names), one pc_load_show each. */
static void pg_dls_build(void) {
    char dir[PC_FILE], file[PC_FILE];
    int n = 0, i, si, code;
    unsigned key;
    pc_ep_t *all;
    for (i = 0; n < PG_DL_MAX && (key = pn_dl_listed(i, dir, file, &code)); ++i) {
        si = pg_show_of(dir);
        if (si >= 0) pg_dl_row(n++, si, dir, file, file, key);
    }
    all = calloc(PC_MAX_EPS, sizeof *all);
    for (si = 0; all && si < pg.nshows; ++si) {
        int k, cnt, used = 0;
        for (k = 0; k < n; ++k) used |= pg.rows[k] == si;
        if (!used && !pg.shows[si].feed[0]) continue;
        cnt = pc_load_show(&pg.shows[si], all, PC_MAX_EPS);
        for (k = 0; k < cnt; ++k) {
            int j, found = -1;
            for (j = 0; j < n; ++j)
                if (pg.rows[j] == si && !strcmp(pg.dls[j].file, all[k].file)) found = j;
            if (found >= 0) {
                pg.dls[found].title[0] = 0;
                pg_cat(pg.dls[found].title, PC_TITLE, all[k].title);
            } else if (all[k].state == PC_PART && all[k].file[0] && n < PG_DL_MAX) {
                pg_dl_row(n++, si, pg.shows[si].dir, all[k].file, all[k].title,
                          pn_dl_key(pg.shows[si].dir, all[k].file));
            }
        }
    }
    free(all);
    pg.nrows = n;
}

/* The Downloads level, behind the Feeds level's Downloads row: a row per download (the show's cover, the episode, its state line). keep: the scroll position stays (the rows are made again). */
static void pg_load_downloads(int keep) {
    int off = keep ? pg_off() : 0;
    if (!pg.dls) {
        pod_toast(TR("Not enough memory"));
        return;
    }
    if (pg.select) pg_select(0);
    if (pg.level == L_FEEDS) pg.feeds_off = pg_off();
    pg_drop_tiles();
    pg.level = L_DLS;
    pg.from_feeds = 0;
    pg_scan();
    free(pg.eps);
    pg.eps = (pc_ep_t *)0;
    pg.neps = 0;
    pg_dls_build();
    pg.gen = pn_gen(), pg.dgen = pn_dl_gen();
    pg_title("Downloads", (const char *)0);
    pg_nav();
    pg_show(pg.view, 1);
    pg_show(pg.status, 0);
    if (!pg.nrows) pg_empty("No downloads");
    grid_shape(&pg.g, LIST_ART, LIST_R, 1);
    grid_placeholder(&pg.g);
    pg_size();
    widget_set_prop_int(pg.sv, "yoffset", off);
    pg_fade();
    pg_redraw();
    pg_kick();
}

/* The Show level of show `si` (an index into shows): the episodes on the card, newest first; opened from Feeds, the ones not on the card as well, greyed. */
static pc_ep_t *pg_eps_of(int si, int remote, int *count) {
    pc_ep_t *all = calloc(PC_MAX_EPS, sizeof *all);
    int n, k, m = 0;
    if (!all) return all;
    n = pc_load_show(&pg.shows[si], all, PC_MAX_EPS);
    for (k = 0; k < n; ++k)
        if (remote || all[k].state == PC_LOCAL) {
            if (m != k) memcpy(&all[m], &all[k], sizeof *all);
            ++m;
        }
    *count = m;
    return all;
}

static void pg_open_show(int si, int remote) {
    int m = 0;
    pc_ep_t *all = pg_eps_of(si, remote, &m);
    if (!all) {
        pod_toast(TR("Not enough memory"));
        return;
    }
    pg.gen = pn_gen(), pg.dgen = pn_dl_gen();
    if (pg.level == L_FEEDS)
        pg.feeds_off = pg_off();
    else
        pg.show_off = pg_off();
    pg_drop_tiles();
    free(pg.eps);
    pg.eps = all, pg.neps = m, pg.sel = si, pg.level = L_EPS, pg.from_feeds = remote;
    pg.rev = pc_rev();
    pg_title((const char *)0, pg.shows[si].title);
    pg_nav();
    pg_show(pg.view, 1);
    pg_show(pg.status, 0);
    if (!m) pg_empty(remote ? "No episodes yet. Refresh the feed in Feeds." : "No downloaded episodes");
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

/* The Show level's episodes read again (a download finished, failed or was started: the list changed): the scroll position and the header stay, the lines are made again. */
static void pg_reload_eps(void) {
    int m = 0;
    pc_ep_t *all = pg_eps_of(pg.sel, pg.from_feeds, &m);
    pg.gen = pn_gen(), pg.dgen = pn_dl_gen();
    if (!all) return;
    free(pg.eps);
    pg.eps = all, pg.neps = m;
    grid_drop(&pg.g);
    pg.press = pg.down = 0;
    if (!m)
        pg_empty(pg.from_feeds ? "No episodes yet. Refresh the feed in Feeds." : "No downloaded episodes");
    else {
        pg_show(pg.view, 1);
        pg_show(pg.status, 0);
    }
    pg_header_texts();
    pg_size();
    pg_nav();
    pg_redraw();
}

/* ---------------------------------------------------------------------------
 * Select mode (the Show and Downloads levels), in the Playlists page's manner (docs/modules/playlists.md "Select mode"): the navbar's Back becomes the x, the title "N Selected", Select All at the
 * right, a mark on every row that can be marked, a bottom bar with one Delete pill and a confirm before anything is removed.
 */
static void pg_head(void) { /* the navbar's title: "N Selected" in select mode, else the level's */
    char buf[64];
    if (!pg.title) return;
    if (!pg.select) {
        if (pg.level == L_EPS)
            pg_title((const char *)0, pg.shows[pg.sel].title);
        else if (pg.level == L_DLS)
            pg_title("Downloads", (const char *)0);
        return;
    }
    pc_fmt(buf, sizeof buf, TR("%d Selected"), pg.npick);
    widget_set_text_utf8(pg.title, buf);
}

static void pg_select(int on) {
    int max;
    if (on == pg.select) return;
    if (on && !(pg.btn_selall && pg.bar && pg.del && pg.mark[0] && pg.mark[1])) return;
    pg.select = on;
    pg.npick = 0;
    memset(pg.pick, 0, sizeof pg.pick);
    pg.ncan = on ? pg_sel_scan(1) : 0;
    pg.press = pg.down = 0;
    pg_show(pg.btn_select, 0);
    pg_show(pg.btn_feeds, 0);
    pg_show(pg.np, !on);
    pg_show(pg.btn_selall, on);
    pg_show(pg.bar, on);
    if (pg.title) widget_resize(pg.title, (on ? SG_SELALL_X : NAV_VIEW_X) - NAV_TITLE_X, 22);
    if (pg.back) {
        widget_set_prop_str(pg.back, "style:normal:icon", on ? "ah_nav_close" : "ah_nav_back");
        widget_set_prop_str(pg.back, "style:over:icon", on ? "ah_nav_close" : "ah_nav_back");
        widget_set_prop_str(pg.back, "style:pressed:icon", on ? "ah_nav_close_down" : "ah_nav_back_down");
    }
    pg_head();
    if (!on) pg_nav();
    grid_drop(&pg.g); /* the texts are made again at the other width */
    pg_size();
    max = pg_content() - GRID_VIEW_H;
    if (max < 0) max = 0;
    if (pg_off() > max) widget_set_prop_int(pg.sv, "yoffset", max);
    pg_fade();
    pg_redraw();
}

static int pg_on_select(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (pg.win && !pg.select && (pg.level == L_EPS || pg.level == L_DLS)) pg_select(1);
    return RET_OK;
}

static void pg_toggle_pick(int i) {
    if (i < 0 || i >= pg_count() || !pg_can_pick(i)) return;
    pg.pick[i >> 3] ^= (unsigned char)(1 << (i & 7));
    pg.npick += pg_is_pick(i) ? 1 : (unsigned)-1;
    pg_head();
    pg_redraw();
}

static int pg_on_selall(void *ctx, void *e) {
    int i, all;
    (void)ctx;
    (void)e;
    if (!pg.select) return RET_OK;
    all = pg.npick < pg.ncan; /* all that can be, unless all are: then none */
    memset(pg.pick, 0, sizeof pg.pick);
    pg.npick = 0;
    if (all)
        for (i = 0; i < pg_count() && i < PC_MAX_EPS; ++i)
            if (pg_can_pick(i)) pg.pick[i >> 3] |= (unsigned char)(1 << (i & 7)), ++pg.npick;
    pg_head();
    pg_redraw();
    return RET_OK;
}

static int pg_on_cancel(void *ctx, void *e);

static int pg_on_back(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (!pg.win) return RET_OK;
    if (pg.dlg) return pg_on_cancel((void *)0, (void *)0); /* Back while the refresh dialog is up is its Cancel */
    if (pg.select)
        pg_select(0); /* the x leaves select mode first */
    else if (pg.level == L_DLS || (pg.level == L_EPS && pg.from_feeds))
        pg_load_feeds();
    else if (pg.level != L_SHOWS)
        pg_load_shows();
    else
        navigator_back();
    return RET_OK;
}

static int pg_on_feeds(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (pg.win && pg.level == L_SHOWS) {
        pg.show_off = pg_off();
        pg_load_feeds();
    }
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The refresh dialog: a modal card over the page while the worker runs (docs/modules/podcasts.md "Feeds"). The worker only writes the status record; this reads it from a page-scoped
 * 200 ms timer (armed while the page is in front and the screen is lit; the 1 s tick re-arms it when the screen comes back), and closes itself when the worker has stopped.
 */
#define PG_DLG_MS 200

static void pg_dlg_show(int on) {
    pg_show(pg.dlg_scrim, on);
    pg_show(pg.dlg_card, on);
    pg.dlg = on;
}

/* The dialog's texts and bar from the status record. */
static void pg_dlg_update(void) {
    int done, total, i;
    unsigned permille, px;
    char line[48];
    unsigned hash = pn_current();
    pn_progress(&done, &total);
    if (total < 1) total = 1;
    if (done >= total) done = total - 1;
    if (hash &&
        hash !=
            pg.dlg_name_hash) { /* the show being fetched: its name in the list's words (the folder rename of a first refresh changes it later, the list is read again then) */
        for (i = 0; i < pg.nshows; ++i)
            if (pc_hash(pg.shows[i].feed) == hash) {
                widget_set_text_utf8(pg.dlg_name, pg.shows[i].title);
                break;
            }
        pg.dlg_name_hash = hash;
    }
    if (pn_cancelling())
        widget_set_text_utf8(pg.dlg_count, TR("Cancelling…"));
    else {
        pc_fmt2(line, sizeof line, TR("%d of %d"), (unsigned)(done + 1), (unsigned)total);
        widget_set_text_utf8(pg.dlg_count, line);
    }
    permille = ((unsigned)done * 1000 + pn_part()) / (unsigned)total;
    px = PD_BAR_W * permille / 1000;
    if (px < 1) px = 1;
    if (px != pg.dlg_px) {
        pg.dlg_px = px;
        widget_resize(pg.dlg_fill, (int)px, PD_BAR_H);
    }
}

/* The worker has stopped: the dialog goes, the rows are read again, one line says how it went. */
static void pg_dlg_finish(void) {
    unsigned ok, failed;
    int cancelled;
    char msg[96];
    const char *shown = msg;
    pg_dlg_show(0);
    pn_summary(&ok, &failed, &cancelled);
    pn_dl_start(); /* the downloads that paused for the refresh go on */
    pg_awake_arm();
    if (cancelled) {
        if (ok)
            pc_fmt(msg, sizeof msg, TR("Cancelled, %d updated"), ok);
        else
            shown = TR("Cancelled");
    } else if (!ok && !failed)
        msg[0] = 0;
    else if (!failed)
        pc_fmt(msg, sizeof msg, TR("%d updated"), ok);
    else if (!ok)
        pc_fmt(msg, sizeof msg, TR("%d failed"), failed);
    else
        pc_fmt2(msg, sizeof msg, TR("%d updated, %d failed"), ok, failed);
    if (pg.level == L_FEEDS)
        pg_load_feeds();
    else
        pg_feed_retext();
    pg_redraw();
    if (shown[0]) pod_toast(shown);
}

static int pg_dlg_tick(const void *timer) {
    (void)timer;
    if (!pg.win || !pg.fg || !pg.dlg ||
        !pod_screen_lit()) { /* behind another page, closed, or dark: no visual work; the page's tick starts this again */
        pg.dlg_timer = 0;
        return RET_OK;
    }
    if (!pn_busy()) {
        pg.dlg_timer = 0;
        pg_dlg_finish();
        return RET_OK;
    }
    pg_dlg_update();
    return RET_REPEAT;
}

static void pg_dlg_arm(void) {
    if (pg.dlg && !pg.dlg_timer) pg.dlg_timer = timer_add(pg_dlg_tick, (void *)0, PG_DLG_MS);
}

static void pg_dlg_open(void) {
    pg.dlg_name_hash = 0, pg.dlg_px = 0;
    widget_set_text_utf8(pg.dlg_name, "");
    widget_set_sensitive(pg.dlg_cancel, 1);
    pg_dlg_show(1);
    pg_dlg_update();
    pg_dlg_arm();
}

/* Cancel: the worker is asked to stop (the transfer in progress is aborted, no further show starts); the dialog stays, "Cancelling…", until it has. */
static int pg_on_cancel(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (!pg.dlg) return RET_OK;
    pn_cancel();
    widget_set_sensitive(pg.dlg_cancel, 0);
    if (pn_busy()) pg_dlg_update();
    pg_dlg_arm();
    return RET_OK;
}
/* The guards' words as a toast, for a refresh that did not start. */
static void pg_toast_code(int code) {
    if (code != PN_OK && code != PN_BUSY) pod_toast(pg_status_word(code));
}

/* Refresh the feeds in rows [first, count) that are subscriptions (every one: Refresh All; the new ones after an import: those never refreshed). */
static void pg_refresh(int only_new) {
    int idx[PC_MAX_SHOWS], n = 0, i, r;
    if (pn_dl_running()) { /* downloads pause for a refresh (the queue stays, they go on when it ends): the refresh starts from the page's tick once the thread has stopped */
        pn_dl_pause();
        pg.rpend = only_new + 1;
        pg_awake_arm();
        pg_feed_retext();
        pg_redraw();
        return;
    }
    for (i = 0; i < pg.nrows; ++i) {
        int s = pg.rows[i];
        if (s >= 0 && (!only_new || !pg.shows[s].checked)) idx[n++] = s;
    }
    r = pn_refresh(pg.root, pg.shows, idx, n);
    pg_toast_code(r);
    if (r == PN_OK && pn_busy()) pg_dlg_open();
    pg_feed_retext();
    pg_redraw();
}

/* The Import row: subscribe to what subscriptions.txt lists, then refresh the new ones. */
static void pg_import(void) {
    int n = pn_import(pg.root, pg.shows, pg.nshows);
    char msg[64];
    if (n < 0) {
        pod_toast(TR("Storage unavailable"));
        return;
    }
    if (!n) {
        pod_toast(TR("Nothing new to import"));
        return;
    }
    pc_fmt(msg, sizeof msg, TR("%d added"), (unsigned)n);
    pod_toast(msg);
    pg_load_feeds();
    pg_refresh(1);
}

/* A tap on row a of the Feeds level. */
static void pg_feeds_tap(int a) {
    int row = pg.rows[a];
    if (row == PG_ROW_REFRESH) {
        if (!pn_busy()) pg_refresh(0);
    } else if (row == PG_ROW_IMPORT) {
        if (!pn_busy()) pg_import();
    } else if (row == PG_ROW_DOWNLOADS) {
        pg_load_downloads(0); /* the Downloads level */
    } else
        pg_open_show(row, 1);
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

static int pg_join(char *out, unsigned size, const char *dir, const char *file) {
    unsigned n = 0, k;
    const char *parts[3];
    int p;
    parts[0] = pg.root, parts[1] = dir, parts[2] = file;
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

static int pg_path(const pc_ep_t *e, char *out, unsigned size) {
    return pg_join(out, size, pg.shows[pg.sel].dir, e->file);
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
    if (at < 0 || at >= pg.neps || pg.eps[at].state != PC_LOCAL || !pg_path(&pg.eps[at], path, sizeof path) ||
        access(path, F_OK)) {
        pod_toast(TR("Storage unavailable"));
        return;
    }
    queue = _create_deque("stSongInfo");
    if (!queue) return;
    deque_init(queue);
    for (i = 0; i < pg.neps; ++i) {
        unsigned rec[PG_REC_SIZE / 4];
        char p[PC_FILE * 2 + 40];
        if (pg.eps[i].state != PC_LOCAL || !pg_path(&pg.eps[i], p, sizeof p)) {
            if (i < at)
                --at; /* not on the card (the Feeds view lists those), or a name that does not fit (the model refused such names; this is the belt): not in the queue */
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
    navigator_to_with_context("playing_page", &context); /* start_player copies the queue */
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
    if (pg.level == L_EPS && pt[1] < PC_HDR_H)
        return pt[0] >= PG_HDR_TEXT_X && pt[1] >= PG_SPEED_Y && pt[1] < PG_SPEED_Y + PG_SPEED_H
                   ? -2
                   : -1; /* the speed, or the header */
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
    if (a >= 0 && !pg.select) pg_set_press(a + 1);
    (void)x;
    return RET_OK;
}

/* A tap on an episode that is not on the card: a queued or running download is cancelled (its .part stays, a later tap resumes it); anything else (not downloaded, Paused, Failed) is queued. */
static void pg_dl_toggle(const char *dir, const char *file) {
    unsigned key, got, total;
    int code, st, r;
    if (!file[0]) return;
    key = pn_dl_key(dir, file);
    st = pn_dl_state(key, &code, &got, &total);
    if (st == PN_DL_WAIT || st == PN_DL_ACTIVE)
        pn_dl_cancel(key);
    else {
        r = pn_dl_add(pg.root, dir, file);
        if (r != PN_OK) pod_toast(pg_dl_word(r));
        pg_awake_arm();
    }
}

static void pg_dl_tap(int a) {
    pg_dl_toggle(pg.shows[pg.sel].dir, pg.eps[a].file);
    grid_drop(&pg.g);
    pg_redraw();
}

/* A tap on a row of the Downloads level: what it does on the Show level (a running or waiting one is paused, a paused one resumes, a failed one is tried again). */
static void pg_dls_tap(int a) {
    pg_dl_toggle(pg.dls[a].dir, pg.dls[a].file);
    pg_load_downloads(1);
}

extern int pod_confirm(const char *text); /* patch/m1plus.c: the stock confirm dialog, modal; nonzero for Yes */

/* Whether the player has this file (the stock playing record's path, as the tag reader and the resume code compare). */
static int pg_playing(const char *path) {
    void *t = cc_playing();
    const char *p = t ? *(const char **)((char *)t + REC_PATH) : (const char *)0;
    return p && !strcasecmp(p, path);
}

/* The Delete pill of the select bar, after a confirm (No: the mode stays). Show level: each marked episode's file and .part are unlinked (a .part marked alone is a paused download taken away); the
 * `.episodes` line stays, so the episode is a remote one again, greyed and downloadable; its resume place and played mark are forgotten (pc_mark: it starts fresh when downloaded again). The episode
 * the player is on is never deleted (it is skipped, with a toast). Downloads level: a waiting one leaves the queue, a paused or failed one loses its .part and its failure. */
static int pg_on_delete(void *ctx, void *e) {
    int i, kept = 0;
    (void)ctx;
    (void)e;
    if (!pg.select || !pg.npick) return RET_OK;
    if (!pod_confirm(pg.level == L_DLS ? TR("Remove the selected downloads?") : TR("Delete the selected episodes?")))
        return RET_OK;
    for (i = 0; i < pg_count() && i < PC_MAX_EPS; ++i) {
        char path[PC_FILE * 3 + 24];
        const char *dir = pg.level == L_DLS ? pg.dls[i].dir : pg.shows[pg.sel].dir,
                   *file = pg.level == L_DLS ? pg.dls[i].file : pg.eps[i].file;
        unsigned key = pg.level == L_DLS ? pg.dls[i].key : pn_dl_key(dir, file),
                 hash = pg.level == L_EPS && pg.eps[i].state == PC_LOCAL ? pg.eps[i].hash : 0;
        if (!pg_is_pick(i) || !pg_can_pick(i) || !pg_join(path, sizeof path - 6, dir, file)) continue;
        if (pg.level == L_EPS && pg_playing(path)) {
            ++kept;
            continue;
        }
        pn_dl_cancel(key); /* a waiting one leaves the queue */
        if (pg.level == L_EPS) unlink(path);
        pg_cat(path, sizeof path, ".part");
        unlink(path);
        pn_dl_clear(key);
        if (hash) pc_mark(hash, 0);
    }
    pc_flush();
    pg_select(0);
    if (pg.level == L_DLS)
        pg_load_downloads(1);
    else
        pg_reload_eps();
    if (kept) pod_toast(TR("The playing episode was kept"));
    return RET_OK;
}

static void pg_speed_cycle(void) {
    const pc_show_t *s = &pg.shows[pg.sel];
    int mode = (pc_speed_get(s->hash) + 1) % PC_SPEEDS;
    if (!pc_speed_set(s->hash, mode)) pod_toast(TR("Storage unavailable"));
    pg_header_texts();
    pc_speed_apply(
        s->hash); /* an episode of this show that plays: the decoder takes it at the next start; the stock page shows it */
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
    if (pg.select) {
        if (a > 0 && same == a - 1) pg_toggle_pick(same); /* a tap marks and unmarks; a drag marks nothing */
    } else if (a == -2) {
        if (same == -2) pg_speed_cycle();
    } else if (same == a - 1) {
        if (pg.level == L_DLS)
            pg_dls_tap(same);
        else if (pg.level == L_SHOWS)
            pg_open_show(pg.rows[same], 0);
        else if (pg.level == L_FEEDS)
            pg_feeds_tap(same);
        else if (pg.eps[same].state != PC_LOCAL)
            pg_dl_tap(same); /* not on the card: nothing to play or mark; a tap downloads it, or cancels the download */
        else
            pg_play(same);
    }
    return RET_OK;
}

static int pg_on_abort(void *ctx, void *e) {
    (void)ctx;
    (void)e;
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
    if (pg.dlg && pod_screen_lit())
        pg_dlg_arm(); /* the screen is back on: the dialog's own timer stopped while it was dark */
    if (pod_screen_lit() && pg.level == L_FEEDS && pn_gen() != pg.gen)
        pg_load_feeds(); /* the worker moved on: a show finished, or it ended (the files are read again; the rows are rebuilt) */
    if (pod_screen_lit() && pg.level == L_FEEDS &&
        pg.dgen != pn_dl_gen()) { /* a download moved on: the Downloads row's line */
        pg.dgen = pn_dl_gen();
        pg_feed_retext();
        pg_redraw();
    }
    if (pod_screen_lit() && pg.level == L_EPS) {
        if (pn_gen() != pg.gen && !pg.select)
            pg_reload_eps(); /* (not while rows are marked: the marks are of these rows) a download started, finished or failed: the episodes are read again (a finished one is a file now) */
        else if (pn_dl_gen() != pg.dgen) { /* a step of progress: the state lines are made again */
            pg.dgen = pn_dl_gen();
            grid_drop(&pg.g);
            pg_redraw();
        }
    }
    if (pod_screen_lit() &&
        pg.level ==
            L_DLS) { /* the Downloads level: the rows again when the worker's state moved, the lines for a step of progress */
        if (pn_gen() != pg.gen && !pg.select)
            pg_load_downloads(1);
        else if (pn_dl_gen() != pg.dgen) {
            pg.dgen = pn_dl_gen();
            pg_dls_retext();
            pg_redraw();
        }
    }
    if (pod_screen_lit() && pg.level == L_EPS &&
        pc_rev() != pg.rev) { /* a place or a mark changed: the grey lines are made again */
        pg.rev = pc_rev();
        grid_drop(&pg.g);
        pg_redraw();
    }
    if (pg.rpend && pg.level == L_FEEDS && pod_screen_lit() && !pn_dl_running() && !pn_busy()) {
        int only_new = pg.rpend - 1; /* the downloads have paused: the refresh the user asked for starts */
        pg.rpend = 0;
        pg_refresh(only_new);
    }
    return RET_REPEAT;
}

/* The downloads' timer (1 s), page-scoped like the others but kept in the background too: while a download runs it calls stock's reset_poweroptions_timer(1, 1, 0), which sets the standby and
 * auto power-off countdowns again and leaves the screen's alone (stock standby would stop the Wi-Fi and the CPU, docs/modules/probe.md). It runs on the UI thread, never from the worker. It also starts the
 * queue again when no thread runs (after a refresh, or a tap that raced the worker's end) and drops a refresh nobody can see start. No widget is touched. It ends when nothing is queued. */
static int pg_awake_tick(const void *timer) {
    (void)timer;
    if (!pg.win) {
        pg.awake = 0;
        return RET_OK;
    }
    if (pn_dl_running()) reset_poweroptions_timer(1, 1, 0);
    if (pg.rpend && !pn_dl_running() && !pn_busy() && (pg.level != L_FEEDS || !pg.fg || !pod_screen_lit()))
        pg.rpend = 0; /* the page is not there to open the refresh's dialog: the downloads go on */
    if (!pg.rpend && pn_dl_waiting() && !pn_dl_running()) pn_dl_start();
    if (!pn_dl_count() && !pg.rpend) {
        pg.awake = 0;
        return RET_OK;
    }
    return RET_REPEAT;
}

static void pg_awake_arm(void) {
    if (pg.win && !pg.awake && (pn_dl_count() > 0 || pg.rpend))
        pg.awake = timer_add(pg_awake_tick, (void *)0, PG_AWAKE_MS);
}

static void pg_arm(void) {
    if (!pg.timer) pg.timer = timer_add(pg_tick, (void *)0, PG_TICK_MS);
}

static int pg_on_fg(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    pg.fg = 1;
    pg_arm();
    if (pg.dlg &&
        pod_screen_lit()) { /* the dialog was up when another page came in front: it is still right (or closes at its first tick) */
        pg_dlg_update();
        pg_dlg_arm();
    }
    if (pg.level == L_FEEDS) pg_load_feeds(); /* a refresh may have ended while another page was in front */
    if (pg.level == L_DLS && !pg.select) pg_load_downloads(1); /* so may a download */
    if (pg.level == L_EPS) { /* the grey lines are made again: a place may have changed, and "4h ago" is a time later */
        pg.rev = pc_rev();
        grid_drop(&pg.g);
        pg_redraw();
    }
    pg_kick();
    return RET_OK;
}

static int pg_on_bg(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    pg.fg = 0;
    if (pg.timer) timer_remove(pg.timer);
    if (pg.load_timer) timer_remove(pg.load_timer);
    if (pg.dlg_timer) timer_remove(pg.dlg_timer);
    pg.timer = pg.load_timer = pg.dlg_timer = 0;
    pg.down = 0;
    pg.press = 0;
    pc_flush();
    return RET_OK;
}

static int pg_on_destroy(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (pg.timer) timer_remove(pg.timer);
    if (pg.load_timer) timer_remove(pg.load_timer);
    if (pg.dlg_timer) timer_remove(pg.dlg_timer);
    if (pg.awake)
        timer_remove(
            pg.awake); /* the downloads go on while the device is awake; nothing keeps it awake without this window */
    if (pg.dlg) pn_cancel(); /* the page is closed (the hardware Back key) with the dialog up: that is Cancel too */
    pc_flush();
    grid_free(&pg.g);
    grid_free(&pg.hg);
    if (pg.mark[0]) bitmap_destroy(pg.mark[0]);
    if (pg.mark[1]) bitmap_destroy(pg.mark[1]);
    free(pg.shows);
    free(pg.eps);
    free(pg.dls);
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
    pg.back = pod_bind(pg.win, "btn_return", pg_on_back, (void *)0);
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
    pg.st_act = widget_lookup(pg.win, "label_row_act", 1);
    pg.np = widget_lookup(pg.win, "btn_backtoplayer", 1);
    pod_bind(pg.win, "btn_feeds", pg_on_feeds, (void *)0);
    pg.dlg_scrim = widget_lookup(pg.win, "pod_pd_scrim", 1);
    pg.dlg_card = widget_lookup(pg.win, "pod_pd_card", 1);
    pg.dlg_name = widget_lookup(pg.win, "pod_pd_name", 1);
    pg.dlg_count = widget_lookup(pg.win, "pod_pd_count", 1);
    pg.dlg_fill = widget_lookup(pg.win, "pod_pd_fill", 1);
    pg.dlg_cancel = pod_bind(pg.win, "pod_pd_cancel", pg_on_cancel, (void *)0);
    pg.btn_feeds = widget_lookup(pg.win, "btn_feeds", 1);
    pg.btn_select =
        pod_bind(pg.win, "btn_select", pg_on_select,
                 (void *)0); /* select mode's widgets: optional (without them the Select button never shows) */
    pg.btn_selall = pod_bind(pg.win, "btn_selall", pg_on_selall, (void *)0);
    pg.del = pod_bind(pg.win, "pg_del", pg_on_delete, (void *)0);
    pg.bar = widget_lookup(pg.win, "pg_bar", 1);
    if (!pg.view || !pg.sv || !pg.status || !pg.title || !pg.st_title || !pg.st_sub || !pg.st_dim || !pg.st_acc ||
        !pg.st_act || !pg.btn_feeds || !pg.dlg_scrim || !pg.dlg_card || !pg.dlg_name || !pg.dlg_count || !pg.dlg_fill ||
        !pg.dlg_cancel) {
        navigator_back(); /* an asset that is not ours */
        return -1;
    }
    label_set_line_wrap(pg.status, 1);
    pg.shows = calloc(PC_MAX_SHOWS, sizeof *pg.shows);
    if (!pg.shows || !grid_init(&pg.g, pg.win, PC_TILES, LIST_ART, LIST_R) ||
        !grid_init(&pg.hg, pg.win, 1, PC_HDR_ART, 10)) {
        pg_empty("Not enough memory");
        return 0;
    }
    pg.g.st_title = pg.st_title, pg.g.st_sub = pg.st_sub;
    pg.dls = calloc(PG_DL_MAX, sizeof *pg.dls);
    if (pg.del) pod_centre_pill(pg.del, PL_BAR_PILL_W);
    pc_root(pg.root);
    pg.mark[0] = pod_make_mark(pg.win, "unselect");
    pg.mark[1] = pod_make_mark(pg.win, "selected");
    if (!pg.mark[1] && pg.mark[0]) bitmap_destroy(pg.mark[0]), pg.mark[0] = (void *)0;
    pg.fg = 1;
    pg.noscroll = !widget_on(pg.sv, EVT_SCROLL, pg_on_scroll, (void *)0) ||
                  !widget_on(pg.sv, EVT_SCROLL_END, pg_on_scroll, (void *)0);
    widget_on(pg.win, EVT_WINDOW_TO_FG, pg_on_fg, (void *)0);
    widget_on(pg.win, EVT_WINDOW_TO_BG, pg_on_bg, (void *)0);
    widget_on(pg.view, EVT_POINTER_DOWN, pg_on_down, (void *)0);
    widget_on(pg.view, EVT_POINTER_UP, pg_on_up, (void *)0);
    widget_on(pg.view, EVT_POINTER_ABORT, pg_on_abort, (void *)0);
    widget_on(pg.view, EVT_AFTER_PAINT, pg_on_paint, (void *)0);
    pg_arm();
    pg_awake_arm(); /* a download queued by an earlier window of the page is still going */
    pg_load_shows();
    return 0;
}
