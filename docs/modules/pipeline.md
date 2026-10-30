# Build pipeline

Split out of docs/architecture.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 1. Pipeline

`tools/build.py` builds the release from the pinned official zip (`firmware/`, SHA-256 in
`build.py`); `--restore` repacks stock with tag V2.1R. Every step edits one work tree in place
(`work/mod-release`, per checkout); inputs resolve through `tools/paths.py`.

| # | step | what |
|---|---|---|
| 0 | `fwtool.py unpack` (first run only) | `work/stock`: `rootfs/`, `recovery-update/`, `stock.pseudo` (exact inode metadata), `meta.json` |
| 1 | `mod_battery.py STOCK TREE` | clones stock into the tree; unified battery in the status bar and the pull-down |
| 2 | `mod_font.py` | Inter + Source Han Sans; runs here so every later step measures the new font |
| 3 | `mod_space.py` | zero demo's `.pdr`, remove 10 unreferenced files (`docs/firmware.md` section 4) |
| 4 | `pod.py` | compile the payload, append it to `demo`, install four hooks, apply the library-row edits, write the four `ui/m1plus_*.bin` |
| 5 | `mod_theme`, `mod_lists`, `mod_nowplaying`, `mod_boot`, `mod_ipodrows`, `mod_pulldown`, `mod_lockscreen`, `mod_wallpaper`, `mod_icons`, `mod_strings`, `mod_polish`, `mod_about` | the asset looks, in this order (`docs/ui.md`); `mod_strings` adds our translation keys to the 16 string tables (section 8b) |
| 6 | `mod_theme.py --scan TREE STOCK` | contrast scan of the finished tree |
| 7 | `fwtool.py repack --tailends --allow-removed ... --allow-added ...` | squashfs (LZO, 128 KiB blocks, tail ends), metadata-exact; refuses a rootfs larger than stock or any unlisted added/removed file; `verify` follows |

Each step lists the files it adds through an `added_rels()` function, which `build.py` passes to
`fwtool --allow-added`. `work/mod-release/podbuild/` (manifest.json, patch.elf) stays for the tests.
Builds are deterministic (added files get fixed mtimes); `tools/check.py` compares the package with
`test/golden.sha256`. Order matters: lock screen layout needs `mod_nowplaying`'s `np_*` glyphs and the
final font; icons run late so they override the theme step's grey discs; the lock screen step also
patches four words of `demo` and so runs after `pod.py`.

Toolchain for the payload: Homebrew clang/LLD/llvm-objcopy/llvm-readelf (`$LLVM_BIN`, `$LLD_BIN`;
Apple clang has no MIPS target), unicorn 2.1.4 for the tests, mksquashfs 4.7.5. Python runs with `-I`
on anything touching extracted firmware.

Source map: `patch/m1plus.c` (hook, pages, rows, the Settings switches), `patch/menu.c` (the customisable menu and the Main Menu page), `patch/covercache.c` (+ `.h`: the cover cache, tile reduction and album helpers
Cover Flow and Albums share), `patch/coverflow.c`, `patch/albums.c`, `patch/artists.c`,
`patch/shuffle.c`, `patch/shot.c` + `shot.h` (Screenshot), `patch/albuminfo.c` (the album view's hook), `patch/nowplaying.c` (Now Playing's hook), `patch/minibar.c` (the mini player bar, no hook), `patch/rows.c` + `patch/rows.json`, `patch/home.c` + `home.h`, `patch/i18n.h` (`TR()`), `patch/offsets.inc`
(every stock offset with its evidence), `patch/link.ld`; `tools/pod.py` (build and pins),
`tools/pod_pages.py` (pages and rows, one source of truth), `tools/pod_ui.py` (page assets), `tools/pod_i18n.py` (our texts in 13 languages), `tools/awtk_strings.py` (string table reader/writer), `tools/mod_strings.py`.
Tests: `test/patch.py WORKDIR` runs `test/pod/<module>.py` (menu, coverflow, albums, assets, artists, rows,
albuminfo, nowplaying, shuffle, home, i18n) on `test/pod/harness.py`; `test/coverflow.py` (host build of the renderer and the pixel helpers),
`test/demo_diff.py`, `test/awtk_fill.py`.
