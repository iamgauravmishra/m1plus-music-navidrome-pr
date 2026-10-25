# Lock screen 2: iPhone-style, large cover (`look-lock2`, V2.1fK)

**Status: built, not yet hardware-tested.** Asset-only. It stacks on `look-all` (V2.1fA: V2.1eA,
which works on the device, with the Now Playing album fix). The only change is the lock screen.
`full` (V2.1gA, `docs/full.md`) runs the same step last, after the Inter font.

```
python3 -I tools/build.py --variant look-lock2
# -> out/M1Plus-V2.1fK-look-lock2-pod-cover-lockscreen-iconpercent-space-update.bin
venv/bin/python -I tools/preview_lockscreen.py work/mod-look-lock2-.../rootfs/release/assets/default/raw \
    docs/lockscreen2-preview.png "V2.1eA=<look-all tree>/.../ui/screensaver_page.bin,raw=<look-all raw>" \
    "look-lock2=.../ui/screensaver_page.bin" "look-lock2=.../ui/screensaver_page.bin,idle"
```

![lock screen 2 preview](lockscreen2-preview.png)

`docs/lockscreen2-preview.png` has three panels: V2.1eA's lock screen, the new one while something is
queued, and the new one when nothing is queued. It is an approximate PIL mock-up. The cover is a
synthetic picture, and a gradient stands in for the wallpaper, which the app sets at runtime.

## What it looks like

- **top**: the date `Monday, Oct 19` (20 px) over an 88 px `09:41`, both centred. A small battery
  gauge sits top right: the stock icon and its fill, **no percentage**. `--battery none` drops it.
  The status bar's `86%` is a different file (`system_bar.bin`) and is unchanged. The status bar
  does not show on this full-screen page anyway.
- **while something is queued**: an opaque dark card (`#131313`, the stock strip colour, radius 20)
  holds the cover at **254 x 254** with rounded corners (radius 10). Under the cover are the title
  (20 px white) and artist (16 px `#CCCCCC`), both scrolling as before, with play/pause and next to
  their right. The glyphs are the off-white `np_*` of the Now Playing look.
- **nothing queued**: the app hides the card. The page is then the date and clock at the top, the
  wallpaper, and the swipe hint, which is the iPhone lock screen without media. Nothing is left
  behind, because the card is the hidden widget's own background.
- the swipe hint `img_slide` stays where it was (136,448).

| widget | V2.1eA (classic) | look-lock2 (cover) |
|---|---|---|
| `view_timeinfo` | 0,82 320x180 | 0,0 320x116 |
| `dclock_date` | 0,114 320x32, `Y-MM-DD` 24 px | 0,7 320x28, `W, MMM D` 20 px, centred |
| `dclock_time` | 0,0 320x138, `hh:mm` 138 px | 0,28 320x88, `hh:mm` 88 px, centred between date and card |
| `img_battery` + `pgbar_battery` | `86%` text + icon, centred under the date | stock gauge (icon + fill, props reset to stock) at 268,9, top right |
| `view_bottomview` | 0,362 320x66 strip, `#131313` | 23,116 274x322 card, `#131313`, `round_radius` 20 |
| `view_img_icon` | 0,0 66x66 (the 254 px cover drawn at 66) | 10,10 254x254, drawn 1:1, `sensitive=false` |
| `img_ls_artmask` (new) | | 10,10 254x254, image `ls_artmask`: corners in the card colour, radius 10; insensitive |
| `view_scrlabel_title` / `_artist` | 76,10 147x20 / 74,36 149x16 | 10,270 154x24 (20 px white) / 10,294 154x20 (16 px `#CCCCCC`) |
| `btn_play` / `btn_next` | 233,0 36x66 / 279,0 41x66, orange glyphs | 168,266 48x56 / 216,266 48x56, `np_pause`/`np_play`, `np_next` |
| `img_slide`, `img_screensaver`, `app_gesture` | | unchanged |

Files: `ui/screensaver_page.bin` (4038 -> 4144 bytes); `styles/screensaver_page.bin`, the page's
window theme (the `icon` of `btn_imgpause1_style` / `btn_imgplay1_style` now points at `np_pause` /
`np_play`, the pressed state at `*_down`; 3991 -> 4011 bytes); and the new
`images/xx/ls_artmask.png` (1,042 bytes). Every widget keeps its name. The app swaps `btn_play`
between those two style names with `widget_use_style`, so the page theme is the place to change
the glyph. An inline icon would override both states.

## The cover image: where it comes from and how big it is

The question was whether a large cover would be a blown-up thumbnail. It is not. The lock screen
gets the **same 254 px file Now Playing uses**:

