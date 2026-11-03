/* Software Update, the pure rules (patch/upver.c; docs/modules/update.md): the release tag, the comparison, the redirect and the downloaded package's first lines.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Nothing here touches the network, a widget or a stock function; patch/pcnet.c runs them on the worker's answers.
 */
#pragma once

#define UP_TAG 20 /* a tag buffer: "99999.99999.99999" and the NUL */
#define UP_MODEL "Shanling M1 Plus" /* line 1 of the package's firmware_v20.info (stock's updater compares it) */
#define UP_PKG_PREFIX "V2.1-" /* line 2 is this and the tag (tools/build.py TAG) */
#define UP_INFO "firmware_v20.info"

/* 1 when s is exactly major.minor.patch: three runs of 1..5 decimal digits, joined by dots, nothing before, between or after (no "v", no suffix, no space, no CR, no query, no sign). v: the three numbers. */
int up_parse(const char *s, unsigned v[3]);
/* major, then minor, then patch: -1, 0 or 1. */
int up_cmp(const unsigned a[3], const unsigned b[3]);
/* What a release tag means for a build whose version is own (dev: a development build, which has none to compare): 0 the tag is not a version (nothing is offered), 1 the build is as new or newer ("Up to date"),
 * 2 the release is offered. A development build is offered any valid tag. */
int up_offer(const char *tag, const char *own, int dev);
/* The tag in the Location of the answer to https://github.com/<repo>/releases/latest: the Location must be exactly https://github.com/<repo>/releases/tag/<tag> with a tag that up_parse accepts. 1 and the tag in out, else 0. */
int up_redirect_tag(const char *location, const char *repo, char *out, unsigned size);
/* 1 when the tar file at path starts with the member firmware_v20.info (a valid header, its checksum right) whose first two lines are UP_MODEL and UP_PKG_PREFIX + tag, each ended by a line feed. */
int up_info_ok(const char *path, const char *tag);

/* The build's own version (tools/build.py VERSION, the compiler's M1PLUS_VERSION), whether it is a development build (M1PLUS_DEV) and the repository (M1PLUS_REPO). Writable so a test can change them. */
extern char up_own[UP_TAG];
extern int up_dev;
extern char up_repo[48];
