"""The entry hook and the M1 Pod menu: the Home icon dispatcher, the kill switch, the row actions, hit tests on the menu."""
import json, os, re, struct, sys
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
    #    HiFi store (Simplified Chinese only) and must no longer trigger M1 Pod.
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
    rows = [c for c in sv.children] if sv else []
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
    n_items = len(P.ITEMS)
    expect(page.rows[ex_i].action == P.ACT_PAGE and P.PAGES[page.rows[ex_i].arg] is ex, 'the Extras row opens the Extras page')
    want = [('Favorites', 10), ('Recently Added', 13), ('Recently Played', 12), ('Most Played', 11), ('Composers', 8),
            ('Hi-Res', 9), ('Update Library', 2), ('Tidal', 1), ('CD Ripper', 15)]
    stock = ex.rows[n_items:]
    expect([(r.label, r.arg) for r in stock] == want and all(r.action == P.ACT_HOME for r in stock),
           'Extras lists the nine stock Home tiles by id, after a row for every menu item')
    expect([(r.label, r.action, r.arg) for r in ex.rows[:n_items]] == [(r.label, r.action, r.arg) for r in P.ITEMS],
           'its first rows mirror the menu items (same labels and actions), so a hidden item opens the same way from Extras')
    shown = {r.arg for r in page.rows if r.action == P.ACT_HOME} | {r.arg for r in P.SETTINGS_PAGE.rows if r.action == P.ACT_HOME}
    expect(not shown & {r.arg for r in stock} and len(shown) + len(stock) + 3 == 18,
           'no tile is twice (Albums, id 5, and Artists, id 6, are the payload pages; HiFi, id 0, is left out)')
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
    return m


def arranged(m, rows):
    """{row index: (y, shown)} as the payload's calls left the page; a row it never touched is absent."""
    out = {}
    for i in range(rows):
        h = m.widgets[f'pod_row{i}']
        if (h, 'visible') in m.props: out[i] = (m.props.get((h, 'y'), 0), bool(m.props[(h, 'visible')]) and bool(m.props.get((h, 'sensitive'), 1)))
    return out


def open_menu(data=None, rows=11, present=()):
    m = page_machine(rows)
    if data is not None: m.fs[MENU_FILE] = data
    m.call(PSYMS['m1pod_home_click'], a0=m.icon(str(pod_pages.HOME_ENTRY)), count=3000000)
    return m


def shown_order(m, rows=11):
    """The labels of the shown rows of the page, top to bottom, from the arrangement."""
    a = arranged(m, rows)
    return [pod_pages.MENU.rows[i].label for _, i in sorted((y, i) for i, (y, on) in a.items() if on)]


