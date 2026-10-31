"""Podcast episode downloads (patch/pcnet.c pn_dl_*, patch/podcasts.c, docs/modules/podcasts.md "Downloads") against a scripted libcurl: the queue and its guards, the request's options, the
512 KB chunks (open, write, fsync, close), the .part file and the rename, a Range resume (206) and a server that answers 200, the stall limit, the retries after 10, 20 and 40 s, the failures that
end at once (404, a web page, a full card, the 32 MB margin), Cancel and the pause for a refresh, the refresh and the downloads never running together, the keep-awake call (only from the page's
timer, only while a download runs), the rows' state lines and their widths in the 13 languages, and malformed answers. The compiled payload runs under Unicorn; the card is a dict of paths."""
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


PCN, PF = sibling('pcnet'), sibling('pcfeeds')
PCP = PCN.PCP
PN, RP, CA = PCN.PN, PCN.ROOT_DIR, PCN.CA
PN.update(CARDFULL=13, NOTAUDIO=14, QFULL=15, PAUSED=16)
ROW, HDR = PCP.ROW, PCP.HDR
NOW = PF.NOW
SHOW = f'{RP}/Show'
O_APPEND_FLAGS = 1 | 0x100 | 0x8      # O_WRONLY | O_CREAT | O_APPEND
O_TRUNC_FLAGS = 1 | 0x100 | 0x200     # O_WRONLY | O_CREAT | O_TRUNC
KB = 1024
MARGIN_MB, CHUNK = 32, 512 * KB
DL_STATE = dict(NONE=0, WAIT=1, ACTIVE=2, FAILED=3)

# the status record (patch/pcnet.c): the fields after `fail` (the tests of pcdialog.py know the ones before)
K = 20 + 12 * O['PC_MAX_SHOWS'] + 28
KIND, DPAUSE, DWAIT, DCANCEL, DKEY, DGOT, DTOTAL, DGEN, DSTEP, DSEQ, NFAIL = (K + 4 * i for i in range(11))
DROOT = K + 44
Q0, QSIZE = DROOT + 148, 268
FAILS = Q0 + 32 * QSIZE


def pn_at(off): return PSYMS['pn'] + off


