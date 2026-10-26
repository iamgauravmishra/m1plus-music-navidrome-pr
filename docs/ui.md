# UI: the looks of the release

Everything here is asset-only (no code) except where it says demo words change or the payload paints (Now Playing); the payload side is
in `docs/architecture.md`. The steps run in the order of `tools/build.py` (battery, font, [payload],
theme, lists, nowplaying, boot, rows, pulldown, lockscreen, wallpaper, icons, polish) on one tree; each
step pins the stock bytes it replaces by SHA-256, keeps every widget name and refuses to apply twice.
Style is q2-pod's Minimal / iPod (MIT, `NOTICE`) fitted to the 320x480 portrait touchscreen.

![the release](release-preview.png)
`docs/release-preview.png` is the one tracked preview (`tools/preview.py WORKDIR [OUT.png]`, default
`out/preview/release-preview.png`, gitignored; the tracked sheet is refreshed only at a release, `docs/workflow.md`):
Home pages 1 and 3 (the M1 Pod icon), the M1 Pod menu as Home (no top bar), the Settings, Main Menu, Shuffle and
Extras pages, the Artists toggle, the album page, an artist's Cover Flow (and the landscape one), the Albums grid and
list, the pull-down with the toggle and slider art (`controls()`), the lock screen (playing; idle on the charger) and
the battery at 8x. The other previews (`tools/preview_all.py`, `preview_icons.py`, `preview_stock.py`,
`preview_battery.py`, `preview_nowplaying.py` ...) write wherever you point them; use `out/preview/`. All are
approximate PIL mock-ups drawn from the built tree (not AWTK), text rasterised from the tree's own `default.ttf`
the stb_truetype way (`tools/preview_font.py`, `tools/stb_raster.py`), sample data.

## 1. Rules every UI step follows

- **Names stay.** Never rename or delete a widget the app looks up by name (`widget_lookup(win, name,
  TRUE)`, recursive, so reparenting is safe); restyle, move or hide it.
