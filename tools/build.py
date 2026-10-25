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
  build.py --variant POD                     the M1 Pod code payload, series 'd' (docs/payload.md)
      pod-inert | pod-hello | pod-menu | pod-cover    stages A B C D (V2.1dA dH dM dE)
  build.py --variant LOOK                    asset looks and payload features on top of pod-cover
      look-theme               Minimal neutral theme, icons, status bar (V2.1eT)
      look-lists               iPod-style library lists (V2.1eL)
      look-nowplaying          iPod-style Now Playing (V2.1fN; V2.1eN before the album fix)
      look-boot                M1 Pod boot logo, straight curly quotes, settings slides (V2.1eB)
      look-all                 all four, in that order (V2.1fA; V2.1eA before the album fix; docs/look-all.md)
      look-all-inter           the UI font (Inter + Source Han Sans SC) first, then all four (V2.1fI,
                               docs/font-inter.md; needs fontTools and `tools/mod_font.py --fetch`)
      look-lock2               look-all + the iPhone-style lock screen as the last step (V2.1fK, docs/lockscreen2.md)
      artists                  look-all on payload stage E: M1 Pod Artists + Cover Flow per artist (V2.1fR, docs/artists.md)
      shuffle                  look-all on payload stage F: Shuffle Songs / Albums / Folders (V2.1fS, docs/shuffle.md)
      full                     font + all four looks + lock screen 2 on payload stage G (Cover Flow + Artists
                               + Shuffle) (V2.1gA, docs/full.md; needs fontTools and `tools/mod_font.py --fetch`)
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
# M1 Pod payload variants (series 'd'): each stacks on lockscreen + icon+percent + space.
# variant -> (tag, pod stage, slug). The stages are tools/pod_pages.py STAGES: A installs no hook
# (inert); B = hello; C = menu; D = menu + Cover Flow (docs/coverflow.md, the device build);
# E = D + Artists, F = D + Shuffle, G = D + both (used by the LOOK variants below).
POD = {'pod-inert': ('V2.1dA', 'A', 'pod-inert'), 'pod-hello': ('V2.1dH', 'B', 'pod-hello'),
       'pod-menu': ('V2.1dM', 'C', 'pod-menu'), 'pod-cover': ('V2.1dE', 'D', 'pod-cover')}
# The asset steps a LOOK variant applies to its pod tree: name -> (module, extra args). Each
# tools/<module>.py WORKDIR WORKDIR [args] edits the tree in place (venv python: Pillow, fontTools);
# <module>.added_rels(stock rootfs), where defined, lists the files it adds (fwtool --allow-added).
STEPS = {'theme': ('mod_theme', []),                     # docs/look-theme.md
         'lists': ('mod_lists', []),                     # docs/look-lists.md
         'nowplaying': ('mod_nowplaying', []),           # docs/look-nowplaying.md
         'boot': ('mod_boot', []),                       # docs/look-boot.md
         'font': ('mod_font', []),                       # docs/font-inter.md
         'lock2': ('mod_lockscreen', ['--layout', 'cover', '--glyphs', 'np'])}   # docs/lockscreen2.md
# Steps in EARLY run right after the battery step, before the classic lock screen, so that every
# later step (lock screen clock size, Now Playing's album offset, boot's quote check, lock screen 2)
# measures the new font. Every other step runs after the payload, in the variant's order; lock2
# re-lays out screensaver_page.bin from scratch, so it goes last (it also needs nowplaying's np_*).
EARLY = ('font',)
LOOK_ALL = ['theme', 'lists', 'nowplaying', 'boot']     # docs/look-all.md: the order they stack in
# variant -> (tag, pod stage, steps). Series 'e': the single looks as first built; 'f': packages
# with the album fix, the font, lock screen 2 or a payload feature; 'g': everything (docs/full.md).
LOOK = {'look-theme': ('V2.1eT', 'D', ['theme']),
        'look-lists': ('V2.1eL', 'D', ['lists']),
        'look-nowplaying': ('V2.1fN', 'D', ['nowplaying']),
        'look-boot': ('V2.1eB', 'D', ['boot']),
        'look-all': ('V2.1fA', 'D', LOOK_ALL),
        'look-all-inter': ('V2.1fI', 'D', ['font'] + LOOK_ALL),       # docs/font-inter.md
        'look-lock2': ('V2.1fK', 'D', LOOK_ALL + ['lock2']),          # docs/lockscreen2.md
        'artists': ('V2.1fR', 'E', LOOK_ALL),                         # docs/artists.md
        'shuffle': ('V2.1fS', 'F', LOOK_ALL),                         # docs/shuffle.md
        'full': ('V2.1gA', 'G', ['font'] + LOOK_ALL + ['lock2'])}     # docs/full.md
