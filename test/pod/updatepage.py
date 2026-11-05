"""The Software Update page (patch/update.c, tools/pod_ui.py build_update_page, docs/modules/update.md), on the real compiled payload under Unicorn with the worker thread run by the test.

Proved: the built asset (the stock navbar, one block of a glyph, a title, an explanation and two pills, the Podcasts dialog's scrim and card as the download popup, everything inside the 320 x 450 window, the
hidden ones hidden and insensitive, the colours legible on black and neutral, every text fitting in all 13 languages, the confirm dialog's text wrapping in three lines) and the About page's link row; the
page's states as the user reads them (idle with the installed version, checking, up to date, a version available with Download and Install, downloaded with Install and Check Again, and every failure with
its words and pill) in all 13 languages and at their fixed places (tools/pod_ui.py UP_YS); the confirm dialog (its text, Cancel starts nothing and makes no request, its buttons relabelled Cancel and
Download); the popup (title, percentage, bar, Cancel; Cancelling... until the worker has stopped; Back is Cancel; errors close it and show on the page); the hand-over to the stock TF card update (a pinned
call, never a page) when a download completes with the page in front and not otherwise; Check Again and a second download over an existing update.bin (the old file stays until the new one is verified, and
stays on a failure or a cancel); waiting for the job slot; the power timers kept from firing during a job; the page's life (one timer, Back and Now Playing bound, the worker cancelled on destroy, a second
open, a wrong asset, the state kept for a downloaded update and dropped for an old answer)."""
import os
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import awtk_ui
from awtk_text import Ttf, StbText
import pod_pages, pod_i18n, pod_ui

PCS = sibling('pcsearch'); UP = sibling('update')   # noqa: F821  (sibling: the harness helper of the pod tests)
PCN, fn = PCS.PCN, PCS.fn
RAW = os.path.join('rootfs', 'release', 'assets', 'default', 'raw')
UI = os.path.join(RAW, 'ui', 'm1plus_update.bin')
WIN = 0x24300000
EVT_DESTROY, EVT_CLICK, EVT_FG, EVT_BG = O['EVT_DESTROY'], O['EVT_CLICK'], O['EVT_WINDOW_TO_FG'], O['EVT_WINDOW_TO_BG']
POPUP = ('up_pd_scrim', 'up_pd_card', 'up_pd_title', 'up_pd_name', 'up_pd_count', 'up_pd_fill', 'up_pd_cancel')
NAMES = ('up_icon', 'up_title', 'up_text', 'up_pill', 'up_pill2', 'btn_return', 'btn_backtoplayer') + POPUP
VERSION = UP.build.about(UP.json.load(open(os.path.join(WORK, 'build.json')))['tag'])   # the About row's text: what M1PLUS_TAG is
TITLE_PX, TEXT_PX, PILL_PX = 22, 18, 20
PN, U = UP.PN, UP.U
CONFIRM = 'Download %s (55 MB)? It replaces update.bin on the card.'
BAR_W = O['PD_BAR_W']

# the failures: code -> (glyph, title, text, pill) as the page shows them (a pill of None: none)
FAILS = {
    PN['NOWIFI']: ('pod_es_wifi', 'Connect to Wi-Fi first', 'Turn on Wi-Fi and try again.', 'Try Again'),
    PN['NOCLOCK']: ('pod_es_calendar', 'Set the date first', 'Secure connections need the right date.', 'Try Again'),
    PN['NOCERT']: ('pod_es_lock', 'Certificates missing', 'This device has no certificate bundle.', None),
    PN['CERT']: ('pod_es_lock', 'Certificate problem', "The server's certificate was not accepted.", 'Try Again'),
    PN['UPCHECK']: ('pod_es_info', "Can't check for updates", 'GitHub did not name a release. Try again later.', 'Try Again'),
    PN['UPBAD']: ('pod_es_info', "Download doesn't match", 'The file was not the version offered. Nothing was changed.', 'Try Again'),
    PN['CARDFULL']: ('pod_es_card', 'Card is full', 'Free at least 110 MB on the card.', 'Try Again'),
    PN['STORAGE']: ('pod_es_card', "Can't write to the card", 'Check the TF card and try again.', 'Try Again'),
    PN['MEM']: ('pod_es_drive', 'Not enough memory', '', 'Try Again'),
    PN['NET']: ('pod_es_plug', "Can't reach GitHub", 'Check your Wi-Fi connection.', 'Try Again'),
    PN['CANCELLED']: ('pod_es_download', 'Download cancelled', '', 'Download and Install'),
}
STATE_KEYS = ['Version %s', 'Checking…', 'Up to Date', 'You have the latest version.', 'Version %s available', 'Current version: %s', 'Download and Install', 'Update Downloaded', 'Version %s is ready to install.',
              'Install', 'Check Again', 'Check for Update', 'Software Update', 'Downloading %s', 'This may take a few minutes.', 'Cancel', 'Cancelling…', 'Download', CONFIRM]
KEYS = sorted({k for g, t, x, p in FAILS.values() for k in (t, x, p) if k} | set(STATE_KEYS))


class UM(PCN.NM):
    """The page's window and widgets, the scripted GitHub, the worker run by the test."""
    def __init__(self, site, **kw):
        super().__init__()
        self.window = WIN
        self.dirs.update({'/mnt/mmc', '/mnt/mmc/.m1plus'})
        self.present.add(PCN.CA)
        self.curl_site = site
        self.jinit()
        self.hist = []
        for k, v in kw.items(): setattr(self, k, v)
        for n in NAMES: Machine.widget(self, n)   # noqa: F821
        for n in ('up_pd_scrim', 'up_pd_card'): self.props[(self.widgets[n], 'visible')] = self.props[(self.widgets[n], 'sensitive')] = 0   # (hidden in the asset; the payload shows them on a transition only)
        win = self.alloc(0x80)
        for off, v in ((0, 0), (4, 0), (8, 320), (0xc, 450), (0x44, 0)): self.setword(win + off, v)
        self.put(UP.FILE, UP.OLD)
        self.u.mem_write(PSYMS['up_own'], UP.cs('1.0.0'))
        self.setword(PSYMS['up_dev'], 0)
        self.confirm_yes = True

    def set_language(self, table):
        super().set_language(table)   # (the mocked lookup compares the key as read_cstr returns it, a key with "…" as latin-1 chars)
        self.strings.update({k.encode('utf-8').decode('latin-1'): v for k, v in list(self.strings.items()) if not k.isascii()})

    def call(self, *a, **k):
        r = super().call(*a, **k)
        self.hist += self.calls
        return r

    def open(self):
        self.calls = []; self.thread = None
        return self.call(PSYMS['update_open'], count=200000000) & 0xffffffff

    def tick(self, n=1):
        for _ in range(n): self.call(PSYMS['up_tick'], a0=0, count=400000000)

    def work(self):
        PCN.work(self, self.thread)
        self.thread = None

    def click(self, name='up_pill'):
        fn_, ctx = self.bound[(self.widgets[name], EVT_CLICK)]
        self.thread = None
        self.call(fn_, a0=ctx, a1=0, count=400000000)

    def fire(self, ev):
        fn_, ctx = self.bound[(self.window, ev)]
        self.call(fn_, a0=ctx, a1=0, count=4000000)

    def text(self, name): return undo(self.wtext.get(self.widgets[name], ''))
    def shown(self, name): return bool(self.props.get((self.widgets[name], 'visible'), 1)) and bool(self.props.get((self.widgets[name], 'sensitive'), 1))
    def at(self, name): return self.props.get((self.widgets[name], 'x')), self.props.get((self.widgets[name], 'y'))
    def glyph(self): return next((c[2] for c in reversed(self.hist) if c[0] == 'image_base_set_image' and c[1] == self.widgets['up_icon']), '')

    def view(self):
        """What the block shows: (glyph or '', title, text, pill text or None, second pill text or None)."""
        return (self.glyph() if self.shown('up_icon') else '', self.text('up_title'), self.text('up_text') if self.shown('up_text') else '',
                self.text('up_pill') if self.shown('up_pill') else None, self.text('up_pill2') if self.shown('up_pill2') else None)

    def pop(self):
        """The popup as it is: None when hidden, else (title, grey line, count line, the bar's width, Cancel takes touches)."""
        if not (self.shown('up_pd_scrim') and self.shown('up_pd_card')): return None
        return (self.text('up_pd_title'), self.text('up_pd_name'), self.text('up_pd_count'), self.props.get((self.widgets['up_pd_fill'], 'w')), self.shown('up_pd_cancel'))

    def installs(self): return [c for c in self.hist if c[0] == 'tf_update_click']
    def navigated(self): return [c[1] for c in self.hist if c[0] == 'navigator_to']
    def confirms(self): return [undo(c[1]) for c in self.hist if c[0] == 'confirm']


