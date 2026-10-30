# The virtual iPod Classic (`patch/ipod.c`)

A fullscreen page that looks and steers like an iPod Classic: the iPod screen on the upper 240 px, a touch click wheel on the lower 240 px. Entry: the
**Pod** item of the M1+ Music menu (hidden by default, like Now Playing; named Pod, not iPod, on the device; the code keeps `ipod` / `IP_*`). Source: `patch/ipod.c`, the asset `ui/m1plus_ipod.bin` (`tools/pod_ui.py`
`build_ipod_page`), the wheel picture `ipod_wheel.png` (`tools/mod_icons.py` `ipod_wheel`), the numbers `IP_*` in `patch/offsets.inc`, tests
`test/pod/ipod.py`. The look is the approved mock `tools/preview_ipod.py` frames 1-4 (classic light look). **Not seen on a device** (see the checklist).

No new hook, nothing at boot, nothing in paint or the main loop beyond what the safety rules list. The page uses only what Albums, Songs, the mini
player bar and Cover Flow already use: a window opened with `window_open`, one view's own `EVT_AFTER_PAINT`, the pointer events of a view with
`widget_grab`, the window's `EVT_WINDOW_TO_BG` / `TO_FG` / `EVT_DESTROY`, and **one page-scoped timer**.

## Layout (320 x 480, `IP_*`)

- **The window** is `fullscreen = true`, as the lock screen's `screensaver_page`: 480 px, the stock status bar is not drawn (the bar window is still
  alive; the page reads its battery, below). Colour `#C6C9CE`, the wheel body. No close animation.
- **The screen** `ipod_screen` (320 x 240, insensitive: it takes no touch; the payload paints it). A 24 px title bar (vertical gradient `#F4F5F7` to
  `#B4B8C0`, a hairline under it), eight 27 px rows (24 + 8 x 27 = 240). Painted by `ip_on_paint` with `canvas_fill_rect`, `canvas_draw_text_in_rect` (the
  text styles are seven hidden labels in the asset, `label_ip_*`: 17 px rows, white on the selection, a left-aligned 16 px title, 14 px grey small
  text, 18 / 16 px Now Playing lines, a right-aligned time) and `canvas_draw_image` for the cover. Every text is cut with an ellipsis (the Albums grid's
  search) to its box, measured by the canvas' own font.