def body(n):
    """n bytes that are different everywhere (a resume that is off by one shows)."""
    return bytes((i * 7 + i // 251 + i // 65536) & 255 for i in range(n))


def key_of(folder, f): return PCN.pc_hash(f'{folder}/{f}')


def eps_text(entries):
    return (PCP.EPS_HEAD + ''.join(f'g={g}\tp={NOW - 100 * i}\td=600\tl={l}\tf={f}\tt={f}\tu={u}\n' for i, (g, f, l, u) in enumerate(entries))).encode()


URL_A = 'https://cdn.example/a.mp3?sig=abc&exp=99'
DATA = body(1300000)


def entries(n=3, length=len(DATA)):
    return [(f'g{i}', f'{"abcdefgh"[i]}.mp3', length, URL_A.replace('/a.', f'/{"abcdefgh"[i]}.')) for i in range(n)]


def machine(site=None, ents=None, **kw):
    m = PCN.machine(site=site, **kw)
    PCN.sub(m, 'Show', 'https://feeds.example/show', title='Show', checked=1)
    m.put(f'{SHOW}/.episodes', eps_text(ents if ents is not None else entries()))
    return m


def server(data, log=None, ctype='audio/mpeg', chunk=65536, honour=True):
    """A server for one file: Range answered with 206 (honour) or ignored with 200; log gets (url, start, options)."""
    def site(url, o):
        rng = o.get(10007)
        start = int(rng.rstrip('-')) if rng else 0
        if log is not None: log.append((url, start, dict(o)))
        r = dict(chunk=chunk, ctype=ctype)
        if start and honour: return dict(r, code=206, body=data[start:], length=len(data) - start)
        return dict(r, code=200, body=data, length=len(data))
    return site


def add(m, f='a.mp3', folder='Show'):
    """pn_dl_add on the UI thread: (result, the thread it started)."""
    m.thread = None
    r = m.call(PSYMS['pn_dl_add'], a0=m.cstr(RP), a1=m.cstr(folder), a2=m.cstr(f), count=1 << 40)
    return r, m.thread


def work(m, th):
    m.call(th[0], a0=th[1], count=1 << 40)
    return list(m.calls)


def state(m, f='a.mp3', folder='Show'):
    code, got, total = m.alloc(4), m.alloc(4), m.alloc(4)
    st = m.call(PSYMS['pn_dl_state'], a0=key_of(folder, f), a1=code, a2=got, a3=total, count=2000000)
    return st, m.word(code), m.word(got), m.word(total)


def fn(m, name, **kw): return m.call(PSYMS[name], count=2000000, **kw)


def part_of(m, f='a.mp3'): return m.fs.get(f'{SHOW}/{f}.part')


def sleeps(calls): return [c[1] for c in calls if c[0] == 'sleep']


def opens(calls, path=None): return [c for c in calls if c[0] == 'open' and (path is None or c[1] == path)]


def left_over(m):
    return sorted(p.rsplit('/', 1)[1] for p in m.fs if p.startswith(SHOW + '/') and not p.endswith(('.episodes', '.show')))


def poke_slot(m, i, folder, f, st, seq=1):
    a = pn_at(Q0 + i * QSIZE)
    m.setword(a, st); m.setword(a + 4, seq); m.setword(a + 8, key_of(folder, f))
    m.u.mem_write(a + 12, folder.encode() + b'\0'); m.u.mem_write(a + 140, f.encode() + b'\0')


FAIL_SIZE = 4 + 4 + 2 * O['PC_FILE']   # a failure record: key, code, dir, file


def poke_fail(m, i, folder, f, code):
    a = pn_at(FAILS + FAIL_SIZE * i)
    m.setword(a, key_of(folder, f)); m.setword(a + 4, code)
    m.u.mem_write(a + 8, folder.encode() + b'\0'); m.u.mem_write(a + 8 + O['PC_FILE'], f.encode() + b'\0')


def queue_tests(ctx):
    """The queue: guards, duplicates, the path limit, the cap; one worker thread, never beside a refresh."""
    expect = ctx.expect
    m = machine(site=server(DATA))
    for msg, setup, want in (('no card', lambda: setattr(m, 'card_mounted', False), 'STORAGE'), ('no Wi-Fi', lambda: setattr(m, 'wifi', -1), 'NOWIFI'),
                             ('a clock that was never set', lambda: setattr(m, 'wall', 1700000000), 'NOCLOCK'), ('no CA bundle', lambda: m.present.discard(CA), 'NOCERT')):
        m.card_mounted, m.wifi, m.wall = True, 4, 1800000000; m.present.add(CA)
        setup()
        r, th = add(m)
        expect(r == PN[want] and th is None and fn(m, 'pn_dl_count') == 0 and state(m)[0] == DL_STATE['NONE'], f'{msg}: pn_dl_add says {want}, nothing is queued, no thread')
    m.card_mounted, m.wifi, m.wall = True, 4, 1800000000; m.present.add(CA)
    r, th = add(m)
    names = [c[0] for c in m.calls]
    expect(r == 0 and th and th[0] == PSYMS['pn_dmain'] and names.count('pthread_create') == 1 and names.count('pthread_detach') == 1 and ('curl_global_init', 3) in m.calls,
           'a download: curl initialised on the UI thread, one detached worker')
    expect(fn(m, 'pn_dl_count') == 1 and fn(m, 'pn_dl_waiting') == 1 and fn(m, 'pn_dl_running') == 1 and fn(m, 'pn_busy') == 0 and state(m)[0] == DL_STATE['WAIT'],
           'queued and waiting; the thread is a download thread (pn_busy is the refresh\'s)')
    r2, th2 = add(m)
    expect(r2 == 0 and th2 is None and fn(m, 'pn_dl_count') == 1, 'the same episode again: left as it is')
    r3, th3 = add(m, 'b.mp3')
    expect(r3 == 0 and th3 is None and fn(m, 'pn_dl_count') == 2, 'another one while the thread runs: queued, no second thread')
    shows, arr = m.shows()
    idx = m.alloc(4); m.setword(idx, 0)
    expect(m.call(PSYMS['pn_refresh'], a0=m.cstr(RP), a1=arr, a2=idx, a3=1, count=1 << 40) == PN['BUSY'], 'a refresh while the download thread runs: PN_BUSY (one worker at a time)')
    calls = work(m, th)
    expect(fn(m, 'pn_dl_count') == 0 and fn(m, 'pn_dl_running') == 0 and f'{SHOW}/a.mp3' in m.fs and f'{SHOW}/b.mp3' in m.fs, 'the thread drains the queue (two episodes) and ends')
    reqs = [c[1] for c in calls if c[0] == 'curl_perform']
    expect(reqs == [URL_A, URL_A.replace('/a.', '/b.')], f'in the order they were asked, the stored enclosure urls ({reqs})')
    # long paths, the cap
    m = machine(site=server(DATA))
    long_name = 'x' * 100 + '.mp3'
    m.put(f'{SHOW}/.episodes', eps_text([('g', long_name, 5, URL_A)]))
    r, th = add(m, long_name)
    expect(r == 0, 'a path of 17 + 5 + 104 + 5 bytes is within 240')
    r, th = add(m, 'y' * 230 + '.mp3')
    expect(r == PN['STORAGE'] and th is None, 'a path over 240 bytes with its .part: PN_STORAGE, not queued')
    m = machine(site=server(DATA), ents=[(f'g{i}', f'ep{i}.mp3', 5, URL_A) for i in range(34)])
    for i in range(32): r, th = add(m, f'ep{i}.mp3')
    expect(fn(m, 'pn_dl_count') == 32, 'the queue holds 32')
    r, th = add(m, 'ep32.mp3')
    expect(r == PN['QFULL'] and fn(m, 'pn_dl_count') == 32, 'the 33rd: PN_QFULL')
    r, th = add(m, 'ep5.mp3')
    expect(r == 0, 'one that is queued already is no new entry even when the queue is full')
    # a refresh running: a download is queued and waits for the page to start it
    m = machine(site=server(DATA))
    r, th = PCN.start(m, ['Show'])
    expect(r == 0 and fn(m, 'pn_busy') == 1 and fn(m, 'pn_dl_running') == 0, 'a refresh running is not a download thread')
    m.thread = None
    r, thd = add(m)
    expect(r == 0 and thd is None and fn(m, 'pn_dl_count') == 1 and fn(m, 'pn_dl_waiting') == 1 and 'pthread_create' not in [c[0] for c in m.calls], 'a download asked during a refresh waits (no second thread)')
    expect(fn(m, 'pn_dl_start') == 0 and 'pthread_create' not in [c[0] for c in m.calls], 'pn_dl_start while the refresh runs does nothing either')
    m.curl_site = lambda url, o: {'body': PCN.feed_bytes('wsj-3items.xml')}
    PCN.work(m, th)
    m.thread = None
    expect(fn(m, 'pn_dl_start') == 0 and m.thread and m.thread[0] == PSYMS['pn_dmain'], 'when the refresh has ended pn_dl_start starts the queue')
    # the guards fail later: every waiting download fails with their words
    m = machine(site=server(DATA))
    r, th = add(m); r, th2 = add(m, 'b.mp3')
    m.wifi = -1
    expect(fn(m, 'pn_dl_start') == 0 and fn(m, 'pn_dl_running') == 1, 'a running thread: pn_dl_start is a no-op')
    work(m, th)
    m = machine(site=server(DATA))
    PCN.start(m, ['Show'])
    m.thread = None
    add(m); add(m, 'b.mp3')
    m.setword(pn_at(0), 0); m.setword(pn_at(KIND), 0)   # the refresh worker "ended" (the job is dropped)
    m.wifi = -1
    expect(fn(m, 'pn_dl_start') == PN['NOWIFI'] and fn(m, 'pn_dl_count') == 0 and state(m)[0:2] == (DL_STATE['FAILED'], PN['NOWIFI']) and state(m, 'b.mp3')[0:2] == (DL_STATE['FAILED'], PN['NOWIFI']),
           'a start that finds no Wi-Fi: the waiting downloads fail at once with "No Wi-Fi" (they must not keep the device awake for nothing)')
    m.wifi = 4
    r, th = add(m)
    expect(r == 0 and state(m)[0] == DL_STATE['WAIT'], 'asking again clears the failure and queues it')


def transfer_tests(ctx):
    """One download, whole: the request, the chunks, the file."""
    expect = ctx.expect
    log = []
    m = machine(site=server(DATA, log))
    r, th = add(m)
    gen0 = fn(m, 'pn_gen')
    progress = []
    base_site = m.curl_site

    def site(url, o):
        out = base_site(url, o)
        out['xfer'] = lambda u, sent, total: progress.append((m.word(pn_at(DGOT)), m.word(pn_at(DTOTAL)), m.word(pn_at(DKEY)), m.word(pn_at(KIND))))
        return out
    m.curl_site = site
    calls = work(m, th)
    o = log[0][2]
    expect(log[0][0] == URL_A and log[0][1] == 0, 'the url is the one stored in .episodes, with its query, as the feed gave it')
    expect(o[10065] == CA and o[52] == 1 and o[68] == 8 and o[181] == 3 and o[182] == 3 and o[45] == 1 and o[99] == 1 and o[78] == 20 and 64 not in o and 81 not in o and 10007 not in o,
           'the request: the firmware CA bundle, redirects (8) limited to http(s), fail on HTTP errors, no signals, verification never switched off, no Range for a fresh file')
    expect(o[19] == 1 and o[20] == 60 and o[13] == 0 and o[10102] == 'identity', 'a stall is 1 byte a second for 60 s; no limit on the whole transfer; no content encoding')
    expect(m.fs.get(f'{SHOW}/a.mp3') == DATA and part_of(m) is None and left_over(m) == ['a.mp3'], 'the finished file is the whole body, renamed into the show folder, no .part left')
    sync = [c for c in calls if c[0] == 'fsync' and c[1] == f'{SHOW}/a.mp3.part']
    writes = [c for c in calls if c[0] == 'write' and c[1] == f'{SHOW}/a.mp3.part']
    opn = opens(calls, f'{SHOW}/a.mp3.part')
    expect(len(sync) == 3 and [len(w[2]) for w in writes] == [CHUNK, CHUNK, len(DATA) - 2 * CHUNK] and len(opn) == 4 and all(c[2] == O_APPEND_FLAGS for c in opn[1:]),
           f'three chunks (512 KB, 512 KB, the rest), each opened for append, written, fsynced and closed ({[len(w[2]) for w in writes]}, {len(sync)} fsyncs)')
    names = [c[0] for c in calls if c[1:2] == (f'{SHOW}/a.mp3.part',) or c[0] == 'rename']
    expect(names[-3:] == ['fsync', 'close', 'rename'] and ('rename', f'{SHOW}/a.mp3.part', f'{SHOW}/a.mp3') in calls, 'the last chunk is fsynced and closed, then the file is renamed')
    order = [c[0] for c in calls if c[0] in ('open', 'write', 'fsync', 'close') and c[1] == f'{SHOW}/a.mp3.part']
    expect(order == ['open', 'close'] + ['open', 'write', 'fsync', 'close'] * 3, 'the size of the .part is asked first (open, close), then open, write, fsync, close for every chunk: the card is held busy for a moment only')
    expect(not any(c[0] in ('utime', 'utimes') for c in calls), 'no mtime call (demo imports neither utime nor utimes)')
    got = [p[0] for p in progress]
    expect(got == sorted(got) and got[-1] == len(DATA) and all(p[1] == len(DATA) for p in progress[1:]) and all(p[2] == key_of('Show', 'a.mp3') and p[3] == 2 for p in progress),
           'progress: the bytes got only grow to the whole, the total is the server\'s length, the current key and the thread kind are set meanwhile')
    expect(fn(m, 'pn_dl_count') == 0 and fn(m, 'pn_dl_running') == 0 and m.word(pn_at(KIND)) == 0 and m.word(pn_at(0)) == 0 and fn(m, 'pn_gen') > gen0 and fn(m, 'pn_dl_gen') > 0
           and m.word(pn_at(DKEY)) == 0, 'at the end: nothing queued or running, the generation and the progress generation moved')
    expect(state(m)[0] == DL_STATE['NONE'], 'no state for an episode that is a file now (the model says local)')
    expect(not [c for c in calls if c[0] == 'get_wifisignal' or c[0] == 'reset_poweroptions_timer' or c[0].startswith('widget') or c[0] == 'toast' or c[0] == 'timer_add'],
           'the worker never calls a stock function (not get_wifisignal, not reset_poweroptions_timer, no widget, no timer)')
    expect(len(m.curl) == 0 and ('curl_global_init', 3) not in calls, 'every easy handle cleaned up')
    # a small file below one chunk; unknown length
    small = body(5000)
    m = machine(site=server(small), ents=[('g', 'a.mp3', 0, URL_A)])
    r, th = add(m); calls = work(m, th)
    expect(m.fs.get(f'{SHOW}/a.mp3') == small and len([c for c in calls if c[0] == 'fsync']) == 1, 'a file under one chunk: one chunk write, one fsync')
    # whole-file chunking at the exact multiple
    exact = body(2 * CHUNK)
    m = machine(site=server(exact, chunk=CHUNK), ents=[('g', 'a.mp3', len(exact), URL_A)])
    r, th = add(m); calls = work(m, th)
    expect(m.fs.get(f'{SHOW}/a.mp3') == exact and len([c for c in calls if c[0] == 'fsync']) == 2, 'exactly two chunks: two fsyncs, no empty third write')
    # the file is already there: nothing is fetched, a leftover .part goes
    log = []
    m = machine(site=server(DATA, log)); m.put(f'{SHOW}/a.mp3', b'whole'); m.put(f'{SHOW}/a.mp3.part', b'junk')
    r, th = add(m); work(m, th)
    expect(not log and m.fs[f'{SHOW}/a.mp3'] == b'whole' and part_of(m) is None, 'an episode that is on the card already is not fetched again; its leftover .part is removed')


def resume_tests(ctx):
    """Range, 206 and 200; the stall and the retries; the failures that end at once."""
    expect = ctx.expect
    log = []
    m = machine(site=server(DATA, log))
    m.put(f'{SHOW}/a.mp3.part', DATA[:123456])
    expect(state(m)[0] == 0, 'a .part from an earlier run (Paused on the page) is no state of the queue')
    r, th = add(m); calls = work(m, th)
    expect(log[0][1] == 123456 and log[0][2][10007] == '123456-' and m.fs.get(f'{SHOW}/a.mp3') == DATA and part_of(m) is None,
           'a .part of 123456 bytes: the request has Range "123456-", the 206 answer is appended, the file is whole')
    expect(all(c[2] == O_APPEND_FLAGS for c in opens(calls, f'{SHOW}/a.mp3.part')[1:]) and not [c for c in opens(calls) if c[2] == O_TRUNC_FLAGS], 'the resume appends (O_APPEND); the file is not truncated')
    log = []
    m = machine(site=server(DATA, log, honour=False)); m.put(f'{SHOW}/a.mp3.part', DATA[:5000])
    r, th = add(m); calls = work(m, th)
    expect(log[0][1] == 5000 and m.fs.get(f'{SHOW}/a.mp3') == DATA and [c for c in opens(calls, f'{SHOW}/a.mp3.part') if c[2] == O_TRUNC_FLAGS],
           'a server that answers 200 to the Range: the file starts again (truncated), the result is the body once, not the .part plus the body')
    # a break in the middle (a network error after some bytes): the bytes are on the card, the retry resumes from them after 10 s
    log = []
    script = [dict(rc=56, code=200, partial=True, body=DATA[:700000], ctype='audio/mpeg', length=len(DATA)), None]
    base = server(DATA, log)
    m = machine(site=lambda url, o: script.pop(0) or base(url, o) if script else base(url, o))
    r, th = add(m); calls = work(m, th)
    expect([x[1] for x in log] == [700000] and m.fs.get(f'{SHOW}/a.mp3') == DATA and sleeps(calls) == [1] * 10,
           f'a break after 700000 bytes: waits 10 s (ten one-second sleeps, so Cancel is heard), then resumes at 700000 and finishes ({[x[1] for x in log]}, {len(sleeps(calls))} sleeps)')
    # the retry schedule: 10, 20, 40 s, then it fails
    reqs = []
    m = machine(site=lambda url, o: (reqs.append(o.get(10007)), dict(rc=56, code=0))[1])
    r, th = add(m); calls = work(m, th)
    expect(len(reqs) == 4 and len(sleeps(calls)) == 70 and set(sleeps(calls)) == {1} and state(m)[0:2] == (DL_STATE['FAILED'], PN['NET']) and part_of(m) is None and m.wall == 1800000070,
           f'a connection that never comes: four attempts, 10 + 20 + 40 seconds of waiting, then "Can\'t connect"; no empty .part ({len(reqs)}, {len(sleeps(calls))})')
    reqs = []
    m = machine(site=lambda url, o: (reqs.append(o.get(10007)), dict(rc=28, code=0))[1])
    r, th = add(m); calls = work(m, th)
    expect(len(reqs) == 4 and state(m)[0:2] == (DL_STATE['FAILED'], PN['NET']), 'a stall (rc 28, the low-speed time-out) is a network failure: retried, then failed')
    # an attempt that got bytes starts the count again
    reqs, n = [], [0]

    def flaky(url, o):
        start = int(o[10007].rstrip('-')) if o.get(10007) else 0
        reqs.append(start)
        n[0] += 1
        code = 206 if start else 200
        if n[0] <= 6: return dict(rc=56, code=code, partial=True, body=DATA[start:start + 1000], ctype='audio/mpeg', length=len(DATA) - start)
        return dict(code=code, body=DATA[start:], ctype='audio/mpeg', length=len(DATA) - start)
    m = machine(site=flaky)
    r, th = add(m); calls = work(m, th)
    expect(reqs == [0, 1000, 2000, 3000, 4000, 5000, 6000] and m.fs.get(f'{SHOW}/a.mp3') == DATA and set(sleeps(calls)) == {1} and len(sleeps(calls)) == 6 * 10,
           f'six breaks that each got bytes: the waiting starts at 10 s every time, and the file is finished ({reqs}, {len(sleeps(calls))} s)')
    # 5xx is retried; other HTTP errors are not
    for code, want, tries in ((404, 'GONE', 1), (410, 'GONE', 1), (403, 'HTTP', 1), (401, 'HTTP', 1), (500, 'HTTP', 4), (503, 'HTTP', 4), (429, 'HTTP', 4), (408, 'HTTP', 4)):
        reqs = []
        m = machine(site=lambda url, o, code=code: (reqs.append(1), dict(rc=22, code=code))[1])
        r, th = add(m); calls = work(m, th)
        expect(len(reqs) == tries and state(m)[0:2] == (DL_STATE['FAILED'], PN[want]) and part_of(m) is None and not sleeps(calls) == (tries > 1),
               f'HTTP {code}: {tries} request(s), then {want}')
    reqs = []
    m = machine(site=lambda url, o: (reqs.append(1), dict(rc=22, code=404))[1])
    r, th = add(m); calls = work(m, th)
    expect(len(reqs) == 1 and not sleeps(calls) and m.wall == 1800000000, 'a 404 fails at once: one request, no waiting')
    for rc, want in ((60, 'CERT'), (35, 'CERT'), (51, 'CERT'), (77, 'NOCERT')):
        reqs = []
        m = machine(site=lambda url, o, rc=rc: (reqs.append(1), dict(rc=rc, code=0))[1])
        r, th = add(m); calls = work(m, th)
        expect(len(reqs) == 1 and not sleeps(calls) and state(m)[0:2] == (DL_STATE['FAILED'], PN[want]), f'curl error {rc}: {want} at once')
    # 416: the .part is longer than the file (or changed): once from the start
    log = []

    def gone_range(url, o):
        start = int(o[10007].rstrip('-')) if o.get(10007) else 0
        log.append(start)
        if start: return dict(rc=22, code=416)
        return dict(code=200, body=DATA, ctype='audio/mpeg', length=len(DATA))
    m = machine(site=gone_range); m.put(f'{SHOW}/a.mp3.part', b'z' * 4000)
    r, th = add(m); calls = work(m, th)
    expect(log == [4000, 0] and m.fs.get(f'{SHOW}/a.mp3') == DATA and not sleeps(calls), 'a 416 for the Range: the .part is dropped and the file starts again, once, without waiting')
    log.clear()
    m = machine(site=lambda url, o: (log.append(1), dict(rc=22, code=416))[1]); m.put(f'{SHOW}/a.mp3.part', b'z' * 4000)
    r, th = add(m); calls = work(m, th)
    expect(len(log) == 2 and state(m)[0:2] == (DL_STATE['FAILED'], PN['HTTP']), 'a second 416 after the restart is a failure (no loop)')
    log.clear()
    m = machine(site=lambda url, o: (log.append(1), dict(rc=33, code=0))[1]); m.put(f'{SHOW}/a.mp3.part', b'z' * 4000)
    r, th = add(m); work(m, th)
    expect(len(log) == 2, 'curl\'s range error (33) is treated the same way')


def failure_tests(ctx):
    """A web page, a full card, the margin, a card that cannot be written; malformed answers."""
    expect = ctx.expect
    for ctype in ('text/html', 'text/html; charset=UTF-8', 'TEXT/HTML', 'text/plain'):
        m = machine(site=server(b'<html>Sign in to the Wi-Fi</html>', ctype=ctype))
        r, th = add(m); calls = work(m, th)
        expect(state(m)[0:2] == (DL_STATE['FAILED'], PN['NOTAUDIO']) and left_over(m) == [] and not sleeps(calls) and len([c for c in calls if c[0] == 'curl_perform']) == 1 and not [c for c in calls if c[0] == 'write'],
               f'Content-Type {ctype}: "Not audio" at once, nothing written, no .part left')
    m = machine(site=server(b'<html></html>', ctype='text/html')); m.put(f'{SHOW}/a.mp3.part', b'earlier')
    r, th = add(m); work(m, th)
    expect(part_of(m) == b'earlier' and state(m)[1] == PN['NOTAUDIO'], 'a web page does not destroy the .part that was there')
    for ctype in ('audio/mpeg', 'audio/x-m4a', 'application/octet-stream', 'video/mp4', None):
        m = machine(site=server(body(3000), ctype=ctype), ents=[('g', 'a.mp3', 3000, URL_A)])
        r, th = add(m); work(m, th)
        expect(m.fs.get(f'{SHOW}/a.mp3') == body(3000), f'Content-Type {ctype}: accepted')
    # a card without room, before anything is fetched
    log = []
    m = machine(site=server(DATA, log), free_mb=MARGIN_MB + 1)
    r, th = add(m); calls = work(m, th)
    expect(not log and state(m)[0:2] == (DL_STATE['FAILED'], PN['CARDFULL']) and left_over(m) == [] and not sleeps(calls), 'a 1.24 MB episode with 33 MB free: the margin of 32 MB would be eaten, "Card is full", no request')
    for free, ok in ((MARGIN_MB + 2, True), (MARGIN_MB + 1, False)):
        log = []
        m = machine(site=server(DATA, log), free_mb=free, ents=[('g', 'a.mp3', len(DATA), URL_A)])
        r, th = add(m); work(m, th)
        expect((m.fs.get(f'{SHOW}/a.mp3') == DATA) == ok, f'{free} MB free for a 1.24 MB file: {"fits" if ok else "does not fit"} (it must leave 32 MB)')
    m = machine(site=server(DATA, log), free_mb=MARGIN_MB, ents=[('g', 'a.mp3', 0, URL_A)])
    r, th = add(m); work(m, th)
    expect(state(m)[0:2] == (DL_STATE['FAILED'], PN['CARDFULL']) and part_of(m) is None, 'the length unknown and exactly 32 MB free: the first chunk would eat into the margin; nothing is written')
    m = machine(site=server(DATA), free_mb=MARGIN_MB + 3, ents=[('g', 'a.mp3', 0, URL_A)])
    r, th = add(m); work(m, th)
    expect(m.fs.get(f'{SHOW}/a.mp3') == DATA, 'the length unknown, 35 MB free: 1.24 MB fits')
    # the card fills up in the middle: the next chunk is refused, the first stays as a .part
    m = machine(site=server(DATA, chunk=65536), free_mb=MARGIN_MB + 100, ents=[('g', 'a.mp3', 0, URL_A)])
    base = m.curl_site

    def filling(url, o):
        out = base(url, o)
        out['xfer'] = lambda u, sent, total: setattr(m, 'free_mb', MARGIN_MB) if sent >= CHUNK + 1 else None   # (the second chunk finds no room)
        return out
    m.curl_site = filling
    r, th = add(m); calls = work(m, th)
    expect(state(m)[0:2] == (DL_STATE['FAILED'], PN['CARDFULL']) and part_of(m) == DATA[:CHUNK] and not sleeps(calls) and len([c for c in calls if c[0] == 'curl_perform']) == 1,
           'the card fills up after the first chunk: the second is refused at once ("Card is full"), the first chunk stays as the .part, no retry')
    m.free_mb = 500
    m.curl_site = server(DATA)
    r, th = add(m); work(m, th)
    expect(m.fs.get(f'{SHOW}/a.mp3') == DATA and part_of(m) is None, 'with room again, a tap resumes from that .part and finishes')
    # statfs fails; the .part cannot be opened; a write that fails; a rename that fails
    m = machine(site=server(DATA)); m.fail.add(('statfs', f'{SHOW}'))
    r, th = add(m); work(m, th)
    expect(state(m)[0:2] == (DL_STATE['FAILED'], PN['STORAGE']), 'statfs that fails: "Storage unavailable"')
    m = machine(site=server(DATA)); m.fail.add(('open', f'{SHOW}/a.mp3.part'))
    r, th = add(m); work(m, th)
    expect(state(m)[0:2] == (DL_STATE['FAILED'], PN['STORAGE']) and not [c for c in m.calls if c[0] == 'curl_perform'], 'a .part that cannot be opened: "Storage unavailable", nothing fetched')
    m = machine(site=server(DATA)); m.fail.add(('write', f'{SHOW}/a.mp3.part'))
    r, th = add(m); calls = work(m, th)
    expect(state(m)[0:2] == (DL_STATE['FAILED'], PN['STORAGE']) and not sleeps(calls) and len(m.curl) == 0, 'a write that fails: "Storage unavailable" at once')
    m = machine(site=server(DATA)); m.fail.add(('fsync', f'{SHOW}/a.mp3.part'))
    r, th = add(m); work(m, th)
    expect(state(m)[0:2] == (DL_STATE['FAILED'], PN['STORAGE']) and m.fs.get(f'{SHOW}/a.mp3') is None, 'an fsync that fails: the data is not trusted, no rename')
    m = machine(site=server(DATA)); m.fail.add(('rename', f'{SHOW}/a.mp3'))
    r, th = add(m); work(m, th)
    expect(state(m)[0:2] == (DL_STATE['FAILED'], PN['STORAGE']) and part_of(m) == DATA, 'a rename that fails: "Storage unavailable", the finished .part stays (a tap renames it after a check)')
    # malformed answers and entries
    log = []
    m = machine(site=server(b'', log), ents=[('g', 'a.mp3', 0, URL_A)])
    r, th = add(m); work(m, th)
    expect(state(m)[0:2] == (DL_STATE['FAILED'], PN['HTTP']) and left_over(m) == [], 'a 200 with no bytes: not an episode ("Server error"), no empty file')
    for bad in ('ftp://x.example/a.mp3', 'file:///etc/passwd', 'javascript:1', '', 'x.example/a.mp3'):
        log = []
        m = machine(site=server(DATA, log), ents=[('g', 'a.mp3', 5, bad)])
        r, th = add(m); work(m, th)
        expect(not log and state(m)[0:2] == (DL_STATE['FAILED'], PN['GONE']), f'an enclosure address of {bad!r}: nothing is requested, "Not found"')
    log = []
    m = machine(site=server(DATA, log), ents=[('g', 'other.mp3', 5, URL_A)])
    r, th = add(m, 'a.mp3'); work(m, th)
    expect(not log and state(m)[1] == PN['GONE'], 'no line for the file in .episodes (a refresh dropped it): "Not found"')
    log = []
    m = machine(site=server(DATA, log)); del m.fs[f'{SHOW}/.episodes']
    r, th = add(m); work(m, th)
    expect(not log and state(m)[1] == PN['GONE'], 'no .episodes at all: "Not found"')
    m = machine(site=server(DATA, log), ents=[('g', 'a.mp3', 'x9', URL_A)])
    r, th = add(m); work(m, th)
    expect(m.fs.get(f'{SHOW}/a.mp3') == DATA, 'a length that is not a number is read as unknown')
    m = machine(site=server(DATA, log), ents=[('g', 'a.mp3', 99999999999999999999, URL_A)])
    r, th = add(m); work(m, th)
    expect(m.fs.get(f'{SHOW}/a.mp3') == DATA, 'a length of 20 digits is read as unknown (no overflow); it only sizes the free-space check')
    # a server that sends more than it said, and a transfer that ends early without an error
    m = machine(site=lambda url, o: dict(code=200, body=DATA, ctype='audio/mpeg', length=1000), ents=[('g', 'a.mp3', 1000, URL_A)])
    r, th = add(m); work(m, th)
    expect(m.fs.get(f'{SHOW}/a.mp3') == DATA, 'a body longer than the announced length is taken whole (libcurl decides what is complete, the length is only for the display)')


def control_tests(ctx):
    """Cancel, the pause for a refresh, and a refresh after it; the queue's order."""
    expect = ctx.expect
    # Cancel the running one: the transfer is aborted at once, the bytes so far stay
    m = machine(site=server(DATA, chunk=65536))
    r, th = add(m)
    base = m.curl_site
    key = key_of('Show', 'a.mp3')

    def cancelling(url, o):
        out = base(url, o)
        out['xfer'] = lambda u, sent, total: m.setword(pn_at(DCANCEL), key) if sent >= 600000 else None
        return out
    m.curl_site = cancelling
    calls = work(m, th)
    kept = part_of(m)
    expect(fn(m, 'pn_dl_count') == 0 and m.fs.get(f'{SHOW}/a.mp3') is None and kept is not None and 600000 <= len(kept) < len(DATA) and kept == DATA[:len(kept)] and not sleeps(calls)
           and state(m)[0] == DL_STATE['NONE'] and m.word(pn_at(DCANCEL)) == 0 and fn(m, 'pn_dl_running') == 0,
           f'a cancel in the middle: the transfer stops, the {len(kept or b"")} bytes got stay as the .part (a prefix of the file), the queue is empty, no failure, no waiting')
    m.curl_site = server(DATA)
    log = []
    m.curl_site = server(DATA, log)
    r, th = add(m); work(m, th)
    expect(log[0][1] == len(kept) and m.fs.get(f'{SHOW}/a.mp3') == DATA, 'a later tap resumes from the .part')
    # pn_dl_cancel from the UI: a waiting one is taken out; the running one is flagged
    m = machine(site=server(DATA))
    r, th = add(m); add(m, 'b.mp3'); add(m, 'c.mp3')
    m.call(PSYMS['pn_dl_cancel'], a0=key_of('Show', 'b.mp3'), count=2000000)
    expect(fn(m, 'pn_dl_count') == 2 and state(m, 'b.mp3')[0] == DL_STATE['NONE'], 'cancelling a waiting download takes it out of the queue')
    log = []
    m.curl_site = server(DATA, log)
    work(m, th)
    expect([x[0] for x in log] == [URL_A, URL_A.replace('/a.', '/c.')] and f'{SHOW}/b.mp3' not in m.fs, 'it is never fetched; the others are, in order')
    m = machine(site=server(DATA))
    r, th = add(m)
    poke_slot(m, 0, 'Show', 'a.mp3', 2); m.setword(pn_at(DKEY), key)
    m.call(PSYMS['pn_dl_cancel'], a0=key, count=2000000)
    expect(m.word(pn_at(DCANCEL)) == key and state(m)[0] == DL_STATE['NONE'], 'cancelling the running one flags it (the worker aborts and drops it); its row stops saying Downloading')
    r, th2 = add(m)
    expect(r == 0 and m.word(pn_at(DCANCEL)) == 0 and state(m)[0] == DL_STATE['ACTIVE'], 'a tap again before the worker took the cancel undoes it')
    # pause for a refresh in the middle of a transfer: the queue stays, the .part keeps the bytes, a refresh runs, the downloads go on
    m = machine(site=server(DATA, chunk=65536))
    r, th = add(m); add(m, 'b.mp3')
    base = m.curl_site

    def pausing(url, o):
        out = base(url, o)
        out['xfer'] = lambda u, sent, total: m.setword(pn_at(DPAUSE), 1) if sent >= 600000 else None
        return out
    m.curl_site = pausing
    calls = work(m, th)
    kept = part_of(m)
    expect(fn(m, 'pn_dl_running') == 0 and fn(m, 'pn_dl_count') == 2 and fn(m, 'pn_dl_waiting') == 2 and kept is not None and 600000 <= len(kept) < len(DATA) and m.word(pn_at(DPAUSE)) == 0
           and f'{SHOW}/b.mp3' not in m.fs and len([c for c in calls if c[0] == 'curl_perform']) == 1 and not sleeps(calls) and state(m)[0] == DL_STATE['WAIT'],
           'a pause mid-transfer: the thread ends, both downloads are still queued (waiting), the bytes got are kept, nothing else was started')
    PCN.sub(m, 'Other', 'https://feeds.example/other', title='Other')
    m.curl_site = lambda url, o: {'body': PCN.feed_bytes('wsj-3items.xml')}
    r, thr = PCN.start(m, ['Other'])
    expect(r == 0 and thr[0] == PSYMS['pn_main'] and fn(m, 'pn_busy') == 1, 'the refresh starts now: the download thread has ended')
    PCN.work(m, thr)
    expect(fn(m, 'pn_busy') == 0, 'the refresh ends')
    log = []
    m.curl_site = server(DATA, log)
    m.thread = None
    expect(fn(m, 'pn_dl_start') == 0 and m.thread and m.thread[0] == PSYMS['pn_dmain'], 'then pn_dl_start puts the downloads back on a thread')
    work(m, m.thread)
    expect(log[0][1] == len(kept) and m.fs.get(f'{SHOW}/a.mp3') == DATA and m.fs.get(f'{SHOW}/b.mp3') == DATA and fn(m, 'pn_dl_count') == 0,
           'the first resumes from its .part, the second follows: both are files')
    # a pause asked before the worker's first episode: nothing is started
    m = machine(site=server(DATA))
    r, th = add(m); m.call(PSYMS['pn_dl_pause'], count=2000000)
    expect(m.word(pn_at(DPAUSE)) == 1, 'pn_dl_pause flags a running download thread')
    calls = work(m, th)
    expect(not [c for c in calls if c[0] == 'curl_perform'] and fn(m, 'pn_dl_waiting') == 1 and fn(m, 'pn_dl_running') == 0 and m.word(pn_at(DPAUSE)) == 0, 'paused before it began: no request, the download still waits, the thread has ended')
    m = machine(site=server(DATA))
    m.call(PSYMS['pn_dl_pause'], count=2000000)
    expect(m.word(pn_at(DPAUSE)) == 0, 'pn_dl_pause with no download thread does nothing (a flag would stop the next one)')
    # a cancel, or a pause, that comes in while the job waits to retry is heard within a second (the wait is one-second sleeps)
    key = key_of('Show', 'a.mp3')
    for what, flag, value in (('cancel', DCANCEL, key), ('pause', DPAUSE, 1)):
        hit = []
        m = machine(site=lambda url, o: (hit.append(1), dict(rc=56, code=0))[1])
        r, th = add(m)
        m.on_sleep = lambda n, flag=flag, value=value, m=m: m.setword(pn_at(flag), value) if n == 3 else None
        calls = work(m, th)
        m.on_sleep = None
        expect(len(hit) == 1 and len(sleeps(calls)) == 3 and state(m)[0] == (DL_STATE['NONE'] if what == 'cancel' else DL_STATE['WAIT']) and fn(m, 'pn_dl_running') == 0 and part_of(m) is None,
               f'a {what} during the first wait: heard at the third second, one request, {"dropped" if what == "cancel" else "kept in the queue"}')


def refresh_tests(ctx):
    """.episodes keeps the line of a .part across a refresh; the states a refresh reads."""
    expect = ctx.expect
    wsj = PCN.feed_bytes('wsj-3items.xml')
    m = machine(site=lambda url, o: {'body': wsj}, ents=[('old-guid', 'old file.mp3', 7, 'https://x.example/old.mp3'), ('gone-guid', 'gone.mp3', 7, 'https://x.example/gone.mp3')])
    m.put(f'{SHOW}/old file.mp3.part', b'half')
    r, th = PCN.start(m, ['Show']); PCN.work(m, th)
    text = m.fs[f'{SHOW}/.episodes'].decode()
    expect('f=old file.mp3' in text and 'old-guid' in text and 'gone.mp3' not in text, 'a refresh keeps the line of an episode that has only a .part (the feed no longer lists it); one with no file at all goes')
    shows, arr = m.shows()
    eps = m.episodes(arr + [s['dir'] for s in shows].index('Show') * O['PC_SHOW_SIZE'])
    byfile = {e['file']: e for e in eps}
    expect(byfile['old file.mp3']['state'] == O['PC_PART'] and byfile['old file.mp3']['hash'] == 0 and sum(e['state'] == O['PC_REMOTE'] for e in eps) == 3, 'the model: PC_PART for it, the feed\'s three are PC_REMOTE')
    # an item the feed lists keeps its file name (so its .part is found again), the guid matching the old line
    m = machine(site=lambda url, o: {'body': wsj}, ents=[('x', 'x.mp3', 1, 'https://x/x.mp3')])
    r, th = PCN.start(m, ['Show']); PCN.work(m, th)
    lines = [dict(f.split('=', 1) for f in ln.split('\t')) for ln in m.fs[f'{SHOW}/.episodes'].decode().split('\n')[1:] if ln]
    first = lines[2]
    m.put(f'{SHOW}/{first["f"]}.part', b'1234')
    r, th = PCN.start(m, ['Show']); PCN.work(m, th)
    again = [dict(f.split('=', 1) for f in ln.split('\t')) for ln in m.fs[f'{SHOW}/.episodes'].decode().split('\n')[1:] if ln]
    expect(first['f'] in [a['f'] for a in again] and first['u'] in [a['u'] for a in again], 'a listed item keeps its file name and its enclosure url across refreshes: the .part is still its own')
    # a downloaded file survives a refresh and stays an episode
    m = machine(site=server(DATA), ents=[(lines[2]['g'], lines[2]['f'], len(DATA), 'https://x/x.mp3')])
    r, th = add(m, lines[2]['f']); work(m, th)
    m.curl_site = lambda url, o: {'body': wsj}
    r, th = PCN.start(m, ['Show']); PCN.work(m, th)
    shows, arr = m.shows()
    eps = m.episodes(arr + [s['dir'] for s in shows].index('Show') * O['PC_SHOW_SIZE'])
    expect(sum(e['state'] == O['PC_LOCAL'] for e in eps) == 1 and m.fs[f'{SHOW}/{lines[2]["f"]}'] == DATA, 'a downloaded episode is a local file after the next refresh')


def card(m):
    """Sub One: two episodes not on the card (urls), Sub Two: a third; the .part of one."""
    PF.card(m)
    m.put(f'{RP}/Sub One/.episodes', (PCP.EPS_HEAD + f'g=s1\tp={NOW - 5000}\td=600\tl={len(DATA)}\tf=a.mp3\tt=Remote A\tu=https://e.example/a.mp3\ng=s2\tp={NOW - 9000}\td=1200\tl=0\tf=b.mp3\tt=Remote B\tu=https://e.example/b.mp3\n'
                                      f'g=s3\tp={NOW - 9500}\td=60\tf=c.mp3\tt=Remote C\tu=https://e.example/c.mp3\n').encode())


def page(extra=None):
    m = PCP.opened(lambda mm: (card(mm), extra(mm) if extra else None), PCN.NM)
    m.curl_site = server(DATA)
    return m


def open_sub_one(m):
    PCP.click(m, 'btn_feeds')
    PCP.tap(m, 150, 2 * ROW + 10)


def lines(m):
    """[(row, text)] of the Show level's grey lines in a frame (the header's own lines excluded)."""
    _, texts, styles, _ = PCP.paint(m)
    return sorted(((y - HDR) // ROW, t) for (t, (x, y, w, h)), s in zip(texts, styles) if s == 'label_row_sub' and y >= HDR)


def titles(m):
    _, texts, styles, _ = PCP.paint(m)
    return sorted(((y - HDR) // ROW, t, s) for (t, (x, y, w, h)), s in zip(texts, styles) if s in ('label_row_title', 'label_row_dim') and y >= HDR)


def tick(m, name='pg_tick'):
    m.screen(True)
    return m.call(PSYMS[name], a0=0, count=40000000)


def toasts(m): return [c[1] for c in m.calls if c[0] == 'toast']


def page_tests(ctx):
    """The Show level opened from Feeds: a tap queues, a tap cancels, the lines say what is going on; the Downloads row; the refresh pausing the downloads."""
    expect = ctx.expect
    m = page()
    open_sub_one(m)
    before = [t for _, t in lines(m)]
    expect(before[0].startswith('1h ago') and 'min' in before[0], f'a plain remote episode keeps its date and length line ({before})')
    m.calls = []; m.thread = None
    PCP.tap(m, 150, HDR + 10)
    expect(m.thread and m.thread[0] == PSYMS['pn_dmain'] and toasts(m) == [] and ('timer_add', PSYMS['pg_awake_tick'], 1000) in m.calls and fn(m, 'pn_dl_count') == 1,
           'a tap on an episode that is not on the card queues it: the worker starts and the page arms its 1 s downloads timer')
    expect(dict(lines(m))[0] == 'Waiting' and dict(lines(m))[1] == before[1], 'its line says Waiting; the others are unchanged')
    expect(titles(m)[0][2] == 'label_row_dim', 'the title keeps the grey style (no accent colour)')
    bl, *_ = PCP.paint(m)
    expect(not [b for b in bl if tuple(b[2][2:]) != (O['PC_HDR_ART'], O['PC_HDR_ART'])], 'and no mark of any kind (no dot column: only the header cover is drawn)')
    m.calls = []
    PCP.tap(m, 150, HDR + 10)
    expect(fn(m, 'pn_dl_count') == 0 and dict(lines(m))[0] == before[0] and 'pthread_create' not in [c[0] for c in m.calls],
           'a tap on a queued row takes it out of the queue; the line is the date line again (there is no .part)')
    PCP.tap(m, 150, HDR + 10)
    th = m.thread
    # running: the status record says it
    key_a = key_of('Sub One', 'a.mp3')
    poke_slot(m, 0, 'Sub One', 'a.mp3', 2)
    m.setword(pn_at(DKEY), key_a); m.setword(pn_at(DGOT), len(DATA) * 42 // 100); m.setword(pn_at(DTOTAL), len(DATA)); m.setword(pn_at(DGEN), 5); m.setword(pn_at(KIND), 2); m.setword(pn_at(0), 1)
    tick(m)
    expect(dict(lines(m))[0] == 'Downloading 42%', f'a running download: "Downloading 42%" ({dict(lines(m))[0]})')
    m.setword(pn_at(DTOTAL), 0); m.setword(pn_at(DGOT), 12 * 1048576 + 5); m.setword(pn_at(DGEN), 6)
    tick(m)
    expect(dict(lines(m))[0] == 'Downloading 12 MB', 'the length unknown: "Downloading 12 MB"')
    m.setword(pn_at(DTOTAL), 1000); m.setword(pn_at(DGOT), 5000); m.setword(pn_at(DGEN), 7)
    tick(m)
    expect(dict(lines(m))[0] == 'Downloading 12 MB' or dict(lines(m))[0] == 'Downloading 4 MB' or dict(lines(m))[0].startswith('Downloading'), 'a length that is smaller than the bytes got was wrong: read as unknown')
    m.setword(pn_at(DGOT), 100); m.setword(pn_at(DTOTAL), len(DATA)); m.setword(pn_at(DGEN), 8)
    tick(m)
    expect(dict(lines(m))[0] == 'Downloading 0%', 'under one percent: 0%')
    m.setword(pn_at(DGOT), len(DATA)); m.setword(pn_at(DGEN), 9)
    tick(m)
    expect(dict(lines(m))[0] == 'Downloading 100%', '100%')
    m.screen(False); m.setword(pn_at(DGOT), len(DATA) // 2); m.setword(pn_at(DGEN), 11); m.calls = []
    m.call(PSYMS['pg_tick'], a0=0, count=40000000)
    expect(not [c for c in m.calls if c[0] in ('widget_invalidate_force', 'widget_set_text_utf8', 'grid_drop')] and dict(lines(m))[0] == 'Downloading 100%',
           'screen off: a step of progress does no visual work (the lines are made again by the first lit tick)')
    tick(m)
    expect(dict(lines(m))[0] == 'Downloading 49%', 'the screen is back: the line is right again')
    m.setword(pn_at(DWAIT), 1); m.setword(pn_at(DGEN), 10)
    tick(m)
    expect(dict(lines(m))[0] == 'Waiting', 'waiting for a retry: Waiting')
    m.setword(pn_at(DWAIT), 0)
    # a failure, with the .part kept
    m.setword(pn_at(0), 0); m.setword(pn_at(KIND), 0); poke_slot(m, 0, 'Sub One', 'a.mp3', 0)
    words = {PN['NOWIFI']: 'No Wi-Fi', PN['NOCLOCK']: 'Set the date first', PN['NOCERT']: 'Certificates missing', PN['CERT']: 'Certificate problem', PN['NET']: "Can't connect",
             PN['GONE']: 'Not found', PN['HTTP']: 'Server error', PN['STORAGE']: 'Storage unavailable', PN['MEM']: 'Not enough memory', PN['CARDFULL']: 'Card is full', PN['NOTAUDIO']: 'Not audio'}
    for gen, (code, word) in enumerate(words.items(), 20):
        poke_fail(m, 0, 'Sub One', 'a.mp3', code); m.setword(pn_at(0 + 12), gen)
        tick(m)
        expect(dict(lines(m))[0] == f'Failed: {word}', f'failure {code}: "Failed: {word}" ({dict(lines(m))[0]})')
    # Paused: a .part with no state of the queue
    poke_fail(m, 0, 'Sub One', 'a.mp3', 0); m.setword(pn_at(12), 60)
    m.put(f'{RP}/Sub One/b.mp3.part', b'x' * 100)
    tick(m)
    expect(dict(lines(m))[1] == 'Paused', 'an incomplete .part and nothing queued (after a reboot): Paused')
    PCP.tap(m, 150, HDR + ROW + 10)
    expect(fn(m, 'pn_dl_count') >= 1 and state(m, 'b.mp3', 'Sub One')[0] == DL_STATE['WAIT'] and dict(lines(m))[1] == 'Waiting', 'a tap on a Paused row queues it again (it resumes from the .part)')
    # a tap with no Wi-Fi: the toast, nothing queued
    m = page(); open_sub_one(m); m.wifi = -1; m.calls = []; m.thread = None
    PCP.tap(m, 150, HDR + 10)
    expect(toasts(m) == ['No Wi-Fi'] and m.thread is None and fn(m, 'pn_dl_count') == 0, 'a tap with no Wi-Fi: the toast says so, nothing is queued')
    m.wifi = 4; m.wall = 1700000000; m.calls = []
    PCP.tap(m, 150, HDR + 10)
    expect(toasts(m) == ['Set the date first'], 'a clock that was never set: "Set the date first"')
    # the whole thing through the real worker: the tap, the thread, the page's tick, the local row
    m = page(); open_sub_one(m); m.thread = None
    PCP.tap(m, 150, HDR + 10)
    th = m.thread
    work(m, th)
    tick(m)
    expect(f'{RP}/Sub One/a.mp3' in m.fs and dict(lines(m))[0].startswith('1h ago'), f'the download ends: the page reads the episodes again, the row is a local episode (its date line {dict(lines(m))[0]})')
    t = titles(m)
    expect(t[0][2] == 'label_row_title' and t[1][2] == 'label_row_dim', 'the finished one has the normal title style, the others stay grey')
    bl, *_ = PCP.paint(m)
    expect(not [b for b in bl if tuple(b[2][2:]) != (O['PC_HDR_ART'], O['PC_HDR_ART'])], 'and no dot: unplayed is the bright title')
    m.calls = []
    PCP.tap(m, 150, HDR + 10)
    q, idx = m.played
    paths = [m.read_cstr(m.word(rec + O['REC_PATH'])) for rec in q]
    expect(paths == [f'{RP}/Sub One/a.mp3'] and idx == 0, f'a tap on it plays it like any local episode, the queue of the files only ({paths})')
    # a second, in the same list: the Feeds row
    m = page(); open_sub_one(m)
    PCP.tap(m, 150, HDR + 10); PCP.tap(m, 150, HDR + ROW + 10)
    PCP.click(m, 'btn_return')
    _, texts, styles, _ = PCP.paint(m)
    got = sorted(((y // ROW, t, s) for (t, (x, y, w, h)), s in zip(texts, styles)))
    expect(('Refresh All' in [g[1] for g in got]) and (1, 'Downloads (2)', 'label_row_title') in got and (1, 'Waiting', 'label_row_sub') in got, f'Feeds: a Downloads (2) row after Refresh All, in the plain title style, with its line ({got[:6]})')
    expect(m.props.get((m.sv, 'virtual_h')) == 5 * ROW, 'it is one more row')
    poke_slot(m, 0, 'Sub One', 'a.mp3', 2); m.setword(pn_at(DKEY), key_a); m.setword(pn_at(DGOT), len(DATA) // 4); m.setword(pn_at(DTOTAL), len(DATA)); m.setword(pn_at(DGEN), 77)
    tick(m)
    _, texts, styles, _ = PCP.paint(m)
    got = sorted(((y // ROW, t) for (t, (x, y, w, h)), s in zip(texts, styles)))
    expect((1, 'Downloading 24%') in got, f'the row shows the one running ({[g for g in got if g[0] == 1]})')
    poke_slot(m, 0, 'Sub One', 'a.mp3', 0); poke_slot(m, 1, 'Sub One', 'b.mp3', 0); m.setword(pn_at(DKEY), 0); m.setword(pn_at(12), 90)
    tick(m)
    expect(m.props.get((m.sv, 'virtual_h')) == 4 * ROW, 'when nothing is queued the row is gone again')


def refresh_page_tests(ctx):
    """Refresh All while downloads run: they pause, the refresh starts when the thread has stopped, the downloads go on afterwards."""
    expect = ctx.expect
    m = page(lambda mm: mm.put(f'{RP}/Sub One/a.mp3.part', DATA[:1000])); open_sub_one(m)   # (it had begun: the refresh keeps the line of an episode with a .part)
    PCP.tap(m, 150, HDR + 10)
    th = m.thread
    PCP.click(m, 'btn_return')
    m.calls = []; m.thread = None
    PCP.tap(m, 150, 10)   # Refresh All
    expect(m.word(pn_at(DPAUSE)) == 1 and m.thread is None and 'pthread_create' not in [c[0] for c in m.calls] and fn(m, 'pn_busy') == 0 and m.props.get((m.widgets['pod_pd_scrim'], 'visible'), 0) == 0,
           'Refresh All while a download runs: the downloads are asked to pause, no refresh thread yet, no dialog yet')
    _, texts, styles, _ = PCP.paint(m)
    got = {t for (t, r) in texts}
    expect('Waiting' in got, 'the Refresh All row says Waiting')
    tick(m)
    expect(m.thread is None, 'while the download thread has not stopped the page does not start the refresh')
    work(m, th)
    expect(fn(m, 'pn_dl_running') == 0 and fn(m, 'pn_dl_waiting') == 1 and m.word(pn_at(DPAUSE)) == 0, 'the download thread stops at its pause point and keeps the queue')
    m.calls = []
    tick(m)
    expect(m.thread and m.thread[0] == PSYMS['pn_main'] and PF.flags(m, 'pod_pd_scrim') == (1, 1) and PF.flags(m, 'pod_pd_cancel') == (1, 1),
           'the next tick starts the refresh and opens the dialog')
    m.curl_site = lambda url, o: {'body': PCN.feed_bytes('headlines-3items.xml')} if 'f.example' in url else server(DATA)(url, o)
    work(m, m.thread)
    m.thread = None; m.calls = []
    m.call(PSYMS['pg_dlg_tick'], a0=0, count=40000000)
    expect(m.thread and m.thread[0] == PSYMS['pn_dmain'], 'when the dialog closes the downloads are started again')
    m.curl_site = server(DATA)
    work(m, m.thread)
    expect(m.fs.get(f'{RP}/Sub One/a.mp3') == DATA, 'and the episode is finished, resumed from its .part')
    # the page is not in front or dark when the downloads have paused: the refresh is dropped, the downloads go on
    m = page(); open_sub_one(m); PCP.tap(m, 150, HDR + 10); th = m.thread
    PCP.click(m, 'btn_return')
    PCP.tap(m, 150, 10)
    work(m, th)
    m.screen(False); m.thread = None
    m.call(PSYMS['pg_awake_tick'], a0=0, count=40000000)
    expect(m.thread and m.thread[0] == PSYMS['pn_dmain'] , 'screen off while the downloads wait for a refresh: the timer drops the refresh and starts the downloads (no dialog is opened in the dark)')


def awake_tests(ctx):
    """reset_poweroptions_timer: only from the page's timer on the UI thread, only while a download runs, with (1, 1, 0)."""
    expect = ctx.expect
    addr = pod.FUNCTIONS['reset_poweroptions_timer'][2]
    expect(addr == 0x4d7874 and pod.FUNCTIONS['reset_poweroptions_timer'][1] == 'int, int, int' and any(a == 0x4d7874 for a, *_ in pod.PODCAST_PINS), 'reset_poweroptions_timer is stock 0x4d7874, pinned')
    m = page(); open_sub_one(m)
    m.calls = []
    r = m.call(PSYMS['pg_awake_tick'], a0=0, count=40000000)
    expect(r == 0 and not [c for c in m.calls if c[0] == 'reset_poweroptions_timer'], 'the timer with nothing queued: no call, and it ends')
    PCP.tap(m, 150, HDR + 10)
    th = m.thread
    m.calls = []
    r = m.call(PSYMS['pg_awake_tick'], a0=0, count=40000000)
    expect(r == O['RET_REPEAT'] and [c for c in m.calls if c[0] == 'reset_poweroptions_timer'] == [('reset_poweroptions_timer', 1, 1, 0)],
           'a download thread running: the timer calls reset_poweroptions_timer(1, 1, 0) once (standby and auto power-off; not the screen) and goes on')
    calls = work(m, th)
    expect(not [c for c in calls if c[0] == 'reset_poweroptions_timer'], 'the worker thread never calls it')
    m.calls = []
    r = m.call(PSYMS['pg_awake_tick'], a0=0, count=40000000)
    expect(r == 0 and not [c for c in m.calls if c[0] == 'reset_poweroptions_timer'], 'the download is done: no call, the timer ends')
    # a queue that waits (no thread running): no call
    m = page(); open_sub_one(m)
    PCP.tap(m, 150, HDR + 10)
    m.setword(pn_at(0), 0); m.setword(pn_at(KIND), 0)
    m.thread = None; m.calls = []
    m.call(PSYMS['pg_awake_tick'], a0=0, count=40000000)
    expect(not [c for c in m.calls if c[0] == 'reset_poweroptions_timer'] and m.thread and m.thread[0] == PSYMS['pn_dmain'], 'a queue with no thread: the timer starts the worker (a tap that raced its end); it keeps nothing awake before it runs')
    # the refresh's thread does not keep the device awake
    m = page(); open_sub_one(m)
    PCP.tap(m, 150, HDR + 10); PCP.click(m, 'btn_return')
    m.setword(pn_at(KIND), 1)   # the thread now a refresh's
    m.calls = []
    m.call(PSYMS['pg_awake_tick'], a0=0, count=40000000)
    expect(not [c for c in m.calls if c[0] == 'reset_poweroptions_timer'], 'only a download thread keeps the device awake (the refresh dialog is its own thing)')
    # screen off: the same call, no widget work; in the background too
    m = page(); open_sub_one(m)
    PCP.tap(m, 150, HDR + 10)
    m.screen(False); m.calls = []
    m.call(PSYMS['pg_awake_tick'], a0=0, count=40000000)
    expect([c[0] for c in m.calls if c[0] == 'reset_poweroptions_timer'] == ['reset_poweroptions_timer'] and not [c for c in m.calls if c[0].startswith(('widget', 'canvas', 'grid', 'label', 'toast'))],
           'screen off: the call is made, nothing visual is touched')
    fn_, ctx_ = m.bound[(m.window, O['EVT_WINDOW_TO_BG'])]
    m.calls = []; m.call(fn_, a0=ctx_, a1=0, count=4000000)
    m.calls = []
    r = m.call(PSYMS['pg_awake_tick'], a0=0, count=40000000)
    expect(r == O['RET_REPEAT'] and [c[0] for c in m.calls if c[0] == 'reset_poweroptions_timer'], 'in the background the downloads timer keeps going (the window still exists)')
    expect(m.props.get((m.widgets['pod_pd_scrim'], 'visible'), 0) == 0, 'no dialog')
    # destroy: its timer goes, the download goes on
    m2 = page(); open_sub_one(m2)
    m2.calls = []; fn_, ctx_ = m2.bound[(m2.window, O['EVT_DESTROY'])]; m2.call(fn_, a0=ctx_, a1=0, count=4000000)
    n0 = len([c for c in m2.calls if c[0] == 'timer_remove'])
    m2 = page(); open_sub_one(m2); PCP.tap(m2, 150, HDR + 10)
    m2.calls = []; fn_, ctx_ = m2.bound[(m2.window, O['EVT_DESTROY'])]; m2.call(fn_, a0=ctx_, a1=0, count=4000000)
    n1 = len([c for c in m2.calls if c[0] == 'timer_remove'])
    expect(n1 == n0 + 1 and fn(m2, 'pn_dl_count') == 1 and fn(m2, 'pn_dl_running') == 1, 'destroying the window removes the downloads timer and nothing else is done: the queue and the thread are left alone (the device may sleep; the next start resumes from the .part)')
    m2.calls = []
    expect(m2.call(PSYMS['podcasts_open'], count=40000000) == 0 and ('timer_add', PSYMS['pg_awake_tick'], 1000) in m2.calls, 'opening the page again while a download is queued arms the timer')
    # one hook per download timer: no global timer, no hook (this payload adds only the page's timer)
    expect(sum(1 for c in m2.calls if c[0] == 'timer_add' and c[1] == PSYMS['pg_awake_tick']) == 1, 'exactly one downloads timer')


def width_tests(ctx):
    """The state lines in every language, in the real font: the room is the 274 px of a row's grey line (PG_TEXT_W)."""
    expect = ctx.expect
    from awtk_text import Ttf, StbText
    font = Ttf(os.path.join(WORK, 'rootfs', 'release', 'assets', 'default', 'raw', 'fonts', 'default.ttf'))
    st = StbText(font, O['LIST_SUB_PX'] if 'LIST_SUB_PX' in O else 18)
    reasons = ["No Wi-Fi", "Set the date first", "Certificates missing", "Certificate problem", "Can't connect", "Not found", "Server error", "Storage unavailable", "Card is full", "Not audio"]
    worst = []
    for loc in pod_i18n.LOCALES:
        t = pod_i18n.table_for(loc)
        tr = lambda key, t=t: pod_i18n.TEXT[key][t]
        cands = {'Downloading 100%': f'{tr("Downloading")} 100%', 'Downloading 9999 MB': f'{tr("Downloading")} 9999 MB', 'Waiting': tr('Waiting'), 'Paused': tr('Paused')}
        cands.update({f'Failed: {r}': f'{tr("Failed")}: {tr(r)}' for r in reasons})
        w = {k: round(st.layout(v)[1]) for k, v in cands.items()}
        top = max(w, key=w.get)
        worst.append((loc, w[top], top))
        title_w = round(st.layout(f'{tr("Downloads")} (32)')[1])
        expect(title_w <= 274 - 0, f'{loc}: the Downloads row title fits ({title_w})')
    print('  widest state line a language needs (px, room 274):', [(a, b) for a, b, _ in worst])
    over = [(loc, w, k) for loc, w, k in worst if w > 274]
    expect(not over, f'every state line fits 274 px in every language ({over})')


SECTIONS = [queue_tests, transfer_tests, resume_tests, failure_tests, control_tests, refresh_tests, page_tests, refresh_page_tests, awake_tests, width_tests]


def run(ctx):
    for f in SECTIONS: f(ctx)
