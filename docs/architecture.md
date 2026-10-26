# Architecture: pipeline, payload, hooks, guard

How the release (V2.1kE) is built and what its code does. The looks (assets) are in `docs/ui.md`,
firmware facts and the space step in `docs/firmware.md`, make/test/flash in `docs/workflow.md`, the
tag history and lessons in `docs/history.md`.

## 1. Pipeline

`tools/build.py` builds the release from the pinned official zip (`firmware/`, SHA-256 in
`build.py`); `--restore` repacks stock with tag V2.1R. Every step edits one work tree in place
(`work/mod-release`, per checkout); inputs resolve through `tools/paths.py`.

| # | step | what |
|---|---|---|
| 0 | `fwtool.py unpack` (first run only) | `work/stock`: `rootfs/`, `recovery-update/`, `stock.pseudo` (exact inode metadata), `meta.json` |
| 1 | `mod_battery.py STOCK TREE` | clones stock into the tree; unified battery in the status bar and the pull-down |
| 2 | `mod_font.py` | Inter + Source Han Sans; runs here so every later step measures the new font |
| 3 | `mod_space.py` | zero demo's `.pdr`, remove 10 unreferenced files (`docs/firmware.md` section 4) |
| 4 | `pod.py` | compile the payload, append it to `demo`, install three hooks, apply the library-row edits, write the four `ui/m1pod_*.bin` |
| 5 | `mod_theme`, `mod_lists`, `mod_nowplaying`, `mod_boot`, `mod_ipodrows`, `mod_pulldown`, `mod_lockscreen`, `mod_wallpaper`, `mod_icons`, `mod_polish` | the asset looks, in this order (`docs/ui.md`) |
| 6 | `mod_theme.py --scan TREE STOCK` | contrast scan of the finished tree |
| 7 | `fwtool.py repack --tailends --allow-removed ... --allow-added ...` | squashfs (LZO, 128 KiB blocks, tail ends), metadata-exact; refuses a rootfs larger than stock or any unlisted added/removed file; `verify` follows |

Each step lists the files it adds through an `added_rels()` function, which `build.py` passes to
`fwtool --allow-added`. `work/mod-release/podbuild/` (manifest.json, patch.elf) stays for the tests.
Builds are deterministic (added files get fixed mtimes); `tools/check.py` compares the package with
`test/golden.sha256`. Order matters: lock screen layout needs `mod_nowplaying`'s `np_*` glyphs and the
final font; icons run late so they override the theme step's grey discs; the lock screen step also
patches four words of `demo` and so runs after `pod.py`.

Toolchain for the payload: Homebrew clang/LLD/llvm-objcopy/llvm-readelf (`$LLVM_BIN`, `$LLD_BIN`;
Apple clang has no MIPS target), unicorn 2.1.4 for the tests, mksquashfs 4.7.5. Python runs with `-I`
on anything touching extracted firmware.

