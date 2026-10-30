# Known addresses of stock V2.1 demo

Split out of docs/architecture.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 3. Known addresses (stock V2.1 `demo`)

Payload `PT_LOAD` `0xb00000`; `$gp = 0xa03ed0`; hooks `0x533b80` (Home icon dispatcher, registered
through `widget_on`, GOT slot `0x9fe700`), `0x534cd4` (`home_page_init`) and `0x526264`
(`albuminfo_listitem0_layout`) and `0x53d1e4` (`playing_page_init`). `.pdr` is zeroed in `demo`
only; the About FW. Version stays `V2.1` and a row `M1+ Music:<tag>` follows it (asset-only, `tools/mod_about.py`, no hook). Find more with `tools/dis.py` (`sym`, `addr`, `xref`,
`strxref`, `callers`, `strings-xref`, `full`).

Pinned stock functions, beyond those in the sections below: `widget_lookup` `0x666a74`, `widget_on`
`0x666d20`, `widget_set_text_utf8` `0x66f720`, `navigator_back` `0x4d20dc`, `on_backtoplayer_onclick`
`0x4cd58c`, `window_open` `0x679fd4`, `widget_set_visible` `0x66c394`, `widget_set_sensitive`
`0x666b9c`, `widget_set_opacity` `0x669140` (stores the byte at `+0x34`, then `widget_invalidate`; the dimmed Regenerate Daily Mix row), `slide_menu_set_value` `0x61399c`, `window_manager` `0x6774b4`,
`window_manager_get_top_main_window` `0x6774f0`, `widget_is_window_opened` `0x66aa04`. Also pinned:
the stock `slide_menu` constructor `0x613914` stores `value = 1` (`sw 1, 0x78` at `0x613970`);
`slide_menu_set_value` -> `0x6120ac` (events `0x11b`, `0x11c`); `songtable` record fields `year`
`+0x30`, `track` `+0x3c`, `cd_num` `+0x40`, `time`/`time_end` `+0x48`/`+0x4c` (CUE offsets, 0 for
ordinary files; no duration column); `toolsLoadAllFile` `0x5efd98` and its insert `0x5edb18`;
`get_screensaver_image` `0x4d7524` (`screensaver_default`, the default wallpaper). Pinned for the Albums grid (section 5a):
`widget_to_local` `0x669b88` (walks the parent chain subtracting each `x`, `y`; the payload runs stock's own), `widget_prepare_text_style`
`0x66a214`, `canvas_draw_text_in_rect` `0x6496a0`, `canvas_measure_text` `0x644544` (returns a float in `$f0`),
`tk_utf8_to_utf16_ex` `0x70eb24` (`wchar_t` is 32 bit), `button_create` `0x622adc`.

Pinned for the mini player bar (`docs/modules/minibar.md`, evidence there): `playpause_quick_click` `0x4cd150` (no arguments; what the lock
screen's play button, Now Playing's and the hardware key call), `next_quick_click(e, 0)` `0x4ccf00` (reads `e->time` at `+8`, ignores a click within 1 s of
the last one: global `0xa05a40`), `mclGetPlayStatus` `0x5d3640` (2 = playing, 3 = paused after `mclSetPause`).

Pinned for the iPod page (`docs/modules/ipod.md`): `prev_quick_click` `0x4cccb0` (the twin of `next_quick_click`: same prologue and 1 s guard on `e->time`, `prev_music` `0x4e428c`), `loadAlbumdetailList(class, album record)` `0x4eea98` (class `0xf003` -> `0xff10`, `0xff01` -> `0xff11`, `0xff02` -> `0xff14`; the second argument is the album record of the shown list: `lw v0, (a1)` the id, `0x14(a1)` the name), and the data word `system_bar` `0xa06f90` (the status bar window; `pgbar_battery` `value` and `img_battery` `image` are what the real bar shows).

Pinned for the Tape page (`docs/modules/tape.md`, `tools/pod.py` `TAPE_PINS`; everything else it calls is pinned above for Cover Flow's landscape captions, the Pod and the mini player bar): `widget_invalidate_force` `0x6691d0` ends in `b widget_invalidate` `0x668d9c` with its rectangle untouched, and `widget_invalidate` uses a non-NULL `rect_t` (four 32 bit words x, y, w, h, 16 bytes, in the widget's own coordinates; NULL: `0, 0, w, h`), `widget_get_text_utf8` `0x667d84`.

Pinned for the Playlists page (`docs/modules/playlists.md`) and the Daily Mix page's Add disc (`checkPlayListExist` `0x4ee1a8` (rec, playlist id), `getPlayListMaxId` `0x4ee184`, `addPlayList` `0x4ee1cc`(rec), thin wrappers on `playlist` in `/mnt/data/database.db` (`0x5ef768`, `0x5ef968`, and `toolsInsertDbTable` `0x5ee2fc`); prologues pinned, with `batch_add_file`'s `0x4db34c..0x4db3d0` words, `tools/pod.py` `PLAYLIST_PINS`): `createPlayListItem` `0x4eeca8` (the stock list, a name or NULL: the new id, -1 full, -2 exists), `loadLocalClassList(0xf00b)` the playlists into `*pdeq_playlist` `0xa045d0`
and `(0xff13)` a playlist's songs (`classinfo[1]` = its id) into `*pdeq_showlist`, `nagvation_title` `0xa0533c`, `navigation_status` `0xa05a24`, the stock Playlists page's static Import / Export click handlers `0x53dedc` /
`0x53dd34` (and its row handler `0x53d300`, create handler `0x53e8e4`, multi-select delete handler `0x53dbcc`, which the page does not call).

