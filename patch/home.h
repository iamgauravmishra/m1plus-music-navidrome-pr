/* M1+ Music as Home: the crash guard and the launcher toggle (patch/home.c, docs/architecture.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE). The crash marker follows q2-pod's
 * (Copyright (c) 2026 Diamond Bond, MIT, https://github.com/DiamondBond/q2-pod; see NOTICE): a file
 * written and fsynced before a risky first step and removed after the step has proven itself.
 */
#pragma once
#include "covercache.h"   /* CARD_DIR */

/* Files in /mnt/data (writable flash) and on the SD card. All of them are plain files the payload
 * checks with access() or reads with open(); none is parsed by stock code. */
#define KILL_SD "/mnt/mmc/m1plus-off"        /* the long-standing kill switch (SD, may be unmounted at boot) */
#define KILL_DATA "/mnt/data/m1plus-off"     /* the same, in flash (stages with the guard) */
#define MB_BLUR_OFF "/mnt/mmc/m1plus-noblur" /* the mini player bar's backdrop blur (patch/minibar.c, experimental) is off while this exists on the card */
#define MARKER "/mnt/data/m1plus-run"       /* exists from "boot attempt armed" until it has proven itself */
#define MARKER_TMP "/mnt/data/m1plus-run.tmp"
#define BAD_NOTE "/mnt/data/m1plus-bad"      /* written when a marker was found at boot */
#define BAD_TMP "/mnt/data/m1plus-bad.tmp"
#define START_FILE "/mnt/data/m1plus-start"  /* "1" = start in M1+ Music (default when missing), "0" = Shanling */
#define START_TMP "/mnt/data/m1plus-start.tmp"
#define ALBUMS_FILE "/mnt/data/m1plus-albums" /* "1" = the Albums grid (default when missing, ALBUMS_DEFAULT_GRID), "0" = the list mode of the same page */
#define ALBUMS_TMP "/mnt/data/m1plus-albums.tmp"
#define PLAYLISTS_FILE "/mnt/data/m1plus-playlists" /* the Playlists page's mode, as ALBUMS_FILE: "1" the grid (default), "0" the list */
#define PLAYLISTS_TMP "/mnt/data/m1plus-playlists.tmp"
#define LANDSCAPE_FILE "/mnt/data/m1plus-landscape" /* "1" = Cover Flow opens in landscape, anything else portrait (the default) */
#define LANDSCAPE_TMP "/mnt/data/m1plus-landscape.tmp"
#define CFSORT_FILE "/mnt/data/m1plus-cfsort" /* the album order of Cover Flow and Albums: "0" or "0\n" = by album title (stock), anything else or missing = Artist (the default) */
#define CFSORT_TMP "/mnt/data/m1plus-cfsort.tmp"
#define MENU_FILE "/mnt/data/m1plus-menu"  /* the menu's visible items in order, one digit (item id) each (patch/menu.c); missing or invalid = the defaults */
#define MENU_TMP "/mnt/data/m1plus-menu.tmp"
#define RECENT_FILE "/mnt/data/m1plus-recent" /* the albums played last, most recent first (patch/recent.c); missing or malformed = none */
#define RECENT_TMP "/mnt/data/m1plus-recent.tmp"
#define SHELF_FILE "/mnt/data/m1plus-shelf"   /* the Recently Played shelf: "0" = off, anything else or missing = on (Customize > Home Screen) */
#define SHELF_TMP "/mnt/data/m1plus-shelf.tmp"
#define DAILY_SET_FILE "/mnt/data/m1plus-daily"  /* the Daily Mix card: "0" = off, anything else or missing = on (Customize > Home Screen) */
#define DAILY_SET_TMP "/mnt/data/m1plus-daily.tmp"
#define MIX_DIR CARD_DIR "/daily-mix"          /* the Daily Mix's own folder inside the card folder (CARD_DIR, patch/covercache.h); made by the writer */
#define MIX_FILE MIX_DIR "/tracks"             /* the card's Daily Mix: day, seed, tones, names, the songs' card paths (patch/dailymix.c; tools/pod_mix.py is the model) */
#define MIX_TMP MIX_DIR "/tracks.tmp"
#define MIX_ART_FILE MIX_DIR "/art"            /* its card art, 296 x 220 RGB565 with a checksummed header */
#define MIX_ART_TMP MIX_DIR "/art.tmp"
#define DATA_DIR "/mnt/data"
#define LOG_ENABLE "/mnt/mmc/m1plus-log"     /* opt-in: an empty file on the card turns the log on */
#define LOG_FILE "/mnt/mmc/m1plus.log"

