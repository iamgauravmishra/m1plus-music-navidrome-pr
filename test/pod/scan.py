"""The library scan's folder walk (patch/common.c pod_scan_dir, tools/pod.py SCAN_SITE, docs/modules/payload.md hook 5): stock's folder lister (0x5ea364) skips a directory whose
name is "." or ".." or a short list of system folders, and walks every other dot-folder. The build replaces its `jalr strcmp(name, ".")` (0x5ea6a8) by `jal pod_scan_dir`;
the stock code from the name test (0x5ea69c) runs for real under Unicorn, stock and built, and must skip every hidden folder in the build only. Modelled on q2-pod's
ringnav_scan_dir test (test/patch.py)."""
import os, struct
import paths
from unicorn.mips_const import UC_MIPS_REG_S0, UC_MIPS_REG_GP
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

SITE, SKIP, KEEP = pod.SCAN_SITE, 0x5ea600, 0x5ea6b8   # the walk goes back to readdir (skip), or on to the next name test (keep)
GOT_STRCMP = -0xa94
HIDDEN = ('.', '..', '.m1plus', '.deezer', '.Trashes', '.hidden', '.a', '.LOST.DIR')
SHOWN = ('Music', 'Deezer', 'Podcasts', 'a.b', 'x.', 'lost+found2', 'Albums .old')   # (lost+found and the like are stock's later tests, not this one's)


class Walk(Machine):
    """Stock's name test at 0x5ea69c, run for real; its callees (strcmp) are the base machine's mocks."""
    COUNT = True   # test() runs emu_start itself: the block hook is its step limit
    def __init__(self, stock=False):
        super().__init__()
        self.handlers[self.word(pod.GP + GOT_STRCMP)] = 'strcmp'
        self.handlers[SKIP], self.handlers[KEEP] = 'skip', 'keep'
        self.end = None
        if stock: self.setword(SITE, 0x0320f809)

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address)
        if name in ('skip', 'keep'):
            self.end = name; u.emu_stop(); return
        return super()._hook(u, address, size, _)

    def test(self, name):
        """'skip' when the walk goes back to readdir for this directory name, 'keep' when it goes on to the next test."""
        self.end = None; self.calls = []; self.icount = 0; self.limit = 100000
        self.u.reg_write(UC_MIPS_REG_SP, STACK); self.setword(STACK + 0x38, pod.GP)
        self.u.reg_write(UC_MIPS_REG_GP, pod.GP); self.u.reg_write(UC_MIPS_REG_RA, RET)
        self.u.reg_write(UC_MIPS_REG_S0, self.cstr(name))
        self.u.emu_start(0x5ea69c, 0)
        return self.end


def run(ctx):
    scan_tests(ctx)
    query_tests(ctx)


def scan_tests(ctx):
    expect = ctx.expect
    stock_demo = open(os.path.join(paths.find_stock(paths.ZIP), 'rootfs', pod.DEMO), 'rb').read()
    m = Walk()
    built = m.data
    w = lambda b, a: struct.unpack_from('<I', b, pod.fileoff(b, a))[0]
    # the build: the one word is a jal into the payload; the pinned words around it are stock's
    expect(pod.SCAN_SITE == 0x5ea6a8 and w(stock_demo, SITE) == 0x0320f809 and w(built, SITE) >> 26 == 3 and (w(built, SITE) & 0x3ffffff) << 2 == PSYMS['pod_scan_dir'],
           'the build replaced stock\'s `jalr t9` at 0x5ea6a8 by `jal pod_scan_dir`')
    expect(all(w(stock_demo, a) == old and (a == SITE or w(built, a) == old) for a, old, _ in pod.SCAN_PINS),
           'every pinned word of the folder lister is stock\'s in the stock demo and unchanged in the build, but the site')
    expect(w(built, 0x5ea6ac) == 0x24a53ed4 and w(built, 0x5ea6b0) == 0x1040ffd3, 'the delay slot still loads a1 = "." and the branch on the result still goes back to readdir')
    expect(MANIFEST['hook_scan'] == {'addr': SITE, 'target': PSYMS['pod_scan_dir']}, 'the manifest records the hook')
    # the stock code, stock and built
    stock = Walk(stock=True)
    for n in HIDDEN + SHOWN: expect(stock.test(n) == ('skip' if n == '.' else 'keep'), f'STOCK: {n!r} -> {stock.end} (this test skips "." only; ".." falls to the next test, which skips it)')
    for n in HIDDEN: expect(m.test(n) == 'skip', f'BUILT: the hidden folder {n!r} is skipped')
    for n in SHOWN: expect(m.test(n) == 'keep', f'BUILT: {n!r} is walked as before')
    # the payload function alone: stock's strcmp for any other name, 0 for a name that starts with a dot
    f = lambda name, dot='.': m.call(PSYMS['pod_scan_dir'], a0=m.cstr(name), a1=m.cstr(dot), count=2000)
    expect(f('.m1plus') == 0 and f('..') == 0 and f('.') == 0 and f('.x', 'zzz') == 0, 'a name starting with a dot returns 0 (a match)')
    expect(f('Music') != 0 and f('') != 0 and f('Music', 'Music') == 0 and f('.', '.') == 0, 'any other name returns strcmp(name, dot)')
    m.call(PSYMS['pod_scan_dir'], a0=m.cstr('.m1plus'), a1=m.cstr('.'), count=2000)
    expect(m.calls == [] and m.icount < 12, f'a hidden name costs a few instructions and calls nothing ({m.icount})')


