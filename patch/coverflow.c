/* M1 Pod Cover Flow: the stock Local Music albums as a cover carousel inside demo.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Ported from q2-pod's patch/coverflow.c, Copyright (c) 2026 Diamond Bond, MIT
 * (https://github.com/DiamondBond/q2-pod); see NOTICE. The depth renderer (pose/project/
 * unproject/column/draw_cover/coverflow_render, after Rockbox PictureFlow), the thumbnail-cache
 * design (one pthread, free-space guard, empty-file "no art" marker, ART_NEAR window) and the
 * texture-ring bookkeeping follow that file closely; everything that touches the device -- the
 * stock queries, the art calls, the page, its layout and its touch handling -- is written for the
 * M1 Plus, which has a touchscreen and no scroll wheel, so the wheel-only parts of q2-pod
 * (keys 172/173, ringnav, scrub) are gone; a transparent touch layer of the page's own drives the
 * stock slide_menu (drag, fling, snap, tap by x).
 *
 * No stock function is hooked. The page is opened from a row of the M1 Pod menu (the library's
 * albums) or from a row of the M1 Pod Artists list (one artist's
 * albums, coverflow_artist: q2-pod's ARTIST_ALBUMS scope, with the stock "All songs" row as its All
 * albums card), and everything here is reached only from that page's own widgets, timers and its
 * one worker thread. A tap on the centre cover opens the stock album page (open_album; the page
 * itself is restyled by patch/albuminfo.c).
 *
 * The shelf is the 168 px one (offsets.inc: 276 px frame, DRAG_PX 108); the cache files carry
 * their size (<key>-168.jpg). The captions are hscroll_labels in the asset (tools/pod_ui.py). With
 * CF_HOST the renderer alone is built for the host (test/coverflow.py). docs/architecture.md.
 */
#include "offsets.inc"

#define CF_ONE 65536
#define CF_REACH 3 /* ring slots either side of the centre that can show (fading in) or preload */
#define CF_RING (2 * CF_REACH + 1)
#define CF_TEXELS (ART_SIZE * ART_SIZE)
#define CF_EYE16 (16 * CF_EYE)
#define CF_HALF16 (16 * ART_SIZE / 2)
#define CF_MID256 (256 * (CF_TOP + ART_SIZE / 2)) /* the horizon every cover centres on */

#ifdef CF_HOST
#include <stdlib.h>
#include <string.h>
#else
#include "stock.h"
#endif

/* ===========================================================================
 * The depth renderer (q2-pod, after Rockbox PictureFlow). All integer: 16.16 turns and
 * rotations, geometry in 1/16 px, row spans in 1/256 px. Built on the host too (test/coverflow.py).
 */

/* cos and sin of 0 to 60 degrees in 16 steps, 16.16 */
static const int cf_cos[17] = { 65536, 65396, 64975, 64277, 63303, 62058, 60547, 58777, 56756,
                                54491, 51993, 49273, 46341, 43211, 39896, 36410, 32768 };
static const int cf_sin[17] = { 0,     4286,  8554,  12785, 16962, 21066, 25080, 28986, 32768,
                                36410, 39896, 43211, 46341, 49273, 51993, 54491, 56756 };

/* A right-hand cover t (16.16, >= 0) from the visual position: centre xc and depth zc (1/16 px),
 * rotation c, s (16.16) and brightness (of 256). Left covers mirror it. */
typedef struct {
    int xc, zc, c, s, bright;
} pose_t;

static void pose(int t, pose_t *p) {
    int a = t < CF_ONE ? t : CF_ONE, i = a >> 12, f = a & 4095;
    p->c = cf_cos[i] + (i < 16 ? (cf_cos[i + 1] - cf_cos[i]) * f >> 12 : 0);
    p->s = cf_sin[i] + (i < 16 ? (cf_sin[i + 1] - cf_sin[i]) * f >> 12 : 0);
    if (t < CF_ONE) {
        /* xc = A t + B t^2: CF_X1 at t = 1, arriving at the stack's CF_XS slope, and quick at
         * first, so the covers turning in and out mid-step keep clear of each other. */
        int sq = (int)((unsigned)t * (unsigned)t >> 16);
        p->xc = (16 * (2 * CF_X1 - CF_XS) * t + 16 * (CF_XS - CF_X1) * sq) >> 16;
        p->zc = 16 * CF_Z1 * t >> 16;
        p->bright = 256 - ((256 - CF_BRIGHT1) * t >> 16);
    } else {
        int e = t - CF_ONE;
        p->xc = 16 * CF_X1 + (16 * CF_XS * e >> 16);
        p->zc = 16 * CF_Z1 + (16 * CF_ZS * e >> 16);
        p->bright = e < CF_ONE ? CF_BRIGHT1 - ((CF_BRIGHT1 - CF_BRIGHT2) * e >> 16)
                    : e < 2 * CF_ONE ? CF_BRIGHT2 * (2 * CF_ONE - e) >> 16
                                     : 0;
    }
}

/* Screen x (1/16 px right of the centre line) of the cover point u (1/16 px from its middle). */
static int project(const pose_t *p, int u) {
    return (p->xc + (u * p->c >> 16)) * CF_EYE16 / (CF_EYE16 + p->zc - (u * p->s >> 16));
}

/* The cover point under screen x dx (1/16 px right of the centre line), the inverse of project;
 * 0 when the column misses the cover. *h gets the cover's projected height there (1/256 px). */
static int unproject(const pose_t *p, int dx, int *u, int *h) {
    int den = (CF_EYE16 * p->c + dx * p->s) >> 16;
    if (den <= 0) return 0;
    *u = (dx * (CF_EYE16 + p->zc) - CF_EYE16 * p->xc) / den;
    if (*u < -CF_HALF16 || *u >= CF_HALF16) return 0;
    *h = ART_SIZE * 256 * CF_EYE16 / (CF_EYE16 + p->zc - (*u * p->s >> 16));
    return 1;
}

#define HOT static inline __attribute__((always_inline)) /* -Oz would call these per pixel */

/* p scaled by b (of 256), per 8-bit channel; alpha is left 0. */
HOT unsigned shade(unsigned p, unsigned b) {
    return ((p & 0xff00ffu) * b >> 8 & 0xff00ffu) | ((p & 0xff00u) * b >> 8 & 0xff00u);
}

/* The frame being drawn, nearest cover first: each pixel's alpha byte holds the coverage so far
 * (255 opaque), and a layer only fills what is left, which composites as drawing back to front
 * would. Per column, rows solid_top to solid_bottom are known opaque and skipped outright. */
typedef struct {
    unsigned *d;
    int pitch;
    short solid_top[CF_VIEW_W], solid_bottom[CF_VIEW_W];
} shelf_t;

