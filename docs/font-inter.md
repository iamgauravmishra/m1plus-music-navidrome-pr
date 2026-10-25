# UI font: Inter + Source Han Sans SC (`font-inter`, `look-all-inter`, V2.1fI)

One asset changes: `release/assets/default/raw/fonts/default.ttf`, the only font the UI uses.
Latin, Greek and Cyrillic come from **Inter 4.1 Regular**, CJK ideographs, kana and Hangul from
**Source Han Sans SC Regular 2.005R**. Everything else in the stock font (symbols, arrows, CJK
punctuation, fullwidth forms, Thai, Arabic, Hebrew, ...) and its vertical metrics stay as they are.
No code changes. `look-all-inter` = the font step first, then the four looks of `look-all`
(theme -> lists -> nowplaying -> boot), on `pod-cover` (V2.1dE). The step also widens the volume label
of the pull-down's own status bar, which `100` overflows in Inter (below). `full` (V2.1gA,
`docs/full.md`) uses the same font step.

```
venv/bin/pip install -r requirements.txt            # fontTools 4.67.0 is now in it
python3 -I tools/mod_font.py --fetch                # Source Han Sans SC zip -> fonts/ (95 MB, SHA-256 checked)
python3 -I tools/build.py --variant look-all-inter
# -> out/M1Plus-V2.1fI-look-all-inter-pod-cover-lockscreen-iconpercent-space-update.bin
venv/bin/python -I tools/preview_font.py work/mod-look-all-... work/mod-look-all-inter-... docs/font-inter-preview.png
```

`tools/mod_font.py SRC OUT [--no-inter] [--no-cjk]` runs one half alone (`--no-cjk` needs no download).
With `--no-inter` the font keeps the stock em-wide curly quotes, and `mod_boot.py` then refuses the
non-stock font: run it with `--no-quotes`.

![font preview](font-inter-preview.png)

`docs/font-inter-preview.png`: V2.1fA (top) and V2.1fI (bottom) on System Settings with the status
bar, Songs, Now Playing (a Chinese title), the lock screen and a list of mixed-script titles, plus a
3x zoom. The panels come from the looks' preview painters, but every glyph is drawn by
`tools/stb_raster.py`, a pure-Python copy of what AWTK does with the font (below), at the
device sizes. The layout is approximate. The glyph pixels are what stb_truetype makes of each file.

## How this firmware draws text

`demo` links AWTK statically with its stb_truetype backend (`font_loader_stb`, `font_stb_create_ex`
at `0x67ee74`). There is no FreeType (`docs/look-boot.md`). What follows from that:

