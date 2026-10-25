# Shuffle (M1 Pod, V2.1fS)

Three new rows in the M1 Pod menu, right after Cover Flow, ported from
[q2-pod](https://github.com/DiamondBond/q2-pod)'s Shuffle page (MIT; see `NOTICE`):

| row | one tap does |
|---|---|
| **Shuffle Songs** | every song of the library, stock **Shuffle** play mode, from a random song; Now Playing opens |
| **Shuffle Albums** | the albums in random order, each album's tracks in album order; Now Playing opens on the first album's first track |
| **Shuffle Folders** | the same by folder: folders in random order, each folder's files in file-name order |

The code is `patch/shuffle.c` (one function, `shuffle_play(kind)`, called from the menu row's
click in `patch/m1pod.c`). It adds **no hook**: the hook count is still one (the Home icon click
dispatcher), and nothing runs at boot, in the main loop, on paint or on a track change. A tap runs
the code once on the UI thread and returns; it leaves no timer, thread or page behind.

```
python3 -I tools/build.py --variant shuffle
# -> out/M1Plus-V2.1fS-shuffle-look-all-pod-cover-lockscreen-iconpercent-space-update.bin
venv/bin/python -I test/patch.py work/mod-shuffle-look-all-pod-cover-lockscreen-iconpercent-space
```

V2.1fS is `look-all` (V2.1fA: the device build V2.1eA with the Now Playing album fix) plus these
rows: payload stage **`F`** (the stage-D menu with the three rows, Cover Flow unchanged; on the
branch it was stage `E`, which is now Artists, and **G** carries both, `docs/full.md`). The stages
read their features off their rows (`pod_pages.stage_features`), and `tools/pod.py` compiles
`patch/shuffle.c` and defines `POD_SHUFFLE` (which `patch/m1pod.c` dispatches `ACT_SHUFFLE` under)
only for F and G, so stage D, `pod-cover` (V2.1dE) and `look-all` (V2.1fA) build byte-identical, and
stage F compiles to the same payload as the branch's stage E (19,288 bytes, 216 of `.scratch`).

Package (after the merge): SHA-256 `baa4996e925655f37c94f72fc7c09a0b7887c3fd747911b842a3f1bffbe6e75c`.
The branch built `447eed67…` on V2.1eA; `fwtool diff` between the two lists only
`ui/playing_page.bin` (the album fix under it).

## How it plays: the stock path, one queue up front

Every row takes the path the stock **Songs** page takes when you tap a song, with the Songs page's
class `0xf001`:

1. `loadLocalClassList(0xf001)` — `getAllMusic` into `*pdeq_showlist`, exactly what opening Songs
   runs (`allmusic_page_init` @`0x528a44`), in its sort order.
2. `loadSongList(queue, name, cue_start, 0xf001)` — the Songs row handler's copy of the list's
   songs into a new `stSongInfo` deque (@`0x5258a0`); it also stamps the class into every copy and
   fills the memory-playback record `g_memory_info`, as for a stock play.
3. Shuffle Albums/Folders only: the queue is reordered (below).
4. The first song's file is checked (`access`), as the row handler does before playing.
5. The play mode is set if it has to change (below).
6. `navigator_to_with_context("playing_page", {queue, index, 0xf001, 2})` — Now Playing opens and
   `playing_page_init` calls `start_player` (`0x4e4648`: `mclLoadPlayList` + `mclStartPlayer`),
   which copies the queue; the payload then destroys its own copy, as the row handler does.

### Shuffle Songs uses the stock Shuffle mode — why

`mclNextSong` in mode 2 (`0x5d5a20` -> `0x5d03b0`) draws the next index from a pool of unplayed
indices that `mclLoadPlayList` fills with the whole queue (`0x5d1fe0`); a played index leaves the
pool, and an empty pool starts again. With the whole library as the queue that **is** "shuffle all":
every song once in random order, then a new round, forever, with stock's own Previous. So Shuffle
Songs queues the library in its normal order, sets mode 2, and starts on a random song.

Building a shuffled queue ourselves and playing it in order would need List play or Repeat all
(stock Shuffle would re-shuffle it anyway), would end or repeat the same order after one round, and
after a reboot stock's resume rebuilds class `0xf001` from `getAllMusic` in the Songs order
(`memeory_startplayer` @`0x4e3714`), so the shuffle would be lost. With the stock mode, the resumed
queue is the library again and the saved mode is still Shuffle: it keeps shuffling.

The first song is drawn by the payload's own xorshift32 (q2-pod's `rand_below`, seeded once from
`toolsRandnum` and `time_now_ms`), because stock's `toolsRandnum` reseeds from `time()` on every
call. `loadSongList` finds a song by file name and CUE start, so with duplicate names (`01.flac` in
every album) it would always find the first; the payload starts on the drawn row itself when the
queue's song at that index is the same file, and falls back to `loadSongList`'s index otherwise.

