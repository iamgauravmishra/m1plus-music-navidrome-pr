# Look: Minimal theme, icon sets and status bar (`look-theme`, V2.1eT)

An asset-only global look for the M1 Plus, after q2-pod's **Theme: Minimal** (`docs/ipod.md` in
q2-pod): black surfaces, white titles, grey secondary text, neutral pressed feedback and no colour
accent, so the stock pages match the M1 Pod menu and Cover Flow pages. It is built on top of the
current device build `pod-cover` (V2.1dE: lock screen + icon+percent + space + M1 Pod + Cover Flow).

```
python3 -I tools/build.py --variant look-theme
# -> out/M1Plus-V2.1eT-look-theme-pod-cover-lockscreen-iconpercent-space-update.bin
venv/bin/python -I tools/mod_theme.py SRC_WORKDIR OUT_WORKDIR [--audit]      # the mod alone
venv/bin/python -I tools/preview_theme.py BASE_WORKDIR MOD_WORKDIR out.png    # PIL mock-up
venv/bin/python -I tools/awtk_style.py dump .../styles/default.bin [STYLE...] # theme reader
```

![V2.1dE vs V2.1eT](look-theme-preview.png)

`docs/look-theme-preview.png` is a PIL mock-up drawn from each tree's own theme, layouts and
images (not AWTK; fonts follow AWTK's size rule, layouts are simplified). Top: V2.1dE (stock
theme); bottom: this mod.

No code changes: `demo`, the payload and every binary are byte-identical to V2.1dE. `fwtool diff`
against V2.1dE lists exactly the 58 files below (55 images, `styles/default.bin`,
`ui/system_bar.bin`, `ui/home_page.bin`); against stock it adds only V2.1dE's own files.
Rootfs cost: **20,480 bytes** (53,149,696 -> 53,170,176). SHA-256 of the package:
`6f921f4fa1f5db6fe2f9f0b3cc4a91fe729edfd4a93bfebe0154740a92326b7c` (two clean builds identical).

## The theme file format (`tools/awtk_style.py`)

`styles/*.bin` is AWTK's compiled theme: a 12-byte header (`fd fc fb fa` magic, version 0, item
count), then one 100-byte item per (state, style name, widget type) with the file offset of its
property block, then the blocks back to back. A block is a count and properties of
`{u8 type, u8 key size, u16 value size, key\0, value}`; types are 6 int32, 7 uint32 (colours are
uint32 r,g,b,a bytes, shown as `#RRGGBBAA`), 14 string. All 18 stock `styles/*.bin` (default and
theme1) round-trip byte-exact; `serialize` re-lays the blocks, so values may change size and
properties may be added. A widget's `style="foo"` in state `pressed` is looked up as
(its widget type, `foo`, `pressed`); `default` is the style of widgets without one.

The stock app ships two themes: `assets/default` (accent orange `#FE7E40`) and `assets/theme1`
(accent salmon `#FA7268`), picked by System settings -> Theme. They differ only in the accent and
the pressed tint. **This mod edits the default theme only**: choosing the second theme gives back
the stock look (its own `styles/default.bin` and status icons are untouched; it has no settings
icons of its own, so those stay grey there).

## Palette

| role | colour | stock | source |
|---|---|---|---|
| row surface | `#000000` | `#131313` cards | q2-pod Minimal: no list fill |
| row hairline | `#222222`, 1 px, bottom | 4 px black gap | |
| pressed row / key | `#333333` | `#362221` (default), `#2E2A1A` (theme1) | q2-pod pinned edit `s_btn_listitem` |
| title text | `#FFFFFF` | same | |
| former accent text | `#FFFFFF` | `#FE7E40` / `#FA7268` | q2-pod `s_scrlabel_red*` -> white |
| muted partner text | `#8C8C8C` | `#FFFFFF` | q2-pod `SUDO_MUTED` |
| secondary text | `#AAAAAA` (unchanged) | same | stock, as the M1 Pod pages |
| settings icon disc | `#777777`, white glyph | coloured discs | q2-pod `MINIMAL_CHEVRON` |
| status glyph on / off | `#FFFFFF` / `#666666` | white / grey | q2-pod `status_icon` |
| Home page dots | `#EEEEEE` / `#555555` | `#FFFFFF` / `#666666` | q2-pod Now Playing dots |

Kept on purpose: the red error text (`msg_centerred18_style`), the green/red battery
charging/low icons, the red `icon_playing` disc that marks the playing row, the orange on/off
toggle images (`sset_on`, `pset_high`, ...: state, not decoration), and every AWTK light default
style (`window`, `dialog`, `list_view`, `label`, `button` "default"): stock pages set their dark
colours inline, and a global change of those defaults is how white-on-white happens.

## Styles changed in `styles/default.bin`

Every edit is pinned: the file's stock SHA-256, and per edit the old value and how many states hold
it (`STYLE_EDITS` in `tools/mod_theme.py`); the build stops if anything differs.

