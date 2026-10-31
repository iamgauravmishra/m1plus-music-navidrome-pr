# Podcasts (local files, P0)

Code: `patch/pcmodel.c` (shows, episodes, the metadata merge, the resume ring, speeds, `pc_note`), `patch/podcasts.c` (the page), `patch/podcasts.h`. Asset: `tools/pod_ui.py`
`build_podcasts_page` (`ui/m1plus_podcasts.bin`). Tests: `test/pod/podcasts.py` (plus the Daily Mix case in `test/pod/dailymix.py`). One hook (the tag reader's call site, "Tags"); the network side (Feeds, Downloads) is a worker thread with no hook.

## What it is

Files the user copies to the card: `/mnt/mmc/Podcasts/<Show>/<episode files>` (the folder name is matched case-insensitively: `pc_root` gives the spelling the card has),
audio extensions `mp3 m4a m4b aac ogg opus flac wav wma`, an optional `cover.jpg|png|jpeg` or `folder.*` per show. The Extras item **Podcasts** (item id 20, saved
character `l`, Library group (last), hidden from the menu by default, `ACT_PODCASTS`) opens one window, `m1plus_podcasts`, with two levels switched in place (Back goes up a level first):

* **Shows**: the Albums list mode's rows (64 px, 52 px cover, name, "N episodes"), sorted by title (a leading "The " aside). The cover is decoded one a tick (16 ms) only after
  `pc_cover_ok` read the picture's header (JPEG SOF / PNG IHDR) and found at most 2.1 million pixels: the stock loader holds the whole bitmap, so a 3000 px cover is refused (placeholder disc).
  No Podcasts folder or no show: a two-line hint (`label_status`).
* **Show**: a 132 px header (96 px cover, name, episode count, the show's speed: a tap on it cycles 1x, 1.25x, 1.5x, 2x, saved) and a row per downloaded episode, newest first:
  the title (bright when unplayed, grey when played or not on the card; no dot, no dot column: the texts start at x 16, 292 px wide), a grey line `4h ago · 23 min left` / `Oct 23 · 45 min` / `Oct 23 · Played` (the date: see "The date"). A tap on the row plays it and the ones after it
  in the list's order (the queue is the whole list from its first row, so Previous goes back up the list).

Played episodes have a grey title (and a line that ends with Played), a started one a bright one; one that is not on the card has a grey title too and a line that ends with its size (`· 48 MB`, when the feed gave one: the two greys are told apart by it). There is no way to mark an episode played by hand (it was the dot). Rows are painted by the content view (no widget per row), tiles are a ring of 44.

## Files (the formats the next phase writes)

Per show folder, both optional, UTF-8, one record per line, `\n` or `\r\n`:

```
.episodes   M1PLUS-EPISODES 1
            g=<guid>\tp=<pubDate, seconds since 1970>\td=<duration s>\tl=<enclosure length bytes>\tf=<local file name>\tt=<title>\tu=<enclosure url>\tx=<description>
.show       M1PLUS-SHOW 1
            title=<name>
            feed=<feed url>
            image=<image url>
```

`.episodes`: tab separated `key=value` fields, any order, unknown keys ignored, `#` lines ignored, an entry needs one of `g f t u`, values have no tab or newline (the writer
strips them). `u` is the **enclosure url as the feed gives it** (never the redirected, signed one: it expires); `f` is the file name in the show folder (while a download runs
`f` + `.part` exists); `x` is optional. P0 keeps guid (as an FNV-1a hash), pub, dur, length, file, title and ignores `u` and `x` (they are for the downloader); a title is cut to 95 bytes,
a file name over 127 bytes is no name. At most 64 KB of the file is read and 300 episodes kept (the newest).

Without `.episodes`: title = file name without its extension, date = the file's modification time, duration unknown. With it, a file with an entry takes the entry's title, date and
duration. The one place they meet is `pm_merge` (`pcmodel.c`): entry + file = `PC_LOCAL`; entry with only `name.part` = `PC_PART`; entry with neither = `PC_REMOTE`; file with no entry = new
`PC_LOCAL`. The page shows `PC_LOCAL` only (a show with metadata and nothing downloaded says "No downloaded episodes"). Sort: date descending, then file name descending (a numbered series reads
from its last), then entry order.

State on the card (written only while the card is mounted, `pod_card_mounted`, atomically: temp file, fsync, rename; `/mnt/mmc/.m1plus/podcasts/`):

* `resume`: `"PCR1"`, slot count (word), then 16-byte slots `hash, pos, len, flags` (flags 1 = played), most recent first, at most 512 (q2-pod's ring size). The hash is FNV-1a over the
  ASCII-lower-cased full path. A bad magic, a count over 512 or a short file is an empty ring.
* `speed`: `"PCS1"`, count, 8-byte pairs `show hash (of the folder name), mode`, at most 64 (oldest out).

## Resume, played, speed

`pc_note(track)` is called from `recent_note` (so from Now Playing's tick, the mini bar's tick and, dark or lit, the page's own 1 s timer) with the playing record (`cc_playing`). Nothing else
runs by itself: **a place is saved only while one of those pages is in front** (positions lag, and an episode that ends while another page is in front is only marked played if the
last look was within its last 30 s or 95 %). For a path under `/mnt/mmc/podcasts/` (any case):

* it reads `get_playtimeandlength`; a place of 30 s or more is stored (`pm_set`); within 30 s of the start nothing is stored (a saved place stays); within 30 s of the end, or past 95 %, the
  episode is played (place cleared); heard again from the middle it is a place again. The ring is written at most every 30 s, at once when paused, at a track change, on the page's actions and when the page goes to the background.
* a saved place of 30 s or more: once the episode plays (status 2) with 1..4 s elapsed, `seek_time(place)` (the stock key-path seek) jumps there; nothing is recorded meanwhile or for 2 s after; a jump not done after 15 s is dropped. A played episode starts at 0 (the page tap calls `pc_restart`).
* speed: when an episode starts its show's mode goes into `playspeed_mode` and `mclSetPlaySpeed(mode)` (the page also does this before starting). When music plays again (and 15 s
  have passed since the page set it) the mode seen before goes back. Modes: 0 1x, 1 1.25x, 2 1.5x, 3 2x (stock "Multiple Speed", images `p_1_25`, `p_1_5`, `p_2`; `config_init` reads a stored value >= 4 as 0). Only RAM: the stock `[PLAYSET] PLAYSPEED` is not touched. The stock player may take a changed
  speed at the next track open (q2-pod sends it before opening for that reason).

## Keeping podcasts out

Daily Mix candidates (`dm_ph_lib`), the Recently Played shelf (`recent_note`) and every Shuffle of ours (`shuffle_play` all three kinds, the Songs page's Shuffle pill, the Pod's Shuffle Songs:
`pc_strip` copies the queue without episodes, only when there are some) skip paths under `/mnt/mmc/Podcasts/`. The stock lists that read `songtable` (Songs, Albums, Artists, Genres, Composers, Hi-Res, Recently Added, search, an album's songs) no longer show scanned episodes (the query filter, payload.md hook 7); Folders, Favourites, Recently Played and Most Played (own tables, lists of copies) still do (those hold the records as played or added; ours skip podcasts for Daily Mix, Recently Played and the Shuffles, which stays needed for them and for the queues). **Why every query, no scope flag** (q2-pod scopes because its Cover Flow and Folders also read `songtable`): here the DB is only read by Library lists, Cover Flow's album source (`getAllAlbum`), Memory Playback's library queue (`getAllMusic`) and the batch Add/Delete on those lists, and a podcast is never in them after the filter; episodes play as class 1 (folder) queues, the Podcasts pages list directories, the scan's duplicate check (`toolsCheckItemExist`) is its own `sqlite3_exec`, and the playlist, `myfav`, recent and often tables are not `songtable`. Queries on other tables, and anything not starting with `select ` and containing ` from songtable` followed by a space, `;` or the end, pass untouched (payload.md hook 7).

## Playing files the library may not have scanned

Stock Folders play builds nothing in the database: `toolsLoadDirectory(dir)` fills a temporary deque (`0xa03964`) of `stSongInfo`, `loadSongList(queue, name, cue, 1)` copies it
(class 1 is not in the `0xf000` class range: the generic path) and `start_player(queue, idx, 1, 2)` / `navigator_to_with_context("playing_page", {queue, idx, 1, 2})` starts it. The page does
the same with records of its own (zeroed `0x58` bytes with name, path, title, album = artist = show title, type 8, class 1, pushed with `_deque_push_back`, which copies the strings), so
playback does not depend on a library scan. `REC_ID` is 0: whether stock then records them in Recently Played / Most Played by path is a device check.

## Addresses and pins

`seek_time` `0x4e0544` (prologue, `move s0,a0`, the CUE add, `jalr mclSetSeek`), `mclSetPlaySpeed` `0x5d281c` (prologue, `move a2,a0` for the `%d` of `{mcl-playspeed\%d}`), data `playspeed_mode`
`0xa05acc`: `PODCAST_PINS` in `tools/pod.py`, checked at build. libc added: `opendir readdir closedir __xstat memmove` (`__xstat(3, path, buf)` is stock's `stat`, struct stat 144 bytes, `st_mtime` +0x40;
`struct dirent` d_name at +11). Directory tests use `opendir` success, never `d_type` or `st_mode`.

## Limits

40 shows, 300 episodes a show (newest), 400 files looked at, names under 128 bytes, `.episodes` 64 KB, 512 places, 64 speeds. Podcasts and the music library share `Podcasts`-named folders case-insensitively only
if the card's file system is case-insensitive; a card spelled `podcasts` is found by listing `/mnt/mmc`.

## Device checks (not run on a device)

1. Does Update Local Music scan `/mnt/mmc/Podcasts` (episodes in Songs, Recently Added) and skip dot files such as `.episodes`? (Dot-folders are skipped by the build: payload.md hook 6. `/mnt/mmc/Podcasts/` is not hidden, so its episodes are probably scanned into `songtable`, but every Library query leaves them out: payload.md hook 7.) Are `.m4b` files accepted by the player (stock's extension list has no `m4b`)?
2. `__xstat` layout: episode dates show the files' dates (a wrong layout shows 1970).
3. A tap on an episode starts it from a record with `REC_ID` 0: Now Playing shows title, show, cover (none), next/previous follow the list; stock Recent / Most Played do not break.
4. Resume: stop an episode at 10 min on Now Playing, play another, tap the first: it jumps to ~10 min within 2 s; reboot keeps places; the card removed: no write, no crash.
5. Speed: set 1.5x on a show, start an episode: plays at 1.5x from the start (or from the next track); music afterwards at the old speed.
6. Large cover (1400 px) decodes without a stall; a 3000 px one shows the disc.
7. Screen off with an episode playing: places still saved (Now Playing / mini bar timers at 1 s).

## Feeds (phase 1, step 1: built; the device results are in git history)

Code: `patch/pcfeed.c` (the RSS push parser and the writers; pure), `patch/pccover.c` (the cover shrink, libjpeg) and `patch/pcpng.c` (the streaming PNG decoder; tests `test/pod/pcpng.py`), `patch/pcnet.c` (guards, the worker thread, import, the status record), `patch/curlopts.h` (libcurl numbers, shared with the probe), the Feeds level of `patch/podcasts.c`.
Tests: `test/pod/pcfeed.py`, `test/pod/pcnet.py`, `test/pod/pcfeeds.py`; fixtures `test/data/feeds/*-3items.xml` (the three project feeds cut to three items; the whole feeds, optional, go in `work/feeds/{allin,headlines,wsj}.xml`
and the parser test then compares the 20 newest items of each with Python's xml.etree). No new hook, no new import.

* **Feeds level** (a third level of the Podcasts window, behind the **Feeds button** at the top right of the Shows level, Lucide `rss`, the capsule's left cap): Refresh All (an action row: the last refresh, or "Refreshing 2/5"), Import shows
  (only while `Podcasts/subscriptions.txt` exists), then a row per subscription (a `.show` with `feed=`): cover, name, and the state: `Refreshing`, the error in words (`No Wi-Fi`, `Set the date first`, `Certificates missing`,
  `Certificate problem`, `Can't connect`, `Feed not found`, `Server error`, `Not a podcast feed`) or `N new · 4h ago` / `Up to date · 4h ago` / `Never refreshed`. A tap on a subscription opens the Show level with the episodes **not on the card
  listed too, greyed** (no dot; a tap on such a row downloads it: see "Downloads"); Back returns to Feeds. **The Shows level now lists only shows with a file on the card** (a subscription with nothing downloaded is in Feeds): the open decision, recommended "no", is applied.
* **Subscribe**: `pn_import` reads `Podcasts/subscriptions.txt` (one http(s) address a line, `#` comments; over-long, spaced or duplicate lines skipped; 40 shows at most), makes `<host>-<hash8>/` with a `.show` (title = the host, `checked=0`);
  the first refresh names the show (title from the feed) and, when the folder holds nothing else (no `.episodes` yet), renames the folder after it. Importing starts a refresh of the shows never refreshed.
* **Worker** (`pn_refresh`, UI thread: the guards, then ONE detached pthread for the whole job, one show at a time): guards = card mounted, `get_wifisignal() > 0` (read on the UI thread only), clock after `PN_MIN_EPOCH` (mid 2025), the CA bundle,
  the firmware's `/etc/m1plus-cacert.pem` (as q2-pod's `/etc/scrobble-ca.pem`, but all of Mozilla's roots as curl extracts them, since a feed and its redirects can be on any host: 118 roots, 200 kB; committed as `assets/cacert.pem`,
  pinned and installed by `tools/mod_cacerts.py`; a name of its own, so stock programs that look in `/etc/ssl` are unchanged; nothing on the card is read). Per show: read `.show`, stream the feed through libcurl into the parser (verification ON, no `SSL_VERIFY*` option ever set; redirects limited to http(s); `FAILONERROR`; gzip accepted; connect 20 s, 30 s under
  1 kB/s, 120 s total; 8 MiB cap), write `.episodes` then `.show` atomically (temp file, fsync, rename), set the status. The page only **reads** the status record from its 1 s timer (`pn_gen` moved: rows rebuilt from the files), so no widget is touched
  from the thread and `pc_scan_shows` (static sort state) is never called from it.
* **Parser** (`pf_*`): a byte-at-a-time state machine (text / tag / comment / CDATA / declaration) over libcurl's chunks, any split; keeps the channel's title and picture (`itunes:image href`, else `<image><url>`) and the **20 newest items by pubDate**
  (stable; an item needs an enclosure that is not a picture or page): guid (else the url), title, pubDate (RFC 822, zones, 2-digit years), `itunes:duration` (seconds, MM:SS, HH:MM:SS), enclosure url / length / type; entities and CDATA decoded, white
  space collapsed (no tab or newline reaches a file), a 5000 byte title cut at 95 bytes on a character boundary. Atom feeds are "Not a podcast feed". Measured under Unicorn: three whole feeds (4 MB, 441-600 items) in about a second.
* **`.episodes` writer**: the kept items first (`g p d l f t u`), then the **old lines whose file (or `.part`) is on the card and that the feed no longer lists**, copied as written (an `x=` stays). An item with an old line keeps that line's `f`;
  a new one is `YYYY-MM-DD Title.ext` (forbidden ExFAT characters → `-`, at most 100 bytes, a clash gets ` (2)`; the extension from the url, else the MIME type, else mp3). `.show` gains `checked=<epoch>` (`pc_show_t.checked`);
  `PC_URL` is now 320 (a feed url longer than that is refused at import).
* **Refresh dialog** (`pg_dlg_*` in `patch/podcasts.c`; the widgets are hidden, insensitive children at the end of `ui/m1plus_podcasts.bin`, `tools/pod_ui.py podcasts_dialog`; test `test/pod/pcdialog.py`, preview `tools/preview_podcasts_dialog.py`):
  Refresh All and Import (which refreshes the shows it added and the ones never refreshed) open a modal dialog over the page, built from the Playlists menu's pieces: a full-client scrim (dimmed as that menu's; it takes every touch, so nothing under it and no
  second job can be started) and a 280 x 200 card in its glass (`pl_glass`, patch3_x, as high as that image), centred: the title **Refreshing Podcasts**, the show being fetched (ellipsis in 240 px), a 6 px bar, `2 of 5` (or **Cancelling…**) and a
  **Cancel** row filling the last 50 px (hairline above, pressed 6 % white, white text; the dialog is neutral, no accent colour). The bar is the shows done plus the running show's part, over the number of shows; the worker keeps the part (0..1000) in the status record: the feed's request is nine
  tenths of the show, advancing by bytes when the server gave a length (libcurl's `CURLOPT_XFERINFOFUNCTION`, scaled to 32 bits, no 64-bit division), else in one step; the cover's request is the last tenth. The page reads the record from a page-scoped
  **200 ms timer** (`pg_dlg_tick`) that runs only while the page is in front **and the screen is lit** (dark: it stops itself and the 1 s tick starts it again when the screen is back; the dialog is then still right, or closes at its first tick). No widget
  is touched from the thread. **When the worker has stopped** the dialog closes by itself, the Feeds rows are read again, and one line is toasted: `3 updated`, `2 updated, 1 failed`, `3 failed` (updated = refreshed, new items or not; the per-feed errors stay on
  the Feeds rows), or after Cancel `Cancelled` / `Cancelled, 2 updated`. **Cancel** (and Back, and leaving the page, i.e. the hardware Back key destroying it, which the page treats as Cancel) sets a flag the worker reads between shows and in the
  transfer-info callback: a non-zero return makes libcurl abort the transfer at once (`CURLE_ABORTED_BY_CALLBACK`; `curl_easy_setopt` is all it needs, no new import). The dialog stays, with the row dead and `Cancelling…`, until the thread has really
  ended, so a second refresh cannot start meanwhile. Files stay consistent (every write is atomic); **a show whose transfer was aborted keeps the status it had** (no "Cancelled" on its row; shows not reached keep theirs too); a show whose feed was written
  before Cancel arrived counts as updated, its picture is dropped. Another page in front: the job goes on, the dialog is there when the page comes back. Strings: 8 new keys in all 13 languages (`tools/pod_i18n.py`); the widest title (German) is 231 of 240 px.
* **Cover art** (`patch/pccover.c`, `pv_shrink`; called by `pn_cover` in `patch/pcnet.c`): after a show's `.episodes` and `.show` are written (and the folder renamed), when the folder has **no** cover file (none of the six names the page
  knows; a user's picture always wins, nothing is downloaded) and the picture url (the feed's `image`, else the one already in `.show`) is http(s), the worker downloads it with the feed's own libcurl setup (`pn_easy`: CA bundle, redirects limited
  to http(s), FAILONERROR, the same time-outs; 6 MiB cap, `PN_COVER_CAP`) into `.cover.src`, then `pv_shrink` writes `.cover.tmp` and it is renamed to `cover.jpg` (a half file is never visible; the page picks it up through its 1 s `pn_gen` rebuild:
  the generation moves when the cover lands). **Size**: stock's loader holds the whole bitmap (3000 x 3000 = 36 MB RGBA, the page refuses above 2.1 million pixels) and stock's shrinker `toolsGetExternCover` refuses a JPEG above 1 million pixels, so it is
  not used. `pv_shrink` uses demo's own libjpeg 7 (already imported; the structures by offset, pinned in `tools/pod.py JPEG_PINS` against stock's decoder and encoder): decode at libjpeg's DCT scale 1/8, 1/4, 1/2 or 1/1 (the largest keeping the longer
  side at 192 px or more: 3000 px -> 1/8 = 375 px), one row at a time, an area average to **192 x 192 at most** (aspect kept, never upscaled; `PV_SIZE` = twice the largest cover any Podcasts page draws, the Show header's 96 px, so the grid's area
  average has pixels to average) and a baseline JPEG at quality 85 (about 10 to 20 kB). Memory: libjpeg's row buffers and about 3 kB of sums, whatever the picture's size (the old full decode would be 27 MB or more); time: Huffman decoding only, at 1/8 scale.
  Refused without libjpeg: not JPEG or PNG, a baseline JPEG above 16 million pixels, a progressive one above 2.1 million (libjpeg keeps all its coefficients); CMYK is refused after the header.
  **PNG** (`patch/pcpng.c`, `pv_shrink_png`; All-In's cover is a 2000 x 2000 RGBA PNG): demo imports only `png_read_image` (the whole image) and has no `png_read_row` and no zlib, so the decoder is our own, streaming: it walks the chunks
  (IHDR, PLTE, tRNS, any number of IDAT, CRCs not checked), inflates the IDAT stream (stored, fixed and dynamic blocks; a 32 kB window; input pulled from the file 4 kB at a time, output pushed byte by byte; written afresh in the shape of Mark Adler's
  `puff.c`, zlib licence, credited in the file's header), unfilters one scanline at a time (None, Sub, Up, Average, Paeth; only the previous row is kept) and converts it to RGB (grey, grey + alpha, RGB, RGBA, palette; 1, 2, 4, 8 and 16 bit; palette and colour-key tRNS;
  **transparency is composited over white**: a JPEG has no alpha, white is how Apple's own apps show transparent art, and black-on-clear logos stay readable (white-on-clear art would vanish: a rarer case)) before the same area average and encoder. Limits: 8192 px a side and 25 million pixels
  (about 5000 x 5000; Apple's art is 1400 to 3000). **Memory**: one calloc of about 40 kB (window, input buffer, two Huffman tables) plus two scanlines of at most 64 kB (an 8192 px RGBA 16-bit row) and one RGB row of at most 24 kB: under 200 kB
  whatever the picture's size, none of it on the thread's stack (the Huffman table of a dynamic block, 0.6 kB, and the 4 kB output sums apart). **Untrusted data**: every chunk length is checked against the file, every Huffman symbol, length and distance
  against its table and the bytes output so far, every filter byte and palette index, the output against the header's size (a zlib bomb stops at the size the header claims), a truncated or short or long stream fails; any failure leaves no file and
  no status. An **interlaced** (Adam7) PNG cannot be done in one pass over its rows: a large one is refused, one the page can decode as it is (at most 2.1 million pixels) is renamed to `cover.png`. Errors: libjpeg's `error_exit` is stock's own (`0x5dbfe0`: `longjmp` to our `_setjmp`), never its default (`exit`); every file and object is released, `.cover.*` removed. **A cover
  failure changes nothing else**: the feed's status (OK, N new) is its own, nothing is logged, and the next refresh tries again (no marker file: a picture that always fails is downloaded again on every refresh, at most 6 MiB). An existing `cover.jpg` is
  never replaced, so a changed picture upstream is not followed (delete the file to fetch again).
* **Not done in step 1**: unsubscribe / long-press, refreshing one feed,
  Add Show / iTunes search (step 3). (Downloads, step 2, are below.) **Stock standby stops the Wi-Fi and the CPU** after the idle time when nothing plays (`docs/modules/probe.md`): a refresh started and left will stall; the time-outs end it and the next one starts again.
* **Device checks (not run)**: the refresh dialog: Refresh All opens it at once (title, the first show's name, `1 of 3`, the bar creeping on the big feeds); it closes by itself with `3 updated` (or the failed count); Cancel mid-feed stops within a second or two
  (`Cancelling…`, then `Cancelled`) and a second Refresh All then works; Back (navbar not reachable under the scrim: the hardware key) cancels; turn the screen off during a refresh and on again: the dialog is right (or gone with its line); Import with a
  subscriptions.txt shows it too; covers (including All-In's 2000 px PNG, which needs about a second of CPU): after Refresh All the three shows get their pictures on Feeds, Shows (after a download) and the Show header within a refresh or two (one 3000 px, one 1400 px); `cover.jpg` is about 10 to 20 kB, 192 px; no `.cover.*` file left on the card; a feed with no picture or a dead picture url keeps the disc and still says "N new"; a `cover.jpg` you put in a show folder is never replaced; the app stays up (a bad picture is a libjpeg error caught by the longjmp, not an exit) and the stock Update Local Music is unaffected by the hidden files; Refresh All on the real feeds (time, RAM, the page's rows rebuilding while lit); the folder rename of an imported show; the Feeds button and the capsule on the glass navbar; a refresh with the screen turned off midway;
  Import with a real `subscriptions.txt` (CRLF, trailing spaces); the stock Update Local Music's view of the `.show` / `.episodes` files and of the renamed folders.

## Downloads (phase 1, step 2: built, not yet run on a device)

Code: `patch/pcnet.c` (`pn_dl_*`, `pn_dmain`, `pn_dl_run`, `pn_dl_attempt`; the queue in the status record), `patch/pcfeed.c` (`pf_find_episode`: the `u` / `l` of an episode's `.episodes` line), `patch/podcasts.c` (the Show level's taps and state lines, the Feeds
level's Downloads row, `pg_awake_tick`), `patch/curlopts.h`. Tests: `test/pod/pcdl.py` (sections `queue_tests transfer_tests resume_tests failure_tests control_tests refresh_tests page_tests refresh_page_tests awake_tests width_tests`; the scripted libcurl of
`test/pod/harness.py` now serves a `Content-Type`, partial bodies that end in an error, and `on_sleep`). **Credit**: the policy follows q2-podcasts (MIT, github.com/m-d-e-v/q2-podcasts: `internal/library/download.go` and `contrib/shanlingq2/README`); the code is our own, over demo's libcurl.

* **What the user does**: Feeds > a show > **a tap on an episode that is not on the card queues its download; a tap on a queued or running one cancels it** (its `.part` stays, so a later tap resumes it). The row's grey line (it replaces the date line while it applies; the title keeps
  the grey style: no accent colour, no dot): `Waiting` (queued, or waiting to retry), `Downloading 42%` (the length is known: the server's, else `l=`; `Downloading 12 MB` when it is not), `Paused` (an incomplete `<f>.part` and nothing queued: after a Cancel, a reboot, a standby), `Failed: <reason>` (a tap
  retries), and when the file is complete the row is an ordinary local episode (date line, bright title, plays like any: the page reads the show again when the worker's generation moves). Toasts: the guards' words on a tap that cannot queue (`No Wi-Fi`, `Set the date first`, `Certificates missing`, `Queue is full`).
  Reasons (the Feeds words plus): `Not found` (HTTP 404 / 410, or no enclosure address in `.episodes`), `Not audio` (the answer is a web page), `Card is full`, `Server error`, `Can't connect`, `Certificate problem`, `Storage unavailable`. Strings: `Downloading Waiting Paused Failed Not found Not audio Card is full Queue is full Downloads`
  (9 keys, 13 languages, `tools/pod_i18n.py`; `test/pod/pcdl.py width_tests` measures every line in the real font: the widest is Spanish at 269 of 274 px).
* **Feeds level**: while anything is queued or running a row **Downloads (3)** follows Refresh All, in the plain title style, with the one running as its grey line (`Downloading 42%`, else `Waiting`). A tap on it opens the **Downloads level** (below). It appears and goes with the queue.
* **The `.part` file and the files**: `<show folder>/<f>.part`, `f` from `.episodes` (at most 100 bytes: `PF_MAX_FILE`); a path (root, folder, `f`, `.part`) over `PN_DL_PATH_MAX` = 240 bytes is refused (`Storage unavailable`). The data is gathered in a **512 KB buffer** and each chunk is written with `open(O_WRONLY|O_CREAT|O_APPEND)`, `write`, `fsync`, `close`, so the card is
  almost never held busy and a break loses at most what was in the buffer (the bytes got when a transfer ends, in whatever way, are flushed first). At the end the file is `rename`d to `<f>` (the last chunk is fsynced before). **No mtime** is set: demo imports neither `utime` nor `utimes` (the model takes an episode's date from `p=`, not from the file). An empty `.part` (nothing on the card) is removed after a failure or a Cancel; one with bytes stays. A leftover `.part` of an episode whose file is there is removed.
* **Worker**: one detached pthread at a time (`pn.kind` = refresh or download), **never a refresh and downloads together**. `pn_dl_add` (UI thread: the guards of `pn_guard`, the path limit, the queue of `PN_QMAX` = 32, then `pn_dl_start`) fills a slot and starts the thread when none runs; the thread takes the slot that was asked first, one episode at a time, until none is left, then ends. The queue
  is memory only: after a reboot `.part` files show as Paused and a tap resumes them. The page writes a slot and then its state; the thread moves a state by compare-and-swap, the page cancels a waiting slot by compare-and-swap, so neither needs a lock. A start the thread's end raced (an episode queued while the thread was ending) is
  caught by the page's 1 s downloads timer (it calls `pn_dl_start` when slots wait and no thread runs). **`pn_dl_start` runs the guards again**: if they fail then (Wi-Fi gone after a standby, say) every waiting download fails at once with their words, so a dead queue does not keep the device awake.
* **The request** (`pn_easy`, as the feed's): the stored enclosure url `u` (never a final signed redirect), `PN_CA`, redirects (8) limited to http(s), `FAILONERROR`, verification on (no `SSL_VERIFY*` option ever set), no signals, connect 20 s; changed for a download: **low speed 1 byte/s for `PN_DL_STALL` = 60 s** (the stall), **no total time limit**, `Accept-Encoding: identity` (a range of an encoded body would not resume).
  libcurl numbers used (`patch/curlopts.h`, checked against libcurl's `curl/curl.h`, the numbers have not changed since before 7.73): `CURLOPT_RANGE` 10007 (`CURLOPTTYPE_STRINGPOINT + 7`, a `"N-"` string; `CURLOPT_RESUME_FROM_LARGE` 30142 is not used: with a Range option a server that answers 200 is handed over as it is, which is the rule below, whereas
  RESUME_FROM would turn it into an error), `CURLOPT_LOW_SPEED_LIMIT` 19, `CURLOPT_LOW_SPEED_TIME` 20, `CURLOPT_TIMEOUT` 13, `CURLOPT_ACCEPT_ENCODING` 10102, `CURLINFO_RESPONSE_CODE` 0x200002, `CURLINFO_CONTENT_TYPE` 0x100012 (`CURLINFO_STRING + 18`, read in the write callback at the first byte), `CURLE_PARTIAL_FILE` 18, `CURLE_RANGE_ERROR` 33.
* **Resume**: when the `.part` has bytes the request is `Range: N-` (N = its size, `lseek(fd, 0, SEEK_END)`). **A 206 is appended; a 200 starts the file again** (the `.part` is truncated at the first byte; checked in the write callback with `CURLINFO_RESPONSE_CODE`). A 416 or curl's range error (33): the `.part` is dropped and the file starts again, once (a second one fails with `Server error`).
  The `Content-Range` start is not read: a 206 is trusted.
* **Failures**: a **network failure** (any curl error that is not one of the next lines, a stall = `CURLE_OPERATION_TIMEDOUT`, a short body `CURLE_PARTIAL_FILE`) and an HTTP 5xx, 408 or 429 are **retried after 10, 20 and 40 s** (`PN_DL_RETRIES` = 3; the wait is one-second `sleep`s so Cancel and a pause are heard at once; the row says `Waiting`; the count starts again
  after an attempt that got bytes, so a long file over a flaky link is not given up); then `Can't connect` / `Server error`. These **fail at once**: HTTP 404 / 410 (`Not found`), another 4xx (`Server error`), a certificate error (`Certificate problem`; a bad CA file `Certificates missing`), **`Content-Type: text/...`** in any case (`Not audio`: a Wi-Fi sign-in page; an existing `.part` is untouched),
  **a full card**, an empty 200, a `.part` that cannot be opened or written or fsynced, a failed rename (`Storage unavailable`, the finished `.part` stays). **The card keeps 32 MB free** (`PN_DL_MARGIN_KB`): `statfs` before the request (the rest of the file, `l` minus the `.part`, plus 32 MB must fit; an unknown `l` is skipped) and before every chunk (the chunk plus 32 MB); a refusal in the middle keeps the chunks already
  written as the `.part`. A body over 2 GiB (`PN_DL_MAX_BYTES`) is refused. An `l=` that is not a number or does not fit 31 bits is unknown. libcurl decides what is complete (`rc == 0`; it checks `Content-Length`), the length in `.episodes` only sizes the check and the percent (a total smaller than the bytes got was wrong: shown as MB).
* **Refresh versus downloads (the choice): downloads pause for a refresh, then go on.** A tap on Refresh All (or Import) while a download thread runs: the page sets a pause flag (`pn_dl_pause`; the transfer is aborted at once through the transfer-info callback, what was received is flushed, the entry goes back to waiting, the queue is kept), keeps the request
  (`pg.rpend`, the Refresh All row says `Waiting`), and **the page's tick starts the refresh and opens its dialog when the thread has stopped**; when the dialog closes `pn_dl_start` puts the queue back on a thread and every episode resumes from its `.part`. A refresh that is running when a download is tapped: the download is queued and starts after it (the dialog is modal anyway). If the page is not in front, not on the
  Feeds level or the screen is off when the downloads have paused, the refresh is dropped (no dialog is opened in the dark) and the downloads go on. A refresh keeps the `.episodes` line of an episode that has a file or a `.part` (even when the feed no longer lists it); a queued episode with neither can lose its line to a refresh and then fails with `Not found`.
* **Keeping the device awake**: stock standby stops the Wi-Fi and the CPU when nothing plays (`probe.md`). `patch/podcasts.c` `pg_awake_tick` is a **page-scoped 1 s timer** (armed after a queue, when the page opens with a queue, and after a refresh; it ends when nothing is queued; removed in the window's destroy) that, **on the UI thread and only while a download thread runs**, calls stock
  **`reset_poweroptions_timer(1, 1, 0)`** (`0x4d7874`, pinned: `addresses.md`): its three arguments each guard one countdown, `a0` the standby time (`setstandby_time`), `a1` the auto power-off (`setsavepower_time`), `a2` the screen's light (`setlight_time`); `(1, 1, 0)` sets the first two again and leaves the screen's timer alone, so the screen still turns off and
  the device does not stand by or power off while a download runs. It does no widget work, so it ignores `pod_screen_lit` (it runs dark too); the visual updates (rows, Downloads row) are in `pg_tick`, which keeps the screen-off rule. **The limit**: AGENTS.md allows page-scoped timers only, so the device is kept awake while the Podcasts window **exists** (in front or behind another page). When the window is
  destroyed (the hardware Back key) the download goes on while the device is awake, the timer is gone, and after a standby the stalled transfer ends in a time-out and fails or retries; a **tap on the row (or opening the page, which arms the timer for a queue still there) resumes from the `.part`**. A refresh's dialog does not keep the device awake (its own matter, as before).
* **The Downloads level** (a fourth level of the Podcasts window: `L_DLS`, behind the Feeds level's Downloads row; Back returns to Feeds). Code: `pg_load_downloads`, `pg_dls_build`, `pg_dls_tap` in `patch/podcasts.c`; `pn_dl_listed` / `pn_dl_clear` in `patch/pcnet.c`. Preview: `tools/preview_podcasts_downloads.py` (`out/peek/podcasts-downloads.png`). Tests: `test/pod/pcsel.py downloads_tests`.
  **One row per download** (at most 40, the tile ring): first what the worker holds, in the order it was asked (running, waiting), then the **failed** ones (the worker's failure table now keeps the show folder and the file name, 16 of them), then the **paused** ones the card has and the worker does not: a `.part` of an episode that its show's
  `.episodes` lists (after a reboot these are the user's unfinished downloads; the scan reads the shows with a feed, and the ones the worker names, one `pc_load_show` each, only when the level is made or the worker's generation moves, never for a step of progress). A row is the show's cover (the Albums list row's cover machinery: `pg.rows[a]` holds the show for `pg_next_cover`), the episode's title and the state line the Show level
  uses (`Downloading 42%`, `Waiting`, `Paused`, `Failed: <reason>`). **A tap does what it does on the Show level**: a running or waiting one is cancelled (a running one keeps its `.part` and shows as Paused; a waiting one leaves the list), a paused one is queued (resumes), a failed one is tried again. A finished download leaves the list (it is a file); with nothing pending the level says **No downloads**. Live: while the screen is lit the page's 1 s tick makes the rows again
  when `pn_gen` moved and the lines again when `pn_dl_gen` moved (the covers stay); dark: nothing.
* **Select mode** (the Show and Downloads levels), **in the Playlists page's Delete-select manner** (`docs/modules/playlists.md` "Select mode", the Songs page's marks, bar and Select All; `pod_make_mark` / `SG_*` as there): a **Select** button (Lucide `list-checks`, `pod_nav_selectl`, the capsule's left cap on the 214 slot, the place the Feeds button has on the Shows level; Now Playing becomes the right cap) shows on a level
  that has a row that can be marked, and hides while there is none. A tap enters the mode: Back becomes the glass x, the title reads `N Selected`, **Select All** (all that can be marked, or none when all are) is at the right, the Select button and Now Playing go (hidden and insensitive), a 26 px mark (cut to its circle) opens a 30 px column left of every row that can be marked, the texts slide right by it (from x 16 to 46 on the Show level, as the Playlists page's rows slide; no column outside select mode), and a 64 px bar with one **Delete**
  pill (the Playlists page's) shows (the content is 64 px longer). A tap on a row marks and unmarks it (a drag marks nothing; no pressed fill; a tap on a row that cannot be marked does nothing, in particular it downloads nothing). Back (the x) leaves the mode first. **Who can be marked**: on the Show level the episodes on the card and a `.part` that no download holds (a paused download; a remote row, a waiting or running one cannot); on the Downloads
  level every row but the running one. While rows are marked the page does not read the list again when a download changes (the marks are of those rows); a visit to Now Playing keeps the marks.
  **Delete** (the pill; nothing marked: nothing) asks with `pod_confirm` (the stock confirm dialog, the one Rebuild covers and Screenshot use; No: nothing is deleted and the mode stays): `Delete the selected episodes?` / `Remove the selected downloads?`. Yes, **Show level**: each marked episode's file and its `.part` are `unlink`ed; **the `.episodes` line stays**, so the episode is a remote one again (greyed, a tap downloads it); its **resume place and
  played mark are forgotten** (`pc_mark(hash, 0)`: downloaded again it starts fresh); a marked `.part` alone (a paused download) is removed with its failure record. **The episode the player is on is never deleted** (`cc_playing`'s path compared case-insensitively): it is skipped and the toast `The playing episode was kept` says so (episodes later in the play queue may be deleted; the player then skips what it cannot open). **Downloads level**: a waiting one leaves the
  queue, a paused or failed one loses its `.part` and its failure record (the finished file, if any, is not touched; the episode is a remote one again). Then the mode ends and the page reads the list again. A show left with no file drops off the Shows level at the next Back (it stays in Feeds). Tests: `test/pod/pcsel.py select_tests`.
* **Strings added for this** (4, 13 languages; `Delete`, `Select All` and `N Selected` are the Songs page's keys): `No downloads`, `Delete the selected episodes?`, `Remove the selected downloads?`, `The playing episode was kept` (`pcsel.py width_tests`: `300 Selected` fits the title room, `The playing episode was kept` fits 300 px in every language).
* **Strings added for the rows** (1 key, 13 languages): `%d MB` (the size ending a remote episode's grey line; no space in the CJK languages); the grey line is up to 292 px wide now (`podcasts.py width_tests`).
* **Device checks for the rows (not run)**: no blue dot and no empty left column on the Show level, the titles at the header's text margin; an unplayed episode bright, a played one grey, one not on the card grey with its size at the end of the line; select mode slides the rows right and back.
* **Device checks for this (not run)**: Feeds > Downloads (n) opens the level; rows with the right covers and lines while an episode downloads (the percent moves while lit, the screen off and on again shows the current one); a tap pauses and resumes; a reboot with an unfinished download: its row is Paused in the level, a tap resumes it; a failed one (Wi-Fi off) is listed with its reason and a tap retries; Select on the level, mark a paused and a failed one, Delete: the `.part` files are gone from the card (`ls`) and the rows with them; on a show: Select, mark two local episodes, Delete > Yes: the files are gone and the rows are grey again, a tap on one downloads it again from the start; mark the episode that is playing: it stays and the toast shows;
  delete every episode of a show: Back, the Shows level no longer lists it, Feeds does; Select All twice; No in the confirm keeps the marks; the x and the hardware Back leave the mode; the capsule (Select | Now Playing) on the glass navbar and the mark circles on the black rows.
* **Not done**: auto-download of new episodes, a retry queue that survives a reboot, `Content-Range` checking, a download progress on the Shows level, unsubscribe, refreshing one feed, Add Show / iTunes search (step 3).
* **Device checks (not run)**: a 20 to 100 MB episode of each of the three project feeds (All-In, The Headlines, WSJ) downloads with the screen turned off by itself (standby does not stop it: the screen goes dark, the file completes; Wi-Fi stays up); its `.part` grows in 512 KB steps; the finished file plays like any local episode and takes its date and title from `.episodes`;
  Cancel in the middle then a tap resumes with a Range request (the file ends whole: compare its size and `md5sum` with `curl`'s); a CDN that signs its redirects (the stored `u` is requested every time); the card's file system: a `.part` over 4 GB is not expected; a server that ignores Range (200) restarts; switch the Wi-Fi off mid-download: `Waiting` for 10 / 20 / 40 s, then `Failed: Can't connect`, the `.part` kept, a tap resumes; fill the card to under 32 MB: `Card is full`, the `.part` kept;
  Refresh All with a download running: the download pauses, the dialog opens, the download goes on after; leave the page (Now Playing) and come back: the rows are right; the hardware Back key out of the page: the download continues and finishes while awake; two episodes queued: they run in order; the battery over an hour of downloading; a captive-portal sign-in page: `Not audio`; whether `reset_poweroptions_timer(1, 1, 0)` also keeps the Wi-Fi up (the screen goes off, the device stays on).

## Next: unsubscribe, covers, search (design only)

Step 0, the device probe (HTTPS and the CA bundle, Wi-Fi, clock, RAM, screen-off soak), is built: `docs/modules/probe.md` (Customize > Developer > Network Probe). Its findings replace the open checks below.

* **Subscriptions**: a feed url per show in `.show` (`feed=`): created by `subscriptions.txt` (built). Next: a Subscribe action with the url typed, unsubscribe.
* **Open device checks for it**: does Update Local Music scan the folder / skip dot folders; is the clock set after boot without Wi-Fi; `get_wifisignal` return values; libcurl's CA path and available TLS version; free RAM during a 4 MB feed parse.
* The Pod (`patch/ipod.c`) has no Podcasts entry yet: its levels are built over stock list queries, so a shows / episodes level is a new list kind (not cheap); follow-up.

## The date (Apple Podcasts style)

`pc_when(pub, now, out, size)` (`pcmodel.c`): under 60 s "Just now"; under 1 h "Nm ago"; under 24 h "Nh ago"; under 7 days "Nd ago"; else "Oct 23" (this year) or "Oct 23, 2025". `now` is `time()`;
the calendar is `localtime` (the one the status bar and the Daily Mix use). The absolute form is used when the clock was never set (its year is before 2024) or the date is more than a minute ahead of it
(up to a minute ahead is "Just now"). The texts are keys of `tools/pod_i18n.py` (13 languages): `Just now`, `%dm ago`, `%dh ago`, `%dd ago`, twelve month texts that carry the day (`Oct %d`, in German `%d. Okt.`, in
Japanese `10月%d日`: the order is the language's) and `, %d` for the year (`DATE_KEYS` tells the tables test these keys have one `%d` though they do not start with it). The lines are made when a tile is first painted, so on
opening a show and whenever the page comes back to the front (`pg_on_fg` drops the tiles): no timer. The longest line (a date with a year, "135 min left") is measured in every language in `test/pod/podcasts.py`
`width_tests` and fits the 274 px row text (Ukrainian "min left" is "Ще %d хв" for that); a longer one would end in an ellipsis.

## Tags (Now Playing, the mini bar and the lock screen show the episode)

Stock `get_id3info` (`0x4dfd58`, run by `start_player` and at each track change) fills `playsong_id3info` (`0xa0d88c`: album +0x404, artist +0x504, title +0x684) from the **file's tags** with `toolsGetMusicInfo`
(`0x5ec6a8`, taglib), skipping the tag read only when the path and CUE start match the cached struct; the record's own strings are used only when `mclGetCueFlag` is set (record CUE start or end > 0: not usable, the
player would seek in the file). It then copies the parsed path into the struct (`jalr strcpy` at `0x4dff4c`: the cache key), and builds `song_name` / `song_artist` from the struct: an empty title becomes the file name, an empty
artist "Unknown" (`0x7466e8`). Tag-less episodes therefore showed "Unknown" and the raw tag title. (A timer route that wrote the globals and the labels from `pc_note` was tried and removed: it lagged a tick and left the lock screen alone.)

**The hook** (hook 5 of `docs/modules/payload.md`, after q2-pod's `ID3_PATH` / `ringnav_id3_path`, `README.md`): the `jalr` at `0x4dff4c` becomes `jal pc_id3_path`; the delay slot still loads `a1` = the record's path, `a0` is the struct, `s0` the record.
`pc_id3_path(info, path)` copies the path (bounded at 0x3ff: the CUE start follows) and returns `info`, exactly stock's `strcpy`; then, **only for a path under `/mnt/mmc/Podcasts/`** (any case) **and without the kill switch**
(`/mnt/mmc/m1plus-off`, `/mnt/data/m1plus-off`): if the playing record (`cc_playing`, the same queue row get_id3info read; its path must match) has a title and an artist that is not empty or "Unknown", title / artist / album come from it
(a record queued by the Podcasts page: the episode title from `.episodes`, else the file name; the show title from `.show`, else the folder as artist and album); otherwise the tags stay as stock found them except an empty or "Unknown"
artist, which becomes the show folder, and an empty album, which becomes the artist. Stock's code after the site copies them into `song_name` / `song_artist`, so Now Playing, the mini bar's source (the record) and the lock screen agree.
No file I/O but the kill-switch check, no allocation; a plain path costs the copy and a prefix test (under 1000 instructions in the test).

**Boot path.** Memory Playback can start a track at boot (`start_player` -> `get_id3info`): `tools/reach.py` reports the site reachable from `platform_init` (over-approximate chain `deqVipPackage_init` -> `get_hifi_lyric_address` -> `sub_500cc0` ->
`get_id3info`). The hook is therefore minimal and falls back to stock for every non-podcast path; a podcast at boot does the kill-switch `access` calls, `mclGetPlayPos` and `deque_at`. The boot guard's crash marker is not consulted (as for the other
page hooks); the SD kill switch is.

Pins (`PODCAST_PINS`): the prologue, the words around the site (`lw t9` strcpy, `lw a0` struct, `sw v0,0x400(s1)`, the `jalr`, the delay slot, `lw t9` memset after it), the `toolsGetMusicInfo` call and the two empty-field tests; data `playsong_id3info`, `song_name`,
`song_artist`. A mismatch refuses the build. Tests: `test/pod/podcasts.py` `tag_tests` runs stock's `get_id3info` for real under Unicorn (callees mocked, `toolsGetMusicInfo` returns the tags a test sets) with the stock word at the site (shows "Unknown") and with the payload;
music, tags that are complete, the cache, both kill switches, a long path and a record with another path; `test/demo_diff.py` allows exactly that one word. Not covered: the Pod's Now Playing level (its own text from the record) and stock list rows.
