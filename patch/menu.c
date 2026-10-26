/* M1 Pod's customisable main menu: which items show, in which order, and the Main Menu page that edits it.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * The menu's asset (ui/m1pod_menu.bin) holds a stock list row for every item in the default order, then the
 * Extras and Settings rows; ui/m1pod_extras.bin holds a row for every item, then the stock Home tiles. The
 * setting is one small file, MENU_FILE: the shown items in menu order, one digit (the item id, its row index)
 * each, then a newline ("0123456\n" is the default). It is read, strictly, every time the menu or Extras page
 * opens (and when the menu comes back to the foreground after the Main Menu page): known ids only, no
 * duplicates, at most POD_MENU_ITEMS of them, a file shorter than POD_MENU_FILE_MAX; anything else, or no file,
 * is the default list. Nothing here can fail the page open: a row or the list missing from the tree leaves
 * the asset as it is, and Extras and Settings are rows the arrangement never hides.
 *
 * Arranging is plain widget calls on the stock list: a hidden row is hidden and insensitive (this AWTK
 * hit-tests hidden widgets) and parked at y 0, the shown ones are moved to y = position x ROW_H, and the
 * scroll_view's virtual_h and offset are set for the shown rows (the Artists list does the same for its
 * rows). Extras shows first the items the menu hides, then its stock rows.
 *
 * The Main Menu page (ui/m1pod_mainmenu.bin, opened by patch/m1pod.c): a row per item with a switch (the row
 * takes the tap) and an up arrow on every shown item but the first. The shown items come first in menu order,
 * the hidden ones after them in the default order; a switch shows or hides an item (shown ones join the end of
 * the menu), an arrow moves it one place up. Each change is saved at once (a failed save is undone) and the
 * rows move in place; the menu re-arranges itself when it is back in front.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"

#define N POD_MENU_ITEMS

static struct {
    unsigned char order[N];   /* the shown items, in menu order */
    unsigned n;
} mn __attribute__((section(".scratch")));

static struct {   /* the Main Menu page while it is open */
    void *row[N], *sw[N], *up[N];
    unsigned char order[N];   /* every item: the shown ones in menu order, then the hidden ones */
} cm __attribute__((section(".scratch")));

static void mn_defaults(void) {
    unsigned i;
    for (i = 0; i < POD_MENU_DEFAULT; i++) mn.order[i] = (unsigned char)i;
    mn.n = POD_MENU_DEFAULT;
}

/* The saved list, or the defaults. */
static void mn_load(void) {
    char buf[POD_MENU_FILE_MAX];
    int fd, n;
    unsigned i, len, seen = 0;
    mn_defaults();
    fd = open(MENU_FILE, 0, 0);
    if (fd < 0) return;
    n = read(fd, buf, sizeof buf);
    close(fd);
    if (n <= 0 || n >= (int)sizeof buf) return;   /* empty, or too long to be a list */
    len = (unsigned)n - (buf[n - 1] == '\n');
    if (len > N) return;
    for (i = 0; i < len; i++) {
        unsigned id = (unsigned char)buf[i] - '0';
        if (id >= N || (seen >> id & 1)) return;
        seen |= 1u << id;
    }
    for (i = 0; i < len; i++) mn.order[i] = (unsigned char)(buf[i] - '0');
    mn.n = len;
}

static int mn_save(void) {
    char buf[N + 2];
    unsigned i;
    for (i = 0; i < mn.n; i++) buf[i] = (char)('0' + mn.order[i]);
    buf[mn.n] = '\n';
    buf[mn.n + 1] = 0;
    return home_write_atomic(MENU_FILE, MENU_TMP, buf);
}

static void mn_show(void *w, int on) {
    widget_set_visible(w, on, 0);
    widget_set_sensitive(w, on);
}

static void *mn_find(void *win, const char *base, unsigned i) {
    char name[24];
    snprintf(name, sizeof name, "%s%u", base, i);
    return widget_lookup(win, name, 1);
}

/* Row w at position pos (shown) or parked and hidden. */
static void mn_place(void *w, unsigned pos, int on) {
    widget_move(w, 0, on ? (int)pos * POD_ROW_H : 0);
    mn_show(w, on);
}

static int mn_shown(unsigned id) {
    unsigned i;
    for (i = 0; i < mn.n; i++) if (mn.order[i] == id) return 1;
    return 0;
}

