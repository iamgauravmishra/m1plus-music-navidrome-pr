#!/usr/bin/env python3
"""Copy the device screenshots off the TF card as PNG: /Volumes/<card>/screenshots/shot-NNNN.bmp -> out/shots/shot-NNNN.png
(patch/shot.c writes them; docs/workflow.md "Screenshots"). Files already converted are skipped; the card is left as it is.

Usage: venv/bin/python -I tools/pull_shots.py [CARD_DIR]     (default: every /Volumes/*/screenshots)
"""
import glob, os, sys
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

def main():
    dirs = [os.path.join(sys.argv[1], 'screenshots')] if len(sys.argv) > 1 else glob.glob('/Volumes/*/screenshots')
    out = os.path.join(paths.OUT, 'shots')
    os.makedirs(out, exist_ok=True)
    n = 0
    for d in dirs:
        for bmp in sorted(glob.glob(os.path.join(d, 'shot-[0-9][0-9][0-9][0-9].bmp'))):
            dst = os.path.join(out, os.path.basename(bmp)[:-4] + '.png')
            if os.path.exists(dst): continue
            Image.open(bmp).convert('RGB').save(dst, optimize=True); n += 1
            print(dst)
    if not dirs: sys.exit('no /Volumes/*/screenshots: is the card mounted?')
    print(f'{n} new screenshot(s) in {out}')

if __name__ == '__main__': main()
