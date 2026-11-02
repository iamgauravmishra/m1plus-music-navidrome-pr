/* The cover cache and the album helpers Cover Flow and the Albums grid share.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE). The cache design follows q2-pod's Cover Flow.
 *
 * One JPEG per album, /mnt/mmc/.m1plus/covers/r<key>-168.jpg, written by the one worker thread below (started by
 * Cover Flow's Preparing screen, its Rebuild Covers, or the Albums page in the background); key = FNV-1a of the artist then the album, so the same album has the same file
 * wherever it is listed. Readers decode through the stock image loader (JPEG and PNG to RGBA8888) and
 * reduce the centred square to the size they draw: nearest for Cover Flow's depth textures, an area
 * average for the grid's small tiles. UI thread only. docs/architecture.md section 4.
 */
#include "offsets.inc"

#ifdef CF_HOST
#include <stdlib.h>
#include <string.h>
#else
#include "stock.h"
#include "home.h"
#include "podcasts.h"
#include "pccover.h"
#endif
#include "covercache.h"
#include "durations.h"

/* FNV-1a over a string, with a separator so "ab"+"c" and "a"+"bc" differ (q2-pod). */
unsigned cc_fnv(unsigned h, const char *s) {
    for (; s && *s; ++s) h = (h ^ (unsigned char)*s) * 16777619u;
    return h * 16777619u;
}

/* One source pixel over black (straight alpha; the offsets of r, g, b, a in the pixel), into the sums. The fully
 * opaque pixel, which is nearly all of them, takes no multiplication. -Oz would call this per pixel. */
static inline __attribute__((always_inline)) void over_black(const unsigned char *px, unsigned ro, unsigned go,
                                                             unsigned bo, unsigned ao, unsigned *r, unsigned *g,
                                                             unsigned *b) {
    unsigned a = px[ao];
    if (a == 255)
        *r += px[ro], *g += px[go], *b += px[bo];
    else
        *r += px[ro] * a / 255, *g += px[go] * a / 255, *b += px[bo] * a / 255;
}

/* floor((start + n * inc) / den) for n = 0, 1, 2, ..., exactly, without a division per step: the quotient and the
 * remainder advance together. A row's x mapping costs two divisions instead of one per pixel. */
typedef struct {
    unsigned q, r, dq, dr, den;
} stepper_t;

static inline __attribute__((always_inline)) void step_init(stepper_t *s, unsigned start, unsigned inc, unsigned den) {
    s->q = start / den, s->r = start % den, s->dq = inc / den, s->dr = inc % den, s->den = den;
}

static inline __attribute__((always_inline)) void step_next(stepper_t *s) {
    s->q += s->dq, s->r += s->dr;
    if (s->r >= s->den) s->r -= s->den, ++s->q;
}

void cc_sample(const unsigned char *data, unsigned w, unsigned h, unsigned stride, const unsigned char *at,
               unsigned size, unsigned *out) {
    unsigned side = w < h ? w : h, x, y, ro = at[0], go = at[1], bo = at[2], ao = at[3];
    const unsigned char *base = data + (h - side) / 2 * stride + (w - side) / 2 * 4;
    for (y = 0; y < size; ++y) {
        const unsigned char *line = base + y * side / size * stride;
        stepper_t sx;
        step_init(&sx, 0, side, size); /* x * side / size */
        for (x = 0; x < size; ++x, step_next(&sx)) {
            unsigned r = 0, g = 0, b = 0;
            over_black(line + sx.q * 4, ro, go, bo, ao, &r, &g, &b);
            *out++ = 0xff000000u | r | g << 8 | b << 16;
        }
    }
}

int ar_init(ar_t *a, unsigned ow, unsigned oh, unsigned tw, unsigned th) {
    if (!ow || !oh || !tw || !th || tw > AR_MAX || ow > 8192 || oh > 8192 || ow * oh > AR_LIMIT) return 0;
    memset(a->acc, 0, tw * 3 * sizeof a->acc[0]);
    a->ow = ow, a->oh = oh, a->tw = tw, a->th = th, a->total = ow * oh, a->j = a->ty = 0, a->rend = oh;
    return 1;
}

/* Target cell k covers [k * ow, (k + 1) * ow) and source pixel i [i * tw, (i + 1) * tw), the same units, so a pixel's share of a cell is an integer: the
 * horizontal sums of one source row (each at most 255 * ow), then the vertical weights the same way over the rows; a pixel or a row meets one cell, or two. */
void ar_push(ar_t *a, const unsigned char *px, unsigned step, unsigned ro, unsigned go, unsigned bo, unsigned ao,
             ar_emit_t emit, void *user) {
    unsigned ow = a->ow, tw = a->tw, i, x, k = 0, cell = ow, p = 0, e, q, *h = a->h;
    memset(h, 0, tw * 3 * sizeof h[0]);
    for (i = 0; i < ow; ++i, px += step) {
        unsigned r = px[ro], g = px[go], b = px[bo], end = p + tw;
        if (ao < step && px[ao] != 255) {
            unsigned al = px[ao];
            r = r * al / 255, g = g * al / 255, b = b * al / 255;
        }
        while (p < end) { /* the part of this pixel in cell k */
            e = end < cell ? end : cell, q = e - p;
            h[3 * k] += q * r, h[3 * k + 1] += q * g, h[3 * k + 2] += q * b;
            p = e;
            if (p == cell) ++k, cell += ow;
        }
    }
    p = a->j++ * a->th;
    for (cell = p + a->th; p < cell;) { /* this row's share of target row ty */
        e = cell < a->rend ? cell : a->rend, q = e - p;
        for (x = 0; x < tw * 3; ++x) a->acc[x] += q * h[x];
        p = e;
        if (p == a->rend) {
            for (x = 0; x < tw * 3; ++x) a->out[x] = (unsigned char)((a->acc[x] + a->total / 2) / a->total);
            memset(a->acc, 0, tw * 3 * sizeof a->acc[0]);
            ++a->ty, a->rend += a->oh;
            emit(user, a->out);
        }
    }
}

