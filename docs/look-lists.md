# Look: iPod-style library lists (`look-lists`, V2.1eL)

An asset-only restyle of the library pages and the dialogs they open, so that every list looks
like the M1 Pod menu (black page, `list_item_style` tiles, white left-aligned titles, grey secondary
text, the stock right chevron, one pressed colour), after q2-pod's iPod list pages (MIT, see
`NOTICE`). It stacks on the device build `pod-cover` (V2.1dE): `build.py --variant look-lists`.
No code changes: `demo`, the M1 Pod payload and every other binary are byte-identical to V2.1dE.

Preview (approximate PIL, stock above, this mod below): `docs/look-lists-preview.png`, and the same
under the System > Theme option theme1: `docs/look-lists-preview-theme1.png`
(`tools/preview_lists.py STOCK_WORKDIR MOD_WORKDIR OUT.png [--theme theme1]`).

## What the pages are made of

The pages, by window name (the Home ids that open them are in `docs/payload.md`):

| page | rows built by | row widgets and styles |
|---|---|---|
| `folder_page` (Folders) | `folder_create_tablerow` @0x5331fc | table_row 310x64 `table_row_style` > button 310x60 `btn_tablerow_style`, layout `default(r=1,c=0,x=12,s=8)`: `img_choice` 26, `img_icon` 40, `scrlabel_name` 200 `srlabel_item_white_style` (playing: `srlabel_item_gold20_style`), `btn_right` 13 `btn_rightarrow_style` |
| `localclass_page` (Artists, Genres, Composers) | `localclass_create_tablerow` @0x5368ac | the same in 310x60 / 310x56 |
| `allmusic_page` (Songs, Hi-Res, Favourites, Recent, ...) | `music_create_tablerow` @0x528560 | 310x60 / 310x56; two lines: name (0,10,200,20) white/gold20, artist (0,30,175,26) created `srlabel_item_gray26_style`, then gray18/gold18 |
| `playerjumpinfo_page` (Now Playing's jump list) | the asset's template row, cloned by `table_client_ensure_children` @0x5f0b54 | as Songs |
| `album_page`, `albuminfo_page`, `playlist_page`, `search_page` | `album_listitem_layout` @0x524228, `albumdeinfo_listitem_layout` @0x526394, `playlist_*item_layout` @0x53e064.., search handlers | `list_item_create(..., 60)` themed `list_item_style` (header: `list_item_notpress_style`), 60 px covers, 20 px label boxes |

Every navbar is rebuilt by code too (`widget_destroy_children(navigationbar_view)`, then Back at
0,0 80x50, the title `srlabel_leftwhite22_style` at 36,14 153x22, Search 178, multi-select 224, Now
Playing 270), which is already the M1 Pod navbar's layout (left title at x 36, 22 px).

So **geometry is code** on these pages: row pitch, tile height, icon, label boxes, chevron.
`table_client` moves each row to its asset `row_height`, but the code's 60/56 px buttons inside do
not follow, and covers/offsets are computed by code. What an asset can change is what the style
names resolve to — and on the stock theme they already resolve to the M1 Pod look: `btn_tablerow_style`
is `list_item_style`'s colours (`#131313` tile, `#362221` pressed) and the 4 px gap under each
button is `list_item_style`'s 4 px black separator.

## How a page gets its own styles

This AWTK resolves a widget's style in its **window's theme first, then the global theme**
(`style_const` @0x6d3038 calls `widget_get_window_theme` @0x66ab78 and `theme_find_style` on the
window theme, then on `default_theme_obj`, per state; a missing state falls back to `normal`), and
a window's theme is the style asset named by its `theme` property **or its own name**
(`window_base` @0x6761dc: `assets_manager_ref(am, ASSET_TYPE_STYLE, theme ?: name)` +
`theme_load_from_data`). That is why stock ships `styles/localclass_page.bin`,
`styles/search_page.bin` and others. The lookup is a linear scan of 100-byte items (@0x662100), so
item order is free; `style_data_get_int` accepts value types 6 and 7, `get_uint`/colours only 7.

`tools/mod_lists.py` writes such page themes, **derived at build time from the tree's
`styles/default.bin`** (owned by the theme mod: build this mod after it and the lists follow its
colours), for both asset themes (`default` and `theme1`, each from its own `default.bin`; a theme
without its own page file starts from default's, which is what it used before).

## Changes, file by file

All under `release/assets/<theme>/raw/`. Every ui edit keeps every widget's type, name and geometry
(the mod asserts it); no window or widget the app looks up is touched beyond its style.

| file | change |
|---|---|
| `styles/folder_page.bin` (new) | `btn_tablerow_style` (5 states) = default's with `list_item_style`'s bg per state; `srlabel_item_white_style`, `srlabel_item_gold20_style` at **21 px** (label box 60 px) |
| `styles/localclass_page.bin` | the same added to the stock entries (artist-switch button styles kept) |
| `styles/allmusic_page.bin` (new) | `btn_tablerow_style` as above; **`srlabel_item_gray26_style` defined** (copy of gray18: `#AAAAAA` 18 px). Stock creates the artist line with that name, which no theme defines, so it drew `#444444` on `#131313` until the row's data loaded |
| `styles/playerjumpinfo_page.bin` (new) | as Songs |
| `styles/playlist_page.bin` | `playlist_btnitem_style` (Import/Export tiles): `list_item_style` colours (stock pressed olive `#2E2A19`) |
| `styles/search_page.bin` | `btn_tab_style`: tabs on the row colour with grey (`#AAAAAA`) labels; the active tab white over a **3 px accent underline** (stock: a solid accent block, `#FE7E40`; theme1 `#FA7268`); pressed in the list pressed colour |
| `theme1/raw/styles/*` | the six page themes again, from theme1's `default.bin` (its pressed `#2E2019`, accent `#FA7268`) |
| `ui/allmusic_page.bin` | `view_letter` (the index letter shown while flicking): a `#262626` rounded square (radius 14, 1 px `#3A3A3A` edge) with a white letter, instead of the light-grey `letter_back` disc with a black one |
| `ui/dialog/batchadd_dialog.bin` | Add to playlist / Favourites press in the list pressed colour (stock olive `#2E2A19`) |
| `ui/dialog/confirminfo_dialog.bin`, `ui/dialog/sortselect_dialog.bin` | pressed = the list pressed colour. Stock already uses `#362221` there, so on the stock theme these files come out byte-identical; they change only if the theme's `list_item_style` does |

Title size: 21 px only where the label box is taller than the text (Folders, Artists: 56-60 px
boxes). The two-line rows (Songs, Albums, Album, Search, Playlists) keep 20 px in their 20 px boxes.

## Left out, and why

- **Page slide transitions.** q2-pod gives its pages `htranslate`; here no window gets an
  `anim_hint`. The "play from here" handlers pop windows in a loop until Now Playing or Home is on
  top — Album detail @0x5258d4..0x5259d0 (`window_manager_get_top_window`, `window_close`, else
  `navigator_back` and loop) and the jump list @0x538cbc — and with a close animation the top window
  stays put until the animation ends in the main loop, so the loop would spin (a hang, then a
  watchdog reboot). q2-pod hit exactly this and patched the handlers to `navigator_close`; that is
  code, so out of scope for an asset mod. (The animators themselves are built in:
  `window_animator_register_builtins` registers htranslate, slide_left, ...)
- **Volume dialog highlight.** q2-pod deletes `highlight="default(alpha=200)"` so nothing dims;
  the M1 Plus already ships `default(alpha=0)`, so there is no dimming to remove.
- **Confirm dialog as two full-width rows** (q2-pod): the M1 Plus dialog is a 260x180 box whose
  `confirminfo_bg` image draws the divider for its two 128x48 buttons; re-laying it would fight the
  image. Only the pressed colour follows the list.
- **Row geometry, q2-pod's 52 px art with an 8 px inset**, the 40 px coloured icon discs, a centred
  title: all set by code (above). The stock 60/64 px rows are already above the 44 px touch floor.
- **Pull-down / status bar** (`dropdown_dialog`, `system_bar`): the theme mod's.
- **Images** (`icon_folder`, `right_arrow`, ...): shared with other pages; untouched.

## Cost

Rootfs (squashfs, with V2.1dE underneath): 53,149,696 -> 53,153,792 bytes, **+4,096** (one block);
17.9 KB of files uncompressed (six new page themes for default and theme1, three grown ones,
`allmusic_page.bin` +145 bytes).

## Verification

- `python3 -I tools/build.py --variant look-lists` -> `out/M1Plus-V2.1eL-look-lists-pod-cover-lockscreen-iconpercent-space-update.bin`;
  two clean builds are byte-identical; `fwtool verify` OK.
- `fwtool diff` against V2.1dE lists only the files in the table above (plus directory sizes);
  against stock it adds the V2.1dE files (`demo`, `m1pod_*`, status bar, lock screen, removals).
- `venv/bin/python -I test/patch.py work/mod-look-lists-pod-cover-lockscreen-iconpercent-space`: 128 passed (M1 Pod pages unaffected).
- `mod_lists.py` asserts byte-exact round trips of every style and ui file it reads, that every
  ui widget keeps type/name/geometry, and the stock values it replaces.

## Device checklist (not yet hardware-tested)

- Folders, Artists, Genres, Composers: rows look as before but titles are a touch larger (21 px);
  pressing a row shows the dark brown pressed tile; the playing folder is still in the accent colour.
- Songs (and Hi-Res, Favourites, Recently played): flick the list fast: the index letter is a dark
  rounded square with a white letter. Artist lines are grey from the first frame.
- Search: the active tab is white with an accent line under it, the others grey; tapping switches.
- Playlists: Import/Export tiles press in the same colour as the rows.
- Add to playlist / delete confirm / sort dialogs open and work; pressed colour as the rows.
- System > Theme -> theme1: the same pages keep theme1's accent (coral) and pressed colour.
- Album, Album detail: unchanged (they already use `list_item_style`).
- The M1 Pod menu, Cover Flow and Now Playing behave as on V2.1dE.
