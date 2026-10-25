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
scrolls). See `docs/workflow.md` for the test order.

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

Previews: `docs/statusbar-preview.png`, `docs/lockscreen-preview.png`, `docs/coverflow-preview.png`
(approximate; the Cover Flow one composes the real renderer's output under a PIL mock-up of the
page, and `docs/coverflow-preview-rest.png` is the renderer's raw frame).
Firmware and updater findings: `docs/firmware.md`.
How to make and test the next mod, step by step: `docs/workflow.md`.
How the M1 Pod code payload is injected (addresses, hook, kill switch, staging): `docs/payload.md`.
Cover Flow (stock queries, depth renderer, thumbnail cache, thread): `docs/coverflow.md`.

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
venv/bin/python -I test/patch.py work/mod-pod-cover-lockscreen-iconpercent-space  # Unicorn tests
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
- `tools/mod_lockscreen.py` the lock screen mod (`--help` lists the layout knobs)
- `tools/mod_space.py` the space-recovery step (`.pdr` zeroing, unused-file removal, opt-in watchdog)
- `tools/pod.py` the M1 Pod code payload: compile, install the one hook, append the segment (`docs/payload.md`)
- `tools/pod_ui.py`, `tools/pod_pages.py` the M1 Pod page assets and their single source of truth
- `patch/coverflow.c` the Cover Flow page and its depth renderer (ported from q2-pod)
- `test/patch.py` Unicorn harness that executes the real payload offline
- `test/coverflow.py` host build of the Cover Flow renderer, with checks and PNG captures
- `tools/preview_bar.py`, `tools/preview_lockscreen.py` PIL mock-ups of the status bar / lock screen
- `tools/dis.py`, `tools/elfinfo.py` read-only ELF inspection helpers used for the analysis

## Safety

M1 Pod adds code to `demo`, so it ships in stages (inert → hello → menu), installs one hook on a
user-initiated Home-icon tap (never the boot path), falls through to stock behaviour on any error,
and can be disabled without reflashing by placing an empty file `m1pod-off` at the root of the SD
card. Details and the on-device test order: `docs/payload.md`, `docs/workflow.md`.

Only the kernel and rootfs partitions are flashed; the bootloader and the recovery kernel that performs
the flash are never written. The rootfs is a read-only squashfs. The M1 Plus recovery button
combination is not documented by Shanling; q2-pod's Q2 procedure is unverified on this model.