- **Title bar**, as the iPod's (a photo of a real one): the title **on the left** (x 8: `M1+ Music` on the main menu, the list's name, `Cover Flow`, `Now Playing`), **no clock**, and on the right the
  play-state glyph (a triangle while playing, two bars paused, nothing otherwise: `mclGetPlayStatus`; in the selection's blue, a row at a time down its gradient) 6 px left of the battery. One centre line
  (rows 7 .. 16, the battery's): the glyphs are 10 px from y 7 and the text box starts at y 1, because AWTK's metric centring put the caps 1 px high on the device (screenshot shot-0014).
- **Battery:** read from the real status bar, no new stock function: `*system_bar` (`0xa06f90`, the window the app keeps) holds `pgbar_battery` (its `value`,
  0 / 20 / 40 / 60 / 80 / 100) and `img_battery` (`bar_charge` while charging). The glyph is drawn with fills: a 20 x 9 outline, a green fill of `value` %, red at
  20 % or less, green and bright while charging. No bar (the pointer is NULL): no fill.
- **Selection:** the classic blue gradient `#5FB1F7` to `#0C62D2` over the whole row (27 line fills), white text, a white chevron; as the iPod, only the selected row has a chevron
  (other rows: black text, no chevron). A track row has none.
- **Main menu** (the 6G split screen): the list in x 0 .. 180 (`IP_SPLIT_X`), a hairline, and the right pane (181 .. 320 x 24 .. 240, 139 x 216 px: `IP_PANE_X/W/H`) with the
  **cover pane** (q2-pod's pan: "The cover pane", below).
- **Now Playing screen:** the 112 px cover (`IP_ART`, of the playing track) at (12, 36), title (18 px), artist, album (16 px grey), `n / N` (the place in the queue; the translation table allows one
  `%d` a text, so no "n of N"), a 10 px progress bar (blue gradient on `#D4D6DA`, y 188) with the elapsed time under its left end and `-m:ss` under its right
  (`get_playtimeandlength`, seconds). Nothing queued: `Not Playing`.
- **The wheel** `ipod_wheel` (view 220 x 220 at (50, 250), the touch target) with the picture `ipod_wheel` as an insensitive image child (decorative overlays
  never take a touch): a light ring, a 90 px centre button, `MENU`, `|<<`, `>>|`, `>||` drawn in; the corners are transparent. The view is square, so the payload does the
  circle's hit test (touch outside radius 110: ignored, no grab). The window is 480 tall; wheel + margins fit the lower 240.

## The wheel

Touch events come from the wheel view's `EVT_POINTER_DOWN / MOVE / UP / ABORT` (`widget_on`, as Cover Flow's input layer); the view is grabbed
(`widget_grab(window, wheel)`) for the touch so moves and the release arrive wherever the finger goes. Positions are `widget_to_local` (demo's own) minus the
centre (110, 110).

- **Regions:** radius < 45 (`IP_HUB_R`): the centre button; 45 .. 110: the ring; beyond: nothing.
- **Angle:** `ip_angle(dx, dy)` = degrees clockwise from 12 o'clock in sixteenths, pure integer code: `atan(x) = x / (1 + 0.28125 x^2)` on the octant (error under
  0.2 degree on large coordinates; the test compares it with `math.atan2` at 1,800 points and the pixel rounding of a small radius allows 1.5 degrees). `ip_turn(a, b)` is the
  shorter way round, so crossing 12 o'clock is smooth.
- **Step: one row per 15 degrees** (`IP_STEP` = 240 sixteenths, 24 steps a turn; the one constant to tune on the device, 288 = 18 degrees was the first guess). The unspent
  turn accumulates (`ip.acc`, signed, sixteenths of a degree); a step fires every time it passes +-`IP_STEP`, the **leftover carries** into the next step, and a new touch, a push or a pop
  of a level (`ip_wheel_reset`) clears it. The cursor moves, **no wrap** (the iPod stops at the ends; clamped: the hard stop below), and the window of 8 rows
  follows it (`top` is the first row shown; the cursor never leaves it).
- **Chord dead zone** (`ip_chord_near`, `IP_DEAD_R` = 11 px, 10 % of the 110 px ring): a move is rejected (no accumulation, the reference angle is taken again from the new
  point, the speed reset) when the straight line from the previous touch point to this one passes closer than 11 px to the centre, or ends there. Integer: `|a x b|^2 < R^2 |b - a|^2`
  for a closest point inside the segment, else the nearer end's `x^2 + y^2 < R^2`; coordinates are clamped to +-150 so the square fits 32 bits. A drag that **began** on the centre
  button (`R_CENTRE`) still turns nothing. (This replaces the old 18 px point test.)
- **Reversal hysteresis** (`IP_REVERSE` = 128 sixteenths = 8 degrees): the drag keeps a committed direction (`ip.dir`). Travel the other way is swallowed (`ip.rev`) until it reaches 8
  degrees; only then the direction flips, the accumulator restarts at 0 and the speed is reset, so the first reverse step comes after 8 + 15 degrees. Travel back in the committed
  direction first takes the swallowed travel back, so a small jitter at the turnaround nets zero and moves nothing.
- **Acceleration, long lists only** (`ip_turn_move`, `ip_tier_rows`): a list of more than `IP_LONG` = 16 rows (Songs, Albums, Artists, long playlists) climbs tiers; 16 rows or fewer
  (the main menu, a short album) always move one row a step. The angular speed (sixteenths of a degree a second, from the event times) is clamped at `IP_VMAX` = 6400 (400 degrees a second) and smoothed `v += (instant - v) * 3 / 20`
  (0.15; `IP_SMOOTH_NUM` / `IP_SMOOTH_DEN`). A gap over `IP_PAUSE_MS` = 250 ms between two moves, or a reversal, sets it to 0. While `v` is above `IP_FAST` = 2880 (180 degrees a second) the tier index is the time
  held above it divided by `IP_TIER_MS` = 500 ms; rows a step by tier: **1, 2, 3, 5, 8, 13, 21, 34** (the last holds). Below `IP_FAST` the tier is 0 at once. These numbers (tiers, the 400 degrees a second clamp, the 0.15 smoothing, 180 degrees a second, 500 ms, 250 ms) follow the Apple Music 404-page iPod's; numbers only, the code is ours. At 375 degrees a second the first 2-row step comes about 0.6 s into the turn (the smoothed speed passes 180 on the 5th move).
- **Hard stop at the ends:** a step that wanted to go past the first or last row clamps there and nothing else happens: no wrap, no bump, no animation, the timer untouched,
  as the iPod (and the Apple Music 404 page iPod). An end-of-list bump (10 px, iOS-style overscroll, on the page's timer) was tried in test build V2.1oPJ and removed: on the
  device it felt bouncy, not like an iPod.
- **Tap:** a touch that turned no step and travelled less than 12 px (`IP_TAP_PX`) is a tap. On the centre button: **select**. On the ring, by where it began:
  the top sector (|dy| > |dx|, up) **MENU** (back; on the main menu it closes the page: `navigator_back`), the bottom sector **play / pause**
  (`playpause_quick_click`), the left sector **previous** (`prev_quick_click(e, 0)`), the right sector **next** (`next_quick_click(e, 0)`); the two skip calls read the
  event's time (stock ignores a click within a second of the last). A drag that began on the centre button turns nothing and is no tap. An abort (a window above, the
  scroll hook's abort) ends the touch and acts on nothing.
- **On Now Playing rotation does nothing** and select is play / pause: the iPod's centre-press cycle (scrubber with seek tiers of 1, 2, 3, 5 s a step, shuffle, rating; wheel volume on the default
  screen) was **not built**, because the stock setters cannot be called safely from here with the evidence at hand (findings below, "Now Playing: the iPod's cycle, why not").

## The cover pane (q2-pod's pan)

The 6G iPod's main menu shows album art in the right pane, edge to edge, moving slowly. Test build V2.1oSIP had a Ken Burns slideshow here (random covers, a pan and zoom of a 168 px
source window scaled into the pane every 80 ms, crossfades): on the device the covers jiggled, because a window whose size and place change every frame is resampled
differently each time, and even a pure pan at a 1.29 scale jumps 1 or 2 screen pixels a source pixel. It was replaced by **q2-pod's Split Home pan** (MIT, `patch/coverflow.c`
`home_fit` / `home_drift`, its docs/ipod.md "Home"; numbers and design borrowed, the code is ours). All on the page's **one timer** (`ip_tick`); no hook, no event, no new timer; paint only copies.

