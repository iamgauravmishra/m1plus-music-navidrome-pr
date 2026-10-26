# Architecture: pipeline, payload, hooks, guard

How the release is built and what its code does. The looks (assets) are in `docs/ui.md`,
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
| 4 | `pod.py` | compile the payload, append it to `demo`, install four hooks, apply the library-row edits, write the four `ui/m1pod_*.bin` |
| 5 | `mod_theme`, `mod_lists`, `mod_nowplaying`, `mod_boot`, `mod_ipodrows`, `mod_pulldown`, `mod_lockscreen`, `mod_wallpaper`, `mod_icons`, `mod_strings`, `mod_polish` | the asset looks, in this order (`docs/ui.md`); `mod_strings` adds our translation keys to the 16 string tables (section 8b) |
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

Source map: `patch/m1pod.c` (hook, pages, rows, the Settings switches), `patch/menu.c` (the customisable menu and the Main Menu page), `patch/covercache.c` (+ `.h`: the cover cache, tile reduction and album helpers
Cover Flow and Albums share), `patch/coverflow.c`, `patch/albums.c`, `patch/artists.c`,
`patch/shuffle.c`, `patch/albuminfo.c` (the album view's hook), `patch/nowplaying.c` (Now Playing's hook), `patch/rows.c` + `patch/rows.json`, `patch/home.c` + `home.h`, `patch/i18n.h` (`TR()`), `patch/offsets.inc`
(every stock offset with its evidence), `patch/link.ld`; `tools/pod.py` (build and pins),
`tools/pod_pages.py` (pages and rows, one source of truth), `tools/pod_ui.py` (page assets), `tools/pod_i18n.py` (our texts in 13 languages), `tools/awtk_strings.py` (string table reader/writer), `tools/mod_strings.py`.
Tests: `test/patch.py WORKDIR` runs `test/pod/<module>.py` (menu, coverflow, albums, assets, artists, rows,
albuminfo, nowplaying, shuffle, home, i18n) on `test/pod/harness.py`; `test/coverflow.py` (host build of the renderer and the pixel helpers),
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
The payload keeps no `.bss`: writable state (400 bytes) is a zero-filled `PROGBITS` `.scratch`
section, so `memsz == filesz` holds; `pod.py` rejects a non-empty `.bss`/`.sbss` and checks `.scratch`
is inside the payload and shipped zeroed. Everything larger (Cover Flow's frame and textures, job
array, album copy, album header cover) is heap, allocated when the page opens and freed on close.
Current payload: 47,832 bytes. Compiled non-PIC (`clang --target=mipsel-linux-gnu -march=mips32r2
-mabi=32 -mfp64 -mno-abicalls -fno-pic -G0 -Oz`, `-Wall -Wextra -Werror`), linked by `patch/link.ld`
at `0xb00000` with `--gc-sections`, sources in this order: `m1pod.c covercache.c coverflow.c albums.c
artists.c shuffle.c albuminfo.c nowplaying.c rows.c home.c`.

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

### The four hooks

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

4. **`playing_page_init`** `0x53d1e4` (Now Playing's init; patch/nowplaying.c, section 8a). Pinned prologue
   `(0x3c1c004c, 0x279c6cec, 0x0399e021)`, `$gp` checked, overwritten with `j m1pod_playing_init; nop`; resume `0x53d1f0`. Its only
   caller is the navigator's page-init dispatcher (`0x4d1b3c`, behind the cut `tools/reach.py` uses), so it runs only when
   the page is built. The hook runs the stock function to completion and returns its result, then (if it returned `RET_OK`
   for a non-null window and the kill switch is absent) starts the page timer; any failure leaves the stock page.

`pod.py` asserts the three prologue words and the resulting `$gp` of each hook before writing, checks
that no row edit touches a hook site, and pins the input `demo` by SHA-256 (the `.pdr`-zeroed stock binary).
Nothing else is hooked: no prologue is rewritten for the library rows (they are call-site edits,
section 6), and nothing runs in `platform_init` or the main loop. The only code at paint is the Now Playing
cover widget's own `EVT_AFTER_PAINT` (section 8a), registered by hook 4 on that page's widget.

### What the entry does (`patch/m1pod.c`)

`m1pod_home_click(icon, e)`: read the icon's name (`icon + 0x10`, stock stores the Home id as a
decimal string), `atoi` it; if it is not the entry id (`POD_ENTRY_ID` = 99, the icon patch/home.c adds; Tidal, id 1, is stock), or the kill-switch
file exists, or the page fails to open, tail into `stock_home_click_trampoline` (unchanged stock
behaviour). Otherwise `window_open` the entry page, bind `btn_return` -> `navigator_back`,
`btn_backtoplayer` -> `on_backtoplayer_onclick` and each `pod_rowN` to its action, return 0.

Pages are defined once in `tools/pod_pages.py` (`PAGES`: menu, Cover Flow, Artists, Shuffle, Settings, Extras, Albums, Main Menu) and
consumed by `pod_ui.py` (assets) and `pod.py` (the C row/page tables in `stock.h`), so a row's widget,
label and handler cannot drift apart. Row actions: `ACT_HOME` (open a stock Home destination through
the dispatcher with a fake numeric-named icon), `ACT_PAGE`, `ACT_PLAYER` (stock
`on_backtoplayer_onclick`), `ACT_COVER`, `ACT_SHUFFLE`, `ACT_ARTISTS`, `ACT_ALBUMS`, `ACT_GRID`, `ACT_STARTUP`, `ACT_LANDSCAPE` (switch rows, below), `ACT_SORT` (a value row, below). The
menu items (`ITEMS`, the item id = the row index, default order) are Now Playing, Cover Flow, Albums (-> our page, grid or list mode, section 5a), Artists (-> our list), Songs, Playlists, Shuffle (-> Shuffle page),
Genres, Folders; then Extras (-> Extras page: a row per item, then the Home ids 10, 13, 12, 11, 8, 9, 2, 1, 15 through the dispatcher) and Settings (-> Settings page: Main Menu, Cover Flow (-> `m1pod_cfset`), the Start in M1 Pod
switch, Playback and System Settings through the stock dispatcher with ids 16 and 17, Shanling Home). Page layout: `docs/ui.md`. To add a
page: add a `Page` and a row to `pod_pages.py`, rebuild (assets and tables regenerate), add a test
module under `test/pod/`.

### Why the entry is an added icon

The entry is an icon of its own, id 99 ("M1 Pod"), which `patch/home.c` adds to the stock grid (section 9);
Tidal opens Tidal. The icon has no stock
id, so it cannot be hidden in Home customisation (the grid rebuild drops it; `hm_fg` puts it back), and the
dispatcher's bounds check (`sltiu 0x12`, `0x533ba8`) sends an id outside 0..17 to its default (nothing), so
a tap that reaches stock with the kill switch on is harmless. The HiFi store (id 0) was never usable: demo
only puts it on Home when the `language` global is 0 (Simplified Chinese), and patching that check needs
branch patches on the boot path (`reset_homemenu_index`, `load_home_menu`).