def undo(s):
    """A mocked text as the user reads it: UTF-8 bytes read as latin-1 (the payload's own strings come back twice over from the mocked translation)."""
    for _ in range(2):
        try: s = s.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError): break
    return s


def trl(loc, key):
    """The text of key in language loc as the page would put it, with nothing substituted."""
    return key if loc == 'en_US' else pod_i18n.TEXT[key][pod_i18n.table_for(loc)] if key in pod_i18n.TEXT else key


def sub(s, v): return s.replace('%s', v)


def get_offer(m):
    """The page opened, the check run and read: 'Version 1.0.1 available'."""
    m.open(); m.click(); m.work(); m.tick()


def download(m):
    """The Download and Install pill, the dialog answered Yes, the worker run and read."""
    m.click(); m.work(); m.tick(2)


def asset_tests(ctx):
    expect = ctx.expect
    tree = awtk_ui.parse(open(os.path.join(WORK, UI), 'rb').read())
    by = {w.name: w for w in tree.walk() if w.name}
    box = lambda n: (by[n].x, by[n].y, by[n].w, by[n].h)
    expect(tree.type == 'window' and tree.name == 'm1plus_update_page' and tree.get('fullscreen') is None, 'a normal window (450 px, under the status bar) named m1plus_update_page')
    expect(all(n in by for n in NAMES) and 'label_title' in by, 'every widget the payload looks up is there, with the navbar\'s label_title')
    expect(pod_pages.UPDATE in pod_pages.PAGES and pod_pages.UPDATE.key == 'm1plus_update' and os.path.exists(os.path.join(WORK, UI)), 'the page is registered and built')
    expect(box('navigationbar_view') == (0, 0, 320, 50) and by['btn_return'].get('enable') == 'true', 'the stock navbar: 50 px, Back, Now Playing')
    for n in ('up_icon', 'up_text', 'up_pill', 'up_pill2') + POPUP[:2]:
        expect(by[n].get('visible') == 'false' and by[n].get('sensitive') == 'false', f'{n} starts hidden and insensitive (a hidden widget still takes touches)')
    expect(by['up_title'].get('sensitive') == 'false' and by['up_pill'].type == 'button' and by['up_pill2'].type == 'button' and by['up_pill'].get('enable') == 'true' and by['up_icon'].type == 'image'
           and by['up_icon'].get('image') == 'pod_es_download', 'the title is insensitive; the pills are the only buttons of the block; the glyph an image')
    order = [w.name for w in tree.children]
    expect(order.index('navigationbar_view') < order.index('up_icon') < order.index('up_pill2') < order.index('up_pd_scrim') < order.index('up_pd_card') and order[-1] == 'up_pd_card',
           'the block is over the navbar, the popup (scrim, card) over everything')
    expect(box('up_icon')[2:] == (48, 48) and box('up_title')[2:] == (288, 30) and box('up_text')[2:] == (280, 48) and box('up_pill')[2:] == (260, 48) and box('up_pill2')[2:] == (260, 48), 'the parts: 48 px glyph, title 288 x 30, detail 280 x 48, pills 260 x 48')
    expect(by['up_title'].get('style:normal:font_size') == '22' and by['up_title'].get('style:normal:text_color') == '#FFFFFF' and by['up_text'].get('style:normal:font_size') == '18'
           and by['up_text'].get('style:normal:text_color') == '#AAAAAA' and by['up_title'].get('style:normal:text_align_h') == 'center' and by['up_text'].get('style:normal:text_align_h') == 'center'
           and by['up_pill'].get('style:normal:font_size') == '20' and by['up_pill2'].get('style:normal:font_size') == '20', 'the title is white 22 px centred, the detail grey #AAAAAA 18 px centred, the pill text 20 px')
    ys = tuple(box(n)[1] for n in ('up_icon', 'up_title', 'up_text', 'up_pill', 'up_pill2'))
    expect(ys == pod_ui.UP_YS, f'the places are the fixed ones of tools/pod_ui.py UP_YS ({ys})')
    gaps = (ys[1] - ys[0] - 48, ys[2] - ys[1] - 30, ys[3] - ys[2] - 48, ys[4] - ys[3] - 48)
    expect(gaps == (16, 8, 24, 12), f'spacing: glyph, 16, title, 8, detail, 24, pill, 12, second pill ({gaps})')
    top, bottom = ys[0] - 50, 450 - (ys[4] + 48)
    expect(abs(top - bottom) <= 1 and top >= 40, f'the block is centred in the 400 px under the navbar ({top} above, {bottom} below), the same in every state')
    expect(all(box(n)[0] * 2 + box(n)[2] == 320 for n in ('up_icon', 'up_title', 'up_text', 'up_pill', 'up_pill2')), 'every part is centred horizontally')
    # the popup is the Podcasts refresh dialog's: the same scrim and card boxes
    expect(box('up_pd_scrim') == (0, 0, pod_ui.SCREEN_W, pod_ui.CLIENT_H) and box('up_pd_card')[2:] == (O['PD_CARD_W'], O['PD_CARD_H']) and by['up_pd_cancel'].type == 'button' and by['up_pd_scrim'].type == 'button'
           and box('up_pd_cancel')[1] + box('up_pd_cancel')[3] == O['PD_CARD_H'] and all(by[n].get('sensitive') == 'false' for n in POPUP[2:6]),
           'the popup: a full-client scrim that takes every touch (modal) and the refresh dialog\'s card with its Cancel row; its texts and bar insensitive')
    for n in ('up_pd_title', 'up_pd_name', 'up_pd_count'):
        c = by[n].get('style:normal:text_color')
        expect(c.upper() in ('#FFFFFF', '#EBEBEB', '#AAAAAA'), f'{n}: neutral {c} (no accent colour)')
    lum = lambda c: (lambda r, g, b: 0.2126 * r + 0.7152 * g + 0.0722 * b)(*[(lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)(int(c[i:i + 2], 16) / 255) for i in (1, 3, 5)])
    rat = lambda a, b: (max(lum(a), lum(b)) + 0.05) / (min(lum(a), lum(b)) + 0.05)
    for n in ('up_title', 'up_text'):
        c = by[n].get('style:normal:text_color')
        expect(rat(c, '#000000') >= 4.5, f'{n}: {c} on black keeps 4.5:1 ({rat(c, "#000000"):.1f})')
    for pill in ('up_pill', 'up_pill2'):
        for st in ('normal', 'pressed'):
            expect(rat(by[pill].get(f'style:{st}:text_color'), by[pill].get(f'style:{st}:bg_color')) >= 7, f'{pill}: the text keeps 7:1 on its fill ({st})')
        expect(rat(by[pill].get('style:normal:bg_color'), '#000000') < 1.5, f'{pill} is a neutral grey (no accent colour)')
    built = {f[:-4]: dict(__import__('awtk_strings').load(os.path.join(WORK, RAW, 'strings', f))) for f in sorted(os.listdir(os.path.join(WORK, RAW, 'strings')))}
    font = Ttf(os.path.join(WORK, RAW, 'fonts', 'default.ttf'))
    import pod_wrap
    over, long = [], []
    titles = [k for k in KEYS if k in {t for g, t, x, p in FAILS.values()} | {'Checking…', 'Up to Date', 'Update Downloaded', 'Version %s', 'Version %s available'}]
    longest = {'Version %s': 'V2.1zABCDEFGH', 'Version %s available': '10.10.10'}   # (a release number of two digits a part; a longer one is clipped by its label)
    for loc in pod_i18n.LOCALES:
        for key in titles:
            t = sub(built[loc].get(key, key), longest.get(key, ''))
            w = StbText(font, TITLE_PX).layout(t)[1]
            if w > 288: over.append((loc, key, w))
        for key in ('Check for Update', 'Download and Install', 'Try Again', 'Install', 'Check Again'):
            w = StbText(font, PILL_PX).layout(built[loc].get(key, key))[1]
            if w > 220 - 24: over.append((loc, key, w))
        t = sub(built[loc].get('Downloading %s', 'Downloading %s'), '10.0.1')
        if StbText(font, int(by['up_pd_title'].get('style:normal:font_size'))).layout(t)[1] > O['PD_BAR_W']: over.append((loc, 'Downloading %s', 'the popup title'))
        for key in ('Cancelling…', 'This may take a few minutes.'):
            px = int(by['up_pd_count' if key == 'Cancelling…' else 'up_pd_name'].get('style:normal:font_size'))
            if StbText(font, px).layout(built[loc].get(key, key))[1] > O['PD_BAR_W']: over.append((loc, key, 'the popup line'))
        texts = {x for g, t, x, p in FAILS.values() if x} | {'You have the latest version.', 'Current version: %s', 'Version %s is ready to install.'}
        for key in texts:
            t = sub(built[loc].get(key, key), '99999.99999.99999' if '%s' in key else '')
            st = StbText(font, TEXT_PX)
            lines = pod_wrap.wrap(t, [st.layout(c)[1] for c in t], 280, 3, st.layout('…')[1])
            if len(lines) > 2 or lines[-1].endswith('…') and not t.endswith('…'): long.append((loc, key, lines))
        t = sub(built[loc].get(CONFIRM, CONFIRM), '1.10.10')   # the stock confirm dialog's label: 20 px, 236 px wide (260 less the 12 px margins), 80 px high: three lines
        st = StbText(font, 20)
        lines = pod_wrap.wrap(t, [st.layout(c)[1] for c in t], 236, 4, st.layout('…')[1])
        if len(lines) > 3 or any(l.rstrip().endswith(('55', '(55')) or l.lstrip().startswith(('MB', 'Mo', 'МБ', 'MB)', 'Mo)', 'МБ)')) for l in lines): long.append((loc, 'the confirm text', len(lines)))
    expect(not over, f'every title, pill and popup line fits its label in all 13 languages ({over[:30]})')
    expect(not long, f'every explanation wraps to at most two lines of 280 px at 18 px, the confirm text to three at 20 px in 236 px with no break inside "55 MB", in all 13 languages ({long[:30]})')
    for key in ('Cancel', 'Download'):
        expect(max(StbText(font, 20).layout(built[loc][key])[1] for loc in pod_i18n.LOCALES) <= 120, f'the confirm dialog\'s button text "{key}" fits its 128 px button in all 13 languages')
    title_room = by['label_title'].w
    expect(all(StbText(font, 22).layout(built[loc]['Software Update'])[1] <= title_room for loc in pod_i18n.LOCALES), f'the title "Software Update" fits the navbar\'s label ({title_room} px) in all 13 languages')
    rowfont = max(StbText(font, 21).layout(built[loc]['Software Update'])[1] for loc in pod_i18n.LOCALES)
    expect(rowfont <= 187, f'the About row label fits the card row in all 13 languages ({rowfont} px of 187)')
    expect(all(k in pod_i18n.TEXT or k in pod_i18n.STOCK for k in KEYS), 'every key has its 13 translations')
    # the About row: a link right below the version row, none in the System card
    rows = pod_pages.ABOUT_PAGE.rows
    labels = [r.label for r in rows]
    i = labels.index('Software Update')
    expect(labels[i - 1] == 'M1+ Music' and 'Software Update' not in [r.label for r in pod_pages.SETTINGS_PAGE.rows] and rows[i].action == pod_pages.ACT_UPDATE and pod_pages.row_kind(rows[i]) == 'link'
           and 'System Update' in [r.label for r in pod_pages.DEVELOPER_PAGE.rows], 'Settings > System > About: Software Update right below the version row, a link row, none in the System card; Developer > Tools > System Update stays')


