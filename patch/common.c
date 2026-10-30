/* Small helpers every page of the payload shares (patch/common.h).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "shot.h"

/* Whether the card is mounted: its mount point is another file system than the one it is in (an unmounted /mnt/mmc is a plain directory on the internal flash). */
int pod_card_mounted(void) {
    unsigned a[32], b[32];
    memset(a, 0, sizeof a);
    memset(b, 0, sizeof b);
    if (statfs(SHOT_CARD, a) || statfs(SHOT_PARENT, b)) return 0;
    return !(a[0] == b[0] && a[8] == b[8] && a[9] == b[9]);   /* f_type, f_fsid (MIPS o32 statfs words 0, 8, 9): the same, nothing mounted */
}

int pod_on_back(void *ctx, void *e) {
    (void)ctx; (void)e;
    navigator_back();
    return RET_OK;
}

int pod_on_player(void *ctx, void *e) {
    (void)ctx; (void)e;
    on_backtoplayer_onclick((void *)0, (void *)0);
    return RET_OK;
}

int pod_is_type(void *w, const char *type) {
    const char *t = w ? widget_get_type(w) : (const char *)0;
    return t && strcmp(t, type) == 0;
}

void *pod_bind(void *win, const char *name, int (*fn)(void *, void *), const void *ctx) {
    void *w = widget_lookup(win, name, 1);
    if (w && fn) widget_on(w, EVT_CLICK, fn, (void *)ctx);
    return w;
}

/* The cover tint (Now Playing's, patch/nowplaying.c, and the album page's, patch/albuminfo.c). Value: NP_V_MIN + v *
 * (NP_V_MAX - NP_V_MIN) / 255 for the brightest channel v; every channel keeps NP_SAT_NUM / NP_SAT_DEN of its distance
 * from v (a grey stays grey). A black cover is the neutral tone. With NP_V_MAX 192 white text keeps 4.5:1 under the
 * gradients of both pages (test/pod/nowplaying.py, test/pod/albuminfo.py). */
__attribute__((noinline)) unsigned pod_tone(unsigned r, unsigned g, unsigned b) {
    unsigned v = r > g ? r : g, c[3], i, vt;
    if (b > v) v = b;
    if (!v) return NP_NEUTRAL;
    c[0] = r, c[1] = g, c[2] = b;
    vt = NP_V_MIN + v * (NP_V_MAX - NP_V_MIN) / 255;
    for (i = 0; i < 3; ++i) c[i] = vt - vt * NP_SAT_NUM * (v - c[i]) / (NP_SAT_DEN * v);
    return 0xff000000u | c[0] | c[1] << 8 | c[2] << 16;
}

/* The status bar (a window of the window manager, vtable type "system_bar") in a page's top-edge colour. One owner at a time:
 * the window that last tinted it. Only the owner can put the stock black back, so a page that is replaced or covered after the
 * next page has taken the bar over (Play all, Back) never undoes the new owner's colour. */
#define POD_LUM(r, g, b) (2126u * (r) * (r) + 7152u * (g) * (g) + 722u * (b) * (b))
static void *bar_owner __attribute__((section(".scratch")));

__attribute__((noinline)) unsigned pod_bar_color(unsigned color) {
    unsigned r = color & 255, g = color >> 8 & 255, b = color >> 16 & 255;
    while (POD_LUM(r, g, b) > NP_BAR_LUM_MAX) r = r * 15 >> 4, g = g * 15 >> 4, b = b * 15 >> 4;
    return 0xff000000u | r | g << 8 | b << 16;
}

static void *bar_find(void) {
    void *wm = window_manager(), *w;
    unsigned i, n;
    if (!wm) return (void *)0;
    for (n = widget_count_children(wm), i = 0; i < n; ++i) {
        w = widget_get_child(wm, i);
        if (pod_is_type(w, "system_bar")) return w;   /* the navbar is "system_bar_bottom" */
    }
    return (void *)0;
}

static int bar_set(unsigned color) {
    void *bar = bar_find();
    unsigned v[4]; /* value_t: type at 0, the uint32 at 8 */
    if (!bar) return 0;
    memset(v, 0, sizeof v);
    value_set_uint32(v, color);
    if (widget_set_style(bar, "normal:bg_color", v) != RET_OK) return 0;
    widget_invalidate_force(bar, (void *)0);
    return 1;
}

