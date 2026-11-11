"""The Show page's recent list and the All Episodes page (docs/modules/podcasts.md "All episodes", "The All Episodes page"): the Show page paints the first 20 rows of .episodes and the files, ends with See All / See All (N),
a tap opens the page with the complete list (the archive's union), Back returns to the Show page's scroll; the search inside a show covers the complete list; the cross-show readers never read .archive. The compiled
payload runs under Unicorn against the Show page's machine (test/pod/pcshow.py)."""
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

PSH = sibling('pcshow')
PCP, PCN, DL = PSH.PCP, PSH.PCN, PSH.DL
PCA = sibling('pcarchive')
RP, DEEP, CELL, NOW, DAY = PSH.RP, PSH.DEEP, PCP.CELL, PSH.NOW, 86400
MORE_H, SHOW_MAX = O['PS_MORE_H'], O['PS_SHOW_MAX']


def card(n_recent=30, n_arch=0, files=(), feed=True, arch_items=None, extra=()):
    """A Deep show with n_recent entries in .episodes (e0 newest .. e<n-1>), the files of `files` on the card, and, when n_arch, an .archive of the same n_recent entries and n_arch older ones (a0 .. )."""
    def make(mm):
        es = [PSH.entry(i) for i in range(n_recent)]
        PSH.deep_card(mm, feed=feed, entries=es, files=files)
        for f in extra: mm.put(f'{RP}/{DEEP}/{f}', b'audio')   # (files only the archive knows)
        if n_arch or arch_items is not None:
            older = [PSH.entry(1000 + i, g=f'a{i}', p=NOW - (200 + i) * DAY, f=f'a{i}.mp3', t=f'Old {i}', u=f'https://cdn.example/a{i}.mp3') for i in range(n_arch)]
            mm.put(f'{RP}/{DEEP}/.archive', PSH.eps_text(arch_items if arch_items is not None else es + older))
    return make


def machine(**kw):
    m = PSH.machine(card=card(**kw)); PSH.open_show(m)
    return m


def bottom(m): return max(0, m.props[(m.sv, 'virtual_h')] - 400)


def rows(m, off=None):
    """The episode titles painted on the list, top to bottom (the list scrolled a screen at a time), and the See All row's text ('' for none)."""
    h, out, more = m.props[(m.sv, 'virtual_h')], {}, ''
    for off in range(0, max(1, h), 120):
        _, texts, styles, _ = PCP.paint(m, off)
        for (t, r), s in zip(texts, styles):
            y = r[1] + off
            if s in ('label_ps_ctitle', 'label_ps_cdim'):
                if t.startswith('See All') or t.startswith('Loading') or t.endswith('Tap to Retry'): more = t
                else: out.setdefault(y, t)
    return [t for _, t in sorted(out.items())], more


