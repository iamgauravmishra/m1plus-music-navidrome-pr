# History: tags, hardware results, lessons

**These tags are historical.** Only the release and `--restore` (V2.1R) are buildable from
this tree; older packages are not reproducible from it (the variants, flags and payload stages that
built them were removed). What each one was is recorded here; the design of what survives is in
`docs/architecture.md` and `docs/ui.md`, the firmware facts in `docs/firmware.md`, the process in
`docs/workflow.md`. Tag format: `V2.1` + lowercase series + capital variant letters; the updater
refuses a version equal to the installed one, so each flashed package needs a new tag.

## Tags

| tag | what | hardware |
|---|---|---|
| V2.1R | stock images repacked with a new tag (the way back) | flashed, works |
| V2.1bA / bB | battery percentage (`86%` replaces the icon / next to it), no space step | bB flashed over stock, works |
| V2.1cS | the space step alone (`.pdr` zeroed in demo, 10 unreferenced files removed, `--tailends`) | flashed, boots |
| V2.1cA / cB / cL / cLB | percent / icon+percent / classic lock screen (big clock, small date, `86%`) / lock screen + icon+percent, each with the space step | cLB flashed, works |
| V2.1dA | M1 Pod payload appended, no hook (inert: proves the loader takes the new PT_LOAD) | skipped |
| V2.1dH | the hook installed, entry icon opens a "hello" page | skipped |
| V2.1dM | the hook; the Tidal icon opens the iPod-style menu whose rows open stock pages | flashed 2026-10-20 over stock, works |
| V2.1dC | + Cover Flow row | flashed 2026-10-25: page and cache build worked, covers ignored touch (hidden full-height view still hit-tested) |
| V2.1dD | hidden widgets also insensitive, a touch layer drives the carousel, menu in a stock list | flashed 2026-10-25: swiping works; track list white on white, menu would not scroll |
| V2.1dE | stock-styled rows, every page laid out in 450 px, the menu a scrolling 52 px list | flashed 2026-10-25: works (swipe, tap, readable tracks, scrolling menu) |
| V2.1eT / eL / eN / eB | single looks on dE: Minimal theme + icons + status bar; library lists; Now Playing; boot logo + quotes + settings slides | not flashed alone |
| V2.1eA | the four looks together | flashed 2026-10-25 over dE, works; the Now Playing album line kept a colon |
| V2.1fA / fN | eA / eN with the album-line fix (text width +1 px per glyph, label `margin_left` 2) | not flashed alone (the fix shipped in gA, confirmed there) |
| V2.1fI | Inter + Source Han Sans font | in gA |
| V2.1fK | iPhone-style lock screen, 254 px rounded cover card | in gA |
| V2.1fR | M1 Pod Artists and Cover Flow per artist | in gA |
| V2.1fS | Shuffle Songs / Albums / Folders | in gA |
| V2.1gA | f series together (font, looks, lock screen 2, Cover Flow + Artists + Shuffle) | flashed 2026-10-25 over eA: font, Artists, Shuffle, Now Playing confirmed; lock screen needed refinement |
| V2.1gB | q2-pod library rows (58 pinned demo edits + row fit), Shuffle page, larger Cover Flow with scrolling captions, battery as an icon without a number, smaller pull-down text | not flashed alone |
| V2.1gK | lock screen 3 after gA feedback: translucent card, 280 px cover (4 demo words), small gauge, smaller clock and hint | not flashed alone |
| V2.1gC | gB + gK | works (2026-10-25); feedback led to hA/hB: album page wanted, wallpaper, battery icons mismatched, artist Cover Flow opened on the 2nd album, single-album captions missing |
| V2.1hA | Tabler Icons, custom Tabler-style glyphs, M1 Pod row icons, one battery drawing | not flashed alone |
| V2.1hB | album page (header, Play, Shuffle), artist Cover Flow starting on its first album, single-album captions on open, Starry Night wallpaper | not flashed alone |
| V2.1hC | hA + hB | flashed (2026-10-26) before iL; no problems reported |
| V2.1hL / hM | boot guard only / M1 Pod as Home, on gC | superseded by iL / iM before a device test |
| V2.1iL | hC + the boot guard only (no window changes) | works: rebooted fine; card log `m1pod: armed` → `m1pod: boot ok, marker cleared` (first start-up code proven) |
| V2.1iM | iL + M1 Pod as Home and the launcher rows | works (boots into the M1 Pod menu); feedback: grid flash at boot and on return, title to remove, ghost "Start in" text, no way back from Shanling Home, navbar titles too big → jA |
| V2.1jA | iM polished (below) | flashed; the build the user's player runs |
| **V2.1kA** | jA + Tidal back to stock, an "M1 Pod" icon on the stock grid, no top bar on the Home menu, one Settings page: release candidate | emulated tests only; not flashed |
| **V2.1kB** | jA + one album page: the stock `albuminfo_page` restyled by a hook on its header builder (120 px cover, year and track count, dark Play all, Shuffle), Cover Flow / Artists / All albums open it, the custom page and its Cover Flow track list removed; the queue page's navbar title 20 px | built, not flashed |
| V2.1kC | jA + Now Playing in q2-pod's layout (Back / index / More on top, mode and heart at the foot of the art page, "Hi-Res" text tag, 4 px line without thumb) and Tabler round 2 (110 more stock icons: navbar actions, selection marks, Folders / Playlists / CD discs, dialogs, Now Playing glyphs); SHA-256 1d11ba9cb8764751ba550ed9d4bb7b1a57d898f8e08cdc63b53c95948677247e | built, not yet flashed (`docs/ui.md` "Icon audit") |
| V2.1kD | kA + kB + kC combined, plus the recovery fallback (while the boot guard's bad note exists, a tap on the Tidal icon opens the M1 Pod menu so Settings > Start in is reachable): the release | flashed; Cover Flow's album page had no cover |
| V2.1kE | kD + the album page's cover from Cover Flow / Artists / All albums (the cover thread is released before the page opens) + the polish listed below (album header, Lucide go-to-player icon, Home padding, queue drawer, Now Playing, speed badges) | emulated tests only; not flashed |
| V2.1lA | kE + UI polish, assets only: the orange left in stock images goes neutral (on/off toggles, slider fills and thumbs, default covers), pull-down tile captions no longer break inside a word (boxes 57 -> 71 px), secondary text one grey `#AAAAAA`, pressed surfaces `#333333` (`docs/ui.md` "Accents in images", "Polish"); SHA-256 b8f0537bdb378f664d7f91815e9712a77f3aaec7e9091e68826050fed572f662 | emulated tests only; not flashed |
| V2.1lB | kE + the Extras menu (an iPod-style page of the stock Home tiles the menu does not repeat) + the Artist / Album Artist toggle on the Artists page (the stock switch's writes, then the list reloads) | emulated tests only; not flashed |
| V2.1lC | kE + the Albums grid: the menu's Albums row opens a grid of covers (3 columns, one custom-painted view, a ring of 24 decoded tiles) or the stock list, one navbar button switches and the choice is saved; the shared cover-cache helpers (`patch/covercache.c`) | emulated tests only; not flashed |
| V2.1lD | kE + lA + lB + lC combined (polish recolours, Extras, Artists toggle, Albums grid); the Albums toggle safety: if the run-time button cannot be added to the stock list's navbar the saved choice is reset to the grid, so the Albums row never strands the user in the list | emulated tests only; not flashed |
| V2.1lE | landscape Cover Flow (main and per artist): navbar toggle, window-sized rotated frame with rotated captions and exit control, remembered in `/mnt/data/m1pod-landscape`; docs previews as palette PNGs (docs/ PNGs 1.59 MB -> 0.71 MB): the **release** | emulated tests only; not flashed |
| V2.1lF | lE's landscape Cover Flow turned 90 degrees clockwise (logical (x, y) at physical (319 - y, x), swipe and captions follow), no zoom (168 px covers 1:1, side covers spread wider), a plain `rotate-clockwise` glyph for the toggle and exit control, tap on the second cover out follows the drawn edge, caption buffer bounded, Tidal (Home grid and Extras row) drawn with Tabler `brand-tidal` | flashed 2026-10-26: landscape broken: only the first ~60 % of the frame animated (only the `slide_menu`'s 320 x 276 was ever repainted), the exit glyph lay over the covers, Now Playing gone with the hidden navbar; the Albums toggle overlapped the stock list's search button and the grid navbar had a gap before Now Playing (fixed in lG) |
| V2.1lG | lF + navbar toggle layout from the stock Albums navbar's real geometry (title 36..183, search 183..243, multi-select 224..284, Now Playing 270..330): the Pod pages' toggle (Albums grid, Artists, Cover Flow landscape) is 46 px wide flush left of Now Playing (x 214); on the stock list it sits flush left of the search button (x 137) with the stock title cut short before it; the Artists page's two-segment strip is a navbar button (microphone-2 / user-star glyphs, title "Artists" / "Album Artists"), the list takes the 44 px back | flashed 2026-10-26: the grid button on the stock Albums list sometimes vanished (the stock navbar rebuild at 0x524e4c destroys its children; replaced by the list mode in lK) |
| V2.1lH | lF's landscape fixed: every shelf move and album change repaints the whole frame (the touch layer is invalidated, not only the stock `slide_menu`'s rectangle), landscape is the 320 x 400 body under the navbar (which stays: Back, the toggle that returns, Now Playing), no control drawn in the frame; tests model AWTK's dirty rectangles and the page's runtime geometry | emulated tests only; not flashed |
| V2.1lI | lH + Cover Flow gestures: the release's own travel counts (one tracker for MOVE and UP; a release far from the press is never a tap), a 5 px drag start apart from the 12 px tap tolerance (counted from the threshold: no dead zone, no jump), mostly vertical motion neither taps nor flings, a press during the snap stops the shelf and its release settles it (no shelf left between covers), elapsed-time cubic easing (180 ms per album), fling over the last 80 ms of samples; trial values to tune on the device | emulated tests only; not flashed |
| V2.1lJ | lI + less work per frame: depth mode owns the shelf position (no stock `slide_menu`, no widget per album: the stock widget laid out all its children, up to 4000, on every drag step and snap tick; the flat fallback keeps it), paint draws only resident textures and a page timer decodes missing covers one per callback (nearest first, then the next one ahead of the travel; 9 slots keep the cover just left behind for a reversal; nothing past an artist's ends) | emulated tests only; not flashed |
| V2.1lK | lG + the Albums page has a **list mode** of its own (64 px rows: 52 px cover, album 21 px, artist 18 px `#AAAAAA`, hairline, pressed `#333333`; box-reduced Cover Flow cache, same tile ring) and the navbar toggle switches grid / list in place; the run-time decoration of the stock Albums list (and `NAV_LIST_X`, the retry timer, the saved-view reset) is removed; the stock list stays under Shanling Home; new pins `canvas_set_fill_color`, `canvas_fill_rect` | emulated tests only; not flashed |
| V2.1lL | lK + lH + lI + lJ merged: the Albums grid / list page with the landscape Cover Flow fix, the gesture rework and the per-frame work cut | flashed 2026-10-26: accepted |
| V2.1mA | lL + a customisable iPod-ordered menu (Now Playing, Cover Flow, Albums, Artists, Songs, Playlists, Shuffle, Extras, Settings; Genres and Folders and anything the user hides are at the top of Extras; the list is `/mnt/data/m1pod-menu`, strictly parsed, defaults on any error) and a reworked Settings page: Main Menu (show / hide switches and up arrows), Cover Flow landscape and Start in M1 Pod as stock-style switches (the navbar rotate button is removed), Playback (was Play Settings), System Settings, Shanling Home; Now Playing row has the wave glyph, Shanling Home the Shanling mark cut from the stock shutdown screen | flashed 2026-10-26 |
| V2.1mB | mA + the cleanup (unused pins, faster tests, docs describing the current state) + the Now Playing redesign (variant D of the exploration): grabber Back, 264 px art with payload-painted round corners, the window in the cover's colour under a black gradient (fourth hook, `playing_page_init` `0x53d1e4`: a 500 ms page timer averages `/tmp/coverpic.jpg` / `externpic.jpg` when it changes), micro dots, title and artist with heart and More on 36 px discs, 6 px bar, `-mm:ss` remaining time, no album line, index or quality line on the art page, bigger solid transport and dimmer 22 px mode / queue glyphs, the A-B markers moved to the new bar (5 pinned immediates); the cover file is **264** px (sharp 1:1: the four cover-size words 0x118 -> 0x108, the lock screen's card 288x334) | flashed 2026-10-26: works (tint, sharp rounded cover, remaining time); the after-paint corner painter kept |
| V2.1mC | mB + the code-audit fixes: the boot guard needs the data directory's open and `fsync` to succeed before it arms (an unconfirmed marker is unlinked again); Home never stays blank (the grid is shown when Home returns with no menu to follow: Start in switched to Shanling, a kill switch, a refused open timer); Albums gestures count both axes and the release position, and a press that stops a fling is not a tap; Cover Flow's cache publication failure leaves no "no art" marker, and a refused preparation timer cancels the build; `cc_sample` / `cc_box` step the x mapping without a division per pixel (pixel-identical); tools: strict `fwtool verify`, `check.py --update` never blesses a failed run (`test/tools.py`) | emulated tests only; not flashed; merged into mD |
| V2.1mD | mB + mC + the language: every text M1 Pod adds follows Settings > Language (13 languages, the stock `tr_text` / `locale_info_tr` mechanism, `patch/i18n.h`, `tools/mod_strings.py`; 40 keys of our own added to the 16 string tables, key = English text, plus 5 stock keys; widths measured per language, no font change needed); the audit fixes of mC are inside (see the mC row): merged into mE | not flashed alone (in mE) |
| **V2.1mE** | mD + Cover Flow opens on the playing album (`mclGetPlayPos` + the play queue `0xa0394c`, matched by album key, else album name; saved last album otherwise); Settings > Cover Flow sub-page (Landscape switch moved there, new Sort value row); album order Artist (default, ignores a leading "The ") or Album (stock), shared by Cover Flow and Albums via a sorted index over the unreordered stock list; `/mnt/data/m1pod-cfsort`; the key "Cover Flow landscape" is gone: the **release** | flashed 2026-10-26: works |

