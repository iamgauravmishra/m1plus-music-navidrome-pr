#!/usr/bin/env python3
"""The release sheet (out/preview/release-preview.png; docs/release-preview.png at a release): PIL mock-up of the release's screens (docs/ui.md), drawn by the look
previews from one finished tree. Approximate, not AWTK; sample data.

  Home pages 1 and 3 (Tabler icons, the M1+ Pod icon) + status bar     preview_icons.home
  M1+ Pod menu as Home (no top bar), Settings page, Shuffle page       preview_icons.pod_page (the tree's own ui files)
  album page (header, Play, Shuffle)             preview_album
  artist Cover Flow, and the landscape Cover Flow (480 x 320, as the user sees it)   preview_cover
  Albums: the grid and the list mode of ui/m1pod_albums.bin, with the mode toggle    preview_icons.albums_grid / albums_list
  lock screen over The Starry Night, unified battery (playing, idle + charging)   preview_lockscreen
  pull-down (the tree's dropdown_dialog.bin, real captions) and the toggle / slider art   controls()
  status bar / lock screen battery at 8x         preview_battery

Usage: venv/bin/python -I tools/preview.py WORKDIR [OUT.png]     (default out/preview/release-preview.png, gitignored;
the one tracked sheet is refreshed with `... WORKDIR docs/release-preview.png`, docs/workflow.md)
"""
import os, subprocess, sys, tempfile
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build, preview_icons as PI
import pod_pages
P = pod_pages

from awtk_ui import RAW

def run(script, *args):
    subprocess.run([sys.executable, '-I', os.path.join(HERE, script), *args], check=True, stdout=subprocess.DEVNULL)

def controls(s, work):
    """The pull-down laid out from the tree's ui/dialog/dropdown_dialog.bin (tile images in a sample state,
    captions word-wrapped with mod_pulldown's model), then the toggle and slider images at 1:1."""
    import awtk_ui, mod_pulldown as MP
    from awtk_text import Ttf
    raw = os.path.join(work, RAW)
    root = awtk_ui.parse(open(os.path.join(raw, 'ui/dialog/dropdown_dialog.bin'), 'rb').read())
    ttf = Ttf(os.path.join(work, MP.FONT)); en = MP.strings(os.path.join(raw, 'strings/en_US.bin'), MP.TILE_KEYS)
    im = Image.new('RGBA', (320, 640), (0x14, 0x14, 0x14, 255)); d = ImageDraw.Draw(im)
    PI.asset_bar(s, root.find('view_sysbar'), im)
    tiles = {'img_wifiswitch': ('drop_wifiopen', 'label_wifi', 'wifiset_wifi'), 'img_btswitch': ('drop_bt', 'label_bt', 'wifiset_bt'),
             'img_keylockswitch': ('drop_keylock', 'label_lock', 'system_keylock'), 'img_gainswitch': ('drop_highgain', 'label_gain', 'gain_high'),
             'img_usbmode': ('drop_usbaudio', 'label_usbmode', 'usbmode_audio'), 'img_outputswitch': ('drop_po', 'label_outputway', 'sset_outputway'),
             'img_playset': ('drop_playset', 'label_playset', 'playset'), 'img_sysset': ('drop_sysset', 'label_sysset', 'sysset')}
    sw = root.find('view_switchs')
    for name, (img, label, key) in tiles.items():
        w, lb = root.find(name), root.find(label)
        im.alpha_composite(s.img(img), (w.x, sw.y + w.y))
        px = int(lb.get('style:normal:font_size'))
        for i, line in enumerate(MP.wrap(ttf, en[key], px, lb.w)):
            s.text(im, lb.x + lb.w / 2, sw.y + lb.y + lb.h / 2 + (i - (len(MP.wrap(ttf, en[key], px, lb.w)) - 1) / 2) * px, line, px, anchor='m')
    bl = root.find('view_backlight'); sl = root.find('slider_backlight'); y = bl.y + 22
    im.alpha_composite(s.img('drop_lighticon0'), (bl.x + 20, y - 10)); im.alpha_composite(s.img('drop_lighticon1'), (bl.x + 260, y - 10))
    im.alpha_composite(s.img('drop_bg'), (bl.x + sl.x, y - 3)); im.alpha_composite(s.img('drop_fg').crop((0, 0, 120, 6)), (bl.x + sl.x, y - 3))
    im.alpha_composite(s.img('drop_dot'), (bl.x + sl.x + 120 - 8, y - 16))
    y = 340 + 18
    # toggles: on / off / the two-state words
    x = 14
    for n in ('sset_on', 'sset_off', 'pset_dual', 'pset_high'):
        im.alpha_composite(s.img(n), (x, y)); x += 74
    y += 40
    # Now Playing's progress line for comparison, the volume bar, the waveform volume, brightness and balance
    d.rectangle((12, y + 6, 12 + 295, y + 9), fill=(0x1C, 0x1C, 0x1C)); d.rectangle((12, y + 6, 12 + 170, y + 9), fill=(0xEE, 0xEE, 0xEC))
    y += 22
    im.alpha_composite(s.img('volume_bg'), (40, y)); im.alpha_composite(s.img('volume_fg').crop((0, 0, 150, 8)), (40, y)); y += 20
    wb, wf = s.img('vol_progressbak'), s.img('vol_progress')
    im.alpha_composite(wb.crop((0, 0, 281, 60)), (20, y)); im.alpha_composite(wf.crop((0, 0, 170, 60)), (20, y)); y += 66
    im.alpha_composite(s.img('other_progressback'), (40, y)); im.alpha_composite(s.img('other_progress').crop((0, 0, 150, 36)), (40, y))
    im.alpha_composite(s.img('light_dot'), (40 + 150 - 29, y - 11)); im.alpha_composite(s.img('balance_dot'), (250, y - 10))
    return im.crop((0, 0, 320, y + 62))