- **Hit testing ignores `visible`.** Hide = `visible=false` + `sensitive=false`; decorative overlays
  are `sensitive=false`. This AWTK's `widget_find_target_default` (`0x6747d4`) takes the first child
  (from the top) with enable and sensitive set (`flags & 9 == 9`) that contains the point;
  `widget_on_pointer_down_children` (`0x6714ac`) checks the same two bits. The tools model it
  (`check_touch` in `mod_lockscreen.py` / `mod_nowplaying.py`: centre of every control reaches that
  control, at least 44 px each way, the album page's two buttons 110x36; the cover reaches the gesture parent) and `test/pod/` runs demo's
  own `widget_find_target` on the built page trees.
- **Normal windows are 450 px tall** (under the 30 px `system_bar`); only fullscreen windows
  (`screensaver_page`) get 480. 68 stock pages end exactly at y = 450 (`systemset/sysset_page.bin`:
  navbar 0-50, list 50-450). Lists use the stock structure `list_view` > `scroll_view` +
  `scroll_bar_m` with stock `list_item` rows (`list_item_style`, an `hscroll_label` themed
  `srlabel_leftwhite21_style`, the `right_arrow` image); bare `list_item`s fall to the light default
  theme (white on white).
- **Window theme first.** A widget's style is resolved in its window's theme (`styles/<window name>.bin`,
  or its `theme` property) before `styles/default.bin` (`style_const` `0x6d3038`,
  `widget_get_window_theme` `0x66ab78`, `window_base` `0x6761dc`; lookup is a linear scan of 100-byte
  items). Page-local styles change one page only.
- **Text width = truncated glyph advance + 1 px per glyph** (below); use `StbText`
  (`tools/awtk_text.py`) and measure the font of the tree being built.
- **No close animation on windows a "play from here" loop can pop** (library pages, album detail, the
  jump list, Now Playing, M1 Pod pages), see the slides audit in section 8.
- The rebuilt rootfs must not exceed stock (fwtool enforces it); one change per package where possible.

## 2. The text-width model (`tools/awtk_text.py`)

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

## 3. Font (`tools/mod_font.py`, `tools/font_inter.py`)

One file, `release/assets/default/raw/fonts/default.ttf` ("微软雅黑+Arial", 256 units/em, 9.4 MB),
rewritten by code point; unitsPerEm, hhea ascender/descender/lineGap and OS/2 stay, so every layout
sized from them still adds up. The step runs first so every later step measures the new font.

- **Latin, Greek, Cyrillic: Inter 4.1 Regular** (`assets/fonts/Inter-m1plus.ttf`, the committed subset,
  159,300 bytes, 1,428 simple glyphs; `font_inter.py INTER_ZIP` regenerates it byte-identically with
  fontTools 4.67.0; OFL in `assets/fonts/`), outlines at 252 stock units per Inter em (cap height 183
  = Arial's), tabular digits baked into the cmap (`0-9` -> `zero.tf..nine.tf`, 163 units, 155 after
  tracking), composites decomposed. **Tracking 8**: every Inter advance loses 8 units and each outline
  moves left 4, because Inter as designed sets English 3-9 % wider than Arial once demo's +1 px per
  glyph is added; k = 8 makes the mean ratio over 16/18/21 px 0.999 (0.989 / 0.984 / 1.023). Regular
  (not Medium) puts the same ink as Arial (within 1 %) with stems as crisp. 1,429 code points (822
  replace stock mappings, 607 are new: Vietnamese, EUR, Latin Ext-B).
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
  points, 9,928,864 bytes (+241,664 squashfs).
- **Pull-down volume.** `100` at 20 px is 33 px in Inter (stock 30), so the font step widens
  `label_volume` of `dialog/dropdown_dialog.bin` (both themes) to the AWTK width and cuts the row's
  `children_layout` spacing 4 -> 3 so the icons stay put; `mod_pulldown.py` later puts it back (section 7).
- Not fixed on purpose: CJK ellipsis/dashes become Inter's, the colon is not raised between digits
  (no contextual alternates in AWTK), combining marks are drawn without positioning (47 absent from
  Inter keep the stock glyph).

## 4. Theme, lists, Now Playing

### Minimal theme (`tools/mod_theme.py`, `tools/awtk_style.py`)

`styles/*.bin` is AWTK's compiled theme: a 12-byte header (`fd fc fb fa`, version 0, item count), one
100-byte item per (state, style name, widget type) with the offset of its property block, then blocks
of `{u8 type, u8 key size, u16 value size, key\0, value}` (types 6 int32, 7 uint32 -- colours r,g,b,a
-- 14 string). All stock theme files (default and theme1) round-trip byte-exact. Only the **default
theme** is modded: theme1 (accent salmon `#FA7268`, its own image files) keeps its stock look.

| role | colour | stock |
|---|---|---|
| row surface | `#000000` | `#131313` |
| row hairline | `#222222`, 1 px bottom | 4 px black gap |
| pressed row / key | `#333333` | `#362221` (default), `#2E2A1A` (theme1) |
| title text | `#FFFFFF` | same |
| former accent text | `#FFFFFF` | `#FE7E40` / `#FA7268` |
| muted partner text | `#8C8C8C` | `#FFFFFF` |
| secondary text | `#AAAAAA` | same |
| settings icon disc | `#777777`, white glyph | coloured discs |
| status glyph on / off | `#FFFFFF` / `#666666` | white / grey |
| slider fill / track / thumb disc | `#EEEEEC` / `#333333` / `#777777` | orange `#FE7E40` / `#333333` / orange disc |
| toggle on / off | white track, dark knob / stock grey track, light knob | orange track / same grey |
| Home page dots | `#EEEEEE` / `#555555` | `#FFFFFF` / `#666666` |

Edits are pinned (file SHA-256, per edit the old value and the state count, `STYLE_EDITS`):
`list_item_style`, `list_item_notpress_style`, `list_itemsort_style`, `btn_tablerow_style` (bg black,
pressed `#333333`, bottom hairline), `kb_btn1/2_style` pressed, the gold label styles
(`srlabel_item_gold18/20`, `label_centergold22`, `text_gold22`, lyric and tab styles: accent -> white
with the partner style muted grey so a selection still reads). Kept: red error text, the green/red
battery states, the red `icon_playing` disc, and every AWTK light default
style (`window`, `dialog`, `list_view`, `label`, `button`): stock pages set their dark colours inline,
and a global change of those defaults is how white-on-white happens. Images: the 46 settings icons
(40x40) get the `#777777` disc with the glyph kept (q2-pod's `ringnav_image_add` rule: saturation
against the icon's most saturated pixel blends disc grey to white, alpha kept bit for bit; replaced
later by the icons step), status icons redrawn at 4x (one weight, round caps, concentric Wi-Fi arcs,
unlit `#666666`). **Status bar** (`system_bar.bin`, on `mod_battery`'s layout): `view_bar_left` x 10
s 4, `label_volume` and the battery slot 16 px middle, `bar_dclock` 104,0 90 wide 18 px (a 12 h
`12:59 PM` is 66-72 px, clear of the Bluetooth rune), `view_bar_right` s 4 ending 4 px before the
battery outline. **Home** (`home_page.bin`): the strip black with a 1 px `#222222` top border, the
artist line `#AAAAAA`, dots `#EEEEEE`/`#555555`; the icon grid is built in code.

**Accents in images (`ACCENT_ART`, `accent_to`):** the orange left in stock art is recoloured at build time
(each file pinned by SHA-256, alpha kept bit for bit, name and size unchanged). A pixel's HSV saturation against the
accent's says how orange it is, its value (to the 1.5 power) keeps shading and dark text on the orange; the grey part
stays. Fills (`vol_progress`, `volume_fg`, `drop_fg`, `eq_plan`, `other_progress`, `cdprogress_bar`, the date selector's
`datetime_back` edge) go `#EEEEEC` on the stock `#333333` tracks;
the brightness / balance thumbs (`light_dot`, `balance_dot`) and the "default cover" corner flag
`screensaver_defaulticon` become `#777777` discs with the white glyph kept (the settings-icon disc); the default
cover tiles (`defaultcover`, `scover_default`) take the "no cover" tile colour `#333333` with the white logo.
**Toggles** (`sset_on`, `pset_dual`, `pset_high`): on = a white track with dark text and a dark knob (luma-mapped
inside the knob circle), the pull-down's "on" is a white disc with a dark glyph; off (`sset_off`) is the stock grey
track with the light knob, which was already neutral. The on/off states read by brightness and by knob side, not by
hue. Left orange on purpose: the CD ripper art (`cdripper_bg*`, `select_right`, `selectde_left`: the page's
styles hard-code orange text), the Online search button, `chargebg`'s red bolt, the hidden `p_hr`, the salmon bit-depth
and store badges (brand art, Chinese or account only), and everything in theme1.

**Contrast gates, every build:** `audit()` checks every state of the row styles against every label
style a row can hold (no light row surface; worst text >= 4.5:1 at rest and pressed: rest 9.04, pressed
5.44, white 21 / 12.6); `page_audit()` checks every text-drawing widget of every `ui/*.bin` against the
nearest opaque ancestor, stock vs mod, and fails if any pair falls below 4.5:1 and got worse;
`mod_theme.py --scan TREE STOCK` repeats the page scan on the finished tree (window themes included).

### Library lists (`tools/mod_lists.py`)

The library pages' rows are built by code (`folder_create_tablerow` `0x5331fc`,
`localclass_create_tablerow` `0x5368ac`, `music_create_tablerow` `0x528560`, the jump list's cloned
template row `0x5f0b54`, `album_listitem_layout` `0x524228`, `albumdeinfo_listitem_layout` `0x526394`,
`playlist_*item_layout` `0x53e064..`, the search handlers), so geometry is code (section 7); an asset
can change what the style names resolve to. `mod_lists.py` writes page themes (`styles/folder_page`,
`localclass_page`, `allmusic_page`, `playerjumpinfo_page`, `playlist_page`, `search_page`, for default and
theme1, each **derived at build time from the tree's own `default.bin`** so the lists follow the theme):
`btn_tablerow_style` = list_item colours per state; `srlabel_item_white/gold20` at 21 px;
`srlabel_item_gray26_style` defined (stock creates the artist line with a name no theme defined, so it
drew `#444444` on `#131313` until data loaded); Import/Export tiles in the list colours; Search tabs on the row
colour with `#AAAAAA` labels and the active tab white over a 3 px accent underline; the Songs index
letter `view_letter` a `#262626` rounded square (radius 14, `#3A3A3A` edge) with a white letter;
`batchadd_dialog`, `confirminfo_dialog`, `sortselect_dialog` pressed in the list colour. Left out:
page slide transitions (loop hazard, section 8), row geometry (code), the confirm dialog's two-row
layout (its `confirminfo_bg` image draws the divider).

### Now Playing (`tools/mod_nowplaying.py`, `patch/nowplaying.c`)

An Apple-Music-style page on the stock `playing_page`, fitted to the 320x450 window (`tools/preview_nowplaying.py` draws it from a built tree):

```
  0   ====== grabber pill 36x5 (the Back button, 100,0 120x44)
 28   +--------------------------+  cover 264x264 at 28,28, corners 12 px
      |                          |
 292  +--------------------------+
 296           . o .               micro page dots: 3 x 4 px, 10 px apart
 304  Title (22 px white)    (heart)(...)    heart, More: 44x44 targets, 36 px discs
 330  Artist (18 px #AAAAAA)
 354  =============---------------   bar 6 px in the stock 30 px target (28,354, 264 wide)
 384  01:23                  -03:42   12 px #AAAAAA: elapsed, remaining
 400  [mode] [<<]   [ || ]   [>>] [queue]   the five stock slots, 50 px high
 450
```

- **Window colour.** The window is the cover's colour (below the gradient) and its colour changes per track: the asset's
  `bg_color` is the neutral tone `#202020`, `patch/nowplaying.c` sets the window's `bg_color` through the style API
  when the cover changes. Over it lies `img_np_tint` (`np_tint.png`, 320x450, black, alpha 38 on the first row to 235 on
  the last = 0.15 .. 0.92), the first child of `view_local`, insensitive. The tone of a cover: its box-averaged colour
  (`cc_box`, the whole picture to one pixel) with value `32 + v * 160 / 255` (`v` the brightest channel, so 32..192) and
  every channel keeping 4/5 of its distance from `v` (a grey stays grey; black is the neutral tone). Under the gradient the
  white title and every `#AAAAAA` line keep at least 4.5:1 at any tone (`test/pod/nowplaying.py` checks the worst case
  at the title, artist and times rows). No cover file (a random or streamed source), or the kill switch: neutral.
- **The cover is 1:1.** AWTK scales an image by nearest neighbour, so the art is drawn at the size of the file:
  demo writes `/tmp/coverpic.jpg` / `/tmp/externpic.jpg` at **264** (four pinned immediates, section 7, Lock screen: "The cover
  size is a demo constant"), the widget is 264 at 28,28 (the 28 px margin is the text column's and the bar's too). A 280 px
  art (margins 20) would cost 16 px of height in the 450 px window and push the transport row under 44 px; 264 keeps the
  rhythm and only makes the lock screen's card 16 px smaller.
- **Rounded corners.** An image cannot be clipped, and a static mask has one colour while the window has many, so
  the payload paints the four 12 px corners in the colour the window has there (the tone under the gradient on that row),
  anti-aliased (8x8 samples a pixel), from the cover widget's own `EVT_AFTER_PAINT`: about 160 one-pixel fills when the cover
  repaints (open, track change), none otherwise. Without the payload (kill switch, a failed hook) the art is square.
- **Controls.** The grabber is the Back button (`btn_return`, `img_btn_style`, `np_grabber` / `np_grabber_down`: a 36x5
  white pill at 43 % in a 120x44 image), overlapping the top 16 px of the art (a swipe starting there goes to the button).
  Heart (`btn_fav`) and More (`btn_more`) are `np_fav` / `np_unfav` / `np_more`, 44x44 images with a 36 px disc (`#FFFFFF1A`,
  `#FFFFFF33` pressed) baked in; the app swaps the heart's style (`btn_imgfav_style` / `btn_imgunfav_style`) as before.
  Transport: prev / play / pause / next are solid PIL-drawn shapes (play 27x32, pause two 8x32 bars, skip two 16x18 triangles),
  mode and queue are Tabler glyphs at 22 px in `#AAAAAA` (repeat-off `#6E6E6E`), pressed `#8C8C8C`. The progress bar is the
  stock `slider_play` (a 30 px seek target) with `bar_size` 6, track `#FFFFFF33`, fill `#FFFFFFEB`, `round_radius` 4 (the
  slider paint reads it; whether this build rounds a 6 px bar is only the device's to say), no thumb. The slide
  indicator has `size` 4, `spacing` 10, dots `#FFFFFF46` / `#FFFFFFEB`.
- **Not on the art page.** The album line (`label_album` is on the info page with genre, year, size, location), the quality
  line (`label_info`, the info page's first line), the "3/12" index (`label_index`, hidden at 0x0 like `img_hr`, which demo toggles
  for Hi-Res tracks), the Hi-Res tag. Every widget the app looks up keeps its name; the new ones are `img_np_tint` and
  `np_remaining`. Lyrics (page 2) and info (page 3) start under the grabber (y 44) and end above the dots (y 288); the slide
  pages are 352 px high so page 1 holds the title and artist.
- **Remaining time.** demo rewrites `label_playlen` with the track's length on every 500 ms tick. `np_remaining` (an insensitive
  label on the same rectangle, hidden in the asset) shows `-mm:ss` (`-hh:mm:ss` from an hour on, stock's zero-padded clock
  format) from `get_playtimeandlength` (the call the stock tick makes) while the player reports a length; the payload swaps
  the two labels' visibility, and `label_playlen` shows again whenever the player does not. A position past the end reads
  `-00:00`. Both labels are insensitive in the asset, so a hidden one never takes a touch.
- **A-B repeat markers.** demo moves `img_repeata` / `img_repeatb` to `x = 12 + pos * 296 / len`, `y = 364` (the bar's centre
  357 + 7) in `getx_by_playtime` (`0x53b824`, `0x53b8f0`; only from this page's timer): five pinned `addiu` immediates make it
  `x = 28 + pos * 264 / len`, `y = 376` (centre 369 + 7). `mod_nowplaying.marker_edits` lists them with their stock words;
  `test/demo_diff.py` allows exactly these.
- **Files.** `ui/playing_page.bin`; `styles/playing_page.bin` (the window theme searched before `default.bin`: the mode and favourite
  styles point at `np_*` icons, which the app swaps with `widget_use_style`; page-local `btn_imgplay_style` / `btn_imgpause_style`, so
  the lock screen and other pages keep theirs; lyric lines `#8C8C8C` and `#EEEEEC`); `images/xx/np_*.png` (21 glyphs from
  `mod_icons.py`, plus `np_tint.png` drawn by the step). `image_wait` and the A-B markers are insensitive. Touch: `check_touch`
  models demo's hit test for every control (44 px, the slider 30), the art and the title rows reach the slide view.

## 5. Boot logo, quotes, settings slides (`tools/mod_boot.py`)

- **Logo.** `/etc/init.d/S11logo_display_shell` runs `display_logo` on `images/xx/logo180.jpg` when
  `/mnt/data/config.ini` has `ROTATEMODE=1`, else `logo.jpg`; these are the only splash images. Stock
  files are upright 320x480 baseline JPEGs (4:4:4, Adobe YCbCr; `logo180` is `logo` turned 180°);
  `display_logo` draws 1:1 and reads libjpeg RGB, so a replacement must be 320x480, 8-bit, 3
  components, baseline. `assets/boot-logo.svg` (q2-pod style: outlined **M1** wordmark in `#F2F2F0`,
  muted **POD** in `#BDBDB8` with the centre button, centred at 47 % height) is rendered by
  `tools/boot_logo.py` (`brew install librsvg`; 4x box-filtered, Pillow q92 4:4:4) into the committed
  `assets/boot-logo.jpg` (5,845 bytes) and `boot-logo180.jpg`; `mod_boot.py` checks both stock files by
  SHA-256 and each new file's frame header (q2-pod's `jpeg_size`) and keeps mode 755.
- **Quotes.** The stock font gives U+2018/2019/201C/201D the CJK em advance (256 units against 48 for
  `'`, 90 for `"`), so "Paul’s" shows a wide gap. The step maps them to the straight glyphs, in pure
  Python (the one format-4 subtable gets four one-codepoint segments, 428 -> 434, the cmap grows 48
  bytes, later tables move, checksums recomputed), verified with the port of stb's lookup for every BMP
  code point. With the Inter font the quotes are proper and proportional, so `apply_quotes` skips
  ("accepts a non-stock font only if every curly quote is mapped and narrower than half an em"): in the
  release the quotes stay curly.
- **Slides.** Every settings window in `ui/systemset/` (33 files) and theme1's `specfolder_page` get
  `open_anim_hint` = `close_anim_hint` = `slide_left(duration=200,easing=cubic_out)` (the animator the
  stock lock screen's `close_anim_hint` uses): a page slides in from the right and back out (AWTK plays
  the close reversed). `fwupdate_page` and `fwdownload_page` stay stock (the way back to a known build).
  +115 bytes each.

## 6. Icons and the battery

### Tabler Icons (`tools/mod_icons.py`)

**Tabler Icons 3.49.0** (`@tabler/icons`, MIT, (c) Pawel Kuna; `NOTICE`, `assets/icons/tabler/LICENSE`),
pinned by the npm tarball's SHA-256 (`mod_icons.py --fetch TGZ` copies the ~95 SVGs it uses, parsed as
data with whitelisted tags and attributes). Committed: the used SVGs (`assets/icons/tabler/svg/`),
custom SVGs (`assets/icons/custom/`) and the generated PNGs (`assets/icons/tabler/png/`, 280 files);
the build only copies PNGs (no rasteriser, deterministic); `--generate` re-renders them with
`rsvg-convert` and Pillow at the exact stock size, `--pins` writes the stock SHA-256 pins
(`tools/mod_icons_pins.txt`), `--check [WORKDIR]` verifies pins, size and mode.

| area | files | design |
|---|---|---|
| settings icons | 42 of the 46 (40x40) | white glyph (26 px, stroke 2) on the `#777777` disc |
| Home grid | 18 + 18 `_down` (66x66) | white glyph (38 px) on `#777777` (`#555555` pressed); HiFi (zh_CN) a store; Tidal is Tabler's `brand-tidal` (`tidal`, `tidal_down`, which every state of `home_tidal_style` names) |
| M1 Pod Home icon | added `m1pod.png`, `m1pod_down.png` (66x66) | the click-wheel glyph on the same disc; the style `home_m1pod_style` (a copy of `home_tidal_style` pointing at them) is added to `styles/home_page.bin` in the stock sort order; the widget is built at run time (`docs/architecture.md` section 9) |
| pull-down tiles | 17 (50x50, 20x20 sun icons) | one ring style, section 7 |
| status bar | 15 (play, pause, volume 0-4, Wi-Fi 0-4, Bluetooth off/on, digital out) | white, unlit Wi-Fi arcs `#666666`; 1.5 px strokes at 14-16 px, 2 px at 20 |
| list placeholders | 6 discs (40x40), 3 "no cover" tiles (60/90/100) | glyph on the `#777777` disc / the tile colour |
| Albums view toggle | 4 added `pod_nav_grid`, `pod_nav_list` (+ `_down`, 24x24) | plain white glyphs (pressed `#777777`) like the navbar's others: Tabler `layout-grid` and `list` (`list.svg` is the one new SVG), each showing the mode a tap switches to; used by `ui/m1pod_albums.bin`, which swaps the glyph with its mode |
| M1 Pod rows | 26 added `pod_ic_*.png` (40x40) | menu, Shuffle, Settings and Extras page rows; disc x 12, title x 64, row height and chevrons unchanged, image insensitive |

Rule: an icon has a real Tabler glyph, or keeps its stock image (when decent), or is drawn in Tabler's
style (24 grid, 2 px stroke, round caps; `assets/icons/custom/`). Custom: `click-wheel` (the M1 Pod
Home icon), `guitar` (Genres), `badge-hr` (Hi-Res), `dac` (USB DAC), `volume-3waves`
(Tabler stops at two), `gain-low`/`gain-high` (tiles). Stock kept: DAC and DSD output (text on the grey
disc), ReplayGain, brand art and text badges (codec badges, SyncLink, A-B), theme1 (own image files),
the Chinese-only Home ids. Row glyphs: Now Playing the Lucide `audio-lines` wave (the navbar button's glyph), Cover Flow `carousel-horizontal`,
Shuffle `arrows-shuffle`, Songs `music`, Albums `vinyl`, Artists `microphone-2`, Genres `guitar`, Folders
`folder`, Playlists `playlist`, Settings `settings`; the Settings page: Main Menu `list-check`, Cover Flow `carousel-horizontal` (the menu's disc; opens Settings > Cover Flow: Landscape `rotate-clockwise`, Sort `sort-descending` with its value Artist / Album as grey 19 px text at the right, no chevron), Start in M1 Pod `home`, Playback `adjustments`, System Settings `settings`, Shanling Home the Shanling mark (`pod_ic_shanling`: the brand's swoosh cut from the stock shutdown screen `images/xx/shutdown.png`, SHA-256 pinned in `tools/mod_icons.py`, isolated by whiteness, thickened by about 1 px and scaled to 32 px wide on the disc; no glyph set involved); Extras `dots` and the Extras page's rows the Home grid's glyphs (`heart`, `clock-plus`, `history`, `flame`, `feather`, `badge-hr`, `refresh`, `world`, `disc`); the Shuffle page uses the song,
album and folder glyphs. `ui/m1pod_menu.bin`, `m1pod_shuffle.bin`, `m1pod_settings.bin`, `m1pod_extras.bin` and `m1pod_mainmenu.bin` get the child image (title x 24 -> 64). `icons` runs late so it overrides the theme step's grey discs.

### Icon audit, round 2 (`tools/audit_images.py`)

`audit_images.py [STOCK [TREE]]` lists every `images/xx` file referenced by a `ui/**/*.bin` property, a style
file or a name string in `demo` (560 files), and with TREE only those still byte-identical to stock. Before
round 2, 429 were stock; round 2 changed 110 stock files plus the `np_*` glyphs (21 now, V2.1mB). Result for the 560:

| class | files | action |
|---|---|---|
| Tabler (rounds 1+2) | 241 (131 + 110) | glyph in the stock size; round 2: navbar add / cancel / delete / multi-select / sort / search / back / chevron / more / settings (+ pressed `#777777`), selection circles and squares, expanders, queue-dialog modes, dialog actions (rename, scan, delete, add network, eye), Now Playing more-dialog and batch-add icons, Bluetooth/USB page transport |
| Tabler on the `#777777` disc | 24 of those | Folders rows (16 audio formats share `file-music`, SD, USB), Playlists page (New, Import, Export), CD track dialog (custom `guitar`, microphone, calendar) |
| custom SVG | 2 uses | `guitar` (Genres, CD genre); round 1 customs unchanged |
| Tabler `multiplier-1x` | 1 | `p_multiple` (28x28): the icon of the playback-speed row in the Now Playing more dialog (`playmore_dialog`, beside the 1.0X / 1.25X / 1.5X / 2.0X badges). The Play Settings list has no speed row, so there is no 40 px disc icon for it |
| Lucide (ISC) | 2 | `back_to_player` / `back_to_player_down` the navbar's go-to-Now-Playing icon, Lucide `audio-lines` (`assets/icons/lucide/`, lucide-static 1.61.0, tarball SHA-256 `62773cd2...ba75f1`, licence beside it, `NOTICE`), 23x24 like search, 2 px stroke, pressed `#777777`. The button is a static `img_btn_style` image pair (names without digits, no frame swap in `demo`: the only other `playing_*` names are the loading spinner `playing_wait_1..12` and the list's `icon_playing` disc) |
| stock recoloured white | 9 | equaliser preset instruments (`eq_*`), the line art is kept |
| drawn (Inter text / Tabler glyph) | 14 | speed badges (8), Play all pills (4: off-white pill, dark text), secured Wi-Fi rows (4: fan + lock) |
| orange to neutral | 15 | toggles, slider fills and thumbs, default covers (section 4, "Accents in images") |
| kept, decent or not an icon | 302 | 100 keyboard keys, 70 backgrounds / scroll arrows / unused check and radio art, 69 brand, codec and text badges, protocol art, the red `icon_playing` disc, 55 Tidal / HiFi store / purchase / guide art (Chinese or account only), 14 CD ripper art, 11 superseded by `np_*` or the brightness suns |

The Folders page has no "up" row image (Back goes up); Favourites and every playlist use `icon_playlist`
(round 1); Genres, Composers, Artists, Albums and search rows use the round-1 `icon_*` discs. `mod_icons.py`
`GLYPHS`, `DISCS`, `RECOLOUR`, `SPEEDS`, `PLAYALL`, `WIFI_LOCK`, `NP` are the tables; glyphs are fitted to the
stock canvas by ink size, 2 px stroke (1.5 under 22 px). Not asset-only: nothing here changes code.
(`tools/preview_icons.py STOCK_TREE RELEASE_TREE OUT.png`) before and after at
1:1 with a 3x status strip; blue **C** = custom glyph, orange **K** = stock kept.

### One battery (`tools/battery_art.py`, `tools/mod_battery.py`, lock screen step)

The app swaps `img_battery`'s image between `bar_power`, `bar_charge` (charging) and `bar_lowpower`
(capacity 0 only, `bgtz` `0x475c94`) and feeds `pgbar_battery` the capacity (100 when charge is done),
in the status bar and in the pull-down's own bar (`dropdown_showface` `0x475c3c`, twin `0x545168`); the
fill is drawn under the image (stock child order). So the image is the outline and the fill lands inside.
**No number anywhere:** `get_battery_capacity` (`0x4e6dd8`) buckets the battery voltage
(`toolsGetBatteryVoltage` `0x5e35b0`) at 3.535 / 3.595 / 3.705 / 3.865 / 3.995 V into 0/20/40/60/80/100
(another table while charging, `0x4e6f58`), so a percentage only ever read those six values. One drawing,
two sizes: 1.5 px outline (the Tabler status stroke), rounded body corners, a 2 px rounded nub, 8x
supersampled and box-reduced, written as a plain zlib PNG (bytes independent of Pillow). Normal: white
outline, the level is the white fill; charging: green `#34C759` outline and bolt with a 0.5 px black
keyline; low: red `#FF1448` outline. Status bar (`STATUS`): image 18x11 at (292,10), body 16x11, fill
12x7 at (294,12) (0.5 px gap), right edge at x 310 as stock, the right icon group ending 4 px before it
(x 187); the same in both `dropdown_dialog.bin` themes. Lock screen (`LOCK`): 34x12, body 22x12 at x 9,
fill 16x6 at (12,3), for `screens_battery/charge/lowbattery`. `fill_gap` asserts the fill stays inside
the outline; `tools/preview_battery.py` draws empty/half/full/charging/low from the tree's files.
Research note: this board's battery is an X-Powers AXP2101 PMIC (kernel `axp2101_charger`); stock demo
reads `/sys/class/power_supply/battery/voltage_now` (its CW2015 gauge code is dead from another model),
so `/sys/class/power_supply/*/capacity` very likely exists for a future honest percentage; nothing
depends on it.

## 7. Rows, pull-down, lock screen, wallpaper, polish

### Library rows (assets; the code half is `docs/architecture.md` section 6)

`tools/mod_ipodrows.py` edits the five row `ui/*.bin` (`localclass_page`, `allmusic_page`,
`playerjumpinfo_page`, `album_page`, `playlist_page`: `row_height` / `default_item_height` 60 -> 64 and the jump list's template row) and the page
themes (`allmusic_page`, `playerjumpinfo_page`, `albuminfo_page`, `playlist_page`, `search_page`, new
`album_page`, both themes, 21 px titles, `srlabel_item_gray18_style` second line). Rows are 64 px with a
60 px body above `list_item_style`'s separator, 52 px art at (4,4), titles to a 12 px right margin.

### The album page and the other stock pages (assets; the code half is `docs/architecture.md` section 8)

`tools/preview_stock.py WORKDIR OUT.png`: the Albums list and the album
page it opens, Cover Flow on an artist and the same page opened by the All albums card, a playlist's
songs, the queue. Approximate mock-ups, as above.

- **One album page.** The stock `albuminfo_page` opens from Albums, Cover Flow, Artists (through Cover
  Flow) and the All albums card; the header is restyled to the design in `docs/architecture.md` section 8
  (120 px cover rendered 1:1, 21 px white title, 18 px grey artist, a 15 px "year . N tracks" line, the
  dark Play all button and a Shuffle button, 110x36 each, the cover 8 px under the navbar). The sizes and positions are in code (the hook
  moves the stock widgets); the look is the page theme `styles/albuminfo_page.bin`
  (`btn_albumbtn_style`, `srlabel_meta15_style`, `tools/mod_ipodrows.py`), new names, so the stock
  `btn_imgplayall_style` (an orange pill image) remains for a header the hook leaves alone. From Cover Flow the cover appears a moment
  after the page opens, as from the Albums list (the cover thread renders it; `docs/architecture.md` section 8). The track
  rows are the q2-pod rows.
- **A playlist's songs** are the Songs page (`allmusic_page`, class `0xff13`, the playlist's name as the
  navbar title): the same 64 px rows and navbar as every library list. The stock page has no header and
  no Play all button, so there is nothing to restyle beyond that; a header with Play all and Shuffle would
  need a hook on that page's init.
- **The queue drawer** (`ui/dialog/playqueue_dialog.bin`, no preview): the 240x450
  panel that slides in from the right over Now Playing (opened by name from `playerjumpinfo_page_init` `0x53b17c` and
  `0x4d126c`; `dialog_playqueue_dialog_init` `0x47a7cc`). Its rows are cloned from a template (`queue_table_row`) by the stock table code, `row_height` read
  from the file, and bound by `0x47a19c`: the song name in `scrlabel_name` with `srlabel_item_gold20_style` for the
  playing row, `srlabel_item_white_style` for the rest. The minimal theme made both white, so nothing marked the
  playing row. Now (asset and page theme `styles/playqueue_dialog.bin`, `mod_lists.py` recipe `queue` and
  `edit_playqueue`): rows 44 px (button 40, a 4 px gap), the other rows muted `#9C9C9C` 18 px, the playing row
  white 20 px; the list's own row colours; a `#3A3A3A` hairline under the 64 px play-mode header (the Tabler mode
  glyph and name the app sets) and a `#3A3A3A` left border; the bottom button in the dark button colours
  (`#1E1E1E`, pressed `#333333`, 20 px). No widget is renamed or moved except the row template's height; no code.
  Not done: a play marker image on the playing row and a count in the header (the row bind and the header are
  code), Tabler icons on the bottom button (it has none).
- **The queue** (the Now Playing list page, `playerjumpinfo_page`): the playing track's row carries the
  stock red `icon_playing` disc in place of its icon (set by the row bind `0x539244`, `is_playing` `0x4d9d64`), the rows are the
  q2-pod rows (white title, grey artist), and the navbar title (the queue's name, a `srlabel_leftwhite22_style`
  `hscroll_label` the page builds) is 20 px like every other navbar title of ours (page theme, `mod_lists.py`
  recipe `navtitle`; the other code-built library titles stay 22 px). The track count and numbers would need
  code; not done.

### Pull-down (`tools/mod_pulldown.py`, `mod_icons.py`)

Runs after the font step on `ui/dialog/dropdown_dialog.bin` (default and theme1; no style file):
`label_volume` and `bar_dclock` 20 -> 18 px; the tile captions (`label_wifi`, `label_bt`, `label_lock`,
`label_gain`, `label_usbmode`, `label_outputway`, `label_playset`, `label_sysset`; word-wrapped)
18 -> 16 px normal, 16 -> 14 disabled/focused. The caption boxes are 71 x 40 instead of 57 x 40 (same centre,
x - 7; the tiles are 74 px apart), because `Bluetooth` is 60 px at 16 and AWTK broke it as "Bluetoot/h" and
"Playbac/k Setting". The tool now also refuses a Latin word wider than the box in English or Chinese. Nothing else
moves; alignment stays centred. Measured with
the text model: `100` at 18 px is 30 px (the stock box), so the font step's widening is undone (label
back to 30 px, spacing 4, the row still ends where it did); `12:59 PM` is 72 px of 90; every English and
Chinese caption fits its box without a mid-word break (the tool refuses otherwise). 22 captions in other languages (long Russian, Ukrainian, Polish, Italian, Spanish, German words in
a 57 px tile) still overflow, as clipped in stock.
**Tile art:** every tile image is one 50x50 ring style, 2 px ring, 28 px glyph: off `#777777` ring +
glyph (`drop_wifi`, `bt`, `keylock`, `eq`, `lowgain`, `po`, `playset`, `sysset`), on a filled white disc +
`#141414` glyph (the `*open` images, `highgain`, `lo`, `usbaudio`, `usbdac`, `usbstorage`, the pressed
`playsetdown`/`syssetdown`), disabled `#444444` (`lowgaindisable`, `highgaindisable`). Gain uses custom
2-/5-bar glyphs, Output the text "PO"/"LO" in Inter Medium 20 px. White disc was chosen over a white ring
(only a brightness step from the grey ring; the disc is what stock does with its orange fill).