Pre-history: q2-pod (Shanling Q2) supplied the method (an asset-only mod first, then a code payload in
a spare `PT_NULL` program header); the M1 Plus runs the same stack, so the pipeline (unpack, edit,
repack with exact metadata, TF-card `update.bin`) was exercised with the battery mod before any code.
Hardware results are the user's reports on the device. Nothing was ever bricked; the recovery button
combination for this model remains unverified.

### The first hardware tests (2026-10-19 to 10-25)

- bB, cS, cLB: the asset pipeline, the updater's checks (`firmware_v20.info` lines, MD5s, "V" in the
  version, version must differ from the installed one) and the space step all work as documented in
  `docs/firmware.md`.
- dM proved the payload loads, the hook fires on the Tidal icon and new assets open.
- dC: the Cover Flow page opened and built 107 thumbnails (14 MB) in `/mnt/mmc/.coverflow`, so the
  extraction path and worker thread work on hardware, but nothing in the cover area took a touch.
- dD fixed that; dE the colours and scrolling.
- eA: the looks work together; the album line still showed `m:` before the album, fixed in fA by
  modelling the text layout exactly (see Lessons).
- gA: fonts, Artists, Shuffle, Now Playing confirmed; lock screen feedback (battery icon huge, clock
  could be smaller, swipe hint smaller, a translucent card using the freed space) became gK.
