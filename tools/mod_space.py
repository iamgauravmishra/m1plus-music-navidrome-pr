#!/usr/bin/env python3
"""Space recovery for the M1 Plus rootfs, so mods that add data still fit the stock squashfs size.

Stock rebuilt with fwtool leaves ~12 KB headroom. This step frees room without changing behaviour:

  pdr      zero the .pdr section (MIPS procedure descriptors, a debugger-only table) of
           /release/bin/demo, as q2-pod does for the Q2. .pdr has address 0, no SHF_ALLOC flag and
           lies outside every program header, so the loader never maps it; it is there for
           debuggers (gdb). File size, headers and every other byte stay identical.
           --pdr-all (opt-in, not hardware-proven) does the same for all 197 executables and
           shared libraries: ~540 KB more compressed.
  remove   delete files nothing on the rootfs references (debug tools, orphaned old library
           versions whose soname symlinks point at the newer copy). Evidence: docs/firmware.md.
  watchdog (opt-in, off by default) checkappprocess.sh polls with `sleep 2` -> `sleep 10`, i.e.
           one pgrep fork every 10 s instead of every 2 s; a crashed UI reboots after <= 10 s.

The -tailends half of the saving lives in `fwtool.py repack --tailends`.

Usage: mod_space.py WORKDIR [--from STOCK_WORKDIR] [--no-pdr | --pdr-all] [--no-remove] [--watchdog]
  (modifies WORKDIR in place; with --from, WORKDIR is first cloned from STOCK_WORKDIR)
"""
import argparse, hashlib, os, shutil, struct, subprocess

ET_EXEC, ET_DYN, EM_MIPS = 2, 3, 8
SHT_PROGBITS, SHT_REL, SHT_RELA, SHT_NOBITS, SHF_ALLOC = 1, 9, 4, 8, 0x2

DEMO = 'release/bin/demo'
DEMO_SHA = '29e23119bc2a0f153f3ea0ba942a39754d1aab0879c1040fae2269df8bd9b3f1'
# --pdr-all: sha256 over "path sha256\n" of every stock ELF whose .pdr is zeroed (sorted): pins the input set
PDR_SET_SHA = '451ddb6c8f83a57344fbed385e90240da0c7555168aedf1c0fca2575e7f771aa'
PDR_SET_COUNT = 197   # REMOVE files are skipped, so the set is the same with or without removal

# path -> stock sha256. Unreferenced by name, symlink or DT_NEEDED anywhere on the rootfs.
REMOVE = {
    'usr/bin/strace':                     '3eaf7d7ed2ad7116f3a393865deab98525e622d6c9aa26e9e818417c32765d71',
    'usr/bin/strace-log-merge':           'ea9258d9805800d65394865104960f805d658661a492fd964b43454f2b6ac783',
    'usr/bin/sqlite3':                    '9defbf88974d2778d099c11166e8db4a4332e512ff971ee3bce2588e02d5e78a',  # needs libreadline.so.8, not shipped
    'usr/bin/hcidump':                    '9def339a96da11011c9b6e32dadf9733c24a15b76e9e6b7458697f30421241c4',
    'usr/lib/libdbus-1.so.3.19.8':        '7613791b2775d65462ee97ea735f996286e2b6ea36a073ba8cc6cfaaf1dfff85',  # libdbus-1.so.3 -> 3.19.15
    'usr/lib/libgio-2.0.so.0.5400.3':     '0433c55bb7a49e14f88933dd2b69d789a7b70780c54071e28f09725f055a6332',  # lib*-2.0.so.0 -> 0.7400.4
    'usr/lib/libglib-2.0.so.0.5400.3':    '0da66705d59b04c1246957663447e27e0c94933a9657ca59372772f4d3b76f0c',
    'usr/lib/libgmodule-2.0.so.0.5400.3': 'adf0cb303c0e19ed0381833f01b2c22dd3e87ce689c921fec1c2c788cccf3216',
    'usr/lib/libgobject-2.0.so.0.5400.3': '1473980eb06ce41477346b8a7ef3509a5e03045eeffa7a97707d64f0c80827b9',
    'usr/lib/libgthread-2.0.so.0.5400.3': '4c3628a06f1ee3cf4e36972a40cd7ba42214600b22a3910bd84e1c3a2ae4043a',
}

WATCHDOG = 'usr/bin/checkappprocess.sh'
WATCHDOG_STOCK = (b'#!/bin/sh\n#\n#\nwhile true\ndo\n\tpgrep "/release/bin/demo" > /dev/null;\n'
                  b'\tif [ $? -ne 0 ] \n   \tthen\n\t\treboot\n\tfi\n\tsleep 2\ndone\n')

def sha256(b): return hashlib.sha256(b).hexdigest()

def write_keep_mode(p, data):
    st = os.stat(p).st_mode & 0o7777
    os.chmod(p, 0o644); open(p, 'wb').write(data); os.chmod(p, st)

