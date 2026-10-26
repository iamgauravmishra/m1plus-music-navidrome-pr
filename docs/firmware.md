# Shanling M1 Plus V2.1 firmware notes

Stock pins (SHA-256):

```
db7bdbc42ffe6d5c1e3fdca9363edb78a01898b9a725c34793394cf6abfa33c0  M1 Plus Firmware V2.1.zip
1ccb4667e3e9bdf9a35be4dc58d09b898ca53c5fd58396b7667fb91fe895f925  update.bin
3b326f04f20690af82fd7b2d3d61f9d01478c75081f30e99973a4e11b58fbcd8  recovery-update/xImage
8794ca4bbbf0ee70b4c23ca6ade589cf61d7213170164d9dc9e6aedb96be0db1  recovery-update/rootfs.squashfs
```

## 1. Is it moddable? Yes, and it is the same stack as the Q2

| | Shanling M1 Plus V2.1 | Shanling Q2 (q2-pod base V1.32) |
|---|---|---|
| SoC / arch | Ingenic X2000, MIPS32r2 LE | same |
| Kernel | Linux 5.10.21+ uImage (xImage), 5,410,880 bytes | same version, same size |
| Userland | Buildroot 2020.02.1, glibc, BusyBox, AWTK UI | same |
| Main app | `/release/bin/demo` (AWTK, dynamic symbols kept, spare PT_NULL phdr) | same layout, different build |
| Audio daemon | `/usr/bin/hciplayer` | same |
| Package | `update.bin` = plain GNU tar: `firmware_v20.info`, `recovery-update/xImage`, `recovery-update/rootfs.squashfs` | identical (named update.tar) |
| rootfs | squashfs 4.0, LZO, 128 KiB blocks, 55,738,368 bytes | same format |
| Signing | none, MD5 only | none |

`update.bin` is not encrypted or signed. The device-side updater (`update_firmware` in `demo`,
disassembled with `tools/dis.py`) does exactly this:

1. `tar xvf /mnt/mmc/update.bin -C <tmp>` ; `sync`
2. read 4 lines of `firmware_v20.info`
3. line 1 must `strcmp` equal `"Shanling M1 Plus"`
4. line 2 must contain the letter `V` (`strchr`) and must NOT equal the built-in `"V2.1"`
   (identical version is refused with error -14; there is no "newer than" check)
5. MD5 of `recovery-update/xImage` and `rootfs.squashfs` must match lines 3 and 4
6. `flash_erase /dev/mtd6` ; write marker `ota:kernel2` to mtd6 with `nandwrite` ; reboot

The actual flashing is then done by a separate recovery kernel ("kernel2") that lives in its own
flash partition. **That recovery kernel and the bootloader are not part of update.bin and are
never rewritten by it**, which is the main reason this is relatively safe: a bad rootfs can be
replaced by flashing again, the same way q2-pod documents for the Q2 (recovery-update folder on the
card, then hold Previous and power on with Centre). I did not find an official M1 Plus recovery
procedure online (Shanling only documents the normal TF-card / OTA update), so treat the button
combination as unverified for this model.

Partition hints from the kernel DTB: `kernel@40000`, `rootfs@360000`, `partition@100000`,
`partition@900000`, `sadc@10070000`; mtd5 holds a config blob, mtd6 the OTA flag.

## 2. Safety assessment

Relatively safe, with the usual caveats:

- Only kernel and rootfs are flashed; bootloader + recovery kernel stay stock.
- The rootfs is read-only squashfs, so a mod cannot corrupt itself at runtime.
- The watchdog script in the stock rootfs reboots the device if `demo` is not running, so a
  crashing UI gives a reboot loop, not a dead device. Recovery flashing fixes it.
- Keep the rebuilt `rootfs.squashfs` no larger than stock (fwtool enforces this).
- Charge the battery first and do not pull the card during the update.
- Residual risks: the recovery button combo for M1 Plus is unverified, and my rebuilt squashfs is
  recompressed (same content, same metadata, verified with a full-precision listing diff, but not
  byte-identical to stock because mksquashfs output differs). The space step (section 4) zeroes
  bytes of `demo` that are never loaded and removes files nothing references; it is not
  hardware-tested.

## 3. The battery widgets (what the release mod relies on)

In `ui/system_bar.bin` the battery is an `image` (`img_battery`, 14x20 at x=296: bar_power /
bar_charge / bar_lowpower) with an AWTK `progress_bar` (`pgbar_battery`, 14x17, vertical) drawn
as its fill. On every refresh `dropdown_showface` in `demo` calls
`progress_bar_set_value(pgbar_battery, capacity)`; while charging it still passes the real
capacity (full = 100). `tools/mod_battery.py` redraws the three state images as an outline and lays
the progress bar out as a horizontal fill inside it (`docs/ui.md`), with **no binary patch**.

