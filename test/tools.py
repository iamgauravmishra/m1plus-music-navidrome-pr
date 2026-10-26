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
    print(f'{ok} passed, {fail} failed')
    sys.exit(1 if fail else 0)


if __name__ == '__main__': main()
