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
HOME_TIDAL = 1
HOME_UPDATE = 2      # systemset/updatemusic_page: Update Library
HOME_MYMUSIC = 3     # allmusic_page 0xf001: all songs
HOME_FOLDER = 4
HOME_GENRE = 7
HOME_COMPOSER = 8
HOME_HIRES = 9
HOME_FAV = 10
HOME_MOST = 11
HOME_RECENT = 12
HOME_RECENTADD = 13
HOME_PLAYLIST = 14
HOME_CDRIPPER = 15
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
ACT_ALBUMS = 11  # open Albums in the last-used view: the grid (patch/albums.c) or the stock list
ACT_GRID = 9     # show the stock Shanling grid for this session (patch/home.c)
ACT_STARTUP = 10 # switch row: the persistent "Start in M1 Pod" setting (patch/home.c)
ACT_LANDSCAPE = 12  # switch row: Cover Flow opens in landscape (patch/coverflow.c)
ACT_SORT = 13    # value row: the album order of Cover Flow and Albums, Artist or Album; a tap toggles (patch/covercache.c)
SWITCH_ACTIONS = (ACT_STARTUP, ACT_LANDSCAPE)
VALUE_ACTIONS = (ACT_SORT,)    # rows with a grey value at the right (the widget pod_value<row>)

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
        self.kind = kind        # 'rows', 'cover' (Cover Flow's own layout), 'list' (an empty stock
                                # list the payload fills, e.g. Artists) or 'grid' (the Albums grid)


# The M1 Pod menu, the Classic iPod main menu adapted to the 320x480 touch screen (q2-pod
# docs/ipod.md geometry). Nine customisable items, then Extras and Settings, which are always shown, always
# last and not customisable. The asset holds every row in the default order (an item's id is its row
# index); patch/menu.c hides the items the user hid (they show at the top of the Extras page) and orders the
# rest, as the saved list in /mnt/data/m1pod-menu says. Shuffle opens the Shuffle page, Artists the payload's
# Artists list, Settings the Settings page (Main Menu, Cover Flow, Start in M1 Pod, Playback, System
# Settings, Shanling Home).
SHUFFLE_PAGE_INDEX = 3   # its index in PAGES
SETTINGS_PAGE_INDEX = 4
EXTRAS_PAGE_INDEX = 5
MENUCFG_PAGE_INDEX = 7
CFSET_PAGE_INDEX = 8
ITEMS = [   # item id = index; the default order, essentials first (iPod classic style)
    Row('Now Playing', ACT_PLAYER),
    Row('Cover Flow', ACT_COVER),
    Row('Albums', ACT_ALBUMS),
    Row('Artists', ACT_ARTISTS),
    Row('Songs', ACT_HOME, HOME_MYMUSIC),
    Row('Playlists', ACT_HOME, HOME_PLAYLIST),
    Row('Shuffle', ACT_PAGE, SHUFFLE_PAGE_INDEX),
    Row('Genres', ACT_HOME, HOME_GENRE),
    Row('Folders', ACT_HOME, HOME_FOLDER),
]
DEFAULT_VISIBLE = 7      # the first seven items show by default; Genres and Folders are in Extras
MENU_FILE_MAX = 16       # patch/menu.c reads at most this many bytes of the saved list; longer is invalid
MENU = Page('m1pod_menu', 'm1pod_menu_page', 'M1 Pod', rows=ITEMS + [
    Row('Extras', ACT_PAGE, EXTRAS_PAGE_INDEX),
    Row('Settings', ACT_PAGE, SETTINGS_PAGE_INDEX),
])


def parse_menu(data):
    """The visible items in menu order from the saved list (patch/menu.c mn_parse's model), or the
    defaults. A line of item ids, one digit each, no duplicate, every id known, at most the file cap."""
    if isinstance(data, str): data = data.encode('latin-1')
    default = list(range(DEFAULT_VISIBLE))
    if data is None or not 0 < len(data) < MENU_FILE_MAX: return default
    body = data[:-1] if data.endswith(b'\n') else data
    ids = [c - 48 for c in body]
    if len(ids) > len(ITEMS) or any(not 0 <= i < len(ITEMS) for i in ids) or len(set(ids)) != len(ids): return default
    return ids
