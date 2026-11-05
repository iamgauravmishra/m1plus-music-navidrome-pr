# Lyrics page

Now Playing shows synchronized lyrics with a highlighted current line, staggered spring
scrolling, drag-to-browse, tap-to-seek and intro dots. Latin lines use 30 px Inter Bold;
other scripts use the default font. Stock still loads and parses local and online lyrics.

**Sources:** `patch/lyrics.c`, `patch/lyrics.h`, `patch/nowplaying.c`,
`tools/mod_nowplaying.py`, `tools/mod_font.py`, `tools/font_inter.py`.
**Validation:** `test/pod/lyrics.py`, `LYRICS_PINS` in `tools/pod.py`,
`tools/preview_lyrics.py` (pass `--shot PATH` for the background screenshot;
`--mode scrim` and `--mode intro` select those previews).
Previews use the shared layout model and real fonts; AWTK wrapping is approximated.

## Stock integration

Local lyrics are loaded by `mclLoadExLyric` (`0x5d41e4`); online lyrics by
`online_lyricthd` (`0x50a048`) and `online_loadexlyric` (`0x508a00`).
Both build children of `scroll_lrc` with text and an integer `lrc_time` property.
The payload reads those rows and compares their times with `get_playtime()` in seconds.
It does not read the lyric deque, take its mutex or change the stock loaders and timers.

`np_lyrics` is a sensitive, non-slidable `scroll_view` at (28, 44, 264, 244) in
`view_lyrics`. It clips its children. `ly_start` creates 20 reusable labels and a
measurement label, then hides `view_lrc` with both `visible=false` and
`sensitive=false`. Stock's no-lyrics message stays stock's. Missing widgets or failed
label creation leave the stock list available.

There is no additional hook: `np_start` calls `ly_start`, the 500 ms `np_work`
tick calls `ly_tick`, and `np_stop` calls `ly_stop`. A row signature (count,
first and last handles and times) detects replacement lyrics; at most 400 rows are read.

## Layout and appearance

- The current line's top is anchored at 85 px (0.35 of the 244 px view).
  Labels have up to three wrapped rows, 34 px per row and a 12 px gap.
- Row height follows AWTK's font size plus `spacer`: 30 + 4 px. Width is measured
  in the line's own face; wrap estimates allow 56 px slack for Latin and 8 px for CJK.
  Actual wrapping remains AWTK's; an underestimated row count can clip text.
  Each line is measured once and kept, except a measure of 0 for non-empty text: that line
  stays one row, is not cached, and later page ticks measure it again and redo the layout
  (after the first failed measure a layout measures nothing more; at most 20 ticks' layouts,
  10 s, per lyrics load can fail, then one row is kept).
- `np_lyric_style` selects `lyrics.ttf` (the Inter Bold subset).
  `np_lyric_cjk_style` uses the default font for mixed scripts, unsupported characters
  or malformed UTF-8. AWTK has no per-glyph font fallback.
- Lines are white with opacities 1.0, 0.45, 0.32, 0.24 and 0.18 by distance
  from the current line. A 56 px edge fade applies at both ends of the view.
  While browsing, non-current lines use opacity 0.6 before the edge fade.
- `np_scrim_lyrics.png` is 27% black (alpha 68), with eased 44 px edges.
  Contrast floors over the tested cover tones are 4.5 / 2.3 / 1.8 / 1.55 / 1.4.
  See [Now Playing](nowplaying.md) for the tint and scrim assets.

## Motion and touch

The motion is inspired by amll-dev/applemusic-like-lyrics (anchor, falloff and staggered
spring). It uses integer arithmetic without blur. A 640 ms damped spring (zeta 0.72,
wn 12/s, 65-entry table) has a 6 px overshoot cap. Lines start in sequence with delays
of 50, 97, 141, 182 ms and so on. One 40 ms timer moves visible labels while needed.
Moves of more than four lines and refused timers snap into place.

Pointer listeners on `np_lyrics` return `RET_OK`, leaving sideways swipes to the slide view.
Labels are insensitive. A vertical move over 10 px starts browsing; after 3 seconds without
touches (checked by the page tick), the lines return to the current position.
The highlight continues following playback during browsing.

A tap seeks with stock `seek_time(seconds)` at `0x4e0544`; it is ignored while stopped
or within the first 200 ms of an animation. A 1 second hold lets the player catch up.
The stock seek can block the UI thread for up to 2 seconds. Stock row taps only toggled
the lyric display flag; those rows are hidden and receive no touches.

## Intro dots

Three 10 px image dots appear at the anchor when the first line starts at 4 seconds or later.
The upcoming lines sit one 46 px pitch lower. The dots fill by thirds, breathe over 2.4 seconds
and fade over the final 500 ms; the lines then spring into the anchor.
An 80 ms timer runs only while the dots show and playback is active.

`ly_clock` interpolates whole-second playback readings with the monotonic clock, bounded
within the reported second. Pauses freeze it; seeks reset it. Dots move with the lines during
a drag and are insensitive. Dots between lyric lines are not enabled.

## Pins and safety

`LYRICS_PINS` checks the row properties, stock timer reads, row-click flag accesses,
font fallback and label pitch instructions. Key evidence includes `lrc_time` at
`0x751c80`, its write at `0x5384bc`, timer reads at `0x538654` / `0x5386a8`,
row-click words at `0x536e3c` / `0x536e50`, pitch instructions at
`0x62e9f8` / `0x62ea04` / `0x62ea24` and font fallback at `0x650ebc`.
Called functions are also checked against `FUNCTIONS`; consult `tools/pod.py` for the full set.

All work runs on the UI thread from page timers and listeners. No stock words are written,
no stock widget is renamed or removed, and no thread or lock is added.
Startup failures preserve the stock list; animation failures snap.
Destroy removes timers and ignores stray events.

## Validation

The emulation tests cover assets and pins, lifecycle failures, line following, font selection,
wrapping, spring and opacity models, drag and seek gestures, intro timing, pause/resume,
song changes and instruction cost. They verify unchanged hooks and stock widget names.
Asset checks include scrim alpha, dot shape, font coverage and contrast.

Device checks remain necessary for actual AWTK wrapping, font loading and baseline placement,
clip and opacity behavior, local and online timing, seek latency, gesture interaction,
animation smoothness and the lighter scrim over bright covers. Emulation and previews do
not establish those results. Blur, translation, per-word fill and a larger current line
are not implemented.
