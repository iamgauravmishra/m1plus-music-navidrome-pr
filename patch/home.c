/* M1 Pod as Home: the boot guard and the launcher. docs/architecture.md has the design and the
 * recovery plan.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE). The crash marker follows q2-pod (Copyright (c)
 * 2026 Diamond Bond, MIT, https://github.com/DiamondBond/q2-pod; see NOTICE).
 *
 * This is the only payload code that runs at start-up. One stock function is hooked for it,
 * home_page_init (0x534cd4, called once through the navigator's page-init dispatcher when the Home
 * window is created). The hook runs the stock function to completion first, then home_boot():
 *
 *   1. state = OFF (stock behaviour) until everything below has succeeded;
 *   2. a kill-switch file (SD or flash) -> stop;
 *   3. the crash marker /mnt/data/m1pod-run exists -> the previous attempt never proved itself:
 *      write the sticky bad note, switch the setting to Shanling, remove the marker (if the note
 *      cannot be written the marker stays, so the next boot is stock too) and stop;
 *   4. the bad note exists -> stop;
 *   5. write the marker (temp file, fsync, rename, directory fsync); any failure -> stop;
 *   6. arm: a one-shot UI timer removes the marker CLEAR_MS later (the boot completed);
 *   7. add the "M1 Pod" icon to the stock grid (whatever the setting says; a failure adds nothing),
 *      register a Home "to foreground" handler (it re-adds the icon if the stock code rebuilt the grid) and,
 *      when the setting says M1 Pod, schedule the first pod-menu open.
 *
 * A Shanling start is armed too (marker, clear timer) because the icon is new code on the boot path; it
 * only opens nothing. Every failure path leaves the stock Home as it was. The kill switch and the setting are checked again before every later open.
 */
#include "offsets.inc"
#include "stock.h"
#include "home.h"

#define F_OK 0
#define O_RDONLY 0
#define O_WRONLY 1
#define O_APPEND 0x8      /* MIPS Linux */
#define O_CREAT 0x100
#define O_TRUNC 0x200
#define EVT_WINDOW_FG 0x12d /* EVT_WINDOW_TO_FOREGROUND: window_manager_dispatch_window_event(.., 0x12d) @0x692a44 */

enum { H_NEW = 0, H_OFF, H_ARMED, H_PROVEN };

static struct {
    int state;
    int start;        /* the setting: 1 = start in M1 Pod */
    int grid;         /* the user chose the stock grid for this session */
    int pending;      /* an open timer is scheduled */
    void *entry;      /* the entry menu window (the Settings page opens over it) */
    int tries;
    int as_home;      /* the menu being opened is the Home instance: its Back is hidden */
    void *home;       /* the stock Home window */
    void *menu;       /* the menu window the toggle row lives in */
    const char *startup_row;
} hs __attribute__((section(".scratch")));

static int hm_exists(const char *p) { return access(p, F_OK) == 0; }

static unsigned hm_len(const char *s) { unsigned n = 0; while (s[n]) n++; return n; }

static void hm_sync_dir(void) {
    int fd = open(DATA_DIR, O_RDONLY, 0);
    if (fd >= 0) { fsync(fd); close(fd); }
}