/* colour (alpha ignored) under what is already at px, covering cov (of 256) of the pixel */
HOT void put(unsigned *px, unsigned colour, unsigned cov) {
    unsigned a = *px >> 24, have = a + (a >> 7), w = cov * (256 - have) >> 8;
    if (!a && cov == 256) {
        *px = colour | 0xff000000u;
        return;
    }
    if (!w) return;
    have += w;
    *px = ((*px & 0xffffffu) + shade(colour, w)) | (have > 255 ? 255u : have) << 24;
}

/* One texture column (texels ART_SIZE apart) h high (1/256 px) on the horizon at frame column col,
 * its partial end rows by coverage, then its reflection fading out below. */
static void column(shelf_t *f, int col, const unsigned *tex, int h, int bright) {
    if (h < 16) return;
    unsigned *d = f->d + col;
    int top = CF_MID256 - h / 2, bottom = top + h, step = (ART_SIZE << 20) / (h >> 4);
    int solid_top = f->solid_top[col], solid_bottom = f->solid_bottom[col];
    int y = top >> 8, end = (bottom + 255) >> 8, last = end < CF_VIEW_H ? end : CF_VIEW_H;
    int first = y, final = end - 1; /* the rows the edges cross */
    int v = (((y << 8) + 128 - top) >> 4) * step >> 4, pitch = f->pitch; /* v: 16.16 texel row */
    unsigned *px;
    if (y < 0) v -= y * step, y = 0;
    px = d + y * pitch;
    while (y < last) {
        int run;
        if (y >= solid_top && y < solid_bottom) {
            int skip = solid_bottom - y;
            v += skip * step, px += skip * pitch, y = solid_bottom;
            continue;
        }
        run = y < solid_top && solid_top < last ? solid_top : last; /* up to the opaque span */
        for (; y < run; ++y, v += step, px += pitch) {
            int row = v < 0 ? 0 : v >> 16 >= ART_SIZE ? ART_SIZE - 1 : v >> 16;
            unsigned cov = 256;
            if (y == first || y == final) {
                int from = y << 8 > top ? y << 8 : top,
                    to = (y + 1) << 8 < bottom ? (y + 1) << 8 : bottom;
                cov = (unsigned)(to - from);
            }
            put(px, shade(tex[row * ART_SIZE], (unsigned)bright), cov);
        }
    }
    /* The reflection starts where the body ends, sharing the row the body only partly covers. */
    {
        int reflect = h * CF_REFLECT / ART_SIZE, stop = (bottom + reflect + 255) >> 8;
        int fade = reflect > 0 ? (256 << 16) / reflect : 0; /* fading per 1/256 px, 16.16 */
        unsigned dim = (unsigned)bright * CF_REFLECT_TOP >> 8;
        int s0, s1;
        if (stop > CF_VIEW_H) stop = CF_VIEW_H;
        for (y = bottom >> 8, px = d + y * pitch; reflect && y < stop; ++y, px += pitch) {
            int from = y << 8 > bottom ? y << 8 : bottom,
                dist = ((from + ((y + 1) << 8)) >> 1) - bottom, mirrored, row;
            unsigned cov;
            if (dist >= reflect) break;
            if (y < 0 || (y >= solid_top && y < solid_bottom)) continue;
            mirrored = dist * step >> 8 >> 16; /* texel rows up from the bottom edge */
            row = ART_SIZE - 1 - (mirrored >= ART_SIZE ? ART_SIZE - 1 : mirrored);
            cov = (unsigned)(((y + 1) << 8) - from) * (256u - (unsigned)(dist * fade >> 16)) >> 8;
            put(px, shade(tex[row * ART_SIZE], dim), cov);
        }
        /* The rows this body covers whole are opaque now: join them to the known span, or keep
         * the longer of the two. */
        s0 = (top + 255) >> 8, s1 = bottom >> 8;
        s0 = s0 < 0 ? 0 : s0, s1 = s1 > CF_VIEW_H ? CF_VIEW_H : s1;
        if (s1 <= s0) return;
        if (solid_bottom > solid_top && s0 <= solid_bottom && s1 >= solid_top) {
            s0 = s0 < solid_top ? s0 : solid_top;
            s1 = s1 > solid_bottom ? s1 : solid_bottom;
        } else if (s1 - s0 <= solid_bottom - solid_top)
            return;
        f->solid_top[col] = (short)s0, f->solid_bottom[col] = (short)s1;
    }
}

/* The cover t (16.16, signed) turns from the visual position, under what is drawn. */
static void draw_cover(shelf_t *f, int t, const unsigned *tex) {
    pose_t p;
    int side = t < 0 ? -1 : 1, a, b, lo, hi, v;
    pose(t * side, &p);
    if (p.bright <= 0 || !tex) return;
    a = project(&p, -CF_HALF16), b = project(&p, CF_HALF16);
    lo = (16 * CF_CX + (a < b ? a : b)) >> 4, hi = (16 * CF_CX + (a < b ? b : a)) >> 4;
    for (v = lo; v <= hi; ++v) { /* v: the column as if the cover were on the right */
        int col = side > 0 ? v : 2 * CF_CX - 1 - v, u, h, k;
        if (col < 0 || col >= CF_VIEW_W || !unproject(&p, (2 * v + 1 - 2 * CF_CX) * 8, &u, &h))
            continue;
        k = (u + CF_HALF16) >> 4;
        if (k < 0) k = 0;
        if (k >= ART_SIZE) k = ART_SIZE - 1;
        column(f, col, tex + (side > 0 ? k : ART_SIZE - 1 - k), h, p.bright);
    }
}

/* The ring slot of the k-th nearest pair's nearer (i 0) or farther (i 1) cover at frac: the side
 * the position is moving away from is farther. */
static int slot(int frac, int k, int i) {
    return (i == 0) == (frac < 0) ? CF_REACH - k : CF_REACH + k;
}

/* The shelf at frac (16.16, -CF_ONE/2 to under CF_ONE/2) past its centre cover: ring[j] is the
 * texture of the cover j - CF_REACH from the centre, or 0 to leave it out. Nearest first; nearer
 * covers and their reflections overlap farther ones. */
void coverflow_render(unsigned *d, int pitch, int frac, const unsigned *const ring[CF_RING]) {
    shelf_t f;
    int x, y, k, i;
    f.d = d, f.pitch = pitch;
    for (x = 0; x < CF_VIEW_W; ++x) f.solid_top[x] = f.solid_bottom[x] = 0;
    for (y = 0; y < CF_VIEW_H; ++y) memset(d + y * pitch, 0, CF_VIEW_W * 4);
    for (k = 0; k <= CF_REACH; ++k)
        for (i = 0; i < (k ? 2 : 1); ++i) {
            int j = slot(frac, k, i);
            draw_cover(&f, (j - CF_REACH) * CF_ONE - frac, ring[j]);
        }
    for (y = 0; y < CF_VIEW_H; ++y) { /* over black */
        unsigned *p = d + y * pitch;
        x = CF_VIEW_W;
        do *p++ |= 0xff000000u;
        while (--x);
    }
}

