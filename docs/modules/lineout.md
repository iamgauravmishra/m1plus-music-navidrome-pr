# The Line Out pill (`patch/lineout.c`, `patch/lineout.h`, `test/pod/lineout.py`; hook 20 in [payload](payload.md))

**Behaviour.** While Line Out is on (stock's byte `0xa05aa7`), the status bar shows an amber pill with a black "LO" in place of stock's white "LO" text, and the same in the
pull-down's own bar copy. Always on: no setting. Everything else is stock: the volume glyph beside it, the volume number in PO mode, the pull-down's Output tile, and the "Line Out sets max volume" confirm.

**Stock.** `show_sysbar_face` (`0x544b48`, the status bar's 1 s timer) and `dropdown_showface` (`0x475c3c`, the pull-down's `view_sysbar`, its own timer) each show `label_volume` (`widget_set_visible(s7, 1)`,
`0x544d90` / `0x4758d8`), then fill a buffer with `strcpy("LO")` (`0x544f7c` / `0x475ac4`, when the byte is set) or `sprintf("%d", volume)`, and join at one call, `widget_set_text_utf8(label_volume, buffer)`
(`0x544f90` / `0x475ad8`). These are the only two "LO" sites.

**The hook.** Both `jalr` words become `jal lo_set_text` (`move a0, s7` stays in the delay slot, `a1` is the buffer). `lo_set_text` runs stock's function first, then finds the pill `pod_lo` among `label_volume`'s siblings
(`widget_lookup(parent, "pod_lo", 0)`, parent at `widget_t + 0x44`). If the text is exactly `LO` and `/mnt/mmc/m1plus-off` is absent, it hides the label and shows the pill (`visible` and `sensitive` both, as hidden widgets must be insensitive);
otherwise it shows the label and hides the pill. It runs in both timers right where stock sets the text and after stock's own show of the label in the same call, so there is no lag and no frame with both or neither (the UI thread paints between timer calls). With the kill
switch present, or no `pod_lo` in the bar (an asset from another build), stock's text stays. Cost: one `access` and one lookup in a small group per tick per bar, a few hundred instructions; no allocation, state or thread. Not on the boot path (`tools/reach.py`:
the same page-init dispatcher as the battery hook). Each site is pinned with its neighbours and the Line Out byte test (`LINEOUT_PINS` in `tools/pod.py`); a mismatch fails the build.

**The pill.** `pod_lo` is an `image` (30 px wide like `label_volume`, the 26 x 16 picture centred by `draw_type` center; hidden and insensitive in the file) right after `label_volume` in `view_bar_left`, added by `tools/statusbar.py` so the real bar and
`dropdown_dialog.bin` are identical (`test/pod/assets.py` compares them). The group's layouter skips an invisible child, so the pill takes the label's place at the same width and the digital-out glyph does not move. Image `pod_bar_lo` (`tools/mod_icons.py` `lo_pill`, committed PNG): amber `#FFD60A` fully rounded pill, black "LO" in Inter Medium 12 px with a 0.33 px stroke, 8x supersampled. It is not the Accent Orange `#FF9F0A`; the accent never tints it
(not in `ACCENT_*` or the glyph prefixes) and Light Mode's flip leaves it (it has colour). `tools/preview.py` writes `lineout.png` (bar off, bar on, the pull-down's bar on).

**Limits.** Device untested ([device checks](device-checks.md) LO-01). The pill is an asset swap, so the pull-down's bar shows it up to a second after Line Out changes, as stock's text did.
