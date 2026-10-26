"""Cover Flow opens on the playing album; the album order (Settings > Cover Flow > Sort): the Artist order, the stock
Album order, the setting file, the same order on the Albums page, and the stock row behind every album that is opened.
(The Settings > Cover Flow page itself is tested in test/pod/menu.py, the localisation in test/pod/i18n.py.)"""
import importlib.util, os, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

HERE = os.path.dirname(os.path.abspath(__file__))
ALBUMS_FILE = '/mnt/data/m1pod-albums'
LAST = '/mnt/mmc/.coverflow/album'
SEED = O['FNV_SEED']


def sibling(name):
    key = f'podtest_{name}'
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, os.path.join(HERE, name + '.py'))
        mod = importlib.util.module_from_spec(spec); sys.modules[key] = mod; spec.loader.exec_module(mod)
    return sys.modules[key]


# (album, artist) in the order the stock Albums query lists them: by album title, ASCII case aside; the "Unknown
# Album" row (id -1) last. It covers: the The-prefix in either case, "The" without a space, "A" which is not ignored,
# an empty artist, the same artist and title once "The " is dropped (a tie), and the Unknown Album row.
LIB = [('A Night at the Opera', 'Queen'), ('Abbey Road', 'The Beatles'), ('Blue', 'Joni Mitchell'),
       ('Greatest Hits', 'Queen'), ('Help!', 'the beatles'), ('Kind of Blue', 'Miles Davis'),
       ('Let It Be', 'The Beatles'), ('Nevermind', 'Nirvana'), ('Pet Sounds', 'The Beach Boys'),
       ('The Wall', 'Pink Floyd'), ('Theory', 'Theo'), ('Wall', 'Pink Floyd'), ('Zeit', ''), ('Unknown Album', '')]
LIB_ARTIST_ORDER = [12, 8, 1, 4, 6, 2, 5, 7, 9, 11, 0, 3, 10, 13]    # by hand: '' < beach boys < beatles (Abbey Road, Help!, Let It Be) < ...
# ... < queen (A Night at the Opera, Greatest Hits) < theo; The Wall and Wall tie and keep the stock order; Unknown Album last


def fold(s): return ''.join(chr(ord(c) + 32) if 'A' <= c <= 'Z' else c for c in s)
def skip(s): return s[4:] if len(s) > 4 and fold(s[:4]) == 'the ' else s


def model(specs):
    """Artist order, independently: Unknown Album last, then the artist and the title without a leading "The ", ASCII
    case folded, then the stock position."""
    return sorted(range(len(specs)), key=lambda i: (specs[i][0] == 'Unknown Album', fold(skip(specs[i][1])), fold(skip(specs[i][0])), i))


def lib_machine(specs=LIB, sort=None, data=None):
    """Cover Flow's machine with these albums in the library list, all cached. sort None: the setting file missing
    (the default, Artist); 'album': the file says Album; data: the file's exact content."""
    m = cover_machine(albums=0, sort='default' if sort is None else sort)
    if data is not None: m.fs[CFSORT_FILE] = data
    fill(m, specs)
    return m


def fill(m, specs):
    m.showlist = []
    for i, (album, artist) in enumerate(specs):
        path = f'/mnt/mmc/m/{i}/1.flac'
        m.showlist.append(m.record(album=album, artist=artist, path=path, rid=-1 if album == 'Unknown Album' else i + 1))
        cache = art_file(fnv(fnv(SEED, artist), album) or 1)
        m.present.update((path, cache)); m.files[cache] = 4096
    m.class_lists[O['CLASS_ALBUMS']] = m.showlist


def caption(m, which):
    return [c[2] for c in m.calls if c[0] == 'widget_set_text_utf8' and c[1] == m.widgets[which]][-1:]


def centred(m):
    """(shelf value, album caption, artist caption) the page opened on."""
    return shelf_value(m), caption(m, 'label_album'), caption(m, 'label_artist')


def shelf(m, n, step=1):
    """What the shelf shows, album by album: [(album, artist)], and the stock row each opens."""
    shown, rows = [], []
    for k in range(0, n, step):
        put_value(m, k)
        m.call(PSYMS['on_changed'], count=2000000)
        shown.append((caption(m, 'label_album')[0], caption(m, 'label_artist')[0]))
        m.tap(O['CF_CX'])
        rows.append([c[3] for c in m.calls if c[0] == 'navigator_to_with_context' and c[1] == 'albuminfo_page'][0])
    return shown, rows


