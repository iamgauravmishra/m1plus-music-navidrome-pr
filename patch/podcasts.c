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
 *   Show       the Apple Podcasts style page (docs/modules/podcasts.md "The Show page"): a header in the album page's manner (the PS_ART px cover, the name, a Latest Episode pill, the
 *              show's description and its "Category - Author" line, tinted from the cover as the album page is), then a fixed height cell per episode, newest first (PS_CELL_H: the date
 *              line with its badges, the title, the description, the state pill and the "..."). The navbar is "... | Now Playing" (the sheet of the show's actions) and, scrolled, the small
 *              title. A tap on a cell that is on the card plays it and the ones after it in the list's order (from the first second, or from the saved place: pc_note jumps there).
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
#include "pcwrap.h"

extern void pod_toast(const char *text); /* patch/shuffle.c: the stock message box */
extern void pod_set_in_order(void); /* patch/shuffle.c: Shuffle and Repeat one become List play */

#define I(w, off) (*(int *)((char *)(w) + (off)))
#define B(w, off) (*(unsigned char *)((char *)(w) + (off)))
#define P(w, off) (*(void **)((char *)(w) + (off)))

#define PG_W 320
#define PG_LOAD_MS 16
#define PG_TICK_MS 1000
#define PG_TAP_PX SC_DRAG_PX
#define PG_BOTTOM 20 /* the Show level's last cell has this much under it */
#define PG_REC_SIZE 0x58
#define PG_ACT_X 16 /* the action rows (Refresh All, Import) of the Feeds level: no cover, the text from here */
#define PG_CELLS \
    8 /* the Show level's cell layouts: a ring keyed by the episode's index modulo this (at most four cells show at once) */
#define PG_FADE_H \
    20 /* the Show level's navbar fade (the page's colour, drawn over the first rows while the list is scrolled): nb_fade's height */
#define PG_TEXT_MAX 232 /* wide chars of a cell's description (at most PC_DESC_CUT bytes) and room for the ellipsis */
#define PG_TITLE_MAX 100 /* wide chars of a title (95 bytes at most) */
#define PG_PILL_MAX 48 /* wide chars of a pill's label */
#define PG_SHEET_ROWS 9 /* the sheets' fixed rows (tools/pod_ui.py PS_SHEET_ROWS) */
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

typedef struct
{ /* a cell's layout: made once when it first paints (the wrap needs the font), dropped when the list is made again */
    int idx; /* the episode's index + 1, 0 = free */
    unsigned title[PG_TITLE_MAX], desc[PG_TEXT_MAX], date[40];
    pw_line_t tl[2], dl[2];
    int tn, dn, datelen;
} pg_cell_t;

typedef struct { /* the Show header's layout: the texts wrapped, the blocks' tops (content y) */
    unsigned name[PG_TITLE_MAX], desc[PG_TEXT_MAX], meta[PG_TEXT_MAX];
    pw_line_t nl[PS_NAME_LINES], dl[PS_DESC_LINES], ml[1];
    int nn, nd, nm; /* lines of each */
    int y_name, y_latest, y_desc, y_meta, y_head, h; /* the blocks' tops; h is where the cells start */
    int has_latest; /* there is an episode: the pill shows */
    int collapse; /* the offset from which the navbar shows the small title */
} pg_hdr_t;

enum {
    PK_PLAY = 0,
    PK_RESUME,
    PK_DOWN,
    PK_RING,
    PK_PAUSED,
    PK_RETRY
}; /* a state pill's kind: the first two are filled (play-type), the others outlined (download-type) */
enum { PH_BODY = 0, PH_PILL = 1, PH_DOTS = 2, PH_LATEST = 3 }; /* what a touch on the Show level hit */
enum {
    SR_SPEED = 0,
    SR_REFRESH,
    SR_SELECT,
    SR_MARKALL,
    SR_UNSUB,
    SR_DL,
    SR_RM,
    SR_MARK,
    SR_UNMARK
}; /* the sheets' rows, tools/pod_ui.py PS_SHEET_ROWS */
enum { SH_NONE = 0, SH_SHOW = 1, SH_CELL = 2 };
enum {
    ST_NAME = 0,
    ST_SEC,
    ST_META,
    ST_HEAD,
    ST_DATE,
    ST_CTITLE,
    ST_CDIM,
    ST_CDESC,
    ST_PILL,
    ST_LATEST,
    ST_LATESTW,
    ST_N
}; /* the text styles of the Show page */

typedef struct { /* a state pill: its kind, the ring step, and the label (wide) with its width in px */
    int kind, ring, nlabel, w;
    unsigned label[PG_PILL_MAX];
} pg_pill_t;

static struct {
    void *win, *view, *sv, *status, *title, *fade;
    void *st_title, *st_sub,
        *st_act; /* hidden labels whose styles are the row title, the grey line and an action row's title */
    void *st[ST_N]; /* the Show page's text styles, hidden labels (tools/pod_ui.py PS_STYLES, in that order) */
    void *dlg_scrim, *dlg_card, *dlg_name, *dlg_count, *dlg_fill,
        *dlg_cancel; /* the refresh dialog (hidden widgets of the asset) */
    void *btn_feeds, *btn_more,
        *np; /* the navbar's Feeds button (the Shows level only), the Show level's "..." and Now Playing (the capsule's right cap, a disc where neither is) */
    void *tint_img; /* img_ah_tint: the album page's gradient, shown on the Show level while the page is tinted */
    void *sh_scrim, *sh_card, *sh_row[PG_SHEET_ROWS], *sh_tx[PG_SHEET_ROWS], *sh_hr[PG_SHEET_ROWS],
        *sh_vl
            [2]; /* the sheets (widgets of the asset): scrim, card, and per row the button, its label, its hairline; the value labels of Playback Speed and Refresh Feed */
    int sheet, sh_ep; /* SH_NONE / SH_SHOW / SH_CELL; the episode of a cell's sheet */
    char root[PC_FILE + 20];
    pc_show_t *shows;
    int nshows; /* every folder the model found (shows with files, subscriptions without) */
    int rows
        [PC_MAX_SHOWS +
         3]; /* the rows of the Shows / Feeds level: an index into shows, or PG_ROW_REFRESH / PG_ROW_IMPORT / PG_ROW_DOWNLOADS */
    int nrows;
    int from_feeds; /* the Show level was opened from Feeds: Back goes there (else to Shows) */
    unsigned gen; /* pn_gen() the Feeds rows were made at */
    pc_ep_t *eps; /* the episodes of the show open (on the card or not), newest first */
    int neps;
    int level, sel, show_off,
        feeds_off; /* the level, the show open (an index into shows), the Shows and Feeds lists' offsets to come back to */
    int press, down, down_part, down_x,
        down_y; /* the row under the finger + 1; the row a press began on + 1 (0 none) and what of it (PH_*), and where */
    int fg, noscroll;
    unsigned rev; /* pc_rev() the rows were made at */
    unsigned timer, load_timer, dlg_timer,
        awake; /* awake: the downloads' timer (keeps the device awake, starts the queue again): scoped to the window, in front or not */
    int rpend; /* a refresh waits for the downloads to pause: 1 + only_new */
    int rone; /* ... and it is of the show open only (the Show level's Refresh Feed): 1, else 0 (Refresh All / Import) */
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
    unsigned
        feed_hash; /* pc_hash of the open show's feed url (0: none): a refresh may rename the folder, so the show is found again by it */
    unsigned tint,
        tint_key; /* the Show page's colour (0x00BBGGRR, 0: black) and the tone cache key of the show (0: none) */
    int tint_on, bar_ours,
        collapsed; /* the page is tinted (window colour, gradient shown); the status bar is ours; the small title shows */
    void *atlas; /* pc_atlas decoded with its alpha (PA_SIZE square), once the Show level first paints */
    pg_cell_t *cells; /* PG_CELLS layouts of the Show level's cells */
    pg_hdr_t *hdr; /* the Show header's layout */
    grid_t g; /* the tiles: a show's cover and texts (Shows, Feeds, Downloads) */
    grid_t hg; /* the Show header's cover (one tile) */
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
static int pg_top(void) {
    return pg.level == L_EPS && pg.hdr ? pg.hdr->h : 0;
} /* where the rows start in the content */
static int pg_row_h(void) { return pg.level == L_EPS ? PS_CELL_H : PC_ROW_H; }
static int pg_content(void) {
    return (pg_count()          ? pg_top() + pg_count() * pg_row_h() + (pg.level == L_EPS ? PG_BOTTOM : 0)
            : pg.level == L_EPS ? pg_top()
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
    *r0 = s / pg_row_h();
    *r1 = (s + GRID_VIEW_H - 1) / pg_row_h();
    if (s < 0) *r0 = 0;
    if (*r0 < 0) *r0 = 0;
    if (*r1 > n - 1) *r1 = n - 1;
}

/* ---------------------------------------------------------------------------
 * Texts and tiles
 */
static void pg_cat(char *out, unsigned size, const char *s);

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

/* ---------------------------------------------------------------------------
 * The Show page's layouts (docs/modules/podcasts.md "The Show page"): the texts are wrapped once, from the glyphs' own advances (patch/pcwrap.c), when the page opens and when a cell first
 * paints; the states (pills, badges, colours) are read at every paint, from the model, the ring and the worker, so a step of progress needs no layout.
 */
static int pg_join(char *out, unsigned size, const char *dir, const char *file);

static int pg_wlen(const unsigned *s) {
    int n = 0;
    while (s[n]) ++n;
    return n;
}

/* The UTF-8 text as wide chars into dst (cap of them, the NUL included); its length. */
static int pg_wide(unsigned *dst, int cap, const char *utf8) {
    unsigned n = 0;
    while (utf8[n] && n < 4u * (unsigned)cap) ++n;
    tk_utf8_to_utf16_ex(utf8, n, dst, (unsigned)cap);
    return pg_wlen(dst);
}

static int pg_width(void *st, const unsigned *s) { return (int)(widget_measure_text(st, s) + 0.999f); }

/* The advance AWTK charges for each of the n chars of s in the style label st (the glyph's width and 1 px: docs/modules/text-width.md): one measure per char, the widths being additive. */
static void pg_adv(void *st, const unsigned *s, int n, unsigned short *adv) {
    unsigned t[2];
    int i;
    t[1] = 0;
    for (i = 0; i < n; ++i) {
        t[0] = s[i];
        adv[i] = (unsigned short)pg_width(st, t);
    }
}

/* s (n chars) in at most maxl lines of room px in the style st (patch/pcwrap.c: kinsoku, an ellipsis on the last line when text is left); the number of lines. */
static int pg_lines(void *st, unsigned *s, int n, int room, int maxl, pw_line_t *out) {
    unsigned short adv[PG_TEXT_MAX];
    unsigned e[2];
    e[0] = ELLIPSIS, e[1] = 0;
    if (n > PG_TEXT_MAX - 1) n = PG_TEXT_MAX - 1, s[n] = 0;
    pg_adv(st, s, n, adv);
    return pw_wrap(s, n, adv, room, maxl, pg_width(st, e), out);
}

/* The Show header's layout of the show open: the name, the pill, the description and the "Category - Author" line wrapped, the blocks' tops (docs/modules/podcasts.md for the rhythm). */
static void pg_hdr_make(void) {
    pg_hdr_t *h = pg.hdr;
    const pc_show_t *s = &pg.shows[pg.sel];
    char meta[PC_CAT + PC_AUTHOR + 8];
    int y, n, gap = PS_LATEST_GAP;
    if (!h) return;
    memset(h, 0, sizeof *h);
    n = pg_wide(h->name, PG_TITLE_MAX, s->title);
    h->nn = pg_lines(pg.st[ST_NAME], h->name, n, PS_NAME_W, PS_NAME_LINES, h->nl);
    y = PS_ART + PS_NAME_GAP;
    h->y_name = y;
    y += h->nn * PS_NAME_PITCH;
    h->collapse = y - PS_COLLAPSE_BACK;
    h->has_latest = pg.neps > 0;
    if (h->has_latest) {
        y += PS_LATEST_GAP;
        h->y_latest = y;
        y += PS_LATEST_H;
        gap = PS_DESC_GAP;
    }
    n = pg_wide(h->desc, PG_TEXT_MAX, s->desc);
    if (n) {
        y += gap;
        h->y_desc = y;
        h->nd = pg_lines(pg.st[ST_SEC], h->desc, n, PS_DESC_W, PS_DESC_LINES, h->dl);
        y += h->nd * PS_DESC_PITCH;
        gap = PS_META_GAP;
    }
    meta[0] = 0;
    pg_cat(meta, sizeof meta, s->category);
    if (s->category[0] && s->author[0]) pg_cat(meta, sizeof meta, " \xc2\xb7 "); /* " · " */
    pg_cat(meta, sizeof meta, s->author);
    n = pg_wide(h->meta, PG_TEXT_MAX, meta);
    if (n) {
        y += gap;
        h->y_meta = y;
        h->nm = pg_lines(pg.st[ST_META], h->meta, n, PS_DESC_W, 1, h->ml);
        y += PS_META_PITCH;
    }
    y += PS_HEAD_GAP;
    h->y_head = y;
    h->h = y + PS_HEAD_H;
}

/* The ring key of an episode: its file's, else the one its name would have (a played mark and a place belong to the path, so they survive a download and a removal). 0: no name. */
static unsigned pg_ep_hash(const pc_ep_t *e) {
    char path[PC_FILE * 3 + 24];
    if (e->hash) return e->hash;
    if (!e->file[0] || !pg_join(path, sizeof path, pg.shows[pg.sel].dir, e->file)) return 0;
    return pc_hash(path);
}

/* An episode's played state (PC_NEW / PC_PROGRESS / PC_DONE), also for one that is not on the card. */
static int pg_ep_state(const pc_ep_t *e, unsigned *pos, unsigned *len) {
    unsigned h = pg_ep_hash(e);
    *pos = *len = 0;
    return h ? pc_state(h, pos, len) : PC_NEW;
}

/* A cell's layout: the title and the description wrapped (two lines each), the date; made when it first paints, kept in the ring until the list is made again. */
static pg_cell_t *pg_cell(int a) {
    pg_cell_t *c;
    char date[48];
    int n, room = PS_CELL_W - (pg.select ? SG_SEL_COL : 0);
    if (!pg.cells || a < 0 || a >= pg.neps) return (pg_cell_t *)0;
    c = &pg.cells[a % PG_CELLS];
    if (c->idx == a + 1) return c;
    memset(c, 0, sizeof *c);
    c->idx = a + 1;
    n = pg_wide(c->title, PG_TITLE_MAX, pg.eps[a].title);
    c->tn = pg_lines(pg.st[ST_CTITLE], c->title, n, room, 2, c->tl);
    n = pg_wide(c->desc, PG_TEXT_MAX, pg.eps[a].desc);
    c->dn = pg_lines(pg.st[ST_CDESC], c->desc, n, room, 2, c->dl);
    date[0] = 0;
    if (pg.eps[a].pub) pc_when(pg.eps[a].pub, (unsigned)time((long *)0), date, sizeof date);
    c->datelen = pg_wide(c->date, 40, date);
    return c;
}

static void pg_cells_drop(void) {
    if (pg.cells) memset(pg.cells, 0, PG_CELLS * sizeof *pg.cells);
}

/* The kind and the words of an episode's state pill (the table in docs/modules/podcasts.md): on the card a play pill (the length, or what is left of a started one), not on the card a
 * download-type pill (its size; the ring and its percent while it downloads, Waiting, Paused, Retry). ring: the step of the progress ring. */
static void pg_pill_base(const pc_ep_t *e, int *kind, int *ring, char *out, unsigned size) {
    int code = 0, st;
    unsigned got = 0, total = 0, key;
    out[0] = 0;
    *ring = 0;
    if (e->state == PC_LOCAL) {
        unsigned pos, len, whole;
        int s = pc_state(e->hash, &pos, &len);
        whole = len ? len : e->dur;
        if (s == PC_PROGRESS && whole > pos) {
            *kind = PK_RESUME;
            pc_fmt(out, size, TR("%dm left"), (whole - pos + 59) / 60);
        } else {
            *kind = PK_PLAY;
            if (whole)
                pc_fmt(out, size, TR("%dm"), (whole + 59) / 60);
            else
                pg_cat(out, size, TR("Play"));
        }
        return;
    }
    key = e->file[0] ? pn_dl_key(pg.shows[pg.sel].dir, e->file) : 0;
    st = key ? pn_dl_state(key, &code, &got, &total) : PN_DL_NONE;
    if (st == PN_DL_ACTIVE) {
        *kind = PK_RING;
        if (total && total >= got) {
            unsigned pct = (got >> 10) * 100 / ((total >> 10) ? (total >> 10) : 1);
            if (pct > 100) pct = 100;
            *ring = (int)(pct * PA_RING_N / 100);
            if (*ring > PA_RING_N - 1) *ring = PA_RING_N - 1;
            pc_fmt(out, size, "%d%", pct);
        } else
            pc_fmt(out, size, TR("%d MB"), got >> 20);
    } else if (st == PN_DL_WAIT) {
        *kind = PK_RING;
        pg_cat(out, size, TR("Waiting"));
    } else if (st == PN_DL_FAILED) {
        *kind = PK_RETRY;
        pg_cat(out, size, TR("Retry"));
    } else if (e->state == PC_PART) {
        *kind = PK_PAUSED;
        pg_cat(out, size, TR("Paused"));
    } else {
        *kind = PK_DOWN;
        if (e->length)
            pc_fmt(out, size, TR("%d MB"), (e->length + 1048575) >> 20);
        else
            pg_cat(out, size, TR("Download"));
    }
}

static void pg_pill_of(const pc_ep_t *e, pg_pill_t *p) {
    char label[72];
    pg_pill_base(e, &p->kind, &p->ring, label, sizeof label);
    p->nlabel = pg_wide(p->label, PG_PILL_MAX, label);
    p->w = PS_PILL_PADL + PA_G_PX + PS_PILL_GAP + pg_width(pg.st[ST_PILL], p->label) + PS_PILL_PADR;
}

/* The Latest Episode pill of episode e (the newest): white with the dark play glyph when it is on the card (a started one too); else outlined, reading "Latest Episode - <the cell's pill>". */
static void pg_latest_of(const pc_ep_t *e, pg_pill_t *p) {
    char base[72], label[110];
    pg_pill_base(e, &p->kind, &p->ring, base, sizeof base);
    label[0] = 0;
    pg_cat(label, sizeof label, TR("Latest Episode"));
    if (e->state == PC_LOCAL)
        p->kind = PK_PLAY;
    else {
        pg_cat(label, sizeof label, " \xc2\xb7 "); /* " · " */
        pg_cat(label, sizeof label, base);
    }
    p->nlabel = pg_wide(p->label, PG_PILL_MAX, label);
    {
        void *st = pg.st[e->state == PC_LOCAL ? ST_LATEST : ST_LATESTW];
        pw_line_t ln;
        if (pg_lines(st, p->label, p->nlabel,
                     PS_LATEST_MAX - PS_LATEST_PADL - PS_LATEST_GLYPH - PS_LATEST_GAPG - PS_LATEST_PADR, 1, &ln) == 1) {
            p->nlabel =
                ln.len; /* (a long state word in a long language: the label ends in an ellipsis, the pill is at most PS_LATEST_MAX) */
            p->label[ln.len] = 0;
        }
        p->w = PS_LATEST_PADL + PS_LATEST_GLYPH + PS_LATEST_GAPG + pg_width(st, p->label) + PS_LATEST_PADR;
    }
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

/* pc_atlas (tools/mod_icons.py pc_atlas: the progress ring, the state glyphs, the badge, the "..." and the pills' ends) decoded WITH its alpha into a bitmap of ours, once: the image manager's copy is
 * dropped at once, as the covers' are. cc_decode would composite over black. NULL when it cannot be made (the Show level then paints no cells). */
static void *pg_atlas(void) {
    static const unsigned char at[4][4] = BITMAP_RGBA_AT;
    unsigned bitmap[32], format, x, y, *px;
    const unsigned char *data;
    void *b = (void *)0;
    if (pg.atlas) return pg.atlas;
    memset(bitmap, 0, sizeof bitmap);
    if (widget_load_image(pg.win, "pc_atlas", bitmap)) return (void *)0;
    format = (unsigned)(*(unsigned short *)((char *)bitmap + BITMAP_FORMAT)) - 1u;
    data = format < 4 && bitmap[0] == PA_SIZE && bitmap[1] == PA_SIZE ? bitmap_lock_buffer_for_read(bitmap)
                                                                      : (const unsigned char *)0;
    if (data) b = bitmap_create_ex(PA_SIZE, PA_SIZE, PA_SIZE * 4, BITMAP_RGBA8888);
    px = b ? (unsigned *)bitmap_lock_buffer_for_write(b) : (unsigned *)0;
    if (px && bitmap_get_line_length(b) == PA_SIZE * 4) {
        unsigned stride = bitmap_get_line_length(bitmap);
        for (y = 0; y < PA_SIZE; ++y)
            for (x = 0; x < PA_SIZE; ++x) {
                const unsigned char *s = data + y * stride + x * 4;
                px[y * PA_SIZE + x] = s[at[format][0]] | s[at[format][1]] << 8 | s[at[format][2]] << 16 |
                                      (unsigned)s[at[format][3]] << 24;
            }
    } else if (b) {
        bitmap_destroy(b);
        b = (void *)0;
    }
    if (px) bitmap_unlock_buffer(b);
    if (data) bitmap_unlock_buffer(bitmap);
    widget_unload_image(pg.win, bitmap);
    pg.atlas = b;
    return b;
}

/* A w x h piece of the atlas from (sx, sy) at (x, y) of the view, cut by hand to the rows inside it (grid_blit's rule). */
static void pg_sprite(void *canvas, int sx, int sy, int w, int h, int x, int y) {
    int src[4], dst[4], top = y < 0 ? -y : 0, bottom = y + h > GRID_VIEW_H ? GRID_VIEW_H - y : h;
    if (!pg.atlas || bottom <= top) return;
    src[0] = sx, src[1] = sy + top, src[2] = w, src[3] = bottom - top;
    dst[0] = x, dst[1] = y + top, dst[2] = w, dst[3] = bottom - top;
    canvas_draw_image(canvas, pg.atlas, src, dst);
}

static void pg_glyph(void *canvas, int idx, int x, int y) {
    pg_sprite(canvas, idx * PA_G_PX, PA_G_Y, PA_G_PX, PA_G_PX, x, y);
}

/* The glyph of a pill of kind k (the ring's step ring): the play triangle, the arrow, the pause bars, the retry arrow, a ring. */
static void pg_kind_glyph(void *canvas, int kind, int ring, int x, int y) {
    if (kind == PK_RING)
        pg_sprite(canvas, ring % PA_RING_COLS * PA_RING_PX, ring / PA_RING_COLS * PA_RING_PX, PA_RING_PX, PA_RING_PX, x,
                  y);
    else
        pg_glyph(canvas,
                 kind == PK_PLAY     ? PA_PLAY
                 : kind == PK_DOWN   ? PA_ARROW
                 : kind == PK_PAUSED ? PA_PAUSE
                                     : PA_RETRY,
                 x, y);
}

/* A stadium of w x h at (x, y): its ends are halves of the disc at atlas x ax (the ring or the filled disc), the body between them a fill (colour body: a filled pill) or two 2 px lines (outlined). */
static void pg_pill_shape(void *canvas, int x, int y, int w, int h, int ax, unsigned body, int outline) {
    int r = h / 2;
    pg_sprite(canvas, ax, PA_PILL_Y, r, h, x, y);
    pg_sprite(canvas, ax + r, PA_PILL_Y, r, h, x + w - r, y);
    if (!outline) {
        az_fill(canvas, x + r, y, y + h, w - 2 * r, body);
    } else {
        az_fill(canvas, x + r, y, y + 2, w - 2 * r, body);
        az_fill(canvas, x + r, y + h - 2, y + h, w - 2 * r, body);
    }
}

/* A cell's state pill at (x, y): filled for the play-type kinds, outlined for the download-type ones, the glyph in the pad. The label is drawn in the text pass. */
static void pg_pill_paint(void *canvas, int x, int y, const pg_pill_t *p) {
    int filled = p->kind <= PK_RESUME;
    pg_pill_shape(canvas, x, y, p->w, PS_PILL_H, filled ? PA_PILLF_X : PA_PILLO_X,
                  ((unsigned)(filled ? PA_FILL_A : PA_RING_A) << 24) | 0xffffffu, !filled);
    pg_kind_glyph(canvas, p->kind, p->ring, x + PS_PILL_PADL, y + (PS_PILL_H - PA_G_PX) / 2);
}

/* The Latest Episode pill at (x, y): white with the dark play glyph, or outlined with the state's glyph. */
static void pg_latest_paint(void *canvas, int x, int y, const pg_pill_t *p) {
    int white = p->kind == PK_PLAY, gx = x + PS_LATEST_PADL - (PA_G_PX - PS_LATEST_GLYPH) / 2,
        gy = y + (PS_LATEST_H - PA_G_PX) / 2;
    pg_pill_shape(canvas, x, y, p->w, PS_LATEST_H, white ? PA_PILLW_X : PA_PILLR_X,
                  white ? 0xffffffffu : (((unsigned)PA_RING_A << 24) | 0xffffffu), !white);
    if (white)
        pg_glyph(canvas, PA_PLAYK, gx, gy);
    else
        pg_kind_glyph(canvas, p->kind, p->ring, gx, gy);
}

/* A text drawn wholly inside the view only (every text of the payload's pages: AWTK does not clip it). The canvas has the style. */
static void pg_text(void *canvas, const unsigned *s, int n, int x, int y, int w, int h) {
    int rect[4];
    rect[0] = x, rect[1] = y, rect[2] = w, rect[3] = h;
    if (n > 0 && y >= 0 && y + h <= GRID_VIEW_H) canvas_draw_text_in_rect(canvas, s, (unsigned)n, rect);
}

static void pg_style(void *canvas, int st) { widget_prepare_text_style(pg.st[st], canvas); }

/* The navbar's fade on the Show level, over the first rows while the list is scrolled: the page's colour (the tone under the gradient, black on a page without a cover) with nb_fade's eased alpha
 * (tools/mod_icons.py nb_fade_alpha), so the rows dissolve under the bar as they do on the other pages; the bar itself is the page behind it. */
static void pg_paint_fade(void *canvas) {
    static const unsigned char alpha[PG_FADE_H] = {233, 193, 158, 128, 102, 80, 62, 47, 35, 25,
                                                   17,  12,  7,   4,   2,   1,  0,  0,  0,  0};
    int y;
    for (y = 0; y < PG_FADE_H; ++y)
        if (alpha[y])
            az_fill(canvas, 0, y, y + 1, PG_W,
                    ((unsigned)alpha[y] << 24) | (pg.tint ? pod_shade(pg.tint, (unsigned)(PG_LIST_Y + y), AH_TINT_A_TOP,
                                                                      AH_TINT_A_BOT, AH_TINT_ROWS)
                                                          : 0));
}

#define PG_SEEN 6 /* cells the view can touch at once (400 / PS_CELL_H rounded up, plus a margin) */

static void pg_paint_eps(void *canvas) {
    int r0, r1, r, k, off = pg_off(), sx = pg.select ? SG_SEL_COL : 0, hy = pg_top(), played[PG_SEEN], datex[PG_SEEN];
    pg_hdr_t *h = pg.hdr;
    pg_pill_t pill[PG_SEEN], lp;
    if (!h || !pg.hg.tiles || !pg_atlas()) return;
    memset(&lp, 0, sizeof lp);
    pg_span(&r0, &r1);
    if (r1 - r0 + 1 > PG_SEEN) r1 = r0 + PG_SEEN - 1;
    if (off < hy) {
        grid_blit(canvas, &pg.hg, &pg.hg.tiles[0], PS_ART_X, -off, GRID_VIEW_H);
        if (h->has_latest) {
            pg_latest_of(&pg.eps[0], &lp);
            pg_latest_paint(canvas, (PG_W - lp.w) / 2, h->y_latest - off, &lp);
        }
    }
    for (r = r0; r <= r1; ++r) { /* the cells' fills and pictures */
        const pc_ep_t *e = &pg.eps[r];
        unsigned pos, len;
        int y = hy + r * PS_CELL_H - off, x = PS_CELL_X + sx, i = r - r0;
        played[i] = pg_ep_state(e, &pos, &len) == PC_DONE;
        pg_pill_of(e, &pill[i]);
        if (pg.press == r + 1 && !pg.select) az_fill(canvas, 0, y, y + PS_CELL_H - 1, PG_W, 0x30ffffffu);
        az_fill(canvas, PS_CELL_X, y + PS_CELL_H - 1, y + PS_CELL_H, PG_W - PS_CELL_X, 0x22ffffffu);
        if (pg.select) pg_mark(canvas, r, PS_CELL_X + (SG_SEL_COL - 6 - SG_MARK) / 2, y + (PS_CELL_H - SG_MARK) / 2);
        if (played[i]) { /* the date line's badges: a check when played, the disc when the file is on the card */
            pg_glyph(canvas, PA_CHECK, x - 1, y + PS_DATE_Y + PS_DATE_H / 2 - PA_G_PX / 2);
            x += PS_BADGE_CHECK_W;
        }
        if (e->state == PC_LOCAL) {
            pg_sprite(canvas, PA_BADGE_X, PA_DOTS_Y, PA_BADGE_PX, PA_BADGE_PX, x,
                      y + PS_DATE_Y + PS_DATE_H / 2 - PA_BADGE_PX / 2);
            x += PS_BADGE_DISC_W;
        }
        datex[i] = x;
        pg_pill_paint(canvas, PS_CELL_X + sx, y + PS_PILL_Y, &pill[i]);
        if (!pg.select)
            pg_sprite(canvas, 0, PA_DOTS_Y, PA_DOTS_PX, PA_DOTS_PX, PS_DOTS_CX - PA_DOTS_PX / 2,
                      y + PS_PILL_Y + PS_PILL_H / 2 - PA_DOTS_PX / 2);
    }
    if (off < hy) { /* the header's texts */
        pg_style(canvas, ST_NAME);
        for (k = 0; k < h->nn; ++k)
            pg_text(canvas, h->name + h->nl[k].start, h->nl[k].len, PS_NAME_X, h->y_name + k * PS_NAME_PITCH - off,
                    PS_NAME_W, PS_NAME_PITCH);
        if (h->has_latest) {
            int x0 = (PG_W - lp.w) / 2, px = x0 + PS_LATEST_PADL + PS_LATEST_GLYPH + PS_LATEST_GAPG;
            pg_style(canvas, lp.kind == PK_PLAY ? ST_LATEST : ST_LATESTW);
            pg_text(canvas, lp.label, lp.nlabel, px, h->y_latest - off, x0 + lp.w - px, PS_LATEST_H);
        }
        pg_style(canvas, ST_SEC);
        for (k = 0; k < h->nd; ++k)
            pg_text(canvas, h->desc + h->dl[k].start, h->dl[k].len, PS_DESC_X, h->y_desc + k * PS_DESC_PITCH - off,
                    PS_DESC_W, PS_DESC_PITCH);
        pg_style(canvas, ST_META);
        if (h->nm)
            pg_text(canvas, h->meta + h->ml[0].start, h->ml[0].len, PS_DESC_X, h->y_meta - off, PS_DESC_W,
                    PS_META_PITCH);
        pg_style(canvas, ST_HEAD);
        {
            unsigned head[40];
            int n = pg_wide(head, 40, TR("Episodes"));
            pg_text(canvas, head, n, PS_DESC_X, h->y_head - off, PS_DESC_W, PS_HEAD_H - 6);
        }
    }
    for (k = 0; k < 5; ++k) { /* the cells' texts, one style at a time */
        pg_style(canvas, k == 0 ? ST_DATE : k == 1 ? ST_CTITLE : k == 2 ? ST_CDIM : k == 3 ? ST_CDESC : ST_PILL);
        for (r = r0; r <= r1; ++r) {
            pg_cell_t *c = pg_cell(r);
            int y = hy + r * PS_CELL_H - off, i = r - r0, j;
            if (!c) continue;
            if (k == 0)
                pg_text(canvas, c->date, c->datelen, datex[i], y + PS_DATE_Y, PS_CELL_X + PS_CELL_W - datex[i],
                        PS_DATE_H);
            else if (k == 1 + played[i])
                for (j = 0; j < c->tn; ++j)
                    pg_text(canvas, c->title + c->tl[j].start, c->tl[j].len, PS_CELL_X + sx,
                            y + PS_TITLE_Y + j * PS_TITLE_PITCH, PS_CELL_W - sx, PS_TITLE_PITCH);
            else if (k == 3)
                for (j = 0; j < c->dn; ++j)
                    pg_text(canvas, c->desc + c->dl[j].start, c->dl[j].len, PS_CELL_X + sx,
                            y + PS_CDESC_Y + j * PS_CDESC_PITCH, PS_CELL_W - sx, PS_CDESC_PITCH);
            else if (k == 4)
                pg_text(canvas, pill[i].label, pill[i].nlabel, PS_CELL_X + sx + PS_PILL_PADL + PA_G_PX + PS_PILL_GAP,
                        y + PS_PILL_Y, pill[i].w - PS_PILL_PADL - PA_G_PX - PS_PILL_GAP, PS_PILL_H);
        }
    }
    if (off > 0) pg_paint_fade(canvas);
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

/* ---------------------------------------------------------------------------
 * The Show page's tint: the album page's (docs/modules/album-page.md "Cover tint", "Status bar"; patch/albuminfo.c) on this window, with the same functions and assets: the window's bg_color is the
 * tone (pod_tone) of the cover's average colour under the black gradient image ah_tint (the window's first child, img_ah_tint, shown only now), so the list over it is transparent; the status bar takes
 * the window's row 0 (pod_bar_tint, pod_bar_black: the one owner of the bar) while the page is in front and tinted; the tone cache (pod_tone_get / pod_tone_put, shared with the album page and Now
 * Playing) remembers it per show. A show without a cover picture stays black. The state is the page's: it is cleared when another level shows, when the page is behind another and when it is destroyed.
 */
static void pg_win_color(unsigned color) {
    unsigned v[4]; /* value_t: type at 0, the uint32 at 8 */
    memset(v, 0, sizeof v);
    value_set_uint32(v, color);
    widget_set_style(pg.win, "normal:bg_color", v);
}

static void pg_bar_apply(void) {
    if (pg.tint_on && pg.fg && pg.level == L_EPS &&
        pod_bar_tint(pg.win, pod_shade(pg.tint, 0, AH_TINT_A_TOP, AH_TINT_A_BOT, AH_TINT_ROWS)))
        pg.bar_ours = 1; /* a failed call keeps what the bar has (and owes) */
}

__attribute__((noinline)) static void pg_bar_black(void) {
    if (!pg.bar_ours) return;
    pg.bar_ours = 0;
    pod_bar_black(pg.win);
}

static void pg_tint_set(unsigned tone) {
    pg.tint = tone & 0xffffff;
    pg.tint_on = 1;
    pg_win_color(tone);
    if (pg.tint_img) widget_set_visible(pg.tint_img, 1, 0); /* (decorative: it stays insensitive) */
    widget_invalidate_force(pg.win, (void *)0);
    pg_bar_apply();
}

static void pg_tint_clear(void) {
    pg_bar_black();
    pg.tint_key = 0;
    if (!pg.tint_on) return;
    pg.tint = 0, pg.tint_on = 0;
    pg_win_color(0xff000000u);
    if (pg.tint_img) widget_set_visible(pg.tint_img, 0, 0);
    widget_invalidate_force(pg.win, (void *)0);
}

/* The show's tone from the tone cache at once (the show was open before in this session), else from the cover once the header's picture is loaded (pg_tint_cover). */
static void pg_tint_open(void) {
    unsigned tone;
    pg.tint_key = cc_key_of("Podcasts", pg.shows[pg.sel].dir);
    if (pod_tone_get(pg.tint_key, &tone)) pg_tint_set(tone);
}

/* The tint from the header's cover, once it is a real picture (the placeholder disc and a refused picture leave the page black): cc_decode box-averages the centred square to one pixel, as the
 * album page's poll does, pod_tone makes the tone of it. */
static void pg_tint_cover(void) {
    char url[PC_FILE * 2 + 60];
    unsigned px, tone;
    if (pg.tint_on || pg.level != L_EPS || !pg.hg.tiles || pg.hg.tiles[0].art != 1) return;
    if (pg_cover_url(&pg.shows[pg.sel], url, sizeof url) && cc_decode(pg.win, url, 1, 1, 1, &px)) {
        tone = pod_tone(px & 255, px >> 8 & 255, px >> 16 & 255);
        pod_tone_put(pg.tint_key, tone);
        pg_tint_set(tone);
    }
}

/* The navbar's title: always on the other levels, on the Show level only once the header's name has scrolled away (or in select mode, which has its own: "N Selected"). */
static void pg_title_show(void) {
    if (pg.title) widget_set_visible(pg.title, pg.level != L_EPS || pg.collapsed || pg.select, 0);
}

static void pg_collapse(void) {
    int c = pg.level == L_EPS && pg.hdr && pg_off() >= pg.hdr->collapse;
    if (c != pg.collapsed) {
        pg.collapsed = c;
        pg_title_show();
    }
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

/* Whether a cover is still to be loaded (the page's tick starts the loader again when the screen is back: nothing is decoded in the dark). */
static int pg_load_pending(void) {
    if (pg.level != L_EPS) return pg_next_cover() >= 0;
    return pg.hg.tiles && !pg.hg.tiles[0].art;
}

static int pg_on_load(const void *unused) {
    (void)unused;
    pg.load_timer = 0;
    if (!pg.win || !pg.fg || !pg.g.tiles || !pod_screen_lit()) return RET_OK;
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
        pg_tint_cover();
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
    widget_move(pg.status, 20, 180);
    pg_show(pg.view, 0);
    pg_show(pg.status, 1);
    widget_set_tr_text(pg.status, key);
}

/* A Show level with no episode: its header stays (the sheet holds Refresh Feed and Unsubscribe), the hint sits under it. */
static void pg_eps_hint(const char *key) {
    pg_show(pg.view, 1);
    pg_show(pg.status, 1);
    widget_set_tr_text(pg.status, key);
    widget_move(pg.status, 20, PG_LIST_Y + pg_top() + 8);
}

static void pg_fade(void) {
    if (!pg.fade) return;
    widget_set_visible(pg.fade, pg_off() > 0 && pg.level != L_EPS,
                       0); /* (the Show level paints its own, in the page's colour) */
    widget_set_sensitive(pg.fade, 0);
}

static int pg_on_scroll(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (!pg.win) return RET_OK;
    pg_collapse();
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
static void pg_sheet_close(void);

/* Leaving the Show level (every other level's loader): its sheet, its tint and its small title go. */
static void pg_leave_show(void) {
    pg_sheet_close();
    pg_tint_clear();
    pg.collapsed = 0;
}

/* The navbar's right end. Shows level: the Feeds button, the capsule's left cap. Show level: the "..." (the sheet's button, the same cap). Downloads level: the Select button (the same cap) when a row
 * can be marked. Elsewhere all are hidden (and out of the hit test) and Now Playing is the glass disc; with a cap beside it Now Playing is the capsule's right cap. The title: see pg_title_show. */
static void pg_nav(void) {
    int shows = pg.level == L_SHOWS, more = pg.level == L_EPS && !pg.select && pg.btn_more,
        sel = !pg.select && pg.level == L_DLS && pg.btn_select && pg.mark[0] && pg_sel_scan(0) > 0,
        cap = shows || sel || more;
    const char *img = cap ? "ah_nav_play" : "ah_nav_np";
    pg_show(pg.btn_feeds, shows);
    pg_show(pg.btn_select, sel);
    pg_show(pg.btn_more, more);
    pg_title_show();
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
    pg_leave_show();
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
    pg_leave_show();
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
    pg_leave_show();
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

/* The episodes of show si (an index into shows): every one the show knows, on the card or not, newest first. The Show page lists them all: a cell's pill says which can be played and which downloaded. */
static pc_ep_t *pg_eps_of(int si, int *count) {
    pc_ep_t *all = calloc(PC_MAX_EPS, sizeof *all);
    if (!all) return all;
    *count = pc_load_show(&pg.shows[si], all, PC_MAX_EPS);
    return all;
}

static const char *pg_no_eps_key(void) {
    return pg.from_feeds ? "No episodes yet. Refresh the feed in Feeds." : "No downloaded episodes";
}

/* The Show level of show si (docs/modules/podcasts.md "The Show page"). from_feeds: Back goes to Feeds, else to Shows. off: the scroll position to keep (a show opened again after a refresh), 0 the top. */
static void pg_open_show(int si, int from_feeds, int off) {
    int m = 0;
    pc_ep_t *all = pg_eps_of(si, &m);
    if (!all) {
        pod_toast(TR("Not enough memory"));
        return;
    }
    pg.gen = pn_gen(), pg.dgen = pn_dl_gen();
    if (pg.level == L_FEEDS)
        pg.feeds_off = pg_off();
    else if (pg.level == L_SHOWS)
        pg.show_off = pg_off();
    pg_sheet_close();
    pg_tint_clear();
    pg_drop_tiles();
    free(pg.eps);
    pg.eps = all, pg.neps = m, pg.sel = si, pg.level = L_EPS, pg.from_feeds = from_feeds;
    pg.feed_hash = pg.shows[si].feed[0] ? pc_hash(pg.shows[si].feed) : 0;
    pg.rev = pc_rev();
    pg.collapsed = 0;
    pg_cells_drop();
    pg_hdr_make();
    pg_title((const char *)0, pg.shows[si].title);
    pg_nav();
    pg_show(pg.view, 1);
    pg_show(pg.status, 0);
    if (!m) pg_eps_hint(pg_no_eps_key());
    grid_shape(&pg.g, LIST_ART, LIST_R, 1);
    grid_shape(&pg.hg, PS_ART, PS_ART_R,
               1); /* (the corners are cut in the alpha: the page's tint shows through them) */
    grid_placeholder(&pg.hg);
    pg_size();
    widget_set_prop_int(pg.sv, "yoffset", off > 0 ? off : 0);
    pg_tint_open();
    pg_collapse();
    pg_fade();
    pg_redraw();
    pg_kick();
}

/* The Show level's episodes read again (a download finished, failed or was started, a file was removed: the list changed): the scroll position stays, the layouts are made again. */
static void pg_reload_eps(void) {
    int m = 0, max;
    pc_ep_t *all = pg_eps_of(pg.sel, &m);
    pg.gen = pn_gen(), pg.dgen = pn_dl_gen();
    if (!all) return;
    free(pg.eps);
    pg.eps = all, pg.neps = m;
    pg.press = pg.down = 0;
    pg_cells_drop();
    pg_hdr_make();
    if (!m)
        pg_eps_hint(pg_no_eps_key());
    else
        pg_show(pg.status, 0);
    pg_size();
    max = pg_content() - GRID_VIEW_H;
    if (max < 0) max = 0;
    if (pg_off() > max) widget_set_prop_int(pg.sv, "yoffset", max);
    pg_collapse();
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
    pg_show(pg.btn_more, 0);
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
    pg_title_show();
    grid_drop(&pg.g); /* the texts are made again at the other width */
    pg_cells_drop();
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
    if (pg.win && !pg.select && pg.level == L_DLS) pg_select(1); /* (the Show level's is in its sheet) */
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
    if (pg.sheet)
        pg_sheet_close();
    else if (pg.select)
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

/* The Show level after a refresh of its show: the folders are read again (the first refresh names an imported show and may rename its folder, a cover may have come) and the show is found by its feed
 * address; the page is made again at the same place. A show that is gone (it cannot be) leaves for the level below. */
static void pg_after_refresh(void) {
    int i, si = -1, off = pg_off();
    pg_scan();
    for (i = 0; pg.feed_hash && i < pg.nshows; ++i)
        if (pg.shows[i].feed[0] && pc_hash(pg.shows[i].feed) == pg.feed_hash) si = i;
    if (si >= 0)
        pg_open_show(si, pg.from_feeds, off);
    else if (pg.from_feeds)
        pg_load_feeds();
    else
        pg_load_shows();
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
    else if (pg.level == L_EPS)
        pg_after_refresh();
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

/* Refresh the feeds in rows [first, count) that are subscriptions (every one: Refresh All; the new ones after an import: those never refreshed), or the show open (one: the Show level's Refresh Feed). */
static void pg_refresh_job(int only_new, int one) {
    int idx[PC_MAX_SHOWS], n = 0, i, r;
    if (pn_dl_running()) { /* downloads pause for a refresh (the queue stays, they go on when it ends): the refresh starts from the page's tick once the thread has stopped */
        pn_dl_pause();
        pg.rpend = only_new + 1;
        pg.rone = one;
        pg_awake_arm();
        pg_feed_retext();
        pg_redraw();
        return;
    }
    if (one)
        idx[n++] = pg.sel;
    else
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

static void pg_refresh(int only_new) { pg_refresh_job(only_new, 0); }

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
        pg_open_show(row, 1, 0);
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
/* What a touch hit: the row (Shows, Feeds, Downloads) or the cell (Show) under it, -1 for none, and on the Show level which part of it (PH_*): the "..." (a PS_DOTS_HIT square), the state pill (its
 * width and 7 px more above and below, for a 44 px target), the body. The Latest Episode pill is cell 0's part PH_LATEST (above the cells). Select mode has the bodies only. */
static int pg_hit(void *e, int *part) {
    int pt[2], y;
    pt[0] = I(e, PE_X), pt[1] = I(e, PE_Y);
    widget_to_local(pg.view, pt);
    *part = PH_BODY;
    if (pg.level == L_EPS) {
        const pg_hdr_t *h = pg.hdr;
        int row, cy, mid = PS_PILL_Y + PS_PILL_H / 2;
        if (!h) return -1;
        if (pt[1] < h->h) {
            if (!pg.select && h->has_latest && pt[1] >= h->y_latest - 2 && pt[1] < h->y_latest + PS_LATEST_H + 2) {
                pg_pill_t lp;
                pg_latest_of(&pg.eps[0], &lp);
                if (pt[0] >= (PG_W - lp.w) / 2 && pt[0] < (PG_W + lp.w) / 2) {
                    *part = PH_LATEST;
                    return 0;
                }
            }
            return -1;
        }
        row = (pt[1] - h->h) / PS_CELL_H;
        if (row >= pg.neps) return -1;
        cy = (pt[1] - h->h) % PS_CELL_H;
        if (!pg.select) {
            if (pt[0] >= PS_DOTS_CX - PS_DOTS_HIT / 2 && pt[0] < PS_DOTS_CX + PS_DOTS_HIT / 2 &&
                cy >= mid - PS_DOTS_HIT / 2 && cy < mid + PS_DOTS_HIT / 2)
                *part = PH_DOTS;
            else if (cy >= PS_PILL_Y - 7 && cy < PS_PILL_Y + PS_PILL_H + 7) {
                pg_pill_t pl;
                pg_pill_of(&pg.eps[row], &pl);
                if (pt[0] >= PS_CELL_X - 4 && pt[0] < PS_CELL_X + pl.w + 4) *part = PH_PILL;
            }
        }
        return row;
    }
    y = pt[1] - pg_top();
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
    int a, part;
    (void)ctx;
    pg.down = 0;
    if (!e || !pg.view) return RET_OK;
    a = pg_hit(e, &part);
    pg.down = a + 1; /* (-1: nothing) */
    pg.down_part = part;
    pg.down_x = I(e, PE_X), pg.down_y = I(e, PE_Y);
    if (a >= 0 && !pg.select && (pg.level != L_EPS || (part == PH_BODY && pg.eps[a].state == PC_LOCAL)))
        pg_set_press(a + 1);
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

static const char *const pg_speed_name[PC_SPEEDS] = {"1\xc3\x97", "1.25\xc3\x97", "1.5\xc3\x97",
                                                     "2\xc3\x97"}; /* "1x" with the multiplication sign U+00D7 */

/* ---------------------------------------------------------------------------
 * The Show page's bottom sheets (docs/modules/podcasts.md "The Show page"; the look is Now Playing's More sheet): one widget set of the asset (tools/pod_ui.py podcasts_sheet), nine fixed rows of
 * which each sheet shows the ones that apply, placed from the card's top, the card as high as its rows over the window's bottom edge. The show's "..." opens the show's: Playback Speed (a tap cycles
 * and the sheet stays), Refresh Feed, Select Episodes, Mark All as Played, Unsubscribe. A cell's "..." opens that episode's: Download or Remove Download, Mark as Played or Unplayed.
 */
static const char *const pg_row_id[PG_SHEET_ROWS] = {"speed", "refresh", "select", "markall", "unsub",
                                                     "dl",    "rm",      "mark",   "unmark"};

static void pg_sheet_close(void) {
    if (!pg.sheet) return;
    pg.sheet = SH_NONE;
    pg_show(pg.sh_scrim, 0);
    pg_show(pg.sh_card, 0);
}

/* The grey value of row i (a value label v: 0 speed, 1 refresh), right aligned to x PS_SHEET_VALUE_R, in the room the row's label leaves (the label keeps its whole text): text, else alt (a shorter
 * one) when text is wider than the room, else text cut with an ellipsis by the label. The value label is as wide as its text and the row's label ends PS_SHEET_GAP before it. */
static void pg_sheet_value(int i, int v, const char *text, const char *alt) {
    const unsigned *w;
    int lw = 0, vw = 0, room;
    if (!pg.sh_vl[v]) return;
    w = widget_get_text(pg.sh_tx[i]);
    if (w && *w) lw = pg_width(pg.sh_tx[i], w);
    room = PS_SHEET_VALUE_R - PS_SHEET_TEXT_X - lw - PS_SHEET_GAP;
    widget_set_text_utf8(pg.sh_vl[v], text);
    w = widget_get_text(pg.sh_vl[v]);
    if (w && *w) vw = pg_width(pg.sh_vl[v], w);
    if (alt && vw > room) {
        widget_set_text_utf8(pg.sh_vl[v], alt);
        w = widget_get_text(pg.sh_vl[v]);
        vw = w && *w ? pg_width(pg.sh_vl[v], w) : 0;
    }
    if (vw > room) vw = room > 0 ? room : 0;
    widget_move(pg.sh_vl[v], PS_SHEET_VALUE_R - vw, 0);
    widget_resize(pg.sh_vl[v], vw, PM_ROW_H);
    widget_resize(pg.sh_tx[i], PS_SHEET_VALUE_R - PS_SHEET_TEXT_X - vw - (vw ? PS_SHEET_GAP : 0), PM_ROW_H);
}

/* Show the rows (ids, in order) and the card that holds them: PM_ROW_H each from the card's top, the first without its hairline, the glass picture of that height. */
static void pg_sheet_rows(const int *rows, int n) {
    static const char *const glass[PM_PAGE_N + 1] = {"",          "pc_sheet1", "pc_sheet2",
                                                     "pc_sheet3", "pc_sheet4", "pc_sheet5"};
    int i, k, h = n * PM_ROW_H;
    for (i = 0; i < PG_SHEET_ROWS; ++i) {
        int at = -1;
        for (k = 0; k < n; ++k)
            if (rows[k] == i) at = k;
        if (at < 0) {
            pg_show(pg.sh_row[i], 0);
            continue;
        }
        widget_move(pg.sh_row[i], 0, at * PM_ROW_H);
        pg_show(pg.sh_row[i], 1);
        widget_set_visible(pg.sh_hr[i], at > 0, 0);
    }
    widget_move(pg.sh_card, 0, AH_WIN_H - h);
    widget_resize(pg.sh_card, PG_W, h);
    widget_set_prop_str(pg.sh_card, "style:normal:bg_image", glass[n]);
    pg_show(pg.sh_scrim, 1);
    pg_show(pg.sh_card, 1);
}

static int pg_any_unplayed(void) {
    unsigned pos, len;
    int i;
    for (i = 0; i < pg.neps; ++i)
        if (pg_ep_hash(&pg.eps[i]) && pg_ep_state(&pg.eps[i], &pos, &len) != PC_DONE) return 1;
    return 0;
}

/* The sheet of the show (SH_SHOW) or of episode ep (SH_CELL). */
static void pg_sheet_open(int kind, int ep) {
    int rows[PG_SHEET_ROWS], n = 0;
    unsigned pos, len;
    char text[96];
    if (!pg.sh_card || pg.sheet || pg.level != L_EPS || pg.dlg || pg.select) return;
    pg.sheet = kind, pg.sh_ep = ep;
    if (kind == SH_SHOW) {
        const pc_show_t *s = &pg.shows[pg.sel];
        rows[n++] = SR_SPEED;
        pg_sheet_value(SR_SPEED, 0, pg_speed_name[pc_speed_get(s->hash)], (const char *)0);
        if (s->feed[0]) {
            char when[48];
            rows[n++] = SR_REFRESH;
            text[0] = when[0] = 0;
            if (s->checked) { /* "Updated 1h ago", or just "1h ago" where the language needs the room */
                pc_when(s->checked, (unsigned)time((long *)0), when, sizeof when);
                snprintf(text, sizeof text, TR("Updated %s"), when);
            } else
                pg_cat(text, sizeof text, TR("Never refreshed"));
            pg_sheet_value(SR_REFRESH, 1, text, when[0] ? when : (const char *)0);
        }
        if (pg_sel_scan(0) > 0) rows[n++] = SR_SELECT;
        if (pg_any_unplayed()) rows[n++] = SR_MARKALL;
        if (s->feed[0]) rows[n++] = SR_UNSUB;
    } else {
        const pc_ep_t *e = &pg.eps[ep];
        if (e->state == PC_REMOTE) {
            rows[n++] = SR_DL;
            text[0] = 0;
            pg_cat(text, sizeof text, TR("Download"));
            if (e->length) { /* "Download - 48 MB" */
                char size[24];
                pg_cat(text, sizeof text, " \xc2\xb7 ");
                pc_fmt(size, sizeof size, TR("%d MB"), (e->length + 1048575) >> 20);
                pg_cat(text, sizeof text, size);
            }
            widget_set_text_utf8(pg.sh_tx[SR_DL], text);
        } else
            rows[n++] = SR_RM;
        if (pg_ep_hash(e)) rows[n++] = pg_ep_state(e, &pos, &len) == PC_DONE ? SR_UNMARK : SR_MARK;
    }
    pg_sheet_rows(rows, n);
}

static void pg_speed_cycle(void) {
    const pc_show_t *s = &pg.shows[pg.sel];
    int mode = (pc_speed_get(s->hash) + 1) % PC_SPEEDS;
    if (!pc_speed_set(s->hash, mode)) pod_toast(TR("Storage unavailable"));
    mode = pc_speed_get(s->hash);
    pg_sheet_value(SR_SPEED, 0, pg_speed_name[mode], (const char *)0);
    pc_speed_apply(
        s->hash); /* an episode of this show that plays: the decoder takes it at the next start; the stock page shows it */
    pg_redraw();
}

/* A tap on an episode's download pill, a Latest Episode pill that is not on the card, or the sheet's Download: a queued or running download is cancelled, anything else is queued (pg_dl_toggle). */
static void pg_dl_tap(int a) {
    pg_dl_toggle(pg.shows[pg.sel].dir, pg.eps[a].file);
    pg_redraw();
}

/* Remove Download (an episode's sheet): its file and its .part go, a download of it is taken out of the queue; the .episodes line stays, so the cell is a download cell again; its resume place and
 * played mark are forgotten, as the select mode's Delete does. The playing episode is never removed. */
static void pg_remove(int ep) {
    const pc_ep_t *e;
    char path[PC_FILE * 3 + 24];
    unsigned key, hash;
    if (ep < 0 || ep >= pg.neps) return;
    e = &pg.eps[ep];
    if (!e->file[0] || !pg_join(path, sizeof path - 6, pg.shows[pg.sel].dir, e->file)) return;
    if (e->state == PC_LOCAL && pg_playing(path)) {
        pod_toast(TR("The playing episode was kept"));
        return;
    }
    key = pn_dl_key(pg.shows[pg.sel].dir, e->file);
    hash = e->state == PC_LOCAL ? e->hash : 0;
    pn_dl_cancel(key);
    unlink(path);
    pg_cat(path, sizeof path, ".part");
    unlink(path);
    pn_dl_clear(key);
    if (hash) pc_mark(hash, 0);
    pc_flush();
    pg_reload_eps();
}

/* Mark All as Played: every episode the show knows that has a file name (one not on the card too: the mark belongs to the path, which a later download takes). */
static void pg_mark_all(void) {
    unsigned pos, len, hash;
    int i;
    for (i = 0; i < pg.neps; ++i) {
        hash = pg_ep_hash(&pg.eps[i]);
        if (hash && pg_ep_state(&pg.eps[i], &pos, &len) != PC_DONE) pc_mark(hash, 1);
    }
    pc_flush();
    pg_redraw();
}

/* Unsubscribe (after a confirm): the show is no longer a subscription (its .show loses feed=, so it is not refreshed and is not in Feeds), the .episodes stay (the titles and dates of the files left on the
 * card), the .part files and the queued downloads of the show go; with no episode file left the show's own files (.show, .episodes, cover.jpg) and the folder (when nothing else is in it) go too and the
 * page returns to the level below; else it stays, reading the show again. The playing episode is a file that stays. */
static void pg_unsub(void) {
    const pc_show_t *s = &pg.shows[pg.sel];
    char dir[PC_FILE], path[PC_FILE * 3 + 24];
    int i, left = 0, off = pg_off(), from_feeds = pg.from_feeds;
    static const char *const own[] = {".show", ".episodes", "cover.jpg"};
    if (!s->feed[0] || pn_busy() || !pod_confirm(TR("Unsubscribe from this show?"))) return;
    memcpy(dir, s->dir, sizeof dir);
    if (!pn_unsubscribe(pg.root, s)) { /* (first: a .show that cannot be written changes nothing else) */
        pod_toast(TR("Storage unavailable"));
        return;
    }
    for (i = 0; i < pg.neps; ++i) {
        const pc_ep_t *e = &pg.eps[i];
        unsigned key;
        if (!e->file[0]) continue;
        key = pn_dl_key(dir, e->file);
        pn_dl_cancel(key);
        if (pg_join(path, sizeof path - 6, dir, e->file)) {
            pg_cat(path, sizeof path, ".part");
            unlink(path);
        }
        pn_dl_clear(key);
        left += e->state == PC_LOCAL;
    }
    if (!left) {
        for (i = 0; i < (int)(sizeof own / sizeof *own); ++i)
            if (pg_join(path, sizeof path, dir, own[i])) unlink(path);
        if (pg_join(path, sizeof path, dir, "")) {
            unsigned n = 0;
            while (path[n]) ++n;
            if (n && path[n - 1] == '/') path[n - 1] = 0;
            rmdir(path);
        }
    }
    pg_scan();
    for (i = 0; left && i < pg.nshows; ++i)
        if (!strcmp(pg.shows[i].dir, dir)) {
            pg_open_show(i, 0, off); /* (it is no subscription now: Back goes to Shows) */
            return;
        }
    if (from_feeds)
        pg_load_feeds();
    else
        pg_load_shows();
}

static int pg_on_sheet_scrim(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    pg_sheet_close();
    return RET_OK;
}

static int pg_on_sheet_row(void *ctx, void *e) {
    int id = (int)(unsigned)ctx - 1, ep = pg.sh_ep;
    unsigned hash;
    (void)e;
    if (!pg.win || !pg.sheet || id < 0 || id >= PG_SHEET_ROWS) return RET_OK;
    if (id == SR_SPEED) { /* a tap cycles; the sheet stays */
        pg_speed_cycle();
        return RET_OK;
    }
    pg_sheet_close();
    switch (id) {
    case SR_REFRESH:
        if (pg.shows[pg.sel].feed[0]) pg_refresh_job(0, 1);
        break;
    case SR_SELECT:
        pg_select(1);
        break;
    case SR_MARKALL:
        pg_mark_all();
        break;
    case SR_UNSUB:
        pg_unsub();
        break;
    case SR_DL:
        if (ep >= 0 && ep < pg.neps) pg_dl_tap(ep);
        break;
    case SR_RM:
        pg_remove(ep);
        break;
    default: /* Mark as Played / Unplayed */
        hash = ep >= 0 && ep < pg.neps ? pg_ep_hash(&pg.eps[ep]) : 0;
        if (hash) {
            pc_mark(hash, id == SR_MARK);
            pc_flush();
            pg_redraw();
        }
    }
    return RET_OK;
}

static int pg_on_more(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (pg.win && pg.level == L_EPS && !pg.select) pg_sheet_open(SH_SHOW, 0);
    return RET_OK;
}

/* A tap on a part of cell a of the Show level (select mode taps are the marks'): the Latest Episode pill, the "...", the state pill (play it, or what its state says: download, pause, resume, retry), the
 * body (play it when it is on the card; a cell that is not does nothing: only the pill and the "..." download). */
static void pg_cell_tap(int a, int part) {
    const pc_ep_t *e = &pg.eps[part == PH_LATEST ? 0 : a];
    if (part == PH_DOTS)
        pg_sheet_open(SH_CELL, a);
    else if (part == PH_BODY && e->state != PC_LOCAL)
        return;
    else if (e->state == PC_LOCAL)
        pg_play(part == PH_LATEST ? 0 : a);
    else
        pg_dl_tap(part == PH_LATEST ? 0 : a);
}

static int pg_on_up(void *ctx, void *e) {
    int a = pg.down, part = pg.down_part, same, part2;
    (void)ctx;
    pg.down = 0;
    pg_set_press(0);
    if (!a || !e || !pg.view) return RET_OK;
    if (pg_abs(I(e, PE_X) - pg.down_x) >= PG_TAP_PX || pg_abs(I(e, PE_Y) - pg.down_y) >= PG_TAP_PX) return RET_OK;
    same = pg_hit(e, &part2);
    if (pg.select) {
        if (a > 0 && same == a - 1) pg_toggle_pick(same); /* a tap marks and unmarks; a drag marks nothing */
    } else if (same == a - 1 && part2 == part) {
        if (pg.level == L_DLS)
            pg_dls_tap(same);
        else if (pg.level == L_SHOWS)
            pg_open_show(pg.rows[same], 0, 0);
        else if (pg.level == L_FEEDS)
            pg_feeds_tap(same);
        else
            pg_cell_tap(same, part);
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
    if (pod_screen_lit() && !pg.load_timer && pg_load_pending())
        pg_kick(); /* the screen is back on: the covers go on (the loader does nothing in the dark) */
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
    if (pod_screen_lit() && pg.level == L_EPS &&
        !pg.dlg) { /* (not under the refresh dialog: it reads the show again when it closes) */
        if (pn_gen() != pg.gen && !pg.select)
            pg_reload_eps(); /* (not while rows are marked: the marks are of these rows) a download started, finished or failed: the episodes are read again (a finished one is a file now) */
        else if (pn_dl_gen() !=
                 pg.dgen) { /* a step of progress: the pills are painted again (their states are read at every paint) */
            pg.dgen = pn_dl_gen();
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
        pc_rev() != pg.rev) { /* a place or a mark changed: the pills and the badges are painted again */
        pg.rev = pc_rev();
        pg_redraw();
    }
    if (pg.rpend && (pg.level == L_FEEDS || (pg.level == L_EPS && pg.rone)) && pod_screen_lit() && !pn_dl_running() &&
        !pn_busy()) {
        int only_new = pg.rpend - 1,
            one = pg.rone; /* the downloads have paused: the refresh the user asked for starts */
        pg.rpend = pg.rone = 0;
        pg_refresh_job(only_new, one);
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
    if (pg.rpend && !pn_dl_running() && !pn_busy() &&
        (!(pg.level == L_FEEDS || (pg.level == L_EPS && pg.rone)) || !pg.fg || !pod_screen_lit()))
        pg.rpend = pg.rone = 0; /* the page is not there to open the refresh's dialog: the downloads go on */
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
    if (pg.level ==
        L_EPS) { /* the layouts (the dates) are made again: "4h ago" is a time later; the status bar is the page's again */
        pg.rev = pc_rev();
        pg_cells_drop();
        pg_bar_apply();
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
    pg_bar_black(); /* the status bar is black again while another page is in front (it tints it itself) */
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
    pg_bar_black();
    pc_flush();
    grid_free(&pg.g);
    grid_free(&pg.hg);
    if (pg.atlas) bitmap_destroy(pg.atlas);
    free(pg.cells);
    free(pg.hdr);
    if (pg.mark[0]) bitmap_destroy(pg.mark[0]);
    if (pg.mark[1]) bitmap_destroy(pg.mark[1]);
    free(pg.shows);
    free(pg.eps);
    free(pg.dls);
    memset(&pg, 0, sizeof pg);
    return RET_OK;
}

/* The sheets' widgets (the asset's, tools/pod_ui.py podcasts_sheet); one missing leaves the page without sheets (pg.sh_card is the switch). */
static void pg_sheet_bind(void) {
    char name[40];
    int i, ok = 1;
    pg.sh_scrim = pod_bind(pg.win, "pg_sh_scrim", pg_on_sheet_scrim, (void *)0);
    pg.sh_card = widget_lookup(pg.win, "pg_sh_card", 1);
    for (i = 0; i < PG_SHEET_ROWS; ++i) {
        snprintf(name, sizeof name, "pg_sh_%s", pg_row_id[i]);
        pg.sh_row[i] = pod_bind(pg.win, name, pg_on_sheet_row, (const void *)(unsigned)(i + 1));
        snprintf(name, sizeof name, "pg_sh_%s_tx", pg_row_id[i]);
        pg.sh_tx[i] = widget_lookup(pg.win, name, 1);
        snprintf(name, sizeof name, "pg_sh_%s_hr", pg_row_id[i]);
        pg.sh_hr[i] = widget_lookup(pg.win, name, 1);
        ok &= pg.sh_row[i] && pg.sh_tx[i] && pg.sh_hr[i];
    }
    pg.sh_vl[0] = widget_lookup(pg.win, "pg_sh_speed_vl", 1);
    pg.sh_vl[1] = widget_lookup(pg.win, "pg_sh_refresh_vl", 1);
    if (!ok || !pg.sh_scrim || !pg.sh_card || !pg.sh_vl[0] || !pg.sh_vl[1]) pg.sh_card = (void *)0;
}

/* The Extras item Podcasts. 0 once the page is up, -1 if it could not open. */
int podcasts_open(void) {
    static const char *const st_name[ST_N] = {"label_ps_name", "label_ps_sec",    "label_ps_meta",   "label_ps_head",
                                              "label_ps_date", "label_ps_ctitle", "label_ps_cdim",   "label_ps_cdesc",
                                              "label_ps_pill", "label_ps_latest", "label_ps_latestw"};
    int i, ok = 1;
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
    pg.tint_img =
        widget_lookup(pg.win, "img_ah_tint",
                      1); /* the Show page's widgets: without the sheet or the tint the page works without them */
    pg.btn_more = pod_bind(pg.win, "btn_more", pg_on_more, (void *)0);
    for (i = 0; i < ST_N; ++i) {
        pg.st[i] = widget_lookup(pg.win, st_name[i], 1);
        ok &= pg.st[i] != (void *)0;
    }
    if (!pg.view || !pg.sv || !pg.status || !pg.title || !pg.st_title || !pg.st_sub || !pg.st_act || !pg.btn_feeds ||
        !pg.dlg_scrim || !pg.dlg_card || !pg.dlg_name || !pg.dlg_count || !pg.dlg_fill || !pg.dlg_cancel || !ok) {
        navigator_back(); /* an asset that is not ours */
        return -1;
    }
    pg_sheet_bind();
    label_set_line_wrap(pg.status, 1);
    pg.shows = calloc(PC_MAX_SHOWS, sizeof *pg.shows);
    pg.hdr = calloc(1, sizeof *pg.hdr);
    pg.cells = calloc(PG_CELLS, sizeof *pg.cells);
    if (!pg.shows || !pg.hdr || !pg.cells || !grid_init(&pg.g, pg.win, PC_TILES, LIST_ART, LIST_R) ||
        !grid_init(&pg.hg, pg.win, 1, PS_ART, PS_ART_R)) {
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
