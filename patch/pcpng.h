/* A streaming PNG decoder for the cover shrink (patch/pcpng.c; docs/modules/podcasts.md "Cover art").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#define PP_MAX_SIDE 8192u /* the longest side a PNG may have */
#define PP_MAX_PX 25000000u /* and the most pixels (the decoder's time is the pixels' bytes, about 5000 x 5000) */

typedef struct pp pp_t;

/* Read the headers of the PNG in the stdio file f (positioned at its start) up to the first IDAT, check them, allocate the decoder state into *out (also on failure: free it with pp_free) and
 * give the size. Returns 1; 0 when the file is not a PNG this decoder takes (bad signature or header, an unknown format, a size over the limits, a missing palette, no IDAT, bad zlib header);
 * -1 for an interlaced (Adam7) PNG, which cannot be shrunk in one pass over its rows. f stays owned by the caller. */
int pp_open(void *f, pp_t **out, unsigned *w, unsigned *h);
/* Inflate the image data and hand over every scanline, top to bottom, as RGB (w * 3 bytes; transparency composited over white): row(user, rgb, w) returns 1 to go on, 0 to stop (that stops
 * pp_run too). Returns 1 when exactly h rows were decoded from a valid stream; 0 on any error: truncated data, a bad Huffman code or block, a distance beyond the output, a bad filter byte,
 * more or fewer bytes than the header's size says. Memory: the state of pp_open (windows, tables, two rows and one RGB row), nothing else. */
int pp_run(pp_t *p, int (*row)(void *, const unsigned char *, unsigned), void *user);
void pp_free(pp_t *p);
