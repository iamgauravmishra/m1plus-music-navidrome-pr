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
`work/cache/build/` (`tools/buildcache.py`) keeps the result of each stage, keyed by the hash of its inputs
(the stage's code and what it imports, `assets/`, `patch/`, the previous stage's key); an unchanged stage is
applied from the cache, the bytes are identical (`--no-cache` or `M1_NO_CACHE=1` bypasses it). The first stage
(battery, font, space) is the 10 s one; `build.py --tree-only` stops before the repack (what the tests need).
Each stage prints its time.
`tools/fwtool.py verify|diff|info` inspects a package; `fwtool diff` prints `-`/`+` pairs for entries
whose metadata changed or that were removed, `~` for same metadata but different content.

Version tags: must contain a capital `V`, must not equal the installed version (the updater refuses
it), so every package you flash needs a tag that is not installed: bump `TAG` in `tools/build.py`
before a build you intend to flash (format `V2.1` + series letter + capital letters; `V2.1R` is the
restore package). `git log --oneline --grep V2.1` shows the release tags used so far (integration commits start with the tag).

## 2. Test

```
venv/bin/python -I tools/check.py --tests-only   # DONE-CRITERION of a feature branch: every test, no package, no golden (~10 s)
venv/bin/python -I tools/check.py --test albums  # selected tests only (patch modules by name, one section as albums/toggle_tests, or tools, coverflow, awtk_fill, demo_diff)
venv/bin/python -I tools/check.py            # DONE-CRITERION of the integration step: both packages vs test/golden.sha256, all tests
venv/bin/python -I tools/check.py --only release --keep   # quick loop, tree left in work/check/release/
venv/bin/python -I tools/check.py --update   # integration only, when a hash change is intended; commit test/golden.sha256
venv/bin/python -I test/patch.py work/check/release/work/mod-release [MODULE...]   # the emulator tests alone
venv/bin/python -I tools/preview.py work/check/release/work/mod-release   # PIL mock-up -> out/preview/ (gitignored)
```

