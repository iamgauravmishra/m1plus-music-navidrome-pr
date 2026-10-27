/* Screenshot (patch/shot.c, docs/architecture.md "Screenshot"): constants the payload and test/pod/shot.py share.
 * The test parses the #defines in this file, so a change cannot leave the mocks behind.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#pragma once

#define SHOT_DIR "/mnt/mmc/screenshots"
#define SHOT_TMP "/mnt/mmc/screenshots/shot.tmp"     /* written and fsynced, then renamed to shot-NNNN.bmp */
#define SHOT_CARD "/mnt/mmc"                         /* the card's mount point: a mounted card is another file system than its parent */
#define SHOT_PARENT "/mnt"
#define SHOT_FB "/dev/fb0"                           /* the node stock opens in lcd_linux_fb_create @0x6393dc */
#define SHOT_SECONDS 5                               /* the countdown, one stock timer tick (1000 ms) each */
#define SHOT_TICK_MS 1000
#define SHOT_SETTLE_MS 120                           /* after the indicator is hidden: a few frames for the main loop to repaint before the grab */
#define SHOT_MAX_NUM 9999                            /* shot-0001.bmp .. shot-9999.bmp; the scan is bounded */
#define SHOT_MIN_FREE_MB 16                          /* as Cover Flow's cache: never fill the card */
#define SHOT_MAX_DIM 1024                            /* a frame buffer larger than this either way is not the panel */
#define SHOT_IND "pod_shot"                          /* the hidden status bar image tools/pod_ui.py adds to the system bar's right group */

/* linux/fb.h (32 bit): FBIOGET_VSCREENINFO / FBIOGET_FSCREENINFO and the word indexes of the fields read */
#define FBIOGET_VSCREENINFO 0x4600
#define FBIOGET_FSCREENINFO 0x4602
#define FBV_WORDS 40        /* sizeof(struct fb_var_screeninfo) = 160 */
#define FBF_WORDS 17        /* sizeof(struct fb_fix_screeninfo) = 68 */
#define FBV_XRES 0
#define FBV_YRES 1
#define FBV_YRES_VIRTUAL 3
#define FBV_YOFFSET 5       /* the visible buffer: FBIOPAN_DISPLAY (double buffering) moves it */
#define FBV_BPP 6
#define FBV_RED 8           /* offset, length, msb_right */
#define FBV_GREEN 11
#define FBV_BLUE 14
#define FBF_SMEM_LEN 5
#define FBF_LINE_LENGTH 11
