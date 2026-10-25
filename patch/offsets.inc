/* Stock M1 Plus V2.1 layout and ABI constants shared by patch/m1pod.c and test/patch.py.
 * The test harness parses the #defines in this file, so a change cannot leave the mocks behind.
 * Structure follows q2-pod's patch/offsets.inc (Copyright (c) 2026 Diamond Bond, MIT); the values
 * are the M1 Plus's own, read from demo with tools/dis.py. */
#define W_NAME 0x10       /* widget_t name; the Home dispatcher reads only this: lw $a0, 0x10($a0) @0x533ba4 */
#define EVT_CLICK 0x10c   /* Home icons register their click with this type: widget_on @0x533f78 */
#define RET_OK 0
#define HOME_IDS 18       /* the Home dispatcher's jump table covers 0..17: sltiu $v1, $v0, 0x12 @0x533ba8 */
/* Home item ids (config.ini [MAIN] HOMEMENU; names from the table at 0x97c940, get_homemenu_showinfo).
 * Which ids reach Home is decided by reset_homemenu_index/load_home_menu: id 0 only when the
 * `language` global (0xa05ab8) is 0 (Simplified Chinese); every other id comes from the saved
 * HOMEMENU list, which the user can edit in the Home customisation dialog. See docs/payload.md. */
#define HOME_HIFIMUSIC 0   /* hifi/hifimusic_page, or "no network"; Simplified Chinese only */
#define HOME_TIDAL 1       /* tidal/tidal_main, or "no network"; the M1 Pod entry icon */
#define HOME_UPDATEMUSIC 2 /* systemset/updatemusic_page */
#define HOME_MYMUSIC 3     /* allmusic_page, context 0xf001: all songs */
#define HOME_FOLDER 4      /* folder_page */
#define HOME_ALBUM 5       /* album_page, context {0xf003, 0} */
#define HOME_SONGER 6      /* localclass_page, 0xf004: artists */
#define HOME_GENRE 7       /* localclass_page, 0xf006 */
#define HOME_COMPOSER 8    /* localclass_page, 0xf005 */
#define HOME_HR 9          /* allmusic_page, 0xf002: hi-res */
#define HOME_FAV 10        /* allmusic_page, 0xf00a: favourites */
#define HOME_MANY 11       /* allmusic_page, 0xf008: most played */
#define HOME_RECENT 12     /* allmusic_page, 0xf007: recently played */
#define HOME_RECENTADD 13  /* allmusic_page, 0xf009: recently added */
#define HOME_PLAYLIST 14   /* playlist_page */
#define HOME_CDRIPPER 15   /* cdripper_page (sets GPIO PA11 first) */
#define HOME_PLAYSET 16    /* playset/playset_page */
#define HOME_SYSSET 17     /* systemset/sysset_page */

/* ---------------------------------------------------------------------------
 * Cover Flow (patch/coverflow.c). Event ids, record layout and widget fields
 * read from this demo with tools/dis.py; the geometry is this project's own
 * (320x480 portrait), the depth model follows q2-pod (docs/coverflow.md).
 */
#define EVT_DESTROY 0x0c        /* widget_destroy_sync: event_init(e, 0xc) @0x670600 */
#define EVT_AFTER_PAINT 0x120   /* widget_paint dispatches it after children+border @0x66de3c */
#define EVT_VALUE_CHANGED 0x11c /* slide_menu commit dispatches 0x11b then 0x11c @0x61213c */

/* stSongInfo record fields (getAllAlbum's row callback @0x4e93c8, loadSongList @0x4e2ce0) */
#define REC_ID 0x00        /* -1 = the "Unknown Album" row getAllAlbum appends */
#define REC_NAME 0x08      /* file name; loadSongList matches a track by it */
#define REC_PATH 0x0c      /* fileurl: for an album row, its first track */
#define REC_TITLE 0x10     /* tag title (album rows carry the album name here too) */
#define REC_ALBUM 0x14
#define REC_ARTIST 0x18
#define REC_TYPE 0x34      /* 8 song, 4 directory/class row */
#define REC_CUE_START 0x48 /* loadSongList's third argument */

/* Stock library/browsing state (all pinned in tools/pod.py DATA) */
#define CLASS_ALBUMS 0xf003   /* loadLocalClassList: getAllAlbum into *pdeq_showlist */
#define CLASS_ALBUM_TRACKS 0xff10 /* what loadAlbumdetailList(0xf003, row) leaves in classinfo[0] */
#define PLAY_MODE 2           /* playing_page context mode, as album_page/albuminfo_page pass */

/* Cover Flow geometry, 320x480 portrait: a CF_VIEW_W x CF_VIEW_H frame under the 50 px navbar.
 * The centre cover is ART_SIZE square with its top CF_TOP below the frame's; side covers turn
 * 60 degrees inward (the sine table in coverflow.c), sit CF_X1 px from the centre and then CF_XS
 * apart, CF_Z1 and then CF_ZS px further back, seen from CF_EYE px. Brightness (of 256) is 256 at
 * the centre, CF_BRIGHT1 one out, CF_BRIGHT2 two out, 0 three out. Each cover reflects CF_REFLECT
 * px at native size from CF_REFLECT_TOP (of 256) of its brightness down to black. */
#define ART_SIZE 140
#define CF_VIEW_W 320
#define CF_VIEW_H 230
#define CF_CX 160          /* the centre line, between columns 159 and 160 */
#define CF_TOP 26
#define CF_EYE 260
#define CF_X1 92
#define CF_XS 40
#define CF_Z1 80
#define CF_ZS 18
#define CF_BRIGHT1 192
#define CF_BRIGHT2 128
#define CF_REFLECT 22
#define CF_REFLECT_TOP 64
#define FNV_SEED 2166136261u

/* AWTK ABI used by the Cover Flow renderer (all read from this demo) */
#define EVENT_PAINT_CANVAS 0x18 /* paint_event_t.canvas: paint_event_init stores a3 there @0x65026c */
#define BITMAP_FLAGS 0x0c       /* bitmap_t: w@0, h@4, flags u16@0xc, format u16@0xe, data@0x14 */
#define BITMAP_FORMAT 0x0e      /*   (bitmap_create_ex @0x6400d4: sw w,0; sw h,4; sh fmt,0xe) */
#define BITMAP_RGBA8888 1       /* bitmap_format_t: 1 RGBA8888, 2 ABGR, 3 BGRA, 4 ARGB */
#define BITMAP_RGBA_AT { { 0, 1, 2, 3 }, { 3, 2, 1, 0 }, { 2, 1, 0, 3 }, { 1, 2, 3, 0 } }
#define IMAGE_SCALE_AUTO 4      /* image_draw_type_t, as the stock cover rows use */

/* Cover Flow page geometry (the ui/m1pod_cover.bin asset must match; tools/pod_ui.py) */
#define SCREEN_W 320
#define TRACKS_H 400            /* the track list fills the window under the 50 px navbar: windows are 450 px tall under the 30 px system_bar */
