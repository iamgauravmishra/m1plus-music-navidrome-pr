/* M1+ Music Podcasts, the feed reader: an RSS push parser and the writers of the show's .episodes and .show files.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * See patch/pcfeed.h. The parser is a byte at a time state machine over libcurl's chunks (any split): text, a tag, a comment, CDATA, and a skipped declaration. Only the elements the
 * model needs are collected (the channel's title and picture; an item's title, guid, pubDate, itunes:duration and enclosure); descriptions and everything else are discarded as they
 * pass, so a 4 MB feed costs the 20 KB parser and nothing more. Atom feeds are not read (a podcast feed is RSS; "Not a feed" otherwise).
 */
#include "offsets.inc"
#include "stock.h"
#include "podcasts.h"
#include "pcfeed.h"

#define PF_TEXT 512 /* the text of the element being collected (a title is cut to PC_TITLE later) */
#define PF_TAG \
    1024 /* a tag (a long enclosure url with its tracking path fits; a longer tag keeps its first PF_TAG bytes) */
#define PF_EPS_MAX 65536 /* the .episodes text the model reads at most (PM_META_MAX) */

enum { M_TEXT, M_TAG, M_COMMENT, M_CDATA, M_SKIP };
enum { W_NONE, W_ITITLE, W_CTITLE, W_GUID, W_PUB, W_DUR, W_IMGURL };
enum { E_NONE, E_RSS, E_ITEM, E_IMAGE, E_TITLE, E_GUID, E_PUB, E_DUR, E_URL, E_ENCL, E_ITUNES_IMAGE };

struct pf_parser {
    int mode, want, in_item, in_image, saw_feed, img_itunes, nitems, seen;
    unsigned tl, tn, en;
    char quote, trunc, d1, d2, tover, inent;
    char ent[12];
    char txt[PF_TEXT];
    char tag[PF_TAG];
    char title[PC_TITLE];
    char image[PC_URL];
    pf_item_t cur;
    pf_item_t items[PF_KEEP];
};

/* ---------------------------------------------------------------------------
 * Small helpers
 */
static unsigned pf_len(const char *s) {
    unsigned n = 0;
    while (s[n]) ++n;
    return n;
}

static int pf_lc(int c) { return (unsigned)(c - 'A') < 26u ? c + 32 : c; }

static int pf_is(const char *nm, unsigned len, const char *s) {
    unsigned i;
    for (i = 0; i < len; ++i)
        if (!s[i] || nm[i] != s[i]) return 0;
    return !s[len];
}

/* The UTF-8 bytes of code point cp into dst[*n..cap): 0 when it does not fit whole (or is not a character). */
static int pf_put_cp(char *dst, unsigned *n, unsigned cap, unsigned cp) {
    unsigned len = cp < 0x80 ? 1 : cp < 0x800 ? 2 : cp < 0x10000 ? 3 : 4;
    if (!cp || cp > 0x10ffff || (cp >= 0xd800 && cp < 0xe000) || *n + len > cap) return 0;
    if (len == 1)
        dst[*n] = (char)cp;
    else if (len == 2)
        dst[*n] = (char)(0xc0 | cp >> 6), dst[*n + 1] = (char)(0x80 | (cp & 0x3f));
    else if (len == 3)
        dst[*n] = (char)(0xe0 | cp >> 12), dst[*n + 1] = (char)(0x80 | (cp >> 6 & 0x3f)),
        dst[*n + 2] = (char)(0x80 | (cp & 0x3f));
    else
        dst[*n] = (char)(0xf0 | cp >> 18), dst[*n + 1] = (char)(0x80 | (cp >> 12 & 0x3f)),
        dst[*n + 2] = (char)(0x80 | (cp >> 6 & 0x3f)), dst[*n + 3] = (char)(0x80 | (cp & 0x3f));
    *n += len;
    return 1;
}

/* The character an entity names: e is the text between "&" and ";" (n bytes). 0 when it is not one we know. */
static unsigned pf_ent_cp(const char *e, unsigned n) {
    unsigned v = 0, i;
    if (n >= 2 && e[0] == '#') {
        if (e[1] == 'x' || e[1] == 'X') {
            for (i = 2; i < n; ++i) {
                int c = pf_lc((unsigned char)e[i]), d = (unsigned)(c - '0') < 10u  ? c - '0'
                                                        : (unsigned)(c - 'a') < 6u ? c - 'a' + 10
                                                                                   : -1;
                if (d < 0 || v > 0x10ffffu) return 0;
                v = v * 16 + (unsigned)d;
            }
            return n > 2 ? v : 0;
        }
        for (i = 1; i < n; ++i) {
            if ((unsigned)(e[i] - '0') >= 10u || v > 0x10ffffu) return 0;
            v = v * 10 + (unsigned)(e[i] - '0');
        }
        return v;
    }
    if (pf_is(e, n, "amp")) return '&';
    if (pf_is(e, n, "lt")) return '<';
    if (pf_is(e, n, "gt")) return '>';
    if (pf_is(e, n, "quot")) return '"';
    if (pf_is(e, n, "apos")) return '\'';
    return 0;
}