#define CLEAR_MS 5000       /* the marker is removed this long after the hook ran */
#define OPEN_FIRST_MS 10    /* the first pod-menu open (1200 before) */
#define OPEN_MS 10          /* later opens, after a window above Home closed (250 before) */
#define RETRY_MS 50         /* Home not opened yet: ask again (250 before) */
#define MAX_TRIES 100       /* 5 s, as 20 x 250 ms before */
#define GRID_ROOT "app_gesture"   /* the stock Home grid's content container (home_page.bin) */

/* The hook (tools/pod.py HOME_INIT): installed over home_page_init; runs the stock function first. */
extern int m1plus_home_init(void *win, void *ctx);
extern int stock_home_init_trampoline(void *win, void *ctx);

/* patch/home.c */
extern void home_boot(void *win);
extern int home_off(void);
extern int home_write_atomic(const char *path, const char *tmp, const char *data); /* temp, fsync, rename, directory fsync; 0 = done */
extern void home_menu_opened(void *win, int settings, int entry);
extern void home_extras_opened(void *win);   /* the Extras page: Customize may be opened from it, Shanling Home closes it too */
extern int home_to_grid(void);
extern int home_start(void);   /* the "Boot to M1+ Music" setting as Customize > Home Screen shows it */
extern int home_toggle(void);  /* flip it; the new state, or -1 when it could not be saved */
extern int home_restore(void);
extern void home_restore_failed(int restored);

/* patch/minibar.c: the mini player bar of the Home instance of the menu (called by home_menu_opened) */
extern void minibar_start(void *win);

/* patch/recent.c: the Recently Played shelf of the Home instance of the menu (recent_start, called by home_menu_opened) and the albums it shows */
extern void recent_start(void *win);
extern int recent_note(void *track);     /* the track the player is on: record its album; 1 when the list changed (cheap when it did not) */
extern void recent_refresh(void);       /* the list changed under a live shelf (the mini bar's tick): show it */
extern int recent_setting(void);         /* the Customize > Home Screen switch: 1 on (the default) */
extern void menu_shelf(void *win, int on);   /* patch/menu.c: show or hide the shelf and move the rows (the list keeps its place) */
extern void menu_daily(void *win, int on);   /* patch/menu.c: the same for the Daily Mix section, which sits above the shelf */

/* patch/dailymix.c: the Daily Mix card of the Home instance of the menu (dailymix_start, called by home_menu_opened) and its Customize > Home Screen rows */
extern void dailymix_start(void *win);
extern int dailymix_setting(void);       /* the Customize > Home Screen switch: 1 on (the default) */
extern int dailymix_toggle(void);        /* flip it, saved atomically; the new state, or -1 when it could not be saved */
extern void dailymix_regen(void);        /* Regenerate Daily Mix: today's mix is made again with a new seed, when the Home menu is in front */
extern int dailymix_can_regen(void);     /* Regenerate can make a mix: the switch is on and the last job did not find the library too small */
extern int recent_toggle(void);         /* flip it, saved atomically; the new state, or -1 when it could not be saved */

/* patch/m1plus.c (stages with the home feature) */
extern int m1plus_open_entry(void);