class QueryMachine(Machine):
    """The payload's Library query hooks run against SQLite: the stock functions behind the trampolines are an in-memory database (modelled on q2-pod's LibraryQueryMachine)."""
    COUNT = True
    TRAMPS = {'stock_dbquery_trampoline': 'db', 'stock_sorted_query_trampoline': 'sorted'}

    def __init__(self, rows):
        super().__init__()
        import sqlite3
        self.db = sqlite3.connect(':memory:')
        self.db.execute('create table songtable(id,album,songer,albumsonger,composer,style,fileurl,track)')
        self.db.executemany('insert into songtable values(?,?,?,?,?,?,?,?)', [r + (None,) * (8 - len(r)) for r in rows])
        self.tramp = {PSYMS[n]: k for n, k in self.TRAMPS.items()}
        for a in self.tramp: self.handlers[a] = 'tramp'
        self.sql = self.results = self.via = None

    def _hook(self, u, address, size, _):
        if address in self.tramp:
            a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
            assert self.read_cstr(a0) == '/mnt/data/database.db' and (a2, a3) == (123, 1), 'the callback and the sort flag pass through'
            self.sql, self.via = self.read_cstr(a1), self.tramp[address]
            self.results = self.db.execute(self.sql).fetchall()
            u.reg_write(UC_MIPS_REG_V0, len(self.results)); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        return super()._hook(u, address, size, _)

    def query(self, sql, fn='pc_library_query'):
        self.sql = None
        n = self.call(PSYMS[fn], a0=self.cstr('/mnt/data/database.db'), a1=self.cstr(sql), a2=123, a3=1, count=20000)
        return n, self.sql