- **Pane:** x 181 .. 320, y 24 .. 240 (139 x 216; the 180 split and the hairline are unchanged).
- **Which cover** (`ip_pane_want`): the **playing album's** (`cc_playing`, `cc_album_key`) when its Cover Flow cache file holds a picture (`cc_url`: `/mnt/mmc/.m1plus/covers/<key>-168.jpg`, not the empty
  "no art" marker; one file test each time the playing album changes); else a **random album's** cached cover (`ip_pane_pick`: `loadLocalClassList(0xf003)`, up to `IP_PANE_TRIES` = 48 random rows,
  `pod_rand`; drawn once a visit of the main menu, `ip_pane_reset`: MENU from a level, the window coming back, open; q2-pod shows its placeholder here instead); else the stock disc (`p_default`), still.
  Only covers already in the cache are used (Cover Flow and the Albums page build it).
- **Decode** (`ip_pane_decode`, on its own tick, never in paint): `cc_decode` of the 168 px cache file **straight to `IP_PANE_ART` = 238** (the pane's 216 px height zoomed 110%, q2-pod's `DRIFT_ZOOM_PCT`;
  `cc_box` averages the source pixels each destination box covers) into one 238 x 238 RGBA bitmap of the page's own (made on first use, freed at destroy; 227 KB). Once per cover: a new cover only when the
  wanted album changes. A file that does not decode: the disc (and it is not tried again each tick).
