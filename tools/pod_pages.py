#!/usr/bin/env python3
"""Shared page/entry definitions for the M1+ Pod payload.

One source of truth, consumed by both:
  tools/pod_ui.py   builds the ui/*.bin assets (widget trees)
  tools/pod.py      emits the C row/page tables into stock.h for patch/m1pod.c

Keeping the rows here means the asset a page shows and the action the payload takes on a tap can
never drift apart: the row's widget name, its label and its handler all come from one record.

Entry point: the payload hooks the Home screen's icon click dispatcher and intercepts exactly one
Home icon, HOME_ENTRY: the "M1+ Pod" icon patch/home.c adds to the stock grid (id 99, which stock never
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

HOME_ENTRY = 99   # the id of the added "M1+ Pod" grid icon (no stock id; the dispatcher's table ends at 17)

# Row actions (mirror the enum in patch/m1pod.c).
ACT_HOME = 0     # open a stock Home destination through the stock dispatcher (arg = HOME_* id)
ACT_PAGE = 1     # open another M1+ Pod page (arg = page index in PAGES)
ACT_PLAYER = 2   # go to Now Playing (stock on_backtoplayer_onclick)
ACT_COVER = 3    # open Cover Flow (patch/coverflow.c; its own page, built at runtime)
ACT_SHUFFLE = 4  # shuffle the library and play it (patch/shuffle.c; arg = SHUFFLE_*)
ACT_ARTISTS = 8  # open the Artists list (patch/artists.c; rows built at runtime from the stock query)
ACT_ALBUMS = 11  # open Albums in the last-used view: the grid (patch/albums.c) or the stock list
ACT_GRID = 9     # show the stock Shanling grid for this session (patch/home.c)
ACT_STARTUP = 10 # switch row: the persistent "Start in M1+ Pod" setting (patch/home.c)
ACT_LANDSCAPE = 12  # switch row: Cover Flow opens in landscape (patch/coverflow.c)
ACT_SORT = 13    # value row: the album order of Cover Flow and Albums, Artist or Album; a tap toggles (patch/covercache.c)
ACT_SHOT = 14    # the Screenshot row (Settings): a 5 s countdown, then the screen is written to /mnt/mmc/screenshots (patch/shot.c)
ACT_REBUILD = 15 # the Rebuild Covers row (Settings > Cover Flow): a confirm dialog, then Cover Flow rebuilds every cover (patch/m1pod.c, patch/coverflow.c)
ACT_SHELF = 16    # switch row: the Recently Played shelf on the Home menu (patch/recent.c)
ACT_PLAYLISTS = 17  # open the Playlists page: a grid of mosaics of each playlist's album covers (patch/playlists.c)
SWITCH_ACTIONS = (ACT_STARTUP, ACT_LANDSCAPE, ACT_SHELF)
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


# The M1+ Pod menu, the Classic iPod main menu adapted to the 320x480 touch screen (q2-pod
# docs/ipod.md geometry). Eighteen customisable items (the nine menu items, then the nine Extras tiles), then Extras
# and Settings, which are always shown, always last and not customisable. The asset holds every row in the default order (an item's id is its row
# index); patch/menu.c hides the items the user hid (they show at the top of the Extras page) and orders the
# rest, as the saved list in /mnt/data/m1pod-menu says. Shuffle opens the Shuffle page, Artists the payload's
# Artists list, Settings the Settings page (Main Menu, Cover Flow, Home Screen, Playback, System
# Settings).
SHUFFLE_PAGE_INDEX = 3   # its index in PAGES
SETTINGS_PAGE_INDEX = 4
EXTRAS_PAGE_INDEX = 5
MENUCFG_PAGE_INDEX = 7
CFSET_PAGE_INDEX = 8
HOMESET_PAGE_INDEX = 9
ITEMS = [   # item id = index; the default order, essentials first (iPod classic style)
    Row('Now Playing', ACT_PLAYER),
    Row('Cover Flow', ACT_COVER),
    Row('Albums', ACT_ALBUMS),
    Row('Artists', ACT_ARTISTS),
    Row('Songs', ACT_HOME, HOME_MYMUSIC),
    Row('Playlists', ACT_PLAYLISTS),
    Row('Shuffle', ACT_PAGE, SHUFFLE_PAGE_INDEX),
    Row('Genres', ACT_HOME, HOME_GENRE),
    Row('Folders', ACT_HOME, HOME_FOLDER),
    # The stock Home tiles the menu does not repeat (Songs, Albums, Artists, Genres, Folders and Playlists are items above,
    # Play/System Settings are on Settings; the HiFi Store, id 0, exists on the grid only in Simplified Chinese and is left
    # out). They are items too, hidden by default: Settings > Main Menu can show any of them in the menu.
    Row('Favorites', ACT_HOME, HOME_FAV),
    Row('Recently Added', ACT_HOME, HOME_RECENTADD),
    Row('Recently Played', ACT_HOME, HOME_RECENT),
    Row('Most Played', ACT_HOME, HOME_MOST),
    Row('Composers', ACT_HOME, HOME_COMPOSER),
    Row('Hi-Res', ACT_HOME, HOME_HIRES),
    Row('Update Library', ACT_HOME, HOME_UPDATE),
    Row('Tidal', ACT_HOME, HOME_TIDAL),
    Row('CD Ripper', ACT_HOME, HOME_CDRIPPER),
]
DEFAULT_MENU = [1, 2, 3, 4, 5, 6]   # the items shown by default, in order (saved string "123456x"): Cover Flow, Albums, Artists, Songs, Playlists, Shuffle. Now Playing is not
                                    # among them: the mini player bar of the Home instance opens it (docs/modules/minibar.md); it stays an item (Settings > Main Menu shows it, Extras lists it)
assert all(0 <= i < len(ITEMS) for i in DEFAULT_MENU) and len(set(DEFAULT_MENU)) == len(DEFAULT_MENU)
ID_CHARS = '012345678abcdefghi'   # the saved list's character for each item id: '0'..'8' the first nine, 'a'..'i' the nine Extras tiles
assert len(ID_CHARS) == len(ITEMS)
EXTRAS_CHAR = 'x'        # the Extras row of the menu: present = shown (right above Settings), absent = hidden. Only ever the last character of the list; not an item id (it is never reordered)
DEFAULT_EXTRAS = True    # the default saved string is "123456x"
MENU_FILE_MAX = 24       # patch/menu.c reads at most this many bytes of the saved list (a list of every item is 18 characters, the x and a newline); longer is invalid
MENU = Page('m1pod_menu', 'm1pod_menu_page', 'M1+ Pod', rows=ITEMS + [
    Row('Extras', ACT_PAGE, EXTRAS_PAGE_INDEX),
    Row('Settings', ACT_PAGE, SETTINGS_PAGE_INDEX),
])


def parse_menu_full(data):
    """(the visible items in menu order, Extras row shown) from the saved list (patch/menu.c mn_load's model), or the
    defaults. A line of item characters (ID_CHARS), no duplicate, every one known, then optionally EXTRAS_CHAR as the
    last character (before the newline), at most the file cap. A list without it hides Extras (an old "123456" file too)."""
    if isinstance(data, str): data = data.encode('latin-1')
    default = (list(DEFAULT_MENU), DEFAULT_EXTRAS)
    if data is None or not 0 < len(data) < MENU_FILE_MAX: return default
    body = data[:-1] if data.endswith(b'\n') else data
    extras = body.endswith(EXTRAS_CHAR.encode())
    if extras: body = body[:-1]
    if len(body) > len(ITEMS) or any(chr(c) not in ID_CHARS for c in body): return default
    ids = [ID_CHARS.index(chr(c)) for c in body]
    if len(set(ids)) != len(ids): return default
    return ids, extras


def parse_menu(data):
    """The visible items in menu order of the saved list (parse_menu_full without the Extras flag)."""
    return parse_menu_full(data)[0]


def format_menu(ids, extras):
    """The saved list for the shown items and the Extras flag, newline included (patch/menu.c mn_save)."""
    return ''.join(ID_CHARS[i] for i in ids) + (EXTRAS_CHAR if extras else '') + '\n'


# Cover Flow's own page (patch/coverflow.c fills it at runtime: the slide_menu of covers, the
# progress/cancel pair of the first-run cache build, and the album's track list).
COVER = Page('m1pod_cover', 'm1pod_cover_page', 'Cover Flow', kind='cover')
# Artists: the stock Artists query as stock-style rows; a tap opens Cover Flow on that artist's albums.
ARTISTS = Page('m1pod_artists', 'm1pod_artists_page', 'Artists', kind='list')
# Albums: the grid of covers or the list (patch/albums.c draws both in one custom view); the navbar button switches the mode.
ALBUMS = Page('m1pod_albums', 'm1pod_albums_page', 'Albums', kind='grid')
# Playlists: the stock playlists as a grid, each a mosaic of its albums' covers (patch/playlists.c); the "..." button opens the popup menu.
PLAYLISTS = Page('m1pod_playlists', 'm1pod_playlists_page', 'Playlists', kind='playlists')
# The popup menu's rows (tools/pod_ui.py builds them as the buttons pl_item0 ..; patch/playlists.c binds them by that order): New, Import, Export
# are the stock keys of the stock Playlists page's rows; Delete opens that page, whose multi-select button deletes.
PLAYLIST_MENU = ('New playlist', 'Import playlist', 'Export playlist', 'Delete Playlists')
SHUFFLE_PAGE = Page('m1pod_shuffle', 'm1pod_shuffle_page', 'Shuffle', rows=[
    Row('Shuffle Songs', ACT_SHUFFLE, SHUFFLE_SONGS),
    Row('Shuffle Albums', ACT_SHUFFLE, SHUFFLE_ALBUMS),
    Row('Shuffle Folders', ACT_SHUFFLE, SHUFFLE_FOLDERS),
])

# Settings: Main Menu (the customise page), Cover Flow and Home Screen (their own sub-pages, below) and the
# stock settings pages.
SETTINGS_PAGE = Page('m1pod_settings', 'm1pod_settings_page', 'Settings', rows=[
    Row('Main Menu', ACT_PAGE, MENUCFG_PAGE_INDEX),
    Row('Cover Flow', ACT_PAGE, CFSET_PAGE_INDEX),
    Row('Home Screen', ACT_PAGE, HOMESET_PAGE_INDEX),
    Row('Playback', ACT_HOME, HOME_PLAYSET),
    Row('System Settings', ACT_HOME, HOME_SYSSET),
    Row('Screenshot', ACT_SHOT),    # a developer's tool, last: a 5 s countdown, then the screen is written to the card (patch/shot.c)
])

# Settings > Home Screen: the Start in M1+ Pod switch (patch/home.c) and Shanling Home, the way out to the grid.
HOMESET_PAGE = Page('m1pod_homeset', 'm1pod_homeset_page', 'Home Screen', rows=[
    Row('Start in M1+ Pod', ACT_STARTUP),
    Row('Recent Albums', ACT_SHELF),
    Row('Shanling Home', ACT_GRID),
])

# Main Menu: the customise page (patch/menu.c builds its behaviour at run time): one row per item with a
# show / hide switch (the row's own tap too) and, on the shown ones, an up arrow that moves it one place up.
MENUCFG_PAGE = Page('m1pod_mainmenu', 'm1pod_mainmenu_page', 'Main Menu', kind='menucfg')

# Extras (iPod style): every item the menu does not show (the asset has a row for each item, in id order, same index as
# the menu's; patch/menu.c hides the ones the menu shows and stacks the rest in EXTRAS_ORDER, the same for every language):
# the default menu items when hidden, then the Library group, then the Tools group, each alphabetical by the English label.
EXTRAS_GROUPS = (
    ('Albums', 'Artists', 'Cover Flow', 'Now Playing', 'Playlists', 'Shuffle', 'Songs'),
    ('Composers', 'Favorites', 'Folders', 'Genres', 'Hi-Res', 'Most Played', 'Recently Added', 'Recently Played'),
    ('CD Ripper', 'Tidal', 'Update Library'),
)
EXTRAS_ORDER = [[r.label for r in ITEMS].index(label) for group in EXTRAS_GROUPS for label in group]   # item ids
assert sorted(EXTRAS_ORDER) == list(range(len(ITEMS))) and all(list(g) == sorted(g) for g in EXTRAS_GROUPS)
EXTRAS_PAGE = Page('m1pod_extras', 'm1pod_extras_page', 'Extras', rows=[Row(r.label, r.action, r.arg) for r in ITEMS])

# Settings > Cover Flow: the landscape switch, the album order and Rebuild Covers. Sort shows its value (Artist or Album) at
# the right and a tap flips it; the same order is used by the Cover Flow page and the Albums page. Rebuild Covers asks
# (the stock confirm dialog) and then opens Cover Flow on its Preparing screen with every cover extracted again.
CFSET_PAGE = Page('m1pod_cfset', 'm1pod_cfset_page', 'Cover Flow', rows=[
    Row('Landscape', ACT_LANDSCAPE),
    Row('Sort', ACT_SORT),
    Row('Rebuild Covers', ACT_REBUILD),
])
SORT_VALUES = ('Artist', 'Album')    # the value shown for the setting's two states (the default, Artist, first)

# PAGES[0] is the entry page.
PAGES = [MENU, COVER, ARTISTS, SHUFFLE_PAGE, SETTINGS_PAGE, EXTRAS_PAGE, ALBUMS, MENUCFG_PAGE, CFSET_PAGE, HOMESET_PAGE, PLAYLISTS]
assert PAGES[SHUFFLE_PAGE_INDEX] is SHUFFLE_PAGE and PAGES[SETTINGS_PAGE_INDEX] is SETTINGS_PAGE
assert PAGES[EXTRAS_PAGE_INDEX] is EXTRAS_PAGE and PAGES[MENUCFG_PAGE_INDEX] is MENUCFG_PAGE
assert PAGES[CFSET_PAGE_INDEX] is CFSET_PAGE and PAGES[HOMESET_PAGE_INDEX] is HOMESET_PAGE
