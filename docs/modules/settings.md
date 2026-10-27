# Settings pages and the launcher

Split out of docs/architecture.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

### The launcher

The menu's last row opens the **Settings** page (`m1pod_settings`, the Shuffle page's machinery), whose rows are
Main Menu, **Cover Flow** and **Home Screen** (sub-pages, below), Playback and System Settings (stock pages through the dispatcher with ids 16 and 17).

**Settings > Home Screen** (`m1pod_homeset`, `pod_pages.HOMESET_PAGE`, key `Home Screen`, icon `layout-grid`): the **Start in M1+ Pod** switch (row 0, `pod_switch0`) and **Shanling Home** (row 1).

**Settings > Cover Flow** (`m1pod_cfset`, `pod_pages.CFSET_PAGE`): **Landscape** (the switch, `/mnt/data/m1pod-landscape`, as before) and **Sort** (`ACT_SORT`: the row shows its value, `Artist` or `Album`, in a grey right-aligned `pod_value<row>` label set by `widget_set_tr_text` so it follows the language; one tap toggles it, saved first, a failed save changes nothing; no sub-choice page). The setting `/mnt/data/m1pod-cfsort` (`cc_sort_artist`, `cc_sort_toggle` in `patch/covercache.c`): only `0` or `0\n` is Album; a missing, empty or any other content is Artist (the default), and reading never writes.

**Settings > Cover Flow > Rebuild Covers** (`ACT_REBUILD` 15, icon Lucide `image-up` `pod_ic_rebuild`, key `Rebuild Covers`; an action row like Screenshot, with its chevron): a tap runs `rebuild_ask` (`patch/m1pod.c`), which opens the **stock confirm dialog** `dialog/confirminfo_dialog` through `navigator_to_with_context` (the one the equaliser reset `on_eqreset_onclick` `0x49dd6c` and the Bluetooth reconnect use). Its context is the msginfo layout `{kind, ms, text[0x200], text2[0x200]}`: kind 5 is a centred white 20 px **word-wrapped** label (260 x 80 at y 25, `dialog_confirminfo_dialog_init` `0x472cec`, the branch at `0x472e1c`; kind 1, the equaliser's, is a one-line hscroll label that would scroll this long text), the text at +8 is `TR("Rebuild all covers? This may take a few minutes.")` (a key of ours, translated in all 16 tables, at most three lines at 260 px in every language, test). The call is modal and returns `CONFIRM_YES` 0xa for the Yes button (`btn_enter`); anything else (No, `btn_cancel`) does nothing at all. Yes calls `coverflow_rebuild` (`docs/modules/coverflow.md`): Cover Flow on its Preparing screen with every cover extracted again, the no-art markers included; Cancel/Back leave a complete cache. Kind 5 and the dialog's look are inferred from the stock code, not yet seen on the device.

**The album order** (`cc_album_order`). Album = the stock list as it is (`getAllAlbum`: by album title, ASCII case-insensitive). Artist = the row's artist (`songer`, the album's representative track: the album query does not fetch the album artist, so there is no album-artist fallback to apply), then album title, each ASCII case-folded with a leading `The ` dropped (`A `/`An ` are not), ties by the stock position; the Unknown Album row (id -1) is last. The stock deque is never reordered: the page holds `order[]` (stock row numbers, a heapsort, no libc callback; about 25 M instructions for 4000 albums on open) and every access goes through `cc_row`; whatever returns to stock (`cc_open_album`) gets the stock row, `order[i]`. Cover Flow sorts a library of at most `MAX_ALBUMS`; the Albums page (grid and list) uses the same call; the per-artist Cover Flow is not re-sorted (its stock order is album title, `group by album COLLATE NOCASE`, not chronological). Cache keys are unaffected (key = album's artist + title).

**Opening on the playing album** (`find_playing`, once, at open, no polling). `cc_playing()`: `mclGetPlayPos` `0x5d4290` (the position, -1 none) and the play queue, a `deque_t *` in the data word `PLAY_QUEUE` `0xa0394c`; the track is `deque_at(*PLAY_QUEUE, pos)` when `0 <= pos < deque_size` (the same test and accessors as `get_playtimeandlength` `0x4e015c`, the lock screen refresh `0x53f718` and the queue drawer). Its album (`REC_ALBUM`; empty = no match) is matched first by `cc_album_key` (FNV of artist then album), else by album title ignoring ASCII case (a compilation's tracks do not share the album row's artist). Found: that cover is centred (main page, or the artist page when the artist's list has the album); otherwise the saved `LAST_ALBUM`, else the first, as before.
Shanling Home shows the stock grid for the rest of the session (nothing re-opens the pod menu while it is on):
it sets `grid`, shows the grid, closes the menu and the Settings page under the Home Screen page by handle
(`window_close(hs.entry)`, `window_close(hs.menu)`: a second `navigator_back` straight after the first would find
the closing page) and then closes the Home Screen page with `navigator_back`; with no known window below it is one `navigator_back`. Tapping the **M1+ Pod icon**
(id 99) on the grid, when the setting is M1+ Pod and the payload is armed, clears the flag and opens the menu as
the Home instance; a failing open restores the previous state. With the switch off ("Shanling") the icon opens a normal
menu. **Start in M1+ Pod** is a switch row: a tap runs `home_toggle`, which flips the persistent setting (`/mnt/data/m1pod-start`, the
same semantics and the same atomic write as before; it returns the new state or -1 for a failed write, which leaves the file and the switch
alone) and `patch/m1pod.c` sets the row's stock `sset_on` / `sset_off` image (`pod_switchN`, found by name; at open it shows `home_start()`).
The switch rows' click ctx is a small slot (action, image) in `.scratch` filled when the Home Screen page opens (the switch image is the page's own, so the state is
right when it opens and after every toggle; `image_base_set_image` repaints it); `home_menu_opened` records the Settings window for Shanling Home. The boot guard is untouched. Toggling to M1+ Pod takes effect at the next Home foreground event (a
Shanling start is armed, so the foreground handler exists). **The Home instance has no top bar**: the whole
`navigationbar_view` is hidden (`visible=false` and `sensitive=false`) and `pod_listview` moves to y `HOME_PAD` (10) and
resizes to 320x430, its `pod_scrollview` and `scroll_bar_m` keep their widths and take the 430 px height (the
Now Playing row replaces the bars icon; nothing happens if the navbar or the list is not found). The menu
opened from the icon keeps its navbar (Back, "M1+ Pod", the bars icon). No setting file = M1+ Pod.