- **scale** = font_size / (hhea ascender - descender) (`stbtt_ScaleForPixelHeight`). The stock font
  has 230 - (-69) = 299 units, so `font_size` 18 draws an em of 256 units at 15.4 px. unitsPerEm is
  never read, so the merged font keeps 256 units/em, ascender 230, descender -69, lineGap 0, and
  every layout that was sized from these (lock clock, battery slot, Now Playing's prefix) still adds up
- **no hinting**: outlines are rasterized as they are (exact-area coverage, curves flattened to
  0.35 px). Glyph programs, `fpgm`, `prep`, `cvt ` and `gasp` do nothing here and were dropped
- **no kerning, no OpenType features**: the AWTK `font_t` built by `font_stb_create_ex` has five
  slots (font+0x20..0x30: match, vmetrics, glyph, shrink, destroy) and none for pair adjustment.
  `canvas_measure_text` sums per-glyph advances, each `trunc(advance * scale)`, **plus 1 px per
  glyph**: `addiu v0, v0, 1` on the glyph advance at 0x6446c8, and `canvas_draw_text` steps the pen
  the same way at 0x6454d4 (a glyph that fails to load advances 4 px). `tools/stb_raster.py` models both.
  This extra pixel is why a font with Arial-like advances reads wider here than it does elsewhere.
  So Inter's tabular figures have to be in the cmap itself. Its contextual and case alternates
  cannot be used
- **no fallback**: one file covers every script the UI can show. Hence one merged font, not
  "Inter Display" for the clock as a second file
- **cmap**: the last Unicode record (platform 0, or 3/1, 3/10) wins. Format 4 is looked up with a
  binary search that trusts `searchRange`/`entrySelector`/`rangeShift`. `mod_boot.stb_lookup` is a
  line-for-line port, and the checks below run every BMP code point through it. The merged font has
  one shared format-4 subtable for 0/3 and 3/1, like stock. The Mac Roman subtable stb never reads
  was dropped
- **outlines**: `glyf` only (stb_truetype needs TrueType outlines, not CFF). Composite glyphs work only
  with plain offsets: stb mis-scales scaled components (it multiplies the scale in twice) and asserts
  on point-matched ones. So the merged font has **no composite glyphs** (Inter's were decomposed,
  Source Han Sans is converted glyph by glyph)

`fonts/config/default*.txt` (three identical 10,827-byte glyph lists: ASCII, some CJK punctuation,
fullwidth forms, the GB2312 hanzi) are inputs for AWTK's bitmap-font generator. Nothing in `demo`
names them, and the device renders `default.ttf` directly, so they stay as they are.

## Sources (both SIL Open Font License 1.1)

| | Inter | Source Han Sans SC |
|---|---|---|
| release | 4.1 (2024-11-16) | 2.005R |
| URL | `https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip` | `https://github.com/adobe-fonts/source-han-sans/releases/download/2.005R/09_SourceHanSansSC.zip` |
| zip SHA-256 | `9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e` | `ef7364f7ac2564be1ae9c1d74276de2653fe38b73449070398c4fc0b7e032ff1` |
| file used | `extras/ttf/Inter-Regular.ttf` `40d692fc...0c82` | `OTF/SimplifiedChinese/SourceHanSansSC-Regular.otf` `f1d86111...7256` |
| in the repo | `assets/fonts/Inter-m1plus.ttf` (159,300 bytes, the derived subset) | nothing. The 95 MB zip is fetched into `fonts/` (gitignored) by `mod_font.py --fetch` and read in memory |
| licence | `assets/fonts/OFL-Inter.txt` (no Reserved Font Name) | `assets/fonts/OFL-SourceHanSans.txt` (Reserved Font Name "Source") |

Why the two are handled differently: the Inter subset is small, so it is committed and the build
never needs the 34 MB Inter zip. Source Han Sans as converted here would be a ~9 MB TrueType file
in git. It would also be a Modified Version that could not keep the reserved name "Source". So the
build converts it locally from the pinned upstream file, and the repo carries only the pins.
`tools/font_inter.py INTER_ZIP` regenerates the Inter subset (byte-identical with fontTools 4.67.0),
and `mod_font.py` pins its SHA-256.

The merged font keeps the stock name table ("微软雅黑+Arial"; it still contains Microsoft glyphs)
and appends the Inter and Source Han Sans copyright lines and the OFL to its copyright string
(nameID 0). It is not named "Source". It is built on your machine and never distributed by this repo.

## Weight and scale (Inter)

Measured with `tools/stb_raster.py` on white-on-black text at the sizes the UI uses (a survey of the
look-all tree: mostly 16, 18, 20, 21, 22 px inline and in styles, 26 and 40 on a few pages, 120-140 for
the lock clock). Inter's em is drawn at E stock units (the outlines scaled by E/2048):

| font | cap height | x-height | ink 16 / 18 / 21 px | stem peak 16 / 18 / 21 px |
|---|---|---|---|---|
| stock Arial | 183 | 133 | 391 / 498 / 686 | 0.85 / 0.82 / 0.86 |
| Inter Regular, E 248 | 180 | 135 | 380 / 481 / 654 | 0.86 / 0.78 / 0.89 |
| **Inter Regular, E 252** | **183** | **138** | **398 / 503 / 685** | **0.87 / 0.77 / 0.94** |
| Inter Regular, E 256 | 186 | 140 | 402 / 510 / 694 | 0.86 / 0.77 / 0.91 |
| Inter Medium, E 252 | 183 | 138 | 465 / 588 / 801 | 0.92 / 0.84 / 0.96 |

(ink: summed coverage of `lihnmudbpqHILETFkr`. Stem peak: the darkest column of each glyph as a
fraction of its height, 1.0 = a stem that lands on whole pixels.)

- **Regular, not Medium.** Regular at E 252 puts the same amount of ink on the screen as the stock
  Arial (within 1 %), and its stems come out as crisp as Arial's (stem peak 0.86 average over the
  three sizes, Arial 0.84). Medium is crisper (0.91), but it is 17 % darker. White-on-black text on
  this LCD already looks heavier than it is, and Medium would outweigh the Regular CJK next to it.
  The preview shows the difference most at 16 px
