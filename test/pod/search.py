"""Search (patch/search.c, docs/modules/search.md): the Apple Music search screen on one page with our keyboard embedded (patch/keyboard.c keyboard_attach). The folding (case, Latin
diacritics, hiragana / katakana, half and full width, NFD), the matching (every term, any order, any field; the qualities, the incremental filter), the chips and the rows (Top Results ranking,
caps, thumbnails, texts, chevrons), live search (the debounce, the keyboard's text, hiding and showing the pad), the taps (artist, album, playlist, song), the entry points (the Songs page's
Search, the album page's search button), the page's asset and a big library's cost. The compiled payload runs under Unicorn on demo's real code with the stock library queries mocked
(test/pod/harness.py)."""
import os, re, struct
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import awtk_ui
import pod_search as PS
from awtk_text import Ttf, StbText

RAW = os.path.join(WORK, 'rootfs', 'release', 'assets', 'default', 'raw')
ASSET = os.path.join(RAW, 'ui', 'm1plus_search.bin')
FONT = Ttf(os.path.join(RAW, 'fonts', 'default.ttf'))
D = PS.D
ALL, ARTISTS, ALBUMS, PLAYLISTS = O['CLASS_ALL_SONGS'], O['CLASS_ARTISTS'], O['CLASS_ALBUMS'], O['CLASS_PLAYLISTS']
SHOWLIST = pod.DATA['PDEQ_SHOWLIST'][0]
SC_YOFF = O['SC_YOFF']
LIST_Y0 = 30 + D['SE_LIST_Y']          # the list's top on the screen: the status bar and the page's own top bar
ROW_H, LIST_H = D['SE_ROW_H'], D['SE_LIST_H']
ARTIST, ALBUM, SONG, PLAYLIST = 0, 1, 2, 3
CH_TOP, CH_ARTISTS, CH_ALBUMS, CH_SONGS, CH_PLAYLISTS = range(5)
CAPS = {ARTIST: D['SE_CAP_ARTISTS'], ALBUM: D['SE_CAP_ALBUMS'], SONG: D['SE_CAP_SONGS'], PLAYLIST: D['SE_CAP_PLAYLISTS']}
KIND_OF_CHIP = {CH_ARTISTS: ARTIST, CH_ALBUMS: ALBUM, CH_SONGS: SONG, CH_PLAYLISTS: PLAYLIST}
TICK_MS, DEBOUNCE = D['SE_TICK_MS'], D['SE_DEBOUNCE']
RET_REPEAT = 8
# struct se (patch/search.c), field by field: the offsets are worked out from the declaration, and checked against the payload's own state in `state()`
_FIELDS = [('win', 4), ('view', 4), ('sv', 4), ('list', 4), ('status', 4), ('chips', 4), ('chl', 4), ('field', 4), ('st_title', 4), ('st_sub', 4), ('st_chip', 4), ('st_chip_on', 4),
           ('query', 64), ('typed', 64), ('q', 264), ('pq', 264), ('toff', 32), ('tlen', 32), ('nterms', 4), ('nq', 4), ('pn', 4), ('have_prev', 4), ('loaded', 4),
           ('lists', 16), ('n', 16), ('cand', 16), ('sc', 16), ('nc', 16), ('rows', 4), ('nrows', 4), ('chip', 4), ('content', 4), ('chip_x', 24), ('chip_sx', 4), ('chip_down', 4),
           ('chip_dx', 4), ('chip_sx0', 4), ('chip_drag', 4), ('chip_text', 480), ('chip_len', 20), ('press', 4), ('down', 4), ('down_x', 4), ('down_y', 4), ('pressing', 4),
           ('wait', 4), ('timer', 4), ('chev', 4)]
OFF, _o = {}, 0
for _n, _s in _FIELDS: OFF[_n] = _o; _o += _s


def window_h(m): return m.window


def state(m, name, i=0):
    """A word of the payload's page state."""
    return m.s32(PSYMS['se'] + OFF[name] + 4 * i)


def rows(m):
    """The rows of the selected chip: [(kind, record index)]."""
    n, ptr = state(m, 'nrows'), state(m, 'rows') & 0xffffffff
    assert 0 <= n <= D['SE_MAX_ROWS'] and (ptr or not n), (n, ptr)
    return [(m.u.mem_read(ptr + 8 * i, 1)[0], m.word(ptr + 8 * i + 4)) for i in range(n)]


def big_record(m, album, artist, path, title, name, rid):
    """A song record on the emulated heap (a big library does not fit the 1 MB the page's other records come from)."""
    r = m.malloc(REC_SIZE); m.u.mem_write(r, bytes(REC_SIZE))
    def s(text):
        a = m.malloc(len(text.encode()) + 1); m.u.mem_write(a, text.encode() + b'\0'); return a
    m.setword(r + O['REC_ID'], rid); m.setword(r + O['REC_TYPE'], 8)
    for off, text in ((O['REC_PATH'], path), (O['REC_TITLE'], title), (O['REC_ALBUM'], album), (O['REC_ARTIST'], artist), (O['REC_NAME'], name)): m.setword(r + off, s(text))
    return r


def width(t, px=18): return StbText(FONT, px).layout(t)[1]


def search_widgets(m, window=0x20003000):
    """The Search page's widgets on machine m: every named widget of the built asset with its geometry and visible / sensitive state, the keyboard's machine under them (the pad, the
    strip, the field), the list's widget chain for demo's widget_to_local, and the window m1plus_search opens."""
    kb = sibling('keyboard')
    kb.keyboard_machine(m)            # the pad, the strip, the field widgets, the measure
    px = {}
    for w in awtk_ui.parse(open(ASSET, 'rb').read()).walk():
        if not w.name: continue
        h = m.widget(w.name)
        px[h] = int(w.get('style:normal:font_size') or 18)
        if w.name not in ('kb_pad', 'kb_strip', 'kb_cands', 'se_scrollview'):
            m.rect(h, w.x, w.y, w.w, w.h)
        m.props[(h, 'visible')] = 0 if w.get('visible') == 'false' else 1
        m.props[(h, 'sensitive')] = 0 if w.get('sensitive') == 'false' else 1
    m.measure_w = lambda h, t: width(t, px.get(h, 18))
    win, lv, sv, view = m.alloc(0x80), m.widgets['se_listview'], m.alloc(0x180), m.widgets['view_grid']
    for w in (lv, view): m.u.mem_write(w, bytes(0x80))
    m.u.mem_write(sv, bytes(0x180))
    for w, y, h, parent in ((win, 30, 450, 0), (lv, D['SE_LIST_Y'], LIST_H, win), (sv, 0, LIST_H, lv), (view, 0, LIST_H, sv)):
        for off, v in ((4, y), (8, 320), (0xc, h), (0x44, parent)): m.setword(w + off, v)
    m.setword(sv + 8, 310)
    m.widgets['se_scrollview'] = sv
    m.mem_geometry, m.live_scroll = True, frozenset({sv})
    m.sv, m.view, m.lv = sv, view, lv
    m.canvas = m.alloc(0x80); m.oy_canvas = m.canvas
    m.window = window; m.windows['m1plus_search'] = window; m.top_main = window
    m.load_image = 0
    m.images['p_default'] = (24, 24, bytes((0x40, 0x40, 0x40, 255)) * (24 * 24))
    m.strings['album'] = 'Album'      # the stock key of the album word (the stock tables translate it)
    return m


def said(m, name):
    t = m.wtext.get(m.widgets[name])
    return None if t is None else t.encode('latin-1').decode('utf-8')


def page_machine(songs=(), artists=(), albums=(), playlists=(), window=0x20003000, covers=()):
    """A machine with the Search page's widgets and a library: songs [(title, artist, album)], artists [name], albums [(album, artist)], playlists [name]. covers: (artist, album) pairs that
    have a cover file in the cache."""
    m = search_widgets(cover_machine(albums=0, cls=ListMachine), window)
    big = len(songs) > 500
    m.class_lists[ARTISTS] = [artist_rec(m, a, i + 1) for i, a in enumerate(artists)]
    m.class_lists[ALBUMS] = [m.record(album=al, artist=ar, path=f'/mnt/mmc/lib/{i}/1.flac', title=al, rid=i + 1) for i, (al, ar) in enumerate(albums)]
    m.songs = [big_record(m, al, ar, f'/mnt/mmc/m/{i}.flac', t, f'{i}.flac', i + 1) if big else m.record(album=al, artist=ar, path=f'/mnt/mmc/m/{i}.flac', title=t, name=f'{i}.flac', rid=i + 1)
               for i, (t, ar, al) in enumerate(songs)]
    m.class_lists[ALL] = m.songs
    m.playlists = [m.record(album='', artist='', path='', title=n, name='', rid=i + 1) for i, n in enumerate(playlists)]
    for i, r in enumerate(m.playlists): m.setword(r + O['REC_DISC'], 40 + i)   # a playlist's id (REC_DISC, as patch/playlists.c reads it)
    m.present.update(f'/mnt/mmc/m/{i}.flac' for i in range(len(songs)))
    for ar, al in covers:
        p = art_file(album_key(ar, al)); m.present.add(p); m.files[p] = 4096
        m.images['file://' + p] = (24, 24, struct.pack('<I', 0xff3070a0) * (24 * 24))
    m.stock_songlist = True
    m.showlist = m.songs
    return m


