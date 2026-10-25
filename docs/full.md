# Everything together (`full`, V2.1gA)

**Status: works on the device.** Hardware result 2026-10-25: V2.1gA (`e81541f1…`) flashed over
V2.1eA; the user confirms the Inter + Source Han Sans font, Artists, Shuffle and Now Playing (album
line fixed) work perfectly. Lock screen 2 works but gets refinements from the user's feedback
(smaller battery icon, clock and swipe hint; a translucent, larger player card): see V2.1gK.

One package with every mod of the
f series on the device build: the **Inter + Source Han Sans** UI font, the four **looks** (theme,
library lists, Now Playing with the album fix, boot logo + settings slides), **lock screen 2** (the
large rounded cover), and an M1 Pod payload with **Cover Flow, Artists and Shuffle**. Still exactly
one hook, still no boot-path code.

```
venv/bin/pip install -r requirements.txt     # fontTools 4.67.0, Pillow, pyelftools, unicorn
python3 -I tools/mod_font.py --fetch         # Source Han Sans SC zip -> fonts/ (95 MB, SHA-256 checked)
venv/bin/python -I tools/build.py --variant full
# -> out/M1Plus-V2.1gA-full-pod-cover-lockscreen-iconpercent-space-update.bin
venv/bin/python -I test/patch.py work/mod-full-pod-cover-lockscreen-iconpercent-space    # stage G
venv/bin/python -I tools/preview_full.py work/mod-full-pod-cover-lockscreen-iconpercent-space docs/full-preview.png
```

![V2.1gA preview](full-preview.png)

`docs/full-preview.png`: boot splash, Home, System Settings, Songs, Now Playing (a Chinese title,
the album line without its prefix), the M1 Pod menu with the Shuffle rows, Artists, Cover Flow on
one artist, and lock screen 2 playing and with nothing queued. Drawn from the finished tree by the
existing preview painters, with every glyph rasterized from the tree's `default.ttf` the
stb_truetype way (`tools/stb_raster.py`); the covers are the real renderer. Approximate, sample data.

## What it contains

| part | what you see | doc |
|---|---|---|
| font | Inter 4.1 (tracked -8/256) for Latin, Greek, Cyrillic; Source Han Sans SC for CJK, kana, Hangul; proper curly quotes; the pull-down's volume label widened for `100` | `docs/font-inter.md` |
| theme | Minimal neutral theme: black rows with hairlines, grey pressed rows and icon discs, redrawn status glyphs, 16 px status bar, Home strip | `docs/look-theme.md` |
| lists | iPod-style library lists following the theme, 21 px titles, Songs index letter, Search tabs | `docs/look-lists.md` |
| Now Playing | iPod-style: rounded art, title / artist / album (no `Album:` prefix, no colon), quiet controls | `docs/look-nowplaying.md` |
| boot | M1 Pod boot logo (upright and 180°), settings pages slide in and out; the quote remap skips (Inter has proper quotes) | `docs/look-boot.md` |
| lock screen 2 | date over an 88 px clock, a 254 px rounded cover card with title / artist / play / next, battery gauge top right; date + clock alone when nothing is queued | `docs/lockscreen2.md` |
| M1 Pod | the Tidal icon opens the menu: Now Playing, Cover Flow, **Shuffle Songs / Albums / Folders**, Songs, Albums, **Artists** (our list; an artist opens Cover Flow on its albums), Genres, Folders, Playlists, Settings | `docs/payload.md`, `docs/coverflow.md`, `docs/artists.md`, `docs/shuffle.md` |
| base | status bar icon + `86%`, space step (`.pdr` zeroed, 10 unused files removed) | `docs/firmware.md` |

## Stacking order (`tools/build.py`, `LOOK['full']`)

1. `mod_battery.py --variant icon+percent` (stock tree -> work tree)
2. **font** (`mod_font.py`, the one `EARLY` step): `default.ttf` replaced, the pull-down label fitted.
   Everything after it measures the new font
3. `mod_lockscreen.py` classic layout (the pod-cover base; lock screen 2 replaces it in step 10)
4. `mod_space.py`: `.pdr` zeroed, removals
5. `pod.py --stage G`: payload compiled with `artists.c` + `shuffle.c` and `-DPOD_ARTISTS -DPOD_SHUFFLE`,
   appended to `demo`, the hook installed, `ui/m1pod_menu.bin`, `m1pod_cover.bin` (no hint),
   `m1pod_artists.bin` written