/* src[0..n) into dst (cap bytes, a NUL at the end): leading and trailing white space dropped, every run of white space and control bytes one space, cut before a split UTF-8 character. */
static void pf_norm(char *dst, unsigned cap, const char *src, unsigned n) {
    unsigned o = 0, i;
    int space = 0, cut = 0;
    for (i = 0; i < n && src[i]; ++i) {
        unsigned char c = (unsigned char)src[i];
        if (c <= 32) {
            space = o != 0;
            continue;
        }
        if (o + (space ? 2 : 1) >= cap) {
            cut = 1;
            break;
        }
        if (space) dst[o++] = ' ', space = 0;
        dst[o++] = (char)c;
    }
    if (cut && i < n &&
        ((unsigned char)src[i] & 0xc0) == 0x80) { /* the cut splits a character: drop its first bytes too */
        while (o && ((unsigned char)dst[o - 1] & 0xc0) == 0x80) --o;
        if (o) --o;
    }
    dst[o] = 0;
}

/* ---------------------------------------------------------------------------
 * Dates and durations
 */
static int pf_civil_days(int y, int m,
                         int d) { /* days since 1970-01-01 of a proleptic Gregorian date (Hinnant's days_from_civil) */
    int era, yoe, doy, doe;
    y -= m <= 2;
    era = (y >= 0 ? y : y - 399) / 400;
    yoe = y - era * 400;
    doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
    doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
    return era * 146097 + doe - 719468;
}

static void pf_civil(unsigned days, int *y, int *m, int *d) { /* the inverse (civil_from_days) */
    int z = (int)days + 719468, era = z / 146097, doe = z - era * 146097;
    int yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365, doy, mp;
    *y = yoe + era * 400;
    doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    mp = (5 * doy + 2) / 153;
    *d = doy - (153 * mp + 2) / 5 + 1;
    *m = mp + (mp < 10 ? 3 : -9);
    *y += *m <= 2;
}

static int pf_digits(const char **s, int max, int *out) { /* up to max decimal digits: how many were read */
    int n = 0, v = 0;
    while (n < max && (unsigned)(**s - '0') < 10u) v = v * 10 + (**s - '0'), ++*s, ++n;
    *out = v;
    return n;
}

unsigned pf_rfc822(const char *s) {
    static const char mon[] = "janfebmaraprmayjunjulaugsepoctnovdec";
    int day, year, hh, mm = 0, ss = 0, m = -1, i, nd, zone = 0;
    long t;
    while (*s && (unsigned)(*s - '0') >= 10u) ++s; /* the weekday and its comma */
    if (!pf_digits(&s, 2, &day)) return 0;
    while (*s == ' ' || *s == '-') ++s;
    for (i = 0; i < 12; ++i)
        if (pf_lc((unsigned char)s[0]) == mon[3 * i] && pf_lc((unsigned char)s[1]) == mon[3 * i + 1] &&
            pf_lc((unsigned char)s[2]) == mon[3 * i + 2])
            m = i + 1;
    if (m < 0) return 0;
    s += 3;
    while ((unsigned)(pf_lc((unsigned char)*s) - 'a') < 26u) ++s; /* "October" */
    while (*s == ' ' || *s == '-') ++s;
    nd = pf_digits(&s, 4, &year);
    if (nd == 2)
        year += year < 70 ? 2000 : 1900;
    else if (nd != 4)
        return 0;
    while (*s == ' ' || *s == ',') ++s;
    if (!pf_digits(&s, 2, &hh) || *s != ':') return 0;
    ++s;
    if (!pf_digits(&s, 2, &mm)) return 0;
    if (*s == ':') ++s, pf_digits(&s, 2, &ss);
    while (*s == ' ') ++s;
    if (*s == '+' || *s == '-') {
        int sign = *s == '-' ? -1 : 1, zh, zm = 0;
        ++s;
        if (pf_digits(&s, 2, &zh)) {
            if (*s == ':') ++s;
            pf_digits(&s, 2, &zm);
            zone = sign * (zh * 3600 + zm * 60);
        }
    } else {
        static const struct {
            const char *n;
            int h;
        } z[] = {{"EST", -5}, {"EDT", -4}, {"CST", -6}, {"CDT", -5},
                 {"MST", -7}, {"MDT", -6}, {"PST", -8}, {"PDT", -7}};
        for (i = 0; i < 8; ++i)
            if (pf_lc((unsigned char)s[0]) == pf_lc(z[i].n[0]) && pf_lc((unsigned char)s[1]) == pf_lc(z[i].n[1]) &&
                pf_lc((unsigned char)s[2]) == pf_lc(z[i].n[2]))
                zone = z[i].h * 3600;
    }
    if (day < 1 || day > 31 || hh > 23 || mm > 59 || ss > 60 || year < 1970 || year > 2100) return 0;
    t = (long)pf_civil_days(year, m, day) * 86400 + hh * 3600 + mm * 60 + ss - zone;
    return t > 0 ? (unsigned)t : 0;
}

