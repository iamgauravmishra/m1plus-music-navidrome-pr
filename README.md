# m1plus-mod

Firmware mod for the **Shanling M1 Plus** (Ingenic X2000, MTouch OS, AWTK UI app `/release/bin/demo`):
**M1 Pod**, an iPod-style UI built from the official V2.1 zip and packaged as a TF-card `update.bin`.
It follows the approach of [q2-pod](https://github.com/DiamondBond/q2-pod) for the Shanling Q2 (see `NOTICE`).

## The release

M1 Pod is the Home screen at start-up, without a top bar, and an "M1 Pod" icon on the stock grid opens it
again. The menu is iPod-classic ordered, essentials first: Now Playing, Cover Flow (with the album page),
Albums (one page: a grid of covers or a list with artist lines, one navbar button switches in place and the
choice is kept), Artists (Artist / Album Artist toggle, Cover Flow per artist), Songs, Playlists, Shuffle (Songs /
Albums / Folders), then Extras and Settings. Genres and Folders are in Extras by default. Settings > Main Menu
shows or hides each item and moves it up; a hidden item goes to the top of Extras, followed by Favorites, Recently
Added / Played, Most Played, Composers, Hi-Res, Update Library, Tidal and CD Ripper. Settings also has the Cover
Flow page (Landscape, Sort by Artist or Album), the Start in M1 Pod switch, Playback, System Settings and Shanling Home (the stock grid). Tidal
is the stock Tidal tile with Tabler's Tidal glyph. Around it: a minimal theme, Tabler
icons, Inter + Source Han Sans font, iPod-style library lists, an Apple-Music-style Now Playing (the cover's colour as the background, a sharp 264 px cover with round corners, remaining time), a translucent lock screen
card with a 280 px cover, one battery drawing for the status bar and the lock screen, a ring-style
pull-down, a boot logo, The Starry Night as the default wallpaper, and a boot guard that falls back to
the stock Home after a failed start. One album page everywhere: the stock album view (a restyled
header with a 120 px cover, year and track count, Play all and Shuffle) opens from Albums, Cover Flow,
the Albums grid, Artists and the All albums card. Everything it adds follows Settings > Language (13 languages). `docs/ui.md` has the pictures and the rules.

Status: the player runs V2.1mE (customisable menu, Apple-style Now Playing, every M1 Pod text localised, Cover Flow on the playing album with Artist / Album sort). History, hardware results and lessons per tag:
`docs/history.md`.

## Build, test, flash

```
python3 -m venv venv && venv/bin/pip install -r requirements.txt ; brew install squashfs llvm lld
cp "M1 Plus Firmware V2.1.zip" firmware/               # SHA-256 pinned in tools/build.py
venv/bin/python -I tools/mod_font.py --fetch           # the Source Han Sans SC zip, once
venv/bin/python -I tools/build.py                      # -> out/M1Plus-<tag>-release-update.bin
venv/bin/python -I tools/build.py --restore            # -> out/M1Plus-V2.1R-stock-restore-update.bin (way back)
venv/bin/python -I tools/check.py                      # both packages vs test/golden.sha256 + all tests
venv/bin/python -I tools/flash_sd.py out/M1Plus-<tag>-release-update.bin   # verified copy to the card
```

On the player: System settings, System Update, TF card update; leave the card in until it restarts.
About still reads V2.1. The updater refuses a package whose version equals the installed one, so bump
`TAG` in `tools/build.py` for every package you flash. An empty file `m1pod-off` at the card root
disables the payload without reflashing. Shanling's firmware is not part of this repo.

## Layout

| | |
|---|---|
| `tools/` | `build.py` (the release), `check.py` (done-criterion), `fwtool.py` (package pack/verify/diff), `mod_*.py` (asset steps), `pod*.py` (payload build, pages, assets, `pod_i18n.py`: the translations), `preview*.py`, `dis.py` / `elfinfo.py` / `reach.py` (binary analysis) |
| `patch/` | the payload C sources (cover cache, Cover Flow, Albums grid, Artists, Shuffle, album view, Now Playing, rows, home guard) and `offsets.inc` |
| `test/` | `patch.py` (emulated payload, modules in `test/pod/`), `demo_diff.py`, `coverflow.py`, `awtk_fill.py`, `golden.sha256` |
| `assets/` | boot logo, Inter subset, Tabler icon sources, wallpaper |
| `docs/` | `architecture.md`, `ui.md`, `workflow.md`, `history.md`, `firmware.md` |

## Docs

- `docs/workflow.md` build, test, flash, device checklist, going back
- `docs/architecture.md` pipeline, payload, hooks, boot guard, known stock addresses
- `docs/ui.md` looks, icons, lock screen, rows, album page, pull-down
- `docs/history.md` tags, hardware results, lessons
- `docs/firmware.md` firmware layout and the space step

## Safety

M1 Pod adds code to `demo`: one hook on a Home-icon tap, a second (`home_page_init`) behind a crash
marker, a third on the album page's header builder (runs only while that page is built), a fourth on Now Playing's init (a page timer for the tint and the remaining time), every patched word pinned, every hook falls back to stock, the kill switch above. Only the kernel
and rootfs are flashed; the bootloader and the recovery kernel are never written. The M1 Plus recovery
button combination is not documented by Shanling and unverified. `docs/workflow.md`, `docs/architecture.md`.