- **E = 252 (scale 252/2048 = 0.1230).** Inter's cap height then equals Arial's 183 units exactly, so
  capitals sit where the stock ones did next to the CJK. The x-height is 138 units against 133:
  Inter's larger lowercase, which helps legibility at 16 px. At E 256 (em for em) the caps would be
  2 % taller and the text 1.6 % wider. As designed, Inter still sets English 3-9 % wider than Arial
  here, hence the tracking below
- **tabular digits**: `0-9` map to Inter's `zero.tf ... nine.tf`, all 163 units (155 after tracking; stock 142).
  Clock, status bar time and play times no longer shift as digits change. The colon stays Inter's
  default (73 units). `colon.case`, which sits higher next to figures, would also apply to text colons
- **lock clock**: `mod_lockscreen.py` measures the font in the tree. With the font step first, `hh:mm`
  fits at **129 px** (296 of 320 px by its measure, which leaves out demo's +1 px per glyph; drawn
  301 px; 138 px with the stock font, 122 px with untracked Inter). The date and battery row follow.
  `ui/screensaver_page.bin` differs from V2.1eA only in these numbers

## Tracking (k = 8)

Inter as designed, after demo's +1 px per glyph, sets English UI text 3-9 % wider than the stock Arial.
The default font step therefore cuts **8 units (of 256 per em) from every Inter advance**
(`mod_font.INTER_TRACKING`, `--tracking K`; `--tracking 0` gives untracked Inter, byte-identical to
the first V2.1fI font `88695838...`). Each outline moves left 4 units, so both sidebearings lose about
4 units and the spacing stays balanced. That covers every Latin, Greek and Cyrillic glyph, spaces
included. Zero-width combining marks are left alone, and the digits lose the same 8, so they stay tabular.

Width against the stock font, with the +1 px, over 392 en_US UI strings and 65 typical
track/album/artist titles (ratio new/stock per string):

| Inter tracking | 16 px mean / max | 18 px mean / max | 21 px mean / max | mean of the three |
|---|---|---|---|---|
| 0 (as designed) | 1.055 / 1.152 | 1.028 / 1.111 | 1.086 / 1.200 | 1.056 |
| 4 | 1.030 / 1.125 | 1.013 / 1.111 | 1.076 / 1.200 | 1.040 |
| 6 | 1.001 / 1.125 | 0.990 / 1.111 | 1.044 / 1.200 | 1.012 |
| **8 (default)** | **0.989 / 1.125** | **0.984 / 1.111** | **1.023 / 1.103** | **0.999** |
| 10 | 0.989 / 1.125 | 0.971 / 1.111 | 1.009 / 1.100 | 0.990 |
| 12 | 0.975 / 1.125 | 0.946 / 1.111 | 0.994 / 1.100 | 0.972 |

The sizes differ because of the per-glyph truncation: at 21 px Inter's advances happen to round less
favourably than Arial's. k = 8 is the cut whose mean over 16/18/21 px matches Arial (0.999).
Ink is unchanged: tracking moves glyphs, it does not thin them.

The worst cases are short digit strings: `21`, `01:23`, `04:56` (+7 to +12 %, i.e. 2-4 px). Inter's
tabular figures are wider than Arial's narrow ones (155 vs 142 units). Cutting them further would
make `00` touch at 16 px, so they keep the same k. Time-zone names like `(GMT+10:00)Asia/...` are
the longest strings that grow by 4 px or more.

Nearest ink gap between neighbours at 16 px (px between the last inked column of the first glyph and
the first of the second, coverage > 25 %; 0 = adjacent columns, nothing overlaps at any k up to 10):

