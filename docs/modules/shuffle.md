# Shuffle

Split out of docs/architecture.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 7. Shuffle (`patch/shuffle.c`)

The Shuffle page (`ui/m1plus_shuffle.bin`, opened by the menu's one Shuffle row as in q2-pod's Library)
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
  CUE start; inside a folder path, then CUE start. Two heapsorts over a 16-byte index
  `{record, group, position, dir}` (no libc `qsort`; `dir` is a path's folder length, found once per song in
  `group_order` for Shuffle Folders and used by every folder comparison and group boundary, 2048 songs: 26.4 M -> 10.6 M
  payload instructions with 22-byte paths, 59.1 M -> 23.7 M with 52-byte paths; folder equality, file-name order and CUE-start ties are unchanged), then the queue's records are permuted in place
  (cycle-following), so every string stays owned by one slot. Peak memory is what tapping a song in
  Songs uses plus the index (1 MB at the cap; a refused allocation still toasts "Not enough memory" and leaves the queue untouched).
- **Play mode** is the stock setting changed as Play settings does (`0x49fc78`): `mclSetPlayMode(m)`,
  `notifyPlayMode()`, `dmrSendPlayMode(m)`, `write_int_config(m, "PLAYSET", "PLAYMODE")`; nothing is
  written when already right. Values 0 List play, 1 Repeat one, 2 Shuffle, 3 Repeat all. Songs -> 2;
  Albums/Folders: 1 and 2 -> 0, 0 and 3 kept (`set_in_order`, exported as `pod_set_in_order` for the Play buttons of the album page, the Songs page and the Daily Mix, so Play after a Shuffle plays in order). The mode stays afterwards (q2-pod restores it with a hook
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