def opened(*a, **k):
    """The page opened with search_open (the Songs page's Search button calls it)."""
    m = page_machine(*a, **k)
    assert m.call(PSYMS['search_open'], count=40000000) == 0
    return m


def ticks(m, limit=60):
    """The page's timer run until it ends (each call is one tick; a tick that answers RET_REPEAT keeps the timer). Returns the ticks run."""
    n = 0
    while n < limit and m.call(PSYMS['se_tick'], count=900000000) == RET_REPEAT: n += 1
    return n + 1


def settle(m):
    """The page after its first tick: the library read once, no query yet."""
    ticks(m)
    return m


def typed(m, text):
    """The keyboard reported a new text; the debounce and the timer run to their end (covers loaded: ticks until the timer ends)."""
    m.call(PSYMS['se_on_text'], a0=m.cstr(text), count=2000000)
    ticks(m)


def chip(m, k):
    """Select chip k as a tap on it does: the chip row's own handler with a press and a lift on the chip."""
    m.call(PSYMS['se_chip_set'], a0=k, count=900000000)


def titles(m, kind=None):
    """The titles of the rows (of a kind), from the records they point at."""
    out = []
    for k, idx in rows(m):
        if kind is not None and k != kind: continue
        src = {ARTIST: m.class_lists[ARTISTS], ALBUM: m.class_lists[ALBUMS], SONG: m.songs, PLAYLIST: m.playlists}[k]
        out.append(m.read_cstr(m.word(src[idx] + O['REC_TITLE'])).encode('latin-1').decode('utf-8'))
    return out


def paint(m):
    ev = m.alloc(0x40); m.u.mem_write(ev, bytes(0x40)); m.setword(ev + O['EVENT_PAINT_CANVAS'], m.canvas)
    m.setword(m.canvas + O['CANVAS_OY'], (LIST_Y0 - m.word(m.sv + SC_YOFF)) & 0xffffffff)
    m.texts.clear(); m.text_styles.clear(); m.fills.clear(); m.blits.clear()
    m.call(PSYMS['se_on_paint'], a0=0, a1=ev, count=400000000)
    return list(m.texts), list(m.text_styles), list(m.fills), list(m.blits)


def tap(m, y, dx=0, dy=0, x=100):
    """A tap at content y (the list's top is the screen's LIST_Y0)."""
    m.touch('down', x, LIST_Y0 + y, 1000, fn='se_on_down', count=30000000)
    calls = list(m.calls)
    m.touch('up', x + dx, LIST_Y0 + y + dy, 1080, fn='se_on_up', count=30000000)
    m.calls = calls + m.calls


def fold(m, text, max_=160):
    """se_fold(text, out, max): the folded code points."""
    s = m.cstr(text); out = m.alloc(4 * (max_ + 2))
    n = m.call(PSYMS['se_fold'], a0=s, a1=out, a2=max_, count=2000000)
    cps = struct.unpack(f'<{n + 1}I', m.u.mem_read(out, 4 * (n + 1)))
    assert cps[-1] == 0, 'the folded text is NUL terminated'
    return ''.join(map(chr, cps[:-1]))


def fold_tests(ctx):
    """The folding: case, Latin diacritics, kana, widths, marks."""
    expect = ctx.expect
    m = Machine()
    cases = [
        ('Beyoncé', 'beyonce'), ('ÀÁÂÃÄÅ àáâãäå', 'aaaaaa aaaaaa'), ('Müller ÜBER', 'muller uber'), ('Straße', 'strasse'), ('Ørsted', 'orsted'),
        ('Æon æon', 'aeon aeon'), ('Łódź', 'lodz'), ('Þór', 'thor'), ('Œuvre', 'oeuvre'), ('Đorđe', 'dorde'), ('Çağlar', 'caglar'), ('İstanbul ıi', 'istanbul ii'),
        ('Ñandú', 'nandu'), ('Zażółć', 'zazolc'), ('Nguyễn Ánh', 'nguyen anh'), ('Ǎǐǒǔ', 'aiou'), ('ŠČŘŽ šč', 'scrz sc'),
        ('Café Müller', 'cafe muller'),                               # NFD: the combining marks go
        ('ЁЛКА Йод', 'елка йод'), ('ΑΘΗΝΑ Άλφα', 'αθηνα αλφα'),                     # Cyrillic and Greek lower case; ё is е
        ('ＡＢＣ１２３ ａｂｃ', 'abc123 abc'), ('a　b c\td', 'a b c d'),      # full-width Latin, every kind of space
        ('Don’t “Stop”', 'don\'t "stop"'), ('A–B', 'a-b'),
        ('周杰伦 Jay', '周杰伦 jay'), ('Café del Mar', 'cafe del mar'), ('', ''),
        ('カタカナ', 'かたかな'), ('ひらがな', 'ひらがな'), ('ｶﾀｶﾅ', 'かたかな'), ('ｱｲｳｴｵｦﾝ', 'あいうえおをん'), ('ｧｨｩｪｫｬｭｮｯ', 'ぁぃぅぇぉゃゅょっ'),
        ('ｶﾞｷﾞｸﾞ', 'がぎぐ'), ('ﾊﾟﾋﾟ ﾊﾞ', 'ぱぴ ば'), ('ｳﾞ', 'ゔ'), ('ヴァイオリン', 'ゔぁいおりん'), ('ガ ヅ', 'が づ'), ('ハ゜', 'ぱ'),
        ('が ぱ ゔ', 'が ぱ ゔ'), ('カ゛', 'が'), ('ー・', 'ー・'), ('ヽヾ', 'ゝゞ'),
        ('か', 'か'), ('ゆ゙', 'ゆ゙'.replace('゙', '')),               # a mark that composes to nothing is dropped
    ]
    bad = [(a, fold(m, a), b) for a, b in cases if fold(m, a) != b]
    expect(not bad, f'the folding of {len(cases)} texts (accents, ligatures, NFD, Cyrillic, Greek, kana, widths, spaces): {bad[:4]}')
    expect(fold(m, 'が') != fold(m, 'か') and fold(m, 'ガ') == fold(m, 'が') and fold(m, 'ｶﾞ') == fold(m, 'が') and fold(m, 'ｶ') == fold(m, 'か'),
           'a dakuten is kept: か and が differ, katakana and half-width katakana fold onto the hiragana of the same sound')
    n = fold(m, 'x' * 300, 160)
    expect(len(n) == 160 or len(n) == 159, f'a long text is cut at the room it has ({len(n)})')
    s = 'é' * 200
    expect(len(fold(m, s, 17)) in (16, 17), 'two-letter folds never write past the room')
    expect('a' in fold(m, '\xc3a\xe2\x82b'), 'invalid UTF-8 does not hang and keeps the letters')



def lib_for_query():
    songs = [('Halo', 'Beyoncé', 'I Am... Sasha Fierce'), ('Blue in Green', 'Miles Davis', 'Kind of Blue'), ('So What', 'Miles Davis', 'Kind of Blue'),
             ('Die Straße', 'Müller', 'Heimat'), ('Straight', 'Nobody', 'Blue Note'), ('カタカナ', 'ｱｲｳ', 'ひらがな'), ('Ørn', 'Sigur Rós', 'Ágætis byrjun'),
             ('Davis Cup', 'Someone', 'Else'), ('Anthem', 'Miles', 'Davis')]
    artists = ['Beyoncé', 'Miles Davis', 'Müller', 'Sigur Rós', 'Unknown Artist']
    albums = [('Kind of Blue', 'Miles Davis'), ('Heimat', 'Müller'), ('Ágætis byrjun', 'Sigur Rós'), ('Unknown Album', 'Unknown Artist')]
    m = opened(songs, artists, albums, playlists=['Miles Mix', 'Road Trip'])
    # the stock list's last rows are the "Unknown ..." ones (id -1), which are never results
    return m


def found(q):
    """The matches of a query by type: (songs, artists, albums, playlists) titles, read through each type's chip."""
    songs = [('Halo', 'Beyoncé', 'I Am... Sasha Fierce'), ('Blue in Green', 'Miles Davis', 'Kind of Blue'), ('So What', 'Miles Davis', 'Kind of Blue'),
             ('Die Straße', 'Müller', 'Heimat'), ('Straight', 'Nobody', 'Blue Note'), ('カタカナ', 'ｱｲｳ', 'ひらがな'), ('Ørn', 'Sigur Rós', 'Ágætis byrjun'),
             ('Davis Cup', 'Someone', 'Else'), ('Anthem', 'Miles', 'Davis')]
    artists = ['Beyoncé', 'Miles Davis', 'Müller', 'Sigur Rós', 'Unknown Artist']
    albums = [('Kind of Blue', 'Miles Davis'), ('Heimat', 'Müller'), ('Ágætis byrjun', 'Sigur Rós'), ('Unknown Album', 'Unknown Artist')]
    m = page_machine(songs, artists, albums, playlists=['Miles Mix', 'Road Trip'])
    m.class_lists[ARTISTS][-1] = artist_rec(m, 'Unknown Artist', -1)
    m.class_lists[ALBUMS][-1] = m.record(album='Unknown Album', artist='Unknown Artist', path='', title='Unknown Album', rid=-1)
    m.call(PSYMS['search_open'], count=40000000)
    typed(m, q)
    out = []
    for c in (CH_SONGS, CH_ARTISTS, CH_ALBUMS, CH_PLAYLISTS):
        chip(m, c)
        out.append(titles(m))
    return tuple(out)


