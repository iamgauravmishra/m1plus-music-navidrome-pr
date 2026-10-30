/* A streaming PNG decoder: chunks, inflate, unfilter, RGB (docs/modules/podcasts.md "Cover art").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE). The inflate follows the shape of Mark Adler's puff.c (zlib licence): canonical Huffman codes decoded from the count of codes of each
 * length, one bit at a time; it is written afresh here, with the input pulled from the IDAT chunks of a stdio file and the output pushed byte by byte.
 *
 * demo imports png_read_image (the whole image) but no png_read_row and no zlib, so this is the only way to a large PNG in bounded memory. The state is one calloc (about 40 kB: the 32 kB
 * window, the input buffer, two Huffman tables) plus two scanlines (at most 64 kB each, an 8192 px RGBA 16-bit row) and one RGB row (24 kB). Everything that comes from the file is bounds
 * checked: chunk lengths against the file, Huffman symbols and distances against the tables and the bytes output so far, the output against the header's size, filter bytes, palette
 * indices. Threads: none of its own; it runs in the refresh worker.
 */
#include "offsets.inc"
#include "stock.h"
#include "pcpng.h"

#define WIN 32768u

typedef struct {
    unsigned short counts[16], symbols[288];
} huff_t;

struct pp {
    void *f;
    unsigned left; /* bytes of the current IDAT chunk not yet read */
    int have, done; /* an IDAT chunk was entered (its CRC still follows); no further IDAT chunk */
    unsigned ipos, ilen, bits, nbits;
    unsigned wpos, total; /* window position; bytes output so far */
    unsigned w, h, rb, bpp, ctype, depth, npal;
    int key; /* a tRNS colour key for grey or RGB */
    unsigned keyv[3];
    unsigned rpos, rows;
    unsigned char *cur, *prev, *rgb;
    int (*row)(void *, const unsigned char *, unsigned);
    void *user;
    huff_t lit, dist;
    unsigned char pal[768], pala[256];
    unsigned char ibuf[4096];
    unsigned char win[WIN];
};

static unsigned pp_be32(const unsigned char *b) {
    return (unsigned)b[0] << 24 | (unsigned)b[1] << 16 | (unsigned)b[2] << 8 | b[3];
}

/* ---------------------------------------------------------------------------
 * Input: the compressed bytes of the IDAT chunks, one after the other
 */
static int pp_fill(pp_t *p) {
    unsigned char h[8];
    unsigned n;
    while (!p->left) {
        if (p->done) return 0;
        if (p->have && fseek(p->f, 4, 1)) return 0; /* the CRC of the chunk just read (not checked) */
        p->have = 0;
        if (fread(h, 1, 8, p->f) != 8) return 0;
        if (h[4] == 'I' && h[5] == 'D' && h[6] == 'A' && h[7] == 'T') {
            p->left = pp_be32(h), p->have = 1;
            if (p->left > 0x7fffffffu) return 0;
        } else {
            p->done = 1;
            return 0;
        }
    }
    n = p->left < sizeof p->ibuf ? p->left : (unsigned)sizeof p->ibuf;
    if (fread(p->ibuf, 1, n, p->f) != n) return 0;
    p->left -= n, p->ipos = 0, p->ilen = n;
    return 1;
}

static int pp_next(pp_t *p) {
    if (p->ipos == p->ilen && !pp_fill(p)) return -1;
    return p->ibuf[p->ipos++];
}

static int pp_bits(pp_t *p, unsigned n) { /* n <= 16 low bits first; -1 at the end of the data */
    int v;
    while (p->nbits < n) {
        if ((v = pp_next(p)) < 0) return -1;
        p->bits |= (unsigned)v << p->nbits, p->nbits += 8;
    }
    v = (int)(p->bits & ((1u << n) - 1));
    p->bits >>= n, p->nbits -= n;
    return v;
}

/* ---------------------------------------------------------------------------
 * Huffman codes
 */
