# M1 Pod Artists and Cover Flow per artist (`artists`, V2.1fR)

**Not yet hardware-tested.** Built on `look-all` (V2.1fA: the device build V2.1eA with the Now
Playing album fix): everything V2.1fA has,
plus the M1 Pod menu's **Artists** row opening an M1 Pod artist list, and a tap on an artist opening
**Cover Flow on that artist's albums**. The Cover Flow page also loses its "Tap the centre cover"
hint (see `docs/coverflow.md`, "Artist scope and the layout without the hint").

```
python3 -I tools/build.py --variant artists
# -> out/M1Plus-V2.1fR-artists-look-all-pod-cover-lockscreen-iconpercent-space-update.bin
venv/bin/python -I test/patch.py work/mod-artists-look-all-pod-cover-lockscreen-iconpercent-space
venv/bin/python -I tools/preview_artists.py work/mod-artists-look-all-pod-cover-lockscreen-iconpercent-space docs/artists-preview.png
```

![Artists preview](artists-preview.png)

`docs/artists-preview.png`: the Artists list, an artist's Cover Flow on its first album (nothing to
the left: the shelf has ends), and its All albums card. Approximate (PIL; the covers are the real
renderer, built for the host), sample data.

## What you see

- **M1 Pod → Artists**: a black list of every artist, built like the M1 Pod menu (52 px stock
  `list_item` rows themed `list_item_style`, a white 21 px `srlabel_leftwhite21_style` name, the
  `right_arrow` chevron), scrolling with the stock scroll bar. The order and the names are the stock
  Artists page's; the stock artist / album-artist switch on that page also decides ours.
  "Update Local Music first" when the library is empty.
- **Tap an artist**: the Cover Flow page opens, titled with the artist, on that artist's albums in
  the stock artist page's order. The covers are the main Cover Flow's cached files. The shelf stops
  at both ends instead of wrapping, so an artist with one or two albums does not see them repeated.
- **All albums**: with two albums or more a last card, "All albums" over the artist, with the
  placeholder art. Its centre tap opens all of the artist's songs; a song plays from that list.
