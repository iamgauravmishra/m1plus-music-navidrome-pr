"""Network probe (patch/probe.c, docs/modules/probe.md): the Developer row, the tap (confirm, one detached worker, one run at a time, the kill switch, the card,
every way the start can fail), and the worker itself under Unicorn against a scripted libcurl and shell: the log's lines, the options of every request (verification
never switched off, the CA file, redirects, time-outs, no signals), the callbacks (the body's printable head, the MiB marks, the cut-off, the debug lines and their cap),
the Range requests of a url file, the soak and the clean-up."""
import os, re
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

DEFS = {}
for _line in open(os.path.join(ROOT, 'patch', 'probe.h')):
    _m = re.match(r'#define (\w+) ("[^"]*"|\w+)\s*(?:/\*.*)?$', _line.strip())
    if _m: DEFS[_m.group(1)] = _m.group(2).strip('"') if _m.group(2).startswith('"') else int(_m.group(2), 0)
LOG, CA, URLS = DEFS['PROBE_LOG'], DEFS['PROBE_CA'], DEFS['PROBE_URLS']
KILL = '/mnt/mmc/m1plus-off'
ASK = 'Run the network probe? It takes about 7 minutes and writes m1plus-probe.log to the card. Turn the screen off after it starts.'
CTX_SIZE = 760                       # sizeof(struct pctx): fd, t0, quiet, dbg, total (8), mark, cap, nhead, wifi_tap, head[160], tmp[300], err[256]
OFF_HEAD, OFF_NHEAD = 40, 32
MEMINFO = b'MemTotal:       61440 kB\nMemFree:         9000 kB\nMemAvailable:   25600 kB\nBuffers:          100 kB\n'
SHELL = {'date': ['Fri Oct 30 16:40:00 UTC 2026'], 'cat /proc/net/wireless': ['Inter-| sta-|   Quality', ' wlan0: 0000   60.  -50.  -256'],
         'ls -la /etc/ssl /etc/ssl/certs': ['total 0'], 'grep wlan0 /proc/net/wireless': [' wlan0: 0000   58.  -52.  -256']}
FEED = b'<?xml version="1.0"?><rss><channel><title>The big feed</title>' + b'<item><title>x</title></item>' * 100000
ITUNES = b'{\n "resultCount": 3,\n "results": [\n{"wrapperType":"track", "kind":"podcast", "feedUrl":"https://feeds.example.com/daily"}'


def site(url, opts, ca_file=True):
    """The scripted internet: what each of the probe's urls answers."""
    ca = 10065 in opts and ca_file
    if url.startswith('https://expired.'): return {'rc': 60, 'err': 'SSL certificate problem: certificate has expired', 'verify': 10}
    if url.startswith('https://') and not ca: return {'rc': 77, 'err': 'error setting certificate verify locations'}
    if 'itunes.apple.com/search' in url:
        return {'body': ITUNES, 'dbg': [(0, '  CAfile: ' + CA + '\n'), (0, 'SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384\n'), (1, 'HTTP/2 200 \r\n'), (2, 'GET / ...'),
                                        (3, 'ignored data in'), (0, 'x' * 600 + '\n')], 'total': 810000, 'dns': 12000, 'conn': 34000, 'tls': 190000, 'first': 250000}
    if url.startswith('http://neverssl.com'): return {'body': b'<html>\x00\x01\xffhello\n\tworld</html>', 'code': 200}
    if 'libsyn.com' in url: return {'body': FEED, 'redirects': 1, 'eff': 'https://feeds.libsyn.example/rss', 'total': 7000000, 'dbg': [(0, f'line {i}\n') for i in range(100)]}
    if 'simplecast' in url: return {'body': FEED * 4}                   # 11 MB: cut off at 8 MiB
    if url.startswith('https://cdn.example/'): return {'body': b'ID3' + bytes(300), 'code': 206, 'redirects': 2, 'eff': 'https://signed.example/a.mp3?sig=1'}
    return {'rc': 6}


def probe_machine(ca=True, urls=None, **kw):
    m = Machine()
    m.confirm_yes = True
    m.fs['/proc/meminfo'] = MEMINFO
    m.shell_out = {k: list(v) for k, v in SHELL.items()}
    m.curl_site = lambda url, o: site(url, o, ca)
    if ca: m.files[CA] = 224000
    if urls is not None:
        m.files[URLS] = 1; m.fs[URLS] = urls.encode()
    for k, v in kw.items(): setattr(m, k, v)
    return m


