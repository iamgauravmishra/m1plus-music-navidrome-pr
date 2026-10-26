/* Cover cache and album helpers shared by the pages that show album art (patch/coverflow.c, patch/albums.c).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * The cache design (one JPEG per album, /mnt/mmc/.coverflow/<key>-168.jpg, an empty file marking "no
 * art") is q2-pod's, Copyright (c) 2026 Diamond Bond, MIT; see NOTICE and docs/architecture.md.
 */
#pragma once

#define ART_DIR "/mnt/mmc/.coverflow" /* the cache: <key>-168.jpg per album, an empty file for "no art" */

/* Pure pixel helpers, also built for the host (test/coverflow.py). */
unsigned cc_fnv(unsigned h, const char *s);
/* The centred square of a w x h image (byte order at[] = r, g, b, a positions; stride in bytes), size x size
 * RGBA over black into out: nearest neighbour (the Cover Flow textures) or an area average (box, the grid tiles). */
void cc_sample(const unsigned char *data, unsigned w, unsigned h, unsigned stride, const unsigned char *at,
               unsigned size, unsigned *out);
void cc_box(const unsigned char *data, unsigned w, unsigned h, unsigned stride, const unsigned char *at,
            unsigned size, unsigned *out);

#ifndef CF_HOST
const char *cc_str(void *rec, int field);              /* a record's string field, "" if none */
unsigned cc_album_key(void *rec);                      /* FNV-1a of artist then album, never 0 */
char *cc_path(char *out, unsigned size, unsigned key, const char *suffix);
long cc_file_size(const char *path);
const char *cc_url(char *out, unsigned key);           /* "file://<cache file>" (out holds 80), NULL: no art cached */
int cc_decode(void *w, const char *url, int unload, unsigned size, int box, unsigned *out);
void *cc_copy_list(void *list);                        /* a stock list copied into a deque of our own */
void *cc_albums(void);                                 /* the stock Albums list (getAllAlbum), copied; NULL if empty */
int cc_open_album(void *artist_row, int index);        /* the stock Albums row sequence; 0 once the page is requested */
/* The album order shared by Cover Flow and Albums (Settings > Cover Flow > Sort). The stock list is never reordered: the
 * sorted view is a permutation of its row numbers, and anything that goes back to stock (cc_open_album) takes the stock row. */
int cc_nocase(const char *a, const char *b);           /* ASCII case-insensitive compare (SQLite NOCASE, as the stock list groups) */
int cc_sort_artist(void);                              /* the setting: 1 Artist (default), 0 Album */
int cc_sort_toggle(void);                              /* flip it, saved atomically; the new state, or -1 when it could not be saved */
unsigned *cc_album_order(void *albums);                /* heap array of the rows in display order; NULL = stock order (Album mode, or no memory) */
void *cc_row(void *albums, const unsigned *order, unsigned i);   /* display row i of the list */
void *cc_playing(void);                                /* the stSongInfo of the track the player is on, NULL if nothing is queued */
#endif
