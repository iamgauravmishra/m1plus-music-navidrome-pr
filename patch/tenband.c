/* M1+ Music 10-Band editor: ten vertical sliders, the Curve page and the Preamp page (docs/modules/peq.md "10-Band EQ").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * The editor (ui/m1plus_tenband.bin, a cards page: tools/pod_pages.py TENBAND_PAGE) is opened by the Equalizer page's 10-Band EQ link row (patch/peq_ui.c). It shows the graph card of patch/peqpage.c (the ten bands at 48 kHz, no preamp;
 * the code is shared) under a Curve row (opens the Curve page) at the top, the slider card, a Preamp row (opens the Preamp page) and Reset. The state is the record (patch/peq.c peq_state): the editor loads it as the page opens and again each time it is
 * back in front (after the Curve or Preamp page), changes its copy and saves it with peq_commit (patch/peq_ui.c: the same save, stock-switch and gain command as a tap on a preset on the Equalizer page, which makes the player reread the
 * record, a 20 ms ramp). An edit makes the 10-Band EQ the mode that plays (a preset file that played is left; the Equalizer page's check follows).
 *
 * The sliders are one view (pod_sliders, TB_H high, the list's width) painted in its EVT_BEFORE_PAINT: the card bitmap with the ten tracks baked in (made once), a thumb bitmap blitted per column at the band's gain, and, while a column
 * is dragged, a white pill bitmap behind its value; the ten values above and the ten frequencies under the columns are labels (children, painted over). The touch: a DOWN on the card takes the column under the finger (TB_COL_W wide, clamped
 * to the first and last) for the whole gesture and sets that band to the finger's height at once, each MOVE sets it again, a step is 0.5 dB (2 px), the range +-12 dB (TB_SPAN px) clamped. The gesture is the view's alone: DOWN
 * grabs the touch at the window (widget_grab(win, view), as the A-Z rail of patch/azlist.c does), so the moves and the release reach the view wherever the finger goes and the page's scroll_view, which would otherwise read a vertical
 * drag as a scroll of the page, never sees them; as a second guard the scroll_view's yslidable is turned off for the gesture and back on at its end (the view's UP, ABORT and the window coming to the front). A touch outside the card
 * (the 10 px beside it) does nothing. The rest of the page scrolls as any cards page does.
 *
 * Cost of a drag: a step that changes the value sets the band, moves the thumb and the value label (cheap). The graph (peq_compile + 249 responses + one 300 x 170 bitmap) is made again at most every TB_GRAPH_MS, and the record is
 * saved and the player told at most every TB_SEND_MS (the player reads the record file on each gain command, so the sound follows; a save is the tmp file, fsync and rename), and once more at the gesture's end. Event times are
 * the pointer events' own (milliseconds). Nothing here runs a timer, a hook or anything at boot.
 *
 * The Curve page (a check on the current curve) and the Preamp page (Auto with its current cut in grey, then 0 dB .. -12 dB) save and go back on a tap. Reset on Custom asks first (the stock confirm "Reset 10-Band EQ?").
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "i18n.h"
#include "peq.h"
#include "peqpage.h"
#include "keyboard.h"
#include "tenband.h"

extern void pod_toast(const char *text); /* patch/shuffle.c: the stock message box */

#define MINUS "\xe2\x88\x92" /* U+2212: the sign of a cut */
#define DOT " \xc2\xb7 "
#define TB_GRAPH_MS 60 /* the graph is made again at most this often while a slider is dragged */
#define TB_SEND_MS 150 /* the record is saved and the player told at most this often while a slider is dragged */
#define TB_GREY_VAL "#8A8A8A"
#define TB_PREAMP_ROWS 14 /* the Preamp page: Auto, then 0 .. -12 dB */
#define TB_REGION_PX 18 /* (the region line's font size: tools/pod_ui.py cards_region) */
#define STEP_MAX (PEQ_GAIN_MAX * 2)
#define I(w, off) (*(int *)((char *)(w) + (off)))

