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

/* The same for Deezer's album search (https://api.deezer.com/search/album): the objects of the top-level "data" array, with title as name, artist.name as author, cover_medium (250 px) as art and id. -1: no "data" array. */
int pj_deezer(const char *json, unsigned n, pj_result_t *out, int max);

typedef struct {
    char title[PJ_NAME], artist[PJ_AUTHOR], album[PJ_NAME]; /* trackName, artistName, albumName */
    unsigned secs; /* duration in whole seconds, 0 = none */
    int synced; /* the text given is syncedLyrics (else plainLyrics) */
} pj_lrc_t;

/* LRCLIB's answer (https://lrclib.net/api/get: one object; /api/search: an array of them), n bytes at json: every record that has lyrics (synced and non blank, else plain and non blank; a record
 * with neither is skipped), in order, as fn(ctx, record, text) with the text decoded (line feeds stay line feeds, carriage returns are dropped, a text that does not fit cap ends at its last whole
 * line); fn returns 0 to stop. a and b are two scratch buffers of cap + 1 bytes (the decoded texts of the record being read); the text passed is one of them, valid during the call only. Returns the
 * records passed to fn, or -1 when the answer is not an object or an array. An object cut short by the end of the text is not passed. */
int pj_lrc_each(const char *json, unsigned n, unsigned cap, char *a, char *b,
                int (*fn)(void *, const pj_lrc_t *, const char *), void *ctx);
