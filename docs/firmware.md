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

## 3. What the first mod does (battery percentage, asset-only)

In `ui/system_bar.bin` the battery is an `image` (`img_battery`, 14x20 at x=296: bar_power /
bar_charge / bar_lowpower) with an AWTK `progress_bar` (`pgbar_battery`, 14x17, vertical) drawn
as its fill. On every refresh `dropdown_showface` in `demo` calls
`progress_bar_set_value(pgbar_battery, capacity)`; while charging it still passes the real
capacity (full = 100). AWTK progress bars can render their value as text (`show_text` + `format`),
so re-styling that one widget gives a live percentage with **no binary patch**:

- `mod_battery.py --variant percent`: icon hidden (visible=false and parked off-screen), the
  progress bar becomes a transparent 42x30 text slot at x=272 with `format=%d%%`, white 16 px,
  right-aligned. Bluetooth/Wi-Fi group shifted left to stay clear.
- `mod_battery.py --variant icon+percent`: state icon kept at x=296, 15 px percentage to its left.

In the `V2.1bA` / `V2.1bB` packages only `release/assets/default/raw/ui/system_bar.bin` differs from
stock (2252 -> ~2360 bytes); the `c` packages add the space step of section 4.
Mock-up: `docs/statusbar-preview.png` (PIL rendering, not pixel-exact AWTK).

The `demo` code is untouched (the space step only zeroes its unloaded `.pdr`), so the installed
version string stays "V2.1". Consequences:
- the mod packages use version tags `V2.1bA` / `V2.1bB` / `V2.1c*` so the updater accepts them;
- official stock V2.1 would be refused by the TF-card menu afterwards (identical version), so a
  `V2.1R` restore package with the untouched stock images is provided;
- any future official release (V2.2 ...) installs normally.

## 3b. The lock screen mod (ui/screensaver_page.bin)

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
AWTK build, so these tokens are not portable between models). `--clock-format HH:TT` gives a 12 h lock
clock, but a fixed one: it does not follow the setting.

Default layout (`mod_lockscreen.py`, widgets keep their names; only geometry and style change):

| widget | stock | mod |
|---|---|---|
| `view_timeinfo` | 0,90 320x130 | 0,82 320x180, centred above the now-playing strip |
| `dclock_time` | 52,0 150x70, 70 px, left aligned | 0,0 320x138, 138 px, centred (widest `00:00` is 295 px) |
| `dclock_date` | 0,72 320x50, 50 px | 0,114 320x32, 24 px, centred (`--date-size`, `--date-format`, `--no-date`) |
| `pgbar_battery` | 227,27 33x20, white horizontal fill | 114,148 46x28, transparent, `%d%%` 20 px white, right aligned |
| `img_battery` | 225,26 40x23 (outline, the bar is its fill) | 166,151, right of the percentage (`--battery percent` hides it, `--battery icon` keeps the gauge) |
| `view_bottomview`, `img_slide`, `img_screensaver`, buttons | | unchanged (`--strip-y` moves the strip) |

