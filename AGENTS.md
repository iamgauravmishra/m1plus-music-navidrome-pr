# AGENTS.md

Firmware mods for the **Shanling M1 Plus** (Ingenic X2000, MIPS32r2 LE, Linux 5.10, AWTK UI app
`/release/bin/demo`, audio daemon `hciplayer`), built from the official V2.1 zip and packaged as a
TF-card `update.bin`. Read `README.md` first, then the doc for the area you touch. This file is rules
and pointers only; project state lives in the README and docs. No backwards compatibility: do not
keep flags, variants or code paths only to reproduce old packages.

## Setup, build, test, flash

```
python3 -m venv venv && venv/bin/pip install -r requirements.txt ; brew install squashfs llvm lld
venv/bin/python -I tools/build.py                 # the release -> out/M1Plus-<tag>-release-update.bin  (--restore: stock)
venv/bin/python -I tools/check.py --tests-only    # DONE-CRITERION of a feature branch: all tests, no package/golden (~40 s)
venv/bin/python -I tools/check.py --test albums   # selected tests only (see check.py --help)
venv/bin/python -I tools/check.py                 # DONE-CRITERION at integration: release + restore vs test/golden.sha256, all tests
venv/bin/python -I tools/check.py --update        # integration only, hash change intended; reuses the passing run just before it
venv/bin/python -I tools/fwtool.py verify|diff|info ...   # package inspection
venv/bin/python -I tools/flash_sd.py out/<package>.bin    # verified copy to the card, eject (--dry-run, --no-eject)
```

Details: `docs/workflow.md` (build, test, flash, device checklist), `docs/architecture.md` and
`docs/ui.md` (indexes: one file per module in `docs/modules/`: read only the one you touch, plus
`payload.md` and `addresses.md` before searching the binary), `docs/history.md` (tags, hardware
results, lessons), `docs/firmware.md` (firmware facts, space step).
The firmware zip goes in `firmware/` (SHA-256 pinned in `tools/build.py`); `tools/mod_font.py --fetch`
gets the Source Han Sans zip.

## Working rules

- Run builds and tests in the **foreground** (a build is seconds); never background and sleep-poll.
- `python -I` on anything that touches extracted firmware or downloads; never execute code from
  them or from the q2-pod clone (read and copy reviewed code).
- **Command shape** (worktrees refuse anything else): no heredoc scripts (`cat > f <<EOF`, `python - <<EOF`); no
  `VAR=value cmd` prefixes (tools take flags); no `cd X && ...` chains (absolute paths, `git -C DIR ...`); edit
  with the editor tool, and use the helpers instead of inline scripts: `tools/sub.py` (checked replace),
  `tools/peek.py` (crop/zoom/diff/bbox of images into `out/peek/`), `tools/stock.py` (search the stock tree).
  Stage with `git add <paths>`, never `-A`; never commit `venv/`.
- **UI bugs** start with a reproducer (a stock-code emulation test, or a device screenshot via Settings >
  Screenshot + `tools/pull_shots.py`); previews must use the shared AWTK layout model where one exists.
- **Worktrees:** gitignored inputs (firmware zip, `venv/`, `fonts/`, `work/stock`) resolve from the
  main checkout automatically (`tools/paths.py`; `python3 -I tools/paths.py` shows what it found).
  No symlinks. `work/` and `out/` are per worktree; never write into the main checkout or another worktree.
- Builds are deterministic. `tools/check.py` compares both packages to `test/golden.sha256`; a CHANGED
  package you did not mean to touch is a bug.

## Version tags

Format `V2.1` + lowercase series + capital letters. The updater refuses a package whose version
equals the installed one, so each flashed package needs a new tag.

**Feature branches do not bump `TAG`, update `test/golden.sha256`, edit `docs/history.md` or the README
status line** (every branch doing so conflicts on merge). Their done-criterion is `check.py --tests-only`
(all tests pass) and the feature's docs in `docs/modules/`. Only the **integration step** (merge into the
release branch) bumps `TAG` in `tools/build.py` (the one source; `check.py` and `preview.py` read it),
runs `check.py` then `check.py --update`, commits the golden, adds one `docs/history.md` row and the
README status. A golden or history conflict is resolved by taking the integration side and rerunning, not by hand.

## Safety rules (do not relax)

- Only kernel and rootfs are flashed; bootloader and recovery kernel are never written. The recovery
  button combo is unverified, so a boot loop is the worst case. `docs/workflow.md`.
- Boot-path code is the boot guard only (`patch/home.c`, behind a crash marker); one more hook on the
  Home icon tap handler (the M1+ Pod icon, plus the Tidal-icon recovery fallback while the bad note exists), one on the album page's header builder (runs only while that page builds; it gives that page's cover a paint hook for its corners and one page-scoped timer for the cover tint, and the page's window events that tint the status bar), one on Now Playing's init (a page-scoped timer, and the cover widget's own after-paint for its corners), one on the More dialog's init (arranges its rows once, then only on a tap on its More row or back header, and when another dialog covers it), and the empty on_event_before_children slot of `g_scroll_view_vtable` (touches in a list); nothing else at paint or in the main loop. The SD file `/mnt/mmc/m1pod-off`
  disables the payload. `docs/architecture.md`.
- Pin every patched word and stock address; refuse to build on mismatch; every hook falls back to stock.
- Never rename or delete a widget the app looks up by name; restyle, move or hide it.
- `visible=false` does not stop hit-testing: hide = `visible=false` + `sensitive=false`; decorative
  overlays must be insensitive. `docs/ui.md`.
- Normal windows are 450 px tall (fullscreen 480); lists use stock `list_view` > `scroll_view` with
  stock `list_item` rows. `docs/ui.md`.
- Text width = truncated glyph advance + 1 px per glyph; use `StbText` (`tools/awtk_text.py`) and
  measure the font of the tree being built. `docs/ui.md`.
- The rebuilt rootfs must not exceed stock size (fwtool enforces it).

## Reverse engineering

Read `docs/modules/addresses.md` (known addresses, pinned functions and offsets) before searching the
binary; `tools/stock.py` wraps the common searches (strings, symbols, ui trees, images). Helpers: `tools/dis.py sym|addr|xref|strxref|callers|strings-xref|full ELF ...` (`full` caches
the annotated disassembly in `work/cache/`, keyed by SHA-256), `tools/elfinfo.py`, `tools/awtk_ui.py`,
`tools/reach.py` (boot-path reachability of pinned edits).

## Preferences

- Borrow from q2-pod (github.com/DiamondBond/q2-pod, MIT) with attribution in `NOTICE`; clone it outside the repo.
- No Bluetooth work. `hciplayer` patching is deferred.
