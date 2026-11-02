/* M1+ Music Home: the background cover build and its progress line (docs/modules/homecover.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * The Home instance of the menu builds the album covers that have no cache file (neither a picture nor the "no art" marker), or every cover
 * again while Settings > Library > Rebuild Covers is requested (REBUILD_FILE, CC_REBUILD, the line reads "Rebuilding covers"), with the
 * shared worker of patch/covercache.c, as the Albums page does (patch/albums.c "background cache build"), and shows a plain line at the
 * top of the page while it runs: "Preparing covers 120/840" (the key "Preparing covers" and the count, built here). The line is the
 * asset's hidden, insensitive label pod_cover_prog (tools/pod_ui.py); showing it moves the list down by HC_H (the list keeps its
 * place, menu_arrange clamps the offset), hiding it moves the list back. Nothing is shown when nothing is missing.
 *
 * No hook of its own: patch/home.c calls homecover_start from home_menu_opened beside recent_start. Everything runs from the window's
 * events and page-scoped timers: HC_START_MS after the page is in front a one-shot opens a CC_MISSING set (refused while Cover Flow, the
 * Albums page or anything else holds the worker: then nothing happens until the next foreground) and scans the albums in steps of
 * HC_BATCH (HC_SCAN_MS apart), the worker starts after the last step, a poll every HC_POLL_MS updates the line and, when the done
 * counter advanced, lets the Recently Played tiles that showed the placeholder try their file again (recent_refresh). The set is
 * stopped when the page goes to the background or is destroyed (only a set this page owns) and offered again at the next foreground.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "covercache.h"
#include "durations.h"
#include "common.h"
#include "i18n.h"

#define I(w, off) (*(int *)((char *)(w) + (off)))
#define P(w, off) (*(void **)((char *)(w) + (off)))

#define HC_START_MS \
    RC_RESOLVE_MS /* after the page is in front: nothing is scanned while the menu opens and settles (Recently Played's album list load waits as long) */
#define HC_POLL_MS 500
#define HC_BATCH 64 /* albums stat'ed per scan step */
#define HC_SCAN_MS 20 /* between steps: input is served in between */

static struct {
    void *win, *lab, *lv;
    unsigned timer; /* the one-shot start, the scan steps, then the poll */
    int fg, own, scanning, shown, done;
    int rebuild; /* the set is a CC_REBUILD one (REBUILD_FILE existed when the scan began) */
    void *albums; /* the library's albums (cc_albums), held for the scan only */
    unsigned *order;
    unsigned count, cur;
    /* the song length pass (after the covers): len 1 = reading the library's songs, 2 = the worker measures */
    void *songs;
    unsigned lcur, lcount, lsaved;
    int len, lmore, lerr;
} hc __attribute__((section(".scratch")));

#define HC_LBATCH 1024 /* songs looked up per step (in memory) */
#define HC_LSTAT 64 /* files stat'ed per step: the songs the table lacks */
#define HC_LSAVE 500 /* measured songs between two saves of the table */
static unsigned hl_clean __attribute__((section(".scratch"))),
    hl_epoch __attribute__((section(
        ".scratch"))); /* albums + 1 of a pass that found every song in the table (and the clears then): not read again until that changes */

/* The line shown or hidden (visible and sensitive together) and the list below it made room for. */
static void hc_show(int on) {
    static const char *const kids[] = {"pod_scrollview", "scroll_bar_m"};
    int h = WIN_H - 2 * HOME_PAD - (on ? HC_H : 0), i;
    if (!hc.win || !hc.lab || !hc.lv || on == hc.shown) return;
    hc.shown = on;
    widget_set_visible(hc.lab, on, 0);
    widget_set_sensitive(hc.lab, on);
    widget_move(hc.lv, 0, HOME_PAD + (on ? HC_H : 0));
    widget_resize(hc.lv, SCREEN_W, h);
    for (i = 0; i < 2; i++) {
        void *c = widget_lookup(hc.win, kids[i], 1);
        int w = c ? widget_get_prop_int(c, "w", 0) : 0;
        if (w > 0) widget_resize(c, w, h);
    }
    menu_arrange(hc.win, 0); /* the scroll offset is clamped to the new height */
}