| style (widget type) | change | used by |
|---|---|---|
| `list_item_style` (list_item) | bg `#131313` -> `#000000` (4 states), pressed `#362221` -> `#333333`, border `#000000` 4 px -> `#222222` 1 px | 29 pages: cdripper_page, dialog/playqueue_dialog, **m1pod_menu**, playset/{filter,memplay,playmode,replaygain}_page, systemset/{about,atmosphereled,dsdmode,fwupdate,keylock,lighttime,netservice,powermanager,reset,rippingset,screenrotate,screensaver,synclink,theme,typedatetime,updatemusic,usbset,usbvolmode,wifiset}_page, tidal/{sortmode_dialog,tidal_description_page,tidal_userlogout}; also the M1 Pod / Cover Flow rows built from it |
| `list_item_notpress_style` (list_item) | bg `#131313` -> `#000000` (5), border as above | dialog/{change_trackinfo,changealbum_dialog,kbaddnet_dialog,kbpassword_dialog,searchalbum_dialog}, hifi/{serach,userlogin}_page, search_page; code: albuminfo rows, BT device rows, Tidal lists |
| `list_itemsort_style` (list_item) | pressed `#362221` -> `#333333`, border `#333333` -> `#222222` | dialog/sortselect_dialog |
| `btn_tablerow_style` (button) | bg `#131313` -> `#000000` (4), pressed -> `#333333`, border `#00000000` -> `#222222` + new `border`=8 (bottom), `border_width`=1 | allmusic_page, dialog/playqueue_dialog, playerjumpinfo_page; code: the All Songs, Folders, Artists/Albums-class and specified-folder table rows (`music_/folder_/localclass_/specfolder_create_tablerow`) |
| `kb_btn1_style`, `kb_btn2_style` (button) | pressed `#362221` -> `#333333` | kb_ascii_t9, kb_default_t9 |
| `srlabel_item_gold18_style`, `srlabel_item_gold20_style` (hscroll_label) | `#FE7E40` -> `#FFFFFF` | code only: the playing row's title in album / album info / folder / song lists (next to `icon_playing`), AirPlay, online search |
| `label_centergold22_style` (label) | `#FE7E40` -> `#FFFFFF` | systemset/wifitransport_page (the URL) |
| `text_gold22_style` (text_selector) | highlight `#FE7E40` -> `#FFFFFF` (other values stay `#AAAAAA`) | systemset/datetime_page, systemset/powermanager_page |
| `btn_selcolor_style` / `btn_unselcolor_style` (button) | selected `#FE7E40`/`#FA7268` -> `#FFFFFF`; unselected `#FFFFFF` -> `#8C8C8C` | onlinesearch_page (cover/lyric tab); code: localclass_page tabs |
| `navbar_lyric_style` / `navbar_sellyric_style` (label) | `#FE7E40` -> `#FFFFFF`; `#FFFFFF` -> `#8C8C8C` | code: playerjumpinfo_page |
| `listitem_sellyric_style` / `listitem_lyric_style` (list_item) | current line `#FE7E40` -> `#FFFFFF`; other lines `#FFFFFF` -> `#8C8C8C` | code: the lyric list |

Where the accent marked one item against white partners (the current lyric line, the selected
tab), the accent becomes white and the partner style becomes muted grey, so the selection still
reads; where the accent stood alone it becomes white. The playing row keeps its red
`icon_playing` disc, which is why q2-pod could do the same for its red playing titles.

## Contrast checks (run on every build)

- **Rows** (`audit()`): every state of the four row styles against every label style a row can
  hold (all `hscroll_label`/`label` styles except the navbar's). No row surface may be light
  (luminance < 0.05); worst text contrast must be >= 4.5:1 at rest and when pressed. Result:
  rest 9.04:1 (stock 8.00), pressed 5.44:1 (stock 6.42), both `#AAAAAA` grey text; white text is
  21:1 at rest and 12.6:1 pressed.
- **Pages** (`page_audit()`): every text-drawing widget of every `ui/*.bin` (M1 Pod pages
  included), normal and pressed-row states, text against the nearest opaque background up its
  ancestors, stock theme vs mod theme. The build fails if any pair falls below 4.5:1 and got worse.
  Result: none.

## Icons

**Settings icons** (46 files, 40x40 8-bit RGBA, only named by demo's settings code: `sset_*`,
`pset_*`, `system_*`, `usb_chargeswitch`, `playset_foldercover`, `screensaver_info`,
`screensaver_timeshow`; each pinned by stock SHA-256). The coloured disc becomes `#777777` with the
white glyph kept, by q2-pod's Minimal rule (its `ringnav_image_add`, which does this at load time
on the Q2): a pixel's saturation against the icon's most saturated one decides how far it blends
from the disc grey to white; alpha is kept bit for bit (checked). The four icons whose disc is
already grey (`pset_eq`, `pset_dsdoutput`, `sset_dsdoutput`, `sset_theme`) are re-levelled so their
disc lands on the same grey. Size, mode and dimensions are unchanged; PNGs are written by Pillow
without metadata (deterministic). Not touched: the 57x28 toggles, the 66x66 Home icons, `usb_dac`
/ `usb_storage` pictures.

