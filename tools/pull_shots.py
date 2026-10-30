#!/usr/bin/env python3
"""Import card screenshots with content identities and optional dev-build attribution.

uv run python -I tools/pull_shots.py [CARD_DIR] [--build latest|DIR]
Without CARD_DIR, scans /Volumes/*/screenshots. Source files are never modified.
"""
import argparse, glob, os, sys
from pathlib import Path
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths, workflow


def import_shot(bmp, out, build=None):
    bmp, out = Path(bmp), Path(out)
    sha = workflow.sha(bmp); dst = out / f'{bmp.stem}-{sha[:16]}.png'
    if dst.exists(): return False
    out.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix('.part')
    try:
        with Image.open(bmp) as im: im.convert('RGB').save(tmp, format='PNG', optimize=True)
        os.replace(tmp, dst)
    finally:
        if tmp.exists(): tmp.unlink()
    workflow.write(dst.with_suffix('.json'), {'source': str(bmp.resolve()), 'source_sha256': sha,
                                            'tag': (build or {}).get('tag'), 'package_sha256': (build or {}).get('package_sha256')})
    print(dst)
    return True

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('card', nargs='?'); ap.add_argument('--build')
    a = ap.parse_args()
    dirs = [os.path.join(a.card, 'screenshots')] if a.card else glob.glob('/Volumes/*/screenshots')
    record = None; out = Path(paths.OUT) / 'shots'
    if a.build:
        directory = workflow.build_dir(a.build)
        record = workflow.validate_tree(directory / 'tree', current=False); out = directory / 'device'
    n = 0
    for d in dirs:
        for bmp in sorted(glob.glob(os.path.join(d, 'shot-[0-9][0-9][0-9][0-9].bmp'))):
            n += import_shot(bmp, out, record)
    if not dirs: sys.exit('no /Volumes/*/screenshots: is the card mounted?')
    print(f'{n} new screenshot(s) in {out}')

if __name__ == '__main__': main()