static void hc_text(void) {
    char text[64];
    snprintf(text, sizeof text, "%s %d/%d",
             TR(hc.len       ? "Measuring tracks"
                : hc.rebuild ? "Rebuilding covers"
                             : "Preparing covers"),
             cc_build_done(), cc_build_total());
    widget_set_text_utf8(hc.lab, text);
    widget_invalidate_force(hc.lab, (void *)0);
}

static void hc_free_scan(void) {
    if (hc.albums) deque_destroy(hc.albums);
    if (hc.songs) deque_destroy(hc.songs);
    hc.songs = (void *)0;
    free(hc.order);
    hc.albums = (void *)0;
    hc.order = (unsigned *)0;
    hc.scanning = 0;
}

/* The durations the worker finished since the last save go into the table (merged, written atomically). */
static void hc_dur_save(void) {
    int done = cc_build_done(), i;
    unsigned n = 0;
    dur_ent_t *e;
    if (hc.len != 2 || done <= (int)hc.lsaved) return;
    e = calloc(1, ((unsigned)(done - (int)hc.lsaved) * sizeof *e));
    if (!e) {
        hc.lerr = 1;
        return;
    }
    for (i = (int)hc.lsaved; i < done; i++)
        if (cc_build_dur(i, &e[n].key, &e[n].size, &e[n].sec)) n++;
    if (dur_merge(e, n)) hc.lerr = 1;
    free(e);
    hc.lsaved = (unsigned)done;
}

/* The page's build released: the timer removed, what was measured saved, a running worker cancelled and joined (bounded by one album's art or one file), the line hidden. */
static void hc_end(void) {
    if (hc.timer) timer_remove(hc.timer);
    hc.timer = 0;
    hc_free_scan();
    hc_dur_save();
    if (hc.own) cc_build_stop();
    hc.own = 0;
    if (hc.len) dur_release();
    hc.len = 0;
    hc_show(0);
}

static int hc_on_dscan(const void *unused);

/* The song length pass: the library's songs are read (one stock query, as the covers' albums are), looked up in the table in steps, the ones it lacks queued for the worker. */
static void hc_dur_begin(void) {
    unsigned cap;
    if (!hc.win || !hc.fg || hc.own || hc.len || hc.timer || cc_build_busy() || !pod_card_mounted() ||
        (hl_clean == hc.count + 1 && hl_epoch == dur_epoch()))
        return;
    hc.songs = cc_songs();
    hc.lcount = hc.songs ? deque_size(hc.songs) : 0;
    cap = hc.lcount < CC_MAX_LEN_JOBS ? hc.lcount : CC_MAX_LEN_JOBS;
    if (!cap || !cc_build_open(cap, CC_DURATIONS)) {
        hc_free_scan();
        return;
    }
    dur_acquire();
    dur_pass_begin();
    hc.len = 1, hc.own = 1, hc.lcur = hc.lsaved = 0, hc.lmore = hc.lerr = 0;
    hc.timer = timer_add(hc_on_dscan, (void *)0, HC_SCAN_MS);
    if (!hc.timer) hc_end();
}

static int hc_on_dpoll(const void *unused) {
    int done, more;
    (void)unused;
    hc.timer = 0;
    if (!hc.win || !hc.own || hc.len != 2) return RET_OK;
    done = cc_build_done();
    if (done != hc.done) {
        hc.done = done;
        hc_text();
        if (done - (int)hc.lsaved >= HC_LSAVE) hc_dur_save();
    }
    if (done >= cc_build_total()) {
        hc_dur_save();
        more = hc.lmore && !hc.lerr; /* more songs than one set holds: another pass */
        if (!hc.lmore && !hc.lerr) hl_clean = hc.count + 1, hl_epoch = dur_epoch();
        hc_end();
        if (more) hc_dur_begin();
        return RET_OK;
    }
    hc.timer = timer_add(hc_on_dpoll, (void *)0, HC_POLL_MS);
    if (!hc.timer) hc_end(); /* no way to watch it: what was measured is saved */
    return RET_OK;
}

