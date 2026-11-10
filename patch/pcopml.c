/* OPML import and export for the Podcasts subscriptions (patch/pcopml.h; docs/modules/podcasts.md "Subscriptions and OPML").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#include "offsets.inc"
#include "podcasts.h"
#include "pcopml.h"
#include "utf8.h"

typedef unsigned char uc;

typedef struct
{ /* where an attribute's value goes: out (NULL: nowhere, it is only skipped), its size, the bytes used; bad: the value is not usable (a url that does not fit or holds a space) */
    char *out;
    unsigned cap, n;
    int bad, cut, pend, url;
} po_o_t;

static int po_ws(unsigned c) { return c == ' ' || c == '\t' || c == '\n' || c == '\r'; }

static unsigned po_lower(unsigned c) { return c >= 'A' && c <= 'Z' ? c + 32 : c; }

/* Whether the n bytes at s (inside [s, e)) are the lower case word w, whatever their case. */
static int po_is(const uc *s, unsigned n, const char *w) {
    unsigned i;
    for (i = 0; i < n; ++i)
        if (!w[i] || po_lower(s[i]) != (uc)w[i]) return 0;
    return !w[n];
}

static int po_has(const uc *s, const uc *e, const char *w) {
    while (*w && s < e && *s == (uc)*w) ++s, ++w;
    return !*w;
}

/* The first place of the text w in [s, e), NULL when there is none. */
static const uc *po_find(const uc *s, const uc *e, const char *w) {
    for (; s < e; ++s)
        if (po_has(s, e, w)) return s;
    return (const uc *)0;
}

/* One code point as UTF-8 into the value, whole or not at all: the first that does not fit ends what is kept (so a cut is on a character boundary). A url that does not fit is bad. */
static void po_put(po_o_t *o, unsigned cp) {
    unsigned len = m1_utf8_len(cp);
    if (!o->out || o->cut) return;
    if (o->n + len + 1 > o->cap) {
        o->cut = 1;
        if (o->url) o->bad = 1;
        return;
    }
    o->n += m1_utf8_put(o->out + o->n, cp);
    o->out[o->n] = 0;
}

/* A decoded character into a value. White space and control characters: in a title one space between words (none at the ends); in a url leading ones are dropped and a later one makes it bad. */
static void po_char(po_o_t *o, unsigned cp) {
    if (!o->out || o->bad) return;
    if (cp < 32 || cp == 127 || (!o->url && cp == 0xa0)) cp = ' ';
    if (cp == ' ') {
        if (o->n) o->pend = 1;
        return;
    }
    if (o->pend) {
        if (o->url) {
            o->bad = 1;
            return;
        }
        po_put(o, ' ');
        o->pend = 0;
    }
    po_put(o, cp);
}

/* The code point of the UTF-8 sequence at *s (advancing), 0xffffffff for a byte that is no valid start (skipped: overlong, surrogate, past U+10FFFF, a lone continuation or a cut sequence). */
static unsigned po_cp(const uc **sp, const uc *e) {
    const uc *s = *sp;
    unsigned c = *s++, need, cp, min;
    if (c < 0x80) {
        *sp = s;
        return c;
    }
    if (c >= 0xc2 && c < 0xe0)
        need = 1, cp = c & 0x1f, min = 0x80;
    else if (c >= 0xe0 && c < 0xf0)
        need = 2, cp = c & 0x0f, min = 0x800;
    else if (c >= 0xf0 && c < 0xf5)
        need = 3, cp = c & 0x07, min = 0x10000;
    else {
        *sp = s;
        return 0xffffffffu;
    }
    while (need && s < e && (*s & 0xc0) == 0x80) cp = cp << 6 | (*s++ & 0x3f), --need;
    *sp = s;
    if (need || cp < min || cp > 0x10ffff || (cp >= 0xd800 && cp < 0xe000)) return 0xffffffffu;
    return cp;
}

/* The entity at s (just after the &), up to its semicolon inside [s, e): its code point and the bytes used (the semicolon included), 0 bytes for none (the & stays as written). */
static unsigned po_entity(const uc *s, const uc *e, unsigned *used) {
    unsigned n = 0, cp = 0;
    *used = 0;
    while (s + n < e && n < 10 && s[n] != ';') ++n;
    if (s + n >= e || s[n] != ';' || !n) return 0;
    if (po_is(s, n, "amp"))
        cp = '&';
    else if (po_is(s, n, "lt"))
        cp = '<';
    else if (po_is(s, n, "gt"))
        cp = '>';
    else if (po_is(s, n, "quot"))
        cp = '"';
    else if (po_is(s, n, "apos"))
        cp = '\'';
    else if (s[0] == '#' && n > 1) {
        unsigned i = 1, base = 10;
        if (s[1] == 'x' || s[1] == 'X') base = 16, i = 2;
        if (i >= n) return 0;
        for (; i < n; ++i) {
            unsigned c = s[i], d = c >= '0' && c <= '9'   ? c - '0'
                                   : c >= 'a' && c <= 'f' ? c - 'a' + 10
                                   : c >= 'A' && c <= 'F' ? c - 'A' + 10
                                                          : 99;
            if (d >= base) return 0;
            cp = cp * base + d;
            if (cp > 0x10ffff) cp = 0x110000;
        }
        if (!cp || cp > 0x10ffff || (cp >= 0xd800 && cp < 0xe000))
            cp = 0xfffd; /* a character that cannot exist: the replacement character */
    } else
        return 0;
    *used = n + 1;
    return cp;
}

