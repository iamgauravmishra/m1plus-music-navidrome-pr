# Install and update

You need a Shanling M1 Plus, a working TF/microSD card and a verified M1 Plus package.
This repository builds packages from the official V2.1 zip; see the [development guide](workflow.md).

Only kernel and rootfs are updated. The bootloader and recovery kernel stay unchanged, but the
M1 Plus recovery button combination remains unverified. Keep the battery charged and leave
the card inserted until the update finishes.

## Install

1. Back up the card and shut down the player before removing it.
2. Copy the verified package to the card root as `update.bin`. For a tested dev build, `make flash`
   performs the copy, read-back verification and eject; see [development](workflow.md#development).
3. Insert the card with the player off, then turn it on.
4. Open **System settings → System Update → TF card update** and confirm.
5. Wait for the player to restart. Check the **M1+ Music** tag in About, below stock V2.1.

Music stays on the card. Overwrite the retained `update.bin` for the next update.
First-time package-path validation should use a restore package (official V2.1 or `V2.1R`).

## Update

Repeat with a new verified package. Developers use `make dev` for a fresh tag; integration
assigns release tags. Confirm the update manually on the player.

## Disable M1+ Music

Create an empty `m1plus-off` file at the card root. Remove it to enable the payload again.
The boot guard also falls back to stock Home after a failed custom startup.

## Restore stock

Download Shanling's official M1 Plus firmware from Shanling's download page, copy its `update.bin`
to the card root and install it through the same TF-card menu (steps above). The updater accepts it
over the mod (`modules/version.md`). Developers can also build the `V2.1R` stock-image package
([development guide](workflow.md#integration-and-restore)).

Do not assume the Q2's recovery buttons work on the M1 Plus. See [firmware facts](firmware.md)
and [boot-guard recovery](modules/home-guard.md#recovery) before investigating a boot failure.
