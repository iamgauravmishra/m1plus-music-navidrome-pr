# UI: the looks of the release

Everything here is asset-only (no code) except where it says demo words change; the payload side is
in `docs/architecture.md`. The steps run in the order of `tools/build.py` (battery, font, [payload],
theme, lists, nowplaying, boot, rows, pulldown, lockscreen, wallpaper, icons, polish) on one tree; each
step pins the stock bytes it replaces by SHA-256, keeps every widget name and refuses to apply twice.
Style is q2-pod's Minimal / iPod (MIT, `NOTICE`) fitted to the 320x480 portrait touchscreen.

![the release](release-preview.png)
`docs/release-preview.png` (`tools/preview.py WORKDIR OUT.png [HOME_MENU.png]`): Home pages 1 and 3 (the
M1 Pod icon), the M1 Pod menu as Home (no top bar), the Settings and Shuffle pages, the album page, an artist's Cover Flow, the lock screen (playing; idle on the charger) and the
battery at 8x. The other looks: `docs/looks-preview.png` (`tools/preview_all.py WORKDIR OUT.png`: boot
splash, Home, Settings, Songs, Now Playing, the M1 Pod menu). All are approximate PIL mock-ups drawn
from the built tree (not AWTK), text rasterised from the tree's own `default.ttf` the stb_truetype way
(`tools/preview_font.py`, `tools/stb_raster.py`), sample data.

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
| Home page dots | `#EEEEEE` / `#555555` | `#FFFFFF` / `#666666` |

Edits are pinned (file SHA-256, per edit the old value and the state count, `STYLE_EDITS`):
`list_item_style`, `list_item_notpress_style`, `list_itemsort_style`, `btn_tablerow_style` (bg black,
pressed `#333333`, bottom hairline), `kb_btn1/2_style` pressed, the gold label styles
(`srlabel_item_gold18/20`, `label_centergold22`, `text_gold22`, lyric and tab styles: accent -> white
with the partner style muted grey so a selection still reads). Kept: red error text, the green/red
battery states, the red `icon_playing` disc, the orange on/off toggles, and every AWTK light default
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

### Now Playing (`tools/mod_nowplaying.py`)

