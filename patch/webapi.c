/* webapi.c: the CGI behind Wi-Fi Transfer's page (docs/modules/wifi-transfer.md).
 *
 * One program, /usr/share/web/cgi-bin/api.cgi, run by the stock thttpd. It lists, downloads (a file, or a
 * selection as a tar stream), creates folders, renames, moves, deletes and uploads inside WEBAPI_ROOT (the card,
 * /mnt/mmc). No shell, no system(), no libc: on the player it is a static MIPS executable over raw Linux system
 * calls (tools/mod_webapp.py builds it); with -DWEBAPI_HOST the same code runs on the build machine over libc
 * (test/webapi.py), WEBAPI_ROOT then pointing at a temporary directory.
 *
 * Every request path is checked component by component below the root: no "." or "..", no name starting with
 * a dot (hidden: macOS ._ files, the player's own .m1plus data), no symbolic link, nothing outside the root.
 */
typedef unsigned char u8;
typedef unsigned short u16;
typedef unsigned int u32;
typedef unsigned long long u64;
typedef long long i64;

#ifndef WEBAPI_ROOT
#define WEBAPI_ROOT "/mnt/mmc"
#endif

#define PMAX 4096 /* longest path handled */
#define NAMEMAX 240 /* longest name the API creates (the card allows 255; ".name.part" and "name 99.ext" fit) */
#define DEPTH 40 /* deepest folder nesting walked */
#define MAXP 4096 /* request parameters */
#define PSTORE 262144 /* card paths of one request's items */
#define BODYMAX 262144 /* form body of the non-upload POSTs */
#define COUNTCAP 9999 /* a folder's "items" stops counting here */
#define COUNTDIRS 3000 /* folders counted per listing */

/* ---- portable OS layer: every function returns >= 0, or -ER_x ---- */

enum {
    ER_NOENT = 1,
    ER_EXIST,
    ER_NOTDIR,
    ER_ISDIR,
    ER_XDEV,
    ER_NOTEMPTY,
    ER_NOSPC,
    ER_ACCES,
    ER_NAME,
    ER_INTR,
    ER_AGAIN,
    ER_RO,
    ER_IO
};
enum { T_NONE, T_FILE, T_DIR, T_LINK, T_OTHER };

struct fst {
    int type;
    u64 size;
    i64 mtime;
};

typedef struct {
    int fd, pos, len;
    void *h;
    u8 buf[2048];
} Dir;

#ifdef WEBAPI_HOST
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <unistd.h>

extern char **environ;

static int mkerr(int e) {
    switch (e) {
    case ENOENT:
        return -ER_NOENT;
    case EEXIST:
        return -ER_EXIST;
    case ENOTDIR:
        return -ER_NOTDIR;
    case EISDIR:
        return -ER_ISDIR;
    case EXDEV:
        return -ER_XDEV;
    case ENOTEMPTY:
        return -ER_NOTEMPTY;
    case ENOSPC:
    case EDQUOT:
        return -ER_NOSPC;
    case EACCES:
    case EPERM:
        return -ER_ACCES;
    case EINVAL:
    case ENAMETOOLONG:
    case EILSEQ:
        return -ER_NAME;
    case EINTR:
        return -ER_INTR;
    case EAGAIN:
        return -ER_AGAIN;
    case EROFS:
        return -ER_RO;
    }
    return -ER_IO;
}
#define RET(x) ((x) < 0 ? mkerr(errno) : (x))

__attribute__((noreturn)) static void os_exit(int c) { _exit(c); }
static int os_lstat(const char *p, struct fst *s) {
    struct stat t;
    if (lstat(p, &t) < 0) return mkerr(errno);
    s->type = S_ISREG(t.st_mode) ? T_FILE : S_ISDIR(t.st_mode) ? T_DIR : S_ISLNK(t.st_mode) ? T_LINK : T_OTHER;
    s->size = (u64)t.st_size;
    s->mtime = (i64)t.st_mtime;
    return 0;
}
static int os_open_rd(const char *p) {
    int r = open(p, O_RDONLY | O_NOFOLLOW);
    return RET(r);
}
/* mode 0: create or truncate; 1: append to an existing file */
static int os_open_wr(const char *p, int mode) {
    int r = open(p, mode ? (O_WRONLY | O_APPEND | O_NOFOLLOW) : (O_WRONLY | O_CREAT | O_TRUNC | O_NOFOLLOW), 0644);
    return RET(r);
}
static long os_read(int fd, void *b, long n) {
    long r = read(fd, b, (size_t)n);
    return RET(r);
}
static long os_write(int fd, const void *b, long n) {
    long r = write(fd, b, (size_t)n);
    return RET(r);
}
static int os_close(int fd) { return close(fd); }
static int os_fsync(int fd) {
    int r = fsync(fd);
    return RET(r);
}
static int os_mkdir(const char *p) {
    int r = mkdir(p, 0755);
    return RET(r);
}
static int os_rename(const char *a, const char *b) {
    int r = rename(a, b);
    return RET(r);
}
static int os_unlink(const char *p) {
    int r = unlink(p);
    return RET(r);
}
static int os_rmdir(const char *p) {
    int r = rmdir(p);
    return RET(r);
}
static int os_statfs(const char *p, u64 *total, u64 *avail) {
    struct statvfs v;
    if (statvfs(p, &v) < 0) return mkerr(errno);
    *total = (u64)v.f_blocks * v.f_frsize;
    *avail = (u64)v.f_bavail * v.f_frsize;
    return 0;
}
static int dir_open(Dir *d, const char *p) {
    d->h = opendir(p);
    return d->h ? 0 : mkerr(errno);
}
static const char *dir_next(Dir *d) {
    struct dirent *e;
    while ((e = readdir((DIR *)d->h))) {
        if (e->d_name[0] == '.' && (!e->d_name[1] || (e->d_name[1] == '.' && !e->d_name[2]))) continue;
        return e->d_name;
    }
    return 0;
}
static void dir_close(Dir *d) { closedir((DIR *)d->h); }
#else /* the player: Linux MIPS o32, raw system calls */

__asm__(".text\n.globl rawsys\n.type rawsys,@function\nrawsys:\n.set push\n.set noreorder\n"
        "move $2,$4\nmove $4,$5\nmove $5,$6\nmove $6,$7\nlw $7,16($29)\nlw $8,20($29)\n"
        "addiu $29,$29,-32\nsw $8,16($29)\nsyscall\naddiu $29,$29,32\nbeqz $7,1f\nnop\nsubu $2,$0,$2\n"
        "1: jr $31\nnop\n.set pop\n.size rawsys,.-rawsys\n"
        ".globl __start\n.type __start,@function\n__start:\n.set push\n.set noreorder\n"
        "move $4,$29\naddiu $29,$29,-32\njal webapi_start\nnop\nbreak\n.set pop\n");
extern long rawsys(long nr, long a, long b, long c, long d, long e);