Sizing follows AWTK's stb font backend: `font_size` equals hhea ascender minus descender (299 units in
`default.ttf`), digits are tabular (142 units), so `hh:mm` is 2.14 x font_size wide; the tool reads the
font and picks the largest size that keeps 12 px margins. Rotation (`ROTATEMODE`) is
`tk_set_lcd_orientation(180)` on the whole LCD, so the page keeps its 320x480 coordinates and nothing in
the layout is rotation-specific. No other UI file carries this page: `theme1` has no
`screensaver_page.bin` (it uses default's, like every page it lacks), and `systemset/screensaver_page.bin` /
`systemset/keylock_page.bin` are the settings lists. The file grows 3616 -> 4038 bytes; without the space step the rebuilt
squashfs is 55,726,080 bytes (12,288 under stock); with it (the default) the lock screen packages
land on the same size as the other `c` packages.

Mock-up: `docs/lockscreen-preview.png` (approximate; the wallpaper is replaced by a gradient).

**Cover size** (for `--layout cover`, `docs/lockscreen2.md`): `view_img_icon` is filled by a loader at
`0x53f9b4` with `file:///tmp/coverpic.jpg` (embedded art; `/tmp/externpic.jpg` for folder or
downloaded art, built-in `random_cover0..7`, else `defaultcover`). That is the same file Now Playing's
`img_playcover1` shows. `parseplaycover_thd` writes it with `toolsGetAlbumCover(track, dst, 254, 254)`:
fitted into 254 x 254 with the aspect kept, and never upscaled. So the stock 66 px strip shrank a
254 px picture, and a 254 px widget draws it 1:1.

**`--layout cover`** (V2.1fK `look-lock2`) is the iPhone-style alternative: date over an 88 px clock at
the top, the strip as a 274x322 card with the 254 px cover rounded by a corner mask, title / artist /
play / next under it, and a battery gauge without a number. Full description, touch analysis and
device checklist: `docs/lockscreen2.md`. The classic layout stays the default (V2.1cL/cLB/dE/eA
rebuild byte-identical).


## 4. Space recovery (`mod_space.py`, default for mod packages)

A plain fwtool rebuild of stock is 12 KB under the stock size, which fwtool enforces as the limit.
`build.py` therefore applies a space step to every mod package (not to `--restore`):

| step | rootfs.squashfs | saved | headroom |
|---|---|---|---|
| stock image | 55,738,368 | | |
| fwtool rebuild, no change | 55,726,080 | | 12,288 |
| + `mksquashfs -tailends` (`fwtool repack --tailends`) | 55,697,408 | 28,672 | 40,960 |
| + `.pdr` zeroed in `demo` | 55,635,968 | 61,440 | 102,400 |
| + 10 unused files removed (**default result**) | 53,141,504 | 2,494,464 | 2,596,864 |
| opt-in `mod_space.py --pdr-all` instead of demo only | 52,600,832 | 540,672 more | 3,137,536 |

(The battery variants land on the same sizes; mksquashfs pads to 4 KiB.)

- **-tailends** packs the last partial block of every file into fragments. Data layout only; names,
  modes, owners and times are unchanged. Directory sizes in a listing change (squashfs directory-table
  length follows the inode layout); the hardware-tested V2.1bB already showed that for 22 directories.
- **.pdr** (MIPS procedure descriptors, a debugger table) is zeroed in `/release/bin/demo` only
  (415,744 bytes at file offset 0x5f388c), the same as q2-pod does for the Q2; every other ELF ships
  untouched. The section is found by name in the section headers and must be `PROGBITS`, without
  `SHF_ALLOC`, address 0, outside every program header, not overlapping another section or the
  headers, with no relocations against it. The loader only maps program headers, so these bytes are
  never mapped; `.pdr` is used by debuggers (gdb), and nothing on the rootfs is known to read it from
  disk. File size, section headers and every other byte are unchanged (cross-checked with
  pyelftools). `demo` is pinned by its stock SHA-256 (`29e23119...b3f1`). The About version string is
  in `demo`'s `.rodata` and stays `V2.1`.
  `mod_space.py --pdr-all` (opt-in, not in build.py, **not hardware-proven**) applies the same checks
  and zeroing to all 197 executables and shared libraries (`hciplayer`, `libawtk.so`, `libtkc.so`,
  libc, ld.so, ...; 3,857,024 bytes), pinned as a set by a manifest digest; kernel modules (`.ko`)
  are never touched. Every file is checked before any is written.
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
- **watchdog** (opt-in, `--watchdog`, tag suffix `W`): `usr/bin/checkappprocess.sh` (started by
  `demo`) polls `pgrep /release/bin/demo` every 2 s and reboots if it is gone; the flag makes that
  `sleep 10`, after checking the script is byte-identical to stock. A crashed UI then reboots after up
  to 10 s instead of 2 s.

V2.1cS (this step alone, stock UI) was flashed on hardware on 2026-10-19 and looked fine in a first
look, and V2.1cLB (with the lock screen and status bar mods) works too (see section 5). `fwtool diff` against stock
lists exactly `demo` (content), the removed files and the mod's own files.

## 5. Packages (out/)

| file | content | info version |
|---|---|---|
| `M1Plus-V2.1bA-percent-update.bin` | percentage replaces the icon | V2.1bA |
| `M1Plus-V2.1bB-iconpercent-update.bin` | icon + percentage | V2.1bB |
| `M1Plus-V2.1cS-space-update.bin` | space step only, UI stock (flash this first) | V2.1cS |
| `M1Plus-V2.1cA-percent-space-update.bin` | percentage + space step | V2.1cA |
| `M1Plus-V2.1cB-iconpercent-space-update.bin` | icon + percentage + space step | V2.1cB |
| `M1Plus-V2.1cBW-iconpercent-space-watchdog-update.bin` | V2.1cB + 10 s watchdog poll | V2.1cBW |
| `M1Plus-V2.1cL-lockscreen-space-update.bin` | lock screen mod + space step | V2.1cL |
| `M1Plus-V2.1cLB-lockscreen-iconpercent-space-update.bin` | lock screen mod + icon + percentage status bar + space step | V2.1cLB |
| `M1Plus-V2.1dA-pod-inert-...-update.bin` | M1 Pod payload segment, **no hook** (+ lock screen + icon+percent + space) | V2.1dA |
| `M1Plus-V2.1dH-pod-hello-...-update.bin` | M1 Pod + hook: the Tidal icon opens a hello page | V2.1dH |
| `M1Plus-V2.1dM-pod-menu-...-update.bin` | M1 Pod + hook: the Tidal icon opens an iPod-style menu | V2.1dM |
| `M1Plus-V2.1dE-pod-cover-...-update.bin` | V2.1dM plus the menu's **Cover Flow** page (`docs/coverflow.md`); touch, track-list contrast and menu scrolling fixed; SHA-256 `0806ade2...` | V2.1dE |
| `M1Plus-V2.1eT-look-theme-pod-cover-...-update.bin` | V2.1dE + Minimal theme (`docs/look-theme.md`); `6f921f4f...` | V2.1eT |
| `M1Plus-V2.1eL-look-lists-pod-cover-...-update.bin` | V2.1dE + library lists (`docs/look-lists.md`); `768b6abd...` | V2.1eL |
| `M1Plus-V2.1eN-look-nowplaying-pod-cover-...-update.bin` | V2.1dE + iPod-style Now Playing (`docs/look-nowplaying.md`); `84ed09f1...` | V2.1eN |
| `M1Plus-V2.1eB-look-boot-pod-cover-...-update.bin` | V2.1dE + boot logo, quotes, settings slides (`docs/look-boot.md`); `9cd5d06c...` | V2.1eB |
| `M1Plus-V2.1eA-look-all-pod-cover-...-update.bin` | V2.1dE + all four looks (`docs/look-all.md`) | V2.1eA |
| `M1Plus-V2.1fK-look-lock2-pod-cover-...-update.bin` | V2.1eA + iPhone-style lock screen with a large cover (`docs/lockscreen2.md`); `5b2549dc...` | V2.1fK |
| `M1Plus-V2.1R-stock-restore-update.bin` | stock kernel + stock rootfs bytes | V2.1R |

`b` = battery mod only (`build.py --no-space`, byte-identical to the packages tested below), `c` =
with the space step. Builds are deterministic: a clean rebuild from the zip gives identical packages.

Hardware test 2026-10-19: V2.1R flashed first as a dry run (accepted, booted stock), then V2.1bB
(accepted, percentage shows next to the icon). Both via the TF-card menu. Later the same day V2.1cS
(space step only, SHA-256 `d7bd5f82...`) was flashed over V2.1bB the same way: accepted, boots and
works in a first look by the user; the full checklist in `docs/workflow.md` section 4 has not been
gone through item by item. Then V2.1cLB (lock screen + icon+percent status bar + space step,
SHA-256 `62f3cb18...`) was flashed over V2.1cS: accepted, and the user reports it works. The other
`c` packages (cA, cB, cBW, cL) are not tested on hardware, but cLB covers their parts except the
watchdog change and the `percent` (icon hidden) status bar.

Hardware test 2026-10-20: **V2.1dM** (M1 Pod menu + lock screen + icon+percent + space, SHA-256
`6b540e660d20d559a412c0330ba557ff453bd0f22237964754969bcb018e38e7`) was flashed **directly over
stock V2.1R** and works: the player boots, so the loader accepts the appended RWX `PT_LOAD` at
`0xb00000`; the Home-icon hook on **Tidal** opens the M1 Pod menu; and the menu's rows open the
stock pages. V2.1dA (inert) and V2.1dH (hello) were never flashed, so the staging order in
`docs/workflow.md` was skipped and the menu stage proved all three steps at once. That SHA-256 is
the package as built at commit `e6a2fc0`; later commits change the payload (the Cover Flow row and
its code), so a rebuild of `V2.1dM` today is functionally the same but not byte-identical.
Hardware test 2026-10-25: **V2.1dC** (Cover Flow, `282a5803…`) boots, the Cover Flow row opens
the page, the "Preparing covers" screen appears and the navbar works, but the cover area ignored
taps and swipes (and the menu could not be scrolled). Root cause: this AWTK build's hit test ignores
`visible`, and a hidden full-screen `view_tracks` sat on top of the covers — details and the fix in
`docs/coverflow.md`. **V2.1dD** carries the fix (hidden = insensitive, a transparent touch layer
driving the carousel, the menu rows in a scroll view). V2.1dC's cache build had written 107
thumbnails (14 MB) to the card, so extraction and the worker thread work on the device.

Hardware test 2026-10-25, **V2.1dD** (`591880e8…`): **swiping the covers works**. The album's
track list showed white text on a white background, and the M1 Pod menu could not scroll: normal
windows are 450 px tall under the 30 px status bar, so the list overhung the window by 30 px and
its rows did not even overflow it. **V2.1dE** fixes both (stock `list_item_style` rows, pages laid
out in 450 px, a stock-structured scrolling list with 52 px rows; `docs/coverflow.md`); not yet
hardware-tested.

Flash: rename to `update.bin`, copy to the root of the microSD card, System settings -> System
Update -> TF card update. Check settings -> About still says V2.1 (expected, the version string is never changed).
Go back: flash the V2.1R restore package the same way.

## 6. Rebuilding

```
# everything from the pinned zip in firmware/
python3 -I tools/build.py --variant space          # or percent, icon+percent; --watchdog, --no-space
python3 -I tools/build.py --restore
# the same, step by step (icon+percent with the space step)
python3 -I tools/fwtool.py unpack "work/M1 Plus Firmware V2.1/update.bin" work/stock
python3 -I tools/mod_battery.py work/stock work/mod-iconpercent-space --variant icon+percent
python3 -I tools/mod_space.py work/mod-iconpercent-space          # in place; --from STOCK clones first
python3 -I tools/fwtool.py repack work/mod-iconpercent-space out/M1Plus-V2.1cB-iconpercent-space-update.bin \
    --version V2.1cB --tailends --allow-removed usr/bin/strace ...   # one --allow-removed per mod_space.REMOVE entry
python3 -I tools/fwtool.py verify out/M1Plus-V2.1cB-iconpercent-space-update.bin
# helpers
python3 -I tools/awtk_ui.py dump work/stock/rootfs/release/assets/default/raw/ui/system_bar.bin
venv/bin/python -I tools/dis.py sym work/stock/rootfs/release/bin/demo update_firmware
venv/bin/python -I tools/dis.py xref work/stock/rootfs/release/bin/demo pgbar_battery
```

The full process, including the on-device test procedure, is in `docs/workflow.md`.

fwtool rebuilds the squashfs with the stock parameters (lzo, 128 KiB, mkfs time) and re-applies
every stock inode's mode/uid/gid/mtime from the `unsquashfs -pf` dump (macOS cannot preserve
symlink modes or setuid bits on extraction), then rebuilds the tar with the stock member metadata
and a regenerated `.info`. An unmodified round trip without `--tailends` produced a zero-line diff
of the full-precision listing against stock; with `--tailends` only 13 directory sizes differ.

