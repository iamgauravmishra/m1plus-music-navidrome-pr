"""Albums: the menu row, the grid (layout, visible cells, tiles, scrolling, taps), the title ellipsis, missing cache
files, a large library, the list mode of the same page (rows, covers, two text styles, pressed row, taps), the in-place
mode toggle with its persistence, and hit tests on the page."""
import os, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

SCREEN_Y0 = 30 + 50     # the grid view on the screen: under the 30 px status bar and the 50 px navbar
ALBUMS_FILE, ALBUMS_TMP = '/mnt/data/m1pod-albums', '/mnt/data/m1pod-albums.tmp'
COVER, GAP, MARGIN, COLS = O['GRID_COVER'], O['GRID_GAP'], O['GRID_MARGIN'], O['GRID_COLS']
TGAP, THEIGHT, VIEW_H, TILES = O['GRID_TITLE_GAP'], O['GRID_TITLE_H'], O['GRID_VIEW_H'], O['GRID_TILES']
CELL = COVER + TGAP + THEIGHT
PITCH = CELL + GAP
ART = O['ART_SIZE']
ROW, LART, LAX, LAY = O['LIST_ROW_H'], O['LIST_ART'], O['LIST_ART_X'], O['LIST_ART_Y']
TX, TW, TY, TH, SY, SH = O['LIST_TEXT_X'], O['LIST_TEXT_W'], O['LIST_TITLE_Y'], O['LIST_TITLE_H'], O['LIST_SUB_Y'], O['LIST_SUB_H']


class Images(dict):
    """widget_load_image's pictures: the stock placeholder, and for any cache file a flat side x side cover
    whose colour depends on the album number (made when asked, so a library of thousands costs nothing). The
    pictures are small: the box filter's work grows with them, and so does the emulation's time."""
    def get(self, url, default=None):
        if url in self: return dict.get(self, url)
        if url.startswith('file://') and url[7:] in self.owner.cache_index:
            i, side = self.owner.cache_index[url[7:]], self.owner.side
            return side, side, bytes((i * 7 % 256, i * 13 % 256, i * 29 % 256, 255)) * (side * side)
        return default


def colour(i):
    return 0xff000000 | (i * 7 % 256) | (i * 13 % 256) << 8 | (i * 29 % 256) << 16


def albums_machine(n=30, cached=True, missing=(), empty=(), title=lambda i: f'Album {i}', side=24, sort='album'):
    """A machine with the grid page's widgets, n albums in the stock list and, unless cached is False or the album
    is in missing / empty (the zero-length "no art" marker), a cache file with a cover. sort: the order setting
    (the machines default to the stock order, 'album', which the layout tests index by album number; 'artist' is the
    setting's own default, tested in the sort tests)."""
    m = Machine()
    if sort == 'album': m.fs[CFSORT_FILE] = b'0\n'
    m.load_image = 0
    for w in ('btn_return', 'btn_backtoplayer', 'btn_albumview', 'view_grid', 'label_status', 'label_row_title', 'label_row_sub'): m.widget(w)
    win = m.alloc(0x80)                      # the window: widget_to_local (stock's own code) walks these words
    m.setword(win + 4, 30)                   # y under the status bar
    view = m.widgets['view_grid']
    m.setword(view + 4, 50); m.setword(view + 0x44, win)
    m.showlist = [m.record(album=title(i), artist=f'Artist {i}', path=f'/mnt/mmc/m/{i}/1.flac', rid=i + 1) for i in range(n)]
    m.cache_index, m.side = {}, side
    m.images = Images(); m.images.owner = m
    m.images['p_default'] = (24, 24, bytes((0x40, 0x40, 0x40, 255)) * (24 * 24))
    for i in range(n):
        p = art_file(fnv(fnv(O['FNV_SEED'], f'Artist {i}'), title(i)) or 1)
        if cached and i not in missing:
            m.present.add(p); m.files[p] = 0 if i in empty else 4096
            if i not in empty: m.cache_index[p] = i
    return m


def page_mode(m):
    """1 if the open page is in list mode (its toggle shows the grid glyph), else 0."""
    return 1 if m.props.get((m.widgets['btn_albumview'], 'style:normal:icon')) == 'pod_nav_grid' else 0


def open_grid(m):
    m.call(PSYMS['albums_open'], count=20000000)
    return list(m.calls)


def paint(m):
    """One EVT_AFTER_PAINT on the grid view: (blits, texts) of that frame."""
    ev = m.alloc(0x40); m.u.mem_write(ev, bytes(0x40)); m.setword(ev + O['EVENT_PAINT_CANVAS'], 0x22220000)
    m.blits.clear(); m.texts.clear(); m.measures.clear(); m.fills.clear(); m.text_styles.clear()
    m.call(PSYMS['al_on_paint'], a0=0, a1=ev, count=400000000)
    return list(m.blits), list(m.texts)


def settle(m, limit=60):
    """Paint, and fire the 16 ms reload timer while one is armed, until the view is complete; the last frame."""
    for _ in range(limit):
        frame = paint(m)
        if not any(c[0] == 'timer_add' for c in m.calls): return frame
        m.call(PSYMS['al_on_more'], count=1000000)
    raise AssertionError('the grid never finished loading')


