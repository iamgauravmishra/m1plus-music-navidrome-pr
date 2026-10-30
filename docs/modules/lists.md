# Library lists (look)

## Library lists (`tools/mod_lists.py`)

The library pages' rows are built by code (`folder_create_tablerow` `0x5331fc`,
`localclass_create_tablerow` `0x5368ac`, `music_create_tablerow` `0x528560`, the jump list's cloned
template row `0x5f0b54`, `album_listitem_layout` `0x524228`, `albumdeinfo_listitem_layout` `0x526394`,
`playlist_*item_layout` `0x53e064..`, the search handlers), so geometry is code (section 7); an asset
can change what the style names resolve to. `mod_lists.py` writes page themes (`styles/folder_page`,
`localclass_page`, `allmusic_page`, `playerjumpinfo_page`, `playlist_page`, `search_page`, for default and
theme1, each **derived at build time from the tree's own `default.bin`** so the lists follow the theme):
`btn_tablerow_style` = list_item colours per state; `srlabel_item_white/gold20` at 21 px;
`srlabel_item_gray26_style` defined (stock creates the artist line with a name no theme defined, so it
drew `#444444` on `#131313` until data loaded); Import/Export tiles in the list colours; Search tabs on the row
colour with `#AAAAAA` labels and the active tab white over a 3 px accent underline; the Songs index
letter `view_letter` a `#262626` rounded square (radius 14, `#3A3A3A` edge) with a white letter;
`batchadd_dialog`, `confirminfo_dialog`, `sortselect_dialog` pressed in the list colour. Left out:
page slide transitions (loop hazard, section 8), row geometry (code), the confirm dialog's two-row
layout (its `confirminfo_bg` image draws the divider).