/* FNV-1a over a string, with a separator so "ab"+"c" and "a"+"bc" differ (q2-pod). */
unsigned cf_fnv(unsigned h, const char *s) {
    for (; s && *s; ++s) h = (h ^ (unsigned char)*s) * 16777619u;
    return h * 16777619u;
}

/* The centred square of a w x h RGBA image, nearest sampled to ART_SIZE over black. at[] maps the
 * source's byte order (r, g, b, a) onto the pixel; out holds CF_TEXELS pixels. */
void cf_sample(const unsigned char *data, unsigned w, unsigned h, unsigned stride,
               const unsigned char *at, unsigned *out) {
    unsigned side = w < h ? w : h, xoff[ART_SIZE], x, y;
    const unsigned char *base = data + (h - side) / 2 * stride + (w - side) / 2 * 4;
    for (x = 0; x < ART_SIZE; ++x) xoff[x] = x * side / ART_SIZE * 4;
    for (y = 0; y < ART_SIZE; ++y) {
        const unsigned char *line = base + y * side / ART_SIZE * stride;
        for (x = 0; x < ART_SIZE; ++x) {
            const unsigned char *px = line + xoff[x];
            unsigned a = px[at[3]], r = px[at[0]], g = px[at[1]], b = px[at[2]];
            if (a < 255) r = r * a / 255, g = g * a / 255, b = b * a / 255; /* over black */
            *out++ = 0xff000000u | r | g << 8 | b << 16;
        }
    }
}

#ifndef CF_HOST
/* ===========================================================================
 * The page. UI thread only, except the worker thread marked below.
 */
#define P(r, off) (*(char **)((char *)(r) + (off)))
#define I(r, off) (*(int *)((char *)(r) + (off)))

#define ART_DIR "/mnt/mmc/.coverflow"
#define LAST_ALBUM ART_DIR "/album" /* the centre album's key, so a reboot opens on it */
#define MIN_FREE_MB 16              /* no new cache files below this much free space on the card */
#define ART_NEAR 3                  /* flat fallback: real art only this many covers either side */
#define PLACEHOLDER "p_default"     /* the stock 254 px disc, Now Playing's missing-art image */
#define F_OK 0
#define POLL_MS 250
#define MAX_ALBUMS 4000 /* the job array and the slide_menu's children are bounded */

enum { CF_COVERS, CF_PREPARING }; /* CF_COVERS is 0: a zeroed cf is on it */
enum { ARTIST_ALBUMS = 1 };         /* cf.scoped, as q2-pod's */

typedef struct {
    char *track; /* the album's first track, copied so the thread never reads stock deques */
    unsigned key;
} job_t;

static struct {
    void *win, *covers, *slide, *name, *artist, *status, *cancel;
    void *input;                  /* the transparent touch layer over the covers */
    void *albums;                 /* our copy of the stock album rows */
    unsigned count;               /* how many of them are covers (scoped: the card only with two albums) */
    /* Scoped (ARTIST_ALBUMS, else 0): albums holds one artist's album rows as the stock artist
     * page lists them (loadAlbumList 0xf004), the last one the stock "All songs" row, shown as
     * the All albums card; artist_row is a deque holding our copy of that artist's row; keys[i]
     * is album i's cache key, the library album of the same name's, so the covers are the main
     * Cover Flow's files. No saved album: the main Cover Flow's last album is left alone. */
    int scoped;
    void *artist_row;
    unsigned *keys;
    job_t *jobs;
    unsigned long thread;
    unsigned timer;
    unsigned saved_album;         /* the centre album's key, kept across opens and reboots */
    int screen, album, running;
    /* touch: a drag in progress, where it started, the offset it started from, the last two
     * samples for the fling velocity, and the snap animation's target offset and timer */
    int dragging, moved, down_x, down_y, base_off, x0, t0, x1, t1, snap_to;
    unsigned snap_timer;
    volatile int done, total, cancelled;
} cf __attribute__((section(".scratch")));

/* The depth renderer's state: the frame, the textures of the covers around the visual position
 * and the placeholder's. No frame: the flat fallback (stock images on the slide_menu). */
static struct {
    void *frame;                  /* bitmap_t *, CF_VIEW_W x CF_VIEW_H RGBA8888 */
    unsigned *tex;                /* CF_RING texture slots, then the placeholder */
    int album[CF_RING];           /* each slot's album + 1; 0 is empty */
    const unsigned *art[CF_RING]; /* its texture: the slot's own, or the placeholder */
    int c, frac, drawn;           /* the position the frame holds, once drawn */
} fx __attribute__((section(".scratch")));

static const char *cf_str(void *r, int field) {
    const char *s = r ? P(r, field) : (const char *)0;
    return s ? s : "";
}

/* Visibility and hit-testing together. This AWTK build's hit test (widget_find_target_default
 * 0x6747d4, widget_on_pointer_down_children 0x6714ac) only checks flags & 9 -- enable (bit 0) and
 * sensitive (bit 3) -- and never visible (bit 2), so a hidden widget still takes the touches over
 * its rectangle. Everything this page hides is therefore made insensitive as well. */
static void show(void *w, int on) {
    if (!w) return;
    widget_set_visible(w, on, 0);
    widget_set_sensitive(w, on);
}

static unsigned album_count(void) { return cf.albums ? cf.count : 0; }
static void *album_at(unsigned i) { return i < album_count() ? deque_at(cf.albums, i) : (void *)0; }

static unsigned album_key(void *r) {
    unsigned h = cf_fnv(cf_fnv(FNV_SEED, cf_str(r, REC_ARTIST)), cf_str(r, REC_ALBUM));
    return h | !h;
}

/* The All albums card: the "All songs" row the stock artist query appends (getAlbumByArtist). */
static int is_card(void *r) { return cf.scoped && r && I(r, REC_ID) == ID_ALL_SONGS; }

/* Album i's cache key; 0 (the card) has no art. */
static unsigned key_at(unsigned i) {
    void *r = album_at(i);
    if (!r || is_card(r)) return 0;
    return cf.keys ? cf.keys[i] : album_key(r);
}

/* ART_DIR/<key>-168.jpg<suffix>: the cache files carry their size, so the 140 px files of the
 * earlier builds are never scaled up (they stay for those builds; the larger set is extracted on
 * the first open, as on a first run). out holds at least 64 bytes. */
