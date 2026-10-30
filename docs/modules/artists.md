# Artists

Split out of docs/architecture.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 5. Artists (`patch/artists.c`)

**Genres and Composers are the same page** (`ACT_ARTISTS` with the row's stock Home tile as its argument: `artists_open(0)` Artists, `HOME_GENRE` 7, `HOME_COMPOSER` 8; `ar.cls` is the stock class listed: `0xf004`, `0xf006` `getAllGenre` (`select id,style from songtable group by style COLLATE NOCASE`), `0xf005` `getAllComposer`). The rows, the 2000 cap, the copy and the empty line ("Update Local Music first") are shared; the title is the menu row's text (`Genres` / `Composers`, the row's own key, translated in the 13 languages), the Artist / Album Artist button (`btn_artisttype`) is hidden (`visible=false` and `sensitive=false`: its slot takes no touch; a stray click is ignored, no setting written) and the `ar_sort` order is **not** applied: these two lists stay in the stock query's own order (`group by ... COLLATE NOCASE`, the "Unknown Genre" / "Unknown Composer" row, id -1, last). A row's name is `REC_TITLE` as the stock rows show (the genre row callback `0x4e9b80` stores the one string at `+0x1c` and at `+0x10`). A window that will not open, or an asset that is not ours, opens the tile's stock `localclass_page` through the Home dispatcher (`pod_home_open`), as the Songs lists do. A **genre's tap** is `songs_open_genre(name, unknown)` (`patch/songs.c`; the genre's songs on our Songs page, class `0xff09`, `docs/modules/songs.md` "A genre's songs"). A **composer's tap** is `coverflow_artist(list, row, CLASS_COMPOSERS)`: Cover Flow scoped to the composer exactly as an artist's (below), with `loadAlbumList(0xf005, row)` in place of `0xf004` and `albuminfo_page` opened with class `0xff02`; the stock evidence is in `docs/modules/addresses.md` ("a composer's albums"). The rest of this section describes Artists.

`ACT_ARTISTS` opens `ui/m1plus_artists.bin` (navbar over an empty stock `list_view`/`scroll_view` plus
scroll bar and a hidden `label_status`), copies the stock artist list (`loadLocalClassList(0xf004)`,
section 3) into its own deque and adds one 52 px stock-styled row per artist (at most 2000) with the
`right_arrow` chevron; the names and artist/album-artist switch are the stock Artists page's. The order is the album Artist order's name rule (`cc_name_cmp`, `cc_heapsort` of `patch/covercache.c`: ASCII case folded, a leading `The ` dropped, ties by stock position), applied by `ar_sort`: `ar.order[]` (stock row at each display position, two `calloc`s of 4 bytes per artist, the pointer array freed at once, `order` freed when the list is rebuilt and on close) is built over the copy, so no stock row moves; a row whose name starts with a non-ASCII byte (the stock index letter at record `+0x54` is not read, our page has no section headers) and the `Unknown Artist` row (id -1) are fixed points at their stock positions and each run of ASCII-initial rows between them is heap-sorted alone, so stock's own placement of other scripts is kept whatever it is; a failed allocation leaves `order` NULL (stock order). A row's click carries its display position and `ar_stock` maps it to the stock row handed to `coverflow_artist`. The sort re-runs at every `ar_load` (open and the mode toggle); about 11 M payload instructions for the 2000 rows the page lists at most. (A navbar button in the toggle slot (`btn_artisttype`; the title reads "Artists" / "Album Artists", the glyph is the other mode's: `pod_nav_artist` / `pod_nav_albumartist`), does what the stock switch handler `0x535770` does: `artist_type` (`0xa05a14`) set, `write_int_config(v, "PLAYSET", "ARTISTTYPE")` (`0x4d6a2c`) and the byte `0xa06d20` (the stock Artists page's reload flag, read at `0x535fe8`) set to 1; then the list is queried again, rows rebuilt and scrolled to the top; the stock toast and style swap belong to the stock page and are skipped; Cover Flow and the album page read `artist_type` themselves). "Update Local Music first" for an empty library.
Statics are prefixed `ar_`.

A tap calls `coverflow_artist(list, index, scope)` (`scope` `CLASS_ARTISTS`, or `CLASS_COMPOSERS` for a composer: `cf.scope`, what `loadAlbumList` takes, and, through `cc_open_album(row, scope, index)`, whether the album page opens as `0xff01` or `0xff02`): the same page, renderer, cache and touch layer scoped to
the artist (q2-pod's `ARTIST_ALBUMS`, `cf.scoped`). Everything below holds for a composer with that substitution (`0xf005`, `0xff02`, the composer in the title and on the card):

- **Albums** `loadAlbumList(0xf004, artist)`, copied into the page's deque with the artist's row.
- **Cards.** The stock list's last "All songs" row is kept as the **All albums** card with two albums
  or more (caption "All albums" over the artist, placeholder art, no cache file, tracks = every song
  of the artist), dropped with one.
- **Covers.** Each album takes the cache key of the library album of the same name (`strcasecmp`
  against `getAllAlbum`'s rows, grouped by name `COLLATE NOCASE`), so the page shows the main page's
  files and builds only covers the library lacks (a compilation's library row names whichever artist
  SQLite returned). With fewer than `IDX_MIN` 24 albums the match is that scan per album (the first library row of a
  name wins). From 24 albums up `load_artist` first builds a temporary case-insensitive index of the library's album
  names (open addressing, `calloc` of 8 bytes per library album rounded up to a power of two, hash = FNV-1a over the
  ASCII-folded bytes, equality `cc_nocase`, an equal name already in the table from an earlier row is kept: the first
  row wins) and looks every album up in it, then frees it; a refused allocation falls back to the scan. 200 albums over a
  1000-album library: about 10.2 M payload instructions (most of it the libc compares, `strcasecmp` counted as one
  instruction by the harness; roughly 180,000 string compares) before, 0.5 M with the index (`test/pod/artists.py`,
  which also pins the keys of both paths against a model, with case duplicates, a non-ASCII name and a missing album).
  Below 24 albums building the index (a pass over the whole library) costs more than the scans it saves, hence the threshold.
- **The album** `loadAlbumList(0xf004, artist)` (the artist goes into the browsing record, the artist's
  albums and the stock All songs row into `*pdeq_showlist`), `albumcoverinfo_init`, `batchadd_albumcover_task(0, 0)`, then
  `navigator_to_with_context("albuminfo_page", 0xff01 | row << 16)`, the context the stock artist page's row
  handler builds (`0x523d94`); the page runs `loadAlbumdetailList(0xff01, row)` itself and leaves class
  `0xff11` (the All albums card: every song of the artist). On every open, as in the main Cover Flow.
- **Songs button.** `btn_songs` (the left cap of the Songs | Now Playing capsule at 214) opens our Songs page on the artist's songs (`songs_open_artist`: `loadAlbumList(0xf004)` + `loadAlbumdetailList(0xff01, the All songs row)`, class `0xff11`; docs/modules/coverflow.md, songs.md).
- **Ends.** The shelf does not wrap (ring slots past either end stay empty, drag clamped, fling and
  side taps stop at an end); the main page still wraps.
- Title is the artist; the scope never reads or writes `/mnt/mmc/.m1plus/covers/album`; "No albums" when
  empty; Back goes covers -> Artists -> menu. The stock list always ends with "Unknown
  Artist" (id -1), which opens to "No albums" without untagged songs. A refused second open while Cover
  Flow is open.

**Row recycling: investigated, not done** (the V2.1nL performance review, item 6). One `list_item` + `hscroll_label` + `image` per
artist is still created up front (2000 artists: 6000 widgets, 11.5 M payload instructions, plus the stock construction that was
never timed on the device; 30 artists: 90 widgets). What was established: the stock scroll_view announces every offset change
itself: its offset setters (`scroll_view_set_offset` `0x6115f0` -> `0x60fe7c` for y) dispatch an `offset_change_event` of type
`0x152` to the scroll_view after the new offset is stored (`+0x80` x, `+0x84` y), so a `widget_on(view, 0x152, ...)` listener (no
hook, page-scoped, gone with the window) could re-bind a viewport's worth of rows on every scroll step, including the 200 ms
fling animator (`scroll_view_scroll_to` `0x610340`) and drags. What blocks shipping it without a device and a real-widget test:
(1) each row's click carries its display position as the `widget_on` context, which cannot be changed afterwards; recycling needs
a slot table and a handler that finds the row's current position (its `y` / `ROW_H`), a different click path than the one the
tests pin (`ar_on_artist`, display position -> `ar_stock`); (2) a row that holds the stock press (list_item DOWN grabs its parent,
`docs/modules/gestures.md`) must never be re-bound under the finger: the scroll_view's drag abort and `scroll.c`'s UP abort clear it
before the offset moves, but that order is only argued from the disassembly, not run; (3) a fling can move many rows in one
step, so the overscan has to cover the worst jump of the 200 ms animator, or rows are blank for a frame and, worse, dead to
touches; (4) the artists tests mock `list_item_create` and friends, while proving scroll, tap and the display-to-stock mapping
needs the stock `list_view`/`scroll_view`/`list_item` code running over the recycled rows (as `test/pod/scroll.py` does for
synthetic children) including hit testing and scroll-bar sync (`virtual_h`); that harness does not exist yet; (5) there is no
measurement saying the up-front build is a problem at real library sizes (a few hundred artists is under 1 M payload
instructions and under 1,000 widgets). So the list stays as it is, capped at 2000. If it is ever done: keep `virtual_h` at
`count x ROW_H` (the scroll bar and the 0x152 offsets keep working), create `viewport / ROW_H + 2 x overscan` rows, one 0x152
listener, ctx = slot, and lift `MAX_ARTISTS` only after a device check of memory and scroll feel.

Borrowed from q2-pod: the scope, the bounded shelf, the All albums rule; not borrowed: its hook on the
stock artist page and its own SQL album list (here the stock page's own list and the stock All songs
row, so no hook). Risks: one row per artist is created up front (slow with thousands); the flat
fallback is not bounded; renamed albums mid-rescan get their own key. Future: A-Z jump (the stock rows
carry an index letter at `+0x54`; the copy function 0x5db54c does copy that byte, `docs/modules/songs.md` has its encoding), a Sort card.
