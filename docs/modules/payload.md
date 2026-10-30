# The code payload: segment, trampolines, hooks, the entry

M1+ Music adds pages through a MIPS payload in `/release/bin/demo`. The M1 Plus uses an
X2000, Linux 5.10, Buildroot glibc and AWTK; `demo` has a spare `PT_NULL` program header.
All stock addresses and patch words are specific to the pinned V2.1 binary.

## The segment

`demo` is `ET_EXEC`; its LOAD segments end at va `0xa10fc8` and `PH[10]` is an unused `PT_NULL`.
`pod.py append_payload` pads the file to 64 KiB, appends `patch.bin` and rewrites `PH[10]` into a
file-backed `PT_LOAD` at va `0xb00000`, RWX, `filesz == memsz == len`, align `0x10000` (the mapping
is checked not to overlap any segment; the ELF still parses with pyelftools, `elfinfo.py`, `disasm.py`).
The payload keeps no `.bss`: writable state is a zero-filled `PROGBITS` `.scratch`
section, so `memsz == filesz` holds; `pod.py` rejects a non-empty `.bss`/`.sbss` and checks `.scratch`
is inside the payload and shipped zeroed. Everything larger (Cover Flow's frame and textures, job
array, album copy, album header cover) is heap, allocated when the page opens and freed on close.
Sizes are recorded in the build manifest. Compilation is non-PIC (`clang --target=mipsel-linux-gnu -march=mips32r2
-mabi=32 -mfp64 -mno-abicalls -fno-pic -G0 -Oz`, `-Wall -Wextra -Werror`), linked by `patch/link.ld`
at `0xb00000` with `--gc-sections`. `tools/pod.py` defines the source order in `SOURCES`.

## $gp and the trampolines

Every stock PIC function starts with `lui $gp,hi; addiu $gp,$gp,lo; addu $gp,$gp,$t9` which makes
`$gp = 0xa03ed0` (`DT_PLTGOT + 0x7ff0`). The payload needs no `$gp` of its own and reaches stock code
and data by absolute address. Each hook has a trampoline that restores `$gp` and resumes the stock
function past its 3-word prologue (`lui $gp,0xa03e; ori $gp,$gp,0x3ed0; j <fn+12>; nop`).

## Calling stock code and libc

- **Stock functions** are absolute-address macros in the generated `stock.h`
  (`#define widget_lookup ((void*(*)(void*,const char*,int))0x666a74u)`); the callee sets up its own
  `$gp` from `$t9`. `pod.py FUNCTIONS` lists every one with its address and checks each against
  `.dynsym` before writing; `DATA` pins the exported data (`pdeq_showlist` `0xa045d8`,
  `parse_cover_mutex` `0xa04588`, `g_class_type` `0x97cad4`, `classinfo` `0xa0c768`).
- **Stock list queries are page state.** `loadLocalClassList` / `loadAlbumList` replace `*pdeq_showlist` (and may
  set `nagvation_title`, `classinfo`), which every stock list page draws its rows from and plays from, and which
  their to-foreground does not read again while the class is unchanged. Run them only from the page in front
  (its open, its tap, its own to-foreground), never from a timer or tick that runs while another page is in front:
  a page goes quiet on `EVT_WINDOW_TO_BG` (`patch/playlists.c` `pl_on_bg`), Now Playing's tick queries nothing
  (`docs/modules/recent.md`).
