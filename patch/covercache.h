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
unsigned cc_key_of(const char *artist, const char *album);   /* the same key from the two names */
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
int cc_name_cmp(const char *a, const char *b);         /* cc_nocase with a leading "The " dropped from both (the Artist order's name key) */
void cc_heapsort(unsigned *v, unsigned n, int (*cmp)(unsigned, unsigned)); /* in place, no memory; cmp must be total (break ties by the row number) */
int cc_sort_artist(void);                           /* the setting: 1 Artist (default), 0 Album */
int cc_sort_toggle(void);                              /* flip it, saved atomically; the new state, or -1 when it could not be saved */
unsigned *cc_album_order(void *albums);                /* heap array of the rows in display order; NULL = stock order (Album mode, or no memory) */
void *cc_row(void *albums, const unsigned *order, unsigned i);   /* display row i of the list */
void *cc_playing(void);                                /* the stSongInfo of the track the player is on, NULL if nothing is queued */

/* The cache builder, shared by Cover Flow (its Preparing screen, and Settings > Cover Flow > Rebuild Covers) and the
 * Albums page (in the background). ONE worker thread app-wide: a job set is held from cc_build_open until
 * cc_build_stop, and cc_build_open refuses while one is held. The owner polls the counters from a page-scoped timer
 * (UI thread) and must call cc_build_stop (cancel, join, free) when it is done with the set and when its page is destroyed.
 * The thread touches only its own jobs, the counters, files under ART_DIR and the stock art calls under parse_cover_mutex;
 * never a widget, a deque or the image manager.
 *   CC_MISSING  only albums with no cache file (neither a picture nor the empty "no art" marker); cc_build_add skips the rest
 *   CC_REBUILD  every album is extracted again and its file replaced (temp + rename), a marker too, so an album that gained
 *               art gets it; an album that now yields none keeps what it has (old files stay until a new one replaces them) */
enum { CC_MISSING = 0, CC_REBUILD = 1 };
#define CC_MAX_JOBS 4000                                /* the job array is bounded (Cover Flow's MAX_ALBUMS) */
int cc_build_open(unsigned capacity, int mode);         /* 1: an empty job set held; 0: another set is held, or no memory */
int cc_build_add(const char *track, unsigned key);      /* 1 added; 0 skipped (CC_MISSING and the file exists); -1 full or no memory */
int cc_build_start(void);                               /* 1: the worker runs. 0: nothing to build, card full (MIN_FREE_MB), or no thread: the set is freed */
int cc_build_done(void);                                /* albums finished so far (advances as files appear) */
int cc_build_total(void);
int cc_build_running(void);                             /* a thread was started and the set is not stopped yet */
int cc_build_busy(void);                                /* a job set is held */
void cc_build_stop(void);                               /* cancel, join (bounded by one album's art), free; safe when nothing is held */
/* Albums by distance from row `centre` (the centre, then one after, one before, ...), as the shared album order shows them
 * (`order` may be NULL): each one with a track path is added. Returns the number of jobs held after (cc_build_total). */
int cc_build_near(void *albums, const unsigned *order, unsigned centre);
#endif
