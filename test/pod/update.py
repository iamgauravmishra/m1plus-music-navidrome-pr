"""Software Update, the worker side (patch/upver.c, patch/pcnet.c "Software Update", docs/modules/update.md): the strict version parse and the numeric comparison (tables), what a release tag means for a
release build and a development build, the redirect that names the latest release (the exact address of the configured repository, nothing else), the check's request (header only, not followed, https only),
the build's own version and repository (the compiler's, equal to tools/build.py), the downloaded package's first lines (a real tar, every way to be another version), and the download job against a
scripted libcurl: the tag's own address (never "latest"), the file only appearing by rename after the checks, every failure deleting the .part and keeping the old update.bin, Cancel, the space and Wi-Fi
guards, one worker at a time."""
import io, json, os, sys, tarfile
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import build
from harness import sibling

PCS = sibling('pcsearch')
PCN, fn, work = PCS.PCN, PCS.fn, PCS.PCN.work
PN = dict(PCN.PN, CANCELLED=12, CARDFULL=13, NOFEED=17, NOLYRICS=18, OVERLOAD=19, UPCHECK=20, UPBAD=21)
U = dict(IDLE=0, CHECKING=1, CHECKED=2, DOWNLOADING=3, DOWNLOADED=4, FAILED=5)
REPO = build.REPO
LATEST = f'https://github.com/{REPO}/releases/latest'
TAGURL = f'https://github.com/{REPO}/releases/tag/'
DOWNLOAD = f'https://github.com/{REPO}/releases/download/'
FILE, PART, CARD = '/mnt/mmc/update.bin', '/mnt/mmc/update.bin.part', '/mnt/mmc'
OLD = b'the update.bin of an earlier download'


def cs(s): return s.encode() + b'\0'


def parse(m, s):
    out = m.alloc(16)
    r = fn(m, 'up_parse', m.cstr(s), out)
    return (r, tuple(m.word(out + 4 * i) for i in range(3))) if r else (0, None)


def offer(m, tag, own, dev=0): return fn(m, 'up_offer', m.cstr(tag), m.cstr(own), dev)


def redirect(m, loc, repo=REPO):
    out = m.alloc(24)
    r = fn(m, 'up_redirect_tag', m.cstr(loc), m.cstr(repo), out, 24)
    return m.read_cstr(out) if r else None


def package(tag='1.0.1', model='Shanling M1 Plus', line2=None, info=None, members=True, extra=b'\0' * 2048):
    """A package as tools/fwtool.py repack writes it (a GNU tar: firmware_v20.info first, then the directory and the two files), with the info lines the keywords choose."""
    if info is None: info = f'{model}\n{line2 if line2 is not None else "V2.1-" + tag}\n' + 'a' * 32 + '  recovery-update/xImage\n' + 'b' * 32 + '  recovery-update/rootfs.squashfs\n'
    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode='w', format=tarfile.GNU_FORMAT) as t:
        ti = tarfile.TarInfo('firmware_v20.info'); ti.size = len(info.encode()); t.addfile(ti, io.BytesIO(info.encode()))
        if members:
            d = tarfile.TarInfo('recovery-update'); d.type = tarfile.DIRTYPE; t.addfile(d)
            for n in ('xImage', 'rootfs.squashfs'):
                f = tarfile.TarInfo('recovery-update/' + n); f.size = len(extra); t.addfile(f, io.BytesIO(extra))
    return b.getvalue()


def info_ok(m, data, tag='1.0.1'):
    m.fs['/mnt/mmc/p.tar'] = data
    return fn(m, 'up_info_ok', m.cstr('/mnt/mmc/p.tar'), m.cstr(tag))


