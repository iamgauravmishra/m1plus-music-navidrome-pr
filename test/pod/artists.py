"""Artists: the list page and Cover Flow scoped to one artist."""
import os, struct
import mod_icons
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)


def artists_tests(expect, page, cover_asset):
    """The menu's Artists row, the Artists page and Cover Flow scoped to one artist."""
    import awtk_ui
    row = artists_row(page)
    open_ = PSYMS['artists_open']
    asset = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1plus_artists.bin')

    # 27. The menu's Artists row opens our list, not the stock Artists page; nothing else moved.
    m = artists_machine()
    m.call(PSYMS['on_row'], a0=PSYMS['pod_rows_0'] + 12 * row, count=5000000)
    expect(('window_open', 'm1plus_artists') in m.calls, 'the Artists row opens m1plus_artists')
    expect('stock_resume' not in m.names(), 'the Artists row no longer opens the stock page')
    P = pod_pages
    expect([(r.label, r.arg) for r in page.rows[:9] if r.action == P.ACT_HOME] ==
           [('Folders', P.HOME_FOLDER)],
           'the other library rows still open their stock Home pages; only Albums (the grid), Artists, Genres (our Artists page), Songs and Playlists (the mosaic grid) changed')

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
    expect(('window_open', 'm1plus_cover') in m.calls, 'an artist opens the Cover Flow page')
    la = [c for c in m.calls if c[0] == 'loadAlbumList']
    expect(la and la[0][1] == O['CLASS_ARTISTS'] and la[0][3] == 'Miles Davis', f'the stock artist query runs for that artist ({la[:1]})')
    expect(any(c[0] == '_deque_push_back' for c in m.calls), "the artist's row is copied")
    expect(('widget_set_text_utf8', m.widgets['label_title'], 'Miles Davis') in m.calls, 'the title is the artist')
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'Kind of Blue') in m.calls, 'the first album is centred')
    expect('pthread_create' not in m.names(), "the library's cached covers are used: nothing to build")
    expect(not any(c[0] == 'fopen' and c[1].endswith('.m1plus/covers/album') for c in m.calls),
           "the main Cover Flow's last album is not read")
    jazz = art_file(fnv(fnv(O["FNV_SEED"], "Various Artists"), "Jazz Hits"))
    loads = [c[1] for c in open_calls if c[0] == 'widget_load_image']   # decoded when the shelf is built (the centre) ...
    for _ in range(10):                                                  # ... and by the loader, one a tick, not in paint
        if not any(c[0] == 'timer_add' and c[1] == PSYMS['on_load'] for c in m.calls): break
        m.call(PSYMS['on_load'], count=20000000)
        loads += [c[1] for c in m.calls if c[0] == 'widget_load_image']
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
    ml = artists_machine(); ml.fs['/mnt/data/m1plus-landscape'] = b'1\n'; ml.canvas_mem = ml.alloc(0x80)
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
    m.files['/mnt/mmc/.m1plus/covers/album'] = 4; m.saved_album = 0x1234abcd
    m.call(PSYMS['coverflow_open'], count=8000000)
    expect(any(c[0] == 'fopen' and c[1] == '/mnt/mmc/.m1plus/covers/album' and c[2] == 'rb' for c in m.calls),
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
    m = artists_machine(); m.present.add('/mnt/mmc/m1plus-off')
    m.call(PSYMS['m1plus_home_click'], a0=m.icon(str(pod_pages.HOME_ENTRY)), count=200000)
    expect('window_open' not in m.names() and 'stock_resume' in m.names(), 'the kill switch keeps Artists closed')

    # 39. The scoped page's hit test: the covers take touches through the touch layer.
    m = artists_machine(); m.call(open_, count=5000000); m.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    got = stock_target(m, cover_page_tree(m, cover_asset), 160, CF_FRAME_Y + 80)
    expect(got[-1] == 'touch_layer', f"the artist's covers take touches ({got})")

    # 39b. The Songs button (btn_songs): our Songs page on all the artist's songs. The capsule's left cap on the 214 slot, Now Playing its right cap, the same for
    #      one album or many (every artist whose stock list had the All songs row); never on the main Cover Flow, a composer's page or while preparing.
    tree = awtk_ui.parse(open(cover_asset, 'rb').read())
    flags = lambda w: {k: v for k, v in w.props}
    sb = tree.find('btn_songs')
    expect(sb and (sb.x, sb.y, sb.w, sb.h) == (O['NAV_VIEW_X'], 0, O['NAV_VIEW_W'], pod_ui.NAVBAR_H)
           and flags(sb).get('visible') == 'false' and flags(sb).get('sensitive') == 'false' and 'pod_nav_songs_down' in str(sb.props) and 'pod_nav_songs' in str(sb.props)
           and mod_icons.NAV_VIEW_POS['pod_nav_songs'] == 'left' and 'NAV_SONGS_X' not in O,
           'the asset has the Songs button at x 214, 46 wide, hidden and insensitive, with its left-cap glyph and pressed glyph')
    expect(tree.find('btn_allalbums') is None and flags(tree.find('btn_backtoplayer')).get('style:normal:icon') == 'ah_nav_np',
           'the asset has no All albums button, and Now Playing is the disc (the main Cover Flow and a composer\'s page keep it)')
    def seed(m): m.props[(m.widgets['label_title'], 'x')] = 58; m.props[(m.widgets['label_title'], 'h')] = 22
    def scentre(m):
        b = node(cover_page_tree(m, cover_asset), 'btn_songs')
        return b.x + b.w // 2, b.y + b.h // 2
    def songs_shown(m): return m.props.get((m.widgets['btn_songs'], 'visible')) == 1 and m.props.get((m.widgets['btn_songs'], 'sensitive')) == 1
    def hit(m, name): return stock_target(m, cover_page_tree(m, cover_asset), *scentre(m))[-1] == name
    def np_cap(m):
        np = m.widgets['btn_backtoplayer']
        return (m.props.get((np, 'style:normal:icon')), m.props.get((np, 'style:over:icon')), m.props.get((np, 'style:pressed:icon')))
    for a0, what in ((0, 'with the card (two albums)'), (1, 'with one album (no card)')):
        m = artists_machine(); seed(m); m.call(open_, count=5000000); m.call(PSYMS['ar_on_artist'], a0=a0, count=8000000)
        opened = list(m.calls)   # (the touch simulation below clears m.calls)
        expect(songs_shown(m) and not any(c[0] == 'widget_move' and c[1] == m.widgets['btn_songs'] for c in opened),
               f'an artist {what}: Songs is shown, at the asset\'s x 214 (not moved)')
        expect(('widget_resize', m.widgets['label_title'], O['NAV_VIEW_X'] - 58, 22) in opened,
               f'an artist {what}: the title ends before the capsule ({[c for c in opened if c[0] == "widget_resize" and c[1] == m.widgets["label_title"]]})')
        expect(hit(m, 'btn_songs'), f'an artist {what}: a touch on Songs reaches it ({stock_target(m, cover_page_tree(m, cover_asset), *scentre(m))[-1]})')
        right = stock_target(m, cover_page_tree(m, cover_asset), O['NAV_VIEW_X'] + O['NAV_VIEW_W'] + 2, 25)[-1]
        expect(right == 'btn_backtoplayer', f'an artist {what}: right of Songs is Now Playing ({right})')
        expect(np_cap(m) == ('ah_nav_play', 'ah_nav_play', 'ah_nav_play_down'), f'an artist {what}: Now Playing is the capsule\'s right cap ({np_cap(m)})')
    m = artists_machine(); seed(m); m.call(open_, count=5000000); m.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    m.click('btn_songs', count=900000000)
    calls = [c for c in m.calls if c[0] in ('loadAlbumList', 'loadAlbumdetailList', 'window_open', 'navigator_to_with_context') and c[1] != 'm1plus_cover']
    expect([c[:2] for c in calls][:3] == [('loadAlbumList', O['CLASS_ARTISTS']), ('loadAlbumdetailList', O['CLASS_ARTIST_ALBUMS']), ('window_open', 'm1plus_songs')]
           and not any(c[0] == 'navigator_to_with_context' and c[1] == 'albuminfo_page' for c in calls), f'a tap opens our Songs page on the artist ({calls})')
    m.call(PSYMS['on_destroy'], count=2000000)
    m = artists_machine(); seed(m); m.windows['m1plus_songs'] = 0; m.call(open_, count=5000000); m.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    m.click('btn_songs', count=900000000)
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ARTIST_ALBUMS'], 3) in m.calls, 'a page that will not open falls back to the stock album page on the All songs row')
    m = artists_machine(); seed(m); m.windows['m1plus_songs'] = 0; m.call(open_, count=5000000); m.call(PSYMS['ar_on_artist'], a0=1, count=8000000)
    m.click('btn_songs', count=900000000)
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ARTIST_ALBUMS'], 1) in m.calls, 'and also for an artist whose card was dropped (one album: the All songs row is the second)')
    m = artists_machine(); seed(m); m.call(open_, count=5000000); m.call(PSYMS['ar_on_artist'], a0=2, count=8000000)
    m.click('btn_songs', count=2000000)
    expect(not songs_shown(m) and np_cap(m)[0] != 'ah_nav_play' and not [c for c in m.calls if c[0] in ('loadAlbumdetailList', 'navigator_to_with_context')],
           'an artist with no albums (No albums): no Songs button, Now Playing keeps its disc, a stray click opens nothing')
    mm = cover_machine(albums=3); seed(mm); mm.call(PSYMS['coverflow_open'], count=5000000)
    mm.click('btn_songs', count=2000000)
    expect(not songs_shown(mm) and np_cap(mm)[0] != 'ah_nav_play' and not any(c[0] == 'widget_resize' and c[1] == mm.widgets['label_title'] for c in mm.calls)
           and not [c for c in mm.calls if c[0] in ('loadAlbumdetailList', 'loadAlbumList', 'navigator_to_with_context')] and not hit(mm, 'btn_songs'),
           'the main Cover Flow keeps Songs hidden, Now Playing the disc and the title full width; a stray click does nothing')
    mp = artists_machine(); seed(mp)
    for f in [f for f in mp.present if f.startswith('/mnt/mmc/.m1plus/covers/')]: mp.present.discard(f)
    mp.call(open_, count=5000000); mp.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    mp.click('btn_songs', count=2000000)
    expect(not songs_shown(mp) and np_cap(mp)[0] != 'ah_nav_play' and not [c for c in mp.calls if c[0] in ('loadAlbumdetailList', 'navigator_to_with_context')],
           'while preparing the Songs button is hidden, Now Playing the disc, and a stray click does nothing')

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


def index_tests(expect):
    """An artist's albums take the cache key of the library's album of the same name (ASCII case folded, the FIRST
    library row of a name), through an index when there are IDX_MIN or more of them and a scan below that. Both give the
    same keys; the index does far less work on a big library."""
    ascii_fold = lambda s: ''.join(c.lower() if c.isascii() else c for c in s)
    def keys(m, n):   # cf.keys: the word of cf that holds the n-key calloc (no struct offset assumed)
        made = {c[2] for c in m.calls if c[0] == 'calloc' and c[1] == 4 * n and c[2]}
        at = [m.word(PSYMS['cf'] + o) for o in range(0, 512, 4) if m.word(PSYMS['cf'] + o) in made]
        return [m.word(at[0] + 4 * i) for i in range(n)] if len(at) == 1 else None
    def build(lib_n, k):
        m = artists_machine(['Miles Davis'])
        library, lib = [], []
        names = [f'Album {i}' for i in range(lib_n)]
        names[lib_n // 2] = 'ALBUM 7'                      # a later duplicate in another case: the first row (7) wins
        names[lib_n - 2] = 'album 3'                       # ... and again, at the end
        names[10] = 'Éclat'                                # not ASCII: no folding
        for i, nm in enumerate(names):
            artist = f'Lib {i}'
            library.append(m.record(album=nm, artist=artist, path=f'/mnt/mmc/L/{i}/1.flac', rid=i + 1)); lib.append((artist, nm))
        wants = ['album 7', 'ALBUM 3', 'éclat', 'Éclat', 'No such album', 'aLbUm 12'] + [f'Album {lib_n - 1 - j}' for j in range(k)]
        wants = wants[:k] if k < len(wants) else wants
        arts = [m.record(album=w, artist='Miles Davis', path=f'/mnt/mmc/M/{j}/1.flac', rid=500 + j) for j, w in enumerate(wants)]
        m.artist_albums['Miles Davis'] = arts
        m.class_lists[O['CLASS_ALBUMS']] = library; m.showlist = library
        exp = []
        for w in wants:
            row = next((i for i, (_, nm) in enumerate(lib) if ascii_fold(nm) == ascii_fold(w)), None)
            a, nm = lib[row] if row is not None else ('Miles Davis', w)
            exp.append(fnv(fnv(O['FNV_SEED'], a), nm) or 1)
        return m, exp + [0]                                # the All albums card: key 0
    for lib_n, k in ((1000, 16), (1000, 30), (1000, 200), (40, 30)):
        m, exp = build(lib_n, k)
        m.call(PSYMS['artists_open'], count=5000000)
        m.call(PSYMS['ar_on_artist'], a0=0, count=900000000)
        got = keys(m, len(exp))
        expect(got == exp, f'{k} artist albums over {lib_n} library albums: every key is the first case-insensitive match\'s (or its own)')
        INDEX_COST[(lib_n, k)] = m.icount
        idx = [c for c in m.calls if c[0] == 'calloc' and c[1] == 4 * 2048]
        frees = [c[1] for c in m.calls if c[0] == 'free']
        expect(bool(idx) == (k >= 24 and lib_n == 1000) and all(c[2] in frees for c in idx), f'{k} albums: the index is built only from 24 albums up, and freed')
    # no memory for the index: the scan gives the same keys
    m, exp = build(1000, 200)
    m.calloc_fail_size = 4 * 2048
    m.call(PSYMS['artists_open'], count=5000000)
    m.call(PSYMS['ar_on_artist'], a0=0, count=900000000)
    got = keys(m, len(exp))
    expect(got == exp and not [c for c in m.calls if c[0] == 'calloc' and c[1] == 4 * 2048 and c[2]], 'a refused index: the scan finds the same keys')
    expect(INDEX_COST[(1000, 200)] < 1000000 and m.icount > 8000000,
           f'200 albums over 1000: {INDEX_COST[(1000, 200)]:,} payload instructions with the index, {m.icount:,} with the scan (10.2 M before the index existed)')


INDEX_COST = {}


def genre_composer_tests(ctx):
    """Genres and Composers on the Artists page (ACT_ARTISTS with the stock Home tile as its argument): the rows, the stock class queried, the stock order, the title
    of the menu row, the Artist / Album Artist switch gone (hidden and insensitive, a stray click does nothing), a genre's tap on our Songs page, a composer's in Cover
    Flow (loadAlbumList(0xf005): class 0xff02), and the fallbacks to the tile's stock page."""
    expect, page, P = ctx.expect, ctx.page, pod_pages
    import awtk_ui
    on_row, rows0, open_ = PSYMS['on_row'], PSYMS['pod_rows_0'], PSYMS['artists_open']
    asset = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1plus_artists.bin')
    CI = pod.DATA['CLASSINFO'][0]
    row = {label: next(i for i, r in enumerate(page.rows) if r.label == label) for label in ('Artists', 'Genres', 'Composers')}
    expect([(page.rows[row[k]].action, page.rows[row[k]].arg) for k in row] ==
           [(P.ACT_ARTISTS, 0), (P.ACT_ARTISTS, P.HOME_GENRE), (P.ACT_ARTISTS, P.HOME_COMPOSER)]
           and O['HOME_GENRE'] == P.HOME_GENRE and O['HOME_COMPOSER'] == P.HOME_COMPOSER
           and (O['CLASS_GENRES'], O['CLASS_COMPOSERS'], O['CLASS_COMPOSER_ALBUMS'], O['CLASS_GENRE_SONGS']) == (0xf006, 0xf005, 0xff02, 0xff09),
           'the Artists, Genres and Composers rows are ACT_ARTISTS with the tile as the argument; offsets.inc has the tiles and classes of docs/modules/addresses.md')
    expect(pod_i18n.key_for('Genres') == 'Genres' and pod_i18n.key_for('Composers') == 'Composers', 'the titles\' keys are the menu rows\'')

    # the page on each class: the stock query, the stock order (no sort), the title, no switch
    for label, home, cls, names in (('Genres', P.HOME_GENRE, 0xf006, ('Rock', 'jazz', '周', 'Unknown Genre')),
                                    ('Composers', P.HOME_COMPOSER, 0xf005, ('Mozart', 'Bach', 'The Beatles', 'Unknown Composer'))):
        m = artists_machine(genres=names if cls == 0xf006 else (), composers=names if cls == 0xf005 else ())
        r = m.call(on_row, a0=rows0 + 12 * row[label], count=20000000)
        calls = list(m.calls)
        title, tog = m.widgets['label_title'], m.widgets['btn_artisttype']
        expect(('window_open', 'm1plus_artists') in calls and [c[1] for c in calls if c[0] == 'loadLocalClassList'] == [cls] and 'stock_resume' not in m.names(),
               f'{label}: our Artists page lists class {cls:#x}')
        expect(shown(m) == list(names),
               f'{label}: the rows are the stock list in its own order, unsorted ({shown(m)})')
        expect(('widget_set_text_utf8', title, label) in calls and not any(c[0] == 'widget_set_text_utf8' and c[1] == title and c[2] in ('Artists', 'Album Artists') for c in calls),
               f'{label}: the title is the menu row\'s text')
        expect(m.props.get((tog, 'visible')) == 0 and m.props.get((tog, 'sensitive')) == 0 and (tog, 'style:normal:icon') not in m.props,
               f'{label}: the Artist / Album Artist switch is hidden and insensitive, its glyph left alone')
        np = m.widgets['btn_backtoplayer']
        expect(m.props.get((np, 'style:normal:icon')) == m.props.get((np, 'style:over:icon')) == 'ah_nav_np' and m.props.get((np, 'style:pressed:icon')) == 'ah_nav_np_down',
               f'{label}: with the switch gone Now Playing is the glass disc (ah_nav_np), not the right cap of a capsule that is not there')
        root = asset_tree(asset)
        node(root, 'btn_artisttype').flags &= ~F_SENSITIVE
        if m.props.get((m.widgets['label_status'], 'sensitive')) == 0: node(root, 'label_status').flags &= ~F_SENSITIVE
        expect(stock_target(m, root, O['NAV_VIEW_X'] + 20, 25)[-1] != 'btn_artisttype', f'{label}: a touch on the switch\'s old slot reaches nothing of it')
        expect(stock_target(m, root, 290, 25)[-1] == 'btn_backtoplayer' and stock_target(m, root, 40, 25)[-1] == 'btn_return', f'{label}: Back and Now Playing are hit')
        at = m.word(pod.DATA['ARTIST_TYPE'][0])
        m.calls = []
        m.call(PSYMS['ar_on_toggle'], count=20000000)
        expect(m.word(pod.DATA['ARTIST_TYPE'][0]) == at and not [c for c in m.calls if c[0] in ('write_int_config', 'loadLocalClassList')],
               f'{label}: a stray click on the switch changes no setting and queries nothing')
        m.call(PSYMS['pod_on_back'], count=200000)
        expect('navigator_back' in m.names(), f'{label}: Back goes back')
        m.call(PSYMS['ar_on_destroy'], count=200000)
        expect('deque_destroy' in m.names(), f'{label}: closing frees the copy')
        # no memory for the page's widgets / window: the tile's stock page
        m = artists_machine(genres=names if cls == 0xf006 else (), composers=names if cls == 0xf005 else ()); m.windows['m1plus_artists'] = 0
        m.call(on_row, a0=rows0 + 12 * row[label], count=2000000)
        expect(('stock_resume', str(home)) in m.calls and 'loadLocalClassList' not in m.names(), f'{label}: a window that will not open leaves the tile\'s stock page')
        m = artists_machine(genres=names if cls == 0xf006 else (), composers=names if cls == 0xf005 else ()); del m.widgets['pod_scrollview']
        m.call(on_row, a0=rows0 + 12 * row[label], count=2000000)
        expect('navigator_back' in m.names() and ('stock_resume', str(home)) in m.calls, f'{label}: an asset that is not ours is left for the tile\'s stock page')
        m = artists_machine(genres=(), composers=()); m.class_lists[cls] = []
        m.call(on_row, a0=rows0 + 12 * row[label], count=2000000)
        expect('list_item_create' not in m.names() and any(c[0] == 'widget_set_text_utf8' and 'Update Local Music' in c[2] for c in m.calls),
               f'{label}: an empty library says so, no rows')

    # Artists itself is as it was: sorted, the switch shown and bound, and the title Artists
    m = artists_machine(); m.call(on_row, a0=rows0 + 12 * row['Artists'], count=20000000)
    tog = m.widgets['btn_artisttype']
    expect(m.props.get((tog, 'visible')) != 0 and m.props.get((tog, 'sensitive')) != 0 and ('widget_set_text_utf8', m.widgets['label_title'], 'Artists') in m.calls
           and [c[1] for c in m.calls if c[0] == 'loadLocalClassList'] == [O['CLASS_ARTISTS']], 'the Artists row: the switch stays, the title is Artists, class 0xf004')
    expect((m.widgets['btn_backtoplayer'], 'style:normal:icon') not in m.props, 'and Now Playing keeps the capsule\'s right cap')

    # a genre's tap: our Songs page (songs_open_genre), the genre's name and the Unknown byte; the stock row tap's own sequence when that window will not open
    names = ('Rock', 'Jazz', 'Unknown Genre')
    for k, (name, unknown) in enumerate(zip(names, (0, 0, 1))):
        m = artists_machine(genres=names); m.call(open_, a0=P.HOME_GENRE, count=20000000)
        m.calls = []
        m.call(PSYMS['ar_on_artist'], a0=k, count=8000000)
        expect(('window_open', 'm1plus_songs') in m.calls and 'loadAlbumList' not in m.names()
               and not any(c == ('window_open', 'm1plus_cover') for c in m.calls), f'a tap on genre {name!r} opens our Songs page, not Cover Flow')
        m = artists_machine(genres=names); m.call(open_, a0=P.HOME_GENRE, count=20000000); m.windows['m1plus_songs'] = 0
        m.calls = []
        m.call(PSYMS['ar_on_artist'], a0=k, count=8000000)
        nav = [c for c in m.calls if c[0] == 'navigator_to_with_context']
        expect(nav and nav[0][:3] == ('navigator_to_with_context', 'allmusic_page', O['CLASS_GENRE_SONGS']) and m.word(CI) == O['CLASS_GENRE_SONGS']
               and m.read_cstr(CI + O['CLASSINFO_GENRE']) == name and m.u.mem_read(CI + O['CLASSINFO_GENRE_UNKNOWN'], 1)[0] == unknown,
               f'songs window will not open: the stock row tap\'s sequence for {name!r} (classinfo[0] 0xff09, the name at +0x30d, byte +0xc = {unknown}, then allmusic_page 0xff09)')

    # a composer's tap: Cover Flow on that composer's albums (loadAlbumList(0xf005, row) = getAlbumByComposer, the All songs row last, class 0xff02)
    comps = ('Mozart', 'Bach', 'Unknown Composer')
    m = artists_machine(composers=comps); m.call(open_, a0=P.HOME_COMPOSER, count=20000000)
    m.calls = []
    m.call(PSYMS['ar_on_artist'], a0=1, count=8000000)   # Bach: two albums and the card
    la = [c for c in m.calls if c[0] == 'loadAlbumList']
    expect(('window_open', 'm1plus_cover') in m.calls and la and la[0][1] == O['CLASS_COMPOSERS'] and la[0][3] == 'Bach' and ('window_open', 'm1plus_songs') not in m.calls,
           f'a composer opens Cover Flow with loadAlbumList(0xf005, that composer) ({la[:1]})')
    expect(('widget_set_text_utf8', m.widgets['label_title'], 'Bach') in m.calls and ('widget_set_text_utf8', m.widgets['label_album'], 'Goldberg Variations') in m.calls,
           'titled with the composer, centred on his first album')
    put_value(m, 2); m.call(PSYMS['on_changed'], count=2000000)
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'All albums') in m.calls and ('widget_set_text_utf8', m.widgets['label_artist'], 'Bach') in m.calls,
           'two albums: the All albums card over the composer')
    m.calls = []
    m.click('btn_songs', count=900000000)
    npw = m.widgets['btn_backtoplayer']
    expect(m.props.get((m.widgets['btn_songs'], 'visible')) != 1 and m.props.get((npw, 'style:normal:icon')) != 'ah_nav_play'
           and not any(c[0] in ('window_open', 'loadAlbumdetailList') or (c[0] == 'navigator_to_with_context' and c[1] == 'albuminfo_page') for c in m.calls),
           'a composer\'s page has no Songs button (it runs the artist queries) and Now Playing keeps its disc, and a stray click on it opens nothing')
    m.tap(O['CF_CX'])
    order = [c[0] for c in m.calls if c[0] in ('loadAlbumList', 'albumcoverinfo_init', 'navigator_to_with_context')][-3:]
    la = [c for c in m.calls if c[0] == 'loadAlbumList']
    expect(order == ['loadAlbumList', 'albumcoverinfo_init', 'navigator_to_with_context'] and la[-1][1] == O['CLASS_COMPOSERS'] and la[-1][3] == 'Bach'
           and ('navigator_to_with_context', 'albuminfo_page', O['CLASS_COMPOSER_ALBUMS'], 2) in m.calls,
           'the card: the composer into the browsing record again, then albuminfo_page with class 0xff02 and the card row')
    cls, rowi, shown_list = m.opened_album
    expect(m.word(m.deques[shown_list][rowi] + O['REC_ID']) == O['ID_ALL_SONGS'] & 0xffffffff, 'that row is the stock All songs row')
    put_value(m, 1); m.call(PSYMS['on_changed'], count=2000000)
    m.tap(O['CF_CX'])
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_COMPOSER_ALBUMS'], 1) in m.calls
           and m.read_cstr(m.word(m.deques[m.opened_album[2]][1] + O['REC_ALBUM'])) == 'Cello Suites', 'a centre album opens as the stock composer page opens it (class 0xff02, its row)')
    m.call(PSYMS['on_destroy'], count=2000000)
    # the artist's own scope is untouched by a composer's (the scope is per open)
    m = artists_machine(composers=comps); m.call(open_, count=20000000); m.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    la = [c for c in m.calls if c[0] == 'loadAlbumList']
    put_value(m, 3); m.call(PSYMS['on_changed'], count=2000000); m.tap(O['CF_CX'])
    expect(la[0][1] == O['CLASS_ARTISTS'] and ('navigator_to_with_context', 'albuminfo_page', O['CLASS_ARTIST_ALBUMS'], 3) in m.calls, 'an artist after a composer: class 0xf004 and 0xff01 again')
    # a composer with one album: no card; the Unknown Composer row: No albums
    m = artists_machine(composers=comps); m.call(open_, a0=P.HOME_COMPOSER, count=20000000)
    m.call(PSYMS['ar_on_artist'], a0=0, count=8000000)
    shown_one = ('widget_set_text_utf8', m.widgets['label_album'], 'Requiem') in m.calls
    put_value(m, 1); m.call(PSYMS['on_changed'], count=2000000)
    expect(shown_one and not any(c[0] == 'widget_set_text_utf8' for c in m.calls), 'a composer with one album gets no card')
    m = artists_machine(composers=comps); m.call(open_, a0=P.HOME_COMPOSER, count=20000000)
    m.call(PSYMS['ar_on_artist'], a0=2, count=8000000)
    expect(any(c[0] == 'widget_set_text_utf8' and c[2] == 'No albums' for c in m.calls), 'a composer without albums says No albums')


def run(ctx):
    artists_tests(ctx.expect, ctx.page, ctx.cover_asset)
    genre_composer_tests(ctx)
    index_tests(ctx.expect)
    sort_tests(ctx.expect)