## 3. Known addresses (stock V2.1 `demo`)

Payload `PT_LOAD` `0xb00000`; `$gp = 0xa03ed0`; hooks `0x533b80` (Home icon dispatcher, registered
through `widget_on`, GOT slot `0x9fe700`), `0x534cd4` (`home_page_init`) and `0x526264`
(`albuminfo_listitem0_layout`) and `0x53d1e4` (`playing_page_init`). `.pdr` is zeroed in `demo`
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
`get_screensaver_image` `0x4d7524` (`screensaver_default`, the default wallpaper). Pinned for the Albums grid (section 5a):
`widget_to_local` `0x669b88` (walks the parent chain subtracting each `x`, `y`; the payload runs stock's own), `widget_prepare_text_style`
`0x66a214`, `canvas_draw_text_in_rect` `0x6496a0`, `canvas_measure_text` `0x644544` (returns a float in `$f0`),
`tk_utf8_to_utf16_ex` `0x70eb24` (`wchar_t` is 32 bit), `button_create` `0x622adc`.

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

- **Covers.** One cover per album on a shelf (committed album, offset, wrap; an artist's shelf has ends) drawn by the payload's
  depth renderer: the centre cover faces you at `ART_SIZE` 168 px, the neighbours turn 60 degrees
  inward, step back and dim (`CF_BRIGHT1` 192, `CF_BRIGHT2` 128 of 256, gone three out), each with a
  26 px reflection. Geometry (`offsets.inc`): frame 320x276, `CF_TOP` 31, `CF_EYE` 312, `CF_X1` 110,
  `CF_XS` 48, `CF_Z1` 96, `CF_ZS` 22, `DRAG_PX` 108. Change them together and re-run
  `test/coverflow.py`.
- **Renderer.** After Rockbox PictureFlow via q2-pod; all integer (16.16 turns, 1/16 px geometry, 1/256
  px row spans). One `bitmap_create_ex(320, 276, ..., RGBA8888)` frame plus 9 textures of 168^2 and one
  placeholder: about 1.48 MB of heap while open. If an allocation fails the page falls back to flat
  covers: a stock `slide_menu` whose `image` children (one per album) show the cached JPEGs, `ART_NEAR`
  3 either side. The frame is drawn from the touch layer's `EVT_AFTER_PAINT` (`0x120`, dispatched by
  `widget_paint` `0x66de3c`), an instance event registered with `widget_on`; an unchanged position
  reuses the frame. About 3.47 M payload instructions per frame under Unicorn.
- **Shelf position.** Depth mode owns it (`cfpos`: committed album, offset) and has no stock
  widget per album: the stock `slide_menu` lays out every child on each `xoffset` or `value` change
  (`slide_menu_set_prop` `0x613c94` -> `widget_layout_children` `0x656d1c`, which hides all children
  and places the near ones, `0x613090`; `slide_menu_set_value` `0x6139fc`), O(albums) per drag step
  and snap tick with up to 4000 empty children. The flat fallback keeps that `slide_menu` and drives it
  through its public properties (`value`, `xoffset`, `h`; no field offset pinned). Both read through
  one set of accessors (`value()`, `offset()`, `stride()`, `count()`, `set_offset()`, `set_value()`):
  `p = value - offset / stride`, the stock commit's `value - round(xoffset / item width)` with the item
  width the widget height (`0x612360`), so depth mode keeps the stock units (`CF_VIEW_H` per cover).
  Wrapping, an artist's ends (`bound()`), the captions and the last-album memory follow `set_value`.
- **Textures.** Paint never touches a file: it renders from resident textures (`fx_ring`),
  the placeholder standing in for a cover not decoded yet. A one-shot page timer (`on_load`, `LOAD_MS`
  1, removed at destroy) decodes one wanted cover per callback on the UI thread (`cc_decode`:
  `widget_load_image` is not known to be thread-safe, so the preparation worker never calls it),
  nearest first: the centre, the ring alternately ahead of and behind the travel, then the next cover
  ahead; a slot is reused from the cover farthest from the centre that is not wanted, so the one just
  left behind survives a reversal (9 slots for 8 wanted). An artist's shelf wants nothing past its
  ends. The first frame's covers are decoded when the shelf is built. Each decode still blocks the
  UI thread for its length; not measured on the device: measure before considering a decoding worker
  (that needs a reviewed thread-safe decoder publishing finished buffers).
- **Touch.** A transparent full-size touch layer (a `view` inside `view_covers`, over the flat
  fallback's `slide_menu`) takes `EVT_POINTER_DOWN/MOVE/UP` (`0xff/0x101/0x103`) and abort `0x107`,
  grabs the pointer (`widget_grab`/`ungrab`) and drives the shelf (`set_offset`, `set_value`). MOVE
  and UP share one tracker (`track()`): the greatest excursion from the
  down point in either axis, a horizontal drag that starts at `DRAG_START` 5 px along the carousel and no
  more across (its travel counted from that threshold, so neither a jump nor a lost sparse event), the
  shelf under the finger, and a ring of samples. A release is a tap only if no drag started, no
  animation was interrupted and the excursion, release included, stayed within `TAP_SLOP` 12 px; a tap
  is hit-tested by x: the centre cover (`|x - 160| < 84`) opens the album, a side cover comes to the
  centre. Anything else settles from where the shelf is: a drag coasts by the fling (the velocity from
  the oldest sample of the last `FLING_WINDOW` 80 ms to the release, coasting `FLING_MS` 120, at most 3
  albums; a finger that rested has none), a mostly vertical gesture moves nothing. A press during the
  snap stops the shelf where it is (its release eases to the nearest cover, or a drag carries on from
  there). The snap eases by elapsed time (`time_now_ms`): `1 - (1 - p)^3` over `SNAP_BASE_MS` 120 +
  `SNAP_ALBUM_MS` 60 per album of travel (180 ms for one album, at most 360), stepped by a 16 ms one-shot
  page timer, exactly on the target when the time is up, so late callbacks do not stretch it; a refused
  timer commits at once, so no nonzero offset is ever left without its timer. Then the commit
  (offset 0, `set_value`). The thresholds and times are trials, to tune on the device. The flat
  fallback's `slide_menu` itself is insensitive. Back leaves the page.
- **Repaint.** AWTK paints only dirty rectangles: `canvas_begin_frame` `0x6447b4` clips the canvas to the LCD's dirty
  rect (`canvas_set_clip_rect`), and `widget_invalidate` `0x668d9c` (no rect: the widget's own 0, 0, w, h; skipped while
  the widget's dirty flag, `0x24` bit 9, is set) hands it up through `widget_invalidate_default` `0x674920` to the window,
  translated by each parent's x, y and not clipped by them. The stock `slide_menu` marks only its own rectangle when
  `xoffset` changes (`slide_menu_set_prop` `0x613c94`: store, `widget_layout_children`, `widget_invalidate`) or `value`
  does (`slide_menu_set_value` `0x61399c`, tail call `0x613a1c`). So every offset change and album change calls
  `widget_invalidate_force` on the touch layer, which is always the frame's rectangle (`redraw()`). Tests model this (`dirty_rects` / `abs_rect` in `test/pod/harness.py`).
- **Landscape.** The page, main or per artist, opens in a landscape presentation in
  the 320 x 400 body under the navbar when **Settings > Cover Flow > Landscape** is on (the switch row of `m1pod_cfset`; nothing changes the presentation while the page is open); no global
  LCD orientation changes. The navbar is untouched in both (Back, the title, Now Playing). The content is turned 90 degrees **clockwise** on the screen (its top edge at the screen's right: the
  player is held turned counter-clockwise, the status bar and navbar then a strip on the left; the direction is the
  map in `turned()` / `where()` / `coverflow_render`), the carousel runs along the 400 px side. `cfg_t` (`cf_portrait`,
  `cf_land`) is the shelf's geometry; `coverflow_render(g, d, pitch, ...)` writes the logical frame through a column
  stride of `pitch` and a row stride of -1, so the turn costs no copy and no second bitmap: logical (x, y) is physical
  (319 - y, x), `CFL_Y` 50 px down the window. Landscape numbers (`CFL_*` in `offsets.inc`): logical 400 x 320, the
  centre cover the 168 px texture 1:1 as in portrait (no zoom) at top 28, portrait's eye, depth and reflection, `x1`
  160, `xs` 84, `CFL_DRAG_PX` 132: two covers either side, the outer ones cut by the edge (portrait: one and a half). A
  tap beyond the first side cover's drawn outer edge (projected) brings the second one in. The frame bitmap is the
  body, 320 x 400 x 4 = 500 KB (portrait 345 KB; one exists at a time, the new one is made before the old goes, so a
  refusal leaves the page as it was); textures are shared. Frame cost under Unicorn about 4.03 M payload instructions
  against 3.48 M (1.16x). In landscape `view_covers` and the touch layer are moved and resized to the body (0, 50,
  320 x 400; the drag stride stays `CF_VIEW_H`), the caption labels are hidden
  (visibility only: they stay insensitive), and the frame carries the captions, drawn after the covers: the page's font comes from the
  canvas (`widget_prepare_text_style(label)` fills `canvas+0x34` font, `canvas+0xc` size, as `canvas_draw_text`
  `0x645348` reads them), `font_get_glyph` `0x6508b0` gives each glyph's 8-bit alpha (`glyph_t`: x, y, w, h, advance,
  format 0 = alpha, data at 0xc) which is blended in turned at `x + g.x, y + g.y + ascent` (`font_get_vmetrics`
  `0x650918`, a hidden-pointer struct return, ascent first), advance + 1 px per glyph (4 for a missing glyph), centred
  in 368 px and cut with an ellipsis. Touch: `where()` turns the
  pointer back (`widget_to_local` on the touch layer, x = y_local, y = 319 - x_local), so drags and flings along the long
  side move the shelf as in portrait, a tap on the centre cover (`|x - 200| < 84`) opens the album by
  `open_album` (stock sequence, cover thread released), a side tap brings that cover in. Persistence:
  `/mnt/data/m1pod-landscape` (`1` landscape, anything else or missing portrait; written atomically by the switch
  (`coverflow_landscape_toggle`), read when the covers screen is first built (`use_land`); shared by the main and artist pages). Without a depth frame (flat fallback) there is
  no landscape, whatever the setting says. A commit redraws the frame (the captions are in it).
- **Captions.** `label_album` / `label_artist` are `hscroll_label`s configured as Now Playing's info
  lines (`loop`, `yoyo`, `lull` 3000 ms, centred, `ellipses`, 22 px white / 18 px `#AAAAAA`, in 16 px
  margins): a long title scrolls back and forth with a pause at each end, a short one is centred
  (`hscroll_label` paint `0x609cbc` -> `hscroll_label_start`; setting text resets the scroll `0x60a49c`).
  They are insensitive and never hidden: they lie over the frame's black rows, so a tap on the album
  name reaches the touch layer and opens the album. There is no hint line.
- **Start index.** The stock `slide_menu` starts on item 1, not 0; the page always sets the start
  album (`cfpos.value`, or `slide_menu_set_value` in the flat fallback), so an artist's page opens on its first album, a
  one-album shelf has its captions on open, and the main page keeps its last-album memory
  (`/mnt/mmc/.coverflow/album`, including album 0).
- **The album.** Tapping the centre cover opens the stock `albuminfo_page` (section 8), as a stock
  Albums row does (`cc_open_album`, `patch/covercache.c`, the same call the Albums grid makes): `loadAlbumList(0xf003, 0)` puts the stock album list back into `*pdeq_showlist` (the
  page's own copy was made from the same query, so the row is the same), `albumcoverinfo_init` rebuilds
  the cover-task list from it, `batchadd_albumcover_task(0, 0)` releases the cover thread (see section 8, The cover), and `navigator_to_with_context("albuminfo_page", 0xf003 | row << 16)`
  opens the page. The queries repeat on every tap (the page may have been left through Now Playing, and
  anything may have reused the list or the browsing record). Back from the album page returns to the
  covers; the page keeps no track list, header or play code of its own.
- **Cache.** The page keeps its own `/mnt/mmc/.coverflow/<key>-168.jpg` thumbnails (the size is in the
  name; key = FNV-1a of artist then album, never 0; the key, path, decode and reduce helpers are in
  `patch/covercache.c`, which the Albums grid reads the same files through). The stock cache `/mnt/mmc/.downpic` is keyed by an
  MD5 the payload cannot reproduce and holds 90 px images, so Cover Flow only reads through the stock
  extractors. First open builds the thumbnails on a "Preparing covers... n/m" screen with Cancel (a
  cancelled build resumes); one pthread runs `build_art` over jobs built on the UI thread, touching
  only its jobs, three `volatile` counters, files under `.coverflow` and the two stock art calls under
  `parse_cover_mutex` (`0xa04588`, the lock every stock caller holds; `parseplaycover_thd` takes the
  same one). Each file is written to `.tmp` and renamed; both extractors failing leaves an empty
  marker (not retried); a vanished track leaves none, and neither does a thumbnail that was extracted but could
  not be published (a failed rename: the next open retries). If the progress timer cannot be created (at the start or
  when re-armed) the worker is cancelled and joined and the cached covers show. No build below 16 MB free (`statfs`), without a
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
(a navbar button in the toggle slot (`btn_artisttype`; the title reads "Artists" / "Album Artists", the glyph is the other mode's: `pod_nav_artist` / `pod_nav_albumartist`), does what the stock switch handler `0x535770` does: `artist_type` (`0xa05a14`) set, `write_int_config(v, "PLAYSET", "ARTISTTYPE")` (`0x4d6a2c`) and the byte `0xa06d20` (the stock Artists page's reload flag, read at `0x535fe8`) set to 1; then the list is queried again, rows rebuilt and scrolled to the top; the stock toast and style swap belong to the stock page and are skipped; Cover Flow and the album page read `artist_type` themselves). "Update Local Music first" for an empty library.
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

## 5a. Albums (`patch/albums.c`, `patch/covercache.c`, test `test/pod/albums.py`, host test `test/coverflow.py`)

The menu's Albums row (`ACT_ALBUMS`) opens our one Albums page in the mode used last: a **grid** of covers or a **list**
(the stock Albums list is not used from here); one navbar button switches the mode in place, the choice is persisted.
`ALBUMS_DEFAULT_GRID` (`offsets.inc`, 1 = grid) is the mode of a first use. No hook; everything runs from the page's widgets and timers.

- **Page** `ui/m1pod_albums.bin` (`kind='grid'`, `tools/pod_ui.py`): the stock navbar (Back, "Albums", Now Playing)
  plus `btn_albumview` (x 214, 46x50, flush left of Now Playing, `img_btn_style`, the `pod_nav_list` glyph: the view a tap switches to), **one**
  `view_grid` (320x400 at y 50, black; its style carries the grid's title text: 16 px white, left, middle), a hidden
  `label_status` and two hidden, insensitive style labels, `label_row_title` (21 px `#FFFFFF`) and `label_row_sub` (18 px `#AAAAAA`), that
  only carry the list mode's text styles. There is no widget per album, no `list_view`, no `scroll_view`.
- **Geometry** (`offsets.inc`): `GRID_COLS` 3 columns of `GRID_COVER` 92 px covers, `GRID_GAP` 12 px apart, centred
  (`GRID_MARGIN` 10 each side: 3 x 92 + 2 x 12 + 2 x 10 = 320); under each cover a one-line title `GRID_TITLE_H` 22 px
  high, `GRID_TITLE_GAP` 4 px below it; cell 118 px, row pitch 130 px; the first row starts 12 px down the content
  and the last ends 12 px above its bottom (`content = 12 + rows x 130`); the content scrolls in the 400 px view,
  clamped to `[0, content - 400]` (two rows or fewer need no scrolling).
- **Painting.** The view's own `EVT_AFTER_PAINT` (as Cover Flow's frame): `widget_prepare_text_style(view, canvas)` once,
  then only the cells that touch the view: the cover (a tile bitmap, `canvas_draw_image` 1:1, cut to the view by
  hand) and the title (`canvas_draw_text_in_rect`, drawn only when it lies wholly in the view). At most 4 rows x 3 =
  12 cells per frame; a steady frame is about 2,500 payload instructions plus the stock blits and text runs
  (Unicorn, 9 cells). The text style is the widget's; the canvas does not clip to the view (the stock paint only
  translates), hence the manual cuts.
- **Tiles and memory.** `GRID_TILES` 24 entries, replaced least recently drawn first (a frame touches at most 15, the
  build checks it). A tile is a 92x92 RGBA8888 `bitmap_create_ex` (34 KB, flagged opaque) holding the album's cover:
  the Cover Flow cache file (`<key>-168.jpg`, key of the album record, so the same files) decoded by the stock
  loader and reduced with an **area average** (`cc_box`: each output pixel is the mean of the source pixels its box
  covers, the centred square, alpha over black; nearest sampling shimmers at 168 -> 92). The title is converted to
  wide chars (`tk_utf8_to_utf16_ex`, at most 47) and, when `canvas_measure_text` says it is wider than the cell, cut
  by a binary search to the longest prefix that fits with an ellipsis (U+2026), the first time it is drawn, never per
  frame. Memory while open: 24 x 34 KB + the placeholder 34 KB + 10 KB of tile records (a title and an artist of 48 wide chars each) = 0.9 MB, **whatever the
  library**, plus the copy of the stock album list (what Cover Flow keeps too, about 0.3 KB per album); closing frees
  all of it (`EVT_DESTROY`). Decoding is paced: at most two covers per frame (`AL_LOADS`; 0.75 to 1.9 M payload
  instructions each under Unicorn, a few ms on the device); the other visible cells show the placeholder and a 16 ms
  timer repaints until the view is complete (a fling past 24 covers keeps up as the cache allows).
- **No cache, no art.** The grid builds nothing: an album with no cache file, or the empty "no art" marker, shows the
  stock placeholder disc (`p_default`, reduced like a cover, flat grey if it will not decode) with its title. Open Cover
  Flow once to build the cache; the covers show the next time the page opens.
- **Touch.** `EVT_POINTER_DOWN/MOVE/UP/ABORT` on `view_grid`, grabbed by the window while a finger is down (as Cover
  Flow's layer). Pointer events carry screen coordinates (`widget_on_pointer_down_children` passes the same event down the
  tree, `0x6714ac`), so every position goes through `widget_to_local(view)`, the same call `widget_find_target` makes. A drag
  scrolls with the finger after 12 px of travel on either axis (the release counts as a position too, so sparse events
  still scroll to where the finger ended); a release under 200 ms coasts (the velocity of the last two samples, at most 48 px per
  16 ms tick, decaying by 1/16 a tick, stopping at an end); a touch stops it, and the release of that touch is never a
  tap. A release within the slop is a tap: the cell under it (cover or title, not the gaps, margins or the empty tail of
  the last row; none outside the view), the same one as under the press, opens its album.
- **Album.** `cc_open_album(0, row)` (`patch/covercache.c`): the stock sequence Cover Flow uses (`loadAlbumList(0xf003, 0)`,
  `albumcoverinfo_init`, `batchadd_albumcover_task(0, 0)` so the cover thread runs, `navigator_to_with_context("albuminfo_page",
  0xf003 | row << 16)`; section 4 and 8). Back returns to the grid where it was.
- **List mode** (the same page and view). Rows of `LIST_ROW_H` 64 px (the library rows'
  pitch, `rows.json`), content `count x 64`, scroll clamped to `[0, content - 400]`. Per row, in view coordinates: the pressed fill
  `LIST_PRESS` `#333333` over lines 0..62 (only the row under a finger), the cover `LIST_ART` 52 px at (4, 4) (the tile bitmap, the Cover Flow cache
  box-reduced to 52, cut to the view by hand), the hairline `LIST_HAIR` `#222222` on line 63 (`canvas_set_fill_color` + `canvas_fill_rect`, both new
  pins: `0x644220` and `0x644e4c`; `color_t` is one word, `lcd_set_fill_color` stores `$a1` at `lcd+0xbc`; the rect is cut to the view by hand), then
  two text passes: all titles with the style of the hidden label `label_row_title` (21 px `#FFFFFF`, left, middle) in a `LIST_TEXT_W` 248 x
  `LIST_TITLE_H` 24 rect at (60, row + 7), then all artists with `label_row_sub` (18 px `#AAAAAA`) in 248 x 20 at (60, row + 33): one
  `widget_prepare_text_style(label, canvas)` per pass (two a frame, none new in the stock code), each text drawn only when wholly inside the view. Each text is
  converted to wide chars when the tile is made and cut with an ellipsis (`al_fit`, the grid's binary search with the canvas' own
  `canvas_measure_text`, in the text's own style) the first time it is drawn; never measured again. Tiles are the grid's ring (24, replaced
  least recently drawn first; at most 8 rows are in view), 52 px bitmaps (11 KB) in this mode, the same placeholder disc at 52 px.
  A tap on a row (any x, lines 0..63) opens its album as a grid tile does (`cc_open_album`). A finger down on a row sets `press`, a move
  past the 12 px slop, the release and an abort clear it; the view is invalidated on each change, nothing else repaints.
- **The toggle.** The navbar button (`btn_albumview`, x 214, shared with the other Pod pages) switches the mode **in place**: no window opens or
  closes. `al_set_mode`: stop a fling and a pending reload timer, drop every tile and the placeholder (their size is the old mode's) and make
  the placeholder at the new size, keep the first album in view (grid -> list: the first row with a visible cell, `row x 3` x 64; list -> grid:
  `(album / 3)` rows down), set the three icon properties of the button to the glyph of the *other* mode
  (`pod_nav_grid` in list mode, `pod_nav_list` in grid mode; the same `widget_set_prop_str` pattern as the Artists toggle), invalidate the view, and
  save the mode (`home_write_atomic`). Nothing is opened, so nothing can be left behind. If the page's asset lacks the two style labels the
  page leaves again (`navigator_back`) as it does without `view_grid`.
- **Persistence.** `/mnt/data/m1pod-albums`: `1` the grid, `0` the list, missing or anything else
  `ALBUMS_DEFAULT_GRID`; written as the Start-in setting is (`home_write_atomic`: temp file, `fsync`, `rename`, directory
  `fsync`) at every toggle. The menu's Albums row (`albums_open`) opens the page in that mode. If the window cannot open at all it opens the
  **stock Albums list** through the Home dispatcher (id 5, `pod_home_open`); the stock list stays reachable from Shanling Home, unmodified.
- **Shared helpers** (`patch/covercache.c`, used by `coverflow.c` and `albums.c`, the next page that shows covers, the landscape
  Cover Flow, can use them as they are): `cc_fnv`, `cc_album_key`, `cc_path`, `cc_file_size`, `cc_url` (the cache file's `file://` url
  if it holds a picture), `cc_decode(widget, url, unload, size, box, out)` (stock loader, centred square, nearest or box to `size`),
  `cc_sample` / `cc_box` (the pure pixel functions, also built for the host), `cc_copy_list`, `cc_albums` (the stock Albums list copied),
  `cc_open_album(artist_row, row)` (the stock open sequence, library or one artist's). Cover Flow keeps the cache *builder* (worker thread).
- **Risks.** `widget_prepare_text_style` on a hidden, insensitive label takes the font, size and colour from that label's style (assumed: it reads
  the style, not the visibility; if not, the list's texts would use the view's 16 px white); `canvas_fill_rect` is assumed to fill the colour
  `canvas_set_fill_color` was given (one word, r,g,b,a) and, like the other canvas calls, not to clip to the view (a clip would be harmless;
  the payload cuts by hand); the stock canvas fill colour is left as the list set it (the stock widgets set their own before each fill). None of
  this was checked on the device. Unicorn cannot judge the real frame time of 7 rows (about 6,000 payload instructions steady, plus 7 blits, 14 text
  runs, 14 fills), nor the stock text and fill calls.

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
| Albums | item 60, cover 60 at x 0, title 180 at y 10, chevron 296 | item 64, cover 52 drawn 1:1 at (4,4), title/artist 60..277 at y 7/33; 8 covers per batch |
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
stock Albums list, from the Albums grid (section 5a), from Cover Flow (main and per artist), from Artists through Cover Flow and from the
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
      |  120x120  |  1959 . 8 tracks         15 px #AAAAAA srlabel_meta15_style (new label)
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
buttons are 110x36.

**Styles** are the page theme's (`styles/albuminfo_page.bin`, both asset themes, `tools/mod_ipodrows.py`):
`btn_albumbtn_style` (`#1E1E1E` fill, `#3A3A3A` hairline border, 20 px white text, `#333333` pressed, no
icon) and `srlabel_meta15_style` (the stock grey line's alignment at 15 px `#AAAAAA`, the secondary grey). The 21 px title is the rows step's.

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

**The cover thread's state.** The thread
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

## 8a. Now Playing (`patch/nowplaying.c`, test `test/pod/nowplaying.py`; the look is `docs/ui.md` section 4)

The stock `playing_page` (`ui/playing_page.bin`, restyled by `tools/mod_nowplaying.py`) gets a cover-coloured window, the
cover's rounded corners and a remaining-time label from one hook and one page timer.

**The hook** (`m1pod_playing_init`, section 2): `playing_page_init` `0x53d1e4` (`a0` the window, `a1` the context
`{queue, index, class, mode}`; it registers the page's `EVT_*` handlers with `widget_on`, starts the queue with
`start_player` when the context's class is not `0xff`, runs `playing_choiceshowpage` and `player_timer_start`, returns 0, or `0x10` for a null window).
The hook calls it through `stock_playing_init_trampoline` and returns its result; with `RET_OK`, a window and no
`/mnt/mmc/m1pod-off`, `np_start` runs: it finds `np_remaining` and `label_playlen` (a missing one turns the time off, not the tint),
registers `EVT_DESTROY` on the window (`np_on_destroy`, context the window), adds a **repeating 500 ms timer** (`np_tick`, answering
`RET_REPEAT` 8 as the stock page timer `0x53cf48` does; a refused timer or `widget_on` leaves the page stock), registers
`np_on_art_paint` on `img_playcover` (`EVT_AFTER_PAINT`) and runs one tick at once. State is one 176-byte `.scratch` struct
(`np`): the window, the labels, the timer id, the cover key, the window colour, the seconds shown, which label is visible and the
12x12 corner table. A page built over a live one removes the old timer first; a destroy whose context is not the current window
(an earlier page's) does nothing; the current one removes the timer and zeroes the state, after which a stray tick returns `RET_OK`
(ends) without touching a widget.

**The tint** (`np_cover`): demo's cover thread `parseplaycover_thd` (`0x4ded84`) removes `/tmp/coverpic.jpg` and `/tmp/externpic.jpg`, sets the
source type word `0x97cad8` to 1 (`0x4df044..0x4df094`), writes the new file (extern and embedded covers under `parse_cover_mutex`) and then
sets the word to 2 (embedded art, `coverpic.jpg`), 3 (a folder image, `externpic.jpg`) or 5 (the `.downpic` cache copied to
`externpic.jpg`); the page's own loader (`0x53a5d8`) draws exactly these. `np_cover` does nothing while the word is 1, sets the neutral tone once for any other value, and
for 2, 3, 5 reads the file through stdio (`np_file_key`: FNV-1a of at most 512 KB and the length, never 0; no file or an empty one:
try again next tick, no colour change). A key different from the last decodes the picture with `cc_decode` (`patch/covercache.c`, the stock
loader, loaded and unloaded at once as the Cover Flow rows do, `box` mode reducing the centred square to one pixel = its average
colour), `np_tone` makes the tone and `np_set_color` stores it as the window's `bg_color` with `widget_set_style(win, "normal:bg_color",
&value_t)` (`0x66c448`, AWTK's `widget_set_style_color`: `widget_ensure_style_mutable` `0x666700`, then `style_set`; the `value_t` is
made by `value_set_uint32` `0x711858`, colour word `0xAABBGGRR`) and invalidates the window; a failing style call changes nothing,
not even the colour the corners use. A picture the loader refuses is not tried again until the file changes (the old colour
stays); the source word is read again before the decode, so a file demo started replacing is left alone. No lock on `parse_cover_mutex`
is taken (the UI thread never waits for an extraction): a file is read only while the word says 2, 3 or 5, which demo sets after
writing it; the few instructions between demo removing the old file and setting the word to 1 can only make `fopen` fail (no key, try again).
Tone: value `NP_V_MIN + v * (NP_V_MAX - NP_V_MIN) / 255` (32..192), every channel keeps `NP_SAT_NUM / NP_SAT_DEN` (4/5) of its
distance from the brightest `v`, black is `NP_NEUTRAL` (`#202020`, the asset's window colour); `tools/mod_nowplaying.py tone` is the model
(the test compares them on 369 colours). The window shows it under `np_tint.png` (alpha 38..235 down the 450 rows); with at most 192 the
white title and the `#AAAAAA` lines keep 4.5:1 (worst case checked at their rows in the test).

**The corners** (`np_on_art_paint`): `img_playcover` is a 264 px square image (the size demo writes, section 6 of `docs/ui.md`); AWTK has no
image clip, and one static mask would be the wrong colour on all but one window colour. The four 12x12 corner squares are
painted from the cover widget's `EVT_AFTER_PAINT` (canvas from the event, `EVENT_PAINT_CANVAS`; coordinates are the widget's, as in
section 5a): `np.corner` holds the coverage (0..255) of the area outside a quarter circle of radius 12 (`np_corner_init`, 8x8 samples
a pixel, computed once at the page's start; the Python model `corner_alpha` equals it), and every non-zero entry is one
`canvas_set_fill_color` (the window colour at that row under the gradient, `np_shade` of `np_alpha(y)`, with the coverage as alpha) and
`canvas_fill_rect(x, y, 1, 1)` that the stock canvas blends, so the corner is anti-aliased over the art. About 160 fills, and only
when the cover widget repaints (page open, track change; not for the slider, the times or a scrolling title). Without the hook the corners are square.

**The remaining time** (`np_time`): `get_playtimeandlength(&pos, &len)` (`0x4e015c`, the call the stock tick makes at `0x53a8fc`: seconds;
returns 1, or -1 for an index outside the queue). With 1 and `len > 0`, `np_format_remaining` writes `-mm:ss` (`-hh:mm:ss` from 3600 s;
zero padded like stock's `toolsTimeItoa`; a position past the length clamps to `-00:00`) into `np_remaining` only when the seconds
changed and shows it while hiding `label_playlen` (`widget_set_visible`; both labels are insensitive in the asset, so hide = invisible +
insensitive); otherwise `label_playlen` is shown again and `np_remaining` hidden. demo keeps rewriting `label_playlen` on its own tick, which is why
the swap is two labels and not one rewritten text (two timers 500 ms apart in phase would flash the total).

**Safety.** Runs only on a Now Playing build; the kill switch, a refused timer, a missing widget or a failing call each leave stock behaviour; the timer is gone with
the window; no stock memory is written (the style and the labels go through the stock setters); no lock, no thread, no heap. The only paint-time code is the one `EVT_AFTER_PAINT` on the cover widget. Newly pinned: `widget_set_style` `0x66c448`,
`value_set_uint32` `0x711858`, `get_playtimeandlength` `0x4e015c`, the data word `COVER_SRC` `0x97cad8`; `canvas_set_fill_color` / `canvas_fill_rect` (section 5a) are reused.
**A-B markers.** `getx_by_playtime` `0x53b824` returns `(pos - cue) * 0x128 / len + 0xc` and its caller `0x53b8f0`
(`img_repeata` / `img_repeatb`, called from the page timer `0x53cf48` through `show_player_face` and from `player_timer_start`) moves the markers to `y = 0x16c`
(three `addiu a2, zero, 0x16c`, one per branch); `mod_nowplaying.patch_markers` changes the 16-bit immediates at `0x53b8d4` (0x128 -> 264),
`0x53b8ec` (0xc -> 28) and `0x53b9c4`, `0x53ba48`, `0x53ba64` (0x16c -> 376, the new bar's centre 369 + 7), after checking those five words and the two functions'
prologues and call sites (nine more words). Neither function is reachable from `main` / `platform_init` (`tools/reach.py`).
Not verified on the device: the style call's repaint, the slider's `round_radius`, the corner fills over the real canvas, the look of the 4 px dots.

## 8b. Localisation (`patch/i18n.h`, `tools/pod_i18n.py`, `tools/awtk_strings.py`, `tools/mod_strings.py`, test `test/pod/i18n.py`)

**How the stock app translates.** AWTK's `tr_text`: a widget stores a key (`widget->tr_text`, offset `0x18`) and
`widget_set_tr_text` (`0x66f994`) sets the key and the text `locale_info_tr(widget_get_locale_info(w), key)` (`0x658db4`;
`widget_get_locale_info` `0x66b904`, the app's `locale_info` `0x6588b0`). `locale_info_tr` is `str_table_lookup` (`0x658cd8`),
a binary search by `strcmp`, and returns the **key itself** when the table or the entry is missing. A ui `.bin` property
`tr_text = key` does the same when the page is built (stock pages use it, e.g. `cdripper_page`; most stock pages set their
texts in code with `widget_set_tr_text`). A language change is `switch_language` (`0x4cca40`, the language menu) ->
`locale_info_change` (`0x6589e8`: the `<lang>_<COUNTRY>` file is re-referenced by `locale_info_reload` `0x6588e4`, then the
locale event `0x122`); the window manager's handler (registered by `locale_info_on` `0x658ba8` at `0x678304`, handler
`0x6772dc`) unloads fonts and images and runs `widget_re_translate_text` (`0x66f788`) on every open window and its
children, so **every window still on the stack, ours included, re-translates at once** (a widget set with `widget_set_text_utf8`
does not: it keeps its text until it is set again, so composed texts are rebuilt each time they are shown).

**Tables.** `strings/<lang>_<COUNTRY>.bin` (`tools/awtk_strings.py`): `u16 0, u16 count`, `count` pairs of `u32` offsets
(key, value, from the file start) sorted by key, eight zero bytes, then `key\0value\0` in order, UTF-8. 16 tables; the language menu
reaches 13: `zh_CN` (the default), `zh_HK`, `en_US`, `ja_JP`, `ko_KR`, `fr_FR`, `ge_DE` (German), `sp_ES` (Spanish), `it_IT`, `th_TH`,
`po_PL` (Polish), `ru_RU`, `uk_UK`. `de_DE`, `es_ES` and `pl_PL` are 11-entry CD ripper stubs nothing loads. The stock
translations are uneven (some untranslated, `msg_no` "Cancel" is "Nein" in German, `it_IT` lacks 2 keys), so a stock key is used only
where it is the same English text and reads well in every language (`tools/pod_i18n.py` `STOCK`: `cdrippersettings` Settings,
`hr`, `sset_updatemusic`, `cdripper`, `album`).

**Our texts.** Every other text M1 Pod adds is a key of our own whose **key is the English text** (`TEXT` in `tools/pod_i18n.py`,
translations for the 13 languages, brand names `M1 Pod` and `Tidal` left plain): a missing table or entry shows English.
`tools/mod_strings.py` (a build step) adds them to all 16 tables in sorted position (the three stubs get their twin's text),
refusing a table that has one already, a stock key that is gone, a text without ink in the shipped font. `tools/pod_ui.py` writes
`tr_text = key` for page titles, row labels and Cancel (`pod_i18n.text_prop`); the payload includes `patch/i18n.h`:
`TR(key)` = `locale_info_tr(locale_info(), key)` for composed texts and the message box, `widget_set_tr_text` for a label
(Artists / Album Artists title, the Update Local Music / Not enough memory / Library too large / No albums / Preparing covers
messages, the album page's Play all and Shuffle). Composed: the Cover Flow progress is `TR("Preparing covers...")` + `" done/total"`;
the album page's count is the key `%d track` or `%d tracks` (by `n == 1`) with the number put where the text has its `%d` (never a
printf format; Polish, Russian and Ukrainian, which have three plural forms, word both keys as a label: "Utwory: 12"); the All albums
caption (also painted into the landscape frame) is `TR("All albums")`. Adding a text: a `TEXT` entry with all 13 languages (the
test fails otherwise), its use in an asset or the payload, `test/pod/i18n.py` checks widths and glyphs. The pull-down, lock screen
and Now Playing add no text.

**Fonts.** One file, no fallback: `mod_font.py` keeps every stock code point, Inter replaces Latin / Greek / Cyrillic, Source Han Sans
SC the CJK, kana and Hangul stock code points, Thai stays stock. All 430 characters of our texts (including Traditional Chinese for
`zh_HK` and Thai) already have ink in the shipped font, so the subset needs no extension (zh_HK shows Source Han Sans **SC** forms,
as the stock zh_HK UI does).

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
      does not stop the guard: the Shanling start is armed too, because step 7 adds the grid icon;
   5. **write the marker**: temp file, `fsync`, `rename`, directory `fsync` (its open and its `fsync` must succeed: an unconfirmed
      marker is not armed on); any failure -> stop with no marker left (it is unlinked again);
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
risks: a power-off within 5 s counts as a failed start (the next start is stock; turn **Start in M1 Pod**
on again); a hang inside `fsync` on a broken flash filesystem would hang the UI thread before the
marker is durable; a later misbehaviour after the 5 s window is not caught.

### Files and the kill switch

| path | meaning |
|---|---|
| `/mnt/mmc/m1pod-off` | SD kill switch: the payload does nothing at boot (no icon), the icon does nothing if it is there, the row fit is off |
| `/mnt/data/m1pod-off` | the same in flash (cannot be created without a shell) |
| `/mnt/data/m1pod-run` | the crash marker: exists from "armed" until 5 s later |
| `/mnt/data/m1pod-bad` | the sticky note when a marker was found; removed by turning on **Start in M1 Pod** |
| `/mnt/data/m1pod-start` | the setting: `1`/missing = M1 Pod, `0` = Shanling (temp + `fsync` + `rename`) |
| `/mnt/data/m1pod-albums` | the Albums page's mode: `1`/missing = the grid (`ALBUMS_DEFAULT_GRID`), `0` = the list (same write; section 5a) |
| `/mnt/data/m1pod-landscape` | Cover Flow's presentation: `1` = landscape, `0`/missing = portrait (atomic write at each switch tap; section 4) |
| `/mnt/data/m1pod-menu` | the menu's shown items in order: one digit (the item id 0-8) each, then `\n`; `0123456\n` is the default (the file missing). Read with the limits below; written atomically at each change on Settings > Main Menu |
| `/mnt/mmc/m1pod-log` | opt-in: if this empty file exists, events are appended to `/mnt/mmc/m1pod.log` (armed, boot ok, marker found, kill switch) |

The menu list is **on the boot path** (the menu is the Home screen at start-up; its asset is arranged by `menu_arrange` while it opens), so
`patch/menu.c` reads `/mnt/data/m1pod-menu` with `open`/`read` of at most 16 bytes (`POD_MENU_FILE_MAX`) and accepts only: no
more than nine digits `0`-`8`, none twice, an optional single final newline, a file shorter than 16 bytes (an empty list, a lone
newline, is valid: every item hidden); a missing, empty, longer, corrupt, duplicated or unknown-id file is the default list. It
never writes while reading, a row or the list missing from the page leaves the asset untouched (every item shown, Extras and
Settings on the menu), and `Extras` / `Settings` are rows the arrangement never hides, so Settings stays reachable from any file.
The page arrangement costs a handful of widget calls (`widget_move`, `widget_set_visible`, `widget_set_sensitive`, one
`virtual_h` / `yoffset` pair); the menu also re-arranges on `EVT_WINDOW_TO_FOREGROUND` (it comes back in front after the Main Menu page).

The setting is an own file, not `config.ini [M1POD]`: `write_int_config` rewrites the shared config
the stock app parses at start-up, and a bad write there is a boot risk.

### The launcher

The menu's last row opens the **Settings** page (`m1pod_settings`, the Shuffle page's machinery), whose rows are
Main Menu, **Cover Flow** (a sub-page, below), the **Start in M1 Pod** switch, Playback and System Settings (stock pages through the dispatcher with ids 16 and 17) and **Shanling Home**.

**Settings > Cover Flow** (`m1pod_cfset`, `pod_pages.CFSET_PAGE`): **Landscape** (the switch, `/mnt/data/m1pod-landscape`, as before) and **Sort** (`ACT_SORT`: the row shows its value, `Artist` or `Album`, in a grey right-aligned `pod_value<row>` label set by `widget_set_tr_text` so it follows the language; one tap toggles it, saved first, a failed save changes nothing; no sub-choice page). The setting `/mnt/data/m1pod-cfsort` (`cc_sort_artist`, `cc_sort_toggle` in `patch/covercache.c`): only `0` or `0\n` is Album; a missing, empty or any other content is Artist (the default), and reading never writes.

**The album order** (`cc_album_order`). Album = the stock list as it is (`getAllAlbum`: by album title, ASCII case-insensitive). Artist = the row's artist (`songer`, the album's representative track: the album query does not fetch the album artist, so there is no album-artist fallback to apply), then album title, each ASCII case-folded with a leading `The ` dropped (`A `/`An ` are not), ties by the stock position; the Unknown Album row (id -1) is last. The stock deque is never reordered: the page holds `order[]` (stock row numbers, a heapsort, no libc callback; about 25 M instructions for 4000 albums on open) and every access goes through `cc_row`; whatever returns to stock (`cc_open_album`) gets the stock row, `order[i]`. Cover Flow sorts a library of at most `MAX_ALBUMS`; the Albums page (grid and list) uses the same call; the per-artist Cover Flow is not re-sorted (its stock order is album title, `group by album COLLATE NOCASE`, not chronological). Cache keys are unaffected (key = album's artist + title).

**Opening on the playing album** (`find_playing`, once, at open, no polling). `cc_playing()`: `mclGetPlayPos` `0x5d4290` (the position, -1 none) and the play queue, a `deque_t *` in the data word `PLAY_QUEUE` `0xa0394c`; the track is `deque_at(*PLAY_QUEUE, pos)` when `0 <= pos < deque_size` (the same test and accessors as `get_playtimeandlength` `0x4e015c`, the lock screen refresh `0x53f718` and the queue drawer). Its album (`REC_ALBUM`; empty = no match) is matched first by `cc_album_key` (FNV of artist then album), else by album title ignoring ASCII case (a compilation's tracks do not share the album row's artist). Found: that cover is centred (main page, or the artist page when the artist's list has the album); otherwise the saved `LAST_ALBUM`, else the first, as before.
Shanling Home shows the stock grid for the rest of the session (nothing re-opens the pod menu while it is on):
it sets `grid`, shows the grid, closes the menu under the Settings page by handle (`window_close(hs.entry)`: a
second `navigator_back` straight after the first would find the closing page) and then closes the Settings
page with `navigator_back`; with no known menu below it is one `navigator_back`. Tapping the **M1 Pod icon**
(id 99) on the grid, when the setting is M1 Pod and the payload is armed, clears the flag and opens the menu as
the Home instance; a failing open restores the previous state. With the switch off ("Shanling") the icon opens a normal
menu. **Start in M1 Pod** is a switch row: a tap runs `home_toggle`, which flips the persistent setting (`/mnt/data/m1pod-start`, the
same semantics and the same atomic write as before; it returns the new state or -1 for a failed write, which leaves the file and the switch
alone) and `patch/m1pod.c` sets the row's stock `sset_on` / `sset_off` image (`pod_switchN`, found by name; at open it shows `home_start()`).
The switch rows' click ctx is a small slot (action, image) in `.scratch` filled when the Settings page opens; `home_menu_opened` still
records the Settings window for Shanling Home. The boot guard is untouched. Toggling to M1 Pod takes effect at the next Home foreground event (a
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
every give-up (kill switch, no top window, Home never opened, `window_open` failure, a refused open timer) shows the grid
again, and Home coming to the foreground with no menu to follow (the kill switch appeared, or Start in was switched to
Shanling while the menu was Home) shows it too (`hm_fg`: never a blank Home), and the stock Home keeps all its widgets so every stock `widget_lookup` resolves. Hiding
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
opens the M1 Pod menu (the normal instance, with Back) instead of Tidal; Settings > **Start in M1 Pod** (switch on) clears
the note and sets the start file, and the next boot arms the guard again (the icon returns). Without the note,
or with the kill switch on, Tidal is stock; if the menu cannot open, the tap falls through to stock. From a
shell, deleting `/mnt/data/m1pod-bad` and writing `1` to `/mnt/data/m1pod-start` does the same; or reflash. Device test procedure: boot, wait 10 s past Home, power-cycle a few times (with the log: every
start `armed` / `boot ok`, never `marker found`); power off within 5 s of Home once (the log says
`marker found; falling back to Shanling`, the device boots to the stock Home); then Songs/Albums/Back,
Now Playing, Cover Flow, Shuffle, lock/unlock, idle timeout, USB mode in and out (you land on the
menu), Settings > Shanling Home and back by the icon, Start in toggles and reboot, Main Menu changes and reboot, and the kill switch.

## 10. Safety rules for the payload

- A boot-time crash is dangerous (the watchdog reboots in a loop, recovery combo unverified): the only
  start-up code is the guarded `home_page_init` hook; every other path is user-initiated.
- Four hooks only (sections 2, 8, 8a, 9); the 59 row edits and the five A-B marker immediates are call-site and immediate edits, not hooks.
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
  hit tests on every menu row through the `list_view`/`scroll_view`; the customisable menu: the default order, saved lists, every invalid or oversized list
  falling back to the defaults (also against the Python model `pod_pages.parse_menu`), the arranged rows hit-tested, Extras with the hidden items, Settings always shown,
  the Settings switches writing their files, the Main Menu page's switches, arrows, failed saves and persistence), `albums` (the grid: layout against the asset, the menu row and the persisted view, the first frame and paced decoding, tiles of the
  box-filtered cover, scroll clamping by drag and fling, taps on every cell kind and gap incl. the last partial row, title ellipsis, missing
  and empty cache files, 4,000 albums with the bitmaps bounded and recycled, destroy, the toggle both ways with its saved file and the decorated
  stock navbar, hit tests with demo's `widget_find_target`), `coverflow` (open with a complete
  cache, the tap that opens the stock album page with its context, Back, side taps, drag/flick/wrap/abort, close, first-run build, worker
  lock order and markers, no space, refused thread, empty library, broken asset, flat fallback,
  re-query, the depth frame compared byte for byte with the host renderer, hit tests with demo's own
  `widget_find_target`, the caption layout), `assets` (dark/light contrast of the page assets, the
  wallpaper, the icon set and battery art), `artists` (an artist's tap and the All albums card open albuminfo_page with class `0xff01`), `rows` (pins,
  then the real stock row constructors run with their widget calls mocked, and the installed layouter),
  `albuminfo` (the header hook on the real stock header builder: stock first, the restyled geometry,
  texts and styles, the year line cases, the kill switch and every mismatch or failed create leaving stock,
  the Shuffle sequence, hit tests on the buttons with demo's `widget_find_target`, the page theme, the
  cover size word, Cover Flow's first album and last-album memory), `nowplaying` (section 8a: the hook, the timer's life, the tint, the remaining time, the corners, the marker words, the built page), `shuffle`, `i18n` (section 8b: the tables, the keys, our texts in all 16 languages through a mocked `locale_info_tr`, widths and glyphs), `home` (every
  boot branch, the call set, the launcher, window-stack cases). Each prints its count and time.
- `test/coverflow.py` builds `patch/coverflow.c` and `patch/covercache.c` for the host (`-DCF_HOST`) and checks geometry,
  compositing, brightness ladder, reflection, cache key, the texture sampler and the grid's box filter (flat colour, chequer, 2:1 block means, stride, alpha); `test/demo_diff.py`
  checks the built `demo` differs from stock only in `.pdr`, `PH[10]`, the four hooks, the 59 rows.json
  words, the four cover-size words, the five A-B marker words and appended bytes; `test/awtk_fill.py` runs demo's own AWTK fill
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
guarded start-up site, the album page's header builder and Now Playing's init (reached only while those pages build), and adds pages.
