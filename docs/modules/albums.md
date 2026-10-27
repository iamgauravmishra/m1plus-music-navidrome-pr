# Albums (grid and list)

Split out of docs/architecture.md and docs/ui.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 5a. Albums (`patch/albums.c`, `patch/covercache.c`, test `test/pod/albums.py`, host test `test/coverflow.py`)

The menu's Albums row (`ACT_ALBUMS`) opens our one Albums page in the mode used last: a **grid** of covers or a **list**
(the stock Albums list is not used from here); one navbar button switches the mode in place, the choice is persisted.
`ALBUMS_DEFAULT_GRID` (`offsets.inc`, 1 = grid) is the mode of a first use. No hook; everything runs from the page's widgets and timers.

- **Page** `ui/m1pod_albums.bin` (`kind='grid'`, `tools/pod_ui.py`): the stock navbar (Back, "Albums", Now Playing)
  plus `btn_albumview` (x 214, 46x50, flush left of Now Playing, `img_btn_style`, the `pod_nav_list` glyph: the view a tap switches to) and
  `btn_coverflow` (`NAV_CF_X` 168, 46x50, flush left of the toggle, the `pod_nav_coverflow` glyph; the title label ends at 168; `al_on_cover` calls
  `coverflow_open`, the menu row's function, over the page: nothing of the Albums page closes, so Cover Flow's Back returns to it), **one**
  `view_grid` (320x400 at y 50, black), a hidden
  `label_status` and four hidden, insensitive style labels that only carry the text styles: `label_row_title` (21 px `#FFFFFF`) and
  `label_row_sub` (18 px `#AAAAAA`) for the list mode, `label_grid_title` (18 px `#FFFFFF`) and `label_grid_sub` (15 px `#AAAAAA`) for the grid. There is no widget per album, no `list_view`, no `scroll_view`.
- **Geometry** (`offsets.inc`): `GRID_COLS` 2 columns of `GRID_COVER` 144 px covers, `GRID_GAP` 8 px apart, centred
  (`GRID_MARGIN` 12 each side: 2 x 144 + 8 + 2 x 12 = 320); under each cover the album `GRID_TITLE_H` 22 px
  high, `GRID_TITLE_GAP` 4 px below it, and directly under it the artist `GRID_SUB_H` 20 px high; cell 190 px, row pitch
  200 px (`GRID_ROW_GAP` 10 between rows); the first row starts 10 px down the content
  and the last ends 10 px above its bottom (`content = 10 + rows x 200`, so two rows fill the view exactly); the content scrolls in the 400 px view,
  clamped to `[0, content - 400]` (one row needs no scrolling). A tile's hit area is its whole 144 x 190 cell.
- **Painting.** The view's own `EVT_AFTER_PAINT` (as Cover Flow's frame): first the covers of the cells that touch the view
  (a tile bitmap, `canvas_draw_image` 1:1, cut to the view by hand), then two text passes, each with one
  `widget_prepare_text_style`: all albums (`label_grid_title`), all artists (`label_grid_sub`), via `al_text`
  (`canvas_draw_text_in_rect`, drawn only when the line lies wholly in the view; the list mode uses the same helper). At most 3 rows x 2 =
  6 cells per frame. The canvas does not clip to the view (the stock paint only
  translates), hence the manual cuts.
- **Tiles and memory.** `GRID_TILES` 12 entries (a frame touches at most 6 grid cells or 8 list rows; the build checks that the ring holds the view,
  the rows ahead and two tiles of history). A tile is a 144x144 RGBA8888 `bitmap_create_ex` (81 KB, flagged opaque) holding the album's cover (the finished tile is cached, not the JPEG):
  the Cover Flow cache file (`<key>-168.jpg`, key of the album record, so the same files) decoded by the stock
  loader and reduced with an **area average** (`cc_box`: each output pixel is the mean of the source pixels its box
  covers, the centred square, alpha over black; nearest sampling shimmers at 168 -> 144). The album and the artist are converted to
  wide chars (`tk_utf8_to_utf16_ex`, at most 47) and, when `canvas_measure_text` says one is wider than the cell, cut
  by a binary search to the longest prefix that fits with an ellipsis (U+2026), the first time it is drawn, never per
  frame. Memory while open: 12 x 81 KB + the placeholder 81 KB (1.08 MB; 1.1 MB is the tested bound) + 5 KB of tile records (an album and an artist of 48 wide chars each), **whatever the
  library**, plus the copy of the stock album list (what Cover Flow keeps too, about 0.3 KB per album) and, for the duration of one decode, the 168 px source (113 KB); closing frees
  all of it (`EVT_DESTROY`).