| pair | rn | ll | fi | rt | ff | ij | LT | AV | ty | r, | ’s | “A | 00 | 11 | 1: |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| stock Arial | 1 | 2 | 1 | 0 | 0 | 2 | 4 | 4 | 0 | 4 | (em gap) | 4 | 1 | 4 | 4 |
| Inter, k 0 | 2 | 3 | 1 | 1 | 0 | 2 | 4 | 4 | 1 | 5 | 3 | 3 | 2 | 2 | 2 |
| **Inter, k 8** | 1 | 2 | 0 | 0 | 1 | 1 | 4 | 3 | 0 | 4 | 3 | 3 | 1 | 2 | 2 |

So at k = 8 Inter's letters sit as close as Arial's do (`rn` still reads as two letters, `fi` and `ty` just
meet as they do in Arial). Before and after: the first V2.1fI (untracked, `aa21d94d...`) against
this one (`fa1f04d7...`). Only `default.ttf`, the lock clock size (122 -> 129 px) and Now Playing's
prefix offset differ. The preview shows the tracked font.

Not pursued: the user picked tracked Inter over the other Latin candidates that were proposed (Inter at
0.97 scale, Source Sans 3, Noto Sans, Roboto), so they were not rendered.

## Source Han Sans for CJK, kana, Hangul

For every stock code point in CJK Unified (U+4E00-9FFF), CJK Ext A (U+3400-4DBF), Hiragana,
Katakana, Katakana Phonetic Extensions and Hangul syllables (38,868 code points; Source Han Sans SC
has all of them), the SHS outline is scaled by 0.256 (1000 -> 256 units/em), shifted down 7 units,
converted to quadratic curves (`Cu2QuPen`, max error 1 unit, direction reversed for TrueType) and
written over the stock glyph. The advance is `round(adv * 0.256)`: 256 for ideographs and kana as
before. Hangul syllables become proportional, 236 units against 256. The research comparison
(original CFF at 1000 units against the converted glyphs, unhinted, 300 sampled glyphs) found mean
absolute differences of 1.5-1.7 % at 16-21 px, which you cannot see.

**dy = -7.** Undisplaced, Source Han Sans' ideographs sit higher than Microsoft YaHei's: the median ink
centre is 97.5 units, against 89 for stock. Shifted 7 units down, it is 90.5, a hair above stock.
That is also the centre of Inter's capitals (91.5), so Latin and CJK share a visual middle in mixed
titles, and CJK rows keep their stock position in every layout. The ink still fits the line box with
room to spare (-27..208 against descender -69 / ascender 230).

Not replaced, on purpose: CJK symbols and punctuation (U+3000-303F: 、。「」《》), fullwidth forms
(，！？（）：), CJK compatibility ideographs, enclosed CJK, Bopomofo and jamo. They keep the stock
(YaHei) glyphs, which follow the same SC conventions. Only the code points of the recipe above were
compared and verified.

## Merge method (`tools/mod_font.py`, fontTools)

1. the tree's `default.ttf` must be the stock V2.1 file (SHA-256). The font step runs **first**,
   right after the battery step and before `mod_lockscreen.py` (`build.py` `EARLY`). Every later step
   therefore measures the new font: the lock clock size, Now Playing's `Album:` width (45 -> 43 px,
   both without the +1 px per glyph),
   and `mod_boot.py`'s quote check
2. CJK: as above, written over the stock glyph by cmap name (no stock glyph is shared by two of
   these code points, so none needs a glyph of its own)
3. Inter: the subset (tracked by `INTER_TRACKING`, above) is added as new glyphs, and its 1,429 code points are pointed
   at them (822 replace stock mappings, 607 are new, e.g. Vietnamese U+1E00-1EFF, € and Latin
   Extended-B, which the stock font lacked: "Tiến" had a hole in it)
4. a fontTools subset pass with every remaining code point: drops the stock glyphs nothing maps to
   any more (the replaced Arial/YaHei Latin, Greek and Cyrillic), the hinting (`fpgm`, `prep`,
   `cvt `, glyph programs), `gasp`, `DSIG` and the glyph names (`post` 3.0). It prunes GDEF/GPOS/GSUB
   to what is left. Those three are kept, though AWTK ignores them
