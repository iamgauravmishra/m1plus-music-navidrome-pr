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
 * HOMEMENU list, which the user can edit in the Home customisation dialog. See docs/architecture.md. */
/* 0 hifi/hifimusic_page (Simplified Chinese only)   1 tidal/tidal_main        2 systemset/updatemusic_page
 * 3 allmusic_page 0xf001: all songs                  4 folder_page            5 album_page, context {0xf003, 0}
 * 6 localclass_page 0xf004: artists                  7 localclass_page 0xf006: genres   8 0xf005: composers
 * 9 allmusic_page 0xf002: hi-res   10 0xf00a: favourites   11 0xf008: most played   12 0xf007: recently played
 * 13 0xf009: recently added        14 playlist_page   15 cdripper_page (sets GPIO PA11 first)
 * 16 playset/playset_page          17 systemset/sysset_page.  The ids tools/pod_pages.py uses are the same. */
#define HOME_ALBUM 5

/* The Home grid, as the stock page builder 0x534064 / icon builder 0x533d8c lay it out (patch/home.c adds one
 * icon the same way): a slide_view "home_sview" of 320x364 page views, six icons each in two columns and three
 * rows; an icon is a 154x118 view holding a 66x66 clickable image (named by the decimal id, EVT_CLICK ->
 * 0x533b80 with the image as ctx, style home_<name>_style) and a 154x36 label at y 92. */
#define ICONS_PER_PAGE 6    /* the icon builder's loop: slt/bne on 6 @0x5340/0x53401c */
#define ICON_W 154          /* view_create(.., 0x9a, 0x76) @0x533e18 */
#define ICON_H 118
#define ICON_X0 6           /* column 0; column 1 is ICON_X0 + ICON_W (0x9a added @0x534010) */
#define ICON_IMG_X 44       /* image_create(cell, 0x2c, 0x14, 0x42, 0x42) @0x533e88 */
#define ICON_IMG_Y 20
#define ICON_IMG 66
#define ICON_LABEL_Y 92     /* label_create(cell, 0, 0x5c, 0x9a, 0x24) @0x533f8c */
#define ICON_LABEL_H 36
#define PAGE_W 320          /* view_create(sview, 0, 0, 0x140, 0x16c) @0x534168 */
#define PAGE_H 364
/* the pod menu as the Home instance (no navbar): the list takes the whole 450 px window */
#define SCREEN_W 320
#define WIN_H 450
#define HOME_PAD 10        /* the Home instance of the pod menu keeps this much air above its first row and below its last (patch/home.c hm_fill_window) */

/* ---------------------------------------------------------------------------
 * Cover Flow (patch/coverflow.c). Event ids, record layout and widget fields
 * read from this demo with tools/dis.py; the geometry is this project's own
 * (320x480 portrait), the depth model follows q2-pod (docs/architecture.md).
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

/* Artists (patch/artists.c, the scoped Cover Flow). loadLocalClassList(0xf004) runs
 * GetAllAlbumArtist when the artist_type global (0xa05a14, PLAYSET ARTISTTYPE, read by config_init
 * @0x4e52d0) is 1, else getAllArtist (@0x4ee6e8); both rows carry the name in REC_TITLE (row
 * callbacks 0x4e95b8 / 0x4e9724), which the stock Artists rows show (@0x535dec). A tap there opens
 * album_page {0xf004, row} (@0x535d40), whose loadAlbumList(0xf004, row) (0x4ee8d8) stores the
 * artist in classinfo_save and loads its albums with class 0xff01 (getAlbumByAlbumArtist /
 * getAlbumByArtist, @0x4ee7cc); an album row then goes through loadAlbumdetailList(0xff01, row),
 * which leaves 0xff11 (getMusicByAlbumAnd[Album]Songer, @0x4ee858) in classinfo[0]. */
#define CLASS_ARTISTS 0xf004
#define CLASS_ARTIST_ALBUMS 0xff01
#define ID_ALL_SONGS -2    /* REC_ID of the "All songs" row getAlbumByArtist appends last (@0x4eae30); its tracks are all the artist's songs (classinfo[8] = 1, @0x4eebec) */

/* Cover Flow geometry, 320x480 portrait: a CF_VIEW_W x CF_VIEW_H frame under the 50 px navbar.
 * The centre cover is ART_SIZE square with its top CF_TOP below the frame's; side covers turn
 * 60 degrees inward (the sine table in coverflow.c), sit CF_X1 px from the centre and then CF_XS
 * apart, CF_Z1 and then CF_ZS px further back, seen from CF_EYE px. Brightness (of 256) is 256 at
 * the centre, CF_BRIGHT1 one out, CF_BRIGHT2 two out, 0 three out. Each cover reflects CF_REFLECT
 * px at native size from CF_REFLECT_TOP (of 256) of its brightness down to black. */
#define ART_SIZE 168
#define CF_VIEW_W 320
#define CF_VIEW_H 276
#define CF_CX 160          /* the centre line, between columns 159 and 160 */
#define CF_TOP 31
#define CF_EYE 312
#define CF_X1 110
#define CF_XS 48
#define CF_Z1 96
#define CF_ZS 22
#define CF_BRIGHT1 192
#define CF_BRIGHT2 128
#define CF_REFLECT 26
#define CF_REFLECT_TOP 64
#define DRAG_PX 108        /* finger travel per album */
#define TAP_SLOP 12        /* px either way: a release within this of the down point (and no drag) is a tap */
#define DRAG_START 5       /* px along the carousel, and no more across, start a drag (counted from there); tune on the device */
#define FLING_MS 120       /* the fling coasts for this long at the release velocity */
#define FLING_WINDOW 80    /* ms of samples the velocity is taken over; none in it but the release, no fling */
#define SNAP_MS 16         /* the snap animation's timer period */
#define OVER_NUM 2          /* the rubber band's ceiling past an end: OVER_NUM / OVER_DEN of a cover (patch/coverflow.c rubber) */
#define OVER_DEN 5
#define SNAP_BASE_MS 120   /* an ease takes this plus SNAP_ALBUM_MS per album of travel, at most SNAP_MAX_MS */
#define SNAP_ALBUM_MS 60
#define SNAP_MAX_MS 360
#define FNV_SEED 2166136261u

