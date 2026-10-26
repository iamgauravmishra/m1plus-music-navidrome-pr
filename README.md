# m1plus-mod

Firmware mod for the **Shanling M1 Plus** (Ingenic X2000, MTouch OS, AWTK UI app `/release/bin/demo`):
**M1 Pod**, an iPod-style UI built from the official V2.1 zip and packaged as a TF-card `update.bin`.
It follows the approach of [q2-pod](https://github.com/DiamondBond/q2-pod) for the Shanling Q2 (see `NOTICE`).

## Current release: V2.1kE

M1 Pod is the Home screen at start-up, without a top bar, and an "M1 Pod" icon on the stock grid opens it
again. The menu has Now Playing, Cover Flow (with the album page), Shuffle (Songs / Albums / Folders),
Songs, Albums, Artists (Cover Flow per artist), Genres, Folders, Playlists and Settings (System and Play
settings, Shanling Home, a "Start in" toggle). Tidal is the stock Tidal icon. Around it: a minimal theme, Tabler
icons, Inter + Source Han Sans font, iPod-style library lists and Now Playing, a translucent lock screen
card with a 280 px cover, one battery drawing for the status bar and the lock screen, a ring-style
pull-down, a boot logo, The Starry Night as the default wallpaper, and a boot guard that falls back to
the stock Home after a failed start. One album page everywhere: the stock album view (a restyled
header with a 120 px cover, year and track count, Play all and Shuffle) opens from Albums, Cover Flow,
Artists and the All albums card. `docs/ui.md` has the pictures and the rules.

Status: V2.1kE is built and tested (emulated payload), not yet flashed; V2.1jA is the build the player runs. History, hardware results and lessons per tag:
`docs/history.md`.

## Build, test, flash

```
python3 -m venv venv && venv/bin/pip install -r requirements.txt ; brew install squashfs llvm lld
cp "M1 Plus Firmware V2.1.zip" firmware/               # SHA-256 pinned in tools/build.py
venv/bin/python -I tools/mod_font.py --fetch           # the Source Han Sans SC zip, once
venv/bin/python -I tools/build.py                      # -> out/M1Plus-V2.1kE-release-update.bin
venv/bin/python -I tools/build.py --restore            # -> out/M1Plus-V2.1R-stock-restore-update.bin (way back)
venv/bin/python -I tools/check.py                      # both packages vs test/golden.sha256 + all tests
venv/bin/python -I tools/flash_sd.py out/M1Plus-V2.1kE-release-update.bin   # verified copy to the card
```

On the player: System settings, System Update, TF card update; leave the card in until it restarts.
About still reads V2.1. The updater refuses a package whose version equals the installed one, so bump
`TAG` in `tools/build.py` for every package you flash. An empty file `m1pod-off` at the card root
disables the payload without reflashing. Shanling's firmware is not part of this repo.

## Layout

| | |
|---|---|
| `tools/` | `build.py` (the release), `check.py` (done-criterion), `fwtool.py` (package pack/verify/diff), `mod_*.py` (asset steps), `pod*.py` (payload build, pages, assets), `preview*.py`, `dis.py` / `elfinfo.py` / `reach.py` (binary analysis) |
| `patch/` | the payload C sources (Cover Flow, Artists, Shuffle, album view, rows, home guard) and `offsets.inc` |
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
marker, a third on the album page's header builder (runs only while that page is built), every patched word pinned, every hook falls back to stock, the kill switch above. Only the kernel
and rootfs are flashed; the bootloader and the recovery kernel are never written. The M1 Plus recovery
button combination is not documented by Shanling and unverified. `docs/workflow.md`, `docs/architecture.md`.
