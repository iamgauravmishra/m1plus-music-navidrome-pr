/* M1+ Music iPod: a virtual iPod Classic. A fullscreen page with the iPod screen on top and a touch click wheel below.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * docs/modules/ipod.md has the design. The page is ui/m1plus_ipod.bin (tools/pod_ui.py build_ipod_page): a fullscreen window (320 x 480, so the stock
 * status bar is not drawn, as the lock screen's) holding the view ipod_screen (320 x 240, insensitive; the payload paints it in its own EVT_AFTER_PAINT:
 * title bar, rows, cover pane, Now Playing screen) and the view ipod_wheel (220 x 220, the touch target; its child image is the drawn wheel, insensitive),
 * and the hidden labels that only carry the text styles. No hook, no widget per row: everything runs from the page's widgets, its window events and ONE
 * page-scoped timer (the battery, the play state and the track), exactly the precedents of Albums, Songs, the mini player bar and Cover Flow.
 *
 *   levels     a small stack (IP_DEPTH): the main menu, then Albums / Artists / Songs / Playlists, an artist's albums, an album's or a playlist's tracks, and Now
 *              Playing. A list level keeps only its row cursor (sel, top); its rows are read from the stock list (*pdeq_showlist, or *pdeq_playlist) while it
 *              is the list the stock queries last made (ip_valid: the pointer, the size and the first record, as the Songs page checks); anything else gets its
 *              query run again (ip_run: the chain of ancestors, as the stock pages do) when the page is in front, from a step, a tap or the window coming back.
 *              The rows are never read from a stale list.
 *   wheel      the touch on the ring. The finger's angle (ip_angle, integer atan) around the wheel's centre turns one step every IP_STEP (15 degrees); a touch
 *              that turns no step and travels less than IP_TAP_PX is a tap: the centre button selects, the ring's four sectors are MENU (top), previous (left),
 *              next (right) and play / pause (bottom). Outside the ring's circle a touch does nothing (the view is square). The view grabs the touch.
 *   play       a track opens the stock way: loadSongList of the shown list, start_player (what the stock Play all button calls), Now Playing level.
 *   sound      none: docs/modules/ipod.md "The click sound" has the evidence and the options.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "covercache.h"
#include "common.h"
#include "i18n.h"
#include "podcasts.h"

extern unsigned np_file_key(const char *path);       /* patch/nowplaying.c: a hash of the picture file, 0 if unreadable */
extern const char *np_cover_file(int *busy);         /* the /tmp file of the playing track's cover, NULL for none; busy while demo makes it */
extern void pod_toast(const char *text);             /* patch/shuffle.c: the stock message box */
extern int pod_open_settings(void);                  /* patch/m1plus.c: the Settings page */
extern unsigned pod_rand(unsigned n);                /* patch/shuffle.c: the shuffle generator (seeded once) */
extern void pod_set_mode(int mode);                  /* patch/shuffle.c: the stock play mode, set as the Play settings page does */
extern void pod_set_in_order(void);                  /* patch/shuffle.c: Shuffle and Repeat one become List play */
/* patch/ipod_cf.c: the Cover Flow screen (level K_CF: the albums list drawn as covers; docs/modules/ipod-coverflow.md) */
extern int ipcf_open(void *win), ipcf_up(void), ipcf_busy(void), ipcf_tick(void *list, unsigned count);
extern void ipcf_close(void), ipcf_goto(int sel), ipcf_paint(void *canvas, void *list, unsigned count, void *style);

#define I(w, off) (*(int *)((char *)(w) + (off)))
#define ART_GREY 0xff2b2b2bu

enum { K_MAIN, K_ALBUMS, K_ARTISTS, K_SONGS, K_PLAYLISTS, K_ARTIST_ALBUMS, K_TRACKS, K_PL_TRACKS, K_NOW, K_SETTINGS, K_CF };
enum { S_SHUFFLE, S_REPEAT, S_ABOUT, S_MORE, S_COUNT };   /* the Settings level's rows */
enum { M_COVER, M_ALBUMS, M_ARTISTS, M_SONGS, M_PLAYLISTS, M_SHUFFLE, M_SETTINGS, M_NOW, M_COUNT };
enum { R_NONE, R_CENTRE, R_RING };

static const char *const MAIN_KEYS[M_COUNT] = {"Cover Flow", "Albums", "Artists", "Songs", "Playlists", "Shuffle Songs", "cdrippersettings", "Now Playing"};
static const char *const SET_KEYS[S_COUNT] = {"Shuffle", "Repeat", "About", "Customize"};

struct lvl {
    int kind, sel, top;
};

static struct {
    void *win, *screen, *wheel;
    void *st_row, *st_sel, *st_title, *st_small, *st_np1, *st_np2, *st_time, *st_chev;   /* hidden labels: the text styles */
    struct lvl st[IP_DEPTH];
    int depth;                    /* index of the level in front */
    void *list;                   /* the stock list the front level's rows are read from (valid while it is still the current one) */
    void *first;
    unsigned count;
    int cls;                      /* the class of the tracks listed (stock: classinfo[0] after the query) */
    unsigned timer;
    int fg;
    /* the wheel */
    int touch;                    /* R_NONE, R_CENTRE, R_RING */
    int sx, sy, lx, ly;           /* the start and the last point, wheel coordinates relative to the centre */
    int last, acc;                /* the last angle (sixteenths of a degree) and the unspent turn */
    int turned, far;              /* a step was made / the finger travelled IP_TAP_PX or more */
    int dir, rev;                 /* the committed turn direction (+1 / -1, 0 none) and the reverse travel since (sixteenths) */
    int speed, fast;              /* smoothed angular speed (sixteenths a second); whether it has been above IP_FAST since fast_t0 */
    unsigned lt, fast_t0;         /* the time of the last move; the time the speed went above IP_FAST (event times, ms) */
    /* what the screen shows besides the lists, and the signature of it */
    void *art;                    /* the cover bitmap IP_ART x IP_ART RGBA */
    unsigned track;               /* the track the cover was made for (a hash), 0 none */
    unsigned fkey;                /* the hash of the /tmp cover file it was made from, 0 when it was not */
    int settle;
    unsigned ival;                /* the page timer's interval now (IPCF_FRAME_MS, IP_DRIFT_MS or IP_TICK_MS); timer_modify changes it */
    unsigned lookn;               /* fast ticks since the last ip_look */
    /* the main menu's cover pane: one cover panning slowly (q2-pod's Split Home) */
    struct {
        void *bmp;                /* the cover, IP_PANE_ART square RGBA, made on first use */
        int have;                 /* bmp holds `key`'s cover */
        unsigned asked, key;      /* the album key bmp was made for, and the one it shows (0 = the stock disc, still: the cover could not be read) */
        unsigned pk;              /* the playing album's key the last look saw, and whether it has a cached cover */
        int pk_art;
        unsigned rnd;             /* the random album shown while nothing with a cached cover plays (0: the disc); drawn once a visit of the main menu */
        int picked;
        unsigned ms, t0;          /* the pan's phase (time shown, ms) and the time of the last step */
        int x, y;                 /* the pan's place now (0 .. IP_PANE_R each), as painted */
    } pane;
    unsigned sig[5];            /* the last painted values of the timer's look: battery, play state, track, position, queue */
} ip __attribute__((section(".scratch")));

/* ---------------------------------------------------------------------------
 * Small helpers
 */
static unsigned ip_len(const char *s) {
    unsigned n = 0;
    while (s[n]) n++;
    return n;
}

static unsigned ip_lerp(unsigned a, unsigned b, int i, int n) {   /* the colour a .. b (r | g << 8 | b << 16) at i of n - 1 */
    unsigned c = 0, k;
    for (k = 0; k < 24; k += 8) {
        int x = (int)(a >> k & 255), y = (int)(b >> k & 255);
        c |= (unsigned)(x + (y - x) * i / (n > 1 ? n - 1 : 1)) << k;
    }
    return c;
}

