"""The Podcasts page's Downloads level and select mode (patch/podcasts.c, docs/modules/podcasts.md "Downloads"): the level behind the Feeds level's Downloads row (rows from the queue, the failed
ones and the .part files the card has, their state lines, taps, the live update, the empty state, the screen-off rule), and the select mode of the Show and Downloads levels in the Playlists page's
manner (the navbar's x, "N Selected", Select All, marks, a Delete bar, a confirm; only episodes on the card are marked; the file and its .part unlinked, the `.episodes` line kept, the playing episode
kept, a show with no file leaving the Shows level). The compiled payload runs under Unicorn; the card is a dict of paths."""
import importlib.util, os, struct, sys
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


DL = sibling('pcdl')
PF, PCN, PCP = DL.PF, DL.PCN, DL.PCP
RP, ROW, HDR, NOW, PN = DL.RP, DL.ROW, DL.HDR, DL.NOW, DL.PN
pn_at, poke_slot, poke_fail, key_of = DL.pn_at, DL.poke_slot, DL.poke_fail, DL.key_of
SG_MARK, SG_BAR_H = O['SG_MARK'], O['SG_BAR_H']
SUB = 'Sub One'


def card(m):
    """Sub One: a.mp3 and b.mp3 on the card (local), c.mp3 not, d.mp3 with a .part, e.mp3 and f.mp3 not; every line has its url."""
    PF.card(m)
    lines_ = ''.join(f'g=s{i}\tp={NOW - 5000 - 100 * i}\td=600\tl=1000\tf={f}.mp3\tt=Ep {f.upper()}\tu=https://e.example/{f}.mp3\n' for i, f in enumerate('abcdef'))
    m.put(f'{RP}/{SUB}/.episodes', (PCP.EPS_HEAD + lines_).encode())
    for f in 'ab': m.put(f'{RP}/{SUB}/{f}.mp3', b'audio-' + f.encode())
    m.put(f'{RP}/{SUB}/d.mp3.part', b'half')


def page():
    m = PCP.opened(lambda mm: (card(mm), mm.images.update({'unselect': (26, 26, struct.pack('<I', 0xff111111) * 676), 'selected': (26, 26, struct.pack('<I', 0xff2222ee) * 676)})), PCN.NM)
    m.curl_site = DL.server(DL.DATA)
    return m


def flags(m, n): return PF.flags(m, n)
def toasts(m): return [c[1] for c in m.calls if c[0] == 'toast']
def confirms(m): return [c[1] for c in m.calls if c[0] == 'confirm']
def unlinks(m): return [c[1].replace(RP + '/', '') for c in m.calls if c[0] == 'unlink']
def tick(m): return DL.tick(m)
def to_feeds(m): PCP.click(m, 'btn_feeds')
def title(m): return PCP.title_text(m)