- the lock screen's cover loader (`0x53f9b4`, called by the refresh at `0x53f520`) does
  `widget_lookup("view_img_icon")`, then picks a source from the cover-type global at `0x97cad8`.
  Type 2 is `file:///tmp/coverpic.jpg`. Types 3 and 5 are `/tmp/externpic.jpg`. Type 4 is the
  built-in `random_cover0..7` (320x320 PNGs). Types 6 and 7 are `/tmp/hifi_album.jpg` and
  `/tmp/album_tidal.jpg`. Anything else gets `defaultcover`. The loader then does
  `widget_load_image` + `image_base_set_image` + `widget_unload_image`;
- Now Playing's loader (`0x53a6c4`, `img_playcover1`) reads the same files with the same switch;
- `parseplaycover_thd` writes them. It calls `toolsGetAlbumCover(track, "/tmp/coverpic.jpg", 254,
  254)` (`addiu a2/a3, zero, 0xfe` at `0x4df1dc`/`0x4df1e0`). Folder art goes through
  `toolsGetExternCover(..., "/tmp/externpic.jpg", 254, 254)` (`0x4df21c`/`0x4df220`). DLNA and
  AirPlay art is 270 (`0x10e`), and Tidal art is downloaded at 320 and cut to 254;
- the resize helper (`0x5e00bc`) decodes the picture with libjpeg, using DCT pre-scaling for
  pictures over 1024 px. It **fits the picture inside 254 x 254 with the aspect ratio kept** and
  re-encodes it. A picture already no larger than 254 in both directions is copied as-is, never
  upscaled. A downloaded cover in `/mnt/mmc/.downpic/<name>.jpg` is copied with `cp -f`, unresized.

So the 254 x 254 widget shows a square cover pixel for pixel. `scale_auto` on a 254 image in a 254
widget is a straight blit, sharper than the 216 px Now Playing look, which shrinks the same file.
`--cover-size` can set another size. Anything above 254 prints a warning, because it would upscale.
Caveats, all shared with Now Playing:

- embedded art smaller than 254 px stays small in the file, and AWTK scales it up to the widget
  (`scale_auto`). A 200 px cover is therefore soft;
- non-square art is fitted by `scale_auto`, full width or full height, from the top-left. The card
  colour shows on the short side, and the mask rounds only the corners that land on the picture;
- a track without art, with random covers off, shows `defaultcover`, a 66x66 placeholder blown up
  to 254, so blocky. Replacing `defaultcover.png` would affect every page that uses it, so it is
  left alone.

**A payload is not needed for this design**: 254 is already the largest size the app produces, and
the card shows it 1:1. Drawing the cover larger than 254, for example full width at 300-320, would
take a code change, but only a tiny one. Patch the four `0xfe` immediates above, plus the two
`0x10e` ones if wanted, to the new size. That makes `/tmp/coverpic.jpg` and `/tmp/externpic.jpg`
bigger for Now Playing too (decode time and memory grow with the square of the size; Now Playing
would then shrink it more). A second, independent copy for the lock screen alone would need payload
code in `parseplaycover_thd` or in the lock screen's loader.

**Cover instead of the wallpaper**: not possible asset-only. `img_screensaver` gets its image only
once, in the init visitor (`screensaver_default` or `file://` plus the custom picture). The cover is
written only to `view_img_icon`. The nearest asset-only option is to make `view_img_icon` itself
full width (0,0 320x320). That is a 1.26x upscale, so soft, with the text over the picture. It was
not chosen.

## Touch

This AWTK's `widget_find_target` takes the top-most child that has enable and sensitive set and
contains the point. It ignores `visible` (`docs/coverflow.md`). `app_gesture` is the parent of the
whole page, and its `on_event` (`0x5219e0`, vtable `0x975654`) handles the pointer events of its
subtree after its children. It records the down point, grabs, and compares on move and up. That is
why swipes already work over the full-screen wallpaper image and the stock strip. The card keeps
that arrangement:

- `view_img_icon` and the mask are `sensitive=false`, so a touch on the cover lands on
  `view_bottomview` itself. A view has no handler, so the swipe reaches `app_gesture` as it did on
  the stock strip. `mod_lockscreen.py` checks this, the centre of play and next landing on them, and
  their size (48x56) with the same hit-test model as `mod_nowplaying.py`;
- the mask sits right above the cover in the child order, under the labels and buttons. The time
  block (0..116) ends where the card starts (116), and it is the lower sibling anyway;
- nothing queued: the app runs `widget_set_visible(view_bottomview, false)` **and**
  `widget_set_enable(view_bottomview, false)` (`0x53f8d4`..`0x53f8f4`), so the hidden card is
  skipped by the hit test. The whole screen swipes as on the stock page.

## Clock, date, fonts

- 12/24 h: unchanged from the classic layout (`docs/firmware.md` 3b). The lock clock is `hh:mm`,
  always 24 h. The 12/24 h setting only reformats the status bar clock. `--clock-format HH:TT` gives a
  fixed 12 h clock (`05:30 PM`), which does not follow the setting.
