# m1plus-mod

Asset-level firmware mods for the **Shanling M1 Plus** (Ingenic X2000, MTouch OS), following the
packaging approach of [q2-pod](https://github.com/DiamondBond/q2-pod) for the Shanling Q2.

Status: pipeline verified on hardware. A stock re-flash and the battery-percentage mod both installed
through the normal TF-card update (V2.1R, V2.1bB). The space-recovery step that is now on by
default flashed and booted fine on its own (V2.1cS), and the lock screen + icon+percent + space
package (V2.1cLB) works on the device. See `docs/workflow.md` for the test order.

## Mods

| variant | what you see | changed file |
|---|---|---|
| `percent` | `86%` replaces the battery icon | `release/assets/default/raw/ui/system_bar.bin` |
| `icon+percent` | state icon stays, `86%` to its left | same |
| `lockscreen` | lock screen: full-width clock, small date, `86%` next to the battery icon | `release/assets/default/raw/ui/screensaver_page.bin` |
| `lockscreen+icon+percent` | the lock screen mod plus the `icon+percent` status bar | both files above |
| `space` | nothing (UI stock): frees ~2.6 MB of rootfs for later mods; applied to every variant | `demo`'s unloaded `.pdr` zeroed (as in q2-pod), 10 unused files removed |

Previews: `docs/statusbar-preview.png`, `docs/lockscreen-preview.png` (both approximate PIL mock-ups).
Firmware and updater findings: `docs/firmware.md`.
How to make and test the next mod, step by step: `docs/workflow.md`.

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
- `tools/preview_bar.py`, `tools/preview_lockscreen.py` PIL mock-ups of the status bar / lock screen
- `tools/dis.py`, `tools/elfinfo.py` read-only ELF inspection helpers used for the analysis

## Safety

Only the kernel and rootfs partitions are flashed; the bootloader and the recovery kernel that performs
the flash are never written. The rootfs is a read-only squashfs. The M1 Plus recovery button
combination is not documented by Shanling; q2-pod's Q2 procedure is unverified on this model.