def parse_tests(ctx):
    expect, m = ctx.expect, Machine()
    good = {'0.0.0': (0, 0, 0), '1.0.0': (1, 0, 0), '1.0.1': (1, 0, 1), '1.10.0': (1, 10, 0), '99999.99999.99999': (99999, 99999, 99999), '01.002.0003': (1, 2, 3), '0.0.00000': (0, 0, 0)}
    for s, want in good.items():
        r, v = parse(m, s)
        expect(r == 1 and v == want, f'{s!r} is a version: {want}')
    bad = ['', '1', '1.0', '1.0.', '.1.0', '1..0', '1.0.0.0', '1.0.0.', 'v1.0.0', 'V1.0.0', '1.0.0-rc1', '1.0.0+1', '1.0.0\r', '1.0.0\n', '1.0.0 ', ' 1.0.0', '1.0.0?x=1', '1.0.0#a', '1.0.0/', '100000.0.0', '1.100000.0',
           '1.0.100000', '123456789012345678901234567890.0.0', '-1.0.0', '+1.0.0', '1.-0.0', '1,0,0', '1.0.a', 'a.b.c', '１.0.0', '1.0.0\0x'.split('\0')[0] + 'x', '1.0.0 ', '0x1.0.0', '1 .0.0', '1.0.0.0.0']
    for s in bad:
        expect(parse(m, s)[0] == 0, f'{s!r} is not a version')
    expect(fn(m, 'up_parse', 0, m.alloc(16)) == 0, 'no string, no version')
    # the comparison, through up_offer (a release build: the tag is offered only when strictly newer)
    table = [('1.0.1', '1.0.0', 2), ('1.0.0', '1.0.0', 1), ('1.0.0', '1.0.1', 1), ('1.10.0', '1.9.9', 2), ('1.9.9', '1.10.0', 1), ('2.0.0', '1.99.99', 2), ('1.99.99', '2.0.0', 1), ('1.0.10', '1.0.9', 2),
             ('1.0.9', '1.0.10', 1), ('0.9.0', '1.0.0', 1), ('10.0.0', '9.99999.99999', 2), ('1.0.1', '1.0.1', 1), ('01.0.1', '1.0.1', 1), ('1.00.2', '1.0.1', 2), ('99999.99999.99999', '99999.99999.99998', 2),
             ('1.0.0', '2.0.0', 1), ('3.0.0', '2.9.9', 2)]
    for tag, own, want in table:
        expect(offer(m, tag, own) == want, f'a release build {own}, release {tag}: {"offered" if want == 2 else "up to date"}')
    for tag in ('v1.0.1', '1.0', '1.0.0.0', '1.0.0-rc1', '', '1.0.1\r', '1.0.1 ', '1.0.1\n', '100000.0.0', 'latest'):
        expect(offer(m, tag, '1.0.0') == 0, f'{tag!r} is no version: nothing is offered (never newer)')
        expect(offer(m, tag, '', 1) == 0 and offer(m, tag, 'V2.1zABCDEFGH', 1) == 0, f'{tag!r} is not offered to a development build either')
    expect(offer(m, '1.0.1', 'garbage') == 0 and offer(m, '1.0.1', '') == 0, 'a build whose own version does not parse is offered nothing')
    for tag in ('0.0.1', '1.0.0', '1.0.1', '9.9.9', '0.0.0'):
        expect(offer(m, tag, '1.0.0', 1) == 2, f'a development build is offered any valid release ({tag}), whatever its number')


def redirect_tests(ctx):
    expect, m = ctx.expect, Machine()
    good = {TAGURL + '1.0.1': '1.0.1', TAGURL + '12.345.67890': '12.345.67890', TAGURL + '0.0.0': '0.0.0'}
    for loc, want in good.items(): expect(redirect(m, loc) == want, f'{loc}: tag {want}')
    bad = [TAGURL + 'v1.0.1', TAGURL + '1.0', TAGURL + '1.0.0.0', TAGURL + '1.0.1-rc1', TAGURL + '1.0.1\r', TAGURL + '1.0.1 ', TAGURL + '1.0.1?x=1', TAGURL + '1.0.1#a', TAGURL + '1.0.1/', TAGURL + '1.0.1/x',
           TAGURL, TAGURL.rstrip('/'), TAGURL + '100000.0.0', 'http://github.com/' + REPO + '/releases/tag/1.0.1', f'https://www.github.com/{REPO}/releases/tag/1.0.1', f'https://github.com.evil.example/{REPO}/releases/tag/1.0.1',
           f'https://evil.example/github.com/{REPO}/releases/tag/1.0.1', 'https://github.com/other/repo/releases/tag/1.0.1', f'https://github.com/{REPO}x/releases/tag/1.0.1', f'https://github.com/{REPO[:-1]}/releases/tag/1.0.1',
           f'https://github.com/{REPO.upper()}/releases/tag/1.0.1', f'https://github.com/{REPO}/releases/download/1.0.1/update.bin', f'https://github.com/{REPO}/releases/latest', f'https://github.com/{REPO}/releases',
           f'https://github.com/{REPO}/tag/1.0.1', f'/{REPO}/releases/tag/1.0.1', f'https://github.com/{REPO}//releases/tag/1.0.1', f'https://github.com/{REPO}/releases/tag/../1.0.1', '', 'https://github.com/', 'releases/tag/1.0.1']
    for loc in bad: expect(redirect(m, loc) is None, f'{loc!r}: not the redirect to a release of {REPO}')
    expect(redirect(m, TAGURL + '1.0.1', 'other/repo') is None and redirect(m, 'https://github.com/other/repo/releases/tag/1.0.1', 'other/repo') == '1.0.1', 'the repository is the configured one, nothing else')
    expect(fn(m, 'up_redirect_tag', 0, m.cstr(REPO), m.alloc(24), 24) == 0 and fn(m, 'up_redirect_tag', m.cstr(TAGURL + '1.0.1'), m.cstr(REPO), m.alloc(24), 5) == 0, 'no address, or a buffer too small for any tag')


def build_tests(ctx):
    """The payload's own version, development flag and repository are the compiler's, from tools/build.py."""
    expect, m = ctx.expect, Machine()
    own = m.read_cstr(PSYMS['up_own'])
    expect(own == build.VERSION and parse(m, own)[0] == 1, f'the payload\'s version {own!r} is tools/build.py VERSION {build.VERSION!r} and parses')
    expect(m.read_cstr(PSYMS['up_repo']) == build.REPO, f'the payload\'s repository is tools/build.py REPO {build.REPO!r}')
    tag = json.load(open(os.path.join(WORK, 'build.json')))['tag']
    expect(m.word(PSYMS['up_dev']) == int(build.about(tag) != build.VERSION), f'the development flag follows the build tag ({tag})')
    expect(('V2.1-' + own) == build.TAG or m.word(PSYMS['up_dev']) == 1, 'a release build\'s package tag is V2.1-<version>')


