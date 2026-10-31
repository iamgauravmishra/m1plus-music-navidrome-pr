# Cover Flow

**Sources:** `patch/coverflow.c`, test `test/pod/coverflow.py`, `test/coverflow.py`.

A cover carousel over the stock Local Music albums, after q2-pod's Cover Flow design, for the
320x480 touchscreen (wheel-only parts gone). Opened from the menu's Cover Flow row; adds no hook:
everything runs from the page's own widgets, one timer and one worker thread. Also opened per artist
(section 5).

- **Covers.** One cover per album on a shelf (committed album, offset; every shelf has ends: no wrap) drawn by the payload's
  depth renderer: the centre cover faces you at `ART_SIZE` 168 px, the neighbours turn 60 degrees
  inward, step back and dim (`CF_BRIGHT1` 192, `CF_BRIGHT2` 128 of 256, gone three out), each with a
  26 px reflection. Geometry (`offsets.inc`): frame 320x276, `CF_TOP` 31, `CF_EYE` 312, `CF_X1` 110,
  `CF_XS` 48, `CF_Z1` 96, `CF_ZS` 22, `DRAG_PX` 108. Change them together and re-run
  `test/coverflow.py`.
- **Renderer.** (`cfg_t` and `coverflow_render` are declared in `patch/coverflow.h`; the iPod page's Cover Flow screen draws with the same renderer, `docs/modules/ipod-coverflow.md`; its `tail` and `bg` fields are 0 for these two shelves: `bg` 0 composites over black; nonzero (the iPod's white) turns the brightness fade into transparency, `put(tex, cov * bright >> 8)`, a faded cover records no solid span, and the final pass adds `shade(bg, 256 - have)` to the premultiplied colour.) After Rockbox PictureFlow via q2-pod; all integer (16.16 turns, 1/16 px geometry, 1/256
  px row spans). One `bitmap_create_ex(320, 276, ..., RGBA8888)` frame plus 9 textures of 168^2 and one
  placeholder: about 1.48 MB of heap while open. If an allocation fails the page falls back to flat
  covers: a stock `slide_menu` whose `image` children (one per album) show the cached JPEGs, `ART_NEAR`
  3 either side. The frame is drawn from the touch layer's `EVT_AFTER_PAINT` (`0x120`, dispatched by
  `widget_paint` `0x66de3c`), an instance event registered with `widget_on`; an unchanged position
  reuses the frame. About 3.47 M payload instructions per frame under Unicorn.
- **Shelf position.** Depth mode owns it (`cfpos`: committed album, offset) and has no stock
  widget per album: the stock `slide_menu` lays out every child on each `xoffset` or `value` change
  (`slide_menu_set_prop` `0x613c94` -> `widget_layout_children` `0x656d1c`, which hides all children
  and places the near ones, `0x613090`; `slide_menu_set_value` `0x6139fc`), O(albums) per drag step
  and snap tick with up to 4000 empty children. The flat fallback keeps that `slide_menu` and drives it
  through its public properties (`value`, `xoffset`, `h`; no field offset pinned). Both read through
  one set of accessors (`value()`, `offset()`, `stride()`, `count()`, `set_offset()`, `set_value()`):
  `p = value - offset / stride`, the stock commit's `value - round(xoffset / item width)` with the item
  width the widget height (`0x612360`), so depth mode keeps the stock units (`CF_VIEW_H` per cover).
  The ends (one bounded path for the main and the artist shelf: `bound()`, `around()`, `visual()`, `commit()` clamp, nothing wraps), the captions and the last-album memory follow `set_value`.