`check.py` builds the release tree, then packs it while the tests already run (one process pool of
`os.cpu_count()` workers, the slowest test first; the floor of a run is the tree build plus the slowest
module, today `albums`), builds the restore package in parallel, compares the SHA-256 of both with the golden
file (CHANGED is a failure unless you meant it), then runs `test/patch.py` (the real compiled payload
under Unicorn, one module per file in `test/pod/`, each its own process; shared machine in
`test/pod/harness.py`) once per distinct payload, `test/demo_diff.py`
(the built `demo` differs from stock only where the mods say), `test/coverflow.py` (host build of the
depth renderer and the cover filters), `test/awtk_fill.py` (demo's own fill code) and `test/tools.py` (package
verification on synthetic archives, check.py's own pass/fail/`--update` decisions). A failed build or test makes
`--update` exit non-zero and write nothing. `--update` right after a passing full run of the same files (content
of every file but `docs/`, the README/AGENTS and the golden file; same tool versions; kept in
`work/cache/check-last.json`) reuses that run: no rebuild, no tests, it only writes the golden file. A feature gets a
`test/pod/<name>.py` with a `run(ctx)`; nothing else to register. A module that runs for seconds lists its parts in a top-level
`SECTIONS = [fn, ...]` (its `run` runs them in order): check.py runs each part as its own task, so no module sets the wall time. The harness counts instructions per
emulated block and traps only the mocked and watched addresses, so `icount` is exact up to the part of a block a mock skips;
the same block hook enforces `Machine.call`'s step limit (`count=`), because Unicorn's own `emu_start(count=)`
hooks every instruction and made the suite about 6x slower.

Previews: `tools/preview*.py` write to `out/preview/` (gitignored). Generate the release sheet with
`venv/bin/python -I tools/preview.py WORKDIR`. Release packages and generated previews stay out of Git.

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
- Then `tools/check.py --tests-only` on a feature branch; at integration `tools/check.py`, and a changed package
  hash means a new tag and `--update` (below).
- **A UI bug starts with a reproducer**: a stock-code emulation test (`test/pod/`, `test/awtk_fill.py`) that fails, or a
  device screenshot (Customize > Developer > Screenshot, then `tools/pull_shots.py`; look with `tools/peek.py`). Previews
  (`tools/preview*.py`) must use the shared AWTK layout model where one exists (`awtk_text.py`, `awtk_ui.py`,
  `statusbar.py`) so they show what the device will; a bug found only on the device gets a test before the fix.

### Branches and integration

Feature branches never touch what two branches would both change: no `TAG` bump, no `test/golden.sha256`, no
`docs/history.md` edit, no README status line. Their done-criterion is `check.py --tests-only` (all tests pass)
plus the docs of the feature in `docs/modules/`. Only the **integration step** (merging into the release branch)
bumps `TAG` in `tools/build.py`, runs `check.py` and `check.py --update` (the second reuses the first: seconds),
commits `test/golden.sha256`, sets the README status line (one line naming the current release) and, only for a notable or accepted
release, adds a milestone line to `docs/history.md` (plus any new device finding or lesson there; per-tag details
are the commit message). A
branch that merged a golden or history conflict resolves it by taking the integration branch's file and
rerunning `--update`, never by editing hashes by hand.

### Helpers (instead of inline scripts and heredocs)

- `tools/sub.py FILE OLD NEW [--count N | --all]`: checked replace, fails if OLD is missing or ambiguous, prints the diff.
- `tools/peek.py crop|zoom|side|diff|bbox|runs|px IMG ...`: look at and measure PNG/JPG/BMP; writes `out/peek/`, prints the path.
- `tools/stock.py strings|syms|sym|addr|callers|ui|images|style ...`: search the stock tree (or `--tree`, the built one).
- `python3 -I tools/paths.py`: every resolved path, absolute.
- Shell shape (worktrees refuse otherwise): no `cat > f <<EOF` scripts (use the editor tool, or a helper above), no
  `VAR=value cmd` prefix (tools take flags: `check.py --no-cache`), no `cd X && cmd` (absolute paths, `git -C DIR ...`).

## 4. Flash

```
venv/bin/python -I tools/flash_sd.py out/M1Plus-<tag>-release-update.bin     # verified copy to the card as update.bin, eject
```

(`--dry-run`, `--no-eject`; by hand: copy to the card root as `update.bin`, compare md5, eject.) Use a
card that mounts fine on the player (exFAT or FAT32); the card's music is untouched. Card in with the
player off, power on, System settings, System Update, TF card update, confirm, leave the card in until
the player restarts by itself. The player does not delete `update.bin`; overwrite it with the next package.

First time only: flash the restore package. It reinstalls the stock kernel and rootfs byte for byte,
so it proves the package path with nothing new on the device.

Before flashing you may pre-place an empty file `m1plus-off` at the root of the SD card to keep the
payload disabled (the entry icon then behaves exactly as stock; the boot guard and row fit are off
too). Delete it to enable M1+ Music.

### Device checklist for the release

- boots to M1+ Music as the Home screen; About still reads V2.1; sleep, wake, reboot; "Shanling Home"
  row shows the stock grid, the "Boot to M1+ Music" switch changes the start-up setting and survives a reboot;
  Settings > Cover Flow > Landscape opens Cover Flow in that orientation, Sort (Artist / Album) orders Cover Flow and Albums
  and survives a reboot, Cover Flow opens on the playing album; Main Menu: the switches and up arrows change the
  menu (and Extras) on going back, survive a reboot, and Extras and Settings stay on the menu
- the Tidal icon on the stock grid opens M1+ Music (it is the hooked entry)
- menu rows (Now Playing, Cover Flow, Albums, Artists, Songs, Playlists, Shuffle, Extras, Settings) open their pages; Back returns; icons on every row; lists scroll, a drag does not open a row
- Cover Flow: first run builds the cache (Cancel works), covers swipe and flick, side tap glides, centre
  tap opens the stock album page (centred 160 px cover with rounded corners, year and track count, round Shuffle, Play all pill; check on
  the device that the pill is round with its play glyph left of the text, and the title row is empty; Play all starts the first
  track and Shuffle a random one in Shuffle mode, both open Now Playing, Back returns to the album page); a track plays from Now Playing; Back unwinds
- Albums list and Artists: the same album page; the queue (Now Playing list) title is 20 px, the playing row has the red disc
- Artists: names in stock order; an artist's Cover Flow with the All albums card; Back chain
- Shuffle Songs / Albums / Folders play and leave the stock play mode as documented in `docs/architecture.md`
- library pages (Songs, Albums, album, Playlists) show 64 px rows, one-line rows elsewhere
- Now Playing (V2.1mB, not yet seen on the device: the window takes the cover's colour within a second of a track change and goes
  neutral for a track without a cover; the 264 px cover is sharp with round corners that match the colour; the remaining time reads
  `-mm:ss` and counts down; the bar is 6 px and round; the A-B repeat markers sit under the bar; heart, More and the grabber work,
  a swipe on the art changes pages; with `m1plus-off` the page is square, black-grey and shows the total), lock screen (264 px cover on a translucent card, small battery gauge, play/next work,
  swipe from anywhere, nothing queued: date + clock only; Starry Night wallpaper by default), pull-down
  tiles and battery icon, boot logo, settings page slides
- language (V2.1mD): in System Settings > Language pick e.g. Russian, Japanese, German: the menu, Extras, Customize, Shuffle, Main Menu, Cover Flow, Artists and Albums pages, the album page buttons and count and the messages are in that language (open pages change on the spot); previews of the pages in other languages: `tools/preview_locales.py`; English again afterwards
- Screenshot (V2.1mT; the confirm dialog not yet seen on the device): Customize > Developer > Screenshot asks "Take a screenshot in 5 s?" (Cancel does nothing); OK, and a camera shows in the status bar (right of Wi-Fi, no overlap with the clock in 12 h and 24 h mode); leave the page, wait: the camera goes, a second later "Screenshot saved", and `screenshots/shot-0001.bmp` on the card is the screen you left it on, status bar included and without the camera; tapping the row again during the countdown asks "Cancel the screenshot?" (OK: the camera goes and nothing is saved; Cancel: the countdown goes on); with the card out, "Storage unavailable"; the picture's colours are right (if not, the driver's format differs from what the tests cover: see `docs/modules/screenshot.md`)
- list gestures (V2.1mV; any long list: Songs, Recently Added, the queue, Folders): a quick flick up and down never starts a song and the
  list flings as before; a slow drag scrolls and starts nothing; drag out and back to the start and release: nothing plays; a touch while
  the list is still coasting stops it and plays nothing (the same finger then drags it); a plain tap (also a long press, held still) still plays the row;
  Customize > Main Menu: the switches and arrows still work; Now Playing's lyrics: a tap right as a line scrolls may need a second tap
- the kill switch: `m1plus-off` on the card makes the entry icon open Tidal again

### Screenshots

To capture a real screen: Customize > Developer > Screenshot, OK, go to the page you want within 5 s,
wait for "Screenshot saved". The file is `/mnt/mmc/screenshots/shot-NNNN.bmp` (24 bit BMP, the whole 320 x 480 panel, next free number). Put
the card in the Mac and run `venv/bin/python -I tools/pull_shots.py` (reads `/Volumes/*/screenshots`, or give it the card's path):
the new files appear in `out/shots/` as PNG. The kill switch disables it like the rest of the payload. Details: `docs/modules/screenshot.md`.

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
