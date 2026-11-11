/* One UTF-8 encoder for the payload (no dependencies: the pure parsers include it too).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

/* The bytes code point cp takes as UTF-8 (1..4). */
static inline unsigned m1_utf8_len(unsigned cp) { return cp < 0x80 ? 1u : cp < 0x800 ? 2u : cp < 0x10000 ? 3u : 4u; }

/* The line [p, stop) up to its newline; the next line starts at *next. Its length is without the CR. */
static inline unsigned m1_line(const char *p, const char *stop, const char **next) {
    const char *q = p;
    unsigned n;
    while (q < stop && *q != '\n') ++q;
    n = (unsigned)(q - p);
    *next = q < stop ? q + 1 : q;
    if (n && p[n - 1] == '\r') --n;
    return n;
}

/* The value of the hex digit c (either case), -1 for anything else. */
static inline int m1_hexval(unsigned c) {
    return c - '0' < 10u ? (int)(c - '0') : (c | 32) - 'a' < 6u ? (int)((c | 32) - 'a' + 10) : -1;
}

/* cp as UTF-8 at p (room for m1_utf8_len(cp) bytes, no NUL written); returns the length. The caller rules out
 * surrogates and values past U+10FFFF. */
static inline unsigned m1_utf8_put(char *p, unsigned cp) {
    unsigned n = m1_utf8_len(cp);
    if (n == 1)
        p[0] = (char)cp;
    else if (n == 2)
        p[0] = (char)(0xc0 | cp >> 6), p[1] = (char)(0x80 | (cp & 0x3f));
    else if (n == 3)
        p[0] = (char)(0xe0 | cp >> 12), p[1] = (char)(0x80 | (cp >> 6 & 0x3f)), p[2] = (char)(0x80 | (cp & 0x3f));
    else
        p[0] = (char)(0xf0 | cp >> 18), p[1] = (char)(0x80 | (cp >> 12 & 0x3f)), p[2] = (char)(0x80 | (cp >> 6 & 0x3f)),
        p[3] = (char)(0x80 | (cp & 0x3f));
    return n;
}