Pinned for the Songs page (`docs/modules/songs.md`, evidence there): `sort_flag` `0xa059d4` (the list order of class `0xf001`: 0 alphabetical, 1 file name, 2 file format, 3 newest first, 4 oldest first; the sort dialog's row handler `0x47d114` stores it and calls
`write_int_config(v, "SYSSET", "SORTSELECT")` `0x4d6a2c`; `config_init` reads it back), the stock Songs page's click handlers `0x527014` (Sort: `navigator_to("dialog/sortselect_dialog")`) and `0x52704c` (Search: `navigator_to("search_page")`; `navigator_to` `0x4d1d80` is `navigator_to_with_context(name, 0)`),
the stock multi-select's selection `*0xa045e0` (a `vector<int>`, one entry per row of `*pdeq_showlist`, 1 = selected) with `select_recordinit(n)` `0x4da3b0` and `set_selectindex(i)` `0x4da434` (a toggle), `batch_delete_file(class, list, vector, 0, delete_file)` `0x4e1408` (`0xf001`: the generic loop `0x4e1664`; ends with `*0xa05a5a = 1`),
the delete handler `0x527f48`, the add handler `0x5280c0` (`dialog/batchadd_dialog`, then `navigator_to_with_context("playlist_page", 0x10000 | class)`: the playlist picker, row handler `0x53d300`, which runs `batch_add_file` `0x4da7dc` and closes itself), the multi-select button `0x52823c`; and `stSongInfo + 0x54`, the Initial byte (`'*'` digit, `'A'..'Z'`, `'#'`; scan `0x5edb18` / `0x5edcb8`, row callback `0x4e936c`, copy `0x5db9ac`, the stock letter index `getsidebarbyoffset` `0x4d94a4`).

