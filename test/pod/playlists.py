"""Playlists: the menu row, the page's structure (a stock list_view > scroll_view holding the one content view, the "..." button and its popup),
the playlists read from the stock query, the mosaic of each playlist's album covers (0, 1, 2, 3, 5+ albums; one source decoded per tick; a
playlist with no songs; the library lookup for an album whose track carries another artist), the names and track counts, the tap that opens a
playlist in the stock songs page, the loader that decodes nothing while the scroll_view moves, reading again when the window comes back to
the front, the empty page, and the menu's actions routed to the stock code (create, import, export, delete)."""
import os, struct
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

SCREEN_Y0 = 30 + 50
COVER, GAP, MARGIN, COLS = O['GRID_COVER'], O['GRID_GAP'], O['GRID_MARGIN'], O['GRID_COLS']
TGAP, THEIGHT, VIEW_H, TILES = O['GRID_TITLE_GAP'], O['GRID_TITLE_H'], O['GRID_VIEW_H'], O['GRID_TILES']
RGAP, SUBH = O['GRID_ROW_GAP'], O['GRID_SUB_H']
CELL = COVER + TGAP + THEIGHT + SUBH
PITCH = CELL + RGAP
CPITCH = COVER + GAP
SVW, CW = 310, 320
SC_YOFF, SC_VH = O['SC_YOFF'], 0x7c
HALF = COVER // 2
REC_DISC = O['REC_DISC']
UI = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1plus_playlists.bin') if WORK else None
NAV_STATUS, CLASSINFO = pod.DATA['NAVIGATION_STATUS'][0], pod.DATA['CLASSINFO'][0]
PL_FILE = '/mnt/data/m1plus-playlists'
GREY_DISC = 0xff404040     # the stock placeholder disc of these tests (p_default, flat)


def colour(i):
    """The flat colour of album i's cover (a 32 bit RGBA word, as the decoder leaves it)."""
    return 0xff000000 | (i * 37 % 256) | (i * 59 % 256) << 8 | (i * 83 % 256) << 16


def near(a, b, tol=2):
    return all(abs(((a >> s) & 255) - ((b >> s) & 255)) <= tol for s in (0, 8, 16, 24))


def alb(i): return f'Artist {i}', f'Album {i}'


def key_path(artist, album): return art_file(fnv(fnv(O['FNV_SEED'], artist), album) or 1)


class LabelMachine(SelectMachine):
    """The menu labels' texts (label_text: handle -> text, widget_get_text's wide string) and their widths (measure: text -> px, None: the
    measure fails and returns 0), as widget_measure_text returns them (a float in $f0)."""

    def __init__(self):
        super().__init__()
        self.label_text, self.measure, self.measured = {}, None, []
        for n in ('widget_get_text', 'widget_measure_text'):
            self.handlers[pod.FUNCTIONS[n][2]] = n

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address, '')
        a0, a1 = u.reg_read(UC_MIPS_REG_A0), u.reg_read(UC_MIPS_REG_A1)
        if name == 'widget_get_text':
            t, ret = self.label_text.get(a0), 0
            if t is not None:
                ret = self.alloc(4 * len(t) + 4); self.u.mem_write(ret, struct.pack(f'<{len(t) + 1}I', *map(ord, t), 0))
            u.reg_write(UC_MIPS_REG_V0, ret); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        if name == 'widget_measure_text':
            n = 0
            while self.word(a1 + 4 * n): n += 1
            t = ''.join(map(chr, struct.unpack(f'<{n}I', self.u.mem_read(a1, 4 * n)))) if n else ''
            w = float(self.measure(t)) if self.measure and t else 0.0
            self.measured.append((a0, t))
            u.reg_write(UC_MIPS_REG_F0, struct.unpack('<I', struct.pack('<f', w))[0]); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        return super()._hook(u, address, size, _)


class PM:
    """A machine with the page's widgets as widget structs (window > list_view > scroll_view > view_grid, for demo's own widget_to_local), the library's
    albums (cover files for the albums not in `missing`), and the playlists given as [(id, name, [album numbers of its songs])]."""

    def __new__(cls, lists, albums=8, missing=(), other_artist=(), window=0x20001000):
        m = LabelMachine()
        m.fs[CFSORT_FILE] = b'0\n'
        m.load_image = 0
        for w in ('btn_return', 'btn_backtoplayer', 'btn_more', 'btn_albumview', 'label_row_title', 'label_row_sub', 'pl_scrim', 'pl_card', 'view_grid', 'label_status', 'label_grid_title', 'label_grid_sub',
                  'pl_item0', 'pl_item1', 'pl_item2', 'pl_item3', 'pl_label0', 'pl_label1', 'pl_label2', 'pl_label3', 'label_title', 'btn_selall', 'pl_bar', 'pl_del'): Machine.widget(m, w)
        m.label_text[m.widgets['pl_del']] = 'Delete'   # the text the asset gives the pill
        for i, text in enumerate(pod_pages.PLAYLIST_MENU): m.label_text[m.widgets[f'pl_label{i}']] = text
        m.canvas = m.alloc(0x80); m.oy_canvas = m.canvas
        m.images = {'p_default': (24, 24, bytes((0x40, 0x40, 0x40, 255)) * (24 * 24)), 'unselect': (26, 26, struct.pack('<I', 0xff111111) * 676),
                    'selected': (26, 26, struct.pack('<I', 0xff2222ee) * 676)}
        m.lib = [m.record(album=alb(i)[1], artist=alb(i)[0], path=f'/mnt/mmc/m/{i}/1.flac', rid=i + 1) for i in range(albums)]
        m.class_lists[O['CLASS_ALBUMS']] = m.lib
        for i in range(albums):
            if i in missing: continue
            p = key_path(*alb(i))
            m.present.add(p); m.files[p] = 4096
            c = colour(i)
            m.images['file://' + p] = (24, 24, struct.pack('<I', c) * (24 * 24))
        m.playlists, m.playlist_songs = [], {}
        for pid, name, songs in lists: PM.add(m, pid, name, songs, other_artist)
        # the page as widget structs, for the stock widget_to_local
        win, lv, sv = m.alloc(0x80), m.alloc(0x80), m.alloc(0x180)
        m.u.mem_write(sv, bytes(0x180))
        for w, y, h, parent in ((win, 30, 450, 0), (lv, 50, VIEW_H, win), (sv, 0, VIEW_H, lv)):
            for off, v in ((4, y), (8, 320), (0xc, h), (0x44, parent)): m.setword(w + off, v)
        m.setword(sv + 8, SVW)
        m.widgets['playlists_scrollview'] = sv
        view = m.widgets['view_grid']
        for off, v in ((4, 0), (8, CW), (0xc, VIEW_H), (0x44, sv)): m.setword(view + off, v)
        m.mem_geometry, m.live_scroll = True, frozenset({sv})
        m.sv = sv
        return m

    @staticmethod
    def add(m, pid, name, songs, other_artist=()):
        rec = m.record(album='', artist='', title=name, rid=pid)
        m.setword(rec + REC_DISC, pid)
        m.playlists.append(rec)
        m.playlist_songs[pid] = [m.record(album=alb(a)[1], artist='Other' if a in other_artist else alb(a)[0], path=f'/mnt/mmc/m/{a}/1.flac',
                                          title=f'T{k}', rid=1000 + k) for k, a in enumerate(songs)]


def open_page(m):
    m.call(PSYMS['playlists_open'], count=60000000)
    return list(m.calls)


def paint(m):
    """One EVT_AFTER_PAINT on the content view: (blits, texts, styles) of that frame, the canvas where the scroll_view leaves it."""
    ev = m.alloc(0x40); m.u.mem_write(ev, bytes(0x40)); m.setword(ev + O['EVENT_PAINT_CANVAS'], m.canvas)
    m.setword(m.canvas + O['CANVAS_OY'], (SCREEN_Y0 - m.word(m.sv + SC_YOFF)) & 0xffffffff)
    m.blits.clear(); m.texts.clear(); m.text_styles.clear(); m.fills.clear()
    m.call(PSYMS['pl_on_paint'], a0=0, a1=ev, count=400000000)
    return list(m.blits), list(m.texts), list(m.text_styles)


def tick(m):
    m.call(PSYMS['pl_on_load'], count=40000000)
    return list(m.calls)


def settle(m, limit=200):
    """Fire the loader's timer until it stops re-arming itself; the decodes per tick (at most one), then a paint."""
    most = 0
    for _ in range(limit):
        calls = tick(m)
        most = max(most, sum(1 for c in calls if c[0] == 'widget_load_image' and c[1] not in ('p_default', 'unselect', 'selected')))
        if not any(c[0] == 'timer_add' and c[1] == PSYMS['pl_on_load'] for c in calls):
            m.most_per_tick = most
            return paint(m)
    raise AssertionError('the page never finished loading')


def pixel(m, bmp, x, y):
    data, w, h = m.bitmaps[bmp]
    return struct.unpack('<I', m.u.mem_read(data + (y * w + x) * 4, 4))[0]


