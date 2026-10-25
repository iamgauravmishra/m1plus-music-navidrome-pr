# m1plus-mod

Asset-level firmware mods for the **Shanling M1 Plus** (Ingenic X2000, MTouch OS), following the
packaging approach of [q2-pod](https://github.com/DiamondBond/q2-pod) for the Shanling Q2.

Status: pipeline verified on hardware, **including the code payload**. A stock re-flash and the
battery-percentage mod both installed through the normal TF-card update (V2.1R, V2.1bB); the
space-recovery step booted fine on its own (V2.1cS); the lock screen + icon+percent + space package
(V2.1cLB) works; and on 2026-10-20 **V2.1dM — M1 Pod, a code payload inside `demo` — was flashed
over stock and works** (the appended segment loads, the Home-icon hook opens the M1 Pod menu, its
rows open stock pages). **V2.1dC** added **Cover Flow**; on the device its page opened but the covers
ignored touch (a hidden full-screen view stayed hittable on this AWTK); **V2.1dD** fixed that and
swiping works on the device; **V2.1dE** fixes the track list's contrast and the menu's scrolling,
and **works on the device** (2026-10-25: covers swipe and tap, track list readable and scrolls, menu
scrolls). Four asset-only **looks** stack on V2.1dE (theme, library lists, Now Playing, boot logo +
quotes + settings slides; V2.1eT/eL/eN/eB) and **V2.1eA `look-all`** combines them (`docs/look-all.md`);
V2.1eA **works on the device** (2026-10-25, flashed over V2.1dE; the individual looks were not
flashed separately), except that the Now Playing album line kept a colon; **V2.1fA** (and the single
look V2.1fN) fixes that (`docs/look-nowplaying.md`, "The album line"). The f series adds, each on
V2.1fA and not yet hardware-tested: **V2.1fI** a new UI font, Inter + Source Han Sans SC
(`docs/font-inter.md`); **V2.1fK** an iPhone-style lock screen with a large rounded cover
(`docs/lockscreen2.md`); **V2.1fR** M1 Pod Artists and Cover Flow per artist (`docs/artists.md`);
**V2.1fS** Shuffle Songs / Albums / Folders (`docs/shuffle.md`). **V2.1gA `full`** combines all of
them (`docs/full.md`) and **works on the device** (2026-10-25: fonts, Artists, Shuffle and Now
Playing confirmed; the lock screen is being refined from feedback). See `docs/workflow.md` for the
test order.

## Mods

| variant | what you see | changed file |
|---|---|---|
| `percent` | `86%` replaces the battery icon | `release/assets/default/raw/ui/system_bar.bin` |
| `icon+percent` | state icon stays, `86%` to its left | same |
| `lockscreen` | lock screen: full-width clock, small date, `86%` next to the battery icon | `release/assets/default/raw/ui/screensaver_page.bin` |
| `lockscreen+icon+percent` | the lock screen mod plus the `icon+percent` status bar | both files above |
| `space` | nothing (UI stock): frees ~2.6 MB of rootfs for later mods; applied to every variant | `demo`'s unloaded `.pdr` zeroed (as in q2-pod), 10 unused files removed |
| `pod-inert` / `pod-hello` / `pod-menu` | **M1 Pod**: new pages injected into `demo` as code (q2-pod-style), opened from the Home Tidal icon. Staged: inert (no hook), hello (a test page), menu (an iPod-style menu). Each also carries lock screen + icon+percent + space | a code payload appended to `demo`, one hook, new `ui/m1pod_*.bin` |
| `pod-cover` | the menu plus **Cover Flow**: the stock Local Music albums as a swipeable cover carousel with a depth effect, its own thumbnail cache on the card, tap to open an album and play a track (`docs/coverflow.md`) | the same payload, one more page asset; still one hook |
| `look-theme` | pod-cover plus a **Minimal neutral theme** (q2-pod style): black list rows with hairlines and grey pressed feedback, accent text neutral, grey settings icon discs, redrawn status glyphs, a tidier status bar (one 16 px size, 18 px clock) and Home strip (`docs/look-theme.md`, V2.1eT) | `styles/default.bin`, `ui/system_bar.bin`, `ui/home_page.bin`, 55 `images/xx` PNGs |
| `look-lists` | `pod-cover` plus iPod-style library lists (V2.1eL): every list follows `list_item_style` like the M1 Pod menu, 21 px titles, a dark index letter, underlined Search tabs, one pressed colour in the dialogs (`docs/look-lists.md`) | page themes `styles/<page>.bin` (default + theme1), `ui/allmusic_page.bin`, `ui/dialog/batchadd_dialog.bin` |
| `look-nowplaying` | `pod-cover` plus an **iPod-style Now Playing** (q2-pod's look): rounded art, title / artist / album hierarchy, quiet monochrome controls, off-white progress line (`docs/look-nowplaying.md`, preview `docs/look-nowplaying-preview.png`) | `ui/playing_page.bin`, `styles/playing_page.bin`, 20 new `images/xx/np_*.png` |
| `look-boot` | `pod-cover` plus an **M1 Pod boot logo** (q2-pod style, upright and 180°), curly quotes ’ “ ” drawn as straight ones without the wide gap, and settings pages that slide in and out (`docs/look-boot.md`) | `images/xx/logo.jpg`, `logo180.jpg`, `fonts/default.ttf`, `ui/systemset/*.bin` |
| `look-all` | all four looks on `pod-cover`, in the order theme -> lists -> nowplaying -> boot: the lists follow the Minimal theme's rows and pressed colour; the settings slides are kept after a safety audit of the window-stack loops (`docs/look-all.md`, preview `docs/look-all-preview.png`, V2.1fA; V2.1eA without the album fix) | the union of the four rows above (133 files vs V2.1dE) |
| `look-all-inter` | `look-all` with a new UI font, built first: **Inter** 4.1 Regular for Latin/Greek/Cyrillic (tracked -8/256 so English averages the stock width, tabular digits, proper curly quotes, Vietnamese) and **Source Han Sans SC** Regular for CJK, kana and Hangul; stock vertical metrics, every stock code point kept; the lock clock and Now Playing re-measure it (`docs/font-inter.md`, preview `docs/font-inter-preview.png`, V2.1fI; needs fontTools and `tools/mod_font.py --fetch`) | `fonts/default.ttf`, `ui/screensaver_page.bin` and `ui/playing_page.bin` re-measured, the pull-down's `ui/dialog/dropdown_dialog.bin` (default + theme1) with a wider volume label (5 files vs V2.1fA) |
| `look-lock2` | `look-all` plus an **iPhone-style lock screen** (V2.1fK): small date over an 88 px clock at the top; while something is queued a dark card with the cover at 254 x 254 (the size the app writes it at, so 1:1) with rounded corners, title / artist and play / next under it; no battery percentage (a small gauge top right); nothing queued: just date and clock on the wallpaper (`docs/lockscreen2.md`, preview `docs/lockscreen2-preview.png`) | `ui/screensaver_page.bin`, `styles/screensaver_page.bin`, new `images/xx/ls_artmask.png` |
| `artists` | `look-all` plus **M1 Pod Artists**: the menu's Artists row opens our own scrolling artist list (the stock Artists query, stock-styled rows), and an artist opens **Cover Flow on that artist's albums** (q2-pod's artist scope: titled with the artist, an All albums card with two albums or more, the shelf stops at both ends, the main page's last album untouched); the Cover Flow page loses its hint line and is re-centred (`docs/artists.md`, preview `docs/artists-preview.png`, V2.1fR) | `demo` (payload stage E), `ui/m1pod_cover.bin`, new `ui/m1pod_artists.bin` (3 files vs V2.1fA) |
| `shuffle` | `look-all` plus three M1 Pod menu rows (q2-pod's Shuffle): **Shuffle Songs** (the whole library, stock Shuffle mode, from a random song), **Shuffle Albums** (albums in random order, each in track order), **Shuffle Folders**; one tap opens Now Playing; no new hook (`docs/shuffle.md`, V2.1fS) | `demo` (payload stage F), `ui/m1pod_menu.bin` (2 files vs V2.1fA) |
| `full` | everything of the f series in one package (V2.1gA): the font first, then theme -> lists -> nowplaying -> boot, lock screen 2 last, on payload stage G (Cover Flow + Artists + Shuffle); still one hook (`docs/full.md`, preview `docs/full-preview.png`; needs fontTools and `tools/mod_font.py --fetch`) | 12 files vs V2.1eA: `demo`, `fonts/default.ttf`, `ui/playing_page.bin`, `ui/screensaver_page.bin` + `styles/screensaver_page.bin` + new `images/xx/ls_artmask.png`, `ui/m1pod_menu.bin`, `ui/m1pod_cover.bin`, new `ui/m1pod_artists.bin`, `ui/dialog/dropdown_dialog.bin` (default + theme1) |

Previews: `docs/full-preview.png` (V2.1gA), `docs/statusbar-preview.png`, `docs/lockscreen-preview.png`, `docs/lockscreen2-preview.png`, `docs/coverflow-preview.png`
(approximate; the Cover Flow one composes the real renderer's output under a PIL mock-up of the
page, and `docs/coverflow-preview-rest.png` is the renderer's raw frame), `docs/artists-preview.png`
(the Artists list and an artist's Cover Flow).
Firmware and updater findings: `docs/firmware.md`.
How to make and test the next mod, step by step: `docs/workflow.md`.
How the M1 Pod code payload is injected (addresses, hook, kill switch, staging): `docs/payload.md`.
Cover Flow (stock queries, depth renderer, thumbnail cache, thread): `docs/coverflow.md`.
Artists and Cover Flow per artist (the stock artist queries, evidence, tests): `docs/artists.md`.
Shuffle (the stock Songs path, the play mode, the album order, limits): `docs/shuffle.md`.
Everything together (V2.1gA: stacking order, verification, the combined device checklist): `docs/full.md`.

## Packages

What each variant builds today (`tools/build.py`; two clean builds of each are byte-identical).
Payload stages: `tools/pod_pages.py` (`docs/payload.md`, "Stages and features").

| variant | tag | stage | SHA-256 | |
|---|---|---|---|---|
| `pod-cover` | V2.1dE | D | `0806ade2…` | works on the device |
| `look-theme` / `look-lists` / `look-boot` | V2.1eT / eL / eB | D | `6f921f4f…` / `768b6abd…` / `9cd5d06c…` | |
| (`look-all` at commit 62015e7) | V2.1eA | D | `cc86e833…` | works on the device (album colon) |
| `look-nowplaying` | V2.1fN | D | `dbb0dee5…` | |
| `look-all` | V2.1fA | D | `0e3980fb…` | V2.1eA + the album fix |
| `look-all-inter` | V2.1fI | D | `ff8d90bf…` | branch build `fa1f04d7…` (old album offset, no pull-down fix) |
| `look-lock2` | V2.1fK | D | `8e825a77…` | branch build `5b2549dc…` (on V2.1eA) |
| `artists` | V2.1fR | E | `d2862615…` | branch build `a7a5bf7a…` (on V2.1eA) |
| `shuffle` | V2.1fS | F | `baa4996e…` | branch build `447eed67…` (on V2.1eA) |
| `full` | V2.1gA | G | `e81541f1…` | `docs/full.md` |

The branch builds of the f packages differ from these only in `ui/playing_page.bin` (and V2.1fI also
in the pull-down files): they were built on V2.1eA, these on V2.1fA. None of them was flashed.

## Build

```
python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp "~/Downloads/M1 Plus Firmware V2.1.zip" firmware/
python3 -I tools/build.py --variant space          # -> out/M1Plus-V2.1cS-space-update.bin (flash this first)
python3 -I tools/build.py --variant icon+percent   # -> out/M1Plus-V2.1cB-iconpercent-space-update.bin
python3 -I tools/build.py --variant percent        # -> out/M1Plus-V2.1cA-percent-space-update.bin
python3 -I tools/build.py --variant lockscreen     # -> out/M1Plus-V2.1cL-lockscreen-space-update.bin
python3 -I tools/build.py --variant lockscreen+icon+percent   # -> ...V2.1cLB-lockscreen-iconpercent-space...
python3 -I tools/build.py --variant icon+percent --watchdog   # -> ...V2.1cBW-iconpercent-space-watchdog...
python3 -I tools/build.py --variant icon+percent --no-space   # -> out/M1Plus-V2.1bB-iconpercent-update.bin (tested)
python3 -I tools/build.py --restore                # -> out/M1Plus-V2.1R-stock-restore-update.bin
# M1 Pod code payload (needs Homebrew llvm + lld; see docs/payload.md). Flash V2.1dA first.
python3 -I tools/build.py --variant pod-inert      # -> out/M1Plus-V2.1dA-pod-inert-...-update.bin (no hook)
python3 -I tools/build.py --variant pod-hello      # -> out/M1Plus-V2.1dH-pod-hello-...-update.bin
python3 -I tools/build.py --variant pod-menu       # -> out/M1Plus-V2.1dM-pod-menu-...-update.bin
python3 -I tools/build.py --variant pod-cover      # -> out/M1Plus-V2.1dE-pod-cover-...-update.bin
# Looks (asset-only, on top of pod-cover; Pillow from the venv). Each alone, or all four together.
python3 -I tools/build.py --variant look-theme     # -> out/M1Plus-V2.1eT-look-theme-pod-cover-...-update.bin
python3 -I tools/build.py --variant look-lists     # -> out/M1Plus-V2.1eL-look-lists-pod-cover-...-update.bin
python3 -I tools/build.py --variant look-nowplaying  # -> out/M1Plus-V2.1fN-look-nowplaying-pod-cover-...
python3 -I tools/build.py --variant look-boot      # -> out/M1Plus-V2.1eB-look-boot-pod-cover-...-update.bin
python3 -I tools/build.py --variant look-all       # -> out/M1Plus-V2.1fA-look-all-pod-cover-...-update.bin
# UI font (fontTools from requirements.txt; downloads the pinned Source Han Sans SC zip once, 95 MB)
python3 -I tools/mod_font.py --fetch
python3 -I tools/build.py --variant look-all-inter # -> out/M1Plus-V2.1fI-look-all-inter-pod-cover-...-update.bin
python3 -I tools/build.py --variant look-lock2     # -> out/M1Plus-V2.1fK-look-lock2-pod-cover-...-update.bin
# Payload features on top of look-all (series f; stages E and F)
python3 -I tools/build.py --variant artists        # -> out/M1Plus-V2.1fR-artists-look-all-pod-cover-...-update.bin
python3 -I tools/build.py --variant shuffle        # -> out/M1Plus-V2.1fS-shuffle-look-all-pod-cover-...-update.bin
# Everything: font + four looks + lock screen 2 on stage G (Cover Flow + Artists + Shuffle)
python3 -I tools/build.py --variant full           # -> out/M1Plus-V2.1gA-full-pod-cover-...-update.bin
venv/bin/python -I test/patch.py work/mod-pod-cover-lockscreen-iconpercent-space  # Unicorn tests (any pod tree)
venv/bin/python -I test/coverflow.py               # host build of the Cover Flow renderer
```

Shanling's firmware is not part of this repo; the build pins its SHA-256.

## Flash

Rename the package to `update.bin`, copy it to the root of the microSD card, then on the player:
System settings, System Update, TF card update. Leave the card in until it restarts. About still
shows V2.1. The official V2.1 file is refused by the menu while V2.1 is installed (identical version
string), so use the restore package to go back. The player does not delete `update.bin` after flashing.

## Tools

- `tools/fwtool.py` unpack / repack / verify `update.bin`, metadata-exact to stock
- `tools/awtk_ui.py` parse / serialize AWTK binary UI files (`ui/*.bin`)
- `tools/mod_battery.py` the battery mod
- `tools/mod_lockscreen.py` the lock screen mod (`--help` lists the layout knobs; `--layout cover` is look-lock2's);
  it also holds the shared AWTK text model (`StbText`: truncated advances, +1 px per glyph) that
  `mod_nowplaying.py` and `mod_font.py` measure with
- `tools/mod_space.py` the space-recovery step (`.pdr` zeroing, unused-file removal, opt-in watchdog)
- `tools/pod.py` the M1 Pod code payload: compile, install the one hook, append the segment (`docs/payload.md`)
- `tools/pod_ui.py`, `tools/pod_pages.py` the M1 Pod page assets and their single source of truth
- `patch/coverflow.c` the Cover Flow page and its depth renderer (ported from q2-pod), with its
  artist scope; `patch/artists.c` the M1 Pod Artists list
- `patch/shuffle.c` Shuffle Songs / Albums / Folders (after q2-pod's Shuffle page, `docs/shuffle.md`)
- `test/patch.py` Unicorn harness that executes the real payload offline
- `test/coverflow.py` host build of the Cover Flow renderer, with checks and PNG captures
- `tools/awtk_style.py` parse / serialize AWTK binary theme files (`styles/*.bin`), shared by the looks
- `tools/mod_theme.py`, `tools/mod_lists.py`, `tools/mod_nowplaying.py`, `tools/mod_boot.py` the four
  looks (`docs/look-*.md`); `mod_theme.py --scan` is the contrast scan build.py runs on every look tree
- `tools/mod_font.py` the UI font step (Inter + Source Han Sans SC merged into `default.ttf`);
  `tools/font_inter.py` makes its committed Inter subset; `tools/stb_raster.py` draws text the way
  AWTK's stb_truetype backend does, for `tools/preview_font.py` (`docs/font-inter.md`)
- `tools/preview_bar.py`, `tools/preview_lockscreen.py` PIL mock-ups of the status bar / lock screen;
  `tools/preview_theme.py`, `preview_lists.py`, `preview_nowplaying.py`, `preview_all.py` of the looks;
  `tools/preview_artists.py` of the Artists list and an artist's Cover Flow; `tools/preview_full.py`
  of a `full` tree (all of them, text drawn from the tree's font)
- `tools/dis.py`, `tools/elfinfo.py` read-only ELF inspection helpers used for the analysis

## Safety

M1 Pod adds code to `demo`, so it ships in stages (inert → hello → menu), installs one hook on a
user-initiated Home-icon tap (never the boot path), falls through to stock behaviour on any error,
and can be disabled without reflashing by placing an empty file `m1pod-off` at the root of the SD
card. Details and the on-device test order: `docs/payload.md`, `docs/workflow.md`.

Only the kernel and rootfs partitions are flashed; the bootloader and the recovery kernel that performs
the flash are never written. The rootfs is a read-only squashfs. The M1 Plus recovery button
combination is not documented by Shanling; q2-pod's Q2 procedure is unverified on this model.
