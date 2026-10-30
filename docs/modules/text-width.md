# The text-width model

**Sources:** `tools/awtk_text.py`.

`demo` links AWTK statically with its stb_truetype backend (`font_stb_create_ex` `0x67ee74`); there is
no FreeType. The lcd is `lcd_mem` with no text functions, so `canvas_draw_text` (`0x645348`) draws
glyph by glyph and steps `x += advance + 1` (`0x6454cc..0x6454d8`), and `canvas_measure_text`
(`0x644544`) adds `advance + 1` too (`0x6446c4`; a glyph the font cannot give adds 4). The scale is
`font_size / (hhea ascender - descender)` in float32 (`stbtt_ScaleForPixelHeight` `0x67cb9c`), each
advance truncated (`trunc.w.s` at `0x680438` into `glyph_t.advance`), the bitmap drawn at `pen + x0`
with `x0 = floor(xMin * scale)`, `x1 = ceil(xMax * scale)`. For the stock font (256 units/em, ascender
230, descender -69: 299) `font_size` 18 draws an em at 15.4 px. `hscroll_label` paint reads
`margin_left`/`margin_right` (default 2) and clips to the box inset by them (`0x609dac`, `0x609dcc`).
`Ttf` reads a TrueType file; `StbText(ttf, px).layout(text)` returns the pen of each glyph and the
width AWTK measures; `awtk_width`, `fit_size` and `worst_case_text` (widest digit, weekday and month
names) size the lock clock and date; `tools/stb_raster.py` rasterises the same way for the previews.
Also: no hinting, no kerning, no OpenType features, no fallback (one font file covers every script),
`glyf` outlines only, composite glyphs only with plain offsets (stb mis-scales scaled components),
cmap format 4 looked up by a binary search that trusts `searchRange`/`entrySelector`/`rangeShift`
(`mod_boot.stb_lookup` is a line-for-line port, used by the font checks).