- iM (M1 Pod as Home) feedback became jA: a second flash of the stock grid at boot and on Back from Now
  Playing (the menu opened 1.2 s / 250 ms after Home; now the grid content is hidden from `home_boot`
  on and the menu opens 10 ms after Home is up); a ghost "Start in: M1 Pod" at the bottom (the text was
  set on the icon image that the icons step inserted as child 0 of the row; now the label is found by
  type); no way back from Shanling Home (the grid flag lived until reboot; now the Tidal icon on the
  grid restores Home); titles too big (22 -> 20 px); the pull-down tiles in two styles (-> one ring
  style); the pod title box wider than stock (248 -> 200).

## Tags in detail (what each step added)

- **b/c series**: battery `percent` (a text progress bar `%d%%`) and `icon+percent`; the classic lock
  screen (138 px clock, 24 px date, `86%`); the watchdog opt-in (`sleep 2 -> 10`) was built as cBW and
  never shipped in the release. `--pdr-all` (zero `.pdr` in all 197 executables, ~540 KB more) was
  never hardware-proven and is gone.
- **d series**: A inert, B hello, C menu, D menu + Cover Flow (dE is the stage-D device build). Rule from
  dD: normal windows are 450 px. Rule from dC: `visible=false` does not stop touches.
- **e series**: Minimal theme (theme+icons+status bar), lists, Now Playing, boot; `look-all` = eA.
- **f series** (all on fA): Inter + SHS font (fI), lock screen 2 (fK, 254 px 1:1 cover, rounded mask
  image), Artists (fR), Shuffle (fS). Branch builds of fI/fK/fR/fS were on eA; the merged ones on fA.
