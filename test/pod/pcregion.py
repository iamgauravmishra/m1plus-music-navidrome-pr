"""Podcast Region (patch/pcregion.c, tools/pcregion.py, docs/modules/podcasts.md "Region"): the 34 storefronts by name, the saved choice (/mnt/data/m1plus/podcast-region: two capital letters and a line feed; anything else
is Automatic), what Automatic infers (the UI language's country, for English and Spanish the Settings time zone's, else the United States) for every language, time zone and a few bad inputs against the Python model,
the value and the picker's first label, the atomic save and the removal for Automatic, the region in the search request, and the strings in 13 languages. The compiled payload runs under Unicorn."""
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


import pcregion, pod_i18n, pod_pages, timezones   # noqa: E402

FILE, TMP = pcregion.FILE, pcregion.FILE + '.tmp'
TZ = pod.DATA['TIME_ZONE'][0]
LOCALES = [('en', 'US'), ('zh', 'CN'), ('zh', 'HK'), ('zh', 'TW'), ('ja', 'JP'), ('ko', 'KR'), ('fr', 'FR'), ('ge', 'DE'), ('sp', 'ES'), ('it', 'IT'), ('th', 'TH'), ('po', 'PL'), ('ru', 'RU'), ('uk', 'UK'),
           ('en', 'GB'), ('de', 'DE'), ('es', 'ES'), ('xx', 'XX')]   # (the 13 tables, then ones no menu reaches: they are English-like or the default)


def machine(lang='en', country='US', zone=timezones.DEFAULT, saved=None):
    m = Machine()
    m.locale = m.alloc(8); m.u.mem_write(m.locale, country.encode().ljust(3, b'\0') + lang.encode().ljust(3, b'\0') + b'\0\0')
    m.setword(TZ, zone)
    if saved is not None: m.fs[FILE] = saved
    return m


def code(m):
    return m.read_cstr(m.call(PSYMS['pcregion_code'], count=2000000))


def table_tests(ctx):
    """The table: 34 storefronts sorted by name, codes unique, the picker rows after Automatic in that order; the model's own constants."""
    expect = ctx.expect
    expect(len(pcregion.REGIONS) == 34 and list(pcregion.NAMES) == sorted(pcregion.NAMES) and pcregion.CODES[-1] == 'US' and pcregion.NAMES[pcregion.CODES.index('GB')] == 'UK' and pcregion.DEFAULT == 'US',
           'thirty four storefronts by name, the United States last; the UK is named UK (the Settings row has no glyph and shares its room with the value)')
    want = set('US GB CA AU IE NZ IN SG HK TW JP KR CN DE AT CH FR BE NL IT ES PT SE NO DK FI PL BR MX AR RU UA TH ZA'.split())
    expect(set(pcregion.CODES) == want, 'the storefronts the design lists: US GB CA AU IE NZ IN SG HK TW JP KR CN DE AT CH FR BE NL IT ES PT SE NO DK FI PL BR MX AR RU UA TH ZA')
    expect(pcregion.FILE == '/mnt/data/m1plus/podcast-region' and pod_pages.REGION_PAGE.rows[0].label == 'Automatic' and [r.label for r in pod_pages.REGION_PAGE.rows[1:]] == list(pcregion.NAMES)
           and [r.arg for r in pod_pages.REGION_PAGE.rows] == list(range(35)) and all(r.action == pod_pages.ACT_REGIONSET for r in pod_pages.REGION_PAGE.rows), 'the picker: Automatic first, then the storefronts by name, the row\'s arg its index plus one')
    expect(all(pcregion.index_of(c) == i + 1 for i, c in enumerate(pcregion.CODES)) and pcregion.index_of('XX') == 0 and pcregion.index_of('us') == 0, 'index_of: the picker row of a code; 0 for one that is not offered')


