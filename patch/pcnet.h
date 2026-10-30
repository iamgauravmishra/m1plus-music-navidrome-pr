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
    PN_CANCELLED /* the transfer was aborted by the page's Cancel (never shown: the show keeps its earlier status) */
};

/* The conditions to start (UI thread): the card is there, the Wi-Fi is connected (stock get_wifisignal), the clock is set, the CA bundle exists. 0 or PN_*. */
int pn_guard(void);
/* Refresh the shows shows[idx[0..n)] that have a feed url: the guards, then one worker thread. root is the Podcasts folder as the card spells it. 0 when the thread runs, else PN_* (nothing started). */
int pn_refresh(const char *root, const pc_show_t *shows, const int *idx, int n);
int pn_busy(void); /* a worker is running */
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