- **Pan** (`ip_drift_at`, q2-pod's `drift_at`): each axis a linear ping-pong across the zoom's margin, `IP_PANE_R` = 22 px, from the centred crop; a sweep takes `IP_DRIFT_X_MS` = 20 s across and
  `IP_DRIFT_Y_MS` = 26 s down (about a pixel a second). The phase (`ip.pane.ms`) counts only time shown: each tick adds the time since the last one (`time_now_ms`), at most `IP_DRIFT_MAX_MS` = 250, so a stall
  or the page coming back never jumps; a new cover keeps the phase. The disc stands still in the middle.
- **Paint** (`ip_paint_pane`): `canvas_draw_image(canvas, bitmap, src, dst)` with src = a 139 x 216 window at (38 + x, y) and dst = the pane, **the same size: a copy, nothing scaled**, so the picture is the
  same pixels every frame and only moves a whole pixel at a time (`test/awtk_fill.py` proves with demo's own code that a same-size window is copied pixel for pixel at any offset). The crossfade's pin
  (`canvas_set_global_alpha`) went with the slideshow.
- **The timer's interval** (`ip_retime`, `timer_modify` `0x663840`: it sets the timer's duration and restarts its clock, nothing else; the timer is never removed or added): `IP_DRIFT_MS` (100 ms, q2-pod's
  `DRIFT_TICK_MS`) **only while the main menu is the level, the page is in front (`ip.fg`) and it is the top window (`pod_is_top`) and the pane shows a cover or is still being made**; `IP_TICK_MS` (500 ms)
  on every other level, with a window above (a message box), with the disc, and after `EVT_WINDOW_TO_BG` (the timer is removed then, as before). While it ticks fast, the battery / play state / track look
  runs every `IP_DRIFT_LOOK` = 5 ticks. A tick that moves no pixel repaints nothing; a moved pixel repaints the whole 320 x 240 screen view (`widget_invalidate_force`; its rectangle argument is not used by
  this build: `0x6691d0` takes only the widget), about twice a second.
- The cover of the **playing track** for the Now Playing level is decoded separately (`ip_cover`, 112 px), as before.

## Levels and the stock library

A stack of at most 6 levels (`IP_DEPTH`): main menu -> Settings (a static list, below) or Albums / Artists / Songs / Playlists -> an artist's albums -> an album's or a playlist's tracks -> Now Playing.
A list level keeps only its cursor (`sel`, `top`); its rows are read from the **stock list** while it is the one the stock queries last made (`ip_valid`: the
pointer, the size, the first record, as the Songs page checks). The queries are the ones the stock pages and our other pages run (`docs/modules/addresses.md`):

| level | query | rows |
|---|---|---|
| Albums | `loadLocalClassList(0xf003)` | `REC_ALBUM` |
| Artists | `loadLocalClassList(0xf004)` (the stock Artist / Album Artist setting applies) | `REC_TITLE` |
| an artist's albums | the artists query, then `loadAlbumList(0xf004, the artist's record)` (class `0xff01`) | `REC_ALBUM`; the stock last "All songs" row as `All albums` |
| an album's tracks | the albums (or the artist's albums) query, then `loadAlbumdetailList(0xf003 or 0xff01, the album's record)` (pinned: its second argument is the album **record**, not a row number); `g_class_type` = classinfo[0] (`0xff10` / `0xff11`) as `albuminfo_page_init` leaves it | title, else file name |
| Songs | `loadLocalClassList(0xf001)` (the stock sort order, `sort_flag`) | title, else file name |
| Playlists | `loadLocalClassList(0xf00b)` into `*pdeq_playlist` | `REC_TITLE` |
| a playlist's tracks | the playlists query, `classinfo[1]` = the playlist's id (`REC_DISC`), `loadLocalClassList(0xff13)` | title, else file name |

Going back (MENU) **runs the chain of queries again** (a child's query replaces the parent's list), keeping each level's cursor. The rule of `docs/modules/payload.md`
holds: stock queries run only from the page in front: its open, a wheel step or tap, its window coming back to the front (`EVT_WINDOW_TO_FG`), and the page's tick **only
while the page is the top normal window** (`pod_is_top`; the Songs page's stale timer). **Paint never queries and never reads a stale list** (it draws no rows
until the tick or the next action reads it again).

**Play:** a track in a track list does what the stock Songs row does (`loadSongList` of the shown list, the row's own index winning over a duplicate file name) and then
`start_player(queue, index, class, PLAY_MODE)` + `force_refreshflag = 1`, exactly what the stock album page's Play all button does (`0x525d48`; the page stays where it is, the
queue is copied). No stock Now Playing page opens: the iPod page pushes its own Now Playing level. A file that is gone: the stock message box, nothing starts.

**Cover Flow** is the iPod's own screen (level `K_CF`, `docs/modules/ipod-coverflow.md`; the existing page only when its memory is refused). **Opens an existing page:** only
the Settings list's last row (the Settings page, `pod_open_settings`, below).

**Shuffle Songs** (`ip_shuffle_all`) stays on the iPod page: `loadLocalClassList(0xf001)` (the Songs query), a random row (`pod_rand`, the Shuffle page's generator) is the first song, then
`ip_play` as for a tapped track with one addition: `pod_set_mode(MODE_SHUFFLE)` (`patch/shuffle.c`: `mclSetPlayMode(2)`, `notifyPlayMode`, `dmrSendPlayMode`, `write_int_config`, exactly the Play settings
page's sequence, nothing written when the mode is already 2) before `start_player`. The queue is the whole library, stock Shuffle draws the following songs from the unplayed pool, and the
iPod's Now Playing level opens (no stock page). An empty library: the stock message `Update Local Music first`; a missing first file: `Storage unavailable`; the mode is then untouched.

## Settings (a list level)

The main menu's **Settings** row pushes `K_SETTINGS`, a static list of four rows (no stock query, no list state). A row with a value shows it **right aligned (to x 310) instead of a chevron**
(the label is cut before it); the centre press changes it. Only settings that code already sets are here:

| row | value | centre press |
|---|---|---|
| Shuffle | `Off` / `Songs` (play mode 2) | `pod_set_mode(MODE_SHUFFLE)`; on `pod_set_in_order()` (List play, or Repeat all kept) |
| Repeat | `Off` / `One` (mode 1) / `All` (mode 3) | cycles Off -> One -> All -> Off with `pod_set_mode` |
| About | the version tag (`M1PLUS_TAG`, the `TAG` of `tools/build.py`, compiled in by `tools/pod.py`; the stock About page shows the same) | nothing |
| Customize (chevron) | | `pod_open_settings()`: our Customize page, Back returns here |

Shuffle and Repeat are **one stock setting** (the play mode 0 List play, 1 Repeat one, 2 Shuffle, 3 Repeat all; shuffle mode has no repeat of its own), so turning Repeat on turns Shuffle off and the
reverse; Repeat reads `Off` in Shuffle mode. The iPod's Shuffle `Albums` value is not offered (stock has no such mode: Shuffle Albums is a queue order, `patch/shuffle.c`). No backlight or other settings:
their setters are not pinned in this payload. Keys: `Shuffle`, `Songs`, `Off`, `Repeat`, `One`, `All`, `About` (our keys, 13 languages, `tools/pod_i18n.py`), the last row is the shared `Customize` key, the row title the stock `cdrippersettings`.
The items count was left out (a library query for a number nobody asked for).

## Entry and exit

- Entry: `ACT_IPOD` (22), the menu item id 19 (`pod_pages.ITEMS`, after Customize, saved as `k`, hidden by default: Customize > Main Menu shows it, the Extras page lists it (Play group)
  with the default menu's items). The label is the name `Pod`, a plain text in every language (like `M1+ Music`); no translation key.
- Exit: MENU on the main menu (`navigator_back`; the stock window under it and its status bar come back). There is no hardware back key in this payload (the stock key handler
  `on_wm_keyup_fun` handles the media keys; nothing here changes it).
- Open again while up: nothing. A window that will not open, an asset missing a widget: the page returns -1 and leaves what it did not make.

## Timer and the page's life

`ip_first` (50 ms one-shot) starts `ip_tick` (`IP_DRIFT_MS` on the main menu, else 500 ms; `ip_retime` changes it with `timer_modify`, above). The tick steps the cover pane (`ip_pane_step`) and looks at the battery, the play state, the playing track, the position (on Now Playing) and the
queue size; a change repaints the screen. A new track makes the cover (the decode is on the timer, never in paint: the Cover Flow cache file via `cc_url`, else the `/tmp`
file demo writes a little after the track changes, else the stock disc). The timer goes on `EVT_WINDOW_TO_BG` and returns on `TO_FG` (which also reads the list again); destroy removes it
and frees the cover. State is one struct in `.scratch`, cleared at open and destroy; a destroy of another window leaves the page alone.

## Now Playing: the iPod's cycle, why not

The wish: centre press on Now Playing cycles default -> scrubber (the wheel seeks 1, 2, 3, 5 s a step) -> shuffle -> rating; on the default screen the wheel changes the volume. Candidates found in the stock `demo`
(`tools/stock.py`, `tools/dis.py`), none of them used:

- **Seek:** `seek_time(int secs)` `0x4e0544` (a0 + the playing record's cue start at `+0x48` -> `dmrSendPause`, `mclSetSeek` `0x5d26dc`; paused (status 3) also `set_outputchannel` + `mclSetResume`; then a **busy loop of up to 200
  x `usleep(10000)`** polling `get_playtimeandlength` until the position is within 1 s of the target, then `dmrSendPlay`). The loop **blocks the UI thread for up to 2 s** (per call; a wheel step is a call), which is
  what the stock progress bar does on release, not 12 times a second. `mclSetSeek` alone does not block, but skips the DLNA / pause handshake the stock path does and has had no hardware test. The position to seek
  from is `get_playtimeandlength` (whole seconds), so 1 s steps would also race the player's own position updates. Needs a design (seek on release of the finger, not per step) and a device test of gapless, DSD, CUE and
  Bluetooth playback; a bad seek can leave `hciplayer` paused.
- **Volume:** `set_devicevolume(int 0..100)` `0x4d6cf8` branches on the output way (`mclGetOutputWay`: wired `mclSetVol`, USB DAC `mclUsbAudioSetVol`, AirPlay `airplaySendVol`, Bluetooth with the `bt_recv_volume`
  scaling), then `notifyVolume` `0x50ef5c` and the DLNA volume send (`0x4f1050`). The volume it sets is not returned by it: the current value lives in more than one data word (`volume` `0x97cb10`, `btsource_volume`, `max_volume`, the BT
  device's own) and the stock volume dialog (`dialog_volume_dialog_init` `0x47e41c`, `on_volume_tsup_fun` `0x47dd9c`) also keeps the on-screen overlay in step. A wheel that sets it blindly could jump the level
  in the headphones on a high-gain output; the stock volume keys are the only tested path.
- **Shuffle / rating** items of the cycle would be the Settings rows' play mode (done there) and a rating (no stock rating exists; Favorites is the only mark).
- Verdict: the scrubber and wheel volume each need a hardware-tested design; nothing built, so nothing can wedge playback or blast a volume. The first step would be to read `volume` back safely and to call
  `mclSetSeek` once on release; both need a device log first.

## The click sound: not implemented, on purpose

The brief wanted a tick on every wheel step and select. Research (stock `demo`, `hciplayer`, the rootfs):

- **No stock key tone.** `demo` has no key-tone, beep, click-sound or sound-effect strings or files (`tools/stock.py strings` for keytone, key_tone, keysound, beep,
  click_sound, touchsound, tone, buzz: nothing; the only `.wav` strings are the file-type table and `process_wav_files`). It does not open a PCM device: its ALSA
  imports are `snd_ctl_*` / `snd_hctl_*` (the mixer: volume), `system`, `popen`, `fork` and `execl` exist as imports.
- **Audio is owned by `hciplayer`**, an MPlayer 1.3 fork started as `nice -n -5 hciplayer -ao alsa &` (`mclWaitAccept`). Its ALSA output calls `snd_pcm_open`
  on `hw:1,0` / `hw:2,0` or `surround*` devices (Bluetooth: `plug:bluealsa`), sets the **file's exact rate and format**, and closes the PCM at `alsa-uninit` (between
  tracks, stop, seek). The rootfs has **no `/etc/asound.conf`**: the default PCM is the card's own (no `dmix`), so a second process opening the same playback device either
  fails (while a track plays) or, **in the gaps where hciplayer has the device closed** (paused, between tracks, stopped, just before a track starts), succeeds and then makes
  hciplayer's next `snd_pcm_open` fail with EBUSY. A click that races a track start is exactly the case that wedges playback; the PCM open also powers the DAC and amp (a pop
  in the headphones at every tick, on a device with a bit-perfect and DSD path).
- The only ways to make a sound from `demo` are a process spawn (`system("aplay file.wav")`; `/usr/bin/aplay` exists) or a new libc/ALSA import; both are new code paths with the
  race above, and a process per wheel step is 20 spawns a turn. Patching `hciplayer` is deferred (`AGENTS.md`).

**Decision: no sound.** Everything else is in. What a sound would need, in order of preference: (1) a mixing PCM for the system: an `asound.conf` with a `dmix` default over the
card, a change of `hciplayer`'s device choice and a device test of gapless, DSD and USB-DAC modes (an audio-path change, not a UI one); (2) a short click mixed into `hciplayer`'s
output (`hciplayer` patch: deferred); (3) haptics: the board has no vibrator that `demo` drives. Until one of these is chosen a tick cannot be made safe.

### The clicker, when the audio path allows it (design only, nothing built)

A setting **Clicker** On / Off, default **On**. A click is a ~3 ms transient (a short decaying burst, a few hundred samples at the output rate, quiet), at most **one per 50 ms**,
**one per row actually moved** (a multi-row tier step is one click; a clamped step at an end makes none), plus the select tap, and **skipped while the PCM is closed**
(paused, between tracks, stopped: opening it would race `hciplayer`, above). It must come from the audio owner (options 1 or 2 above), not from `demo`.

## Research sources (ideas and constants only, no code)

- **Apple's Music 404-page iPod** (a web page that mimics the wheel): the ideas of a reversal threshold, a dead zone judged on the chord of a move rather than the point, a
  smoothed angular speed with a threshold, tiers of rows per step that climb with the time held fast, and a nudge at the end of a list. Its code is proprietary: nothing is
  copied, and only its numbers are followed (tiers 1, 2, 3, 5, 8, 13, 21, 34; speed clamp 400 degrees a second; smoothing 0.15; 180 degrees a second; 500 ms a tier; 250 ms reset).
- **q2-pod** (MIT, `patch/navigation.c`, read for its end bump): nothing was borrowed (the bump tried here was our own, and is gone).
  `NOTICE` is unchanged for this reason.

## Addresses used

Pinned in `tools/pod.py`: `prev_quick_click` `0x4cccb0` (the twin of `next_quick_click`; prologue, the `e->time` read and the 1 s guard pinned), `loadAlbumdetailList` `0x4eea98`
(prologue, the Albums class compare, the record argument), `timer_modify` `0x663840` (prologue, the duration store `sw s1, 0x40(s0)`), the data word `system_bar` `0xa06f90` (checked against `.dynsym`). Already pinned and used: `window_open`, `widget_grab` /
`widget_ungrab`, `widget_to_local`, `widget_prepare_text_style`, `canvas_fill_rect`, `canvas_set_fill_color`, `canvas_draw_text_in_rect`, `canvas_measure_text`, `canvas_draw_image`,
`tk_utf8_to_utf16_ex`, `loadLocalClassList`, `loadAlbumList`, `loadSongList`, `start_player`, `force_refreshflag`, `playpause_quick_click`, `next_quick_click`, `mclGetPlayStatus`,
`mclGetPlayPos`, `get_playtimeandlength`, `mclGetPlayMode` and the `patch/shuffle.c` setters (`pod_set_mode`, `pod_set_in_order`, `pod_rand`), `timer_add`, `timer_remove`, `bitmap_*`, libc `time` / `localtime`.

## Known limits

- Not run on a device: the canvas calls, the fullscreen window (the status bar must be hidden by `fullscreen`, as for the lock screen), the touch feel (the 15 degree step, the chord dead zone, the reversal and tier constants, the 12 px tap slop are guesses to tune), the cover pane's pan (its speed, the repaint cost) and Cover Flow's frame rate are only proven under emulation and with demo's own AWTK code (`test/awtk_fill.py`).
- The page timer's interval is set in one place (`ip_want_ms`: `IPCF_FRAME_MS` while Cover Flow slides or decodes, `IP_DRIFT_MS` while the cover pane pans, else `IP_TICK_MS`) and changed in place
  with `timer_modify`; the timer is never removed or added while the page lives.
- No sound (above). No rotation action on Now Playing (above), no scrubber. No cover flip in Cover Flow (the centre opens the tracks as a list). No search, no Genres,
  Composers or Folders, no Shuffle Albums value. The cover pane does not follow the row and shows only covers already in the Cover Flow cache (from its 168 px file, upscaled to 238). `tools/preview_ipod.py` still draws the old static pane.
- No clock in the title bar (the iPod's has none); a language with a very long `Shuffle Songs` is cut with an ellipsis (checked: all 13 fit the 148 px).
- Albums are in the stock query's order, not Settings > Cover Flow > Sort.
- The play queue is the stock one: `start_player` copies the shown list; a Songs list of thousands of rows is copied once per play, as the Songs page does.

## Device checklist

- Menu: Settings > Main Menu > Pod on; the Pod row opens the page; the status bar is gone (the page is 480 tall: nothing under the bottom edge); MENU closes it and the bar returns.
- Wheel: drag round the ring: one row per 15 degrees, both ways, the selection stops at the ends and never wraps, a hard stop with no bump (the music does not stutter); the window scrolls with the cursor in a long list; a drag across
  12 o'clock does not jump; a drag that starts on the centre button does nothing; a tap on the centre selects; taps on MENU / `|<<` / `>>|` / `>||` act; a touch in the square's corners does nothing.
- Feel (tune `IP_STEP` first): a slow turn is one row per 15 degrees (neither too jumpy nor too heavy; try 12 / 18); turning round at the end of a drag does not flicker the cursor
  (8 degrees of hysteresis; if the first reverse step feels late lower `IP_REVERSE`); a finger that crosses the centre does not jump the list; on Songs a fast sustained turn
  speeds up after about half a second (1, 2, 3, 5, 8, 13, 21, 34 rows), slowing or stopping brings one row back at once, a pause or turning back resets; a list of 16 rows or fewer never
  accelerates; at the first and last row the cursor stops dead (no bump, no wrap).
- Lists: Albums -> an album -> a track plays and Now Playing shows title, artist, album, `n / N`, the bar moves, the time counts; MENU returns to the tracks (same cursor); Artists -> albums
  -> tracks; Songs; Playlists -> tracks; Cover Flow and Settings open and Back returns; Shuffle Songs plays.
- Title bar: the title on the left, no clock; the battery agrees with the real one (charge it); the blue play glyph next to it follows play / pause.
- Cover pane: the cover fills the pane edge to edge and drifts about a pixel a second with **no jiggle** (the slideshow's fault in V2.1oSIP); it is the playing album's cover (play a track from a
  cached album, MENU back: it changes), else a random cached one, a new one after MENU back to the main menu; the wheel and music stay responsive; with no cover cache (never opened Cover Flow / Albums)
  the stock disc, still; the pane stops moving on every other level (the timer slows to 500 ms) and in a message box.
- Shuffle Songs: playback starts at a random song with shuffle on, the iPod's Now Playing shows it, Next picks another random song. Settings: Shuffle and Repeat values change on the centre press and agree with
  Customize > Playback, About shows the build tag, Customize opens our Customize page and Back returns.
- Idle: nothing queued shows `Not Playing`; the stock disc in Now Playing; sleep / wake and the lock screen do not leave the page broken; a language change re-draws in the new language.
- Music keeps playing (no glitch) while the wheel turns; the page leaves no timer (go to Home and back).
