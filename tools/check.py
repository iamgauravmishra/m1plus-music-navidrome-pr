#!/usr/bin/env python3
"""The done-criterion for every change: build the release and the restore package, compare them to
the golden hashes, run the tests.

  venv/bin/python -I tools/check.py [--only release|restore] [--no-tests] [--update] [--keep]

- Builds both packages in parallel, each in its own work/out dirs under work/check/ (M1_WORK /
  M1_OUT, tools/paths.py). A target whose optional input is missing (Source Han Sans zip, LLVM) is
  SKIPPED with the reason, not failed.
- Compares each package's SHA-256 with test/golden.sha256 (`<sha256>  <tag>  <name>`): MATCH,
  CHANGED (exit 1 unless --update), NEW (not in golden yet).
- Tests: test/patch.py (the emulated payload, one module per feature) once per distinct payload
  (keyed by the built demo's SHA-256), test/demo_diff.py (the built demo differs from stock only
  where the mods say), test/coverflow.py (host build of the depth renderer) and test/awtk_fill.py
  (demo's own AWTK fill code on the stock tree).
- --update rewrites the golden lines of the selected targets (after you meant to change them, and
  README says so). --keep leaves work/check/<name>/ in place.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, re, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools'); TEST = os.path.join(ROOT, 'test')
GOLDEN = os.path.join(TEST, 'golden.sha256')
sys.path.insert(0, TOOLS)
import paths   # noqa: E402

TARGETS = {'release': ('V2.1kE', []), 'restore': ('V2.1R', ['--restore'])}   # name -> (tag, build.py args)

def missing_input(name):
    if not os.path.exists(paths.ZIP): return f'missing {paths.ZIP}'
    if not shutil.which('mksquashfs'): return 'mksquashfs not on PATH (brew install squashfs)'
    if name == 'release':
        for env, d, what in (('LLVM_BIN', '/opt/homebrew/opt/llvm/bin', 'LLVM'), ('LLD_BIN', '/opt/homebrew/opt/lld/bin', 'LLD')):
            if not os.path.isdir(os.environ.get(env, d)): return f'{what} not found (brew install llvm lld)'
        if not os.path.exists(paths.SHS_ZIP): return 'fonts/09_SourceHanSansSC.zip missing (venv/bin/python -I tools/mod_font.py --fetch)'
    return None

def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
    return h.hexdigest()

def sh(cmd, env=None):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr

def counts(text):
    m = re.findall(r'(\d+) passed, (\d+) failed', text)
    return (int(m[-1][0]), int(m[-1][1])) if m else None

def build_one(name):
    """Worker (own process): build into work/check/<name>/; the tree is left for run_tree_tests."""
    t0 = time.time(); base = os.path.join(paths.ROOT, 'work', 'check', name)
    shutil.rmtree(base, ignore_errors=True)
    env = dict(os.environ, M1_WORK=os.path.join(base, 'work'), M1_OUT=os.path.join(base, 'out'))
    res = {'name': name, 'sha': None, 'error': None, 'log': '', 'base': base}
    rc, log = sh([paths.VENV_PY, '-I', os.path.join(TOOLS, 'build.py'), *TARGETS[name][1]], env)
    pk = glob.glob(os.path.join(base, 'out', '*.bin'))
    if rc or len(pk) != 1: res['error'] = 'build failed' if rc else f'{len(pk)} packages'; res['log'] = log[-1500:]
    else: res['sha'] = sha256(pk[0])
    mods = glob.glob(os.path.join(base, 'work', 'mod-*'))
    if mods and os.path.exists(os.path.join(mods[0], 'podbuild', 'manifest.json')):
        res['tree'] = mods[0]
        res['payload'] = json.load(open(os.path.join(mods[0], 'podbuild', 'manifest.json')))['patched_demo_sha256']
    res['secs'] = time.time() - t0
    return res

def run_test(name, cmd, key=None):
    t0 = time.time(); rc, log = sh(cmd); c = counts(log)
    return {'test': name, 'key': key, 'rc': rc, 'counts': c, 'log': log[-2500:], 'secs': time.time() - t0}

def read_golden():
    g = {}
    if os.path.exists(GOLDEN):
        for line in open(GOLDEN):
            p = line.split()
            if len(p) >= 3 and not line.startswith('#'): g[p[2]] = (p[0], p[1])
    return g

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', nargs='+', choices=list(TARGETS)); ap.add_argument('--no-tests', action='store_true')
    ap.add_argument('--keep', action='store_true'); ap.add_argument('--update', action='store_true')
    a = ap.parse_args(); t0 = time.time()
    sel = [n for n in TARGETS if not a.only or n in a.only]
    golden = read_golden(); skipped = {n: missing_input(n) for n in sel if missing_input(n)}
    todo = [n for n in sel if n not in skipped]
    stock = paths.find_stock() or os.path.join(paths.WORK, 'stock')
    builds, tests, payloads = {}, [], set()
    with cf.ProcessPoolExecutor(max_workers=4) as ex:
        futs = {ex.submit(build_one, n): n for n in todo}
        if not a.no_tests:
            futs[ex.submit(run_test, 'coverflow', [paths.VENV_PY, '-I', os.path.join(TEST, 'coverflow.py')])] = 'coverflow'
            if os.path.exists(os.path.join(stock, 'rootfs')):
                futs[ex.submit(run_test, 'awtk_fill', [paths.VENV_PY, '-I', os.path.join(TEST, 'awtk_fill.py'), stock])] = 'awtk_fill'
        pending = set(futs)
        while pending:
            done, pending = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
            for f in done:
                r = f.result()
                if 'test' in r: tests.append(r); continue
                builds[r['name']] = r
                if r.get('tree') and not a.no_tests:     # the emulator tests, once per distinct payload
                    if r['payload'] not in payloads:
                        payloads.add(r['payload'])
                        pending.add(ex.submit(run_test, 'patch.py', [paths.VENV_PY, '-I', os.path.join(TEST, 'patch.py'), r['tree']], r['payload']))
                    pending.add(ex.submit(run_test, 'demo_diff', [paths.VENV_PY, '-I', os.path.join(TEST, 'demo_diff.py'),
                                                                    os.path.join(stock, 'rootfs', 'release', 'bin', 'demo'),
                                                                    os.path.join(r['tree'], 'rootfs', 'release', 'bin', 'demo')]))

    fail = False; npass = nfail = 0; rows = []
    for n in sel:
        tag = TARGETS[n][0]
        if n in skipped: print(f'{n:8} {tag:7} SKIPPED: {skipped[n]}'); continue
        r = builds[n]
        if r['error']: fail = True; print(f'{n:8} {tag:7} ERROR {r["error"]}\n{r["log"]}'); continue
        g = golden.get(n); st = 'NEW' if not g else 'MATCH' if g[0] == r['sha'] else 'CHANGED'
        fail |= st == 'CHANGED'
        print(f'{n:8} {tag:7} {st:7} {r["sha"][:12]}  {r["secs"]:3.0f}s' + (f'  (golden {g[0][:12]})' if st == 'CHANGED' else ''))
        rows.append((n, tag, r['sha']))
    for t in sorted(tests, key=lambda t: t['test']):
        c = t['counts']; ok = t['rc'] == 0 and (c is None or c[1] == 0)
        if not ok: fail = True; print(t['log'])
        if c: npass += c[0]; nfail += c[1]
        print(f'test {t["test"]:10} {"PASS" if ok else "FAIL"}  {f"{c[0]} passed, {c[1]} failed" if c else ""}  {t["secs"]:.0f}s')
    print(f'checks {npass} passed, {nfail} failed; {time.time() - t0:.0f}s wall')
    if a.update:
        for n, tag, sha in rows: golden[n] = (sha, tag)
        with open(GOLDEN, 'w') as f:
            for n in TARGETS:
                if n in golden: f.write(f'{golden[n][0]}  {golden[n][1]}  {n}\n')
        print(f'updated {os.path.relpath(GOLDEN, ROOT)}'); fail = nfail > 0 or any(b['error'] for b in builds.values())
    if not a.keep: shutil.rmtree(os.path.join(paths.ROOT, 'work', 'check'), ignore_errors=True)
    sys.exit(1 if fail or nfail else 0)

if __name__ == '__main__': main()