def artists_page(s, album_artist=False):
    """The Artists page from the tree's asset: the navbar with the title and toggle glyph the payload sets for
    artist_type (the glyph is the other mode's), sample rows."""
    im = PI.pod_page(s, 'm1pod_artists', 8, title='Album Artists' if album_artist else 'Artists',
                     icon='pod_nav_artist' if album_artist else 'pod_nav_albumartist').crop((0, 0, 320, 450))
    d = ImageDraw.Draw(im)
    names = ('Miles Davis', 'Nina Simone', 'Unknown Artist') if not album_artist else ('Various Artists', 'Miles Davis')
    for i, n in enumerate(names):
        y = 50 + i * 52
        d.rectangle((0, y + 51, 319, y + 51), fill=(0x22, 0x22, 0x22))
        s.text(im, 24, y + 26, n, 21); im.alpha_composite(s.img('right_arrow'), (300 - 40 + 8, y + 16))
    return im

def menu_page(s, data, home=False):
    """The menu as patch/menu.c arranges it for the saved list `data` (None: no file), 400 px under the navbar or the Home instance."""
    ids, extras = P.parse_menu_full(data)
    names = [f'pod_row{i}' for i in ids] + ([f'pod_row{len(P.ITEMS)}'] if extras else []) + [f'pod_row{len(P.ITEMS) + 1}']   # Extras only when the list ends in x
    return PI.pod_page(s, 'm1pod_menu', 9, home=home, order=names).convert('RGB')