def infer_tests(ctx):
    """Automatic for every language of the menu and every time zone, against the model; the cases the design names; bad zone values; the saved choice wins."""
    expect = ctx.expect
    bad = []
    for lang, country in LOCALES:
        for zone in list(range(timezones.COUNT)) + [timezones.COUNT, 100, 0xffffffff]:
            m = machine(lang, country, zone)
            got = code(m)
            want = pcregion.infer(lang, country, zone if zone < timezones.COUNT else -1)
            if got != want: bad.append((lang, country, zone, got, want))
    expect(not bad, f'Automatic as the model says for {len(LOCALES)} locales and every time zone index and a few out of range ({bad[:5]})')
    for lang, country, zone, want in (('ja', 'JP', 2, 'JP'), ('ko', 'KR', 7, 'KR'), ('zh', 'CN', 7, 'CN'), ('zh', 'HK', 7, 'HK'), ('zh', 'TW', 7, 'TW'), ('ge', 'DE', 12, 'DE'), ('fr', 'FR', 12, 'FR'), ('it', 'IT', 12, 'IT'),
                                      ('po', 'PL', 12, 'PL'), ('th', 'TH', 12, 'TH'), ('ru', 'RU', 12, 'RU'), ('uk', 'UK', 12, 'UA'),
                                      ('en', 'US', 12, 'GB'), ('en', 'US', 25, 'AU'), ('en', 'US', 41, 'AU'), ('en', 'US', 42, 'NZ'), ('en', 'US', 40, 'IN'), ('en', 'US', 7, 'US'), ('en', 'US', 4, 'US'), ('en', 'US', 6, 'MX'),
                                      ('en', 'US', 8, 'CA'), ('en', 'US', 9, 'CA'), ('sp', 'ES', 6, 'MX'), ('sp', 'ES', 12, 'GB'), ('sp', 'ES', 10, 'AR'),
                                      ('en', 'US', timezones.DEFAULT, 'US'), ('sp', 'ES', timezones.DEFAULT, 'US'), ('en', 'US', 0, 'US'), ('en', 'US', 17, 'US')):
        got = code(machine(lang, country, zone))
        expect(got == want, f'{lang}_{country}, zone {zone} ({timezones.TIMEZONES[zone][0]}): Automatic is {want} ({got})')
    expect(code(machine('ja', 'JP', 12)) == 'JP' and code(machine('en', 'US', 23)) == 'JP', 'a language that is one country wins over the zone; English follows Tokyo to JP')
    for saved, lang in ((b'GB\n', 'ja'), (b'FR', 'en'), (b'ZA\n', 'zh')):
        expect(code(machine(lang, 'XX', 23, saved)) == saved[:2].decode(), f'the saved {saved[:2].decode()} wins over the language ({lang}) and the zone')
    for data in (b'', b'\n', b'G', b'gb\n', b'GBR', b'GB \n', b'XX\n', b'GB\nUS\n', b'\nGB', b'GB\r\n', b'U\n', b'ZZ'):
        expect(code(machine('en', 'US', 12, data)) == 'GB', f'saved {data!r} is not a storefront of the table (or not exactly its two letters and a line feed): Automatic')
    for data in (b'US', b'US\n', b'ZA\n', b'ZA'):
        expect(code(machine('ja', 'JP', 2, data)) == data[:2].decode(), f'saved {data!r}: two letters of the table, a line feed or nothing after')
    m = machine('en', 'US', 12)
    expect(m.call(PSYMS['pcregion_saved'], count=2000000) == 0 and not m.fs.get(FILE) and 'open' not in [c[0] for c in m.calls if c[0] == 'open' and 'write' in str(c)], 'reading writes nothing, Automatic is row 0')
    for data, row in ((b'AR\n', 1), (b'JP\n', 1 + pcregion.CODES.index('JP')), (b'US\n', 34), (b'ZZ\n', 0)):
        expect(machine(saved=data).call(PSYMS['pcregion_saved'], count=2000000) == row, f'pcregion_saved: {data!r} is picker row {row}')