unsigned pf_duration(const char *s) {
    unsigned parts[3] = {0, 0, 0}, n = 0, v = 0;
    int any = 0;
    for (; *s; ++s) {
        if ((unsigned)(*s - '0') < 10u) {
            if (v > 100000u) return 0;
            v = v * 10 + (unsigned)(*s - '0'), any = 1;
        } else if (*s == ':' && n < 2)
            parts[n++] = v, v = 0, any = 0;
        else if (*s == '.')
            break;
        else if (*s != ' ')
            return 0;
    }
    if (!any && !n) return 0;
    parts[n++] = v;
    return n == 1 ? parts[0] : n == 2 ? parts[0] * 60 + parts[1] : parts[0] * 3600 + parts[1] * 60 + parts[2];
}

/* ---------------------------------------------------------------------------
 * Attributes: the value of name in the tag (entities decoded) into out; 0 when there is none.
 */
static int pf_attr(const char *tag, unsigned n, const char *name, char *out, unsigned cap) {
    unsigned i = 1;
    while (i < n && (unsigned char)tag[i] > 32 && tag[i] != '/' && tag[i] != '>') ++i; /* the element's name */
    while (i < n) {
        unsigned s, e;
        while (i < n && ((unsigned char)tag[i] <= 32 || tag[i] == '/')) ++i;
        s = i;
        while (i < n && tag[i] != '=' && (unsigned char)tag[i] > 32 && tag[i] != '>' && tag[i] != '/') ++i;
        e = i;
        if (i == s && (i >= n || tag[i] != '=')) { /* nothing read (the closing '>'): never stand still */
            ++i;
            continue;
        }
        while (i < n && (unsigned char)tag[i] <= 32) ++i;
        if (i < n && tag[i] == '=') {
            char q;
            ++i;
            while (i < n && (unsigned char)tag[i] <= 32) ++i;
            q = i < n ? tag[i] : 0;
            if (q == '"' || q == '\'') {
                unsigned o = 0, v = ++i;
                int match = pf_is(tag + s, e - s, name);
                while (i < n && tag[i] != q) ++i;
                if (match) {
                    unsigned k = v;
                    while (k < i) {
                        if (tag[k] == '&') {
                            unsigned j = k + 1;
                            while (j < i && j - k < 11 && tag[j] != ';') ++j;
                            if (j < i && tag[j] == ';' && pf_ent_cp(tag + k + 1, j - k - 1) &&
                                pf_put_cp(out, &o, cap - 1, pf_ent_cp(tag + k + 1, j - k - 1))) {
                                k = j + 1;
                                continue;
                            }
                        }
                        if (o + 1 < cap) out[o++] = tag[k];
                        ++k;
                    }
                    out[o] = 0;
                    return 1;
                }
                ++i;
            } else
                while (i < n && (unsigned char)tag[i] > 32 && tag[i] != '>') ++i; /* an unquoted value */
        }
    }
    return 0;
}

/* ---------------------------------------------------------------------------
 * The parser
 */
pf_parser_t *pf_new(void) { return calloc(1, sizeof(pf_parser_t)); }
void pf_free(pf_parser_t *p) { free(p); }
int pf_is_feed(const pf_parser_t *p) { return p->saw_feed; }
int pf_items(const pf_parser_t *p) { return p->nitems; }
int pf_seen(const pf_parser_t *p) { return p->seen; }
const char *pf_title(const pf_parser_t *p) { return p->title; }
const char *pf_image(const pf_parser_t *p) { return p->image; }

static void pf_txt_cp(pf_parser_t *p, unsigned cp) {
    if (!pf_put_cp(p->txt, &p->tn, PF_TEXT - 1, cp)) p->tover = 1;
}

static void pf_txt(pf_parser_t *p, unsigned char c) {
    if (p->tn < PF_TEXT - 1)
        p->txt[p->tn++] = (char)c;
    else
        p->tover = 1;
}