The `demo` code is untouched by the asset steps (the space step only zeroes its unloaded `.pdr`; the
payload appends a segment and patches pinned words, `docs/architecture.md`), so the installed version
string stays "V2.1". Consequences:
- every package needs its own version tag so the updater accepts it (`docs/workflow.md`);
- official stock V2.1 would be refused by the TF-card menu afterwards (identical version), so a
  `V2.1R` restore package with the untouched stock images is built by `build.py --restore`;
- any future official release (V2.2 ...) installs normally.

## 3b. The lock screen page (ui/screensaver_page.bin): what the app does with it

What `demo` does with this page (`screensaver_page_init` and the static handlers after
`poweroff_page_init`, read with `dis.py`):

- at init a `widget_foreach` visitor matches names: `img_screensaver` gets the wallpaper
  (`screensaver_default` or `file://` + the custom picture), `view_timeinfo` is shown or hidden by the
  "show time" screensaver setting, `app_gesture` gets the swipe handler, `btn_play` / `btn_next` get
  click handlers;
- a widget timer runs a refresh (0x53f520; lookups at 0x53f564 / 0x53f584, `progress_bar_set_value` at
  0x53f640) that does `widget_lookup("img_battery")`, `widget_lookup("pgbar_battery")`,
  sets the icon to `screens_battery` / `screens_charge` / `screens_lowbattery` and calls
  `progress_bar_set_value(pgbar_battery, power_capacity)` (a constant 100 when on the charger and the PMU
  reports charge complete), then updates `view_bottomview` (shown or hidden), `view_scrlabel_title`,
  `view_scrlabel_artist`, the `btn_play` style and the `view_img_icon` cover. So this page's
  `pgbar_battery` is fed by the app just like the status bar's, and `show_text` + `format=%d%%` gives a
  live percentage here too;
- `dclock_time` and `dclock_date` are never looked up and their format is never changed (the strings
  are not in `demo` at all).

`dis.py xref` now resumes after undecodable words in `.text` and sees call arguments set in branch
delay slots; before that it reported 0 references for most strings.

12/24 h: `demo` calls `digit_clock_set_format` in two places only: the date-time settings row
(`Y-MM-DD`) and `change_time24h_12h`, which sets the status bar's `bar_dclock` to `hh:mm` (24 h) or
`HH:TT` (12 h).
The stock lock screen clock therefore always shows 24 h, whatever the setting, and the mod keeps that
by default. The digit_clock formatter is statically linked into `demo` (`wstr_format_date_time`,
modified by Shanling) and supports:

| token | output | token | output |
|---|---|---|---|
| `Y` / `YY` | 2026 / 26 | `h` / `hh` | hour 0-23 / 00-23 |
| `M` / `MM` / `MMM` | 1-12 / 01-12 / month name | `H` / `HH` | hour 0-23 unpadded / 01-12 |
| `D` / `DD` | 1-31 / 01-31 | `m` / `mm`, `s` / `ss` | minute, second |
| `w` / `W` | weekday 0-6 / name (EN or CN) | `T` / `TT` | minute / minute + ` AM` or ` PM` |

so `HH:TT` renders `05:30 PM` on the M1 Plus (q2-pod saw `05:PM` on the Q2's lock screen: a different
AWTK build, so these tokens are not portable between models). A `HH:TT` lock clock would be a fixed 12 h one: it does not follow the setting.