#define CF_STR_(x) #x
#define CF_STR(x) CF_STR_(x)
static char *art_path(char *out, unsigned size, unsigned key, const char *suffix) {
    snprintf(out, size, ART_DIR "/%08x-" CF_STR(ART_SIZE) ".jpg%s", key, suffix);
    return out;
}

static long file_size(const char *path) {
    void *f = fopen(path, "rb");
    long size = f && !fseek(f, 0, 2) ? ftell(f) : -1;
    if (f) fclose(f);
    return size;
}

/* Whether dir's file system has MIN_FREE_MB free (statfs, MIPS o32 layout: f_bsize is word 1,
 * f_bavail word 7), as q2-pod's card_space. */
static int card_space(const char *dir) {
    unsigned fs[32];
    memset(fs, 0, sizeof fs);
    return !statfs(dir, fs) &&
           (unsigned long long)fs[7] * fs[1] >= (unsigned long long)MIN_FREE_MB << 20;
}

/* ---------------------------------------------------------------------------
 * The worker thread. It touches only: its own job array (built before it started), the volatile
 * counters below, files under ART_DIR, and the two stock art functions under parse_cover_mutex,
 * which is the lock every stock caller of them holds (parse_albumcovertask_thd 0x4dd68c,
 * parseplaycover_thd 0x4df1c4). It never touches a widget, a deque or the image manager.
 */
static void build_art(const job_t *j) {
    char dst[64], tmp[64];
    int ok;
    void *f;
    if (access(j->track, F_OK)) return; /* storage gone: no marker, the next open retries */
    art_path(dst, sizeof dst, j->key, "");
    art_path(tmp, sizeof tmp, j->key, ".tmp");
    pthread_mutex_lock((void *)PARSE_COVER_MUTEX);
    ok = toolsGetAlbumCover(j->track, tmp, ART_SIZE, ART_SIZE) == 1 ||
         toolsGetExternCover(j->track, tmp, ART_SIZE, ART_SIZE) == 1;
    pthread_mutex_unlock((void *)PARSE_COVER_MUTEX);
    if (ok && file_size(tmp) > 0 && !rename(tmp, dst)) return;
    unlink(tmp);
    if (access(j->track, F_OK)) return;
    f = fopen(dst, "w"); /* an empty file marks "no art": the placeholder shows, no retry */
    if (f) fclose(f);
}

static void *worker(void *unused) {
    (void)unused;
    while (cf.done < cf.total && !cf.cancelled) {
        build_art(&cf.jobs[cf.done]);
        ++cf.done;
    }
    return (void *)0;
}

/* ------------------------------------------------------------------------ */

static void stop_timer(void) {
    if (cf.timer) timer_remove(cf.timer);
    cf.timer = 0;
}

/* A running worker cancelled and joined (bounded by one album's art), and the job array freed. */
static void worker_stop(void) {
    int i;
    if (cf.running) {
        cf.cancelled = 1;
        pthread_join(cf.thread, (void **)0);
        cf.running = 0;
    }
    for (i = 0; i < cf.total; ++i)
        if (cf.jobs) free(cf.jobs[i].track);
    free(cf.jobs);
    cf.jobs = (job_t *)0;
    cf.total = cf.done = cf.cancelled = 0;
}

static void fx_close(void) {
    if (fx.frame) bitmap_destroy(fx.frame);
    free(fx.tex);
    memset(&fx, 0, sizeof fx);
}

/* The frame and every texture at once, or neither: the flat covers then stand in. */
static int fx_open(void) {
    unsigned *placeholder;
    int i;
    memset(&fx, 0, sizeof fx);
    fx.frame = bitmap_create_ex(CF_VIEW_W, CF_VIEW_H, CF_VIEW_W * 4, BITMAP_RGBA8888);
    fx.tex = fx.frame ? calloc(CF_RING + 1, CF_TEXELS * 4) : (unsigned *)0;
    if (!fx.tex) {
        fx_close();
        return 0;
    }
    *(unsigned short *)((char *)fx.frame + BITMAP_FLAGS) |= 1; /* OPAQUE: every pixel is */
    placeholder = fx.tex + CF_RING * CF_TEXELS;
    for (i = 0; i < CF_TEXELS; ++i) placeholder[i] = 0xff2b2b2bu; /* until the theme image loads */
    return 1;
}

/* A decoded image copied into a texture: its centred square, nearest sampled to ART_SIZE, over
 * black. Only the four 32-bit formats; the stock loader decodes JPEG and PNG to RGBA8888 with
 * straight alpha. The image manager's copy is only read, and a cover's load is dropped again at
 * once, as the stock cover rows do. */
static int decode(const char *url, unsigned *out, int unload) {
    static const unsigned char at[4][4] = BITMAP_RGBA_AT;
    unsigned bitmap[32]; /* bitmap_t is 0x48 bytes */
    unsigned w, h, format;
    const unsigned char *data;
    memset(bitmap, 0, sizeof bitmap);
    if (widget_load_image(cf.win, url, bitmap)) return 0;
    w = bitmap[0], h = bitmap[1];
    format = (unsigned)(*(unsigned short *)((char *)bitmap + BITMAP_FORMAT)) - 1u;
    data = format < 4 && w && h && w <= 4096 && h <= 4096 ? bitmap_lock_buffer_for_read(bitmap)
                                                          : (const unsigned char *)0;
    if (data) {
        cf_sample(data, w, h, bitmap_get_line_length(bitmap), at[format], out);
        bitmap_unlock_buffer(bitmap);
    }
    if (unload) widget_unload_image(cf.win, bitmap);
    return data != (const unsigned char *)0;
}

/* Album a's cached art in buf, else the placeholder (no art, or no cache file yet). */
static const unsigned *fx_load(int a, unsigned *buf) {
    char url[80];
    unsigned key = key_at((unsigned)a);
    if (key) {
        memcpy(url, "file://", 8);
        art_path(url + 7, sizeof url - 7, key, "");
        if (!access(url + 7, F_OK) && file_size(url + 7) > 0 && decode(url, buf, 1)) return buf;
    }
    return fx.tex + CF_RING * CF_TEXELS;
}

/* The CF_RING covers around album c of n stay decoded, others are dropped as movement crosses
 * albums; ring gets each ring slot's texture. A small library repeats albums round the ring, as
 * the slide_menu wraps. */