/* A byte of character data (outside CDATA) of an element being collected: entities are decoded, an unknown one stays as written. */
static void pf_text_byte(pf_parser_t *p, unsigned char c) {
    if (p->inent) {
        if (c == ';') {
            unsigned cp = pf_ent_cp(p->ent, p->en), k;
            p->inent = 0;
            if (cp)
                pf_txt_cp(p, cp);
            else {
                pf_txt(p, '&');
                for (k = 0; k < p->en; ++k) pf_txt(p, (unsigned char)p->ent[k]);
                pf_txt(p, ';');
            }
            return;
        }
        if (p->en < sizeof p->ent && ((unsigned)(c - '0') < 10u || (unsigned)(pf_lc(c) - 'a') < 26u || c == '#')) {
            p->ent[p->en++] = (char)c;
            return;
        }
        { /* not an entity after all: what was read, literally, then this byte as any other */
            unsigned k;
            pf_txt(p, '&');
            for (k = 0; k < p->en; ++k) pf_txt(p, (unsigned char)p->ent[k]);
            p->inent = 0;
        }
    }
    if (c == '&')
        p->inent = 1, p->en = 0;
    else
        pf_txt(p, c);
}

static void pf_flush_ent(pf_parser_t *p) {
    if (p->inent && p->want) {
        unsigned k;
        pf_txt(p, '&');
        for (k = 0; k < p->en; ++k) pf_txt(p, (unsigned char)p->ent[k]);
    }
    p->inent = 0;
}

static void pf_start_text(pf_parser_t *p, int want) {
    p->want = want, p->tn = 0, p->tover = 0, p->inent = 0, p->en = 0;
}

static void pf_finish_text(pf_parser_t *p) {
    int w = p->want;
    p->want = 0;
    pf_flush_ent(p);
    p->txt[p->tn] = 0;
    if (w == W_ITITLE)
        pf_norm(p->cur.title, PC_TITLE, p->txt, p->tn);
    else if (w == W_CTITLE)
        pf_norm(p->title, PC_TITLE, p->txt, p->tn);
    else if (w == W_GUID)
        pf_norm(p->cur.guid, PF_GUID, p->txt, p->tn);
    else if (w == W_PUB)
        p->cur.pub = pf_rfc822(p->txt);
    else if (w == W_DUR)
        p->cur.dur = pf_duration(p->txt);
    else if (w == W_IMGURL && !p->image[0])
        pf_norm(p->image, PC_URL, p->txt, p->tn);
}

/* The element a tag names: its code, for the names the parser looks at. */
static int pf_code(const char *nm, unsigned len) {
    static const struct {
        const char *name;
        int code;
    } tab[] = {
        {"item", E_ITEM},
        {"title", E_TITLE},
        {"guid", E_GUID},
        {"pubDate", E_PUB},
        {"enclosure", E_ENCL},
        {"itunes:duration", E_DUR},
        {"itunes:image", E_ITUNES_IMAGE},
        {"image", E_IMAGE},
        {"url", E_URL},
        {"rss", E_RSS},
        {"channel", E_RSS},
    };
    unsigned i;
    for (i = 0; i < sizeof tab / sizeof *tab; ++i)
        if (pf_is(nm, len, tab[i].name)) return tab[i].code;
    return E_NONE;
}

/* The item just read, into the kept list: newest first by pubDate, a later item after an equal date; a full list drops the oldest. */
static void pf_keep(pf_parser_t *p) {
    int i;
    pf_item_t *c = &p->cur;
    if (!c->url[0]) return;
    if (!c->guid[0]) pf_norm(c->guid, PF_GUID, c->url, pf_len(c->url));
    ++p->seen;
    if (p->nitems == PF_KEEP) {
        if (c->pub <= p->items[PF_KEEP - 1].pub) return;
        i = PF_KEEP - 1;
    } else
        i = p->nitems++;
    while (i > 0 && p->items[i - 1].pub < c->pub) {
        memcpy(&p->items[i], &p->items[i - 1], sizeof *c);
        --i;
    }
    memcpy(&p->items[i], c, sizeof *c);
}