The More sheet's rows (`playmore_dialog`, bound by the binder `0x478b44` with `widget_on(row, 0x10c, handler, dlg)`): Look up album `0x4795cc` (empty album string at `0xa0d88c + 0x404` -> the msginfo error via `0x479544`; else `window_close(dlg)`, fills the browsing record `0xa0c768` and `navigator_to("playerjumpinfo_page")`), Look up artist `0x4793ac` (`window_close(dlg)`, `navigator_close` `0x4d2118` of `album_page` and of `albuminfo_page` when `navigator_window_is_exist`, `songerinfoflag` `0xa04737` = 1, `navigator_to_with_context("album_page")`); `songerinfoflag` is cleared only by `album_page`'s window event handler `0x522c64` (bound @0x5248a0). `patch/playmore.c` replaces the album handler (docs/modules/playmore.md).

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
| an album's tracks | `loadAlbumdetailList(0xf003, row)` (`0x4eea98`) -> `loadLocalClassList(0xff10)` -> `getMusicByAlbum` | `albuminfo_page_init` `0x5268bc`; fills the browsing record `0xa0c768`; an artist's album: `0xff01` -> `0xff11` (`getMusicByAlbumAnd[Album]Songer` `0x4ed008` / `0x4ecd3c`); All songs row (`classinfo[8]` = 1, `0x4eebec`) -> every song of the artist. `loadAlbumdetailList`'s second argument is the album RECORD pointer (not an index; `loadAlbumList` leaves the All songs row last in `*pdeq_showlist`, `REC_ID` -2); the whole state is the 0x390 byte record (`loadAlbumList` memsets it; name +0x10d, album +0xd, all-songs byte +8, Unknown Artist byte +0xa), which a list that outlives the page snapshots (`patch/songs.c` `sg.ci`) |
| opening the album page | `navigator_to_with_context("albuminfo_page", class \| row << 16)`: the context is an integer, not a pointer. The Albums row handler `0x523d94` builds it from `g_class_type` (`0xf003` Albums, `0xff01` an artist's albums) and the row; the Search handler `0x540588` assigns its albums into `*pdeq_showlist` first and passes `0xf003`. `albuminfo_page_init` (`0x526828`) reads the album row from `*pdeq_showlist`, runs `loadAlbumdetailList(class, row)`, `add_albumcover_task(row, 1)` and stores `classinfo[0]` in `g_class_type` | the page expects `*pdeq_showlist` to be the album list the row came from and the cover-task list (`albumcoverinfo_init` `0x4dcf9c`, which `album_page_init` `0x5248d0` runs right after `loadAlbumList`) built from it |
| the album page's header | `albuminfo_listitem0_layout` `0x526264`: a 100 px `list_item` (`list_item_notpress_style`) holding the `img_albumcover_m` image 100x100 (draw type scale-auto, file `/tmp/abp/<md5>1.jpg` set by `0x525a38` once the cover task has made it), the title `hscroll_label` (`0x524990`, `srlabel_item_white_style`, text `classinfo+0xd`), the artist (`0x524a64`, `srlabel_item_gray18_style`, `classinfo+0x20d`) and the Play all `button` 90x28 (`btn_imgplayall_style`: an orange pill image with its text baked in); row 0 of the scroll_view, the 64 px track rows follow | the cover thread (`parse_albumcovertask_thd`) renders the flag-1 file at `0x64` px (`addiu s3, zero, 0x64` at `0x4dd670`; the flag-0 files of the Albums rows at `0x3c`); the file's only reader is this page |
| Play all | the button handler `0x525d48`: the list's first track, `loadSongList(queue, name, cue, g_class_type)`, `start_player(queue, index, class, 2)` (`0x4e4648`), `force_refreshflag` `0xa05a63` = 1; the page stays up | what ours copies (Play all and Shuffle then open Now Playing like a track tap; the hook takes this handler off the button, `widget_off_by_func` `0x666ec0`) |
| play | `loadSongList(queue, name, cue_start, cls)` (`0x4e2ce0`) then `navigator_to_with_context("playing_page", {queue, index, cls, 2})` (`0x4d1d48`) | the row handler `0x5275a4`; `loadSongList` also fills `g_memory_info` `0xa0caf8` for memory playback |
| art | `toolsGetAlbumCover` `0x5eaee0` (embedded) then `toolsGetExternCover` `0x5eafec` (folder image) | order and lock of `parse_albumcovertask_thd` `0x4dd68c` |
| Most Played, Recently Played, Favourites | `loadLocalClassList(0xf008)` -> `getAllOftenRecord` `0x4ec690` (`select * from oftenplay`, then sorted; `REC_TRACK` = plays - 1), `(0xf007)` -> `getAllRecentRecord` `0x4ec578` (`select * from recentplay ORDER BY id DESC`: the last played first, at most 100), `(0xf00a)` -> `getAllFav` `0x4ec45c` (`myfav`) | jump table `0x74c5b8`; the Daily Mix reads the three and the library |
| the playlist headers | `loadLocalClassList(0xf00b)` -> `getAllPlayList` `0x4ec4e8` (`select * from playlist where id <= 100`) into `*pdeq_playlist` (`0xa045d0`; the temporary list `0xa03964` is assigned to it and cleared, `0x4ee638..0x4ee664`), then `musicNagvationTitle` | `playlist_page_init` `0x53eb24`, `checkPlayListByName` `0x4ef2e4` |
| a playlist's songs | `loadLocalClassList(0xff13)` -> `getMusicByPlayList(classinfo[1])` `0x4eddac` (`select * from playlist where id > 100 and cd_num=%d`, no ORDER BY: row order = insertion order) into `*pdeq_showlist`, at `0x4ee744..0x4ee754` | the Songs page, `allmusic_page_init` `0x528968` |
| the other song lists of `allmusic_page` (our Songs page lists them too, docs/modules/songs.md "The other lists") | Home tiles 9 / 10 / 11 / 12 / 13 open it with `0xf002` Hi-Res, `0xf00a` Favourites, `0xf008` Most played, `0xf007` Recently played, `0xf009` Recently added (the table above); its navbar builder `0x526a3c` adds Sort only for `0xf001` (`0x526d04`) and Search for every class but `0xff09` (`0x526cf0`) | `0x526ce0..0x526e78` |
| a Genres row (`localclass_page` `0xf006`) | the row tap `0x535c4c`: `classinfo[0]` = `0xff09`, the genre's name (row `+0x1c`) into `classinfo + 0x30d`, `classinfo + 0xc` = (row id == -1), then `navigator_to_with_context("allmusic_page", 0xff09)`: the genre's songs | `0x535c4c..0x535cfc` |
| a composer's albums (our Artists page on `0xf005`, `coverflow_artist(.., CLASS_COMPOSERS)`) | `loadAlbumList(0xf005, row)` (`0x4ee8d8`; the branch `0x4ee9c0`): classinfo cleared, `classinfo[0]` = `0xff02`, the composer's name (row `+0x20`) into `classinfo + 0x20d` (0x100 bytes), the byte `classinfo + 0xb` = (row id == -1), then `loadLocalClassList(0xff02)` = `getAlbumByComposer` `0x4eb514` (`select id,album,composer,fileurl from songtable where composer=".." group by album COLLATE NOCASE`, NULL name for the unknown row; it appends the same last "All songs" row as `getAlbumByArtist`: id -2, type 4, "local_allsong", `0x4eb668..0x4eb690`, so the All albums card works unchanged). `loadAlbumdetailList(0xff02, row)` (`0x4eeb70`): `classinfo[8]` = (row id == -2), title from `row + 0x14`, class `0xff14` (`getMusicByAlbumAndComposer` `0x4ed2d4`; the album page's artist line is `classinfo + 0x20d` for `0xff14`, `CLASSINFO_ARTIST_14`, which `patch/albuminfo.c` already reads). So a composer's tap is an artist's with `0xf005` / `0xff02` for `0xf004` / `0xff01` | `0x4ee9c0..0x4eea2c`, `0x4ee810..0x4ee830`, `0x4eeb70..0x4eebc4`; not run on a device |
| a genre's name in the Genres rows | `getAllGenre` `0x4ec0dc` (`select id,style from songtable group by style COLLATE NOCASE`, an "Unknown Genre" row id -1) with its row callback `0x4e9b80`: the one string is copied twice, to `+0x1c` (what the row tap reads) and `+0x10` (`REC_TITLE`, what the rows show); `loadAlbumList(0xf006, row)` (`0x4eea2c`, class `0xff03`, name into `classinfo + 0x30d`, byte `+0xc`) is the stock album list of a genre, not used by ours (a genre's tap lists its songs) | `0x4e9bd8..0x4e9c64` |
| the title of a genre's songs | the page's title is made by the stock query itself (`loadLocalClassList` calls `musicNagvationTitle` `0x4ee2e4..`; `allmusic_page_init` copies `nagvation_title` `0xa0533c` into `0xa06690` after the query, `0x528a40..0x528a6c`), so the fallback to the stock page needs only the browsing record and `navigator_to_with_context("allmusic_page", 0xff09)` | `0x528a40` |
| an Artists / Composers row (`localclass_page` `0xf004` / `0xf005`) | the same handler's other branch `0x535d04`: `navigator_to_with_context("album_page", {g_class_type, row record})`: the stock list of that artist's or composer's albums | `0x535d04..0x535d54` |
| the stock Add button of `allmusic_page` | `0x5280c0`: `dialog/batchadd_dialog` (0 playlist, 1 favourites), then `navigator_to_with_context("playlist_page", 1 << 16 \| g_class_type)` (`0x52817c..0x528194`); favourites: `batch_add_file(.., 0xf00a, ..)` (`0x5281c8`) | `batch_add_file` (`0x4da7dc`) with class `0xff11` takes the generic path (rows of type 8), like the library's: an artist's songs list needs nothing special for Add (nor for Delete: `0xff11` is in the generic loop below) |
| opening a playlist | the Playlists row's tap `0x53d578..0x53d5f4`: `memset(0xa0533c, 0, 0x200)`, `snprintf(0xa0533c, 0x200, "%s", header->title)`, `classinfo[1]` (`0xa0c768 + 4`) = `header->cd_num`, `navigator_to_with_context("allmusic_page", 0xff13)`: the context is the class, a value. The page copies the title (`0xa0533c` -> `0xa06690`, `0x528a6c`) | what `patch/playlists.c` repeats (Daily Mix no longer opens a stock playlist: it has no playlist) |
| the playlist table | `playlist` in `/mnt/data/database.db`, the `songtable` columns: a header has `id <= 100`, type 4 (`+0x34`), the name at `+8` and `+0x10`, `cd_num` (`+0x40`) = its id; a song row has `id > 100` and `cd_num` = the header's id. `createPlayListItem` `0x4eeca8(deque, name)`: -1 for no deque, 100 or more headers or ids, -2 for a name already there, else the first id from 0 the headers (in id order) do not have, inserted with `addPlayList` | `0x4eed1c..0x4eeeb4` |
| the Daily Mix page (`dp_*`, docs/modules/dailymix.md "The page") | **no new address**: it uses calls already pinned above (`window_open` `0x679fd4`, `widget_set_style` `0x66c448` for the tint, `widget_move`, `widget_measure_text` `0x66c7e0`, the canvas calls, `loadLocalClassList(0xf001)` for the library, `loadSongList`, `_deque_push_back`); the asset is ours (`ui/m1plus_dailymix.bin`) | |
| the stock import sequence (`importPlayList` `0x4ef394`; the Daily Mix does not use it, but its files must never be importable: it reads only `/mnt/mmc/_explaylist_data` through `toolsGetDirectoryM3u8` `0x5e9794`, names ending `.m3u8` / `.m3u`; `checkPlayListExist`, `getPlayListMaxId` and `addPlayList` below ARE pinned since the Daily Mix page's Add disc, `docs/modules/dailymix.md` "The Add disc"; `deletePlaylist`, `deleteAllMusicByPlaylist` are not) | per playlist file: `checkPlayListByName` -> `deletePlaylist(id)` `0x4edf98` + `deleteAllMusicByPlaylist(id)` `0x4edfdc` + `loadLocalClassList(0xf00b)`; `createPlayListItem`; then per song `checkPlayListExist(rec, id)` `0x4ee1a8` (1 = already in), `getPlayListMaxId()` `0x4ee184` (the row id is `max(100, that) + 1`, `0x4ef614..0x4ef62c`), `get_songid3_info` `0x4da694` (tags from the file; the Daily Mix has them from the library), `addPlayList(rec)` `0x4ee1cc` (= `toolsInsertDbTable(rec, "playlist", db, 1)` `0x5ee2fc`: the row keeps `rec + 0`; strings `+8 +0xc +0x10 +0x14 +0x18 +0x1c +0x20 +0x24`, ints `+0x30 +0x3c +0x40 +0x48 +0x4c +0x50`, byte `+0x54`; returns 1). Addresses from the disassembly (no longer pinned by a test) | `0x4ef4b0..0x4ef83c` |

### Deleting by class

`batch_delete_file(class, list, selection, 0, delete_file)` (`0x4e1408`, pinned) is what every stock list's Delete runs, with `g_class_type` (the `allmusic_page` handler
`0x527f48`, after the one confirm dialog for all classes: `0xa` the list only, `0x14` with the file). It dispatches on the class: `0xf003..0xf00b` through the jump table
`0x74b7b0`, `0xff01..0xff14` through `0x74b7d4` (target = word + gp `0xa03ed0`), anything below `0xf003` (the library `0xf001`, Hi-Res `0xf002`) to the generic loop. Each loop
runs one table delete per marked row and then `remove_file` `0x4e1264` (`access`, `remove`, `sync`, then a look at the player's state) when `delete_file` is set:

| class | loop | per row |
|---|---|---|
| `0xf001` library, `0xf002` Hi-Res, `0xf009` Recently added, `0xff09` a genre's songs, `0xff10..0xff12`, `0xff14` | `0x4e1664` | `deleteMusicFromMusicDb` `0x4ede44` (`songtable`) |
| `0xf00a` Favourites | `0x4e1710` | `0x4ede88` (`myfav`: unfavourite) |
| `0xf008` Most played | `0x4e17b4` | `0x4edf10` (`oftenplay`) |
| `0xf007` Recently played | `0x4e1858` | `0x4edecc` (`recentplay`) |
| `0xff13` a playlist's songs | `0x4e18fc` | `deleteMusicFromPlaylist` `0x4edf54` (`playlist`) |
| `0xff04..0xff08`, `0xff0a..0xff0f` | none | nothing |

Screen state: exported byte `backlight_status` at `0x97cae4` is pinned in `tools/pod.py`. Stock `awake_screen` sets it to 1 before enabling the framebuffer; zero means off. Existing page-owned timers use it to defer visual work.

### Library scan and queries (patch/common.c `pod_scan_dir`, patch/pcmodel.c `pc_library_query`; `SCAN_PINS`, `QUERY_PINS` in tools/pod.py)

| What | Address | Evidence |
|---|---|---|
| `toolsLoadAllFile` | `0x5efd98` | recursive walk (calls itself through `0x418(sp)`); lists each folder with `0x5ea364`; callers `scanAllMusicFile` `0x4e9e5c`, `scanSpecFolder` `0x4e9f74`; not boot-reachable |
| the folder lister | `0x5ea364` | prologue `(0x3c1c0042, 0x279c9b6c, 0x0399e021)`; readdir loop at `0x5ea600`; a directory entry (`d_type` 4) goes through `strcmp` tests against `.`, `..`, `lost+found`, `System Volume Information`, `RECYCLER`, `$RECYCLE.BIN`, `.LOST.DIR`, `.fseventsd`, `.Spotlight-V100`, `.Trashes` (a zero result: back to `0x5ea600`), then `._` for files |
| the folder test's hook site | `0x5ea6a8` | `jalr strcmp(name, ".")` (words @`0x5ea69c..0x5ea6b0` pinned, the delay slot `0x24a53ed4` loads `"."` `0x743ed4`): replaced by `jal pod_scan_dir`; docs/modules/payload.md hook 6 |
| `toolsQueryDbTable` | `0x5ee77c` | prologue `(0x3c1c0041, 0x279c5754, 0x0399e021)`; `(db, sql, row cb, sort)`; `sqlite3_exec` @`0x5ee7fc`; 36 callers (every `getAll*` / `getMusicBy*` / `getAlbumBy*` / `Search*`, the fav / recent / often / playlist lists); hooked: `pc_library_query`, payload.md hook 7 |
| `toolsQueryDbTableAndSort` | `0x5ee9ac` | prologue `(0x3c1c0041, 0x279c5524, 0x0399e021)`; callers `sort_filename` `0x4ea18c`, `sort_format` `0x4ea218` (via `getAllMusic`); hooked: `pc_sorted_query` |
| the SQL texts | `0x74ba4c`.. | `"songtable"` `0x74ba4c`, `"myfav"` `0x74ba58`, formats from `0x74ba6c` (`select * from %s ...`) to `0x74c510`; sprintf'd by the `getAll*` / `getMusicBy*` wrappers; `toolsCheckItemExist` `0x5ef578` (the scan's duplicate check) runs its own `sqlite3_exec` |

### Podcasts (patch/pcmodel.c, `PODCAST_PINS` in tools/pod.py)

| What | Address | Evidence |
|---|---|---|
| `seek_time(sec)` (q2-pod's `player_seek_time`) | `0x4e0544` | prologue `(0x3c1c0052, 0x279c398c, 0x0399e021)`; `move s0,a0` @`0x4e0560`; `lw a0,0x48(v0)` (the record's CUE start) @`0x4e05f0`; `addu s0,s0,a0` @`0x4e05fc`; `jalr mclSetSeek` @`0x4e0608`; it returns 0 at once when `mclGetPlayStatus` is 1, resumes a paused player, waits up to 2 s for the second |
| `mclSetPlaySpeed(mode)` | `0x5d281c` | prologue `(0x3c1c0043, 0x279c16b4, 0x0399e021)`; `move a2,a0` @`0x5d2830` is the `%d` of `{mcl-playspeed\%d}` (`0x756510`) |
| `playspeed_mode` (data, dynsym) | `0xa05acc` | 0..3 = 1x, 1.25x, 1.5x, 2x; the Multiple Speed handlers (`0x479970`.. ) store 3, 2, 1, 0 and call `mclSetPlaySpeed`; `config_mplayer` `0x4d869c` sends it at set-up; `config_init` reads a value >= 4 as 0 |
| `get_id3info` | `0x4dfd58` | prologue `(0x3c1c0052, 0x279c4178, 0x0399e021)`; fills `playsong_id3info` from `toolsGetMusicInfo` `0x5ec6a8` (call @`0x4e0000`, `addiu a1,s1,0x404` @`0x4dfff8`) unless `mclGetCueFlag` (record `+0x48` or `+0x4c` > 0); title `lb 0x684(s1)` @`0x4dff74`, artist `lb 0x504(s1)` @`0x4dffac` |
| the tag reader's hook site | `0x4dff4c` | `jalr strcpy(info, path)` (words @`0x4dff40..0x4dff50` pinned): replaced by `jal pc_id3_path`; docs/modules/payload.md hook 5 |
| `playsong_id3info` (data, dynsym) | `0xa0d88c` | 0xa9c bytes: path (cache key) `+0`, CUE start `+0x400`, album `+0x404` (0x100), artist `+0x504` (0x100), composer `+0x604` (0x80), title `+0x684` (0x200) |
| `song_name` / `song_artist` (data, dynsym) | `0xa0513c` (0x200) / `0xa0503c` (0x100) | built by `get_id3info` after the site from the struct: title (else the file name `rec+8`), artist (else `"Unknown"` @`0x7466e8`); read by the Now Playing page (`0x5397a0`), the lock screen (`0x53f77c`), the Home guide page |
