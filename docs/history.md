# History: milestones, hardware results, lessons

Release details live in git (`git log --oneline`); only the current release and `--restore` build from
this tree. The surviving design is in `docs/architecture.md` and `docs/ui.md`, firmware facts in
`docs/firmware.md`, the process in `docs/workflow.md`. Hardware results are the user's reports from the
device. Nothing was ever bricked.

## Milestones

### 1.0.0 (2026-11-01, current release; package tag `V2.1-1.0.0`)

Semantic versions as in q2-pod, a manual macOS CI (`make dev` on the runner, the package as its
artifact), `make publish` (a draft GitHub release named `VERSION`), deterministic cold builds. Adds
**Find Cover & Lyrics** (Now Playing > More: iTunes and Deezer covers with a confirmation, LRCLIB lyric
candidates, fails fast with Try Again), the **Home cover build** ("Preparing covers n/m", Recently Played
first) and **Rebuild Covers** from Home and Settings > Developer > **Cover Cache**. Flashed, accepted.
LRCLIB under load answers uncached queries with 503. A Recently Played cover key resolved under an older
album-row rule named a file no build makes: the tile kept the placeholder while a tap showed the cover.

### Pre-1.0.0 (2026-10-19 to 11-01)

- **Firmware and payload**: stock images repacked with a new tag, the way back (`--restore`), the asset
  pipeline, the updater's checks and the space step (`docs/firmware.md`); the first payload (appended
  `PT_LOAD`, one hook) opening an iPod-style menu from the Tidal icon.
- **Look and entry**: Cover Flow with a per-album cache, the Minimal theme (Inter + Source Han Sans),
  Tabler then Lucide icons, classic then iPhone-style lock screens, the boot guard, its own Home icon
  (id 99) with the Tidal-icon fallback, 13 languages, a cover-tinted Now Playing, glass (mini player, More
  sheet, navbars), the rename to **M1+ Music** (device files renamed by one migration build, then removed).
- **Library**: Albums grid and landscape Cover Flow, a customisable iPod-ordered menu, Apple Music-style
  Songs with an A-Z rail (also Artists, Genres, Composers), Playlists, **Daily Mix** in its own file,
  library search with pinyin initials and recent searches, our own album, queue and lyrics pages, albums
  keyed by their first track.
- **Pod**: a virtual iPod Classic with a touch click wheel, its own Now Playing and Cover Flow, Podcasts on
  its main menu.
- **Now Playing modes**: **Cassette Mode**, **Vinyl Mode** with record and base colours (red, smoke, clear
  and Walnut were mocked and dropped for rootfs headroom).
- **Podcasts**: feeds over the app's libcurl with Mozilla's CA bundle, covers shrunk once on download,
  episode downloads (`.part`, 512 KB synced chunks, Range resume), Apple Podcasts-style pages, OPML,
  Podcast Search through Apple's directory (off by default), Saved episodes as `myfav` rows.
- **Input and Settings**: our own keyboard with Pinyin input, Settings as grouped cards, Battery
  Percentage, cover resampling by exact area average.

Findings still worth knowing:

- Podcast art is often too large for the stock loader (36 MB for 3000 px): shrink once on download.
  Feeds need 16 redirects; an over-cap feed is kept up to the cap.
- iTunes search: the US, TW and HK storefronts suit Chinese shows, CN the worst.
- `reset_poweroptions_timer(1, 1, 0)` (0x4d7874) from a page timer keeps the device out of standby while
  the screen still turns off.
- Stock's T9 popup is laid out 640 px wide in a 320 px window and stock Chinese input never had a
  dictionary; the shipped `data/gpinyin.dat` opens with `im_open_decoder` in 76 ms. A 155-tap log showed
  no systematic offset, all misses between keys: hence the nearest-key rule.
- A page's touch handler must not grab or eat move events, or the system pull-down stops working.
- `cc_decode` flattens over black: an image drawn over a cover needs its own alpha.
- AWTK destroys a closed window later, so closing and reopening a page in one call finds it still there;
  the emulated window mock never closes either.
- An icon change must commit the regenerated PNG under `assets/icons/png`; neither the preview nor the
  draw-call tests catch a missing one.
- The user rejected a top-right dropdown as crowded and accepted the same actions in a bottom sheet.
- Three parallel branches on one file cost more in merging than they saved; tests must not build on
  another module's constants.

