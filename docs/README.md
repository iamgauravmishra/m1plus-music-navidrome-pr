# Documentation

## Guides

| Guide | Use it for |
|---|---|
| [Install](install.md) | Prepare the card, update the player, disable the mod or restore stock |
| [User guide](guide.md) | Browse music, control playback and customize the interface |
| [Development](workflow.md) | Set up uv, build, test, format and prepare releases |

## References

| Reference | Contents |
|---|---|
| [Architecture](architecture.md) | Payload, build pipeline, hooks and feature source maps |
| [UI](ui.md) | Preview, layout rules, fonts, assets and rendering |
| [Firmware](firmware.md) | Stock hashes, updater behaviour, partitions and space recovery |
| [Device checks](modules/device-checks.md) | Hardware validation checklist |
| [History](history.md) | Recorded milestones, device findings and lessons |

Module documents under `modules/` hold implementation details, pins and test evidence. Read the
relevant module before changing a feature. Read [payload](modules/payload.md) and
[addresses](modules/addresses.md) before searching the stock binary.

## Source layout

| Directory | Contents |
|---|---|
| `tools/` | Host build, validation, assets, previews and binary analysis |
| `patch/` | Runtime C payload, stock offsets and linker script |
| `test/` | MIPS/host tests and package goldens |
| `assets/` | Fonts, icon sources, boot logo and wallpaper |

Module notes retain technical evidence and historical experiments. Current pin/source lists
are defined in `tools/pod.py`; current artifact sizes are in build manifests. A device result
applies to its recorded build, not automatically to later releases.
