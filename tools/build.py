#!/usr/bin/env python3
"""One-shot build: official zip in firmware/ -> flashable package in out/.

  build.py --variant VARIANT [--no-space] [--watchdog]
                                             mod package; the space step (mod_space.py + mksquashfs
                                             -tailends) is applied by default, --no-space skips it
                                             (reproduces the original V2.1bA / V2.1bB packages)
      space                    space step only, stock UI
      percent | icon+percent   battery-percentage status bar
      lockscreen               lock screen mod (big clock, small date, battery %)
      lockscreen+icon+percent  lock screen mod + the icon+percent status bar
  build.py --restore                         stock images with a new version tag (way back after a mod)

  --watchdog   also slow the demo watchdog poll from 2 s to 10 s (opt-in)

Pins the official zip by SHA-256 so a wrong or corrupted input is refused.
"""
import argparse, hashlib, os, subprocess, sys, zipfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
sys.path.insert(0, TOOLS)
import mod_space

ZIP = os.path.join(ROOT, 'firmware', 'M1 Plus Firmware V2.1.zip')
ZIP_SHA = 'db7bdbc42ffe6d5c1e3fdca9363edb78a01898b9a725c34793394cf6abfa33c0'
# variant -> (capital tag letters, slug); series letter: b = without, c = with the space step
VARIANTS = {'space': ('S', ''), 'percent': ('A', 'percent'), 'icon+percent': ('B', 'iconpercent'),
            'lockscreen': ('L', 'lockscreen'), 'lockscreen+icon+percent': ('LB', 'lockscreen-iconpercent')}

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()

def run(*cmd): subprocess.run([sys.executable, '-I', *cmd], check=True)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--variant', choices=VARIANTS); g.add_argument('--restore', action='store_true')
    ap.add_argument('--no-space', action='store_true'); ap.add_argument('--watchdog', action='store_true')
    a = ap.parse_args()
    if a.restore and (a.no_space or a.watchdog): ap.error('--restore ships the stock images; no other options')
    if a.variant == 'space' and a.no_space: ap.error('--variant space needs the space step')
    if not os.path.exists(ZIP): sys.exit(f'missing {ZIP}')
    if sha256(ZIP) != ZIP_SHA: sys.exit('firmware zip SHA-256 mismatch: not the pinned V2.1 package')
    work = os.path.join(ROOT, 'work'); os.makedirs(work, exist_ok=True); os.makedirs(os.path.join(ROOT, 'out'), exist_ok=True)
    stock = os.path.join(work, 'stock')
    if not os.path.exists(os.path.join(stock, 'meta.json')):
        with zipfile.ZipFile(ZIP) as z:
            name = [n for n in z.namelist() if n.endswith('update.bin')][0]
            z.extract(name, work)
        run(os.path.join(TOOLS, 'fwtool.py'), 'unpack', os.path.join(work, name), stock)
    if a.restore:
        out = os.path.join(ROOT, 'out', 'M1Plus-V2.1R-stock-restore-update.bin')
        run(os.path.join(TOOLS, 'fwtool.py'), 'repack', stock, out, '--version', 'V2.1R', '--reuse-squashfs')
    else:
        space = not a.no_space
        letter, slug = VARIANTS[a.variant]
        tag = 'V2.1' + ('c' if space else 'b') + letter + ('W' if a.watchdog else '')
        slug = '-'.join(s for s in (slug, 'space' if space else '', 'watchdog' if a.watchdog else '') if s)
        mod = os.path.join(work, f'mod-{slug}')
        if a.variant == 'space': src = ['--from', stock]
        else:
            src = []
            battery = a.variant.removeprefix('lockscreen').removeprefix('+')
            if battery: run(os.path.join(TOOLS, 'mod_battery.py'), stock, mod, '--variant', battery)
            if a.variant.startswith('lockscreen'): run(os.path.join(TOOLS, 'mod_lockscreen.py'), mod if battery else stock, mod)
        if space or a.watchdog:   # in place on the modded tree, or a fresh clone for --variant space
            run(os.path.join(TOOLS, 'mod_space.py'), mod, *src, *([] if space else ['--no-pdr', '--no-remove']),
                *(['--watchdog'] if a.watchdog else []))
        out = os.path.join(ROOT, 'out', f'M1Plus-{tag}-{slug}-update.bin')
        extra = ['--tailends', *(x for p in mod_space.REMOVE for x in ('--allow-removed', p))] if space else []
        run(os.path.join(TOOLS, 'fwtool.py'), 'repack', mod, out, '--version', tag, *extra)
        shutil.rmtree(os.path.join(mod, 'build'), ignore_errors=True)
    run(os.path.join(TOOLS, 'fwtool.py'), 'verify', out)
    print('->', out)

if __name__ == '__main__': main()
