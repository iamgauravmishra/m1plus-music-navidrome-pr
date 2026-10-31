/* M1+ Music Network probe: a developer's check of what the device's network stack can do, before the podcast feeds are built on it
 * (docs/modules/probe.md; the questions are those of docs/modules/podcasts.md "Next: subscribe and download").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Settings > Developer > Network Probe: a tap asks (the stock confirm dialog), Yes starts ONE detached pthread that runs the checks and
 * writes one line per fact to /mnt/mmc/m1plus-probe.log. The thread uses only what demo already imports (libcurl's easy interface,
 * popen, fgets, sleep, pthread_create / pthread_detach); no stock function is hooked, nothing runs at boot, in the main loop or at paint,
 * and the UI is never touched from the thread (the toast and the dialog are the tap's). The kill switch is checked at the tap.
 *
 * What it records:
 *   1. The clock (time, local calendar), the Wi-Fi state (stock get_wifisignal from the tap, the kernel's /proc/net/wireless from the thread), the free RAM, the
 *      addresses, the stock ntpdate result, which CA files exist, a battery reading and the shell's view of /mnt/mmc/.m1plus.
 *   2. HTTPS GETs through libcurl, verification ON, with the CA bundle on the card (PROBE_CA): the iTunes search (TLS version and cipher,
 *      the certificate chain, the times of each phase), the same without a CA file (does libcurl have a built-in one: it should not), a
 *      site with an expired certificate (must fail with 60), a plain http page, and the big feed (redirects, gzip, the streaming speed and
 *      the free RAM at every MiB, which is what the feed parser will have to live with); then each url of PROBE_URLS with a Range
 *      request (do enclosure redirects answer 206).
 *   3. The soak: PROBE_SOAK_N rounds PROBE_SOAK_S seconds apart of: the time, whether the screen is lit, the link line and a small HTTPS GET.
 *      Start it, turn the screen off, wait, and read the log: gaps in the times are the CPU sleeping, failures are the Wi-Fi dropping.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "common.h"
#include "i18n.h"
#include "probe.h"
#include "curlopts.h"

extern void pod_toast(const char *text); /* patch/shuffle.c: the stock message box */
extern int pod_confirm(const char *text); /* patch/m1plus.c: the stock confirm dialog; nonzero for Yes */

#define PR_RDONLY 0
#define SEEK_END_ 2

#define LINE 300
#define DBG_MAX 60 /* verbose lines logged per request */
#define POPEN_LINES 30

struct pctx {
    int fd; /* the log */
    unsigned t0; /* time() at the start */
    int quiet; /* a soak request: one summary line, no verbose lines */
    unsigned dbg; /* verbose lines logged for this request */
    unsigned long long total; /* body bytes of this request */
    unsigned mark; /* the next MiB at which the free RAM is logged */
    unsigned cap; /* the body is cut off beyond this */
    unsigned nhead; /* bytes of the body kept in head */
    int wifi_tap; /* get_wifisignal at the tap */
    char head[160]; /* the first bytes of the body, printable only */
    char tmp[LINE];
    char err[256];
};

static struct {
    int running;
} pr __attribute__((section(".scratch")));

/* ---- log ---- */

static unsigned slen(const char *s) {
    unsigned n = 0;
    while (s[n]) n++;
    return n;
}

static void put(struct pctx *c, const char *s) {
    char line[LINE + 40];
    unsigned now = (unsigned)time((long *)0);
    int n = snprintf(line, sizeof line, "[%u +%u] %s\n", now, now - c->t0, s);
    if (n < 0) return;
    if ((unsigned)n >= sizeof line) n = sizeof line - 1;
    write(c->fd, line, (unsigned)n);
    fsync(c->fd);
}

#define LOGF(c, ...) \
    do { \
        snprintf((c)->tmp, sizeof(c)->tmp, __VA_ARGS__); \
        put((c), (c)->tmp); \
    } while (0)

/* The value (kB) of a /proc/meminfo line such as "MemAvailable:", 0 when absent. */
static unsigned meminfo(const char *key) {
    char buf[1200];
    int fd = open("/proc/meminfo", PR_RDONLY, 0), n, i, j;
    if (fd < 0) return 0;
    n = read(fd, buf, sizeof buf - 1);
    close(fd);
    if (n <= 0) return 0;
    buf[n] = 0;
    for (i = 0; i < n; i++) {
        if (i && buf[i - 1] != '\n') continue;
        for (j = 0; key[j] && buf[i + j] == key[j]; j++) {
        }
        if (key[j]) continue;
        {
            unsigned v = 0;
            for (i += j; buf[i] == ' '; i++) {
            }
            for (; buf[i] >= '0' && buf[i] <= '9'; i++) v = v * 10 + (unsigned)(buf[i] - '0');
            return v;
        }
    }
    return 0;
}