static int hc_on_dscan(const void *unused) {
    unsigned stop, stat = 0;
    (void)unused;
    hc.timer = 0;
    if (!hc.win || !hc.fg || hc.len != 1 || !hc.songs) return RET_OK;
    stop = hc.lcur + HC_LBATCH;
    for (; hc.lcur < hc.lcount && hc.lcur < stop && stat < HC_LSTAT; hc.lcur++) {
        void *r = deque_at(hc.songs, hc.lcur);
        const char *path = (const char *)P(r, REC_PATH);
        long size;
        if (!path || !*path) continue;
        dur_pass_seen(path);
        if (I(r, REC_CUE_END) > I(r, REC_CUE_START) || dur_has(path) || hc.lmore)
            continue; /* nothing to measure, or the set is full */
        ++stat;
        size = cc_file_size(path);
        if (size > 0 && size <= 0x7fffffff && cc_build_add_dur(path, dur_key(path), (unsigned)size) < 0) hc.lmore = 1;
    }
    if (hc.lcur < hc.lcount) {
        hc.timer = timer_add(hc_on_dscan, (void *)0, HC_SCAN_MS);
        if (!hc.timer) hc_end();
        return RET_OK;
    }
    hc_free_scan();
    dur_pass_end(); /* the entries of files no song names any more */
    if (!cc_build_total()) { /* every song is in the table */
        if (!hc.lmore) hl_clean = hc.count + 1, hl_epoch = dur_epoch();
        hc_end();
        return RET_OK;
    }
    if (!cc_build_start()) {
        hc.own = 0; /* the set is freed */
        hc_end();
        return RET_OK;
    }
    hc.len = 2, hc.done = 0;
    hc_show(1);
    hc_text();
    hc.timer = timer_add(hc_on_dpoll, (void *)0, HC_POLL_MS);
    if (!hc.timer) hc_end();
    return RET_OK;
}

static int hc_on_poll(const void *unused) {
    int done;
    (void)unused;
    hc.timer = 0;
    if (!hc.win || !hc.own) return RET_OK;
    done = cc_build_done();
    if (done != hc.done) {
        hc.done = done;
        hc_text();
        recent_refresh(); /* the tiles that found no file try again */
    }
    if (done >= cc_build_total()) {
        if (hc.rebuild) unlink(REBUILD_FILE); /* the request is done only when every album was extracted again */
        hc_end();
        hc_dur_begin(); /* then the songs' durations */
        return RET_OK;
    }
    hc.timer = timer_add(hc_on_poll, (void *)0, HC_POLL_MS);
    if (!hc.timer) hc_end(); /* no way to watch it: stop, the covers built so far stay */
    return RET_OK;
}

/* The scan in steps (as al_on_build_start): the first call opens the set, every call considers HC_BATCH albums in the list's order and,
 * while more remains, re-arms itself; the worker starts only after the last step. */
/* The scan's order: the list's (cc_album_order, NULL = as stored), with the Recently Played albums moved to the front, most recent first,
 * so the shelf's covers are made first (the rest keep their order). No memory for an order: the list's own. */
static unsigned *hc_order(void *albums, const unsigned *rows, int shelf) {
    unsigned n = deque_size(albums), *v = cc_album_order(albums), i, p, k;
    int s;
    if (!shelf) return v;
    if (!v) {
        v = calloc(n, sizeof *v);
        if (!v) return v;
        for (i = 0; i < n; ++i) v[i] = i;
    }
    for (s = 0, k = 0; s < shelf; ++s) {
        for (p = k; p < n && v[p] != rows[s]; ++p) {
        }
        if (p == n) continue; /* already moved (two entries, one row) */
        for (; p > k; --p) v[p] = v[p - 1];
        v[k++] = rows[s];
    }
    return v;
}

