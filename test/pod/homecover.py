"""Home cover build (patch/homecover.c, docs/modules/homecover.md): the progress line "Preparing covers n/m" above the Home list while the shared worker builds the
albums that have no cache file. Hidden when nothing is missing and after the build; the list moves down by HC_H while it shows; the worker stops in the background
and on destroy and is offered again at the next foreground; it never starts while another set (Cover Flow, Albums) holds the worker."""
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

import pod_recent
import pod_i18n

CFSORT_FILE = '/mnt/data/m1plus/album-order'
RECENT = '/mnt/mmc/.m1plus/recently-played'
HC_X, HC_Y, HC_W, HC_H, HOME_PAD, WIN_H = (O[k] for k in ('HC_X', 'HC_Y', 'HC_W', 'HC_H', 'HOME_PAD', 'WIN_H'))
START_MS, POLL_MS = O['RC_RESOLVE_MS'], 500


def key_of(i): return album_key(f'Artist {i}', f'Album {i}')


REQ = '/mnt/data/m1plus/covers-rebuild'


def home_machine(n=8, missing=(), empty=(), rebuild=False):
    """The Home instance's widgets (plain ones: the line, the list_view, the scroll view and its bar) and n albums in the stock list, each with a cache
    file unless it is in missing (no file) or empty (the zero-length 'no art' marker)."""
    m = Machine()
    m.fs[CFSORT_FILE] = b'0\n'
    if rebuild: m.fs[REQ] = b'1\n'   # Settings > Library > Rebuild Covers was confirmed
    m.window = m.widget('home_window')
    for w in ('pod_cover_prog', 'pod_listview', 'pod_scrollview', 'scroll_bar_m'): m.widget(w)
    m.props[(m.widgets['pod_scrollview'], 'w')] = 310
    m.props[(m.widgets['scroll_bar_m'], 'w')] = 10
    m.class_lists[O['CLASS_ALL_SONGS']] = []   # no songs: Home's song length pass (test/pod/durations.py) has nothing to read
    m.showlist = [m.record(album=f'Album {i}', artist=f'Artist {i}', path=f'/mnt/mmc/m/{i}/1.flac', rid=i + 1) for i in range(n)]
    m.present |= {f'/mnt/mmc/m/{i}/1.flac' for i in range(n)}
    for i in range(n):
        if i not in missing:
            p = art_file(key_of(i))
            m.present.add(p); m.files[p] = 0 if i in empty else 4096
    m.call(PSYMS['homecover_start'], a0=m.window, count=2000000)
    return m


def label(m): return m.widgets['pod_cover_prog']
def lv(m): return m.widgets['pod_listview']


def shown_calls(m, calls=None):
    """[(visible, sensitive)] changes of the line in the given calls."""
    calls = m.calls if calls is None else calls
    return [(c[0], c[2]) for c in calls if c[0] in ('widget_set_visible', 'widget_set_sensitive') and c[1] == label(m)]


def texts(m, calls=None):
    return [c[2] for c in (m.calls if calls is None else calls) if c[0] == 'widget_set_text_utf8' and c[1] == label(m)]


def scan(m, limit=100):
    """The start timer's callback until it stops re-arming itself (the scan steps, then the worker starts)."""
    for _ in range(limit):
        new = fired(m, 'hc_on_start', 400000000)
        if not [c for c in new if c[0] == 'timer_add' and c[1] == PSYMS['hc_on_start']]: return new
    raise AssertionError('the scan did not end')


def hook(m, fn, win=None, count=6000000):
    """A window handler (ctx = the window) runs: the calls it made."""
    m.call(PSYMS[fn], a0=m.window if win is None else win, a1=0, count=count)
    return list(m.calls)


def finish_worker(m, files):
    """The worker finishes the given album numbers: their cache files appear and the done counter moves."""
    for i in files:
        p = art_file(key_of(i)); m.present.add(p); m.files[p] = 4096
    m.call(PSYMS['cc_worker'], count=5000000)


