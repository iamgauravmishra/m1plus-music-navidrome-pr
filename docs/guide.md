# M1+ Music user guide

For installation, updates and restore, see [Install](install.md).

## Home and menus

M1+ Music opens at startup and from its icon on Shanling Home. The default menu shows Cover Flow,
Albums, Artists, Songs, Playlists and Extras. Daily Mix and Recently Played appear below it;
the mini player appears while a track is queued.
Open **Extras → Settings** using the navbar button. **Settings → Home Screen** holds **Main Menu**
(show, hide and reorder items) and **Extras** (turn off items you do not want listed there). Settings
remains reachable. **Developer → Open Shanling Home** returns to the stock grid; **Boot to M1+ Music**
(Developer → Startup) changes startup.

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
More sheet provides playback options, Look up album, Cassette Mode, Vinyl Mode and (on its More page, with Wi-Fi on) Find Cover & Lyrics. A drag on a list scrolls;
a tap opens or plays a row.

Copy music to the card, then use **Extras → Update Library** to scan it.

## Settings

Settings is iOS-style grouped cards; a grey value at the right shows the current state.

- **Wi-Fi, Bluetooth:** open the stock pages (the value shows On or Off).
- **Home Screen, Library, Now Playing, Keyboards:** the pages below.
- **Playback:** **Play Mode** and **EQ** open the stock pages (the value shows the mode and the preset); **All Playback Settings** opens the stock list (Gapless is there).
- **System:** **Display** opens the stock page (Language is on the stock System Settings list), **Keyboards** is below, **About** is our own page (the build and firmware versions; Device: model, serial number, Wi-Fi MAC and IP address; Storage: card capacity and free space), **All System Settings** opens the stock list.
- **Home Screen:** the Recent Albums and Daily Mix switches; then Main Menu and Extras, as above; under Status Bar the Battery Percentage switch (off by default), which shows the battery's exact charge, such as 87%, beside the battery icon (the charge is the fuel gauge's reading, not the voltage steps stock shows); and last Regenerate Daily Mix, which appears while Daily Mix is on and answers a tap with "New mix when Home opens".
- **Library:** Update Library; **Album Order** (Artist or Album, a picker with a check mark, for Albums and Cover Flow); **Rebuild Covers** (next to Update Library); under Cover Flow, landscape presentation.
- **Now Playing:** under Cassette Mode, **Theme** (Normal, Chrome or Metal; a picker, applied the next time Cassette Mode opens).
- **Keyboards:** English is always on; switch on Chinese (Pinyin) to get a language key and pinyin input on the on-screen keyboard (candidates above the keys, swipe them sideways, space takes the first).
- **Developer:** Startup (**Boot to M1+ Music**, **Open Shanling Home**) and Tools (**Screenshot**: confirm a capture, then leave the page within five seconds; **Cover Cache** shows how many covers are cached, missing or stale and what is being built, and **Clear Cover Cache** on it deletes the cached covers after a confirm (Home makes them again); **System Update** opens the stock firmware update page).

Rebuild Covers asks first; Yes shows a toast and the Home screen regenerates every cover in the background ("Rebuilding covers n/m" at its top; it restarts at the next visit if you leave Home meanwhile). Screenshots can be cancelled during their
countdown; see [capture details](modules/screenshot.md).

## Extras

**Cassette Mode** is a landscape Now Playing screen. Tap the cassette to pause/resume and the
top-left screw to close. Change its theme under Settings.

**Vinyl Mode** is a turntable Now Playing screen: the cover turns as the record's label while
playing. Tap the record or the large key to pause/resume, the side keys to skip, the top-left
chevron to close.

**Cover & Lyrics** (Now Playing > ... > More > Cover & Lyrics, needs Wi-Fi) looks up the playing album's covers
(iTunes, then Deezer) and its lyrics (LRCLIB). Tap a cover to use it for the album everywhere; Save Lyrics writes
`<song>.lrc` next to the song (Replace Lyrics when one is there). See [details](modules/onlineart.md).

**Pod** opens a virtual iPod with a touch click wheel. See its [controls and limits](modules/ipod.md).

**Podcasts** reads local episodes from `Podcasts/<Show>/` on the card. Tap a show, then an
episode to play; tap the unplayed dot to change its played state. The show header cycles playback
speed. Feeds, downloads and the search for new shows (Settings > Library > Podcast Search, off by default: a Search button on the Podcasts page, then Subscribe on a show's preview) are described in [formats and limits](modules/podcasts.md).

**Search** (hidden from the menu by default) opens the library search, the same page as the Songs page's Search button; show it in the menu through **Settings → Home Screen → Main Menu**.

For a missing feature, show its row through **Settings → Main Menu**, or find it under Extras.
The [UI reference](ui.md) includes a preview; [module docs](architecture.md) describe implementation
and hardware-validation limits.
