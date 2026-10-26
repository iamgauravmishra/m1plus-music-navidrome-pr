#!/usr/bin/env python3
"""docs/release-preview.png: PIL mock-up of the release's screens (docs/ui.md), drawn by the look
previews from one finished tree. Approximate, not AWTK; sample data.

  Home pages 1 and 3 (Tabler icons, the M1 Pod icon) + status bar     preview_icons.home
  M1 Pod menu as Home (no top bar), Settings page, Shuffle page       preview_icons.pod_page (the tree's own ui files)
  album page (header, Play, Shuffle)             preview_album
  artist Cover Flow                              preview_cover2
  lock screen over The Starry Night, unified battery (playing, idle + charging)   preview_lockscreen
  status bar / lock screen battery at 8x         preview_battery

With a third argument it also writes the Home / menu / Settings trio (docs/home-menu-preview.png).

Usage: venv/bin/python -I tools/preview.py WORKDIR OUT.png [HOME_MENU.png]
"""
import os, subprocess, sys, tempfile
from PIL import Image, ImageDraw
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import preview_icons as PI

RAW = 'rootfs/release/assets/default/raw'

def run(script, *args):
    subprocess.run([sys.executable, '-I', os.path.join(HERE, script), *args], check=True, stdout=subprocess.DEVNULL)

def main():
    work, out = sys.argv[1:3]
    out_home = sys.argv[3] if len(sys.argv) > 3 else None
    raw = os.path.join(work, RAW)
    s = PI.Side(work, True); s.mark = lambda *a: None   # no C/K markers here
    with tempfile.TemporaryDirectory() as t:
        p = lambda n: os.path.join(t, n)
        run('preview_lockscreen.py', raw, p('lock.png'), f'release={raw}/ui/screensaver_page.bin',
            f'release={raw}/ui/screensaver_page.bin,idle,charging,pct=40', '--wallpaper', 'stock')
        run('preview_album.py', work, p('album.png'))
        run('preview_cover2.py', work, p('cf.png'))
        run('preview_battery.py', work, p('bat.png'))
        lock, album, cf, bat = (Image.open(p(n + '.png')).convert('RGB') for n in ('lock', 'album', 'cf', 'bat'))
    panel = lambda im, i, n: im.crop((i * im.width // n, 0, (i + 1) * im.width // n, im.height))
    home, home3 = PI.home(s, 0).convert('RGB'), PI.home(s, 2).convert('RGB')
    menu = PI.pod_page(s, 'm1pod_menu', 9, home=True).convert('RGB')
    sett = PI.pod_page(s, 'm1pod_settings', 4).convert('RGB')
    shuf = PI.pod_page(s, 'm1pod_shuffle', 3).convert('RGB')
    pad, lab = 12, 20
    if out_home:   # the launcher: the grid's M1 Pod icon, the menu it opens as Home (no top bar), its Settings page
        trio = [('Home page 3: the M1 Pod icon', home3), ('M1 Pod menu as Home (no top bar)', menu), ('Settings page', sett)]
        w = sum(i.width for _, i in trio) + pad * 4; h = max(i.height for _, i in trio) + lab + 2 * pad
        sh = Image.new('RGB', (w, h), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sh); x = pad
        for title, im in trio:
            d.text((x, pad), title, fill=(0xAA,) * 3, font=PI.ANN); sh.paste(im, (x, pad + lab)); x += im.width + pad
        sh.save(out_home); print('wrote', out_home, sh.size)
    cols = [('Home page 1', home), ('Home page 3: the M1 Pod icon', home3), ('M1 Pod menu as Home (no top bar)', menu),
            ('Settings page', sett), ('Shuffle page', shuf),
            ('Album page', panel(album, 0, 4)), ('Album page, long title', panel(album, 1, 4)),
            ('Artist Cover Flow', panel(cf, 2, 3)),
            ('Lock screen over The Starry Night (playing, idle + charging)', lock)]
    # rows of panels, packed left to right
    rows = [cols[0:3], cols[3:6], cols[6:8], cols[8:9]]
    wid = max(sum(i.width for _, i in r) + pad * (len(r) + 1) for r in rows)
    wid = max(wid, bat.width + 2 * pad)
    hei = sum(max(i.height for _, i in r) + lab + pad for r in rows) + bat.height + 2 * pad + 40
    sh = Image.new('RGB', (wid, hei), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sh)
    d.text((pad, 6), 'V2.1kE release (1:1 device pixels)',
           fill=(255, 255, 255), font=PI.ANN)
    y = 30
    for r in rows:
        x = pad
        for title, im in r:
            d.text((x, y), title, fill=(0xAA,) * 3, font=PI.ANN); sh.paste(im, (x, y + lab)); x += im.width + pad
        y += max(i.height for _, i in r) + lab + pad
    d.text((pad, y), 'Battery, status bar and lock screen, 8x', fill=(0xAA,) * 3, font=PI.ANN)
    sh.paste(bat, (pad, y + lab))
    sh.crop((0, 0, wid, y + lab + bat.height + pad)).save(out); print('wrote', out, sh.size)

if __name__ == '__main__':
    main()
