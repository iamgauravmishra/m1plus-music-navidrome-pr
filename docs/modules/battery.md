# The battery art

Split out of docs/ui.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

### One battery (`tools/battery_art.py`, `tools/mod_battery.py`, lock screen step)

The app swaps `img_battery`'s image between `bar_power`, `bar_charge` (charging) and `bar_lowpower`
(capacity 0 only, `bgtz` `0x475c94`) and feeds `pgbar_battery` the capacity (100 when charge is done),
in the status bar and in the pull-down's own bar (`dropdown_showface` `0x475c3c`, twin `0x545168`); the
fill is drawn under the image (stock child order). So the image is the outline and the fill lands inside.
**No number anywhere:** `get_battery_capacity` (`0x4e6dd8`) buckets the battery voltage
(`toolsGetBatteryVoltage` `0x5e35b0`) at 3.535 / 3.595 / 3.705 / 3.865 / 3.995 V into 0/20/40/60/80/100
(another table while charging, `0x4e6f58`), so a percentage only ever read those six values. One drawing,
two sizes: 1.5 px outline (the status-icon stroke), rounded body corners, a 2 px rounded nub, 8x
supersampled and box-reduced, written as a plain zlib PNG (bytes independent of Pillow). Normal: white
outline, the level is the white fill; charging: green `#34C759` outline and bolt with a 0.5 px black
keyline; low: red `#FF1448` outline. Status bar (`STATUS`): image 18x11 at (292,10), body 16x11, fill
12x7 at (294,12) (0.5 px gap), right edge at x 310 as stock, the right icon group ending 4 px before it
(x 187); the same in both `dropdown_dialog.bin` themes. Lock screen (`LOCK`): 34x12, body 22x12 at x 9,
fill 16x6 at (12,3), for `screens_battery/charge/lowbattery`. `fill_gap` asserts the fill stays inside
the outline; `tools/preview_battery.py` draws empty/half/full/charging/low from the tree's files.
Research note: this board's battery is an X-Powers AXP2101 PMIC (kernel `axp2101_charger`); stock demo
reads `/sys/class/power_supply/battery/voltage_now` (its CW2015 gauge code is dead from another model),
so `/sys/class/power_supply/*/capacity` very likely exists for a future honest percentage; nothing
depends on it.