static void ip_fill(void *canvas, int x, int y, int w, int h, unsigned rgb) {
    canvas_set_fill_color(canvas, 0xff000000u | rgb);
    canvas_fill_rect(canvas, x, y, w, h);
}

static void ip_vgrad(void *canvas, int x, int y, int w, int h, unsigned top, unsigned bot) {
    int i;
    for (i = 0; i < h; ++i) ip_fill(canvas, x, y + i, w, 1, ip_lerp(top, bot, i, h));
}

static void ip_redraw(void) {
    if (ip.screen) widget_invalidate_force(ip.screen, (void *)0);
}

static int ip_is_list(int kind) { return kind != K_MAIN && kind != K_NOW && kind != K_SETTINGS; }
static int ip_is_tracks(int kind) { return kind == K_SONGS || kind == K_TRACKS || kind == K_PL_TRACKS; }
static struct lvl *ip_top(void) { return &ip.st[ip.depth]; }

/* The wide string cut with an ellipsis to maxw px (the canvas has the text's style): grid.c's search. Its length. */
unsigned ip_fit(void *canvas, unsigned *s, int maxw) {
    unsigned len = 0, lo, hi;
    while (s[len]) len++;
    if (len && (int)(canvas_measure_text(canvas, s, len) + 0.999f) > maxw) {
        lo = 0, hi = len - 1;
        while (lo < hi) {
            unsigned mid = (lo + hi + 1) / 2, keep = s[mid];
            s[mid] = ELLIPSIS;
            if ((int)(canvas_measure_text(canvas, s, mid + 1) + 0.999f) <= maxw) lo = mid;
            else hi = mid - 1;
            s[mid] = keep;
        }
        s[lo] = ELLIPSIS;
        s[lo + 1] = 0;
        len = lo + 1;
    }
    return len;
}

/* Text in rect (x, y, w, h) with the style the canvas has (widget_prepare_text_style was called), cut to w. At most 63 characters are read. */
static void ip_text(void *canvas, const char *utf8, int x, int y, int w, int h) {
    unsigned wide[64], n;
    int rect[4];
    n = ip_len(utf8);
    if (!n) return;
    tk_utf8_to_utf16_ex(utf8, n, wide, 64);
    n = ip_fit(canvas, wide, w);
    rect[0] = x, rect[1] = y, rect[2] = w, rect[3] = h;
    if (n) canvas_draw_text_in_rect(canvas, wide, n, rect);
}

/* ---------------------------------------------------------------------------
 * The wheel's angle. Sixteenths of a degree, clockwise from 12 o'clock (0 .. 5759). atan(x) = x / (1 + 0.28125 x^2) radians for 0 <= x <= 1 (error under
 * 0.1 degree), in Q10; the octants are folded onto it. Pure integer code, so the emulation tests check it against math.atan2.
 */
__attribute__((noinline)) int ip_angle(int dx, int dy) {
    unsigned ax = (unsigned)(dx < 0 ? -dx : dx), ay = (unsigned)(dy < 0 ? -dy : dy), lo = ax < ay ? ax : ay, hi = ax < ay ? ay : ax, t, d, a;
    if (!hi) return 0;
    t = (lo << 10) / hi;                          /* tan of the angle from the nearer axis, Q10, 0 .. 1024 */
    d = 1024 + ((288u * t * t) >> 20);
    a = (t << 10) / d;                            /* radians, Q10 */
    a = a * 917u >> 10;                           /* sixteenths of a degree: 16 * 180 / pi = 917.7 */
    /* a = atan(lo / hi): the angle from the vertical axis when |dx| <= |dy|, else from the horizontal one. dy < 0 is up; 90 degrees = 1440 (right), 270 = 4320 (left) */
    if (ax > ay) a = dx > 0 ? (dy < 0 ? 1440 - a : 1440 + a) : (dy < 0 ? 4320 + a : 4320 - a);
    else a = dy < 0 ? (dx >= 0 ? a : 5760 - a) : (dx >= 0 ? 2880 - a : 2880 + a);
    return (int)(a % 5760u);
}

/* The turn from angle a to b: the shorter way, -2880 .. 2879. */
__attribute__((noinline)) int ip_turn(int a, int b) {
    int d = b - a;
    if (d >= 2880) d -= 5760;
    if (d < -2880) d += 5760;
    return d;
}

/* Whether the chord from (ax, ay) to (bx, by) passes within IP_DEAD_R of the origin (coordinates clamped to +-150 by the caller: the cross product squared must
 * fit 32 bits). Integer: |a x b|^2 < R^2 |b - a|^2 inside the segment, else the nearer end. */
__attribute__((noinline)) int ip_chord_near(int ax, int ay, int bx, int by) {
    int dx = bx - ax, dy = by - ay, t = -(ax * dx + ay * dy), len2 = dx * dx + dy * dy, cross;
    unsigned c2;
    if (len2 == 0 || t <= 0) return ax * ax + ay * ay < IP_DEAD_R * IP_DEAD_R;
    if (t >= len2) return bx * bx + by * by < IP_DEAD_R * IP_DEAD_R;
    cross = ax * by - ay * bx;
    c2 = (unsigned)(cross * cross);
    return c2 < (unsigned)(IP_DEAD_R * IP_DEAD_R) * (unsigned)len2;
}

/* The wheel's memory of a drag goes (a new target or list, a new touch): the unspent turn, the direction, the speed, the tier. */
static void ip_wheel_reset(void) {
    ip.acc = ip.dir = ip.rev = ip.speed = ip.fast = 0;
}

/* ---------------------------------------------------------------------------
 * The stock lists
 */
static void *ip_stock_list(int kind) { return *(void **)(kind == K_PLAYLISTS ? PDEQ_PLAYLIST : PDEQ_SHOWLIST); }

static int ip_valid(void) {
    void *cur;
    if (!ip_is_list(ip_top()->kind)) return 1;
    cur = ip_stock_list(ip_top()->kind);
    return ip.list && cur == ip.list && deque_size(cur) == ip.count && (!ip.count || deque_at(cur, 0) == ip.first);
}

/* The query of level d (its ancestors first: an artist's albums need the artists list, a track list the albums list). 1 when the level's list exists. */
static int ip_run(int d) {
    struct lvl *l = &ip.st[d];
    void *par;
    switch (l->kind) {
    case K_ALBUMS: case K_CF: loadLocalClassList(CLASS_ALBUMS); break;
    case K_ARTISTS: loadLocalClassList(CLASS_ARTISTS); break;
    case K_SONGS: loadLocalClassList(CLASS_ALL_SONGS); break;
    case K_PLAYLISTS: loadLocalClassList(CLASS_PLAYLISTS); break;
    case K_ARTIST_ALBUMS:
        if (d < 1 || !ip_run(d - 1)) return 0;
        par = ip_stock_list(ip.st[d - 1].kind);
        if (!par || (unsigned)ip.st[d - 1].sel >= deque_size(par)) return 0;
        loadAlbumList(CLASS_ARTISTS, deque_at(par, (unsigned)ip.st[d - 1].sel));
        break;
    case K_TRACKS:
        if (d < 1 || !ip_run(d - 1)) return 0;
        par = ip_stock_list(ip.st[d - 1].kind);
        if (!par || (unsigned)ip.st[d - 1].sel >= deque_size(par)) return 0;
        loadAlbumdetailList(ip.st[d - 1].kind == K_ALBUMS || ip.st[d - 1].kind == K_CF ? CLASS_ALBUMS : CLASS_ARTIST_ALBUMS, deque_at(par, (unsigned)ip.st[d - 1].sel));
        *(int *)G_CLASS_TYPE = *(int *)CLASSINFO;   /* as albuminfo_page_init leaves it */
        break;
    case K_PL_TRACKS:
        if (d < 1 || !ip_run(d - 1)) return 0;
        par = ip_stock_list(K_PLAYLISTS);
        if (!par || (unsigned)ip.st[d - 1].sel >= deque_size(par)) return 0;
        *(int *)(CLASSINFO + CLASSINFO_ARG) = I(deque_at(par, (unsigned)ip.st[d - 1].sel), REC_DISC);   /* what the stock row tap leaves (@0x53d5f4) */
        loadLocalClassList(CLASS_PLAYLIST_SONGS);
        break;
    default: return 1;
    }
    return ip_stock_list(l->kind) != (void *)0;
}

