# Safety rules for the payload

Split out of docs/architecture.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 10. Safety rules for the payload

- A boot-time crash is dangerous (the watchdog reboots in a loop, recovery combo unverified): the only
  start-up code is the guarded `home_page_init` hook; every other path is user-initiated.
- Four code hooks only (sections 2, 8, 8a, 9), plus one empty vtable slot filled (section 8d: touches in a `scroll_view`); the 59 row edits and the five A-B marker immediates are call-site and immediate edits, not hooks.
- Every patched word, hook site, `$gp`, address and the input SHA are pinned; `pod.py` refuses to build
  on mismatch; every hook falls back to stock through its trampoline; every error path (non-entry
  icon, kill switch, `window_open` NULL because the asset could not load, null icon) calls stock.
- Kill switch `/mnt/mmc/m1plus-off` (`access()` first) disables the entry, the guard and the row fit (the list gesture hook reads it once per session, section 8d).
- On this AWTK `visible=false` does not stop hit testing (`widget_find_target_default` `0x6747d4` takes
  the first child with `flags & 9 == 9`: enable bit 0 and sensitive bit 3; `widget_set_visible` `0x66c394`
  only flips bit 2): hide = `visible=false` + `sensitive=false` (asset) or `widget_set_sensitive(w, 0)`
  (runtime); decorative overlays are insensitive. Normal windows are 450 px tall (fullscreen 480).
- No stock widget the app looks up by name is renamed or deleted.