### Lock screen (`tools/mod_lockscreen.py`)

`ui/screensaver_page.bin` (fullscreen 320x480), page theme `styles/screensaver_page.bin`, the three
`screens_*` battery images, `screens_rightslide.png` (default + theme1), and four words of `demo`.
What the app touches by name: `img_screensaver` (wallpaper), `view_timeinfo` (shown/hidden by the "show
time" setting), `app_gesture` (swipe), `btn_play`, `btn_next`, `img_battery` (image set to
`screens_battery`/`screens_charge`/`screens_lowbattery`, refresh `0x53f520`, names at
`0x53f5f0..0x53f694` only), `pgbar_battery`, `view_bottomview` (hidden **and disabled** when nothing is
queued, `0x53f8d4..0x53f8f4`), `view_scrlabel_title/artist`, `view_img_icon`. Nothing looks up
`dclock_time`/`dclock_date`. Every property is set absolutely, so the layout does not depend on earlier
edits; applying it twice is refused. Digit_clock format tokens (demo's formatter): `Y YY M MM MMM D DD`
(MMM English only, September `Sept`), `w`, `W` (full English weekday; Chinese UI `星期日..`), `h hh H HH`
(HH = 01..12), `m mm s ss`, `T`, `TT` (minute + " AM"/" PM"); the lock clock is always `hh:mm`
24 h whatever the setting (the 12/24 h setting only reformats the status bar clock).

Layout, top to bottom (window y): date `W, MMM D` 20 px, ink top 12 (box from `text_box`); the 68 px
`hh:mm` clock centred (fitted to the widest digit, 159 px wide in Inter); a **translucent card** at
16,108 288x334 (`#000000A6`, radius 18) holding the **square 264x264 cover** at 12,12 (no mask), title
(20 px white) and artist (16 px `#DDDDDD`) at 12,282 / 12,306 (164 wide), play and next at 180,278 /
228,278 (48x56, off-white `np_*` glyphs via the page theme's `btn_imgplay1/pause1_style`); the swipe hint
`img_slide` 31x14 (65 %) at 144,452; a small gauge on the date line at 274,12 (34x12 `LOCK` art; fill
`pgbar_battery` 286,15 16x6). With nothing queued the card is the hidden widget's own background, so
the page is date, clock and gauge on the wallpaper and the whole screen swipes. theme1 keeps its own
page theme (orange play/pause); `screens_rightslide` is replaced in both themes (premultiplied Lanczos).
The stock battery props are restored on `pgbar_battery` (no text readout).

- **Translucency works.** `bg_color` with alpha: `widget_fill_rect` (`0x66b170`) reads `bg_color` and
  `round_radius` and calls `canvas_fill_rect`, or `canvas_fill_rounded_rect_gradient_ex` (the
  `0x64d028` code) with a radius; the low-level fill dispatches per pixel format (`soft_fill_rect`
  `0x681440`, e.g. `0x6cfc84` sends alpha >= 0xf9 to a plain fill and less to a per-pixel blend).
  `test/awtk_fill.py` runs demo's own code on a bgr565 framebuffer: inside pixels are the blend within
  one 565 step, outside untouched, anti-aliased edge, no seams. AWTK repaints a dirty region from the
  window down, so a scrolling title or a clock tick re-blends over fresh wallpaper and never stacks.
- **Why the cover is square.** A corner mask paints one fixed colour, wrong over a translucent card on
  any wallpaper; image clipping does not exist (the image paint `0x62d494` is `widget_paint_helper`
  plus `canvas_draw_image_ex` into the widget rect, canvas clip is a rectangle, `round_radius` rounds
  only the background; only `draw_type icon` can transform), so rounding the picture would need payload
  code. The card itself is rounded and the square cover sits 12 px inside, clear of the arcs.
  Contrast over the worst wallpaper (pure white): card (89,89,89), white title 7.0:1, `#DDDDDD` artist 5.2:1.
- **Touch.** `app_gesture` is the parent of the whole page; its `on_event` (`0x5219e0`, vtable
  `0x975654`) records the down point, grabs and compares on move and up. `view_img_icon` is
  insensitive, so a touch on the cover, the card or its text lands on `view_bottomview` (a view with no
  handler) and a swipe unlocks; play/next are 48x56 and hit at their centre; `check_touch` verifies this.
- **The cover size is a demo constant.** demo writes `/tmp/coverpic.jpg` / `/tmp/externpic.jpg` with
  `toolsGetAlbumCover` / `toolsGetExternCover(track, dst, w, h)` in `parseplaycover_thd` (`0x4ded84`):
  fitted inside w x h, aspect kept, never upscaled, JPEG q90, per new track (the thread polls a start
  flag every 100 ms and skips an unchanged path). The four `addiu a3/a2, zero, 0xfe` at `0x4df1dc`,
  `0x4df1e0`, `0x4df21c`, `0x4df220` become `0x108` (264); `patch_cover_src` pins the 23 stock words
  `0x4df1d4..0x4df22c` and the GOT slots (`0x9ff74c` -> `0x5eaee0`, `0x9ff750` -> `0x5eafec`) and refuses
  otherwise. AWTK draws a smaller picture at the widget size by nearest neighbour, hence the 1:1 264 (the lock
  card's cover and Now Playing's `img_playcover` are both 264: `mod_nowplaying` asserts the sizes agree).
  Cost: 1.08x output pixels (about 209 KB instead of 194 KB RGB while encoding). Other readers of the
  files (resampled by nearest neighbour, as before): `bigcover_page` (320), the Home strip (66), theme1's
  Now Playing (254), the remote-control replies (check
  `stat().st_size < 0x16801` = 92,161 bytes; 264 px files are about 1.08x the 254 ones; a larger file means the phone shows no cover). Unchanged: `.downpic` art
  (`cp -f`), DLNA/AirPlay 270 (`0x10e`), HiFi/Tidal 254 (`0x4df348`, `0x4df424`). Cover source types
  (loader `0x53f9b4`, global `0x97cad8`): 2 = `/tmp/coverpic.jpg`, 3 and 5 = `/tmp/externpic.jpg`, 4 =
  `random_cover0..7` (320x320 PNG), 6/7 = `/tmp/hifi_album.jpg` / `/tmp/album_tidal.jpg`, else
  `defaultcover` (a 66x66 placeholder blown up, blocky; left alone because other pages use it).
- **Not possible asset-only:** the cover instead of the wallpaper (`img_screensaver` gets its image once,
  in the init visitor).

### Wallpaper (`tools/mod_wallpaper.py`, `tools/wallpaper_prepare.py`)

With no custom wallpaper `get_screensaver_image` (`0x4d7524`) and `config_init` keep the resource name
`screensaver_default` as `SCREENSAVERPATH`; a chosen picture is `file://` plus its path. Only the
resource changes: `images/xx/screensaver_default.png` (320x480; `xx` is the only set that has it,
theme1 uses it; `screensaver_default1.png`, 640x480, is unreferenced and stays) becomes Van Gogh's *The
Starry Night* (public domain; Google Art Project scan from Wikimedia Commons, SHA-256 `dbca2f16...`,
`wallpaper_prepare.py --fetch DIR` verifies before anything decodes it; attribution in `NOTICE`): a 2:3
crop (full height, 1013 px from x 250: the cypress and the large swirl), Lanczos to 320x480, brightness
x 0.8 so the card, white clock and `#DDDDDD` artist keep contrast, an 8-bit palette PNG (256 colours,
no dithering), 134,313 bytes, SHA-256 `c824ad7a...`. demo's loader is stb_image, which expands palette
PNGs. The step pins the stock file's SHA-256 (`92e7162b...`) and the asset's.

### Polish (`tools/mod_polish.py`)

- navbar title size 22 -> 20 px (`navbar_label_white`, `navbar_centerlabel_white`, all states, both
  themes; `leftlabel`/`rightlabel` were 20); box (y 14, h 22) and middle alignment unchanged;
  `TITLE_NEW` in the tool.
- the pod pages' `label_title` is the stock 200 px wide (248 would run under the bars icon), so a
  long artist name on the Artists Cover Flow is cut where every stock title is. The Home instance of the
  menu hides its whole navbar at run time (below); the menu the grid icon opens keeps it.
- With the grid hidden by the payload (`docs/architecture.md` section 9) the window under the menu is plain black, so no stock grid flashes at boot or on Back.
- **Consistency audit, every item decided** (the pull-down and the toggle / slider art, stock and release: `controls()` in the release sheet):
  - secondary greys: *applied*. The secondary text grey is `#AAAAAA` (Home artist line, Now Playing times, artist
    and album lines, album page year line); `#8C8C8C` stays as the muted partner / pressed glyph grey. Now Playing's
    `#CCCCCC` / `#BBBBBB` and the album page's `#9C9C9C` became `#AAAAAA`. *Rejected:* the lock screen's `#DDDDDD`
    artist line (it sits on a wallpaper, not on black) and the queue's stock muted rows (derived from the stock style).
  - pressed colours: *applied*. Pressed surfaces are `#333333` (rows, keys, the album page's buttons, the queue
    drawer's bottom button). `#3A3A3A` stays as the edge colour (hairline borders,
    the index letter), `#555555` is the pressed disc and the inactive dot.
  - disc greys (`#777777` / `#555555` / `#666666` / `#444444`): *rejected*, each has one job (disc, pressed disc,
    unlit glyph, disabled tile).
  - glyph stroke scaling (Home discs 3.2 px, 40 px discs 2.2 px, tiles 2.3 px, status 1.5 px): *rejected*, the
    strokes are 2 px on Tabler's 24 grid scaled to the glyph size, so the weight on screen is the same ratio.
  - font size ladder (22/20 titles, 21 rows, 18 second lines, 16 captions, 15/16 meta), row heights (52, 60/64,
    56, 50, 44) and margins 12 vs 16: *rejected*, they are code-built geometry (`docs/architecture.md`) or stock
    dialogs; changing one needs a patch and moves hit targets.
  - theme1's stock pull-down art: *rejected*, theme1 stays stock on purpose.

## 8. M1 Pod page layout (`tools/pod_ui.py`)

The release sheet: Home page 3 with the M1 Pod icon in its free slot, the menu as the Home instance (no top bar: the
Now Playing row replaces the bars icon, the list starts at y 10 and ends at y 440 (`HOME_PAD`, a little air above the first and below the last row; it scrolls to the last row) and the Settings page it opens.
The menu opened from the grid icon is the same page with its navbar (Back, "M1 Pod", the bars icon).

Each page is a window with the stock navbar (50 px: `label_title` x 36 y 14 200x22 after the polish step (248 in `pod_ui.py`), `navbar_label_white`,
Back `btn_return` 0,0 80x50, Now Playing `btn_backtoplayer` 260,0 60x50) over a stock-structured
list: `list_view` (`default_item_height` 52, black in every state) > `scroll_view` (310 wide with the
scroll bar, speeds scaled) + `scroll_bar_m` (10 px, max 1000, only when rows overflow 400 px), 52 px
rows built like stock's scrolling rows (`list_item` `list_item_style` holding an `hscroll_label`
`srlabel_leftwhite21_style`, `only_parent_focus`, ellipses, text x 24 -> 64 with the icon; the
`right_arrow` image for rows that navigate, not for Now Playing, Shuffle rows or the switch rows).
**The menu is customisable (`patch/menu.c`).** The asset holds a row for each of nine items in the default
order (Now Playing, Cover Flow, Albums, Artists, Songs, Playlists, Shuffle, Genres, Folders; the item id is the row
index) followed by Extras and Settings; at open the payload hides the rows the saved list leaves out (`visible=false` and
`sensitive=false`, parked at y 0), moves the shown ones to y = position x 52 and sets the list's `virtual_h` and offset
(the Artists list does the same for its rows), so the scrolling height, the hit test, the stock press visuals and the scroll
bar follow the shown rows. Default: the first seven show (Genres and Folders are in Extras); 9 shown rows are 468 px, so the
menu scrolls (400 px visible with the navbar, 450 px on the Home instance); Extras and Settings always show, last. The saved list
is `/mnt/data/m1pod-menu`, the shown item ids in order, one digit each (`0123456` is the default; see `docs/architecture.md`).
The **Settings** page (`m1pod_settings`, 6 rows, fits without a bar): Main Menu (opens the customise page), Cover Flow
landscape and Start in M1 Pod (rows with the stock on/off switch image, `sset_on` / `sset_off` 57 x 28 at x 251 as the stock
Power and Display pages; the row's tap flips it and the image follows), Playback (the stock Play settings page), System Settings (kept: it reads as the pair of Playback), Shanling Home. **Settings > Main Menu**
(`m1pod_mainmenu`, nine rows, the stock list): a row per item with the switch (the whole row is the target) and, on the shown
items but the first, an up arrow (a stock button with the stock chevron-up art, `expansion_2`, 50 px, left of the switch) that
moves the item one place up; the shown items come first in menu order, the hidden ones below them in the default order, and a
switch shows an item at the end of the menu. Touch reordering by arrows rather than drag-to-reorder: the stock list drags
to scroll, and a press-and-drag reorder needs custom gesture code on a page that must always work; an arrow is a stock
button, a 50 x 52 px target, and one tap is one saved step. Changes are saved at once and the menu re-arranges itself when it is
in front again. The Extras page (`m1pod_extras`, the same machinery, 18 rows: a row for every menu item, which the payload
shows (at the top, in the default order) only for the items the menu hides, then the stock Home tiles; icons as the Home grid's) lists the stock Home tiles the menu does not repeat, each opened through the Home dispatcher: Favorites, Recently Added, Recently Played, Most Played, Composers, Hi-Res, Update Library, Tidal, CD Ripper (ids 10, 13, 12, 11, 8, 9, 2, 1, 15; Extras itself `dots`; HiFi, id 0, exists only in Simplified Chinese and is left out). The Artists page has its Artist / Album Artist switch in the navbar (`btn_artisttype`, the toggle slot below): the title reads "Artists" or "Album Artists" and the glyph is the other mode's (Tabler `microphone-2` for Artist, `user-star` for Album Artist, 24 px white, pressed `#777777`); the list starts right under the navbar. Names `pod_row0..N`, `pod_listview`, `pod_scrollview`, `scroll_bar_m`.
Everything the page hides starts `visible=false` and `sensitive=false` (`label_status`, `btn_cancel`).
Cover Flow landscape (chosen by Settings > Cover Flow > Landscape; the release sheet's last panel, 480 x 320 as seen): with the
switch on the page opens as a 400 x 320 view in the 320 x 400 body under the navbar (the navbar has no rotate button and its
title has the whole width; the setting is read when the page opens)
landscape view, the content turned 90 degrees clockwise on the screen (the player held turned counter-clockwise): the
carousel along the long side with the same 168 px covers as portrait (no zoom) and more of the neighbours, the album
(22 px white) and artist (18 px grey) captions centred under the reflections (long names cut with an ellipsis, no
scrolling). The status bar and the navbar stay as they are, a portrait strip on the left as the player is held: Back and
Now Playing work in both presentations, and nothing is drawn over the covers.
The choice is remembered like the Albums view's. Details: `docs/architecture.md` section 4.
Cover Flow's page: `view_covers` 0,89 320x276; captions `label_album` 16,318 288x34
(22 px) and `label_artist` 16,352 288x28 (18 px) as scrolling `hscroll_label`s; block centred in the
400 px under the navbar (art top at y 120, 70 px above it and below the artist line); a progress
`label_status` 10,210 and `btn_cancel` 100,260 120x46 for the first-run build. These must match the
`CF_*` constants in `patch/offsets.inc`. (The page has no track list: an album opens the stock album
page, section 7.)

### The Albums page (`ui/m1pod_albums.bin`, `docs/architecture.md` section 5a)

(the two Albums panels of `docs/release-preview.png`, grid and list mode with row 2 pressed: `PI.albums_grid` / `PI.albums_list` in `tools/preview_icons.py`, sample covers.)
The Albums row opens this page in the mode used last (first use: the grid, `ALBUMS_DEFAULT_GRID`); the stock Albums list is not part of it
(it stays under Shanling Home, unmodified).
The grid mode is the standard navbar over one 320x400 `view_grid`: three 92 px covers a row, 12 px between them and 10 px
margins, a 16 px white one-line title under each cover (cut with an ellipsis at the cover's width, left-aligned like the lists'
titles), 12 px between rows, the first row 12 px from the navbar and the last 12 px from the bottom; no scroll bar (the content
follows the finger and coasts). Covers are the Cover Flow cache reduced with an area average; an album without a cached cover
shows the stock disc on `#2B2B2B` (as Cover Flow's placeholder), still with its title. Greys and fonts are the other pages':
`#000000` background, `#FFFFFF` text, `img_btn_style` glyph buttons.
The list mode is the library rows' look on the same view: 64 px rows on black, a 52 px cover at (4, 4) (the same cache, box-reduced to 52; the
same disc as placeholder), the album in 21 px `#FFFFFF` and the artist under it in 18 px `#AAAAAA`, both from x 60 to a 12 px right margin and cut
with an ellipsis there (no chevron: a tap opens the album, as on the grid), a 1 px `#222222` hairline closing each row, and the row under the finger
filled `#333333` (the stock pressed row) until the release; a drag past 12 px cancels it. Scrolling, coasting and the end stops are the grid's. A text
that is not wholly inside the view is not drawn, so a row cut by the navbar or the bottom edge shows its cover and hairline first.
The toggle is a 24 px glyph in a 46x50 button at `NAV_VIEW_X` 214..260, flush left of Now Playing (260..320), the slot every Pod page uses (Albums,
Artists, Cover Flow's landscape switch); the title label ends at its left edge. It switches the mode in place (no window opens, nothing flashes), swaps its
glyph (`list` on the grid, `grid` / `layout-grid` on the list) and keeps the first album in view. Pressed is `#777777` like the other navbar glyphs.

### Settings slide safety audit (static, on stock `demo`)

A close animation is dangerous where code pops windows in a loop expecting the stack to change
synchronously. `navigator_back` (`0x4d20dc`) -> `window_manager_back` (`0x677d2c`) ->
`EVT_REQUEST_CLOSE_WINDOW` -> `window_close` -> `close_window` (`0x6927cc`): a window not yet `OPENED`
gets an idle retry; while an animation runs `pending_close_window` takes one slot (`0x692960`); with a
hint the window stays in the list, visible, until the animation ends in the main loop (`0x691a24`), so
`window_manager_get_top_window` (`0x6775c4`) keeps returning it for 200 ms and a synchronous `while
(top != X) navigator_back();` would spin (UI hang, watchdog reboot). Input is dropped while animating
(`0x68ff64`); `window_manager_close_window_force` (`0x691cd8`) finishes an animation synchronously
(what q2-pod's `navigator_close` fix uses). The only loops that test the stack: Album detail "play from
here" (handler `0x52569c`, loop `0x525908-0x5259d8`) and the jump list (`0x538b7c`, loop
`0x538ce4-0x538db4`), both stopping at the first `playing_page` or `home_page`, opened only from library
pages, the Now Playing "more" dialog, the Home dispatcher and search -- never from the settings code
(`0x49f000-0x4b0000`); a library page can sit over a settings window only with a `playing_page` between
them. `window_manager_close_all` (`0x678b0c`) only runs at exit. Go-home (`0x677ea0`, idle callback
`0x6777c8`) force-closes the windows and animates only the top one. Decision: the slides stay on all 34
windows; the evidence is a CFG reachability search (computed jumps treated as exits, wrappers followed
three levels), not a device test; `--no-anim` is gone, so a stuck page needs a code change in
`mod_boot.apply_anim`. Behaviour differences without hanging: the folder-scan dialog on the
specified-folder page opens ~200 ms late after Back; two closes or opens within one slide share a
pending slot; the pull-down to settings slides in while the finger is down.

## 8a. Localisation

All text M1 Pod adds follows Settings > Language (mechanism: `docs/architecture.md` section 8b). Assets carry `tr_text = key`,
the payload sets labels with `widget_set_tr_text`; the 13 languages of the language menu are translated by us
(`tools/pod_i18n.py`), terms matching the stock ones (library, artist, shuffle). Widths: every row label (21 px, 187-212 px wide,
137 px on the Main Menu page with its up arrow and switch), page title (20 px, 178-248 px), message-box line (20 px, 260 px;
it scrolls if longer), album button (110 px), count line (15 px, 154 px) and Cover Flow status (20 px, 300 px, with a four digit
progress count) is measured in the shipped font for every language by `test/pod/i18n.py`; strings that did not fit were reworded
(`Cover Flow landscape` in Italian, Russian and Ukrainian is `Cover Flow orizz.` / `гориз.`; the German Now Playing is `Jetzt läuft`,
French `En lecture`, Polish `Teraz gra` for the 127 px Main Menu rows; Russian Recently Played / Most Played `Недавно слушали` / `Часто слушаемые`;
the album page's Play all is the short `Abspielen`, `Reproducir`, `Riproduci`, `Odtwórz`, `Слушать`, `Відтворити`). Previews:
`tools/preview_locales.py WORKDIR [TABLE ...]` draws the menu, Extras, Settings, Shuffle and Main Menu pages in other languages
into `out/preview/locale-<table>.png`.

## 9. Device checks for the looks

Boot splash upright (and after a 180° rotation); no text hole, tofu or jitter in the new font at
16/18/20/21 px; digits and clocks do not jitter; CJK, Cyrillic, Vietnamese, Thai titles; curly quotes
proper; status bar clear of Bluetooth in 12 h mode; settings rows black with hairlines and grey discs,
slides in and out; lists and Search as described; Now Playing as in section 4; lock screen
card translucent without notches, 264 px cover sharp, gauge small, hint small, touch rules; pull-down
tiles rings, captions fit; Home menu without grid flash, title or Back; theme1 returns the stock look.
Albums page (not yet seen on the device): the grid as before (covers sharp and aligned in three columns, titles one line with the ellipsis, scrolling
follows the finger and coasts, a tap opens the album page, Back returns to the same place); the toggle switches to the list and back in place, at the same first
album, without a flash, and the Albums row then opens the last mode (also after a reboot); list rows: 52 px cover, album, artist, hairline, pressed `#333333`
under the finger only, a long title or artist ends in an ellipsis before the right margin; an album without a cached cover shows the disc in both modes.
Fallback: `tools/build.py --restore`.
