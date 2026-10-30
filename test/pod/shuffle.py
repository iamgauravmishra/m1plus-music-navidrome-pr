"""Shuffle: the page rows, Songs / Albums / Folders, errors."""
import os
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)


# ======================= Shuffle (patch/shuffle.c) =======================
def song(m, path, album='', track=0, disc=0, cue=0, kind=8):
    """A songtable row as getAllMusic's callback leaves it (@0x4e9058)."""
    name = path.rsplit('/', 1)[1]
    r = m.record(album=album, path=path, title=name, name=name)
    m.setword(r + O['REC_TRACK'], track); m.setword(r + O['REC_DISC'], disc)
    m.setword(r + O['REC_CUE_START'], cue); m.setword(r + O['REC_TYPE'], kind)
    return r


def shuffle_machine(rows, mode=0, clock=1, present=True):
    """A library (rows of song() arguments) that loadLocalClassList(0xf001) loads, and a stock
    loadSongList that copies it as the Songs page's row handler gets it."""
    m = Machine()
    m.stock_songlist = True
    m.mode, m.clock = mode, clock
    m.showlist = [song(m, *r) for r in rows]
    if present:
        for r in m.showlist: m.present.add(m.read_cstr(m.word(r + O['REC_PATH'])))
    return m


def field(m, r, off): return m.read_cstr(m.word(r + off))


def runs(q, key):
    """The queue as consecutive runs of equal key(record)."""
    out = []
    for r in q:
        k = key(r)
        if not out or out[-1][0] != k: out.append((k, []))
        out[-1][1].append(r)
    return out


def shuffle_page():
    """(index, page) of the page holding the Shuffle rows: the Shuffle page the menu's one Shuffle
    row opens (q2-pod's Library > Shuffle)."""
    return next((i, p) for i, p in enumerate(pod_pages.PAGES)
                if any(r.action == pod_pages.ACT_SHUFFLE for r in p.rows))