static int hc_on_start(const void *unused) {
    unsigned cap, rows[SH_TILES];
    int shelf;
    (void)unused;
    hc.timer = 0;
    if (!hc.win || !hc.fg) return RET_OK;
    if (!hc.scanning) {
        if (hc.own || cc_build_busy())
            return RET_OK; /* the worker is held by someone else: the next foreground retries */
        hc.albums = cc_albums();
        /* Recently Played: a stale cover key names a file the build never makes; its albums are queued first */
        shelf = recent_rekey(hc.albums, rows);
        hc.count = hc.albums ? deque_size(hc.albums) : 0;
        cap = hc.count < CC_MAX_JOBS ? hc.count : CC_MAX_JOBS;
        hc.rebuild = !access(REBUILD_FILE,
                             F_OK); /* Settings > Library > Rebuild Covers asked: every album, existing files too */
        if (!cap || !cc_build_open(cap, hc.rebuild ? CC_REBUILD : CC_MISSING)) {
            hc_free_scan();
            return RET_OK;
        }
        hc.order = hc_order(hc.albums, rows, shelf);
        hc.own = hc.scanning = 1;
        hc.cur = 0;
    }
    if (!cc_build_near_step(hc.albums, hc.order, 0, &hc.cur, HC_BATCH)) {
        hc.timer = timer_add(hc_on_start, (void *)0, HC_SCAN_MS);
        if (!hc.timer) hc_end(); /* no way to continue: nothing built, the next foreground retries */
        return RET_OK;
    }
    hc_free_scan(); /* the jobs hold their own copies of the paths */
    if (hc.rebuild && !cc_build_total())
        unlink(REBUILD_FILE); /* nothing to extract (no album has a track): nothing to wait for */
    if (!cc_build_start()) { /* nothing missing, no card, no space, no thread: the set is already freed */
        hc.own = 0;
        hc_dur_begin(); /* the covers are as built as they will be: the songs' durations */
        return RET_OK;
    }
    hc.done = 0;
    hc_show(1);
    hc_text();
    hc.timer = timer_add(hc_on_poll, (void *)0, HC_POLL_MS);
    if (!hc.timer) hc_end();
    return RET_OK;
}

static void hc_later(void) {
    if (hc.win && hc.fg && !hc.own && !hc.timer) hc.timer = timer_add(hc_on_start, (void *)0, HC_START_MS);
}

static int hc_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx != hc.win) return RET_OK; /* an earlier window's end leaves the new one alone */
    hc_end();
    memset(&hc, 0, sizeof hc);
    return RET_OK;
}

/* The menu goes away: the worker stops, so it never runs beside Cover Flow's or the Albums page's own build. */
static int hc_on_background(void *ctx, void *e) {
    (void)e;
    if (!hc.win || ctx != hc.win) return RET_OK;
    hc.fg = 0;
    hc_end();
    return RET_OK;
}

static int hc_on_foreground(void *ctx, void *e) {
    (void)e;
    if (!hc.win || ctx != hc.win) return RET_OK;
    hc.fg = 1;
    hc_later();
    return RET_OK;
}

/* The Home instance of the menu is up (patch/home.c, after the list took the whole window). */
void homecover_start(void *win) {
    if (!win || home_off()) return;
    if (hc.win) hc_on_destroy(hc.win, (void *)0); /* an earlier window that never said it was gone */
    memset(&hc, 0, sizeof hc);
    hc.win = win;
    hc.lab = widget_lookup(win, "pod_cover_prog", 1);
    hc.lv = widget_lookup(win, "pod_listview", 1);
    hc.fg = 1;
    if (!hc.lab || !hc.lv || !widget_on(win, EVT_DESTROY, hc_on_destroy, win) ||
        !widget_on(win, EVT_WINDOW_TO_BG, hc_on_background, win) ||
        !widget_on(win, EVT_WINDOW_TO_FG, hc_on_foreground, win)) {
        hc.win = (void *)0; /* a handler that was registered finds no window of ours any more */
        return;
    }
    hc_later();
    if (!hc.timer) hc.win = (void *)0;
}

/* ---------------------------------------------------------------------------
 * Settings > Developer > Clear Cover Cache (after its confirm): every file in ART_DIR is removed (Cover Flow's position is outside it):
 * the r<key>-168.jpg pictures, their empty no-art markers, .tmp leftovers and the stale old-format files. HC_CLEAR_N unlinks a tick on a
 * one-shot that re-arms itself (the directory handle is kept between ticks), so a big cache never blocks input; the timer needs no page, it
 * ends with the last file. A pending Rebuild Covers request goes too (every cover is missing now, the next Home build makes them all).
 */