- **A centre cover** opens that album's tracks by the artist, and a track plays as on the stock
  artist page (the queue is that album's songs by that artist).
- **Back**: tracks → covers → the Artists list → the M1 Pod menu.
- An artist without albums (the stock list always ends with "Unknown Artist", even when nothing is
  untagged) shows "No albums".
- The main Cover Flow's last-album memory (`/mnt/mmc/.coverflow/album`) is never read or written by
  the per-artist page.

## How it maps onto stock

The stock flow (Home → Artists → an artist → an album → a track) is reused call for call. The
payload adds no hook; the Artists page and the scoped Cover Flow are its own pages.

| step | stock call | evidence (V2.1 `demo`) |
|---|---|---|
| the artist list | `loadLocalClassList(0xf004)` (`0x4ee504`): `GetAllAlbumArtist` (`0x4ea6e4`) when `artist_type` == 1, else `getAllArtist` (`0x4ea9d8`), into `*pdeq_showlist` | jump table at `0x74c5b8` entry `0xf004` → `0x4ee6e8`: `lw artist_type; bne 1 → getAllArtist`. The stock Artists page runs it from `localclass_page_init` (`0x536bb0`) |
| the name on a row | `REC_TITLE` (+0x10) | `getAllArtist`'s row callback `0x4e9724` stores the name at +0x10 and +0x18, `GetAllAlbumArtist`'s `0x4e95b8` at +0x10, +0x18, +0x24; both append an "Unknown Artist" row (id −1) whenever the list is non-empty; the stock row binder prints +0x10 (`0x535dec`) |
| artist or album artist | the `artist_type` global (`0xa05a14`, `.dynsym`) | read from config `PLAYSET ARTISTTYPE` at boot by `config_init` (`0x4e52d0`), toggled and saved by the stock Artists page's `btn_artistswitch` (`0x5357d8`). The payload never reads or writes it: every query below reads it itself. Unlike the Q2 there is no separate `g_artist_type`; this build's `loadLocalClassList` reads `artist_type` directly |
| an artist's albums | `loadAlbumList(0xf004, row)` (`0x4ee8d8`, `.dynsym`) | what `album_page_init` (`0x5248b8`) runs with the context `{0xf004, row}` the stock Artists row handler passes (`0x535d40`). It clears `classinfo_save` (`0xa0c768`, `.dynsym`), stores the artist (row +0x24 when `artist_type` == 1, else +0x18) and loads class `0xff01`: `getAlbumByAlbumArtist` (`0x4eb0e4`) / `getAlbumByArtist` (`0x4eaccc`), `select id,album,songer,fileurl … where [album]songer like '%s' group by album COLLATE NOCASE` |
| the All songs row | the last row of that list: `REC_ID` −2, type 4, `REC_ALBUM` = the translated `local_allsong`, `REC_ARTIST` = the artist | `getAlbumByArtist` pushes it after the query, always (`0x4eae30`: `li v0,-2`) |
| an album's tracks | `loadAlbumdetailList(0xff01, row)` (`0x4eea98`) → class `0xff11` | what `albuminfo_page_init` (`0x5268bc`) runs with the album page's class; `0xff11` = `getMusicByAlbumAndAlbumSonger` (`0x4ed008`) / `getMusicByAlbumAndSonger` (`0x4ecd3c`) with the artist kept in `classinfo_save`. For the All songs row (`classinfo[8]` = 1, `0x4eebec`) the same query returns every song of the artist (`select * … where songer like '%s'`, `0x74c014`) |
| playing | `loadSongList(queue, name, cue, 0xff11)` + `playing_page {queue, index, 0xff11, 2}` | the album page's row handler (`0x5275a4`), unchanged from the main Cover Flow; `loadSongList` copies the class's browsing record into `g_memory_info` for any `0xfXXX` class (`0x4e2d78`) |
| copies of stock rows | `deque_assign` / `_deque_push_back` on an `stSongInfo` deque | the type's copy function (`0x5db54c`, registered by `_type_register(0x58, "stSongInfo", …)` at `0x5dbc7c`) duplicates every string at +0x04 … +0x2c (the album artist at +0x24 included) and copies the words at +0x00, +0x30 … +0x50 |

New pins in `tools/pod.py`: `loadAlbumList` `0x4ee8d8` (checked against `.dynsym`), and two libc
slots demo already imports, `strcasecmp` (`0xa03290`) and `_deque_push_back` (`0xa03358`). New
constants in `patch/offsets.inc`: `CLASS_ARTISTS` `0xf004`, `CLASS_ARTIST_ALBUMS` `0xff01`,
`ID_ALL_SONGS` −2, each with the address that shows it.

**Cover keys.** The main Cover Flow keys a cover by FNV-1a of the library row's artist and album.
An artist's rows can carry another artist (a compilation's library row names whichever track
SQLite returns for the group), so each scoped album takes the key of the library album with the
same name (`getAllAlbum` groups by name `COLLATE NOCASE`, so there is one; compared with
`strcasecmp`, ASCII case aside, as NOCASE does). No cover is extracted twice; an album missing from
the library list keys itself and is built like any missing cover.

## The pieces

- `patch/artists.c` (new): the Artists page. `artists_open` opens `ui/m1pod_artists.bin`, copies the
  stock list into its own deque and adds one row per artist (at most 2000) to the asset's
  `pod_scrollview`; a row tap calls `coverflow_artist(list, index)`. Its statics are prefixed `ar_`
  (test/patch.py finds functions by name).
- `patch/coverflow.c`: `coverflow_artist` and the `ARTIST_ALBUMS` scope (`docs/coverflow.md`), all
  under `#ifdef POD_ARTISTS`; the `#ifndef` halves are the V2.1dE code, so stages without Artists
  compile exactly as before.
- `patch/m1pod.c`: one action, `ACT_ARTISTS` (8: kept clear of the low numbers other features may
  take; Shuffle has 4), dispatched to `artists_open` under `#ifdef POD_ARTISTS`.
- `tools/pod_pages.py`: page `ARTISTS` (kind `list`), `with_artists(menu)` (the Artists row pointed
  at `ACT_ARTISTS`), the hint-free cover page `COVER_NOHINT`, and stage **E** = `[MENU_ARTISTS,
  COVER_NOHINT, ARTISTS]` (stage **G** = the same with the Shuffle rows, `docs/full.md`). A stage
  has the feature when one of its rows is `ACT_ARTISTS`; `tools/pod.py` then compiles
  `patch/artists.c` and defines `POD_ARTISTS` (`docs/payload.md`, "Stages and features").
