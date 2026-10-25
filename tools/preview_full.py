#!/usr/bin/env python3
"""Combined PIL mock-up of a `full` tree (V2.1gA, docs/full.md), drawn by the existing preview tools
from the finished tree, with the text rasterized from the tree's own default.ttf the stb_truetype
way (tools/preview_font.py's redirect to tools/stb_raster.py). Approximate, not AWTK; sample data.

  boot splash        images/xx/logo.jpg as shipped (look-boot)
  Home, Settings     preview_theme (look-theme)
  Songs              preview_lists (look-lists)
  Now Playing        preview_nowplaying (look-nowplaying, the album line without its prefix)
  M1 Pod menu        preview_all.menu: ui/m1pod_menu.bin with the Shuffle rows
  Artists            preview_artists.artists_page: ui/m1pod_artists.bin with sample rows
  an artist          preview_artists.shelf: the scoped Cover Flow page, the real depth renderer
  lock screen        preview_lockscreen (lock screen 2): playing, and nothing queued

Usage: venv/bin/python -I tools/preview_full.py WORKDIR OUT.png [--label TEXT]
"""
import argparse, os, sys, tempfile
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui
import preview_font   # noqa: F401  (redirects the painters' text to stb_raster, the tree's font)
import preview_theme, preview_lists, preview_nowplaying, preview_lockscreen, preview_all, preview_artists
from preview_artists import hostcf

RAW = 'rootfs/release/assets/default/raw'
W, H = 320, 480


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('work'); ap.add_argument('out'); ap.add_argument('--label', default='V2.1gA')
    a = ap.parse_args()
    raw = os.path.join(a.work, RAW)
    t = preview_theme.Tree(a.work)
    np_root = awtk_ui.parse(open(os.path.join(raw, 'ui', 'playing_page.bin'), 'rb').read())
    lock = awtk_ui.parse(open(os.path.join(raw, 'ui', 'screensaver_page.bin'), 'rb').read())
    lp = preview_lockscreen.Painter(raw, False)
    with tempfile.TemporaryDirectory() as tmp:
        lib = hostcf.build(tmp)
        kob, hits, brew = (hostcf.texture(c, mark=m) for c, m in
                           (((60, 160, 200), 1), ((230, 190, 70), 0), ((200, 120, 200), 0)))
        artist = preview_artists.shelf(a.work, lib, [None] * 3 + [kob, hits, brew, hostcf.placeholder()],
                                       'Kind of Blue', 'Miles Davis', hostcf.ONE // 10)
    shots = [('boot splash', preview_all.splash(a.work)), ('Home', preview_theme.home(t)),
             ('System Settings', preview_theme.settings(t)), ('Songs', preview_lists.panels(a.work, 'default')[1]),
             ('Now Playing', preview_nowplaying.Painter(raw).render(np_root, 0)),
             ('M1 Pod menu', preview_all.menu(a.work)), ('Artists', preview_artists.artists_page(a.work)),
             ('Cover Flow on an artist', artist),
             ('lock screen, playing', lp.render(lock, 86, False, False)),
             ('lock screen, nothing queued', lp.render(lock, 86, False, True))]
    pad, top, cols = 12, 20, 5
    rows = (len(shots) + cols - 1) // cols
    out = Image.new('RGB', (cols * (W + pad) + pad, rows * (H + top + pad) + pad + 16), (40, 40, 40))
    d = ImageDraw.Draw(out)
    for i, (cap, im) in enumerate(shots):
        x, y = pad + (i % cols) * (W + pad), pad + (i // cols) * (H + top + pad)
        assert im.size == (W, H), (cap, im.size)
        out.paste(im.convert('RGB'), (x, y + top)); d.text((x, y + 4), f'{a.label}: {cap}', fill=(230, 230, 230))
    d.text((pad, out.height - 18), 'approximate PIL mock-ups from the finished tree (not AWTK), text drawn from its '
           'default.ttf the stb_truetype way; the covers are the real renderer; sample data; lock screen wallpaper '
           'replaced by a gradient', fill=(160, 160, 160))
    out.quantize(colors=192).save(a.out, optimize=True); print('wrote', a.out)


if __name__ == '__main__': main()
