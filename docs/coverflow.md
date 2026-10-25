# Cover Flow (M1 Pod)

A cover carousel over the stock Local Music albums, ported from
[q2-pod](https://github.com/DiamondBond/q2-pod)'s `patch/coverflow.c` (MIT; see `NOTICE`) to the
M1 Plus's 320x480 portrait touchscreen. It is a page of the M1 Pod payload
(`docs/payload.md`), opened from the **Cover Flow** row of the M1 Pod menu, and it installs **no
new hook**: everything runs from that page's own widgets, its own timer and its one worker thread.

Preview (approximate, PIL): `docs/coverflow-preview.png`, and the raw frame
`docs/coverflow-preview-rest.png`.

## Hardware result and fixes (V2.1dD -> V2.1dE)

**V2.1dE** (`0806ade2…`) on the device, 2026-10-25: **works** as intended per the user — covers
swipe and tap, the album's track list is readable and scrolls, tracks play, and the M1 Pod menu
scrolls.

**V2.1dD** (`591880e8…`) on the device: **swiping the covers works**. On V2.1dC the first-run build
had already produced **107 thumbnails (14 MB)** in `/mnt/mmc/.coverflow`, so the extraction path and
the worker thread work on hardware. Two problems remained:

1. **Track list unreadable** — a white list with white text; the text showed only while a row was
   pressed. *Cause:* the rows were bare `list_item`s with no style, so the theme's default
   `list_item` style applied (light), under labels given white text. *Fix:* the rows are now built
   exactly as stock builds its scrolling rows (`systemset_sysset_page_init` @`0x4adb7c`): a
   `list_item` themed **`list_item_style`** holding an `hscroll_label` themed
   **`srlabel_leftwhite21_style`** (white, 21 px, left; `only_parent_focus`, ellipsis). The list
   itself gets black inline styles in every state, set in the string form the assets use.
2. **The M1 Pod menu does not scroll.** *Cause:* a normal window here is **450 px tall**, not 480:
   it sits under the 30 px `system_bar` (68 stock pages end exactly at y = 450, e.g.
   `systemset/sysset_page.bin`'s list spans 50-450; only fullscreen windows such as
   `screensaver_page` use 480). The menu's list was 430 px tall at y = 50, so its bottom 30 px were
   off the window, and its nine 47 px rows (423 px) were *shorter* than the list, so there was
   nothing to scroll. The track list (`view_tracks`, 430 px) had the same 30 px overhang. *Fix:* all
   our pages lay out in a 450 px window (`CLIENT_H`); the menu list is 400 px with fixed 52 px rows
   (nine rows = 468 px, so it scrolls), built with the structure and properties of `sysset_page`'s
   list (`list_view` with `default_item_height` and black states > 310 px `scroll_view` with the
   speed scales + `scroll_bar_m`), and its rows are the same stock `list_item` rows as above —
   the widget every stock list uses inside a `scroll_view`. `view_tracks` is 400 px.

## Hardware result and the touch fix (V2.1dC -> V2.1dD)

**V2.1dC** (`282a5803…`) was flashed by the user: it boots, the menu's Cover Flow row opens the page,
the "Preparing covers" screen appears and the navbar (Back, Now Playing) works — but in the cover
area **neither taps nor swipes did anything**, and the user also could not scroll the menu.

**Root cause.** This demo's AWTK hit test never looks at `visible`. `widget_find_target_default`
(`0x6747d4`) walks the children from the top and takes the first whose `flags & 9 == 9` —
enable (bit 0) and sensitive (bit 3) — that contains the point; `widget_on_pointer_down_children`
(`0x6714ac`) checks the same two bits; `widget_set_visible` (`0x66c394`) only flips bit 2. The
Cover Flow asset ended with `view_tracks`, the track-list container, which is **0,50 320x430 —
the whole screen under the navbar** — and the page only *hid* it. So every touch below y = 50 went
to that invisible, empty view, while the navbar above it kept working: exactly what the user saw.
(`label_status` and `btn_cancel`, also only hidden, overlapped the covers too.) `test/patch.py`
now reproduces this with demo's own `widget_find_target` on the page's real widget tree: in the
V2.1dC model a touch at (160,150) lands on `view_tracks`.

**Fix (V2.1dD).**
- Everything the page hides is made **insensitive** as well (`show()` couples
  `widget_set_visible` with `widget_set_sensitive`), and the asset ships `view_tracks`,
  `label_status` and `btn_cancel` with `visible=false` **and** `sensitive=false`.
- Touch no longer depends on the stock `slide_menu`'s drag or on clicks reaching its children: a
  **transparent full-size touch layer** (a `view` on top of the `slide_menu`, inside
  `view_covers`) takes `EVT_POINTER_DOWN/MOVE/UP` (`0xff`/`0x101`/`0x103`, from the input jump
  table at `0x88f120`) and the abort `0x107`, grabs the pointer for the gesture
  (`widget_grab`/`widget_ungrab`, as the stock `slide_menu` does) and drives the `slide_menu`
  through its public `xoffset` property and `slide_menu_set_value`: the shelf follows the finger
  (`DRAG_PX` = 90 px per album), a release coasts by the fling (120 ms, at most 3 albums) and snaps
  to a cover with a 16 ms timer animation, then commits as stock does (`xoffset` 0, `value -
  offset/h`). A release within 12 px is a **tap**, hit-tested by x: the centre cover opens the
  album, a side cover (one or two out) is brought to the centre. The `slide_menu` itself is made
  insensitive. The depth frame is now drawn from the touch layer's `EVT_AFTER_PAINT`, so it is on
  top of everything in that rectangle.
- The menu's rows now sit in a stock-style `list_view` > `scroll_view` (+ `scroll_bar_m` when
  needed), copied from `systemset/sysset_page.bin`. With nine rows they still fit (47 px rows,
  473 px), so there is nothing to scroll today — the old page had no scroll container at all and
  simply could not scroll; with more rows (row height floor 44 px) it now scrolls like a stock list.

