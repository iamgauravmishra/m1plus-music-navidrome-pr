"""Localisation: the string tables (reader / writer, our keys in all 16), our assets and payload texts going through
the stock translation, every language's payload output, widths per language, glyphs in the shipped font."""
import importlib.util, os, re, stat, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import awtk_strings, awtk_style, pod_i18n
from awtk_text import Ttf, StbText

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join('rootfs', 'release', 'assets', 'default', 'raw')
SAME_AS_ENGLISH = {'Cover Flow', 'Playlists', 'Genres', 'Extras', 'Albums', 'Start in M1 Pod', 'Artists'}   # translations that are the English word by design


def sibling(name):
    """test/pod/<name>.py as test/patch.py loaded it, or loaded here when this module runs alone."""
    key = f'podtest_{name}'
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, os.path.join(HERE, name + '.py'))
        mod = importlib.util.module_from_spec(spec); sys.modules[key] = mod; spec.loader.exec_module(mod)
    return sys.modules[key]


def call_args(src, name):
    """The text inside every `name( ... )` call of C source `src` (balanced parentheses)."""
    out = []
    for m in re.finditer(r'\b' + name + r'\(', src):
        depth, i = 1, m.end()
        while depth and i < len(src):
            depth += {'(': 1, ')': -1}.get(src[i], 0); i += 1
        out.append(src[m.end():i - 1])
    return out


