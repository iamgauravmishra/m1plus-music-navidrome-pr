# Home cover build

Sources: `patch/homecover.c`, `tools/pod_ui.py` (`cover_progress`), `HC_*` in `patch/offsets.inc`, `Preparing covers` in
`tools/pod_i18n.py`; test `test/pod/homecover.py`. The shared builder is described in [Cover Flow](coverflow.md) (`cc_build_*`),
its Albums-page use in [Albums](albums.md) "Background cache build".

The Home page ([menu](menu.md)) builds the album covers that have no cache file in the background, with the same shared worker as
the Albums page, and shows a plain progress line at the top of the page while it runs: `Preparing covers 120/840`.

## The line

- Placement: a window child of the menu asset, `pod_cover_prog`, a label at (`HC_X` 10, `HC_Y` 8), `HC_W` 300 x `HC_H` 20, text 15 px
  (`HC_PX`), `#AAAAAA` (the grey of the Recently Played subtitles and the Settings values), left, middle. No background, pill or icon.
  The asset has it on the Normal menu too, hidden and insensitive; only Home ever shows it.
- Showing it makes room instead of overlapping: the stock `list_view` (`pod_listview`) and its `pod_scrollview` / `scroll_bar_m` move
  down to `HOME_PAD + HC_H` (28) and shrink by `HC_H` (412 px), then `menu_arrange` clamps the scroll offset; hiding it puts them back
  to 10 / 430. So the first row is never covered, and the line ends exactly where the list starts.
- Hidden = `visible=false` + `sensitive=false` together. Shown only when the worker runs with at least one job: a library whose
  albums all have a picture or the empty "no art" marker never shows it, and it is hidden again when the done counter reaches the total,
  on background and on destroy. No first-run flag.
- Text: `TR("Preparing covers")` (a key of our own, 13 languages) + `" done/total"`, the count formatted in code and rewritten at each poll that saw
  the counter move (`widget_set_text_utf8`, rebuilt each time as the Cover Flow progress is). `test/pod/i18n.py` checks the widest
  `... 4000/4000` fits the label in every language.

## The build

Called from `home_menu_opened` beside `recent_start` / `dailymix_start` (`homecover_start`, the Home instance only; no kill switch, no
widget: nothing). **No new hook, nothing at boot:** `homecover_start` looks up two widgets, registers `EVT_DESTROY`, `EVT_WINDOW_TO_BG`,
`EVT_WINDOW_TO_FG` on the window and arms one one-shot `HC_START_MS` (= `RC_RESOLVE_MS`, 5 s) out; a refused registration or timer leaves Home as it was.

- `hc_on_start` (page-scoped timer): if the worker is held (`cc_build_busy`: Cover Flow, the Albums page, anything) it does nothing and
  the next foreground offers again. Otherwise it copies the library's albums (`cc_albums`, one stock query like the Albums page's open; `recent_rekey` first corrects Recently Played's cover keys from it, `docs/modules/recent.md`, and names the shelf's rows: `hc_order` moves them to the front of the scan, most recent first, so the shelf's placeholders are the first covers made),
  opens a `CC_MISSING` set (capacity min(albums, `CC_MAX_JOBS`)) and scans in steps of `HC_BATCH` 64 albums with `cc_build_near_step(centre 0)`
  (the displayed album order, no "in view" centre), re-arming itself `HC_SCAN_MS` 20 ms later so input is served between steps. After the
  last step the album copy is freed (the jobs hold their own path copies) and `cc_build_start` runs: nothing missing, no card, under 16 MB
  free or no thread frees the set and nothing is shown. Otherwise the line shows `0/total` and the poll starts.
- `hc_on_poll` (`HC_POLL_MS` 500 ms): reads `cc_build_done`; when it moved, rewrites the line and calls `recent_refresh`, which lets the
  Recently Played tiles that showed the placeholder because their file was missing try again (`rc_tiles`: `art == 2` and the file exists now,
  then the shelf's own one-per-tick loader decodes it; paint never touches files). The Daily Mix card's art is its own render and the
  Made for You tiles pick the new covers up on the next foreground. At done == total the set is stopped (joined, freed), the line hidden.
- `EVT_WINDOW_TO_BG`: `hc_end` removes the timer, frees a half-scanned copy, `cc_build_stop`s a set Home owns (only then: a set held by
  anyone else is never touched) and hides the line, so the worker never runs beside Cover Flow's or the Albums page's own build.
  `EVT_WINDOW_TO_FG` arms the one-shot again (5 s, only if nothing runs or is pending). A page that goes to the background and comes back
  rescans (about one `access` per album, 64 per 20 ms step; a built library finds nothing and shows nothing). `EVT_DESTROY` ends it likewise
  and clears the state (an earlier window's destroy is ignored).

## Rebuild Covers

Settings > Library > Rebuild Covers ([settings](settings.md)) no longer opens Cover Flow. Its Yes writes the request file
`/mnt/data/m1plus-covers-rebuild` (`REBUILD_FILE`) and shows a toast. When `hc_on_start` begins a scan it checks the file (`access`):

- present: the set is opened in `CC_REBUILD` mode, so `cc_build_near_step` queues EVERY album with a track path (existing pictures and
  markers too; the shelf's albums first, as always), and the line reads `Rebuilding covers n/m` (key `Rebuilding covers`, 13 languages);
- absent: the normal missing-only build above.

The request is removed only when the rebuild set completes (`done == total` in the poll), or at once when no album has a track path (nothing
to extract). Interruption (Home to the background, destroy, a held worker, no card or space, no thread) leaves the file, and the next
foreground (5 s later) starts the rebuild again **from the beginning**: simple, and the worker replaces each file atomically, so a
restart only repeats work (resuming would need a per-album marker). Files already replaced stay new. The worker is the one at a time, so a
rebuild never runs beside Cover Flow's or Albums' own build.

Settings > Developer > Cover Cache shows the cache's counts and this build's status, and its Clear Cover Cache row is the opposite request: it deletes the cache (and this request file) in steps, see [settings](settings.md) "Clear Cover Cache"; the next scan then queues every album as missing.

## Notes

- The scan's `cc_albums` runs `loadLocalClassList` like the other pages' opens do; it happens 5 s after Home is in front, never in the
  boot window.
- Tests (`test/pod/homecover.py`, Unicorn on the real payload with the harness's cache-file and worker mocks): hidden with nothing missing
  (also an empty library), `0/2` then `1/2` then hidden with the list restored, scan bounded at 64 albums a step, stop on background and
  destroy (also mid-scan), foreground re-offers once, a held worker / full card / refused thread / refused timer / asset without the line.
