# History: milestones, hardware results, lessons

Per-tag details live in git: the commit message of each integration commit says what the tag added
(`git log --oneline`, `git log --grep V2.1nB`). Test-build tags (suffixed, such as oHF or nWS) are not
recorded; they were the content of the release that followed. The checkpoint tags in git
(`git tag`: `checkpoint-V2.1kE`, `lL`, `mB`, `mE`, `nL`, `nN`) mark flashed or accepted states.
Only the current release and `--restore` (V2.1R) are buildable from this tree; older packages are not
reproducible from it (their variants and flags were removed). The design of what survives is in
`docs/architecture.md` and `docs/ui.md`, firmware facts in `docs/firmware.md`, the process in
`docs/workflow.md`. Hardware results are the user's reports on the device. Nothing was ever bricked;
the recovery button combination for this model remains unverified.

## Milestones

- **V2.1R** (2026-10-19): stock images repacked with a new tag, the way back (`--restore`). Flashed, works.
- **V2.1bB / cS / cLB** (2026-10-19): battery percentage, the space step alone, a classic lock screen: the
  asset pipeline, the updater's checks and the space step work as in `docs/firmware.md`. cLB works.
- **V2.1dM** (2026-10-20): the first payload (appended `PT_LOAD`, one hook); the Tidal icon opens an
  iPod-style menu. Works. (dA inert payload and dH hello page were skipped.)
- **V2.1dE** (2026-10-25): Cover Flow page and per-album cache, after dC (touch ignored) and dD
  (white-on-white tracks, menu would not scroll). Works.
- **V2.1eA / gA** (2026-10-25): Minimal theme, library lists, Now Playing, boot logo; Inter + Source Han Sans font,
  Artists, Shuffle, iPhone-style lock screen. Confirmed (lock screen refined in gK).
- **V2.1hC** (2026-10-26): Tabler icons, album page, wallpaper, artist Cover Flow fixes. Flashed, no problems.
- **V2.1iL / iM** (2026-10-26): the boot guard alone (first start-up code proven), then M1+ Pod as Home.
  Both work; iM's feedback became jA.
