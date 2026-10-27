/* M1+ Pod album view: the stock albuminfo_page (an album's tracks, opened by the stock Albums list,
 * Cover Flow, Artists and the All albums card) restyled to the M1+ Pod album page (an Apple Music style
 * detail page): a centred 160 px cover with 10 px rounded corners, the title (22 px white), the artist
 * (18 px grey) and a "year . N tracks" line (15 px) centred under it, and a row of a round Shuffle button
 * (a 38 px disc in a 44 px touch rectangle) and the stock Play all as a white 180x40 pill (in a 44 px high
 * button) with a play glyph.
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
 * tools/mod_ipodrows.py) defines the centred text styles and the two button styles (Shuffle's disc and
 * glyph and the pill's play glyph are images, tools/mod_icons.py); a header the hook does not touch keeps
 * the stock look. The cover's corners are painted from its own after-paint in the colour behind them, and a real cover
 * tints the page (ah_*, below); a cover smaller than the box (a small embedded image) sits centred and keeps square corners.
 *
 * Play all and Shuffle share the stock Play all handler's sequence (@0x525d48: the page's list, the track on the card,
 * loadSongList) and then open Now Playing the way a track row's tap does (@0x52569c, ah_open_player); Shuffle sets the
 * stock Shuffle mode and starts from a random track (the generator of patch/shuffle.c). The hook takes the stock Play
 * all handler off its button and binds ours.
 */
#include "offsets.inc"
#include "stock.h"
#include "i18n.h"
#include "home.h"
#include "common.h"
#include "covercache.h"

#define P(r, off) (*(char **)((char *)(r) + (off)))
#define I(r, off) (*(int *)((char *)(r) + (off)))

extern unsigned pod_rand(unsigned n);       /* patch/shuffle.c */
extern void pod_toast(const char *text);
extern void pod_set_mode(int mode);

/* Open Now Playing on the queue exactly as a track row's tap does (the stock row handler @0x52569c, its tail
 * @0x5258c8..0x525970): when songerinfoflag is set and a playing_page is in the stack, the windows above it are popped
 * with navigator_back and the old playing_page is closed (the stock loop, which also stops at home_page); then
 * navigator_to_with_context("playing_page", {queue, index, class, 2}), whose init starts the player. Stock's loop
 * trusts every navigator_back to change the top window at once (true for these pages: none has a close animation);
 * a bound of AH_POP_MAX turns that trust into a limit, after which the page is opened over what is left. */
static void ah_open_player(void *queue, int idx, int cls) {
    struct { void *dq; int idx, cls, mode; } context;
    if (*(unsigned char *)SONGER_FLAG && navigator_window_is_exist("playing_page")) {
        void *wm = window_manager();
        int i;
        for (i = 0; i < AH_POP_MAX; ++i) {
            void *top = window_manager_get_top_window(wm);
            const char *name = top ? P(top, WIDGET_NAME) : (const char *)0;
            if (!name) break;
            if (!strcmp(name, "playing_page")) {
                window_close(top);
                break;
            }
            if (!strcmp(name, "home_page")) break;
            navigator_back();
        }
    }
    context.dq = queue, context.idx = idx, context.cls = cls, context.mode = PLAY_MODE;
    navigator_to_with_context("playing_page", &context); /* playing_page_init -> start_player copies the queue */
}

/* Play all (shuffle == 0: the page's first track) and Shuffle (a random track, the stock Shuffle mode): the stock Play
 * all sequence (@0x525d48: the track on the card, loadSongList, the page's class g_class_type, which albuminfo_page_init
 * stored from classinfo[0]: 0xff10, or 0xff11 for an artist's album and the All albums card), then Now Playing the way
 * a track tap opens it. Nothing is written until the queue is ready and the track is on the card; a missing track is
 * the usual message and the page stays. */
static void ah_play(int shuffle) {
    void *list = *(void **)PDEQ_SHOWLIST, *pick, *queue;
    unsigned n = list ? deque_size(list) : 0, at = 0, idx = 0;
    int cls = *(int *)G_CLASS_TYPE, found;
    if (!n) return;
    if (shuffle) at = pod_rand(n);
    pick = deque_at(list, at);
    if (!pick || access(P(pick, REC_PATH), F_OK)) {
        pod_toast(TR("Storage unavailable"));
        return;
    }
    queue = _create_deque("stSongInfo");
    if (!queue) return;
    deque_init(queue);
    found = loadSongList(queue, P(pick, REC_NAME), I(pick, REC_CUE_START), cls);
    n = deque_size(queue);
    if (found >= 0 && n) { /* a duplicate file name resolves to its first copy: the drawn row wins */
        if (at < n && !strcmp(P(deque_at(queue, at), REC_PATH), P(pick, REC_PATH))) idx = at;
        else if ((unsigned)found < n) idx = (unsigned)found;
        if (shuffle) pod_set_mode(MODE_SHUFFLE);
        ah_open_player(queue, (int)idx, cls);
    }
    deque_destroy(queue);
}