- **g series**: gA everything of f; gB rows + Shuffle page + larger Cover Flow (140 -> 168 px, frame
  320x276, `<key>-168.jpg` cache) + icon battery + pull-down font; gK lock screen 3; gC = gB + gK.
- **h series**: hA icons + unified battery (13 `pod_ic_*` row icons); hB album page + wallpaper + two
  Cover Flow fixes; hC = both; hL/hM guard and Home on gC.
- **i series**: iL guard only on hC, iM Home (device test procedure: iL first, wait 10 s past Home, power-cycle,
  then power off within 5 s of Home once to prove the failure branch, then iM).
- **jA**: polish (`mod_polish`, ring tiles, no grid flash, no title on Home, way back from Shanling Home,
  20 px navbar titles, 200 px title box). The release is stage-N payload, `V2.1jA`, SHA-256
  `f925fba04b5462fe801ce5fd98f23775b38bc033cf7a804874abf8f178f414de`.
- **kA**: the entry moves from the Tidal icon to an added grid icon (id 99, built by the boot guard; Shanling
  starts are armed too), the Home instance of the menu loses its navbar, the three launcher rows become one
  Settings page. SHA-256 `4b7e26dab401074c236d064e9cdb2648d21189754d15417d5f76667a51f92223`
  (`test/golden.sha256`). To check on the device: the icon in page 3's free slot and its press look, Tidal
  opening Tidal, the Home menu from y 0, Settings > Shanling Home and back by the icon, a Shanling start with
  the icon, and the failed-start fallback (no icon afterwards; see `docs/architecture.md` section 9, Recovery).
