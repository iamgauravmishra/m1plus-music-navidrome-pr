"""Built assets: the M1 Pod pages are dark with light text and inside the window, the default wallpaper, the icon set and the battery art."""
import hashlib, json, os, re, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)


def run(ctx):
    expect, page = ctx.expect, ctx.page
    ui_dir = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui')

    # 25. Contrast in the built assets: every button we style inline has a dark background and
    #     light text in every widget state (theme-styled navbar buttons excepted).
    for asset_name in ('m1pod_menu.bin', 'm1pod_cover.bin', 'm1pod_artists.bin', 'm1pod_shuffle.bin', 'm1pod_settings.bin'):
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
           'inserted in the stock sort order, and the Tidal icon keeps its stock image')
    stock_tidal = open(os.path.join(mod_icons.find_stock_img(), 'tidal.png'), 'rb').read()
    expect(open(os.path.join(img_dir, 'tidal.png'), 'rb').read() == stock_tidal and
           open(os.path.join(img_dir, 'tidal_down.png'), 'rb').read() == open(os.path.join(mod_icons.find_stock_img(), 'tidal_down.png'), 'rb').read(),
           'tidal.png and tidal_down.png are the stock files (Tidal is Tidal again)')
    lock_imgs = {n: open(os.path.join(img_dir, n + '.png'), 'rb').read() for n in ('screens_battery', 'screens_charge', 'screens_lowbattery')}
    expect(all(lock_imgs[n] == battery_art.png(battery_art.LOCK, s) for n, s in
               (('screens_battery', 'normal'), ('screens_charge', 'charge'), ('screens_lowbattery', 'low'))),
           'the lock screen battery images are battery_art.png(LOCK)')

    # 41. Now Playing (round 2, V2.1kE layout): the np_* glyphs are the committed Tabler PNGs; the top row is Back / index
    #     / heart / More (44 px targets, as V2.1jA), the play mode is the transport row's first slot, nothing sits at the
    #     foot of the art page; img_hr (app-driven: demo only calls widget_set_visible on it) stays at 0x0, insensitive,
    #     so the Hi-Res tag never shows; the progress line has no thumb.
    np_names = mod_icons.np_names()
    expect(all(open(os.path.join(img_dir, n + '.png'), 'rb').read() == open(os.path.join(mod_icons.PNG, n + '.png'), 'rb').read() for n in np_names),
           f'the {len(np_names)} np_* glyphs are the committed PNGs')
    from PIL import Image
    solid = {'np_play': ('play', 44, mod_icons.NP_FG), 'np_pause': ('pause', 44, mod_icons.NP_FG), 'np_next': ('next', 36, mod_icons.NP_FG),
             'np_prev': ('prev', 36, mod_icons.NP_FG), 'np_play_down': ('play', 44, mod_icons.NP_DIM), 'np_pause_down': ('pause', 44, mod_icons.NP_DIM),
             'np_next_down': ('next', 36, mod_icons.NP_DIM), 'np_prev_down': ('prev', 36, mod_icons.NP_DIM)}
    expect(all(Image.open(os.path.join(img_dir, n + '.png')).convert('RGBA').tobytes() == mod_icons.pil_glyph(k, px, rgb).tobytes()
               for n, (k, px, rgb) in solid.items()),
           'prev / play / pause / next (and their pressed greys) are the solid PIL-drawn glyphs of V2.1jA, the rest of the np_* Tabler')
    tabler_np = [n for n in np_names if n not in solid and n != 'np_artmask']
    expect(all(len(set(Image.open(os.path.join(img_dir, n + '.png')).convert('RGBA').getchannel('A').tobytes())) > 2 for n in tabler_np),
           'heart, mode, more and queue stay the antialiased Tabler glyphs')
    pp = awtk_ui.parse(open(os.path.join(ui_dir, 'playing_page.bin'), 'rb').read())
    page1 = {c.name for c in pp.find('view').children}
    expect(not ({'btn_fav', 'btn_playmode', 'img_hr'} & page1), 'heart, mode and the Hi-Res tag are not on the art page')
    fav, more, mode, prev = (pp.find(n) for n in ('btn_fav', 'btn_more', 'btn_playmode', 'btn_prev'))
    expect((fav.y, fav.h, more.y, more.h) == (0, 44, 0, 44) and fav.x + fav.w == more.x and more.x + more.w == 320 and fav.w >= 44 and more.w >= 44,
           f'the heart sits left of More in the 44 px top row ({(fav.x, fav.w, more.x, more.w)})')
    expect(mode.x + mode.w <= prev.x and mode.w >= 44 and mode.h >= 44 and mode.x >= 0, 'the play mode is the transport row\'s first slot, left of prev')
    hr = pp.find('img_hr')
    expect((hr.w, hr.h) == (0, 0) and hr.get('sensitive') == 'false' and hr.get('visible') == 'false', 'img_hr is kept at 0x0, insensitive: the Hi-Res tag never shows')
    art = pp.find('img_playcover'); title = pp.find('scrlabel_title'); album = pp.find('scroll_np_album')
    expect(art.w == 216 and title.y >= art.y + art.w and album.y + album.h <= pp.find('slide_view').h, 'the art is back to 216 px with the title, artist and album under it')
    sl = pp.find('slider_play')
    expect((sl.y, sl.h, sl.get('bar_size'), sl.get('style:normal:bg_color'), sl.get('style:normal:icon')) == (342, 30, '4', '#1C1C1C', ''),
           'the progress line is 4 px in the stock 30 px target, track #1C1C1C, no thumb')

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
    expect((btm.y, btm.h) == (396, 44) and btm.get('style:normal:bg_color') == '#1E1E1E' and btm.get('style:pressed:bg_color') == '#3A3A3A',
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