/* Level d = the front one, its list read again from the stock queries. */
static void ip_load(void) {
    struct lvl *l = ip_top();
    void *list;
    ip.list = ip.first = (void *)0;
    ip.count = 0;
    if (!ip_is_list(l->kind)) return;
    if (ip_run(ip.depth) && (list = ip_stock_list(l->kind)) != (void *)0) {
        ip.list = list, ip.count = deque_size(list), ip.first = ip.count ? deque_at(list, 0) : (void *)0;
        ip.cls = ip_is_tracks(l->kind) ? (l->kind == K_SONGS ? CLASS_ALL_SONGS : l->kind == K_PL_TRACKS ? CLASS_PLAYLIST_SONGS : *(int *)CLASSINFO) : 0;
    }
    if (l->sel >= (int)ip.count) l->sel = ip.count ? (int)ip.count - 1 : 0;
    if (l->top > l->sel) l->top = l->sel;
    if (l->top < 0) l->top = 0;
}

/* The page is in front and its list went stale (another page queried): read it again. Returns whether the rows can be read now. */
static int ip_ensure(void) {
    if (ip_valid()) return 1;
    if (!pod_is_top(ip.win)) return 0;
    ip_load();
    return ip_valid();
}

static const char *ip_row_text(int kind, int i) {
    void *rec;
    const char *s;
    if (kind == K_MAIN) return TR(MAIN_KEYS[i]);
    if (kind == K_SETTINGS) return TR(SET_KEYS[i]);
    rec = deque_at(ip.list, (unsigned)i);
    if (kind == K_ALBUMS || kind == K_ARTIST_ALBUMS) {
        if (I(rec, REC_ID) == ID_ALL_SONGS) return TR("All albums");
        s = cc_str(rec, REC_ALBUM);
    } else if (kind == K_ARTISTS || kind == K_PLAYLISTS) s = cc_str(rec, REC_TITLE);
    else {
        s = cc_str(rec, REC_TITLE);
        if (!*s) s = cc_str(rec, REC_NAME);
    }
    return *s ? s : "-";
}

static int ip_rows(void) { return ip_top()->kind == K_MAIN ? M_COUNT : ip_top()->kind == K_SETTINGS ? S_COUNT : (int)ip.count; }

/* ---------------------------------------------------------------------------
 * The cover (decoded on the timer, never in paint) and the battery reading
 */
static unsigned ip_track_key(void *t) {
    unsigned h = cc_fnv(cc_fnv(cc_fnv(FNV_SEED, cc_str(t, REC_PATH)), cc_str(t, REC_TITLE)), cc_str(t, REC_NAME));
    return h | !h;
}

static void ip_cover(void *t, int first) {
    char url[80], tmp[40];
    const char *file = (const char *)0, *path;
    unsigned album = t && *cc_str(t, REC_ALBUM) ? cc_album_key(t) : 0, *px, i;
    int busy = 0;
    if (!ip.art) ip.art = bitmap_create_ex(IP_ART, IP_ART, IP_ART * 4, BITMAP_RGBA8888);
    if (!ip.art) return;
    px = (unsigned *)bitmap_lock_buffer_for_write(ip.art);
    if (!px) return;
    if (first) ip.settle = 4;
    ip.fkey = 0;
    file = album ? cc_url(url, album) : (const char *)0;
    if (file) {
        if (first) ip.settle = 0;
    } else if (t && (path = np_cover_file(&busy)) != (const char *)0 && !busy) {
        ip.fkey = np_file_key(path);
        if (ip.fkey) {
            snprintf(tmp, sizeof tmp, "file://%s", path);
            file = tmp;
        }
    }
    if (!file || !cc_decode(ip.win, file, 1, IP_ART, 1, px)) {   /* the stock disc, else flat grey */
        for (i = 0; i < IP_ART * IP_ART; ++i) px[i] = ART_GREY;
        cc_decode(ip.win, "p_default", 0, IP_ART, 1, px);
    }
    bitmap_unlock_buffer(ip.art);
}

/* ---------------------------------------------------------------------------
 * The main menu's cover pane, as q2-pod's Split Home (docs/modules/ipod.md "The cover pane"). All of it runs on the page's one timer (ip_tick); paint only copies.
 *   cover   the playing album's cover when the Cover Flow cache has it (cc_url: a picture, not the "no art" marker), else a random album's cached cover (drawn once a
 *           visit of the main menu: IP_PANE_TRIES cache file tests), else the stock disc, still. Decoded once, straight from the 168 px cache file to IP_PANE_ART (the
 *           pane's height zoomed 110%), on a tick of its own.
 *   pan     each axis a linear ping-pong across the zoom's margin (IP_PANE_R px, a sweep IP_DRIFT_X_MS / IP_DRIFT_Y_MS) from the centred crop. The phase counts only
 *           time shown (a step at most IP_DRIFT_MAX_MS) and carries over to a new cover. Paint copies a pane-sized window of the bitmap 1:1 at whole pixels, so nothing
 *           is resampled while it moves (the slideshow before this zoomed a 168 px window every frame and shimmered); a tick that moves no pixel repaints nothing.
 */
static void ip_pane_reset(void) {   /* the main menu comes back: a new random cover, and the playing album's cover looked up again (it may be cached since) */
    ip.pane.picked = ip.pane.pk_art = 0;
    ip.pane.pk = 0;
}

/* A random album with a cached cover, 0 when IP_PANE_TRIES draws found none. */
static unsigned ip_pane_pick(void) {
    char url[80];
    void *list = loadLocalClassList(CLASS_ALBUMS) > 0 ? *(void **)PDEQ_SHOWLIST : (void *)0;
    unsigned n = list ? deque_size(list) : 0, t, key;
    for (t = 0; n && t < IP_PANE_TRIES; ++t) {
        void *rec = deque_at(list, pod_rand(n));
        if (!rec || I(rec, REC_ID) == ID_ALL_SONGS || !*cc_str(rec, REC_ALBUM)) continue;
        key = cc_album_key(rec);
        if (cc_url(url, key)) return key;
    }
    return 0;
}

/* The album whose cover the pane should show: the playing one's when it is cached, else the random one. A cache file test only when the playing album changes. */
static unsigned ip_pane_want(void) {
    char url[80];
    void *t = cc_playing();
    unsigned k = t && *cc_str(t, REC_ALBUM) ? cc_album_key(t) : 0;
    if (k != ip.pane.pk) ip.pane.pk = k, ip.pane.pk_art = k && cc_url(url, k);
    if (ip.pane.pk_art) return k;
    if (!ip.pane.picked) ip.pane.rnd = ip_pane_pick(), ip.pane.picked = 1;
    return ip.pane.rnd;
}

/* q2-pod's drift_at: the place (0 .. range) of a linear ping-pong of `period` ms a sweep, at the phase. */
static int ip_drift_at(int range, unsigned period) {
    unsigned t = ip.pane.ms % (2 * period);
    return (int)((unsigned)range * ((t < period ? t : 2 * period - t) >> 4) / (period >> 4));
}