- **Textures.** Paint never touches a file: it renders from resident textures (`fx_ring`),
  the placeholder standing in for a cover not decoded yet. A one-shot page timer (`on_load`, `LOAD_MS`
  1, removed at destroy) decodes one wanted cover per callback on the UI thread (`cc_decode`:
  `widget_load_image` is not known to be thread-safe, so the preparation worker never calls it),
  nearest first: the centre, the ring alternately ahead of and behind the travel, then the next cover
  ahead; a slot is reused from the cover farthest from the centre that is not wanted, so the one just
  left behind survives a reversal (9 slots for 8 wanted). No shelf wants anything past its ends. Only the centre cover is decoded when the shelf is built (`to_covers`: one `fx_fill(1)`, so the open call makes two image loads, the placeholder and the centre, instead of the whole wanted set of up to nine); the ring and the next one ahead follow one per `on_load` tick (armed there, or by the first paint if the timer was refused). The Preparing screen flow is unchanged (a progressive shelf while missing art builds is not done: placeholders count as resident today). Each decode still blocks the
  UI thread for its length; not measured on the device: measure before considering a decoding worker
  (that needs a reviewed thread-safe decoder publishing finished buffers).
- **Touch.** A transparent full-size touch layer (a `view` inside `view_covers`, over the flat
  fallback's `slide_menu`) takes `EVT_POINTER_DOWN/MOVE/UP` (`0xff/0x101/0x103`) and abort `0x107`,
  grabs the pointer (`widget_grab`/`ungrab`) and drives the shelf (`set_offset`, `set_value`). MOVE
  and UP share one tracker (`track()`): the greatest excursion from the
  down point in either axis, a horizontal drag that starts at `DRAG_START` 5 px along the carousel and no
  more across (its travel counted from that threshold, so neither a jump nor a lost sparse event), the
  shelf under the finger, and a ring of samples. A release is a tap only if no drag started, no
  animation was interrupted and the excursion, release included, stayed within `TAP_SLOP` 12 px; a tap
  is hit-tested by x: the centre cover (`|x - 160| < 84`) opens the album, a side cover comes to the
  centre. **The ends.** The shelf stops at the first and the last album, as Apple's does. Past an end only the finger goes, rubber-banded (`rubber()`): the shelf follows at half speed and saturates at `OVER_NUM` / `OVER_DEN` (2/5) of a cover, `m x / (x + 2 m)` for `x` offset units of finger travel past the end (so the end cover stays the centre: `visual()` clamps it and the renderer's offset from it stays under 1/2). `unrubber()` is its inverse: a press that finds the shelf stretched (the snap is springing back) takes the drag up from where it is, no jump. A fling and a tap are clamped by `bound()`, so they stop at the ends; the release eases (the one snap) from the stretched offset back to the end cover. A one-album shelf is both ends. The flat fallback has no rubber band (its `slide_menu` would show wrapped covers): the drag is clamped. Anything else settles from where the shelf is: a drag coasts by the fling (the velocity from
  the oldest sample of the last `FLING_WINDOW` 80 ms to the release, coasting `FLING_MS` 120, at most 3
  albums; a finger that rested has none), a mostly vertical gesture moves nothing. A press during the
  snap stops the shelf where it is (its release eases to the nearest cover, or a drag carries on from
  there). The snap eases by elapsed time (`time_now_ms`): `1 - (1 - p)^3` over `SNAP_BASE_MS` 120 +
  `SNAP_ALBUM_MS` 60 per album of travel (180 ms for one album, at most 360), stepped by a 16 ms one-shot
  page timer, exactly on the target when the time is up, so late callbacks do not stretch it; a refused
  timer commits at once, so no nonzero offset is ever left without its timer. Then the commit
  (offset 0, `set_value`). The thresholds and times are trials, to tune on the device. The flat
  fallback's `slide_menu` itself is insensitive. Back leaves the page.
