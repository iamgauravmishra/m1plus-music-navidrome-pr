/* Podcast feeds on the network: subscribe (import), refresh one show or all (patch/pcnet.c; docs/modules/podcasts.md "Feeds").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * ONE detached pthread does all the network and card writes of a refresh, one show at a time; the UI never calls into it. The page asks pn_refresh (UI thread: the guards, then the
 * thread) and afterwards only READS the status record (pn_busy / pn_gen / pn_progress / pn_current / pn_status) from its own timer, and reloads the shows when pn_gen changed: AWTK is
 * not thread safe, and the model's list functions stay the one source of the page's rows (the worker writes the same .episodes / .show files they read).
 */
#pragma once

#define PN_CA \
    "/etc/m1plus-cacert.pem" /* the CA bundle libcurl verifies with: Mozilla's roots, in the firmware (tools/mod_cacerts.py; stock's /etc/ssl/certs is empty) */
#define PN_MIN_EPOCH \
    1750000000u /* a clock before this (mid 2025, before the firmware existed) was never set: certificates would not verify */
#define PN_FEED_CAP 8388608u /* a feed larger than this (after gzip) is refused */
#define PN_COVER_CAP 6291456u /* a cover picture larger than this is refused while it downloads */
#define PN_IMPORT_FILE "subscriptions.txt" /* in the Podcasts folder: one feed url a line */
#define PN_OPML_FILE \
    "subscriptions.opml" /* in the Podcasts folder: an OPML export of another app (any *.opml in the card root is read too) */
#define PN_EXPORT_FILE \
    "subscriptions-export.opml" /* what the Subscriptions page's Export OPML writes, in the Podcasts folder */

/* Results of a refresh, per feed (and what the guards say): the page shows the words. */
enum {
    PN_OK = 0,
    PN_NOWIFI, /* the Wi-Fi is not connected */
    PN_NOCLOCK, /* the clock was never set (certificates need the date) */
    PN_NOCERT, /* PN_CA is missing, or libcurl cannot read it */
    PN_CERT, /* the server's certificate was refused */
    PN_NET, /* no connection, no answer, a time-out */
    PN_GONE, /* HTTP 404 or 410 */
    PN_HTTP, /* another HTTP error */
    PN_NOTFEED, /* the answer is not an RSS feed (or it is too large) */
    PN_STORAGE, /* no card, or a file could not be written */
    PN_MEM, /* no memory, or no thread */
    PN_BUSY, /* a refresh is already running */
    PN_CANCELLED, /* the transfer was aborted by the page's Cancel (never shown: the show keeps its earlier status) */
    PN_CARDFULL, /* a download: the card would keep less than PN_DL_MARGIN_KB free */
    PN_NOTAUDIO, /* a download: the answer is a web page (Content-Type text/...), not an episode */
    PN_QFULL, /* the download queue is full (PN_QMAX) */
    PN_PAUSED, /* a download stopped for a refresh and kept in the queue (never shown) */
    PN_NOFEED /* search: an Apple Podcasts address whose show has no feed address */
};

/* Episode downloads (docs/modules/podcasts.md "Downloads"). The policy follows q2-podcasts (MIT): one at a time, chunks written with open / write / fsync / close, Range resume, a stall limit,
 * retries after 10, 20 and 40 s, a free-space margin. The queue is in memory only. */
/* PN_QMAX: downloads queued or running. PN_DL_BUF: bytes gathered before a chunk is written (open, write, fsync, close), so the card is rarely held busy. PN_DL_MARGIN_KB: the card always keeps this much
 * free (32 MB), checked before the download and before every chunk. PN_DL_PATH_MAX: the longest path of a download, the .part file included. PN_DL_STALL: seconds without a byte (libcurl's low-speed
 * time-out at 1 byte a second). PN_DL_RETRIES: network failures retried, after 10, 20 and 40 s (the count starts again after an attempt that got bytes). PN_DL_MAX_BYTES: a larger download is
 * refused (the file offsets are 32 bit). PN_FAILS: download failures remembered for the rows. */
#define PN_QMAX 32
#define PN_DL_BUF 524288u
#define PN_DL_MARGIN_KB 32768u
#define PN_DL_PATH_MAX 240
#define PN_DL_STALL 60
#define PN_DL_RETRIES 3
#define PN_DL_MAX_BYTES 2147483647u
#define PN_FAILS 16

enum { PN_DL_NONE = 0, PN_DL_WAIT = 1, PN_DL_ACTIVE = 2, PN_DL_FAILED = 3 };