def tests(ctx):
    expect = ctx.expect
    START, POLL = PSYMS['hc_on_start'], PSYMS['hc_on_poll']

    # 1. Start: the window's events are bound and one one-shot is armed HC_START_MS out; nothing is scanned, shown or moved yet.
    m = home_machine(6, missing={2, 4})
    binds = {c[2] for c in m.calls if c[0] == 'widget_on' and c[1] == m.window}
    expect({O['EVT_DESTROY'], O['EVT_WINDOW_TO_BG'], O['EVT_WINDOW_TO_FG']} <= binds, 'destroy, to-background and to-foreground are bound')
    expect([c for c in m.calls if c[0] == 'timer_add'] == [('timer_add', START, START_MS)], f'one start timer, {START_MS} ms out')
    expect(not shown_calls(m) and build_state(m)['jobs'] == 0 and 'pthread_create' not in m.names(), 'the line is hidden and nothing is scanned at start')
    expect(not [c for c in m.calls if c[0] == 'access' and '.m1plus' in str(c[1])], 'start stats no cache file')

    # 2. The scan queues the albums with neither a picture nor the marker, in the list's order; the worker starts after the last step; the line shows 0/2
    #    and the list makes room for it.
    new = scan(m)
    s = build_state(m)
    expect(s['running'] == 1 and s['mode'] == 0 and s['total'] == 2 and [t for t, _ in build_jobs(m)] == ['/mnt/mmc/m/2/1.flac', '/mnt/mmc/m/4/1.flac'],
           f'one CC_MISSING worker, the jobs are the missing albums in the list order ({s})')
    expect(shown_calls(m, new) == [('widget_set_visible', 1), ('widget_set_sensitive', 1)], 'the line is shown: visible and sensitive together')
    expect(texts(m, new) == ['Preparing covers 0/2'], f'the line reads "Preparing covers 0/2" ({texts(m, new)})')
    expect(('widget_move', lv(m), 0, HOME_PAD + HC_H) in new and ('widget_resize', lv(m), 320, WIN_H - 2 * HOME_PAD - HC_H) in new,
           'the list moves down by the line and shrinks by it')
    expect(('widget_resize', m.widgets['pod_scrollview'], 310, WIN_H - 2 * HOME_PAD - HC_H) in new and ('widget_resize', m.widgets['scroll_bar_m'], 10, WIN_H - 2 * HOME_PAD - HC_H) in new,
           'and so do its scroll view and bar')
    expect(HC_Y + HC_H <= HOME_PAD + HC_H and HC_Y >= 0, 'the line lies above the first row (it ends where the list starts)')
    expect([c for c in new if c[0] == 'timer_add' and c[1] == POLL] == [('timer_add', POLL, POLL_MS)], 'the poll runs every 500 ms')

    # 3. The poll shows n/m as the done counter advances and lets the Recently Played tiles retry; the end hides the line, restores the list and stops the worker.
    m.setword(PSYMS['cb'] + 4 * 5, 1)
    new = fired(m, 'hc_on_poll')
    expect(texts(m, new) == ['Preparing covers 1/2'] and not shown_calls(m, new) and [c for c in new if c[0] == 'timer_add' and c[1] == POLL], 'half done: "1/2", the line stays, the poll re-arms')
    new = fired(m, 'hc_on_poll')
    expect(not texts(m, new), 'a poll with no advance rewrites nothing')
    finish_worker(m, (2, 4))
    new = fired(m, 'hc_on_poll', 40000000)
    s = build_state(m)
    expect(shown_calls(m, new) == [('widget_set_visible', 0), ('widget_set_sensitive', 0)], 'done: the line is hidden and insensitive')
    expect(('widget_move', lv(m), 0, HOME_PAD) in new and ('widget_resize', lv(m), 320, WIN_H - 2 * HOME_PAD) in new, 'the list is back where it was')
    expect(s['jobs'] == 0 and [c for c in new if c[0] == 'pthread_join'] and not [c for c in new if c[0] == 'timer_add'], f'the worker is joined, the set freed, the poll ends ({s})')
    expect(not [c for c in fired(m, 'hc_on_poll', 1000000) if c[0] in ('timer_add', 'widget_set_text_utf8')], 'a late poll does nothing')

    # 3b. Recently Played's albums are queued first, most recent first (the shelf's placeholders go first); a stale shelf key is corrected from the list.
    m = home_machine(6, missing={1, 3, 5})
    m.fs[RECENT] = pod_recent.dump([(pod_recent.identity(f'Album {i}'), album_key('Old Row', f'Album {i}'), 1, f'Album {i}', 'Old Row', f'/x/{i}.flac') for i in (5, 3, 0)])
    scan(m)
    expect([t for t, _ in build_jobs(m)] == ['/mnt/mmc/m/5/1.flac', '/mnt/mmc/m/3/1.flac', '/mnt/mmc/m/1/1.flac'] and build_state(m)['total'] == 3,
           f'the shelf\'s missing albums first, in its order, then the rest, each once ({build_jobs(m)})')
    expect([e[1] for e in pod_recent.parse(m.fs[RECENT])] == [key_of(5), key_of(3), key_of(0)], 'the shelf\'s stale keys are the rows\' now')
    m = home_machine(6, missing={1, 3, 5}); m.fs[CFSORT_FILE] = b'1\n'
    m.fs[RECENT] = pod_recent.dump([(pod_recent.identity('Album 3'), key_of(3), 1, 'Album 3', 'Artist 3', '/x/3.flac')])
    scan(m)
    expect([t for t, _ in build_jobs(m)][0] == '/mnt/mmc/m/3/1.flac' and build_state(m)['total'] == 3, f'with the artist order too ({build_jobs(m)})')

    # 4. Nothing missing (a picture or the marker for every album): never shown, no worker, no list move; the next foreground scans again.
    m = home_machine(8, empty={3})
    new = scan(m)
    expect(not shown_calls(m, new) and not texts(m, new) and 'pthread_create' not in [c[0] for c in new] and build_state(m)['jobs'] == 0
           and not [c for c in new if c[0] in ('widget_move', 'widget_resize')], 'a complete cache: no line, no worker, the list untouched')
    expect([c for c in hook(m, 'hc_on_foreground') if c[0] == 'timer_add' and c[1] == START], 'the next foreground offers the scan again (the library may have changed)')
    # an empty library
    m = home_machine(0); new = scan(m)
    expect(not shown_calls(m, new) and 'pthread_create' not in [c[0] for c in new], 'no albums: nothing')

    # 5. The scan is bounded per step (64 albums a tick) and the line appears only after the last one.
    m = home_machine(300, missing={250})
    steps = 0
    for _ in range(20):
        new = fired(m, 'hc_on_start', 400000000)
        steps += 1
        expect(len([c for c in new if c[0] == 'access' and '.m1plus/covers' in str(c[1])]) <= 64, 'at most 64 cache files checked a step')
        if not [c for c in new if c[0] == 'timer_add' and c[1] == START]: break
        expect(not shown_calls(m, new), 'no line while the scan runs')
    expect(steps == 5 and shown_calls(m, new) and build_state(m)['total'] == 1, f'300 albums: five steps, then the line ({steps})')
    # a destroy in the middle of a scan drops the set
    m = home_machine(300, missing={250}); fired(m, 'hc_on_start', 400000000)
    hook(m, 'hc_on_destroy')
    expect(build_state(m)['jobs'] == 0 and ('timer_remove', 0x777) in m.calls and 'pthread_create' not in m.names(), 'destroy mid-scan: the timer is removed, the set freed')

    # 6. Background: the worker is cancelled and joined, the line hidden, the list restored, the timer gone; the foreground offers the build again.
    m = home_machine(6, missing={2, 4}); scan(m)
    hook(m, 'hc_on_background')
    s = build_state(m)
    expect(count_of(m, 'pthread_join') == 1 and s['jobs'] == 0 and ('timer_remove', 0x777) in m.calls, f'background stops the worker and removes the poll ({s})')
    expect(shown_calls(m)[-2:] == [('widget_set_visible', 0), ('widget_set_sensitive', 0)] and ('widget_move', lv(m), 0, HOME_PAD) in m.calls, 'and hides the line and restores the list')
    expect(not [c for c in fired(m, 'hc_on_poll', 1000000) + fired(m, 'hc_on_start', 1000000) if c[0] in ('timer_add', 'pthread_create', 'access')], 'late timers in the background do nothing')
    new = hook(m, 'hc_on_foreground')
    expect([c for c in new if c[0] == 'timer_add'] == [('timer_add', START, START_MS)], 'the foreground arms the start again')
    expect(not [c for c in hook(m, 'hc_on_foreground') if c[0] == 'timer_add'], 'and only once while it is pending')
    scan(m)
    expect(build_state(m)['running'] == 1 and shown_calls(m)[-2:] == [('widget_set_visible', 1), ('widget_set_sensitive', 1)], 'the build resumes and shows the line again')
    expect(not [c for c in hook(m, 'hc_on_foreground') if c[0] == 'timer_add'], 'foreground while the worker runs arms nothing')

    # 7. Destroy: cancelled and joined, line hidden; a late callback does nothing.
    m = home_machine(6, missing={2, 4}); scan(m)
    hook(m, 'hc_on_destroy')
    expect(count_of(m, 'pthread_join') == 1 and build_state(m)['jobs'] == 0 and ('timer_remove', 0x777) in m.calls, 'destroy cancels and joins the worker and removes the poll')
    expect(not [c for c in fired(m, 'hc_on_poll', 1000000) + fired(m, 'hc_on_start', 1000000) if c[0] in ('timer_add', 'pthread_create', 'access')], 'late callbacks after destroy do nothing')
    m = home_machine(6, missing={2}); hook(m, 'hc_on_destroy')
    expect(('timer_remove', 0x777) in m.calls and not shown_calls(m), 'destroy before the start fired removes the one-shot')
    m = home_machine(6, missing={2}); hook(m, 'hc_on_destroy', win=0x1234)
    expect(('timer_remove', 0x777) not in m.calls, 'another window\'s destroy is ignored')

    # 8. The worker belongs to one owner at a time: held by Cover Flow / Albums (any set), Home starts nothing and shows nothing; its set is left alone.
    m = home_machine(6, missing={2, 4})
    m.call(PSYMS['cc_build_open'], a0=6, a1=0, count=2000000)
    new = fired(m, 'hc_on_start', 4000000)
    expect(not shown_calls(m, new) and not [c for c in new if c[0] in ('pthread_create', 'timer_add', 'widget_move')] and build_state(m)['jobs'] != 0, 'a held worker: nothing starts')
    hook(m, 'hc_on_background')
    expect(build_state(m)['jobs'] != 0 and not [c for c in m.calls if c[0] == 'pthread_join'], 'background does not stop a set Home does not own')
    expect([c for c in hook(m, 'hc_on_foreground') if c[0] == 'timer_add'], 'and the foreground offers again')

    # 9. No space, no thread, no timer: Home unchanged, nothing held.
    m = home_machine(6, missing={2}); m.free_mb = 2; new = scan(m)
    expect(not shown_calls(m, new) and 'pthread_create' not in [c[0] for c in new] and build_state(m)['jobs'] == 0 and not [c for c in new if c[0] in ('widget_move', 'widget_resize')], 'a full card: no line, no worker')
    m = home_machine(6, missing={2}); m.thread_ok = False; new = scan(m)
    expect(not shown_calls(m, new) and build_state(m)['jobs'] == 0 and not [c for c in new if c[0] in ('widget_move', 'widget_resize')], 'a refused thread: no line, the set freed')
    m = home_machine(6, missing={2}); m.timer_fail = True; fired(m, 'hc_on_start', 400000000)
    expect(build_state(m)['jobs'] == 0 and count_of(m, 'pthread_join') == 1 and shown_calls(m)[-2:] == [('widget_set_visible', 0), ('widget_set_sensitive', 0)], 'a poll timer that cannot be made: stopped, hidden')
    m = Machine(); m.widget('home_window'); m.window = m.widgets['home_window']
    m.call(PSYMS['homecover_start'], a0=m.window, count=2000000)
    expect('timer_add' not in m.names(), 'an asset without the line (not ours): nothing is armed')
    m = Machine(); m.timer_fail = True
    for w in ('home_window', 'pod_cover_prog', 'pod_listview'): m.widget(w)
    m.call(PSYMS['homecover_start'], a0=m.widgets['home_window'], count=2000000)
    new = fired(m, 'hc_on_start', 4000000)
    expect(not [c for c in new if c[0] in ('pthread_create', 'access')], 'a start timer that cannot be made: Home never builds')