def find_pdr(d):
    """(offset, size) of an ELF's .pdr if it is provably never loaded, None if there is no .pdr.
    Raises AssertionError if a .pdr exists but is not safe to zero."""
    assert d[4] == 1 and d[5] == 1, 'need ELF32 LE'
    e_type, e_machine = struct.unpack_from('<HH', d, 16)
    e_phoff, e_shoff = struct.unpack_from('<II', d, 28)
    e_ehsize, phentsize, phnum, shentsize, shnum, shstrndx = struct.unpack_from('<HHHHHH', d, 40)
    if e_type not in (ET_EXEC, ET_DYN) or not shnum: return None      # leave .ko (ET_REL) alone
    assert e_machine == EM_MIPS
    shs = [struct.unpack_from('<10I', d, e_shoff + i * shentsize) for i in range(shnum)]
    so = shs[shstrndx][4]
    name = lambda s: d[so + s[0]:d.index(b'\0', so + s[0])]
    idx = [i for i, s in enumerate(shs) if name(s) == b'.pdr']
    if not idx: return None
    assert len(idx) == 1, 'several .pdr sections'
    i = idx[0]; _, typ, flags, addr, off, size = shs[i][:6]
    end = off + size
    assert typ == SHT_PROGBITS and not flags & SHF_ALLOC and addr == 0, '.pdr is allocated'
    assert 0 < off and end <= len(d)
    for ph in (struct.unpack_from('<8I', d, e_phoff + j * phentsize) for j in range(phnum)):
        assert not (ph[4] and ph[1] < end and off < ph[1] + ph[4]), f'.pdr inside a segment (type {ph[0]:#x})'
    for j, s in enumerate(shs):
        if j != i and s[1] != SHT_NOBITS and s[5]: assert not (s[4] < end and off < s[4] + s[5]), 'overlaps another section'
        if s[1] in (SHT_REL, SHT_RELA): assert s[7] != i, 'relocations target .pdr'
    for lo, n in ((0, e_ehsize), (e_phoff, phnum * phentsize), (e_shoff, shnum * shentsize)):
        assert not (lo < end and off < lo + n), 'overlaps ELF/program/section headers'
    return off, size

def zero_pdr(rootfs, all_elfs=False):
    """Zero .pdr in demo, or with all_elfs in every ET_EXEC/ET_DYN under rootfs; returns [(path, bytes)].
    Every file is checked (and the set pinned) before the first one is written."""
    todo, manifest = [], hashlib.sha256()
    paths = sorted(os.path.relpath(os.path.join(dp, f), rootfs) for dp, _, fn in os.walk(rootfs) for f in fn) if all_elfs else [DEMO]
    for rel in paths:
        p = os.path.join(rootfs, rel)
        if rel in REMOVE or os.path.islink(p) or not os.path.isfile(p): continue   # same set with or without removal
        with open(p, 'rb') as fh:
            if fh.read(4) != b'\x7fELF': continue
        d = open(p, 'rb').read()
        r = find_pdr(d)
        if not r: continue
        if rel == DEMO: assert sha256(d) == DEMO_SHA, f'{DEMO} is not the stock V2.1 binary'
        manifest.update(f'{rel} {sha256(d)}\n'.encode()); todo.append((rel, *r))
    assert DEMO in [t[0] for t in todo], f'{DEMO} has no .pdr to zero'
    assert not all_elfs or (len(todo) == PDR_SET_COUNT and manifest.hexdigest() == PDR_SET_SHA), \
        f'unexpected ELF set: {len(todo)} files, manifest {manifest.hexdigest()}'
    for rel, off, size in todo:
        p = os.path.join(rootfs, rel); d = bytearray(open(p, 'rb').read())
        d[off:off + size] = bytes(size)
        write_keep_mode(p, bytes(d))
    return [(rel, size) for rel, _, size in todo]

def remove_unused(rootfs):
    for rel, h in REMOVE.items():
        p = os.path.join(rootfs, rel)
        assert os.path.isfile(p) and not os.path.islink(p), f'missing {rel}'
        assert sha256(open(p, 'rb').read()) == h, f'{rel} is not the stock file'
    size = sum(os.path.getsize(os.path.join(rootfs, r)) for r in REMOVE)
    for rel in REMOVE: os.remove(os.path.join(rootfs, rel))
    return size

def slow_watchdog(rootfs):
    p = os.path.join(rootfs, WATCHDOG)
    assert open(p, 'rb').read() == WATCHDOG_STOCK, f'{WATCHDOG} is not the stock script'
    write_keep_mode(p, WATCHDOG_STOCK.replace(b'\tsleep 2\n', b'\tsleep 10\n'))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir'); ap.add_argument('--from', dest='src', metavar='STOCK_WORKDIR')
    g = ap.add_mutually_exclusive_group()
    g.add_argument('--no-pdr', action='store_true')
    g.add_argument('--pdr-all', action='store_true', help='zero .pdr in all 197 ELFs, not just demo (not hardware-proven)')
    ap.add_argument('--no-remove', action='store_true')
    ap.add_argument('--watchdog', action='store_true', help='checkappprocess.sh: sleep 2 -> sleep 10')
    a = ap.parse_args()
    if a.src:
        if os.path.exists(a.workdir): shutil.rmtree(a.workdir)
        # APFS clone (fast, no extra space); fall back to a plain copy elsewhere
        r = subprocess.run(['cp', '-Rc', a.src, a.workdir], capture_output=True)
        if r.returncode: shutil.copytree(a.src, a.workdir, symlinks=True)
        shutil.rmtree(os.path.join(a.workdir, 'build'), ignore_errors=True)
    rootfs = os.path.join(a.workdir, 'rootfs')
    if not a.no_remove: print(f'remove: {len(REMOVE)} unused files, {remove_unused(rootfs)} bytes')
    if not a.no_pdr:
        done = zero_pdr(rootfs, a.pdr_all)
        print(f'pdr: zeroed .pdr in {len(done)} ELFs, {sum(s for _, s in done)} bytes ({DEMO}: {dict(done)[DEMO]})')
    if a.watchdog: slow_watchdog(rootfs); print(f'watchdog: {WATCHDOG} sleep 2 -> sleep 10')

if __name__ == '__main__': main()
