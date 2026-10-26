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
venv/bin/python -I tools/check.py                 # DONE-CRITERION: release + restore vs test/golden.sha256, all tests (~1 min)
venv/bin/python -I tools/check.py --only release --keep   # quick loop (also --no-tests)
venv/bin/python -I tools/check.py --update        # only when a hash change is intended; commit test/golden.sha256
venv/bin/python -I tools/fwtool.py verify|diff|info ...   # package inspection
venv/bin/python -I tools/flash_sd.py out/<package>.bin    # verified copy to the card, eject (--dry-run, --no-eject)
```

Details: `docs/workflow.md` (build, test, flash, device checklist), `docs/architecture.md` (pipeline,
payload, hooks, guard, known addresses), `docs/ui.md` (looks, lock screen, rows, album page),
`docs/history.md` (tags, hardware results, lessons), `docs/firmware.md` (firmware facts, space step).
The firmware zip goes in `firmware/` (SHA-256 pinned in `tools/build.py`); `tools/mod_font.py --fetch`
gets the Source Han Sans zip.

## Working rules

- Run builds and tests in the **foreground** (a build is seconds); never background and sleep-poll.
- `python -I` on anything that touches extracted firmware or downloads; never execute code from
  them or from the q2-pod clone (read and copy reviewed code).
- Edit with the editor tool, not shell heredocs; keep shell commands plain (no `cd X && ...`
  chains, they are refused in worktrees). Stage with `git add <paths>`, never `-A`; never commit `venv/`.
- **Worktrees:** gitignored inputs (firmware zip, `venv/`, `fonts/`, `work/stock`) resolve from the
  main checkout automatically (`tools/paths.py`; `python3 -I tools/paths.py` shows what it found).
  No symlinks. `work/` and `out/` are per worktree; never write into the main checkout or another worktree.
- Builds are deterministic. `tools/check.py` compares both packages to `test/golden.sha256`; a CHANGED
  package you did not mean to touch is a bug.

## Version tags

Format `V2.1` + lowercase series + capital letters. The updater refuses a package whose version
equals the installed one, so each flashed package needs a new tag: bump `TAG` in `tools/build.py`,
update `test/golden.sha256` (`check.py --update`) and add a line to `docs/history.md`.

## Safety rules (do not relax)

- Only kernel and rootfs are flashed; bootloader and recovery kernel are never written. The recovery
  button combo is unverified, so a boot loop is the worst case. `docs/workflow.md`.
- Boot-path code is the boot guard only (`patch/home.c`, behind a crash marker); one more hook on the
  Home icon tap handler (the M1 Pod icon, plus the Tidal-icon recovery fallback while the bad note exists), and one on the album page's header builder (runs only while that page builds); nothing at paint or in the main loop. The SD file `/mnt/mmc/m1pod-off`
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

Read `docs/architecture.md` (known addresses, pinned functions and offsets) before searching the
binary. Helpers: `tools/dis.py sym|addr|xref|strxref|callers|strings-xref|full ELF ...` (`full` caches
the annotated disassembly in `work/cache/`, keyed by SHA-256), `tools/elfinfo.py`, `tools/awtk_ui.py`,
`tools/reach.py` (boot-path reachability of pinned edits).

## Preferences

- Borrow from q2-pod (github.com/DiamondBond/q2-pod, MIT) with attribution in `NOTICE`; clone it outside the repo.
- No Bluetooth work. `hciplayer` patching is deferred.