/* Cover Flow landscape (patch/coverflow.c, docs/ui.md): the same depth renderer into the 320 x 400 body under
 * the navbar (which stays, Back, toggle and Now Playing working as in portrait), its bitmap rotated a quarter
 * turn, so the carousel runs along the 400 px side. A logical landscape frame CFL_W x CFL_H (x right, y down as
 * the user sees it, the content turned 90 degrees clockwise on the screen, the device held turned
 * counter-clockwise): logical (x, y) is physical (CFL_H - 1 - y, x), CFL_Y px down the window. The centre cover is
 * the 168 px texture 1:1 like portrait's and the eye, depth and reflection are portrait's; the side covers are
 * spread wider (CFL_X1, CFL_XS). The captions are drawn into the frame with the page's font (the glyphs turned by
 * the same map) in the CFL_CAP_W px under the reflections. */
#define CFL_Y 50           /* the frame's top in the window: under the 50 px navbar */
#define CFL_W 400          /* the window's 450 px less the navbar */
#define CFL_H 320
#define CFL_CX 200
#define CFL_TOP 28
#define CFL_X1 160
#define CFL_XS 84
#define CFL_DRAG_PX 132    /* finger travel per album */
#define CFL_ALBUM_Y 244    /* the caption lines' tops (logical), the album's 22 px, the artist's 18 px */
#define CFL_ARTIST_Y 274
#define CFL_CAP_W 368      /* 16 px margins, as portrait's captions */
#define CANVAS_FONT_SIZE 0x0c   /* canvas_t: font_size u16 @0xc, font_t * @0x34 (canvas_draw_text @0x645348 reads both) */
#define CANVAS_FONT 0x34
#define GLYPH_FORMAT_ALPHA 0    /* glyph_t: x,y s16, w,h,advance u16 @0..9, format u8 @0xa (0 = 8 bit alpha, rows w bytes), pitch u8, data @0xc */

/* Pointer events (Cover Flow's touch layer, the Albums grid) */
#define EVT_POINTER_DOWN 0xff   /* input_device_status_on_input_event jump table @0x88f120 */
#define EVT_POINTER_MOVE 0x101
#define EVT_POINTER_UP 0x103
#define EVT_POINTER_ABORT 0x107 /* widget_on_pointer_up/move dispatch it @0x6719b8 */
#define PE_X 0x18               /* pointer_event_t: x, y (screen coordinates, widget_to_local turns them local); event_t.time u64 @0x8 */
#define PE_Y 0x1c
#define EV_TIME 0x08

/* AWTK ABI used by the Cover Flow renderer (all read from this demo) */
#define EVENT_PAINT_CANVAS 0x18 /* paint_event_t.canvas: paint_event_init stores a3 there @0x65026c */
#define BITMAP_FLAGS 0x0c       /* bitmap_t: w@0, h@4, flags u16@0xc, format u16@0xe, data@0x14 */
#define BITMAP_FORMAT 0x0e      /*   (bitmap_create_ex @0x6400d4: sw w,0; sw h,4; sh fmt,0xe) */
#define BITMAP_RGBA8888 1       /* bitmap_format_t: 1 RGBA8888, 2 ABGR, 3 BGRA, 4 ARGB */
#define BITMAP_RGBA_AT { { 0, 1, 2, 3 }, { 3, 2, 1, 0 }, { 2, 1, 0, 3 }, { 1, 2, 3, 0 } }
#define IMAGE_SCALE_AUTO 4      /* image_draw_type_t, as the stock cover rows use */
#define IMAGE_DRAW_CENTER 2     /* centred at its own size (DEFAULT 0, ICON 1, CENTER 2, SCALE 3, SCALE_AUTO 4) */

/* Cover Flow page geometry (the ui/m1pod_cover.bin asset must match; tools/pod_ui.py) */
#define CF_COVER_Y 89      /* view_covers' y in the window (NAVBAR_H + 39) */

/* ---------------------------------------------------------------------------
 * Shuffle (patch/shuffle.c, docs/architecture.md). Read from this demo with tools/dis.py.
 */
#define REC_SIZE 0x58      /* stSongInfo: memset(local, 0, 0x58) in loadSongList @0x4e2e4c and the row callback @0x4e908c */
#define REC_CLASS 0x38     /* loadSongList stores its class argument here in every copy @0x4e3144 */
#define REC_TRACK 0x3c     /* atoi(track) @0x4e9304 (column 10 of songtable) */
#define REC_DISC 0x40      /* atoi(cd_num) @0x4e9318 (column 11); getMusicByAlbum sorts by disc, then track (0x4e9020) */
#define CLASS_ALL_SONGS 0xf001 /* loadLocalClassList: getAllMusic into *pdeq_showlist (@0x4ee5bc), the Songs page's class */
/* mclGetPlayMode/mclSetPlayMode values: Now Playing's mode button cycles 0..3 and styles them
 * btn_imgorder / btn_imgcycle1 / btn_imgrandom / btn_imgcycle (@0x5398cc..0x539948) */
