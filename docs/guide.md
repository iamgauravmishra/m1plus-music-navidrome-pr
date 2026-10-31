# M1+ Music user guide

For installation, updates and restore, see [Install](install.md).

## Home and menus

M1+ Music opens at startup and from its icon on Shanling Home. The default menu shows Cover Flow,
Albums, Artists, Songs, Playlists and Extras. Daily Mix and Recently Played appear below it;
the mini player appears while a track is queued.

Open **Extras → Customize** using the navbar button. **Main Menu** shows, hides and reorders
items; **Extras** turns off items you do not want listed there. Customize remains reachable.
**Home Screen → Shanling Home** returns to the stock grid; **Boot to M1+ Music** changes startup.

## Browse and play

| Page | Controls |
|---|---|
| Cover Flow | Drag to browse, tap a side cover to centre it, tap the centre cover to open its album |
| Albums | Switch grid/list mode with the navbar button; the choice is remembered |
| Artists | Switch Artist/Album Artist in the navbar, then open an artist's albums |
| Songs | Jump with the A–Z rail; use Search, Sort or Select from the navbar |
| Album | Play all, shuffle the album, or tap a track |
| Playlists | Open a playlist or use its menu to create, import, export or delete |
| Shuffle | Shuffle songs, albums or folders from Extras |

The mini player's cover opens Now Playing; its buttons pause/resume or skip. Now Playing's
More sheet provides playback options, Look up album and Cassette Mode. A drag on a list scrolls;
a tap opens or plays a row.

Copy music to the card, then use **Extras → Update Library** to scan it.

## Customize

- **Home Screen:** startup, Recent Albums, Daily Mix and Regenerate Daily Mix.
- **Cover Flow:** landscape presentation, artist/album order and Rebuild Covers.
- **Cassette Mode:** cycle Normal, Chrome and Metal themes.
- **Keyboards:** English is always on; switch on Chinese (Pinyin) to get a language key and pinyin input on the on-screen keyboard (candidates above the keys, swipe them sideways, space takes the first).
- **Playback / System Settings:** open the stock settings pages.
- **Developer → Screenshot:** confirm a capture, then leave the page within five seconds.

Rebuild Covers asks before regenerating the cache. Screenshots can be cancelled during their
countdown; see [capture details](modules/screenshot.md).

## Extras

**Cassette Mode** is a landscape Now Playing screen. Tap the cassette to pause/resume and the
top-left screw to close. Change its theme under Customize.

**Pod** opens a virtual iPod with a touch click wheel. See its [controls and limits](modules/ipod.md).

**Podcasts** reads local episodes from `Podcasts/<Show>/` on the card. Tap a show, then an
episode to play; tap the unplayed dot to change its played state. The show header cycles playback
speed. Feed subscription and downloading are not implemented; see [formats and limits](modules/podcasts.md).

For a missing feature, show its row through **Customize → Main Menu**, or find it under Extras.
The [UI reference](ui.md) includes a preview; [module docs](architecture.md) describe implementation
and hardware-validation limits.