def info_tests(ctx):
    expect, m = ctx.expect, Machine()
    expect(info_ok(m, package('1.0.1')) == 1, 'a package made as tools/fwtool.py does: model and V2.1-<tag> on the first two lines')
    expect(info_ok(m, package('1.10.0'), '1.10.0') == 1 and info_ok(m, package('1.10.0'), '1.1.0') == 0, 'the tag is compared as text, whole')
    expect(info_ok(m, package('1.0.1', members=False)) == 1, 'only the first member is read')
    expect(info_ok(m, package('1.0.0')) == 0, 'the package of another version: refused')
    expect(info_ok(m, package('1.0.1', line2='V2.1-1.0.10')) == 0 and info_ok(m, package('1.0.10', line2='V2.1-1.0.1'), '1.0.10') == 0, 'a longer or shorter tag is another version')
    expect(info_ok(m, package('1.0.1', line2='V2.1')) == 0 and info_ok(m, package('1.0.1', line2='V2.1zABCDEFGH')) == 0, 'the stock version or a development tag: refused')
    expect(info_ok(m, package('1.0.1', line2='V2.1-1.0.1 ')) == 0 and info_ok(m, package('1.0.1', line2='V2.1-1.0.1\r')) == 0 and info_ok(m, package('1.0.1', line2='v2.1-1.0.1')) == 0, 'trailing space or CR, a lower case v: refused')
    expect(info_ok(m, package('1.0.1', model='Shanling M1')) == 0 and info_ok(m, package('1.0.1', model='Shanling Q2')) == 0 and info_ok(m, package('1.0.1', model='shanling m1 plus')) == 0 and info_ok(m, package('1.0.1', model='Shanling M1 Plus ')) == 0, 'another model: refused')
    expect(info_ok(m, package('1.0.1', info='Shanling M1 Plus\n')) == 0, 'the second line missing: refused')
    expect(info_ok(m, package('1.0.1', info='Shanling M1 Plus\nV2.1-1.0.1')) == 0, 'the second line not ended by a line feed: refused')
    expect(info_ok(m, package('1.0.1', info='V2.1-1.0.1\nShanling M1 Plus\n')) == 0, 'the lines in the wrong order: refused')
    expect(info_ok(m, package('1.0.1', info='')) == 0, 'an empty info file: refused')
    expect(info_ok(m, package('1.0.1', info='Shanling M1 Plus\r\nV2.1-1.0.1\r\n')) == 0, 'CRLF lines: refused')
    p = package('1.0.1')
    expect(info_ok(m, b'') == 0 and info_ok(m, p[:511]) == 0 and info_ok(m, p[:512]) == 0 and info_ok(m, p[:513]) == 0, 'a file cut inside the header or the info: refused')
    expect(info_ok(m, bytes(2048)) == 0 and info_ok(m, b'not a tar file ' * 100) == 0, 'zeros or text: refused')
    bad = bytearray(p); bad[0:17] = b'firmware_v20.inf0'
    expect(info_ok(m, bytes(bad)) == 0, 'another member name (and a checksum that no longer fits): refused')
    bad = bytearray(p); bad[1] ^= 0x20
    expect(info_ok(m, bytes(bad)) == 0, 'a header whose checksum is wrong: refused')
    bad = bytearray(p); bad[512] ^= 1
    expect(info_ok(m, bytes(bad)) == 0, 'a changed info line (line 1): refused')
    b2 = io.BytesIO()
    with tarfile.open(fileobj=b2, mode='w', format=tarfile.GNU_FORMAT) as t:
        d = tarfile.TarInfo('recovery-update'); d.type = tarfile.DIRTYPE; t.addfile(d)
        ti = tarfile.TarInfo('firmware_v20.info'); ti.size = 40; t.addfile(ti, io.BytesIO(b'Shanling M1 Plus\nV2.1-1.0.1\n'.ljust(40)))
    expect(info_ok(m, b2.getvalue()) == 0, 'the info file not the first member: refused')
    b3 = io.BytesIO()
    with tarfile.open(fileobj=b3, mode='w', format=tarfile.GNU_FORMAT) as t:
        ti = tarfile.TarInfo('./firmware_v20.info'); ti.size = 30; t.addfile(ti, io.BytesIO(b'Shanling M1 Plus\nV2.1-1.0.1\n'.ljust(30)))
    expect(info_ok(m, b3.getvalue()) == 0, 'a "./" in the name: refused (the tools write the bare name)')
    b4 = io.BytesIO()
    with tarfile.open(fileobj=b4, mode='w', format=tarfile.GNU_FORMAT) as t:
        ti = tarfile.TarInfo('firmware_v20.info'); ti.type = tarfile.SYMTYPE; ti.linkname = 'x'; t.addfile(ti)
    expect(info_ok(m, b4.getvalue()) == 0, 'a link, not a file: refused')
    expect(fn(m, 'up_info_ok', m.cstr('/mnt/mmc/none.tar'), m.cstr('1.0.1')) == 0 and fn(m, 'up_info_ok', m.cstr('/mnt/mmc/p.tar'), m.cstr('v1.0.1')) == 0, 'no file, or a tag that is no version: refused')


