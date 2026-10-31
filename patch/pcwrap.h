/* Line breaking for the Podcasts Show page's texts (patch/pcwrap.c; docs/modules/podcasts.md "The Show page").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Pure: the caller measures every glyph once (adv[i] = the advance AWTK charges for s[i], the glyph's width plus its 1 px) and gets the lines back as
 * (start, length) pairs into the same string; tools/pod_wrap.py is the same algorithm in Python (the preview and the tests compare the two).
 */
#pragma once

typedef struct {
    short start, len; /* chars of the line, from s[start] */
} pw_line_t;

/* Break the wide string s (n chars, widths adv[]) into at most maxl lines of at most room px each: a latin line breaks after a space, a CJK line between any two characters, a word longer
 * than the line anywhere. Kinsoku: no line starts with closing punctuation (the break moves back so that it goes to the next line with the character before it) and none ends with an
 * opening quote or bracket. When text is left after the last line that line is cut with an ellipsis (ellw: its width): the longest prefix that fits with it, an opening bracket never last;
 * s[start + len - 1] is then the ellipsis (the string is changed there and nowhere else). Returns the number of lines, 0 for an empty text. */
int pw_wrap(unsigned *s, int n, const unsigned short *adv, int room, int maxl, int ellw, pw_line_t *out);
