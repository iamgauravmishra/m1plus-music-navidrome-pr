# M1+ Pod page layout (the menu and its pages)

Split out of docs/ui.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 8. M1+ Pod page layout (`tools/pod_ui.py`)

The release sheet: Home page 3 with the M1+ Pod icon in its free slot, the menu as the Home instance (no top bar: the
Now Playing row replaces the bars icon, the list starts at y 10 and ends at y 440 (`HOME_PAD`, a little air above the first and below the last row; it scrolls to the last row) and the Settings page it opens.
The menu opened from the grid icon is the same page with its navbar (Back, "M1+ Pod", the bars icon).

Each page is a window with the stock navbar (50 px: `label_title` x 36 y 14 200x22 after the polish step (248 in `pod_ui.py`), `navbar_label_white`,
Back `btn_return` 0,0 80x50, Now Playing `btn_backtoplayer` 260,0 60x50) over a stock-structured
list: `list_view` (`default_item_height` 52, black in every state) > `scroll_view` (310 wide with the
scroll bar, speeds scaled) + `scroll_bar_m` (10 px, max 1000, only when rows overflow 400 px), 52 px
rows built like stock's scrolling rows (`list_item` `list_item_style` holding an `hscroll_label`
`srlabel_leftwhite21_style`, `only_parent_focus`, ellipses, text x 24 -> 64 with the icon; the
`right_arrow` image for rows that navigate, not for Now Playing, Shuffle rows or the switch rows).
**The menu is customisable (`patch/menu.c`).** The asset holds a row for each of eighteen items in the default
order (Now Playing, Cover Flow, Albums, Artists, Songs, Playlists, Shuffle, Genres, Folders, then the Extras tiles Favorites,
Recently Added, Recently Played, Most Played, Composers, Hi-Res, Update Library, Tidal, CD Ripper; the item id is the row
index) followed by Extras and Settings (20 rows); at open the payload hides the rows the saved list leaves out (`visible=false` and
`sensitive=false`, parked at y 0), moves the shown ones to y = position x 52 and sets the list's `virtual_h` and offset
(the Artists list does the same for its rows), so the scrolling height, the hit test, the stock press visuals and the scroll
bar follow the shown rows. Default: the first seven show (Genres and Folders are in Extras); 9 shown rows are 468 px, so the
menu scrolls (400 px visible with the navbar, 450 px on the Home instance); Extras and Settings always show, last. The saved list
is `/mnt/data/m1pod-menu`, the shown item ids in order, one character each (`0`-`8`, then `a`-`i` for the Extras tiles; `0123456` is the default; see `docs/architecture.md`).
**Settings > Screenshot** (the last Settings row, Lucide `camera` as a bare glyph; a developer's tool, not a menu item: it is not on Extras or the Main Menu
page. a saved menu file containing `j`, the old Extras id, is invalid and gives the default menu): a tap starts the 5 s countdown of `docs/modules/screenshot.md`. The **status bar** shows a 16 px
white camera (`pod_bar_shot`) while it runs: the last, right-most icon of the right-aligned group, against the battery outline; the Bluetooth,
SyncLink and Wi-Fi icons shift 20 px left to make room and come back when it is hidden (`test/pod/shot.py` checks the ink stays clear of the
12 h and 24 h clock; the release sheet shows both). The camera widget (`pod_shot`, hidden and insensitive) is in the real bar only: the pull-down's
copy of the bar (`tools/statusbar.py`) has none, and the bar test (assets section 52) skips exactly that one widget. The toasts are the stock message box: "Screenshot in 5 s", "Screenshot saved", "Screenshot failed"
and the existing "Storage unavailable" (16 tables, `tools/pod_i18n.py`).
The **Settings** page (`m1pod_settings`, 6 rows, fits without a bar): Main Menu (opens the customise page), Cover Flow
(its sub-page: the Landscape switch and Sort), Home Screen (its sub-page, `m1pod_homeset`, titled Home Screen: Start in M1+ Pod, a row with the stock on/off switch image, `sset_on` / `sset_off` 57 x 28 at x 251 as the stock
Power and Display pages, whose tap flips it and the image follows, and Shanling Home, which shows the stock grid), Playback (the stock Play settings page), System Settings (kept: it reads as the pair of Playback), Screenshot (last). **Settings > Main Menu**
(`m1pod_mainmenu`, eighteen rows, the stock list, scrolling: the nine menu items then the nine Extras tiles, all selectable): a row per item with the switch (the whole row is the target) and, on the shown
items but the first, an up arrow (the stock chevron-up art, `expansion_2`, on an insensitive button 50 px wide, left of the switch: a picture; the row
takes every tap and a tap that begins on the arrow's rectangle, x 191..240 of the row, moves the item one place up, a tap anywhere else toggles it; the arrow
shows its pressed art while held) that
moves the item one place up; the shown items come first in menu order, the hidden ones below them in the default order, and a
switch shows an item at the end of the menu. Touch reordering by arrows rather than drag-to-reorder: the stock list drags
to scroll, and a press-and-drag reorder needs custom gesture code on a page that must always work; an arrow is a 50 x 52 px
target, and one tap is one saved step. Changes are saved at once and the menu re-arranges itself when it is
in front again. The Extras page (`m1pod_extras`, the same machinery, 18 rows: a row for every item, which the payload
shows only for the items the menu does not show; an item shown in the menu leaves the page; icons as the Home grid's) is in a **fixed order, the same in every language**
(`pod_pages.EXTRAS_ORDER`, by the English labels): the default menu items if the user hid them (Albums, Artists, Cover Flow, Now Playing, Playlists, Shuffle, Songs), then the **Library** group
(Composers, Favorites, Folders, Genres, Hi-Res, Most Played, Recently Added, Recently Played), then the **Tools** group (CD Ripper, Tidal, Update Library), each group alphabetical. With the default menu the page reads
Composers ... Recently Played, CD Ripper, Tidal, Update Library; Genres and Folders have no special place. The payload stacks the rows in that order (`widget_restack`, hidden rows last), so a stock relayout keeps it. There is no separator between the groups: a gap would be a y the stock list layouter does not know, and the next relayout would flatten it. The page lists the stock Home tiles the menu does not repeat, each opened through the Home dispatcher: Favorites, Recently Added, Recently Played, Most Played, Composers, Hi-Res, Update Library, Tidal, CD Ripper (ids 10, 13, 12, 11, 8, 9, 2, 1, 15; Extras itself `dots`; HiFi, id 0, exists only in Simplified Chinese and is left out). The Artists page has its Artist / Album Artist switch in the navbar (`btn_artisttype`, the toggle slot below): the title reads "Artists" or "Album Artists" and the glyph is the other mode's (Tabler `microphone-2` for Artist, `user-star` for Album Artist, 24 px white, pressed `#777777`); the list starts right under the navbar. The artists are listed A to Z in both modes, by the rule of the album Artist order (ASCII case ignored, a leading "The " dropped, so "The Beatles" is under B; "Them" and "Theo" are not stripped; equal names keep the stock order). A name that starts with a non-ASCII byte (CJK, Cyrillic, accented capital, ...) and the "Unknown Artist" row stay where the stock list put them, and only the runs of ASCII-initial names between them are sorted. The page has no section headers or index letters. Names `pod_row0..N`, `pod_listview`, `pod_scrollview`, `scroll_bar_m`.
Everything the page hides starts `visible=false` and `sensitive=false` (`label_status`, `btn_cancel`).
Cover Flow landscape (chosen by Settings > Cover Flow > Landscape; the release sheet's last panel, 480 x 320 as seen): with the
switch on the page opens as a 400 x 320 view in the 320 x 400 body under the navbar (the navbar has no rotate button and its
title has the whole width; the setting is read when the page opens)
landscape view, the content turned 90 degrees clockwise on the screen (the player held turned counter-clockwise): the
carousel along the long side with the same 168 px covers as portrait (no zoom) and more of the neighbours, the album
(22 px white) and artist (18 px grey) captions centred under the reflections (long names cut with an ellipsis, no
scrolling). The status bar and the navbar stay as they are, a portrait strip on the left as the player is held: Back and
Now Playing work in both presentations, and nothing is drawn over the covers.
The choice is remembered like the Albums view's. Details: `docs/modules/coverflow.md`.
Cover Flow's page: `view_covers` 0,89 320x276; captions `label_album` 16,318 288x34
(22 px) and `label_artist` 16,352 288x28 (18 px) as scrolling `hscroll_label`s; block centred in the
400 px under the navbar (art top at y 120, 70 px above it and below the artist line); a progress
`label_status` 10,210 and `btn_cancel` 100,260 120x46 for the first-run build. These must match the
`CF_*` constants in `patch/offsets.inc`. (The page has no track list: an album opens the stock album
page, section 7.)