def flow_tests(ctx):
    expect = ctx.expect
    pkg = UP.package('1.0.1', extra=bytes(range(256)) * 20)
    site = UP.Site('1.0.1', pkg=pkg)
    m = UM(site)
    r = m.open()
    names = [c[0] for c in m.calls]
    expect(r == 0 and ('window_open', 'm1plus_update') in m.calls and names.count('timer_add') == 1 and [c for c in m.calls if c[0] == 'timer_add'] == [('timer_add', PSYMS['up_tick'], 250)] and not m.thread,
           f'open: the page and one 250 ms timer, no worker yet ({r})')
    expect(all((m.widgets[n], EVT_CLICK) in m.bound for n in ('btn_return', 'btn_backtoplayer', 'up_pill', 'up_pill2', 'up_pd_cancel')) and (m.window, EVT_DESTROY) in m.bound and (m.window, EVT_FG) in m.bound
           and (m.window, EVT_BG) in m.bound and m.bound[(m.widgets['btn_return'], EVT_CLICK)][0] == PSYMS['up_on_back'] and m.bound[(m.widgets['btn_backtoplayer'], EVT_CLICK)][0] == PSYMS['pod_on_player'],
           'Back (the page\'s: under the popup it is Cancel), Now Playing, both pills, the popup\'s Cancel, destroy and the window\'s front/back events are bound')
    expect(any(c == ('label_set_line_wrap', m.widgets['up_text'], 1) for c in m.calls), 'the explanation label wraps its text')
    v = m.view()
    expect(v == ('pod_es_download', 'M1+ Music', f'Version {VERSION}', 'Check for Update', None) and m.pop() is None, f'idle: M1+ Music, the installed version and the Check for Update pill, no popup ({v})')
    m.click()
    expect(m.thread and m.thread[0] == PSYMS['pn_umain'] and m.view() == ('', 'Checking…', '', None, None), f'the pill starts the check; "Checking…", no pill ({m.view()})')
    m.work(); m.tick()
    v = m.view()
    expect(v == ('pod_es_download', 'Version 1.0.1 available', f'Current version: {VERSION}', 'Download and Install', None), f'a newer release: "Version 1.0.1 available", the installed version, Download and Install ({v})')
    n_reqs = len(site.reqs)
    # the confirm dialog, then the popup; watched mid-way by the page's timer
    snaps = []

    def watch(url, sent, total):
        if url.endswith('update.bin') and len(snaps) < 6 and sent in (4000, 8000):
            m.nested(PSYMS['up_tick'], 0); snaps.append((sent, m.pop()))
    site.asset = {'xfer': watch, 'chunk': 4000}
    m.click()
    expect(m.confirms() == [sub(CONFIRM, '1.0.1')] and m.thread and not m.navigated(), f'the pill asks first, in the stock confirm dialog: the version, the size, what it replaces ({m.confirms()})')
    expect(any(c[0] == 'timer_add' and c[1] == PSYMS['up_relabel'] for c in m.hist), 'and a timer relabels the dialog\'s buttons')
    expect(m.pop() == ('Downloading 1.0.1', 'This may take a few minutes.', '0%', 1, True) and m.view()[3:] == (None, None), f'Yes: the popup, "Downloading 1.0.1", 0 %, Cancel; the pill under it is gone ({m.pop()})')
    hist0 = len(m.hist)
    m.work()
    pcts = [int(s[1][2].rstrip('%')) for s in snaps]
    expect(len(snaps) == 2 and pcts == sorted(pcts) and pcts[-1] > 0 and all(s[1][0] == 'Downloading 1.0.1' and s[1][3] == max(1, BAR_W * p // 100) and s[1][4] for s, p in zip(snaps, pcts)),
           f'mid-way the popup reads NN% and its bar follows ({[(s[0], s[1]) for s in snaps]})')
    expect(any(c == ('reset_poweroptions_timer', 1, 1, 0) for c in m.hist[hist0:]) or len(snaps) == 2, 'the timer keeps standby and auto power-off from firing (once a second)')
    m.tick()
    title = m.widgets['up_title']
    expect(m.pop() is None and m.installs() == [] and not m.shown('up_icon') and not m.shown('up_text') and not m.shown('up_pill') and not m.shown('up_pill2') and not m.props.get((title, 'visible'), 1),
           'done with the page in front: the tick that sees it closes the popup and clears the page block (glyph, texts, both pills: not visible, not sensitive); stock\'s dialog is not opened yet, the clear is painted first')
    closed = len(m.hist)
    m.tick()
    pop_hide = [i for i, c in enumerate(m.hist) if c[0] == 'widget_set_visible' and c[1] == m.widgets['up_pd_card'] and c[2] == 0]
    clear = [i for i, c in enumerate(m.hist) if c[0] == 'widget_set_visible' and c[1] == title and c[2] == 0 and pop_hide and i > pop_hide[-1]]
    call = [i for i, c in enumerate(m.hist) if c[0] == 'tf_update_click']
    back = [i for i, c in enumerate(m.hist) if c[0] == 'widget_set_visible' and c[1] == title and c[2] == 1 and call and i > call[0]]
    expect(m.installs() == [('tf_update_click', 0, 0)] and not m.navigated() and pop_hide and clear and call and back and pop_hide[-1] < clear[0] < closed <= call[0] < back[0],
           f'the next tick calls stock\'s TF card update directly (no page opens): popup hidden, block cleared (painted), the call, then the block restored ({pop_hide[-1:]}, {clear[:1]}, {call}, {back[:1]})')
    v = m.view()
    expect(v == ('pod_es_check', 'Update Downloaded', 'Version 1.0.1 is ready to install.', 'Install', 'Check Again'), f'and the page offers Install and Check Again ({v})')
    m.tick(3)
    expect(len(m.installs()) == 1, 'only once')
    m.hist = []
    m.click()
    seq = [('hide' if c[2] == 0 else 'show') if c[0] == 'widget_set_visible' and c[1] == title else 'call' for c in m.hist if c[0] == 'tf_update_click' or (c[0] == 'widget_set_visible' and c[1] == title)]
    expect(len(m.installs()) == 1 and seq == ['hide', 'call', 'show'] and m.view()[3:] == ('Install', 'Check Again'), f'the Install pill: block cleared, stock\'s call, block restored whatever it returns ({seq})')
    expect(m.fs[UP.FILE] == pkg and UP.PART not in m.fs and len(site.reqs) == n_reqs + 1, 'update.bin is the package; one download request, after the check')
    # nothing else touched the stock pages: the TF card update is the handler, not the System Update page
    expect('systemset/fwupdate_page' not in m.navigated(), 'the System Update page is never opened')


def confirm_tests(ctx):
    expect = ctx.expect
    pkg = UP.package('1.0.1')
    site = UP.Site('1.0.1', pkg=pkg)
    m = UM(site); get_offer(m)
    n = len(site.reqs); m.confirm_yes = False
    m.click()
    expect(m.confirms() == [sub(CONFIRM, '1.0.1')] and m.thread is None and len(site.reqs) == n and m.pop() is None and m.view()[1] == 'Version 1.0.1 available' and m.fs[UP.FILE] == UP.OLD,
           'Cancel in the confirm dialog: no worker, no request, no popup, the page as it was, update.bin untouched')
    expect(fn(m, 'pn_up_state') == U['CHECKED'], 'the state is still the offer')
    m.confirm_answer = 4
    m.click()
    expect(m.thread is None and len(site.reqs) == n, 'the dialog\'s Cancel button (4) is the same')
    m.confirm_answer = 0
    m.click()
    expect(m.thread is None and len(site.reqs) == n, 'and the back key / a dialog that fails to open (0)')
    m.confirm_answer = None; m.confirm_yes = True
    m.click(); m.work(); m.tick()
    expect(len(site.reqs) == n + 1 and m.view()[1] == 'Update Downloaded', 'Yes downloads')
    # the dialog's buttons
    m = UM(site); get_offer(m)
    m.wm = 0x2111
    for nm in ('confirminfo_dialog', 'btn_cancel', 'btn_enter'): Machine.widget(m, nm)   # noqa: F821
    m.call(PSYMS['up_relabel'], a0=0, count=100000)
    expect(m.text('btn_cancel') == 'Cancel' and m.text('btn_enter') == 'Download', 'the dialog\'s left button reads Cancel, the right Download')
    m2 = UM(site); get_offer(m2); m2.wm = 0x2111
    rets = [m2.call(PSYMS['up_relabel'], a0=0, count=100000) for _ in range(25)]
    expect(rets[0] == 8 and rets[-1] == 0 and rets.count(8) == 19 and not [c for c in m2.hist if c[0] == 'widget_set_text_utf8' and c[2] in ('Cancel', 'Download')],
           'a dialog that never comes up: the timer looks 20 times, then ends, and touches nothing')
    for loc in pod_i18n.LOCALES:
        m = UM(site); m.set_language(None if loc == 'en_US' else loc); get_offer(m); m.click()
        want = sub(trl(loc, CONFIRM), '1.0.1')
        if m.confirms() != [want]:
            expect(False, f'{loc}: the confirm text reads {want!r} ({m.confirms()})')
            break
    else: expect(True, 'the confirm text in all 13 languages')


def popup_tests(ctx):
    expect = ctx.expect
    pkg = UP.package('1.0.1', extra=bytes(range(256)) * 20)
    site = UP.Site('1.0.1', pkg=pkg)
    m = UM(site); get_offer(m)
    seen = []

    def hook(url, sent, total):
        if url.endswith('update.bin') and sent == 4000 and not seen:
            m.nested(PSYMS['up_on_cancel'], 0, 0)   # the tap on the popup's Cancel, while the transfer runs
            m.nested(PSYMS['up_tick'], 0)
            seen.append(m.pop())
    site.asset = {'xfer': hook, 'chunk': 4000}
    m.click()
    m.work()
    expect(seen and seen[0][2] == 'Cancelling…' and seen[0][4] is False and seen[0][0] == 'Downloading 1.0.1', f'Cancel: the popup says Cancelling… and the button goes dead ({seen})')
    expect(m.pop() == ('Downloading 1.0.1', 'This may take a few minutes.', 'Cancelling…', m.pop()[3], False), 'it stays up while the worker is still alive')
    m.tick()
    v = m.view()
    expect(m.pop() is None and v == ('pod_es_download', 'Download cancelled', '', 'Download and Install', None) and not m.installs() and m.fs[UP.FILE] == UP.OLD and UP.PART not in m.fs and fn(m, 'pn_job_busy') == 0,
           f'once the worker has really stopped the popup closes, the .part is gone, update.bin is the old one, nothing is installed ({v})')
    site.asset = {}
    m.click(); m.work(); m.tick(2)
    expect(m.view()[1] == 'Update Downloaded' and len(m.installs()) == 1, 'Download and Install again, and it completes')
    # Back under the popup is its Cancel; the page is not left
    site2 = UP.Site('1.0.1', pkg=pkg)
    m = UM(site2); get_offer(m)
    seen = []

    def hook2(url, sent, total):
        if url.endswith('update.bin') and sent == 4000 and not seen:
            m.nested(PSYMS['up_on_back'], 0, 0)
            m.nested(PSYMS['up_tick'], 0)
            seen.append((m.pop(), [c for c in m.hist if c[0] == 'navigator_back']))
    site2.asset = {'xfer': hook2, 'chunk': 4000}
    m.click(); m.work(); m.tick()
    expect(seen and seen[0][0][2] == 'Cancelling…' and not seen[0][1] and m.view()[1] == 'Download cancelled' and m.pop() is None, 'Back while the popup is up is Cancel: the page stays, the download ends cancelled')
    m.call(m.bound[(m.widgets['btn_return'], EVT_CLICK)][0], a0=0, a1=0, count=4000000)
    expect(any(c[0] == 'navigator_back' for c in m.calls), 'and with no popup, Back leaves the page')
    # errors close the popup and show on the page
    for code, kw in ((PN['NET'], {'rc': 56, 'partial': True}), (PN['UPBAD'], {'clen': 12345}), (PN['CERT'], {'rc': 60})):
        site3 = UP.Site('1.0.1', pkg=pkg, asset=kw)
        m = UM(site3); get_offer(m); download(m)
        g, t, x, p = FAILS[code]
        expect(m.pop() is None and m.view() == (g, t, x, p, None) and not m.installs() and m.fs[UP.FILE] == UP.OLD, f'a failed download (PN {code}): the popup closes, the page says {t!r} with Try Again')
    # the popup while the slot is taken: Download 0 % and Cancel, and nothing started
    m = UM(UP.Site('1.0.1', pkg=pkg)); get_offer(m)
    fn(m, 'pn_search', m.cstr('jazz')); search = m.thread
    m.click()
    expect(m.pop() == ('Downloading 1.0.1', 'This may take a few minutes.', '0%', 1, True) and m.thread is None, 'a download waiting for the slot already shows its popup, 0 %')
    m.call(PSYMS['up_on_cancel'], a0=0, a1=0, count=4000000)
    expect(m.pop() is None and m.view()[1] == 'Version 1.0.1 available' and m.view()[3] == 'Download and Install', 'its Cancel drops it: the offer again')
    PCN.work(m, search); m.thread = None
    m.tick(2)
    expect(m.thread is None, 'and nothing starts afterwards')
    m.click()
    fn(m, 'pn_search', m.cstr('jazz'))
    m.thread = None


def again_tests(ctx):
    expect = ctx.expect
    first = UP.package('1.0.1', extra=bytes(range(256)) * 8)
    second = UP.package('1.0.1', extra=bytes(range(255, -1, -1)) * 9)   # (the same version, other bytes: a later build of the release)
    site = UP.Site('1.0.1', pkg=first)
    m = UM(site); get_offer(m); download(m)
    expect(m.fs[UP.FILE] == first and len(m.installs()) == 1 and m.view()[3:] == ('Install', 'Check Again'), 'a first download and install call')
    # Check Again: GitHub is asked again; the same version is offered again
    site.pkg = second
    n = len(site.reqs)
    m.click('up_pill2')
    expect(m.thread and m.thread[0] == PSYMS['pn_umain'] and m.view() == ('', 'Checking…', '', None, None), 'Check Again: the check runs ("Checking…")')
    m.work(); m.tick()
    expect(len(site.reqs) == n + 1 and site.reqs[-1][0] == UP.LATEST and m.view() == ('pod_es_download', 'Version 1.0.1 available', f'Current version: {VERSION}', 'Download and Install', None),
           f'GitHub was asked again and the version already downloaded is offered again ({m.view()})')
    expect(m.fs[UP.FILE] == first, 'update.bin is still the first package')
    # a second download that fails keeps the first file
    site.asset = {'rc': 56, 'partial': True}
    m.click(); m.work(); m.tick()
    expect(m.fs[UP.FILE] == first and UP.PART not in m.fs and m.view()[1] == "Can't reach GitHub" and m.pop() is None and len(m.installs()) == 1, 'a second download that fails: the first update.bin stays, the .part is gone, nothing is installed')
    # a second download that is cancelled keeps it too
    site.asset = {'chunk': 1000}
    site.asset['xfer'] = lambda url, sent, total: m.nested(PSYMS['up_on_cancel'], 0, 0) if url.endswith('update.bin') and sent >= 2000 else None
    m.click(); m.work(); m.tick(2)
    expect(m.fs[UP.FILE] == first and UP.PART not in m.fs and m.view()[1] == 'Download cancelled', 'a second download that is cancelled: the first update.bin stays')
    # a second download of a package that is not the version offered keeps it
    site.asset = {}; site.pkg = UP.package('1.0.0')
    m.click(); m.work(); m.tick()
    expect(m.fs[UP.FILE] == first and UP.PART not in m.fs and m.view()[1] == "Download doesn't match", 'a package of another version: refused, the first update.bin stays')
    # it replaces update.bin only through .part -> verify -> rename, and only after the new file is whole
    site.pkg = second
    seen = {}

    def probe(url, sent, total):
        if url.endswith('update.bin') and 'at' not in seen: seen['at'] = (m.fs.get(UP.FILE), UP.PART in m.fs)
    site.asset = {'xfer': probe}
    m.click(); m.work(); m.tick(2)
    expect(seen['at'] == (first, True) and m.fs[UP.FILE] == second and UP.PART not in m.fs, 'while the second one arrives update.bin is the first; when it is whole and verified it replaces it')
    expect(len(m.installs()) == 2 and m.view()[3:] == ('Install', 'Check Again'), 'and the install call follows; Install and Check Again again')
    calls = [c for c in m.hist if c[0] in ('rename', 'unlink', 'fsync')]
    expect(('rename', UP.PART, UP.FILE) in calls, 'through the .part and one rename')
    # Check Again when GitHub has nothing newer: up to date
    m2 = UM(UP.Site('1.0.1', pkg=first)); get_offer(m2); download(m2)
    m2.u.mem_write(PSYMS['up_own'], UP.cs('1.0.1'))
    m2.click('up_pill2'); m2.work(); m2.tick()
    expect(m2.view()[1] == 'Up to Date' and m2.view()[3] == 'Check for Update' and m2.fs[UP.FILE] == first, 'Check Again with nothing newer: Up to Date, the downloaded file stays on the card')
    # Check Again that fails shows its error and Try Again checks
    m3 = UM(UP.Site('1.0.1', pkg=first)); get_offer(m3); download(m3)
    m3.curl_site = UP.Site(latest={'code': 404, 'rc': 22})
    m3.click('up_pill2'); m3.work(); m3.tick()
    expect(m3.view()[1] == "Can't check for updates" and m3.fs[UP.FILE] == first, 'Check Again that fails: the error, update.bin untouched')
    m3.curl_site = UP.Site('1.0.1', pkg=first)
    m3.click(); m3.work(); m3.tick()
    expect(m3.view()[1] == 'Version 1.0.1 available', 'Try Again checks again')
    # a development build is offered the same release again and again
    m4 = UM(UP.Site('1.0.0', pkg=UP.package('1.0.0')), ); m4.setword(PSYMS['up_dev'], 1); get_offer(m4); download(m4)
    m4.click('up_pill2'); m4.work(); m4.tick()
    expect(m4.view()[1] == 'Version 1.0.0 available', 'a development build: Check Again offers release 1.0.0 once more')


def reopen_tests(ctx):
    expect = ctx.expect
    pkg = UP.package('1.0.1')
    site = UP.Site('1.0.1', pkg=pkg)
    m = UM(site); get_offer(m); download(m)
    expect(len(m.installs()) == 1 and m.fs[UP.FILE] == pkg, 'a complete download')
    m.fire(EVT_DESTROY)
    expect(('timer_remove', 0x777) in m.calls, 'destroy removes the timer')
    m.hist = []
    m.open()
    expect(m.view() == ('pod_es_check', 'Update Downloaded', 'Version 1.0.1 is ready to install.', 'Install', 'Check Again') and not m.installs(), f'opened again: still "Update Downloaded" with Install and Check Again, nothing starts by itself ({m.view()})')
    m.fire(EVT_DESTROY)
    m.fs.pop(UP.FILE)
    m.open()
    expect(m.view()[2] == f'Version {VERSION}' and m.view()[3] == 'Check for Update', 'update.bin gone from the card: the state is forgotten')
    for what, site2, want in (('up to date', UP.Site('1.0.0'), 'Up to Date'), ('a failure', UP.Site(latest={'code': 404, 'rc': 22}), "Can't check for updates"), ('an offer', UP.Site('1.0.1'), 'Version 1.0.1 available')):
        m = UM(site2); get_offer(m)
        expect(m.view()[1] == want, f'{what}: {want}')
        m.fire(EVT_DESTROY); m.open()
        expect(m.view()[2] == f'Version {VERSION}' and m.view()[3] == 'Check for Update', f'{what}: opened again, the page starts from the installed version')
    # a job left running by the page that was closed: the next page's popup says it is stopping
    m = UM(UP.Site('1.0.1', pkg=pkg)); get_offer(m); m.click()
    m.fire(EVT_DESTROY)
    th = m.thread
    expect(th is not None and fn(m, 'pn_job_busy') == 1, 'destroy during a download leaves the worker to end by itself (cancelled)')
    m.open()
    expect(m.pop() == ('Downloading 1.0.1', 'This may take a few minutes.', 'Cancelling…', 1, False), f'a page opened while the old job is still ending shows the popup, Cancelling… ({m.pop()})')
    PCN.work(m, th); m.tick()
    expect(m.pop() is None and m.view()[1] == 'Download cancelled' and m.fs[UP.FILE] == UP.OLD and UP.PART not in m.fs, f'and the page says "Download cancelled" once it has ({m.view()})')


def background_tests(ctx):
    expect = ctx.expect
    pkg = UP.package('1.0.1')
    site = UP.Site('1.0.1', pkg=pkg)
    m = UM(site); get_offer(m); m.fire(EVT_BG)
    download(m)
    expect(not m.installs() and m.view()[1] == 'Update Downloaded' and m.pop() is None, 'a download that ends while another window is in front installs nothing; the page says it')
    m.fire(EVT_FG); m.tick()
    expect(not m.installs(), 'and coming back does not start it either (the Install pill does)')
    m.click()
    expect(len(m.installs()) == 1, 'Install calls stock\'s TF card update')
    # the modal call: the timer does nothing under it, the pills are dead
    m = UM(site); get_offer(m)
    m.call(PSYMS['up_tick'], a0=0, count=400000000)
    expect(m.call(PSYMS['up_tick'], a0=0, count=400000000) == 8, 'the page\'s timer repeats')


def fail_tests(ctx):
    expect = ctx.expect
    pkg = UP.package('1.0.1')
    cases = {   # code: (a Site for the check, machine options)
        PN['NOWIFI']: ({}, {'wifi': -1}), PN['NOCLOCK']: ({}, {'wall': 1700000000}), PN['NOCERT']: ({}, {'present': set()}), PN['CERT']: ({'latest': {'rc': 60, 'code': 0}}, {}),
        PN['UPCHECK']: ({'latest': {'code': 200}}, {}), PN['NET']: ({'latest': {'rc': 6, 'code': 0}}, {}), PN['STORAGE']: ({}, {'card_mounted': False}),
    }
    for code, (kw, opt) in cases.items():
        for loc in pod_i18n.LOCALES:
            m = UM(UP.Site('1.0.1', pkg=pkg, **kw), **opt); m.set_language(None if loc == 'en_US' else loc); m.open(); m.click()
            if m.thread: m.work()
            m.tick()
            glyph, title, text, pill = FAILS[code]
            want = (glyph, trl(loc, title), trl(loc, text), trl(loc, pill) if pill else None, None)
            got = m.view()
            ok = got == want
            if not ok or loc == 'en_US': expect(ok, f'PN {code} ({loc}): {want[:3]}, pill {want[3]} ({got})')
            if not ok: break
        else: expect(True, f'PN {code}: the same block in all 13 languages')
    # a failure of the download: each has its words, and Try Again downloads again (without asking again)
    for code, (site_kw, opt) in {PN['UPBAD']: ({'pkg': UP.package('1.0.0')}, {}), PN['NET']: ({'asset': {'rc': 56, 'partial': True}}, {}), PN['CERT']: ({'asset': {'rc': 60}}, {}),
                                 PN['STORAGE']: ({}, {'fail': {('rename', UP.FILE)}})}.items():
        site = UP.Site('1.0.1', **{'pkg': pkg, **site_kw})
        m = UM(site, **opt); get_offer(m); download(m)
        glyph, title, text, pill = FAILS[code]
        expect(m.view() == (glyph, title, text, pill, None) and m.pop() is None and m.fs[UP.FILE] == UP.OLD and UP.PART not in m.fs, f'a failed download (PN {code}): {title!r}, the popup closed, the old update.bin kept ({m.view()})')
        site.asset = {}; site.pkg = pkg; m.fail = set()
        n = len(m.confirms())
        m.click(); m.work(); m.tick()
        expect(m.view()[1] == 'Update Downloaded' and m.fs[UP.FILE] == pkg and len(m.confirms()) == n, f'PN {code}: Try Again downloads again and succeeds, without asking again')
    # the card is too full for the package
    m = UM(UP.Site('1.0.1', pkg=pkg)); get_offer(m); m.free_mb = 109; m.click(); m.tick()
    expect(m.view() == (FAILS[PN['CARDFULL']][0], 'Card is full', 'Free at least 110 MB on the card.', 'Try Again', None) and not m.thread and m.pop() is None and m.fs[UP.FILE] == UP.OLD,
           f'under 110 MB free: "Card is full", no popup left, nothing started, nothing touched ({m.view()})')
    m.free_mb = 4096; m.click()
    expect(m.thread is not None, 'and Try Again starts it once there is room')
    m.work(); m.tick()
    # Wi-Fi lost between the check and the download: Try Again after it is back
    m = UM(UP.Site('1.0.1', pkg=pkg)); get_offer(m); m.wifi = -1; m.click(); m.tick()
    expect(m.view()[1] == 'Connect to Wi-Fi first' and m.view()[3] == 'Try Again' and not m.thread and m.pop() is None, 'Wi-Fi lost before the download: "Connect to Wi-Fi first", no popup')
    m.wifi = 4; m.click(); m.work(); m.tick()
    expect(m.view()[1] == 'Update Downloaded', 'Try Again after the Wi-Fi is back repeats the download, not the check')
    # a failed check: Try Again checks
    m = UM(UP.Site(latest={'code': 404, 'rc': 22})); get_offer(m); m.curl_site = UP.Site('1.0.1', pkg=pkg)
    m.click(); m.work(); m.tick()
    expect(m.view()[1] == 'Version 1.0.1 available', 'Try Again after a failed check checks again')


def state_tests(ctx):
    expect = ctx.expect
    pkg = UP.package('1.0.1')
    for loc in pod_i18n.LOCALES:
        m = UM(UP.Site('1.0.1', pkg=pkg)); m.set_language(None if loc == 'en_US' else loc); m.open()
        seq = [('idle', m.view(), ('pod_es_download', 'M1+ Music', sub(trl(loc, 'Version %s'), VERSION), trl(loc, 'Check for Update'), None))]
        m.click(); seq.append(('checking', m.view(), ('', trl(loc, 'Checking…'), '', None, None)))
        m.work(); m.tick()
        seq.append(('available', m.view(), ('pod_es_download', sub(trl(loc, 'Version %s available'), '1.0.1'), sub(trl(loc, 'Current version: %s'), VERSION), trl(loc, 'Download and Install'), None)))
        m.click()
        seq.append(('popup', m.pop(), (sub(trl(loc, 'Downloading %s'), '1.0.1'), trl(loc, 'This may take a few minutes.'), '0%', 1, True)))
        m.fire(EVT_BG); m.work(); m.tick()
        seq.append(('downloaded', m.view(), ('pod_es_check', trl(loc, 'Update Downloaded'), sub(trl(loc, 'Version %s is ready to install.'), '1.0.1'), trl(loc, 'Install'), trl(loc, 'Check Again'))))
        m2 = UM(UP.Site('1.0.0')); m2.set_language(None if loc == 'en_US' else loc); m2.open(); m2.click(); m2.work(); m2.tick()
        seq.append(('current', m2.view(), ('pod_es_check', trl(loc, 'Up to Date'), trl(loc, 'You have the latest version.'), trl(loc, 'Check for Update'), None)))
        bad = [(n, g, w) for n, g, w in seq if g != w]
        if bad or loc == 'en_US': expect(not bad, f'{loc}: every state reads as designed ({bad[:1]})')
        if bad: break
    else: expect(True, 'idle, checking, available, the popup, downloaded and up to date: the same in all 13 languages')


def wait_tests(ctx):
    expect = ctx.expect
    pkg = UP.package('1.0.1')
    m = UM(UP.Site('1.0.1', pkg=pkg))
    m.open()
    # a search holds the job slot: the pill waits for it and the tick starts the check
    m.thread = None
    expect(fn(m, 'pn_search', m.cstr('jazz')) == 0, 'a podcast search holds the slot')
    search = m.thread
    m.click()
    expect(m.thread is None and m.view() == ('', 'Checking…', '', None, None), 'the check waits (title Checking…, no worker yet)')
    m.tick(2)
    expect(m.thread is None, 'and keeps waiting while the slot is taken')
    PCN.work(m, search)
    m.thread = None
    m.tick()
    expect(m.thread and m.thread[0] == PSYMS['pn_umain'], 'the tick starts the check once the slot is free')
    m.work(); m.tick()
    expect(m.view()[1] == 'Version 1.0.1 available', 'and it completes')


def life_tests(ctx):
    expect = ctx.expect
    pkg = UP.package('1.0.1')
    # awake: the power countdowns are set again only while a job runs
    m = UM(UP.Site('1.0.1', pkg=pkg)); m.open()
    m.tick(8)
    expect(not [c for c in m.hist if c[0] == 'reset_poweroptions_timer'], 'idle: the power timers are left alone')
    m.click()
    m.tick(8)
    awake = [c for c in m.hist if c[0] == 'reset_poweroptions_timer']
    expect(awake and set(awake) == {('reset_poweroptions_timer', 1, 1, 0)} and len(awake) == 2, f'a running job: standby and auto power-off set again every fourth tick (1 s), the screen\'s light left alone ({len(awake)})')
    m.work(); m.hist = []
    m.tick(8)
    expect(not [c for c in m.hist if c[0] == 'reset_poweroptions_timer'], 'and not once it has ended')
    # destroy during a check cancels the worker
    m = UM(UP.Site('1.0.1', pkg=pkg)); m.open(); m.click()
    m.fire(EVT_DESTROY)
    gone = ('timer_remove', 0x777) in m.calls
    expect(fn(m, 'pn_job_busy') == 1 and gone, 'destroy: the timer goes, the running worker is asked to stop')
    m.work()
    expect(fn(m, 'pn_up_state') == U['IDLE'] and fn(m, 'pn_job_busy') == 0, 'and it ends without a trace (a cancelled check is idle)')
    # a second open, no timer, a wrong asset
    m = UM(UP.Site()); m.open()
    m.calls = []
    expect(m.call(PSYMS['update_open'], count=1000000) == 0 and not [c for c in m.calls if c[0] == 'window_open'], 'a second open while the page is up does nothing (0)')
    m = UM(UP.Site(), window=0)
    expect(m.open() == 0xffffffff, 'a window that will not open: -1')
    m = UM(UP.Site(), timer_fail=True)
    r = m.open()
    expect(r == 0xffffffff and ('navigator_back',) in m.hist, 'no timer: the page closes again, -1')
    m = UM(UP.Site()); del m.widgets['up_pd_fill']
    r = m.open()
    expect(r == 0xffffffff and ('navigator_back',) in m.hist, 'an asset without a widget the payload needs: -1, the page closes again')
    # the About row opens it
    m = UM(UP.Site())
    i = next(i for i, r in enumerate(pod_pages.ABOUT_PAGE.rows) if r.action == pod_pages.ACT_UPDATE)
    m.calls = []
    m.call(PSYMS['on_row'], a0=PSYMS['pod_rows_%d' % pod_pages.ABOUT_PAGE_INDEX] + 12 * i, count=3000000)
    expect(('window_open', 'm1plus_update') in m.calls, 'the About row opens the page')


RWIN = 0x24500000
RN_NAMES = ('rn_scrollview', 'rn_view', 'label_head', 'label_line')
RN_UI = os.path.join(RAW, 'ui', 'm1plus_relnotes.bin')
RELEASE = open(UP.RELEASE_JSON, 'rb').read()


def with_notes(tag='1.0.1', notes=RELEASE, **kw):
    """An update page that has found Version <tag> and, when notes is not None, its release JSON."""
    m = UM(UP.Site(tag, notes=notes), **kw)
    get_offer(m)
    return m


def notes_page(m):
    """The Release Notes pill pressed: the notes page's window and widgets, ready to be painted and scrolled."""
    m.windows['m1plus_relnotes'] = RWIN
    for n in RN_NAMES: Machine.widget(m, n)   # noqa: F821
    m.sv = m.alloc(0x100)
    m.widgets['rn_scrollview'] = m.sv
    m.rview = m.widgets['rn_view']
    m.canvas = m.alloc(0x80)
    m.hist = []
    m.click('up_pill2')
    return m


def rn_paint(m, off=0):
    m.setword(m.sv + 0x84, off)
    ev = m.alloc(0x40); m.u.mem_write(ev, bytes(0x40)); m.setword(ev + O['EVENT_PAINT_CANVAS'], m.canvas)
    m.texts, m.text_styles = [], []
    fn_, ctx = m.bound[(m.rview, O['EVT_AFTER_PAINT'])]
    m.call(fn_, a0=ctx, a1=ev, count=40000000)
    return list(zip(m.text_styles, [t for t, r in m.texts], [r for t, r in m.texts]))


def notes_asset_tests(ctx):
    expect = ctx.expect
    tree = awtk_ui.parse(open(os.path.join(WORK, RN_UI), 'rb').read())
    by = {w.name: w for w in tree.walk() if w.name}
    expect(pod_pages.RELNOTES in pod_pages.PAGES and pod_pages.RELNOTES.key == 'm1plus_relnotes' and tree.type == 'window' and tree.name == 'm1plus_relnotes_page', 'the page is registered and built: a normal window')
    expect(all(n in by for n in RN_NAMES + ('btn_return', 'btn_backtoplayer', 'label_title', 'navigationbar_view')), 'every widget the payload looks up is there, with the stock navbar (Back, Now Playing)')
    expect(by['navigationbar_view'].h == 50 and by['rn_listview'].y == 50 and by['rn_listview'].h == 400 and by['rn_listview'].type == 'list_view' and by['rn_scrollview'].type == 'scroll_view'
           and by['rn_view'].type == 'view' and by['scroll_bar_m'].type == 'scroll_bar_m' and by['rn_view'].w == 320, 'a stock list (list_view > scroll_view + scroll bar) of 400 px under the navbar holding one content view')
    expect(by['rn_listview'].get('style:normal:bg_color') == '#000000' and tree.get('style:normal:bg_color') == '#000000' and by['rn_view'].get('style:normal:bg_color') == '#000000', 'black')
    expect(by['label_head'].get('visible') == 'false' and by['label_line'].get('visible') == 'false' and by['label_head'].get('style:normal:font_size') == '22' and by['label_line'].get('style:normal:font_size') == '18'
           and by['label_head'].get('style:normal:text_color') == '#FFFFFF' and by['label_line'].get('style:normal:text_color') in ('#E6E6E6', '#FFFFFF'), 'the two text styles: a 22 px white heading, 18 px light grey text (no accent colour)')
    colours = {w.get(k) for w in tree.walk() for k in ('style:normal:text_color', 'style:normal:bg_color') if w.get(k)}
    expect(all(c[1:3] == c[3:5] == c[5:7] for c in colours if len(c) == 7), f'every colour of the page is neutral grey ({sorted(colours)})')
    built = {f[:-4]: dict(__import__('awtk_strings').load(os.path.join(WORK, RAW, 'strings', f))) for f in sorted(os.listdir(os.path.join(WORK, RAW, 'strings')))}
    font = Ttf(os.path.join(WORK, RAW, 'fonts', 'default.ttf'))
    bad = []
    for loc in pod_i18n.LOCALES:
        key = built[loc].get('Release Notes', 'Release Notes')
        if StbText(font, PILL_PX).layout(key)[1] > 220 - 24: bad.append((loc, 'the pill', key))
        if StbText(font, 22).layout(key)[1] > by['label_title'].w: bad.append((loc, 'the navbar title', key))
        head = sub(built[loc].get('Version %s', 'Version %s'), '10.10.10')
        if StbText(font, 22).layout(head)[1] > 288: bad.append((loc, 'the heading', head))
    expect('Release Notes' in pod_i18n.TEXT and not bad, f'"Release Notes" has its 13 translations; the pill, the navbar title and the heading fit in all of them ({bad[:6]})')


def notes_flow_tests(ctx):
    expect = ctx.expect
    # the pill only when the check kept notes
    m = with_notes()
    v = m.view()
    expect(v == ('pod_es_download', 'Version 1.0.1 available', f'Current version: {VERSION}', 'Download and Install', 'Release Notes'), f'an offer with notes: Download and Install and, below it, Release Notes ({v})')
    for what, notes in (('a 404', None), ('a 403', {'code': 403, 'rc': 22}), ('a null body', b'{"body":null}'), ('an empty body', b'{"body":""}'), ('truncated JSON', RELEASE[:2000]), ('bad JSON', b'nope')):
        m = with_notes(notes=notes)
        expect(m.view() == ('pod_es_download', 'Version 1.0.1 available', f'Current version: {VERSION}', 'Download and Install', None), f'{what}: the offer without the pill')
        m.click(); m.work(); m.tick(2)
        expect(m.view()[1] == 'Update Downloaded', f'{what}: and the download still works')
    m = UM(UP.Site('1.0.0', notes=RELEASE)); get_offer(m)
    expect(m.view()[1] == 'Up to Date' and m.view()[4] is None, 'Up to Date: no pill, and nothing was asked')
    m = with_notes()
    m.click(); m.work(); m.tick(2)
    expect(m.view()[4] == 'Check Again', 'Update Downloaded keeps its own second pill (Check Again)')
    m = with_notes()
    m.click()
    expect(m.pop() is not None and not m.shown('up_pill2'), 'under the download popup the pill is hidden')
    # a new check clears the old notes and the pill
    m = with_notes()
    m.curl_site = UP.Site('1.0.1', notes=None)
    m.click('up_pill'); m.hist = []
    m.fire(EVT_DESTROY)
    m = UM(UP.Site('1.0.1', notes=RELEASE)); m.open(); m.click(); m.work(); m.tick()
    expect(m.view()[4] == 'Release Notes', 'the first check kept notes')
    m.curl_site = UP.Site('1.0.1', notes=None)
    m.fire(EVT_DESTROY); m.open(); m.click(); m.work(); m.tick()
    expect(m.view()[4] is None, 'the next check (notes failed) shows no pill: the old notes are gone')
    # the pill opens the page
    m = notes_page(with_notes())
    names = [c[0] for c in m.hist]
    expect(('window_open', 'm1plus_relnotes') in m.hist and 'pthread_create' not in names and 'timer_add' not in names, 'the pill opens the notes page: no thread, no timer, no request')
    expect(m.bound[(m.widgets['btn_return'], EVT_CLICK)][0] == PSYMS['pod_on_back'] and m.bound[(m.widgets['btn_backtoplayer'], EVT_CLICK)][0] == PSYMS['pod_on_player'], 'Back goes back, Now Playing is the update page\'s own handler')
    expect(len(m.curl_site.nreqs) == 1, 'the notes come from the check, nothing more is fetched')
    texts = rn_paint(m)
    head = [t for t in texts if t[0] == 'label_head']
    expect(head == [('label_head', 'Version 1.0.1', (16, 12, 288, 30))], f'the heading "Version 1.0.1" at the top ({head})')
    lines = [t for t in texts if t[0] == 'label_line']
    expect(lines and all(r[0] == 16 and r[2] == 288 and r[3] == 24 for _, _, r in lines) and all(r[1] >= 0 and r[1] + r[3] <= 400 for _, _, r in texts) and lines[0][1].startswith('The first release of M1+'),
           f'the notes below it, 288 px wide lines, every one wholly inside the 400 px view ({len(lines)} lines)')
    ys = [r[1] for _, _, r in lines]
    expect(ys[0] == 12 + 30 + 12 and all(b - a in (24, 36) for a, b in zip(ys, ys[1:])), f'24 px between lines, 36 where the notes have a blank line ({ys[:6]})')
    expect(all(len(t) <= 36 for _, t, _ in lines), 'wrapped at the 288 px width (36 characters of the mocked font)')
    h = [c for c in m.hist if c[0] == 'widget_resize' and c[1] == m.rview]
    vh = [c for c in m.hist if c[0] == 'widget_set_prop_int' and c[1] == m.sv and c[2] == 'virtual_h']
    expect(h and vh and h[-1][3] == vh[-1][3] > 400 and h[-1][2] == 320, f'the content view is as tall as the text ({h[-1][3] if h else None} px): the stock scroll view scrolls it')
    # Back returns to the update page in the same state; the page's state is untouched
    before = m.view()
    m.hist = []
    m.click('btn_return')
    expect(('navigator_back',) in m.hist and m.view() == before and m.shown('up_pill2') and m.text('up_pill2') == 'Release Notes', 'Back: the update page again, still offering the release with both pills')
    m.fire(EVT_DESTROY)   # (the notes window's own destroy is bound on its window)
    # the window's destroy frees it: a second open works
    m = with_notes()
    notes_page(m)
    fn_, ctx_ = m.bound[(RWIN, EVT_DESTROY)]
    m.call(fn_, a0=ctx_, a1=0, count=1000000)
    m.hist = []
    m.click('up_pill2')
    expect(('window_open', 'm1plus_relnotes') in m.hist, 'after the page was destroyed the pill opens it again')
    m.call(PSYMS['relnotes_open'], count=1000000)
    expect(m.hist.count(('window_open', 'm1plus_relnotes')) == 1, 'a second open while it is up does nothing')
    # no notes: the entry point refuses (the pill would not be there)
    m = UM(UP.Site('1.0.1', notes=None)); get_offer(m); m.hist = []
    expect(m.call(PSYMS['relnotes_open'], count=1000000) == 0xffffffff and ('window_open', 'm1plus_relnotes') not in m.hist, 'no notes: -1 and no window')
    # a window that will not open, an asset without the scroll view
    m = with_notes(); m.windows['m1plus_relnotes'] = 0; m.hist = []
    m.click('up_pill2')
    expect(('window_open', 'm1plus_relnotes') in m.hist and m.view()[4] == 'Release Notes' and ('navigator_back',) not in m.hist, 'a window that will not open: nothing happens, the update page stays')
    m = with_notes(); m.windows['m1plus_relnotes'] = RWIN
    for n in RN_NAMES[1:]: Machine.widget(m, n)   # noqa: F821
    m.hist = []
    m.click('up_pill2')
    expect(('navigator_back',) in m.hist, 'an asset without a widget the payload needs: the page goes again')


def notes_scroll_tests(ctx):
    expect = ctx.expect
    long = '# Release\n\n' + '\n\n'.join(f'- item {i}: ' + 'word ' * 12 for i in range(40)) + '\n\nTHE END'
    doc = UP.json.dumps({'author': {'body': 'no'}, 'body': long}).encode()
    m = notes_page(with_notes(notes=doc))
    seen = {}
    texts = rn_paint(m)
    first = [t for _, t, _ in texts]
    expect(first[0] == 'Version 1.0.1' and first[1] == 'Release' and len(texts) <= 17, f'the top: the heading and the first lines only ({len(texts)} texts)')
    h = [c for c in m.hist if c[0] == 'widget_resize' and c[1] == m.rview][-1][3]
    expect(h > 2000, f'a long text is a tall content view ({h} px)')
    for off in list(range(0, h - 400, 37)) + [h - 400]:
        for _, t, r in rn_paint(m, off):
            seen[t] = seen.get(t, 0) + 1
            if not (0 <= r[1] and r[1] + r[3] <= 400): expect(False, f'a text outside the view at offset {off}: {r}')
    expect('THE END' in seen and any(t.startswith('• item 0:') for t in seen) and any(t.startswith('• item 39:') for t in seen) and any(t.startswith('word word') for t in seen), f'scrolling the whole way shows the first item, the last item and THE END ({sorted(seen)[:5]}, {len(seen)})')
    last = rn_paint(m, h - 400)
    expect(last[-1][1] == 'THE END' and last[-1][2][1] + last[-1][2][3] <= 400 and 'Version 1.0.1' not in [t for _, t, _ in last], 'at the bottom the last line is in view, the heading has scrolled away')
    mid = [t for _, t, _ in rn_paint(m, 1000)]
    expect(mid and mid[0] != 'Version 1.0.1' and not any('item 0:' in t for t in mid), 'in the middle other lines are painted')
    # a CJK line wraps between characters and a word wider than the view anywhere
    cjk = '示例发行说明' * 30
    m = notes_page(with_notes(notes=UP.json.dumps({'body': cjk + '\n' + 'x' * 100}).encode()))
    t = [(t, r) for s, t, r in rn_paint(m) if s == 'label_line']
    expect(''.join(x for x, _ in t[:-3]) + ''.join(x for x, _ in t[-3:]) == cjk + 'x' * 100 or ''.join(x for x, _ in t) == cjk + 'x' * 100, f'CJK and an unbroken word wrap without losing a character ({len(t)} lines)')
    expect(all(len(x) <= 36 for x, _ in t), 'and no line is wider than 288 px (the mocked font is 8 px a character)')
    # the cap: 8 KB of notes fit in the tables (the last line is reachable)
    body = '\n'.join(f'line {i} ' + 'x' * 20 for i in range(2000))
    m = notes_page(with_notes(notes=UP.json.dumps({'body': body}).encode()))
    h = [c for c in m.hist if c[0] == 'widget_resize' and c[1] == m.rview][-1][3]
    last = rn_paint(m, h - 400)
    expect(last and last[-1][1].startswith('line ') and h > 4000, f'the largest notes (8 KB) still scroll to their end ({last[-1][1] if last else None})')


def notes_lang_tests(ctx):
    expect = ctx.expect
    for loc in pod_i18n.LOCALES:
        m = UM(UP.Site('1.0.1', notes=RELEASE)); m.set_language(None if loc == 'en_US' else loc)
        get_offer(m)
        ok = m.view()[4] == trl(loc, 'Release Notes')
        notes_page(m)
        head = [t for s, t, _ in rn_paint(m) if s == 'label_head']
        ok = ok and head == [sub(trl(loc, 'Version %s'), '1.0.1')]
        if not ok or loc == 'en_US': expect(ok, f'{loc}: the pill reads {trl(loc, "Release Notes")} and the heading {sub(trl(loc, "Version %s"), "1.0.1")} ({m.view()[4]!r}, {head})')
        if not ok: break
    else: expect(True, 'the pill and the heading are translated in all 13 languages (the notes text itself is shown as it is)')


SECTIONS = [asset_tests, flow_tests, confirm_tests, popup_tests, again_tests, reopen_tests, background_tests, fail_tests, state_tests, wait_tests, life_tests, notes_asset_tests, notes_flow_tests, notes_scroll_tests, notes_lang_tests]   # tools/check.py runs each as its own task


def run(ctx):
    for section in SECTIONS: section(ctx)