q2-pod's iPod Now Playing fitted to 320x450 (`docs/nowplaying-preview.png`: before, art, lyrics, info):
window bg `#000000`; **top row** (44 px): Back 52x44 (kept, no hardware Return key), `label_index` centred
over the rest (16 px `#AAAAAA`), the heart `btn_fav` 52x44 (x 216, Tabler heart, as in V2.1jA) and More 52x44
(x 268, Tabler dots). **Page 1** (slide page, y 44..342): art 216x216 at 52,2 (rounded by an insensitive
`np_artmask`, radius 10), title 22 px white at y 224, artist 18 px `#CCCCCC` at 250, album 18 px `#BBBBBB` at 272
(left aligned on the art's edges, long lines scroll); nothing at the foot (V2.1kC had the mode and the heart
there, a Hi-Res tag and a 192 px art; V2.1kE puts both buttons back and keeps the round-2 glyphs). The play
mode is the transport row's first slot (x 4, 56 wide). **No Hi-Res tag:** demo only calls `widget_set_visible`
on `img_hr` (`0x53bfb4..0x53bff8`), so the widget stays (the app looks it up) at 0x0, insensitive and hidden:
whatever the app toggles, nothing paints or takes touches. **Progress:** the
stock 30 px seek target (`slider_play`, 12,342,296x30, the A-B markers depend on it) with q2-pod's 4 px
line, track `#1C1C1C`, fill `#EEEEEC`, no thumb (`icon` empty); times 14 px `#AAAAAA` below, page dots
between; the total stays on the right (the label is filled with the length once per track; remaining time
needs code). The **index reads "3/12"**: the format `%d/%d` is shared by 11 call sites and its string has
only 3 spare bytes, so "3 of 12" needs a code patch (not done). A 58 px transport row (mode 4/56, prev 64/60, play
124/72, next 196/60, queue 260/56) with the `np_*` glyphs (16 images from `mod_icons.py`, off-white, pressed `#8C8C8C`; plus `np_artmask`): prev / play /
pause / next are the solid PIL-drawn shapes of V2.1jA (a 24x28 triangle, two 7x26 bars, two 13x16 triangle pairs;
V2.1kC's Tabler filled ones read worse on the device), the rest Tabler: shuffle / repeat / repeat-once / repeat-off (in
order, dim) / heart filled and outline / dots / playlist, 26 px ink; lyrics and info
pages restyled. `scrlabel_title`,
`scrlabel_artist` and `label_album` change parent, safe because demo looks every widget on this page
up recursively. `styles/playing_page.bin` (window theme searched before `default.bin`): the mode and
favourite styles point at `np_*` icons (the app swaps them with `widget_use_style`), page-local
`btn_imgplay/pause_style` (the lock screen and other pages keep the stock ones), lyric styles `#8C8C8C`
/ `#EEEEEC`. `image_wait` is insensitive (it covered the play button's centre).

**The album line.** Stock has no album-only widget: demo fills `label_album` with `"%s:%s"`
(`getFormatString("album")` + album; format at `0x8be13c`: a plain ASCII colon). The mod puts the label
in a non-scrolling `scroll_view` (`scroll_np_album`, 216x22, a scroll_view clips, a plain view does
not) and moves it left until `Album:` lies left of the clip edge. `album_clip` computes the shift with
the text model: the prefix's AWTK width (including +1 px per glyph) plus 1 px of safety, from the
tree's font and the label's `margin_left`; the colon's ink must end left of the edge and the album's
first letter keep all its ink (printable ASCII and Latin-1 letters overhang at most 1 px; a likely
letter that would lose ink prints a warning). In the Inter font the label sits at x -50 (`Album:` is
49 px). Other UI languages: the prefix differs (`ALBUM_PREFIX` is the English word; Spanish `Álbum:` is
the same width, Russian/Ukrainian `Альбом:` 66 px and Japanese 69 px leave the end of the prefix
showing, Chinese/Korean cut the album's first ~14 px).

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
custom SVGs (`assets/icons/custom/`) and the generated PNGs (`assets/icons/tabler/png/`, 132 files);
the build only copies PNGs (no rasteriser, deterministic); `--generate` re-renders them with
`rsvg-convert` and Pillow at the exact stock size, `--pins` writes the stock SHA-256 pins
(`tools/mod_icons_pins.txt`), `--check [WORKDIR]` verifies pins, size and mode.

| area | files | design |
|---|---|---|
| settings icons | 42 of the 46 (40x40) | white glyph (26 px, stroke 2) on the `#777777` disc |
| Home grid | 17 + 17 `_down` (66x66) | white glyph (38 px) on `#777777` (`#555555` pressed); HiFi (zh_CN) a store; Tidal keeps its stock image (`tidal`, `tidal_down`) |
| M1 Pod Home icon | added `m1pod.png`, `m1pod_down.png` (66x66) | the click-wheel glyph on the same disc; the style `home_m1pod_style` (a copy of `home_tidal_style` pointing at them) is added to `styles/home_page.bin` in the stock sort order; the widget is built at run time (`docs/architecture.md` section 9) |
| pull-down tiles | 17 (50x50, 20x20 sun icons) | one ring style, section 7 |
| status bar | 15 (play, pause, volume 0-4, Wi-Fi 0-4, Bluetooth off/on, digital out) | white, unlit Wi-Fi arcs `#666666`; 1.5 px strokes at 14-16 px, 2 px at 20 |
| list placeholders | 6 discs (40x40), 3 "no cover" tiles (60/90/100) | glyph on the `#777777` disc / the tile colour |
| M1 Pod rows | 14 added `pod_ic_*.png` (40x40) | menu, Shuffle page and Settings page rows; disc x 12, title x 64, row height and chevrons unchanged, image insensitive |

Rule: an icon has a real Tabler glyph, or keeps its stock image (when decent), or is drawn in Tabler's
style (24 grid, 2 px stroke, round caps; `assets/icons/custom/`). Custom: `click-wheel` (the M1 Pod
Home icon), `guitar` (Genres), `badge-hr` (Hi-Res), `dac` (USB DAC), `volume-3waves`
(Tabler stops at two), `gain-low`/`gain-high` (tiles). Stock kept: DAC and DSD output (text on the grey
disc), ReplayGain, brand art and text badges (codec badges, SyncLink, A-B), theme1 (own image files),
the Chinese-only Home ids. Row glyphs: Now Playing `player-play`, Cover Flow `carousel-horizontal`,
Shuffle `arrows-shuffle`, Songs `music`, Albums `vinyl`, Artists `microphone-2`, Genres `guitar`, Folders
`folder`, Playlists `playlist`, Settings `settings`; the Settings page: System Settings `settings`, Play
Settings `adjustments`, Shanling Home `layout-grid`, Start in `home`; the Shuffle page uses the song,
album and folder glyphs. `ui/m1pod_menu.bin`, `m1pod_shuffle.bin` and `m1pod_settings.bin` get the child image (title x 24 -> 64). `icons` runs late so it overrides the theme step's grey discs.

### Icon audit, round 2 (`tools/audit_images.py`, `docs/icons2-preview.png`)

`audit_images.py [STOCK [TREE]]` lists every `images/xx` file referenced by a `ui/**/*.bin` property, a style
file or a name string in `demo` (560 files), and with TREE only those still byte-identical to stock. Before
round 2, 429 were stock; round 2 changed 110 stock files plus the 16 `np_*` glyphs. Result for the 560:

| class | files | action |
|---|---|---|
| Tabler (rounds 1+2) | 241 (131 + 110) | glyph in the stock size; round 2: navbar add / cancel / delete / multi-select / sort / search / back / chevron / more / settings (+ pressed `#777777`), selection circles and squares, expanders, queue-dialog modes, dialog actions (rename, scan, delete, add network, eye), Now Playing more-dialog and batch-add icons, Bluetooth/USB page transport |
| Tabler on the `#777777` disc | 24 of those | Folders rows (16 audio formats share `file-music`, SD, USB), Playlists page (New, Import, Export), CD track dialog (custom `guitar`, microphone, calendar) |
| custom SVG | 2 uses | `guitar` (Genres, CD genre); round 1 customs unchanged |
| Tabler `multiplier-1x` | 1 | `p_multiple` (28x28, V2.1kE): the icon of the playback-speed row in the Now Playing more dialog (`playmore_dialog`, beside the 1.0X / 1.25X / 1.5X / 2.0X badges; it was `list-check`). The Play Settings list has no speed row, so there is no 40 px disc icon for it |
| Lucide (ISC) | 2 | `back_to_player` / `back_to_player_down` (V2.1kE): the navbar's go-to-Now-Playing icon, Lucide `audio-lines` (`assets/icons/lucide/`, lucide-static 1.61.0, tarball SHA-256 `62773cd2...ba75f1`, licence beside it, `NOTICE`), 23x24 like search, 2 px stroke, pressed `#777777`. The button is a static `img_btn_style` image pair (names without digits, no frame swap in `demo`: the only other `playing_*` names are the loading spinner `playing_wait_1..12` and the list's `icon_playing` disc) |
| stock recoloured white | 9 | equaliser preset instruments (`eq_*`), the line art is kept |
| drawn (Inter text / Tabler glyph) | 14 | speed badges (8), Play all pills (4: off-white pill, dark text), secured Wi-Fi rows (4: fan + lock) |
| kept, decent or not an icon | 317 | 100 keyboard keys, 70 backgrounds / sliders / scroll arrows / unused check and radio art, 69 brand, codec and text badges, toggles (orange on/off kept), protocol art, the red `icon_playing` disc, 55 Tidal / HiFi store / purchase / guide art (Chinese or account only), 14 CD ripper art, 11 superseded by `np_*` or the brightness suns |

The Folders page has no "up" row image (Back goes up); Favourites and every playlist use `icon_playlist`
(round 1); Genres, Composers, Artists, Albums and search rows use the round-1 `icon_*` discs. `mod_icons.py`
`GLYPHS`, `DISCS`, `RECOLOUR`, `SPEEDS`, `PLAYALL`, `WIFI_LOCK`, `NP` are the tables; glyphs are fitted to the
stock canvas by ink size, 2 px stroke (1.5 under 22 px). Not asset-only: nothing here changes code.
![icons round 2](icons2-preview.png)
![icons](icons-preview.png)
`docs/icons-preview.png` (`tools/preview_icons.py STOCK_TREE RELEASE_TREE OUT.png`): before and after at
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
![battery](battery-unified-preview.png)
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

![the stock pages](stock-pages-preview.png)
`docs/stock-pages-preview.png` (`tools/preview_stock.py WORKDIR OUT.png`): the Albums list and the album
page it opens, Cover Flow on an artist and the same page opened by the All albums card, a playlist's
songs, the queue. Approximate mock-ups, as above.

- **One album page.** The stock `albuminfo_page` opens from Albums, Cover Flow, Artists (through Cover
  Flow) and the All albums card; the header is restyled to the design in `docs/architecture.md` section 8
  (120 px cover rendered 1:1, 21 px white title, 18 px grey artist, a 15 px "year . N tracks" line, the
  dark Play all button and a Shuffle button, 110x36 each, the cover 8 px under the navbar; `docs/album-page-preview.png`: before, after). The sizes and positions are in code (the hook
  moves the stock widgets); the look is the page theme `styles/albuminfo_page.bin`
  (`btn_albumbtn_style`, `srlabel_meta15_style`, `tools/mod_ipodrows.py`), new names, so the stock
  `btn_imgplayall_style` (an orange pill image) remains for a header the hook leaves alone. From Cover Flow the cover appears a moment
  after the page opens, as from the Albums list (the cover thread renders it; `docs/architecture.md` section 8). The track
  rows are the q2-pod rows. The custom album page the Cover Flow page had until V2.1jA is gone.
- **A playlist's songs** are the Songs page (`allmusic_page`, class `0xff13`, the playlist's name as the
  navbar title): the same 64 px rows and navbar as every library list. The stock page has no header and
  no Play all button, so there is nothing to restyle beyond that; a header with Play all and Shuffle would
  need a hook on that page's init.
