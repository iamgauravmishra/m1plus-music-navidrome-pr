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
Fallback: `tools/build.py --restore`.
