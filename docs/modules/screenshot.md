# Screenshot

**Sources:** `patch/shot.c`, `patch/shot.h`, test `test/pod/shot.py`, `tools/pull_shots.py`.

A developer's screen grab, the Screenshot row of Settings > Developer (`ACT_SHOT`, page `m1plus_developer`). No stock function is hooked, nothing
runs on the boot path, in the main loop or at paint, and there is no thread: a tap starts a payload-owned countdown, and the only
code that runs afterwards is two timer callbacks. It has no kill-switch check of its own: the menu entry gates the row.

Import with `uv run python -I tools/pull_shots.py [CARD_DIR] [--build latest|DIR]`.
PNG names include the source content hash, so another card reusing `shot-0001.bmp` does not lose
an image. JSON sidecars record the original path/hash and, when selected, the dev tag/package
hash. `--build` stores captures in that artifact's `device/` directory; otherwise `out/shots/`.

- **Confirm and cancel.** A tap on the idle row opens the stock confirm dialog (`pod_confirm` in `patch/m1plus.c`, shared with Rebuild
  Covers: `dialog/confirminfo_dialog`, kind 5 wrapped text, modal, `CONFIRM_YES` for Yes) asking "Take a screenshot?" (step 1, plain Yes / No); only Yes goes on, anything else (No, the dialog failing to open) does nothing. Yes opens
  the same dialog again, "Take a screenshot in:", with the delay as its two buttons (step 2, below); only those start, any other result does nothing. A tap while the countdown runs asks "Cancel the screenshot?"; Yes
  removes the tick timer by its id (`timer_remove` `0x66360c`, already pinned, called from the tap, never from inside the timer's own
  callback), hides the camera and returns to idle; No leaves the countdown running. The dialog is modal, so ticks may run under it:
  the phase is looked at again when it returns, and a countdown that ended meanwhile is not cancelled (its timer is gone). A tap in the settle phase (capture
  committed) shows nothing.
- **Delay: 5 s or 10 s, on the dialog's buttons.** `confirminfo_dialog` has only `btn_cancel` (left, `tr_text msg_no`) and `btn_enter` (right, `msg_yes`);
  the check-box kinds (3, 6, 7) carry fixed texts, so no stock dialog offers three free choices and none is hooked. **Device finding (V2.1zGVNSAAAG): the back key does not close `confirminfo_dialog`**, so a single dialog with the delay on both buttons had no way out; hence the two steps. At step 2 `shot_start` adds a 10 ms
  stock timer (`shot_relabel`, `timer_add`) just before `pod_confirm_code` (the raw result of `pod_confirm`) opens the modal dialog; the main loop runs under
  the dialog, so the timer's first turn finds the window with `widget_lookup(window_manager(), "confirminfo_dialog", recursive)` and sets the two
  buttons' text (`widget_set_text_utf8`, after stock's own `widget_set_tr_text` at init) to "5 s" and "10 s", then ends. Until the dialog is found it repeats, at most
  `SHOT_RELABEL_TRIES` (20) times, then ends touching nothing; a refused timer leaves stock's Yes / No (Yes = 10 s). The result is the dialog's quit code: `btn_cancel`'s click
  handler `0x473230` is `dialog_quit(dialog, 4)`, `btn_enter` quits with `CONFIRM_YES` (0xa): 4 is 5 s, 0xa is 10 s, anything else is cancel. No new hook, pin or GOT slot.
  **Unverified on device:** the dialog is relabelled one timer turn after it opens (a first frame may show Yes / No). The
  Cancel dialog (during the countdown) is unchanged Yes / No.
- **Sequence.** A button on the first dialog adds a 1 s stock timer (`timer_add`
  `0x663530`, pinned) and shows the camera in the status bar (no toast: the dialog was the notice). The delay minus one ticks return `RET_REPEAT`; the last (the 5th or 10th) hides the camera (`widget_set_visible`, which invalidates it and relayouts the group)
  and returns `RET_OK`, which ends that timer, after arming a one-shot of `SHOT_SETTLE_MS` (120 ms, a few frames for the main loop to
  repaint). That one reads the panel, writes the file and then toasts "Screenshot saved", "Storage unavailable" (no card, no
  room, no directory) or "Screenshot failed" (the frame buffer, the number scan, a write): the toast follows the capture so it is not in
  the picture. A refused timer at either step is a failure toast with the camera hidden. The user leaves the Developer page during
  the countdown; the state is the payload's own, not the page's.
