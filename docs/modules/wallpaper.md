# Wallpaper

Split out of docs/ui.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

### Wallpaper (`tools/mod_wallpaper.py`, `tools/wallpaper_prepare.py`)

With no custom wallpaper `get_screensaver_image` (`0x4d7524`) and `config_init` keep the resource name
`screensaver_default` as `SCREENSAVERPATH`; a chosen picture is `file://` plus its path. Only the
resource changes: `images/xx/screensaver_default.png` (320x480; `xx` is the only set that has it,
theme1 uses it; `screensaver_default1.png`, 640x480, is unreferenced and stays) becomes Van Gogh's *The
Starry Night* (public domain; Google Art Project scan from Wikimedia Commons, SHA-256 `dbca2f16...`,
`wallpaper_prepare.py --fetch DIR` verifies before anything decodes it; attribution in `NOTICE`): a 2:3
crop (full height, 1013 px from x 250: the cypress and the large swirl), Lanczos to 320x480, brightness
x 0.8 so the card, white clock and `#DDDDDD` artist keep contrast, an 8-bit palette PNG (256 colours,
no dithering), 134,313 bytes, SHA-256 `c824ad7a...`. demo's loader is stb_image, which expands palette
PNGs. The step pins the stock file's SHA-256 (`92e7162b...`) and the asset's.
