# Workflow: making and testing an asset-level mod

This is the process that produced the battery-percentage mod, written down so the next mod follows the
same path. Everything here was exercised on a real M1 Plus on 2026-10-19.

## 0. One-time setup

```
python3 -m venv venv && venv/bin/pip install -r requirements.txt
brew install squashfs            # unsquashfs / mksquashfs >= 4.5 (needs -pf support)
cp "M1 Plus Firmware V2.1.zip" firmware/
python3 -I tools/build.py --restore          # also unpacks stock into work/stock
```

`work/stock/` then holds `rootfs/` (extracted root filesystem), `recovery-update/` (stock kernel and
squashfs), `stock.pseudo` (exact inode metadata) and `meta.json` (tar member metadata, superblock
parameters). Treat `work/stock` as read-only reference; mods are built in copies of it.

Run Python on extracted firmware with `-I` so nothing inside the untrusted tree can be imported.

## 1. Find what to change

1. UI layouts are AWTK binary files under `rootfs/release/assets/default/raw/ui/`. Dump one:
   ```
   python3 -I tools/awtk_ui.py dump work/stock/rootfs/release/assets/default/raw/ui/system_bar.bin
   ```
   Each widget has a type, fixed `x y w h`, and ordered `key = value` properties. Children layouts
   such as `default(r=1,c=0,a=right,s=5)` override the children's own `x`. Only
   `assets/default` matters; `theme1` carries a handful of pages and no status bar.
2. Images live in `images/xx` (1x) with `x1 x2 x3` variants; fonts in `fonts/default.ttf`; the
   theme in `styles/default.bin`; strings in `strings/`.
3. Which widget the app drives at runtime: search the player binary for the widget name and read
   the surrounding code.
   ```
   venv/bin/python -I tools/dis.py xref work/stock/rootfs/release/bin/demo pgbar_battery
   venv/bin/python -I tools/dis.py sym  work/stock/rootfs/release/bin/demo dropdown_showface
   ```
   `dis.py` annotates calls, GOT loads and string references, so the dump reads like
   "widget_lookup(win, "pgbar_battery") ... progress_bar_set_value(...)". The app looks widgets up by
   name, so names must stay the same; type, geometry and style properties are free to change.
4. Check the property is honoured by this AWTK build: either the stock assets already use it
   (grep the `ui/*.bin` files, e.g. `visible`, `#RRGGBBAA` colours, `show_text`, `format`) or the
   binary contains the property string.

## 2. Make the change

Write a small script like `tools/mod_battery.py`: clone `work/stock` (APFS `cp -Rc` is instant),
parse the `.bin` with `awtk_ui.parse`, edit widgets with `.set()` / `.remove()` / geometry fields,
`awtk_ui.serialize` back, and assert the untouched file round-trips byte-exact first. Keep the
file's permission bits (stock UI files are mode 744).

Rules that keep a mod safe:

- never rename or delete a widget the app looks up by name; restyle, move, or hide it instead
  (`visible=false`, plus parking it off-screen as a belt-and-braces measure)
- keep the rootfs no larger than stock (fwtool refuses otherwise). A bare rebuild has only 12 KB
  of headroom; run the space step on your tree (`tools/mod_space.py WORKDIR`, then repack with
  `--tailends` and the `--allow-removed` list) for ~2.6 MB, see `docs/firmware.md` section 4.
  `build.py` does this for every mod variant
- change one thing per package so a bad result is attributable

## 3. Package

```
python3 -I tools/fwtool.py repack work/mod-xyz out/M1Plus-V2.1xY-update.bin --version V2.1xY \
    [--tailends --allow-removed PATH ...]     # with the space step; one --allow-removed per removed file
python3 -I tools/fwtool.py verify out/M1Plus-V2.1xY-update.bin
python3 -I tools/fwtool.py diff "work/M1 Plus Firmware V2.1/update.bin" out/M1Plus-V2.1xY-update.bin
```

`fwtool diff` prints `-`/`+` pairs for entries whose metadata changed or that were removed, `~` for
files with the same metadata but different content, and one summary line for directories that
differ only in listed size (directory-table layout). Expect only your files, plus `demo` (`.pdr`
zeroed) and the 10 removals when the space step is on. To check contents, extract the package's
squashfs and `diff -rq` it against `work/stock/rootfs`.

Version tag rules (from the updater's code): must contain a capital `V`, must not equal the
installed version string, and every package needs a distinct tag so re-flashing is never refused.
Convention used so far: `V2.1` + lowercase series letter + capital variant letters. `b` = without
the space step (`V2.1bA`, `V2.1bB`), `c` = with it (`V2.1cS` space only, `V2.1cA`, `V2.1cB`
battery, `V2.1cL` lock screen, `V2.1cLB` lock screen + icon+percent), a trailing `W` for the slower
watchdog (`V2.1cBW`); `V2.1R` for the stock restore package.

`fwtool repack` rebuilds the squashfs with the stock parameters (LZO, 128 KiB blocks, stock
mkfs time), re-applies every stock inode's mode, owner and mtime from `stock.pseudo` (macOS loses
symlink modes and setuid bits on extraction), checks the metadata against stock (a stock entry may
be missing only if it is listed with `--allow-removed`), regenerates the `.info` file and rebuilds
the tar with the stock member metadata. An unmodified round trip without `--tailends` gives a
zero-line full-precision listing diff against stock.