static void fx_window(int c, int n, const unsigned *ring[CF_RING]) {
    int want[CF_RING], i, j;
    for (j = 0; j < CF_RING; ++j) want[j] = ((c + j - CF_REACH) % n + n) % n + 1;
    for (i = 0; i < CF_RING; ++i) {
        int keep = 0;
        for (j = 0; j < CF_RING; ++j) keep |= fx.album[i] == want[j];
        if (!keep) fx.album[i] = 0;
    }
    for (j = 0; j < CF_RING; ++j) {
        i = 0;
        while (i < CF_RING && fx.album[i] != want[j]) ++i;
        if (i == CF_RING) { /* at most CF_RING albums are wanted, so a slot is free */
            for (i = 0; fx.album[i]; ++i) {}
            fx.album[i] = want[j];
            fx.art[i] = fx_load(want[j] - 1, fx.tex + i * CF_TEXELS);
            fx.drawn = 0;
        }
        ring[j] = fx.art[i];
    }
}

static int floor_div(int a, int b) { /* floor division, b > 0 */
    return a / b - (a % b < 0);
}

/* The visual position from the slide_menu's committed index and its live drag/animation offset,
 * both read through the stock property accessors ("value", "xoffset", "h"), so no field offset of
 * the stock widget is pinned. The stock commit is value - round(xoffset / item width) and the item
 * width is the widget's height (slide_menu's delta index @0x612360), so the continuous position is
 * p = value - xoffset / h: a positive xoffset (a drag to the right) walks back towards the
 * previous album. c gets the centre album of n and frac (16.16, -1/2 to under 1/2) how far past it
 * the shelf stands, the renderer's sign. */
static int visual(void *s, int n, int *c, int *frac) {
    int stride = widget_get_prop_int(s, "h", 0), d = widget_get_prop_int(s, "xoffset", 0), q;
    if (n <= 0 || stride <= 0) return 0;
    q = floor_div(2 * d + stride, 2 * stride);   /* round(d / stride) */
    *frac = (q * stride - d) * CF_ONE / stride;  /* p - c */
    *c = ((widget_get_prop_int(s, "value", 0) - q) % n + n) % n;
    return stride;
}

/* The slide_menu's own EVT_AFTER_PAINT: the covers are drawn over its (empty) children. */
static int on_paint(void *ctx, void *e) {
    int c, frac, n, k, r[4];
    const unsigned *ring[CF_RING];
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    (void)ctx;
    if (!canvas || !fx.frame || cf.screen != CF_COVERS || !cf.slide) return RET_OK;
    n = (int)widget_count_children(cf.slide);
    if (!visual(cf.slide, n, &c, &frac)) return RET_OK;
    fx_window(c, n, ring);
    if (cf.scoped) /* an artist's shelf stops at both ends (q2-pod coverflow_bounded): no repeats */
        for (k = 0; k < CF_RING; ++k)
            if ((unsigned)(c + k - CF_REACH) >= (unsigned)n) ring[k] = 0;
    if (!fx.drawn || c != fx.c || frac != fx.frac) {
        unsigned *d = (unsigned *)bitmap_lock_buffer_for_write(fx.frame);
        if (!d) return RET_OK;
        coverflow_render(d, (int)(bitmap_get_line_length(fx.frame) / 4), frac, ring);
        bitmap_unlock_buffer(fx.frame);
        fx.c = c, fx.frac = frac, fx.drawn = 1;
    }
    r[0] = 0, r[1] = 0, r[2] = CF_VIEW_W, r[3] = CF_VIEW_H;
    canvas_draw_image(canvas, fx.frame, r, r);
    return RET_OK;
}

/* Flat fallback (no depth frame): the children are stock images, real art only near the centre.
 * The picture is set only when it changes, so a commit costs one property read per child and a
 * file check for the few covers in the window (q2-pod's cover()). */
static void flat_cover(void *img, unsigned i, int near) {
    char url[80];
    const char *want = PLACEHOLDER;
    unsigned key = near ? key_at(i) : 0;
    if (key) {
        memcpy(url, "file://", 8);
        art_path(url + 7, sizeof url - 7, key, "");
        if (!access(url + 7, F_OK) && file_size(url + 7) > 0) want = url;
    }
    if (strcmp(widget_get_prop_str(img, "image", ""), want)) image_base_set_image(img, want);
}

/* Album over artist under the covers; the card is All albums over the artist. */
static void captions(void *r) {
    widget_set_text_utf8(cf.name, is_card(r) ? "All albums" : cf_str(r, REC_ALBUM));
    widget_set_text_utf8(cf.artist, cf_str(r, REC_ARTIST));
}

static void show_album(void) {
    unsigned n = album_count(), c = (unsigned)widget_get_prop_int(cf.slide, "value", 0);
    void *r = album_at(c);
    if (!r) return;
    cf.album = (int)c;
    if (!cf.scoped) cf.saved_album = album_key(r);
    captions(r);
    if (!fx.frame) {
        unsigned i;
        for (i = 0; i < n; ++i) {
            unsigned d = i > c ? i - c : c - i;
            flat_cover(widget_get_child(cf.slide, i), i, d <= ART_NEAR || n - d <= ART_NEAR);
        }
    }
}

static int on_changed(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (cf.screen == CF_COVERS) show_album();
    return RET_OK;
}


/* ---------------------------------------------------------------------------
 * Touch. A transparent view over the covers takes every pointer event in the frame and drives
 * the slide_menu through its public "xoffset" property and slide_menu_set_value, so nothing
 * depends on the stock widget's own drag or on clicks reaching its children. A drag moves the
 * shelf with the finger (DRAG_PX per album), a release coasts by the fling and snaps to a cover
 * with a short timer animation, and a tap is hit-tested by x: the centre cover opens its album,
 * a side cover is brought to the centre. All in the UI thread.
 */
#define TAP_SLOP 12     /* px: within this a release is a tap */
#define FLING_MS 120    /* the fling coasts for this long at the release velocity */
#define SNAP_MS 16
#define EVT_POINTER_DOWN 0xff   /* input_device_status_on_input_event jump table @0x88f120 */
#define EVT_POINTER_MOVE 0x101
#define EVT_POINTER_UP 0x103
#define EVT_POINTER_ABORT 0x107 /* widget_on_pointer_up/move dispatch it @0x6719b8 */
#define PE_X 0x18               /* pointer_event_t: x, y (absolute); event_t.time u64 @0x8 */
#define PE_Y 0x1c
#define EV_TIME 0x08

static int abs_i(int v) { return v < 0 ? -v : v; }
static int stride(void) { return widget_get_prop_int(cf.slide, "h", CF_VIEW_H); }
static int offset(void) { return widget_get_prop_int(cf.slide, "xoffset", 0); }
static void set_offset(int off) { widget_set_prop_int(cf.slide, "xoffset", off); }

static int clamp_i(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }

/* Scoped, the shelf has ends: an offset of `albums` covers (positive: towards the first album)
 * stays within the artist's albums, so p = value - offset / h never leaves 0..n-1. */