static int ah_on_shuffle(void *ctx, void *e) { (void)ctx; (void)e; ah_play(1); return RET_OK; }
static int ah_on_play(void *ctx, void *e) { (void)ctx; (void)e; ah_play(0); return RET_OK; }

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

/* The cover tint and the cover's corners. The cover is square (AWTK cannot clip an image): its four AH_CORNER px corners are
 * painted over in the colour the window has behind them, anti-aliased (pod_corners, the table Now Playing's corners use), from the
 * cover widget's own EVT_AFTER_PAINT, so they are exact on black and on a tint. The window colour is black until the page shows
 * a real cover (the image property of img_albumcover_m is a file:// url: the cover thread has rendered /tmp/abp/<md5>1.jpg, the
 * stock refresh timer 0x5261d8 set it); then a page timer decodes the file, box-averages it (cc_decode, as Now Playing's tint
 * does) and sets the window's bg_color to pod_tone of that, under the static gradient image of the asset (ah_tint). The
 * placeholder disc, the All albums card and a page without a window stay black. One page at a time (ah.win); the timer and the
 * state go with the window's EVT_DESTROY. The header may be built again (to-foreground): the state is kept for the same window. */
static struct {
    void *win;                                  /* the page window the state belongs to, 0 none */
    unsigned timer;                             /* the polling timer, 0 none (never started, or the tint is done) */
    unsigned color;                             /* the window's bg_color as 0x00BBGGRR: black until tinted */
    int tinted;
    int fg;                                     /* 1 from the page's start and EVT_WINDOW_TO_FOREGROUND, 0 after EVT_WINDOW_TO_BACKGROUND */
    int barok;                                  /* 1: both window events are registered, so the status bar may be tinted (else never) */
    int bar;                                    /* 1: the status bar's bg_color is ours and must go back to black */
    unsigned key;                              /* the album's cache key (cc_album_key of its names), 0 none */
    unsigned char corner[AH_CORNER * AH_CORNER];
} ah __attribute__((section(".scratch")));

/* The status bar takes the page's top-edge colour (the tone under the gradient's first row, darkened for the white glyphs,
 * pod_bar_color) while a TINTED page is in front and its window events are registered; black pages never tint it. The stock
 * black comes back on every way out: background, destroy, a replaced page. Only the owner restores (pod_bar_black), so Now
 * Playing taking the bar over (Play all) is never undone by this page's late events. */
static void ah_bar_apply(void) {
    if (ah.barok && ah.fg && ah.tinted &&
        pod_bar_tint(ah.win, pod_shade(ah.color, 0, AH_TINT_A_TOP, AH_TINT_A_BOT, AH_TINT_ROWS)))
        ah.bar = 1;   /* a failed call keeps what the bar has (and owes) */
}

__attribute__((noinline)) static void ah_bar_black(void) {
    if (!ah.bar) return;
    ah.bar = 0;
    pod_bar_black(ah.win);
}

static int ah_on_background(void *ctx, void *e) {
    (void)e;
    if (!ah.win || ctx != ah.win) return RET_OK;
    ah.fg = 0;
    ah_bar_black();
    return RET_OK;
}

static int ah_on_foreground(void *ctx, void *e) {
    (void)e;
    if (!ah.win || ctx != ah.win) return RET_OK;
    ah.fg = 1;
    ah_bar_apply();
    return RET_OK;
}

static void ah_set_color(unsigned color) {
    unsigned v[4]; /* value_t: type at 0, the uint32 at 8 */
    memset(v, 0, sizeof v);
    value_set_uint32(v, color);
    if (widget_set_style(ah.win, "normal:bg_color", v) != RET_OK) return;
    ah.color = color & 0xffffff;
    ah.tinted = 1;
    widget_invalidate_force(ah.win, (void *)0);
    ah_bar_apply();
}

/* The cover widget's EVT_AFTER_PAINT: row 0 of the cover is window row AH_NAV_H + AH_ART_Y less how far the list is scrolled. */
static int ah_on_art_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    void *item = ctx ? P(ctx, W_PARENT) : (void *)0, *sv = item ? P(item, W_PARENT) : (void *)0;
    int row0 = AH_NAV_H + AH_ART_Y - (sv ? widget_get_prop_int(sv, "yoffset", 0) : 0);
    if (!canvas) return RET_OK;
    pod_corners(canvas, ah.corner, AH_CORNER, AH_ART, ah.color, row0, AH_TINT_A_TOP, AH_TINT_A_BOT, AH_TINT_ROWS);
    return RET_OK;
}

