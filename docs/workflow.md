# Workflow: making and testing an asset-level mod

This is the process that produced the battery-percentage mod, written down so the next mod follows the
same path. Everything here was exercised on a real M1 Plus on 2026-10-19.

## 0. One-time setup

```
python3 -m venv venv && venv/bin/pip install -r requirements.txt
brew install squashfs            # unsquashfs / mksquashfs >= 4.5 (needs -pf support)
cp "M1 Plus Firmware V2.1.zip" firmware/
python3 -I tools/build.py --restore          # also unpacks stock into work/stock
```

`work/stock/` then holds `rootfs/` (extracted root filesystem), `recovery-update/` (stock kernel and
squashfs), `stock.pseudo` (exact inode metadata) and `meta.json` (tar member metadata, superblock
parameters). Treat `work/stock` as read-only reference; mods are built in copies of it.

Run Python on extracted firmware with `-I` so nothing inside the untrusted tree can be imported.

## 1. Find what to change

1. UI layouts are AWTK binary files under `rootfs/release/assets/default/raw/ui/`. Dump one:
   ```
   python3 -I tools/awtk_ui.py dump work/stock/rootfs/release/assets/default/raw/ui/system_bar.bin
   ```
   Each widget has a type, fixed `x y w h`, and ordered `key = value` properties. Children layouts
   such as `default(r=1,c=0,a=right,s=5)` override the children's own `x`. Only
   `assets/default` matters; `theme1` carries a handful of pages and no status bar.
2. Images live in `images/xx` (1x) with `x1 x2 x3` variants; fonts in `fonts/default.ttf`; the
   theme in `styles/default.bin`; strings in `strings/`.
3. Which widget the app drives at runtime: search the player binary for the widget name and read
   the surrounding code.
   ```
   venv/bin/python -I tools/dis.py xref work/stock/rootfs/release/bin/demo pgbar_battery
   venv/bin/python -I tools/dis.py sym  work/stock/rootfs/release/bin/demo dropdown_showface
   ```
   `dis.py` annotates calls, GOT loads and string references, so the dump reads like
   "widget_lookup(win, "pgbar_battery") ... progress_bar_set_value(...)". The app looks widgets up by
   name, so names must stay the same; type, geometry and style properties are free to change.
4. Check the property is honoured by this AWTK build: either the stock assets already use it
   (grep the `ui/*.bin` files, e.g. `visible`, `#RRGGBBAA` colours, `show_text`, `format`) or the
   binary contains the property string.

## 2. Make the change

Write a small script like `tools/mod_battery.py`: clone `work/stock` (APFS `cp -Rc` is instant),
parse the `.bin` with `awtk_ui.parse`, edit widgets with `.set()` / `.remove()` / geometry fields,
`awtk_ui.serialize` back, and assert the untouched file round-trips byte-exact first. Keep the
file's permission bits (stock UI files are mode 744).

Rules that keep a mod safe:

- never rename or delete a widget the app looks up by name; restyle, move, or hide it instead
  (`visible=false`, plus parking it off-screen as a belt-and-braces measure)
- keep the rootfs no larger than stock (fwtool refuses otherwise). A bare rebuild has only 12 KB
  of headroom; run the space step on your tree (`tools/mod_space.py WORKDIR`, then repack with
  `--tailends` and the `--allow-removed` list) for ~2.6 MB, see `docs/firmware.md` section 4.
  `build.py` does this for every mod variant
- change one thing per package so a bad result is attributable

## 3. Package

```
python3 -I tools/fwtool.py repack work/mod-xyz out/M1Plus-V2.1xY-update.bin --version V2.1xY \
    [--tailends --allow-removed PATH ...]     # with the space step; one --allow-removed per removed file
python3 -I tools/fwtool.py verify out/M1Plus-V2.1xY-update.bin
python3 -I tools/fwtool.py diff "work/M1 Plus Firmware V2.1/update.bin" out/M1Plus-V2.1xY-update.bin
```

`fwtool diff` prints `-`/`+` pairs for entries whose metadata changed or that were removed, `~` for
files with the same metadata but different content, and one summary line for directories that
differ only in listed size (directory-table layout). Expect only your files, plus `demo` (`.pdr`
zeroed) and the 10 removals when the space step is on. To check contents, extract the package's
squashfs and `diff -rq` it against `work/stock/rootfs`.

