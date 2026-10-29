#!/usr/bin/env python3
"""Run the payload tests: the real compiled payload executed under Unicorn with the stock functions
and libc it calls mocked (test/pod/harness.py), one module per feature (test/pod/<name>.py, each
with a run(ctx)). Proves the hook's entry/fall-through logic, the trampoline, Cover Flow, Artists,
the album page, Shuffle, the library rows, the boot guard and the launcher on the actual MIPS code,
without a device. Modelled on q2-pod's test/patch.py (Copyright (c) 2026 Diamond Bond, MIT; see NOTICE).

Requires unicorn (venv) and a workdir built by tools/build.py (its podbuild/manifest.json).
Usage: venv/bin/python -I test/patch.py WORKDIR [MODULE[/SECTION]...]     (default: every module; SECTION: one function of
the module's SECTIONS list, which its run(ctx) runs in order and tools/check.py runs as separate tasks)
"""
import importlib.util, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
MODULES = sorted(f[:-3] for f in os.listdir(os.path.join(HERE, 'pod')) if f.endswith('.py') and f != 'harness.py')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod       # the feature modules star-import 'harness'
    spec.loader.exec_module(mod)
    return mod


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    work, wanted = sys.argv[1], sys.argv[2:] or MODULES
    harness = load('harness', os.path.join(HERE, 'pod', 'harness.py'))
    harness.init(work)
    ctx = harness.Ctx(work)
    print(f'harness: entry {harness.PSYMS["m1pod_home_click"]:#x}, hook {harness.MANIFEST["hook"]}')
    t0 = time.time()
    for name in wanted:
        before, t = (ctx.passed, ctx.failed), time.time()
        mod, _, section = name.partition('/')
        m = load(f'podtest_{mod}', os.path.join(HERE, 'pod', mod + '.py'))
        if section: next(f for f in m.SECTIONS if f.__name__ == section)(ctx)
        else: m.run(ctx)
        print(f'{name:10} {ctx.passed - before[0]:4} passed, {ctx.failed - before[1]} failed  {time.time() - t:5.1f}s')
    print(f'{ctx.passed} passed, {ctx.failed} failed  ({time.time() - t0:.1f}s)')
    sys.exit(1 if ctx.failed else 0)


if __name__ == '__main__': main()