## What it does

- **Covers.** One cover per album on a stock `slide_menu`, drawn by the payload's depth renderer:
  the centre cover faces you at `ART_SIZE` (140 px), the neighbours turn 60 degrees inward, step
  back and dim, and each has a short reflection. The `slide_menu` holds the index, the offset and
  the wrap-around (and draws the covers itself in the flat fallback); the touch layer moves it.
- **Text.** The album name and the artist under the frame, updated when a move commits
  (`EVT_VALUE_CHANGED`), plus the hint *"Tap the centre cover to open the album"*.
- **Touch.** Drag the shelf (it follows the finger and snaps to a cover; a flick coasts), tap
  the **centre** cover to open the album, tap a **side** cover to bring it to the centre, tap a
  track to play it. **Back** goes tracks -> covers -> out of the page. All of it comes from the
  page's own transparent touch layer (see the section above); the hardware prev/next/play keys are
  not touched and keep working as stock handles them.
- **Tracks.** The album's songs, title tag (else file name), in the stock order, played through the
  stock path; a scrolling list of stock-styled rows (`list_item_style`) under the navbar.
- **Cache.** The first open builds `/mnt/mmc/.coverflow/<key>.jpg` thumbnails on a modal
  "Preparing covers... n/m" screen with a **Cancel** button; a cancelled build resumes on the next
  open.
- **Last album.** The centre album's key is written to `/mnt/mmc/.coverflow/album`, so the page
  reopens where you left it, across reboots.

## Where the data comes from (all stock)

| what | stock call | evidence |
|---|---|---|
| the album list | `loadLocalClassList(0xf003)` (`0x4ee504`) -> `getAllAlbum` (`0x4ea3c4`) into `*pdeq_showlist` (`0xa045d8`) | what the Albums page itself runs; the list is `deque_assign`ed into the payload's own `stSongInfo` deque so later queries cannot pull it away |
| an album's tracks | `loadAlbumdetailList(0xf003, row)` (`0x4eea98`) -> `loadLocalClassList(0xff10)` -> `getMusicByAlbum` | exactly what `albuminfo_page_init` does (`0x5268bc`); it fills the stock browsing record at `0xa0c768`, so stock resume and memory playback see the same album as a stock album page |
| playing a track | `loadSongList(queue, name, cue_start, 0xff10)` (`0x4e2ce0`) then `navigator_to_with_context("playing_page", {queue, index, 0xff10, 2})` | the album page's own row handler (`0x5275a4`); `loadSongList` also fills `g_memory_info` (`0xa0caf8`) for memory playback |
| the album's artwork | `toolsGetAlbumCover` (`0x5eaee0`, embedded art) then `toolsGetExternCover` (`0x5eafec`, the image beside the track) | the order and the lock `parse_albumcovertask_thd` uses (`0x4dd68c`) |