def shelf_image(s, albums):
    """The Recently Played shelf of ui/m1pod_menu.bin (patch/recent.c) as it shows: the section header (the label pod_sh_head, 20 px white, its text 2 px in from the label),
    then up to SH_TILES cells of the Albums grid (patch/grid.c; geometry from offsets.inc GRID_*) row by row, 2 columns: the cover (rgb, None: the placeholder disc)
    GRID_COVER px square with GRID_R px rounded corners (drawn 4x and reduced), the album (18 px white) and the artist (15 px #AAAAAA) under it, cut with an ellipsis to the
    cover's width. ceil(albums / 2) rows of covers. tools/pod_ui.py's numbers."""
    import pod_ui as U
    k = 4
    rows = (len(albums[:U.SH_TILES]) + U.GRID_COLS - 1) // U.GRID_COLS
    im = Image.new('RGBA', (U.SH_W, U.SH_H(rows)), (0, 0, 0, 255))
    s.text(im, U.SH_HEAD_X + 2, U.SH_HEAD_TOP + U.SH_HEAD_H / 2, s.clip('Recently Played', U.SH_HEAD_PX, U.SH_HEAD_W - 4), U.SH_HEAD_PX)
    grey = tuple(int(U.SH_SUB_RGB[i:i + 2], 16) for i in (1, 3, 5))
    for i, (album, artist, rgb) in enumerate(albums[:U.SH_TILES]):
        x = U.GRID_MARGIN + i % U.GRID_COLS * (U.GRID_COVER + U.GRID_GAP)
        y = U.SH_TOP + i // U.GRID_COLS * U.GRID_PITCH
        art = PI.sample_cover(rgb, U.GRID_COVER)
        mask = Image.new('L', (U.GRID_COVER * k, U.GRID_COVER * k), 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, U.GRID_COVER * k - 1, U.GRID_COVER * k - 1), radius=U.GRID_R * k, fill=255)
        art.putalpha(mask.resize((U.GRID_COVER, U.GRID_COVER), Image.LANCZOS))
        im.alpha_composite(art, (x, y))
        ty = y + U.GRID_COVER + U.GRID_TITLE_GAP
        s.text(im, x, ty + U.GRID_TITLE_H / 2, s.clip(album, U.SH_TITLE_PX, U.GRID_COVER), U.SH_TITLE_PX)
        s.text(im, x, ty + U.GRID_TITLE_H + U.GRID_SUB_H / 2, s.clip(artist, U.SH_SUB_PX, U.GRID_COVER), U.SH_SUB_PX, grey)
    return im

SHELF_ALBUMS = [('Kind of Blue', 'Miles Davis', (70, 110, 190)), ('Music Has the Right to Children', 'Boards of Canada', None), ('Homogenic', 'Björk', (190, 90, 120)),
                ('Dummy', 'Portishead', (150, 120, 70)), ('Kid A', 'Radiohead', (60, 140, 150)), ('Mezzanine', 'Massive Attack', (110, 90, 130))]

