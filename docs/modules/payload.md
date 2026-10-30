# The code payload: segment, trampolines, hooks, the entry

Split out of docs/architecture.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 2. The payload

M1+ Music adds new pages to the UI app by injecting machine code into `/release/bin/demo`, the way
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
at `0xb00000` with `--gc-sections`, sources in this order: `m1plus.c covercache.c coverflow.c albums.c
artists.c shuffle.c albuminfo.c nowplaying.c minibar.c grid.c recent.c rows.c shot.c home.c`.

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
- **Stock list queries are page state.** `loadLocalClassList` / `loadAlbumList` replace `*pdeq_showlist` (and may
  set `nagvation_title`, `classinfo`), which every stock list page draws its rows from and plays from, and which
  their to-foreground does not read again while the class is unchanged. Run them only from the page in front
  (its open, its tap, its own to-foreground), never from a timer or tick that runs while another page is in front:
  a page goes quiet on `EVT_WINDOW_TO_BG` (`patch/playlists.c` `pl_on_bg`), Now Playing's tick queries nothing
  (`docs/modules/recent.md`).
- **libc** only through slots `demo` already imports: a stub `lui/ori $t8, slot; lw $t9,0($t8); jr
  $t9` tail-calls the resolved pointer (`pod.py LIBC`: atoi, access, open/read/write/close/fsync,
  memset/memcpy/strcmp/strcasecmp/strdup/snprintf, calloc/free, fopen/fclose/fread/fwrite/fseek/ftell,
  rename/unlink/mkdir/statfs, pthread_create/join, mutex lock/unlock, the libcstl deque calls). No
  new imports are added.

### The five hooks

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
   `deqVipPackage_init` -> `get_hifi_lyric_address` -> `sub_500cc0` -> `get_id3info`), so it does no file I/O except the kill-switch check for a podcast path, no allocation and nothing else for any other path. Attribution: q2-pod's `ID3_PATH` / `ringnav_id3_path` (the same site in its demo), `NOTICE`.

