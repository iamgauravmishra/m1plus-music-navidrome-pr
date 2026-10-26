# Workflow: build, test, flash

## 0. One-time setup

```
python3 -m venv venv && venv/bin/pip install -r requirements.txt
brew install squashfs llvm lld     # unsquashfs/mksquashfs >= 4.5 (-pf support); clang + ld.lld for the payload
cp "M1 Plus Firmware V2.1.zip" firmware/
venv/bin/python -I tools/mod_font.py --fetch   # Source Han Sans SC zip (SHA-256 pinned) into fonts/
venv/bin/python -I tools/build.py --restore    # also unpacks stock into work/stock
```

`work/stock/` holds `rootfs/` (extracted root filesystem), `recovery-update/` (stock kernel and
squashfs), `stock.pseudo` (exact inode metadata) and `meta.json` (tar member metadata, superblock
parameters). Treat it as read-only; mods are built in copies. Run Python on extracted firmware with
`-I` so nothing inside the untrusted tree can be imported. Gitignored inputs (zip, `venv/`, `fonts/`,
`work/stock`) resolve from the main checkout when you work in a git worktree (`tools/paths.py`).

## 1. Build

```
venv/bin/python -I tools/build.py            # the release -> out/M1Plus-<TAG>-release-update.bin
venv/bin/python -I tools/build.py --restore  # stock images with a new tag -> out/M1Plus-V2.1R-stock-restore-update.bin
```

The release is the battery step, the font, the space step, the payload (`tools/pod.py`) and the asset
steps in the order of `STEPS` in `tools/build.py`, then `fwtool repack`. Builds are deterministic.
`tools/fwtool.py verify|diff|info` inspects a package; `fwtool diff` prints `-`/`+` pairs for entries
whose metadata changed or that were removed, `~` for same metadata but different content.

Version tags: must contain a capital `V`, must not equal the installed version (the updater refuses
it), so every package you flash needs a tag that is not installed: bump `TAG` in `tools/build.py`
before a build you intend to flash (format `V2.1` + series letter + capital letters; `V2.1R` is the
restore package). `docs/history.md` lists the tags used so far.

## 2. Test

```
venv/bin/python -I tools/check.py            # DONE-CRITERION: both packages vs test/golden.sha256, all tests (~1 min)
venv/bin/python -I tools/check.py --only release --keep   # quick loop, tree left in work/check/release/
venv/bin/python -I tools/check.py --update   # only when a hash change is intended; commit test/golden.sha256
venv/bin/python -I test/patch.py work/check/release/work/mod-release [MODULE...]   # the emulator tests alone
venv/bin/python -I tools/preview.py WORKDIR docs/release-preview.png    # PIL mock-up of the screens
```

