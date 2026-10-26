/* M1 Pod Now Playing: the stock playing_page (ui/playing_page.bin, tools/mod_nowplaying.py) gets a cover-tinted
 * background, rounded cover corners that match it, and a remaining-time label that the assets cannot give it.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * One hook, playing_page_init (0x53d1e4): the page's init, run when Now Playing is built, never at boot or in the
 * main loop. It runs the stock function to completion and then, unless the kill switch /mnt/mmc/m1pod-off exists,
 * starts a page-scoped 500 ms timer (np_tick) and registers EVT_DESTROY on the window, which removes the timer.
 * The timer does two things and nothing else:
 *   - the tint: demo writes the track's cover to /tmp/coverpic.jpg or /tmp/externpic.jpg (parseplaycover_thd,
 *     source type word 0x97cad8: 2 and 3/5; 1 while it works); when the file changes (a hash of its bytes) the
 *     picture is decoded by the stock loader, box-averaged to one colour (patch/covercache.c) and np_tone turns that
 *     into a dark, slightly desaturated tone that is set as the window's bg_color (widget_set_style); a static
 *     gradient image over it (ui/playing_page.bin, np_tint.png) fades it to black towards the bottom. No cover, or a
 *     source that is not a JPEG file: the neutral dark tone.
 *   - the remaining time: label_playlen carries the total (stock rewrites it on every tick); np_remaining, a label
 *     of the asset, shows "-mm:ss" from get_playtimeandlength while that call gives a length, and label_playlen
 *     shows again whenever it does not.
 * The cover is square (AWTK cannot clip an image); its four corners are painted over in the colour the window has
 * there (the tone under the gradient), anti-aliased, from the cover widget's own EVT_AFTER_PAINT: 4 x 12 x 12 pixels
 * of a table np_corner_init computes once, a few dozen canvas_fill_rect calls, and only when the cover repaints.
 * Every failure (kill switch, a widget of the asset missing, no timer, an unreadable file, an undecodable picture)
 * leaves the stock page as it is, square corners included. docs/architecture.md section 8a.
 */
#include "offsets.inc"
#include "stock.h"
#include "covercache.h"

#define KILL_FILE "/mnt/mmc/m1pod-off"
#define F_OK 0

static struct {
    void *win, *rem, *tot; /* the window, np_remaining (ours), label_playlen (stock) */
    unsigned timer;        /* the repeating np_tick timer */
    unsigned key;          /* what the colour was last made from: 0 nothing yet, NP_KEY_NEUTRAL, or a file's hash */
    unsigned color;        /* the window's bg_color as 0x00BBGGRR (what the corners are painted from) */
    int shown;             /* the seconds np_remaining shows, -1 none */
    int own;               /* 1: np_remaining is the visible label, 0: label_playlen is */
    unsigned char corner[NP_ART_R * NP_ART_R]; /* the top left corner's coverage outside the arc, 0..255 */
} np __attribute__((section(".scratch")));

/* A dark, slightly desaturated tone of the cover's average colour (r, g, b bytes), as a color_t word
 * (0xAABBGGRR, alpha ff). Value: NP_V_MIN + v * (NP_V_MAX - NP_V_MIN) / 255 for the brightest channel v; every
 * channel keeps NP_SAT_NUM / NP_SAT_DEN of its distance from v (a grey stays grey). A black cover is the neutral
 * tone. With NP_V_MAX 192 the white title and the #AAAAAA lines keep 4.5:1 over the gradient (test/pod/nowplaying.py). */
__attribute__((noinline)) unsigned np_tone(unsigned r, unsigned g, unsigned b) {
    unsigned v = r > g ? r : g, c[3], i, vt;
    if (b > v) v = b;
    if (!v) return NP_NEUTRAL;
    c[0] = r, c[1] = g, c[2] = b;
    vt = NP_V_MIN + v * (NP_V_MAX - NP_V_MIN) / 255;
    for (i = 0; i < 3; ++i) c[i] = vt - vt * NP_SAT_NUM * (v - c[i]) / (NP_SAT_DEN * v);
    return 0xff000000u | c[0] | c[1] << 8 | c[2] << 16;
}

