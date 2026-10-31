/* M1+ Music Podcasts on the network: import, refresh one show or all (docs/modules/podcasts.md "Feeds").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * See patch/pcnet.h. One detached worker thread per job: for each show it reads the show file's feed url, streams the feed through libcurl into the push parser (patch/pcfeed.c;
 * verification ON with the CA bundle on the card, redirects followed, gzip accepted, time-outs and a size cap on every request), then writes .episodes and .show atomically (a temp file,
 * fsync, rename) and records the result. The thread touches no widget and calls no stock function; the status record is plain words the page reads on its own timer (a store barrier
 * before the generation counter moves). Only demo's own imports are used (libcurl's easy interface, pthread_create / pthread_detach, open / write / fsync / rename / access).
 *
 * Episode downloads (pn_dl_*, "Downloads" below) run on the same kind of thread, one at a time and never beside a refresh. The download policy follows q2-podcasts (MIT licence,
 * github.com/m-d-e-v/q2-podcasts): chunked writes, Range resume, stall limit, retries after 10, 20 and 40 s, a 32 MB free-space margin. The code is our own.
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "podcasts.h"
#include "pcfeed.h"
#include "pcnet.h"
#include "pccover.h"
#include "curlopts.h"

#define PN_PATH 400
#define PN_SHOW_MAX 4096 /* bytes of a show file read */
#define PN_URLS_MAX 16384 /* bytes of subscriptions.txt read */
#define PN_EPS_MAX 65536 /* bytes of .episodes read and written (the model reads at most this much) */

struct pn_job {
    char root[PC_FILE + 20];
    int n;
    char dirs[PC_MAX_SHOWS][PC_FILE];
};

typedef struct {
    unsigned feed, fresh;
    int code;
} pn_stat_t;

static struct {
    volatile int busy, done, total;
    volatile unsigned gen, cur;
    pn_stat_t st[PC_MAX_SHOWS]; /* (the poke of test/pod/pcfeeds.py knows the offsets above; new fields go below) */
    volatile unsigned part, base,
        span; /* the running show: how far along (0..1000, never back), and the part of 1000 the request in progress covers */
    volatile int cancel,
        stopped; /* cancel: asked by the page (read by the worker); stopped: the last job ended because of it */
    volatile unsigned ok, fail; /* the last job: shows refreshed, shows that failed */
    /* Downloads (new fields go below the ones the tests poke). kind: what the running thread does (PN_KIND_*); dpause: the page asked the download thread to stop for a refresh; dcancel: key of the download
     * the page cancelled; dkey / dgot / dtotal / dwait: the one being fetched; dgen / dstep: progress steps; dseq: the queue's order; fails: the words of the failed ones. The page writes slot
     * fields and the thread reads them (a barrier, then the state); the state moves only by compare-and-swap. */
    volatile int kind, dpause, dwait;
    volatile unsigned dcancel, dkey, dgot, dtotal, dgen, dstep, dseq, nfail;
    char droot[PC_FILE + 20];
    struct {
        volatile unsigned state, seq, key;
        char dir[PC_FILE], file[PC_FILE];
    } q[PN_QMAX];
    struct {
        unsigned key;
        int code;
        char dir[PC_FILE], file[PC_FILE]; /* the names, for the Downloads page's rows */
    } fails[PN_FAILS];
} pn __attribute__((section(".scratch")));

enum { PN_KIND_REFRESH = 1, PN_KIND_DL = 2 };
enum { PN_Q_FREE = 0, PN_Q_WAIT = 1, PN_Q_ACTIVE = 2 };

static int pn_eq(const char *a, const char *b) {
    while (*a && *a == *b) ++a, ++b;
    return *a == *b;
}

static int pn_starts(const char *s, const char *prefix) {
    while (*prefix && *s == *prefix) ++s, ++prefix;
    return !*prefix;
}

static int pn_join(char *out, unsigned size, const char *a, const char *b, const char *c) {
    unsigned o = 0, k;
    const char *parts[3];
    int p;
    parts[0] = a, parts[1] = b, parts[2] = c;
    for (p = 0; p < 3; ++p) {
        if (!parts[p]) continue;
        if (p) {
            if (o + 1 >= size) return 0;
            out[o++] = '/';
        }
        for (k = 0; parts[p][k]; ++k) {
            if (o + 1 >= size) return 0;
            out[o++] = parts[p][k];
        }
    }
    out[o] = 0;
    return 1;
}

static void pn_bump(void) {
    __sync_synchronize();
    ++pn.gen;
}

static void pn_set(unsigned feed, int code, unsigned fresh) {
    int i, free_slot = -1;
    for (i = 0; i < PC_MAX_SHOWS; ++i) {
        if (pn.st[i].feed == feed) break;
        if (free_slot < 0 && !pn.st[i].feed) free_slot = i;
    }
    if (i == PC_MAX_SHOWS) i = free_slot < 0 ? 0 : free_slot;
    pn.st[i].feed = feed, pn.st[i].code = code, pn.st[i].fresh = fresh;
    if (code == PN_OK)
        ++pn.ok;
    else
        ++pn.fail;
    pn_bump();
}

int pn_busy(void) { return pn.busy && pn.kind != PN_KIND_DL; }
void pn_cancel(void) { pn.cancel = 1; }
int pn_cancelling(void) { return pn_busy() && pn.cancel; }
unsigned pn_part(void) { return pn.part; }

void pn_summary(unsigned *ok, unsigned *failed, int *cancelled) {
    *ok = pn.ok, *failed = pn.fail, *cancelled = pn.stopped;
}
unsigned pn_gen(void) { return pn.gen; }
unsigned pn_current(void) { return pn.cur; }

void pn_progress(int *done, int *total) {
    *done = pn.done;
    *total = pn.total;
}

int pn_status(unsigned feed, int *code, unsigned *fresh) {
    int i;
    for (i = 0; i < PC_MAX_SHOWS; ++i)
        if (feed && pn.st[i].feed == feed) {
            *code = pn.st[i].code, *fresh = pn.st[i].fresh;
            return 1;
        }
    return 0;
}

