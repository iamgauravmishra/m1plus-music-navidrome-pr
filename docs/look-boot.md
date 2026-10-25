# Look: boot logo, curly quotes, settings slides (`look-boot`, V2.1eB)

Three asset-only changes stacked on the current device build `pod-cover` (V2.1dE contents):
`tools/mod_boot.py`, built by `python3 -I tools/build.py --variant look-boot`
(-> `out/M1Plus-V2.1eB-look-boot-pod-cover-lockscreen-iconpercent-space-update.bin`). No binary,
script or payload changes; `demo` is byte-identical to V2.1dE's.

Preview: `docs/look-boot-preview.png` (stock splash, new splash, and track titles in the stock and
the fixed font; drawn with PIL/FreeType, which takes advances from `hmtx` as AWTK does).

| part | files | what changes |
|---|---|---|
| logo | `release/assets/default/raw/images/xx/logo.jpg`, `logo180.jpg` | an M1 Pod splash in q2-pod's style replaces the Shanling one |
| quotes | `release/assets/default/raw/fonts/default.ttf` | ’ ‘ “ ” render as ' and ", no wide gap |
| slides | 33 `ui/systemset/*.bin` + `theme1/.../systemset/specfolder_page.bin` | settings pages slide in from the right and back out |

`mod_boot.py --no-logo / --no-quotes / --no-anim` drops a part; `--logo/--logo180` take other JPEGs.

## Boot logo

`/etc/init.d/S11logo_display_shell` waits for `/dev/fb0`, then runs
`display_logo /release/assets/default/raw/images/xx/logo180.jpg` if `/mnt/data/config.ini` has
`ROTATEMODE=1` (System settings, screen rotated 180°), else `.../logo.jpg`. Those two files are the
only splash images on the rootfs: V2.1 has **no `release/bin/logo.jpg`/`logo180.jpg`**, nothing else
names `logo.jpg`/`logo180` (byte search of the whole tree), and the one `logo` string in `demo` and
`libawtk.so` is a word in the password-strength dictionary, not an image name.

The stock files are **upright 320x480 portrait** baseline JPEGs (SOF0 8-bit, 3 components, 4:4:4,
Adobe YCbCr), the panel's own orientation (`soc_fb.sh`: `is_rotated=0 rotator_angle=0`), and
`logo180.jpg` is exactly `logo.jpg` turned 180° (decoded difference ≤ 1). So, unlike the Q2 (whose
320x375 framebuffer takes the picture stored turned 90°), nothing is stored sideways here.
`display_logo` (7,112 bytes, libjpeg + libhardware2) draws 1:1 without scaling and reads libjpeg's
output as RGB triples, so the replacement must be 320x480, 8-bit, three components, baseline.

The design follows q2-pod's `assets/boot-logo.svg` / `docs/boot.md`: a thin outlined wordmark in
warm off-white `#F2F2F0` on black, widely spaced **POD** below in muted grey `#BDBDB8` with the small
centre button (`#85857D`) inside the O, no gradients or glows, the group centred at 47 % of the
height (perfect centring looks low). Same scale as the Q2's: 70 px cap height, 7 px stems.
"Q2" became **M1**: the M (splayed legs, pointed middle reaching the baseline, flat-cut tops) and the
flagged 1 are plain geometric outlines computed for this logo, not glyphs from a font; POD and the
button are q2-pod's paths unchanged, moved with a `translate`. Source: `assets/boot-logo.svg`
(upright 320x480).

`tools/boot_logo.py` (repo venv + `brew install librsvg`) renders the SVG with `rsvg-convert` at 4x,
box-filters it to 320x480, and encodes both files from that one raster with Pillow (quality 92,
4:4:4, optimized Huffman, baseline, JFIF, no EXIF): `assets/boot-logo.jpg` (5,845 bytes) and
`assets/boot-logo180.jpg` (5,849 bytes, the raster turned 180°). The JPEGs are committed; the build
only copies them. `mod_boot.py` first checks both stock files by SHA-256, then checks each new file
with q2-pod's `jpeg_size` frame-header walk (SOF0, 8-bit, 3 components; progressive, grayscale and
CMYK refused) and requires 320x480 and an EOI marker. File modes stay stock (755).