typedef struct {
    unsigned *out, size;
} box_out_t;

static void box_emit(void *user, const unsigned char *rgb) {
    box_out_t *o = user;
    unsigned x;
    for (x = 0; x < o->size; ++x, rgb += 3) *o->out++ = 0xff000000u | rgb[0] | rgb[1] << 8 | rgb[2] << 16;
}

/* Every destination pixel is the exact area average of the source its box covers: edge pixels count for the fraction of them inside (ar_push), so a 168 px
 * cover reduced to 144 or 92 reads cleanly where nearest sampling would shimmer, and no ratio blurs more than the box itself. */
void cc_box(const unsigned char *data, unsigned w, unsigned h, unsigned stride, const unsigned char *at, unsigned size,
            unsigned *out) {
    ar_t a;
    unsigned side = w < h ? w : h, y;
    const unsigned char *base = data + (h - side) / 2 * stride + (w - side) / 2 * 4;
    box_out_t o;
    o.out = out, o.size = size;
    if (!ar_init(&a, side, side, size, size)) {
        cc_sample(data, w, h, stride, at, size, out);
        return;
    }
    for (y = 0; y < side; ++y) ar_push(&a, base + y * stride, 4, at[0], at[1], at[2], at[3], box_emit, &o);
}

/* Stock's resize 0x5e00bc (toolsGetAlbumCover / toolsGetExternCover) with the picture decoded to w x h and t the requested size on both sides. The wider side (the
 * width when square) is cut to t when it is over t, the other side follows by single precision division (the FPU sequence at 0x5e0200..0x5e0228 and, for a
 * portrait, 0x5e02c4..0x5e02ec, so the same truncation); a side exactly t falls through to the resize with the plain request, t x t (0x5e02f0..0x5e02f8, a stretch of
 * the other side); a smaller picture is kept as it is (a copy of the file, or the decoded rows encoded again). */
int cc_stock_fit(unsigned w, unsigned h, unsigned t, unsigned *tw, unsigned *th) {
    float f;
    if (w >= h) {
        if (t < w) {
            f = (float)(int)w /
                (float)(int)t; /* (signed: an unsigned conversion would be a libgcc call, which the payload has not) */
            *tw = t, *th = (unsigned)(int)((float)(int)h / f);
        } else if (w == t)
            *tw = *th = t;
        else
            return 0;
    } else {
        if (t < h) {
            f = (float)(int)h / (float)(int)t;
            *th = t, *tw = (unsigned)(int)((float)(int)w / f);
        } else if (h == t)
            *tw = *th = t;
        else
            return 0;
    }
    if (!*tw) *tw = 1;
    if (!*th) *th = 1;
    return 1;
}

void cc_stock_dims(unsigned w0, unsigned h0, unsigned ncomp, unsigned *w, unsigned *h) {
    unsigned m = w0 > h0 ? w0 : h0, d = m < 1024 ? 1 : m <= 2048 ? 2 : m <= 4096 ? 4 : 8;
    if (w0 <= 1024 && h0 <= 1024 && ncomp >= 3) d = 1; /* 0x5de8cc..0x5de8e4: the whole picture */
    *w = (w0 + d - 1) / d, *h = (h0 + d - 1) / d;
}

#ifndef CF_HOST
#define P(r, off) (*(char **)((char *)(r) + (off)))
#define I(r, off) (*(int *)((char *)(r) + (off)))
#define CF_STR_(x) #x
#define CF_STR(x) CF_STR_(x)

const char *cc_str(void *r, int field) {
    const char *s = r ? P(r, field) : (const char *)0;
    return s ? s : "";
}

unsigned cc_key_of(const char *artist, const char *album) {
    unsigned h = cc_fnv(cc_fnv(FNV_SEED, artist), album);
    return h | !h;
}

unsigned cc_album_key(void *r) { return cc_key_of(cc_str(r, REC_ARTIST), cc_str(r, REC_ALBUM)); }

/* ART_DIR/r<key>-168.jpg<suffix>: the cache files carry their size, so the 140 px files of the earlier
 * builds are never scaled up, and the prefix says how the cover was made: r = from an album's first track (what f meant) by the area average of pv_cover (art_embedded, art_folder
 * below). It supersedes f (first track, stock's bilinear resize) and the unprefixed files (any track): neither is read again, so every cover is made once more. Bump the letter when the way a
 * cover is made changes. out holds at least 64 bytes. */
char *cc_path(char *out, unsigned size, unsigned key, const char *suffix) {
    snprintf(out, size, ART_DIR "/r%08x-" CF_STR(ART_SIZE) ".jpg%s", key, suffix);
    return out;
}