static struct {
    void *win, *sv, *graph, *gtop, *gbot, *view, *curve_row, *curve_val, *pre_row, *pre_val, *reset_row, *save_row;
    void *vlab[TB_COLS], *flab[TB_COLS], *region;
    void *card, *thumb, *pill; /* bitmaps: the card with its tracks, one thumb, the value pill (none: no memory) */
    peq_state st;
    peq_graph g;
    int drag, dirty, last_graph, last_send, sent,
        slide; /* drag: the column being dragged, -1 none; slide: yslidable before the gesture */
    int graph_due;
    int replaced; /* a drag has switched playback from a preset file to the 10-Band EQ (the message waits for the release) */
} tb __attribute__((section(".scratch")));

static struct {
    void *win, *check[PEQ_CURVES];
    void *row[PEQ_CURVES];
} tc __attribute__((section(".scratch")));

static struct {
    void *win, *auto_val, *check[TB_PREAMP_ROWS];
    void *row[TB_PREAMP_ROWS];
    peq_state st;
} tp __attribute__((section(".scratch")));

/* ---------------------------------------------------------------------------
 * Numbers and texts
 */
/* A gain as the sliders show it, no unit: "+4.5", "-2.5" (U+2212), "0", "+12". */
static void tb_gain_text(char *out, unsigned size, float g) {
    int g10 = (int)(g * 10 + (g < 0 ? -0.5f : 0.5f)), a = g10 < 0 ? -g10 : g10;
    if (!g10)
        snprintf(out, size, "0");
    else if (a % 10)
        snprintf(out, size, "%s%d.%d", g10 < 0 ? MINUS : "+", a / 10, a % 10);
    else
        snprintf(out, size, "%s%d", g10 < 0 ? MINUS : "+", a / 10);
}

/* A fixed preamp as the pages show it: "0 dB", "-3 dB" (the value form "%d dB" with U+2212 before a cut). */
static void tb_cut_text(char *out, unsigned size, int cut) {
    char num[24];
    pod_fmt(num, sizeof num, TR("%d dB"), cut);
    snprintf(out, size, "%s%s", cut > 0 ? MINUS : "", num);
}

/* The preamp row's grey text: "Auto - 5.0 dB" (the cut the player makes at 48 kHz) or "-3 dB". */
static void tb_preamp_text(char *out, unsigned size, const peq_state *s) {
    if (s->preamp == PEQ_PREAMP_AUTO) {
        peq_preset p;
        peq_tenband(&p, s->gain, PEQ_PREAMP_AUTO);
        pp_preamp(out, size, &p);
    } else
        tb_cut_text(out, size, s->preamp);
}

/* The column under a card-relative x (the first and the last take what is beside them), the half-decibel step of a card-relative y (+- STEP_MAX, the track's ends and past them clamp): 2 px a step, 0 at the track's middle. */
__attribute__((used, retain)) /* the tests call it; the page's own calls may inline it */
int tenband_col(int x) {
    int c = x < TB_X0 ? -1 : (x - TB_X0) / TB_COL_W;
    return c < 0 ? 0 : c > TB_COLS - 1 ? TB_COLS - 1 : c;
}

__attribute__((used, retain)) int tenband_step(int y) {
    int s = (TB_Y0 + TB_SPAN / 2 - y) /
            (TB_PX_DB /
             2); /* (truncated toward zero: 0 dB takes the three pixels around the middle, each other step two) */
    return s < -STEP_MAX ? -STEP_MAX : s > STEP_MAX ? STEP_MAX : s;
}

static int tb_center_x(int c) {
    return TB_X0 + c * TB_COL_W + TB_COL_W / 2;
} /* the column's middle pixel (the card's x) */

/* ---------------------------------------------------------------------------
 * Bitmaps: the card with its tracks, a thumb, the value pill (one grey and one alpha a pixel, antialiased)
 */
static double tb_clamp(double v, double lo, double hi) { return v < lo ? lo : v > hi ? hi : v; }

