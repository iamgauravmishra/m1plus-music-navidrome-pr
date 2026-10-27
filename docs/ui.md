# UI: the looks of the release

Everything here is asset-only (no code) except where it says demo words change or the payload paints (Now Playing); the payload side is
in `docs/architecture.md`. The steps run in the order of `tools/build.py` (battery, font, [payload],
theme, lists, nowplaying, boot, rows, pulldown, lockscreen, wallpaper, icons, polish) on one tree; each
step pins the stock bytes it replaces by SHA-256, keeps every widget name and refuses to apply twice.
Style is q2-pod's Minimal / iPod (MIT, `NOTICE`) fitted to the 320x480 portrait touchscreen.

![the release](release-preview.png)
`docs/release-preview.png` is the one tracked preview (`tools/preview.py WORKDIR [OUT.png]`, default
`out/preview/release-preview.png`, gitignored; the tracked sheet is refreshed only at a release, `docs/workflow.md`):
Home pages 1 and 3 (the M1+ Pod icon), the M1+ Pod menu as Home (no top bar), the Settings, Main Menu, Shuffle and
Extras pages, the Artists toggle, the album page, an artist's Cover Flow (and the landscape one), the Albums grid and
list, the pull-down with the toggle and slider art (`controls()`), the lock screen (playing; idle on the charger) and
the battery at 8x. The other previews (`tools/preview_all.py`, `preview_icons.py`, `preview_stock.py`,
`preview_battery.py`, `preview_nowplaying.py` ...) write wherever you point them; use `out/preview/`. All are
approximate PIL mock-ups drawn from the built tree (not AWTK), text rasterised from the tree's own `default.ttf`
the stb_truetype way (`tools/preview_font.py`, `tools/stb_raster.py`), sample data.

This file is an index. The text lives in one file per module under `docs/modules/`. Read
`ui-rules.md` and `text-width.md` before any UI step; then the module you touch. Old section numbers
(`docs/ui.md` section 7 ...) are kept in the "Old §" column. A UI bug starts with a reproducer (an
emulation test or a device screenshot, `docs/workflow.md`), and previews must use the shared AWTK
layout model where one exists (`tools/awtk_text.py`, `tools/awtk_ui.py`).

## Rules and models

| Doc | Old § | What |
|---|---|---|
| [`modules/ui-rules.md`](modules/ui-rules.md) | 1 | Rules every UI step follows |
| [`modules/text-width.md`](modules/text-width.md) | 2 | The text-width model (`tools/awtk_text.py`) |
| [`modules/fonts.md`](modules/fonts.md) | 3 | Font (`tools/mod_font.py`, `tools/font_inter.py`) |
| [`modules/theme.md`](modules/theme.md) | 4 | Minimal theme (`tools/mod_theme.py`, `tools/awtk_style.py`) |

## Looks per module

| Doc | Old § | What |
|---|---|---|
| [`modules/lists.md`](modules/lists.md) | 4 | Library lists (`tools/mod_lists.py`) |
| [`modules/nowplaying.md`](modules/nowplaying.md) | 4 | Now Playing look (`tools/mod_nowplaying.py`); the code half is in the same file |
| [`modules/boot.md`](modules/boot.md) | 5, 8 | Boot logo, quotes, settings slides (`tools/mod_boot.py`), the settings-slide safety audit |
| [`modules/icons.md`](modules/icons.md) | 6 | Lucide icons, icon audit (`tools/mod_icons.py`, `tools/audit_images.py`) |
| [`modules/battery.md`](modules/battery.md) | 6 | One battery (`tools/battery_art.py`, `tools/mod_battery.py`) |
| [`modules/rows.md`](modules/rows.md) | 7 | Library rows (assets); code half in the same file |
| [`modules/album-page.md`](modules/album-page.md) | 7 | The album page and the other stock pages (assets) |
| [`modules/pulldown.md`](modules/pulldown.md) | 7 | Pull-down (`tools/mod_pulldown.py`) |
| [`modules/lockscreen.md`](modules/lockscreen.md) | 7 | Lock screen (`tools/mod_lockscreen.py`) |
| [`modules/wallpaper.md`](modules/wallpaper.md) | 7 | Wallpaper (`tools/mod_wallpaper.py`) |
| [`modules/polish.md`](modules/polish.md) | 7 | About row, polish (`tools/mod_about.py`, `tools/mod_polish.py`) |
| [`modules/menu.md`](modules/menu.md) | 8 | M1+ Pod page layout (`tools/pod_ui.py`) |
| [`modules/albums.md`](modules/albums.md) | 8 | The Albums page (`ui/m1pod_albums.bin`); code half in the same file |
| [`modules/playmore.md`](modules/playmore.md) | new | Now Playing's More menu: a dimmed bottom sheet with two pages (`patch/playmore.c`, `tools/mod_lists.py`) |
| [`modules/i18n.md`](modules/i18n.md) | 8a | Localisation (the look half) |
| [`modules/device-checks.md`](modules/device-checks.md) | 9 | Device checks for the looks |
