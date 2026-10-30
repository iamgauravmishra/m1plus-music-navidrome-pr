#!/usr/bin/env python3
"""Which stock functions can run on the boot path? A deliberately over-approximate reachability
check for pinned demo edits (docs/architecture.md, "Safety").

  reach.py DEMO ADDR... [--root main --root platform_init] [--cut 0x4d00c0]

Functions are the .dynsym function symbols plus every PIC prologue (lui $gp / addiu $gp / addu $gp,
$gp, $t9) in .text. F -> G is an edge whenever F's code produces G's start address in any way
tools/disasm.py tracks: a jal/bal target, a GOT load, a lui/addiu or lui/ori pair (so a callback F only
registers counts as called, too). From the roots (main and platform_init: everything that runs at
start-up, including every handler and thread they register) it walks every edge except into the
--cut functions (the navigator's open-by-name dispatcher, through which every page init runs when a
page is opened), and reports, for each ADDR, its function and whether it is reachable that way, with
one shortest chain if so.
"""
import argparse, bisect, collections, os, struct, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import disasm as m1dis

PROLOGUE = (0x3c1c0000, 0x279c0000, 0x0399e021)   # lui $gp, hi; addiu $gp, $gp, lo; addu $gp, $gp, $t9


def functions(b):
    va, size = b.text
    starts = {a for n, (a, sz) in b.syms.items() if va <= a < va + size}
    code = b.read(va, size)
    for off in range(0, size - 12, 4):
        w0, w1, w2 = struct.unpack_from('<III', code, off)
        if w0 & 0xffff0000 == PROLOGUE[0] and w1 & 0xffff0000 == PROLOGUE[1] and w2 == PROLOGUE[2]:
            starts.add(va + off)
    return sorted(starts)


def graph(b, starts):
    sset = set(starts)
    edges = collections.defaultdict(set)
    va, size = b.text; end = va + size; hi = {}
    fn = lambda a: starts[bisect.bisect_right(starts, a) - 1]
    while va < end:   # capstone stops at an undecodable word: skip it and resume
        nxt = va
        for ins in b.md.disasm(b.read(va, end - va), va):
            nxt = ins.address + 4
            if ins.address in sset: hi = {}
            b._track(ins, hi)
            vals = set(v for v in b.pre_clobber.values() if isinstance(v, int)) | set(v for v in hi.values() if isinstance(v, int))
            if ins.mnemonic in ('jal', 'bal', 'j'):
                try: vals.add(int(ins.op_str, 0))
                except ValueError: pass
            for v in vals:
                if v in sset and v != fn(ins.address): edges[fn(ins.address)].add(v)
        va = nxt + 4 if nxt < end else end
    return edges


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('demo'); ap.add_argument('addrs', nargs='+')
    ap.add_argument('--root', action='append', default=None); ap.add_argument('--cut', action='append', default=None)
    a = ap.parse_args()
    b = m1dis.Bin(a.demo); b.gp = m1dis.gp_of(b)
    starts = functions(b)
    edges = graph(b, starts)
    name = lambda f: b.by_addr.get(f, f'sub_{f:x}')
    roots = [b.syms[r][0] for r in (a.root or ['main', 'platform_init'])]
    cut = {int(c, 0) for c in (a.cut or ['0x4d00c0'])}
    prev = {r: None for r in roots}; q = collections.deque(roots)
    while q:
        f = q.popleft()
        for g in edges[f]:
            if g in cut or g in prev: continue
            prev[g] = f; q.append(g)
    print(f'{len(starts)} functions, {sum(len(v) for v in edges.values())} edges; from {", ".join(map(name, roots))}, '
          f'not through {", ".join(name(c) for c in cut)}: {len(prev)} reachable')
    bad = 0
    for x in a.addrs:
        t = int(x, 0); f = starts[bisect.bisect_right(starts, t) - 1]
        if f in prev:
            chain, g = [], f
            while g is not None: chain.append(name(g)); g = prev[g]
            print(f'{t:#x} {name(f)}: REACHABLE  ' + ' <- '.join(chain)); bad += 1
        else:
            print(f'{t:#x} {name(f)}: not reached')
    sys.exit(0)


if __name__ == '__main__': main()