/* Coverage of pixel (x, y) in a w x h rounded rectangle of radius r. */
double tb_cover(int x, int y, int w, int h, double r) {
    double dx = x + 0.5 - w / 2.0, dy = y + 0.5 - h / 2.0;
    dx = (dx < 0 ? -dx : dx) - (w / 2.0 - r), dy = (dy < 0 ? -dy : dy) - (h / 2.0 - r);
    if (dx < 0) dx = 0;
    if (dy < 0) dy = 0;
    return tb_clamp(r + 0.5 - __builtin_sqrt(dx * dx + dy * dy), 0, 1);
}

/* A w x h bitmap whose pixel is made by fn (the grey in the low byte, the alpha in the top one); none with no memory. */
void *tb_make(int w, int h, unsigned (*fn)(int x, int y, int w, int h)) {
    int x, y;
    unsigned *px;
    void *b = bitmap_create_ex(w, h, w * 4, BITMAP_RGBA8888);
    if (!b) return (void *)0;
    px = (unsigned *)bitmap_lock_buffer_for_write(b);
    if (!px || bitmap_get_line_length(b) != (unsigned)(w * 4)) {
        if (px) bitmap_unlock_buffer(b);
        bitmap_destroy(b);
        return (void *)0;
    }
    for (y = 0; y < h; ++y)
        for (x = 0; x < w; ++x) px[y * w + x] = fn(x, y, w, h);
    bitmap_unlock_buffer(b);
    return b;
}

unsigned tb_px(double grey, double alpha) {
    return (unsigned)(alpha * 255 + 0.5) << 24 | (unsigned)(grey + 0.5) * 0x010101u;
}

/* The card: #1C1C1C with TB_R corners in the alpha and, per column, a track (a capsule TB_TRACK_W wide from +12 dB to -12 dB, grey 62). */
static unsigned tb_card_px(int x, int y, int w, int h) {
    double v = 28, a = 1;
    int c =
        (x - TB_X0) /
        TB_COL_W; /* (the one column whose track can reach this pixel: they are TB_COL_W apart, a track TB_TRACK_W wide) */
    if (x >= TB_X0 && c < TB_COLS) {
        double dx = x + 0.5 - (tb_center_x(c) + 0.5), r = TB_TRACK_W / 2.0, py = y + 0.5, y0 = TB_Y0,
               y1 = TB_Y0 + TB_SPAN;
        if (dx > -r - 1 && dx < r + 1 && py > y0 - r - 1 && py < y1 + r + 1) {
            double d;
            py = py < y0 ? y0 : py > y1 ? y1 : py; /* the nearest point of the track's axis */
            d = __builtin_sqrt(dx * dx + (y + 0.5 - py) * (y + 0.5 - py));
            v += (62 - v) * tb_clamp(r + 0.5 - d, 0, 1);
        }
    }
    if ((x < TB_R || x >= w - TB_R) && (y < TB_R || y >= h - TB_R)) a = tb_cover(x, y, w, h, TB_R);
    return tb_px(v, a);
}

/* The thumb: a white pill with a darker line across its middle. */
static unsigned tb_thumb_px(int x, int y, int w, int h) {
    double v = 242;
    if (y == h / 2 && x >= 6 && x < w - 6) v = 196;
    return tb_px(v, tb_cover(x, y, w, h, 5.5));
}

static unsigned tb_pill_px(int x, int y, int w, int h) { return tb_px(242, tb_cover(x, y, w, h, h / 2.0)); }

/* ---------------------------------------------------------------------------
 * The page
 */
static void tb_blit(void *canvas, void *bmp, int w, int h, int x, int y) {
    int src[4], dst[4];
    src[0] = src[1] = 0, src[2] = w, src[3] = h;
    dst[0] = x, dst[1] = y, dst[2] = w, dst[3] = h;
    canvas_draw_image(canvas, bmp, src, dst);
}

static int tb_thumb_y(float g) {
    return TB_Y0 + TB_SPAN / 2 - (int)(g * TB_PX_DB + (g < 0 ? -0.5f : 0.5f)) - TB_THUMB_H / 2;
}

