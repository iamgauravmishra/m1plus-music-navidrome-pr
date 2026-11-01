# Payload safety

- **Keep the approved entry points.** Home icon tap, guarded Home initialization,
  Now Playing initialization, More-dialog initialization, the podcast tag-copy call site, the
  status bar's battery-capacity call site (Battery Percentage, off by default, not on the boot path)
  and the previously empty `scroll_view` event slot. See [payload](payload.md) and `AGENTS.md` for
  their scope. Do not add global paint or main-loop work.
- **Treat startup as critical.** Home initialization needs the crash marker. The tag-reader
  hook is also reachable through Memory Playback at boot: run stock's copy first and restrict
  podcast processing to its card path. The recovery button combination remains unverified.
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