- `tools/pod_ui.py`: `build_list_page` (navbar, the stock `list_view` > `scroll_view` +
  `scroll_bar_m` of the menu, a hidden and insensitive `label_status`), and the Cover Flow layout
  without the hint (`page.hint` False; stages D and F keep the V2.1dE page).
- `tools/build.py`: `LOOK['artists'] = ('V2.1fR', 'E', LOOK_ALL)`: stage E under the look-all steps.

## Borrowed from q2-pod

q2-pod (MIT, Copyright (c) 2026 Diamond Bond) hands an artist's albums to Cover Flow from its
Artists list (`patch/navigation.c` `artist_list`/`artist_cf_open`, `patch/coverflow.c`
`coverflow_artist`, `docs/internals.md` "Artist Albums in Coverflow"). Taken from it: the
`ARTIST_ALBUMS` scope (`cf.scoped`), the library list kept aside and the artist's list owned by the
page while it is open, no saved album in the scope, the All albums card only with two albums or
more, and the bounded shelf (`coverflow_bounded`: no wrap, ring slots past the ends left empty). Not
taken: q2-pod hooks the stock artist page (veils it and opens Cover Flow over it) and builds its own
artist album list (`coverflow_split`, album identity filters, year order, `play_all` concatenating
each album's tracks); here the list is our own page, the albums are the stock artist page's own
list and the card is the stock "All songs" row, so the M1 needs no hook and no SQL of its own. No
q2-pod code is copied verbatim.

## Tests

- `test/patch.py` on the V2.1fR tree: **203 passed**. New for stage E (sections 26–39): the hint is
  gone and the page is centred; the Artists row opens `m1pod_artists` and nothing else in the menu
  changed; the list comes from `loadLocalClassList(0xf004)`, one stock-styled row per artist with
  its `REC_TITLE`, chevron and index; real hit tests (`widget_find_target`) on every row through the
  `list_view`/`scroll_view`, the navbar buttons, and the hidden message; Back and close (the copy is
  freed); empty library; broken asset; a tap on an artist runs `loadAlbumList(0xf004, that row)` and
  opens Cover Flow with only that artist's albums plus the card, titled with the artist, nothing to
  build, the compilation's cover from the library's file; the frame at the first album compared
  byte for byte with the host renderer's frame of that bounded ring; the card's caption, its tracks
  (`loadAlbumList` then `loadAlbumdetailList(0xff01, the −2 row)`) and playing with `0xff11`; an
  album's tracks; Back tracks → covers → the list; the shelf's two ends and a drag of two albums
  from the card; no last-album read or write in the scope while the main page still reads its own;
  one album (no card), no albums ("No albums"), Cover Flow already open (refused); the kill switch;
  the scoped page's touch layer is hit.
- Mutation check: eight deliberate bugs (ring left unbounded, saved album written in the scope,
  card always shown, artist step skipped, own cache keys, drag unclamped, name from the wrong field,
  hidden-but-sensitive rows) each fail at least one test.
- The other stages, each built into a scratch tree with `tools/pod.py`: A 17, B 15, C 17, D 137
  (the look-all tree, rebuilt with this code), all passing. `test/coverflow.py` (host renderer):
  23 passed, unchanged. After the merge (stage D back to the V2.1dE page): D 132, E 203, F 182,
  G 253 (`docs/full.md`).

## Package

`out/M1Plus-V2.1fR-artists-look-all-pod-cover-lockscreen-iconpercent-space-update.bin`, tag
**V2.1fR**, SHA-256 `a7a5bf7a0bef8cf238f45d8575b24fa4bd2c44a2c654426dcba6642fc65fc7b3`; two clean
builds are byte-identical; `fwtool verify` OK. `fwtool diff` against V2.1eA (`cc86e833…`, rebuilt
from commit 62015e7, byte-identical to the flashed package) lists exactly three files:
`/release/bin/demo` (6,700,712 → 6,704,248 bytes: the payload), `ui/m1pod_cover.bin` (2,673 →
2,504: the hint gone, the layout re-centred) and the new `ui/m1pod_artists.bin` (1,445), plus two
directories that differ only in listed size. `ui/m1pod_menu.bin` is byte-identical (the Artists
row's action is in the payload, not the asset). rootfs 53,129,216 bytes, as V2.1eA (2,609,152 under
the stock limit). Payload 19,576 bytes (248 of `.scratch`), still exactly one hook.

On the branch, rebuilding `pod-cover` or the `look-*` variants gave the new Cover Flow code under
their old tags (look-all `6f5c67ce…`). The merge gates the scope and the hint-free page behind the
Artists feature (`#ifdef POD_ARTISTS`, `COVER_NOHINT`), so `pod-cover` is V2.1dE `0806ade2…` again
and stage E compiles to exactly this payload (19,576 bytes). After the merge V2.1fR stacks on
`look-all` V2.1fA: SHA-256 `d286261590983c35f1c742df0420b10eb107de39d1422879ea2ae6c1353483ab`;
`fwtool diff` against the branch's `a7a5bf7a…` lists only `ui/playing_page.bin` (the album fix).

## Device checklist (not yet hardware-tested)

Fall back to V2.1eA (or V2.1fA) if anything misbehaves; `m1pod-off` on the card still disables M1 Pod.

- boots, About reads V2.1, Home, the looks and Now Playing as on V2.1eA
- **M1 Pod → Artists**: the list opens at once for a normal library (time it with a large one: one
  row per artist is created up front), rows look like the menu rows, the names match the stock
  Artists page in the same order, it scrolls with the scroll bar, a drag does not open an artist
- switch the stock Artists page between artist and album artist (its top-right button), go back to
  M1 Pod → Artists: the list follows the switch
- **tap an artist with several albums**: the title is the artist, only that artist's albums, covers
  without a "Preparing covers" pass if the main Cover Flow has built its cache; no cover repeats;
  the first album is the left end, the All albums card the right end; dragging past either end
  stops
- the **All albums** card: All albums over the artist, placeholder disc; tap it centred: every song
  of the artist; tap one: it plays, and next/previous stay inside the artist's songs
- an album: its tracks; a track plays, the queue is that album by that artist
- **Back** from the tracks to the covers, again to the Artists list, again to the menu
- an artist with **one album** (no card, the cover alone, no repeats) and **Unknown Artist** (likely
  "No albums" unless untagged songs exist)
- after per-artist browsing, open the **main Cover Flow**: it opens on the album it showed last
  before, not on one from the artist
- Cover Flow page itself: no hint line; the album and artist lines sit just under the reflections;
  a tap on the album name opens the album like a tap on the centre cover
- the hardware keys, sleep/wake, a reboot

## Risks

- **Rows up front.** Each artist is a `list_item` with a label and an image, created when the page
  opens (capped at 2000). Fine for hundreds of artists; a library with thousands may open slowly or
  use a few MB. The stock page uses a virtual `table_client`; the task's rule for our lists is the
  stock `list_view`/`scroll_view`, which has no virtual mode.
- **Unknown Artist** is always listed, as on the stock page; with no untagged songs it opens to
  "No albums".
- The flat fallback (no frame bitmap) is not bounded: the stock `slide_menu` draws its own images
  and wraps, so a small artist shelf could repeat there. It only runs when the 1 MB frame and
  textures cannot be allocated.
- The per-artist covers rely on the library list's album names; a renamed album that is in the
  artist's list but not the library list (only possible mid-rescan) gets its own key and is built.

## Next

- **A–Z jump** on the Artists list: the stock rows carry an index letter at +0x54 (`sb s2, 0x54(v0)`
  in `getAllArtist` @`0x4eaca8`, `GetAllAlbumArtist` @`0x4ea9b4`), but the `stSongInfo` copy function
  does not copy that word, so it would have to be read from `*pdeq_showlist` before the copy.
- **Sort card** for the main Cover Flow (artist / title / year / random, q2-pod's Sort card): the
  album rows carry no year (`getAllAlbum` selects `id,album,songer,fileurl`), so Year needs a query of
  its own; Artist and Random would be a `qsort`/`rand` over our copy (both in demo's GOT).
- An album count or the first cover per artist on the Artists rows: needs a query per artist.