6. **The library scan's folder test** `0x5ea6a8` (stock's folder lister `0x5ea364`, called by `toolsLoadAllFile` `0x5efd98`; `patch/common.c` `pod_scan_dir`). A **call-site** word: for a directory entry (`d_type` 4, name in `s0`) the lister's readdir loop (`0x5ea600`) tests `strcmp(name, ".")`, then `".."`, `lost+found`, `System Volume Information`, `RECYCLER`, `$RECYCLE.BIN`, `.LOST.DIR`, `.fseventsd`, `.Spotlight-V100`, `.Trashes`; a zero result (`beqz v0, 0x5ea600`) goes back to readdir, so the entry is neither listed nor walked (the recursion into a folder is `toolsLoadAllFile` itself, over the listed names). Every other dot-folder (such as `/mnt/mmc/.m1plus/`) was walked, and its audio files joined Songs and Albums. The `jalr` becomes `jal pod_scan_dir`, which returns 0 for a name starting with `.` and `strcmp(name, dot)` otherwise (the delay slot `addiu a1,a1,0x3ed4` still loads `"."`). Only directory entries are affected: files take the other branch (`d_type` 8; `._*` AppleDouble files are already skipped there). Pinned: the prologue `(0x3c1c0042, 0x279c9b6c, 0x0399e021)`, `lw a1` `0x8f85a708` @0x5ea69c, `move a0,s0` `0x02002025` @0x5ea6a0, `lw t9` GOT strcmp `0x8f99f56c` @0x5ea6a4, the `jalr` `0x0320f809`, the delay slot `0x24a53ed4`, `beqz v0` `0x1040ffd3` @0x5ea6b0. **Not reachable at boot** (`tools/reach.py`: neither `0x5ea6a8` nor `toolsLoadAllFile`); the scan runs from Update Local Music (`scanAllMusicFile`, `scanSpecFolder`). No kill switch and no I/O: a compare of the first byte. Attribution: q2-pod's `SCAN_DIRS` / `ringnav_scan_dir`, `NOTICE`. Test: `test/pod/scan.py` (stock's name test run under Unicorn, stock and built).
7. **The Library queries** `toolsQueryDbTable` `0x5ee77c` and `toolsQueryDbTableAndSort` `0x5ee9ac` (`patch/pcmodel.c` `pc_library_query` / `pc_sorted_query`; the Songs title sorts `sort_filename` / `sort_format` use the second). Both are PIC-prologue hooks like hooks 1-4: pinned `(0x3c1c0041, 0x279c5754, 0x0399e021)` and `(0x3c1c0041, 0x279c5524, 0x0399e021)` (the `gp` checked to be `0xa03ed0`), overwritten with `j target; nop`, and trampolines (`stock_dbquery_trampoline`, `stock_sorted_query_trampoline`) that restore `gp` and resume at `+12` (`addiu sp` `0x27bdff28` @0x5ee788 and `0x27bdfe80` @0x5ee9b8 pinned, as are the `jalr sqlite3_exec` `0x0320f809` @0x5ee7fc and @0x5eea2c, whose `a1` is the SQL). Arguments `(db, sql, row callback, sort)` pass through unchanged. For a statement that starts with `select ` and contains ` from songtable` (followed by a space, `;` or the end) the hook runs stock with the table replaced by `(select * from songtable where ifnull(fileurl,'') not like '/mnt/mmc/podcasts/%')` (SQLite LIKE: ASCII case-insensitive, so `/mnt/mmc/pOdCaStS/x.mp3` goes, `/mnt/mmc/Podcasts Extra/` and `/mnt/mmc/Music/Podcasts/` stay), before stock's grouping: an album shared by music and an episode keeps the music row and its artwork, untagged episodes add no Unknown rows. Any other text, a missing SQL pointer or a rewrite over 1 KB (a stack buffer; no allocation) goes to stock untouched; no file I/O, no kill-switch read. **Reachable at boot** (`tools/reach.py`: `onlineDownloadThd` -> `loadLocalClassList` -> `getAllMusic` -> `sort_format` -> `toolsQueryDbTableAndSort`, over-approximated; really Memory Playback's library queue), so a failure degrades to the stock SQL and nothing else. The filter is not scoped (podcasts.md "Keeping podcasts out" has the reasons). Attribution: q2-pod's `dbquery` / `sorted_query` hooks, `ringnav_library_query` and `MUSIC_WHERE`, `NOTICE`. Test: `test/pod/scan.py` (SQLite).

`pod.py` asserts the three prologue words and the resulting `$gp` of each hook before writing, checks
that no row edit touches a hook site, and pins the input `demo` by SHA-256 (the `.pdr`-zeroed stock binary).
Nothing else is hooked: no prologue is rewritten for the library rows (they are call-site edits,
section 6), and nothing runs in `platform_init` or the main loop. The only code at paint is the Now Playing
cover widget's own `EVT_AFTER_PAINT` (section 8a), registered by hook 4 on that page's widget.
One more site is a data word, not a code hook (section 8d): `g_scroll_view_vtable + 0x98` (`0x97a330`), the
`on_event_before_children` slot, empty in stock, runs for touches inside a `scroll_view` only; that includes the Albums page since its content sits in a stock `list_view > scroll_view` (the page has no drag, fling or catch code of its own; it adds
no hook: its taps are `EVT_POINTER_*` handlers on its own content view, its loader a page-scoped timer, `docs/modules/albums.md`; payload 95,416 B).

### What the entry does (`patch/m1plus.c`)

`m1plus_home_click(icon, e)`: read the icon's name (`icon + 0x10`, stock stores the Home id as a
decimal string), `atoi` it; if it is not the entry id (`POD_ENTRY_ID` = 99, the icon patch/home.c adds; Tidal, id 1, is stock), or the kill-switch
file exists, or the page fails to open, tail into `stock_home_click_trampoline` (unchanged stock
behaviour). Otherwise `window_open` the entry page, bind `btn_return` -> `navigator_back`,
`btn_backtoplayer` -> `on_backtoplayer_onclick` and each `pod_rowN` to its action, return 0.

