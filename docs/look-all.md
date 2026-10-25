# Look: all four looks together (`look-all`, V2.1fA)

**Hardware result, 2026-10-25:** V2.1eA (`cc86e833…`) flashed over V2.1dE and **works** per the
user. The individual look packages (V2.1eT/eL/eN/eB) were not flashed on their own. One flaw showed:
the Now Playing album line kept the colon of `Album:` (and a sliver of the `m`) in front of the album.

**V2.1fA** is V2.1eA with that fixed (`docs/look-nowplaying.md`, "The album line": the offset
ignored AWTK's +1 px after every glyph and the label's 2 px margin). The only file that differs from
V2.1eA is `ui/playing_page.bin`, so it flashes over V2.1eA like any update. look-all builds V2.1fA;
the tag moved to series `f` so the fixed package can't be mistaken for the installed one. The
flashed V2.1eA itself is reproducible only from commit `62015e7` (`git worktree add /tmp/eA 62015e7`,
then `build.py --variant look-all` there gives `cc86e833…` again, checked after the merge of the
f-series branches); the current tree has no switch back to the old album offset.

The four asset-only looks stacked on the device build `pod-cover` (V2.1dE: lock screen +
icon+percent + space + M1 Pod + Cover Flow), in this order:

1. **theme** (`tools/mod_theme.py`, `docs/look-theme.md`): Minimal neutral `styles/default.bin`,
   grey settings icon discs, redrawn status glyphs, status bar and Home strip polish
2. **lists** (`tools/mod_lists.py`, `docs/look-lists.md`): window themes for the library pages
   (default + theme1) **derived from the tree's `default.bin`**, so they follow the theme; Songs
   index letter; dialog pressed colour
3. **nowplaying** (`tools/mod_nowplaying.py`, `docs/look-nowplaying.md`): iPod-style Now Playing
   (`ui/playing_page.bin`, its own `styles/playing_page.bin`, 20 `np_*.png`)
4. **boot** (`tools/mod_boot.py`, `docs/look-boot.md`): M1 Pod boot logo, straight curly quotes in
   `default.ttf`, settings pages slide in and out

```
python3 -I tools/build.py --variant look-all
# -> out/M1Plus-V2.1fA-look-all-pod-cover-lockscreen-iconpercent-space-update.bin
venv/bin/python -I tools/preview_all.py work/mod-look-all-pod-cover-lockscreen-iconpercent-space docs/look-all-preview.png
venv/bin/python -I tools/mod_theme.py --scan work/mod-look-all-... work/stock     # contrast scan alone
```

![look-all preview](look-all-preview.png)

`docs/look-all-preview.png`: boot splash, Home, System Settings, Songs, Now Playing and the M1 Pod
menu, drawn from the finished tree by the looks' own PIL preview code (approximate, not AWTK).

No code changes: `demo`, the M1 Pod payload and every binary are byte-identical to V2.1dE. Each look
also builds alone (`look-theme` V2.1eT, `look-lists` V2.1eL, `look-nowplaying` V2.1fN (V2.1eN before
the album fix), `look-boot` V2.1eB) from the same `LOOK` table in `tools/build.py`.

## How the looks stack

The looks touch disjoint files except where one reads what an earlier one wrote:

- **lists after theme**: `mod_lists.py` copies `btn_tablerow_style` and reads `list_item_style`,
  `srlabel_item_gold20_style` and `srlabel_item_gray18_style` from the tree's `default.bin`. On the
  theme's file that gives black rows with the 1 px hairline, a neutral `#333333` pressed colour, and
  white for the accent (Search's active-tab underline is white instead of orange); the build log
  prints the palette it used. The confirm and sort dialogs, which stay byte-identical in `look-lists`
  alone (stock already presses them in `#362221`), now press in `#333333` like the rows; their
  check (`edit_pressed`) still pins the stock value in the ui file. theme1 is left stock by the
  theme, so its window themes keep theme1's coral and pressed colour.
- **nowplaying after theme**: the theme changes the lyric styles in `default.bin`; Now Playing
  defines its own page-local `listitem_lyric_style` / `listitem_sellyric_style` (grey / off-white),
  which win on that page. Its glyphs come from the stock `p_*.png`. The album offset is measured
  from the tree's own `default.ttf` and the label margin from the tree's `default.bin` as they are when
  the step runs (so an earlier font step is followed; the boot step's four quote cmap entries come
  later and do not touch `Album:`).
- **boot last**: it pins the stock `logo.jpg`, `logo180.jpg` and `default.ttf` by SHA-256 and only
  adds the animation hints to the settings windows; no earlier look touches those files.

Every mod keeps its own checks unchanged (stock pins, round trips, touch and geometry asserts); none
had to be loosened. `tools/awtk_style.py` is the one theme-file parser for all of them (the lists
and Now Playing tools first carried their own; their outputs are byte-identical with the shared one).

## Contrast scan of the finished tree

`mod_theme.py` checks contrast inside the theme step, but later looks add window themes and edit ui
files, so `build.py` runs `mod_theme.py --scan WORKDIR work/stock` after every look variant. For
both asset themes (default, theme1) it resolves each of the 137 ui files the way the app does
(`assets/<theme>` first, then default), looks each text widget's colours up inline, then in its
window theme (`styles/<window>.bin`), then in that asset theme's `default.bin`, and compares text
against the nearest opaque background in the normal and pressed-row states; it also runs the theme's
row audit for the code-built rows under `default.bin` and under each of the 16 window themes. The
build fails on any pair below 4.5:1 that is worse than in the stock tree. look-all result: no
failures; code-built rows worst 9.04:1 at rest and 5.44:1 pressed (stock 8.00 / 6.42), theme1
8.00 / 6.76 (unchanged). Negative tests (a dark title in `folder_page.bin`, a dark artist line
inline on Now Playing, dark Search tabs) all fail the scan as they should.

## The settings slides

Kept in look-all. A close animation can hang this firmware when code pops windows in a loop
(`while (top != Now Playing/Home) navigator_back()`): during the 200 ms slide the closing window
stays on top and `close_window` only records a pending close. The audit (`docs/look-boot.md`,
"Safety audit of the slides") found exactly two such loops in `demo`, album detail and the jump
list. Both stop at the first `playing_page`/`home_page`, and no path puts a library page above a
settings window without a `playing_page` between them. Go-home force-closes, back-to-player only
restacks, and the M1 Pod payload has no stack loop. So all 34 slide windows are safe. This is a
static argument, not a device result: if a page ever sticks, `mod_boot.py --no-anim` drops the
slides.

## Size

| | rootfs.squashfs | vs stock limit 55,738,368 |
|---|---|---|
| V2.1dE pod-cover | 53,149,696 | 2,588,672 free |
| V2.1eA / V2.1fA look-all | 53,129,216 (−20,480: the smaller logo JPEGs outweigh the rest) | **2,609,152 free** |

## Verification

- `fwtool verify` OK; two clean builds give the same package
- `fwtool diff` V2.1dE -> V2.1eA: 133 files, the union of the four looks' own diffs (58 + 14 + 22 +
  37, no file shared), plus `ui/dialog/confirminfo_dialog.bin` and `ui/dialog/sortselect_dialog.bin`.
  Both are among `mod_lists.py`'s files, and only when stacked does their content change (see
  above). Modes, owners and times are stock; directories differ only in listed size