def text_of(m, fnname, *a):
    buf = m.alloc(96)
    m.call(PSYMS[fnname], a0=buf, a1=96, count=4000000)
    return m.read_cstr(buf)


def save_tests(ctx):
    """pcregion_set: a row saves its code atomically; Automatic removes the file; a failed write changes nothing; a row out of range is -1; the value and the picker's first label."""
    expect = ctx.expect
    m = machine('en', 'US', 12)
    r = m.call(PSYMS['pcregion_set'], a0=1 + pcregion.CODES.index('JP'), count=4000000)
    expect(r == 1 + pcregion.CODES.index('JP') and m.fs.get(FILE) == b'JP\n' and TMP not in m.fs and ('rename', TMP, FILE) in m.calls and ('fsync', '/mnt/data/m1plus') in m.calls and code(m) == 'JP',
           'a tap on Japan: written atomically (a temp file, fsync, rename, the folder fsync\'d), the region reads JP at once')
    r = m.call(PSYMS['pcregion_set'], a0=0, count=4000000)
    expect(r == 0 and FILE not in m.fs and code(m) == 'GB' and m.call(PSYMS['pcregion_saved'], count=2000000) == 0, 'Automatic: the file is removed, the region is the inferred one again (London: GB)')
    r = m.call(PSYMS['pcregion_set'], a0=0, count=4000000)
    expect(r == 0 and FILE not in m.fs, 'Automatic with no file: nothing to remove, still 0')
    m = machine(saved=b'FR\n'); m.fail.add(('write', TMP))
    r = m.call(PSYMS['pcregion_set'], a0=1 + pcregion.CODES.index('DE'), count=4000000)
    expect(r == 0xffffffff and m.fs.get(FILE) == b'FR\n' and TMP not in m.fs and code(m) == 'FR', 'a failed write: -1, the file and the region as they were')
    for row in (35, 36, -1, 1000):
        m = machine(saved=b'FR\n')
        expect(m.call(PSYMS['pcregion_set'], a0=row & 0xffffffff, count=4000000) == 0xffffffff and m.fs.get(FILE) == b'FR\n', f'row {row} is not a row: -1, nothing written')
    for i, (c, n) in enumerate(pcregion.REGIONS):
        m = machine()
        m.call(PSYMS['pcregion_set'], a0=i + 1, count=4000000)
        expect(m.fs.get(FILE) == c.encode() + b'\n' and code(m) == c and text_of(m, 'pcregion_value') == n, f'row {i + 1}: {c} saved, the Settings value reads "{n}"')
    # names: the table's, the code itself for one that is not in it
    m = machine()
    p = m.cstr('US'); nm = m.read_cstr(m.call(PSYMS['pcregion_name'], a0=p, count=2000000))
    p2 = m.cstr('XQ'); nm2 = m.read_cstr(m.call(PSYMS['pcregion_name'], a0=p2, count=2000000))
    expect(nm == 'United States' and nm2 == 'XQ', 'pcregion_name: United States for US, the code for one the table lacks')
    # the Settings value and the picker's first row
    expect(text_of(machine(), 'pcregion_value') == 'Automatic' and text_of(machine(saved=b'ZZ\n'), 'pcregion_value') == 'Automatic', 'no choice (or a bad file): the value reads Automatic')
    for lang, country, zone, want in (('en', 'US', timezones.DEFAULT, 'Automatic (United States)'), ('ja', 'JP', 2, 'Automatic (Japan)'), ('en', 'US', 12, 'Automatic (UK)'), ('sp', 'ES', 6, 'Automatic (Mexico)'),
                                      ('zh', 'HK', 7, 'Automatic (Hong Kong)')):
        expect(text_of(machine(lang, country, zone), 'pcregion_auto_label') == want, f'the picker\'s first row for {lang}_{country}, zone {zone}: "{want}"')
    expect(text_of(machine('ja', 'JP', 2, b'DE\n'), 'pcregion_auto_label') == 'Automatic (Japan)', 'it names the inferred storefront even when another is chosen')
    m = machine('ja', 'JP', 2); m.set_language('zh_CN')
    got = text_of(m, 'pcregion_auto_label').encode('latin-1').decode('utf-8')   # (a mocked translation comes back as UTF-8 read as latin-1)
    expect(got == pod_i18n.TEXT['Automatic']['zh_CN'] + ' (Japan)', f'"Automatic" follows the language, the storefront\'s name stays English ({got})')