Not done: q2-pod's card override (`/Q2Pod/boot/boot-logo.jpg` copied to `/mnt/data/boot-logo.jpg`)
needs code in `demo`. A shell-only `S11logo_display_shell` that prefers `/mnt/data/boot-logo.jpg`
was considered and left out: nothing a user can do without that code puts a file in `/mnt/data`
(USB storage exposes only the card), so it would be dead weight in a boot script.

## Curly quotes

`default.ttf` (9.4 MB, "微软雅黑+Arial", 256 units/em, ascender − descender = 299) is Arial merged
into a CJK font, and the curly quotes come from the CJK side with the full em advance:

| char | glyph | advance | ink x | | ASCII | advance |
|---|---|---|---|---|---|---|
| U+2018 ‘ | quoteleft | 256 | 204..241 | | `'` quotesingle | 48 |
| U+2019 ’ | quoteright | 256 | 15..52 | | | |
| U+201C “ | quotedblleft | 256 | 162..241 | | `"` quotedbl | 90 |
| U+201D ” | quotedblright | 256 | 15..95 | | | |

So "Paul’s" carries ~0.8 em of blank after the apostrophe, and an opening quote floats a whole em
early (see the preview). Track and album names from tags use these characters often. AWTK here uses
its stb_truetype backend (`font_stb_*`; no FreeType code in `demo`/`libawtk.so`), which takes the
advance from `hmtx` and the ink box from `glyf`, so the gap shows exactly like this on the device.

Fix, as q2-pod 1.0.4 (`tools/build.py` `font_quotes`, fontTools): the Unicode cmap maps the four
curly quotes to the straight glyphs. Done here in pure Python (no fontTools needed for the build) to
keep the font byte-stable:

- the Unicode records (0/3 and 3/1) share one format-4 subtable; its segment 0x2010-0x2063 (idDelta)
  is split around the four quotes, each quote getting a one-codepoint idDelta segment pointing at
  glyph 39 (`'`) or 34 (`"`): 428 -> 434 segments, `searchRange`/`entrySelector`/`rangeShift`
  recomputed, the 172 idRangeOffsets re-based to the same glyphIdArray entries (the array itself
  is unchanged), the Mac Roman subtable untouched (its record offset moves with it)
- the cmap grows by 48 bytes, so every table after it moves by 48; their bytes and checksums are
  unchanged. The cmap directory entry and `head.checkSumAdjustment` are recomputed; nothing else in
  `head` changes (no timestamp). File: 9,794,280 -> 9,794,328 bytes
- checks in `mod_boot.py`: the stock font's SHA-256; a line-for-line port of stb_truetype's format-4
  lookup (which trusts the binary-search header fields) agrees with a plain segment decode on the
  stock font, and on the result gives the stock glyph for **every BMP codepoint** except the four
  quotes; every other table is byte-identical; all table checksums and the whole-file checksum hold.
  Cross-checked once with fontTools 4.67 (`checkChecksums=2`, every table decompiles, `getBestCmap`
  differs from stock in exactly the four entries)

With the UI font step (`docs/font-inter.md`, `look-all-inter`) the font is no longer stock and its
curly quotes are Inter's proportional ones; `apply_quotes` then skips (it accepts a non-stock font
only if every curly quote is mapped and narrower than half an em) and the quotes stay curly.

There is no `kern` table; should anything apply GPOS kerning, the straight glyphs simply use their
own pairs, as for typed ' and ".

## Settings slides

AWTK windows take `open_anim_hint` / `close_anim_hint`; this `demo` links AWTK statically and its
`window_base_set_prop` / `window_base_get_prop` and the default window manager read both
(`dis.py xref demo open_anim_hint`), with the built-in window animators registered (`slide_left`,
`slide_right`, `htranslate`, `fade`, ...). The stock lock screen already uses one on a window asset:
`screensaver_page.bin` has `close_anim_hint = slide_left(duration=200,easing=cubic_out)`.

