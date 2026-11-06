# Entry point of the M1 Plus wpa_supplicant (tools/mod_wpa.py).
#
# Debian's crt1.o/crti.o/crtn.o are legacy-NaN objects and lld refuses to link them into a NaN2008 executable
# (the M1 userland is NaN2008), so the program has its own start-up: this stub aligns the stack and calls
# m1_start_c (shim.c), which hands main, init and fini to the stock glibc's __libc_start_main.
# ld.so passes its termination function in $v0.
	.text
	.set	noreorder
	.globl	_start
	.type	_start, @function
_start:
	move	$a1, $v0		# rtld_fini
	move	$a0, $sp		# the initial stack: argc, argv, envp, auxv
	li	$at, -8
	and	$sp, $sp, $at
	addiu	$sp, $sp, -32		# o32 argument area for the C callee
	lui	$t9, %hi(m1_start_c)
	addiu	$t9, $t9, %lo(m1_start_c)
	move	$ra, $zero
	jalr	$t9
	nop
	break	0			# __libc_start_main does not return
	.size	_start, .-_start