long cc_file_size(const char *path) {
    void *f = fopen(path, "rb");
    long size = f && !fseek(f, 0, 2) ? ftell(f) : -1;
    if (f) fclose(f);
    return size;
}

/* The url of key's cache file when it exists and holds a picture (an empty file is the "no art"
 * marker), else NULL. */
const char *cc_url(char *out, unsigned key) {
    if (!key) return (const char *)0;
    memcpy(out, "file://", 8);
    cc_path(out + 7, 73, key, "");
    return cc_file_size(out + 7) > 0 ? out : (const char *)0; /* a missing file does not open: -1 */
}

/* A song's or an album's cover: the cache is keyed by the library's album record, which lists an album once under the artist of
 * one of its tracks, so a track of a compilation (its own artist) finds no file under its own key, and the album of that name has it. */
unsigned cc_cover_key(void *albums, unsigned key, const char *album, char *url) {
    char tmp[80];
    unsigned n = albums ? deque_size(albums) : 0, i;
    if (!url) url = tmp;
    if (cc_url(url, key)) return key;
    for (i = 0; album && *album && i < n; ++i) {
        void *r = deque_at(albums, i);
        if (I(r, REC_ID) != -1 && !cc_nocase(cc_str(r, REC_ALBUM), album) && cc_url(url, cc_album_key(r)))
            return cc_album_key(r);
    }
    url[0] = 0;
    return key;
}

/* A decoded image reduced to size x size over black. Only the four 32-bit formats; the stock loader
 * decodes JPEG and PNG to RGBA8888 with straight alpha. The image manager's copy is only read, and a
 * cover's load is dropped again at once (unload), as the stock cover rows do; w is any widget (the
 * loader needs one). */
int cc_decode(void *w, const char *url, int unload, unsigned size, int box, unsigned *out) {
    static const unsigned char at[4][4] = BITMAP_RGBA_AT;
    unsigned bitmap[32]; /* bitmap_t is 0x48 bytes */
    unsigned iw, ih, format;
    const unsigned char *data;
    memset(bitmap, 0, sizeof bitmap);
    if (widget_load_image(w, url, bitmap)) return 0;
    iw = bitmap[0], ih = bitmap[1];
    format = (unsigned)(*(unsigned short *)((char *)bitmap + BITMAP_FORMAT)) - 1u;
    data = format < 4 && iw && ih && iw <= 4096 && ih <= 4096 ? bitmap_lock_buffer_for_read(bitmap)
                                                              : (const unsigned char *)0;
    if (data) {
        (box ? cc_box : cc_sample)(data, iw, ih, bitmap_get_line_length(bitmap), at[format], size, out);
        bitmap_unlock_buffer(bitmap);
    }
    if (unload) widget_unload_image(w, bitmap);
    return data != (const unsigned char *)0;
}

/* A stock list copied into a deque of our own, so later stock queries cannot pull it away. */
void *cc_copy_list(void *list) {
    void *d = _create_deque("stSongInfo");
    if (!d) return d;
    deque_init(d);
    deque_assign(d, list);
    return d;
}

/* The albums, exactly as the stock Albums page lists them (loadLocalClassList 0xf003 = getAllAlbum into
 * *pdeq_showlist), copied. NULL when the library has none. */
void *cc_albums(void) {
    void *list, *copy;
    if (loadLocalClassList(CLASS_ALBUMS) <= 0) return (void *)0;
    list = *(void **)PDEQ_SHOWLIST;
    if (!list || !deque_size(list)) return (void *)0;
    copy = cc_copy_list(list);
    if (copy && !deque_size(copy)) {
        deque_destroy(copy);
        copy = (void *)0;
    }
    return copy;
}

/* The library's songs as the Songs page lists them (loadLocalClassList 0xf001 = getAllMusic into *pdeq_showlist), copied; NULL when there are none. */
void *cc_songs(void) {
    void *list, *copy;
    if (loadLocalClassList(CLASS_ALL_SONGS) <= 0) return (void *)0;
    list = *(void **)PDEQ_SHOWLIST;
    if (!list || !deque_size(list)) return (void *)0;
    copy = cc_copy_list(list);
    if (copy && !deque_size(copy)) {
        deque_destroy(copy);
        copy = (void *)0;
    }
    return copy;
}

extern int album_open(
    unsigned cls,
    void *
        row); /* patch/albumpage.c: our album page on an album row; 0 opened, -1 not tried, -2 tried and left (the tracks' query replaced the list) */

/* The stock album list the album page is opened from (the Albums rows, or an artist's / composer's): into *pdeq_showlist, the browsing record set. */
static void cc_album_list(void *artist_row, unsigned scope) {
    if (artist_row)
        loadAlbumList(scope == CLASS_COMPOSERS ? CLASS_COMPOSERS : CLASS_ARTISTS, deque_at(artist_row, 0));
    else
        loadAlbumList(CLASS_ALBUMS, (void *)0);
}

