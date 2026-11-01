/* The cover cache and the album helpers Cover Flow and the Albums grid share.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE). The cache design follows q2-pod's Cover Flow.
 *
 * One JPEG per album, /mnt/mmc/.m1plus/covers/<key>-168.jpg, written by the one worker thread below (started by
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
#endif
#include "covercache.h"

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

/* Every destination pixel is the plain average of the source pixels its box covers (from the floor of
 * its start to the ceiling of its end, so neighbouring boxes share an edge pixel at a fractional ratio):
 * a 168 px cover reduced to 92 reads cleanly where nearest sampling would shimmer. */
void cc_box(const unsigned char *data, unsigned w, unsigned h, unsigned stride, const unsigned char *at, unsigned size,
            unsigned *out) {
    unsigned side = w < h ? w : h, x, y, i, j, ro = at[0], go = at[1], bo = at[2], ao = at[3];
    const unsigned char *base = data + (h - side) / 2 * stride + (w - side) / 2 * 4;
    for (y = 0; y < size; ++y) {
        unsigned y0 = y * side / size, y1 = ((y + 1) * side + size - 1) / size;
        stepper_t s0, s1;
        if (y1 > side) y1 = side;
        if (y1 <= y0) y1 = y0 + 1;
        step_init(&s0, 0, side, size); /* x * side / size */
        step_init(&s1, side + size - 1, side, size); /* ((x + 1) * side + size - 1) / size */
        for (x = 0; x < size; ++x, step_next(&s0), step_next(&s1)) {
            unsigned x0 = s0.q, x1 = s1.q, r = 0, g = 0, b = 0, n;
            if (x1 > side) x1 = side;
            if (x1 <= x0) x1 = x0 + 1;
            n = (x1 - x0) * (y1 - y0);
            for (j = y0; j < y1; ++j) {
                const unsigned char *px = base + j * stride + x0 * 4;
                for (i = x0; i < x1; ++i, px += 4) over_black(px, ro, go, bo, ao, &r, &g, &b);
            }
            *out++ = 0xff000000u | r / n | g / n << 8 | b / n << 16;
        }
    }
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

/* ART_DIR/<key>-168.jpg<suffix>: the cache files carry their size, so the 140 px files of the earlier
 * builds are never scaled up. out holds at least 64 bytes. */
char *cc_path(char *out, unsigned size, unsigned key, const char *suffix) {
    snprintf(out, size, ART_DIR "/%08x-" CF_STR(ART_SIZE) ".jpg%s", key, suffix);
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
 * runs loadAlbumdetailList on it and opens ui/m1plus_album.bin); when it cannot (the kill switch, the All albums card, a window that will not open) the stock albuminfo_page,
 * restyled by patch/albuminfo.c, below: the stock list the page's own copy was made from goes back into
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

int cc_sort_artist(void) {
    char b[4];
    int fd = open(CFSORT_FILE, 0, 0), n;
    if (fd < 0) return 1;
    n = read(fd, b, sizeof b);
    close(fd);
    return !(n >= 1 && b[0] == '0' && (n == 1 || (n == 2 && b[1] == '\n'))); /* only "0" / "0\n" is Album */
}

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
 * ART_DIR, and the two stock art functions under parse_cover_mutex, which is the lock every stock caller of them holds
 * (parse_albumcovertask_thd 0x4dd68c, parseplaycover_thd 0x4df1c4). It never touches a widget, a deque or the image manager.
 */
#define MIN_FREE_MB 16 /* no new cache files below this much free space on the card */

typedef struct {
    char *track; /* the album's first track, copied so the thread never reads stock deques */
    unsigned key; /* 0: the one transient job (xf below), not a cache job (cc_build_add refuses key 0) */
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

/* A transient extraction (the Pod's cover pane, docs/modules/ipod.md): the album's art, fitted inside px x px by the stock art call (never upscaled), into xf.dst through
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
    ok = toolsGetAlbumCover(j->track, tmp, xf.px, xf.px) == 1 || toolsGetExternCover(j->track, tmp, xf.px, xf.px) == 1;
    pthread_mutex_unlock((void *)PARSE_COVER_MUTEX);
    if (ok && jpeg_long_side(tmp) >= xf.px) {
        if (rename(tmp, xf.dst)) unlink(tmp);
        return;
    }
    unlink(tmp);
}

static void build_art(const job_t *j) {
    char dst[64], tmp[64];
    int ok;
    void *f;
    if (!j->key) {
        build_file(j);
        return;
    }
    if (access(j->track, F_OK)) return; /* storage gone: no marker, the next open retries */
    cc_path(dst, sizeof dst, j->key, "");
    cc_path(tmp, sizeof tmp, j->key, ".tmp");
    pthread_mutex_lock((void *)PARSE_COVER_MUTEX);
    if (cb.cancelled) { /* cancelled while waiting for the parser: no extraction, no marker */
        pthread_mutex_unlock((void *)PARSE_COVER_MUTEX);
        return;
    }
    ok = toolsGetAlbumCover(j->track, tmp, ART_SIZE, ART_SIZE) == 1 ||
         toolsGetExternCover(j->track, tmp, ART_SIZE, ART_SIZE) == 1;
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
        build_art(&cb.jobs[cb.done]);
        ++cb.done;
    }
    return (void *)0;
}

int cc_build_open(unsigned capacity, int mode) {
    if (cb.jobs) return 0;
    if (capacity > CC_MAX_JOBS) capacity = CC_MAX_JOBS;
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
    if (!cb.jobs || cb.running || !key || !track || !*track) return 0;
    if (cb.mode == CC_MISSING && !access(cc_path(path, sizeof path, key, ""), F_OK)) return 0;
    if ((unsigned)cb.total >= cb.cap) return -1;
    j = &cb.jobs[cb.total];
    j->track = strdup(track);
    if (!j->track) return -1;
    j->key = key;
    ++cb.total;
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
    mkdir(CARD_DIR, 0755); /* the folder, then the cache in it (EEXIST is fine) */
    mkdir(ART_DIR, 0755);
    if (!card_space(ART_DIR) || pthread_create(&cb.thread, (void *)0, cc_worker, (void *)0)) {
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
