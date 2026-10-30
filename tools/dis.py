#!/usr/bin/env python3
"""MIPS32 LE disassembly helper (capstone + pyelftools) for the Shanling 'demo' binary.

  dis.py sym  ELF NAME...          disassemble functions by (dyn)symbol name
  dis.py addr ELF ADDR [LEN]       disassemble a range
  dis.py words ELF ADDR [COUNT]    the raw instruction words (to pin them)
  dis.py xref ELF STRING...        find lui/addiu(ori) pairs referencing the address of a NUL-terminated string
  dis.py strxref ELF ADDR          find code referencing an absolute address
  dis.py callers ELF ADDR|SYM      every call site (jal/j/bal, jalr through a register or the GOT) and every
                                   load of the address (lui/addiu/ori, GOT slot), from a scan of all of .text
  dis.py strings-xref ELF "TEXT"   strings containing TEXT -> the functions that load their address
  dis.py full ELF                  write the whole .text, annotated, to work/cache/<elf name>.dis (keyed by
                                   the ELF's SHA-256; callers / strings-xref reuse it, grep it freely)
Each cached line ends in =0xVALUE when it calls or loads that value, so `grep '=0x533b80$'` finds callers.
Calls (jal / jalr via GOT loads) are annotated with symbol names where possible.
"""
import sys, struct, bisect, os, hashlib
sys.path.append(os.path.dirname(os.path.abspath(__file__)))   # appended: this file must not shadow the stdlib dis
import paths
from elftools.elf.elffile import ELFFile
from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN

class Bin:
    def __init__(self, path):
        self.f = open(path, 'rb'); self.elf = ELFFile(self.f)
        self.data = open(path, 'rb').read()
        self.segs = [(s['p_vaddr'], s['p_filesz'], s['p_offset']) for s in self.elf.iter_segments() if s['p_type'] == 'PT_LOAD']
        self.syms = {}; self.by_addr = {}
        for secname in ('.dynsym', '.symtab'):
            sec = self.elf.get_section_by_name(secname)
            if not sec: continue
            for s in sec.iter_symbols():
                if s['st_value'] and s.name:
                    self.syms.setdefault(s.name, (s['st_value'], s['st_size']))
                    self.by_addr.setdefault(s['st_value'], s.name)
        self.addrs = sorted(self.by_addr)
        text = self.elf.get_section_by_name('.text'); self.text = (text['sh_addr'], text['sh_size'])
        self.md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 | CS_MODE_LITTLE_ENDIAN); self.md.detail = False
        # GOT -> symbol map via .dynamic MIPS_LOCAL_GOTNO / MIPS_GOTSYM
        self.got = {}
        dyn = self.elf.get_section_by_name('.dynamic'); got = self.elf.get_section_by_name('.got'); dynsym = self.elf.get_section_by_name('.dynsym')
        if dyn and got and dynsym:
            tags = {t.entry.d_tag: t.entry.d_val for t in dyn.iter_tags()}
            local, gotsym = tags.get('DT_MIPS_LOCAL_GOTNO'), tags.get('DT_MIPS_GOTSYM')
            if local is not None and gotsym is not None:
                n = dynsym.num_symbols()
                for i in range(gotsym, n):
                    self.got[got['sh_addr'] + 4 * (local + i - gotsym)] = dynsym.get_symbol(i).name
    def off(self, va):
        for a, sz, o in self.segs:
            if a <= va < a + sz: return o + va - a
        return None
    def read(self, va, n):
        o = self.off(va); return self.data[o:o + n] if o is not None else b''
    def cstr(self, va, n=80):
        b = self.read(va, n); e = b.find(b'\0'); return b[:e if e >= 0 else n]
    def name(self, va):
        if va in self.by_addr: return self.by_addr[va]
        i = bisect.bisect_right(self.addrs, va) - 1
        if i >= 0 and va - self.addrs[i] < 0x4000: return f'{self.by_addr[self.addrs[i]]}+{va - self.addrs[i]:#x}'
        return hex(va)
    def _track(self, ins, hi):
        """Update hi (reg -> absolute value) for lui / lw off($gp) / addiu / ori; return note string."""
        ops = ins.op_str.replace(' ', ''); note = ''
        if ins.mnemonic == 'lui':
            r, imm = ops.split(','); hi[r] = int(imm, 0) << 16
        elif ins.mnemonic == 'lw' and '(' in ops:
            r, rest = ops.split(',', 1); imm, base = rest[:-1].split('(')
            hi.pop(r, None)
            if base == '$gp':
                slot = (self.gp + int(imm, 0)) & 0xffffffff
                if slot in self.got:
                    note = f'; GOT {self.got[slot]}'; hi[r] = self.syms.get(self.got[slot], (None,))[0]
                else:
                    v = self.read(slot, 4)
                    if len(v) == 4: hi[r] = struct.unpack('<I', v)[0]; note = f'; GOT page {hi[r]:#x}'
        elif ins.mnemonic in ('addiu', 'ori'):
            p = ops.split(',')
            if len(p) == 3 and hi.get(p[1]) is not None:
                imm = int(p[2], 0)
                a = (hi[p[1]] + (imm if ins.mnemonic == 'ori' else (imm if imm < 0x8000 else imm - 0x10000))) & 0xffffffff
                hi[p[0]] = a
                s = self.cstr(a)
                if len(s) >= 2 and all(32 <= c < 127 for c in s): note = f'; {a:#x} "{s.decode()}"'
                elif self.off(a) is not None: note = f'; {a:#x} {self.name(a)}'
            elif len(p) == 3: hi.pop(p[0], None)
        elif ins.mnemonic in ('jal', 'j', 'bal'):
            t = int(ops, 0); note = f'; {self.name(t)}'
        elif ins.mnemonic == 'jalr':
            r = ops.split(',')[-1]
            if hi.get(r): note = f'; -> {self.name(hi[r])}'
        elif ins.mnemonic.startswith('b'):
            try: t = int(ops.split(',')[-1], 0); note = f'; -> {t:#x}'
            except ValueError: pass
        elif ',' in ops and ins.mnemonic not in ('sw', 'sb', 'sh', 'swc1', 'sdc1'):
            hi.pop(ops.split(',')[0], None)
        # branch delay slot: the instruction after a call still sees pre-call registers
        self.pre_clobber = dict(hi)   # values as the call sees them (xref needs delay-slot arguments)
        if hi.pop('__clobber__', None):
            for r in list(hi):
                if r[1] in 'vat': hi.pop(r)
        if ins.mnemonic in ('jalr', 'jal', 'bal'): hi['__clobber__'] = 1
        return note
    def dis(self, va, size, out=sys.stdout):
        code = self.read(va, size); hi = {}
        for ins in self.md.disasm(code, va):
            note = self._track(ins, hi)
            print(f'{ins.address:#010x}  {ins.mnemonic:8s} {ins.op_str:32s} {note}', file=out)
    def find_str(self, s):
        b = s.encode() + b'\0'; res = []; i = self.data.find(b'\0' + b)
        while i >= 0:
            for a, sz, o in self.segs:
                if o <= i + 1 < o + sz: res.append(a + i + 1 - o)
            i = self.data.find(b'\0' + b, i + 1)
        return res
    def xref(self, target):
        """Scan .text for register values equal to target (GOT-page/lui + addiu/ori). Returns addresses."""
        va, size = self.text; end = va + size; res = []; hi = {}
        while va < end:   # capstone stops at an undecodable word (data in .text): skip it and resume
            nxt = va
            for ins in self.md.disasm(self.read(va, end - va), va):
                before = dict(hi); self._track(ins, hi); nxt = ins.address + 4
                if ins.mnemonic in ('addiu', 'ori', 'lw'):
                    r = ins.op_str.replace(' ', '').split(',')[0]
                    if self.pre_clobber.get(r) == target and before.get(r) != target: res.append(ins.address)
            va = nxt + 4 if nxt < end else end
        return res

