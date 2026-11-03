/* Software Update, the pure rules (patch/upver.h; docs/modules/update.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#include "offsets.inc"
#include "stock.h"
#include "upver.h"

#ifndef M1PLUS_VERSION
#error "M1PLUS_VERSION is set by tools/pod.py from tools/build.py VERSION"
#endif

char up_own[UP_TAG] = M1PLUS_VERSION;
int up_dev __attribute__((section(".data.up_dev"))) =
    M1PLUS_DEV; /* (a zero would be .bss, which the payload does not have) */
char up_repo[48] = M1PLUS_REPO;

static unsigned up_len(const char *s) {
    unsigned n = 0;
    while (s[n]) ++n;
    return n;
}

int up_parse(const char *s, unsigned v[3]) {
    int part, digits;
    unsigned n;
    if (!s) return 0;
    for (part = 0; part < 3; ++part) {
        n = 0;
        for (digits = 0; s[digits] >= '0' && s[digits] <= '9'; ++digits) {
            if (digits >= 5) return 0;
            n = n * 10 + (unsigned)(s[digits] - '0');
        }
        if (!digits) return 0;
        v[part] = n;
        s += digits;
        if (part < 2) {
            if (*s != '.') return 0;
            ++s;
        }
    }
    return *s == 0;
}

int up_cmp(const unsigned a[3], const unsigned b[3]) {
    int i;
    for (i = 0; i < 3; ++i)
        if (a[i] != b[i]) return a[i] < b[i] ? -1 : 1;
    return 0;
}

int up_offer(const char *tag, const char *own, int dev) {
    unsigned t[3], o[3];
    if (!up_parse(tag, t)) return 0;
    if (dev) return 2;
    if (!up_parse(own, o)) return 0;
    return up_cmp(t, o) > 0 ? 2 : 1;
}

int up_redirect_tag(const char *loc, const char *repo, char *out, unsigned size) {
    static const char head[] = "https://github.com/", mid[] = "/releases/tag/";
    unsigned v[3], i, n;
    if (!loc || !repo || !out || size < UP_TAG) return 0;
    for (i = 0; head[i]; ++i)
        if (loc[i] != head[i]) return 0;
    loc += i;
    n = up_len(repo);
    for (i = 0; i < n; ++i)
        if (loc[i] != repo[i]) return 0;
    loc += n;
    for (i = 0; mid[i]; ++i)
        if (loc[i] != mid[i]) return 0;
    loc += i;
    if (!up_parse(loc, v)) return 0;
    n = up_len(loc);
    for (i = 0; i <= n; ++i) out[i] = loc[i];
    return 1;
}

/* Octal digits of a tar header field (spaces and NULs after them), -1 when it is anything else. */
static long up_oct(const unsigned char *f, unsigned n) {
    long v = 0;
    unsigned i = 0;
    while (i < n && f[i] == ' ') ++i;
    if (i == n || f[i] < '0' || f[i] > '7') return -1;
    for (; i < n && f[i] >= '0' && f[i] <= '7'; ++i) v = v * 8 + (f[i] - '0');
    for (; i < n; ++i)
        if (f[i] != ' ' && f[i] != 0) return -1;
    return v;
}

int up_info_ok(const char *path, const char *tag) {
    unsigned char hdr[512], body[512];
    char want[96];
    unsigned i, sum = 0, got = 0, size, w = 0;
    unsigned v[3];
    long n, chk;
    int fd, r, ok = 0;
    static const char pre[] = UP_MODEL "\n" UP_PKG_PREFIX;
    if (!up_parse(tag, v)) return 0;
    fd = open(path, O_RDONLY, 0);
    if (fd < 0) return 0;
    while (got < sizeof hdr && (r = read(fd, hdr + got, sizeof hdr - got)) > 0) got += (unsigned)r;
    if (got == sizeof hdr) {
        for (i = 0; i < sizeof hdr; ++i) sum += i >= 148 && i < 156 ? ' ' : hdr[i];
        chk = up_oct(hdr + 148, 8);
        n = up_oct(hdr + 124, 12);
        for (i = 0; UP_INFO[i] && hdr[i] == (unsigned char)UP_INFO[i]; ++i) {
        }
        /* the member is the plain file firmware_v20.info of a tar (magic "ustar", checksum right), small enough to be one block */
        if (!UP_INFO[i] && hdr[i] == 0 && chk >= 0 && (unsigned)chk == sum && hdr[257] == 'u' && hdr[258] == 's' &&
            hdr[259] == 't' && hdr[260] == 'a' && hdr[261] == 'r' && (hdr[156] == '0' || hdr[156] == 0) && n > 0 &&
            n <= (long)sizeof body) {
            size = (unsigned)n;
            got = 0;
            while (got < size && (r = read(fd, body + got, size - got)) > 0) got += (unsigned)r;
            if (got == size) {
                for (i = 0; pre[i]; ++i) want[w++] = pre[i];
                for (i = 0; tag[i] && w < sizeof want - 2; ++i) want[w++] = tag[i];
                want[w++] = '\n';
                ok = size >= w;
                for (i = 0; ok && i < w; ++i) ok = body[i] == (unsigned char)want[i];
            }
        }
    }
    close(fd);
    return ok;
}