def minibar_page(s, title, artist, rgb, playing=True, scroll=0, blur=True, shelf=None):
    """The menu as the Home instance with the mini player bar (patch/minibar.c) for a playing track: the list runs to the window bottom,
    scrolled by `scroll` px (48 is the end for the default menu: 8 rows and MB_PAD of padding in 430 px), under the translucent glass pill
    (the tree's own mb_glass.png composited as the device blends it), the cover (rgb: its colour, None: the placeholder disc) with rounded
    corners, the title and artist cut to their boxes, the white bar glyphs. tools/pod_ui.py's numbers."""
    import pod_ui as U
    k = 4   # the cover's corners drawn 4x and reduced
    base = menu_page(s, None, home=True).convert('RGBA')
    im = Image.new('RGBA', base.size, (0, 0, 0, 255))
    if shelf is None:
        im.paste(base.crop((0, 10 + scroll, 320, 440)), (0, 10))
    else:   # the Recently Played shelf (shelf: (albums,)) follows the last row (Settings) in the list's content and scrolls with it; scroll=None: to the end
        bottom = shelf_image(s, *shelf)
        content = Image.new('RGBA', (320, 8 * U.ROW_H + bottom.height + U.MB_PAD + 430), (0, 0, 0, 255))
        content.paste(base.crop((0, 10, 320, 10 + 8 * U.ROW_H)), (0, 0)); content.paste(bottom, (0, 8 * U.ROW_H))
        if scroll is None: scroll = 8 * U.ROW_H + bottom.height + U.MB_PAD - 430
        im.paste(content.crop((0, scroll, 320, scroll + 430)), (0, 10))
    if blur:   # the experimental backdrop blur (patch/minibar.c mb_blur) as its bit-exact model computes it, on the RGB565 pixels under the pill
        import pod_blur
        px = im.convert('RGB').load()
        def get(x, y):
            r, g, b = px[U.MB_X + x, U.MB_Y + y]; return (r >> 3) << 11 | (g >> 2) << 5 | (b >> 3)
        for (x, y), v in pod_blur.blur(get).items():
            r, g, b = v >> 11, v >> 5 & 63, v & 31
            im.putpixel((U.MB_X + x, U.MB_Y + y), (r << 3 | r >> 2, g << 2 | g >> 4, b << 3 | b >> 2, 255))
    im.alpha_composite(s.img('mb_glass'), (U.MB_X, U.MB_Y))
    art = PI.sample_cover(rgb, U.MB_ART)
    mask = Image.new('L', (U.MB_ART * k, U.MB_ART * k), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, U.MB_ART * k - 1, U.MB_ART * k - 1), radius=U.MB_ART_R * k, fill=255)
    art.putalpha(mask.resize((U.MB_ART, U.MB_ART), Image.LANCZOS))
    im.alpha_composite(art, (U.MB_X + U.MB_ART_X, U.MB_Y + U.MB_ART_Y))
    x = U.MB_X + U.MB_TEXT_X
    s.text(im, x, U.MB_Y + U.MB_TITLE_Y + U.MB_TITLE_H / 2, s.clip(title, U.MB_TITLE_PX, U.MB_TEXT_W), U.MB_TITLE_PX)
    s.text(im, x, U.MB_Y + U.MB_ARTIST_Y + U.MB_ARTIST_H / 2, s.clip(artist, U.MB_ARTIST_PX, U.MB_TEXT_W), U.MB_ARTIST_PX, tuple(int(U.MB_ARTIST_RGB[i:i + 2], 16) for i in (1, 3, 5)))
    for name, bx in (('mb_pause' if playing else 'mb_play', U.MB_PLAY_X), ('mb_next', U.MB_NEXT_X)):
        g = s.img(name)
        im.alpha_composite(g, (U.MB_X + bx + (U.MB_BTN_W - g.width) // 2, U.MB_Y + (U.MB_H - g.height) // 2))
    return im.convert('RGB')

def extras_page(s, data):
    """Extras: the items the saved list does not show, in the fixed grouped order (pod_pages.EXTRAS_ORDER)."""
    shown = set(P.parse_menu(data))
    names = [f'pod_row{i}' for i in P.EXTRAS_ORDER if i not in shown]
    return PI.pod_page(s, 'm1pod_extras', 9, order=names).convert('RGB')

def mainmenu_page(s, data, first=0):
    """The Main Menu page: the shown items in order (an arrow on each but the first), then the hidden ones, then the Extras row (a switch only,
    no arrow), switches as saved; first: the row the list is scrolled to (10: the last nine rows, the Extras row at the bottom)."""
    ids, extras = P.parse_menu_full(data)
    order = ids + [i for i in range(len(P.ITEMS)) if i not in ids] + [len(P.ITEMS)]
    return PI.pod_page(s, 'm1pod_mainmenu', 9, first=first, order=[f'pod_row{i}' for i in order],
                       switches={**{f'pod_switch{i}': i in ids for i in range(len(P.ITEMS))}, f'pod_switch{len(P.ITEMS)}': extras},
                       arrows={f'pod_up{i}' for i in ids[1:]}).convert('RGB')

def shot_bars(work):
    """The status bar while a Screenshot is pending (the camera shown, Wi-Fi and a connected Bluetooth lit), with the 12 h and the 24 h
    clock, then the same bar as it is for the capture (the camera hidden), drawn from the tree's own system_bar.bin; 3x."""
    import preview_theme as PT
    t = PT.Tree(work)
    rows = []
    for clock, shot in (('12:59 PM', True), ('12:59', True), ('12:59 PM', False)):
        im = Image.new('RGBA', (320, PT.BAR), (0, 0, 0, 255)); PT.status_bar(im, t, shot=shot, clock=clock); rows.append(im)
    sheet = Image.new('RGB', (320, 3 * PT.BAR + 12), (0x2A, 0x2A, 0x2A))
    for i, im in enumerate(rows): sheet.paste(im.convert('RGB'), (0, i * (PT.BAR + 6)))
    return sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST)

def main():
    work = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'release-preview.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    raw = os.path.join(work, RAW)
    s = PI.Side(work, True); s.mark = lambda *a: None   # no C/K markers here
    with tempfile.TemporaryDirectory() as t:
        p = lambda n: os.path.join(t, n)
        run('preview_lockscreen.py', raw, p('lock.png'), f'release={raw}/ui/screensaver_page.bin',
            f'release={raw}/ui/screensaver_page.bin,idle,charging,pct=40', '--wallpaper', 'stock')
        run('preview_album.py', work, p('album.png'))
        run('preview_cover.py', work, p('cf.png'), p('land.png'))
        run('preview_battery.py', work, p('bat.png'))
        lock, album, cf, bat, land = (Image.open(p(n + '.png')).convert('RGB') for n in ('lock', 'album', 'cf', 'bat', 'land'))
    panel = lambda im, i, n: im.crop((i * im.width // n, 0, (i + 1) * im.width // n, im.height))
    home, home3 = PI.home(s, 0).convert('RGB'), PI.home(s, 2).convert('RGB')
    menu = menu_page(s, None, home=True)
    bar1 = minibar_page(s, 'Blue in Green (Remastered, Mono Version)', 'Miles Davis', (70, 110, 190), scroll=0)
    bar3 = minibar_page(s, 'Blue in Green (Remastered, Mono Version)', 'Miles Davis', (70, 110, 190), scroll=0, blur=False)
    bar2 = minibar_page(s, 'Gloomy Sunday', 'Billie Holiday', None, playing=False, scroll=48)
    bar_args = ('Blue in Green (Remastered, Mono Version)', 'Miles Davis', (70, 110, 190))
    sh6top = minibar_page(s, *bar_args, shelf=(SHELF_ALBUMS,), scroll=0)
    sh6 = minibar_page(s, *bar_args, shelf=(SHELF_ALBUMS,), scroll=None)
    sh5 = minibar_page(s, *bar_args, shelf=(SHELF_ALBUMS[:5],), scroll=None)
    sh3 = minibar_page(s, *bar_args, shelf=(SHELF_ALBUMS[:3],), scroll=None)
    sh1 = minibar_page(s, *bar_args, shelf=(SHELF_ALBUMS[:1],), scroll=None)
    for name, panel_im in (('shelf-home-top', sh6top), ('shelf-6-albums-end', sh6), ('shelf-5-albums-end', sh5), ('shelf-3-albums-end', sh3), ('shelf-1-album-end', sh1)):   # the panels alone, for tools/peek.py crops
        panel_im.save(os.path.join(os.path.dirname(os.path.abspath(out)), name + '.png'))
    sett = PI.pod_page(s, 'm1pod_settings', 6).convert('RGB')
    homeset = PI.pod_page(s, 'm1pod_homeset', 3, switches={'pod_switch0': True, 'pod_switch1': True}).convert('RGB')
    cfset = PI.pod_page(s, 'm1pod_cfset', 2, switches={'pod_switch0': False}, values={'pod_value1': 'Artist'}).convert('RGB')
    shuf = PI.pod_page(s, 'm1pod_shuffle', 3).convert('RGB')
    ctl = controls(s, work).convert('RGB')
    bars, bars_same = PI.bars_compare(s); bars = bars.convert('RGB')
    custom = b'2301458\n'   # Albums, Artists, Now Playing, Cover Flow, Songs, Playlists, Folders: Shuffle and Genres are hidden, and so is the Extras row (no x)
    mm_def, mm_cust = mainmenu_page(s, None), mainmenu_page(s, custom)
    mm_end, mm_end_off = mainmenu_page(s, None, first=10), mainmenu_page(s, custom, first=10)   # scrolled to the end: the Extras row, on and off
    menu_cust = menu_page(s, custom)
    extras = extras_page(s, None)
    extras_cust = extras_page(s, custom)
    art0, art1 = artists_page(s).convert('RGB'), artists_page(s, True).convert('RGB')
    pad, lab = 12, 20
    cols = [('Home page 1', home), ('Home page 3: the M1+ Pod icon', home3), ('M1+ Pod menu as Home (no top bar)', menu),
            ('Mini player bar: playing, long title', bar1), ('Mini player bar: paused, no cover', bar2), ('Mini player bar: backdrop blur off', bar3),
            ('Home menu with the Recently Played shelf below the rows (list at the top)', sh6top), ('Scrolled to the end: the shelf above the bar, 6 albums (one with no cache file)', sh6), ('Scrolled to the end: 5 albums', sh5), ('Scrolled to the end: 3 albums', sh3),
            ('Scrolled to the end: 1 album', sh1),
            ('Settings page', sett), ('Settings > Cover Flow (Sort: Artist)', cfset), ('Settings > Home Screen', homeset),('Shuffle page', shuf),
            ('Settings > Main Menu (default: Now Playing, Genres, Folders hidden)', mm_def), ('Main Menu after customising (Shuffle, Genres, Extras hidden)', mm_cust),
            ('Main Menu scrolled to the end: the Extras row on (default), a switch row without an arrow', mm_end), ('Main Menu scrolled to the end: Extras off', mm_end_off),
            ('The menu with that list', menu_cust), ('Extras (default: Now Playing, Library, then Tools)', extras),
            ('Extras with Shuffle, Genres hidden', extras_cust), ('Artists: Artist mode (toggle shows Album Artist)', art0), ('Artists: Album Artist mode (toggle shows Artist)', art1),
            ('Album page', panel(album, 0, 4)), ('Album page, long title', panel(album, 1, 4)),
            ('Artist Cover Flow', panel(cf, 2, 3)),
            ('Albums: grid view (toggle shows the list)', PI.albums_grid(s).convert('RGB')),
            ('Albums: list mode (toggle shows the grid; row 2 pressed)', PI.albums_list(s).convert('RGB')),
            ('Playlists: a 2x2 mosaic of each playlist\'s albums (4, 2, 3, 1, 0 and 7 albums)', PI.playlists_grid(s).convert('RGB')),
            ('Playlists: the "..." menu (New, Import, Export, Delete)', PI.playlists_grid(s, menu=True).convert('RGB')),
            ('Playlists: list mode (toggle shows the grid; row 2 pressed)', PI.playlists_grid(s, list_mode=True).convert('RGB')),
            ('Pull-down, toggles and sliders', ctl),
            ('Status bar: real (top), pull-down default, theme1; below, their differences x16 (' + ('identical' if bars_same else 'DIFFER') + ')', bars),
            ('Lock screen over The Starry Night (playing, idle + charging)', lock),
            ('Cover Flow landscape (Settings > Cover Flow > Landscape; player held turned counter-clockwise)', land)]
    # rows of panels, packed left to right
    rows = [cols[i:i + 3] for i in range(0, len(cols), 3)]
    wid = max(sum(i.width for _, i in r) + pad * (len(r) + 1) for r in rows)
    wid = max(wid, bat.width + 2 * pad)
    hei = sum(max(i.height for _, i in r) + lab + pad for r in rows) + bat.height + 2 * pad + 40
    sh = Image.new('RGB', (wid, hei), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sh)
    d.text((pad, 6), f'{build.TAG} release (1:1 device pixels)',
           fill=(255, 255, 255), font=PI.ANN)
    y = 30
    for r in rows:
        x = pad
        for title, im in r:
            d.text((x, y), title, fill=(0xAA,) * 3, font=PI.ANN); sh.paste(im, (x, y + lab)); x += im.width + pad
        y += max(i.height for _, i in r) + lab + pad
    d.text((pad, y), 'Battery, status bar and lock screen, 8x', fill=(0xAA,) * 3, font=PI.ANN)
    sh.paste(bat, (pad, y + lab))
    sb = shot_bars(work)
    sh2 = Image.new('RGB', (wid, sh.height + sb.height + lab + pad), (0x2A, 0x2A, 0x2A))
    sh2.paste(sh.crop((0, 0, wid, y + lab + bat.height + pad)), (0, 0))
    y2 = y + lab + bat.height + pad
    ImageDraw.Draw(sh2).text((pad, y2), 'Status bar while a Screenshot is pending: 12 h clock, 24 h clock, then as captured (camera hidden); 3x', fill=(0xAA,) * 3, font=PI.ANN)
    sh2.paste(sb, (pad, y2 + lab))
    PI.save_compact(sh2.crop((0, 0, wid, y2 + lab + sb.height + pad)), out); print('wrote', out, sh2.size)

if __name__ == '__main__':
    main()