static int bound(int albums) {
    int v = widget_get_prop_int(cf.slide, "value", 0), n = (int)widget_count_children(cf.slide);
    return cf.scoped ? clamp_i(albums, v - (n - 1), v) : albums;
}

static void snap_stop(void) {
    if (cf.snap_timer) timer_remove(cf.snap_timer);
    cf.snap_timer = 0;
}

/* The offset reached its target: commit it as the stock widget does (offset back to 0 and
 * value - offset / h, wrapped), which dispatches EVT_VALUE_CHANGED and updates the captions. */
static void commit(void) {
    int h = stride(), n = (int)widget_count_children(cf.slide), q, v, now;
    if (n <= 0 || h <= 0) return;
    q = cf.snap_to / h;
    now = widget_get_prop_int(cf.slide, "value", 0);
    v = ((now - q) % n + n) % n;
    set_offset(0);
    if (v != now) slide_menu_set_value(cf.slide, v);
    else show_album();
}

static int on_snap(const void *unused) {
    int off, d, step;
    (void)unused;
    cf.snap_timer = 0;
    if (cf.screen != CF_COVERS || !cf.slide) return RET_OK;
    off = offset(), d = cf.snap_to - off;
    if (abs_i(d) <= 2) {
        set_offset(cf.snap_to);
        commit();
        return RET_OK;
    }
    step = d / 3;
    if (!step) step = d > 0 ? 1 : -1;
    set_offset(off + step);
    cf.snap_timer = timer_add(on_snap, (void *)0, SNAP_MS);
    return RET_OK;
}

/* Animate the offset to `albums` covers away from the committed one (positive: towards the
 * previous albums, as a drag to the right does). */
static void snap(int albums) {
    snap_stop();
    cf.snap_to = bound(albums) * stride();
    cf.snap_timer = timer_add(on_snap, (void *)0, SNAP_MS);
}


static void open_album(int index);

static void tap(int x) {
    int d = x - CF_CX, far = abs_i(d) > CF_X1 + ART_SIZE / 4 ? 2 : 1;
    if (abs_i(d) < ART_SIZE / 2) {   /* the centre cover */
        if (!offset()) open_album(widget_get_prop_int(cf.slide, "value", 0));
        return;
    }
    snap(d < 0 ? far : -far);        /* a side cover comes to the centre */
}

static int pe(void *e, int field) { return *(int *)((char *)e + field); }

static int on_pointer(void *ctx, void *e) {
    int type, x;
    (void)ctx;
    if (!e || !cf.slide || cf.screen != CF_COVERS) return RET_OK;
    type = pe(e, 0), x = pe(e, PE_X);
    if (type == EVT_POINTER_DOWN) {
        snap_stop();
        cf.dragging = 1, cf.moved = 0;
        cf.down_x = x, cf.down_y = pe(e, PE_Y), cf.base_off = offset();
        cf.x0 = cf.x1 = x, cf.t0 = cf.t1 = pe(e, EV_TIME);
        widget_grab(cf.covers, cf.input); /* moves and the release come here wherever they go */
    } else if (type == EVT_POINTER_MOVE && cf.dragging) {
        int dx = x - cf.down_x;
        if (abs_i(dx) > TAP_SLOP || abs_i(pe(e, PE_Y) - cf.down_y) > TAP_SLOP) cf.moved = 1;
        if (cf.moved) {
            int h = stride(), off = cf.base_off + dx * h / DRAG_PX;
            set_offset(cf.scoped ? clamp_i(off, bound(-0x7fff) * h, bound(0x7fff) * h) : off);
        }
        cf.x0 = cf.x1, cf.t0 = cf.t1, cf.x1 = x, cf.t1 = pe(e, EV_TIME);
    } else if ((type == EVT_POINTER_UP || type == EVT_POINTER_ABORT) && cf.dragging) {
        int h = stride(), off = offset(), dt = pe(e, EV_TIME) - cf.t0, fling = 0, albums;
        cf.dragging = 0;
        widget_ungrab(cf.covers, cf.input);
        if (type == EVT_POINTER_UP && !cf.moved) {
            set_offset(cf.base_off);
            tap(x);
            return RET_OK;
        }
        if (type == EVT_POINTER_UP && dt > 0 && dt < 200)
            fling = (x - cf.x0) * FLING_MS / dt * h / DRAG_PX;
        if (fling > 3 * h) fling = 3 * h;
        if (fling < -3 * h) fling = -3 * h;
        off += fling;
        albums = (off >= 0 ? off + h / 2 : off - h / 2) / h;
        snap(albums);
    }
    return RET_OK;
}

/* The covers screen: one slide_menu child per album, empty under the depth frame, stock images
 * in the flat fallback. The slide_menu is stock: it drags, wraps, animates and commits an index. */
static void to_covers(void) {
    cf.screen = CF_COVERS;
    show(cf.status, 0);
    show(cf.cancel, 0);
    show(cf.covers, 1); /* the captions are never hidden, and stay insensitive (the asset): they
                         * lie over the frame's black bottom rows, so its touch layer gets the touch */
    if (!cf.slide) {
        unsigned n = album_count(), i;
        int depth = fx_open();
        cf.slide = widget_factory_create_widget(widget_factory(), "slide_menu", cf.covers, 0, 0,
                                                CF_VIEW_W, depth ? CF_VIEW_H : ART_SIZE);
        if (!cf.slide) return;
        for (i = 0; i < n; ++i) {
            void *img = image_create(cf.slide, 0, 0, 0, 0);
            if (!img) break;
            image_set_draw_type(img, IMAGE_SCALE_AUTO);
        }
        widget_set_sensitive(cf.slide, 0); /* the input layer drives it; it takes no touch */
        cf.input = widget_factory_create_widget(widget_factory(), "view", cf.covers, 0, 0,
                                                CF_VIEW_W, CF_VIEW_H);
        if (cf.input) {
            /* fully transparent, in the string form the assets use */
            widget_set_prop_str(cf.input, "style:normal:bg_color", "#00000000");
            widget_set_prop_str(cf.input, "style:normal:border_color", "#00000000");
            widget_on(cf.input, EVT_POINTER_DOWN, on_pointer, (void *)0);
            widget_on(cf.input, EVT_POINTER_MOVE, on_pointer, (void *)0);
            widget_on(cf.input, EVT_POINTER_UP, on_pointer, (void *)0);
            widget_on(cf.input, EVT_POINTER_ABORT, on_pointer, (void *)0);
            widget_on(cf.input, EVT_AFTER_PAINT, on_paint, (void *)0); /* the frame, on top */
        }
        if (depth) decode(PLACEHOLDER, fx.tex + CF_RING * CF_TEXELS, 0); /* a theme image */
        widget_on(cf.slide, EVT_VALUE_CHANGED, on_changed, (void *)0);
        /* The stock slide_menu starts on item 1, not 0 (its constructor stores 1 in `value`,
         * @0x613970), so a page that wants the first album, or has only one, must set it: the
         * artist's Cover Flow opened on its second album and, with a single album, on item 1 of 1
         * whose captions were then never set. slide_menu_set_value is a no-op for the value it
         * already has. */
        slide_menu_set_value(cf.slide, cf.album);
    }
    show_album();
    widget_invalidate_force(cf.win, (void *)0);
}