- **V2.1jA**: iM polished; the build the player ran for a while.
- **V2.1kD / kE** (checkpoint kE, 2026-10-26): entry as its own Home icon (id 99) with the Tidal-icon recovery
  fallback, one restyled stock album page everywhere (hook on its header builder), Now Playing in q2-pod's
  layout, Tabler round 2. kD flashed (Cover Flow's album page had no cover, fixed in kE).
- **V2.1lL** (checkpoint, 2026-10-26): Albums grid/list page, landscape Cover Flow (turned 90 degrees, whole-frame
  repaint), Cover Flow gestures, depth-mode shelf. Accepted.
- **V2.1mA** (2026-10-26): customisable iPod-ordered menu and Settings pages (Main Menu, Cover Flow, Home Screen,
  Playback). Flashed.
- **V2.1mB** (checkpoint, 2026-10-26): Now Playing variant D (grabber Back, 264 px art with rounded corners, cover-tinted
  window, remaining time). Works.
- **V2.1mE** (checkpoint, 2026-10-26): 13 languages, Cover Flow opens on the playing album, album sort Artist/Album. Works.
- **V2.1mK / mM / mS** (2026-10-26): Lucide icon set adopted (experiment mK, then mM, mS flashed); rounded transport glyphs,
  wave playing-row marker, tinted status bar, Cover Flow button in the Albums navbar.
- **V2.1mX / mY** (2026-10-26): bare Lucide glyph rows, Settings > Home Screen, Extras > Screenshot. mY flashed; its
  pull-down and lock-screen bugs were fixed in nB (see Lessons).
- **V2.1nJ** (2026-10-27): Inter Medium, list gestures, 2-column Albums grid, one-tap Main Menu, the pull-down fix,
  boot logo "M1+ Pod". Flashed.
- **V2.1nK / nL / nM / nN** (nL, nN checkpoints, 2026-10-27): album page Play all/Shuffle, tone cache and tinted album page,
  More menu reworked as a bottom sheet (nM's in-place expansion sat mid-screen). Flashed, looks good.
- **V2.1nP / nT** (2026-10-27/28): mini player bar on the Home menu with backdrop blur; Recently Played shelf. Flashed, good.
- **V2.1nW / nX** (2026-10-28): glass beyond the mini bar (lock card, More sheet, Now Playing discs), Lucide star favorite.
  Looks great.
- **V2.1oA** (2026-10-28): Albums on the stock `scroll_view`. Good.
- **V2.1oC / oD** (2026-10-28): Playlists page, every navbar on the Pod slots, glass navbars on our pages. Good.
- **V2.1oE / oF / oG** (2026-10-28): Playlists "..." menu in glass, hideable Extras row, navbar fade hidden at rest. Good.
- **V2.1oH / oI** (2026-10-29): Back from Now Playing no longer turns song lists into albums; the Songs page in the
  Apple Music manner. Copied to the card, good enough.
- **V2.1oJ** (2026-10-29): less glass on the album page buttons and Now Playing discs, plus the performance
  commit (cover-cache scan in steps, Now Playing idle behind other pages). Test build oHF looked good.
- **V2.1oK** (2026-10-29): the Daily Mix, a "Made for You" card on the Home menu and its Apple Music style page, kept in our
  own file (no stock playlist). Test build oJD flashed.
- **V2.1oL** (2026-10-29): Play (album page, Songs page, Daily Mix) turns shuffle off.
- **V2.1oM** (2026-10-29): the product is **M1+ Music** (was M1+ Pod: Home icon label, menu title,
  About row, Start in M1+ Music), the internal name `m1plus` (was `m1pod`: symbols, assets, `/mnt/data` files, the
  `m1plus-off` kill switch) and the Home grid icon the Lucide smartphone. The device files were moved by a one-time
  boot-guard migration in test build oKM (on oK), flashed and booted with settings kept; oM drops the migration, so a
  player still on oL or older starts with default settings. The way to rename device files: a migration build first, then remove it.
- **V2.1oN** (2026-10-29): Favorites, Recently Added, Recently Played, Most Played, Hi-Res and every playlist
  open on our Songs page instead of the stock song list (no Sort, no rail; play, Shuffle, Delete and Add with the list's
  class, as stock). Test build oMS flashed, "looks great".
- **V2.1oO** (2026-10-29): the album page's multi-select and Now Playing are one glass capsule like our pages'
  toolbars (images only, the shared stock builders untouched), and a pressed capsule piece shows a round highlight on its glyph
  instead of a lit slab. Test build oNC flashed, "works".
- **V2.1oP** (2026-10-29): Genres and Composers open on our Artists page (no artist-type switch), a genre's
  songs on our Songs page (class 0xff09, no Search: a Select | Now Playing capsule) and a composer's albums in Cover Flow
  (loadAlbumList(0xf005) -> 0xff02, the album page as 0xff14). Test build oNG (on oN) flashed, "looks good".
- **V2.1oU** (2026-10-29): an artist's Cover Flow page has a Songs | Now Playing capsule (the All albums
  navbar disc is gone; the card stays) whose Songs opens all the artist's songs on our Songs page (class 0xff11: the 0x390 byte
  browsing record of loadAlbumList(0xf004) + loadAlbumdetailList(0xff01, the All songs row), put back before every query
  and play; the album as a row's grey line). Test build oTA flashed.
- **V2.1oW** (2026-10-30): the **Pod** MVP, a virtual iPod Classic (an Extras item, Play group): a fullscreen page,
  320 x 240 screen over a touch click wheel tuned to the Apple Music 404-page iPod (15 degree steps, tiers 1 .. 34, a hard stop at the ends),
  the library lists, its own Now Playing, Shuffle Songs, a Settings list, Cover Flow on white under the title bar, and the main menu's cover
  pane panning as q2-pod's Split Home. Test builds oPK .. oUIP flashed; the user accepted it as the MVP.
- **V2.1oX** (2026-10-30): Artists, Genres and Composers in the Songs page's style (one painted list, letter sections, the
  A-Z rail; patch/azlist.c shared with Songs), Delete Playlists as a select mode on our Playlists page (the stock delete, verified on the
  device), and a playlist's header on the Songs page (mosaic and name; the count only under the last row). Test builds oWA, oWB flashed,
  "looks good". Lesson: cc_decode flattens over black, so an image drawn over a cover needs its own alpha (the select mark's black square).
- **V2.1pA** (2026-10-30): **Cassette Mode**, a landscape fullscreen cassette Now Playing page (after Sony's NW-A100
  cassette screen and FiiO's Tape mode) from a row on page 1 of the More sheet: the picture turned onto the portrait panel, rotated text
  blended glyph by glyph, reels from pre-rendered hub frames, tape packs that show progress, taps only (play/pause, a screw closes),
  Normal, Chrome and Metal themes in Customize > Cassette Mode. Test builds oXTP .. oXTS flashed, "good enough". Lesson: a page's touch
  handler must not grab or eat move events, or the system pull-down from the top edge stops working (oXTP's swipes broke it).
- **V2.1pF** (2026-10-30): **Podcasts feeds** on the device: shows imported from `Podcasts/subscriptions.txt`,
  Refresh All on one worker thread over the app's own libcurl with Mozilla's CA bundle in the firmware, a progress dialog with
  Cancel, episodes not on the card listed greyed on a show opened from Feeds, and cover art downloaded and shrunk once to a 192 px
  JPEG (demo's libjpeg; PNG through a streaming decoder of our own). Test builds pAFA, pCFA .. pCFC flashed: the 4 MB All-In feed,
  a 3000 px JPEG and a 2000 px RGBA PNG cover all worked. Lesson: podcast art is often too large for the stock loader (36 MB for
  3000 px), so shrink once on download instead of decoding at full size on every page open.
- **V2.1pI** (2026-10-31): **Podcasts episode downloads** (policy after q2-podcasts): one at a time into a `.part`
  beside the episode, 512 KB chunks each opened, written, synced and closed, Range resume, retries, a 32 MB card margin; a Downloads
  page; select-and-delete of episodes; no unplayed-dot column. Test build zQKWXAAAC flashed: an episode downloaded and played.
  Finding: stock's `reset_poweroptions_timer(1, 1, 0)` (0x4d7874; its arguments gate standby, auto power-off and the screen light)
  called from a page timer while a download runs keeps the device out of standby with the screen still turning off.
- **V2.1pJ** (2026-10-31): **our own on-screen keyboard** (`docs/modules/keyboard.md`): iPhone OS 1 style QWERTY
  (29 x 36 keys, 3 px gaps, 180 px), a key pop-up, 123 and #+= pages, a search field, gaps resolved to the nearest key, and
  **Chinese (Pinyin)** input behind Customize > Keyboards (a 中/EN key, a candidate strip, predictions). Test builds zPPCPAAAC,
  zPGFYAAAB (probe) and zPGFYAAAC flashed: all worked. Findings: stock's T9 popup is laid out 640 px wide in a 320 px window, and
  stock's Chinese input never had a dictionary (its init asks for an absent `/usr/dict_pinyin.dat`) while the shipped, unreferenced
  `data/gpinyin.dat` opens with `im_open_decoder` in 76 ms (~1 MB, searches 0.1-2.5 ms). Tap log of 155 taps: no systematic offset
  (mean -2, +3 px), all 9 misses in the 1-4 px gaps between keys, hence the nearest-key rule.
- **V2.1pK** (2026-10-31, current release): the **Podcasts Show page in Apple Podcasts style** (round 1 of the revamp, designed
  from preview sheets the user picked): the page tinted from the cover (the album page's algorithm), the album page's 160 px header,
  episode cells with a date line (played check, downloaded disc), 2-line title and description from the feed, and a state pill
  (outlined download, filled play); bottom sheets in the style of Now Playing's More sheet replace dropdown menus (Playback Speed,
  Refresh Feed, Select Episodes, Mark All as Played, Unsubscribe; per episode Download / Remove Download, Mark as Played /
  Unplayed). Test build zWWLSAAAB flashed, accepted. Lesson: the user rejected a top-right dropdown menu as crowded but accepted
  the same actions in a bottom sheet behind the same "…" button.

## Hardware results (what broke on the device, and why)

First tests, 2026-10-19 to 10-25:

- **dC.** The Cover Flow page opened and built 107 thumbnails (14 MB) in `/mnt/mmc/.coverflow`, so extraction and the worker
  thread work on hardware, but nothing in the cover area took a touch: a hidden full-height view still hit-tested. dD made hidden
  widgets insensitive and added a touch layer; its track list was white on white and the menu would not scroll (lists were
  430 px high, 47 px rows too short for the list); dE fixed both.
- **eA.** The Now Playing album line still showed a slice of `m:`: the text layout was not modelled exactly (fA: width +1 px per
  glyph, label `margin_left` 2; the prefix is 51 px in the stock font, not 45).
- **gA.** Lock screen feedback: battery icon huge, clock and swipe hint too big, free space for a translucent card (became gK, 280 px
  cover). gC feedback: album page wanted, wallpaper, battery icons mismatched, artist Cover Flow opened on the 2nd album,
  single-album captions missing (hA/hB).
- **iM** (Home) feedback became jA: a second flash of the stock grid at boot and on Back from Now Playing (the menu opened 1.2 s /
  250 ms after Home; now the grid content is hidden from `home_boot` on and the menu opens 10 ms after Home is up); a ghost
  "Start in: M1+ Pod" (text set on the icon image the icons step inserted as child 0 of the row; the label is now found by type);
  no way back from Shanling Home (the grid flag lived until reboot; now the Tidal icon on the grid restores Home); titles too big
  (22 -> 20 px); pull-down tiles in two styles (-> one ring style); the pod title box wider than stock (248 -> 200).
- **iL device test procedure:** iL first, wait 10 s past Home, power-cycle, then power off within 5 s of Home once to prove the
  failure branch, then iM. Card log `m1pod: armed` -> `m1pod: boot ok, marker cleared`.
- **kD.** An album opened from Cover Flow had no cover. `albumcoverinfo_init` (Cover Flow runs it, as the stock Albums page does) sets
  `albumcover_taskstate` (`0xa05a18`) to 2 and `parse_albumcovertask_thd` sleeps while it is 2; stock's Albums list then runs
  `batchadd_albumcover_task`, ending with the state 1, but `albuminfo_page_init`'s `add_albumcover_task` does not, so the
  page's cover task was never taken. Cover Flow now calls `batchadd_albumcover_task(0, 0)` (queues nothing, state := 1) before
  opening the page; the page's 500 ms timer then shows the file the stock thread writes.
- **lF (landscape Cover Flow).** Only the first ~60 % of the frame animated (only the `slide_menu`'s 320 x 276 was repainted), the exit
  glyph lay over the covers, Now Playing was gone with the hidden navbar; the Albums toggle overlapped the stock list's search
  button. lH repaints the whole frame, keeps the navbar; mA moved the toggle to a Settings switch.
- **lG.** The grid/list button added at run time to the stock Albums navbar sometimes vanished: the stock navbar is rebuilt by `0x524e4c`
  (from the multi-select handlers `0x525274`, `0x52532c` and callers `0x5265f4`, `0x5267f0`), the window is found by name
  (possibly an earlier one still closing) and builds on the dispatcher's schedule, so a decoration cannot order itself against
  it. Cause not isolated; lK made the list the Albums page's own mode (no run-time decoration of stock pages).
- **mB.** Tint, sharp rounded cover and remaining time work; the after-paint corner painter stayed. The cover file is 264 px so
  it draws 1:1.
- **mY.** Pulling the control centre down from the main menu, after about 40 % of the screen everything but Now Playing vanished;
  coming back from the lock screen showed one frame of the menu in the default order. Cause (nB): the stock `list_view` layouter
  re-stacks children by index before every paint (after any `widget_set_visible`), putting the asset order back, and its
  paint-children hook exits early at the first row below the canvas. Fix: `menu_arrange` and the Main Menu page restack the rows'
  children in page order (`widget_restack`, hidden rows last) and clear the `list_view` paint hook (`0x60c164`). Verified on demo's
  own layout/scroll/paint/pointer code in Unicorn (`test/pod/pulldown.py`: relayout, lock screen frame, pull-down sequence,
  Main Menu arrows each fail with the mY arrangement and pass now). Not reproduced: the exact device canvas while the dropdown
  animates (rendering is not emulated). Device checks: pull down over the first row slowly and fast with default and custom
  order, rows stay behind the dialog and after it closes; lock/unlock with a custom order shows no default-order frame; Main
  Menu arrows and switches; scroll the menu.
- **nA.** A tap on the Main Menu up arrow moved the item and toggled it too: the stock button answers pointer DOWN/UP with `RET_OK`
  so the row got the click as well (reproduced in Unicorn, `test/pod/menutap.py`). The arrow is now an insensitive picture
  and the row decides by where the touch went down (arrow rectangle row x 191..240, 50 x 52 px).
- **Main Menu not following its own changes (mQ).** The saved order showed in the menu but the page's rows did not re-order
  until reopened; after every save the page re-arranges, keeps the changed row inside the list window (`yoffset`) and
  invalidates the whole window (`widget_invalidate_force`) instead of per-widget dirty rectangles; a failed save touches nothing.
- **nC / nI (Play all pill).** nC assumed AWTK centres the pill's text; it draws it LEFT aligned at the start of its rect
  (`widget_draw_icon_text` `0x67235c` reads `text_align_h`, default 2 = left), so a negative `spacer` pulled the text onto the
  glyph ("P" touching). Also `icon_at` auto is top when icon height + font size < rect height (18 + 20 < 44). nI: `text_align_h`
  left, `spacer` -5, `margin_right` 0, and the album header hook sets `margin_left` per page build from `widget_measure_text`
  (`0x66c7e0`) via `widget_set_style` (fallback: the style's English margin 45), so the glyph/text pair is centred with an 8 px gap
  in every language.
- **nM / nN (More menu).** The folded menu (Look up Album / Look up Artist / Add to playlist / More) expanded in place mid-screen;
  nN made it a bottom sheet (y 280, 4 x 50 rows) with the dialog highlighter (alpha 130) dimming Now Playing, two pages of
  equal height, re-anchored when the Delete confirm covers it; the Speed row label was widened ("Speed", badges moved), its note
  shortened to "Files below 48 kHz only".
- **oA.** Without the stock `scroll_bar_m` the `list_view` layouter does not make the `scroll_view` yslidable, so nothing scrolled
  (test build nX); a list pulled past an end (stock overscroll) must never look up an album outside the list (row -1 crashed the
  app and rebooted the player, test build nY); no cover decoded while a list drags or animates.
- **oB.** The menu re-arranged whenever it was back in front (`on_menu_fg`) and reset the list offset to 0, so Back from any page
  returned to the top; `menu_arrange` leaves the offset, clamped to the new range.
- **oC.** On device shots the stock Now Playing glyph sits 2 px left (x 262), the 44 px Back 3 px left (x 3), multi-select needs no
  shift: the Pod navbar slots follow these measurements.
- **oE.** A 24 px glyph per Playlists menu row looked big (20 px kept); the last row looked taller with padding, so four 50 px
  rows fill the card with none; the card is as wide as the language needs (`pl_fit`: English 180, Spanish 291).
- **oF.** A menu file saved before oF has no trailing `x`, so a customised menu comes up without Extras until switched on (no compat path).
- **oG.** The navbar fade (`img_nb_fade`) darkened the first content at rest (Albums/Playlists list alpha 146, grid ~50): now built
  hidden on those pages and shown only while scrolled; text pages a steeper curve.
- **oH.** `cc_albums()` (`loadLocalClassList(0xf003)`) in Now Playing's tick left the album list in `*pdeq_showlist`; the stock
  `allmusic_page` does not read again on a to-foreground with its class unchanged (`0x527c28`), so a playlist's songs page came
  back as the library's albums with folder icons (`list_get_left_icon` `0x4d972c`: type 4 = `icon_folder`) and a tap played from
  that list. The tick now only records; the menu's to-foreground resolves the key. The Playlists page also stops its loader on
  `EVT_WINDOW_TO_BG` (a scan replaced `*pdeq_showlist` and `classinfo[1]` under the songs page).
- **oI.** A run-per-letter rule left no sections on a real library; the Songs page uses the non-decreasing labelling with the most
  songs under their own letter (stock Initial byte `stSongInfo + 0x54`).
- **Font fit (nG).** Inter Medium: tightest Cover Flow progress line fr_FR / it_IT / po_PL 299 of 300 px, ru_RU Sort value 105 of 106
  px; uk_UK stock "System Settings" clips at 202 of 200 px (a stock label). A saved main-menu file containing `j` is invalid and
  gives the default menu (accepted, no compat).
- **Space step.** Flashed 2026-10-19 (V2.1cS); in every package since. The watchdog opt-in (`sleep 2 -> 10`, cBW) never shipped;
  `--pdr-all` (all 197 executables, ~540 KB more) was never hardware-proven and is gone.

## Retired designs (what the docs no longer describe)

- **The Pod's Ken Burns cover pane** (test build V2.1oSIP): a 168 px cover window panned and zoomed into the pane every 80 ms, with
  crossfades; on the device the covers jiggled (a window resized and moved every frame is resampled differently each time). Replaced by
  one cover scaled once and copied 1:1 at whole pixels (`docs/modules/ipod.md` "The cover pane").
- **Entry icon.** Up to jA the M1+ Pod entry was the Tidal icon (id 1, taken over); kA made it an icon of its own (id 99).
- **Stock Albums list with a run-time toggle (lC..lG).** See the lG result above; replaced by the page's own list mode (lK).
- **Landscape Cover Flow navbar button (lE/lF).** Exit glyph in the frame, navbar hidden; now a Settings switch and the navbar stays.
- **Now Playing foot (kC).** Mode and heart at the foot of the art page, a Hi-Res tag, a 192 px art and Tabler's filled transport
  glyphs (they read worse on the device); jA's PIL glyphs stay, kE put both buttons back at the top row.
- **Custom album page and Cover Flow track list (before kB).** The stock `albuminfo_page` is the album view everywhere.
- **Custom drag/velocity/fling code for the Albums grid (before oA).** Replaced by the stock `scroll_view`.

## Lessons

Hit-testing and layout
- **Hidden widgets still hit-test.** This AWTK's hit test checks only `enable` and `sensitive`, never `visible`
  (`widget_find_target_default` `0x6747d4`, `widget_on_pointer_down_children` `0x6714ac`; `widget_set_visible` flips bit 2 only).
  dC shipped a hidden full-screen `view_tracks` that swallowed every touch below the navbar. Pair hide with `sensitive=false`;
  decorative overlays are insensitive; the tests run demo's own `widget_find_target` on the built page trees.
- **Normal windows are 450 px, not 480** (30 px `system_bar`; 68 stock pages end at y = 450). Rows 52 px.
- **Pointer events carry screen coordinates**: `widget_to_local` before any hit test.
- **The stock `slide_menu` starts on item 1**, not 0 (constructor `0x613970`): always call `slide_menu_set_value`, or an artist's
  shelf opens on its second album and a one-album shelf has no captions.
- **Stock relayouts re-stack list children by index** and `list_view`'s paint-children hook exits at the first row below the canvas
  (see mY/nB above): restack rows in page order, clear that hook. Stock never met rows hand-placed under a pull-down zone.
- **A `list_view` needs the mobile `scroll_bar_m`** for its `scroll_view` to be yslidable; the stock list code is also what gives
  drag, fling and overscroll for free.
- **Unstyled `list_item`s are white.** Rows must be stock `list_item_style` > `hscroll_label` themed `srlabel_leftwhite21_style`
  (built like `systemset_sysset_page_init` `0x4adb7c`).
- **Asset order is behaviour.** The icons step inserts an image as child 0 of every menu row, so code touching "child 0" set text on
  the icon (iM's ghost label); find widgets by type or name. Steps that re-lay out a page from scratch go after the steps whose
  glyphs they use.
- **Widget names are an API.** demo looks everything up by name (recursively): reparenting or restyling is safe, renaming or
  deleting is not.

Painting and text
- **AWTK repaints only dirty rectangles.** A widget that draws beyond itself must invalidate the whole area it draws (lF's landscape:
  only the `slide_menu`'s 276 of 450 px moved). The tests replay invalidations against runtime geometry (`dirty_rects`,
  `test/pod/harness.py`). Prefer `widget_invalidate_force` on the whole window after structural changes.
- **Text width = truncated glyph advance + 1 px per glyph** (`canvas_measure_text` `0x644544`, `canvas_draw_text` `0x645348`), and
  `hscroll_label` insets by `margin_left` 2. Measure with `StbText` on the font of the tree being built; run font steps first.
- **AWTK button text is left-aligned in its rect** (`text_align_h` default left), not centred; a negative `spacer` pulls the text
  onto the icon. `icon_at` auto is top when icon height + font size < the rect height.
- **AWTK scales images by nearest neighbour** and has no image clipping (`round_radius` rounds only the background): pre-scale
  images and draw them 1:1 (cover file 264 px); for a rounded picture over a translucent card the card is rounded and the picture square.
- **A button's icon is drawn at its own size on the rect's centre, unclipped** (`canvas_draw_icon_in_rect` `0x648f90`): an image wider than
  its button reaches past it (oO: multi-select's 50 px glass over its 46 px button bridges the stock builders' 2 px gap; seen seamless on the
  device). Keep what a press changes inside the button: only its rect is repainted.
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
  track 1 but kept shuffling with Now Playing showing Shuffle (oL): an explicit Play sets the in-order mode (`pod_set_in_order`,
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
- **The recovery path is unverified.** Keep the stock restore package (`--restore`) and the previous tag at hand, never flash two
  untested things in one package when one will do; the SD kill switch `m1pod-off` does not help a loop before the hook runs.
- **Static evidence is not a device test.** The tests run the real payload under Unicorn with mocked stock calls and model demo's
  hit test, text layout and fills with demo's own code (`test/awtk_fill.py`), but playback, gapless, real frame timing and the
  panel were only ever checked on the device. A UI bug starts with a reproducer.
- **Determinism.** Added files get a fixed mtime, PNGs are written without metadata or by a plain zlib writer, fontTools is pinned
  (4.67.0): two clean builds are byte-identical, which is what makes golden hashes useful.
- **The updater checks** `firmware_v20.info` lines, MD5s, "V" in the version, and that the version differs from the installed one
  (`docs/firmware.md`).
