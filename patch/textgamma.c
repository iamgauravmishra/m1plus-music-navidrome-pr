/* Text coverage gamma (docs/modules/fonts.md "Coverage gamma"; G and the table TEXT_GAMMA_LUT are tools/textgamma.py's).
 * AWTK's stb_truetype backend blends each glyph's 8-bit coverage straight into sRGB, so light text on black reads thin.
 * tg_apply swaps the default font object's get_glyph slot (+0x24, read on every font_get_glyph call) for tg_get_glyph.
 * The wrapper looks the glyph up in the font's cache first: a hit returns stock's copy untouched, because its mask was
 * mapped when it was rasterized. A miss calls stock, which rasterizes and caches the glyph; the mask that comes back
 * (the cache entry shares it) is mapped in place, once. Mono fonts are not wrapped.
 *
 * No hook: patch/fontregion.c calls tg_apply from its apply (fr_boot in the boot guard's ready path, and the one-shot
 * timer after a language or theme change, which recreates the font object with the stock slot). A mismatch (the slot is
 * neither stock's nor ours, the font is mono, not an stb font, no font manager) or the kill switch leaves the stock slot.
 * The kill switch is read at each apply, so a file made during a session takes effect at the next apply. */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "textgamma.h"

static const unsigned char tg_lut[256] = TEXT_GAMMA_LUT;

static unsigned tg_u16(const unsigned char *p) { return (unsigned)p[0] | (unsigned)p[1] << 8; }

int tg_get_glyph(unsigned char *f, unsigned ch, unsigned size, unsigned char *out) {
    unsigned char *data;
    unsigned i, n;
    int rc;
    if (!glyph_cache_lookup(f + FONT_CACHE, ch, size, out)) return 0; /* a hit: mapped when it was rasterized */
    rc = ((int (*)(void *, unsigned, unsigned, void *))STB_GET_GLYPH)(f, ch, size, out);
    if (rc || f[FONT_MONO] || out[GLYPH_FORMAT]) return rc;
    data = (unsigned char *)(unsigned long)(tg_u16(out + GLYPH_DATA) | tg_u16(out + GLYPH_DATA + 2) << 16);
    if (!data) return rc;
    n = tg_u16(out + GLYPH_W) * tg_u16(out + GLYPH_H);
    for (i = 0; i < n; i++) data[i] = tg_lut[data[i]];
    return rc;
}

/* Whether the font's slot is stock's or ours: the caller may then run its own checks on the font. */
int tg_stb_slot(const unsigned char *f) {
    unsigned s = *(const unsigned *)(f + FONT_GET_GLYPH);
    return s == STB_GET_GLYPH || s == (unsigned)(unsigned long)tg_get_glyph;
}

/* Installs (or, with the kill switch, restores) the wrapper on the default font f. Only the slot changes: the glyph
 * cache is emptied then, so glyphs rasterized before are drawn again. Any mismatch leaves the font alone. */
void tg_apply(void *fm, unsigned char *f) {
    unsigned *slot, want;
    void *wm;
    if (!fm || !f || *(unsigned *)(f + FONT_MATCH) != STB_MATCH || f[FONT_MONO] || !tg_stb_slot(f)) return;
    slot = (unsigned *)(f + FONT_GET_GLYPH);
    want = home_off() ? STB_GET_GLYPH : (unsigned)(unsigned long)tg_get_glyph;
    if (*slot == want) return;
    *slot = want;
    font_manager_shrink_cache(fm, 0); /* the cached glyphs are the old (un)mapped masks */
    wm = window_manager();
    if (wm) widget_invalidate_force(wm, (void *)0);
}
