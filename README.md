# m1plus-mod

Firmware mod for the **Shanling M1 Plus** (Ingenic X2000, MTouch OS, AWTK UI app `/release/bin/demo`):
**M1+ Pod**, an iPod-style UI built from the official V2.1 zip and packaged as a TF-card `update.bin`.
It follows the approach of [q2-pod](https://github.com/DiamondBond/q2-pod) for the Shanling Q2 (see `NOTICE`).

## The release

M1+ Pod is the Home screen at start-up, without a top bar, and an "M1+ Pod" icon on the stock grid opens it
again. The menu is iPod-classic ordered, essentials first: Now Playing, Cover Flow (with the album page),
Albums (one page: a grid of covers or a list with artist lines, one navbar button switches in place and the
choice is kept), Artists (Artist / Album Artist toggle, Cover Flow per artist), Songs, Playlists, Shuffle (Songs /
Albums / Folders), then Extras and Settings. Genres and Folders are in Extras by default. Settings > Main Menu
shows or hides each item and moves it up; a hidden item goes to the top of Extras, followed by Favorites, Recently
Added / Played, Most Played, Composers, Hi-Res, Update Library, Tidal and CD Ripper, which Main Menu can show in the
menu too (a shown one leaves Extras). The Extras row itself is the last switch on that page and can be hidden; Settings always shows. Settings also has the Cover
Flow page (Landscape, Sort by Artist or Album), Home Screen (the Start in M1+ Pod switch and Shanling Home, the stock grid), Playback and System Settings. Tidal
is the stock Tidal tile with Tabler's Tidal glyph. Around it: a minimal theme, Lucide
icons, Inter + Source Han Sans font, iPod-style library lists, an Apple-Music-style Now Playing (the cover's colour as the background, a sharp 264 px cover with round corners, remaining time), a translucent lock screen
card with a 280 px cover, one battery drawing for the status bar and the lock screen, a ring-style
pull-down, a boot logo, The Starry Night as the default wallpaper, and a boot guard that falls back to
the stock Home after a failed start. One album page everywhere: the stock album view (a restyled
header with a centred 160 px rounded cover, year and track count, a round Shuffle and a Play all pill) opens from Albums, Cover Flow,
the Albums grid, Artists and the All albums card. Everything it adds follows Settings > Language (13 languages). `docs/ui.md` has the pictures and the rules.

Status: V2.1oH (oG + Back from Now Playing no longer shows a playlist's songs as album rows with folder icons: Now Playing's tick no longer loads the stock album list, and the Playlists page's loader stops behind other pages) is the release; its content, test build oGP (on oG), was copied to the card 2026-10-29. Before it, V2.1oG (oF + the fade under our navbars darkens nothing at rest: on Albums and Playlists it shows only once the list is scrolled, on text pages a steeper curve); its content, test build oEA (on oE), was flashed 2026-10-28, looks good. Before it, V2.1oF (oE + Settings > Main Menu can hide the Extras row), its content, test build oEX, was copied to the card 2026-10-28, good. Before it, V2.1oE (oD + the Playlists "..." menu in Now Playing's More sheet's glass, with a glyph per row and a card as wide as the language needs); its menu, test build oCJ (on oC), was copied to the card 2026-10-28. Before it, V2.1oD (oC + glass navbars on our own pages: a glass Back disc, the title after it, the right-hand buttons as one glass capsule and a soft fade under the bar; the album page's controls float as glass discs over the cover tint; stock pages unchanged); its content, test build oCA, was flashed 2026-10-28, good. Before it, V2.1oC (oB + the Playlists page: a grid or list of 2x2 album-cover mosaics, a "..." menu with New / Import / Export / Delete; every reachable navbar on the Pod navbar's slots) was copied to the card as test build oAT 2026-10-28, good enough. Before it, V2.1oB (oA + the main menu keeps its scroll position: Back returns to the row the user left), copied to the card as test build oAS 2026-10-28, good enough. Before it, V2.1oA (nX + the Albums page on the stock scroll view: stock drag and fling, no cover decoding while it moves, the stock scroll bar, the crash when the list was pulled past its top fixed); its Albums part was flashed as test build nZ 2026-10-28 (on nW), good. Before it, V2.1nX (nW + the favorite glyph a star instead of a heart: Now Playing filled / outline, the Home Favorites tile, the Extras row, the batch-add dialog); its content, test build nWS, was copied to the card 2026-10-28. Before it, V2.1nW (nT + the mini bar's glass on the lock screen's now-playing card, the album page's Play all and Shuffle, Now Playing's heart and More, and the More sheet) was flashed as test build nTG 2026-10-28, looks great. Before it, V2.1nT (nP + a Recently Played shelf at the foot of the Home menu: the last 6 albums as 2 x up to 3 rows of the Albums grid's covers, a tap opens the album, Settings > Home Screen > Recent Albums; rounded covers in the Albums grid and list) was flashed 2026-10-28, good. Before it, V2.1nP (nO + a mini player bar on the Home menu: an Apple-Music-style glass pill with the cover, title, artist, play/pause and next, the list scrolling behind it under an experimental backdrop blur; Now Playing hidden in the default menu) was flashed 2026-10-27, looks great. Before it, V2.1nO (nN + the boot logo reads just M1+: smaller, the plus a superscript flush with the cap top) was built, not flashed; V2.1nN (nM + the More menu as a dimmed bottom sheet with two pages, a readable speed row); V2.1nM (nL + the album page navbar 44 px and an even header rhythm, Now Playing polish (times, rhythm, vivid tint, cover shadow, brighter glyphs, centred heart), an All albums button on the artist Cover Flow). Before it, V2.1nL (nK + a RAM tone cache so the album tint appears at once, the album track list on a deep tint, the status bar tinted on the album page, a shared cover worker, the Albums page building missing covers, Settings > Cover Flow > Rebuild Covers) is on the player (flashed 2026-10-27, looks good). Earlier: V2.1nF (see below; mY = Lucide icons, redrawn transport glyphs, a 20 px Now Playing title, a wave marker at the right of the playing row, an experimental status bar that takes Now Playing's colour, a Cover Flow button in the Albums navbar, the Main Menu fix mQ, the new album page mR, bare list glyphs and the approved icon sizes, a pull-down status bar identical to the real one (mX), Settings > Home Screen (mU), Extras > Screenshot (mT)). V2.1nJ (nG + nH + nI: the UI font Inter Medium; the boot logo reads M1+ Pod; the Play all pill's glyph and text centred as a pair with an 8 px gap in every language; nG = nF + the nB fix: the menu lists keep their order through the stock relayout and the pull-down no longer meets the list_view's early-exit paint hook; nF = mY + list gestures: a swipe never plays a song, a touch on a coasting list stops it and presses nothing; the Albums grid in 2 columns; Main Menu one tap = one action; the Play all pill with the glyph left of the text; secondary album track numbers and no placeholder disc on Artists / Genres / Composers rows; Artists sorted A to Z; and Screenshot moved to the last Settings row, the Extras page in a fixed Library / Tools order) is built, not flashed. History, hardware results and lessons per tag:
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
About shows the stock firmware version V2.1 and, below it, an `M1+ Pod:<tag>` row. The updater refuses a package whose version equals the installed one, so bump
`TAG` in `tools/build.py` for every package you flash. An empty file `m1pod-off` at the card root (the internal name stays `m1pod`, so existing settings and the switch survive the rename to M1+ Pod)
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
- `docs/history.md` tags, hardware results, lessons
- `docs/firmware.md` firmware layout and the space step

## Safety

M1+ Pod adds code to `demo`: one hook on a Home-icon tap, a second (`home_page_init`) behind a crash
marker, a third on the album page's header builder (runs only while that page is built), a fourth on Now Playing's init (a page timer for the tint and the remaining time), every patched word pinned, every hook falls back to stock, the kill switch above. Only the kernel
and rootfs are flashed; the bootloader and the recovery kernel are never written. The M1 Plus recovery
button combination is not documented by Shanling and unverified. `docs/workflow.md`, `docs/architecture.md`.