void *memcpy(void *d, const void *s, unsigned long n) {
    u8 *x = d;
    const u8 *y = s;
    while (n--) *x++ = *y++;
    return d;
}
void *memmove(void *d, const void *s, unsigned long n) {
    u8 *x = d;
    const u8 *y = s;
    if (x < y)
        while (n--) *x++ = *y++;
    else {
        x += n;
        y += n;
        while (n--) *--x = *--y;
    }
    return d;
}
void *memset(void *d, int c, unsigned long n) {
    u8 *x = d;
    while (n--) *x++ = (u8)c;
    return d;
}
int memcmp(const void *a, const void *b, unsigned long n) {
    const u8 *x = a, *y = b;
    for (; n; n--, x++, y++)
        if (*x != *y) return *x - *y;
    return 0;
}
unsigned long strlen(const char *s) {
    const char *p = s;
    while (*p) p++;
    return (unsigned long)(p - s);
}
int strcmp(const char *a, const char *b) {
    while (*a && *a == *b) a++, b++;
    return (u8)*a - (u8)*b;
}

/* o32 errno values (MIPS numbers them differently from other architectures) */
static int mkerr(long e) {
    switch (e) {
    case 2:
        return -ER_NOENT;
    case 17:
        return -ER_EXIST;
    case 20:
        return -ER_NOTDIR;
    case 21:
        return -ER_ISDIR;
    case 18:
        return -ER_XDEV;
    case 93:
        return -ER_NOTEMPTY;
    case 28:
    case 1133:
        return -ER_NOSPC;
    case 13:
    case 1:
        return -ER_ACCES;
    case 22:
    case 78:
        return -ER_NAME;
    case 4:
        return -ER_INTR;
    case 11:
        return -ER_AGAIN;
    case 30:
        return -ER_RO;
    }
    return -ER_IO;
}
#define RET(r) ((r) < 0 ? mkerr(-(r)) : (r))

#define SYS_read 4003
#define SYS_write 4004
#define SYS_open 4005
#define SYS_close 4006
#define SYS_unlink 4010
#define SYS_rename 4038
#define SYS_mkdir 4039
#define SYS_rmdir 4040
#define SYS_statfs 4099
#define SYS_fsync 4118
#define SYS_getdents64 4219
#define SYS_exit_group 4246
#define SYS_statx 4366
#define O_WRONLY 1
#define O_APPEND 8
#define O_CREAT 0x100
#define O_TRUNC 0x200
#define O_LARGEFILE 0x2000
#define O_DIRECTORY 0x10000
#define O_NOFOLLOW 0x20000

struct statx_ts {
    i64 sec;
    u32 nsec;
    int pad;
};
struct statx_k { /* include/uapi/linux/stat.h; the same on every architecture */
    u32 mask, blksize;
    u64 attributes;
    u32 nlink, uid, gid;
    u16 mode, pad1;
    u64 ino, size, blocks, attributes_mask;
    struct statx_ts atime, btime, ctime, mtime;
    u32 rdev_major, rdev_minor, dev_major, dev_minor;
    u64 spare[14];
};
_Static_assert(sizeof(struct statx_k) == 256, "statx layout");

__attribute__((noreturn)) static void os_exit(int c) {
    rawsys(SYS_exit_group, c, 0, 0, 0, 0);
    for (;;) {
    }
}
static int os_lstat(const char *p, struct fst *s) {
    struct statx_k x;
    long r =
        rawsys(SYS_statx, -100, (long)p, 0x100 | 0x800, 0x241, (long)&x); /* AT_FDCWD, no follow, TYPE|SIZE|MTIME */
    if (r < 0) return mkerr(-r);
    u32 t = x.mode & 0170000;
    s->type = t == 0100000 ? T_FILE : t == 0040000 ? T_DIR : t == 0120000 ? T_LINK : T_OTHER;
    s->size = x.size;
    s->mtime = x.mtime.sec;
    return 0;
}
static int os_open_rd(const char *p) {
    long r = rawsys(SYS_open, (long)p, O_LARGEFILE | O_NOFOLLOW, 0, 0, 0);
    return RET(r);
}
static int os_open_wr(const char *p, int mode) {
    long r = rawsys(SYS_open, (long)p, O_LARGEFILE | O_NOFOLLOW | O_WRONLY | (mode ? O_APPEND : (O_CREAT | O_TRUNC)),
                    0644, 0, 0);
    return RET(r);
}
static long os_read(int fd, void *b, long n) {
    long r = rawsys(SYS_read, fd, (long)b, n, 0, 0);
    return RET(r);
}
static long os_write(int fd, const void *b, long n) {
    long r = rawsys(SYS_write, fd, (long)b, n, 0, 0);
    return RET(r);
}
static int os_close(int fd) { return (int)rawsys(SYS_close, fd, 0, 0, 0, 0); }
static int os_fsync(int fd) {
    long r = rawsys(SYS_fsync, fd, 0, 0, 0, 0);
    return RET(r);
}
static int os_mkdir(const char *p) {
    long r = rawsys(SYS_mkdir, (long)p, 0755, 0, 0, 0);
    return RET(r);
}
static int os_rename(const char *a, const char *b) {
    long r = rawsys(SYS_rename, (long)a, (long)b, 0, 0, 0);
    return RET(r);
}
static int os_unlink(const char *p) {
    long r = rawsys(SYS_unlink, (long)p, 0, 0, 0, 0);
    return RET(r);
}
static int os_rmdir(const char *p) {
    long r = rawsys(SYS_rmdir, (long)p, 0, 0, 0, 0);
    return RET(r);
}
/* statfs(2) with o32's struct statfs: f_type, f_bsize, f_frsize, f_blocks, f_bfree, f_files, f_ffree, f_bavail (32 bits each) */
static int os_statfs(const char *p, u64 *total, u64 *avail) {
    u32 v[40];
    long r = rawsys(SYS_statfs, (long)p, (long)v, 0, 0, 0);
    if (r < 0) return mkerr(-r);
    u64 bs = v[2] ? v[2] : v[1];
    if (bs < 512 || bs > (1u << 24) || v[4] > v[3] || v[7] > v[3])
        return -ER_IO; /* a layout that is not the one assumed */
    *total = (u64)v[3] * bs;
    *avail = (u64)v[7] * bs;
    return 0;
}
static int dir_open(Dir *d, const char *p) {
    long r = rawsys(SYS_open, (long)p, O_LARGEFILE | O_DIRECTORY | O_NOFOLLOW, 0, 0, 0);
    if (r < 0) return mkerr(-r);
    d->fd = (int)r;
    d->pos = d->len = 0;
    return 0;
}
static const char *dir_next(Dir *d) {
    for (;;) {
        if (d->pos >= d->len) {
            long n = rawsys(SYS_getdents64, d->fd, (long)d->buf, sizeof d->buf, 0, 0);
            if (n <= 0) return 0;
            d->len = (int)n;
            d->pos = 0;
        }
        u8 *e = d->buf + d->pos; /* struct linux_dirent64: ino 8, off 8, reclen 2, type 1, name */
        d->pos += e[16] | (e[17] << 8);
        const char *nm = (const char *)e + 19;
        if (nm[0] == '.' && (!nm[1] || (nm[1] == '.' && !nm[2]))) continue;
        return nm;
    }
}
static void dir_close(Dir *d) { os_close(d->fd); }
#endif

