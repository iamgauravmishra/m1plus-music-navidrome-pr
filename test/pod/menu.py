"""The entry hook and the M1 Pod menu: the Home icon dispatcher, the kill switch, the row actions, hit tests on the menu."""
import json, os, re, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)


def run(ctx):
    expect, page = ctx.expect, ctx.page
    entry = PSYMS['m1pod_home_click']
    binds = 2 + len(page.rows)                  # btn_return, btn_backtoplayer, then each row
    # 1. Entry icon, kill switch absent: opens the entry page, binds its widgets, no stock.
    m = Machine()
    m.widgets = {n: 0x30000000 + i for i, n in enumerate(
        ['btn_return', 'btn_backtoplayer', 'label_info'] + [f'pod_row{i}' for i in range(len(page.rows))])}
    v = m.call(entry, a0=m.icon(str(pod_pages.HOME_ENTRY)))
    names = m.names()
    expect(('window_open', page.key) in m.calls, f'entry opens {page.key}')
    expect('stock_resume' not in names, 'entry does not fall through to stock')
    expect(names.count('widget_on') == binds, f'binds navbar + {len(page.rows)} rows (got {names.count("widget_on")})')
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