/* The view's EVT_BEFORE_PAINT: the card, a thumb per column, the pill behind the dragged value. The labels are children: painted after. */
static int tb_on_paint(void *ctx, void *e) {
    void *canvas = e ? *(void **)((char *)e + EVENT_PAINT_CANVAS) : (void *)0;
    int c;
    (void)ctx;
    if (!canvas || !tb.win || !tb.card) return RET_OK;
    tb_blit(canvas, tb.card, TB_W, TB_H, TB_CARD_X, 0);
    if (tb.thumb)
        for (c = 0; c < TB_COLS; ++c)
            tb_blit(canvas, tb.thumb, TB_THUMB_W, TB_THUMB_H, TB_CARD_X + tb_center_x(c) - TB_THUMB_W / 2,
                    tb_thumb_y(tb.st.gain[c]));
    if (tb.pill && tb.drag >= 0)
        tb_blit(canvas, tb.pill, TB_PILL_W, TB_PILL_H, TB_CARD_X + tb_center_x(tb.drag) - TB_PILL_W / 2, TB_VAL_Y);
    return RET_OK;
}

static void tb_label_colors(void *w, const char *rgb) {
    static const char *const prop[3] = {"style:normal:text_color", "style:disable:text_color",
                                        "style:focused:text_color"};
    int s;
    for (s = 0; s < 3; ++s) widget_set_prop_str(w, prop[s], rgb);
}

static void tb_value_label(int c) {
    char text[16];
    tb_gain_text(text, sizeof text, tb.st.gain[c]);
    widget_set_text_utf8(tb.vlab[c], text);
}

/* The graph again from the bands, and its scale. */
static void tb_graph(void) {
    peq_preset p;
    peq_tenband(&p, tb.st.gain, 0); /* (the graph leaves the preamp out: a fixed 0 needs no peak search) */
    peq_graph_curve(&tb.g, &p);
    peq_graph_scale(&tb.g, tb.gtop, tb.gbot);
    peq_graph_draw(&tb.g);
    widget_invalidate_force(tb.graph, (void *)0);
    tb.graph_due = 0;
}

/* The Curve and Preamp rows' grey values. */
static void tb_rows(void) {
    char text[48];
    widget_set_tr_text(tb.curve_val, peq_curve_key(tb.st.curve));
    tb_preamp_text(text, sizeof text, &tb.st);
    widget_set_text_utf8(tb.pre_val, text);
}

/* Everything from the record: the graph, the ten values, the two rows, the sliders. */
static void tb_refresh(void) {
    int c;
    for (c = 0; c < TB_COLS; ++c) tb_value_label(c);
    tb_graph();
    tb_rows();
    widget_invalidate_force(tb.view, (void *)0);
}

/* Reads the record again: what the Curve and Preamp pages (or a failed save) left. */
static void tb_reload(void) { peq_state_load(&tb.st); }

static void tb_slide(int on) {
    if (!on) {
        tb.slide = widget_get_prop_int(tb.sv, "yslidable", 1);
        widget_set_prop_int(tb.sv, "yslidable", 0);
    } else
        widget_set_prop_int(tb.sv, "yslidable", tb.slide);
}

/* Saves the record and has the player play it (peq_commit); a failed save puts the page back to the record as it is. */
static void tb_commit(void) {
    tb.st.mode = PEQ_TENBAND_MODE;
    memset(tb.st.name, 0, sizeof tb.st.name);
    if (!peq_commit(&tb.st)) {
        tb_reload();
        tb_refresh();
    }
}

/* ---------------------------------------------------------------------------
 * The drag
 */
/* Band c to a step: a built-in curve is copied into Custom first (the previous Custom is overwritten), the curve reads Custom. 1 when the band moved. */
static int tb_set(int c, int step) {
    float g = step * 0.5f;
    int i;
    if (tb.st.gain[c] == g) return 0; /* (a touch that leaves the band where it is leaves a built-in curve alone too) */
    if (tb.st.curve != PEQ_CUSTOM) {
        for (i = 0; i < PEQ_TENBAND; ++i) tb.st.custom[i] = tb.st.gain[i];
        tb.st.curve = PEQ_CUSTOM;
        widget_set_tr_text(tb.curve_val, peq_curve_key(PEQ_CUSTOM));
    }
    tb.st.gain[c] = tb.st.custom[c] = g;
    return 1;
}