/* ---- output ---- */

static u8 ob[16384];
static int on;

static void flush(void) {
    int o = 0;
    while (o < on) {
        long r = os_write(1, ob + o, on - o);
        if (r == -ER_INTR || r == -ER_AGAIN) continue;
        if (r <= 0) os_exit(1);
        o += (int)r;
    }
    on = 0;
}
static void put(const void *p, long n) {
    const u8 *s = p;
    while (n > 0) {
        long c = (long)sizeof ob - on;
        if (c > n) c = n;
        memcpy(ob + on, s, (unsigned long)c);
        on += (int)c;
        s += c;
        n -= c;
        if (on == (int)sizeof ob) flush();
    }
}
static void puts_(const char *s) { put(s, (long)strlen(s)); }
static void putc_(char c) { put(&c, 1); }

static u64 div10(u64 v, u32 *r) {
    if (!(v >> 32)) {
        u32 x = (u32)v;
        *r = x % 10;
        return x / 10;
    }
    u64 q = 0;
    u32 rem = 0;
    for (int i = 63; i >= 0; i--) {
        rem = (rem << 1) | (u32)((v >> i) & 1);
        if (rem >= 10) {
            rem -= 10;
            q |= 1ULL << i;
        }
    }
    *r = rem;
    return q;
}
static void putu(u64 v) {
    char t[24];
    int i = 24;
    do {
        u32 d;
        v = div10(v, &d);
        t[--i] = (char)('0' + d);
    } while (v);
    put(t + i, 24 - i);
}
static void puti(i64 v) {
    if (v < 0) {
        putc_('-');
        v = -v;
    }
    putu((u64)v);
}

/* A JSON string body: quotes, backslash and control characters escaped, valid UTF-8 as it is, anything else U+FFFD. */
static void putjson(const char *s, long n) {
    static const char hex[] = "0123456789abcdef";
    const u8 *p = (const u8 *)s;
    putc_('"');
    for (long i = 0; i < n;) {
        u8 c = p[i];
        if (c == '"' || c == '\\') {
            putc_('\\');
            putc_((char)c);
            i++;
        } else if (c == '\n') {
            puts_("\\n");
            i++;
        } else if (c == '\r') {
            puts_("\\r");
            i++;
        } else if (c == '\t') {
            puts_("\\t");
            i++;
        } else if (c < 0x20 || c == 0x7f) {
            puts_("\\u00");
            putc_(hex[c >> 4]);
            putc_(hex[c & 15]);
            i++;
        } else if (c < 0x80) {
            putc_((char)c);
            i++;
        } else {
            int len = c >= 0xf0 ? 4 : c >= 0xe0 ? 3 : c >= 0xc2 ? 2 : 0, ok = len && c <= 0xf4 && i + len <= n;
            u32 cp = len == 2 ? c & 0x1f : len == 3 ? c & 0x0f : c & 0x07;
            for (int k = 1; ok && k < len; k++) {
                if ((p[i + k] & 0xc0) != 0x80) ok = 0;
                cp = (cp << 6) | (p[i + k] & 0x3f);
            }
            if (ok && ((len == 3 && (cp < 0x800 || (cp >= 0xd800 && cp <= 0xdfff))) ||
                       (len == 4 && (cp < 0x10000 || cp > 0x10ffff))))
                ok = 0;
            if (ok) {
                put(p + i, len);
                i += len;
            } else {
                puts_("\\ufffd");
                i++;
            }
        }
    }
    putc_('"');
}
static void putjs(const char *s) { putjson(s, (long)strlen(s)); }

static const char *status_text(int s) {
    switch (s) {
    case 200:
        return "OK";
    case 400:
        return "Bad Request";
    case 403:
        return "Forbidden";
    case 404:
        return "Not Found";
    case 405:
        return "Method Not Allowed";
    case 409:
        return "Conflict";
    case 507:
        return "Insufficient Storage";
    }
    return "Internal Server Error";
}
static void head(int status, const char *type) {
    if (status != 200) {
        puts_("Status: ");
        putu((u64)status);
        putc_(' ');
        puts_(status_text(status));
        puts_("\r\n");
    }
    puts_("Content-Type: ");
    puts_(type);
    puts_("\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n");
}
static void json_head(void) {
    head(200, "application/json; charset=utf-8");
    puts_("\r\n");
}
static u64 pending_body; /* an upload's unread bytes: a refusal swallows the first few MiB so the client sees it */
static void drain(u64 n);
__attribute__((noreturn)) static void die(int status, const char *msg) {
    if (pending_body) drain(pending_body);
    pending_body = 0;
    head(status, "application/json; charset=utf-8");
    if (status == 405) puts_("Allow: GET, POST\r\n");
    puts_("\r\n{\"error\":");
    putjs(msg);
    puts_("}\n");
    flush();
    os_exit(0);
}

/* ---- request ---- */

static char **envp;
static const char *getenv_(const char *k) {
    long n = (long)strlen(k);
    for (char **e = envp; e && *e; e++)
        if (!memcmp(*e, k, (unsigned long)n) && (*e)[n] == '=') return *e + n + 1;
    return 0;
}

static char qbuf[16384], body[BODYMAX + 1];
static char *pk[MAXP];
static const char *pv[MAXP];
static int np;

static void pdecode(char *s) {
    char *o = s;
    for (; *s; s++) {
        if (*s == '+')
            *o++ = ' ';
        else if (*s == '%') {
            int v = 0;
            for (int k = 1; k <= 2; k++) {
                char c = s[k];
                int d = c >= '0' && c <= '9'   ? c - '0'
                        : c >= 'a' && c <= 'f' ? c - 'a' + 10
                        : c >= 'A' && c <= 'F' ? c - 'A' + 10
                                               : -1;
                if (d < 0) die(400, "bad percent-encoding");
                v = v * 16 + d;
            }
            if (!v) die(400, "bad percent-encoding");
            *o++ = (char)v;
            s += 2;
        } else
            *o++ = *s;
    }
    *o = 0;
}
static void parse(char *s) {
    while (*s) {
        char *e = s;
        while (*e && *e != '&') e++;
        char *next = *e ? e + 1 : e;
        *e = 0;
        char *eq = s;
        while (eq < e && *eq != '=') eq++;
        char *v = e; /* no '=': the empty value is the terminating NUL inside the writable buffer */
        if (eq < e) {
            *eq = 0;
            v = eq + 1;
        }
        if (np == MAXP) die(400, "too many parameters");
        pdecode(s);
        pdecode(v);
        if (*s) {
            pk[np] = s;
            pv[np] = v;
            np++;
        }
        s = next;
    }
}
static const char *param(const char *k) {
    for (int i = 0; i < np; i++)
        if (!strcmp(pk[i], k)) return pv[i];
    return 0;
}

