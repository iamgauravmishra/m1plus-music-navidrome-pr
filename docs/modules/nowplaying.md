# Now Playing

Split out of docs/architecture.md and docs/ui.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 8a. Now Playing (`patch/nowplaying.c`, test `test/pod/nowplaying.py`; the look is `docs/modules/nowplaying.md`)

The stock `playing_page` (`ui/playing_page.bin`, restyled by `tools/mod_nowplaying.py`) gets a cover-coloured window, the
cover's rounded corners and a remaining-time label from one hook and one page timer.

**The hook** (`m1plus_playing_init`, section 2): `playing_page_init` `0x53d1e4` (`a0` the window, `a1` the context
`{queue, index, class, mode}`; it registers the page's `EVT_*` handlers with `widget_on`, starts the queue with
`start_player` when the context's class is not `0xff`, runs `playing_choiceshowpage` and `player_timer_start`, returns 0, or `0x10` for a null window).
The hook calls it through `stock_playing_init_trampoline` and returns its result; with `RET_OK`, a window and no
`/mnt/mmc/m1plus-off`, `np_start` runs: it finds `np_remaining` and `label_playlen` (a missing one turns the time off, not the tint),
registers `EVT_DESTROY` on the window (`np_on_destroy`, context the window), adds a **repeating 500 ms timer** (`np_tick`, answering
`RET_REPEAT` 8 as the stock page timer `0x53cf48` does; a refused timer or `widget_on` leaves the page stock), registers
`np_on_art_paint` on `img_playcover` (`EVT_AFTER_PAINT`) and runs one tick at once. State is one 176-byte `.scratch` struct
(`np`): the window, the labels, the timer id, the cover key, the window colour, the seconds shown, which label is visible and the
12x12 corner table. A page built over a live one removes the old timer first; a destroy whose context is not the current window
(an earlier page's) does nothing; the current one removes the timer and zeroes the state, after which a stray tick returns `RET_OK`
(ends) without touching a widget.

**The tint** (`np_cover`): demo's cover thread `parseplaycover_thd` (`0x4ded84`) removes `/tmp/coverpic.jpg` and `/tmp/externpic.jpg`, sets the
source type word `0x97cad8` to 1 (`0x4df044..0x4df094`), writes the new file (extern and embedded covers under `parse_cover_mutex`) and then
sets the word to 2 (embedded art, `coverpic.jpg`), 3 (a folder image, `externpic.jpg`) or 5 (the `.downpic` cache copied to
`externpic.jpg`); the page's own loader (`0x53a5d8`) draws exactly these. `np_cover` does nothing while the word is 1, sets the neutral tone once for any other value, and
for 2, 3, 5 reads the file through stdio (`np_file_key`: FNV-1a of at most 512 KB and the length, never 0; no file or an empty one:
try again next tick, no colour change). **Tone cache:** when the key changed, the playing track's album key (`cc_playing`, `cc_album_key`;
none for no queued track or an untagged one: empty album name) is looked up in the tone cache (`pod_tone_get`, `patch/common.c`, shared with the
album page; docs/modules/album-page.md): a hit sets that tone and decodes nothing (the hash only decides *when* to look, so a different cover
file of an album keeps the album's cached tone); a miss decodes as below and `pod_tone_put`s the result. A key different from the last decodes the picture with `cc_decode` (`patch/covercache.c`, the stock
loader, loaded and unloaded at once as the Cover Flow rows do, `box` mode reducing the centred square to one pixel = its average
colour), `np_tone` makes the tone and `np_set_color` stores it as the window's `bg_color` with `widget_set_style(win, "normal:bg_color",
&value_t)` (`0x66c448`, AWTK's `widget_set_style_color`: `widget_ensure_style_mutable` `0x666700`, then `style_set`; the `value_t` is
made by `value_set_uint32` `0x711858`, colour word `0xAABBGGRR`) and invalidates the window; a failing style call changes nothing,
not even the colour the corners use. A picture the loader refuses is not tried again until the file changes (the old colour
stays); the source word is read again before the decode, so a file demo started replacing is left alone. No lock on `parse_cover_mutex`
is taken (the UI thread never waits for an extraction): a file is read only while the word says 2, 3 or 5, which demo sets after
writing it; the few instructions between demo removing the old file and setting the word to 1 can only make `fopen` fail (no key, try again).
Tone: value `NP_V_MIN + v * (NP_V_MAX - NP_V_MIN) / 255` (32..192), every channel keeps `NP_SAT_NUM / NP_SAT_DEN` (23/25 = 0.92, HSV saturation x 0.92; it was 4/5) of its
distance from the brightest `v`, black is `NP_NEUTRAL` (`#202020`, the asset's window colour); `tools/mod_nowplaying.py tone` is the model
(the test compares them on 369 colours). The window shows it under `np_tint.png` (alpha 38..235 down the 450 rows); with at most 192 the
white title and the `#AAAAAA` lines keep 4.5:1 (worst case checked at their rows in the test).