Source map: `patch/m1pod.c` (hook, pages, rows), `patch/coverflow.c`, `patch/artists.c`,
`patch/shuffle.c`, `patch/albuminfo.c` (the album view's hook), `patch/rows.c` + `patch/rows.json`, `patch/home.c` + `home.h`, `patch/offsets.inc`
(every stock offset with its evidence), `patch/link.ld`; `tools/pod.py` (build and pins),
`tools/pod_pages.py` (pages and rows, one source of truth), `tools/pod_ui.py` (page assets).
Tests: `test/patch.py WORKDIR` runs `test/pod/<module>.py` (menu, coverflow, assets, artists, rows,
albuminfo, shuffle, home) on `test/pod/harness.py`; `test/coverflow.py` (host build of the renderer),
`test/demo_diff.py`, `test/awtk_fill.py`.

## 2. The payload

M1 Pod adds new pages to the UI app by injecting machine code into `/release/bin/demo`, the way
q2-pod does on the Shanling Q2 (MIT, `NOTICE`). The M1 Plus runs the same stack (X2000 MIPS32r2 LE,
Linux 5.10, Buildroot glibc, AWTK, a `demo` ELF with a spare `PT_NULL` program header); only
addresses, symbols and pages differ.

### The segment

`demo` is `ET_EXEC`; its LOAD segments end at va `0xa10fc8` and `PH[10]` is an unused `PT_NULL`.
`pod.py append_payload` pads the file to 64 KiB, appends `patch.bin` and rewrites `PH[10]` into a
file-backed `PT_LOAD` at va `0xb00000`, RWX, `filesz == memsz == len`, align `0x10000` (the mapping
is checked not to overlap any segment; the ELF still parses with pyelftools, `elfinfo.py`, `dis.py`).
The payload keeps no `.bss`: writable state (312 bytes) is a zero-filled `PROGBITS` `.scratch`
section, so `memsz == filesz` holds; `pod.py` rejects a non-empty `.bss`/`.sbss` and checks `.scratch`
is inside the payload and shipped zeroed. Everything larger (Cover Flow's frame and textures, job
array, album copy, album header cover) is heap, allocated when the page opens and freed on close.
Current payload: 28,888 bytes. Compiled non-PIC (`clang --target=mipsel-linux-gnu -march=mips32r2
-mabi=32 -mfp64 -mno-abicalls -fno-pic -G0 -Oz`, `-Wall -Wextra -Werror`), linked by `patch/link.ld`
at `0xb00000` with `--gc-sections`, sources in this order: `m1pod.c coverflow.c artists.c shuffle.c
albuminfo.c rows.c home.c`.

### $gp and the trampolines

Every stock PIC function starts with `lui $gp,hi; addiu $gp,$gp,lo; addu $gp,$gp,$t9` which makes
`$gp = 0xa03ed0` (`DT_PLTGOT + 0x7ff0`). The payload needs no `$gp` of its own and reaches stock code
and data by absolute address. Each hook has a trampoline that restores `$gp` and resumes the stock
function past its 3-word prologue (`lui $gp,0xa03e; ori $gp,$gp,0x3ed0; j <fn+12>; nop`).

### Calling stock code and libc

- **Stock functions** are absolute-address macros in the generated `stock.h`
  (`#define widget_lookup ((void*(*)(void*,const char*,int))0x666a74u)`); the callee sets up its own
  `$gp` from `$t9`. `pod.py FUNCTIONS` lists every one with its address and checks each against
  `.dynsym` before writing; `DATA` pins the exported data (`pdeq_showlist` `0xa045d8`,
  `parse_cover_mutex` `0xa04588`, `g_class_type` `0x97cad4`, `classinfo` `0xa0c768`).
- **libc** only through slots `demo` already imports: a stub `lui/ori $t8, slot; lw $t9,0($t8); jr
  $t9` tail-calls the resolved pointer (`pod.py LIBC`: atoi, access, open/read/write/close/fsync,
  memset/memcpy/strcmp/strcasecmp/strdup/snprintf, calloc/free, fopen/fclose/fread/fwrite/fseek/ftell,
  rename/unlink/mkdir/statfs, pthread_create/join, mutex lock/unlock, the libcstl deque calls). No
  new imports are added.

### The three hooks

1. **Home icon click dispatcher** `0x533b80` (unnamed in `.dynsym`; registered on each Home icon by
   `home_page_init` via `widget_on(icon, EVT_CLICK=0x10c, ...)`). Pinned prologue `(0x3c1c004d,
   0x279c0350, 0x0399e021)` is overwritten with `j m1pod_home_click; nop`; resume `0x533b8c`. It opens the menu for
   id 99 (the M1 Pod icon) and, as the recovery fallback (section 9, Recovery), for id 1 (Tidal) while
   `/mnt/data/m1pod-bad` exists; every other tap goes to stock.
2. **`home_page_init`** `0x534cd4` (the boot guard, section 7). Pinned prologue `(0x3c1c004d,
   0x279cf1fc, 0x0399e021)`, `$gp` checked, overwritten with `j m1pod_home_init; nop`; resume `0x534ce0`.

3. **`albuminfo_listitem0_layout`** `0x526264` (the album page's header builder; patch/albuminfo.c,
   section 8). Pinned prologue `(0x3c1c004e, 0x279cdc6c, 0x0399e021)`, `$gp` checked, overwritten with
   `j m1pod_albuminfo_header; nop`; resume `0x526270`. Its only callers are `albumdeinfo_listitem_layout+0x1d0`
   (`0x526564`: the list builder of `albuminfo_page_init` and of the page's to-foreground rebuild), so it
   runs only while that page builds its list: never at boot, in the main loop or during paint. The hook
   runs the stock function to completion, then restyles its four widgets; any mismatch leaves stock.

`pod.py` asserts the three prologue words and the resulting `$gp` of each hook before writing, checks
that no row edit touches a hook site, and pins the input `demo` by SHA-256 (the `.pdr`-zeroed stock binary).
Nothing else is hooked: no prologue is rewritten for the library rows (they are call-site edits,
section 6), and nothing runs in `platform_init`, the main loop or paint.

### What the entry does (`patch/m1pod.c`)

`m1pod_home_click(icon, e)`: read the icon's name (`icon + 0x10`, stock stores the Home id as a
decimal string), `atoi` it; if it is not the entry id (`POD_ENTRY_ID` = 99, the icon patch/home.c adds; Tidal, id 1, is stock), or the kill-switch
file exists, or the page fails to open, tail into `stock_home_click_trampoline` (unchanged stock
behaviour). Otherwise `window_open` the entry page, bind `btn_return` -> `navigator_back`,
`btn_backtoplayer` -> `on_backtoplayer_onclick` and each `pod_rowN` to its action, return 0.

Pages are defined once in `tools/pod_pages.py` (`PAGES`: menu, Cover Flow, Artists, Shuffle, Settings) and
consumed by `pod_ui.py` (assets) and `pod.py` (the C row/page tables in `stock.h`), so a row's widget,
label and handler cannot drift apart. Row actions: `ACT_HOME` (open a stock Home destination through
the dispatcher with a fake numeric-named icon), `ACT_PAGE`, `ACT_PLAYER` (stock
`on_backtoplayer_onclick`), `ACT_COVER`, `ACT_SHUFFLE`, `ACT_ARTISTS`, `ACT_GRID`, `ACT_STARTUP`. The
menu is Now Playing, Cover Flow, Shuffle (-> Shuffle page), Songs, Albums, Artists (-> our list),
Genres, Folders, Playlists, Settings (-> Settings page: System Settings and Play Settings through the
stock dispatcher with ids 17 and 16, Shanling Home, Start in). Page layout: `docs/ui.md`. To add a
page: add a `Page` and a row to `pod_pages.py`, rebuild (assets and tables regenerate), add a test
module under `test/pod/`.

### Why the entry is an added icon

Up to V2.1jA the entry was the Tidal icon (id 1, taken over). It is now an icon of its own, id 99 ("M1 Pod"),
which `patch/home.c` adds to the stock grid (section 9), so Tidal opens Tidal again. The icon has no stock
id, so it cannot be hidden in Home customisation (the grid rebuild drops it; `hm_fg` puts it back), and the
dispatcher's bounds check (`sltiu 0x12`, `0x533ba8`) sends an id outside 0..17 to its default (nothing), so
a tap that reaches stock with the kill switch on is harmless. The HiFi store (id 0) was never usable: demo
only puts it on Home when the `language` global is 0 (Simplified Chinese), and patching that check needs
branch patches on the boot path (`reset_homemenu_index`, `load_home_menu`).

## 3. Known addresses (stock V2.1 `demo`)

Payload `PT_LOAD` `0xb00000`; `$gp = 0xa03ed0`; hooks `0x533b80` (Home icon dispatcher, registered
through `widget_on`, GOT slot `0x9fe700`), `0x534cd4` (`home_page_init`) and `0x526264`
(`albuminfo_listitem0_layout`). `.pdr` is zeroed in `demo`
only; the About version string stays `V2.1`. Find more with `tools/dis.py` (`sym`, `addr`, `xref`,
`strxref`, `callers`, `strings-xref`, `full`).

Pinned stock functions, beyond those in the sections below: `widget_lookup` `0x666a74`, `widget_on`
`0x666d20`, `widget_set_text_utf8` `0x66f720`, `navigator_back` `0x4d20dc`, `on_backtoplayer_onclick`
`0x4cd58c`, `window_open` `0x679fd4`, `widget_set_visible` `0x66c394`, `widget_set_sensitive`
`0x666b9c`, `slide_menu_set_value` `0x61399c`, `window_manager` `0x6774b4`,
`window_manager_get_top_main_window` `0x6774f0`, `widget_is_window_opened` `0x66aa04`. Also pinned:
the stock `slide_menu` constructor `0x613914` stores `value = 1` (`sw 1, 0x78` at `0x613970`);
`slide_menu_set_value` -> `0x6120ac` (events `0x11b`, `0x11c`); `songtable` record fields `year`
`+0x30`, `track` `+0x3c`, `cd_num` `+0x40`, `time`/`time_end` `+0x48`/`+0x4c` (CUE offsets, 0 for
ordinary files; no duration column); `toolsLoadAllFile` `0x5efd98` and its insert `0x5edb18`;
`get_screensaver_image` `0x4d7524` (`screensaver_default`, the default wallpaper).

### Home icons and their conditions

The Home grid is built by `home_page_init` (`0x534cd4`) -> the page builder (`0x534064`) -> the icon
builder (`0x533d8c`), which walks a `deque` of 8-byte records `{int id; char shown; ...}` at
**`0xa045c0`**, six icons per slide page. For each record it calls `get_homemenu_showinfo(id, buf)`
(`0x4d9ffc`), indexing an 18-entry table at **`0x97c940`** for the name; the style is
`home_<name>_style`, the label `widget_set_tr_text(<name>)`, and the widget **name is the decimal id**
(`tk_snprintf("%d", id)`), which the dispatcher `0x533b80` reads back and `atoi`s.

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

Which ids are in that deque:

- `reset_homemenu_index(0)` (`0x4d8114`, the defaults) clears it and pushes every id of `main_allmenu`
  (`0x97ca88`, exactly `0..17`) with `shown = 1`, except that when the `language` global (`0xa05ab8`) is
  non-zero it skips `id == 0` (`lw $v1, language; beqz $v1, push; lw $v0, id; beqz $v0, skip` at `0x4d8170`).
- `reset_homemenu_index(non-zero)` loads the saved list (`get_menu_file`, config `[MAIN] HOMEMENU`); if
  `change_lanflag` is set it removes ids 0 and 1 and pushes them back at the front (both when
  `language == 0`, only one otherwise), then saves. A language change therefore puts Tidal first.
- `load_home_menu` (`0x4d7dc4`) builds the customisation dialog's list (`0xa045c4`) from the saved list
  plus every `main_allmenu` id not in it with `shown = 0`, with the same `language != 0` skip for id 0.
- The user can show/hide any other id in Home customisation (`dialog/homemenu_dialog`).

`language` values (`switch_language` `0x4cca40`, jump table indexed by `language - 1`, Simplified
Chinese the default case): 0 (and anything outside 1-12) `zh_CN`, 1 `zh_HK`, 2 `en_US`, 3 `ja_JP`, 4
`ko_KR`, 5 `fr_FR`, 6 `ge_DE`, 7 `sp_ES`, 8 `it_IT`, 9 `th_TH`, 10 `po_PL`, 11 `ru_RU`, 12 `uk_UK`. The
HiFi icon exists only in Simplified Chinese; in English the default list is ids `1..17`.

### The stock library flow (record layout)

Browsing records are `stSongInfo` (0x58 bytes, `REC_*` in `offsets.inc`; read from the row callback
`0x4e93c8` / `0x4e908c`): `REC_ID`, `REC_TITLE` `+0x10` (an artist row's name too), `REC_ALBUM`,
`REC_ARTIST`, `REC_PATH` (`fileurl`), `REC_NAME`, `REC_CLASS` `+0x38` (stamped by `loadSongList`),
`REC_TRACK` `0x3c`, `REC_DISC` `0x40`, `REC_YEAR` `0x30`, `REC_CUE_START` `0x48`, `REC_TYPE` (8 = song,
4 = a card row), `REC_SIZE` `0x58` (`memset(local, 0, 0x58)` in `loadSongList` `0x4e2e4c`). The type's
copy function `0x5db54c` (registered by `_type_register(0x58, "stSongInfo", ...)` at `0x5dbc7c`)
duplicates every string at `+0x04..+0x2c` (the album artist at `+0x24` included) and copies the words
at `+0x00`, `+0x30..+0x50`, so `deque_assign` / `_deque_push_back` give a page its own copy.
Stock queries the payload runs:

| step | call | evidence |
|---|---|---|
| albums | `loadLocalClassList(0xf003)` (`0x4ee504`) -> `getAllAlbum` (`0x4ea3c4`) into `*pdeq_showlist` | what the Albums page runs |
| songs | `loadLocalClassList(0xf001)` -> `getAllMusic` | `allmusic_page_init` `0x528a44` |
| artists | `loadLocalClassList(0xf004)`: `GetAllAlbumArtist` (`0x4ea6e4`) when `artist_type` (`0xa05a14`) == 1, else `getAllArtist` (`0x4ea9d8`) | jump table `0x74c5b8` entry `0xf004` -> `0x4ee6e8`; `localclass_page_init` `0x536bb0` |
| an artist's albums | `loadAlbumList(0xf004, row)` (`0x4ee8d8`) -> class `0xff01` (`getAlbumByAlbumArtist` `0x4eb0e4` / `getAlbumByArtist` `0x4eaccc`) | `album_page_init` `0x5248b8`; clears `classinfo_save`, stores the artist (row `+0x24` when `artist_type` == 1 else `+0x18`) |
| the All songs row | the list's last row: `REC_ID` -2, type 4, `REC_ARTIST` = the artist | `getAlbumByArtist` appends it always (`0x4eae30`) |
| an album's tracks | `loadAlbumdetailList(0xf003, row)` (`0x4eea98`) -> `loadLocalClassList(0xff10)` -> `getMusicByAlbum` | `albuminfo_page_init` `0x5268bc`; fills the browsing record `0xa0c768`; an artist's album: `0xff01` -> `0xff11` (`getMusicByAlbumAnd[Album]Songer` `0x4ed008` / `0x4ecd3c`); All songs row (`classinfo[8]` = 1, `0x4eebec`) -> every song of the artist |
| opening the album page | `navigator_to_with_context("albuminfo_page", class \| row << 16)`: the context is an integer, not a pointer. The Albums row handler `0x523d94` builds it from `g_class_type` (`0xf003` Albums, `0xff01` an artist's albums) and the row; the Search handler `0x540588` assigns its albums into `*pdeq_showlist` first and passes `0xf003`. `albuminfo_page_init` (`0x526828`) reads the album row from `*pdeq_showlist`, runs `loadAlbumdetailList(class, row)`, `add_albumcover_task(row, 1)` and stores `classinfo[0]` in `g_class_type` | the page expects `*pdeq_showlist` to be the album list the row came from and the cover-task list (`albumcoverinfo_init` `0x4dcf9c`, which `album_page_init` `0x5248d0` runs right after `loadAlbumList`) built from it |
| the album page's header | `albuminfo_listitem0_layout` `0x526264`: a 100 px `list_item` (`list_item_notpress_style`) holding the `img_albumcover_m` image 100x100 (draw type scale-auto, file `/tmp/abp/<md5>1.jpg` set by `0x525a38` once the cover task has made it), the title `hscroll_label` (`0x524990`, `srlabel_item_white_style`, text `classinfo+0xd`), the artist (`0x524a64`, `srlabel_item_gray18_style`, `classinfo+0x20d`) and the Play all `button` 90x28 (`btn_imgplayall_style`: an orange pill image with its text baked in); row 0 of the scroll_view, the 64 px track rows follow | the cover thread (`parse_albumcovertask_thd`) renders the flag-1 file at `0x64` px (`addiu s3, zero, 0x64` at `0x4dd670`; the flag-0 files of the Albums rows at `0x3c`); the file's only reader is this page |
| Play all | the button handler `0x525d48`: the list's first track, `loadSongList(queue, name, cue, g_class_type)`, `start_player(queue, index, class, 2)` (`0x4e4648`), `force_refreshflag` `0xa05a63` = 1; the page stays up | what the Shuffle button copies |
| play | `loadSongList(queue, name, cue_start, cls)` (`0x4e2ce0`) then `navigator_to_with_context("playing_page", {queue, index, cls, 2})` (`0x4d1d48`) | the row handler `0x5275a4`; `loadSongList` also fills `g_memory_info` `0xa0caf8` for memory playback |
| art | `toolsGetAlbumCover` `0x5eaee0` (embedded) then `toolsGetExternCover` `0x5eafec` (folder image) | order and lock of `parse_albumcovertask_thd` `0x4dd68c` |

## 4. Cover Flow (`patch/coverflow.c`, test `test/pod/coverflow.py`, `test/coverflow.py`)

A cover carousel over the stock Local Music albums, ported from q2-pod's `patch/coverflow.c` to the
320x480 touchscreen (wheel-only parts gone). Opened from the menu's Cover Flow row; adds no hook:
everything runs from the page's own widgets, one timer and one worker thread. Also opened per artist
(section 5).

- **Covers.** One cover per album on a stock `slide_menu` (index, offset, wrap) drawn by the payload's
  depth renderer: the centre cover faces you at `ART_SIZE` 168 px, the neighbours turn 60 degrees
  inward, step back and dim (`CF_BRIGHT1` 192, `CF_BRIGHT2` 128 of 256, gone three out), each with a
  26 px reflection. Geometry (`offsets.inc`): frame 320x276, `CF_TOP` 31, `CF_EYE` 312, `CF_X1` 110,
  `CF_XS` 48, `CF_Z1` 96, `CF_ZS` 22, `DRAG_PX` 108. Change them together and re-run
  `test/coverflow.py`.
- **Renderer.** After Rockbox PictureFlow via q2-pod; all integer (16.16 turns, 1/16 px geometry, 1/256
  px row spans). One `bitmap_create_ex(320, 276, ..., RGBA8888)` frame plus 7 textures of 168^2 and one
  placeholder: about 1.26 MB of heap while open. If an allocation fails the page falls back to flat
  covers (the `slide_menu`'s own `image` children show the cached JPEGs, `ART_NEAR` 3 either side).
  The frame is drawn from the touch layer's `EVT_AFTER_PAINT` (`0x120`, dispatched by `widget_paint`
  `0x66de3c`), an instance event registered with `widget_on`. The position comes only from stock
  properties (`value`, `xoffset`, `h`): `p = value - xoffset/h` (the stock commit is `value -
  round(xoffset / item width)`, the item width being the widget height, `0x612360`), so no field
  offset of the `slide_menu` is pinned. About 3.45 M payload instructions per frame under Unicorn.
- **Touch.** A transparent full-size touch layer (a `view` over the `slide_menu`, inside
  `view_covers`) takes `EVT_POINTER_DOWN/MOVE/UP` (`0xff/0x101/0x103`) and abort `0x107`, grabs the
  pointer (`widget_grab`/`ungrab`) and drives the `slide_menu` through `xoffset` and
  `slide_menu_set_value`: the shelf follows the finger, a release coasts by the fling (120 ms, at most
  3 albums) and snaps with a 16 ms timer animation, then commits (`xoffset` 0). A release within 12 px
  is a tap hit-tested by x: the centre cover (`|x - 160| < 84`) opens the album, a side cover comes to
  the centre. The `slide_menu` itself is insensitive. Back leaves the page.
- **Captions.** `label_album` / `label_artist` are `hscroll_label`s configured as Now Playing's info
  lines (`loop`, `yoyo`, `lull` 3000 ms, centred, `ellipses`, 22 px white / 18 px `#AAAAAA`, in 16 px
  margins): a long title scrolls back and forth with a pause at each end, a short one is centred
  (`hscroll_label` paint `0x609cbc` -> `hscroll_label_start`; setting text resets the scroll `0x60a49c`).
  They are insensitive and never hidden: they lie over the frame's black rows, so a tap on the album
  name reaches the touch layer and opens the album. There is no hint line.
- **Start index.** The stock `slide_menu` starts on item 1, not 0; the page always calls
  `slide_menu_set_value(cf.slide, cf.album)`, so an artist's page opens on its first album, a
  one-album shelf has its captions on open, and the main page keeps its last-album memory
  (`/mnt/mmc/.coverflow/album`, including album 0).
- **The album.** Tapping the centre cover opens the stock `albuminfo_page` (section 8), as a stock
  Albums row does: `loadAlbumList(0xf003, 0)` puts the stock album list back into `*pdeq_showlist` (the
  page's own copy was made from the same query, so the row is the same), `albumcoverinfo_init` rebuilds
  the cover-task list from it, `batchadd_albumcover_task(0, 0)` releases the cover thread (see section 8, The cover), and `navigator_to_with_context("albuminfo_page", 0xf003 | row << 16)`
  opens the page. The queries repeat on every tap (the page may have been left through Now Playing, and
  anything may have reused the list or the browsing record). Back from the album page returns to the
  covers; the page keeps no track list, header or play code of its own.
- **Cache.** The page keeps its own `/mnt/mmc/.coverflow/<key>-168.jpg` thumbnails (the size is in the
  name; key = FNV-1a of artist then album, never 0). The stock cache `/mnt/mmc/.downpic` is keyed by an
  MD5 the payload cannot reproduce and holds 90 px images, so Cover Flow only reads through the stock
  extractors. First open builds the thumbnails on a "Preparing covers... n/m" screen with Cancel (a
  cancelled build resumes); one pthread runs `build_art` over jobs built on the UI thread, touching
  only its jobs, three `volatile` counters, files under `.coverflow` and the two stock art calls under
  `parse_cover_mutex` (`0xa04588`, the lock every stock caller holds; `parseplaycover_thd` takes the
  same one). Each file is written to `.tmp` and renamed; both extractors failing leaves an empty
  marker (not retried); a vanished track leaves none. No build below 16 MB free (`statfs`), without a
  card or if `pthread_create` fails. A 250 ms timer polls the counters; Cancel and closing set the
  cancel flag and `pthread_join` (bounded by one album). `EVT_DESTROY` removes the timer, joins, frees
  everything. Nothing is written outside the card.
- **Not ported from q2-pod:** Sort and Refresh cards, the rated scope, A-Z jump, the album split by
  album-artist/folder, the audiobook filter, the ffmpeg WebP fallback, wheel/ringnav. To clear the
  cache delete `/mnt/mmc/.coverflow` from a computer.

## 5. Artists (`patch/artists.c`)

`ACT_ARTISTS` opens `ui/m1pod_artists.bin` (navbar over an empty stock `list_view`/`scroll_view` plus
scroll bar and a hidden `label_status`), copies the stock artist list (`loadLocalClassList(0xf004)`,
section 3) into its own deque and adds one 52 px stock-styled row per artist (at most 2000) with the
`right_arrow` chevron; the order, names and artist/album-artist switch are the stock Artists page's
(the payload never reads or writes `artist_type`). "Update Local Music first" for an empty library.
Statics are prefixed `ar_`.

A tap calls `coverflow_artist(list, index)`: the same page, renderer, cache and touch layer scoped to
the artist (q2-pod's `ARTIST_ALBUMS`, `cf.scoped`):

- **Albums** `loadAlbumList(0xf004, artist)`, copied into the page's deque with the artist's row.
- **Cards.** The stock list's last "All songs" row is kept as the **All albums** card with two albums
  or more (caption "All albums" over the artist, placeholder art, no cache file, tracks = every song
  of the artist), dropped with one.
- **Covers.** Each album takes the cache key of the library album of the same name (`strcasecmp`
  against `getAllAlbum`'s rows, grouped by name `COLLATE NOCASE`), so the page shows the main page's
  files and builds only covers the library lacks (a compilation's library row names whichever artist
  SQLite returned).
- **The album** `loadAlbumList(0xf004, artist)` (the artist goes into the browsing record, the artist's
  albums and the stock All songs row into `*pdeq_showlist`), `albumcoverinfo_init`, `batchadd_albumcover_task(0, 0)`, then
  `navigator_to_with_context("albuminfo_page", 0xff01 | row << 16)`, the context the stock artist page's row
  handler builds (`0x523d94`); the page runs `loadAlbumdetailList(0xff01, row)` itself and leaves class
  `0xff11` (the All albums card: every song of the artist). On every open, as in the main Cover Flow.
- **Ends.** The shelf does not wrap (ring slots past either end stay empty, drag clamped, fling and
  side taps stop at an end); the main page still wraps.
- Title is the artist; the scope never reads or writes `/mnt/mmc/.coverflow/album`; "No albums" when
  empty; Back goes covers -> Artists -> menu. The stock list always ends with "Unknown
  Artist" (id -1), which opens to "No albums" without untagged songs. A refused second open while Cover
  Flow is open.

Borrowed from q2-pod: the scope, the bounded shelf, the All albums rule; not borrowed: its hook on the
stock artist page and its own SQL album list (here the stock page's own list and the stock All songs
row, so no hook). Risks: one row per artist is created up front (slow with thousands); the flat
fallback is not bounded; renamed albums mid-rescan get their own key. Future: A-Z jump (the stock rows
carry an index letter at `+0x54`, which the copy function does not copy), a Sort card.

## 6. Library rows (`patch/rows.c`, `patch/rows.json`)

q2-pod's restyle of the stock library pages (from its `patch/ipod.json`, `compact_set_row_layout` /
`compact_row_layout`): Songs (and Hi-Res, Favourites, Recent, Most played, a playlist's songs),
Folders, Artists/Genres/Composers, Albums, an album's tracks, Playlists, Search and Now Playing's jump
list get 64 px rows on a 60 px body, 52 px album art drawn 1:1, 21 px titles to a 12 px right margin,
and long titles ending in an ellipsis instead of all scrolling at once. These rows are built by demo's
row constructors with their sizes as `addiu` immediates, so an asset can only choose the pitch; hence
pinned edits plus a small payload function. Constants: `PITCH 64` (Folders divides `yoffset` by 64
with `(y + 63) >> 6` at `0x531bac/0x531bb8` and `0x532488/0x532498`), `BODY 60`, `ART 52`,
`ART_INSET 4`, title box y 7 / h 24, meta y 33 / h 20, `ROW_RIGHT` 12.

| page | stock | now |
|---|---|---|
| Songs | row 60, button 56; title 200 wide, 20 px at y 10; artist 175 at y 30 | row 64, body 60; title x 60..298 (238), 21 px in 24 at y 7; grey 18 px line at y 33 (20) full width, 213 after the MQA badge; multi-select 94..298 |
| Folders | row 64/60; title 220, chevron at 288 | title 60..277, chevron 285..298; 60..298 for a song file |
| Artists / Genres / Composers | row 60, button 56, title 220 | row 64, body 60, title 60..277, chevron 285..298 |
| Albums | item 60, cover 60 at x 0, title 180 at y 10, chevron 296 | item 64, cover 52 drawn 1:1 at (4,4), title/artist 60..277 at y 7/33; 8 covers per batch (was 7) |
| an album | track rows 60, "N title" 260 wide; header boxes 20/18 at y 10/30 | track rows 64, "N title" 12..298; header boxes 24/20 at y 7/33 |
| Playlists | items 60, name 220, create label (60,20,220,20), Import/Export (60,20,90,20) | items 64, name to 12 px before the arrow, create label (60,18,238,24), Import/Export y 18, 24 high |
| Search | tab rows 64, title 250 at y 10, album covers 60, scroll-end divides by 120 | title 238 at y 7, artist y 33, covers 52 at x 4, divides by 64 |
| jump list | row 60, button 56, text 200, rebind 250x56 | row 64, button 60, text 238, title (0,7,238,24), artist y 33, rebind 238x60 |

Every title is 21 px (`srlabel_item_white_style`/`gold20` per page theme, `mod_lists.py`), the
second line stock's `srlabel_item_gray18_style`; hscroll_labels scroll only while focused
(`hscroll_label_set_only_focus`), which on this touch UI no row is.

**The demo edits** (`patch/rows.json`, applied by `pod.py patch_rows`, every listed word checked
against stock first; the build refuses any mismatch): 59 edits and 26 more words pinned unchanged.
46 `addiu rt, $zero, imm` immediates (pitch, body, rebind size, cover width, the cover thread's
thumbnail size 60 -> 52 at `0x4dd604` and the album page header cover 100 -> 120 at `0x4dd670`, title/meta boxes, Playlists labels, cover batch); 10 call sites
where each ordinary row constructor's `jalr $t9` to `widget_set_children_layout(row, "default(...)")`
becomes `jal compact_set_row_layout` (layout string left in the delay slot): Folders `0x5332bc`, Songs
`0x528624`, Artists `0x53696c`, Albums `0x524494`, album tracks `0x52651c`, Playlists `0x53e6ec`,
Search tracks/artists/genres/albums `0x541924/0x542208/0x542560/0x542930`; 3 nops (the Folders,
Artists and Songs rebinds' `widget_resize(title, 220/250, h)` at `0x532f6c`, `0x535e94`, `0x527918`;
the jump list's `0x5390ac` stays, patched in width/height). Pinned unchanged: the folder pitch, bodies
already 64/60, the `>> 6` divisions, the shared layout strings `0x745158/0x745360` and the default
layouter's vtable slot (`0x904924`, layout fn `0x63a444`).

**The row fit.** `compact_set_row_layout(row, params)` calls the stock `widget_set_children_layout`,
then, if it succeeded, the layouter is the stock default one (checked at run time and build time) and
the kill switch is absent, points it at a copy of the default vtable in `.scratch` whose layout slot
is `compact_row_layout`, which on each layout: finds the text (first `hscroll_label`, or the first
child holding one), gives it the row width minus left margin, right margin (at least 12) and every
other visible child's width + spacing; lays `list_item` rows out 4 px short so children sit on the
60 px body above the separator; calls the stock default layout (anything unexpected -- no layouter,
no text, more than 16 children, a hidden title -- leaves it to stock alone); then moves an x=0 row's
cover to x 4 and stretches a line's last label to the view's end. No relayout loop: every value is the
same on every pass (a widget's resize marks the window for relayout; `widget_resize`/`widget_move`
return early on an unchanged size, `0x66d198`). About 1.8 KB of payload.

**Safety.** `tools/reach.py` builds an over-approximate graph of stock demo (12,162 functions; an edge
for every call, GOT load or address taken) and walks it from `main` and `platform_init` except through
the navigator's open-by-name dispatcher (`sub_4d00c0`): none of the 25 functions holding an edit is
reachable, except `parse_albumcovertask_thd`, started at boot, which sleeps 50 ms, takes a task from
the cover task list and loops when empty; its producers are not reachable at boot either, and the edit
is the thumbnail size constant (tmpfs files, read only by the Albums and Search album rows, both now 52
px). No prologue is rewritten, the payload runs only where the patched instruction ran, `$gp` is
reloaded by every patched caller from its stack slot (checked at all ten sites), and nothing is hidden
or shown (hit testing unchanged). The kill switch `/mnt/mmc/m1pod-off` turns the fit off (stock layouter);
the 46 immediates and 3 nops are static, so the way back from them is a stock re-flash.

## 7. Shuffle (`patch/shuffle.c`)

The Shuffle page (`ui/m1pod_shuffle.bin`, opened by the menu's one Shuffle row as in q2-pod's Library)
has three rows: **Shuffle Songs** (the library, stock Shuffle mode, from a random song), **Shuffle
Albums** (albums in random order, each in track order), **Shuffle Folders** (folders in random order,
each in file-name order). One call `shuffle_play(kind)`, no timer, thread or page left behind.

Every row takes the stock Songs path with class `0xf001`: `loadLocalClassList(0xf001)`;
`loadSongList(queue, name, cue_start, 0xf001)` (copies the list, stamps the class, fills
`g_memory_info`); Albums/Folders reorder the queue; the first file is checked with `access`; the play
mode is set if needed; `navigator_to_with_context("playing_page", {queue, index, 0xf001, 2})`
(`playing_page_init` -> `start_player` `0x4e4648` copies the queue; the payload destroys its own copy).

- **Songs uses stock Shuffle (mode 2):** `mclNextSong` draws from a pool of unplayed indices
  `mclLoadPlayList` fills with the whole queue (`0x5d5a20` -> `0x5d03b0`, `0x5d1fe0`), so with the
  library as the queue it is "shuffle all", with stock's own Previous, and after a reboot the stock
  resume rebuilds `0xf001` from `getAllMusic` (`memeory_startplayer` `0x4e3714`) with the mode still
  Shuffle. The first song comes from the payload's xorshift32 (q2-pod `rand_below`, seeded once from
  `toolsRandnum` and `time_now_ms`, because stock reseeds from `time()` each call); the payload starts
  on the drawn row itself when the queue's song there is the same file (`loadSongList` matches by file
  name and CUE start, so duplicates like `01.flac` would otherwise always give the first).
- **Albums/Folders build one queue already in play order** and let stock play it sequentially, so no
  hook on the playback path. Group: albums by name with ASCII case folded (SQLite NOCASE, as the Albums
  list groups; no-album songs one group); folders by path up to the last `/`. Groups in Fisher-Yates
  order; inside an album disc, then track (`getMusicByAlbum` comparator `0x4e9020`), then path, then
  CUE start; inside a folder path, then CUE start. Two heapsorts over a 12-byte index
  `{record, group, position}` (no libc `qsort`), then the queue's records are permuted in place
  (cycle-following), so every string stays owned by one slot. Peak memory is what tapping a song in
  Songs uses plus the index (768 KB at the cap).
- **Play mode** is the stock setting changed as Play settings does (`0x49fc78`): `mclSetPlayMode(m)`,
  `notifyPlayMode()`, `dmrSendPlayMode(m)`, `write_int_config(m, "PLAYSET", "PLAYMODE")`; nothing is
  written when already right. Values 0 List play, 1 Repeat one, 2 Shuffle, 3 Repeat all. Songs -> 2;
  Albums/Folders: 1 and 2 -> 0, 0 and 3 kept. The mode stays afterwards (q2-pod restores it with a hook
  on the queue load; not ported).
- **Limits** (stock one-line message box `dialog/msginfo_dialog`, kind 1, 2 s; nothing played, mode
  untouched): "Update Local Music first" (empty), "Storage unavailable" (first file missing), "Too many
  songs to shuffle" (Albums/Folders over `SHUFFLE_MAX` 65536, checked before copying), "Not enough
  memory to shuffle". About 12 M payload instructions for Shuffle Albums over 2,048 songs.
- After a reboot Shuffle Songs resumes and keeps shuffling; Albums/Folders resume on the same track
  and continue in Songs order (the album order is not saved).

Pinned: `mclGetPlayMode` `0x5d3628`, `mclSetPlayMode` `0x5d278c` (mode word `0xa0abe0`; closes a gapless
preload for modes 1, 2), `notifyPlayMode` `0x50ee04`, `dmrSendPlayMode` `0x4f10f0`, `write_int_config`
`0x4d6a2c`, `toolsRandnum` `0x5e0c58`, `time_now_ms` `0x70cf58` (AWTK `uint64_t`, low word in `$v0`).
Mode values: Now Playing's button cycles `(mode+1) % 4` (`0x53b634`, styles at `0x5398cc`); the mode
sequence appears in Play settings `0x49fc78`, Now Playing `0x53b648`, Play More `0x47a54c`. msginfo
context `{int kind; int ms; char text[0x200]; char text2[0x200]}` (`dialog_msginfo_dialog_init`
`0x4786f8`, `0x478884`). Not ported: q2-pod's advanced-playback engine, Up Next, Next/Previous Album,
the audiobook filter, the multi-disc folder merge, and Shuffle Folder from inside the folder browser
(it needs a second hook).

## 8. The album view (`patch/albuminfo.c`, test `test/pod/albuminfo.py`)

There is one album view: the stock `albuminfo_page` (an album's tracks), restyled. It opens from the
stock Albums list, from Cover Flow (main and per artist), from Artists through Cover Flow and from the
All albums card, always through `navigator_to_with_context("albuminfo_page", class | row << 16)` with
`*pdeq_showlist` holding the album list the row came from (section 3: the stock Albums handler's
sequence; Cover Flow and the card repeat it, `coverflow.c open_album`). The stock page loads the
tracks itself (`loadAlbumdetailList`: class `0xf003` -> `0xff10`, an artist's album and the All songs
row `0xff01` -> `0xff11`), builds the 64 px track rows (q2-pod rows, section 6) and the header item.
The payload has no album code of its own except the one hook below (and Cover Flow's one extra call, below).

```
y   0                                         header item 310 wide, 184 high (stock: 100)
    8 +-----------+  Kind of Blue            21 px white   srlabel_item_white_style (stock label)
      |  cover    |  Miles Davis             18 px grey    srlabel_item_gray18_style (stock label)
      |  120x120  |  1959 . 8 tracks         15 px #9C9C9C srlabel_meta15_style (new label)
  128 +-----------+
  136   [ Play all ] [ Shuffle ]            two 110 x 36 buttons, 10 px apart, btn_albumbtn_style
  184   1  So What                             stock track rows, 64 px
```

**The hook** (`m1pod_albuminfo_header`, section 2): `albuminfo_listitem0_layout` `0x526264` builds the
header, called only from the page's list builder (init and the to-foreground rebuild), so a rebuilt page is
restyled again. The hook runs the stock function first (a 100 px `list_item` with, in this order, the
`img_albumcover_m` image, the title and artist `hscroll_label`s and the Play all `button`), then, unless the
kill switch `/mnt/mmc/m1pod-off` exists or the item is not exactly that shape (four children of those
types), creates the year line (`hscroll_label`) and the Shuffle `button` first; if either fails it
destroys what it made and leaves stock; otherwise it moves and resizes the stock widgets to the numbers
above (`AH_*` in `offsets.inc`), gives the Play all button the dark style and the text "Play all" (stock
draws an orange image with its text baked in; the stock style `btn_imgplayall_style` is left in the page
theme, so a header the hook skips is the stock one), keeps its stock handler (`0x525d48`, bound to the
item) and resizes the item to 184. Nothing is renamed or removed (`img_albumcover_m` is looked up by name
by the cover refresh `0x525a38`). The year line is insensitive (a drag over it scrolls the list); the
buttons are 110x36 (V2.1kE: the cover starts 8 px under the navbar and the buttons are smaller, so the track list starts 24 px higher).

**Styles** are the page theme's (`styles/albuminfo_page.bin`, both asset themes, `tools/mod_ipodrows.py`):
`btn_albumbtn_style` (`#1E1E1E` fill, `#3A3A3A` hairline border, 20 px white text, `#3A3A3A` pressed, no
icon) and `srlabel_meta15_style` (the stock grey line's alignment at 15 px `#9C9C9C`: 4.5:1 on the pressed
row, which the page audit tests). The 21 px title is the rows step's.

**Record fields.** `getMusicByAlbum` / `getMusicByAlbumAnd[Album]Songer` (`select * from songtable`)
fill an `stSongInfo` per row via the callback `0x4e908c`; schema: `id, filename, fileurl, album, songer,
style, name, composer, albumsonger, year, track, cd_num, time, time_end, time_create, Initial,
bitdepth, samprate`. `year` is `atoi`'d to `+0x30`; the scanner (`toolsLoadAllFile` -> insert
`0x5edfc4`) writes it from `taglib_tag_year` (`toolsGetMusicInfo` `0x5ec6a8`, `+0x680` of its out
buffer). Shown: year (first track with 1000..2999; the All albums card, `classinfo[8]` set, shows none),
the track count. **No duration**: there is no duration column; `time`/`time_end` are CUE offsets, 0 for
ordinary files, and `toolsGetMusicInfo` reads only the sample rate and an MQA flag, never a length. The
line reads "year . N tracks" or "N tracks" ("1 track").

**Shuffle** (`ah_on_shuffle`) is the stock Play all handler's sequence (`0x525d48`): a random track of
the page's list (`pod_rand`, the Shuffle page's generator), `access` check ("Storage unavailable"),
`loadSongList(queue, name, cue, g_class_type)` (class `0xff10`, or `0xff11` for an artist's album and the
card), the stock Shuffle mode (`pod_set_mode`: `mclSetPlayMode`, `notifyPlayMode`, `dmrSendPlayMode`,
`write_int_config`; nothing is written when already Shuffle), `start_player(queue, index, class, 2)` and
`force_refreshflag` = 1; the page stays up, as with Play all, the queue is this album alone so stock
Shuffle shuffles exactly the album, and the mode stays Shuffle afterwards. A queue that does not resolve
starts nothing and changes nothing. `pod_rand`, `pod_toast`, `pod_set_mode` are three exports at the end of
`patch/shuffle.c`.

**The cover.** The stock header cover is `/tmp/abp/<md5>1.jpg`, rendered by the cover thread
(`parse_albumcovertask_thd`) at 100 px, fitted inside, aspect kept, never upscaled, and drawn into a
100x100 scale-auto image: 1:1 for a square cover. The release renders it at 120 (`rows.json`, one
immediate at `0x4dd670`; this page is the only reader of the `1.jpg` files, tmpfs) and the hook makes the
image widget 120x120 with draw type `center` (stock: scale-auto), so the file, or the 100 px stock
default disc before the cover task is done and for an album without art, is always drawn at its own size
and never scaled (AWTK's scaling is nearest neighbour, `test/awtk_fill.py`); a cover under 120 px (a
small embedded image, a non-square one) sits centred in the 120 px box. With the kill switch the stock
100 px scale-auto widget shows the 120 px file scaled down.

**The cover thread's state** (found on the device, V2.1kD: Cover Flow's album page had no cover). The thread
(`0x4dd450`) sleeps 50 ms while `albumcover_taskstate` (`0xa05a18`) is 2. `albumcoverinfo_init` (`0x4dcf9c`)
sets it to 2 (and clears `albumcover_finishflag` `0xa05a5b`); the batch queuers (`batchadd_albumcover_task`
`0x4dccac` -> `local_albumsmallcover_task` `0x4dcbb4`, `local_songercover_task` `0x4dccc8`) end by setting it
to 1; `add_albumcover_task` (`0x4dca38`, the one `albuminfo_page_init` calls) only clears the task list and
pushes `{row, 0, flag}`. The stock Albums list always runs the batch queuer right after the init
(`album_page_init` `0x5248d0`/`0x52496c`), so the state is 1 by the time albuminfo_page opens; Cover Flow ran
only the init, the thread stayed parked and the page's cover task (and its 500 ms refresh timer, `0x5261d8`,
which picks the `/tmp/abp/<md5>1.jpg` file up when it appears) waited for nothing. Cover Flow now calls
`batchadd_albumcover_task(0, 0)` after the init: no task, state := 1; the page queues its own. The header
shows the placeholder disc until the thread has rendered the file, as from the Albums list.

Not done: a duration, a current-track marker in the track rows (the stock page marks nothing), a
Shuffle that goes to Now Playing (Play all does not either).

## 9. Home and the boot guard (`patch/home.c`, `patch/home.h`, test `test/pod/home.py`)

M1 Pod is the Home screen at start-up. This is the only payload code that runs at start-up, and the
recovery button combination is unverified, so everything is behind a crash marker and falls to stock.

### Boot sequence

```
main -> application_init -> navigator_to("home_page") -> navigator_to_with_context -> page-init dispatcher
 (0x4d00c0, strcmp "home_page" @0x4d1cd8)  -> home_page_init (0x534cd4)    <- the hook
```

`tools/reach.py` confirms this is the only route. The hook `m1pod_home_init`:

1. **runs the stock `home_page_init` to completion** through `stock_home_init_trampoline` and returns
   its result;
2. only if it returned `RET_OK` for a non-null window, runs `home_boot(win)`, where the state is OFF
   (stock) until everything succeeded:
   1. **kill switch** `/mnt/mmc/m1pod-off` (SD, may not be mounted yet) or `/mnt/data/m1pod-off` -> stop;
   2. **marker found** (`/mnt/data/m1pod-run`): the previous attempt never proved itself. Write the
      sticky note `/mnt/data/m1pod-bad`, set `/mnt/data/m1pod-start` to `0`, remove the marker, stop.
      If the note cannot be written the marker stays, so every later boot is stock too;
   3. **bad note found** -> stop (sticky: a crash cannot alternate with good boots);
   4. the setting (`/mnt/data/m1pod-start`: `0` = Shanling, missing or anything else = M1 Pod) is read; it
      no longer stops the guard (V2.1kA): the Shanling start is armed too, because step 7 adds the grid icon;
   5. **write the marker**: temp file, `fsync`, `rename`, directory `fsync`; any failure -> stop with no
      marker left;
   6. **arm**: a one-shot UI timer (5 s, `CLEAR_MS`) removes the marker and fsyncs the directory; with
      no timer the marker is removed at once;
   7. **add the "M1 Pod" icon** to the grid (`hm_add_icon`, below; any failure adds nothing), register a
      Home "to foreground" handler (`EVT_WINDOW_TO_FOREGROUND` `0x12d`) on the Home window, and, when the
      setting is M1 Pod, hide the grid content (`app_gesture`: icon pages + bottom strip, `visible=false`
      and `sensitive=false`; after the marker is durable) and schedule the first pod-menu open (10 ms,
      `OPEN_FIRST_MS`).

#### The grid icon (`hm_add_icon`, `hm_icon_cell`)

The stock page builder `0x534064` (called from `home_page_init` at `0x534de4`, and again from the Home
foreground handler `0x534860` when the icon list changed) looks up `home_sview` (a `slide_view`) and
`home_sindicator`, destroys the pages and makes one 320x364 `view` per six icons (`view_create(sview, 0, 0,
0x140, 0x16c)` at `0x534168`, `deque_size / 6` rounded up) and calls the icon builder `0x533d8c` for each:
per icon a 154x118 `view` at column x 6 or 160 and row y 0/118/236, inside it a 66x66 `image` at (44, 20)
(`image_create`, `widget_set_prop_bool "clickable"`, `widget_use_style "home_<name>_style"`,
`widget_set_name` = the decimal id, `widget_on(image, 0x10c, 0x533b80, image)`) and a 154x36 `label` at y 92
(`label_centerwhitehome_white`, line wrap, the name). `hm_icon_cell` makes exactly that, in that order, with
the name `"99"`, the style `home_m1pod_style` and the text "M1 Pod" (`widget_set_text_utf8`: no translation
needed). `hm_add_icon` takes the **last page's first free slot** (cell `n` = its child count: column
`n & 1`, row `n >> 1`; English Home's 17 icons leave slot 5 of page 3 free); a full last page gets a new
page view (the builder makes as many as the list needs) with the icon in slot 0 and
`slide_indicator_set_max(pages + 1)`. Anything unexpected (no `home_sview`, not a `slide_view`, no pages,
more than 8 pages, a last page that is not a `view` or has more than six cells) or a failed constructor
adds nothing; a partial cell (or page) is `widget_destroy`ed. Newly pinned: `view_create` `0x6346f0`,
`widget_set_prop_bool` `0x670170`, `widget_set_name` `0x6668d0`, `label_set_line_wrap` `0x62e068`,
`slide_indicator_set_max` `0x616b70`, `widget_destroy` `0x66e544`, `window_close` `0x675b70`. Because the
stock rebuild drops the icon (Home customisation), `hm_fg` re-adds it when `99` is not found in Home.

Only one-shot UI-thread timers and plain file calls (`open/read/write/fsync/close/rename/unlink/access`
through demo's own GOT, `timer_add`, `widget_on`). No thread, no polling, nothing in paint or the main
loop; `home_tests` pins the whole set of calls the boot path makes. Newly pinned: `window_manager`,
`window_manager_get_top_main_window`, `widget_is_window_opened`.

**Why this hook and not the Home foreground handler** (`0x534b88`): the foreground event fires when a
window above Home closes but not at start-up (the first open dispatches `WILL_OPEN`/`OPEN`
`0x12a/0x12b`; `TO_FOREGROUND` `0x12d` only comes with a later switch or close: `window_manager_default`
`0x691930`, `0x692a44`, `0x6789f4`, `0x691b3c`). Hooking `home_page_init` gives the start-up trigger and
lets the same function register an extra `0x12d` handler with `widget_on`, so the foreground path
needs no second prologue hook.

### Why it is safe

The stock function runs first and completely; our code runs after it and only on success. Any failure
(no file access, failing `fsync`, no timer, a kill file) leaves the boot stock. **A boot loop is
impossible by construction:** arming needs the marker and the bad note both absent; a start that dies
after arming leaves the marker, the next start writes the sticky note (or, if it cannot, leaves the
marker) and runs stock, and every start after that finds the note or marker and runs stock: at most one
crash, never an alternation. The pod-menu open is covered by the same marker. Costs and residual
risks: a power-off within 5 s counts as a failed start (the next start is stock; choose **Start in: M1
Pod** again); a hang inside `fsync` on a broken flash filesystem would hang the UI thread before the
marker is durable; a later misbehaviour after the 5 s window is not caught.

### Files and the kill switch

| path | meaning |
|---|---|
| `/mnt/mmc/m1pod-off` | SD kill switch: the payload does nothing at boot (no icon), the icon does nothing if it is there, the row fit is off |
| `/mnt/data/m1pod-off` | the same in flash (cannot be created without a shell) |
| `/mnt/data/m1pod-run` | the crash marker: exists from "armed" until 5 s later |
| `/mnt/data/m1pod-bad` | the sticky note when a marker was found; removed by choosing **Start in: M1 Pod** |
| `/mnt/data/m1pod-start` | the setting: `1`/missing = M1 Pod, `0` = Shanling (temp + `fsync` + `rename`) |
| `/mnt/mmc/m1pod-log` | opt-in: if this empty file exists, events are appended to `/mnt/mmc/m1pod.log` (armed, boot ok, marker found, kill switch) |

The setting is an own file, not `config.ini [M1POD]`: `write_int_config` rewrites the shared config
the stock app parses at start-up, and a bad write there is a boot risk.

### The launcher

The menu's last row opens the **Settings** page (`m1pod_settings`, the Shuffle page's machinery), whose rows are
System Settings and Play Settings (stock pages through the dispatcher), **Shanling Home** and **Start in**.
Shanling Home shows the stock grid for the rest of the session (nothing re-opens the pod menu while it is on):
it sets `grid`, shows the grid, closes the menu under the Settings page by handle (`window_close(hs.entry)`: a
second `navigator_back` straight after the first would find the closing page) and then closes the Settings
page with `navigator_back`; with no known menu below it is one `navigator_back`. Tapping the **M1 Pod icon**
(id 99) on the grid, when the setting is M1 Pod and the payload is armed, clears the flag and opens the menu as
the Home instance; a failing open restores the previous state. With "Start in: Shanling" the icon opens a normal
menu. **Start in: M1 Pod / Shanling** flips the persistent setting and rewrites the label (found by type, the
`hscroll_label`, since the icons step makes the icon image child 0; `home_menu_opened` runs for the page that
holds the row, the Settings page). Toggling to M1 Pod takes effect at the next Home foreground event (a
Shanling start is armed, so the foreground handler exists). **The Home instance has no top bar**: the whole
`navigationbar_view` is hidden (`visible=false` and `sensitive=false`) and `pod_listview` moves to y `HOME_PAD` (10) and
resizes to 320x430, its `pod_scrollview` and `scroll_bar_m` keep their widths and take the 430 px height (the
Now Playing row replaces the bars icon; nothing happens if the navbar or the list is not found). The menu
opened from the icon keeps its navbar (Back, "M1 Pod", the bars icon). No setting file = M1 Pod.

### Window stack

The pod menu is not the bottom window: stock code looks Home up by name (`home_page`; the "play from
here" loops stop at it, `navigator_back_to_home` closes down to it), so the menu is opened with
`window_open` above the stock Home, as the Tidal icon did before. The Home window's `TO_FOREGROUND`
event is the single "we are home again" trigger: `hm_fg` only schedules a 10 ms timer; `hm_open` opens
the menu iff the topmost visible normal window (`window_manager_get_top_main_window`) is the stock
Home and it is opened, retrying every 50 ms up to 100 times while Home is not opened yet. Whatever
else is on top (resumed Now Playing, the first-run guide, a library page, a dialog's owner) wins:
nothing is opened and when it closes Home comes to the foreground and `hm_fg` fires. The open is a
one-shot timer, never inside the event, so no window opens while the manager is closing one.

| path | result |
|---|---|
| start-up | the hook schedules the first open: menu over Home (after Now Playing's resume, once closed) |
| go-home idle callback (`0x677a28` -> `0x6777c8`: idle timeout, USB, search, keylock, ...) and `navigator_back_to_home` | force-closes everything above Home (menu too), animates the top one; Home gets `TO_FOREGROUND` -> menu again |
| Back on the Home menu | no navbar, so no Back button; a hardware Back would close the menu and it reopens (a flash, no loop; the loop breaks via Settings > Shanling Home) |
| Back from Now Playing / library pages opened from the menu | their `navigator_back` closes them; the menu is below and becomes top |
| "Back to player", Shuffle's Now Playing | `window_manager_switch_to` restacks/opens `playing_page` above the menu; Back returns to it |
| lock screen / power-off dialog cancel | fullscreen window above / a dialog closes; nothing changes |
| "play from here" / jump-list loops (`0x525908`, `0x538ce4`) | pop with `navigator_back` until `playing_page` or `home_page`; `playing_page` is above the menu so the loop stops first |
| Settings > Shanling Home row | `grid = 1`, `window_close` of the menu, `navigator_back` of the Settings page; `hm_fg` sees `grid` and schedules nothing |

No close animations on the pod pages and nothing in the payload loops on `navigator_back`.
Evidence that the open order is safe and the grid is hidden before the menu appears: the grid content
is hidden from `home_boot` on, the window under the menu is plain black (`home_page` bg `#000000`),
every give-up (kill switch, no top window, Home never opened, `window_open` failure) shows the grid
again, and the stock Home keeps all its widgets so every stock `widget_lookup` resolves. Hiding
`app_gesture` assumes stock never toggles its visibility itself (it would only re-show the grid).

### Recovery

Any bad state: reflash a stock image (`tools/build.py --restore`, V2.1R); it does not touch
`/mnt/data` where the marker and settings live, and nothing stock reads them. A start that cannot
proceed falls to stock by itself after one bad boot. If the device were in a real boot loop (not
expected: the guard acts at the first boot after a failure), the SD kill switch is not reachable
before the hook runs; use the bootloader/recovery flash of V2.1R, whose button combination is
unverified. To re-enable after a fallback: a fallback boot is stock and adds no grid icon (the icon is new boot
code, so it is behind the sticky note like everything else). The way back is the **recovery fallback** in the Home
icon tap hook (not boot code): while the bad note `/mnt/data/m1pod-bad` exists, a tap on the Tidal icon (id 1)
opens the M1 Pod menu (the normal instance, with Back) instead of Tidal; Settings > **Start in: M1 Pod** clears
the note and sets the start file, and the next boot arms the guard again (the icon returns). Without the note,
or with the kill switch on, Tidal is stock; if the menu cannot open, the tap falls through to stock. From a
shell, deleting `/mnt/data/m1pod-bad` and writing `1` to `/mnt/data/m1pod-start` does the same; or reflash. Device test procedure: boot, wait 10 s past Home, power-cycle a few times (with the log: every
start `armed` / `boot ok`, never `marker found`); power off within 5 s of Home once (the log says
`marker found; falling back to Shanling`, the device boots to the stock Home); then Songs/Albums/Back,
Now Playing, Cover Flow, Shuffle, lock/unlock, idle timeout, USB mode in and out (you land on the
menu), Settings > Shanling Home and back by the icon, Start in toggles and reboot, and the kill switch.

## 10. Safety rules for the payload

- A boot-time crash is dangerous (the watchdog reboots in a loop, recovery combo unverified): the only
  start-up code is the guarded `home_page_init` hook; every other path is user-initiated.
- Three hooks only (sections 2, 8, 9); the 59 row edits are call-site and immediate edits, not hooks.
- Every patched word, hook site, `$gp`, address and the input SHA are pinned; `pod.py` refuses to build
  on mismatch; every hook falls back to stock through its trampoline; every error path (non-entry
  icon, kill switch, `window_open` NULL because the asset could not load, null icon) calls stock.
- Kill switch `/mnt/mmc/m1pod-off` (`access()` first) disables the entry, the guard and the row fit.
- On this AWTK `visible=false` does not stop hit testing (`widget_find_target_default` `0x6747d4` takes
  the first child with `flags & 9 == 9`: enable bit 0 and sensitive bit 3; `widget_set_visible` `0x66c394`
  only flips bit 2): hide = `visible=false` + `sensitive=false` (asset) or `widget_set_sensitive(w, 0)`
  (runtime); decorative overlays are insensitive. Normal windows are 450 px tall (fullscreen 480).
- No stock widget the app looks up by name is renamed or deleted.

## 11. Offline validation

- **Unicorn harness** (`test/pod/harness.py`): loads the real patched `demo` LOAD segments, mocks the
  stock functions and libc and executes the actual compiled payload. `test/patch.py` runs the modules:
  `menu` (entry, non-entry ids, kill switch, `window_open` failure, empty/null icons, row actions,
  hit tests on every menu row through the `list_view`/`scroll_view`), `coverflow` (open with a complete
  cache, the tap that opens the stock album page with its context, Back, side taps, drag/flick/wrap/abort, close, first-run build, worker
  lock order and markers, no space, refused thread, empty library, broken asset, flat fallback,
  re-query, the depth frame compared byte for byte with the host renderer, hit tests with demo's own
  `widget_find_target`, the caption layout), `assets` (dark/light contrast of the page assets, the
  wallpaper, the icon set and battery art), `artists` (an artist's tap and the All albums card open albuminfo_page with class `0xff01`), `rows` (pins,
  then the real stock row constructors run with their widget calls mocked, and the installed layouter),
  `albuminfo` (the header hook on the real stock header builder: stock first, the restyled geometry,
  texts and styles, the year line cases, the kill switch and every mismatch or failed create leaving stock,
  the Shuffle sequence, hit tests on the buttons with demo's `widget_find_target`, the page theme, the
  cover size word, Cover Flow's first album and last-album memory), `shuffle`, `home` (every
  boot branch, the call set, the launcher, window-stack cases). Each prints its count and time.
- `test/coverflow.py` builds `patch/coverflow.c` for the host (`-DCF_HOST`) and checks geometry,
  compositing, brightness ladder, reflection, cache key and the texture sampler; `test/demo_diff.py`
  checks the built `demo` differs from stock only in `.pdr`, `PH[10]`, the three hooks, the 59 rows.json
  words, the four cover-size words and appended bytes; `test/awtk_fill.py` runs demo's own AWTK fill
  and image code (translucency, rounded fill, scale_auto nearest neighbour).
- `fwtool verify` / `diff` on every package; a clean rebuild is byte-identical.

## 12. How this maps to q2-pod

| q2-pod | here |
|---|---|
| `tools/build.py` `append_payload`, `HOOKS`, `patch_word`, `fileoff`, prologue checks | `tools/pod.py` |
| `tools/peq.py` `compile_common` (GOT stubs, FLAGS, trampoline) | `tools/pod.py` `gen_asm` / `compile_payload` |
| `patch/link.ld`, `patch/offsets.inc` | `patch/link.ld`, `patch/offsets.inc`, `tools/pod_pages.py` |
| `patch/navigation.c` | `patch/m1pod.c`, `shuffle.c`, `artists.c` |
| `patch/coverflow.c` (wheel-driven) | `patch/coverflow.c` (renderer and cache design, touch-driven, this model's queries) |
| `patch/ipod.json`, `compact_row_layout` | `patch/rows.json`, `patch/rows.c` |
| `test/coverflow.py`, `test/patch.py` | `test/coverflow.py`, `test/patch.py` + `test/pod/` |

q2-pod hooks dozens of sites for a full scroll-wheel reskin; M1 Pod hooks one user-initiated site, one
guarded start-up site and the album page's header builder (reached only while that page builds), and adds pages.
