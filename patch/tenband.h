/* M1+ Music 10-Band editor (patch/tenband.c, docs/modules/peq.md "10-Band EQ"): the editor page with its ten sliders, and its Curve and Preamp pages.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#include "peq.h"

/* patch/peq_ui.c: the Equalizer page's 10-Band EQ link row opens the editor (1 once it is opening). */
int tenband_open(void);

/* patch/m1plus.c open_page: a page's window is up (the editor, the Curve page, the Preamp page). Each fills itself from the record; a page that is not our asset is left as it is. */
void tenband_opened(void *win);
void tencurve_opened(void *win);
/* patch/peq_ui.c peq_output_changed: the output changed; the editor reads the new output's record and redraws. */
void tenband_output_changed(void);
void tenpreamp_opened(void *win);

/* patch/m1plus.c: open_page of the three pages (the normal instance, with Back). */
int pod_open_tenband(void);
int pod_open_tencurve(void);
int pod_open_tenpreamp(void);

/* patch/peq_ui.c: save the record and have the player play it (stock's Equalizer turned on when it was off, as a tap on a preset does); 1 when it was saved, else the message box said so and the record is as it was. */
int peq_commit(const peq_state *s);
/* patch/peq_ui.c: a curve's name as a translation key (Flat, Pop, ... Custom). */
const char *peq_curve_key(int curve);

/* The slider card's touch maths (tests read them): the column (0..9) under a card-relative x, clamped; the half-decibel step (-24..24, 0.5 dB each) of a card-relative y, clamped. */
int tenband_col(int x);
int tenband_step(int y);

/* The bitmap helpers the band page (patch/peqband.c) shares: the coverage of pixel (x, y) in a w x h rounded rectangle of radius r; a w x h RGBA bitmap whose pixel is fn's (null with no memory); a pixel of a grey and an alpha. */
double tb_cover(int x, int y, int w, int h, double r);
void *tb_make(int w, int h, unsigned (*fn)(int x, int y, int w, int h));
unsigned tb_px(double grey, double alpha);