#define MODE_ORDER 0       /* list play: stops after the last track (mclNextSong @0x5d5950) */
#define MODE_REPEAT_ONE 1
#define MODE_SHUFFLE 2     /* mclNextSong draws from the unplayed-index pool mclLoadPlayList fills (@0x5d1fe0, 0x5d03b0) */
#define MODE_REPEAT_ALL 3
#define MSGINFO_KIND 1     /* dialog/msginfo_dialog context {kind, ms, text[0x200], text2[0x200]}: kind 1 one white line (@0x4786f8) */
#define MSGINFO_MS 2000    /* as the stock "file not found" toast @0x525a04 */
#define MSGINFO_TEXT 0x200
#define CONFIRM_KIND_WRAP 5 /* dialog/confirminfo_dialog context, same layout: kind 5 = a centred white 20 px word-wrapped label (260 x 80 at y 25, @0x472e1c), text at +8 */
#define CONFIRM_YES 0xa     /* navigator_to_with_context returns this for the Yes button (btn_enter); the call is modal (on_eqreset_onclick @0x49dd6c) */
#define SHUFFLE_MAX 65536  /* Shuffle Albums/Folders sort an index of at most this many songs (q2-pod QUEUE_LIMIT) */

/* ---------------------------------------------------------------------------
 * Library rows (patch/rows.c, patch/rows.json, docs/architecture.md). The row fit follows q2-pod's
 * compact_row_layout (patch/navigation.c, MIT); the ABI is this demo's (tools/dis.py).
 */
#define W_X 0x00                /* widget_t x, y, w, h: widget_move_resize_ex stores them @0x66d268 */
#define W_Y 0x04
#define W_W 0x08
#define W_H 0x0c
#define W_PARENT 0x44           /* widget_t parent: widget_restack reads it, lw $v0, 0x44($a0) @0x66a014 */
#define W_CHILDREN_LAYOUT 0x64  /* widget_set_children_layout: sw $v0, 0x64($s0) @0x657014 */
#define W_VT 0x70               /* widget_t vtable: widget_paint reads it, lw $v0, 0x70($s0) @0x66dd6c */
#define SV_PAINT_CHILDREN 0xf4  /* scroll_view_t paint-children hook: scroll_view_on_paint_children calls it (lw $t9, 0xf4($s3) @0x610ed0), list_view stores 0x60c164 (sw @0x60cd10) */
#define LAYOUT_VTABLE 0x0c      /* children_layouter_t: str_t params (12 bytes), then the vtable */
#define LAYOUT_X_MARGIN 0x14    /* children_layouter_default_t u8s, read by its layout @0x63a5a0 */
#define LAYOUT_SPACING 0x16
#define DEFAULT_LAYOUT_VTABLE 0x904924u /* children_layouter_default_create stores it @0x63af28 */
#define DEFAULT_LAYOUT_FN 0x63a444u     /* its slot 2, the layout (children_layouter_default_layout) */
#define LAYOUT_VTABLE_WORDS 8   /* type, to_string, layout, get_param, set_param, destroy, is_valid, clone */
#define LAYOUT_SLOT 2
#define ROW_RIGHT 12            /* a row's text ends this far from its right edge (the x=12 rows' margin) */
#define ROW_ART 52              /* the album cover (rows.json ART): 1:1 thumbnails */
#define ROW_ART_INSET 4         /* the cover's left inset on x=0 rows */
#define ROW_SEPARATOR 4         /* list_item_style draws a 4 px separator under each list_item row */
#define ROW_MARKER_IMAGE "np_row_playing"   /* the playing row's marker: 40 x 20, a 20 px wave at its right end (tools/mod_icons.py NP) */
#define ROW_NUM_W 22           /* the album tracks' number column (rows_track_number): every digit is 10 px at 19 px by AWTK's metrics, "99" = 20 */
#define ROW_NUM_W3 32          /* the column of a 3-digit number (a 100+ track album): "999" = 30 */
#define ROW_NUM_STYLE "srlabel_tracknum_style"   /* label style of the number: #AAAAAA, 19 px, right aligned (tools/mod_ipodrows.py) */
#define ROW_MAX_CHILDREN 16   /* the row fit leaves anything with more children to the stock layout */


/* ---------------------------------------------------------------------------
 * The album view (patch/albuminfo.c, docs/ui.md): the stock albuminfo_page's header item, rebuilt
 * in place by the hook on albuminfo_listitem0_layout. REC_YEAR: songtable's column 9 (`year`),
 * which the row callback @0x4e908c atoi()s into the stack record at +0x30; the insert (@0x5edfc4)
 * writes it from taglib_tag_year. There is no duration column (time / time_end are CUE offsets, 0
 * for ordinary files, @0x5edb88), so the page shows none. CLASSINFO_ALL_SONGS: the byte
 * loadAlbumdetailList sets in the browsing record for the stock All songs row (0xff01, @0x4eebec).
 * Geometry in the header list_item (310 wide, the 320 px list less its scroll bar; the item starts at
 * screen x 0, so item x is screen x and everything is centred on x AH_MID = 160, not on the item's 155):
 * the cover AH_ART square, centred (the cover thread renders /tmp/abp/<md5>1.jpg at AH_ART, rows.json),
 * its four AH_CORNER px corners masked by images; the title, artist and "year . N tracks" lines centred in
 * AH_TEXT_W; the round Shuffle (AH_SHUF_W) and the Play all pill (AH_PLAY_W), AH_GAP apart, centred as a
 * pair; the stock track rows follow at AH_HDR_H. The list starts at the window's top (the floating controls, AH_NAV_*, sit
 * over it), so the header's first AH_NAV_TOP rows are padding: the cover's AH_ART_Y is AH_NAV_TOP + 6.
 */