Optional: `tools/preview_bar.py` renders a PIL mock-up of the status bar for a quick look before
flashing. It is not AWTK, so font metrics are approximate.

## 4. Test on the device

Use a card that mounts fine on the player (exFAT or FAT32). The card's music is untouched by the
update; `update.bin` sits next to it at the root.

1. First time only: flash the restore package (`--restore`, tag `V2.1R`). It reinstalls the stock
   kernel and rootfs byte for byte, so it proves the whole package path (tar layout, `.info`,
   MD5 check, recovery flasher) with nothing new on the device.
2. Copy the mod package to the card root as `update.bin` and confirm the copy:
   ```
   cp out/M1Plus-V2.1bB-iconpercent-update.bin /Volumes/<card>/update.bin && sync
   md5 -r /Volumes/<card>/update.bin out/M1Plus-V2.1bB-iconpercent-update.bin
   diskutil eject /Volumes/<card>
   ```
3. Card in with the player off, power on, System settings, System Update, TF card update,
   confirm, leave the card in until the player restarts by itself. The player reboots into a plain
   flashing screen, then boots normally.
4. Checklist after boot:
   - About still reads V2.1 (the version string in `demo` is never changed)
   - the changed screen looks right; for the status bar: number updates, charging swaps the icon
     and keeps the real level, Bluetooth and Wi-Fi together do not crowd the clock
   - other pages that embed the same widgets (pull-down panel, screensaver, lock screen) still draw
   - lock screen (`V2.1cL` / `V2.1cLB`), lock the player and wake it:
     - clock fits on one line, is centred, and ticks over each minute
     - switch System settings 12/24 h both ways: the status bar clock changes, the lock clock stays 24 h
       (stock behaviour; note what the status bar shows in 12 h, the code suggests `05:30 PM`)
     - date correct, centred under the clock
     - battery percentage shows, matches the status bar, and changes over time; plug in a charger:
       the icon becomes the bolt and the number keeps updating (100% once the charge completes)
     - now-playing strip shows cover, title and artist while playing, play/pause and next work, and
       the strip disappears when nothing is queued
     - swipe to unlock works
     - a custom wallpaper (Screensaver settings) still shows; turning "show time" off hides clock,
       date and battery together (stock behaviour)
     - screen rotation set to 180: the lock screen turns as a whole, nothing clipped or misplaced
   - sleep, wake and a reboot
5. The player does not delete `update.bin` after flashing; overwrite it with the next package.

### Space step: test order (not yet hardware-tested)

The space step changes one binary, `demo` (unloaded `.pdr` bytes only, as q2-pod does on the Q2),
and removes 10 files, so it gets its own package before anything is combined with it:

1. `V2.1R` if the player is not already on a known-good build.
2. `M1Plus-V2.1cS-space-update.bin`: space step only, UI identical to stock. Check:
   - it boots to the normal home screen and stays up (no watchdog reboot loop)
   - About still reads V2.1
   - playback from the card: start, pause, seek, next track, a few formats (FLAC, MP3, AAC/M4A)
   - library: browse by folder and by artist/album, cover art shows, a library rescan finishes
   - settings pages open and a changed setting survives a reboot
   - sleep, wake, a reboot; if you use them: Bluetooth output and Wi-Fi (the removed old glib and
     dbus copies sit next to the libraries their daemons use)
3. Then `M1Plus-V2.1cB-iconpercent-space-update.bin` (or `cA`) with the status-bar checks above.
   `cBW` additionally slows the watchdog poll to 10 s; nothing visible should change.

If `cS` misbehaves, flash `V2.1R` and bisect: build a tree with
`tools/mod_space.py work/mod-x --from work/stock --no-remove` (only `.pdr`) or `--no-pdr` (only the
removals), repack with `--tailends` (and the `--allow-removed` list for removals) under a new tag.

`mod_space.py --pdr-all` zeroes `.pdr` in all 197 executables and libraries for ~540 KB more. It is
off by default and not in `build.py`: no hardware has run such binaries yet. If you try it, use its
own tag and run the full checklist above.

## 5. Going back

Flash the `V2.1R` restore package. The official V2.1 file is refused by the menu while V2.1 is the
installed version (identical string). If the UI ever fails to start, the watchdog reboots the player
in a loop rather than leaving it dead; the fallback is the recovery path with `recovery-update/`
from the official zip on the card root. The button combination for the M1 Plus is unverified
(q2-pod's Q2 procedure: hold Previous, power on with Centre).

## 6. Where things are

| | |
|---|---|
| official zip | `firmware/` (gitignored, SHA-256 pinned in `tools/build.py`) |
| unpacked stock | `work/stock/` |
| modified trees | `work/mod-*/` |
| packages | `out/` |
| reference | q2-pod clone for its docs and asset conventions (kept outside this repo) |