# Cover Flow's own page (patch/coverflow.c fills it at runtime: the slide_menu of covers, the
# progress/cancel pair of the first-run cache build, and the album's track list).
COVER = Page('m1pod_cover', 'm1pod_cover_page', 'Cover Flow', kind='cover')
# Artists: the stock Artists query as stock-style rows; a tap opens Cover Flow on that artist's albums.
ARTISTS = Page('m1pod_artists', 'm1pod_artists_page', 'Artists', kind='list')
# Albums: the grid of covers (patch/albums.c draws it in one custom view); the navbar button switches to the
# stock Albums list, whose own navbar gets the same button at runtime.
ALBUMS = Page('m1pod_albums', 'm1pod_albums_page', 'Albums', kind='grid')
SHUFFLE_PAGE = Page('m1pod_shuffle', 'm1pod_shuffle_page', 'Shuffle', rows=[
    Row('Shuffle Songs', ACT_SHUFFLE, SHUFFLE_SONGS),
    Row('Shuffle Albums', ACT_SHUFFLE, SHUFFLE_ALBUMS),
    Row('Shuffle Folders', ACT_SHUFFLE, SHUFFLE_FOLDERS),
])

# Settings: Main Menu (the customise page), Cover Flow (its own sub-page, below), the Start in M1 Pod switch
# (patch/home.c) and the stock settings pages; Shanling Home is the way out to the grid.
SETTINGS_PAGE = Page('m1pod_settings', 'm1pod_settings_page', 'Settings', rows=[
    Row('Main Menu', ACT_PAGE, MENUCFG_PAGE_INDEX),
    Row('Cover Flow', ACT_PAGE, CFSET_PAGE_INDEX),
    Row('Start in M1 Pod', ACT_STARTUP),
    Row('Playback', ACT_HOME, HOME_PLAYSET),
    Row('System Settings', ACT_HOME, HOME_SYSSET),
    Row('Shanling Home', ACT_GRID),
])

# Main Menu: the customise page (patch/menu.c builds its behaviour at run time): one row per item with a
# show / hide switch (the row's own tap too) and, on the shown ones, an up arrow that moves it one place up.
MENUCFG_PAGE = Page('m1pod_mainmenu', 'm1pod_mainmenu_page', 'Main Menu', kind='menucfg')

# Extras (iPod style): first the menu items the user hid (the asset has a row for each item, patch/menu.c shows
# the hidden ones), then the stock Home tiles the menu does not repeat (ids 1, 2, 8-13, 15; Songs, Albums,
# Artists, Genres, Folders and Playlists are menu items, Play/System Settings are on Settings). The HiFi
# Store (id 0) exists on the grid only in Simplified Chinese and is left out.
EXTRAS_PAGE = Page('m1pod_extras', 'm1pod_extras_page', 'Extras', rows=[Row(r.label, r.action, r.arg) for r in ITEMS] + [
    Row('Favorites', ACT_HOME, HOME_FAV),
    Row('Recently Added', ACT_HOME, HOME_RECENTADD),
    Row('Recently Played', ACT_HOME, HOME_RECENT),
    Row('Most Played', ACT_HOME, HOME_MOST),
    Row('Composers', ACT_HOME, HOME_COMPOSER),
    Row('Hi-Res', ACT_HOME, HOME_HIRES),
    Row('Update Library', ACT_HOME, HOME_UPDATE),
    Row('Tidal', ACT_HOME, HOME_TIDAL),
    Row('CD Ripper', ACT_HOME, HOME_CDRIPPER),
])

# Settings > Cover Flow: the landscape switch and the album order. Sort shows its value (Artist or Album) at the
# right and a tap flips it; the same order is used by the Cover Flow page and the Albums page.
CFSET_PAGE = Page('m1pod_cfset', 'm1pod_cfset_page', 'Cover Flow', rows=[
    Row('Landscape', ACT_LANDSCAPE),
    Row('Sort', ACT_SORT),
])
SORT_VALUES = ('Artist', 'Album')    # the value shown for the setting's two states (the default, Artist, first)

# PAGES[0] is the entry page.
PAGES = [MENU, COVER, ARTISTS, SHUFFLE_PAGE, SETTINGS_PAGE, EXTRAS_PAGE, ALBUMS, MENUCFG_PAGE, CFSET_PAGE]
assert PAGES[SHUFFLE_PAGE_INDEX] is SHUFFLE_PAGE and PAGES[SETTINGS_PAGE_INDEX] is SETTINGS_PAGE
assert PAGES[EXTRAS_PAGE_INDEX] is EXTRAS_PAGE and PAGES[MENUCFG_PAGE_INDEX] is MENUCFG_PAGE
assert PAGES[CFSET_PAGE_INDEX] is CFSET_PAGE