#define REC_YEAR 0x30
#define CLASSINFO_ALL_SONGS 8
#define AH_MID 160
#define AH_ART 160
#define AH_ART_X 80
#define AH_ART_Y 50
#define AH_CORNER 10
#define AH_TEXT_X 17
#define AH_TEXT_W 286
/* vertical rhythm (tools/ah_ink.py, measured ink): cover bottom -> title capitals 16, title baseline -> artist capitals 9,
 * artist baseline -> year digits 9, year baseline -> pill top 16; the label rects are their font size high */
#define AH_TITLE_Y 224
#define AH_TITLE_H 22
#define AH_ARTIST_Y 247
#define AH_ARTIST_H 18
#define AH_META_Y 267
#define AH_META_H 15
#define AH_BTN_Y 292
#define AH_BTN_H 44
#define AH_SHUF_X 42
#define AH_SHUF_W 44
#define AH_DISC 38              /* the Shuffle disc as drawn (ah_shuffle*.png), centred in its AH_SHUF_W x AH_BTN_H touch rectangle */
#define AH_GAP 12               /* drawn gap between the disc and the pill */
#define AH_PLAY_X 95            /* AH_SHUF_X + (AH_SHUF_W + AH_DISC) / 2 + AH_GAP: the pill's touch rectangle starts where it is drawn */
#define AH_PLAY_W 180
#define AH_PILL_H 40            /* the pill as drawn (ah_pill*.png, the style's bg_image), centred in its AH_BTN_H touch rectangle */
/* The pill's glyph and text (tools/mod_ipodrows.py PLAY_*, docs/ui.md): AWTK centres the AH_PILL_GLYPH px glyph in a
 * square AH_BTN_H wide at margin_left, and draws the text left aligned at the square's end plus spacer. The hook sets
 * margin_left (per state, inline) so that glyph + AH_PILL_GAP + text is centred in the pill; the style carries
 * AH_PILL_MARGIN (the margin for an English text) for when the text cannot be measured. */
#define AH_PILL_GLYPH 16
#define AH_PILL_GAP 8
#define AH_PILL_MARGIN 37
#define AH_HDR_H 344
/* Play all and Shuffle open Now Playing like a track tap (ah_open_player): the widget name field the stock pop loop
 * compares (@0x525920 lw a0, 0x10(top)), at most AH_POP_MAX pages popped, and the stock Play all handler the hook takes
 * off the button (bound @0x526368 with the item as its context) */
#define WIDGET_NAME 0x10
#define AH_POP_MAX 16
#define AH_STOCK_PLAY 0x525d48u
/* The album page's cover tint (patch/albuminfo.c, tools/mod_icons.py ah_tint): the window colour is the cover's tone (pod_tone,
 * the constants of Now Playing's) under a black gradient image, ah_tint.png (a window sized child of the page window, first,
 * insensitive), whose alpha runs from AH_TINT_A_TOP on window row 0 to AH_TINT_A_BOT on row AH_TINT_ROWS - 1 (the end of
 * the header: AH_HDR_H) and stays there below (200: the deep tint, 78 % dark), so the transparent track rows and the scroll bar strip show a deep version of the cover colour.
 * Only a real cover tints (the page's image is a file:// url): the placeholder disc and the All albums card stay black. The
 * cover's corners are painted in the colour behind them from its after-paint (the cover is AH_ART_Y below the header's top,
 * the header scrolls: window row = AH_ART_Y - yoffset + cover row). AH_TICK_MS: the poll that waits for the cover
 * thread's file.
 * The floating controls (docs/modules/album-page.md): the stock navbar view is a band over the top of the page, AH_NAV_W x AH_NAV_BAND_H at the
 * window's origin, last in the window (above the list, which starts at the window's top and is AH_WIN_H high); the stock builders'
 * buttons (main's slots, docs/modules/navbar.md; AH_NAV_H high in 0x526a3c) draw glass discs through the page theme. The header's first
 * AH_NAV_TOP rows are padding, so at rest the cover stays where it was, at row AH_ART_Y. */
#define AH_NAV_H 44             /* the shared builder's buttons (rows.json) */
#define AH_NAV_BAND_H 50        /* the band: tall enough for the page's own builder's 50 px buttons */
#define AH_NAV_TOP 44
#define AH_WIN_H 450
#define AH_TINT_A_TOP 64
#define AH_TINT_A_BOT 200
#define AH_TINT_ROWS 344        /* AH_HDR_H: the ramp ends with the header */
#define AH_TICK_MS 300
/* The tone cache (patch/common.c): entries of {key, tone, stamp}, 12 bytes each. The album page names its album as the stock
 * header does: classinfo + 0xd the title, the artist at +0x10d (+0x20d when g_class_type is 0xff14, @0x524b00). */
#define TONE_CACHE_N 64
#define CLASSINFO_ALBUM 0xd
#define CLASSINFO_ARTIST 0x10d
#define CLASSINFO_ARTIST_14 0x20d
#define CLASS_14 0xff14