def rebuild_tests(ctx):
    """A requested Rebuild Covers (REBUILD_FILE): the scan opens a CC_REBUILD set with every album, the line reads Rebuilding covers, the request ends with the set."""
    expect = ctx.expect
    OLD = 111
    START = PSYMS['hc_on_start']

    def machine(n=3, **kw):
        m = home_machine(n, rebuild=True, **kw)
        for i in range(n):
            p = art_file(key_of(i)); m.files[p] = OLD
        return m

    # 1. A complete cache is queued whole, in CC_REBUILD mode; the line says Rebuilding covers 0/3.
    m = machine(); new = scan(m); s = build_state(m)
    expect(s['running'] == 1 and s['mode'] == 1 and s['total'] == 3 and [k for _, k in build_jobs(m)] == [key_of(i) for i in range(3)], f'every album is a job, CC_REBUILD ({s})')
    expect(texts(m, new) == ['Rebuilding covers 0/3'] and shown_calls(m, new) == [('widget_set_visible', 1), ('widget_set_sensitive', 1)], f'the line reads Rebuilding covers 0/3 ({texts(m, new)})')
    expect(REQ in m.fs, 'the request stays while the rebuild runs')

    # 2. The worker replaces each file (temp, rename), a marker too; the request ends only when the set is done.
    dst = [art_file(key_of(i)) for i in range(3)]
    m.files[dst[1]] = 0
    m.album_cover = 1
    m.setword(PSYMS['cb'] + 4 * 5, 1)   # album 0 is done (the mock worker takes up at job 1)
    new = fired(m, 'hc_on_poll')
    expect(texts(m, new) == ['Rebuilding covers 1/3'] and REQ in m.fs, 'part way: 1/3, the request stays')
    m.call(PSYMS['cc_worker'], count=5000000)
    renames = [c for c in m.calls if c[0] == 'rename']
    expect([c[2] for c in renames] == dst[1:] and all(c[1] == c[2] + '.tmp' for c in renames) and m.files[dst[0]] == OLD and all(m.files[p] == 4096 for p in dst[1:]),
           'each cover is extracted to a temp file and renamed over the old one, the marker replaced by the new picture')
    new = fired(m, 'hc_on_poll', 40000000)
    expect(REQ not in m.fs and ('unlink', REQ) in new and [c for c in new if c[0] == 'pthread_join'] and shown_calls(m, new)[-2:] == [('widget_set_visible', 0), ('widget_set_sensitive', 0)],
           'done: the request file is removed, the worker joined, the line hidden')
    m2 = home_machine(3)
    scan(m2)
    expect(build_state(m2)['total'] == 0 and 'pthread_create' not in m2.names(), 'without a request the complete cache is not touched again')

    # 3. Interrupted (background, destroy): the request stays, the worker is stopped; the next foreground starts the rebuild again from the first album.
    m = machine(); scan(m)
    m.setword(PSYMS['cb'] + 4 * 5, 1)
    fired(m, 'hc_on_poll')
    hook(m, 'hc_on_background')
    expect(REQ in m.fs and build_state(m)['jobs'] == 0 and count_of(m, 'pthread_join') == 1, 'background mid-way: stopped, the request stays')
    new = hook(m, 'hc_on_foreground')
    expect([c for c in new if c[0] == 'timer_add'] == [('timer_add', START, START_MS)], 'the foreground arms the scan again')
    new = scan(m)
    expect(build_state(m)['mode'] == 1 and build_state(m)['total'] == 3 and texts(m, new) == ['Rebuilding covers 0/3'], 'and the rebuild starts again from the beginning')
    hook(m, 'hc_on_destroy')
    expect(REQ in m.fs and build_state(m)['jobs'] == 0, 'destroy mid-way: the request stays')

    # 4. A held worker: nothing starts, the request stays; no space or no thread likewise.
    m = machine(); m.call(PSYMS['cc_build_open'], a0=3, a1=0, count=2000000)
    new = fired(m, 'hc_on_start', 4000000)
    expect(not shown_calls(m, new) and REQ in m.fs and not [c for c in new if c[0] == 'pthread_create'], 'a held worker: nothing, the request stays')
    m = machine(); m.free_mb = 2; scan(m)
    expect(REQ in m.fs and build_state(m)['jobs'] == 0 and 'pthread_create' not in m.names(), 'a full card: the request stays')

    # 5. No album has a track path: nothing to extract, nothing to wait for.
    m = home_machine(2, rebuild=True)
    for r in m.showlist: m.setword(r + O['REC_PATH'], 0)
    scan(m)
    expect(REQ not in m.fs and 'pthread_create' not in m.names(), 'nothing to extract: the request is dropped')


