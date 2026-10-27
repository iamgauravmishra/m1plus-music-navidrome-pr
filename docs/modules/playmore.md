# Now Playing's More menu (`patch/playmore.c`, `tools/mod_lists.py`, `test/pod/playmore.py`)

The sheet Now Playing's "..." button opens is the stock `dialog/playmore_dialog` (`ui/dialog/playmore_dialog.bin`, a 320 x 350 dialog at
y 130: `list_view` `playmore_listview` > `scroll_view` `playmore_scrollview` > `list_item` rows `listitem0..6`, the scroll bar
`scroll_bar_m`). Stock order and rows: A-B repeat (0, a switch `img_switch`), Playback speed (1, the badges `img_1x`, `img_1_25x`,
`img_1_5x`, `img_2x` and `label1_msg`), Add to playlist (2), Online search (3), Look up album (4), Look up artist (5), Delete song (6).
M1+ Pod makes it an iOS style bottom sheet with two pages.

Preview, both pages over Now Playing with the dim: `venv/bin/python -I tools/preview_playmore.py work/mod-release out/preview/playmore.png` (not tracked).

## What the user sees

- **A bottom sheet.** The sheet is 4 rows x 50 = **200 px** on both pages and sits on the bottom of the screen (y 280, bottom 480). The page above it is
  dimmed (the AWTK dialog highlighter, below). A tap above the sheet closes it (stock behaviour, see "Positioning"); a tap on the sheet does not.
- **Page 1** (when it opens, every time): Look up album (`listitem4`), Look up artist (5), Add to playlist (2) and **More** (`pod_more`: the Extras
  ellipsis glyph, the label, the stock grey chevron-right `right_arrow` at its right).
- **Page 2** (a tap on More): a header row **< More** (`pod_back`: the stock chevron-left `return`, the label "More"; a tap returns to page 1), then
  Playback speed (1), A-B repeat (0) and **Delete song** (6, its label red `#FF5A4F`). The stock rows keep their own handlers (speed badges,
  A-B switch, delete, add to playlist, look up album / artist): the payload moves rows, it replaces no behaviour. Switching only swaps which
  rows are visible and sensitive: the sheet never resizes, there is no slide.
- **Online search** (3) is never shown (`visible=false` and `sensitive=false`).
- **Playback speed's row.** The stock label box is 60 px wide (the badges start at x 122), so "Multiple Speed" was cut. The label now reads **Speed**
  (our key `Speed`, set by the payload after the stock binder wrote `player_multiple`; 13 translations, `tools/pod_i18n.py`), its box is 96 px
  (x 48..144), and the four badges moved right (x 148, 188, 228, 268, 36 px each, 40 px apart, the last ends at 304 of the 310 px row).
  The note under it (`label1_msg`, 14 px; stock "*Affecting only files below 48khz", 138 px wide and cut in most languages) reads **Files below 48 kHz only**
  (our key, 13 translations) in a 262 px box: it fits in all 13 languages (test), so it stays visible.
- The stock layouter keeps a row's own height: the asset has Look up artist (5) and Delete (6) at 60 px (stock: 370 px of rows in the 350 px sheet, so
  the stock list scrolled by 20 px). The payload resizes every row to `PM_ROW_H` 50, so both pages are exact and nothing scrolls.
- The red: `#FF5A4F` is 6.8:1 on the black sheet and 4.85:1 on the pressed row (`#362221`; a label in a pressed row keeps its normal state, which is how
  `tools/mod_theme.py --scan` counts it). The Delete glyph (`p_delete`) stays white.

## Positioning (the bottom sheet)

