# Architecture

The build copies the official V2.1 rootfs, compiles a fixed-address MIPS payload into
`/release/bin/demo`, applies pinned code/asset edits and repacks the kernel and rootfs as
`update.bin`. Input mismatches and an oversized rootfs fail the build.

Start with the relevant module below. Read [payload](modules/payload.md) and
[addresses](modules/addresses.md) before searching the binary. See [workflow](workflow.md)
for commands, [UI](ui.md) for layout/assets, and [history](history.md) for recorded device findings.

## Core

| Reference | Contents |
|---|---|
| [Pipeline](modules/pipeline.md) | Build stages, ordering and package validation |
| [Payload](modules/payload.md) | Segment layout, trampolines, stock calls and hooks |
| [Addresses](modules/addresses.md) | Stock symbols, offsets and record layouts |
| [Home and boot guard](modules/home-guard.md) | Startup marker, grid entry, window stack and fallback |
| [Settings](modules/settings.md) | Settings pages and persisted choices |
| [Safety](modules/safety.md) | Allowed entry points and required invariants |
| [Validation](modules/validation.md) | Test boundaries and what they prove |
| [q2-pod comparison](modules/q2pod.md) | Corresponding mechanisms and platform differences |

## Features

| Reference | Contents |
|---|---|
| [Cover Flow](modules/coverflow.md) | Renderer, cache, gestures and landscape mode |
| [Albums](modules/albums.md) | Shared grid/list page and cover loading |
| [Artists](modules/artists.md) | Artists, Album Artists, Genres and Composers |
| [Songs](modules/songs.md) | A–Z sections, rail, sort and selection |
| [Search](modules/search.md) | Library search: the Apple Music screen, chips, live results, embedded keyboard, folded multi-word matching |
| [Playlists](modules/playlists.md) | Cover mosaics, list mode and stock playlist operations |
| [Add to Playlist](modules/picker.md) | Our own picker (the Playlists page in pick mode) in place of stock's; the stock batch add |
| [Folders](modules/folders.md) | Our own Folders page over the stock folder state (one window, every level) |
| [Album page](modules/album-page.md) | Our own album page (tint, status bar, tone cache, playback actions); the stock page stays plain stock as its fallback |
| [Queue page](modules/queue.md) | Our own queue page (Now Playing's queue button; the stock drawer is the fallback): playing track, icon-only Shuffle / Repeat buttons, Up Next rows |
| [Rows](modules/rows.md) | Stock row edits, layout and text sizing |
| [Shuffle](modules/shuffle.md) | Song, album and folder queues |
| [Now Playing](modules/nowplaying.md) | Cover tint, remaining time and rounded artwork |
| [Lyrics page](modules/lyrics.md) | Our own lyrics lines over the stock rows: anchor, opacity falloff, eased scroll |
| [More sheet](modules/playmore.md) | Playback options, Cassette Mode, Vinyl Mode and Find Cover & Lyrics entries |
| [Find Cover & Lyrics](modules/onlineart.md) | Online album covers (iTunes, Deezer) and lyrics (LRCLIB) for the playing track: page, worker, storage |
| [Mini player](modules/minibar.md) | Home overlay, controls, blur and timer |
| [Recently Played](modules/recent.md) | History file, covers and shelf layout |
| [Daily Mix](modules/dailymix.md) | Selection job, stored mix, card and page |
| [Home cover build](modules/homecover.md) | Background cover cache build and its progress line |
| [Podcasts](modules/podcasts.md) | Local episodes, feeds, covers, resume and speed |
| [Virtual iPod](modules/ipod.md) | Touch wheel, navigation and playback |
| [iPod Cover Flow](modules/ipod-coverflow.md) | Embedded carousel and album navigation |
| [Cassette Mode](modules/tape.md) | Landscape rendering, themes and timer |
| [Vinyl Mode](modules/vinyl.md) | Portrait turntable page: turning cover label, tonearm, keys |
| [Menu](modules/menu.md) | Home/normal instances, Extras and customization |
| [Languages](modules/i18n.md) | Translation tables, keys and width checks |
| [Screenshot](modules/screenshot.md) | Countdown, framebuffer capture and import |
| [Keyboard](modules/keyboard.md) | Own QWERTY keyboard page, API, tap log; gap rule; Chinese (Pinyin) layer and candidate strip |
| [List gestures](modules/gestures.md) | Drag cancellation and stopping coasting lists |

Older source comments cite numbered sections from the former architecture document:
1 pipeline, 2 payload, 3 addresses, 4 Cover Flow, 5 Artists, 5a Albums, 6 rows, 7 shuffle,
8 album page, 8a Now Playing, 8b languages, 8c screenshot, 8d gestures, 9 Home/settings,
10 safety, 11 validation, 12 q2-pod comparison.
