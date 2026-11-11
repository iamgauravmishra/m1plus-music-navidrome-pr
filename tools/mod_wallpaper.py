#!/usr/bin/env python3
"""The default lock screen wallpaper: a drawn bokeh field in place of the stock picture.

When no custom wallpaper is set, demo's get_screensaver_image (@0x4d7524) keeps the resource name
"screensaver_default" as the SCREENSAVERPATH, and screensaver_page_init gives img_screensaver that
image; a picture the user chose (Screensaver settings: "file://" + the path) replaces it and is
untouched by this step. The resource is

  release/assets/default/raw/images/xx/screensaver_default.png     320 x 480, 8-bit RGBA, 398,437 bytes

(the `xx` set is the only one that has it: `theme1` has no `screensaver_default`, so it falls back to
this file; screensaver_default1.png, 640 x 480, is not referenced by demo or any ui file and stays).
It is replaced byte for byte by assets/bokeh-320x480.png (tools/wallpaper_prepare.py: a drawn bokeh
field, 256-colour palette PNG compressed by primage, ~9 KB), the same name and size. The stock file is pinned by
SHA-256, so a different firmware refuses to build rather than overwrite something else.

Usage: mod_wallpaper.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import argparse, os, stat, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir, sha256 as sha

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE = 'rootfs/release/assets/default/raw/images/xx/screensaver_default.png'
STOCK_SHA = '92e7162b035fd5c6797d782db482e871ed696baa44e1a40160d0244e4970828c'
ASSET = os.path.join(ROOT, 'assets', 'bokeh-320x480.png')
ASSET_SHA = '8bf483509e85afd980c6476b3fb74e6ed7903b187a81138fa1b553c94845989d'
SIZE = (320, 480)




def check(ok, msg):
    if not ok: raise SystemExit(f'mod_wallpaper: {msg}')


def apply(work):
    path = os.path.join(work, IMAGE)
    old = open(path, 'rb').read()
    new = open(ASSET, 'rb').read()
    check(sha(old) == STOCK_SHA, f'{IMAGE} is not the stock picture ({sha(old)})')
    check(sha(new) == ASSET_SHA, f'{os.path.relpath(ASSET, ROOT)} is not the pinned asset ({sha(new)})')
    check(new[:8] == b'\x89PNG\r\n\x1a\n' and int.from_bytes(new[16:20], 'big') == SIZE[0]
          and int.from_bytes(new[20:24], 'big') == SIZE[1], 'the wallpaper is not a 320x480 PNG')
    mode = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, mode | 0o200); open(path, 'wb').write(new); os.chmod(path, mode)
    return [f'{IMAGE}: {len(old)} -> {len(new)} bytes']


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('out')
    a = ap.parse_args()
    clone_workdir(a.src, a.out)
    for line in apply(a.out): print('wallpaper:', line)


if __name__ == '__main__': main()