/* ---------------------------------------------------------------------------
 * The album view is the stock albuminfo_page (restyled by patch/albuminfo.c and the assets, one
 * view everywhere). A tap on the centre cover does what a stock Albums row does: the stock list
 * the page's own copy was made from goes back into *pdeq_showlist (albuminfo_page_init reads the
 * album row from it), the cover-task list is rebuilt from it (album_page_init's
 * albumcoverinfo_init, which add_albumcover_task indexes) and released, and the page opens with the context
 * the row handler builds, the browsing class in the low 16 bits and the row in the high ones
 * (@0x523d94). Main: loadAlbumList(0xf003, 0), class 0xf003. Scoped: loadAlbumList(0xf004, artist)
 * puts the artist into the browsing record (and the cover-task list is rebuilt for it), class
 * 0xff01; the All albums card is the stock All songs row of that list, which the page loads as the
 * artist's every song. Both repeat on every open: the stock queries since cf.albums were copied
 * may have reused the record.
 *
 * albumcoverinfo_init leaves albumcover_taskstate (0xa05a18) at 2, which parks the cover thread
 * (parse_albumcovertask_thd sleeps while it is 2); only the batch queuers (batchadd_albumcover_task
 * -> local_albumsmallcover_task, run by the stock Albums list right after) set it back to 1, and
 * albuminfo_page_init's add_albumcover_task(row, 1) does not. Without this call the page's cover
 * task waits forever and the header keeps its placeholder. batchadd_albumcover_task(0, 0) queues
 * nothing (the page clears and refills the task list itself) and sets the state to 1; the page's
 * own 500 ms timer (@0x5261d8) then picks the finished /tmp/abp file up.
 */
static void open_album(int index) {
    void *r = album_at((unsigned)index), *list;
    unsigned cls = cf.scoped ? CLASS_ARTIST_ALBUMS : CLASS_ALBUMS;
    if (!r) return;
    snap_stop();
    cf.album = index;
    if (!cf.scoped) cf.saved_album = album_key(r);
    if (cf.scoped) loadAlbumList(CLASS_ARTISTS, deque_at(cf.artist_row, 0));
    else loadAlbumList(CLASS_ALBUMS, (void *)0);
    list = *(void **)PDEQ_SHOWLIST;
    if (!list || (unsigned)index >= deque_size(list)) return;
    albumcoverinfo_init(list);
    batchadd_albumcover_task(0, 0); /* no row queued: it only ends as stock's Albums list does, taskstate = 1 */
    navigator_to_with_context("albuminfo_page", (const void *)(cls | (unsigned)index << 16));
}

/* ---------------------------------------------------------------------------
 * Opening: the album list, then art for the albums with no cache file (q2-pod's first-run build;
 * later opens resume where a cancel left off).
 */
static void blob(const char *path, unsigned *value, int write) {
    void *f = fopen(path, write ? "wb" : "rb");
    if (!f) return;
    if (write) fwrite(value, sizeof *value, 1, f);
    else if (fread(value, sizeof *value, 1, f) != 1) *value = 0;
    fclose(f);
}

static int on_poll(const void *unused) {
    char progress[64];
    (void)unused;
    cf.timer = 0;
    if (cf.done >= cf.total || cf.cancelled) {
        worker_stop(); /* joins the thread's last steps */
        to_covers();
        return RET_OK;
    }
    snprintf(progress, sizeof progress, "Preparing covers... %d/%d", cf.done, cf.total);
    widget_set_text_utf8(cf.status, progress);
    cf.timer = timer_add(on_poll, (void *)0, POLL_MS);
    return RET_OK;
}

static int on_cancel(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (cf.screen != CF_PREPARING) return RET_OK;
    cf.cancelled = 1;
    stop_timer();
    worker_stop();
    to_covers();
    return RET_OK;
}

/* A stock list copied into a deque of our own, so later stock queries cannot pull it away. */
static void *copy_list(void *list) {
    void *d = _create_deque("stSongInfo");
    if (!d) return d;
    deque_init(d);
    deque_assign(d, list);
    return d;
}

/* The albums, exactly as the stock Albums page lists them (loadLocalClassList 0xf003 =
 * getAllAlbum into *pdeq_showlist), copied into a deque of our own so later stock queries (the album page's)
 * cannot pull it away. */
static int load_albums(void) {
    void *list;
    if (loadLocalClassList(CLASS_ALBUMS) <= 0) return 0;
    list = *(void **)PDEQ_SHOWLIST;
    if (!list || !deque_size(list) || !(cf.albums = copy_list(list))) return 0;
    cf.count = deque_size(cf.albums);
    return (int)cf.count;
}

/* One artist's albums, exactly as the stock artist page lists them (loadAlbumList(0xf004, artist),
 * album_page_init), the stock "All songs" row last: kept as the All albums card when there are two
 * albums or more (q2-pod's ARTIST_ALBUMS cards), dropped otherwise. Each album takes the cache key
 * of the library's album of the same name (getAllAlbum groups by name, ASCII case aside, as
 * strcasecmp compares), so the covers are the files the main Cover Flow built and nothing is
 * extracted twice; an album the library list lacks keys itself. */
static int load_artist(void) {
    void *list, *all;
    unsigned n, i, j;
    loadAlbumList(CLASS_ARTISTS, deque_at(cf.artist_row, 0));
    list = *(void **)PDEQ_SHOWLIST;
    n = list ? deque_size(list) : 0;
    if (!n || !(cf.albums = copy_list(list))) return 0;
    if (I(deque_at(cf.albums, n - 1), REC_ID) == ID_ALL_SONGS && n - 1 < 2) --n;
    cf.count = n;
    if (!n || n > MAX_ALBUMS) return (int)n;
    cf.keys = calloc(n, sizeof *cf.keys); /* none: each album keys itself (key_at) */
    all = cf.keys && loadLocalClassList(CLASS_ALBUMS) > 0 ? *(void **)PDEQ_SHOWLIST : (void *)0;
    for (i = 0; cf.keys && i < n; ++i) {
        void *r = deque_at(cf.albums, i), *same = r;
        if (is_card(r)) continue; /* key 0: no art */
        for (j = 0; all && j < deque_size(all); ++j)
            if (!strcasecmp(cf_str(deque_at(all, j), REC_ALBUM), cf_str(r, REC_ALBUM))) {
                same = deque_at(all, j);
                break;
            }
        cf.keys[i] = album_key(same);
    }
    return (int)n;
}