- **Repaint.** AWTK paints only dirty rectangles: `canvas_begin_frame` `0x6447b4` clips the canvas to the LCD's dirty
  rect (`canvas_set_clip_rect`), and `widget_invalidate` `0x668d9c` (no rect: the widget's own 0, 0, w, h; skipped while
  the widget's dirty flag, `0x24` bit 9, is set) hands it up through `widget_invalidate_default` `0x674920` to the window,
  translated by each parent's x, y and not clipped by them. The stock `slide_menu` marks only its own rectangle when
  `xoffset` changes (`slide_menu_set_prop` `0x613c94`: store, `widget_layout_children`, `widget_invalidate`) or `value`
  does (`slide_menu_set_value` `0x61399c`, tail call `0x613a1c`). So every offset change and album change calls
  `widget_invalidate_force` on the touch layer, which is always the frame's rectangle (`redraw()`). Tests model this (`dirty_rects` / `abs_rect` in `test/pod/harness.py`).
- **Landscape.** The page, main or per artist, opens in a landscape presentation in
  the 320 x 400 body under the navbar when **Settings > Library > Landscape** is on (the switch row of `m1plus_library`; nothing changes the presentation while the page is open); no global
  LCD orientation changes. The navbar is untouched in both (Back, the title, Now Playing). The content is turned 90 degrees **clockwise** on the screen (its top edge at the screen's right: the
  player is held turned counter-clockwise, the status bar and navbar then a strip on the left; the direction is the
  map in `turned()` / `where()` / `coverflow_render`), the carousel runs along the 400 px side. `cfg_t` (`cf_portrait`,
  `cf_land`) is the shelf's geometry; `coverflow_render(g, d, pitch, ...)` writes the logical frame through a column
  stride of `pitch` and a row stride of -1, so the turn costs no copy and no second bitmap: logical (x, y) is physical
  (319 - y, x), `CFL_Y` 50 px down the window. Landscape numbers (`CFL_*` in `offsets.inc`): logical 400 x 320, the
  centre cover the 168 px texture 1:1 as in portrait (no zoom) at top 28, portrait's eye, depth and reflection, `x1`
  160, `xs` 84, `CFL_DRAG_PX` 132: two covers either side, the outer ones cut by the edge (portrait: one and a half). A
  tap beyond the first side cover's drawn outer edge (projected) brings the second one in. The frame bitmap is the
  body, 320 x 400 x 4 = 500 KB (portrait 345 KB; one exists at a time, the new one is made before the old goes, so a
  refusal leaves the page as it was); textures are shared. Frame cost under Unicorn about 4.03 M payload instructions
  against 3.48 M (1.16x). In landscape `view_covers` and the touch layer are moved and resized to the body (0, 50,
  320 x 400; the drag stride stays `CF_VIEW_H`), the caption labels are hidden
  (visibility only: they stay insensitive), and the frame carries the captions, drawn after the covers: the page's font comes from the
  canvas (`widget_prepare_text_style(label)` fills `canvas+0x34` font, `canvas+0xc` size, as `canvas_draw_text`
  `0x645348` reads them), `font_get_glyph` `0x6508b0` gives each glyph's 8-bit alpha (`glyph_t`: x, y, w, h, advance,
  format 0 = alpha, data at 0xc) which is blended in turned at `x + g.x, y + g.y + ascent` (`font_get_vmetrics`
  `0x650918`, a hidden-pointer struct return, ascent first), advance + 1 px per glyph (4 for a missing glyph), centred
  in 368 px and cut with an ellipsis. Touch: `where()` turns the
  pointer back (`widget_to_local` on the touch layer, x = y_local, y = 319 - x_local), so drags and flings along the long
  side move the shelf as in portrait, a tap on the centre cover (`|x - 200| < 84`) opens the album by
  `open_album` (stock sequence, cover thread released), a side tap brings that cover in. Persistence:
  `/mnt/data/m1plus-landscape` (`1` landscape, anything else or missing portrait; written atomically by the switch
  (`coverflow_landscape_toggle`), read when the covers screen is first built (`use_land`); shared by the main and artist pages). Without a depth frame (flat fallback) there is
  no landscape, whatever the setting says. A commit redraws the frame (the captions are in it).
