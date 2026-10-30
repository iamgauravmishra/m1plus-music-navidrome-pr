#!/usr/bin/env python3
"""Search the extracted stock tree (read-only; tools/paths.py finds it, also from a worktree), or with
--tree the release tree built in work/mod-release. Wraps tools/disasm.py, tools/awtk_ui.py and
tools/audit_images.py; the output is plain text.

  stock.py strings TEXT                strings of bin/demo containing TEXT: address and the functions that load them
  stock.py syms REGEX                  demo symbols matching REGEX: address, size, name
  stock.py sym NAME...                 disassemble functions of bin/demo by symbol
  stock.py addr ADDR [LEN]             disassemble a range of bin/demo
  stock.py callers ADDR|SYM            every call site and address load of a function or address
  stock.py ui NAME [--widget W]        ui/*.bin files whose name contains NAME: the widget tree, or only
                                       the subtree of the widget(s) named W
  stock.py images PATTERN              images/xx/*.png whose name contains PATTERN: size, and who refers to it
  stock.py style NAME                  styles/NAME*.bin dumped (awtk_style)
  stock.py paths                       the resolved stock and tree locations
Options: --tree (use the built release tree, work/mod-release), --theme default|theme1 (default: default).
"""
import argparse, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

TOOLS = os.path.dirname(os.path.abspath(__file__))
RAW = 'rootfs/release/assets/{theme}/raw'

def root(tree):
    if tree:
        r = os.path.join(paths.WORK, 'mod-release')
        if not os.path.isdir(r): sys.exit(f'{r}: no built tree (uv run python -I tools/build.py --tree-only)')
        return r
    s = paths.find_stock()
    if not s: sys.exit('no unpacked stock tree (uv run python -I tools/build.py unpacks it)')
    return s

def dis(*args): sys.exit(subprocess.run([sys.executable, '-I', os.path.join(TOOLS, 'disasm.py'), *args]).returncode)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd', choices=['strings', 'syms', 'sym', 'addr', 'callers', 'ui', 'images', 'style', 'paths'])
    ap.add_argument('args', nargs='*'); ap.add_argument('--tree', action='store_true'); ap.add_argument('--widget')
    ap.add_argument('--theme', default='default')
    a = ap.parse_args(); A = a.args
    if a.cmd == 'paths':
        print('stock', root(False)); print('tree ', os.path.join(paths.WORK, 'mod-release')); return
    r = root(a.tree); demo = os.path.join(r, 'rootfs', 'release', 'bin', 'demo'); raw = os.path.join(r, RAW.format(theme=a.theme))
    if not A: ap.error(f'{a.cmd} needs an argument')
    if a.cmd == 'strings': dis('strings-xref', demo, A[0])
    elif a.cmd == 'syms': dis('syms', demo, A[0])
    elif a.cmd == 'sym': dis('sym', demo, *A)
    elif a.cmd == 'addr': dis('addr', demo, *A)
    elif a.cmd == 'callers': dis('callers', demo, A[0])
    elif a.cmd == 'ui':
        import awtk_ui
        files = [os.path.join(d, f) for d, _, fs in os.walk(os.path.join(raw, 'ui')) for f in sorted(fs) if A[0] in f]
        if not files: sys.exit(f'no ui file with "{A[0]}" in its name under {os.path.join(raw, "ui")}')
        for p in sorted(files):
            tree = awtk_ui.parse(open(p, 'rb').read())
            print(f'# {os.path.abspath(p)}')
            if not a.widget: awtk_ui.dump(tree)
            else:
                hits = [w for w in tree.walk() if w.name == a.widget]
                if not hits: print(f'  (no widget named {a.widget})')
                for w in hits: awtk_ui.dump(w)
    elif a.cmd == 'images':
        from PIL import Image
        import audit_images
        refs = audit_images.refs(os.path.join(r, 'rootfs', 'release'))
        xx = os.path.join(raw, 'images', 'xx')
        names = sorted(f for f in os.listdir(xx) if A[0] in f)
        for f in names:
            try: size = '%dx%d' % Image.open(os.path.join(xx, f)).size
            except OSError: size = '?'
            who = sorted(refs.get(f.rsplit('.', 1)[0], ()))
            print(f'{f}\t{size}\t{"; ".join(who[:5]) or "-"}{" ..." if len(who) > 5 else ""}')
        print(f'# {len(names)} image(s) in {os.path.abspath(xx)}', file=sys.stderr)
    elif a.cmd == 'style':
        import awtk_style
        sd = os.path.join(raw, 'styles')
        for f in sorted(x for x in os.listdir(sd) if x.startswith(A[0])):
            print(f'# {os.path.abspath(os.path.join(sd, f))}')
            th = awtk_style.parse(open(os.path.join(sd, f), 'rb').read())
            for it in th.items:
                print(it.style, *[f'{k}={v!r}' for k, t, v in it.props])

if __name__ == '__main__': main()