- **Why the frame buffer.** It is what is on screen: status bar, dialogs, Cover Flow's own drawing. `widget_take_snapshot_rect`
  (`0x671cb8`) repaints a widget tree into a new RGBA bitmap through `widget_paint_with_clip` and the window manager's paint,
  so its content depends on the widget handed in (the system bar is painted separately, `window_manager_paint_system_bar`
  `0x690b98`) and it re-runs page paint code. Stock opens `/dev/fb0` (string `0x74b3d8`) in `lcd_linux_fb_create`
  (`0x6393dc`, from `main_loop_init`), issues `FBIOGET_FSCREENINFO` `0x4602` (`0x63953c`) and `FBIOGET_VSCREENINFO` `0x4600`
  (`0x639558`), picks its `lcd_mem_*` class from the fields (16 bit with offsets 10 / 5 / 0 and a 1 bit alpha: `lcd_mem_bgra5551`;
  other 16 bit: `bgr565`; 24 and 32 bit have their own) and mmaps the node `PROT_READ|PROT_WRITE`. The payload does the same on its own
  descriptor (`open` read-only, the two ioctls, `mmap` `PROT_READ`, `MAP_SHARED`, then `munmap` and `close`), so the format is never
  assumed: it reads `xres`, `yres`, `bits_per_pixel` (16, 24 or 32), each channel's offset and length (4 to 8 bits, expanded by
  bit replication), `line_length`, `smem_len` and `yoffset` (the visible buffer when the driver pans between two). The frame must lie
  inside the mapping and be at most 1024 x 1024, or the capture fails instead of reading outside the memory. Unverified on the
  device: the actual format and size the panel reports (the tests run every format the driver can report).
- **File.** `/mnt/mmc/screenshots/shot-NNNN.bmp`, NNNN the first free number from 0001 to 9999 (a bounded `access` scan; none free is a
  failure). A 24 bit, bottom-up BMP (54 byte header, rows padded to 4 bytes; 460,854 bytes for 320 x 480), written to `shot.tmp` in the
  same directory one row at a time (a 3 KB stack buffer), `fsync`ed and `rename`d; any failure unlinks the temp file. Before
  anything is written: the card must be mounted (`statfs` of `/mnt/mmc` differs from `/mnt` in type or `f_fsid`), the directory is
  made (`mkdir`, existing is fine) and the card has `SHOT_MIN_FREE_MB` (16, as Cover Flow's cache) plus the file free.
- **Status bar camera.** `pod_shot`, a hidden, insensitive 16 px image (`pod_bar_shot`, Lucide `camera`, `tools/mod_icons.py`)
  that `tools/pod_ui.py add_shot_indicator` appends as the last child of `view_bar_right` in `ui/system_bar.bin` (the right-aligned icon
  group). The group's layouter skips an invisible child (`widget_get_children_for_layout` `0x657194`, `keep_invisible` off), so the
  bar is stock-laid-out while it is hidden; shown, it sits against the battery outline and the icons to its left move 20 px left. The
  payload finds it with `widget_lookup(window_manager(), "pod_shot", recursive)` each time it is needed (no pointer is kept); a missing
  widget only means no camera. The Bluetooth image `bar_bt` is 47 px wide but its glyph is the right 11 px, so
  with Bluetooth, SyncLink and Wi-Fi all lit the ink (the boxes would reach into a 12 h clock by a few px, the glyphs do not) stays clear of the 12 h and 24 h clock (`test/pod/shot.py` computes it). The
  pull-down's own bar is a different asset and gets no camera. A brief "saved" glyph in the same slot was left out: the toast already says
  it, and a second state would need a second timer and image for no new information.
- **Pins.** `timer_add`, `widget_lookup`, `widget_set_visible`, `window_manager` (`0x6774b4`), `locale_info_tr`, the stock message box
  (`navigator_to_with_context` `0x4d1d48` with `dialog/msginfo_dialog`) and demo's own GOT slots for `ioctl`, `mmap`, `munmap`, `statfs`,
  `mkdir`, `open`, `write`, `fsync`, `rename`; `tools/pod.py` checks every address and slot at build time.
- **Test.** `test/pod/shot.py`: the stock ioctl numbers and the node string read from `demo`; every format (RGB565, BGR565, BGRA5551, BGRA8888,
  RGBA8888, RGB888), row padding and a visible buffer at `yoffset` > 0 against exact BMP bytes, and the 320 x 480 file opened by Pillow;
  the order of calls (camera shown, hidden, grab armed, frame buffer opened, file renamed, toast); numbering; no card, low space,
  mkdir / statfs / open / write / fsync / rename failures and unreadable frame buffers (no file, no temp, descriptor and mapping released);
  double taps; refused timers; a missing camera widget; every text in all 16 tables.