- **Captions.** `label_album` / `label_artist` are `hscroll_label`s configured as Now Playing's info
  lines (`loop`, `yoyo`, `lull` 3000 ms, centred, `ellipses`, 22 px white / 18 px `#AAAAAA`, in 16 px
  margins): a long title scrolls back and forth with a pause at each end, a short one is centred
  (`hscroll_label` paint `0x609cbc` -> `hscroll_label_start`; setting text resets the scroll `0x60a49c`).
  They are insensitive and never hidden: they lie over the frame's black rows, so a tap on the album
  name reaches the touch layer and opens the album. There is no hint line.
- **Songs button.** The artist page's navbar is one glass capsule, **Songs | Now Playing** (glass 216 .. 311, the Artists page's switch + Now Playing), the same for one album or many (there is no
  All albums button; the All albums card on the shelf stays). `btn_songs` (Lucide `list`, `pod_nav_songs`, a left cap) is in the asset at x `NAV_VIEW_X` 214, w 46, hidden and insensitive, and
  opens **our Songs page on all the artist's songs** (`songs_open_artist`, docs/modules/songs.md "The other lists"). **The covers and the list are two views of the artist, a toggle**: the list stays its own window over the covers (no widget of ours can hold that painted page, and there is no open or close animation on these pages, so there is no slide to suppress); on the list the capsule's left cap (x 168, the Albums page's `pod_nav_coverflow` glyph; Search is not shown there) closes the list and shows the covers again, and Back from either view leaves the artist (the list's Back closes itself and this page too: `coverflow_artist_page()`, `patch/songs.c` `sg_on_back`), to the Artists list or to Now Playing when it came from Look up artist. The glyph is the list button here (x 214) and the Cover Flow one there (x 168): the capsule differs per page. One list window at a time, so repeated toggling never stacks pages. `artist_nav` (from `to_covers`) shows it for every
  artist whose stock list had the All songs row (`has_songs()`: `cf.albums` keeps the full stock copy also when the card is dropped) and then sets `btn_backtoplayer`'s icons to the right cap
  (`ah_nav_play`, `_down`; the asset keeps the disc `ah_nav_np`, which the main Cover Flow and a composer's page keep: `songs_open_artist` runs the artist queries, a composer's songs would be
  `0xf005` / `0xff02` -> `0xff14`, not done). Not shown while preparing, nor for "No albums". On an artist page (`cf.scoped`) the title ends at 214 (`coverflow_artist` and `artist_nav`); the main
  page keeps its full width. `on_songs` is guarded by the covers screen and a non-empty shelf; if the page does not open it does what the card does (`cc_open_album` on the All songs row).
- **Start index.** The stock `slide_menu` starts on item 1, not 0; the page always sets the start
  album (`cfpos.value`, or `slide_menu_set_value` in the flat fallback), so an artist's page opens on its first album, a
  one-album shelf has its captions on open, and the main page keeps its last-album memory
  (`/mnt/mmc/.m1plus/covers/album`, including album 0).
