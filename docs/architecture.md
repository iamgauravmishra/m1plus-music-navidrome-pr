# Architecture: pipeline, payload, hooks, guard

How the release is built and what its code does. The looks (assets) are in `docs/ui.md`,
firmware facts and the space step in `docs/firmware.md`, make/test/flash in `docs/workflow.md`, the
milestones, device results and lessons in `docs/history.md`.

This file is an index. The text lives in one file per module under `docs/modules/`; read the
one you touch (and `payload.md` + `addresses.md` before searching the binary). Source comments and
older notes cite the old section numbers (`docs/architecture.md section 5a`); the "Old §" column maps
them. The asset (look) half of a module is in the same file where it has one (Now Playing, Albums, the
album page, Library rows, Localisation); the rest of the looks is indexed in `docs/ui.md`.

**Overview.** The build copies the official V2.1 rootfs, runs the asset steps, patches `release/bin/demo`
(a payload of C compiled by LLVM, linked into a new segment, entered through a few pinned hooks) and
repacks `rootfs.squashfs` + the kernel into a TF-card `update.bin`. The only boot-time code is the
guarded `home_page_init` hook (a crash marker falls back to stock after one bad boot) and the tag reader's call site (`get_id3info`, podcast paths only, `docs/modules/payload.md` hook 5); the library scan's folder test (skips dot-folders, not boot-reachable, hook 6) and the two database query functions (songtable selects without podcast paths, hook 7, reachable at boot); everything else
runs from a user tap. Every patched word and stock address is pinned and the build refuses on mismatch.

## Core

| Doc | Old § | What |
|---|---|---|
| [`modules/pipeline.md`](modules/pipeline.md) | 1 | The build pipeline: steps, order, the package, what is pinned |
| [`modules/payload.md`](modules/payload.md) | 2 | The code payload: segment, `$gp` and trampolines, calling stock code and libc, the hooks, the entry (`patch/m1plus.c`) |
| [`modules/addresses.md`](modules/addresses.md) | 3 | Known addresses of stock V2.1 `demo`, the Home icons and their conditions, the library record layout |
| [`modules/home-guard.md`](modules/home-guard.md) | 9 | Home and the boot guard (`patch/home.c`): boot sequence, grid icon, why it is safe, files and the kill switch, the window stack, recovery |
| [`modules/settings.md`](modules/settings.md) | 9 | The launcher: the Customize page and its sub-pages (Home Screen, Cover Flow, Developer), the album order, opening on the playing album |
| [`modules/safety.md`](modules/safety.md) | 10 | Safety rules for the payload |
| [`modules/validation.md`](modules/validation.md) | 11 | Offline validation (Unicorn harness, what the tests prove) |
| [`modules/q2pod.md`](modules/q2pod.md) | 12 | How this maps to q2-pod |

## Features

| Doc | Old § | What |
|---|---|---|
| [`modules/coverflow.md`](modules/coverflow.md) | 4 | Cover Flow (`patch/coverflow.c`; tests `test/pod/coverflow.py`, `test/coverflow.py`) |
| [`modules/artists.md`](modules/artists.md) | 5 | Artists, Genres and Composers as an A-Z list in the Songs page's manner (`patch/artists.c`, `patch/azlist.c`) |
| [`modules/albums.md`](modules/albums.md) | 5a | Albums grid and list (`patch/albums.c`, `patch/covercache.c`) and the Albums page layout |
| [`modules/rows.md`](modules/rows.md) | 6 | Library rows (`patch/rows.c`, `patch/rows.json`) and their assets |
| [`modules/shuffle.md`](modules/shuffle.md) | 7 | Shuffle (`patch/shuffle.c`) |
| [`modules/album-page.md`](modules/album-page.md) | 8 | The album view (`patch/albuminfo.c`) and the album page assets |
| [`modules/nowplaying.md`](modules/nowplaying.md) | 8a | Now Playing (`patch/nowplaying.c`, `tools/mod_nowplaying.py`): code and look |
| [`modules/minibar.md`](modules/minibar.md) | (new) | The mini player bar on the menu's Home instance (`patch/minibar.c`, no hook): layout, timer, stock player calls |
| [`modules/recent.md`](modules/recent.md) | (new) | The Recently Played shelf on the menu's Home instance (`patch/recent.c`, no hook): the list file, recording, covers, taps, the rows below it |
| [`modules/playlists.md`](modules/playlists.md) | (new) | The Playlists grid of album-cover mosaics and its "..." menu (`patch/playlists.c`, `patch/grid.c`, no hook): the stock database calls, the loader, the stock create / import / export / songs code it reuses |
| [`modules/songs.md`](modules/songs.md) | (new) | The Songs page: one list with sections, the A-Z rail, the sort card, Search and a select mode with Add / Delete (`patch/songs.c`, `patch/azlist.c` shared with the Artists page, `patch/grid.c`, no hook): the data (the 8 byte index, the Initial byte, `sort_flag`), the stock multi-select calls it reuses (`batch_delete_file`, the playlist picker), the evidence |
| [`modules/ipod-coverflow.md`](modules/ipod-coverflow.md) | (new) | The iPod page's Cover Flow screen (`patch/ipod_cf.c`, the shared renderer, no hook): seven covers on white under the title bar, the slide on the page's one timer, the album's tracks, the device checklist |
| [`modules/tape.md`](modules/tape.md) | (new) | The Tape page, a landscape fullscreen cassette Now Playing page opened from the More sheet (`patch/tape.c`, `tools/tape_art.py`, no hook): the quarter-turn frame and the glyph-alpha rotated text, the packs and hubs, touch, the one timer, pins, device checklist |
| [`modules/ipod.md`](modules/ipod.md) | (new) | The virtual iPod Classic: a fullscreen page with the iPod screen and a touch click wheel (`patch/ipod.c`, no hook): layout, the wheel's angle math and step, the levels over the stock library queries, play, the click-sound decision, addresses, device checklist |
| [`modules/dailymix.md`](modules/dailymix.md) | (new) | The Daily Mix hero card above the shelf (`patch/dailymix.c`): card layout, art generator, the stock playlist rewrite, the once-a-day job in timer slices, files, tests |
| [`modules/podcasts.md`](modules/podcasts.md) | (new) | Podcasts from the card (`patch/pcmodel.c`, `patch/podcasts.c`; one hook, in the tag reader): the show / episode model and its metadata files, the resume ring, played marks, speed per show, the page, what stays out of Daily Mix, Recently Played and Shuffle, device checks, the subscribe and download design |
| [`modules/i18n.md`](modules/i18n.md) | 8b | Localisation (`patch/i18n.h`, `tools/pod_i18n.py`) |
| [`modules/screenshot.md`](modules/screenshot.md) | 8c | Screenshot (`patch/shot.c`, `tools/pull_shots.py`) |
| [`modules/gestures.md`](modules/gestures.md) | 8d | List gestures (`patch/scroll.c`) |
| [`modules/menu.md`](modules/menu.md) | (ui 8) | The M1+ Music menu and its pages (`tools/pod_ui.py`) |