static u64 parse_u64(const char *s, int *ok) {
    u64 v = 0;
    *ok = *s != 0;
    for (; *s; s++) {
        if (*s < '0' || *s > '9' || v > 1844674407370955160ULL / 2) {
            *ok = 0;
            return 0;
        }
        v = v * 10 + (u64)(*s - '0');
    }
    return v;
}
static int ieq(const char *a, const char *b) {
    for (; *a && *b; a++, b++) {
        char x = *a >= 'A' && *a <= 'Z' ? *a + 32 : *a, y = *b >= 'A' && *b <= 'Z' ? *b + 32 : *b;
        if (x != y) return 0;
    }
    return *a == *b;
}
static int starts_ieq(const char *s, const char *prefix) {
    for (; *prefix; s++, prefix++) {
        char x = *s >= 'A' && *s <= 'Z' ? *s + 32 : *s;
        if (x != *prefix) return 0;
    }
    return 1;
}

static u64 content_length(void) {
    const char *c = getenv_("CONTENT_LENGTH");
    int ok;
    u64 v = c ? parse_u64(c, &ok) : 0;
    if (c && *c && !ok) die(400, "bad Content-Length");
    return v;
}

/* Read the request body into buf (n bytes, which must be there). */
static void read_exact(char *buf, u64 n) {
    u64 got = 0;
    while (got < n) {
        long r = os_read(0, buf + got, (long)(n - got));
        if (r == -ER_INTR || r == -ER_AGAIN) continue;
        if (r <= 0) die(400, "short request body");
        got += (u64)r;
    }
}

/* Swallow up to 4 MiB of the body so a refusal reaches a client that is still sending a small file. */
static void drain(u64 n) {
    static char junk[16384];
    if (n > 4u << 20) n = 4u << 20;
    while (n) {
        long r = os_read(0, junk, n > sizeof junk ? (long)sizeof junk : (long)n);
        if (r == -ER_INTR || r == -ER_AGAIN) continue;
        if (r <= 0) return;
        n -= (u64)r;
    }
}

/* ---- paths ---- */

static int rootlen;

static int pjoin(char *dst, int n, const char *name) {
    int l = (int)strlen(name);
    if (n + 1 + l >= PMAX) return -1;
    dst[n] = '/';
    memcpy(dst + n + 1, name, (unsigned long)l + 1);
    return n + 1 + l;
}

/* The card path of a request path, checked component by component; dies with 400, 403 or 404. A missing last
   component is allowed when allow_missing (st->type is then T_NONE). Returns the length of out. */
static int resolve(const char *v, char *out, int allow_missing, struct fst *st) {
    int n = rootlen;
    memcpy(out, WEBAPI_ROOT, (unsigned long)n + 1);
    st->type = T_DIR;
    st->size = 0;
    st->mtime = 0;
    const char *p = v ? v : "";
    while (*p) {
        while (*p == '/') p++;
        if (!*p) break;
        const char *c = p;
        while (*p && *p != '/') p++;
        long cl = p - c;
        if ((cl == 1 && c[0] == '.') || (cl == 2 && c[0] == '.' && c[1] == '.')) die(400, "bad path");
        if (c[0] == '.') die(403, "hidden name");
        if (cl > 255) die(400, "name too long");
        if (st->type != T_DIR) die(404, "not found");
        if (n + 1 + cl >= PMAX) die(400, "path too long");
        out[n++] = '/';
        memcpy(out + n, c, (unsigned long)cl);
        n += (int)cl;
        out[n] = 0;
        int r = os_lstat(out, st);
        if (r == -ER_NOENT || r == -ER_NOTDIR) {
            const char *q = p;
            while (*q == '/') q++;
            if (*q || !allow_missing) die(404, "not found");
            st->type = T_NONE;
            return n;
        }
        if (r < 0) die(500, "cannot read the card");
        if (st->type == T_LINK) die(403, "symbolic link");
    }
    return n;
}
static int resolve_dir(const char *v, char *out) {
    struct fst st;
    int n = resolve(v, out, 0, &st);
    if (st.type != T_DIR) die(400, "not a folder");
    return n;
}

/* A name the API creates: one component, no control characters, not hidden, not too long. */
static void check_name(const char *s) {
    long n = (long)strlen(s);
    if (!n || (n == 1 && s[0] == '.') || (n == 2 && s[0] == '.' && s[1] == '.')) die(400, "bad name");
    if (s[0] == '.') die(400, "a name cannot start with a dot");
    if (n > NAMEMAX) die(400, "name too long");
    for (long i = 0; i < n; i++)
        if (s[i] == '/' || (u8)s[i] < 0x20 || s[i] == 0x7f) die(400, "bad name");
}
/* A name for the card itself (exFAT): none of  " * : < > ? \ |, no trailing dot or space. Checked before any body is read. */
static void check_card_name(const char *s) {
    check_name(s);
    long n = (long)strlen(s);
    for (long i = 0; i < n; i++)
        for (const char *b = "\"*:<>?\\|"; *b; b++)
            if (s[i] == *b)
                die(400, "a name cannot contain double quotes, asterisks, colons, angle brackets, question marks, "
                         "backslashes or bars");
    if (s[n - 1] == '.' || s[n - 1] == ' ') die(400, "a name cannot end with a dot or a space");
}
static const char *base_name(const char *abs) {
    const char *b = abs;
    for (const char *p = abs; *p; p++)
        if (*p == '/') b = p + 1;
    return b;
}
static void put_vpath(const char *abs) { putjs(abs[rootlen] ? abs + rootlen : "/"); }

/* "name 2.ext", "name 3.ext", ... : the first one that does not exist in dir (a card path of length dl). */
static void keep_name(char *dir, int dl, const char *name, char *out) {
    long n = (long)strlen(name), dot = -1;
    for (long i = 1; i < n; i++)
        if (name[i] == '.') dot = i;
    long bl = dot < 0 ? n : dot;
    for (int i = 2; i < 10000; i++) {
        char num[8], rev[8];
        int k = 0, t = 0;
        for (int x = i; x; x /= 10) rev[t++] = (char)('0' + x % 10);
        while (t) num[k++] = rev[--t];
        long l = bl + 1 + k + (n - bl);
        if (l > 255) die(400, "name too long");
        memcpy(out, name, (unsigned long)bl);
        out[bl] = ' ';
        memcpy(out + bl + 1, num, (unsigned long)k);
        memcpy(out + bl + 1 + k, name + bl, (unsigned long)(n - bl) + 1);
        int pl = pjoin(dir, dl, out);
        struct fst st;
        int r = pl < 0 ? -ER_NAME : os_lstat(dir, &st);
        dir[dl] = 0;
        if (pl < 0) die(400, "path too long");
        if (r == -ER_NOENT) return;
    }
    die(409, "no free name");
}