/* The region line between the graph and the slider card: what the dragged band's frequency is (one key per band, 13 languages), empty when no band is dragged. */
static void tb_region(int c) {
    static const char *const key[6] = {"Sub bass · rumble",
                                       "Mid bass · punch and warmth",
                                       "Lower mids · body and fullness",
                                       "Upper mids · shouty if too much",
                                       "Treble · detail and sparkle",
                                       "Air · openness"};
    static const unsigned char of[TB_COLS] = {0, 1, 1, 2, 2,
                                              3, 3, 3, 4, 5}; /* 31, 63, 125, 250, 500, 1k, 2k, 4k, 8k, 16k Hz */
    if (c >= 0)
        widget_set_tr_text(tb.region, key[of[c]]);
    else
        widget_set_text_utf8(tb.region, "");
}

static unsigned tb_time(void *e) { return (unsigned)I(e, 8); }

static void tb_follow(void *e) {
    int pt[2], c = tb.drag, moved;
    unsigned now = tb_time(e);
    pt[0] = I(e, PE_X), pt[1] = I(e, PE_Y);
    widget_to_local(tb.view, pt);
    moved = tb_set(c, tenband_step(pt[1]));
    if (!moved) return;
    if (tb.st.mode == PEQ_FILE && tb.st.name[0])
        tb.replaced = 1; /* this move switches to the 10-Band EQ (tb_commit below) */
    tb.dirty = 1;
    tb_value_label(c);
    widget_invalidate_force(tb.view, (void *)0);
    if (!tb.sent || now - (unsigned)tb.last_graph >= TB_GRAPH_MS)
        tb.last_graph = (int)now, tb_graph();
    else
        tb.graph_due = 1;
    if (!tb.sent || now - (unsigned)tb.last_send >= TB_SEND_MS) {
        tb.last_send = (int)now, tb.sent = 1;
        tb.dirty = 0;
        tb_commit();
    }
}

static void tb_end(void) {
    int c = tb.drag;
    if (c < 0) return;
    tb.drag = -1;
    widget_ungrab(tb.win, tb.view);
    tb_slide(1);
    tb_label_colors(tb.vlab[c], TB_GREY_VAL);
    tb_label_colors(tb.flab[c], TB_GREY_VAL);
    if (tb.dirty) tb_commit(); /* the last step, saved */
    tb.dirty = 0;
    if (tb.graph_due) tb_graph();
    tb_rows(); /* the Preamp row's Auto cut follows the gains */
    tb_region(-1);
    widget_invalidate_force(tb.view, (void *)0);
    if (tb.replaced) { /* the stock message box would take the touch if it opened mid-drag, so it waits for the release: once per switch, and only when the save took (a failed one reloaded the file) */
        if (tb.st.mode == PEQ_TENBAND_MODE) pod_toast(TR("Switched to 10-Band EQ"));
        tb.replaced = 0;
    }
}

static int tb_on_down(void *ctx, void *e) {
    int pt[2], c;
    (void)ctx;
    if (!e || !tb.win || tb.drag >= 0) return RET_OK;
    pt[0] = I(e, PE_X), pt[1] = I(e, PE_Y);
    widget_to_local(tb.view, pt);
    pt[0] -= TB_CARD_X;
    if (pt[0] < 0 || pt[0] >= TB_W || pt[1] < 0 || pt[1] >= TB_H) return RET_OK; /* beside the card */
    c = tenband_col(pt[0]);
    if (peq_state_load(&tb.st))
        tb_refresh(); /* a touch edits the record of the output playing now (a notify may not have reached the page yet) */
    tb.drag = c, tb.dirty = tb.sent = 0;
    widget_grab(tb.win, tb.view);
    tb_slide(0);
    tb_region(c);
    tb_label_colors(tb.vlab[c], "#000000"); /* the value on the pill, the frequency white */
    tb_label_colors(tb.flab[c], "#FFFFFF");
    tb_follow(e);
    widget_invalidate_force(tb.view, (void *)0); /* the pill, even when the band did not move */
    return RET_OK;
}