static int pp_build(huff_t *t, const unsigned char *lens, unsigned n) { /* nonzero: over-subscribed */
    unsigned short offs[16];
    unsigned i;
    int left = 1;
    memset(t, 0, sizeof *t);
    for (i = 0; i < n; ++i) ++t->counts[lens[i]];
    t->counts[0] = 0;
    for (i = 1; i < 16; ++i) {
        left = left * 2 - t->counts[i];
        if (left < 0) return 1;
    }
    offs[1] = 0;
    for (i = 1; i < 15; ++i) offs[i + 1] = (unsigned short)(offs[i] + t->counts[i]);
    for (i = 0; i < n; ++i)
        if (lens[i]) t->symbols[offs[lens[i]]++] = (unsigned short)i;
    return 0;
}

static int pp_sym(pp_t *p, const huff_t *t) { /* the next symbol, -1 for a bad code or the end of the data */
    int sum = 0, cur = 0, len = 0;
    do {
        if (!p->nbits) {
            int v = pp_next(p);
            if (v < 0) return -1;
            p->bits = (unsigned)v, p->nbits = 8;
        }
        cur = cur * 2 + (int)(p->bits & 1);
        p->bits >>= 1, --p->nbits;
        if (++len > 15) return -1;
        sum += t->counts[len], cur -= t->counts[len];
    } while (cur >= 0);
    sum += cur;
    return sum >= 0 && sum < 288 ? t->symbols[sum] : -1;
}

/* ---------------------------------------------------------------------------
 * A scanline: unfilter, to RGB, to the caller
 */
static unsigned pp_smp(const unsigned char *r, unsigned k, unsigned d) { /* sample k of a row (16 bit: both bytes) */
    if (d == 8) return r[k];
    if (d == 16) return (unsigned)r[2 * k] << 8 | r[2 * k + 1];
    return (r[k * d >> 3] >> (8 - d - (k * d & 7))) & ((1u << d) - 1);
}

static unsigned pp_s8(unsigned v, unsigned d) { return d == 8 ? v : d == 16 ? v >> 8 : v * 255 / ((1u << d) - 1); }

static void pp_px(unsigned char *o, unsigned r, unsigned g, unsigned b, unsigned a) { /* over white */
    if (a != 255) {
        r = (r * a + 255 * (255 - a) + 127) / 255;
        g = (g * a + 255 * (255 - a) + 127) / 255;
        b = (b * a + 255 * (255 - a) + 127) / 255;
    }
    o[0] = (unsigned char)r, o[1] = (unsigned char)g, o[2] = (unsigned char)b;
}

