# Known addresses of stock V2.1 demo

Split out of docs/architecture.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 3. Known addresses (stock V2.1 `demo`)

Payload `PT_LOAD` `0xb00000`; `$gp = 0xa03ed0`; hooks `0x533b80` (Home icon dispatcher, registered
through `widget_on`, GOT slot `0x9fe700`), `0x534cd4` (`home_page_init`) and `0x526264`
(`albuminfo_listitem0_layout`) and `0x53d1e4` (`playing_page_init`). `.pdr` is zeroed in `demo`
only; the About FW. Version stays `V2.1` and a row `M1+ Pod:<tag>` follows it (asset-only, `tools/mod_about.py`, no hook). Find more with `tools/dis.py` (`sym`, `addr`, `xref`,
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
| Play all | the button handler `0x525d48`: the list's first track, `loadSongList(queue, name, cue, g_class_type)`, `start_player(queue, index, class, 2)` (`0x4e4648`), `force_refreshflag` `0xa05a63` = 1; the page stays up | what ours copies (Play all and Shuffle then open Now Playing like a track tap; the hook takes this handler off the button, `widget_off_by_func` `0x666ec0`) |
| play | `loadSongList(queue, name, cue_start, cls)` (`0x4e2ce0`) then `navigator_to_with_context("playing_page", {queue, index, cls, 2})` (`0x4d1d48`) | the row handler `0x5275a4`; `loadSongList` also fills `g_memory_info` `0xa0caf8` for memory playback |
| art | `toolsGetAlbumCover` `0x5eaee0` (embedded) then `toolsGetExternCover` `0x5eafec` (folder image) | order and lock of `parse_albumcovertask_thd` `0x4dd68c` |