# package slug (before -lockscreen-iconpercent-space); default '<variant>-pod-cover'
SLUG = {'artists': 'artists-look-all-pod-cover', 'shuffle': 'shuffle-look-all-pod-cover'}

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()

def run(*cmd): subprocess.run([sys.executable, '-I', *cmd], check=True)

# pod.py needs pyelftools; prefer the repo venv so `python3 -I tools/build.py` works too.
VENV_PY = next((p for p in (os.path.join(ROOT, 'venv', 'bin', 'python'),
                            os.path.join(ROOT, '.venv', 'bin', 'python')) if os.path.exists(p)), sys.executable)
def run_pod(*cmd): subprocess.run([VENV_PY, '-I', *cmd], check=True)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--variant', choices=list(VARIANTS) + list(POD) + list(LOOK)); g.add_argument('--restore', action='store_true')
    ap.add_argument('--no-space', action='store_true'); ap.add_argument('--watchdog', action='store_true')
    a = ap.parse_args()
    if a.restore and (a.no_space or a.watchdog): ap.error('--restore ships the stock images; no other options')
    if (a.variant in POD or a.variant in LOOK) and (a.no_space or a.watchdog): ap.error('pod and look variants always stack on lockscreen+icon+percent+space; no other options')
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
    elif a.variant in POD or a.variant in LOOK:
        import pod_pages, pod_ui, importlib
        if a.variant in POD: (tag, stage, slug), steps = POD[a.variant], []
        else: (tag, stage, names), slug = LOOK[a.variant], SLUG.get(a.variant, f'{a.variant}-pod-cover'); steps = [(n, *STEPS[n]) for n in names]
        slug = f'{slug}-lockscreen-iconpercent-space'
        mod = os.path.join(work, f'mod-{slug}')
        run(os.path.join(TOOLS, 'mod_battery.py'), stock, mod, '--variant', 'icon+percent')
        for name, module, args in steps:                                  # the font, before anything measures it
            if name in EARLY: run_pod(os.path.join(TOOLS, module + '.py'), mod, mod, *args)
        run(os.path.join(TOOLS, 'mod_lockscreen.py'), mod, mod)
        run(os.path.join(TOOLS, 'mod_space.py'), mod)                       # .pdr zero + remove (default)
        run_pod(os.path.join(TOOLS, 'pod.py'), mod, '--stage', stage)       # patch demo + add assets
        added = [x for rel in pod_ui.asset_rels(pod_pages.STAGES[stage]) for x in ('--allow-added', rel)]
        for name, module, args in steps:                                  # the looks, in order, in place
            if name not in EARLY: run_pod(os.path.join(TOOLS, module + '.py'), mod, mod, *args)
            rels = getattr(importlib.import_module(module), 'added_rels', None)
            added += [x for rel in (rels(os.path.join(stock, 'rootfs')) if rels else []) for x in ('--allow-added', rel)]
        if steps:   # contrast scan of the finished tree (window themes included) against stock
            run_pod(os.path.join(TOOLS, 'mod_theme.py'), '--scan', mod, stock)
        removed = [x for p in mod_space.REMOVE for x in ('--allow-removed', p)]
        out = os.path.join(ROOT, 'out', f'M1Plus-{tag}-{slug}-update.bin')
        run(os.path.join(TOOLS, 'fwtool.py'), 'repack', mod, out, '--version', tag, '--tailends', *removed, *added)
        shutil.rmtree(os.path.join(mod, 'build'), ignore_errors=True)
        # keep mod/podbuild (manifest + patch.elf) so test/patch.py can run against the built tree
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