int pn_guard(void) {
    if (!pod_card_mounted()) return PN_STORAGE;
    if (get_wifisignal() <= 0) return PN_NOWIFI;
    if ((unsigned)time((long *)0) < PN_MIN_EPOCH) return PN_NOCLOCK;
    if (access(PN_CA, F_OK)) return PN_NOCERT;
    return PN_OK;
}

/* ---------------------------------------------------------------------------
 * Files
 */

/* Up to cap bytes of a file into a heap buffer (a NUL after them); NULL when it is missing or empty. */
static char *pn_slurp(const char *path, unsigned cap, unsigned *n) {
    char *buf;
    int fd = open(path, O_RDONLY, 0), got = 0, r;
    if (fd < 0) return (char *)0;
    buf = calloc(cap + 1, 1);
    while (buf && (unsigned)got < cap && (r = read(fd, buf + got, cap - (unsigned)got)) > 0) got += r;
    close(fd);
    if (!buf || got <= 0) {
        free(buf);
        return (char *)0;
    }
    *n = (unsigned)got;
    return buf;
}

/* data into path atomically: written to tmp, fsynced, renamed over path. 1 on success; a failure leaves no temp file. */
static int pn_save(const char *path, const char *tmp, const char *data, unsigned n) {
    unsigned at = 0;
    int fd = open(tmp, O_WRONLY | O_CREAT | O_TRUNC, 0644), ok = fd >= 0;
    while (ok && at < n) {
        int w = write(fd, data + at, n - at);
        if (w <= 0)
            ok = 0;
        else
            at += (unsigned)w;
    }
    ok = ok && fsync(fd) == 0;
    if (fd >= 0) ok = close(fd) == 0 && ok;
    if (ok && rename(tmp, path)) ok = 0;
    if (!ok) unlink(tmp);
    return ok;
}

/* ---------------------------------------------------------------------------
 * The request
 */
struct fx {
    pf_parser_t *p;
    unsigned long long total;
    int capped; /* the cap was reached: the transfer was stopped there */
    char err[160];
};

/* A feed over PN_FEED_CAP is parsed up to the cap and the transfer stopped there (a write error); feeds list the newest items first, so what was parsed is
 * kept when it holds a feed and an item (pn_fetch). The item cut by the cap is not kept: the parser keeps an item at its end tag only. */
static unsigned pn_write(char *d, unsigned size, unsigned nmemb, void *user) {
    struct fx *f = user;
    unsigned len = size * nmemb;
    if (f->total + len > PN_FEED_CAP) {
        pf_push(f->p, d, (unsigned)(PN_FEED_CAP - f->total));
        f->total = PN_FEED_CAP, f->capped = 1;
        return 0;
    }
    f->total += len;
    pf_push(f->p, d, len);
    return len;
}

/* libcurl's transfer-info callback (about once a second, and with every chunk): non-zero aborts the transfer (CURLE_ABORTED_BY_CALLBACK). The 64-bit counts are scaled down to
 * 32 bits first (no 64-bit division in the payload). The progress of the show is what the request in progress covers (pn.base, pn.span of 1000) times its share of the answer, when
 * the server told the length; never moves back. */
struct dx { /* one download attempt (the write callback's and the transfer-info callback's data) */
    void *h;
    char *buf; /* PN_DL_BUF bytes waiting for their chunk write */
    unsigned used, have, base, key, seen,
        bad; /* have: bytes of the episode got (on the card and in buf); base: where this request's data starts; bad: the PN_* the callbacks refused with */
    char part[PN_PATH];
    char dir[PN_PATH];
    char err[160];
};

/* A download is to stop: the page cancelled it, or asked the thread to pause for a refresh. */
static int pn_dl_stopped(unsigned key) { return pn.dcancel == key || pn.dpause; }

static int pn_xfer(void *user, long long dt, long long dn, long long ut, long long un) {
    unsigned t, n, p;
    (void)ut, (void)un;
    if (user) { /* a download: stop on the page's say; the length the server announced (what follows base) is the total */
        struct dx *d = user;
        if (pn_dl_stopped(d->key)) return 1;
        if (dt > 0 && dt <= (long long)PN_DL_MAX_BYTES) pn.dtotal = d->base + (unsigned)dt;
        return 0;
    }
    if (pn.cancel) return 1;
    if (dt > 0 && dn >= 0) {
        while (dt > 0xffffff) dt >>= 8, dn >>= 8;
        t = (unsigned)dt, n = (unsigned)dn;
        if (n > t) n = t;
        if (t) {
            p = pn.base + pn.span * n / t;
            if (p > pn.part) pn.part = p;
        }
    }
    return 0;
}

/* A configured easy handle for url (NULL: no memory): every request of the worker, feed or picture, is made with these options. Verification stays ON: no SSL_VERIFYPEER / SSL_VERIFYHOST
 * option is ever set. */
