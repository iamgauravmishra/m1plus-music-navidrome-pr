"""The entry hook and the M1+ Pod menu: the Home icon dispatcher, the kill switch, the row actions, hit tests on the menu."""
import os
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)


def run(ctx):
    expect, page = ctx.expect, ctx.page
    entry = PSYMS['m1pod_home_click']
    binds = 3 + len(page.rows)                  # btn_return, btn_backtoplayer, each row, and the foreground handler that arranges the menu again
    # 1. Entry icon, kill switch absent: opens the entry page, binds its widgets, no stock.
    m = Machine()
    m.widgets = {n: 0x30000000 + i for i, n in enumerate(
        ['btn_return', 'btn_backtoplayer', 'label_info'] + [f'pod_row{i}' for i in range(len(page.rows))])}
    v = m.call(entry, a0=m.icon(str(pod_pages.HOME_ENTRY)))
    names = m.names()
    expect(('window_open', page.key) in m.calls, f'entry opens {page.key}')
    expect('stock_resume' not in names, 'entry does not fall through to stock')
    expect(names.count('widget_on') == binds, f'binds navbar + {len(page.rows)} rows + the foreground handler (got {names.count("widget_on")})')
    expect('widget_set_text_utf8' not in names, 'the menu sets no info text')
    expect(v == 0, 'entry returns 0 (handled)')

    # 2. Non-entry icons: straight to stock through the trampoline, no page opened. id 0 is the
    #    HiFi store (Simplified Chinese only) and must no longer trigger M1+ Pod.
    for other in ('5', '0'):
        if other == str(pod_pages.HOME_ENTRY): continue
        m = Machine()
        m.call(entry, a0=m.icon(other))
        expect(('stock_resume', other) in m.calls, f'non-entry id {other} falls through to stock')
        expect('window_open' not in m.names(), f'non-entry id {other} opens no page')

    # 3. Kill switch present: entry icon falls through to stock.
    m = Machine(); m.present = {'/mnt/mmc/m1pod-off'}
    m.call(entry, a0=m.icon(str(pod_pages.HOME_ENTRY)))
    expect('stock_resume' in m.names(), 'kill switch -> stock')
    expect('window_open' not in m.names(), 'kill switch opens no page')

    # 4. window_open fails: entry icon falls through to stock.
    m = Machine(); m.window = 0
    m.call(entry, a0=m.icon(str(pod_pages.HOME_ENTRY)))
    expect(('window_open', page.key) in m.calls, 'page open attempted')
    expect('stock_resume' in m.names(), 'open failure -> stock')

    # 5. Empty / null name: no crash, straight to stock.
    m = Machine(); m.call(entry, a0=m.icon(''))
    expect('window_open' not in m.names(), 'empty name opens no page')
    m = Machine(); m.call(entry, a0=0)
    expect('window_open' not in m.names() and 'stock_resume' in m.names(), 'null icon falls through to stock')

    # 6. A menu row: ACT_HOME row opens the stock destination via the trampoline with its id.
    on_row = PSYMS['on_row']; rows0 = PSYMS['pod_rows_0']
    by_action = {}
    for i, r in enumerate(page.rows): by_action.setdefault(r.action, i)
    songs = next(i for i, r in enumerate(page.rows)
                 if r.action == pod_pages.ACT_HOME and r.arg == pod_pages.HOME_MYMUSIC)
    m = Machine()
    m.call(on_row, a0=rows0 + 12 * songs)
    expect(('stock_resume', str(pod_pages.HOME_MYMUSIC)) in m.calls, 'Songs row opens its Home id')
    m = Machine()
    m.call(on_row, a0=rows0 + 12 * by_action[pod_pages.ACT_PLAYER])
    expect('on_backtoplayer_onclick' in m.names(), 'Now Playing row calls the player')

    # 7. The menu: every row is hit by a touch on it, through the list_view/scroll_view.
    m = Machine()
    menu = asset_tree(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1pod_menu.bin'))
    sv = node(menu, 'pod_scrollview')
    rows = [c for c in sv.children if c.name.startswith('pod_row')] if sv else []   # (the menu also has the spacer row pod_pad, patch/minibar.c)
    lv = node(menu, 'pod_listview')
    visible = [r for r in rows if 50 + r.y + r.h // 2 < CLIENT_H]
    for i, r in enumerate(visible):
      for x in (160, 32):     # 32: on the row icon, when it has one (insensitive: the touch goes to the row)
        got = stock_target(m, menu, x, 50 + r.y + r.h // 2)
        expect(f'pod_row{i}' in got and 'pod_scrollview' in got and 'pod_icon' not in got,
               f'menu row {i} is hit through the scroll view ({got})')
    expect(len(rows) == len(page.rows), 'every menu row is in the scroll view')
    expect(lv and lv.y + lv.h == CLIENT_H, f'the menu list ends at the window bottom (450), not off-screen')
    content = max(r.y + r.h for r in rows)
    expect(content > sv.h and len(visible) < len(rows),
           f'{len(rows)} 52 px rows ({content} px) overflow the 400 px list, so it scrolls')
    expect(node(menu, 'scroll_bar_m') is not None, 'the stock scroll bar is there when the list scrolls')

    # 8. Extras (iPod style): one menu row before Settings opens a page of the stock Home tiles the menu does not
    #    repeat. Each row opens its stock destination through the dispatcher with its Home id, as Songs does.
    P = pod_pages
    labels = [r.label for r in page.rows]
    expect(labels[-2:] == ['Extras', 'Settings'] and labels.index('Artists') < labels.index('Extras'),
           'the menu ends with Extras, Settings; the library rows come first')
    ex_i = labels.index('Extras')
    ex = P.EXTRAS_PAGE
    n_items = 9    # the menu items proper; the nine stock Home tiles follow them among the items
    expect(len(P.ITEMS) == 18 and len(page.rows) == 20 and ex_i == 18 and not any(r.label == 'Screenshot' for r in P.ITEMS),
           'eighteen items (nine menu items, nine stock tiles; no Screenshot), then Extras and Settings')
    expect(page.rows[ex_i].action == P.ACT_PAGE and P.PAGES[page.rows[ex_i].arg] is ex, 'the Extras row opens the Extras page')
    want = [('Favorites', 10), ('Recently Added', 13), ('Recently Played', 12), ('Most Played', 11), ('Composers', 8),
            ('Hi-Res', 9), ('Update Library', 2), ('Tidal', 1), ('CD Ripper', 15)]
    stock = ex.rows[n_items:]
    expect([(r.label, r.arg) for r in stock] == want and all(r.action == P.ACT_HOME for r in stock),
           'the items after the menu\'s own nine are the nine stock Home tiles by id')
    expect([(r.label, r.action, r.arg) for r in ex.rows] == [(r.label, r.action, r.arg) for r in P.ITEMS]
           and [(r.label, r.action, r.arg) for r in page.rows[:18]] == [(r.label, r.action, r.arg) for r in P.ITEMS],
           'Extras and the menu have a row for every item (same labels and actions), so an item opens the same way from either')
    homes = [r.arg for r in P.ITEMS if r.action == P.ACT_HOME] + [r.arg for r in P.SETTINGS_PAGE.rows if r.action == P.ACT_HOME]
    expect(len(set(homes)) == len(homes) and len(homes) + 4 == 18,
           'no tile is twice (Albums, id 5, Artists, id 6, and Playlists, id 14, are the payload pages; HiFi, id 0, is left out)')
    m = Machine()
    m.widgets = {n: 0x30000000 + i for i, n in enumerate(['btn_return', 'btn_backtoplayer'] + [f'pod_row{i}' for i in range(len(ex.rows))])}
    m.call(on_row, a0=rows0 + 12 * ex_i)
    expect(('window_open', ex.key) in m.calls and m.names().count('widget_on') == 2 + len(ex.rows),
           'the Extras row opens m1pod_extras and binds the navbar and its eighteen rows')
    rows_ex = PSYMS[f'pod_rows_{P.EXTRAS_PAGE_INDEX}']
    for i, (name, hid) in enumerate(want):
        m = Machine()
        m.call(on_row, a0=rows_ex + 12 * (n_items + i))
        expect(('stock_resume', str(hid)) in m.calls and 'window_open' not in m.names(), f'Extras > {name} opens Home id {hid}')
    m = Machine(); m.present = {'/mnt/mmc/m1pod-off'}
    m.call(entry, a0=m.icon(str(P.HOME_ENTRY)))
    expect('window_open' not in m.names(), 'kill switch: neither the menu nor Extras opens')
    path = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1pod_extras.bin')
    asset = asset_tree(path)
    ex_rows = node(asset, 'pod_scrollview').children
    icons = [r for r in awtk_ui.parse(open(path, 'rb').read()).walk() if r.name == 'pod_icon']
    expect(len(ex_rows) == 18 and len(icons) == 18, 'eighteen Extras rows, each with its icon disc')
    m = Machine()
    for i, r in enumerate([c for c in ex_rows if 50 + c.y + c.h // 2 < CLIENT_H]):
        got = stock_target(m, asset, 160, 50 + r.y + r.h // 2)
        expect(f'pod_row{i}' in got and 'pod_icon' not in got, f'Extras row {i} is hit through the scroll view ({got})')

    arrange_tests(ctx, entry, on_row, rows0, rows_ex, ex_i)
    settings_tests(ctx, on_row, rows0)


# ---------------------------------------------------------------------------
# The customisable menu (patch/menu.c): the saved list, the arrangement of the stock list's rows, the Main Menu page.
MENU_FILE, MENU_TMP = '/mnt/data/m1pod-menu', '/mnt/data/m1pod-menu.tmp'
UI = os.path.join('rootfs', 'release/assets/default/raw/ui')


def page_machine(rows, extra=()):
    """A machine whose window has the navbar buttons, the stock list and `rows` pod_row widgets (and `extra` names)."""
    m = Machine()
    names = ['btn_return', 'btn_backtoplayer', 'pod_scrollview'] + [f'pod_row{i}' for i in range(rows)] + list(extra)
    m.widgets = {n: 0x30000000 + 0x100 * i for i, n in enumerate(names)}
    m.widgets['pod_scrollview'] = m.alloc(0x180)   # the payload looks at the scroll_view's vtable word and paint hook (zeros: not a list_view's)
    return m


def arranged(m, rows):
    """{row index: (y, shown)} as the payload's calls left the page; a row it never touched is absent."""
    out = {}
    for i in range(rows):
        h = m.widgets[f'pod_row{i}']
        if (h, 'visible') in m.props: out[i] = (m.props.get((h, 'y'), 0), bool(m.props[(h, 'visible')]) and bool(m.props.get((h, 'sensitive'), 1)))
    return out


MENU_ROWS = 20   # eighteen items, Extras, Settings


def open_menu(data=None, rows=MENU_ROWS, present=()):
    m = page_machine(rows)
    if data is not None: m.fs[MENU_FILE] = data
    m.call(PSYMS['m1pod_home_click'], a0=m.icon(str(pod_pages.HOME_ENTRY)), count=3000000)
    return m


def X(data):
    """A saved list with the Extras character: 'x' last, before the newline (the Extras row of the menu is shown)."""
    return data[:-1] + b'x\n' if data.endswith(b'\n') else data + b'x'


def shown_order(m, rows=MENU_ROWS):
    """The labels of the shown rows of the page, top to bottom, from the arrangement."""
    a = arranged(m, rows)
    return [pod_pages.MENU.rows[i].label for _, i in sorted((y, i) for i, (y, on) in a.items() if on)]


def arrange_tests(ctx, entry, on_row, rows0, rows_ex, ex_i):
    expect, P = ctx.expect, pod_pages
    items = [r.label for r in P.ITEMS]
    default = ['Cover Flow', 'Albums', 'Artists', 'Songs', 'Playlists', 'Shuffle', 'Extras', 'Settings']
    ROW_H = pod_ui.ROW_H

    # 9. The default menu: Cover Flow, Albums, Artists, Songs, Playlists, Shuffle (saved string "123456"); Now Playing is an item that is
    #    hidden by default (the mini player bar opens it), so are Genres and Folders (Extras); Extras and Settings last.
    NI = len(P.ITEMS)
    expect(items[:9] == ['Now Playing', 'Cover Flow', 'Albums', 'Artists', 'Songs', 'Playlists', 'Shuffle', 'Genres', 'Folders']
           and P.DEFAULT_MENU == [1, 2, 3, 4, 5, 6] and P.parse_menu(None) == P.DEFAULT_MENU and P.parse_menu(b'123456\n') == P.DEFAULT_MENU,
           'the asset order is the item order; the default menu is items 1..6 (Cover Flow ... Shuffle), Now Playing hidden')
    m = open_menu()
    expect(shown_order(m) == default, f'no saved list: the default menu, unchanged by the Extras items ({shown_order(m)})')
    a = arranged(m, MENU_ROWS)
    expect(all(a[i] == ((i - 1) * ROW_H, True) for i in range(1, 7)) and a[NI] == (6 * ROW_H, True) and a[NI + 1] == (7 * ROW_H, True),
           f'the shown rows are consecutive 52 px steps from y 0, Extras and Settings right after them ({a})')
    expect(all(a[i] == (0, False) for i in [0] + list(range(7, NI))), 'Now Playing, Genres, Folders and the nine Extras items are hidden (and insensitive) and parked at y 0')
    expect(('widget_set_prop_int', m.widgets['pod_scrollview'], 'virtual_h', 8 * ROW_H) in m.calls
           and not [c for c in m.calls if c[:3] == ('widget_set_prop_int', m.widgets['pod_scrollview'], 'yoffset')],
           'the list scrolls over exactly the shown rows (virtual_h 8 x 52), from the asset\'s top (the offset is not touched)')
    expect(not any(c[0] in ('write', 'rename', 'unlink') for c in m.calls) and
           [c[1] for c in m.calls if c[0] == 'open'] == [MENU_FILE], 'opening the menu reads the list file and writes nothing')

    # 10. Saved lists: order, subsets, none at all
    for data, want in ((b'6543210\n', ['Shuffle', 'Playlists', 'Songs', 'Artists', 'Albums', 'Cover Flow', 'Now Playing']),
                       (b'078\n', ['Now Playing', 'Genres', 'Folders']), (b'3\n', ['Artists']), (b'0123456', items[:7]),
                       (b'876543210\n', items[8::-1]), (b'\n', []),
                       (b'a\n', ['Favorites']), (b'0ei\n', ['Now Playing', 'Composers', 'CD Ripper']), (b'0123456ad\n', items[:7] + ['Favorites', 'Most Played']),
                       (b'ihgfedcba876543210\n', items[::-1]), (b'012345678abcdefghi', items), (b'012345678abcdefgh', items[:-1]),
                       (b'i0\n', ['CD Ripper', 'Now Playing'])):
        for with_x in (True, False):   # 'x' last in the list: Extras is shown right above Settings; without it Extras is hidden and Settings follows the items
            d = X(data) if with_x else data
            m = open_menu(d)
            w = want + (['Extras'] if with_x else []) + ['Settings']
            expect(shown_order(m) == w, f'saved {d!r}: {w}')
            a = arranged(m, MENU_ROWS)
            n = len(want)
            if with_x:
                expect(a[NI] == (n * ROW_H, True) and a[NI + 1] == ((n + 1) * ROW_H, True),
                       f'saved {d!r}: Extras and Settings are shown, last ({a[NI]}, {a[NI + 1]})')
            else:
                expect(a[NI] == (0, False) and a[NI + 1] == (n * ROW_H, True),
                       f'saved {d!r}: Extras is hidden (insensitive, parked at y 0) and Settings sits right after the items ({a[NI]}, {a[NI + 1]})')
            expect(('widget_set_prop_int', m.widgets['pod_scrollview'], 'virtual_h', (n + 1 + with_x) * ROW_H) in m.calls, f'saved {d!r}: virtual_h follows')

    # 10b. The stock list_view lays its visible rows out again in child order at every relayout (test/pod/pulldown.py runs that code):
    #      the children are stacked in page order, hidden rows last (widget_restack child, index), and the plain painter replaces the
    #      list_view's paint hook (only the exact stock hook on a scroll_view)
    for data, shown in ((None, [1, 2, 3, 4, 5, 6]), (b'6502x\n', [6, 5, 0, 2]), (b'x\n', []), (b'i0x\n', [17, 0]),
                        (b'123456\n', [1, 2, 3, 4, 5, 6]), (b'6502\n', [6, 5, 0, 2]), (b'\n', [])):
        m = open_menu(data)
        hidden_x = data is not None and not data.rstrip(b'\n').endswith(b'x')   # no 'x': the Extras row is parked with the hidden items, last
        want = shown + ([NI + 1] if hidden_x else [NI, NI + 1]) + [i for i in range(NI) if i not in shown] + ([NI] if hidden_x else [])
        got = [c for c in m.calls if c[0] == 'widget_restack']
        expect(got == [('widget_restack', m.widgets[f'pod_row{r}'], k) for k, r in enumerate(want)],
               f'saved {data!r}: the rows are restacked in page order, the hidden ones last ({[g[2] for g in got]} for rows {want})')
    hook = 0x60c164
    for what, vt, hk, cleared in (('a list_view scroll_view', 0x97a298, hook, True), ('another widget', 0x97a018, hook, False),
                                  ('another hook', 0x97a298, 0x60c0fc, False), ('a plain scroll_view', 0x97a298, 0, False)):
        m = page_machine(MENU_ROWS)
        sv = m.widgets['pod_scrollview']; m.setword(sv + 0x70, vt); m.setword(sv + 0xf4, hk)
        m.call(PSYMS['m1pod_home_click'], a0=m.icon(str(pod_pages.HOME_ENTRY)), count=3000000)
        expect(m.word(sv + 0xf4) == (0 if cleared else hk), f'{what}: the paint-children hook word is ' + ('cleared' if cleared else 'left alone'))
        expect(m.word(sv + 0x70) == vt, f'{what}: the vtable word is left alone')
    m = page_machine(MENU_ROWS)   # the Extras page
    sv = m.widgets['pod_scrollview']; m.setword(sv + 0x70, 0x97a298); m.setword(sv + 0xf4, hook)
    m.call(PSYMS['menu_arrange'], a0=m.window, a1=1, count=3000000)
    expect(m.word(sv + 0xf4) == 0, 'the Extras page: the plain painter')
    got = [c for c in m.calls if c[0] == 'widget_restack']
    shown = set(P.parse_menu(None))
    want = [i for i in P.EXTRAS_ORDER if i not in shown] + [i for i in P.EXTRAS_ORDER if i in shown]
    expect(got == [('widget_restack', m.widgets[f'pod_row{r}'], k) for k, r in enumerate(want)],
           f'the Extras page: the children are restacked in the Extras order, the hidden ones last ({[g[2] for g in got]})')

    # 11. Anything invalid is the default list: unknown ids, duplicates, too long, empty, binary, text after the list
    bad = [b'9\n', b'0129\n', b'00\n', b'01234567801\n', b'0123456789\n', b'', b'01 2\n', b'01\n\n',
           # the Extras character 'x': only as the last character (before the newline), once; anywhere else, doubled, or with more after it is invalid
           b'x1\n', b'1x2\n', b'123456xx\n', b'xx', b'x\nx', b'x\n\n', b'0x1', b'123456x ', b'123456 x', b'X', b'012345678abcdefghixi\n', b'012345678abcdefghix\n\n',
           b'012345678abcdefghi0x\n', b'0123456789abcdefghx\n', b'x0\n', b'0x0\n', b'\nx', b'\n\n', b'0\r\n',
           b'0123456780123456', b'a' * 200, bytes(range(256)), b'01\x002\n', b'-1\n', b'0123456789012345678901234567890123456789\n', b'0' * 1000000,
           # the Extras characters: unknown ones, duplicates, an uppercase letter, one too many, over the file cap
           # 'j' was Screenshot (V2.1nF): a menu file saved with it is invalid now, whatever else is in it
           b'j\n', b'j0\n', b'0j\n', b'012345678abcdefghij\n', b'ihgfedcba876543210j\n', b'0123456j', b'ihgfedcba876543210\n\n',
           b'k\n', b'aa\n', b'A\n', b'0a0\n', b'012345678abcdefghijk\n', b'012345678abcdefghij0\n', b'012345678abcdefghija\n', b'012345678abcdefghij\n\n',
           b'0123456789abcdefgh\n', b'z', b'0123456789abcdefghijklmn', b'0123456789abcdefghijklm']
    for data in bad:
        m = open_menu(data)
        expect(shown_order(m) == default and P.parse_menu(data) == P.DEFAULT_MENU
               and P.parse_menu_full(data) == (P.DEFAULT_MENU, True), f'saved {data[:20]!r} ({len(data)} bytes): the default menu, Extras shown')
        expect(m.icount < 200000, f'saved {len(data)} bytes: read is bounded, the open stays cheap ({m.icount} instructions)')
    # the Python model of the parser (tools/pod_pages.py parse_menu, which the docs and previews use) agrees with the payload
    import random
    rnd = random.Random(7)
    for _ in range(300):
        n = rnd.choice((0, 1, 2, 5, 9, 10, 11, 15, 16, 17, 18, 19, 20, 23, 24, 25))
        pool = b'0123456789\n xjA' if rnd.random() < 0.3 else P.ID_CHARS.encode() if rnd.random() < 0.5 else b'012345678'
        data = bytes(rnd.choice(pool) for _ in range(n))
        if rnd.random() < 0.3:   # a valid-looking permutation prefix, so the accepted case is exercised too
            ids = list(P.ID_CHARS.encode()); rnd.shuffle(ids); data = bytes(ids[:rnd.randrange(0, 19)]) + rnd.choice((b'', b'x')) + rnd.choice((b'', b'\n'))
        m = open_menu(data)
        ids, with_x = P.parse_menu_full(data)
        want = [P.MENU.rows[i].label for i in ids] + (['Extras'] if with_x else []) + ['Settings']
        if shown_order(m) != want: expect(False, f'parser model differs for {data!r}: {shown_order(m)} vs {want}'); break
    else: expect(True, 'the payload reads 300 random lists as the Python model does')
    expect(P.parse_menu(b'0123456\n') == list(range(7)) == P.parse_menu(b'0123456') and P.parse_menu(b'0e8a\n') == [0, 13, 8, 9]
           and P.parse_menu(b'012345678abcdefghi\n') == list(range(18)) and P.parse_menu(b'012345678abcdefghij\n') == P.DEFAULT_MENU
           and P.parse_menu(b'0j\n') == P.DEFAULT_MENU,
           'the Python model: old digit files parse as before, the Extras characters are ids 9..17, j (Screenshot, V2.1nF) is unknown')
    # the Extras row's character: 'x', last only; the default string is 123456x; a list without it (an old 123456 file too) hides Extras
    expect(P.EXTRAS_CHAR == 'x' and P.DEFAULT_EXTRAS is True and P.format_menu(P.DEFAULT_MENU, P.DEFAULT_EXTRAS) == '123456x\n'
           and P.parse_menu_full(b'123456x\n') == ([1, 2, 3, 4, 5, 6], True) and P.parse_menu_full(b'123456x') == ([1, 2, 3, 4, 5, 6], True)
           and P.parse_menu_full(b'123456\n') == ([1, 2, 3, 4, 5, 6], False) and P.parse_menu_full(None) == ([1, 2, 3, 4, 5, 6], True)
           and P.parse_menu_full(b'x\n') == ([], True) and P.parse_menu_full(b'\n') == ([], False)
           and P.parse_menu_full(b'012345678abcdefghix\n') == (list(range(18)), True) and P.parse_menu_full(b'0ex\n') == ([0, 13], True)
           and P.format_menu([], False) == '\n' and P.format_menu(list(range(18)), True) == '012345678abcdefghix\n'
           and len(P.format_menu(list(range(18)), True)) < P.MENU_FILE_MAX,
           'the Python model: the Extras character x is allowed only last; "123456x" is the default, "123456" hides Extras, the longest list fits the file cap')
    m = open_menu(b'0\n'); m.fs[MENU_FILE] = b'0\n'
    expect(m.fs[MENU_FILE] == b'0\n', 'a valid list is never rewritten by reading it')
    m = open_menu(b'ihgfedcba876543210x\n')
    expect(m.icount < 200000, f'the longest valid list: arranging twenty rows stays cheap ({m.icount} instructions)')

    # 11b. A page that is not ours (a row or the list missing) is left exactly as the asset has it
    for gone in ('pod_scrollview', 'pod_row5', 'pod_row12', 'pod_row18'):
        m = page_machine(MENU_ROWS); m.widgets.pop(gone); m.call(PSYMS['m1pod_home_click'], a0=m.icon(str(P.HOME_ENTRY)), count=3000000)
        expect(('window_open', P.MENU.key) in m.calls and not any(c[0] in ('widget_move', 'widget_set_visible', 'widget_set_sensitive') for c in m.calls),
               f'no {gone}: the menu opens as the asset has it, nothing moved or hidden')

    # 12. Extras: every item the menu does not show, in id order (the hidden menu items, then the stock tiles)
    def extras(data=None):
        m = page_machine(NI)
        if data is not None: m.fs[MENU_FILE] = data
        m.call(on_row, a0=rows0 + 12 * ex_i, count=3000000)
        a = arranged(m, NI)
        order = [(P.EXTRAS_PAGE.rows[i].label) for _, i in sorted((y, i) for i, (y, on) in a.items() if on)]
        return m, order, a
    # The fixed order, the same in every language (the English labels): the default menu items when hidden, the Library group, the
    # Tools group, each group alphabetical.
    MAIN = ['Albums', 'Artists', 'Cover Flow', 'Now Playing', 'Playlists', 'Shuffle', 'Songs']
    LIB = ['Composers', 'Favorites', 'Folders', 'Genres', 'Hi-Res', 'Most Played', 'Recently Added', 'Recently Played']
    TOOLS = ['CD Ripper', 'Tidal', 'Update Library']
    expect(MAIN == sorted(MAIN) and LIB == sorted(LIB) and TOOLS == sorted(TOOLS) and sorted(MAIN + LIB + TOOLS) == sorted(items)
           and [items[i] for i in P.EXTRAS_ORDER] == MAIN + LIB + TOOLS, f'the Extras order is the three alphabetical groups ({[items[i] for i in P.EXTRAS_ORDER]})')
    full = MAIN + LIB + TOOLS
    left = lambda shown: [x for x in full if x not in shown]
    m, order, a = extras()
    want_ex = left([items[i] for i in P.DEFAULT_MENU])
    expect(order == want_ex == ['Now Playing'] + LIB + TOOLS, f'default: Now Playing (hidden in the menu), the Library group, then the Tools group ({order})')
    expect(all(a[i] == (0, False) for i in P.DEFAULT_MENU) and ('widget_set_prop_int', m.widgets['pod_scrollview'], 'virtual_h', len(want_ex) * ROW_H) in m.calls,
           'the items the menu shows are hidden here, the list is the twelve others long')
    ys = [y for y, i in sorted((y, i) for i, (y, on) in a.items() if on)]
    expect(ys == [k * ROW_H for k in range(len(want_ex))], 'the Extras rows are consecutive from y 0')
    expect('Genres' in order and order.index('Genres') == 4 and order.index('Folders') == 3, 'Genres and Folders take their alphabetical places')
    m, order, a = extras(b'\n')
    expect(order == full, 'every item hidden: all eighteen are in Extras, in the fixed order')
    m, order, a = extras(b'012345678\n')
    expect(order == left(items[:9]) and all(a[i] == (0, False) for i in range(9)), 'Genres and Folders in the menu too: Extras is the other nine')
    m, order, a = extras(b'0345\n')
    expect(order == left([items[i] for i in (0, 3, 4, 5)]), f'a hidden item is in Extras whatever order it had: {order}')
    m, order, a = extras(b'zz')
    expect(order == ['Now Playing'] + LIB + TOOLS, 'an invalid list: the default split')
    # an Extras item shown in the menu leaves the Extras page (and the page shortens); the rest stay, in order
    m, order, a = extras(b'0123456ad\n')
    want_ex = left(items[:7] + ['Favorites', 'Most Played'])
    expect(order == want_ex and a[9] == (0, False) and a[12] == (0, False)
           and ('widget_set_prop_int', m.widgets['pod_scrollview'], 'virtual_h', len(want_ex) * ROW_H) in m.calls,
           f'Favorites and Most Played shown in the menu are hidden (and insensitive) on Extras, which is nine rows long, the others in place ({order})')
    ys = [y for y, i in sorted((y, i) for i, (y, on) in a.items() if on)]
    expect(ys == [k * ROW_H for k in range(len(want_ex))], 'the remaining Extras rows are consecutive from y 0')
    m, order, a = extras(b'012345678abcdefghi\n')
    expect(order == [] and all(a[i] == (0, False) for i in range(NI)) and ('widget_set_prop_int', m.widgets['pod_scrollview'], 'virtual_h', 0) in m.calls,
           'every item shown in the menu: Extras is empty (its menu row stays)')
    m, order, a = extras(b'i0\n')
    expect(order == left(['CD Ripper', 'Now Playing']), f'a shown last tile and a shown first item both leave Extras ({order})')
    m, order, a = extras(b'j\n')
    expect(order == ['Now Playing'] + LIB + TOOLS, f'a file with the retired Screenshot character j is invalid: the default menu and the default Extras ({order})')
    # the children are stacked in that order (a stock relayout lays visible rows out in child order), the hidden ones last
    for data in (None, b'\n', b'0123456ad\n', b'3\n'):
        m, order, a = extras(data)
        shown = P.parse_menu(data)
        want = [i for i in P.EXTRAS_ORDER if i not in shown] + [i for i in P.EXTRAS_ORDER if i in shown]
        got = [c for c in m.calls if c[0] == 'widget_restack']
        expect(got == [('widget_restack', m.widgets[f'pod_row{r}'], k) for k, r in enumerate(want)],
               f'saved {data!r}: Extras restacks its rows in the fixed order, the hidden ones last ({[g[2] for g in got]})')
    # no item is ever in neither place, in any saved list
    for data in (None, b'\n', b'8\n', b'0123\n', b'87654321\n', b'0123456\n', b'a\n', b'ie0\n', b'j\n', b'0123456abcdefghi\n', b'012345678abcdefghi\n'):
        mm = open_menu(data); ids = P.parse_menu(data)
        _, ex_order, _ = extras(data)
        in_menu = set(shown_order(mm)) - {'Extras', 'Settings'}
        expect(in_menu | set(ex_order) >= set(items) and not in_menu & set(ex_order), f'saved {data!r}: every item is in exactly one of the menu and Extras')
    # a tap on a hidden item's row in Extras does what the menu row would
    rows_x = PSYMS[f'pod_rows_{P.EXTRAS_PAGE_INDEX}']
    for i, r in enumerate(P.ITEMS):
        m = Machine()
        m.call(on_row, a0=rows_x + 12 * i)
        mm = Machine()
        mm.call(on_row, a0=rows0 + 12 * i)
        expect([c for c in m.calls if c[0] != 'widget_on'] == [c for c in mm.calls if c[0] != 'widget_on'], f'Extras > {r.label} acts as the menu row')

    # 13. Hit testing on the arranged menu, by demo's own code: a touch in the middle of every shown row reaches that row, one
    #     over the place a hidden row was parked reaches the row that is there, and none below the last row hits any
    def apply_arrangement(m, tree):
        for i, row in enumerate([c for c in node(tree, 'pod_scrollview').children if c.name.startswith('pod_row')]):
            h = m.widgets[f'pod_row{i}']
            if (h, 'y') in m.props: row.y = m.props[(h, 'y')]
            if (h, 'visible') in m.props: row.flags = (row.flags & ~F_VISIBLE) | (F_VISIBLE if m.props[(h, 'visible')] else 0)
            if (h, 'sensitive') in m.props: row.flags = (row.flags & ~F_SENSITIVE) | (F_SENSITIVE if m.props[(h, 'sensitive')] else 0)
    # the Extras page, arranged for a list that shows some Extras items in the menu: every shown row is hit, no hidden row is
    for data in (None, b'0123456ad\n', b'ai\n', b'\n'):
        m, order, a = extras(data)
        tree = asset_tree(os.path.join(WORK, UI, 'm1pod_extras.bin'))
        apply_arrangement(m, tree)
        shown = sorted((y, i) for i, (y, on) in a.items() if on)
        hidden = {f'pod_row{i}' for i, (y, on) in a.items() if not on}
        mx = Machine()
        for y, i in shown:
            if y + ROW_H // 2 >= 400: continue
            got = stock_target(mx, tree, 160, 50 + y + ROW_H // 2)
            expect(f'pod_row{i}' in got and not hidden & set(got), f'Extras, saved {data!r}: a touch on row {i} reaches it ({got})')
        if shown:
            got = stock_target(mx, tree, 160, 50 + ROW_H // 2)
            expect(f'pod_row{shown[0][1]}' in got and not hidden & set(got), f'Extras, saved {data!r}: the parked hidden rows take no touch ({got})')
        if len(shown) * ROW_H + 10 < 400:
            got = stock_target(mx, tree, 160, 50 + len(shown) * ROW_H + 10)
            expect(not [g for g in got if g.startswith('pod_row')], f'Extras, saved {data!r}: below the last row nothing is hit ({got})')
    for data in (None, b'6543210\n', b'\n', b'01234\n', b'a0ei\n', b'012345678abcdefghi\n'):
        m = open_menu(data)
        tree = asset_tree(os.path.join(WORK, UI, 'm1pod_menu.bin'))
        apply_arrangement(m, tree)
        a = arranged(m, MENU_ROWS)
        shown = sorted((y, i) for i, (y, on) in a.items() if on)
        hidden = {f'pod_row{i}' for i, (y, on) in a.items() if not on}
        mx = Machine()
        for y, i in shown:
            if y + ROW_H // 2 >= 400: continue
            got = stock_target(mx, tree, 160, 50 + y + ROW_H // 2)
            expect(f'pod_row{i}' in got and not hidden & set(got), f'saved {data!r}: a touch on row {i} reaches it ({got})')
        got = stock_target(mx, tree, 160, 50 + ROW_H // 2)
        expect(f'pod_row{shown[0][1]}' in got and not hidden & set(got), f'saved {data!r}: where hidden rows are parked the first shown row takes the touch ({got})')
        if len(shown) * ROW_H + 10 < 400:
            got = stock_target(mx, tree, 160, 50 + len(shown) * ROW_H + 10)
            expect(not [g for g in got if g.startswith('pod_row')], f'saved {data!r}: below the last row nothing is hit ({got})')

    # 14. The menu arranges again when it is back in front (after the Main Menu page changed the list)
    m = open_menu()
    fg = [c for c in m.calls if c[0] == 'widget_on' and c[2] == 0x12d]   # EVT_WINDOW_FG (patch/home.h)
    expect(len(fg) == 1, 'the menu registers one to-foreground handler')
    sw = m.widgets['pod_scrollview']
    m.fs[MENU_FILE] = b'012345678abcx\n'   # 12 items + Extras, Settings: 728 px in a 400 px list
    m.props[(sw, 'h')] = 400; m.props[(sw, 'yoffset')] = 200; m.calls = []
    m.call(fg[0][3], a0=fg[0][4], count=3000000)
    expect(m.props[(sw, 'yoffset')] == 200 and not [c for c in m.calls if c[:3] == ('widget_set_prop_int', sw, 'yoffset')],
           f'back in front (from a page it opened) the list stays where it was scrolled (yoffset {m.props[(sw, "yoffset")]})')
    m.props[(sw, 'yoffset')] = 380
    m.fs[MENU_FILE] = b'4x\n'
    m.call(fg[0][3], a0=fg[0][4], count=3000000)
    expect(shown_order(m) == ['Songs', 'Extras', 'Settings'], f'back in front it shows the new list ({shown_order(m)})')
    expect(m.props[(sw, 'yoffset')] == 0, f'a list now shorter than its window is back at the top (yoffset {m.props[(sw, "yoffset")]})')


def settings_tests(ctx, on_row, rows0):
    expect, P = ctx.expect, pod_pages
    S = P.SETTINGS_PAGE
    rows_s = PSYMS[f'pod_rows_{P.SETTINGS_PAGE_INDEX}']
    sw = lambda i: f'pod_switch{i}'
    mm_i = next(i for i, r in enumerate(S.rows) if r.action == P.ACT_PAGE and r.arg == P.MENUCFG_PAGE_INDEX)
    cf_i = next(i for i, r in enumerate(S.rows) if r.action == P.ACT_PAGE and r.arg == P.CFSET_PAGE_INDEX)
    settings_i = next(i for i, r in enumerate(P.MENU.rows) if r.action == P.ACT_PAGE and r.arg == P.SETTINGS_PAGE_INDEX)

    def open_settings():
        m = Machine()
        m.widgets = {n: 0x30000000 + 0x100 * i for i, n in enumerate(
            ['btn_return', 'btn_backtoplayer'] + [f'pod_row{i}' for i in range(len(S.rows))])}
        m.call(on_row, a0=rows0 + 12 * settings_i, count=3000000)
        return m

    # 15. Settings: Main Menu, Cover Flow and Home Screen (sub-pages), Playback, System Settings, Screenshot; always reachable from the menu, in any saved list
    expect([r.label for r in S.rows] == ['Main Menu', 'Cover Flow', 'Home Screen', 'Playback', 'System Settings', 'Screenshot']
           and (S.rows[5].action, S.rows[5].arg) == (P.ACT_SHOT, 0),
           'the Settings page lists Main Menu, Cover Flow, Home Screen, Playback, System Settings and Screenshot (last; tests/shot.py starts it)')
    expect(S.rows[3].label == 'Playback' and (S.rows[3].action, S.rows[3].arg) == (P.ACT_HOME, P.HOME_PLAYSET)
           and (S.rows[4].action, S.rows[4].arg) == (P.ACT_HOME, P.HOME_SYSSET), 'Playback opens the stock Play settings page, System Settings the stock one')
    ex_r, st_r = len(P.ITEMS), len(P.ITEMS) + 1
    for data in (None, b'\n', b'0123456\n', b'87\n', b'zz', b'ihgfedcba876543210\n', b'012345678abcdefghi\n', b'a\n', b'0123456abcdefghi8\n'):
        for with_x in (True, False):   # Settings is always shown and bound; Extras only when the list ends in 'x'
            if data is None and not with_x: continue
            d = data if data is None or not with_x else X(data)
            m = open_menu(d)
            a = arranged(m, MENU_ROWS)
            ids, extras_on = P.parse_menu_full(d)
            if extras_on: expect(a[st_r][1] and a[ex_r][1] and a[ex_r][0] == len(ids) * pod_ui.ROW_H and a[st_r][0] == a[ex_r][0] + pod_ui.ROW_H, f'saved {d!r}: the Extras and Settings rows are shown and reachable')
            else: expect(a[st_r][1] and not a[ex_r][1] and a[ex_r][0] == 0 and a[st_r][0] == len(ids) * pod_ui.ROW_H,
                         f'saved {d!r}: Extras is hidden, Settings is shown right after the items')
            expect(('widget_on', m.widgets[f'pod_row{st_r}'], O['EVT_CLICK']) in [c[:3] for c in m.calls], f'saved {d!r}: the Settings row is bound')
        m = open_menu(data)
        expect(('widget_on', m.widgets[f'pod_row{st_r}'], O['EVT_CLICK']) in [c[:3] for c in m.calls]
               and ('widget_on', m.widgets[f'pod_row{ex_r}'], O['EVT_CLICK']) in [c[:3] for c in m.calls], f'saved {data!r}: the Extras and Settings rows are bound')
    m = open_settings()
    expect(('window_open', S.key) in m.calls and m.names().count('widget_on') == 2 + len(S.rows), 'the menu row opens the Settings page and binds its rows')
    expect(not any(c[0] == 'widget_set_tr_text' for c in m.calls), 'the Settings page shows no sort value (it is on the Cover Flow page)')

    # 16. Settings > Cover Flow: the row opens the sub-page (landscape switch, sort value); the generic page open binds its rows
    m = Machine()
    m.widgets = {n: 0x30000000 + 0x100 * i for i, n in enumerate(['btn_return', 'btn_backtoplayer'] + [f'pod_row{i}' for i in range(len(S.rows))])}
    m.call(on_row, a0=rows_s + 12 * cf_i, count=3000000)
    expect(('window_open', P.CFSET_PAGE.key) in m.calls, 'the Cover Flow row on the Settings page opens m1pod_cfset')
    cfset_tests(ctx, on_row)

    # 17. The Main Menu row opens the customise page (the generic page open: navbar bound, no row table)
    m = Machine()
    m.widgets = {n: 0x30000000 + 0x100 * i for i, n in enumerate(['btn_return', 'btn_backtoplayer'])}
    m.call(on_row, a0=rows_s + 12 * mm_i, count=3000000)
    expect(('window_open', P.MENUCFG_PAGE.key) in m.calls and P.MENUCFG_PAGE.rows == [], 'the Main Menu row opens the Main Menu page')
    mainmenu_tests(ctx, on_row, rows_s, mm_i)


def cfset_tests(ctx, on_row):
    """Settings > Cover Flow (m1pod_cfset): the Landscape switch and the Sort value row."""
    expect, P = ctx.expect, pod_pages
    C = P.CFSET_PAGE
    rows_s = PSYMS[f'pod_rows_{P.SETTINGS_PAGE_INDEX}']
    cf_i = next(i for i, r in enumerate(P.SETTINGS_PAGE.rows) if r.action == P.ACT_PAGE and r.arg == P.CFSET_PAGE_INDEX)
    LAND, SORT = '/mnt/data/m1pod-landscape', CFSORT_FILE
    land_i = next(i for i, r in enumerate(C.rows) if r.action == P.ACT_LANDSCAPE)
    sort_i = next(i for i, r in enumerate(C.rows) if r.action == P.ACT_SORT)
    sw, val = f'pod_switch{land_i}', f'pod_value{sort_i}'
    expect([(r.label, r.action) for r in C.rows] == [('Landscape', P.ACT_LANDSCAPE), ('Sort', P.ACT_SORT), ('Rebuild Covers', P.ACT_REBUILD)] and C.title == 'Cover Flow',
           'the Cover Flow page: titled Cover Flow, rows Landscape (switch), Sort (value) and Rebuild Covers')

    def open_cf(land=None, sort=None, language=None):
        m = Machine()
        m.widgets = {n: 0x30000000 + 0x100 * i for i, n in enumerate(
            ['btn_return', 'btn_backtoplayer'] + [f'pod_row{i}' for i in range(len(P.SETTINGS_PAGE.rows))] + [sw, val])}
        if land is not None: m.fs[LAND] = land
        if sort is not None: m.fs[SORT] = sort
        if language: m.set_language(language)
        m.call(on_row, a0=rows_s + 12 * cf_i, count=3000000)
        return m

    def label(m):
        """The last key the sort value was set to, and the text it shows."""
        keys = [c[2] for c in m.calls if c[0] == 'widget_set_tr_text' and c[1] == m.widgets[val]]
        texts = [c[2] for c in m.calls if c[0] == 'widget_set_text_utf8' and c[1] == m.widgets[val]]
        return (keys[-1] if keys else None), (texts[-1] if texts else None)

    m = open_cf()
    # (the Settings page's own row tables bind the cfset page's rows by name: row0 the switch, row1 the sort tap)
    expect(('window_open', C.key) in m.calls and ('widget_on', m.widgets['pod_row0'], O['EVT_CLICK']) in [c[:3] for c in m.calls]
           and ('widget_on', m.widgets['pod_row1'], O['EVT_CLICK']) in [c[:3] for c in m.calls], 'the Settings row opens the page and binds both rows')
    # Landscape: the switch writes the setting Cover Flow reads, atomically, the image follows (as the Settings page's switch did)
    expect(('image_base_set_image', m.widgets[sw], 'sset_off') in m.calls, 'Landscape is off with nothing saved')
    m = open_cf(b'1\n')
    expect(('image_base_set_image', m.widgets[sw], 'sset_on') in m.calls, 'saved landscape: the switch opens on')
    for data in (b'x', b'', b'0\n'):
        m = open_cf(data)
        expect(('image_base_set_image', m.widgets[sw], 'sset_off') in m.calls, f'saved {data!r}: the switch opens off')
    m = open_cf()
    m.click(f'pod_row{land_i}')
    expect(m.fs.get(LAND) == b'1\n' and LAND + '.tmp' not in m.fs and ('rename', LAND + '.tmp', LAND) in m.calls and ('fsync', '/mnt/data') in m.calls
           and ('image_base_set_image', m.widgets[sw], 'sset_on') in m.calls, 'a tap turns it on: written atomically, the switch on')
    m.click(f'pod_row{land_i}')
    expect(m.fs.get(LAND) == b'0\n' and ('image_base_set_image', m.widgets[sw], 'sset_off') in m.calls, 'and off again')
    expect(SORT not in m.fs, 'the landscape switch does not touch the sort file')
    m = open_cf(b'1\n'); m.fail.add(('write', LAND + '.tmp'))
    m.click(f'pod_row{land_i}')
    expect(m.fs.get(LAND) == b'1\n' and not any(c[0] == 'image_base_set_image' for c in m.calls) and LAND + '.tmp' not in m.fs,
           'a failed write changes neither the file nor the switch')

    # Sort: Artist by default, the value in the row's grey label (set by key, so the language follows), a tap flips it
    expect(label(open_cf()) == ('Artist', 'Artist'), 'with nothing saved the order is Artist')
    expect(label(open_cf(sort=b'0\n')) == ('album', 'album'), 'saved "0": Album (the stock key album)')
    for data in (b'1\n', b'1', b'', b'x', b'00', b'0x', b'0\n\n', b'2\n', b' 0\n', b'\x000'):
        expect(label(open_cf(sort=data))[0] == 'Artist', f'saved {data!r}: invalid or Artist, the label reads Artist')
    expect(label(open_cf(sort=b'0'))[0] == 'album', 'saved "0" without a newline is Album too')
    m = open_cf()
    m.click(f'pod_row{sort_i}')
    expect(m.fs.get(SORT) == b'0\n' and SORT + '.tmp' not in m.fs and ('rename', SORT + '.tmp', SORT) in m.calls and ('fsync', '/mnt/data') in m.calls
           and label(m) == ('album', 'album'), 'a tap on Sort: Album, written atomically, the value follows')
    m.click(f'pod_row{sort_i}')
    expect(m.fs.get(SORT) == b'1\n' and label(m) == ('Artist', 'Artist'), 'and back to Artist')
    expect(LAND not in m.fs, 'the sort tap does not touch the landscape file')
    m = open_cf(sort=b'0\n'); m.fail.add(('write', SORT + '.tmp'))
    m.click(f'pod_row{sort_i}')
    expect(m.fs.get(SORT) == b'0\n' and label(m) == (None, None) and SORT + '.tmp' not in m.fs, 'a failed write changes neither the file nor the value')
    m = open_cf(); m.fail.add(('rename', SORT))
    m.click(f'pod_row{sort_i}')
    expect(SORT not in m.fs and label(m) == (None, None), 'a failed rename changes neither')
    # localisation: the value is the translation in every language
    for loc in pod_i18n.ALL_TABLES:
        T = tr_of(loc)
        m = open_cf(language=loc)
        expect(label(m) == ('Artist', T('Artist')), f'{loc}: Artist reads {T("Artist")!r}')
        m.click(f'pod_row{sort_i}')
        expect(label(m)[0] == 'album', f'{loc}: Album is the stock key album')
    # Rebuild Covers: the row asks first (the stock confirm dialog, a wrapped message), and only Yes opens the rebuild
    rb_i = next(i for i, r in enumerate(C.rows) if r.action == P.ACT_REBUILD)
    KEY = 'Rebuild all covers? This may take a few minutes.'

    def rebuild_machine(language=None, yes=False):
        m = cover_machine(albums=3)
        for n in ['btn_return', 'btn_backtoplayer'] + [f'pod_row{i}' for i in range(len(P.SETTINGS_PAGE.rows))] + [sw, val]:
            if n not in m.widgets: m.widget(n)
        if language: m.set_language(language)
        m.confirm_yes = yes
        m.call(on_row, a0=rows_s + 12 * cf_i, count=3000000)
        m.click(f'pod_row{rb_i}', count=6000000)
        return m

    m = rebuild_machine()
    confirms = [c for c in m.calls if c[0] == 'confirm']
    expect(confirms == [('confirm', KEY, O['CONFIRM_KIND_WRAP'])], f'a tap on Rebuild Covers asks first, in the stock confirm dialog, kind 5 (wrapped) ({confirms})')
    expect(('navigator_to_with_context', 'dialog/confirminfo_dialog') == m.calls[[c[0] for c in m.calls].index('navigator_to_with_context')][:2]
           if 'navigator_to_with_context' in m.names() else False, 'through navigator_to_with_context(dialog/confirminfo_dialog)')
    expect(not any(n in m.names() for n in ('window_open', 'pthread_create', 'mkdir', 'rename', 'unlink', 'fopen')) and build_state(m)['jobs'] == 0,
           'No (or the dialog closed): nothing happens at all, no page, no thread, no file touched')
    m = rebuild_machine(yes=True)
    expect(('window_open', 'm1pod_cover') in m.calls and count_of(m, 'pthread_create') == 1 and build_state(m)['mode'] == 1 and build_state(m)['total'] == 3
           and ('widget_set_visible', m.widgets['btn_cancel'], 1) in m.calls, 'Yes opens Cover Flow on the Preparing screen with every cover queued (CC_REBUILD)')
    for loc in pod_i18n.ALL_TABLES:
        T = tr_of(loc)
        m = rebuild_machine(language=loc)
        expect([c[1] for c in m.calls if c[0] == 'confirm'] == [T(KEY)], f'{loc}: the confirm message reads {T(KEY)!r}')
    # the built asset: a value label that takes no touch, no chevron, the row takes the tap
    path = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui', C.key + '.bin')
    tree = awtk_ui.parse(open(path, 'rb').read())
    row, value = tree.find(f'pod_row{sort_i}'), tree.find(val)
    expect(value is not None and value.get('sensitive') == 'false' and value.get('tr_text') == 'Artist'
           and not [c for c in row.children if c.type == 'image' and c.get('image') == 'right_arrow'],
           'the Sort row: an insensitive value label (tr_text Artist) and no chevron')
    expect(tree.find(f'pod_switch{land_i}') is not None and tree.find(f'pod_switch{land_i}').get('sensitive') == 'false'
           and not [c for c in tree.find(f'pod_row{land_i}').children if c.name == val], 'the Landscape row: its switch image, no value')
    node_tree = asset_tree(path)
    mm = Machine()
    for r in (land_i, sort_i):
        y = 50 + r * pod_ui.ROW_H + pod_ui.ROW_H // 2
        for x in (100, 290):
            got = stock_target(mm, node_tree, x, y)
            expect(f'pod_row{r}' in got and not any(n.startswith('pod_value') or n.startswith('pod_switch') for n in got), f'a tap at x {x} on row {r} reaches the row ({got})')


def mainmenu_tests(ctx, on_row, rows_s, mm_i):
    expect, P = ctx.expect, pod_pages
    n = len(P.ITEMS)
    ROW_H = pod_ui.ROW_H
    items = [r.label for r in P.ITEMS]
    ZX, ZW = 191, 50   # the arrow's rectangle in the row (the asset's pod_up button, checked in 22); the tap of an arrow is a click on its row in this zone
    arrow = lambda m, i: m.click(f'pod_row{i}', x=ZX + ZW // 2)

    def open_page(data=None):
        m = Machine()
        names = ['btn_return', 'btn_backtoplayer', 'pod_scrollview'] + [f'pod_{k}{i}' for k in ('row', 'switch') for i in range(n + 1)] + [f'pod_up{i}' for i in range(n)]   # row / switch n: the menu's Extras row, no arrow
        m.widgets = {x: 0x30000000 + 0x100 * i for i, x in enumerate(names)}
        m.widgets['pod_scrollview'] = m.alloc(0x180)   # real memory: the payload reads its vtable word and paint hook
        for i in range(n + 1):   # a row is a zeroed widget_t (x 0, y 0, no parent): widget_to_local, stock's own code, turns the tap's x into the row's
            m.widgets[f'pod_row{i}'] = m.alloc(0x180); m.u.mem_write(m.widgets[f'pod_row{i}'], bytes(0x180))
            if i < n: m.props[(m.widgets[f'pod_up{i}'], 'x')], m.props[(m.widgets[f'pod_up{i}'], 'w')] = ZX, ZW
        m.props[(m.widgets['pod_scrollview'], 'h')] = 398   # the list's window: 7.6 rows of 18
        if data is not None: m.fs[MENU_FILE] = data
        m.call(on_row, a0=rows_s + 12 * mm_i, count=3000000)
        return m

    def state(m):
        """(labels top to bottom, shown flags, arrow flags, switch images) as the page was left."""
        pos = sorted((m.props.get((m.widgets[f'pod_row{i}'], 'y'), i * ROW_H), i) for i in range(n))
        sw = lambda i: [c[2] for c in m.log if c[0] == 'image_base_set_image' and c[1] == m.widgets[f'pod_switch{i}']]
        up = lambda i: bool(m.props.get((m.widgets[f'pod_up{i}'], 'visible'), 1))   # the arrow is a picture: shown or not
        return ([items[i] for _, i in pos], [sw(i)[-1] == 'sset_on' if sw(i) else None for _, i in pos], [up(i) for _, i in pos])

    def xstate(m):
        """(y, switch image) of the 19th row, the menu's Extras row, as the page was left; its switch image is None if never set."""
        sw = [c[2] for c in m.log if c[0] == 'image_base_set_image' and c[1] == m.widgets[f'pod_switch{n}']]
        return m.props.get((m.widgets[f'pod_row{n}'], 'y'), n * ROW_H), (sw[-1] if sw else None)

    def run(m, fn):
        """Call fn and keep the whole log: the machine forgets its calls at each call."""
        log = getattr(m, 'log', [])
        fn()
        m.log = log + m.calls

    # 18. The page lays out the saved list: the shown items first, in order, then the hidden ones; arrows on the shown ones but the first
    D = P.DEFAULT_MENU
    dflt = [items[i] for i in D] + [items[i] for i in range(n) if i not in D]   # the default menu, then the hidden items in default order
    m = open_page(); m.log = list(m.calls)
    labels, on, up = state(m)
    expect(labels == dflt and labels[0] == 'Cover Flow' and labels[6] == 'Now Playing' and on == [True] * 6 + [False] * 12 and up == [False] + [True] * 5 + [False] * 12,
           f'default: the six shown items on top, Now Playing, Genres, Folders and the nine Extras items off below, an arrow on each shown item but the first ({labels}, {on}, {up})')
    expect(all(('widget_on', m.widgets['pod_row3'], O[e]) in [c[:3] for c in m.calls] for e in ('EVT_CLICK', 'EVT_POINTER_DOWN', 'EVT_POINTER_UP', 'EVT_POINTER_ABORT'))
           and not any(c[0] == 'widget_on' and c[1] == m.widgets['pod_up3'] for c in m.calls)
           and m.names().count('widget_on') == 2 + 4 * (n + 1) + 1, 'each row (the Extras row too) is bound (click, pointer down, up, abort), no arrow is (and the window destroy)')
    m = open_page(b'6502\n'); m.log = list(m.calls)
    labels, on, up = state(m)
    expect(labels[:4] == ['Shuffle', 'Playlists', 'Now Playing', 'Albums'] and labels[4:] == ['Cover Flow', 'Artists', 'Songs', 'Genres', 'Folders'] + items[9:]
           and on == [True] * 4 + [False] * 14 and up == [False, True, True, True] + [False] * 14, f'a saved list is laid out as saved ({labels}, {on})')
    stack = lambda m: [next(i for i in range(n + 1) if m.widgets[f'pod_row{i}'] == c[1]) for c in m.calls if c[0] == 'widget_restack']
    expect(stack(m) == [6, 5, 0, 2, 1, 3, 4] + list(range(7, n + 1)), f'the rows are restacked in page order (a relayout keeps it): {stack(m)}')
    m = open_page(b'xx'); m.log = list(m.calls)
    expect(state(m)[0] == dflt and state(m)[1][:6] == [True] * 6 and state(m)[1][6] is False, 'a corrupt list: the defaults')
    expect([c[2] for c in m.calls if c[0] == 'widget_restack'] == list(range(n + 1)), 'and the children index follows the page order')
    m = open_page(b'e0i\n'); m.log = list(m.calls)
    labels, on, up = state(m)
    expect(labels[:3] == ['Composers', 'Now Playing', 'CD Ripper'] and labels[3:] == [x for x in items if x not in labels[:3]]
           and on == [True] * 3 + [False] * 15 and up == [False, True, True] + [False] * 15,
           f'Extras items in a saved list come first in their place, the rest follow in default order ({labels[:5]})')
    m = open_page(b'012345678abcdefghi\n'); m.log = list(m.calls)
    labels, on, up = state(m)
    expect(labels == items and all(on) and up == [False] + [True] * 17, 'all eighteen shown: an arrow on every row but the first')
    m = open_page(b'0123456j\n'); m.log = list(m.calls)
    labels, on, up = state(m)
    expect(labels == dflt and on == [True] * 6 + [False] * 12 and not m.fs.get(MENU_FILE) == b'', 'a saved list with the retired j (Screenshot): the defaults')

    # 19. A switch (the row's tap) hides an item (it leaves the list) or shows it (it joins the end); saved at once, atomically
    m = open_page(); m.log = list(m.calls)
    run(m, lambda: m.click('pod_row1'))   # Cover Flow off
    expect(m.fs.get(MENU_FILE) == b'23456x\n' and ('rename', MENU_TMP, MENU_FILE) in m.calls and MENU_TMP not in m.fs, f'hide Cover Flow: saved atomically ({m.fs.get(MENU_FILE)!r})')
    labels, on, up = state(m)
    expect(labels == items[2:7] + items[:2] + items[7:] and on == [True] * 5 + [False] * 13
           and up == [False] + [True] * 4 + [False] * 13, f'it moves to the hidden group (default order after the shown ones), its switch off ({labels}, {on})')
    run(m, lambda: m.click('pod_row8'))   # Folders on
    expect(m.fs.get(MENU_FILE) == b'234568x\n', f'show Folders: it joins the end ({m.fs.get(MENU_FILE)!r})')
    labels, on, up = state(m)
    expect(labels[:6] == ['Albums', 'Artists', 'Songs', 'Playlists', 'Shuffle', 'Folders'] and labels[6:9] == ['Now Playing', 'Cover Flow', 'Genres']
           and on == [True] * 6 + [False] * 12, f'and is the last shown row ({labels})')
    run(m, lambda: m.click('pod_row0'))   # Now Playing, hidden by default, on: it joins the end
    expect(m.fs.get(MENU_FILE) == b'2345680x\n' and state(m)[0][6] == 'Now Playing' and state(m)[1][6] is True, 'show Now Playing (hidden by default): it joins the end')
    run(m, lambda: m.click('pod_row0'))   # hide it
    run(m, lambda: m.click('pod_row0'))   # show it again: it is last
    expect(m.fs.get(MENU_FILE) == b'2345680x\n', 'hide and show again: the item goes to the end')
    # an Extras item (Favorites, id 9, character 'a') is shown like any other: it joins the end, in the saved file as 'a'
    run(m, lambda: m.click('pod_row9'))
    expect(m.fs.get(MENU_FILE) == b'2345680ax\n' and state(m)[0][7] == 'Favorites' and state(m)[1][7] is True and state(m)[2][7] is True,
           f'show Favorites: it joins the end as "a", with its switch on and an arrow ({m.fs.get(MENU_FILE)!r})')
    run(m, lambda: arrow(m, 9))
    expect(m.fs.get(MENU_FILE) == b'234568a0x\n' and state(m)[0][6] == 'Favorites', 'its arrow moves it up one place, past Now Playing')
    run(m, lambda: m.click('pod_row17'))   # CD Ripper
    expect(m.fs.get(MENU_FILE) == b'234568a0ix\n' and state(m)[0][8] == 'CD Ripper', 'the last Extras item, CD Ripper, saves as "i"')
    run(m, lambda: m.click('pod_row9'))
    expect(m.fs.get(MENU_FILE) == b'2345680ix\n' and state(m)[1][:8] == [True] * 8 and state(m)[1][8] is False and 'Favorites' not in state(m)[0][:8],
           'and hidden again, it goes back to the hidden group')
    for i in range(n): run(m, lambda i=i: m.click(f'pod_row{i}') if P.ID_CHARS[i].encode() in m.fs[MENU_FILE].rstrip(b'\n') else None)
    expect(m.fs.get(MENU_FILE) == b'x\n' and all(x is False for x in state(m)[1]) and not any(state(m)[2]),
           'every item can be hidden (Extras and Settings stay on the menu): the list is empty, no arrow shows')
    for i in range(n): run(m, lambda i=i: m.click(f'pod_row{i}'))
    expect(m.fs.get(MENU_FILE) == b'012345678abcdefghix\n' and all(state(m)[1]) and len(m.fs[MENU_FILE]) < P.MENU_FILE_MAX,
           'and every item, all eighteen, can be shown again: the longest list fits the file cap')
    run(m, lambda: arrow(m, 17))
    expect(m.fs.get(MENU_FILE) == b'012345678abcdefgihx\n', 'arrows work down at the end of the long list (the page scrolls)')
    m = open_page(); m.fail.add(('write', MENU_TMP)); m.log = list(m.calls)
    run(m, lambda: m.click('pod_row1'))
    expect(MENU_FILE not in m.fs and state(m)[0] == dflt and state(m)[1][:6] == [True] * 6 and MENU_TMP not in m.fs,
           'a failed save is undone: the file, the order and the switches are as they were')

    # 19b. The 19th row, last: the menu's Extras row, a switch only (no arrow, never reordered); saved as the list's trailing 'x'
    m = open_page(); m.log = list(m.calls)
    expect(xstate(m) == (n * ROW_H, 'sset_on') and m.props.get((m.widgets[f'pod_row{n}'], 'y')) == n * ROW_H,
           f'default: the Extras row is the last row (y {n * ROW_H}) with its switch on ({xstate(m)})')
    expect(f'pod_up{n}' not in m.widgets and not any(c[0] in ('widget_set_visible', 'widget_set_sensitive') and c[1] == m.widgets[f'pod_row{n}'] for c in m.calls),
           'it has no arrow widget and the row is not hidden or disabled')
    m = open_page(b'123456\n'); m.log = list(m.calls)
    expect(xstate(m) == (n * ROW_H, 'sset_off') and state(m)[0] == dflt, f'a list without x (also an old 123456 file): the switch is off, the items are as saved ({xstate(m)})')
    m = open_page(b'\n'); m.log = list(m.calls)
    expect(xstate(m)[1] == 'sset_off' and state(m)[1] == [False] * n, 'an empty list: no item, no Extras')
    m = open_page(b'xx\n'); m.log = list(m.calls)
    expect(xstate(m)[1] == 'sset_on' and state(m)[0] == dflt, 'a corrupt list (x twice): the defaults, Extras on')
    m = open_page(); m.log = list(m.calls)
    run(m, lambda: m.click(f'pod_row{n}'))   # Extras off
    expect(m.fs.get(MENU_FILE) == b'123456\n' and ('rename', MENU_TMP, MENU_FILE) in m.calls and MENU_TMP not in m.fs, f'hide Extras: saved atomically, no x ({m.fs.get(MENU_FILE)!r})')
    expect(xstate(m) == (n * ROW_H, 'sset_off') and state(m)[0] == dflt and state(m)[1][:6] == [True] * 6, 'its switch is off, the items did not move')
    mm = open_menu(m.fs[MENU_FILE])
    expect(shown_order(mm) == [items[i] for i in D] + ['Settings'], f'the menu then ends with Settings, no Extras ({shown_order(mm)})')
    run(m, lambda: m.click(f'pod_row{n}'))   # Extras on
    expect(m.fs.get(MENU_FILE) == b'123456x\n' and xstate(m)[1] == 'sset_on', f'show Extras again: x is back, last ({m.fs.get(MENU_FILE)!r})')
    run(m, lambda: m.click(f'pod_row{n}', x=ZX + ZW // 2))   # the tap lands where item rows have an arrow: here it is a plain toggle
    expect(m.fs.get(MENU_FILE) == b'123456\n' and state(m)[0] == dflt, 'a tap in the arrow zone of the Extras row toggles it too (it has no arrow)')
    run(m, lambda: m.click(f'pod_row{n}')); run(m, lambda: m.click('pod_row3')); run(m, lambda: arrow(m, 4))
    expect(m.fs.get(MENU_FILE) == b'14256x\n', f'items change and move with Extras on: x stays last ({m.fs.get(MENU_FILE)!r})')
    run(m, lambda: m.click(f'pod_row{n}')); run(m, lambda: arrow(m, 5))
    expect(m.fs.get(MENU_FILE) == b'14526\n' and xstate(m)[0] == n * ROW_H,
           'with Extras off, items still move; the Extras row stays last on the page and the list has no x')
    for i in range(n): run(m, lambda i=i: m.click(f'pod_row{i}') if P.ID_CHARS[i].encode() in m.fs[MENU_FILE].rstrip(b'\n') else None)
    expect(m.fs.get(MENU_FILE) == b'\n' and xstate(m)[0] == n * ROW_H, 'every item and Extras hidden: an empty list; only Settings remains in the menu')
    for i in range(n): run(m, lambda i=i: m.click(f'pod_row{i}'))
    run(m, lambda: m.click(f'pod_row{n}'))
    expect(m.fs.get(MENU_FILE) == b'012345678abcdefghix\n' and len(m.fs[MENU_FILE]) < P.MENU_FILE_MAX and state(m)[1] == [True] * n and xstate(m)[1] == 'sset_on',
           'all eighteen items and Extras shown: the longest list, x last, fits the file cap')
    m = open_page(); m.fail.add(('write', MENU_TMP)); m.log = list(m.calls)
    run(m, lambda: m.click(f'pod_row{n}'))
    expect(MENU_FILE not in m.fs and MENU_TMP not in m.fs and xstate(m)[1] == 'sset_on' and m.names().count('widget_move') == 0 and 'widget_invalidate_force' not in m.names(),
           'a failed save of the Extras switch is undone: no file, the switch is still on, nothing re-laid out')
    m = open_page(); m.fail.add(('rename', MENU_FILE)); m.log = list(m.calls)
    run(m, lambda: m.click(f'pod_row{n}'))
    expect(MENU_FILE not in m.fs and xstate(m)[1] == 'sset_on', 'a failed rename: the same')
    m = open_page(b'123456\n'); m.log = list(m.calls)
    run(m, lambda: m.click('pod_row1'))
    expect(m.fs.get(MENU_FILE) == b'23456\n', f'an item change with Extras off keeps it off ({m.fs.get(MENU_FILE)!r})')

    # 20. The up arrow: one place up among the shown items; saved at once
    m = open_page(); m.log = list(m.calls)
    run(m, lambda: arrow(m, 3))
    expect(m.fs.get(MENU_FILE) == b'132456x\n', f'Artists up: swaps with Albums ({m.fs.get(MENU_FILE)!r})')
    labels, on, up = state(m)
    expect(labels[:6] == ['Cover Flow', 'Artists', 'Albums', 'Songs', 'Playlists', 'Shuffle'], f'the rows moved ({labels})')
    for _ in range(1): run(m, lambda: arrow(m, 3))
    expect(m.fs.get(MENU_FILE) == b'312456x\n' and state(m)[0][0] == 'Artists' and state(m)[2][0] is False and state(m)[2][1] is True,
           'up again: to the top, where the arrow goes away and the next row gets one')
    run(m, lambda: arrow(m, 3))
    expect(m.fs.get(MENU_FILE) == b'12456x\n', 'the top row has no arrow: a tap on that spot is a toggle (it never moves a first item)')
    m = open_page(); m.log = list(m.calls); m.fail.add(('rename', MENU_FILE))
    run(m, lambda: arrow(m, 6))
    expect(MENU_FILE not in m.fs and state(m)[0] == dflt and state(m)[2] == [False] + [True] * 5 + [False] * 12, 'a failed save of a move is undone too')
    m = open_page()
    h = {x: m.widgets[x] for x in m.widgets if x.startswith('pod_up')}
    expect(all((h[f'pod_up{i}'], 0) in [c[1:3] for c in m.calls if c[0] == 'widget_set_visible'] and (h[f'pod_up{i}'], 0) in [c[1:3] for c in m.calls if c[0] == 'widget_set_sensitive']
               for i in (1, 0, 7, 8, 9, 17)), 'the arrows of the first shown and of the hidden items are hidden and insensitive (hidden widgets still hit-test)')

    # 20b. In place, at once: every change re-arranges the page (no reopen), repaints it whole, keeps the moved row in view
    def moves(m): return [c for c in m.calls if c[0] == 'widget_move']
    sv = lambda m: m.widgets['pod_scrollview']
    m = open_page(); m.log = list(m.calls)
    expect(('widget_invalidate_force', m.window) in m.calls, 'the page lays itself out and repaints whole at open')
    arrow(m, 3)
    expect(('widget_invalidate_force', m.window) in m.calls and len(moves(m)) >= 2 and 'image_base_set_image' in m.names(),
           'an arrow tap re-arranges (moves the rows, sets the switches) and invalidates the whole window')
    expect(m.props[(m.widgets['pod_row3'], 'y')] == 1 * ROW_H and m.props[(m.widgets['pod_row2'], 'y')] == 2 * ROW_H,
           'the tapped row is at its new place at once, and the one it passed is at its old one')
    # hit-testing: the arrow of the row now first is hidden and insensitive; the one under it shows
    arrow(m, 3)
    h = lambda x: m.widgets[x]
    expect(m.props[(h('pod_row3'), 'y')] == 0 and m.props[(h('pod_up3'), 'visible')] == 0 and m.props[(h('pod_up3'), 'sensitive')] == 0
           and m.props[(h('pod_up1'), 'visible')] == 1 and m.props[(h('pod_up1'), 'sensitive')] == 0,
           'to the top: its arrow is hidden, the next row shows one; every arrow is insensitive (a picture, the row takes the tap)')
    # the click contexts are item ids: the arrow of an item that moved still moves that item
    run(m, lambda: arrow(m, 1))
    expect(m.fs[MENU_FILE] == b'132456x\n', f'an arrow still moves its own item after rows moved ({m.fs[MENU_FILE]!r})')
    # a failed save changes nothing on the page (no move, no repaint)
    m = open_page(); m.fail.add(('write', MENU_TMP)); m.log = list(m.calls)
    arrow(m, 3)
    expect(m.names().count('widget_move') == 0 and 'image_base_set_image' not in m.names() and 'widget_invalidate_force' not in m.names(),
           'a failed save: the page is not touched')
    # the scroll position follows the moved row
    m = open_page()
    for i in range(9, 17): m.click(f'pod_row{i}')   # Favorites .. Tidal on: positions 6..13
    m.props[(sv(m), 'yoffset')] = 0
    m.click('pod_row17')   # CD Ripper joins at position 14 (y 728): the window scrolls down to it
    off = m.props[(sv(m), 'yoffset')]
    expect(off <= 14 * ROW_H and off + 398 >= 15 * ROW_H and off <= n * ROW_H - 398, f'a row shown far below scrolls into view (yoffset {off})')
    for _ in range(14):
        arrow(m, 17)
        off = m.props[(sv(m), 'yoffset')]
        top = m.props[(m.widgets['pod_row17'], 'y')]
        expect(off <= top and top + ROW_H <= off + 398 and off >= 0, f'an arrow keeps the moved row in view (row y {top}, yoffset {off})')
    expect(m.props[(m.widgets['pod_row17'], 'y')] == 0 and m.props[(sv(m), 'yoffset')] == 0, 'up to the top: the list is scrolled back to the top')

    # 21. What the page saved is what the menu shows, and the persistence survives a reboot (a new machine with the file)
    m = open_page(); m.log = list(m.calls)
    run(m, lambda: m.click('pod_row2')); run(m, lambda: arrow(m, 6)); run(m, lambda: m.click('pod_row7'))
    saved = m.fs[MENU_FILE]
    expect(saved == b'134657x\n', f'hide Albums, Shuffle up, show Genres: {saved!r}')
    run(m, lambda: m.click('pod_row11')); run(m, lambda: m.click('pod_row13')); saved = m.fs[MENU_FILE]
    expect(saved == b'134657cex\n', f'and show Recently Played and Composers: {saved!r}')
    want = [P.ITEMS[i].label for i in P.parse_menu(saved)] + ['Extras', 'Settings']
    mm = open_menu(saved)
    expect(shown_order(mm) == want and 'Albums' not in want, f'the menu after the page ({want})')
    again = open_page(saved); again.log = list(again.calls)
    expect(state(again)[0][:len(want) - 2] == want[:-2], 'and the page opens with it again')

    # 22. The assets: a row per item in the default order, each with an up arrow and a switch; the page is the stock list
    path = os.path.join(WORK, UI, 'm1pod_mainmenu.bin')
    tree = awtk_ui.parse(open(path, 'rb').read())
    rows = [w for w in tree.walk() if w.type == 'list_item']
    expect([pod_i18n.shown_english(next(c for c in r.children if c.type == 'hscroll_label')) for r in rows] == items + ['Extras']
           and [r.name for r in rows] == [f'pod_row{i}' for i in range(n + 1)],
           'nineteen rows named pod_row0..18: the eighteen items in the default order, then the menu\'s Extras row')
    lv = tree.find('pod_listview')
    expect(lv.type == 'list_view' and lv.children[0].type == 'scroll_view' and tree.find('scroll_bar_m') is not None and lv.y + lv.h == CLIENT_H
           and max(r.y + r.h for r in rows) == (n + 1) * ROW_H > lv.h,
           'stock list_view > scroll_view + scroll bar (nineteen 52 px rows scroll), ending at the window bottom')
    xr = rows[n]   # the 19th row: the Extras switch, same look as the other switch rows, but no arrow and not reorderable
    xsw, xlab = xr.find(f'pod_switch{n}'), next(c for c in xr.children if c.type == 'hscroll_label')
    expect(xr.find(f'pod_up{n}') is None and not [w for w in xr.walk() if w.name.startswith('pod_up')] and (xsw.w, xsw.h) == (57, 28)
           and xsw.get('image') == 'sset_on' and xsw.get('sensitive') == 'false' and xsw.y == (ROW_H - 28) // 2 and xsw.x + xsw.w == xr.w - 12
           and xr.find('pod_icon') is not None and xr.y == n * ROW_H and xlab.x == rows[0].children[[c.type for c in rows[0].children].index('hscroll_label')].x,
           'the Extras row is the last row: the same switch image (on by default), the icon disc and label of the others, no up arrow')
    for i, r in enumerate(rows[:n]):
        swi, upb = r.find(f'pod_switch{i}'), r.find(f'pod_up{i}')
        lab = next(c for c in r.children if c.type == 'hscroll_label')
        expect(swi.type == 'image' and swi.get('image') == ('sset_on' if i in P.DEFAULT_MENU else 'sset_off') and (swi.w, swi.h) == (57, 28)
               and swi.get('sensitive') == 'false' and swi.y == (ROW_H - 28) // 2 and swi.x + swi.w == r.w - 12,
               f'row {i}: the stock 57x28 switch image, insensitive, 12 px from the right')
        expect(upb.type == 'button' and upb.get('style:normal:icon') == 'expansion_2' and upb.get('style:pressed:icon') == 'expansion_2_down' and upb.get('sensitive') == 'false'
               and upb.x + upb.w == swi.x and upb.h == ROW_H and (upb.x, upb.w) == (ZX, ZW) and upb.w >= 44,
               f'row {i}: the stock chevron-up art on an insensitive button (a picture) right of the label, left of the switch; its rectangle is the arrow zone')
        ic = r.find('pod_icon')
        expect(ic is not None and ic.get('sensitive') == 'false' and lab.x + lab.w <= upb.x, f'row {i}: icon disc, label clear of the arrow')
    m = Machine()
    tree_n = asset_tree(path)
    for i, r in enumerate(node(tree_n, 'pod_scrollview').children):
        y = 50 + r.y + r.h // 2
        if y >= CLIENT_H: continue
        for x in (160, r.x + 220, r.x + 270):
            got = stock_target(m, asset_tree(path), x, y)
            expect(f'pod_row{i}' in got and (got[-1] == f'pod_row{i}' or x == 160), f'row {i}: a touch at x {x} goes to the row ({got}): the arrow is a picture, the row decides by the position')