def clear_tests(ctx):
    """Settings > Developer > Clear Cover Cache (clear_ask / homecover_clear): the confirm, then every file in the cache folder is removed in bounded steps."""
    expect = ctx.expect
    ART = '/mnt/mmc/.m1plus/covers'
    CONFIRM = 'Delete all cached covers? They will be made again on Home.'
    BUSY, DONE = 'Covers are being made, try later', 'Cover cache cleared'

    def machine(n=100, yes=True, loc=None):
        m = Machine()
        m.confirm_yes = yes
        if loc: m.set_language(loc)
        names = ['album'] + [f'r{i:08x}-168.jpg' for i in range(n)] + ['r000000aa-168.jpg.tmp', f'{0x1234:08x}-168.jpg', f'f{0x1234:08x}-168.jpg', 'r000000bb-168.jpg']
        m.listing[ART] = [('.', 4), ('..', 4)] + [(nm, 8) for nm in names]
        for nm in names:
            m.present.add(ART + '/' + nm); m.files[ART + '/' + nm] = 0 if nm == 'r000000bb-168.jpg' else 4096   # (the last is a no-art marker)
        m.fs[REQ] = b'1\n'
        return m, [ART + '/' + nm for nm in names]

    def unlinks(m): return [c[1] for c in m.calls if c[0] == 'unlink' and c[1] != REQ]
    def toasts(m): return [c[1] for c in m.calls if c[0] == 'toast']

    # Yes: the confirm, the request dropped at once, then ticks of at most 32 unlinks; the toast at the end.
    m, paths = machine()
    m.call(PSYMS['clear_ask'], count=3000000)
    expect([c[1] for c in m.calls if c[0] == 'confirm'] == [CONFIRM] and REQ not in m.fs and not toasts(m), 'the confirm is asked, the pending rebuild request is dropped, no toast yet')
    seen, ticks = [], 0
    while [c for c in m.calls if c[0] == 'timer_add' and c[1] == PSYMS['cl_tick']] and ticks < 20:
        m.call(PSYMS['cl_tick'], count=4000000); ticks += 1
        seen.append(len(unlinks(m)))
        if not [c for c in m.calls if c[0] == 'timer_add' and c[1] == PSYMS['cl_tick']]: break
    gone = [p for p in paths if p not in m.present]
    expect(set(gone) == set(paths), 'every file is deleted (pictures, markers, .tmp, unprefixed and f files, the old Cover Flow position file album)')
    expect(ticks >= 4 and all(n <= 32 for n in seen), f'bounded: {ticks} ticks of at most 32 unlinks ({seen})')
    expect(toasts(m) == [DONE] and not [c for c in m.calls if c[0] == 'unlink' and c[1] in ('.', '..')], 'the toast reads Cover cache cleared at the end')
    expect(m.open_dirs == {} , 'the directory handle is closed')

    # No (or a failed dialog): nothing at all.
    m, paths = machine(yes=False)
    m.call(PSYMS['clear_ask'], count=3000000)
    expect(not unlinks(m) and not toasts(m) and REQ in m.fs and 'timer_add' not in m.names() and 'opendir' not in m.names(), 'No: nothing is touched, the request stays')

    # The cover worker busy: refused with a toast before the dialog; nothing is deleted.
    m, paths = machine(); m.call(PSYMS['cc_build_open'], a0=3, a1=0, count=2000000)
    m.call(PSYMS['clear_ask'], count=3000000)
    expect(toasts(m) == [BUSY] and 'confirm' not in m.names() and not unlinks(m) and REQ in m.fs and build_state(m)['jobs'] != 0, 'a busy worker: the toast, no dialog, nothing deleted, the set untouched')
    # a build that starts between the ticks stops the clearing (no toast)
    m, paths = machine(); m.call(PSYMS['clear_ask'], count=3000000)
    m.call(PSYMS['cc_build_open'], a0=3, a1=0, count=2000000)
    m.call(PSYMS['cl_tick'], count=4000000)
    expect(not unlinks(m) and not toasts(m) and not [c for c in m.calls if c[0] == 'timer_add'], 'a build started meanwhile: the clearing stops quietly')

    # No cache folder: nothing to delete, still the toast. A second ask while one runs starts no second timer.
    m = Machine(); m.confirm_yes = True; m.call(PSYMS['clear_ask'], count=3000000)
    expect(toasts(m) == [DONE] and not unlinks(m), 'no cache folder: nothing to delete, the toast')
    m, paths = machine(); m.call(PSYMS['clear_ask'], count=3000000); m.call(PSYMS['clear_ask'], count=3000000)
    expect(count_of(m, 'opendir') == 0 and not unlinks(m), 'a second ask while the clearing runs opens nothing')

    # All 13 languages: the confirm and the toasts.
    for loc in pod_i18n.ALL_TABLES:
        T = tr_of(loc)
        m, _ = machine(n=3, loc=loc); m.call(PSYMS['clear_ask'], count=3000000)
        asked = [c[1] for c in m.calls if c[0] == 'confirm']
        m.call(PSYMS['cl_tick'], count=4000000)   # (a short listing ends in the first tick)
        expect(asked == [T(CONFIRM)] and toasts(m) == [T(DONE)], f'{loc}: confirm and done toast translated')
        m, _ = machine(n=3, loc=loc); m.call(PSYMS['cc_build_open'], a0=3, a1=0, count=2000000); m.call(PSYMS['clear_ask'], count=3000000)
        expect(toasts(m) == [T(BUSY)], f'{loc}: busy toast translated')