#define HC_CLEAR_N 32
#define HC_CLEAR_MS 20
static struct {
    void *dir;
    unsigned timer;
} cl __attribute__((section(".scratch")));

static void cp_recount(void);

static void cl_end(int done) {
    if (cl.dir) closedir(cl.dir);
    cl.dir = (void *)0;
    cl.timer = 0;
    if (done) {
        pod_toast(TR("Cover cache cleared"));
        cp_recount(); /* a Cover Cache page in front counts again (nothing happens when it is not open) */
    }
}

static int cl_tick(const void *unused) {
    int n = 0;
    char *ent;
    (void)unused;
    cl.timer = 0;
    if (cc_build_busy()) { /* a build started meanwhile: leave the rest alone */
        cl_end(0);
        return RET_OK;
    }
    while (n < HC_CLEAR_N && (ent = readdir(cl.dir)) != (char *)0) {
        char path[300]; /* (d_name is at most 255 bytes) */
        const char *name = ent + 11; /* struct dirent: d_type at 10, d_name at 11 */
        if (ent[10] != 8) continue;
        snprintf(path, sizeof path, ART_DIR "/%s", name);
        unlink(path);
        ++n;
    }
    if (n == HC_CLEAR_N) {
        cl.timer = timer_add(cl_tick, (void *)0, HC_CLEAR_MS);
        if (cl.timer) return RET_OK;
    }
    cl_end(n < HC_CLEAR_N); /* the listing ended (a refused timer stops quietly, the rest stays) */
    return RET_OK;
}

/* 1 once the clearing is under way (or already was), 0 when the cover worker is busy: nothing is touched. */
int homecover_clear(void) {
    if (cl.timer) return 1;
    if (cc_build_busy()) return 0;
    unlink(REBUILD_FILE);
    cl.dir = opendir(ART_DIR);
    if (!cl.dir) {
        pod_toast(TR("Cover cache cleared")); /* no cache folder: nothing to clear */
        return 1;
    }
    cl.timer = timer_add(cl_tick, (void *)0, HC_CLEAR_MS);
    if (!cl.timer) cl_end(0);
    return 1;
}

/* ---------------------------------------------------------------------------
 * Settings > Developer > Cover Cache (docs/modules/settings.md "Cover Cache"): a status page over the cache folder. Nothing runs unless the page
 * is open. At open (and after a clear, and on coming back to the front) the folder is counted in bounded steps of CP_N entries on a one-shot
 * that re-arms itself: the pictures, the empty no-art markers and the old files, then the library's albums (cc_albums, once) are checked
 * against the CC_MISSING rule, CP_N a tick. Until a count is known the page shows an ellipsis. A 500 ms poll refreshes the page when the Status
 * line changed. All timers stop on background and destroy.
 */
#define CP_N 64
#define CP_MS 20
#define CP_POLL_MS 500
extern void pod_page_refresh(int index); /* patch/m1plus.c: the page's values are read again */
enum { CP_DIR = 1, CP_ALBUMS, CP_DONE };

static struct {
    void *win, *dir, *albums;
    unsigned timer, poll;
    int fg, phase, page; /* page: the Cover Cache page's index (patch/m1plus.c) */
    unsigned cur, n_albums, covers, noart, missing, old, size;
    unsigned *order; /* cc_album_order of the held album list: the scan walks display positions */
    unsigned short *im,
        *in; /* the albums with no file (Missing) and with an empty marker (No art): display positions, at most CC_MAX_JOBS, for the lists */
    unsigned nim, nin;
    char last[64]; /* the Status text the page shows now */
} cp __attribute__((section(".scratch")));

/* r<8 hex>-168.jpg exactly: the current cache name; anything else in the folder is an old or temporary file. */
static int cp_is_pic(const char *name) {
    int i;
    if (name[0] != 'r') return 0;
    for (i = 1; i <= 8; ++i)
        if (!((name[i] >= '0' && name[i] <= '9') || (name[i] >= 'a' && name[i] <= 'f'))) return 0;
    return !strcmp(name + 9, "-168.jpg");
}

