/* A small, bounded JSON extractor for the iTunes search and lookup answers (patch/pcjson.h; docs/modules/podcasts.md "Search").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#include "offsets.inc"
#include "pcjson.h"

typedef struct {
    const unsigned char *s, *e;
} pj_t;

typedef struct
{ /* where a string goes: out (NULL: nowhere, the string is only skipped), its size, the bytes used, whether something was left out */
    char *out;
    unsigned cap, n;
    int cut;
} pj_out_t;

static void pj_ws(pj_t *p) {
    while (p->s < p->e && (*p->s == ' ' || *p->s == '\t' || *p->s == '\n' || *p->s == '\r')) ++p->s;
}

static int pj_hex(unsigned c) {
    return c >= '0' && c <= '9'   ? (int)(c - '0')
           : c >= 'a' && c <= 'f' ? (int)(c - 'a' + 10)
           : c >= 'A' && c <= 'F' ? (int)(c - 'A' + 10)
                                  : -1;
}

/* The value of the four hex digits at s (all four must be inside the text), -1 for anything else. */
static int pj_hex4(const unsigned char *s, const unsigned char *e) {
    int v = 0, i;
    if (e - s < 4) return -1;
    for (i = 0; i < 4; ++i) {
        int h = pj_hex(s[i]);
        if (h < 0) return -1;
        v = v << 4 | h;
    }
    return v;
}

/* One code point as UTF-8 into the string, whole or not at all: the first one that does not fit (the NUL has its byte) ends what is kept, so the result is always a prefix cut on a character boundary. */
static void pj_put(pj_out_t *o, unsigned cp) {
    unsigned len = cp < 0x80 ? 1 : cp < 0x800 ? 2 : cp < 0x10000 ? 3 : 4;
    char *d;
    if (!o->out || o->cut) return;
    if (o->n + len + 1 > o->cap) {
        o->cut = 1;
        return;
    }
    d = o->out + o->n;
    if (len == 1)
        d[0] = (char)cp;
    else if (len == 2)
        d[0] = (char)(0xc0 | cp >> 6), d[1] = (char)(0x80 | (cp & 0x3f));
    else if (len == 3)
        d[0] = (char)(0xe0 | cp >> 12), d[1] = (char)(0x80 | (cp >> 6 & 0x3f)), d[2] = (char)(0x80 | (cp & 0x3f));
    else
        d[0] = (char)(0xf0 | cp >> 18), d[1] = (char)(0x80 | (cp >> 12 & 0x3f)), d[2] = (char)(0x80 | (cp >> 6 & 0x3f)),
        d[3] = (char)(0x80 | (cp & 0x3f));
    o->n += len;
}

/* The string whose opening quote is at p->s, decoded into o: \" \\ \/ and the escapes of a control character (a space), \uXXXX (a surrogate pair is one character; a lone surrogate, \u0000 and a \u
 * without four hex digits are dropped), a raw control character is a space, a raw byte sequence that is not UTF-8 is dropped. p ends after the closing quote; 0 when the text ends first. */