def query_tests(ctx):
    """Which records a query finds: every term, any order, any field; folded on both sides; kana; the tiers; the unknown rows."""
    expect = ctx.expect
    s, a, al, pl = found('miles davis')
    expect(s == ['Blue in Green', 'So What', 'Anthem'] and a == ['Miles Davis'] and al == ['Kind of Blue'] and pl == [],
           f'two words: every term, in any field (the artist, the album): {s} {a} {al} {pl}')
    expect(found('davis miles') == (s, a, al, pl), 'the order of the words does not matter')
    expect(found('  MILES   davis ') == (s, a, al, pl), 'case and extra spaces do not matter')
    s, a, al, pl = found('davis')
    expect(s == ['Davis Cup', 'Blue in Green', 'So What', 'Anthem'] and a == ['Miles Davis'], f'one word: the titles that start with it come first, then the rest in the library order ({s})')
    expect(found('miles')[3] == ['Miles Mix'], 'the playlists are searched by name')
    expect(found('blue')[0] == ['Blue in Green', 'So What', 'Straight'] and found('blue')[2] == ['Kind of Blue'], f'a word in the album name: {found("blue")}')
    expect(found('kind blue')[0] == ['Blue in Green', 'So What'], 'two words of one field')
    expect(found('what davis')[0] == ['So What'] and found('what nobody')[0] == [], 'a term that matches nothing leaves nothing (AND)')
    for q in ('beyonce', 'BEYONCE', 'Beyoncé', 'beyoncé', 'BEYONCÉ'):
        r = found(q)
        expect(r[0] == ['Halo'] and r[1] == ['Beyoncé'], f'accent and case insensitive both ways: {q} -> {r[:2]}')
    expect(found('strasse')[0] == ['Die Straße'] and found('straße')[0] == ['Die Straße'] and found('STRASSE muller')[0] == ['Die Straße'], 'ß is ss, in the title; the artist ü is u')
    expect(found('orn')[0] == ['Ørn'] and found('sigur ros')[1] == ['Sigur Rós'], 'ø is o; ros finds Rós')
    expect(found('agætis')[2] == ['Ágætis byrjun'] and found('AGAETIS')[2] == ['Ágætis byrjun'] and found('agaetis byrjun')[2] == ['Ágætis byrjun'] and found('agtis')[2] == [],
           'Á is a, æ is ae (agaetis finds it, agtis does not)')
    for q in ('カタカナ', 'かたかな', 'ｶﾀｶﾅ', 'タカ'):
        expect(found(q)[0] == ['カタカナ'], f'katakana, hiragana and half-width katakana find each other: {q}')
    expect(found('ひらがな')[0] == ['カタカナ'] and found('ヒラガナ')[0] == ['カタカナ'] and found('ｱｲｳ')[0] == ['カタカナ'] and found('あいう')[0] == ['カタカナ'],
           'in the album and the artist too (the half-width artist ｱｲｳ is あいう)')
    expect(found('かたかな ひらがな あいう')[0] == ['カタカナ'], 'three terms')
    expect(found('')[0] == [] and found('   ')[0:2] == ([], []), 'an empty query finds nothing')
    expect(found('unknown')[1] == [] and found('unknown')[2] == [], 'the "Unknown Artist" and "Unknown Album" rows (id -1) are never results')
    expect(found('a' * 63)[0] == [], 'the longest query')
    expect(found('miles davis kind of blue what so what')[0] == ['So What'], 'eight terms are used')


def rank_tests(ctx):
    """Top Results: the best quality first, in each quality artists, albums, playlists, songs; the cap; a type chip shows its type only, best quality first, up to its cap."""
    expect = ctx.expect
    songs = [('Love Letter', 'Zed', 'Q'), ('Lovely', 'Zed', 'Q'), ('Love', 'Zed', 'Q'), ('I Love You', 'Zed', 'Q'), ('Nothing', 'Zed', 'Q')]
    artists = ['Lover Boy', 'Love', 'Be Loved', 'Other']
    albums = [('Love', 'Y'), ('Only Love', 'Y'), ('Lovesick', 'Y')]
    m = opened(songs, artists, albums, playlists=['Love', 'Mix'])
    typed(m, 'love')
    top = [(k, t) for (k, _), t in zip(rows(m), titles(m))]
    names = {ARTIST: 'artist', ALBUM: 'album', SONG: 'song', PLAYLIST: 'playlist'}
    got = [(names[k], t) for k, t in top]
    expect(got == [('artist', 'Love'), ('album', 'Love'), ('playlist', 'Love'), ('song', 'Love'),
                   ('artist', 'Lover Boy'), ('album', 'Lovesick'), ('song', 'Love Letter'), ('song', 'Lovely'),
                   ('artist', 'Be Loved'), ('album', 'Only Love'), ('song', 'I Love You')],
           f'Top Results: whole-name matches first (artist, album, playlist, song), then names that start with the query, then the rest, each in the library order ({got})')
    expect(state(m, 'chip') == CH_TOP, 'Top Results is the selected chip when the page opens')
    chip(m, CH_SONGS)
    expect(titles(m) == ['Love', 'Love Letter', 'Lovely', 'I Love You'] and all(k == SONG for k, _ in rows(m)), f'the Songs chip: songs only, best quality first ({titles(m)})')
    chip(m, CH_ARTISTS)
    expect(titles(m) == ['Love', 'Lover Boy', 'Be Loved'], 'the Artists chip')
    chip(m, CH_TOP)
    expect(len(rows(m)) == 11 and titles(m)[0] == 'Love', 'back to Top Results')
    # the caps: Top Results SE_CAP_TOP, a type chip its own cap
    songs = [(f'Love Song {i}', f'Artist {i % 3}', f'Album {i % 4}') for i in range(260)]
    artists = [f'Lover {i}' for i in range(130)]
    albums = [(f'Love Album {i}', 'Z') for i in range(130)]
    m = opened(songs, artists, albums, playlists=[f'Loved {i}' for i in range(120)])
    typed(m, 'love')
    expect(len(rows(m)) == D['SE_CAP_TOP'], f'Top Results has {D["SE_CAP_TOP"]} rows ({len(rows(m))})')
    for c, cap in ((CH_SONGS, D['SE_CAP_SONGS']), (CH_ARTISTS, D['SE_CAP_ARTISTS']), (CH_ALBUMS, D['SE_CAP_ALBUMS']), (CH_PLAYLISTS, D['SE_CAP_PLAYLISTS'])):
        chip(m, c)
        expect(len(rows(m)) == cap, f'chip {c}: its matches up to the cap {cap} ({len(rows(m))})')
    chip(m, CH_SONGS)
    expect(titles(m)[:3] == ['Love Song 0', 'Love Song 1', 'Love Song 10'] or titles(m)[0].startswith('Love Song'), 'the first matches of the library order')


def incremental_tests(ctx):
    """A query that extends the last one tests only the last matches; any other query scans the library."""
    expect = ctx.expect
    songs = [(f'{"ab" if i % 3 == 0 else "ac"}{i} tune {i % 7}', f'Artist {i % 5}', 'Album') for i in range(300)]
    m = opened(songs, ['Artist 1'], [('Album', 'Artist 1')])
    settle(m)
    def reads(m):
        before = sum(m.deque_reads.values())
        return before
    def apply(m, text):
        d0 = {h: n for h, n in m.deque_reads.items()}
        typed(m, text)
        return sum(n - d0.get(h, 0) for h, n in m.deque_reads.items())
    songs_h = m.word(PSYMS['se'] + OFF['lists'] + 4 * SONG)
    nc = lambda: state(m, 'nc', SONG)
    n_a = apply(m, 'a')
    expect(nc() == 300 and n_a >= 300, f'a first query scans the whole library ({n_a} record reads, {nc()} matches)')
    n_ac = apply(m, 'ac')
    expect(nc() == 200 and n_ac <= 300 + 12, f'"ac" extends "a": only its matches are tested ({n_ac} reads); 200 match')
    n_ac1 = apply(m, 'ac1')
    expect(nc() == 75 and n_ac1 <= 200 + 12, f'"ac1" extends "ac": only its 200 matches are read ({n_ac1}), {nc()} match')
    n_term = apply(m, 'ac1 tune')
    expect(nc() == 75 and n_term <= 75 + 12, f'a second term extends the query too ({n_term}: only the 75 are read)')
    n_back = apply(m, 'a')
    expect(n_back >= 300 and nc() == 300, f'deleting back to "a" is a new query: the library is scanned again, with the same answer ({n_back})')
    apply(m, 'ac')
    n_other = apply(m, 'ab')
    expect(n_other >= 300 and nc() == 100, f'a query that does not extend the last one scans the library ({n_other})')
    # the same answers as scanning from scratch
    apply(m, 'ac')
    a = apply(m, 'ac1')
    ref = opened(songs, ['Artist 1'], [('Album', 'Artist 1')])
    typed(ref, 'ac1')
    expect(titles_all(m, CH_SONGS) == titles_all(ref, CH_SONGS) and a < n_other, 'the filtered answer is the scanned one')
    expect(songs_h == m.word(PSYMS['se'] + OFF['lists'] + 4 * SONG), 'the song list is not read again by a query')


