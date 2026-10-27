#!/usr/bin/env python3
"""The done-criterion for every change: build the release and the restore package, compare them to
the golden hashes, run the tests.

  venv/bin/python -I tools/check.py [--only release|restore] [--no-tests] [--update] [--keep]
                                    [--tests-only] [--test NAME[,NAME]]

- Builds both packages in parallel, each in its own work/out dirs under work/check/ (M1_WORK /
  M1_OUT, tools/paths.py). A target whose optional input is missing (Source Han Sans zip, LLVM) is
  SKIPPED with the reason, not failed. The release is built in two halves: the tree (tools/build.py
  --tree-only; the asset stages come from work/cache/build when their inputs are unchanged,
  tools/buildcache.py) and then the package (--pack-only), which runs while the tests already run.
- Compares each package's SHA-256 with test/golden.sha256 (`<sha256>  <tag>  <name>`): MATCH,
  CHANGED (exit 1 unless --update), NEW (not in golden yet).
- Tests, all in one process pool of os.cpu_count() workers, the slowest first (their last durations
  are kept in work/cache/test-times.json): test/patch.py (the emulated payload; one process per
  module of test/pod/) once per distinct payload (keyed by the built demo's SHA-256),
  test/demo_diff.py (the built demo differs from stock only where the mods say), test/coverflow.py
  (host build of the depth renderer), test/awtk_fill.py (demo's own AWTK fill code on the stock tree)
  and test/tools.py (fwtool verify, this script's decisions).
- --tests-only: no packaging, no golden comparison, no restore build; only the release tree the tests
  need. This is the done-criterion of a feature branch (docs/workflow.md). --test NAME[,NAME] runs only
  those tests (patch modules by name, e.g. albums or patch:albums; or tools, coverflow, awtk_fill,
  demo_diff) and implies --tests-only; the tree is built only if a selected test needs it.
- --update rewrites the golden lines of the selected targets (after you meant to change them, and
  README says so), but only when every build and test passed; otherwise it writes nothing and exits 1.
  When the last complete run of this very tree (same file contents apart from docs and the golden
  file, same tool versions) passed, --update reuses its results and only writes the golden file.
  --keep leaves work/check/<name>/ in place.
"""
import argparse, concurrent.futures as cf, glob, hashlib, json, os, re, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools'); TEST = os.path.join(ROOT, 'test')
GOLDEN = os.path.join(TEST, 'golden.sha256')
sys.path.insert(0, TOOLS)
import build, buildcache, paths   # noqa: E402

CACHE = os.path.join(ROOT, 'work', 'cache')
LAST = os.path.join(CACHE, 'check-last.json'); TIMES = os.path.join(CACHE, 'test-times.json')
TARGETS = {'release': (build.TAG, []), 'restore': (build.RESTORE_TAG, ['--restore'])}   # name -> (tag, build.py args)
MODULES = sorted(os.path.basename(f)[:-3] for f in glob.glob(os.path.join(TEST, 'pod', '*.py')) if not f.endswith('harness.py'))
LIGHT = ['tools', 'coverflow', 'awtk_fill']     # tests that need no built tree
ALL_TESTS = LIGHT + ['demo_diff'] + [f'patch:{m}' for m in MODULES]
NOT_KEYED = ('docs/', 'test/golden.sha256', 'README.md', 'AGENTS.md', 'NOTICE', 'LICENSE')   # cannot change a build or a test

def missing_input(name):
    if not os.path.exists(paths.ZIP): return f'missing {paths.ZIP}'
    if not shutil.which('mksquashfs'): return 'mksquashfs not on PATH (brew install squashfs)'
    if name == 'release':
        for env, d, what in (('LLVM_BIN', '/opt/homebrew/opt/llvm/bin', 'LLVM'), ('LLD_BIN', '/opt/homebrew/opt/lld/bin', 'LLD')):
            if not os.path.isdir(os.environ.get(env, d)): return f'{what} not found (brew install llvm lld)'
        if not os.path.exists(paths.SHS_ZIP): return 'fonts/09_SourceHanSansSC.zip missing (venv/bin/python -I tools/mod_font.py --fetch)'
    return None

sha256 = buildcache.file_sha

