#!/usr/bin/env python3
"""The parametric EQ's player side: hciplayer's equalizer filter replaced by patch/peq_player.c (docs/modules/peq.md).

hciplayer (/usr/bin/hciplayer, the audio daemon: MPlayer 1.3.0 modified) is pinned by SHA-256. Its final program
header is an unused PT_NULL; pod.py's append_payload turns it into a file-backed PT_LOAD (RWX) at PLAYER_BASE holding the
payload (patch/peq.c and patch/peq_player.c, built with PEQ_PLAYER, non-PIC, linked at PLAYER_BASE, no .bss: per-instance
state is heap). Three edits, each pinned with its neighbours and the facts the C code reads:

  * the equalizer's af_info open slot (EQ_OPEN_SLOT, stock af_equalizer open 0x44fd14) becomes peq_open;
  * stock skips the equalizer above 48 kHz in two places (RATE_GATES): the mcl-seteq command (beqz to the
    "===setequalizer off===" log) becomes a nop, and the playback loop's per-stream insert (bnez around the add at
    0x42fbc4) an unconditional branch, so the filter runs at every rate (it passes DSD through itself).

libc is reached only through hciplayer's own PLT GOT slots (no new import): a stub sets $gp and $t8 (the slot, which
the lazy resolver PLT0 expects) and jumps through it, as q2-pod's tools/peq.py does.

Usage: mod_player.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import json, os, pathlib, re, stat, struct, sys
from elftools.elf.elffile import ELFFile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir
import pod

REL = 'usr/bin/hciplayer'
PLAYER_SHA = 'a64503746862af3e69b57f2e06167351b30cda28479348a845be5172e083a8c6'
PLAYER_GP = 0xb16750          # DT_PLTGOT + 0x7ff0
PLAYER_BASE = 0xe10000        # stock's last LOAD ends at 0xe03b38
SOURCES = ['peq.c', 'peq_player.c']
FLAGS = [*pod.FLAGS, '-mnan=2008', '-fno-math-errno', '-DPEQ_PLAYER']   # hciplayer: FP64, NaN2008 (its .MIPS.abiflags, e_flags 0x400)

# The equalizer's af_info: info, name ("equalizer"), author, comment, flags, open.
EQ_INFO = 0x893808
EQ_INFO_WORDS = (0x8937bc, 0x885e2c, 0x89354c, 0x88c3b8, 1, 0x44fd14)
EQ_OPEN_SLOT, STOCK_OPEN = EQ_INFO + 0x14, 0x44fd14
# (address, stock word, patched word)
RATE_GATES = ((0x42ce34, 0x10400098, 0),             # mcl-seteq: beqz $v0, 0x42d098 ("setequalizer off") -> nop
              (0x42fa78, 0x14400052, 0x10000052))    # the insert: bnez $v0, 0x42fbc4 -> b 0x42fbc4
# Checked, not written: (address, stock word, what it proves).
PINS = (
    (0x42ce1c, 0x3c0200b0, 'mcl-seteq gate: lui $v0, 0xb0'),
    (0x42ce20, 0x3403bb81, 'mcl-seteq gate: ori $v1, $zero, 48001'),
    (0x42ce24, 0x8c429e30, 'mcl-seteq gate: lw $v0, -0x61d0($v0): mpctx at 0xaf9e30'),
    (0x42ce28, 0x8c42002c, 'mcl-seteq gate: lw $v0, 0x2c($v0): mpctx->sh_audio'),
    (0x42ce2c, 0x8c42003c, 'mcl-seteq gate: lw $v0, 0x3c($v0): the sample rate'),
    (0x42ce30, 0x0043102a, 'mcl-seteq gate: slt $v0, $v0, $v1'),
    (0x42f43c, 0x1062018a, 'the loop: beq $v1, $v0 (insert pending) to the insert gate'),
    (0x42f440, 0x3403bb81, 'the loop: ori $v1, $zero, 48001'),
    (0x42fa68, 0x8e649e30, 'insert gate: lw $a0, -0x61d0($s3): mpctx'),
    (0x42fa6c, 0x8c82002c, 'insert gate: sh_audio'),
    (0x42fa70, 0x8c42003c, 'insert gate: the sample rate'),
    (0x42fa74, 0x0043102a, 'insert gate: slt'),
    (0x42fbc4, 0x0c10a473, 'the insert: jal 0x4291cc (find or add "equalizer", then GAIN SET channels 0..7)'),
    (0x4291f8, 0x26715e2c, 'add: the name "equalizer" (0x885e2c)'),
    (0x429228, 0x3c1300b1, 'add: lui $s3, 0xb1'),
    (0x42922c, 0x3c124000, 'add: lui $s2, 0x4000'),
    (0x429234, 0x26730df4, 'add: the gains at 0xb10df4'),
    (0x429238, 0x26521d00, 'add: AF_CONTROL_EQUALIZER_GAIN | SET (0x40001d00)'),
    (0x42923c, 0x8e190004, 'add: lw $t9, 4($s0): af->control'),
    (0x429250, 0x0320f809, 'add: jalr $t9'),
    (0x42ca74, 0x24570df4, 'mcl-seteq: the ten gains parsed into 0xb10df4'),
    (0x42ca7c, 0xe4400df4, 'mcl-seteq: swc1 (float gains)'),
    (0x42f78c, 0x8e629e30, 'the audio EOF test: lw $v0, -0x61d0($s3): mpctx'),
    (0x42f790, 0x8c420034, 'the audio EOF test: mpctx->d_audio (+0x34)'),
    (0x42f794, 0x8c42001c, 'the audio EOF test: d_audio->eof (+0x1c), what the carried filter memory reads'),
    (0x47ed5c, 0x8e020004, 'sh_audio->codec (+4)'),
    (0x47ed74, 0x8c4703d0, 'codec->name (+0x3d0)'),
    (0x47ed7c, 0x8c4203e0, 'codec->drv (+0x3e0)'),
    (0x44fd38, 0xac820004, 'stock open: af->control at +4'),
    (0x44fd48, 0xac820008, 'stock open: af->uninit at +8'),
    (0x44fd54, 0xf4800028, 'stock open: af->mul (double) at +0x28'),
    (0x44fd60, 0xae02000c, 'stock open: af->play at +0xc'),
    (0x44fd6c, 0xae020014, 'stock open: af->data at +0x14'),
    (0x44fd7c, 0xae020010, 'stock open: af->setup at +0x10'),
    (0x44fe38, 0x3c021000, 'stock control: lui 0x1000'),
    (0x44fe3c, 0x24420100, 'stock control: AF_CONTROL_REINIT 0x10000100'),
    (0x44fe48, 0x3c022000, 'stock control: lui 0x2000'),
    (0x44fe4c, 0x24420300, 'stock control: AF_CONTROL_COMMAND_LINE 0x20000300'),
    (0x44fddc, 0x3c024000, 'stock control: lui 0x4000'),
    (0x44fdec, 0x24431d00, 'stock control: AF_CONTROL_EQUALIZER_GAIN 0x40001d00'),
)
NAME_AT, NAME = 0x885e2c, b'equalizer\0'
DSD_DRV = (0x89b4f0, b'dsdiff\0')   # the vendor's DSD driver name, as the filter compares it
# libc: name -> (C prototype, the PLT symbol hciplayer imports it as)
LIBC = {
    'memset': ('void *', 'void *, int, unsigned', 'memset'), 'memcpy': ('void *', 'void *, const void *, unsigned', 'memcpy'),
    'memcmp': ('int', 'const void *, const void *, unsigned', 'memcmp'), 'strcmp': ('int', 'const char *, const char *', 'strcmp'),
    'strlen': ('unsigned', 'const char *', 'strlen'), 'calloc': ('void *', 'unsigned, unsigned', 'calloc'),
    'free': ('void', 'void *', 'free'), 'fopen': ('void *', 'const char *, const char *', 'fopen64'),
    'fread': ('unsigned', 'void *, unsigned, unsigned, void *', 'fread'), 'fclose': ('int', 'void *', 'fclose'),
    'clock_gettime': ('int', 'int, void *', 'clock_gettime'),
    'pow': ('double', 'double, double', '__pow_finite'), 'cos': ('double', 'double', 'cos'), 'sin': ('double', 'double', 'sin'),
}


def plt_slots(path):
    """name -> the .got.plt slot of each LIBC import (the MIPS PLT: .rel.plt's R_MIPS_JUMP_SLOT entries)."""
    with open(path, 'rb') as f:
        elf = ELFFile(f)
        rel, syms = elf.get_section_by_name('.rel.plt'), elf.get_section_by_name('.dynsym')
        found = {syms.get_symbol(r['r_info_sym']).name: r['r_offset'] for r in rel.iter_relocations()}
    want = {imp for _, _, imp in LIBC.values()}
    missing = sorted(want - set(found))
    pod.check(not missing, f'hciplayer does not import {missing}')
    return {name: found[imp] for name, (_, _, imp) in LIBC.items()}


def word(b, a): return struct.unpack_from('<I', b, pod.fileoff(b, a))[0]


def check_stock(raw):
    pod.check(pod.sha(raw) == PLAYER_SHA, f'{REL} is not the pinned stock binary')
    got = tuple(word(raw, EQ_INFO + 4 * i) for i in range(6))
    pod.check(got == EQ_INFO_WORDS, f'equalizer af_info at {EQ_INFO:#x}: {[hex(w) for w in got]}')
    for a, old, _ in RATE_GATES:
        pod.check(word(raw, a) == old, f'{a:#x}: rate gate {word(raw, a):#010x} != {old:#010x}')
    for a, old, what in PINS:
        pod.check(word(raw, a) == old, f'{a:#x} ({what}): {word(raw, a):#010x} != pinned {old:#010x}')
    for a, s in ((NAME_AT, NAME), DSD_DRV):
        off = pod.fileoff(raw, a)
        pod.check(raw[off:off + len(s)] == s, f'{a:#x}: not {s!r}')


def compile_payload(build, slots):
    header = ['/* generated by tools/mod_player.py: hciplayer libc through its own PLT slots */', '#pragma once']
    asm = ['.set noreorder', '.text']
    for name, (ret, args, _) in LIBC.items():
        header += [f'extern {ret} peq_lib_{name}({args});', f'#define {name} peq_lib_{name}']
        slot = slots[name]
        asm += [f'.section .text.peq_lib_{name},"ax",@progbits', f'.globl peq_lib_{name}', f'peq_lib_{name}:',
                f'lui $gp, {PLAYER_GP >> 16}', f'ori $gp, $gp, {PLAYER_GP & 0xffff}',
                f'lui $t8, {slot >> 16}', f'ori $t8, $t8, {slot & 0xffff}', 'lw $t9, 0($t8)', 'jr $t9', 'nop']
    asm += ['.globl memcpy', '.set memcpy, peq_lib_memcpy', '.globl memset', '.set memset, peq_lib_memset']   # the compiler's own struct copies
    (build / 'player.h').write_text('\n'.join(header) + '\n')
    (build / 'player_asm.S').write_text('\n'.join(asm) + '\n')
    objs = []
    for src in SOURCES:
        obj = build / (src + '.o')
        pod.run(pod.CLANG, *FLAGS, '-I', build, '-I', pod.PATCH, '-c', os.path.join(pod.PATCH, src), '-o', obj)
        objs.append(obj)
    pod.run(pod.CLANG, *FLAGS, '-c', build / 'player_asm.S', '-o', build / 'player_asm.o')
    script = build / 'player.ld'
    script.write_text(f'SECTIONS {{ . = {PLAYER_BASE:#x}; .text : {{ *(.text*) }} .rodata : {{ *(.rodata*) }} '
                      '.data : { *(.data*) *(.sdata*) } .bss : { *(.bss*) *(.sbss*) *(COMMON) } '
                      '/DISCARD/ : { *(.comment) *(.note*) *(.pdr) *(.mdebug*) *(.MIPS.abiflags) *(.reginfo) *(.gnu.attributes) } }\n')
    pod.run(pod.LD, '-m', 'elf32ltsmip', '--gc-sections', '-T', script, '-e', 'peq_open', *objs, build / 'player_asm.o',
            '-o', build / 'player.elf')
    pod.run(pod.OBJCOPY, '-O', 'binary', build / 'player.elf', build / 'player.bin')
    with open(build / 'player.elf', 'rb') as f:
        elf = ELFFile(f)
        for sec in elf.iter_sections():
            if sec.name in ('.bss', '.sbss') and sec['sh_size']:
                raise ValueError(f'player payload has non-empty {sec.name}: its state is per instance, on the heap')
        syms = {s.name: s['st_value'] for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name}
    return syms, (build / 'player.bin').read_bytes()


def patch(raw, payload, syms):
    image = bytearray(raw)
    entry = syms['peq_open']
    pod.check(PLAYER_BASE <= entry < PLAYER_BASE + len(payload), 'peq_open outside the payload')
    struct.pack_into('<I', image, pod.fileoff(image, EQ_OPEN_SLOT), entry)
    for a, _, new in RATE_GATES: struct.pack_into('<I', image, pod.fileoff(image, a), new)
    seg_off = pod.append_payload(image, payload, PLAYER_BASE)
    return bytes(image), seg_off


def apply(out):
    path = os.path.join(out, 'rootfs', REL)
    raw = open(path, 'rb').read()
    check_stock(raw)
    build = pathlib.Path(out) / 'playerbuild'; build.mkdir(exist_ok=True)
    slots = plt_slots(path)
    syms, payload = compile_payload(build, slots)
    patched, seg_off = patch(raw, payload, syms)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, mode | 0o200); open(path, 'wb').write(patched); os.chmod(path, mode)
    manifest = {'stock_sha256': PLAYER_SHA, 'patched_sha256': pod.sha(patched), 'base': PLAYER_BASE, 'gp': PLAYER_GP,
                'payload_len': len(payload), 'payload_sha256': pod.sha(payload), 'segment_file_off': seg_off,
                'open_slot': {'addr': EQ_OPEN_SLOT, 'stock': STOCK_OPEN, 'target': syms['peq_open']},
                'rate_gates': [[a, old, new] for a, old, new in RATE_GATES], 'libc_slots': slots,
                'symbols': {n: syms[n] for n in sorted(syms) if re.fullmatch(r'peq_\w+', n)}}
    (build / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    print(f'player: payload {len(payload)} bytes @ {PLAYER_BASE:#x}, equalizer open {EQ_OPEN_SLOT:#x} -> '
          f'{syms["peq_open"]:#x}, rate gates {", ".join(hex(a) for a, _, _ in RATE_GATES)}')


if __name__ == '__main__':
    clone_workdir(sys.argv[1], sys.argv[2]); apply(sys.argv[2])