static void cp_stop_timers(void) {
    if (cp.timer) timer_remove(cp.timer);
    if (cp.poll) timer_remove(cp.poll);
    cp.timer = cp.poll = 0;
    if (cp.dir) closedir(cp.dir);
    cp.dir = (void *)0;
    if (cp.albums) deque_destroy(cp.albums);
    cp.albums = (void *)0;
    free(cp.order);
    cp.order = (unsigned *)0;
}

static void cp_free_idx(void) {
    free(cp.im);
    free(cp.in);
    cp.im = cp.in = (unsigned short *)0;
    cp.nim = cp.nin = 0;
}

static int cp_tick(const void *unused) {
    int n = 0;
    (void)unused;
    cp.timer = 0;
    if (!cp.win || !cp.fg) return RET_OK;
    if (cp.phase == CP_DIR) {
        char *ent;
        while (n < CP_N && cp.dir && (ent = readdir(cp.dir)) != (char *)0) {
            const char *name = ent + 11; /* struct dirent: d_type at 10, d_name at 11 */
            char path[300];
            long size;
            if (ent[10] != 8) continue;
            ++n;
            snprintf(path, sizeof path, ART_DIR "/%s", name);
            size = cc_file_size(path);
            if (size < 0) size = 0;
            cp.size += (unsigned)size;
            if (!cp_is_pic(name))
                ++cp.old;
            else if (size)
                ++cp.covers;
            else
                ++cp.noart;
        }
        if (n < CP_N) { /* the listing ended (or no folder) */
            if (cp.dir) closedir(cp.dir);
            cp.dir = (void *)0;
            cp.phase = CP_ALBUMS;
            cp.albums = cc_albums();
            cp.n_albums = cp.albums ? deque_size(cp.albums) : 0;
            cp.order = cp.albums ? cc_album_order(cp.albums) : (unsigned *)0;
            cp.im = calloc(CC_MAX_JOBS, sizeof *cp.im);
            cp.in = calloc(CC_MAX_JOBS, sizeof *cp.in);
            cp.cur = 0;
            pod_page_refresh(cp.page);
        }
    } else if (cp.phase == CP_ALBUMS) {
        for (; cp.cur < cp.n_albums && n < CP_N; ++cp.cur, ++n) {
            void *r = cc_row(cp.albums, cp.order, cp.cur);
            unsigned key = cc_album_key(r);
            char path[64];
            const char *track = cc_str(r, REC_PATH);
            if (!track[0] || !key) continue;
            cc_path(path, sizeof path, key, "");
            if (access(path, F_OK)) { /* cc_build_add's CC_MISSING rule */
                ++cp.missing;
                if (cp.im && cp.nim < CC_MAX_JOBS) cp.im[cp.nim++] = (unsigned short)cp.cur;
            } else if (!cc_file_size(path)) { /* the empty no-art marker */
                if (cp.in && cp.nin < CC_MAX_JOBS) cp.in[cp.nin++] = (unsigned short)cp.cur;
            }
        }
        if (cp.cur >= cp.n_albums) {
            if (cp.albums) deque_destroy(cp.albums);
            cp.albums = (void *)0;
            cp.phase = CP_DONE;
            pod_page_refresh(cp.page);
        }
    }
    if (cp.phase != CP_DONE) cp.timer = timer_add(cp_tick, (void *)0, CP_MS);
    return RET_OK;
}

static void cp_status(char *buf, unsigned n) {
    int total = cc_build_total();
    if (cl.timer)
        snprintf(buf, n, "%s", TR("Clearing"));
    else if (hc.own)
        snprintf(buf, n, "%s %d/%d",
                 TR(hc.len       ? "Measuring tracks"
                    : hc.rebuild ? "Rebuilding"
                                 : "Preparing"),
                 cc_build_done(), total);
    else if (cc_build_busy()) {
        if (total > 0)
            snprintf(buf, n, "%s %d/%d", TR("Building"), cc_build_done(), total);
        else
            snprintf(buf, n, "%s", TR("Building"));
    } else
        snprintf(buf, n, "%s", TR(access(REBUILD_FILE, F_OK) == 0 ? "Rebuild requested" : "Idle"));
}