static void pf_open(pf_parser_t *p, int code, int selfclose) {
    unsigned n = p->tl;
    char buf[PF_URL];
    if (code == E_RSS)
        p->saw_feed = 1;
    else if (code == E_ITEM) {
        p->in_item = 1;
        memset(&p->cur, 0, sizeof p->cur);
    } else if (code == E_IMAGE) {
        if (!p->in_item) p->in_image = 1;
    } else if (code == E_TITLE) {
        if (p->in_item)
            pf_start_text(p, W_ITITLE);
        else if (!p->in_image && !p->title[0])
            pf_start_text(p, W_CTITLE);
    } else if (code == E_GUID) {
        if (p->in_item) pf_start_text(p, W_GUID);
    } else if (code == E_PUB) {
        if (p->in_item) pf_start_text(p, W_PUB);
    } else if (code == E_DUR) {
        if (p->in_item) pf_start_text(p, W_DUR);
    } else if (code == E_URL) {
        if (p->in_image && !p->image[0]) pf_start_text(p, W_IMGURL);
    } else if (code == E_ENCL) {
        if (p->in_item && !p->cur.url[0] && pf_attr(p->tag, n, "url", buf, sizeof buf)) {
            char type[PF_TYPE], len[16];
            type[0] = 0;
            pf_attr(p->tag, n, "type", type, sizeof type); /* a picture or a page is no episode */
            if (!(type[0] == 'i' || type[0] == 't')) {
                pf_norm(p->cur.url, PF_URL, buf, pf_len(buf));
                pf_norm(p->cur.type, PF_TYPE, type, pf_len(type));
                if (pf_attr(p->tag, n, "length", len, sizeof len)) {
                    unsigned v = 0, i;
                    for (i = 0; len[i] && (unsigned)(len[i] - '0') < 10u && v < 429496729u; ++i)
                        v = v * 10 + (unsigned)(len[i] - '0');
                    p->cur.length = v;
                }
            }
        }
    } else if (code == E_ITUNES_IMAGE) {
        if (!p->in_item && !p->img_itunes && pf_attr(p->tag, n, "href", buf, sizeof buf)) {
            pf_norm(p->image, PC_URL, buf, pf_len(buf));
            p->img_itunes = p->image[0] != 0;
        }
    }
    if (selfclose && p->want) p->want = 0; /* an empty element */
}

static void pf_close(pf_parser_t *p, int code) {
    int w = p->want;
    if (w && ((code == E_TITLE && (w == W_ITITLE || w == W_CTITLE)) || (code == E_GUID && w == W_GUID) ||
              (code == E_PUB && w == W_PUB) || (code == E_DUR && w == W_DUR) || (code == E_URL && w == W_IMGURL)))
        pf_finish_text(p);
    if (code == E_ITEM && p->in_item) {
        p->in_item = 0;
        p->want = 0;
        pf_keep(p);
    } else if (code == E_IMAGE)
        p->in_image = 0;
}

/* The tag in p->tag[0..tl) is complete. */
static void pf_tag(pf_parser_t *p) {
    const char *nm = p->tag + 1;
    unsigned n = 0, tl = p->tl;
    int closing = p->tag[1] == '/', selfclose = !p->trunc && tl >= 3 && p->tag[tl - 2] == '/';
    if (closing) ++nm;
    while (nm + n < p->tag + tl && (unsigned char)nm[n] > 32 && nm[n] != '/' && nm[n] != '>') ++n;
    if (closing)
        pf_close(p, pf_code(nm, n));
    else {
        int code = pf_code(nm, n);
        pf_open(p, code, selfclose);
        if (selfclose && (code == E_ITEM)) pf_close(p, code);
    }
}

void pf_push(pf_parser_t *p, const char *d, unsigned n) {
    unsigned i = 0;
    while (i < n) {
        unsigned char c = (unsigned char)d[i];
        switch (p->mode) {
        case M_TEXT:
            if (c == '<') {
                pf_flush_ent(p);
                p->mode = M_TAG, p->tag[0] = '<', p->tl = 1, p->quote = 0, p->trunc = 0;
            } else if (p->want)
                pf_text_byte(p, c);
            else
                while (i + 1 < n && d[i + 1] != '<') ++i; /* nothing is collected: skip to the next tag */
            break;
        case M_TAG:
            if (p->tl < PF_TAG - 1)
                p->tag[p->tl++] = (char)c;
            else
                p->trunc = 1;
            if (!p->trunc && p->tl == 2 && c == '?')
                p->mode = M_SKIP; /* <?xml ... ?> */
            else if (!p->trunc && p->tl == 3 && p->tag[1] == '!' && c != '-' && c != '[')
                p->mode = M_SKIP; /* <!DOCTYPE ...> */
            else if (!p->trunc && p->tl == 4 && p->tag[1] == '!' && p->tag[2] == '-' && c == '-')
                p->mode = M_COMMENT, p->d1 = p->d2 = 0;
            else if (!p->trunc && p->tl == 9 && p->tag[1] == '!' && p->tag[2] == '[' && c == '[' && p->tag[8] == '[')
                p->mode = M_CDATA, p->d1 = p->d2 = 0;
            else if (p->quote) {
                if (c == (unsigned char)p->quote) p->quote = 0;
            } else if (c == '"' || c == '\'')
                p->quote = (char)c;
            else if (c == '>') {
                p->mode = M_TEXT;
                pf_tag(p);
            }
            break;
        case M_SKIP:
            if (c == '>') p->mode = M_TEXT;
            break;
        case M_COMMENT:
            if (c == '>' && p->d1 == '-' && p->d2 == '-') p->mode = M_TEXT;
            p->d1 = p->d2, p->d2 = (char)c;
            break;
        case M_CDATA:
            if (c == '>' && p->d1 == ']' && p->d2 == ']') {
                p->mode = M_TEXT;
                if (p->want && !p->tover && p->tn >= 2) p->tn -= 2; /* the "]]" that was kept as text */
            } else if (p->want)
                pf_txt(p, c);
            p->d1 = p->d2, p->d2 = (char)c;
            break;
        }
        ++i;
    }
}