/* "-mm:ss", or "-hh:mm:ss" from an hour on: the seconds left, as stock's own clock (toolsTimeItoa) prints
 * the elapsed time. A position past the end shows -00:00. */
__attribute__((noinline)) void np_format_remaining(char *out, unsigned size, int pos, int len) {
    int left = len - pos;
    if (left < 0) left = 0;
    if (left >= 3600) snprintf(out, size, "-%02d:%02d:%02d", left / 3600, left / 60 % 60, left % 60);
    else snprintf(out, size, "-%02d:%02d", left / 60, left % 60);
}

/* The gradient's alpha on window row y (np_tint.png: black, NP_ALPHA_TOP at the first row to NP_ALPHA_BOTTOM at the last). */
__attribute__((noinline)) unsigned np_alpha(unsigned y) {
    return NP_ALPHA_TOP + ((NP_ALPHA_BOTTOM - NP_ALPHA_TOP) * y + (NP_WIN_H - 1) / 2) / (NP_WIN_H - 1);
}

/* color (0x..BBGGRR) as the window shows it on row y: under the black gradient. */
__attribute__((noinline)) unsigned np_shade(unsigned color, unsigned y) {
    unsigned keep = 255 - np_alpha(y);
    return (color & 255) * keep / 255 | (color >> 8 & 255) * keep / 255 << 8 | (color >> 16 & 255) * keep / 255 << 16;
}

/* The coverage of the area outside a quarter circle of radius NP_ART_R in the corner square of NP_ART_R pixels
 * (the circle's centre at the square's inner corner), 0..255: each pixel is sampled 8 x 8 times. The same numbers
 * as the PNG mask of the earlier builds (test/pod/nowplaying.py). */
__attribute__((noinline)) void np_corner_init(void) {
    unsigned x, y, i, j, n, c = 2 * 8 * NP_ART_R;
    for (y = 0; y < NP_ART_R; ++y)
        for (x = 0; x < NP_ART_R; ++x) {
            for (n = 0, i = 0; i < 8; ++i)
                for (j = 0; j < 8; ++j) {
                    int dx = (int)(2 * (x * 8 + i) + 1) - (int)c, dy = (int)(2 * (y * 8 + j) + 1) - (int)c;
                    n += (unsigned)(dx * dx + dy * dy) > c * c;
                }
            np.corner[y * NP_ART_R + x] = (unsigned char)((n * 255 + 32) / 64);
        }
}

/* The cover widget's EVT_AFTER_PAINT: the four corners, in widget coordinates (the stock paint only translates). */
static int np_on_art_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    unsigned k, x, y;
    (void)ctx;
    if (!canvas || !np.win) return RET_OK;
    for (k = 0; k < 4; ++k)
        for (y = 0; y < NP_ART_R; ++y) {
            unsigned ly = k & 2 ? NP_ART - 1 - y : y, shade = np_shade(np.color, NP_ART_Y + ly);
            for (x = 0; x < NP_ART_R; ++x) {
                unsigned a = np.corner[y * NP_ART_R + x];
                if (!a) continue;
                canvas_set_fill_color(canvas, shade | a << 24);
                canvas_fill_rect(canvas, k & 1 ? NP_ART - 1 - x : x, ly, 1, 1);
            }
        }
    return RET_OK;
}

/* FNV-1a over the file's bytes (at most NP_HASH_MAX of them) and its length, never 0; 0 when it cannot be read or is
 * empty. */
__attribute__((noinline)) unsigned np_file_key(const char *path) {
    unsigned char buf[512];
    unsigned h = 2166136261u, total = 0, n, i;
    void *f = fopen(path, "rb");
    if (!f) return 0;
    while (total < NP_HASH_MAX && (n = fread(buf, 1, sizeof buf, f)) > 0) {
        for (i = 0; i < n; ++i) h = (h ^ buf[i]) * 16777619u;
        total += n;
    }
    fclose(f);
    h = (h ^ total) * 16777619u;
    return total ? h | !h : 0;
}

static void np_set_color(unsigned color) {
    unsigned v[4]; /* value_t: type at 0, the uint32 at 8 */
    memset(v, 0, sizeof v);
    value_set_uint32(v, color);
    if (widget_set_style(np.win, "normal:bg_color", v) != RET_OK) return;
    np.color = color & 0xffffff;
    widget_invalidate_force(np.win, (void *)0);
}

