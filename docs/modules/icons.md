# Icons

Split out of docs/ui.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 6. Icons and the battery

### Lucide icons (`tools/mod_icons.py`)

**Lucide** (lucide-static 1.61.0, ISC; `NOTICE`, `assets/icons/lucide/LICENSE`); `mod_icons.py` is the mapping table. **Sizes:** the Home grid keeps its 66 px discs, glyph canvas 38 px at stroke 1.75 (grid units); every
list icon is a **bare** white glyph, no disc: a 24 px canvas at stroke 2.0 px absolute (the M1+ Music rows' image is that
canvas, the stock 40x40 settings, Folders, Playlists and CD images carry it centred); pull-down tiles: glyph 24 px, stroke 2
grid units, "PO" / "LO" 17 px Inter; Now Playing star and More: 32 px translucent disc, glyph ink 18 px, stroke 2.0 px, centred optically (box and centroid averaged, quarter-pixel placement); the
navbar and the other glyph buttons (`SMALL_GLYPHS`) fit a 20 px ink box (stock 22) at 2.0 px stroke, the Now Playing button
`back_to_player` unchanged; dialog glyphs (`DIALOG_GLYPHS`) and selection marks x0.88; the "no cover" tiles' glyph is 0.52 of the
tile; the Play all pill's play glyph is 10 px; the status bar and the transport shapes are unchanged; every touch target is
unchanged. The list chevrons (`right_arrow`, the Main Menu's `expansion_2`, `expansion`) are `#8C8C8C`, `#6E6E6E` pressed.
Now Playing keeps the solid PIL transport shapes. Lucide has no filled style: `name:filled` fills the outline
shapes (star, play, pause, skip, lock); `ellipsis` is always filled. Kept Tabler (`T:` prefix, 4 glyphs,
`assets/icons/tabler/svg/`, Tabler 3.49.0, MIT): `brand-tidal`, `circle-check` filled (selection marks: a disc
with the tick cut out), `a-b`, `multiplier-1x`. Custom SVGs kept: `badge-hr`, `dac`,
`gain-low/high`, `volume-3waves`; the custom guitar is gone (Lucide `guitar`); the Shanling mark is stock art.
`mod_icons.py --fetch TGZ` takes either pinned tarball (Lucide to `assets/icons/lucide/svg/`, Tabler to
`assets/icons/tabler/svg/`); PNGs: `assets/icons/png/`.

**Sources.** Both sets (Tabler: `@tabler/icons` 3.49.0, MIT, (c) Pawel Kuna; `NOTICE`, `assets/icons/tabler/LICENSE`)
are pinned by the npm tarball's SHA-256 (`mod_icons.py --fetch TGZ` copies the SVGs it uses, parsed as
data with whitelisted tags and attributes). Committed: the used SVGs (`assets/icons/lucide/svg/`),
custom SVGs (`assets/icons/custom/`) and the generated PNGs (`assets/icons/png/`, 318 files);
the build only copies PNGs (no rasteriser, deterministic); `--generate` re-renders them with
`rsvg-convert` and Pillow at the exact stock size, `--pins` writes the stock SHA-256 pins
(`tools/mod_icons_pins.txt`), `--check [WORKDIR]` verifies pins, size and mode.

