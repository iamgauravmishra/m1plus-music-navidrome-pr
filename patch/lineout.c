/* M1+ Music Line Out pill: an amber pill instead of the status bar's white "LO" text (docs/modules/lineout.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * While Line Out is on (the byte 0xa05aa7), stock's show_sysbar_face (0x544b48, the status bar's 1 s timer) and dropdown_showface (0x475c3c, the pull-down's own bar copy, its own timer)
 * put the text "LO" in label_volume instead of the volume number, then call widget_set_text_utf8(label_volume, text) (0x544f90 / 0x475ad8), having shown the label
 * (widget_set_visible 1) earlier in the same call. Both call-site words `jalr widget_set_text_utf8` are now `jal lo_set_text` (the delay slot `move a0, s7` and a1 = the text stay stock's).
 * lo_set_text runs stock's function first; then, if the text is exactly "LO" and the kill switch /mnt/mmc/m1plus-off is absent, it hides label_volume (visible and sensitive off) and shows the sibling pill
 * `pod_lo` (an image in the same group, hidden and insensitive in the UI files); otherwise it restores the label and hides the pill. It runs in both timers right where stock sets the text, so
 * nothing lags and nothing flickers (the label is shown and hidden inside one timer call, before any paint). The group's layouter skips an invisible child, so the pill takes the label's place.
 * Cost: one access and a parent lookup of a child by name per second per bar; no allocation, no state. Not on the boot path.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"
#include "lineout.h"

static void lo_show(void *w, int on) {
    widget_set_visible(w, on, 0);
    widget_set_sensitive(w, on);
}

/* The hooks (tools/pod.py LINEOUT_SITES): stock's widget_set_text_utf8(label, text), then the pill swap. */
int lo_set_text(void *label, const char *text) {
    int r = widget_set_text_utf8(label, text);
    void *parent, *pill;
    if (!label) return r;
    parent = (void *)((int *)label)[LO_W_PARENT / 4];
    if (!parent) return r;
    pill = widget_lookup(parent, LO_PILL, 0);
    if (!pill) return r; /* no pill in this bar: stock's "LO" text stays */
    if (text && text[0] == 'L' && text[1] == 'O' && !text[2] && access(KILL_SD, F_OK) != 0) {
        lo_show(label, 0);
        lo_show(pill, 1);
    } else {
        lo_show(label, 1);
        lo_show(pill, 0);
    }
    return r;
}
