/* FNV-1a over a string, the payload's one copy (no dependencies). The values are file names and keys on the card:
 * never change what a caller gets.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#define FNV_PRIME 16777619u

/* The bytes of s mixed into h (start with FNV_SEED, 2166136261). */
static inline unsigned m1_fnv(unsigned h, const char *s) {
    for (; *s; ++s) h = (h ^ (unsigned char)*s) * FNV_PRIME;
    return h;
}

/* The same with ASCII capitals folded to lower case (the stock library's NOCASE). */
static inline unsigned m1_fnv_fold(unsigned h, const char *s) {
    for (; *s; ++s) h = (h ^ (unsigned char)((unsigned char)*s - 'A' < 26u ? *s + 32 : *s)) * FNV_PRIME;
    return h;
}
