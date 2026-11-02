# Payload safety

- **Keep the approved entry points.** Home icon tap, guarded Home initialization,
  Now Playing initialization, More-dialog initialization, the podcast tag-copy call site, the
  dot-folder scan, library query functions, status bar's battery-capacity call site
  (Battery Percentage, off by default) and the previously empty `scroll_view` event slot.
  [Payload](payload.md) defines the hook sites and fallbacks. Do not add boot, global paint
  or main-loop work outside that scope.
- **Treat startup as critical.** Home initialization needs the crash marker. The tag-reader
  hook is also reachable through Memory Playback at boot: run stock's copy first and restrict
  podcast processing to its card path. The recovery button combination remains unverified.
- **Preserve hook restrictions.** Tidal-icon recovery applies only while the bad note exists.
  Home's ready path changes the language's CJK cmap field and glyph-cache size, repeated
  by a timer after language/theme changes. Podcast tags apply only under
  `/mnt/mmc/Podcasts/` after stock's path copy. Library query hooks are reachable through
  Memory Playback at boot: rewrite only the documented songtable/myfav cases and pass
  other SQL untouched. Album queries use track order so the first track supplies the row/cover.
  The scan hook skips dot-folders outside the boot path. The battery hook runs stock first
  from the first status refresh; only an enabled percentage setting changes capacity/label.
  Disabled it adds only an access and cached flag. Now Playing's paint work stays on the
  cover widget; More work stays on init, More/back taps and covering-dialog handling.
- **Pin every edit.** Check stock SHA-256, words, symbols, `$gp` and offsets before writing.
  A mismatch fails the build; hook errors fall back to stock.
- **Honor the kill switch.** `/mnt/mmc/m1plus-off` disables the payload. The list-gesture hook
  reads it once per session; other entry points check it at their documented boundaries.
- **Preserve widget names.** Restyle, move or hide widgets the application looks up; never
  rename or delete them. Hide with both `visible=false` and `sensitive=false`; decorative
  overlays must be insensitive. See [UI rules](ui-rules.md) for hit-test evidence.
- **Preserve update boundaries.** Only kernel and rootfs are packaged. Never write bootloader
  or recovery kernel. The rebuilt rootfs must not exceed stock size.

Normal windows are 450 px below the status bar; fullscreen windows are 480 px. Feature timers,
workers and paint events must remain owned by their page and follow its lifetime.
