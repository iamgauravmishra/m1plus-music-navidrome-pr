# Library rows

**Sources:** `patch/rows.c`, `patch/rows.json`.

q2-pod's restyle of the stock library pages (from its `patch/ipod.json`, `compact_set_row_layout` /
`compact_row_layout`): Songs (and Hi-Res, Favourites, Recent, Most played, a playlist's songs),
Folders, Artists/Genres/Composers, Albums, an album's tracks, Playlists, Search and Now Playing's jump
list get 64 px rows on a 60 px body, 52 px album art drawn 1:1, 21 px titles to a 12 px right margin,
and long titles ending in an ellipsis instead of all scrolling at once. These rows are built by demo's
row constructors with their sizes as `addiu` immediates, so an asset can only choose the pitch; hence
pinned edits plus a small payload function. Constants: `PITCH 64` (Folders divides `yoffset` by 64
with `(y + 63) >> 6` at `0x531bac/0x531bb8` and `0x532488/0x532498`), `BODY 60`, `ART 52`,
`ART_INSET 4`, title box y 7 / h 24, meta y 33 / h 20, `ROW_RIGHT` 12.

| page | stock | now |
|---|---|---|
| Songs | row 60, button 56; title 200 wide, 20 px at y 10; artist 175 at y 30 | row 64, body 60; title x 60..298 (238), 21 px in 24 at y 7; grey 18 px line at y 33 (20) full width, 213 after the MQA badge; multi-select 94..298 |
| Folders | row 64/60; title 220, chevron at 288 | title 60..277, chevron 285..298; 60..298 for a song file |
| Artists / Genres / Composers | row 60, button 56, title 220 | row 64, body 60, title 60..277, chevron 285..298 |
| Albums | item 60, cover 60 at x 0, title 180 at y 10, chevron 296 | item 64, cover 52 drawn 1:1 at (4,4), title/artist 60..277 at y 7/33; 8 covers per batch |
| an album | track rows 60, "N title" 260 wide; header boxes 20/18 at y 10/30 | track rows 64, "N title" 12..298; header boxes 24/20 at y 7/33 |
| Playlists | items 60, name 220, create label (60,20,220,20), Import/Export (60,20,90,20) | items 64, name to 12 px before the arrow, create label (60,18,238,24), Import/Export y 18, 24 high |
| Search | tab rows 64, title 250 at y 10, album covers 60, scroll-end divides by 120 | title 238 at y 7, artist y 33, covers 52 at x 4, divides by 64 |
| jump list | row 60, button 56, text 200, rebind 250x56 | row 64, button 60, text 238, title (0,7,238,24), artist y 33, rebind 238x60 |

Every title is 21 px (`srlabel_item_white_style`/`gold20` per page theme, `mod_lists.py`), the
second line stock's `srlabel_item_gray18_style`; hscroll_labels scroll only while focused
(`hscroll_label_set_only_focus`), which on this touch UI no row is.

**The demo edits** (`patch/rows.json`, applied by `pod.py patch_rows`, every listed word checked
against stock first; the build refuses any mismatch): 101 edits and 38 more words pinned unchanged.
84 `addiu rt, $zero, imm` immediates (one of them, the navbar's Back x, replaces a `move rd, $zero`) (pitch, body, rebind size, cover width, the cover thread's
thumbnail size 60 -> 52 at `0x4dd604` and the album page header cover 100 -> 160 at `0x4dd670`, title/meta boxes, Playlists labels, cover batch,
the navbar builders' heights and right-hand buttons on the Pod navbar's slots, see `docs/modules/album-page.md` and `docs/modules/navbar.md`); 10 call sites
where each ordinary row constructor's `jalr $t9` to `widget_set_children_layout(row, "default(...)")`
becomes `jal compact_set_row_layout` (layout string left in the delay slot): Folders `0x5332bc`, Songs
`0x528624`, Artists `0x53696c`, Albums `0x524494`, album tracks `0x52651c`, Playlists `0x53e6ec`,
Search tracks/artists/genres/albums `0x541924/0x542208/0x542560/0x542930`; 3 nops (the Folders,
Artists and Songs rebinds' `widget_resize(title, 220/250, h)` at `0x532f6c`, `0x535e94`, `0x527918`;
the jump list's `0x5390ac` stays, patched in width/height). Pinned unchanged: the folder pitch, bodies
already 64/60, the `>> 6` divisions, the shared layout strings `0x745158/0x745360` and the default
layouter's vtable slot (`0x904924`, layout fn `0x63a444`).

**The row fit.** `compact_set_row_layout(row, params)` calls the stock `widget_set_children_layout`,
then, if it succeeded, the layouter is the stock default one (checked at run time and build time) and
the kill switch is absent, points it at a copy of the default vtable in `.scratch` whose layout slot
is `compact_row_layout`, which on each layout: finds the text (first `hscroll_label`, or the first
child holding one), gives it the row width minus left margin, right margin (at least 12) and every
other visible child's width + spacing; lays `list_item` rows out 4 px short so children sit on the
60 px body above the separator; calls the stock default layout (anything unexpected -- no layouter,
no text, more than 16 children, a hidden title -- leaves it to stock alone); then moves an x=0 row's
cover to x 4 and stretches a line's last label to the view's end. No relayout loop: every value is the
same on every pass (a widget's resize marks the window for relayout; `widget_resize`/`widget_move`
return early on an unchanged size, `0x66d198`). About 1.8 KB of payload.

**The repeated disc** (`rows_track_icon`, `rows.json` `icon_calls`). The Songs-family rows (Songs, Hi-Res, Favourites, Recent,
Most played, Recently added, a playlist's songs) and the queue show, left of the title, the track's file-format disc
(`list_get_left_icon` `0x4d972c`: `icon_flac`, `icon_mp3` ... one picture for a library in one format) or, on the playing row,
`icon_playing`. Both rebinds (`0x5283a0`, `0x539244`) end both paths in `image_base_set_image(img_icon, name)` (`0x5284e0`,
`0x53935c`); that `jalr` becomes `jal rows_track_icon` (its `lw $t9` and the two argument moves pinned). It makes the stock call,
then, unless the kill switch exists, hides `img_icon` (visible and sensitive off) for any name but `icon_playing` and the place
icons (`icon_folder`, `icon_playlist`, `icon_tf`, `icon_otg`). `widget_set_visible` relayouts the row, whose fit skips
the hidden child, so the text container starts at the 12 px margin and runs to 298. The playing row (`icon_playing`) keeps the
widget as its marker: the image becomes `np_row_playing` (40x20, a 20 px wave at its right end, added with the `np_*` images), drawn
`IMAGE_DRAW_CENTER`, and the widget is restacked last in the row (`widget_restack` `0x669fc4`, `widget_set_need_relayout_children`
`0x66c338` when only the order changed; both pinned in `tools/pod.py`, parent at widget offset `0x44`): the flow (the row fit, or the
queue's stock `default(r=1,c=0,x=12,s=8)`) then puts the title at x 12 (238 px: the row fit subtracts the 40 px widget and its spacing;
the queue's title is 238 by its immediate) and the 40 px marker widget at 258..298, wave at 278..298. A recycled row rebound to another
track hides the widget and restacks it back before the text. Rows with a check box keep it first. The kill switch leaves the stock call.
The same function serves a third call site, the Artists / Genres / Composers rebind (`0x536634`): its four paths (`icon_playing`,
`icon_artist`, `icon_composer`, `icon_genre`: one placeholder per page, no per-item art) join at `0x5367ac`, and the `jalr` at
`0x5367b0` becomes `jal rows_track_icon` (`0x5367ac` and the delay slot `0x5367b4` pinned). Those rows end in the chevron button
(`btn_right`), so the marker is restacked before a trailing button (`end = n - 2`), not after it: name 217, marker 237..277, chevron 285..298;
without the marker the name is 265 px from x 12. Not touched: Folders (its icons tell folders from files), Search (types), the Playlists
page (a playlist is not a track). No site is reachable from `main` / `platform_init` (`tools/reach.py`).

**The track number** (`rows_track_number`, `rows.json` `text_calls`). The album detail rows are built by `albumdeinfo_listitem_layout`
(`0x526394`: the tick `img_choice`, then `0x524b50`, called once per row at `0x5264a0` while the page builds, which creates the
`listsscrlabel_N` hscroll_label, styles it white or gold, and formats `"%d %s"` (position + 1, the title; `0x524ce0`) into a stack buffer
that `widget_set_text_utf8(label, buffer)` (`0x524cf4`) sets). That `jalr` becomes `jal rows_track_number` (the format load `0x524cdc`,
`move $a1` `0x524ce8`, the GOT load `0x524cf0` and the delay slot `0x524cf8` pinned; stock label builder otherwise untouched, the page's one
hook stays `albuminfo_listitem0_layout`). It splits the leading 1-3 digits and one space off, creates once per row a plain `label`
(`label_create`, `ROW_NUM_W` 24 px wide, 35 for three digits; `srlabel_tracknum_style`, insensitive) restacked just before the title, sets the number
on it and the rest on the stock title label. The row fit does the rest (the number is a visible child, so the title is narrowed by its width + 8).
A row that already has the label (a rebuilt or recycled row) reuses it and sets its column width. Anything else (no number, no space, more than
three digits, kill switch, `label_create` failing) sets the whole text on the title as stock. The style is in the `albuminfo_page` page theme
(`tools/mod_ipodrows.py`: `label`, `#AAAAAA`, 21 px, right aligned). The multi-select pass (`visiable_list_selectbox` `0x4cc9b0`) matches
children by the name `img_choice` only, so the extra child is invisible to it. Not reachable from `main` / `platform_init`.

**Safety.** `tools/reach.py` builds an over-approximate graph of stock demo (12,162 functions; an edge
for every call, GOT load or address taken) and walks it from `main` and `platform_init` except through
the navigator's open-by-name dispatcher (`sub_4d00c0`): none of the 25 functions holding an edit is
reachable, except `parse_albumcovertask_thd`, started at boot, which sleeps 50 ms, takes a task from
the cover task list and loops when empty; its producers are not reachable at boot either, and the edit
is the thumbnail size constant (tmpfs files, read only by the Albums and Search album rows, both now 52
px). No prologue is rewritten, the payload runs only where the patched instruction ran, `$gp` is
reloaded by every patched caller from its stack slot (checked at all ten sites), and nothing is hidden
or shown (hit testing unchanged). The kill switch `/mnt/mmc/m1plus-off` turns the fit off (stock layouter);
the 46 immediates and 3 nops are static, so the way back from them is a stock re-flash.

## Row assets

`tools/mod_ipodrows.py` edits the five row `ui/*.bin` (`localclass_page`, `allmusic_page`,
`playerjumpinfo_page`, `album_page`, `playlist_page`: `row_height` / `default_item_height` 60 -> 64 and the jump list's template row) and the page
themes (`allmusic_page`, `playerjumpinfo_page`, `albuminfo_page`, `playlist_page`, `search_page`, new
`album_page`, both themes, 21 px titles, `srlabel_item_gray18_style` second line). Rows are 64 px with a
60 px body above `list_item_style`'s separator, 52 px art at (4,4), titles to a 12 px right margin. Track rows of the Songs
family and the queue show no per-row disc (below), so every title starts at x 12. The playing row has a small marker at the
right end instead (`np_row_playing`, below the text column's end: four round bars, a 20x20 wave, `#EEEEEC`, x 278..298 of the
310 px row, centred vertically); its title is 238 px wide (x 12..250) and ellipsises before it.