Pages are defined once in `tools/pod_pages.py` (`PAGES`: menu, Cover Flow, Artists, Shuffle, Settings, Extras, Albums, Main Menu) and
consumed by `pod_ui.py` (assets) and `pod.py` (the C row/page tables in `stock.h`), so a row's widget,
label and handler cannot drift apart. Row actions: `ACT_HOME` (open a stock Home destination through
the dispatcher with a fake numeric-named icon), `ACT_PAGE`, `ACT_PLAYER` (stock
`on_backtoplayer_onclick`), `ACT_COVER`, `ACT_SHUFFLE`, `ACT_ARTISTS` (arg 0 Artists, else the Genres / Composers tile), `ACT_ALBUMS`, `ACT_PLAYLISTS` (the mosaic grid, `docs/modules/playlists.md`), `ACT_SONGS` (the Songs page, `docs/modules/songs.md`), `ACT_IPOD` (the virtual iPod Classic page, `docs/modules/ipod.md`), `ACT_GRID`, `ACT_STARTUP`, `ACT_LANDSCAPE` (switch rows, below), `ACT_SORT` (a value row, below), `ACT_SHOT` (Screenshot, section 8c), `ACT_SHELF` and `ACT_DAILY` (the shelf and Daily Mix card switches), `ACT_REGEN` (Regenerate Daily Mix: an action row without a chevron, `docs/modules/dailymix.md`). The
menu items (`ITEMS`, the item id = the row index, default order) are Now Playing, Cover Flow, Albums (-> our page, grid or list mode, section 5a), Artists (-> our list), Songs (-> our page, `docs/modules/songs.md`), Playlists (-> our mosaic grid), Shuffle (-> Shuffle page),
Genres (-> the Artists page on class `0xf006`), Folders, then the nine Extras tiles (ids 9-17: Favorites, Recently Added, Recently Played, Most Played, Composers, Hi-Res, Update Library, Tidal, CD Ripper; the Home ids 10, 13, 12, 11, 8, 9, 2, 1, 15: the song lists on our Songs page, Composers on our Artists page, the rest through the dispatcher, which is also every fallback; hidden by default); then Customize (item 18, saved character `j`, hidden by default) and Extras (always last; -> Extras page: a row per item, of which it lists those the menu does not show and the saved list's `-` part did not turn off, never Customize, in the fixed grouped order `pod_pages.EXTRAS_ORDER`, emitted as `POD_EXTRAS_ORDER` in `stock.h`; its navbar has the Customize button; Customize > Extras edits the `-` part). Customize (-> Customize page: Main Menu, Cover Flow (-> `m1plus_cfset`), Home Screen (-> `m1plus_homeset`: the Start in M1+ Music
switch and Shanling Home), Playback and System Settings through the stock dispatcher with ids 16 and 17, and Screenshot, `ACT_SHOT`, section 8c: no item id, no menu character). Page layout: `docs/ui.md`. To add a
page: add a `Page` and a row to `pod_pages.py`, rebuild (assets and tables regenerate), add a test
module under `test/pod/`.

### Why the entry is an added icon

The entry is an icon of its own, id 99 ("M1+ Music"), which `patch/home.c` adds to the stock grid (section 9);
Tidal opens Tidal. The icon has no stock
id, so it cannot be hidden in Home customisation (the grid rebuild drops it; `hm_fg` puts it back), and the
dispatcher's bounds check (`sltiu 0x12`, `0x533ba8`) sends an id outside 0..17 to its default (nothing), so
a tap that reaches stock with the kill switch on is harmless. The HiFi store (id 0) was never usable: demo
only puts it on Home when the `language` global is 0 (Simplified Chinese), and patching that check needs
branch patches on the boot path (`reset_homemenu_index`, `load_home_menu`).
