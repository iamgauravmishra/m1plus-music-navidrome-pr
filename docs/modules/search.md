# Search

Our own library search, in the Apple Music manner (the reference is the iOS search screen): a rounded field with a clear disc and a round X, a row of chips (**Top Results, Artists, Albums,
Songs, Playlists**) of which exactly one is selected, and rows with a thumbnail, a title and a grey line, results that follow the typing, and **our keyboard embedded at the bottom of the same
page**. It replaces stock's `search_page` (a T9 dialog, then `SearchMusicByName` and its siblings, SQLite `LIKE '%x%'`) on the Songs page. A pinyin-initials index is round 2
and is not built (the code is structured for it, below).

Code: `patch/search.c` (all of it), `patch/search.h` (the entry point and the page's geometry), `patch/keyboard.c` (`keyboard_attach`, below), `patch/songs.c` `sg_on_search`. Asset: `ui/m1plus_search.bin` (`tools/pod_ui.py` `build_search_page` and `keyboard_pad_widgets`), `tools/pod_pages.py` `SEARCH`. Layout
model: `tools/pod_search.py` (parses the `#define`s of `patch/search.h`: one set of numbers for the builder, `tools/preview_search.py` and the tests). Tests: `test/pod/search.py` (sections
`fold_tests`, `query_tests`, `rank_tests`, `incremental_tests`, `page_tests`, `chips_tests`, `live_tests`, `tap_tests`, `perf_tests`, `entry_tests`, `embed_tests`, `asset_tests`).
Preview: `uv run python -I tools/preview_search.py work/mod-release out/preview/search.png` (Top Results with the keyboard up, the Albums chip with it hidden, the empty state, the Songs chip;
each panel also as `search-<name>.png`; thumbnails are stand-in colours). **No hook, no new import, no thread; one page-scoped timer; nothing else runs from outside the page's widgets.**
Strings: `Top Results`, `Song`, `Playlist` (new, 13 languages), `No Results`, `Artist`, `Search`, `Artists`, `Albums`, `Songs`, `Playlists` and the stock `album` (existing keys).

## The page

Window 320 x 450 (the numbers are `patch/search.h`; `pod_search.py` mirrors them):

* **Field** (x 12, y 8, 250 x 36, radius 18, `#1C1C1E`): the keyboard's own field widgets (`kb_field`, `kb_mag`, `kb_hint`, `kb_text`, `kb_caret`, `kb_clear`) with the page's text x (36) and room (178),
  so the keyboard code measures, cuts with an ellipsis and moves the caret exactly as on its own page. The placeholder is `Search`. A tap on the field (a pointer-up on `kb_field`) shows the keyboard.
* **X** (`btn_return`, x 270, 46 x 44 touch, drawing `se_close`: a flat 36 px disc in the field's grey (#1C1C1E, pressed #3A3A3C) with a white 13 px x, as high as the field and on its centre line; the 42 px glass disc of the navbars looked larger than the 36 px field beside it): Back (`pod_on_back`). The hardware Back key does the same.
* **Chips** (`se_chips`, y 52, 34 high): each chip is as wide as its text plus 14 px a side, 6 px apart from x 12 (`PS.chip_layout`, texts measured in the 16 px chip font at open: the page's
  language); with the five of English the row is wider than the screen, so it **scrolls sideways** (a drag of 6 px, clamped to the ends; a tap selects). The selected chip is a light grey pill
  (`se_chip_hl`, `#E5E5EA`, radius 15, a view behind, moved under the chip) with dark text (`label_chip_on`); the others are white text. The texts are painted by the row's
  `EVT_AFTER_PAINT`; no accent colour anywhere (the reference's blue chip is grey).
* **Line** under the chips (y 88, `#2C2C2E`), then the **list** (y 90 to the window's bottom): a stock `list_view` > `scroll_view` holding ONE content view that paints the rows itself (the Artists
  page's pattern; the keyboard covers the list's lower part, so with it up the content is padded by the pad's height and the list scrolls clear of it).
* **Rows** (60 px, no headers): a 44 px thumbnail at x 12 (**round for an artist**, 4 px corners for an album, a song and a playlist), the title (21 px white) and the grey line (18 px, `#AAAAAA`)
  from x 68, a chevron (the Artists page's, `pod_make_chevron`) at x 288 on artists, albums and playlists and none on songs, and a hairline from x 68 to 310 under every row. The grey line is
  `Artist`, `Album · <artist>`, `Song · <artist>` or `Playlist` (translated; the album word is the stock key `album`).
* **Thumbnails** use the covers we already have and are loaded lazily: an album's and a song's is the Cover Flow cache file of its artist + album (`cc_album_key`, `cc_url`; a song whose own file is
  missing takes the library album of that name's), an artist's the cover of the first album of theirs that has one, a playlist's and anything without a file the stock placeholder disc (`p_default`),
  all through the Albums grid's ring (`patch/grid.c`; `grid_art` decodes one cover; `GRID_MAX_ROUND` is 22 for the round ones). Text and thumbnail of a row are made when it is first painted (16 tiles
  of each shape: the rows in view, two beyond and the history); **one cover is decoded per tick of the page's timer**, never while a query is waiting, so typing is not blocked by decoding. The timer ends when nothing is left, so **a paint that finds a tile without its thumbnail starts it again** (`se_cover_next` in `se_on_paint`): a chip change or a scroll makes
  new tiles after the timer ended. The source is the cache's only size (168 px JPEG, the Songs page's rows read the same file), box-reduced to 44 px per decode; there is no smaller tier.
* **Empty state** (the page as it opens): the keyboard up on its capital page, the field with its placeholder and caret, the chips, an empty list and no text. **No Results** (`label_status`) shows
  for a query that matches nothing; an emptied field goes back to the empty state.

## Live search

The keyboard is not a page of its own here: `keyboard_attach` (below) puts its pad, candidate strip and key pop-up on this window, so **nothing flashes** when the page opens or when the user types
or searches. The flow:

1. `search_open()` (the Songs page's Search button) opens `m1plus_search`, attaches the keyboard (`se_on_text` for the text, `se_on_go` for the action key), lays the
   chips out and starts the page's timer with `wait` 1. It returns -1 when a Search page exists already or the window or its widgets are not there; both callers then open the stock search page.
2. Every change of the field's **committed** text calls `se_on_text`: it ignores a repeat (a layer or page switch re-reports the same text), keeps the text and sets `wait` to `SE_DEBOUNCE` (5).
   The Chinese layer's pinyin still being composed is not in the field, so it is not searched until a candidate is taken (space, a tap on a candidate or the action key commits it).
3. **One page-scoped timer** (`se_tick`, `SE_TICK_MS` 40 ms, started on demand, removed with the page, ended by the tick that has nothing to do): each tick counts `wait` down; at zero the text is
   applied (`se_apply`: the library is read if it has not been, the query searched, the rows of the selected chip built). That is **200 ms after the last keystroke**. Between queries the same
   tick loads one cover; it returns the timer's end (RET_OK) when there is nothing to load.
4. **The library is read once**, by the first tick (the page has been shown by then): `loadLocalClassList(0xf004)` copied (the Artists page's list), `cc_albums()` (the Albums page's, copied),
   `loadLocalClassList(0xf00b)` into `*pdeq_playlist` copied (patch/playlists.c's way) and `loadLocalClassList(0xf001)` left in `*pdeq_showlist` (the Songs page's list, not copied: the rows are
   record numbers). Stock queries are page state, run only from this page in front (its timer, never a key's handler). The songs query is last, and `g_class_type` is then set to `0xf001`: the stock
   album page under this page compares `g_class_type` with the class it saved (its to-foreground handler `0x5266d4`) and re-runs its own query when they differ, and rebuilds its header, whose cover then stays the placeholder (stock shows the cover file only when the cover thread finishes). Search is never over a live album page (it opens from the Songs page; an album page opened from a result is destroyed by Back), so this does not happen with ours. Search never touches the cover-task list: only the tap that opens an album does (`cc_open_album`).
5. **A replaced list.** Another page's query replaces `*pdeq_showlist` (an album or an artist was opened from a result). `se_valid` (the pointer and the size) is checked when the page comes back
   (`EVT_WINDOW_TO_FG`), when a song tap is made and when paint needs the list; a stale list re-reads the library on the timer and searches again at the same query, and a song tap that found
   it stale is lost. Artist, album and playlist rows use the page's own copies.
6. **Hiding the keyboard**: dragging the list (the scroll_view takes the gesture and aborts the press: `se_on_abort` with a press in progress), and the keyboard's action key (`kb_go`, which reads
   `Search` here). A tap on the field shows it again. Hidden, the pad is invisible **and insensitive** (it takes no touch), the caret goes, a held key or a pop-up in the air is let go, the content
   is no longer padded. Going behind another page leaves the keyboard as it is.

## Matching

Everything is code points. `se_next` decodes UTF-8 (a byte that is not UTF-8 is its own code point), `se_cp` folds one, `se_cat` appends a text's folding to a key, `se_fold` is the test entry
(external, so the compiler keeps its general form). **The folding and the multi-term AND are unchanged from round 1:**

* Case: ASCII, Latin, Greek (capitals and small letters, final sigma, tonos) and Cyrillic (`ё` is `е`).
* Latin diacritics: Latin-1, Extended-A, the Extended-B letters songs use, Extended Additional and the Vietnamese block, as one table of ranges (`se_latin`): `é ü` give `e u`, `ß` gives `ss`,
  `ø` gives `o`, `æ œ þ ĳ` give `ae oe th ij`, `ł đ ð` give `l d d`, `ı İ` give `i`. NFD input (the combining marks U+0300..036F) loses its marks.
* Kana: katakana and `ヽヾ` become hiragana; half-width katakana become the hiragana of the full-width form, with a following `ﾞ` / `ﾟ` (or U+3099, U+309A, U+309B, U+309C) composed onto the
  letter before it. A dakuten stays a distinction (`か` is not `が`); `ー` stays. Full-width Latin and digits become ASCII, every kind of space is `' '`, typographic quotes and dashes become ASCII.

The query is folded and split at spaces into at most `SE_TERMS` (8) terms. A record matches when every term is a substring of its key: the record's fields folded and joined by a space (a term has
no space, so it cannot match across two fields): a song's title (its file name when it has none), artist and album; an album's album and artist; an artist's or a playlist's name. A key is cut
at 160 code points. The rows `Unknown Artist` / `Unknown Album` (id -1) are never results.

**Quality** (`se_test`): 0 when the key's first field is the whole query (the terms joined by single spaces), 1 when the key starts with the first term, 2 otherwise. **Incremental filtering:** the
records that match are kept per type in library order with their quality (`cand`, `sc`, `nc`; every match, not just the rows shown). A new query whose folding **starts with** the folding of the
one they are of (`se_search`: the previous code points compared) can only match what matched before, so only those are tested, in place (a match is written at or before where it was read); any
other query (a deleted letter, a different word) scans the library. `have_prev` is cleared whenever the library is read again.

**Round 2 (pinyin initials, not built).** `se_key` builds one key per record and `se_test` tests one array. A second key (the initials of the characters' readings, from the engine's
`get_splids_for_hanzi`, `keyboard.md` "Hanzi to pinyin") is another array tested the same way, the best quality of the two kept; the folding, the terms and `se_find` do not change.

## Rows by chip

* **Top Results** (`SE_CAP_TOP` 30): the best quality first (0, 1, 2) and inside a quality the types in the order artists, albums, playlists, songs, each in library order. So an artist or album
  named exactly what was typed comes first, then names that start with it, then the rest, interleaved by match quality.
* **A type chip** (Artists 100, Albums 100, Songs 200, Playlists 100): that type's matches, best quality first, library order inside a quality. Selecting a chip builds its rows from the matches
  already known (no query, no library read), resets the list to the top and scrolls the chip row so that the chip shows.

| Row | Tap |
|---|---|
| artist | `coverflow_artist(copy, row, CLASS_ARTISTS)`: Cover Flow on that artist, as the Artists page's tap |
| album | `cc_open_album(NULL, 0, stock row)`: our album page, as the Albums page's tap |
| playlist | `songs_open_playlist(id, name)` (the id is `REC_DISC`), else the stock Songs page with the playlist class, as the Playlists page's tap |
| song | the library in its stock order as the queue (`loadSongList`, class `0xf001`, the row's own index wins for duplicate file names), Now Playing at the song (`se_play`, the Songs page's `sg_play_at`); a missing file toasts `Storage unavailable` |

A tap is a press and a lift within `SC_DRAG_PX` on the same row (a drag, an abort or a background take it back).

## `keyboard_attach` (patch/keyboard.c)

`keyboard_open` is unchanged for its callers (Playlists New, the Developer Keyboard page: same asset, API and tests). Its body is split: `kb_init` finds the widgets by name and binds them, sets the
first page and layers (the same for both ways of having the pad); `keyboard_open` adds the window, the title, `KB_DONE`, Back and the destroy handler. `keyboard_attach(win, placeholder, text_x,
text_w, caret_y, on_change, on_go)` runs the same `kb_init` on another page's window (`kb.embedded`): the field's inner geometry is the caller's (`kb.tx`, `kb.tw`, `kb.cy` instead of the page's
constants), `kb_refresh` ends by calling `on_change` with the text, the action key calls `on_go` (after committing a pending candidate; no page is closed), and the page's destroy handler calls
`keyboard_detach` (the timer, the engine's megabyte, the state). `keyboard_show(0/1)`, `keyboard_shown()` and `keyboard_text()` are the rest of it. One keyboard at a time: an attach or an open
refuses while one exists. The asset side is `keyboard_pad_widgets()` in `tools/pod_ui.py`, which both pages end with: the pad, the strip and the pop-up are the same widgets by the same names
(a test compares the two assets' copies byte for byte).

## Entry points

* **Songs page**: `sg_on_search` calls `search_open()` instead of `navigator_to("search_page")`; the button does nothing in select mode or with the sort card open, as before. The other lists on
  that page (Favourites, a playlist, an artist's songs ...) search the whole library as the stock search did. When ours will not open the stock page does (`search_open() < 0`).
* **Album page**: untouched. Stock's search disc (made by the toggle navbar builder `0x526a3c` after a select cycle) still opens the stock search page; a custom album page will replace it. A result's album row opens the album page.

## Cost

Test `perf_tests` (`m.icount`, payload instructions; the stock queries cost extra, and are made once): reading the library (the first tick) is 0.5 M besides the stock queries; a **full scan** of
5,000 songs (with 300 artists, 800 albums) is 20 M, of 20,000 songs 76 M (about 3,800 a song; some tens of milliseconds to a few hundred on the device); a query that extends the last one costs only
its matches (a query matching one title in eight: 2.4 M and 8.2 M); typing a query letter by letter runs one full scan for the first letter at most and the rest on the shrinking matches, a
deleted letter one scan.

## Not verified on a device

1. Everything about the embedded keyboard on the real page: the pad's touches with the list and chips behind and above, the hide/show by drag (the abort that the scroll_view's takeover sends to the
   content view), the tap on the field (a pointer-up on a view), the pop-up over the list.
2. The time of the first query on a 20,000 song library on the device (the emulation says about 76 M instructions), and the first tick's stock queries.
3. The thumbnails: the lazy loader's feel while scrolling, the round artist picture (a corner table of radius 22, blended in the alpha), the placeholder, the artist's cover being the first album's.
4. The chip row's drag and tap, the pill following it, the texts in the 13 languages (widths checked against the font, not seen).

## Deferred

A pinyin-initials key, highlighting the matched text, a "show all" row past the caps, scoped search from a type, recent searches (the empty state is blank), the Folders and stock Artists / Albums
pages' own search buttons (stock pages; the Albums grid and Artists pages have none), album and song covers beyond the cache (no extraction here), playlist mosaics.
