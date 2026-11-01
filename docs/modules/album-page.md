# The album page

**Sources:** `patch/albumpage.c` (our page), `patch/songops.c` (play / Delete / Add shared with the Songs page, `pod_open_player`), `patch/covercache.c` `cc_open_album`, `tools/pod_ui.py` `build_album_page`,
tests `test/pod/albumpage.py`, `test/pod/shared.py` (`pod_open_player`, the tone cache).

## Our page (ui/m1plus_album.bin, window m1plus_album_page)

Every entry (Albums grid, Cover Flow, Recently Played, Now Playing's Look up album) goes through `cc_open_album`, which calls `album_open(class, album row)` first:
it runs `loadAlbumdetailList(class, row)` (class 0xff10 library album, 0xff11 artist's, 0xff14 composer's; the browsing record is snapshotted and put back before every query and play, as the
Songs page's artist list does) and opens our window. It returns -1 (kill switch, the All albums card, a page already open) or -2 (window or asset missing) and `cc_open_album` then loads the
album list again where needed and opens the **plain stock `albuminfo_page`**: the stock page is no longer restyled (no hook, no page theme; only its navbar view sits 3 px down like
`allmusic_page`'s, `mod_ipodrows.center_navbar`, because the shared navbar builder makes 44 px buttons). The stock Shanling Albums list and the stock Artists page's albums open the stock page. The
All albums card of Cover Flow's artist page is not an album: it opens our Songs page on all the artist's songs (`songs_open_artist`, as the Songs button does; a composer's card, or a Songs
page that will not open, falls back to `cc_open_album` on the All songs row: the stock page).

The design: a stock list that is the whole 450 px window (`view_grid` content view as on the Songs page) over a window colour and the `img_ah_tint`
gradient; header numbers `AH_*` (cover 160 px, 10 px corners cut in the alpha, at y 50; title 22 / artist 18 / "year · N tracks" 15 px lines; Shuffle disc and Play all pill at y 292); rows
64 px with a 19 px number column (22 px, 32 from 100) and 19 px title (gold when `is_playing`, a CUE track shows its file name), press fill 20 % white, hairline 13 % white, select marks.
Play all / Shuffle / track tap are `so_play` with `pod_open_player` (the stock row handler's tail and the songerinfoflag pop loop). Cover: the Cover Flow cache file, else one cache-worker
job polled every `AB_COVER_MS`, else the placeholder; tint from the tone cache or the file's average; status bar `pod_bar_tint` with the one-owner hand-over.

The controls are glass buttons, direct children of the window (last, so over the list): Back (`ah_nav_back`), capsule Select
(`pod_nav_selectl`, left cap) | Now Playing (`ah_nav_play`); select mode swaps in the all / none toggle, Add, Delete, Cancel at the stock builder's places. No Search button. They are not inside a bar
view because this AWTK's hit test would give a view's whole band to it.

Pinned stock: `is_playing` 0x4d9d64 and the album row builder's calls 0x524c40..0x524ca4 (`SONGS_PINS`). No hook.
Not verified on the device. The pill's text is painted by the page (not a button text), centred as a pair with the glyph from the measured text.

```
y   0  (back)                (select | now playing)   header 344 high; x is screen x, centre 160; the list starts at window row 0
    5   glass controls, 42 px high (band 4..48); the header's first 44 rows are padding
   50      +-----------+                 cover 160x160 at x 80, corners rounded 10 px (cut in the alpha)
           |   cover   |
  210      +-----------+
  224        Kind of Blue                 22 px white   (x 17 w 286 h 22, centred)
  247        Miles Davis                  18 px #AAAAAA (h 18, centred)
  267        1959 . 8 tracks              15 px #9C9C9C (h 15, centred)
  292   (shuf)  [ > Play all       ]      Shuffle 44x44 touch at x 42 (38 px disc), Play all 180x44 touch at x 95 (180x40 pill); drawn 12 px apart
  344   1  So What                        track rows, 64 px
```

**Vertical rhythm** (`tools/ah_ink.py`, measured on the shipped font's ink with the stb rasterizer; test `albumpage`): a gap runs from the
capitals' / digits' top to the line above's baseline (descenders not counted). Cap heights 14 / 11 / 9 px at 22 / 18 / 15 px. Cover bottom to title
capitals **16**, title baseline to artist capitals **9**, artist baseline to year digits **9**, year baseline to the pill's top **16** (outer gaps equal,
text gaps equal); the touch rectangles end 8 px above the first row. The label rects are their font size high (the line box centred in them).

**Cover tint.** A page showing a real cover is tinted like Now Playing: the window's `bg_color` is `pod_tone` (Now Playing's
`np_tone`, in `patch/common.c`; `NP_V_MIN/MAX`, white text keeps 4.5:1) of the cover's average colour, under `ah_tint.png`
(320x450, black, alpha 64 on window row 0 rising to **200** on row 343, the end of the header, and held at 200 below; the window's first
child `img_ah_tint`, insensitive), so the header fades from the tone to a **deep tint** (78 % dark) and the list below shows a deep version of the
cover colour (the track rows are painted by the page, transparent over it). Contrast (white title >= 4.5, track number `#AAAAAA` >= 3) over the
whole tone range at the held alpha 200: title 14.5:1, number 6.26:1 at rest; on the pressed row title 7.69:1, number 3.31:1 (the floor that fixed the alpha: at 190 it is 3.02:1; 20 % pressed, 4.5:1 for the number would need alpha 220+).
The gradient is fixed in the window: scrolled, text passes over lighter rows. The header at rest (ramp 64 to 200) keeps, over every tone: title 8.59:1, artist 4.06:1,
year line 3.78:1 (the controls' glyphs sit on glass: 8.0 / 15.9:1 over white / black, test `glassbtn`). A track row scrolled up to the window's top (window row 0, the brightest ramp row;
it passes under the controls) keeps at worst 3.23:1 for the title and 1.39:1 for the grey number over the brightest grey tone: a transient, only while it passes.
The placeholder disc, an album without art and the All albums card leave the page black.

**Status bar.** A tinted page tints the status bar like Now Playing (`pod_bar_tint` / `pod_bar_black`, `patch/common.c`; the full story is in `nowplaying.md`, section
"The status bar"): the bar takes the page's window row 0, the tone under the overlay's first alpha (64), darkened (`pod_bar_color`, `NP_BAR_LUM_MAX`) until the bar's
white clock and glyphs keep 4.5:1. That colour is constant (the overlay is a child of the window and does not scroll). `ab_bar_apply` applies it when the page is in front,
the window's TO_BG / TO_FG events black / re-tint it, destroy restores black first. **Hand-over:** the bar has one owner (the window that last tinted it) and only the owner can restore black, so Play all /
Shuffle (this page backgrounds, Now Playing takes the bar in any order of the two events) and Back never fight. Seam: for the tones the bar equals row 0 (155 of 217 tones in the test grid); for bright, high-luminance tones
(greens, cyans, yellows) it is darker: a bright cover (240, 225, 150) is 8 levels, the worst grid tone (131, 192, 192) is 34 levels in a channel.

**Tone cache (the tint at once).** `pod_tone_get` / `pod_tone_put` (`patch/common.c`): 64 entries of `{album key, tone word, use stamp}` (12 bytes, 768 bytes of
`.scratch`, no malloc), least recently used out, RAM only (nothing is written to the card), shared with Now Playing. The key is `cc_album_key`'s
(`cc_key_of(artist, album)`, FNV-1a of artist then album, the Cover Flow cache file's name). The page looks the key up first (a hit tints at once, no decode); a miss decodes
`/mnt/mmc/.m1plus/covers/<key>-168.jpg` (168 px, a few ms), sets the tint and inserts; the file there but **empty** (Cover Flow's "no art" marker) leaves the page black. Both pages take `pod_tone` of the `cc_box` average
of the centred square, and the cache then serves every later page. Measured (synthetic 900 px covers and the boot logo, JPEG q85 full size
against the same square at 160, 168 and 264 px, JPEG q80): the averages differ by at most 1 of 255 in a channel, a tone difference of at most 1 level. `test/pod/albumpage.py` and
`test/pod/shared.py` `tone_cache_tests` (LRU and bounds), `test/pod/nowplaying.py`.

**Record fields.** `getMusicByAlbum` / `getMusicByAlbumAnd[Album]Songer` (`select * from songtable`)
fill an `stSongInfo` per row via the callback `0x4e908c`; schema: `id, filename, fileurl, album, songer,
style, name, composer, albumsonger, year, track, cd_num, time, time_end, time_create, Initial,
bitdepth, samprate`. `year` is `atoi`'d to `+0x30`; the scanner (`toolsLoadAllFile` -> insert
`0x5edfc4`) writes it from `taglib_tag_year` (`toolsGetMusicInfo` `0x5ec6a8`, `+0x680` of its out
buffer). Shown: year (first track with 1000..2999; the All albums card, `classinfo[8]` set, shows none),
the track count. **No duration**: there is no duration column; `time`/`time_end` are CUE offsets, 0 for
ordinary files, and `toolsGetMusicInfo` reads only the sample rate and an MQA flag, never a length. The
line reads "year . N tracks" or "N tracks" ("1 track").

**Play all and Shuffle** (`ab_on_play`, `ab_on_shuffle`, `so_play` in `patch/songops.c`) run the stock Play all handler's sequence
(`0x525d48`) and then open Now Playing the way a track row's tap does. Play all takes the page's first track,
Shuffle a random one (`pod_rand`, the Shuffle page's generator); `access` check on that track (missing: the
toast "Storage unavailable", the page stays), `loadSongList(queue, name, cue, g_class_type)` (class `0xff10`, or
`0xff11` for an artist's album); Shuffle sets the stock Shuffle mode first (`pod_set_mode`:
`mclSetPlayMode`, `notifyPlayMode`, `dmrSendPlayMode`, `write_int_config`; nothing is written when already
Shuffle; the queue is this album alone so stock Shuffle shuffles exactly the album, and the mode stays Shuffle
afterwards); Play all sets an in-order mode (`pod_set_in_order`: Shuffle and Repeat one become List play, List play and Repeat all are kept, nothing written when unchanged). A queue that does not resolve starts nothing, changes nothing and
is freed. **Opening Now Playing** (`pod_open_player`, `patch/songops.c`) is the tail of the stock row handler `0x52569c` (a track
tap, `0x5258c8..0x525970`): if `songerinfoflag` (`0xa04737`) is set and `navigator_window_is_exist("playing_page")`,
the loop `0x525904..0x5259d8` pops with `navigator_back` every window above the topmost `playing_page` and
`window_close`s that old Now Playing (it also stops at `home_page`); then
`navigator_to_with_context("playing_page", {queue, index, class, 2})`, whose init (`start_player`) starts the player.
The stock loop trusts every `navigator_back` to change the top window at once (a close animation would spin it: `docs/modules/boot.md`); no library, Cover Flow, menu
or Now Playing page has one (only the settings windows, the keyboard and the lock screen slide), and the payload's copy is
bounded (`POP_MAX` 16 pops, then it opens over what is left). With the flag clear (or no Now Playing in the stack) the page
simply opens over the album page, exactly as a track tap does, so Back from Now Playing returns to it. `test/pod/shared.py` runs `pod_open_player` against a window stack (`StackMachine`: demo's own
`window_manager_get_top_window` over a window manager laid out in emulated memory, the rest of the stack calls modelled,
including a window that stays after `navigator_back`). `pod_rand`, `pod_toast`, `pod_set_mode`, `pod_set_in_order` are four exports at the end of
`patch/shuffle.c`.

**The cover thread's state** (for the stock page and Cover Flow's open). The thread
(`0x4dd450`) sleeps 50 ms while `albumcover_taskstate` (`0xa05a18`) is 2. `albumcoverinfo_init` (`0x4dcf9c`)
sets it to 2 (and clears `albumcover_finishflag` `0xa05a5b`); the batch queuers (`batchadd_albumcover_task`
`0x4dccac` -> `local_albumsmallcover_task` `0x4dcbb4`, `local_songercover_task` `0x4dccc8`) end by setting it
to 1; `add_albumcover_task` (`0x4dca38`, the one `albuminfo_page_init` calls) only clears the task list and
pushes `{row, 0, flag}`. The stock Albums list always runs the batch queuer right after the init
(`album_page_init` `0x5248d0`/`0x52496c`), so the state is 1 by the time albuminfo_page opens; Cover Flow ran
only the init, the thread stayed parked and the stock page's cover task (and its 500 ms refresh timer, `0x5261d8`,
which picks the `/tmp/abp/<md5>1.jpg` file up when it appears) waited for nothing. `cc_open_album` calls
`batchadd_albumcover_task(0, 0)` after the init for the stock fallback: no task, state := 1; the page queues its own. The stock header cover is
rendered at its stock 100 px (the release no longer changes that size).

Not done: a duration, a current-track marker in the stock page's rows (the stock page marks nothing).

## Other stock pages (assets; the code half is in the module docs)

`tools/preview_stock.py WORKDIR OUT.png`: the Albums list, Cover Flow on an artist, a playlist's
songs, the queue. Approximate mock-ups.

- **Artists, Genres, Composers** (stock `localclass_page`): the per-page placeholder disc (`icon_artist` / `icon_genre` /
  `icon_composer`, the same on every row) is hidden, so the name starts at the 12 px margin and runs to the chevron (265 px,
  was 217). The artist or genre that is playing shows the wave marker before the chevron (name 217 px).
- **A playlist's songs** (the stock `allmusic_page`, class `0xff13`, the playlist's name as the navbar title):
  the same 64 px rows and navbar as every library list, no header and no Play all button. The Pod's Playlists
  page no longer opens it (it opens our Songs page with the large title and Play / Shuffle, no hook:
  `docs/modules/songs.md` "The other lists"); it is reached from the stock Playlists page and as that page's
  fallback.
- **The queue drawer** (the stock fallback of our own Queue page, `docs/modules/queue.md`; `ui/dialog/playqueue_dialog.bin`, no preview): the 240x450
  panel that slides in from the right over Now Playing (opened by name from `playerjumpinfo_page_init` `0x53b17c` and
  `0x4d126c`; `dialog_playqueue_dialog_init` `0x47a7cc`). Its rows are cloned from a template (`queue_table_row`) by the stock table code, `row_height` read
  from the file, and bound by `0x47a19c`: the song name in `scrlabel_name` with `srlabel_item_gold20_style` for the
  playing row, `srlabel_item_white_style` for the rest. The minimal theme made both white, so nothing marked the
  playing row. Now (asset and page theme `styles/playqueue_dialog.bin`, `mod_lists.py` recipe `queue` and
  `edit_playqueue`): rows 44 px (button 40, a 4 px gap), the other rows muted `#9C9C9C` 18 px, the playing row
  white 20 px; the list's own row colours; a `#3A3A3A` hairline under the 64 px play-mode header (the mode
  glyph and name the app sets) and a `#3A3A3A` left border; the bottom button in the dark button colours
  (`#1E1E1E`, pressed `#333333`, 20 px). No widget is renamed or moved except the row template's height; no code.
  Not done: a play marker image on the playing row and a count in the header (the row bind and the header are
  code), icons on the bottom button (it has none).
- **The queue** (the Now Playing list page, `playerjumpinfo_page`; no longer reached from the queue button, `docs/modules/queue.md`): the playing track's row carries the
  stock red `icon_playing` disc in place of its icon (set by the row bind `0x539244`, `is_playing` `0x4d9d64`; now the wave
  marker at the right end, as in Songs, and no disc at the left on any row), the rows are the
  q2-pod rows (white title, grey artist), and the navbar title (the queue's name, a `srlabel_leftwhite22_style`
  `hscroll_label` the page builds) is 20 px like every other navbar title of ours (page theme, `mod_lists.py`
  recipe `navtitle`; the other code-built library titles stay 22 px). The track count and numbers would need
  code; not done.
