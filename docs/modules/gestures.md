# List gestures

**Sources:** `patch/scroll.c`, test `test/pod/scroll.py`.

A swipe on a list must never play the song under the finger, and a touch on a list that is still coasting must stop it
and press nothing. This is a patch in AWTK's input path, so it is a data word, not a code hook: nothing of the stock text is
overwritten, and it runs only for touches that land inside a `scroll_view` (every stock list is `list_view > scroll_view >
list_item` rows; Songs, Recently Added / Played, Favorites, Most Played, playlist songs, the queue, Folders, Artists, our menu
and settings lists, the lyrics, and the Albums grid / list, whose one custom content view sits in a stock `list_view > scroll_view`, `docs/modules/albums.md`; Cover Flow has its own touch layer and no `scroll_view`).

**The stock paths** (all read from `demo` and run unchanged in `test/pod/scroll.py`):

- The window manager calls `widget_on_pointer_down / _move / _up` (`0x67126c / 0x6715f4 / 0x67187c`) on the window. Each one,
  per widget: the emitter's PRE event, `widget_on_event_before_children` (`0x666c34`, which calls `vtable[0x98]` of the
  widget, a no-op when the slot is zero), then the **children first** (`_children`: `widget_find_target` `0x666bdc`, whose
  default `0x6747d4` returns `widget->grab_widget` (`+0x4c`) at once when there is one), then the widget's own `on_event`
  (`widget_dispatch` `0x66cec8`, `vtable[0x94]`) and its emitter listeners. A `RET_STOP` from before-children ends the DOWN
  there.
- `list_item_on_event` (`0x60bb80`, jump table `0x75a150`): DOWN (`0x60bc00`) sets pressed (`+0x7d`) and down (`+0x7e`), keeps the
  press position, **grabs its parent** (`widget_grab(scroll_view, row)`: every later event of the gesture reaches this row,
  wherever the finger is), arms a 30 ms timer for the pressed look. MOVE (`0x60bde4`): when the pointer is down and
  `|y - y_down| >= 11` it cancels (`+0x7c = 1`, `+0x7d = 0`, ungrab). UP (`0x60bd08`): **dispatches `EVT_CLICK` (`0x10c`) when
  `+0x7c == 0 && +0x7d != 0`** (no position check) and clears the state. `EVT_POINTER_DOWN_ABORT` (`0x107`, `0x60bca4`) clears
  the state, the timer and the grab: the row is no longer pressed, so its UP is no click.
- `scroll_view_on_event` (`0x610724`; `vtable[0x94]` of `g_scroll_view_vtable` `0x97a298`) keeps `pressed` (`+0xa0`), `dragged`
  (`+0xa1`), the press position (`+0x98`, `+0x9c`), the offsets (`+0x80`, `+0x84`) and the running scroll animator `wa`
  (`+0xe8`). DOWN (`0x610830`): pressed, `widget_grab(parent, scroll_view)`, velocity reset, the press position and offsets saved.
  MOVE (`0x610acc`): while not dragged, `scroll_view_is_dragged` (`0x61064c`: the slidable axes only, `|d| >= 10` (`0x6106e0`),
  always true for `snap_to_page`) decides; when it is true the MOVE sends the **abort** (`0x107`, `widget_dispatch_event_to_target_recursive`
  `0x66e08c`, which starts at the grab widget) to the children, sets `dragged` and returns `RET_STOP` **without scrolling**;
  later MOVEs scroll, **but not while `wa` is set** (`0x610b28`). UP (`0x6108c4`): `is_dragged` on the release position
  decides the fling (`scroll_view_scroll_to(.., 200 ms)` `0x610340`: a `widget_animator_scroll` stored in `wa`, ended by the
  EVT_ANIM_END handler `0x6101b8`, which clears `wa` and sends the scroll-end events `0x14f` / `0x151`); the abort is **never sent from
  UP**, and the UP reaches the scroll_view *after* its rows.

**Confirmed holes** (each reproduces on the stock code in the test, "STOCK ... gets a click"):