## Hardware results (what broke on the device, and why)

- **Vinyl Cover record rim.** On a track change the previous tint's disc edge stayed: the anti-aliased rim
  blended onto a base pixel that already held the last tint, and the emulation model mirrored the same
  arithmetic, so the tests agreed with the bug. The pristine rim pixels (about 1,020, 6 KB) are now saved
  at the first recolour, and a test compares every change with a fresh compose on the installed base.
- **Vinyl Mode pause.** A pause tap stalled the page, then the arm stuttered until parked. Stock's
  `play_pause_music` (0x4e43b4) mutes and sleeps 150 ms (`usleep` 0x4e4460) on the UI thread before
  `mclSetPause`, and each arm tick composed two whole diagonal boxes (25 to 36 M instructions per 50 ms
  tick). Fixed by per-row spans, layer passes and stepped samplers (about 4 M a swing tick, 2.1 M playing;
  budgets in `test/pod/vinyl.py`), a 100 ms cap on a late tick, and the arm waiting for the record to stop.
- **Songs letter sections.** A run-per-letter rule left none on a real library; the page labels
  non-decreasingly, with the most songs under their own letter.

## Retired designs (what the docs no longer describe)

- **The Pod's Ken Burns cover pane**: a 168 px cover window panned and zoomed every 80 ms with crossfades
  jiggled on the device (a window resized and moved every frame resamples differently each time). Now one
  cover scaled once and copied 1:1 at whole pixels (`docs/modules/ipod.md` "The cover pane").
- **Now Playing foot**: mode and heart at the foot of the art page, a Hi-Res tag, 192 px art and Tabler's
  filled transport glyphs read worse on the device; the PIL glyphs stayed and both buttons returned to the
  top row.
- **Custom drag, velocity and fling code for the Albums grid**: replaced by the stock `scroll_view`.

## Lessons

Hit-testing and layout
- **Hidden widgets still hit-test.** The hit test checks only `enable` and `sensitive`, never `visible`
  (`widget_find_target_default` `0x6747d4`, `widget_on_pointer_down_children` `0x6714ac`;
  `widget_set_visible` flips bit 2 only). An early hidden full-screen view swallowed every touch below the
  navbar. Pair hide with `sensitive=false`, make decorative overlays insensitive; the tests run demo's own
  `widget_find_target` on the built page trees.
- **Normal windows are 450 px, not 480** (30 px `system_bar`; 68 stock pages end at y = 450). Rows 52 px.
- **Pointer events carry screen coordinates**: `widget_to_local` before any hit test.
- **The stock `slide_menu` starts on item 1**, not 0 (constructor `0x613970`): always call
  `slide_menu_set_value`, or an artist's shelf opens on its second album and a one-album shelf has no
  captions.
- **Stock relayouts re-stack list children by index**, and `list_view`'s paint-children hook exits at the
  first row below the canvas: a pull-down over the main menu hid every row but Now Playing, and the lock
  screen flashed the default order. Restack rows in page order (`widget_restack`) and clear that hook
  (`0x60c164`); `test/pod/pulldown.py`.
- **A `list_view` needs the mobile `scroll_bar_m`** for its `scroll_view` to be yslidable; the stock list
  code then gives drag, fling and overscroll for free.
- **Unstyled `list_item`s are white.** Rows are stock `list_item_style` > `hscroll_label` themed
  `srlabel_leftwhite21_style` (built like `systemset_sysset_page_init` `0x4adb7c`).
- **Asset order is behaviour.** The icons step inserts an image as child 0 of every menu row, so code
  touching "child 0" set text on the icon; find widgets by type or name. Steps that re-lay out a page from
  scratch run after the steps whose glyphs they use.
- **Widget names are an API.** demo looks everything up by name, recursively: reparenting or restyling is
  safe, renaming or deleting is not.