def first_track_tests(expect):
    """An album is its first track: the album lists keep the lowest track number (untagged after tagged, then the lowest path) and an album's own query lists in that order.
    The device's SQLite 3.19.3 keeps the LAST row of a group for bare columns, newer ones the first, so the engine's rule is probed and the chosen row is checked against the
    rule applied to the ordered subquery; where the rule is the device's (last row) it must be the album's first track."""
    import sqlite3
    probe = sqlite3.connect(':memory:')
    probe.execute('create table t(a,b)')
    probe.executemany('insert into t values(?,?)', [('x', 1), ('x', 2), ('x', 3), ('y', 5), ('y', 4)])
    last_row = probe.execute('select b from (select * from t order by b) group by a COLLATE NOCASE order by a').fetchall() == [(3,), (5,)]
    #        id, album, songer, albumsonger, composer, style, fileurl, track
    rows = [(1, 'Alpha', 'A', 'A', 'C1', 'Rock', '/mnt/mmc/m/a/03.flac', 3), (2, 'alpha', 'A', 'A', 'C1', 'Rock', '/mnt/mmc/m/a/02.flac', 2),
            (3, 'ALPHA', 'B', 'A', 'C2', 'Pop', '/mnt/mmc/m/a/01.flac', 1), (4, 'Alpha', 'A', 'A', 'C1', 'Rock', '/mnt/mmc/m/a/00.flac', 0),
            (5, 'Beta', 'C', 'C', 'C3', 'Pop', '/mnt/mmc/m/b/z.flac', None), (6, 'Beta', 'C', 'C', 'C3', 'Pop', '/mnt/mmc/m/b/y.flac', 0),
            (7, 'Beta', 'C', 'C', 'C3', 'Pop', '/mnt/mmc/m/b/x.flac', 7), (8, 'Gamma', 'C', 'C', 'C3', 'Pop', '/mnt/mmc/m/g/b.flac', 5),
            (9, 'Gamma', 'C', 'C', 'C3', 'Pop', '/mnt/mmc/m/g/a.flac', 5), (10, 'Delta', 'D', 'D', 'C4', 'Jazz', '/mnt/mmc/m/d/b.flac', None),
            (11, 'Delta', 'D', 'D', 'C4', 'Jazz', '/mnt/mmc/m/d/a.flac', None), (12, 'Alpha', 'A', 'A', 'C1', 'Rock', '/mnt/mmc/Podcasts/a/ep.mp3', 1)]
    first = {'alpha': 3, 'beta': 7, 'gamma': 9, 'delta': 11}   # per album (NOCASE), the lowest tagged track, then the lowest path; untagged only when nothing is tagged
    q = QueryMachine(rows)

    def chosen(sql, fn='pc_library_query'):
        q.query(sql, fn)
        return {r[1].lower(): r[0] for r in q.results}
    for fn in ('pc_library_query', 'pc_sorted_query'):
        for sql, want in (('select id,album,songer,fileurl from songtable group by album COLLATE NOCASE', first),
                          ("select id,album,songer,fileurl from songtable where songer like 'A' group by album COLLATE NOCASE", {'alpha': 2}),
                          ("select id,album,songer,fileurl from songtable where songer like 'B' group by album COLLATE NOCASE", {'alpha': 3}),
                          ("select id,album,songer,fileurl from songtable where albumsonger like 'C' group by album COLLATE NOCASE", {'beta': 7, 'gamma': 9}),
                          ("select id,album,composer,fileurl from songtable where composer like 'C3' group by album COLLATE NOCASE", {'beta': 7, 'gamma': 9}),
                          ("select id,album,songer,style,fileurl from songtable where style like 'Pop' group by album COLLATE NOCASE", {'alpha': 3, 'beta': 7, 'gamma': 9}),
                          ('select id,album,songer,fileurl from songtable where songer="Nobody" group by album COLLATE NOCASE', {}),
                          ('select id,album,songer,fileurl from songtable group by album COLLATE NOCASE;', first)):
            got = chosen(sql, fn)
            expect('order by' in q.sql and 'podcasts/%' in q.sql, f'{fn}: {sql[:50]!r}: the rewrite orders the filtered subquery')
            if last_row: expect(got == want, f'{fn}: {sql[:70]!r} -> {got} (want {want}): the first track of each album')
            else: expect(len(got) == len(want) and set(got) == set(want), f'{fn}: {sql[:70]!r}: the same albums ({got})')
    # the text verified by hand against the SQLite 3.19.3 amalgamation (shell: first tracks 3, 7, 11, 9 in the rows above)
    q.query("select id,album,songer,fileurl from songtable where songer like 'A' group by album COLLATE NOCASE")
    expect(q.sql == "select id,album,songer,fileurl from (select * from songtable where ifnull(fileurl,'') not like '/mnt/mmc/podcasts/%' order by (ifnull(track,0)<=0) desc, "
                    "ifnull(track,0) desc, fileurl desc) where songer like 'A' group by album COLLATE NOCASE", f'the album list text: {q.sql}')
    # the other grouping queries are not ordered; an album's own tracks are, ascending (the first is the album's first track)
    for sql in ('select id,songer from songtable group by songer COLLATE NOCASE', 'select id,albumsonger from songtable group by albumsonger COLLATE NOCASE',
                'select id,style from songtable group by style COLLATE NOCASE', 'select * from songtable where albumsonger like \'A\''):
        q.query(sql)
        expect('order by' not in q.sql, f'{sql[:50]!r}: not an album list, no order added')
    for sql, want in (("select * from songtable where album like 'alpha'", [3, 2, 1, 4]),   # tracks 1, 2, 3, then the untagged one
                      ("select * from songtable where album like 'Beta'", [7, 6, 5]), ('select * from songtable where album="Gamma"', [9, 8]),
                      ("select * from songtable where album like 'Delta' and songer like 'D'", [11, 10]),
                      ("select * from songtable where album like 'alpha' and songer='B'", [3])):
        q.query(sql)
        ids = [r[0] for r in q.results]
        expect(ids == want, f'{sql[:60]!r}: tracks in order, ids {ids} (want {want})')
    # a text that does not fit once ordered goes to stock untouched; one that fits is rewritten within the buffer
    seen = set()
    for pad in range(800, 1000, 4):
        sql = 'select id,album,songer,fileurl from songtable group by album COLLATE NOCASE' + ' ' * (pad - 77)
        qq = QueryMachine([])
        qq.query(sql)
        seen.add(qq.sql == sql)
        expect(qq.sql == sql or ('order by' in qq.sql and len(qq.sql) < 1024), f'a {len(sql)} byte album list: stock or rewritten within the buffer')
    expect(seen == {True, False}, 'the long album lists reach both outcomes')


