/* Network probe (patch/probe.c, docs/modules/probe.md): constants the payload and test/pod/probe.py share.
 * The test parses the #defines in this file, so a change cannot leave the mocks behind.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#define PROBE_LOG "/mnt/mmc/m1plus-probe.log" /* appended to, one line per fact, fsynced */
#define PROBE_CA "/mnt/mmc/.m1plus/cacert.pem" /* the CA bundle the user copies there; the real feature ships its own */
/* PROBE_URLS: optional: one url a line, each fetched with a Range of PROBE_RANGE */
#define PROBE_URLS "/mnt/mmc/.m1plus/probe-urls.txt"
#define PROBE_RANGE "0-262143"
#define PROBE_SOAK_N 10 /* soak rounds ... */
#define PROBE_SOAK_S 30 /* ... this many seconds apart: the screen-off check */
#define PROBE_FEED_CAP 8388608 /* a feed larger than this is cut off */
#define PROBE_URL_MAX 400
