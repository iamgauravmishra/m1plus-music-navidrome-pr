/* M1+ Music Podcasts on the network: import, refresh one show or all (docs/modules/podcasts.md "Feeds").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * See patch/pcnet.h. One detached worker thread per job: for each show it reads the show file's feed url, streams the feed through libcurl into the push parser (patch/pcfeed.c;
 * verification ON with the CA bundle on the card, redirects followed, gzip accepted, time-outs and a size cap on every request), then writes .episodes and .show atomically (a temp file,
 * fsync, rename) and records the result. The thread touches no widget and calls no stock function; the status record is plain words the page reads on its own timer (a store barrier
 * before the generation counter moves). Only demo's own imports are used (libcurl's easy interface, pthread_create / pthread_detach, open / write / fsync / rename / access).
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
} pn __attribute__((section(".scratch")));

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

int pn_busy(void) { return pn.busy; }
void pn_cancel(void) { pn.cancel = 1; }
int pn_cancelling(void) { return pn.busy && pn.cancel; }
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
    char err[160];
};

static unsigned pn_write(char *d, unsigned size, unsigned nmemb, void *user) {
    struct fx *f = user;
    unsigned len = size * nmemb;
    f->total += len;
    if (f->total > PN_FEED_CAP) return 0; /* a write error: the transfer stops */
    pf_push(f->p, d, len);
    return len;
}

/* libcurl's transfer-info callback (about once a second, and with every chunk): non-zero aborts the transfer (CURLE_ABORTED_BY_CALLBACK). The 64-bit counts are scaled down to
 * 32 bits first (no 64-bit division in the payload). The progress of the show is what the request in progress covers (pn.base, pn.span of 1000) times its share of the answer, when
 * the server told the length; never moves back. */
static int pn_xfer(void *user, long long dt, long long dn, long long ut, long long un) {
    unsigned t, n, p;
    (void)user, (void)ut, (void)un;
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
static void *pn_easy(const char *url, unsigned (*write_cb)(char *, unsigned, unsigned, void *), void *user, char *err) {
    void *h = curl_easy_init();
    if (!h) return h;
    curl_easy_setopt(h, CURLOPT_URL, url);
    curl_easy_setopt(h, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(h, CURLOPT_WRITEDATA, user);
    curl_easy_setopt(h, CURLOPT_ERRORBUFFER, err);
    curl_easy_setopt(h, CURLOPT_NOPROGRESS,
                     0); /* the transfer-info callback below: the dialog's progress and its Cancel */
    curl_easy_setopt(h, CURLOPT_XFERINFOFUNCTION, pn_xfer);
    curl_easy_setopt(h, CURLOPT_XFERINFODATA, 0);
    curl_easy_setopt(h, CURLOPT_NOSIGNAL, 1); /* a thread: no SIGALRM resolver time-outs */
    curl_easy_setopt(h, CURLOPT_FOLLOWLOCATION, 1);
    curl_easy_setopt(h, CURLOPT_MAXREDIRS, 8);
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
    h = pn_easy(url, pn_write, &f, f.err);
    if (!h) return PN_MEM;
    rc = curl_easy_perform(h);
    curl_easy_getinfo(h, CURLINFO_RESPONSE_CODE, &http);
    curl_easy_cleanup(h);
    if (rc == 0) return pf_is_feed(p) ? PN_OK : PN_NOTFEED;
    if (rc == CURLE_HTTP_RETURNED_ERROR) return http == 404 || http == 410 ? PN_GONE : PN_HTTP;
    if (rc == CURLE_ABORTED_BY_CALLBACK) return PN_CANCELLED;
    if (rc == CURLE_WRITE_ERROR) return PN_NOTFEED;
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
    h = pn_easy(url, pn_cwrite, &c, err);
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
                                   eps, PN_EPS_MAX);
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
    pn.busy = 1, pn.done = 0, pn.total = j->n;
    pn.cancel = pn.stopped = 0, pn.ok = pn.fail = pn.part = 0;
    pn_bump();
    if (pthread_create(&th, (const void *)0, pn_main, j)) {
        pn.busy = 0;
        pn_bump();
        free(j);
        return PN_MEM;
    }
    pthread_detach(th);
    return PN_OK;
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
        n = pf_render_show(host, line, "", 0, text, sizeof text);
        if (!pn_save(file, tmp, text, n)) continue;
        seen[nseen++] = hash;
        ++added, ++subs;
    }
    free(buf);
    return added;
}