def titles_all(m, chip_k):
    """The titles of a type chip's rows (selects the chip, restores Top Results)."""
    chip(m, chip_k)
    t = titles(m)
    chip(m, CH_TOP)
    return t


def page_tests(ctx):
    """The page as it opens (keyboard up, empty), the rows' paint (thumbnails, texts, chevrons, separators), no results, the library read once."""
    expect = ctx.expect
    songs = [('Taylor Song', 'Taylor Swift', 'Folklore'), ('Other', 'Z', 'Y'), ('Swift Thing', 'Q', 'Folklore')]
    m = page_machine(songs, ['Taylor Swift', 'Zed'], [('Folklore', 'Taylor Swift'), ('Encore', 'Taylor Swift')], playlists=['Taylor Mix'], covers=[('Taylor Swift', 'Folklore')])
    expect(m.call(PSYMS['search_open'], count=40000000) == 0 and ('window_open', 'm1plus_search') in m.calls and ('window_open', 'm1plus_keyboard') not in m.calls,
           'search_open opens m1plus_search only: no separate keyboard page, so nothing flashes')
    expect(not [c for c in m.calls if c[0] in ('loadLocalClassList', 'loadAlbumList')], 'opening reads no library (it is read once the page has been shown)')
    shown = lambda n: (m.props[(m.widgets[n], 'visible')], m.props[(m.widgets[n], 'sensitive')])
    expect(shown('kb_pad') == (1, 1) and shown('kb_field') == (1, 1), 'the keyboard is up when the page opens')
    expect(any(c[0] == 'timer_add' and c[1] == PSYMS['se_tick'] and c[2] == TICK_MS for c in m.calls) and sum(1 for c in m.calls if c[0] == 'timer_add') == 1, 'one page timer')
    expect(rows(m) == [] and shown('label_status')[0] == 0 and shown('se_listview') == (0, 0), 'the empty state: no rows, no status text, the list hidden')
    expect(state(m, 'chip') == CH_TOP and m.props[(m.widgets['se_chip_hl'], 'visible')] == 1, 'Top Results is selected and its pill shown')
    m.call(PSYMS['se_tick'], count=900000000)
    expect([c[1] for c in m.calls if c[0] == 'loadLocalClassList'] == [ARTISTS, ALBUMS, PLAYLISTS, ALL], f'the first tick reads the four lists once, the songs last ({[c[1] for c in m.calls if c[0] == "loadLocalClassList"]})')
    ticks(m)
    expect(m.s32(pod.DATA['G_CLASS_TYPE'][0]) == ALL, 'the browsing class is the library\'s (0xf001): a stock page under this one reads its own list again when it comes back')
    expect(rows(m) == [] and shown('se_listview') == (0, 0), 'still empty after the library was read')
    typed(m, 'taylor')
    expect(not [c for c in m.calls if c[0] == 'loadLocalClassList'], 'a query reads no library')
    r = rows(m)
    expect([(k) for k, _ in r] == [ARTIST, ALBUM, PLAYLIST, SONG, SONG] or [k for k, _ in r][:1] == [ARTIST], f'rows ({r})')
    texts, styles, fills, blits = paint(m)
    names = [t[0] for t in texts]
    expect(names[0] == 'Taylor Swift' and 'Artist' in names, f'an artist row: the name over "Artist" ({names[:6]})')
    expect(names.count('Album · Taylor Swift') == 2, f'an album row: "Album · artist" ({names})')
    expect('Playlist' in names and 'Taylor Mix' in names, 'a playlist row: the name over "Playlist"')
    expect(any(n == 'Song · Taylor Swift' for n in names), 'a song row: "Song · artist"')
    seps = [f for f in fills if f[0] == O['LIST_HAIR']]
    expect(len(seps) == len(r) and all(f[1] == D['SE_TEXT_LEFT'] and f[3] == D['SE_SEP_END'] - D['SE_TEXT_LEFT'] for f in seps), 'a thin separator under every row, inset to the text')
    expect(len(blits) >= len(r), f'a thumbnail for every row in view ({len(blits)})')
    chev = [b for b in blits if (b[2][2], b[2][3]) == (10, 16)]
    expect(len(chev) == 4, f'a chevron on the artist, the two album and the playlist rows and none on the songs ({len(chev)})')
    # the thumbnails: lazily, one a tick; the artist's from their album
    m.calls = []
    m.call(PSYMS['se_tick'], count=900000000)
    loads = [c[1] for c in m.calls if c[0] == 'widget_load_image']
    cover = 'file://' + art_file(album_key('Taylor Swift', 'Folklore'))
    expect(len(loads) <= 1, f'at most one cover is decoded per tick ({loads})')
    for _ in range(12): m.call(PSYMS['se_tick'], count=900000000); loads += [c[1] for c in m.calls if c[0] == 'widget_load_image']
    expect(cover in loads and loads.count(cover) >= 2, f'the album and the artist take the library\'s cover file; the others have none ({loads})')
    # no results
    typed(m, 'zzzz')
    expect(rows(m) == [] and shown('label_status')[0] == 1 and said(m, 'label_status') == 'No Results' and shown('se_listview') == (0, 0), 'no result: "No Results" shows, the list is hidden')
    expect(paint(m)[0] == [], 'nothing to paint')
    tap(m, 40)
    expect(not [c for c in m.calls if c[0] in ('navigator_to_with_context', 'window_open', 'loadSongList')], 'a tap on the empty page does nothing')
    typed(m, '')
    expect(rows(m) == [] and shown('label_status')[0] == 0, 'an emptied field goes back to the empty state')
    # an empty library
    m = page_machine((), (), ())
    m.class_lists[ARTISTS] = []; m.class_lists[ALBUMS] = []; m.class_lists[ALL] = []
    m.call(PSYMS['search_open'], count=40000000)
    typed(m, 'love')
    expect(rows(m) == [] and said(m, 'label_status') == 'No Results', 'an empty library: No Results')
    # destroy frees and forgets the state; a second page opens
    m.call(PSYMS['se_on_destroy'], count=2000000)
    expect(state(m, 'win') == 0 and state(m, 'rows') == 0 and 'free' in m.names() and 'timer_remove' in m.names() or state(m, 'win') == 0, 'destroy frees the copies and the rows, removes the timer and clears the state')
    expect(m.call(PSYMS['search_open'], count=40000000) == 0 and state(m, 'win') == m.window, 'a second page opens after the first was destroyed')
    expect(m.call(PSYMS['search_open'], count=40000000) == 0xffffffff, 'a second search_open while a page exists refuses (the callers fall back to the stock page)')
    m = page_machine(); m.windows['m1plus_search'] = 0
    expect(m.call(PSYMS['search_open'], count=40000000) == 0xffffffff and state(m, 'win') == 0, 'a window that will not open: -1, no state')
    m = page_machine(); del m.widgets['se_chips']
    expect(m.call(PSYMS['search_open'], count=40000000) == 0xffffffff and ('navigator_back',) in m.calls, 'an asset that is not ours is closed again')


