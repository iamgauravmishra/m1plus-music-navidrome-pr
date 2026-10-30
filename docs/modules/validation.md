# Offline validation

Split out of docs/architecture.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 11. Offline validation

- **Unicorn harness** (`test/pod/harness.py`): loads the real patched `demo` LOAD segments, mocks the
  stock functions and libc and executes the actual compiled payload. `test/patch.py` runs the modules:
  `menu` (entry, non-entry ids, kill switch, `window_open` failure, empty/null icons, row actions,
  hit tests on every menu row through the `list_view`/`scroll_view`; the customisable menu: the default order, saved lists, every invalid or oversized list
  falling back to the defaults (also against the Python model `pod_pages.parse_menu`), the arranged rows hit-tested, Extras with the hidden items, Settings always shown,
  the Settings switches writing their files, the Main Menu page's switches, arrows, failed saves and persistence), `pulldown` (the menu lists under demo's own
  `widget_layout`, `list_view` layouter, scroll_view, paint hook, default painter, `widget_restack` and pointer path on a tree of real widget structs: a relayout after the
  arrangement, the lock screen's first frame, the pull-down with the dialog's abort / snapshot layout / foreground arrangement, the paint hook against rows out of order
  and a short canvas, the Main Menu page's arrows, each run as the V2.1mY arrangement and as the current one), `albums` (the grid: layout against the asset, the menu row and the persisted view, the first frame and paced decoding, tiles of the
  box-filtered cover, scroll offset / content size / clamping on demo's own list_view layouter and scroll_view (1, 8 and 4000 albums, both modes), drag, fling, tap and catch-a-coasting-list through demo's pointer code, the loader deferred while the scroll_view moves, taps on every cell kind and gap incl. the last partial row, title ellipsis, missing
  and empty cache files, 4,000 albums with the bitmaps bounded and recycled, destroy, the toggle both ways with its saved file and the decorated
  stock navbar, hit tests with demo's `widget_find_target`), `coverflow` (open with a complete
  cache, the tap that opens the stock album page with its context, Back, side taps, drag/flick/wrap/abort, close, first-run build, worker
  lock order and markers, no space, refused thread, empty library, broken asset, flat fallback,
  re-query, the depth frame compared byte for byte with the host renderer, hit tests with demo's own
  `widget_find_target`, the caption layout), `assets` (dark/light contrast of the page assets, the
  wallpaper, the icon set and battery art), `artists` (an artist's tap and the All albums card open albuminfo_page with class `0xff01`), `rows` (pins,
  then the real stock row constructors run with their widget calls mocked, and the installed layouter),
  `albuminfo` (the header hook on the real stock header builder: stock first, the restyled geometry,
  texts and styles, the year line cases, the kill switch and every mismatch or failed create leaving stock,
  the Shuffle sequence, hit tests on the buttons with demo's `widget_find_target`, the page theme, the
  cover size word, Cover Flow's first album and last-album memory), `nowplaying` (section 8a: the hook, the timer's life, the tint, the remaining time, the corners, the marker words, the built page), `scroll` (section 8c: the stock scroll_view / list_item pointer code with and without the slot filled), `shuffle`, `dailymix` (the Daily Mix card: its design numbers, the art generator against the model pixel for pixel, the whole mix job on a library under Unicorn with the stock library, playlist table, clock and canvas mocked, the files read strictly, the text lines in 13 languages, the touch, the section in the list, every failure; `docs/modules/dailymix.md`), `i18n` (section 8b: the tables, the keys, our texts in all 16 languages through a mocked `locale_info_tr`, widths and glyphs), `home` (every
  boot branch, the call set, the launcher, window-stack cases). Each prints its count and time.
- `test/coverflow.py` builds `patch/coverflow.c` and `patch/covercache.c` for the host (`-DCF_HOST`) and checks geometry,
  compositing, brightness ladder, reflection, cache key, the texture sampler and the grid's box filter (flat colour, chequer, 2:1 block means, stride, alpha); `test/demo_diff.py`
  checks the built `demo` differs from stock only in `.pdr`, `PH[10]`, the four hooks, the scroll_view vtable slot, the 59 rows.json
  words, the four cover-size words, the five A-B marker words and appended bytes; `test/awtk_fill.py` runs demo's own AWTK fill
  and image code (translucency, rounded fill, scale_auto nearest neighbour).
- `fwtool verify` / `diff` on every package; a clean rebuild is byte-identical.