| area | files | design |
|---|---|---|
| settings icons | all 46 (40x40) | bare white glyph (24 px canvas, stroke 2.0 px) centred in the image, no disc; DAC, DSD output (twice) and ReplayGain are white text badges (Inter in a 24x16 rounded rectangle, 1.5 px line; `badge()`), labels stay at x 60 |
| Home grid | 18 + 18 `_down` (66x66) | white glyph (38 px) on `#777777` (`#555555` pressed); HiFi (zh_CN) a store; Tidal is Tabler's `brand-tidal` (`tidal`, `tidal_down`, which every state of `home_tidal_style` names) |
| M1+ Music Home icon | added `m1plus.png`, `m1plus_down.png` (66x66) | the Lucide `smartphone` glyph on the same disc (the iPod click wheel until V2.1oK); the style `home_m1plus_style` (a copy of `home_tidal_style` pointing at them) is added to `styles/home_page.bin` in the stock sort order; the widget is built at run time (`docs/modules/home-guard.md`) |
| pull-down tiles | 17 (50x50, 20x20 sun icons) | one ring style, section 7 |
| status bar | 15 (play, pause, volume 0-4, Wi-Fi 0-4, Bluetooth off/on, digital out) | white, unlit Wi-Fi arcs `#666666`; 1.5 px strokes at 14-16 px, 2 px at 20 |
| list placeholders | 6 bare glyphs (40x40), 3 "no cover" tiles (60/90/100) | bare glyph / the tile colour with a muted glyph (0.52 of the tile) |
| Extras Customize button | `pod_nav_customize` (+ `_down`) | the left cap of the Customize + Now Playing capsule (like `pod_nav_artist`), Lucide `sliders-horizontal` (the Customize row icon's glyph); `ui/m1plus_extras.bin` |
| Albums view toggle | 4 added `pod_nav_grid`, `pod_nav_list` (+ `_down`, 24x24) | plain white glyphs (pressed `#777777`) like the navbar's others: Lucide `layout-grid` and `list` (`list.svg` is the one new SVG), each showing the mode a tap switches to; used by `ui/m1plus_albums.bin`, which swaps the glyph with its mode |
| M1+ Music rows | 26 added `pod_ic_*.png` (24x24, bare) | menu (also as Home), Shuffle, Customize, Developer, Extras settings, Cover Flow settings, Extras and Main Menu page rows; glyph x 16..40, title x 56, a 1 px `#222222` hairline from x 56 to the row's right edge (child view `pod_hair`, insensitive; the theme's full-width bottom border is switched off on these rows, `border_width` 0; the pressed `#333333` band stays full width), row height and chevrons unchanged, image insensitive |