static void ah_stop(void) {
    ah_bar_black();
    if (ah.timer) timer_remove(ah.timer);
    memset(&ah, 0, sizeof ah);
}

static int ah_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx != ah.win) return RET_OK; /* an earlier page's end: the new one keeps its state */
    ah_stop();
    return RET_OK;
}

/* The tone of a decoded average colour (0x00BBGGRR bytes), set on the page and remembered for the album. */
static void ah_tone(unsigned px) {
    unsigned tone = pod_tone(px & 255, px >> 8 & 255, px >> 16 & 255);
    ah_set_color(tone);
    pod_tone_put(ah.key, tone);
}

/* The tint at once, without waiting for the cover thread: the album's tone from the tone cache (RAM), else from Cover Flow's cache
 * file of the album (one 168 px decode), whose empty "no art" marker leaves the page black. 1: decided (tinted, or black for
 * good); 0: nothing known, the page polls for the stock cover file. The album is named as the stock header names it (classinfo's
 * title and artist), which is what the album rows' key is made of. */
static int ah_cached(void) {
    const char *ci = (const char *)CLASSINFO, *album = ci + CLASSINFO_ALBUM;
    const char *artist = ci + (*(int *)G_CLASS_TYPE == CLASS_14 ? CLASSINFO_ARTIST_14 : CLASSINFO_ARTIST);
    char path[80], url[80];
    unsigned tone, px;
    long size;
    ah.key = *album ? cc_key_of(artist, album) : 0;
    if (!ah.key) return 0;
    if (pod_tone_get(ah.key, &tone)) {
        ah_set_color(tone);
        return ah.tinted;
    }
    size = cc_file_size(cc_path(path, sizeof path, ah.key, ""));
    if (size == 0) return 1;   /* the "no art" marker */
    if (size > 0 && cc_url(url, ah.key) && cc_decode(ah.win, url, 1, 1, 1, &px)) {
        ah_tone(px);
        return ah.tinted;
    }
    return 0;
}

/* The tint, once the cover is a real file: the page's cover widget is looked up by name (a rebuilt header made a new one). */
static void ah_work(void) {
    void *art = widget_lookup(ah.win, "img_albumcover_m", 1);
    const char *url = art ? widget_get_prop_str(art, "image", "") : "";
    unsigned px;
    const char *scheme = "file://";
    unsigned i;
    for (i = 0; i < 7; ++i)
        if (url[i] != scheme[i]) return;   /* the placeholder disc ("albumcover_info"): nothing to tint from */
    if (access(url + 7, F_OK) != 0) return;
    if (cc_decode(ah.win, url, 1, 1, 1, &px)) ah_tone(px); /* the corners follow from their next paint */
}

static int ah_tick(const void *timer) {
    (void)timer;
    if (!ah.win || ah.tinted) { /* gone, or done: the timer ends */
        ah.timer = 0;
        return RET_OK;
    }
    ah_work();
    if (ah.tinted) { ah.timer = 0; return RET_OK; }
    return RET_REPEAT;
}

/* The header was (re)built: the corners are ours, and a real cover will tint the page. */
static void ah_tint_start(void *item, void *art) {
    void *win = widget_get_window(item);
    if (ah.win && ah.win != win) ah_stop();
    if (!ah.corner[0]) pod_corner_fill(ah.corner, AH_CORNER);   /* the corners are ours in any case: black without a tint */
    widget_on(art, EVT_AFTER_PAINT, ah_on_art_paint, art);
    if (!win) return;
    if (!ah.win) {
        ah.win = win;
        if (!widget_on(win, EVT_DESTROY, ah_on_destroy, win)) { ah.win = 0; return; }
        ah.fg = 1;
        ah.barok = widget_on(win, EVT_WINDOW_TO_BG, ah_on_background, win) && widget_on(win, EVT_WINDOW_TO_FG, ah_on_foreground, win);
    }
    if (*(unsigned char *)(CLASSINFO + CLASSINFO_ALL_SONGS) || ah.tinted || ah.timer) return; /* the card stays black */
    if (ah_cached()) return;
    ah.timer = timer_add(ah_tick, (void *)0, AH_TICK_MS);
    if (ah.timer) ah_work();
}

/* The pill's glyph and text, centred as a pair for the page's language. The style (tools/mod_ipodrows.py) puts the glyph
 * left and the text left aligned beside it, AH_PILL_GAP px from the glyph; the pair's width is the glyph, the gap and
 * the text, which is measured here (widget_measure_text: the pill's own font, the translated text), so margin_left
 * is half what is left over, less the glyph's padding in its square. Set on the widget for every state (an inline
 * style, as Now Playing sets its colour). If the text cannot be measured the style's margin (English) stays. */