### Shuffle Albums / Folders build the queue in play order — why

Albums in random order with each album in order cannot be done with stock Shuffle (it draws single
tracks). q2-pod keeps groups together at play time with hooks in the player (`mclNextSong`,
`mclLoadPlayList`, the mode setter, its queue file); here that would mean hooks on the playback
path, which runs on every track change and at boot resume. Not needed: the whole order is known up
front, so the payload builds **one queue already in play order** and lets stock play it in a
sequential mode. No hook, and next/previous, gapless, the queue view and the end of the queue all
behave as stock does for any list.

The order, from that one library query:

- **group**: albums by name, ASCII case folded — SQLite `NOCASE`, as the stock Albums list groups
  them (`getAllAlbum`: `group by album COLLATE NOCASE`); songs without an album are one group, as
  stock's "Unknown Album". So two albums with the same name are one album here too, as on the stock
  Albums page. Folders: the path up to its last `/` (a subfolder is its own folder; a multi-disc
  album in `CD1`/`CD2` folders is two folders).
- **groups in random order**: a Fisher-Yates shuffle of the group numbers (q2-pod `make_order`).
- **inside an album**: disc, then track — the stock album page's order (`getMusicByAlbum` sorts with
  the comparator @`0x4e9020`: `cd_num`, then `track`) — then path, so an untagged album keeps its
  file-name order (q2-pod `album_before`), then CUE start. Inside a folder: path, then CUE start.

