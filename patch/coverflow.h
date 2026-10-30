/* Cover Flow's depth renderer, shared by the Cover Flow page (patch/coverflow.c) and the iPod page's Cover Flow screen (patch/ipod_cf.c).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE). The renderer follows q2-pod's design, after Rockbox PictureFlow (see coverflow.c).
 */
#pragma once

#define CF_ONE 65536
#define CF_REACH 3 /* ring slots either side of the centre that can show (fading in) or preload */
#define CF_RING (2 * CF_REACH + 1)

/* A shelf's geometry: w x h logical columns and rows (the cover's x right, y down), the centre line
 * cx, the centre cover's top and size on screen (art; its texture is always ART_SIZE), the eye
 * distance, the first side cover's offset x1 and depth z1, the spacing xs and zs of the rest, the
 * reflection's length in px at the cover's own size. rot: the frame is the logical one turned a
 * quarter clockwise (logical (x, y) is physical (h - 1 - y, x)), see coverflow_render.
 * tail: 0 = the stock fade (CF_BRIGHT2 at two out, gone at three out); else the brightness (of 256) of the
 * cover three out, which then fades out by 3.5 out (the iPod page's seven visible covers).
 * bg: 0 = the frame is over black (the distance fade darkens the covers); else the colour (r | g << 8 | b << 16) it is over (the fade turns
 * the covers transparent, and the frame ends composited on bg: the iPod page's white Cover Flow). Always the last field. */
typedef struct {
    int w, h, cx, top, art, eye, x1, xs, z1, zs, reflect, rot, tail;
    unsigned bg;
} cfg_t;

void coverflow_render(const cfg_t *g, unsigned *d, int pitch, int frac, const unsigned *const ring[CF_RING]);