Version tag rules (from the updater's code): must contain a capital `V`, must not equal the
installed version string, and every package needs a distinct tag so re-flashing is never refused.
Convention used so far: `V2.1` + lowercase series letter + capital variant letters. `b` = without
the space step (`V2.1bA`, `V2.1bB`), `c` = with it (`V2.1cS` space only, `V2.1cA`, `V2.1cB`
battery, `V2.1cL` lock screen, `V2.1cLB` lock screen + icon+percent), a trailing `W` for the slower
watchdog (`V2.1cBW`); `V2.1R` for the stock restore package.

`fwtool repack` rebuilds the squashfs with the stock parameters (LZO, 128 KiB blocks, stock
mkfs time), re-applies every stock inode's mode, owner and mtime from `stock.pseudo` (macOS loses
symlink modes and setuid bits on extraction), checks the metadata against stock (a stock entry may
be missing only if it is listed with `--allow-removed`), regenerates the `.info` file and rebuilds
the tar with the stock member metadata. An unmodified round trip without `--tailends` gives a
zero-line full-precision listing diff against stock.

Optional: `tools/preview_bar.py` renders a PIL mock-up of the status bar for a quick look before
flashing. It is not AWTK, so font metrics are approximate.

## 4. Test on the device

Use a card that mounts fine on the player (exFAT or FAT32). The card's music is untouched by the
update; `update.bin` sits next to it at the root.

1. First time only: flash the restore package (`--restore`, tag `V2.1R`). It reinstalls the stock
   kernel and rootfs byte for byte, so it proves the whole package path (tar layout, `.info`,
   MD5 check, recovery flasher) with nothing new on the device.
2. Copy the mod package to the card root as `update.bin` and confirm the copy:
   ```
   cp out/M1Plus-V2.1bB-iconpercent-update.bin /Volumes/<card>/update.bin && sync
   md5 -r /Volumes/<card>/update.bin out/M1Plus-V2.1bB-iconpercent-update.bin
   diskutil eject /Volumes/<card>
   ```
3. Card in with the player off, power on, System settings, System Update, TF card update,
   confirm, leave the card in until the player restarts by itself. The player reboots into a plain
   flashing screen, then boots normally.
4. Checklist after boot:
   - About still reads V2.1 (the version string in `demo` is never changed)
   - the changed screen looks right; for the status bar: number updates, charging swaps the icon
     and keeps the real level, Bluetooth and Wi-Fi together do not crowd the clock
   - other pages that embed the same widgets (pull-down panel, screensaver, lock screen) still draw
   - lock screen (`V2.1cL` / `V2.1cLB`), lock the player and wake it:
     - clock fits on one line, is centred, and ticks over each minute
     - switch System settings 12/24 h both ways: the status bar clock changes, the lock clock stays 24 h
       (stock behaviour; note what the status bar shows in 12 h, the code suggests `05:30 PM`)
     - date correct, centred under the clock
     - battery percentage shows, matches the status bar, and changes over time; plug in a charger:
       the icon becomes the bolt and the number keeps updating (100% once the charge completes)
     - now-playing strip shows cover, title and artist while playing, play/pause and next work, and
       the strip disappears when nothing is queued
     - swipe to unlock works
     - a custom wallpaper (Screensaver settings) still shows; turning "show time" off hides clock,
       date and battery together (stock behaviour)
     - screen rotation set to 180: the lock screen turns as a whole, nothing clipped or misplaced
   - sleep, wake and a reboot
5. The player does not delete `update.bin` after flashing; overwrite it with the next package.

### Space step: test order (not yet hardware-tested)

The space step changes one binary, `demo` (unloaded `.pdr` bytes only, as q2-pod does on the Q2),
and removes 10 files, so it gets its own package before anything is combined with it:

1. `V2.1R` if the player is not already on a known-good build.
2. `M1Plus-V2.1cS-space-update.bin`: space step only, UI identical to stock. Check:
   - it boots to the normal home screen and stays up (no watchdog reboot loop)
   - About still reads V2.1
   - playback from the card: start, pause, seek, next track, a few formats (FLAC, MP3, AAC/M4A)
   - library: browse by folder and by artist/album, cover art shows, a library rescan finishes
   - settings pages open and a changed setting survives a reboot
   - sleep, wake, a reboot; if you use them: Bluetooth output and Wi-Fi (the removed old glib and
     dbus copies sit next to the libraries their daemons use)
