# Build, test and flash

Run `make help` for common tasks. Direct tools use `uv run python -I tools/<name>.py`.

## Setup

```sh
brew install uv squashfs llvm lld
make setup
cp "M1 Plus Firmware V2.1.zip" firmware/
uv run python -I tools/mod_font.py --fetch
make doctor
```

uv owns each checkout's `.venv` and locked dependencies. Change `pyproject.toml` and regenerate
`uv.lock` when updating dependencies. Builds require Python 3.15 and Homebrew LLVM/LLD; Apple
clang lacks MIPS support. `LLVM_BIN` and `LLD_BIN` override toolchain locations.

Each worktree runs `make setup`. Firmware, fonts and a matching stock tree may be read from
the main checkout; outputs, caches and counters stay local. `tools/paths.py` resolves data only;
run it to inspect paths. Never execute code from extracted firmware or a reference clone.
Keep `-I` on Python tools.

`make doctor` checks pinned inputs, native tools and Unicorn MIPS execution. SIGILL can indicate
that a sandbox prohibits native JIT. Use an environment that permits Unicorn; failures report
their signal and log path without silently retrying or escalating.

## Development

```sh
make test TEST=albums           # selected tests; comma-separated modules or module/section
make test                      # feature-branch done criterion; no package or goldens
make dev                       # fresh dev tag, one tree, full tests and verified package
make preview                   # approximate render of that dev tree
make flash                     # verified SD copy, then eject
```

Dev artifacts stay in `out/dev/<tag>/`: `tree/`, `update.bin`, logs and `results.json`.
`tree/build.json` records the tag, inputs, environment and artifact hashes. Tests and packaging
use the same tree; About, iPod About, the preview and package use its tag.

Only a fully passing build becomes `latest`. `make flash` verifies its full test receipt,
package, target card and read-back hash. It never rebuilds. A failed dev run leaves the previous
latest selected; check the printed tag, or choose `BUILD=out/dev/<tag>` explicitly. Use
`VOLUME=/Volumes/Name` for another card and `DRY_RUN=1` to check without copying or ejecting.

Dev tags reserve `V2.1z` plus four checkout-namespace letters and four counter letters. Keep
the gitignored `.dev-number.json`; never reset the counter or reuse an output directory.
Namespace collisions, moved worktrees and exhausted counters fail explicitly. Releases use `V2.1-<VERSION>` tags. No shared checkout state is written.

```sh
uv run python -I tools/check.py --list
uv run python -I tools/check.py --test albums/toggle_tests
uv run python -I tools/check.py --tests-only --jobs 4 --timeout 300
```

`JOBS=4` also works with Makefile test/build targets. The runner prints failures and one summary
line (`--verbose` prints every pass too); it reports completed tasks, native crashes and assertion
totals separately. Missing inputs/results fail; subprocess groups have
wall-time limits. Logs and failed trees are retained. `make clean` removes `work/check` only,
keeping dev artifacts, counters and caches. Locks prevent overlapping writes.

## CI

`.github/workflows/ci.yml` runs only when started (Actions > ci > Run workflow, or
`gh workflow run ci --repo imfing/m1plus-music`): macOS runners cost 10x. One `macos-latest` job
mirrors local use: Homebrew `llvm lld squashfs librsvg`, the stock firmware zip, `make setup`,
Source Han Sans, `make doctor`, `make format-check`, `make dev` (lint, all tests and a verified dev package;
the dev counter is seeded from the run number, so each run gets a new `V2.1z...` tag). The run's
artifact is that `update.bin` (14 days). It checks no golden and publishes nothing; releases stay
local (`make check`, `make publish`). Linux cannot reproduce the goldens: Pillow's Linux wheel has zlib, not zlib-ng, so the
built PNGs differ in bytes, and so does the merged CJK font. Tests compare generated PNGs by pixels.

The firmware zip is the asset of a private prerelease (tag `m1plus-firmware-v2.1`) in this
repository, downloaded with `GITHUB_TOKEN`. The repository must never be made public while that
release exists.

Start UI fixes with a failing emulation test or device capture. Previews use the shared AWTK
layout/text model and the built font. Keep feature details and device checks in `docs/modules/`.

Previews: `tools/preview*.py` write to `out/preview/` (gitignored). Generate the release sheet with
`uv run python -I tools/preview.py WORKDIR`. Release packages and generated previews stay out of Git.

## Context budget

An audit of one week (2026-10-25 to 11-01) found almost every token was a cache read: each turn
sends the whole context again, so cost is turns times context size. Turns above 400k context were
a fifth of the turns and 45% of the reads, and subagents were 72% of all reads (300 to 500 turn
feature agents reaching 900k). Hence:

