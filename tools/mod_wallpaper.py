#!/usr/bin/env python3
"""The default lock screen wallpaper: The Starry Night in place of the stock picture (V2.1hB).

When no custom wallpaper is set, demo's get_screensaver_image (@0x4d7524) keeps the resource name
"screensaver_default" as the SCREENSAVERPATH, and screensaver_page_init gives img_screensaver that
image; a picture the user chose (Screensaver settings: "file://" + the path) replaces it and is
untouched by this step. The resource is

  release/assets/default/raw/images/xx/screensaver_default.png     320 x 480, 8-bit RGBA, 398,437 bytes

(the `xx` set is the only one that has it: `theme1` has no `screensaver_default`, so it falls back to
this file; screensaver_default1.png, 640 x 480, is not referenced by demo or any ui file and stays).
It is replaced byte for byte by assets/starry-night-320x480.png (tools/wallpaper_prepare.py: crop,
tone, 256-colour palette PNG, ~134 KB), the same name, size and mode. The stock file is pinned by
SHA-256, so a different firmware refuses to build rather than overwrite something else.

Usage: mod_wallpaper.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import argparse, hashlib, os, stat, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGE = 'rootfs/release/assets/default/raw/images/xx/screensaver_default.png'
STOCK_SHA = '92e7162b035fd5c6797d782db482e871ed696baa44e1a40160d0244e4970828c'
ASSET = os.path.join(ROOT, 'assets', 'starry-night-320x480.png')
ASSET_SHA = 'c824ad7a9f3b65c9dcccb4622f56cc88a366d1d764c8f8d061527916460f9f6a'
SIZE = (320, 480)


def sha(b): return hashlib.sha256(b).hexdigest()


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