3. Then `M1Plus-V2.1cB-iconpercent-space-update.bin` (or `cA`) with the status-bar checks above.
   `cBW` additionally slows the watchdog poll to 10 s; nothing visible should change.

If `cS` misbehaves, flash `V2.1R` and bisect: build a tree with
`tools/mod_space.py work/mod-x --from work/stock --no-remove` (only `.pdr`) or `--no-pdr` (only the
removals), repack with `--tailends` (and the `--allow-removed` list for removals) under a new tag.

`mod_space.py --pdr-all` zeroes `.pdr` in all 197 executables and libraries for ~540 KB more. It is
off by default and not in `build.py`: no hardware has run such binaries yet. If you try it, use its
own tag and run the full checklist above.

### UI font (V2.1fI, not yet hardware-tested)

`look-all-inter` is `look-all` (V2.1fA: V2.1eA, which works on the device, plus the album fix) with
the font step first (`docs/font-inter.md`); only `fonts/default.ttf`, two re-measured ui files and the
pull-down's `dropdown_dialog.bin` (default and theme1) differ. Flash it over V2.1eA and go through the
checklist in `docs/font-inter.md`; V2.1eA is the fallback. The build needs fontTools
(`requirements.txt`) and, once, `python3 -I tools/mod_font.py --fetch`; so does `full` (V2.1gA,
`docs/full.md`), which carries the same font.

### M1 Pod code payload: test order (V2.1dM and V2.1dE work on hardware)

M1 Pod injects code into `demo` (see `docs/payload.md`), so it is riskier than an asset edit and
ships in three stages. **Flash them in order**, and keep a `V2.1cLB` or `V2.1R` package on hand to
fall back. Before flashing any stage, you may pre-place an empty file named `m1pod-off` at the root
of the SD card to keep the payload disabled (the entry icon then behaves exactly as stock); delete it
to enable M1 Pod.

**The entry is the Tidal icon** — the first icon on the Home screen in English. Tapping it opens M1
Pod instead of Tidal (which needs Wi-Fi and a subscription); nothing else on Home changes. The HiFi
Music icon cannot be used: `demo` only puts it on Home when the language is 简体中文
(`docs/payload.md#home-icons-and-their-conditions`). If you ever build with `HOME_ENTRY = 0`,
switching the UI language to Simplified Chinese is the one stock way to make that icon appear for
testing.

1. `V2.1R` or `V2.1cLB` if the player is not already on a known-good build.
2. **`M1Plus-V2.1dA-pod-inert-...`** (no hook). The one thing to confirm: the player boots to the
   normal Home screen and stays up (no watchdog reboot loop), About still reads V2.1, and the Home
   Tidal icon still opens Tidal / the "no network" message (nothing changed). This proves the loader
   accepts the new program segment. If it reboot-loops, flash `V2.1cLB`/`V2.1R` back; do not continue.
3. **`M1Plus-V2.1dH-pod-hello-...`** (hook + hello page). Tap the **Tidal** icon on Home: a small
   "M1 Pod is alive" page should open. Press **Back** (top-left) → returns to Home. Press **Now
   Playing** (top-right) → goes to the player. Then test the kill switch: power off, add
   `/m1pod-off` to the card root, boot, tap the Tidal icon → it should behave as stock Tidal again;
   remove the file to re-enable. Reboot once and confirm it still boots.
4. **`M1Plus-V2.1dM-pod-menu-...`** (hook + iPod menu). Tap the Tidal icon: the menu opens (Now
   Playing, Songs, Albums, Artists, Genres, Folders, Playlists, Settings). Each row should open the
   matching stock page (or the player); Back returns through the pages to Home. Check a few rows and
   that playback/library still work, then sleep/wake and reboot.
   **Done on 2026-10-20** — flashed straight over V2.1R (skipping dA and dH) and it works.

