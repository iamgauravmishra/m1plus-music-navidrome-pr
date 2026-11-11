"""The Show page's Filter (patch/podcasts.c pg_vis_make / pg_ix, docs/modules/podcasts.md "Filter"): the sheet's row and its three values, the rows each value leaves (in the show's order, under both orders),
the Filter as page state (reset when the show is left, kept across the episode page), the row to episode mapping of hit testing, the episode page, the queue, select mode, Mark All as Played and Delete, the empty
hints, and what ignores it (the Latest Episode pill, the search inside the show). The compiled payload runs under Unicorn against the Show page's machine (test/pod/pcshow.py): the Deep show has eight episodes, e0
on the card unplayed, e1 on the card played, e2 on the card started, e3 .. e7 not on the card (so Unplayed leaves seven rows, Downloaded three)."""
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

PSH = sibling('pcshow')
PCP, PCN, DL = PSH.PCP, PSH.PCN, PSH.DL
SEL = sibling('pcsel')
PCD = sibling('pcdetail')
PF = sibling('pcfind')
RP, DEEP, CELL = PSH.RP, PSH.DEEP, PCP.CELL


def ids(m):
    """The episode numbers of the rows now, from their titles ("Episode 3"; e0's long title is the one starting Trump)."""
    cells = PCP.all_cells(m)
    return [0 if c['title'][0].startswith('Trump') else int(c['title'][0].split()[1]) for _, c in sorted(cells.items())]


def to_filter(m, n):
    """Open the sheet, tap Filter until its value is the n-th (0 All, 1 Unplayed, 2 Downloaded), close the sheet."""
    PCP.click(m, 'btn_more')
    for _ in range(n): PCP.click(m, 'pg_sh_filter')
    PCP.click(m, 'pg_sh_scrim')


def h_of(p): return PCP.pc_hash(f'{RP}/{DEEP}/e{p}.mp3')


def bump(m):
    """The worker moved (pn_gen): the tick reads the show's episodes again."""
    m.setword(DL.pn_at(12), m.word(DL.pn_at(12)) + 100)


def hint(m): return PCP.hint(m, PCP.hdr(m))   # (the hint is under the header, below a 400 px view at the top)


def sheet_tests(ctx):
    """The row after Episode Order with its grey value; a tap cycles All, Unplayed, Downloaded and back; the sheet stays; nothing is written."""
    expect = ctx.expect
    m = PSH.shown()
    rows, h, glass, _ = PSH.show_sheet(m)
    expect(rows[:3] == ['speed', 'order', 'filter'] and PSH.text_of(m, 'pg_sh_filter_tx') == 'Filter' and PSH.text_of(m, 'pg_sh_filter_vl') == 'All', f'Filter follows Episode Order and says All ({rows})')
    expect(h == 350 and glass == 'pc_sheet7' and ('widget_move', m.widgets['pg_sh_card'], 0, 100) in m.calls, f'the sheet is seven rows, 350 px, on the 450 px window ({h}, {glass})')
    expect(('widget_resize', m.widgets['pg_sh_filter_vl'], PSH.font().width('All', 18), 50) in m.calls, 'its value label is as wide as the text, as Episode Order\'s')
    files = set(m.fs)
    seq = []
    for _ in range(4):
        PCP.click(m, 'pg_sh_filter')
        seq.append(PSH.text_of(m, 'pg_sh_filter_vl'))
    expect(seq == ['Unplayed', 'Downloaded', 'All', 'Unplayed'] and PSH.flags(m, 'pg_sh_card') == (1, 1), f'a tap cycles All, Unplayed, Downloaded and the sheet stays ({seq})')
    expect(set(m.fs) == files and m.fs.get(PCP.ORDER) is None, 'nothing is written to the card (the Filter is page state)')
    # the value labels of both rows do not disturb each other
    expect(PSH.text_of(m, 'pg_sh_order_vl') == 'Newest First' and PSH.text_of(m, 'pg_sh_speed_vl') == '1×', 'Episode Order and Playback Speed keep their values')
    PCP.click(m, 'pg_sh_scrim')
    PCP.click(m, 'btn_more')
    expect(PSH.text_of(m, 'pg_sh_filter_vl') == 'Unplayed', 'the sheet opens on the Filter in force')
    # a show with no episode has no Filter row
    m = PSH.machine(entries=[]); PSH.open_show(m)
    rows, *_ = PSH.show_sheet(m)
    expect('filter' not in rows, 'no episode: no Filter row')


