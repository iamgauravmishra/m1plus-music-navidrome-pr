/* Song list operations shared by the Songs page and the album page (patch/songops.h has the design).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "covercache.h"
#include "i18n.h"
#include "podcasts.h"
#include "songops.h"

extern void pod_toast(const char *text); /* patch/shuffle.c: the stock message box */
extern void pod_set_in_order(void); /* patch/shuffle.c: Shuffle and Repeat one become List play */
extern void pod_set_mode(int mode); /* patch/shuffle.c: the stock play mode */
extern unsigned pod_rand(unsigned n); /* patch/shuffle.c: 0 .. n - 1 */

#define I(w, off) (*(int *)((char *)(w) + (off)))

static int so_marked(const unsigned char *sel, unsigned i) { return sel[i >> 3] >> (i & 7) & 1; }

int so_selection(unsigned count, const unsigned char *sel) {
    unsigned i;
    if (!*(void **)SEL_VEC) return 0;
    select_recordinit((int)count);
    for (i = 0; i < count; ++i)
        if (so_marked(sel, i)) set_selectindex((int)i);
    return 1;
}

/* The stock confirm dialog: modal, the button pressed is the result. */
static void so_ask(const char *text, int kind, int *answer) {
    struct {
        int kind, ms;
        char text[MSGINFO_TEXT], text2[MSGINFO_TEXT];
    } info;
    unsigned i;
    memset(&info, 0, sizeof info);
    info.kind = kind;
    for (i = 0; text[i] && i < sizeof info.text - 1; ++i) info.text[i] = text[i];
    *answer = navigator_to_with_context("dialog/confirminfo_dialog", &info);
}

/* Delete: the stock handler's sequence (@0x527f48): nothing selected is a message; the confirm dialog (0xa: the library only, 0x14: the files too); then
 * batch_delete_file on the shown list and the selection; the message. The stock handler leaves the list as it was (the page rebuilds on its next show): the pages read it again.
 * The class is the list's, as the stock handler passes g_class_type: batch_delete_file removes the songs from the library (the generic loop: the library, Hi-Res,
 * Recently Added, an album's tracks), from myfav, oftenplay, recentplay or the playlist (its jump tables @0x74b7b0, @0x74b7d4; docs/modules/addresses.md), and the files when asked. */
int so_delete(int cls, void *list, unsigned count, const unsigned char *sel, unsigned nsel, int valid) {
    int r;
    if (!nsel) {
        pod_toast(TR("msg_delsongfailed"));
        return 0;
    }
    so_ask(TR("msg_delsong"), CONFIRM_KIND_DELETE, &r);
    if (r != CONFIRM_DELETE_LIBRARY && r != CONFIRM_DELETE_FILE) return 0;
    if (!valid || !so_selection(count, sel)) return -1;
    batch_delete_file(cls, list, *(void **)SEL_VEC, 0, r == CONFIRM_DELETE_FILE);
    pod_toast(TR("msg_delsongsuccess"));
    return 1;
}

/* Add to playlist: the stock Add button's path (@0x5280c0) to its playlist picker: playlist_page with the add context; tapping a playlist there adds the
 * selection (batch_add_file on *pdeq_showlist and the vector) and closes the picker. The title the picker may overwrite and the browsing class it sets are put back
 * by the page when its window is back in front. */
int so_add(int cls, unsigned count, const unsigned char *sel, unsigned nsel, int valid, char *title_save, int *picker) {
    if (!nsel) {
        pod_toast(TR("msg_addfailed"));
        return 0;
    }
    if (!valid || !so_selection(count, sel)) return -1;
    memcpy(title_save, (void *)NAV_TITLE, 0x200);
    *(int *)NAVIGATION_STATUS =
        0; /* the picker's mode is a page that is not in multi-select (@0x53d300 tests navigation_status != 1) */
    *picker = 1;
    navigator_to_with_context(
        "playlist_page",
        (const void *)(long)(PICKER_ADD | cls)); /* batch_add_file takes the class from it, as from the stock button */
    return 1;
}

/* Song `at` (-1: a random one) of the list and the list as the queue, in Now Playing: the stock Songs row's handler (@0x5275a4: loadSongList of the shown list, then
 * Now Playing at the row), as Shuffle Songs does it (patch/shuffle.c). The caller has put the browsing record back (loadSongList runs the class query again and keeps
 * classinfo for the memory playback). */
void so_play(int cls, void *list, int at, int how, so_open_fn open) {
    void *pick, *queue, *first;
    unsigned n, idx = 0, count = deque_size(list);
    int found;
    if (at < 0 && count) at = (int)pod_rand(count);
    if (at < 0 || at >= (int)count) return;
    pick = deque_at(list, (unsigned)at);
    queue = _create_deque("stSongInfo");
    if (!queue) return;
    deque_init(queue);
    found = loadSongList(queue, cc_str(pick, REC_NAME), I(pick, REC_CUE_START), cls);
    n = deque_size(queue);
    if (n) { /* loadSongList finds a song by file name and CUE start: a duplicate name (01.flac) would always start at the first, so the row's own index wins */
        if ((unsigned)at < n && !strcmp(cc_str(deque_at(queue, (unsigned)at), REC_PATH), cc_str(pick, REC_PATH)))
            idx = (unsigned)at;
        else if (found >= 0 && (unsigned)found < n)
            idx = (unsigned)found;
    }
    if (how == SO_SHUFFLE &&
        n) { /* a shuffle leaves the podcast episodes out (patch/pcmodel.c; the queue itself when there are none) */
        int at_i = (int)idx;
        queue = pc_strip(queue, &at_i);
        idx = (unsigned)at_i;
        n = queue ? deque_size(queue) : 0;
        if (!queue) {
            pod_toast(TR("Update Local Music first"));
            return;
        }
    }
    first = n ? deque_at(queue, idx) : (void *)0;
    if (!first || access(cc_str(first, REC_PATH), F_OK)) {
        deque_destroy(queue);
        pod_toast(TR(n ? "Storage unavailable" : "Update Local Music first"));
        return;
    }
    if (how == SO_IN_ORDER)
        pod_set_in_order(); /* Play: the list in order, even after a Shuffle; a row tap keeps the mode, as stock */
    else if (how == SO_SHUFFLE)
        pod_set_mode(MODE_SHUFFLE);
    *(int *)G_CLASS_TYPE = cls; /* as allmusic_page_init leaves it */
    open(queue, (int)idx, cls);
    deque_destroy(queue);
}