def reference(scroll, n):
    """Independent model of what a frame at `scroll` shows: [(album, (src, dst) of the cover or None, title rect or
    None)] for the cells that touch the view. Brute force over every album unless n is large (then a window of rows)."""
    out = []
    first = max(0, (scroll - GAP - CELL) // PITCH - 1) * COLS
    for a in range(first, min(n, first + 40) if n > 200 else n):
        x, top = MARGIN + (a % COLS) * (COVER + GAP), GAP + (a // COLS) * PITCH - scroll
        if top >= VIEW_H or top + CELL <= 0: continue
        cut_top, cut_bottom = max(0, -top), min(COVER, VIEW_H - top)
        cover = ((0, cut_top, COVER, cut_bottom - cut_top), (x, top + cut_top, COVER, cut_bottom - cut_top)) if cut_bottom > cut_top else None
        ty = top + COVER + TGAP
        title = (x, ty, COVER, THEIGHT) if 0 <= ty and ty + THEIGHT <= VIEW_H else None
        out.append((a, cover, title))
    return out


def dsts(blits): return sorted(b[2] for b in blits)
def want_dsts(ref): return sorted(c[1][1] for c in ref if c[1])


def gesture(m, events):
    """Pointer events [(kind, x, local y, ms)] delivered one after the other; every call they made."""
    calls = []
    for kind, x, y, t in events:
        m.touch(kind, x, SCREEN_Y0 + y, t, fn='al_on_pointer'); calls += m.calls
    m.calls = calls
    return calls


def drag_to(m, target, current, t0=0):
    """Scroll from `current` to `target` px with a slow drag (no fling): down, one move, a late release."""
    y = 300
    return gesture(m, [('down', 100, y, t0), ('move', 100, y + current - target, t0 + 300), ('up', 100, y + current - target, t0 + 700)])


def tap_at(m, x, y, t0=1000):
    return gesture(m, [('down', x, y, t0), ('up', x, y, t0 + 80)])


def run(ctx):
    expect, page = ctx.expect, ctx.page
    row = next(i for i, r in enumerate(page.rows) if r.label == 'Albums')
    expect(page.rows[row].action == pod_pages.ACT_ALBUMS, 'the menu\'s Albums row opens our page (ACT_ALBUMS)')
    on_row, rows0 = PSYMS['on_row'], PSYMS['pod_rows_0']

    # 1. Layout: three 92 px covers 12 px apart, centred; the view is the 400 px under the navbar; the ring holds
    #    every cell a frame can touch.
    expect(COLS * COVER + (COLS - 1) * GAP + 2 * MARGIN == pod_ui.SCREEN_W, f'{COLS} covers + gutters + margins fill the 320 px width')
    expect(VIEW_H == pod_ui.GRID_VIEW_H == pod_ui.CLIENT_H - pod_ui.NAVBAR_H, 'the grid view is the 400 px under the navbar')
    expect(TILES >= COLS * ((VIEW_H + CELL) // PITCH + 2), f'{TILES} tiles hold the {COLS * ((VIEW_H + CELL) // PITCH + 2)} cells a frame can touch')
    expect(THEIGHT >= pod_ui.GRID_TITLE_PX + 4 and (O['NAV_VIEW_X'], O['NAV_VIEW_W']) == (pod_ui.NAV_VIEW_X, pod_ui.NAV_VIEW_W),
           'the title line fits its font; the toggle geometry is shared with the asset')
    asset = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1pod_albums.bin')
    tree = awtk_ui.parse(open(asset, 'rb').read())
    grid = tree.find('view_grid')
    expect(grid is not None and (grid.x, grid.y, grid.w, grid.h) == (0, pod_ui.NAVBAR_H, 320, VIEW_H) and grid.type == 'view',
           'the asset has one 320x400 view_grid under the navbar')
    expect(all(grid.get(f'style:normal:{k}') == v for k, v in (('text_color', '#FFFFFF'), ('font_size', '16'),
                                                                 ('text_align_h', 'left'), ('bg_color', '#000000'))),
           'its style is the 16 px white title text on black (what widget_prepare_text_style reads)')
    expect(not [w for w in tree.walk() if w.type in ('list_view', 'scroll_view', 'list_item', 'image', 'slide_menu')],
           'no widget per album, no list: the page is a navbar, one view and a status label')
    btn = tree.find('btn_albumview')
    expect(btn is not None and (btn.x, btn.w, btn.h) == (O['NAV_VIEW_X'], O['NAV_VIEW_W'], O['NAV_H'])
           and btn.get('style:normal:icon') == 'pod_nav_list' and btn.get('style:pressed:icon') == 'pod_nav_list_down',
           'the navbar button shows the list glyph (the view a tap switches to)')
    nb = tree.find('btn_backtoplayer')
    expect(O['NAV_VIEW_X'] + O['NAV_VIEW_W'] == nb.x, 'the toggle sits flush left of Now Playing, no gap')
    lbl = tree.find('label_title')
    expect(lbl.x + lbl.w == O['NAV_VIEW_X'], 'and the title ends where it begins')
    #     list mode: the two hidden text-style labels, the geometry the rows share with the library rows
    for nm, px, col in (('label_row_title', 21, '#FFFFFF'), ('label_row_sub', 18, '#AAAAAA')):
        w = tree.find(nm)
        expect(w is not None and w.type == 'label' and w.get('visible') == 'false' and w.get('sensitive') == 'false'
               and w.get('style:normal:font_size') == str(px) and w.get('style:normal:text_color') == col and w.get('style:normal:text_align_h') == 'left',
               f'{nm}: a hidden, insensitive label whose style is {px} px {col} (what the list rows are drawn with)')
    expect(ROW == 64 and LAX + LART + LAX <= 64 and TX + TW + 12 == 320 and TY + TH <= SY and SY + SH <= ROW - 1 and ROW == O['LIST_ROW_H'],
           'list rows: 64 px like the library rows, 52 px cover at (4,4), text from 60 to a 12 px right margin, two lines and a hairline fit')
    expect(O['LIST_HAIR'] == 0xff222222 and O['LIST_PRESS'] == 0xff333333, 'hairline #222222, pressed #333333 (the other lists\' colours)')
    expect(not [w for w in tree.walk() if w.name in ('btn_stocklist',)] and O.get('NAV_LIST_X') is None, 'no trace of the stock-list toggle')
    imgs = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/images/xx')
    expect(all(os.path.isfile(os.path.join(imgs, f'pod_nav_{k}{s}.png')) for k in ('grid', 'list') for s in ('', '_down')),
           'the four toggle glyph images are in the tree')

    # 2. The menu row: the persisted mode, the default constant when there is none (or it is garbage); "0" is the list
    #    mode of the same page, "1" the grid; never a second window or the stock list.
    m = albums_machine(3)
    m.call(on_row, a0=rows0 + 12 * row, count=20000000)
    expect(('window_open', 'm1pod_albums') in m.calls and 'stock_resume' not in m.names() and page_mode(m) == (0 if O['ALBUMS_DEFAULT_GRID'] else 1),
           'with no setting the Albums row opens our page in the default mode')
    for data, want_list in ((b'1\n', 0), (b'0\n', 1), (b'x', 1 - O['ALBUMS_DEFAULT_GRID']), (b'', 1 - O['ALBUMS_DEFAULT_GRID'])):
        m = albums_machine(3); m.fs[ALBUMS_FILE] = data
        calls = open_grid(m)
        expect(('window_open', 'm1pod_albums') in calls and 'stock_resume' not in m.names() and page_mode(m) == want_list,
               f'setting {data!r}: the Albums row opens our page in {"list" if want_list else "grid"} mode')
    #     a page that cannot open falls back to the stock Albums list through the Home dispatcher (Albums = id 5)
    m = albums_machine(3); m.window = 0
    open_grid(m)
    expect(('stock_resume', '5') in m.calls, 'if the window will not open the Albums row opens the stock list (Home id 5)')
    m = albums_machine(3); del m.widgets['label_row_sub']
    open_grid(m)
    expect('navigator_back' in m.names() and 'stock_resume' not in m.names(), 'an asset without the list styles leaves the page and does not open the stock list over it')

    # 3. Opening the grid: the page's widgets bound, the album list copied, the placeholder made, nothing per album,
    #    no cache build.
    m = albums_machine(30)
    calls = open_grid(m)
    names = [c[0] for c in calls]
    expect(('window_open', 'm1pod_albums') in calls and names.count('widget_on') == 3 + 1 + 4 + 1,
           f'the window, Back, Now Playing, the toggle, four pointer events and the paint are bound ({names.count("widget_on")})')
    expect(('loadLocalClassList', O['CLASS_ALBUMS']) in calls and ('deque_assign', 30) in calls, 'the stock album list is copied')
    expect(not any(n in names for n in ('image_create', 'list_item_create', 'label_create', 'hscroll_label_create', 'widget_factory_create_widget')),
           'no widget is created per album')
    expect(not any(n in names for n in ('pthread_create', 'toolsGetAlbumCover', 'toolsGetExternCover', 'mkdir')),
           'the grid builds no cache')
    expect(len(m.bitmaps) == 1 and ('widget_load_image', 'p_default') in calls, 'the placeholder disc is the only bitmap before the first frame')
    expect(('widget_set_visible', m.widgets['label_status'], 0) in calls, 'the status line starts hidden')

    # 4. The first frame: the cells that touch the view, each cover blitted 1:1, titles under them; decoding is
    #    paced (two covers a frame) and the rest show the placeholder until the reload timer fills them in.
    blits, texts = paint(m)
    ref = reference(0, 30)
    expect(len(ref) == 9 and [a for a, *_ in ref] == list(range(9)), 'three rows of three are in view at the top')
    expect(dsts(blits) == want_dsts(ref) and all(b[1] == (0, 0, COVER, COVER) for b in blits),
           f'one blit per visible cell, at its place, source = the whole tile ({dsts(blits)[:3]})')
    expect(sorted(t[1] for t in texts) == sorted(c[2] for c in ref), 'one title per visible cell, 92x22 under its cover')
    expect([t[0] for t in sorted(texts, key=lambda t: (t[1][1], t[1][0]))] == [f'Album {i}' for i in range(9)], 'the titles are the album names')
    expect(len([c for c in m.calls if c[0] == 'widget_load_image']) == 2, 'a frame decodes at most two covers')
    expect(any(c[0] == 'timer_add' and c[1] == PSYMS['al_on_more'] and c[2] == 16 for c in m.calls), 'and arms a 16 ms timer for the rest')
    expect(('widget_prepare_text_style', m.widgets['view_grid']) in m.calls, 'the text style is the view\'s own')
    m.call(PSYMS['al_on_more'], count=1000000)      # the timer fires
    expect(('widget_invalidate_force', m.widgets['view_grid']) in m.calls, 'and redraws the view')
    blits, texts = settle(m)
    expect(len(blits) == 9 and len(m.bitmaps) == 1 + 9, f'every visible cover is a tile of its own once loaded ({len(m.bitmaps)} bitmaps)')
    first = m.blits[0][0]
    data, bw, bh = m.bitmaps[first]
    expect((bw, bh) == (COVER, COVER) and set(struct.unpack(f'<{bw * bh}I', bytes(m.u.mem_read(data, bw * bh * 4)))) == {colour(0)},
           f'album 0\'s tile is its cache picture reduced to {COVER}x{COVER}')
    expect(struct.unpack('<H', m.u.mem_read(first + O['BITMAP_FLAGS'], 2))[0] & 1, 'tiles are flagged opaque (a plain blit)')
    paint(m); steady = m.icount
    expect('widget_load_image' not in m.names() and 'bitmap_create_ex' not in m.names() and not m.measures,
           'a steady frame decodes, allocates and measures nothing')
    print(f'  grid frame: {steady:,} payload instructions steady (9 cells), {TILES} tiles of {COVER}x{COVER}')
    # a real 168 px cache file (left half red, right half blue): the box filter's reduction, edge to edge
    m = albums_machine(1)
    url = 'file://' + next(iter(m.cache_index))
    half = bytes((255, 0, 0, 255)) * (ART // 2) + bytes((0, 0, 255, 255)) * (ART // 2)
    m.images[url] = (ART, ART, half * ART)
    open_grid(m); settle(m)
    data = m.bitmaps[m.blits[0][0]][0]
    row0 = struct.unpack(f'<{COVER}I', bytes(m.u.mem_read(data + 40 * COVER * 4, COVER * 4)))
    expect(set(row0[:COVER // 2]) == {0xff0000ff} and set(row0[COVER // 2:]) == {0xffff0000},
           f'a {ART} px cache picture reduces to {COVER} px with its halves intact')
    print(f'  one {ART}->{COVER} tile: {m.icount:,} payload instructions')

    # 5. Scrolling: a drag moves the content with the finger and clamps at both ends; the frame at the new offset is the
    #    reference model (partial rows cut by hand to the view, a title only when it fits). No art: only geometry here.
    n = 15      # five rows
    m = albums_machine(n, cached=False)
    open_grid(m); settle(m)
    expect(not any(c[0] == 'widget_invalidate_force' for c in m.calls), 'painting invalidates nothing once complete')
    calls = drag_to(m, 100, 0)
    expect(any(c[0] == 'widget_invalidate_force' and c[1] == m.widgets['view_grid'] for c in calls), 'a drag redraws the view')
    blits, texts = paint(m)
    ref = reference(100, n)
    expect(dsts(blits) == want_dsts(ref), 'after scrolling 100 px: the cells and the cut first row')
    expect(sorted(t[1] for t in texts) == sorted(c[2] for c in ref if c[2]), 'after scrolling 100 px: the titles that fit the view')
    top_row = [b for b in blits if b[2][1] == 0][0]
    expect(top_row[1] == (0, 88, COVER, 4) and top_row[2] == (MARGIN, 0, COVER, 4), f'the first row is cut to its last 4 px ({top_row[1]} -> {top_row[2]})')
    mx = GAP + ((n + COLS - 1) // COLS) * PITCH - VIEW_H
    drag_to(m, 100000, 100, 2000)
    blits, texts = paint(m)
    expect(dsts(blits) == want_dsts(reference(mx, n)), f'dragging far past the end stops at {mx} px')
    expect(max(b[2][1] + b[2][3] for b in blits) + THEIGHT + TGAP + GAP == VIEW_H, f'the last row ends {GAP} px above the bottom')
    drag_to(m, -5000, mx, 4000)
    blits, texts = paint(m)
    expect(dsts(blits) == want_dsts(reference(0, n)), 'dragging past the start stops at 0')
    m2 = albums_machine(5, cached=False); open_grid(m2)
    drag_to(m2, 300, 0)
    blits, _ = paint(m2)
    expect(dsts(blits) == want_dsts(reference(0, 5)) and len(blits) == 5, 'five albums (two rows) cannot scroll')

    # 6. Fling: a quick drag keeps coasting on the 16 ms timer, decaying, and stops by itself or at an end.
    flick = lambda dy, t0=1000: [('down', 100, 350, t0), ('move', 100, 350 + dy // 2, t0 + 16), ('move', 100, 350 + dy, t0 + 32), ('up', 100, 350 + dy, t0 + 40)]
    m = albums_machine(300, cached=False); open_grid(m)
    calls = gesture(m, flick(-80))
    expect(any(c[0] == 'timer_add' and c[1] == PSYMS['al_on_fling'] for c in calls), 'a quick release arms the fling timer')
    ticks = 0
    while ticks < 400:
        m.call(PSYMS['al_on_fling'], count=2000000); ticks += 1
        if not any(c[0] == 'timer_add' and c[1] == PSYMS['al_on_fling'] for c in m.calls): break
    expect(8 < ticks < 400, f'the fling decays and stops by itself ({ticks} ticks)')
    m = albums_machine(300, cached=False); open_grid(m)
    gesture(m, flick(80))
    m.call(PSYMS['al_on_fling'], count=2000000)
    expect(not any(c[0] == 'timer_add' for c in m.calls), 'a fling into the top stops there')
    m = albums_machine(300, cached=False); open_grid(m)
    gesture(m, flick(-80))
    calls = gesture(m, [('down', 100, 350, 2000)])
    expect(('timer_remove', 0x777) in calls, 'a new touch stops the fling')
    calls = gesture(m, [('abort', 100, 350, 2100)])
    expect(any(c[0] == 'widget_ungrab' for c in calls), 'an aborted gesture releases the grab')
    expect(not any(c[0] == 'timer_add' for c in gesture(m, [('down', 100, 350, 3000), ('move', 100, 340, 3300), ('up', 100, 340, 3700)])),
           'a slow release (over 200 ms) does not fling')

    # 7. Taps: a cell (cover or title) opens the stock album page for its row exactly as Cover Flow does; gaps, margins,
    #    the empty tail of the last row and a tap after a drag open nothing; the mapping follows the scroll.
    n = 11      # four rows, the last with two albums
    m = albums_machine(n, cached=False)
    open_grid(m); settle(m)
    def cell_xy(a, scroll=0, dy=10):
        return MARGIN + (a % COLS) * (COVER + GAP) + 10, GAP + (a // COLS) * PITCH - scroll + dy
    opened = lambda calls: [c for c in calls if c[0] == 'navigator_to_with_context']
    calls = tap_at(m, *cell_xy(4))
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ALBUMS'], 4) in calls, 'a tap on album 4\'s cover opens albuminfo_page with 0xf003 | 4 << 16')
    seq = [c[0] for c in calls if c[0] in ('loadAlbumList', 'albumcoverinfo_init', 'batchadd_albumcover_task', 'navigator_to_with_context')]
    expect(seq == ['loadAlbumList', 'albumcoverinfo_init', 'batchadd_albumcover_task', 'navigator_to_with_context']
           and ('batchadd_albumcover_task', 0, 0) in calls, f'the open sequence includes the cover thread release ({seq})')
    expect(m.deques[m.opened_album[2]] == m.showlist and m.opened_album[1] == 4, 'the page reads its row from the stock list')
    calls = tap_at(m, *cell_xy(7, dy=COVER + TGAP + 5))
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ALBUMS'], 7) in calls, 'a tap on a title opens its album too')
    for what, (x, y) in {'the gap between columns': (MARGIN + COVER + 4, 20), 'the left margin': (4, 20), 'the right margin': (316, 20),
                         'the gap between rows': (30, GAP + CELL + 4), 'above the first row': (30, 5),
                         'the empty bottom of the view': (30, VIEW_H - 3)}.items():
        expect(not opened(tap_at(m, x, y)), f'a tap on {what} opens nothing')
    mx = GAP + 4 * PITCH - VIEW_H
    drag_to(m, 100000, 0, 5000); settle(m)
    for a, want in ((10, True), (9, True), (11, False), (2, False)):
        x, y = cell_xy(a, mx)
        got = opened(tap_at(m, x, y))
        expect(bool(got) == want and (not want or got[0][3] == a),
               f'scrolled to the end, album {a}: ' + ('opens' if want else 'nothing' + (' (the empty cell of the last row)' if a == 11 else ' (scrolled out above)')))
    expect(not opened(gesture(m, [('down', 100, 200, 9000), ('move', 100, 150, 9300), ('up', 100, 150, 9700)])), 'releasing after a drag is not a tap')
    x, y = cell_xy(10, mx)
    expect(opened(gesture(m, [('down', x, y, 9800), ('move', x, y + 5, 9850), ('up', x, y + 5, 9900)])), 'a few px of wobble is still a tap')
    # the screen offset does not matter (widget_to_local), and a stale list is queried again
    m = albums_machine(n, cached=False); open_grid(m)
    m.setword(m.word(m.widgets['view_grid'] + 0x44) + 4, 30 + 17)
    x, y = cell_xy(4)
    m.tap(x, SCREEN_Y0 + 17 + y, fn='al_on_pointer')
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ALBUMS'], 4) in m.calls, 'taps are converted with widget_to_local (the window\'s position does not matter)')
    m.setword(pod.DATA['PDEQ_SHOWLIST'][0], m.new_deque([m.record(name='other.flac')]))
    x, y = cell_xy(2); m.tap(x, SCREEN_Y0 + 17 + y, fn='al_on_pointer')
    expect(m.deques[m.opened_album[2]] == m.showlist, 'the stock queries run again on every open')

    # 7b. Gestures with sparse or sideways events (audit): the release is a position, both axes count, and the press that
    #     stopped a coasting fling is not a tap.
    def mode_machine(mode):
        m = albums_machine(300, cached=False)
        if mode == 'list': m.fs[ALBUMS_FILE] = b'0\n'
        open_grid(m)
        return m
    opened = lambda calls: [c for c in calls if c[0] == 'navigator_to_with_context']
    for mode in ('grid', 'list'):
        xa = MARGIN + 10 if mode == 'grid' else 40
        m = mode_machine(mode)
        expect(not opened(gesture(m, [('down', xa, 300, 1000), ('up', xa, 50, 1080)])),
               f'{mode}: down and up 250 px apart with no move between is a scroll, not a tap')
        m = mode_machine(mode)
        expect(not opened(gesture(m, [('down', xa, 50, 1000), ('move', 262, 50, 1040), ('up', 262, 50, 1080)])),
               f'{mode}: a horizontal swipe from one cell/row to another opens nothing')
        expect(not opened(gesture(m, [('down', xa, 50, 2000), ('up', 262, 52, 2080)])),
               f'{mode}: a horizontal release with no move opens nothing either')
        m = mode_machine(mode)       # the release carries the final 160 px of the travel: the same place as a drag of 200 px
        gesture(m, [('down', 100, 300, 3000), ('move', 100, 260, 3100), ('up', 100, 100, 3800)])
        got = dsts(paint(m)[0])
        m2 = mode_machine(mode); drag_to(m2, 200, 0)
        expect(got and got == dsts(paint(m2)[0]), f'{mode}: the release applies its final position (the full 200 px, not 40)')
        m = mode_machine(mode)       # a press that stops a fling is not a tap; the next one is
        gesture(m, [('down', 100, 350, 4000), ('move', 100, 310, 4016), ('move', 100, 270, 4032), ('up', 100, 270, 4040)])
        expect(any(c[0] == 'timer_add' and c[1] == PSYMS['al_on_fling'] for c in m.calls), f'{mode}: the flick coasts')
        calls = gesture(m, [('down', xa, 100, 4100), ('up', xa, 100, 4180)])
        expect(not opened(calls) and ('timer_remove', 0x777) in calls, f'{mode}: a touch that stops the fling opens nothing on release')
        expect(len(opened(gesture(m, [('down', xa, 100, 5000), ('up', xa, 100, 5080)]))) == 1, f'{mode}: the next plain tap opens the album again')

    # 8. Titles: one line, cut with an ellipsis to the cell width by the canvas' own measure; what fits is untouched.
    longs = {0: 'Short', 1: 'Twelve chars', 2: 'A very long album title that cannot fit', 3: 'ABCDEFGHIJK', 4: 'ABCDEFGHIJKL',
             5: '日本語のアルバム名前', 6: '日本語のア'}
    m = albums_machine(7, cached=False, title=lambda i: longs[i])
    open_grid(m); paint(m)
    nmeasure = len(m.measures)
    texts = sorted(m.texts, key=lambda t: (t[1][1], t[1][0]))
    by_album = {a: t[0] for a, t in enumerate(texts)}
    expect(by_album[0] == 'Short' and by_album[3] == 'ABCDEFGHIJK', 'a title that fits is drawn whole')
    expect(by_album[1] == 'Twelve ch…' and by_album[2] == 'A very lo…' and by_album[4] == 'ABCDEFGHI…',
           f'long titles are cut where text + ellipsis fits 92 px (8 px a char, 16 for the ellipsis) ({by_album[1]!r}, {by_album[2]!r}, {by_album[4]!r})')
    expect(by_album[5] == '日本語の…' and by_album[6] == '日本語のア', f'wide characters count their width ({by_album[5]!r}, {by_album[6]!r})')
    expect(nmeasure <= 7 * 7, f'a title is measured about log2(48) times ({nmeasure} for 7)')
    paint(m)
    expect(not m.measures, 'titles are measured once, when the tile is made, never again')

    # 9. Missing cache files: no picture for them, the placeholder disc instead, no decode attempt, nothing built.
    m = albums_machine(9, missing={1, 4}, empty={2, 7})
    open_grid(m); blits, _ = settle(m)
    counts = {bm: sum(1 for b in blits if b[0] == bm) for bm in {b[0] for b in blits}}
    expect(len(blits) == 9 and sorted(counts.values()) == [1] * 5 + [4], f'five albums have a tile each, the four without art share one bitmap ({sorted(counts.values())})')
    expect(not any(n in m.names() for n in ('pthread_create', 'toolsGetAlbumCover', 'mkdir')) and not any(c[0] == 'fopen' and 'w' in c[2] for c in m.calls),
           'a missing cache file starts no build and writes no marker (open Cover Flow once to make the cache)')
    m = albums_machine(6, cached=False)
    open_grid(m); blits, texts = settle(m)
    expect(len(blits) == 6 and len({b[0] for b in blits}) == 1 and len(texts) == 6, 'with no cache at all every cell is the placeholder with its title')
    m = albums_machine(3, cached=False); m.images.pop('p_default')
    open_grid(m); blits, _ = settle(m)
    d = m.bitmaps[blits[0][0]][0]
    expect(len(blits) == 3 and set(struct.unpack('<64I', bytes(m.u.mem_read(d, 256)))) == {0xff2b2b2b}, 'without the stock disc the placeholder is flat grey')
    m = albums_machine(3, cached=False); m.bitmap_ok = False
    open_grid(m); blits, texts = paint(m)
    expect(blits == [] and len(texts) == 3, 'if bitmaps cannot be made the titles still show')

    # 10. A large library: the work per frame and the memory do not grow with it.
    n = 4000
    m = albums_machine(n)
    open_grid(m)
    opened_cost = m.icount
    expect(sum(1 for c in m.calls if c[0] == 'calloc') <= 3, 'opening a library of 4000 allocates its list copy and one tile ring')
    expect(len([c for c in m.calls if c[0] == 'bitmap_create_ex']) == 1, 'the open itself makes one bitmap (the placeholder)')
    settle(m)
    rows = (n + COLS - 1) // COLS
    mx = GAP + rows * PITCH - VIEW_H
    last, loaded = 0, [len(m.bitmaps)]
    for target in (mx // 2, mx, 0):
        drag_to(m, target, last, 10000 + 1000 * len(loaded)); last = target
        blits, texts = settle(m)
        expect(dsts(blits) == want_dsts(reference(target, n)), f'4000 albums, scroll {target}: the frame is the visible cells only ({len(blits)})')
        expect(len(m.bitmaps) <= TILES + 1, f'live bitmaps stay within {TILES} tiles + the placeholder ({len(m.bitmaps)})')
        loaded.append(len(m.bitmaps))
    top_urls = [u for u in m.loads if u.startswith('file://')]
    expect(m.destroyed > 0 and len(top_urls) > len(set(top_urls)), f'old tiles are recycled as the view moves, and the albums back at the top are decoded again ({m.destroyed} destroyed, {len(top_urls)} loads of {len(set(top_urls))} covers)')
    m.call(PSYMS['al_on_destroy'], count=2000000)
    expect(len(m.bitmaps) == 0, f'closing the page destroys every bitmap ({len(m.bitmaps)} left)')
    expect(any(c[0] == 'deque_destroy' for c in m.calls) and any(c[0] == 'free' for c in m.calls), 'and frees the list copy and the tile ring')
    print(f'  4000 albums: open {opened_cost:,} payload instructions, at most {max(loaded)} bitmaps live')

    # 11. Closing mid-gesture or with a reload timer pending leaves nothing behind.
    m = albums_machine(30); open_grid(m); paint(m)       # a reload timer is pending after the first frame
    m.touch('down', 100, SCREEN_Y0 + 100, 1000, fn='al_on_pointer')
    m.call(PSYMS['al_on_destroy'], count=2000000)
    expect(('timer_remove', 0x777) in m.calls and any(c[0] == 'widget_ungrab' for c in m.calls), 'destroy removes the timers and releases a grab')
    expect(len(m.bitmaps) == 0, 'and every bitmap')
    m.call(PSYMS['al_on_more'], count=1000000)
    expect('widget_invalidate_force' not in m.names(), 'a late timer after close does nothing')

    # 12. Empty library: the status line, no view.
    m = albums_machine(0)
    open_grid(m)
    expect(('widget_set_text_utf8', m.widgets['label_status'], 'Update Local Music first') in m.calls, 'an empty library says so')
    expect(('widget_set_visible', m.widgets['view_grid'], 0) in m.calls and ('widget_set_sensitive', m.widgets['view_grid'], 0) in m.calls,
           'and hides the (insensitive) view')
    m = albums_machine(3); del m.widgets['view_grid']
    open_grid(m)
    expect('navigator_back' in m.names(), 'an asset without view_grid leaves the page')

    # 13. List mode: the same page, rows of LIST_ROW_H px (cover, album, artist, hairline), custom-drawn.
    def list_machine(n=30, **kw):
        m = albums_machine(n, **kw); m.fs[ALBUMS_FILE] = b'0\n'
        open_grid(m)
        return m

    def list_ref(scroll, n):
        """[(album, cover (src, dst) or None, title rect or None, artist rect or None, hairline y or None)] of a list frame."""
        out = []
        for a in range(n):
            top = a * ROW - scroll
            if top >= VIEW_H or top + ROW <= 0: continue
            ct, cb = max(0, -(top + LAY)), min(LART, VIEW_H - (top + LAY))
            cover = ((0, ct, LART, cb - ct), (LAX, top + LAY + ct, LART, cb - ct)) if cb > ct else None
            ok = lambda y, h: (TX, y, TW, h) if 0 <= y and y + h <= VIEW_H else None
            out.append((a, cover, ok(top + TY, TH), ok(top + SY, SH), top + ROW - 1 if 0 <= top + ROW - 1 < VIEW_H else None))
        return out

    m = list_machine(30)
    blits, texts = paint(m)
    ref = list_ref(0, 30)
    expect(len(ref) == 7, 'seven rows touch the 400 px view at the top (the last by 16 px)')
    expect(dsts(blits) == sorted(c[1][1] for c in ref if c[1]) and all(b[1][2:] == (LART, LART) or b[1][3] < LART for b in blits),
           f'one {LART} px cover per visible row at ({LAX}, row + {LAY}), the seventh cut to the view')
    want_t = sorted((f'Album {a}', t) for a, _, t, _, _ in ref if t)
    want_a = sorted((f'Artist {a}', s_) for a, _, _, s_, _ in ref if s_)
    got_t = sorted((t[0], t[1]) for t, sty in zip(texts, m.text_styles) if sty == 'label_row_title')
    got_a = sorted((t[0], t[1]) for t, sty in zip(texts, m.text_styles) if sty == 'label_row_sub')
    expect(got_t == want_t and got_a == want_a and len(texts) == len(want_t) + len(want_a),
           f'the album names in the title style and the artists in the sub style, each in its {TW} px rect; texts cut by the view are not drawn ({len(want_t)} + {len(want_a)})')
    prep = [c[1] for c in m.calls if c[0] == 'widget_prepare_text_style']
    expect(prep == [m.widgets['label_row_title'], m.widgets['label_row_sub']] and m.text_styles == ['label_row_title'] * len(want_t) + ['label_row_sub'] * len(want_a),
           'two text-style switches a frame: all titles, then all artists')
    expect(sorted(f[1:] for f in m.fills if f[0] == O['LIST_HAIR']) == sorted((0, c[4], 320, 1) for c in ref if c[4] is not None)
           and not [f for f in m.fills if f[0] == O['LIST_PRESS']], 'a one pixel hairline under every row whose last line is in view, no pressed fill')
    expect(len([c for c in m.calls if c[0] == 'widget_load_image']) == 2, 'covers are decoded two a frame here too')
    m.call(PSYMS['al_on_more'], count=1000000)      # the reload timer fires
    blits, texts = settle(m)
    expect(len(blits) == 7 and len(m.bitmaps) == 1 + 7, f'every visible row has its own cover once loaded ({len(m.bitmaps)} bitmaps)')
    data, bw, bh = m.bitmaps[m.blits[0][0]]
    expect((bw, bh) == (LART, LART) and set(struct.unpack(f'<{bw * bh}I', bytes(m.u.mem_read(data, bw * bh * 4)))) == {colour(0)},
           f'row 0\'s cover is its cache picture reduced to {LART}x{LART}')
    paint(m)
    expect('widget_load_image' not in m.names() and 'bitmap_create_ex' not in m.names() and not m.measures,
           'a steady list frame decodes, allocates and measures nothing')
    print(f'  list frame: {m.icount:,} payload instructions steady (7 rows)')

    # 13b. Scrolling and bounds: the content is count x 64 px; partial rows are cut by hand.
    n = 20
    m = list_machine(n, cached=False); settle(m)
    mx = n * ROW - VIEW_H
    expect(mx == 880, 'twenty rows are 1280 px of content: 880 px of scroll')
    drag_to(m, 100, 0)
    blits, texts = paint(m)
    ref = list_ref(100, n)
    expect(dsts(blits) == sorted(c[1][1] for c in ref if c[1]), 'after scrolling 100 px: the rows and the cut first cover')
    top_row = [b for b in blits if b[2][1] == 0][0]
    want_top = [c[1] for c in ref if c[1] and c[1][1][1] == 0][0]
    expect((top_row[1], top_row[2]) == want_top and top_row[1][1] + top_row[1][3] == LART,
           f'the first cover is cut to its last pixels ({top_row[1]} -> {top_row[2]})')
    expect(sorted(t[0] for t in texts) == sorted([f'Album {a}' for a, _, t, _, _ in ref if t] + [f'Artist {a}' for a, _, _, s_, _ in ref if s_]),
           'texts that do not lie wholly in the view are not drawn')
    drag_to(m, 100000, 100, 2000)
    blits, texts = paint(m)
    ref = list_ref(mx, n)
    expect(dsts(blits) == sorted(c[1][1] for c in ref if c[1]), f'dragging far past the end stops at {mx} px')
    expect(m.fills and max(f[2] + f[4] for f in m.fills if f[0] == O['LIST_HAIR']) == VIEW_H, 'the last hairline is the last line of the view')
    drag_to(m, -5000, mx, 4000)
    blits, texts = paint(m)
    expect(dsts(blits) == sorted(c[1][1] for c in list_ref(0, n) if c[1]), 'dragging past the start stops at 0')
    m2 = list_machine(6, cached=False); drag_to(m2, 300, 0)
    blits, _ = paint(m2)
    expect(dsts(blits) == sorted(c[1][1] for c in list_ref(0, 6) if c[1]) and len(blits) == 6, 'six rows (384 px) cannot scroll')
    flick = lambda dy, t0=1000: [('down', 100, 350, t0), ('move', 100, 350 + dy // 2, t0 + 16), ('move', 100, 350 + dy, t0 + 32), ('up', 100, 350 + dy, t0 + 40)]
    m3 = list_machine(300, cached=False)
    expect(any(c[0] == 'timer_add' and c[1] == PSYMS['al_on_fling'] for c in gesture(m3, flick(-80))), 'a quick release flings in list mode too')

    # 13c. Taps: any x on a row opens its album (the hairline line included); below the last row nothing; the pressed row
    #      is filled while the finger is down and clears on release, on a drag and on abort.
    n = 9
    m = list_machine(n, cached=False); settle(m)
    row_xy = lambda a, scroll=0, dy=20, x=200: (x, a * ROW - scroll + dy)
    calls = tap_at(m, *row_xy(4))
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ALBUMS'], 4) in calls, 'a tap on row 4 opens its album with 0xf003 | 4 << 16')
    seq = [c[0] for c in calls if c[0] in ('loadAlbumList', 'albumcoverinfo_init', 'batchadd_albumcover_task', 'navigator_to_with_context')]
    expect(seq == ['loadAlbumList', 'albumcoverinfo_init', 'batchadd_albumcover_task', 'navigator_to_with_context'], f'the stock open sequence, as the grid\'s ({seq})')
    for what, (x, y, want) in {'its cover': (20, 2 * ROW + 20, 2), 'the right edge': (319, 2 * ROW + 5, 2), 'the hairline line': (100, 3 * ROW - 1, 2),
                               'the next row\'s first line': (100, 3 * ROW, 3)}.items():
        got = [c for c in tap_at(m, x, y) if c[0] == 'navigator_to_with_context']
        expect((got[0][3] if got else None) == want, f'a tap on {what}: ' + (f'album {want}' if want is not None else 'nothing'))
    expect(not [c for c in tap_at(m, 100, -1) if c[0] == 'navigator_to_with_context'], 'a tap above the view opens nothing')
    paint(m)
    m.touch('down', 100, SCREEN_Y0 + 3 * ROW + 20, 5000, fn='al_on_pointer')
    expect(any(c[0] == 'widget_invalidate_force' for c in m.calls), 'touching a row redraws the view')
    paint(m)
    pf = [f for f in m.fills if f[0] == O['LIST_PRESS']]
    expect(pf == [(O['LIST_PRESS'], 0, 3 * ROW, 320, ROW - 1)], f'the pressed row is filled #333333 over its body, above the hairline ({pf})')
    m.touch('up', 100, SCREEN_Y0 + 3 * ROW + 20, 5080, fn='al_on_pointer')
    paint(m)
    expect(not [f for f in m.fills if f[0] == O['LIST_PRESS']], 'and the fill is gone after the release')
    m.touch('down', 100, SCREEN_Y0 + 3 * ROW + 20, 6000, fn='al_on_pointer')
    m.touch('move', 100, SCREEN_Y0 + 3 * ROW + 60, 6300, fn='al_on_pointer')
    paint(m)
    expect(not [f for f in m.fills if f[0] == O['LIST_PRESS']], 'a drag past the slop takes the highlight away')
    m.touch('up', 100, SCREEN_Y0 + 3 * ROW + 60, 6700, fn='al_on_pointer')
    m.touch('down', 100, SCREEN_Y0 + 3 * ROW + 20, 7000, fn='al_on_pointer')
    m.touch('abort', 100, SCREEN_Y0 + 3 * ROW + 20, 7100, fn='al_on_pointer')
    paint(m)
    expect(not [f for f in m.fills if f[0] == O['LIST_PRESS']], 'an aborted gesture clears it too')
    ms = list_machine(3, cached=False); settle(ms)
    expect(not [c for c in tap_at(ms, 100, 3 * ROW + 10) if c[0] == 'navigator_to_with_context'], 'a tap below the last row opens nothing')
    ms.touch('down', 100, SCREEN_Y0 + 3 * ROW + 10, 8000, fn='al_on_pointer')
    paint(ms)
    expect(not [f for f in ms.fills if f[0] == O['LIST_PRESS']], 'and a touch there highlights nothing')
    mg = albums_machine(n, cached=False); open_grid(mg); settle(mg)
    gesture(mg, [('down', 30, 20, 1000)]); paint(mg)
    expect(not mg.fills, 'the grid mode never fills a row')

    # 13d. Ellipsis: the same rule as the grid\'s, at LIST_TEXT_W, separately for the album and the artist (the mock
    #      font is 8 px a character, 16 for CJK and the ellipsis: 248 px hold 31 characters, or 29 and an ellipsis).
    fits = TW // 8
    longs = {0: 'T' * fits, 1: 'T' * (fits + 1), 2: 'あ' * 15, 3: 'あ' * 16, 4: 'Short'}
    m = albums_machine(5, cached=False, title=lambda i: longs[i])
    m.fs[ALBUMS_FILE] = b'0\n'
    for i in range(5): m.setword(m.showlist[i] + O['REC_ARTIST'], m.cstr(longs[(i + 1) % 5]))
    open_grid(m); texts = paint(m)[1]
    titles = {t[1][1] // ROW: t[0] for t, sty in zip(texts, m.text_styles) if sty == 'label_row_title'}
    artists = {t[1][1] // ROW: t[0] for t, sty in zip(texts, m.text_styles) if sty == 'label_row_sub'}
    expect(titles[0] == 'T' * fits and titles[1] == 'T' * (fits - 2) + '…', f'a title that fits {TW} px is whole, one more character is cut with an ellipsis ({titles[1]!r})')
    expect(titles[2] == 'あ' * 15 and titles[3] == 'あ' * 14 + '…', f'wide characters count their width ({titles[2]!r}, {titles[3]!r})')
    expect(artists[0] == 'T' * (fits - 2) + '…' and artists[1] == 'あ' * 15 and artists[2] == 'あ' * 14 + '…' and artists[3] == 'Short',
           f'the artist line is cut by the same rule ({artists[0]!r}, {artists[2]!r})')
    expect(len(m.measures) <= 10 * 7, f'about log2(48) measures per cut text ({len(m.measures)})')
    paint(m)
    expect(not m.measures, 'texts are measured once, never again')

    # 13e. Placeholders in the list: the stock disc at the list size, shared; flat grey without it; no bitmaps, still text.
    m = list_machine(6, cached=False); blits, texts = settle(m)
    expect(len(blits) == 6 and len({b[0] for b in blits}) == 1 and len(texts) == 12 and m.bitmaps[blits[0][0]][1:] == (LART, LART),
           'with no cache every row shows the one shared placeholder, 52x52, with both lines')
    m = albums_machine(3, cached=False); m.fs[ALBUMS_FILE] = b'0\n'; m.images.pop('p_default'); open_grid(m)
    blits, _ = settle(m); d = m.bitmaps[blits[0][0]][0]
    expect(set(struct.unpack('<64I', bytes(m.u.mem_read(d, 256)))) == {0xff2b2b2b}, 'without the stock disc the placeholder is flat grey')
    m = albums_machine(3, cached=False); m.fs[ALBUMS_FILE] = b'0\n'; m.bitmap_ok = False; open_grid(m)
    blits, texts = paint(m)
    expect(blits == [] and len(texts) == 6, 'if bitmaps cannot be made the texts still show')
    m = albums_machine(4000); m.fs[ALBUMS_FILE] = b'0\n'; open_grid(m); settle(m)
    mx, last = 4000 * ROW - VIEW_H, 0
    for target in (mx // 2, mx, 0):
        drag_to(m, target, last, 20000 + target); last = target; settle(m)
        expect(len(m.bitmaps) <= TILES + 1, f'list of 4000: live bitmaps stay within {TILES} tiles + the placeholder ({len(m.bitmaps)})')
    m.call(PSYMS['al_on_destroy'], count=2000000)
    expect(len(m.bitmaps) == 0, 'closing the list frees every bitmap')

    # 14. The toggle: switches the mode in place (no window opens or closes), saves the choice atomically, swaps the
    #     glyph, drops the tiles, keeps the first album in view.
    def glyph(m): return m.props.get((m.widgets['btn_albumview'], 'style:normal:icon'))
    opened_ev = ('window_open', 'window_close', 'navigator_back', 'navigator_to_with_context', 'stock_resume', 'widget_destroy')
    m = albums_machine(60)
    open_grid(m); settle(m)
    expect(glyph(m) == 'pod_nav_list', 'the grid shows the list glyph')
    drag_to(m, 700, 0); paint(m)
    first_row = (700 - GAP - CELL) // PITCH + 1
    m.calls = []
    m.call(PSYMS['al_on_toggle'], a0=0, count=20000000)
    calls = m.calls
    expect(not [c for c in calls if c[0] in opened_ev], f'toggling opens and closes nothing ({[c[0] for c in calls if c[0] in opened_ev]})')
    expect(m.fs.get(ALBUMS_FILE) == b'0\n' and ALBUMS_TMP not in m.fs, f'it saves "0" atomically ({m.fs.get(ALBUMS_FILE)!r})')
    expect(('fsync', ALBUMS_TMP) in calls and ('fsync', '/mnt/data') in calls and ('rename', ALBUMS_TMP, ALBUMS_FILE) in calls,
           'temp file, fsync, rename, directory fsync (as the Start-in setting)')
    expect(glyph(m) == 'pod_nav_grid' and m.props.get((m.widgets['btn_albumview'], 'style:pressed:icon')) == 'pod_nav_grid_down'
           and m.props.get((m.widgets['btn_albumview'], 'style:over:icon')) == 'pod_nav_grid', 'the button now shows the grid glyph')
    expect(('widget_invalidate_force', m.widgets['view_grid']) in calls, 'and the view is redrawn')
    expect(len(m.bitmaps) == 1 and m.bitmaps[next(iter(m.bitmaps))][1:] == (LART, LART), 'the grid\'s covers are dropped; the placeholder is the list\'s size')
    blits, texts = paint(m)
    top = [t for t, sty in zip(texts, m.text_styles) if sty == 'label_row_title' and t[1][1] < 40]
    expect(top and top[0][0] == f'Album {first_row * COLS}', f'the first album in view stays first: Album {first_row * COLS} ({top[0][0] if top else None})')
    # and back
    m.calls = []
    m.call(PSYMS['al_on_toggle'], a0=0, count=20000000)
    expect(not [c for c in m.calls if c[0] in opened_ev] and m.fs.get(ALBUMS_FILE) == b'1\n' and glyph(m) == 'pod_nav_list'
           and m.props.get((m.widgets['btn_albumview'], 'style:pressed:icon')) == 'pod_nav_list_down', 'toggling back: in place, "1" saved, the list glyph')
    blits, texts = paint(m)
    expect(min(int(t[0].split()[1]) for t in texts) == first_row * COLS, f'back in the grid the same album row is in view (Album {first_row * COLS})')
    # the tiles of the other mode are never reused: no 92 px blit in the list, no 52 px one in the grid
    blits, _ = settle(m)
    expect(all(m.bitmaps[b[0]][1:] == (COVER, COVER) for b in blits), 'grid covers are 92 px again')
    # many switches: no window churn, no leak
    seen = []
    for _ in range(8):
        m.call(PSYMS['al_on_toggle'], a0=0, count=20000000); seen += m.calls; settle(m); seen += m.calls
    expect(len(m.bitmaps) <= TILES + 1, f'after many switches the live bitmaps are still bounded ({len(m.bitmaps)})')
    expect(not [c for c in seen if c[0] in opened_ev], 'eight more switches opened and closed no window')
    # a pending reload timer and a fling are cancelled by the switch
    m = albums_machine(60); open_grid(m); paint(m)
    assert any(c[0] == 'timer_add' and c[1] == PSYMS['al_on_more'] for c in m.calls)
    m.calls = []
    m.call(PSYMS['al_on_toggle'], a0=0, count=20000000)
    expect(('timer_remove', 0x777) in m.calls, 'the pending reload timer is removed when the mode changes')
    m = albums_machine(300, cached=False); open_grid(m); gesture(m, [('down', 100, 350, 1000), ('move', 100, 310, 1016), ('move', 100, 270, 1032), ('up', 100, 270, 1040)])
    m.calls = []; m.call(PSYMS['al_on_toggle'], a0=0, count=20000000)
    expect(('timer_remove', 0x777) in m.calls, 'a fling in progress is stopped by the switch')
    # list -> grid -> list keeps the position to the nearest row
    m = list_machine(60, cached=False); drag_to(m, 5 * ROW, 0)
    m.call(PSYMS['al_on_toggle'], a0=0, count=20000000)
    blits, texts = paint(m)
    expect(m.fs.get(ALBUMS_FILE) == b'1\n' and min(int(t[0].split()[1]) for t in texts) == (5 // COLS) * COLS, 'from the list at row 5 the grid shows row 1 (albums 3..5) first')
    # an empty library, a closed page
    m = albums_machine(0); m.fs[ALBUMS_FILE] = b'0\n'; open_grid(m); m.calls = []
    m.call(PSYMS['al_on_toggle'], a0=0, count=20000000)
    expect(m.fs.get(ALBUMS_FILE) == b'1\n' and glyph(m) == 'pod_nav_list', 'with an empty library the toggle still switches and saves')
    m = albums_machine(3); open_grid(m); m.call(PSYMS['al_on_destroy'], count=2000000); m.calls = []
    m.call(PSYMS['al_on_toggle'], a0=0, count=20000000)
    expect(not m.calls and ALBUMS_FILE not in m.fs, 'a late toggle after the page closed does nothing')

    # 15. Persistence across opens: the Albums row opens the last mode.
    m = albums_machine(3)
    open_grid(m)
    m.call(PSYMS['al_on_toggle'], a0=0, count=20000000)
    m.call(PSYMS['al_on_destroy'], count=2000000)
    m.calls = []; m.call(on_row, a0=rows0 + 12 * row, count=20000000)
    expect(('window_open', 'm1pod_albums') in m.calls and glyph(m) == 'pod_nav_grid' and 'stock_resume' not in m.names(), 'after switching to the list, the next Albums row opens the list')
    m.call(PSYMS['al_on_toggle'], a0=0, count=20000000)
    m.call(PSYMS['al_on_destroy'], count=2000000)
    m.calls = []; m.call(on_row, a0=rows0 + 12 * row, count=20000000)
    expect(('window_open', 'm1pod_albums') in m.calls and glyph(m) == 'pod_nav_list', 'and after switching back, the grid')
    m = albums_machine(3); open_grid(m)
    m.calls = []; m.call(PSYMS['albums_open'], count=20000000)
    expect('window_open' not in m.names() and 'stock_resume' not in m.names(), 'the page that is up is neither opened twice nor replaced by the stock list')

    # 16. Hit tests with demo's own widget_find_target on the page: the grid view takes touches under the navbar, the
    #     navbar buttons theirs, and the hidden status line none.
    m = albums_machine(30)
    open_grid(m)
    root = asset_tree(asset)
    for x, y, want in ((160, 60, 'view_grid'), (20, 200, 'view_grid'), (160, 449, 'view_grid'), (40, 25, 'btn_return'),
                       (O['NAV_VIEW_X'] + 20, 25, 'btn_albumview'), (290, 25, 'btn_backtoplayer'), (160, 230, 'view_grid')):
        got = stock_target(m, root, x, y)
        expect(got[-1] == want, f'a touch at ({x},{y}) goes to {want} ({got})')
    expect(all(node(root, nm).flags & F_SENSITIVE == 0 for nm in ('label_status', 'label_row_title', 'label_row_sub')),
           'the status label and the two list-style labels are insensitive')