static void ip_pane_place(void) {   /* the stock disc stands still in the middle */
    ip.pane.x = ip.pane.key ? ip_drift_at(IP_PANE_R, IP_DRIFT_X_MS) : IP_PANE_R / 2;
    ip.pane.y = ip.pane.key ? ip_drift_at(IP_PANE_R, IP_DRIFT_Y_MS) : IP_PANE_R / 2;
}

/* The cover of `key` (0: the stock disc) into the pane's bitmap. */
static void ip_pane_decode(unsigned key) {
    char url[80];
    const char *file = key ? cc_url(url, key) : (const char *)0;
    unsigned *px, i;
    ip.pane.asked = key;
    if (!ip.pane.bmp) ip.pane.bmp = bitmap_create_ex(IP_PANE_ART, IP_PANE_ART, IP_PANE_ART * 4, BITMAP_RGBA8888);
    if (!ip.pane.bmp) return;
    px = (unsigned *)bitmap_lock_buffer_for_write(ip.pane.bmp);
    if (!px) return;
    if (!file || !cc_decode(ip.win, file, 1, IP_PANE_ART, 1, px)) {   /* the stock disc, else flat grey */
        for (i = 0; i < IP_PANE_ART * IP_PANE_ART; ++i) px[i] = ART_GREY;
        cc_decode(ip.win, "p_default", 0, IP_PANE_ART, 1, px);
        key = 0;
    }
    bitmap_unlock_buffer(ip.pane.bmp);
    ip.pane.key = key, ip.pane.have = 1;
    ip_pane_place();
}

/* One tick (the page is in front and the main menu is the level): a new cover, else the pan's step. Whether the pane changed. */
static int ip_pane_step(void) {
    unsigned want, now, step;
    int x = ip.pane.x, y = ip.pane.y;
    if (ip.depth != 0 || !pod_is_top(ip.win)) return 0;
    now = time_now_ms(), step = now - ip.pane.t0;
    ip.pane.t0 = now;
    want = ip_pane_want();
    if (!ip.pane.have || want != ip.pane.asked) {   /* the one decode of this tick */
        ip_pane_decode(want);
        return 1;
    }
    if (!ip.pane.key) return 0;
    ip.pane.ms = (ip.pane.ms + (step < IP_DRIFT_MAX_MS ? step : IP_DRIFT_MAX_MS)) % (2u * IP_DRIFT_X_MS * IP_DRIFT_Y_MS);   /* a whole number of both axes' cycles */
    ip_pane_place();
    return ip.pane.x != x || ip.pane.y != y;
}

/* The interval the page's one timer should have: IPCF_FRAME_MS while the Cover Flow level in front slides or decodes (ipod_cf.c); IP_DRIFT_MS while the cover pans
 * (the main menu is the level, the page is in front, and the pane has a cover or is still being made); IP_TICK_MS otherwise (the disc: the slow look still finds a new cover). */
static unsigned ip_want_ms(void) {
    if (ip.fg && ip_top()->kind == K_CF && ipcf_busy()) return IPCF_FRAME_MS;
    return ip.depth == 0 && ip.fg && (!ip.pane.have || ip.pane.key) && pod_is_top(ip.win) ? IP_DRIFT_MS : IP_TICK_MS;
}

static void ip_retime(void) {
    unsigned want = ip_want_ms();
    if (ip.timer && want != ip.ival) {
        timer_modify(ip.timer, want);
        ip.ival = want;
    }
}

/* The battery as the real status bar shows it: pgbar_battery's value (0 .. 100) and whether img_battery is the charging picture. -1: no bar. */
static int ip_battery(int *charging) {
    void *bar = *(void **)SYSTEM_BAR, *pg, *img;
    const char *name;
    *charging = 0;
    pg = bar ? widget_lookup(bar, "pgbar_battery", 1) : (void *)0;
    if (!pg) return -1;
    img = widget_lookup(bar, "img_battery", 1);
    name = img ? widget_get_prop_str(img, "image", "") : "";
    *charging = name && !strcmp(name, "bar_charge");
    return widget_get_prop_int(pg, "value", 0);
}

/* One look at everything the timer watches. Returns whether the screen needs a repaint, and keeps the cover. */
static int ip_look(void) {
    unsigned sig[5];
    int charging, i, pos = 0, len = 0, changed = 0;
    void *t = cc_playing(), *q = *(void **)PLAY_QUEUE;
    sig[0] = (unsigned)(ip_battery(&charging) + 1) | (unsigned)charging << 8;
    sig[1] = (unsigned)mclGetPlayStatus();
    sig[2] = t ? ip_track_key(t) : 0;
    sig[3] = 0;
    if (ip_top()->kind == K_NOW && t && get_playtimeandlength(&pos, &len) == 1) sig[3] = (unsigned)(pos + 1) * 4099u ^ (unsigned)len;
    sig[4] = q ? deque_size(q) : 0;
    if (sig[2] != ip.track) {
        ip.track = sig[2];
        ip_cover(t, 1);
        changed = 1;
    } else if (ip.settle > 0 && t) {   /* demo writes the /tmp cover a little after the track changes */
        int busy = 0;
        const char *path = np_cover_file(&busy);
        unsigned k;
        if (!busy) {
            ip.settle--;
            k = path ? np_file_key(path) : 0;
            if (k && k != ip.fkey) ip_cover(t, 0), changed = 1;
        }
    }
    for (i = 0; i < 5; ++i)
        if (sig[i] != ip.sig[i]) ip.sig[i] = sig[i], changed = 1;
    return changed;
}

/* ---------------------------------------------------------------------------
 * Painting
 */
static void ip_chevron(void *canvas, int x, int ymid, unsigned rgb) {
    int dy;
    for (dy = -4; dy <= 4; ++dy) ip_fill(canvas, x + 4 - (dy < 0 ? -dy : dy), ymid + dy, 2, 1, rgb);
}

static void ip_battery_glyph(void *canvas, int x, int y) {
    int charging, pct = ip_battery(&charging), w;
    ip_fill(canvas, x, y, 21, 1, 0), ip_fill(canvas, x, y + 9, 21, 1, 0), ip_fill(canvas, x, y, 1, 10, 0), ip_fill(canvas, x + 20, y, 1, 10, 0);
    ip_fill(canvas, x + 21, y + 3, 2, 4, 0);
    if (pct < 0) return;
    w = 16 * (pct > 100 ? 100 : pct) / 100;
    if (w > 0) ip_fill(canvas, x + 2, y + 2, w, 6, charging ? 0x59c734u : pct <= 20 ? 0x4814ffu : 0x4cb84cu);
}

/* The play state, 10 px tall from y (the rows the battery glyph uses, so the bar's glyphs share one centre line), in the selection's blue, a row at a time down its
 * gradient, as the iPod's: a triangle 5 px wide, or two 3 px bars 8 px across; both end at x + 8. */
static void ip_play_glyph(void *canvas, int x, int y) {
    int st = mclGetPlayStatus() == 2 ? 1 : mclGetPlayStatus() == 3 ? 2 : 0, r;
    for (r = 0; st && r < 10; ++r) {
        unsigned c = ip_lerp(IP_SEL_TOP, IP_SEL_BOT, r, 10);
        if (st == 1) ip_fill(canvas, x + 3, y + r, (r < 9 - r ? r : 9 - r) + 1, 1, c);
        else ip_fill(canvas, x, y + r, 3, 1, c), ip_fill(canvas, x + 5, y + r, 3, 1, c);
    }
}