def sh(cmd, env=None):
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    return r.returncode, r.stdout + r.stderr

def counts(text):
    m = re.findall(r'(\d+) passed, (\d+) failed', text)
    return (int(m[-1][0]), int(m[-1][1])) if m else None

def env_for(base): return dict(os.environ, M1_WORK=os.path.join(base, 'work'), M1_OUT=os.path.join(base, 'out'))   # M1_NO_CACHE passes through
def base_of(name): return os.path.join(paths.ROOT, 'work', 'check', name)

def build_tree(name):
    """Worker (own process): the release tree in work/check/<name>/work/mod-*, no package."""
    t0 = time.time(); base = base_of(name)
    shutil.rmtree(base, ignore_errors=True)
    res = {'name': name, 'error': None, 'log': '', 'base': base}
    rc, log = sh([paths.VENV_PY, '-I', os.path.join(TOOLS, 'build.py'), '--tree-only', *TARGETS[name][1]], env_for(base))
    if rc: res['error'] = 'build failed'; res['log'] = log[-1500:]
    mods = glob.glob(os.path.join(base, 'work', 'mod-*'))
    if not rc and mods and os.path.exists(os.path.join(mods[0], 'podbuild', 'manifest.json')):
        res['tree'] = mods[0]
        res['payload'] = json.load(open(os.path.join(mods[0], 'podbuild', 'manifest.json')))['patched_demo_sha256']
    res['secs'] = time.time() - t0
    return res

def build_pack(name, flags):
    """Worker: the package of a built tree (--pack-only) or, for the restore, the whole build."""
    t0 = time.time(); base = base_of(name)
    if not flags: shutil.rmtree(base, ignore_errors=True)
    res = {'name': name, 'sha': None, 'error': None, 'log': '', 'pack': True}
    rc, log = sh([paths.VENV_PY, '-I', os.path.join(TOOLS, 'build.py'), *flags], env_for(base))
    pk = glob.glob(os.path.join(base, 'out', '*.bin'))
    if rc or len(pk) != 1: res['error'] = 'build failed' if rc else f'{len(pk)} packages'; res['log'] = log[-1500:]
    else: res['sha'] = sha256(pk[0])
    res['secs'] = time.time() - t0
    return res

def run_test(name, cmd, key=None):
    t0 = time.time(); rc, log = sh(cmd); c = counts(log)
    return {'test': name, 'key': key, 'rc': rc, 'counts': c, 'log': log[-2500:], 'secs': time.time() - t0}

def test_ok(t):
    """A test passed: exit 0 and no failure count (a crash or a non-zero exit never passes, counts or not)."""
    return t['rc'] == 0 and (t['counts'] is None or t['counts'][1] == 0)

def outcome(bad, changed, update):
    """(exit failure, write the golden file). A build or test failure always fails and never updates the
    golden hashes; a changed hash fails unless --update accepts it."""
    return bad or (changed and not update), update and not bad

def read_golden():
    g = {}
    if os.path.exists(GOLDEN):
        for line in open(GOLDEN):
            p = line.split()
            if len(p) >= 3 and not line.startswith('#'): g[p[2]] = (p[0], p[1])
    return g

# ---------------------------------------------------------------- last-run record (the --update shortcut)
def tree_key():
    """Identifies this tree's build and test inputs: the content of every tracked or untracked (not
    ignored) file except docs and the golden file, plus the tool versions. Content, not git state, so
    a commit or an amend of the same files keeps it."""
    r = subprocess.run(['git', '-C', ROOT, 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], capture_output=True, text=True)
    if r.returncode: return None
    parts = []
    for rel in sorted(set(x for x in r.stdout.split('\0') if x)):
        p = os.path.join(ROOT, rel)
        if rel.startswith(NOT_KEYED) or not os.path.isfile(p): continue
        parts += [rel, sha256(p)]
    tools = [buildcache.versions()]
    for cmd in (['mksquashfs', '-version'], [os.path.join(os.environ.get('LLVM_BIN', '/opt/homebrew/opt/llvm/bin'), 'clang'), '--version']):
        try: tools.append(subprocess.run(cmd, capture_output=True, text=True).stdout.splitlines()[0])
        except (OSError, IndexError): tools.append('none')
    return buildcache.H(*parts, *tools)