/* Jobs for the albums with no cache file yet. 1 when a build is running and the preparing screen
 * is up, 0 when there is nothing to build (or no card, no space, or no thread). */
static int start_build(void) {
    unsigned n = album_count(), i;
    char path[64];
    cf.done = cf.total = cf.cancelled = 0;
    cf.jobs = calloc(n ? n : 1, sizeof(job_t));
    if (!cf.jobs) return 0;
    for (i = 0; i < n; ++i) {
        void *r = album_at(i);
        job_t *j = &cf.jobs[cf.total];
        unsigned key = key_at(i);
        if (cf.saved_album && key == cf.saved_album) cf.album = (int)i;
        if (!key || !*cf_str(r, REC_PATH) || !access(art_path(path, sizeof path, key, ""), F_OK)) continue;
        j->track = strdup(cf_str(r, REC_PATH));
        if (!j->track) break;
        j->key = key;
        ++cf.total;
    }
    if (!cf.total) {
        worker_stop(); /* nothing to build: free the job array */
        return 0;
    }
    mkdir(ART_DIR, 0755);
    if (!card_space(ART_DIR) || pthread_create(&cf.thread, (void *)0, worker, (void *)0)) {
        worker_stop(); /* no card, no space, or no thread: show what is cached already */
        return 0;
    }
    cf.running = 1;
    cf.screen = CF_PREPARING;
    show(cf.covers, 0);
    show(cf.status, 1);
    show(cf.cancel, 1);
    widget_set_text_utf8(cf.status, "Preparing covers...");
    cf.timer = timer_add(on_poll, (void *)0, POLL_MS);
    return 1;
}

/* Back: preparing -> cancel and covers, covers -> leave the page. */
static int on_back(void *ctx, void *e) {
    (void)ctx; (void)e;
    if (cf.screen == CF_PREPARING) return on_cancel((void *)0, (void *)0);
    navigator_back();
    return RET_OK;
}

static int on_player(void *ctx, void *e) {
    (void)ctx; (void)e;
    on_backtoplayer_onclick((void *)0, (void *)0);
    return RET_OK;
}

/* The window is going: stop the timer, join the worker, free everything we own. Nothing of ours
 * may outlive the page. */
static int on_destroy(void *ctx, void *e) {
    (void)ctx; (void)e;
    stop_timer();
    snap_stop();
    if (cf.dragging) widget_ungrab(cf.covers, cf.input);
    cf.dragging = 0;
    worker_stop();
    fx_close();
    if (cf.saved_album && !cf.scoped) blob(LAST_ALBUM, &cf.saved_album, 1);
    if (cf.albums) deque_destroy(cf.albums);
    if (cf.artist_row) deque_destroy(cf.artist_row);
    free(cf.keys);
    cf.albums = cf.artist_row = (void *)0;
    cf.keys = (unsigned *)0;
    cf.win = cf.covers = cf.slide = cf.input = cf.name = cf.artist = (void *)0;
    cf.status = cf.cancel = (void *)0;
    cf.screen = CF_COVERS;
    cf.album = cf.scoped = 0;
    return RET_OK;
}

static void *bind(const char *name, int (*fn)(void *, void *)) {
    void *w = widget_lookup(cf.win, name, 1);
    if (w && fn) widget_on(w, EVT_CLICK, fn, (void *)0);
    return w;
}

/* The page and its widgets, everything hidden that waits for a screen; -1 if it did not open. */
static int open_page(void) {
    cf.win = window_open("m1pod_cover");
    if (!cf.win) return -1;
    widget_on(cf.win, EVT_DESTROY, on_destroy, (void *)0);
    bind("btn_return", on_back);
    bind("btn_backtoplayer", on_player);
    cf.covers = widget_lookup(cf.win, "view_covers", 1);
    cf.name = widget_lookup(cf.win, "label_album", 1);
    cf.artist = widget_lookup(cf.win, "label_artist", 1);
    cf.status = widget_lookup(cf.win, "label_status", 1);
    cf.cancel = bind("btn_cancel", on_cancel);
    if (!cf.covers || !cf.name || !cf.artist || !cf.status || !cf.cancel) {
        navigator_back(); /* an asset that is not ours: leave rather than work on half a page */
        return -1;
    }
    show(cf.status, 0);
    show(cf.cancel, 0);
    return 0;
}

/* n albums loaded: their covers (after building the missing art), else `empty` or "too large". */
static int open_covers(int n, const char *empty) {
    if (n <= 0 || n > MAX_ALBUMS) {
        show(cf.covers, 0);
        show(cf.status, 1);
        widget_set_text_utf8(cf.name, "");
        widget_set_text_utf8(cf.artist, "");
        widget_set_text_utf8(cf.status, n > 0 ? "Library too large" : empty);
        cf.screen = CF_COVERS;
        return 0;
    }
    if (!cf.scoped) blob(LAST_ALBUM, &cf.saved_album, 0); /* the last album outlives a reboot */
    if (!start_build()) to_covers();
    return 0;
}

/* The M1 Pod menu's Cover Flow row. 0 once the page is up, -1 if it could not open (the caller
 * then leaves the menu as it was). */
int coverflow_open(void) {
    if (cf.win) return -1;
    memset(&cf, 0, sizeof cf);
    if (open_page()) return -1;
    return open_covers(load_albums(), "Update Local Music first");
}

/* The Artists list's row `index` of `artists` (patch/artists.c; the caller keeps its list): the
 * same page on that artist's albums, titled with the artist (q2-pod's coverflow_artist). Back
 * leaves it for the list. 0 once the page is up, -1 if it could not open. */
int coverflow_artist(void *artists, unsigned index) {
    void *row = artists && index < deque_size(artists) ? deque_at(artists, index) : (void *)0, *title;
    if (cf.win || !row) return -1;
    memset(&cf, 0, sizeof cf);
    cf.scoped = ARTIST_ALBUMS;
    cf.artist_row = _create_deque("stSongInfo");
    if (!cf.artist_row) return -1;
    deque_init(cf.artist_row);
    _deque_push_back(cf.artist_row, row); /* a copy, as the stock queries push rows */
    if (open_page()) {
        if (!cf.win) { /* else the window's on_destroy frees it */
            deque_destroy(cf.artist_row);
            cf.artist_row = (void *)0;
        }
        return -1;
    }
    title = widget_lookup(cf.win, "label_title", 1);
    if (title) widget_set_text_utf8(title, cf_str(row, REC_TITLE));
    return open_covers(load_artist(), "No albums");
}
#endif /* CF_HOST */
