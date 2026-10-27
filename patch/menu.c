/* M1+ Pod's customisable main menu: which items show, in which order, and the Main Menu page that edits it.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * The menu's asset (ui/m1pod_menu.bin) holds a stock list row for every item in the default order (the nine
 * menu items, then the nine Extras tiles: Favorites ... CD Ripper), then the Extras and Settings rows;
 * ui/m1pod_extras.bin holds the same row for every item. The setting is one small file, MENU_FILE: the shown
 * items in menu order, one character each (the item id, its row index: '0'..'8', then 'a'..'i' for ids 9..17),
 * then a newline ("0123456\n" is the default). It is read, strictly, every time the menu or Extras page
 * opens (and when the menu comes back to the foreground after the Main Menu page): known characters only, no
 * duplicates, at most POD_MENU_ITEMS of them, a file shorter than POD_MENU_FILE_MAX; anything else, or no file,
 * is the default list. Nothing here can fail the page open: a row or the list missing from the tree leaves
 * the asset as it is, and Extras and Settings are rows the arrangement never hides.
 *
 * Arranging is plain widget calls on the stock list: a hidden row is hidden and insensitive (this AWTK
 * hit-tests hidden widgets) and parked at y 0, the shown ones are moved to y = position x ROW_H, and the
 * scroll_view's virtual_h and offset are set for the shown rows (the Artists list does the same for its
 * rows), and the children are stacked in the order they are shown (the stock list_view lays its visible rows out in child
 * order whenever the window is marked for relayout, and its paint hook assumes y order; see menu_arrange). Extras shows the
 * items the menu does not show in a fixed order (tools/pod_pages.py EXTRAS_ORDER): the default menu items if hidden,
 * the Library group, the Tools group, each alphabetical by the English label.
 *
 * The Main Menu page (ui/m1pod_mainmenu.bin, opened by patch/m1pod.c): a row per item with a switch and an up
 * arrow on every shown item but the first, both pictures (insensitive); the row takes every tap and decides by
 * where it is: on the arrow's rectangle it moves the item one place up, elsewhere it shows or hides the item
 * (shown ones join the end of the menu). The shown items come first in menu order, the hidden ones after them
 * in the default order. Each change is saved at once (a failed save is undone) and the
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
    void *row[N], *sw[N], *up[N], *win, *sv;
    unsigned char order[N];   /* every item: the shown ones in menu order, then the hidden ones */
    unsigned down, pressed;   /* item id + 1 of the row a touch went down on / of the arrow showing its pressed look (0: none) */
    int zone;                 /* that touch went down inside the row's arrow rectangle */
} cm __attribute__((section(".scratch")));

static const unsigned char EX_ORDER[N] = POD_EXTRAS_ORDER;   /* the Extras page's rows (item ids), top to bottom */

static void mn_defaults(void) {
    unsigned i;
    for (i = 0; i < POD_MENU_DEFAULT; i++) mn.order[i] = (unsigned char)i;
    mn.n = POD_MENU_DEFAULT;
}

/* The item id of a saved character ('0'..'8' the menu items, 'a'..'i' the Extras tiles, ids 9..17), or 255. */
static unsigned mn_id(unsigned c) {
    if (c - '0' < 9) return c - '0';
    if (c - 'a' < 9) return 9 + c - 'a';
    return 255;
}

static char mn_char(unsigned id) {
    return (char)(id < 9 ? '0' + id : 'a' + (id - 9));
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
        unsigned id = mn_id((unsigned char)buf[i]);
        if (id >= N || (seen >> id & 1)) return;
        seen |= 1u << id;
    }
    for (i = 0; i < len; i++) mn.order[i] = (unsigned char)mn_id((unsigned char)buf[i]);
    mn.n = len;
}

