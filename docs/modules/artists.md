# Artists

Split out of docs/architecture.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 5. Artists (`patch/artists.c`)

`ACT_ARTISTS` opens `ui/m1pod_artists.bin` (navbar over an empty stock `list_view`/`scroll_view` plus
scroll bar and a hidden `label_status`), copies the stock artist list (`loadLocalClassList(0xf004)`,
section 3) into its own deque and adds one 52 px stock-styled row per artist (at most 2000) with the
`right_arrow` chevron; the names and artist/album-artist switch are the stock Artists page's. The order is the album Artist order's name rule (`cc_name_cmp`, `cc_heapsort` of `patch/covercache.c`: ASCII case folded, a leading `The ` dropped, ties by stock position), applied by `ar_sort`: `ar.order[]` (stock row at each display position, two `calloc`s of 4 bytes per artist, the pointer array freed at once, `order` freed when the list is rebuilt and on close) is built over the copy, so no stock row moves; a row whose name starts with a non-ASCII byte (the stock index letter at record `+0x54` is not read, our page has no section headers) and the `Unknown Artist` row (id -1) are fixed points at their stock positions and each run of ASCII-initial rows between them is heap-sorted alone, so stock's own placement of other scripts is kept whatever it is; a failed allocation leaves `order` NULL (stock order). A row's click carries its display position and `ar_stock` maps it to the stock row handed to `coverflow_artist`. The sort re-runs at every `ar_load` (open and the mode toggle); about 11 M payload instructions for the 2000 rows the page lists at most. (A navbar button in the toggle slot (`btn_artisttype`; the title reads "Artists" / "Album Artists", the glyph is the other mode's: `pod_nav_artist` / `pod_nav_albumartist`), does what the stock switch handler `0x535770` does: `artist_type` (`0xa05a14`) set, `write_int_config(v, "PLAYSET", "ARTISTTYPE")` (`0x4d6a2c`) and the byte `0xa06d20` (the stock Artists page's reload flag, read at `0x535fe8`) set to 1; then the list is queried again, rows rebuilt and scrolled to the top; the stock toast and style swap belong to the stock page and are skipped; Cover Flow and the album page read `artist_type` themselves). "Update Local Music first" for an empty library.
Statics are prefixed `ar_`.

A tap calls `coverflow_artist(list, index)`: the same page, renderer, cache and touch layer scoped to
the artist (q2-pod's `ARTIST_ALBUMS`, `cf.scoped`):

- **Albums** `loadAlbumList(0xf004, artist)`, copied into the page's deque with the artist's row.
- **Cards.** The stock list's last "All songs" row is kept as the **All albums** card with two albums
  or more (caption "All albums" over the artist, placeholder art, no cache file, tracks = every song
  of the artist), dropped with one.
- **Covers.** Each album takes the cache key of the library album of the same name (`strcasecmp`
  against `getAllAlbum`'s rows, grouped by name `COLLATE NOCASE`), so the page shows the main page's
  files and builds only covers the library lacks (a compilation's library row names whichever artist
  SQLite returned).
- **The album** `loadAlbumList(0xf004, artist)` (the artist goes into the browsing record, the artist's
  albums and the stock All songs row into `*pdeq_showlist`), `albumcoverinfo_init`, `batchadd_albumcover_task(0, 0)`, then
  `navigator_to_with_context("albuminfo_page", 0xff01 | row << 16)`, the context the stock artist page's row
  handler builds (`0x523d94`); the page runs `loadAlbumdetailList(0xff01, row)` itself and leaves class
  `0xff11` (the All albums card: every song of the artist). On every open, as in the main Cover Flow.
- **Ends.** The shelf does not wrap (ring slots past either end stay empty, drag clamped, fling and
  side taps stop at an end); the main page still wraps.
- Title is the artist; the scope never reads or writes `/mnt/mmc/.coverflow/album`; "No albums" when
  empty; Back goes covers -> Artists -> menu. The stock list always ends with "Unknown
  Artist" (id -1), which opens to "No albums" without untagged songs. A refused second open while Cover
  Flow is open.

Borrowed from q2-pod: the scope, the bounded shelf, the All albums rule; not borrowed: its hook on the
stock artist page and its own SQL album list (here the stock page's own list and the stock All songs
row, so no hook). Risks: one row per artist is created up front (slow with thousands); the flat
fallback is not bounded; renamed albums mid-rescan get their own key. Future: A-Z jump (the stock rows
carry an index letter at `+0x54`, which the copy function does not copy), a Sort card.