Rule: an icon has a real Lucide glyph (Tabler for the four it lacks), or keeps its stock image (when decent), or is drawn in Lucide's
style (24 grid, 2 px stroke, round caps; `assets/icons/custom/`). Custom: `guitar` (Genres), `badge-hr` (Hi-Res), `dac` (USB DAC), `volume-3waves`
(Lucide stops at two), `gain-low`/`gain-high` (tiles). Stock kept: brand art and text badges (codec badges, SyncLink, A-B), theme1 (own image files),
the Chinese-only Home ids. Row glyphs: Now Playing the Lucide `audio-lines` wave (the navbar button's glyph), Cover Flow `gallery-horizontal`,
Shuffle `shuffle`, Songs `music`, Albums `disc-3`, Artists `mic-vocal`, Genres `guitar`, Folders
`folder`, Playlists `list-music`, Customize `sliders-horizontal` (was Settings `settings`; `settings` is now System Settings only); the Customize page: Main Menu `list-checks`, Extras `ellipsis`, Cover Flow `gallery-horizontal` (opens Customize > Cover Flow: Landscape `rotate-cw-square`, Sort `arrow-down-wide-narrow` with its value Artist / Album as grey 19 px text at the right, no chevron), Home Screen `house` (opens Customize > Home Screen: Boot to M1+ Music `power`, Shanling Home the mark below), Playback `headphones`, System Settings `settings`, Developer `code` (opens Customize > Developer: Screenshot), Shanling Home the Shanling mark (`pod_ic_shanling`: the brand's swoosh cut from the stock shutdown screen `images/xx/shutdown.png`, SHA-256 pinned in `tools/mod_icons.py`, isolated by whiteness, scaled to 24 px wide and thickened by a round 1.5 px dilation to a stroke of about 2 px; no glyph set involved); Extras `ellipsis` and the Extras page's rows the Home grid's glyphs (`star`, `clock-plus`, `history`, `flame`, `feather`, `badge-hr`, `refresh-cw`, `globe`, `disc`); the Shuffle page uses the song,
album and folder glyphs. `ui/m1plus_menu.bin`, `m1plus_shuffle.bin`, `m1plus_settings.bin`, `m1plus_extras.bin` and `m1plus_mainmenu.bin` (and `m1plus_cfset.bin`) get the child image and hairline (title x 24 -> 56). `icons` runs late so it overrides the theme step's grey discs.

### Icon audit, round 2 (`tools/audit_images.py`)

`audit_images.py [STOCK [TREE]]` lists every `images/xx` file referenced by a `ui/**/*.bin` property, a style
file or a name string in `demo` (560 files), and with TREE only those still byte-identical to stock. Before
round 2, 429 were stock; round 2 changed 110 stock files plus the `np_*` glyphs (21 now, V2.1mB). Result for the 560:

| class | files | action |
|---|---|---|
| Lucide (rounds 1+2) | 241 (131 + 110) | glyph in the stock size; round 2: navbar add / cancel / delete / multi-select / sort / search / back / chevron / more / settings (+ pressed `#777777`), selection circles and squares, expanders, queue-dialog modes, dialog actions (rename, scan, delete, add network, eye), Now Playing more-dialog and batch-add icons, Bluetooth/USB page transport |
| bare glyph (40x40) | 24 of those | Folders rows (16 audio formats share `file-music`, SD, USB), Playlists page (New, Import, Export), CD track dialog (custom `guitar`, microphone, calendar) |
| custom SVG | 2 uses | `guitar` (Genres, CD genre); round 1 customs unchanged |
| Tabler `multiplier-1x` | 1 | `p_multiple` (28x28): the icon of the playback-speed row in the Now Playing more dialog (`playmore_dialog`, beside the 1.0X / 1.25X / 1.5X / 2.0X badges). The Play Settings list has no speed row, so there is no 40 px disc icon for it |
| Lucide (ISC) | 2 | `back_to_player` / `back_to_player_down` the navbar's go-to-Now-Playing icon, Lucide `audio-lines` (`assets/icons/lucide/`, lucide-static 1.61.0, tarball SHA-256 `62773cd2...ba75f1`, licence beside it, `NOTICE`), 23x24 like search, 2 px stroke, pressed `#777777`. The button is a static `img_btn_style` image pair (names without digits, no frame swap in `demo`: the only other `playing_*` names are the loading spinner `playing_wait_1..12` and the list's `icon_playing` disc) |
| stock recoloured white | 9 | equaliser preset instruments (`eq_*`), the line art is kept |
| drawn (Inter text / Lucide glyph) | 14 | speed badges (8), Play all pills (4: off-white pill, dark text), secured Wi-Fi rows (4: fan + lock) |
| orange to neutral | 15 | toggles, slider fills and thumbs, default covers (section 4, "Accents in images") |
| kept, decent or not an icon | 302 | 100 keyboard keys, 70 backgrounds / scroll arrows / unused check and radio art, 69 brand, codec and text badges, protocol art, the red `icon_playing` disc, 55 Tidal / HiFi store / purchase / guide art (Chinese or account only), 14 CD ripper art, 11 superseded by `np_*` or the brightness suns |

The Folders page has no "up" row image (Back goes up); Favourites and every playlist use `icon_playlist`
(round 1); Genres, Composers, Artists, Albums and search rows use the round-1 `icon_*` discs. `mod_icons.py`
`GLYPHS`, `DISCS`, `RECOLOUR`, `SPEEDS`, `PLAYALL`, `WIFI_LOCK`, `NP` are the tables; glyphs are fitted to the
stock canvas by ink size, 2 px stroke (1.5 under 22 px), the navbar and dialog glyphs smaller (above). Not asset-only: nothing here changes code.
(`tools/preview_icons.py STOCK_TREE RELEASE_TREE OUT.png`) before and after at
1:1 with a 3x status strip; blue **C** = custom glyph, orange **K** = stock kept.
