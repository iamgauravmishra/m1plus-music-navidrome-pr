"""The album view: the stock albuminfo_page restyled by the hook on its header builder, Shuffle, the
year line, the cover size, hit tests; Cover Flow's first album and its last-album memory."""
import json, os, re, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import importlib.util


def _rows_module():
    """test/pod/rows.py (RowMachine: demo's own widget constructors mocked into a model in emulated memory),
    as test/patch.py loaded it, or loaded here when this module runs alone."""
    if 'podtest_rows' not in sys.modules:
        spec = importlib.util.spec_from_file_location('podtest_rows', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'rows.py'))
        mod = importlib.util.module_from_spec(spec); sys.modules['podtest_rows'] = mod; spec.loader.exec_module(mod)
    return sys.modules['podtest_rows']


RowMachine = _rows_module().RowMachine

HEADER_BUILDER = pod.ALBUMINFO_HEADER             # albuminfo_listitem0_layout
KILL = '/mnt/mmc/m1pod-off'
HDR_ART = 0x4dd670                                # the cover thread's flag-1 size word
STOCK_HEADER = {'cover': (0, 0, 100, 100), 'title': (108, 7, 200, 24), 'artist': (108, 33, 200, 20),
                'button': (108, 62, 90, 28)}      # what the stock builder makes (@0x526264, 0x524990, 0x524a64), the title boxes as rows.json sets them