- date `W, MMM D`: demo's formatter writes `W` as the full English weekday (`Monday`). With a CN/zh
  UI it writes `星期日`..`星期六`. `MMM` is English only (`Jan`..`Dec`, with September as `Sept`). So a
  Chinese UI shows `星期一, Oct 19`. `--date-format Y-MM-DD` brings back the stock date. The tool
  checks that the widest date (`Wednesday, Sept 30`) clears the battery gauge.
- widths are measured as demo lays text out (the shared `StbText` model in `mod_lockscreen.py`, also
  used by `mod_nowplaying.py`: float32 stb scale, truncated advances, **+1 px after every glyph**).
  The branch summed advances, which undercounts by up to a pixel per glyph. Re-checked after the
  merge: stock font, the widest date (`Wednesday, Sept 00`) at 20 px is 169 px (limit 208, clear of
  the gauge on both sides) and `00:00` at 88 px 189 px (limit 298); with Inter (V2.1gA) 167 and
  204 px. Nothing moved: V2.1fK's screensaver files are the branch's byte for byte.
- fonts: the clock and date are sized from `fonts/default.ttf` **of the tree being built**, read
  when the step runs. In `look-lock2` this step is the last one, so it sees the font any earlier
  step left. That covers a font step such as the planned Inter one, wherever it sits in
  `LOOK_ORDER`. The fit uses the widest digit and the widest weekday and month names, so
  proportional digits still fit. With the stock font, whose digits are tabular, the classic
  layout's output is unchanged: V2.1cLB and V2.1eA rebuild byte-identical. The 88 px clock is a
  maximum. If a font's `00:00` is too wide, the tool shrinks it and says so.
- the cover layout does not depend on what the classic run (the pod-cover base) did to the page. It
  sets every property it relies on absolutely and gives `pgbar_battery` its stock gauge props back.
  The output is the same from the stock page and from each classic variant (checked). Running it
  twice is refused.

## theme1

`theme1` has its own `styles/screensaver_page.bin`, and the window theme of the current asset theme
wins, so under theme1 play/pause keep the stock orange circles. The next glyph is inline in the ui
file, so it is off-white in both themes. Everything else is shared.

## Verification

- `fwtool verify` OK. Two clean builds give the same package, SHA-256 `5b2549dc7681176d40eee4dceb86b7ac6b771ca2f19d1191dbf55427d58607af`
  on the branch (on V2.1eA). After the merge V2.1fK stacks on V2.1fA:
  **`8e825a77d8bb992139dbf57a9b22e4d122fc484b07d63d9d1b26a373b830cd44`**; `fwtool diff` against
  `5b2549dc...` lists only `ui/playing_page.bin` (the album fix)
- `fwtool diff` V2.1eA -> V2.1fK: `ui/screensaver_page.bin`, `styles/screensaver_page.bin`, and
  the added `images/xx/ls_artmask.png`, nothing else (2 directories differ only in listed size).
  rootfs.squashfs is 53,129,216 bytes, the same as V2.1eA (2,609,152 free)
- `venv/bin/python -I test/patch.py work/mod-look-lock2-...`: 128 passed, 0 failed (`demo` and
  the payload are untouched)
- contrast scan (`mod_theme.py --scan`, run by build.py) ok
- after the tool changes, `look-all` still gives V2.1eA `cc86e833...` and
  `lockscreen+icon+percent` still gives V2.1cLB `62f3cb18...`

## Device checklist (not yet hardware-tested)

Fall back to V2.1eA (or V2.1fA) if anything misbehaves. Lock the player and wake it, with music playing:

- **cover**: large, sharp (a cover with real embedded art at least 254 px should show fine detail,
  no blur or blockiness), centred on the card, **rounded corners** without dark or light fringes.
  Also try a track whose art comes from a folder `cover.jpg`. Note what a track without art shows
- **title / artist**: readable, scroll when long, and change with the track
- **play/pause and next**: off-white glyphs, the play/pause glyph swaps, and both work on the first
  tap (they turn grey while pressed)
- **swipe to unlock**: works starting on the cover, on the card's text, on the clock, and on the
  empty wallpaper
- **nothing queued** (after clearing the queue or a fresh boot with nothing played): the card is
  gone, date and clock sit at the top, the wallpaper is clear, and swipe works everywhere,
  including where the card was
- **clock and date**: centred. The clock ticks over each minute, the date reads like
  `Monday, Oct 19`, and the lock clock stays 24 h after switching the 12/24 h setting both ways
- **battery**: the small gauge top right with no number. On the charger it shows the bolt icon
- **custom wallpaper** (Screensaver settings): shows behind everything. Turning "show time" off
  hides date, clock and battery together, and the card still shows
- **rotation 180**: the whole page turns, nothing clipped
- **theme1**: play/pause back to the orange circles, the rest as above
- sleep, wake, a reboot
