/* M1+ Pod payload layout. Derived from q2-pod patch/link.ld (Copyright (c) 2026 Diamond Bond, MIT).
 * Everything lives in one file-backed PT_LOAD at 0xb00000 (tools/pod.py append_payload): code,
 * read-only data, initialised data and the zero-filled .scratch state. The segment's memory size
 * equals its file size, because .scratch is PROGBITS in the file; tools/pod.py rejects a non-empty
 * .bss (that would need memsz > filesz) and checks .scratch ships zeroed. */
SECTIONS {
  . = 0xb00000;
  .text : { *(.text*) }
  .rodata : { *(.rodata*) }
  .data : { *(.data*) *(.sdata*) }
  /* Writable state (Cover Flow's page and renderer): explicitly sectioned, so the compiler emits
   * it as zero-filled PROGBITS inside the file image rather than .bss. The segment stays
   * file-backed with memsz == filesz, so the loader maps it from demo like the code. */
  .scratch : { *(.scratch*) }
  .bss : { *(.bss*) *(.sbss*) *(COMMON) }
  /DISCARD/ : { *(.comment) *(.note*) *(.pdr) *(.mdebug*) *(.MIPS.abiflags) *(.reginfo) *(.gnu.attributes) }
}