/* Open the album page on row `index` of the album list the page was built from, the way a stock Albums row does. Ours first (patch/albumpage.c: album_open takes the album row,
 * runs loadAlbumdetailList on it and opens ui/m1plus_album.bin); when it cannot (the kill switch, the All albums card, a window that will not open) the plain stock albuminfo_page, below:
 * the stock list the page's own copy was made from goes back into
 * *pdeq_showlist (albuminfo_page_init reads the album row from it), the cover-task list is rebuilt
 * from it (album_page_init's albumcoverinfo_init, which add_albumcover_task indexes) and released, and
 * the page opens with the context the row handler builds, the browsing class in the low 16 bits and the
 * row in the high ones (@0x523d94). Library: loadAlbumList(0xf003, 0), class 0xf003. Scoped to an artist
 * (artist_row: a deque holding our copy of the artist's row): loadAlbumList(0xf004, artist) puts the
 * artist into the browsing record (and the cover-task list is rebuilt for it), class 0xff01; the All
 * albums card is the stock All songs row of that list, which the page loads as the artist's every
 * song. Both repeat on every open: the stock queries since our copy was made may have reused the record.
 *
 * albumcoverinfo_init leaves albumcover_taskstate (0xa05a18) at 2, which parks the cover thread
 * (parse_albumcovertask_thd sleeps while it is 2); only the batch queuers (batchadd_albumcover_task ->
 * local_albumsmallcover_task, run by the stock Albums list right after) set it back to 1, and
 * albuminfo_page_init's add_albumcover_task(row, 1) does not. Without this call the page's cover task
 * waits forever and the header keeps its placeholder. batchadd_albumcover_task(0, 0) queues nothing (the
 * page clears and refills the task list itself) and sets the state to 1; the page's own 500 ms timer
 * (@0x5261d8) then picks the finished /tmp/abp file up. Returns -1 when the row is not in the list. */
int cc_open_album(void *artist_row, unsigned scope, int index) {
    void *list;
    int r;
    unsigned cls = !artist_row ? CLASS_ALBUMS : scope == CLASS_COMPOSERS ? CLASS_COMPOSER_ALBUMS : CLASS_ARTIST_ALBUMS;
    cc_album_list(artist_row, scope);
    list = *(void **)PDEQ_SHOWLIST;
    if (!list || (unsigned)index >= deque_size(list)) return -1;
    r = album_open(cls, deque_at(list, (unsigned)index)); /* our page (patch/albumpage.c) */
    if (r == 0) return 0;
    if (r < -1) { /* it queried the tracks: the album list again for the stock page */
        cc_album_list(artist_row, scope);
        list = *(void **)PDEQ_SHOWLIST;
        if (!list || (unsigned)index >= deque_size(list)) return -1;
    }
    albumcoverinfo_init(list);
    batchadd_albumcover_task(0, 0); /* no row queued: it only ends as stock's Albums list does, taskstate = 1 */
    navigator_to_with_context("albuminfo_page", (const void *)(cls | (unsigned)index << 16));
    return 0;
}

/* The row of the library's album list (the stock Albums rows, class 0xf003) whose album is `album` (ASCII case-insensitive:
 * the list groups by album COLLATE NOCASE, so there is one row per name; "Unknown Album", id -1, is never matched), or -1 when
 * the name is empty or no row has it. Loads the list into *PDEQ_SHOWLIST as cc_open_album does and changes nothing else; the
 * row number is what cc_open_album(NULL, 0, row) opens (it loads the list again). */
int cc_find_album(const char *album) {
    void *list;
    unsigned i, n;
    if (!album || !*album) return -1;
    loadAlbumList(CLASS_ALBUMS, (void *)0);
    list = *(void **)PDEQ_SHOWLIST;
    n = list ? deque_size(list) : 0;
    for (i = 0; i < n; i++) {
        void *r = deque_at(list, i);
        if (*(int *)((char *)r + REC_ID) != -1 && !cc_nocase(cc_str(r, REC_ALBUM), album)) return (int)i;
    }
    return -1;
}

/* ---------------------------------------------------------------------------
 * The album order (Settings > Library > Album Order), shared by Cover Flow and the Albums page.
 *
 * Album: the stock list as it is (getAllAlbum: group by album COLLATE NOCASE, so by album title). Artist (the
 * default, iPod style): by the album row's artist, then by album title, each compared ASCII case-insensitively
 * (SQLite's NOCASE, which the stock list groups by) with a leading "The " ignored ("The Beatles" files under B);
 * ties (the same artist and title) keep the stock order, so the order is total and the same on every open. The
 * stock album row carries only the artist of the album's representative track (`select id,album,songer,fileurl`;
 * the album artist is a separate column the Albums query does not fetch), so that is the artist sorted by.
 * The "Unknown Album" row (id -1) stays last. The stock deque is never touched: the sorted view is an array of
 * the rows' stock numbers (a heapsort, no libc callback into the payload), and cc_open_album gets the stock number.
 * The Artist Cover Flow keeps the stock order of an artist's albums (album title, NOCASE: the same query's group by).
 */
static int fold(int c) { return c >= 'A' && c <= 'Z' ? c + 32 : c; }

int cc_nocase(const char *a, const char *b) {
    while (*a && fold((unsigned char)*a) == fold((unsigned char)*b)) ++a, ++b;
    return fold((unsigned char)*a) - fold((unsigned char)*b);
}

/* s without a leading "The " (when something follows it). */
static const char *so_name(const char *s) {
    if (fold((unsigned char)s[0]) == 't' && fold((unsigned char)s[1]) == 'h' && fold((unsigned char)s[2]) == 'e' &&
        s[3] == ' ' && s[4])
        return s + 4;
    return s;
}

