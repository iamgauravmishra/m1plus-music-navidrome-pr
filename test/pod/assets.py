"""Built assets: the M1 Pod pages are dark with light text and inside the window, the default wallpaper, the icon set and the battery art."""
import hashlib, json, os, re, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)


def run(ctx):
    expect, page = ctx.expect, ctx.page
    ui_dir = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui')

    # 25. Contrast in the built assets: every button we style inline has a dark background and
    #     light text in every widget state (theme-styled navbar buttons excepted).
    for asset_name in ('m1pod_menu.bin', 'm1pod_cover.bin', 'm1pod_artists.bin', 'm1pod_shuffle.bin', 'm1pod_settings.bin', 'm1pod_cfset.bin'):
        tree = awtk_ui.parse(open(os.path.join(ui_dir, asset_name), 'rb').read())
        for w in tree.walk():
            if w.type == 'list_item':   # rows: stock's widget and theme styles, as sysset's rows
                labs = [c for c in w.children if c.type == 'hscroll_label']
                expect(w.get('style') == 'list_item_style' and labs
                       and labs[0].get('style') == 'srlabel_leftwhite21_style',
                       f'{asset_name}:{w.name} is a stock-styled row')
            if w.type != 'button' or w.get('style'): continue
            bad = [st for st in STATES if not is_dark(w.get(f'style:{st}:bg_color', ''))
                   or not is_light(w.get(f'style:{st}:text_color', ''))]
            expect(not bad, f'{asset_name}:{w.name} is dark with light text in every state ({bad})')
        for w in tree.children:   # the window's own children (scroll content may extend below)
            expect(w.y + w.h <= CLIENT_H,
                   f'{asset_name}:{w.name or w.type} ends inside the 450 px window ({w.y}+{w.h})')

    # 39. The default lock screen wallpaper: screensaver_default.png (the resource name demo keeps as
    #     SCREENSAVERPATH when no custom picture is set) is The Starry Night, a 320x480 PNG well
    #     under 150 KB; the other files are left alone and no theme shadows it.
    assets = os.path.join(WORK, 'rootfs', 'release', 'assets')
    img = os.path.join(assets, 'default', 'raw', 'images', 'xx', 'screensaver_default.png')
    data = open(img, 'rb').read()
    expect(data[:8] == b'\x89PNG\r\n\x1a\n' and struct.unpack('>II', data[16:24]) == (320, 480) and len(data) <= 150000,
           f'screensaver_default.png is a 320x480 PNG of {len(data)} bytes (<= 150,000)')
    import mod_wallpaper
    expect(hashlib.sha256(data).hexdigest() == mod_wallpaper.ASSET_SHA, 'it is assets/starry-night-320x480.png')
    expect(not any(f.startswith('screensaver_default.') for t in os.listdir(assets) if t != 'default'
                   for _, _, fs in os.walk(os.path.join(assets, t)) for f in fs),
           'no other theme carries a screensaver_default that would shadow it')
    expect(os.path.getsize(os.path.join(os.path.dirname(img), 'screensaver_default1.png')) == 521927, 'screensaver_default1.png is untouched')
    lock = awtk_ui.parse(open(os.path.join(ui_dir, 'screensaver_page.bin'), 'rb').read())
    expect(any(w.name == 'img_screensaver' for w in lock.walk()), 'the lock screen still has the img_screensaver the app feeds')

    # 40. The icon set: every replaced stock image is the committed Tabler PNG, byte for byte; the
    #     row icons the menu and the Shuffle page use are added and every row names one of them.
    import battery_art, mod_battery, mod_icons
    img_dir = os.path.join(WORK, mod_icons.IMG)
    names = mod_icons.replaced_names()
    # the three battery state images are the unified battery drawing, not Tabler
    own = {n: battery_art.png(battery_art.STATUS, s) for n, s in mod_battery.STATE.items()}
    tabler = [n for n in names if n not in own]
    differ = [n for n in tabler if open(os.path.join(img_dir, n + '.png'), 'rb').read() != open(os.path.join(mod_icons.PNG, n + '.png'), 'rb').read()]
    expect(not differ and len(tabler) > 100, f'{len(tabler)} replaced images are the committed PNGs (differ: {differ[:3]})')
    expect(all(open(os.path.join(img_dir, n + '.png'), 'rb').read() == png for n, png in own.items() if n in names) or not set(own) & set(names),
           'the status bar battery images are battery_art.png(STATUS)')
    added = mod_icons.pod_names()
    expect(all(open(os.path.join(img_dir, n + '.png'), 'rb').read() == open(os.path.join(mod_icons.PNG, n + '.png'), 'rb').read() for n in added),
           f'the {len(added)} M1 Pod row icons are added from the committed PNGs')
    used = set()
    for key in mod_icons.POD_UI:
        tree = awtk_ui.parse(open(os.path.join(ui_dir, key + '.bin'), 'rb').read())
        for row in [w for w in tree.walk() if w.type == 'list_item']:
            ic = [c for c in row.children if c.name == 'pod_icon']
            expect(len(ic) == 1 and ic[0].get('image') in added and ic[0].get('sensitive') == 'false',
                   f'{key}:{row.name} has one insensitive icon image from the added set')
            used.update(c.get('image') for c in ic)
    expect(used == set(mod_icons.pod_row_names()), 'every added row icon is used by a row')
    # the Home grid icon (patch/home.c builds the widget): its two 66x66 images and the style that names them
    import awtk_style
    for n in mod_icons.POD_HOME:
        im = mod_icons.read_png(os.path.join(img_dir, n + '.png'))
        expect(n in added and im.size == (66, 66), f'{n}.png is added (66x66, the stock Home icon size)')
    th = awtk_style.parse(open(os.path.join(WORK, mod_icons.HOME_STYLES), 'rb').read())
    items = th.find('image', mod_icons.POD_HOME_STYLE)
    expect([i.state for i in items] == [i.state for i in th.find('image', 'home_tidal_style')] and
           all(i.get('bg_image') == mod_icons.POD_HOME[i.state == 'pressed'] for i in items),
           'home_m1pod_style has the five states of the stock icon styles: m1pod, m1pod_down when pressed')
    expect(th.items.index(items[-1]) + 1 == min(k for k, i in enumerate(th.items) if i.widget == 'image' and i.style > mod_icons.POD_HOME_STYLE) and
           th.find('image', 'home_tidal_style')[0].get('bg_image') == 'tidal',
           'inserted in the stock sort order, and the Tidal icon keeps its image names')
    tidal = {i.get('bg_image') for i in th.find('image', 'home_tidal_style')}
    expect(tidal == {'tidal', 'tidal_down'} and all(
               open(os.path.join(img_dir, n + '.png'), 'rb').read() == open(os.path.join(mod_icons.PNG, n + '.png'), 'rb').read()
               and mod_icons.read_png(os.path.join(img_dir, n + '.png')).size == (66, 66) and n in {h[0] for h in mod_icons.HOME} | {h[0] + '_down' for h in mod_icons.HOME}
               for n in tidal),
           'every state of home_tidal_style shows the generated brand-tidal disc (tidal, tidal_down: 66x66, not the stock files)')
    expect(dict((n, g) for n, _, g in mod_icons.HOME)['tidal'] == 'brand-tidal' and mod_icons.POD_ROWS['Tidal'][1] == 'brand-tidal',
           'the Home grid and the Extras row both use Tabler\'s brand-tidal')
    # the Settings rows' icons: Now Playing's wave is the navbar button's glyph (Lucide audio-lines), Shanling Home's mark is cut
    # from the pinned stock shutdown screen (the committed disc is what the derivation makes), the rest are existing mappings
    glyphs = {n: g for n, g, _ in mod_icons.GLYPHS}
    expect(mod_icons.POD_ROWS['Now Playing'][1] == glyphs['back_to_player'] == '+audio-lines', 'the Now Playing row uses the wave glyph of the navbar\'s Now Playing button')
    from PIL import Image
    mark = Image.open(os.path.join(mod_icons.PNG, mod_icons.POD_ROWS['Shanling Home'][0] + '.png')).convert('RGBA')
    expect(mod_icons.POD_ROWS['Shanling Home'][1] == mod_icons.SHANLING and mark.tobytes() == mod_icons.on_disc(mod_icons.shanling_mark(), mod_icons.POD_ICON, mod_icons.DISC).tobytes(),
           'the Shanling Home row has the brand mark derived from the stock shutdown screen (pinned), on the 40 px disc')
    ink = [p for p in mark.getdata() if p[0] > 0xc0 and p[3] > 200]
    expect(len(ink) > 100 and mark.size == (40, 40), f'the mark is light ink on the grey disc ({len(ink)} px)')
    expect({'Main Menu', 'Cover Flow', 'Landscape', 'Sort', 'Start in M1 Pod', 'Playback'} <= set(mod_icons.POD_ROWS)
           and not {'Play Settings', 'Start in: M1 Pod', 'Cover Flow landscape'} & set(mod_icons.POD_ROWS)
           and not any(k.startswith('pod_nav_rotate') for k in mod_icons.NAV_VIEW), 'icons exist for the Settings rows and the Cover Flow page\'s, none for the old labels or the removed rotate button')
    expect(mod_icons.POD_ROWS['Landscape'][1] == 'rotate-clockwise' and mod_icons.POD_ROWS['Sort'][1] == 'sort-descending'
           and mod_icons.POD_ROWS['Cover Flow'][1] == 'carousel-horizontal' and 'm1pod_cfset' in mod_icons.POD_UI,
           'Settings > Cover Flow: the carousel row (also the menu\'s), the rotate glyph for Landscape, Tabler\'s sort-descending for Sort')
    lock_imgs = {n: open(os.path.join(img_dir, n + '.png'), 'rb').read() for n in ('screens_battery', 'screens_charge', 'screens_lowbattery')}
    expect(all(lock_imgs[n] == battery_art.png(battery_art.LOCK, s) for n, s in
               (('screens_battery', 'normal'), ('screens_charge', 'charge'), ('screens_lowbattery', 'low'))),
           'the lock screen battery images are battery_art.png(LOCK)')

    # 41. Now Playing: the np_* images are the committed PNGs (tools/mod_icons.py draws them); the page's own checks are
    #     in test/pod/nowplaying.py.
    np_names = mod_icons.np_names()
    expect(all(open(os.path.join(img_dir, n + '.png'), 'rb').read() == open(os.path.join(mod_icons.PNG, n + '.png'), 'rb').read() for n in np_names),
           f'the {len(np_names)} np_* glyphs are the committed PNGs')

    # 42. The queue drawer (ui/dialog/playqueue_dialog.bin, V2.1kE): compact rows built from the template (44 px; the code
    #     reads row_height for its scroll offset), the playing row (srlabel_item_gold20_style, set by the row bind @0x47a19c)
    #     white 20 px against muted 18 px, a quieter left border, a header hairline, a dark bottom button; widgets and
    #     the drawer's position and animation unchanged.
    import awtk_style
    stock_ui = awtk_ui.parse(open(os.path.join(paths.find_stock(paths.ZIP), 'rootfs/release/assets/default/raw/ui/dialog/playqueue_dialog.bin'), 'rb').read())
    pq = awtk_ui.parse(open(os.path.join(ui_dir, 'dialog/playqueue_dialog.bin'), 'rb').read())
    expect([(w.type, w.name) for w in pq.walk()] == [(w.type, w.name) for w in stock_ui.walk()], 'the drawer has the stock widgets')
    dlg = pq.find('playqueue_dialog'); sdlg = stock_ui.find('playqueue_dialog')
    expect((dlg.x, dlg.y, dlg.w, dlg.h) == (sdlg.x, sdlg.y, sdlg.w, sdlg.h) and dlg.get('animation') == sdlg.get('animation'),
           'its position, size and slide-in animation are stock')
    rh = int(pq.find('queue_table_client').get('row_height'))
    trow, rbtn, rlab = (pq.find(n) for n in ('queue_table_row', 'btn_table_row', 'scrlabel_name'))
    expect(rh == 44 and trow.h == rh and 40 <= rbtn.h <= rh - 4 and rlab.h == rbtn.h and rlab.y == 0 and rbtn.w == trow.w == 230,
           f'rows are {rh} px: the table row, a {rbtn.h} px button and its label (touch target >= 40)')
    sb = pq.find('scroll_bar_m'); tc = pq.find('queue_table_client')
    expect(tc.w + sb.w == 240 + 0 and sb.x == tc.w, 'the row column and the scroll bar still fill the 240 px drawer')
    expect(all(int(rlab.get(f'style:{st}:font_size')) == 18 for st in ('normal', 'disable', 'focused')), 'row text 18 px')
    expect(dlg.get('style:normal:border_color') == '#3A3A3A', 'a quiet left border')
    head = pq.find('list_item')
    expect(head.h == 64 and head.get('style:normal:border') == 'bottom' and head.get('style:normal:border_width') == '1', 'a hairline under the 64 px mode header')
    btm = pq.find('button')
    expect((btm.y, btm.h) == (396, 44) and btm.get('style:normal:bg_color') == '#1E1E1E' and btm.get('style:pressed:bg_color') == '#333333',
           'the bottom button keeps its 44 px target in the dark button colours')
    # touches by demo's own hit test: a row button in the template column, the bottom button, the scroll bar, the header
    m = Machine()
    tree = asset_tree(os.path.join(ui_dir, 'dialog/playqueue_dialog.bin'))
    tree.x, tree.y, tree.w, tree.h = 80, 30, 240, 450      # where the slide-in animation ends
    for nm, h in (('table_view', 322), ('queue_table_client', 322), ('scroll_bar_m', 322)): node(tree, nm).h = h   # the layouts' h=-128 / 100%
    node(tree, 'list_item').w = 240
    node(tree, 'queue_table_row').flags |= F_VISIBLE      # the template row is hidden: runtime clones are not
    for x, y, want in ((100, 64 + 20, 'btn_table_row'), (120, 396 + 22, 'button'), (235, 200, 'scroll_bar_m'), (50, 30, 'list_item')):
        got = stock_target(m, tree, 80 + x, 30 + y)
        expect(want in got, f'a touch at ({x}, {y}) in the drawer lands on {want} ({got})')
    for theme in ('default', 'theme1'):
        th = awtk_style.parse(open(os.path.join(WORK, 'rootfs', 'release/assets', theme, 'raw/styles/playqueue_dialog.bin'), 'rb').read())
        white = [i for i in th.items if (i.widget, i.style) == ('hscroll_label', 'srlabel_item_white_style')]
        gold = [i for i in th.items if (i.widget, i.style) == ('hscroll_label', 'srlabel_item_gold20_style')]
        expect(white and gold and all(i.get('font_size') == 18 for i in white) and all(i.get('font_size') == 20 for i in gold)
               and all(i.color('text_color') == '#FFFFFFFF' for i in gold) and all(i.color('text_color') != '#FFFFFFFF' for i in white),
               f'{theme}: other rows muted 18 px, the playing row white 20 px')
