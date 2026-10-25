# Look: iPod-style Now Playing (`look-nowplaying`, V2.1fN)

An asset-only restyle of the stock Now Playing page in the style of q2-pod's iPod Now Playing
([q2-pod](https://github.com/DiamondBond/q2-pod) `docs/ipod.md` "Now Playing", changelog 1.1.7, MIT;
see `NOTICE`), re-fitted from the Q2's 375x290 landscape client area to the M1 Plus's **320x450**
portrait window. No code changes: `demo`, the M1 Pod payload and every shared asset stay as they are.

```
python3 -I tools/build.py --variant look-nowplaying
  # -> out/M1Plus-V2.1fN-look-nowplaying-pod-cover-lockscreen-iconpercent-space-update.bin
venv/bin/python -I tools/mod_nowplaying.py SRC_WORKDIR OUT_WORKDIR [--album clip|full] [--album-prefix TEXT]
venv/bin/python -I tools/preview_nowplaying.py OUT.png stock=work/stock/rootfs/release/assets/default/raw \
    mod=work/mod-look-nowplaying-.../rootfs/release/assets/default/raw
venv/bin/python -I tools/preview_nowplaying.py --album-strip OUT.png "old=RAW,album_x=-45" new=RAW   # album line, 4x
```

V2.1fN is V2.1eN with the album-line fix (below, "The album line"): on the device V2.1eA showed a
colon in front of the album.

The variant is the current device build `pod-cover` (V2.1dE: lock screen + icon+percent + space + M1
Pod + Cover Flow) with `mod_nowplaying.py` run on top. Preview: `docs/look-nowplaying-preview.png`
(stock, mod, mod's info page; PIL mock-up with sample data and a synthetic cover, text laid out with
AWTK's metrics, glyphs drawn by PIL) and `docs/look-nowplaying-album.png` (the album line at 4x).

## Layout (window coordinates, 450 px under the status bar)

```
  0   [<] 3/12            HR [heart] [...]      top row: 44 px touch targets
 46   +------------------------+
      |   cover 216 x 216      |                 slide page 1: art with rounded corners,
      +------------------------+                 title 22 px white, artist 18 px #CCCCCC,
268   Title                                       album 18 px #BBBBBB, left-aligned on the
294   Artist                                      cover's edges (x 52..268); long lines scroll
316   Album
342   (=====o-------------------------)          4 px #EEEEEC fill on a #333333 track, white thumb
374   01:23          . o .           06:22       times 14 px #AAAAAA, page dots between them
392   [mode]  [<<]   [ > ]   [>>]  [queue]       58 px transport row, monochrome glyphs
450
```

A swipe on the art page replaces art, title, artist and album with the lyrics page or the info page,
as on q2-pod. The page background is black (`#000000`, the status bar's colour; stock `#141414`).

| widget | stock | mod |
|---|---|---|
| window | bg `#141414` | `#000000` |
| `app_gesture`, `view_local` | 320x438, centred (6 px top/bottom unused) | 320x450 |
| `slide_view_view` | 0,46 320x313 | 0,0 320x392 (parents the top-row and times-row widgets below; later siblings stay on top for touch) |
| `slide_view` | 254 px high at its top | 0,44 320x298 |
| `img_playcover` | 36,0 254x254 | 52,2 216x216 |
| `img_np_artmask` (new) | | 52,2 216x216 image `np_artmask`: black corners, transparent inside (radius 10); insensitive |
| `scrlabel_title` | 36,0 244x20 in the top row, 20 px centred | moved onto page 1: 52,224 216x26, 22 px white, left |
| `scrlabel_artist` | 36,22 244x18 in the top row, 18 px grey centred | page 1: 52,250 216x22, 18 px `#CCCCCC`, left |
| `label_album` | info page line "Album:..." | page 1 album line: inside `scroll_np_album` (new, 52,272 216x22, non-scrolling, insensitive) at x -52 w 268 (V2.1eN: -45), 18 px `#BBBBBB`, left |
| `label_index` ("%d/%d") | between the times | top row 52,0 128x44, 16 px `#AAAAAA`, left (as q2-pod's "3 of 12") |
| `img_hr` | 280,10 (top right) | 184,13 (left of the heart); insensitive |
| `btn_fav` | 23,252 42x32 under the art | top row 216,0 52x44; pressed icon `np_unfav_down` |
| `btn_more` | 255,254 42x32 under the art | top row 268,0 52x44, `np_more` / `np_more_down` |
| `btn_return` | 0,0 80x36 | 0,0 52x44 (same style) |
| `slider_play` | 12,342 296x30, orange `#FE7E40` on `#888888` | same geometry (the A-B markers depend on it), `#EEEEEC` on `#333333`; pressed thumb `drop_dot_down` |
| `img_repeata`, `img_repeatb` | | unchanged, insensitive (they lie over the slider) |
| `label_playtime`, `label_playlen` | 12,288 / 246,288 (above the bar), 18 px | 12,374 / 218,374 90x18 (below the bar), 14 px `#AAAAAA` |
| `slide_indicator` | 133,264 under the art, white / `#ffffff28` | 132,378 between the times, `#EEEEEC` / `#555555` |
| `view_buttons` | 0,372 320x66 | 0,392 320x58 |
| `btn_playmode`, `btn_prev`, `btn_play`, `btn_next`, `btn_queue` | x 0/58/123/203/272, w 48/65/80/59/48 | x 4/64/124/196/260, w 56/60/72/60/56, all 58 high |
| `image_wait` | 138,8 50x50 | centred on play (135,4); insensitive (it covers the play button's centre) |
| lyrics page | `view_lrc` 33,26 254x228, message at y 100 | `view_lrc` 33,8 254x282 (stock line width kept), "No lyrics" centred, `#AAAAAA` |
| info page | `label_info` orange, lines 26 px apart | `label_info` 18 px `#EEEEEC`, genre/year/size 30 px apart, location wraps below, all `#AAAAAA`, centred |
| `view_dlna` (DLNA playback) | | unchanged |

Every widget keeps its name; only `scrlabel_title`, `scrlabel_artist` (top row -> page 1) and
`label_album` (info page -> page 1) change parent, which is safe because `demo` looks every widget on
this page up with `widget_lookup(win, name, TRUE)` (recursive). The tool asserts that no name is lost.

## The page theme (`styles/playing_page.bin`)

A window loads `styles/<window name>.bin` as its own theme, and this AWTK build searches it **before**
`styles/default.bin`: the style lookup at `0x6d2f6c` calls `widget_get_window_theme(widget, &win,
&default)`, then `theme_find_style(win, ...)` and only on a miss `theme_find_style(default, ...)`. So
styles added here change this page only, and `default.bin` (owned by the theme work) is not touched.

- the play-mode and favourite styles that live here in stock (`btn_imgrandom/cycle/cycle1/order_style`,
  `btn_imgfav/unfav_style`, all five states) now point at `np_*` icons. The app switches `btn_playmode`
  and `btn_fav` between these styles with `widget_use_style`, so the states keep working;
- **new** page-local `btn_imgplay_style` / `btn_imgpause_style` (copies of the stock props, icon
  `np_play`/`np_pause`, pressed `*_down`). The app swaps `btn_play` between these two default.bin styles;
  the page copies win here, and the lock screen and other pages keep the stock orange buttons;
- **new** page-local `listitem_lyric_style` (`#8C8C8C`) and `listitem_sellyric_style` (current line,
  `#EEEEEC`; stock white / orange) for the lyric rows `demo` creates in `scroll_lrc`;
- the A-B and speed styles are unchanged.

`tools/awtk_style.py` (the shared theme-file parser, from the look-theme work; format in its header,
after q2-pod's `style_props`) parses and serializes these files; all 14 `default/raw/styles/*.bin` and the
4 theme1 files round-trip byte-exact. This mod first shipped its own copy of such a parser; since the
look-all merge it uses the shared one, and its output is byte-identical (V2.1eN `84ed09f1...`).

## Images (20 new, `images/xx/np_*.png`, 9,741 bytes)

All new names, referenced only from the two files above, so nothing shared (and no other page) changes.

| image | from |
|---|---|
| `np_play`, `np_pause`, `np_prev`, `np_next` (+ `_down`) | drawn with PIL (8x supersampled): filled triangle / bars / double triangles, `#EEEEEC`, pressed `#8C8C8C` (stock: orange outlined glyphs, `#FE7E40`) |
| `np_random`, `np_cycle`, `np_cycle1`, `np_order`, `np_fav`, `np_unfav`, `np_more`, `np_playqueue` (+ `np_unfav_down`, `np_more_down`, `np_playqueue_down`) | the stock `p_*` glyphs' alpha, recoloured to `#EEEEEC` (pressed `#8C8C8C`): q2-pod's "quiet icons" (`quiet_icon` colourises to `#eeeeee`); the red favourite heart becomes off-white |
| `np_artmask` | 216x216 black-corner mask, radius 10 (q2-pod rounds the art at runtime in its payload; here an insensitive image over the cover does it) |

## The album line

Stock has no album-only widget. `demo` fills `label_album` (in `show_player_face`'s info filler,
`0x539c40`) with `tk_snprintf(buf, 0x200, "%s:%s", getFormatString("album"), album)`: the format at
`0x8be13c` is the bytes `25 73 3a 25 73 00`, so the separator is a plain ASCII colon (0x3a, no space,
not the full-width U+FF1A). `getFormatString` is `locale_info_tr(locale_info(), key)`, and the English
`strings/en_US.bin` maps `album` to `Album` (`41 6c 62 75 6d`). A missing album gives `player_unknown`
(`Unknown`). The mod puts the label in a non-scrolling `scroll_view` (a scroll_view clips its children;
a plain AWTK view does not) and moves it left until `Album:` lies left of the clip edge.

![album line, old and new offset](look-nowplaying-album.png)

### The V2.1eA / V2.1eN bug: a colon on the device

V2.1eN and V2.1eA put the label at x -45, the sum of the six truncated advances of `Album:` at 18 px.
On the device the end of the `m` and the colon stayed visible at the left of the album line. Two
things in the way this `demo` draws text had been left out (checked in the disassembly of the stock
`demo`):

- **+1 px after every glyph.** The lcd is `lcd_mem` (from `lcd_linux_fb_create`, every variant built
  with `tk_calloc`), which sets no `draw_text` / `measure_text` (lcd offsets 0x4c / 0x50 stay NULL).
  So `canvas_draw_text` (`0x645348`) draws glyph by glyph and steps `x += glyph.advance + 1`
  (`0x6454cc..0x6454d8`), and `canvas_measure_text` (`0x644544`) adds `advance + 1` too (`0x6446c4..`;
  a glyph the font cannot give adds 4). `Album:` is therefore 45 + 6 = **51 px** wide, not 45.
- **margin_left 2.** `hscroll_label`'s paint function reads `style_get_int(style, "margin_left", 2)`
  and `"margin_right", 2` (`0x609dac`, `0x609dcc`), clips the text to the label inset by them and starts
  it at margin_left. `label_album` has no style of its own (`default`), and neither the page theme nor
  `default.bin` (stock, or the look-theme one) gives `hscroll_label` / `default` a margin, so 2 applies.

The rest of the model was right: stb_truetype with `scale = font_size / (hhea ascender - descender)` in
float32 (`stbtt_ScaleForPixelHeight`, `0x67cb9c`: `div.s` of the int font size by `ascender - descender`
read from hhea), each advance truncated (`trunc.w.s` at `0x680438` into `glyph_t.advance`), the bitmap
drawn at `pen + x0` with `x0 = floor(xMin * scale)`, `x1 = ceil(xMax * scale)` (`stbtt_GetGlyphBitmapBox`).
The label is 18 px in every state (inline). For the stock `default.ttf` (256 units/em, ascender 230,
descender -69, so 18 px means a scale of 18/299 = 0.060201):

| glyph | advance (units -> px) | pen | ink columns (from the text start) |
|---|---|---|---|
| `A` | 170 -> 10 | 0 | 0..10 |
| `l` | 56 -> 3 | 11 | 12..13 |
| `b` | 142 -> 8 | 15 | 16..22 |
| `u` | 142 -> 8 | 24 | 25..31 |
| `m` | 213 -> 12 | 33 | 34..44 |
| `:` | 71 -> 4 | 46 | 47..48 (box x0 1, x1 3: xMin 23, xMax 49) |
| album | | **51** | |

With the label at x -45 the text started at -45 + 2 = -43 in the clip: the `m`'s last stem landed on
columns 0..1, the colon on columns 4..5 (window x 56..57) and the album at pen 8. That is the "ı:"
the device showed (`docs/look-nowplaying-album.png`, top row, drawn with these metrics).

### The fix (V2.1fN, V2.1fA)

`mod_nowplaying.py` now models this text layout (`StbText`, `album_clip`; since the f-series merge
`StbText` lives in `mod_lockscreen.py` as the text model both tools share) and places the label at
**x -52** (w 268): the prefix's AWTK width 51, plus 1 px of clear space (`ALBUM_SAFETY`). The text then
starts at -50, the colon's ink ends at column -2 (column -1 stays clear), and the album's first pen
position is column 1 (window x 53; the title and artist start at 54). The safety pixel is only kept
if no likely first letter loses ink: over printable ASCII and the Latin-1 letters the widest left
overhang is 1 px (`j`, `_`, `Î`, `ï`..., x0 -1), which lands on column 0. (Rarer letters overhang 2 px
and would lose their leftmost, partly covered column: `ĵ`, Cyrillic `ј`, `Ƒ`.) Hiding the prefix always
wins: with another font whose colon ink reaches past its advance, the label moves further left, and if
that cuts a likely first letter the build prints a warning naming it (with macOS's Georgia, for
example, `j` would lose a column) instead of letting the colon back.

All of it is measured from `fonts/default.ttf` of the tree being edited and from that tree's styles, so
a font step that runs earlier (another `default.ttf`) or a theme that gives labels a margin moves the
label with it; on the stock font the result is the x -52 above. The build log prints the numbers:

```
  album prefix "Album:" at 18 px: AWTK width 51 px (advances + 1 each), margin_left 2; label at x -52 in
  scroll_np_album: prefix ink x -50..-2 (colon advance 4, box (1, 3)), album pen x 1 (safety 1 px; ...)
```

A black mask image over the prefix was considered: it would need the same width computation, would
hide the album's first letters while it scrolls, and adds an image; the clip offset stays the simplest
asset-only fix. A long album still scrolls inside the label, which only moves the prefix further left.

### Other UI languages

The prefix is the language's `album` string plus `:`. With the English offset (x -52), measured with
the stock font:

| UI language (`strings/*.bin`) | prefix | AWTK width | what shows |
|---|---|---|---|
| English, French, German (`ge_DE`), Italian, Polish (`po_PL`) | `Album:` | 51 | album only |
| Spanish (`sp_ES`) | `Álbum:` | 51 | album only (`Á` is as wide as `A`) |
| Russian, Ukrainian | `Альбом:` | 66 | the end of `м` and the colon, album 15 px further right |
| Japanese | `アルバム:` | 69 | the end of `ム` and the colon, album 18 px further right |
| Chinese (both), Korean | `专辑:` / `專輯:` / `앨범:` | 37 | the album's first ~14 px are cut |
| Thai | `อัลบั้ม:` | 46 | the album's first ~4 px are cut (stb draws Thai marks unshaped) |

`--album-prefix TEXT` measures another language's word instead (for example `--album-prefix Альбом`
gives x -67); it changes the build, not the device, so a package fits one language. `--album full`
shows the label as the app fills it (`Album:Abbey Road`).

### Device check (V2.1fA)

- English UI: the album line starts with the album's first letter, at the left edge of the title and
  artist; no colon and no sliver of `m` before it, also for an album starting with `j` or `W`, and for
  a missing album (`Unknown`)
- a long album scrolls and no part of `Album:` appears at any point of the scroll
- the title and artist lines are unchanged

## Touch

`check_touch` in the tool models this AWTK's hit test (`widget_find_target_default`, see
`docs/coverflow.md`: children from the top, first with enable and sensitive set, `visible` ignored) on
the final tree and asserts that the centre of every control (`btn_return`, `btn_fav`, `btn_more`,
`slider_play` and the five transport buttons) reaches that control, that every one is at least 44 px
wide and 44 px high (the slider: 30 px, stock), and that the cover and the album line reach the
`slide_view` (swipe). `view_dlna` is left out of the model because `playing_choiceshowpage` disables it
(`widget_set_enable`) in local playback. It caught the stock spinner `image_wait` sitting on top of
`btn_play`'s centre (no code references `image_wait` by name), hence its `sensitive=false`.

## Cost and verification

- rootfs.squashfs **+12,288 bytes** over pod-cover (53,149,696 -> 53,161,984; headroom left 2,576,384);
  uncompressed +15,085 bytes (`ui/playing_page.bin` 12,863 -> 13,606, `styles/playing_page.bin`
  15,368 -> 19,969, images 9,741)
- `fwtool diff` against pod-cover: exactly the two playing_page files and the 20 `np_*.png`
  (plus 12 directories that differ only in listed size)
- builds are deterministic (two clean builds byte-identical); `test/patch.py` on the built tree: 128 passed
- package `M1Plus-V2.1fN-look-nowplaying-pod-cover-lockscreen-iconpercent-space-update.bin`,
  SHA-256 `dbb0dee50188ad48c469eb26e039346a0c5ce409c530055a7059d9fa3fb43713`; `fwtool diff` against
  V2.1eN (`84ed09f1...`): only `ui/playing_page.bin` (label_album x -45 w 261 -> x -52 w 268), same
  rootfs size. Not flashed on its own; the fix ships to the device in V2.1fA (`docs/look-all.md`)

## What to check on the device

- Now Playing opens and looks like the preview; the status bar sits directly above the black page
  with no seam; nothing overhangs the bottom (the page uses the full 450 px)
- the album line shows the album without `Album:` and without a colon or a sliver of `m` before it
  (English UI); it starts at the title's left edge; with a long album it scrolls and the prefix stays
  hidden (V2.1eA showed the colon: see "The album line")
- the art corners are rounded, also on the placeholder cover and while the cover loads
- every control works: Back, heart (toggles filled / outline), More, mode (cycles random / repeat one /
  repeat all / in order), previous, play/pause (glyph swaps), next, queue; tap and drag on the bar seek
- swipe left on the art: lyrics (current line off-white, others grey) and info; the dots follow; swipe back
- A-B repeat (from More): the markers sit under the bar as in stock
- the loading spinner, if it ever shows, is centred on the play button
- the lock screen's play/next buttons and other pages are unchanged (stock orange)
- theme1 (System settings, if selected) carries its own playing_page files and stays stock
