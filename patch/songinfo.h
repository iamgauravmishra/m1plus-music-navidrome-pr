/* Get Info: a track's details page (patch/songinfo.c, docs/modules/songinfo.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

/* Opens the Get Info page for the track whose stSongInfo is rec (the title, artist, album, path and CUE fields are copied at once: rec may be destroyed after the call).
 * 0 opened (or already up), -1 not (no record, window or memory). */
int songinfo_open(void *rec);