def run(ctx):
    expect = ctx.expect
    stock_raw = os.path.join(paths.find_stock(paths.ZIP), RAW)
    tables_dir, stock_dir = os.path.join(WORK, RAW, 'strings'), os.path.join(stock_raw, 'strings')
    stock = {f[:-4]: awtk_strings.load(os.path.join(stock_dir, f)) for f in sorted(os.listdir(stock_dir))}
    built = {f[:-4]: awtk_strings.load(os.path.join(tables_dir, f)) for f in sorted(os.listdir(tables_dir))}
    ALL, LOC = pod_i18n.ALL_TABLES, pod_i18n.LOCALES

    # 1. The reader and writer: the 16 stock tables round-trip byte for byte; keys stay sorted and unique; text is UTF-8.
    for loc in ALL:
        data = open(os.path.join(stock_dir, loc + '.bin'), 'rb').read()
        expect(awtk_strings.serialize(awtk_strings.parse(data)) == data, f'stock {loc}.bin round-trips byte-exact')
    sample = [('a', 'x'), ('b', '日本語'), ('c', 'Привет')]
    expect(awtk_strings.parse(awtk_strings.serialize(sample)) == sample and awtk_strings.serialize([]) == bytes(12),
           'a small table with CJK and Cyrillic round-trips; an empty one is the 12 header bytes')
    for bad in ([('b', '1'), ('a', '2')], [('a', '1'), ('a', '2')]):
        try: awtk_strings.serialize(bad); ok = False
        except AssertionError: ok = True
        expect(ok, f'unsorted or duplicate keys are refused ({bad})')
    expect(sorted(stock) == ALL and len(ALL) == 16 and set(LOC) | set(pod_i18n.TWINS) == set(ALL), 'there are 16 tables: 13 the language menu reaches, 3 stubs')

    # 2. The built tables: the stock entries untouched, our keys added, in all 16, sorted for the binary search.
    for loc in ALL:
        want = pod_i18n.add_to_tables({loc: stock[loc]})[loc]
        expect(built[loc] == want, f'{loc}: the stock entries plus exactly our {len(pod_i18n.TEXT)} keys')
        have = dict(built[loc])
        keys = [k.encode() for k, _ in built[loc]]
        expect(keys == sorted(keys), f'{loc}: sorted')
        expect(all(have.get(k) for k in pod_i18n.TEXT), f'{loc}: every added key is there and not empty')
        expect(stat.S_IMODE(os.stat(os.path.join(tables_dir, loc + '.bin')).st_mode) == stat.S_IMODE(os.stat(os.path.join(stock_dir, loc + '.bin')).st_mode), f'{loc}: file mode kept')
    en = dict(built['en_US'])
    expect(all(en[k] == k for k in pod_i18n.TEXT), 'en_US: our keys are their own English text')
    for loc in LOC:
        have = dict(built[loc])
        expect(all(have.get(k) for k in pod_i18n.STOCK) and all(dict(stock['en_US'])[k] == v for k, v in pod_i18n.STOCK.items()),
               f'{loc}: the stock keys we use are there and en_US reads as pod_i18n.STOCK says')
        same = {k for k in pod_i18n.TEXT if have[k] == k}
        expect(loc == 'en_US' or same <= SAME_AS_ENGLISH, f'{loc}: only the words that stay English by design are untranslated ({sorted(same - SAME_AS_ENGLISH)})')
    for stub, twin in pod_i18n.TWINS.items():
        expect(all(dict(built[stub])[k] == dict(built[twin])[k] for k in pod_i18n.TEXT), f'{stub} holds {twin}\'s language')
    for k, by in pod_i18n.TEXT.items():
        counts = {loc: by[loc].count('%d') for loc in LOC}
        expect(set(counts.values()) == ({1} if k.startswith('%d') else {0}) and all('%' not in by[l].replace('%d', '') for l in LOC),
               f'{k!r}: %d only in the track counts, once each')
    expect(sorted(pod_i18n.TEXT) == pod_i18n.KEYS and all(set(by) == set(LOC) for by in pod_i18n.TEXT.values()), 'every key has all 13 languages')

    # 3. Our assets: tr_text keys, no English left but the brand names.
    used = set()
    for page in pod_pages.PAGES:
        tree = awtk_ui.parse(open(os.path.join(WORK, RAW, 'ui', page.key + '.bin'), 'rb').read())
        bad = []
        for w in tree.walk():
            t, k = w.get('text'), w.get('tr_text')
            if k is not None:
                used.add(k)
                if k not in pod_i18n.TEXT and k not in pod_i18n.STOCK: bad.append((w.name, k))
            if t not in (None, '') and t not in pod_i18n.BRANDS: bad.append((w.name, t))
            expect(not (t and k), f'{page.key}:{w.name} does not carry both text and tr_text')
        expect(not bad, f'{page.key}: every text is a tr_text key of ours or the stock tables, or a brand name ({bad})')
        title = tree.find('label_title')
        expect(pod_i18n.shown_english(title) == page.title, f'{page.key}: the title reads {page.title!r} (was {pod_i18n.shown_english(title)!r})')
        for i, r in enumerate(page.rows):
            lab = next(c for c in tree.find(f'pod_row{i}').children if c.type == 'hscroll_label')
            expect(pod_i18n.shown_english(lab) == r.label, f'{page.key}:pod_row{i} reads {r.label!r}')
    expect(tree is not None and used, 'the pages use keys')
    cover = awtk_ui.parse(open(os.path.join(WORK, RAW, 'ui', 'm1pod_cover.bin'), 'rb').read())
    expect(cover.find('btn_cancel').get('tr_text') == 'Cancel', 'the Cancel button is translated')
    expect(pod_i18n.key_for('Settings') == 'cdrippersettings' and pod_i18n.key_for('Hi-Res') == 'hr' and pod_i18n.key_for('M1 Pod') is None
           and pod_i18n.key_for('Tidal') is None and pod_i18n.key_for('Albums') == 'Albums', 'stock keys where the English is the same, brand names plain')

    # 4. The payload's source: nothing user-visible bypasses the translation.
    sources = {f: open(os.path.join(ROOT, 'patch', f), encoding='utf-8').read() for f in sorted(os.listdir(os.path.join(ROOT, 'patch'))) if f.endswith('.c')}
    literal = re.compile(r'"((?:[^"\\]|\\.)*)"')
    keys_in_c = set(); plain = []
    for f, src in sources.items():
        for a in call_args(src, 'widget_set_text_utf8'):
            for inner in call_args(a, 'TR'): a = a.replace(inner, '')       # a translated key inside is fine
            for lit in literal.findall(a):
                if lit not in ('', 'M1 Pod'): plain.append((f, lit))
        for a in call_args(src, 'toast') + call_args(src, 'pod_toast'):
            if literal.search(a) and not a.startswith('TR('): plain.append((f, a))
        for name in ('TR', 'widget_set_tr_text'):
            for a in call_args(src, name):
                keys_in_c.update(literal.findall(a))
    expect(not plain, f'no text is set or toasted untranslated: {plain}')
    expect(all(k in pod_i18n.TEXT or k in pod_i18n.STOCK for k in keys_in_c), f'every key the payload uses exists ({sorted(k for k in keys_in_c if k not in pod_i18n.TEXT and k not in pod_i18n.STOCK)})')
    orphans = set(pod_i18n.TEXT) | set(pod_i18n.STOCK)
    orphans -= used | {k for k in orphans if any(f'"{k}"' in src for src in sources.values())}
    expect(not orphans, f'every key is used by an asset or the payload: {sorted(orphans)}')
    expect({'Landscape', 'Sort', 'Artist', 'album', 'Cover Flow'} <= used | keys_in_c and 'Cover Flow landscape' not in pod_i18n.TEXT,
           'the Settings > Cover Flow page uses its keys (rows in the asset, the value by key in the payload); the old landscape row key is gone')
    expect(all(k in sources['home.c'] for k in ('"M1 Pod"',)), 'the Home icon keeps the brand name as plain text')
    expect(len(re.findall(r'locale_info_tr|widget_set_tr_text', ' '.join(pod.FUNCTIONS))) == 2 and pod.FUNCTIONS['locale_info_tr'][2] == 0x658db4
           and pod.FUNCTIONS['widget_set_tr_text'][2] == 0x66f994 and pod.FUNCTIONS['locale_info'][2] == 0x6588b0, 'the three stock translation functions are pinned')

    # 5. The payload in every language (the stock lookup mocked with the built table): each text it sets is the table's.
    albuminfo = sibling('albuminfo')
    shuffle = sibling('shuffle')
    play = PSYMS['shuffle_play']
    cover_open = PSYMS['coverflow_open']
    open_artists = PSYMS['artists_open']
    A = offsets()
    for loc in ALL:
        T = lambda key: pod_i18n.TEXT[key][pod_i18n.table_for(loc)].encode('utf-8').decode('latin-1')    # as read_cstr returns it
        text_of = lambda m, w: [c[2] for c in m.calls if c[0] == 'widget_set_text_utf8' and c[1] == w][-1:]
        tr_keys = lambda m, w: [c[2] for c in m.calls if c[0] == 'widget_set_tr_text' and c[1] == w]
        # Artists: the title follows the mode, the empty message
        m = artists_machine(); m.set_language(loc)
        m.call(open_artists, count=5000000)
        title = m.widgets['label_title']
        expect(tr_keys(m, title) == ['Artists'] and text_of(m, title) == [T('Artists')], f'{loc}: the Artists title is set by key and reads {T("Artists")!r}')
        m.call(PSYMS['ar_on_toggle'], count=5000000)
        expect(tr_keys(m, title)[-1:] == ['Album Artists'] and text_of(m, title) == [T('Album Artists')], f'{loc}: the Album Artists title')
        m = artists_machine(artists=()); m.set_language(loc)
        m.call(open_artists, count=2000000)
        st = m.widgets['label_status']
        expect(tr_keys(m, st) == ['Update Local Music first'] and text_of(m, st) == [T('Update Local Music first')], f'{loc}: the empty Artists message')
        # an artist without albums, and the All albums card
        m = artists_machine(); m.set_language(loc); m.call(open_artists, count=5000000)
        m.call(PSYMS['ar_on_artist'], a0=2, count=8000000)
        st = m.widgets['label_status']
        expect(text_of(m, st) == [T('No albums')] and tr_keys(m, st) == ['No albums'], f'{loc}: an artist without albums')
        m = artists_machine(); m.set_language(loc); m.call(open_artists, count=5000000)
        m.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
        put_value(m, 3); m.call(PSYMS['on_changed'], count=2000000)
        expect(text_of(m, m.widgets['label_album']) == [T('All albums')], f'{loc}: the All albums card')
        # Cover Flow: empty library, too large, first-run status and progress
        m = cover_machine(albums=0); m.set_language(loc); m.call(cover_open, count=2000000)
        expect(text_of(m, m.widgets['label_status']) == [T('Update Local Music first')], f'{loc}: Cover Flow with no library')
        m = cover_machine(albums=4001, cached=False); m.set_language(loc); m.call(cover_open, count=50000000)
        expect(text_of(m, m.widgets['label_status']) == [T('Library too large')], f'{loc}: Cover Flow with a library over the limit')
        m = cover_machine(albums=3, cached=False); m.set_language(loc); m.call(cover_open, count=5000000)
        st = m.widgets['label_status']
        expect(text_of(m, st) == [T('Preparing covers...')] and tr_keys(m, st) == ['Preparing covers...'], f'{loc}: Cover Flow preparing')
        m.call(PSYMS['on_poll'], count=2000000)
        expect(text_of(m, st) == [T('Preparing covers...') + ' 0/3'], f'{loc}: the progress line is the translation and the count ({text_of(m, st)})')
        # Albums grid with no library
        m = Machine(); m.set_language(loc)
        for w in ('btn_return', 'btn_backtoplayer', 'btn_albumview', 'view_grid', 'label_status', 'label_row_title', 'label_row_sub'): m.widget(w)
        m.call(PSYMS['albums_open'], count=2000000)
        expect(text_of(m, m.widgets['label_status']) == [T('Update Local Music first')], f'{loc}: the empty Albums page')
        # Shuffle: the message boxes
        def toast_of(m): return [c[1] for c in m.calls if c[0] == 'toast']
        m = shuffle.shuffle_machine([]); m.set_language(loc)
        m.call(play, a0=0, count=50000000)
        expect(toast_of(m) == [T('Update Local Music first')], f'{loc}: Shuffle with no library')
        m = shuffle.shuffle_machine([('/mnt/mmc/a/1.flac', 'A', 1)], present=False); m.set_language(loc)
        m.call(play, a0=0, count=50000000)
        expect(toast_of(m) == [T('Storage unavailable')], f'{loc}: Shuffle with the card out')
        m = shuffle.shuffle_machine([('/mnt/mmc/a/1.flac', 'A', 1), ('/mnt/mmc/b/1.flac', 'B', 1)]); m.set_language(loc); m.calloc_fail = True
        m.call(play, a0=1, count=50000000)
        expect(toast_of(m) == [T('Not enough memory')], f'{loc}: Shuffle Albums without memory')
        m = shuffle.shuffle_machine([]); m.set_language(loc)
        one = shuffle.song(m, '/mnt/mmc/big/01.flac', 'Big', 1); m.present.add('/mnt/mmc/big/01.flac')
        m.showlist = [one] * (A['SHUFFLE_MAX'] + 1)
        m.call(play, a0=1, count=50000000)
        expect(toast_of(m) == [T('Too many songs to shuffle')], f'{loc}: Shuffle Albums with too many songs')
        # the album page: both buttons and the count line
        am = albuminfo.AlbumMachine(); am.set_language(loc)
        item = am.header(tracks=6, year=1959)
        kids = am.kids(item)
        expect(am.texts.get(kids[3]) == T('Play all') and am.texts.get(kids[5]) == T('Shuffle'), f'{loc}: the buttons read {T("Play all")!r} / {T("Shuffle")!r}')
        for n in (1, 2, 5, 11, 21, 100):
            am = albuminfo.AlbumMachine(); am.set_language(loc)
            item = am.header(tracks=n, year=1959 if n % 2 else 0)
            want = T('%d track' if n == 1 else '%d tracks').replace('%d', str(n))
            if n % 2: want = '1959 \xc2\xb7 ' + want
            expect(am.texts.get(am.kids(item)[4]) == want, f'{loc}: {n} tracks reads {want!r} (got {am.texts.get(am.kids(item)[4])!r})')
        am = albuminfo.AlbumMachine(); am.set_language(loc)
        item = am.header(tracks=3, year=1959); am.present.clear()
        am.call(PSYMS['ah_on_shuffle'], count=5000000)
        expect(toast_of(am) == [T('Storage unavailable')], f'{loc}: Shuffle on the album page with the card out')

    # 6. English stays English: no table, or a table without the key, shows the key (= the English text).
    m = artists_machine(); m.call(open_artists, count=5000000)
    expect(text_of(m, m.widgets['label_title']) == ['Artists'], 'no translation loaded: English')
    am = albuminfo.AlbumMachine(); item = am.header(tracks=1, year=1959)
    expect(am.texts.get(am.kids(item)[4]) == '1959 \xc2\xb7 1 track' and am.texts.get(am.kids(item)[3]) == 'Play all', 'the album header in English')

    # 7. Widths in the shipped font, per language: rows, titles, messages, buttons.
    font = Ttf(os.path.join(WORK, RAW, 'fonts', 'default.ttf'))
    th = awtk_style.parse(open(os.path.join(WORK, RAW, 'styles', 'default.bin'), 'rb').read())
    px_of = lambda widget, style: th.find(widget, style, 'normal')[0].get('font_size')
    row_px, title_px, msg_px = px_of('hscroll_label', 'srlabel_leftwhite21_style'), px_of('label', 'navbar_label_white'), px_of('hscroll_label', 'srlabel_msgwhite_style')
    width = lambda text, px: StbText(font, px).layout(text)[1]
    tr_text = lambda loc, key: pod_i18n.tr(loc, key, {l: dict(built[l]) for l in LOC})
    over = []
    for page in pod_pages.PAGES:
        tree = awtk_ui.parse(open(os.path.join(WORK, RAW, 'ui', page.key + '.bin'), 'rb').read())
        lt = tree.find('label_title')
        keys = [(r.label, [c for c in tree.find(f'pod_row{i}').children if c.type == 'hscroll_label'][0].w) for i, r in enumerate(page.rows)]
        for loc in LOC:
            if pod_i18n.key_for(page.title):
                w = width(tr_text(loc, pod_i18n.key_for(page.title)), title_px)
                if w > lt.w: over.append((page.key, 'title', loc, w, lt.w))
            for english, room in keys:
                k = pod_i18n.key_for(english)
                if k and width(tr_text(loc, k), row_px) > room: over.append((page.key, english, loc, width(tr_text(loc, k), row_px), room))
    expect(not over, f'every menu, Extras, Shuffle, Settings and Main Menu row and every page title fits its label in all 13 languages ({over[:4]})')
    over = []
    for loc in LOC:
        for key in ('Update Local Music first', 'Not enough memory', 'Storage unavailable', 'Too many songs to shuffle'):
            if width(tr_text(loc, key), msg_px) > 260: over.append((loc, key))          # the message box's line is 260 px (@0x4788a0)
        for key in ('Update Local Music first', 'Library too large', 'No albums', 'Not enough memory'):
            if width(tr_text(loc, key), 20) > cover.find('label_status').w: over.append((loc, key, 'status'))
        if width(tr_text(loc, 'Preparing covers...') + ' 4000/4000', 20) > cover.find('label_status').w: over.append((loc, 'progress'))
        if width(tr_text(loc, 'Cancel'), 20) > cover.find('btn_cancel').w - 10: over.append((loc, 'Cancel'))
        if width(tr_text(loc, 'All albums'), 22) > 288: over.append((loc, 'All albums'))
        for key in ('Play all', 'Shuffle'):
            if width(tr_text(loc, key), 20) > A['AH_BTN_W'] - 4: over.append((loc, key, 'button'))
        for key in ('%d track', '%d tracks'):
            if width('1959 \xb7 ' + tr_text(loc, key).replace('%d', '9999'), 15) > A['AH_TEXT_W']: over.append((loc, key, 'count line'))
        for key in pod_pages.SORT_VALUES:                              # the Sort row's value, in its own label (and the Artist/Album words in the title room)
            k = pod_i18n.key_for(key)
            if width(tr_text(loc, k), pod_ui.VALUE_PX) > pod_ui.VALUE_W - 4: over.append((loc, key, 'sort value'))
    for loc in LOC:      # the label and the value of the Sort row do not meet: the room left of the value, and the longest value
        longest = max(width(tr_text(loc, pod_i18n.key_for(v)), pod_ui.VALUE_PX) for v in pod_pages.SORT_VALUES)
        label = width(tr_text(loc, pod_i18n.key_for('Sort')), row_px)
        if 64 + label + 8 > pod_ui.value_x(320) + pod_ui.VALUE_W - longest: over.append((loc, 'Sort', 'label meets value', label, longest))
    expect(not over, f'messages, the cover page, the album buttons and count line, and the Sort value fit in all languages ({over[:4]})')

    # 8. Glyphs: every character of every text we add, and of the stock texts we reuse, has ink in the shipped font.
    probe = StbText(font, 20)
    missing = {}
    for loc in LOC:
        texts = [pod_i18n.TEXT[k][loc] for k in pod_i18n.TEXT] + [dict(built[loc])[k] for k in pod_i18n.STOCK]
        for t in texts:
            for c in t:
                if c != ' ' and probe.box(c) is None: missing.setdefault(c, loc)
    expect(not missing, f'no character is missing from the font: {[(hex(ord(c)), l) for c, l in missing.items()]}')
    chars = {c for loc in LOC for k in pod_i18n.TEXT for c in pod_i18n.TEXT[k][loc]} - {' '}
    print(f'  {len(chars)} distinct characters in our texts; the font subset needs no extension')