The mod gives every settings window in `ui/systemset/` (and theme1's `specfolder_page`) the same
string as both hints: opening a settings page slides it in from the right over the previous page,
and closing it slides it back out to the right (AWTK plays the close animation reversed). Stock
settings pages go forward with `navigator_to` and back with `on_syssetback_onclick` ->
`navigator_back` -> `window_manager_back`, the animated close path. Skipped on purpose:
`fwupdate_page` (System Update) and `fwdownload_page` (online update), so the way back to a known
build stays byte-for-byte stock. Other pages (Home, lists, Now Playing, status bar, M1 Pod pages)
are not touched. Each file grows by 115 bytes; the edit round-trips byte-exact before it is made.

## Safety audit of the slides (look-all merge)

A close animation is dangerous on this firmware wherever code pops windows in a loop and expects the
stack to change synchronously (q2-pod hit this on the Q2 and patched its handlers in code). The
audit below was done on the stock `demo` (AWTK is statically linked: no `libawtk.so` in
`DT_NEEDED`; default window-manager vtable at `0x97d6a0`, its `back`/`back_to` slots NULL, so the
generic AWTK code runs). Scripts: a natural-loop search over an instruction-level CFG of `.text`
(delay slots modelled, calls resolved by symbol and `$gp` GOT slot, wrappers followed three levels).

**How a close behaves during an animation.**
`navigator_back` (0x4d20dc) -> `window_manager_back` (0x677d2c) -> `EVT_REQUEST_CLOSE_WINDOW` ->
`window_close` -> the default `close_window` (0x6927cc):

- window not yet `OPENED` (still sliding in): an idle retry `check_and_close_window_idle_id` is
  scheduled, nothing is closed now;
- **an animation is running (`wm+0x98`): `pending_close_window = window` (`sw $s0, 0xc0($s1)` at
  0x692960) and return RET_OK** -- one slot, nothing removed;
- otherwise the close animator is created (0x69149c, from the *closing* window's
  `close_anim_hint`, else `anim_hint`; only for the topmost normal window, only if no other
  animation runs); with a hint the window **stays in the list, visible, until the animation ends
  in the main loop** (0x691a24), so `window_manager_get_top_window` (0x6775c4, topmost visible
  child) keeps returning it for the 200 ms.

So a synchronous `while (top != X) navigator_back();` that reaches a sliding window never sees the
stack change and spins (UI hang, watchdog reboot). Input is dropped while animating ("animating
ignore input", 0x68ff64). `window_manager_close_window_force` (0x691cd8) finishes a running
animation synchronously, which is why q2-pod's `navigator_close` fix works.

**Every loop that touches or tests the window stack** (calls to `navigator_*`,
`window_manager_back*`, `window_close*`, `close_window*`, `get_top_*`, `switch_to`, `close_all`,
`window_open` in the loop body):

| loop | what it does | can it meet a slide window? |
|---|---|---|
| Album detail "play from here", handler 0x52569c, loop 0x525908-0x5259d8 | if `navigator_window_is_exist("playing_page")`: while top is neither `playing_page` nor `home_page`: `navigator_back`; then `window_close(playing_page)` + `navigator_to_with_context("playing_page")` | no, see below |
| Jump list (`playerjumpinfo_page`) row handler 0x538b7c, loop 0x538ce4-0x538db4 | the same pattern | no, see below |
| `window_manager_close_all` 0x678b0c | force-closes every window | only from `tk_deinit_internal` <- `tk_exit` (app exit) |
| `requestMusiclistDetail` 0x4936b0 | online list paging, calls `navigator_to` | does not test the stack |

Not loops: go-home (`navigator_back_to_home` -> `window_manager_back_to(NULL)` 0x677ea0) is an idle
callback (0x6777c8) that snapshots the windows above Home, **force-closes** them and animates only
the top one (11 callers: search, keylock, Tidal, the touch/idle/network/USB handlers, ...);
`on_backtoplayer_onclick` (0x4cd58c) -> `navigator_switch_to_with_context` (0x4d1f4c) ->
`window_manager_switch_to` only restacks or opens `playing_page`; the `navigator_to` dispatcher
(0x4d00c0) has no loop; the M1 Pod payload (`patch/m1pod.c`, `patch/coverflow.c`) makes single
`navigator_back` / `navigator_to_with_context` calls and has no stack loop.

**Why the two loops cannot reach a slide window.** They stop at the first `playing_page` or
`home_page` from the top. Album detail and the jump list are opened only from library pages, the
Now Playing "more" dialog (which `navigator_close`s old album pages first), the Home icon dispatcher
(also what M1 Pod uses) and the search results -- none from the settings code (0x49f000-0x4b0000).
Settings pages open only `systemset/*`, `playset/*`, dialogs, `playing_page` (by the switch above,
which puts it **above** the settings window) or Home; the global handlers (pull-down, keys, timers,
idle status) open only the dropdown, settings roots, volume, lock screen, power-off, Bluetooth
receive, USB mode, AirPlay, auto-shutdown, CD ripper, scan, or go Home. So a library page can sit
above a settings window only with a `playing_page` between them, and the loops stop there. They also
cannot start during an animation: they run from a tap on the top window and taps are dropped while
animating (the one theoretical edge, a pointer-up passing through right after the pull-down opens
`sysset_page`, needs a press on the navbar plus a drag that AWTK cancels as a scroll). Language and
theme changes re-translate / restyle windows without closing them; factory reset, Update Library,
USB mode, power-off and firmware update contain no stack loops (and the firmware-update pages stay
without slides by design). The stock lock screen already closes with the same slide.

**Decision: the slides stay on all 34 windows**, in `look-boot` and in `look-all`. The evidence is
static (CFG + reachability), not a device test; its blind spots: computed jumps are treated as exits
(those seen were register tail calls, not switch tables), wrappers are followed three levels, and
navigation targets built in switches were checked as string sets. `mod_boot.py --no-anim` remains
the fallback if a device shows a stuck page. **Rule for later mods:** never give a close hint to a
window that a "play from here" loop can pop (library pages, album detail, the jump list, Now
Playing, M1 Pod pages) -- that is why look-lists and look-nowplaying add none.

Behaviour that differs from stock without hanging (on the checklist): the folder-scan dialog on
the specified-folder page opens ~200 ms late after Back (deferred `pending_open`); two closes or
opens requested within one 200 ms slide share one pending slot (the earlier request is lost, e.g.
two timed pop-ups); a page still sliding in is closed through an idle retry; the pull-down to
settings slides in while the finger is still down.

## Size

| | rootfs.squashfs |
|---|---|
| V2.1dE pod-cover | 53,149,696 |
| V2.1eB look-boot | 53,096,448 (**−53,248**: the two JPEGs shrink by 75 KB, the font and UI add ~4 KB) |

## Verification

- `fwtool diff` V2.1dE -> V2.1eB: exactly the 37 files above (font, 2 JPEGs, 34 UI files), modes,
  owners and times stock; against stock V2.1 additionally V2.1dE's own files and removals
- `fwtool verify`; two clean builds give the same package
  (SHA-256 `9cd5d06c920edaa5eee54d7e6b74a6378c33423216e3426f356e9e89e9495104`)
- `venv/bin/python -I test/patch.py work/mod-look-boot-pod-cover-lockscreen-iconpercent-space`:
  128 passed (the M1 Pod payload and pages are unaffected)

## Device checklist (not yet hardware-tested)

- power on: the M1 Pod splash shows upright and centred until the UI starts (no garbage, no
  black screen); set System settings rotation to 180°, reboot: the splash is upright again in the
  turned orientation
- a track or album with ’ or “ ” in its tag (Library, Now Playing, lock screen strip): straight
  quotes with normal spacing
- System settings: each sub-page slides in from the right; Back slides it out; tapping fast through
  several pages and Back does not leave a page half-drawn or ignore input for more than a moment;
  Back to player (`btn_backtoplayer`) and Home still work; System Update opens without a slide and
  still flashes
- the hang check (see the safety audit): open a settings page, Back to player, then from Now
  Playing open the jump list (or More -> album) and tap a track ("play from here"): it plays and the
  UI stays responsive; do the same with a settings page open underneath via the pull-down
- the specified-folder settings page: Start scan, Back right away: the scan dialog still appears;
  pull-down -> settings while holding the finger down: the page slides in, no stuck input
- fallback: `V2.1dE` (same build without this mod) or `V2.1R`