def _scan(b):
    """Every instruction of .text, resuming after undecodable words: (address, mnemonic, ops, note, value, raw);
    value = the call target / the address a load puts in a register (None otherwise); raw only for data words."""
    va, size = b.text; end = va + size; hi = {}
    while va < end:
        nxt = va
        for ins in b.md.disasm(b.read(va, end - va), va):
            before = dict(hi); note = b._track(ins, hi); nxt = ins.address + 4
            m, ops, val = ins.mnemonic, ins.op_str.replace(' ', ''), None
            if m in ('jal', 'j', 'bal'): val = int(ops, 0)
            elif m == 'jalr': val = before.get(ops.split(',')[-1])
            elif m in ('addiu', 'ori', 'lw'):
                v = b.pre_clobber.get(ops.split(',')[0])
                if v is not None and v != before.get(ops.split(',')[0]): val = v
            yield ins.address, m, ins.op_str, note, val, None
        if nxt < end:
            yield nxt, '.word', '', '', None, struct.unpack('<I', b.read(nxt, 4).ljust(4, b'\0'))[0]
        va = nxt + 4 if nxt < end else end

def _fmt(a, m, ops, note, val, raw):
    if raw is not None: return f'{a:#010x}  .word    {raw:#010x}'
    return f'{a:#010x}  {m:8s} {ops:32s} {note}' + (f' ={val:#x}' if val is not None else '')

