#!/usr/bin/env python3
"""Shared page/entry definitions for the M1 Pod payload.

One source of truth, consumed by both:
  tools/pod_ui.py   builds the ui/*.bin assets (widget trees)
  tools/pod.py      emits the C row/page tables into stock.h for patch/m1pod.c

Keeping the rows here means the asset a page shows and the action the payload takes on a tap can
never drift apart: the row's widget name, its label and its handler all come from one record.

Entry point: the payload hooks the Home screen's icon click dispatcher and intercepts exactly one
Home icon, HOME_ENTRY. Tapping it opens the stage's entry page; the kill-switch file and every other
icon fall through to stock behaviour.

HOME_ENTRY is **Tidal** (id 1): it is in the English Home list by default and is its first icon,
and it is online-only (Wi-Fi + a Tidal subscription), so taking it over costs nothing offline.
The HiFi store (id 0) is *not* usable as the entry: demo only ever puts it on Home when the
`language` global is 0, i.e. Simplified Chinese (docs/payload.md#home-icons-and-their-conditions).
"""

# Home item ids (must match patch/offsets.inc HOME_*). The entry icon and the destinations rows open.
HOME_HIFIMUSIC = 0   # Simplified Chinese only -- never on Home in English
HOME_TIDAL = 1       # online-only (Wi-Fi + subscription); first Home icon in English
HOME_MYMUSIC = 3     # allmusic_page 0xf001: all songs
HOME_FOLDER = 4
HOME_ALBUM = 5
HOME_SONGER = 6      # artists
HOME_GENRE = 7
HOME_PLAYLIST = 14
HOME_CDRIPPER = 15   # needs the external CD drive accessory; the alternative entry candidate
HOME_SYSSET = 17
HOME_PLAYSET = 16

HOME_ENTRY = HOME_TIDAL   # the icon that opens M1 Pod (see the note above)

# Row actions (mirror the enum in patch/m1pod.c).
ACT_HOME = 0     # open a stock Home destination through the stock dispatcher (arg = HOME_* id)
ACT_PAGE = 1     # open another M1 Pod page (arg = page index within the stage's page list)
ACT_PLAYER = 2   # go to Now Playing (stock on_backtoplayer_onclick)
ACT_COVER = 3    # open Cover Flow (patch/coverflow.c; its own page, built at runtime)


class Row:
    def __init__(self, label, action, arg=0):
        self.label, self.action, self.arg = label, action, arg


class Page:
    def __init__(self, key, name, title, rows=(), info=None, kind='rows'):
        self.key = key          # asset basename under ui/ (ui/<key>.bin) and window resource name
        self.name = name        # root widget name property
        self.title = title      # navbar title text
        self.rows = list(rows)
        self.info = info        # optional body text shown in label_info (the hello page)
        self.kind = kind        # 'rows', 'info' or 'cover' (the Cover Flow page's own layout)


# The Classic iPod main menu, adapted to the 320x480 touch screen (q2-pod docs/ipod.md geometry).
MENU = Page('m1pod_menu', 'm1pod_menu_page', 'M1 Pod', info=None, rows=[
    Row('Now Playing', ACT_PLAYER),
    Row('Cover Flow', ACT_COVER),
    Row('Songs', ACT_HOME, HOME_MYMUSIC),
    Row('Albums', ACT_HOME, HOME_ALBUM),
    Row('Artists', ACT_HOME, HOME_SONGER),
    Row('Genres', ACT_HOME, HOME_GENRE),
    Row('Folders', ACT_HOME, HOME_FOLDER),
    Row('Playlists', ACT_HOME, HOME_PLAYLIST),
    Row('Settings', ACT_HOME, HOME_SYSSET),
])

# Cover Flow's own page (patch/coverflow.c fills it at runtime: the slide_menu of covers, the
# progress/cancel pair of the first-run cache build, and the album's track list).
COVER = Page('m1pod_cover', 'm1pod_cover_page', 'Cover Flow', kind='cover')

# Stages A and C are the already-flashed builds (V2.1dA, V2.1dM): the same menu without the
# Cover Flow row, so re-running them rebuilds exactly what the hardware has.
MENU_NOCOVER = Page('m1pod_menu', 'm1pod_menu_page', 'M1 Pod', info=None,
                    rows=[r for r in MENU.rows if r.action != ACT_COVER])

# A tiny, obviously-safe page for the "hello" stage: a title, one line of text and the navbar's Back.
HELLO = Page('m1pod_hello', 'm1pod_hello_page', 'M1 Pod', info='M1 Pod is alive. Press Back.', rows=[])

# index 0 of each list is the stage's entry page.
STAGES = {
    'A': [MENU_NOCOVER],   # inert: payload present, no hook installed -> this is never reached
    'B': [HELLO],
    'C': [MENU_NOCOVER],
    'D': [MENU, COVER],    # the menu with its Cover Flow row, and that page
}