static const char *ip_title(int kind) {
    switch (kind) {
    case K_ALBUMS: return TR("Albums");
    case K_ARTISTS: return TR("Artists");
    case K_SONGS: return TR("Songs");
    case K_PLAYLISTS: return TR("Playlists");
    case K_NOW: return TR("Now Playing");
    case K_CF: return TR("Cover Flow");
    case K_SETTINGS: return TR("cdrippersettings");
    default: return "M1+ Music";   /* a brand name: not translated, like the menu's title */
    }
}

/* The iPod's title bar: the title on the left, no clock; the play state right of it, next to the battery. */
static void ip_paint_bar(void *canvas, int kind) {
    ip_vgrad(canvas, 0, 0, IP_W, IP_BAR_H - 1, IP_BAR_TOP, IP_BAR_BOT);
    ip_fill(canvas, 0, IP_BAR_H - 1, IP_W, 1, 0x8c8480u);
    /* One centre line, y 11.5 (rows 7 .. 16): the glyphs are 10 px from y 7; the text box starts at y 1, because AWTK's metric centring in the 23 px
     * box put the caps 1 px high on the device (shot-0014: caps 6 .. 15). */
    ip_play_glyph(canvas, IP_W - 32 - 14, IP_BAR_H / 2 - 5);
    ip_battery_glyph(canvas, IP_W - 32, IP_BAR_H / 2 - 5);
    widget_prepare_text_style(ip.st_title, canvas);   /* left 16 px */
    ip_text(canvas, ip_title(kind), 8, 1, IP_W - 32 - 14 - 8 - 8, IP_BAR_H - 1);
}

/* The cover pane of the main menu (the iPod 6G split screen): a pane-sized window of the cover's bitmap at the pan's place, copied 1:1 (source and destination the same
 * size: canvas_draw_image blits, it does not scale). Paint only draws what the timer decoded. */
static void ip_paint_pane(void *canvas) {
    int src[4], dst[4];
    ip_fill(canvas, IP_SPLIT_X, IP_BAR_H, IP_W - IP_SPLIT_X, IP_SCREEN_H - IP_BAR_H, IP_PANE);
    if (ip.pane.have && ip.pane.bmp) {
        src[0] = (IP_PANE_ART - IP_PANE_W - IP_PANE_R) / 2 + ip.pane.x, src[1] = ip.pane.y, src[2] = IP_PANE_W, src[3] = IP_PANE_H;
        dst[0] = IP_PANE_X, dst[1] = IP_BAR_H, dst[2] = IP_PANE_W, dst[3] = IP_PANE_H;
        canvas_draw_image(canvas, ip.pane.bmp, src, dst);
    }
    ip_fill(canvas, IP_SPLIT_X, IP_BAR_H, 1, IP_SCREEN_H - IP_BAR_H, 0xddddddu);
}

/* A text in the canvas' current style, right aligned so that it ends at x2 (a Settings row's value; at most 120 px). Its width. */
static int ip_text_right(void *canvas, const char *utf8, int x2, int y, int h) {
    unsigned wide[64], n = ip_len(utf8);
    int rect[4], w;
    if (!n) return 0;
    tk_utf8_to_utf16_ex(utf8, n, wide, 64);
    n = ip_fit(canvas, wide, 120);
    w = n ? (int)(canvas_measure_text(canvas, wide, n) + 0.999f) : 0;
    rect[0] = x2 - w, rect[1] = y, rect[2] = w + 2, rect[3] = h;
    if (n) canvas_draw_text_in_rect(canvas, wide, n, rect);
    return w;
}

/* The value a Settings row shows: the play mode as the stock Play settings page names it (Shuffle is mode 2; Repeat is mode 1 or 3), the version tag on About. NULL: none. */
static const char *ip_set_value(int row) {
    int mode = mclGetPlayMode();
    if (row == S_SHUFFLE) return TR(mode == MODE_SHUFFLE ? "Songs" : "Off");
    if (row == S_REPEAT) return mode == MODE_REPEAT_ONE ? TR("One") : mode == MODE_REPEAT_ALL ? TR("All") : TR("Off");
    if (row == S_ABOUT) return M1PLUS_TAG;
    return (const char *)0;
}

static void ip_paint_list(void *canvas, int kind) {
    struct lvl *l = ip_top();
    int i, fixed = kind == K_MAIN || kind == K_SETTINGS, n = ip.list || fixed ? ip_rows() : 0, right = kind == K_MAIN ? IP_SPLIT_X : IP_W, pass, y;
    if (!fixed && !ip_valid()) n = 0;   /* a stale list is never read */
    for (pass = 0; pass < 2; ++pass) {   /* the unselected rows, then the selected one: one text style at a time */
        widget_prepare_text_style(pass ? ip.st_sel : ip.st_row, canvas);
        for (i = 0; i < IP_ROWS && l->top + i < n; ++i) {
            int idx = l->top + i, sel = idx == l->sel, vw = 0, chev = !ip_is_tracks(kind);
            const char *val = kind == K_SETTINGS ? ip_set_value(idx) : (const char *)0;
            if (sel != pass) continue;
            y = IP_BAR_H + i * IP_ROW_H;
            if (sel) ip_vgrad(canvas, 0, y, right, IP_ROW_H, IP_SEL_TOP, IP_SEL_BOT);
            if (val) vw = ip_text_right(canvas, val, IP_W - IP_TEXT_X, y, IP_ROW_H), chev = 0;   /* a Settings row with a value: the value instead of the chevron */
            ip_text(canvas, ip_row_text(kind, idx), IP_TEXT_X, y, vw ? IP_W - 2 * IP_TEXT_X - vw - 12 : right - IP_TEXT_X - 22, IP_ROW_H);
            if (sel && chev) ip_chevron(canvas, right - 14, y + IP_ROW_H / 2, 0xffffffu);   /* as the iPod: only the selected row has one */
        }
    }
    if (!fixed && n == 0 && ip_valid()) {
        widget_prepare_text_style(ip.st_small, canvas);
        ip_text(canvas, TR("No songs"), IP_TEXT_X, IP_BAR_H, IP_W - 2 * IP_TEXT_X, IP_ROW_H);
    }
}

static void ip_clock_text(char *out, unsigned size, int secs) {
    if (secs < 0) secs = 0;
    snprintf(out, size, "%d:%02d", secs / 60, secs % 60);
}