static int tb_on_move(void *ctx, void *e) {
    (void)ctx;
    if (e && tb.win && tb.drag >= 0) tb_follow(e);
    return RET_OK;
}

static int tb_on_up(void *ctx, void *e) {
    (void)ctx;
    if (e && tb.win && tb.drag >= 0) tb_follow(e); /* the release position counts */
    tb_end();
    return RET_OK;
}

static int tb_on_abort(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (tb.win) tb_end();
    return RET_OK;
}

/* ---------------------------------------------------------------------------
 * Rows
 */
static int tb_on_curve(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (tb.win) pod_open_tencurve();
    return RET_OK;
}

static int tb_on_preamp(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (tb.win) pod_open_tenpreamp();
    return RET_OK;
}

/* Reset: Flat and Auto (all ten gains 0). On Custom it erases the user's curve, so it asks first; a built-in curve is reset at once (the Curve page brings it back). */
static int tb_on_reset(void *ctx, void *e) {
    int i;
    (void)ctx;
    (void)e;
    if (!tb.win) return RET_OK;
    if (tb.st.curve == PEQ_CUSTOM) {
        if (!peq_ask(TR("Reset 10-Band EQ?"))) return RET_OK;
        for (i = 0; i < PEQ_TENBAND; ++i) tb.st.custom[i] = 0;
    }
    tb.st.curve = PEQ_FLAT;
    tb.st.preamp = PEQ_PREAMP_AUTO;
    for (i = 0; i < PEQ_TENBAND; ++i) tb.st.gain[i] = 0;
    tb_commit();
    tb_refresh();
    return RET_OK;
}

/* Save as Preset: the name entry, initial text the curve's name; its Done writes the record's curve as a preset file (peq_save_new), which
 * does not play: the record stays as it is. */
__attribute__((used, retain)) void
tenband_named(const char *text) { /* the keyboard's Done (the tests call it as the keyboard would) */
    peq_state s;
    peq_preset p, back;
    char file[PEQ_NAME];
    if (!tb.win) return;
    peq_state_load(&s);
    peq_tenband(&p, s.gain, s.preamp);
    if (peq_save_new(text, &p, file, &back)) pod_toast(TR("Saved as Preset"));
}

static int tb_on_save(void *ctx, void *e) {
    char init[PEQ_NAME];
    (void)ctx;
    (void)e;
    if (!tb.win) return RET_OK;
    snprintf(init, sizeof init, "%s", TR(peq_curve_key(tb.st.curve)));
    keyboard_open(TR("Save As"), "", init, tenband_named, (kb_cancel_fn)0, KB_DONE);
    return RET_OK;
}

/* Back in front (the Curve or Preamp page was open): the record again. */
static int tb_on_fg(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (!tb.win) return RET_OK;
    if (tb.drag >= 0) tb_end();
    tb_reload();
    tb_refresh();
    return RET_OK;
}

/* The output changed under the open editor (peqout_sync with notify): the new output's record is shown and edited, not the old one's copy. */
void tenband_output_changed(void) {
    if (!tb.win) return;
    tb_reload();
    tb_refresh();
}

/* The editor's bitmaps and graph go, the state is cleared. */
static void tb_release(void) {
    if (tb.win && tb.drag >= 0) tb_slide(1);
    if (tb.card) bitmap_destroy(tb.card);
    if (tb.thumb) bitmap_destroy(tb.thumb);
    if (tb.pill) bitmap_destroy(tb.pill);
    peq_graph_free(&tb.g);
    memset(&tb, 0, sizeof tb);
}

/* ctx is the window: the late destroy of an editor that a newer one replaced finds tb.win changed and leaves the newer one alone. */
static int tb_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx == tb.win) tb_release();
    return RET_OK;
}

int tenband_open(void) { return pod_open_tenband() == 0; }

static int tb_on_gpaint(void *ctx, void *e) {
    (void)ctx;
    if (tb.win) peq_graph_paint(&tb.g, e);
    return RET_OK;
}