- **kB**: one album page. The stock `albuminfo_page` is the album view everywhere (a hook on its header builder
  `0x526264`, a 120 px cover rendered by the cover thread, year line, dark Play all, Shuffle; page theme styles);
  Cover Flow, Artists and the All albums card open it with the stock context; the custom album page and
  Cover Flow's track list are gone; the queue page's navbar title is 20 px. Release SHA-256
  `e3ad3be980e95be59ca262ba5303659b6ce2df010651eb2f9b59420a2f41f052` (`test/golden.sha256`).
- **kC**: Now Playing in q2-pod's layout and Tabler round 2 (110 more stock icons; `tools/audit_images.py`).
- **kD**: kA + kB + kC in one build. Tidal's two stock icons are no longer replaced (pins dropped); the album header, Now Playing
  and the Tabler assets were checked together. Recovery fallback: with `/mnt/data/m1pod-bad` present, a tap on Tidal (id 1) opens
  the menu (normal instance, Back); otherwise Tidal is stock. SHA-256 `06c2ff9351acdf2ca321c931ba12395dff40935a2fceb992f31c53d0562dde90` (`test/golden.sha256`).
- **kE**: hardware bug in kD: an album opened from Cover Flow showed no cover. `albumcoverinfo_init` (which Cover Flow runs, as the stock
  Albums page does) sets `albumcover_taskstate` (`0xa05a18`) to 2, and `parse_albumcovertask_thd` sleeps while it is 2; stock's Albums list
  then runs `batchadd_albumcover_task`, which ends with the state 1, but `albuminfo_page_init`'s `add_albumcover_task` does not, so the
  page's cover task was never taken. Cover Flow now calls `batchadd_albumcover_task(0, 0)` (queues nothing, state := 1) before opening
  the page; the page's own 500 ms timer then shows the file the stock thread writes. Also in kE: the album header is tighter (cover 8 px under the
  navbar, 110x36 buttons, header 184 px), the navbar's go-to-Now-Playing icon is Lucide `audio-lines`, the Home instance of the menu keeps 10 px above
  and below its list, the queue drawer is restyled (44 px rows, the playing row white 20 px against muted 18 px), Now Playing: no Hi-Res tag, the heart back
  in the top row and the play mode back in the transport row (round-2 glyphs kept), art 216 px again, prev / play / pause / next back to V2.1jA's solid
  glyphs; the playback-speed badges read 1.0x 1.25x 1.5x 2.0x with a real x sign. SHA-256 `514c52e7bc705500731231350dc9a110b69d80147638757b9ee45157057be0a2` (`test/golden.sha256`).