static void ip_paint_now(void *canvas) {
    void *t = cc_playing();
    int pos = 0, len = 0, src[4], dst[4], fw, i, n = 0, q = 0;
    char line[48], a[12], b[12];
    const char *f;
    void *queue = *(void **)PLAY_QUEUE;
    if (!t) {
        widget_prepare_text_style(ip.st_np2, canvas);
        ip_text(canvas, TR("Not Playing"), IP_TEXT_X, IP_BAR_H + 80, IP_W - 2 * IP_TEXT_X, 30);
        return;
    }
    if (ip.art) {
        src[0] = 0, src[1] = 0, src[2] = IP_ART, src[3] = IP_ART;
        dst[0] = IP_NP_ART_X, dst[1] = IP_NP_ART_Y, dst[2] = IP_ART, dst[3] = IP_ART;
        canvas_draw_image(canvas, ip.art, src, dst);
    }
    widget_prepare_text_style(ip.st_np1, canvas);
    f = cc_str(t, REC_TITLE);
    ip_text(canvas, *f ? f : cc_str(t, REC_NAME), IP_NP_TEXT_X, IP_NP_ART_Y + 4, IP_W - IP_NP_TEXT_X - 8, 26);
    widget_prepare_text_style(ip.st_np2, canvas);
    ip_text(canvas, cc_str(t, REC_ARTIST), IP_NP_TEXT_X, IP_NP_ART_Y + 32, IP_W - IP_NP_TEXT_X - 8, 24);
    ip_text(canvas, cc_str(t, REC_ALBUM), IP_NP_TEXT_X, IP_NP_ART_Y + 56, IP_W - IP_NP_TEXT_X - 8, 24);
    widget_prepare_text_style(ip.st_small, canvas);
    if (queue) {   /* the place in the queue: "3 / 12" (the translation table allows one %d a text, so no "3 of 12") */
        q = mclGetPlayPos() + 1, n = (int)deque_size(queue);
        snprintf(line, sizeof line, "%d / %d", q, n);
        ip_text(canvas, line, IP_NP_TEXT_X, IP_NP_ART_Y + 92, IP_W - IP_NP_TEXT_X - 8, 22);
    }
    if (get_playtimeandlength(&pos, &len) == 1 && len > 0) {
        if (pos < 0) pos = 0;
        if (pos > len) pos = len;
        ip_fill(canvas, 12, IP_NP_BAR_Y, IP_W - 24, IP_NP_BAR_H, 0xdad6d4u);
        fw = (IP_W - 24) * pos / len;
        for (i = 0; i < IP_NP_BAR_H && fw > 0; ++i) ip_fill(canvas, 12, IP_NP_BAR_Y + i, fw, 1, ip_lerp(IP_SEL_TOP, IP_SEL_BOT, i, IP_NP_BAR_H));
        ip_clock_text(a, sizeof a, pos);
        snprintf(b, sizeof b, "-%d:%02d", (len - pos) / 60, (len - pos) % 60);
        ip_text(canvas, a, 12, IP_NP_BAR_Y + 14, 80, 22);
        widget_prepare_text_style(ip.st_time, canvas);   /* right aligned */
        ip_text(canvas, b, IP_W - 12 - 80, IP_NP_BAR_Y + 14, 80, 22);
    }
}

static int ip_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int kind;
    (void)ctx;
    if (!canvas || !ip.win) return RET_OK;
    kind = ip_top()->kind;   /* paint reads only a list that is still the stock one; it never queries (the timer reads a stale one again) */
    ip_fill(canvas, 0, 0, IP_W, IP_SCREEN_H, 0xffffffu);
    if (kind == K_MAIN) ip_paint_pane(canvas);
    if (kind == K_CF) ipcf_paint(canvas, ip_valid() ? ip.list : (void *)0, ip_valid() ? ip.count : 0, ip.st_row);   /* the covers on white under the bar (patch/ipod_cf.c) */
    else if (kind == K_NOW) ip_paint_now(canvas);
    else ip_paint_list(canvas, kind);
    ip_paint_bar(canvas, kind);
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * Actions
 */

static void ip_push(int kind) {
    if (ip.depth + 1 >= IP_DEPTH) return;
    ip.st[++ip.depth] = (struct lvl){kind, 0, 0};
    ip_wheel_reset();
    ip_load();
    ip_redraw();
    ip_retime();   /* the pace of the new level: Cover Flow's frames, else the pan stops */
}

static void ip_pop(void) {
    if (ip.depth == 0) {
        navigator_back();   /* MENU on the main menu closes the page */
        return;
    }
    if (ip_top()->kind == K_CF) ipcf_close();   /* Cover Flow's frame and textures go */
    ip.depth--;
    ip_wheel_reset();
    ip_load();
    if (ip.depth == 0) ip_pane_reset();   /* back on the main menu: a new random cover, the playing one looked up again */
    ip_redraw();
    ip_retime();
}

/* A step of the wheel: the cursor moves `rows` rows (no wrap, as the iPod; clamped at the ends, and a step that wanted to go past an end nudges the rows), the
 * window follows it. */
static void ip_step(int dir, int rows) {
    struct lvl *l = ip_top();
    int n, want;
    if (l->kind == K_NOW) return;   /* nothing turns on Now Playing in this version (docs/modules/ipod.md) */
    if (l->kind != K_MAIN && l->kind != K_SETTINGS && !ip_ensure()) return;
    n = ip_rows();
    if (n <= 0) return;
    want = l->sel + dir * rows;
    want = want < 0 ? 0 : want >= n ? n - 1 : want;
    if (l->kind == K_CF) {   /* the slide goes to the album (ipod_cf.c), the pace is the animation's; at an end nothing happens */
        if (want != l->sel) l->sel = want, ipcf_goto(want), ip_retime(), ip_redraw();
        return;
    }
    l->sel = want;
    if (l->sel < l->top) l->top = l->sel;
    if (l->sel >= l->top + IP_ROWS) l->top = l->sel - IP_ROWS + 1;
    ip_redraw();
}

/* The stock Songs row's handler (@0x5275a4: loadSongList of the shown list), then start_player as the stock Play all button does (@0x525d48): the queue is
 * copied, force_refreshflag is set, the page stays where it is. The Now Playing level shows the result. */
static void ip_play(int at, int shuffle) {
    void *pick, *queue, *first;
    unsigned n, idx = 0;
    int found;
    if (!ip_ensure() || at < 0 || (unsigned)at >= ip.count) return;
    pick = deque_at(ip.list, (unsigned)at);
    if (!pick || access(cc_str(pick, REC_PATH), F_OK)) {
        pod_toast(TR("Storage unavailable"));
        return;
    }
    queue = _create_deque("stSongInfo");
    if (!queue) return;
    deque_init(queue);
    if (ip_top()->kind == K_PL_TRACKS) {   /* the playlist's id goes back into classinfo[1], as the stock row tap leaves it (the Songs page does the same before every play) */
        void *pl = ip_stock_list(K_PLAYLISTS);
        int row = ip.st[ip.depth - 1].sel;
        if (pl && (unsigned)row < deque_size(pl)) *(int *)(CLASSINFO + CLASSINFO_ARG) = I(deque_at(pl, (unsigned)row), REC_DISC);
    }
    found = loadSongList(queue, cc_str(pick, REC_NAME), I(pick, REC_CUE_START), ip.cls);
    n = deque_size(queue);
    if (n) {   /* the row's own index wins over a duplicate file name (the Songs page's rule) */
        if ((unsigned)at < n && !strcmp(cc_str(deque_at(queue, (unsigned)at), REC_PATH), cc_str(pick, REC_PATH))) idx = (unsigned)at;
        else if (found >= 0 && (unsigned)found < n) idx = (unsigned)found;
    }
    if (shuffle && n) {   /* Shuffle Songs leaves the podcast episodes out (patch/pcmodel.c; the queue itself when there are none) */
        int at_i = (int)idx;
        queue = pc_strip(queue, &at_i);
        idx = (unsigned)at_i;
        n = queue ? deque_size(queue) : 0;
        if (!queue) {
            pod_toast(TR("No songs"));
            return;
        }
    }
    first = n ? deque_at(queue, idx) : (void *)0;
    if (!first || access(cc_str(first, REC_PATH), F_OK)) {
        deque_destroy(queue);
        pod_toast(TR(n ? "Storage unavailable" : "No songs"));
        return;
    }
    *(int *)G_CLASS_TYPE = ip.cls;
    if (shuffle) pod_set_mode(MODE_SHUFFLE);   /* Shuffle Songs: stock Shuffle over the whole queue, as the Shuffle page sets it (patch/shuffle.c) */
    start_player(queue, (int)idx, ip.cls, PLAY_MODE);
    *(unsigned char *)FORCE_REFRESH = 1;
    deque_destroy(queue);
    ip_push(K_NOW);
}

/* Shuffle Songs: the whole library is the queue (the Songs query, as the Shuffle page), a random first song, stock Shuffle (mode 2) so the rest are drawn at random; the iPod's
 * own Now Playing level shows it (no stock page). Nothing is changed when the library is empty or the first file is gone. */