`check.py` builds the release and restore packages in parallel, compares their SHA-256 with the golden
file (CHANGED is a failure unless you meant it), then runs `test/patch.py` (the real compiled payload
under Unicorn, one module per feature in `test/pod/`: menu, coverflow, assets, artists, rows, albuminfo,
shuffle, home; shared machine in `test/pod/harness.py`) once per distinct payload, `test/demo_diff.py`
(the built `demo` differs from stock only where the mods say), `test/coverflow.py` (host build of the
depth renderer) and `test/awtk_fill.py` (demo's own fill code). A feature gets a module with a
`run(ctx)` and a line in `MODULES` in `test/patch.py`.

## 3. Change something

- **An asset step** (`tools/mod_*.py`): clone the tree (`modlib.clone_workdir`), parse the `.bin` with
  `awtk_ui.parse`, edit widgets, `awtk_ui.serialize` back after asserting the untouched file
  round-trips byte-exact, keep file modes (`modlib.edit_ui`). Find widgets the app drives with
  `tools/dis.py xref|sym work/stock/rootfs/release/bin/demo NAME`. Rules: never rename or delete a
  widget the app looks up by name (restyle, move or hide it: `visible=false` plus `sensitive=false`);
  pin stock files by SHA-256 and refuse to build on mismatch; the rootfs must not exceed stock size
  (`docs/firmware.md` section 4 for the space step).
- **The payload** (`patch/*.c`, `tools/pod.py`, `tools/pod_pages.py`): `docs/architecture.md`. Every
  patched word is pinned; a new stock function goes into `FUNCTIONS` in `tools/pod.py` with its address.
- Then `tools/check.py`; a changed package hash means `--update` and a new tag.

## 4. Flash

```
venv/bin/python -I tools/flash_sd.py out/M1Plus-V2.1kE-release-update.bin     # verified copy to the card as update.bin, eject
```

(`--dry-run`, `--no-eject`; by hand: copy to the card root as `update.bin`, compare md5, eject.) Use a
card that mounts fine on the player (exFAT or FAT32); the card's music is untouched. Card in with the
player off, power on, System settings, System Update, TF card update, confirm, leave the card in until
the player restarts by itself. The player does not delete `update.bin`; overwrite it with the next package.

First time only: flash the restore package. It reinstalls the stock kernel and rootfs byte for byte,
so it proves the package path with nothing new on the device.

Before flashing you may pre-place an empty file `m1pod-off` at the root of the SD card to keep the
payload disabled (the entry icon then behaves exactly as stock; the boot guard and row fit are off
too). Delete it to enable M1 Pod.

### Device checklist for the release

- boots to M1 Pod as the Home screen; About still reads V2.1; sleep, wake, reboot; "Shanling Home"
  row shows the stock grid, "Start in" toggles the start-up setting and survives a reboot
- the Tidal icon on the stock grid opens M1 Pod (it is the hooked entry)
- menu rows (Now Playing, Cover Flow, Shuffle, Songs, Albums, Artists, Genres, Folders, Playlists,
  Settings) open their pages; Back returns; icons on every row; lists scroll, a drag does not open a row
- Cover Flow: first run builds the cache (Cancel works), covers swipe and flick, side tap glides, centre
  tap opens the stock album page (120 px cover, year and track count, Play all, Shuffle; Shuffle starts a
  random track of the album in Shuffle mode and stays on the page); a track plays from Now Playing; Back unwinds
- Albums list and Artists: the same album page; the queue (Now Playing list) title is 20 px, the playing row has the red disc
- Artists: names in stock order; an artist's Cover Flow with the All albums card; Back chain
- Shuffle Songs / Albums / Folders play and leave the stock play mode as documented in `docs/architecture.md`
- library pages (Songs, Albums, album, Playlists) show 64 px rows, one-line rows elsewhere
- Now Playing, lock screen (280 px cover on a translucent card, small battery gauge, play/next work,
  swipe from anywhere, nothing queued: date + clock only; Starry Night wallpaper by default), pull-down
  tiles and battery icon, boot logo, settings page slides
- the kill switch: `m1pod-off` on the card makes the entry icon open Tidal again

## 5. Going back and safety

Flash the `V2.1R` restore package. The official V2.1 file is refused by the menu while V2.1 is the
installed version (identical string). Only the kernel and rootfs are flashed; the bootloader and the
recovery kernel are never written. If the UI ever fails to start, the watchdog reboots the player in
a loop rather than leaving it dead; the fallback is the recovery path with `recovery-update/` from the
official zip on the card root (the button combination for the M1 Plus is unverified; q2-pod's Q2
procedure: hold Previous, power on with Centre). The payload's boot guard (`docs/architecture.md`)
returns to the stock Home after a failed start by itself.

## 6. Where things are

| | |
|---|---|
| official zip | `firmware/` (gitignored, SHA-256 pinned in `tools/build.py`) |
| unpacked stock | `work/stock/` |
| the release tree | `work/mod-release/` (with `podbuild/`: payload ELF and manifest) |
| packages | `out/` |
| reference | q2-pod clone for its docs and asset conventions (kept outside this repo) |