static int cp_poll(const void *unused) {
    char s[64];
    (void)unused;
    cp.poll = 0;
    if (!cp.win || !cp.fg) return RET_OK;
    cp_status(s, sizeof s);
    if (strcmp(s, cp.last)) {
        memcpy(cp.last, s, sizeof cp.last);
        pod_page_refresh(cp.page);
    }
    cp.poll = timer_add(cp_poll, (void *)0, CP_POLL_MS);
    return RET_OK;
}

/* The counting starts again from nothing (the page opened, came back to the front, or a clear finished). */
static void cp_restart(void) {
    cp_stop_timers();
    cp_free_idx();
    cp.phase = CP_DIR;
    cp.cur = cp.n_albums = cp.covers = cp.noart = cp.missing = cp.old = cp.size = 0;
    cp.dir = opendir(ART_DIR); /* none: the first tick moves on (everything is missing) */
    cp.timer = timer_add(cp_tick, (void *)0, CP_MS);
    cp.poll = timer_add(cp_poll, (void *)0, CP_POLL_MS);
    cp_status(cp.last, sizeof cp.last);
    pod_page_refresh(cp.page);
}

static void cp_recount(void) {
    if (cp.win && cp.fg) cp_restart();
}

static int cp_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx != cp.win) return RET_OK;
    cp_stop_timers();
    cp_free_idx();
    memset(&cp, 0, sizeof cp);
    return RET_OK;
}

static int cp_on_background(void *ctx, void *e) {
    (void)e;
    if (!cp.win || ctx != cp.win) return RET_OK;
    cp.fg = 0;
    cp_stop_timers();
    return RET_OK;
}

static int cp_on_foreground(void *ctx, void *e) {
    (void)e;
    if (!cp.win || ctx != cp.win) return RET_OK;
    cp.fg = 1;
    cp_restart();
    return RET_OK;
}

/* The Cover Cache page's window is up (patch/m1plus.c open_page): bind its events and start counting. */
void homecover_cache_open(void *win, int page) {
    if (cp.win) cp_on_destroy(cp.win, (void *)0);
    memset(&cp, 0, sizeof cp);
    cp.win = win;
    cp.page = page;
    cp.fg = 1;
    if (!widget_on(win, EVT_DESTROY, cp_on_destroy, win) || !widget_on(win, EVT_WINDOW_TO_BG, cp_on_background, win) ||
        !widget_on(win, EVT_WINDOW_TO_FG, cp_on_foreground, win)) {
        memset(&cp, 0, sizeof cp); /* the page shows its ellipses: nothing counted */
        return;
    }
    cp_restart();
}

/* A row's value (idx 0 Albums, 1 Covers, 2 No art, 3 Missing, 4 Old files, 5 Size, 6 Status); an ellipsis until counted. */
void homecover_stat(int idx, char *buf, unsigned n) {
    unsigned v;
    if (idx == 6) {
        cp_status(buf, n);
        return;
    }
    if (!cp.win || cp.phase < (idx == 0 || idx == 3 ? CP_DONE : CP_ALBUMS)) {
        snprintf(buf, n, "\xe2\x80\xa6");
        return;
    }
    if (idx == 5) {
        v = (cp.size / 1024 * 10 + 512) / 1024; /* tenths of a MB */
        if (v < 100)
            snprintf(buf, n, "%u.%u MB", v / 10, v % 10);
        else
            snprintf(buf, n, "%u MB", v / 10);
        return;
    }
    v = idx == 0 ? cp.n_albums : idx == 1 ? cp.covers : idx == 2 ? cp.noart : idx == 3 ? cp.missing : cp.old;
    snprintf(buf, n, "%u", v);
}

/* The No art (idx 2) and Missing (idx 3) rows open a list when counted and not zero. */
int homecover_tappable(int idx) { return cp.win && cp.phase == CP_DONE && (idx == 2 ? cp.noart : cp.missing) > 0; }

/* The list of those albums (patch/covlist.c); -1 when the row is not tappable. */
int homecover_list_open(int idx) {
    if (!homecover_tappable(idx)) return -1;
    return covlist_open(idx == 3, idx == 3 ? cp.im : cp.in, idx == 3 ? cp.nim : cp.nin);
}
