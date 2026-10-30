# Podcasts (local files, P0)

Code: `patch/pcmodel.c` (shows, episodes, the metadata merge, the resume ring, speeds, `pc_note`), `patch/podcasts.c` (the page), `patch/podcasts.h`. Asset: `tools/pod_ui.py`
`build_podcasts_page` (`ui/m1plus_podcasts.bin`). Tests: `test/pod/podcasts.py` (plus the Daily Mix case in `test/pod/dailymix.py`). One hook (the tag reader's call site, "Tags"), no new thread.

## What it is

Files the user copies to the card: `/mnt/mmc/Podcasts/<Show>/<episode files>` (the folder name is matched case-insensitively: `pc_root` gives the spelling the card has),
audio extensions `mp3 m4a m4b aac ogg opus flac wav wma`, an optional `cover.jpg|png|jpeg` or `folder.*` per show. The Extras item **Podcasts** (item id 20, saved
character `l`, Library group (last), hidden from the menu by default, `ACT_PODCASTS`) opens one window, `m1plus_podcasts`, with two levels switched in place (Back goes up a level first):

* **Shows**: the Albums list mode's rows (64 px, 52 px cover, name, "N episodes"), sorted by title (a leading "The " aside). The cover is decoded one a tick (16 ms) only after
  `pc_cover_ok` read the picture's header (JPEG SOF / PNG IHDR) and found at most 2.1 million pixels: the stock loader holds the whole bitmap, so a 3000 px cover is refused (placeholder disc).
  No Podcasts folder or no show: a two-line hint (`label_status`).
* **Show**: a 132 px header (96 px cover, name, episode count, the show's speed: a tap on it cycles 1x, 1.25x, 1.5x, 2x, saved) and a row per downloaded episode, newest first:
  the blue unplayed dot, the title, a grey line `4h ago · 23 min left` / `Oct 23 · 45 min` / `Oct 23 · Played` (the date: see "The date"). A tap on the dot toggles played; a tap on the row plays it and the ones after it
  in the list's order (the queue is the whole list from its first row, so Previous goes back up the list).

Played episodes have a grey title and no dot; a started one keeps its dot. Rows are painted by the content view (no widget per row), tiles are a ring of 44.

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

## Feeds (phase 1, step 1: built, not yet run on a device)

Code: `patch/pcfeed.c` (the RSS push parser and the writers; pure), `patch/pccover.c` (the cover shrink, libjpeg) and `patch/pcpng.c` (the streaming PNG decoder; tests `test/pod/pcpng.py`), `patch/pcnet.c` (guards, the worker thread, import, the status record), `patch/curlopts.h` (libcurl numbers, shared with the probe), the Feeds level of `patch/podcasts.c`.
Tests: `test/pod/pcfeed.py`, `test/pod/pcnet.py`, `test/pod/pcfeeds.py`; fixtures `test/data/feeds/*-3items.xml` (the three project feeds cut to three items; the whole feeds, optional, go in `work/feeds/{allin,headlines,wsj}.xml`
and the parser test then compares the 20 newest items of each with Python's xml.etree). No new hook, no new import.

* **Feeds level** (a third level of the Podcasts window, behind the **Feeds button** at the top right of the Shows level, Lucide `rss`, the capsule's left cap): Refresh All (an action row: the last refresh, or "Refreshing 2/5"), Import shows
  (only while `Podcasts/subscriptions.txt` exists), then a row per subscription (a `.show` with `feed=`): cover, name, and the state: `Refreshing`, the error in words (`No Wi-Fi`, `Set the date first`, `Certificates missing`,
  `Certificate problem`, `Can't connect`, `Feed not found`, `Server error`, `Not a podcast feed`) or `N new · 4h ago` / `Up to date · 4h ago` / `Never refreshed`. A tap on a subscription opens the Show level with the episodes **not on the card
  listed too, greyed and silent** (no dot; a tap anywhere on such a row neither plays, toasts nor marks it; the download is step 2); Back returns to Feeds. **The Shows level now lists only shows with a file on the card** (a subscription with nothing downloaded is in Feeds): the open decision, recommended "no", is applied.
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
  Add Show / iTunes search (step 3), downloads (step 2). **Stock standby stops the Wi-Fi and the CPU** after the idle time when nothing plays (`docs/modules/probe.md`): a refresh started and left will stall; the time-outs end it and the next one starts again.
* **Device checks (not run)**: the refresh dialog: Refresh All opens it at once (title, the first show's name, `1 of 3`, the bar creeping on the big feeds); it closes by itself with `3 updated` (or the failed count); Cancel mid-feed stops within a second or two
  (`Cancelling…`, then `Cancelled`) and a second Refresh All then works; Back (navbar not reachable under the scrim: the hardware key) cancels; turn the screen off during a refresh and on again: the dialog is right (or gone with its line); Import with a
  subscriptions.txt shows it too; covers (including All-In's 2000 px PNG, which needs about a second of CPU): after Refresh All the three shows get their pictures on Feeds, Shows (after a download) and the Show header within a refresh or two (one 3000 px, one 1400 px); `cover.jpg` is about 10 to 20 kB, 192 px; no `.cover.*` file left on the card; a feed with no picture or a dead picture url keeps the disc and still says "N new"; a `cover.jpg` you put in a show folder is never replaced; the app stays up (a bad picture is a libjpeg error caught by the longjmp, not an exit) and the stock Update Local Music is unaffected by the hidden files; Refresh All on the real feeds (time, RAM, the page's rows rebuilding while lit); the folder rename of an imported show; the Feeds button and the capsule on the glass navbar; a refresh with the screen turned off midway;
  Import with a real `subscriptions.txt` (CRLF, trailing spaces); the stock Update Local Music's view of the `.show` / `.episodes` files and of the renamed folders.

## Next: download, unsubscribe, covers, search (design only)

Step 0, the device probe (HTTPS and the CA bundle, Wi-Fi, clock, RAM, screen-off soak), is built: `docs/modules/probe.md` (Customize > Developer > Network Probe). Its findings replace the open checks below.

* **Subscriptions**: a feed url per show in `.show` (`feed=`), created by a "Subscribe" action (url typed or from a file `/mnt/mmc/Podcasts/subscriptions.txt`, one url a line, the simplest first step).
* **Refresh**: a pthread worker (the app's libcurl is already imported; follow redirects, `CURLOPT_RANGE` for `.part` resume) streams the feed through a small push parser (no DOM: feeds reach 4 MB / 441 items), keeps the newest ~20 items
  and rewrites `.episodes` atomically; `<enclosure url length>` become `u` / `l`, `<guid>` `g`, `<pubDate>` `p`, `<itunes:duration>` `d`. The page only reads the file (`pc_load_show` is the one list source: the worker feeds it).
* **Download**: `u` as stored, never the final signed url; write `<f>.part`, `statfs` check against `l` plus a margin, rename on success; the model's `PC_PART` / `PC_REMOTE` rows get a download glyph and a progress line, a tap starts / cancels.
* **TLS**: done in step 1 (the rootfs bundle and the clock guard, "Feeds" above); downloads use the same `PN_CA`.
* **Wi-Fi**: gate on `get_wifisignal` (`0x506cc8`) and the stock network state; never run while the screen is off on battery.
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