The dialog's coordinates are the screen's (the window manager sits at 0,0 and is 320 x 480; stock 130 + 350 ends at 480). The stock init moves the
dialog to y 130 (`widget_move(dialog, 0, 130)`, `0x479d10`, pinned); `pm_arrange` moves it to `PM_SCREEN_H - 200` = 280 after the stock init and resizes
it to 320 x 200 (the list_view's `self_layout` `h=100%` follows). Pins touched: none changed; added read-only pins `0x479ce0` (the stock init binds
`EVT_WINDOW_TO_BG 0x12c` to `0x4789f0`) and `0x478a1c` (that handler's `widget_move(dialog, 0, 130)`), next to the existing `0x478ac8` / `0x478acc`.

- **Tap above closes.** The stock handler `0x478abc` (bound to `EVT_POINTER_UP` by the stock init, kept) compares the pointer's y with `dialog->y` and
  closes when it is smaller. With the sheet at y 280 that is exactly "a tap above the sheet": nothing of ours is involved (the old `pm_on_up`, which
  closed on a tap *below* a top-anchored short sheet, is gone: the sheet touches the bottom edge).
- **Another dialog opens over it** (Delete's confirm): the window manager sends `EVT_WINDOW_TO_BG` and the stock handler `0x4789f0` moves the dialog back to
  y 130, which would drop the sheet in mid screen. The payload binds its own handler for the same event after the stock one (handlers run in
  registration order) and puts the sheet back on the bottom in the same dispatch, before any paint. (The stock init also adds a 200 ms timer, `0x478a48`,
  that moves the dialog to y 130 when `scr_rotateflag` is set: a screen rotation, which this firmware's UI does not do while a dialog is open; not handled.)
- **The dim** is the dialog's own `highlight` property in the asset, `highlight="default(alpha=130)"`: the stock window manager (the function at `0x690100`, its
  `widget_get_prop(dialog, "highlight")` at `0x6901c4`) reads it when the dialog opens and builds the "default" dialog highlighter (registered at tk init, `0x68e8bc`) with `dialog_highlighter_factory`,
  which draws the page under the dialog dimmed by that alpha; no widget is added and no touch is involved (a highlighter paints, it does not hit-test). The
  stock dialogs of this app never set one (their init calls `set_dialog_highlight`, `0x4cd344`, with an empty string), and the highlight has to be in the
  asset: the navigator runs the dialog's init after `window_open_and_close` (`0x4d0158`), too late for the window manager's setup. With the kill switch the
  asset's look stays (the dim over the stock menu), as for every look step. **Not verifiable in the emulator (a paint path): check on the device.**

## The hook

`dialog_playmore_dialog_init` `0x479cc4`, pinned prologue `(0x3c1c0059, 0x279ca20c, 0x0399e021)` (`$gp` checked), overwritten with
`j m1pod_playmore_init; nop`; the trampoline resumes at `0x479cd0` (`beqz $a0`). It is called only by the navigator's dialog-init dispatcher
(`0x4d1244` / `0x4d124c`, behind the `strcmp` with `"dialog/playmore_dialog"` `0x749f78`), when the sheet is built; `tools/reach.py` finds it
only behind the navigator cut (`0x4d00c0`), so it never runs at boot or in the main loop. `tools/pod.py` `PLAYMORE_PINS` also pins the dispatcher's
words and the stock handlers' words (above). The stock init (it binds every row and badge through the `widget_foreach` visitor `0x478b44`, sets the
texts, binds the to-background and tap-above handlers, moves the sheet to y 130) runs first and its result is returned; then, unless the kill switch
`/mnt/mmc/m1pod-off` exists, `pm_start` looks up the dialog's widgets by name and checks the asset is the one it knows (nine rows under the scroll_view,
each row's parent, the four labels), sets the texts (`widget_set_tr_text`: `More` twice, `Speed`, `Files below 48 kHz only`) and registers four
handlers (the More row's and the back header's `EVT_CLICK`, the dialog's `EVT_DESTROY` and `EVT_WINDOW_TO_BG`). **Everything fallible happens before the
first row moves**; any failure leaves the stock seven rows (`pod_more` and `pod_back` are `visible=false` and `sensitive=false` in the asset, so they do
not show; a text already set stays, and fits the stock label). The state is one `.scratch` struct (handles, `page`), cleared by the destroy handler; each
handler checks that its context is the dialog the state belongs to, so a handler a failed start left behind does nothing.

`pm_arrange` (open, and every page switch): every row `widget_resize(310, 50)` and back to the `normal` state (the row whose click switched the page
is hidden by its own click); the page's four rows `widget_move(0, position x 50)` and shown; the other five `widget_move(0, 200)` (parked under the sheet) and
hidden (`visible=false` **and** `sensitive=false`: a hidden widget would still take touches); the children `widget_restack`ed shown rows first, hidden last
(the stock list_view layouter re-stacks the visible children in child order at every relayout and gives each `y` = the sum of the heights above,
`docs/modules/home-guard.md` "The stock list code under the menu's hand-placed rows", so the order survives it); the dialog, list_view (320),
scroll_view (310) and scroll bar (10 wide) `widget_resize`d to 200, the dialog moved to y 280, `virtual_h` 200, `yoffset` 0, the dialog invalidated before
and after.

## Assets (`tools/mod_lists.py` `edit_playmore`, both asset themes)

`ui/dialog/playmore_dialog.bin` exists in `default` and `theme1` (the A-B label 20 px narrower there); both get the same edit, and `build_ui` asserts that
every stock widget keeps its type, name and rectangle (`ADD_EDITS`: only the `pod_more*` / `pod_back*` widgets are new, and the six speed row widgets of
`PM_SPEED` change their rectangle, asserted from the stock values). The dialog gets `highlight`. `pod_more` and `pod_back` are `list_item`s styled as the Add to
playlist row (`pod_back`: no hairline, it is the first row of its page), appended as the eighth and ninth children: `pod_more_icon` (24 x 24 at 14,13: the
Extras glyph `pod_ic_extras`), `pod_more_label` (`hscroll_label`, `srlabel_item_white_style`, 200 px at x 48, no text in the asset: the payload sets it) and
`pod_more_chev` (13 x 22 at 283,14, `right_arrow`); `pod_back_chev` (13 x 22 at 14,14, `return`) and `pod_back_label` (200 px at x 40). The pictures are
insensitive. No new image file. The hairlines follow the new order (Look up album and the back header, the first rows, have none; A-B repeat has one); with
the kill switch the stock order shows with those two hairlines and the red label. `scrlabel6` (Delete) takes the red as an inline text colour in every state.

## Findings

- **Delete asks first.** The stock Delete handler (`0x4791f4`, bound to `listitem6`) opens `dialog/confirminfo_dialog` with the text `msg_delsong`
  ("Delete Song?") through `navigator_to_with_context`; only on the dialog's yes (`0xa`) does it call `delete_playqueue_file(0)` and show
  `msg_delsongsuccess` / `msg_delsongfailed`. Nothing to add.
- **Sleep timer.** Stock has one: Settings > Power (`powermanager_page`, `on_powermanagertoplayer_onclick`): the row `listitem_sleep` ("Sleep Timer",
  `powerm_sleep`, `imgswitch_sleep`: a switch) with an hour / minute text selector (`tselector_hour`, `tselector_min`), the auto-shutdown countdown dialog
  `dialog/dialog_autoshutdown` (`msg_autoshutdown`, shown from `on_wm_idle_status`) and the SyncLink `GetAutoShutdown` / `SetAutoShutdown` messages. A More
  menu shortcut would open that page (or its dialog); not done here.

## Tests (`test/pod/playmore.py`)

The dialog is the built asset as real widget structs under demo's own window code (the `pulldown.py` machine): `widget_move` / `_resize` / `_set_visible` /
`_set_sensitive` / `_restack`, the list_view layouter (`window_manager_check_and_layout`), `widget_find_target` and the pointer path run unmocked, and so do
the stock to-background (`0x4789f0`) and tap-above (`0x478abc`) handlers. The stock init is run as far as its binding goes (the stock visitor per widget, the
two dialog handlers registered as the stock init does, in order), so `m.bound` / `m.reg` hold the stock handlers before the hook runs. Checks: the hook words,
pins and `$gp`; the premise of the dim (the window manager's `highlight` read and the registered `default` highlighter); the stock layout (the 60 px rows,
370 px); page 1 and page 2 order, visibility, sensitivity, stacking, heights, sheet size and y + h = 480; every stock handler unchanged and first in order and
only four added; hit tests per page (a tap lands on the row drawn there, no touch ever lands on a hidden widget, the badges and A-B are reachable only on
page 2, the page 1 rows only on page 1); More -> page 2, back header -> page 1 through real taps (list_item click -> our handler), relayouts on both pages,
repeated switching; the stock tap handler closing above the sheet and not on it, on both pages; the stock to-background handler followed by ours (the sheet
back on the bottom, the rows unmoved); destroy and reopen (starts on page 1); kill switch, stock failure, no dialog, each missing widget, wrong parent, 7, 8
or 10 children, each text and each bind failure: the stock menu, nothing moved, leftover handlers inert; the four texts in all 16 tables and their fit in 13
languages (More before its chevron, Speed in 96 px, the note in 262 px); both asset themes (stock widgets unchanged but the speed row, highlight, hidden
start, styles, red contrast, hairlines, the stock chevron images).

## Device check

Open More on Now Playing: the page above the sheet is dimmed (if not, the highlight is not taking effect: the paint path is the one thing the emulator cannot
show), four rows on the bottom edge of the screen (Look up album, Look up artist, Add to playlist, More with a grey chevron); tap above the sheet closes it; tap
More: the same sheet shows "< More", Speed (readable, the four badges tappable, the note under it), AB Repeat and a red Delete Song; tap "< More": page 1; tap
Delete: "Delete Song?" confirm opens over the sheet and, on No, the sheet is back on the bottom as it was (no jump to the middle); speed badges and the A-B
switch work; a new language shows the translated texts; `/mnt/mmc/m1pod-off`: the stock seven rows (dimmed by the asset).