**The status bar (EXPERIMENTAL, `np_bar_*`; the machinery is `pod_bar_*` in `patch/common.c`, shared with the album page, `album-page.md`).** The names `np_bar`
and `np_bar_set` below are now `bar_find` / `bar_set` there; `pod_bar_color` is the darkening, `pod_bar_tint(win, colour)` sets the bar and records `win` as its owner,
`pod_bar_black(win)` puts the stock black back **only if `win` is the owner** (so a page that lost the bar to the next page, Play all or Back, never undoes the new
owner's colour), `pod_is_top(win)` is the top-window check. `np_bar_color`, `np_bar_apply`, `np_bar_black` and `np_bar_sync` are thin wrappers (`np.bar` still says "I think the bar is
mine"). The stock status bar is a child of the window manager whose vtable type is
`"system_bar"` (`widget_is_system_bar` `0x66c894` compares `vt->type`; the navbar is `"system_bar_bottom"`; the window manager paints
both with `window_manager_paint_system_bar` `0x690b98` on every frame, so a changed style plus an invalidation is all it needs, the way the
clock repaints). `np_bar` finds it with `window_manager()` and `widget_count_children` / `widget_get_child` / `widget_get_type`
(all pinned already), per use, nothing cached. `np_bar_set` is the window's own call: `widget_set_style(bar, "normal:bg_color",
&value_t)` then `widget_invalidate_force(bar, NULL)`; a failed style call changes and repaints nothing. The colour is
`np_bar_color(np.color)` = `np_shade(color, 0)` (the page's first row under the gradient, alpha 38) divided by 16/15 steps until
`2126 r^2 + 7152 g^2 + 722 b^2 <= NP_BAR_LUM_MAX` (119000000: gamma 2 is above the sRGB luminance, so white keeps 4.5:1; worst
case 4.57:1 over any colour, 5.09:1 over the tones); a dark tone is exactly the page's row. Lifecycle, all in the page's code:
`np_start` registers `EVT_WINDOW_TO_BACKGROUND` `0x12c` and `EVT_WINDOW_TO_FOREGROUND` `0x12d` on the window (`window_manager_default_open_window`
`0x691930` dispatches `0x12c` to the window a new window (not a keyboard or overlay) covers and `0x12d` to the one a closing window
uncovers, `0x69182c`, `0x691b3c`; dialogs such as the pull-down are included, so the bar is black while one is open), and tints the bar
only if both registered (`np.barok`) and after the timer exists. `np_on_background` clears `np.fg` and `np_bar_black`; `np_on_foreground` sets
`np.fg` and tints. `np_set_color` re-tints when the cover's colour changes. The tick's `np_bar_sync` covers a missed event: the bar is
ours only while `window_manager_get_top_main_window` is the page (black when another normal window is on top, tinted again when the
page is on top and `np.fg`; a dialog leaves the top normal window as it is, which is why `np.fg` stays 0 after its background event).
**Hidden page, unchanged cover.** While another page is the top normal window (`np_bar_sync` returns `pod_is_top`), `np.fg` is 0
and both window events are registered (`np.barok`), `np_tick` runs only `np_bar_sync` (the bar cleanup) and does no cover, time or
info work: a page above it costs a few hundred instructions a tick instead of a full cover read. A dialog (the pull-down) also clears
`np.fg` but leaves the page the top normal window and partly visible, so under it the remaining time, the info lines and the tint go on. `np_on_foreground` runs `np_work` itself before it sets `np.fg` and tints
(one bar style call for a changed colour), so the page is current when it reappears. When in front, `np_cover` first takes the cheap
look `np_cover_sig` (no byte of the cover is read: `fopen`/`fseek`/`ftell` for the length, a hash of the source type, that length and
the playing track's path; no `stat`, which the payload does not import) and skips the hash while it equals `np.sig`, the signature at
the last full hash, and a real colour is held (`np.key` neither 0 nor neutral). Any difference, or an unreadable file, takes the full
`np_file_key` as before. This relies on demo writing a new cover per track change (and via the busy state, which is not hashed); a
same-length, same-source cover swapped under the same track without a pass the tick could see would be missed until the track
changes. Measured (Unicorn, 64 KiB cover): 396,187 instructions and 64 KiB read per tick before; after, an unchanged tick reads nothing
and a covered tick is under 3,000 instructions with no cover, time or info calls (`test/pod/nowplaying.py`).

`np_stop` (destroy, or a new page over a live one) sets black before it removes the timer and clears the state, so every exit path restores
the stock colour; `np.bar` records that the bar is ours. Black is set by the same style call (the bar keeps a mutable style
overriding the asset's `#000000`). No new hook, no paint or main-loop code; the kill switch, a refused timer, a refused window
event or a missing bar leave it untouched. `np` is now 188 bytes of `.scratch`.

