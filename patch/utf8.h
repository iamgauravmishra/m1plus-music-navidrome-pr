/* One UTF-8 encoder for the payload (no dependencies: the pure parsers include it too).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

/* The bytes code point cp takes as UTF-8 (1..4). */
static inline unsigned m1_utf8_len(unsigned cp) { return cp < 0x80 ? 1u : cp < 0x800 ? 2u : cp < 0x10000 ? 3u : 4u; }

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
