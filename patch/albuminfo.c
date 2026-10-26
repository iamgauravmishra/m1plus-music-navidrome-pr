/* M1 Pod album view: the stock albuminfo_page (an album's tracks, opened by the stock Albums list,
 * Cover Flow, Artists and the All albums card) restyled to the M1 Pod album page: a 120 px sharp
 * cover, the title (21 px white), the artist (18 px grey), a "year . N tracks" line, the stock
 * Play all in the dark button style and a Shuffle button beside it.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * One hook, albuminfo_listitem0_layout (0x526264): the function that builds the page's header item,
 * called only while albuminfo_page_init (or its to-foreground rebuild) builds the list. Never at
 * boot, never in paint. The hook runs the stock function to completion and then, if the header is
 * exactly what stock builds (the cover image, the title and artist hscroll_labels, the Play all
 * button) and the kill switch is absent, restyles it in place; anything else leaves stock alone.
 * The stock header is a 100 px list_item: image 100x100, title and artist at x 108, Play all
 * 90x28 (an orange pill image with its text baked in). The page's theme (styles/albuminfo_page.bin,
 * tools/mod_ipodrows.py) defines the dark button and the 15 px line; a header the hook does not
 * touch keeps the stock look.
 *
 * Shuffle is the stock Play all handler's own sequence (@0x525d48: the page's list, loadSongList,
 * start_player, force_refreshflag) with the stock Shuffle mode and a random first track from the
 * Shuffle page's generator (patch/shuffle.c): the page stays up, as with Play all.
 */
#include "offsets.inc"
#include "stock.h"
#include "i18n.h"

#define KILL_FILE "/mnt/mmc/m1pod-off"
#define F_OK 0
#define P(r, off) (*(char **)((char *)(r) + (off)))
#define I(r, off) (*(int *)((char *)(r) + (off)))

extern unsigned pod_rand(unsigned n);       /* patch/shuffle.c */
extern void pod_toast(const char *text);
extern void pod_set_mode(int mode);

static int is_type(void *w, const char *type) {
    const char *t = w ? widget_get_type(w) : (const char *)0;
    return t && strcmp(t, type) == 0;
}

/* Shuffle: the stock Play all sequence (@0x525d48) from a random track, in the stock Shuffle mode.
 * The class is g_class_type, as there (albuminfo_page_init stored classinfo[0]: 0xff10, or 0xff11
 * for an artist's album and the All albums card). Nothing is written until the queue is ready and
 * the track is on the card. */
static int ah_on_shuffle(void *ctx, void *e) {
    void *list = *(void **)PDEQ_SHOWLIST, *pick, *queue;
    unsigned n = list ? deque_size(list) : 0, at, idx = 0;
    int cls = *(int *)G_CLASS_TYPE, found;
    (void)ctx; (void)e;
    if (!n) return RET_OK;
    at = pod_rand(n);
    pick = deque_at(list, at);
    if (!pick || access(P(pick, REC_PATH), F_OK)) {
        pod_toast(TR("Storage unavailable"));
        return RET_OK;
    }
    queue = _create_deque("stSongInfo");
    if (!queue) return RET_OK;
    deque_init(queue);
    found = loadSongList(queue, P(pick, REC_NAME), I(pick, REC_CUE_START), cls);
    n = deque_size(queue);
    if (found >= 0 && n) { /* a duplicate file name resolves to its first copy: the drawn row wins */
        if (at < n && !strcmp(P(deque_at(queue, at), REC_PATH), P(pick, REC_PATH))) idx = at;
        else if ((unsigned)found < n) idx = (unsigned)found;
        pod_set_mode(MODE_SHUFFLE);
        start_player(queue, (int)idx, cls, PLAY_MODE);
        *(unsigned char *)FORCE_REFRESH = 1;
    }
    deque_destroy(queue);
    return RET_OK;
}

/* "8 tracks" in the player's language: the key by n == 1 ("%d track" / "%d tracks"; a language with more
 * plural forms words both the same), the number put where the translation has its %d. The table's text is
 * never a printf format. Returns the length. */
