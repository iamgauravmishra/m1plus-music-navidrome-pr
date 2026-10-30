# Validation

Use `make test` for feature branches, `make dev` for a tested package and `make check` for
integration. Commands, receipts and golden acceptance are defined in [workflow](../workflow.md).

## Test boundaries

| Test | Evidence |
|---|---|
| `test/patch.py`, `test/pod/*.py` | Execute the compiled MIPS payload under Unicorn with stock calls/libc mocked; selected tests also run stock constructors, layout and pointer code |
| `test/pod/harness.py` | Load the final binary and ELF symbols; reject stale or changed source/binary identities; model widgets, stock services and watched memory. Instruction counting is opt-in (`m.count()` before a measured call; `icount` on a machine that does not count is an error): its block hook is most of the emulation time, and an uncounted call has no step limit (a runaway ends at check.py's per-test timeout) |
| `test/coverflow.py` | Compile the renderer/cache helpers for the host; check geometry, compositing, sampling and filters |
| `test/demo_diff.py` | Limit stock-binary changes to the pinned edits, program header and appended payload |
| `test/awtk_fill.py` | Exercise stock fill, image-scaling and transparency code |
| `test/tools.py` | Check package validation, completion/golden gates, receipts, counters, locks, signals/timeouts and screenshot collisions |
| `fwtool verify` / `diff` | Check package members, checksums and changes; packing also checks metadata and rootfs size |

Feature-specific cases live beside their implementation notes and in the test sources. Use
`check.py --list` to discover modules and independently runnable sections. Avoid copying assertion
counts or exhaustive test inventories into docs; they go stale as the suite changes.

## Required outcomes

Every expected task must finish. Missing inputs/results, process errors, native signals and
timeouts fail validation. Logs and failed trees are retained. A dev receipt identifies the
exact source/environment, tree, package and full test scope; installation checks it again.
Golden acceptance requires both packages and the complete suite, or matching retained evidence.

Emulation proves only the modelled paths. Playback, real frame timing, panel appearance and
hardware behaviour still need [device checks](device-checks.md). A preview is approximate;
a successful golden comparison proves byte identity, not hardware correctness.