/* The name order of both lists (albums by artist and title, the Artists page): ASCII case aside, "The " dropped. */
int cc_name_cmp(const char *a, const char *b) { return cc_nocase(so_name(a), so_name(b)); }
const char *cc_name_key(const char *s) { return so_name(s); }

/* Heapsort of v[0..n) by cmp, which must be total (ties broken by the row numbers in v, so equal names keep the stock
 * order). No libc callback into the payload; no memory. */
static int (*so_less)(unsigned, unsigned) __attribute__((section(".scratch")));

static void so_sift(unsigned *v, unsigned i, unsigned n) {
    for (;;) {
        unsigned c = 2 * i + 1, t;
        if (c >= n) return;
        if (c + 1 < n && so_less(v[c], v[c + 1]) < 0) ++c;
        if (so_less(v[i], v[c]) >= 0) return;
        t = v[i], v[i] = v[c], v[c] = t;
        i = c;
    }
}

void cc_heapsort(unsigned *v, unsigned n, int (*cmp)(unsigned, unsigned)) {
    unsigned i, t;
    so_less = cmp;
    for (i = n / 2; i-- > 0;) so_sift(v, i, n);
    for (i = n; i-- > 1;) {
        t = v[0], v[0] = v[i], v[i] = t;
        so_sift(v, 0, i);
    }
}

static void **so_rec __attribute__((section(".scratch"))); /* the rows being sorted, by stock number */

static int so_cmp(unsigned a, unsigned b) {
    void *ra = so_rec[a], *rb = so_rec[b];
    int ua = I(ra, REC_ID) == -1, ub = I(rb, REC_ID) == -1, d;
    if (ua != ub) return ua - ub;
    d = cc_name_cmp(cc_str(ra, REC_ARTIST), cc_str(rb, REC_ARTIST));
    if (!d) d = cc_name_cmp(cc_str(ra, REC_ALBUM), cc_str(rb, REC_ALBUM));
    return d ? d : a < b ? -1 : a > b;
}

int cc_sort_artist(void) { return set_read(CFSORT_FILE, '1') != '0'; /* only "0" / "0\n" is Album */ }

int cc_sort_set(int artist) {
    artist = artist != 0;
    return home_write_atomic(CFSORT_FILE, CFSORT_TMP, artist ? "1\n" : "0\n") == 0 ? artist : -1;
}

unsigned *cc_album_order(void *albums) {
    unsigned n = albums ? deque_size(albums) : 0, i;
    unsigned *v;
    if (!n || !cc_sort_artist()) return (unsigned *)0;
    v = calloc(n, sizeof *v);
    so_rec = calloc(n, sizeof *so_rec);
    if (!v || !so_rec) {
        free(v);
        free(so_rec);
        so_rec = (void **)0;
        return (unsigned *)0;
    }
    for (i = 0; i < n; ++i) v[i] = i, so_rec[i] = deque_at(albums, i);
    cc_heapsort(v, n, so_cmp);
    free(so_rec);
    so_rec = (void **)0;
    return v;
}

void *cc_row(void *albums, const unsigned *order, unsigned i) { return deque_at(albums, order ? order[i] : i); }

/* The track the player is on: the stock readers (get_playtimeandlength, the lock screen) take the position
 * mclGetPlayPos and the row of the play queue (a deque_t * at PLAY_QUEUE) at it; "queued" is 0 <= position < size. */
void *cc_playing(void) {
    int pos = mclGetPlayPos();
    void *queue = *(void **)PLAY_QUEUE;
    return pos >= 0 && queue && (unsigned)pos < deque_size(queue) ? deque_at(queue, (unsigned)pos) : (void *)0;
}

/* ---------------------------------------------------------------------------
 * The cache builder (see covercache.h): the one worker thread of the app. Moved from Cover Flow unchanged in behaviour.
 *
 * The thread touches only: its own job array (built before it started), the volatile counters below, files under
 * ART_DIR, and the art calls (art_make: taglib_album_picture and our resize, with the two stock art functions as the fallback) under parse_cover_mutex, which is the lock every stock caller holds
 * (parse_albumcovertask_thd 0x4dd68c, parseplaycover_thd 0x4df1c4). It never touches a widget, a deque or the image manager.
 */
#define MIN_FREE_MB 16 /* no new cache files below this much free space on the card */

typedef struct {
    char *track; /* the album's first track, copied so the thread never reads stock deques */
    unsigned
        key; /* 0: the one transient job (xf below), not a cache job (cc_build_add refuses key 0); CC_DURATIONS: the path's dur_key */
    unsigned size,
        sec; /* CC_DURATIONS: the file's size when queued, and its measured seconds (written by the worker before done advances) */
} job_t;

/* The one transient extraction a set may hold instead of cache jobs (cc_build_add_file): where it writes and how big. Set before the worker starts, read only by it. */
static struct {
    char dst[80];
    unsigned px;
} xf __attribute__((section(".scratch")));

static struct {
    job_t *jobs;
    unsigned cap;
    unsigned long thread;
    int mode, running;
    volatile int done, total, cancelled;
} cb __attribute__((section(".scratch")));

/* Whether dir's file system has MIN_FREE_MB free (statfs, MIPS o32 layout: f_bsize is word 1,
 * f_bavail word 7), as q2-pod's card_space. */