void tenband_opened(void *win) {
    int c;
    char name[24];
    if (tb.win) { /* an editor exists already (opened from Now Playing's pull-down while it sat under other pages): the new one replaces it */
        void *old = tb.win;
        tb_release();
        if (widget_is_window_opened(old)) window_close(old);
    }
    memset(&tb, 0, sizeof tb);
    tb.graph = widget_lookup(win, "pod_graph", 1);
    tb.gtop = widget_lookup(win, "pod_gr_top", 1);
    tb.gbot = widget_lookup(win, "pod_gr_bot", 1);
    tb.view = widget_lookup(win, "pod_sliders", 1);
    tb.sv = widget_lookup(win, "pod_scrollview", 1);
    tb.curve_row = widget_lookup(win, "pod_row0", 1);
    tb.curve_val = widget_lookup(win, "pod_value0", 1);
    tb.pre_row = widget_lookup(win, "pod_row1", 1);
    tb.pre_val = widget_lookup(win, "pod_value1", 1);
    tb.reset_row = widget_lookup(win, "pod_row2", 1);
    tb.save_row = widget_lookup(win, "pod_row3", 1);
    tb.region = widget_lookup(win, "pod_region", 1);
    for (c = 0; c < TB_COLS; ++c) {
        snprintf(name, sizeof name, "pod_sl_v%d", c);
        tb.vlab[c] = widget_lookup(win, name, 1);
        snprintf(name, sizeof name, "pod_sl_f%d", c);
        tb.flab[c] = widget_lookup(win, name, 1);
        if (!tb.vlab[c] || !tb.flab[c]) goto bad;
    }
    if (!tb.graph || !tb.gtop || !tb.gbot || !tb.view || !tb.sv || !tb.curve_row || !tb.curve_val || !tb.pre_row ||
        !tb.pre_val || !tb.reset_row || !tb.save_row || !tb.region)
        goto bad;
    tb.drag = -1;
    tb.slide = 1;
    peq_state_load(&tb.st);
    tb.card = tb_make(TB_W, TB_H, tb_card_px);
    tb.thumb = tb_make(TB_THUMB_W, TB_THUMB_H, tb_thumb_px);
    tb.pill = tb_make(TB_PILL_W, TB_PILL_H, tb_pill_px);
    tb.win = win;
    tb_refresh();
    widget_on(tb.graph, EVT_BEFORE_PAINT, tb_on_gpaint, (void *)0);
    widget_on(tb.view, EVT_BEFORE_PAINT, tb_on_paint, (void *)0);
    widget_on(tb.view, EVT_POINTER_DOWN, tb_on_down, (void *)0);
    widget_on(tb.view, EVT_POINTER_MOVE, tb_on_move, (void *)0);
    widget_on(tb.view, EVT_POINTER_UP, tb_on_up, (void *)0);
    widget_on(tb.view, EVT_POINTER_ABORT, tb_on_abort, (void *)0);
    widget_on(tb.curve_row, EVT_CLICK, tb_on_curve, (void *)0);
    widget_on(tb.pre_row, EVT_CLICK, tb_on_preamp, (void *)0);
    widget_on(tb.reset_row, EVT_CLICK, tb_on_reset, (void *)0);
    widget_on(tb.save_row, EVT_CLICK, tb_on_save, (void *)0);
    widget_on(win, EVT_WINDOW_TO_FG, tb_on_fg, (void *)0);
    widget_on(win, EVT_DESTROY, tb_on_destroy, win);
    return;
bad: /* an asset that is not ours */
    memset(&tb, 0, sizeof tb);
}

/* ---------------------------------------------------------------------------
 * The Curve page: a check on the current curve; a tap picks it (its gains loaded: Custom is the user's), saves, and goes back.
 */
static int tc_on_pick(void *ctx, void *e) {
    peq_state s;
    (void)e;
    if (!tc.win) return RET_OK;
    peq_state_load(&s);
    peq_set_curve(&s, (int)(long)ctx);
    s.mode = PEQ_TENBAND_MODE;
    memset(s.name, 0, sizeof s.name);
    if (peq_commit(&s)) navigator_back();
    return RET_OK;
}

static int tc_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx == tc.win)
        memset(&tc, 0, sizeof tc); /* (a page a newer one replaced is destroyed late: leave the newer one) */
    return RET_OK;
}