- **Loading (smooth scrolling).** Paint **never decodes** (`al_on_paint` draws the resident tiles, the placeholder for the others; it allocates no bitmap
  and arms no timer; it only makes the cheap tile record and the text cut). The page's own loader timer (`al_on_load`, 16 ms) decodes **one cover a
  tick**: of the albums in the *window* (the rows in view plus `AL_AHEAD` rows beyond them in the scroll direction, 1 grid row / 2 list rows; `al.dir` follows the last
  movement) that have no tile yet, the cell whose centre is nearest the middle of the view, cells in view before the rows ahead. It is armed (`al_kick`) at open, by every
  scroll and mode change, only if something is missing, re-arms itself while something is, and is removed on destroy and when the mode changes. It invalidates the view
  only if the decoded cell is in view. A tile inside the window is never replaced; otherwise the least recently used goes, so the 2+ tiles of the ring outside the window are the
  history: after a reversal what was just left is still there (no cover is decoded twice in a back-and-forth over the same rows, tested). The decode costs 0.75 to 1.9 M payload
  instructions under Unicorn, a few ms on the device, one per tick instead of two inside a paint.
- **No cache, no art.** An album with no cache file, or the empty "no art" marker, shows the
  stock placeholder disc (`p_default`, reduced like a cover, flat grey if it will not decode) with its title.
- **Background cache build.** Albums with neither a cache file nor the marker are built by the shared worker of
  `patch/covercache.c` (`cc_build_*`, `docs/modules/coverflow.md`) while the page is up: no Preparing screen, no blocking.
  `al_open` only arms a one-shot timer (`AL_BUILD_START_MS` 50 ms): the scan stats every album's file, so it is not part of
  opening. `al_on_build_start` opens a `CC_MISSING` set (refused if Cover Flow or anything holds the worker: then nothing
  starts), queues the albums with `cc_build_near(albums, order, al_first())`: nearest the first album in view first (that
  album, then one after, one before, ... in the displayed order; at most `CC_MAX_JOBS` 4000), and starts the thread. The poll
  (`al_on_build`, `AL_BUILD_MS` 500 ms, page-scoped, re-armed while the worker runs) reads the done counter; when it advanced,
  `al_retry` lets every tile that showed the placeholder because it found no file (`art == 2`) try again if its file exists
  now (it sets `art = 0` and `al_kick`s the loader, which decodes one per 16 ms tick as always); when done is total the set is
  stopped (joined, freed) and the poll ends. `EVT_WINDOW_TO_FG` (back from Cover Flow or an album page) offers the build again
  (`al_build_later`: nothing is armed while one runs or is pending). The Cover Flow button stops the page's build first
  (`al_build_end`: one worker at a time; Cover Flow then builds what is missing with its Preparing screen). `al_on_destroy` removes
  the timer, cancels and joins the worker and frees the set (only a set this page owns, `al.own`). The queue is made once, at the
  start: scrolling far away does not re-order it. No space under 16 MB, no thread or a refused timer: no build, the grid is as before.
- **Touch.** `EVT_POINTER_DOWN/MOVE/UP/ABORT` on `view_grid`, grabbed by the window while a finger is down (as Cover
  Flow's layer). Pointer events carry screen coordinates (`widget_on_pointer_down_children` passes the same event down the
  tree, `0x6714ac`), so every position goes through `widget_to_local(view)`, the same call `widget_find_target` makes. A drag
  starts after `AL_DRAG` 5 px of **vertical** travel and the content follows the finger from there (the origin is the 5 px point: no jump; horizontal travel
  does not start it); the release counts as a position too, so sparse events still scroll to where the finger ended. A release within `AL_SLOP` 12 px on both axes
  with no drag is a tap (so vertically the tap tolerance is the 5 px of the drag threshold, sideways 12): the cell under it (cover or title, not the gaps, margins or the empty tail of
  the last row; none outside the view), the same one as under the press, opens its album. A touch that stops a fling is never a tap.
  **Fling**: a release of a drag under 200 ms after the second-to-last sample coasts; speed = travel / time of those samples in Q16 px per ms, at most 3 px/ms (`AL_MAX_FLING`,
  the old 48 px per tick). The timer (16 ms) is only a wake-up: each tick reads `time_now_ms`, steps the speed once per elapsed millisecond (`v -= v / AL_DECAY`, 248:
  (247/248)^16 = 15/16 a 16 ms tick, the old friction), adds it to a Q16 position (the remainder is kept), and the fling is over below 1/32 px/ms or when the content
  hits an end, where it stops exactly. The distance does not depend on the timer's pace (a late or irregular tick lands in the same place; tested against a model: about 410 px for a
  40 px / 24 ms flick, about 740 px at the cap).