def search_tests(ctx):
    """The search request takes the region: country=<CODE> (upper case) from the saved choice, Automatic from the language and the zone."""
    expect = ctx.expect
    SE = sibling('pcsearch')
    for saved, lang, zone, want in ((None, 'en', timezones.DEFAULT, 'US'), (None, 'en', 12, 'GB'), (None, 'ja', 12, 'JP'), (b'AU\n', 'en', 12, 'AU'), (b'ZA\n', 'ko', 7, 'ZA'), (b'junk', 'en', 12, 'GB')):
        reqs = []

        def site(url, o_): reqs.append(url); return {'body': b'{"resultCount":0,"results":[]}'}
        m = SE.machine(site=site)
        m.locale = m.alloc(8); m.u.mem_write(m.locale, b'XX\0' + lang.encode().ljust(3, b'\0') + b'\0\0'); m.setword(TZ, zone)
        if saved is not None: m.fs[FILE] = saved
        r, th = SE.start_search(m, 'jazz'); SE.PCN.work(m, th)
        expect(reqs[0] == f'https://itunes.apple.com/search?media=podcast&entity=podcast&limit=25&country={want}&term=jazz', f'{lang}, zone {zone}, saved {saved!r}: the request is for {want} ({reqs[0]})')


def files_tests(ctx):
    """Settings > Developer > Tools > Settings Files shows podcast-region: the two letters, missing, empty or other."""
    expect = ctx.expect
    P = pod_pages
    expect('podcast-region' in P.SETTING_FILES and 'podcast-online-search' in P.SETTING_FILES, 'the Settings Files page lists podcast-region, after the Podcast Discover switch\'s podcast-online-search')
    k = P.SETTING_FILES.index('podcast-region')
    for data, want in ((None, 'missing'), (b'JP\n', 'JP'), (b'GB', 'GB'), (b'', 'empty'), (b'JAPAN\n', 'other'), (b'J\n', 'J')):
        m = Machine()
        if data is not None: m.fs[FILE] = data
        m.call(PSYMS['setfiles_open'], count=4000000)
        buf = m.alloc(64)
        m.call(PSYMS['setfiles_stat'], a0=5 + k, a1=buf, a2=64, count=2000000)
        expect(m.read_cstr(buf) == want, f'podcast-region {data!r}: the row reads "{want}" ({m.read_cstr(buf)})')


def string_tests(ctx):
    """The strings of the Region row in 13 languages: a text each; the key of the Discover line keeps its %s."""
    expect = ctx.expect
    for loc in pod_i18n.LOCALES:
        t = pod_i18n.table_for(loc)
        expect(all(pod_i18n.TEXT[k][t] for k in ('Podcast Region', 'Automatic', 'Top 25 Shows in %s', 'Top 25 Episodes in %s')) and all(pod_i18n.TEXT[k][t].count('%s') == 1 for k in ('Top 25 Shows in %s', 'Top 25 Episodes in %s')),
               f'{loc}: Podcast Region, Automatic and the two Discover lines have a text (the lines one %s)')
    expect(all(n in pod_i18n.BRANDS for n in pcregion.NAMES) and 'Podcast Search' not in pod_i18n.TEXT and all(pod_i18n.TEXT['Podcast Discover']), 'the storefront names are shown as they are; Podcast Search\'s key is gone, Podcast Discover has its own')


SECTIONS = [table_tests, infer_tests, save_tests, search_tests, files_tests, string_tests]


def run(ctx):
    for f in SECTIONS: f(ctx)
