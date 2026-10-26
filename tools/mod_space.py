#!/usr/bin/env python3
"""Space recovery for the M1 Plus rootfs, so the mod's added data still fits the stock squashfs size.

Stock rebuilt with fwtool leaves ~12 KB headroom. This step frees room without changing behaviour:

  pdr      zero the .pdr section (MIPS procedure descriptors, a debugger-only table) of
           /release/bin/demo, as q2-pod does for the Q2. .pdr has address 0, no SHF_ALLOC flag and
           lies outside every program header, so the loader never maps it; it is there for
           debuggers (gdb). File size, headers and every other byte stay identical.
  remove   delete files nothing on the rootfs references (debug tools, orphaned old library
           versions whose soname symlinks point at the newer copy). Evidence: docs/firmware.md.

The -tailends half of the saving lives in `fwtool.py repack --tailends`.

Usage: mod_space.py WORKDIR   (modifies WORKDIR in place)
"""
import hashlib, os, struct, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import write_keep_mode

ET_EXEC, ET_DYN, EM_MIPS = 2, 3, 8
SHT_PROGBITS, SHT_REL, SHT_RELA, SHT_NOBITS, SHF_ALLOC = 1, 9, 4, 8, 0x2

DEMO = 'release/bin/demo'
DEMO_SHA = '29e23119bc2a0f153f3ea0ba942a39754d1aab0879c1040fae2269df8bd9b3f1'

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

def sha256(b): return hashlib.sha256(b).hexdigest()

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

def zero_pdr(rootfs):
    """Zero .pdr in demo (pinned by SHA-256 first); returns the number of bytes."""
    p = os.path.join(rootfs, DEMO)
    d = bytearray(open(p, 'rb').read())
    assert sha256(d) == DEMO_SHA, f'{DEMO} is not the stock V2.1 binary'
    r = find_pdr(d)
    assert r, f'{DEMO} has no .pdr to zero'
    off, size = r
    d[off:off + size] = bytes(size)
    write_keep_mode(p, bytes(d))
    return size

def remove_unused(rootfs):
    for rel, h in REMOVE.items():
        p = os.path.join(rootfs, rel)
        assert os.path.isfile(p) and not os.path.islink(p), f'missing {rel}'
        assert sha256(open(p, 'rb').read()) == h, f'{rel} is not the stock file'
    size = sum(os.path.getsize(os.path.join(rootfs, r)) for r in REMOVE)
    for rel in REMOVE: os.remove(os.path.join(rootfs, rel))
    return size

def main():
    if len(sys.argv) != 2: sys.exit(__doc__)
    rootfs = os.path.join(sys.argv[1], 'rootfs')
    print(f'remove: {len(REMOVE)} unused files, {remove_unused(rootfs)} bytes')
    print(f'pdr: zeroed .pdr in {DEMO}, {zero_pdr(rootfs)} bytes')

if __name__ == '__main__': main()
