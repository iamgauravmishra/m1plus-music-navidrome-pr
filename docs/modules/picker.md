# Add to Playlist picker

Our own picker replaces the stock one. Add on the Songs page and the album page (`so_add`, `patch/songops.c`) opens it; the stock `playlist_page` in picker mode
is only the fallback. Files: `patch/picker.c` / `picker.h` (the add and the copies), `patch/playlists.c` (the page: pick mode), `test/pod/picker.py`,
`tools/preview_picker.py` (the mock: `out/preview/picker.png`, rows as `preview_icons.playlists_grid(pick=True)`).

## Choice: a page, not a sheet

Our Playlists page in list mode, titled "Add to Playlist". A glass sheet (the Playlists "..." menu, the Songs Sort card) is for a handful of fixed rows; the picker
lists up to 100 playlists with mosaics and counts, so it needs the scrolling list, the mosaic loader and the row painter the Playlists page already has. One
code path, the same rows the user knows, nothing new to keep in step. The design is the page's: neutral greys, 64 px rows (52 px mosaic, name, count), the
pressed row `#333333`.

- Navbar: Back (glass chevron) and the title "Add to Playlist" (the Songs pill's text, short in all 13 languages; its label is widened to `SG_SELALL_X`, as
  in select mode). The "..." button, the view toggle and Now Playing are hidden and insensitive; the page is always the list (the saved grid / list choice is
  the Playlists page's own and is not written).
- Row 0: "New playlist" (the stock key `playlist_create`, as the Playlists "..." menu), a white plus on a dark rounded square (`pl_plus`), no count. A tap opens our keyboard
  (`keyboard_open`, as the Playlists New); its Done creates the playlist (`createPlayListItem`: -1 full and -2 exists say the stock message and leave the picker
  open) and adds to it.
- Row 1: "Favorites" (our own key, the Favorites row of the Extras page, translated in all 13 languages), a white filled star (24 px alpha bitmap made at open by `pl_make_star`, 4 x 4 samples a pixel; the same glyph as the Favorites icon, which the repo draws as a star everywhere, not a heart) on the New row's dark rounded square, no count. A tap adds to Favourites and closes, as a playlist row does. `pl_v()` is 2 in pick mode (the rows before the playlists).
- Rows 2..n: the playlists, the name and "N tracks" once read (the page's loader, one playlist a tick). A tap adds and closes.
- Back, or the system back, closes with nothing added; there is no tap-outside (it is a page). Now Playing is not offered.

## What it does with a tap

The stock row handler (`0x53d300`, in picker mode) is: `batch_add_file(class, 0xf00b, *pdeq_showlist, *SEL_VEC, playlist id)` (`0x4da7dc`; the id is the row's
`REC_DISC`; it skips songs already in the playlist with `checkPlayListExist`, then `addPlayList`), the message `msg_addplaylistsuccess` in `dialog/msginfo_dialog`,
`window_close` of the picker's window. `picker_add` does the same, in the same order. Pinned (`tools/pod.py` `PICKER_PINS`): the prologue of `batch_add_file`,
and the handler's `ori a1, 0xf00b`, `jalr batch_add_file` and the store of the 5th argument. `batch_add_file` is declared there (`FUNCTIONS`, `int (int, int, void *, void *, int)`).
Stock returns nothing the handler tests, so neither do we: the message is always the success one, as stock.

**Favourites** is the stock Add button's other choice (`dialog/batchadd_dialog` returns 1; handler `0x5280c0`, the path at `0x5281c8`): `batch_add_file(g_class_type, 0xf00a, *pdeq_showlist, *SEL_VEC, 0)` (`ori a1, 0xf00a` `0x5281c8`, 5th argument `sw zero, 0x10(sp)` `0x5281cc`, `jalr` `0x5281e8` with `a0 = *g_class_type` loaded in its delay slot `0x5281ec`), then the message `msg_addfavsuccess` (`0x52822c`; stock en_US text "Added To Fav", in `pod_i18n.STOCK`) in `dialog/msginfo_dialog`. Stock stays on its page afterwards; ours closes the picker, as for a playlist. With nothing selected stock shows `msg_addfailed` first (`0x5280ec`): ours never opens with an empty selection (`so_add`). `picker_add(PICKER_FAVOURITES)` does it on the same copies, so the arguments are the playlist add's with class `0xf00a` and 0 for the id. Pinned in `PICKER_PINS`: `0x5281c8`, `0x5281cc`, `0x5281d4` (the GOT load of `batch_add_file`), `0x5281e8`, `0x5281ec`, `0x52822c`.

**The copies.** The Playlists page reads every playlist to show its count and mosaic (`loadLocalClassList(0xff13)`), and each read replaces `*pdeq_showlist`, the list
the add needs. So `picker_open` copies the list (`cc_copy_list`: the page's `count` rows must be the stock list's, else -1) and the marks (the page's bitset)
when it opens; `picker_add` fills the stock selection vector from the copy of the marks (`so_selection`, as the stock-picker path did) and passes the copy to
`batch_add_file`. The call writes the new ids into the copy's records (stock writes them into the shown list's); the caller reads its list again anyway.

**The browsing record.** Those queries also set the browsing class, `classinfo[0..1]` and the navigation title. The picker saves them at open and puts them back
after every query it runs (`picker_restore`: after each playlist scan, the playlist list, the creating query) and when the page is gone (`picker_release`, from
the page's destroy), so the caller's own restore on its to-foreground (which `so_add` still sets up: `title_save`, `*picker`) finds them as they were, and its
reload of the list uses them. The stock picker's side effects (class `0xf00b`, the saved title) do not happen: stock's page never runs.

**Over our Playlists page's Songs page.** The Playlists page keeps its state in one struct (`pl`). When the picker opens while the Playlists page is below (Playlists >
a playlist's Songs page > Add), the state is copied aside (`calloc`) and `pl` is the picker's; the page's destroy puts the copy back (the Playlists page below
was in the background all along: its loader stopped, to-foreground reads it again).

**Fallback.** `picker_open` returns -1 and `so_add` runs the stock path exactly as before (the selection into the stock vector, `playlist_page` with `PICKER_ADD |
class`) when: the stock list is not the one the marks are of, the copies cannot be made, the window `m1plus_playlists` does not open, the asset lacks a widget,
or a picker is already open. The SD file `/mnt/mmc/m1plus-off` disables the whole payload (then stock's page is the only one).

## Not seen on a device

Whether `window_close` of the picker after the toast dialog behaves as stock's (it is stock's order); the keyboard closing while the add runs (`pl_named` is
called after the keyboard was told to close; its other results already work that way for the Playlists New); the look of the star on the Favorites row (the New row's plus and the star are drawn by the page's after-paint over a dark square), and that `batch_add_file` with class `0xf00a` adds the way the stock Favourites button does on a list that is not the library's, are not seen on a device).

## Tests (`test/pod/picker.py`)

Opening (page, title, hidden buttons, the list with New playlist and Favorites first and the counts, the caller's record kept through the scans), the Favorites row (`batch_add_file` with class `0xf00a` and 0, `msg_addfavsuccess`, the star bitmap's pixels), a tap (`batch_add_file`
arguments and rows, the copy of the list, the stock vector, the message, the close, a second tap does nothing, the record back at destroy), New playlist
(keyboard, -1 / -2 stay, a made playlist gets the songs), Back (nothing added), the fallbacks (-1 with no window, a changed list, a second picker) and the stash
over an open Playlists page. `test/pod/songs.py` and `albumpage.py` refuse the window `m1plus_playlists` where they assert the stock picker fallback.