__attribute__((noinline)) int pod_bar_tint(void *win, unsigned color) {
    if (!win || !bar_set(pod_bar_color(color))) return 0;   /* a failed call keeps what the bar has (and owes) */
    bar_owner = win;
    return 1;
}

__attribute__((noinline)) void pod_bar_black(void *win) {
    if (!win || bar_owner != win) return;
    bar_owner = (void *)0;
    bar_set(NP_BAR_STOCK);
}

__attribute__((noinline)) int pod_is_top(void *win) {
    void *wm = window_manager();
    return win && wm && window_manager_get_top_main_window(wm) == win;
}

/* The tone cache: album key (cc_album_key) -> pod_tone word, RAM only, fixed size, least recently used out. Both pages look
 * an album up before they decode a cover; a miss is decoded once and inserted. A key is never 0 (0 marks a free entry). */
static struct { unsigned key, tone, used; } tone_tab[TONE_CACHE_N] __attribute__((section(".scratch")));
static unsigned tone_clock __attribute__((section(".scratch")));

__attribute__((noinline)) int pod_tone_get(unsigned key, unsigned *tone) {
    unsigned i;
    if (!key) return 0;
    for (i = 0; i < TONE_CACHE_N; ++i)
        if (tone_tab[i].key == key) {
            tone_tab[i].used = ++tone_clock;
            *tone = tone_tab[i].tone;
            return 1;
        }
    return 0;
}

__attribute__((noinline)) void pod_tone_put(unsigned key, unsigned tone) {
    unsigned i, at = 0;
    if (!key) return;
    for (i = 0; i < TONE_CACHE_N; ++i) {
        if (tone_tab[i].key == key) { at = i; break; }   /* the same album again: replaced in place */
        if (!tone_tab[i].key) { at = i; break; }          /* the first free entry */
        if (tone_tab[i].used < tone_tab[at].used) at = i; /* else the least recently used */
    }
    tone_tab[at].key = key, tone_tab[at].tone = tone, tone_tab[at].used = ++tone_clock;
}

__attribute__((noinline)) unsigned pod_alpha(unsigned y, unsigned a_top, unsigned a_bot, unsigned rows) {
    if (y >= rows - 1) return a_bot;
    return a_top + ((a_bot - a_top) * y + (rows - 1) / 2) / (rows - 1);
}

__attribute__((noinline)) unsigned pod_shade(unsigned color, unsigned y, unsigned a_top, unsigned a_bot, unsigned rows) {
    unsigned keep = 255 - pod_alpha(y, a_top, a_bot, rows);
    return (color & 255) * keep / 255 | (color >> 8 & 255) * keep / 255 << 8 | (color >> 16 & 255) * keep / 255 << 16;
}

/* The coverage of the area outside a quarter circle of radius r in the corner square of r pixels (the circle's centre at
 * the square's inner corner), 0..255: each pixel is sampled 8 x 8 times. */
__attribute__((noinline)) void pod_corner_fill(unsigned char *tab, unsigned r) {
    unsigned x, y, i, j, n, c = 2 * 8 * r;
    for (y = 0; y < r; ++y)
        for (x = 0; x < r; ++x) {
            for (n = 0, i = 0; i < 8; ++i)
                for (j = 0; j < 8; ++j) {
                    int dx = (int)(2 * (x * 8 + i) + 1) - (int)c, dy = (int)(2 * (y * 8 + j) + 1) - (int)c;
                    n += (unsigned)(dx * dx + dy * dy) > c * c;
                }
            tab[y * r + x] = (unsigned char)((n * 255 + 32) / 64);
        }
}

__attribute__((noinline)) void pod_corners(void *canvas, const unsigned char *tab, unsigned r, unsigned side, unsigned color,
                                           int row0, unsigned a_top, unsigned a_bot, unsigned rows) {
    unsigned k, x, y;
    for (k = 0; k < 4; ++k)
        for (y = 0; y < r; ++y) {
            unsigned ly = k & 2 ? side - 1 - y : y;
            int row = row0 + (int)ly;
            unsigned shade = pod_shade(color, row < 0 ? 0 : (unsigned)row, a_top, a_bot, rows);
            for (x = 0; x < r; ++x) {
                unsigned a = tab[y * r + x];
                if (!a) continue;
                canvas_set_fill_color(canvas, shade | a << 24);
                canvas_fill_rect(canvas, k & 1 ? side - 1 - x : x, ly, 1, 1);
            }
        }
}
