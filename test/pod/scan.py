"""The library scan's folder walk (patch/common.c m1_scan_dir, tools/pod.py SCAN_SITE, docs/modules/payload.md hook 5): stock's folder lister (0x5ea364) skips a directory whose
name is "." or ".." or a short list of system folders, and walks every other dot-folder. The build replaces its `jalr strcmp(name, ".")` (0x5ea6a8) by `jal m1_scan_dir`;
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
    expect(pod.SCAN_SITE == 0x5ea6a8 and w(stock_demo, SITE) == 0x0320f809 and w(built, SITE) >> 26 == 3 and (w(built, SITE) & 0x3ffffff) << 2 == PSYMS['m1_scan_dir'],
           'the build replaced stock\'s `jalr t9` at 0x5ea6a8 by `jal m1_scan_dir`')
    expect(all(w(stock_demo, a) == old and (a == SITE or w(built, a) == old) for a, old, _ in pod.SCAN_PINS),
           'every pinned word of the folder lister is stock\'s in the stock demo and unchanged in the build, but the site')
    expect(w(built, 0x5ea6ac) == 0x24a53ed4 and w(built, 0x5ea6b0) == 0x1040ffd3, 'the delay slot still loads a1 = "." and the branch on the result still goes back to readdir')
    expect(MANIFEST['hook_scan'] == {'addr': SITE, 'target': PSYMS['m1_scan_dir']}, 'the manifest records the hook')
    # the stock code, stock and built
    stock = Walk(stock=True)
    for n in HIDDEN + SHOWN: expect(stock.test(n) == ('skip' if n == '.' else 'keep'), f'STOCK: {n!r} -> {stock.end} (this test skips "." only; ".." falls to the next test, which skips it)')
    for n in HIDDEN: expect(m.test(n) == 'skip', f'BUILT: the hidden folder {n!r} is skipped')
    for n in SHOWN: expect(m.test(n) == 'keep', f'BUILT: {n!r} is walked as before')
    # the payload function alone: stock's strcmp for any other name, 0 for a name that starts with a dot
    f = lambda name, dot='.': m.call(PSYMS['m1_scan_dir'], a0=m.cstr(name), a1=m.cstr(dot), count=2000)
    expect(f('.m1plus') == 0 and f('..') == 0 and f('.') == 0 and f('.x', 'zzz') == 0, 'a name starting with a dot returns 0 (a match)')
    expect(f('Music') != 0 and f('') != 0 and f('Music', 'Music') == 0 and f('.', '.') == 0, 'any other name returns strcmp(name, dot)')
    m.call(PSYMS['m1_scan_dir'], a0=m.cstr('.m1plus'), a1=m.cstr('.'), count=2000)
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


MUSIC = "ifnull(fileurl,'') not like '/mnt/mmc/podcasts/%'"
HAVING = " having min(printf('%d%08x%d%s',ifnull(track,0)<=0,ifnull(track,0)+2147483648,fileurl is not null,fileurl)) is not null"
ORDER = ' order by (ifnull(track,0)<=0), ifnull(track,0), fileurl'
# stock's album lists (getAllAlbum, getAlbumByArtist/AlbumArtist/Composer/Genre, SearchAlbumByName) and an album's own tracks (getMusicByAlbum, getMusicByAlbumAnd*): the format, its arguments
ALBUM_LISTS = (('select id,album,songer,fileurl from %s group by album COLLATE NOCASE', ()),
               ('select id,album,songer,fileurl from %s where songer="" group by album COLLATE NOCASE', ()),
               ("select id,album,songer,fileurl from %s where songer like '%s' group by album COLLATE NOCASE", ('A',)),
               ("select id,album,songer,fileurl from %s where songer like '%s' group by album COLLATE NOCASE", ('B',)),
               ('select id,album,songer,fileurl from %s where albumsonger="" group by album COLLATE NOCASE', ()),
               ("select id,album,songer,fileurl from %s where albumsonger like '%s' group by album COLLATE NOCASE", ('C',)),
               ('select id,album,composer,fileurl from %s where composer="" group by album COLLATE NOCASE', ()),
               ("select id,album,composer,fileurl from %s where composer like '%s' group by album COLLATE NOCASE", ('C3',)),
               ('select id,album,songer,style,fileurl from %s where style="" group by album COLLATE NOCASE', ()),
               ("select id,album,songer,style,fileurl from %s where style like '%s' group by album COLLATE NOCASE", ('Pop',)),
               ("select id,album,songer,fileurl from %s where album like '%%%s%%' group by album COLLATE NOCASE", ('lph',)),
               ("select id,album,songer,fileurl from %s where songer like '%s' group by album COLLATE NOCASE", ('Nobody',)))
ALBUM_TRACKS = (('select * from %s where album=""', ()), ("select * from %s where album like '%s'", ('alpha',)),
                ('select * from %s where album like \'%s\' and songer=""', ('zeta',)), ("select * from %s where album like '%s' and songer like '%s'", ('alpha', 'B')),
                ('select * from %s where album like \'%s\' and albumsonger=""', ('zeta',)), ("select * from %s where album like '%s' and albumsonger like '%s'", ('Beta', 'C')),
                ('select * from %s where album like \'%s\' and composer=""', ('zeta',)), ("select * from %s where album like '%s' and composer like '%s'", ('Gamma', 'C3')),
                ('select * from %s where album like \'%s\' and style=""', ('zeta',)), ("select * from %s where album like '%s' and style like '%s'", ('Delta', 'Jazz')))


def first_track_tests(expect, stock_demo):
    """An album is its first track: the album lists keep the lowest track number (untagged, NULL or <= 0, after tagged; then the lowest path, NULL first) through one min() in
    HAVING, the bare-column rule SQLite documents (the host's SQLite and the device's 3.19.3 agree), and an album's own query lists its tracks in that order. Every stock statement
    of both kinds runs, rewritten, against SQLite; the column list stays stock's (its callbacks count the columns)."""
    import re
    #        id, album, songer, albumsonger, composer, style, fileurl, track
    rows = [(1, 'Alpha', 'A', 'A', 'C1', 'Rock', '/mnt/mmc/m/a/03.flac', 3), (2, 'alpha', 'A', 'A', 'C1', 'Rock', '/mnt/mmc/m/a/02.flac', 2),
            (3, 'ALPHA', 'B', 'A', 'C2', 'Pop', '/mnt/mmc/m/a/01.flac', 1), (4, 'Alpha', 'A', 'A', 'C1', 'Rock', '/mnt/mmc/m/a/00.flac', 0),
            (5, 'Beta', 'C', 'C', 'C3', 'Pop', '/mnt/mmc/m/b/z.flac', None), (6, 'Beta', 'C', 'C', 'C3', 'Pop', '/mnt/mmc/m/b/y.flac', 0),
            (7, 'Beta', 'C', 'C', 'C3', 'Pop', '/mnt/mmc/m/b/x.flac', 7), (8, 'Gamma', 'C', 'C', 'C3', 'Pop', '/mnt/mmc/m/g/b.flac', 5),
            (9, 'Gamma', 'C', 'C', 'C3', 'Pop', '/mnt/mmc/m/g/a.flac', 5), (10, 'Delta', 'D', 'D', 'C4', 'Jazz', '/mnt/mmc/m/d/b.flac', None),
            (11, 'Delta', 'D', 'D', 'C4', 'Jazz', '/mnt/mmc/m/d/a.flac', None), (12, 'Alpha', 'A', 'A', 'C1', 'Rock', '/mnt/mmc/Podcasts/a/ep.mp3', 1),
            (13, 'Edge', 'E', 'E', 'C5', 'Edge', '/mnt/mmc/m/e/b.flac', 2147483647), (14, 'edge', 'E', 'E', 'C5', 'Edge', '/mnt/mmc/m/e/a.flac', 0),
            (15, 'Neg', 'E', 'E', 'C5', 'Edge', '/mnt/mmc/m/n/a.flac', -2147483648), (16, 'Neg', 'E', 'E', 'C5', 'Edge', '/mnt/mmc/m/n/b.flac', 1),
            (17, 'Paths', 'E', 'E', 'C5', 'Edge', '', 1), (18, 'Paths', 'E', 'E', 'C5', 'Edge', None, 1), (19, 'Paths', 'E', 'E', 'C5', 'Edge', '/a', 1),
            (20, 'Paths2', 'E', 'E', 'C5', 'Edge', '/a', 1), (21, 'Paths2', 'E', 'E', 'C5', 'Edge', '', 1),
            (22, 'Zeta', '', '', '', '', '/mnt/mmc/m/z/2.flac', 2), (23, 'zeta', '', '', '', '', '/mnt/mmc/m/z/1.flac', 2)]
    first = {'alpha': 3, 'beta': 7, 'gamma': 9, 'delta': 11, 'edge': 13, 'neg': 16, 'paths': 18, 'paths2': 21, 'zeta': 23}   # per album (NOCASE)
    wants = (first, {'zeta': 23}, {'alpha': 2}, {'alpha': 3}, {'zeta': 23}, {'beta': 7, 'gamma': 9}, {'zeta': 23}, {'beta': 7, 'gamma': 9}, {'zeta': 23},
             {'alpha': 3, 'beta': 7, 'gamma': 9}, {'alpha': 3}, {})
    tracks = ([], [3, 2, 1, 4], [23, 22], [3], [23, 22], [7, 6, 5], [23, 22], [9, 8], [23, 22], [11, 10])
    q = QueryMachine(rows)
    album_text = lambda m: f'{m[1]} where ' + (f'({m[2]}) and ' if m[2] else '') + f'{MUSIC} group by album COLLATE NOCASE{HAVING}{m[3]}'
    for (fmt, args), want in zip(ALBUM_LISTS, wants):
        expect(b'\0' + fmt.encode() + b'\0' in stock_demo, f'{fmt[:60]!r} is a stock format')
        for sql in (fmt % (('songtable',) + args), fmt % (('songtable',) + args) + ';'):
            for fn in ('pc_library_query', 'pc_sorted_query'):
                q.query(sql, fn)
                got = {r[1].lower(): r[0] for r in q.results}
                m = re.fullmatch(r'(select [a-z,]+ from songtable)(?: where (.*))? group by album COLLATE NOCASE(;?)', sql)
                expect(q.sql == album_text(m), f'{fn}: {sql[:70]!r}: one grouping with the filter in its WHERE and the first track in HAVING: {q.sql}')
                expect(got == want, f'{fn}: {sql[:70]!r} -> {got} (want {want}): the first track of each album')
                stock = q.db.execute(sql)
                expect(len(q.db.execute(q.sql).description) == len(stock.description) and {r[1].lower() for r in stock} == set(got),
                       f'{sql[:70]!r}: stock\'s columns, no album beyond stock\'s')
    # Get Info's lookup (patch/covercache.c cc_album_rep_key): getAllAlbum's statement filtered to one album name is an album list like the others, so the filter gives its group the same
    # first track, and the record is the one the full list has for that name, whatever the order SQLite scans the rows in (a track list under several songers, a quote in the name,
    # a name that exists only as a podcast, a name the library lacks). The stock database has no index (no CREATE INDEX string in the demo), so the unfiltered plan would be a table scan.
    more = rows + [(24, "It's", 'S1', 'S1', '', '', '/mnt/mmc/m/i/2.flac', 2), (25, "IT'S", 'S2', 'S2', '', '', '/mnt/mmc/m/i/1.flac', 1), (26, "it's", 'S3', 'S3', '', '', '/mnt/mmc/m/i/3.flac', 3),
                   (27, 'Pod Only', 'P', 'P', '', '', '/mnt/mmc/Podcasts/x.mp3', 1), (28, 'Spaces and, commas; (parens)', 'S4', 'S4', '', '', '/mnt/mmc/m/s/1.flac', 1)]
    for order in (more, list(reversed(more))):   # (insertion order is the other thing the plain bare-column rule would depend on)
        q = QueryMachine(order)
        q.query(pod.ALBUM_SQL)
        full = {r[1].lower(): r[0] for r in q.results}
        for name in sorted({r[1] for r in more} | {'ALPHA', 'bEtA', 'No Such Album'}):
            sql = f"{pod.ALBUM_HEAD} where album='{name.replace(chr(39), chr(39) * 2)}' COLLATE NOCASE{pod.ALBUM_GROUP}"
            for fn in ('pc_library_query', 'pc_sorted_query'):
                q.query(sql, fn)
                got = [r[0] for r in q.results]
                expect(q.sql == f"{pod.ALBUM_HEAD} where (album='{name.replace(chr(39), chr(39) * 2)}' COLLATE NOCASE) and {MUSIC}{pod.ALBUM_GROUP}{HAVING}", f'{fn}: the targeted album statement is filtered like an album list: {q.sql}')
                expect(got == ([full[name.lower()]] if name.lower() in full else []), f'{fn}: {name!r}: one record, the full list\'s ({got} against {full.get(name.lower())})')
    q.query("select id,album,songer,fileurl from songtable where album='x' COLLATE NOCASE group by album COLLATE NOCASE;")
    expect(q.sql.endswith(HAVING + ';'), 'with a trailing semicolon too')
    # the texts verified by hand against the SQLite 3.19.3 amalgamation
    q.query("select id,album,songer,fileurl from songtable where songer like 'A' group by album COLLATE NOCASE")
    expect(q.sql == "select id,album,songer,fileurl from songtable where (songer like 'A') and ifnull(fileurl,'') not like '/mnt/mmc/podcasts/%' group by album COLLATE NOCASE "
                    "having min(printf('%d%08x%d%s',ifnull(track,0)<=0,ifnull(track,0)+2147483648,fileurl is not null,fileurl)) is not null", f'the album list text: {q.sql}')
    expect(q.icount < 3500 and q.calls == [], f'the album list rewrite costs {q.icount} instructions and calls nothing but the trampoline ({q.calls})')
    q.query("select * from songtable where album like 'Beta' and songer like 'C'")
    expect(q.sql == "select * from songtable where (album like 'Beta' and songer like 'C') and ifnull(fileurl,'') not like '/mnt/mmc/podcasts/%' "
                    "order by (ifnull(track,0)<=0), ifnull(track,0), fileurl", f'the album tracks text: {q.sql}')
    for (fmt, args), want in zip(ALBUM_TRACKS, tracks):
        expect(b'\0' + fmt.encode() + b'\0' in stock_demo, f'{fmt[:60]!r} is a stock format')
        sql = fmt % (('songtable',) + args)
        for fn in ('pc_library_query', 'pc_sorted_query'):
            q.query(sql, fn)
            ids = [r[0] for r in q.results]
            expect(q.sql == f'select * from songtable where ({sql[30:]}) and {MUSIC}{ORDER}', f'{fn}: {sql[:60]!r}: the filter and the order in its WHERE: {q.sql}')
            expect(ids == want, f'{fn}: {sql[:60]!r}: tracks in order, ids {ids} (want {want})')
    for sql, want in (("select * from songtable where album like 'paths'", [18, 17, 19]), ("select * from songtable where album like 'paths2'", [21, 20]),
                      ("select * from songtable where album like 'Neg'", [16, 15]), ("select * from songtable where album like 'edge'", [13, 14]),
                      ("select * from songtable where album like 'Delta' and songer like 'D'", [11, 10]), ('select * from songtable where album="Gamma";', [9, 8])):
        q.query(sql)
        ids = [r[0] for r in q.results]
        expect(ids == want and q.sql.endswith(ORDER + (';' if sql.endswith(';') else '')), f'{sql[:60]!r}: tracks in order, ids {ids} (want {want})')
    # anything else (other groupings, other album-list shapes) reads the filtered subquery, unordered
    for sql in ('select id,songer from songtable group by songer COLLATE NOCASE', 'select id,albumsonger from songtable group by albumsonger COLLATE NOCASE',
                'select id,style from songtable group by style COLLATE NOCASE', 'select * from songtable where albumsonger like \'A\'',
                'select id,album,songer,fileurl from songtable group by album COLLATE NOCASE ', 'select id,album,songer,fileurl from songtable group by album',
                'select count(id),album from songtable group by album COLLATE NOCASE', 'select id,album from songtable group by album COLLATE NOCASE order by id',
                'select *,album from songtable where album=""', 'select * from songtable where albumsonger=""'):
        q.query(sql)
        expect(q.sql == sql.replace(' from songtable', f' from (select * from songtable where {MUSIC})', 1), f'{sql[:60]!r}: not a stock album shape, the plain filter: {q.sql}')
    # a text that does not fit once rewritten goes to stock untouched; one that fits is rewritten within the buffer
    for kind, make, mark in (('album list', lambda p: f"select id,album,songer,fileurl from songtable where songer like '{p}' group by album COLLATE NOCASE", HAVING),
                             ('album', lambda p: f"select * from songtable where album like '{p}'", ORDER), ('songs', lambda p: f"select * from songtable where songer like '{p}'", MUSIC)):
        seen, qq = set(), QueryMachine([])
        for pad in range(700, 1000, 3):
            sql = make('x' * pad)
            qq.query(sql)
            seen.add(qq.sql == sql)
            expect(qq.sql == sql or (mark in qq.sql and len(qq.sql) < 1024), f'a {len(sql)} byte {kind} query: stock or rewritten within the buffer')
        expect(seen == {True, False}, f'the long {kind} queries reach both outcomes')


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
    first_track_tests(expect, stock_demo)
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