static int pp_row(pp_t *p) { /* the row in p->cur is complete: 1 stops the decoder */
    unsigned char *c = p->cur + 1, *u = p->prev + 1, *o = p->rgb;
    unsigned n = p->rb, bpp = p->bpp, d = p->depth, i, x;
    switch (p->cur[0]) {
    case 0:
        break;
    case 1:
        for (i = bpp; i < n; ++i) c[i] = (unsigned char)(c[i] + c[i - bpp]);
        break;
    case 2:
        for (i = 0; i < n; ++i) c[i] = (unsigned char)(c[i] + u[i]);
        break;
    case 3:
        for (i = 0; i < n; ++i) c[i] = (unsigned char)(c[i] + (((i >= bpp ? c[i - bpp] : 0) + u[i]) >> 1));
        break;
    case 4:
        for (i = 0; i < n; ++i) {
            int a = i >= bpp ? c[i - bpp] : 0, b = u[i], cc = i >= bpp ? u[i - bpp] : 0, pa = b - cc, pb = a - cc,
                pc = a + b - 2 * cc;
            if (pa < 0) pa = -pa;
            if (pb < 0) pb = -pb;
            if (pc < 0) pc = -pc;
            c[i] = (unsigned char)(c[i] + (pa <= pb && pa <= pc ? a : pb <= pc ? b : cc));
        }
        break;
    default:
        return 1;
    }
    for (x = 0; x < p->w; ++x, o += 3) {
        unsigned v, r, g, b, a = 255;
        switch (p->ctype) {
        case 0:
            v = pp_smp(c, x, d);
            if (p->key && v == p->keyv[0]) a = 0;
            g = pp_s8(v, d);
            pp_px(o, g, g, g, a);
            break;
        case 2:
            r = pp_smp(c, 3 * x, d), g = pp_smp(c, 3 * x + 1, d), b = pp_smp(c, 3 * x + 2, d);
            if (p->key && r == p->keyv[0] && g == p->keyv[1] && b == p->keyv[2]) a = 0;
            pp_px(o, pp_s8(r, d), pp_s8(g, d), pp_s8(b, d), a);
            break;
        case 3:
            v = pp_smp(c, x, d);
            if (v >= 256) v = 0;
            pp_px(o, p->pal[3 * v], p->pal[3 * v + 1], p->pal[3 * v + 2], p->pala[v]);
            break;
        case 4:
            g = pp_s8(pp_smp(c, 2 * x, d), d);
            pp_px(o, g, g, g, pp_s8(pp_smp(c, 2 * x + 1, d), d));
            break;
        default:
            pp_px(o, pp_s8(pp_smp(c, 4 * x, d), d), pp_s8(pp_smp(c, 4 * x + 1, d), d),
                  pp_s8(pp_smp(c, 4 * x + 2, d), d), pp_s8(pp_smp(c, 4 * x + 3, d), d));
            break;
        }
    }
    {
        unsigned char *t = p->cur; /* this row is the next one's "previous" */
        p->cur = p->prev, p->prev = t;
    }
    ++p->rows;
    return p->row(p->user, p->rgb, p->w) ? 0 : 1;
}

/* One inflated byte: into the window and the row; 1 for an error (more data than the image has, or the row's consumer stopped). */
static int pp_put(pp_t *p, unsigned char b) {
    if (p->rows >= p->h) return 1;
    p->win[p->wpos++ & (WIN - 1)] = b;
    ++p->total;
    p->cur[p->rpos++] = b;
    if (p->rpos == p->rb + 1) {
        p->rpos = 0;
        return pp_row(p);
    }
    return 0;
}

/* ---------------------------------------------------------------------------
 * Inflate (RFC 1951)
 */
static const unsigned short pp_lbase[29] = {3,  4,  5,  6,  7,  8,  9,  10, 11,  13,  15,  17,  19,  23, 27,
                                            31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258};
static const unsigned char pp_lext[29] = {0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2,
                                          2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 5, 5, 5, 0};
static const unsigned short pp_dbase[30] = {1,    2,    3,    4,    5,    7,    9,    13,    17,    25,
                                            33,   49,   65,   97,   129,  193,  257,  385,   513,   769,
                                            1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577};
static const unsigned char pp_dext[30] = {0, 0, 0, 0, 1, 1, 2, 2,  3,  3,  4,  4,  5,  5,  6,
                                          6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13};

static int pp_block(pp_t *p) { /* the symbols of one Huffman block with p->lit and p->dist; 0 at its end */
    for (;;) {
        int s = pp_sym(p, &p->lit), d, len, dist, e;
        if (s < 0) return -1;
        if (s < 256) {
            if (pp_put(p, (unsigned char)s)) return -1;
            continue;
        }
        if (s == 256) return 0;
        s -= 257;
        if (s >= 29) return -1;
        e = pp_bits(p, pp_lext[s]);
        if (e < 0) return -1;
        len = pp_lbase[s] + e;
        d = pp_sym(p, &p->dist);
        if (d < 0 || d >= 30) return -1;
        e = pp_bits(p, pp_dext[d]);
        if (e < 0) return -1;
        dist = pp_dbase[d] + e;
        if ((unsigned)dist > p->total) return -1;
        while (len--)
            if (pp_put(p, p->win[(p->wpos - (unsigned)dist) & (WIN - 1)])) return -1;
    }
}