static unsigned ah_count(char *out, unsigned size, int n) {
    const char *f = TR(n == 1 ? "%d track" : "%d tracks");
    char digits[12];
    unsigned o = 0, d = 0, i;
    for (i = (unsigned)(n < 0 ? 0 : n); d == 0 || i; i /= 10) digits[d++] = (char)('0' + i % 10);
    while (*f && o + 1 < size) {
        if (f[0] == '%' && f[1] == 'd') {
            while (d && o + 1 < size) out[o++] = digits[--d];
            f += 2;
        } else out[o++] = *f++;
    }
    out[o] = 0;
    return o;
}

/* "1959 . 8 tracks" when a track carries a year (the first that does), else "8 tracks"; the All
 * albums card (classinfo[8], @0x4eebec) is only a count. */
static void ah_meta(char *out, unsigned size, int n) {
    int year = 0, i;
    unsigned o = 0;
    if (!*(unsigned char *)(CLASSINFO + CLASSINFO_ALL_SONGS)) {
        void *list = *(void **)PDEQ_SHOWLIST;
        for (i = 0; list && i < n && !year; ++i) {
            year = I(deque_at(list, (unsigned)i), REC_YEAR);
            if (year < 1000 || year > 2999) year = 0;
        }
    }
    if (year) o = (unsigned)snprintf(out, size, "%d \xc2\xb7 ", year);
    ah_count(out + o, size - o, n);
}

/* The header, after stock built it. item is the list_item holding the four widgets in stock's
 * order. The two new widgets are made first: if either fails, nothing is moved. */
__attribute__((noinline)) static void ah_restyle(void *item) {
    void *art, *title, *artist, *play, *meta, *shuf;
    void *list = *(void **)PDEQ_SHOWLIST;
    char line[64];
    if (!item || access(KILL_FILE, F_OK) == 0 || widget_count_children(item) != 4) return;
    art = widget_get_child(item, 0), title = widget_get_child(item, 1);
    artist = widget_get_child(item, 2), play = widget_get_child(item, 3);
    if (!is_type(art, "image") || !is_type(title, "hscroll_label") || !is_type(artist, "hscroll_label") ||
        !is_type(play, "button"))
        return;
    meta = hscroll_label_create(item, AH_TEXT_X, AH_META_Y, AH_TEXT_W, AH_META_H);
    shuf = button_create(item, AH_SHUFFLE_X, AH_BTN_Y, AH_BTN_W, AH_BTN_H);
    if (!meta || !shuf) {
        if (meta) widget_destroy(meta);
        if (shuf) widget_destroy(shuf);
        return;
    }
    widget_use_style(meta, "srlabel_meta15_style");
    hscroll_label_set_ellipses(meta, 1);
    widget_set_sensitive(meta, 0); /* decoration: a drag that starts on it scrolls the list */
    ah_meta(line, sizeof line, list ? (int)deque_size(list) : 0);
    widget_set_text_utf8(meta, line);
    widget_use_style(play, "btn_albumbtn_style");
    widget_set_tr_text(play, "Play all");
    widget_move(play, AH_PAD, AH_BTN_Y);
    widget_resize(play, AH_BTN_W, AH_BTN_H);
    widget_use_style(shuf, "btn_albumbtn_style");
    widget_set_tr_text(shuf, "Shuffle");
    widget_on(shuf, EVT_CLICK, ah_on_shuffle, (void *)0);
    widget_move(art, AH_PAD, AH_ART_Y);
    widget_resize(art, AH_ART, AH_ART);
    image_set_draw_type(art, IMAGE_DRAW_CENTER); /* never scaled: the 120 px file, or the 100 px default disc, 1:1 */
    widget_move(title, AH_TEXT_X, AH_TITLE_Y);
    widget_resize(title, AH_TEXT_W, AH_TITLE_H);
    widget_move(artist, AH_TEXT_X, AH_ARTIST_Y);
    widget_resize(artist, AH_TEXT_W, AH_ARTIST_H);
    widget_resize(item, widget_get_prop_int(item, "w", 0), AH_HDR_H);
}

/* The hook (tools/pod.py ALBUMINFO_HEADER): stock first, then ours. */
void m1pod_albuminfo_header(void *item) {
    stock_albuminfo_header_trampoline(item);
    ah_restyle(item);
}
