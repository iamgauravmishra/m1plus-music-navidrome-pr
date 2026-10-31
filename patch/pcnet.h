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
    PN_PAUSED /* a download stopped for a refresh and kept in the queue (never shown) */
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
int pn_busy(void); /* a refresh worker is running (a download worker is pn_dl_running) */
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
/* Subscribe to the urls in <root>/subscriptions.txt that no show has yet: a folder and a .show file each (the title is the host until the first refresh names it). Returns how many were
 * added (the shows in the file already there do not count), -1 when there is no such file. shows[0..nshows): the folders now there. */
int pn_import(const char *root, const pc_show_t *shows, int nshows);

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
