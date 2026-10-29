#!/usr/bin/env python3
"""Tests of the build tooling itself (no firmware needed): fwtool's package verification on synthetic
update files and check.py's pass/fail/--update decisions.

  venv/bin/python -I test/tools.py
"""
import hashlib, io, os, sys, tarfile, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import fwtool, check   # noqa: E402

ok = fail = 0


def expect(name, cond):
    global ok, fail
    if cond: ok += 1
    else: fail += 1; print(f'FAIL {name}')


def make(path, manifest=None, files=None, extra=(), model='Shanling M1 Plus', dup=None, drop=()):
    """A synthetic update tar. files: payload name -> bytes; manifest: list of lines (default: correct)."""
    files = {'recovery-update/xImage': b'kernel', 'recovery-update/rootfs.squashfs': b'rootfs'} if files is None else files
    if manifest is None:
        manifest = [f'{hashlib.md5(d).hexdigest()}  {n}' for n, d in files.items()]
    info = '\n'.join([model, 'V9.9x'] + manifest) + '\n'
    with tarfile.open(path, 'w') as t:
        def add(name, data, typ=tarfile.REGTYPE):
            ti = tarfile.TarInfo(name); ti.type = typ; ti.size = len(data) if typ == tarfile.REGTYPE else 0
            t.addfile(ti, io.BytesIO(data) if typ == tarfile.REGTYPE else None)
        add(fwtool.INFO_NAME, info.encode())
        add('recovery-update', b'', tarfile.DIRTYPE)
        for n, d in files.items():
            if n not in drop: add(n, d)
        for n in extra: add(n, b'x')
        if dup: add(dup, b'again')


def problems(**kw):
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'u.bin'); make(p, **kw)
        return fwtool.verify_package(p)[0]