/* ---------------------------------------------------------------------------
 * File names
 */

/* A title as a file name: forbidden characters (the card is ExFAT: \ / : * ? " < > | and controls) turn into '-', white space runs into one space, at most max bytes
 * (cut before a split character), no leading dot or space, no trailing dot or space. */
static void pf_slug(char *out, unsigned cap, const char *title, unsigned max) {
    char tmp[PC_TITLE + 8];
    unsigned i, o = 0, n = pf_len(title);
    if (max > cap - 1) max = cap - 1;
    pf_norm(tmp, sizeof tmp, title, n);
    for (i = 0; tmp[i]; ++i) {
        char c = tmp[i];
        if (c == '/' || c == '\\' || c == ':' || c == '*' || c == '?' || c == '"' || c == '<' || c == '>' || c == '|')
            c = '-';
        tmp[i] = c;
    }
    for (i = 0; tmp[i] == '.' || tmp[i] == ' ' || tmp[i] == '-'; ++i) {
    }
    n = pf_len(tmp);
    for (; i < n && o < max; ++i) out[o++] = tmp[i];
    if (i < n && ((unsigned char)tmp[i] & 0xc0) == 0x80) {
        while (o && ((unsigned char)out[o - 1] & 0xc0) == 0x80) --o;
        if (o) --o;
    }
    while (o && (out[o - 1] == '.' || out[o - 1] == ' ')) --o;
    out[o] = 0;
}

void pf_folder_name(char *out, unsigned size, const char *title) { pf_slug(out, size, title, PF_MAX_FILE); }

static int pf_audio_ext(const char *e, unsigned n) {
    static const char *const ext[] = {"mp3", "m4a", "m4b", "aac", "ogg", "opus", "flac", "wav", "wma"};
    unsigned i, k;
    char low[8];
    if (n >= sizeof low) return 0;
    for (k = 0; k < n; ++k) low[k] = (char)pf_lc((unsigned char)e[k]);
    for (i = 0; i < sizeof ext / sizeof *ext; ++i)
        if (pf_is(low, n, ext[i])) return 1;
    return 0;
}

/* The extension of an episode's file: the url path's when it is an audio one, else from the MIME type, else mp3. */
static const char *pf_ext(const pf_item_t *it, char *ext) { /* ext: 8 bytes (the result may point into it) */
    const char *u = it->url, *dot = (const char *)0, *s;
    unsigned n = 0, i;
    for (s = u; *s && *s != '?' && *s != '#'; ++s) {
        if (*s == '/')
            dot = (const char *)0;
        else if (*s == '.')
            dot = s + 1;
    }
    if (dot && (unsigned)(s - dot) < 6 && pf_audio_ext(dot, (unsigned)(s - dot))) {
        for (i = 0; i < (unsigned)(s - dot); ++i) ext[n++] = (char)pf_lc((unsigned char)dot[i]);
        ext[n] = 0;
        return ext;
    }
    if (pf_is(it->type, pf_len(it->type), "audio/mp4") || pf_is(it->type, pf_len(it->type), "audio/x-m4a") ||
        pf_is(it->type, pf_len(it->type), "audio/m4a"))
        return "m4a";
    if (pf_is(it->type, pf_len(it->type), "audio/aac")) return "aac";
    if (pf_is(it->type, pf_len(it->type), "audio/ogg")) return "ogg";
    return "mp3";
}