void tencurve_opened(void *win) {
    peq_state s;
    int i;
    char name[24];
    if (tc.win) { /* a page exists already: the new one replaces it */
        void *old = tc.win;
        memset(&tc, 0, sizeof tc);
        if (widget_is_window_opened(old)) window_close(old);
    }
    memset(&tc, 0, sizeof tc);
    for (i = 0; i < PEQ_CURVES; ++i) {
        snprintf(name, sizeof name, "pod_row%d", i);
        tc.row[i] = widget_lookup(win, name, 1);
        snprintf(name, sizeof name, "pod_check%d", i);
        tc.check[i] = widget_lookup(win, name, 1);
        if (!tc.row[i] || !tc.check[i]) {
            memset(&tc, 0, sizeof tc);
            return;
        }
    }
    peq_state_load(&s);
    for (i = 0; i < PEQ_CURVES; ++i) {
        widget_set_visible(tc.check[i], i == s.curve, 0);
        widget_on(tc.row[i], EVT_CLICK, tc_on_pick, (void *)(long)i);
    }
    tc.win = win;
    widget_on(win, EVT_DESTROY, tc_on_destroy, win);
}

/* ---------------------------------------------------------------------------
 * The Preamp page: Auto (its grey value the cut Auto makes at 48 kHz now), then 0 dB .. -12 dB; a tap picks, saves and goes back.
 */
static int tp_on_pick(void *ctx, void *e) {
    int k = (int)(long)ctx;
    peq_state s;
    (void)e;
    if (!tp.win) return RET_OK;
    peq_state_load(&s);
    s.preamp = k ? k - 1 : PEQ_PREAMP_AUTO;
    s.mode = PEQ_TENBAND_MODE;
    memset(s.name, 0, sizeof s.name);
    if (peq_commit(&s)) navigator_back();
    return RET_OK;
}

static int tp_on_destroy(void *ctx, void *e) {
    (void)e;
    if (ctx == tp.win)
        memset(&tp, 0, sizeof tp); /* (a page a newer one replaced is destroyed late: leave the newer one) */
    return RET_OK;
}

void tenpreamp_opened(void *win) {
    int i;
    char name[24], text[32];
    peq_preset p;
    double lin;
    if (tp.win) { /* a page exists already: the new one replaces it */
        void *old = tp.win;
        memset(&tp, 0, sizeof tp);
        if (widget_is_window_opened(old)) window_close(old);
    }
    memset(&tp, 0, sizeof tp);
    tp.auto_val = widget_lookup(win, "pod_value0", 1);
    for (i = 0; i < TB_PREAMP_ROWS; ++i) {
        snprintf(name, sizeof name, "pod_row%d", i);
        tp.row[i] = widget_lookup(win, name, 1);
        snprintf(name, sizeof name, "pod_check%d", i);
        tp.check[i] = widget_lookup(win, name, 1);
        if (!tp.row[i] || !tp.check[i]) {
            memset(&tp, 0, sizeof tp);
            return;
        }
    }
    if (!tp.auto_val) {
        memset(&tp, 0, sizeof tp);
        return;
    }
    peq_state_load(&tp.st);
    peq_tenband(&p, tp.st.gain, PEQ_PREAMP_AUTO);
    lin = peq_preamp_gain(&p, 48000);
    pp_gain(text, sizeof text, pp_db10(lin * lin), 1);
    widget_set_text_utf8(tp.auto_val, text);
    for (i = 0; i < TB_PREAMP_ROWS; ++i) {
        char label[32];
        if (i) {
            tb_cut_text(label, sizeof label, i - 1);
            snprintf(name, sizeof name, "pod_label%d", i);
            widget_set_text_utf8(widget_lookup(win, name, 1), label);
        }
        widget_set_visible(tp.check[i], i == (tp.st.preamp == PEQ_PREAMP_AUTO ? 0 : tp.st.preamp + 1), 0);
        widget_on(tp.row[i], EVT_CLICK, tp_on_pick, (void *)(long)i);
    }
    tp.win = win;
    widget_on(win, EVT_DESTROY, tp_on_destroy, win);
}
