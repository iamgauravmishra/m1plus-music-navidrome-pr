#!/usr/bin/env python3
"""MIPS32 LE disassembly helper (capstone + pyelftools) for the Shanling 'demo' binary.

  dis.py sym  ELF NAME...          disassemble functions by (dyn)symbol name
  dis.py addr ELF ADDR [LEN]       disassemble a range
  dis.py xref ELF STRING...        find lui/addiu(ori) pairs referencing the address of a NUL-terminated string
  dis.py strxref ELF ADDR          find code referencing an absolute address
Calls (jal / jalr via GOT loads) are annotated with symbol names where possible.
"""
import sys, struct, bisect
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
    elif cmd == 'xref':
        for s in sys.argv[3:]:
            for a in b.find_str(s):
                refs = b.xref(a)
                print(f'"{s}" @ {a:#x}: {len(refs)} refs: ' + ', '.join(f'{r:#x} ({b.name(r)})' for r in refs))
    elif cmd == 'syms':
        import re
        for n, (va, sz) in sorted(b.syms.items(), key=lambda kv: kv[1][0]):
            if re.search(sys.argv[3], n): print(f'{va:#x} {sz:#x} {n}')
    elif cmd == 'strxref':
        a = int(sys.argv[3], 0)
        for r in b.xref(a): print(f'{r:#x} ({b.name(r)})')