static void log_mem(struct pctx *c, const char *what) {
    LOGF(c, "mem %s: available %u kB, free %u kB", what, meminfo("MemAvailable:"), meminfo("MemFree:"));
}

/* Run a shell command and log its first lines (stderr too). */
static void run(struct pctx *c, const char *cmd) {
    char full[200], line[LINE];
    void *f;
    int n = 0;
    snprintf(full, sizeof full, "%s 2>&1", cmd);
    LOGF(c, "$ %s", cmd);
    f = popen(full, "r");
    if (!f) {
        put(c, "  (popen failed)");
        return;
    }
    while (n < POPEN_LINES && fgets(line, sizeof line, f)) {
        unsigned l = slen(line);
        while (l && (line[l - 1] == '\n' || line[l - 1] == '\r')) line[--l] = 0;
        LOGF(c, "  %s", line);
        n++;
    }
    pclose(f);
}

/* ---- libcurl callbacks (they run in this thread) ---- */

static unsigned wr_cb(char *p, unsigned size, unsigned nmemb, void *user) {
    struct pctx *c = user;
    unsigned len = size * nmemb, i;
    for (i = 0; i < len && c->nhead < sizeof c->head - 1; i++, c->nhead++) {
        unsigned char ch = (unsigned char)p[i];
        c->head[c->nhead] = ch >= 32 && ch < 127 ? (char)ch : ' ';
    }
    c->head[c->nhead] = 0;
    c->total += len;
    if (c->total >= c->mark) {
        c->mark += 1u << 20;
        if (!c->quiet) LOGF(c, "  body %u MiB: available %u kB", (unsigned)(c->total >> 20), meminfo("MemAvailable:"));
    }
    if (c->total > c->cap) return 0; /* the transfer is cut off (a write error) */
    return len;
}

static int dbg_cb(void *h, int type, char *data, unsigned size, void *user) {
    struct pctx *c = user;
    char line[LINE];
    unsigned n = size < sizeof line - 12 ? size : sizeof line - 12;
    (void)h;
    if (c->quiet || (type != CURLINFO_TEXT && type != CURLINFO_HEADER_IN) || c->dbg >= DBG_MAX) return 0;
    c->dbg++;
    memcpy(line, type == CURLINFO_TEXT ? "  . " : "  < ", 4);
    memcpy(line + 4, data, n);
    n += 4;
    while (n > 4 && (line[n - 1] == '\n' || line[n - 1] == '\r')) n--;
    line[n] = 0;
    put(c, line);
    return 0;
}