5. **`M1Plus-V2.1dE-pod-cover-...`** (the menu plus Cover Flow). History, 2026-10-25: `V2.1dC` opened
   and built its cache (107 thumbnails, 14 MB) but the covers ignored every touch; `V2.1dD` fixed
   that (swiping works) but its track list was white on white and the menu could not scroll
   (`docs/coverflow.md`). Checklist:
   - the player boots, About still reads V2.1, Home looks normal
   - tap **Tidal**: the menu opens with a **Cover Flow** row; the rows look like the stock settings
     list (dark, white text, arrows), about seven and a half fit, and **dragging the list up shows
     the last rows** (Playlists, Settings); a tap still opens a row, a drag does not
   - tap **Cover Flow**:
     - **first run**: "Preparing covers... n/m" counts up and the covers appear when it finishes.
       Time it roughly (it extracts one thumbnail per album). Press **Cancel** part-way through on
       purpose: the covers should appear at once with the finished ones real and the rest a grey
       disc, and the next open should resume the build where it stopped
     - the covers: the centre one upright and sharp, the neighbours turned and dimmer, reflections
       under them, the album name and artist below
     - **swipe** left and right: the shelf should follow your finger, flick should coast and settle
       on one cover, and the captions should change when it settles. Watch for lag with a large
       library (a cover takes about 2.8 M instructions to draw, so a slow frame rate here is the
       thing most likely to need tuning: `ART_SIZE` and `CF_VIEW_H` in `patch/offsets.inc`)
     - tap a **side** cover: it should glide to the centre; tap the **centre** cover: the album's
       track list opens, **dark with white titles like a stock list**, and the last track is
       reachable by dragging the list up (nothing is hidden under the bottom edge)
     - drag slowly by about a cover's width (90 px): one album moves; flick: it coasts a few
       albums and settles; drag right from the first album: it wraps to the last
     - after **Cancel** or a finished build, the covers must react at once (that is the V2.1dC bug)
     - tap a **track**: it should play from Now Playing exactly as from the stock album page
       (check the queue: next/previous stay inside the album), and the hardware prev/next/play keys
       still work
     - **Back** from the track list returns to the covers on the same album; **Back** again leaves
       the page to the menu; **Back** again to Home
     - reboot, open Cover Flow again: it should open on the **last album** you looked at, with no
       build (the cache is on the card)
   - with the **card removed** or nearly full: Cover Flow should still open and show the
     placeholder discs, never hang
   - with an **empty library** (or before Update Local Music has run): "Update Local Music first"
   - the **kill switch** still works: `m1pod-off` at the card root makes the Tidal icon open Tidal
   - to clear the cache, delete `/mnt/mmc/.coverflow` from a computer
   - check free space on the card afterwards (one JPEG per album, 140 px)

6. **The looks** (asset-only, each on top of V2.1dE; fall back to `V2.1dE`). Flash one at a time
   if you want to attribute a problem, or go straight to the combined package:
   - **`M1Plus-V2.1eT-look-theme-...`** (the Minimal theme): `docs/look-theme.md#device-checklist-v21et`
   - **`M1Plus-V2.1eL-look-lists-...`** (library lists): the checklist in `docs/look-lists.md`
   - **`M1Plus-V2.1fN-look-nowplaying-...`** (iPod-style Now Playing; V2.1eN before the album fix): `docs/look-nowplaying.md` ("What to check on the device")
   - **`M1Plus-V2.1eB-look-boot-...`** (boot logo, quotes, settings slides): `docs/look-boot.md#device-checklist-not-yet-hardware-tested`,
     including the "play from here" hang check for the slides
   - **`M1Plus-V2.1eA-look-all-...`** (all four, theme -> lists -> nowplaying -> boot): the merged
     checklist in `docs/look-all.md`. If something is off there, the single looks tell which one it
     is. V2.1eA works on the device except for a colon in front of the Now Playing album
   - **`M1Plus-V2.1fA-look-all-...`** (V2.1eA with the album fix; only `ui/playing_page.bin` differs):
     flash over V2.1eA and check the album line (`docs/look-all.md`, "V2.1fA on the device")

7. **`M1Plus-V2.1fK-look-lock2-...`** (look-all + the iPhone-style lock screen; asset-only, only the
   lock screen changes; fall back to `V2.1eA`). Checklist, in short (details in
   `docs/lockscreen2.md#device-checklist-not-yet-hardware-tested`):
   - cover size and sharpness: a track with embedded art of 254 px or more fills the 254 px square
     sharply, with no blur or blockiness. Also a folder `cover.jpg` track, and note what a track
     without art shows
   - rounded corners on the cover and the card, no fringes
   - title and artist readable, scrolling, updating with the track
   - play/pause (off-white glyph swaps) and next work on the first tap
   - swipe to unlock starting on the cover, the card text, the clock and the bare wallpaper
   - nothing queued: card gone, date + clock at the top, swipe works everywhere
   - date `Monday, Oct 19`-style, clock centred and ticking, still 24 h after toggling 12/24 h;
     battery gauge top right without a number, bolt on the charger
   - custom wallpaper shows behind; "show time" off hides date/clock/battery
   - rotation 180: the page turns as a whole

