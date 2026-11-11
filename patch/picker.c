/* The Add to Playlist picker (patch/picker.h; docs/modules/picker.md has the design and the stock code read).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * Stock's picker is playlist_page opened with PICKER_ADD | class; its row handler (@0x53d300) calls batch_add_file(class, 0xf00b, *pdeq_showlist, *SEL_VEC, the playlist's
 * id), shows msg_addplaylistsuccess and closes. Ours is the Playlists page in pick mode (patch/playlists.c); a tap there comes here with the playlist's id.
 *
 * The page reads every playlist (loadLocalClassList(0xff13) for its count and mosaic), and each read replaces *pdeq_showlist, the list the add needs. So the picker
 * copies the list (cc_copy_list) and the marks when it opens, and the add runs on the copy: the stock selection vector is filled from the marks at that moment (as
 * so_selection does for the stock picker) and batch_add_file takes the list as an argument. The browsing class, classinfo[0..1] and the navigation title that those
 * queries change are put back after each of them and when the page goes (the caller's own restore, patch/songs.c and patch/albumpage.c, then finds them as they were).
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "covercache.h"
#include "i18n.h"
#include "songops.h"
#include "picker.h"
#include "home.h"
#include "playlists.h"

static struct {
    int on, done;
    void *list; /* the copy of *pdeq_showlist at open */
    unsigned char *sel; /* the marks at open */
    unsigned count;
    int cls; /* the browsing class of the list: batch_add_file's first argument, as the stock picker's context carries it */
    int cls0, ci[2];
    char title[NAV_TITLE_SIZE];
} pk __attribute__((section(".scratch")));

void picker_restore(void) {
    if (!pk.on) return;
    *(int *)G_CLASS_TYPE = pk.cls0;
    memcpy((void *)CLASSINFO, pk.ci, sizeof pk.ci);
    memcpy((void *)NAV_TITLE, pk.title, sizeof pk.title);
}

void picker_release(void) {
    if (!pk.on) return;
    picker_restore();
    if (pk.list) deque_destroy(pk.list);
    free(pk.sel);
    memset(&pk, 0, sizeof pk);
}

int picker_open(int cls, unsigned count, const unsigned char *sel) {
    void *list = *(void **)PDEQ_SHOWLIST;
    unsigned bytes = (count + 7) / 8;
    if (pk.on || !count || !list || deque_size(list) != count) return -1;
    pk.on = 1; /* from here picker_release undoes what is made */
    pk.list = cc_copy_list(list);
    pk.sel = calloc(bytes, 1);
    if (!pk.list || !pk.sel || deque_size(pk.list) != count) {
        picker_release();
        return -1;
    }
    memcpy(pk.sel, sel, bytes);
    pk.count = count, pk.cls = cls;
    pk.cls0 = *(int *)G_CLASS_TYPE;
    memcpy(pk.ci, (void *)CLASSINFO, sizeof pk.ci);
    memcpy(pk.title, (void *)NAV_TITLE, sizeof pk.title);
    if (playlists_pick() < 0) {
        picker_release();
        return -1;
    }
    return 1;
}

/* The stock row handler's sequence: the selection into the stock vector, batch_add_file (duplicates skipped by checkPlayListExist; the rows of the copy get the new
 * ids), the message. A selection that cannot be made is msg_addfailed. PICKER_FAVOURITES is the stock Add button's Favourites choice (@0x5281c8):
 * batch_add_file(class, 0xf00a, list, vector, 0), then msg_addfavsuccess. */
void picker_add(int playlist) {
    int fav = playlist == PICKER_FAVOURITES;
    if (!pk.on || pk.done) return;
    pk.done = 1;
    if (!so_selection(pk.count, pk.sel)) {
        pod_toast(TR("msg_addfailed"));
        return;
    }
    batch_add_file(pk.cls, fav ? CLASS_FAV : CLASS_PLAYLISTS, pk.list, *(void **)SEL_VEC, fav ? 0 : playlist);
    pod_toast(TR(fav ? "msg_addfavsuccess" : "msg_addplaylistsuccess"));
}