- **libc** only through slots `demo` already imports: a stub `lui/ori $t8, slot; lw $t9,0($t8); jr
  $t9` tail-calls the resolved pointer (`pod.py LIBC`: atoi, access, open/read/write/close/fsync,
  memset/memcpy/strcmp/strcasecmp/strdup/snprintf, calloc/free, fopen/fclose/fread/fwrite/fseek/ftell,
  rename/unlink/mkdir/statfs, pthread_create/join, mutex lock/unlock, the libcstl deque calls; for the Podcasts refresh worker also libcurl's easy interface, pthread_detach and
  demo's libjpeg 7 with `_setjmp`). No new imports are added. The worker (`patch/pcnet.c`, `pcfeed.c`, `pccover.c`; source order `pcmodel.c pcfeed.c pcpng.c pccover.c pcnet.c podcasts.c`; `pcpng.c` is a streaming PNG decoder of our own, with no import of its own) is started by a tap on
  Refresh All / Import and ends by itself; it touches no widget and calls no stock function, so the safety list of `AGENTS.md` does not change. The one stock address it uses is libjpeg's
  `error_exit` `0x5dbfe0`; `JPEG_PINS` in `tools/pod.py` pins it and every libjpeg structure offset and size `patch/pccover.c` writes against stock's own decoder and encoder
  (`0x5dd5ec`, `0x5de554`).

## Hook sites

1. **Home icon click dispatcher** `0x533b80` (unnamed in `.dynsym`; registered on each Home icon by
   `home_page_init` via `widget_on(icon, EVT_CLICK=0x10c, ...)`). Pinned prologue `(0x3c1c004d,
   0x279c0350, 0x0399e021)` is overwritten with `j m1plus_home_click; nop`; resume `0x533b8c`. It opens the menu for
   id 99 (the M1+ Music icon) and, as the recovery fallback (section 9, Recovery), for id 1 (Tidal) while
   `/mnt/data/m1plus-bad` exists; every other tap goes to stock.
2. **`home_page_init`** `0x534cd4` (the boot guard, section 7). Pinned prologue `(0x3c1c004d,
   0x279cf1fc, 0x0399e021)`, `$gp` checked, overwritten with `j m1plus_home_init; nop`; resume `0x534ce0`.

3. **`albuminfo_listitem0_layout`** `0x526264` (the album page's header builder; patch/albuminfo.c,
   section 8). Pinned prologue `(0x3c1c004e, 0x279cdc6c, 0x0399e021)`, `$gp` checked, overwritten with
   `j m1plus_albuminfo_header; nop`; resume `0x526270`. Its only callers are `albumdeinfo_listitem_layout+0x1d0`
   (`0x526564`: the list builder of `albuminfo_page_init` and of the page's to-foreground rebuild), so it
   runs only while that page builds its list: never at boot, in the main loop or during paint. The hook
   runs the stock function to completion, then restyles its four widgets; any mismatch leaves stock.

4. **`playing_page_init`** `0x53d1e4` (Now Playing's init; patch/nowplaying.c, section 8a). Pinned prologue
   `(0x3c1c004c, 0x279c6cec, 0x0399e021)`, `$gp` checked, overwritten with `j m1plus_playing_init; nop`; resume `0x53d1f0`. Its only
   caller is the navigator's page-init dispatcher (`0x4d1b3c`, behind the cut `tools/reach.py` uses), so it runs only when
   the page is built. The hook runs the stock function to completion and returns its result, then (if it returned `RET_OK`
   for a non-null window and the kill switch is absent) starts the page timer; any failure leaves the stock page.

5. **`get_id3info`'s tag copy** `0x4dff4c` (stock's tag reader, `0x4dfd58`; `patch/pcmodel.c` `pc_id3_path`, `docs/modules/podcasts.md` "Tags"). A **call-site** word, not a prologue: the `jalr strcpy(info, path)` that every fresh
   parse reaches after `toolsGetMusicInfo` has filled `playsong_id3info`, becomes `jal pc_id3_path` (the pinned words: the prologue `(0x3c1c0052, 0x279c4178, 0x0399e021)`, `lw t9` GOT strcpy `0x8f99f324` @0x4dff40, `lw a0` GOT info `0x8f84aa64` @0x4dff44, `sw v0,0x400(s1)` `0xae220400` @0x4dff48,
   the `jalr` `0x0320f809` @0x4dff4c, the delay slot `lw a1,0xc(s0)` `0x8e05000c` @0x4dff50, `lw t9` memset `0x8f99f524` @0x4dff58). The delay slot still loads the path, `s0` is the record. The function does stock's strcpy (bounded at 0x3ff, the CUE start follows) and returns `info`;
   for a path under `/mnt/mmc/Podcasts/` only (and no kill switch) it then writes the episode, show and album into the struct, and stock's code after the site builds `song_name` / `song_artist` from them. It is **reachable at boot** (`tools/reach.py`: Memory Playback's `start_player` -> `get_id3info`, over-approximated chain `platform_init` ->
   `deqVipPackage_init` -> `get_hifi_lyric_address` -> `sub_500cc0` -> `get_id3info`), so it does no file I/O except the kill-switch check for a podcast path, no allocation and nothing else for any other path. Attribution: q2-pod's `ID3_PATH` / `ringnav_id3_path` (the same site in its demo), `README.md`.

6. **The library scan's folder test** `0x5ea6a8` (stock's folder lister `0x5ea364`, called by `toolsLoadAllFile` `0x5efd98`; `patch/common.c` `pod_scan_dir`). A **call-site** word: for a directory entry (`d_type` 4, name in `s0`) the lister's readdir loop (`0x5ea600`) tests `strcmp(name, ".")`, then `".."`, `lost+found`, `System Volume Information`, `RECYCLER`, `$RECYCLE.BIN`, `.LOST.DIR`, `.fseventsd`, `.Spotlight-V100`, `.Trashes`; a zero result (`beqz v0, 0x5ea600`) goes back to readdir, so the entry is neither listed nor walked (the recursion into a folder is `toolsLoadAllFile` itself, over the listed names). Every other dot-folder (such as `/mnt/mmc/.m1plus/`) was walked, and its audio files joined Songs and Albums. The `jalr` becomes `jal pod_scan_dir`, which returns 0 for a name starting with `.` and `strcmp(name, dot)` otherwise (the delay slot `addiu a1,a1,0x3ed4` still loads `"."`). Only directory entries are affected: files take the other branch (`d_type` 8; `._*` AppleDouble files are already skipped there). Pinned: the prologue `(0x3c1c0042, 0x279c9b6c, 0x0399e021)`, `lw a1` `0x8f85a708` @0x5ea69c, `move a0,s0` `0x02002025` @0x5ea6a0, `lw t9` GOT strcmp `0x8f99f56c` @0x5ea6a4, the `jalr` `0x0320f809`, the delay slot `0x24a53ed4`, `beqz v0` `0x1040ffd3` @0x5ea6b0. **Not reachable at boot** (`tools/reach.py`: neither `0x5ea6a8` nor `toolsLoadAllFile`); the scan runs from Update Local Music (`scanAllMusicFile`, `scanSpecFolder`). No kill switch and no I/O: a compare of the first byte. After q2-pod's `SCAN_DIRS` / `ringnav_scan_dir`. Test: `test/pod/scan.py` (stock's name test run under Unicorn, stock and built).
7. **The Library queries** `toolsQueryDbTable` `0x5ee77c` and `toolsQueryDbTableAndSort` `0x5ee9ac` (`patch/pcmodel.c` `pc_library_query` / `pc_sorted_query`; the Songs title sorts `sort_filename` / `sort_format` use the second). Both are PIC-prologue hooks like hooks 1-4: pinned `(0x3c1c0041, 0x279c5754, 0x0399e021)` and `(0x3c1c0041, 0x279c5524, 0x0399e021)` (the `gp` checked to be `0xa03ed0`), overwritten with `j target; nop`, and trampolines (`stock_dbquery_trampoline`, `stock_sorted_query_trampoline`) that restore `gp` and resume at `+12` (`addiu sp` `0x27bdff28` @0x5ee788 and `0x27bdfe80` @0x5ee9b8 pinned, as are the `jalr sqlite3_exec` `0x0320f809` @0x5ee7fc and @0x5eea2c, whose `a1` is the SQL). Arguments `(db, sql, row callback, sort)` pass through unchanged. For a statement that starts with `select ` and contains ` from songtable` (followed by a space, `;` or the end) the hook runs stock with the table replaced by `(select * from songtable where ifnull(fileurl,'') not like '/mnt/mmc/podcasts/%')` (SQLite LIKE: ASCII case-insensitive, so `/mnt/mmc/pOdCaStS/x.mp3` goes, `/mnt/mmc/Podcasts Extra/` and `/mnt/mmc/Music/Podcasts/` stay), before stock's grouping: an album shared by music and an episode keeps the music row and its artwork, untagged episodes add no Unknown rows. Any other text, a missing SQL pointer or a rewrite over 1 KB (a stack buffer; no allocation) goes to stock untouched; no file I/O, no kill-switch read. **Reachable at boot** (`tools/reach.py`: `onlineDownloadThd` -> `loadLocalClassList` -> `getAllMusic` -> `sort_format` -> `toolsQueryDbTableAndSort`, over-approximated; really Memory Playback's library queue), so a failure degrades to the stock SQL and nothing else. The filter is not scoped (podcasts.md "Keeping podcasts out" has the reasons). After q2-pod's `dbquery` / `sorted_query` hooks, `ringnav_library_query` and `MUSIC_WHERE`. Test: `test/pod/scan.py` (SQLite).
8. **More dialog initialization** `dialog_playmore_dialog_init` `0x479cc4`. Pinned prologue
   `(0x3c1c0059, 0x279ca20c, 0x0399e021)` becomes `j m1plus_playmore_init; nop`; resume
   `0x479cd0`. Stock runs first. Arrangement is confined to the dialog's open and own handlers;
   failures leave stock rows. See [More sheet](playmore.md#the-hook).

`pod.py` asserts the three prologue words and the resulting `$gp` of each hook before writing, checks
that no row edit touches a hook site, and pins the input `demo` by SHA-256 (the `.pdr`-zeroed stock binary).
Library rows use call-site/immediate edits, not additional prologue hooks. Page-owned paint
events and timers follow their feature's lifetime; there is no added global paint or main-loop hook.
One more site is a data word, not a code hook (section 8d): `g_scroll_view_vtable + 0x98` (`0x97a330`), the
`on_event_before_children` slot, empty in stock, runs for touches inside a `scroll_view` only; that includes the Albums page since its content sits in a stock `list_view > scroll_view` (the page has no drag, fling or catch code of its own; it adds
no hook: taps use its content view's `EVT_POINTER_*` handlers and loading uses a page timer;
see [Albums](albums.md)).

## What the entry does (`patch/m1plus.c`)

`m1plus_home_click(icon, e)`: read the icon's name (`icon + 0x10`, stock stores the Home id as a
decimal string), `atoi` it; if it is not the entry id (`POD_ENTRY_ID` = 99, the icon patch/home.c adds; Tidal, id 1, is stock), or the kill-switch
file exists, or the page fails to open, tail into `stock_home_click_trampoline` (unchanged stock
behaviour). Otherwise `window_open` the entry page, bind `btn_return` -> `navigator_back`,
`btn_backtoplayer` -> `on_backtoplayer_onclick` and each `pod_rowN` to its action, return 0.

`tools/pod_pages.py` defines `PAGES`, `ITEMS` and actions once. `pod_ui.py` builds their assets;
`pod.py` emits the C tables into `stock.h`. The dispatcher in `patch/m1plus.c` binds actions
and falls back to stock when a destination cannot open. See [menu layout](menu.md) and
[settings](settings.md) for persisted state and navigation.

To add a page, define its page/row in `pod_pages.py`, implement its action, rebuild the assets
and tables, and add a `test/pod/` module. Keep widget names and stock fallback intact.

## Why the entry is an added icon

The entry is an icon of its own, id 99 ("M1+ Music"), which `patch/home.c` adds to the stock grid (section 9);
Tidal opens Tidal. The icon has no stock
id, so it cannot be hidden in Home customisation (the grid rebuild drops it; `hm_fg` puts it back), and the
dispatcher's bounds check (`sltiu 0x12`, `0x533ba8`) sends an id outside 0..17 to its default (nothing), so
a tap that reaches stock with the kill switch on is harmless. The HiFi store (id 0) was never usable: demo
only puts it on Home when the `language` global is 0 (Simplified Chinese), and patching that check needs
branch patches on the boot path (`reset_homemenu_index`, `load_home_menu`).