static int card_space(const char *dir) {
    unsigned fs[32];
    memset(fs, 0, sizeof fs);
    return !statfs(dir, fs) && (unsigned long long)fs[7] * fs[1] >= (unsigned long long)MIN_FREE_MB << 20;
}

/* The longer side of the JPEG at path (its SOF marker, in the first 4 KB: the stock encoder's files have a short header), 0 when it cannot be read. */
static unsigned jpeg_long_side(const char *path) {
    unsigned char b[4096];
    unsigned n, i = 2, w, h;
    void *f = fopen(path, "rb");
    if (!f) return 0;
    n = (unsigned)fread(b, 1, sizeof b, f);
    fclose(f);
    if (n < 4 || b[0] != 0xff || b[1] != 0xd8) return 0;
    while (i + 9 < n) {
        unsigned m;
        if (b[i] != 0xff) {
            ++i;
            continue;
        }
        m = b[i + 1];
        if (m == 0xff) {
            ++i;
            continue;
        }
        if (m >= 0xc0 && m <= 0xcf && m != 0xc4 && m != 0xc8 && m != 0xcc) {
            h = (unsigned)b[i + 5] << 8 | b[i + 6], w = (unsigned)b[i + 7] << 8 | b[i + 8];
            return w > h ? w : h;
        }
        if (m == 0xd8 || (m >= 0xd0 && m <= 0xd7) || m == 0x01) {
            i += 2;
            continue;
        }
        i += 2 + ((unsigned)b[i + 2] << 8 | b[i + 3]);
    }
    return 0;
}

/* ---- The extraction: stock's two art calls, with the resize replaced. Both run under parse_cover_mutex (the whole call, as stock's do: /tmp/.tmp_picture is shared with the
 * stock threads). Any failure of ours hands the same album to the stock call, so a cover is never lost; a picture smaller than the size (stock copies it, or encodes it again as it is)
 * and an interlaced PNG are stock's too. docs/modules/coverflow.md "Cover resampling". */
#define TAG_TMP \
    "/tmp/.tmp_picture" /* where libtag_c's save_picturefile writes the embedded picture; toolsGetAlbumCover reads and removes it (the string at 0x757838, pinned) */
#define TAG_LIMIT_A \
    0x100000 /* taglib_album_picture's last two arguments, as toolsGetAlbumCover passes them (0x5eaf00, 0x5eaf0c) */
#define TAG_LIMIT_B 0x600000

/* The embedded picture, as toolsGetAlbumCover finds it (taglib_album_picture: 2 a JPEG, 1 a PNG, saved to TAG_TMP), shrunk by pv_cover. No picture: 0, and stock's call is not made (it would
 * ask taglib the same). */
static int art_embedded(const char *track, const char *dst, unsigned px) {
    int kind = taglib_album_picture(track, (char *)dst, TAG_LIMIT_A, TAG_LIMIT_B), r = 0;
    if (kind != 1 && kind != 2) return 0;
    if (!access(TAG_TMP, 4)) r = pv_cover(TAG_TMP, dst, px);
    unlink(TAG_TMP);
    return r == 1 || toolsGetAlbumCover(track, dst, px, px) == 1;
}

#define FL_MAX 48 /* the folder's pictures looked at (a folder of more has its first ones) */
#define FL_NAME 256
#define FL_STOCK_JPEG \
    0x600000 /* toolsGetExternCover (0x5eb760, 0x5eb7bc) passes a picture file by its size in bytes: a PNG up to 1 MiB, a JPEG up to 6 MiB */
#define FL_STOCK_PNG 0x100000

static unsigned fl_len(const char *s) {
    unsigned n = 0;
    while (s[n]) ++n;
    return n;
}

static int fl_ext(const char *name) { /* the last extension is .jpg, .png or .jpeg, any case */
    const char *dot = (const char *)0;
    for (; *name; ++name)
        if (*name == '.') dot = name;
    return dot && (!cc_nocase(dot, ".jpg") || !cc_nocase(dot, ".png") || !cc_nocase(dot, ".jpeg"));
}

/* Stock's choice of the folder picture (toolsGetExternCover 0x5eb314..0x5eb684): the regular files with those extensions, in readdir order; then for each of folder.png, folder.jpg,
 * folder.jpeg, cover.png, cover.jpg, cover.jpeg, <track>.png, <track>.jpg, <track>.jpeg in that order the file of that name (any case) moves to the front, so the order tried is the
 * reverse of that list for the files that exist (<track>.jpeg first, folder.png last of them), then the others as listed. The first whose header is a picture within stock's
 * file size limit goes to pv_cover. 1 when the cover was made; any other outcome is stock's own call (which does the same walk again and handles what is left). */
