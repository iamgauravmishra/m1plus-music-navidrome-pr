# AGENTS.md

Firmware mods for the **Shanling M1 Plus** (Ingenic X2000, MIPS32r2 LE, Linux 5.10, AWTK UI app
`/release/bin/demo`, audio daemon `hciplayer`), built from the official V2.1 zip and packaged as a
TF-card `update.bin`. Read `README.md` first, then the doc for the area you touch. This file is rules
and pointers only; project state lives in the README and docs. No backwards compatibility: do not
keep flags, variants or code paths only to reproduce old packages.

## Setup, build, test, flash

```
brew install uv squashfs llvm lld
make setup                      # uv sync --locked, Python 3.15 in this checkout's .venv
make doctor                     # pinned inputs, native tools and Unicorn execution
make lint                       # Ruff bug checks on the Python (test, dev and check run it first)
make test                       # feature done-criterion: all tests, no package/golden
make test TEST=albums            # selected tests; uv run python -I tools/check.py --list lists them
make dev                        # fresh dev tag, full tests and a retained package; no tracked version edit
make preview                    # latest tested dev build (BUILD=out/dev/<tag> selects another)
make flash                      # verified SD copy of that tested package; on-device update stays manual
make check                      # integration: release + restore vs goldens, all tests
make accept                     # integration only; accepts complete matching results
uv run python -I tools/build.py --restore
uv run python -I tools/fwtool.py verify|diff|info ...
```

Guides: `docs/README.md` (index), `docs/install.md` (install/restore), `docs/guide.md` (user controls),
`docs/workflow.md` (development), `docs/architecture.md` and
`docs/ui.md` (indexes: one file per module in `docs/modules/`: read only the one you touch, plus
`payload.md` and `addresses.md` before searching the binary), `docs/history.md` (milestones, hardware
results, lessons), `docs/firmware.md` (firmware facts, space step).
The firmware zip goes in `firmware/` (SHA-256 pinned in `tools/build.py`); `tools/mod_font.py --fetch`
gets the Source Han Sans zip.

## Working rules

- Run builds and tests in the **foreground** (a build is seconds); never background and sleep-poll.
- **Context budget:** read the lines you need (`grep -n`, Read with offset/limit), not whole large
  files or `docs/history.md`; read an image once, cropped with `tools/peek.py`; batch mechanical edits
  with `tools/sub.py --pairs`. One topic per session: past ~250k context or on a topic change, write
  the result to its doc, then compact or start fresh. Subagents do one stage (probe, implement or
  test) and hand back branch, commit and doc. `docs/workflow.md`.
- C formatting: `make format`, then `make format-check`; `.clang-format` is the style definition.
- Python lint: `make lint` (Ruff, bug rules only; `make test` runs it). Do not run `ruff format`.
- `python -I` on anything that touches extracted firmware or downloads; never execute code from
  them or from the q2-pod clone (read and copy reviewed code).
- **Command shape** (worktrees refuse anything else): no heredoc scripts (`cat > f <<EOF`, `python - <<EOF`); no
  `VAR=value cmd` prefixes (tools take flags); no `cd X && ...` chains (absolute paths, `git -C DIR ...`); edit
  with the editor tool, and use the helpers instead of inline scripts: `tools/sub.py` (checked replace),
  `tools/peek.py` (crop/zoom/diff/bbox of images into `out/peek/`), `tools/stock.py` (search the stock tree).
  Stage with `git add <paths>`, never `-A`; never commit `venv/`.
- **UI bugs** start with a reproducer (a stock-code emulation test, or a device screenshot via Settings >
  Screenshot + `tools/pull_shots.py`); previews must use the shared AWTK layout model where one exists.
- **Python env:** use `uv run python -I` or the Makefile; `uv sync --locked` owns this checkout's
  `.venv`. Keep Python 3.15. Add dependencies to `pyproject.toml` and update `uv.lock`, not ad hoc.
