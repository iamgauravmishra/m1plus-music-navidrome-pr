# Device checks for the looks

Split out of docs/ui.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 9. Device checks for the looks

Boot splash upright (and after a 180° rotation); no text hole, tofu or jitter in the new font at
16/18/20/21 px; digits and clocks do not jitter; CJK, Cyrillic, Vietnamese, Thai titles; curly quotes
proper; status bar clear of Bluetooth in 12 h mode; settings rows black with hairlines and grey discs,
slides in and out; lists and Search as described; Now Playing as in section 4; lock screen
card translucent without notches, 264 px cover sharp, gauge small, hint small, touch rules; pull-down
tiles rings, captions fit; Home menu without grid flash, title or Back; theme1 returns the stock look.
Albums page (not yet seen on the device): the grid as before (covers sharp and aligned in two columns, album and artist one line each with the ellipsis, scrolling
follows the finger and coasts, a tap opens the album page, Back returns to the same place); the toggle switches to the list and back in place, at the same first
album, without a flash, and the Albums row then opens the last mode (also after a reboot); list rows: 52 px cover, album, artist, hairline, pressed `#333333`
under the finger only, a long title or artist ends in an ellipsis before the right margin; an album without a cached cover shows the disc in both modes.
Mini player bar (`docs/modules/minibar.md`, not yet seen on the device): nothing queued at boot: the menu as before; play something: the bar shows within
a second, the list scrolls behind it (rows show through the glass, the last row scrolls clear above it), the cover is sharp with rounded corners, the pill is a translucent dark glass pill with a light rim, brighter on its top arc, the same for every track (white bar glyphs, a pressed pill a little lighter, the cover 36 px at the pill's left
curve), long titles end in an ellipsis before the buttons and do not scroll; play / pause toggles the sound and the glyph (also when paused from the
headset key or Now Playing); next skips and the title follows within the tick (a second next within a second is ignored, as on the lock screen); a tap on
the card opens Now Playing and Back returns with the bar current; the pull-down over the menu and a dialog do not leave the bar stuck; the menu opened
from the grid icon (Home, Settings > Home Screen) has no bar; Settings > Home Screen > Shanling Home and back leave no bar on the grid.
Backdrop blur (experimental, `docs/modules/minibar.md`): the rows behind the glass are blurred and slightly darker, not sharp, with no rectangular patch at the pill's rounded ends and no seam
or colour cast; scrolling the list under the pill stays smooth (about 0.6 ms of blur a frame is the estimate); pressing play or next, a track change and a pause show no flash of sharp rows;
pressing a row just above the pill shows at most one frame of sharp rows inside the pill. With `/mnt/mmc/m1pod-noblur` on the card the glass is over sharp rows (the pre-blur look). If the panel is
`bgra5551` (it reports a 1 bit alpha) the blur is simply absent: that is the answer to "which lcd".
Recently Played shelf (`docs/modules/recent.md`, not yet seen on the device): play two or three albums (from the Albums page, Cover Flow, the album page), return to the Home menu: the shelf shows at the foot of the list, below the Settings row, under a white "Recently Played" header
(20 px, starting where the covers start, about 20 px below the Settings row, 8 px above the covers), the albums in the order played with the latest first as the Albums page's grid, 2 columns of 144 px covers with rounded corners (one row for one or two albums, two for three or four, three for five or six), the album (white, 18 px) and the artist (grey, 15 px) under each ending in an ellipsis; scrolled to the end the artist line sits just above the mini bar; the covers are made only when the shelf is scrolled into view (or within a row of it), one after the other, with no hitch while scrolling the list towards it; the rows above never jump when the shelf appears or goes; an album without a cached cover shows the disc until the Albums page has built it (then a to-foreground, i.e. after leaving and returning, shows it). The list scrolls with the shelf (a drag that starts on a
cover or a caption scrolls it; a tap opens the album page, Back returns; a swipe never opens an album; a touch that stops a coasting list opens nothing); the last row still scrolls clear above the mini bar. Keep playing a new album with the menu in front: its cover appears first within a second. Play a compilation (or an album whose tracks have different artist tags) through several tracks: ONE shelf entry, not copies; its cover is the album's (the disc only until the album list has been read: after the first Now Playing tick of a new album, or a leave-and-return of the menu 5 s or more after boot; note any hitch when that list loads on a large library). Delete a cover cache file or the album: the disc, a tap still behaves as described.
Settings > Home Screen > Recent Albums off: the shelf is gone and the rows are as before; on: it is back with its covers. An album deleted from the library: its tile shows, a tap does nothing. Reboot: the shelf is still there (`/mnt/data/m1pod-recent`); no shelf on the menu opened from the grid icon; a first boot with no history shows no shelf. Listen for any stutter while scrolling the list with the shelf (each cover is 96 x 96 RGBA, 110 KB in all).
Fallback: `tools/build.py --restore`.