/* "YYYY-MM-DD Title.ext" (no date when the item has none), at most PF_MAX_FILE bytes. */
static void pf_fname(const pf_item_t *it, char *out, unsigned size) {
    char slug[PC_TITLE + 8], extbuf[8];
    const char *ext = pf_ext(it, extbuf);
    unsigned o = 0, k, room;
    int y, m, d;
    if (it->pub) {
        pf_civil(it->pub / 86400, &y, &m, &d);
        out[o++] = (char)('0' + y / 1000 % 10), out[o++] = (char)('0' + y / 100 % 10),
        out[o++] = (char)('0' + y / 10 % 10), out[o++] = (char)('0' + y % 10);
        out[o++] = '-', out[o++] = (char)('0' + m / 10), out[o++] = (char)('0' + m % 10);
        out[o++] = '-', out[o++] = (char)('0' + d / 10), out[o++] = (char)('0' + d % 10);
        out[o++] = ' ';
    }
    room = PF_MAX_FILE - o - pf_len(ext) - 1;
    pf_slug(slug, sizeof slug, it->title, room);
    if (!slug[0]) memcpy(slug, "episode", 8);
    for (k = 0; slug[k] && o + 1 < size; ++k) out[o++] = slug[k];
    out[o++] = '.';
    for (k = 0; ext[k] && o + 1 < size; ++k) out[o++] = ext[k];
    out[o] = 0;
}

/* f with " (n)" before its extension: "2026-10-30 Title.mp3" becomes "2026-10-30 Title (2).mp3". */
static void pf_numbered(char *f, unsigned size, unsigned n) {
    unsigned fl = pf_len(f), dot = fl, tl;
    char tail[12];
    while (dot && f[dot - 1] != '.') --dot;
    dot = dot ? dot - 1 : fl;
    tl = fl - dot;
    if (tl >= sizeof tail || dot + 4 + tl + 1 > size) return;
    memcpy(tail, f + dot, tl + 1);
    f[dot++] = ' ', f[dot++] = '(', f[dot++] = (char)('0' + n), f[dot++] = ')';
    memcpy(f + dot, tail, tl + 1);
}

/* ---------------------------------------------------------------------------
 * The writers
 */
static void pf_app(char *out, unsigned *o, unsigned cap, const char *s) {
    while (*s && *o + 1 < cap) out[(*o)++] = *s++;
}

static void pf_app_n(char *out, unsigned *o, unsigned cap, const char *s, unsigned n) {
    unsigned i;
    for (i = 0; i < n && *o + 1 < cap; ++i) out[(*o)++] = s[i];
}

static void pf_app_u(char *out, unsigned *o, unsigned cap, unsigned v) {
    char num[12];
    unsigned k = 0;
    do num[k++] = (char)('0' + v % 10), v /= 10;
    while (v);
    while (k && *o + 1 < cap) out[(*o)++] = num[--k];
}

/* Text with white space and control bytes as single spaces: the text formats have no tab or newline inside a value. */
static void pf_app_plain(char *out, unsigned *o, unsigned cap, const char *s) {
    char tmp[PF_URL];
    pf_norm(tmp, sizeof tmp, s, pf_len(s));
    pf_app(out, o, cap, tmp);
}

unsigned pf_render_show(const char *title, const char *feed, const char *image, unsigned checked, char *out,
                        unsigned cap) {
    unsigned o = 0;
    pf_app(out, &o, cap, "M1PLUS-SHOW 1\ntitle=");
    pf_app_plain(out, &o, cap, title);
    pf_app(out, &o, cap, "\nfeed=");
    pf_app_plain(out, &o, cap, feed);
    pf_app(out, &o, cap, "\nimage=");
    pf_app_plain(out, &o, cap, image);
    pf_app(out, &o, cap, "\nchecked=");
    pf_app_u(out, &o, cap, checked);
    pf_app(out, &o, cap, "\n");
    out[o] = 0;
    return o;
}

/* The line [p, stop) up to its newline; the next line starts at *next. Its length is without the CR. */
static unsigned pf_line(const char *p, const char *stop, const char **next) {
    const char *q = p;
    unsigned n;
    while (q < stop && *q != '\n') ++q;
    n = (unsigned)(q - p);
    *next = q < stop ? q + 1 : q;
    if (n && p[n - 1] == '\r') --n;
    return n;
}

/* The value of the field `key=` of a tab separated line (0 when there is none). */
static int pf_field(const char *line, unsigned n, char key, const char **v, unsigned *vn) {
    unsigned at = 0;
    while (at < n) {
        unsigned flen = 0;
        while (at + flen < n && line[at + flen] != '\t') ++flen;
        if (flen >= 2 && line[at] == key && line[at + 1] == '=') {
            *v = line + at + 2, *vn = flen - 2;
            return 1;
        }
        at += flen + 1;
    }
    return 0;
}

static int pf_same(const char *a, unsigned an, const char *b) {
    unsigned i;
    for (i = 0; i < an; ++i)
        if (a[i] != b[i]) return 0;
    return !b[an];
}