- **Worktrees:** first run `make setup` to create the worktree's own environment. Never borrow
  another checkout's interpreter. The other
  gitignored inputs (firmware zip, `fonts/`, `work/stock`) resolve from the main checkout automatically
  (`tools/paths.py`; `uv run python -I tools/paths.py` shows what it found). No symlinks. `work/` and `out/` are per worktree; never write into the main checkout or another worktree.
- Builds are deterministic. `tools/check.py` compares both packages to `test/golden.sha256`; a CHANGED
  package you did not mean to touch is a bug.

## Version tags

Format `V2.1` + lowercase series + capital letters. The updater refuses a package whose version
equals the installed one, so each flashed package needs a new tag.

`make dev` reserves series `z`: four checkout-namespace letters plus four local counter letters.
Keep `.dev-number.json` (gitignored); do not reset it or reuse a dev output directory. It never
changes `TAG`. Dev artifacts and test receipts stay together under `out/dev/<tag>`.

**Feature branches do not bump `TAG`, update `test/golden.sha256` or edit `docs/history.md`** (every
branch doing so conflicts on merge). Their done-criterion is `check.py --tests-only`
(all tests pass) and the feature's docs in `docs/modules/`. Only the **integration step** (merge into the
release branch) bumps `TAG` in `tools/build.py` (the one source; `check.py` and `preview.py` read it),
runs `check.py` then `check.py --update` and commits the golden. The README names no release (the
release is `TAG`, its changes the squash commit). `docs/history.md` is not a per-tag log (git is): add a milestone line only for a
notable or accepted release, and any new device finding or lesson. A golden or history conflict is resolved by taking the integration side and rerunning, not by hand.

## Safety rules (do not relax)

- Only kernel and rootfs are flashed; bootloader and recovery kernel are never written. The recovery
  button combo is unverified, so a boot loop is the worst case. `docs/workflow.md`.
- Boot-path code is the boot guard only (`patch/home.c`, behind a crash marker); one more hook on the
  Home icon tap handler (the M1+ Music icon, plus the Tidal-icon recovery fallback while the bad note exists), one on Now Playing's init (a page-scoped timer, and the cover widget's own after-paint for its corners), one on the More dialog's init (arranges its rows once, then only on a tap on its More row or back header, and when another dialog covers it), one in stock's tag reader (get_id3info's strcpy of the parsed path at 0x4dff4c: stock's copy, then podcast tags only for a path under /mnt/mmc/Podcasts/; reachable at boot by Memory Playback), one in the stock library scan's folder walk (the strcmp(name, ".") at 0x5ea6a8: skips dot-folders; not on the boot path), one on each of stock's two database query functions (toolsQueryDbTable 0x5ee77c and toolsQueryDbTableAndSort 0x5ee9ac: a select from songtable gets a subquery without /mnt/mmc/Podcasts/ paths, any other statement passes untouched; reachable at boot by Memory Playback), and the empty on_event_before_children slot of `g_scroll_view_vtable` (touches in a list); nothing else at paint or in the main loop. The guard's ready path also points the font at the UI language's CJK cmap (`patch/fontregion.c`: one font field and a glyph-cache shrink; again from one timer after a language or theme change). The SD file `/mnt/mmc/m1plus-off`
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
binary; `tools/stock.py` wraps the common searches (strings, symbols, ui trees, images). Helpers: `tools/disasm.py sym|addr|xref|strxref|callers|strings-xref|full ELF ...` (`full` caches
the annotated disassembly in `work/cache/`, keyed by SHA-256), `tools/elfinfo.py`, `tools/awtk_ui.py`,
`tools/reach.py` (boot-path reachability of pinned edits).

## Preferences

- q2-pod (github.com/DiamondBond/q2-pod) is acknowledged in the README. Preserve any file-specific attribution when borrowing code; clone it outside the repo.
- No Bluetooth work. `hciplayer` patching is deferred.