/* The value that starts at s: to the closing quote q (consumed), or with q = 0 to the next white space or '>' (not consumed), decoded into o. Returns where the tag goes on, NULL when the text ends first. */
static const uc *po_value(const uc *s, const uc *e, unsigned q, po_o_t *o) {
    while (s < e) {
        unsigned c = *s;
        if (q ? c == q : (po_ws(c) || c == '>')) return q ? s + 1 : s;
        if (c == '&') {
            unsigned used, cp = po_entity(s + 1, e, &used);
            if (used) {
                po_char(o, cp);
                s += 1 + used;
                continue;
            }
        }
        if (c < 0x80)
            po_char(o, c), ++s;
        else {
            unsigned cp = po_cp(&s, e);
            if (cp != 0xffffffffu) po_char(o, cp);
        }
    }
    return q ? (const uc *)0 : s;
}

/* The end of the declaration that starts at s (just after "<!"): its '>' outside the [ ] of an internal subset; NULL when the text ends first. */
static const uc *po_decl_end(const uc *s, const uc *e) {
    int depth = 0;
    for (; s < e; ++s) {
        if (*s == '[')
            ++depth;
        else if (*s == ']' && depth)
            --depth;
        else if (*s == '>' && !depth)
            return s + 1;
    }
    return (const uc *)0;
}

void po_open(po_t *p, const char *buf, unsigned n) {
    p->s = (const uc *)buf;
    p->e = (const uc *)buf + n;
}

/* An http(s) address, at least one character after the scheme. */
static int po_url_ok(const char *u) {
    unsigned n = 0, i = 0;
    while (u[n]) ++n;
    if (n > 7 && u[0] == 'h' && u[1] == 't' && u[2] == 't' && u[3] == 'p') i = u[4] == 's' ? 5 : 4;
    return i && u[i] == ':' && u[i + 1] == '/' && u[i + 2] == '/' && n > i + 3;
}

int po_next(po_t *p, po_item_t *it) {
    const uc *s = p->s, *e = p->e;
    char alt[PC_TITLE];
    while (s < e) {
        const uc *name;
        unsigned nlen;
        int outline, got_text = 0;
        po_o_t o;
        int url_bad = 0;
        while (s < e && *s != '<') ++s;
        if (s >= e) break;
        ++s;
        if (po_has(s, e, "!--")) {
            s = po_find(s + 3, e, "-->");
            if (!s) break;
            s += 3;
            continue;
        }
        if (po_has(s, e, "![CDATA[")) {
            s = po_find(s + 8, e, "]]>");
            if (!s) break;
            s += 3;
            continue;
        }
        if (s < e && *s == '?') {
            s = po_find(s + 1, e, "?>");
            if (!s) break;
            s += 2;
            continue;
        }
        if (s < e && *s == '!') {
            s = po_decl_end(s + 1, e);
            if (!s) break;
            continue;
        }
        if (s < e && *s == '/') {
            while (s < e && *s != '>') ++s;
            continue;
        }
        name = s;
        while (s < e && !po_ws(*s) && *s != '/' && *s != '>') ++s;
        nlen = (unsigned)(s - name);
        outline = po_is(name, nlen, "outline");
        it->url[0] = it->title[0] = alt[0] = 0;
        for (;;) { /* the attributes, up to the '>' (every tag: a '>' inside a quote does not end it) */
            const uc *an;
            unsigned alen;
            while (s < e && (po_ws(*s) || *s == '/')) ++s;
            if (s >= e) {
                p->s = e;
                return 0; /* the tag is cut short by the end of the text */
            }
            if (*s == '>') {
                ++s;
                break;
            }
            an = s;
            while (s < e && !po_ws(*s) && *s != '=' && *s != '>' && *s != '/') ++s;
            alen = (unsigned)(s - an);
            if (s == an) { /* a byte that starts no name (a stray quote or equals sign) */
                ++s;
                continue;
            }
            while (s < e && po_ws(*s)) ++s;
            if (s < e && *s == '=') {
                char *dst = (char *)0;
                unsigned q, cap = 0;
                int is_url = 0;
                ++s;
                while (s < e && po_ws(*s)) ++s;
                if (s >= e) {
                    p->s = e;
                    return 0;
                }
                if (outline && po_is(an, alen, "xmlurl")) {
                    dst = it->url, cap = PC_URL, is_url = 1;
                } else if (outline && po_is(an, alen, "text")) {
                    dst = it->title, cap = PC_TITLE;
                    got_text = 1;
                } else if (outline && po_is(an, alen, "title")) {
                    dst = alt, cap = PC_TITLE;
                }
                o.out = dst, o.cap = cap, o.n = o.bad = o.cut = o.pend = 0, o.url = is_url;
                if (dst) dst[0] = 0;
                q = *s == '"' || *s == '\'' ? *s++ : 0;
                s = po_value(s, e, q, &o);
                if (is_url) url_bad = o.bad;
                if (!s) {
                    p->s = e;
                    return 0;
                }
            }
        }
        p->s = s;
        if (outline && it->url[0] && !url_bad && po_url_ok(it->url)) {
            if (!got_text || !it->title[0]) {
                unsigned i = 0;
                while (alt[i] && i + 1 < PC_TITLE) it->title[i] = alt[i], ++i;
                it->title[i] = 0;
            }
            return 1;
        }
    }
    p->s = e;
    return 0;
}