def start(m):
    """Tap the row (confirm Yes): returns the worker's (routine, argument), or None when no thread was made."""
    m.thread = None
    m.call(PSYMS['probe_start'], count=400000000)
    return m.thread


def work(m, th):
    m.call(th[0], a0=th[1], count=900000000)
    return (m.fs.get(LOG, b'')).decode('latin-1').split('\n')[:-1]


def lines(log, *needle):
    return [ln for ln in log if all(n in ln for n in needle)]


def run(ctx):
    expect = ctx.expect
    P = pod_pages

    # 1. The row and what it needs
    S = P.DEVELOPER_PAGE
    expect([r.label for r in S.rows] == ['Boot to M1+ Music', 'Open Shanling Home', 'Screenshot', 'Network Probe', 'Keyboard'] and S.rows[3].action == P.ACT_NETPROBE == 25, 'Settings > Developer has Network Probe as its fourth row, ACT_NETPROBE 25')
    expect(not [r for page in P.PAGES if page is not S for r in page.rows if r.action == P.ACT_NETPROBE], 'no other page has the row')
    rows_s = PSYMS[f'pod_rows_{P.DEVELOPER_PAGE_INDEX}']
    m = probe_machine()
    expect((m.read_cstr(m.word(rows_s + 36)), m.word(rows_s + 40)) == ('pod_row3', P.ACT_NETPROBE), 'the payload row table binds pod_row3 of the Developer page to ACT_NETPROBE')
    needed = ('curl_global_init', 'curl_easy_init', 'curl_easy_setopt', 'curl_easy_perform', 'curl_easy_getinfo', 'curl_easy_cleanup', 'curl_easy_strerror', 'pthread_create',
              'pthread_detach', 'sleep', 'popen', 'pclose', 'fgets', 'fopen', 'fclose', 'fseek', 'ftell', 'open', 'read', 'write', 'fsync', 'close', 'time', 'localtime')
    expect(all(n in pod.LIBC for n in needed) and len(pod.got_slots(DEMO, list(needed))) == len(needed), 'every call the probe makes is an import of demo, reached through its own GOT slot (no new import)')
    expect(pod.FUNCTIONS['get_wifisignal'][2] == 0x506cc8, 'get_wifisignal is the stock function at 0x506cc8')
    ui = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui')
    tree = awtk_ui.parse(open(os.path.join(ui, 'm1plus_developer.bin'), 'rb').read())
    row = tree.find('pod_row3')
    expect(row is not None and pod_i18n.shown_english(next(c for c in row.children if c.type == 'hscroll_label')) == 'Network Probe'
           and next(c for c in row.children if c.name == 'pod_icon').get('image') == 'pod_ci_globe', 'the asset row reads Network Probe with its glyph')
    expect(os.path.isfile(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/images/xx/pod_ci_globe.png')), 'the glyph is in the tree')

    # 2. The tap
    m = probe_machine()
    th = start(m)
    names = [c[0] for c in m.calls]
    expect(names.count('get_wifisignal') == 1, 'the tap reads get_wifisignal once, on the UI thread')
    expect([c[1] for c in m.calls if c[0] == 'confirm'] == [ASK] and th is not None and th[0] == PSYMS['probe_main'] and names.count('pthread_create') == 1
           and names.count('pthread_detach') == 1 and ('curl_global_init', 3) in m.calls and 'toast' not in names and 'window_open' not in names,
           'a tap asks, Yes starts one detached worker (probe_main) after curl_global_init(ALL) on the UI thread; no toast, no page')
    expect(('calloc', CTX_SIZE, th[1]) in m.calls, 'the worker gets one calloc of the context, the size the test knows')
    expect(names.index('curl_global_init') < names.index('pthread_create') < names.index('pthread_detach'), 'curl is initialised before the thread exists')
    expect(LOG not in m.fs and not [c for c in m.calls if c[0] in ('curl_easy_init', 'popen')], 'nothing is written or fetched by the tap itself')
    m.calls = []
    th2 = start(m)
    expect(th2 is None and [c[1] for c in m.calls if c[0] == 'toast'] == ['Network probe is running'] and 'confirm' not in [c[0] for c in m.calls],
           'a second tap while the worker runs only says so: no dialog, no second thread')
    work(m, th)
    m.calls = []
    th3 = start(m)
    expect(th3 is not None and 'toast' not in [c[0] for c in m.calls], 'when the worker has finished the row starts it again')

    m = probe_machine(); m.confirm_yes = False
    expect(start(m) is None and not [c for c in m.calls if c[0] in ('calloc', 'pthread_create', 'curl_global_init')], 'No in the dialog starts nothing')
    m = probe_machine(); m.present.add(KILL)
    expect(start(m) is None and not [c for c in m.calls if c[0] in ('confirm', 'toast', 'calloc', 'pthread_create')], 'the kill switch: no dialog, no toast, no thread')
    m = probe_machine(); m.card_mounted = False
    expect(start(m) is None and [c[1] for c in m.calls if c[0] == 'toast'] == ['Storage unavailable'] and 'confirm' not in [c[0] for c in m.calls],
           'no card: "Storage unavailable" before any question')
    m = probe_machine(); m.thread_ok = False
    expect(start(m) is None and [c[1] for c in m.calls if c[0] == 'toast'] == ['Network probe failed'] and ('free', m.calls[[c[0] for c in m.calls].index('calloc')][2]) in m.calls
           and 'pthread_detach' not in [c[0] for c in m.calls], 'a thread that cannot be made: the context is freed, "Network probe failed", nothing detached')
    m.thread_ok = True; m.calls = []
    expect(start(m) is not None, 'and the row works again afterwards (the running flag was cleared)')
    m = probe_machine(); m.calloc_fail = True
    expect(start(m) is None and [c[1] for c in m.calls if c[0] == 'toast'] == ['Network probe failed'] and 'pthread_create' not in [c[0] for c in m.calls],
           'no memory for the context: "Network probe failed", no thread')

    # 3. The worker, start to end
    m = probe_machine(urls='# enclosure urls\n\nshort\nhttps://cdn.example/a.mp3?x=1\r\nhttps://cdn.example/b.mp3  \n')
    m.screen(False); m.wifi = -1
    th = start(m); w0 = m.wall
    log = work(m, th)
    ctx_calls = m.calls
    expect(re.match(r'\[\d+ \+0\] =+ M1\+ Music network probe =+$', log[0]) and log[-1].endswith('probe done ================'), 'the log opens with a banner and ends with "probe done"')
    expect(all(re.match(r'\[\d+ \+\d+\] ', ln) for ln in log), 'every line carries the epoch and the seconds since the start')
    expect(lines(log, 'clock at the start: epoch 1800000000 = 2027-1-15 8:0:0 local') and lines(log, 'clock after the first requests') and lines(log, 'clock at the end'),
           'the clock is logged at the start, after the first requests and at the end (epoch and local calendar)')
    expect(lines(log, 'wifi: get_wifisignal at the tap -1 (-1 = not connected') and not [c for c in m.calls if c[0] == 'get_wifisignal'],
           'get_wifisignal is asked once, on the UI thread at the tap (logged); the worker never calls it')
    expect(lines(log, 'mem at the start: available 25600 kB, free 9000 kB') and lines(log, 'mem at the end: available 25600 kB'), 'free RAM is read from /proc/meminfo (MemAvailable and MemFree)')
    popens = [c for c in m.calls if c[0] == 'popen']
    expect([c[1] for c in popens][:3] == ['date 2>&1', 'uname -a 2>&1', 'cat /proc/net/wireless 2>&1'] and all(c[2] == 'r' for c in popens) and len([c for c in m.calls if c[0] == 'pclose']) == len(popens),
           'the shell commands run through popen (stderr folded in), each closed')
    expect(lines(log, '$ date') and lines(log, '  Fri Oct 30 16:40:00 UTC 2026') and lines(log, ' wlan0: 0000   60.  -50.  -256'), 'their output is logged under the command')
    expect(lines(log, f'CA bundle {CA}: 224000 bytes'), 'the CA bundle on the card is found and its size logged')
    reqs = [c for c in m.calls if c[0] == 'curl_perform']
    urls = [c[1] for c in reqs]
    expect(urls[:6] == ['https://itunes.apple.com/search?media=podcast&entity=podcast&limit=3&term=daily', 'https://itunes.apple.com/search?media=podcast&entity=podcast&limit=1&term=daily',
                        'https://expired.badssl.com/', 'http://neverssl.com/', 'https://allinchamathjason.libsyn.com/rss', 'https://feeds.simplecast.com/ydACIPHO']
           and urls[6:8] == ['https://cdn.example/a.mp3?x=1', 'https://cdn.example/b.mp3'] and len(urls) == 8 + DEFS['PROBE_SOAK_N'],
           'the requests in order: the iTunes search, it again without a CA file, an expired certificate, plain http, two feeds, the two urls of the file (comments, blanks and short lines skipped, line ends and trailing spaces cut), the soak')
    expect([c[2] for c in reqs[:8]] == [0, 77, 60, 0, 0, 23, 0, 0], 'the results: 0 with the CA bundle, 77 without one, 60 for the expired certificate, the second feed cut off with 23 (write error)')
    expect(lines(log, 'rc 77 (curl error 77)') and lines(log, 'error buffer: SSL certificate problem: certificate has expired') and lines(log, 'rc 60 (curl error 60) http 200 redirects 0 verify 10'),
           'the result, curl\'s message, the verify result and the error buffer are logged')
    expect(lines(log, 'ms: dns 12 connect 34 tls 190 first byte 250 total 810') and lines(log, 'url now https://feeds.libsyn.example/rss') and lines(log, 'redirects 1'), 'the phase times in ms, the final url and the redirect count are logged')
    expect(lines(log, '  . SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384') and lines(log, '  < HTTP/2 200') and lines(log, '  .   CAfile: ' + CA)
           and not lines(log, 'GET / ...') and not lines(log, 'ignored data in'), 'the verbose text and incoming header lines are logged (the TLS version and cipher among them), outgoing lines and data are not')
    expect(max(len(ln) for ln in log) < 340 and lines(log, '  . ' + 'x' * 100), 'a long line is cut to the buffer, not overrun')
    expect(len(lines(log, 'line ')) == 60, 'at most 60 verbose lines of one request are logged')
    expect(lines(log, 'body starts: {  "resultCount": 3,  "results": [ {"wrapperType"'), 'the start of the body is logged (line ends blanked)')
    expect(lines(log, 'body starts: <html>   hello  world</html>'), 'its control and high bytes are blanked to spaces')
    big = len(FEED)
    expect(len(lines(log, '  body ')) >= 3 and lines(log, '  body 1 MiB: available 25600 kB') and lines(log, f'  body {big >> 20} MiB'), 'the feed logs the free RAM at every MiB')
    expect(lines(log, f'downloaded {big} bytes ({big >> 10} kB), {(big >> 10) * 1000 // 7000} kB/s'), 'the size and the speed (kB / s from curl\'s own total time) are logged')
    cap = DEFS['PROBE_FEED_CAP']
    expect(lines(log, f'downloaded {cap + 16384} bytes ({(cap + 16384) >> 10} kB)') and cap == 8 << 20 and len(FEED * 4) > cap, 'the 11 MB feed is cut off by the write callback in the first chunk past the 8 MiB cap')
    N, S = DEFS['PROBE_SOAK_N'], DEFS['PROBE_SOAK_S']
    soak = lines(log, 'soak ', f'/{N}: epoch')
    expect(N == 10 and S == 30 and len(soak) == N and all(ln.endswith('screen dark') for ln in soak) and len(lines(log, ' wlan0: 0000   58.  -52.  -256')) == N and [c[1] for c in ctx_calls if c[0] == 'sleep'] == [S] * N and w0 + N * S <= m.wall,
           'the soak: 10 rounds, 30 s apart (5 min), each with whether the screen is lit (here dark) and the kernel\'s link line')
    expect(len(lines(log, 'soak get: rc 0 http 200 810 ms')) == N and not [ln for ln in log if '  . ' in ln and log.index(ln) > log.index(soak[0])], 'a soak request logs one summary line and none of the verbose ones')
    expect(len([c for c in popens if 'power_supply' in c[1]]) == 1 + N // 5, 'the battery is read once at the start and every fifth round of the soak')
    inits = [c for c in m.calls if c[0] == 'curl_easy_init']
    cleans = [c for c in m.calls if c[0] == 'curl_easy_cleanup']
    expect(len(inits) == len(cleans) == len(reqs), 'every easy handle is cleaned up')

    # 3b. The options of the requests: what the feature must not lose
    seen = []
    m2 = probe_machine(urls='https://cdn.example/a.mp3\n')
    orig = m2.curl_perform
    def spy(h):
        seen.append(dict(m2.curl[h])); return orig(h)
    m2.curl_perform = spy
    work(m2, start(m2))
    expect(len(seen) == 7 + DEFS['PROBE_SOAK_N'], 'the spy saw every request')
    expect(not [o for o in seen if 64 in o or 81 in o], 'certificate checks are never switched off (no SSL_VERIFYPEER or SSL_VERIFYHOST option is set)')
    expect([10065 in o for o in seen[:3]] == [True, False, True] and all(o[10065] == CA for o in seen if 10065 in o), 'CAINFO is the card\'s bundle; only the "no CA file" request has none')
    expect(all(o[52] == 1 and o[68] == 8 and o[99] == 1 and o[78] == 20 and o[19] == 1000 and o[20] == 30 and o[41] == 1 and o[43] == 1 for o in seen),
           'every request follows redirects (at most 8), sets NOSIGNAL, a connect time-out, a low-speed limit and time, verbose and no progress meter')
    expect(all(o[13] == (300 if o[10002].endswith(('/rss', 'ydACIPHO')) else 60) for o in seen) and seen[0][10018].startswith('M1PlusMusic'), 'the total time-out is 300 s for a feed and 60 s otherwise; a User-Agent is sent')
    expect([10102 in o for o in seen[:7]] == [True] * 6 + [False] and [10007 in o for o in seen[:7]] == [False] * 6 + [True] and seen[6][10007] == DEFS['PROBE_RANGE'],
           'feeds accept every encoding; the url of the file is a Range request and takes no encoding')

    # 4. Missing pieces
    m = probe_machine(ca=False)
    log = work(m, start(m))
    expect(lines(log, f'CA bundle {CA}: MISSING') and lines(log, f'no {URLS}') and lines(log, 'probe done'), 'no CA bundle and no url file: said in the log, the run goes on')
    expect(lines(log, 'rc 77') and len(lines(log, 'rc 77')) >= 5, 'every https request then fails with 77 (the log shows why)')
    m = probe_machine(); m.fail.add(('open', LOG))
    th = start(m); m.calls = []
    work(m, th)
    expect(not [c for c in m.calls if c[0] in ('curl_easy_init', 'popen', 'sleep')] and ('free', th[1]) in m.calls, 'a log that cannot be opened ends the worker at once, nothing run, the context freed')
    m.calls = []
    expect(start(m) is not None, 'and the row works again')
    m = probe_machine(); m.shell_out = {}
    log = work(m, start(m))
    expect(lines(log, '$ date') and lines(log, 'probe done'), 'a command with no output is just a header')
    expect(len([w for w in m.calls if w[0] == 'write']) == len([w for w in m.calls if w[0] == 'fsync']) and ('close', LOG) in m.calls, 'every log line is fsynced; the log is closed at the end')

    # 5. The callbacks on their own
    m = probe_machine()
    th = start(m)
    c = th[1]
    buf = m.alloc(4096)
    m.u.mem_write(c, bytes(CTX_SIZE)); m.setword(c + 28, 1 << 30); m.setword(c + 24, 1 << 30)          # cap, mark (no memory line)
    m.u.mem_write(buf, b'Hello\x00\x1fWorld' + b'z' * 400)
    n = m.call(PSYMS['wr_cb'], a0=buf, a1=1, a2=411, a3=c, count=2000000)
    head = bytes(m.u.mem_read(c + OFF_HEAD, 160)).split(b'\0')[0]
    expect(n == 411 and head == b'Hello  World' + b'z' * 147 and m.word(c + OFF_NHEAD) == 159, 'the write callback keeps the first 159 printable bytes (others blanked), returns the length')
    m.setword(c + 16, 0); m.setword(c + 20, 0); m.setword(c + 28, 100); m.setword(c + 24, 1 << 30)
    expect(m.call(PSYMS['wr_cb'], a0=buf, a1=1, a2=101, a3=c, count=2000000) == 0, 'past the cap the callback returns 0 (libcurl stops with a write error)')
    m.setword(c + 28, 1 << 30)
    expect(m.call(PSYMS['wr_cb'], a0=buf, a1=4, a2=10, a3=c, count=2000000) == 40, 'size * nmemb is the length')