/* The menu (extras 0) or the Extras page (extras 1) as the saved list says. */
void menu_arrange(void *win, int extras) {
    void *sv = widget_lookup(win, "pod_scrollview", 1), *row[POD_EXTRAS_ROWS];
    unsigned total = extras ? POD_EXTRAS_ROWS : POD_MENU_ROWS, i, pos = 0;
    if (!sv) return;
    for (i = 0; i < total; i++) {
        row[i] = mn_find(win, "pod_row", i);
        if (!row[i]) return;   /* not our asset: leave it as it is */
    }
    mn_load();
    if (extras) {
        for (i = 0; i < N; i++) if (mn_shown(i)) mn_place(row[i], 0, 0);
        for (i = 0; i < N; i++) if (!mn_shown(i)) mn_place(row[i], pos++, 1);
        for (i = N; i < total; i++) mn_place(row[i], pos++, 1);
    } else {
        for (i = 0; i < N; i++) if (!mn_shown(i)) mn_place(row[i], 0, 0);
        for (i = 0; i < mn.n; i++) mn_place(row[mn.order[i]], pos++, 1);
        for (i = N; i < total; i++) mn_place(row[i], pos++, 1);   /* Extras, Settings */
    }
    widget_set_prop_int(sv, "virtual_h", (int)pos * POD_ROW_H);
    widget_set_prop_int(sv, "yoffset", 0);
}

/* ---- the Main Menu page */

static void cm_rebuild(void) {
    unsigned i, k = mn.n;
    for (i = 0; i < mn.n; i++) cm.order[i] = mn.order[i];
    for (i = 0; i < N; i++) if (!mn_shown(i)) cm.order[k++] = (unsigned char)i;
}

static void cm_layout(void) {
    unsigned pos;
    for (pos = 0; pos < N; pos++) {
        unsigned id = cm.order[pos];
        int on = pos < mn.n;
        widget_move(cm.row[id], 0, (int)pos * POD_ROW_H);
        image_base_set_image(cm.sw[id], on ? "sset_on" : "sset_off");
        mn_show(cm.up[id], on && pos > 0);
    }
}

/* Keep the change if it saved, else put the list back. */
static void cm_commit(const unsigned char *old, unsigned old_n) {
    unsigned i;
    if (mn_save() != 0) {
        for (i = 0; i < old_n; i++) mn.order[i] = old[i];
        mn.n = old_n;
    }
    cm_rebuild();
    cm_layout();
}

static int cm_on_row(void *ctx, void *e) {
    unsigned id = (unsigned)(long)ctx, i, k = 0;
    unsigned char old[N];
    unsigned old_n = mn.n;
    (void)e;
    for (i = 0; i < mn.n; i++) old[i] = mn.order[i];
    if (mn_shown(id)) {
        for (i = 0; i < old_n; i++) if (old[i] != id) mn.order[k++] = old[i];
        mn.n = k;
    } else if (mn.n < N) {
        mn.order[mn.n++] = (unsigned char)id;
    }
    cm_commit(old, old_n);
    return RET_OK;
}

static int cm_on_up(void *ctx, void *e) {
    unsigned id = (unsigned)(long)ctx, i, k;
    unsigned char old[N];
    unsigned old_n = mn.n;
    (void)e;
    for (i = 0; i < mn.n; i++) old[i] = mn.order[i];
    for (k = 1; k < mn.n; k++) {
        if (mn.order[k] != id) continue;
        mn.order[k] = mn.order[k - 1];
        mn.order[k - 1] = (unsigned char)id;
        cm_commit(old, old_n);
        break;
    }
    return RET_OK;
}

static int cm_on_destroy(void *ctx, void *e) {
    (void)ctx; (void)e;
    memset(&cm, 0, sizeof cm);
    return RET_OK;
}

/* The Main Menu page is up (patch/m1pod.c open_page): lay it out from the saved list and bind its rows. */
void menu_custom_opened(void *win) {
    unsigned i;
    for (i = 0; i < N; i++) {
        cm.row[i] = mn_find(win, "pod_row", i);
        cm.sw[i] = mn_find(win, "pod_switch", i);
        cm.up[i] = mn_find(win, "pod_up", i);
        if (!cm.row[i] || !cm.sw[i] || !cm.up[i]) {   /* not our asset: leave it as it is */
            memset(&cm, 0, sizeof cm);
            return;
        }
    }
    mn_load();
    cm_rebuild();
    cm_layout();
    for (i = 0; i < N; i++) {
        widget_on(cm.row[i], EVT_CLICK, cm_on_row, (void *)(long)i);
        widget_on(cm.up[i], EVT_CLICK, cm_on_up, (void *)(long)i);
    }
    widget_on(win, EVT_DESTROY, cm_on_destroy, (void *)0);
}