- `venv/bin/python -I test/patch.py work/mod-look-all-...`: 128 passed, 0 failed;
  `test/coverflow.py` 23 passed; every style (26) and ui file (144) in the tree round-trips byte-exact
- each look alone is byte-identical to its own branch's build (V2.1eT `6f921f4f...`, V2.1eL
  `768b6abd...`, V2.1eN `84ed09f1...`, V2.1eB `9cd5d06c...`), and `pod-cover` still gives V2.1dE
  `0806ade2...`
- V2.1fA (album fix): `M1Plus-V2.1fA-look-all-pod-cover-lockscreen-iconpercent-space-update.bin`,
  SHA-256 `0e3980fb9c1065c6a110cabdab4abbf1493e888c68837117a8925687c38c35e1`; `fwtool verify` OK;
  `fwtool diff` V2.1eA -> V2.1fA: only `ui/playing_page.bin` (label_album x -45 -> -52); two clean builds
  identical; `test/patch.py` 128 passed, 0 failed; the contrast scan passes as before

## V2.1fA on the device

Flash over V2.1eA, then on Now Playing (English UI): the album line starts with the album's first
letter, at the left edge of the title and artist, with no colon or sliver of `m` before it (also for
`Unknown`, and while a long album scrolls). Everything else is V2.1eA.

## Device checklist (V2.1eA: works on the device, except the album colon)

Fall back to `V2.1dE` (or a single look) if anything misbehaves; `m1pod-off` still disables M1 Pod.

- **boot**: the M1 Pod splash, upright and centred; with rotation 180° set, upright again after a
  reboot. About still reads V2.1
- **status bar**: play state, 16 px volume number, 18 px clock, Wi-Fi/Bluetooth, `86%` + icon;
  12 h `05:30 PM` clears the Bluetooth icon, also with a codec badge
- **Home**: black strip with a thin top line, grey artist line, neutral page dots; Tidal opens
  M1 Pod
- **settings** (System and Play): black rows with hairlines, grey icon discs, grey pressed flash,
  every row readable; each System settings sub-page **slides in from the right and out on Back**;
  fast taps through several pages and Back leave nothing half-drawn; Back to player and Home work;
  System Update opens without a slide and still flashes
- **hang check for the slides**: open a settings page, Back to player, open the jump list (or More
  -> album -> album detail) and tap a track: it plays, the UI stays responsive. Repeat with a
  settings page opened by the pull-down underneath. Specified-folder page: Start scan, then Back
  at once: the scan dialog still appears
- **library lists** (Folders, Artists/Genres/Composers, Songs, Albums, Album detail, Playlists,
  Search): black rows with hairlines, 21 px titles on Folders/Artists, the playing item white with
  its red disc, pressed rows grey; Songs index letter a dark rounded square with a white letter;
  artist lines grey from the first frame; Search: active tab white with a white underline, others
  grey; Import/Export tiles and the add-to / confirm / sort dialogs press grey
- **Now Playing**: looks like the preview, no seam under the status bar, nothing overhangs; the
  album line has no `Album:` prefix and no colon (English UI; V2.1fA); art corners rounded; every
  control works (Back, heart, More, mode cycle, prev, play/pause glyph swap, next, queue, seek by tap
  and drag); swipe to lyrics (current line off-white, others grey) and info; A-B markers under the bar
- **quotes**: a title with ’ or “ ” shows straight quotes with normal spacing (library, Now
  Playing, lock screen strip)
- **pickers, keyboard, dialogs**: Date & time / Auto-off pickers show the chosen value white;
  keyboard keys press grey; track-info dialogs readable
- **M1 Pod**: the menu rows and Cover Flow's track list match the settings rows; Cover Flow swipes
  and plays as on V2.1dE
- **theme1** (System settings -> Theme): the stock coral look returns on lists, Now Playing and
  settings (settings icons stay grey); switch back
- lock screen, sleep/wake, a reboot
