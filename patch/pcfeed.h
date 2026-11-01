/* Podcast feeds: the RSS push parser and the writers of .episodes / .show (patch/pcfeed.c; docs/modules/podcasts.md "Feeds").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Pure functions, no I/O but access(): the network worker (patch/pcnet.c) feeds libcurl's chunks to pf_push and writes what pf_render_* return. A feed reaches 4 MB / 600 items, so
 * nothing is built as a tree: a small state machine keeps the channel's title and image and the PF_KEEP newest items (by pubDate), and throws everything else away as it goes.
 */
#pragma once

#define PF_KEEP 20 /* items kept from a feed: the newest by pubDate */
#define PF_GUID 128 /* a guid, cut here (the same cut every time, so the match against the old entries holds) */
#define PF_URL 640 /* an enclosure url */
#define PF_TYPE 32
#define PF_MAX_FILE \
    100 /* a file name made from a title: bytes, with its date and extension (a ".part" and the path still fit PC_FILE) */

typedef struct {
    char title[PC_TITLE];
    char guid[PF_GUID];
    char url[PF_URL];
    char type[PF_TYPE]; /* the enclosure's MIME type */
    char desc
        [PC_DESC]; /* itunes:summary, else description, else content:encoded: plain text (HTML stripped), at most PC_DESC_CUT bytes; "" = none */
    unsigned pub, dur, length; /* seconds since 1970 (0 = none), seconds, bytes */
} pf_item_t;

typedef struct pf_parser pf_parser_t;

pf_parser_t *pf_new(void); /* NULL when there is no memory */
void pf_free(pf_parser_t *p);
void pf_push(pf_parser_t *p, const char *data, unsigned n); /* the next bytes of the feed, any split */
int pf_is_feed(const pf_parser_t *p); /* an <rss> or <channel> element was seen */
int pf_items(const pf_parser_t *p); /* items kept (at most PF_KEEP), newest first */
const pf_item_t *pf_item(const pf_parser_t *p, int i); /* kept item i, 0 <= i < pf_items (newest first), else NULL */
int pf_seen(const pf_parser_t *p); /* items with an enclosure seen in the whole feed */
const char *pf_title(const pf_parser_t *p); /* the channel's title ("" = none) */
const char *
pf_image(const pf_parser_t *p); /* the channel's picture url: itunes:image href, else <image><url> ("" = none) */
const char *pf_author(
    const pf_parser_t *p); /* the channel's itunes:author (not an item's; "" = none), at most PC_AUTHOR - 1 bytes */
const char *pf_category(
    const pf_parser_t *p); /* the first itunes:category's text attribute ("" = none), at most PC_CAT - 1 bytes */
const char *pf_summary(
    const pf_parser_t
        *p); /* the channel's itunes:summary, else description, as plain text, at most PC_DESC_CUT bytes ("" = none) */

/* The .episodes text (header, then one line per kept item, then the old lines whose file is still in dir) into out (cap bytes); returns its length. old / oldn: the file as it is now (NULL: none).
 * An item whose guid an old line has keeps that line's file name; the others get "YYYY-MM-DD Title.ext". *fresh: kept items no old line had. dir: the show folder's path (the files are looked at with access). */
unsigned pf_render_episodes(const pf_parser_t *p, const char *dir, const char *old, unsigned oldn, char *out,
                            unsigned cap, unsigned *fresh);
/* The line of .episodes (eps, n bytes) whose file name is `file`: its enclosure url (u=) into url (usize bytes) and its length (l=, 0 when none or not a number) into *length. 0 when there is no such line, no url, or the url does not fit. */
int pf_find_episode(const char *eps, unsigned n, const char *file, char *url, unsigned usize, unsigned *length);
/* The .show text. title / feed / image / author / category / desc: plain text (control bytes become spaces; the last three are written only when not empty), checked: seconds since 1970 (0 = never).
 * Pure: the caller merges (a refresh passes the feed's value, else the show's old one). Returns its length. */
unsigned pf_render_show(const char *title, const char *feed, const char *image, unsigned checked, const char *author,
                        const char *category, const char *desc, char *out, unsigned cap);
/* A title as a folder name (forbidden characters replaced, at most PF_MAX_FILE bytes, no leading or trailing dot or space); "" when nothing is left. */
void pf_folder_name(char *out, unsigned size, const char *title);
/* The date of an RFC 822 / 2822 pubDate ("Thu, 30 Oct 2026 11:00:00 GMT", "30 Oct 2026 07:00 -0400", zones UT GMT Z EST EDT CST CDT MST MDT PST PDT or +hhmm), seconds since 1970; 0 when it is not one. */
unsigned pf_rfc822(const char *s);
/* "1234", "12:34" or "1:02:03" as seconds (a fraction is dropped); 0 when it is none of those. */
unsigned pf_duration(const char *s);