/* ---------------------------------------------------------------------------
 * The Albums grid (patch/albums.c, docs/ui.md). GRID_COLS columns of GRID_COVER px square covers with GRID_GAP px
 * between them, centred (GRID_MARGIN each side: (320 - 2 * 144 - 8) / 2 = 12); under each cover the album
 * (GRID_TITLE_H high, GRID_TITLE_GAP below the cover) and the artist (GRID_SUB_H high), each one line; rows
 * GRID_ROW_GAP apart; the first row GRID_ROW_GAP below the top and the last GRID_ROW_GAP above the bottom. The
 * view is the 400 px under the 50 px navbar (ui/m1pod_albums.bin, tools/pod_ui.py). GRID_TILES covers stay decoded
 * (memory: GRID_TILES * GRID_COVER^2 * 4 = 0.99 MB at most, plus the placeholder).
 * ALBUMS_DEFAULT_GRID is the mode a first use opens (1 grid, 0 list); the choice is then the setting file
 * ALBUMS_FILE. The navbar toggle button is NAV_VIEW_W wide. On the Pod pages (Albums, Artists, Cover Flow's
 * landscape switch; ui assets) it sits at NAV_VIEW_X, flush left of Now Playing (x 260); the page title ends at
 * its left edge.
 *
 * The list mode of the same page: rows LIST_ROW_H high like the library rows (rows.json PITCH 64), a LIST_ART px
 * cover at (LIST_ART_X, LIST_ART_Y), the title (LIST_TITLE_H high at LIST_TITLE_Y, the page's label_row_title
 * style: 21 px white) and the artist (LIST_SUB_H high at LIST_SUB_Y, label_row_sub: 18 px #AAAAAA) from
 * LIST_TEXT_X for LIST_TEXT_W px (12 px right margin); a pressed row is filled LIST_PRESS over its LIST_ROW_H - 1
 * top lines, the last line is the LIST_HAIR hairline. Colours are r,g,b,a bytes of canvas_set_fill_color's word.
 */
#define ALBUMS_DEFAULT_GRID 1
#define GRID_COLS 2
#define GRID_COVER 144
#define GRID_GAP 8              /* between columns */
#define GRID_ROW_GAP 10         /* between rows, and above the first / below the last: two rows (10 + 190 + 10 + 190) fill the 400 px view exactly */
#define GRID_MARGIN 12
#define GRID_R 8                /* the covers' corner radius (the Albums grid and the Recently Played shelf), blended into the black behind them (patch/grid.c) */
#define GRID_TITLE_GAP 4
#define GRID_TITLE_H 22         /* the album, the grid title style (18 px white) */
#define GRID_SUB_H 20           /* the artist, directly under it (15 px #AAAAAA) */
#define GRID_VIEW_H 400
#define GRID_TILES 12           /* the ring: the cells in view, the next rows in the scroll direction, a little history behind */
#define NAV_H 50
#define NAV_VIEW_X 214
#define NAV_VIEW_W 46
#define NAV_CF_X 168            /* the Albums page's Cover Flow button, flush left of the toggle; its title ends here */
#define NAV_CF_W 46
#define LIST_ROW_H 64
#define LIST_ART 52
#define LIST_R 4                /* the list covers' corner radius: cut in the bitmap's alpha (a pressed row's fill shows behind them; patch/grid.c blend) */
#define LIST_ART_X 10
#define LIST_ART_Y 4
#define LIST_TEXT_X 74          /* LIST_ART_X + LIST_ART + 12 */
#define LIST_TEXT_W 234         /* to the 12 px right margin: 74 + 234 + 12 = 320 */
#define LIST_TITLE_Y 7
#define LIST_TITLE_H 24
#define LIST_SUB_Y 33
#define LIST_SUB_H 20
#define LIST_HAIR 0xff222222u
#define LIST_PRESS 0xff333333u

/* ---------------------------------------------------------------------------
 * Now Playing (patch/nowplaying.c, docs/architecture.md section 8a, ui assets tools/mod_nowplaying.py). The hook is
 * on playing_page_init (0x53d1e4). Timer callbacks answer RET_REPEAT to run again (the stock page timer does:
 * player_timer_start @0x53c210 registers 0x53cf48, which returns 8 while the page lives) and RET_OK to end.
 * COVER_SRC is the cover source type word (0x97cad8): parseplaycover_thd (0x4ded84) sets it to 1 before it
 * replaces the files and to 2 (/tmp/coverpic.jpg, embedded art), 3 (/tmp/externpic.jpg, a folder image) or 5
 * (/tmp/externpic.jpg, copied from the .downpic cache) once the file is complete; the page's cover loader
 * (0x53a5d8) reads exactly these. Any other value has no JPEG file (4 random_cover, 6/7 streamed).
 * NP_NEUTRAL is the no-cover tone; the cover's tone has value NP_V_MIN..NP_V_MAX and keeps NP_SAT_NUM/NP_SAT_DEN of
 * the colour's distance from its brightest channel, so the 0.15..0.92 black gradient over it leaves the white title and the #AAAAAA lines at least 4.5:1 (test/pod/nowplaying.py).
 */
#define RET_REPEAT 8
#define COVER_SRC_BUSY 1
#define COVER_SRC_EMBEDDED 2
#define COVER_SRC_FOLDER 3
#define COVER_SRC_CACHE 5
#define NP_TICK_MS 500
#define NP_HASH_MAX 524288
#define NP_KEY_NEUTRAL 1
#define NP_NEUTRAL 0xff202020u
#define NP_V_MIN 32
#define NP_V_MAX 192
#define NP_SAT_NUM 23
#define NP_SAT_DEN 25
/* The cover's rounded corners (painted by the payload, np_on_art_paint) and the gradient under them (np_tint.png:
 * black, alpha NP_ALPHA_TOP on the window's first row to NP_ALPHA_BOTTOM on its last, NP_WIN_H rows): the cover is
 * NP_ART px square at window y NP_ART_Y, its corners NP_ART_R px. Equal to the constants of tools/mod_nowplaying.py. */
#define NP_ART 264
#define NP_ART_Y 28
#define NP_ART_R 12
#define NP_ALPHA_TOP 38
#define NP_ALPHA_BOTTOM 235
#define NP_WIN_H 450
/* The info page's lines (np_info): the stock text is read into NP_INFO_BUF bytes (stock writes them with a 0x200
 * buffer, so a longer text is never rewritten); the quality line keeps single spaces round its bars when the result is
 * at most NP_INFO_SPACED characters (the label is 304 px wide at 18 px, 8 px from each side: such a line is at most 272 px
 * wide, a DSD line without the spaces at most 295). */
