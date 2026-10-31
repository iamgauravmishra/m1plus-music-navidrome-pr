/* M1+ Music's own on-screen QWERTY keyboard (patch/keyboard.c, docs/modules/keyboard.md): the API, and the geometry that tools/pod_keyboard.py repeats.
 * test/pod/keyboard.py parses the #defines in this file, so the asset, the payload and the preview cannot drift apart.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

/* Open the keyboard page over whatever is in front: a navbar (Back = cancel), a search field with the placeholder, and the pad.
 *   title        the navbar's title, UTF-8 and already translated; NULL keeps the page's own ("Keyboard")
 *   placeholder  the grey text of the empty field (UTF-8, already translated); NULL or "" for none
 *   initial      the field's text to start with (UTF-8, at most KB_MAX bytes, cut on a character boundary); NULL for none
 *   on_done      Search with a non-empty text: called with the text (spaces at both ends removed) right after the page was told to close
 *   on_cancel    Back (the navbar's or the hardware key) without Search; NULL for none
 *   flags        KB_LOG: every touch on the pad and every key is appended to the Network Probe's log (/mnt/mmc/m1plus-probe.log)
 * Returns 0 once the page is up, -1 when it could not open (another keyboard is still there: one at a time, also from inside a callback, since the page is
 * destroyed only after the callback ran; or the asset is not ours). The callbacks run on the UI thread, from the event that closed the page (on_cancel for the hardware
 * Back key from the page's destroy event); the page is gone or closing, so a callback must not use it. */
typedef void (*kb_done_fn)(const char *text);
typedef void (*kb_cancel_fn)(void);
#define KB_LOG 1
int keyboard_open(const char *title, const char *placeholder, const char *initial, kb_done_fn on_done,
                  kb_cancel_fn on_cancel, unsigned flags);
/* The Developer row Keyboard: keyboard_open with a placeholder, KB_LOG, and Search showing the text in a toast. */
void keyboard_test(void);

#define KB_W 320
#define KB_H 180 /* the pad's height; its top is at 450 - KB_H in the window */
#define KB_WIN_H 450
#define KB_PAD 6 /* the padding above and under the four rows */
#define KB_PITCH 44 /* the rows' pitch */
#define KB_KH 36 /* every key's height */
#define KB_KW 29 /* a char key's width: ten across with KB_GAP between */
#define KB_GAP 3
#define KB_NUM_KW 41 /* the third row's keys on the 123 and #+= pages */
#define KB_FN_W 40 /* shift, #+= and delete */
#define KB_MODE_W 74 /* 123 / ABC and Search */
#define KB_EDGE 2 /* the left margin of a full row (the right one is 1) */
#define KB_LANG_W 40 /* the language key of row four (more than one keyboard on); space gives it room */
#define KB_KEYS 26 /* char key widgets */
#define KB_MAX 63 /* bytes of text */
#define KB_POP_W 46 /* the key pop-up: the balloon */
#define KB_POP_H 50
#define KB_POP_GAP 10 /* above the key */
#define KB_STEM_UP 12 /* the stem rises to this far under the balloon's bottom edge */
#define KB_TEXT_X 30 /* the field's text and caret start (field coordinates) */
#define KB_TEXT_W 228 /* the room for the text */
#define KB_CARET_Y 7
#define KB_HOLD_MS 80 /* delete repeats on this tick ... */
#define KB_HOLD_TICKS 6 /* ... after this many ticks of holding */

/* The Chinese (Pinyin) layer: the candidate strip above the pad and the engine it asks (docs/modules/keyboard.md) */
#define KB_STRIP_Y 234 /* the strip's top in the window (the pad's top minus its height) */
#define KB_STRIP_H 36
#define KB_POOL 12 /* candidate item widgets; at most this many items are on screen */
#define KB_PY_X 8 /* the pinyin label: its left margin, the room it may take */
#define KB_PY_MAX 120
#define KB_CAND_PAD 12 /* the padding either side of a candidate's text, the narrowest and the widest item */
#define KB_CAND_MIN 36
#define KB_CAND_MAXW 230
#define KB_CHL_Y 4 /* the pressed item's highlight */
#define KB_CHL_H 28
#define KB_SEP_Y 8 /* the divider between the pinyin and the candidates */
#define KB_SEP_H 20
#define KB_DRAG 6 /* px a finger moves before a press on the strip is a scroll */
#define KB_MAX_CAND 100 /* candidates taken from the engine for one input */
#define KB_CHUNK 12 /* ... this many at a time, more as the strip scrolls towards its end */
#define KB_POOL_BYTES 4096 /* the UTF-8 of the candidates read */
#define KB_PRED 10 /* predictions asked for after a commit */
#define KB_RAW_MAX 39 /* letters of pinyin the engine takes */
#define KB_CAND_U16 48 /* char16 units given to im_get_candidate, the terminator included */
#define PINYIN_DICT "/release/assets/default/raw/data/gpinyin.dat" /* stock ships it; nothing else loads it */
#define PINYIN_USER "/proc/m1plus/pinyin-user.dat" /* neither readable nor creatable: no learning */
