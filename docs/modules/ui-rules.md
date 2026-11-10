# Rules every UI step follows

- **Preserve names.** Restyle, move or hide named widgets; never rename/delete them.
  `widget_lookup(win, name, TRUE)` is recursive, so reparenting is safe.
- **Hit testing ignores `visible`.** Hide = `visible=false` + `sensitive=false`; decorative overlays
  are `sensitive=false`. This AWTK's `widget_find_target_default` (`0x6747d4`) takes the first child
  (from the top) with enable and sensitive set (`flags & 9 == 9`) that contains the point;
  `widget_on_pointer_down_children` (`0x6714ac`) checks the same two bits. The tools model it
  (`check_touch` in `mod_lockscreen.py` / `mod_nowplaying.py`: centre of every control reaches that
  control, at least 44 px each way, the album page's two buttons 44 px high; the cover reaches the gesture parent) and `test/pod/` runs demo's
  own `widget_find_target` on the built page trees.
- **Normal windows are 450 px tall** (under the 30 px `system_bar`); only fullscreen windows
  (`screensaver_page`) get 480. 68 stock pages end exactly at y = 450 (`systemset/sysset_page.bin`:
  navbar 0-50, list 50-450). Lists use the stock structure `list_view` > `scroll_view` +
  `scroll_bar_m` with stock `list_item` rows (`list_item_style`, an `hscroll_label` themed
  `srlabel_leftwhite21_style`, the `right_arrow` image, a 13 px widget at x 285 so its ink is the shared list chevron at x 288..298; the text ends at 278 and the hairline at 310); bare `list_item`s fall to the light default
  theme (white on white).
- **Window theme first.** A widget's style is resolved in its window's theme (`styles/<window name>.bin`,
  or its `theme` property) before `styles/default.bin` (`style_const` `0x6d3038`,
  `widget_get_window_theme` `0x66ab78`, `window_base` `0x6761dc`; lookup is a linear scan of 100-byte
  items). Page-local styles change one page only.
- **Text width = truncated glyph advance + 1 px per glyph** (below); use `StbText`
  (`tools/awtk_text.py`) and measure the font of the tree being built.
- **No close animation on windows a "play from here" loop can pop:** library pages, album detail,
  jump list, Now Playing and M1+ Music pages. See [slides audit](boot.md#settings-slide-safety-audit-static-on-stock-demo).
- The rebuilt rootfs must not exceed stock (fwtool enforces it); one change per package where possible.
- **The Pod is its own view:** every Pod row opens a Pod level, never one of our full pages; a function without a Pod-designed level is left out of the Pod (`docs/modules/ipod.md`).
- **Segmented control.** One painter, `m1_segmented` (`patch/common.c`; constants `SEG_*`, model `tools/pod_show.py segmented`): a fully rounded track (#1C1C1E), the selected segment a fully rounded thumb (#D1D1D6, black label) floating 3 px inside it on every side, the other labels white, a short hairline (#3A3A3C, half the track high) between two unselected segments, none beside the thumb. Neutral (no accent). First user: the Podcasts Discover level's Shows | Episodes ([podcasts](podcasts.md) "Discover").