# ---- the jobs against a scripted libcurl
class Site:
    """The scripted GitHub: /releases/latest answers with `latest` (a dict for the harness), the tag's asset with `asset`; every request is written down."""
    def __init__(self, tag='1.0.1', pkg=None, latest=None, asset=None):
        self.reqs, self.pkg = [], pkg if pkg is not None else package(tag)
        self.latest = latest if latest is not None else {'code': 302, 'redirect_url': TAGURL + tag, 'body': b''}
        self.asset = asset or {}

    def __call__(self, url, o):
        self.reqs.append((url, dict(o)))
        if url == LATEST: return dict(self.latest)
        return {'body': self.pkg, 'chunk': 1000, 'length': len(self.pkg), **self.asset}


def machine(site, own=None, dev=None):
    m = PCS.machine(site=site)
    m.put(FILE, OLD)
    if own is not None: m.u.mem_write(PSYMS['up_own'], cs(own))
    if dev is not None: m.setword(PSYMS['up_dev'], dev)
    return m


def st(m): return fn(m, 'pn_up_state'), fn(m, 'pn_up_code'), fn(m, 'pn_up_stage'), fn(m, 'pn_up_result'), m.read_cstr(fn(m, 'pn_up_tag'))


def check(m):
    m.thread = None
    r = fn(m, 'pn_up_check')
    if r == 0:
        assert m.thread and m.thread[0] == PSYMS['pn_umain'], 'one worker thread'
        work(m, m.thread)
    return r


def download(m):
    m.thread = None
    r = fn(m, 'pn_up_download')
    if r == 0:
        assert m.thread and m.thread[0] == PSYMS['pn_umain']
        work(m, m.thread)
    return r


def put_fs(m, p): return m.fs.get(p)