def quadrants(m, bmp, side=COVER):
    h = side // 2
    return [pixel(m, bmp, x, y) for y in (h // 2, h + h // 2) for x in (h // 2, h + h // 2)]


def scroll_to(m, v):
    """The scroll_view's offset to v, and the page told as the stock setter's EVT_SCROLL tells it."""
    m.setword(m.sv + SC_YOFF, v)
    fn, ctx = m.bound[(m.sv, O['EVT_SCROLL'])]
    m.call(fn, a0=ctx, a1=0, count=40000000)


def cell_blit(blits, i, off=0):
    x, y = MARGIN + (i % COLS) * CPITCH, RGAP + (i // COLS) * PITCH - off
    return next((b[0] for b in blits if b[2][0] == x and b[2][1] == y and b[2][2] == COVER), None)


def want_mosaic(distinct):
    n = len(distinct)
    if n == 0: return None
    c = [colour(a) for a in distinct]
    return [c[0]] * 4 if n == 1 else [c[0], c[1], c[1], c[0]] if n == 2 else [c[0], c[1], c[2], c[0]] if n == 3 else c[:4]


def tap(m, x, y, dx=0, dy=0):
    m.touch('down', x, SCREEN_Y0 + y, 1000, fn='pl_on_down')
    m.touch('up', x + dx, SCREEN_Y0 + y + dy, 1080, fn='pl_on_up')
    return list(m.calls)


GP = 0xa03ed0
DIM = 130    # the scrim's alpha: Now Playing's More sheet's highlight (tools/mod_lists.py PM_HIGHLIGHT)


def glass_checks(expect, tree, scrim, card, items):
    """The menu's glass: pl_glass.png is the generator's (Now Playing's More sheet's fill, all four corners), its middle third the same in every
    column (patch3_x stretches it), the card draws it patch3_x over no fill, the scrim dims the page as the sheet's highlighter does; the stock
    code draws patch3_x as assumed; white labels keep 7:1 at rest and pressed over black and over white under the dim."""
    import io, mod_icons
    from PIL import Image
    png = lambda im: (lambda b: (im.save(b, 'PNG', optimize=True), b.getvalue())[1])(io.BytesIO())
    w, h, r = mod_icons.GLASS_MENU
    raw_ = open(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/images/xx/pl_glass.png'), 'rb').read()
    gen = mod_icons.glass_image(w, h, r, fill=mod_icons.GLASS_SHEET_FILL)
    expect(raw_ == open(os.path.join(mod_icons.PNG, 'pl_glass.png'), 'rb').read() == png(gen) and (w, h, r) == (72, card.h, pod_ui.PL_CARD_R),
           f'pl_glass.png is the generator output byte for byte: {w}x{h} (the card\'s height), r {r}, the sheet\'s fill {mod_icons.GLASS_SHEET_FILL[2]}')
    g = Image.open(io.BytesIO(raw_)).convert('RGBA')
    a = lambda x, y: g.getpixel((x, y))[3]
    third = w // 3
    expect(all(a(x, y) == 0 for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))) and a(w // 2, h // 2) >= 0.85 * 255 and r <= third
           and all(len({g.getpixel((x, y)) for x in range(third, w - third)}) == 1 for y in range(h)),
           f'pl_glass: four transparent corners (r {r} inside the outer thirds of {third} px), the middle third the same in every column (a stretch is exact)')
    expect(all(card.get(f'style:{st}:bg_image') == 'pl_glass' and card.get(f'style:{st}:bg_image_draw_type') == 'patch3_x' and card.get(f'style:{st}:bg_color') == '#00000000'
               and card.get(f'style:{st}:round_radius') is None for st in pod_ui.STATES)
           and (card.x + card.w, card.y, card.w) == (pod_ui.PL_CARD_RIGHT, pod_ui.PL_CARD_Y, pod_ui.PL_CARD_MAX) == (314, 44, 292),
           'the card is the glass image drawn patch3_x over no fill, at its widest in the asset (292 px), its right edge at 314 under the button')
    expect(all(scrim.get(f'style:{st}:bg_color') == '#%08X' % DIM for st in pod_ui.STATES) and DIM == int(pod_ui.PL_DIM[-2:], 16),
           f'the scrim dims the page by {DIM}/255, as Now Playing\'s More sheet\'s highlighter')
    users = []
    ui_root = os.path.join(WORK, 'rootfs', 'release/assets')
    for base, _, files in os.walk(ui_root):
        users += [os.path.relpath(os.path.join(base, f), ui_root) for f in files if f.endswith('.bin') and b'pl_glass' in open(os.path.join(base, f), 'rb').read()]
    expect(users == ['default/raw/ui/m1plus_playlists.bin', 'default/raw/ui/m1plus_podcasts.bin'], f'pl_glass is used by the Playlists page and the Podcasts refresh dialog only ({users})')
    # the stock code: an inline bg_image_draw_type name is normalised by image_draw_type_find (style_normalize_value @0x65a1f4: strstr "image_draw_type"),
    # "patch3_x" is 13 in its table (@0x9050d8), canvas_draw_image_ex's case 13 (jump table @0x75ce40) calls canvas_draw_image_patch3_x (@0x647a08),
    # which keeps min(dst.w, img.w) / 3 at each end (li $v0, 3; div @0x647b0c) and stretches the middle
    m = Machine()
    s32 = lambda v: v - (1 << 32) if v >> 31 else v
    case13 = (GP + s32(m.word(0x75ce40 + 13 * 4))) & 0xffffffff
    ins = m.word(case13)
    expect(m.read_cstr(0x75dee0) == 'image_draw_type' and m.word(0x65a25c) & 0xffff == 0xdee0 and m.read_cstr(m.word(0x9050d8 + 14 * 12)) == 'patch3_x'
           and m.word(0x9050d8 + 14 * 12 + 8) == 13 and case13 == 0x649404 and ins >> 16 == 0x8f99 and m.word((GP + s32(ins & 0xffff | (0xffff0000 if ins & 0x8000 else 0))) & 0xffffffff) == 0x647a08
           and (m.word(0x647b0c), m.word(0x647b14)) == (0x24020003, 0x0222001a),
           'stock draws an inline patch3_x background as canvas_draw_image_patch3_x, both ends a third of the image wide (pinned words)')
    # contrast: the glass (middle column, every label row) over black and over white under the dim, at rest and pressed
    press = 0x10 / 255
    worst = 99
    for level in (0, round(255 * (255 - DIM) / 255)):
        for pressed in (False, True):
            for it in items:
                for y in range(it.y + (it.h - 22) // 2, it.y + (it.h + 22) // 2):   # the text band (18 px glyphs, centred), as playmore measures each label's box
                    p = g.getpixel((w // 2, y)); al = p[3] / 255
                    c = [al * p[i] + (1 - al) * level for i in range(3)]
                    if pressed: c = [press * 255 + (1 - press) * v for v in c]
                    worst = min(worst, contrast((255, 255, 255), c))
    expect(worst >= 7, f'white labels on the glass (their 22 px text band): worst {worst:.1f}:1 over black and over white under the dim, at rest and pressed (floor 7:1)')


def vis(m, name):
    w = m.widgets[name]
    return m.props.get((w, 'visible'), 1), m.props.get((w, 'sensitive'), 1)


MARK, SEL_COL = O['SG_MARK'], O['SG_SEL_COL']
SEL_VEC, PDEQ_PLAYLIST = pod.DATA['SEL_VEC'][0], pod.DATA['PDEQ_PLAYLIST'][0]


def marks_of(blits):
    """The select marks painted: (x, y, bitmap) of every 26 px blit."""
    return sorted((b[2][0], b[2][1], b[0]) for b in blits if b[2][2] == MARK and b[2][3] == MARK)


def select_tests(expect, lists):
    """Delete Playlists is select mode on this page (the Songs page's manner): the navbar's x, "N Selected", Select All, a mark on every cell or row, a bar with the Delete
    pill; Delete runs the stock handler's sequence (@0x53dbcc) on the stock selection vector: the message when nothing is marked, the stock confirm dialog (Yes 0xa),
    batch_delete_file(0xf00b, *pdeq_playlist, the vector, 0, 0), the success message; the page reads again. Where the page cannot do it the stock page opens."""
    names = ('btn_return', 'btn_more', 'btn_albumview', 'btn_backtoplayer')
    # the asset: the select widgets start hidden and insensitive, the bar is the Songs page's (black, a hairline, the flat pill), the popup stays last
    tree = awtk_ui.parse(open(UI, 'rb').read())
    sa, bar, line, pill = (tree.find(n) for n in ('btn_selall', 'pl_bar', 'pl_bar_line', 'pl_del'))
    expect(sa.type == 'button' and (sa.x, sa.y, sa.w, sa.h) == (O['SG_SELALL_X'], 0, 104, O['NAV_H']) and sa.get('visible') == 'false' and sa.get('sensitive') == 'false'
           and sa in tree.find('navigationbar_view').children, 'Select All is the Songs page\'s text button in the navbar, hidden and insensitive')
    expect(bar.type == 'view' and (bar.x, bar.y, bar.w, bar.h) == (0, 450 - O['SG_BAR_H'], 320, O['SG_BAR_H']) and bar.get('visible') == 'false' and bar.get('sensitive') == 'false'
           and line in bar.children and line.get('sensitive') == 'false' and pill in bar.children
           and (pill.x, pill.y, pill.w, pill.h) == (O['SG_PILL_X0'], (O['SG_BAR_H'] - O['SG_PILL_H']) // 2, O['PL_BAR_PILL_W'], O['SG_PILL_H']) and pill.get('style:normal:icon') == 'sg_trash'
           and pill.get('style:normal:round_radius') == str(O['SG_PILL_R']), 'the bar is the Songs page\'s (64 px, a hairline) with one Delete pill across it, hidden and insensitive')
    kids = tree.children
    expect(kids.index(bar) > kids.index(tree.find('playlists_listview')) and kids.index(bar) < kids.index(tree.find('pl_scrim')), 'the bar lies over the list and under the popup')

    # entering: from the menu's Delete Playlists row (the card closes); the navbar, the bar, the title, the marks
    m = PM(lists, missing=(7,)); open_page(m)
    expect(sum(1 for c in m.calls if c[0] == 'bitmap_create_ex' and c[1:3] == (MARK, MARK)) == 2 and ('widget_set_visible', m.widgets['pl_bar'], 1) not in m.calls,
           'select mode is off at open (the asset starts its widgets hidden and insensitive); the two marks are decoded once')
    settle(m)
    m.click('btn_more'); m.calls = []
    m.click('pl_item3')
    calls = list(m.calls)
    t, back = m.widgets['label_title'], m.widgets['btn_return']
    expect(vis(m, 'pl_card') == (0, 0) and vis(m, 'btn_selall') == (1, 1) and vis(m, 'pl_bar') == (1, 1) and all(vis(m, n) == (0, 0) for n in ('btn_more', 'btn_albumview', 'btn_backtoplayer')),
           'the menu closes; Select All and the bar show; "...", the toggle and Now Playing go (hidden and insensitive)')
    expect(vis(m, 'btn_return') != (0, 0) and m.props.get((back, 'style:normal:icon')) == 'ah_nav_close' and m.props.get((back, 'style:pressed:icon')) == 'ah_nav_close_down',
           'Back becomes the glass x')
    expect(('widget_set_text_utf8', t, '0 Selected') in calls and ('widget_resize', t, O['SG_SELALL_X'] - O['NAV_TITLE_X'], 22) in calls, 'the title reads 0 Selected and runs to Select All')
    expect('stock_resume' not in [c[0] for c in calls], 'the stock Playlists page is not opened')
    expect(m.props.get((m.sv, 'virtual_h')) == RGAP + 3 * PITCH + O['SG_BAR_H'], 'the content is the bar\'s height longer, so the last row scrolls clear of it')
    blits, texts, styles = paint(m)
    mk = marks_of(blits)
    want = [(MARGIN + (i % COLS) * CPITCH + COVER - MARK - 6, RGAP + (i // COLS) * PITCH + COVER - MARK - 6) for i in range(4)]
    expect([(x, y) for x, y, _ in mk] == sorted(want) and len({b for _, _, b in mk}) == 1, f'a mark at the bottom right of each cover in view, all the unselected image ({mk})')
    # a tap marks (and opens nothing); another unmarks; the count follows
    centre = lambda i: (MARGIN + (i % COLS) * CPITCH + 10, RGAP + (i // COLS) * PITCH + 10)
    calls = tap(m, *centre(1))
    expect(('widget_set_text_utf8', t, '1 Selected') in calls and not [c for c in calls if c[0] in ('window_open', 'navigator_to_with_context')], 'a tap on a cell marks it (the title reads 1 Selected) and opens no playlist')
    tap(m, *centre(3)); calls = tap(m, *centre(0)); calls = tap(m, *centre(0))
    expect(('widget_set_text_utf8', t, '2 Selected') in calls, 'a second tap on a cell unmarks it')
    mk = {(x, y): b for x, y, b in marks_of(paint(m)[0])}
    on, off = mk[want[1]], mk[want[0]]
    expect(on != off and mk[want[3]] == on and mk[want[2]] == off and pixel(m, on, 13, 13) == 0xff2222ee and pixel(m, off, 13, 13) == 0xff111111
           and pixel(m, on, 0, 0) >> 24 == 0, 'the marked cells show the selected image, the others the unselected one (cut to its circle: no square over the cover)')
    # a drag past the threshold marks nothing
    calls = tap(m, *centre(2), dy=14)
    expect(not [c for c in calls if c[0] == 'widget_set_text_utf8' and c[1] == t], 'a drag marks nothing')
    # Select All: all, then none
    m.click('btn_selall')
    expect(('widget_set_text_utf8', t, f'{len(lists)} Selected') in m.calls, 'Select All marks every playlist')
    m.click('btn_selall')
    expect(('widget_set_text_utf8', t, '0 Selected') in m.calls, 'and a second tap marks none')
    # Back (the x) leaves select mode first; the title and navbar are restored
    tap(m, *centre(1)); m.calls = []
    m.click('btn_return')
    expect('navigator_back' not in m.names() and vis(m, 'btn_selall') == (0, 0) and vis(m, 'pl_bar') == (0, 0) and all(vis(m, n) == (1, 1) for n in names)
           and ('widget_set_tr_text', t, 'Playlists') in m.calls and ('widget_resize', t, O['NAV_CF_X'] - O['NAV_TITLE_X'], 22) in m.calls
           and m.props.get((back, 'style:normal:icon')) == 'ah_nav_back' and m.props.get((m.sv, 'virtual_h')) == RGAP + 3 * PITCH,
           'Back leaves select mode (no navigation): the navbar, the title and the content are as before')
    expect(not marks_of(paint(m)[0]), 'no marks outside select mode')
    calls = tap(m, *centre(1))
    expect(('window_open', 'm1plus_songs') in calls, 'and a tap opens the playlist again')
    m.click('btn_return')
    expect('navigator_back' in m.names(), 'Back with no select mode goes back')

    # Delete: nothing marked is the message; No keeps the mode; Yes runs the stock calls in the stock order
    m = PM(lists, missing=(7,)); open_page(m); settle(m); m.setword(SEL_VEC, m.alloc(8))
    m.click('btn_more'); m.click('pl_item3'); m.calls = []
    m.click('pl_del')
    expect([c for c in m.calls if c[0] == 'toast'] == [('toast', 'msg_delplaylistfailed', 1, 2000)] and not [c for c in m.calls if c[0] in ('confirm', 'batch_delete_file')],
           'Delete with nothing marked: the stock message (msg_delplaylistfailed), no dialog, no delete')
    tap(m, *centre(1)); tap(m, *centre(3)); m.calls = []
    m.click('pl_del')
    expect([c for c in m.calls if c[0] == 'confirm'] == [('confirm', 'msg_delplaylist', 1)] and not [c for c in m.calls if c[0] in ('batch_delete_file', 'loadLocalClassList')]
           and vis(m, 'pl_bar') == (1, 1), 'No: the stock confirm dialog (kind 1, msg_delplaylist), nothing is deleted or read, select mode stays')
    m.confirm_yes = True; m.calls = []
    m.click('pl_del')
    order = [c for c in m.calls if c[0] in ('confirm', 'loadLocalClassList', 'select_recordinit', 'set_selectindex', 'batch_delete_file', 'toast')]
    expect([c[0] for c in order] == ['confirm', 'loadLocalClassList', 'select_recordinit', 'set_selectindex', 'set_selectindex', 'batch_delete_file', 'toast', 'loadLocalClassList'], f'Yes: confirm, the stock list read, the stock vector filled, batch_delete_file, the message, the page reads again ({[c[0] for c in order]})')
    bd = next(c for c in order if c[0] == 'batch_delete_file')
    expect(bd[:2] == ('batch_delete_file', O['CLASS_PLAYLISTS']) and bd[3] == m.word(SEL_VEC) and bd[4:] == (0, 0, [1, 3]) and order[1] == ('loadLocalClassList', O['CLASS_PLAYLISTS'])
           and order[2] == ('select_recordinit', len(lists)), f'batch_delete_file(0xf00b, the stock list, the stock vector, 0, 0) with rows 1 and 3 selected ({bd})')
    expect(order[-2] == ('toast', 'msg_delplaylistsuccess', 1, 2000) and vis(m, 'pl_bar') == (0, 0) and vis(m, 'btn_selall') == (0, 0) and all(vis(m, n) == (1, 1) for n in names),
           'then the success message, select mode is over and the page shows the playlists read again')
    # the stock list changed under the page (a playlist added elsewhere): nothing is deleted, the page reads again
    m = PM(lists, missing=(7,)); open_page(m); settle(m); m.setword(SEL_VEC, m.alloc(8)); m.confirm_yes = True
    m.click('btn_more'); m.click('pl_item3'); tap(m, *centre(1))
    PM.add(m, 9, 'Late', [1])
    m.calls = []
    m.click('pl_del')
    expect('batch_delete_file' not in m.names() and 'select_recordinit' not in m.names() and ('loadLocalClassList', O['CLASS_PLAYLISTS']) in m.calls and vis(m, 'pl_bar') == (0, 0),
           'a stock list that is not what the page shows (a playlist added meanwhile): nothing is deleted, the page reads again')
    m = PM(lists, missing=(7,)); open_page(m); settle(m); m.setword(SEL_VEC, m.alloc(8)); m.confirm_yes = True
    m.click('btn_more'); m.click('pl_item3'); tap(m, *centre(1))
    m.playlists[1], m.playlists[2] = m.playlists[2], m.playlists[1]   # the same playlists in another order
    m.calls = []
    m.click('pl_del')
    expect('batch_delete_file' not in m.names(), 'the same playlists in another order: nothing is deleted (the marks are of rows, not of ids)')
    m = PM(lists, missing=(7,)); open_page(m); settle(m); m.confirm_yes = True   # no selection vector (never made): no delete
    m.click('btn_more'); m.click('pl_item3'); tap(m, *centre(1)); m.calls = []
    m.click('pl_del')
    expect('batch_delete_file' not in m.names(), 'no stock selection vector: nothing is deleted')

    # list mode: a mark column left of each row, the cover and the texts 30 px to the right, taps mark
    m = PM(lists, missing=(7,)); m.fs[PL_FILE] = b'0\n'; open_page(m); settle(m)
    m.click('btn_more'); m.click('pl_item3')
    blits, texts, styles = settle(m)
    mk = marks_of(blits)
    expect([(x, y) for x, y, _ in mk] == [(O['LIST_ART_X'] + (SEL_COL - 6 - MARK) // 2, r * O['LIST_ROW_H'] + (O['LIST_ROW_H'] - MARK) // 2) for r in range(6)],
           f'list mode: a mark in a column left of every row ({mk})')
    covers = sorted(b[2][:4] for b in blits if b[2][2] == O['LIST_ART'])
    expect(all(c[0] == O['LIST_ART_X'] + SEL_COL for c in covers) and len(covers) == 6, 'the covers move right by the mark column')
    rows = [(t, r) for (t, r), s in zip(texts, styles) if s == 'label_row_title']
    expect(rows and all(r[0] == O['LIST_TEXT_X'] + SEL_COL and r[2] == O['LIST_TEXT_W'] - SEL_COL for _, r in rows), f'the texts too, 30 px narrower ({rows[:1]})')
    calls = tap(m, 150, 1 * O['LIST_ROW_H'] + 20)
    expect(('widget_set_text_utf8', m.widgets['label_title'], '1 Selected') in calls and not [c for c in calls if c[0] == 'window_open'], 'a tap on a row marks it')
    m.touch('down', 150, SCREEN_Y0 + 2 * O['LIST_ROW_H'] + 20, 5000, fn='pl_on_down'); paint(m)
    expect(not [f for f in m.fills if f[0] == O['LIST_PRESS']], 'a pressed row is not filled in select mode')
    m.touch('abort', 150, SCREEN_Y0 + 2 * O['LIST_ROW_H'] + 20, 5010, fn='pl_on_abort')
    m.click('btn_return')
    blits, texts, styles = settle(m)
    rows = [(t, r) for (t, r), s in zip(texts, styles) if s == 'label_row_title']
    expect(all(r[0] == O['LIST_TEXT_X'] and r[2] == O['LIST_TEXT_W'] for _, r in rows) and not marks_of(blits), 'leaving select mode puts the texts back at their width')

    # fallbacks: the stock Playlists page where the page cannot do it, nothing when there is nothing to select
    for what, tweak in (('the select widgets are not in the asset', lambda m: m.widgets.pop('pl_bar')), ('the Delete pill is not in the asset', lambda m: m.widgets.pop('pl_del')),
                        ('Select All is not in the asset', lambda m: m.widgets.pop('btn_selall')), ('the marks do not decode', lambda m: m.images.pop('selected'))):
        m = PM(lists); tweak(m); open_page(m); settle(m); m.click('btn_more'); m.calls = []
        m.click('pl_item3')
        expect(('stock_resume', '14') in m.calls, f'{what}: Delete Playlists opens the stock Playlists page (Home id 14), as before')
    m = PM([]); open_page(m); m.click('btn_more'); m.calls = []
    m.click('pl_item3')
    expect(('widget_set_visible', m.widgets['pl_bar'], 1) not in m.calls and 'stock_resume' not in m.names() and vis(m, 'pl_card') == (0, 0), 'with no playlist there is nothing to select: the menu closes, nothing else')
    # the page read again (back from another window) leaves select mode
    m = PM(lists, missing=(7,)); open_page(m); settle(m)
    m.click('btn_more'); m.click('pl_item3'); tap(m, *centre(1))
    fn, c = m.bound[(m.window, O['EVT_WINDOW_TO_FG'])]
    m.call(fn, a0=c, a1=0, count=60000000)
    expect(vis(m, 'pl_bar') == (0, 0) and vis(m, 'btn_selall') == (0, 0) and all(vis(m, n) == (1, 1) for n in names), 'the page read again is out of select mode (the marks were of the old list)')
    # closing frees the marks
    m.call(PSYMS['pl_on_destroy'], count=400000)
    expect(sum(1 for c in m.calls if c[0] == 'bitmap_destroy') >= 2, 'closing frees the marks')
    # the stock hit test on the asset: the bar's pill and Select All are reached where they show, nothing under the bar's top
    m = PM(lists, missing=(7,)); open_page(m); settle(m); m.click('btn_more'); m.click('pl_item3')
    root = asset_tree(UI)
    for n in ('btn_selall', 'pl_bar', 'pl_del'):
        if m.props.get((m.widgets[n], 'sensitive')) == 1: node(root, n).flags |= F_SENSITIVE
    for n in ('btn_more', 'btn_albumview', 'btn_backtoplayer'):
        if m.props.get((m.widgets[n], 'sensitive')) == 0: node(root, n).flags &= ~F_SENSITIVE
    node(root, 'view_grid').h = 3000
    expect(stock_target(m, root, 160, 450 - 32)[-1] == 'pl_del' and stock_target(m, root, 280, 25)[-1] == 'btn_selall' and stock_target(m, root, 190, 25)[-1] != 'btn_albumview',
           'in select mode the pill and Select All are hit where they show, and the hidden navbar buttons take no touch')


def run(ctx):
    expect, page = ctx.expect, ctx.page
    row = next(i for i, r in enumerate(page.rows) if r.label == 'Playlists')
    expect(page.rows[row].action == pod_pages.ACT_PLAYLISTS, 'the menu\'s Playlists row opens our page (ACT_PLAYLISTS)')
    expect(pod_pages.PLAYLISTS in pod_pages.PAGES and pod_pages.PLAYLISTS.key == 'm1plus_playlists', 'the page is in the page table')
    on_row, rows0 = PSYMS['on_row'], PSYMS['pod_rows_0']

    # 1. The asset: the Albums page's structure with a "..." button in place of the toggles, and the hidden popup
    tree = awtk_ui.parse(open(UI, 'rb').read())
    lv, sv, grid, bar = tree.find('playlists_listview'), tree.find('playlists_scrollview'), tree.find('view_grid'), tree.find('scroll_bar_m')
    expect(lv.type == 'list_view' and sv.type == 'scroll_view' and sv.children == [grid] and lv.children[:1] == [sv] and bar in lv.children
           and (lv.x, lv.y, lv.w, lv.h) == (0, 50, 320, VIEW_H) and (sv.w, bar.x, bar.w) == (SVW, SVW, 10),
           'the body is list_view > scroll_view > view_grid with the stock mobile scroll bar, as the Albums page')
    more = tree.find('btn_more')
    tog = tree.find('btn_albumview')
    expect(more is not None and (more.x, more.w, more.h) == (O['NAV_CF_X'], O['NAV_CF_W'], O['NAV_H']) and more.get('style') == 'img_btn_style'
           and more.get('style:normal:icon') == 'pod_nav_more' and more.get('style:pressed:icon') == 'pod_nav_more_down'
           and tree.find('label_title').x + tree.find('label_title').w == more.x == 168 and more.x + more.w == tog.x,
           'the "..." button sits at the Albums page\'s Cover Flow button (x 168), flush left of the toggle; the title ends at its edge')
    expect((tog.x, tog.w, tog.h) == (O['NAV_VIEW_X'], O['NAV_VIEW_W'], O['NAV_H']) and tog.get('style:normal:icon') == 'pod_nav_list'
           and tog.get('style:pressed:icon') == 'pod_nav_list_down' and tog.x + tog.w == tree.find('btn_backtoplayer').x,
           'the view toggle is the Albums page\'s: x 214, 46x50, the list glyph (the view a tap switches to), flush left of Now Playing')
    for nm, px, col in (('label_row_title', 21, '#FFFFFF'), ('label_row_sub', 18, '#AAAAAA')):
        w = tree.find(nm)
        expect(w is not None and w.get('visible') == 'false' and w.get('sensitive') == 'false' and w.get('style:normal:font_size') == str(px)
               and w.get('style:normal:text_color') == col, f'{nm}: a hidden label carrying the list rows\' {px} px {col} text style')
    expect(os.path.isfile(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/images/xx/pod_nav_more.png'))
           and os.path.isfile(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/images/xx/pod_nav_more_down.png')), 'its glyph images are in the tree')
    for nm, px, col in (('label_grid_title', 18, '#FFFFFF'), ('label_grid_sub', 15, '#AAAAAA')):
        w = tree.find(nm)
        expect(w is not None and w.get('visible') == 'false' and w.get('sensitive') == 'false' and w.get('style:normal:font_size') == str(px)
               and w.get('style:normal:text_color') == col, f'{nm}: a hidden label carrying the {px} px {col} text style (the Albums grid\'s)')
    scrim, card = tree.find('pl_scrim'), tree.find('pl_card')
    expect(scrim.type == 'button' and (scrim.x, scrim.y, scrim.w, scrim.h) == (0, 0, 320, 450) and card.type == 'view'
           and all(w.get('visible') == 'false' and w.get('sensitive') == 'false' for w in (scrim, card)),
           'the popup\'s scrim (the whole window) and card start hidden AND insensitive (hit tests ignore visible)')
    kids = tree.children
    expect(kids.index(scrim) > kids.index(lv) and kids.index(scrim) > kids.index(tree.find('navigationbar_view')) and kids.index(card) == kids.index(scrim) + 1,
           'the scrim and the card come after the navbar and the list: they lie over everything')
    items = [tree.find(f'pl_item{i}') for i in range(4)]
    expect(all(it is not None and it.type == 'button' and it in card.children and (it.y, it.h, it.w) == (50 * i, 50, card.w) for i, it in enumerate(items))
           and card.h == 200 and card.y + card.h <= 450 and card.x + card.w <= 320,
           'four 50 px row buttons fill the 200 px card edge to edge (Now Playing\'s More sheet\'s rows, no padding: the last row as tall as the others)')
    labels = [next(c for c in it.children if c.type == 'hscroll_label') for it in items]
    labs = [pod_i18n.shown_english(lab) for lab in labels]
    expect(labs == list(pod_pages.PLAYLIST_MENU) == ['New playlist', 'Import playlist', 'Export playlist', 'Delete Playlists'], f'menu rows: {labs}')
    expect(all(c.get('sensitive') == 'false' for it in items for c in it.children), 'the glyphs and labels in the rows are insensitive (the row button takes the tap)')
    import mod_icons
    icons = [next((c for c in it.children if c.type == 'image'), None) for it in items]
    xx = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/images/xx')
    expect([ic and ic.get('image') for ic in icons] == [n for n, _ in mod_icons.PL_MENU_ICONS] == ['pl_ic_new', 'pl_ic_import', 'pl_ic_export', 'pl_ic_delete']
           and [g for _, g in mod_icons.PL_MENU_ICONS] == ['list-plus', 'file-input', 'file-output', 'trash']
           and all((ic.x, ic.y, ic.w, ic.h, ic.name) == (16, 15, 20, 20, f'pl_icon{i}') for i, ic in enumerate(icons))
           and all((lab.x, lab.w) == (48, card.w - 64) for lab in labels),
           'every row: its 20 px glyph at x 16 (centred where the sheet\'s 24 px glyphs are), vertically centred (New list-plus, Import file-input, Export file-output, Delete trash), the label from x 48 to 16 px before the edge')
    expect(all(open(os.path.join(xx, n + '.png'), 'rb').read() == open(os.path.join(mod_icons.PNG, n + '.png'), 'rb').read() for n, _ in mod_icons.PL_MENU_ICONS),
           'the four glyph images are in the tree, the committed PNGs')
    expect(all(it.get(f'style:{st}:bg_color') == ('#FFFFFF10' if st == 'pressed' else '#00000000') and it.get(f'style:{st}:text_color') == '#FFFFFF'
               and it.get(f'style:{st}:border') == ('top' if i else 'none') and it.get(f'style:{st}:border_color') == ('#FFFFFF22' if i else '#00000000')
               for i, it in enumerate(items) for st in pod_ui.STATES),
           'rows are transparent on the glass, pressed 6 % white, a 13 % white hairline above every row but the first (Now Playing\'s More sheet\'s rows)')
    glass_checks(expect, tree, scrim, card, items)
    # the labels fit their room in all 13 languages (19 px in the shipped font)
    import awtk_strings
    from awtk_text import Ttf, StbText
    raw = os.path.join(WORK, 'rootfs', 'release', 'assets', 'default', 'raw')
    font = Ttf(os.path.join(raw, 'fonts', 'default.ttf'))
    built = {loc: dict(awtk_strings.load(os.path.join(raw, 'strings', loc + '.bin'))) for loc in pod_i18n.LOCALES}
    over = [(loc, k, w) for loc in pod_i18n.LOCALES for k in ('playlist_create', 'playlist_import', 'playlist_export', 'Delete Playlists')
            for w in [StbText(font, pod_ui.PL_LABEL_PX).layout(built[loc][k])[1]] if w > labels[0].w]
    expect(not over, f'every menu label fits its {labels[0].w} px room in all 13 languages ({over[:4]})')
    over = [(loc, w) for loc in pod_i18n.LOCALES for w in [StbText(font, 20).layout(built[loc]['No playlists'])[1]] if w > tree.find('label_status').w]
    expect(not over, f'"No playlists" fits the status line in all languages ({over})')
    over = [(loc, w) for loc in pod_i18n.LOCALES for w in [StbText(font, 20).layout(built[loc]['Playlists'])[1]] if tree.find('label_title').x + w > more.x]
    expect(not over, f'the title "Playlists" ends before the "..." button in all languages ({over})')

    # 2. The menu row opens the page; a window that will not open leaves the stock Playlists page (Home id 14)
    m = PM([(1, 'Mix', [0, 1])])
    m.call(on_row, a0=rows0 + 12 * row, count=60000000)
    expect(('window_open', 'm1plus_playlists') in m.calls and 'stock_resume' not in m.names(), 'the Playlists row opens our page')
    m = PM([(1, 'Mix', [0])]); m.window = 0
    open_page(m)
    expect(('stock_resume', '14') in m.calls, 'if the window will not open the row opens the stock Playlists page')
    m = PM([(1, 'Mix', [0])])
    m.widgets.pop('pl_card')
    open_page(m)
    expect(('navigator_back',) in m.calls and not any(c[0] == 'loadLocalClassList' for c in m.calls), 'an asset that is not ours: the page leaves again')

    # 3. Opening reads the stock playlists (class 0xf00b) and the page binds its buttons; nothing is shown or decoded before the first tick
    lists = [(1, 'Empty', []), (2, 'One', [0]), (3, 'Two', [1, 2, 1, 2]), (4, 'Three', [3, 4, 5]), (5, 'Many', [0, 1, 2, 3, 4, 5, 6]), (6, 'Bare', [7])]
    m = PM(lists, missing=(7,))
    calls = open_page(m)
    expect(('window_open', 'm1plus_playlists') in calls and [c for c in calls if c[0] == 'loadLocalClassList'] == [('loadLocalClassList', O['CLASS_PLAYLISTS'])],
           'opening runs the playlist query once and not the song queries (those are the loader\'s, one a tick)')
    expect(all((m.widgets[n], O['EVT_CLICK']) in m.bound for n in ('btn_return', 'btn_backtoplayer', 'btn_more', 'btn_albumview', 'pl_scrim', 'pl_item0', 'pl_item1', 'pl_item2', 'pl_item3'))
           and (m.widgets['view_grid'], O['EVT_AFTER_PAINT']) in m.bound and (m.window, O['EVT_WINDOW_TO_FG']) in m.bound,
           'the buttons, the paint and the window\'s to-foreground event are bound')
    expect(vis(m, 'view_grid') == (1, 1) and vis(m, 'label_status')[0] == 0 and vis(m, 'pl_scrim') == (0, 0) and vis(m, 'pl_card') == (0, 0),
           'the grid shows; the status line, the scrim and the card are hidden and insensitive')
    h = m.word(m.widgets['view_grid'] + 0xc)
    expect(h == RGAP + 3 * PITCH and m.props.get((m.sv, 'virtual_h')) == h, f'6 playlists are 3 rows: the content is {h} px and the scroll_view is told')
    expect(not [c for c in m.calls if c[0] == 'widget_load_image' and c[1] not in ('p_default', 'unselect', 'selected')], 'no cover is decoded in the open (only the placeholder disc)')

    # 4. The loader: one playlist read or one cover source decoded a tick; the mosaics (cells 4 and 5 are in the third row: scrolled to)
    blits, texts, styles = settle(m)
    expect(m.most_per_tick <= 1, f'at most one cover source decoded per tick (saw {m.most_per_tick})')
    top = m.word(m.widgets['view_grid'] + 0xc) - VIEW_H
    scroll_to(m, top)
    blits2, texts2, styles2 = settle(m)
    expect(len(m.bitmaps) <= TILES + 1 and m.most_per_tick <= 1, f'the bitmaps alive stay within the tile ring and the placeholder ({len(m.bitmaps)})')
    cover = {i: cell_blit(blits, i) for i in range(4)}
    cover.update({i: cell_blit(blits2, i, top) for i in (4, 5)})
    holder = None
    for i, (pid, name, songs) in enumerate(lists):
        distinct = []
        for a in songs:
            if a not in distinct and a != 7: distinct.append(a)
        distinct = distinct[:4]
        b = cover[i]
        expect(b is not None, f'{name}: its cover is painted')
        if b is None: continue
        q = quadrants(m, b)
        w = want_mosaic(distinct)
        if w is None:
            holder = holder or b
            expect(near(q[0], GREY_DISC) and len(set(q)) == 1 and b == holder,
                   f'{name}: {len(songs)} songs, no album with a cover: the one placeholder disc ({[hex(x) for x in q]})')
        else:
            expect(all(near(a, b2) for a, b2 in zip(q, w)), f'{name}: {len(distinct)} album(s) fill the quadrants {[f"{x:#010x}" for x in w]} (got {[f"{x:#010x}" for x in q]})')
    texts_by = {}
    for f, off in (((texts, styles), 0), ((texts2, styles2), top)):
        for (text, rect), st in zip(*f): texts_by.setdefault(st, {})[(rect[1] + off - RGAP) // PITCH * COLS + (rect[0] - MARGIN) // CPITCH] = text
    names = {'label_grid_title': {i: l[1] for i, l in enumerate(lists)},
             'label_grid_sub': {i: ('1 track' if len(l[2]) == 1 else f'{len(l[2])} tracks') for i, l in enumerate(lists)}}
    expect(texts_by.get('label_grid_title') == names['label_grid_title'] and texts_by.get('label_grid_sub') == names['label_grid_sub'],
           f'each cell shows the playlist\'s name and its track count ({texts_by})')
    expect(len(set(quadrants(m, cover[4]))) == 4, 'a playlist of seven albums shows its first four, all different')

    # 5. The scan reads at most PL_SCAN songs and takes the first four albums that have a cover (missing covers are skipped)
    songs = [7] * 10 + [0, 7, 1, 2, 3, 4]
    m = PM([(1, 'Skip', songs)], missing=(7,)); open_page(m)
    blits, _, _ = settle(m)
    q = quadrants(m, cell_blit(blits, 0))
    expect(all(near(a, b2) for a, b2 in zip(q, want_mosaic([0, 1, 2, 3]))), 'albums with no cover file are skipped: the first four with one fill the mosaic')
    m = PM([(1, 'Far', [7] * O['PL_SCAN'] + [0, 1])], missing=(7,)); open_page(m)
    blits, _, _ = settle(m)
    expect(near(pixel(m, cell_blit(blits, 0), 36, 36), GREY_DISC), f'only the first {O["PL_SCAN"]} songs are looked at: covers after them do not count')

    # 6. A track of a compilation carries another artist than the album's cache key: the library album of that name is found
    m = PM([(1, 'Comp', [0, 1])], other_artist=(0, 1)); open_page(m)
    blits, _, _ = settle(m)
    expect(all(near(a, b2) for a, b2 in zip(quadrants(m, cell_blit(blits, 0)), want_mosaic([0, 1]))), 'songs by another artist find their album\'s cover through the library list')
    # ... and only once per album: a song whose key was looked at already (its cover is in, or it had none) does not walk the library list again
    m = PM([(1, 'Repeat', [30] * 20 + [39] * 10)], albums=40, missing=(39,)); open_page(m)
    blits, _, _ = settle(m)
    reads = sum(n for h, n in m.deque_reads.items() if len(m.deques.get(h, [])) == 40)
    expect(reads <= 40, f'repeated albums look the library up once: one pass for the coverless album, none for the repeats ({reads} reads)')
    expect(all(near(a, b2) for a, b2 in zip(quadrants(m, cell_blit(blits, 0)), want_mosaic([30]))), 'the repeated album still fills the tile')

    # 7. Tap: the playlist opens in our Songs page (patch/songs.c songs_open_playlist; test/pod/songs.py lists_tests has the page); a Songs window that will not
    #    open leaves the stock songs page (allmusic_page, class 0xff13) with its id in classinfo[1] and its name as the title
    m = PM(lists, missing=(7,)); open_page(m); settle(m)
    calls = tap(m, MARGIN + 40, RGAP + 40)
    expect(('window_open', 'm1plus_songs') in calls and not [c for c in calls if c[0] == 'navigator_to_with_context' and c[1] == 'allmusic_page'],
           'a tap opens the playlist in our Songs page, not the stock one')
    m = PM(lists, missing=(7,)); m.windows['m1plus_songs'] = 0; open_page(m); settle(m)
    for i in (0, 3, 5):
        x, y = MARGIN + (i % COLS) * CPITCH + 40, RGAP + (i // COLS) * PITCH + 40
        calls = tap(m, x, y)
        opened = [c for c in calls if c[0] == 'navigator_to_with_context' and c[1] == 'allmusic_page']
        expect(opened == [('navigator_to_with_context', 'allmusic_page', O['CLASS_PLAYLIST_SONGS'], lists[i][0], lists[i][1])],
               f'a tap on cell {i} opens playlist {lists[i][0]} ({lists[i][1]!r}) in the Songs page ({opened})')
    calls = tap(m, MARGIN + 40, RGAP + 40, dx=O['SC_DRAG_PX'] + 2)
    expect(not [c for c in calls if c[0] == 'navigator_to_with_context'], 'a release past the drag threshold opens nothing')
    calls = tap(m, MARGIN + COVER + 3, RGAP + 40)
    expect(not [c for c in calls if c[0] == 'navigator_to_with_context'], 'the gap between the columns is dead')
    m.touch('down', MARGIN + 40, SCREEN_Y0 + RGAP + 40, 1000, fn='pl_on_down'); m.touch('abort', MARGIN + 40, SCREEN_Y0 + RGAP + 40, 1010, fn='pl_on_abort')
    m.touch('up', MARGIN + 40, SCREEN_Y0 + RGAP + 40, 1080, fn='pl_on_up')
    expect(not [c for c in m.calls if c[0] == 'navigator_to_with_context'], 'the scroll_view\'s abort forgets the press')

    # 8. Nothing is decoded while the scroll_view moves
    m = PM(lists, missing=(7,)); open_page(m)
    m.u.mem_write(m.sv + O['SC_PRESSED'], bytes([1, 1]))
    calls = tick(m)
    expect(not [c for c in calls if c[0] in ('widget_load_image', 'loadLocalClassList')] and any(c[0] == 'timer_add' for c in calls),
           'while a finger drags the list the loader reads and decodes nothing and keeps polling')
    m.u.mem_write(m.sv + O['SC_PRESSED'], bytes([0, 0]))
    calls = tick(m)
    expect(any(c[0] == 'loadLocalClassList' for c in calls), 'and goes on the tick after')

    # 8b. Behind another window (the stock songs page of the playlist just tapped) the loader stops: a scan sets classinfo[1] and replaces
    # *pdeq_showlist, the list that page draws its rows from and plays
    m = PM(lists, missing=(7,)); open_page(m)
    fn, c = m.bound[(m.window, O['EVT_WINDOW_TO_BG'])]
    m.call(fn, a0=c, a1=0, count=4000000)
    expect(any(c_[0] == 'timer_remove' for c_ in m.calls), 'going behind another window removes the loader\'s timer before a scan is done')
    scroll_to(m, 0)
    expect(not [c_ for c_ in m.calls if c_[0] in ('timer_add', 'loadLocalClassList')], 'a scroll event while behind (a fling ending) arms no loader')
    fn, c = m.bound[(m.window, O['EVT_WINDOW_TO_FG'])]
    m.call(fn, a0=c, a1=0, count=60000000)
    expect(any(c_[0] == 'timer_add' and c_[1] == PSYMS['pl_on_load'] for c_ in m.calls), 'back in front the page reads again and the loader runs')

    # 9. Back in the front: the playlists are read again (a playlist may have been edited in the stock page)
    m = PM(lists[:2]); open_page(m); settle(m)
    PM.add(m, 7, 'Fresh', [5, 6])
    fn, c = m.bound[(m.window, O['EVT_WINDOW_TO_FG'])]
    m.call(fn, a0=c, a1=0, count=60000000)
    expect(('loadLocalClassList', O['CLASS_PLAYLISTS']) in m.calls, 'the window coming to the front runs the playlist query again')
    blits, texts, styles = settle(m)
    titles = [t for (t, r), s in zip(texts, styles) if s == 'label_grid_title']
    expect(titles == ['Empty', 'One', 'Fresh'], f'the new list is what the page shows ({titles})')
    expect(all(near(a, b2) for a, b2 in zip(quadrants(m, cell_blit(blits, 2)), want_mosaic([5, 6]))), 'and the new playlist\'s mosaic is made')
    m.playlist_songs[2] = m.playlist_songs[2][:0]
    m.call(fn, a0=c, a1=0, count=60000000)
    blits, texts, styles = settle(m)
    subs = [t for (t, r), s in zip(texts, styles) if s == 'label_grid_sub']
    expect(subs[1:2] == ['0 tracks'] and near(quadrants(m, cell_blit(blits, 1))[0], GREY_DISC),
           f'a playlist emptied in the stock page shows 0 tracks and the placeholder after the next visit ({subs})')

    # 10. The empty state: a centred line, no grid; the menu is still there
    m = PM([]); open_page(m)
    expect(vis(m, 'view_grid')[0] == 0 and vis(m, 'label_status')[0] == 1 and ('widget_set_tr_text', m.widgets['label_status'], 'No playlists') in m.calls,
           'with no playlist the grid is hidden and the status line says "No playlists"')
    m.click('btn_more')
    expect(vis(m, 'pl_card') == (1, 1) and vis(m, 'pl_scrim') == (1, 1), 'the "..." menu opens on the empty page')

    # 11. The menu: open, close by the button, by the scrim, by an action; the actions run the stock code
    m = PM(lists, missing=(7,)); open_page(m); settle(m)
    m.click('btn_more')
    expect(vis(m, 'pl_card') == (1, 1) and vis(m, 'pl_scrim') == (1, 1), 'the "..." button shows the card and the scrim (visible and sensitive)')
    m.click('btn_more')
    expect(vis(m, 'pl_card') == (0, 0) and vis(m, 'pl_scrim') == (0, 0), 'and a second tap closes them (hidden and insensitive)')
    m.click('btn_more'); m.click('pl_scrim')
    expect(vis(m, 'pl_card') == (0, 0) and vis(m, 'pl_scrim') == (0, 0), 'a tap on the scrim closes the menu')
    # New playlist: the stock keyboard dialog, createPlayListItem on the freshly read stock list, then the page reads again
    m.click('btn_more'); m.calls = []
    m.click('pl_item0')
    names_ = m.names()
    expect(vis(m, 'pl_card') == (0, 0) and ('navigator_to_with_context', 'dialog/kbaddplaylist_dialog', 'Mix') in m.calls
           and ('createPlayListItem', 'Mix', len(lists)) in m.calls and 'stock_resume' not in names_,
           'New playlist: the menu closes, the stock keyboard dialog, createPlayListItem(stock list, name)')
    order = [c for c in m.calls if c[0] in ('navigator_to_with_context', 'loadLocalClassList', 'createPlayListItem')]
    expect([c[0] for c in order] == ['navigator_to_with_context', 'loadLocalClassList', 'createPlayListItem', 'loadLocalClassList'] and order[1][1] == order[3][1] == O['CLASS_PLAYLISTS'],
           f'... the stock list is read before the playlist is made and the page reads again after ({[c[0] for c in order]})')
    for ret, key in ((-1, 'msg_playlistfull'), (-2, 'msg_playlistexist')):
        m.create_ret = ret; m.calls = []
        m.click('pl_item0')
        expect([c for c in m.calls if c[0] == 'toast'] == [('toast', key, 1, 2000)], f'a playlist that cannot be made says {key} in the stock message box ({[c for c in m.calls if c[0] == "toast"]})')
    m.create_ret = 5; m.dialog_name = None; m.calls = []
    m.click('pl_item0')
    expect(not [c for c in m.calls if c[0] == 'createPlayListItem'], 'a cancelled keyboard dialog creates nothing')
    # Import / Export: the stock click handlers, in the normal (not multi-select) mode, then the page reads again
    for item, handler in (('pl_item1', 'stock_playlist_import'), ('pl_item2', 'stock_playlist_export')):
        m.setword(NAV_STATUS, 1); m.calls = []
        m.click(item)
        expect([c for c in m.calls if c[0] == handler] == [(handler, 0)] and m.word(NAV_STATUS) == 0
               and ('loadLocalClassList', O['CLASS_PLAYLISTS']) in m.calls, f'{item}: the stock {handler[15:]} handler runs with the list in normal mode, then the page reads again')
    # Delete Playlists: select mode on this page (select_tests below); the stock Playlists page only where the page cannot do it
    m.calls = []
    m.click('pl_item3')
    expect('stock_resume' not in m.names() and vis(m, 'pl_card') == (0, 0) and vis(m, 'pl_bar') == (1, 1), 'Delete Playlists starts select mode on this page (select_tests); the stock page stays closed')
    select_tests(expect, lists)

    # 11b. The card fits the language: the glyph's 48 px + its widest label + 16 px, 180..292, its right edge at 314; rows and labels follow
    raw = os.path.join(WORK, 'rootfs', 'release', 'assets', 'default', 'raw')
    font = Ttf(os.path.join(raw, 'fonts', 'default.ttf'))
    keys = ('playlist_create', 'playlist_import', 'playlist_export', 'Delete Playlists')
    def fit(m):
        moves = [c[2:] for c in m.calls if c[0] == 'widget_move' and c[1] == m.widgets['pl_card']]
        sizes = {n: c[2:] for c in m.calls if c[0] == 'widget_resize' for n in m.widgets if m.widgets[n] == c[1] and n.startswith('pl_')}
        return (moves[-1] if moves else None), sizes
    def menu_for(texts, measure):
        m = PM(lists); open_page(m)
        for i, t in enumerate(texts): m.label_text[m.widgets[f'pl_label{i}']] = t
        m.measure = measure; m.calls = []
        m.click('btn_more')
        return m
    for loc, want in (('en_US', 180), ('zh_CN', 180), ('sp_ES', None), ('ja_JP', None), ('ge_DE', None)):
        texts = [built[loc][k] for k in keys]
        widths = [StbText(font, pod_ui.PL_LABEL_PX).layout(t)[1] for t in texts]
        w = want or max(widths) + 64
        m = menu_for(texts, lambda t: StbText(font, pod_ui.PL_LABEL_PX).layout(t)[1])
        pos, sizes = fit(m)
        expect(pos == (314 - w, 44) and sizes.get('pl_card') == (w, 200) and all(sizes.get(f'pl_item{i}') == (w, 50) and sizes.get(f'pl_label{i}') == (w - 64, 50) for i in range(4))
               and 180 <= w <= 292 and max(widths) <= w - 64 and vis(m, 'pl_card') == (1, 1),
               f'{loc}: the card {w} px wide (glyph room 48 + labels up to {max(widths)} px + 16, at least 180), x {314 - w}..314; rows {w}, labels {w - 64} ({pos}, {sizes.get("pl_card")})')
    m = menu_for(pod_pages.PLAYLIST_MENU, lambda t: 300)
    expect(fit(m)[0] == (22, 44) and fit(m)[1].get('pl_card') == (292, 200), f'a label wider than the room keeps the widest card (292 px, its ellipsis): {fit(m)}')
    m = menu_for(pod_pages.PLAYLIST_MENU, None)
    expect(fit(m) == (None, {}) and vis(m, 'pl_card') == (1, 1), 'a label that cannot be measured leaves the asset\'s card (292 px), and the menu opens')
    m = PM(lists); m.widgets.pop('pl_label2'); open_page(m); m.measure = lambda t: 50; m.calls = []
    m.click('btn_more')
    expect(fit(m) == (None, {}) and vis(m, 'pl_card') == (1, 1), 'a missing label leaves the asset\'s card, and the menu opens')
    m = menu_for(pod_pages.PLAYLIST_MENU, lambda t: 100)
    m.click('btn_more'); m.measure = lambda t: 200; m.calls = []
    m.click('btn_more')
    expect(fit(m)[1].get('pl_card') == (264, 200) and fit(m)[0] == (50, 44), f'every open measures again (a language changed meanwhile): {fit(m)}')

    # 12. Closing frees everything
    m = PM(lists, missing=(7,)); open_page(m); settle(m)
    m.calls = []
    fn, c = m.bound[(m.window, O['EVT_DESTROY'])]
    m.call(fn, a0=c, a1=0, count=20000000)
    alive = len(m.bitmaps)
    expect(alive == 0, f'closing the page destroys every tile and the placeholder ({alive} left)')
    open_page(m)
    expect(('window_open', 'm1plus_playlists') in m.calls, 'and the page opens again')

    # 13. List mode (the Albums page's): 64 px rows, a 52 px mosaic (quadrants of 26 px), the name and the count in the list's two text styles
    ROW, LART, LAX, LAY = O['LIST_ROW_H'], O['LIST_ART'], O['LIST_ART_X'], O['LIST_ART_Y']
    TX, TW, TY, TH, SY, SH = O['LIST_TEXT_X'], O['LIST_TEXT_W'], O['LIST_TITLE_Y'], O['LIST_TITLE_H'], O['LIST_SUB_Y'], O['LIST_SUB_H']
    glyph = lambda m: m.props.get((m.widgets['btn_albumview'], 'style:normal:icon'))
    m = PM(lists, missing=(7,)); open_page(m)
    expect(glyph(m) == 'pod_nav_list' and m.fs.get(PL_FILE) is None, 'with no setting the page opens as the grid (the toggle shows the list glyph)')
    m = PM(lists, missing=(7,)); m.fs[PL_FILE] = b'0\n'; calls = open_page(m)
    expect(glyph(m) == 'pod_nav_grid' and m.props.get((m.widgets['btn_albumview'], 'style:pressed:icon')) == 'pod_nav_grid_down',
           'the saved "0" opens the list mode: the toggle shows the grid glyph')
    expect(('bitmap_create_ex', LART, LART) in calls and not any(c[:3] == ('bitmap_create_ex', COVER, COVER) for c in calls), 'its covers are 52 px bitmaps')
    h = m.word(m.widgets['view_grid'] + 0xc)
    expect(h == len(lists) * ROW and m.props.get((m.sv, 'virtual_h')) == h, f'the content is {len(lists)} rows of {ROW} px = {h} and the scroll_view is told')
    blits, texts, styles = settle(m)
    for i, (pid, name, songs) in enumerate(lists):
        b = next((x[0] for x in blits if x[2] == (LAX, i * ROW + LAY, LART, LART)), None)
        distinct = []
        for a in songs:
            if a not in distinct and a != 7: distinct.append(a)
        w = want_mosaic(distinct[:4])
        q = quadrants(m, b, LART) if b else []
        expect(b is not None and (all(near(x, y) for x, y in zip(q, w)) if w else len(set(q)) == 1 and near(q[0], GREY_DISC)),
               f'row {i} ({name}): its 52 px cover is the {len(distinct[:4])}-album mosaic in 26 px quadrants ({[hex(x) for x in q]})')
    got = {st: {r[1] // ROW: t for (t, r), s in zip(texts, styles) if s == st} for st in ('label_row_title', 'label_row_sub')}
    expect(got['label_row_title'] == {i: l[1] for i, l in enumerate(lists)}
           and got['label_row_sub'] == {i: ('1 track' if len(l[2]) == 1 else f'{len(l[2])} tracks') for i, l in enumerate(lists)}, f'each row shows the name and the count ({got})')
    expect(all(r[0] == TX and r[2] == TW and (r[1] % ROW, r[3]) in ((TY, TH), (SY, SH)) for (t, r) in texts), 'the texts are in the list rows\' rects')
    expect(sum(1 for f in m.fills if f[0] == O['LIST_HAIR']) == len(lists) and not [f for f in m.fills if f[0] == O['LIST_PRESS']], 'a hairline closes each row, no row is pressed')
    #     a tap on a row (any x) opens its playlist; the press fills the row until the release
    m.touch('down', 300, SCREEN_Y0 + 3 * ROW + 20, 1000, fn='pl_on_down')
    blits, texts, styles = paint(m)
    expect([f for f in m.fills if f[0] == O['LIST_PRESS']] == [(O['LIST_PRESS'], 0, 3 * ROW, 320, ROW - 1)], 'a finger down fills its row with the pressed colour')
    m.windows['m1plus_songs'] = 0   # (our Songs page will not open: the stock one shows which playlist the tap opened)
    m.touch('up', 300, SCREEN_Y0 + 3 * ROW + 20, 1080, fn='pl_on_up')
    opened = [c for c in m.calls if c[0] == 'navigator_to_with_context' and c[1] == 'allmusic_page']
    expect(('window_open', 'm1plus_songs') in m.calls and opened == [('navigator_to_with_context', 'allmusic_page', O['CLASS_PLAYLIST_SONGS'], lists[3][0], lists[3][1])],
           f'a tap on row 3 opens its playlist ({opened})')
    paint(m)
    expect(not [f for f in m.fills if f[0] == O['LIST_PRESS']], 'and the fill is gone')
    calls = tap(m, 100, 5 * ROW + 70)
    expect(not [c for c in calls if c[0] == 'navigator_to_with_context'], 'below the last row nothing opens')
    m.touch('down', 40, SCREEN_Y0 + 20, 1000, fn='pl_on_down'); m.touch('abort', 40, SCREEN_Y0 + 20, 1010, fn='pl_on_abort'); paint(m)
    expect(not [f for f in m.fills if f[0] == O['LIST_PRESS']], 'the scroll_view\'s abort clears the pressed row')
    #     the toggle: both ways in place, saved, the first playlist in view kept
    many = [(i + 1, f'P{i}', [i % 7]) for i in range(12)]
    m = PM(many); open_page(m); settle(m)
    scroll_to(m, 300); first_grid = 2
    m.calls = []; m.click('btn_albumview', count=60000000)
    expect(glyph(m) == 'pod_nav_grid' and m.fs.get(PL_FILE) == b'0\n' and not [c for c in m.calls if c[0] in ('window_open', 'navigator_to_with_context', 'window_close')],
           'the toggle switches to the list in place and saves "0"')
    expect(m.word(m.sv + SC_YOFF) == first_grid * ROW and m.word(m.widgets['view_grid'] + 0xc) == 12 * ROW and m.props.get((m.sv, 'virtual_h')) == 12 * ROW,
           'the first playlist in view stays at the top; the content is 12 rows')
    blits, texts, styles = settle(m)
    expect(('bitmap_create_ex', LART, LART) in m.calls or any(m.bitmaps[b][1] == LART for b in m.bitmaps), 'the tiles were remade at 52 px')
    tiles_ = [b for b in m.bitmaps if m.bitmaps[b][1] != MARK]   # (the two select marks are 26 px and live as long as the page)
    expect(all(m.bitmaps[b][1] == LART for b in tiles_) and len(tiles_) <= TILES + 1, 'no 144 px tile survives the switch; the ring is bounded')
    m.calls = []; m.click('btn_albumview', count=60000000)
    expect(glyph(m) == 'pod_nav_list' and m.fs.get(PL_FILE) == b'1\n' and m.word(m.sv + SC_YOFF) == first_grid // COLS * PITCH == 0 + 2 // COLS * PITCH,
           'back to the grid: "1" saved, the glyph back, the first playlist in view kept')
    settle(m)
    expect(all(m.bitmaps[b][1] in (COVER, MARK) for b in m.bitmaps), 'and the tiles are 144 px again')
    #     the choice survives a re-open, and is the Albums page's own file apart
    m.click('btn_albumview', count=60000000)
    fn, c = m.bound[(m.window, O['EVT_DESTROY'])]
    m.call(fn, a0=c, a1=0, count=20000000)
    open_page(m)
    expect(glyph(m) == 'pod_nav_grid' and PL_FILE != '/mnt/data/m1plus-albums', 'the list mode is remembered when the page is opened again, in its own file')
    m.fs['/mnt/data/m1plus-albums'] = b'1\n'; m.fs[PL_FILE] = b'junk'
    fn, c = m.bound[(m.window, O['EVT_DESTROY'])]
    m.call(fn, a0=c, a1=0, count=20000000)
    open_page(m)
    expect(glyph(m) == 'pod_nav_list', 'garbage in the file is the grid')
    #     the loader rules hold in the list: one step a tick, nothing while the list is dragged
    m = PM(many); m.fs[PL_FILE] = b'0\n'; open_page(m)
    m.u.mem_write(m.sv + O['SC_PRESSED'], bytes([1, 1]))
    calls = tick(m)
    expect(not [c for c in calls if c[0] in ('widget_load_image', 'loadLocalClassList')], 'the list mode decodes and reads nothing while the list is dragged')
    m.u.mem_write(m.sv + O['SC_PRESSED'], bytes([0, 0]))
    settle(m)
    expect(m.most_per_tick <= 1, 'and one cover source at most a tick')
    # the menu works in the list mode too
    m.click('btn_more')
    expect(vis(m, 'pl_card') == (1, 1), 'the "..." menu opens in the list mode')

    # The navbar's fade (img_nb_fade, built hidden) is shown only while the list is scrolled; insensitive throughout; without the widget nothing happens.
    for mode in ('1', '0'):
        m = PM(many); m.fs[PL_FILE] = (mode + '\n').encode()
        fade = Machine.widget(m, 'img_nb_fade'); m.props[(fade, 'visible')] = 0
        state = lambda: (m.props.get((fade, 'visible')), m.props.get((fade, 'sensitive'), 0))
        open_page(m)
        s = [state()]
        for v in (1, 300, 0):
            scroll_to(m, v); s.append(state())
        expect(s == [(0, 0), (1, 0), (1, 0), (0, 0)], f'{"grid" if mode == "1" else "list"}: the fade is hidden at rest, shown (insensitive) when scrolled, hidden again back at 0 ({s})')
        scroll_to(m, 300); m.click('btn_albumview', count=60000000)
        expect(state() == ((1, 0) if m.word(m.sv + SC_YOFF) > 0 else (0, 0)), f'a mode switch: the fade follows the new offset ({m.word(m.sv + SC_YOFF)}, {state()})')
    m = PM(many); open_page(m); scroll_to(m, 300)
    expect(m.word(m.sv + SC_YOFF) == 300, 'no fade widget: the page opens and scrolls as before')
