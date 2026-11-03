# Pull-down

## Pull-down (`tools/mod_pulldown.py`, `mod_icons.py`)

Runs after the font step on `ui/dialog/dropdown_dialog.bin` (default and theme1; no style file):
its status bar (`view_sysbar`) is laid out from the same table as the real bar (`tools/statusbar.py`, section 4: volume number
16 px middle, clock 18 px at x 104, left group from x 10, right group 4 px, black), so the two are identical in 12 h and 24 h mode
and in both themes; the tile captions (`label_wifi`, `label_bt`, `label_lock`,
`label_gain`, `label_usbmode`, `label_outputway`, `label_playset`, `label_sysset`; word-wrapped)
18 -> 16 px normal, 16 -> 14 disabled/focused. The caption boxes are 71 x 40 instead of 57 x 40 (same centre,
x - 7; the tiles are 74 px apart), because `Bluetooth` is 60 px at 16 and AWTK broke it as "Bluetoot/h" and
"Playbac/k Setting". The tool now also refuses a Latin word wider than the box in English or Chinese. Nothing else
moves; alignment stays centred. Measured with
the text model: `100` at 16 px fits the 30 px label; `12:59 PM` is 66-72 px of 90; every English and
Chinese caption fits its box without a mid-word break (the tool refuses otherwise). 22 captions in other languages (long Russian, Ukrainian, Polish, Italian, Spanish, German words in
a 57 px tile) still overflow, as clipped in stock.
**Tile art:** every tile image is one 50x50 ring style, 2 px ring, 24 px glyph: off `#777777` ring +
glyph (`drop_wifi`, `bt`, `keylock`, `eq`, `lowgain`, `po`, `playset`, `sysset`), on a filled white disc +
`#141414` glyph (the `*open` images, `highgain`, `lo`, `usbaudio`, `usbdac`, `usbstorage`, the pressed
`playsetdown`/`syssetdown`), disabled `#444444` (`lowgaindisable`, `highgaindisable`). Gain uses custom
2-/5-bar glyphs, Output the text "PO"/"LO" in Inter Medium 17 px. White disc was chosen over a white ring
(only a brightness step from the grey ring; the disc is what stock does with its orange fill). With an accent the ON tiles' disc is the accent and the glyph stays `#141414` ([accent](accent.md), `ACCENT_DISC`).