def arrange_tests(ctx, entry, on_row, rows0, rows_ex, ex_i):
    expect, P = ctx.expect, pod_pages
    items = [r.label for r in P.ITEMS]
    default = ['Now Playing', 'Cover Flow', 'Albums', 'Artists', 'Songs', 'Playlists', 'Shuffle', 'Extras', 'Settings']
    ROW_H = pod_ui.ROW_H

    # 9. The default menu: essentials first, iPod classic style; Genres and Folders are in Extras; Extras and Settings last.
    expect(items == ['Now Playing', 'Cover Flow', 'Albums', 'Artists', 'Songs', 'Playlists', 'Shuffle', 'Genres', 'Folders']
           and P.DEFAULT_VISIBLE == 7 and P.parse_menu(None) == list(range(7)), 'the asset order is the default order, the first seven shown')
    m = open_menu()
    expect(shown_order(m) == default, f'no saved list: the default menu ({shown_order(m)})')
    a = arranged(m, 11)
    expect(all(a[i] == (i * ROW_H, True) for i in range(7)) and a[9] == (7 * ROW_H, True) and a[10] == (8 * ROW_H, True),
           f'the shown rows are consecutive 52 px steps from y 0, Extras and Settings right after them ({a})')
    expect(all(a[i] == (0, False) for i in (7, 8)), 'Genres and Folders are hidden (and insensitive) and parked at y 0')
    expect(('widget_set_prop_int', m.widgets['pod_scrollview'], 'virtual_h', 9 * ROW_H) in m.calls
           and ('widget_set_prop_int', m.widgets['pod_scrollview'], 'yoffset', 0) in m.calls,
           'the list scrolls over exactly the shown rows (virtual_h 9 x 52) from the top')
    expect(not any(c[0] in ('write', 'rename', 'unlink') for c in m.calls) and
           [c[1] for c in m.calls if c[0] == 'open'] == [MENU_FILE], 'opening the menu reads the list file and writes nothing')

    # 10. Saved lists: order, subsets, none at all
    for data, want in ((b'6543210\n', ['Shuffle', 'Playlists', 'Songs', 'Artists', 'Albums', 'Cover Flow', 'Now Playing']),
                       (b'078\n', ['Now Playing', 'Genres', 'Folders']), (b'3\n', ['Artists']), (b'0123456', items[:7]),
                       (b'876543210\n', items[::-1]), (b'\n', [])):
        m = open_menu(data)
        want = want + ['Extras', 'Settings']
        expect(shown_order(m) == want, f'saved {data!r}: {want}')
        a = arranged(m, 11)
        n = len(want) - 2
        expect(a[9] == (n * ROW_H, True) and a[10] == ((n + 1) * ROW_H, True),
               f'saved {data!r}: Extras and Settings are always shown, always last ({a[9]}, {a[10]})')
        expect(('widget_set_prop_int', m.widgets['pod_scrollview'], 'virtual_h', (n + 2) * ROW_H) in m.calls, f'saved {data!r}: virtual_h follows')

    # 11. Anything invalid is the default list: unknown ids, duplicates, too long, empty, binary, text after the list
    bad = [b'9\n', b'0129\n', b'00\n', b'01234567801\n', b'0123456789\n', b'', b'x', b'01 2\n', b'01\n\n', b'\n\n', b'0\r\n',
           b'0123456780123456', b'a' * 200, bytes(range(256)), b'01\x002\n', b'-1\n', b'0123456789012345678901234567890123456789\n', b'0' * 1000000]
    for data in bad:
        m = open_menu(data)
        expect(shown_order(m) == default and P.parse_menu(data) == list(range(7)), f'saved {data[:20]!r} ({len(data)} bytes): the default menu')
        expect(m.icount < 200000, f'saved {len(data)} bytes: read is bounded, the open stays cheap ({m.icount} instructions)')
    # the Python model of the parser (tools/pod_pages.py parse_menu, which the docs and previews use) agrees with the payload
    import random
    rnd = random.Random(7)
    for _ in range(120):
        n = rnd.choice((0, 1, 2, 5, 9, 10, 11, 15, 16, 17))
        data = bytes(rnd.choice(b'0123456789\n x') if rnd.random() < 0.3 else rnd.choice(b'012345678') for _ in range(n))
        m = open_menu(data, rows=11)
        want = [P.MENU.rows[i].label for i in P.parse_menu(data)] + ['Extras', 'Settings']
        if shown_order(m) != want: expect(False, f'parser model differs for {data!r}: {shown_order(m)} vs {want}'); break
    else: expect(True, 'the payload reads 120 random lists as the Python model does')
    m = open_menu(b'0\n'); m.fs[MENU_FILE] = b'0\n'
    expect(m.fs[MENU_FILE] == b'0\n', 'a valid list is never rewritten by reading it')

    # 11b. A page that is not ours (a row or the list missing) is left exactly as the asset has it
    for gone in ('pod_scrollview', 'pod_row5', 'pod_row10'):
        m = page_machine(11); m.widgets.pop(gone); m.call(PSYMS['m1pod_home_click'], a0=m.icon(str(P.HOME_ENTRY)), count=3000000)
        expect(('window_open', P.MENU.key) in m.calls and not any(c[0] in ('widget_move', 'widget_set_visible', 'widget_set_sensitive') for c in m.calls),
               f'no {gone}: the menu opens as the asset has it, nothing moved or hidden')

    # 12. Extras: first the items the menu hides, then the stock tiles
    def extras(data=None):
        m = page_machine(18)
        if data is not None: m.fs[MENU_FILE] = data
        m.call(on_row, a0=rows0 + 12 * ex_i, count=3000000)
        a = arranged(m, 18)
        order = [(P.EXTRAS_PAGE.rows[i].label) for _, i in sorted((y, i) for i, (y, on) in a.items() if on)]
        return m, order, a
    stock = [r.label for r in P.EXTRAS_PAGE.rows[len(P.ITEMS):]]
    m, order, a = extras()
    expect(order == ['Genres', 'Folders'] + stock, f'default: Genres and Folders first, then the stock tiles ({order})')
    expect(all(a[i] == (0, False) for i in range(7)) and ('widget_set_prop_int', m.widgets['pod_scrollview'], 'virtual_h', 11 * ROW_H) in m.calls,
           'the items the menu shows are hidden here, the list is eleven rows long')
    m, order, a = extras(b'\n')
    expect(order == items + stock, 'every item hidden: all nine are at the top of Extras, in the default order')
    m, order, a = extras(b'012345678\n')
    expect(order == stock and all(a[i] == (0, False) for i in range(9)), 'nothing hidden: Extras is only the stock tiles')
    m, order, a = extras(b'0345\n')
    expect(order[:5] == ['Cover Flow', 'Albums', 'Shuffle', 'Genres', 'Folders'] and order[5:] == stock,
           f'a hidden item is in Extras whatever order it had: {order[:5]}')
    m, order, a = extras(b'zz')
    expect(order == ['Genres', 'Folders'] + stock, 'an invalid list: the default split')
    # no item is ever in neither place, in any saved list
    for data in (None, b'\n', b'8\n', b'0123\n', b'87654321\n', b'0123456\n'):
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
    for data in (None, b'6543210\n', b'\n', b'01234\n'):
        m = open_menu(data)
        tree = asset_tree(os.path.join(WORK, UI, 'm1pod_menu.bin'))
        for i, row in enumerate(node(tree, 'pod_scrollview').children):
            h = m.widgets[f'pod_row{i}']
            if (h, 'y') in m.props: row.y = m.props[(h, 'y')]
            if (h, 'visible') in m.props: row.flags = (row.flags & ~F_VISIBLE) | (F_VISIBLE if m.props[(h, 'visible')] else 0)
            if (h, 'sensitive') in m.props: row.flags = (row.flags & ~F_SENSITIVE) | (F_SENSITIVE if m.props[(h, 'sensitive')] else 0)
        a = arranged(m, 11)
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
    m.fs[MENU_FILE] = b'4\n'
    m.call(fg[0][3], a0=fg[0][4], count=3000000)
    expect(shown_order(m) == ['Songs', 'Extras', 'Settings'], f'back in front it shows the new list ({shown_order(m)})')