def query_tests(ctx):
    expect = ctx.expect
    stock_demo = open(os.path.join(paths.find_stock(paths.ZIP), 'rootfs', pod.DEMO), 'rb').read()
    built = Machine().data
    w = lambda b, a: struct.unpack_from('<I', b, pod.fileoff(b, a))[0]
    for at, pro, fn, name in ((pod.QUERY_DB, pod.QUERY_DB_PROLOGUE, 'pc_library_query', 'toolsQueryDbTable'), (pod.QUERY_SORT, pod.QUERY_SORT_PROLOGUE, 'pc_sorted_query', 'toolsQueryDbTableAndSort')):
        expect(tuple(w(stock_demo, at + 4 * i) for i in range(3)) == pro, f'{name} is stock\'s PIC prologue in the stock demo')
        j = w(built, at)
        expect(j >> 26 == 2 and (j & 0x3ffffff) << 2 == PSYMS[fn] and w(built, at + 4) == 0, f'the build replaced {name}\'s prologue by `j {fn}; nop`')
        expect(w(built, at + 12) == w(stock_demo, at + 12), f'{name}: the word the trampoline resumes at is stock\'s')
    expect(all(w(stock_demo, a) == old and w(built, a) == old for a, old, _ in pod.QUERY_PINS), 'the pinned words of both query functions are stock\'s, in the stock demo and in the build')
    cstr_at = lambda b, a: b[pod.fileoff(b, a):].split(b'\0')[0]
    expect(cstr_at(stock_demo, 0x74ba58) == b'myfav' and cstr_at(stock_demo, 0x74ba6c) == b'select * from %s', 'stock: getAllFav formats "select * from %s" with "myfav" (the filter matches the text exactly)')
    expect(MANIFEST['hook_query'] == {'addr': pod.QUERY_DB, 'target': PSYMS['pc_library_query']} and MANIFEST['hook_sorted_query']['addr'] == pod.QUERY_SORT, 'the manifest records both hooks')
    for n, at in (('stock_dbquery_trampoline', pod.QUERY_DB), ('stock_sorted_query_trampoline', pod.QUERY_SORT)):   # gp restored, then a jump past the displaced prologue
        tw = [w(built, PSYMS[n] + 4 * i) for i in range(4)]
        expect(tw[0] >> 16 == 0x3c1c and tw[2] >> 26 == 2 and (tw[2] & 0x3ffffff) << 2 == at + 12, f'{n} jumps to {at + 12:#x}')

    rows = [(1, 'Shared', 'Shared', 'Shared', 'Shared', 'Rock', '/mnt/mmc/Podcasts/show/episode.mp3'),
            (2, 'Shared', 'Shared', 'Shared', 'Shared', 'Rock', '/mnt/mmc/Music/track.flac'),
            (3, '', '', '', '', '', '/mnt/mmc/PODCASTS/untagged.mp3'),
            (4, 'Pod', 'Host', 'Host', 'Host', 'Talk', '/mnt/mmc/pOdCaStS/Show/ep.mp3'),
            (5, 'Extra', 'Singer', 'Singer', 'Singer', 'Pop', '/mnt/mmc/Podcasts Extra/song.mp3'),
            (6, 'Nested', 'Singer', 'Singer', 'Singer', 'Pop', '/mnt/mmc/Music/Podcasts/song.mp3'),
            (7, 'Nopath', 'Nobody', 'Nobody', 'Nobody', 'Pop', None),
            (8, '', '', '', '', '', '/mnt/mmc/Music/untagged.mp3')]
    q = QueryMachine(rows)
    for fn, via in (('pc_library_query', 'db'), ('pc_sorted_query', 'sorted')):
        for sql, want in (('select id,album,songer,fileurl from songtable group by album COLLATE NOCASE', {2, 5, 6, 7, 8}),
                          ('select id,songer from songtable group by songer COLLATE NOCASE', {2, 5, 7, 8}),
                          ('select id,albumsonger from songtable group by albumsonger COLLATE NOCASE', {2, 5, 7, 8}),
                          ('select id,composer from songtable group by composer COLLATE NOCASE', {2, 5, 7, 8}),
                          ('select id,style from songtable group by style COLLATE NOCASE', {2, 5, 8}),
                          ("select id,album,songer,fileurl from songtable where songer like 'Shared' group by album COLLATE NOCASE", {2}),
                          ("select * from songtable where album like 'Shared'", {2}),
                          ('select * from songtable ORDER BY id DESC limit 100;', {2, 5, 6, 7, 8}),
                          ('select * from songtable', {2, 5, 6, 7, 8})):
            n, got = q.query(sql, fn)
            expect(got is not None and q.via == via and {r[0] for r in q.results} == want and n == len(q.results),
                   f'{fn}: {sql[:60]!r} -> ids {sorted(r[0] for r in q.results)} (want {sorted(want)}); the shared album keeps the music row, untagged episodes add no Unknown row')
    # stock's text for anything that is not a songtable select, or does not fit: unchanged
    for sql in ('select * from playlist where id > 100 and cd_num=3', 'select * from myfav where id=1', 'select * from myfav ', 'select * from myfav;', 'select * from myfav2', 'delete from songtable', 'select * from songtable2', 'SELECT * FROM songtable',
                '', 'select 1 where 0 /* from songtable */ ' + 'x' * 1100, 'select * from songtable where fileurl=\'' + 'y' * 1100 + '\''):
        qq = QueryMachine([])
        qq.db.execute('create table playlist(id,cd_num)'); qq.db.execute('create table myfav(id)'); qq.db.execute('create table songtable2(id)')
        try: qq.query(sql)
        except Exception: pass
        expect(qq.sql == sql, f'{sql[:50]!r}: stock SQL, untouched')
    first_track_tests(expect)
    # Favourites (getAllFav: exactly "select * from myfav") is music only; with pc_saved_scope set (the Saved page) it is the episodes only, the last saved first
    fav = [(1, '/mnt/mmc/Music/a.flac'), (2, '/mnt/mmc/Podcasts/Show/ep1.mp3'), (3, '/mnt/mmc/Music/Podcasts/b.flac'), (4, '/mnt/mmc/pOdCaStS/Show/ep2.mp3'), (5, None), (6, '/mnt/mmc/Podcasts Extra/c.mp3'), (7, '/mnt/mmc/Podcasts/Other/ep3.mp3')]
    qf = QueryMachine([])
    qf.db.execute('create table myfav(id,fileurl)'); qf.db.executemany('insert into myfav values(?,?)', fav)
    for fn in ('pc_library_query', 'pc_sorted_query'):
        n, got = qf.query('select * from myfav', fn)
        expect(got is not None and [r[0] for r in qf.results] == [1, 3, 5, 6], f'{fn}: Favourites lists the music rows, in the table order ({[r[0] for r in qf.results]}): {got}')
        qf.u.mem_write(PSYMS['pc_saved_scope'], b'\1')
        n, got = qf.query('select * from myfav', fn)
        expect(got is not None and [r[0] for r in qf.results] == [7, 4, 2], f'{fn}: with the Saved scope the episodes, the last saved first ({[r[0] for r in qf.results]}): {got}')
        qf.u.mem_write(PSYMS['pc_saved_scope'], b'\0')
    expect(qf.icount < 1500 and qf.calls == [], f'the myfav rewrite costs {qf.icount} instructions')
    n, got = q.query('select * from songtable where id=2')
    expect(got == "select * from (select * from songtable where ifnull(fileurl,'') not like '/mnt/mmc/podcasts/%') where id=2", f'the rewritten text: {got}')
    expect(q.icount < 2500 and q.calls == [], f'one rewrite costs {q.icount} instructions and calls nothing but the trampoline')