`getAllAlbum`'s rows carry the album's first track in `fileurl` (`REC_PATH`), which is what the art
calls are given. The record layout (`REC_*` in `patch/offsets.inc`) was read from the row callback
at `0x4e93c8`.

**Why its own cache and not the stock one.** The stock cover cache (`/mnt/mmc/.downpic`, written by
`parse_albumcovertask_thd`) is keyed by an MD5 of names that the payload cannot reproduce without
duplicating that function, its sizes are the stock list's (90 px), and writing into it would mean
sharing a cache stock prunes. Cover Flow therefore keeps its own directory, exactly as q2-pod does,
and only *reads* through the stock extractors.

## The depth renderer

Borrowed from q2-pod (after Rockbox PictureFlow) and kept almost unchanged; only the geometry is
this screen's, the iPod rounded-corner inset is gone and the texture sampler is split out so the
host test can call it.

- All integer: 16.16 turns, 1/16 px geometry, 1/256 px row spans; no floating point.
- One `bitmap_create_ex(320, 230, 1280, RGBA8888)` frame plus `CF_RING` (7) textures of
  `ART_SIZE^2` pixels and one placeholder: **about 1.0 MB of heap** while the page is open, freed
  on close. If either allocation fails the page falls back to **flat** covers: the `slide_menu`'s
  own `image` children show the cached JPEGs (`ART_NEAR` = 3 either side of the centre, the
  placeholder elsewhere) and stock draws them.
- The frame is drawn from the touch layer's own **`EVT_AFTER_PAINT`** (`0x120`, dispatched by
  `widget_paint` after the children and the border, `0x66de3c`) — an instance event registered with
  `widget_on`, not a hook on stock code. The layer has a transparent background and covers exactly
  the `slide_menu`'s rectangle; with the depth frame the `slide_menu`'s children carry no image, so
  stock paints nothing under it.
- The position comes only from stock **properties**: `value`, `xoffset` and `h`
  (`widget_get_prop_int`). The stock commit is `value - round(xoffset / item width)` and the item
  width is the widget's height (`0x612360`), so the continuous position is `p = value - xoffset/h`;
  the renderer gets the centre album and `frac = p - centre`. No field offset of the stock
  `slide_menu` is pinned, so a different layout of that struct cannot corrupt anything.
- Tunables: `CF_*` and `ART_SIZE` in `patch/offsets.inc`. Change them together and re-run
  `test/coverflow.py`.

Cost: `test/patch.py` counts **~2.8 M payload instructions per frame** under Unicorn
(320x230, `ART_SIZE` 140) — a relative measure, not a frame time. That is the same order as q2-pod's
3.5 M on the Q2, which runs the same SoC.

## The cache and its thread

- One `pthread`, started only after the page is up, running `build_art` over a job array built on
  the UI thread (each job owns a `strdup`ed track path and the album's key).
- The thread touches **only**: its own jobs, three `volatile` counters, files under
  `/mnt/mmc/.coverflow`, and the two stock art calls under `parse_cover_mutex` — the lock every
  stock caller of them holds. It never touches a widget, a deque or the image manager.
  (On this build `parseplaycover_thd` takes the *same* mutex (`0xa04588`) as
  `parse_albumcovertask_thd`, so unlike the Q2 there is no second art lock to take.)
- Each thumbnail is written to `<key>.jpg.tmp` and `rename`d into place. Both extractors failing
  leaves an **empty** `<key>.jpg`: the placeholder shows and the album is not retried (until the
  cache is deleted). A track that has gone (`access` fails) leaves no marker, so the next open
  retries it.
- No build starts below **16 MB** free on the card (`statfs`), without a card, or if
  `pthread_create` fails: the page then shows whatever is already cached.
- A 250 ms timer polls the counters and updates the progress text. **Cancel** and closing the page
  both set the cancel flag and `pthread_join` — a wait bounded by one album's extraction.
- Nothing of the page outlives it: `EVT_DESTROY` removes the timer, joins the thread, frees the
  frame, the textures, the job array and the album copy.

Never written outside the card: the rootfs is read-only squashfs and `/mnt/data` holds Shanling's
own database and settings.

## Safety

Everything in `docs/payload.md#safety` still holds — this page adds no hook, so the hook count is
still exactly one (the Home icon click dispatcher), it is still only reachable by tapping the entry
icon and then a menu row, and the kill switch (`/mnt/mmc/m1pod-off`) still disables the entry
before any of this runs. In addition:

- every stock call's result is checked, and any failure (no window, a missing widget in the asset,
  no album list, no bitmap, no thread) degrades to a message, the flat fallback or leaving the page;
