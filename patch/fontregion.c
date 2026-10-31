/* Regional CJK forms (docs/modules/fonts.md "Regional forms"). default.ttf carries, besides the Unicode cmap
 * stb_truetype picks at font creation (3, 1), Mac-platform format-4 subtables it never picks (tools/mod_font.py
 * REGIONS): the same map with Source Han Sans's Japanese, Traditional Chinese (Taiwan) or Simplified Chinese
 * glyphs where they differ, and the full-width dash and centred ellipsis. stbtt_FindGlyphIndex reads the font's
 * index_map on every lookup, so pointing it at a subtable and emptying the glyph cache switches the forms:
 * ja -> JP, zh_HK / zh_TW -> TC, other zh -> SC, every other language (and the kill switch) the default map.
 *
 * No hook: fr_boot runs once in the boot guard's ready path (patch/home.c home_boot), and a language or theme change
 * (both recreate the font object: the window manager's locale handler and widget_set_theme call
 * font_manager_unload_all) schedules one 1-shot timer that applies it again. Any mismatch (not an stb font, no
 * cmap, no such subtable) leaves the font as it is. */
#include "offsets.inc"
#include "stock.h"
#include "home.h"

#define FR_DELAY_MS 10
enum { FR_DEFAULT = 0, FR_JP = 1, FR_TC = 2, FR_SC = 25 }; /* the subtables' Mac encoding IDs (mod_font.REGIONS) */

static struct {
    int pending; /* a change timer is scheduled */
    int bound; /* the change handlers are registered */
} fr __attribute__((section(".scratch")));

static unsigned fr_u16(const unsigned char *p) { return (unsigned)p[0] << 8 | p[1]; }
static unsigned fr_u32(const unsigned char *p) { return fr_u16(p) << 16 | fr_u16(p + 2); }
static int fr_is(const char *s, char a, char b) { return s[0] == a && s[1] == b && !s[2]; }

/* The subtable for the UI language, by its encoding ID. */
static int fr_region(void) {
    const char *l = locale_info();
    if (!l || home_off()) return FR_DEFAULT;
    if (fr_is(l + LOCALE_LANGUAGE, 'j', 'a')) return FR_JP;
    if (!fr_is(l + LOCALE_LANGUAGE, 'z', 'h')) return FR_DEFAULT;
    return fr_is(l + LOCALE_COUNTRY, 'H', 'K') || fr_is(l + LOCALE_COUNTRY, 'T', 'W') ? FR_TC : FR_SC;
}

/* The offset from data of the format-4 subtable of the record (3, 1) (FR_DEFAULT) or (1, enc); 0 if absent. */
static unsigned fr_subtable(const unsigned char *data, unsigned start, int enc) {
    const unsigned char *d = data + start, *r;
    unsigned n = fr_u16(d + 4), cmap = 0, i, pid = enc ? 1 : 3, eid = enc ? (unsigned)enc : 1;
    if (n > 64) return 0;
    for (i = 0; i < n; i++)
        if (fr_u32(d + 12 + 16 * i) == 0x636d6170u) cmap = fr_u32(d + 12 + 16 * i + 8); /* 'cmap' */
    if (!cmap) return 0;
    n = fr_u16(data + cmap + 2);
    if (n > 16) return 0;
    for (i = 0; i < n; i++) {
        r = data + cmap + 4 + 8 * i;
        if (fr_u16(r) == pid && fr_u16(r + 2) == eid) {
            unsigned off = cmap + fr_u32(r + 4);
            return fr_u16(data + off) == 4 ? off : 0;
        }
    }
    return 0;
}

static void fr_apply(void) {
    void *fm = font_manager(), *wm;
    unsigned char *f, *data;
    unsigned off;
    if (!fm) return;
    f = font_manager_get_font(fm, "default", 0); /* creates it if no text was drawn yet */
    if (!f || *(unsigned *)(f + FONT_MATCH) != STB_MATCH || *(unsigned *)(f + FONT_GET_GLYPH) != STB_GET_GLYPH) return;
    data = *(unsigned char **)(f + FONT_DATA);
    if (!data) return;
    off = fr_subtable(data, *(unsigned *)(f + FONT_START), fr_region());
    if (!off || *(unsigned *)(f + FONT_INDEX_MAP) == off) return;
    *(unsigned *)(f + FONT_INDEX_MAP) = off;
    font_manager_shrink_cache(fm, 0); /* the cached glyphs are the old forms */
    wm = window_manager();
    if (wm) widget_invalidate_force(wm, (void *)0);
}

static int fr_tick(const void *unused) {
    (void)unused;
    fr.pending = 0;
    fr_apply();
    return RET_OK;
}

/* A language or theme change: the font object is being replaced (the locale handlers run newest first, before the
 * window manager's unload), so the new one is set on the next tick. */
static int fr_changed(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (!fr.pending && timer_add(fr_tick, (void *)0, FR_DELAY_MS)) fr.pending = 1;
    return RET_OK;
}

/* Every Home init (a re-created Home applies it again); the change handlers are registered once a session. */
void fr_boot(void) {
    void *wm = window_manager();
    fr_apply();
    if (fr.bound) return;
    fr.bound = 1;
    locale_info_on(locale_info(), EVT_LOCALE_CHANGED, fr_changed, (void *)0);
    if (wm) widget_on(wm, EVT_THEME_CHANGED, fr_changed, (void *)0);
}
