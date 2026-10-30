#!/usr/bin/env python3
"""One-shot build: official zip in firmware/ -> flashable package in out/.

  build.py             the release, M1+ Music (docs/architecture.md): the asset looks (docs/ui.md) and the
                       code payload on the official V2.1 rootfs -> out/M1Plus-<TAG>-release-update.bin
  build.py --restore   stock images with a new version tag (the way back after a mod)
  build.py --tree-only the release tree in work/mod-release only (what the tests need; no package)
  build.py --pack-only package an existing work/mod-release tree (the second half of a full build)
  build.py --no-cache  ignore work/cache/build (tools/buildcache.py; same as M1_NO_CACHE=1)

The updater refuses a package whose version equals the installed one: bump TAG for every package
that is flashed (docs/workflow.md). Pins the official zip by SHA-256 so a wrong or corrupted input
is refused. Every stage prints its time; "cached" marks a stage reused from work/cache/build.
"""
import argparse, hashlib, importlib, os, subprocess, sys, time, zipfile, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
sys.path.insert(0, TOOLS)
import mod_space, paths

ZIP = paths.ZIP     # this checkout's firmware/, else the main checkout's (tools/paths.py)
ZIP_SHA = 'db7bdbc42ffe6d5c1e3fdca9363edb78a01898b9a725c34793394cf6abfa33c0'
TAG = 'V2.1pB'
RESTORE_TAG = 'V2.1R'
# The asset steps after the payload, in order: name -> (module, extra args). Each
# tools/<module>.py WORKDIR WORKDIR [args] edits the tree in place (venv python: Pillow, fontTools);
# <module>.added_rels(stock rootfs, *args), where defined, lists the files it adds (fwtool --allow-added).
# The battery step runs first and the font right after it, before anything that measures text.
STEPS = [('mod_theme', []), ('mod_lists', []), ('mod_nowplaying', []), ('mod_boot', []),
         ('mod_ipodrows', []), ('mod_pulldown', []), ('mod_lockscreen', []), ('mod_wallpaper', []),
         ('mod_icons', []), ('mod_strings', []), ('mod_polish', []), ('mod_about', [TAG])]
BASE = ('mod_battery', 'mod_font', 'mod_space')     # stock tree -> battery art, font, space (cached as one stage)

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()

# the steps need Pillow, fontTools or pyelftools: run them with the repo venv
def run(*cmd):
    t = time.time(); subprocess.run([paths.VENV_PY, '-I', *cmd], check=True)
    print(f'  [{time.time() - t:5.1f}s] {os.path.basename(cmd[0])}', flush=True)

def stage_report(what, t, cached): print(f'  [{time.time() - t:5.1f}s] {what}{" (cached)" if cached else ""}', flush=True)

def make_tree(stock, mod, cache):
    """stock -> the finished release tree, every stage through tools/buildcache.py."""
    import buildcache as bc
    bc.ENABLED = bc.ENABLED and cache
    t = time.time(); key = bc.base_key(ZIP_SHA, *BASE)
    cached = bc.restore_base(key, mod)
    if not cached:
        run(os.path.join(TOOLS, 'mod_battery.py'), stock, mod)
        run(os.path.join(TOOLS, 'mod_font.py'), mod, mod)                  # before anything measures text
        run(os.path.join(TOOLS, 'mod_space.py'), mod)                      # .pdr zero + remove
        bc.store_base(key, mod)
    stage_report('base: battery, font, space', t, cached)
    before = bc.snap(mod)
    run(os.path.join(TOOLS, 'pod.py'), mod)                                # patch demo + add assets (always runs)
    changed, removed, _ = bc.delta_since(before, mod)
    prev = bc.H('pod', key, bc.delta_sha(mod, changed, removed))
    for module, args in STEPS:
        t = time.time(); prev = bc.step_key(prev, module, args)
        if bc.have_step(prev): bc.apply_delta(prev, mod); stage_report(module, t, True); continue
        before = bc.snap(mod)
        run(os.path.join(TOOLS, module + '.py'), mod, mod, *args)
        if bc.ENABLED:
            changed, removed, _ = bc.delta_since(before, mod); bc.store_delta(prev, mod, changed, removed)
    run(os.path.join(TOOLS, 'mod_theme.py'), '--scan', mod, stock)         # contrast scan of the finished tree

def pack_args(stock):
    """The --allow-added / --allow-removed flags of the release repack."""
    import pod_pages, pod_ui
    added = [x for rel in pod_ui.asset_rels(pod_pages.PAGES) for x in ('--allow-added', rel)]
    for module, args in STEPS:
        rels = getattr(importlib.import_module(module), 'added_rels', None)
        added += [x for rel in (rels(os.path.join(stock, 'rootfs'), *args) if rels else []) for x in ('--allow-added', rel)]
    return [x for p in mod_space.REMOVE for x in ('--allow-removed', p)], added

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--restore', action='store_true')
    ap.add_argument('--tree-only', action='store_true'); ap.add_argument('--pack-only', action='store_true')
    ap.add_argument('--no-cache', action='store_true')
    a = ap.parse_args()
    if not os.path.exists(ZIP): sys.exit(f'missing {ZIP}')
    if sha256(ZIP) != ZIP_SHA: sys.exit('firmware zip SHA-256 mismatch: not the pinned V2.1 package')
    work, outdir = paths.WORK, paths.OUT; os.makedirs(work, exist_ok=True); os.makedirs(outdir, exist_ok=True)
    stock = paths.find_stock(ZIP) or os.path.join(work, 'stock')   # a shared stock tree is read-only
    if not os.path.exists(os.path.join(stock, 'meta.json')):
        with zipfile.ZipFile(ZIP) as z:
            name = [n for n in z.namelist() if n.endswith('update.bin')][0]
            z.extract(name, work)
        run(os.path.join(TOOLS, 'fwtool.py'), 'unpack', os.path.join(work, name), stock)
    fwtool = os.path.join(TOOLS, 'fwtool.py')
    if a.restore:
        out = os.path.join(outdir, f'M1Plus-{RESTORE_TAG}-stock-restore-update.bin')
        run(fwtool, 'repack', stock, out, '--version', RESTORE_TAG, '--reuse-squashfs',
            '--build-dir', os.path.join(work, 'build-restore'))
    else:
        mod = os.path.join(work, 'mod-release')
        if not a.pack_only: make_tree(stock, mod, not a.no_cache)
        if a.tree_only: return
        removed, added = pack_args(stock)
        out = os.path.join(outdir, f'M1Plus-{TAG}-release-update.bin')
        run(fwtool, 'repack', mod, out, '--version', TAG, '--tailends', *removed, *added)
        shutil.rmtree(os.path.join(mod, 'build'), ignore_errors=True)
        # keep mod/podbuild (manifest + patch.elf) so test/patch.py can run against the built tree
    run(fwtool, 'verify', out)
    print('->', out)

if __name__ == '__main__': main()