def shuffle_tests(expect, menu):
    play = PSYMS['shuffle_play']
    spi, page = shuffle_page()
    rows0 = PSYMS[f'pod_rows_{spi}']
    K = {pod_pages.SHUFFLE_SONGS: 'Songs', pod_pages.SHUFFLE_ALBUMS: 'Albums', pod_pages.SHUFFLE_FOLDERS: 'Folders'}
    COUNT = 50000000

    # 26. The rows: one per kind, stock-styled, no chevron (they play, as Now Playing's row), and the payload's
    #     own row table binds them to ACT_SHUFFLE and the kind. Stage H: the menu has one Shuffle row, with a
    #     chevron, opening the Shuffle page, whose rows are the three, in that order.
    import awtk_ui
    at = [i for i, r in enumerate(page.rows) if r.action == pod_pages.ACT_SHUFFLE]
    if spi == 0:
        cover = next(i for i, r in enumerate(page.rows) if r.action == pod_pages.ACT_COVER)
        expect(at == [cover + 1, cover + 2, cover + 3] and [page.rows[i].arg for i in at] == sorted(K),
               f'Shuffle Songs, Albums, Folders follow Cover Flow ({at})')
    else:
        shuffle_page_tests(expect, menu, spi, page)
        expect(at == [0, 1, 2] and [page.rows[i].arg for i in at] == sorted(K) and len(page.rows) == 3,
               f'the Shuffle page lists Shuffle Songs, Albums, Folders ({at})')
    tree = awtk_ui.parse(open(os.path.join(WORK, 'rootfs', f'release/assets/default/raw/ui/{page.key}.bin'), 'rb').read())
    items = {w.name: w for w in tree.walk() if w.type == 'list_item'}
    for i in at:
        w = items.get(f'pod_row{i}')
        labs = [pod_i18n.shown_english(c) for c in w.children if c.type == 'hscroll_label'] if w else []
        expect(labs == [page.rows[i].label] and not any(c.type == 'image' and c.name != 'pod_icon' for c in w.children) and
               all(c.get('sensitive') == 'false' for c in w.children if c.name == 'pod_icon'),
               f'{page.key} row {i} reads "{page.rows[i].label}", no chevron ({labs})')
        m = Machine()
        name, action, arg = (m.word(rows0 + 12 * i + o) for o in (0, 4, 8))
        expect((m.read_cstr(name), action, arg) == (f'pod_row{i}', pod_pages.ACT_SHUFFLE, page.rows[i].arg),
               f'the payload row table binds pod_row{i} to ACT_SHUFFLE {page.rows[i].arg}')

    lib = [(f'/mnt/mmc/m/{d}/{t:02d}.flac', f'Album {d}', t) for d in 'ABCDE' for t in range(1, 4)]

    # 27. Shuffle Songs from its menu row: the Songs page's stock sequence with its class, the play
    #     mode set to Shuffle the way the Play settings page sets it, then Now Playing.
    m = shuffle_machine(lib)
    m.call(PSYMS['on_row'], a0=rows0 + 12 * at[0], count=COUNT)
    n = m.names()
    seq = [c for c in n if c in ('loadLocalClassList', '_create_deque', 'loadSongList', 'access', 'mclSetPlayMode',
                                 'notifyPlayMode', 'dmrSendPlayMode', 'write_int_config',
                                 'navigator_to_with_context', 'deque_destroy')]
    expect(seq == ['loadLocalClassList', '_create_deque', 'loadSongList', 'access', 'mclSetPlayMode', 'notifyPlayMode',
                   'dmrSendPlayMode', 'write_int_config', 'navigator_to_with_context', 'deque_destroy'],
           f'Shuffle Songs runs the stock sequence in order ({seq})')
    expect(('loadLocalClassList', O['CLASS_ALL_SONGS']) in m.calls, "the library is the Songs page's query (0xf001)")
    ls = [c for c in m.calls if c[0] == 'loadSongList']
    expect(ls and ls[0][3] == O['CLASS_ALL_SONGS'], f'loadSongList with the Songs class ({ls})')
    expect(('mclSetPlayMode', O['MODE_SHUFFLE']) in m.calls and ('dmrSendPlayMode', O['MODE_SHUFFLE']) in m.calls
           and ('write_int_config', O['MODE_SHUFFLE'], 'PLAYSET', 'PLAYMODE') in m.calls and m.mode == O['MODE_SHUFFLE'],
           'the stock play mode becomes Shuffle, saved as [PLAYSET] PLAYMODE=2')
    nav = [c for c in m.calls if c[0] == 'navigator_to_with_context']
    q, idx = m.played
    expect(len(nav) == 1 and nav[0][1] == 'playing_page' and nav[0][3] == O['CLASS_ALL_SONGS']
           and nav[0][4] == O['PLAY_MODE'], f'Now Playing opens with {{queue, index, 0xf001, 2}} ({nav})')
    expect([field(m, r, O['REC_PATH']) for r in q] == [r[0] for r in lib],
           "the queue is the whole library in the library's order (stock Shuffle draws the play order)")
    expect(0 <= idx < len(lib) and nav[0][2] == idx, f'it starts on a song of the library ({idx})')
    expect(all(m.word(r + O['REC_CLASS']) == O['CLASS_ALL_SONGS'] for r in q), 'every queued song carries the class')
    expect(m.word(pod.DATA['G_CLASS_TYPE'][0]) == O['CLASS_ALL_SONGS'], 'g_class_type is the Songs class')
    expect(not any(c in n for c in ('timer_add', 'pthread_create', 'widget_on', 'window_open')),
           'a shuffle leaves nothing behind: no timer, thread, handler or page of its own')
    starts = set()
    for clock in range(1, 41):
        m = shuffle_machine(lib, clock=clock * 7919)
        m.call(play, a0=pod_pages.SHUFFLE_SONGS, count=COUNT)
        starts.add(m.played[1])
    expect(len(starts) >= 8, f'the first song is drawn at random ({sorted(starts)})')
    m = shuffle_machine(lib)
    firsts = []
    for _ in range(6):   # taps in a row keep drawing (the generator is seeded once)
        m.call(play, a0=pod_pages.SHUFFLE_SONGS, count=COUNT); firsts.append(m.played[1])
    expect(len(set(firsts)) >= 3, f'repeated taps start on different songs ({firsts})')

    # 28. Duplicate file names (01.flac in every album): loadSongList's match by name would always
    #     give the first; the drawn song itself plays.
    dup = [(f'/mnt/mmc/m/{d}/01.flac', f'Album {d}', 1) for d in 'ABCDEFGH']
    starts = set()
    for clock in range(1, 31):
        m = shuffle_machine(dup, clock=clock * 104729)
        m.call(play, a0=pod_pages.SHUFFLE_SONGS, count=COUNT)
        starts.add(m.played[1])
    expect(len(starts) >= 4, f'with duplicate names the start is still random ({sorted(starts)})')

    # 29. Already in Shuffle: nothing is written.
    m = shuffle_machine(lib, mode=O['MODE_SHUFFLE'])
    m.call(play, a0=pod_pages.SHUFFLE_SONGS, count=COUNT)
    expect(not any(c[0] in ('mclSetPlayMode', 'write_int_config') for c in m.calls) and m.played,
           'Shuffle Songs in Shuffle mode plays without touching the setting')

    # 30. Shuffle Albums: every album once, as one run, in a random order; each album in the stock
    #     album page's order (disc, then track), untagged ones by file name; album names grouped as
    #     the stock Albums list groups them (NOCASE); from the first album's first track.
    albums = [('/mnt/mmc/x/kob/03.flac', 'Kind of Blue', 3), ('/mnt/mmc/x/ar/02.flac', 'Abbey Road', 2),
              ('/mnt/mmc/x/u/b.mp3', '', 0), ('/mnt/mmc/x/kob/01.flac', 'Kind of Blue', 1),
              ('/mnt/mmc/x/dbl/cd2/01.flac', 'Double', 1, 2), ('/mnt/mmc/x/ar/01.flac', 'abbey road', 1),
              ('/mnt/mmc/x/u/a.mp3', '', 0), ('/mnt/mmc/x/dbl/cd1/02.flac', 'Double', 2, 1),
              ('/mnt/mmc/x/kob/02.flac', 'Kind of Blue', 2), ('/mnt/mmc/x/dbl/cd1/01.flac', 'Double', 1, 1),
              ('/mnt/mmc/x/ar/03.flac', 'ABBEY ROAD', 3)]
    want = {'kind of blue': ['/mnt/mmc/x/kob/01.flac', '/mnt/mmc/x/kob/02.flac', '/mnt/mmc/x/kob/03.flac'],
            'abbey road': ['/mnt/mmc/x/ar/01.flac', '/mnt/mmc/x/ar/02.flac', '/mnt/mmc/x/ar/03.flac'],
            '': ['/mnt/mmc/x/u/a.mp3', '/mnt/mmc/x/u/b.mp3'],
            'double': ['/mnt/mmc/x/dbl/cd1/01.flac', '/mnt/mmc/x/dbl/cd1/02.flac', '/mnt/mmc/x/dbl/cd2/01.flac']}
    orders, good = set(), True
    for clock in range(1, 25):
        m = shuffle_machine(albums, mode=O['MODE_REPEAT_ALL'], clock=clock * 2654435)
        v = m.call(play, a0=pod_pages.SHUFFLE_ALBUMS, count=COUNT)
        q, idx = m.played
        got = runs(q, lambda r: field(m, r, O['REC_ALBUM']).lower())
        good &= (v == 0 and idx == 0 and len(got) == 4 and len(q) == len(albums)
                 and all([field(m, r, O['REC_PATH']) for r in rs] == want[k] for k, rs in got))
        orders.add(tuple(k for k, _ in got))
    expect(good, 'Shuffle Albums queues each album once, contiguous, in album order, from its first track')
    expect(len(orders) >= 6, f'the albums come in a random order ({len(orders)} orders in 24 taps)')
    expect(not any(c[0] in ('mclSetPlayMode', 'write_int_config') for c in m.calls), 'Shuffle Albums keeps Repeat all')
    expect(m.names().count('calloc') == 2 and m.names().count('free') == 2, 'its index and the group ranks are freed')
    nav = [c for c in m.calls if c[0] == 'navigator_to_with_context']
    expect(nav and nav[0][1:] == ('playing_page', 0, O['CLASS_ALL_SONGS'], O['PLAY_MODE']),
           f"Now Playing opens on the first album's first track ({nav})")
    expect(sorted(field(m, r, O['REC_PATH']) for r in m.played[0]) == sorted(a[0] for a in albums)
           and sorted(field(m, r, O['REC_NAME']) for r in m.played[0]) == sorted(a[0].rsplit('/', 1)[1] for a in albums),
           'the in-place reorder moved whole records: every song is there exactly once')
    for start, end in ((O['MODE_SHUFFLE'], O['MODE_ORDER']), (O['MODE_REPEAT_ONE'], O['MODE_ORDER']),
                       (O['MODE_ORDER'], None), (O['MODE_REPEAT_ALL'], None)):
        m = shuffle_machine(albums, mode=start)
        m.call(play, a0=pod_pages.SHUFFLE_ALBUMS, count=COUNT)
        if end is None:
            expect(not any(c[0] == 'mclSetPlayMode' for c in m.calls) and m.played, f'Shuffle Albums keeps mode {start}')
        else:
            expect(('mclSetPlayMode', end) in m.calls and ('write_int_config', end, 'PLAYSET', 'PLAYMODE') in m.calls,
                   f'Shuffle Albums turns mode {start} into List play')

    # 31. Shuffle Folders: by folder (a subfolder is its own), each in file-name order.
    folders = [('/mnt/mmc/B/2.flac',), ('/mnt/mmc/A/b.flac',), ('/mnt/mmc/B/sub/1.flac',),
               ('/mnt/mmc/A/a.flac',), ('/mnt/mmc/B/1.flac',), ('/mnt/mmc/C/x.flac', 'Abbey Road', 1)]
    orders, good = set(), True
    for clock in range(1, 13):
        m = shuffle_machine(folders, clock=clock * 31337)
        m.call(play, a0=pod_pages.SHUFFLE_FOLDERS, count=COUNT)
        q, idx = m.played
        got = runs(q, lambda r: field(m, r, O['REC_PATH']).rsplit('/', 1)[0])
        paths = [[field(m, r, O['REC_PATH']) for r in rs] for _, rs in got]
        good &= (idx == 0 and sorted(k for k, _ in got) == ['/mnt/mmc/A', '/mnt/mmc/B', '/mnt/mmc/B/sub', '/mnt/mmc/C']
                 and all(p == sorted(p) for p in paths))
        orders.add(tuple(k for k, _ in got))
    expect(good, 'Shuffle Folders queues each folder once, contiguous, in file-name order')
    expect(len(orders) >= 4, f'the folders come in a random order ({len(orders)} seen)')

    # 32. An empty library: the stock message box, nothing copied, nothing played, the mode untouched.
    for kind in K:
        m = shuffle_machine([])
        v = m.call(play, a0=kind, count=COUNT)
        expect(v == 0xffffffff and ('toast', 'Update Local Music first', O['MSGINFO_KIND'], O['MSGINFO_MS']) in m.calls
               and not m.played and '_create_deque' not in m.names() and 'mclSetPlayMode' not in m.names(),
               f'an empty library: Shuffle {K[kind]} says "Update Local Music first" and plays nothing')

    # 33. The first song is not on the card (card out, stale library): a message, no play, no mode
    #     change, the queue freed.
    for kind in K:
        m = shuffle_machine(lib, present=False)
        v = m.call(play, a0=kind, count=COUNT)
        expect(v == 0xffffffff and any(c[0] == 'toast' and c[1] == 'Storage unavailable' for c in m.calls)
               and not m.played and 'mclSetPlayMode' not in m.names() and 'deque_destroy' in m.names(),
               f'Shuffle {K[kind]} with the card missing says so and plays nothing')

    # 34. No memory for the album index: a message, the queue freed, nothing played.
    m = shuffle_machine(albums); m.calloc_fail = True
    v = m.call(play, a0=pod_pages.SHUFFLE_ALBUMS, count=COUNT)
    expect(v == 0xffffffff and any(c[0] == 'toast' and 'memory' in c[1] for c in m.calls) and not m.played
           and 'deque_destroy' in m.names() and 'mclSetPlayMode' not in m.names(),
           'no memory for the index: Shuffle Albums says so and plays nothing')

    # 35. A huge library: Albums/Folders refuse past SHUFFLE_MAX songs before copying anything;
    #     Songs is the stock Songs path and has no cap of its own.
    m = shuffle_machine([])
    one = song(m, '/mnt/mmc/big/01.flac', 'Big', 1)
    m.present.add('/mnt/mmc/big/01.flac')
    big = O['SHUFFLE_MAX']
    m.showlist = [one] * (big + 1)
    for kind in (pod_pages.SHUFFLE_ALBUMS, pod_pages.SHUFFLE_FOLDERS):
        try: v = m.call(play, a0=kind, count=COUNT)
        except AssertionError: v = None   # still sorting at the step limit: the cap did not hold
        expect(v == 0xffffffff and any(c[0] == 'toast' and c[1] == 'Too many songs to shuffle' for c in m.calls)
               and '_create_deque' not in m.names() and 'calloc' not in m.names(),
               f'{big + 1} songs: Shuffle {K[kind]} refuses before copying the library')
    # exactly SHUFFLE_MAX passes the cap and goes on to allocate the index (refused here, so the
    # harness need not sort 65,536 songs)
    m.played = None
    m.showlist = [one] * big
    m.calloc_fail = True
    v = m.call(play, a0=pod_pages.SHUFFLE_ALBUMS, count=COUNT)
    expect(v == 0xffffffff and ('calloc', 16 * big, 0) in m.calls
           and not any(c[0] == 'toast' and c[1] == 'Too many songs to shuffle' for c in m.calls),
           f'{big} songs pass the cap: the {16 * big}-byte index is the only extra allocation')
    m.calloc_fail = False
    # the cost on a real-shaped library: 128 albums of 16 tracks, every album intact
    m2 = shuffle_machine([(f'/mnt/mmc/l/{a:03d}/{t:02d}.flac', f'Album {a:03d}', 16 - t) for a in range(128)
                          for t in range(16)])
    v = m2.call(play, a0=pod_pages.SHUFFLE_ALBUMS, count=2000000000)
    got = runs(m2.played[0], lambda r: field(m2, r, O['REC_ALBUM'])) if m2.played else []
    expect(v == 0 and len(got) == 128 and all(len(rs) == 16 and [m2.word(r + O['REC_TRACK']) for r in rs]
                                              == list(range(1, 17)) for _, rs in got),
           '2048 songs in 128 albums: every album once, tracks 1-16 in order')
    print(f'  Shuffle Albums over 2048 songs (128 albums): {m2.icount:,} payload instructions')
    # Shuffle Folders on the same size: the folder length is kept per song, not found again in every comparison
    FOLDER_COST = {}
    deep = '/mnt/mmc/Music/Library/Collection/Artist'
    for tag, prefix in (('short', '/mnt/mmc/l'), ('long', deep)):
        m3 = shuffle_machine([(f'{prefix}/{a:03d}/{t:02d}.flac', f'Album {a:03d}', 16 - t) for a in range(128) for t in range(16)])
        v = m3.call(play, a0=pod_pages.SHUFFLE_FOLDERS, count=2000000000)
        got = runs(m3.played[0], lambda r: field(m3, r, O['REC_PATH']).rsplit('/', 1)[0]) if m3.played else []
        expect(v == 0 and len(got) == 128 and len({k for k, _ in got}) == 128
               and all(len(rs) == 16 and [field(m3, r, O['REC_PATH']) for r in rs] == sorted(field(m3, r, O['REC_PATH']) for r in rs) for _, rs in got),
               f'2048 songs in 128 {tag}-path folders: every folder once, contiguous, in file-name order')
        print(f'  Shuffle Folders over 2048 songs ({tag} paths, {len(m3.played[0] and field(m3, m3.played[0][0], O["REC_PATH"]))} bytes): {m3.icount:,} payload instructions')
        FOLDER_COST[tag] = m3.icount
    expect(FOLDER_COST['short'] < 14000000 and FOLDER_COST['long'] < 30000000,
           f'the folder length is found once per song: {FOLDER_COST["short"]:,} / {FOLDER_COST["long"]:,} instructions (26.4 M / 59.1 M before)')
    m.showlist = [one] * (big + 1)
    v = m.call(play, a0=pod_pages.SHUFFLE_SONGS, count=COUNT)
    expect(v == 0 and m.played and len(m.played[0]) == big + 1, 'Shuffle Songs plays a library of any size')

    # 36. An unknown kind does nothing at all; the kill switch keeps the whole menu (and so every
    #     shuffle) away.
    m = shuffle_machine(lib)
    expect(m.call(play, a0=7, count=COUNT) == 0xffffffff and not m.calls, 'an unknown kind does nothing')
    m = shuffle_machine(lib); m.present.add('/mnt/mmc/m1plus-off')
    m.call(PSYMS['m1plus_home_click'], a0=m.icon(str(pod_pages.HOME_ENTRY)), count=COUNT)
    expect('stock_resume' in m.names() and 'loadLocalClassList' not in m.names() and 'window_open' not in m.names(),
           'kill switch: the entry icon is stock again, no menu, no shuffle')