- **lC**: the Albums grid (`docs/architecture.md` section 5a, `docs/ui.md` section 8). The menu's Albums row opens `ui/m1pod_albums.bin`: one
  320x400 `view_grid` that paints three 92 px covers a row and a one-line ellipsised title under each in its own `EVT_AFTER_PAINT`,
  drag and fling scrolling clamped to the content, a tap opens the stock album page (`cc_open_album`, the sequence Cover Flow uses incl. the cover
  thread release). Covers come from the Cover Flow cache (`<key>-168.jpg`) reduced with an area average into a ring of 24 tiles (0.9 MB, any library
  size), two decodes a frame; an album without a cached cover shows the stock disc, nothing is built. The navbar toggle (Tabler `layout-grid` / `list`,
  four added images) switches to the stock Albums list, whose navbar gets the same button at run time, and back; the choice is
  `/mnt/data/m1pod-albums` (atomic write as Start in) and the Albums row opens the last view. Shared by Cover Flow and the grid and ready for
  the landscape Cover Flow: `patch/covercache.c` (key, path, decode, nearest / box reduction, album list, open album). Pointer events carry
  screen coordinates (`widget_to_local` before any hit test). Payload 37,048 bytes. SHA-256 `e67cb548d7c8a113a39d589f8233ed570d58378c16431d3f808b3c602481742c`
  (`test/golden.sha256`).

## Retired designs (what the docs no longer describe)

- **Entry icon.** Up to jA the M1 Pod entry was the Tidal icon (id 1, taken over); kA made it an icon of its own (id 99).
- **Stock Albums list with a run-time toggle (lC..lG).** The grid/list button was added to the stock `album_page`
  navbar after the dispatcher returned. On the device (lG) it was sometimes missing: the stock navbar is rebuilt by
  `0x524e4c` from the multi-select handlers (`0x525274`, `0x52532c`) and two more callers (`0x5265f4`, `0x5267f0`), the
  window is found by name (possibly an earlier one still closing) and builds on the dispatcher's schedule, so a decoration
  can order itself against none of it. Cause not isolated; lK made the list the page's own mode (no run-time decoration).
- **Landscape Cover Flow navbar (lE/lF).** The navbar was hidden and an exit glyph drawn in the frame's corner, over the
  covers and with Now Playing gone; only the `slide_menu`'s 320 x 276 (61 %) repainted. lH keeps the navbar and invalidates
  the whole frame; mA replaced the navbar button (`btn_landscape`, `on_rotate`, `set_land`) by the Settings switch.
- **Now Playing foot (kC).** Mode and heart at the foot of the art page, a Hi-Res tag, a 192 px art and Tabler's filled
  transport glyphs (they read worse on the device); jA's PIL glyphs stay, kE put both buttons back at the top row.
- **Cover thread (kD).** Cover Flow's album page had no cover: only `albumcoverinfo_init` ran, leaving
  `albumcover_taskstate` 2 and the thread parked; Cover Flow now also calls `batchadd_albumcover_task(0, 0)`.
- **Album page buttons (kE).** The cover starts 8 px under the navbar and the buttons are 110x36, so the track list
  starts 24 px higher than before.

## Lessons

- **A custom-painted view beats a widget per item.** The Albums grid is one `view` that draws only what is visible and keeps a small ring of
  decoded tiles: the cost per frame and the memory (0.9 MB) do not depend on the library, where the stock lists and the artist list create one
  row of widgets per entry. Pointer events are in screen coordinates: convert with `widget_to_local` before hit-testing a position.