def run(ctx):
    expect = ctx.expect
    cover_open = PSYMS['coverflow_open']
    n = len(LIB)
    assert model(LIB) == LIB_ARTIST_ORDER, (model(LIB), LIB_ARTIST_ORDER)

    # ===================== 1. the Artist order =====================
    m = lib_machine()
    m.call(cover_open, count=30000000)
    shown, rows = shelf(m, n)
    expect(rows == LIB_ARTIST_ORDER, f'Artist order (the default): the shelf lists the stock rows {rows}')
    expect(shown == [LIB[i] for i in LIB_ARTIST_ORDER], f'... and each cover shows its own album and artist ({shown[:3]})')
    expect(rows[:3] == [12, 8, 1] and [LIB[i][0] for i in rows[8:10]] == ['The Wall', 'Wall'],
           'an empty artist first; "The Beach Boys" (B-e-a-c) before "The Beatles"; The Wall and Wall tie and keep their stock order')
    expect([LIB[i][1] for i in rows[2:5]] == ['The Beatles', 'the beatles', 'The Beatles'] and [LIB[i][0] for i in rows[2:5]] == ['Abbey Road', 'Help!', 'Let It Be'],
           'the Beatles, in either case, under B and then by title')
    expect(LIB[rows[-1]][0] == 'Unknown Album' and LIB[rows[-2]][1] == 'Theo', '"Theo" is not "The ": it sorts under T; the Unknown Album row stays last')
    expect([LIB[i][0] for i in rows if LIB[i][1] == 'Queen'] == ['A Night at the Opera', 'Greatest Hits'], '"A" is not ignored (only "The "): by title within an artist')
    expect(model(LIB) == rows, 'and it is the independent model\'s order')
    # every cover is still its own album: the cache key of a shelf position is the album's, not the stock row's
    m2 = lib_machine(); m2.call(cover_open, count=30000000)
    put_value(m2, 0); m2.call(PSYMS['on_changed'], count=2000000)
    first = LIB[12]
    expect(shelf_value(m2) == 0 and caption(m2, 'label_album') == [first[0]], 'the first cover is the first in the new order')
    key0 = fnv(fnv(SEED, first[1]), first[0]) or 1
    expect(f'file://{art_file(key0)}' in m2.loads, f'its texture is its own cache file ({m2.loads[:2]})')
    # a tap on the centre cover opens the STOCK row: the album page reads it from the stock list, which is not reordered
    m3 = lib_machine(); m3.call(cover_open, count=30000000)
    put_value(m3, 0); m3.tap(O['CF_CX'])
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ALBUMS'], 12) in m3.calls
           and m3.deques[m3.opened_album[2]] == m3.showlist and m3.deques[m3.opened_album[2]][12] is m3.showlist[12],
           'the first cover (Zeit) opens stock row 12 of the unreordered stock list')

    # ===================== 2. the Album order is exactly the stock one =====================
    for data in (b'0\n', b'0'):
        m = lib_machine(data=data)
        m.call(cover_open, count=30000000)
        shown, rows = shelf(m, n)
        expect(rows == list(range(n)) and shown == LIB, f'saved {data!r}: Album order is the stock order, row for row')

    # ===================== 3. the setting file: strict, anything invalid is Artist =====================
    small = [('Alpha', 'Zed'), ('Beta', 'Amy'), ('Gamma', 'Mel')]
    for data, artist in ((None, True), (b'1\n', True), (b'1', True), (b'', True), (b'x\n', True), (b'00', True), (b'0x', True),
                         (b'0\n\n', True), (b'2\n', True), (b' 0\n', True), (b'\x00\n', True), (b'\xff\xff', True),
                         (b'0\n', False), (b'0', False)):
        m = lib_machine(small, data=data) if data is not None else lib_machine(small)
        m.call(cover_open, count=10000000)
        shown, rows = shelf(m, 3)
        expect(rows == ([1, 2, 0] if artist else [0, 1, 2]), f'saved {data!r}: {"Artist" if artist else "Album"} order ({rows})')
    m = lib_machine(small); m.call(cover_open, count=10000000)
    expect(CFSORT_FILE not in m.fs and CFSORT_TMP not in m.fs and not any(c[0] in ('write', 'rename') for c in m.calls),
           'reading the setting never writes it (a default or an invalid file is left as it is)')
    expect(len([c for c in m.calls if c[0] == 'open' and c[1] == CFSORT_FILE]) == 1, 'the file is read once, when the page opens')

    # ===================== 4. memory and size limits =====================
    m = lib_machine(small); m.calloc_fail = True
    m.call(cover_open, count=10000000)
    expect(('window_open', 'm1pod_cover') in m.calls and shelf_value(m) == 0 and caption(m, 'label_album') == ['Alpha'],
           'with no memory for the order the page still opens, on the stock order (the flat covers stand in)')
    m = lib_machine(small); m.call(cover_open, count=10000000); m.call(PSYMS['on_destroy'], count=2000000)
    freed = [c for c in m.calls if c[0] == 'free']
    expect(freed, 'closing the page frees what it allocated (the order included)')
    big = [(f'Album {i:04d}', f'Artist {(i * 37) % 4000:04d}') for i in range(4000)]
    m = lib_machine(big); m.call(cover_open, count=200000000)
    spent = m.icount
    shown, rows = shelf(m, 4000, step=401)
    mdl = model(big)
    print(f'  sort of 4000 albums on open: {spent:,} payload instructions')
    expect(rows == mdl[::401] and spent < 120000000, f'4000 albums: sorted on open in {spent:,} payload instructions, and in the model\'s order')
    m = lib_machine(big + [('Album 4000', 'Artist')]); m.call(cover_open, count=2000000)
    expect(not any(c[0] == 'calloc' and c[1] == 4001 * 4 for c in m.calls) and m.props.get((m.widgets['label_status'], 'sensitive')) == 1,
           'a library over the limit is not sorted (nothing shows)')

    # ===================== 5. opens on the playing album =====================
    def opened(m, tracks, pos, **kw):
        if tracks is not None: m.play(tracks, pos)
        m.call(cover_open, count=30000000)
        return centred(m)
    rec = lambda m, album, artist: m.record(album=album, artist=artist, path='/mnt/mmc/p/1.flac')
    want = lambda i: (LIB_ARTIST_ORDER.index(i), [LIB[i][0]], [LIB[i][1]])
    m = lib_machine()
    expect(opened(m, [rec(m, 'Kind of Blue', 'Miles Davis')], 0) == want(5), 'the playing album (Kind of Blue) is centred: the sorted position, not the stock row')
    expect(('mclGetPlayPos',) in [(c[0],) for c in m.calls], 'the position is read from the player (mclGetPlayPos)')
    m = lib_machine(sort='album')
    expect(opened(m, [rec(m, 'Kind of Blue', 'Miles Davis')], 0) == (5, ['Kind of Blue'], ['Miles Davis']), 'and in Album order the stock row')
    m = lib_machine()
    t = [rec(m, 'Abbey Road', 'The Beatles'), rec(m, 'Zeit', ''), rec(m, 'Nevermind', 'Nirvana')]
    expect(opened(m, t, 2) == want(7), 'the playing track is the queue\'s row at the position, not the first (3 queued, on the third)')
    m = lib_machine()
    expect(opened(m, [rec(m, 'Blue', 'Joni Mitchell and guests')], 0) == want(2), 'a track whose artist is not the album row\'s artist (a compilation): matched by album name')
    m = lib_machine()
    expect(opened(m, [rec(m, 'KIND OF BLUE', 'miles davis')], 0) == want(5), 'the album name is compared ignoring ASCII case')
    m = lib_machine()
    expect(opened(m, [rec(m, 'Zeit', '')], 0) == want(12), 'an album with an empty artist')
    m = lib_machine()
    expect(opened(m, [rec(m, 'Unknown Album', '')], 0) == want(13), 'the Unknown Album row can be the playing one')
    # not found, nothing playing, errors: today's behaviour, the saved last album
    key = fnv(fnv(SEED, 'Nirvana'), 'Nevermind') or 1
    def saved(m):
        m.files[LAST] = 4; m.saved_album = key
    for what, setup in (('an album the library does not have', lambda m: m.play([rec(m, 'Not In The Library', 'Nobody')], 0)),
                        ('a track with no album tag', lambda m: m.play([rec(m, '', 'Nobody')], 0)),
                        ('nothing playing (position -1)', lambda m: m.play([rec(m, 'Kind of Blue', 'Miles Davis')], -1)),
                        ('no queue at all', lambda m: None),
                        ('a position but no queue', lambda m: setattr(m, 'play_pos', 0)),
                        ('a position past the queue', lambda m: m.play([rec(m, 'Kind of Blue', 'Miles Davis')], 1)),
                        ('a position far past the queue', lambda m: m.play([], 7)),
                        ('an empty queue', lambda m: m.play([], 0))):
        m = lib_machine(); saved(m); setup(m)
        expect(opened(m, None, 0) == want(7), f'{what}: the saved last album (Nevermind) opens as before')
        m = lib_machine(); setup(m)
        expect(opened(m, None, 0)[0] == 0, f'{what}, no saved album: the first')
    m = lib_machine(); saved(m); m.play([rec(m, 'Kind of Blue', 'Miles Davis')], 0)
    expect(opened(m, None, 0) == want(5), 'the playing album wins over the saved one')
    m = lib_machine(); m.play([rec(m, 'Kind of Blue', 'Miles Davis')], 0)
    m.call(cover_open, count=30000000); m.call(PSYMS['on_destroy'], count=2000000)
    expect(any(c[0] == 'fopen' and c[1] == LAST and c[2] == 'wb' for c in m.calls) and
           ('fwrite', fnv(fnv(SEED, 'Miles Davis'), 'Kind of Blue') or 1) in m.calls, 'leaving writes the centred album as the last one, as before')
    # looked up once, at open: nothing in the page reads the player afterwards
    m = lib_machine(); m.play([rec(m, 'Kind of Blue', 'Miles Davis')], 0); m.call(cover_open, count=30000000)
    m.play([rec(m, 'Nevermind', 'Nirvana')], 0)
    put_value(m, 3); m.call(PSYMS['on_changed'], count=2000000); m.tap(O['CF_CX']); m.settle()
    polled = []
    for fn in ('on_changed', 'on_load', 'on_snap', 'on_poll'):
        m.call(PSYMS[fn], count=2000000); polled += [c for c in m.calls if c[0] == 'mclGetPlayPos']
    paint(m); polled += [c for c in m.calls if c[0] == 'mclGetPlayPos']
    expect(not polled, 'the page never polls the player after it opened (the shelf stays where the user put it)')
    # the playing album is also found when the cache is being built (the preparing screen, then the covers)
    m = cover_machine(albums=0, sort='default', cached=False); fill(m, LIB)
    for c in list(m.present):
        if c.startswith('/mnt/mmc/.coverflow/'): m.present.discard(c)
    m.play([rec(m, 'Kind of Blue', 'Miles Davis')], 0)
    m.call(cover_open, count=30000000)
    expect(('pthread_create',) in m.calls, 'a library with no cache starts the build')
    m.call(PSYMS['on_cancel'], count=5000000)
    expect(centred(m) == want(5), 'the build\'s screen does not lose the playing album: the covers open on it')

    # ===================== 6. the artist's Cover Flow =====================
    def artist_page(artist_index, tracks=None, pos=0):
        m = artists_machine()
        m.fs.pop(CFSORT_FILE, None)       # the setting at its default, Artist: the artist's shelf must still keep its own order
        m.call(PSYMS['artists_open'], count=5000000)
        if tracks: m.play(tracks(m), pos)
        m.call(PSYMS['ar_on_artist'], a0=artist_index, count=8000000)
        return m
    m = artist_page(0)
    shown, rows = shelf(m, 3)
    expect([s[0] for s in shown] == ['Kind of Blue', 'Jazz Hits', 'Bitches Brew'] and rows == [0, 1, 2],
           'the artist\'s shelf keeps the stock order of its albums (by title as the artist query groups them, not re-sorted by artist)')
    m = artist_page(0, lambda m: [m.record(album='Bitches Brew', artist='Miles Davis', path='/mnt/mmc/p/1.flac')])
    expect(centred(m) == (2, ['Bitches Brew'], ['Miles Davis']), 'the playing album belongs to the artist: the artist page opens on it')
    m = artist_page(0, lambda m: [m.record(album='Jazz Hits', artist='Various Artists', path='/mnt/mmc/p/1.flac')])
    expect(centred(m)[0] == 1, 'a track of the artist\'s album filed under another artist in the library (a compilation): found by album name')
    m = artist_page(0, lambda m: [m.record(album='Pastel Blues', artist='Nina Simone', path='/mnt/mmc/p/1.flac')])
    expect(centred(m) == (0, ['Kind of Blue'], ['Miles Davis']), 'the playing album is another artist\'s: the artist page opens on its first album')
    m = artist_page(0, lambda m: [m.record(album='Bitches Brew', artist='Miles Davis', path='/mnt/mmc/p/1.flac')], pos=-1)
    expect(centred(m)[0] == 0, 'nothing playing: the first album')
    m = artist_page(1, lambda m: [m.record(album='Bitches Brew', artist='Miles Davis', path='/mnt/mmc/p/1.flac')])
    expect(centred(m) == (0, ['Pastel Blues'], ['Nina Simone']), 'an artist with one album and another artist playing: that album')
    m = artist_page(0, lambda m: [m.record(album='Bitches Brew', artist='Miles Davis', path='/mnt/mmc/p/1.flac')])
    m.call(PSYMS['on_destroy'], count=2000000)
    expect('fwrite' not in m.names(), 'and the artist page still writes no last album')

    # ===================== 7. the Albums page has the same order =====================
    albums = sibling('albums')

    def albums_page(specs, data=None, sort='artist'):
        m = albums.albums_machine(0, sort=sort)
        m.fs[ALBUMS_FILE] = b'0\n'      # list mode: a row per album, the title in label_row_title
        if data is not None: m.fs[CFSORT_FILE] = data
        fill(m, specs)
        albums.open_grid(m)
        return m

    def listed(m):
        albums.settle(m)
        rows = sorted(zip(m.texts, m.text_styles), key=lambda t: t[0][1][1])
        return [t[0][0] for t in rows if t[1] == 'label_row_title'], [t[0][0] for t in rows if t[1] == 'label_row_sub']

    def tap_row(m, r):
        m.tap(40, albums.SCREEN_Y0 + r * albums.ROW + 20, fn='al_on_pointer')
        return [c[3] for c in m.calls if c[0] == 'navigator_to_with_context' and c[1] == 'albuminfo_page']

    m = albums_page(LIB)
    titles, artists = listed(m)
    top = LIB_ARTIST_ORDER[:len(titles)]
    expect(len(titles) >= 6 and titles == [LIB[i][0] for i in top] and artists == [LIB[i][1] for i in top if LIB[i][1]],
           f'Albums (list): the rows are in the Artist order, each with its artist ({titles})')
    got = [tap_row(m, r) for r in range(6)]
    expect(got == [[LIB_ARTIST_ORDER[r]] for r in range(6)], f'a tap on a row opens the stock album row behind it ({got})')
    expect(m.deques[m.opened_album[2]] == m.showlist, 'and the album page reads the unreordered stock list')
    m = albums_page(LIB, data=b'0\n')
    titles, _ = listed(m)
    expect(titles == [a for a, _ in LIB][:len(titles)] and [tap_row(m, r) for r in range(6)] == [[r] for r in range(6)], 'Album order: the stock rows, as before')
    m = albums_page(LIB, data=b'junk')
    expect(listed(m)[0][:3] == [LIB[12][0], LIB[8][0], LIB[1][0]], 'a corrupt file: Artist')
    # grid mode: the same order, three to a row
    m = albums.albums_machine(0, sort='artist'); fill(m, LIB); albums.open_grid(m)
    albums.settle(m)
    cells = sorted(((t[1][1], t[1][0], t[0]) for t in m.texts))
    expect([c[2] for c in cells][:6] == [LIB[i][0] for i in LIB_ARTIST_ORDER[:6]],
           f'Albums (grid): the same order, three to a row ({[c[2] for c in cells][:6]})')
    # an empty library, and the page's memory
    m = albums.albums_machine(0, sort='artist'); albums.open_grid(m)
    expect(('window_open', 'm1pod_albums') in m.calls and ('widget_set_tr_text', m.widgets['label_status'], 'Update Local Music first') in m.calls,
           'no albums: no order, the message')
    m = albums_page(LIB); m.call(PSYMS['al_on_destroy'], count=2000000)
    expect(any(c[0] == 'free' for c in m.calls), 'closing the Albums page frees the order')
    # Cover Flow and Albums agree
    m1 = lib_machine(); m1.call(cover_open, count=30000000); _, cf_rows = shelf(m1, n)
    m2 = albums_page(LIB); listed(m2)
    expect(cf_rows[:6] == [tap_row(m2, r)[0] for r in range(6)], 'Cover Flow and Albums open the same stock rows in the same order')
