# m1plus-mod

Firmware mod for the **Shanling M1 Plus** (Ingenic X2000, MTouch OS, AWTK UI app `/release/bin/demo`):
**M1+ Music**, a modern music player UI (much of it in the manner of Apple Music) built from the official V2.1 zip and packaged as a TF-card `update.bin`.
It follows the approach of [q2-pod](https://github.com/DiamondBond/q2-pod) for the Shanling Q2 (see `NOTICE`).

## The release

M1+ Music is the Home screen at start-up, without a top bar, and an "M1+ Music" icon on the stock grid opens it
again. The default menu is minimal: Cover Flow (with the album page),
Albums (one page: a grid of covers or a list with artist lines, one navbar button switches in place and the
choice is kept), Artists (Artist / Album Artist toggle, Cover Flow per artist with all its songs on the Songs page), Songs (letter sections, an A-Z rail, Search / Sort / Select; Favorites, Recently Added / Played, Most Played, Hi-Res and each playlist open on the same page), Playlists, then Extras, always last. Everything else is on Extras, under four section headers: Play (Now Playing, Shuffle (Songs /
Albums / Folders)), Library (Albums, Artists, Songs, Playlists, Cover Flow, Genres, Composers, Folders), Collections (Favorites, Recently Played / Added, Most Played, Hi-Res) and Tools (Update Library, CD Ripper, Tidal, Customize);
a header shows only while its group has a row. Customize > Main Menu shows or hides each item and moves it up (a shown one leaves Extras, a hidden one goes back to its group);
Customize > Extras (same groups) turns off the ones you never want listed, and a hidden Customize is always listed on Extras. Below the menu, the Home screen has a Daily Mix card ("Made for You": a mix made once a day from what you play, with its own Apple-Music-style page) and the Recently Played shelf, with the mini player bar floating over them. Customize also has the Cover
Flow page (Landscape, Sort by Artist or Album), Home Screen (the Boot to M1+ Music, Recent Albums and Daily Mix switches, Regenerate Daily Mix, and Shanling Home, the stock grid), Playback, System Settings and Developer (Screenshot, which asks first and can be cancelled). Tidal
is the stock Tidal tile with Tabler's Tidal glyph. Around it: a minimal theme, Lucide
icons, Inter + Source Han Sans font, iPod-style library lists, an Apple-Music-style Now Playing (the cover's colour as the background, a sharp 264 px cover with round corners, remaining time), a translucent lock screen
card with a 280 px cover, one battery drawing for the status bar and the lock screen, a ring-style
pull-down, a boot logo, The Starry Night as the default wallpaper, and a boot guard that falls back to
the stock Home after a failed start. One album page everywhere: the stock album view (a restyled
header with a centred 160 px rounded cover, year and track count, a round Shuffle and a Play all pill) opens from Albums, Cover Flow,
the Albums grid, Artists, the All albums card and Now Playing's Look up album. Everything it adds follows Settings > Language (13 languages). `docs/ui.md` has the pictures and the rules.

Status: the release is V2.1oV (its test build oUDM is on the card). Milestones, hardware results and lessons:
`docs/history.md`; per-tag details are in git.

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
About shows the stock firmware version V2.1 and, below it, an `M1+ Music:<tag>` row. The updater refuses a package whose version equals the installed one, so bump
`TAG` in `tools/build.py` for every package you flash. An empty file `m1plus-off` at the card root
disables the payload without reflashing. Shanling's firmware is not part of this repo.

## Layout

| | |
|---|---|
| `tools/` | `build.py` (the release), `check.py` (done-criterion), `fwtool.py` (package pack/verify/diff), `mod_*.py` (asset steps), `pod*.py` (payload build, pages, assets, `pod_i18n.py`: the translations), `preview*.py`, `dis.py` / `elfinfo.py` / `reach.py` (binary analysis) |
| `patch/` | the payload C sources (cover cache, Cover Flow, Albums grid, Artists, Shuffle, album view, Now Playing, rows, home guard) and `offsets.inc` |
| `test/` | `patch.py` (emulated payload, modules in `test/pod/`), `demo_diff.py`, `coverflow.py`, `awtk_fill.py`, `golden.sha256` |
| `assets/` | boot logo, Inter subset, Lucide (and a few Tabler) icon sources, wallpaper |
| `docs/` | `architecture.md`, `ui.md`, `workflow.md`, `history.md`, `firmware.md` |

## Docs

- `docs/workflow.md` build, test, flash, device checklist, going back
- `docs/architecture.md` index of `docs/modules/` (one file per module): pipeline, payload, hooks, boot guard, known stock addresses, features
- `docs/ui.md` index of the looks (same `docs/modules/`): icons, lock screen, rows, album page, pull-down
- `docs/history.md` milestones, hardware results, lessons
- `docs/firmware.md` firmware layout and the space step

## Safety

M1+ Music adds code to `demo`: one hook on a Home-icon tap, a second (`home_page_init`) behind a crash
marker, a third on the album page's header builder (runs only while that page is built), a fourth on Now Playing's init (a page timer for the tint and the remaining time), every patched word pinned, every hook falls back to stock, the kill switch above. Only the kernel
and rootfs are flashed; the bootloader and the recovery kernel are never written. The M1 Plus recovery
button combination is not documented by Shanling and unverified. `docs/workflow.md`, `docs/architecture.md`.
