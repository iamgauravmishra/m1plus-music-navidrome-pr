# Validation

Use `make test` for feature branches, `make dev` for a tested package and `make check` for
integration. Commands, receipts and golden acceptance are defined in [workflow](../workflow.md).

`make test` skips cost and stress-scale checks (instruction budgets, big-library and fuzz loops;
`PERF` in `test/pod/harness.py`, from `M1_PERF=1`); `PERF=1` runs them, and `make dev`, `check` and
`accept` always do, so receipts and goldens cover the full suite.

## Test boundaries

| Test | Evidence |
|---|---|
| `test/patch.py`, `test/pod/*.py` | Execute the compiled MIPS payload under Unicorn with stock calls/libc mocked; selected tests also run stock constructors, layout and pointer code |
| `test/pod/harness.py` | Verify final binary/source identity and ELF symbols; model widgets, stock services and watched memory. Counting is opt-in (`m.count()`); `icount` without counting errors. The block hook dominates emulation time; uncounted calls have no step limit but remain subject to check.py's test timeout |
| `test/coverflow.py` | Compile the renderer/cache helpers for the host; check geometry, compositing, sampling and filters |
| `test/demo_diff.py` | Limit stock-binary changes to the pinned edits, program header and appended payload |
| `test/awtk_fill.py` | Exercise stock fill, image-scaling and transparency code |
| `test/tools.py` | Check package validation, completion/golden gates, receipts, counters, locks, signals/timeouts and screenshot collisions |
| `fwtool verify` / `diff` | Check package members, checksums and changes; packing also checks metadata and rootfs size |

Find feature cases in module notes and test sources; `check.py --list` lists runnable sections.
Keep assertion counts and exhaustive inventories out of docs: they go stale.

## Required outcomes

Every task must finish; missing inputs/results, process errors, native signals and timeouts
fail. Logs and failed trees remain. Installation rechecks the dev receipt's recorded inputs, tree,
package and full test scope (not the current source or environment: a built package stays installable after later edits). Golden acceptance needs both packages and the full suite,
or matching retained evidence.

Emulation proves only the modelled paths. Playback, real frame timing, panel appearance and
hardware behaviour still need [device checks](device-checks.md). A preview is approximate;
a successful golden comparison proves byte identity, not hardware correctness.

## Harness performance

`test/pod/palette.py` counts instructions only on the machines of its cost checks.