- **Album.** `cc_open_album(0, row)` (`patch/covercache.c`): the stock sequence Cover Flow uses (`loadAlbumList(0xf003, 0)`,
  `albumcoverinfo_init`, `batchadd_albumcover_task(0, 0)` so the cover thread runs, `navigator_to_with_context("albuminfo_page",
  0xf003 | row << 16)`; section 4 and 8). Back returns to the grid where it was.
- **List mode** (the same page and view). Rows of `LIST_ROW_H` 64 px (the library rows'
  pitch, `rows.json`), content `count x 64`, scroll clamped to `[0, content - 400]`. Per row, in view coordinates: the pressed fill
  `LIST_PRESS` `#333333` over lines 0..62 (only the row under a finger), the cover `LIST_ART` 52 px at (`LIST_ART_X` 10, 4) (the tile bitmap, the Cover Flow cache
  box-reduced to 52, cut to the view by hand), the hairline `LIST_HAIR` `#222222` on line 63 (`canvas_set_fill_color` + `canvas_fill_rect`, both new
  pins: `0x644220` and `0x644e4c`; `color_t` is one word, `lcd_set_fill_color` stores `$a1` at `lcd+0xbc`; the rect is cut to the view by hand), then
  two text passes: all titles with the style of the hidden label `label_row_title` (21 px `#FFFFFF`, left, middle) in a `LIST_TEXT_W` 234 x
  `LIST_TITLE_H` 24 rect at (`LIST_TEXT_X` 74, row + 7), then all artists with `label_row_sub` (18 px `#AAAAAA`) in 234 x 20 at (74, row + 33): one
  `widget_prepare_text_style(label, canvas)` per pass (two a frame, none new in the stock code), each text drawn only when wholly inside the view. Each text is
  converted to wide chars when the tile is made and cut with an ellipsis (`al_fit`, the grid's binary search with the canvas' own
  `canvas_measure_text`, in the text's own style) the first time it is drawn; never measured again. Tiles are the grid's ring and loader (12; at most 8 rows are in view, the next 2 in the
  scroll direction are prefetched), 52 px bitmaps (11 KB, 130 KB for the ring) in this mode, the same placeholder disc at 52 px.
  A tap on a row (any x, lines 0..63) opens its album as a grid tile does (`cc_open_album`). A finger down on a row sets `press`, a move
  past the drag threshold (5 px) or the 12 px slop, the release and an abort clear it; the view is invalidated on each change, nothing else repaints.
- **The toggle.** The navbar button (`btn_albumview`, x 214, shared with the other Pod pages) switches the mode **in place**: no window opens or
  closes. `al_set_mode`: stop a fling and the loader timer (re-armed for the new mode), drop every tile and the placeholder (their size is the old mode's) and make
  the placeholder at the new size, keep the first album in view (grid -> list: the first row with a visible cell, `row x 3` x 64; list -> grid:
  `(album / 3)` rows down), set the three icon properties of the button to the glyph of the *other* mode
  (`pod_nav_grid` in list mode, `pod_nav_list` in grid mode; the same `widget_set_prop_str` pattern as the Artists toggle), invalidate the view, and
  save the mode (`home_write_atomic`). Nothing is opened, so nothing can be left behind. If the page's asset lacks the two style labels the
  page leaves again (`navigator_back`) as it does without `view_grid`.
- **Persistence.** `/mnt/data/m1pod-albums`: `1` the grid, `0` the list, missing or anything else
  `ALBUMS_DEFAULT_GRID`; written as the Start-in setting is (`home_write_atomic`: temp file, `fsync`, `rename`, directory
  `fsync`) at every toggle. The menu's Albums row (`albums_open`) opens the page in that mode. If the window cannot open at all it opens the
  **stock Albums list** through the Home dispatcher (id 5, `pod_home_open`); the stock list stays reachable from Shanling Home, unmodified.
- **Shared helpers** (`patch/covercache.c`, used by `coverflow.c` and `albums.c`, the next page that shows covers, the landscape
  Cover Flow, can use them as they are): `cc_fnv`, `cc_album_key`, `cc_path`, `cc_file_size`, `cc_url` (the cache file's `file://` url
  if it holds a picture), `cc_decode(widget, url, unload, size, box, out)` (stock loader, centred square, nearest or box to `size`),
  `cc_sample` / `cc_box` (the pure pixel functions, also built for the host), `cc_copy_list`, `cc_albums` (the stock Albums list copied),
  `cc_open_album(artist_row, row)` (the stock open sequence, library or one artist's). The cache *builder* (the one worker thread, `cc_build_*`) is there too: Cover Flow's Preparing screen, Rebuild Covers and the Albums page's background build use it.
- **Risks.** `widget_prepare_text_style` on a hidden, insensitive label takes the font, size and colour from that label's style (assumed: it reads
  the style, not the visibility; if not, the list's texts would use the view's 16 px white); `canvas_fill_rect` is assumed to fill the colour
  `canvas_set_fill_color` was given (one word, r,g,b,a) and, like the other canvas calls, not to clip to the view (a clip would be harmless;
  the payload cuts by hand); the stock canvas fill colour is left as the list set it (the stock widgets set their own before each fill). None of
  this was checked on the device. Unicorn cannot judge the real frame time of 7 rows (about 6,000 payload instructions steady, plus 7 blits, 14 text
  runs, 14 fills), nor the stock text and fill calls.

### The Albums page (`ui/m1pod_albums.bin`, `docs/modules/albums.md`)

(the two Albums panels of `docs/release-preview.png`, grid and list mode with row 2 pressed: `PI.albums_grid` / `PI.albums_list` in `tools/preview_icons.py`, sample covers.)
The Albums row opens this page in the mode used last (first use: the grid, `ALBUMS_DEFAULT_GRID`); the stock Albums list is not part of it
(it stays under Settings > Home Screen > Shanling Home, unmodified).
The grid mode is the standard navbar over one 320x400 `view_grid`: two 144 px covers a row, 8 px between them and 12 px
margins (Apple Music style), the album in 18 px white and under it the artist in 15 px `#AAAAAA`, one line each (cut with an ellipsis at the
cover's width, left-aligned; a 22 px and a 20 px line, 4 px under the cover), so a tile is 190 px tall; 10 px between rows, the first row 10 px from the navbar and the last 10 px from the bottom
(two rows fill the view exactly); a tap anywhere on the 144 x 190 tile (cover or text) opens the album; no scroll bar (the content
follows the finger and coasts). The covers have square corners. Covers are the Cover Flow cache reduced with an area average; an album without a cached cover
shows the stock disc on `#2B2B2B` (as Cover Flow's placeholder), still with its album and artist. Greys and fonts are the other pages':
`#000000` background, `#FFFFFF` text, `img_btn_style` glyph buttons.
The list mode is the library rows' look on the same view: 64 px rows on black, a 52 px cover at (10, 4) (the same cache, box-reduced to 52; the
same disc as placeholder), the album in 21 px `#FFFFFF` and the artist under it in 18 px `#AAAAAA`, both from x 74 (12 px after the cover) to a 12 px right margin (234 px) and cut
with an ellipsis there (no chevron: a tap opens the album, as on the grid), a 1 px `#222222` hairline closing each row, and the row under the finger
filled `#333333` (the stock pressed row) until the release; a drag (5 px) or 12 px of travel cancels it. Scrolling, coasting and the end stops are the grid's. A text
that is not wholly inside the view is not drawn, so a row cut by the navbar or the bottom edge shows its cover and hairline first.
The toggle is a 24 px glyph in a 46x50 button at `NAV_VIEW_X` 214..260, flush left of Now Playing (260..320), the slot every Pod page uses (Albums,
Artists, Cover Flow's landscape switch); the title label ends at its left edge. It switches the mode in place (no window opens, nothing flashes), swaps its
glyph (`list` on the grid, `grid` / `layout-grid` on the list) and keeps the first album in view. Pressed is `#777777` like the other navbar glyphs.

The Albums page (grid and list) has a second button, **Cover Flow** (`btn_coverflow`), flush left of the toggle at `NAV_CF_X` 168..214 (46x50, same style, the
`pod_nav_coverflow` glyph = the menu row's `gallery-horizontal`). The navbar reads Back, title, Cover Flow, toggle, Now Playing; the title label ends at 168 (132 px
from x 36; "Albums" fits in all 16 languages, tested). A tap opens Cover Flow as the menu's row does (the playing album, else the last), over the Albums page, so Back returns to it.
The other Pod pages (Artists keeps its single toggle slot at 214; Cover Flow's navbar has none) are unchanged.