/* The title as the sort sees it: without a leading "The " (the Shows page's order does the same). */
static const uc *po_key(const char *title) {
    const uc *t = (const uc *)title;
    if (po_lower(t[0]) == 't' && po_lower(t[1]) == 'h' && po_lower(t[2]) == 'e' && t[3] == ' ' && t[4]) return t + 4;
    return t;
}

/* Negative, zero or positive: a before b by title (case aside for ASCII, then the bytes), then by folder name. */
static int po_cmp(const pc_show_t *a, const pc_show_t *b) {
    const uc *x = po_key(a->title), *y = po_key(b->title);
    while (*x && po_lower(*x) == po_lower(*y)) ++x, ++y;
    if (po_lower(*x) != po_lower(*y)) return po_lower(*x) < po_lower(*y) ? -1 : 1;
    x = (const uc *)a->dir, y = (const uc *)b->dir;
    while (*x && *x == *y) ++x, ++y;
    return *x == *y ? 0 : *x < *y ? -1 : 1;
}

int po_order(const pc_show_t *shows, int n, int *order) {
    int i, k, m = 0;
    for (i = 0; i < n; ++i) {
        if (!shows[i].feed[0]) continue;
        for (k = m++; k > 0 && po_cmp(&shows[order[k - 1]], &shows[i]) > 0; --k) order[k] = order[k - 1];
        order[k] = i;
    }
    return m;
}

typedef struct {
    char *out;
    unsigned cap, n;
    int full;
} po_w_t;

static void po_raw(po_w_t *w, const char *s) {
    for (; *s; ++s) {
        if (w->n + 1 >= w->cap) {
            w->full = 1;
            return;
        }
        w->out[w->n++] = *s;
    }
}

/* An attribute value, escaped (& < > " ' as entities, control bytes left out). */
static void po_attr(po_w_t *w, const char *name, const char *v) {
    po_raw(w, " ");
    po_raw(w, name);
    po_raw(w, "=\"");
    for (; *v; ++v) {
        unsigned c = (uc)*v;
        if (c == '&')
            po_raw(w, "&amp;");
        else if (c == '<')
            po_raw(w, "&lt;");
        else if (c == '>')
            po_raw(w, "&gt;");
        else if (c == '"')
            po_raw(w, "&quot;");
        else if (c == '\'')
            po_raw(w, "&apos;");
        else if (c >= 32 && c != 127) {
            char one[2];
            one[0] = (char)c, one[1] = 0;
            po_raw(w, one);
        }
    }
    po_raw(w, "\"");
}

unsigned po_render(const pc_show_t *shows, const int *order, int n, char *out, unsigned cap) {
    po_w_t w;
    int i;
    w.out = out, w.cap = cap, w.n = 0, w.full = 0;
    po_raw(&w, "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<opml version=\"2.0\">\n  <head>\n    <title>M1+ Music "
               "Podcasts</title>\n  </head>\n  <body>\n");
    for (i = 0; i < n; ++i) {
        const pc_show_t *s = &shows[order[i]];
        po_raw(&w, "    <outline type=\"rss\"");
        po_attr(&w, "text", s->title);
        po_attr(&w, "title", s->title);
        po_attr(&w, "xmlUrl", s->feed);
        po_raw(&w, "/>\n");
    }
    po_raw(&w, "  </body>\n</opml>\n");
    if (w.full || !cap) return 0;
    out[w.n] = 0;
    return w.n;
}
