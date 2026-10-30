"""Podcasts, the Feeds level of the page (patch/podcasts.c with patch/pcnet.c, docs/modules/podcasts.md "Feeds"): the navbar button, the rows (Refresh All, Import, a row per subscription) and
their words, the status record read from the page's timer, Refresh All and Import through the real worker (a scripted libcurl), the Show level opened from Feeds (the episodes that are
not on the card greyed and silent), Back, and the empty hints. The compiled payload runs under Unicorn; the card is a dict of paths."""
import importlib.util, os, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

HERE = os.path.dirname(os.path.abspath(__file__))
FEEDS = os.path.join(ROOT, 'test', 'data', 'feeds')


def sibling(name):
    mod = sys.modules.get(f'podtest_{name}')
    if mod is None:
        spec = importlib.util.spec_from_file_location(f'podtest_{name}', os.path.join(HERE, name + '.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f'podtest_{name}'] = mod
        spec.loader.exec_module(mod)
    return mod


PCP, PCN = sibling('podcasts'), sibling('pcnet')
PN, CA = PCN.PN, PCN.CA
RP, ROW, HDR = PCP.ROOT, PCP.ROW, PCP.HDR
NOW = 1800000000
F = {k: f'https://f.example/{k}' for k in ('alpha', 'one', 'two', 'three')}
OK_NEW = 3     # a status: fresh items


def hash_of(s): return PCP.pc_hash(s)


def card(m):
    """Alpha Show (two files, a feed, refreshed an hour ago), bravo (files, no feed), Sub One (a feed, never refreshed, two episodes not downloaded), Sub Two (a feed, refreshed 2 days ago)."""
    PCP.page_card(m)
    m.put(f'{RP}/Alpha Show/.show', f'M1PLUS-SHOW 1\ntitle=Alpha Show\nfeed={F["alpha"]}\nimage=\nchecked={NOW - 3600}\n'.encode())
    m.put(f'{RP}/Sub One/.show', f'M1PLUS-SHOW 1\ntitle=Sub One\nfeed={F["one"]}\nimage=\nchecked=0\n'.encode())
    m.put(f'{RP}/Sub One/.episodes', (PCP.EPS_HEAD + f'g=s1\tp={NOW - 5000}\td=600\tl=1000\tf=a.mp3\tt=Remote A\tu=https://e/a.mp3\ng=s2\tp={NOW - 9000}\td=1200\tf=b.mp3\tt=Remote B\tu=https://e/b.mp3\n').encode())
    m.put(f'{RP}/Sub Two/.show', f'M1PLUS-SHOW 1\ntitle=Sub Two\nfeed={F["two"]}\nimage=\nchecked={NOW - 2 * 86400}\n'.encode())
    m.present.add(CA)
    m.wall = NOW


def opened(extra=None):
    def c(m):
        card(m)
        if extra: extra(m)
    m = PCP.opened(c, PCN.NM)
    m.curl_site = lambda url, o: {'rc': 6}
    return m


def pn_set(m, **kw):
    """Poke the worker's status record (patch/pcnet.c): busy, done, total, gen, cur and statuses=[(feed hash, code, fresh)]."""
    base = PSYMS['pn']
    for k, off in (('busy', 0), ('done', 4), ('total', 8), ('gen', 12), ('cur', 16)):
        if k in kw: m.setword(base + off, kw[k])
    for i, (feed, code, fresh) in enumerate(kw.get('statuses', [])):
        m.setword(base + 20 + 12 * i, feed); m.setword(base + 24 + 12 * i, fresh); m.setword(base + 28 + 12 * i, code)


def tick(m):
    m.screen(True)
    return m.call(PSYMS['pg_tick'], a0=0, count=40000000)


def rows(m, off=0):
    """{row: {'title': (text, x, w), 'sub': (text, x)}} of a frame at the Feeds / Shows level scrolled to off (a multiple of ROW)."""
    out = {}
    for t, (x, y, w, h) in PCP.drawn(m, off):
        r = (y + off) // ROW
        d = out.setdefault(r, {})
        if y % ROW == O['LIST_TITLE_Y']: d['title'] = (t, x, w)
        else: d['sub'] = (t, x)
    return out


def styled_rows(m):
    _, texts, styles, _ = PCP.paint(m)
    return [(t, r[0], r[1] // ROW, s) for (t, r), s in zip(texts, styles)]


def flags(m, name):
    return m.props.get((m.widgets[name], 'visible'), 1), m.props.get((m.widgets[name], 'sensitive'), 1)


def toasts(m): return [c[1] for c in m.calls if c[0] == 'toast']


def ep_titles(m):
    """[(title, style)] of the Show level's frame in row order: the header's name first, then the episodes (the page paints the titles and the grey titles in two passes)."""
    _, texts, styles, _ = PCP.paint(m)
    return [(t, s) for (t, r), s in sorted(zip(texts, styles), key=lambda e: e[0][1][1]) if s in ('label_row_title', 'label_row_dim')]


def run(ctx):
    expect = ctx.expect
    WSJ = open(os.path.join(FEEDS, 'wsj-3items.xml'), 'rb').read()
    HEAD = open(os.path.join(FEEDS, 'headlines-3items.xml'), 'rb').read()

    # 1. The Shows level: the offline library, and the Feeds button
    m = opened()
    expect([t for t, _, _, s in styled_rows(m) if s == 'label_row_title'] == ['Alpha Show', 'bravo'] and m.props.get((m.sv, 'virtual_h')) == 2 * ROW,
           'the Shows level lists what is on the card: Alpha Show and bravo, not the subscriptions with nothing downloaded')
    expect(flags(m, 'btn_feeds') == (1, 1) and m.props.get((m.widgets['btn_backtoplayer'], 'style:normal:icon')) == 'ah_nav_play',
           'the Feeds button is shown and sensitive on the Shows level, Now Playing the capsule\'s right cap')

    # 2. The Feeds level
    PCP.click(m, 'btn_feeds')
    expect(PCP.title_text(m) == 'Feeds' and flags(m, 'btn_feeds') == (0, 0) and m.props[(m.widgets['btn_backtoplayer'], 'style:normal:icon')] == 'ah_nav_np'
           and m.props[(m.widgets['btn_backtoplayer'], 'style:pressed:icon')] == 'ah_nav_np_down', 'Feeds: the title, the button hidden and out of the hit test, Now Playing the glass disc')
    expect(m.props.get((m.sv, 'virtual_h')) == 4 * ROW, 'Refresh All and three subscriptions: four rows')
    want = [('Refresh All', O['LIST_TITLE_Y'], 0, 'label_row_act'), ('1h ago', O['LIST_SUB_Y'], 0, 'label_row_sub'),
            ('Alpha Show', O['LIST_TITLE_Y'], 1, 'label_row_title'), ('Up to date \u00b7 1h ago', O['LIST_SUB_Y'], 1, 'label_row_sub'),
            ('Sub One', O['LIST_TITLE_Y'], 2, 'label_row_title'), ('Never refreshed', O['LIST_SUB_Y'], 2, 'label_row_sub'),
            ('Sub Two', O['LIST_TITLE_Y'], 3, 'label_row_title'), ('Up to date \u00b7 2d ago', O['LIST_SUB_Y'], 3, 'label_row_sub')]
    bl, texts, styles, fills = PCP.paint(m)
    got = sorted([(t, r[1] % ROW, r[1] // ROW, s) for (t, r), s in zip(texts, styles)], key=lambda x: (x[2], x[1]))
    expect(got == want, f'the rows: Refresh All (the action colour) with the last refresh, then Alpha Show, Sub One, Sub Two with their state: {got}')
    xs = {t: r[0] for (t, r) in texts}
    expect(xs['Refresh All'] == 16 and xs['1h ago'] == 16 and xs['Alpha Show'] == O['LIST_TEXT_X'] and xs['Never refreshed'] == O['LIST_TEXT_X'],
           'the action row\'s text starts at 16 px (no cover), a subscription\'s at the list\'s text column')
    covers = [b for b in bl if tuple(b[2][2:]) == (O['LIST_ART'], O['LIST_ART'])]
    expect([b[2][1] for b in covers] == [O['LIST_ART_Y'] + i * ROW for i in (1, 2, 3)], 'a cover (the placeholder disc) only in the three subscription rows')
    hair = sorted(f[1:] for f in fills if f[0] == O['LIST_HAIR'])
    expect(len(hair) == 4 and {h[0] for h in hair} == {16, O['LIST_TEXT_X']}, f'a hairline under each row, from 16 px under the action row and from the text column under the others ({hair})')

    # 3. The status record: a refresh moving on, the words of every result
    h = {k: hash_of(v) for k, v in F.items()}
    pn_set(m, busy=1, done=1, total=3, cur=h['one'], gen=7, statuses=[(h['alpha'], PN['OK'], 3)])
    tick(m)
    expect(rows(m)[0]['sub'][0] == 'Refreshing 1/3' and rows(m)[1]['sub'][0] == '3 new \u00b7 1h ago' and rows(m)[2]['sub'][0] == 'Refreshing', 'a refresh under way: "Refreshing 1/3" on Refresh All, "Refreshing" on the feed being fetched, "3 new \u00b7 1h ago" on the one that found three')
    expect(m.props[(m.sv, 'virtual_h')] == 4 * ROW, 'the rows were rebuilt from the same files')
    pn_set(m, busy=0, gen=8, cur=0, statuses=[(h['alpha'], PN['OK'], 0), (h['one'], PN['NOWIFI'], 0), (h['two'], PN['OK'], 0)])
    tick(m)
    r = rows(m)
    expect(r[1]['sub'][0] == 'Up to date \u00b7 1h ago' and r[2]['sub'][0] == 'No Wi-Fi' and r[3]['sub'][0] == 'Up to date \u00b7 2d ago' and r[0]['sub'][0] == '1h ago',
           'the worker ended: no new item is "Up to date", an error is its words alone (no time), the last refresh on Refresh All')
    words = {PN['NOWIFI']: 'No Wi-Fi', PN['NOCLOCK']: 'Set the date first', PN['NOCERT']: 'Certificates missing', PN['CERT']: 'Certificate problem', PN['NET']: "Can't connect", PN['GONE']: 'Feed not found',
             PN['HTTP']: 'Server error', PN['NOTFEED']: 'Not a podcast feed', PN['STORAGE']: 'Storage unavailable', PN['MEM']: 'Not enough memory'}
    for gen, (code, word) in enumerate(words.items(), 20):
        pn_set(m, gen=gen, statuses=[(h['one'], code, 0)])
        tick(m)
        expect(rows(m)[2]['sub'][0] == word, f'result {code}: "{word}"')
    pn_set(m, gen=40, statuses=[(h['one'], PN['OK'], 1)])
    tick(m)
    expect(rows(m)[2]['sub'][0] == '1 new', 'a first refresh with one new episode, no refresh time yet: "1 new"')
    pn_set(m, gen=41, statuses=[(h['one'], PN['OK'], 0)])
    tick(m)
    expect(rows(m)[2]['sub'][0] == 'Up to date', 'refreshed in this session, no time on the show file yet: "Up to date"')
    m.screen(False); pn_set(m, gen=50, statuses=[(h['one'], PN['NET'], 0)])
    m.call(PSYMS['pg_tick'], a0=0, count=40000000)
    expect(rows(m)[2]['sub'][0] == 'Up to date', 'screen off: the rows are not rebuilt (a lit tick does it)')

    # 4. Back: Feeds -> Shows -> out
    m = opened()
    PCP.click(m, 'btn_feeds')
    PCP.click(m, 'btn_return')
    expect(PCP.title_text(m) == 'Podcasts' and flags(m, 'btn_feeds') == (1, 1) and m.props[(m.widgets['btn_backtoplayer'], 'style:normal:icon')] == 'ah_nav_play' and 'navigator_back' not in m.names(),
           'Back from Feeds: the Shows level, the Feeds button back, Now Playing the capsule\'s right cap again')
    PCP.click(m, 'btn_return')
    expect('navigator_back' in m.names(), 'Back from the Shows level leaves the page')

    # 5. Refresh All: the guards, then the worker through the real page (Sub One has no .episodes yet: nothing in its folder is anyone's, so it may be renamed)
    m = opened(lambda mm: mm.fs.pop(f'{RP}/Sub One/.episodes'))
    PCP.click(m, 'btn_feeds')
    m.wifi = -1
    PCP.tap(m, 150, 10)
    expect(toasts(m) == ['No Wi-Fi'] and 'pthread_create' not in m.names(), 'Refresh All with no Wi-Fi: the toast says so, nothing starts')
    m.wifi = 4; m.wall = 1700000000
    PCP.tap(m, 150, 10)
    expect(toasts(m) == ['Set the date first'], 'a clock that was never set: "Set the date first"')
    m.wall = NOW; m.present.discard(CA)
    PCP.tap(m, 150, 10)
    expect(toasts(m) == ['Certificates missing'], 'no CA bundle: "Certificates missing"')
    m.present.add(CA); m.thread = None
    seen = []
    def site(url, o):
        seen.append(url)
        return {'body': {F['alpha']: WSJ, F['one']: HEAD}.get(url, b'<html></html>')}
    m.curl_site = site
    PCP.tap(m, 150, 10)
    expect(m.thread is not None and toasts(m) == [] and rows(m)[0]['sub'][0] == 'Refreshing 0/3', 'Refresh All: the worker starts (three feeds), the row says "Refreshing 0/3"')
    m.call(m.thread[0], a0=m.thread[1], count=1 << 40)
    expect([u for u in seen if u in F.values()] == [F['alpha'], F['one'], F['two']], 'the feeds are fetched in the order of the rows (a picture is requested after its feed)')
    tick(m)
    r = rows(m)
    titles = [r[i]['title'][0] for i in sorted(r)]
    expect(titles == ['Refresh All', 'Alpha Show', 'The Headlines', 'Sub Two'],
           f'the page rebuilt from the files the worker wrote: Sub One is "The Headlines" now (named by its feed, first refresh); order by title, a leading "The " aside: {titles}')
    expect([r[i]['sub'][0] for i in sorted(r)] == ['Just now', '3 new \u00b7 Just now', '3 new \u00b7 Just now', 'Not a podcast feed'],
           f'Refresh All "Just now"; Alpha Show 3 new (it had no .episodes); The Headlines 3 new; Sub Two an HTML page: "Not a podcast feed": {[r[i]["sub"][0] for i in sorted(r)]}')
    expect(f'{RP}/The Headlines/.episodes' in m.fs and f'{RP}/The Headlines/.show' in m.fs and not [p for p in m.fs if p.startswith(f'{RP}/Sub One/')],
           'the folder was renamed after the show the first time')
    m.calls = []
    PCP.tap(m, 150, 10)
    expect(m.thread is not None and m.names().count('pthread_create') == 1, 'a second Refresh All, once the first is done, starts again')
    pn_set(m, busy=1)
    m.calls = []
    PCP.tap(m, 150, 10)
    expect('pthread_create' not in m.names() and toasts(m) == [], 'while a refresh runs the row does nothing (no second thread, no toast)')
    m = opened()
    PCP.click(m, 'btn_feeds')
    m.curl_site = lambda url, o: {'body': HEAD if url == F['one'] else WSJ}
    m.thread = None
    PCP.tap(m, 150, 10)
    m.call(m.thread[0], a0=m.thread[1], count=1 << 40)
    show = m.fs.get(f'{RP}/Sub One/.show', b'')
    expect(b'\ntitle=The Headlines\n' in show and not [p for p in m.fs if p.startswith(f'{RP}/The Headlines/')],
           'a first refresh of a folder that already has an .episodes: the title is the feed\'s, the folder keeps its name')

    # 6. Import
    sub_txt = f'{RP}/subscriptions.txt'
    m = opened(lambda mm: mm.put(sub_txt, f'# mine\n{F["three"]}\n{F["alpha"]}\nhttps://f.example/four\n'.encode()))
    PCP.click(m, 'btn_feeds')
    r = rows(m)
    expect([r[i]['title'][0] for i in sorted(r)] == ['Refresh All', 'Import shows', 'Alpha Show', 'Sub One', 'Sub Two'] and r[1]['sub'][0] == 'Podcasts/subscriptions.txt',
           f'with subscriptions.txt on the card an Import row follows Refresh All ({[r[i]["title"][0] for i in sorted(r)]})')
    sr = styled_rows(m)
    expect([(t, s) for t, _, rw, s in sr if rw == 1] == [('Import shows', 'label_row_act'), ('Podcasts/subscriptions.txt', 'label_row_sub')], 'the Import row is an action row too')
    m.curl_site = lambda url, o: {'body': WSJ}
    m.thread = None
    PCP.tap(m, 150, ROW + 10)
    expect(toasts(m) == ['2 added'] and m.thread is not None, 'a tap on Import: the two new addresses are added (the one Alpha Show has is not), "2 added", and the shows never refreshed are refreshed')
    expect(f'{RP}/f.example-{hash_of(F["three"]):08x}/.show' in m.fs and f'{RP}/f.example-{hash_of("https://f.example/four"):08x}/.show' in m.fs, 'a folder and a show file for each, named by the host and the address\'s hash')
    r = {**rows(m), **rows(m, 2 * ROW)}   # (a frame paints the rows that touch the view: about six)
    expect(m.props.get((m.sv, 'virtual_h')) == 7 * ROW and [r[i]['title'][0] for i in sorted(r)] == ['Refresh All', 'Import shows', 'Alpha Show', 'f.example', 'f.example', 'Sub One', 'Sub Two'],
           f'the rows now: the new subscriptions are listed, titled by their host until refreshed ({[r[i]["title"][0] for i in sorted(r)]})')
    job = m.thread
    m.call(job[0], a0=job[1], count=1 << 40)
    expect(m.fs.get(sub_txt) is not None, 'subscriptions.txt is left alone')
    m.calls = []
    m.thread = None
    PCP.tap(m, 150, ROW + 10)
    expect(toasts(m) == ['Nothing new to import'] and m.thread is None, 'importing again: "Nothing new to import"')

    # 7. A feed opens the Show level, with the episodes that are not on the card greyed and silent
    m = opened()
    PCP.click(m, 'btn_feeds')
    PCP.tap(m, 150, 2 * ROW + 10)
    expect(PCP.title_text(m) == 'Sub One' and flags(m, 'btn_feeds') == (0, 0), 'a tap on a subscription opens its Show level')
    tt = ep_titles(m)
    expect(tt == [('Sub One', 'label_row_title'), ('Remote A', 'label_row_dim'), ('Remote B', 'label_row_dim')], f'the episodes not on the card are in the grey (played) style: {tt}')
    bl, *_ = PCP.paint(m)
    expect(not [b for b in bl if tuple(b[2][2:]) == (O['PC_DOT'], O['PC_DOT'])], 'and they have no unplayed dot')
    m.calls = []
    PCP.tap(m, 150, HDR + 10)
    expect('navigator_to_with_context' not in m.names() and toasts(m) == [], f'a tap on an episode that is not on the card does nothing (the download is the next step): {toasts(m)}')
    ring = m.ring()
    m.calls = []
    PCP.tap(m, 20, HDR + 10)
    expect(m.ring() == ring and toasts(m) == [], 'nor does a tap where the unplayed dot would be (it marks nothing)')
    PCP.click(m, 'btn_return')
    expect(PCP.title_text(m) == 'Feeds' and m.props[(m.sv, 'virtual_h')] == 4 * ROW and flags(m, 'btn_feeds') == (0, 0), 'Back from a Show opened from Feeds returns to Feeds')
    PCP.click(m, 'btn_return')
    expect(PCP.title_text(m) == 'Podcasts', 'and Back again to the Shows level')

    # 8. The same show from the Shows level lists only what is on the card; a mixed show plays only its files
    m = opened(lambda mm: (mm.put(f'{RP}/Alpha Show/.episodes', (PCP.EPS_HEAD + f'g=r1\tp={NOW}\tf=new.mp3\tt=Not yet\tu=https://e/n.mp3\ng=e1\tp={T0_(1)}\tf=ep1.mp3\tt=One\ng=e2\tp={T0_(2)}\tf=ep2.mp3\tt=Two\n').encode())))
    PCP.tap(m, 150, 10)   # Alpha Show on the Shows level
    tt = [t for t, _ in ep_titles(m)]
    expect(tt[1:] == ['Two', 'One'], f'from the Shows level only the files are listed ({tt})')
    PCP.click(m, 'btn_return')
    PCP.click(m, 'btn_feeds')
    PCP.tap(m, 150, 1 * ROW + 10)
    tt = ep_titles(m)
    expect(tt[1:] == [('Not yet', 'label_row_dim'), ('Two', 'label_row_title'), ('One', 'label_row_title')], f'from Feeds the episode that is not on the card is listed too, newest first, grey ({tt})')
    m.calls = []
    PCP.tap(m, 150, HDR + 1 * ROW + 10)   # "Two": the first file
    ctxs = [c for c in m.calls if c[0] == 'navigator_to_with_context']
    q, idx = m.played
    paths = [m.read_cstr(m.word(rec + O['REC_PATH'])) for rec in q]
    expect(len(ctxs) == 1 and paths == [f'{RP}/Alpha Show/ep2.mp3', f'{RP}/Alpha Show/ep1.mp3'] and idx == 0,
           f'a file is played with the queue of the files only (two), not the episode that is not on the card ({paths}, {idx})')

    # 9. The hints
    m = PCP.opened(lambda mm: mm.folder('/mnt/mmc/Music'), PCN.NM)
    expect(('widget_set_tr_text', m.widgets['label_status'], 'No podcasts. Copy a folder for each show into Podcasts on the card, or subscribe in Feeds, at the top right.') in m.calls, 'nothing at all: the hint names Feeds')
    m = opened(lambda mm: [mm.fs.pop(p) for p in list(mm.fs) if '/Alpha Show/' in p or '/bravo/' in p])
    expect(('widget_set_tr_text', m.widgets['label_status'], 'Nothing downloaded yet. Open Feeds, at the top right.') in m.calls, 'subscriptions and no file: "Nothing downloaded yet. Open Feeds, at the top right."')
    m = PCP.opened(lambda mm: mm.put(f'{RP}/Only/o.mp3', b'x', 5), PCN.NM)
    PCP.click(m, 'btn_feeds')
    expect(('widget_set_tr_text', m.widgets['label_status'], 'No subscriptions. List one feed address per line in subscriptions.txt in Podcasts on the card, then open Feeds again.') in m.calls
           and m.props.get((m.widgets['label_status'], 'visible')) == 1, 'no subscription and no subscriptions.txt: the Feeds level says how to start')
    m = PCP.opened(lambda mm: (mm.put(f'{RP}/Only/o.mp3', b'x', 5), mm.put(f'{RP}/subscriptions.txt', b'https://x.example/rss\n')), PCN.NM)
    PCP.click(m, 'btn_feeds')
    r = rows(m)
    expect([r[i]['title'][0] for i in sorted(r)] == ['Import shows'] and m.props.get((m.widgets['label_status'], 'visible'), 0) == 0, 'subscriptions.txt and no subscription yet: just the Import row (no Refresh All)')
    # no memory for the page's shows
    m = PCP.page_machine(card, PCN.NM)
    m.calloc_fail = True
    m.call(PSYMS['podcasts_open'], count=40000000)
    expect(('widget_set_tr_text', m.widgets['label_status'], 'Not enough memory') in m.calls, 'no memory: the page says so (as before)')


def T0_(i): return PCP.T0 + i * PCP.DAY