def rows_tests(ctx):
    """The rows each value leaves, newest first and oldest first; the cells; the content's height."""
    expect = ctx.expect
    m = PSH.shown()
    expect(ids(m) == list(range(8)), f'All: the eight episodes ({ids(m)})')
    full_h = m.props[(m.sv, 'virtual_h')]
    to_filter(m, 1)
    expect(ids(m) == [0, 2, 3, 4, 5, 6, 7], f'Unplayed: every episode that is not marked played, a started one too, in the show\'s order ({ids(m)})')
    expect(m.props[(m.sv, 'virtual_h')] == full_h - CELL and not any(c['played'] for c in PCP.all_cells(m).values()), 'one cell shorter; no played title')
    to_filter(m, 1)
    expect(ids(m) == [0, 1, 2] and m.props[(m.sv, 'virtual_h')] == full_h - 5 * CELL, f'Downloaded: the files on the card ({ids(m)})')
    expect([c['played'] for _, c in sorted(PCP.all_cells(m).items())] == [False, True, False], 'e1 is played: its title is grey')
    to_filter(m, 1)
    expect(ids(m) == list(range(8)), 'and back to All')
    # oldest first: the same rows, reversed
    PCP.click(m, 'btn_more'); PCP.click(m, 'pg_sh_order'); PCP.click(m, 'pg_sh_filter')
    expect(ids(m) == [7, 6, 5, 4, 3, 2, 0], f'Oldest First and Unplayed ({ids(m)})')
    PCP.click(m, 'pg_sh_filter')
    expect(ids(m) == [2, 1, 0], f'Oldest First and Downloaded ({ids(m)})')
    PCP.click(m, 'pg_sh_order')
    expect(ids(m) == [0, 1, 2], f'Episode Order back to Newest First keeps the Downloaded filter ({ids(m)})')
    PCP.click(m, 'pg_sh_scrim')
    # a mark made under Unplayed leaves the row where it is; the next filter change makes the list again
    m = PSH.shown()
    to_filter(m, 1)
    PCP.dots(m, 0); PCP.click(m, 'pg_sh_mark')
    expect(m.state(h_of(0))[0] == 2 and ids(m) == [0, 2, 3, 4, 5, 6, 7] and PCP.all_cells(m)[0]['played'], 'Mark as Played under Unplayed: the row stays, now grey')
    to_filter(m, 2); to_filter(m, 1)
    expect(ids(m) == [2, 3, 4, 5, 6, 7], f'the next list made leaves it out ({ids(m)})')
    # Downloaded: a download that finishes is read in by the reload
    m = PSH.shown()
    to_filter(m, 2)
    m.put(f'{RP}/{DEEP}/e3.mp3', b'audio')
    bump(m)
    DL.tick(m)
    expect(ids(m) == [0, 1, 2, 3], f'a file that arrives joins the Downloaded rows at the next reload ({ids(m)})')


def state_tests(ctx):
    """Page state: kept over the episode page, reset by leaving the show and by another show; the See All row's place."""
    expect = ctx.expect
    m = PSH.shown()
    to_filter(m, 2)
    PCP.body(m, 1)
    expect(PCP.title_text(m) is not None and PCP.hdr is not None and PSH.texts_of(m, 'label_ps_head'), 'the episode page opens on the second Downloaded row')
    PCP.click(m, 'btn_return')
    expect(ids(m) == [0, 1, 2], f'back from the episode page the Filter is kept ({ids(m)})')
    PCP.click(m, 'btn_more')
    expect(PSH.text_of(m, 'pg_sh_filter_vl') == 'Downloaded', 'and the sheet says so')
    PCP.click(m, 'pg_sh_scrim')
    PCP.click(m, 'btn_return')
    PSH.open_show(m)
    expect(ids(m) == list(range(8)), f'leaving the show for Shows and opening it again: All ({ids(m)})')
    PCP.click(m, 'btn_more')
    expect(PSH.text_of(m, 'pg_sh_filter_vl') == 'All', 'the sheet says All')
    PCP.click(m, 'pg_sh_filter'); PCP.click(m, 'pg_sh_scrim')
    PCP.click(m, 'btn_return')
    PSH.open_show(m, 'bravo')
    PCP.click(m, 'btn_more')
    expect(PSH.text_of(m, 'pg_sh_filter_vl') == 'All', 'another show starts at All')
    # a reload (the worker moved) keeps the Filter
    m = PSH.shown()
    to_filter(m, 2)
    bump(m)
    DL.tick(m)
    expect(ids(m) == [0, 1, 2], f'a reload keeps the Filter ({ids(m)})')


