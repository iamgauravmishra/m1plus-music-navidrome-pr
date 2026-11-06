/* M1+ Music preset page (patch/peqpage.c, docs/modules/peq.md "Preset page"): a preset's frequency response, preamp and bands, read only.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#include "peq.h"

/* A row of the Presets page (patch/peqlib.c): parses the preset file of the card's EQ folder and opens the page. 1 once it is opening; 0 when the file cannot be read (the message box says so, nothing opens). */
int peqpage_show(const char *file);

/* patch/m1plus.c open_page: the page's window is up. Fills it from the preset peqpage_show parsed; a page that is not our asset is left as it is. */
void peqpage_opened(void *win);

/* patch/peq_ui.c: a preset file's name as the pages show it (without its .txt), into size bytes. */
void peq_shown(char *out, unsigned size, const char *file);

/* patch/peq_ui.c: the card piece (0 single, 1 top, 2 middle, 3 bottom) a list row shows in every state; tall: the 60 px row's pieces (pod_cdl_*), else 52 px; cache (one byte per row, 0 at first) keeps the last one so that nothing is set twice. */
void peq_piece_set(void *row, char *cache, int piece, int tall);

/* The graph card (shared with the 10-Band editor, patch/tenband.c; needs offsets.inc's GR_*): the curve of a preset at 48 kHz without its preamp, one value a plot column, the range that holds it, and the card's bitmap. */
typedef struct {
    void *bmp;
    int range; /* dB at the top and (negated) at the bottom: 12, 18 or 24 */
    float db[GR_PW];
} peq_graph;
void peq_graph_curve(peq_graph *g, const peq_preset *p); /* g->db and g->range from the preset's bands */
int peq_graph_draw(peq_graph *g); /* g->bmp made or drawn again from the curve; 0 with no memory */
void peq_graph_free(peq_graph *g);
void peq_graph_paint(const peq_graph *g, void *e); /* the view's EVT_BEFORE_PAINT event: one blit */
void peq_blit(void *canvas, void *bmp, int w, int h, int x, int y); /* one 1:1 canvas_draw_image */
void peq_label_colors(void *w, const char *rgb); /* a label's text colour in its normal, disabled and focused states */
void peq_graph_scale(const peq_graph *g, void *top, void *bot); /* the scale labels: +R, -R */
/* "+4.8 dB", "-2.4 dB" (U+2212), "0.0 dB" (plus: the "+" of a boost); the preamp as the page shows it: "Auto - 6.0 dB" or the file's own */
void pp_gain(char *out, unsigned size, double g, int plus);
void pp_preamp(char *out, unsigned size, const peq_preset *p);

/* "105 Hz", "1.25 kHz" (a frequency from 20 Hz), "1.41" (a Q in hundredths, zeros trimmed), and a number to four decimals, zeros trimmed ("105", "-3.5", "0.7071"; out needs 16 bytes; returns the length) */
void pp_freq(char *out, unsigned size, double f);
void pp_qtext(char *out, unsigned size, double q);
unsigned pp_num(char *out, double v);

/* The stock confirm dialog with text (modal): 1 for Yes, 0 for Cancel (Delete Preset, Reset 10-Band EQ?). */
int peq_ask(const char *text);

/* 10 * log10(x) to about 1e-5 dB (-120 for x too small): the preamp's linear gain squared is its decibels. */
double pp_db10(double x);

/* Preset editing (docs/modules/peq.md "Preset editing"). The preset page owns the working preset; the band page (patch/peqband.c) edits its bands in place. */
/* The bands that play, the edited copy (count = the rows the page shows); null with no Preset page up. */
peq_preset *peqpage_work(void);
/* The working preset is what plays: into the record under this file's name, and the Edited state recomputed. play 1 (a band edit): stock's Equalizer is turned on and the player told, as a tap on a preset does (peq_commit); 0 (Save, Save As, Revert):
 * the record only, the player told when the Equalizer is on (peq_record). 1 when saved; else the message box said so. */
int peqpage_commit(int play);
/* The band page's unsaved-changes dialog (patch/peqband.c) asks the preset page: whether the working preset differs from the file; the preset's name; Save (written in place, atomically; 1 when it was); Save As New (the name entry, whose Done writes the new
 * file and makes it the page's, so peqpage_edited is 0 afterwards; Cancel or a refused name leaves it 1); Don't Save (the file's preset again; 1 when it was read). */
int peqpage_edited(void);
void peqpage_name(char *out, unsigned size);
int peqpage_save(void);
void peqpage_saveas(void);
/* patch/peqpage.c peq_save_new: the name entry's Done for a new preset file in PEQ_DIR (Save As, and the 10-Band editor's Save as Preset): the name cleaned, ".txt" added into file (PEQ_NAME bytes), p written to it atomically.
 * 1 when written; else the message box said why (a name in use, the limit, a failed write) or nothing was typed. */
int peq_save_new(const char *text, const peq_preset *p, char *file, peq_preset *back);
int peqpage_revert(void);
/* patch/peq_ui.c: the record saved and, when stock's Equalizer is on, the player told (no switching it on). 1 when saved. */
int peq_record(const peq_state *s);
/* patch/peq_ui.c: a Rename Preset of file from to to: the record's name follows when from is the preset that plays. */
void peq_renamed(const char *from, const char *to);
/* patch/peqband.c: a band row of the preset page opens the band page on band (0-based); 1 once it is opening. */
int peqband_open(int band);
/* patch/m1plus.c open_page: the band page's window is up; fills itself from the preset page's working preset (a page that is not our asset is left as it is). */
void peqband_opened(void *win);
int pod_open_peqband(void);