#define NP_INFO_N 6
#define NP_INFO_BUF 512
#define NP_INFO_SPACED 36
/* The status bar follows the page (EXPERIMENTAL, np_bar_*): the window events of the page (widget_on on the window:
 * window_manager_default_open_window dispatches 0x12c to the window a new non-keyboard, non-overlay window covers and 0x12d
 * to the one it uncovers, @0x69182c / @0x691b3c), the stock black, and the largest weighted square sum (2126 r^2 + 7152 g^2
 * + 722 b^2, channels 0..255) the bar colour may have: gamma 2 is above the sRGB luminance, so L <= 0.183 and white text
 * keeps 4.5:1 (test/pod/nowplaying.py checks the true figure). */
#define EVT_WINDOW_TO_BG 0x12c
#define EVT_WINDOW_TO_FG 0x12d
#define NP_BAR_STOCK 0xff000000u
#define NP_BAR_LUM_MAX 119000000u

/* ---------------------------------------------------------------------------
 * The mini player bar on the Home instance of the menu (patch/minibar.c, docs/modules/minibar.md; the widgets are in
 * ui/m1pod_menu.bin, tools/pod_ui.py MB_*, which must equal these). Apple Music's floating mini player: a full pill in the 450 px
 * window, MB_W x MB_H at (MB_X, MB_Y), corner radius MB_R = MB_H / 2, a pre-rendered translucent glass image (mb_glass, mb_glass_down:
 * dark fill, sheen, rim light; the card button's bg_image; not tinted by the album). The cover is MB_ART px square, MB_ART_X from the pill's left and MB_ART_Y from its top, its
 * four corners MB_ART_R px (alpha in the bitmap). Title (17 px white) and artist (16 px, light grey) are hscroll_labels MB_TEXT_W wide
 * from MB_TEXT_X (ellipsis, never scrolling); play (or pause, one of the two shows) and next are MB_BTN_W x MB_H touch targets at
 * MB_PLAY_X / MB_NEXT_X (glyph centres 51 px apart, the next centre 35 px from the pill's right end). The list always runs to the window
 * bottom, under the translucent pill; while the bar shows, a trailing spacer row pod_pad (MB_PAD high) is visible so the last row can scroll
 * clear above it (the stock list_view layout keeps it: it sums every visible child's own height). MB_FIRST_MS: the one-shot that starts the page timer (nothing runs
 * in the menu's first paint), MB_TICK_MS its period; MB_SETTLE: ticks that re-read the /tmp cover file after a track change (demo
 * writes it a little later). MB_PLAYING: mclGetPlayStatus() while playing.
 */
#define MB_X 8
#define MB_Y 384
#define MB_W 304
#define MB_H 56
#define MB_R 28
#define MB_GAP 8
#define MB_PAD 64          /* the list's bottom padding while the bar shows: a trailing spacer row pod_pad of this height, so the last row scrolls clear above the pill (WIN_H - HOME_PAD - (MB_Y - MB_GAP)) */
#define MB_ART 36
#define MB_ART_X 14
#define MB_ART_Y 10
#define MB_ART_R 5
#define MB_TEXT_X 60
#define MB_TEXT_W 130
#define MB_TITLE_Y 7
#define MB_TITLE_H 22
#define MB_ARTIST_Y 29
#define MB_ARTIST_H 20
#define MB_PLAY_X 194
#define MB_NEXT_X 245
#define MB_BTN_W 48
#define MB_FIRST_MS 120
#define MB_TICK_MS 500
#define MB_SETTLE 3
#define MB_PLAYING 2
#define MB_GREY 0xff2b2b2bu
/* The backdrop blur behind the glass (EXPERIMENTAL, patch/minibar.c mb_blur, tools/pod_blur.py, docs/modules/minibar.md): the pixels under the pill are
 * read from and written to the lcd's drawing buffer in the card's EVT_BEFORE_PAINT, only when every pin below holds at run time.
 * EVT_BEFORE_PAINT: widget_paint dispatches 0x11f right after canvas_translate to the widget and before widget_on_paint_background (@0x66dd98), 0x120 after
 * the children and the border (@0x66de3c). canvas_t: ox, oy at 0 / 4 (canvas_translate @0x6434d4 adds to them), the clip rectangle left, top, right, bottom
 * (inclusive) at 0x10..0x1c (canvas_get_clip_rect @0x643718 turns it into x, y, w, h), its lcd at 0x30 (canvas_get_width @0x64352c passes it to lcd_get_width).
 * lcd_t: the first word is begin_frame (lcd_begin_frame @0x657b60 `lw v0, (a0)`, @0x657b8c `lw t9, (s0); jr t9`); the 565 memory lcd's init @0x695dc8
 * (reached by lcd_mem_bgr565_init @0x696bc4, bitmap_get_bpp_of_format(6) = 2 bytes @0x695e20) stores 0x695cb0 there (@0x695ec4), width and height at
 * 0xb0 / 0xb4 (@0x695eb0, @0x695eb8; lcd_get_width @0x658484 reads 0xb0), line length at 0x120 (and 0x124: its set_line_length @0x695034 writes both; init @0x695ed0 =
 * width x 2), and the drawing buffer at 0x110 (lcd_mem_set_fb @0x695d9c `sw a1, 0x110(a0)`; the double-buffered create @0x696cc4 stores the online one at 0x114
 * and gives the offline one to that setter). Any other lcd type (the 5551 special one, 24/32 bit) fails the begin_frame word and gets no blur.
 * MB_HW x MB_HH: the half-resolution plane (4 bytes a block, calloc'd once). MB_BLUR_OFF: an SD file that turns the blur off. */
