# Lock screen

## Lock screen (`tools/mod_lockscreen.py`)

`ui/screensaver_page.bin` (fullscreen 320x480), page theme `styles/screensaver_page.bin`, the three
`screens_*` battery images, `screens_rightslide.png`, and four words of `demo`.
What the app touches by name: `img_screensaver` (wallpaper), `view_timeinfo` (shown/hidden by the "show
time" setting), `app_gesture` (swipe), `btn_play`, `btn_next`, `img_battery` (image set to
`screens_battery`/`screens_charge`/`screens_lowbattery`, refresh `0x53f520`, names at
`0x53f5f0..0x53f694` only), `pgbar_battery`, `view_bottomview` (hidden **and disabled** when nothing is
queued, `0x53f8d4..0x53f8f4`), `view_scrlabel_title/artist`, `view_img_icon`. Nothing looks up
`dclock_time`/`dclock_date`. Every property is set absolutely, so the layout does not depend on earlier
edits; applying it twice is refused. Digit_clock format tokens (demo's formatter): `Y YY M MM MMM D DD`
(MMM English only, September `Sept`), `w`, `W` (full English weekday; Chinese UI `星期日..`), `h hh H HH`
(HH = 01..12), `m mm s ss`, `T`, `TT` (minute + " AM"/" PM"); the lock clock is always `hh:mm`
24 h whatever the setting (the 12/24 h setting only reformats the status bar clock).

Layout, top to bottom (window y): date `W, MMM D` 20 px, ink top 12 (box from `text_box`); the 68 px
`hh:mm` clock centred (fitted to the widest digit, 159 px wide in Inter); a **glass card** at
16,108 288x334 (the image `lk_card`, see Glass card) holding the **square 264x264 cover** at 12,12 (no mask), title
(20 px white) and artist (16 px `#DDDDDD`) at 12,282 / 12,306 (164 wide), play and next at 180,278 /
228,278 (48x56, off-white `np_*` glyphs via the page theme's `btn_imgplay1/pause1_style`); the swipe hint
`img_slide` 31x14 (65 %) at 144,452; a small gauge on the date line at 274,12 (34x12 `LOCK` art; fill
`pgbar_battery` 286,15 16x6). With nothing queued the card is the hidden widget's own background, so
the page is date, clock and gauge on the wallpaper and the whole screen swipes. `screens_rightslide` is replaced (premultiplied Lanczos).
The stock battery props are restored on `pgbar_battery` (no text readout).

- **Glass card.** The card (`view_bottomview`) has `bg_image` `lk_card` and a transparent `bg_color` in every state, no radius of its own: the same
  pane as the Home mini player bar (`docs/modules/minibar.md`, `mod_icons.py glass_image(288, 334, 18, fill=GLASS_CARD_FILL)`: dark vertical gradient
  `#2A2A2C` to `#1E1E20`, alpha 0.76 (the bar: 0.82; a little more see-through because only the 12 px frame and the text band show around the opaque
  cover), 1 px rim light 30 % at the top to 8 % at the bottom, a faint inner highlight line). Committed as `assets/icons/png/lk_card.png` (2.5 KB) and
  installed by `mod_nowplaying` with the `np_*` images. Drawn 1:1 by `canvas_draw_image_ex` (proved for the bar by `test/awtk_fill.py`), so the decoded
  bitmap is 288 x 334 x 4 = 384,768 bytes in RAM. A 9-patch was not used: `canvas_draw_image_patch9` exists in demo (`0x647d20`) but no stock style
  in this tree selects it (nothing pins the `bg_image_draw_type` value), and a stretched middle would smear the gradient and rim. Contrast over a pure
  white wallpaper (the worst case): white title and `#DDDDDD` artist checked by `test/pod/assets.py` (>= 7:1 and >= 4.5:1 over every pixel of their
  boxes, over white and over black). **Baked blur: not feasible.** The wallpaper is only the default (`screensaver_default`, `docs/modules/wallpaper.md`);
  the user can pick any picture (`SCREENSAVERPATH` = `file://` path), and the card sits on whatever it is, so a blur baked at build time would only match the
  default wallpaper. Blurring live needs payload code (as the bar's backdrop blur, `minibar.md`), which the boot-path rules keep off this page.
- **Translucency works** (the flat `bg_color` fill the card had before the glass image; still how the fill API behaves). `bg_color` with alpha: `widget_fill_rect` (`0x66b170`) reads `bg_color` and
  `round_radius` and calls `canvas_fill_rect`, or `canvas_fill_rounded_rect_gradient_ex` (the
  `0x64d028` code) with a radius; the low-level fill dispatches per pixel format (`soft_fill_rect`
  `0x681440`, e.g. `0x6cfc84` sends alpha >= 0xf9 to a plain fill and less to a per-pixel blend).
  `test/awtk_fill.py` runs demo's own code on a bgr565 framebuffer: inside pixels are the blend within
  one 565 step, outside untouched, anti-aliased edge, no seams. AWTK repaints a dirty region from the
  window down, so a scrolling title or a clock tick re-blends over fresh wallpaper and never stacks.
- **Why the cover is square.** A corner mask paints one fixed colour, wrong over a translucent card on
  any wallpaper; image clipping does not exist (the image paint `0x62d494` is `widget_paint_helper`
  plus `canvas_draw_image_ex` into the widget rect, canvas clip is a rectangle, `round_radius` rounds
  only the background; only `draw_type icon` can transform), so rounding the picture would need payload
  code. The card itself is rounded and the square cover sits 12 px inside, clear of the arcs.
  Contrast over the worst wallpaper (pure white): see Glass card.
- **Touch.** `app_gesture` is the parent of the whole page; its `on_event` (`0x5219e0`, vtable
  `0x975654`) records the down point, grabs and compares on move and up. `view_img_icon` is
  insensitive, so a touch on the cover, the card or its text lands on `view_bottomview` (a view with no
  handler) and a swipe unlocks; play/next are 48x56 and hit at their centre; `check_touch` verifies this.
- **The cover size is a demo constant.** demo writes `/tmp/coverpic.jpg` / `/tmp/externpic.jpg` with
  `toolsGetAlbumCover` / `toolsGetExternCover(track, dst, w, h)` in `parseplaycover_thd` (`0x4ded84`):
  fitted inside w x h, aspect kept, never upscaled, JPEG q90, per new track (the thread polls a start
  flag every 100 ms and skips an unchanged path). The four `addiu a3/a2, zero, 0xfe` at `0x4df1dc`,
  `0x4df1e0`, `0x4df21c`, `0x4df220` become `0x108` (264); `patch_cover_src` pins the 23 stock words
  `0x4df1d4..0x4df22c` and the GOT slots (`0x9ff74c` -> `0x5eaee0`, `0x9ff750` -> `0x5eafec`) and refuses
  otherwise. AWTK draws a smaller picture at the widget size by nearest neighbour, hence the 1:1 264 (the lock
  card's cover and Now Playing's `img_playcover` are both 264: `mod_nowplaying` asserts the sizes agree).
  Cost: 1.08x output pixels (about 209 KB instead of 194 KB RGB while encoding). Other readers of the
  files (resampled by nearest neighbour, as before): `bigcover_page` (320; it has a 320 px picture of its own since [bigcover](bigcover.md), stock's 264 px one stays underneath), the Home strip (66), the
  Now Playing (254), the remote-control replies (check
  `stat().st_size < 0x16801` = 92,161 bytes; 264 px files are about 1.08x the 254 ones; a larger file means the phone shows no cover). Unchanged: `.downpic` art
  (`cp -f`), DLNA/AirPlay 270 (`0x10e`), HiFi/Tidal 254 (`0x4df348`, `0x4df424`). Cover source types
  (loader `0x53f9b4`, global `0x97cad8`): 2 = `/tmp/coverpic.jpg`, 3 and 5 = `/tmp/externpic.jpg`, 4 =
  `random_cover0..7` (320x320 PNG), 6/7 = `/tmp/hifi_album.jpg` / `/tmp/album_tidal.jpg`, else
  `defaultcover` (a 66x66 placeholder blown up, blocky; left alone because other pages use it).
- **Not possible asset-only:** the cover instead of the wallpaper (`img_screensaver` gets its image once,
  in the init visitor).