/* The conditions to start (UI thread): the card is there, the Wi-Fi is connected (stock get_wifisignal), the clock is set, the CA bundle exists. 0 or PN_*. */
int pn_guard(void);
/* Refresh the shows shows[idx[0..n)] that have a feed url: the guards, then one worker thread. root is the Podcasts folder as the card spells it. 0 when the thread runs, else PN_* (nothing started). */
int pn_refresh(const char *root, const pc_show_t *shows, const int *idx, int n);
int pn_busy(
    void); /* a refresh worker is running (a download worker is pn_dl_running, a search or preview worker pn_job_busy) */
void pn_cancel(
    void); /* UI thread: ask the worker to stop: the transfer in progress is aborted (libcurl's transfer-info callback), no further show is started */
int pn_cancelling(void); /* a worker is running and was asked to stop */
unsigned pn_part(
    void); /* how far the show being refreshed has come, 0..1000 (the feed's length when the server gave it; the picture is the last tenth) */
/* The last job: shows refreshed (OK, up to date or new), shows that failed, and whether Cancel ended it. Valid when pn_busy() is 0. */
void pn_summary(unsigned *ok, unsigned *failed, int *cancelled);
unsigned pn_gen(void); /* changes whenever the status record does (a show finished, the worker ended) */
void pn_progress(int *done, int *total); /* shows finished / asked, of the last (or running) job */
unsigned pn_current(void); /* pc_hash of the feed url being fetched now, 0 when none */
int pn_status(
    unsigned feed, int *code,
    unsigned *
        fresh); /* the last result of the feed (pc_hash of its url) in this session: 1 and *code (PN_*), *fresh new items; 0 when there is none */
/* Subscribe to the feeds the card offers that no show has yet: the lines of <root>/subscriptions.txt and the outlines of <root>/subscriptions.opml and of every *.opml in the card's root (patch/pcopml.h), one
 * source after another sharing the 40 shows' room. A folder and a .show file each (the title is the OPML's name, else the host, until the first refresh names it). An OPML file all of whose outlines were seen
 * (and that held one) is renamed <name>.imported; subscriptions.txt stays. Returns how many were added (the shows already there do not count), -1 when there is no source at all. shows[0..nshows): the folders now there. */
int pn_import(const char *root, const pc_show_t *shows, int nshows);
/* How many import sources the card has now (subscriptions.txt, subscriptions.opml, *.opml in the card's root): the Shows page's "..." shows Import from Card when it is not 0. */
int pn_import_found(const char *root);
/* Write Podcasts/subscriptions-export.opml: OPML 2.0, one outline per show with a feed address, by title, atomically. *count: the shows written. 1 when written, 0 when not (nothing is left behind). */
int pn_export(const char *root, const pc_show_t *shows, int nshows, int *count);
/* Unsubscribe: the show's .show rewritten without its feed address (nothing else changes; the .episodes stay). 1 when written. */
int pn_unsubscribe(const char *root, const pc_show_t *show);
/* Unsubscribe completely, as the Show page does: pn_unsubscribe, the .part files and queued downloads of the show gone, and with no episode file left its own files and folder too. 0 not written (nothing touched), 1 the show stays (files left), 2 gone. */
int pn_unsubscribe_show(const char *root, const pc_show_t *show);

/* ---- Downloads. All of these run on the UI thread; the worker thread (one at a time, never beside a refresh) only reads and writes the status record. */
/* The key of an episode in the queue and the failure table: pc_hash of "<show folder>/<file name>". */
unsigned pn_dl_key(const char *dir, const char *file);
/* Queue the download of file in the show folder dir (the names as the model has them; root is the Podcasts folder). The guards run first (card, Wi-Fi, clock, CA bundle: PN_*), a path over PN_DL_PATH_MAX is PN_STORAGE, a full queue PN_QFULL;
 * a queued or running one is left as it is (a cancel not yet taken is undone). Starts the worker when none runs. 0 when queued. */
int pn_dl_add(const char *root, const char *dir, const char *file);
/* Take the episode out of the queue; one that is running is aborted at once (the .part stays: a later add resumes it). */
void pn_dl_cancel(unsigned key);
/* Start the worker for the queued downloads when none runs (the page's timer calls this after a refresh and after a pause). The guards run first; when they fail every queued download fails with their code (shown on its row). 0 or PN_*. */
int pn_dl_start(void);
/* Ask a running download worker to stop and keep the queue (for a refresh); pn_dl_running() turns 0 when it has. */
void pn_dl_pause(void);
int pn_dl_running(void); /* the download worker thread is running */
int pn_dl_count(void); /* downloads queued or running */
int pn_dl_waiting(void); /* downloads queued and not running */
unsigned pn_dl_gen(
    void); /* moves with every step of progress (another percent, or another MB when the length is unknown) and every state change */
