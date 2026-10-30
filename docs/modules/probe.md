# Network Probe

Code: `patch/probe.c`, `patch/probe.h`. Test: `test/pod/probe.py` (the harness gained scripted libcurl, shell and thread mocks, `Machine.nested`). A developer's tool, step 0 of Podcasts phase 1
(`docs/modules/podcasts.md` "Next: subscribe and download"): it answers on the device what the feed downloader will rely on, before any of it is built. Nothing of it is meant to stay in the
release once the answers are in (the worker design, the CA bundle and the guards move into the feature).

## What it is

**Customize > Developer > Network Probe** (`ACT_NETPROBE` 25, Lucide `globe`). A tap asks in the stock confirm dialog; Yes makes one `calloc`ed context, calls `curl_global_init(ALL)` and
`get_wifisignal()` (both on the UI thread), then starts **one detached pthread** (`probe_main`) and returns. The thread writes one line per fact to **`/mnt/mmc/m1plus-probe.log`** (appended, `fsync`ed
per line, each line `[epoch +seconds]`) and frees its context when done. A tap while it runs only toasts "Network probe is running". The kill switch is checked at the tap; no card = "Storage unavailable".
No hook, nothing at boot, in the main loop or at paint; the UI is never touched from the thread. **No new import**: only what demo already has (`curl_easy_*`, `curl_global_init`, `popen`, `pclose`,
`fgets`, `sleep`, `pthread_detach`, plus the libc the payload already used); `get_wifisignal` (`0x506cc8`) is pinned in `FUNCTIONS`.

`get_wifisignal` (`networkGetWifiSignal` + `networkGetConnectStatus` + `networkGetPhysicStatus`) returns -1 when not connected, else 2..5 from the dBm. It is asked **only on the UI thread** (the tap):
the stock status reader is not known to be thread safe, so the worker takes the link from the kernel (`/proc/net/wireless`) instead. The real feature gates on a UI-thread timer for the same reason.

## What it records (the log, in order)

1. The banner, the clock (epoch and local calendar), `get_wifisignal` at the tap, `MemAvailable` / `MemFree`, then shell output (`popen`, stderr folded in, 30 lines each at most): `date`,
   `uname -a`, `/proc/net/wireless`, `ifconfig wlan0`, `/etc/resolv.conf`, `/tmp/result_ntpdate` (the stock `ntpdate` result), `ls /etc/ssl /etc/ssl/certs`, `ls /mnt/mmc/.m1plus /mnt/mmc/Podcasts`,
   `df`, the battery's `capacity` / `status`, `ps`. The CA bundle's size (`/mnt/mmc/.m1plus/cacert.pem`, or MISSING).