static int pp_fixed(pp_t *p) {
    unsigned char lens[288];
    unsigned i;
    for (i = 0; i < 288; ++i) lens[i] = i < 144 ? 8 : i < 256 ? 9 : i < 280 ? 7 : 8;
    pp_build(&p->lit, lens, 288);
    for (i = 0; i < 30; ++i) lens[i] = 5;
    pp_build(&p->dist, lens, 30);
    return pp_block(p);
}

static int pp_dynamic(pp_t *p) {
    static const unsigned char order[19] = {16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15};
    unsigned char lens[320];
    huff_t cl;
    int a = pp_bits(p, 5), b = pp_bits(p, 5), c = pp_bits(p, 4), i, total;
    if (a < 0 || b < 0 || c < 0) return -1;
    a += 257, b += 1, c += 4;
    if (a > 286 || b > 30) return -1;
    memset(lens, 0, 19);
    for (i = 0; i < c; ++i) {
        int v = pp_bits(p, 3);
        if (v < 0) return -1;
        lens[order[i]] = (unsigned char)v;
    }
    if (pp_build(&cl, lens, 19)) return -1;
    total = a + b;
    for (i = 0; i < total;) {
        int s = pp_sym(p, &cl), rep, val = 0;
        if (s < 0) return -1;
        if (s >= 16 && (rep = pp_bits(p, s == 16 ? 2 : s == 17 ? 3 : 7)) < 0) return -1;
        if (s < 16) {
            lens[i++] = (unsigned char)s;
            continue;
        }
        if (s == 16) {
            if (!i) return -1;
            val = lens[i - 1], rep += 3;
        } else if (s == 17)
            rep += 3;
        else
            rep += 11;
        if (i + rep > total) return -1;
        while (rep--) lens[i++] = (unsigned char)val;
    }
    if (pp_build(&p->lit, lens, (unsigned)a) || pp_build(&p->dist, lens + a, (unsigned)b)) return -1;
    return pp_block(p);
}

static int pp_stored(pp_t *p) {
    int a, b, c, d;
    unsigned n;
    p->bits = 0, p->nbits = 0; /* to the byte boundary: fewer than 8 bits are ever held */
    if ((a = pp_next(p)) < 0 || (b = pp_next(p)) < 0 || (c = pp_next(p)) < 0 || (d = pp_next(p)) < 0) return -1;
    n = (unsigned)(a | b << 8);
    if ((n ^ 0xffffu) != (unsigned)(c | d << 8)) return -1;
    while (n--) {
        int v = pp_next(p);
        if (v < 0 || pp_put(p, (unsigned char)v)) return -1;
    }
    return 0;
}

static int pp_inflate(pp_t *p) {
    int last, type, r;
    do {
        last = pp_bits(p, 1), type = pp_bits(p, 2);
        if (last < 0 || type < 0) return -1;
        r = type == 0 ? pp_stored(p) : type == 1 ? pp_fixed(p) : type == 2 ? pp_dynamic(p) : -1;
        if (r) return -1;
    } while (!last);
    return 0;
}

/* ---------------------------------------------------------------------------
 * The file
 */
void pp_free(pp_t *p) {
    if (!p) return;
    free(p->cur), free(p->prev), free(p->rgb), free(p);
}