static int art_folder(const char *track, const char *dst, unsigned px) {
    static const char *const pri[6] = {"folder.png", "folder.jpg", "folder.jpeg",
                                       "cover.png",  "cover.jpg",  "cover.jpeg"};
    static const char *const ext[3] = {".png", ".jpg", ".jpeg"};
    char dir[FL_NAME], base[FL_NAME], path[FL_NAME * 2 + 2], want[FL_NAME + 8], (*names)[FL_NAME];
    int rank[FL_MAX], n = 0, i, p, r = 0, done = 0;
    unsigned len = fl_len(track), slash = len, dot;
    void *d;
    char *ent;
    while (slash && track[slash - 1] != '/') --slash;
    if (!slash || slash >= sizeof dir || len - slash >= FL_NAME) goto stock;
    memcpy(dir, track, slash - 1), dir[slash - 1] = 0;
    memcpy(base, track + slash, len - slash + 1);
    for (dot = fl_len(base); dot && base[dot - 1] != '.'; --dot) {
    }
    if (dot) base[dot - 1] = 0; /* the name without its last extension */
    names = calloc(FL_MAX, FL_NAME);
    d = names ? opendir(dir) : (void *)0;
    if (!d) {
        free(names);
        goto stock;
    }
    while (n < FL_MAX && (ent = readdir(d)) != (char *)0) {
        const char *name = ent + 11; /* struct dirent: d_type at 10, d_name at 11 */
        if (ent[10] != 8 || fl_len(name) >= FL_NAME || !fl_ext(name)) continue;
        memcpy(names[n], name, fl_len(name) + 1);
        rank[n] = 9; /* the others */
        for (p = 0; p < 9; ++p) {
            if (p < 6)
                snprintf(want, sizeof want, "%s", pri[p]);
            else
                snprintf(want, sizeof want, "%s%s", base, ext[p - 6]);
            if (!cc_nocase(name, want)) rank[n] = 8 - p;
        }
        ++n;
    }
    closedir(d);
    for (p = 0; p < 10 && !done; ++p)
        for (i = 0; i < n && !done; ++i) {
            unsigned w, h, sof;
            long size;
            int kind;
            if (rank[i] != p) continue;
            snprintf(path, sizeof path, "%s/%s", dir, names[i]);
            kind = pc_pic_info(path, &w, &h, &sof);
            size = cc_file_size(path);
            if (!(kind == 1 && (sof == 0xc0 || sof == 0xc1 || sof == 0xc2) && size > 0 && size <= FL_STOCK_JPEG) &&
                !(kind == 2 && size > 0 && size <= FL_STOCK_PNG))
                continue;
            r = pv_cover(path, dst, px), done = 1;
        }
    free(names);
    if (r == 1) return 1;
stock:
    return toolsGetExternCover(track, dst, px, px) == 1;
}

/* The album's art at px x px into dst: the embedded picture, else the folder's. */
static int art_make(const char *track, const char *dst, unsigned px) {
    return art_embedded(track, dst, px) || art_folder(track, dst, px);
}

/* A transient extraction (the Pod's cover pane, docs/modules/ipod.md): the album's art, fitted inside px x px by art_make (never upscaled), into xf.dst through
 * dst.tmp and a rename. A picture whose longer side is under px (a small source) is not kept, and nothing else is written: no cache file, no marker. */
static void build_file(const job_t *j) {
    char tmp[96];
    int ok;
    snprintf(tmp, sizeof tmp, "%s.tmp", xf.dst);
    if (access(j->track, F_OK)) return;
    pthread_mutex_lock((void *)PARSE_COVER_MUTEX);
    if (cb.cancelled) {
        pthread_mutex_unlock((void *)PARSE_COVER_MUTEX);
        return;
    }
    ok = art_make(j->track, tmp, xf.px);
    pthread_mutex_unlock((void *)PARSE_COVER_MUTEX);
    if (ok && jpeg_long_side(tmp) >= xf.px) {
        if (rename(tmp, xf.dst)) unlink(tmp);
        return;
    }
    unlink(tmp);
}

static void build_art(const job_t *j) {
    char dst[64], tmp[64], pick[72];
    int ok;
    void *f;
    if (!j->key) {
        build_file(j);
        return;
    }
    if (access(j->track, F_OK)) return; /* storage gone: no marker, the next open retries */
    cc_path(dst, sizeof dst, j->key, "");
    cc_path(tmp, sizeof tmp, j->key, ".tmp");
    cc_path(pick, sizeof pick, j->key, ".pick");
    if (!access(pick, F_OK) && !access(dst, F_OK))
        return; /* a cover picked in Find Cover & Lyrics (docs/modules/onlineart.md): Rebuild Covers keeps it */
    pthread_mutex_lock((void *)PARSE_COVER_MUTEX);
    if (cb.cancelled) { /* cancelled while waiting for the parser: no extraction, no marker */
        pthread_mutex_unlock((void *)PARSE_COVER_MUTEX);
        return;
    }
    ok = art_make(j->track, tmp, ART_SIZE);
    pthread_mutex_unlock((void *)PARSE_COVER_MUTEX);
    if (ok && cc_file_size(tmp) > 0) {
        if (rename(tmp, dst)) unlink(tmp); /* extracted but not published: no marker, the next open retries */
        return; /* (a rebuild's rename replaces the old picture or marker) */
    }
    unlink(tmp);
    if (access(j->track, F_OK)) return;
    if (!access(dst, F_OK)) return; /* a rebuild that finds no art keeps the file it has */
    f = fopen(dst, "w"); /* an empty file marks "no art": the placeholder shows, no retry */
    if (f) fclose(f);
}

static void *cc_worker(void *unused) {
    (void)unused;
    while (cb.done < cb.total && !cb.cancelled) {
        if (cb.mode == CC_DURATIONS)
            cb.jobs[cb.done].sec = (unsigned)dur_probe(cb.jobs[cb.done].track);
        else
            build_art(&cb.jobs[cb.done]);
        ++cb.done;
    }
    return (void *)0;
}