def lines(m, top=0):
    """[(row, title, grey line)] of a frame: the titles and the grey lines by row (top: where the first row starts)."""
    _, texts, styles, _ = PCP.paint(m)
    t = {(y - top) // ROW: v for (v, (x, y, w, h)), s in zip(texts, styles) if s in ('label_row_title', 'label_row_dim', 'label_row_act') and y >= top and (y - top) % ROW == O['LIST_TITLE_Y']}
    g = {(y - top) // ROW: v for (v, (x, y, w, h)), s in zip(texts, styles) if s == 'label_row_sub' and y >= top and (y - top) % ROW == O['LIST_SUB_Y']}
    return [(r, t.get(r), g.get(r)) for r in sorted(t)]


def marks(m, off=0):
    bl, *_ = PCP.paint(m, off)
    return sorted((b[2][0], b[2][1], b[0]) for b in bl if tuple(b[2][2:]) == (SG_MARK, SG_MARK))


def running(m, f='e.mp3', got=420000, total=1000000):
    """The status record as it is while f downloads (slot 0, seq 1)."""
    poke_slot(m, 0, SUB, f, 2, seq=1)
    m.setword(pn_at(DL.DKEY), key_of(SUB, f)); m.setword(pn_at(DL.DGOT), got); m.setword(pn_at(DL.DTOTAL), total)
    m.setword(pn_at(DL.KIND), 2); m.setword(pn_at(0), 1); m.setword(pn_at(DL.DSEQ), 10)


def downloads_tests(ctx):
    expect = ctx.expect
    m = page()
    running(m)
    poke_slot(m, 1, SUB, 'c.mp3', 1, seq=2)
    poke_fail(m, 0, SUB, 'f.mp3', PN['NET'])
    to_feeds(m)
    expect(any(t == 'Downloads (2)' for _, t, _ in lines(m)), f'Feeds: Downloads (2) ({lines(m)})')
    m.calls = []
    PCP.tap(m, 150, ROW + 10)
    expect(title(m) == 'Downloads' and flags(m, 'btn_feeds') == (0, 0), 'a tap on the Downloads row opens the level: the title Downloads, the Feeds button gone')
    got = lines(m)
    expect(got == [(0, 'Ep E', 'Downloading 42%'), (1, 'Ep C', 'Waiting'), (2, 'Ep F', "Failed: Can't connect"), (3, 'Ep D', 'Paused')],
           f'a row per download: the running and waiting ones in queue order, then the failed one, then the paused .part the card has and the worker does not: {got}')
    expect(m.props.get((m.sv, 'virtual_h')) == 4 * ROW, 'four rows')
    bl, texts, styles, _ = PCP.paint(m)
    expect(len([b for b in bl if tuple(b[2][2:]) == (O['LIST_ART'], O['LIST_ART'])]) == 4, 'each with the show\'s cover (the placeholder here)')
    expect({s for s in styles} <= {'label_row_title', 'label_row_sub'}, 'neutral styles only (no accent colour)')
    # taps
    m.calls = []; m.thread = None
    PCP.tap(m, 150, 10)   # the running one: paused (cancelled; its .part stays)
    expect(m.word(pn_at(DL.DCANCEL)) == key_of(SUB, 'e.mp3') and toasts(m) == [], 'a tap on the running one pauses it (the worker is told to cancel it; the .part stays)')
    m.setword(pn_at(DL.DCANCEL), 0)
    PCP.tap(m, 150, ROW + 10)   # the waiting one leaves the queue
    expect(DL.fn(m, 'pn_dl_count') == 1 and DL.state(m, 'c.mp3', SUB)[0] == 0, 'a tap on a waiting one takes it out of the queue')
    names = [t for _, t, _ in lines(m)]
    expect('Ep C' not in names, f'its row is gone ({names})')
    PCP.tap(m, 150, names.index('Ep F') * ROW + 10)   # the failed one is tried again
    expect(DL.state(m, 'f.mp3', SUB)[0] == 1 and DL.fn(m, 'pn_dl_count') == 2, 'a tap on a failed one tries it again (queued; the poked record says a thread runs, so no second one starts)')
    expect(dict((t, g) for _, t, g in lines(m)).get('Ep F') == 'Waiting', f'its line says Waiting ({lines(m)})')
    names = [t for _, t, _ in lines(m)]
    PCP.tap(m, 150, names.index('Ep D') * ROW + 10)   # the paused one resumes
    expect(DL.state(m, 'd.mp3', SUB)[0] == 1, 'a tap on a paused one resumes it (queued)')
    PCP.click(m, 'btn_return')
    expect(title(m) == 'Feeds', 'Back returns to Feeds')
    # a finished download leaves the list; the live update; the empty state
    PCP.tap(m, 150, ROW + 10)
    for i in range(32): poke_slot(m, i, SUB, 'x.mp3', 0)
    m.setword(pn_at(DL.DKEY), 0); m.setword(pn_at(0), 0); m.setword(pn_at(DL.KIND), 0)
    m.u.mem_write(pn_at(DL.FAILS), bytes(DL.FAIL_SIZE * 16))
    m.fs.pop(f'{RP}/{SUB}/d.mp3.part')
    m.setword(pn_at(12), 500)   # the generation moves
    before = lines(m)
    m.screen(False); m.calls = []
    m.call(PSYMS['pg_tick'], a0=0, count=40000000)
    expect(lines(m) == before and not [c for c in m.calls if c[0] in ('widget_set_tr_text', 'widget_invalidate_force')], 'screen off: the rows are not rebuilt (a lit tick does it)')
    tick(m)
    expect(('widget_set_tr_text', m.widgets['label_status'], 'No downloads') in m.calls and lines(m) == [], 'nothing pending: the page says "No downloads" (a finished download is a file, not a row)')
    # the cap: 32 queued and 16 failed make 40 rows at most
    m = page()
    for i in range(32): poke_slot(m, i, SUB, f'q{i}.mp3', 1, seq=i + 1)
    for i in range(16): poke_fail(m, i, SUB, f'z{i}.mp3', PN['HTTP'])
    to_feeds(m); PCP.tap(m, 150, ROW + 10)
    expect(m.props.get((m.sv, 'virtual_h')) == 40 * ROW, 'at most 40 rows (the tile ring): 32 queued, 16 failed, the rest left out')
    # progress changes a line, not the rows
    m = page()
    running(m, got=100000)
    to_feeds(m); PCP.tap(m, 150, ROW + 10)
    expect(lines(m)[0][2] == 'Downloading 9%', f'{lines(m)}')
    m.setword(pn_at(DL.DGOT), 500000); m.setword(pn_at(DL.DGEN), 9)
    m.calls = []
    tick(m)
    expect(lines(m)[0][2] == 'Downloading 50%' and not [c for c in m.calls if c[0] in ('opendir', '__xstat')], 'a step of progress: the line is made again, the card is not read')


def select_tests(ctx):
    expect = ctx.expect
    m = page()
    expect(flags(m, 'btn_select') == (0, 0) and flags(m, 'btn_feeds') == (1, 1), 'the Shows level: Feeds, no Select')
    PCP.tap(m, 150, 10)   # Alpha Show (two files)
    expect(title(m) == 'Alpha Show' and flags(m, 'btn_select') == (1, 1) and flags(m, 'btn_feeds') == (0, 0) and m.props[(m.widgets['btn_backtoplayer'], 'style:normal:icon')] == 'ah_nav_play',
           'a show with episodes on the card: the Select button (the capsule\'s left cap) and Now Playing as its right cap')
    m = page(); to_feeds(m)
    m.put(f'{RP}/Sub Two/.episodes', (PCP.EPS_HEAD + 'g=t1\tp=5\tf=t.mp3\tt=T\tu=https://e.example/t.mp3\n').encode())
    PCP.tap(m, 150, 3 * ROW + 10)   # Sub Two: one episode, not on the card
    expect(title(m) == 'Sub Two' and flags(m, 'btn_select') == (0, 0) and m.props[(m.widgets['btn_backtoplayer'], 'style:normal:icon')] == 'ah_nav_np',
           'a show with only remote episodes: no Select button, Now Playing is the glass disc')
    # Sub One from Feeds: a, b local, c, e, f remote, d paused
    m = page(); to_feeds(m)
    PCP.tap(m, 150, 2 * ROW + 10)
    expect(title(m) == SUB and flags(m, 'btn_select') == (1, 1), 'Sub One from Feeds: Select')
    h0 = m.props.get((m.sv, 'virtual_h'))
    m.calls = []
    PCP.click(m, 'btn_select')
    t, back = m.widgets['label_title'], m.widgets['btn_return']
    expect(('widget_set_text_utf8', t, '0 Selected') in m.calls and ('widget_resize', t, O['SG_SELALL_X'] - O['NAV_TITLE_X'], 22) in m.calls, 'Select: the title reads 0 Selected and runs to Select All')
    expect(flags(m, 'btn_selall') == (1, 1) and flags(m, 'pg_bar') == (1, 1) and flags(m, 'btn_select') == (0, 0) and flags(m, 'btn_backtoplayer') == (0, 0) and flags(m, 'btn_feeds') == (0, 0),
           'Select All and the bar show; Select and Now Playing go (hidden and insensitive)')
    expect(m.props.get((back, 'style:normal:icon')) == 'ah_nav_close' and m.props.get((back, 'style:pressed:icon')) == 'ah_nav_close_down', 'Back becomes the glass x')
    expect(m.props.get((m.sv, 'virtual_h')) == h0 + SG_BAR_H, 'the content is the bar\'s height longer')
    mk = marks(m)
    expect(len(mk) == 3 and len({b for _, _, b in mk}) == 1, f'a mark on each row that can be marked (two files and the .part), all unselected ({len(mk)})')
    expect(all(x == 16 + (O['SG_SEL_COL'] - 6 - SG_MARK) // 2 for x, _, _ in mk), 'in the mark column that opens left of the texts')
    ls = lines(m, HDR)
    expect([t_ for _, t_, _ in ls][:4] == ['Ep A', 'Ep B', 'Ep C', 'Ep D'], f'the four rows in view: {ls}')
    _, texts, styles, _ = PCP.paint(m)
    xs = [r[0] for (v, r), s in zip(texts, styles) if s in ('label_row_title', 'label_row_dim') and r[1] >= HDR]
    expect(xs and all(x == 16 + O['SG_SEL_COL'] for x in xs), f'the texts moved right by the mark column ({xs})')
    # taps: a remote row marks nothing, a local one marks
    m.calls = []
    PCP.tap(m, 150, HDR + 2 * ROW + 10)   # Ep C: remote
    expect(not [c for c in m.calls if c[0] == 'widget_set_text_utf8' and c[1] == t] and DL.fn(m, 'pn_dl_count') == 0 and 'pthread_create' not in [c[0] for c in m.calls],
           'a tap on a remote row marks nothing and downloads nothing')
    m.calls = []
    PCP.tap(m, 150, HDR + 10)
    expect(('widget_set_text_utf8', t, '1 Selected') in m.calls and 'navigator_to_with_context' not in [c[0] for c in m.calls], 'a tap on a file marks it (1 Selected) and plays nothing')
    expect(len({b for _, _, b in marks(m)}) == 2, 'the marked row has the selected image')
    m.calls = []
    PCP.tap(m, 20, HDR + 10)   # where the dot would be
    expect(m.ring() is None and ('widget_set_text_utf8', t, '0 Selected') in m.calls, 'a tap where the dot would be unmarks (it does not toggle played)')
    m.calls = []
    PCP.click(m, 'btn_selall')
    expect(('widget_set_text_utf8', t, '3 Selected') in m.calls, 'Select All marks the three that can be marked')
    m.calls = []
    PCP.click(m, 'btn_selall')
    expect(('widget_set_text_utf8', t, '0 Selected') in m.calls, 'Select All again: none')
    m.calls = []
    PCP.tap(m, 150, HDR + 10, move=40)
    expect(not [c for c in m.calls if c[0] == 'widget_set_text_utf8' and c[1] == t], 'a drag marks nothing')
    m.calls = []
    PCP.click(m, 'btn_return')
    expect(flags(m, 'pg_bar') == (0, 0) and flags(m, 'btn_selall') == (0, 0) and flags(m, 'btn_select') == (1, 1) and m.props.get((back, 'style:normal:icon')) == 'ah_nav_back' and title(m) == SUB
           and 'navigator_back' not in [c[0] for c in m.calls] and m.props.get((m.sv, 'virtual_h')) == h0,
           'Back (the x) leaves select mode first: the bar goes, Select is back, the title and the content are as before')
    PCP.click(m, 'btn_select'); m.calls = []
    PCP.click(m, 'pg_del')
    expect(not confirms(m), 'Delete with nothing marked does nothing')
    PCP.tap(m, 150, HDR + 10); m.calls = []; m.confirm_yes = False
    PCP.click(m, 'pg_del')
    expect(confirms(m) == ['Delete the selected episodes?'] and not unlinks(m) and flags(m, 'pg_bar') == (1, 1), 'Delete asks; No: nothing is deleted and the mode stays')
    # Yes, with the playing episode among them
    m.confirm_yes = True
    h = PCP.pc_hash(f'{RP}/{SUB}/b.mp3')
    m.call(PSYMS['pc_mark'], a0=h, a1=1, count=2000000)
    expect(m.state(h)[0] == 2, 'b.mp3 is marked played before')
    m.track(f'{RP}/{SUB}/a.mp3')
    PCP.click(m, 'btn_selall'); m.calls = []
    PCP.click(m, 'pg_del')
    expect(confirms(m) == ['Delete the selected episodes?'], 'Delete asks first')
    expect(sorted(unlinks(m)) == sorted([f'{SUB}/b.mp3', f'{SUB}/b.mp3.part', f'{SUB}/d.mp3', f'{SUB}/d.mp3.part']), f'each marked file and its .part is unlinked, the playing a.mp3 is not touched ({unlinks(m)})')
    expect(toasts(m) == ['The playing episode was kept'], 'the playing episode is kept, with a toast')
    expect(f'{RP}/{SUB}/a.mp3' in m.fs and f'{RP}/{SUB}/b.mp3' not in m.fs and f'{RP}/{SUB}/d.mp3.part' not in m.fs, 'the card: a.mp3 stays; b.mp3 and the paused d.mp3.part are gone')
    eps = m.fs[f'{RP}/{SUB}/.episodes']
    expect(b'f=b.mp3' in eps and b'f=d.mp3' in eps, 'the .episodes lines are kept (the episodes are remote again)')
    expect(flags(m, 'pg_bar') == (0, 0) and title(m) == SUB and flags(m, 'btn_select') == (1, 1), 'the mode ended; the page is read again')
    expect(m.state(h)[0] == 0, 'the played mark of a deleted episode is forgotten')
    got = lines(m, HDR)
    _, _, styles, _ = PCP.paint(m)
    expect([t_ for _, t_, _ in got][:2] == ['Ep A', 'Ep B'] and styles.count('label_row_title') >= 1 + 1, f'the page now: {got}')
    # a show left with no file drops off the Shows level, and stays in Feeds
    m = page()
    PCP.tap(m, 150, 10)   # Alpha Show
    PCP.click(m, 'btn_select'); PCP.click(m, 'btn_selall'); m.calls = []; m.confirm_yes = True
    PCP.click(m, 'pg_del')
    expect(sorted(unlinks(m)) == sorted(['Alpha Show/ep1.mp3', 'Alpha Show/ep1.mp3.part', 'Alpha Show/ep2.mp3', 'Alpha Show/ep2.mp3.part']) and title(m) == 'Alpha Show' and flags(m, 'btn_select') == (0, 0),
           f'Alpha Show: both files deleted; the page is empty, Select goes ({unlinks(m)})')
    expect(('widget_set_tr_text', m.widgets['label_status'], 'No downloaded episodes') in m.calls, 'and says so')
    PCP.click(m, 'btn_return')
    names = [t_ for _, t_, _ in lines(m)]
    expect('Alpha Show' not in names, f'Back: the Shows level no longer lists it ({names})')
    to_feeds(m)
    expect('Alpha Show' in [t_ for _, t_, _ in lines(m)], 'it is still in Feeds')

    # the Downloads level: a running row cannot be marked; Delete removes .part, failure and queue entry
    m = page()
    running(m)
    poke_slot(m, 1, SUB, 'c.mp3', 1, seq=2)
    poke_fail(m, 0, SUB, 'f.mp3', PN['CARDFULL'])
    to_feeds(m); PCP.tap(m, 150, ROW + 10)
    m.confirm_yes = True
    expect(flags(m, 'btn_select') == (1, 1), 'the Downloads level has Select')
    PCP.click(m, 'btn_select')
    mk = marks(m)
    expect(len(mk) == 3 and sorted(y for _, y, _ in mk) == sorted(r * ROW + (ROW - SG_MARK) // 2 for r in (1, 2, 3)), f'a mark on each row but the running one ({mk})')
    expect(all(x == O['LIST_ART_X'] + (O['SG_SEL_COL'] - 6 - SG_MARK) // 2 for x, _, _ in mk), 'in the list rows\' mark column')
    m.calls = []
    PCP.tap(m, 150, 10)
    expect(not [c for c in m.calls if c[0] == 'widget_set_text_utf8' and c[1] == m.widgets['label_title']], 'the running row cannot be marked')
    PCP.click(m, 'btn_selall'); m.calls = []
    PCP.click(m, 'pg_del')
    expect(confirms(m) == ['Remove the selected downloads?'], 'the confirm for downloads: "Remove the selected downloads?"')
    expect(sorted(unlinks(m)) == sorted([f'{SUB}/c.mp3.part', f'{SUB}/d.mp3.part', f'{SUB}/f.mp3.part']), f'each marked row loses its .part (the finished file is not touched) ({unlinks(m)})')
    expect(DL.state(m, 'c.mp3', SUB)[0] == 0 and DL.state(m, 'f.mp3', SUB)[0] == 0 and DL.state(m, 'e.mp3', SUB)[0] == 2, 'the waiting one left the queue, the failure is forgotten, the running one is untouched')
    expect([t_ for _, t_, _ in lines(m)] == ['Ep E'] and flags(m, 'pg_bar') == (0, 0), 'the page shows what is left; the mode ended')
    expect(f'{RP}/{SUB}/a.mp3' in m.fs and b'f=c.mp3' in m.fs[f'{RP}/{SUB}/.episodes'], 'the episodes stay remote (their lines are kept)')
    # a download finishing while rows are marked does not reload the list under the marks; and a dark tick does no visual work
    m = page(); to_feeds(m); PCP.tap(m, 150, 2 * ROW + 10); PCP.click(m, 'btn_select'); PCP.tap(m, 150, HDR + 10)
    m.setword(pn_at(12), 700); tick(m)
    expect(len(marks(m)) == 3 and len({b for _, _, b in marks(m)}) == 2, 'the generation moves while rows are marked: the rows and the marks stay as they are')
    m.screen(False); m.calls = []; m.setword(pn_at(12), 800)
    m.call(PSYMS['pg_tick'], a0=0, count=40000000)
    expect(not [c for c in m.calls if c[0] in ('widget_invalidate_force', 'widget_set_text_utf8', 'widget_set_visible')], 'screen off: a tick does no visual work in select mode')


def width_tests(ctx):
    expect = ctx.expect
    from awtk_text import Ttf, StbText
    font = Ttf(os.path.join(WORK, 'rootfs', 'release', 'assets', 'default', 'raw', 'fonts', 'default.ttf'))
    st = StbText(font, O['LIST_SUB_PX'] if 'LIST_SUB_PX' in O else 18)
    title = StbText(font, 22)
    room = O['SG_SELALL_X'] - O['NAV_TITLE_X']
    worst = []
    for loc in pod_i18n.LOCALES:
        t = pod_i18n.table_for(loc)
        tr = lambda key, t=t: pod_i18n.TEXT[key][t]
        worst.append((loc, round(title.layout(tr('%d Selected').replace('%d', '300'))[1]), round(st.layout(tr('No downloads'))[1]), round(st.layout(tr('The playing episode was kept'))[1]),
                      round(title.layout(tr('Downloads'))[1])))
    print('  widths in px per language (300 Selected in the', room, 'px title room, No downloads, the toast, the Downloads title):', worst)
    expect(all(w <= room for _, w, _, _, _ in worst), f'"300 Selected" fits the title room in every language ({[x for x in worst if x[1] > room]})')
    expect(all(w <= 280 for _, _, w, _, _ in worst), 'No downloads fits one line of the empty-state label')
    expect(all(w <= 300 for _, _, _, w, _ in worst), f'the toast fits 300 px in every language ({[x for x in worst if x[3] > 300]})')
    room_n = O['NAV_VIEW_X'] - O['NAV_TITLE_X']
    expect(all(w <= room_n for _, _, _, _, w in worst), f'the Downloads title fits the title room of {room_n} px ({[x for x in worst if x[4] > room_n]})')


SECTIONS = [downloads_tests, select_tests, width_tests]


def run(ctx):
    for f in SECTIONS: f(ctx)