static void fail_errno(int e, const char *what) {
    switch (-e) {
    case ER_EXIST:
        die(409, "already exists");
    case ER_NOSPC:
        die(507, "the card is full");
    case ER_NAME:
        die(400, "the card does not accept this name");
    case ER_ACCES:
    case ER_RO:
        die(403, "not allowed");
    case ER_NOENT:
    case ER_NOTDIR:
        die(404, "not found");
    case ER_XDEV:
        die(500, "cannot move across file systems");
    }
    die(500, what);
}

/* ---- list, df ---- */

static int countdirs;
static int count_items(const char *path) {
    Dir d;
    int n = 0;
    if (dir_open(&d, path) < 0) return -1;
    const char *nm;
    while ((nm = dir_next(&d)) && n < COUNTCAP)
        if (nm[0] != '.') n++;
    dir_close(&d);
    return n;
}

static void op_list(void) {
    static char dp[PMAX], ep[PMAX];
    int dl = resolve_dir(param("path"), dp);
    Dir d;
    int r = dir_open(&d, dp);
    if (r < 0) fail_errno(r, "cannot read the folder");
    json_head();
    puts_("{\"path\":");
    put_vpath(dp);
    puts_(",\"entries\":[");
    int first = 1;
    const char *nm;
    memcpy(ep, dp, (unsigned long)dl + 1);
    while ((nm = dir_next(&d))) {
        if (nm[0] == '.') continue;
        int el = pjoin(ep, dl, nm);
        struct fst st;
        int bad = el < 0 || os_lstat(ep, &st) < 0 || (st.type != T_FILE && st.type != T_DIR);
        if (!bad) {
            if (!first) putc_(',');
            first = 0;
            puts_("{\"name\":");
            putjs(nm);
            puts_(st.type == T_DIR ? ",\"dir\":true,\"size\":0,\"mtime\":" : ",\"dir\":false,\"size\":");
            if (st.type == T_FILE) {
                putu(st.size);
                puts_(",\"mtime\":");
            }
            puti(st.mtime);
            if (st.type == T_DIR && countdirs < COUNTDIRS) {
                countdirs++;
                int c = count_items(ep);
                if (c >= 0) {
                    puts_(",\"items\":");
                    puti(c);
                }
            }
            putc_('}');
        }
        ep[dl] = 0;
    }
    dir_close(&d);
    puts_("]}\n");
}

static void op_df(void) {
    u64 total, avail;
    int r = os_statfs(WEBAPI_ROOT, &total, &avail);
    if (r < 0) die(500, "cannot read the card's size");
    json_head();
    puts_("{\"total\":");
    putu(total);
    puts_(",\"free\":");
    putu(avail);
    puts_("}\n");
}

/* ---- download, tar ---- */

static u8 iobuf[65536];

/* Content-Disposition: attachment, an ASCII fallback and the UTF-8 name of RFC 5987/6266. */
static void put_disposition(const char *name) {
    static const char hex[] = "0123456789ABCDEF";
    puts_("Content-Disposition: attachment; filename=\"");
    for (const u8 *p = (const u8 *)name; *p; p++)
        putc_(*p < 0x20 || *p >= 0x7f || *p == '"' || *p == '\\' || *p == '%' ? '_' : (char)*p);
    puts_("\"; filename*=UTF-8''");
    for (const u8 *p = (const u8 *)name; *p; p++) {
        int plain = (*p >= '0' && *p <= '9') || (*p >= 'a' && *p <= 'z') || (*p >= 'A' && *p <= 'Z');
        for (const char *s = "!#$&+-.^_`|~"; *s && !plain; s++) plain = *s == (char)*p;
        if (plain)
            putc_((char)*p);
        else {
            putc_('%');
            putc_(hex[*p >> 4]);
            putc_(hex[*p & 15]);
        }
    }
    puts_("\r\n");
}

static void op_download(void) {
    static char fp[PMAX];
    struct fst st;
    resolve(param("path"), fp, 0, &st);
    if (st.type != T_FILE) die(st.type == T_DIR ? 400 : 404, st.type == T_DIR ? "a folder, use tar" : "not found");
    int fd = os_open_rd(fp);
    if (fd < 0) fail_errno(fd, "cannot open the file");
    head(200, "application/octet-stream");
    puts_("Content-Length: ");
    putu(st.size);
    puts_("\r\n");
    put_disposition(base_name(fp));
    puts_("\r\n");
    u64 left = st.size;
    while (left) {
        long r = os_read(fd, iobuf, left > sizeof iobuf ? (long)sizeof iobuf : (long)left);
        if (r == -ER_INTR || r == -ER_AGAIN) continue;
        if (r <= 0) break; /* the file shrank: the client sees a short body */
        put(iobuf, r);
        left -= (u64)r;
    }
    flush();
    os_close(fd);
}

static const u8 zeros[512];
static void octal(u8 *dst, int width, u64 v) { /* width - 1 digits and a NUL */
    for (int i = width - 2; i >= 0; i--) {
        dst[i] = (u8)('0' + (v & 7));
        v >>= 3;
    }
    dst[width - 1] = 0;
}
static void tar_block(const char *name, long nlen, char type, u64 size, i64 mtime, u32 mode) {
    u8 h[512];
    memset(h, 0, sizeof h);
    memcpy(h, name, (unsigned long)(nlen > 100 ? 100 : nlen));
    octal(h + 100, 8, mode);
    octal(h + 108, 8, 0);
    octal(h + 116, 8, 0);
    if (size >> 33) { /* GNU base-256 for 8 GiB and up */
        h[124] = 0x80;
        for (int i = 0; i < 8; i++) h[135 - i] = (u8)(size >> (8 * i));
    } else
        octal(h + 124, 12, size);
    octal(h + 136, 12, mtime < 0 ? 0 : (u64)mtime);
    memset(h + 148, ' ', 8);
    h[156] = (u8)type;
    memcpy(h + 257, "ustar  ", 8); /* GNU magic and version */
    memcpy(h + 265, "root", 4);
    memcpy(h + 297, "root", 4);
    u32 sum = 0;
    for (int i = 0; i < 512; i++) sum += h[i];
    octal(h + 148, 7, sum); /* six digits, a NUL, then the space already there */
    put(h, 512);
}
/* A member header; names over 100 bytes get a GNU ././@LongLink record first. */
static void tar_header(const char *name, int slash, char type, u64 size, i64 mtime, u32 mode) {
    long nl = (long)strlen(name);
    if (nl + slash > 100) {
        long total = nl + slash + 1; /* the name, its slash and a NUL, padded to a block */
        tar_block("././@LongLink", 13, 'L', (u64)total, 0, 0);
        put(name, nl);
        if (slash) putc_('/');
        put(zeros, 1);
        put(zeros, (512 - total % 512) % 512);
    }
    char nm[102];
    long c = nl > 100 ? 100 : nl;
    memcpy(nm, name, (unsigned long)c);
    if (slash && c < 100) nm[c++] = '/';
    tar_block(nm, c, type, size, mtime, mode);
}

