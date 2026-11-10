# Theme

## Minimal theme (`tools/mod_theme.py`, `tools/awtk_style.py`)

`styles/*.bin` is AWTK's compiled theme: a 12-byte header (`fd fc fb fa`, version 0, item count), one
100-byte item per (state, style name, widget type) with the offset of its property block, then blocks
of `{u8 type, u8 key size, u16 value size, key\0, value}` (types 6 int32, 7 uint32 -- colours r,g,b,a
-- 14 string). All stock theme files round-trip byte-exact. Only the **default
theme** is modded: stock's theme1 (accent salmon `#FA7268`) is forced off at run time and its tree is removed from the rootfs (below).

| role | colour | stock |
|---|---|---|
| row surface | `#000000` | `#131313` |
| row hairline | `#222222`, 1 px bottom (M1+ Music rows: from x 56, under the title) | 4 px black gap |
| pressed row / key | `#333334` (one blue level off `#333333`: the accent maps it, nothing else has it) | `#362221` |
| title text | `#FFFFFF` | same |
| former accent text | `#FFFFFF` | `#FE7E40` / `#FA7268` |
| muted partner text | `#8C8C8C` | `#FFFFFF` |
| secondary text | `#AAAAAA` | same |
| settings icon | bare white glyph (no disc; the Home grid keeps its `#777777` discs) | coloured discs |
| list chevron | `#8A8A8A` (pressed `#6E6E6E`) | white |
| status glyph on / off | `#FFFFFF` / `#666666` | white / grey |
| slider fill / track / thumb disc | `#EEEEEC` / `#333333` / `#777777` | orange `#FE7E40` / `#333333` / orange disc |
| toggle on / off | white track, dark knob / stock grey track, light knob | orange track / same grey |
| Home page dots | `#EEEEEE` / `#555555` | `#FFFFFF` / `#666666` |

Edits are pinned (file SHA-256, per edit the old value and the state count, `STYLE_EDITS`):
`list_item_style`, `list_item_notpress_style`, `list_itemsort_style`, `btn_tablerow_style` (bg black,
pressed `#333333`, bottom hairline), `kb_btn1/2_style` pressed, the gold label styles
(`srlabel_item_gold18/20`, `label_centergold22`, `text_gold22`, lyric and tab styles: accent -> white
with the partner style muted grey so a selection still reads). Kept: red error text, the green/red
battery states, the red `icon_playing` disc, and every AWTK light default
style (`window`, `dialog`, `list_view`, `label`, `button`): stock pages set their dark colours inline,
and a global change of those defaults is how white-on-white happens. Images: the 46 settings icons
(40x40) get the `#777777` disc with the glyph kept (q2-pod's `ringnav_image_add` rule: saturation
against the icon's most saturated pixel blends disc grey to white, alpha kept bit for bit; replaced
later by the icons step), status icons redrawn at 4x (one weight, round caps, concentric Wi-Fi arcs,
unlit `#666666`). **Status bar** (`system_bar.bin`, on `mod_battery`'s layout; the table is `tools/statusbar.py`, which also
lays out the pull-down's own copy of the bar, `view_sysbar` in `dialog/dropdown_dialog.bin`: same widgets,
positions, images, fonts and colours, at y 0 of the dialog on the real bar's black; `test/pod/assets.py` compares the two files
and `preview.py` shows both bars stacked with their difference): `view_bar_left` x 10
s 4, `label_volume` 16 px middle in 30 px, `bar_dclock` 104,0 90 wide 18 px (a 12 h
`12:59 PM` is 66-72 px, clear of the Bluetooth rune), `view_bar_right` s 4 ending 4 px before the
battery outline. **Home** (`home_page.bin`): the strip black with a 1 px `#222222` top border, the
artist line `#AAAAAA`, dots `#EEEEEE`/`#555555`; the icon grid is built in code.

**Accents in images (`ACCENT_ART`, `accent_to`):** the orange left in stock art is recoloured at build time
(each file pinned by SHA-256, alpha kept bit for bit, name and size unchanged). A pixel's HSV saturation against the
accent's says how orange it is, its value (to the 1.5 power) keeps shading and dark text on the orange; the grey part
stays. Fills (`vol_progress`, `volume_fg`, `drop_fg`, `eq_plan`, `other_progress`, `cdprogress_bar`, the date selector's
`datetime_back` edge) go `#EEEEEC` on the stock `#333333` tracks;
the brightness / balance thumbs (`light_dot`, `balance_dot`) and the "default cover" corner flag
`screensaver_defaulticon` become `#777777` discs with the white glyph kept (the settings-icon disc); the default
cover tiles (`defaultcover`, `scover_default`) take the "no cover" tile colour `#333333` with the white logo.
**Switches** (`sset_on`, `sset_off`): redrawn without text
by `mod_theme.toggle_image` on the stock 57x28 canvas, a 46x24 pill track right-aligned in it (x 11, y 2) and an 18 px round knob
inset 3 px, 8x supersampled: on = off-white track `#EEEEEC` with a dark `#141414` knob on the right (the pull-down's white disc with a dark
glyph), off = `#3A3A3A` track with a `#8C8C8C` knob on the left. They serve the stock settings pages and our Settings, Main
Menu and Cover Flow rows alike (same size and anchor, so no row moves). `pset_dual` / `pset_high` keep their words
("Dual", "High": a value, no off twin), recoloured: a white track, dark text, a dark knob (luma-mapped inside the knob
circle); the pull-down's "on" is a white disc with a dark glyph. The states read by brightness and knob side, not by hue. Left orange on purpose: the CD ripper art (`cdripper_bg*`, `select_right`, `selectde_left`: the page's
styles hard-code orange text), the Online search button, `chargebg`'s red bolt, the hidden `p_hr`, the salmon bit-depth
and store badges (brand art, Chinese or account only).