/* EVT_SCROLL 0x152: the scroll_view's yoffset setter (0x60ff08) builds offset_change_event_init(e, 0x152, widget, new, old) and widget_dispatch es it to the scroll view
 * (@0x60ff38..0x60ff74); it is called by scroll_view_scroll_delta_to (the drag, @0x610b9c), scroll_view_set_offset (the fling and scroll_to animations, @0x6116b4)
 * and the property setter (@0x611dfc), every way the list's offset changes. The list scrolls under the pill, so the pill is invalidated on it (mb_on_scroll). */
#define EVT_SCROLL 0x152
#define EVT_BEFORE_PAINT 0x11f
#define CANVAS_OX 0x00
#define CANVAS_OY 0x04
#define CANVAS_CLIP 0x10
#define CANVAS_LCD 0x30
#define LCD_BEGIN 0x00
#define LCD_W 0xb0
#define LCD_H 0xb4
#define LCD_FB 0x110
#define LCD_LINE 0x120
#define LCD_565_BEGIN 0x695cb0u
#define MB_HW 152          /* MB_W / 2 */
#define MB_HH 28           /* MB_H / 2 */

/* ---------------------------------------------------------------------------
 * The Recently Played shelf on the Home instance of the menu (patch/recent.c, docs/modules/recent.md; the widgets are in
 * ui/m1pod_menu.bin, tools/pod_ui.py SH_*, which reads GRID_* from this file and must equal the rest). The shelf is the Albums grid
 * (patch/grid.c, the GRID_* geometry above: GRID_COVER covers, GRID_GAP apart, from x GRID_MARGIN, the album GRID_TITLE_H and the artist
 * GRID_SUB_H under each, rows GRID_ROW_GAP apart) in a view of its own, SH_W (the scroll view's width) wide: a child of pod_scrollview that
 * follows the last shown row (Settings), before the mini bar's spacer, hidden and insensitive in the asset, scrolling with the list.
 * GRID_COLS x SH_ROWS cells, the SH_TILES (= RC_MAX) most recent albums, row-major; ceil(albums / GRID_COLS) rows, SH_H(n) high, SH_HMAX at most: the
 * payload sets the view's height before the rows are arranged and the menu sums it into virtual_h. The 2 cells of a row end at
 * GRID_MARGIN + 2 * GRID_COVER + GRID_GAP = 308, inside the 310 px scroll view. At the top a section header, the stock hscroll_label
 * pod_sh_head (the translation of \"Recently Played\", SH_HEAD_PX white, one line cut with an ellipsis, insensitive) at x SH_HEAD_X,
 * SH_HEAD_TOP from the top, SH_HEAD_W x SH_HEAD_H (its text starts 2 px in: the label's margin, so it lines up with the covers at
 * GRID_MARGIN), then SH_HEAD_GAP of air; its ink starts 20 px below the Settings row and ends 8 px above the covers (the line box has a
 * little slack). The first row starts at SH_TOP = SH_HEAD_TOP + SH_HEAD_H + SH_HEAD_GAP; nothing below the last artist line (SH_BOTTOM), so
 * scrolled to the end it is MB_GAP above the pill. The covers' corners are the Albums grid's (GRID_R).
 * RC_MAX: entries the file keeps; RC_FIRST_MS: the one-shot that starts the page timer (the menu's first paint decodes nothing);
 * RC_TICK_MS: one cover decoded per tick; RC_TAP_PX: a release closer than this to the press (both axes) is a tap (the scroll view's own
 * drag threshold, SC_DRAG_PX: from there on it drags). The file: RC_MAGIC line, then one line per album (tools/pod_recent.py)
 * (the most recent first); RC_STR / RC_PATH: bytes kept per name / path (NUL included); RC_FILE_MAX: the most bytes read.
 */
#define SH_W 310
#define SH_ROWS 3
#define SH_TILES 6          /* GRID_COLS * SH_ROWS, and RC_MAX: every album the file keeps (patch/recent.c #errors if they differ) */
#define SH_HEAD_X 10
#define SH_HEAD_W 300
#define SH_HEAD_TOP 17
#define SH_HEAD_H 22
#define SH_HEAD_PX 20
#define SH_HEAD_GAP 5
#define SH_TOP 44
#define SH_BOTTOM 0
#define SH_H(n) (SH_TOP + (n) * GRID_CELL_H + ((n) - 1) * GRID_ROW_GAP + SH_BOTTOM)   /* the shelf's height for n rows of covers: 234, 434, 634 */
#define SH_HMAX SH_H(SH_ROWS)
#define RC_MAX 6
#define RC_STR 96
#define RC_PATH 256
#define RC_FILE_MAX 3072
#define RC_FIRST_MS 150
#define RC_TICK_MS 30
#define RC_TAP_PX 10
#define RC_RESOLVE_MS 5000   /* the menu's to-foreground resolves an album's cover key (loads the stock album list) only this long after the menu opened */


/* ---------------------------------------------------------------------------
 * List gestures (patch/scroll.c, docs/architecture.md "List gestures"). The stock scroll_view (g_scroll_view_vtable
 * 0x97a298; every stock list is list_view > scroll_view > list_item rows) keeps its drag state in the widget:
 * scroll_view_t fields as its on_event (0x610724) and scroll_view_is_dragged (0x61064c) read them. The hook is the
 * vtable's on_event_before_children slot, which widget_on_event_before_children (0x666c34) calls with every pointer event
 * before the widget's children see it. widget_animator_t: manager @0x58, state @0x28 (1 = running, widget_animator_start
 * @0x673114), the widget it animates @4.
 */