def index_tests(ctx):
    """Hit testing and the actions on a filtered list reach the episode of the row, not the row's number."""
    expect = ctx.expect
    paths = lambda m: [m.read_cstr(m.word(r + O['REC_PATH'])).rsplit('/', 1)[1] for r in m.played[0]]
    m = PSH.shown()
    to_filter(m, 1)   # rows: e0 e2 e3 e4 e5 e6 e7
    m.calls = []; PCP.act(m, 1)   # e2, the second row
    expect(paths(m) == ['e0.mp3', 'e2.mp3'] and m.played[1] == 1, f'Unplayed: a tap on the pill of row 1 plays e2 with the visible local rows, e0 e2 (not e1: it is hidden) ({paths(m)}, {m.played[1]})')
    m = PSH.shown()
    to_filter(m, 1)
    PCP.body(m, 1)
    expect(any(t.startswith('Episode 2') for (s, t, x, y) in PCD.page_texts(m)), 'the body of row 1 opens the page of e2, the row\'s episode')
    PCP.click(m, 'btn_return')
    expect(ids(m) == [0, 2, 3, 4, 5, 6, 7], 'Back: the same rows')
    # the cell's sheet and its Mark as Played reach the row's episode
    PCP.dots(m, 1)
    expect(PSH.sheet_state(m)[0] == ['rm', 'save', 'mark'], 'the sheet of row 1: e2 is on the card, unplayed (a started one)')
    PCP.click(m, 'pg_sh_mark')
    expect(m.state(h_of(2))[0] == 2 and m.state(h_of(1))[0] == 2 and PCP.all_cells(m)[1]['played'] and ids(m) == [0, 2, 3, 4, 5, 6, 7],
           'Mark as Played marks e2; the row stays under the finger, grey')
    # Remove Download on row 0 removes e0's file
    PCP.dots(m, 0); PCP.click(m, 'pg_sh_rm')
    expect(f'{RP}/{DEEP}/e0.mp3' not in m.fs and f'{RP}/{DEEP}/e1.mp3' in m.fs and f'{RP}/{DEEP}/e2.mp3' in m.fs, 'Remove Download on row 0 removes e0.mp3 and nothing else')
    # Downloaded: row 2 is e2
    m = PSH.shown()
    to_filter(m, 2)
    m.calls = []; PCP.act(m, 1)
    expect(paths(m) == ['e0.mp3', 'e1.mp3', 'e2.mp3'] and m.played[1] == 1, f'Downloaded: the queue is the three files, from e1 ({paths(m)}, {m.played[1]})')
    # a download pill of a row under Unplayed queues that episode
    m = PSH.shown()
    to_filter(m, 1)
    m.thread = None
    PCP.act(m, 2)   # row 2 = e3
    expect(DL.state(m, 'e3.mp3', DEEP)[0] == 1 and DL.state(m, 'e2.mp3', DEEP)[0] == 0, 'the pill of row 2 downloads e3')
    # the Latest Episode pill is e0 whatever the Filter leaves
    m = PSH.shown(files=(1, 2))
    to_filter(m, 2)
    expect(ids(m) == [1, 2] and [t for t, _ in PSH.texts_of(m, 'label_ps_latestw')] == ['Latest Episode · 48 MB'], f'Downloaded with the newest not on the card: the pill is still that episode ({ids(m)})')
    m.thread = None
    PCP.latest(m)
    expect(DL.state(m, 'e0.mp3', DEEP)[0] == 1, 'and a tap downloads e0')
    m = PSH.shown()
    to_filter(m, 2)
    PCP.click(m, 'btn_more'); PCP.click(m, 'pg_sh_order'); PCP.click(m, 'pg_sh_scrim')
    expect(ids(m) == [2, 1, 0], 'Oldest First')
    m.calls = []; PCP.latest(m)
    expect(paths(m) == ['e2.mp3', 'e1.mp3', 'e0.mp3'] and m.played[1] == 2, f'Latest Episode plays e0 with the visible rows ({paths(m)}, {m.played[1]})')
    # the pill hides: Unplayed with e0 played, the pill (e0) is played text still; plays with the whole list
    m = PSH.shown()
    m.call(PSYMS['pc_mark'], a0=h_of(0), a1=1, count=2000000)
    to_filter(m, 1)
    expect(ids(m) == [2, 3, 4, 5, 6, 7], f'e0 played: not a row of Unplayed ({ids(m)})')
    m.calls = []; PCP.latest(m)
    expect(paths(m) == ['e0.mp3', 'e1.mp3', 'e2.mp3'] and m.played[1] == 0, f'the pill\'s episode is not a visible row: it plays with the whole list ({paths(m)}, {m.played[1]})')