static int pf_file_here(const char *dir, const char *f, unsigned fn) {
    char path[PC_FILE * 2 + 40];
    unsigned o = 0;
    if (!fn || fn >= PC_FILE) return 0;
    pf_app(path, &o, sizeof path, dir);
    pf_app(path, &o, sizeof path, "/");
    pf_app_n(path, &o, sizeof path, f, fn);
    path[o] = 0;
    if (access(path, F_OK) == 0) return 1;
    pf_app(path, &o, sizeof path, ".part");
    path[o] = 0;
    return access(path, F_OK) == 0;
}

unsigned pf_render_episodes(const pf_parser_t *p, const char *dir, const char *old, unsigned oldn, char *out,
                            unsigned cap, unsigned *fresh) {
    unsigned o = 0, k, n = 0, lo;
    char names[PF_KEEP][PC_FILE], ln[1280];
    const char *stop = old ? old + oldn : (const char *)0, *q, *next;
    if (cap > PF_EPS_MAX) cap = PF_EPS_MAX;
    *fresh = 0;
    pf_app(out, &o, cap, "M1PLUS-EPISODES 1\n");
    for (k = 0; k < (unsigned)p->nitems; ++k) {
        const pf_item_t *it = &p->items[k];
        char f[PC_FILE];
        const char *fv = (const char *)0;
        unsigned fn = 0, gl = pf_len(it->guid), j, tries;
        f[0] = 0;
        if (old) { /* an old line with this guid keeps its file name */
            for (q = old; q < stop; q = next) {
                unsigned len = pf_line(q, stop, &next), vn;
                const char *v;
                if (len && pf_field(q, len, 'g', &v, &vn) && vn == gl && pf_same(v, vn, it->guid)) {
                    if (pf_field(q, len, 'f', &fv, &fn) && fn && fn < PC_FILE) memcpy(f, fv, fn), f[fn] = 0;
                    break;
                }
            }
            if (q >= stop) ++*fresh;
        } else
            ++*fresh;
        if (!f[0]) {
            char base[PC_FILE];
            pf_fname(it, f, sizeof f);
            memcpy(base, f, pf_len(f) + 1);
            for (tries = 2; tries < 10;
                 ++tries) { /* two items of one day with one title: a number before the extension */
                int clash = 0;
                for (j = 0; j < n; ++j)
                    if (pf_same(names[j], pf_len(names[j]), f)) clash = 1;
                if (!clash) break;
                memcpy(f, base, pf_len(base) + 1);
                pf_numbered(f, sizeof f, tries);
            }
        }
        memcpy(names[n], f, pf_len(f) + 1);
        ++n;
        lo = 0; /* the line is made whole, and added whole: a full buffer never ends in half a line */
        pf_app(ln, &lo, sizeof ln, "g=");
        pf_app_plain(ln, &lo, sizeof ln, it->guid);
        pf_app(ln, &lo, sizeof ln, "\tp=");
        pf_app_u(ln, &lo, sizeof ln, it->pub);
        pf_app(ln, &lo, sizeof ln, "\td=");
        pf_app_u(ln, &lo, sizeof ln, it->dur);
        pf_app(ln, &lo, sizeof ln, "\tl=");
        pf_app_u(ln, &lo, sizeof ln, it->length);
        pf_app(ln, &lo, sizeof ln, "\tf=");
        pf_app(ln, &lo, sizeof ln, f);
        pf_app(ln, &lo, sizeof ln, "\tt=");
        pf_app_plain(ln, &lo, sizeof ln, it->title);
        pf_app(ln, &lo, sizeof ln, "\tu=");
        pf_app_plain(ln, &lo, sizeof ln, it->url);
        pf_app(ln, &lo, sizeof ln, "\n");
        if (o + lo < cap) memcpy(out + o, ln, lo), o += lo;
    }
    if (old) /* the old entries that are not in the feed's window any more but have their file (or a started download) stay, as they were written */
        for (q = old; q < stop; q = next) {
            unsigned len = pf_line(q, stop, &next), vn, fnn;
            const char *v, *fvv;
            int listed = 0;
            if (!len || q[0] == '#' || !pf_field(q, len, 'f', &fvv, &fnn) || !pf_file_here(dir, fvv, fnn)) continue;
            if (pf_field(q, len, 'g', &v, &vn))
                for (k = 0; k < (unsigned)p->nitems; ++k)
                    if (vn == pf_len(p->items[k].guid) && pf_same(v, vn, p->items[k].guid)) listed = 1;
            if (listed || o + len + 2 >= cap) continue;
            pf_app_n(out, &o, cap, q, len);
            pf_app(out, &o, cap, "\n");
        }
    out[o] = 0;
    return o;
}
