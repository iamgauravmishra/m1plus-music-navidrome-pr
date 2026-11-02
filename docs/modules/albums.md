# Albums

**Sources:** `patch/albums.c`, `patch/grid.c`, `patch/covercache.c`,
`tools/pod_ui.py`. **Tests:** `test/pod/albums.py`, `test/coverflow.py`.
Previews: the Albums panels in `tools/preview_icons.py`.

Albums opens a grid or list in the last selected mode. Tapping an album calls
`cc_open_album`; Back returns to the same position. Cover Flow opens above this page.
If the window cannot open, the Home dispatcher opens stock Albums.

## Layout and state

| Element | Contract |
|---|---|
| Window | `ui/m1plus_albums.bin`; 320 × 450 px with a 50 px navbar |
| Scrolling | `albums_listview` > `albums_scrollview` > `view_grid`, plus `scroll_bar_m` |
| Grid | Two 144 px covers, 12 px margins, 8 px column gap; 190 px cells on a 200 px pitch |
| Grid text | Album 18 px white, artist 15 px grey; one ellipsized line each |
| List | 64 px rows, 52 px covers at (10, 4), text from x 74; title 21 px, artist 18 px |
| Corners | Grid 8 px blended into black; list 4 px in the bitmap alpha |
| Navbar | Back, title, Cover Flow at x 168, view toggle at x 214, Now Playing at x 260 |
| Mode file | `/mnt/data/m1plus/albums-view`: 1 grid, 0 list; otherwise `ALBUMS_DEFAULT_GRID` |

The stock mobile scrollbar is required: the list-view layouter enables vertical scrolling
through it (`0x60b1c8..0x60b1e8`). The content view and `virtual_h` both hold the full
content height as 32-bit integers. Empty content is hidden and insensitive.

The toggle stops a running scroll animation, drops tiles, changes geometry and preserves
the first visible album. It updates the glyph to the other mode and writes the choice with
`home_write_atomic`. Missing required style labels or content widgets close the page.

## Covers and painting

The shared grid supplies tile records, rounded artwork, ellipsis fitting, painting and hit
testing. Recently Played uses the same helpers. Covers come from
`r<album-key>-168.jpg`, reduced by an area average of the centered square.
An absent file or empty “no art” marker uses the placeholder disc.

Twelve resident tiles cover visible cells, prefetch and recent history. Grid artwork uses
about 1.1 MB including the placeholder; list artwork about 130 KB for the ring. The copied
album list adds about 0.3 KB per album. A decode temporarily holds the 168 px source.

Paint draws resident covers and text only: no image decoding, bitmap allocation or timer
creation. Text is measured and ellipsized once per tile. Drawing is limited to the 400 px
viewport; partial text lines are omitted. The stock scroll view clips the canvas.

The 16 ms loader decodes at most one cover per tick, prioritizing visible cells nearest the
viewport center, then one grid row or two list rows ahead in the scroll direction.
Visible tiles are retained; other tiles use LRU replacement. Decoding pauses during a stock
drag or running scroll animation (`grid_moving`) and resumes when it ends.
Backgrounding stops the loader; foregrounding restarts missing work.
If scroll events cannot be registered, the loader polls while the page is open.

## Cache building

The shared `cc_build_*` worker builds missing cache files without blocking page open.
A 50 ms startup timer scans in batches of 64 albums, 20 ms apart, nearest the initial
viewport first. The worker starts after the scan finishes; scrolling does not reorder it.
A 500 ms poll makes placeholder tiles eligible for reload as files arrive.

Only one page owns the worker. Opening Cover Flow releases the Albums build first.
Destroy cancels and joins owned work, frees the set and removes timers.
A refused timer/thread, busy worker or less than 16 MB free space leaves placeholders.
A completed scan with no missing files is not repeated during that page's lifetime.

## Input and validation

The stock scroll view owns drag, fling and end stops; [list gestures](gestures.md) handles
coasting catches. Page listeners return without consuming events. A release on the original
cell within 10 px on both axes opens the album. Drag, abort, backgrounding or a touch that
stops coasting clears the press and opens nothing. List presses use `#333333`.

Tests cover both modes, real stock layout and pointer handlers, large-library content
heights, tile bounds, loader deferral, cache-worker ownership, persistence and failure paths.
Real frame timing and canvas/text appearance require [device checks](device-checks.md).
See [album page](album-page.md) for album opening, [Cover Flow](coverflow.md) for the shared
cache worker and [rows](rows.md) for common library styling.