**Status icons** (`bar_play`, `bar_pause`, `bar_wifi0..4`, `bar_bt`, `bar_btcon`): redrawn at 4x
and downsampled, as q2-pod's `status_icon` does with ImageMagick: one stroke weight, round caps,
Wi-Fi arcs concentric round the dot (lit per level 0..4, unlit `#666666`), the Bluetooth rune at
the right end of its 47 px canvas like stock (the codec badges `bar_aac/aptx/ldac/sbc` keep their
stock art and share that canvas). Canvas sizes are stock (14x18, 24x16, 47x20). The battery icons
are stock (`img_battery` semantics: the app swaps `bar_power` / `bar_charge` / `bar_lowpower`).

q2-pod's `menu_coverflow` Home icon was not added: the M1 Pod entry is the Tidal icon, whose label
the app sets to "TIDAL" by name; a new picture over that label would confuse more than help.

## Status bar (`ui/system_bar.bin`)

Stacks on `mod_battery.py --variant icon+percent` (the tool refuses any other layout): the
percentage is still `pgbar_battery` with `show_text` and `%d%%`, `img_battery` is untouched.

| widget | V2.1dE | V2.1eT |
|---|---|---|
| `view_bar_left` | `x=14,s=4` | `x=10,s=4`: 10 px edge, as the battery icon's right margin |
| `label_volume` | 20 px, `text_align_v none` | 16 px, middle (all three states) |
| `bar_dclock` | 108,0 90 wide, 20 px | 104,0 90 wide, 18 px |
| `pgbar_battery` | 252,0 40x30, 15 px | same slot, 16 px ("100%" is 35 px) |
| `view_bar_right` | `s=5` | `s=4` |

The volume number and the percentage now share one 16 px size. The clock was offset left in stock
(centre 153) to leave room for the right-hand icons; at 18 px and centre 149 a 12 h `12:59 PM`
(66 px) spans 116..182 and clears the Bluetooth rune (its ink starts at 188 with SyncLink, Wi-Fi
and Bluetooth all shown, and the left group ends at 108 with every icon shown), which the stock
20 px clock (73 px wide) overlapped. All widgets keep their names; the app re-shows the icons and
sets their images and text every second but never their geometry.

## Home (`ui/home_page.bin`)

Cosmetic only; the icon grid is built in code and untouched. The now-playing strip
(`home_bottomview`) turns from `#131313` to black with a 1 px `#222222` top border (`border=top`,
the string form stock pages use), the artist line (`home_scrlabel_artist`) turns `#AAAAAA`, and the
page dots (`home_sindicator`) become `#EEEEEE` / `#555555`.

## Borrowed from q2-pod (MIT, see NOTICE)

The theme direction and colours (Minimal: `MINIMAL_CHEVRON` #777777, `SUDO_MUTED` #8C8C8C,
neutral pressed #333333, list fills removed, accent text to white; page dots #EEEEEE/#555555), the
settings-disc recolouring rule (`ringnav_image_add`), the status glyph set and its drawing approach
(`status_icon`: 4x render, one weight, #666666 unlit), and the idea of pinning style edits by old
value and state count (`patch_style`). The style parser was written fresh but reads the format
the same way as q2-pod's `style_props`. q2-pod's rounded-corner logic does not apply (the M1 Plus
panel is square) and its Q2 geometry was not used.

## Device checklist (V2.1eT)

- boots; About says V2.1; the status bar shows play state, volume number (16 px), the clock, Wi-Fi /
  Bluetooth and `86%` + icon; switch 12 h: `05:30 PM` fits without touching the Bluetooth icon,
  also with a codec badge showing (aptX HD is the widest)
- System settings / Play settings: black rows with thin grey lines, grey icon discs with white
  glyphs, a tap flashes neutral grey (not red-brown); every row readable
- All Songs, Folders, Albums, Artists lists: rows black with hairlines; the playing track is white
  with its red playing disc; the pressed row grey
- lyrics (Now Playing): the current line white, the others grey; the cover/lyric tab and the
  Artists A-Z tabs: selected white, others grey
- Date & time and Auto-off pickers: the chosen value white, the others grey
- sort dialog, keyboard (Wi-Fi password), track-info dialogs: readable, pressed keys grey
- Home: the strip black with a thin line on top, artist grey, page dots
- M1 Pod menu and Cover Flow track list: rows match the settings rows
- System settings -> Theme -> the second theme: the stock salmon look returns (settings icons
  stay grey there); switch back