Sizing follows AWTK's stb font backend: `font_size` equals hhea ascender minus descender (299 units in
`default.ttf`), digits are tabular (142 units), so `hh:mm` is 2.14 x font_size wide; the tool reads the
font and picks the largest size that keeps 12 px margins. Rotation (`ROTATEMODE`) is
`tk_set_lcd_orientation(180)` on the whole LCD, so the page keeps its 320x480 coordinates and nothing in
the layout is rotation-specific. No other UI file carries this page: `theme1` has no
`screensaver_page.bin` (it uses default's, like every page it lacks), and `systemset/screensaver_page.bin` /
`systemset/keylock_page.bin` are the settings lists. 

**Cover size**: `view_img_icon` is filled by a loader at
`0x53f9b4` with `file:///tmp/coverpic.jpg` (embedded art; `/tmp/externpic.jpg` for folder or
downloaded art, built-in `random_cover0..7`, else `defaultcover`). That is the same file Now Playing's
`img_playcover1` shows. `parseplaycover_thd` writes it with `toolsGetAlbumCover(track, dst, 254, 254)`:
fitted into 254 x 254 with the aspect kept, and never upscaled. So the stock 66 px strip shrank a
254 px picture, and a 254 px widget draws it 1:1.

The lock screen layout the release builds from this: `docs/ui.md` ("Lock screen").

## 4. Space recovery (`mod_space.py`)

A plain fwtool rebuild of stock is 12 KB under the stock size, which fwtool enforces as the limit.
`build.py` therefore applies a space step to the release (not to `--restore`):

| step | rootfs.squashfs | saved | headroom |
|---|---|---|---|
| stock image | 55,738,368 | | |
| fwtool rebuild, no change | 55,726,080 | | 12,288 |
| + `mksquashfs -tailends` (`fwtool repack --tailends`) | 55,697,408 | 28,672 | 40,960 |
| + `.pdr` zeroed in `demo` | 55,635,968 | 61,440 | 102,400 |
| + 10 unused files removed (**default result**) | 53,141,504 | 2,494,464 | 2,596,864 |

(mksquashfs pads to 4 KiB.)

- **-tailends** packs the last partial block of every file into fragments. Data layout only; names,
  modes, owners and times are unchanged. Directory sizes in a listing change (squashfs directory-table
  length follows the inode layout); seen on the first hardware-tested packages for 22 directories.
- **.pdr** (MIPS procedure descriptors, a debugger table) is zeroed in `/release/bin/demo` only
  (415,744 bytes at file offset 0x5f388c), the same as q2-pod does for the Q2; every other ELF ships
  untouched. The section is found by name in the section headers and must be `PROGBITS`, without
  `SHF_ALLOC`, address 0, outside every program header, not overlapping another section or the
  headers, with no relocations against it. The loader only maps program headers, so these bytes are
  never mapped; `.pdr` is used by debuggers (gdb), and nothing on the rootfs is known to read it from
  disk. File size, section headers and every other byte are unchanged (cross-checked with
  pyelftools). `demo` is pinned by its stock SHA-256 (`29e23119...b3f1`). The About version string is
  in `demo`'s `.rodata` and stays `V2.1`.
- **removed**, each pinned by SHA-256: `usr/bin/strace`, `strace-log-merge`, `sqlite3`, `hcidump`;
  `usr/lib/libdbus-1.so.3.19.8`; `usr/lib/lib{gio,glib,gmodule,gobject,gthread}-2.0.so.0.5400.3`
  (6,438,409 bytes). Evidence they are unused: no symlink resolves to any of them; a byte search of
  every other file on the rootfs (binaries included) finds neither their file names nor `0.5400.3` /
  `3.19.8` (the only `5400` hits are a jQuery clsid and font glyph names), so no DT_NEEDED, script,
  config or `dlopen` string names them; the libraries' sonames (`libglib-2.0.so.0`,
  `libdbus-1.so.3`, ...) resolve through the `/usr/lib` symlinks to the newer 0.7400.4 / 3.19.15
  copies, and there is no
  `ld.so.cache`; no script or binary invokes `strace`, `sqlite3` or `hcidump` (`demo` uses
  `libsqlite3.so.0`, which stays); `sqlite3` could not even start (needs `libreadline.so.8`, not
  shipped). fwtool accepts the missing inodes only via an explicit `--allow-removed PATH` list.
  Further orphan candidates seen but kept: `libbluetooth.so.3.18.16`, `libexpat.so.1.6.2`,
  `lib{form,menu,panel}.so.6.1` (~415 KB uncompressed).
The checkappprocess.sh watchdog (`usr/bin/checkappprocess.sh`, started by `demo`) polls
`pgrep /release/bin/demo` every 2 s and reboots if it is gone; the release leaves it as it is.

The space step was flashed on hardware on 2026-10-19 (V2.1cS, stock UI) and has been part of every package
since (`docs/history.md`). `fwtool diff` against stock lists exactly `demo` (content), the removed files and
the mod's own files.

## 5. Rebuilding

`python3 -I tools/build.py` does it all from the pinned zip in `firmware/` (`docs/workflow.md`). By hand,
the pieces:

```
python3 -I tools/fwtool.py unpack "work/M1 Plus Firmware V2.1/update.bin" work/stock
python3 -I tools/fwtool.py repack work/mod-x out/x-update.bin --version V2.1xY --tailends --allow-removed usr/bin/strace ...
python3 -I tools/fwtool.py verify out/x-update.bin
python3 -I tools/awtk_ui.py dump work/stock/rootfs/release/assets/default/raw/ui/system_bar.bin
venv/bin/python -I tools/dis.py sym work/stock/rootfs/release/bin/demo update_firmware
venv/bin/python -I tools/dis.py xref work/stock/rootfs/release/bin/demo pgbar_battery
```

fwtool rebuilds the squashfs with the stock parameters (lzo, 128 KiB, mkfs time) and re-applies
every stock inode's mode/uid/gid/mtime from the `unsquashfs -pf` dump (macOS cannot preserve
symlink modes or setuid bits on extraction), then rebuilds the tar with the stock member metadata
and a regenerated `.info`. An unmodified round trip without `--tailends` produced a zero-line diff
of the full-precision listing against stock; with `--tailends` only 13 directory sizes differ.

## 6. The code payload

`demo` has the same injectable layout as the Q2 (`ET_EXEC`, LOAD ends at va `0xa10fc8`, a spare
final `PT_NULL` program header, `$gp = 0xa03ed0`). M1 Pod appends a non-PIC MIPS payload at va
`0xb00000` and hooks two functions; mechanism, addresses, trampolines, kill switch and boot guard:
`docs/architecture.md`.
