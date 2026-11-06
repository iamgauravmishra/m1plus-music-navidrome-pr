/* Start-up and libc_nonshared replacements for the M1 Plus wpa_supplicant (tools/mod_wpa.py).
 *
 * Debian's crt objects and libc_nonshared.a are legacy-NaN and cannot be linked with NaN2008 code, so this file
 * supplies what they would: the C half of _start (start.S), the init/fini routines glibc runs around main, and
 * the few wrappers that glibc 2.28 only ships in libc_nonshared.a (atexit, stat family). Everything else comes
 * from the stock libc.so.6. */
#define _GNU_SOURCE
#include <stddef.h>
#include <sys/stat.h>

extern int main(int, char **, char **);
extern int __libc_start_main(int (*)(int, char **, char **), int, char **, void (*)(int, char **, char **),
                             void (*)(void), void (*)(void), void *);
extern int __cxa_atexit(void (*)(void *), void *, void *);
extern int __xstat(int, const char *, struct stat *);
extern int __fxstat(int, int, struct stat *);
extern int __lxstat(int, const char *, struct stat *);
extern int __xstat64(int, const char *, struct stat64 *);
extern int __fxstat64(int, int, struct stat64 *);
extern int __lxstat64(int, const char *, struct stat64 *);

void *__dso_handle = 0;

/* the linker defines these for an executable with the matching output sections */
extern void (*__preinit_array_start[])(int, char **, char **);
extern void (*__preinit_array_end[])(int, char **, char **);
extern void (*__init_array_start[])(int, char **, char **);
extern void (*__init_array_end[])(int, char **, char **);
extern void (*__fini_array_start[])(void);
extern void (*__fini_array_end[])(void);

static void m1_init(int argc, char **argv, char **envp) {
    for (size_t i = 0; i < (size_t)(__preinit_array_end - __preinit_array_start); i++)
        __preinit_array_start[i](argc, argv, envp);
    for (size_t i = 0; i < (size_t)(__init_array_end - __init_array_start); i++)
        __init_array_start[i](argc, argv, envp);
}

static void m1_fini(void) {
    for (size_t i = (size_t)(__fini_array_end - __fini_array_start); i > 0; i--)
        __fini_array_start[i - 1]();
}

void m1_start_c(unsigned long *sp, void (*rtld_fini)(void)) {
    __libc_start_main(main, (int)sp[0], (char **)(sp + 1), m1_init, m1_fini, rtld_fini, sp);
    for (;;)
        ;
}

int atexit(void (*f)(void)) { return __cxa_atexit((void (*)(void *))f, NULL, __dso_handle); }

/* _STAT_VER_LINUX on MIPS o32 */
#define M1_STAT_VER 3
int stat(const char *p, struct stat *b) { return __xstat(M1_STAT_VER, p, b); }
int fstat(int fd, struct stat *b) { return __fxstat(M1_STAT_VER, fd, b); }
int lstat(const char *p, struct stat *b) { return __lxstat(M1_STAT_VER, p, b); }
int stat64(const char *p, struct stat64 *b) { return __xstat64(M1_STAT_VER, p, b); }
int fstat64(int fd, struct stat64 *b) { return __fxstat64(M1_STAT_VER, fd, b); }
int lstat64(const char *p, struct stat64 *b) { return __lxstat64(M1_STAT_VER, p, b); }