6. **theme** (`mod_theme.py`)
7. **lists** (`mod_lists.py`, reads the theme's `default.bin`)
8. **nowplaying** (`mod_nowplaying.py`): the album offset measured in the Inter font with demo's
   +1 px per glyph: `Album:` is 49 px, the label sits at x -50
9. **boot** (`mod_boot.py`): logo, slides; quotes skipped (non-stock font with proportional quotes)
10. **lock2** (`mod_lockscreen.py --layout cover --glyphs np`, last: it re-lays out the lock screen
    from scratch and uses nowplaying's `np_*` glyphs)
11. contrast scan of the finished tree (`mod_theme.py --scan`), repack with the stock metadata

## Payload stages

`tools/pod_pages.py` `STAGES`: D = the menu and Cover Flow (V2.1dE), E = D + Artists (V2.1fR),
F = D + Shuffle (V2.1fS), **G = D + both**. A stage's features are read off its rows
(`stage_features`); `pod.py` compiles each feature's source and defines `POD_<FEATURE>` only for the
stages that have it, and the shared sources keep the feature code under `#ifdef`
(`docs/payload.md`, "Stages and features"). So D still compiles to the V2.1dE payload byte for
byte, E to the Artists branch's and F to the Shuffle branch's, and G is their union: 22,824 bytes
(256 of `.scratch`) at `0xb00000`. In the menu, Artists keeps its place (row 8) and points at our
list; the Shuffle rows follow Cover Flow (rows 3-5); twelve 52 px rows scroll in the 400 px list.

## Verification (2026-10-25)

- `fwtool verify` OK. Two clean builds give the same package: **SHA-256
  `e81541f1f940a8532930b0a8c4e500c5c9f12169c44a07e374870e8f85dc55fb`** (58,798,080 bytes)
- `fwtool diff` V2.1eA (the flashed `cc86e833…`) -> V2.1gA: 12 files, plus 5 directories that
  differ only in listed size:
  - `/release/bin/demo` 6,700,712 -> 6,707,496 (payload stage D -> G)
  - `fonts/default.ttf` 9,794,328 -> 9,928,864 (the font; SHA-256 `5d22aee2…`, as on the font branch)
  - `ui/playing_page.bin` (album offset), `ui/screensaver_page.bin` 4,038 -> 4,144 and
    `styles/screensaver_page.bin` 3,991 -> 4,011 (lock screen 2), new `images/xx/ls_artmask.png` (1,042)
  - `ui/m1pod_menu.bin` 4,058 -> 4,795 (Shuffle rows), `ui/m1pod_cover.bin` 2,673 -> 2,504 (no hint),
    new `ui/m1pod_artists.bin` (1,445)
  - `ui/dialog/dropdown_dialog.bin` in `default` and `theme1` (the pull-down volume label)
- rootfs.squashfs 53,374,976 bytes; the stock size is the limit (55,738,368): **2,363,392 bytes
  free** (V2.1eA: 2,609,152; the font costs 241,664, the rest ~4 KB)
- `test/patch.py` on the V2.1gA tree (stage G): **253 passed, 0 failed** (the entry and fall-through
  tests, the whole Cover Flow page on its hint-free layout, the Artists page and the artist scope,
  the Shuffle rows and all three shuffles). The other stages, built by this tree: A 17, B 15, C 17,
  D 132, E 203, F 182, all passing. `test/coverflow.py` 23 passed
- contrast scan: ok (code-built rows worst 9.04:1 at rest, 5.44:1 pressed; theme1 8.00 / 6.76;
  nothing below 4.5:1 that is worse than stock)
- font audit (`mod_font.verify`, in the build): all 42,853 stock code points still map, every one
  that had ink still has ink, 39,690 replaced, 607 added, 3,163 unchanged vertex for vertex;
  vertical metrics stock
- `demo` against stock: inside the stock file's length only `.pdr` (zeroed, not loaded), `PH[10]`
  (`PT_NULL` -> `PT_LOAD` at file `0x660000`, va `0xb00000`, 0x5928 bytes, RWX) and the 8 hook bytes
  at `0x533b80` (`j 0xb00000; nop` over the pinned prologue) differ; inside the loaded segments
  nothing else changed. The payload is appended after a pad to 64 KiB. **Exactly one hook**
- every other variant still builds its documented bytes (see the table in `README.md`)

## Device checklist (not yet hardware-tested)

Flash over V2.1eA (or any earlier build). Fall back to **V2.1eA** if anything is wrong; to tell
which part misbehaves, flash the single f-package of that part over V2.1eA (V2.1fI font, V2.1fK lock
screen 2, V2.1fR Artists, V2.1fS Shuffle, V2.1fA album fix). `m1pod-off` at the card root still
disables M1 Pod (the Tidal icon opens Tidal).

**Boot and text**
- boots to Home, the M1 Pod splash upright and centred (also after a reboot with rotation 180°);
  About still reads V2.1; text draws everywhere
- the new font at small sizes (16 px status bar volume, 18 px clock, `86%`, settings rows, the 14 px
  play times): crisp, evenly spaced (`rn`, `fi`, `ty`), digits and clocks do not jitter
- a Chinese, a Japanese, a Korean, a Russian and a Vietnamese title in Songs and Now Playing: one
  baseline, no holes or tofu; Thai as before; curly quotes ’ “ ” proper and normally spaced
- **pull-down** at volume 100: `100` whole in its status bar, the speaker icon a pixel closer, the
  digital-output icon where it was and clear of the clock (also in 12 h mode); also under theme1

**Looks** (as on V2.1eA, which works)
- status bar: play state, volume, clock, Wi-Fi / Bluetooth, `86%` + icon; 12 h `05:30 PM` clear of
  the Bluetooth icon
- Home strip, settings rows (hairlines, grey icon discs, grey pressed flash), each System settings
  page slides in and out; the slide hang check: a settings page, Back to player, the jump list or
  More -> album -> album detail, tap a track: it plays, the UI responds
- library lists and Search as on V2.1eA; theme1 brings the coral look back

**Now Playing**
- the album line starts with the album's first letter at the title's left edge, no `Album:`, no
  colon, no sliver of `m` (English UI), also while a long album scrolls; every control works;
  lyrics and info pages; A-B markers

**Lock screen 2** (lock, wake, with music playing)
- the cover large and sharp at 254 px (embedded art; also a folder `cover.jpg` track; note a track
  without art), rounded corners without fringes; title and artist readable and scrolling
- play/pause (off-white, glyph swaps) and next work on the first tap
- swipe to unlock from the cover, the card text, the clock and the bare wallpaper
- nothing queued: no card, date and clock at the top, swipe works where the card was
- date like `Monday, Oct 19` and the 88 px clock centred, fully on screen in the new font, ticking;
  24 h after toggling 12/24 h; battery gauge top right without a number, the bolt on the charger
- custom wallpaper behind everything; "show time" off hides date, clock and gauge; rotation 180°;
  theme1 (orange play/pause)

**M1 Pod**
- Tidal opens the menu: Now Playing, Cover Flow, Shuffle Songs, Shuffle Albums, Shuffle Folders,
  Songs, Albums, Artists, Genres, Folders, Playlists, Settings; it scrolls to Settings; the shuffle
  rows have no arrow
- **Cover Flow**: opens on the last album, swipes, flings and snaps, wraps at the ends; the album and
  artist lines sit right under the reflections, no hint line; a tap on the album name opens the
  album like the centre cover; tracks play with next/previous inside the album
- **Artists**: the stock Artists names and order (follows the stock artist / album-artist switch),
  scrolls, a drag does not open an artist; an artist with several albums: titled with the artist,
  only its albums, no repeats, the shelf stops at the first album and at the **All albums** card;
  All albums -> every song of the artist; an album -> its tracks by that artist; Back: tracks ->
  covers -> Artists -> menu; a one-album artist has no card; Unknown Artist probably "No albums";
  afterwards the main Cover Flow reopens on its own last album
- **Shuffle Songs**: plays a random song, mode icon Shuffle, Next is random, a second tap starts
  elsewhere; **Shuffle Albums**: track 1 of a random album, the album in order (multi-disc: disc 1
  then 2), then another album; **Shuffle Folders** the same by folder; Shuffle or Repeat one turns
  into List play, Repeat all stays; empty library / card out: a message box, nothing else changes
- reboot while a shuffle plays (Memory play on): Songs keeps shuffling, Albums resumes on the track
- with a large library: how long Artists takes to open, and a shuffle to start

**General**: sleep / wake, a reboot, Bluetooth and Wi-Fi if used; the kill switch.

## Risks

- **Not hardware-tested as a whole**, and three of its parts (font, lock screen 2, Artists /
  Shuffle) have not been on the device at all; the single f-packages exist to bisect.
- The font is the largest change by bytes and touches every screen; a font that failed to load would
  show no text (static checks only: the same stb rules, table kinds and cmap format as stock).
- Payload: two features in one segment (22.8 KB); each is reached only from its menu row, adds no
  hook and keeps the fall-through paths, but G is the first build where Artists and Shuffle meet
  (they share no state; `test/patch.py` runs both test sets on the G payload).
- Artists builds one row per artist up front (capped at 2,000): slow to open with thousands.
- Free rootfs space drops to 2.36 MB (from 2.61 MB).
- Tags: the f packages keep their branch tags but were rebuilt on V2.1fA, so their bytes differ
  from the branch builds (only `ui/playing_page.bin`, plus the pull-down files in V2.1fI). If a
  branch build was flashed, the updater refuses the same tag: flash another package first.