def chips_tests(ctx):
    """The chip row: one selected, the pill under it, a tap selects, a drag scrolls, the row is wider than the screen."""
    expect = ctx.expect
    m = opened([('Love', 'A', 'B')], ['Love'], [('Love', 'A')], playlists=['Love'])
    typed(m, 'love')
    widths = [width(m.tr(PS.CHIPS[i]) if False else PS.CHIPS[i], D['SE_CHIP_PX']) for i in range(5)]
    lay = PS.chip_layout(widths)
    xs = [state(m, 'chip_x', i) for i in range(6)]
    expect([x for x, _ in lay] == xs[:5] and xs[5] - D['SE_CHIP_GAP'] == lay[-1][0] + lay[-1][1], f'the chips are placed from the texts\' widths in the chip font ({xs} against {lay})')
    end = PS.chips_end(lay)
    expect(end > 320, f'the row is wider than the screen and scrolls ({end})')
    hl = m.widgets['se_chip_hl']
    geo = lambda: tuple(m.props[(hl, k)] for k in 'xywh')
    expect(geo()[0] == lay[0][0] and geo()[2] == lay[0][1] and geo()[1] == D['SE_CHIP_Y'] and geo()[3] == D['SE_CHIP_H'], f'the pill is under Top Results ({geo()})')
    # a tap on a chip selects it (the chip row's own touch handler)
    def chips_touch(kind, x, t=1000):
        e = m.alloc(0x30); m.u.mem_write(e, bytes(0x30))
        m.setword(e, {'down': 0xff, 'move': 0x101, 'up': 0x103, 'abort': 0x107}[kind]); m.setword(e + 8, t); m.setword(e + 0x18, x); m.setword(e + 0x1c, 30 + D['SE_CHIPS_Y'] + 10)
        fn, ctx_ = m.bound[(m.widgets['se_chips'], {'down': O['EVT_POINTER_DOWN'], 'move': O['EVT_POINTER_MOVE'], 'up': O['EVT_POINTER_UP'], 'abort': O['EVT_POINTER_ABORT']}[kind])]
        m.call(fn, a0=ctx_, a1=e, count=40000000)
    x2 = lay[2][0] + lay[2][1] // 2
    chips_touch('down', x2); chips_touch('up', x2, 1080)
    expect(state(m, 'chip') == CH_ALBUMS and titles(m) == ['Love'] and all(k == ALBUM for k, _ in rows(m)), 'a tap on Albums selects it: its rows only')
    expect(geo()[0] == lay[2][0] - state(m, 'chip_sx') and geo()[2] == lay[2][1], 'the pill moves under it')
    expect(state(m, 'chip') in range(5), 'exactly one chip is selected')
    chips_touch('down', 250); chips_touch('move', 250 - 8, 1030); chips_touch('move', 250 - 60, 1060); chips_touch('up', 250 - 60, 1090)
    sx = state(m, 'chip_sx')
    expect(sx == 60 and state(m, 'chip') == CH_ALBUMS, f'a drag of the row scrolls it and selects nothing ({sx})')
    chips_touch('down', 250); chips_touch('move', 250 - 400, 1030); chips_touch('up', 250 - 400, 1090)
    expect(state(m, 'chip_sx') == end - 320, 'the scroll stops at the end of the row')
    chips_touch('down', 100); chips_touch('move', 100 + 900, 1030); chips_touch('up', 100 + 900, 1090)
    expect(state(m, 'chip_sx') == 0, 'and at its start')
    # the paint: the selected chip in the dark style over its pill, the others white
    ev = m.alloc(0x40); m.u.mem_write(ev, bytes(0x40)); m.setword(ev + O['EVENT_PAINT_CANVAS'], m.canvas)
    m.texts.clear(); m.text_styles.clear()
    m.call(m.bound[(m.widgets['se_chips'], O['EVT_AFTER_PAINT'])][0], a0=0, a1=ev, count=2000000)
    on = [t for t, s in zip(m.texts, m.text_styles) if s == 'label_chip_on']
    expect([t[0] for t in on] == ['Albums'] and len(m.texts) >= 4, f'the selected chip is painted in the dark style ({[t[0] for t in m.texts]})')
    # selecting a chip does not read the library again
    m.calls = []
    chip(m, CH_SONGS)
    expect(not [c for c in m.calls if c[0] in ('loadLocalClassList', 'loadAlbumList')], 'a chip filters the matches already known')
    for loc in pod_i18n.LOCALES:   # the chips' texts: every chip is at least its own text wide in every language (the row scrolls)
        ws = [width(pod_i18n.TEXT[k][loc], D['SE_CHIP_PX']) for k in PS.CHIPS]
        expect(all(w < 200 for w in ws), f'{loc}: the chips\' texts are short enough for a chip ({max(ws)})')


def chip_cover_tests(ctx):
    """Switching chips after the covers of the first tab were loaded (the page's timer has ended): the new tab's rows get their thumbnails, loaded on the timer, which the paint of the new rows starts again."""
    expect = ctx.expect
    songs = [('Taylor Song', 'Taylor Swift', 'Folklore'), ('Taylor Two', 'Taylor Swift', 'Folklore')]
    m = opened(songs, ['Taylor Swift'], [('Folklore', 'Taylor Swift')], playlists=['Taylor Mix'], covers=[('Taylor Swift', 'Folklore')])
    settle(m)
    typed(m, 'taylor')
    paint(m); ticks(m)
    expect(state(m, 'timer') == 0, 'the first tab\'s covers are loaded and the timer has ended')
    cover = 'file://' + art_file(album_key('Taylor Swift', 'Folklore'))
    for k, kind in ((CH_SONGS, SONG), (CH_ALBUMS, ALBUM), (CH_ARTISTS, ARTIST), (CH_TOP, None)):
        m.calls = []
        chip(m, k)
        paint(m)
        expect(any(c[0] == 'timer_add' and c[1] == PSYMS['se_tick'] for c in m.calls), f'chip {k}: the new rows start the page\'s timer')
        loads = []
        for _ in range(12):   # each call resets m.calls: collect per tick
            m.call(PSYMS['se_tick'], count=900000000); loads += [c[1] for c in m.calls if c[0] == 'widget_load_image']
        want = len([1 for kk, _ in rows(m) if kk != PLAYLIST])
        expect(loads.count(cover) == want, f'chip {k}: every row with a cover gets it ({loads.count(cover)} of {want})')


def live_tests(ctx):
    """Live search: the debounce on the page's one timer, the keyboard's own keys, hiding and showing the pad."""
    expect = ctx.expect
    kb = sibling('keyboard')
    songs = [('Miles Song', 'Miles Davis', 'Kind of Blue'), ('Other', 'Z', 'Y')]
    m = opened(songs, ['Miles Davis'], [('Kind of Blue', 'Miles Davis')])
    settle(m)
    # typing M-i-l-e-s on the embedded pad
    m.calls = []
    kb.typ(m, 'Mi')
    expect(kb.said(m, 'kb_text') == 'Mi' and state(m, 'wait') == DEBOUNCE, f'the keys type into the field and the countdown starts ({kb.said(m, "kb_text")}, {state(m, "wait")})')
    expect(rows(m) == [], 'nothing is searched while keys are being typed')
    expect(m.call(PSYMS['se_tick'], count=900000000) == RET_REPEAT and state(m, 'wait') == DEBOUNCE - 1, 'a tick counts down')
    kb.typ(m, 'l')
    expect(state(m, 'wait') == DEBOUNCE, 'another key restarts the countdown')
    for i in range(DEBOUNCE - 1): m.call(PSYMS['se_tick'], count=900000000)
    expect(rows(m) == [] and state(m, 'wait') == 1, f'{DEBOUNCE - 1} ticks later it is still waiting')
    m.call(PSYMS['se_tick'], count=900000000)
    expect(len(rows(m)) >= 1 and titles(m)[0] == 'Miles Davis', f'after {DEBOUNCE} ticks ({DEBOUNCE * TICK_MS} ms) without a key the results show ({titles(m)})')
    expect(sum(1 for c in m.calls if c[0] == 'timer_add') <= 1, 'one timer for the whole page: no second timer is started while it runs')
    expect(DEBOUNCE * TICK_MS == 200, 'the debounce is 200 ms')
    # delete goes back through the same path
    kb.press(m, 'kb_del'); kb.press(m, 'kb_del')
    ticks(m)
    expect(kb.said(m, 'kb_text') == 'M' and titles(m, ARTIST) == ['Miles Davis'], 'delete is live too')
    kb.press(m, 'kb_clear') if False else m.click('kb_clear')
    ticks(m)
    expect(rows(m) == [] and kb.said(m, 'kb_text') == '', 'the clear disc empties the field and the results')
    # the same text again (a layer switch repeats the callback with the same text) starts nothing
    m.call(PSYMS['se_on_text'], a0=m.cstr(''), count=2000000)
    expect(state(m, 'wait') == 0, 'an unchanged text starts no countdown')
    # hiding and showing the pad
    kb.typ(m, 'M')
    ticks(m)
    pad = lambda: (m.props[(m.widgets['kb_pad'], 'visible')], m.props[(m.widgets['kb_pad'], 'sensitive')])
    content = state(m, 'content')
    expect(pad() == (1, 1) and content >= len(rows(m)) * ROW_H + 180, f'the keyboard up: the content is padded by the pad\'s height ({content})')
    kb.press(m, 'kb_go')
    expect(pad() == (0, 0) and m.props[(m.widgets['kb_caret'], 'visible')] == 0, 'the action key hides the keyboard (the pad takes no touch, the caret goes)')
    expect(state(m, 'content') == len(rows(m)) * ROW_H + D['SE_BOTTOM'] or state(m, 'content') == len(rows(m)) * ROW_H + 12, f'the content is no longer padded ({state(m, "content")})')
    expect(kb.said(m, 'kb_text') == 'M', 'the text stays')
    # a tap on the field brings it back
    e = m.alloc(0x30); m.u.mem_write(e, bytes(0x30)); m.setword(e, O['EVT_POINTER_UP'])
    fn, c = m.bound[(m.widgets['kb_field'], O['EVT_POINTER_UP'])]
    m.call(fn, a0=c, a1=e, count=4000000)
    expect(pad() == (1, 1) and m.props[(m.widgets['kb_caret'], 'visible')] == 1, 'a tap on the field shows the keyboard again')
    expect(state(m, 'content') >= len(rows(m)) * ROW_H + 180, 'and pads the content again')
    # dragging the list hides it: a press on the list that the scroll_view takes (the abort)
    m.touch('down', 100, LIST_Y0 + 20, 1000, fn='se_on_down', count=30000000)
    m.call(PSYMS['se_on_abort'], count=2000000)
    expect(pad() == (0, 0), 'a drag of the results list hides the keyboard')
    m.call(m.bound[(m.widgets['kb_field'], O['EVT_POINTER_UP'])][0], a0=0, a1=e, count=4000000)
    m.call(PSYMS['se_on_abort'], count=2000000)
    expect(pad() == (1, 1), 'an abort with no press on the list (the page went behind another) leaves the keyboard')
    m.touch('down', 100, LIST_Y0 + 20, 1000, fn='se_on_down', count=30000000)
    m.touch('up', 100, LIST_Y0 + 20, 1080, fn='se_on_up', count=30000000)
    expect(pad() == (1, 1), 'a tap on a row leaves the keyboard as it is')
    # a hidden pad takes no key
    kb.press(m, 'kb_go')
    expect(pad() == (0, 0), 'hidden again')
    # the strip of the Chinese layer is hidden with the pad and comes back only with candidates
    expect(m.props[(m.widgets['kb_strip'], 'visible')] == 0, 'no candidate strip without candidates')
    # Back (the X) leaves: the page closes, the keyboard and the timer go with it
    m.calls = []
    m.click('btn_return')
    expect(('navigator_back',) in m.calls, 'the X goes back to the caller')
    m.call(PSYMS['se_on_destroy'], count=2000000)
    expect(('timer_remove', 0x777) in m.calls or 'timer_remove' in m.names() or state(m, 'timer') == 0, 'the destroy removes the timer')
    expect(state(m, 'win') == 0 and m.word(PSYMS['kb']) == 0, 'the page and the keyboard state are gone')
    # the keyboard page can be opened afterwards (the embedded one released the single keyboard)
    expect(kb.kopen(m, ph='x') == 0, 'keyboard_open works after the embedded keyboard was detached')


