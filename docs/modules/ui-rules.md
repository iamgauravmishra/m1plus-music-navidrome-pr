# Rules every UI step follows

- **Preserve names.** Restyle, move or hide named widgets; never rename/delete them.
  `widget_lookup(win, name, TRUE)` is recursive, so reparenting is safe.
- **Hit testing ignores `visible`.** Hide = `visible=false` + `sensitive=false`; decorative overlays
  are `sensitive=false`. This AWTK's `widget_find_target_default` (`0x6747d4`) takes the first child
  (from the top) with enable and sensitive set (`flags & 9 == 9`) that contains the point;
  `widget_on_pointer_down_children` (`0x6714ac`) checks the same two bits. The tools model it
  (`check_touch` in `mod_lockscreen.py` / `mod_nowplaying.py`: centre of every control reaches that
  control, at least 44 px each way, the album page's two buttons 44 px high; the cover reaches the gesture parent) and `test/pod/` runs demo's
  own `widget_find_target` on the built page trees. A button inside an insensitive parent never gets its touch (the hit test
  does not look into it): the keyboard's field `kb_field` is sensitive for its clear button, and a page puts its eye button after
  the field, so over it. A page's test asks the hit test itself, on the page as the payload left it: `touch_misses(m, asset, names)`
  (`test/pod/harness.py`, with `live_tree` and `touch`) lists the controls whose centre does not reach them; a paint order alone
  proves nothing (Sign In and Join Wi-Fi Network shipped with a clear button that took no touch).
- **Trailing controls of a card are one column, and a control with nothing to do is hidden.** The clear button's disc and the eye's
  glyph share a centre (x 287: `tools/pod_ui.py trail_field_w`); the eye shows only while there is typed text behind the dots.
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
- **Text and colour roles** (our pages; names in `tools/pod_ui.py`). Secondary text (sub lines, footers, values, keys, credits, empty-state hints) is `#AAAAAA` (`SUB_RGB`, `HINT_RGB`); the only dimmer line is the album page's 15 px meta line `#9C9C9C`. A field's placeholder is `#8E8E93`. An empty-state hint (`label_status`) is 20 px on one line, 18 px when it wraps. The list chevron is `#8A8A8A`, a row's "..." `#8C8C8C`. The one red (a destructive row's label and glyph) is `#FF6B6B` (`RED_RGB`). A group header on a card page is the Settings pages' 18 px grey (`pod_settings.HDR_PX`).
- **Bottom sheets** (the track rows' menu, the Podcasts and Radio sheets, Now Playing's More sheet's own rows): 50 px rows, a 24 px glyph at x 14, the 18 px label from x 48, the scrim `PL_DIM`. The Albums "..." sort card (48 px rows) and the Playlists menu (20 px glyphs) are floating cards, not sheets.
- **Segmented control.** One painter, `m1_segmented` (`patch/common.c`; constants `SEG_*`, model `tools/pod_show.py segmented`): a fully rounded track (#1C1C1E), the selected segment a fully rounded thumb (#D1D1D6, black label) floating 3 px inside it on every side, the other labels white, a short hairline (#3A3A3C, half the track high) between two unselected segments, none beside the thumb. Neutral (no accent). First user: the Podcasts Discover level's Shows | Episodes ([podcasts](podcasts.md) "Discover").
