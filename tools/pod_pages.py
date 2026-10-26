#!/usr/bin/env python3
"""Shared page/entry definitions for the M1 Pod payload.

One source of truth, consumed by both:
  tools/pod_ui.py   builds the ui/*.bin assets (widget trees)
  tools/pod.py      emits the C row/page tables into stock.h for patch/m1pod.c

Keeping the rows here means the asset a page shows and the action the payload takes on a tap can
never drift apart: the row's widget name, its label and its handler all come from one record.

Entry point: the payload hooks the Home screen's icon click dispatcher and intercepts exactly one
Home icon, HOME_ENTRY: the "M1 Pod" icon patch/home.c adds to the stock grid (id 99, which stock never
uses). Tapping it opens the entry page (PAGES[0]); the kill-switch file and every other icon (Tidal
included) fall through to stock behaviour.
"""

# Home item ids (must match patch/offsets.inc HOME_*). The entry icon and the destinations rows open.
HOME_MYMUSIC = 3     # allmusic_page 0xf001: all songs
HOME_FOLDER = 4
HOME_ALBUM = 5
HOME_GENRE = 7
HOME_PLAYLIST = 14
HOME_PLAYSET = 16
HOME_SYSSET = 17

HOME_ENTRY = 99   # the id of the added "M1 Pod" grid icon (no stock id; the dispatcher's table ends at 17)

# Row actions (mirror the enum in patch/m1pod.c).
ACT_HOME = 0     # open a stock Home destination through the stock dispatcher (arg = HOME_* id)
ACT_PAGE = 1     # open another M1 Pod page (arg = page index in PAGES)
ACT_PLAYER = 2   # go to Now Playing (stock on_backtoplayer_onclick)
ACT_COVER = 3    # open Cover Flow (patch/coverflow.c; its own page, built at runtime)
ACT_SHUFFLE = 4  # shuffle the library and play it (patch/shuffle.c; arg = SHUFFLE_*)
ACT_ARTISTS = 8  # open the Artists list (patch/artists.c; rows built at runtime from the stock query)
ACT_GRID = 9     # show the stock Shanling grid for this session (patch/home.c)
ACT_STARTUP = 10 # toggle the persistent "Start in: M1 Pod / Shanling" setting (patch/home.c)

# ACT_SHUFFLE arguments (mirror the enum in patch/shuffle.c)
SHUFFLE_SONGS = 0    # every song, stock Shuffle play mode, from a random song
SHUFFLE_ALBUMS = 1   # albums in random order, each album's tracks in order
SHUFFLE_FOLDERS = 2  # folders in random order, each folder's files in order


class Row:
    def __init__(self, label, action, arg=0):
        self.label, self.action, self.arg = label, action, arg


class Page:
    def __init__(self, key, name, title, rows=(), kind='rows'):
        self.key = key          # asset basename under ui/ (ui/<key>.bin) and window resource name
        self.name = name        # root widget name property
        self.title = title      # navbar title text
        self.rows = list(rows)
        self.kind = kind        # 'rows', 'cover' (Cover Flow's own layout) or 'list' (an empty stock
                                # list the payload fills, e.g. Artists)


# The M1 Pod menu, the Classic iPod main menu adapted to the 320x480 touch screen (q2-pod
# docs/ipod.md geometry): Shuffle is one row opening the Shuffle page, Artists opens the payload's
# Artists list, and the last row opens the Settings page (system and play settings, and the launcher:
# way back to the stock grid and the persistent start-up toggle whose label is rewritten at runtime).
SHUFFLE_PAGE_INDEX = 3   # its index in PAGES
SETTINGS_PAGE_INDEX = 4
MENU = Page('m1pod_menu', 'm1pod_menu_page', 'M1 Pod', rows=[
    Row('Now Playing', ACT_PLAYER),
    Row('Cover Flow', ACT_COVER),
    Row('Shuffle', ACT_PAGE, SHUFFLE_PAGE_INDEX),
    Row('Songs', ACT_HOME, HOME_MYMUSIC),
    Row('Albums', ACT_HOME, HOME_ALBUM),
    Row('Artists', ACT_ARTISTS),
    Row('Genres', ACT_HOME, HOME_GENRE),
    Row('Folders', ACT_HOME, HOME_FOLDER),
    Row('Playlists', ACT_HOME, HOME_PLAYLIST),
    Row('Settings', ACT_PAGE, SETTINGS_PAGE_INDEX),
])
# Cover Flow's own page (patch/coverflow.c fills it at runtime: the slide_menu of covers, the
# progress/cancel pair of the first-run cache build, and the album's track list).
COVER = Page('m1pod_cover', 'm1pod_cover_page', 'Cover Flow', kind='cover')
# Artists: the stock Artists query as stock-style rows; a tap opens Cover Flow on that artist's albums.
ARTISTS = Page('m1pod_artists', 'm1pod_artists_page', 'Artists', kind='list')
SHUFFLE_PAGE = Page('m1pod_shuffle', 'm1pod_shuffle_page', 'Shuffle', rows=[
    Row('Shuffle Songs', ACT_SHUFFLE, SHUFFLE_SONGS),
    Row('Shuffle Albums', ACT_SHUFFLE, SHUFFLE_ALBUMS),
    Row('Shuffle Folders', ACT_SHUFFLE, SHUFFLE_FOLDERS),
])

SETTINGS_PAGE = Page('m1pod_settings', 'm1pod_settings_page', 'Settings', rows=[
    Row('System Settings', ACT_HOME, HOME_SYSSET),
    Row('Play Settings', ACT_HOME, HOME_PLAYSET),
    Row('Shanling Home', ACT_GRID),
    Row('Start in: M1 Pod', ACT_STARTUP),
])

# PAGES[0] is the entry page.
PAGES = [MENU, COVER, ARTISTS, SHUFFLE_PAGE, SETTINGS_PAGE]
assert PAGES[SHUFFLE_PAGE_INDEX] is SHUFFLE_PAGE and PAGES[SETTINGS_PAGE_INDEX] is SETTINGS_PAGE