def select_tests(ctx):
    """Select mode, Select All, Delete and Mark All as Played over the visible rows."""
    expect = ctx.expect
    m = PSH.shown()
    to_filter(m, 2)
    SEL.start_select(m)
    mk = SEL.all_marks(m)
    expect(sorted(mk) == [0, 1, 2], f'Downloaded: a mark on each of the three rows ({sorted(mk)})')
    PCP.click(m, 'btn_selall')
    expect(PCP.title_text(m) == '3 Selected', f'Select All marks the visible rows only ({PCP.title_text(m)})')
    PCP.click(m, 'btn_selall')
    # under Unplayed: rows e0 e2 e3 e4 e5 e6 e7; the ones that can be marked are e0, e2 and the paused .part e6
    m = PSH.shown()
    to_filter(m, 1)
    SEL.start_select(m)
    mk = SEL.all_marks(m)
    expect(sorted(mk) == [0, 1, 5], f'Unplayed: marks on e0, e2 and the paused e6 (rows 0, 1, 5) ({sorted(mk)})')
    PCP.click(m, 'btn_selall')
    expect(PCP.title_text(m) == '3 Selected', f'Select All: three ({PCP.title_text(m)})')
    PCP.click(m, 'btn_selall')
    PCP.body(m, 0)   # e0 (e2 is the playing one: it would be kept)
    expect(PCP.title_text(m) == '1 Selected', 'a tap on row 0 marks it')
    m.confirm_yes = True; m.calls = []
    PCP.click(m, 'pg_del')
    gone = SEL.unlinks(m)
    expect(sorted(gone) == [f'{DEEP}/e0.mp3', f'{DEEP}/e0.mp3.part'] and f'{RP}/{DEEP}/e1.mp3' in m.fs and f'{RP}/{DEEP}/e2.mp3' in m.fs, f'Delete removes the marked row\'s episode, e0 only ({gone})')
    expect(ids(m) == [0, 2, 3, 4, 5, 6, 7], f'the list is read again under the same Filter ({ids(m)})')
    # Mark All as Played: the visible rows only
    m = PSH.shown()
    to_filter(m, 2)
    PCP.click(m, 'btn_more'); PCP.click(m, 'pg_sh_markall')
    st = [m.state(h_of(i))[0] for i in range(8)]
    expect(st[0] == 2 and st[2] == 2 and st[3:] == [0] * 5, f'Downloaded: Mark All as Played marks e0 and e2 only, the other episodes stay as they were ({st})')
    m = PSH.shown()
    to_filter(m, 1)
    PCP.click(m, 'btn_more'); PCP.click(m, 'pg_sh_markall')
    st = [m.state(h_of(i))[0] for i in range(8)]
    expect(all(s == 2 for s in st), f'Unplayed: every visible row is marked ({st})')
    # the row is offered only while a visible row is unplayed: Downloaded with e0 and e2 played
    m = PSH.shown()
    m.call(PSYMS['pc_mark'], a0=h_of(0), a1=1, count=2000000); m.call(PSYMS['pc_mark'], a0=h_of(2), a1=1, count=2000000)
    to_filter(m, 2)
    rows, *_ = PSH.show_sheet(m)
    expect('markall' not in rows, f'Downloaded and every file played: no Mark All as Played row, though other episodes are not ({rows})')