def cache_tests(ctx):
    """Settings > Developer > Cover Cache (homecover_cache_open / homecover_stat): the counts in bounded steps, the Status line, the timers, the refresh after a clear."""
    expect = ctx.expect
    ART = '/mnt/mmc/.m1plus/covers'
    PAGE = 29
    ELL = '\xe2\x80\xa6'
    TICK, POLL = PSYMS['cp_tick'], PSYMS['cp_poll']

    def stat(m, idx):
        buf = m.alloc(64)
        m.call(PSYMS['homecover_stat'], a0=idx, a1=buf, a2=64)
        return m.read_cstr(buf)

    def values(m): return [stat(m, i) for i in range(7)]

    def machine(pictures=3, markers=2, old=3, albums=8, folder=True, big=0):
        """A Home machine (n albums, none with a cache file of the album's own name) plus a mixed cache folder: `pictures` r<key> files (400000 bytes; the keys of albums 0..),
        `markers` empty r files (the last is no album's), `old` stale files (unprefixed, f-prefixed, .tmp: 100000 bytes), `big` tiny pictures."""
        m = home_machine(albums, missing=set(range(albums)))
        names = [(f'r{key_of(i):08x}-168.jpg', 400000) for i in range(pictures)]
        names += [(f'r{key_of(pictures + i):08x}-168.jpg', 0) for i in range(markers - 1)] + [('r000000aa-168.jpg', 0)]
        names += [(f'{0x1234:08x}-168.jpg', 100000), (f'f{0x1234:08x}-168.jpg', 100000), (f'r{key_of(0):08x}-168.jpg.tmp', 100000)][:old]
        names += [(f'r{0x7000 + i:08x}-168.jpg', 10) for i in range(big)]
        for nm, size in names if folder else ():
            m.present.add(f'{ART}/{nm}'); m.files[f'{ART}/{nm}'] = size
        if folder: m.listing[ART] = [('.', 4), ('..', 4)] + [(nm, 8) for nm, _ in names]
        m.watch[PSYMS['pod_page_refresh']] = 'pod_page_refresh'
        return m, names

    def open_page(m):
        m.call(PSYMS['homecover_cache_open'], a0=m.window, a1=PAGE, count=3000000)
        return list(m.calls)

    def count_all(m, limit=60):
        """cp_tick until it stops re-arming: the files and albums looked at in each tick."""
        per = []
        for _ in range(limit):
            new = fired(m, 'cp_tick', 40000000)
            per.append(max(len([c for c in new if c[0] == 'fopen']), len([c for c in new if c[0] == 'access' and '/r' in str(c[1])])))
            if not [c for c in new if c[0] == 'timer_add' and c[1] == TICK]: return per
        raise AssertionError('the count did not end')

    # 1. Opening: events bound, the two timers armed, every count an ellipsis (Status is read at once); the open itself reads no file.
    m, names = machine()
    new = open_page(m)
    binds = {c[2] for c in new if c[0] == 'widget_on' and c[1] == m.window}
    expect({O['EVT_DESTROY'], O['EVT_WINDOW_TO_BG'], O['EVT_WINDOW_TO_FG']} <= binds, 'destroy, background and foreground are bound')
    expect([c for c in new if c[0] == 'timer_add' and c[1] in (TICK, POLL)] == [('timer_add', TICK, 20), ('timer_add', POLL, 500)], 'the count tick and the 500 ms poll are armed')
    expect(values(m)[:6] == [ELL] * 6 and values(m)[6] == 'Idle' and not [c for c in new if c[0] == 'fopen'], 'before counting every count is an ellipsis and Status is Idle')

    # 2. Counted: pictures, markers (the dot entries excluded), old files, albums, missing albums, size.
    count_all(m)
    tenths = ((3 * 400000 + 3 * 100000) // 1024 * 10 + 512) // 1024
    expect(values(m) == ['8', '3', '2', '4', '3', f'{tenths // 10}.{tenths % 10} MB', 'Idle'],
           f'Albums 8, Covers 3, No art 2, Missing 4 (albums 0..3 have their files in the folder), Old files 3, Size {tenths / 10} MB ({values(m)})')
    m, names = machine(old=0)
    for i in range(4):   # albums 0..2 have their pictures and 3 a marker (the cache files of their own keys)
        p = art_file(key_of(i)); m.present.add(p); m.files[p] = 400000 if i < 3 else 0
    open_page(m); count_all(m)
    expect(stat(m, 3) == '4' and stat(m, 4) == '0' and stat(m, 0) == '8', 'Missing = albums with neither a picture nor a marker by the CC_MISSING rule (albums 4..7)')

    # 3. Bounded: 143 pictures and 130 albums in steps of at most 64; the size has a decimal under 10 MB and none above.
    m, names = machine(albums=130, big=140)
    open_page(m); per = count_all(m)
    expect(len(per) >= 4 and max(per) <= 64, f'bounded steps: {len(per)} ticks of at most 64 files or albums ({per})')
    expect(stat(m, 1) == '143' and stat(m, 0) == '130' and stat(m, 5) == '1.4 MB' and m.open_dirs == {}, f'the counts after many ticks ({values(m)}), the directory is closed')
    m, _ = machine(pictures=0, markers=1, old=1); m.files[f'{ART}/{0x1234:08x}-168.jpg'] = 12 * 1024 * 1024
    open_page(m); count_all(m)
    expect(stat(m, 5) == '12 MB', f'from 10 MB up the size has no decimal ({stat(m, 5)})')

    # 4. No folder: zeros, Status Idle, every album missing; an empty library too.
    m, _ = machine(folder=False)
    open_page(m); count_all(m)
    expect(values(m) == ['8', '0', '0', '8', '0', '0.0 MB', 'Idle'], f'no cache folder: zeros and every album missing ({values(m)})')
    m = home_machine(0); open_page(m); count_all(m)
    expect(values(m)[:5] == ['0'] * 5, 'an empty library and no folder: all zeros')

    # 5. Status: Idle, Rebuild requested, Building (another page's set, n/m with jobs), Clearing, Preparing n/m and Rebuilding n/m (Home's own set).
    m, _ = machine(); open_page(m)
    expect(stat(m, 6) == 'Idle', 'Idle')
    m.fs[REQ] = b'1\n'
    expect(stat(m, 6) == 'Rebuild requested', 'Rebuild requested: the request file exists and nothing builds')
    del m.fs[REQ]
    m.call(PSYMS['cc_build_open'], a0=4, a1=0, count=2000000)
    expect(stat(m, 6) == 'Building', 'Building (another page holds the worker, no jobs yet)')
    trk = m.alloc(32); m.u.mem_write(trk, b'/mnt/mmc/m/1/1.flac\0')
    m.call(PSYMS['cc_build_add'], a0=trk, a1=0x4321, count=2000000)
    expect(stat(m, 6) == 'Building 0/1', f'Building n/m ({stat(m, 6)})')
    m.call(PSYMS['cc_build_stop'], count=2000000)
    m, _ = machine(); m.confirm_yes = True; open_page(m)
    m.call(PSYMS['clear_ask'], count=3000000)
    expect(stat(m, 6) == 'Clearing', 'Clearing while the files are being deleted')
    m, _ = machine(); open_page(m); scan(m)
    expect(stat(m, 6) == 'Preparing 0/4', f'Preparing n/m while Home builds the missing covers ({stat(m, 6)})')
    m, _ = machine(); m.fs[REQ] = b'1\n'; open_page(m); scan(m)
    expect(stat(m, 6) == 'Rebuilding 0/8', f'Rebuilding n/m while Home rebuilds ({stat(m, 6)})')

    # 6. The poll refreshes the page when the Status changed, not otherwise, and re-arms itself.
    m, _ = machine(); open_page(m)
    new = fired(m, 'cp_poll', 2000000)
    expect(('pod_page_refresh', PAGE) not in new and [c for c in new if c[0] == 'timer_add' and c[1] == POLL], 'an unchanged Status: no refresh, the poll re-arms')
    m.fs[REQ] = b'1\n'
    new = fired(m, 'cp_poll', 2000000)
    expect(('pod_page_refresh', PAGE) in new and [c for c in new if c[0] == 'timer_add' and c[1] == POLL], 'a changed Status: the page is refreshed')
    expect(('pod_page_refresh', PAGE) not in fired(m, 'cp_poll', 2000000), 'and only once')

    # 7. Background and destroy: both timers removed, the directory closed, the album copy freed, late callbacks do nothing; the foreground counts again from nothing.
    m, _ = machine(albums=130, big=140); open_page(m); fired(m, 'cp_tick', 40000000)
    hook(m, 'cp_on_background')
    expect(len([c for c in m.calls if c[0] == 'timer_remove']) == 2 and m.open_dirs == {}, 'background removes the tick and the poll and closes the directory')
    late = fired(m, 'cp_tick', 4000000) + fired(m, 'cp_poll', 4000000)
    expect(not [c for c in late if c[0] in ('timer_add', 'readdir', 'fopen')], 'late callbacks in the background do nothing')
    new = hook(m, 'cp_on_foreground')
    expect([c for c in new if c[0] == 'timer_add' and c[1] in (TICK, POLL)] == [('timer_add', TICK, 20), ('timer_add', POLL, 500)] and stat(m, 1) == ELL, 'the foreground counts again from nothing')
    count_all(m)
    expect(stat(m, 1) == '143' and stat(m, 0) == '130', 'and gets the same counts')
    new = hook(m, 'cp_on_destroy')
    expect(len([c for c in new if c[0] == 'timer_remove']) == 1 and stat(m, 0) == ELL, 'destroy removes the poll (the count had ended) and forgets the counts')
    expect(not [c for c in fired(m, 'cp_tick', 4000000) + fired(m, 'cp_poll', 4000000) if c[0] in ('timer_add', 'readdir', 'fopen')], 'nothing runs after destroy')
    m, _ = machine(albums=130, big=140); open_page(m)
    for _ in range(5): fired(m, 'cp_tick', 40000000)      # the directory is done, the albums are under way
    hook(m, 'cp_on_destroy')
    expect(m.open_dirs == {} and [c for c in m.calls if c[0] == 'timer_remove'], 'destroy mid-count: the timers go')
    expect(not [c for c in hook(m, 'cp_on_foreground') if c[0] == 'timer_add'], 'a foreground for a window already gone does nothing')
    m, _ = machine(); m.widget_on_fail = frozenset({O['EVT_WINDOW_TO_BG']}); open_page(m)
    expect(not [c for c in m.calls if c[0] == 'timer_add' and c[1] == TICK], 'a refused event registration: nothing is counted')

    # 8. A clear finishing refreshes the counts (page in front); with no page open nothing of the page is armed.
    m, _ = machine(); m.confirm_yes = True; open_page(m); count_all(m)
    expect(stat(m, 1) == '3', 'counted before the clear')
    m.call(PSYMS['clear_ask'], count=3000000)
    new = fired(m, 'cl_tick', 4000000)
    expect([c for c in new if c[0] == 'timer_add' and c[1] == TICK] and ('pod_page_refresh', PAGE) in new, 'the clear ends: the page counts again')
    m.listing[ART] = [e for e in m.listing[ART] if e[1] == 4 or f'{ART}/{e[0]}' in m.present]   # (the mock directory forgets what was unlinked; the count that began inside the tick listed the old one: count again)
    hook(m, 'cp_on_foreground')
    count_all(m)
    expect(values(m) == ['8', '0', '0', '8', '0', '0.0 MB', 'Idle'], f'and finds an empty folder ({values(m)})')
    m, _ = machine(); m.confirm_yes = True
    m.call(PSYMS['clear_ask'], count=3000000)
    fired(m, 'cl_tick', 4000000)
    expect(not [c for c in m.calls if c[0] == 'timer_add' and c[1] in (TICK, POLL)], 'no Cover Cache page open: a clear arms no count')


def covlist_tests(ctx):
    """The No art / Missing rows of the Cover Cache page open a plain list (patch/covlist.c): tappable only when counted and not zero, the rows are the albums with an empty marker /
    with no file in the album list's order, a tap opens that album, the empty state, everything freed with the window."""
    expect = ctx.expect
    ART = '/mnt/mmc/.m1plus/covers'
    PAGE = 29

    def world(albums=8, marker=(3, 5), have=(0, 1), folder=True, sort=None):
        """A Home machine with `albums` albums; albums in `have` have a picture, those in `marker` an empty marker; the rest are missing. The cache folder lists exactly those files."""
        m = home_machine(albums, missing=set(range(albums)))
        if sort: m.fs[CFSORT_FILE] = sort
        files = [(f'r{key_of(i):08x}-168.jpg', 4096) for i in have] + [(f'r{key_of(i):08x}-168.jpg', 0) for i in marker]
        for nm, size in files:
            m.present.add(f'{ART}/{nm}'); m.files[f'{ART}/{nm}'] = size
        if folder: m.listing[ART] = [('.', 4), ('..', 4)] + [(nm, 8) for nm, _ in files]
        m.watch[PSYMS['pod_page_refresh']] = 'pod_page_refresh'
        # the list page's widgets as the Albums page's are: real widget structs for widget_to_local (window > list_view > scroll_view > view_grid)
        win, lv, sv = m.alloc(0x80), m.alloc(0x80), m.alloc(0x180)
        m.u.mem_write(sv, bytes(0x180))
        for w, y, h, parent in ((win, 30, 450, 0), (lv, 50, 400, win), (sv, 0, 400, lv)):
            for off, v in ((4, y), (8, 320), (0xc, h), (0x44, parent)): m.setword(w + off, v)
        m.setword(sv + 0x70, SV_VT); m.setword(sv + 8, 310)
        m.windows = {'m1plus_covlist': win}
        for w in ('btn_return', 'btn_backtoplayer', 'label_title', 'label_status', 'label_row_title', 'label_row_sub', 'view_grid'): m.widget(w)
        m.widgets['covlist_scrollview'] = sv
        view = m.widgets['view_grid']
        for off, v in ((4, 0), (8, 320), (0xc, 400), (0x44, sv)): m.setword(view + off, v)
        m.mem_geometry, m.live_scroll = True, frozenset({sv})
        m.cl_win = win
        return m

    def count(m):
        m.call(PSYMS['homecover_cache_open'], a0=m.window, a1=PAGE, count=3000000)
        for _ in range(30):
            new = fired(m, 'cp_tick', 40000000)
            if not [c for c in new if c[0] == 'timer_add' and c[1] == PSYMS['cp_tick']]: return

    def tappable(m, idx):
        return bool(m.call(PSYMS['homecover_tappable'], a0=idx, count=100000))

    def paint(m):
        e = m.alloc(0x40); m.u.mem_write(e, bytes(0x40)); m.setword(e + O['EVENT_PAINT_CANVAS'], m.alloc(0x80))
        m.texts.clear()
        m.call(PSYMS['cv_on_paint'], a0=0, a1=e, count=40000000)
        return [t for t, _ in m.texts]

    def open_list(m, idx):
        m.call(PSYMS['homecover_list_open'], a0=idx, count=6000000)
        return list(m.calls)

    # 1. Tappable only once counted and not zero: not while the page shows an ellipsis; the zero rows do nothing.
    m = world()
    m.call(PSYMS['homecover_cache_open'], a0=m.window, a1=PAGE, count=3000000)
    expect(not tappable(m, 2) and not tappable(m, 3), 'while counting neither row is tappable')
    open_list(m, 3)
    expect('window_open' not in m.names(), 'a tap while counting opens nothing')
    while True:
        new = fired(m, 'cp_tick', 40000000)
        if not [c for c in new if c[0] == 'timer_add' and c[1] == PSYMS['cp_tick']]: break
    expect(tappable(m, 2) and tappable(m, 3), 'counted and not zero: both rows are tappable')
    m = world(marker=(), folder=True); count(m)
    open_list(m, 2)
    expect(not tappable(m, 2) and tappable(m, 3) and 'window_open' not in m.names(), 'no art 0: that row does nothing; Missing 6 still opens')
    m = world(have=(0, 1, 2, 3, 4, 5, 6, 7), marker=()); count(m)
    expect(not tappable(m, 2) and not tappable(m, 3), 'nothing missing, no marker: neither row opens')

    # 2. The lists: No Art = the albums with an empty marker, Missing = no file at all; each in the album list's order (stock order here and the Artist order below).
    m = world(); count(m)
    new = open_list(m, 3)
    expect(('window_open', 'm1plus_covlist') in new and ('widget_set_tr_text', m.widgets['label_title'], 'Missing Covers') in new, 'Missing Covers opens the plain list page with its title')
    texts = paint(m)
    expect(texts == ['Album 2', 'Album 4', 'Album 6', 'Album 7', 'Artist 2', 'Artist 4', 'Artist 6', 'Artist 7'], f'the missing albums in order, titles then artists ({texts})')
    m.call(PSYMS['cv_on_destroy'], a0=0, a1=0, count=3000000)
    m = world(); count(m)
    new = open_list(m, 2)
    expect(('widget_set_tr_text', m.widgets['label_title'], 'No Art') in new and paint(m) == ['Album 3', 'Album 5', 'Artist 3', 'Artist 5'], 'No Art lists the albums with an empty marker only (3 and 5)')
    # a tap on a row opens that album, as the Albums page does
    SCREEN_Y0 = 30 + 50

    def tap(m, x, y):
        for kind, t in (('down', 1000), ('up', 1080)):
            m.touch(kind, x, SCREEN_Y0 + y, t, fn='cv_on_' + kind)
        return list(m.calls)
    calls = tap(m, 100, 64 + 20)
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ALBUMS'], 5) in calls, 'a tap on the second row opens that album (stock row 5)')
    m.touch('down', 100, SCREEN_Y0 + 20, 1000, fn='cv_on_down'); m.touch('up', 100, SCREEN_Y0 + 20 + 40, 1080, fn='cv_on_up')
    expect(not [c for c in m.calls if c[0] == 'navigator_to_with_context'], 'a release far from the press (a drag) opens nothing')
    m.call(PSYMS['cv_on_destroy'], a0=0, a1=0, count=3000000)
    # the Artist order: display position d is stock row order[d]
    m = world(sort=b'1\n'); count(m)
    open_list(m, 2)
    rows = paint(m)
    m.touch('down', 100, SCREEN_Y0 + 20, 1000, fn='cv_on_down'); m.touch('up', 100, SCREEN_Y0 + 20, 1080, fn='cv_on_up')
    opened = [c for c in m.calls if c[0] == 'navigator_to_with_context' and c[1] == 'albuminfo_page']
    expect(len(rows) == 4 and opened and opened[0][3] == int(rows[0][len('Album '):]), f'in the Artist order the tap opens the stock row of the album shown ({rows}, {opened})')
    m.call(PSYMS['cv_on_destroy'], a0=0, a1=0, count=3000000)

    # 3. Empty after all (the list page opened with nothing: the build made them meanwhile): No albums, no view.
    m = world(); count(m)
    m.call(PSYMS['covlist_open'], a0=1, a1=0, a2=0, count=6000000)
    expect(('widget_set_tr_text', m.widgets['label_status'], 'No albums') in m.calls and ('widget_set_visible', m.widgets['view_grid'], 0) in m.calls, 'an empty list shows "No albums" and hides the view')
    m.call(PSYMS['cv_on_destroy'], a0=0, a1=0, count=3000000)

    # 4. Memory: the album copy, the order and the rows are freed with the window; a second open after the destroy works; a second open while one is up is refused.
    m = world(); count(m)
    open_list(m, 3)
    allocs_before = len([c for c in m.calls if c[0] == 'free'])
    expect(m.call(PSYMS['homecover_list_open'], a0=3, count=6000000) == 0xffffffff, 'a second list while one is up is refused')
    m.call(PSYMS['cv_on_destroy'], a0=0, a1=0, count=3000000)
    freed = [c for c in m.calls if c[0] in ('free', 'deque_destroy')]
    expect(len(freed) >= 3 and allocs_before >= 0, f'destroy frees the rows, the order and the album copy ({[c[0] for c in freed]})')
    open_list(m, 3)
    expect(('window_open', 'm1plus_covlist') in m.calls, 'a list can be opened again after the first closed')
    m.call(PSYMS['cv_on_destroy'], a0=0, a1=0, count=3000000)


def files_tests(ctx):
    """Settings > Developer > Tools > Settings Files (patch/setfiles.c): opens from Developer, every row's label, the values of a seeded file system, and no file read after the page opened."""
    expect, P = ctx.expect, pod_pages
    FP = P.FILES_PAGE
    d_i = next(i for i, r in enumerate(P.DEVELOPER_PAGE.rows) if r.action == P.ACT_PAGE and r.arg == P.FILES_PAGE_INDEX)
    expect(P.DEVELOPER_PAGE.rows[d_i].label == 'Settings Files' and FP.title == 'Settings Files', 'Developer > Tools has a Settings Files link row that opens the page of that title')
    labels = [r.label for r in FP.rows]
    expect(labels == list(P.GUARD_FILES) + [P.FOLDER_LABEL] + list(P.SETTING_FILES) and all(r.action == P.ACT_INFO for r in FP.rows),
           'the rows: the four guard files, the folder, the setting files; all information rows')
    expect(sorted(r.arg for r in FP.rows) == list(range(P.INFO_SF, P.INFO_SF + len(FP.rows))), 'their kinds are unique and consecutive')
    D = '/mnt/data/'
    S = D + 'm1plus/'
    m = Machine()
    for n in ['btn_return', 'btn_backtoplayer'] + [f'pod_row{i}' for i in range(len(FP.rows))] + [f'pod_value{i}' for i in range(len(FP.rows))] + [f'pod_label{i}' for i in range(len(FP.rows))]:
        m.widget(n)
    m.fs[D + 'm1plus-start'], m.fs[D + 'm1plus-bad'] = b'1\n', b''
    m.present.add(S.rstrip('/'))
    m.fs.update({S + 'albums-view': b'1', S + 'playlists-view': b'0\n', S + 'recently-added-view': b'1\n', S + 'home-menu': b'6502\n', S + 'pulldown-tiles': b'2013-4567\n', S + 'cassette-theme': b'12', S + 'search-history': b'a\nb\nc\n',
                 S + 'covers-rebuild': b'1\n', S + 'battery-percentage': b'1'})
    m.call(PSYMS['on_row'], a0=PSYMS[f'pod_rows_{P.DEVELOPER_PAGE_INDEX}'] + 12 * d_i, count=6000000)
    expect(('window_open', FP.key) in m.calls, 'the link row opens m1plus_files')
    want = {'m1plus-start': '1', 'm1plus-run': 'missing', 'm1plus-bad': 'present', 'm1plus-off': 'missing', P.FOLDER_LABEL: 'present', 'albums-view': '1', 'playlists-view': '0', 'recently-added-view': '1',
            'album-order': 'missing', 'cassette-theme': 'other', 'home-menu': '6502', 'pulldown-tiles': '2013-4567', 'battery-percentage': '1', 'search-history': '3', 'covers-rebuild': 'present',
            'keyboard-pinyin': 'missing'}
    got = {r.label: next((c[2] for c in reversed(m.calls) if c[0] == 'widget_set_text_utf8' and c[1] == m.widgets[f'pod_value{i}']), None) for i, r in enumerate(FP.rows)}
    expect(all(got[k] == v for k, v in want.items()), f'the seeded values: {[(k, got[k], v) for k, v in want.items() if got[k] != v]}')
    del m.fs[S + 'albums-view']
    m.call(PSYMS['on_page_fg'], a0=P.FILES_PAGE_INDEX, a1=0, count=3000000)
    expect(not [c for c in m.calls if c[0] in ('open', 'read', 'access', 'timer_add')] and any(c[0] == 'widget_set_text_utf8' for c in m.calls),
           'a refresh of the page (foreground) shows the values it read at open and reads no file, adds no timer')


SECTIONS = [tests, rebuild_tests, clear_tests, cache_tests, covlist_tests, files_tests]


def run(ctx):
    for section in SECTIONS: section(ctx)