**The corners** (`np_on_art_paint`): `img_playcover` is a 264 px square image (the size demo writes, section 6 of `docs/ui.md`); AWTK has no
image clip, and one static mask would be the wrong colour on all but one window colour. The four 12x12 corner squares are
painted from the cover widget's `EVT_AFTER_PAINT` (canvas from the event, `EVENT_PAINT_CANVAS`; coordinates are the widget's, as in
section 5a): `np.corner` holds the coverage (0..255) of the area outside a quarter circle of radius 12 (`np_corner_init`, 8x8 samples
a pixel, computed once at the page's start; the Python model `corner_alpha` equals it), and every non-zero entry is one
`canvas_set_fill_color` (the window colour at that row under the gradient, `np_shade` of `np_alpha(y)`, with the coverage as alpha) and
`canvas_fill_rect(x, y, 1, 1)` that the stock canvas blends, so the corner is anti-aliased over the art. About 160 fills, and only
when the cover widget repaints (page open, track change; not for the slider, the times or a scrolling title). Without the hook the corners are square.

**The remaining time** (`np_time`): `get_playtimeandlength(&pos, &len)` (`0x4e015c`, the call the stock tick makes at `0x53a8fc`: seconds;
returns 1, or -1 for an index outside the queue). With 1 and `len > 0`, `np_format_remaining` writes `-m:ss` (`-h:mm:ss` from 3600 s;
no leading zero, as Apple Music; `np_format_clock`; a position past the length clamps to `-0:00`) into `np_remaining` only when the seconds
changed and shows it while hiding `label_playlen` (`widget_set_visible`; both labels are insensitive in the asset, so hide = invisible +
insensitive); otherwise `label_playlen` is shown again and `np_remaining` hidden. demo keeps rewriting `label_playlen` on its own tick, which is why
the swap is two labels and not one rewritten text (two timers 500 ms apart in phase would flash the total).

**The elapsed time** (`np_elapsed`, same tick): `label_playtime` is stock's, rewritten by the stock page timer as `mm:ss` / `hh:mm:ss`. Looked up at the start
(`np.pt`); each tick its text is read (`widget_get_text_utf8`, 24 bytes; a text that may be cut is left alone) and its hash compared with `np.pdone`, the hash
of what the label held after our last look. Only a different text is parsed (`np_parse_clock`: two or three groups of one to three digits, nothing else; otherwise
stock's text stays) and rewritten with `np_format_clock` (`0:20`, `10:00`, `1:02:03`; a leading `00:` hour group goes), the hash stored first so nothing is
retried. Both stock's page timer and ours are 500 ms timers of the same loop, so stock's text is normally never painted between its write and our rewrite.

**The info page** (`np_info`, same tick). Stock fills it when the track changes (`show_player_face` `0x53bab4`, which the page timer
calls every tick but which fills only while its changed flags `0xa05a62/3` are set; the fill is `0x539c40`): `label_info`
`%s|%.1fkHz|%dbit|%dkbps` (or `%dkHz`), `label_album/genre/year/location` `%s:%s` (year `%s:%d`), `label_size` `%s:%.2fMB`; the label
and the "Unknown" of a missing value come from the app's language (`player_unknown`, `player_location`, `player_filesize`).
At start `np_start` looks the six labels up; each tick `np_info` reads each text (`widget_get_text_utf8` `0x667d84`, 512 bytes; a text that
may be cut is left alone) and compares its hash with `np.done[i]`, the hash of what the label held after our last look. Only a
different text is rewritten (hash stored first, so nothing is retried; then the rewritten text's hash): "Label: value" (a space after
the first colon), `Genre` / `Year` swapped in as `TR()` keys for stock's `genre` / `player_era` label (stock's "Genres" / "Era" read as
a tab name, a decade or "age" in several languages), spaced units after a digit (`kHz`, `kbps`, `-bit` on the quality line,
` MB` on the size only), the quality line's bars spaced unless the result is over `NP_INFO_SPACED` 36 characters. No colon, an empty text,
a failed read or an overflowing result leaves stock's text. The flash of stock's text between its write and our next tick is at most 500 ms
and only while that page is showing. No new hook, no stock memory written. `test/pod/nowplaying.py` runs it for every language and every
plausible quality line (PCM, DSD) against the 304 px label.

**Safety.** Runs only on a Now Playing build; the kill switch, a refused timer, a missing widget or a failing call each leave stock behaviour; the timer is gone with
the window; no stock memory is written (the style and the labels go through the stock setters); no lock, no thread, no heap. The only paint-time code is the one `EVT_AFTER_PAINT` on the cover widget. Newly pinned: `widget_set_style` `0x66c448`,
`value_set_uint32` `0x711858`, `get_playtimeandlength` `0x4e015c`, the data word `COVER_SRC` `0x97cad8`; `canvas_set_fill_color` / `canvas_fill_rect` (section 5a) are reused.
**A-B markers.** `getx_by_playtime` `0x53b824` returns `(pos - cue) * 0x128 / len + 0xc` and its caller `0x53b8f0`
(`img_repeata` / `img_repeatb`, called from the page timer `0x53cf48` through `show_player_face` and from `player_timer_start`) moves the markers to `y = 0x16c`
(three `addiu a2, zero, 0x16c`, one per branch); `mod_nowplaying.patch_markers` changes the 16-bit immediates at `0x53b8d4` (0x128 -> 264),
`0x53b8ec` (0xc -> 28) and `0x53b9c4`, `0x53ba48`, `0x53ba64` (0x16c -> 370, the new bar's centre 363 + 7), after checking those five words and the two functions'
prologues and call sites (nine more words). Neither function is reachable from `main` / `platform_init` (`tools/reach.py`).
Not verified on the device: the style call's repaint, the slider's `round_radius`, the corner fills over the real canvas, the look of the 4 px dots.

### Now Playing (`tools/mod_nowplaying.py`, `patch/nowplaying.c`)

An Apple-Music-style page on the stock `playing_page`, fitted to the 320x450 window (`tools/preview_nowplaying.py` draws it from a built tree):

```
  0   ====== grabber pill 36x5 (the Back button, 100,0 120x44)
 28   +--------------------------+  cover 264x264 at 28,28, corners 12 px
      |                          |
 292  +--------------------------+
 296           . o .               micro page dots: 3 x 4 px, 10 px apart
 305  Title (20 px white)    (star)(...)    star, More: 44x44 targets, 32 px discs
 329  Artist (18 px #AAAAAA)
 348  =============---------------   bar 6 px (ink 360..366) in the stock 30 px target (28,348, 264 wide)
 379  1:23                    -3:42   14 px #AAAAAA: elapsed, remaining (72 px boxes, 18 high; digits 382..391)
 392  [mode] [<<]   [ || ]   [>>] [queue]   the five stock slots, 58 px high (glyphs 407..435, centred on 421)
 450
```

Rhythm of the lower half, measured on ink (artist bottom 344): 16 px to the bar, 16 to the digits, 16 to the transport glyphs, 15 to the window's
bottom (V2.1nL: 22 / 13 / 17 / 11). `mod_nowplaying.py` places every box from the font's ink offset (the 14 px digits start 3 px below their label's top).
`slide_view_view` ends at the times' bottom (397); the transport row (a later sibling, on top) overlaps its last 5 px.

- **Window colour.** The window is the cover's colour (below the gradient) and its colour changes per track: the asset's
  `bg_color` is the neutral tone `#202020`, `patch/nowplaying.c` sets the window's `bg_color` through the style API
  when the cover changes. Over it lies `img_np_tint` (`np_tint.png`, 320x450, black, alpha 38 on the first row to 235 on
  the last = 0.15 .. 0.92), the first child of `view_local`, insensitive. The tone of a cover: its box-averaged colour
  (`cc_box`, the whole picture to one pixel) with value `32 + v * 160 / 255` (`v` the brightest channel, so 32..192) and
  every channel keeping 23/25 of its distance from `v` (a grey stays grey; black is the neutral tone). Under the gradient the
  white title and every `#AAAAAA` line keep at least 4.5:1 at any tone (`test/pod/nowplaying.py` checks the worst case
  at the title, artist and times rows). No cover file (a random or streamed source), or the kill switch: neutral.
- **Status bar (EXPERIMENTAL, V2.1mO).** While Now Playing is in front, the 30 px status bar (`system_bar`, black in stock) takes
  the colour the page has on its first row (the tone under the gradient's alpha 38, so the bar and the page read as one
  surface), changing with the cover. Its children have no backgrounds (`mod_battery` made the battery fill transparent), so the
  bar's own `bg_color` is all there is to change. The white clock, volume, Wi-Fi and battery keep 4.5:1: the bar colour is
  darkened until its luminance allows it, so for a bright cover (value over about 150) the bar is darker than the page's first
  row (a visible step of up to 55 per channel at the brightest) and the unlit Wi-Fi arcs (`#666666`) fade into it. Black comes
  back when the page goes behind another window (page, dialog, the pull-down), is closed, or on any failure; it is re-tinted
  when the page is in front again. There is no separate switch: `/mnt/mmc/m1plus-off` turns all of the page's code off, the bar
  included. Whether it looks right is a device question.
- **The cover is 1:1.** AWTK scales an image by nearest neighbour, so the art is drawn at the size of the file:
  demo writes `/tmp/coverpic.jpg` / `/tmp/externpic.jpg` at **264** (four pinned immediates, section 7, Lock screen: "The cover
  size is a demo constant"), the widget is 264 at 28,28 (the 28 px margin is the text column's and the bar's too). A 280 px
  art (margins 20) would cost 16 px of height in the 450 px window and push the transport row under 44 px; 264 keeps the
  rhythm and only makes the lock screen's card 16 px smaller.
- **Rounded corners.** An image cannot be clipped, and a static mask has one colour while the window has many, so
  the payload paints the four 12 px corners in the colour the window has there (the tone under the gradient on that row),
  anti-aliased (8x8 samples a pixel), from the cover widget's own `EVT_AFTER_PAINT`: about 160 one-pixel fills when the cover
  repaints (open, track change), none otherwise. Without the payload (kill switch, a failed hook) the art is square.
- **Cover shadow** (`np_shadow.png`, 312x312, black; `img_np_shadow`, insensitive, an asset only). The art's rectangle shifted down 4 px and blurred
  by a Gaussian of sigma 7 px (exact erf profile, `mod_nowplaying.shadow_alpha`), 55 % at full strength under the art, so the visible maximum just under the
  art's bottom edge is 38 % (26 % at the sides, 14 % above, ~0 beyond 20 px). The image lies **over** the cover (the next sibling after `img_playcover` on page 1, so it slides away with
  the art and is painted under the title and artist) and has a **hole** exactly where the art is (alpha 0 inside the rounded rectangle, the corner painter's
  own 8x8 coverage on the 12 px arcs), so the cover is untouched while the four corner squares the payload fills with the window colour are darkened like the
  rest of the surroundings (a shadow behind the art would leave them as light notches). Image at (4, 4), inside the 320x352 page: no clipping.
  Without the payload (kill switch) the square art corners are darkened a little by it (9..22 %, only the corner pixels). 2.4 KB.
- **Controls.** The grabber is the Back button (`btn_return`, `img_btn_style`, `np_grabber` / `np_grabber_down`: a 36x5
  white pill at 43 % in a 120x44 image), overlapping the top 16 px of the art (a swipe starting there goes to the button).
  Favorite (`btn_fav`) and More (`btn_more`) are `np_fav` / `np_unfav` / `np_more`, 44x44 images with a flat 32 px translucent white disc (`#FFFFFF1A`,
  `#FFFFFF33` pressed; not glass, `np_disc`) and an 18 px glyph (2.0 px stroke) baked in: Lucide `star`, filled when the song is a favorite, outline when not (was `heart`; the Home grid's Favorites tile, the Extras row and the batch-add dialog use the same star). The glyph is **centred optically**: the middle of the glyph's box and of its silhouette's centroid (a star's lower points reach less far than its top one, so its box centre alone looks low) sits at the disc's centre, placed in quarter-pixel steps by an SVG translation (`mod_icons.np_glyph`; V2.1nL measured the then heart on the device 0.5 px up and left with box-only placement). More is exactly centred; the app swaps the star's style (`btn_imgfav_style` / `btn_imgunfav_style`) as before.
  Transport: prev / play / pause / next are solid shapes drawn by `tools/mod_icons.py` (`transport_mask`): rounded convex
  polygons (inset by r, dilated by r), 16x supersampled and box-downsampled, `#EEEEEC` (pressed `#8C8C8C`). Play: triangle,
  ink 29x31, 1.5 px right of centre, r = 0.10 x 31 = 3.1 px. Pause: two bars 28 tall, 8.4 wide, 10.1 apart, r = 0.30 x bar
  width. Skip: two overlapping triangles (overlap 0.18 x triangle width), ink 24 tall x 35 wide (1.46 x height), r = 0.6 x the
  play r; canvases 44x44 (play, pause, prev, next; the 60 px slots and the lock screen's 48 px play / next targets hold them),
  mode and queue are Lucide glyphs at 18 px (1.5 px stroke, in their 30 px slots, targets unchanged) in `#C8C8C8` (was the secondary grey `#AAAAAA`; repeat-off `#6E6E6E`), pressed `#8C8C8C`. The progress bar is the
  stock `slider_play` (a 30 px seek target) with `bar_size` 6, track `#FFFFFF4D` (30 % white, was 20 %; 2.4:1 or more against the window on every tone, the fill 4.5:1 against the track), fill `#FFFFFFEB`, `round_radius` 4 (the
  slider paint reads it; whether this build rounds a 6 px bar is only the device's to say), no thumb. The slide
  indicator has `size` 4, `spacing` 10, dots `#FFFFFF46` / `#FFFFFFEB`.
- **The info page** (page 3): `label_info` (the quality line, 304 px at x 8, `#EEEEEC` 18 px) then album, genre, year, size, 18 px
  `#AAAAAA`, then the location. The text is stock's, rewritten by the page timer (`docs/modules/nowplaying.md`) as
  "Label: value" with spaced units, `FLAC | 44.1 kHz | 16-bit | 950 kbps` (tight bars, `FLAC|...`, for a line over 36 characters:
  every DSD line), `File Size: 35.92 MB`, `Genre:` and `Year:` (our keys, 13 languages) for stock's "Genres" / "Era", `Location: SD:/...`;
  a missing value is stock's own "Unknown" in the app's language.
- **Not on the art page.** The album line (`label_album` is on the info page with genre, year, size, location), the quality
  line (`label_info`, the info page's first line), the "3/12" index (`label_index`, hidden at 0x0 like `img_hr`, which demo toggles
  for Hi-Res tracks), the Hi-Res tag. Every widget the app looks up keeps its name; the new ones are `img_np_tint` and
  `np_remaining`. Lyrics (page 2) and info (page 3) start under the grabber (y 44) and end above the dots (y 288); the slide
  pages are 352 px high so page 1 holds the title and artist.
- **Remaining time.** demo rewrites `label_playlen` with the track's length on every 500 ms tick. `np_remaining` (an insensitive
  label on the same rectangle, hidden in the asset) shows `-m:ss` (`-h:mm:ss` from an hour on; no leading zero, the elapsed label is
  reformatted the same way: `0:20`, `1:02:03`) from `get_playtimeandlength` (the call the stock tick makes) while the player reports a length; the payload swaps
  the two labels' visibility, and `label_playlen` shows again whenever the player does not. A position past the end reads
  `-0:00`. Both labels are insensitive in the asset, so a hidden one never takes a touch.
- **A-B repeat markers.** demo moves `img_repeata` / `img_repeatb` to `x = 12 + pos * 296 / len`, `y = 364` (the bar's centre
  357 + 7) in `getx_by_playtime` (`0x53b824`, `0x53b8f0`; only from this page's timer): five pinned `addiu` immediates make it
  `x = 28 + pos * 264 / len`, `y = 370` (centre 363 + 7). `mod_nowplaying.marker_edits` lists them with their stock words;
  `test/demo_diff.py` allows exactly these.
- **Files.** `ui/playing_page.bin`; `styles/playing_page.bin` (the window theme searched before `default.bin`: the mode and favourite
  styles point at `np_*` icons, which the app swaps with `widget_use_style`; page-local `btn_imgplay_style` / `btn_imgpause_style`, so
  the lock screen and other pages keep theirs; lyric lines `#A0A0A0` and `#EEEEEC`); `images/xx/np_*.png` (21 glyphs from
  `mod_icons.py`, plus `np_tint.png` and `np_scrim.png` drawn by the step). **The scrim** (`np_scrim.png`, 320x324, black at 50 % alpha 128, ramping linearly to 0 over 36 rows at the top and the bottom;
  `img_np_scrim_lyrics` / `img_np_scrim_info`, the first child of `view_lyrics` / `view_info` at page y 8, insensitive, an asset only): the lyric and info text (y 44..288) lies
  in the full-strength middle; the art page has none and keeps the full tint. The inactive lyric grey went from `#8C8C8C` to `#A0A0A0`.
  `test/pod/nowplaying.py` checks over every tone under the tint and the scrim: inactive lyrics and the info labels >= 3:1, the current lyric and the quality line >= 4.5:1 (the inactive lyric alone, without the scrim, is under 3:1 on the brightest tone). `image_wait` and the A-B markers are insensitive. Touch: `check_touch`
  models demo's hit test for every control (44 px, the slider 30), the art and the title rows reach the slide view.
