"""The Queue page (patch/queuepage.c, docs/modules/queue.md): our own page in place of the stock queue drawer. The built asset (the list that is the whole window, the header's
widgets and the icon-only mode buttons at the numbers of patch/offsets.inc, the glass Back last, touches by demo's own hit test), Now Playing's queue button (the click handler bound
after the stock init and what each of its answers does), the open and its fallbacks to the stock drawer (kill switch, empty queue, streams, a window that will not open, a foreign
asset), the header (the playing track, the cover from the cache), Up Next (the tracks after the playing one, texts, covers, the press fill, the hairline, the grey line when nothing
follows), the loader, the taps (start_playqueue with the queue index as the stock drawer's row handler calls it; drags and the header play nothing), the mode buttons (Shuffle
toggles, Repeat cycles off / all / one, the buttons' look), the refresh timer (the player moves on, the mode changes elsewhere, the queue is replaced, a dark screen) and the destroy.
The compiled payload runs under Unicorn; the player is the machine's queue (the deque at PLAY_QUEUE) and position."""
import importlib.util, os, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

HERE = os.path.dirname(os.path.abspath(__file__))


def sibling(name):
    mod = sys.modules.get(f'podtest_{name}')
    if mod is None:
        spec = importlib.util.spec_from_file_location(f'podtest_{name}', os.path.join(HERE, name + '.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f'podtest_{name}'] = mod
        spec.loader.exec_module(mod)
    return mod


SG = sibling('songs')

WIN_H, TOP, ROW, SY0 = O['QP_WIN_H'], O['QP_TOP'], O['LIST_ROW_H'], 30   # SY0: the window's screen y (the status bar's 30 px; the list is the whole window)
SC_YOFF = O['SC_YOFF']
PLAY_QUEUE, FORCE = pod.DATA['PLAY_QUEUE'][0], pod.DATA['FORCE_REFRESH'][0]
UI = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1plus_queue.bin') if WORK else None
KILL = '/mnt/mmc/m1plus-off'
WIDGETS = ('view_queue', 'btn_return', 'btn_shuffle', 'btn_repeat', 'label_status', 'label_row_title', 'label_row_sub', 'qp_title', 'qp_artist', 'qp_empty', 'qp_head', 'label_title', 'qp_shuf_img', 'qp_shuf_title', 'qp_shuf_sub')
NAMES = ['So What', 'Freddie Freeloader', 'Blue in Green', 'All Blues', 'Flamenco Sketches', 'Chorus Complains', 'Come Together', 'Something', 'Hey Jude', 'Let It Be']
RGB = (190, 50, 55)


class QM(SG.SongsMachine):
    """The Songs machine plus what the Queue page calls: the player's play type, start_playqueue (the position moves)."""
    ptype = 0     # mclGetPlayType

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for n in ('mclGetPlayType', 'start_playqueue'): self.handlers[pod.FUNCTIONS[n][2]] = n

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address, '')
        a0 = u.reg_read(UC_MIPS_REG_A0)
        if name == 'mclGetPlayType': ret = self.ptype
        elif name == 'start_playqueue': self.calls.append(('start_playqueue', a0)); self.play_pos = a0; ret = 0
        else: return super()._hook(u, address, size, _)
        u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))