Two heapsorts over an index of `{record, group, position}` (12 bytes a song; no libc `qsort`, so no
callback from libc into the payload), then the queue's own records are **permuted in place**
(cycle-following with one record of temporary storage). A record's strings stay owned by exactly one
slot, so the deque frees them as usual, and no second copy of the library is made: the memory at
the peak is what tapping a song in Songs uses (the shown list, the queue, the player's copy) plus
the index. Index and group ranks are freed before Now Playing opens.

## The play mode afterwards

The mode is the stock setting, changed exactly as the **Play settings** page changes it
(@`0x49fc78`): `mclSetPlayMode(m)`, `notifyPlayMode()` (SyncLink), `dmrSendPlayMode(m)` (DLNA),
`write_int_config(m, "PLAYSET", "PLAYMODE")` (`/mnt/data/config.ini`). Nothing is written when the
mode is already the one needed, and nothing at all when a shuffle fails. Values (Now Playing's mode
button, @`0x5398cc`): 0 List play, 1 Repeat one, 2 Shuffle, 3 Repeat all.

| before | Shuffle Songs | Shuffle Albums / Folders |
|---|---|---|
| 0 List play | -> 2 Shuffle | stays 0: the albums play through once, then stop |
| 1 Repeat one | -> 2 | -> 0 List play (Repeat one would loop the first track) |
| 2 Shuffle | stays 2 | -> 0 List play (Shuffle would scatter the albums) |
| 3 Repeat all | -> 2 | stays 3: after the last album the same album order starts again |

The mode **stays** what it was set to, like any change on Now Playing: after Shuffle Songs, a song
tapped in a stock list also plays shuffled until the mode is changed back (Now Playing's mode
button or Play settings). q2-pod restores the previous mode with a hook on the queue load ("one
shot" Shuffle Songs); that hook is on the playback path and is deliberately not ported.

After a reboot the stock resume (memory play) rebuilds the queue from the saved class `0xf001`,
i.e. the whole library in the Songs order, at the saved track (`memeory_startplayer`). For Shuffle
Songs that is the same queue and the mode is still Shuffle. For Shuffle Albums/Folders the album
order is not saved: the resumed queue continues through the library in the Songs order from that
track. Tap the row again for a new album order.

## Messages and limits

All through the stock one-line message box (`dialog/msginfo_dialog`, kind 1, 2 s — as Songs shows
"file not found", @`0x5259dc`); in each case nothing is played and the mode is not touched:

| when | message |
|---|---|
| the library is empty (or Update Local Music has not run) | Update Local Music first |
| the first song's file is missing (card out, stale library) | Storage unavailable |
| Albums/Folders with more than `SHUFFLE_MAX` (65536) songs | Too many songs to shuffle |
| Albums/Folders, the index cannot be allocated | Not enough memory to shuffle |

Shuffle Songs has no cap of its own: it is the stock Songs path, which plays any library the Songs
page can list (stock has no queue limit in `start_player`/`mclLoadPlayList`). Albums/Folders check
the size before copying anything; their extra memory is the 12-byte index (768 KB at the cap). The
time is the Songs page's own query (opening Songs on a big library takes as long) plus the sort:
`test/patch.py` counts ~12 M payload instructions for Shuffle Albums over 2,048 songs in 128
albums (heapsort is O(n log n), so a full 65,536-song library is in the order of half a billion
instructions, about a second at the X2000's clock, in the worst case where every comparison runs
to the end of the strings); a typical library is far less. The UI waits for it, as it waits for
Songs to open.

## Stock symbols (all pinned)

Functions are checked against `.dynsym` by `tools/pod.py` before anything is written; data and
record offsets are in `patch/offsets.inc` with the instruction that proves each.

| symbol | address | evidence |
|---|---|---|
| `loadLocalClassList` | `0x4ee504` | `.dynsym`; `0xf001` -> `getAllMusic` + `musicNagvationTitle(0xf001)` (@`0x4ee5bc`), then `deque_assign`s the staging deque into `*pdeq_showlist` (@`0x4ee638`) |
| `loadSongList` | `0x4e2ce0` | `.dynsym`; copies the type-8 rows of `*pdeq_showlist`, sets `+0x38` = class (@`0x4e3144`), returns the first index whose name and CUE start match (@`0x4e3190`), fills `g_memory_info` |
| `navigator_to_with_context` | `0x4d1d48` | `.dynsym`; `playing_page_init` (`0x53d1e4`) calls `start_player(ctx[0], ctx[1], ctx[2], ctx[3])` unless `ctx[2] == 0xff` |
| `mclGetPlayMode` / `mclSetPlayMode` | `0x5d3628` / `0x5d278c` | `.dynsym`; read/write the mode word `0xa0abe0`; `mclSetPlayMode` closes a gapless preload for modes 1 and 2 |
| `notifyPlayMode` | `0x50ee04` | `.dynsym`; SyncLink notification, a no-op without a client |
| `dmrSendPlayMode` | `0x4f10f0` | `.dynsym`; DLNA renderer notification, a no-op unless `dlna_service_running` |
| `write_int_config` | `0x4d6a2c` | `.dynsym`; `sprintf("%d")` + `toolsWriteConfig("/mnt/data/config.ini", section, key, value)` |
| `toolsRandnum` | `0x5e0c58` | `.dynsym`; `srand(time(0)); rand() % n` (only seeds the payload's generator) |
| `time_now_ms` | `0x70cf58` | `.dynsym` (AWTK, `uint64_t`; o32 little-endian returns the low word in `$v0`) |
| `pdeq_showlist` | `0xa045d8` | `.dynsym` (already pinned for Cover Flow) |
| `g_class_type` | `0x97cad4` | `allmusic_page_init` stores its class there (@`0x5289e8`); already pinned for Cover Flow |
| mode values 0-3 | — | Now Playing's mode button cycles `(mode + 1) % 4` (@`0x53b634`) and styles `btn_imgorder` / `btn_imgcycle1` / `btn_imgrandom` / `btn_imgcycle` (@`0x5398cc`) |
| the mode sequence | — | Play settings @`0x49fc78`, Now Playing @`0x53b648`, Play More @`0x47a54c`: `mclSetPlayMode` + `write_int_config(m, "PLAYSET", "PLAYMODE")` (+ the two notifications) |
| `REC_TRACK` `0x3c`, `REC_DISC` `0x40` | — | songtable columns 10/11 (`track`, `cd_num`) `atoi`'d into the record by the row callback (@`0x4e9304`, `0x4e9318`) |
| `REC_SIZE` `0x58` | — | `memset(local, 0, 0x58)` in `loadSongList` (@`0x4e2e4c`) and the row callback |
| msginfo context | — | `{int kind; int ms; char text[0x200]; char text2[0x200]}`, kind 1 = one white line (`dialog_msginfo_dialog_init` @`0x4786f8`, `0x478884`) |

libc is reached as before, through `demo`'s own GOT (`memset`, `memcpy`, `strcmp`, `calloc`,
`free`, `access`, the `deque_*` calls); nothing new is imported.

## What was borrowed from q2-pod

From `patch/navigation.c` (`shuffle_play`, `shuffle_songs`, `shuffle_groups`, `sp_pick`,
`shuffle_menu`) and `patch/playback.c` (`rand_below`, `shuffle`, `make_order`):

- the three actions and their names, Shuffle Songs as "stock Shuffle mode + the library from a
  random song" (`config_playmode(2, 1)` + `play_folder(all, rand_below(n), 0xf001)`), and the
  messages "Update Local Music first" / "Too many songs to shuffle";
- the xorshift32 generator seeded once from `toolsRandnum` and the tick clock, and why;
- the Fisher-Yates group ranks, the album order (disc, track, path, CUE start) and the folder
  order (path);
- the 65,536-song limit (`QUEUE_LIMIT`).

Not ported: the advanced-playback engine (`playback.c`: hooks on `mclNextSong`, `mclPrevSong`,
`mclLoadPlayList`, `mclSetPlayMode`, the gapless preload and the queue save), which keeps groups
while letting stock Shuffle run and restores the old mode after Shuffle Songs; Up Next; the hold
menu's Next/Previous Album; the music-only filter (`MUSIC_WHERE`, audiobooks/podcasts); the
multi-disc folder merge in `folder_cmp`; the separate Shuffle page (here the rows are in the main
menu, one tap each).

**Shuffle Folder from the selected folder** (a row inside the stock folder browser) is not done: it
needs a handler on a stock page (the folder browser builds its rows itself), i.e. a second hook.
Shuffle Folders works on the whole library instead.

## Tests

`test/patch.py` runs the real payload under Unicorn (shuffle checks in sections 26-36, after the
Cover Flow ones; 178/178 on the branch's V2.1fS, 182/182 after the merge, which added four
checks of the V2.1dE Cover Flow page to every stage that has it; they also run on stage G):

- the menu asset has the three rows after Cover Flow, stock-styled, without a chevron, and the
  payload's row table binds each to `ACT_SHUFFLE` and its kind;
- Shuffle Songs from its row: the exact stock sequence in order (`loadLocalClassList(0xf001)`,
  `_create_deque`, `loadSongList(.., 0xf001)`, `access`, `mclSetPlayMode(2)`, `notifyPlayMode`,
  `dmrSendPlayMode(2)`, `write_int_config(2, PLAYSET, PLAYMODE)`, `playing_page {queue, i, 0xf001,
  2}`, `deque_destroy`), the queue is the library in order with the class stamped, `g_class_type`
  set, no timer/thread/handler/page created; the start is random across seeds and across repeated
  taps, also with duplicate file names; nothing is written when already in Shuffle;
- Shuffle Albums: each album once and contiguous, NOCASE-grouped, disc/track/path order, unknown
  album as one group, from the first track; at least 6 different album orders in 24 seeds; every
  record still there exactly once after the in-place permutation; index and ranks freed; the mode
  table above (2 and 1 -> 0, 0 and 3 kept);
- Shuffle Folders: each folder once, contiguous, file-name order, subfolders separate, random order;
- empty library, missing first file, no memory, and over-the-cap libraries: the message, no Now
  Playing, the mode untouched, the queue freed (the cap is checked before anything is copied);
  65,536 songs still shuffle, and Shuffle Songs plays 65,537;
- an unknown kind does nothing; with the kill switch the entry icon is stock and no shuffle can run.

The stock `loadSongList` is modelled from its disassembly (type-8 filter, class stamp, first match
by name and CUE start). The playback itself (stock Shuffle's pool, List play stopping at the end,
Repeat all wrapping) is stock code the harness does not run; that is for the device.

## Device checklist (not yet hardware-tested)

Fall back to V2.1eA (or V2.1fA) if anything misbehaves; `m1pod-off` still disables M1 Pod.

- Tap Tidal: the menu shows **Shuffle Songs, Shuffle Albums, Shuffle Folders** after Cover Flow,
  dark rows without arrows; the list scrolls to Settings.
- **Shuffle Songs**: Now Playing opens and plays a random song; the mode icon is Shuffle. **Next**
  goes to another random song (not the next title); Previous behaves as stock Shuffle. Back returns
  to the menu. Tap Shuffle Songs again: a different first song. Play settings shows Shuffle.
- **Shuffle Albums**: Now Playing opens on track 1 of a random album and plays it in order (check a
  multi-disc album: disc 1, then disc 2); at the album's end the next album starts, from its first
  track. Tap again: a different album first. Starting from Shuffle mode, the mode icon turns to List
  play; starting from Repeat all it stays Repeat all.
- **Shuffle Folders**: a random folder, its files in name order, then another folder.
- Afterwards: change the mode on Now Playing; tapping a song in stock Songs/Albums plays with the
  mode you chose (after Shuffle Songs it is still Shuffle until you change it). The queue view
  lists the library (Songs) or the album order (Albums/Folders).
- **Reboot** while a shuffle plays (with Memory play on): Shuffle Songs resumes and keeps shuffling;
  Shuffle Albums resumes on the same track and then continues in the Songs order (expected).
- Timing: on your library, how long from the tap to the first note (Songs vs Albums/Folders).
- Empty library / card removed: the message box, nothing else changes.
- Kill switch: `m1pod-off` makes the Tidal icon open Tidal again.