2. Requests, each with: label and url, memory before and after, curl's verbose text lines and incoming headers (at most 60 a request; this is where "SSL connection using TLSv1.x / cipher",
   "CAfile", the certificate subject / issuer / dates and the ALPN show), the result and message, the HTTP code, redirects, `CURLINFO_SSL_VERIFYRESULT`, the primary IP, the final url, the phases in ms
   (dns, connect, tls, first byte, total), bytes, kB/s and the first bytes of the body:
   * the iTunes search with the CA bundle (the Add Show path; the body shows `feedUrl`),
   * the same with **no** CA file (libcurl's own default: expect 60 or 77: `/etc/ssl/certs` is empty),
   * `https://expired.badssl.com/` with the bundle: **must fail with 60** (verification is on),
   * `http://neverssl.com/` (plain http),
   * the big feed (`allinchamathjason.libsyn.com/rss`, redirects, `Accept-Encoding: ""`, a line of free RAM at every MiB, cut at 8 MiB) and The Headlines' feed,
   * every url of the optional `/mnt/mmc/.m1plus/probe-urls.txt` (one per line, 8 at most), as a **Range** request `0-262143` (does an enclosure redirect chain answer 206).
3. The **soak**: 10 rounds, 30 s apart (5 min): epoch, whether the screen is lit (`pod_screen_lit`), the `/proc/net/wireless` line and one small HTTPS GET (one summary line); every fifth round the battery.
   Start it and **turn the screen off**: a gap in the epochs is the CPU asleep, a failed GET is the Wi-Fi gone.
4. The clock again at the end, memory at the end, "probe done".

Every request sets `FOLLOWLOCATION` (at most 8), `NOSIGNAL`, `CONNECTTIMEOUT` 20, `LOW_SPEED_LIMIT` 1000 B/s over 30 s, `TIMEOUT` 300 s (a feed) or 60 s, `NOPROGRESS`, and `CAINFO`; **it never sets
`SSL_VERIFYPEER` or `SSL_VERIFYHOST`** (the test checks that no handle has them). Times use the `_T` info (microseconds): the 64-bit values are cut to the low word (no 64-bit divide in the payload).

## Running it

Files on the card (the probe never writes them): `/mnt/mmc/.m1plus/cacert.pem` (any PEM bundle: macOS has one at `/etc/ssl/cert.pem`, 128 roots, 333 KB; loading it is itself timed by the first
request's connect / tls figures: it decides how small the shipped bundle must be) and optionally `/mnt/mmc/.m1plus/probe-urls.txt`. Wi-Fi must be connected first (System Settings). Read
`m1plus-probe.log` afterwards; the log is appended, so runs stack.

## Questions it answers (checked in the device log)

| Question | Where |
|---|---|
| HTTPS with our CA bundle works? Which TLS version / cipher? | request 1: `rc 0`, "SSL connection using ..." |
| libcurl has no built-in CA path? Verification really on? | request 2 (60 / 77), request 3 (60, verify 10) |
| `get_wifisignal` connected / not connected | the `wifi:` line (run it with Wi-Fi on, then once off) |
| Is the clock right after Wi-Fi connects (`ntpdate`)? | the clock lines, `/tmp/result_ntpdate`, `date` |
| RAM free during a feed (4 MB, 441+ items) | `body N MiB: available ... kB` lines, `mem before / after` |
| Do Wi-Fi and the worker survive the screen off on battery? | the soak lines' epochs and results |
| Cost of the bundle, DNS, redirects, gzip, speed | the phase times, `Content-Encoding` header, kB/s |
| Does stock Update Local Music scan `Podcasts/`? | **not** answered here (a manual check: update the library, look in Songs); dot folders are scanned (`docs/modules/q2pod.md`: q2-pod patches the stock scan) |

## Test (`test/pod/probe.py`)

The row, its asset and glyph, the confirm text; the tap in every state (confirm Yes / No, kill switch, no card, no thread, no memory, a second tap, the next run); the worker against a scripted
internet (`Machine.curl_site`; libcurl callbacks run for real through `Machine.nested`, the registers saved around them): the log's lines, the options of every request, the 8 MiB cut-off, the
verbose-line cap and truncation, the printable head of a body, the url file's parsing, the soak (sleeps, the screen state, one summary line a request), a missing CA bundle and url file, an unwritable
log, the clean-up (every handle, every `fsync`, the log closed, the context freed) and the write callback on its own.

## Device results (V2.1pANQ, 2026-10-30, Wi-Fi 4 / link 47 / -63 dBm, on battery)

* **HTTPS works with a bundle on the card**: TLS 1.3 (`TLS_AES_256_GCM_SHA384`, `TLS_AES_128_GCM_SHA256`), TLS 1.2 only for podtrac. No CA file = 60 (`CApath: none`; `/etc/ssl/certs` is empty), an expired certificate = 60 with verification
  on. Loading the 128-root macOS bundle costs nothing visible: tls 225-740 ms in all (handshake included). Issuers seen: Apple EV, Sectigo (libsyn), Amazon (simplecast, podtrac).
* **gzip works** (`Accept-Encoding: ""`): a 3 MB feed came over as 408 kB, a 4 MiB one as 471 kB. Feeds ran at 300-800 kB/s; ranged enclosure fetches at 94-237 kB/s (a 15 MB episode: 1-2.5 min).
* **Redirects and Range**: the podtrac chain (6 redirects, to signed urls) and the Dow Jones one answer 206 with `Content-Range`: storing the original `u=` and following redirects each time works.
* **RAM**: 89 MB available at the start; a 4 MiB feed cost 1-2 MB (curl and the callback only; no parser yet).
* **Clock** right (`date` and the epoch); `/tmp/result_ntpdate` does not exist (ntpdate did not run this boot, so the RTC keeps the time). `get_wifisignal` 4 connected; the not-connected value was not run.
* **Screen-off soak, 5 minutes**: rounds 30-31 s apart, every GET 200, the screen dark throughout: the CPU and Wi-Fi stayed up. The log stops at round 9 of 10 (the card was probably taken out); the user saw the Wi-Fi disconnected after a longer idle.
* **Why: stock standby** (read in `demo`, not run): the idle timer `on_wm_idle_status` (`0x4ce7d8`) calls `to_poweroptions` (`0x4ce5a8`), which does nothing while `mclGetPlayStatus` is 2 (playing) and otherwise calls `into_standby`
  (`0x4e7508`): `save_stop_player`, `mclSetDacPwr(0)`, `stop_btsynclink`, the DLNA / AirPlay stops, **`networkStop`**, then `toolsIntoStandby` (`0x5e5228`: `system("echo mem > /sys/power/state")`). So an idle device (not playing) loses its
  Wi-Fi and suspends after the stock idle time; audio playing keeps it up. A refresh or download must therefore expect the network to vanish with the CPU frozen mid-request (the worker resumes after the wake with a dead socket: the time-outs
  and the `.part` resume cover it); whether a running worker can postpone standby is for the download step.
* Left unanswered: the plain-http request timed out at connect (`neverssl.com`, 20 s; the host or the network), and whether stock Update Local Music scans `Podcasts/`. The soak's link line printed `wlan1` (all zeros: `tail -n 1`), not `wlan0`.