static int mn_save(void) {
    char buf[N + 2];
    unsigned i;
    for (i = 0; i < mn.n; i++) buf[i] = mn_char(mn.order[i]);
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

/* The stock list_view gives its scroll_view a paint-children hook (list_view_on_add_child, sw 0xf4 @0x60cd10, stock
 * function 0x60c164) that returns at the first visible child whose top is below the canvas: it takes the children to be
 * in y order. The plain painter (what a scroll_view outside a list_view uses) has no such early exit, so a page whose
 * rows are placed by hand lets the scroll_view use that one. Only the exact stock hook on a real scroll_view is cleared. */
static void mn_plain_paint(void *sv) {
    if (*(unsigned *)((char *)sv + W_VT) == SV_VTABLE && *(unsigned *)((char *)sv + SV_PAINT_CHILDREN) == LV_PAINT_HOOK)
        *(unsigned *)((char *)sv + SV_PAINT_CHILDREN) = 0;
}

/* The menu (extras 0) or the Extras page (extras 1) as the saved list says. The stock list_view lays its visible rows
 * out again, in child order (children_layouter_list_view @0x60abbc, set_virtual_h @0x60b20c), whenever the window is
 * marked for relayout (widget_set_visible does that, and the main loop lays out before every paint, @0x6939f4): the
 * first frame after the menu comes back from the lock screen showed the asset's order. So the children are stacked in
 * the order they are shown (hidden rows last, they are skipped), and that layout gives the rows the y and the virtual
 * height set here: any relayout leaves the page as it is. */
void menu_arrange(void *win, int extras) {
    void *sv = widget_lookup(win, "pod_scrollview", 1), *row[POD_MENU_ROWS], *seq[POD_MENU_ROWS];
    unsigned total = extras ? POD_EXTRAS_ROWS : POD_MENU_ROWS, i, pos = 0, k = 0;
    if (!sv) return;
    for (i = 0; i < total; i++) {
        row[i] = mn_find(win, "pod_row", i);
        if (!row[i]) return;   /* not our asset: leave it as it is */
    }
    mn_load();
    if (extras) {   /* the rows the menu does not show, in the fixed Extras order (EX_ORDER); the shown ones hidden, last */
        for (i = 0; i < N; i++) if (!mn_shown(EX_ORDER[i])) { seq[k++] = row[EX_ORDER[i]]; mn_place(row[EX_ORDER[i]], pos++, 1); }
        for (i = 0; i < N; i++) if (mn_shown(EX_ORDER[i])) { seq[k++] = row[EX_ORDER[i]]; mn_place(row[EX_ORDER[i]], 0, 0); }
        for (i = 0; i < k; i++) widget_restack(seq[i], i);
    } else {
        for (i = 0; i < mn.n; i++) { seq[k++] = row[mn.order[i]]; mn_place(row[mn.order[i]], pos++, 1); }
        for (i = N; i < total; i++) { seq[k++] = row[i]; mn_place(row[i], pos++, 1); }   /* Extras, Settings */
        for (i = 0; i < N; i++) if (!mn_shown(i)) { seq[k++] = row[i]; mn_place(row[i], 0, 0); }
        for (i = 0; i < k; i++) widget_restack(seq[i], i);
    }
    mn_plain_paint(sv);
    widget_set_prop_int(sv, "virtual_h", (int)pos * POD_ROW_H);
    widget_set_prop_int(sv, "yoffset", 0);
}

/* ---- the Main Menu page */

static void cm_rebuild(void) {
    unsigned i, k = mn.n;
    for (i = 0; i < mn.n; i++) cm.order[i] = mn.order[i];
    for (i = 0; i < N; i++) if (!mn_shown(i)) cm.order[k++] = (unsigned char)i;
}

/* Arrange the rows from cm.order (the same pass at open and after every change): y, switch image, arrow. Then keep
 * the row of item `focus` (255: none) inside the scroll view's window, and repaint the whole page (a change moves
 * rows under the finger; the dirty rectangles of single widgets are not relied on). */
static void cm_layout(unsigned focus) {
    unsigned pos;
    for (pos = 0; pos < N; pos++) {
        unsigned id = cm.order[pos];
        int on = pos < mn.n;
        widget_move(cm.row[id], 0, (int)pos * POD_ROW_H);
        image_base_set_image(cm.sw[id], on ? "sset_on" : "sset_off");
        widget_set_visible(cm.up[id], on && pos > 0, 0);   /* a picture only: never a touch target */
        widget_set_sensitive(cm.up[id], 0);
    }
    for (pos = 0; pos < N; pos++) widget_restack(cm.row[cm.order[pos]], pos);   /* the children in page order: a relayout keeps it (see menu_arrange) */
    if (cm.sv && focus < N) {
        int vh = widget_get_prop_int(cm.sv, "h", 0), off = widget_get_prop_int(cm.sv, "yoffset", 0), top = 0, max = (int)N * POD_ROW_H - vh;
        for (pos = 0; pos < N; pos++) if (cm.order[pos] == focus) top = (int)pos * POD_ROW_H;
        if (vh > 0) {
            if (top < off) off = top;
            if (top + POD_ROW_H > off + vh) off = top + POD_ROW_H - vh;
            if (off > max) off = max;
            if (off < 0) off = 0;
            widget_set_prop_int(cm.sv, "yoffset", off);
        }
    }
    if (cm.win) widget_invalidate_force(cm.win, (void *)0);
}

/* Keep the change if it saved, else put the list back (and leave the page as it is). */
static void cm_commit(const unsigned char *old, unsigned old_n, unsigned id) {
    unsigned i;
    if (mn_save() != 0) {
        for (i = 0; i < old_n; i++) mn.order[i] = old[i];
        mn.n = old_n;
        return;
    }
    cm_rebuild();
    cm_layout(id);
}

/* One touch target per row. The up arrow is only a picture (insensitive): a stock button would answer the pointer
 * DOWN and UP with RET_OK and the row, a list_item, would be clicked as well (one tap would move the item and
 * toggle it). So the row decides by where the finger went down: inside the arrow's rectangle (the arrow button's x
 * and w in the row, the full 52 px height) the tap moves the item up, anywhere else it shows or hides the item. A
 * row without an arrow (hidden, or first) takes the whole width as a toggle. The pointer event carries screen
 * coordinates; widget_to_local turns them into the row's. */
static int cm_has_arrow(unsigned id) {
    return mn.n > 1 && mn.order[0] != id && mn_shown(id);
}

static int cm_in_zone(unsigned id, void *e) {
    int pt[2], x, w;
    if (!e || !cm_has_arrow(id)) return 0;
    pt[0] = *(int *)((char *)e + PE_X);
    pt[1] = *(int *)((char *)e + PE_Y);
    widget_to_local(cm.row[id], pt);
    x = widget_get_prop_int(cm.up[id], "x", 0);
    w = widget_get_prop_int(cm.up[id], "w", 0);
    return pt[0] >= x && pt[0] < x + w;
}

static void cm_release(void) {   /* the arrow that shows its pressed look goes back to normal */
    if (cm.pressed) widget_set_state(cm.up[cm.pressed - 1], "normal");
    cm.pressed = 0;
}

static void cm_toggle(unsigned id) {
    unsigned i, k = 0;
    unsigned char old[N];
    unsigned old_n = mn.n;
    for (i = 0; i < mn.n; i++) old[i] = mn.order[i];
    if (mn_shown(id)) {
        for (i = 0; i < old_n; i++) if (old[i] != id) mn.order[k++] = old[i];
        mn.n = k;
    } else if (mn.n < N) {
        mn.order[mn.n++] = (unsigned char)id;
    }
    cm_commit(old, old_n, id);
}

static void cm_up(unsigned id) {
    unsigned i, k;
    unsigned char old[N];
    unsigned old_n = mn.n;
    for (i = 0; i < mn.n; i++) old[i] = mn.order[i];
    for (k = 1; k < mn.n; k++) {
        if (mn.order[k] != id) continue;
        mn.order[k] = mn.order[k - 1];
        mn.order[k - 1] = (unsigned char)id;
        cm_commit(old, old_n, id);
        break;
    }
}

/* The row's pointer DOWN, UP and ABORT: remember where this touch began and show the arrow pressed while it is
 * down inside its rectangle. */
static int cm_on_touch(void *ctx, void *e) {
    unsigned id = (unsigned)(long)ctx;
    int type = e ? *(int *)e : 0;
    if (type == EVT_POINTER_DOWN) {
        cm_release();
        cm.down = id + 1;
        cm.zone = cm_in_zone(id, e);
        if (cm.zone) {
            widget_set_state(cm.up[id], "pressed");
            cm.pressed = id + 1;
        }
    } else {
        cm_release();
    }
    return RET_OK;
}

static int cm_on_row(void *ctx, void *e) {
    unsigned id = (unsigned)(long)ctx;
    int zone = cm.down == id + 1 ? cm.zone : cm_in_zone(id, e);
    cm_release();
    cm.down = 0;
    if (zone && cm_has_arrow(id)) cm_up(id);
    else cm_toggle(id);
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
    cm.win = win;
    cm.sv = widget_lookup(win, "pod_scrollview", 1);
    if (cm.sv) mn_plain_paint(cm.sv);
    mn_load();
    cm_rebuild();
    cm_layout(255);
    for (i = 0; i < N; i++) {
        widget_on(cm.row[i], EVT_CLICK, cm_on_row, (void *)(long)i);
        widget_on(cm.row[i], EVT_POINTER_DOWN, cm_on_touch, (void *)(long)i);
        widget_on(cm.row[i], EVT_POINTER_UP, cm_on_touch, (void *)(long)i);
        widget_on(cm.row[i], EVT_POINTER_ABORT, cm_on_touch, (void *)(long)i);
    }
    widget_on(win, EVT_DESTROY, cm_on_destroy, (void *)0);
}