class AlbumMachine(RowMachine):
    """RowMachine (demo's real widget constructors mocked into a model in emulated memory) plus what
    the album view's code calls: bound handlers, failing creates, destroys."""
    def __init__(self):
        super().__init__()
        self.bound = {}           # widget -> {event: (handler, ctx)}
        self.create_fail = set()  # widget kinds whose create returns NULL
        self.destroyed = []
        self.handlers[pod.FUNCTIONS['widget_destroy'][2]] = 'row:widget_destroy'

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address, '')
        a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        if name == 'row:widget_on':
            self.bound.setdefault(a0, {})[a1] = (a2, a3)
        elif name == 'row:widget_destroy':
            self.destroyed.append(a0)
            for kids in self.children.values():
                if a0 in kids: kids.remove(a0)
            u.reg_write(UC_MIPS_REG_V0, 0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        elif name in ('row:button_create', 'row:hscroll_label_create', 'row:image_create') and \
                name[len('row:'):-len('_create')] in self.create_fail:
            u.reg_write(UC_MIPS_REG_V0, 0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        return super()._hook(u, address, size, _)

    def header(self, tracks=6, year=1959, card=False, cls=None):
        """A header item built by the patched stock builder (the hook runs, then restyles), with the
        stock list loaded as albuminfo_page_init leaves it: the album's tracks."""
        recs = [self.record(album='Kind of Blue', artist='Miles Davis', title=f'Track {i}', name=f'{i}.flac',
                            path=f'/mnt/mmc/m/{i}.flac', rid=100 + i) for i in range(tracks)]
        for r in recs:
            self.setword(r + O['REC_YEAR'], year)
            self.present.add(self.read_cstr(self.word(r + O['REC_PATH'])))
        self.tracks = recs
        self.setword(pod.DATA['PDEQ_SHOWLIST'][0], self.new_deque(recs))
        self.u.mem_write(pod.DATA['CLASSINFO'][0] + O['CLASSINFO_ALL_SONGS'], bytes([1 if card else 0]))
        self.setword(pod.DATA['G_CLASS_TYPE'][0], cls or O['CLASS_ALBUM_TRACKS'])
        parent = self.new_widget('scroll_view', 0, 0, 0, 310, 400)
        item = self.new_widget('list_item', parent, 0, 0, 0, 100)
        self.props[(item, 'w')] = 310
        self.call(HEADER_BUILDER, a0=item, count=2000000)
        return item


def album_tests(expect, page, cover_asset):
    # ------------------------------------------------------------------ the hook is installed as pinned
    built = open(DEMO, 'rb').read()
    w = lambda a: struct.unpack_from('<I', built, pod.fileoff(built, a))[0]
    hook = MANIFEST['hook_albuminfo']
    expect(hook['addr'] == HEADER_BUILDER == 0x526264 and hook['target'] == PSYMS['m1pod_albuminfo_header'],
           'the manifest records the album header hook and its target')
    expect(pod.ALBUMINFO_HEADER_PROLOGUE == (0x3c1c004e, 0x279cdc6c, 0x0399e021),
           'the hook pins the three PIC prologue words of albuminfo_listitem0_layout')
    expect((w(HEADER_BUILDER), w(HEADER_BUILDER + 4)) == (pod.j(PSYMS['m1pod_albuminfo_header']), 0)
           and w(HEADER_BUILDER + 8) == pod.ALBUMINFO_HEADER_PROLOGUE[2],
           'the built demo has `j m1pod_albuminfo_header; nop` over the first two prologue words')
    expect(w(HDR_ART) == 0x24130078, f'the header cover is rendered at 120 px ({w(HDR_ART):#010x}; stock addiu s3, zero, 0x64)')
    expect(O['AH_ART'] == 120, 'and the header shows it 1:1 (AH_ART)')
    # the page is reached by the album page's builders only: the hook's only callers in stock
    stock_demo = open(os.path.join(paths.find_stock() or os.path.join(os.path.dirname(WORK), 'stock'), 'rootfs', pod.DEMO), 'rb').read()
    sw = struct.unpack_from('<III', stock_demo, pod.fileoff(stock_demo, HEADER_BUILDER))
    expect(sw == pod.ALBUMINFO_HEADER_PROLOGUE, 'stock has the pinned prologue at the hook site')

    # ------------------------------------------------------------------ stock first, then ours
    m = AlbumMachine()
    item = m.header()
    kids = m.kids(item)
    expect(len(kids) == 6, f'the header holds the stock four widgets and the two added ({len(kids)})')
    art, title, artist, play, meta, shuf = kids
    order = [c[1] for c in m.calls if c[0] == 'create']
    expect(order == ['image', 'hscroll_label', 'hscroll_label', 'button', 'hscroll_label', 'button'],
           f'stock builds its header first (image, title, artist, button), then ours (meta, Shuffle) ({order})')
    expect(m.wname.get(art) == 'img_albumcover_m', 'the cover keeps its stock name (the app looks it up)')
    draws = [c[2] for c in m.calls if c[0] == 'image_set_draw_type' and c[1] == art]
    expect(draws == [O['IMAGE_SCALE_AUTO'], O['IMAGE_DRAW_CENTER']], f'stock scales the cover (scale-auto), the hook draws it centred at its own size ({draws})')
    geo = m.geo
    expect(geo(art) == (O['AH_PAD'], O['AH_ART_Y'], O['AH_ART'], O['AH_ART']), f'cover {geo(art)}')
    expect(geo(title) == (O['AH_TEXT_X'], O['AH_TITLE_Y'], O['AH_TEXT_W'], O['AH_TITLE_H'])
           and geo(artist) == (O['AH_TEXT_X'], O['AH_ARTIST_Y'], O['AH_TEXT_W'], O['AH_ARTIST_H'])
           and geo(meta) == (O['AH_TEXT_X'], O['AH_META_Y'], O['AH_TEXT_W'], O['AH_META_H']),
           'title, artist and the year line in the column beside the cover')
    expect(geo(play) == (O['AH_PAD'], O['AH_BTN_Y'], O['AH_BTN_W'], O['AH_BTN_H'])
           and geo(shuf) == (O['AH_SHUFFLE_X'], O['AH_BTN_Y'], O['AH_BTN_W'], O['AH_BTN_H']),
           f'Play all and Shuffle side by side ({geo(play)}, {geo(shuf)})')
    expect(geo(item)[2:] == (310, O['AH_HDR_H']),
           f'the header item is AH_HDR_H high at the list width ({geo(item)})')
    # the layout numbers
    A = O
    expect(A['AH_PAD'] + A['AH_ART'] < A['AH_TEXT_X'] and A['AH_TEXT_X'] + A['AH_TEXT_W'] == 310 - A['AH_PAD']
           and A['AH_META_Y'] + A['AH_META_H'] <= A['AH_ART_Y'] + A['AH_ART']
           and A['AH_BTN_Y'] >= A['AH_ART_Y'] + A['AH_ART'] + A['AH_PAD'] // 2
           and A['AH_BTN_Y'] + A['AH_BTN_H'] + A['AH_PAD'] == A['AH_HDR_H'] and A['AH_BTN_H'] >= 36
           and A['AH_ART_Y'] <= 8 and A['AH_PAD'] + A['AH_BTN_W'] + 10 == A['AH_SHUFFLE_X'] and A['AH_SHUFFLE_X'] + A['AH_BTN_W'] + A['AH_PAD'] <= 310,
           'the header is symmetric in the 310 px list; the buttons are touch-sized and inside it')
    expect(A['AH_TITLE_H'] >= 24 and A['AH_ARTIST_H'] >= 20 and A['AH_META_H'] >= 18,
           'every line box holds its font (21 / 18 / 15 px)')
    expect(m.style.get(play) == m.style.get(shuf) == 'btn_albumbtn_style' and m.style.get(meta) == 'srlabel_meta15_style',
           'Play all and Shuffle share the dark button style; the year line has its own style')
    expect(m.texts.get(play) == 'Play all' and m.texts.get(shuf) == 'Shuffle', 'the buttons read Play all and Shuffle')
    expect(m.props.get((meta, 'sensitive')) == 0, 'the year line is decoration: a drag over it scrolls the list')
    expect(any(c[0] == 'hscroll_label_set_ellipses' and c[1] == meta for c in m.calls),
           'a long line ends in an ellipsis')
    stock_play = m.bound.get(play, {}).get(O['EVT_CLICK'])
    expect(stock_play == (0x525d48, item), 'the stock Play all handler stays bound to the stock button')
    expect(m.bound.get(shuf, {}).get(O['EVT_CLICK'], (None,))[0] == PSYMS['ah_on_shuffle'],
           'Shuffle is bound to its handler on click')
    expect(m.style.get(title) == 'srlabel_item_white_style' and m.style.get(artist) == 'srlabel_item_gray18_style',
           'the title (21 px white) and artist (18 px grey) keep their stock styles')

    # ------------------------------------------------------------------ the year line
    for tracks, year, card, want in ((6, 1959, False, '1959 \xc2\xb7 6 tracks'), (1, 1959, False, '1959 \xc2\xb7 1 track'),
                                     (8, 0, False, '8 tracks'), (1, 0, False, '1 track'),
                                     (24, 1959, True, '24 tracks'), (3, 3999, False, '3 tracks')):
        m = AlbumMachine(); item = m.header(tracks=tracks, year=year, card=card)
        expect(m.texts.get(m.kids(item)[4]) == want, f'the year line for {tracks} tracks, year {year}, card {card}: {want!r} (got {m.texts.get(m.kids(item)[4])!r})')
    # the first track that carries a year is the album's
    m = AlbumMachine(); m.header(tracks=4, year=0)
    for i, r in enumerate(m.tracks): m.setword(r + O['REC_YEAR'], 0 if i < 2 else 1971)
    parent = m.new_widget('scroll_view', 0, 0, 0, 310, 400)
    item = m.new_widget('list_item', parent, 0, 0, 0, 100)
    m.props[(item, 'w')] = 310
    m.call(HEADER_BUILDER, a0=item, count=2000000)
    expect(m.texts.get(m.kids(item)[4]) == '1971 \xc2\xb7 4 tracks', 'the first track with a year gives the album its year')

    # ------------------------------------------------------------------ failures leave stock alone
    # kill switch: the stock header exactly
    m = AlbumMachine(); m.present.add(KILL)
    item = m.header()
    kids = m.kids(item)
    got = [m.geo(k) for k in kids]
    expect(len(kids) == 4 and got == [STOCK_HEADER[k] for k in ('cover', 'title', 'artist', 'button')],
           f'with the kill switch the header is the stock one ({got})')
    expect(m.geo(item)[3] == 100 and m.style.get(kids[3]) == 'btn_imgplayall_style' and not m.texts.get(kids[3]),
           'stock size, stock Play all style, no text added')
    # not the header stock builds: nothing is moved, nothing is added
    def hand_built(kinds):
        mm = AlbumMachine()
        parent = mm.new_widget('scroll_view', 0, 0, 0, 310, 400)
        it = mm.new_widget('list_item', parent, 0, 0, 0, 100)
        mm.props[(it, 'w')] = 310
        for kind, g in zip(kinds, (STOCK_HEADER['cover'], STOCK_HEADER['title'], STOCK_HEADER['artist'], STOCK_HEADER['button'],
                                   (0, 0, 10, 10))):
            mm.new_widget(kind, it, *g)
        mm.setword(pod.DATA['PDEQ_SHOWLIST'][0], mm.new_deque([]))
        mm.call(PSYMS['ah_restyle'], a0=it, count=200000)
        return mm, it
    mm, it = hand_built(('image', 'hscroll_label', 'hscroll_label', 'button'))
    expect(len(mm.kids(it)) == 6, 'the stock shape is restyled (control)')
    for kinds, why in ((('image', 'hscroll_label', 'hscroll_label'), 'three children'),
                       (('image', 'hscroll_label', 'hscroll_label', 'button', 'view'), 'five children'),
                       (('image', 'hscroll_label', 'label', 'button'), 'the artist is not an hscroll_label'),
                       (('view', 'hscroll_label', 'hscroll_label', 'button'), 'the cover is not an image'),
                       (('image', 'hscroll_label', 'hscroll_label', 'image'), 'the button is not a button')):
        mm, it = hand_built(kinds)
        expect(len(mm.kids(it)) == len(kinds) and mm.geo(it)[3] == 100 and not mm.style
               and all(mm.geo(k) == g for k, g in zip(mm.kids(it), (STOCK_HEADER['cover'], STOCK_HEADER['title'],
                                                                      STOCK_HEADER['artist'], STOCK_HEADER['button'], (0, 0, 10, 10)))),
               f'{why}: untouched')
    mm = AlbumMachine(); mm.call(PSYMS['ah_restyle'], a0=0, count=200000)
    expect(not mm.calls, 'no item: nothing happens')
    for fail in ('button', 'hscroll_label'):
        mm = AlbumMachine()
        parent = mm.new_widget('scroll_view', 0, 0, 0, 310, 400)
        it = mm.new_widget('list_item', parent, 0, 0, 0, 100)
        mm.props[(it, 'w')] = 310
        for kind, g in zip(('image', 'hscroll_label', 'hscroll_label', 'button'), STOCK_HEADER.values()):
            mm.new_widget(kind, it, *g)
        mm.setword(pod.DATA['PDEQ_SHOWLIST'][0], mm.new_deque([]))
        n_before = len(mm.kids(it))
        mm.create_fail = {fail}
        mm.call(PSYMS['ah_restyle'], a0=it, count=200000)
        expect(len(mm.kids(it)) == n_before and mm.geo(it)[3] == 100 and not mm.style
               and len(mm.destroyed) == 1, f'a failing {fail} create: the one that was made is destroyed, the header stays stock')
    # the stock functions' own results are what the hook returns through: the hook has no return value
    # (albuminfo_listitem0_layout is void); the trampoline resumes stock at the fourth word
    expect(PSYMS['stock_albuminfo_header_trampoline'] >= pod.BASE, 'the trampoline is in the payload')
    tr = [struct.unpack_from('<I', open(os.path.join(BUILD, 'patch.bin'), 'rb').read(), PSYMS['stock_albuminfo_header_trampoline'] - pod.BASE + 4 * i)[0]
          for i in range(4)]
    expect(tr[2] == pod.j(HEADER_BUILDER + 12) and tr[3] == 0, 'the trampoline jumps to the stock function past its 3-word prologue')

    # ------------------------------------------------------------------ Shuffle: the stock Play all sequence
    shuffle = PSYMS['ah_on_shuffle']

    def played(m): return [c for c in m.calls if c[0] == 'start_player']
    def flag(m): return m.u.mem_read(pod.DATA['FORCE_REFRESH'][0], 1)[0]
    m = AlbumMachine(); m.header(tracks=6)
    m.stock_songlist = True
    starts = set()
    for clock in range(1, 41):
        m.mode = 0; m.clock = clock * 7919; m.call(shuffle, count=60000000)
        sp = played(m); starts.add(sp[0][1])
    expect(len(starts) >= 4 and starts <= set(range(6)), f'the first track is drawn at random from the album ({sorted(starts)})')
    expect(sp[0][2:] == (O['CLASS_ALBUM_TRACKS'], O['PLAY_MODE']) and len(m.played[0]) == 6,
           'the whole album is queued with its class and the stock mode argument, as Play all does')
    seq = [c[0] for c in m.calls if c[0] in ('access', 'loadSongList', 'mclSetPlayMode', 'start_player', 'deque_destroy')]
    expect(seq == ['access', 'loadSongList', 'mclSetPlayMode', 'start_player', 'deque_destroy'],
           f'access, resolve, mode, start, free ({seq})')
    expect(m.mode == O['MODE_SHUFFLE'] and ('dmrSendPlayMode', O['MODE_SHUFFLE']) in m.calls and ('notifyPlayMode',) in m.calls
           and ('write_int_config', O['MODE_SHUFFLE'], 'PLAYSET', 'PLAYMODE') in m.calls,
           'Shuffle sets the stock play mode the way the Play settings page does')
    expect(flag(m) == 1, 'force_refreshflag is set after the start, as the stock Play all does')
    expect('navigator_to_with_context' not in m.names() and 'navigator_back' not in m.names(),
           'the page stays up, as with Play all')
    expect(not any(n in m.names() for n in ('timer_add', 'pthread_create', 'window_open')), 'a start leaves no timer, thread or page behind')
    m.mode = O['MODE_SHUFFLE']; m.call(shuffle, count=60000000)
    expect(not any(c[0] in ('mclSetPlayMode', 'write_int_config') for c in m.calls) and played(m), 'already in Shuffle: nothing is written')
    # a missing file, an empty list, a queue that does not resolve: nothing starts, nothing changes
    m = AlbumMachine(); m.header(tracks=3); m.stock_songlist = True
    for p in list(m.present):
        if p.startswith('/mnt/mmc/m/'): m.present.discard(p)
    m.mode = 0; m.call(shuffle, count=60000000)
    expect(not played(m) and m.mode == 0 and ('toast', 'Storage unavailable', O['MSGINFO_KIND'], O['MSGINFO_MS']) in m.calls,
           'a missing track starts nothing and says so')
    m = AlbumMachine(); m.header(tracks=0); m.stock_songlist = True
    m.call(shuffle, count=60000000)
    expect(not played(m) and 'loadSongList' not in m.names(), 'an empty list starts nothing')
    m = AlbumMachine(); m.header(tracks=3); m.stock_songlist = True
    for t in m.tracks: m.setword(t + O['REC_TYPE'], 4)   # loadSongList only takes songs: nothing to queue
    m.mode = 0; m.call(shuffle, count=60000000)
    expect(not played(m) and m.mode == 0 and 'mclSetPlayMode' not in m.names() and 'deque_destroy' in m.names(),
           'a queue that does not resolve starts nothing, changes nothing and is freed')
    # an artist's album and the All albums card: the page's class goes through (0xff11)
    m = AlbumMachine(); m.header(tracks=6, cls=0xff11); m.stock_songlist = True
    m.clock = 99991; m.call(shuffle, count=60000000)
    expect(played(m) and played(m)[0][2] == 0xff11 and any(c[0] == 'loadSongList' and c[3] == 0xff11 for c in m.calls),
           'an artist album and the All albums card queue with class 0xff11')

    # ------------------------------------------------------------------ hit tests (demo's widget_find_target)
    m = AlbumMachine(); item = m.header()
    art, title, artist, play, meta, shuf = m.kids(item)
    nm = {art: 'cover', title: 'title', artist: 'artist', play: 'btn_play', meta: 'meta', shuf: 'btn_shuffle', item: 'header'}
    def node_of(h):
        gx, gy, gw, gh = m.geo(h)
        flags = F_ENABLE | F_VISIBLE | (F_SENSITIVE if m.props.get((h, 'sensitive'), 1) not in (0,) else 0)
        n = Node(nm.get(h, f'w{h:x}'), gx, gy, gw, gh, flags)
        n.children = [node_of(c) for c in m.kids(h)]
        return n
    hdr = node_of(item)
    hdr.w = 310
    window = Node('albuminfo_page', 0, 0, 320, CLIENT_H, children=[
        Node('navigationbar_view', 0, 0, 320, 50, children=[Node('btn_return', 0, 0, 80, 50)]),
        Node('albuminfo_listview', 0, 50, 320, 400, children=[Node('albuminfo_scrollview', 0, 0, 310, 400, children=[hdr])])])
    top = 50
    for x, y, want in ((O['AH_PAD'] + 55, O['AH_BTN_Y'] + 18, 'btn_play'), (O['AH_SHUFFLE_X'] + 55, O['AH_BTN_Y'] + 18, 'btn_shuffle'),
                       (O['AH_PAD'] + 2, O['AH_BTN_Y'] + 2, 'btn_play'), (O['AH_PAD'] + O['AH_BTN_W'] - 2, O['AH_BTN_Y'] + O['AH_BTN_H'] - 2, 'btn_play'),
                       (O['AH_SHUFFLE_X'] + 2, O['AH_BTN_Y'] + 2, 'btn_shuffle'),
                       (O['AH_SHUFFLE_X'] + O['AH_BTN_W'] - 2, O['AH_BTN_Y'] + O['AH_BTN_H'] - 2, 'btn_shuffle'),
                       (O['AH_PAD'] + 60, 40, 'cover'), (O['AH_TEXT_X'] + 20, O['AH_TITLE_Y'] + 5, 'title'),
                       (O['AH_TEXT_X'] + 20, O['AH_ARTIST_Y'] + 5, 'artist'),
                       (O['AH_TEXT_X'] + 20, O['AH_META_Y'] + 5, 'header'),     # the year line lets the touch through to the header
                       (O['AH_SHUFFLE_X'] - 5, O['AH_BTN_Y'] + 18, 'header'),   # the 10 px gap between the buttons
                       (O['AH_SHUFFLE_X'] + O['AH_BTN_W'] + 20, O['AH_BTN_Y'] + 18, 'header'),   # right of the buttons
                       (O['AH_PAD'] + 55, O['AH_BTN_Y'] - 3, 'header'),          # above the buttons
                       (150, O['AH_HDR_H'] - 4, 'header')):
        got = stock_target(m, window, x, top + y)
        expect(got[-1] == want and 'albuminfo_scrollview' in got, f'a touch at ({x},{y}) lands on {want} ({got})')
    expect(stock_target(m, window, 40, 25)[-1] == 'btn_return', 'Back on the album page is still hit')
    expect(O['AH_BTN_W'] >= 44 and O['AH_BTN_H'] >= 36, 'both buttons are at least 36 px tall and 44 wide (docs/ui.md)')

    # ------------------------------------------------------------------ the cover size and the page theme
    for theme in ('default', 'theme1'):
        path = os.path.join(WORK, 'rootfs', 'release/assets', theme, 'raw/styles/albuminfo_page.bin')
        import awtk_style
        th = awtk_style.parse(open(path, 'rb').read())
        btn = {i.state: i for i in th.items if (i.widget, i.style) == ('button', 'btn_albumbtn_style')}
        expect(sorted(btn) == sorted(('normal', 'pressed', 'over', 'focused', 'disable')), f'{theme}: the dark button style has every state')
        bad = [s for s, i in btn.items() if not is_dark(i.color('bg_color')) or i.color('text_color') != '#FFFFFFFF'
               or i.get('font_size') != 20 or i.has('icon')]
        expect(not bad and btn['pressed'].color('bg_color') == '#333333FF', f'{theme}: dark fill, white 20 px text, lighter when pressed, no icon ({bad})')
        meta = [i for i in th.items if (i.widget, i.style) == ('hscroll_label', 'srlabel_meta15_style')]
        expect(len(meta) == 3 and all(i.get('font_size') == 15 and i.color('text_color') == '#AAAAAAFF' for i in meta),
               f'{theme}: the year line is 15 px #AAAAAA')
        stock = [i for i in th.items if (i.widget, i.style) == ('button', 'btn_imgplayall_style')]
        expect(len(stock) == 5 and all(i.get('icon') in ('playall', 'playall_down') for i in stock),
               f'{theme}: the stock Play all style is untouched (a header the hook leaves alone keeps it)')

    # ------------------------------------------------------------------ Cover Flow
    # the artist's Cover Flow starts on its first album; the main one keeps its last album
    m = artists_machine(); m.load_image = 0; m.stock_songlist = True
    m.call(PSYMS['artists_open'], count=5000000)
    m.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    expect(shelf_value(m) == 0,
           "the artist's Cover Flow starts on its first (leftmost) album, not the stock slide_menu's item 1")
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'Kind of Blue') in m.calls
           and ('widget_set_text_utf8', m.widgets['label_artist'], 'Miles Davis') in m.calls, 'and its captions are set')
    m.tap(O['CF_CX'], count=60000000)
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ARTIST_ALBUMS'], 0) in m.calls,
           "a tap on that album opens the stock album page with the artist page's class")
    # one album: the captions are there as soon as the page opens
    m = artists_machine(); m.call(PSYMS['artists_open'], count=5000000)
    m.call(PSYMS['ar_on_artist'], a0=1, count=8000000)
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'Pastel Blues') in m.calls
           and ('widget_set_text_utf8', m.widgets['label_artist'], 'Nina Simone') in m.calls and shelf_value(m) == 0,
           'an artist with one album shows its captions on open')
    for last in (0, 2):
        m = cover_machine(albums=3)
        key = fnv(fnv(O['FNV_SEED'], f'Artist {last}'), f'Album {last}') or 1
        m.files['/mnt/mmc/.coverflow/album'] = 4; m.saved_album = key
        m.call(PSYMS['coverflow_open'], count=5000000)
        expect(shelf_value(m) == last
               and ('widget_set_text_utf8', m.widgets['label_album'], f'Album {last}') in m.calls,
               f'the main Cover Flow reopens on its last album ({last})')
    m = cover_machine(albums=1); m.call(PSYMS['coverflow_open'], count=5000000)
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'Album 0') in m.calls, 'a library with one album shows its captions on open')
    tree = awtk_ui.parse(open(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1pod_cover.bin'), 'rb').read())
    expect('view_tracks' not in [x.name for x in tree.walk()], 'the Cover Flow asset has no track list view any more')


def run(ctx):
    album_tests(ctx.expect, ctx.page, ctx.cover_asset)