#define SC_RET_STOP 0xb         /* ret_t RET_STOP: widget_on_pointer_down returns at once, children and the widget itself skipped (@0x671324) */
#define SC_XSLIDE 0x90          /* scroll_view_t: xslidable, yslidable, snap_to_page (bytes; is_dragged @0x610680, @0x610688, @0x6106cc) */
#define SC_YSLIDE 0x91
#define SC_SNAP 0x92
#define SC_DOWN_X 0x98          /* the pointer-down position (on_event DOWN stores e->x, e->y @0x61086c, @0x61087c) */
#define SC_DOWN_Y 0x9c
#define SC_PRESSED 0xa0         /* bytes: pressed (set by DOWN, @0x61083c) and dragged (set by the first MOVE past the threshold, @0x610c34) */
#define SC_DRAGGED 0xa1
#define SC_WA 0xe8              /* the running scroll animator (scroll_view_scroll_to @0x610548); cleared by the end handler 0x6101b8 (@0x610208) */
#define SC_AN_STATE 0x28        /* widget_animator_t: state, 1 = running (widget_animator_start @0x673114) */
#define SC_AN_WIDGET 0x04       /* the widget it animates (widget_animator_stop reads it @0x673258) */
#define SC_AN_RUNNING 1
#define SC_DRAG_PX 10           /* scroll_view_is_dragged's threshold: slti .., 0xa @0x6106e0 (kept) */
#define SC_YOFF 0x84            /* scroll_view_t yoffset (int): the setter 0x60ff08 stores it `sw s1, 0x84(s0)` @0x60ff78, the list_view layouter clamps it @0x60b250..0x60b278 (xoffset 0x80, virtual_h 0x7c) */
#define EVT_SCROLL_END 0x151    /* widget_dispatch_simple_event(scroll_view, 0x151), the last thing the scroll animation's end handler 0x6101b8 does (@0x610238..0x610248; 0x14f before it) */

/* libc constants (MIPS Linux) the payload passes to the stock libc stubs */
#define F_OK 0
#define O_RDONLY 0
#define O_WRONLY 1
#define O_APPEND 0x8
#define O_CREAT 0x100
#define O_TRUNC 0x200
#define PROT_READ 1
#define MAP_SHARED 1
#define MAP_FAILED ((void *)-1)

/* Now Playing's More dialog (patch/playmore.c, docs/modules/playmore.md): ui/dialog/playmore_dialog.bin is a 320 px wide
 * sheet pinned at y 130 (the stock init, @0x479d10, and its to-background handler @0x4789f0) holding list_view playmore_listview >
 * scroll_view playmore_scrollview (310 px, the scroll bar scroll_bar_m beside it, 10 px) > list_item rows, PM_ROW_H (50, the
 * list_view's item_height) high each; the asset adds the hidden rows pod_more and pod_back. The payload shows PM_PAGE_N rows
 * at a time and puts the sheet on the bottom of the 480 px screen (the stock 130 + 350 ends there too). */
#define PM_ROW_H 50
#define PM_PAGE_N 4
#define PM_SCREEN_H 480
#define PM_DIALOG_W 320
#define PM_SV_W 310
#define PM_BAR_W 10

/* The Playlists page (patch/playlists.c, docs/modules/playlists.md). Playlists live in /mnt/data/database.db, table `playlist`: a row with
 * id <= 100 is a playlist (getAllPlayList @0x4ec4e8: `select * from playlist where id <= 100`; its name is REC_TITLE, its id REC_ID and also
 * REC_DISC, createPlayListItem @0x4eeca8 stores both), a row with id > 100 is a song (getMusicByPlayList @0x4eddac: `where id > 100 and
 * cd_num=<id>`, no ORDER BY: insertion order) with the same 18 columns as a library song, so its album and artist are as they were when it was
 * added. loadLocalClassList(CLASS_PLAYLISTS) puts the playlists in *pdeq_playlist (@0x4ee614: getAllPlayList, assigned @0x4ee63c), and
 * (CLASS_PLAYLIST_SONGS) the songs of playlist classinfo[1] in *pdeq_showlist (@0x4ee744). The stock Playlists page opens a playlist (the
 * shared row handler @0x53d300, mode 0): the playlist's name into nagvation_title (snprintf "%s", 0x200 @0x53d5b8), its REC_DISC into
 * classinfo[1] (@0x53d5f4), navigator_to_with_context("allmusic_page", 0xff13). PL_MAX: ids 1..100. */
#define CLASS_PLAYLISTS 0xf00b
#define CLASS_PLAYLIST_SONGS 0xff13
#define PL_MAX 100
#define PL_SCAN 50             /* songs read per playlist for the mosaic: the first PL_SCAN, in order */
#define PL_TILES GRID_TILES
#define PL_MORE_MS 16
/* The "..." menu's card (tools/pod_ui.py builds it, patch/playlists.c pl_fit sizes it): PL_MENU_ROWS rows of PL_ROW_H filling it (Now Playing's
 * More sheet's 50 px rows, no padding), in each a 20 px glyph at PL_ICON_X and the label from PL_TEXT_X to PL_TEXT_R before the right edge. Its
 * right edge stays at PL_CARD_RIGHT under the button; its width is the language's widest label plus PL_TEXT_X + PL_TEXT_R, at least PL_CARD_MIN,
 * at most PL_CARD_MAX (the asset's: the widest of the 13 languages fits, test/pod/playlists.py). */
#define PL_MENU_ROWS 4
#define PL_CARD_RIGHT 314
#define PL_CARD_Y 44
#define PL_CARD_R 14
#define PL_ROW_H 50
#define PL_ICON_X 16
#define PL_TEXT_X 48
#define PL_TEXT_R 16
#define PL_CARD_MIN 180
#define PL_CARD_MAX 292