5. the copyright line, then save with the stock `head` dates. The output is deterministic for a
   given fontTools version, which is why requirements.txt pins 4.67.0

`tools/font_inter.py` made the subset: Inter 4.1 Regular's code points in `mod_font.INTER_RANGES`
(Basic Latin, Latin-1, Latin Extended-A/B, spacing modifiers, combining marks, Greek, Cyrillic +
supplement, Latin Extended Additional, General Punctuation, super/subscripts, currency, № and ™).
It bakes tnum into the digits, drops hinting and layout tables, decomposes composites, prunes, and
scales to E 252 with `scale_upem`. The result is 1,428 simple glyphs, 159,300 bytes.

## Checks

In the build (`mod_font.verify`, through the stb view of both files):

- vertical metrics and unitsPerEm are stock. stb's cmap choice is a format-4 subtable
- **no code point is lost**: all 42,853 stock code points still map, and every one that had ink in
  stock still has ink (no tofu). 39,690 point at new glyphs and 607 were added
- the 3,163 others keep their exact stock outline and advance (compared vertex by vertex as stb reads them)

Code point audit of the built V2.1fI font against stock (changed = different outline or advance):

| block | stock | changed | unchanged | added |
|---|---|---|---|---|
| Basic Latin U+0000-007F | 123 | 95 | 28 (control characters) | 0 |
| Latin-1 U+0080-00FF | 96 | 95 | 1 (U+00AD soft hyphen) | 0 |
| Latin Ext-A U+0100-017F | 128 | 127 | 1 (U+0149) | 0 |
| Latin Ext-B U+0180-024F | 19 | 19 | 0 | 188 |
| Spacing modifiers U+02B0-02FF | 80 | 80 | 0 | 0 |
| Combining marks U+0300-036F | 112 | 65 | 47 (Inter lacks them) | 0 |
| Greek U+0370-03FF | 127 | 102 | 25 (Coptic and archaic letters) | 3 |
| Cyrillic U+0400-052F | 145 | 139 | 6 (Ѻ-ѿ) | 110 |
| Thai U+0E00-0E7F | 87 | 0 | 87 | 0 |
| Latin Ext Additional U+1E00-1EFF | 0 | 0 | 0 | 255 |
| General Punctuation U+2000-206F | 90 | 65 | 25 | 12 |
| Super/subscripts U+2070-209F | 34 | 34 | 0 | 8 |
| Currency U+20A0-20CF | 0 | 0 | 0 | 29 |
| Letterlike U+2100-214F | 39 | 0 | 39 | 2 (№, ™) |
| symbols, arrows, math, boxes U+2150-2FFF | 1,784 | 0 | 1,784 | 0 |
| CJK Symbols/Punctuation U+3000-303F | 64 | 0 | 64 | 0 |
| Kana U+3040-30FF | 189 | 189 | 0 | 0 |
| Bopomofo, jamo, enclosed, compat U+3100-33FF | 451 | 16 (U+31F0-31FF kana ext) | 435 | 0 |
| CJK Ext A U+3400-4DBF | 6,582 | 6,582 | 0 | 0 |
| CJK Unified U+4E00-9FFF | 20,909 | 20,909 | 0 | 0 |
| Hangul syllables U+AC00-D7A3 | 11,172 | 11,172 | 0 | 0 |
| compat, presentation forms U+D7A4-FEFF | 91 | 0 | 91 | 0 |
| Halfwidth/Fullwidth U+FF00-FFEF | 225 | 0 | 225 | 0 |
| Specials | 2 | 0 | 2 | 0 |

Total: 42,853 -> 43,460 code points, 0 lost, 39,689 changed (one replaced code point, U+034F
combining grapheme joiner, is an empty zero-width glyph in both), nothing changed outside the two range lists. Cross-checked once with fontTools
4.67.0 (`checkChecksums=2`, every table decompiles, no composites, no glyph programs, `post` 3.0).

Build-level:

