# Recently Played

The Home menu shows up to six recent albums in a two-column shelf below Daily Mix. Covers use
the shared Albums grid, with album and artist labels. The shelf scrolls with the menu and is
absent from the normal menu instance.

Sources: `patch/recent.c` (recording/file/shelf), `patch/grid.c` and `grid.h` (cells),
`patch/menu.c` (`menu_shelf`), and `tools/pod_ui.py` (`shelf()`). Constants: `SH_*`, `RC_*`
and `GRID_*` in `offsets.inc`. File model: `tools/pod_recent.py`; tests: `test/pod/recent.py`;
preview: `tools/preview.py` (`shelf_image`, `minibar_page`).

The feature adds no stock hook or address. It uses its window/widgets, events and one page
timer. See the final section for the boundary between emulation evidence and device testing.

## Layout (shelf-local y; `tools/pod_ui.py` SH_*, `patch/offsets.inc` SH_* and GRID_*)

The shelf is `pod_shelf`, a `view` 310 wide (`SH_W` = the scroll view's width), a child of `pod_scrollview` that follows the last shown row (Settings) and precedes the mini bar's spacer, hidden and insensitive in
the asset. Its **height depends on the albums**: `ceil(albums / 2)` rows of covers, `SH_H(n)` = `SH_TOP + n * GRID_CELL_H + (n - 1) * GRID_ROW_GAP + SH_BOTTOM` = 234, 434 or 634 for 1, 2 or 3 rows (1-2 albums one row, 3-4 two, 5-6 three); the asset has the largest (`SH_HMAX`) and the payload sets the real one
with `widget_resize` before the rows are arranged, and `menu.c` sums the shelf's own height into `virtual_h`.

| part | geometry | |
|---|---|---|
| header `pod_sh_head` | label at (10, 17), 300 x 22; **20 px** white `hscroll_label` (`only_parent_focus`, `ellipses`: never scrolls, cut with an ellipsis), `sensitive=false`; text key `Recently Played` (`pod_i18n`, the menu item's) so all 13 languages follow Settings > Language | ink 20..36: **20 px of air above it** (the Settings row ends at 0, so the header reads as a new section), 8 px below it to the covers; the label insets its text 2 px, so it starts at x 12 like the covers |
| cell | the Albums grid's, **not copied**: `GRID_COVER` 144 covers at x `GRID_MARGIN` 12 and 164 (`GRID_GAP` 8), the first row at y 44 (`SH_TOP` = 17 + 22 + 5), row pitch `GRID_CELL_H` 190 + `GRID_ROW_GAP` 10 = 200 | two covers end at x 308, inside the 310 px scroll view (the 10 px strip beside it holds the scroll bar): 12 px on the left, 12 on the right counting the strip, so the Albums geometry fits unchanged |
| cover | 144 x 144, the four **8 px** (`GRID_R`) corners blended into the black behind them, the tile opaque | the same corners as the Albums grid (one constant); 8 px is 5.5% of the cover, between Now Playing's 12 on 264 (4.5%) and the mini bar's 5 on 36 |
| album | `GRID_TITLE_GAP` 4 under the cover, 144 x `GRID_TITLE_H` 22, **18 px** white, one line, ellipsis | text style from the hidden label `pod_sh_title` |
| artist | directly under, 144 x `GRID_SUB_H` 20, **15 px** `#AAAAAA`, one line, ellipsis | `pod_sh_sub` |
| air below | none (`SH_BOTTOM` 0): the last artist line's box ends the shelf, so scrolled to the end with the bar up it is `MB_GAP` (8) above the pill, as the last row was | |

Cells fill row by row (cell i is column `i % 2`, row `i / 2`): 1 or 2 albums are one row, 3 or 4 two rows, 5 or 6 three rows: `SH_TILES` = `GRID_COLS` x `SH_ROWS` (3) = `RC_MAX` = 6, so the shelf shows every album the file keeps (`recent.c` `#error`s if the three differ; `recent.py` asserts it).
The header is a stock label child of the shelf (the stock paint draws it, so the language and the ellipsis are the stock's); the covers and the text lines are painted by the shelf itself
(below). The widest translation of the header at 20 px in the shipped font is Spanish and Ukrainian, 189 px of the label's 296 (`test/pod/recent.py` measures all 13 with `StbText`: none needs the
ellipsis). The 20 / 8 px air is the result of measuring `tools/preview.py`'s render (`peek.py runs`): header ink 20..36 below the Settings row's hairline, covers at 44.

With the shelf (six albums) and the mini player bar up a menu of 8 rows (416 px; the default menu has 6, so everything below is 104 px higher) is 416 + 634 + 64 (`MB_PAD`) = 1114 px in a 430 px list; at the top the shelf's first row is already within a row of the
viewport (416 < 430), at the end the last row fills the bottom of the list above the pill. One album: 416 + 234 + 64 = 714 px.

## The list file (`/mnt/data/m1plus-recent`, `tools/pod_recent.py` is the model)

```
M1R2\n
<id: 8 hex>\t<cover key: 8 hex>\t<0|1>\t<album>\t<artist>\t<path of a track of the album>\n        (one line per album, most recent first, at most 6)
```

**Identity.** The id is FNV-1a of the album title with ASCII letters folded to lower case (`rc_id`), and nothing else: **not the track's artist**. Evidence: the stock album list is
`getAllAlbum` (`0x4ea3c4`), `select id,album,songer,fileurl from %s group by album COLLATE NOCASE` (string `0x74bad8`, referenced at `0x4ea438`): it groups by album title alone, NOCASE,
and its rows do not even select the album artist (the artist rows' `GetAllAlbumArtist`, `0x4ea6e4`, groups `albumsonger`; the song record has the album artist at `+0x24`, but the album
query leaves it out). So an album is the same album exactly when the stock list has one row for both: every track of a compilation, whatever its artist tag, is one shelf entry and one file
write, and two albums of one title in different folders are one row in the stock list and one entry here (a tap opens that row). (The directory-based identity was the fallback; it was not needed.)
The RAM fast path compares this id with the most recent entry's: no file access, no stock call.
The **cover key** is the Cover Flow cache key (`cc_album_key`, FNV of artist then album, the cache's `<key>-168.jpg`) of the album ROW; until the row has been looked up (flag `0`) it is the
playing track's own key (right whenever the track's artist is the row's), after (flag `1`, `rc_resolve`) the row's, and the artist is then the row's too. An `M1R1` file (identity = the track key)
is not read: it reads as empty, no compatibility. Read **strictly**
(`rc_load`): the first line exactly the magic, at most `RC_MAX` (6) lines of exactly six tab-separated fields, a non-zero id and cover key, no id twice, the flag 0 or 1, a non-empty
album, no control byte (below 0x20, or 0x7f) in a field, every line ended by a newline, an album or artist under `RC_STR` (96) bytes, a path under `RC_PATH` (256), the
whole file at most `RC_FILE_MAX` (3072) bytes. Anything else, or no file, or an unreadable one, is an empty list. Only the magic line is a valid empty list.
When an entry is made (`recent_note`) control bytes in the tags become spaces and a name or path longer than the field is cut before a UTF-8 continuation byte (never inside a
sequence), so a tag can never make the file invalid; the key is computed from the original tag, so it is still the album's. The path is the playing track's (refreshed
when an album moves to the front); it is the last way to find the stock album row (below).

## Recording

`recent_note(track)` is the one shared helper. Callers: the mini player bar's `mb_work` (the Home menu in front, every 500 ms tick) and Now Playing's `np_work` (its 500 ms tick,
`recent_note(cc_playing())`, and nothing else: no stock query runs from that tick). It is cheap while nothing changed: **the album key is compared with the most recent one held in RAM first** and the function returns,
touching no file and calling no stock function but the key hash. An empty album tag is not recorded. A new album goes to the front, an album already in the list moves
there (not added twice), the list is capped at six (the oldest falls off), and RECENT_FILE is written with `home_write_atomic` (temp file, `fsync`, `rename`, directory `fsync`):
**one write per change of the most recent album**, none otherwise. A failed write leaves the RAM list current and is tried again with the next change (the next
to-foreground read drops what the card does not hold). The first call reads the file (lazily), so a note before any shelf exists starts from the file. The bar's tick
calls `recent_refresh()` when `recent_note` returned 1, so a new album shows under a menu in front at once.
Recording runs whether or not the shelf is switched on (the switch only shows or hides it).

## The shelf (`recent_start`, `rc_*`)

`home_menu_opened` (patch/home.c) calls `recent_start(win)` after `minibar_start` for the Home instance only (when `hm_fill_window` found the navbar and the list). Kill switch
(`home_off()`): nothing is looked up.

- **Start** looks up `pod_shelf`, `pod_scrollview` and the two style labels `pod_sh_title` / `pod_sh_sub`, registers `EVT_DESTROY`, `EVT_WINDOW_TO_BG`, `EVT_WINDOW_TO_FG` on the window and
  `EVT_AFTER_PAINT`, `EVT_POINTER_DOWN`, `EVT_POINTER_UP`, `EVT_POINTER_ABORT` on the shelf, arms a **one-shot `RC_FIRST_MS` (150 ms)**, registers `EVT_SCROLL` on the list (refused: the covers are then made
  as soon as the shelf is shown, `rc.noscroll`), makes the grid (`grid_init`, six tiles, rounded corners), and only then reads the file and the setting and, if there is an album and the switch is on, sizes
  and shows the shelf (`widget_resize`, then `menu_shelf`: visible and sensitive together). The menu **decodes nothing** at its first paint: a tile has no cover until a tick has made it. Any widget missing,
  any registration, the grid's memory or the timer refused: the shelf is never shown and nothing is moved (`rc_stop` clears the state and frees the grid; a handler that was registered finds no window of ours).
  The header label is not looked up: the payload does not need it (a tree without it still shows the cells).
- **Cells** (`patch/grid.c`, the Albums page's code): `grid_tile_t` per cell (the converted texts, the cover key, a 144 x 144 RGBA bitmap, `bitmap_create_ex`, 81 KB **each, 486 KB for six** (497,664 B), freed on destroy,
  plus one **shared placeholder disc** bitmap of the same size when some tile has no picture: 567 KB at most, made when first needed; but see the decode bound below). The cover (`grid_art`) is the Cover Flow cache file of the entry's cover key
  (`cc_url`) box-reduced to 144 px (`cc_box` via `cc_decode`, the grid's own decode), the four `GRID_R` (8 px) corners blended into black once per tile (`grid_round`, `pod_corner_fill`'s table; the tile stays opaque); no file, the empty "no art" marker or a picture that does
  not decode: the shared disc (`p_default`, else flat grey `GRID_GREY`). No bitmap memory: the texts alone, the tile still opens its album. The file is the entry's **cover key**: the album row's once resolved
  (below), else the playing track's key (right when the track's artist is the row's), else the disc. When a resolution changes an entry's cover key the tile is made again.
- **Resolving the cover key** (`rc_resolve`): `cc_albums()` loads the stock album list (`loadLocalClassList(0xf003)` = `getAllAlbum`, then a copy) and the row is matched by title (NOCASE; the
  "Unknown Album" row never) then by the recorded path; the entry takes `cc_album_key(row)` and the row's artist, flag 1, and the file is written once more. The list load grows with the
  library (the stock SQL query is not emulated; the payload's part of the to-foreground that resolves, the copy walk and the title scan included, is measured for 100, 1000 and 4000 albums in
  `test/pod/recent.py` and bounded there, but the query is the stock's), so it is done **never at boot, in a tick or in paint**, and **only from the menu's to-foreground**: **one unresolved entry
  (of the three shown) per event, only `RC_RESOLVE_MS` (5000 ms, `time_now_ms` against the stamp taken in `recent_start`) or more after the menu opened**, so never inside the boot guard's window
  and never from `recent_start` or the first one-shot. **Never from Now Playing's tick** (it was, up to V2.1oG): the query leaves the album list in `*pdeq_showlist` (and "Albums" in
  `nagvation_title`), and the page under Now Playing is often a stock song list that draws its rows from that list and plays from it. Its to-foreground does not read again when its class
  is unchanged (`allmusic_page` `0x527c28`), so Back from Now Playing showed the album rows with the folder icon (`list_get_left_icon` `0x4d972c`: type 4 = `icon_folder`) in a playlist's
  songs page, and a tap there played from the album list. An album the library has no row for is asked once (`rc.tried`, per page) and
  stays unresolved: it keeps the track key's file or the disc. A fully resolved list never loads the album list except on a tap.
- **When the covers are decoded** (the shelf is at the foot of the list, so most of the time it is below the viewport): **lazily, once the shelf is in view or about to be.** `rc_near(i)`, **per cell**: the cell's top is less than one row
  (`POD_ROW_H` 52) below the bottom of the viewport (`shelf y + SH_TOP + row x 200 < yoffset + h + 52`), so the rows far below the viewport wait and **the cells are made row by row, top row first** (index order, the nearest to the viewport as the list scrolls down). Bound: at the top of the default menu only row 0 (162 KB for its two covers) is resident, row 1 when the list has scrolled about 250 px, and all six (486 KB) only once the third row is within a row of the viewport (scrolled towards the end); never more than the rows within reach. `rc_next` answers "no tile waits" otherwise, so the one-shot (`rc_first`, 150 ms after start) ends without a decode and arms
  nothing for a shelf out of reach; **the list's `EVT_SCROLL`** (`rc_on_scroll`, fired by every offset change: drag, fling, scroll animation) re-checks and arms the tick when the shelf comes within a row, and the
  **to-foreground** re-checks too (`rc_apply` -> `rc_kick`), so a shelf already in view is made right then. Then **one cover per `RC_TICK_MS` (30 ms) tick**, never in paint; the tick ends itself
  when none waits or the shelf was scrolled away again. In a menu of 8 rows (shelf at y 416) the first row is within a row of the viewport already at the top, so its two covers are made after the one-shot;
  in a menu of 17 shown rows (the shelf at y 988) nothing is decoded until the list is scrolled to within a row of it. Only while the window is in front: `EVT_WINDOW_TO_BG` removes the timer, `EVT_DESTROY` removes
  it and frees the grid. A window started over one that never said it was gone replaces its state.
- **Paint** (`rc_on_paint` -> `grid_paint`, the shelf's own `EVT_AFTER_PAINT`, after the stock paint drew the header): the resident bitmaps with `canvas_draw_image` (the shared disc for a tile without a picture), then the
  albums in the album style and the artists in the artist style (`widget_prepare_text_style` of the two hidden labels, one style at a time). Each text is converted to wide characters when the tile is set and **cut with
  an ellipsis once**, the first time it is drawn, measured with the canvas' own font (the Albums grid's cut). Paint allocates and decodes nothing. No manual clipping: the scroll view clips its children to its rectangle
  (`scroll_view_on_paint_children` sets the canvas clip with `canvas_set_clip_rect`, `0x610ec4`), so a cover or a line below the list's bottom edge is cut exactly as a row is, and the mini bar's pill, a later sibling of
  the list, is painted over the shelf.
- **Refresh**: `EVT_WINDOW_TO_FG` (after an album page, Now Playing, Settings, a dialog) re-reads the file and the switch, then `rc_apply`: the tiles are rebuilt for the six albums; **a tile whose album
  (and cover key) moved to another cell keeps its cover**, the others are made again (the bitmap of a tile that went is freed), a placeholder tile whose cache file exists now is queued again (the Albums page builds
  covers in the background). The shelf is shown, resized and hidden as the list and the switch say (`menu_shelf`, the list keeps its place, clamped to the new range). The mini bar's tick does the same without
  reading the file (`recent_refresh`) when it recorded a new album under a menu in front.

## Touch

The shelf is one `view` with its own hit areas, not a row. A **cell** is its cover and its two text lines (`grid_cell_at`: x from `tile_x(i)`, 144 wide, y from the cell's top to its artist line's bottom, 190 high);
the header, the margins, the 8 px gap between the covers, the 10 px between the rows and a place with no album are dead. The header label is insensitive, so a touch on it is the shelf's
(`widget_find_target`, tested with demo's own code) and opens nothing. Every cell is reachable once its row is scrolled into view (tested at the scroll positions that bring each one in); a cell below the list's
bottom edge cannot be touched (the touch is outside the list), the Settings row above the shelf stays reachable, and the mini bar's pill, a later sibling of the list, takes its area first.

- The shelf registers pointer down, up and abort and **never consumes an event** (it answers `RET_OK`), takes no grab and draws no pressed look. The stock `scroll_view` takes every drag: a vertical drag that
  starts on the shelf scrolls the list as on any row (`scroll_view_on_event` grabs at 10 px; it sends its children `EVT_POINTER_ABORT` then, so `rc_on_abort` forgets the press).
- A press that begins on a tile (`rc_on_down` remembers the tile and the screen point; `widget_to_local` is the stock one, which includes the scroll offset) and is released **closer than `RC_TAP_PX` (10) to
  it on both axes**, on the same tile, opens that album. Ten pixels is the scroll view's own drag threshold (`scroll_view_is_dragged`, `slti 0xa`; `patch/scroll.c`'s `SC_DRAG_PX`), so the two rules
  meet: a press the list took as a drag never opens an album, and a quick flick released far away with no MOVE between is no tap either (`sc_up` sends the abort before the
  shelf sees the up, and the shelf's own distance check says the same).
- **A touch that stops a coasting list presses nothing**: `patch/scroll.c` `sc_down` ends the animator and swallows the down, so the shelf never sees it, and its up has no press to complete (`rc.down` is 0). `test/pod/recent.py` runs the same
  gesture without the hook: stock opens the album (the hole the hook closes, which the rows have too).
- The menu going to the background (`rc_on_background`) forgets a press.

**Opening** (`rc_open`, on a tap only; never at boot, in a tick or in paint): `cc_albums()` loads the stock album list (`loadLocalClassList(0xf003)`) and copies it; the row is found by **the entry's cover key**
(`cc_album_key` of the row's artist and album), else by **the album title** (ASCII case aside, `cc_nocase`; the "Unknown Album" row, id -1, never), else by **the recorded track path** (the row's
first track); the copy is released and `cc_open_album(NULL, row)` runs the Albums grid's own stock sequence (`loadAlbumList(0xf003)`, `albumcoverinfo_init`, `batchadd_albumcover_task(0, 0)`,
`navigator_to_with_context("albuminfo_page", 0xf003 | row << 16)`). Not found (the album is gone, an empty library, no memory): nothing happens (no toast: the stock ones are not trivially
available without a new pin).

## The shelf after the rows (`patch/menu.c`)

(The Daily Mix card's section `pod_daily`, `docs/modules/dailymix.md`, sits between the shown rows and the shelf: the shelf's y is the rows plus the section's height while the card is shown, and `virtual_h` sums both. The paragraph describes the list as it was before the card: with the section hidden, which is the default until a mix exists, nothing below changes.)

The stock `list_view` layouter (`children_layouter_list_view`, `0x60b12c..`) puts every **visible** child at the running y in **child order** and sums the children's own heights into `virtual_h`
(the model the mini bar's `pod_pad` spacer proved). So the order of the scroll view's children is: **the shown rows (menu items, Extras, Settings), the shelf, the hidden rows, the spacer `pod_pad`**
(`mn_arrange`, the old `menu_arrange` body, restacks them with `widget_restack`; the hidden rows are skipped by the layouter, so between the shelf and the spacer they change nothing). The rows keep
their places (y 0, 52, ...); the shelf sits right after the last shown row; the spacer after the shelf; `virtual_h` = rows + the shelf's **own height** (`widget_get_prop_int(shelf, "h")`: one or two rows
of covers) + the spacer when visible. A hidden shelf (no album, the switch off) is skipped by the layouter and by the hit test (hidden **and** insensitive), so the menu is exactly as before.
`menu_shelf(win, on)` (used by `recent.c`) shows or hides it, or arranges again when it is shown (its height may have changed), keeping `yoffset` (clamped to `virtual_h - h`): **a list at the top does not
jump** when the shelf comes or goes, since nothing is above it that moves; if the asset is not ours it puts the visibility back. `menu_arrange` (open, and every to-foreground: `on_menu_fg`, which scrolls to
the top as before) reads the shelf's visibility and height like the spacer's. `test/pod/recent.py` runs **demo's own layouter** (`window_manager_check_and_layout`, `list_view`, `scroll_view`,
`widget_set_visible`/`move`/`resize`/`restack`, the pointer code) on a tree of real widget structs: for four saved menus (the default, none, a reordered one, the same with Extras hidden), with and without the mini bar's spacer and with 0, 1 and 6 albums (the shelf's height for every count from 1 to 6 in the grid's own tests; three rows for 5 and 6, scrolled to the end the last artist line is MB_GAP above the pill, every cell reachable once its row is scrolled into view):
the rows are at 52 n, the shelf right below them at the height its albums need, `virtual_h` is the sum, the children stay in the order above, and repeated relayouts, the menu's own arrangement, a pull-down
snapshot's relayout and the bar coming and going change nothing. `test/pod/pulldown.py` section 6 (the spacer alone) is unchanged.
Scrolled to the end with the bar up, the shelf's last line ends exactly `MB_GAP` above the pill (`MB_PAD` 64 below the shelf, the pill at list y 374: tested).

## The setting (Customize > Home Screen > Recent Albums)

A switch row (`ACT_SHELF` 16, `pod_pages.HOMESET_PAGE` row 1, the stock on/off image `sset_on` / `sset_off`), **on by default**, saved like the other switches: `/mnt/data/m1plus-shelf`, `0\n` off,
`1\n` on, no file or anything but `0` = on (`recent_setting`, `recent_toggle`: `home_write_atomic`, a failed save changes neither the file nor the image). The menu reads it at start and at every to-foreground,
so the shelf follows the switch when Settings is closed. The label is its own key **"Recent Albums"** (13 languages, `tools/pod_i18n.py`) instead of the menu item's "Recently Played": that text is too wide for the
switch row in Spanish (202 px of 195) and Ukrainian (197 of 195); the row uses the item's clock glyph (`pod_ic_recent`).

## Failure behaviour (every one is the plain menu)

The kill switch, a missing widget (shelf, list, either style label), a refused `widget_on` (any of the seven), no timer, a menu asset that is not ours (a row missing: `menu_shelf` puts the visibility back),
an unreadable or malformed file, the switch off: the shelf is never shown and nothing moves. No bitmap or a cover that does not decode: the shelf shows with its texts, or the placeholder / grey. An album that
is gone from the library: a tap does nothing. Nothing runs in the main loop; nothing but this runs at paint but `rc_on_paint` (resident bitmaps and text draws).

## Verified in emulation only

All of it (`test/pod/recent.py`): the stock calls (`loadLocalClassList`, `loadAlbumList`, `albumcoverinfo_init`, `navigator_to_with_context`) are the harness's mocks, as for the Albums grid; the layouter, scroll_view and pointer
code are demo's own. Not seen on the device (`docs/modules/device-checks.md`): the look (the header's size and spacing in the real font, the covers' rounded corners on the real lcd), the cost of a decode tick (144 px, box filter), and the touch feel (no pressed look on a cell). The clipping at the list's edges follows from the stock code (`0x610ec4`), not from a device.

The shelf's loader checks once per second for as long as covers remain pending while the screen is off, then resumes on its first lit check and stops when covers are loaded.
