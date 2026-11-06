/* Per-output EQ (patch/peqout.c, docs/modules/peq.md "Per-output EQ"): constants the payload and test/pod/peq.py share.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once
#include "peq.h"

enum { PO_HEADPHONES, PO_LINEOUT, PO_USB, PO_N }; /* the outputs that keep an EQ of their own */

#define PO_OUTPUT_FILE \
    "/mnt/data/m1plus/playback-eq-output" /* which output the playing record belongs to, and each output's Equalizer switch */
#define PO_MAGIC "M1PEQO1" /* 8 bytes with its NUL */

int peqout_current(void); /* the output now: PO_HEADPHONES (the jacks, and Bluetooth), PO_LINEOUT or PO_USB */
const char *peqout_key(
    int output); /* its translation key for the Equalizer page's grey line: "For Headphones", "For Line Out", "For USB DAC" */
int peqout_sync(
    int notify); /* the output changed since the last call: the playing record goes to the old output's slot and the new output's comes back; 1 when it switched */
int peqout_renamed(
    const char *from,
    const char
        *to); /* a preset file was renamed: the output slots that name it follow; 0 when one could not be rewritten */
int peqout_deleted(
    const char *
        file); /* a preset file was deleted: the output slots that name it point at the 10-Band EQ with the switch off; 0 when one could not be rewritten */
int peqout_session(
    void); /* an edit session's owner token: the output playing now, plus 1 (0 is "no live edit yet"); taken when a live edit is committed or an earlier session's edits are found in the record */
int peqout_away(
    int session); /* the output changed since `session` was taken (syncs first, the status bar's timer may not have run yet): the record playing now is not the session's */
int peqout_session_filed(
    int session, const char *from, const char *to,
    const peq_preset *
        p); /* the session's output slot, if it is in file mode and names `from`, takes the preset `p` and the name `to`; 0 when it could not be rewritten, 1 otherwise (also with nothing to do) */
int peqout_playing_filed(
    const char *file,
    const peq_preset *
        p); /* the record playing now, if it is in file mode and names `file`, takes the preset `p` (the player told when the Equalizer is on); 0 when it could not be written, 1 otherwise */
void peq_output_changed(
    void); /* patch/peq_ui.c: peqout_sync switched outputs on the UI thread: the open EQ pages reload the record and redraw */