8. **`M1Plus-V2.1fR-artists-...`** (V2.1fA plus M1 Pod Artists and Cover Flow per artist; fall back
   to `V2.1eA`). Full list in `docs/artists.md#device-checklist-not-yet-hardware-tested`; in short:
   - M1 Pod -> **Artists** opens a black list like the menu, same names and order as the stock
     Artists page, scrolls with a scroll bar; a drag does not open an artist; with a large library
     note how long it takes to open
   - flip the stock Artists page's artist / album-artist button: our list follows it
   - an artist with several albums: titled with the artist, only its albums, no "Preparing covers"
     if the main Cover Flow's cache is built, no repeats, the first album and the **All albums**
     card are the two ends (a drag past them stops)
   - All albums (centred, tap): every song of the artist; a song plays, next/previous stay inside
     the artist; an album: its tracks by the artist, a track plays
   - Back: tracks -> covers -> Artists -> menu; one-album artist: no card; Unknown Artist: probably
     "No albums"
   - then the main **Cover Flow**: it reopens on its own last album; no hint line on either page,
     the captions sit right under the reflections, a tap on the album name opens the album

9. **`M1Plus-V2.1fS-shuffle-look-all-...`** (V2.1fA plus Shuffle in the M1 Pod menu; fall back to
   `V2.1eA`). Full list in `docs/shuffle.md#device-checklist-not-yet-hardware-tested`; the core:
   - tap **Shuffle Songs**: Now Playing opens and plays a random song with the Shuffle mode icon;
     **Next** goes to another random song (not the next title); tap the row again: another first song
   - tap **Shuffle Albums**: Now Playing plays track 1 of a random album and the album in order
     (a multi-disc album: disc 1 then disc 2), then another album from its first track; tap again: a
     different first album. **Shuffle Folders** the same by folder
   - play mode afterwards: Shuffle Songs leaves the stock mode on **Shuffle** (a song tapped later in
     Songs/Albums also shuffles until you change the mode on Now Playing or in Play settings); Shuffle
     Albums/Folders turn Shuffle or Repeat one into **List play** (stops after the last album) and keep
     List play or **Repeat all** (the same album order starts again)
   - reboot mid-shuffle (Memory play on): Songs keeps shuffling; Albums resumes on the track and then
     follows the Songs order (expected); empty library / card out: a message box, nothing changes

10. **`M1Plus-V2.1gA-full-...`** (everything: the font, the four looks, lock screen 2, Cover Flow,
   Artists and Shuffle; fall back to `V2.1eA`, or to the single f-package of whatever misbehaves).
   The combined checklist is `docs/full.md#device-checklist-not-yet-hardware-tested`.

If any stage misbehaves, place `m1pod-off` on the card (disables the hook) or flash `V2.1eA`
(the device build before Artists), `V2.1dM`
(menu only), `V2.1cLB` (no payload at all) or `V2.1R` (stock).
Because the hook only runs on a deliberate tap of the entry icon and always falls through to stock on
error, a failure should not prevent boot; the worst likely case is the icon doing nothing new.
If the Tidal icon is not on your Home screen (it can be hidden in Home customisation), show it there
again, or rebuild with another `HOME_ENTRY` (e.g. 15, CD Ripper).

## 5. Going back

Flash the `V2.1R` restore package. The official V2.1 file is refused by the menu while V2.1 is the
installed version (identical string). If the UI ever fails to start, the watchdog reboots the player
in a loop rather than leaving it dead; the fallback is the recovery path with `recovery-update/`
from the official zip on the card root. The button combination for the M1 Plus is unverified
(q2-pod's Q2 procedure: hold Previous, power on with Centre).

## 6. Where things are

| | |
|---|---|
| official zip | `firmware/` (gitignored, SHA-256 pinned in `tools/build.py`) |
| unpacked stock | `work/stock/` |
| modified trees | `work/mod-*/` |
| packages | `out/` |
| reference | q2-pod clone for its docs and asset conventions (kept outside this repo) |
