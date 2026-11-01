"""Harness callback isolation: CPU state is restored while callback memory writes survive."""
from unicorn.mips_const import UC_MIPS_REG_HI, UC_MIPS_REG_LO
from harness import *   # noqa: F401,F403


def run(ctx):
    m = Machine(); u = m.u
    fn, outer, out = SCRATCH + 0x80000, SCRATCH + 0x80100, m.alloc(4)
    # lw v0,16(sp); addu v0,v0,a0; sw v0,0(a1); mthi v0; mtlo v0; jr ra; nop
    u.mem_write(fn, struct.pack('<7I', 0x8fa20010, 0x00441021, 0xaca20000, 0x00400011, 0x00400013, 0x03e00008, 0))
    # addiu v0,a0,1; jr ra; nop
    u.mem_write(outer, struct.pack('<3I', 0x24820001, 0x03e00008, 0))
    regs = [UC_MIPS_REG_0 + i for i in range(32)] + [UC_MIPS_REG_PC, UC_MIPS_REG_HI, UC_MIPS_REG_LO, UC_MIPS_REG_F0]
    for i, reg in enumerate(regs): u.reg_write(reg, 0x1000 + i)
    u.reg_write(UC_MIPS_REG_SP, STACK); u.reg_write(UC_MIPS_REG_PC, RET)
    state = lambda: [u.reg_read(r) for r in regs]
    before = state()
    for a, b in ((5, 9), (11, 17)):
        r = m.nested(fn, a, out, 0, 0, b)
        ctx.expect(r == a + b and m.word(out) == a + b, 'callback returns its result, receives stack arguments and keeps memory writes')
        ctx.expect(state() == before, 'callback restores every GPR, PC, HI/LO and floating-point register, including on reuse')
    ctx.expect(len(m._nested_contexts) == 1, 'sequential callbacks reuse one CPU snapshot')

    def reenter(uc, address, size, data):
        active = state()
        uc.reg_write(UC_MIPS_REG_F0, 0xdeadbeef)
        ctx.expect(m.nested(fn, 7, out, 0, 0, 19) == 26, 'a callback can invoke another callback')
        ctx.expect(state()[:-1] == active[:-1] and u.reg_read(UC_MIPS_REG_F0) == 0xdeadbeef,
                   'inner callback restores its immediate caller')

    hook = u.hook_add(UC_HOOK_CODE, reenter, begin=outer, end=outer)
    ctx.expect(m.nested(outer, 41) == 42 and m.word(out) == 26, 'outer callback resumes after the inner callback')
    ctx.expect(state() == before and len(m._nested_contexts) == 2, 'reentrant callbacks restore outer CPU state with distinct snapshots')
    u.hook_del(hook)

    def broken(uc, address, size, data): raise RuntimeError('mock callback failed')
    hook = u.hook_add(UC_HOOK_CODE, broken, begin=outer, end=outer)
    try:
        m.nested(outer)
        failed = False
    except RuntimeError: failed = True
    finally: u.hook_del(hook)
    ctx.expect(failed and state() == before, 'callback errors propagate after restoring caller CPU state')
    ctx.expect(m.nested(outer, 9) == 10 and state() == before, 'snapshots remain reusable after a callback error')
