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
| `test/cdefs.py` | Check the shared `#define` reader (`tools/cdefs.py`) and that it agrees with `harness.O` |
| `test/consts.py` | Check that Python asset-builder constants agree with their `offsets.inc` defines (the table in the C constants section) |
| `fwtool verify` / `diff` | Check package members, checksums and changes; packing also checks metadata and rootfs size |

Find feature cases in module notes and test sources; `check.py --list` lists runnable sections.
Keep assertion counts and exhaustive inventories out of docs: they go stale.

## C constants (tools/cdefs.py)

`defines(path, names=None, known=None, strings=False)` returns `{name: int}` for the integer `#define`s of a C file;
`parse(text, names, source, known, strings)` does the same for text. Continuations and `/* */` / `//` comments are
handled; values are integer expressions (literals with u/l suffixes, `+ - * / % << >> & | ~`, parentheses, earlier
names), evaluated by an ast walker, not `eval`. Function-like macros and non-integer defines are skipped; a name
passed in `names` that is not a define of the requested kind raises `CDefError` naming the file. `#if` branches are
not evaluated. `known={name: int}` seeds names the file's expressions use from elsewhere (not returned);
`strings=True` also returns a define that is one string literal (its text, no escapes decoded).

Tests write expected draw output as literals; C reads are for cross-checks only (a relation between two sources, such
as "fits within" or agreement), never the expected value of what the C code draws, which would pass if the constant changed.

Every reader of `#define`s in `tools/` and `test/` uses this module: `harness.O` and the `offsets.inc` readers,
`folders.c` (seeded with `POD_ROW_H`), the `search.h`, `pcdetail.h`, `keyboard.h`, `battery.h`, `lineout.h`,
`shot.h` readers, `vinyl.c` and `ipod_render.c` values, and the build's `stock.h` numbers (`BP_W2..4`,
`GOT_DEQUE_SIZE`). Left as they are, because they are not scalar `#define`s: `tools/preview_ipod.py` expands
`ipod_theme.c` macro bodies as text (`SCREEN_COLORS` and `SCREEN_REST` are comma lists), and `test/pod/textgamma.py`
reads the `TEXT_GAMMA_LUT` brace list. Tests that compare the generated header's text (`palette`, `queuepage`,
`search`) check text, not values.

`test/consts.py` (`make test TEST=consts`) is the agreement table for Python asset builders that copy a C constant:
each row is (module, Python name or expression, C define or expression over `offsets.inc`, `int` or `rgb`). It imports
the `tools/` module and fails with both file:lines and values when they differ. Rows the table knows to disagree sit in
`XFAIL` and print as MISMATCH without failing. `SKIPPED` lists the literals with no C twin or a different meaning, with
the reason. Add a row when a Python module-level number is meant to equal an offsets.inc define.

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