def empty_tests(ctx):
    """A Filter that leaves nothing: the hint under the header, the header, the navbar and the sheet stay; See All stays."""
    expect = ctx.expect
    m = PSH.shown(files=())
    to_filter(m, 2)
    expect(hint(m) == 'No downloaded episodes' and ids(m) == [] and PSH.texts_of(m, 'label_ps_name'), f'Downloaded with no file: the hint under the header ({hint(m)!r})')
    expect(PSH.flags(m, 'btn_more') == (1, 1) and PSH.flags(m, 'btn_return') == (1, 1) and PCP.title_text(m) is not None, 'the navbar is as before, "..." included')
    PCP.click(m, 'btn_more')
    expect(PSH.text_of(m, 'pg_sh_filter_vl') == 'Downloaded', 'the sheet is there and says Downloaded')
    PCP.click(m, 'pg_sh_filter'); PCP.click(m, 'pg_sh_scrim')
    expect(ids(m) == list(range(8)) and 'No downloaded episodes' not in hint(m), 'back to All: the rows are back and the hint gone')
    # Unplayed with everything played
    m = PSH.machine(entries=[PSH.entry(i) for i in range(3)], files=(0, 1)); PSH.open_show(m)   # (no download running: the tap on See All starts its job)
    for i in range(3): m.call(PSYMS['pc_mark'], a0=h_of(i), a1=1, count=2000000)
    to_filter(m, 1)
    expect(hint(m) == 'No unplayed episodes' and ids(m) == [], f'Unplayed with every episode played: the hint ({hint(m)!r})')
    # the See All row stays (a feed show with no archive), under the hint
    h, bottom = PCP.hdr(m), max(0, m.props[(m.sv, 'virtual_h')] - 400)
    y = h + O['PG_HINT_H'] if 'PG_HINT_H' in O else h + 8 + 4 * O['PS_TITLE_PITCH']
    _, texts, styles, _ = PCP.paint(m, bottom)
    row = [(t, r) for (t, r), s in zip(texts, styles) if t == 'See All']
    expect(row and row[0][1][1] + bottom >= y and m.props[(m.sv, 'virtual_h')] == y + O['PS_MORE_H'], f'See All is still the last row, under the hint ({row}, content {m.props[(m.sv, "virtual_h")]}, row at {y})')
    PCP.tap(m, 150, y + O['PS_MORE_H'] // 2, off=bottom)
    expect(m.thread and m.thread[0] == PSYMS['pn_armain'], 'a tap on it starts the job')
    # reload while the list is empty keeps the hint
    bump(m)
    DL.tick(m)
    expect('No unplayed episodes' in hint(m), f'a reload keeps it ({hint(m)!r}, {ids(m)})')


def find_tests(ctx):
    """The search inside the show ignores the Filter: all the episodes, its queue the show's order."""
    expect = ctx.expect
    paths = lambda m: [m.read_cstr(m.word(r + O['REC_PATH'])).rsplit('/', 1)[1] for r in m.played[0]]
    m = PF.find_widgets(PSH.shown())
    to_filter(m, 2)   # Downloaded: e0 e1 e2
    expect(ids(m) == [0, 1, 2], 'the Show page is filtered')
    PF.click_find(m)
    expect(PF.found(m, 'episode') == [f'Episode {i}' for i in range(1, 8)], f'the search finds every episode with "episode", the ones the Filter hides included ({PF.found(m, "episode")})')
    m = PF.find_widgets(PSH.shown())
    to_filter(m, 1)   # Unplayed: e1 hidden
    PF.click_find(m)
    expect(PF.found(m, 'episode 1') == ['Episode 1'], 'a played episode the list hides is found')
    PF.tap_row(m, 0)
    m.call(PSYMS['pf_on_destroy'], count=2000000)
    m.sv, m.view = m.psv, m.pview
    m.calls = []
    PCP.tap(m, 30, sibling('pcdetail').page_y(m) + O['PS_PILL_H'] // 2)
    expect(paths(m) == ['e0.mp3', 'e1.mp3', 'e2.mp3'] and m.played[1] == 1, f'playing it queues the show\'s order, not the filtered rows ({paths(m)}, {m.played[1]})')
    PCP.click(m, 'btn_return')
    m.sv, m.view = m.psv, m.pview
    PCP.click(m, 'pf_close')
    expect(ids(m) == [0, 2, 3, 4, 5, 6, 7], f'back on the Show page the Filter is still on ({ids(m)})')
    # a result the Filter shows too (e2, unplayed): its queue is still the show's order, the played e1 in it
    m = PF.find_widgets(PSH.shown())
    to_filter(m, 1)
    PF.click_find(m)
    expect(PF.found(m, 'episode 2') == ['Episode 2'], 'an unplayed episode is found')
    PF.tap_row(m, 0)
    m.call(PSYMS['pf_on_destroy'], count=2000000)
    m.sv, m.view = m.psv, m.pview
    m.calls = []
    PCP.tap(m, 30, sibling('pcdetail').page_y(m) + O['PS_PILL_H'] // 2)
    expect(paths(m) == ['e0.mp3', 'e1.mp3', 'e2.mp3'] and m.played[1] == 2, f'a result that is one of the filtered rows queues the show\'s order too ({paths(m)}, {m.played[1]})')
    # the same episode opened from the Show page's own row under the Filter: the rows the Filter leaves
    m = PSH.shown()
    to_filter(m, 1)
    PCP.body(m, 1)   # row 1 is e2
    m.calls = []
    PCP.tap(m, 30, sibling('pcdetail').page_y(m) + O['PS_PILL_H'] // 2)
    expect(paths(m) == ['e0.mp3', 'e2.mp3'] and m.played[1] == 1, f'from the filtered list the queue is the visible rows ({paths(m)}, {m.played[1]})')


SECTIONS = [sheet_tests, rows_tests, state_tests, index_tests, select_tests, empty_tests, find_tests]