/* The cover file of the source type, or NULL for a source with no JPEG file; busy is set while demo is still making it. */
static const char *np_cover_file(int *busy) {
    int src = *(volatile int *)COVER_SRC;
    *busy = src == COVER_SRC_BUSY;
    if (src == COVER_SRC_EMBEDDED) return "/tmp/coverpic.jpg";
    if (src == COVER_SRC_FOLDER || src == COVER_SRC_CACHE) return "/tmp/externpic.jpg";
    return (const char *)0;
}

static void np_cover(void) {
    int busy;
    const char *path = np_cover_file(&busy);
    unsigned key, px;
    char url[40];
    if (busy) return; /* the file is being replaced: keep the colour */
    if (!path) { /* no picture file: the neutral tone, once */
        if (np.key != NP_KEY_NEUTRAL) np.key = NP_KEY_NEUTRAL, np_set_color(NP_NEUTRAL);
        return;
    }
    key = np_file_key(path);
    if (!key || key == np.key) return; /* unreadable: try again next tick; unchanged: nothing to do */
    if (*(volatile int *)COVER_SRC == COVER_SRC_BUSY) return; /* demo started over while we read */
    np.key = key;
    snprintf(url, sizeof url, "file://%s", path);
    if (cc_decode(np.win, url, 1, 1, 1, &px)) np_set_color(np_tone(px & 255, px >> 8 & 255, px >> 16 & 255));
}

/* np_remaining is the visible label while the player gives a length, label_playlen (stock's total) otherwise. */
static void np_label(int own) {
    if (own == np.own) return;
    np.own = own;
    widget_set_visible(np.rem, own, 0); /* both are insensitive in the asset, so hidden is also untouchable */
    widget_set_visible(np.tot, !own, 0);
}

static void np_time(void) {
    int pos = 0, len = 0;
    char text[16];
    if (!np.rem || !np.tot) return;
    if (get_playtimeandlength(&pos, &len) != 1 || len <= 0) {
        np_label(0);
        return;
    }
    if (pos < 0) pos = 0;
    if (pos > len) pos = len;
    if (np.shown != len - pos) {
        np_format_remaining(text, sizeof text, pos, len);
        widget_set_text_utf8(np.rem, text);
        np.shown = len - pos;
    }
    np_label(1);
}

static int np_tick(const void *timer) {
    (void)timer;
    if (!np.win) return RET_OK; /* not ours any more: a timer that returns RET_OK ends */
    np_cover();
    np_time();
    return RET_REPEAT;
}

static int np_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx != np.win) return RET_OK; /* an earlier page's end: the new one keeps its state */
    if (np.timer) timer_remove(np.timer);
    memset(&np, 0, sizeof np);
    return RET_OK;
}

static void np_start(void *win) {
    void *art;
    if (access(KILL_FILE, F_OK) == 0) return;
    if (np.win) { /* an earlier page that never said it was gone */
        if (np.timer) timer_remove(np.timer);
        memset(&np, 0, sizeof np);
    }
    np.win = win;
    np.rem = widget_lookup(win, "np_remaining", 1);
    np.tot = widget_lookup(win, "label_playlen", 1);
    np.shown = -1;
    np.color = NP_NEUTRAL & 0xffffff; /* the asset's window colour */
    if (!widget_on(win, EVT_DESTROY, np_on_destroy, win)) { memset(&np, 0, sizeof np); return; }
    np.timer = timer_add(np_tick, (void *)0, NP_TICK_MS);
    if (!np.timer) { /* the page stays stock; the destroy handler finds no window of ours any more */
        memset(&np, 0, sizeof np);
        return;
    }
    art = widget_lookup(win, "img_playcover", 1);
    if (art) {
        np_corner_init();
        widget_on(art, EVT_AFTER_PAINT, np_on_art_paint, (void *)0);
    }
    np_tick((const void *)0);
}

/* The hook (tools/pod.py PLAYING_INIT): stock first, then ours. */
int m1pod_playing_init(void *win, void *ctx) {
    int ret = stock_playing_init_trampoline(win, ctx);
    if (ret == RET_OK && win) np_start(win);
    return ret;
}