def load_json(p, default):
    try: return json.load(open(p))
    except (OSError, ValueError): return default

def save_json(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(obj, open(p, 'w'))

def test_priority(times):
    def key(name):
        if name in times: return times[name]
        f = os.path.join(TEST, 'pod', name[6:] + '.py') if name.startswith('patch:') else os.path.join(TEST, name + '.py')
        return os.path.getsize(f) / 5000 if os.path.exists(f) else 0     # unknown: by size
    return key

def test_cmd(name, stock, tree=None):
    py = [paths.VENV_PY, '-I']
    if name == 'tools': return py + [os.path.join(TEST, 'tools.py')]
    if name == 'coverflow': return py + [os.path.join(TEST, 'coverflow.py')]
    if name == 'awtk_fill': return py + [os.path.join(TEST, 'awtk_fill.py'), stock]
    if name == 'demo_diff':
        return py + [os.path.join(TEST, 'demo_diff.py'), os.path.join(stock, 'rootfs', 'release', 'bin', 'demo'),
                     os.path.join(tree, 'rootfs', 'release', 'bin', 'demo')]
    return py + [os.path.join(TEST, 'patch.py'), tree, name[6:]]

def parse_tests(spec):
    names = [('patch:' + n if n in MODULES else n) for s in spec for n in s.split(',') if n]
    bad = [n for n in names if n not in ALL_TESTS]
    if bad: sys.exit(f'unknown test {", ".join(bad)}; known: {", ".join(t.replace("patch:", "") for t in ALL_TESTS)}')
    return names

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--only', nargs='+', choices=list(TARGETS)); ap.add_argument('--no-tests', action='store_true')
    ap.add_argument('--keep', action='store_true'); ap.add_argument('--update', action='store_true')
    ap.add_argument('--tests-only', action='store_true'); ap.add_argument('--test', nargs='+', metavar='NAME[,NAME]')
    ap.add_argument('--no-cache', action='store_true', help='ignore work/cache/build (a cold build)')
    a = ap.parse_args(); t0 = time.time()
    if a.no_cache: os.environ['M1_NO_CACHE'] = '1'
    selected = parse_tests(a.test) if a.test else None
    if selected: a.tests_only = True
    if a.tests_only and (a.update or a.no_tests): sys.exit('--tests-only/--test cannot be combined with --update or --no-tests')
    stock = paths.find_stock() or os.path.join(paths.WORK, 'stock')
    run_names = [] if a.no_tests else [t for t in ALL_TESTS if not selected or t in selected]
    if 'awtk_fill' in run_names and not os.path.exists(os.path.join(stock, 'rootfs')): run_names.remove('awtk_fill')
    follow = [t for t in run_names if t == 'demo_diff' or t.startswith('patch:')]     # the tests that need the release tree
    sel = (['release'] if follow else []) if a.tests_only else [n for n in TARGETS if not a.only or n in a.only]
    golden = read_golden(); skipped = {n: missing_input(n) for n in sel if missing_input(n)}
    todo = [n for n in sel if n not in skipped]
    key = None if a.tests_only else tree_key()

    # --update right after a complete run of this very tree that passed: reuse it, only the golden file is written
    last = load_json(LAST, {})
    if a.update and key and last.get('key') == key and all(last['builds'].get(n, {}).get('sha') for n in todo) \
            and all(t in last['tests'] and test_ok(last['tests'][t]) for t in run_names):
        print(f'reusing the passing run of this tree ({time.strftime("%H:%M:%S", time.localtime(last["time"]))}); no rebuild, no tests')
        return finish(a, sel, skipped, golden, {n: last['builds'][n] for n in todo}, [last['tests'][t] for t in run_names], t0, reused=True)

    times = load_json(TIMES, {}); prio = test_priority(times)
    builds, tests = {}, []
    with cf.ProcessPoolExecutor(max_workers=os.cpu_count() or 4) as ex:
        pending = {ex.submit(build_tree, n) if n == 'release' else ex.submit(build_pack, n, TARGETS[n][1]) for n in todo}
        pending |= {ex.submit(run_test, t, test_cmd(t, stock)) for t in sorted((t for t in run_names if t in LIGHT), key=prio, reverse=True)}
        tree_secs = 0
        while pending:
            done, pending = cf.wait(pending, return_when=cf.FIRST_COMPLETED)
            for f in done:
                r = f.result()
                if 'test' in r: tests.append(r); continue
                if r['name'] == 'release' and not r.get('pack'):      # the tree is ready: tests and package start together
                    tree_secs = r['secs']
                    if not r['error'] and not r.get('tree'): r['error'] = 'no payload manifest in the tree'
                    if r['error'] or a.tests_only: builds['release'] = r
                    if r['error']: continue
                    if not a.tests_only: pending.add(ex.submit(build_pack, 'release', ['--pack-only']))
                    pending |= {ex.submit(run_test, t, test_cmd(t, stock, r['tree']), r['payload']) for t in sorted(follow, key=prio, reverse=True)}
                    continue
                if r['name'] == 'release': r['secs'] += tree_secs
                builds[r['name']] = r
    save_json(TIMES, {**times, **{t['test']: round(t['secs'], 1) for t in tests}})
    results = {t['test']: t for t in tests}
    finish(a, sel, skipped, golden, {n: builds[n] for n in todo}, [results[t] for t in run_names if t in results], t0, key=key)

def finish(a, sel, skipped, golden, builds, tests, t0, reused=False, key=None):
    bad = changed = False; npass = nfail = 0; rows = []   # bad: a build or test failed; changed: a hash differs from golden
    for n in sel:
        tag = TARGETS[n][0]
        if n in skipped: print(f'{n:8} {tag:7} SKIPPED: {skipped[n]}'); continue
        if n not in builds: continue
        r = builds[n]
        if r.get('error'): bad = True; print(f'{n:8} {tag:7} ERROR {r["error"]}\n{r["log"]}'); continue
        if a.tests_only: print(f'{n:8} {tag:7} tree built  {r["secs"]:3.0f}s'); continue
        g = golden.get(n); st = 'NEW' if not g else 'MATCH' if g[0] == r['sha'] else 'CHANGED'
        changed |= st == 'CHANGED'
        print(f'{n:8} {tag:7} {st:7} {r["sha"][:12]}  {r["secs"]:3.0f}s' + (f'  (golden {g[0][:12]})' if st == 'CHANGED' else ''))
        rows.append((n, tag, r['sha']))
    for t in sorted(tests, key=lambda t: t['test']):
        ok = test_ok(t); c = t['counts']
        if not ok: bad = True; print(t['log'])
        if c: npass += c[0]; nfail += c[1]
        print(f'test {t["test"]:15} {"PASS" if ok else "FAIL"}  {f"{c[0]} passed, {c[1]} failed" if c else ""}  {t["secs"]:.0f}s')
    print(f'checks {npass} passed, {nfail} failed; {time.time() - t0:.0f}s wall')
    if key and not reused:     # remember the run of this tree for --update (results of earlier partial runs of it are kept)
        old = load_json(LAST, {}) if load_json(LAST, {}).get('key') == key else {}
        save_json(LAST, {'key': key, 'time': time.time(),
                         'builds': {**old.get('builds', {}), **{n: {k: v for k, v in builds[n].items() if k in ('sha', 'secs', 'error', 'log')} for n in builds}},
                         'tests': {**old.get('tests', {}), **{t['test']: {k: t[k] for k in ('test', 'key', 'rc', 'counts', 'log', 'secs')} for t in tests}}})
    fail, write = outcome(bad, changed, a.update)
    if write:
        for n, tag, sha in rows: golden[n] = (sha, tag)
        with open(GOLDEN, 'w') as f:
            for n in TARGETS:
                if n in golden: f.write(f'{golden[n][0]}  {golden[n][1]}  {n}\n')
        print(f'updated {os.path.relpath(GOLDEN, ROOT)}')
    elif a.update: print('NOT updating the golden file: a build or test failed')
    if not a.keep and not reused: shutil.rmtree(os.path.join(paths.ROOT, 'work', 'check'), ignore_errors=True)
    sys.exit(1 if fail else 0)

if __name__ == '__main__': main()