/* One request. use_ca: set CAINFO to PROBE_CA. range: a Range value or 0. Returns curl's result. */
static int get(struct pctx *c, const char *label, const char *url, const char *range, unsigned cap, int use_ca) {
    void *h = curl_easy_init();
    long code = 0, redirects = 0, verify = -1;
    unsigned long long dl = 0, t_total = 0, t_dns = 0, t_conn = 0, t_tls = 0, t_first = 0;
    const char *eff = 0, *ip = 0;
    unsigned ms, kb;
    int rc;
    if (!c->quiet) LOGF(c, "== %s: %s", label, url);
    if (!h) {
        put(c, "  curl_easy_init failed");
        return -1;
    }
    c->total = 0;
    c->mark = 1u << 20;
    c->cap = cap;
    c->nhead = 0;
    c->head[0] = 0;
    c->dbg = 0;
    c->err[0] = 0;
    if (!c->quiet) log_mem(c, "before");
    curl_easy_setopt(h, CURLOPT_URL, url);
    curl_easy_setopt(h, CURLOPT_WRITEFUNCTION, wr_cb);
    curl_easy_setopt(h, CURLOPT_WRITEDATA, c);
    curl_easy_setopt(h, CURLOPT_DEBUGFUNCTION, dbg_cb);
    curl_easy_setopt(h, CURLOPT_DEBUGDATA, c);
    curl_easy_setopt(h, CURLOPT_VERBOSE, 1);
    curl_easy_setopt(h, CURLOPT_NOPROGRESS, 1);
    curl_easy_setopt(h, CURLOPT_NOSIGNAL, 1); /* a thread: no SIGALRM resolver timeouts */
    curl_easy_setopt(h, CURLOPT_FOLLOWLOCATION, 1);
    curl_easy_setopt(h, CURLOPT_MAXREDIRS, 8);
    curl_easy_setopt(h, CURLOPT_CONNECTTIMEOUT, 20);
    curl_easy_setopt(h, CURLOPT_LOW_SPEED_LIMIT, 1000);
    curl_easy_setopt(h, CURLOPT_LOW_SPEED_TIME, 30);
    curl_easy_setopt(h, CURLOPT_TIMEOUT, cap > (1u << 20) ? 300 : 60);
    curl_easy_setopt(h, CURLOPT_USERAGENT, "M1PlusMusic-probe/1");
    curl_easy_setopt(h, CURLOPT_ERRORBUFFER, c->err);
    if (!range) curl_easy_setopt(h, CURLOPT_ACCEPT_ENCODING, ""); /* every encoding libcurl was built with */
    if (use_ca) curl_easy_setopt(h, CURLOPT_CAINFO, PROBE_CA);
    if (range) curl_easy_setopt(h, CURLOPT_RANGE, range);
    rc = curl_easy_perform(h);
    curl_easy_getinfo(h, CURLINFO_RESPONSE_CODE, &code);
    curl_easy_getinfo(h, CURLINFO_REDIRECT_COUNT, &redirects);
    curl_easy_getinfo(h, CURLINFO_SSL_VERIFYRESULT, &verify);
    curl_easy_getinfo(h, CURLINFO_EFFECTIVE_URL, &eff);
    curl_easy_getinfo(h, CURLINFO_PRIMARY_IP, &ip);
    curl_easy_getinfo(h, CURLINFO_SIZE_DOWNLOAD_T, &dl);
    curl_easy_getinfo(h, CURLINFO_TOTAL_TIME_T, &t_total);
    curl_easy_getinfo(h, CURLINFO_NAMELOOKUP_TIME_T, &t_dns);
    curl_easy_getinfo(h, CURLINFO_CONNECT_TIME_T, &t_conn);
    curl_easy_getinfo(h, CURLINFO_APPCONNECT_TIME_T, &t_tls);
    curl_easy_getinfo(h, CURLINFO_STARTTRANSFER_TIME_T, &t_first);
    ms = (unsigned)t_total / 1000; /* microseconds, low word: good for 71 minutes */
    if (c->quiet) {
        LOGF(c, "  soak get: rc %d http %d %u ms", rc, (int)code, ms);
    } else {
        LOGF(c, "  rc %d (%s) http %d redirects %d verify %d ip %s", rc, curl_easy_strerror(rc), (int)code,
             (int)redirects, (int)verify, ip ? ip : "-");
        LOGF(c, "  url now %s", eff ? eff : "-");
        if (c->err[0]) LOGF(c, "  error buffer: %s", c->err);
        LOGF(c, "  ms: dns %u connect %u tls %u first byte %u total %u", (unsigned)t_dns / 1000,
             (unsigned)t_conn / 1000, (unsigned)t_tls / 1000, (unsigned)t_first / 1000, ms);
        kb = (unsigned)(dl >> 10);
        LOGF(c, "  downloaded %u bytes (%u kB), %u kB/s", (unsigned)dl, kb,
             ms ? kb * 1000 / ms : 0u); /* kb < 4300000: no overflow, no 64 bit divide */
        LOGF(c, "  body starts: %s", c->head);
        log_mem(c, "after");
    }
    curl_easy_cleanup(h);
    return rc;
}

/* ---- the checks ---- */

static void clock_state(struct pctx *c, const char *when) {
    long now = time((long *)0);
    const int *tm = localtime(&now);
    LOGF(c, "clock %s: epoch %u = %d-%d-%d %d:%d:%d local", when, (unsigned)now, tm[5] + 1900, tm[4] + 1, tm[3], tm[2],
         tm[1], tm[0]);
}

static void soak(struct pctx *c) {
    int i;
    put(c, "== soak: turn the screen off now; a gap in the times is the CPU asleep, a failed get is the Wi-Fi gone");
    c->quiet = 1;
    for (i = 1; i <= PROBE_SOAK_N; i++) {
        sleep(PROBE_SOAK_S);
        LOGF(c, "soak %d/%d: epoch %u, screen %s", i, PROBE_SOAK_N, (unsigned)time((long *)0),
             pod_screen_lit() ? "lit" : "dark");
        run(c, "grep wlan0 /proc/net/wireless"); /* the link, read by the kernel and not by the stock status reader */
        get(c, "soak", "https://itunes.apple.com/search?media=podcast&entity=podcast&limit=1&term=news", 0, 65536, 1);
        if (i % 5 == 0) run(c, "cat /sys/class/power_supply/*/capacity /sys/class/power_supply/*/status");
    }
    c->quiet = 0;
}

