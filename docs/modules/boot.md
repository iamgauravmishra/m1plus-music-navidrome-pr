# Boot logo, quotes, settings slides

Split out of docs/ui.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 5. Boot logo, quotes, settings slides (`tools/mod_boot.py`)

- **Logo.** `/etc/init.d/S11logo_display_shell` runs `display_logo` on `images/xx/logo180.jpg` when
  `/mnt/data/config.ini` has `ROTATEMODE=1`, else `logo.jpg`; these are the only splash images. Stock
  files are upright 320x480 baseline JPEGs (4:4:4, Adobe YCbCr; `logo180` is `logo` turned 180°);
  `display_logo` draws 1:1 and reads libjpeg RGB, so a replacement must be 320x480, 8-bit, 3
  components, baseline. `assets/boot-logo.svg` (q2-pod style: just the outlined **M1+** wordmark in
  `#F2F2F0` on black, no product name, so a rename of the launcher does not touch it: 50 px cap height
  (y 200 to 250, centred at 47 % height), 5 px strokes, the plus a 25 px superscript whose top is flush
  with the cap top, the whole wordmark centred horizontally (x 102 to 218); cap line, baseline, the 1's
  stem and the plus bars on whole pixels) is rendered by
  `tools/boot_logo.py` (`brew install librsvg`; 4x box-filtered, Pillow q92 4:4:4) into the committed
  `assets/boot-logo.jpg` (4,434 bytes) and `boot-logo180.jpg`; `mod_boot.py` checks both stock files by
  SHA-256 and each new file's frame header (q2-pod's `jpeg_size`) and keeps mode 755.
- **Quotes.** The stock font gives U+2018/2019/201C/201D the CJK em advance (256 units against 48 for
  `'`, 90 for `"`), so "Paul’s" shows a wide gap. The step maps them to the straight glyphs, in pure
  Python (the one format-4 subtable gets four one-codepoint segments, 428 -> 434, the cmap grows 48
  bytes, later tables move, checksums recomputed), verified with the port of stb's lookup for every BMP
  code point. With the Inter font the quotes are proper and proportional, so `apply_quotes` skips
  ("accepts a non-stock font only if every curly quote is mapped and narrower than half an em"): in the
  release the quotes stay curly.
- **Slides.** Every settings window in `ui/systemset/` (33 files) and theme1's `specfolder_page` get
  `open_anim_hint` = `close_anim_hint` = `slide_left(duration=200,easing=cubic_out)` (the animator the
  stock lock screen's `close_anim_hint` uses): a page slides in from the right and back out (AWTK plays
  the close reversed). `fwupdate_page` and `fwdownload_page` stay stock (the way back to a known build).
  +115 bytes each.

### Settings slide safety audit (static, on stock `demo`)

A close animation is dangerous where code pops windows in a loop expecting the stack to change
synchronously. `navigator_back` (`0x4d20dc`) -> `window_manager_back` (`0x677d2c`) ->
`EVT_REQUEST_CLOSE_WINDOW` -> `window_close` -> `close_window` (`0x6927cc`): a window not yet `OPENED`
gets an idle retry; while an animation runs `pending_close_window` takes one slot (`0x692960`); with a
hint the window stays in the list, visible, until the animation ends in the main loop (`0x691a24`), so
`window_manager_get_top_window` (`0x6775c4`) keeps returning it for 200 ms and a synchronous `while
(top != X) navigator_back();` would spin (UI hang, watchdog reboot). Input is dropped while animating
(`0x68ff64`); `window_manager_close_window_force` (`0x691cd8`) finishes an animation synchronously
(what q2-pod's `navigator_close` fix uses). The only loops that test the stack: Album detail "play from
here" (handler `0x52569c`, loop `0x525908-0x5259d8`) and the jump list (`0x538b7c`, loop
`0x538ce4-0x538db4`), both stopping at the first `playing_page` or `home_page`, opened only from library
pages, the Now Playing "more" dialog, the Home dispatcher and search -- never from the settings code
(`0x49f000-0x4b0000`); a library page can sit over a settings window only with a `playing_page` between
them. `window_manager_close_all` (`0x678b0c`) only runs at exit. Go-home (`0x677ea0`, idle callback
`0x6777c8`) force-closes the windows and animates only the top one. Decision: the slides stay on all 34
windows; the evidence is a CFG reachability search (computed jumps treated as exits, wrappers followed
three levels), not a device test; `--no-anim` is gone, so a stuck page needs a code change in
`mod_boot.apply_anim`. Behaviour differences without hanging: the folder-scan dialog on the
specified-folder page opens ~200 ms late after Back; two closes or opens within one slide share a
pending slot; the pull-down to settings slides in while the finger is down.
