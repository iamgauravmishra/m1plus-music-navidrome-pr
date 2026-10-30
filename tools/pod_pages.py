#!/usr/bin/env python3
"""Shared page/entry definitions for the M1+ Music payload.

One source of truth, consumed by both:
  tools/pod_ui.py   builds the ui/*.bin assets (widget trees)
  tools/pod.py      emits the C row/page tables into stock.h for patch/m1plus.c

Keeping the rows here means the asset a page shows and the action the payload takes on a tap can
never drift apart: the row's widget name, its label and its handler all come from one record.

Entry point: the payload hooks the Home screen's icon click dispatcher and intercepts exactly one
Home icon, HOME_ENTRY: the "M1+ Music" icon patch/home.c adds to the stock grid (id 99, which stock never
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

HOME_ENTRY = 99   # the id of the added "M1+ Music" grid icon (no stock id; the dispatcher's table ends at 17)

# Row actions (mirror the enum in patch/m1plus.c).
ACT_HOME = 0     # open a stock Home destination through the stock dispatcher (arg = HOME_* id)
ACT_PAGE = 1     # open another M1+ Music page (arg = page index in PAGES)
ACT_PLAYER = 2   # go to Now Playing (stock on_backtoplayer_onclick)
ACT_COVER = 3    # open Cover Flow (patch/coverflow.c; its own page, built at runtime)
ACT_SHUFFLE = 4  # shuffle the library and play it (patch/shuffle.c; arg = SHUFFLE_*)
ACT_ARTISTS = 8  # open the Artists list (patch/artists.c; rows built at runtime from the stock query); arg 0 Artists, HOME_GENRE / HOME_COMPOSER: Genres / Composers on the same page
ACT_ALBUMS = 11  # open Albums in the last-used view: the grid (patch/albums.c) or the stock list
ACT_GRID = 9     # show the stock Shanling grid for this session (patch/home.c)
ACT_STARTUP = 10 # switch row: the persistent "Boot to M1+ Music" setting (patch/home.c)
ACT_LANDSCAPE = 12  # switch row: Cover Flow opens in landscape (patch/coverflow.c)
ACT_SORT = 13    # value row: the album order of Cover Flow and Albums, Artist or Album; a tap toggles (patch/covercache.c)
ACT_SHOT = 14    # the Screenshot row (Settings): a 5 s countdown, then the screen is written to /mnt/mmc/screenshots (patch/shot.c)
ACT_REBUILD = 15 # the Rebuild Covers row (Settings > Cover Flow): a confirm dialog, then Cover Flow rebuilds every cover (patch/m1plus.c, patch/coverflow.c)
ACT_SHELF = 16    # switch row: the Recently Played shelf on the Home menu (patch/recent.c)
ACT_PLAYLISTS = 17  # open the Playlists page: a grid of mosaics of each playlist's album covers (patch/playlists.c)
ACT_SONGS = 18      # open the Songs page: the library as one list with a large title, sections and a jump rail (patch/songs.c)
ACT_DAILY = 19   # switch row: the Daily Mix card on the Home menu (patch/dailymix.c)
ACT_REGEN = 20   # action row (no chevron, like the Shuffle rows): make today's Daily Mix again with a new seed (patch/dailymix.c)
ACT_LIST = 21    # open a stock song list on the Songs page (patch/songs.c songs_open_list; arg = its HOME_* tile, where a window that will not open falls back)
ACT_IPOD = 22    # open the Pod, the virtual iPod Classic page: a fullscreen window with a touch click wheel (patch/ipod.c ipod_open)
ACT_PODCASTS = 23   # open the Podcasts page: the shows in /mnt/mmc/Podcasts and their episodes (patch/podcasts.c podcasts_open)
ACT_NETPROBE = 25 # the Network Probe row (Developer): a thread checks HTTPS, Wi-Fi, the clock, RAM and the screen-off soak, and logs to /mnt/mmc/m1plus-probe.log (patch/probe.c)
ACT_CTHEME = 24  # value row: the Cassette Mode page's theme, Normal, Chrome or Metal; a tap cycles it (patch/tape.c tape_theme_cycle)
SWITCH_ACTIONS = (ACT_STARTUP, ACT_LANDSCAPE, ACT_SHELF, ACT_DAILY)
NO_CHEVRON_ACTIONS = (ACT_PLAYER, ACT_SHUFFLE, ACT_REGEN)   # rows that play or act in place (a switch or a value row has none either)
VALUE_ACTIONS = (ACT_SORT, ACT_CTHEME)    # rows with a grey value at the right (the widget pod_value<row>)
VALUE_INIT = {ACT_SORT: 'Artist', ACT_CTHEME: 'Normal'}   # what the asset's value label says before the payload sets it

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
        self.kind = kind        # 'rows', 'cover' (Cover Flow's own layout), 'artists' (the A-Z list page the payload
                                # fills: Artists, Genres, Composers) or 'grid' (the Albums grid)


# The M1+ Music menu, the Classic iPod main menu adapted to the 320x480 touch screen (q2-pod
# docs/ipod.md geometry). Nineteen customisable items (the nine menu items, the nine Extras tiles and Customize), then Extras,
# which is always shown, always last and not customisable. The asset holds every row in the default order (an item's id is its row
# index); patch/menu.c hides the items the user hid (the Extras page lists them unless the user turned them off there) and orders the
# rest, as the saved list in /mnt/data/m1plus-menu says. Shuffle opens the Shuffle page, Artists the payload's
# Artists list, Customize the Customize page (Main Menu, Extras, Home Screen, Cover Flow, Playback, System Settings,
# Developer). Customize is hidden from the menu by default like Shuffle; it then shows on the Extras page (Tools), where it can never be turned off.
SHUFFLE_PAGE_INDEX = 3   # its index in PAGES
CUSTOMIZE_PAGE_INDEX = 4
EXTRAS_PAGE_INDEX = 5
MENUCFG_PAGE_INDEX = 7
CFSET_PAGE_INDEX = 8
CASSETTE_PAGE_INDEX = 18
HOMESET_PAGE_INDEX = 9
EXTRASCFG_PAGE_INDEX = 13
DEVELOPER_PAGE_INDEX = 14
ITEMS = [   # item id = index; the default order, essentials first (iPod classic style)
    Row('Now Playing', ACT_PLAYER),
    Row('Cover Flow', ACT_COVER),
    Row('Albums', ACT_ALBUMS),
    Row('Artists', ACT_ARTISTS),
    Row('Songs', ACT_SONGS),
    Row('Playlists', ACT_PLAYLISTS),
    Row('Shuffle', ACT_PAGE, SHUFFLE_PAGE_INDEX),
    Row('Genres', ACT_ARTISTS, HOME_GENRE),
    Row('Folders', ACT_HOME, HOME_FOLDER),
    # The stock Home tiles the menu does not repeat (Songs, Albums, Artists, Genres, Folders and Playlists are items above,
    # Play/System Settings are on Customize; the HiFi Store, id 0, exists on the grid only in Simplified Chinese and is left
    # out). They are items too, hidden by default: Customize > Main Menu can show any of them in the menu. The five song lists (Favorites, Recently Added,
    # Recently Played, Most Played, Hi-Res) open on our Songs page (ACT_LIST, docs/modules/songs.md "The other lists"), the rest their stock page.
    Row('Favorites', ACT_LIST, HOME_FAV),
    Row('Recently Added', ACT_LIST, HOME_RECENTADD),
    Row('Recently Played', ACT_LIST, HOME_RECENT),
    Row('Most Played', ACT_LIST, HOME_MOST),
    Row('Composers', ACT_ARTISTS, HOME_COMPOSER),
    Row('Hi-Res', ACT_LIST, HOME_HIRES),
    Row('Update Library', ACT_HOME, HOME_UPDATE),
    Row('Tidal', ACT_HOME, HOME_TIDAL),
    Row('CD Ripper', ACT_HOME, HOME_CDRIPPER),
    # The Customize page (was the always-shown Settings row): an item like the others, hidden from the menu by default (a Tool on Extras).
    Row('Customize', ACT_PAGE, CUSTOMIZE_PAGE_INDEX),
    # The Pod, the virtual iPod Classic (docs/modules/ipod.md): an item like the rest, hidden from the menu by default (on Extras, in Play).
    Row('Pod', ACT_IPOD),
    # Podcasts (docs/modules/podcasts.md): the shows on the card and their episodes; an item like the rest, hidden from the menu by default (on Extras, in Play).
    Row('Podcasts', ACT_PODCASTS),
]
CUSTOMIZE_ID = 18
assert ITEMS[CUSTOMIZE_ID].label == 'Customize'
DEFAULT_MENU = [1, 2, 3, 4, 5]   # the items shown by default, in order (saved string "12345"): Cover Flow, Albums, Artists, Songs, Playlists, then Extras. A minimal menu: Now Playing is not
                                    # among them (the mini player bar of the Home instance opens it, docs/modules/minibar.md), nor are Shuffle and Customize; every other item is on the Extras page,
                                    # grouped (EXTRAS_GROUPS), and Customize > Main Menu can show any of them
assert all(0 <= i < len(ITEMS) for i in DEFAULT_MENU) and len(set(DEFAULT_MENU)) == len(DEFAULT_MENU)
ID_CHARS = '012345678abcdefghijkl'   # the saved list's character for each item id: '0'..'8' the first nine, 'a'..'i' the nine Extras tiles, 'j' Customize, 'k' the Pod, 'l' Podcasts
assert len(ID_CHARS) == len(ITEMS)
OFF_CHAR = '-'           # the saved list's separator: the item characters after it are turned off (not listed on the Extras page); at most once
DEFAULT_OFF = []         # no item is turned off by default
MENU_FILE_MAX = 24       # patch/menu.c reads at most this many bytes of the saved list (21 item characters at most in both parts together, the '-' and a newline); longer is invalid
MENU = Page('m1plus_menu', 'm1plus_menu_page', 'M1+ Music', rows=ITEMS + [
    Row('Extras', ACT_PAGE, EXTRAS_PAGE_INDEX),   # always shown, always last
])


def parse_menu_full(data):
    """(the visible items in menu order, the items turned off) from the saved list (patch/menu.c mn_load's model), or the
    defaults. A line of item characters (ID_CHARS), then optionally OFF_CHAR and more item characters (the items the
    Extras page leaves out), then an optional newline, shorter than the file cap. Invalid, giving the default
    ([DEFAULT_MENU], []): an unknown character, an id twice (in either part or across them), a second OFF_CHAR, or
    Customize (CUSTOMIZE_ID) after it (it can never be turned off: it must stay reachable)."""
    if isinstance(data, str): data = data.encode('latin-1')
    default = (list(DEFAULT_MENU), list(DEFAULT_OFF))
    if data is None or not 0 < len(data) < MENU_FILE_MAX: return default
    body = (data[:-1] if data.endswith(b'\n') else data).decode('latin-1')
    shown, sep, off = body.partition(OFF_CHAR)
    if OFF_CHAR in off or any(c not in ID_CHARS for c in shown + off): return default
    ids, offs = [ID_CHARS.index(c) for c in shown], [ID_CHARS.index(c) for c in off]
    if len(set(ids + offs)) != len(ids) + len(offs) or CUSTOMIZE_ID in offs: return default
    return ids, offs


def parse_menu(data):
    """The visible items in menu order of the saved list (parse_menu_full without the turned-off items)."""
    return parse_menu_full(data)[0]


def format_menu(ids, off=()):
    """The saved list for the shown items and the turned-off ones, newline included (patch/menu.c mn_save). No OFF_CHAR
    when nothing is off; the off items in the Extras order (EXTRAS_ORDER)."""
    off = [i for i in EXTRAS_ORDER if i in off]
    return ''.join(ID_CHARS[i] for i in ids) + (OFF_CHAR + ''.join(ID_CHARS[i] for i in off) if off else '') + '\n'


# Cover Flow's own page (patch/coverflow.c fills it at runtime: the slide_menu of covers, the
# progress/cancel pair of the first-run cache build, and the album's track list).
COVER = Page('m1plus_cover', 'm1plus_cover_page', 'Cover Flow', kind='cover')
# Artists: the stock Artists query as an A-Z list in the Songs page's manner; a tap opens Cover Flow on that artist's albums.
ARTISTS = Page('m1plus_artists', 'm1plus_artists_page', 'Artists', kind='artists')
# Albums: the grid of covers or the list (patch/albums.c draws both in one custom view); the navbar button switches the mode.
ALBUMS = Page('m1plus_albums', 'm1plus_albums_page', 'Albums', kind='grid')
# Playlists: the stock playlists as a grid, each a mosaic of its albums' covers (patch/playlists.c); the "..." button opens the popup menu.
PLAYLISTS = Page('m1plus_playlists', 'm1plus_playlists_page', 'Playlists', kind='playlists')
# The popup menu's rows (tools/pod_ui.py builds them as the buttons pl_item0 ..; patch/playlists.c binds them by that order): New, Import, Export
# are the stock keys of the stock Playlists page's rows; Delete opens that page, whose multi-select button deletes.
PLAYLIST_MENU = ('New playlist', 'Import playlist', 'Export playlist', 'Delete Playlists')
# Songs: the library as one list (patch/songs.c): a large title, Play / Shuffle pills, sections with a pinned header and the A-Z rail (Title order), the navbar's
# Search / Sort / Select buttons. The sort card's rows are the stock sort dialog's labels (tools/pod_ui.py builds them as sg_item0 ..; the order is the stock
# sort_flag 0..4, patch/songs.c writes the flag the way the stock dialog's row handler does).
SONGS = Page('m1plus_songs', 'm1plus_songs_page', 'Songs', kind='songs')
SORT_MENU = ('sort_alphabet', 'sort_filename', 'sort_format', 'sort_time_desc', 'sort_time_asc')   # the stock keys of sort_flag 0..4
SHUFFLE_PAGE = Page('m1plus_shuffle', 'm1plus_shuffle_page', 'Shuffle', rows=[
    Row('Shuffle Songs', ACT_SHUFFLE, SHUFFLE_SONGS),
    Row('Shuffle Albums', ACT_SHUFFLE, SHUFFLE_ALBUMS),
    Row('Shuffle Folders', ACT_SHUFFLE, SHUFFLE_FOLDERS),
])

# Customize (M1+ Music's own settings; System Settings is the stock one): the menu's two pages (Main Menu, Extras), the Home
# Screen and Cover Flow sub-pages (below), the stock Playback and System Settings pages, and Developer (Screenshot).
CUSTOMIZE_PAGE = Page('m1plus_customize', 'm1plus_customize_page', 'Customize', rows=[
    Row('Main Menu', ACT_PAGE, MENUCFG_PAGE_INDEX),
    Row('Extras', ACT_PAGE, EXTRASCFG_PAGE_INDEX),
    Row('Home Screen', ACT_PAGE, HOMESET_PAGE_INDEX),
    Row('Cover Flow', ACT_PAGE, CFSET_PAGE_INDEX),
    Row('Cassette Mode', ACT_PAGE, CASSETTE_PAGE_INDEX),
    Row('Playback', ACT_HOME, HOME_PLAYSET),
    Row('System Settings', ACT_HOME, HOME_SYSSET),
    Row('Developer', ACT_PAGE, DEVELOPER_PAGE_INDEX),
])

# Customize > Developer: the developer's tools. Screenshot: a confirm dialog, then a 5 s countdown (cancellable), then the screen
# is written to the card (patch/shot.c). Network Probe: a confirm dialog, then one worker thread logs what the network stack can do to the card (patch/probe.c).
DEVELOPER_PAGE = Page('m1plus_developer', 'm1plus_developer_page', 'Developer', rows=[
    Row('Screenshot', ACT_SHOT),
    Row('Network Probe', ACT_NETPROBE),
])

# Customize > Home Screen: the Boot to M1+ Music switch (patch/home.c), the Recent Albums and Daily Mix switches (the shelf and the card of the Home menu), Regenerate
# Daily Mix and Shanling Home, the way out to the grid.
HOMESET_PAGE = Page('m1plus_homeset', 'm1plus_homeset_page', 'Home Screen', rows=[
    Row('Boot to M1+ Music', ACT_STARTUP),
    Row('Recent Albums', ACT_SHELF),
    Row('Daily Mix', ACT_DAILY),
    Row('Regenerate Daily Mix', ACT_REGEN),
    Row('Shanling Home', ACT_GRID),
])

# Main Menu: the customise page (patch/menu.c builds its behaviour at run time): one row per item with a
# show / hide switch (the row's own tap too) and, on the shown ones, an up arrow that moves it one place up.
MENUCFG_PAGE = Page('m1plus_mainmenu', 'm1plus_mainmenu_page', 'Main Menu', kind='menucfg')

# Extras (iPod style): every item the menu does not show and the user did not turn off (the asset has a row for each item, in id
# order, same index as the menu's; patch/menu.c hides the ones the menu shows or that are off and stacks the rest in EXTRAS_ORDER,
# the same for every language). The items are in four titled groups, in a deliberate order (not alphabetical; the title is the
# group's section header, a non-interactive caption, shown while the group has a row on the page): what plays, the library's
# views, the song collections, the tools. Customize is in none: it is the Extras page's navbar button.
EXTRAS_GROUPS = (
    ('Play', ('Now Playing', 'Shuffle', 'Pod')),
    ('Library', ('Albums', 'Artists', 'Songs', 'Playlists', 'Cover Flow', 'Genres', 'Composers', 'Folders', 'Podcasts')),
    ('Collections', ('Favorites', 'Recently Played', 'Recently Added', 'Most Played', 'Hi-Res')),
    ('Tools', ('Update Library', 'CD Ripper', 'Tidal')),
)
_LABELS = [r.label for r in ITEMS]
# Customize is in no group and is never listed: the Extras page's navbar has a Customize button instead (the asset keeps its row for the
# index, hidden by the payload), and Customize > Extras has no row for it. Its id ends EXTRAS_ORDER, and its group is the sentinel len(EXTRAS_GROUPS).
EXTRAS_ORDER = [_LABELS.index(label) for _, group in EXTRAS_GROUPS for label in group] + [CUSTOMIZE_ID]   # item ids, the flattened groups, then Customize
EXTRAS_GROUP_OF = [next((g for g, (_, labels) in enumerate(EXTRAS_GROUPS) if label in labels), len(EXTRAS_GROUPS)) for label in _LABELS]   # item id -> its group (Customize: none)
EXTRAS_TITLES = [title for title, _ in EXTRAS_GROUPS]
assert sorted(EXTRAS_ORDER) == list(range(len(ITEMS))) and len(set(EXTRAS_TITLES)) == len(EXTRAS_GROUPS)
HDR_H = 40         # the section header's strip: shorter than a row (patch/menu.c puts it above the group's first row)


def extras_display(ids, off=(), cfg=False):
    """The Extras page's children as patch/menu.c stacks them for the saved list (shown item ids `ids`, turned-off ids `off`):
    [('hdr', group)] and [('row', item id)] in display order, then the hidden ones last (the hidden headers in group order, then the hidden rows in
    EXTRAS_ORDER). A row is shown when the menu does not show the item and (Extras) the list did not turn it off, or (cfg: Customize > Extras, which
    has no row for Customize) whatever the list says about it off; Customize is never listed (on Extras its row is hidden: the navbar has its button); a header is shown only while its group has a shown row, right above it.
    Returns (shown, hidden)."""
    listed = (lambda i: i != CUSTOMIZE_ID and i not in ids) if cfg else (lambda i: i != CUSTOMIZE_ID and i not in ids and i not in off)
    shown, hidden = [], []
    for g in range(len(EXTRAS_GROUPS)):
        rows = [i for i in EXTRAS_ORDER if EXTRAS_GROUP_OF[i] == g and listed(i)]
        if rows: shown += [('hdr', g)] + [('row', i) for i in rows]
        else: hidden.append(('hdr', g))
    hidden += [('row', i) for i in EXTRAS_ORDER if not listed(i) and not (cfg and i == CUSTOMIZE_ID)]
    return shown, hidden


def extras_layout(shown, row_h):
    """([(kind, key, y)], the list's height): the y of each shown child of extras_display, a header HDR_H high and a row row_h high, from 0."""
    out, y = [], 0
    for kind, key in shown:
        out.append((kind, key, y))
        y += HDR_H if kind == 'hdr' else row_h
    return out, y


EXTRAS_PAGE = Page('m1plus_extras', 'm1plus_extras_page', 'Extras', rows=[Row(r.label, r.action, r.arg) for r in ITEMS])

# Customize > Extras: which of the items the menu does not show the Extras page lists (patch/menu.c builds its behaviour at run time).
# A switch row (the whole row toggles) per item but Customize, in id order like the Extras page's asset; the payload shows only the
# items the menu does not show, stacked in EXTRAS_ORDER. Off = left out of Extras (the saved list's part after OFF_CHAR); showing
# an item in the menu (Main Menu) turns it on again, so an item hidden from the menu later is back on Extras.
EXTRASCFG_PAGE = Page('m1plus_extrascfg', 'm1plus_extrascfg_page', 'Extras', kind='extrascfg')

# Settings > Cover Flow: the landscape switch, the album order and Rebuild Covers. Sort shows its value (Artist or Album) at
# the right and a tap flips it; the same order is used by the Cover Flow page and the Albums page. Rebuild Covers asks
# (the stock confirm dialog) and then opens Cover Flow on its Preparing screen with every cover extracted again.
CFSET_PAGE = Page('m1plus_cfset', 'm1plus_cfset_page', 'Cover Flow', rows=[
    Row('Landscape', ACT_LANDSCAPE),
    Row('Sort', ACT_SORT),
    Row('Rebuild Covers', ACT_REBUILD),
])
SORT_VALUES = ('Artist', 'Album')    # the value shown for the setting's two states (the default, Artist, first)

# The Daily Mix page (patch/dailymix.c dp_*): opened by a tap on the Home card; it has no navbar and no rows of its own (the payload paints the songs).
DAILYMIX = Page('m1plus_dailymix', 'm1plus_dailymix_page', 'Daily Mix', kind='dailymix')

# The Pod page (patch/ipod.c): a fullscreen window, no navbar and no rows; the payload paints the Pod screen and takes the wheel's touches.
IPOD = Page('m1plus_ipod', 'm1plus_ipod_page', 'Pod', kind='ipod')

# The Podcasts page (patch/podcasts.c): the Albums page's structure (a navbar over a stock list holding one view the payload paints); two levels, the shows and a show's episodes.
PODCASTS = Page('m1plus_podcasts', 'm1plus_podcasts_page', 'Podcasts', kind='podcasts')

# The Tape page (patch/tape.c): a fullscreen window drawn landscape; the payload paints the cassette and takes the touches (opened from Now Playing's More dialog, not from a menu row).
TAPE = Page('m1plus_tape', 'm1plus_tape_page', 'Cassette Mode', kind='tape')

# Customize > Cassette Mode: the cassette's look. Cassette Theme shows its value (Normal, Chrome or Metal) at the right and a tap cycles it; the choice is saved and the Tape page reads it when it opens.
CASSETTE_PAGE = Page('m1plus_tapeset', 'm1plus_tapeset_page', 'Cassette Mode', rows=[
    Row('Cassette Theme', ACT_CTHEME),
])
CTHEME_VALUES = ('Normal', 'Chrome', 'Metal')   # the value shown for the setting's three states, in the order of the saved index (tools/tape_art.py THEME_NAMES)

# PAGES[0] is the entry page.
PAGES = [MENU, COVER, ARTISTS, SHUFFLE_PAGE, CUSTOMIZE_PAGE, EXTRAS_PAGE, ALBUMS, MENUCFG_PAGE, CFSET_PAGE, HOMESET_PAGE, PLAYLISTS, SONGS, DAILYMIX,
         EXTRASCFG_PAGE, DEVELOPER_PAGE, IPOD, PODCASTS, TAPE, CASSETTE_PAGE]
assert PAGES[CASSETTE_PAGE_INDEX] is CASSETTE_PAGE
assert PAGES[SHUFFLE_PAGE_INDEX] is SHUFFLE_PAGE and PAGES[CUSTOMIZE_PAGE_INDEX] is CUSTOMIZE_PAGE
assert PAGES[EXTRASCFG_PAGE_INDEX] is EXTRASCFG_PAGE and PAGES[DEVELOPER_PAGE_INDEX] is DEVELOPER_PAGE
assert PAGES[EXTRAS_PAGE_INDEX] is EXTRAS_PAGE and PAGES[MENUCFG_PAGE_INDEX] is MENUCFG_PAGE
assert PAGES[CFSET_PAGE_INDEX] is CFSET_PAGE and PAGES[HOMESET_PAGE_INDEX] is HOMESET_PAGE
