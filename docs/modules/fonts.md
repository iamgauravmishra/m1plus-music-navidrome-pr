# Font

**Sources:** `tools/mod_font.py`, `tools/font_inter.py`.

One file, `release/assets/default/raw/fonts/default.ttf` ("微软雅黑+Arial", 256 units/em, 9.4 MB),
rewritten by code point; unitsPerEm, hhea ascender/descender/lineGap and OS/2 stay, so every layout
sized from them still adds up. The step runs first so every later step measures the new font.

- **Latin, Greek, Cyrillic: Inter 4.1 Medium** (`assets/fonts/Inter-m1plus.ttf`, the committed subset,
  155,888 bytes, 1,428 simple glyphs, `INTER_WEIGHT` in `mod_font.py`; `font_inter.py INTER_ZIP` regenerates it byte-identically with
  fontTools 4.67.0; OFL in `assets/fonts/`), outlines at 252 stock units per Inter em (cap height 183
  = Arial's), tabular digits baked into the cmap (`0-9` -> `zero.tf..nine.tf`, 163 units, 155 after
  tracking), composites decomposed. **Tracking 8**: every Inter advance loses 8 units and each outline
  moves left 4, because Inter as designed sets English 3-9 % wider than Arial once demo's +1 px per
  glyph is added; k = 8 makes the mean ratio over 16/18/21 px 0.999 (0.989 / 0.984 / 1.023) for Regular. **Why Medium (V2.1nG):** on
  the 320 x 480 panel at 16 to 21 px Regular's stems read thin against the black pages; Medium has the weight of the stock
  Microsoft YaHei / Arial text it replaced (and of the Source Han Sans Medium next to it for CJK), with the same em, tabular digits and
  tracking. It is a replacement, not a second font: the merged `default.ttf` is about 1.4 KB smaller than with Regular and the rootfs
  stays at the stock size. Medium is slightly wider: every fit test (`test/pod/i18n.py` and the rest) passes with no overflow in
  the 13 languages (tightest: the Cover Flow progress line in fr_FR, it_IT and po_PL, 299 of 300 px; the ru_RU Sort value
  "Исполнитель", 105 of 106 px). Stock navbar titles (a 200 px `label_title` that clips, 20 px; Songs, Playlists, Folders, Composers,
  Genres, Artists, Albums, System Settings, Playback) were measured in all 16 tables against Regular: the only one that clips in Medium and
  not in Regular is the uk_UK "System Settings" (`Системні налаштування`, 202 px against 198 px of 200). It is a stock label, left as it is.
  1,429 code points (822 replace stock mappings, 607 are new: Vietnamese, EUR, Latin Ext-B).
- **CJK, kana, Hangul: Source Han Sans SC Medium 2.005R** (`SHS_WEIGHT`) for every stock code point in CJK Unified,
  Ext A, Hiragana, Katakana (+ phonetic ext) and Hangul syllables (38,868), plus
  CJK punctuation, fullwidth and halfwidth forms, Bopomofo, compatibility jamo, radicals, strokes, Kanbun,
  vertical and small forms, enclosed and squared CJK (1,069 more, 39,937 in all), so `，。：！？（）「」《》` in
  Chinese text are drawn like the ideographs (SC placement: comma and full stop low left, the colon left of
  centre) instead of Microsoft YaHei's; SHS has every one, at the stock advance except compatibility jamo
  (236, like the syllables). Conjoining jamo and halfwidth Hangul stay stock (SHS widths differ). The CFF outline scaled 0.256,
  shifted down 7 units (so the ideographs' ink centre 90.5 matches Inter's capitals 91.5 and stock rows
  keep their position), converted to quadratics (`cu2qu`, max error 1 unit), advance `round(adv *
  0.256)` (Hangul becomes proportional, ~8 % narrower). Thai, Arabic, symbols and arrows keep the stock glyphs.
  **Why Medium:** Regular's stems read thin at 16 to 22 px on the unhinted panel, and Medium matches the Inter
  Medium beside it (picked from a device-rasterized sheet of Regular and Medium). Two other routes were tried: the static SHS weights are not
  point-compatible (about 60 % of sampled ideographs differ in point count), so no in-between instance; and
  Regular widened 6 of 256 units (FreeType-style emboldening) fills in dense ideographs (鬱, 齉) where Medium
  stays open. Source: the 2.005R TTC zip `01_SourceHanSans.ttc.zip` (96 MB, zip and TTC SHA-256 pinned; faces
  `SHS_FACES`, name-checked: Medium JP 25, SC 27, TC 28), fetched into `fonts/`
  by `tools/mod_font.py --fetch` and read in memory, never committed (it would be a Modified Version
  that cannot keep the reserved name "Source"); the merged font keeps the stock name table and appends
  the Inter and SHS copyright lines and the OFL.
