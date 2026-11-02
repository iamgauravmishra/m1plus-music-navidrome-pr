# The Queue page

**Sources:** `patch/queuepage.c` (our page), `patch/nowplaying.c` (`np_on_queue`: the queue button's handler), `tools/pod_ui.py` `build_queue_page`, `tools/pod_pages.py` `QUEUE_PAGE`,
`patch/offsets.inc` `QP_*`, tests `test/pod/queuepage.py`, preview `tools/preview_queue.py` (`uv run python -I tools/preview_queue.py work/mod-release out/preview/queue.png`, not tracked).

## What the stock app does

- **Now Playing's queue button** (`btn_queue`, the right end of the transport row) is bound by the page's widget binder (`0x53b3dc` looks the name up, the handler is `0x53b14c`): it
  stores the idle countdown of the big-cover page (`0x97ccd0` = 0x14, which every button of Now Playing does) and calls `navigator_to("dialog/playqueue_dialog")` (`0x53b178`).
  That is the **queue drawer** (`ui/dialog/playqueue_dialog.bin`, `dialog_playqueue_dialog_init` `0x47a7cc`, also named in the dialog table at `0x4d126c`), a 240 px panel that slides in
  from the right: a play-mode header (`img_playmode`, `label_playmode`, the stock mode cycle `0x47a530`), the rows, a bottom button.
- **`playerjumpinfo_page`** (the full-screen queue list, `playerjumpinfo_page_init` `0x5393bc`) is **not** reached from the queue button. Only the stock More sheet's *Look up album*
  (`0x4795cc`) opened it, and our Look up album opens our album page first (`docs/modules/playmore.md`), so it remains the fallback of that fallback. Its asset and page theme are
  untouched (`docs/modules/album-page.md` "Stock pages").
- **The queue** is the deque `*0xa0394c` (`PLAY_QUEUE`, `stSongInfo` rows `start_player` copied) and the play position `mclGetPlayPos` (`0x5d4290`): every stock reader pairs them
  (`get_playtimeandlength`, the lock screen, the drawer's init `0x47a8f0..0x47a93c`, which also scrolls the drawer to the playing row).
- **A drawer row** is bound by `0x47a19c`: the text is the file name for a CUE track (`+0x48 > 0` or `+0x4c > 0`, or `mclGetPlayType() == 1`), else the title (`+0x10`); the row of the
  play position takes `srlabel_item_gold20_style`, unless `mclGetPlayStatus() == 1` (stopped; `0x47a268..0x47a288`).
- **A row tap** (`0x479f60`): the row's index `+0x78` of the table row; when `networkGetConnectStatus()` is non-zero, or the play type is not a stream (2, 3, 0xf0, 0xf1:
  `0x47a014..0x47a028`), `start_playqueue(index)` (`0x4e47d0`: `airplay_stop`, `mclSetPlayPos`, `mclStartPlayer`, `notifyPlayStatus`), the drawer's rows are bound again (`0x479f0c`)
  and `force_refreshflag` (`0xa05a63`) is set; a stream while offline shows `msg_notnetwork` instead. Nothing else reads or changes the queue: **stock cannot remove a track from it or clear
  it** (the Delete song of the More sheet deletes the file, `delete_playqueue_file`), nor reorder it; so the page has no Clear and no reordering.
- The play mode is the one stock mode (`mclGetPlayMode` 0 List play, 1 Repeat one, 2 Shuffle, 3 Repeat all), changed as the Play settings page changes it (`pod_set_mode`, `pod_set_in_order`, `patch/shuffle.c`).

## Our page (ui/m1plus_queue.bin, window m1plus_queue_page)

`np_on_queue` is a click handler bound on `btn_queue` after the stock init (`np_start`, from the existing Now Playing init hook; no new hook): the emitter runs it before the stock handler,
`RET_STOP` keeps the drawer from opening. It answers `RET_OK` (the stock drawer opens as before) for the kill switch, an empty queue or no track at the play position, a stream play type (the drawer's
own offline test) and a window that will not open or an asset that is not ours.

The design (Apple Music's queue, kept simple; mock `out/preview/queue.png`): a list that is the whole 450 px window (the album page's structure: `list_view` > `scroll_view` > one content view that paints
the rows) under **one** glass control, the Back disc (`ah_nav_back`, top left, window child; a drag beside it scrolls the list). No Now Playing disc (the page always opens from Now Playing, Back returns to it)
and no close chevron: the Back disc is what every other page of ours uses to leave.

```
y   0   (back)                                                  glass Back (band 4..48), over the rows
   56   +------+  Chorus Complains                              cover 64 px at x 10 (8 px corners cut in the alpha, the Cover Flow cache file or the placeholder),
        | cov  |  Driftless Pony Club                           title 20 px white (y 65, 24 high), artist 16 px #AAAAAA (y 91, 20 high), x 86, 224 wide
  120   +------+
  136   [   shuffle   ]  [   repeat   ]                          two equal icon-only buttons, 145 x 40 at x 10 and 165 (10 px apart, spanning 10..310), the Songs page's flat pill look
  192   Queue                                                    20 px white at x 10, 28 high; nothing at its right
  226   [cover] Title                                            Up Next: rows 64 px as the Songs page's: 52 px cover (4 px corners) at x 10, title 21 px, artist 18 px #AAAAAA from x 74 to 298, hairline
        [cover] Artist                                           (or "No upcoming songs", 16 px #9C9C9C at x 10, where the first row would be)
```

- **Up Next** is the tracks after the play position, **in queue order** while the mode is not Shuffle. The playing track is only in the header. A row's text rules are the stock drawer's (CUE: file name; no title: file name). Covers are
  the Cover Flow cache file of the row's artist and album (`cc_album_key`), one per 16 ms tick on the page's timer, none while the list moves, nearest to the middle first (the Songs page's loader, `patch/grid.c`
  ring of `GRID_TILES`); a row with no file shows the placeholder disc. No drag handles, no marker, no count, no Clear (stock cannot clear, remove or reorder).
- **Header**: the track at the play position (title, artist, cover). No tint: the page is black.
- **Shuffle placeholder**: stock Shuffle has no order to show (`mclNextSong` draws one index at random from the unplayed pool, `toolsRandnum`, each time a track ends; the pool is filled when a queue loads, not when the mode is set; all demo code, hciplayer only gets the chosen file). So while `mclGetPlayMode` is Shuffle the page has **no Up Next**:
  below the (unchanged) "Queue" line it shows a centred placeholder: the 40 px grey (`#8C8C8C`) Lucide shuffle glyph (`sg_shuffle_big`), "Shuffle is on" (20 px white), "N songs play in random order" (16 px `#9C9C9C`, N = the queue's size; "1 song plays ..."; pl, ru, uk the label form "Utwory w losowej kolejności: N" like the other counts). The widgets are visible only while Shuffle (insensitive for good, so no tap reaches them), the content is the window's height (nothing scrolls) and there are no rows to hit. The mode is read by every `qp_load` and
  `qp_mode_changed`, called after our two buttons and by the refresh tick, so Shuffle turned on or off anywhere swaps list and placeholder without a rebuild of the header; the list returns at the top. All lines fit 300 px in the 13 languages (test).
- **Buttons**: icon only (`sg_shuffle`, `sg_repeat`, `sg_repeat1`, `tools/mod_icons.py` `SONGS_IMAGES`), equal width. Shuffle toggles `MODE_SHUFFLE` (`pod_set_in_order` when it was on); Repeat cycles off -> all -> one -> off
  (`MODE_ORDER`, `MODE_REPEAT_ALL`, `MODE_REPEAT_ONE`; from Shuffle it gives Repeat all, since stock Shuffle has no repeat). Apple's look: **on** is a light pill (`QP_PILL_ON` `#C8C8C8`, pressed `#A8A8A8`) with a near-black glyph (`sg_shuffle_on`, `sg_repeat_on`, `sg_repeat1_on`, the same
  Lucide glyphs in `#141414`); **off** is a dark pill (`#2C2C2E`, pressed `#3A3A3C`) with the white glyph. Glyph on pill is >= 4.5:1 in every state (about 14:1 white on #2C2C2E, 11:1 #141414 on #C8C8C8, 7.7:1 on #A8A8A8; tested). Repeat one shows the repeat-1 glyph. Neutral greys, no accent; no autoplay / infinity (stock has none).
- **Sync with Now Playing**: both read `mclGetPlayMode` (0 List play, 1 Repeat one, 2 Shuffle, 3 Repeat all; Now Playing's button cycles 0..3 and styles itself from it, `0x539888`, `btn_imgorder` / `cycle1` / `random` / `cycle`). Stock's click handler `0x53b5fc` does `mclSetPlayMode`,
  `write_int_config`, the picture (`0x539888`), `notifyPlayMode`, `dmrSendPlayMode`; our `pod_set_mode` does the same calls (no cached copy: it reads `mclGetPlayMode` first) except the picture, which stock sets only there and at the page's init.
  Bug found on the device: a mode set on this page left Now Playing's button showing the old mode. Fix: `np_on_foreground` (`patch/nowplaying.c`, the existing Now Playing hook's window event) calls the stock picture function `0x539888` (pinned, `stock_np_mode_button`) when the page is back in front. The mapping of the two buttons
  (Shuffle = mode 2; Repeat off / all / one = 0 / 3 / 1) is Now Playing's own cycle's modes.
- **Tap a row**: `start_playqueue(play position + 1 + row)`, `force_refreshflag` = 1; the page reads the player again (the header is the new track, Up Next the tracks after it, at the top) and stays, as the drawer does;
  Now Playing below follows. A drag, the header and the air play nothing.
- **Refresh timer** (500 ms, `QP_TICK_MS`; 1 s with the screen dark, as Now Playing's): the play position moved (the next track, a key) -> the page is read again; the mode changed elsewhere -> the buttons; the queue was replaced ->
  read again when the page is on top (`EVT_WINDOW_TO_FG` reads at once). The stock queue is checked by pointer, size and first record, like the other pages' lists (`qp_valid`).
- **Not done**: Clear, reordering and removing (stock has none), a cover tint, the playing track's `/tmp` cover when the cache has no file, Now Playing's idle countdown reset (`0x97ccd0`: the big-cover page opens only over
  `playing_page`, never over ours).

Pinned stock (`tools/pod.py` `SONGS_PINS`): the queue button's handler (`0x53b178`, `0x53b17c`), the drawer's row handler (`0x47a014..0x47a028`, `0x47a0c4..0x47a0cc`), prologues of `start_playqueue` `0x4e47d0`,
`mclGetPlayType` `0x5d3658` and `mclGetPlayPos` `0x5d4290`. Calls: `start_playqueue`, `mclGetPlayType`, `mclGetPlayPos`, `mclGetPlayMode`. Not verified on the device.