Painting and text
- **AWTK repaints only dirty rectangles.** A widget that draws beyond itself must invalidate all it draws
  (landscape Cover Flow animated only the `slide_menu`'s 276 of 450 px). The tests replay invalidations
  against runtime geometry (`dirty_rects`, `test/pod/harness.py`). After structural changes, prefer
  `widget_invalidate_force` on the whole window.
- **Text width = truncated glyph advance + 1 px per glyph** (`canvas_measure_text` `0x644544`,
  `canvas_draw_text` `0x645348`), and `hscroll_label` insets by `margin_left` 2. Measure with `StbText` on
  the font of the tree being built; run font steps first.
- **AWTK button text is left-aligned in its rect** (`text_align_h` default left): a negative `spacer`
  pulls the text onto the icon. `icon_at` auto is top when icon height + font size < the rect height.
- **AWTK scales images by nearest neighbour** and does not clip them (`round_radius` rounds only the
  background): pre-scale and draw 1:1 (the cover file is 264 px); for a rounded picture on a translucent
  card, round the card and keep the picture square.
- **A button's icon is drawn at its own size on the rect's centre, unclipped**
  (`canvas_draw_icon_in_rect` `0x648f90`), so a wider image reaches past the button (multi-select's 50 px
  glass over its 46 px button bridges the stock 2 px gap, seamless on the device). Keep what a press
  changes inside the button: only its rect is repainted.
- **A list's scroll view has no free positions.** The `list_view` layouter stacks every visible child in
  order and ignores its y (Settings card backgrounds behind the rows stacked as a block above them). Draw
  a card by its rows (per-row background pieces) and test list pages on demo's own layouter.
- **A custom-painted view beats a widget per item.** One view drawing only what is visible, with a small
  ring of decoded tiles, costs the same per frame and in memory for any library; the stock `slide_menu`
  laid out all its children (up to 4000) on every drag step.
- **Rendering is not emulated.** The canvas a hook gets while a dialog animates cannot be reproduced:
  remove a stock mechanism rather than rely on a hook there.

Dialogs, windows, input
- **A close animation on a window a stack-popping loop can reach hangs the UI** (the loop spins while the
  closing window stays topmost): no `close_anim_hint` on library pages, album detail, the jump list, Now
  Playing or Pod pages; the settings slides pass the static audit (`docs/ui.md` section 8).
- **A dialog dims the page below only through its `highlight` property**, read once at open (`0x6901c4`):
  set it in the asset (the More sheet, alpha 130). The highlighter paints; it does not hit-test.
- **A stock button answers pointer DOWN and UP with `RET_OK`**, so a child button on a clickable row also
  clicks the row. Use an insensitive picture and decide by the DOWN position.
- **Stock state outlives a page** (`*pdeq_showlist`, `classinfo`, `albumcover_taskstate`): a stock loader
  called from a tick or timer changes what a stock page shows later. Record in the tick, resolve in the
  owner's foreground, stop loaders on `EVT_WINDOW_TO_BG`.
- **The stock play mode outlives the button that set it.** After a Shuffle, Play all started at track 1
  but kept shuffling: an explicit Play sets the in-order mode (`pod_set_in_order`,
  `docs/modules/shuffle.md`); row taps keep the mode, as stock.
- **Never index outside the list** on overscroll (row -1 rebooted the player).

Boot, build, process
- **A boot hook needs a crash marker.** The Home foreground handler does not fire at start-up (the first
  open dispatches `WILL_OPEN`/`OPEN`): hook `home_page_init`, run stock first, write the marker (temp +
  fsync + rename) before anything risky, clear it by a 5 s timer, and on a found marker write a sticky
  note and fall back to stock. The guard arms only after the data directory's open and `fsync` succeed.
- **Library row geometry is code, not asset** (`addiu` immediates; an asset only picks style names).
  q2-pod's way: pinned immediates, call-site retargets and a small payload function; never a prologue
  rewrite, never anything reachable from `platform_init` (`tools/reach.py` checks).
- **The recovery path is unverified.** Keep the stock restore package (`--restore`) and the previous
  release at hand, and never flash two untested things in one package; the SD kill switch `m1plus-off`
  does not help a loop before the hook runs.
- **Static evidence is not a device test.** The tests run the real payload under Unicorn with mocked
  stock calls and use demo's own hit test, text layout and fills (`test/awtk_fill.py`), but playback,
  gapless, frame timing and the panel were only ever checked on the device.
- **Determinism.** Added files get a fixed mtime, PNGs carry no metadata, fontTools is pinned (4.67.0):
  two clean builds are byte-identical, which makes the golden hashes useful. The build cache hid two
  build-time mtimes (rewritten `m1plus_*.bin`, the added `lyrics.ttf`) until the first cold CI build
  (2026-11-01): compare two `--no-cache` builds after adding a file.