static char tp[PMAX], ap[PMAX];

/* Streaming has begun and the archive can no longer be completed: end the response without the end-of-archive
   blocks, so no reader mistakes it for a whole archive. */
__attribute__((noreturn)) static void tar_abort(void) {
    flush();
    os_exit(1);
}

/* The dry run of tar_walk, before any header goes out: everything the walk would skip or fail on is refused here
   (a folder nested deeper than DEPTH with something inside, a path over PMAX, an entry that cannot be read). */
static void tar_check(int tl, int al, int depth) {
    struct fst st;
    if (os_lstat(tp, &st) < 0) die(500, "cannot read the selection");
    if (st.type == T_DIR) {
        Dir d;
        if (dir_open(&d, tp) < 0) die(500, "cannot read the selection");
        const char *nm;
        while ((nm = dir_next(&d))) {
            if (nm[0] == '.') continue;
            int t2 = pjoin(tp, tl, nm), a2 = pjoin(ap, al, nm);
            if (t2 < 0 || a2 < 0) die(400, "a path in the selection is too long");
            if (depth >= DEPTH) {
                struct fst c;
                if (os_lstat(tp, &c) < 0) die(500, "cannot read the selection");
                if (c.type == T_DIR || c.type == T_FILE) die(400, "folders are nested too deeply to download");
            } else
                tar_check(t2, a2, depth + 1);
            tp[tl] = 0;
            ap[al] = 0;
        }
        dir_close(&d);
    } else if (st.type == T_FILE) {
        int fd = os_open_rd(tp);
        if (fd < 0) die(500, "cannot read the selection");
        os_close(fd);
    }
}

static void tar_walk(int tl, int al, int depth) {
    struct fst st;
    if (os_lstat(tp, &st) < 0) tar_abort();
    if (st.type == T_DIR) {
        tar_header(ap, 1, '5', 0, st.mtime, 0755);
        if (depth >= DEPTH) return; /* tar_check refused anything inside */
        Dir d;
        if (dir_open(&d, tp) < 0) tar_abort();
        const char *nm;
        while ((nm = dir_next(&d))) {
            if (nm[0] == '.') continue;
            int t2 = pjoin(tp, tl, nm), a2 = pjoin(ap, al, nm);
            if (t2 >= 0 && a2 >= 0) tar_walk(t2, a2, depth + 1);
            tp[tl] = 0;
            ap[al] = 0;
        }
        dir_close(&d);
    } else if (st.type == T_FILE) {
        int fd = os_open_rd(tp);
        if (fd < 0) tar_abort();
        tar_header(ap, 0, '0', st.size, st.mtime, 0644);
        u64 left = st.size;
        while (left) {
            long r = os_read(fd, iobuf, left > sizeof iobuf ? (long)sizeof iobuf : (long)left);
            if (r == -ER_INTR || r == -ER_AGAIN) continue;
            if (r < 0) tar_abort(); /* a read error: no end-of-archive blocks follow */
            if (r == 0) { /* shrank: zero fill to the size already announced */
                while (left) {
                    long z = left > 512 ? 512 : (long)left;
                    put(zeros, z);
                    left -= (u64)z;
                }
                break;
            }
            put(iobuf, r);
            left -= (u64)r;
        }
        os_close(fd);
        if (st.size % 512) put(zeros, (long)(512 - st.size % 512));
    }
}

static void op_tar(void) {
    /* Check every path before the first byte goes out. */
    static char *srcs[MAXP];
    static char store[PSTORE];
    int used = 0, k = 0;
    for (int i = 0; i < np; i++) {
        if (strcmp(pk[i], "path")) continue;
        char path[PMAX];
        struct fst st;
        int l = resolve(pv[i], path, 0, &st);
        if (l == rootlen) die(400, "not the whole card");
        if (st.type != T_FILE && st.type != T_DIR) die(404, "not found");
        if (used + l + 1 > (int)sizeof store) die(400, "too many paths");
        memcpy(store + used, path, (unsigned long)l + 1);
        srcs[k++] = store + used;
        used += l + 1;
    }
    if (!k) die(400, "no path");
    /* The archive's name: name=, else the one item's name, else "M1 Plus"; ".tar" added. */
    static char aname[NAMEMAX + 8];
    const char *given = param("name");
    if (given && *given) check_name(given);
    const char *an = given && *given ? given : k == 1 ? base_name(srcs[0]) : "M1 Plus";
    long l = (long)strlen(an);
    if (l > NAMEMAX) l = NAMEMAX;
    memcpy(aname, an, (unsigned long)l);
    aname[l] = 0;
    if (l < 4 || strcmp(aname + l - 4, ".tar")) memcpy(aname + l, ".tar", 5);
    for (int i = 0; i < k; i++) { /* dry run: nothing is skipped silently once streaming starts */
        int tl = (int)strlen(srcs[i]), al = (int)strlen(base_name(srcs[i]));
        memcpy(tp, srcs[i], (unsigned long)tl + 1);
        memcpy(ap, base_name(srcs[i]), (unsigned long)al + 1);
        tar_check(tl, al, 0);
    }
    head(200, "application/x-tar");
    put_disposition(aname);
    puts_("\r\n");
    for (int i = 0; i < k; i++) {
        int tl = (int)strlen(srcs[i]), al = (int)strlen(base_name(srcs[i]));
        memcpy(tp, srcs[i], (unsigned long)tl + 1);
        memcpy(ap, base_name(srcs[i]), (unsigned long)al + 1); /* members are named from the item's own name */
        tar_walk(tl, al, 0);
    }
    put(zeros, 512);
    put(zeros, 512);
    flush();
}

/* ---- mkdir, rename, move, delete ---- */

static void need_octet_stream(void) {
    const char *ct = getenv_("CONTENT_TYPE");
    if (!ct || !starts_ieq(ct, "application/octet-stream")) die(403, "send Content-Type: application/octet-stream");
}

static void op_mkdir(void) {
    static char dp[PMAX];
    int dl = resolve_dir(param("path"), dp);
    const char *name = param("name");
    if (!name) die(400, "no name");
    check_card_name(name);
    if (pjoin(dp, dl, name) < 0) die(400, "path too long");
    struct fst st;
    if (os_lstat(dp, &st) == 0) die(409, "already exists");
    int r = os_mkdir(dp);
    if (r < 0) fail_errno(r, "cannot create the folder");
    json_head();
    puts_("{\"name\":");
    putjs(name);
    puts_("}\n");
}

