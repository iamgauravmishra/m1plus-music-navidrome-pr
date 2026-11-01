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
First-time package-path validation should use the stock restore package.

## Update

Repeat with a new verified package. Developers use `make dev` for a fresh tag; integration
assigns release tags. Confirm the update manually on the player.

## Disable M1+ Music

Create an empty `m1plus-off` file at the card root. Remove it to enable the payload again.
The boot guard also falls back to stock Home after a failed custom startup.

## Restore stock

Build the `V2.1R` restore package using the [development guide](workflow.md#integration-and-restore),
then install it through the same TF-card menu. It carries the untouched stock kernel and rootfs
with a different package tag; official V2.1 can be refused by the menu's version check.

Do not assume the Q2's recovery buttons work on the M1 Plus. See [firmware facts](firmware.md)
and [boot-guard recovery](modules/home-guard.md#recovery) before investigating a boot failure.