static int pj_str(pj_t *p, pj_out_t *o) {
    ++p->s;
    for (;;) {
        unsigned c;
        if (p->s >= p->e) return 0;
        c = *p->s++;
        if (c == '"') return 1;
        if (c == '\\') {
            if (p->s >= p->e) return 0;
            c = *p->s++;
            if (c == 'u') {
                int hi = pj_hex4(p->s, p->e);
                if (hi < 0) continue;
                p->s += 4;
                if (hi >= 0xd800 && hi < 0xdc00) { /* needs its low half right behind it */
                    int lo = p->e - p->s >= 2 && p->s[0] == '\\' && p->s[1] == 'u' ? pj_hex4(p->s + 2, p->e) : -1;
                    if (lo >= 0xdc00 && lo < 0xe000) {
                        p->s += 6;
                        pj_put(o, 0x10000u + ((unsigned)(hi - 0xd800) << 10) + (unsigned)(lo - 0xdc00));
                    }
                } else if ((hi >= 0xdc00 && hi < 0xe000) || hi == 0) {
                    continue;
                } else
                    pj_put(o, hi < 0x20 ? ' ' : (unsigned)hi);
            } else if (c == 'n' || c == 'r' || c == 't' || c == 'b' || c == 'f')
                pj_put(o, ' ');
            else if (c >= 0x80)
                --p->s; /* a backslash before a multi-byte character: the character is read as itself */
            else
                pj_put(o, c < 0x20 ? ' ' : c);
        } else if (c < 0x20)
            pj_put(o, ' ');
        else if (c < 0x80)
            pj_put(o, c);
        else {
            int need = c >= 0xf0 ? 3 : c >= 0xe0 ? 2 : c >= 0xc2 ? 1 : 0, i;
            unsigned cp = c & (need == 3 ? 0x07u : need == 2 ? 0x0fu : 0x1fu);
            if (!need || c > 0xf4 || p->e - p->s < need) continue;
            for (i = 0; i < need; ++i) {
                if ((p->s[i] & 0xc0) != 0x80) break;
                cp = cp << 6 | (p->s[i] & 0x3fu);
            }
            if (i < need || (need == 2 && cp < 0x800) || (need == 3 && (cp < 0x10000 || cp > 0x10ffff)) ||
                (cp >= 0xd800 && cp < 0xe000))
                continue; /* the lead byte is dropped; what follows it is read on its own */
            p->s += need;
            pj_put(o, cp);
        }
    }
}

/* One value skipped, at any depth up to PJ_DEPTH, by its brackets and strings. 1 when it ended inside the text, 0 when the text ended (or went too deep, or the value is not one). */
static int pj_skip(pj_t *p) {
    int depth = 0;
    for (;;) {
        unsigned c;
        pj_ws(p);
        if (p->s >= p->e) return 0;
        c = *p->s;
        if (c == '"') {
            pj_out_t none = {(char *)0, 0, 0, 0};
            if (!pj_str(p, &none)) return 0;
        } else if (c == '{' || c == '[') {
            if (++depth > PJ_DEPTH) return 0;
            ++p->s;
            continue;
        } else if (c == '}' || c == ']') {
            if (!depth) return 0;
            ++p->s;
            if (--depth) continue;
            return 1;
        } else if (c == ',' || c == ':') {
            if (!depth) return 0;
            ++p->s;
            continue;
        } else {
            const unsigned char *start = p->s;
            while (p->s < p->e && *p->s != ',' && *p->s != '}' && *p->s != ']' && *p->s != ':' && *p->s != ' ' &&
                   *p->s != '\t' && *p->s != '\n' && *p->s != '\r' && *p->s != '"' && *p->s != '{' && *p->s != '[')
                ++p->s;
            if (p->s == start) return 0;
        }
        if (!depth) return 1;
    }
}

/* A number at p->s: its digits as an unsigned (more than 32 bits: 0xffffffff, a sign, fraction or exponent: the digits before them, a negative number 0); p ends after the token. */
static unsigned pj_num(pj_t *p) {
    unsigned long long v = 0;
    int neg = *p->s == '-', digits = 1;
    while (p->s < p->e && *p->s != ',' && *p->s != '}' && *p->s != ']' && *p->s != ' ' && *p->s != '\t' &&
           *p->s != '\n' && *p->s != '\r') {
        if (*p->s < '0' || *p->s > '9')
            digits = 0;
        else if (digits && v < 0xffffffffull)
            v = v * 10 + (*p->s - '0');
        ++p->s;
    }
    return neg ? 0 : v > 0xffffffffull ? 0xffffffffu : (unsigned)v;
}

static int pj_is(const char *a, const char *b) {
    while (*a && *a == *b) ++a, ++b;
    return *a == *b;
}