static void ah_centre_pill(void *play) {
    static const char *const key[5] = {"normal:margin_left", "pressed:margin_left", "over:margin_left",
                                       "focused:margin_left", "disable:margin_left"};
    const unsigned *text = widget_get_text(play);
    float w = text && *text ? widget_measure_text(play, text) : 0.0f;
    int tw = (int)(w + 0.999f), margin, i;
    unsigned v[4]; /* value_t: type at 0, the uint32 at 8 */
    if (tw <= 0) return;
    margin = (AH_PLAY_W - (AH_PILL_GLYPH + AH_PILL_GAP + tw)) / 2 - (AH_BTN_H - AH_PILL_GLYPH) / 2;
    if (margin < 0) return;
    memset(v, 0, sizeof v);
    value_set_uint32(v, (unsigned)margin);
    for (i = 0; i < 5; ++i) widget_set_style(play, key[i], v);
}

/* The header, after stock built it. item is the list_item holding the four widgets in stock's
 * order. The six new widgets (year line, Shuffle, four corner masks) are made first: if any fails,
 * the others are destroyed and nothing is moved. */
__attribute__((noinline)) static void ah_restyle(void *item) {
    void *art, *title, *artist, *play, *meta, *shuf, *nw[2];
    void *list = *(void **)PDEQ_SHOWLIST;
    char line[64];
    int i, ok = 1;
    if (!item || access(KILL_SD, F_OK) == 0 || widget_count_children(item) != 4) return;
    art = widget_get_child(item, 0), title = widget_get_child(item, 1);
    artist = widget_get_child(item, 2), play = widget_get_child(item, 3);
    if (!pod_is_type(art, "image") || !pod_is_type(title, "hscroll_label") || !pod_is_type(artist, "hscroll_label") ||
        !pod_is_type(play, "button"))
        return;
    meta = nw[0] = hscroll_label_create(item, AH_TEXT_X, AH_META_Y, AH_TEXT_W, AH_META_H);
    shuf = nw[1] = button_create(item, AH_SHUF_X, AH_BTN_Y, AH_SHUF_W, AH_BTN_H);
    for (i = 0; i < 2; ++i) ok &= nw[i] != (void *)0;
    if (!ok) {
        for (i = 0; i < 2; ++i)
            if (nw[i]) widget_destroy(nw[i]);
        return;
    }
    widget_use_style(meta, "srlabel_ahmeta_style");
    hscroll_label_set_ellipses(meta, 1);
    widget_set_sensitive(meta, 0); /* decoration: a drag that starts on it scrolls the list */
    ah_meta(line, sizeof line, list ? (int)deque_size(list) : 0);
    widget_set_text_utf8(meta, line);
    widget_use_style(play, "btn_ahplay_style");
    widget_set_tr_text(play, "Play all");
    ah_centre_pill(play);
    /* the stock handler stays on the page; ours replaces it (the same sequence, then Now Playing) */
    widget_off_by_func(play, EVT_CLICK, (void *)AH_STOCK_PLAY, item);
    widget_on(play, EVT_CLICK, ah_on_play, (void *)0);
    widget_move(play, AH_PLAY_X, AH_BTN_Y);
    widget_resize(play, AH_PLAY_W, AH_BTN_H);
    widget_use_style(shuf, "btn_ahshuf_style"); /* the glyph and its disc are the style's images: no text */
    widget_on(shuf, EVT_CLICK, ah_on_shuffle, (void *)0);
    widget_move(art, AH_ART_X, AH_ART_Y);
    widget_resize(art, AH_ART, AH_ART);
    image_set_draw_type(art, IMAGE_DRAW_CENTER); /* never scaled: the 160 px file, or the 160 px default disc, 1:1 */
    widget_use_style(title, "srlabel_ahtitle_style");
    widget_move(title, AH_TEXT_X, AH_TITLE_Y);
    widget_resize(title, AH_TEXT_W, AH_TITLE_H);
    widget_use_style(artist, "srlabel_ahartist_style");
    widget_move(artist, AH_TEXT_X, AH_ARTIST_Y);
    widget_resize(artist, AH_TEXT_W, AH_ARTIST_H);
    widget_use_style(item, "list_item_ahhead_style"); /* transparent: the window's colour and the tint gradient show through */
    widget_resize(item, widget_get_prop_int(item, "w", 0), AH_HDR_H);
    ah_tint_start(item, art);
}

/* The hook (tools/pod.py ALBUMINFO_HEADER): stock first, then ours. */
void m1pod_albuminfo_header(void *item) {
    stock_albuminfo_header_trampoline(item);
    ah_restyle(item);
}