static void *probe_main(void *arg) {
    struct pctx *c = arg;
    static const char *const cmds[] = {
        "date",
        "uname -a",
        "cat /proc/net/wireless",
        "ifconfig wlan0",
        "cat /etc/resolv.conf",
        "cat /tmp/result_ntpdate",
        "ls -la /etc/ssl /etc/ssl/certs",
        "ls -la /mnt/mmc/.m1plus /mnt/mmc/Podcasts",
        "df /mnt/mmc /mnt/data /tmp",
        "cat /sys/class/power_supply/*/capacity /sys/class/power_supply/*/status",
        "ps",
    };
    char urls[8][PROBE_URL_MAX];
    unsigned i, nurls = 0;
    void *f;
    c->fd = open(PROBE_LOG, O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (c->fd < 0) {
        pr.running = 0;
        free(c);
        return (void *)0;
    }
    c->t0 = (unsigned)time((long *)0);
    put(c, "================ M1+ Music network probe ================");
    clock_state(c, "at the start");
    LOGF(c,
         "wifi: get_wifisignal at the tap %d (-1 = not connected; 2..5 = signal level; asked on the UI thread only, "
         "the stock status reader is not known to be thread safe)",
         c->wifi_tap);
    log_mem(c, "at the start");
    for (i = 0; i < sizeof cmds / sizeof cmds[0]; i++) run(c, cmds[i]);
    f = fopen(PROBE_CA, "r");
    if (f) {
        fseek(f, 0, SEEK_END_);
        LOGF(c, "CA bundle %s: %u bytes", PROBE_CA, (unsigned)ftell(f));
        fclose(f);
    } else
        LOGF(c, "CA bundle %s: MISSING (copy a PEM bundle there; the checks with a CA file will fail with 77)",
             PROBE_CA);

    get(c, "https, CA bundle, the iTunes search (the Add Show path)",
        "https://itunes.apple.com/search?media=podcast&entity=podcast&limit=3&term=daily", 0, 65536, 1);
    get(c, "https, no CA file (libcurl's own default: expect failure 60 or 77)",
        "https://itunes.apple.com/search?media=podcast&entity=podcast&limit=1&term=daily", 0, 65536, 0);
    get(c, "https, expired certificate, CA bundle (must FAIL with 60: verification is on)",
        "https://expired.badssl.com/", 0, 65536, 1);
    get(c, "plain http", "http://neverssl.com/", 0, 65536, 1);
    clock_state(c, "after the first requests");
    get(c, "the big feed (All-In, libsyn: redirects, gzip, speed, RAM)", "https://allinchamathjason.libsyn.com/rss", 0,
        PROBE_FEED_CAP, 1);
    get(c, "a second feed (NYT The Headlines)", "https://feeds.simplecast.com/ydACIPHO", 0, PROBE_FEED_CAP, 1);

    f = fopen(PROBE_URLS, "r");
    if (f) {
        char line[PROBE_URL_MAX];
        while (nurls < 8 && fgets(line, sizeof line, f)) {
            unsigned l = slen(line);
            while (l && (line[l - 1] == '\n' || line[l - 1] == '\r' || line[l - 1] == ' ')) line[--l] = 0;
            if (l < 8 || line[0] == '#') continue;
            memcpy(urls[nurls++], line, l + 1);
        }
        fclose(f);
    } else
        LOGF(c, "no %s (one url a line: enclosure urls to try with a Range request)", PROBE_URLS);
    for (i = 0; i < nurls; i++) get(c, "ranged get of a url from the file (206?)", urls[i], PROBE_RANGE, 262144, 1);

    soak(c);
    clock_state(c, "at the end");
    log_mem(c, "at the end");
    put(c, "================ probe done ================");
    close(c->fd);
    pr.running = 0;
    free(c);
    return (void *)0;
}

/* The Network Probe row was tapped (patch/m1plus.c on_row). */
void probe_start(void) {
    struct pctx *c;
    unsigned long th = 0;
    if (home_off()) return;
    if (pr.running) {
        pod_toast(TR("Network probe is running"));
        return;
    }
    if (!pod_card_mounted()) {
        pod_toast(TR("Storage unavailable"));
        return;
    }
    // clang-format off: a translation key stays on one line (test/pod/i18n.py reads the source)
    if (!pod_confirm(TR("Run the network probe? It takes about 7 minutes and writes m1plus-probe.log to the card. Turn the screen off after it starts.")) ||
        home_off() || pr.running)
        return;
    // clang-format on
    c = calloc(1, sizeof *c);
    if (!c) {
        pod_toast(TR("Network probe failed"));
        return;
    }
    c->wifi_tap = get_wifisignal(); /* the UI thread's own call: stock does the same from its status bar */
    curl_global_init(
        CURL_GLOBAL_ALL); /* stock's curl_init already did; the call is counted, and not thread safe, so it is made here */
    pr.running = 1;
    if (pthread_create(&th, (const void *)0, probe_main, c)) {
        pr.running = 0;
        free(c);
        pod_toast(TR("Network probe failed"));
        return;
    }
    pthread_detach(th);
}