static void *pn_easy(const char *url, unsigned (*write_cb)(char *, unsigned, unsigned, void *), void *user, char *err,
                     void *xdata) {
    void *h = curl_easy_init();
    if (!h) return h;
    curl_easy_setopt(h, CURLOPT_URL, url);
    curl_easy_setopt(h, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(h, CURLOPT_WRITEDATA, user);
    curl_easy_setopt(h, CURLOPT_ERRORBUFFER, err);
    curl_easy_setopt(h, CURLOPT_NOPROGRESS,
                     0); /* the transfer-info callback below: the dialog's progress and its Cancel */
    curl_easy_setopt(h, CURLOPT_XFERINFOFUNCTION, pn_xfer);
    curl_easy_setopt(h, CURLOPT_XFERINFODATA, xdata); /* 0: a refresh's request; the attempt of a download otherwise */
    curl_easy_setopt(h, CURLOPT_NOSIGNAL, 1); /* a thread: no SIGALRM resolver time-outs */
    curl_easy_setopt(h, CURLOPT_FOLLOWLOCATION, 1);
    curl_easy_setopt(h, CURLOPT_MAXREDIRS, 16); /* tracking chains reach 8 hops (podtrac, Art19 through 4 counters) */
    curl_easy_setopt(h, CURLOPT_PROTOCOLS, CURLPROTO_HTTP_HTTPS); /* a redirect to file:// or ftp:// is refused */
    curl_easy_setopt(h, CURLOPT_REDIR_PROTOCOLS, CURLPROTO_HTTP_HTTPS);
    curl_easy_setopt(h, CURLOPT_FAILONERROR, 1);
    curl_easy_setopt(h, CURLOPT_CONNECTTIMEOUT, 20);
    curl_easy_setopt(h, CURLOPT_LOW_SPEED_LIMIT, 1000);
    curl_easy_setopt(h, CURLOPT_LOW_SPEED_TIME, 30);
    curl_easy_setopt(h, CURLOPT_TIMEOUT, 120);
    curl_easy_setopt(h, CURLOPT_USERAGENT, "M1PlusMusic/1.0");
    curl_easy_setopt(h, CURLOPT_ACCEPT_ENCODING,
                     ""); /* every encoding libcurl has (gzip: a 3 MB feed is 400 kB on the wire) */
    curl_easy_setopt(h, CURLOPT_CAINFO, PN_CA);
    return h;
}

/* The feed at url through the parser. Returns a PN_* code (PN_OK: the answer was a feed). */
static int pn_fetch(const char *url, pf_parser_t *p) {
    struct fx f;
    void *h;
    long http = 0;
    int rc;
    memset(&f, 0, sizeof f);
    f.p = p;
    h = pn_easy(url, pn_write, &f, f.err, (void *)0);
    if (!h) return PN_MEM;
    rc = curl_easy_perform(h);
    curl_easy_getinfo(h, CURLINFO_RESPONSE_CODE, &http);
    curl_easy_cleanup(h);
    if (rc == 0) return pf_is_feed(p) ? PN_OK : PN_NOTFEED;
    if (rc == CURLE_HTTP_RETURNED_ERROR) return http == 404 || http == 410 ? PN_GONE : PN_HTTP;
    if (rc == CURLE_ABORTED_BY_CALLBACK) return PN_CANCELLED;
    if (rc == CURLE_WRITE_ERROR) return f.capped && pf_is_feed(p) && pf_items(p) > 0 ? PN_OK : PN_NOTFEED;
    if (rc == CURLE_SSL_CACERT || rc == CURLE_SSL_CONNECT_ERROR || rc == CURLE_PEER_FAILED_VERIFICATION ||
        rc == CURLE_SSL_CERTPROBLEM || rc == CURLE_SSL_CIPHER || rc == CURLE_SSL_ISSUER_ERROR)
        return PN_CERT;
    if (rc == CURLE_SSL_CACERT_BADFILE) return PN_NOCERT;
    return PN_NET;
}

/* ---------------------------------------------------------------------------
 * The cover picture (docs/modules/podcasts.md "Cover art")
 */
struct cx {
    int fd;
    unsigned total;
};

static unsigned pn_cwrite(char *d, unsigned size, unsigned nmemb, void *user) {
    struct cx *c = user;
    unsigned len = size * nmemb, at = 0;
    if (len > PN_COVER_CAP || c->total > PN_COVER_CAP - len) return 0; /* a write error: the transfer stops */
    c->total += len;
    while (at < len) {
        int w = write(c->fd, d + at, len - at);
        if (w <= 0) return 0;
        at += (unsigned)w;
    }
    return len;
}

/* The picture at url into the file path (a plain file, not yet a cover). 1 when the whole answer was written; else 0 and no file. */
static int pn_fetch_file(const char *url, const char *path) {
    struct cx c;
    char err[160];
    void *h;
    int rc, ok;
    c.fd = open(path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    c.total = 0;
    if (c.fd < 0) return 0;
    h = pn_easy(url, pn_cwrite, &c, err, (void *)0);
    rc = h ? curl_easy_perform(h) : -1;
    if (h) curl_easy_cleanup(h);
    ok = close(c.fd) == 0 && rc == 0 && c.total > 0;
    if (!ok) unlink(path);
    return ok;
}

/* Whether the show folder has a picture the page would use (the names pc_cover_rank knows; the card is case-insensitive). */
static int pn_has_cover(const char *dir) {
    static const char *const names[] = {"cover.jpg",  "cover.png",  "cover.jpeg",
                                        "folder.jpg", "folder.png", "folder.jpeg"};
    char file[PN_PATH];
    unsigned i;
    for (i = 0; i < sizeof names / sizeof *names; ++i)
        if (pn_join(file, sizeof file, dir, names[i], (const char *)0) && !access(file, F_OK)) return 1;
    return 0;
}

/* The show's cover when its folder has none: the picture at url (the channel image the feed named), downloaded to a hidden file, a JPEG shrunk by pv_shrink (a PNG by pv_shrink_png) to a hidden temp file and
 * renamed to cover.jpg (the page never sees a half file); only an interlaced PNG the page can decode as it is is renamed to cover.png. Whatever fails leaves nothing
 * behind and changes nothing else: the feed's status is its own, the next refresh tries again. */
static void pn_cover(const char *dir, const char *url) {
    char src[PN_PATH], tmp[PN_PATH], dst[PN_PATH];
    unsigned w, h, sof;
    int kind, ok = 0;
    if (!pn_starts(url, "http://") && !pn_starts(url, "https://")) return;
    if (pn_has_cover(dir)) return;
    pn.base = 900, pn.span = 100;
    if (!pn_join(src, sizeof src, dir, ".cover.src", (const char *)0) ||
        !pn_join(tmp, sizeof tmp, dir, ".cover.tmp", (const char *)0))
        return;
    if (!pn_fetch_file(url, src)) return;
    kind = pc_pic_info(src, &w, &h, &sof);
    if (kind == 1) {
        ok = pn_join(dst, sizeof dst, dir, "cover.jpg", (const char *)0) && pv_shrink(src, tmp) && !rename(tmp, dst);
        unlink(tmp);
    } else if (kind == 2) {
        int r = pv_shrink_png(src, tmp);
        if (r > 0)
            ok = pn_join(dst, sizeof dst, dir, "cover.jpg", (const char *)0) && !rename(tmp, dst);
        else if (r < 0)
            ok = pc_cover_ok(src) && pn_join(dst, sizeof dst, dir, "cover.png", (const char *)0) &&
                 !rename(src, dst); /* interlaced: only a small one, as it is */
        unlink(tmp);
    }
    unlink(src);
    if (ok) pn_bump();
}

/* ---------------------------------------------------------------------------
 * One show
 */
static void pn_refresh_one(const struct pn_job *j, const char *dir) {
    char path[PN_PATH], file[PN_PATH], tmp[PN_PATH];
    pc_show_t s;
    pf_parser_t *p;
    char *buf, *old = (char *)0, *eps, shown[PC_TITLE];
    unsigned n, oldn = 0, fresh = 0, feed;
    int code, first;
    if (!pn_join(path, sizeof path, j->root, dir, (const char *)0) ||
        !pn_join(file, sizeof file, path, ".show", (const char *)0))
        return;
    memset(&s, 0, sizeof s);
    buf = pn_slurp(file, PN_SHOW_MAX, &n);
    if (!buf) return;
    pc_parse_show(buf, n, &s);
    free(buf);
    if (!s.feed[0]) return;
    feed = pc_hash(s.feed);
    pn.cur = feed;
    pn.part = 0, pn.base = 0, pn.span = 900; /* the feed is nine tenths of the show, its picture the last tenth */
    pn_bump();
    p = pf_new();
    if (!p) {
        pn_set(feed, PN_MEM, 0);
        pn.cur = 0;
        return;
    }
    code = pn_fetch(s.feed, p);
    if (code ==
        PN_CANCELLED) { /* Cancel: the transfer was aborted, nothing written, the show keeps the status it had */
        pf_free(p);
        pn.cur = 0;
        return;
    }
    if (code == PN_OK) {
        eps = calloc(PN_EPS_MAX + 1, 1);
        if (!eps)
            code = PN_MEM;
        else {
            pn_join(file, sizeof file, path, ".episodes", (const char *)0);
            old = pn_slurp(file, PN_EPS_MAX, &oldn);
            n = pf_render_episodes(p, path, old, oldn, eps, PN_EPS_MAX, &fresh);
            first = s.checked == 0;
            pn_join(tmp, sizeof tmp, path, ".episodes.tmp", (const char *)0);
            if (!pn_save(file, tmp, eps, n))
                code = PN_STORAGE;
            else { /* the show file: the feed's title the first time (the import wrote the host), its picture url; the time of this refresh */
                pn_join(file, sizeof file, path, ".show", (const char *)0);
                pn_join(tmp, sizeof tmp, path, ".show.tmp", (const char *)0);
                memcpy(shown, first && pf_title(p)[0] ? pf_title(p) : s.title, PC_TITLE);
                n = pf_render_show(shown, s.feed, pf_image(p)[0] ? pf_image(p) : s.image, (unsigned)time((long *)0),
                                   pf_author(p)[0] ? pf_author(p) : s.author,
                                   pf_category(p)[0] ? pf_category(p) : s.category,
                                   pf_summary(p)[0] ? pf_summary(p) : s.desc, eps, PN_EPS_MAX);
                if (!pn_save(file, tmp, eps, n))
                    code = PN_STORAGE;
                else {
                    if (pn.part < 900) pn.part = 900;
                    if (first &&
                        !old) { /* nothing of the folder is anyone's yet: it takes the show's name instead of the import's */
                        char name[PC_FILE], to[PN_PATH];
                        pf_folder_name(name, sizeof name, shown);
                        if (name[0] && !pn_eq(name, dir) && pn_join(to, sizeof to, j->root, name, (const char *)0) &&
                            access(to, F_OK) && !rename(path, to))
                            pn_join(path, sizeof path, to, (const char *)0, (const char *)0);
                    }
                    pn_cover(
                        path,
                        pf_image(p)[0]
                            ? pf_image(p)
                            : s.image); /* the feed is done: its picture, when the folder has none; its result is nobody's status */
                }
            }
            free(eps);
            free(old);
        }
    }
    pf_free(p);
    pn_set(feed, code, code == PN_OK ? fresh : 0);
    pn.cur = 0;
}

static void *pn_main(void *arg) {
    struct pn_job *j = arg;
    int i;
    for (i = 0; i < j->n && !pn.cancel; ++i) {
        pn_refresh_one(j, j->dirs[i]);
        pn.done = i + 1;
        pn_bump();
    }
    free(j);
    pn.stopped = pn.cancel;
    pn.kind = 0;
    pn.busy = 0;
    pn_bump();
    return (void *)0;
}

int pn_refresh(const char *root, const pc_show_t *shows, const int *idx, int n) {
    struct pn_job *j;
    unsigned long th = 0;
    int i, g = pn_guard();
    if (pn.busy) return PN_BUSY;
    if (g) return g;
    j = calloc(1, sizeof *j);
    if (!j) return PN_MEM;
    for (i = 0; i < n && j->n < PC_MAX_SHOWS; ++i) {
        const pc_show_t *s = &shows[idx[i]];
        if (!s->feed[0]) continue;
        memcpy(j->dirs[j->n++], s->dir, PC_FILE);
    }
    if (!j->n) {
        free(j);
        return PN_OK;
    }
    pn_join(j->root, sizeof j->root, root, (const char *)0, (const char *)0);
    curl_global_init(
        CURL_GLOBAL_ALL); /* counted, and not thread safe: made here, on the UI thread (stock's own curl_init did it once already) */
    pn.busy = 1, pn.kind = PN_KIND_REFRESH, pn.done = 0, pn.total = j->n;
    pn.cancel = pn.stopped = 0, pn.ok = pn.fail = pn.part = 0;
    pn_bump();
    if (pthread_create(&th, (const void *)0, pn_main, j)) {
        pn.kind = 0;
        pn.busy = 0;
        pn_bump();
        free(j);
        return PN_MEM;
    }
    pthread_detach(th);
    return PN_OK;
}

/* ---------------------------------------------------------------------------
 * Downloads (docs/modules/podcasts.md "Downloads")
 *
 * The policy follows q2-podcasts (MIT licence, github.com/m-d-e-v/q2-podcasts: internal/library/download.go and contrib/shanlingq2/README): one episode at a time; the data is gathered
 * in 512 KB chunks and each chunk is written with open, write, fsync, close, so the card is rarely held busy; a break resumes with an HTTP Range request (a 200 answer starts the file
 * again); 60 s without a byte is a stall; a network failure is retried after 10, 20 and 40 s, while a 404, a web page instead of audio and a full card fail at once; the card keeps
 * 32 MB free (checked before the download and before every chunk); the finished file is renamed into the show folder. The code is our own, over demo's libcurl.
 */
static unsigned pn_len(const char *s) {
    unsigned n = 0;
    while (s[n]) ++n;
    return n;
}

static int pn_cat(char *out, unsigned size, const char *s) {
    unsigned o = pn_len(out), k;
    for (k = 0; s[k]; ++k) {
        if (o + 1 >= size) return 0;
        out[o++] = s[k];
    }
    out[o] = 0;
    return 1;
}

unsigned pn_dl_key(const char *dir, const char *file) {
    char path[PC_FILE * 2 + 2];
    if (!pn_join(path, sizeof path, dir, file, (const char *)0)) return 0;
    return pc_hash(path);
}

static void pn_fail_set(unsigned key, int code, const char *dir, const char *file) {
    unsigned i;
    for (i = 0; i < PN_FAILS; ++i)
        if (pn.fails[i].key == key) break;
    if (i == PN_FAILS) i = pn.nfail++ % PN_FAILS;
    pn.fails[i].key = 0; /* (not a half record while the page reads) */
    memcpy(pn.fails[i].dir, dir, pn_len(dir) + 1);
    memcpy(pn.fails[i].file, file, pn_len(file) + 1);
    pn.fails[i].code = code;
    __sync_synchronize();
    pn.fails[i].key = key;
}

static void pn_fail_clear(unsigned key) {
    unsigned i;
    for (i = 0; i < PN_FAILS; ++i)
        if (pn.fails[i].key == key) pn.fails[i].key = 0;
}

/* The queued download that came first (the lowest sequence number), -1 for none. */
static int pn_next_slot(void) {
    int i, best = -1;
    for (i = 0; i < PN_QMAX; ++i)
        if (pn.q[i].state == PN_Q_WAIT && (best < 0 || (int)(pn.q[i].seq - pn.q[best].seq) < 0)) best = i;
    return best;
}

/* KB free for a non-root user on the file system of path (MIPS o32 statfs: f_bsize is word 1, f_bavail word 7); 0 when statfs fails. */
static int pn_free_kb(const char *path, unsigned *kb) {
    unsigned fs[32];
    unsigned long long b;
    memset(fs, 0, sizeof fs);
    if (statfs(path, fs)) return 0;
    b = (unsigned long long)fs[7] * fs[1] >> 10;
    *kb = b > 0xffffffffull ? 0xffffffffu : (unsigned)b;
    return 1;
}

/* A page instead of audio: any Content-Type of text/..., in any case. */
static int pn_is_text(const char *t) {
    return t && (t[0] | 32) == 't' && (t[1] | 32) == 'e' && (t[2] | 32) == 'x' && (t[3] | 32) == 't' && t[4] == '/';
}

/* Another step of progress for the page (a percent, or a MB when the length is not known): the generation moves. */
static void pn_dl_step(void) {
    unsigned t = pn.dtotal, g = pn.dgot, s;
    s = t > g ? (g >> 10) * 100 / ((t >> 10) ? (t >> 10) : 1) : 1000 + (g >> 20);
    if (s == pn.dstep) return;
    pn.dstep = s;
    __sync_synchronize();
    ++pn.dgen;
}

/* The gathered bytes into the .part file as a chunk of their own (open for append, write, fsync, close), the card keeping its margin. 1 on success, else 0 and d->bad. */
static int pn_dflush(struct dx *d) {
    unsigned kb, at = 0;
    int fd, ok = 1;
    if (!d->used) return 1;
    if (!pn_free_kb(d->dir, &kb)) return d->bad = PN_STORAGE, 0;
    if (kb < PN_DL_MARGIN_KB || kb - PN_DL_MARGIN_KB < (d->used >> 10)) return d->bad = PN_CARDFULL, 0;
    fd = open(d->part, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (fd < 0) return d->bad = PN_STORAGE, 0;
    while (at < d->used) {
        int w = write(fd, d->buf + at, d->used - at);
        if (w <= 0) {
            ok = 0;
            break;
        }
        at += (unsigned)w;
    }
    ok = ok && fsync(fd) == 0;
    ok = close(fd) == 0 && ok;
    if (!ok) return d->bad = PN_STORAGE, 0;
    d->used = 0;
    return 1;
}

static unsigned pn_dwrite(char *data, unsigned size, unsigned nmemb, void *user) {
    struct dx *d = user;
    unsigned len = size * nmemb, at = 0;
    if (!d->seen) { /* the first bytes: the headers are in */
        long code = 0;
        const char *ctype = (const char *)0;
        d->seen = 1;
        curl_easy_getinfo(d->h, CURLINFO_RESPONSE_CODE, &code);
        curl_easy_getinfo(d->h, CURLINFO_CONTENT_TYPE, &ctype);
        if (pn_is_text(ctype)) return d->bad = PN_NOTAUDIO, 0;
        if (d->base && code != 206) { /* the server ignored the Range: the file starts again */
            int fd = open(d->part, O_WRONLY | O_CREAT | O_TRUNC, 0644);
            if (fd < 0 || close(fd)) return d->bad = PN_STORAGE, 0;
            d->base = d->have = 0;
        }
    }
    if (pn_dl_stopped(d->key)) return 0; /* a write error ends the transfer; the caller knows why */
    if (len > PN_DL_MAX_BYTES - d->have) return d->bad = PN_HTTP, 0;
    while (at < len) {
        unsigned n = len - at;
        if (n > PN_DL_BUF - d->used) n = PN_DL_BUF - d->used;
        memcpy(d->buf + d->used, data + at, n);
        d->used += n, at += n;
        if (d->used == PN_DL_BUF && !pn_dflush(d)) return 0;
    }
    d->have += len;
    pn.dgot = d->have;
    pn_dl_step();
    return len;
}

/* One request for the rest of the episode (a Range from the bytes the file has). Returns PN_OK (the whole answer arrived), PN_CANCELLED / PN_PAUSED (the page's say), or the failure; *retry: worth trying
 * again after a wait (the network, a 5xx); *again: the server refused the range (416, a range error): the file may start again, once. The bytes got are on the card when this returns. */
static int pn_dl_attempt(struct dx *d, const char *url, int *retry, int *again) {
    void *h;
    char range[16];
    long http = 0;
    int rc;
    d->seen = d->bad = 0, d->base = d->have, d->used = 0;
    h = pn_easy(url, pn_dwrite, d, d->err, d);
    if (!h) return PN_MEM;
    d->h = h;
    curl_easy_setopt(h, CURLOPT_LOW_SPEED_LIMIT, 1); /* a stall: under 1 byte a second for PN_DL_STALL seconds */
    curl_easy_setopt(h, CURLOPT_LOW_SPEED_TIME, PN_DL_STALL);
    curl_easy_setopt(h, CURLOPT_TIMEOUT, 0); /* no limit on the whole transfer */
    curl_easy_setopt(h, CURLOPT_ACCEPT_ENCODING,
                     "identity"); /* audio is sent as it is: a range of an encoded body would not resume */
    if (d->have) {
        pc_fmt(range, sizeof range, "%d-", d->have);
        curl_easy_setopt(h, CURLOPT_RANGE, range);
    }
    rc = curl_easy_perform(h);
    curl_easy_getinfo(h, CURLINFO_RESPONSE_CODE, &http);
    curl_easy_cleanup(h);
    d->h = (void *)0;
    if (!d->bad)
        pn_dflush(d); /* what arrived goes to the card whatever ended the transfer: the next attempt resumes after it */
    if (d->bad) return d->bad;
    if (rc == 0) return d->have ? PN_OK : PN_HTTP; /* an empty answer is no episode */
    if (pn_dl_stopped(d->key)) return pn.dcancel == d->key ? PN_CANCELLED : PN_PAUSED;
    if (rc == CURLE_HTTP_RETURNED_ERROR) {
        if (http == 404 || http == 410) return PN_GONE;
        if (http == 416) *again = 1;
        if (http >= 500 || http == 408 || http == 429) *retry = 1;
        return PN_HTTP;
    }
    if (rc == CURLE_RANGE_ERROR) return *again = 1, PN_HTTP;
    if (rc == CURLE_SSL_CACERT || rc == CURLE_SSL_CONNECT_ERROR || rc == CURLE_PEER_FAILED_VERIFICATION ||
        rc == CURLE_SSL_CERTPROBLEM || rc == CURLE_SSL_CIPHER || rc == CURLE_SSL_ISSUER_ERROR)
        return PN_CERT;
    if (rc == CURLE_SSL_CACERT_BADFILE) return PN_NOCERT;
    return *retry = 1, PN_NET;
}

/* The bytes the .part file has (it is made when missing: the next chunk appends to it); 0 when it cannot be opened. */
static int pn_part_size(const char *part, unsigned *size) {
    int fd = open(part, O_WRONLY | O_CREAT | O_APPEND, 0644);
    long off;
    if (fd < 0) return 0;
    off = lseek(fd, 0, 2);
    close(fd);
    if (off < 0 || (unsigned long)off > PN_DL_MAX_BYTES) return 0;
    *size = (unsigned)off;
    return 1;
}

/* The slot's episode, to the end: PN_OK when the file is in place, PN_CANCELLED / PN_PAUSED for the page's say, else the failure. */
static int pn_dl_run(struct dx *d, const char *show, const char *name, unsigned key) {
    char file[PN_PATH], eps_path[PN_PATH], url[PF_URL];
    char *eps;
    unsigned n = 0, length = 0, tries = 0, start, kb, i;
    int code, retry, again, restarted = 0;
    if (!pn_join(d->dir, sizeof d->dir, pn.droot, show, (const char *)0) ||
        !pn_join(file, sizeof file, d->dir, name, (const char *)0) || pn_len(file) + sizeof(".part") > PN_DL_PATH_MAX)
        return PN_STORAGE;
    memcpy(d->part, file, pn_len(file) + 1);
    pn_cat(d->part, sizeof d->part, ".part");
    d->key = key;
    if (!access(file, F_OK)) { /* it is on the card already: nothing to fetch, a leftover .part goes */
        unlink(d->part);
        return PN_OK;
    }
    pn_join(eps_path, sizeof eps_path, d->dir, ".episodes", (const char *)0);
    eps = pn_slurp(eps_path, PN_EPS_MAX, &n);
    i = eps && pf_find_episode(eps, n, name, url, sizeof url, &length);
    free(eps);
    if (!i || !(pn_starts(url, "http://") || pn_starts(url, "https://")))
        return PN_GONE; /* the entry is gone, or has no address */
    d->buf = calloc(PN_DL_BUF, 1);
    if (!d->buf) return PN_MEM;
    for (;;) {
        if (!pn_part_size(d->part, &start)) {
            code = PN_STORAGE;
            break;
        }
        d->have = start;
        pn.dgot = start, pn.dtotal = length, pn.dwait = 0, pn.dstep = ~0u;
        pn_dl_step();
        if (!pn_free_kb(d->dir, &kb)) {
            code = PN_STORAGE;
            break;
        }
        if (length > start &&
            kb < PN_DL_MARGIN_KB + ((length - start) >> 10)) { /* the rest of the file would eat into the margin */
            code = PN_CARDFULL;
            break;
        }
        retry = again = 0;
        code = pn_dl_attempt(d, url, &retry, &again);
        if (code == PN_OK) {
            if (rename(d->part, file)) code = PN_STORAGE;
            break;
        }
        if (code == PN_CANCELLED || code == PN_PAUSED) break;
        if (again && !restarted) { /* the range was refused: from the start, once */
            restarted = 1;
            unlink(d->part);
            continue;
        }
        if (!retry) break;
        if (d->have > start) tries = 0; /* it went on a while before it broke: the count starts again */
        if (tries >= PN_DL_RETRIES) break;
        n = 10u << tries++;
        pn.dwait = 1;
        pn_bump();
        for (i = 0; i < n && !pn_dl_stopped(key); ++i) sleep(1);
        pn.dwait = 0;
        if (pn_dl_stopped(key)) {
            code = pn.dcancel == key ? PN_CANCELLED : PN_PAUSED;
            break;
        }
    }
    if (code != PN_OK && (!pn_part_size(d->part, &start) || !start))
        unlink(d->part); /* nothing on the card: no file to say "Paused" */
    free(d->buf);
    return code;
}

/* The worker: the queued downloads in the order they were asked, one at a time, until none is left (or the page asked it to pause for a refresh: then the queue stays). */
static void *pn_dmain(void *arg) {
    int i;
    (void)arg;
    while (!pn.dpause && (i = pn_next_slot()) >= 0) {
        unsigned key = pn.q[i].key;
        struct dx *d;
        int code;
        if (!__sync_bool_compare_and_swap(&pn.q[i].state, PN_Q_WAIT, PN_Q_ACTIVE)) continue; /* the page took it back */
        pn.dkey = key, pn.dgot = pn.dtotal = 0, pn.dwait = 0;
        pn_bump();
        d = calloc(1, sizeof *d);
        code = d ? pn_dl_run(d, pn.q[i].dir, pn.q[i].file, key) : PN_MEM;
        free(d);
        if (code == PN_PAUSED)
            pn.q[i].state = PN_Q_WAIT;
        else {
            if (code != PN_OK && code != PN_CANCELLED) pn_fail_set(key, code, pn.q[i].dir, pn.q[i].file);
            if (pn.dcancel == key) pn.dcancel = 0;
            pn.q[i].state = PN_Q_FREE;
        }
        pn.dkey = 0;
        pn_bump();
    }
    pn.dpause = 0;
    pn.kind = 0;
    pn.busy = 0;
    pn_bump();
    return (void *)0;
}

int pn_dl_start(void) {
    unsigned long th = 0;
    int g, i;
    if (pn.busy || pn_next_slot() < 0)
        return PN_OK; /* a worker is on it (a refresh: the page starts this again when it ends) */
    g = pn_guard();
    if (g) { /* the downloads cannot start: they fail now, with the words of the guard on their rows */
        for (i = 0; i < PN_QMAX; ++i)
            if (pn.q[i].state == PN_Q_WAIT) {
                unsigned key = pn.q[i].key;
                if (__sync_bool_compare_and_swap(&pn.q[i].state, PN_Q_WAIT, PN_Q_FREE))
                    pn_fail_set(key, g, pn.q[i].dir, pn.q[i].file);
            }
        pn_bump();
        return g;
    }
    curl_global_init(CURL_GLOBAL_ALL);
    pn.busy = 1, pn.kind = PN_KIND_DL, pn.dpause = 0;
    pn_bump();
    if (pthread_create(&th, (const void *)0, pn_dmain, (void *)0)) {
        pn.kind = 0;
        pn.busy = 0;
        pn_bump();
        return PN_MEM;
    }
    pthread_detach(th);
    return PN_OK;
}

int pn_dl_add(const char *root, const char *dir, const char *file) {
    unsigned key = pn_dl_key(dir, file), i;
    int free_slot = -1, g;
    char path[PN_PATH];
    if (!key || !file[0] || !pn_join(path, sizeof path, root, dir, file) ||
        pn_len(path) + sizeof(".part") > PN_DL_PATH_MAX)
        return PN_STORAGE;
    for (i = 0; i < PN_QMAX; ++i) {
        if (pn.q[i].state != PN_Q_FREE && pn.q[i].key == key) {
            if (pn.dcancel == key) pn.dcancel = 0; /* asked again before the worker took the cancel: it goes on */
            return PN_OK;
        }
        if (pn.q[i].state == PN_Q_FREE && free_slot < 0) free_slot = (int)i;
    }
    g = pn_guard();
    if (g) return g;
    if (free_slot < 0) return PN_QFULL;
    pn_fail_clear(key);
    if (!pn_eq(pn.droot, root)) pn_join(pn.droot, sizeof pn.droot, root, (const char *)0, (const char *)0);
    memcpy(pn.q[free_slot].dir, dir, pn_len(dir) + 1);
    memcpy(pn.q[free_slot].file, file, pn_len(file) + 1);
    pn.q[free_slot].key = key;
    pn.q[free_slot].seq = ++pn.dseq;
    __sync_synchronize();
    pn.q[free_slot].state = PN_Q_WAIT;
    pn_bump();
    return pn_dl_start();
}

void pn_dl_cancel(unsigned key) {
    int i;
    for (i = 0; i < PN_QMAX; ++i) {
        if (pn.q[i].key != key) continue;
        if (pn.q[i].state == PN_Q_WAIT && __sync_bool_compare_and_swap(&pn.q[i].state, PN_Q_WAIT, PN_Q_FREE)) {
            pn_bump();
            return;
        }
        if (pn.q[i].state == PN_Q_ACTIVE) pn.dcancel = key; /* the worker aborts the transfer and drops it */
    }
}

void pn_dl_pause(void) {
    if (pn_dl_running()) pn.dpause = 1;
}

int pn_dl_running(void) { return pn.busy && pn.kind == PN_KIND_DL; }

int pn_dl_count(void) {
    int i, n = 0;
    for (i = 0; i < PN_QMAX; ++i) n += pn.q[i].state != PN_Q_FREE;
    return n;
}

int pn_dl_waiting(void) {
    int i, n = 0;
    for (i = 0; i < PN_QMAX; ++i) n += pn.q[i].state == PN_Q_WAIT;
    return n;
}

unsigned pn_dl_gen(void) { return pn.dgen; }

int pn_dl_state(unsigned key, int *code, unsigned *got, unsigned *total) {
    int i;
    unsigned g, t;
    for (i = 0; i < PN_QMAX; ++i)
        if (pn.q[i].state != PN_Q_FREE && pn.q[i].key == key) {
            if (pn.q[i].state == PN_Q_WAIT || pn.dwait) return PN_DL_WAIT;
            if (pn.dcancel == key) return PN_DL_NONE; /* cancelled: the worker is about to drop it */
            g = pn.dgot, t = pn.dtotal;
            *got = g, *total = t < g ? 0 : t; /* a length that is too small was wrong: unknown */
            return PN_DL_ACTIVE;
        }
    for (i = 0; i < PN_FAILS; ++i)
        if (pn.fails[i].key == key) {
            *code = pn.fails[i].code;
            return PN_DL_FAILED;
        }
    return PN_DL_NONE;
}

unsigned pn_dl_current(unsigned *got, unsigned *total) {
    unsigned key = pn.dkey;
    int code;
    return key && pn_dl_state(key, &code, got, total) == PN_DL_ACTIVE ? key : 0;
}

void pn_dl_clear(unsigned key) {
    pn_fail_clear(key);
    pn_bump();
}

unsigned pn_dl_listed(int n, char *dir, char *file, int *code) {
    unsigned last = 0;
    int have = 0, i, k;
    for (k = 0;; ++k) { /* the queue in the order it was asked: the lowest sequence number after the last one given */
        int best = -1;
        for (i = 0; i < PN_QMAX; ++i)
            if (pn.q[i].state != PN_Q_FREE && (!have || (int)(pn.q[i].seq - last) > 0) &&
                (best < 0 || (int)(pn.q[i].seq - pn.q[best].seq) < 0))
                best = i;
        if (best < 0) break;
        if (k == n) {
            memcpy(dir, pn.q[best].dir, pn_len(pn.q[best].dir) + 1);
            memcpy(file, pn.q[best].file, pn_len(pn.q[best].file) + 1);
            *code = 0;
            return pn.q[best].key;
        }
        last = pn.q[best].seq, have = 1;
    }
    n -= k;
    for (i = 0; i < PN_FAILS; ++i) /* then the failed ones */
        if (pn.fails[i].key && n-- == 0) {
            memcpy(dir, pn.fails[i].dir, pn_len(pn.fails[i].dir) + 1);
            memcpy(file, pn.fails[i].file, pn_len(pn.fails[i].file) + 1);
            *code = pn.fails[i].code;
            return pn.fails[i].key;
        }
    return 0;
}

/* ---------------------------------------------------------------------------
 * Import
 */
static int pn_ws(char c) { return c == ' ' || c == '\t' || c == '\r' || c == '\n'; }

/* The folder name of a new subscription: the host (letters, digits, dot and dash), a dash and the url's hash in hex. */
static void pn_folder(const char *url, char *out, unsigned size, char *host, unsigned hsize) {
    static const char hex[] = "0123456789abcdef";
    const char *h = url;
    unsigned o = 0, k;
    unsigned hash = pc_hash(url);
    while (*h && *h != '/') ++h; /* "http:" */
    while (*h == '/') ++h;
    for (k = 0; h[k] && h[k] != '/' && h[k] != ':' && h[k] != '?' && h[k] != '#' && k + 1 < hsize; ++k) host[k] = h[k];
    host[k] = 0;
    for (k = 0; host[k] && o + 12 < size && o < 40; ++k) {
        char c = host[k];
        out[o++] = (c >= '0' && c <= '9') || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '.' || c == '-'
                       ? c
                       : '-';
    }
    out[o++] = '-';
    for (k = 0; k < 8; ++k) out[o++] = hex[hash >> (28 - 4 * k) & 15];
    out[o] = 0;
}

int pn_import(const char *root, const pc_show_t *shows, int nshows) {
    char path[PN_PATH], *buf, *p, *stop;
    unsigned n;
    int added = 0, i, subs = nshows;
    unsigned seen[PC_MAX_SHOWS];
    int nseen = 0;
    if (!pn_join(path, sizeof path, root, PN_IMPORT_FILE, (const char *)0)) return -1;
    buf = pn_slurp(path, PN_URLS_MAX, &n);
    if (!buf) return -1;
    stop = buf + n;
    for (p = buf; p < stop && subs < PC_MAX_SHOWS;) {
        char *line = p, *e;
        unsigned len, hash;
        int dup = 0, ok = 1;
        char dir[PC_FILE], host[PC_FILE], show[PN_PATH], file[PN_PATH], tmp[PN_PATH], text[PC_URL + 160];
        while (p < stop && *p != '\n') ++p;
        e = p;
        if (p < stop) ++p;
        while (line < e && pn_ws(*line)) ++line;
        while (e > line && pn_ws(e[-1])) --e;
        len = (unsigned)(e - line);
        if (!len || line[0] == '#') continue;
        if (!((len > 7 && pn_starts(line, "http://")) || (len > 8 && pn_starts(line, "https://"))) || len >= PC_URL)
            continue;
        for (i = 0; i < (int)len; ++i)
            if ((unsigned char)line[i] <= 32) ok = 0;
        if (!ok) continue;
        line[len] = 0;
        for (i = 0; i < nshows; ++i)
            if (pn_eq(shows[i].feed, line)) dup = 1;
        hash = pc_hash(line);
        for (i = 0; i < nseen; ++i)
            if (seen[i] == hash) dup = 1;
        if (dup) continue;
        pn_folder(line, dir, sizeof dir, host, sizeof host);
        if (!pn_join(show, sizeof show, root, dir, (const char *)0)) continue;
        mkdir(show, 0755);
        if (!pn_join(file, sizeof file, show, ".show", (const char *)0) ||
            !pn_join(tmp, sizeof tmp, show, ".show.tmp", (const char *)0))
            continue;
        if (!access(file, F_OK)) continue; /* a folder of this name is already a subscription */
        n = pf_render_show(host, line, "", 0, "", "", "", text, sizeof text);
        if (!pn_save(file, tmp, text, n)) continue;
        seen[nseen++] = hash;
        ++added, ++subs;
    }
    free(buf);
    return added;
}

/* Unsubscribe (the Show page's sheet, docs/modules/podcasts.md "The Show page"): the show's .show again without its feed address, the rest as it was (title, picture, author, category,
 * description, last refresh), written atomically; the .episodes stay (the caller removes what else goes). UI thread; no worker runs a refresh of this show (the page is not refreshing).
 * 1 when written, 0 when the file could not be. */
int pn_unsubscribe(const char *root, const pc_show_t *s) {
    char file[PN_PATH], tmp[PN_PATH], text[PC_URL + PC_URL + 2 * PC_DESC + 320];
    unsigned n;
    if (!pn_join(file, sizeof file, root, s->dir, ".show") || !pn_join(tmp, sizeof tmp, root, s->dir, ".show.tmp"))
        return 0;
    n = pf_render_show(s->title, "", s->image, s->checked, s->author, s->category, s->desc, text, sizeof text);
    return pn_save(file, tmp, text, n);
}
