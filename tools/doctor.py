#!/usr/bin/env python3
"""Check the uv environment, pinned inputs, native tools and Unicorn execution."""
import argparse, importlib.metadata, os, subprocess, sys, tempfile, tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths, workflow


def emulator():
    from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN
    from unicorn.mips_const import UC_MIPS_REG_V0
    uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    uc.mem_map(0x10000, 0x1000)
    uc.mem_write(0x10000, b'\x2a\x00\x02\x24')  # addiu v0, zero, 42
    uc.emu_start(0x10000, 0x10004)
    if uc.reg_read(UC_MIPS_REG_V0) != 42: raise SystemExit('Unicorn did not execute the MIPS smoke test')
    print('Unicorn MIPS execution: OK')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--emulator', action='store_true', help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.emulator: emulator(); return 0
    bad = []
    def check(label, ok, detail=''):
        print(f'{"OK" if ok else "FAIL"}: {label}{": " + detail if detail else ""}')
        if not ok: bad.append(label)
    check('Python 3.15', sys.version_info[:2] == (3, 15), sys.version.split()[0])
    project = tomllib.loads((Path(paths.ROOT) / 'pyproject.toml').read_text())
    for spec in project['project']['dependencies']:
        name, want = spec.split('==')
        try: got = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: got = 'missing'
        check(name, got == want, got)
    for tool, version in workflow.environment().items():
        if tool not in ('python', 'requirements'): check(tool, version != 'missing', version)
    import build, mod_font, mod_wpa
    for label, path, want in [('firmware', paths.ZIP, build.ZIP_SHA), ('Source Han Sans', paths.SHS_ZIP, mod_font.SHS_ZIP_SHA)]:
        check(label, os.path.isfile(path) and workflow.sha(path) == want, path)
    for url, want in [mod_wpa.HOSTAP] + [(mod_wpa.DEBIAN + n, s) for n, s in mod_wpa.DEBS]:
        path = mod_wpa.dl_path(url)
        check(os.path.basename(path), os.path.isfile(path) and workflow.sha(path) == want, f'{path} (run tools/mod_wpa.py --fetch)')
    llvm = os.environ.get('LLVM_BIN', '/opt/homebrew/opt/llvm/bin')
    try:
        targets = subprocess.run([os.path.join(llvm, 'clang'), '--print-targets'], capture_output=True, text=True, timeout=10)
        check('clang MIPS target', targets.returncode == 0 and 'mipsel' in targets.stdout)
        help_ = subprocess.run(['mksquashfs', '-help-all'], capture_output=True, text=True, timeout=10)
        check('mksquashfs tailends', '-tailends' in help_.stdout + help_.stderr)
    except (OSError, subprocess.SubprocessError) as exc: check('native build tools', False, str(exc))
    with tempfile.TemporaryDirectory() as td:
        rc, log = workflow.run_logged([sys.executable, '-I', __file__, '--emulator'], Path(td) / 'emulator.log', 15)
        check('Unicorn MIPS execution', rc == 0, workflow.exit_description(rc))
        if rc:
            print(log)
            print('A native signal here can mean the execution sandbox disallows Unicorn JIT. Use a permitted native test environment; changing Python is not the fix.')
    return bool(bad)


if __name__ == '__main__': sys.exit(main())