- Merge: tree font must be the stock SHA-256; CJK glyphs written over the stock glyph by cmap name; Inter
  glyphs added; a fontTools subset pass drops the replaced Latin/Greek/Cyrillic glyphs, hinting (`fpgm`,
  `prep`, `cvt `, glyph programs), `gasp`, `DSIG` and glyph names (`post` 3.0); stock `head` dates. Checks
  (`mod_font.verify`): metrics stock; all 42,853 stock code points still map and every one with ink in
  stock has ink (no tofu); 2,094 others keep their exact stock outline and advance. Result 43,460 code
  points, 11,188,620 bytes (9,895,732 without the regional forms); rootfs.squashfs 54,755,328 bytes, 983,040 under the
  stock size fwtool enforces (the regional forms cost 823,296).
- **Regional forms.** One file cannot hold three fonts (a second 10 MB face would not fit the rootfs), so default.ttf
  carries the SC forms in its Unicode cmap (3, 1), which stb_truetype picks, and three more format-4 subtables on the
  Mac platform, which it never picks (`stbtt_InitFont` takes the last record of platform 0 or 3/1, 3/10): (1, 25) SC,
  (1, 1) JP, (1, 2) TC, each the default map with that region's Source Han Sans glyph wherever it differs from SC
  (`mod_font.REGIONS`). In the TTC the regions of a weight share one CFF, so a differing glyph is a different glyph
  name and a glyph two regions share is added once (`shs.<cid>`). Ideographs only within the region's common set
  (the rootfs headroom: all 16,247 differing glyphs would not fit): JP the JIS X 0208 level-1 kanji (Shift-JIS
  `889F..9872`, 1,770 that differ), TC the Big5 frequent hanzi (`A440..C67E`, 2,577); every differing non-ideograph
  (TC centres `，。！？：；`, JP its `！？：；`, radicals, enclosed forms). Every regional map also gives `—` U+2014
  SHS's full-width dash (its `fwid` form) with the ink stretched 12 units past both edges (demo's +1 px per glyph
  and truncated advance would otherwise leave a 1 px gap in `——`) and `…` U+2026 SHS's centred full-width
  ellipsis, so `——` and `……` run on in Chinese and Japanese UIs; the default map keeps Inter's for English
  and the other Latin UIs. Curly quotes stay Inter's in every map: English titles in a Chinese UI use `’` as the
  apostrophe, and a full-width one would split `Don’t`. 4,353 glyphs added (JP 1,897 code points, TC 2,618, SC 2).
  `verify` checks each regional map through stb's lookup: the default map's code points, its glyph everywhere except
  the region's, inked glyphs there. At run time `patch/fontregion.c` points the live font's `index_map`
  (`stbtt_fontinfo` +0x2c, font object +0x64, read on every glyph lookup; addresses.md "Fonts and locale") at the
  subtable of the UI language (`ja` JP; `zh` + `HK`/`TW` TC; other `zh` SC; anything else, or the kill switch, the
  default map), then empties the glyph cache (`font_manager_shrink_cache(fm, 0)`) and repaints, only when it
  changes: from the boot guard's ready path (`fr_boot`, before the first frame) and from one 10 ms timer after
  `EVT_LOCALE_CHANGED` or `EVT_THEME_CHANGED` (both recreate the font; registered once a session). No hook. The
  language picks the forms, not the text: a Japanese title in a Chinese UI is drawn with SC forms (a per-text choice
  would need code at paint). `tools/preview_cjk.py STOCK_WORKDIR` draws the four maps side by side
  (`out/peek/cjk_regions.png`).
- **Pull-down volume.** The pull-down's status bar is laid out like the real one (`tools/statusbar.py`, section 4), where
  `100` at 16 px fits the stock 30 px label; the font step does nothing for it.
- Not fixed on purpose: Latin UIs draw CJK ellipsis/dashes with Inter's, the colon is not raised between digits
  (no contextual alternates in AWTK), combining marks are drawn without positioning (47 absent from
  Inter keep the stock glyph).