def check_tests(ctx):
    expect = ctx.expect
    site = Site('1.0.1')
    m = machine(site, own='1.0.0', dev=0)
    expect(st(m) == (U['IDLE'], 0, 0, 0, ''), 'nothing checked: idle')
    m.thread = None
    r = fn(m, 'pn_up_check')
    calls = list(m.calls)
    expect(r == 0 and st(m)[0] == U['CHECKING'] and fn(m, 'pn_job_busy') == 1 and fn(m, 'pn_busy') == 0 and ('curl_global_init', 3) in calls and [c[0] for c in calls].count('pthread_create') == 1 and 'pthread_detach' in [c[0] for c in calls],
           'a check starts one detached worker')
    expect(fn(m, 'pn_up_check') == PN['BUSY'] and fn(m, 'pn_up_download') == PN['BUSY'] and fn(m, 'pn_search', m.cstr('x')) == PN['BUSY'] and fn(m, 'pn_dl_start') == 0, 'one worker at a time: the second job is PN_BUSY')
    work(m, m.thread)
    expect(st(m) == (U['CHECKED'], 0, 1, 2, '1.0.1') and fn(m, 'pn_job_busy') == 0, f'1.0.0 and the latest release 1.0.1: offered ({st(m)})')
    expect(len(site.reqs) == 1 and site.reqs[0][0] == LATEST, f'one request, to {LATEST}')
    o = site.reqs[0][1]
    expect(o[44] == 1 and o[52] == 0 and o[45] == 1 and o[181] == 2 and o[182] == 2 and o[10065] == PCN.CA and o[10018].startswith('M1PlusMusic/') and 64 not in o and 81 not in o,
           'header only, the redirect not followed, https only, the firmware CA bundle, verification never switched off')
    expect(o[10102] == '' and o[78] == 20 and o[19] == 1000 and o[20] == 30, 'the same time-outs as every request')
    # the other verdicts
    for own, tag, want in (('1.0.1', '1.0.1', 1), ('1.0.2', '1.0.1', 1), ('1.9.9', '1.10.0', 2), ('1.0.0', '1.0.0', 1)):
        m = machine(Site(tag), own=own, dev=0); check(m)
        s = st(m)
        expect(s[0] == U['CHECKED'] and s[3] == want and s[4] == (tag if want == 2 else ''), f'build {own}, release {tag}: {"offered" if want == 2 else "Up to date"} ({s})')
    # answers that are not "the redirect to a release of this repository"
    ok = TAGURL + '1.0.1'
    cases = [('200 without a Location', {'code': 200}), ('200 with a body', {'code': 200, 'body': b'<html>'}), ('302 without a Location', {'code': 302}), ('404', {'code': 404, 'rc': 22}), ('500', {'code': 500, 'rc': 22}),
             ('503', {'code': 503, 'rc': 22}), ('200 with a Location', {'code': 200, 'redirect_url': ok}), ('304', {'code': 304, 'redirect_url': ok}),
             ('another host', {'code': 302, 'redirect_url': f'https://evil.example/{REPO}/releases/tag/1.0.1'}), ('another repo', {'code': 302, 'redirect_url': 'https://github.com/other/repo/releases/tag/1.0.1'}),
             ('http', {'code': 302, 'redirect_url': 'http://github.com/' + REPO + '/releases/tag/1.0.1'}), ('releases/download', {'code': 302, 'redirect_url': f'https://github.com/{REPO}/releases/download/1.0.1/update.bin'}),
             ('v1.0.1', {'code': 302, 'redirect_url': TAGURL + 'v1.0.1'}), ('1.0', {'code': 302, 'redirect_url': TAGURL + '1.0'}), ('1.0.0.0', {'code': 302, 'redirect_url': TAGURL + '1.0.0.0'}),
             ('1.0.1-rc1', {'code': 302, 'redirect_url': TAGURL + '1.0.1-rc1'}), ('a CR', {'code': 302, 'redirect_url': ok + '\r'}), ('a query', {'code': 302, 'redirect_url': ok + '?a=1'}), ('a fragment', {'code': 302, 'redirect_url': ok + '#a'}),
             ('empty tag', {'code': 302, 'redirect_url': TAGURL}), ('huge number', {'code': 302, 'redirect_url': TAGURL + '100000.0.0'})]
    for what, ans in cases:
        m = machine(Site(latest=ans), own='1.0.0', dev=0); check(m)
        s = st(m)
        expect(s[0] == U['FAILED'] and s[1] == PN['UPCHECK'] and s[2] == 1 and s[3] == 0 and s[4] == '' and fn(m, 'pn_job_busy') == 0, f'{what}: "can\'t check", nothing offered, never "up to date" ({s})')
        expect(fn(m, 'pn_up_download') == PN['UPCHECK'] and not [c for c in m.calls if c[0] == 'open' and c[1] == PART], f'{what}: nothing can be downloaded after it')
    for code in (301, 302, 303, 307, 308):
        m = machine(Site(latest={'code': code, 'redirect_url': ok}), own='1.0.0', dev=0); check(m)
        expect(st(m)[0] == U['CHECKED'] and st(m)[3] == 2, f'a {code} redirect is read the same')
    # network failures
    for rc, want, why in ((6, PN['NET'], 'no DNS'), (28, PN['NET'], 'a time-out'), (7, PN['NET'], 'refused'), (60, PN['CERT'], 'the certificate'), (51, PN['CERT'], 'the host name'), (77, PN['NOCERT'], 'the CA file'),
                          (56, PN['NET'], 'a reset')):
        m = machine(Site(latest={'rc': rc, 'code': 0}), own='1.0.0', dev=0); check(m)
        expect(st(m)[:3] == (U['FAILED'], want, 1), f'curl {rc} ({why}): PN {want} ({st(m)})')
    # the guards
    m = machine(Site(), own='1.0.0', dev=0); m.wifi = -1
    expect(check(m) == PN['NOWIFI'] and st(m)[:3] == (U['FAILED'], PN['NOWIFI'], 1) and not m.thread and not site_calls(m), 'no Wi-Fi: PN_NOWIFI, the state says so, no thread, no request')
    m = machine(Site(), own='1.0.0', dev=0); m.wall = 1700000000
    expect(check(m) == PN['NOCLOCK'] and st(m)[1] == PN['NOCLOCK'], 'a clock never set: PN_NOCLOCK')
    m = machine(Site(), own='1.0.0', dev=0); m.present.discard(PCN.CA)
    expect(check(m) == PN['NOCERT'] and st(m)[1] == PN['NOCERT'], 'no CA bundle: PN_NOCERT')
    m = machine(Site(), own='1.0.0', dev=0); m.card_mounted = False
    expect(check(m) == PN['STORAGE'], 'no card: PN_STORAGE')
    m = machine(Site(), own='1.0.0', dev=0); m.thread_ok = False
    expect(check(m) == PN['MEM'] and st(m)[:3] == (U['FAILED'], PN['MEM'], 1) and fn(m, 'pn_job_busy') == 0, 'no thread: PN_MEM, the slot is free')
    # Cancel: a running check forgets itself
    site = Site()
    site.latest = {'code': 302, 'redirect_url': TAGURL + '1.0.1', 'xfer': lambda url, sent, total: m.nested(PSYMS['pn_cancel'])}
    m = machine(site, own='1.0.0', dev=0); check(m)
    expect(st(m)[:2] == (U['IDLE'], PN['CANCELLED']) and st(m)[3] == 0 and fn(m, 'pn_job_busy') == 0, f'Cancel during a check: back to idle, nothing offered ({st(m)})')
    # a new check forgets an earlier offer; a failed one keeps none
    m = machine(Site(), own='1.0.0', dev=0); check(m)
    s2 = Site(latest={'code': 404, 'rc': 22}); m.curl_site = s2; check(m)
    expect(st(m)[0] == U['FAILED'] and st(m)[3] == 0 and st(m)[4] == '' and fn(m, 'pn_up_download') == PN['UPCHECK'], 'a failed second check leaves no offer from the first')
    m.curl_site = Site('1.0.2'); check(m)
    expect(st(m)[4] == '1.0.2', 'and a third check offers what it found')
    # reset
    fn(m, 'pn_up_reset')
    expect(st(m) == (U['IDLE'], 0, 1, 0, ''), 'pn_up_reset forgets an old answer')


