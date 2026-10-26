"""Artists: the list page and Cover Flow scoped to one artist."""
import json, os, re, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)


def artists_tests(expect, page, cover_asset):
    """The menu's Artists row, the Artists page and Cover Flow scoped to one artist."""
    import awtk_ui
    row = artists_row(page)
    open_ = PSYMS['artists_open']
    asset = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1pod_artists.bin')

    # 27. The menu's Artists row opens our list, not the stock Artists page; nothing else moved.
    m = artists_machine()
    m.call(PSYMS['on_row'], a0=PSYMS['pod_rows_0'] + 12 * row, count=5000000)
    expect(('window_open', 'm1pod_artists') in m.calls, 'the Artists row opens m1pod_artists')
    expect('stock_resume' not in m.names(), 'the Artists row no longer opens the stock page')
    P = pod_pages
    expect([(r.label, r.arg) for r in page.rows if r.action == P.ACT_HOME] ==
           [('Songs', P.HOME_MYMUSIC), ('Albums', P.HOME_ALBUM), ('Genres', P.HOME_GENRE), ('Folders', P.HOME_FOLDER),
            ('Playlists', P.HOME_PLAYLIST)],
           'the other library rows still open their stock Home pages; only Artists changed')

    # 28. The list is the stock Artists query, one stock-styled row per artist, in its order.
    m = artists_machine()
    v = m.call(open_, count=5000000)
    expect(v == 0, 'artists_open returns 0')
    expect(('loadLocalClassList', O['CLASS_ARTISTS']) in m.calls, 'the list comes from loadLocalClassList(0xf004)')
    expect('deque_assign' in m.names(), 'the stock list is copied')
    sv = m.widgets['pod_scrollview']
    rows = [c[1] for c in m.calls if c[0] == 'list_item_create']
    expect(len(rows) == 3 and m.children.get(sv) == rows, f'one row per artist in the scroll view ({len(rows)})')
    labels = {c[2]: c[1] for c in m.calls if c[0] == 'hscroll_label_create'}
    texts = {c[1]: c[2] for c in m.calls if c[0] == 'widget_set_text_utf8'}
    expect([texts.get(labels.get(r)) for r in rows] == ['Miles Davis', 'Nina Simone', 'Unknown Artist'],
           "each row shows the stock row's name (REC_TITLE), in the stock order")
    for r in rows:
        lab = labels.get(r)
        expect(m.props.get((r, 'style')) == 'list_item_style' and lab
               and m.props.get((lab, 'style')) == 'srlabel_leftwhite21_style'
               and m.props.get((lab, 'hscroll_label_set_only_parent_focus')) == 1,
               'an artist row is a stock list_item with an srlabel_leftwhite21_style label')
    imgs = [c for c in m.calls if c[0] == 'image_base_set_image']
    expect(len(imgs) == 3 and all(c[2] == 'right_arrow' for c in imgs), 'every artist row has the right_arrow chevron')
    clicks = [c for c in m.calls if c[0] == 'widget_on' and c[2] == O['EVT_CLICK'] and c[1] in rows]
    expect([c[4] for c in clicks] == [0, 1, 2] and all(c[3] == PSYMS['ar_on_artist'] for c in clicks),
           "each row's click carries its index")
    expect(m.props.get((sv, 'virtual_h')) == 3 * 52, 'the scroll view is as tall as the rows')
    expect(m.props.get((m.widgets['label_status'], 'sensitive')) == 0, 'the hidden message takes no touch')

    # 29. Real hit tests (demo's widget_find_target) on the page as the asset and the payload
    #     leave it: every row is hit through the list_view/scroll_view, the navbar keeps its
    #     buttons, the hidden message takes nothing.
    root = asset_tree(asset)
    if m.props.get((m.widgets['label_status'], 'sensitive')) == 0: node(root, 'label_status').flags &= ~F_SENSITIVE
    node(root, 'pod_scrollview').children = [Node(f'artist{i}', 0, i * 52, 310, 52) for i in range(len(rows))]
    for i in range(len(rows)):
        got = stock_target(m, root, 160, 50 + i * 52 + 26)
        expect(got[-1] == f'artist{i}' and 'pod_scrollview' in got, f'artist row {i} is hit through the scroll view ({got})')
    expect(stock_target(m, root, 40, 25)[-1] == 'btn_return', 'Back on the Artists page is hit')
    expect(stock_target(m, root, 290, 25)[-1] == 'btn_backtoplayer', 'Now Playing on the Artists page is hit')
    got = stock_target(m, root, 160, 225)
    expect('label_status' not in got, f'the hidden message is not hit ({got})')
    tree = awtk_ui.parse(open(asset, 'rb').read())
    lv = next(w for w in tree.walk() if w.name == 'pod_listview')
    expect(lv.y == 50 and lv.y + lv.h == CLIENT_H, 'the artist list fills the window under the navbar (50-450)')
    expect([c.type for c in lv.children] == ['scroll_view', 'scroll_bar_m'], 'list_view > scroll_view + scroll_bar_m, as stock')

    # 30. Back leaves the Artists page; closing it frees its copy.
    m.call(PSYMS['ar_on_back'], count=200000)
    expect('navigator_back' in m.names(), 'Back on the Artists page goes back')
    m.call(PSYMS['ar_on_destroy'], count=200000)
    expect('deque_destroy' in m.names(), 'closing the Artists page frees its list')

    # 31. An empty library: the message, no rows. A broken asset: leave.
    m = artists_machine(artists=())
    m.call(open_, count=2000000)
    expect('list_item_create' not in m.names(), 'no artists, no rows')
    expect(any(c[0] == 'widget_set_text_utf8' and 'Update Local Music' in c[2] for c in m.calls), 'no artists says so')
    expect(m.props.get((m.widgets['pod_listview'], 'sensitive')) == 0
           and m.props.get((m.widgets['label_status'], 'visible')) == 1, 'the empty list is hidden, the message shown')
    m = artists_machine(); del m.widgets['pod_scrollview']
    expect(m.call(open_, count=2000000) == 0xffffffff and 'navigator_back' in m.names(), 'a broken Artists asset closes')

    # 32. Tap an artist: Cover Flow on exactly that artist's albums (the stock loadAlbumList(0xf004)),
    #     titled with the artist, the All albums card last, the covers the library's cached files.
    m = artists_machine()
    m.call(open_, count=5000000)
    m.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    expect(('window_open', 'm1pod_cover') in m.calls, 'an artist opens the Cover Flow page')
    la = [c for c in m.calls if c[0] == 'loadAlbumList']
    expect(la and la[0][1] == O['CLASS_ARTISTS'] and la[0][3] == 'Miles Davis', f'the stock artist query runs for that artist ({la[:1]})')
    expect(any(c[0] == '_deque_push_back' for c in m.calls), "the artist's row is copied")
    slide = m.widgets.get('slide_menu')
    expect(slide and len(m.children.get(slide, [])) == 4, 'three albums and the All albums card')
    expect(('widget_set_text_utf8', m.widgets['label_title'], 'Miles Davis') in m.calls, 'the title is the artist')
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'Kind of Blue') in m.calls, 'the first album is centred')
    expect('pthread_create' not in m.names(), "the library's cached covers are used: nothing to build")
    expect(not any(c[0] == 'fopen' and c[1].endswith('.coverflow/album') for c in m.calls),
           "the main Cover Flow's last album is not read")
    jazz = art_file(fnv(fnv(O["FNV_SEED"], "Various Artists"), "Jazz Hits"))
    paint(m)
    loads = [c[1] for c in m.calls if c[0] == 'widget_load_image']
    expect(('file://' + jazz) in loads, f"the compilation shows the library's cover file ({loads})")
    expect(not any('00000000' in u for u in loads), 'the card has no cover file of its own')
    b, data, w, h = m.bitmap
    frame = bytes(m.u.mem_read(data, w * h * 4))
    host = host_frame(0, ring=[None] * 3 + [True] * 4)
    if host is not None:   # q2-pod's bounded artist shelf: nothing left of the first album, no repeats
        expect(frame == host, 'at the first album nothing is drawn to its left (the host frame of that ring)')

    # 33. The card: All albums over the artist; it opens the stock albuminfo_page on the stock All songs
    #     row of the artist's list (class 0xff01, row = the card's index, the last), which the page
    #     loads as every song of the artist (0xff11); the artist is put into the browsing record by
    #     loadAlbumList(0xf004, artist) first, and the cover-task list is rebuilt from that list.
    m.props[(slide, 'value')] = 3
    m.call(PSYMS['on_changed'], count=2000000)
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'All albums') in m.calls, 'the card reads All albums')
    expect(('widget_set_text_utf8', m.widgets['label_artist'], 'Miles Davis') in m.calls, 'over the artist')
    m.tap(O['CF_CX'])
    order = [c[0] for c in m.calls if c[0] in ('loadAlbumList', 'albumcoverinfo_init', 'loadAlbumdetailList', 'navigator_to_with_context')]
    expect(order == ['loadAlbumList', 'albumcoverinfo_init', 'navigator_to_with_context'],
           f'the artist goes into the browsing record, then the page opens ({order})')
    la = [c for c in m.calls if c[0] == 'loadAlbumList']
    expect(la and la[0][1] == O['CLASS_ARTISTS'] and la[0][3] == 'Miles Davis', f'for that artist ({la[:1]})')
    expect(('batchadd_albumcover_task', 0, 0) in m.calls, 'the cover thread is released for the page\'s cover task')
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ARTIST_ALBUMS'], 3) in m.calls,
           'albuminfo_page opens with class 0xff01 and the card row (3)')
    cls, row, shown = m.opened_album
    card = m.deques[shown][row]
    expect(m.word(card + O['REC_ID']) == O['ID_ALL_SONGS'] & 0xffffffff and ('albumcoverinfo_init', shown) in m.calls,
           'that row of the list is the stock All songs row')
    expect(not any(c[0] in ('list_item_create', 'loadSongList') for c in m.calls), 'no track list or play code of our own')

    # 34. A centre album: the same, with its own row; Back from the covers returns to the Artists list.
    m.props[(slide, 'value')] = 1
    m.call(PSYMS['on_changed'], count=2000000)
    m.tap(O['CF_CX'])
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ARTIST_ALBUMS'], 1) in m.calls
           and m.read_cstr(m.word(m.deques[m.opened_album[2]][1] + O['REC_ALBUM'])) == 'Jazz Hits',
           'the centre album opens as the stock artist page opens it (class 0xff01, its row)')
    m.call(PSYMS['on_back'], count=2000000)
    expect('navigator_back' in m.names(), 'Back from the covers returns to the Artists list')

    # 35. The shelf has ends: a drag right from the first album does not wrap to the card, a drag
    #     left from the card does not wrap to the first album.
    m.props[(slide, 'value')] = 0
    m.touch('down', 60, t=9000); m.touch('move', 120, t=9300); m.touch('move', 200, t=9600)
    off = struct.unpack('<i', struct.pack('<I', m.props.get((slide, 'xoffset'), 0) & 0xffffffff))[0]
    m.touch('up', 200, t=9900); m.settle()
    expect(off == 0 and not any(c[0] == 'slide_menu_set_value' for c in m.calls), f'the first album is an end (xoffset {off})')
    m.props[(slide, 'value')] = 3
    m.touch('down', 250, t=12000); m.touch('move', 150, t=12300); m.touch('move', 20, t=12600)
    m.touch('up', 20, t=12610); m.settle()
    expect(not any(c[0] == 'slide_menu_set_value' for c in m.calls), 'the card is the other end')
    m.props[(slide, 'value')] = 3
    m.touch('down', 100, t=15000); m.touch('move', 200, t=15300); m.touch('move', 290, t=15600)
    m.touch('up', 290, t=15900); m.settle()
    expect(('slide_menu_set_value', 1) in m.calls, 'a drag of two spacings from the card goes back two albums')

    # 36. Closing: the scoped page writes no last album, and the main Cover Flow still reads its own.
    m.call(PSYMS['on_destroy'], count=2000000)
    expect('fwrite' not in m.names(), "scoped browsing leaves the main Cover Flow's last album alone")
    expect(sum(1 for c in m.calls if c[0] == 'deque_destroy') >= 2, "the artist's albums and row are freed")
    m.files['/mnt/mmc/.coverflow/album'] = 4; m.saved_album = 0x1234abcd
    m.call(PSYMS['coverflow_open'], count=8000000)
    expect(any(c[0] == 'fopen' and c[1] == '/mnt/mmc/.coverflow/album' and c[2] == 'rb' for c in m.calls),
           'the main Cover Flow still reads its last album')

    # 37. One album: no card. No albums: the message. Cover Flow already open: refused.
    m = artists_machine(); m.call(open_, count=5000000)
    m.call(PSYMS['ar_on_artist'], a0=1, count=8000000)
    slide = m.widgets.get('slide_menu')
    expect(slide and len(m.children.get(slide, [])) == 1, 'an artist with one album gets no card')
    expect(m.call(PSYMS['ar_on_artist'], a0=0, count=200000) == 0 and
           [c for c in m.calls if c[0] == 'window_open'] == [], 'Cover Flow does not open twice')
    m = artists_machine(); m.call(open_, count=5000000)
    m.call(PSYMS['ar_on_artist'], a0=2, count=8000000)
    expect('slide_menu' not in m.names() and
           any(c[0] == 'widget_set_text_utf8' and c[2] == 'No albums' for c in m.calls),
           'an artist without albums says No albums')
    expect(m.props.get((m.widgets['view_covers'], 'sensitive')) == 0, 'and its empty frame takes no touch')

    # 38. Kill switch: the entry falls through, so neither page can open.
    m = artists_machine(); m.present.add('/mnt/mmc/m1pod-off')
    m.call(PSYMS['m1pod_home_click'], a0=m.icon(str(pod_pages.HOME_ENTRY)), count=200000)
    expect('window_open' not in m.names() and 'stock_resume' in m.names(), 'the kill switch keeps Artists closed')

    # 39. The scoped page's hit test: the covers take touches through the touch layer.
    m = artists_machine(); m.call(open_, count=5000000); m.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    got = stock_target(m, cover_page_tree(m, cover_asset), 160, CF_FRAME_Y + 80)
    expect(got[-1] == 'touch_layer', f"the artist's covers take touches ({got})")


def run(ctx):
    artists_tests(ctx.expect, ctx.page, ctx.cover_asset)
