/* M1+ Music timed cover page: stock's bigcover_page (ui/bigcover_page.bin, opened by Now Playing's 500 ms timer after about ten idle seconds) shows a 320 x 320 img_playcover
 * (scale_auto, nearest neighbour) filled from the shared 264 px /tmp/coverpic.jpg or /tmp/externpic.jpg, so the artwork is enlarged 21 % and reads blocky. This page gets a
 * 320 px picture of its own, made from the original track's art and shown 1:1.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * One hook, bigcover_page_init (0x529a24, tools/pod.py BIGCOVER_INIT): the page's init, run by the navigator's page-init dispatcher whenever the page is built, whoever opened it (the
 * timed open is the only caller of navigator_to("bigcover_page"), 0x53d0ec, but the hook does not depend on that). It runs the stock init to completion and then starts a page-scoped
 * 250 ms timer (bc_tick), registers EVT_DESTROY on the window and EVT_AFTER_PAINT on img_playcover. Never at boot, never in the main loop; the kill switch /mnt/mmc/m1plus-off
 * leaves the stock page untouched.
 * The timer, for the track that plays now (cc_playing; a track is its path's hash):
 *   - waits while the cover source is the embedded art or the folder's (2, 3), not a `.downpic` file (5: stock's picture stays) and not being rewritten by demo, and for the shared worker to be free (cc_build_busy, retried for
 *     BC_TRY_MS), then asks it for the track's art at 320 px (cc_build_add_aspect, the Pod cover pane's transient job without stock's square fit, docs/modules/ipod.md) into BC_TMP;
 *   - polls the job (cc_build_done); a finished job's file is decoded and fitted into the page's own 320 x 320 bitmap (cc_decode_fit: the whole picture, centred over the page's
 *     colour, an exact area average, a pixel copy when its longer side is 320 as the worker makes it) and shown by the cover widget's EVT_AFTER_PAINT, over stock's picture;
 *   - gives up (the stock picture stays) when the worker is busy for BC_TRY_MS, the job runs over BC_RUN_MS, no file comes (no art, art under 320 px, an unreadable or corrupt
 *     picture, a stream) or the decode fails; a new track starts over.
 * Stock keeps drawing its 264 px picture underneath and reloading it when the track changes; ours is drawn only while its track is the playing one (checked on every paint), so a late
 * stock reload or a track change never shows the old track's picture. The destroy cancels the job without waiting (cc_build_stop), removes the timer and the files and frees the
 * bitmap. Every failure leaves the stock page as it is. docs/modules/bigcover.md.
 */
#include "offsets.inc"
#include "stock.h"
#include "covercache.h"
#include "home.h"
#include "common.h"

extern const char *np_cover_file(
    int *
        busy); /* patch/nowplaying.c: demo's cover file of the playing track, NULL for none; busy while demo makes it */

#define BC_SIZE 320 /* the widget's size and the picture's */
#define BC_TICK_MS 250
#define BC_TRY_MS 6000 /* how long a track waits for its cover source and the worker */
#define BC_RUN_MS 10000 /* how long a job may run */
#define BC_TMP "/tmp/m1plus-bigcover.jpg"
#define BC_BG 0xff141414u /* the page's bg_color, #141414: what shows around a non-square picture */
#define BC_IDLE 0 /* the track is known, its job not started */
#define BC_RUN 1 /* the job runs on the shared worker */
#define BC_READY 2 /* the bitmap holds the track's picture */
#define BC_GAVE 3 /* nothing more is tried for this track */

static struct {
    void *win, *img,
        *bmp; /* the page, img_playcover, the 320 x 320 RGBA bitmap (made on first use, freed with the page) */
    unsigned timer, tkey, t1,
        t0; /* the timer, the playing track's key (0 none), time_now_ms of the track's first sight / its job's start */
    int st, worker,
        src; /* BC_*; this page holds the shared job set; the cover source the job (or the picture) was made for */
} bc __attribute__((section(".scratch")));

/* The playing track and its path; the key is the path's hash, never 0, 0 for nothing playing or not a file path. */
static const char *bc_track(unsigned *key) {
    void *rec = cc_playing();
    const char *path = rec ? cc_str(rec, REC_PATH) : "";
    *key = *path == '/' ? cc_fnv(2166136261u, path) | 1u : 0;
    return path;
}

/* The job goes (never waits) and its files; the page's state for the track is cleared. */
static void bc_drop(void) {
    if (bc.worker) cc_build_stop();
    if (bc.worker || bc.st == BC_RUN) unlink(BC_TMP), unlink(BC_TMP ".tmp");
    bc.worker = 0;
    if (bc.st == BC_READY && bc.img) widget_invalidate_force(bc.img, (void *)0); /* stock's picture shows again */
    bc.st = BC_IDLE;
}

/* Stock's picture is the track's own embedded art (source 2) or its folder art (3), which is what the worker searches for, and the source is this track's: stock's parser stores
 * the path it finished a cover for in COVER_PARSED only after it has stored the source, so the source word belongs to the playing track once that buffer equals the track's path
 * (source 1, busy, and a path of the previous track both fail). A `.downpic` file (5, a cached download) is another picture: the page leaves stock's for it. Returns the source, 0 when none. */
static int bc_src(const char *path) {
    int src = *(volatile int *)COVER_SRC;
    if (src != COVER_SRC_EMBEDDED && src != COVER_SRC_FOLDER) return 0;
    return strcmp((const char *)COVER_PARSED, path) ? 0 : src;
}

/* The job's source is still the track's current one. */
static int bc_same(void) {
    unsigned key;
    const char *path = bc_track(&key);
    return key == bc.tkey && bc.src && bc_src(path) == bc.src;
}