- **The album.** Tapping the centre cover opens the stock `albuminfo_page` (section 8), as a stock
  Albums row does (`cc_open_album`, `patch/covercache.c`, the same call the Albums grid makes): `loadAlbumList(0xf003, 0)` puts the stock album list back into `*pdeq_showlist` (the
  page's own copy was made from the same query, so the row is the same), `albumcoverinfo_init` rebuilds
  the cover-task list from it, `batchadd_albumcover_task(0, 0)` releases the cover thread (see section 8, The cover), and `navigator_to_with_context("albuminfo_page", 0xf003 | row << 16)`
  opens the page. The queries repeat on every tap (the page may have been left through Now Playing, and
  anything may have reused the list or the browsing record). Back from the album page returns to the
  covers; the page keeps no track list, header or play code of its own.
- **Cache.** (The cache has one size, 168; the Pod's cover pane needs 264 and gets it without a second tier of files: from demo's own full-resolution file for the playing track and, for its random rotation, from one transient extraction into `/tmp/m1plus-pane.jpg` by this builder's worker (`cc_build_add_file`: no cache file, no marker), docs/modules/ipod.md "The cover pane".) The page keeps its own `/mnt/mmc/.m1plus/covers/<key>-168.jpg` thumbnails (the size is in the
  name; key = FNV-1a of artist then album, never 0; the key, path, decode and reduce helpers are in
  `patch/covercache.c`, which the Albums grid reads the same files through). The stock cache `/mnt/mmc/.downpic` is keyed by an
  MD5 the payload cannot reproduce and holds 90 px images, so Cover Flow only reads through the stock
  extractors. First open builds the thumbnails on a "Preparing covers... n/m" screen with Cancel (a
  cancelled build resumes). **The builder is shared** (`cc_build_*` in `patch/covercache.h`, `covercache.c`; it used to live in
  this file, behaviour unchanged): `cc_build_open(capacity, mode)` takes the app's one job set (refused while another page
  holds it), `cc_build_add(track, key)` queues an album (in `CC_MISSING` mode it skips an album whose cache file, picture or marker,
  exists), `cc_build_start()` makes the cache directory, checks 16 MB free (`statfs`) and starts the one pthread (`cc_worker` runs
  `build_art`), `cc_build_done()` / `cc_build_total()` are the polled counters, `cc_build_stop()` cancels, joins (bounded by
  one album) and frees. The thread touches only its jobs (strings copied on the UI thread), three `volatile` counters, files under
  `.m1plus/covers` and the two stock art calls under `parse_cover_mutex` (`0xa04588`, the lock every stock caller holds;
  `parseplaycover_thd` takes the same one); never a widget, a deque or the image manager. `build_art` checks the cancel flag again
  after taking that mutex (a Back that waited behind a stock parse skips the extraction). `cc_build_near_step` is the resumable
  nearest-first walk the Albums page uses to scan in 64-album steps (`docs/modules/albums.md`); Cover Flow's own `start_build`
  stays one synchronous pass (it runs before the Preparing screen is shown, whose state machine has no scan state, and the
  screen is the expected wait there; making it incremental would add a screen state for no change in what the user sees). Each file is written to `.tmp` and
  renamed; both extractors failing leaves an empty marker (not retried; none is written over a file that exists); a vanished
  track leaves none, and neither does a thumbnail that was extracted but could not be published (a failed rename: the next open
  retries). This page owns its set only while `cf.owns` (`build_end`). If the progress timer cannot be created (at the start or
  when re-armed) the worker is cancelled and joined and the cached covers show. No build below 16 MB free, without a
  card or if `pthread_create` fails. A 250 ms timer polls the counters; Cancel, Back and closing stop it (`pthread_join`);
  `EVT_DESTROY` removes the timer, joins, frees everything. Nothing is written outside the card.
- **Rebuild Covers** (`coverflow_rebuild`, Settings > Library > Rebuild Covers after its confirm dialog, `docs/modules/settings.md`): the
  library's Cover Flow opened with `cf.rebuild`, so `start_build` opens the set in `CC_REBUILD` mode and queues EVERY album with a
  track path. The Preparing screen, counters, Cancel and Back are the same. The worker extracts each album again to `.tmp` and
  `rename`s it over the cache file, so an old picture is replaced atomically and a "no art" marker is replaced by the picture an
  album gained; an album that now yields no art keeps what it has (the old picture, or its marker: nothing is written or removed).
  Cancel, Back or closing mid-way leaves a complete cache (files already replaced are new, the rest are the old ones). When it is
  done the covers show as usual. Refused like any build: no card, under 16 MB free, no thread, another page holding the worker
  (the covers then show with what is cached). An empty library shows "Update Local Music first".
- **One worker at a time**, app-wide: the Albums page builds missing covers in the background (`docs/modules/albums.md`) with the
  same set; its Cover Flow button stops its own build before opening this page, and a page that finds the set taken starts nothing.
- **Not ported from q2-pod:** Sort and Refresh cards, the rated scope, A-Z jump, the album split by
  album-artist/folder, the audiobook filter, the ffmpeg WebP fallback, wheel/ringnav. To clear the
  cache delete `/mnt/mmc/.m1plus/covers` from a computer.
