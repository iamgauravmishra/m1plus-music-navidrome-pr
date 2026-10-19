#!/usr/bin/env python3
"""Print program headers, section names, and symbol counts of a 32-bit LE ELF (MIPS)."""
import struct, sys
PT = {0:'NULL',1:'LOAD',2:'DYNAMIC',3:'INTERP',4:'NOTE',6:'PHDR',7:'TLS',0x70000000:'MIPS_REGINFO',0x70000003:'MIPS_ABIFLAGS',0x6474e551:'GNU_STACK',0x6474e550:'GNU_EH_FRAME'}
for path in sys.argv[1:]:
    d = open(path,'rb').read()
    assert d[:4]==b'\x7fELF' and d[4]==1 and d[5]==1, 'need ELF32 LE'
    e_type,e_machine,_,e_entry,e_phoff,e_shoff,e_flags,e_ehsize,e_phentsize,e_phnum,e_shentsize,e_shnum,e_shstrndx = struct.unpack('<HHIIIIIHHHHHH', d[16:52])
    print(f"== {path}  size={len(d)} type={e_type} machine={e_machine:#x} entry={e_entry:#x} flags={e_flags:#x} phnum={e_phnum} shnum={e_shnum}")
    maxva = 0
    for i in range(e_phnum):
        p_type,p_off,p_va,p_pa,p_filesz,p_memsz,p_flags,p_align = struct.unpack('<IIIIIIII', d[e_phoff+i*e_phentsize:e_phoff+(i+1)*e_phentsize])
        print(f"  PH[{i}] {PT.get(p_type,hex(p_type)):13s} off={p_off:#09x} va={p_va:#010x} filesz={p_filesz:#09x} memsz={p_memsz:#09x} flags={p_flags} align={p_align:#x}")
        if p_type==1: maxva = max(maxva, p_va+p_memsz)
    print(f"  max LOAD end va = {maxva:#x}")
    shs = [struct.unpack('<IIIIIIIIII', d[e_shoff+i*e_shentsize:e_shoff+(i+1)*e_shentsize]) for i in range(e_shnum)]
    strtab = shs[e_shstrndx]; so = strtab[4]
    def nm(off):
        e = d.index(b'\0', so+off); return d[so+off:e].decode()
    names = []
    for s in shs:
        n = nm(s[0]); names.append(n)
        if n in ('.symtab','.dynsym'):
            cnt = s[5]//16 if s[5] else 0
            print(f"  {n}: {cnt} symbols")
        if n in ('.pdr','.text','.data','.bss','.got'):
            print(f"  {n}: addr={s[3]:#x} off={s[4]:#x} size={s[5]:#x}")
    print("  sections:", ' '.join(names))