def see_all(m, n=SHOW_MAX):
    """A tap on the See All row (under the n-th cell: the Show page shows 20 at most)."""
    PCP.tap(m, 150, PCP.hdr(m) + n * CELL + MORE_H // 2, off=bottom(m))


def is_page(m):
    """The All Episodes page: no header (no Episodes heading) and the show's name in the navbar."""
    _, texts, styles, _ = PCP.paint(m, 100)
    return not [1 for s in styles if s == 'label_ps_head'] and m.props.get((m.widgets['label_title'], 'visible'), 0)


def reads(m, name='.archive'):
    """The opens and reads of a file of that name since m.calls was last cleared."""
    return [c for c in m.calls if c[0] in ('open', 'fopen', 'read') and isinstance(c[1], str) and c[1].endswith(name)]


def order(m, n=1):
    PCP.click(m, 'btn_more')
    PCP.click(m, 'pg_sh_order')
    PCP.click(m, 'pg_sh_scrim')


def filt(m, n):
    PSH_to = sibling('pcfilter').to_filter
    PSH_to(m, n)


def show_tests(ctx):
    expect = ctx.expect
    m = machine()
    titles, more = rows(m)
    expect(titles == [f'Episode {i}' for i in range(20)] and more == 'See All' and m.props[(m.sv, 'virtual_h')] == PCP.hdr(m) + 20 * CELL + MORE_H + 20,
           f'30 recent entries, a feed, no archive: the first 20 rows and the See All row ({len(titles)}, {more!r})')
    order(m)
    titles, more = rows(m)
    expect(titles == [f'Episode {i}' for i in range(29, 9, -1)] and more == 'See All', f'Oldest First: the first 20 rows of the reversed list ({titles[:2]}..{titles[-1:]})')
    order(m)
    m = machine(files=range(25))
    filt(m, 2)
    titles, more = rows(m)
    expect(len(titles) == 20 and titles[0] == 'Episode 0' and more == 'See All', f'Downloaded: 25 rows, 20 shown ({len(titles)})')
    filt(m, 1)
    titles, more = rows(m)
    expect(len(titles) == 20 and more == 'See All', f'Unplayed: 20 rows shown ({len(titles)}, {more})')
    # a short list still has the row for a subscription with no archive
    m = machine(n_recent=5)
    titles, more = rows(m)
    expect(len(titles) == 5 and more == 'See All', 'five entries, no archive: the row is there (the count is not known)')
    # with an archive the row says how many
    m = machine(n_arch=40)
    titles, more = rows(m)
    expect(len(titles) == 20 and more == 'See All (70)', f'an archive of 70 (30 recent + 40 older): See All (70) ({more!r})')
    m = machine(n_recent=10, n_arch=0, arch_items=[PSH.entry(i) for i in range(10)])
    titles, more = rows(m)
    expect(len(titles) == 10 and more == '' and m.props[(m.sv, 'virtual_h')] == PCP.hdr(m) + 10 * CELL + 20, 'an archive no longer than the rows shown and no Filter: no row')
    filt(m, 1)
    titles, more = rows(m)
    expect(more == 'See All (10)', f'the same under a Filter: the row is there ({more!r})')
    m = machine(n_recent=30, arch_items=[PSH.entry(i) for i in range(30)])
    titles, more = rows(m)
    expect(len(titles) == 20 and more == 'See All (30)', f'30 recent and the same 30 in the archive: See All (30) ({more!r})')
    # a show with no feed: See All (N) when there are more than 20, no row otherwise
    m = machine(n_recent=25, feed=False, files=range(25))
    titles, more = rows(m)
    expect(len(titles) == 20 and more == 'See All (25)', f'copied files, 25 episodes: See All (25) ({more!r})')
    m = machine(n_recent=15, feed=False, files=range(15))
    titles, more = rows(m)
    expect(len(titles) == 15 and more == '', 'copied files, 15 episodes: no row')


def page_tests(ctx):
    expect = ctx.expect
    m = machine(n_arch=40)   # 30 recent + 40 older = 70
    m.curl_site_calls = []
    seen = []
    m.curl_site = lambda url, o: (seen.append(url), {'body': b''})[1]
    off = bottom(m)
    see_all(m)
    expect(not seen and is_page(m), 'a tap on See All (70) opens the All Episodes page with no request')
    expect((PCP.title_text(m) or '').startswith('All-In with') and m.props.get((m.widgets['label_title'], 'visible')), f'its navbar title is the show\'s name, shown at the top ({PCP.title_text(m)!r})')
    titles, more = rows(m)
    expect(len(titles) == 70 and more == '' and titles[:3] == ['Episode 0', 'Episode 1', 'Episode 2'] and titles[-1] == 'Old 39' and m.props[(m.sv, 'virtual_h')] == 70 * CELL + 20,
           f'every episode of the complete list, in order, no See All row ({len(titles)}: {titles[:1]}..{titles[-1:]})')
    expect(m.props.get((m.sv, 'yoffset'), 0) == 0, 'the list starts at the top')
    # Back: the Show page at its scroll offset
    PCP.click(m, 'btn_return')
    titles, more = rows(m)
    expect(not is_page(m) and len(titles) == 20 and more == 'See All (70)' and m.props.get((m.sv, 'yoffset')) == off, f'Back: the Show page, its 20 rows and its offset ({m.props.get((m.sv, "yoffset"))} of {off})')
    # Oldest First on the page: the exact reverse, saved (the Show page follows)
    see_all(m)
    order(m)
    titles, _ = rows(m)
    expect(len(titles) == 70 and titles[0] == 'Old 39' and titles[-1] == 'Episode 0', f'Oldest First: the complete list reversed ({titles[:1]}..{titles[-1:]})')
    PCP.click(m, 'btn_return')
    titles, more = rows(m)
    expect(titles[0] == 'Episode 29' and len(titles) == 20 and more == 'See All (70)', f'and the Show page is Oldest First too: the 20 first rows of its recent list ({titles[:1]})')


PCD = sibling('pcdetail')
SEL = sibling('pcsel')


def hash_of(f): return PCP.pc_hash(f'{RP}/{DEEP}/{f}')


def ep_page_title(m):
    return [t for s, t, x, y in sorted(PCD.page_texts(m), key=lambda a: a[3]) if s == 'label_ps_head']


def paths(m): return [m.read_cstr(m.word(r + O['REC_PATH'])).rsplit('/', 1)[1] for r in m.played[0]]


def to_all(m):
    see_all(m, min(20, 30))


def flow_tests(ctx):
    expect = ctx.expect
    kw = dict(n_arch=40, files=(0,), extra=('a5.mp3',))
    # an old episode downloaded from the complete list is a local file of the recent list, with its title and date from .archive
    m = machine(**kw)
    expect(m.props[(m.sv, 'virtual_h')] == PCP.hdr(m) + 20 * CELL + MORE_H + 20, 'the Show page paints 20 rows')
    filt(m, 2)
    titles, more = rows(m)
    expect(titles == ['Episode 0', 'Old 5'] and more == 'See All (70)', f'the Show page under Downloaded: the file only the archive lists is there with its title ({titles})')
    # the sheets: the Show page's keeps Refresh Feed and Unsubscribe, the All Episodes page has neither
    rws, *_ = PSH.show_sheet(m)
    expect(rws == ['speed', 'order', 'filter', 'refresh', 'select', 'markall', 'unsub'], f'the Show page\'s sheet ({rws})')
    PCP.click(m, 'pg_sh_scrim')
    see_all(m, 2)
    expect(is_page(m), 'See All under a Filter opens the page')
    titles, more = rows(m)
    expect(titles == ['Episode 0', 'Old 5'] and more == '', f'the page keeps the Filter (Downloaded): ({titles})')
    rws, *_ = PSH.show_sheet(m)
    expect(rws == ['speed', 'order', 'filter', 'select', 'markall'], f'the All Episodes page\'s sheet has no Refresh Feed and no Unsubscribe ({rws})')
    PCP.click(m, 'pg_sh_filter')   # Downloaded -> All
    PCP.click(m, 'pg_sh_scrim')
    titles, _ = rows(m)
    expect(len(titles) == 70, f'changing the Filter on the page changes the list ({len(titles)})')
    PCP.click(m, 'btn_return')
    PCP.click(m, 'btn_more')
    expect(PSH.text_of(m, 'pg_sh_filter_vl') == 'All', 'and the Show page: the same Filter state')
    PCP.click(m, 'pg_sh_scrim')
    # the episode page of an episode only the archive lists, and back
    m = machine(**kw)
    see_all(m)
    y = 40 * CELL
    PCP.tap(m, 150, y + 12, off=y - 100)
    expect(ep_page_title(m) == ['Old 10'], f'a tap on the row of Old 10 opens its episode page ({ep_page_title(m)})')
    PCP.click(m, 'btn_return')
    expect(is_page(m) and m.props.get((m.sv, 'yoffset')) == y - 100, f'Back from it: the All Episodes page at the same scroll offset ({m.props.get((m.sv, "yoffset"))})')
    # the downloaded one plays; its queue is the files in the list's order
    m.calls = []
    y = 31 * CELL   # (row 31: Old 0 .. ; Old 5 is row 35)
    PCP.tap(m, 30, 35 * CELL + O['PS_PILL_Y'] + O['PS_PILL_H'] // 2, off=35 * CELL - 100)
    expect(paths(m) == ['e0.mp3', 'a5.mp3'] and m.played[1] == 1, f'playing Old 5 from the page queues the files of the list ({paths(m)}, {m.played[1]})')
    # Mark All as Played: the Show page marks its recent list, the page marks every episode
    m = machine(**kw)
    PCP.click(m, 'btn_more'); PCP.click(m, 'pg_sh_markall')
    st = [m.state(hash_of(f'e{i}.mp3'))[0] for i in range(30)] + [m.state(hash_of(f'a{i}.mp3'))[0] for i in range(40)]
    expect(st[:30] == [2] * 30 and [i for i, v in enumerate(st[30:]) if v == 2] == [5], f'Mark All as Played on the Show page: the recent list (30 episodes and the downloaded Old 5), not the archive\'s other episodes ({st.count(2)} played)')
    m = machine(**kw)
    see_all(m)
    PCP.click(m, 'btn_more'); PCP.click(m, 'pg_sh_markall')
    st = [m.state(hash_of(f'e{i}.mp3'))[0] for i in range(30)] + [m.state(hash_of(f'a{i}.mp3'))[0] for i in range(40)]
    expect(st == [2] * 70, f'on the All Episodes page: all 70 ({st.count(2)} played)')
    # select mode on the page: the rows of the page, Select All, Delete reaches the archive-only file
    m = machine(**kw)
    see_all(m)
    SEL.start_select(m)
    mk = SEL.all_marks(m)
    expect(sorted(mk) == [0, 35], f'select mode on the page: a mark on the two rows with a file (rows {sorted(mk)})')
    PCP.click(m, 'btn_selall')
    expect(PCP.title_text(m) == '2 Selected', 'Select All marks the rows that can be')
    m.confirm_yes = True; m.calls = []
    PCP.click(m, 'pg_del')
    expect(f'{RP}/{DEEP}/a5.mp3' not in m.fs and f'{RP}/{DEEP}/e0.mp3' not in m.fs, 'Delete removes both files')
    titles, _ = rows(m)
    expect(is_page(m) and len(titles) == 70, f'the page is read again (the complete list, {len(titles)} rows)')


def feed_of(n, prefix='f'):
    """A feed of n items newer than nothing in .episodes: guids f<i> (the Deep entries have g<i>), newest first, as the job writes them."""
    items = [PCA.item(i).replace(f'<guid>g{i}</guid>', f'<guid>{prefix}{i}</guid>') for i in range(n, 0, -1)]
    return PCA.feed(items)


def finish_job(m):
    m.call(m.thread[0], a0=m.thread[1], count=1 << 40)
    m.call(PSYMS['pg_tick'], a0=0, count=40000000)


def fetch_tests(ctx):
    expect = ctx.expect
    # a subscription with no archive: See All starts the fetch (the guards, Loading…, the spinner are the Show All Episodes row\'s) and the All Episodes page opens when the job ends well
    m = machine(n_recent=30)
    xml = feed_of(40)
    seen = []
    m.curl_site = lambda url, o: (seen.append(url), {'body': xml})[1]
    m.thread = None
    off = bottom(m)
    see_all(m)
    expect(m.thread and m.thread[0] == PSYMS['pn_armain'] and not is_page(m), 'a tap on See All starts the job; the Show page stays while it runs')
    titles, more = rows(m)
    expect(more.startswith('Loading') and len(titles) == 20, f'the row reads Loading… ({more!r})')
    finish_job(m)
    titles, more = rows(m)
    expect(is_page(m) and len(titles) == 70 and more == '' and len(seen) == 1, f'the job ended: the All Episodes page is open with all 70 episodes, one request ({len(titles)}, {len(seen)})')
    PCP.click(m, 'btn_return')
    titles, more = rows(m)
    expect(not is_page(m) and len(titles) == 20 and more == 'See All (70)' and m.props.get((m.sv, 'yoffset')) == off, f'Back: the Show page at its offset, the row now has the count ({more!r})')
    # the job failing: the row says so and keeps See All's retry, no page
    m = machine(n_recent=30)
    m.curl_site = lambda url, o: {'rc': 6}
    m.thread = None
    see_all(m)
    finish_job(m)
    titles, more = rows(m)
    expect(not is_page(m) and more.endswith('Tap to Retry'), f'a failed job: no page, the row says why ({more!r})')
    # the user left meanwhile: nothing opens, the row reads See All (N) next time
    for how in ('shows', 'episode'):
        m = machine(n_recent=30)
        m.curl_site = lambda url, o: {'body': xml}
        m.thread = None
        see_all(m)
        if how == 'shows': PCP.click(m, 'btn_return')
        else: PCP.body(m, 0)
        finish_job(m)
        if how == 'shows':
            expect(PCP.title_text(m) == 'Podcasts' and f'{RP}/{DEEP}/.archive' in m.fs, 'left for the Shows level while the job ran: it ended and nothing opened')
            PSH.open_show(m)
        else:
            expect(not is_page(m) and ep_page_title(m), 'on an episode page while the job ran: the page stays')
            PCP.click(m, 'btn_return')
        titles, more = rows(m)
        expect(not is_page(m) and more == 'See All (70)', f'{how}: the Show page now reads See All (70) ({more!r})')
    # with an archive, a tap starts nothing
    m = machine(n_arch=40)
    m.thread = None
    see_all(m)
    expect(m.thread is None and is_page(m), 'with an archive no job starts')


PF = sibling('pcfind')


def to_show_page(m):
    """The search page closed (the harness's navigator_back destroys nothing): the Show page is in front again."""
    m.call(PSYMS['pf_on_destroy'], count=2000000)
    m.sv, m.view = m.psv, m.pview
    m.call(PSYMS['pg_on_fg'], a0=0, a1=0, count=40000000)


def search_tests(ctx):
    """The search inside a show covers the complete list when the show has an archive, from the Show page and from the All Episodes page; Back from a result's episode page opens the search again; closing it leaves the page
    that was under it with its own list (the Show page's 20 rows, the All Episodes page's 70)."""
    expect = ctx.expect
    kw = dict(n_arch=40, files=(0,))
    for where in ('Show page', 'All Episodes page'):
        m = PSH.machine(card=card(**kw)); PSH.open_show(m)
        m = PF.find_widgets(m)
        if where == 'All Episodes page': see_all(m)
        off = m.props.get((m.sv, 'yoffset'), 0)
        PF.click_find(m)
        PF.typed(m, 'old')
        expect([t for t, _, _ in PF.rows(m, 45)] == [f'Old {i}' for i in range(40)], f'{where}: the search finds the 40 episodes only the archive lists')
        expect(PF.found(m, 'old 3') == ['Old 3'] and PF.found(m, 'episode 7') == ['Episode 7'], f'{where}: a whole number, and an episode of the recent list')
        PF.typed(m, 'old')
        PF.tap_row(m, 12)
        m.call(PSYMS['pf_on_destroy'], count=2000000)
        m.sv, m.view = m.psv, m.pview
        expect(ep_page_title(m) == ['Old 12'], f'{where}: a result opens its episode page ({ep_page_title(m)})')
        m.calls = []
        PCP.click(m, 'btn_return')
        expect(('window_open', 'm1plus_pcfind') in m.calls, f'{where}: Back from the episode page opens the search again')
        m.sv, m.view = m.psv, m.pview
        expect([t for t, _, _ in PF.rows(m, 45)][:2] == ['Old 0', 'Old 1'] and len(PF.rows(m, 45)) == 40, f'{where}: with its text and results')
        PCP.click(m, 'pf_close')
        to_show_page(m)
        titles, more = rows(m)
        if where == 'Show page':
            expect(len(titles) == 20 and more == 'See All (70)' and not is_page(m), f'closing the search: the Show page with its 20 rows ({len(titles)}, {more!r})')
        else:
            expect(len(titles) == 70 and more == '' and is_page(m), f'closing the search: the All Episodes page with its 70 rows ({len(titles)})')
        expect(m.props.get((m.sv, 'yoffset'), 0) == off, f'{where}: at its scroll offset')
    # the episode page of a result and its show row: the Show page again, with its recent list
    m = PSH.machine(card=card(**kw)); PSH.open_show(m)
    m = PF.find_widgets(m)
    PF.click_find(m)
    PF.found(m, 'old 3')
    PF.tap_row(m, 0)
    m.call(PSYMS['pf_on_destroy'], count=2000000)
    m.sv, m.view = m.psv, m.pview
    PCD.tap_show_row(m)
    titles, more = rows(m)
    expect(not PCD.is_page(m) and len(titles) == 20 and more == 'See All (70)', f'the episode page\'s show row: the Show page with its recent list ({len(titles)}, {more!r})')
    # a show with no archive: the search holds the recent list (and its own Search All Episodes row); the page does not read .archive
    m = PSH.machine(card=card(n_recent=30)); PSH.open_show(m)
    m = PF.find_widgets(m)
    PF.click_find(m)
    expect(len(PF.found(m, 'episode')) == 30 and not reads(m), 'no archive: the 30 recent episodes (and the row that fetches)')


def downloaded_rows(m):
    """The titles of the Downloaded page's rows once the scan has run (a show a tick)."""
    PCP.tap_downloads(m)
    for _ in range(20): m.call(PSYMS['pg_on_load'], a0=0, count=400000000)
    return sorted(t for t, _ in PCP.drawn(m, 0, 'label_row_title'))


def readers_tests(ctx):
    """The pages that read many shows (Shows, Downloaded) and a reload of the Show page never read .archive unless a file on the card has no .episodes entry; a downloaded old episode shows with its title."""
    expect = ctx.expect
    kw = dict(n_arch=40, files=(0,))
    m = machine(**kw)
    m.calls = []
    sibling('pcfilter').bump(m)
    DL.tick(m)
    PCP.paint(m, 0)
    expect(not reads(m), 'a reload of the Show page (a download finished) does not read .archive: the count is kept')
    PCP.click(m, 'btn_return')
    PCP.paint(m, 0)
    expect(not reads(m), 'the Shows page does not read .archive')
    rws = downloaded_rows(m)
    expect(not reads(m) and 'Episode 0' in rws and not [t for t in rws if t.startswith('Old')], f'the Downloaded page does not read .archive when every file has its entry ({rws})')
    m = machine(**dict(kw, extra=('a5.mp3',)))
    PCP.click(m, 'btn_return')
    m.calls = []
    rws = downloaded_rows(m)
    expect('Episode 0' in rws and 'Old 5' in rws and 'Old 6' not in rws and 'a5' not in rws, f'a downloaded episode only the archive lists is a Downloaded row with its title ({rws})')
    # Continue Listening: the same episode, half played
    m = machine(**dict(kw, extra=('a5.mp3',)))
    m.call(PSYMS['pc_mark'], a0=hash_of('a5.mp3'), a1=0, count=2000000)
    h = hash_of('a5.mp3')
    m.pt = (1500, 3600, 1); m.status = 2
    m.play([m.record(path=f'{RP}/{DEEP}/a5.mp3')], 0); m.clock += 40000
    m.call(PSYMS['pc_note'], a0=m.record(path=f'{RP}/{DEEP}/a5.mp3'), count=40000000)
    expect(m.state(h)[0] == 1, 'a place on the downloaded old episode')
    PCP.click(m, 'btn_return')
    sibling('pcfilter').bump(m); DL.tick(m)
    cont = [t for t, _ in PCP.drawn(m, 0, 'label_ps_stitle')]
    expect('Old 5' in cont, f'Continue Listening finds it with its title ({cont})')
    # a show of copied files with more than 20 episodes: See All (N) opens the page over its local list, no request
    m = machine(n_recent=25, feed=False, files=range(25))
    seen = []
    m.curl_site = lambda url, o: (seen.append(url), {'body': b''})[1]
    see_all(m)
    titles, more = rows(m)
    expect(is_page(m) and len(titles) == 25 and more == '' and not seen, f'copied files: See All (25) opens the page with the 25 local episodes ({len(titles)})')


SECTIONS = [show_tests, page_tests, flow_tests, fetch_tests, search_tests, readers_tests]
