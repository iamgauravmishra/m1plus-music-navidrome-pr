#!/usr/bin/env python3
"""Image audit of the stock UI (docs/ui.md "Icon audit"): every images/xx file, who refers to it, and what
the release does with it.

  audit_images.py [STOCK_ROOTFS_RELEASE] [RELEASE_TREE_ROOTFS_RELEASE]

A reference is an image-file stem found as a property value in ui/**/*.bin (image, icon, bg_image, ...),
as a style property in styles/*.bin, or as a NUL-delimited string in bin/demo (images the app sets in
code, formats like "bar_wifi%d" are expanded by hand in EXPAND). Prints a table of the images that are
still byte-identical to stock in the release tree and are referenced somewhere.
"""
import hashlib, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui, awtk_style, paths

RAW = 'assets/default/raw'
STOCK = os.path.join(paths.find_stock(paths.ZIP), 'rootfs/release')
EXPAND = {'bar_wifi%d': [f'bar_wifi{i}' for i in range(5)], 'bar_vol%d': [f'bar_vol{i}' for i in range(5)]}

def sha(p): return hashlib.sha256(open(p, 'rb').read()).hexdigest()

def refs(root):
    xx = os.path.join(root, RAW, 'images/xx')
    stems = {f[:-4] for f in os.listdir(xx) if f.endswith('.png')}
    out = {}
    def add(stem, who):
        if stem in stems: out.setdefault(stem, set()).add(who)
    ui = os.path.join(root, RAW, 'ui')
    for d, _, fs in os.walk(ui):
        for f in fs:
            p = os.path.join(d, f); rel = os.path.relpath(p, ui)
            for w in awtk_ui.parse(open(p, 'rb').read()).walk():
                for k, v in w.props:
                    if isinstance(v, str) and v in stems and ('image' in k or 'icon' in k or k == 'text'): add(v, f'ui/{rel}:{w.name or w.type}')
    sd = os.path.join(root, RAW, 'styles')
    for f in sorted(os.listdir(sd)):
        th = awtk_style.parse(open(os.path.join(sd, f), 'rb').read())
        for it in th.items:
            for k, t, v in it.props:
                if isinstance(v, str) and v in stems: add(v, f'styles/{f}:{it.style}')
    demo = open(os.path.join(root, 'bin/demo'), 'rb').read()
    for s in set(re.findall(rb'[A-Za-z0-9_%]{3,40}', demo)):
        s = s.decode()
        for e in EXPAND.get(s, [s]): add(e, 'demo')
    return out

def main():
    stock = sys.argv[1] if len(sys.argv) > 1 else STOCK
    rel = sys.argv[2] if len(sys.argv) > 2 else None
    r = refs(stock)
    xx = os.path.join(stock, RAW, 'images/xx')
    rows = []
    for stem in sorted(r):
        same = rel is None or sha(os.path.join(xx, stem + '.png')) == sha(os.path.join(rel, RAW, 'images/xx', stem + '.png'))
        rows.append((stem, same, sorted(r[stem])))
    for stem, same, who in rows:
        if rel is None or same:
            print(f'{stem}\t{len(who)}\t{"; ".join(who[:4])}')
    print(f'# {len(rows)} referenced, {sum(1 for _, s, _ in rows if s)} unchanged', file=sys.stderr)

if __name__ == '__main__': main()