def queue_machine(n=6, pos=1, titles=None, cover=True, cues=()):
    """The page's widgets as widget structs (window > list_view > scroll_view > view_queue, for demo's own widget_to_local) and the player on an n track queue at pos. Track i is
    Artist {i // 3} / Album {i // 3}; a cover file for the first two albums (cover: True, 'marker' for the empty "no art" file, False for none)."""
    m = QM()
    m.load_image = 0
    for w in WIDGETS: Machine.widget(m, w)
    m.canvas = m.alloc(0x80); m.oy_canvas = m.canvas
    m.images = {'p_default': (24, 24, bytes((0x40, 0x40, 0x40, 255)) * (24 * 24))}
    recs = []
    for i in range(n):
        title = titles[i] if titles else NAMES[i % len(NAMES)] if n <= len(NAMES) else f'Track {i + 1}'
        r = m.record(album=f'Album {i // 3}', artist=f'Artist {i // 3}', path=f'/mnt/mmc/m/{i}.flac', title=title, name=f'{i}.flac', rid=100 + i)
        if i in cues: m.setword(r + O['REC_CUE_START'], 1000 * i)
        m.present.add(f'/mnt/mmc/m/{i}.flac')
        recs.append(r)
    m.songs = recs
    m.play(recs, pos)
    m.cover_paths = {}
    for k in range(min(2, (n + 2) // 3)):
        path = art_file(album_key(f'Artist {k}', f'Album {k}'))
        m.cover_paths[k] = path
        if cover == 'marker': m.present.add(path); m.files[path] = 0
        elif cover:
            m.present.add(path); m.files[path] = 4096
            m.images['file://' + path] = (168, 168, bytes((RGB[0] + 20 * k, RGB[1], RGB[2], 255)) * (168 * 168))
    win, lv, sv, view = m.alloc(0x80), m.alloc(0x80), m.alloc(0x180), m.widgets['view_queue']
    m.u.mem_write(sv, bytes(0x180))
    for w, y, h, parent in ((win, SY0, WIN_H, 0), (lv, 0, WIN_H, win), (sv, 0, WIN_H, lv)):
        for off, v in ((4, y), (8, 320), (0xc, h), (0x44, parent)): m.setword(w + off, v)
    m.setword(sv + 8, 310); m.setword(sv + 0x70, SV_VT)   # a real scroll_view's vtable: demo's widget_to_local adds its offset
    m.widgets['queue_scrollview'] = sv
    for off, v in ((4, 0), (8, 320), (0xc, WIN_H), (0x44, sv)): m.setword(view + off, v)
    m.mem_geometry, m.live_scroll = True, frozenset({sv})
    m.sv, m.view = sv, view
    return m


def open_queue(m):
    r = m.call(PSYMS['queue_open'], count=900000000)
    return r if r < 0x80000000 else r - 2 ** 32, list(m.calls)


def opened(**kw):
    m = queue_machine(**kw)
    m.top_main = m.window
    r, calls = open_queue(m)
    assert r == 0 and ('window_open', 'm1plus_queue') in calls, f'the page did not open ({r}, {calls[:12]})'
    return m


def scroll_to(m, v): m.setword(m.sv + SC_YOFF, v & 0xffffffff)


def paint(m):
    """One EVT_AFTER_PAINT on the content view: (blits, texts, fills) of that frame, the canvas where the scroll_view leaves it."""
    ev = m.alloc(0x40); m.u.mem_write(ev, bytes(0x40)); m.setword(ev + O['EVENT_PAINT_CANVAS'], m.canvas)
    m.setword(m.canvas + O['CANVAS_OY'], (SY0 - m.word(m.sv + SC_YOFF)) & 0xffffffff)
    m.blits.clear(); m.texts.clear(); m.text_styles.clear(); m.fills.clear()
    m.call(PSYMS['qp_on_paint'], a0=0, a1=ev, count=400000000)
    return list(m.blits), list(zip(m.texts, m.text_styles)), list(m.fills)


def touch(m, kind, x, y, fn, t=1000): return m.touch(kind, x, SY0 + y, t, fn=fn)


def tap(m, x, y, dx=0, dy=0):
    """A tap on the content view at list point (x, y) (the list starts at the window's top; the scroll offset is not included)."""
    touch(m, 'down', x, y, 'qp_on_down')
    touch(m, 'up', x + dx, y + dy, 'qp_on_up', 1080)
    return list(m.calls)


def click(m, name):
    m.click(name, count=900000000)
    return list(m.calls)


def tick(m):
    r = m.call(PSYMS['qp_on_tick'], count=900000000)
    return r, list(m.calls)


def destroy(*ms):
    for m in ms: m.call(PSYMS['qp_on_destroy'], count=4000000)


def row_y(i): return TOP + i * ROW
def ui(): return awtk_ui.parse(open(UI, 'rb').read())
def text_of(m, name): return m.wtext.get(m.widgets[name])
def utf(s): return s.encode('latin-1').decode('utf-8')
def fills_of(fills, colour): return [f_ for f_ in fills if f_[0] == colour]
def vh(m): return m.props.get((m.sv, 'virtual_h'))
def shown(m, name): return m.props.get((m.widgets[name], 'visible'), 1) and m.props.get((m.widgets[name], 'sensitive'), 1)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def asset_tests(ctx):
    """1. The built asset: a list that is the whole window, the header's widgets and the mode buttons at the numbers of offsets.inc, the glass Back last."""
    expect = ctx.expect
    root = ui()
    f = root.find
    kids = [c.name for c in root.children]
    expect(root.name == 'm1plus_queue_page' == pod_pages.QUEUE_PAGE.name == O.get('QP_WINDOW', 'm1plus_queue_page') and pod_pages.QUEUE_PAGE in pod_pages.PAGES and pod_pages.QUEUE_PAGE.key == 'm1plus_queue',
           'the page is m1plus_queue (window m1plus_queue_page)')
    expect(kids[0] == 'queue_listview' and kids[-2:] == ['label_title', 'btn_return'] and 'btn_backtoplayer' not in kids, f'the list is the window\'s first child, the glass Back its last, no Now Playing: {kids}')
    lv, sv, view = f('queue_listview'), f('queue_scrollview'), f('view_queue')
    expect((lv.x, lv.y, lv.w, lv.h) == (0, 0, 320, WIN_H) and (sv.y, sv.w, sv.h) == (0, 310, WIN_H) and f('scroll_bar_m') is not None and (view.x, view.y, view.w, view.h) == (0, 0, 320, WIN_H),
           'the list is the whole window (y 0, 450 high), its scroll_view 310 wide with the stock scroll bar, the content view in it')
    for name, y, h, px, colour in (('qp_title', O['QP_TITLE_Y'], O['QP_TITLE_H'], 20, '#FFFFFF'), ('qp_artist', O['QP_ARTIST_Y'], O['QP_ARTIST_H'], 16, '#AAAAAA')):
        w = f(name)
        expect(w.type == 'hscroll_label' and (w.x, w.y, w.w, w.h) == (O['QP_TEXT_X'], y, O['QP_TEXT_W'], h) and w.get('sensitive') == 'false' and w.get('ellipses') == 'true'
               and w.get('style:normal:font_size') == str(px) and w.get('style:normal:text_color') == colour and w.get('style:normal:text_align_h') == 'left',
               f'{name}: a left aligned {px} px {colour} hscroll_label at x {O["QP_TEXT_X"]}, insensitive (a drag over it scrolls the list)')
    expect(O['QP_TEXT_X'] == O['QP_COVER_X'] + O['QP_COVER'] + 12 and O['QP_TEXT_X'] + O['QP_TEXT_W'] == 310 and O['QP_TITLE_Y'] + O['QP_TITLE_H'] + 2 + O['QP_ARTIST_H'] + (O['QP_TITLE_Y'] - O['QP_COVER_Y']) == O['QP_COVER_Y'] + O['QP_COVER'],
           'the two lines are centred on the cover (the title 24 px, 2 px, the artist 20 px) and start 12 px after it')
    for name, x, icon in (('btn_shuffle', O['QP_PILL_X0'], 'sg_shuffle'), ('btn_repeat', O['QP_PILL_X1'], 'sg_repeat')):
        b = f(name)
        expect(b.type == 'button' and (b.x, b.y, b.w, b.h) == (x, O['QP_PILL_Y'], O['QP_PILL_W'], O['SG_PILL_H']) and b.get('style:normal:round_radius') == str(O['SG_PILL_R'])
               and b.get('style:normal:bg_color') == '#2C2C2E' and b.get('style:pressed:bg_color') == '#3A3A3C' and b.get('style:normal:icon') == icon and b.get('tr_text') is None and not b.get('text'),
               f'{name}: an icon-only flat button ({O["QP_PILL_W"]} x {O["SG_PILL_H"]}, the 20 px radius, off: #2C2C2E, pressed #3A3A3C, no label) with the {icon} glyph at x {x}')
    expect(O['QP_PILL_X0'] + O['QP_PILL_W'] + 10 == O['QP_PILL_X1'] and O['QP_PILL_X1'] + O['QP_PILL_W'] == 310 and O['QP_PILL_X0'] == 10 and O['QP_PILL_Y'] == O['QP_COVER_Y'] + O['QP_COVER'] + 16,
           'the two buttons are equal, 10 px apart, spanning the 10 px margins, 16 px under the cover')
    head, empty = f('qp_head'), f('qp_empty')
    expect((head.x, head.y, head.h) == (O['SG_HDR_X'], O['QP_HEAD_Y'], O['QP_HEAD_H']) and head.get('style:normal:font_size') == '20' and head.get('style:normal:text_color') == '#FFFFFF'
           and head.get('tr_text', 'Queue') == 'Queue' and head.get('sensitive') == 'false' and f('qp_count') is None, '"Queue" 20 px white at x 10 (the shelf header\'s style), no count')
    expect((empty.x, empty.y, empty.h) == (O['SG_HDR_X'], TOP + O['QP_EMPTY_Y'], O['QP_EMPTY_H']) and empty.get('visible') == 'false' and empty.get('sensitive') == 'false'
           and empty.get('style:normal:text_color') == '#9C9C9C' and empty.get('style:normal:font_size') == '16' and empty.get('tr_text', 'No upcoming songs') == 'No upcoming songs',
           '"No upcoming songs": a quiet grey 16 px line where the first row would be, hidden until nothing follows')
    expect(O['QP_HEAD_Y'] == O['QP_PILL_Y'] + O['SG_PILL_H'] + 16 and O['QP_TOP'] == O['QP_HEAD_Y'] + O['QP_HEAD_H'] + 6, 'the section line is 16 px under the buttons, the rows 6 px under it')
    for name, px, colour in (('label_row_title', 21, '#FFFFFF'), ('label_row_sub', 18, '#AAAAAA')):
        w = f(name)
        expect(w.get('visible') == 'false' and w.get('sensitive') == 'false' and w.get('style:normal:font_size') == str(px) and w.get('style:normal:text_color') == colour,
               f'{name}: the hidden {px} px {colour} text style of the rows (the Songs page\'s)')
    img, st, ss = f('qp_shuf_img'), f('qp_shuf_title'), f('qp_shuf_sub')
    mid = lambda w: w.x + w.w / 2
    expect(img.type == 'image' and (img.w, img.h) == (O['QP_SHUF_IMG'], O['QP_SHUF_IMG']) and mid(img) == 160 and img.y == TOP + O['QP_SHUF_IMG_Y'] and img.get('image') == 'sg_shuffle_big'
           and st.get('style:normal:font_size') == '20' and st.get('style:normal:text_color') == '#FFFFFF' and ss.get('style:normal:font_size') == '16' and ss.get('style:normal:text_color') == '#9C9C9C'
           and mid(st) == 160 == mid(ss) and st.w == ss.w == O['QP_SHUF_W'] and st.y == TOP + O['QP_SHUF_TITLE_Y'] and ss.y == TOP + O['QP_SHUF_SUB_Y'] and st.get('tr_text', 'Shuffle is on') == 'Shuffle is on'
           and all(w.get('visible') == 'false' and w.get('sensitive') == 'false' for w in (img, st, ss)) and all(w.get('style:normal:text_align_h') == 'center' for w in (st, ss)),
           'the Shuffle placeholder: a 40 px glyph, a 20 px white line and a 16 px grey line, centred below the Queue line, hidden until Shuffle and insensitive for good')
    expect(img.y + img.h < st.y and st.y + st.h <= ss.y and ss.y + ss.h < WIN_H, 'the glyph, the two lines and the air fit the list area under the Queue line')
    k = {c.name: c for c in root.children}
    xx = os.path.join(WORK, 'rootfs', 'release', 'assets', 'default', 'raw', 'images', 'xx')
    b = k['btn_return']
    expect((b.x, b.y, b.w, b.h) == (7, 0, 44, 50) and b.get('style') == 'img_btn_style' and b.get('style:normal:icon') == 'ah_nav_back' and b.get('style:pressed:icon') == 'ah_nav_back_down'
           and os.path.exists(os.path.join(xx, 'ah_nav_back.png')), 'btn_return: the glass ah_nav_back disc at x 7 (44 wide), pressed ah_nav_back_down: the only control, to leave')
    expect('navigationbar_view' not in k and k['label_title'].get('visible') == 'false', 'the control is a child of the window itself (no bar view); the section line is the page\'s title')
    for img in ('sg_shuffle', 'sg_repeat', 'sg_repeat1', 'sg_shuffle_on', 'sg_repeat_on', 'sg_repeat1_on', 'sg_shuffle_big'): expect(os.path.exists(os.path.join(xx, img + '.png')), f'{img}.png is in the build')
    # contrast of the glyph on its pill (WCAG): white on the off fill, the dark glyph on the lit fill, pressed too
    from PIL import Image

    def lum(c):
        v = [x / 255 for x in c[:3]]
        v = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]
    ratio = lambda a, b: (max(lum(a), lum(b)) + 0.05) / (min(lum(a), lum(b)) + 0.05)
    rgb = lambda w: (w & 255, (w >> 8) & 255, (w >> 16) & 255)
    for img, fills in (('sg_shuffle', (O['QP_PILL_OFF'], O['QP_PILL_OFF_DOWN'])), ('sg_repeat1_on', (O['QP_PILL_ON'], O['QP_PILL_ON_DOWN']))):
        im = Image.open(os.path.join(xx, img + '.png')).convert('RGBA')
        ink = max((p for p in im.getdata() if p[3] > 200), key=lambda p: lum(p) if img.endswith('_on') is False else -lum(p))
        for w in fills: expect(ratio(ink, rgb(w)) >= 4.5, f'{img} on #{w & 0xffffff:06x}: {ratio(ink, rgb(w)):.1f}:1 (>= 4.5)')
    expect(O['QP_PILL_ON'] == 0xffc8c8c8 and O['QP_PILL_OFF'] == 0xff2e2c2c, 'on is #C8C8C8, off #2C2C2E (Apple\'s lit and unlit buttons)')
    # demo's own hit test: rows under the disc, drags that start beside it reach the list
    m = QM()
    tree = asset_tree(UI)
    node(tree, 'view_queue').h = 3000
    top = lambda x, y: stock_target(m, tree, x, y)[-1]
    expect(top(29, 25) == 'btn_return' and top(8, 6) == 'btn_return' and top(290, 25) == 'view_queue' and top(160, 25) == 'view_queue' and top(160, 300) == 'view_queue',
           f'Back is hit at the glass\'s centre and corner, everything else on the band is the list ({[top(29, 25), top(290, 25), top(160, 25)]})')
    expect(top(80, O['QP_PILL_Y'] + 20) == 'btn_shuffle' and top(230, O['QP_PILL_Y'] + 20) == 'btn_repeat' and top(160, O['QP_PILL_Y'] + 20) == 'view_queue', 'the buttons are hit, the 10 px between them is the list')
    import pod_i18n
    from awtk_text import Ttf, StbText
    font = Ttf(os.path.join(WORK, 'rootfs', 'release', 'assets', 'default', 'raw', 'fonts', 'default.ttf'))
    over = [(key, lc, StbText(font, px).layout(pod_i18n.TEXT[key][lc].replace('%d', '1000'))[1]) for key, px in (('Shuffle is on', 20), ('%d song plays in random order', 16), ('%d songs play in random order', 16))
            for lc in pod_i18n.LOCALES if StbText(font, px).layout(pod_i18n.TEXT[key][lc].replace('%d', '1000'))[1] > O['QP_SHUF_W']]
    expect(not over, f'the placeholder\'s lines fit their 300 px in all 13 languages ({over})')
    for key in ('Queue', 'No upcoming songs', 'Shuffle is on', '%d song plays in random order', '%d songs play in random order'):
        expect(set(pod_i18n.TEXT[key]) == set(pod_i18n.LOCALES) and all(pod_i18n.TEXT[key][lc] for lc in pod_i18n.LOCALES) and pod_i18n.TEXT[key]['en_US'] == key, f'"{key}" is translated in all 13 languages')


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def open_tests(ctx):
    """2. Now Playing's queue button and the open: what it reads, binds and shows; the fallbacks to the stock drawer."""
    expect = ctx.expect
    m = queue_machine()
    r = m.call(PSYMS['np_on_queue'], count=900000000)
    expect(r == O['RET_STOP'] and ('window_open', 'm1plus_queue') in m.calls, f'the queue button opens our page and stops the stock handler (RET_STOP, {r})')
    destroy(m)
    for why, setup in (('the kill switch', lambda m: m.present.add(KILL)), ('an empty queue', lambda m: m.setword(PLAY_QUEUE, m.new_deque([]))), ('no queue at all', lambda m: m.setword(PLAY_QUEUE, 0)),
                       ('no track at the position', lambda m: setattr(m, 'play_pos', -1)), ('a position past the queue', lambda m: setattr(m, 'play_pos', 99)),
                       ('a stream (play type 2)', lambda m: setattr(m, 'ptype', 2)), ('play type 3', lambda m: setattr(m, 'ptype', 3)),
                       ('play type 0xf0', lambda m: setattr(m, 'ptype', 0xf0)), ('play type 0xf1', lambda m: setattr(m, 'ptype', 0xf1)),
                       ('a window that will not open', lambda m: m.windows.__setitem__('m1plus_queue', 0))):
        m = queue_machine(); setup(m)
        r = m.call(PSYMS['np_on_queue'], count=900000000)
        expect(r == O['RET_OK'] and not [c for c in m.calls if c[0] in ('navigator_back', 'start_playqueue')], f'{why}: RET_OK, the stock drawer opens ({r})')
    for t in (0, 1):
        m = queue_machine(); m.ptype = t
        expect(m.call(PSYMS['queue_open'], count=900000000) == 0, f'play type {t} (a local file) opens the page')
        destroy(m)
    m = queue_machine(); del m.widgets['btn_repeat']
    r = m.call(PSYMS['queue_open'], count=900000000)
    expect((r & 0xffffffff) == 0xfffffffe and ('navigator_back',) in m.calls, 'a window without the page\'s widgets goes back and says -2')
    m = opened()
    expect(all((m.widgets[n], O['EVT_CLICK']) in m.bound for n in ('btn_return', 'btn_shuffle', 'btn_repeat')), 'Back, Shuffle and Repeat have click handlers')
    expect(all((m.view, O[e]) in m.bound for e in ('EVT_POINTER_DOWN', 'EVT_POINTER_UP', 'EVT_POINTER_ABORT', 'EVT_AFTER_PAINT')) and (m.sv, O['EVT_SCROLL']) in m.bound and (m.sv, O['EVT_SCROLL_END']) in m.bound
           and (m.window, O['EVT_DESTROY']) in m.bound and (m.window, O['EVT_WINDOW_TO_FG']) in m.bound and (m.window, O['EVT_WINDOW_TO_BG']) in m.bound,
           'the content view takes the touches and the paint, the scroll_view its scroll events, the window its destroy and foreground events')
    expect(len([1 for t in m.timers if t[1] == O['QP_TICK_MS']]) == 1, f'one refresh timer of {O["QP_TICK_MS"]} ms ({m.timers})')
    expect(vh(m) == TOP + 4 * ROW + O['QP_BOTTOM'] and m.props.get((m.sv, 'yoffset')) == 0 and not shown(m, 'qp_empty'),
           'six tracks, the second playing: Up Next is the four after it; the content is the header, four rows and the air; the page opens at the top; no empty line')
    deep = opened(n=60, pos=40)
    expect(vh(deep) == TOP + 19 * ROW + O['QP_BOTTOM'] and deep.props.get((deep.sv, 'yoffset')) == 0, 'the 41st of 60 playing: 19 rows, opened at the top (Up Next starts at once)')
    last = opened(n=6, pos=5)
    expect(vh(last) == WIN_H and shown(last, 'qp_empty') and text_of(last, 'qp_title') == NAMES[5], 'the last track playing: no rows, the grey "No upcoming songs" line shows, the header keeps the track')
    blits, texts, fills = paint(last)
    expect(not [t for (t, r), s in texts if s.startswith('label_row')] and [b for b in blits if tuple(b[2][2:]) == (64, 64)], 'and nothing is painted below the header but the cover')
    stopped = opened(n=6, pos=0)
    expect(vh(stopped) == TOP + 5 * ROW + O['QP_BOTTOM'], 'the first track playing: the other five follow')
    r, calls = open_queue(stopped)
    expect(r == -1, 'a page that is open is not opened again')
    destroy(stopped)
    stopped.play(stopped.songs[:2], 0)
    expect(open_queue(stopped)[0] == 0 and vh(stopped) == TOP + ROW + O['QP_BOTTOM'], 'after the destroy the page opens again, on the queue the player has now')
    destroy(m, deep, last, stopped)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def header_tests(ctx):
    """3. The header: the playing track and its cover."""
    expect = ctx.expect
    m = opened(n=6, pos=1)
    expect(text_of(m, 'qp_title') == 'Freddie Freeloader' and text_of(m, 'qp_artist') == 'Artist 0', f'the playing track\'s title and artist ({[text_of(m, n) for n in ("qp_title", "qp_artist")]})')
    destroy(m)
    m = opened(n=4, pos=1, titles=['A', '', 'C', 'D'])
    expect(text_of(m, 'qp_title') == '1.flac', 'a playing track with no title shows its file name')
    destroy(m)
    m = opened(n=4, pos=2, titles=['A', 'B', 'C', 'D'], cues=(2,))
    expect(text_of(m, 'qp_title') == '2.flac', 'a CUE track shows its file name (the stock drawer\'s rule)')
    destroy(m)
    m = opened(n=6, pos=1)
    blits, texts, fills = paint(m)
    cov = [b for b in blits if tuple(b[2][2:]) == (64, 64)]
    expect(len(cov) == 1 and tuple(cov[0][2][:2]) == (O['QP_COVER_X'], O['QP_COVER_Y']), f'the cover is a 64 px blit at (10, 56) ({[b[2] for b in blits][:3]})')
    expect(('file://' + m.cover_paths[0]) in m.loads, 'it is decoded from the Cover Flow cache file of Artist 0 / Album 0')
    expect(not any('/tmp/' in u for u in m.loads), 'nothing is read from /tmp (the playing track\'s cover is the cache\'s)')
    destroy(m)
    for cover in ('marker', False):
        m = opened(cover=cover)
        blits, texts, fills = paint(m)
        expect(len([b for b in blits if tuple(b[2][2:]) == (64, 64)]) == 1 and not any(u.startswith('file://') for u in m.loads), f'cover {cover}: the placeholder disc (a blit, no file read)')
        destroy(m)
    long_title = 'The Complete Concert in Paris, Olympia, 1961 (Remastered Live Edition)'
    m = opened(n=3, pos=0, titles=[long_title, 'x', 'y'])
    expect(text_of(m, 'qp_title') == long_title, 'a long title is set whole (the label scrolls it)')
    destroy(m)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def rows_tests(ctx):
    """4. Up Next: the tracks after the playing one, painted from the stock queue."""
    expect = ctx.expect
    m = opened(n=6, pos=1)
    blits, texts, fills = paint(m)
    ttl = [(t, r) for (t, r), s in texts if s == 'label_row_title']
    sub = [(t, r) for (t, r), s in texts if s == 'label_row_sub']
    room = O['QP_TEXT_END'] - O['LIST_TEXT_X']
    expect(ttl == [(NAMES[2 + i], (74, row_y(i) + 7, room, 24)) for i in range(4)], f'the rows are the tracks after the playing one, never the playing track: titles from x 74 to 298, 24 px high 7 px down ({ttl})')
    expect(sub == [(f'Artist {(2 + i) // 3}', (74, row_y(i) + 33, room, 20)) for i in range(3)], f'the artists 33 px down, 20 px high (row 3\'s line ends below the window): {sub}')
    expect([s for _, s in texts] == ['label_row_title'] * 4 + ['label_row_sub'] * 3, 'the titles, then the artists: one text style at a time')
    expect(fills_of(fills, O['LIST_HAIR']) == [(O['LIST_HAIR'], 74, row_y(i) + 63, room, 1) for i in range(3)], 'a 1 px hairline under the text of the rows wholly in view')
    rowcov = [b for b in blits if tuple(b[2][2:]) == (52, 52)]
    expect([tuple(b[2][:2]) for b in rowcov] == [(10, row_y(i) + 4) for i in range(3)], f'a 52 px cover at x 10, 4 px down each row that is wholly in view: {[tuple(b[2]) for b in rowcov]}')
    expect(len(fills) == 3 and not [f_ for f_ in fills if f_[0] == O['LIST_PRESS']], 'no wave, no dim, no mark: only the hairlines; nothing is pressed at rest')
    scroll_to(m, 200)
    blits, texts, fills = paint(m)
    got = [(t, r[1]) for (t, r), s in texts if s == 'label_row_title']
    expect(got == [(NAMES[2 + i], row_y(i) + 7 - 200) for i in range(4)], f'scrolled 200 px: the rows at their y less the offset ({got})')
    cover_blits = [b for b in blits if tuple(b[2][2:]) == (64, 64)]
    expect(not cover_blits or cover_blits[0][2][1] == O['QP_COVER_Y'] - 200, 'the header\'s cover goes up with the list')
    destroy(m)
    long_title = 'The Complete Concert in Paris, Olympia, 1961 (Remastered Live Edition)'
    m2 = opened(n=5, pos=0, titles=['P', long_title, '', 'C', 'D'], cues=(3,))
    scroll_to(m2, 100)
    blits, texts, fills = paint(m2)
    got = [t for (t, r), s in texts if s == 'label_row_title']
    expect(got[0].endswith('…') and long_title.startswith(got[0][:-1]) and 8 * len(got[0]) <= room < 8 * (len(got[0]) + 2) and got[1:] == ['2.flac', '3.flac', 'D'],
           f'a title wider than its room is cut with an ellipsis, an untitled track shows its file name, a CUE track always ({got})')
    destroy(m2)
    big = opened(n=300, pos=0)
    expect(vh(big) == TOP + 299 * ROW + O['QP_BOTTOM'], 'the content grows with the queue')
    scroll_to(big, TOP + 120 * ROW)
    blits, texts, fills = paint(big)
    seen = [t for (t, r), s in texts if s == 'label_row_title']
    expect(seen and seen[0] == 'Track 122' and len(seen) <= 8, f'row 120 (queue index 121) at the top of a 300 track queue: {seen[:3]} ({len(seen)} rows)')
    scroll_to(big, TOP + 300 * ROW + 5000)
    paint(big)
    expect(not any(c[0] == 'deque_at_oob' for c in big.calls), 'a list pulled past its end reads no record beyond it')
    destroy(big)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def loader_tests(ctx):
    """5. The cover loader: one per tick, none while the list moves, the cache's file or the placeholder."""
    expect = ctx.expect
    m = opened(n=9, pos=0)
    paint(m)
    m.loads.clear()
    ticks = 0
    while ticks < 40:
        m.calls = []
        m.call(PSYMS['qp_on_load'], count=900000000)
        ticks += 1
        if not any(c[0] == 'timer_add' for c in m.calls): break
    expect(3 <= ticks <= 10, f'the visible rows are loaded one a tick and the timer stops when none is left ({ticks} ticks)')
    expect(sorted(set(m.loads)) == sorted('file://' + p for p in m.cover_paths.values()) and len(m.loads) >= 2, f'the covers come from the Cover Flow cache files ({m.loads})')
    blits, texts, fills = paint(m)
    expect(len([b for b in blits if tuple(b[2][2:]) == (52, 52)]) >= 3, 'every visible row has a cover blit (the file\'s or the placeholder)')
    destroy(m)
    m = opened(n=9, pos=0)
    paint(m)
    m.loads.clear()
    m.u.mem_write(m.sv + O['SC_PRESSED'], bytes([1, 1]))
    m.calls = []
    m.call(PSYMS['qp_on_load'], count=900000000)
    expect(not m.loads and any(c[0] == 'timer_add' for c in m.calls), 'a list that is being dragged decodes nothing and looks again next tick')
    m.u.mem_write(m.sv + O['SC_PRESSED'], bytes([0, 0]))
    destroy(m)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def play_tests(ctx):
    """6. The taps: a row plays through start_playqueue (the queue index); the press fill; Back."""
    expect = ctx.expect
    m = opened(n=6, pos=1)
    calls = tap(m, 150, row_y(1) + 20)
    expect(('start_playqueue', 3) in calls and m.play_pos == 3 and m.word(FORCE) & 0xff == 1, 'a tap on the second row (queue index 3): start_playqueue(3) (the stock drawer\'s row handler) and force_refreshflag set')
    expect(not [c for c in calls if c[0] in ('navigator_to_with_context', 'loadSongList', 'start_player', 'navigator_back')], 'the page stays and the queue is not rebuilt: only the position moves')
    expect(text_of(m, 'qp_title') == NAMES[3] and vh(m) == TOP + 2 * ROW + O['QP_BOTTOM'], 'the header follows at once and Up Next is now the tracks after the new one')
    _, texts, _ = paint(m)
    expect([t for (t, r), s in texts if s == 'label_row_title'] == NAMES[4:6], 'its rows are the two after it')
    for label, dx, dy in (('a drag', 0, 14), ('a slide sideways', 12, 0)):
        expect(not [c for c in tap(m, 150, row_y(1) + 20, dx, dy) if c[0] == 'start_playqueue'], f'{label} plays nothing')
    expect(not [c for c in tap(m, 150, 100) if c[0] == 'start_playqueue'] and not [c for c in tap(m, 150, TOP - 4) if c[0] == 'start_playqueue'] and not [c for c in tap(m, 150, row_y(2) + 10) if c[0] == 'start_playqueue'],
           'a tap on the header, the gap above the first row and the air below the last plays nothing')
    touch(m, 'down', 150, row_y(0) + 20, 'qp_on_down')
    _, _, fills = paint(m)
    expect((O['LIST_PRESS'], 0, row_y(0), O['QP_ROW_W'], ROW - 1) in fills, f'the row under the finger is filled: {[f_ for f_ in fills if f_[0] == O["LIST_PRESS"]]}')
    touch(m, 'abort', 150, row_y(0) + 20, 'qp_on_abort')
    _, _, fills = paint(m)
    expect(not any(f_[0] == O['LIST_PRESS'] for f_ in fills), 'an abort (the scroll_view took a drag) clears it')
    touch(m, 'down', 150, row_y(0) + 20, 'qp_on_down'); touch(m, 'up', 150, row_y(0) + 20, 'qp_on_up', 1080)
    expect(m.play_pos == 4, 'a tap on the first row plays the next track')
    _, _, fills = paint(m)
    expect(not any(f_[0] == O['LIST_PRESS'] for f_ in fills), 'and a release clears the fill')
    destroy(m)
    new = lambda m: [m.record(album='New', artist='New Artist', path=f'/mnt/mmc/n/{i}.flac', title=f'New {i}', name=f'n{i}.flac', rid=500 + i) for i in range(3)]
    m = opened(n=6, pos=1)
    m.play(new(m), 0)
    blits, texts, fills = paint(m)
    expect(not texts and not blits and any(c[0] == 'timer_add' for c in m.calls), 'a paint of a queue that is not the page\'s paints nothing and asks to read it again')
    m.call(PSYMS['qp_on_stale'], count=900000000)
    expect(text_of(m, 'qp_title') == 'New 0' and vh(m) == TOP + 2 * ROW + O['QP_BOTTOM'], 'the page reads the new queue when it is on top')
    destroy(m)
    m = opened(n=6, pos=1)
    m.play(new(m), 0)
    expect(not [c for c in tap(m, 150, row_y(1) + 20) if c[0] == 'start_playqueue'], 'a tap on rows that are not the player\'s queue plays nothing')
    destroy(m)
    m = opened(n=6, pos=1)
    touch(m, 'down', 150, row_y(1) + 20, 'qp_on_down')
    m.play(new(m), 0)
    touch(m, 'up', 150, row_y(1) + 20, 'qp_on_up', 1080)
    expect(not [c for c in m.calls if c[0] == 'start_playqueue'] and text_of(m, 'qp_title') == 'New 0', 'a queue replaced between the press and the release: the page reads the new one instead of playing a row of the old')
    destroy(m)
    m = opened()
    expect(('navigator_back',) in click(m, 'btn_return'), 'Back goes back to Now Playing')
    destroy(m)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def mode_tests(ctx):
    """7. The buttons: Shuffle toggles the stock Shuffle, Repeat cycles off / all / one; the buttons show the mode."""
    expect = ctx.expect
    SH, RA, RO, OR = O['MODE_SHUFFLE'], O['MODE_REPEAT_ALL'], O['MODE_REPEAT_ONE'], O['MODE_ORDER']
    on_n, on_d, off_n, off_d = O['QP_PILL_ON'], O['QP_PILL_ON_DOWN'], O['QP_PILL_OFF'], O['QP_PILL_OFF_DOWN']

    def look(m):
        out = {}
        for name in ('btn_shuffle', 'btn_repeat'):
            w = m.widgets[name]
            bg = {s[1]: s[2] for s in m.styled if s[0] == w and s[1].endswith(':bg_color')}
            out[name] = (bg.get('normal:bg_color'), bg.get('pressed:bg_color'), m.props.get((w, 'style:normal:icon')), m.props.get((w, 'style:pressed:icon')))
        return out
    m = queue_machine(); m.top_main = m.window; m.mode = OR; open_queue(m)
    lk = look(m)
    expect(lk['btn_shuffle'] == (off_n, off_d, 'sg_shuffle', 'sg_shuffle') and lk['btn_repeat'] == (off_n, off_d, 'sg_repeat', 'sg_repeat'), f'List play: both buttons dark with the white glyph ({lk})')
    expect(O['QP_PILL_OFF'] == 0xff2e2c2c and O['QP_PILL_OFF_DOWN'] == 0xff3c3a3a and O['QP_PILL_ON_DOWN'] < O['QP_PILL_ON'], 'the off look is the asset\'s own colours (#2C2C2E, pressed #3A3A3C); the lit one is lighter, pressed a little darker')
    destroy(m)
    for start, after, shuffle_on in ((OR, SH, True), (RA, SH, True), (RO, SH, True), (SH, OR, False)):
        m = opened(); m.mode = start
        m.call(PSYMS['qp_load'], a0=1, count=900000000)
        calls = click(m, 'btn_shuffle')
        expect(m.mode == after and (('mclSetPlayMode', after) in calls), f'Shuffle from mode {start}: mode {after}')
        expect(look(m)['btn_shuffle'][0] == (on_n if shuffle_on else off_n), f'Shuffle from mode {start}: the button is {"on" if shuffle_on else "off"}')
        destroy(m)
    m = opened(); m.mode = OR; m.call(PSYMS['qp_load'], a0=1, count=900000000)
    seq = []
    for _ in range(4):
        click(m, 'btn_repeat'); seq.append((m.mode, look(m)['btn_repeat']))
    expect([s[0] for s in seq] == [RA, RO, OR, RA], f'Repeat cycles all, one, off, all ({[s[0] for s in seq]})')
    expect(seq[0][1] == (on_n, on_d, 'sg_repeat_on', 'sg_repeat_on') and seq[1][1] == (on_n, on_d, 'sg_repeat1_on', 'sg_repeat1_on') and seq[2][1] == (off_n, off_d, 'sg_repeat', 'sg_repeat'),
           f'Repeat all is the lit button with the dark repeat glyph, Repeat one with the dark repeat-1 glyph, off the dark button ({seq})')
    m.mode = SH; click(m, 'btn_repeat')
    expect(m.mode == RA and look(m)['btn_shuffle'][0] == off_n, 'Repeat from Shuffle gives Repeat all and puts Shuffle out')
    expect(('write_int_config', RA, 'PLAYSET', 'PLAYMODE') in m.calls, 'the mode is saved as the Play settings page saves it')
    destroy(m)


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def tick_tests(ctx):
    """8. The refresh timer: the player moves on, the mode changes elsewhere, the queue is replaced, a dark screen, the destroy."""
    expect = ctx.expect
    m = opened(n=6, pos=1)
    paint(m)
    r, calls = tick(m)
    expect(r == O['RET_REPEAT'] and not [c for c in calls if c[0] in ('widget_set_text_utf8', 'widget_invalidate_force')], 'a tick with nothing new changes nothing and repeats')
    m.play_pos = 2   # the next track started (auto advance, a hardware key)
    r, calls = tick(m)
    expect(r == O['RET_REPEAT'] and text_of(m, 'qp_title') == NAMES[2] and vh(m) == TOP + 3 * ROW + O['QP_BOTTOM'] and any(c[0] == 'widget_invalidate_force' and c[1] == m.sv for c in calls),
           'the next track: the header follows, the rows are the three after it, the list is redrawn')
    _, texts, _ = paint(m)
    expect([t for (t, r), s in texts if s == 'label_row_title'] == NAMES[3:6], 'the playing track left Up Next')
    m.play_pos = 5; tick(m)
    expect(shown(m, 'qp_empty') and vh(m) == WIN_H, 'the last track: "No upcoming songs" shows')
    m.play_pos = 0; tick(m)
    expect(not shown(m, 'qp_empty'), 'and goes when rows follow again')
    m.mode = O['MODE_SHUFFLE']; tick(m)
    expect(m.props.get((m.widgets['btn_shuffle'], 'style:normal:icon')) == 'sg_shuffle_on' and [s[2] for s in m.styled if s[0] == m.widgets['btn_shuffle'] and s[1] == 'normal:bg_color'][-1] == O['QP_PILL_ON'],
           'a mode set elsewhere (Now Playing\'s own button, the Play settings) lights the button')
    m.mode = O['MODE_ORDER']; tick(m)
    new = [m.record(album='New', artist='New Artist', path=f'/mnt/mmc/n/{i}.flac', title=f'New {i}', name=f'n{i}.flac', rid=500 + i) for i in range(4)]
    m.play(new, 1)
    m.call(PSYMS['qp_on_bg'], count=900000000); tick(m)
    expect(text_of(m, 'qp_title') == NAMES[0], 'behind another page the queue is not read')
    m.call(PSYMS['qp_on_fg'], count=900000000)
    expect(text_of(m, 'qp_title') == 'New 1' and vh(m) == TOP + 2 * ROW + O['QP_BOTTOM'], 'back in front it reads the new queue (EVT_WINDOW_TO_FG)')
    m.screen(False); tick(m)
    expect(any(c[0] == 'timer_modify' and c[2] == 1000 for c in m.calls), 'a dark screen slows the timer to 1 s')
    m.screen(True); tick(m)
    expect(any(c[0] == 'timer_modify' and c[2] == O['QP_TICK_MS'] for c in m.calls), 'and a lit one restores it')
    destroy(m)
    removed = [c for c in m.calls if c[0] == 'timer_remove']
    expect(len(removed) >= 1, f'the destroy removes the page\'s timers ({removed})')
    expect(open_queue(m)[0] == 0, 'a fresh open after the destroy works (no state is left)')
    destroy(m)


def shuffle_tests(ctx):
    """9. Shuffle: no Up Next (stock draws the next track at random), a placeholder instead; the list returns when the mode changes, from our buttons or from elsewhere (the refresh tick)."""
    expect = ctx.expect
    SH, OR, RA = O['MODE_SHUFFLE'], O['MODE_ORDER'], O['MODE_REPEAT_ALL']
    vis = lambda m: [m.props.get((m.widgets[n], 'visible'), 1) for n in ('qp_shuf_img', 'qp_shuf_title', 'qp_shuf_sub')]
    sens = lambda m: [m.props.get((m.widgets[n], 'sensitive'), 0) for n in ('qp_shuf_img', 'qp_shuf_title', 'qp_shuf_sub')]
    m = queue_machine(n=6, pos=1); m.top_main = m.window; m.mode = SH; open_queue(m)
    expect(vis(m) == [1, 1, 1] and not shown(m, 'qp_empty') and vh(m) == WIN_H, 'opened in Shuffle: the placeholder shows, no rows, no "No upcoming songs", the content is the window (nothing to scroll)')
    expect(text_of(m, 'qp_shuf_sub') == '6 songs play in random order' and text_of(m, 'qp_head') in (None, 'Queue'), 'the count line is the queue\'s size; the section label stays "Queue"')
    expect(text_of(m, 'qp_title') == NAMES[1], 'the header keeps the playing track')
    expect(not any(v for v in sens(m)), 'the placeholder is insensitive: no tap reaches it')
    blits, texts, fills = paint(m)
    expect(not [t for (t, r), s in texts if s.startswith('label_row')] and not [f_ for f_ in fills if f_[0] == O['LIST_HAIR']], 'no row is painted')
    expect(not [c for c in tap(m, 150, row_y(0) + 20) if c[0] == 'start_playqueue'] and not [c for c in tap(m, 150, row_y(1) + 20) if c[0] == 'start_playqueue'], 'a tap where rows were plays nothing')
    # Shuffle off from our button: the list comes back, at the top
    click(m, 'btn_shuffle')
    expect(m.mode == OR and vis(m) == [0, 0, 0] and vh(m) == TOP + 4 * ROW + O['QP_BOTTOM'] and m.props.get((m.sv, 'yoffset')) == 0 and not shown(m, 'qp_empty'), 'Shuffle off: the placeholder goes, Up Next is back (the four after the playing track), at the top')
    _, texts, _ = paint(m)
    expect([t for (t, r), s in texts if s == 'label_row_title'] == NAMES[2:6], 'and painted')
    click(m, 'btn_shuffle')
    expect(m.mode == SH and vis(m) == [1, 1, 1] and vh(m) == WIN_H, 'Shuffle on from our button: the list gives way to the placeholder at once')
    # Repeat from Shuffle gives Repeat all: the list returns
    click(m, 'btn_repeat')
    expect(m.mode == RA and vis(m) == [0, 0, 0] and vh(m) == TOP + 4 * ROW + O['QP_BOTTOM'], 'Repeat from Shuffle (Repeat all): the list returns')
    # another page changes the mode: the refresh tick swaps
    scroll_to(m, 100)
    m.mode = SH; tick(m)
    expect(vis(m) == [1, 1, 1] and vh(m) == WIN_H, 'Shuffle turned on elsewhere (Now Playing\'s button, the Play settings): the tick shows the placeholder')
    m.mode = OR; tick(m)
    expect(vis(m) == [0, 0, 0] and vh(m) == TOP + 4 * ROW + O['QP_BOTTOM'] and m.props.get((m.sv, 'yoffset')) == 0, 'and off elsewhere: the tick brings the list back, scrolled to the top')
    m.mode = RA; tick(m)
    expect(vis(m) == [0, 0, 0] and not any(c[0] == 'widget_resize' for c in m.calls), 'a change between the other modes touches only the buttons')
    # one song; the next track in Shuffle keeps the placeholder
    m.mode = SH; tick(m)
    m.play_pos = 3; tick(m)
    expect(vis(m) == [1, 1, 1] and text_of(m, 'qp_title') == NAMES[3], 'a new track in Shuffle: the header follows, the placeholder stays')
    destroy(m)
    m = queue_machine(n=1, pos=0); m.top_main = m.window; m.mode = SH; open_queue(m)
    expect(text_of(m, 'qp_shuf_sub') == '1 song plays in random order', 'one song: "1 song plays in random order"')
    destroy(m)
    m = queue_machine(n=6, pos=1); m.top_main = m.window; m.mode = SH; m.set_language('ge_DE'); open_queue(m)
    expect(utf(text_of(m, 'qp_shuf_sub')) == '6 Titel in zufälliger Reihenfolge', f'translated: {utf(text_of(m, "qp_shuf_sub"))!r}')
    destroy(m)


SECTIONS = [asset_tests, open_tests, header_tests, rows_tests, loader_tests, play_tests, mode_tests, tick_tests, shuffle_tests]   # tools/check.py runs each as its own task


def run(ctx):
    for section in SECTIONS: section(ctx)
