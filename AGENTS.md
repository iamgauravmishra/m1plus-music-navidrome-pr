# AGENTS.md

Firmware mods for the Shanling M1 Plus, built from official V2.1 and packaged as a TF-card
`update.bin`. Read [README](README.md), then the relevant reference below.

## Required references

| Work | Read |
|---|---|
| Setup, commands, worktrees, formatting, releases | [Development workflow](docs/workflow.md) |
| Runtime changes and safety boundaries | [Payload safety](docs/modules/safety.md), [architecture](docs/architecture.md) |
| Binary searches or patches | [Payload](docs/modules/payload.md), [pinned addresses](docs/modules/addresses.md) |
| UI changes | [UI reference](docs/ui.md), [UI rules](docs/modules/ui-rules.md), the feature's module |
| Testing and hardware evidence | [Validation](docs/modules/validation.md), [device checks](docs/modules/device-checks.md) |
| Installation, restore and firmware facts | [Install](docs/install.md), [firmware](docs/firmware.md) |

The [documentation index](docs/README.md) lists the remaining guides.
Read relevant ranges; avoid loading entire large files or history.

## Working rules

- Follow the linked workflow and safety rules before editing. Run builds/tests in the
  foreground. Use this checkout's uv environment and `python -I`; never execute extracted
  firmware or reference-clone code.
- UI fixes require a reproducer. Use the shared layout/text model and built font for previews.
- Pin every binary edit and fail on mismatch; hooks must fall back to stock.
- Never expand the approved global paint or main-loop scope (paint: only the palette's three hooks,
  `docs/modules/accent.md`). Pinned boot-reachable hooks that fall back to stock and do bounded work are a paved path ([safety](docs/modules/safety.md)). Preserve the crash guard and
  `/mnt/mmc/m1plus-off` kill switch. Never write bootloader or recovery kernel;
  rebuilt rootfs must fit within stock size.
- Preserve widget names. Hidden widgets must also be insensitive.
- Feature branches leave `VERSION`, goldens and history unchanged; release integration owns
  their updates. Never reset dev counters or reuse dev output directories.
- Keep module docs factual and concise: behavior, interfaces, constraints, source references
  and validation limits. Consolidate repeated facts; omit roadmaps and implementation phases.
  History holds only milestones, device findings and lessons.
- No compatibility flags or code paths solely for old packages. No Bluetooth work.
  `hciplayer` is patched for the parametric EQ only (`tools/mod_player.py`,
  [peq](docs/modules/peq.md)); any other `hciplayer` change needs a decision first.
- Preserve borrowed-code attribution, including q2-pod's README acknowledgement.
  Clone references outside this repository.