- **The queue drawer** (`ui/dialog/playqueue_dialog.bin`, `docs/queue-preview.png`: before, after): the 240x450
  panel that slides in from the right over Now Playing (opened by name from `playerjumpinfo_page_init` `0x53b17c` and
  `0x4d126c`; `dialog_playqueue_dialog_init` `0x47a7cc`). Its rows are cloned from a template (`queue_table_row`) by the stock table code, `row_height` read
  from the file, and bound by `0x47a19c`: the song name in `scrlabel_name` with `srlabel_item_gold20_style` for the
  playing row, `srlabel_item_white_style` for the rest. The minimal theme made both white, so nothing marked the
  playing row. Now (asset and page theme `styles/playqueue_dialog.bin`, `mod_lists.py` recipe `queue` and
  `edit_playqueue`): rows 44 px (button 40, a 4 px gap), the other rows muted `#9C9C9C` 18 px, the playing row
  white 20 px; the list's own row colours; a `#3A3A3A` hairline under the 64 px play-mode header (the Tabler mode
  glyph and name the app sets) and a `#3A3A3A` left border; the bottom button in the dark button colours
  (`#1E1E1E`, pressed `#3A3A3A`, 20 px). No widget is renamed or moved except the row template's height; no code.
  Not done: a play marker image on the playing row and a count in the header (the row bind and the header are
  code), Tabler icons on the bottom button (it has none).