static void ip_shuffle_all(void) {
    void *list = loadLocalClassList(CLASS_ALL_SONGS) > 0 ? *(void **)PDEQ_SHOWLIST : (void *)0;
    unsigned n = list ? deque_size(list) : 0;
    if (!n) {
        pod_toast(TR("Update Local Music first"));
        return;
    }
    ip.list = list, ip.count = n, ip.first = deque_at(list, 0), ip.cls = CLASS_ALL_SONGS;
    ip_play((int)pod_rand(n), 1);
}

/* Centre press on a Settings row: Shuffle flips Off / Songs, Repeat cycles Off, One, All (both are the one stock play mode: Shuffle is mode 2, which has no repeat of its own, so
 * turning Repeat on turns Shuffle off and the reverse), Customize opens our Customize page, About does nothing. */
static void ip_settings_select(int row) {
    int mode = mclGetPlayMode();
    if (row == S_SHUFFLE) {
        if (mode == MODE_SHUFFLE) pod_set_in_order();
        else pod_set_mode(MODE_SHUFFLE);
    } else if (row == S_REPEAT) pod_set_mode(mode == MODE_REPEAT_ONE ? MODE_REPEAT_ALL : mode == MODE_REPEAT_ALL ? MODE_ORDER : MODE_REPEAT_ONE);
    else if (row == S_MORE) pod_open_settings();
    ip_redraw();
}

static void ip_select(void) {
    struct lvl *l = ip_top();
    int kind = l->kind;
    if (kind == K_NOW) {
        playpause_quick_click();
        ip_look();
        ip_redraw();
        return;
    }
    if (kind == K_SETTINGS) {
        ip_settings_select(l->sel);
        return;
    }
    if (kind == K_MAIN) {
        switch (l->sel) {
        case M_COVER:   /* Cover Flow inside the iPod screen (ipod_cf.c); no memory for its frame: the existing Cover Flow page, over this one */
            if (ipcf_open(ip.win)) ip_push(K_CF);
            else coverflow_open();
            break;
        case M_ALBUMS: ip_push(K_ALBUMS); break;
        case M_ARTISTS: ip_push(K_ARTISTS); break;
        case M_SONGS: ip_push(K_SONGS); break;
        case M_PLAYLISTS: ip_push(K_PLAYLISTS); break;
        case M_SHUFFLE: ip_shuffle_all(); break;   /* Shuffle Songs: stock Shuffle over the library, the iPod's own Now Playing */
        case M_SETTINGS: ip_push(K_SETTINGS); break;   /* the iPod's Settings list; its last row opens the existing Settings page */
        case M_NOW: ip_push(K_NOW); break;
        }
        return;
    }
    if (!ip_ensure() || !ip.count) return;
    if (ip_is_tracks(kind)) ip_play(l->sel, 0);
    else if (kind == K_ALBUMS || kind == K_CF) ip_push(K_TRACKS);   /* Cover Flow's centre button: the album's tracks */
    else if (kind == K_ARTISTS) ip_push(K_ARTIST_ALBUMS);
    else if (kind == K_ARTIST_ALBUMS) ip_push(K_TRACKS);
    else if (kind == K_PLAYLISTS) ip_push(K_PL_TRACKS);
}

/* previous / next: the stock functions the Now Playing buttons and the hardware keys call (a click within a second of the last is ignored by stock). */
static void ip_skip(int next, void *e) {
    unsigned ev[4];
    if (!e) {
        memset(ev, 0, sizeof ev);
        ev[2] = time_now_ms();
        e = ev;
    }
    if (next) next_quick_click(e, 0);
    else prev_quick_click(e, 0);
    if (ip_look()) ip_redraw();
}

/* ---------------------------------------------------------------------------
 * The wheel's touch
 */
static void ip_local(void *e, int *x, int *y) {
    int pt[2];
    pt[0] = I(e, PE_X), pt[1] = I(e, PE_Y);
    widget_to_local(ip.wheel, pt);
    *x = pt[0] - IP_WHEEL_D / 2, *y = pt[1] - IP_WHEEL_D / 2;
}

static void ip_release(void) {
    if (ip.touch != R_NONE) widget_ungrab(ip.win, ip.wheel);
    ip.touch = R_NONE;
}

/* Rows a step for a list of n rows at tier idx (0 .. any: past the last tier is the last tier). A list of IP_LONG rows or fewer is always 1. */
__attribute__((noinline)) int ip_tier_rows(int n, int idx) {
    static const unsigned char tiers[] = {1, 2, 3, 5, 8, 13, 21, 34};
    if (n <= IP_LONG || idx <= 0) return 1;
    return tiers[idx > (int)sizeof tiers - 1 ? (int)sizeof tiers - 1 : idx];
}

static int ip_clamp150(int v) { return v < -150 ? -150 : v > 150 ? 150 : v; }

/* One move of a finger that began on the ring, to (x, y) at time `now` (ms). The turn from the last angle accumulates in ip.acc and every IP_STEP of it moves
 * the cursor, with these rules (docs/modules/ipod.md "The wheel"):
 *   chord      a move whose chord passes within IP_DEAD_R of the centre turns nothing (the angle jumps there); the reference angle is just taken again.
 *   reversal   after the direction flips, IP_REVERSE of reverse travel is swallowed first (the turn-around jitter), then the accumulator starts again from 0.
 *   speed      the angular speed, clamped at IP_VMAX and smoothed (3/20), reset by a pause (IP_PAUSE_MS) or a reversal; on a list of more than IP_LONG rows, held above IP_FAST
 *              for IP_TIER_MS a time it climbs one tier of rows a step, and it is tier 0 (one row) again the moment the speed falls below. */
static void ip_turn_move(int x, int y, unsigned now) {
    int a = ip_angle(x, y), d, mag, dt, idx = 0, rows;
    if (ip_chord_near(ip_clamp150(ip.lx), ip_clamp150(ip.ly), ip_clamp150(x), ip_clamp150(y))) {
        ip.last = a, ip.lt = now, ip.speed = ip.fast = 0;
        return;
    }
    d = ip_turn(ip.last, a);
    ip.last = a;
    if (!d) return;
    mag = d < 0 ? -d : d;
    dt = (int)(now - ip.lt);
    ip.lt = now;
    if (dt > IP_PAUSE_MS || dt < 0) ip.speed = ip.fast = 0;
    else if (dt > 0) {
        int inst = mag * 1000 / dt;
        if (inst > IP_VMAX) inst = IP_VMAX;
        ip.speed += (inst - ip.speed) * IP_SMOOTH_NUM / IP_SMOOTH_DEN;
    }
    if (!ip.dir) ip.dir = d > 0 ? 1 : -1;
    if ((d > 0 ? 1 : -1) != ip.dir) {
        ip.rev += mag;
        if (ip.rev < IP_REVERSE) return;
        ip.dir = -ip.dir, ip.rev = 0, ip.acc = 0, ip.speed = ip.fast = 0;
        return;
    }
    if (ip.rev) {   /* travel back in the committed direction first takes back the swallowed reverse travel (a jitter nets zero) */
        int back = mag < ip.rev ? mag : ip.rev;
        ip.rev -= back, mag -= back;
        d = d < 0 ? -mag : mag;
    }
    ip.acc += d;
    if (ip.speed > IP_FAST) {
        if (!ip.fast) ip.fast = 1, ip.fast_t0 = now;
        idx = (int)((now - ip.fast_t0) / IP_TIER_MS);
    } else ip.fast = 0;
    rows = ip_tier_rows(ip_rows(), idx);
    while (ip.acc >= IP_STEP) ip.acc -= IP_STEP, ip.turned = 1, ip_step(1, rows);
    while (ip.acc <= -IP_STEP) ip.acc += IP_STEP, ip.turned = 1, ip_step(-1, rows);
}

