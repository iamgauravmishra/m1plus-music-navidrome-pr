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
  Microsoft YaHei / Arial text it replaced (and of Source Han Sans Regular next to it for CJK), with the same em, tabular digits and
  tracking. It is a replacement, not a second font: the merged `default.ttf` is about 1.4 KB smaller than with Regular and the rootfs
  stays at the stock size. Medium is slightly wider: every fit test (`test/pod/i18n.py` and the rest) passes with no overflow in
  the 13 languages (tightest: the Cover Flow progress line in fr_FR, it_IT and po_PL, 299 of 300 px; the ru_RU Sort value
  "Исполнитель", 105 of 106 px). Stock navbar titles (a 200 px `label_title` that clips, 20 px; Songs, Playlists, Folders, Composers,
  Genres, Artists, Albums, System Settings, Playback) were measured in all 16 tables against Regular: the only one that clips in Medium and
  not in Regular is the uk_UK "System Settings" (`Системні налаштування`, 202 px against 198 px of 200). It is a stock label, left as it is.
  1,429 code points (822 replace stock mappings, 607 are new: Vietnamese, EUR, Latin Ext-B).
- **CJK, kana, Hangul: Source Han Sans SC Regular 2.005R** for every stock code point in CJK Unified,
  Ext A, Hiragana, Katakana (+ phonetic ext) and Hangul syllables (38,868): the CFF outline scaled 0.256,
  shifted down 7 units (so the ideographs' ink centre 90.5 matches Inter's capitals 91.5 and stock rows
  keep their position), converted to quadratics (`cu2qu`, max error 1 unit), advance `round(adv *
  0.256)` (Hangul becomes proportional, ~8 % narrower). CJK punctuation, fullwidth forms, Thai, Arabic,
  symbols and arrows keep the stock glyphs. The SHS zip (95 MB, SHA-256 pinned) is fetched into `fonts/`
  by `tools/mod_font.py --fetch` and read in memory, never committed (it would be a Modified Version
  that cannot keep the reserved name "Source"); the merged font keeps the stock name table and appends
  the Inter and SHS copyright lines and the OFL.
- Merge: tree font must be the stock SHA-256; CJK glyphs written over the stock glyph by cmap name; Inter
  glyphs added; a fontTools subset pass drops the replaced Latin/Greek/Cyrillic glyphs, hinting (`fpgm`,
  `prep`, `cvt `, glyph programs), `gasp`, `DSIG` and glyph names (`post` 3.0); stock `head` dates. Checks
  (`mod_font.verify`): metrics stock; all 42,853 stock code points still map and every one with ink in
  stock has ink (no tofu); 3,163 others keep their exact stock outline and advance. Result 43,460 code
  points, 9,927,468 bytes (Regular: 9,928,864); the rebuilt rootfs stays within the stock size (fwtool checks).
- **Pull-down volume.** The pull-down's status bar is laid out like the real one (`tools/statusbar.py`, section 4), where
  `100` at 16 px fits the stock 30 px label; the font step does nothing for it.
- Not fixed on purpose: CJK ellipsis/dashes become Inter's, the colon is not raised between digits
  (no contextual alternates in AWTK), combining marks are drawn without positioning (47 absent from
  Inter keep the stock glyph).