1. The row cancels itself only on a MOVE of 11 px or more, the scroll_view only on a MOVE of 10 px or more. A gesture with no such
   MOVE (sparse touch samples in a quick flick: DOWN, one MOVE of 5 to 9 px, UP 60 px away; or DOWN and UP only) reaches the row's UP
   still pressed and grabbed, and the row **clicks** (a song starts) while the scroll_view flings. The same for a release 10 px
   away after small MOVEs. (A MOVE past the threshold, out and back near the start, already cancels in stock: `dragged` and the
   row's cancel are sticky.)
2. Nothing in DOWN looks at `wa`: a touch on a coasting list presses the row under the finger and the tap clicks it, and the drag
   that follows does not move the list until the 200 ms animation ends (the MOVE skips the offset while `wa` is set).

**The intervention.** `g_scroll_view_vtable + 0x98` (`0x97a330`, the `on_event_before_children` slot, zero in stock) is set
to `m1plus_scroll_event(widget, event)` (`tools/pod.py patch_scroll`; `demo_diff` allows exactly this word). It sees the event
before the children:

- **DOWN** on a scroll_view that has a live scroll animator (`wa != 0`, not `snap_to_page`, animator state `+0x28 == 1` running and
  its widget `+4` this scroll_view; anything else is left to stock): `widget_animator_destroy(wa)` (`0x6735ac`: out of the manager,
  freed on an idle), the stock end handler `0x6101b8(widget, 0)` (clears `wa`, sends the end events), `widget_dispatch(widget, event)`
  (the scroll_view takes its own press: grab, velocity, press position) and `RET_STOP`: the rows never see this DOWN. The rest
  of the gesture is stock: a drag scrolls from the touch, a tap is no click (the row was never pressed).
- **UP** with `pressed && !dragged && !snap_to_page` and a release at least 10 px from the press along a slidable axis (the
  stock threshold and axes; nothing changes the threshold): the same `0x107` abort the stock MOVE path sends (a copy of the
  pointer event), before the rows see the UP. The row drops its press and the release is no click; the scroll_view's own UP
  (fling) is unchanged.
- MOVE, key and wheel events: two compares and out. Only slidable axes count, as in stock: a horizontal drag in a vertical list
  (a slider in a settings row) is not aborted; a list that cannot scroll and a page-snapping scroll_view are stock.

**Why it is safe.** No stock text is overwritten; the pinned words (`SCROLL_PINS` in `tools/pod.py`: the vtable words, the
dispatcher's `lw t9, 0x98(vt)`, the three call sites, the field accesses of `on_event` / `is_dragged` / the end handler / the
animator) must all match or the build refuses; the slot must be zero. The hook runs on the UI thread in the input path only,
never at boot, in paint or in a timer. No allocation, no log, a small stack frame (the 48 byte event copy); the stock calls it makes are the ones
the stock MOVE path and animator code make. The kill switch (`home_off()`, both files) is read **once**, the first time a
late-drag UP or a DOWN on a coasting list needs it (never on a MOVE or an ordinary tap), and the hook is then a no-op for the
session; creating the file mid-session takes effect at the next start. Hot path: a MOVE costs 15 instructions including
call and return, an idle DOWN or UP 36 / 19, no call and no syscall (`test/pod/scroll.py`).

**Known limits.** Any scroll animation counts as a coast: a touch within the 200 ms of a programmatic scroll (the lyrics view moving
to the next line, a list scrolled to the playing song) stops it and is not a tap; tap again. A swipe starting on a button inside
a row (the Main Menu's up arrow) is aborted like any swipe; a plain tap on that button still clicks the button, and in the
emulation the row also gets its click, as in stock (the button returns `RET_OK`). The abort threshold is the stock 10 px; a
first-MOVE scroll update (the other half of the "not following" feeling) is a separate change.

**Tests** (`test/pod/scroll.py`, the stock event code under Unicorn on real widget structs, every scenario with the slot zeroed
and with the hook): six gestures that click in stock and do not with the hook, the flick, out-and-back and slow-drag gestures and
every tap kind unchanged, the touch on a coasting list (stock: clicks and the list cannot be caught; hooked: animator
destroyed, end events sent, no press, the next tap clicks, a drag scrolls), the stale-animator, snap, no-scroll and horizontal
exceptions, the kill switch (SD file and flash file), no syscall on the hot path, the up arrow and switch of a Main Menu row,
the pinned words.
