# History: milestones, hardware results, lessons

Release details live in git: each commit message says what it added (`git log --oneline`). Only the
current release and `--restore` are buildable from this tree. The design of what survives is in
`docs/architecture.md` and `docs/ui.md`, firmware facts in `docs/firmware.md`, the process in
`docs/workflow.md`. Hardware results are the user's reports on the device. Nothing was ever bricked; the
recovery button combination remains unverified.

## Milestones

### 1.0.0 (2026-11-01, current release; package tag `V2.1-1.0.0`)

Semantic versions as in q2-pod, a manual macOS CI (`make dev` on the runner, the package as the run's
artifact), `make publish` (draft GitHub release named `VERSION`), deterministic cold builds. Everything
from pre-1.0.0 plus **Find Cover & Lyrics** (Now Playing > More: iTunes and Deezer covers with a
confirmation, LRCLIB lyric candidates; fails fast with Try Again), the **Home cover build** ("Preparing
covers n/m", Recently Played first), **Rebuild Covers** through Home and Settings > Developer > **Cover
Cache**. Flashed, accepted. LRCLIB under load answers uncached queries with 503 (cached ones 200).
Lesson: a Recently Played cover key resolved under an older album-row rule names a file no build makes;
the tile kept the placeholder while a tap showed the cover.

### Pre-1.0.0 (2026-10-19 to 11-01)

- **Firmware and payload**: stock images repacked with a new tag, the way back (`--restore`); the asset
  pipeline, the updater's checks and the space step (`docs/firmware.md`); a classic lock screen; the first
  payload (appended `PT_LOAD`, one hook) opening an iPod-style menu from the Tidal icon.
- **Look and entry**: Cover Flow with a per-album cache, the Minimal theme (Inter + Source Han Sans),
  Tabler then Lucide icons, an iPhone-style lock screen, the boot guard (the first start-up code), its own
  Home icon (id 99) with the Tidal-icon fallback, 13 languages, Now Playing with a cover-tinted window,
  glass (mini player bar, More sheet, navbars), the product renamed **M1+ Music** with a one-time
  device-file migration (rename device files by a migration build first, then remove it).
- **Library**: Albums grid and landscape Cover Flow, a customisable iPod-ordered menu, the Songs page in
  the Apple Music manner with an A-Z rail (also Artists, Genres, Composers), Playlists, **Daily Mix** in
  its own file, library search with pinyin initials and recent searches, our own album, queue and lyrics
  pages, albums keyed by their first track.
- **Pod**: a virtual iPod Classic with a touch click wheel, its own Now Playing and Cover Flow, Podcasts on
  its main menu.
- **Now Playing modes**: **Cassette Mode**, **Vinyl Mode** and its record and base colours (Cover-tinted
  record, Snow plinth; red, smoke, clear and Walnut were mocked and dropped for rootfs headroom).
- **Podcasts**: feeds over the app's libcurl with Mozilla's CA bundle, covers shrunk once on download,
  episode downloads (`.part`, 512 KB synced chunks, Range resume), Apple Podcasts-style Shows, Show and
  episode pages, OPML, Podcast Search through Apple's directory (off by default), Saved episodes as
  `myfav` rows under `Podcasts/`.
- **Input and Settings**: our own on-screen keyboard with Pinyin input, Settings as grouped cards,
  Battery Percentage, cover resampling with an exact area average.

Findings from this period still worth knowing:

- Podcast art is often too large for the stock loader (36 MB for 3000 px): shrink once on download.
- `reset_poweroptions_timer(1, 1, 0)` (0x4d7874) from a page timer keeps the device out of standby with
  the screen still turning off.
- Stock's T9 popup is laid out 640 px wide in a 320 px window; stock Chinese input never had a dictionary,
  while the shipped `data/gpinyin.dat` opens with `im_open_decoder` in 76 ms. A 155-tap log showed no
  systematic offset, all misses in the gaps between keys, hence the nearest-key rule.
- A page's touch handler must not grab or eat move events, or the system pull-down stops working.
- `cc_decode` flattens over black, so an image drawn over a cover needs its own alpha.
- An icon change must commit the regenerated PNG under `assets/icons/png`; neither the preview nor the
  draw-call tests catch a missing one. Feeds need 16 redirects and over-cap feeds kept up to the cap.
- The user rejected a top-right dropdown as crowded but accepted the same actions in a bottom sheet.
- iTunes search: US, TW and HK storefronts are right for Chinese shows, CN the worst.
- AWTK destroys a closed window later, so closing and reopening a page in one call finds it still there;
  the emulated window mock never closes either.
- Three parallel branches on one file cost more in merging than they saved; tests must not build on
  another module's constants.

## Hardware results (what broke on the device, and why)
- **Vinyl Cover record rim.** On a track change the previous tint's disc edge stayed. The anti-aliased rim blended onto
  the current base pixel, which already held the last tint; the emulation model mirrored the same arithmetic, so the tests agreed with
  the bug. Fixed by saving the pristine rim pixels (about 1,020, 6 KB) at the first recolour; a test now compares every change with a
  fresh compose on the installed base.
- **Vinyl Mode pause.** Tapping pause stalled the page, then the arm stuttered until parked. Stock's `play_pause_music`
  (0x4e43b4) mutes and sleeps 150 ms (`usleep` 0x4e4460) on the UI thread before `mclSetPause`, and each arm-swing tick composed two whole
  diagonal boxes (25 to 36 M instructions, over a 50 ms tick). Fixed by per-row spans, layer passes and stepped samplers (about 4 M a
  swing tick, 2.1 M playing; budgets in `test/pod/vinyl.py`), a 100 ms cap on a late tick, and the arm waiting for the record to stop.

First tests, 2026-10-19 to 10-25:

- **Cover Flow touch.** The Cover Flow page opened and built 107 thumbnails (14 MB) in `/mnt/mmc/.coverflow`, so extraction and
  the worker thread work on hardware, but nothing in the cover area took a touch: a hidden full-height view still hit-tested. The
  next build made hidden widgets insensitive and added a touch layer; its track list was white on white and the menu would not
  scroll (lists were 430 px high, 47 px rows too short for the list); the one after fixed both.
- **Now Playing album line.** It still showed a slice of `m:`: the text layout was not modelled exactly (width +1 px per
  glyph, label `margin_left` 2; the prefix is 51 px in the stock font, not 45).
- **Lock screen feedback.** Battery icon huge, clock and swipe hint too big, free space for a translucent card (became the 280 px
  cover card). Later feedback: album page wanted, wallpaper, battery icons mismatched, artist Cover Flow opened on the 2nd album,
  single-album captions missing.
- **Pod as Home.** A second flash of the stock grid at boot and on Back from Now Playing (the menu opened 1.2 s /
  250 ms after Home; now the grid content is hidden from `home_boot` on and the menu opens 10 ms after Home is up); a ghost
  "Start in: M1+ Pod" (text set on the icon image the icons step inserted as child 0 of the row; the label is now found by type);
  no way back from Shanling Home (the grid flag lived until reboot; now the Tidal icon on the grid restores Home); titles too big
  (22 -> 20 px); pull-down tiles in two styles (-> one ring style); the pod title box wider than stock (248 -> 200).
- **Boot guard device test procedure:** the guard alone first, wait 10 s past Home, power-cycle, then power off within 5 s of
  Home once to prove the failure branch, then Home on top. Card log `m1pod: armed` -> `m1pod: boot ok, marker cleared`.
- **Album from Cover Flow without a cover.** `albumcoverinfo_init` (Cover Flow runs it, as the stock Albums page does) sets
  `albumcover_taskstate` (`0xa05a18`) to 2 and `parse_albumcovertask_thd` sleeps while it is 2; stock's Albums list then runs
  `batchadd_albumcover_task`, ending with the state 1, but `albuminfo_page_init`'s `add_albumcover_task` does not, so the
  page's cover task was never taken. Cover Flow now calls `batchadd_albumcover_task(0, 0)` (queues nothing, state := 1) before
  opening the page; the page's 500 ms timer then shows the file the stock thread writes.
- **Landscape Cover Flow.** Only the first ~60 % of the frame animated (only the `slide_menu`'s 320 x 276 was repainted), the exit
  glyph lay over the covers, Now Playing was gone with the hidden navbar; the Albums toggle overlapped the stock list's search
  button. Now the whole frame repaints, the navbar stays, and the toggle is a Settings switch.
- **Albums grid/list button.** The button added at run time to the stock Albums navbar sometimes vanished: the stock navbar is
  rebuilt by `0x524e4c` (from the multi-select handlers `0x525274`, `0x52532c` and callers `0x5265f4`, `0x5267f0`), the window is
  found by name (possibly an earlier one still closing) and builds on the dispatcher's schedule, so a decoration cannot order itself
  against it. Cause not isolated; the list became the Albums page's own mode (no run-time decoration of stock pages).
- **Tinted Now Playing.** Tint, sharp rounded cover and remaining time work; the after-paint corner painter stayed. The cover file
  is 264 px so it draws 1:1.
- **Pull-down over the main menu.** Pulling the control centre down from the main menu, after about 40 % of the screen everything
  but Now Playing vanished; coming back from the lock screen showed one frame of the menu in the default order. Cause: the stock
  `list_view` layouter re-stacks children by index before every paint (after any `widget_set_visible`), putting the asset order
  back, and its paint-children hook exits early at the first row below the canvas. Fix: `menu_arrange` and the Main Menu page
  restack the rows' children in page order (`widget_restack`, hidden rows last) and clear the `list_view` paint hook (`0x60c164`).
  Verified on demo's own layout/scroll/paint/pointer code in Unicorn (`test/pod/pulldown.py`: relayout, lock screen frame,
  pull-down sequence, Main Menu arrows each fail with the old arrangement and pass now). Not reproduced: the exact device canvas
  while the dropdown animates (rendering is not emulated). Device checks: pull down over the first row slowly and fast with
  default and custom order, rows stay behind the dialog and after it closes; lock/unlock with a custom order shows no
  default-order frame; Main Menu arrows and switches; scroll the menu.
- **Main Menu arrow tap.** A tap on the up arrow moved the item and toggled it too: the stock button answers pointer DOWN/UP with
  `RET_OK` so the row got the click as well (reproduced in Unicorn, `test/pod/menutap.py`). The arrow is now an insensitive
  picture and the row decides by where the touch went down (arrow rectangle row x 191..240, 50 x 52 px).
- **Main Menu not following its own changes.** The saved order showed in the menu but the page's rows did not re-order
  until reopened; after every save the page re-arranges, keeps the changed row inside the list window (`yoffset`) and
  invalidates the whole window (`widget_invalidate_force`) instead of per-widget dirty rectangles; a failed save touches nothing.
- **Play all pill.** The first version assumed AWTK centres the pill's text; it draws it LEFT aligned at the start of its rect
  (`widget_draw_icon_text` `0x67235c` reads `text_align_h`, default 2 = left), so a negative `spacer` pulled the text onto the
  glyph ("P" touching). Also `icon_at` auto is top when icon height + font size < rect height (18 + 20 < 44). Fix: `text_align_h`
  left, `spacer` -5, `margin_right` 0, and the album header hook sets `margin_left` per page build from `widget_measure_text`
  (`0x66c7e0`) via `widget_set_style` (fallback: the style's English margin 45), so the glyph/text pair is centred with an 8 px gap
  in every language.
- **More menu.** The folded menu (Look up Album / Look up Artist / Add to playlist / More) expanded in place mid-screen;
  it became a bottom sheet (y 280, 4 x 50 rows) with the dialog highlighter (alpha 130) dimming Now Playing, two pages of
  equal height, re-anchored when the Delete confirm covers it; the Speed row label was widened ("Speed", badges moved), its note
  shortened to "Files below 48 kHz only".
- **Albums on `scroll_view`.** Without the stock `scroll_bar_m` the `list_view` layouter does not make the `scroll_view`
  yslidable, so nothing scrolled; a list pulled past an end (stock overscroll) must never look up an album outside the list (row
  -1 crashed the app and rebooted the player); no cover decoded while a list drags or animates.
- **Menu offset on Back.** The menu re-arranged whenever it was back in front (`on_menu_fg`) and reset the list offset to 0, so
  Back from any page returned to the top; `menu_arrange` leaves the offset, clamped to the new range.
- **Navbar slots.** On device shots the stock Now Playing glyph sits 2 px left (x 262), the 44 px Back 3 px left (x 3),
  multi-select needs no shift: the Pod navbar slots follow these measurements.
- **Playlists menu.** A 24 px glyph per row looked big (20 px kept); the last row looked taller with padding, so four 50 px
  rows fill the card with none; the card is as wide as the language needs (`pl_fit`: English 180, Spanish 291).
- **Hideable Extras row.** A menu file saved before it has no trailing `x`, so a customised menu comes up without Extras until
  switched on (no compat path).
- **Navbar fade.** The fade (`img_nb_fade`) darkened the first content at rest (Albums/Playlists list alpha 146, grid ~50): now
  built hidden on those pages and shown only while scrolled; text pages a steeper curve.
- **Song list turned into albums.** `cc_albums()` (`loadLocalClassList(0xf003)`) in Now Playing's tick left the album list in
  `*pdeq_showlist`; the stock `allmusic_page` does not read again on a to-foreground with its class unchanged (`0x527c28`), so a
  playlist's songs page came back as the library's albums with folder icons (`list_get_left_icon` `0x4d972c`: type 4 =
  `icon_folder`) and a tap played from that list. The tick now only records; the menu's to-foreground resolves the key. The
  Playlists page also stops its loader on `EVT_WINDOW_TO_BG` (a scan replaced `*pdeq_showlist` and `classinfo[1]` under the songs
  page).
- **Songs letter sections.** A run-per-letter rule left no sections on a real library; the Songs page uses the non-decreasing
  labelling with the most songs under their own letter (stock Initial byte `stSongInfo + 0x54`).
- **Font fit.** Inter Medium: tightest Cover Flow progress line fr_FR / it_IT / po_PL 299 of 300 px, ru_RU Sort value 105 of 106
  px; uk_UK stock "System Settings" clips at 202 of 200 px (a stock label). A saved main-menu file containing `j` is invalid and
  gives the default menu (accepted, no compat).
- **Space step.** Flashed 2026-10-19; in every package since. The watchdog opt-in (`sleep 2 -> 10`) never shipped;
  `--pdr-all` (all 197 executables, ~540 KB more) was never hardware-proven and is gone.

## Retired designs (what the docs no longer describe)

- **The Pod's Ken Burns cover pane**: a 168 px cover window panned and zoomed into the pane every 80 ms, with crossfades; on the
  device the covers jiggled (a window resized and moved every frame is resampled differently each time). Replaced by one cover
  scaled once and copied 1:1 at whole pixels (`docs/modules/ipod.md` "The cover pane").
- **Entry icon.** At first the M1+ Pod entry was the Tidal icon (id 1, taken over); then it became an icon of its own (id 99).
- **Stock Albums list with a run-time toggle.** See the Albums grid/list button result above; replaced by the page's own list mode.
- **Landscape Cover Flow navbar button.** Exit glyph in the frame, navbar hidden; now a Settings switch and the navbar stays.
- **Now Playing foot.** Mode and heart at the foot of the art page, a Hi-Res tag, a 192 px art and Tabler's filled transport
  glyphs (they read worse on the device); the PIL glyphs stayed and both buttons went back to the top row.
- **Custom album page and Cover Flow track list.** The stock `albuminfo_page` became the album view everywhere (our own album
  page later replaced it).
- **Custom drag/velocity/fling code for the Albums grid.** Replaced by the stock `scroll_view`.

## Lessons

Hit-testing and layout
- **Hidden widgets still hit-test.** This AWTK's hit test checks only `enable` and `sensitive`, never `visible`
  (`widget_find_target_default` `0x6747d4`, `widget_on_pointer_down_children` `0x6714ac`; `widget_set_visible` flips bit 2 only).
  An early build shipped a hidden full-screen `view_tracks` that swallowed every touch below the navbar. Pair hide with
  `sensitive=false`; decorative overlays are insensitive; the tests run demo's own `widget_find_target` on the built page trees.
- **Normal windows are 450 px, not 480** (30 px `system_bar`; 68 stock pages end at y = 450). Rows 52 px.
- **Pointer events carry screen coordinates**: `widget_to_local` before any hit test.
- **The stock `slide_menu` starts on item 1**, not 0 (constructor `0x613970`): always call `slide_menu_set_value`, or an artist's
  shelf opens on its second album and a one-album shelf has no captions.
- **Stock relayouts re-stack list children by index** and `list_view`'s paint-children hook exits at the first row below the canvas
  (see the pull-down result above): restack rows in page order, clear that hook. Stock never met rows hand-placed under a
  pull-down zone.
- **A `list_view` needs the mobile `scroll_bar_m`** for its `scroll_view` to be yslidable; the stock list code is also what gives
  drag, fling and overscroll for free.
- **Unstyled `list_item`s are white.** Rows must be stock `list_item_style` > `hscroll_label` themed `srlabel_leftwhite21_style`
  (built like `systemset_sysset_page_init` `0x4adb7c`).
- **Asset order is behaviour.** The icons step inserts an image as child 0 of every menu row, so code touching "child 0" set text on
  the icon (the ghost label); find widgets by type or name. Steps that re-lay out a page from scratch go after the steps whose
  glyphs they use.
- **Widget names are an API.** demo looks everything up by name (recursively): reparenting or restyling is safe, renaming or
  deleting is not.

Painting and text
- **AWTK repaints only dirty rectangles.** A widget that draws beyond itself must invalidate the whole area it draws (landscape
  Cover Flow: only the `slide_menu`'s 276 of 450 px moved). The tests replay invalidations against runtime geometry (`dirty_rects`,
  `test/pod/harness.py`). Prefer `widget_invalidate_force` on the whole window after structural changes.
- **Text width = truncated glyph advance + 1 px per glyph** (`canvas_measure_text` `0x644544`, `canvas_draw_text` `0x645348`), and
  `hscroll_label` insets by `margin_left` 2. Measure with `StbText` on the font of the tree being built; run font steps first.
- **AWTK button text is left-aligned in its rect** (`text_align_h` default left), not centred; a negative `spacer` pulls the text
  onto the icon. `icon_at` auto is top when icon height + font size < the rect height.
- **AWTK scales images by nearest neighbour** and has no image clipping (`round_radius` rounds only the background): pre-scale
  images and draw them 1:1 (cover file 264 px); for a rounded picture over a translucent card the card is rounded and the picture square.
- **A button's icon is drawn at its own size on the rect's centre, unclipped** (`canvas_draw_icon_in_rect` `0x648f90`): an image wider than
  its button reaches past it (multi-select's 50 px glass over its 46 px button bridges the stock builders' 2 px gap; seen seamless on
  the device). Keep what a press changes inside the button: only its rect is repainted.
- **A list's scroll view has no free positions.** The stock `list_view` layouter stacks every visible child in child order and
  ignores its y (Settings card backgrounds as views behind the rows stacked as a block above them). Draw a card by its rows
  (per-row background pieces) and test a list page on demo's own layouter, not the asset's y.
- **A custom-painted view beats a widget per item.** One view that draws only what is visible with a small ring of decoded tiles costs
  per frame and in memory independently of the library; the stock `slide_menu` laid out all its children (up to 4000) on every drag step.
- **Rendering is not emulated.** The canvas a hook gets while a dialog animates cannot be reproduced; prefer removing a stock
  mechanism over relying on a hook there.

Dialogs, windows, input
- **A close animation on a window that a stack-popping loop can reach hangs the UI** (the loop spins while the closing window stays
  topmost for the animation): never give `close_anim_hint` to library pages, album detail, the jump list, Now
  Playing or M1+ Pod pages; the settings slides are safe by the static audit (`docs/ui.md` section 8).
- **A dialog dims the page below only through its `highlight` property**, read once when it opens (`0x6901c4`): put it in the asset (the More sheet, alpha 130); the highlighter paints, it does not hit-test.
- **A stock button answers pointer DOWN and UP with `RET_OK`**: a child button on a clickable row also clicks the row. Use an
  insensitive picture and decide by the DOWN position.
- **Stock state that outlives a page**: `*pdeq_showlist`, `classinfo`, `albumcover_taskstate`; calling a stock loader from a tick or a
  timer changes what a stock page shows later. Record in the tick, resolve in the owner's foreground; stop loaders on `EVT_WINDOW_TO_BG`.
- **The stock play mode outlives the button that set it.** A Shuffle left the mode on Shuffle, so a later Play all started at
  track 1 but kept shuffling with Now Playing showing Shuffle: an explicit Play sets the in-order mode (`pod_set_in_order`,
  `docs/modules/shuffle.md`); row taps keep the mode, as stock.
- **Never index outside the list** on overscroll (row -1 rebooted the player).

Boot, build, process
- **A boot hook needs a crash marker.** The Home foreground handler does not fire at start-up (the first open dispatches
  `WILL_OPEN`/`OPEN`); hook `home_page_init`, run stock first, write the marker (temp + fsync + rename) before anything risky,
  clear it by a 5 s timer, let a found marker write a sticky note and fall to stock. The guard arms only after the data directory's
  open and `fsync` succeed.
- **An asset can only pick what style names resolve to.** Row geometry on the library pages is code (`addiu` immediates); q2-pod's
  way is pinned immediates, call-site retargets and a small payload function, never a prologue rewrite, never anything reachable
  from `platform_init` (`tools/reach.py` checks).
- **The recovery path is unverified.** Keep the stock restore package (`--restore`) and the previous release at hand, never flash
  two untested things in one package when one will do; the SD kill switch `m1pod-off` does not help a loop before the hook runs.
- **Static evidence is not a device test.** The tests run the real payload under Unicorn with mocked stock calls and model demo's
  hit test, text layout and fills with demo's own code (`test/awtk_fill.py`), but playback, gapless, real frame timing and the
  panel were only ever checked on the device. A UI bug starts with a reproducer.
- **Determinism.** Added files get a fixed mtime, PNGs are written without metadata or by a plain zlib writer, fontTools is pinned
  (4.67.0): two clean builds are byte-identical, which is what makes golden hashes useful. The build cache hid two
  build-time mtimes (rewritten `m1plus_*.bin`, the added `lyrics.ttf`) until the first CI build ran cold (2026-11-01):
  compare two `--no-cache` builds after adding a file.
- **The updater checks** `firmware_v20.info` lines, MD5s, "V" in the version, and that the version differs from the installed one
  (`docs/firmware.md`).