static void op_rename(void) {
    static char fp[PMAX], tp2[PMAX];
    struct fst st;
    int fl = resolve(param("path"), fp, 0, &st);
    if (fl == rootlen) die(403, "the card itself");
    const char *name = param("name");
    if (!name) die(400, "no name");
    check_card_name(name);
    const char *base = base_name(fp);
    int dl = (int)(base - fp) - 1;
    memcpy(tp2, fp, (unsigned long)dl + 1);
    tp2[dl] = 0;
    if (pjoin(tp2, dl, name) < 0) die(400, "path too long");
    if (strcmp(base, name)) {
        struct fst t;
        /* the card ignores case: "a" to "A" is the same entry, so it is not a clash */
        if (!ieq(base, name) && os_lstat(tp2, &t) == 0) die(409, "already exists");
        int r;
        if (ieq(base, name)) {
            /* exFAT keeps the old case when the name only differs in case: go through a hidden temporary name */
            static char tmp[PMAX];
            char tn[16] = ".rename0.tmp";
            int tl = -1, i;
            for (i = 0; i < 10; i++) {
                tn[7] = (char)('0' + i);
                memcpy(tmp, fp, (unsigned long)dl + 1);
                tmp[dl] = 0;
                tl = pjoin(tmp, dl, tn);
                if (tl < 0) die(400, "path too long");
                if (os_lstat(tmp, &st) == -ER_NOENT) break;
            }
            if (i == 10) die(409, "no free temporary name");
            r = os_rename(fp, tmp);
            if (r < 0) fail_errno(r, "cannot rename");
            r = os_rename(tmp, tp2);
            if (r < 0) {
                os_rename(tmp, fp); /* roll back */
                fail_errno(r, "cannot rename");
            }
        } else {
            r = os_rename(fp, tp2);
            if (r < 0) fail_errno(r, "cannot rename");
        }
    }
    json_head();
    puts_("{\"name\":");
    putjs(name);
    puts_("}\n");
}

static int is_inside(const char *path, const char *dir) { /* path is dir or below it */
    long n = (long)strlen(dir);
    return !memcmp(path, dir, (unsigned long)n) && (!path[n] || path[n] == '/');
}

static void op_move(void) {
    static char dp[PMAX];
    static char store[PSTORE];
    static char *src[MAXP];
    int k = 0, used = 0;
    int dl = resolve_dir(param("to"), dp);
    const char *mode = param("conflict");
    int keep = mode && !strcmp(mode, "keep");
    if (mode && !keep && strcmp(mode, "fail")) die(400, "bad conflict mode");
    for (int i = 0; i < np; i++) {
        if (strcmp(pk[i], "path")) continue;
        char path[PMAX];
        struct fst st;
        int l = resolve(pv[i], path, 0, &st);
        if (l == rootlen) die(403, "the card itself");
        if (st.type == T_DIR && is_inside(dp, path)) die(400, "a folder cannot go into itself");
        if (used + l + 1 > (int)sizeof store) die(400, "too many paths");
        memcpy(store + used, path, (unsigned long)l + 1);
        src[k++] = store + used;
        used += l + 1;
    }
    if (!k) die(400, "no path");
    /* A clash is refused before anything moves. */
    static char nn[256];
    if (!keep) {
        for (int i = 0; i < k; i++) {
            const char *b = base_name(src[i]);
            if ((int)(b - src[i]) - 1 == dl && !memcmp(src[i], dp, (unsigned long)dl)) continue; /* already there */
            struct fst t;
            if (pjoin(dp, dl, b) < 0) die(400, "path too long");
            int r = os_lstat(dp, &t);
            dp[dl] = 0;
            if (r == 0) die(409, "already exists");
        }
    }
    static char tstore[PSTORE];
    static char *dst[MAXP];
    int tused = 0;
    for (int i = 0; i < k; i++) {
        const char *b = base_name(src[i]);
        if ((int)(b - src[i]) - 1 == dl && !memcmp(src[i], dp, (unsigned long)dl)) {
            dst[i] = 0;
            continue;
        }
        const char *to = b;
        if (keep) {
            struct fst t;
            if (pjoin(dp, dl, b) < 0) die(400, "path too long");
            int exists = os_lstat(dp, &t) == 0;
            dp[dl] = 0;
            if (exists) {
                keep_name(dp, dl, b, nn);
                to = nn;
            }
        }
        struct fst t;
        int tl = pjoin(dp, dl, to);
        if (tl < 0) die(400, "path too long");
        if (os_lstat(dp, &t) == 0) die(409, "already exists");
        if (tused + tl + 1 > (int)sizeof tstore) die(400, "too many paths");
        memcpy(tstore + tused, dp, (unsigned long)tl + 1);
        dst[i] = tstore + tused;
        tused += tl + 1;
        dp[dl] = 0;
        int r = os_rename(src[i], dst[i]);
        if (r < 0) fail_errno(r, "cannot move");
    }
    json_head();
    puts_("{\"moved\":[");
    for (int i = 0, first = 1; i < k; i++) {
        if (!dst[i]) continue;
        if (!first) putc_(',');
        first = 0;
        puts_("{\"from\":");
        put_vpath(src[i]);
        puts_(",\"to\":");
        put_vpath(dst[i]);
        putc_('}');
    }
    puts_("]}\n");
}

static char wp[PMAX];
static int rm_rf(int wl, int depth) {
    struct fst st;
    int r = os_lstat(wp, &st);
    if (r == -ER_NOENT) return 0;
    if (r < 0) return r;
    if (st.type != T_DIR) return os_unlink(wp);
    if (depth > DEPTH) return -ER_NAME;
    for (int pass = 0; pass < 4; pass++) {
        Dir d;
        r = dir_open(&d, wp);
        if (r < 0) return r;
        int bad = 0;
        const char *nm;
        while ((nm = dir_next(&d))) {
            int w2 = pjoin(wp, wl, nm);
            if (w2 < 0) {
                bad = -ER_NAME;
                continue;
            }
            int e = rm_rf(w2, depth + 1);
            wp[wl] = 0;
            if (e < 0) bad = e;
        }
        dir_close(&d);
        if (bad) return bad;
        r = os_rmdir(wp);
        if (r != -ER_NOTEMPTY) return r;
    }
    return -ER_NOTEMPTY;
}

static void op_delete(void) {
    static char store[PSTORE];
    static char *src[MAXP];
    int k = 0, used = 0;
    for (int i = 0; i < np; i++) {
        if (strcmp(pk[i], "path")) continue;
        char path[PMAX];
        struct fst st;
        int l = resolve(pv[i], path, 0, &st);
        if (l == rootlen) die(403, "the card itself");
        if (used + l + 1 > (int)sizeof store) die(400, "too many paths");
        memcpy(store + used, path, (unsigned long)l + 1);
        src[k++] = store + used;
        used += l + 1;
    }
    if (!k) die(400, "no path");
    for (int i = 0; i < k; i++) {
        int wl = (int)strlen(src[i]);
        memcpy(wp, src[i], (unsigned long)wl + 1);
        int r = rm_rf(wl, 0);
        if (r < 0) fail_errno(r, "cannot delete");
    }
    json_head();
    puts_("{\"deleted\":");
    putu((u64)k);
    puts_("}\n");
}