## 7. M1 Pod: a code payload (not asset-only)

`demo` has the same injectable layout as the Q2 (`ET_EXEC`, LOAD ends at va `0xa10fc8`, a spare
final `PT_NULL` program header, `$gp = 0xa03ed0`). M1 Pod appends a non-PIC MIPS payload at va
`0xb00000` (rewriting that `PT_NULL` into an RWX `PT_LOAD`) and hooks exactly one function — the
Home icon click dispatcher at `0x533b80` — to open new pages. It is the first code mod here and is
built on top of the lock screen + icon+percent + space tree. Full mechanism, addresses, hook,
trampoline, kill switch and staging: **`docs/payload.md`**. Built with Homebrew clang/ld.lld 23.1.3
and validated offline with a Unicorn harness (`test/patch.py`). V2.1dM works on hardware
(section 5).

The payload's largest page is **Cover Flow** (`docs/coverflow.md`): the stock Local Music albums as
a depth-rendered cover carousel on a stock `slide_menu`, with its own thumbnail cache under
`/mnt/mmc/.coverflow` built by one worker thread. It adds no hook of its own.

## 8. Ideas for next small mods (still asset-only)

- status bar clock seconds / 12h, font sizes, colours (`styles/default.bin`, `ui/*.bin`)
- boot logo image, screensaver page layout
- hide widgets you never use (e.g. the SyncLink icon)