def settings_tests(ctx, on_row, rows0):
    expect, P = ctx.expect, pod_pages
    S = P.SETTINGS_PAGE
    rows_s = PSYMS[f'pod_rows_{P.SETTINGS_PAGE_INDEX}']
    sw = lambda i: f'pod_switch{i}'
    start_i = next(i for i, r in enumerate(S.rows) if r.action == P.ACT_STARTUP)
    mm_i = next(i for i, r in enumerate(S.rows) if r.action == P.ACT_PAGE and r.arg == P.MENUCFG_PAGE_INDEX)
    cf_i = next(i for i, r in enumerate(S.rows) if r.action == P.ACT_PAGE and r.arg == P.CFSET_PAGE_INDEX)
    settings_i = next(i for i, r in enumerate(P.MENU.rows) if r.action == P.ACT_PAGE and r.arg == P.SETTINGS_PAGE_INDEX)

    def open_settings():
        m = Machine()
        m.widgets = {n: 0x30000000 + 0x100 * i for i, n in enumerate(
            ['btn_return', 'btn_backtoplayer'] + [f'pod_row{i}' for i in range(len(S.rows))] + [sw(start_i)])}
        m.call(on_row, a0=rows0 + 12 * settings_i, count=3000000)
        return m

    # 15. Settings: Main Menu, Cover Flow (a sub-page), the Start in switch, Playback, System Settings, Shanling Home; always reachable from the menu, in any saved list
    expect([r.label for r in S.rows] == ['Main Menu', 'Cover Flow', 'Start in M1 Pod', 'Playback', 'System Settings', 'Shanling Home'],
           'the Settings page lists Main Menu, Cover Flow, the Start in switch, Playback, System Settings and Shanling Home')
    expect(S.rows[3].label == 'Playback' and (S.rows[3].action, S.rows[3].arg) == (P.ACT_HOME, P.HOME_PLAYSET)
           and (S.rows[4].action, S.rows[4].arg) == (P.ACT_HOME, P.HOME_SYSSET), 'Playback opens the stock Play settings page, System Settings the stock one')
    for data in (None, b'\n', b'0123456\n', b'87\n', b'zz'):
        m = open_menu(data)
        a = arranged(m, 11)
        expect(a[10][1] and a[9][1] and a[10][0] == a[9][0] + pod_ui.ROW_H, f'saved {data!r}: the Settings row is shown and reachable')
        expect(('widget_on', m.widgets['pod_row10'], O['EVT_CLICK']) in [c[:3] for c in m.calls], f'saved {data!r}: the Settings row is bound')
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
    expect([(r.label, r.action) for r in C.rows] == [('Landscape', P.ACT_LANDSCAPE), ('Sort', P.ACT_SORT)] and C.title == 'Cover Flow',
           'the Cover Flow page: titled Cover Flow, rows Landscape (switch) and Sort (value)')

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
        T = lambda key: pod_i18n.TEXT[key][pod_i18n.table_for(loc)].encode('utf-8').decode('latin-1')
        m = open_cf(language=loc)
        expect(label(m) == ('Artist', T('Artist')), f'{loc}: Artist reads {T("Artist")!r}')
        m.click(f'pod_row{sort_i}')
        expect(label(m)[0] == 'album', f'{loc}: Album is the stock key album')
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

    def open_page(data=None):
        m = Machine()
        names = ['btn_return', 'btn_backtoplayer'] + [f'pod_{k}{i}' for k in ('row', 'switch', 'up') for i in range(n)]
        m.widgets = {x: 0x30000000 + 0x100 * i for i, x in enumerate(names)}
        if data is not None: m.fs[MENU_FILE] = data
        m.call(on_row, a0=rows_s + 12 * mm_i, count=3000000)
        return m

    def state(m):
        """(labels top to bottom, shown flags, arrow flags, switch images) as the page was left."""
        pos = sorted((m.props.get((m.widgets[f'pod_row{i}'], 'y'), i * ROW_H), i) for i in range(n))
        sw = lambda i: [c[2] for c in m.log if c[0] == 'image_base_set_image' and c[1] == m.widgets[f'pod_switch{i}']]
        up = lambda i: bool(m.props.get((m.widgets[f'pod_up{i}'], 'visible'), 1)) and bool(m.props.get((m.widgets[f'pod_up{i}'], 'sensitive'), 1))
        return ([items[i] for _, i in pos], [sw(i)[-1] == 'sset_on' if sw(i) else None for _, i in pos], [up(i) for _, i in pos])

    def run(m, fn):
        """Call fn and keep the whole log: the machine forgets its calls at each call."""
        log = getattr(m, 'log', [])
        fn()
        m.log = log + m.calls

    # 18. The page lays out the saved list: the shown items first, in order, then the hidden ones; arrows on the shown ones but the first
    m = open_page(); m.log = list(m.calls)
    labels, on, up = state(m)
    expect(labels == items and on == [True] * 7 + [False] * 2 and up == [False] + [True] * 6 + [False] * 2,
           f'default: the seven shown items on top, Genres and Folders off below, an arrow on each shown item but the first ({labels}, {on}, {up})')
    expect(('widget_on', m.widgets['pod_row3'], O['EVT_CLICK']) in [c[:3] for c in m.calls] and ('widget_on', m.widgets['pod_up3'], O['EVT_CLICK']) in [c[:3] for c in m.calls]
           and m.names().count('widget_on') == 2 + 2 * n + 1, 'each row and each arrow is bound (and the window destroy)')
    m = open_page(b'6502\n'); m.log = list(m.calls)
    labels, on, up = state(m)
    expect(labels[:4] == ['Shuffle', 'Playlists', 'Now Playing', 'Albums'] and labels[4:] == ['Cover Flow', 'Artists', 'Songs', 'Genres', 'Folders']
           and on == [True] * 4 + [False] * 5 and up == [False, True, True, True] + [False] * 5, f'a saved list is laid out as saved ({labels}, {on})')
    m = open_page(b'xx'); m.log = list(m.calls)
    expect(state(m)[0] == items and state(m)[1][:7] == [True] * 7, 'a corrupt list: the defaults')

    # 19. A switch (the row's tap) hides an item (it leaves the list) or shows it (it joins the end); saved at once, atomically
    m = open_page(); m.log = list(m.calls)
    run(m, lambda: m.click('pod_row1'))   # Cover Flow off
    expect(m.fs.get(MENU_FILE) == b'023456\n' and ('rename', MENU_TMP, MENU_FILE) in m.calls and MENU_TMP not in m.fs, f'hide Cover Flow: saved atomically ({m.fs.get(MENU_FILE)!r})')
    labels, on, up = state(m)
    expect(labels == ['Now Playing', 'Albums', 'Artists', 'Songs', 'Playlists', 'Shuffle', 'Cover Flow', 'Genres', 'Folders'] and on == [True] * 6 + [False] * 3
           and up == [False] + [True] * 5 + [False] * 3, f'it moves to the hidden group (default order after the shown ones), its switch off ({labels}, {on})')
    run(m, lambda: m.click('pod_row8'))   # Folders on
    expect(m.fs.get(MENU_FILE) == b'0234568\n', f'show Folders: it joins the end ({m.fs.get(MENU_FILE)!r})')
    labels, on, up = state(m)
    expect(labels[:7] == ['Now Playing', 'Albums', 'Artists', 'Songs', 'Playlists', 'Shuffle', 'Folders'] and labels[7:] == ['Cover Flow', 'Genres']
           and on == [True] * 7 + [False] * 2, f'and is the last shown row ({labels})')
    run(m, lambda: m.click('pod_row0'))   # hide the first
    run(m, lambda: m.click('pod_row0'))   # show it again: it is now last
    expect(m.fs.get(MENU_FILE) == b'2345680\n', 'hide and show again: the item goes to the end')
    for i in range(n): run(m, lambda i=i: m.click(f'pod_row{i}') if f'{i}'.encode() in m.fs[MENU_FILE] else None)
    expect(m.fs.get(MENU_FILE) == b'\n' and all(x is False for x in state(m)[1]) and not any(state(m)[2]),
           'every item can be hidden (Extras and Settings stay on the menu): the list is empty, no arrow shows')
    for i in range(n): run(m, lambda i=i: m.click(f'pod_row{i}'))
    expect(m.fs.get(MENU_FILE) == b'012345678\n' and all(state(m)[1]), 'and every item can be shown again')
    m = open_page(); m.fail.add(('write', MENU_TMP)); m.log = list(m.calls)
    run(m, lambda: m.click('pod_row1'))
    expect(MENU_FILE not in m.fs and state(m)[0] == items and state(m)[1][:7] == [True] * 7 and MENU_TMP not in m.fs,
           'a failed save is undone: the file, the order and the switches are as they were')

    # 20. The up arrow: one place up among the shown items; saved at once
    m = open_page(); m.log = list(m.calls)
    run(m, lambda: m.click('pod_up3'))
    expect(m.fs.get(MENU_FILE) == b'0132456\n', f'Artists up: swaps with Albums ({m.fs.get(MENU_FILE)!r})')
    labels, on, up = state(m)
    expect(labels[:7] == ['Now Playing', 'Cover Flow', 'Artists', 'Albums', 'Songs', 'Playlists', 'Shuffle'], f'the rows moved ({labels})')
    for _ in range(2): run(m, lambda: m.click('pod_up3'))
    expect(m.fs.get(MENU_FILE) == b'3012456\n' and state(m)[0][0] == 'Artists' and state(m)[2][0] is False and state(m)[2][1] is True,
           'up again and again: to the top, where the arrow goes away and the next row gets one')
    run(m, lambda: m.click('pod_up3'))
    expect(m.fs.get(MENU_FILE) == b'3012456\n', 'an arrow that is not shown (top row) is not a place to tap, and a stray call changes nothing')
    m = open_page(); m.log = list(m.calls); m.fail.add(('rename', MENU_FILE))
    run(m, lambda: m.click('pod_up6'))
    expect(MENU_FILE not in m.fs and state(m)[0] == items and state(m)[2] == [False] + [True] * 6 + [False] * 2, 'a failed save of a move is undone too')
    m = open_page()
    h = {x: m.widgets[x] for x in m.widgets if x.startswith('pod_up')}
    expect(all((h[f'pod_up{i}'], 0) in [c[1:3] for c in m.calls if c[0] == 'widget_set_visible'] and (h[f'pod_up{i}'], 0) in [c[1:3] for c in m.calls if c[0] == 'widget_set_sensitive']
               for i in (0, 7, 8)), 'the arrows of the first shown and of the hidden items are hidden and insensitive (hidden widgets still hit-test)')

    # 21. What the page saved is what the menu shows, and the persistence survives a reboot (a new machine with the file)
    m = open_page(); m.log = list(m.calls)
    run(m, lambda: m.click('pod_row2')); run(m, lambda: m.click('pod_up6')); run(m, lambda: m.click('pod_row7'))
    saved = m.fs[MENU_FILE]
    expect(saved == b'0134657\n', f'hide Albums, Shuffle up, show Genres: {saved!r}')
    want = [P.ITEMS[i].label for i in P.parse_menu(saved)] + ['Extras', 'Settings']
    mm = open_menu(saved)
    expect(shown_order(mm) == want and 'Albums' not in want, f'the menu after the page ({want})')
    again = open_page(saved); again.log = list(again.calls)
    expect(state(again)[0][:len(want) - 2] == want[:-2], 'and the page opens with it again')

    # 22. The assets: a row per item in the default order, each with an up arrow and a switch; the page is the stock list
    path = os.path.join(WORK, UI, 'm1pod_mainmenu.bin')
    tree = awtk_ui.parse(open(path, 'rb').read())
    rows = [w for w in tree.walk() if w.type == 'list_item']
    expect([pod_i18n.shown_english(next(c for c in r.children if c.type == 'hscroll_label')) for r in rows] == items and [r.name for r in rows] == [f'pod_row{i}' for i in range(n)],
           'nine rows named pod_row0..8 in the default order')
    lv = tree.find('pod_listview')
    expect(lv.type == 'list_view' and lv.children[0].type == 'scroll_view' and tree.find('scroll_bar_m') is not None and lv.y + lv.h == CLIENT_H,
           'stock list_view > scroll_view + scroll bar (nine 52 px rows scroll), ending at the window bottom')
    for i, r in enumerate(rows):
        swi, upb = r.find(f'pod_switch{i}'), r.find(f'pod_up{i}')
        lab = next(c for c in r.children if c.type == 'hscroll_label')
        expect(swi.type == 'image' and swi.get('image') == ('sset_on' if i < 7 else 'sset_off') and (swi.w, swi.h) == (57, 28)
               and swi.get('sensitive') == 'false' and swi.y == (ROW_H - 28) // 2 and swi.x + swi.w == r.w - 12,
               f'row {i}: the stock 57x28 switch image, insensitive, 12 px from the right')
        expect(upb.type == 'button' and upb.get('style:normal:icon') == 'expansion_2' and upb.get('style:pressed:icon') == 'expansion_2_down'
               and upb.x + upb.w == swi.x and upb.h == ROW_H, f'row {i}: the stock chevron-up art on a button right of the label, left of the switch')
        ic = r.find('pod_icon')
        expect(ic is not None and ic.get('sensitive') == 'false' and lab.x + lab.w <= upb.x, f'row {i}: icon disc, label clear of the arrow')
    m = Machine()
    tree_n = asset_tree(path)
    for i, r in enumerate(node(tree_n, 'pod_scrollview').children):
        y = 50 + r.y + r.h // 2
        if y >= CLIENT_H: continue
        for x, want in ((160, f'pod_row{i}'), (r.x + 220, f'pod_up{i}'), (r.x + 270, f'pod_row{i}')):
            got = stock_target(m, asset_tree(path), x, y)
            expect(want in got and (got[-1] == want or x == 160), f'row {i}: a touch at x {x} goes to {want} ({got}): the arrow takes its own touch, the switch image the row')