def site_calls(m): return [c for c in m.calls if c[0] in ('curl_easy_init', 'curl_perform')]


def dev_tests(ctx):
    """A development build has no version to compare: the latest release is always offered, and every other check still applies."""
    expect = ctx.expect
    for tag in ('1.0.0', '0.0.1', '1.0.1', '9.9.9'):
        site = Site(tag)
        m = machine(site, own='1.0.0', dev=1); check(m)
        expect(st(m) == (U['CHECKED'], 0, 1, 2, tag), f'a development build is offered release {tag} ({st(m)})')
        expect(download(m) == 0 and st(m)[:2] == (U['DOWNLOADED'], 0) and m.fs.get(FILE) == site.pkg and PART not in m.fs, f'and it downloads {tag}: update.bin is that package')
        expect(site.reqs[1][0] == DOWNLOAD + tag + '/update.bin', 'from the tag\'s own address')
    # all the checks still apply
    for what, ans in (('a 200', {'code': 200}), ('another repo', {'code': 302, 'redirect_url': 'https://github.com/other/repo/releases/tag/1.0.0'}), ('v1.0.0', {'code': 302, 'redirect_url': TAGURL + 'v1.0.0'}),
                      ('1.0.0-rc1', {'code': 302, 'redirect_url': TAGURL + '1.0.0-rc1'}), ('a CR', {'code': 302, 'redirect_url': TAGURL + '1.0.0\r'}), ('1.0', {'code': 302, 'redirect_url': TAGURL + '1.0'})):
        m = machine(Site(latest=ans), own='1.0.0', dev=1); check(m)
        expect(st(m)[:2] == (U['FAILED'], PN['UPCHECK']) and st(m)[3] == 0, f'a development build: {what} is "can\'t check", nothing offered')
    m = machine(Site('1.0.0', pkg=package('1.0.0', line2='V2.1-1.0.1')), own='1.0.0', dev=1); check(m)
    expect(download(m) == 0 and st(m)[:2] == (U['FAILED'], PN['UPBAD']) and m.fs.get(FILE) == OLD and PART not in m.fs, 'a development build: a package of another version is refused, the old update.bin stays')
    m = machine(Site('1.0.0', pkg=package('1.0.0', model='Shanling Q2')), own='1.0.0', dev=1); check(m)
    expect(download(m) == 0 and st(m)[1] == PN['UPBAD'] and m.fs.get(FILE) == OLD and PART not in m.fs, 'a development build: another model is refused')
    m = machine(Site('1.0.0', asset={'length': 99999999}), own='1.0.0', dev=1); check(m)
    expect(download(m) == 0 and st(m)[1] == PN['UPBAD'] and m.fs.get(FILE) == OLD and PART not in m.fs, 'a development build: a length that is not what arrived is refused')
    m = machine(Site('1.0.0'), own='1.0.0', dev=1); m.free_mb = 109; check(m)
    expect(download(m) == PN['CARDFULL'] and m.fs.get(FILE) == OLD, 'a development build: the space check applies')


