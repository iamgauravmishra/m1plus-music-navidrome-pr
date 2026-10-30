# UI reference

The interface uses a minimal, iPod-inspired style for the 320 × 480 touchscreen. Asset steps
preserve widget names, pin the stock bytes they replace and run in `tools/build.py` order.
Runtime behaviour is documented in [architecture](architecture.md).

Generate the release preview with `tools/preview.py WORKDIR [OUT.png]` (default
`out/preview/release-preview.png`, gitignored; `docs/workflow.md`). The sheet shows:
Home pages 1 and 3 (the M1+ Music icon), the M1+ Music menu as Home (no top bar), the Settings, Main Menu, Shuffle and
Extras pages, the Artists toggle, the album page, an artist's Cover Flow (and the landscape one), the Albums grid and
list, the pull-down with the toggle and slider art (`controls()`), the lock screen (playing; idle on the charger) and
the battery at 8x. The feature previews (`preview_icons.py`, `preview_stock.py`,
`preview_battery.py`, `preview_nowplaying.py` ...) write wherever you point them; use `out/preview/`. All are
approximate PIL mock-ups drawn from the built tree (not AWTK), text rasterised from the tree's own `default.ttf`
the stb_truetype way (`tools/preview_font.py`, `tools/stb_raster.py`), sample data.

`make preview` renders the selected dev artifact without changing it; see [workflow](workflow.md).
Device captures and checks are documented [here](modules/device-checks.md).

## Before changing the UI

Read [UI rules](modules/ui-rules.md) and [text measurement](modules/text-width.md). Reproduce
bugs with an emulation test or device screenshot. Reuse the shared layout/text model in previews
and measure the font from the tree being built.

## References

| Area | Documentation |
|---|---|
| Fonts and theme | [Fonts](modules/fonts.md), [theme format/palette](modules/theme.md) |
| Navigation | [Menu](modules/menu.md), [settings](modules/settings.md), [navbars](modules/navbar.md) |
| Library | [Lists](modules/lists.md), [rows](modules/rows.md), [Albums](modules/albums.md), [album page](modules/album-page.md) |
| Playback | [Now Playing](modules/nowplaying.md), [More sheet](modules/playmore.md), [mini player](modules/minibar.md) |
| Home content | [Recently Played](modules/recent.md), [Daily Mix](modules/dailymix.md) |
| Extras | [Playlists](modules/playlists.md), [Songs](modules/songs.md), [Podcasts](modules/podcasts.md), [Cassette Mode](modules/tape.md), [virtual iPod](modules/ipod.md), [iPod Cover Flow](modules/ipod-coverflow.md) |
| System appearance | [Boot logo/slides](modules/boot.md), [icons](modules/icons.md), [battery](modules/battery.md), [pull-down](modules/pulldown.md), [lock screen](modules/lockscreen.md), [wallpaper](modules/wallpaper.md), [About/polish](modules/polish.md) |
| Languages | [Translation and sizing](modules/i18n.md) |

Older source comments refer to former UI sections: 1 rules, 2 text width, 3 fonts, 4 theme/lists/
Now Playing, 5 boot, 6 icons/battery, 7 stock pages and assets, 8 menu/Albums, 8a languages,
9 device checks. Detailed code and asset notes now share the corresponding module file.