def sha256_of(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()

def cache_path(path): return os.path.join(paths.WORK, 'cache', os.path.basename(path) + '.dis')

def write_full(b, path):
    """work/cache/<name>.dis: first line '; sha256 <hex>', then one line per instruction, a '; ===== name' line at each symbol."""
    out = cache_path(path); os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + '.tmp'
    with open(tmp, 'w') as f:
        f.write(f'; sha256 {sha256_of(path)}\n')
        for rec in _scan(b):
            if rec[0] in b.by_addr: f.write(f'; ===== {b.by_addr[rec[0]]} @ {rec[0]:#x}\n')
            f.write(_fmt(*rec) + '\n')
    os.replace(tmp, out); return out

def cached_lines(path):
    """The cache's lines if it exists for this exact ELF (SHA-256 in line 1), else None."""
    out = cache_path(path)
    if os.path.exists(out):
        with open(out) as f:
            if f.readline().strip() == f'; sha256 {sha256_of(path)}': return f.readlines()
    return None

def refs_to(b, path, targets):
    """{target: [(address, mnemonic)]}: every call of / load of each target; from the cache when valid, else one live scan."""
    res = {t: [] for t in targets}
    lines = cached_lines(path)
    if lines is not None:
        toks = {f' ={t:#x}\n': t for t in res}
        for l in lines:
            i = l.rfind(' =')
            if i > 0 and l[i:] in toks: res[toks[l[i:]]].append((int(l[:10], 16), l[12:20].strip()))
    else:
        for a, m, _, _, v, _ in _scan(b):
            if v in res: res[v].append((a, m))
    return res

def kind(m): return 'call' if m in ('jal', 'j', 'bal') else 'jalr' if m == 'jalr' else 'addr'

def find_text(b, text):
    """NUL-terminated strings containing text: {address: string}."""
    t = text.encode(); out = {}; i = b.data.find(t)
    while i >= 0 and len(out) < 50:
        s = b.data.rfind(b'\0', 0, i) + 1; e = b.data.find(b'\0', i)
        for a, sz, o in b.segs:
            if o <= s < o + sz: out[a + s - o] = b.data[s:e].decode('latin-1')
        i = b.data.find(t, e)
    return out

def gp_of(b):
    # _gp symbol if present, else derive from .dynamic DT_PLTGOT + 0x7ff0
    if '_gp' in b.syms: return b.syms['_gp'][0]
    dyn = b.elf.get_section_by_name('.dynamic')
    for t in dyn.iter_tags():
        if t.entry.d_tag == 'DT_PLTGOT': return t.entry.d_val + 0x7ff0
    return 0

if __name__ == '__main__':
    cmd, path = sys.argv[1], sys.argv[2]; b = Bin(path); b.gp = gp_of(b)
    print(f'; gp = {b.gp:#x}, {len(b.syms)} symbols, {len(b.got)} GOT entries')
    if cmd == 'sym':
        for n in sys.argv[3:]:
            if n not in b.syms: print(f'; {n}: not found'); continue
            va, sz = b.syms[n]
            if not sz:  # size unknown: until next symbol
                i = bisect.bisect_right(b.addrs, va); sz = (b.addrs[i] - va) if i < len(b.addrs) else 0x400
            print(f'\n; ===== {n} @ {va:#x} size {sz:#x} =====')
            b.dis(va, sz)
    elif cmd == 'addr':
        va = int(sys.argv[3], 0); sz = int(sys.argv[4], 0) if len(sys.argv) > 4 else 0x200
        b.dis(va, sz)
    elif cmd == 'words':   # raw words, to pin: ADDR [COUNT]
        va = int(sys.argv[3], 0); n = int(sys.argv[4], 0) if len(sys.argv) > 4 else 4
        for i in range(n): print(f'{va + 4 * i:#x}  {struct.unpack("<I", b.read(va + 4 * i, 4))[0]:#010x}')
    elif cmd == 'xref':
        for s in sys.argv[3:]:
            for a in b.find_str(s):
                refs = b.xref(a)
                print(f'"{s}" @ {a:#x}: {len(refs)} refs: ' + ', '.join(f'{r:#x} ({b.name(r)})' for r in refs))
    elif cmd == 'syms':
        import re
        for n, (va, sz) in sorted(b.syms.items(), key=lambda kv: kv[1][0]):
            if re.search(sys.argv[3], n): print(f'{va:#x} {sz:#x} {n}')
    elif cmd == 'full':
        out = cache_path(path)
        if cached_lines(path) is None: write_full(b, path); print('; wrote', out)
        else: print('; up to date', out)
    elif cmd == 'callers':
        t = sys.argv[3]
        try: target = int(t, 0)
        except ValueError:
            if t not in b.syms: sys.exit(f'; {t}: not found')
            target = b.syms[t][0]
        refs = refs_to(b, path, [target])[target]; funcs = {}
        print(f'; {b.name(target)} ({target:#x}): {len(refs)} references')
        for a, m in refs:
            print(f'{a:#x}  {kind(m):5s} {m:6s} {b.name(a)}'); funcs.setdefault(b.name(a).split('+')[0], []).append(a)
        print(f'; {len(funcs)} functions: ' + ', '.join(sorted(funcs)))
    elif cmd == 'strings-xref':
        found = find_text(b, sys.argv[3]); allrefs = refs_to(b, path, found)
        for a, text in found.items():
            refs = allrefs[a]
            print(f'"{text[:70]}" @ {a:#x}: {len(refs)} refs: ' + ', '.join(f'{r:#x} ({b.name(r)})' for r, _ in refs))
    elif cmd == 'strxref':
        a = int(sys.argv[3], 0)
        for r in b.xref(a): print(f'{r:#x} ({b.name(r)})')