/* Temp file, fsync, rename onto the target, fsync of the directory. 0 on success. */
static int hm_write_atomic(const char *path, const char *tmp, const char *data) {
    unsigned n = hm_len(data);
    int fd = open(tmp, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    int ok;
    if (fd < 0) return -1;
    ok = write(fd, data, n) == (int)n && fsync(fd) == 0;
    ok = (close(fd) == 0) && ok;
    if (!ok || rename(tmp, path) != 0) { unlink(tmp); return -1; }
    hm_sync_dir();
    return 0;
}

/* Opt-in log on the SD card: only when /mnt/mmc/m1pod-log exists. Best effort. */
static void hm_log(const char *s) {
    int fd;
    if (!hm_exists(LOG_ENABLE)) return;
    fd = open(LOG_FILE, O_WRONLY | O_APPEND | O_CREAT, 0644);
    if (fd < 0) return;
    write(fd, s, hm_len(s));
    write(fd, "\n", 1);
    close(fd);
}

int home_off(void) { return hm_exists(KILL_SD) || hm_exists(KILL_DATA); }

static void hm_clear_marker(void) {
    unlink(MARKER);
    hm_sync_dir();
}

/* A marker at boot: the last attempt never proved itself. Record it (the bad note is sticky: no
 * later boot arms again until the user re-enables M1 Pod) and fall back to Shanling. If the note
 * cannot be written the marker stays, so every following boot is stock as well. */
static void hm_record_failure(void) {
    if (hm_write_atomic(BAD_NOTE, BAD_TMP, "1\n") != 0) return;
    hm_write_atomic(START_FILE, START_TMP, "0\n");
    hm_clear_marker();
    hm_log("m1pod: marker found; falling back to Shanling");
}

/* The boot completed: remove the marker (UI thread, CLEAR_MS after the hook). */
static int hm_clear(const void *unused) {
    (void)unused;
    if (hs.state == H_ARMED) {
        hm_clear_marker();
        hs.state = H_PROVEN;
        hm_log("m1pod: boot ok, marker cleared");
    }
    return RET_OK;
}

static int hm_read_start(void) {   /* the setting; anything but "0", or no file, is M1 Pod */
    char c = 0;
    int fd = open(START_FILE, O_RDONLY, 0), n;
    if (fd < 0) return 1;
    n = read(fd, &c, 1);
    close(fd);
    return !(n == 1 && c == '0');
}

static void hm_arm(void) {
    hs.state = H_OFF;
    hs.start = 1;
    hs.start = hm_read_start() && !hm_exists(BAD_NOTE);   /* what the menu shows, whatever happens below */
    if (home_off()) { hm_log("m1pod: kill switch"); return; }
    if (hm_exists(MARKER)) { hm_record_failure(); return; }
    if (hm_exists(BAD_NOTE)) { hm_log("m1pod: an earlier boot failed; stock until re-enabled"); return; }
    if (!hs.start) hm_log("m1pod: starting in Shanling");
    if (hm_write_atomic(MARKER, MARKER_TMP, "1\n") != 0) return;
    if (!timer_add(hm_clear, (void *)0, CLEAR_MS)) { hm_clear_marker(); return; }
    hs.state = H_ARMED;
    hm_log("m1pod: armed");
}

static int hm_ready(void) { return hs.state == H_ARMED || hs.state == H_PROVEN; }
static void hm_grid(int show);
static void hm_add_icon(void *win);

/* Open the pod menu as Home when the stock Home is the topmost normal window and opened; wait a
 * little if it is not up yet; give up if anything else is on top (that window's Back or the go-home
 * path brings Home to the foreground again, which schedules this again). */
static int hm_open(const void *unused) {
    void *wm, *top;
    (void)unused;
    hs.pending = 0;
    if (!hm_ready() || hs.grid || !hs.start || !hs.home) return RET_OK;
    if (home_off()) { hm_grid(1); return RET_OK; }
    wm = window_manager();
    top = wm ? window_manager_get_top_main_window(wm) : (void *)0;
    if (!top) { hm_grid(1); return RET_OK; }
    if (top != hs.home) return RET_OK;   /* that window's close brings Home to the foreground again */
    if (!widget_is_window_opened(hs.home)) {
        if (++hs.tries < MAX_TRIES && timer_add(hm_open, (void *)0, RETRY_MS)) hs.pending = 1;
        else hm_grid(1);                  /* never opened: show the stock grid */
        return RET_OK;
    }
    hs.as_home = 1;
    if (m1pod_open_entry() != 0) { hs.as_home = 0; hm_grid(1); }
    return RET_OK;
}

static void hm_schedule(unsigned ms) {
    if (hs.pending || hs.grid || !hs.start || !hm_ready() || home_off()) return;
    hs.tries = 0;
    if (timer_add(hm_open, (void *)0, ms)) hs.pending = 1;
}

/* Home came to the foreground again: a window above it closed (Back, go-home, USB, lock screen, ..). */
static int hm_fg(void *ctx, void *e) {
    (void)e;
    if (!home_off() && !widget_lookup(ctx, POD_ENTRY_NAME, 1)) hm_add_icon(ctx);   /* the stock code rebuilt the grid (Home customisation) */
    hm_schedule(OPEN_MS);
    return RET_OK;
}

/* The stock grid's content (gesture > icon pages + the bottom strip) is hidden while M1 Pod is Home, so
 * the window under the menu is plain black and the grid never flashes (V2.1jA, docs/ui.md). Hidden and
 * insensitive; the widgets stay (stock looks them up by name). */
static void hm_grid(int show) {
    void *g = hs.home ? widget_lookup(hs.home, GRID_ROOT, 1) : (void *)0;
    if (!g) return;
    widget_set_visible(g, show, 0);
    widget_set_sensitive(g, show);
}

/* The "M1 Pod" icon on the stock grid: a clone of what the stock icon builder (0x533d8c) makes per icon, in
 * the same calls and order: a 154x118 view in the page, the 66x66 clickable image named by its id with
 * the style home_m1pod_style (tools/mod_icons.py: the click-wheel disc, its _down) and the stock click
 * handler 0x533b80 with the image as ctx (m1pod_home_click maps the id to the pod menu), and the centred
 * white label. Returns the cell or 0; a partial cell is destroyed again. */
static void *hm_icon_cell(void *page, unsigned slot) {
    void *cell = view_create(page, (int)(ICON_X0 + (slot & 1) * ICON_W), (int)((slot >> 1) * ICON_H), ICON_W, ICON_H);
    void *img = cell ? image_create(cell, ICON_IMG_X, ICON_IMG_Y, ICON_IMG, ICON_IMG) : (void *)0;
    void *label = img ? label_create(cell, 0, ICON_LABEL_Y, ICON_W, ICON_LABEL_H) : (void *)0;
    if (!label) { if (cell) widget_destroy(cell); return (void *)0; }
    widget_set_prop_bool(img, "clickable", 1);
    widget_use_style(img, "home_m1pod_style");
    widget_set_name(img, POD_ENTRY_NAME);
    widget_on(img, EVT_CLICK, (void *)STOCK_HOME_CLICK, img);
    widget_use_style(label, "label_centerwhitehome_white");
    label_set_line_wrap(label, 1);
    widget_set_text_utf8(label, "M1 Pod");
    return cell;
}

static int hm_is(void *w, const char *type) {
    const char *t = w ? widget_get_type(w) : (const char *)0;
    return t && strcmp(t, type) == 0;
}

/* Put the icon in the first free slot: the last page's, or a new page (the page builder makes as many as
 * the icon list needs) when that one is full. Anything unexpected in the tree or a failed create: no icon. */
static void hm_add_icon(void *win) {
    void *sv = win ? widget_lookup(win, "home_sview", 1) : (void *)0, *page, *ind;
    unsigned pages, n;
    if (!hm_is(sv, "slide_view")) return;
    pages = widget_count_children(sv);
    if (pages == 0 || pages > 8) return;
    page = widget_get_child(sv, pages - 1);
    if (!hm_is(page, "view")) return;
    n = widget_count_children(page);
    if (n < ICONS_PER_PAGE) { hm_icon_cell(page, n); return; }
    if (n > ICONS_PER_PAGE) return;
    page = view_create(sv, 0, 0, PAGE_W, PAGE_H);
    if (!page) return;
    if (!hm_icon_cell(page, 0)) { widget_destroy(page); return; }
    ind = widget_lookup(win, "home_sindicator", 1);
    if (ind) slide_indicator_set_max(ind, pages + 1);
}

/* The Home instance of the menu has no top bar: the navbar view is hidden (hidden and insensitive; a hidden
 * widget still takes touches) and the stock list moves up to fill the 450 px window
 * less HOME_PAD above and below (the first row starts a little below the status bar and the last one ends above the screen edge). The stock list_view's
 * children keep their widths (scroll_view and its bar); only the heights follow. Nothing is touched unless the
 * navbar and the list are both found. */
static void hm_fill_window(void *win) {
    void *nb = widget_lookup(win, "navigationbar_view", 1), *lv = widget_lookup(win, "pod_listview", 1);
    static const char *const kids[] = {"pod_scrollview", "scroll_bar_m"};
    unsigned i;
    if (!nb || !lv) return;
    widget_set_visible(nb, 0, 0);
    widget_set_sensitive(nb, 0);
    widget_move(lv, 0, HOME_PAD);
    widget_resize(lv, SCREEN_W, WIN_H - 2 * HOME_PAD);
    for (i = 0; i < 2; i++) {
        void *c = widget_lookup(win, kids[i], 1);
        int w = c ? widget_get_prop_int(c, "w", 0) : 0;
        if (w > 0) widget_resize(c, w, WIN_H - 2 * HOME_PAD);
    }
}

/* The row's text label is the hscroll_label child, not child 0: the icon image sits in the row too, and
 * widget_set_text on the image drew a second, ghost "Start in: ..." over the icon (V2.1iM on the device). */
static void hm_set_label(void) {
    void *row, *c, *label = (void *)0;
    const char *t;
    unsigned i, n;
    if (!hs.menu || !hs.startup_row) return;
    row = widget_lookup(hs.menu, hs.startup_row, 1);
    n = row ? widget_count_children(row) : 0;
    for (i = 0; i < n && i < 8 && !label; i++) {
        c = widget_get_child(row, i);
        t = c ? widget_get_type(c) : (const char *)0;
        if (t && t[0] == 'h' && t[1] == 's') label = c;   /* "hscroll_label" */
    }
    if (label) widget_set_text_utf8(label, hs.start ? "Start in: M1 Pod" : "Start in: Shanling");
}

/* Called by m1pod.c for the entry page (entry = 1) and for the page holding the Start-in row: remember the
 * windows and show the setting; the entry page as the Home instance loses its navbar (the Now Playing row
 * replaces the bars icon; the Settings > Shanling Home row is the way out). */
void home_menu_opened(void *win, const char *startup_row, int entry) {
    if (entry) {
        hs.entry = win;
        if (hs.as_home) {
            hm_fill_window(win);
            hm_grid(0);
            hs.as_home = 0;
        }
    }
    if (startup_row) {
        hs.menu = win;
        hs.startup_row = startup_row;
        hm_set_label();
    }
}

/* The M1 Pod icon was tapped on the stock grid. After "Shanling Home" (grid flag set, setting M1 Pod) it
 * restores M1 Pod as Home for the session: the menu opens as the Home instance. Returns 1 if so. */
int home_restore(void) {
    if (!hs.grid || !hs.home || !hs.start || !hm_ready() || home_off()) return 0;
    hs.grid = 0;
    hs.as_home = 1;
    return 1;
}

/* The restoring open failed (m1pod.c): back to the grid state it was in. */
void home_restore_failed(int restored) {
    if (!restored) return;
    hs.as_home = 0;
    hs.grid = 1;
}

/* "Shanling Home" (on the Settings page): show the stock grid, keep it for this session, and close the
 * pages above Home: the menu under the Settings page first (by handle: a second back right after the first
 * would find the closing page), then the Settings page itself. */
int home_to_grid(void) {
    hs.grid = 1;
    hm_grid(1);
    if (hs.entry && hs.menu && hs.entry != hs.menu) window_close(hs.entry);
    hs.entry = (void *)0;
    navigator_back();
    return RET_OK;
}

/* "Start in": flip the persistent setting (takes effect at the next start). */
int home_toggle(void) {
    int next = !hs.start;
    if (hm_write_atomic(START_FILE, START_TMP, next ? "1\n" : "0\n") != 0) return RET_OK;
    hs.start = next;
    if (next) unlink(BAD_NOTE);
    hm_set_label();
    return RET_OK;
}

void home_boot(void *win) {
    if (hs.state == H_NEW) hm_arm();
    if (hm_ready()) {
        hs.home = win;
        hm_add_icon(win);                /* after the marker, in the guard's path; a failure adds nothing */
        widget_on(win, EVT_WINDOW_FG, hm_fg, win);
        if (hs.start) {
            hm_grid(0);                  /* no grid flash behind the menu */
            hm_schedule(OPEN_FIRST_MS);
        }
    }
}

/* Installed over home_page_init's PIC prologue (tools/pod.py HOME_INIT). */
int m1pod_home_init(void *win, void *ctx) {
    int r = stock_home_init_trampoline(win, ctx);
    if (r == RET_OK && win) home_boot(win);   /* a stock init that failed leaves everything stock */
    return r;
}