**Contrast gates, every build:** `audit()` checks every state of the row styles against every label
style a row can hold (no light row surface; worst text >= 4.5:1 at rest and pressed: rest 9.04, pressed
5.44, white 21 / 12.6); `page_audit()` checks every text-drawing widget of every `ui/*.bin` against the
nearest opaque ancestor, stock vs mod, and fails if any pair falls below 4.5:1 and got worse;
`mod_theme.py --scan TREE STOCK` repeats the page scan on the finished tree (window themes included).

The colours above are the Black background with the Neutral accent. A user-picked accent and the Light background map them at run time ([accent and palette](accent.md)). Two colours exist only for that mapping and are one level off their neutral: a pressed row/key `#333334` (`PRESSED`, `LIST_PRESS`) and the Now Playing progress fill `#FFFFFEEB`; a test proves no other style or source has them.

## theme1 is off (`tools/themeoff.py`, `test/pod/themeoff.py`)

The palette ([accent](accent.md)) only maps the modded default theme, so stock's System > Theme choice is gone. Stock keeps it in `/mnt/data/config.ini [SYSSET] THEME` (0 default, 1 theme1; RAM word `0xa05a98`): `config_init` (`0x4e5030`, key read at `0x4e63b8`) does `atoi` and treats a value >= 2 as 0, `awtk_configinit` (`0x4ccb5c`, called from `application_init` after `platform_init`) calls `widget_set_theme(window_manager(), flag ? "theme1" : "default")`, and the Theme page (`systemset/theme_page`, init `0x4ae7c4`; rows `theme_item0/1`, handlers `0x4ae730` / `0x4ae77c` -> `0x4ae588`) writes it with `write_int_config`. Three pinned word edits in demo, no payload code and no boot hook (so the kill switch cannot undo them and boot has no new work):

- the clamp in `config_init`, `sltiu v1, v0, 2` (`0x4e63d8`) -> `sltiu v1, v0, 1`: any stored THEME other than 0 is read as 0, so `awtk_configinit` picks `"default"` on the first and only theme load of the boot. A device that was on theme1 comes up on default; the file keeps `THEME=1` (never rewritten: there is nothing left that reads it as 1, and a stock restore brings theme1 back as it was);
- the row table of the stock System page (`All System Settings`, `sysset` id 17): `systemset_sysset_page_init` (`0x4ada7c`) lists rows `0 .. count-1` of the table at `0x97c8c0` (identity 0..15) and the click handler (`0x4ad7b0`) maps the tapped row's name (`"%d"`) through the same table to a jump table (`0x748ae0`); index 10 is `sset_theme` -> `systemset/theme_page`. Entry 10 moves to the end of the table;
- the row count (`addiu v0, v0, 0xf` at `0x4adb1c`; one more for language 3) is one less. The rows built in code, so there is no Theme row in any asset (`ui/systemset/system_page.bin` and `theme_page.bin` have only the empty list and the navbar). The switch rows keep their positions 6 and 7 (`img_carmode%d`, `img_doublewake%d`).

`systemset/theme_page` is named only by the click dispatcher (`0x4ad9fc`, now unreachable) and by the page-init dispatcher `0x4d13d8`; nothing else opens it. The stock `release/assets/theme1` tree (271 files, 2.3 MB) is deleted from the rootfs by `tools/mod_space.py` (`remove_theme1`; `build.py` passes every entry as `--allow-removed`), and no build step, preview or test handles theme1 any more (`test/pod/navbars.py` asserts the directory is absent). Demo still has two names for it: the `"theme1"` literal (`0x748b84`) in `awtk_configinit` and the theme page, the latter unreachable, the former reached only with the flag set, which the clamp prevents. **The clamp must stay**: a stock-like `demo` without it would ask `assets_manager` for `theme1` when `THEME=1` is in `config.ini`. A stock restore brings the tree back with the stock rootfs.