![queue drawer](queue-preview.png)
- **The queue** (the Now Playing list page, `playerjumpinfo_page`): the playing track's row carries the
  stock red `icon_playing` disc in place of its icon (set by the row bind `0x539244`, `is_playing` `0x4d9d64`), the rows are the
  q2-pod rows (white title, grey artist), and the navbar title (the queue's name, a `srlabel_leftwhite22_style`
  `hscroll_label` the page builds) is 20 px like every other navbar title of ours (page theme, `mod_lists.py`
  recipe `navtitle`; the other code-built library titles stay 22 px). The track count and numbers would need
  code; not done.

### Pull-down (`tools/mod_pulldown.py`, `mod_icons.py`)

Runs after the font step on `ui/dialog/dropdown_dialog.bin` (default and theme1; no style file):
`label_volume` and `bar_dclock` 20 -> 18 px; the tile captions (`label_wifi`, `label_bt`, `label_lock`,
`label_gain`, `label_usbmode`, `label_outputway`, `label_playset`, `label_sysset`; 57x40, word-wrapped)
18 -> 16 px normal, 16 -> 14 disabled/focused. No widget moves; alignment stays centred. Measured with
the text model: `100` at 18 px is 30 px (the stock box), so the font step's widening is undone (label
back to 30 px, spacing 4, the row still ends where it did); `12:59 PM` is 72 px of 90; every English and
Chinese caption fits its box (the tool refuses otherwise: `Playback Setting` was 3 lines at 18 px, 2 at
16). 22 captions in other languages (long Russian, Ukrainian, Polish, Italian, Spanish, German words in
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
8,92 304x350 (`#000000A6`, radius 18) holding the **square 280x280 cover** at 12,12 (no mask), title
(20 px white) and artist (16 px `#DDDDDD`) at 12,298 / 12,322 (180 wide), play and next at 196,294 /
244,294 (48x56, off-white `np_*` glyphs via the page theme's `btn_imgplay1/pause1_style`); the swipe hint
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
  `0x4df1e0`, `0x4df21c`, `0x4df220` become `0x118` (280); `patch_cover_src` pins the 23 stock words
  `0x4df1d4..0x4df22c` and the GOT slots (`0x9ff74c` -> `0x5eaee0`, `0x9ff750` -> `0x5eafec`) and refuses
  otherwise. AWTK draws a smaller picture at the widget size by nearest neighbour, hence the 1:1 280.
  Cost: 1.22x output pixels (about 235 KB instead of 194 KB RGB while encoding). Other readers of the
  files (resampled by nearest neighbour, as before): Now Playing's `img_playcover` (216 in the look,
  254 in theme1), `bigcover_page` (320), the Home strip (66), the remote-control replies (check
  `stat().st_size < 0x16801` = 92,161 bytes; 280 px files are 1.13-1.22x the 254 ones, the largest
  measured 43 -> 51 KB; a larger file means the phone shows no cover). Unchanged: `.downpic` art
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
- the pod pages' `label_title` is the stock 200 px wide (was 248, running under the bars icon), so a
  long artist name on the Artists Cover Flow is cut where every stock title is. The Home instance of the
  menu hides its whole navbar at run time (below); the menu the grid icon opens keeps it.
- With the grid hidden by the payload (`docs/architecture.md` section 9) the window under the menu is plain black, so no stock grid flashes at boot or on Back.
- Possible further consistency work (not done): secondary greys (`#AAAAAA`, `#8C8C8C`, `#888888`,
  `#BBBBBB`/`#CCCCCC`), disc greys (`#777777`/`#555555`/`#666666`/`#444444`), glyph stroke scaling (Home
  discs 3.2 px, 40 px discs 2.2 px, tiles 2.3 px, status 1.5 px), font size ladder (22/20 titles, 21 rows,
  18 second lines, 16 captions, 15/16 meta), row heights (52, 60/64, 56, 50, 44 in a few stock dialogs),
  margins 12 vs 16, pressed colours (`#333333` rows, `#555555` discs, `#3A3A3A` album buttons), theme1's
  stock pull-down art.

## 8. M1 Pod page layout (`tools/pod_ui.py`)

![the launcher](home-menu-preview.png)
`docs/home-menu-preview.png`: Home page 3 with the M1 Pod icon in its free slot, the menu as the Home instance (no top bar: the
Now Playing row replaces the bars icon, the list starts at y 10 and ends at y 440 (`HOME_PAD`, a little air above the first and below the last row; it scrolls to the last row) and the Settings page it opens.
The menu opened from the grid icon is the same page with its navbar (Back, "M1 Pod", the bars icon).

Each page is a window with the stock navbar (50 px: `label_title` x 36 y 14 200x22 after the polish step (248 in `pod_ui.py`), `navbar_label_white`,
Back `btn_return` 0,0 80x50, Now Playing `btn_backtoplayer` 260,0 60x50) over a stock-structured
list: `list_view` (`default_item_height` 52, black in every state) > `scroll_view` (310 wide with the
scroll bar, speeds scaled) + `scroll_bar_m` (10 px, max 1000, only when rows overflow 400 px), 52 px
rows built like stock's scrolling rows (`list_item` `list_item_style` holding an `hscroll_label`
`srlabel_leftwhite21_style`, `only_parent_focus`, ellipses, text x 24 -> 64 with the icon; the
`right_arrow` image for rows that navigate, not for Now Playing, Shuffle rows or Start in). The menu's
10 rows are 520 px, so it scrolls (400 px visible with the navbar, 450 px on the Home instance). The Settings page
(`m1pod_settings`, same machinery as the Shuffle page, 4 rows: System Settings and Play Settings open the stock pages,
Shanling Home, Start in) fits without a bar. The menu's last row, Settings, opens it. Names `pod_row0..N`, `pod_listview`, `pod_scrollview`, `scroll_bar_m`.
Everything the page hides starts `visible=false` and `sensitive=false` (`label_status`, `btn_cancel`).
Cover Flow's page: `view_covers` 0,89 320x276; captions `label_album` 16,318 288x34
(22 px) and `label_artist` 16,352 288x28 (18 px) as scrolling `hscroll_label`s; block centred in the
400 px under the navbar (art top at y 120, 70 px above it and below the artist line); a progress
`label_status` 10,210 and `btn_cancel` 100,260 120x46 for the first-run build. These must match the
`CF_*` constants in `patch/offsets.inc`. (The page has no track list: an album opens the stock album
page, section 7.)

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

## 9. Device checks for the looks

Boot splash upright (and after a 180° rotation); no text hole, tofu or jitter in the new font at
16/18/20/21 px; digits and clocks do not jitter; CJK, Cyrillic, Vietnamese, Thai titles; curly quotes
proper; status bar clear of Bluetooth in 12 h mode; settings rows black with hairlines and grey discs,
slides in and out; lists and Search as described; Now Playing's album line without `Album:`; lock screen
card translucent without notches, 280 px cover sharp, gauge small, hint small, touch rules; pull-down
tiles rings, captions fit; Home menu without grid flash, title or Back; theme1 returns the stock look.
Fallback: `tools/build.py --restore`.