def download_tests(ctx):
    expect = ctx.expect
    pkg = package('1.0.1', extra=bytes(range(256)) * 30)
    site = Site('1.0.1', pkg=pkg)
    seen = {}
    pcts = []

    def probe(url, sent, total):
        if url != LATEST and 'first' not in seen:
            seen['first'] = (m.fs.get(FILE), PART in m.fs)
        if url != LATEST: pcts.append(m.nested(PSYMS['pn_up_pct']))
    site.asset = {'xfer': probe}
    m = machine(site, own='1.0.0', dev=0)
    m.put(PART, b'half of an earlier try')
    expect(download(m) == PN['UPCHECK'], 'no release offered yet: nothing to download')
    check(m)
    m.calls = []; m.thread = None
    r = fn(m, 'pn_up_download')
    expect(r == 0 and st(m)[:3] == (U['DOWNLOADING'], 0, 2) and fn(m, 'pn_up_pct') == 0, 'the download starts: state 3, 0 %')
    work(m, m.thread)
    wcalls = list(m.calls)
    s = st(m)
    expect(s == (U['DOWNLOADED'], 0, 2, 2, '1.0.1') and fn(m, 'pn_job_busy') == 0, f'done: downloaded ({s})')
    url, o = site.reqs[-1]
    expect(url == DOWNLOAD + '1.0.1/update.bin' and 'latest' not in url, f'the tag\'s own address, never latest: {url}')
    expect(o[52] == 1 and o[45] == 1 and o[181] == 2 and o[182] == 2 and o[10065] == PCN.CA and o[13] == 0 and o[10102] is None and o[19] == 1000 and o[20] == 30 and 64 not in o and 81 not in o,
           'redirects followed, https only, verification on, no limit on the whole transfer, the low-speed limit kept, no content encoding')
    expect(m.fs.get(FILE) == pkg and PART not in m.fs, 'update.bin is the package whole and there is no .part')
    expect(seen['first'] == (OLD, True), 'while the package arrived, update.bin was still the old one and the .part existed')
    calls = [c for c in wcalls if c[0] in ('open', 'write', 'fsync', 'close', 'rename', 'unlink')]
    names = [c[0] for c in calls]
    i_rename, i_dir = names.index('rename'), [k for k, c in enumerate(calls) if c[0] == 'open' and c[1] == CARD][0]
    fs_part = [k for k, c in enumerate(calls) if c[0] == 'fsync' and c[1] == PART]
    expect(calls[names.index('unlink')][1] == PART and fs_part and fs_part[0] < i_rename < i_dir and calls[i_rename][1:] == (PART, FILE) and calls[i_dir + 1] == ('fsync', CARD),
           'the old .part removed; the .part fsynced, renamed over update.bin, then the card\'s root directory fsynced')
    expect(len([c for c in calls if c[0] == 'rename']) == 1, 'one rename')
    expect(pcts and pcts == sorted(pcts) and pcts[-1] >= 90 and fn(m, 'pn_up_pct') >= 99, f'the progress moves up to the end ({pcts[:3]}...{pcts[-2:]})')
    # a package of another version, in every way
    pkg_ok = package('1.0.1')
    cases = [('an older version', package('1.0.0')), ('the stock version', package('1.0.1', line2='V2.1')), ('a development tag', package('1.0.1', line2='V2.1zABCDEFGH')), ('another model', package('1.0.1', model='Shanling M1')),
             ('no second line', package('1.0.1', info='Shanling M1 Plus\n')), ('not a tar', b'<html>rate limited</html>' * 100), ('an empty body', b''), ('cut short', pkg_ok[:300]), ('zeros', bytes(4096))]
    for what, bad in cases:
        site = Site('1.0.1', pkg=bad)
        m = machine(site, own='1.0.0', dev=0); check(m); site.pkg = bad
        r = download(m)
        expect(r == 0 and st(m)[:3] == (U['FAILED'], PN['UPBAD'], 2) and m.fs.get(FILE) == OLD and PART not in m.fs and fn(m, 'pn_job_busy') == 0, f'{what}: refused, the .part deleted, the old update.bin kept ({st(m)})')
        expect(not [c for c in m.calls if c[0] == 'rename'], f'{what}: never renamed')
    # the length the server gave and what arrived
    for clen, why in ((len(pkg_ok) + 1, 'one byte more announced'), (len(pkg_ok) - 1, 'one byte less announced'), (99999999, 'a lot more announced')):
        site = Site('1.0.1', pkg=pkg_ok, asset={'clen': clen})
        m = machine(site, own='1.0.0', dev=0); check(m); download(m)
        expect(st(m)[:2] == (U['FAILED'], PN['UPBAD']) and m.fs.get(FILE) == OLD and PART not in m.fs, f'{why}: refused')
    site = Site('1.0.1', pkg=pkg_ok, asset={'clen': -1})
    m = machine(site, own='1.0.0', dev=0); check(m); download(m)
    expect(st(m)[:2] == (U['DOWNLOADED'], 0) and m.fs.get(FILE) == pkg_ok, 'a server that gave no length is fine: the info lines still decide')
    # network and HTTP failures, part way and at once
    for rc, code, partial, why in ((56, PN['NET'], True, 'a reset part way'), (18, PN['NET'], True, 'a short transfer'), (28, PN['NET'], True, 'a time-out'), (60, PN['CERT'], False, 'a certificate'), (22, PN['GONE'], False, 'a 404'),
                                   (6, PN['NET'], False, 'no DNS'), (47, PN['NET'], False, 'too many redirects')):
        site = Site('1.0.1', pkg=pkg_ok, asset={'rc': rc, 'code': 404 if rc == 22 else 200, 'partial': partial})
        m = machine(site, own='1.0.0', dev=0); check(m)
        m.curl_site = site
        download(m)
        expect(st(m)[:3] == (U['FAILED'], code, 2) and m.fs.get(FILE) == OLD and PART not in m.fs and not [c for c in m.calls if c[0] == 'rename'] and fn(m, 'pn_job_busy') == 0,
               f'{why}: PN {code}, the .part deleted, the old update.bin kept ({st(m)})')
        expect(st(m)[3] == 2 and st(m)[4] == '1.0.1' and fn(m, 'pn_up_download') == 0, f'{why}: the offer stays, another try can start')
        m.curl_site = Site('1.0.1', pkg=pkg_ok); m.thread and work(m, m.thread)
        expect(st(m)[:2] == (U['DOWNLOADED'], 0) and m.fs.get(FILE) == pkg_ok, f'{why}: and the second try succeeds')
    # the card
    site = Site('1.0.1', pkg=pkg_ok)
    m = machine(site, own='1.0.0', dev=0); check(m); m.fail.add(('write', PART)); m.free_mb = 0
    m.free_mb = 200; download(m)
    expect(st(m)[:3] == (U['FAILED'], PN['STORAGE'], 2) and m.fs.get(FILE) == OLD and PART not in m.fs, f'a write that fails on a card with room: can\'t write ({st(m)})')
    m = machine(site, own='1.0.0', dev=0); check(m); m.fail.add(('write', PART))
    m.curl_site = lambda url, o: (setattr(m, 'free_mb', 0), site(url, o))[1]
    download(m)
    expect(st(m)[:3] == (U['FAILED'], PN['CARDFULL'], 2) and m.fs.get(FILE) == OLD and PART not in m.fs, f'a write that fails on a full card: card is full ({st(m)})')
    m = machine(site, own='1.0.0', dev=0); check(m); m.fail.add(('open', PART))
    download(m)
    expect(st(m)[:2] == (U['FAILED'], PN['STORAGE']) and m.fs.get(FILE) == OLD and fn(m, 'pn_job_busy') == 0, 'the .part cannot be created: can\'t write, no request made')
    m = machine(site, own='1.0.0', dev=0); check(m); m.fail.add(('fsync', PART))
    download(m)
    expect(st(m)[:2] == (U['FAILED'], PN['STORAGE']) and m.fs.get(FILE) == OLD and PART not in m.fs and not [c for c in m.calls if c[0] == 'rename'], 'the .part cannot be fsynced: refused before the rename')
    m = machine(site, own='1.0.0', dev=0); check(m); m.fail.add(('rename', FILE))
    download(m)
    expect(st(m)[:2] == (U['FAILED'], PN['STORAGE']) and m.fs.get(FILE) == OLD and PART not in m.fs, 'the rename fails: the .part deleted, the old update.bin kept')
    m = machine(site, own='1.0.0', dev=0); check(m); m.fail.add(('fsync', CARD))
    download(m)
    expect(st(m)[:2] == (U['FAILED'], PN['STORAGE']) and m.fs.get(FILE) == pkg_ok and PART not in m.fs, 'the directory cannot be fsynced: reported (the file is in place)')
    # space before the start
    for mb, want in ((110, 0), (109, PN['CARDFULL']), (0, PN['CARDFULL']), (4096, 0)):
        m = machine(Site('1.0.1', pkg=pkg_ok), own='1.0.0', dev=0); check(m); m.free_mb = mb; m.thread = None
        r = fn(m, 'pn_up_download')
        expect(r == want and (want == 0 or (not m.thread and st(m)[:3] == (U['FAILED'], want, 2) and st(m)[3] == 2 and m.fs.get(FILE) == OLD and PART not in m.fs)), f'{mb} MB free: {"starts" if want == 0 else "card is full, nothing is touched"}')
    m = machine(Site('1.0.1', pkg=pkg_ok), own='1.0.0', dev=0); check(m); m.fail.add(('statfs', CARD)); m.thread = None
    expect(fn(m, 'pn_up_download') == PN['STORAGE'] and not m.thread, 'the free space cannot be read: can\'t write')
    # Wi-Fi lost
    m = machine(Site('1.0.1', pkg=pkg_ok), own='1.0.0', dev=0); check(m); m.wifi = -1; m.thread = None
    expect(fn(m, 'pn_up_download') == PN['NOWIFI'] and not m.thread and st(m)[:4] == (U['FAILED'], PN['NOWIFI'], 2, 2), 'Wi-Fi off: PN_NOWIFI, the offer kept')
    m.wifi = 4
    expect(download(m) == 0 and st(m)[0] == U['DOWNLOADED'], 'and with Wi-Fi back it downloads')
    # Cancel
    site = Site('1.0.1', pkg=pkg_ok, asset={'chunk': 100})
    site.asset['xfer'] = lambda url, sent, total: m.nested(PSYMS['pn_cancel']) if sent >= 300 else None
    m = machine(site, own='1.0.0', dev=0); check(m)
    download(m)
    expect(st(m)[:3] == (U['FAILED'], PN['CANCELLED'], 2) and m.fs.get(FILE) == OLD and PART not in m.fs and fn(m, 'pn_job_busy') == 0 and st(m)[3] == 2, f'Cancel: stopped through the progress callback, the .part deleted, the old update.bin kept ({st(m)})')
    m.curl_site = Site('1.0.1', pkg=pkg_ok); m.calls = []; m.thread = None
    expect(fn(m, 'pn_up_download') == 0, 'and a download can be started again at once')
    work(m, m.thread)
    expect(st(m)[0] == U['DOWNLOADED'], 'and it completes (Cancel does not stay set)')
    # reset keeps a downloaded file's state while the file is there
    fn(m, 'pn_up_reset')
    expect(st(m)[0] == U['DOWNLOADED'] and st(m)[4] == '1.0.1', 'pn_up_reset keeps a download whose update.bin is on the card')
    m.fs.pop(FILE)
    fn(m, 'pn_up_reset')
    expect(st(m)[0] == U['IDLE'] and st(m)[4] == '', 'and forgets it once update.bin is gone')


SECTIONS = [parse_tests, redirect_tests, build_tests, info_tests, check_tests, dev_tests, download_tests]   # tools/check.py runs each as its own task


def run(ctx):
    for section in SECTIONS: section(ctx)