int pp_open(void *f, pp_t **out, unsigned *w, unsigned *h) {
    static const unsigned char sig[8] = {0x89, 'P', 'N', 'G', '\r', '\n', 0x1a, '\n'};
    unsigned char b[32];
    unsigned i, ch, bits, ctype;
    pp_t *p;
    *out = (pp_t *)0;
    if (fread(b, 1, 8, f) != 8) return 0;
    for (i = 0; i < 8; ++i)
        if (b[i] != sig[i]) return 0;
    if (fread(b, 1, 25, f) != 25 || pp_be32(b) != 13 || b[4] != 'I' || b[5] != 'H' || b[6] != 'D' || b[7] != 'R')
        return 0; /* length, type, the 13 bytes, the CRC */
    *w = pp_be32(b + 8), *h = pp_be32(b + 12), bits = b[16], ctype = b[17];
    if (!*w || !*h || *w > PP_MAX_SIDE || *h > PP_MAX_SIDE || *w * *h > PP_MAX_PX || b[18] || b[19] || b[20] > 1)
        return 0;
    ch = ctype == 0 || ctype == 3 ? 1 : ctype == 2 ? 3 : ctype == 4 ? 2 : ctype == 6 ? 4 : 0;
    if (!ch || (bits != 1 && bits != 2 && bits != 4 && bits != 8 && bits != 16)) return 0;
    if ((ctype == 3 && bits == 16) || ((ctype == 2 || ctype == 4 || ctype == 6) && bits < 8)) return 0;
    if (b[20]) return -1;
    p = calloc(1, sizeof *p);
    if (!p) return 0;
    *out = p;
    p->f = f, p->w = *w, p->h = *h, p->ctype = ctype, p->depth = bits;
    p->rb = (*w * ch * bits + 7) / 8;
    p->bpp = ch * bits >= 8 ? ch * bits / 8 : 1;
    memset(p->pala, 255, sizeof p->pala);
    p->cur = calloc(p->rb + 1, 1), p->prev = calloc(p->rb + 1, 1), p->rgb = calloc(*w * 3, 1);
    if (!p->cur || !p->prev || !p->rgb) return 0;
    for (;;) { /* the chunks up to the first IDAT */
        unsigned len;
        if (fread(b, 1, 8, f) != 8) return 0;
        len = pp_be32(b);
        if (len > 0x7fffffffu) return 0;
        if (b[4] == 'I' && b[5] == 'D' && b[6] == 'A' && b[7] == 'T') {
            p->left = len, p->have = 1;
            break;
        }
        if (b[4] == 'I' && b[5] == 'E' && b[6] == 'N' && b[7] == 'D') return 0;
        if (b[4] == 'P' && b[5] == 'L' && b[6] == 'T' && b[7] == 'E') {
            if (!len || len > 768 || len % 3 || fread(p->pal, 1, len, f) != len) return 0;
            p->npal = len / 3;
            len = 0;
        } else if (b[4] == 't' && b[5] == 'R' && b[6] == 'N' && b[7] == 'S' &&
                   ((ctype == 3 && len <= 256) || (ctype == 0 && len == 2) || (ctype == 2 && len == 6))) {
            unsigned char t[256];
            if (fread(t, 1, len, f) != len) return 0;
            if (ctype == 3)
                memcpy(p->pala, t, len);
            else {
                p->key = 1;
                for (i = 0; i < len / 2; ++i) p->keyv[i] = (unsigned)t[2 * i] << 8 | t[2 * i + 1];
                if (bits < 16) /* the key is a sample of the image's depth: its low bits */
                    for (i = 0; i < len / 2; ++i) p->keyv[i] &= (1u << bits) - 1;
            }
            len = 0;
        }
        if (fseek(f, (long)len + 4, 1)) return 0; /* the rest of a chunk we do not read, and its CRC */
    }
    if (ctype == 3 && !p->npal) return 0;
    {
        int c0 = pp_next(p),
            c1 = pp_next(p); /* the zlib header: deflate, a window of at most 32 kB, no preset dictionary */
        if (c0 < 0 || c1 < 0 || (c0 & 15) != 8 || (c0 >> 4) > 7 || ((c0 << 8 | c1) % 31) || (c1 & 0x20)) return 0;
    }
    return 1;
}

int pp_run(pp_t *p, int (*row)(void *, const unsigned char *, unsigned), void *user) {
    p->row = row, p->user = user;
    return !pp_inflate(p) && p->rows == p->h && !p->rpos;
}
