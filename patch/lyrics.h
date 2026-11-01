/* The Now Playing lyrics page (patch/lyrics.c, docs/modules/lyrics.md). Called from patch/nowplaying.c's page timer; no hook of its own.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

/* The page is built (win: the playing window). Finds the asset's np_lyrics box and the stock lyric list, makes the label pool and hides the stock list.
 * Anything missing leaves the stock list as it is. */
void ly_start(void *win);
/* The page's 500 ms tick: new lyrics, the current line, the layout. */
void ly_tick(void);
/* The page is over (or replaced): the animation timer goes, the state is cleared. */
void ly_stop(void);