int cc_build_open(unsigned capacity, int mode) {
    if (cb.jobs) return 0;
    if (capacity > (mode == CC_DURATIONS ? CC_MAX_LEN_JOBS : CC_MAX_JOBS))
        capacity = mode == CC_DURATIONS ? CC_MAX_LEN_JOBS : CC_MAX_JOBS;
    cb.jobs = calloc(capacity ? capacity : 1, sizeof(job_t));
    if (!cb.jobs) return 0;
    cb.cap = capacity;
    cb.mode = mode;
    cb.done = cb.total = cb.cancelled = 0;
    return 1;
}

int cc_build_add(const char *track, unsigned key) {
    char path[64];
    job_t *j;
    if (!cb.jobs || cb.running || cb.mode == CC_DURATIONS || !key || !track || !*track) return 0;
    if (cb.mode == CC_MISSING && !access(cc_path(path, sizeof path, key, ""), F_OK)) return 0;
    if ((unsigned)cb.total >= cb.cap) return -1;
    j = &cb.jobs[cb.total];
    j->track = strdup(track);
    if (!j->track) return -1;
    j->key = key;
    ++cb.total;
    return 1;
}

int cc_build_add_dur(const char *track, unsigned key, unsigned size) {
    int i;
    job_t *j;
    if (!cb.jobs || cb.running || cb.mode != CC_DURATIONS || !key || !track || !*track) return 0;
    for (i = 0; i < cb.total; ++i)
        if (cb.jobs[i].key == key) return 0; /* one file, one measurement (the tracks of a CUE image) */
    if ((unsigned)cb.total >= cb.cap) return -1;
    j = &cb.jobs[cb.total];
    j->track = strdup(track);
    if (!j->track) return -1;
    j->key = key, j->size = size, j->sec = 0;
    ++cb.total;
    return 1;
}

int cc_build_dur(int i, unsigned *key, unsigned *size, unsigned *sec) {
    if (!cb.jobs || cb.mode != CC_DURATIONS || i < 0 || i >= cb.done) return 0;
    *key = cb.jobs[i].key, *size = cb.jobs[i].size, *sec = cb.jobs[i].sec;
    return 1;
}

int cc_build_add_file(const char *track, const char *dst, unsigned px) {
    unsigned n;
    job_t *j;
    if (!cb.jobs || cb.running || cb.total || !track || !*track || !dst || !*dst || !px) return 0;
    j = &cb.jobs[0];
    j->track = strdup(track);
    if (!j->track) return -1;
    j->key = 0;
    for (n = 0; dst[n] && n < sizeof xf.dst - 5; ++n)
        xf.dst[n] = dst[n]; /* (a path that does not fit is cut: the callers' is short) */
    xf.dst[n] = 0;
    xf.px = px;
    cb.total = 1;
    return 1;
}

void cc_build_stop(void) {
    int i;
    if (cb.running) {
        cb.cancelled = 1;
        pthread_join(cb.thread, (void **)0);
        cb.running = 0;
    }
    for (i = 0; i < cb.total; ++i)
        if (cb.jobs) free(cb.jobs[i].track);
    free(cb.jobs);
    cb.jobs = (job_t *)0;
    cb.cap = 0;
    cb.total = cb.done = cb.cancelled = 0;
}

int cc_build_start(void) {
    if (!cb.jobs || cb.running) return 0;
    if (!cb.total) {
        cc_build_stop(); /* nothing to build: free the job array */
        return 0;
    }
    if (cb.mode != CC_DURATIONS) {
        mkdir(CARD_DIR, 0755); /* the folder, then the cache in it (EEXIST is fine) */
        mkdir(ART_DIR, 0755);
    }
    if ((cb.mode != CC_DURATIONS && !card_space(ART_DIR)) ||
        pthread_create(&cb.thread, (void *)0, cc_worker, (void *)0)) {
        cc_build_stop(); /* no card, no space, or no thread: the caller shows what is cached already */
        return 0;
    }
    cb.running = 1;
    return 1;
}

int cc_build_done(void) { return cb.done; }
int cc_build_total(void) { return cb.total; }
int cc_build_running(void) { return cb.running; }
int cc_build_busy(void) { return cb.jobs != (job_t *)0; }

int cc_build_near_step(void *albums, const unsigned *order, unsigned centre, unsigned *cursor, unsigned batch) {
    unsigned n = albums ? deque_size(albums) : 0, c = *cursor, left = batch;
    if (centre >= n) centre = n ? n - 1 : 0;
    while ((c >> 1) < n && left) { /* the cursor is 2 x distance + (0 after the centre, 1 before it) */
        unsigned d = c >> 1, k = c & 1, i;
        void *r;
        ++c;
        if (k ? !d || d > centre : centre + d >= n) continue; /* out of range or d = 0 twice: free */
        i = k ? centre - d : centre + d;
        r = cc_row(albums, order, i);
        --left;
        if (cc_build_add(cc_str(r, REC_PATH), cc_album_key(r)) < 0) c = n << 1; /* full: done */
    }
    *cursor = c;
    return (c >> 1) >= n;
}

int cc_build_near(void *albums, const unsigned *order, unsigned centre) {
    unsigned c = 0;
    cc_build_near_step(albums, order, centre, &c, ~0u);
    return cb.total;
}
#endif /* CF_HOST */