- One stage per subagent (probe, implement, test). It ends with a short handoff (branch, commit,
  doc updated) and the next stage starts fresh from that, not from the transcript.
- One topic per session. Past ~250k context, or when the topic changes, write the conclusion to
  the module doc, then compact or start a new session. Close sessions that are not in use.
- Large files (`test/pod/harness.py`, `tools/pod_ui.py`, `docs/modules/podcasts.md`,
  `patch/coverflow.c`, `docs/architecture.md`, `docs/ui.md`): `grep -n` first, then Read the range.
  Do not re-read a file you have not changed. `docs/history.md` is for people, not agents.
- Images stay in context for every later turn: crop or zoom with `tools/peek.py` and read the
  result once; do not re-read an unchanged preview.
- Mechanical edits across files: one `tools/sub.py FILE... --pairs PAIRS.json --stat` call, not a
  `sed -i` per change. Tests: `make test TEST=...` while iterating, the full suite once at the end.

## C formatting

`make format` runs clang-format on tracked payload `.c` and `.h` files; `make format-check`
checks without edits. `.clang-format` keeps four-space indentation, attached braces and a
120-column limit. Includes stay in their original order; comments are not reflowed.
Homebrew LLVM supplies the formatter. `LLVM_BIN` or `CLANG_FORMAT` can select another binary.
Keep formatting separate from functional changes and verify the package hashes afterward.

## Python lint

`make lint` runs Ruff (pinned in the `dev` group of `pyproject.toml`) with the pyflakes rules and
syntax errors only: unused imports and variables, undefined names, redefinitions. `make test`,
`make dev` and `make check` run it first. Ruff does not format the Python; the compact style stays.
`test/pod/*.py` and `tools/preview_tape.py` star-import their helpers, so the star-import rules are
off there, and `test/pod/harness.py` may import names only to re-export them to the tests.

## Integration and restore

Feature branches leave release `VERSION`, goldens and history unchanged. The README names no release.
At integration, bump `VERSION` in `tools/build.py` (semantic: patch for fixes, minor for features, major by decision;
`TAG = V2.1-<VERSION>` is the package version the updater compares, About shows the plain `VERSION`; dev tags stay `V2.1z...`), then run:

```sh
make check                     # both packages and all tests against existing goldens
make accept                    # accept intended changes; reuse complete matching evidence
```

CHANGED and NEW fail until accepted. Acceptance requires both packages and every test;
`--no-tests` and `--only` cannot bypass it. Reuse validates inputs, test coverage and package
hashes. Source changes during a run invalidate its evidence. Commit the golden and README
status; add history only for milestones or device findings. Resolve golden/history conflicts
from the integration side and rerun.

Checked packages stay in `work/check/release/out` and `work/check/restore/out`. Direct builds
retain the established `out/M1Plus-<tag>-release-update.bin` naming:

```sh
uv run python -I tools/build.py
uv run python -I tools/build.py --restore
uv run python -I tools/fwtool.py verify out/M1Plus-<tag>-release-update.bin
uv run python -I tools/flash_sd.py out/M1Plus-<tag>-release-update.bin
```

Release/restore copies require golden bytes; dev copies require a full receipt. There is no
`--force` bypass. `build.py --dev` alone creates no test receipt; use `make dev` for installation.
`--pack-only` rejects stale trees. Payload edits retain the font/base cache; `--no-cache`
supports cold-build comparisons.

## Publish

After the integration commit and a matching `make check`, `make publish` uploads the golden release
package (as `update.bin`, with `SHA256SUMS`) to a draft GitHub release named `VERSION` (for example `1.0.0`) created with
`--target HEAD`, notes = the golden's last commit message; it downloads the assets back and compares
hashes. It creates and pushes no tag (q2-pod's model): GitHub creates the tag `VERSION` at HEAD when the draft
is published. Review the draft, then `make publish PUBLISH=1` (or publish it on GitHub). `DRY_RUN=1`
checks and stages `out/publish/<VERSION>/` only. It refuses a dirty tree, a package that is not the
golden, a local tag on another commit and an already published release. The restore image stays local.

## Device checks

Follow [Install](install.md) for card preparation, update confirmation and restore. Use
[device checks](modules/device-checks.md) and the feature's module doc to validate a build. Record the tag,
pass/fail/untested status and captures. Emulation does not certify hardware timing or appearance.

**Settings → Developer → Screenshot** asks first, then captures after five seconds.
See [capture details](modules/screenshot.md). With the card mounted:

```sh
uv run python -I tools/pull_shots.py --build latest
uv run python -I tools/peek.py info out/dev/<tag>/device/<capture>.png
```

Content hashes prevent filename collisions; sidecars record capture/build identity. Remote
screenshots, logs, input and update navigation remain future hardware-validated work.
