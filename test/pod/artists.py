"""Artists: the list page and Cover Flow scoped to one artist."""
import os, struct
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
    expect([(r.label, r.arg) for r in page.rows[:9] if r.action == P.ACT_HOME] ==
           [('Songs', P.HOME_MYMUSIC), ('Genres', P.HOME_GENRE), ('Folders', P.HOME_FOLDER)],
           'the other library rows still open their stock Home pages; only Albums (the grid), Artists and Playlists (the mosaic grid) changed')

    # 28. The list is the stock Artists query, one stock-styled row per artist, in its order.
    m = artists_machine()
    v = m.call(open_, count=5000000)
    opened = list(m.calls)
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
        got = stock_target(m, root, 160, pod_ui.NAVBAR_H + i * 52 + 26)
        expect(got[-1] == f'artist{i}' and 'pod_scrollview' in got, f'artist row {i} is hit through the scroll view ({got})')
    expect(stock_target(m, root, 40, 25)[-1] == 'btn_return', 'Back on the Artists page is hit')
    expect(stock_target(m, root, 290, 25)[-1] == 'btn_backtoplayer', 'Now Playing on the Artists page is hit')
    got = stock_target(m, root, 160, 225)
    expect('label_status' not in got, f'the hidden message is not hit ({got})')
    tree = awtk_ui.parse(open(asset, 'rb').read())
    lv = next(w for w in tree.walk() if w.name == 'pod_listview')
    expect(lv.y == pod_ui.NAVBAR_H and lv.y + lv.h == CLIENT_H, 'the artist list fills the window under the navbar (50-450)')
    expect([c.type for c in lv.children] == ['scroll_view', 'scroll_bar_m'], 'list_view > scroll_view + scroll_bar_m, as stock')

    # 29b. The navbar toggle: in the Albums toggle's slot (flush left of Now Playing), hit by a touch, the title
    #      ends at its left edge, the glyph is the other mode's; no segment strip is left.
    tog = tree.find('btn_artisttype')
    expect(tog is not None and (tog.x, tog.y, tog.w, tog.h) == (O['NAV_VIEW_X'], 0, O['NAV_VIEW_W'], O['NAV_H'])
           and tog.x + tog.w == tree.find('btn_backtoplayer').x, 'btn_artisttype is in the toggle slot, flush left of Now Playing')
    lbl = tree.find('label_title')
    expect(lbl.x + lbl.w == O['NAV_VIEW_X'], 'the title ends where the toggle begins')
    expect(not [w for w in tree.walk() if w.name.startswith('seg_')], 'the segment strip is gone')
    expect(tog.get('style:normal:icon') == 'pod_nav_albumartist' and tog.get('style:pressed:icon') == 'pod_nav_albumartist_down',
           'built in Artist mode, the button shows the Album Artist glyph')
    expect(stock_target(m, root, O['NAV_VIEW_X'] + 20, 25)[-1] == 'btn_artisttype', 'a touch on the toggle hits it')
    title, tglyph = m.widgets['label_title'], m.widgets['btn_artisttype']
    expect(('widget_set_text_utf8', title, 'Artists') in opened and m.props.get((tglyph, 'style:normal:icon')) == 'pod_nav_albumartist'
           and m.props.get((tglyph, 'style:pressed:icon')) == 'pod_nav_albumartist_down', 'artist_type 0: "Artists", the Album Artist glyph')
    expect(opened.count(('widget_set_text_utf8', title, 'Artists')) == 1, 'the title is set once')
    import awtk_style, awtk_text
    raw = os.path.join(WORK, 'rootfs', 'release/assets/default/raw')
    px = awtk_style.parse(open(os.path.join(raw, 'styles/default.bin'), 'rb').read()).find('label', 'navbar_label_white', 'normal')[0].get('font_size')
    ttf = awtk_text.Ttf(os.path.join(raw, 'fonts/default.ttf'))
    widest = max(awtk_text.awtk_width(ttf, t, px) for t in ('Artists', 'Album Artists'))
    expect(lbl.x + widest <= O['NAV_VIEW_X'], f'both titles fit before the toggle ({widest} px at {px} in {O["NAV_VIEW_X"] - lbl.x})')
    tclicks = [c for c in opened if c[0] == 'widget_on' and c[1] == tglyph and c[2] == O['EVT_CLICK']]
    expect(len(tclicks) == 1 and tclicks[0][3] == PSYMS['ar_on_toggle'], 'the toggle button is bound')

    # 29c. Tapping it makes the stock switch's writes (artist_type = 1, [PLAYSET] ARTISTTYPE, the stock page's
    #      reload flag), retitles and re-icons and lists again: the album-artist rows, scrolled to the top.
    AT, RELOAD = pod.DATA['ARTIST_TYPE'][0], pod.DATA['ARTIST_RELOAD'][0]
    m.calls = []
    m.call(PSYMS['ar_on_toggle'], count=5000000)
    new = m.calls
    expect(m.word(AT) == 1 and ('write_int_config', 1, 'PLAYSET', 'ARTISTTYPE') in new and m.u.mem_read(RELOAD, 1)[0] == 1,
           'a tap sets artist_type, saves [PLAYSET] ARTISTTYPE and raises the stock reload flag')
    expect(('widget_set_text_utf8', title, 'Album Artists') in new and m.props.get((tglyph, 'style:normal:icon')) == 'pod_nav_artist'
           and m.props.get((tglyph, 'style:pressed:icon')) == 'pod_nav_artist_down', 'the title reads "Album Artists", the glyph is the Artist one')
    expect(('loadLocalClassList', O['CLASS_ARTISTS']) in new and ('widget_destroy_children', sv) in new
           and ('widget_set_prop_int', sv, 'yoffset', 0) in new, 'the old rows go, the stock query runs again, the list is at the top')
    rows = [c[1] for c in new if c[0] == 'list_item_create']
    labels = {c[2]: c[1] for c in new if c[0] == 'hscroll_label_create'}
    texts = {c[1]: c[2] for c in new if c[0] == 'widget_set_text_utf8'}
    expect([texts.get(labels.get(r)) for r in rows] == ['Miles Davis', 'Various Artists'], 'the list is the album-artist list (sorted: stock has Various Artists first)')
    expect(m.props.get((sv, 'virtual_h')) == 2 * 52, 'the scroll view is as tall as the new rows')
    expect('deque_destroy' in [c[0] for c in new], 'the previous list copy is freed')
    # a second tap goes back to Artist
    m.call(PSYMS['ar_on_toggle'], count=5000000)
    expect(m.word(AT) == 0 and ('write_int_config', 0, 'PLAYSET', 'ARTISTTYPE') in m.calls and m.props.get((tglyph, 'style:normal:icon')) == 'pod_nav_albumartist'
           and m.calls.count(('widget_set_text_utf8', title, 'Artists')) == 1, 'the second tap sets Artist again, title and glyph with it')
    # the page opens with the saved setting shown
    m3 = artists_machine(); m3.setword(AT, 1); m3.call(open_, count=5000000)
    t3 = {c[1]: c[2] for c in m3.calls if c[0] == 'widget_set_text_utf8'}
    expect([t3.get(c[1]) for c in m3.calls if c[0] == 'hscroll_label_create'] == ['Miles Davis', 'Various Artists']
           and t3.get(m3.widgets['label_title']) == 'Album Artists' and m3.props.get((m3.widgets['btn_artisttype'], 'style:normal:icon')) == 'pod_nav_artist',
           'opening with album artist set lists them, titled "Album Artists" with the Artist glyph')
    # without the button or the title the page still lists in the current mode
    m4 = artists_machine(); del m4.widgets['btn_artisttype']; del m4.widgets['label_title']
    m4.call(open_, count=5000000)
    expect(len([c for c in m4.calls if c[0] == 'list_item_create']) == 3 and 'navigator_back' not in m4.names(),
           'a page without the toggle or the title still lists')

    # 30. Back leaves the Artists page; closing it frees its copy.
    m.call(PSYMS['pod_on_back'], count=200000)
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
    open_calls = list(m.calls)
    expect(('window_open', 'm1pod_cover') in m.calls, 'an artist opens the Cover Flow page')
    la = [c for c in m.calls if c[0] == 'loadAlbumList']
    expect(la and la[0][1] == O['CLASS_ARTISTS'] and la[0][3] == 'Miles Davis', f'the stock artist query runs for that artist ({la[:1]})')
    expect(any(c[0] == '_deque_push_back' for c in m.calls), "the artist's row is copied")
    expect(('widget_set_text_utf8', m.widgets['label_title'], 'Miles Davis') in m.calls, 'the title is the artist')
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'Kind of Blue') in m.calls, 'the first album is centred')
    expect('pthread_create' not in m.names(), "the library's cached covers are used: nothing to build")
    expect(not any(c[0] == 'fopen' and c[1].endswith('.coverflow/album') for c in m.calls),
           "the main Cover Flow's last album is not read")
    jazz = art_file(fnv(fnv(O["FNV_SEED"], "Various Artists"), "Jazz Hits"))
    loads = [c[1] for c in open_calls if c[0] == 'widget_load_image']   # decoded when the shelf is built, not in paint
    expect(('file://' + jazz) in loads, f"the compilation shows the library's cover file ({loads})")
    expect(not any('00000000' in u for u in loads), 'the card has no cover file of its own')
    files = [u for u in loads if u.startswith('file://')]
    expect(len(files) == len(set(files)) == 3, f'the shelf asks for nothing past its ends: three albums, each once ({files})')
    paint(m)
    expect(not any(c[0] in ('widget_load_image', 'fopen', 'access') for c in m.calls), 'paint loads nothing')
    put_value(m, 3); m.call(PSYMS['on_changed'], count=2000000)
    card = ('widget_set_text_utf8', m.widgets['label_album'], 'All albums') in m.calls
    put_value(m, 4); m.call(PSYMS['on_changed'], count=2000000)
    expect(card and not any(c[0] == 'widget_set_text_utf8' for c in m.calls), 'three albums and the All albums card, no more')
    put_value(m, 0); m.call(PSYMS['on_changed'], count=2000000)
    b, data, w, h = m.bitmap
    frame = bytes(m.u.mem_read(data, w * h * 4))
    host = host_frame(0, ring=[None] * 3 + [True] * 4)
    if host is not None:   # q2-pod's bounded artist shelf: nothing left of the first album, no repeats
        expect(frame == host, 'at the first album nothing is drawn to its left (the host frame of that ring)')

    # 32b. Landscape on an artist's Cover Flow (the choice is shared with the main one): the body-sized frame, the card's
    #      caption All albums over the artist, and the shelf still has its ends.
    lw, lh = O['CFL_W'], O['CFL_H']
    ml = artists_machine(); ml.fs['/mnt/data/m1pod-landscape'] = b'1\n'; ml.canvas_mem = ml.alloc(0x80)
    ml.call(open_, count=5000000); ml.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    expect([(c[1], c[2]) for c in ml.calls if c[0] == 'bitmap_create_ex'] == [(lh, lw)], 'the artist\'s Cover Flow opens in landscape when that is saved')
    def paint_land(m):
        ev = m.alloc(0x40); m.u.mem_write(ev, bytes(0x40)); m.setword(ev + O['EVENT_PAINT_CANVAS'], m.canvas_mem)
        m.glyphs.clear(); m.call(PSYMS['on_paint'], a0=0, a1=ev, count=400000000)
    put_value(ml, 3); ml.call(PSYMS['on_changed'], count=2000000); paint_land(ml)
    text = lambda size: ''.join(chr(c) for c, s in ml.glyphs if s == size)
    expect(text(22).startswith('All albums') and text(18).startswith('Miles Davis'), 'the card reads All albums over the artist in landscape too')
    put_value(ml, 0); ml.call(PSYMS['on_changed'], count=2000000); paint_land(ml)
    b, data, w, h = ml.bitmap
    frame = bytes(ml.u.mem_read(data, w * h * 4))
    host = host_frame(0, ring=[None] * 3 + [True] * 4, land=True)
    if host is not None:
        at = lambda x, y: (x * lh + lh - 1 - y) * 4
        ok = all(frame[at(x, y):at(x, y) + 4] == host[at(x, y):at(x, y) + 4]
                 for y in range(0, O['CFL_ALBUM_Y'] - 6, 3) for x in range(0, lw, 2))
        expect(ok, 'at the first album nothing is drawn to its left in landscape (the host frame of that ring)')

    # 33. The card: All albums over the artist; it opens the stock albuminfo_page on the stock All songs
    #     row of the artist's list (class 0xff01, row = the card's index, the last), which the page
    #     loads as every song of the artist (0xff11); the artist is put into the browsing record by
    #     loadAlbumList(0xf004, artist) first, and the cover-task list is rebuilt from that list.
    put_value(m, 3)
    m.call(PSYMS['on_changed'], count=2000000)
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'All albums') in m.calls, 'the card reads All albums')
    expect(('widget_set_text_utf8', m.widgets['label_artist'], 'Miles Davis') in m.calls, 'over the artist')
    m.tap(O['CF_CX'])
    order = [c[0] for c in m.calls if c[0] in ('loadAlbumList', 'albumcoverinfo_init', 'navigator_to_with_context')]
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
    put_value(m, 1)
    m.call(PSYMS['on_changed'], count=2000000)
    m.tap(O['CF_CX'])
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ARTIST_ALBUMS'], 1) in m.calls
           and m.read_cstr(m.word(m.deques[m.opened_album[2]][1] + O['REC_ALBUM'])) == 'Jazz Hits',
           'the centre album opens as the stock artist page opens it (class 0xff01, its row)')
    m.call(PSYMS['on_back'], count=2000000)
    expect('navigator_back' in m.names(), 'Back from the covers returns to the Artists list')

    # 35. The shelf has ends: a drag right from the first album does not wrap to the card, a drag
    #     left from the card does not wrap to the first album.
    put_value(m, 0)
    m.touch('down', 60, t=9000); m.touch('move', 120, t=9300); m.touch('move', 200, t=9600)
    off = struct.unpack('<i', struct.pack('<I', shelf_off(m) & 0xffffffff))[0]
    m.touch('up', 200, t=9900); m.settle()
    expect(0 < off <= O['CF_VIEW_H'] * O['OVER_NUM'] // O['OVER_DEN'] and shelf_off(m) == 0 and shelf_value(m) == 0 and not any(c[0] == 'set_value' for c in m.calls),
           f'the first album is an end: stretched by the rubber band (xoffset {off}), then back at 0 with no wrap')
    put_value(m, 3)
    m.touch('down', 250, t=12000); m.touch('move', 150, t=12300); m.touch('move', 20, t=12600)
    m.touch('up', 20, t=12610); m.settle()
    expect(not any(c[0] == 'set_value' for c in m.calls), 'the card is the other end')
    put_value(m, 3)
    m.touch('down', 100, t=15000); m.touch('move', 200, t=15300); m.touch('move', 290, t=15600)
    m.touch('up', 290, t=15900); m.settle()
    expect(('set_value', 1) in m.calls, 'a drag of two spacings from the card goes back two albums')

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
    shown = ('widget_set_text_utf8', m.widgets['label_album'], 'Pastel Blues') in m.calls
    put_value(m, 1); m.call(PSYMS['on_changed'], count=2000000)
    expect(shown and not any(c[0] == 'widget_set_text_utf8' for c in m.calls), 'an artist with one album gets no card')
    put_value(m, 0)
    expect(m.call(PSYMS['ar_on_artist'], a0=0, count=200000) == 0 and
           [c for c in m.calls if c[0] == 'window_open'] == [], 'Cover Flow does not open twice')
    m = artists_machine(); m.call(open_, count=5000000)
    m.call(PSYMS['ar_on_artist'], a0=2, count=8000000)
    expect('view' not in m.names() and
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

    # 39b. The navbar's All albums button (btn_allalbums, the slot left of Now Playing): on the artist page only, and only
    #      with the card; a tap does what the card's does (same row, so Back returns to the covers).
    tree = awtk_ui.parse(open(cover_asset, 'rb').read())
    btn = tree.find('btn_allalbums')
    flags = lambda w: {k: v for k, v in w.props}
    expect(btn and (btn.x, btn.y, btn.w, btn.h) == (O['NAV_VIEW_X'], 0, O['NAV_VIEW_W'], pod_ui.NAVBAR_H)
           and flags(btn).get('visible') == 'false' and flags(btn).get('sensitive') == 'false'
           and 'pod_nav_allalbums_down' in str(btn.props) and 'pod_nav_allalbums' in str(btn.props),
           'the asset has the button in the shared slot (x 214, w 46), hidden and insensitive, with its glyph and pressed glyph')
    def centre(m):
        b = node(cover_page_tree(m, cover_asset), 'btn_allalbums')
        return b.x + b.w // 2, b.y + b.h // 2
    def opened(m): return [c[:1] + c[2:] if c[0] == 'albumcoverinfo_init' else c for c in m.calls   # the list handle differs per machine
                           if c[0] in ('loadAlbumList', 'albumcoverinfo_init', 'batchadd_albumcover_task', 'navigator_to_with_context')]
    def seed(m): m.props[(m.widgets['label_title'], 'x')] = 58; m.props[(m.widgets['label_title'], 'h')] = 22
    m = artists_machine(); seed(m); m.call(open_, count=5000000); m.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    expect(m.props.get((m.widgets['btn_allalbums'], 'visible')) == 1 and m.props.get((m.widgets['btn_allalbums'], 'sensitive')) == 1,
           'the artist page with the card shows the button (visible and sensitive)')
    expect(('widget_resize', m.widgets['label_title'], O['NAV_VIEW_X'] - 58, 22) in m.calls, 'the title ends where the button starts')
    cx, cy = centre(m)
    got = stock_target(m, cover_page_tree(m, cover_asset), cx, cy)
    expect(got[-1] == 'btn_allalbums', f"a touch on the button's middle reaches it ({got})")
    expect(stock_target(m, cover_page_tree(m, cover_asset), O['NAV_VIEW_X'] - 2, cy)[-1] != 'btn_allalbums'
           and stock_target(m, cover_page_tree(m, cover_asset), O['NAV_VIEW_X'] + O['NAV_VIEW_W'] + 2, cy)[-1] == 'btn_backtoplayer',
           'its slot is x 214..260: Now Playing starts right after it')
    m.click('btn_allalbums', count=4000000)
    via_button = opened(m)
    mc = artists_machine(); mc.call(open_, count=5000000); mc.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    put_value(mc, 3); mc.call(PSYMS['on_changed'], count=2000000); mc.tap(O['CF_CX'])
    expect(via_button == opened(mc) and ('navigator_to_with_context', 'albuminfo_page', O['CLASS_ARTIST_ALBUMS'], 3) in m.calls,
           f'the button opens the All albums row exactly as the card does, wherever the shelf is ({via_button})')
    cls, row, shown_list = m.opened_album
    expect(m.word(m.deques[shown_list][row] + O['REC_ID']) == O['ID_ALL_SONGS'] & 0xffffffff, 'that row is the stock All songs row')
    m.call(PSYMS['on_back'], count=2000000)
    expect('navigator_back' in m.names(), 'Back from the album page is the stock back to the artist covers (the page stays open)')

    # the main Cover Flow: the button stays hidden, takes no touch, does nothing, the title keeps its width
    mm = cover_machine(albums=3); seed(mm); mm.call(PSYMS['coverflow_open'], count=5000000)
    expect(mm.props.get((mm.widgets['btn_allalbums'], 'visible')) != 1 and mm.props.get((mm.widgets['btn_allalbums'], 'sensitive')) != 1
           and not any(c[0] == 'widget_resize' and c[1] == mm.widgets['label_title'] for c in mm.calls),
           'the main Cover Flow keeps the button hidden and the title as it was')
    expect(stock_target(mm, cover_page_tree(mm, cover_asset), *centre(mm))[-1] != 'btn_allalbums', 'and its slot takes no touch')
    mm.click('btn_allalbums', count=2000000)
    expect(not [c for c in mm.calls if c[0] in ('navigator_to_with_context', 'loadAlbumList')], 'even a stray click opens nothing')

    # no card (one album, none): no button
    for a0 in (1, 2):
        m1 = artists_machine(); seed(m1); m1.call(open_, count=5000000); m1.call(PSYMS['ar_on_artist'], a0=a0, count=8000000)
        expect(m1.props.get((m1.widgets['btn_allalbums'], 'visible')) != 1 and m1.props.get((m1.widgets['btn_allalbums'], 'sensitive')) != 1
               and stock_target(m1, cover_page_tree(m1, cover_asset), *centre(m1))[-1] != 'btn_allalbums',
               f'artist {a0} has no All albums card: no button, no touch')
        m1.click('btn_allalbums', count=2000000)
        expect(not [c for c in m1.calls if c[0] == 'navigator_to_with_context'], 'and a stray click opens nothing')

    # preparing: the button waits for the covers
    mp = artists_machine(); seed(mp)
    for f in [f for f in mp.present if f.startswith('/mnt/mmc/.coverflow/')]: mp.present.discard(f)
    mp.call(open_, count=5000000); mp.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    expect(('widget_set_visible', mp.widgets['btn_cancel'], 1) in mp.calls, 'the artist page is preparing covers')
    expect(mp.props.get((mp.widgets['btn_allalbums'], 'visible')) != 1 and mp.props.get((mp.widgets['btn_allalbums'], 'sensitive')) != 1
           and stock_target(mp, cover_page_tree(mp, cover_asset), *centre(mp))[-1] != 'btn_allalbums',
           'while preparing the button is hidden and insensitive')
    mp.click('btn_allalbums', count=2000000)
    expect(not [c for c in mp.calls if c[0] == 'navigator_to_with_context'], 'and a stray click opens nothing')

    # landscape keeps the navbar: the button is there and works
    ml = artists_machine(); seed(ml); ml.fs['/mnt/data/m1pod-landscape'] = b'1\n'; ml.canvas_mem = ml.alloc(0x80)
    ml.call(open_, count=5000000); ml.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    expect(ml.props.get((ml.widgets['btn_allalbums'], 'visible')) == 1 and
           stock_target(ml, cover_page_tree(ml, cover_asset), *centre(ml))[-1] == 'btn_allalbums', 'landscape: the button is shown and takes touches')
    ml.click('btn_allalbums', count=4000000)
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ARTIST_ALBUMS'], 3) in ml.calls, 'and opens the All albums page')

    # closing frees the handle: a following main Cover Flow starts clean
    m.call(PSYMS['on_destroy'], count=2000000)


def shown(m, calls=None):
    """The artist names of the rows built in `calls` (default all), top to bottom."""
    calls = m.calls if calls is None else calls
    rows = [c[1] for c in calls if c[0] == 'list_item_create']
    labels = {c[2]: c[1] for c in calls if c[0] == 'hscroll_label_create'}
    texts = {c[1]: c[2] for c in calls if c[0] == 'widget_set_text_utf8'}
    return [texts.get(labels.get(r)).encode('latin-1').decode('utf-8') for r in rows]   # the harness reads C strings as latin-1


def fold(s): return ''.join(chr(ord(c) + 32) if 'A' <= c <= 'Z' else c for c in s)
def skip(s): return s[4:] if len(s) > 4 and fold(s[:4]) == 'the ' else s


def sort_model(names):
    """Independent model: runs of ASCII-initial names (not Unknown Artist) sorted by (folded name without "The ", stock
    position); every other row stays at its stock position."""
    out, i = [], 0
    ok = lambda n: n != 'Unknown Artist' and ord(n[:1] or 'a') < 128
    while i < len(names):
        j = i
        while j < len(names) and ok(names[j]): j += 1
        out += sorted(range(i, j), key=lambda k: (fold(skip(names[k])), k))
        if j == i: out.append(i); j += 1
        i = j
    return [names[k] for k in out], out


def sort_tests(expect):
    open_ = PSYMS['artists_open']
    # 40. The sort: the album Artist order's rule (ASCII case aside, a leading "The " dropped, ties stable).
    stock = ['the Beatles', 'Zed', 'The Who', 'Theo', 'Them', 'Abba', 'Beach Boys', 'THE ROLLING STONES', 'The', 'The ',
             'Abba', 'abba', 'Miles Davis', 'Unknown Artist']
    want, order = sort_model(stock)
    m = artists_machine(stock)
    m.call(open_, count=20000000)
    got = shown(m)
    expect(got == want, f'artists sorted: {got}')
    ix = got.index
    expect(ix('Beach Boys') < ix('the Beatles') < ix('Miles Davis') < ix('THE ROLLING STONES') < ix('Them') < ix('Theo') < ix('The Who') < ix('Zed'),
           '"The " (any case) is ignored (Beatles under B, Rolling Stones under R, The Who under W); "Them" and "Theo" are not stripped and file under T')
    expect(got[:3] == ['Abba', 'Abba', 'abba'], 'ties keep the stock order: the two "Abba" rows (stock 5, 10) before "abba" (11)')
    expect(got[-1] == 'Unknown Artist', 'Unknown Artist stays last')
    expect(got.index('The') < got.index('The ') < got.index('Them'),
           '"The" and "The " (nothing after it) are not stripped: they file under T, ahead of "Them"')
    # the tap on a display position opens the artist shown there (the stock row behind it)
    for k in (0, 1, 5, len(stock) - 1):
        m2 = artists_machine(stock); m2.call(open_, count=20000000)
        clicks = [c for c in m2.calls if c[0] == 'widget_on' and c[2] == O['EVT_CLICK'] and c[4] == k and c[3] == PSYMS['ar_on_artist']]
        expect(len(clicks) == 1, f'display row {k} is bound to its position')
        m2.call(PSYMS['ar_on_artist'], a0=k, count=8000000)
        la = [c for c in m2.calls if c[0] == 'loadAlbumList']
        expect(la and la[0][3] == got[k], f'a tap on row {k} opens {got[k]!r} ({la[:1]})')

    # 41. Non-Latin names keep stock's placement: the sortable runs are sorted around them, in place.
    stock = ['Zed', '周杰伦', 'The Beatles', 'Abba', 'Мумий Тролль', 'Bob', 'Éric', 'Aaa', 'あいみょん', 'Unknown Artist']
    want, _ = sort_model(stock)
    m = artists_machine(stock); m.call(open_, count=20000000)
    got = shown(m)
    expect(got == want, f'mixed scripts: {got}')
    expect(got[1] == '周杰伦' and got[4] == 'Мумий Тролль' and got[6] == 'Éric' and got[8] == 'あいみょん' and got[9] == 'Unknown Artist'
           and got[0] == 'Zed' and got[2:4] == ['Abba', 'The Beatles'] and got[5] == 'Bob' and got[7] == 'Aaa',
           'a non-ASCII-initial name (and Unknown Artist) stays at its stock position; the runs between are sorted')
    m2 = artists_machine(stock); m2.call(open_, count=20000000)
    m2.call(PSYMS['ar_on_artist'], a0=3, count=8000000)   # display 3 is stock row 2
    la = [c for c in m2.calls if c[0] == 'loadAlbumList']
    expect(la and la[0][3] == 'The Beatles', 'a tap in a sorted run opens the right artist')
    # stock order already as a library sorts by bytes: CJK after the Latin block; sorting leaves that block placement
    stock = ['Zed', 'abc', 'The Beatles', '周杰伦', '孙燕姿']
    m = artists_machine(stock); m.call(open_, count=20000000)
    expect(shown(m) == ['abc', 'The Beatles', 'Zed', '周杰伦', '孙燕姿'], 'CJK after the Latin block, in stock order, as stock places them')

    # 42. Both modes and the toggle: each mode's list is sorted, a tap opens the right one, the toggle re-sorts.
    m = artists_machine(); m.album_artists = [artist_rec(m, a, i + 1) for i, a in enumerate(('The Zed', 'Various Artists', 'the Abba', '周'))]
    m.call(open_, count=20000000)
    m.calls = []
    m.call(PSYMS['ar_on_toggle'], count=20000000)
    expect(shown(m) == ['the Abba', 'Various Artists', 'The Zed', '周'],
           'Album Artist mode is sorted too (The Zed files under Z); the CJK name keeps its place')
    m.calls = []
    m.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    expect([c for c in m.calls if c[0] == 'loadAlbumList'][:1] and [c for c in m.calls if c[0] == 'loadAlbumList'][0][3] == 'the Abba',
           'a tap on the first Album Artist row opens it')
    m.calls = []
    m.call(PSYMS['ar_on_toggle'], count=20000000)
    expect(shown(m) == ['Miles Davis', 'Nina Simone', 'Unknown Artist'] and 'free' in m.names(), 'toggling back re-sorts the Artist list; the old order is freed')

    # 43. Bounds: a large library is capped as before, the sort is bounded and its memory freed on closing.
    big = [f'Artist {(i * 37) % 3000:04d}' for i in range(3000)]
    big[10] = 'The ' + big[10]
    m = artists_machine(big); m.call(open_, count=300000000)
    spent = m.icount
    got = shown(m)
    cap = 2000
    expect(len(got) == cap and got == sort_model(big[:cap])[0], f'3000 artists: the first {cap} (the page cap) are listed, sorted')
    print(f'  sort of {cap} artists on open: {spent:,} payload instructions')
    expect(spent < 150000000, f'the sort and the rows are bounded ({spent:,} payload instructions)')
    callocs = [c for c in m.calls if c[0] == 'calloc']
    expect(sorted(c[1] for c in callocs if c[1] in (cap * 4,)) == [cap * 4, cap * 4], 'two arrays of 4 bytes per artist: the order and the row pointers')
    m.call(PSYMS['ar_on_destroy'], count=200000)
    expect('free' in m.names(), 'closing frees the order')

    # 44. No memory for the order: the stock order, everything works.
    stock = ['Zed', 'The Beatles', 'Abba']
    m = artists_machine(stock); m.calloc_fail = True
    expect(m.call(open_, count=20000000) == 0 and shown(m) == stock, 'allocation failure: the stock order')
    m.call(PSYMS['ar_on_artist'], a0=1, count=8000000)
    la = [c for c in m.calls if c[0] == 'loadAlbumList']
    expect(la and la[0][3] == 'The Beatles', 'and a tap opens the right artist')
    m = artists_machine(['Solo']); m.call(open_, count=20000000)
    expect(shown(m) == ['Solo'] and not [c for c in m.calls if c[0] == 'calloc'], 'one artist needs no order')


def run(ctx):
    artists_tests(ctx.expect, ctx.page, ctx.cover_asset)
    sort_tests(ctx.expect)