def shuffle_page_tests(expect, menu, spi, page):
    """Stage H: the menu's one Shuffle row (q2-pod's Library > Shuffle) opens the Shuffle page."""
    import awtk_ui
    rows0 = PSYMS['pod_rows_0']
    i = next(k for k, r in enumerate(menu.rows) if r.action == pod_pages.ACT_PAGE and r.arg == spi)
    cover = next(k for k, r in enumerate(menu.rows) if r.action == pod_pages.ACT_COVER)
    expect(menu.rows[i].label == 'Shuffle' and not any(r.action == pod_pages.ACT_SHUFFLE for r in menu.rows),
           f'the menu has one Shuffle row (row {i} of the default order, after Playlists), opening the page, and no shuffle rows of its own')
    tree = awtk_ui.parse(open(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1plus_menu.bin'), 'rb').read())
    w = next((x for x in tree.walk() if x.type == 'list_item' and x.name == f'pod_row{i}'), None)
    labs = [pod_i18n.shown_english(c) for c in w.children if c.type == 'hscroll_label'] if w else []
    expect(labs == ['Shuffle'] and any(c.type == 'image' and c.get('image') == 'right_arrow' for c in w.children),
           f'the Shuffle menu row reads "Shuffle" and has the chevron ({labs})')
    m = Machine()
    name, action, arg = (m.word(rows0 + 12 * i + o) for o in (0, 4, 8))
    expect((m.read_cstr(name), action, arg) == (f'pod_row{i}', pod_pages.ACT_PAGE, spi),
           f'the payload row table binds pod_row{i} to ACT_PAGE {spi}')
    # a tap opens the page by name and binds its navbar and its three rows to their table entries
    m = Machine()
    m.widgets = {n: 0x30000000 + k for k, n in enumerate(['btn_return', 'btn_backtoplayer'] +
                                                          [f'pod_row{k}' for k in range(len(page.rows))])}
    m.call(PSYMS['on_row'], a0=rows0 + 12 * i, count=200000)
    ons = [c for c in m.calls if c[0] == 'widget_on']
    expect(('window_open', page.key) in m.calls and 'stock_resume' not in m.names(),
           f'the Shuffle row opens {page.key}')
    srows = PSYMS[f'pod_rows_{spi}']
    expect(len(ons) == 2 + len(page.rows) and
           [(c[1], c[2], c[4]) for c in ons[2:]] == [(m.widgets[f'pod_row{k}'], O['EVT_CLICK'], srows + 12 * k)
                                                    for k in range(len(page.rows))],
           f'it binds Back, Now Playing and pod_row0..{len(page.rows) - 1} to the Shuffle page\'s row table')
    back = next((c for c in ons if c[1] == m.widgets['btn_return']), None)
    if back:
        m2 = Machine(); m2.call(back[3], count=200000)
        expect(m2.names() == ['navigator_back'], 'Back on the Shuffle page is navigator_back (to the menu)')
    else:
        expect(False, 'Back on the Shuffle page is bound')
    # the page: the M1+ Music navbar titled Shuffle, stock-styled rows exactly like the menu's, no chevrons
    st = awtk_ui.parse(open(os.path.join(WORK, 'rootfs', f'release/assets/default/raw/ui/{page.key}.bin'), 'rb').read())
    title = next((x for x in st.walk() if x.name == 'label_title'), None)
    items = [x for x in st.walk() if x.type == 'list_item']
    menu_item = next(x for x in tree.walk() if x.type == 'list_item')
    sig = lambda x: (x.get('style'), x.h, [(c.type, c.get('style'), c.x, c.y, c.h) for c in x.children if c.type == 'hscroll_label'])
    expect(title is not None and pod_i18n.shown_english(title) == 'Shuffle' and
           any(x.name == 'btn_return' for x in st.walk()) and any(x.name == 'btn_backtoplayer' for x in st.walk()),
           'the Shuffle page has the M1+ Music navbar: Shuffle, Back, Now Playing')
    expect([x.name for x in items] == ['pod_row0', 'pod_row1', 'pod_row2'] and
           [[pod_i18n.shown_english(c) for c in x.children if c.type == 'hscroll_label'] for x in items] ==
           [['Shuffle Songs'], ['Shuffle Albums'], ['Shuffle Folders']] and
           all(sig(x) == sig(menu_item) for x in items) and not any(c.type == 'image' and c.name != 'pod_icon' for x in items for c in x.children) and
           all(c.get('sensitive') == 'false' for x in items for c in x.children if c.name == 'pod_icon'),
           'its rows: Shuffle Songs / Albums / Folders, styled as the menu rows, no chevrons')
    root = asset_tree(os.path.join(WORK, 'rootfs', f'release/assets/default/raw/ui/{page.key}.bin'))
    hits = [stock_target(Machine(), root, x, pod_ui.NAVBAR_H + k * pod_ui.ROW_H + pod_ui.ROW_H // 2)
            for k in range(3) for x in (160, 32)]   # 32: on the row icon, when it has one
    expect(all(f'pod_row{i // 2}' in h for i, h in enumerate(hits)), f'a tap on each row (and on its icon) reaches that row ({hits})')


def run(ctx):
    shuffle_tests(ctx.expect, ctx.page)
