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
    names = [f'pod_row{i}' for i in P.parse_menu(data)] + [f'pod_row{len(P.ITEMS)}', f'pod_row{len(P.ITEMS) + 1}']
    return PI.pod_page(s, 'm1pod_menu', 9, home=home, order=names).convert('RGB')

def extras_page(s, data):
    """Extras: the items the saved list does not show, in the fixed grouped order (pod_pages.EXTRAS_ORDER)."""
    shown = set(P.parse_menu(data))
    names = [f'pod_row{i}' for i in P.EXTRAS_ORDER if i not in shown]
    return PI.pod_page(s, 'm1pod_extras', 9, order=names).convert('RGB')

def mainmenu_page(s, data):
    """The Main Menu page: the shown items in order (an arrow on each but the first), then the hidden ones, switches as saved."""
    ids = P.parse_menu(data)
    order = ids + [i for i in range(len(P.ITEMS)) if i not in ids]
    return PI.pod_page(s, 'm1pod_mainmenu', 9, order=[f'pod_row{i}' for i in order],
                       switches={f'pod_switch{i}': i in ids for i in range(len(P.ITEMS))},
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
    sett = PI.pod_page(s, 'm1pod_settings', 6).convert('RGB')
    homeset = PI.pod_page(s, 'm1pod_homeset', 2, switches={'pod_switch0': True}).convert('RGB')
    cfset = PI.pod_page(s, 'm1pod_cfset', 2, switches={'pod_switch0': False}, values={'pod_value1': 'Artist'}).convert('RGB')
    shuf = PI.pod_page(s, 'm1pod_shuffle', 3).convert('RGB')
    ctl = controls(s, work).convert('RGB')
    bars, bars_same = PI.bars_compare(s); bars = bars.convert('RGB')
    custom = b'2301458\n'   # Albums, Artists, Now Playing, Cover Flow, Songs, Playlists, Folders: Shuffle and Genres are hidden
    mm_def, mm_cust = mainmenu_page(s, None), mainmenu_page(s, custom)
    menu_cust = menu_page(s, custom)
    extras = extras_page(s, None)
    extras_cust = extras_page(s, custom)
    art0, art1 = artists_page(s).convert('RGB'), artists_page(s, True).convert('RGB')
    pad, lab = 12, 20
    cols = [('Home page 1', home), ('Home page 3: the M1+ Pod icon', home3), ('M1+ Pod menu as Home (no top bar)', menu),
            ('Settings page', sett), ('Settings > Cover Flow (Sort: Artist)', cfset), ('Settings > Home Screen', homeset),('Shuffle page', shuf),
            ('Settings > Main Menu (default: Genres, Folders hidden)', mm_def), ('Main Menu after customising (Shuffle, Genres hidden)', mm_cust),
            ('The menu with that list', menu_cust), ('Extras (default: Library, then Tools)', extras),
            ('Extras with Shuffle, Genres hidden', extras_cust), ('Artists: Artist mode (toggle shows Album Artist)', art0), ('Artists: Album Artist mode (toggle shows Artist)', art1),
            ('Album page', panel(album, 0, 4)), ('Album page, long title', panel(album, 1, 4)),
            ('Artist Cover Flow', panel(cf, 2, 3)),
            ('Albums: grid view (toggle shows the list)', PI.albums_grid(s).convert('RGB')),
            ('Albums: list mode (toggle shows the grid; row 2 pressed)', PI.albums_list(s).convert('RGB')),
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