- the album list is a private copy, so the stock list the tracks screen loads cannot invalidate it;
- the page writes exactly two kinds of file, both under `/mnt/mmc/.coverflow`;
- the payload's writable state lives in a zero-filled `.scratch` section inside the file-backed
  segment (`memsz == filesz`, `tools/pod.py` checks it ships zeroed), so no new mapping is needed.

## What is not ported

q2-pod's Sort and Refresh cards, the artist and rated scopes, the A-Z jump, the album split by
album-artist/folder (`ALBUM_SQL`), the audiobook filter, the ffmpeg fallback for WebP/large PNG
artwork, Now Playing artwork integration and the wheel/ringnav behaviour. The album list is the
stock Albums list, name-grouped exactly as the stock page shows it. To clear the cache, delete
`/mnt/mmc/.coverflow` from a computer (there is no Refresh card yet).

## The package

`python3 -I tools/build.py --variant pod-cover` -> `out/M1Plus-V2.1dE-pod-cover-lockscreen-iconpercent-space-update.bin`
(tag **V2.1dE**, SHA-256 `0806ade24ce6cf33b151e4c9992f4c04d7e927081a7f033a7bc90ac06f6e9db6`; V2.1dC `282a5803…` had dead touch, V2.1dD `591880e8…` swipes but had an unreadable track list and a menu that could not scroll),
which carries everything V2.1dM has — lock screen, icon+percent status bar, the space step and the
M1 Pod menu on the Tidal icon — plus Cover Flow. `fwtool diff` against stock lists only `demo`,
the two M1 Pod assets, the two mod assets and the space step's ten removals; the rebuilt rootfs is
53,149,696 bytes (2.59 MB under stock) and a clean rebuild is byte-identical.

## Tests

```
venv/bin/python -I test/coverflow.py --captures /tmp/cf --preview docs/coverflow-preview.png
venv/bin/python -I test/patch.py work/mod-pod-cover-lockscreen-iconpercent-space
```

- `test/coverflow.py` compiles the same `patch/coverflow.c` for the host (`-DCF_HOST`) and checks
  the centre cover pixel for pixel, the frame's opacity and bounds, mirror symmetry at rest, the
  brightness ladder (`CF_BRIGHT1`, `CF_BRIGHT2`, gone three out), the reflection and its fade, that
  a small step moves the frame only a little, a missing texture, a one-album library, the FNV cache
  key (including the separator) and the texture sampler's centred square and alpha-over-black.
- `test/patch.py` runs the **real payload** under Unicorn against the real patched `demo` with the
  stock calls mocked: the menu row, opening with a complete cache, the slide_menu and its children,
  the captions, tapping the centre cover (the stock album query, the track rows, `g_class_type`),
  playing a track (`loadSongList` + `playing_page` with the stock context), a missing file, Back
  from tracks and from the covers, tapping a side cover, closing the page, the first-run build
  (jobs, thread, progress, Cancel), the worker's lock order and its empty marker, no space, a
  refused thread, an empty library, a broken asset, the flat fallback when the frame bitmap cannot
  be allocated (real art only within `ART_NEAR`, no frame drawn), re-querying the album when
  something else has replaced the stock list, and finally the depth frame rendered by the payload
  compared **byte for byte** with the host build of the same renderer. Touch is driven through
  the page's real pointer handler (tap centre/side, slow drag, flick, wrap, abort, grab/release),
  and **hit testing runs demo's own `widget_find_target`** on the page's widget tree as the asset
  and the payload leave it: the V2.1dC model sends a touch on the covers to the hidden
  `view_tracks` (the hardware bug), the fixed page sends it to the touch layer, the navbar and
  Cancel still get theirs, the track list gets them on the tracks screen, and every menu row is hit
  through its `list_view`/`scroll_view`. Since V2.1dE it also checks that every row (menu and
  tracks) is a stock `list_item` themed `list_item_style` with an `srlabel_leftwhite21_style`
  label, that every inline-styled button is dark with light text in all six states, that every
  page widget ends inside the 450 px window, and that the nine menu rows overflow the 400 px list
  (so it scrolls) with the stock scroll bar present. 128/128.
