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

Grey values show the current setting.

| Page | Options |
|---|---|
| Wi-Fi / Bluetooth | Stock connection pages; values show On/Off |
| Home Screen | Recent Albums, Daily Mix, Main Menu and Extras; Battery Percentage (off by default, reads the fuel gauge); Regenerate Daily Mix (while enabled, takes effect next Home visit) |
| Library | Update Library, Album Order (Artist/Album, for Albums and Cover Flow), Rebuild Covers and landscape Cover Flow |
| Now Playing | Cassette Theme: Normal, Chrome or Metal; applies next time Cassette Mode opens |
| Playback | Stock Play Mode and EQ pages; All Playback Settings includes Gapless |
| System | Stock Display and All System Settings (including Language); Keyboards; About shows build/firmware, model, serial, Wi-Fi MAC/IP and card capacity/free space |
| Keyboards | English always enabled; Chinese (Pinyin) adds a language key and candidates above the keys. Swipe candidates sideways; space selects the first |
| Developer → Startup | Boot to M1+ Music; Open Shanling Home |
| Developer → Tools | Screenshot, Cover Cache and stock System Update |

**Rebuild Covers** asks for confirmation, then Home rebuilds in the background with
"Rebuilding covers n/m" progress. Leaving Home restarts it on the next visit. **Cover Cache**
shows cached/missing/stale counts and current work; **Clear Cover Cache** asks before deleting,
then Home regenerates covers.

**Screenshot** asks first: leave the page within five seconds to capture another screen.
Cancel during the countdown if needed; see [capture details](modules/screenshot.md).

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

For a missing feature, enable it through **Settings → Home Screen → Main Menu**, or find it under Extras.
The [UI reference](ui.md) includes a preview; [module docs](architecture.md) describe implementation
and hardware-validation limits.
