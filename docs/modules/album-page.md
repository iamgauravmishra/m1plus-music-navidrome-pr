# Album page

**Sources:** `patch/albumpage.c`, `patch/songops.c`, `patch/covercache.c`, `patch/durations.c`,
`tools/pod_ui.py` (`build_album_page`).
**Tests:** `test/pod/albumpage.py`, `test/pod/durations.py`, `test/pod/shared.py`.
Preview: `tools/ah_ink.py` measures header typography; `tools/preview/preview_albumlen.py` draws the scrolled page with its footer and the footer line in all languages.

Albums, Cover Flow, Recently Played and Look up album open `m1plus_album_page`
(`ui/m1plus_album.bin`) through `cc_open_album`.
Stock Shanling library pages retain their stock album-details page.

## Opening and fallback

`album_open(class, row)` loads details for library albums (`0xff10`), artist albums
(`0xff11`) or composer albums (`0xff14`). The browsing record is snapshotted and
restored before each query/play operation.

An already-open page or missing window/assets falls back to
`albuminfo_page`. Cover Flow's All albums card opens the artist's Songs page;
unsupported composer/all-songs cases use the stock fallback.

The stock fallback requires `albumcoverinfo_init` followed by
`batchadd_albumcover_task(0, 0)`: initialization parks the cover worker at state 2,
and the batch call releases it to state 1 before the page queues its task.
The relevant state is `albumcover_taskstate` at `0xa05a18`.
Stock album artwork retains its 100 px size.

## Layout

A stock list fills the 320 × 450 px window. Its content view paints a 346 px header
and 64 px track rows. Glass navigation controls are direct window children above the
list so an enclosing view cannot intercept the whole navigation band.