static int ip_on_wheel(void *ctx, void *e) {
    int type, x, y, r2;
    (void)ctx;
    if (!e || !ip.win) return RET_OK;
    type = *(int *)e;
    if (type == EVT_POINTER_DOWN) {
        ip_local(e, &x, &y);
        r2 = x * x + y * y;
        ip_release();
        if (r2 > IP_RING_R * IP_RING_R) return RET_OK;   /* the square's corners are not the wheel */
        ip.touch = r2 < IP_HUB_R * IP_HUB_R ? R_CENTRE : R_RING;
        ip.sx = ip.lx = x, ip.sy = ip.ly = y;
        ip.last = ip_angle(x, y), ip.turned = ip.far = 0, ip.lt = (unsigned)I(e, 8);
        ip_wheel_reset();
        widget_grab(ip.win, ip.wheel);
    } else if (type == EVT_POINTER_MOVE && ip.touch != R_NONE) {
        int dx, dy;
        ip_local(e, &x, &y);
        dx = x - ip.sx, dy = y - ip.sy;
        if (dx * dx + dy * dy >= IP_TAP_PX * IP_TAP_PX) ip.far = 1;
        if (ip.touch == R_RING) ip_turn_move(x, y, (unsigned)I(e, 8));
        ip.lx = x, ip.ly = y;
    } else if (type == EVT_POINTER_UP && ip.touch != R_NONE) {
        int touch = ip.touch, turned = ip.turned, far = ip.far, sx = ip.sx, sy = ip.sy;
        ip_local(e, &x, &y);
        if ((x - sx) * (x - sx) + (y - sy) * (y - sy) >= IP_TAP_PX * IP_TAP_PX) far = 1;
        ip_release();
        if (turned || far) return RET_OK;
        if (touch == R_CENTRE) ip_select();
        else if ((sy < 0 ? -sy : sy) > (sx < 0 ? -sx : sx)) {
            if (sy < 0) ip_pop();   /* MENU */
            else playpause_quick_click(), ip_look(), ip_redraw();
        } else ip_skip(sx > 0, e);
    } else if (type == EVT_POINTER_ABORT) {
        ip_release();
    }
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * The timer, the window's events
 */
static int ip_tick(const void *timer) {
    (void)timer;
    if (!ip.win || !ip.fg) {
        ip.timer = 0;
        return RET_OK;
    }
    if (!ip_valid() && pod_is_top(ip.win)) {   /* another query replaced the stock list under the page: read it again (the Songs page's stale timer) */
        ip_load();
        ip_redraw();
    }
    if (ip_top()->kind == K_CF && ip_valid() && ipcf_tick(ip.list, ip.count)) ip_redraw();   /* Cover Flow slides and decodes on this timer (ipod_cf.c) */
    if (ip_pane_step()) ip_redraw();   /* the main menu's cover pane (only on the main menu) */
    if (ip.ival == IP_TICK_MS || ++ip.lookn >= IP_DRIFT_LOOK) {   /* a fast tick (the pan, Cover Flow): the rest of the look (battery, play state, track) every IP_DRIFT_LOOK ticks */
        ip.lookn = 0;
        if (ip_look()) ip_redraw();
    }
    ip_retime();   /* one timer, its interval changed in place (timer_modify): never removed or added while the page lives */
    return RET_REPEAT;
}

static int ip_first(const void *timer) {
    (void)timer;
    ip.timer = 0;
    if (!ip.win || !ip.fg) return RET_OK;
    ip.ival = ip_want_ms();
    ip.timer = timer_add(ip_tick, (void *)0, ip.ival);
    if (ip_look()) ip_redraw();
    return RET_OK;
}

static void ip_unarm(void) {
    if (ip.timer) timer_remove(ip.timer);
    ip.timer = 0;
}

static int ip_on_background(void *ctx, void *e) {
    (void)e;
    if (!ip.win || ctx != ip.win) return RET_OK;
    ip.fg = 0;
    ip_unarm();
    ip_release();
    return RET_OK;
}

static int ip_on_foreground(void *ctx, void *e) {
    (void)e;
    if (!ip.win || ctx != ip.win) return RET_OK;
    ip.fg = 1;
    ip_load();   /* another page may have queried (the Playlists a stock page opened, Cover Flow ...): the list is read again */
    if (ip.depth == 0) ip_pane_reset();   /* ... and the main menu has a new random cover */
    ip.sig[0] = ip.sig[1] = ip.sig[2] = ip.sig[3] = ip.sig[4] = ~0u;   /* ... and the screen is painted fresh */
    if (!ip.timer) ip.timer = timer_add(ip_first, (void *)0, IP_FIRST_MS);
    ip_redraw();
    return RET_OK;
}

static int ip_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx != ip.win) return RET_OK;   /* an earlier window's end leaves a newer page alone */
    ip_unarm();
    if (ip.touch != R_NONE) widget_ungrab(ip.win, ip.wheel);
    if (ip.art) bitmap_destroy(ip.art);
    if (ip.pane.bmp) bitmap_destroy(ip.pane.bmp);
    ipcf_close();
    memset(&ip, 0, sizeof ip);
    return RET_OK;
}

/* The menu's iPod row. 0 once the page is up (or already open); -1 when it could not open (no window, an asset that is not ours): nothing happens. */
int ipod_open(void) {
    if (ip.win) return 0;
    memset(&ip, 0, sizeof ip);
    ip.win = window_open("m1plus_ipod");
    if (!ip.win) {
        memset(&ip, 0, sizeof ip);
        return -1;
    }
    widget_on(ip.win, EVT_DESTROY, ip_on_destroy, ip.win);
    ip.screen = widget_lookup(ip.win, "ipod_screen", 1);
    ip.wheel = widget_lookup(ip.win, "ipod_wheel", 1);
    ip.st_row = widget_lookup(ip.win, "label_ip_row", 1);
    ip.st_sel = widget_lookup(ip.win, "label_ip_sel", 1);
    ip.st_title = widget_lookup(ip.win, "label_ip_title", 1);
    ip.st_small = widget_lookup(ip.win, "label_ip_small", 1);
    ip.st_np1 = widget_lookup(ip.win, "label_ip_np1", 1);
    ip.st_np2 = widget_lookup(ip.win, "label_ip_np2", 1);
    ip.st_time = widget_lookup(ip.win, "label_ip_time", 1);
    if (!ip.screen || !ip.wheel || !ip.st_row || !ip.st_sel || !ip.st_title || !ip.st_small || !ip.st_np1 || !ip.st_np2 || !ip.st_time) {
        navigator_back();   /* an asset that is not ours: the window goes again */
        ip.win = (void *)0;   /* (its destroy handler leaves a newer page alone) */
        memset(&ip, 0, sizeof ip);
        return -1;
    }
    ip.depth = 0;
    ip.st[0].kind = K_MAIN;
    ip.track = ~0u;   /* the first look makes the cover (the stock disc when nothing plays) */
    ip.fg = 1;
    widget_on(ip.win, EVT_WINDOW_TO_BG, ip_on_background, ip.win);
    widget_on(ip.win, EVT_WINDOW_TO_FG, ip_on_foreground, ip.win);
    widget_on(ip.wheel, EVT_POINTER_DOWN, ip_on_wheel, (void *)0);
    widget_on(ip.wheel, EVT_POINTER_MOVE, ip_on_wheel, (void *)0);
    widget_on(ip.wheel, EVT_POINTER_UP, ip_on_wheel, (void *)0);
    widget_on(ip.wheel, EVT_POINTER_ABORT, ip_on_wheel, (void *)0);
    widget_on(ip.screen, EVT_AFTER_PAINT, ip_on_paint, (void *)0);
    ip.timer = timer_add(ip_first, (void *)0, IP_FIRST_MS);
    return 0;
}
