/* A small, bounded JSON extractor for the iTunes search and lookup answers (patch/pcjson.c; docs/modules/podcasts.md "Search").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * demo has no JSON library and the answer is untrusted, so this is no parser: it walks the text once, without recursion and without allocating, finds the top-level "results" array and takes
 * five members of each object in it (collectionId, collectionName, artistName, feedUrl, artworkUrl100); everything else is skipped by its brackets and quotes. Every read is bounded by the
 * length given; every write by the field's size. Strings are decoded to UTF-8 (escapes, \uXXXX with surrogate pairs) and cut on a character boundary.
 */
#pragma once

#define PJ_MAX 25 /* results kept (the request asks for 25) */
#define PJ_NAME 80 /* a show's name, UTF-8 bytes with the NUL (cut before a continuation byte) */
#define PJ_AUTHOR 56
#define PJ_ART 160 /* the artwork url; one that does not fit is no url ("") */
#define PJ_DEPTH 32 /* nesting skipped; a deeper value ends the walk */

typedef struct {
    unsigned id; /* collectionId, 0 = none (a larger number is 0xffffffff) */
    char name[PJ_NAME]; /* collectionName */
    char author[PJ_AUTHOR]; /* artistName */
    char feed[PC_URL]; /* feedUrl: "" = none, also for one longer than the field (a cut address is no address) */
    char art[PJ_ART]; /* artworkUrl100, "" likewise */
} pj_result_t;

/* The objects of the top-level "results" array of the n bytes at json that have a collectionName or a feedUrl, at most max, in order, into out. An object cut short by the end of the text is
 * not kept. Returns how many (0 for an empty array), or -1 when there is no "results" array (not an answer of the store). Never reads outside json[0, n) or writes outside out[0, max). */
int pj_results(const char *json, unsigned n, pj_result_t *out, int max);