/* The finished job: its file into the bitmap. READY, or GAVE when there is no file or it does not decode. */
static void bc_finish(void) {
    unsigned *px;
    int ok = 0;
    cc_build_stop(); /* joins the exited worker and frees the set */
    bc.worker = 0;
    if (!bc_same()) { /* the source changed (or is another track's) meanwhile: this result is for another picture, dropped; the tick asks again */
        unlink(BC_TMP), unlink(BC_TMP ".tmp");
        bc.st = BC_IDLE;
        return;
    }
    if (!access(BC_TMP, F_OK)) {
        if (!bc.bmp) bc.bmp = bitmap_create_ex(BC_SIZE, BC_SIZE, BC_SIZE * 4, BITMAP_RGBA8888);
        px = bc.bmp ? (unsigned *)bitmap_lock_buffer_for_write(bc.bmp) : (unsigned *)0;
        if (px) {
            ok = cc_decode_fit(bc.win, "file://" BC_TMP, 1, BC_SIZE, BC_BG, px);
            bitmap_unlock_buffer(bc.bmp);
        }
    }
    unlink(BC_TMP), unlink(BC_TMP ".tmp");
    bc.st = ok ? BC_READY : BC_GAVE;
    if (ok && bc.img) widget_invalidate_force(bc.img, (void *)0);
}

/* Ask the worker for the track's art. Whether it is running; busy or not yet allowed: nothing is changed (the next tick retries). */
static void bc_start_job(const char *path) {
    int busy, src = bc_src(path);
    if (!src || !np_cover_file(&busy) || busy || cc_build_busy() || !pod_screen_lit()) return;
    unlink(BC_TMP), unlink(BC_TMP ".tmp");
    if (!cc_build_open(1, CC_MISSING)) return;
    if (cc_build_add_aspect(path, BC_TMP, BC_SIZE, src) != 1 || !cc_build_start()) {
        cc_build_stop();
        bc.st = BC_GAVE;
        return;
    }
    bc.worker = 1, bc.st = BC_RUN, bc.src = src, bc.t0 = time_now_ms();
}

/* One step: the track, its job. */
static void bc_step(void) {
    unsigned key, now = time_now_ms();
    const char *path = bc_track(&key);
    if (key != bc.tkey) { /* a new track (or none): the old one's job and picture go */
        bc_drop();
        bc.tkey = key, bc.t0 = bc.t1 = now;
    }
    if (!key || bc.st == BC_GAVE) return;
    if (bc.st ==
        BC_READY) { /* the source moved on (another picture, or stock is making a new one): ours goes, the job is asked again */
        if (bc_same()) return;
        bc_drop();
    }
    if (bc.st == BC_RUN) {
        if (cc_build_done() >= cc_build_total())
            bc_finish();
        else if (now - bc.t0 > BC_RUN_MS) {
            bc_drop();
            bc.st = BC_GAVE;
        }
        return;
    }
    if (now - bc.t1 > BC_TRY_MS)
        bc.st = BC_GAVE;
    else
        bc_start_job(path);
}

static int bc_tick(const void *timer) {
    (void)timer;
    if (!bc.win) return RET_OK; /* not ours any more: a timer that returns RET_OK ends */
    bc_step();
    return RET_REPEAT;
}

/* The cover widget's EVT_AFTER_PAINT: our picture over stock's, while it is the playing track's. */
static int bc_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int r[4] = {0, 0, BC_SIZE, BC_SIZE};
    unsigned key;
    (void)ctx;
    if (!canvas || !bc.win || bc.st != BC_READY || !bc.bmp) return RET_OK;
    bc_track(&key);
    if (key != bc.tkey || !bc_same()) return RET_OK; /* (the track's, and for the source it was made for) */
    canvas_draw_image(canvas, bc.bmp, r, r);
    return RET_OK;
}

/* The page is over (or replaced): the job goes, the timer, the files and the bitmap. */
static void bc_stop(void) {
    bc_drop();
    if (bc.timer) timer_remove(bc.timer);
    if (bc.bmp) bitmap_destroy(bc.bmp);
    memset(&bc, 0, sizeof bc);
}

static int bc_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx != bc.win) return RET_OK; /* an earlier page's end: the new one keeps its state */
    bc.img = (void *)0; /* (the widget is going: no invalidate) */
    bc_stop();
    return RET_OK;
}

static void bc_start(void *win) {
    if (bc.win) {
        bc.img = (void *)0; /* an earlier page that never said it was gone: its widgets may be gone too */
        bc_stop();
    }
    bc.img = widget_lookup(win, "img_playcover", 1);
    if (!bc.img) {
        memset(&bc, 0, sizeof bc);
        return;
    }
    bc.win = win;
    if (!widget_on(win, EVT_DESTROY, bc_on_destroy, win)) {
        memset(&bc, 0, sizeof bc);
        return;
    }
    bc.timer = timer_add(bc_tick, (void *)0, BC_TICK_MS);
    if (!bc.timer ||
        !widget_on(bc.img, EVT_AFTER_PAINT, bc_on_paint,
                   (void *)0)) { /* the page stays stock; the destroy handler finds no window of ours any more */
        if (bc.timer) timer_remove(bc.timer);
        memset(&bc, 0, sizeof bc);
        return;
    }
    bc_step();
}

/* The hook (tools/pod.py BIGCOVER_INIT): stock first, then ours. */
int m1plus_bigcover_init(void *win, void *ctx) {
    int ret = stock_bigcover_init_trampoline(win, ctx);
    if (ret == RET_OK && win && access(KILL_SD, F_OK) != 0) bc_start(win);
    return ret;
}