def tap_tests(ctx):
    """A tap: a song plays in the library's order, an artist opens Cover Flow, an album our album page, a playlist our Songs page; a drag or an abort does nothing; a stale list is read again."""
    expect = ctx.expect
    songs = [('Alpha one', 'Ann', 'First'), ('Alpha two', 'Bob', 'Second'), ('Beta', 'Ann', 'First')]
    def fresh(**kw):
        m = opened(songs, ['Alphaville', 'Ann'], [('Alpha Album', 'Ann'), ('Gamma', 'Bob')], playlists=['Alpha Mix'], **kw)
        m.artist_albums['Alphaville'] = [m.record(album='X', artist='Alphaville', path='/mnt/mmc/a/1.flac', rid=7)]
        typed(m, 'alpha')
        return m
    m = fresh()
    r = rows(m)
    # Top Results: [artist Alphaville, album Alpha Album, playlist Alpha Mix, song one, song two]
    expect([k for k, _ in r] == [ARTIST, ALBUM, PLAYLIST, SONG, SONG], f'the rows ({r})')
    y_of = lambda i: i * ROW_H + ROW_H // 2
    tap(m, y_of(4))        # Alpha two
    played = getattr(m, 'played', None)
    expect(played and [m.read_cstr(m.word(q + O['REC_TITLE'])) for q in played[0]] == ['Alpha one', 'Alpha two', 'Beta'] and played[1] == 1,
           f'a song: the library in its order is the queue, Now Playing at the song ({played and len(played[0])})')
    ctxs = [c for c in m.calls if c[0] == 'navigator_to_with_context' and c[1] == 'playing_page']
    expect(ctxs and ctxs[0][2] == 1 and ctxs[0][3] == ALL, f'class 0xf001 ({ctxs})')
    expect(('loadSongList', '1.flac', 0, ALL) in m.calls, 'loadSongList of the Songs page\'s class from the song')
    tap(m, y_of(3))
    expect([c for c in m.calls if c[0] == 'navigator_to_with_context' and c[1] == 'playing_page'][0][2] == 0, 'the first song plays from index 0')
    m.present.discard('/mnt/mmc/m/0.flac')
    tap(m, y_of(3))
    expect(not [c for c in m.calls if c[0] == 'navigator_to_with_context' and c[1] == 'playing_page'] and any(c[0] == 'toast' for c in m.calls), 'a missing file starts nothing and says so')
    m = fresh()
    tap(m, y_of(1))        # the album
    expect(('navigator_to_with_context', 'albuminfo_page', ALBUMS, 0) in m.calls and ('loadAlbumList', ALBUMS, 0, '') in m.calls, 'an album: the Albums row sequence (cc_open_album) on its stock row')
    names = [c[0] for c in m.calls]
    expect(names.count('albumcoverinfo_init') == 1 and names.count('batchadd_albumcover_task') == 1 and names.index('albumcoverinfo_init') < names.index('batchadd_albumcover_task') < names.index('navigator_to_with_context'),
           'the album page gets its cover task list once, from the album list (init, then the thread released), and only from the tap: the page\'s queries (the library read) never touch it')
    m = fresh()
    tap(m, y_of(0))        # the artist
    expect(('window_open', 'm1plus_cover') in m.calls and any(c[0] == 'loadAlbumList' and c[1] == ARTISTS and c[3] == 'Alphaville' for c in m.calls), 'an artist: Cover Flow on that artist (coverflow_artist)')
    m = fresh()
    tap(m, y_of(2))        # the playlist
    expect(any(c[0] == 'window_open' and c[1] == 'm1plus_songs' for c in m.calls) or any(c[0] == 'navigator_to_with_context' for c in m.calls), 'a playlist opens our Songs page (or the stock one)')
    # the artist that is the second stock row opens itself, not row 0
    m = opened(songs, ['Zed', 'Alphaville'], [('Alpha Album', 'Ann')])
    m.artist_albums['Alphaville'] = [m.record(album='X', artist='Alphaville', path='/mnt/mmc/a/1.flac', rid=7)]
    typed(m, 'alpha')
    tap(m, ROW_H // 2)
    expect(any(c[0] == 'loadAlbumList' and c[3] == 'Alphaville' for c in m.calls), 'the tap opens the artist it shows, not the stock row 0')
    # a drag, an abort, a press that leaves the row
    m = fresh()
    tap(m, 70, dy=15)
    expect(not [c for c in m.calls if c[0] in ('navigator_to_with_context', 'window_open')], 'a lift 15 px from the press is a drag: nothing opens')
    m.touch('down', 100, LIST_Y0 + 70, 1000, fn='se_on_down', count=30000000)
    expect(state(m, 'press') == 2, 'a press shows the row pressed')
    m.call(PSYMS['se_on_abort'], count=2000000)
    expect(state(m, 'press') == 0, 'an abort takes the press away')
    # the stock list replaced under the page
    m = fresh()
    n_before = len(rows(m))
    m.setword(SHOWLIST, m.new_deque([]))        # another page's query
    m.calls = []
    tap(m, y_of(4))
    expect(not [c for c in m.calls if c[0] in ('navigator_to_with_context', 'loadSongList')], 'a stale song list: the tap is lost')
    m.call(PSYMS['se_tick'], count=900000000)
    expect(('loadLocalClassList', ALL) in m.calls and len(rows(m)) == n_before, 'the page reads the library again (its timer) and has the same rows')
    ticks(m)
    m.setword(SHOWLIST, m.new_deque([]))
    m.call(m.bound[(m.window, O['EVT_WINDOW_TO_FG'])][0], count=900000000)
    m.call(PSYMS['se_tick'], count=900000000)
    expect(('loadLocalClassList', ALL) in m.calls, 'to the foreground with a replaced list: read again')
    ticks(m)
    m.calls = []
    m.call(m.bound[(m.window, O['EVT_WINDOW_TO_FG'])][0], count=900000000)
    expect(not [c for c in m.calls if c[0] == 'loadLocalClassList'] and state(m, 'wait') == 0, 'to the foreground with the list still ours: nothing is read')
    m.setword(SHOWLIST, m.new_deque([]))
    m.calls = []
    tap(m, y_of(0))
    expect(('window_open', 'm1plus_cover') in m.calls, 'an artist still opens when the song list was replaced (the page keeps its own copy)')


def perf_tests(ctx):
    """A big library: the first query (a full scan), an extending query, a shortening one, and the first tick that reads the library."""
    expect = ctx.expect
    for count in (5000, 20000):
        words = ('qzebra', 'alpha', 'beta', 'gamma', 'delta', 'omega', 'sigma', 'theta')   # one title in eight has the rare word the first query is for
        songs = [(f'{words[i % 8]} {i} Ünder ñandú', f'Artist {i % 300}', f'Album {i % 800}') for i in range(count)]
        m = opened(songs, [f'Artist {i}' for i in range(300)], [(f'Album {i}', f'Artist {i % 300}') for i in range(800)])
        m.count()
        m.call(PSYMS['se_tick'], count=900000000)
        load = m.icount
        m.call(PSYMS['se_on_text'], a0=m.cstr('qz'), count=2000000)
        for _ in range(D['SE_DEBOUNCE']): m.call(PSYMS['se_tick'], count=900000000)
        first = m.icount
        m.call(PSYMS['se_on_text'], a0=m.cstr('qzeb'), count=2000000)
        for _ in range(D['SE_DEBOUNCE']): m.call(PSYMS['se_tick'], count=900000000)
        ext = m.icount
        m.call(PSYMS['se_on_text'], a0=m.cstr('qzeb 4'), count=2000000)
        for _ in range(D['SE_DEBOUNCE']): m.call(PSYMS['se_tick'], count=900000000)
        ext2 = m.icount
        m.call(PSYMS['se_on_text'], a0=m.cstr('x'), count=2000000)
        for _ in range(D['SE_DEBOUNCE']): m.call(PSYMS['se_tick'], count=900000000)
        scan = m.icount
        print(f'PERF {count}: read {load / 1e6:.1f} M, first query "qz" {first / 1e6:.1f} M, "qzeb" (extends) {ext / 1e6:.1f} M, "qzeb 4" {ext2 / 1e6:.1f} M, "x" (a scan) {scan / 1e6:.1f} M')
        per = scan / count
        expect(per < 6000, f'{count} songs: a full scan costs {scan / 1e6:.1f} M payload instructions ({per:.0f} a song)')
        expect(ext < first * 0.5 and ext2 < first * 0.5, f'{count} songs: an extending query ({ext / 1e6:.1f} M) and the next one ({ext2 / 1e6:.1f} M) cost under half of the first scan ({first / 1e6:.1f} M)')
        expect(load < 3_000_000, f'{count} songs: the first tick does not search ({load / 1e6:.2f} M besides the stock queries)')


def entry_tests(ctx):
    """The Songs page's Search and the album page's search button."""
    expect = ctx.expect
    songs_t = sibling('songs')
    def songs_page():
        m = songs_t.songs_machine([('A', 'X', 'Y')], albums=())
        songs_t.open_page(m)
        search_widgets(m)           # the Search page's widgets (a few names are shared with the Songs page: the clicks are what matter here)
        return m
    m = songs_page()
    m.calls = []
    m.click('btn_search', count=40000000)
    expect(('window_open', 'm1plus_search') in m.calls and not [c for c in m.calls if c[0] == 'navigator_to_with_context'] and ('window_open', 'm1plus_keyboard') not in m.calls,
           'the Songs page\'s Search opens the Search page (the keyboard is on it), not the stock search page or a keyboard page')
    m = songs_page()
    m.windows['m1plus_search'] = 0
    m.calls = []
    m.click('btn_search', count=40000000)
    expect(('navigator_to_with_context', 'search_page', 0) in m.calls, 'where the Search page will not open the stock search page does')
    m = songs_page()
    m.calls = []
    m.setword(PSYMS['se'], 0x1234)    # a Search page is under this one
    m.click('btn_search', count=40000000)
    expect(('navigator_to_with_context', 'search_page', 0) in m.calls and ('window_open', 'm1plus_search') not in m.calls, 'a Search page already under: the stock page (one at a time)')
    m.setword(PSYMS['se'], 0)
    # the album page is untouched by Search: its header hook binds nothing on the bar and adds no timer but the tint poll
    alb = sibling('albuminfo')
    am = alb.AlbumMachine()
    band = am.new_widget('view', 0, 0, 0, 320, 50)
    am.wname[band] = 'navigationbar_view'; am.widgets['navigationbar_view'] = band
    am.header(tracks=3)
    expect(not am.bound.get(band) and all(c[1] == PSYMS['ah_tick'] for c in am.calls if c[0] == 'timer_add')
           and not any(k in PSYMS for k in ('ah_on_search', 'ah_hide_search', 'ah_on_bar_paint')),
           'the album page: nothing of Search (no button, no bar handler, no timer)')


def return_tests(ctx):
    """Back from Search to the page under it (the Songs page): its covers load again. Search's queries replace the stock list, so the page reads it again on its to-foreground event."""
    expect = ctx.expect
    st = sibling('songs')
    titles_ = [f'Song {i}' for i in range(12)]
    m = st.songs_machine([(t, f'Artist {i}', f'Album {i}') for i, t in enumerate(titles_)], albums=())
    m.class_lists[ARTISTS] = []; m.class_lists[PLAYLISTS] = []; m.playlists = []
    st.open_page(m)
    blits = st.settle(m)[0]
    colours = [st.colour(i) for i in range(12)]
    covered = lambda bl: sum(1 for b in bl if b[2][2] == O['LIST_ART'] and b[0] in m.bitmaps and any(st.near(st.pixel(m, b[0], 26, 26), c) for c in colours))
    n0 = covered(blits)
    expect(n0 >= 4, f'the Songs page shows its covers before Search ({n0})')
    keep = (m.sv, m.view, m.window, m.canvas, m.oy_canvas, m.rail)
    search_widgets(m)
    m.sv, m.view, m.window, m.canvas, m.oy_canvas, m.rail = keep
    m.window = keep[2]
    m.click('btn_search', count=40000000)
    expect(('window_open', 'm1plus_search') in m.calls, 'Search opened over the Songs page')
    m.call(PSYMS['se_on_text'], a0=m.cstr('song'), count=2000000)
    ticks(m)
    m.call(PSYMS['se_on_destroy'], count=2000000)
    m.calls = []
    m.call(PSYMS['sg_on_fg'], a0=0, a1=0, count=900000000)
    blits = st.settle(m)[0]
    expect(covered(blits) == n0, f'back from Search the Songs page loads its covers again ({covered(blits)} of {n0})')
    # the stock list refilled in place (the same deque object, size and first record, as the library query leaves it) while covers were still to load: the loader ran into the
    # replaced list while Search was up and stopped; the page's list is valid again when it is back, so only the to-foreground event can start it
    m = st.songs_machine([(t, f'Artist {i}', f'Album {i}') for i, t in enumerate(titles_)], albums=())
    st.open_page(m)
    mine = m.word(SHOWLIST)
    m.setword(SHOWLIST, m.new_deque([]))      # Search's artists / albums queries are in *pdeq_showlist
    expect(not any(c[0] == 'timer_add' and c[1] == PSYMS['sg_on_load'] for c in st.tick(m)), 'the loader stops on a replaced list')
    m.setword(SHOWLIST, mine)                 # its songs query is last
    m.calls = []
    m.call(PSYMS['sg_on_fg'], a0=0, a1=0, count=900000000)
    expect(any(c[0] == 'timer_add' and c[1] == PSYMS['sg_on_load'] for c in m.calls), 'back with covers still to load: the loader runs again')


def embed_tests(ctx):
    """keyboard_attach: the pad of another page. The page's widgets are found by name, the text goes to the callback, the action key to the other, nothing is opened or closed; detach lets go."""
    expect = ctx.expect
    kb = sibling('keyboard')
    m = opened([('A', 'B', 'C')], [], [])
    expect(kb.said(m, 'kb_hint') == 'Search' and kb.said(m, 'kb_text') in (None, ''), 'the field shows the placeholder (Search)')
    expect(kb.keys(m)[0] == 'Q', 'an empty field starts on capitals (the keyboard\'s rule), as on the keyboard page')
    kb.typ(m, 'Ab')
    expect(kb.said(m, 'kb_text') == 'Ab', 'keys type into the embedded field')
    c_geo = lambda: kb.geo(m, 'kb_caret')
    expect(c_geo()[0] == D['SE_TEXT_X'] + width('Ab', 18) + 1 and c_geo()[1] == D['SE_CARET_Y'], f'the caret follows the measured width from the page\'s text x ({c_geo()})')
    expect(('navigator_back',) not in m.calls and not [c for c in m.calls if c[0] == 'window_open'], 'typing opens and closes no page')
    for name in ('kb_pad', 'kb_strip', 'kb_stem', 'kb_pop'): assert name in m.widgets
    # Chinese: the committed text only
    m.calls = []
    kb.press(m, 'kb_mode'); kb.press(m, 'kb_k0')
    expect(kb.said(m, 'kb_text') == 'Ab1', 'the 123 page types into the same field')
    # a second attach or an open while attached refuses
    expect(m.call(PSYMS['keyboard_attach'], a0=m.window, a1=0, a2=1, a3=2, count=400000) == 0xffffffff, 'a second keyboard_attach refuses')
    expect(kb.kopen(m, ph='x') == -1, 'keyboard_open refuses while the pad is embedded (one keyboard at a time)')
    # keyboard_open unchanged on a fresh machine: the page, title, Done, Back
    m2 = kb.keyboard_machine()
    expect(kb.kopen(m2, title='New playlist', ph='Name', flags=2) == 0 and ('window_open', 'm1plus_keyboard') in m2.calls and kb.said(m2, 'kb_go') == 'Done', 'keyboard_open still opens its own page, with its title and the Done key')
    kb.typ(m2, 'Mix'); m2.calls = []
    kb.press(m2, 'kb_go')
    expect(('navigator_back',) in m2.calls and [c for c in m2.calls if c[0] == 'atoi'] == [('atoi', 'Mix')], 'and Search / Done still closes it and calls on_done with the text')
    # a missing widget: attach fails and leaves nothing
    m3 = page_machine()
    del m3.widgets['kb_clear']
    expect(m3.call(PSYMS['search_open'], count=40000000) == 0xffffffff and m3.word(PSYMS['kb']) == 0, 'an asset without the field\'s widgets: the page closes again and no keyboard state is left')


def asset_tests(ctx):
    """The built page: names, geometry (the model's), neutral colours, hidden decorations, the widgets the keyboard needs."""
    expect = ctx.expect
    t = awtk_ui.parse(open(ASSET, 'rb').read())
    by = {w.name: w for w in t.walk() if w.name}
    need = ('se_listview', 'se_scrollview', 'view_grid', 'label_status', 'label_title', 'label_row_title', 'label_row_sub', 'label_chip', 'label_chip_on', 'btn_return', 'se_chips', 'se_chip_hl',
            'se_sep', 'kb_field', 'kb_mag', 'kb_hint', 'kb_text', 'kb_caret', 'kb_clear', 'kb_pad', 'kb_strip', 'kb_stem', 'kb_pop', 'kb_pop_l', 'kb_cands', 'kb_chl', 'kb_go', 'kb_lang')
    expect(t.name == 'm1plus_search_page' and all(n in by for n in need), f'm1plus_search has every widget the payload and the keyboard look up ({[n for n in need if n not in by]})')
    kbt = awtk_ui.parse(open(os.path.join(RAW, 'ui', 'm1plus_keyboard.bin'), 'rb').read())
    kby = {w.name: w for w in kbt.walk() if w.name}
    same = [n for n in kby if n.startswith('kb_') and n not in ('kb_field', 'kb_mag', 'kb_hint', 'kb_text', 'kb_caret', 'kb_clear')]
    ok = all(n in by and (by[n].x, by[n].y, by[n].w, by[n].h) == (kby[n].x, kby[n].y, kby[n].w, kby[n].h) and by[n].props == kby[n].props for n in same)
    expect(ok, 'the pad, the strip and the pop-up are the keyboard page\'s own widgets, byte for byte (one builder)')
    f = by['kb_field']
    expect((f.x, f.y, f.w, f.h) == (D['SE_FIELD_X'], D['SE_FIELD_Y'], D['SE_FIELD_W'], D['SE_FIELD_H']) and f.get('style:normal:round_radius') == str(D['SE_FIELD_R']) and f.get('sensitive') == 'true',
           'the field is a rounded capsule at the model\'s place, sensitive (its clear button needs it; a tap on it brings the keyboard back)')
    expect((by['kb_text'].x, by['kb_text'].w, by['kb_hint'].x) == (D['SE_TEXT_X'], D['SE_TEXT_W'], D['SE_TEXT_X']) and by['kb_clear'].x == D['SE_FIELD_W'] - D['SE_CLEAR_W'] and by['kb_caret'].y == D['SE_CARET_Y'],
           'the text, hint, clear button and caret are where the payload is told they are (keyboard_attach\'s arguments)')
    c = by['btn_return']
    expect((c.x, c.y, c.w, c.h) == (D['SE_CLOSE_X'], D['SE_CLOSE_Y'], D['SE_CLOSE_W'], D['SE_CLOSE_H']) and [c.get(f'style:{s}:icon') for s in ('normal', 'pressed')] == ['se_close', 'se_close_down'], 'the round X button at the right: the flat 36 px disc se_close, centred on the field')
    expect(f.x + f.w < c.x and c.x + c.w <= 320 and by['kb_clear'].x + by['kb_clear'].w == f.w, 'the field and the X do not overlap and fit the screen')
    ch = by['se_chips']
    expect((ch.y, ch.h, ch.w) == (D['SE_CHIPS_Y'], D['SE_CHIPS_H'], 320) and ch.get('sensitive') != 'false' and by['se_chip_hl'].get('sensitive') == 'false' and by['se_chip_hl'].get('style:normal:bg_color') == PS.CHIP_ON_RGB,
           'the chip row takes the touches; its pill is behind and insensitive, light grey')
    expect(by['se_sep'].y == D['SE_SEP_Y'] and by['se_sep'].h == 1 and by['se_sep'].y < D['SE_LIST_Y'], 'the line under the chips')
    lv = by['se_listview']
    expect((lv.y, lv.h, by['view_grid'].h) == (D['SE_LIST_Y'], D['SE_LIST_H'], D['SE_LIST_H']) and lv.y + lv.h == 450, 'the list runs from under the chips to the window\'s bottom (the keyboard covers its lower part)')
    names = [w.name for w in t.children]
    expect(names.index('se_listview') < names.index('kb_pad') and names[-4:] == ['kb_pad', 'kb_strip', 'kb_stem', 'kb_pop'][:0] + names[-4:] and names.index('kb_pad') > names.index('kb_field'), 'the pad is painted over the list')
    for n in ('label_status', 'label_title', 'label_row_title', 'label_row_sub', 'label_chip', 'label_chip_on'):
        expect(by[n].get('visible') == 'false' and by[n].get('sensitive') == 'false', f'{n} starts hidden and out of the hit test')
    expect(by['label_chip_on'].get('style:normal:text_color') == PS.CHIP_ON_INK and by['label_chip_on'].get('style:normal:bg_color') == PS.CHIP_ON_RGB, 'the selected chip\'s text is dark, on the pill\'s grey')
    cols = [v for w in t.walk() for k, v in w.props if isinstance(v, str) and re.fullmatch(r'#[0-9a-fA-F]{6,8}', v) and 'color' in k]
    def neutral(c):
        c = c.lstrip('#'); r, g, b = (int(c[i:i + 2], 16) for i in (0, 2, 4)); return max(r, g, b) - min(r, g, b) <= 12
    expect(all(neutral(c) for c in cols), f'no accent colour: every colour is a grey ({sorted({c for c in cols if not neutral(c)})})')
    P = pod_pages
    expect(P.SEARCH in P.PAGES and P.SEARCH.key == 'm1plus_search' and P.SEARCH.kind == 'search' and P.SEARCH.rows == [] and not any(r.label == 'Search' for p in P.PAGES for r in p.rows),
           'the page is registered, with no menu row')
    # the model and the header agree with the payload's own text for the geometry the builder does not hold
    src = open(os.path.join(ROOT, 'patch', 'search.h')).read()
    expect(all(f'#define {k} {v}' in src for k, v in D.items()), 'tools/pod_search.py reads patch/search.h: one set of numbers')
    expect(D['SE_FIELD_Y'] + D['SE_FIELD_H'] <= D['SE_CHIPS_Y'] and D['SE_CHIPS_Y'] + D['SE_CHIPS_H'] <= D['SE_SEP_Y'] < D['SE_LIST_Y'] and D['SE_ART'] + 2 * D['SE_ART_Y'] == D['SE_ROW_H'] - 8 + 8 - 0 or D['SE_ART_Y'] * 2 + D['SE_ART'] <= D['SE_ROW_H'],
           'the field, the chips, the line and the list stack without overlap; the thumbnail fits its row')
    expect(D['SE_TEXT_LEFT'] == D['SE_ART_X'] + D['SE_ART'] + 12 and D['SE_END_CHEV'] < D['SE_CHEV_X'] and D['SE_CHEV_X'] + 10 <= D['SE_SEP_END'] <= 310, 'the text starts 12 px after the thumbnail and ends before the chevron')
    # i18n: the new keys in 13 languages; every text fits its room in every language, measured in the real font
    for k in ('Top Results', 'No Results', 'Search', 'Artists', 'Albums', 'Songs', 'Playlists', 'Artist', 'Song', 'Playlist'):
        expect(k in pod_i18n.TEXT and set(pod_i18n.TEXT[k]) == set(pod_i18n.LOCALES), f'{k} is translated in the 13 languages')
    wide = [(loc, k, width(pod_i18n.TEXT[k][loc], 20)) for k in ('No Results',) for loc in pod_i18n.LOCALES]
    expect(all(w <= 296 for *_, w in wide), f'the status line fits its room in every language ({max(wide, key=lambda t: t[2])})')
    room = D['SE_END_CHEV'] - D['SE_TEXT_LEFT']
    sub = [(loc, k, width(pod_i18n.TEXT[k][loc] if k in pod_i18n.TEXT else k, 18)) for k in ('Artist', 'Song', 'Playlist', 'album') for loc in pod_i18n.LOCALES]
    expect(all(w < room // 2 for *_, w in sub), f'the type words of the grey line leave room for a name ({max(sub, key=lambda t: t[2])} of {room})')
    hint = [(loc, width(pod_i18n.TEXT['Search'][loc], D['SE_TEXT_W'] and 18)) for loc in pod_i18n.LOCALES]
    expect(all(w <= D['SE_TEXT_W'] for _, w in hint), 'the placeholder fits the field in every language')


SECTIONS = [fold_tests, query_tests, rank_tests, incremental_tests, page_tests, chips_tests, chip_cover_tests, live_tests, tap_tests, perf_tests, entry_tests, return_tests, embed_tests, asset_tests]   # tools/check.py runs each as its own task


def run(ctx):
    for s in SECTIONS: s(ctx)