/* The object whose '{' is at p->s into r. 1 when its '}' was reached, 0 when the text ended (or it was not an object): then r is not an answer. */
static int pj_obj(pj_t *p, pj_result_t *r) {
    r->id = 0;
    r->name[0] = r->author[0] = r->feed[0] = r->art[0] = 0;
    ++p->s;
    for (;;) {
        char key[24];
        pj_out_t ko, vo;
        int which;
        unsigned c;
        pj_ws(p);
        if (p->s >= p->e) return 0;
        c = *p->s;
        if (c == '}') {
            ++p->s;
            return 1;
        }
        if (c == ',') {
            ++p->s;
            continue;
        }
        if (c != '"') return 0;
        ko.out = key, ko.cap = sizeof key, ko.n = ko.cut = 0;
        if (!pj_str(p, &ko)) return 0;
        key[ko.n] = 0;
        pj_ws(p);
        if (p->s >= p->e || *p->s != ':') return 0;
        ++p->s;
        pj_ws(p);
        if (p->s >= p->e) return 0;
        which = pj_is("collectionId", key)     ? 1
                : pj_is("collectionName", key) ? 2
                : pj_is("artistName", key)     ? 3
                : pj_is("feedUrl", key)        ? 4
                : pj_is("artworkUrl100", key)  ? 5
                                               : 0;
        if (which == 1 && *p->s >= '0' && *p->s <= '9')
            r->id = pj_num(p);
        else if (which >= 2 && *p->s == '"') {
            char *dst = which == 2 ? r->name : which == 3 ? r->author : which == 4 ? r->feed : r->art;
            vo.out = dst, vo.cap = which == 2 ? PJ_NAME : which == 3 ? PJ_AUTHOR : which == 4 ? PC_URL : PJ_ART;
            vo.n = vo.cut = 0;
            if (!pj_str(p, &vo)) return 0;
            dst[vo.n] = 0;
            if (vo.cut && which >= 4) dst[0] = 0; /* a cut address is no address */
        } else if (!pj_skip(p))
            return 0;
    }
}

/* The elements of the array whose '[' has been passed: the objects (the others are skipped) into out, up to max. Returns how many were kept. */
static int pj_array(pj_t *p, pj_result_t *out, int max) {
    int n = 0;
    for (;;) {
        unsigned c;
        pj_ws(p);
        if (p->s >= p->e) return n;
        c = *p->s;
        if (c == ']') {
            ++p->s;
            return n;
        }
        if (c == ',') {
            ++p->s;
            continue;
        }
        if (n >= max) return n;
        if (c == '{') {
            if (!pj_obj(p, &out[n])) return n; /* cut short: not kept */
            if (out[n].name[0] || out[n].feed[0]) ++n;
        } else if (!pj_skip(p))
            return n;
    }
}

int pj_results(const char *json, unsigned n, pj_result_t *out, int max) {
    pj_t p;
    p.s = (const unsigned char *)json, p.e = p.s + n;
    pj_ws(&p);
    if (p.s >= p.e || *p.s != '{' || max <= 0) return -1;
    ++p.s;
    for (;;) {
        char key[16];
        pj_out_t ko;
        unsigned c;
        pj_ws(&p);
        if (p.s >= p.e) return -1;
        c = *p.s;
        if (c == '}') return -1;
        if (c == ',') {
            ++p.s;
            continue;
        }
        if (c != '"') return -1;
        ko.out = key, ko.cap = sizeof key, ko.n = ko.cut = 0;
        if (!pj_str(&p, &ko)) return -1;
        key[ko.n] = 0;
        pj_ws(&p);
        if (p.s >= p.e || *p.s != ':') return -1;
        ++p.s;
        pj_ws(&p);
        if (p.s < p.e && *p.s == '[' && pj_is("results", key)) {
            ++p.s;
            return pj_array(&p, out, max);
        }
        if (!pj_skip(&p)) return -1;
    }
}
