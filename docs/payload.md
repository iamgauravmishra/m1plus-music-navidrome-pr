# M1 Pod: a code payload inside `demo`

The asset-only mods (battery percentage, lock screen) change `ui/*.bin` and never touch code. M1 Pod
goes further: it adds **new pages** to the UI app by injecting a small machine-code payload into
`/release/bin/demo`, exactly the way [q2-pod](https://github.com/DiamondBond/q2-pod) does on the
Shanling Q2 (MIT; see `NOTICE`). This is inherently riskier than an asset edit, so it ships in
stages and fails safe at every step (see [Safety](#safety)).

The M1 Plus and the Q2 run the same stack (Ingenic X2000, Linux 5.10, Buildroot glibc, AWTK, a
`demo` ELF with a spare `PT_NULL` program header), so q2-pod's approach ports directly; only the
addresses, symbols and pages differ.

## Toolchain (recorded)

| tool | version | why |
|---|---|---|
| clang | Homebrew clang 23.1.3 (`/opt/homebrew/opt/llvm/bin`) | Apple clang has no MIPS target |
| ld.lld | Homebrew LLD 23.1.3 (`/opt/homebrew/opt/lld/bin`) | links the non-PIC payload |
| llvm-objcopy / llvm-readelf | LLVM 23.1.3 | `.elf` -> flat `patch.bin`, symbol table |
| unicorn | 2.1.4 (pip, in a venv) | offline execution test (`test/patch.py`) |
| squashfs-tools | mksquashfs 4.7.5 | unchanged from the asset mods |

`$LLVM_BIN` / `$LLD_BIN` override the toolchain paths. `brew install llvm lld` provides them.

## How the injection works

### The segment

`demo` is `ET_EXEC`, MIPS32r2 LE. Its LOAD segments end at va `0xa10fc8`, and the last program
header, `PH[10]`, is an unused `PT_NULL`. `tools/pod.py` `append_payload`:

1. pads the file to a 64 KiB boundary and appends `patch.bin`;
2. rewrites `PH[10]` from `PT_NULL` into a file-backed **`PT_LOAD` at va `0xb00000`**, flags `RWX`
   (7), `filesz == memsz == len(payload)`, align `0x10000`.

The payload keeps **no** `.bss`: its writable state (Cover Flow's page and renderer bookkeeping,
160 bytes) lives in an explicit **`.scratch`** section, which the compiler emits as zero-filled
`PROGBITS`, so it is part of `patch.bin` and `memsz == filesz` still holds — the loader needs no
mapping beyond the file image and no `.bss` clearing. `pod.py` rejects a non-empty `.bss`/`.sbss`
and checks that `.scratch` is `PROGBITS`, inside the payload and shipped all-zero. (q2-pod uses a
`NOLOAD .scratch` covered by `memsz`; file-backed zeros are simpler here and keep the segment's
two sizes equal, which is the one invariant the appender relies on.) Everything larger — the depth
frame, the cover textures, the job array, the album copy — is heap, allocated when the Cover Flow
page opens and freed when it closes. `0xb00000` is above every stock
LOAD end, and the mapping is checked not to overlap any existing segment. The file offset is
congruent to the vaddr mod the alignment, so the loader can `mmap` it. The ELF still parses
(pyelftools, `tools/elfinfo.py`, `tools/dis.py`), with `PH[10]` now `LOAD … va=0x00b00000`.

### $gp

Every stock PIC function starts with the 3-word prologue `lui $gp, hi; addiu $gp, $gp, lo; addu
$gp, $gp, $t9`, which reconstructs the global pointer `$gp = 0xa03ed0` (matches
`DT_PLTGOT + 0x7ff0` and `dis.py`). The payload is compiled **non-PIC** (`-mno-abicalls -fno-pic
-G0`), so it needs no `$gp` of its own; it reaches stock code and data by absolute address.

### The hook

One stock function is hooked: the **Home screen icon click dispatcher** at `0x533b80` (unnamed in
`.dynsym`; registered on each Home icon by `home_page_init` via `widget_on(icon, EVT_CLICK=0x10c,
…)`). Its pinned prologue `(0x3c1c004d, 0x279c0350, 0x0399e021)` is overwritten with

```
j  m1pod_home_click      ; 0x08000000 | (target >> 2)
nop
```

`pod.py` asserts the three prologue words and that they resolve `$gp == 0xa03ed0` before writing.

### The trampoline

`stock_home_click_trampoline` re-establishes `$gp` and resumes the stock dispatcher past its
prologue:

```
lui $gp, 0xa03e ; ori $gp, $gp, 0x3ed0 ; j 0x533b8c ; nop
```

`m1pod_home_click` calls it to fall through to stock behaviour (any non-entry tap, the kill switch,
or a failed page open), and `home_open()` calls it with a fake numeric-named icon to open a stock
Home destination.

### Calling stock code and libc

- **Stock functions** are plain absolute-address macros in the generated `stock.h`, e.g.
  `#define widget_lookup ((void*(*)(void*,const char*,int))0x666a74u)`. clang emits `lui/ori $t9;
  jalr $t9`, and the callee sets up its own `$gp` from `$t9`. Pinned functions: `widget_lookup`
  `0x666a74`, `widget_on` `0x666d20`, `widget_set_text_utf8` `0x66f720`, `navigator_back`
  `0x4d20dc`, `on_backtoplayer_onclick` `0x4cd58c`, `window_open` `0x679fd4`.
- **libc** is reached only through slots `demo` already imports, in its own `.got`: a tiny stub
  `lui/ori $t8, slot; lw $t9, 0($t8); jr $t9` tail-calls the resolved pointer. Used: `atoi`
  (`0xa031e4`), `access` (`0xa0369c`). No new imports are added.

### What the payload does

`patch/m1pod.c`, in `m1pod_home_click(icon, e)`:

1. read the clicked icon's name (`icon + 0x10`), `atoi` it (stock stores the Home id as a decimal
   string there);
2. if it is **not** the entry id (`POD_ENTRY_ID`, the Tidal icon, id 1), or the kill-switch file
   exists, or the page fails to open -> `stock_home_click_trampoline(icon, e)` (unchanged stock
   behaviour);
3. otherwise `window_open` the stage's entry page, bind `btn_return` -> `navigator_back`,
   `btn_backtoplayer` -> `on_backtoplayer_onclick`, and each `pod_rowN` to its row action, then
   return 0 (handled).

Row actions: open a stock Home destination (through the dispatcher with a fake numeric icon), open
Now Playing, open another M1 Pod page, or open **Cover Flow** (`ACT_COVER`, `patch/coverflow.c`,
`docs/coverflow.md`), which creates its own window from `ui/m1pod_cover.bin` and installs no hook.

## The pages

Pages are defined once in `tools/pod_pages.py` and consumed by both `tools/pod_ui.py` (which builds
the `ui/*.bin` with `tools/awtk_ui.py`) and `tools/pod.py` (which emits the C row/page tables into
`stock.h`), so a row's asset widget, its label and its handler can never drift apart. Each page is a
window with a stock-styled navigation bar (title, Back = `btn_return`, Now Playing =
`btn_backtoplayer`) over `pod_row0…` buttons.

The Stage C menu is the Classic iPod main menu adapted to 320x480 touch (q2-pod `docs/ipod.md`
geometry), inside the **450 px** a normal window gets under the 30 px status bar (68 stock pages end
at y = 450): a 50 px navbar over a 400 px list with the structure and properties of
`systemset/sysset_page.bin`'s (`list_view` > `scroll_view` + `scroll_bar_m`), of 52 px rows built
like stock's (`list_item` themed `list_item_style`, an `hscroll_label` themed
`srlabel_leftwhite21_style`, the `right_arrow` image), scrolling when the rows overflow (stage D's
nine rows: 468 px): Now Playing, Songs, Albums, Artists, Genres, Folders, Playlists, Settings. Rows open the
stock windows by id, or Now Playing. Row buttons are styled inline (white left text, dark pressed
shade, thin separators, a right chevron), so **no theme file changes**.

The entry icon is **Tidal** (Home id 1) — see the next section for why. Tapping it opens M1 Pod;
the kill switch restores Tidal. To move the entry, change `HOME_ENTRY` in `pod_pages.py`
(`POD_ENTRY_ID` follows it, and `test/patch.py` reads the same constant).

## Home icons and their conditions

The Home grid is built by `home_page_init` (`0x534cd4`) → the page builder (`0x534064`) → the icon
builder (`0x533d8c`), which walks a `deque` of 8-byte records `{int id; char shown; …}` at
**`0xa045c0`** and renders six icons per slide page. For each record it calls
`get_homemenu_showinfo(id, buf)` (`0x4d9ffc`), which indexes an 18-entry table at **`0x97c940`** for
the item's name string; the icon's style is `home_<name>_style`, its label is
`widget_set_tr_text(<name>)`, and its widget **name is the decimal id** (`tk_snprintf("%d", id)`).
That is what the click dispatcher at `0x533b80` reads back and `atoi`s to pick a destination.

| id | name | opens |
|---|---|---|
| 0 | `hifimusic` | `hifi/hifimusic_page`, or the `msg_notnetwork` dialog offline |
| 1 | `tidal` | `tidal/tidal_main`, or the `msg_notnetwork` dialog offline |
| 2 | `sset_updatemusic` | `systemset/updatemusic_page` (Update Library) |
| 3 | `mymusic` | `allmusic_page` ctx `0xf001` (All Songs) |
| 4 | `folder` | `folder_page` |
| 5 | `album` | `album_page` ctx `{0xf003, 0}` |
| 6 | `songer` | `localclass_page` `0xf004` (Artists) |
| 7 | `genre` | `localclass_page` `0xf006` |
| 8 | `composer` | `localclass_page` `0xf005` |
| 9 | `hr` | `allmusic_page` `0xf002` (Hi-Res) |
| 10 | `fav` | `allmusic_page` `0xf00a` (Favourites) |
| 11 | `many` | `allmusic_page` `0xf008` (Most played) |
| 12 | `recent` | `allmusic_page` `0xf007` (Recently played) |
| 13 | `recentadd` | `allmusic_page` `0xf009` (Recently added) |
| 14 | `playlist` | `playlist_page` |
| 15 | `cdripper` | `cdripper_page` (sets GPIO `PA11` first; needs the CD drive accessory) |
| 16 | `playset` | `playset/playset_page` |
| 17 | `sysset` | `systemset/sysset_page` |

Which ids end up in that deque:

- `reset_homemenu_index(0)` (`0x4d8114`, the *defaults*) clears it and pushes every id of
  `main_allmenu` (`0x97ca88`, exactly `0,1,…,17` in order) with `shown = 1` — **except** that when
  the `language` global (`0xa05ab8`, 4 bytes) is **non-zero** it skips `id == 0`
  (`lw $v1, language; beqz $v1, push; lw $v0, id; beqz $v0, skip` at `0x4d8170`).
- `reset_homemenu_index(non-zero)` loads the saved list (`get_menu_file`, config `[MAIN] HOMEMENU`);
  if `change_lanflag` is set it removes ids 0 and 1 and pushes them back at the **front** (both when
  `language == 0`, only one when it is not), then saves. So a language change puts Tidal first.
- `load_home_menu` (`0x4d7dc4`) builds the *customisation dialog's* list (`0xa045c4`) from the saved
  list plus every `main_allmenu` id not in it with `shown = 0`, applying the same `language != 0`
  skip for id 0. So id 0 is not even offered in the dialog outside Simplified Chinese.
- The user can show/hide any other id in **Home customisation** (`dialog/homemenu_dialog`), which
  rewrites the saved list.

`language` values come from `switch_language` (`0x4cca40`), whose jump table is indexed by
`language - 1`, with Simplified Chinese as the default case:

| value | 0 (and anything outside 1–12) | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| locale | `zh_CN` | `zh_HK` | `en_US` | `ja_JP` | `ko_KR` | `fr_FR` | `ge_DE` | `sp_ES` | `it_IT` | `th_TH` | `po_PL` | `ru_RU` | `uk_UK` |

**So the HiFi store icon exists only in Simplified Chinese** (`language == 0`); not even Traditional
Chinese (`zh_HK`) shows it. In English the default Home list is ids `1…17`, starting with Tidal.
Setting the UI language to 简体中文 is the one stock setting that makes the HiFi icon appear — useful
only if you want to test a build whose `HOME_ENTRY` is 0.

### Why Tidal, and why not patch the language check

An earlier build used id 0 and was unreachable in English. The options considered:

- **Patch the language comparison so English also gets id 0** (the coordinator's first preference).
  Rejected. The gate is not a single site on a page-local path: it is in `reset_homemenu_index`,
  which `platform_init` (`0x50bc90`) calls **at boot**, and in `load_home_menu`; and flipping the
  defaults branch alone changes nothing on a device that already has a saved HOMEMENU list, so it
  would take two or three branch patches plus a settings reset to show the icon. Those patches sit
  exactly on the boot path, where a mistake means a watchdog reboot loop on a device whose recovery
  button combination is unverified — a large risk for a purely cosmetic gain (which icon hosts the
  entry). The Chinese path itself looks benign (the icon only needs a style, a PNG and a `tr` key,
  and in English the label would fall back to the raw key `hifimusic`), but the risk is in the
  list-building edits, not in the icon.
- **Reuse a Home icon that English does show, preferring an online-only one.** Chosen: **Tidal
  (id 1)**. It is pushed to the front of the English Home list, it is online-only (its handler at
  `0x533c88` calls `networkGetConnectStatus` and shows `msg_notnetwork` with no connection, else
  opens `tidal/tidal_main`, which additionally needs a Tidal subscription), so offline it does
  nothing useful — the same "costs nothing" property the user confirmed for the HiFi store. No boot
  path change, no asset or string change, one constant.
  Runner-up: **CD Ripper (id 15)**, useless without the external CD drive accessory, but buried on
  the third Home page rather than first.
- **A handler outside Home** (e.g. `on_sn_qrcode_onclick` on the About page, or adding a row in
  `systemset_about_page_init`). Also safe and user-initiated, but far less discoverable, and adding
  a row means creating widgets natively; kept as a fallback idea.

What the user loses with the chosen entry: the Tidal icon no longer opens Tidal (unless the kill
switch file is present, which restores it exactly). Nothing else changes. The icon keeps its stock
Tidal label and artwork — relabelling it "M1 Pod" needs a parser for `strings/*.bin`, which this
repo does not have yet.

Caveat: like any Home icon, Tidal can be hidden in Home customisation, which would make the entry
unreachable until it is shown again there (and any language change re-adds it at the front).

## Safety

A boot-time crash on this device is dangerous (the watchdog reboots in a loop and the recovery
button combo is unverified), so:

- **No boot-path code.** The only hook is the Home icon click dispatcher, reached solely by a
  deliberate tap on a Home icon. Nothing runs in `platform_init`, the main loop, paint, or any
  startup path.
- **Kill switch.** The payload calls `access("/mnt/mmc/m1pod-off")` first; if that file is on the
  SD card it falls straight through to stock behaviour. Create it from any computer to disable M1
  Pod without reflashing.
- **Fail-safe.** Every error path (non-entry icon, kill switch present, `window_open` returns NULL
  because the asset could not load, a null icon) calls the stock function through the trampoline.
  The worst case for a bad asset is that the entry icon opens Tidal as it did stock, not a
  crash.
- **Staged.** Each stage is its own package and tag:
  - **V2.1dA — inert:** payload segment appended, **zero hooks**. Proves the loader accepts the new
    `PT_LOAD` and `demo` boots unchanged (the Home icon is still the stock store).
  - **V2.1dH — hello:** the hook installed; the entry icon opens a tiny new page (`ui/m1pod_hello.bin`:
    a label and Back) with the kill switch. Proves a new asset loads, the hook fires on tap, and
    Back works.
  - **V2.1dM — menu:** the hook installed; the entry icon opens the iPod-style menu
    (`ui/m1pod_menu.bin`) whose rows open stock pages. **Flashed on 2026-10-20, over stock V2.1R,
    and it works** (the segment loads, the hook fires on the Tidal icon, the rows open stock
    pages). dA and dH were skipped.
  - **V2.1dC — Cover Flow:** everything V2.1dM has plus a ninth menu row, **Cover Flow**
    (`ui/m1pod_cover.bin`, `patch/coverflow.c`): the stock albums as a cover carousel with its own
    thumbnail cache. Still one hook. **Flashed 2026-10-25: the page opens and builds its cache,
    but the covers ignored every touch** — a hidden full-screen view stayed hittable, because this
    AWTK's hit test checks only enable and sensitive (`docs/coverflow.md`).
  - **V2.1dD — Cover Flow, touch fixed:** hidden widgets are insensitive too, a transparent touch
    layer drives the carousel (drag, fling, snap, tap by x), and the menu rows live in a stock
    `list_view`/`scroll_view`. **Flashed 2026-10-25: swiping works**; the track list was white on
    white and the menu still could not scroll (450 px window, see `docs/coverflow.md`).
  - **V2.1dE:** stock-styled rows (`list_item_style`) for the menu and the track list, every page
    laid out in 450 px, the menu a stock-structured scrolling list of 52 px rows. Not yet
    hardware-tested.

  Rule learnt from V2.1dD: **normal windows are 450 px tall** (under the 30 px `system_bar`);
  only `fullscreen` windows get 480.

  Rule learnt from V2.1dC for every page: **on this build `visible=false` does not stop touches** —
  always pair it with `sensitive=false` (asset) or `widget_set_sensitive(w, 0)` (runtime).
- **Pinned.** `pod.py` pins the input demo SHA (the `.pdr`-zeroed stock V2.1 binary), the hook-site
  words, `$gp`, and every stock-function address before writing. `fwtool` pins the stock zip and
  rebuilds metadata-exact.

Every M1 Pod package also carries the user's current mods (lock screen + icon+percent status bar +
space step, as in V2.1cLB), so flashing one does not lose them.

## Offline validation

- **Unicorn harness** `test/patch.py` loads the real patched `demo` LOAD segments, mocks the stock
  functions and libc, and executes the actual compiled payload: entry opens the right page and
  binds its widgets; non-entry, kill switch, `window_open` failure, empty and null icons all fall
  through to stock; menu rows open the right destination; and for stage D the whole Cover Flow page
  (open, cache build, cancel, album, play, Back, close, empty library, no space, broken asset) plus
  a byte-for-byte comparison of the payload's rendered frame against the host build of the same
  renderer, plus hit tests run on demo's own `widget_find_target`, row styles and window bounds.
  128/128 (Cover Flow), 17/17 (menu), 15/15 (hello), 17/17 (inert).
- **Host renderer test** `test/coverflow.py` builds `patch/coverflow.c` for the host and checks the
  depth renderer's geometry, compositing, brightness ladder, reflection and cache key, and writes
  the preview PNGs. 23/23.
- **Pin checks** in `pod.py` (prologue words, `$gp`, addresses, input SHA) and `append_payload`
  (segment does not overlap; single final `PT_NULL`).
- **ELF still parses** (pyelftools / `elfinfo.py` / `dis.py`) with the new `PT_LOAD`.
- **fwtool verify / diff** on every package; diff shows only `demo`, the new `m1pod_*` asset, the
  two existing mod assets, and the 10 space-step removals.
- **Deterministic**: a clean rebuild yields a byte-identical package (added assets get a fixed
  mtime).

## Cover Flow

The one page that is more than rows and buttons has its own document: **`docs/coverflow.md`** (the
stock queries it uses, the depth renderer, the thumbnail cache and its thread, what is not ported
from q2-pod). It is reached only from the menu's Cover Flow row, adds no hook, and falls back to
flat stock images if its bitmaps cannot be allocated.

## Adding a page

1. add a `Page(...)` to `tools/pod_pages.py` with its rows, and reference it from a stage (or from
   another page's `Row(..., ACT_PAGE, index)`);
2. rebuild — `pod_ui.py` writes `ui/<key>.bin`, `pod.py` emits its row table, `m1pod.c` opens and
   binds it generically;
3. run `test/patch.py` and flash the staged packages in order.

New row targets must be stock window names reachable by the Home dispatcher (ids in
`patch/offsets.inc`) or `ACT_PLAYER` / `ACT_PAGE`.

## How this maps to q2-pod

| q2-pod | here |
|---|---|
| `tools/build.py` `append_payload`, `HOOKS`, `patch_word`, `fileoff`, prologue checks | `tools/pod.py` |
| `tools/peq.py` `compile_common` (GOT stubs, FLAGS, trampoline) | `tools/pod.py` `gen_asm` / `compile_payload` |
| `patch/link.ld`, `patch/offsets.inc`, `patch/contexts.inc` | `patch/link.ld`, `patch/offsets.inc`, `tools/pod_pages.py` |
| `patch/navigation.c` and friends | `patch/m1pod.c` |
| `patch/coverflow.c` (2152 lines, wheel-driven) | `patch/coverflow.c` (the renderer and cache design, touch-driven, stock queries of this model) |
| `test/coverflow.py` | `test/coverflow.py` |
| `test/patch.py` (Unicorn) | `test/patch.py` |
| iPod menu design (`docs/ipod.md`, `ipod.json`) | the Stage C menu geometry/look |

q2-pod hooks dozens of sites for a full scroll-wheel reskin; M1 Pod deliberately hooks **one**
user-initiated site and adds pages, which is all the safety budget allows for a first code mod on an
unverified-recovery device.
