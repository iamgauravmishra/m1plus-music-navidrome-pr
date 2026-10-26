/* M1 Pod as Home: the crash guard and the launcher toggle (patch/home.c, docs/architecture.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE). The crash marker follows q2-pod's
 * (Copyright (c) 2026 Diamond Bond, MIT, https://github.com/DiamondBond/q2-pod; see NOTICE): a file
 * written and fsynced before a risky first step and removed after the step has proven itself.
 */
#pragma once

/* Files in /mnt/data (writable flash) and on the SD card. All of them are plain files the payload
 * checks with access() or reads with open(); none is parsed by stock code. */
#define KILL_SD "/mnt/mmc/m1pod-off"        /* the long-standing kill switch (SD, may be unmounted at boot) */
#define KILL_DATA "/mnt/data/m1pod-off"     /* the same, in flash (stages with the guard) */
#define MARKER "/mnt/data/m1pod-run"        /* exists from "boot attempt armed" until it has proven itself */
#define MARKER_TMP "/mnt/data/m1pod-run.tmp"
#define BAD_NOTE "/mnt/data/m1pod-bad"      /* written when a marker was found at boot */
#define BAD_TMP "/mnt/data/m1pod-bad.tmp"
#define START_FILE "/mnt/data/m1pod-start"  /* "1" = start in M1 Pod (default when missing), "0" = Shanling */
#define START_TMP "/mnt/data/m1pod-start.tmp"
#define ALBUMS_FILE "/mnt/data/m1pod-albums" /* "1" = the Albums grid (default when missing, ALBUMS_DEFAULT_GRID), "0" = the list mode of the same page */
#define ALBUMS_TMP "/mnt/data/m1pod-albums.tmp"
#define LANDSCAPE_FILE "/mnt/data/m1pod-landscape" /* "1" = Cover Flow opens in landscape, anything else portrait (the default) */
#define LANDSCAPE_TMP "/mnt/data/m1pod-landscape.tmp"
#define CFSORT_FILE "/mnt/data/m1pod-cfsort" /* the album order of Cover Flow and Albums: "0" or "0\n" = by album title (stock), anything else or missing = Artist (the default) */
#define CFSORT_TMP "/mnt/data/m1pod-cfsort.tmp"
#define MENU_FILE "/mnt/data/m1pod-menu"  /* the menu's visible items in order, one digit (item id) each (patch/menu.c); missing or invalid = the defaults */
#define MENU_TMP "/mnt/data/m1pod-menu.tmp"
#define DATA_DIR "/mnt/data"
#define LOG_ENABLE "/mnt/mmc/m1pod-log"     /* opt-in: an empty file on the card turns the log on */
#define LOG_FILE "/mnt/mmc/m1pod.log"

#define CLEAR_MS 5000       /* the marker is removed this long after the hook ran */
#define OPEN_FIRST_MS 10    /* the first pod-menu open (1200 before) */
#define OPEN_MS 10          /* later opens, after a window above Home closed (250 before) */
#define RETRY_MS 50         /* Home not opened yet: ask again (250 before) */
#define MAX_TRIES 100       /* 5 s, as 20 x 250 ms before */
#define GRID_ROOT "app_gesture"   /* the stock Home grid's content container (home_page.bin) */
#define EVT_WINDOW_FG 0x12d       /* EVT_WINDOW_TO_FOREGROUND: window_manager_dispatch_window_event(.., 0x12d) @0x692a44 */

/* The hook (tools/pod.py HOME_INIT): installed over home_page_init; runs the stock function first. */
extern int m1pod_home_init(void *win, void *ctx);
extern int stock_home_init_trampoline(void *win, void *ctx);

/* patch/home.c */
extern void home_boot(void *win);
extern int home_off(void);
extern int home_write_atomic(const char *path, const char *tmp, const char *data); /* temp, fsync, rename, directory fsync; 0 = done */
extern void home_menu_opened(void *win, int settings, int entry);
extern int home_to_grid(void);
extern int home_start(void);   /* the "Start in M1 Pod" setting as the Settings page shows it */
extern int home_toggle(void);  /* flip it; the new state, or -1 when it could not be saved */
extern int home_restore(void);
extern void home_restore_failed(int restored);

/* patch/m1pod.c (stages with the home feature) */
extern int m1pod_open_entry(void);