- `fwtool verify` OK. Two clean builds give the same package. `look-all` still builds V2.1eA
  byte-identical (`cc86e833...`) on the branch (after the merge `look-all` is V2.1fA, `0e3980fb...`)
- `fwtool diff` V2.1eA -> V2.1fI (the branch build): exactly 3 files, `fonts/default.ttf`,
  `ui/screensaver_page.bin` (lock clock 138 -> 129 px and the rows under it) and `ui/playing_page.bin`
  (the `Album:` offset 45 -> 43 px). After the merge, V2.1fA -> V2.1fI: 5 files, the same three
  (the album offset now measured with the +1 px: `Album:` is 49 px, the label at x -50) plus both
  `dialog/dropdown_dialog.bin` (default and theme1, the pull-down fix below)
- `test/patch.py` on the built tree: 128 passed, 0 failed. `mod_theme.py --scan`: ok (worst 9.04 / 5.44, as V2.1eA)
- widths with the +1 px (all 404 en_US strings at 18 px, against the stock font): median -1.7 %, worst
  +9 %; Russian median -4.5 %, Korean -6.8 %, Chinese and Japanese unchanged.
- static ui texts that overflow their widget: the two that already did with the stock font (the lock
  screen's sample title and a Tidal login hint, both scrolling or wrapped), plus one new case. The
  pull-down's own status bar (`dialog/dropdown_dialog.bin`) shows the volume at 20 px in a 30 px
  label: `100` is 33 px (stock exactly 30), and its ink ends at 32 px. So at volume 100 the last zero
  may lose two pixel columns if the label clips. Untracked Inter does the same. **Fixed in the merge**
  (`mod_font.fit_pulldown`): `label_volume` grows to the AWTK width of `100` (33 px, measured with the
  shared text model `mod_lockscreen.StbText`) and the row's `children_layout` spacing drops 4 -> 3, so
  the three gaps give the 3 px back and `img_digital` (94..112), the clock and the right-hand icons stay
  put. The app resizes only `img_volume` there (15..24 px by level, `dropdown_showface` `0x475978`), so
  the widest layout is the asset's. Both asset themes (default, theme1) get it; with the stock font
  `100` fits and the step leaves the files alone.
- status bar (look-theme, 16/18 px): `12:59 PM` 70 -> 72 px in its 90 px slot (still clear of the
  Bluetooth icon at 201), volume `100` in 30, `100%` 36 px in 40

## Interplay with the other mods

- `mod_boot.py` (curly quotes): the stock font gives ’ “ ” the CJK em advance, so look-boot maps them
  to the straight glyphs. Inter's quotes are proper and proportional (58 and 103 of 256 units after tracking), so
  `apply_quotes` now accepts a non-stock font only if every curly quote is mapped and narrower than
  half an em. Then it prints `quotes: skipped ...` and leaves the font alone. Any other font is
  refused as before. With the stock font nothing changed (V2.1eA byte-identical)
- `mod_lockscreen.py`, `mod_nowplaying.py`: they read `fonts/default.ttf` from the tree, which the
  font step has already replaced. After the merge both measure with demo's +1 px per glyph (the shared
  `StbText` model in `mod_lockscreen.py`): the classic lock clock is 129 px (297 of 320 px drawn, as
  in stock), the `Album:` prefix 49 px (label at x -50), and lock screen 2's 88 px clock and date fit
  (`docs/lockscreen2.md`)
- `mod_theme.py`, `mod_lists.py`: no font measurements

## Size

| | default.ttf | rootfs.squashfs | free (limit 55,738,368) |
|---|---|---|---|
| V2.1eA look-all | 9,794,328 | 53,129,216 | 2,609,152 |
| **V2.1fI look-all-inter** | **9,928,864** | **53,370,880 (+241,664)** | **2,367,488** |
| V2.1gA full (`docs/full.md`) | 9,928,864 | 53,374,976 | 2,363,392 |