/* ---- upload ---- */

/* POST op=upload&path=<folder>&name=<file>&conflict=fail|replace|keep, the file as the raw body.
   Chunked: also offset=<bytes already stored> (0 starts) and last=1 on the final chunk; one request is then
   at most what thttpd carries (2 GiB - 1). The data goes to <folder>/.<name>.part, then rename. */
static void op_upload(void) {
    static char dp[PMAX], part[PMAX], fin[PMAX], kn[256];
    if (!getenv_("CONTENT_LENGTH")) die(400, "Content-Length required");
    u64 len = content_length();
    pending_body = len;
    need_octet_stream();
    const char *name = param("name"), *mode = param("conflict"), *off = param("offset"), *last = param("last");
    if (!name) die(400, "no name");
    if (!mode) mode = "fail";
    int cf = !strcmp(mode, "fail") ? 0 : !strcmp(mode, "replace") ? 1 : !strcmp(mode, "keep") ? 2 : -1;
    if (cf < 0) die(400, "bad conflict mode");
    int chunked = off != 0, final_ = !chunked || (last && !strcmp(last, "1"));
    u64 offset = 0;
    if (off) {
        int ok;
        offset = parse_u64(off, &ok);
        if (!ok) die(400, "bad offset");
    }
    check_card_name(name);
    int dl = resolve_dir(param("path"), dp);
    memcpy(fin, dp, (unsigned long)dl + 1);
    memcpy(part, dp, (unsigned long)dl + 1);
    kn[0] = '.';
    {
        long nl = (long)strlen(name);
        memcpy(kn + 1, name, (unsigned long)nl);
        memcpy(kn + 1 + nl, ".part", 6);
    }
    if (pjoin(part, dl, kn) < 0 || pjoin(fin, dl, name) < 0) die(400, "path too long");
    struct fst st;
    int exists = os_lstat(fin, &st) == 0;
    if (exists && !offset) {
        if (cf == 0 || (st.type != T_FILE && cf != 2)) die(409, "already exists");
    }
    u64 total, avail;
    if (os_statfs(WEBAPI_ROOT, &total, &avail) == 0 && avail < len) die(507, "the card is full");
    struct fst ps;
    int pr = os_lstat(part, &ps);
    if (offset) {
        if (pr < 0 || ps.type != T_FILE || ps.size != offset) die(409, "offset does not match the stored part");
    }
    int fd = os_open_wr(part, offset ? 1 : 0);
    if (fd < 0) fail_errno(fd, "cannot create the file");
    pending_body = 0; /* from here on the body is read, and a failure ends the request */
    u64 left = len;
    int err = 0;
    while (left) {
        long r = os_read(0, iobuf, left > sizeof iobuf ? (long)sizeof iobuf : (long)left);
        if (r == -ER_INTR || r == -ER_AGAIN) continue;
        if (r <= 0) {
            err = 400;
            break;
        } /* the client went away */
        long o = 0;
        while (o < r) {
            long w = os_write(fd, iobuf + o, r - o);
            if (w == -ER_INTR || w == -ER_AGAIN) continue;
            if (w <= 0) {
                err = w == -ER_NOSPC ? 507 : 500;
                break;
            }
            o += w;
        }
        if (err) break;
        left -= (u64)r;
    }
    if (!err && final_) {
        int s = os_fsync(fd);
        if (s < 0) err = s == -ER_NOSPC ? 507 : 500;
    }
    os_close(fd);
    if (err) {
        os_unlink(part);
        die(err, err == 507 ? "the card is full" : err == 400 ? "upload interrupted" : "cannot write the file");
    }
    if (!final_) {
        json_head();
        puts_("{\"size\":");
        putu(offset + len);
        puts_("}\n");
        return;
    }
    const char *fname = name;
    if (os_lstat(fin, &st) == 0) { /* it may have appeared since the first look */
        if (cf == 0 || (st.type != T_FILE && cf != 2)) {
            os_unlink(part);
            die(409, "already exists");
        }
        if (cf == 2) {
            fin[dl] = 0;
            keep_name(fin, dl, name, kn);
            fname = kn;
            pjoin(fin, dl, fname);
        }
    }
    int r = os_rename(part, fin);
    if (r < 0) {
        os_unlink(part);
        fail_errno(r, "cannot store the file");
    }
    json_head();
    puts_("{\"name\":");
    putjs(fname);
    puts_(",\"size\":");
    putu(offset + len);
    puts_("}\n");
}

/* ---- main ---- */

static int app(char **env) {
    envp = env;
    rootlen = (int)strlen(WEBAPI_ROOT);
    const char *method = getenv_("REQUEST_METHOD");
    const char *qs = getenv_("QUERY_STRING");
    if (!method) die(400, "not a CGI request");
    int post = !strcmp(method, "POST");
    if (!post && strcmp(method, "GET")) die(405, "use GET or POST");
    if (qs) {
        if (strlen(qs) >= sizeof qbuf) die(400, "query too long");
        memcpy(qbuf, qs, strlen(qs) + 1);
        parse(qbuf);
    }
    const char *op = param("op");
    if (!op) die(400, "no op");
    int mutating = !strcmp(op, "mkdir") || !strcmp(op, "rename") || !strcmp(op, "move") || !strcmp(op, "delete") ||
                   !strcmp(op, "upload");
    if (mutating && !post) die(405, "use POST");
    if (strcmp(op, "upload") && post) { /* the form body adds parameters */
        if (mutating) need_octet_stream();
        u64 n = content_length();
        if (n > BODYMAX) die(400, "body too large");
        read_exact(body, n);
        body[n] = 0;
        parse(body);
    }
    if (!strcmp(op, "list"))
        op_list();
    else if (!strcmp(op, "df"))
        op_df();
    else if (!strcmp(op, "download"))
        op_download();
    else if (!strcmp(op, "tar"))
        op_tar();
    else if (!strcmp(op, "mkdir"))
        op_mkdir();
    else if (!strcmp(op, "rename"))
        op_rename();
    else if (!strcmp(op, "move"))
        op_move();
    else if (!strcmp(op, "delete"))
        op_delete();
    else if (!strcmp(op, "upload"))
        op_upload();
    else
        die(400, "unknown op");
    flush();
    return 0;
}

#ifdef WEBAPI_HOST
int main(void) { return app(environ); }
#else
__attribute__((noreturn, used)) void webapi_start(long *sp) {
    long argc = sp[0];
    os_exit(app((char **)(sp + argc + 2)));
    for (;;) {
    }
}
#endif
