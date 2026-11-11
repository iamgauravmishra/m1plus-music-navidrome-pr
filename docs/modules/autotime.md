# Automatic time over Wi-Fi

Stock V2.1 already syncs the clock over NTP. The mod changes only how the RTC is stored, as
q2-pod does (`RTC_WRITE`, `hwclock -wu`; its `docs/internals.md` "Clock"), with two pinned string
edits (`tools/autotime.py`, applied by `tools/pod.py`). No code word, hook or UI changes, nothing
at boot, in the main loop or at paint. Stock's ntpdate command and servers are untouched.

## Stock flow

- Setting `[SYSSET] AUTOSYNCTIME` (string `0x747a2c`) is read by `config_init` `0x4e5030`
  (`toolsReadConfig`, default text `"0"` at `0x74c728`) into the byte `0xa05ab1`.
  `network_checkstatus` `0x5068e0` sets the need-sync byte `0xa05a66` (`0x506a04`) only while the
  setting is on; the Settings handler `0x4a2618` clears both and writes the key when it is switched off.
- `networktime_adjust_thd` `0x4d92bc` (created at `0x50bd2c`) wakes every second; when
  `networkGetConnectStatus` is positive and `0xa05a66` is set it calls `toolsGetNetworkTime`
  `0x5e32d4` for `time.nist.gov`, `time.apple.com`, `cn.pool.ntp.org`, `time.windows.com`
  (`0x74ab24`..`0x74ab54`) in turn. It stops at the first success, clears the flag even if all
  four fail, then calls `toolsGetSysTime` and `toolsSetRtcTime`.
- `toolsGetNetworkTime` runs `system("ntpdate %s &> /tmp/result_ntpdate")` (`0x756f38`), then
  searches the file for `"no server"`. BusyBox 1.31.1 ash may not support `&>` (it would background
  ntpdate and leave the file empty); this is unverified and left as in stock.
- `toolsSetRtcTime` `0x5e34f4` runs `date -s "..."` then `hwclock -w` (`0x756fa4`); it is also
  called by `set_systime` `0x4d7770` (manual time). `toolsGetRtcTime` `0x5e34d8` is a tail call of
  `system("hwclock -s")` (`0x756f7c`) from `platform_init` (`0x50be94`), after `config_init` has
  exported `TZ` (`select_timezone` `0x4d6b2c` -> `toolsSetTimeZone` = `setenv("TZ")`).
- `/etc/localtime` is `Etc/UTC`; the rootfs has no `/var/lib/hwclock/adjtime`, so BusyBox
  `hwclock` without `-u` treats the RTC as local time in the inherited `TZ`.

## Edits

| Address | Stock slot | New slot | Reason |
|---|---|---|---|
| `0x756fa4` (12 bytes) | `hwclock -w` | `hwclock -wu` | RTC holds UTC (q2-pod) |
| `0x756f7c` (12) | `hwclock -s` | `hwclock -su` | The player's own boot read, so the UTC RTC is not read as local time |

Each is a NUL-padded literal replaced by text of the same slot length. `EDITS` pins the stock
bytes and `NEIGHBOURS` the following literal of each slot (`0x756f88`, `0x756fb0`); a mismatch
fails the build before anything is written. Both literals are referenced only by the code listed above.

### Why the read changes too

q2-pod changes only the write because the Q2 kernel's `hctosys` sets the clock from the RTC as
UTC at boot. The M1 player instead runs `hwclock -s` itself at every start (`0x50be94`), after
`TZ` is exported, so without `-u` it would read a UTC RTC as local time and shift the clock by the
zone offset. Static check of the M1 kernel and rootfs: `xImage` (Linux 5.10.21, uncompressed) has
no `hctosys` or RTC driver strings, the rootfs has no init script or module that reads the RTC
(`soc_utils.ko` only enables the 32 kHz clock), and `hwclock` appears only in `demo`. If a kernel
`hctosys` did exist it would run before the player, which sets the clock again. So `-su` is
required for `-wu` to be consistent.

## Default and existing devices

`config_init` copies `/release/assets/default/raw/config.ini` to `/mnt/data/config.ini` only when
the latter is missing, and that default already has `AUTOSYNCTIME=1` (and `TIMEZONE=22`). A fresh
device has auto time on; a device keeps whatever it saved, so a saved `0` stays off. A config
without the key reads the code default `"0"`, off. The mod does not touch `config.ini`.

## Limits

- An RTC last written by stock holds local time; after the update `hwclock -su` reads it as UTC,
  so the clock is off by the zone offset until the next sync (automatic when Wi-Fi connects with
  auto time on) or a manual set.
- The sync runs once per connection event, not periodically.
- Stock `time_t` is 32-bit; dates after January 2038 are wrong in `ntpdate` and `date -s`.

## Validation

`test/demo_diff.py` checks stock and new bytes of each slot and its neighbour and that nothing
else changed; `test/pod/rows.py` allows only those words; `test/tools.py` checks slot lengths and
that a changed stock byte or neighbour is refused without writing.
