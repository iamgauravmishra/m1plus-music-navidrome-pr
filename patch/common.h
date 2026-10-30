/* Small helpers every page of the payload shares (patch/common.c).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#define ELLIPSIS 0x2026   /* U+2026 HORIZONTAL ELLIPSIS, the wide char texts are cut with */

int pod_on_back(void *ctx, void *e);     /* click handler: navigator_back() */
int pod_on_player(void *ctx, void *e);   /* click handler: the stock "back to the player" button */
int pod_card_mounted(void);              /* the SD card is mounted (statfs: /mnt/mmc is another file system than /mnt); never write under /mnt/mmc otherwise */
int pod_is_type(void *w, const char *type);   /* w is a widget of exactly this type name */
/* Bind fn to EVT_CLICK of the widget called name in win (ctx passed through); returns the widget, NULL if
 * the page has none (or fn is NULL). */

/* Cover tint, shared by Now Playing and the album page (patch/common.c). */
/* A dark, slightly desaturated tone of a cover's average colour (r, g, b bytes), a color_t word (0xAABBGGRR, alpha ff). */
unsigned pod_tone(unsigned r, unsigned g, unsigned b);
/* The tone cache (RAM, TONE_CACHE_N entries, least recently used out): the tone word of an album key (cc_album_key).
 * get: 1 and *tone when cached. put: insert or replace. A key of 0 is never stored or found. */
int pod_tone_get(unsigned key, unsigned *tone);
void pod_tone_put(unsigned key, unsigned tone);
/* The black gradient's alpha on row y of `rows`: a_top on the first row to a_bot on the last (rows past it: a_bot). */
unsigned pod_alpha(unsigned y, unsigned a_top, unsigned a_bot, unsigned rows);
/* color (0x..BBGGRR) as it shows on row y under that gradient. */
unsigned pod_shade(unsigned color, unsigned y, unsigned a_top, unsigned a_bot, unsigned rows);
/* The top left corner's coverage (0..255) outside a quarter circle of radius r, r * r bytes. */
void pod_corner_fill(unsigned char *tab, unsigned r);
/* A square cover's four corners painted in the colour the window has behind them (a canvas in the cover's own
 * coordinates): cover row 0 is window row row0, under the gradient (a_top, a_bot, rows). Returns nothing. */
void pod_corners(void *canvas, const unsigned char *tab, unsigned r, unsigned side, unsigned color, int row0,
                 unsigned a_top, unsigned a_bot, unsigned rows);
/* The status bar in a page's top-edge colour (Now Playing, the album page). color is 0x..BBGGRR as the page shows it on row 0;
 * pod_bar_color darkens it until the bar's white glyphs keep 4.5:1 (luminance cap NP_BAR_LUM_MAX) and returns a color_t word.
 * pod_bar_tint: the bar takes it and win owns the bar; 1 on success, 0 (nothing owed) when there is no bar or the style call fails.
 * pod_bar_black: the stock black, only if win is the owner (so a page that lost the bar to the next page leaves it alone).
 * pod_is_top: win is the window manager's top normal window. */
unsigned pod_bar_color(unsigned color);
int pod_bar_tint(void *win, unsigned color);
void pod_bar_black(void *win);
int pod_is_top(void *win);
void *pod_bind(void *win, const char *name, int (*fn)(void *, void *), const void *ctx);