- **Hidden widgets still hit-test.** This AWTK's hit test checks only `enable` and `sensitive`, never
  `visible` (`widget_find_target_default` `0x6747d4`, `widget_on_pointer_down_children` `0x6714ac`;
  `widget_set_visible` flips bit 2 only). dC shipped a hidden full-screen `view_tracks` that swallowed
  every touch below the navbar. Always pair hide with `sensitive=false`; decorative overlays are
  insensitive; the tests run demo's own `widget_find_target` on the built page trees.
- **Normal windows are 450 px, not 480** (30 px `system_bar`; 68 stock pages end at y = 450). dD's
  430 px lists overhung the window and 47 px rows (423 px) were shorter than the list, so the menu could
  not scroll. Lay out in 450 px; rows 52 px.
- **Unstyled `list_item`s are white.** Rows must be stock `list_item_style` > `hscroll_label` themed
  `srlabel_leftwhite21_style` (built like `systemset_sysset_page_init` `0x4adb7c`), not bare widgets
  with white text (dD's unreadable track list).
- **Text width = truncated glyph advance + 1 px per glyph** (`canvas_measure_text` `0x644544`,
  `canvas_draw_text` `0x645348`), and `hscroll_label` insets by `margin_left` 2. Summing advances
  undercounts by up to a pixel per glyph; the eA album-line offset (-45) left a sliver of `m:` visible
  (the prefix is 51 px in the stock font, not 45). Measure with `StbText` on the font of the tree being
  built; run font steps first.
- **AWTK repaints only dirty rectangles.** A widget that draws beyond itself (Cover Flow's frame over the
  `slide_menu`) must invalidate the whole area it draws: the canvas is clipped to the dirty rects and a stock widget marks
  only its own rectangle (lF's landscape: only the `slide_menu`'s 276 of 450 px moved). The tests replay the payload's
  invalidations against its runtime geometry (`dirty_rects`, `test/pod/harness.py`).
- **The stock `slide_menu` starts on item 1**, not 0 (constructor `0x613970`): always call
  `slide_menu_set_value`, or an artist's shelf opens on its second album and a one-album shelf has no
  captions.
- **A close animation on a window that a stack-popping loop can reach hangs the UI** (the loop spins
  while the closing window stays topmost for the animation): never give `close_anim_hint` to library
  pages, album detail, the jump list, Now Playing or M1 Pod pages; the settings slides are safe by the
  static audit (`docs/ui.md` section 8).
- **A boot hook needs a crash marker.** The Home foreground handler does not fire at start-up (the first
  open dispatches `WILL_OPEN`/`OPEN`); hook `home_page_init` instead, run stock first, write the marker
  (temp + fsync + rename) before anything risky, clear it by a 5 s timer, let a found marker write a
  sticky note and fall to stock. The boot loop is impossible by construction.
- **Asset order is behaviour.** The icons step inserts an image as child 0 of every menu row, so code
  that touched "child 0" set text on the icon (iM's ghost label); find widgets by type or name. Steps
  that re-lay out a page from scratch (lock screen) go after the steps whose glyphs they use.
- **Widget names are an API.** demo looks everything up by name (recursively), so reparenting or
  restyling is safe and renaming or deleting is not.
- **An asset can only pick what style names resolve to.** Row geometry on the library pages is code
  (`addiu` immediates); q2-pod's way is pinned immediates, call-site retargets and a small payload
  function, never a prologue rewrite, never anything reachable from `platform_init`
  (`tools/reach.py` checks).
- **The recovery path is unverified.** Only kernel and rootfs are flashed; keep the stock restore
  package (`--restore`) and the previous tag at hand, never flash two untested things in one package
  when one will do, and the SD kill switch `m1pod-off` does not help a loop before the hook runs.
- **AWTK scales images by nearest neighbour** and has no image clipping (`round_radius` rounds only
  the background): pre-scale images and draw them 1:1; for a rounded picture over a translucent card
  the card is rounded and the picture square.
- **Static evidence is not a device test.** The tests run the real payload under Unicorn with mocked
  stock calls and model demo's hit test, text layout and fills with demo's own code
  (`test/awtk_fill.py`), but playback, gapless, real frame timing and the panel were only ever checked
  on the device.
- **Determinism.** Added files get a fixed mtime, PNGs are written without metadata or by a plain zlib
  writer, fontTools is pinned (4.67.0): two clean builds are byte-identical, which is what makes golden
  hashes useful.