| Element | Geometry / appearance |
|---|---|
| Navigation | Back; Select / Now Playing capsule; selection mode adds All/None, Add, Delete, Cancel |
| Cover | 160 × 160 at (80, 50), 10 px corners |
| Album | Centered 22 px white at y 224 |
| Artist | Centered 18 px grey at y 247 |
| Metadata | 15 px at y 267: year and track count, or track count alone |
| Playback | Shuffle target 44 × 44 at x 42 with a 40 px disc (the pill's height); Play target 180 × 44 at x 96 (12 px after the disc); y 292. A playlist's page (the Songs page with its header) copies this group (`patch/common.c` `m1_pill_place` / `m1_pill_paint`; [Songs](songs.md)) |
| Tracks | Number column (24 px, 34 from track 100) and white title at the list title size (21 px) in a 22 px line 20 px down the 64 px row (`AB_TEXT_Y`, centred over the hairline), 20% white press fill, 13% white hairline. The playing track keeps its white title; a 12 px wave (`ah_wave`, `#EEEEEC`, four round bars, the rows' `np_row_playing` scaled; static) replaces its number, right-aligned in the number column, 1 px above the centre of the title's line so it sits on the centre of the capitals (`AB_WAVE`, `AB_WAVE_Y`) |
| Footer | `ab_foot` (`13 tracks, 49 minutes`): 15 px `#AAAAAA` left-aligned label at x 12 (`AB_NUM_X`, the number column's left edge), `AB_FOOT_GAP` 14 px under the last row, 20 px high; only when the duration is known (52 px of content), else none |

Each track ends with a grey "..." (24 px `#8C8C8C`, a 44 px tap zone at x 266..310) that opens the Play Next / Play After / Add to Playlist menu ([rowmenu](rowmenu.md)); the title ends at **x 262** (was 298) so it never runs under it. Select mode has neither. The window's last two children are the menu's `rm_scrim` and `rm_card`, above the glass navbar.

Year is the first track year in 1000..2999.
Track numbers use a wider column from 100 onward. CUE titles use the file name.

## Album length

The database has no duration: `time/time_end` are CUE offsets, 0 for ordinary files. File durations are measured once
through stock's TagLib and kept on the card in `/mnt/mmc/.m1plus/durations` beside the cover cache (`patch/durations.c`, `DUR_FILE`; written by `m1_card_write`; no card or USB mode: no table, nothing measured, no duration shown; a card swapped while a page holds the table is not noticed):
`taglib_file_new(path, 1)`, `taglib_file_audioproperties`, then `AudioProperties::length()` through vtable slot 3
(`+0xc`, what libtag_c's `taglib_audioproperties_length` does; `demo` imports the first, second and `taglib_file_free`, not
that one). `.iso` images are never opened, as stock never reads their properties. The design follows q2-pod's Long Songs
lengths cache (`patch/navigation.c`, `docs/internals.md#long-songs`).

- **File:** 12-byte header (`M1LN`, count, FNV-1a of the entries), then `{key, size, seconds}` entries (12 bytes) sorted by
  key; key = FNV-1a of the path (never 0). It is read whole and searched by bisection. Wrong magic, count, checksum, order
  or size means the file is ignored and the next write replaces it. Writes merge, sort and drop duplicates, go to `.tmp`,
  `fsync`, then `rename`; a failed write keeps the old file. 0 seconds records a file TagLib could not read; it is not
  measured again until its size changes.
- **Track seconds** (`dur_song`): a CUE track with both ends is `end - start` and is never measured; otherwise the file's
  length less the CUE start (the last CUE track). A start at or past the length, a missing file, an unreadable file or a
  size different from the entry's is unusable (0) or missing (-1, to be measured).
- **Page:** `ab_durations` looks up every track (a `stat` per track; the album is small). With all known, the total is
  formatted by `dur_text` and shown. Otherwise, only while the worker is free, one `CC_DURATIONS` set of this album's missing
  files runs (polled every `AB_DUR_MS` 400 ms, after the cover set when there is one), the results are merged into the table
  and the footer appears. A busy worker, an unreadable track or a missing file shows no footer: the total is shown
  only when every track's length is known. The page leaves the table acquired until destroy; destroy stops its set.
- **Footer:** the Apple Music footer without the label line, its own block at the number column's left edge (x 12, not the
  title's, so it does not depend on the track count). `ab_foot` is a label of the content view (it scrolls with the rows),
  insensitive, 15 px `#AAAAAA`, left-aligned, 20 px high, `AB_FOOT_GAP` 14 px under the last row, `AB_FOOT_R` from the right
  edge. It shows only when the duration is known; otherwise it is hidden and no band is kept. It is not a row (`ab_at`), so
  select mode, All and None never count it, and it takes no touch or press fill. The content (`virtual_h`, `ab_max_scroll`)
  is 52 px longer (`AB_FOOT_GAP + AB_FOOT_TEXT_H + AB_FOOT_PAD` = 14 + 20 + 18) while it shows, so the last row is never
  hidden; when the measurement finishes the content grows at the bottom and the scroll offset does not change. The header
  line is unchanged: the stock song table keeps only a year, which the header already shows.
- **Text:** rounded to the minute, at least one: `49 minutes`, `1 hour, 12 minutes`, `2 hours`; singular and plural by
  count. Parts are keys (`%d minute(s)`, `%d hour(s)`), hours with minutes one key per singular/plural pair so each language
  controls its own join (Chinese and Korean a space, Japanese none), and the line is `%d track(s), %s` as one key per language
  (`13 首歌，1 小时 12 分钟`, `13曲、1時間12分`, `13곡, 1시간 12분`). Russian, Polish and Ukrainian abbreviate the units.
  With the built font the widest case (`999 tracks, 24 hours, 59 minutes`) is 226 px (Spanish) in the 298 px line.
- **Limits:** TagLib's MP3 length is an estimate for constant-bitrate files without a Xing header, otherwise exact to the
  second. Home measures songs ahead of the page ([Home cover build](homecover.md#track-durations)).

## Artwork and shared tint

The page uses the 168 px Cover Flow cache; missing art starts one shared cache-worker
job, polled at `AB_COVER_MS`, with a placeholder until ready.
`m1_tone_get/put` supplies a 64-entry RAM-only LRU cache keyed by
`cc_album_key` (artist + album FNV-1a). Each entry holds key, tone and use stamp:
768 bytes total, no card writes.

A cache miss averages the centered cover square and applies `m1_tone`.
`ah_tint.png` overlays black alpha 64 at the top, rising to 200 at header row 345
and held below it. No art, an empty cache marker or an All albums card leaves black.
The gradient stays fixed while content scrolls.

At rest, the tested header contrast is at least 8.59:1 for the title, 4.06:1 for the
artist and 3.78:1 for metadata. Track numbers over the held tint keep 3.31:1 when pressed.
Rows passing over the brighter top of the gradient have lower transient contrast.

Status-bar tint uses the same single-owner helpers as [Now Playing](nowplaying.md#status-bar).
Background/destroy restore black only while this page owns the bar; foreground retints.
A page left with only its status line (a source's album whose cover came and whose tracks then did not) goes back to a black window
and bar (`ab_tint_drop`): the line's grey (#AAAAAA) is chosen for black and fell to 3.6:1 over a white cover's tone. A cover that comes after that (the cover poll's
callback) does not tint it (`ab_tint_cover` asks for tracks or a wait) but its tone is worked out and kept in the tone cache; tracks that come later tint it again from the tone cache (`ab_cover`). Test: `albumpage` `loading_tests`.
Bright tones may require a darker bar than the top window row to preserve 4.5:1 contrast.

## Playback and selection

Track taps, Play and Shuffle use `so_play` in `patch/songops.c`.
A missing starting file shows Storage unavailable. An unresolved queue starts nothing
and changes no play mode.

Play sets an in-order mode: Shuffle and Repeat one become List play; List play and
Repeat all are retained. Shuffle chooses a random starting track and sets the stock
Shuffle mode for this album queue. Mode changes use the stock notification/config path.
Selection shares Add/Delete operations with [Songs](songs.md).

`pod_open_player` follows the stock row handler's navigation sequence. With
`songerinfoflag` (`0xa04737`) set, it removes windows above an existing
`playing_page`, closes that page, then opens Now Playing with the new queue/context.
The pop loop is bounded at 16; a window that does not close cannot cause an infinite loop.
Library and playback windows must not have close animations that defer this stack change.

## Stock pages

Stock artist/genre/composer rows hide their placeholder icon and use the freed width;
the playing row reserves space for the wave marker. Stock playlist songs retain the
common 64 px library rows; our Playlists entry opens [Songs](songs.md).

The fallback queue drawer (`dialog/playqueue_dialog.bin`) has 44 px rows, muted 18 px
non-playing text and white 20 px playing text, plus a mode-header hairline and left border.
It has no added playing image or header count. The stock `playerjumpinfo_page` uses the
shared wave marker and a 20 px navbar title. See [Queue](queue.md) and [rows](rows.md).

## Pins and validation

`SONGS_PINS` checks `is_playing` (`0x4d9d64`) and album row-builder calls
at `0x524c40..0x524ca4`. This page adds no hook.
Tests cover layout, tint contrast, tone-cache bounds/LRU, playback mode changes, stack
navigation and failures; `test/pod/durations.py` covers the table, CUE math, measuring and the line. Hardware appearance and input remain unverified by those models;
use [device checks](device-checks.md).