def main():
    expect('good package verifies', problems() == [])
    expect('manifest-only archive rejected', problems(files={}) != [])
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'u.bin')
        with tarfile.open(p, 'w') as t:
            info = b'Shanling M1 Plus\nV9.9x\n'
            ti = tarfile.TarInfo(fwtool.INFO_NAME); ti.size = len(info); t.addfile(ti, io.BytesIO(info))
        expect('manifest-only tar: verify command fails', fwtool.cmd_verify(type('A', (), {'update': p})) == 1)
        open(p, 'wb').write(b'not a tar')
        expect('non-tar rejected', fwtool.verify_package(p)[0] != [])
    good = [f'{hashlib.md5(b"kernel").hexdigest()}  recovery-update/xImage',
            f'{hashlib.md5(b"rootfs").hexdigest()}  recovery-update/rootfs.squashfs']
    expect('empty manifest rejected', problems(manifest=[]) != [])
    expect('truncated manifest (one entry) rejected', problems(manifest=good[:1]) != [])
    expect('malformed checksum line rejected', problems(manifest=good + ['zz  recovery-update/other']) != [])
    expect('duplicate checksum line rejected', problems(manifest=good + good[:1]) != [])
    expect('extra manifest entry rejected', problems(manifest=good + [f'{"0" * 32}  recovery-update/extra']) != [])
    expect('md5 mismatch rejected', problems(manifest=['0' * 32 + '  recovery-update/xImage', good[1]]) != [])
    expect('wrong model rejected', problems(model='Other Player') != [])
    expect('missing payload file rejected', problems(drop=('recovery-update/xImage',)) != [])
    expect('unexpected member rejected', problems(extra=('recovery-update/evil',)) != [])
    expect('path traversal member rejected', problems(extra=('../evil',)) != [])
    expect('duplicate member rejected', problems(dup='recovery-update/xImage') != [])

    # check.py: a failing test never passes, and --update never blesses a failed run
    t = lambda rc, c: {'rc': rc, 'counts': c}
    expect('test crash without counts fails', not check.test_ok(t(-11, None)))
    expect('non-zero exit after a success line fails', not check.test_ok(t(1, (10, 0))))
    expect('failed count fails', not check.test_ok(t(1, (9, 1))))
    expect('clean run passes', check.test_ok(t(0, (10, 0))) and check.test_ok(t(0, None)))
    expect('plain match passes', check.outcome(False, False, False) == (False, False))
    expect('changed hash fails without --update', check.outcome(False, True, False) == (True, False))
    expect('--update accepts a changed hash', check.outcome(False, True, True) == (False, True))
    expect('--update with a failed test fails and writes nothing', check.outcome(True, True, True) == (True, False))
    expect('--update with a failed test and no change fails', check.outcome(True, False, True) == (True, False))

    # check.py --test: names resolve to patch modules (a module with SECTIONS: one test per section) or the named tests; unknown names are refused
    expect('--test resolves a patch module', check.parse_tests(['home,tools']) == ['patch:home', 'tools'])
    albums = [f'patch:albums/{s}' for s in check.sections('albums')]
    expect('a module with SECTIONS is one test per section, by name or as patch:', len(albums) > 1 and check.parse_tests(['albums']) == check.parse_tests(['patch:albums']) == albums)
    expect('--test runs one section', check.parse_tests([albums[1][6:]]) == [albums[1]])
    try: check.parse_tests(['nosuchtest']); refused = False
    except SystemExit: refused = True
    expect('--test refuses an unknown name', refused)

    # the build cache: a rewrite that keeps size and mtime (the steps set mtimes on purpose) is still a change
    import buildcache, subprocess
    with tempfile.TemporaryDirectory() as td:
        root = os.path.join(td, 'tree'); os.makedirs(os.path.join(root, 'd'))
        for n, d in (('a', b'one'), ('d/b', b'two'), ('gone', b'x')): open(os.path.join(root, n), 'wb').write(d)
        os.symlink('a', os.path.join(root, 'lnk'))
        before = buildcache.snap(root); st = os.stat(os.path.join(root, 'a'))
        open(os.path.join(root, 'a'), 'wb').write(b'ONE'); os.utime(os.path.join(root, 'a'), ns=(st.st_atime_ns, st.st_mtime_ns))
        open(os.path.join(root, 'new'), 'wb').write(b'n'); os.remove(os.path.join(root, 'gone'))
        changed, removed, _ = buildcache.delta_since(before, root)
        expect('delta sees a same-size same-mtime rewrite, an addition, a removal', sorted(changed) == ['a', 'new'] and removed == ['gone'])
        buildcache.CACHE = os.path.join(td, 'cache'); buildcache.ENABLED = True
        buildcache.store_delta('k', root, changed, removed)
        other = os.path.join(td, 'other'); os.makedirs(other)
        for n, d in (('a', b'one'), ('gone', b'x')): open(os.path.join(other, n), 'wb').write(d)
        buildcache.apply_delta('k', other)
        expect('a stored delta reproduces the tree', open(os.path.join(other, 'a'), 'rb').read() == b'ONE'
               and os.path.exists(os.path.join(other, 'new')) and not os.path.exists(os.path.join(other, 'gone')))
    expect('code hash follows imports', 'modlib' in buildcache.closure('mod_theme') or 'awtk_ui' in buildcache.closure('mod_theme'))

    # sub.py refuses an ambiguous or missing OLD and changes nothing
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, 'f.txt'); open(f, 'w').write('x = 1\nx = 1\ny = 2\n')
        sub = lambda *a: subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'tools', 'sub.py'), f, *a], capture_output=True, text=True).returncode
        expect('sub: ambiguous OLD refused', sub('x = 1', 'x = 3') == 1 and open(f).read() == 'x = 1\nx = 1\ny = 2\n')
        expect('sub: missing OLD refused', sub('z', 'w') == 1)
        expect('sub: --all replaces every occurrence', sub('x = 1', 'x = 3', '--all') == 0 and open(f).read() == 'x = 3\nx = 3\ny = 2\n')
    print(f'{ok} passed, {fail} failed')
    sys.exit(1 if fail else 0)


if __name__ == '__main__': main()