/* The state of an episode: PN_DL_NONE, PN_DL_WAIT (queued, or waiting to retry), PN_DL_ACTIVE (*got of *total bytes; total 0 = unknown), PN_DL_FAILED (*code PN_*). */
int pn_dl_state(unsigned key, int *code, unsigned *got, unsigned *total);
/* The download being fetched now: its key (0 when none) and its progress. */
unsigned pn_dl_current(unsigned *got, unsigned *total);
/* Forget the failure of an episode (its row is a plain remote one again, or Paused with a .part). */
void pn_dl_clear(unsigned key);
/* The n-th download the Downloads page lists, from 0: the queue in the order it was asked (dir, file, *code 0), then the failed ones (*code the PN_* reason). Returns its key, 0 past the last. dir and file take PC_FILE bytes. */
unsigned pn_dl_listed(int n, char *dir, char *file, int *code);
/* KB free for a non-root user on the file system of path (statfs); 0 when it fails (*kb is then not set). The Downloads page's storage line. */
int pn_free_kb(const char *path, unsigned *kb);

/* ---- Search (docs/modules/podcasts.md "Search"). One worker at a time, never beside a refresh or a download (the page pauses the downloads first, as for a refresh). All of these run on the UI thread; the worker only
 * writes the record they read. The country of the store is a constant: a region switch comes later. */
#define PN_COUNTRY "US"
#define PN_SEARCH_URL \
    "https://itunes.apple.com/search?media=podcast&entity=podcast&limit=25&country=" PN_COUNTRY "&term="
#define PN_LOOKUP_URL "https://itunes.apple.com/lookup?id="
#define PN_JSON_CAP 98304u /* a search or lookup answer over 96 KB is cut there (25 results are about 44 KB) */
#define PN_THUMB_CAP 262144u /* a result's artwork (about 5 KB) over this is refused */
#define PN_SEARCH_DIR \
    "/mnt/mmc/.m1plus/podcasts/search" /* the thumbnails t<n>.jpg|png and the preview's cover preview.jpg: scratch, made again by every search */
#define PN_PREVIEW_COVER PN_SEARCH_DIR "/preview.jpg"

enum { PN_S_IDLE = 0, PN_S_QUERY = 1, PN_S_THUMBS = 2, PN_S_DONE = 3 };

/* What a text typed in the search field is: 0 a search term, 1 a feed address (http:// or https://, not an Apple Podcasts show link), 2 an Apple Podcasts show link (podcasts.apple.com ... /id<digits>; the digits into id, size bytes: ids pass 32 bits). */
int pn_classify(const char *text, char *id, unsigned size);
/* Start the search for the UTF-8 term: the guards, the old thumbnails removed, one worker (the query, then the artwork of each result one by one). 0 when it runs; PN_BUSY when a worker runs (the page waits and asks again). */
int pn_search(const char *term);
int pn_job_busy(void); /* a search or preview worker is running */
int pn_search_state(
    void); /* PN_S_*: the query runs / its answer is in and the artwork follows / the worker has ended */
int pn_search_code(
    void); /* the query's result once the answer is in (PN_OK, or PN_NET, PN_HTTP, ... and PN_CANCELLED) */
unsigned pn_search_gen(void); /* moves whenever the answer or a thumbnail arrives, and when the worker ends */
int pn_search_count(void); /* results (valid once the state is past PN_S_QUERY with PN_OK) */
const pj_result_t *pn_search_result(int i);
int pn_search_thumb(int i, char *path,
                    unsigned size); /* 1 and the path of result i's picture file when it has arrived */
void pn_search_clean(void); /* remove the thumbnails and forget the results */
/* Preview a show: the feed at url (an address), or the feed the store's lookup gives for the Apple id digits (id not empty), fetched and parsed as a refresh does, held in memory (not a show folder), with its picture shrunk to PN_PREVIEW_COVER. 0 when it runs. */
int pn_preview(const char *url, const char *id);
int pn_preview_state(void); /* 0 none, 1 running, 2 done */
int pn_preview_code(void); /* PN_OK, or why not (PN_NOFEED: the lookup found no feed address) */
void *pn_preview_parser(void); /* the held pf_parser_t, NULL when none */
const char *pn_preview_feed(void); /* the feed address of the held preview */
int pn_preview_cover(void); /* the preview's picture file is there */
void pn_preview_drop(void); /* free the held preview and its picture */
/* Subscribe to the held preview exactly as an import and its first refresh would: a folder named from the feed's title, .episodes, .show (feed, title, image, author, category, description), cover.jpg. root: the Podcasts folder; shows[0..nshows): the folders now there.
 * Returns PN_OK (*dir the folder's name, the preview dropped), PN_STORAGE when nothing could be written (nothing is left behind), PN_NOTFEED when no preview is held. UI thread, no network. */
int pn_subscribe(const char *root, const pc_show_t *shows, int nshows, char *dir, unsigned dsize);