The font alone, squashed as the build does (LZO, 128 KiB, tail ends): 5,384,585 -> 5,627,359 bytes.
Source Han Sans' outlines need more bytes than YaHei's, and Inter adds 1,428 glyphs. Dropping the
hinting, `gasp`, `DSIG` and 426 KB of glyph names wins most of that back. Package SHA-256 on the
branch: `fa1f04d7cd56babfea29a3de9c104fafc717d5b14e589f10cc419adcd6deed9f` (tracked, the default), font
SHA-256 `5d22aee2e97f4a8d00900ed4b0d820f919d19f9e421bce3c4e49fcfa43d572d0`. The first, untracked
build was `aa21d94d...` (font `88695838...`), never flashed. Tracking does not change the size.
After the merge (album fix measured with +1 px, pull-down fix): **V2.1fI
`ff8d90bfe5469f71b842e2ad436f3bee512e8217a61cd05cbb8499c44ede81da`**, the same font; `fwtool diff`
against `fa1f04d7...` lists `ui/playing_page.bin` and the two `dialog/dropdown_dialog.bin`.

## Risks

- **not hardware-tested**. The rendering argument is static: the same stb rules as stock, checked
  through ports of stb's own lookups, and no tables or glyph kinds the stock font did not already have
  (simple `glyf` glyphs, format-4 cmap, long `loca`, full `hmtx`). A font that fails to load would
  show no text at all; fall back to V2.1eA
- **memory/speed**: the file is 1.4 % larger. AWTK caches rendered glyphs, so first draws of new
  glyphs cost about what they did. Source Han Sans' CJK outlines may have more points than
  YaHei's, so a long Chinese list might draw a little slower the first time
- **widths**: with tracking, English text averages Arial's width. Digit strings are still 2-4 px wider
  (Inter's tabular figures), which is why the pull-down's `100` overflowed its 30 px label by 3 px
  (now widened). Most texts are set by code, so check tight labels on the device
- **CJK punctuation stays YaHei**, ellipsis and dashes in General Punctuation become Inter's: a Chinese
  string with `……` or `——` shows Inter's baseline ellipsis and its dash, narrower than the CJK em forms
- the colon is not raised between digits (no contextual alternates in AWTK)
- combining marks (NFD-tagged titles) are drawn without mark positioning, as before. Inter lacks
  47 of them, which keep the stock glyph
- Hangul is now proportional, so Korean text is ~8 % narrower

## Device checklist (not yet hardware-tested)

Fall back to V2.1fA (same build, stock font) or V2.1eA if anything misbehaves.

- boots, the UI draws text everywhere; About still reads V2.1
- **crispness at small sizes**: status bar (16 px volume, 18 px clock, `86%` at 15 px), settings rows,
  the 14 px play times. Thin or fuzzy text compared with V2.1eA is a finding (Medium is the alternative)
- **lock clock**: `hh:mm` centred and fully on screen at 129 px, digits evenly spaced; date and battery
  row under it, not overlapping; it ticks over a minute
- **spacing**: English settings rows and titles look evenly spaced, neither cramped (`rn`, `fi`, `ty`)
  nor loose; compare a list against V2.1eA
- **pull-down at volume 100**: the volume number `100` in the pull-down's status bar is whole, the
  speaker icon a pixel closer to it than before; with digital output on, its icon is where it was and
  clear of the clock (also in 12 h mode); at volume 0-9 the row closes up as on stock; also with the
  coral theme (theme1)
- **times do not jitter**: status bar clock, Now Playing elapsed time while playing, the lock clock
- **CJK mixing**: a Chinese, a Japanese and a Korean title in Songs and Now Playing: ideographs and
  Latin share a baseline and a visual middle; Chinese UI language: settings, dialogs, keyboard
- **Cyrillic / Greek / Vietnamese**: a Russian title (Inter's Cyrillic), a Vietnamese one (no holes)
- **Thai unaffected**: a Thai title draws as on V2.1eA
- **curly quotes**: a title with ’ “ ” shows proper curly quotes with normal spacing (not the straight
  ones V2.1eA shows), in the library, Now Playing and the lock screen strip
- Now Playing: the album line still hides `Album:` (English UI); the long-title scroll is smooth
- status bar with Bluetooth on, in 12 h mode: `05:30 PM` clear of the Bluetooth icon
