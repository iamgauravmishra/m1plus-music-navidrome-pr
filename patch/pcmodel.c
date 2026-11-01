/* M1+ Music Podcasts, the model: the shows and episodes on the card, the resume ring, the per-show speeds and the timer hook (pc_note).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 * The resume ring, the jump to a saved place a moment after an episode starts and the speed per folder follow q2-pod: its Resume and Podcasts sections. docs/modules/podcasts.md has the formats, the evidence and the approximations.
 *
 * One hook (pc_id3_path, below). Nothing else here runs by itself: the page (patch/podcasts.c) calls the model from its own events, and pc_note is called by the timers that already look at the
 * playing track (recent_note: Now Playing's tick, the mini player bar's, the Podcasts page's). So a place is saved only while one of those pages is in front.
 */
#include "offsets.inc"
#include "stock.h"
#include "covercache.h"
#include "common.h"
#include "i18n.h"
#include "home.h"
#include "podcasts.h"

#define I(r, off) (*(int *)((char *)(r) + (off)))

_Static_assert(sizeof(pc_ep_t) == PC_EP_SIZE, "pc_ep_t");
_Static_assert(sizeof(pc_show_t) == PC_SHOW_SIZE, "pc_show_t");
_Static_assert(
    __builtin_offsetof(pc_ep_t, hash) == PC_EP_HASH && __builtin_offsetof(pc_show_t, hash) == PC_SH_HASH &&
        __builtin_offsetof(pc_show_t, checked) == PC_SH_CHECKED && __builtin_offsetof(pc_show_t, feed) == PC_SH_FEED &&
        __builtin_offsetof(pc_show_t, image) == PC_SH_IMAGE && __builtin_offsetof(pc_ep_t, desc) == PC_EP_DESC &&
        __builtin_offsetof(pc_show_t, author) == PC_SH_AUTHOR && __builtin_offsetof(pc_show_t, category) == PC_SH_CAT &&
        __builtin_offsetof(pc_show_t, desc) == PC_SH_DESC && __builtin_offsetof(pc_show_t, newest) == PC_SH_NEWEST,
    "offsets");

#define PM_ROOT "/mnt/mmc"
#define PM_STATE_DIR CARD_DIR "/podcasts"
#define PM_RING_FILE PM_STATE_DIR "/resume"
#define PM_RING_TMP PM_STATE_DIR "/resume.tmp"
#define PM_SPEED_FILE PM_STATE_DIR "/speed"
#define PM_SPEED_TMP PM_STATE_DIR "/speed.tmp"
#define PM_DNAME 11 /* struct dirent (32-bit, MIPS o32): d_ino, d_off, d_reclen (2), d_type (1), d_name at 11 */
#define PM_PATH 400
#define PM_MAX_FILES 400 /* files looked at in one show folder */
#define PM_META_MAX 65536 /* bytes of a metadata file read */
#define PM_LINE_MAX 4096

/* ---------------------------------------------------------------------------
 * Small helpers (the payload links no libc string functions of its own)
 */
static unsigned pm_len(const char *s) {
    unsigned n = 0;
    while (s[n]) ++n;
    return n;
}

static int pm_lc(int c) { return (unsigned)(c - 'A') < 26u ? c + 32 : c; }

/* The first n bytes of a and b equal, ASCII case aside (b is never shorter). */
static int pm_ieq_n(const char *a, const char *b, unsigned n) {
    unsigned i;
    for (i = 0; i < n; ++i)
        if (!a[i] || pm_lc((unsigned char)a[i]) != pm_lc((unsigned char)b[i])) return 0;
    return 1;
}

static int pm_eq(const char *a, const char *b) {
    while (*a && *a == *b) ++a, ++b;
    return *a == *b;
}

/* s (n bytes, or to its NUL when n < 0) into out of size bytes with a NUL, cut before a UTF-8 continuation byte; control bytes become spaces. */
static void pm_cpy_n(char *out, unsigned size, const char *s, int n) {
    unsigned len = 0, k;
    while ((n < 0 ? s[len] : len < (unsigned)n) && s[len]) ++len;
    if (len >= size) {
        len = size - 1;
        while (len && ((unsigned char)s[len] & 0xc0) == 0x80) --len;
    }
    for (k = 0; k < len; ++k) out[k] = (unsigned char)s[k] < 32 ? ' ' : s[k];
    out[len] = 0;
}

static void pm_cpy(char *out, unsigned size, const char *s) { pm_cpy_n(out, size, s, -1); }

/* out (size) ends with s appended; 0 when it does not fit. */
static int pm_cat(char *out, unsigned size, const char *s) {
    unsigned n = pm_len(out), m = pm_len(s);
    if (n + m + 1 > size) return 0;
    memcpy(out + n, s, m + 1);
    return 1;
}

/* The decimal number in s[0..n): its leading digits (0 when there are none), capped at 0xfffffffe. */
static unsigned pm_num(const char *s, unsigned n) {
    unsigned v = 0, i;
    for (i = 0; i < n && (unsigned)(s[i] - '0') < 10u; ++i) {
        if (v > 429496728u) return 0xfffffffeu;
        v = v * 10 + (unsigned)(s[i] - '0');
    }
    return v;
}

unsigned pc_hash(const char *s) {
    unsigned h = FNV_SEED;
    for (; *s; ++s) h = (h ^ (unsigned)pm_lc((unsigned char)*s)) * 16777619u;
    return h | !h;
}

static unsigned pm_fnv_n(const char *s, unsigned n) {
    unsigned h = FNV_SEED, i;
    for (i = 0; i < n; ++i) h = (h ^ (unsigned char)s[i]) * 16777619u;
    return h | !h;
}

unsigned pc_guid_hash(const char *s, unsigned n) { return pm_fnv_n(s, n); }

/* fmt with its %d replaced by n (the translation tables allow one %d a text). */
void pc_fmt(char *out, unsigned size, const char *fmt, unsigned n) {
    char num[12];
    unsigned k = 0, o = 0, i;
    do num[k++] = (char)('0' + n % 10), n /= 10;
    while (n && k < sizeof num);
    for (; *fmt && o + 1 < size; ++fmt) {
        if (fmt[0] == '%' && fmt[1] == 'd') {
            for (i = k; i && o + 1 < size; --i) out[o++] = num[i - 1];
            ++fmt;
        } else
            out[o++] = *fmt;
    }
    out[o] = 0;
}

void pc_fmt2(char *out, unsigned size, const char *fmt, unsigned a, unsigned b) {
    char num[2][12];
    unsigned len[2], k, i, o = 0, which = 0, v[2];
    v[0] = a, v[1] = b;
    for (which = 0; which < 2; ++which) {
        unsigned n = v[which];
        k = 0;
        do num[which][k++] = (char)('0' + n % 10), n /= 10;
        while (n && k < sizeof num[0]);
        len[which] = k;
    }
    which = 0;
    for (; *fmt && o + 1 < size; ++fmt) {
        if (fmt[0] == '%' && fmt[1] == 'd') {
            for (i = len[which]; i && o + 1 < size; --i) out[o++] = num[which][i - 1];
            which = 1;
            ++fmt;
        } else
            out[o++] = *fmt;
    }
    out[o] = 0;
}

/* The date of an episode as Apple Podcasts writes it, in the language: "Just now", "Nm ago", "Nh ago", "Nd ago" (under 7 days), else "Oct 23" (this year) or "Oct 23, 2025".
 * now and pub are seconds since 1970 (UTC); the calendar is the local one the status bar clock keeps (localtime). A clock that was never set (before 2024) or a date more than a
 * minute ahead of it gives the absolute form. The month texts are keys with their one %d ("Oct %d": the order of month and day is the language's). */
void pc_when(unsigned pub, unsigned now, char *out, unsigned size) {
    static const char *const mon[12] = {"Jan %d", "Feb %d", "Mar %d", "Apr %d", "May %d", "Jun %d",
                                        "Jul %d", "Aug %d", "Sep %d", "Oct %d", "Nov %d", "Dec %d"};
    long t = (long)pub, n = (long)now;
    int tm[9], i, year_now;
    const int *p;
    unsigned d;
    out[0] = 0;
    p = localtime(&n);
    year_now = p ? p[5] + 1900 : 0;
    if (year_now >= 2024 && pub <= now + 60) {
        d = pub >= now ? 0 : now - pub;
        if (d < 60)
            pm_cpy(out, size, TR("Just now"));
        else if (d < 3600)
            pc_fmt(out, size, TR("%dm ago"), d / 60);
        else if (d < 86400)
            pc_fmt(out, size, TR("%dh ago"), d / 3600);
        else if (d < 7 * 86400)
            pc_fmt(out, size, TR("%dd ago"), d / 86400);
        else
            d = 0;
        if (out[0]) return;
    }
    p = localtime(&t);
    if (!p) return;
    for (i = 0; i < 9; ++i) tm[i] = p[i]; /* (localtime's one buffer) */
    pc_fmt(out, size, TR(mon[tm[4] < 0 || tm[4] > 11 ? 0 : tm[4]]), (unsigned)tm[3]);
    if (tm[5] + 1900 != year_now) {
        char yr[24];
        unsigned o = pm_len(out);
        pc_fmt(yr, sizeof yr, TR(", %d"), (unsigned)(tm[5] + 1900));
        if (o + pm_len(yr) + 1 <= size) memcpy(out + o, yr, pm_len(yr) + 1);
    }
}

/* ---------------------------------------------------------------------------
 * The folder and the files
 */

/* Whether the extension of name is one the player takes for spoken audio. */
static int pm_audio(const char *name) {
    static const char *const ext[] = {"mp3", "m4a", "m4b", "aac", "ogg", "opus", "flac", "wav", "wma"};
    unsigned n = pm_len(name), i, e;
    const char *dot = name + n;
    while (dot > name && dot[-1] != '.') --dot;
    if (dot == name || dot[-1] != '.' || dot == name + 1) return 0;
    for (i = 0; i < sizeof ext / sizeof *ext; ++i) {
        e = pm_len(ext[i]);
        if (pm_len(dot) == e && pm_ieq_n(dot, ext[i], e)) return 1;
    }
    return 0;
}

static int pm_part(const char *name) {
    unsigned n = pm_len(name);
    return n > 5 && pm_ieq_n(name + n - 5, ".part", 5);
}

static const char *pm_name(char *ent) { return ent + PM_DNAME; }

/* A directory: opendir works. */
static int pm_is_dir(const char *path) {
    void *d = opendir(path);
    if (d) closedir(d);
    return d != (void *)0;
}

int pc_root(char *out) {
    void *d;
    char *ent;
    int found = 0;
    memcpy(out, PM_ROOT "/Podcasts", sizeof(PM_ROOT "/Podcasts"));
    if (pm_is_dir(out)) return 1;
    d = opendir(PM_ROOT);
    if (!d) return 0;
    while (!found && (ent = readdir(d)) != (char *)0) {
        const char *n = pm_name(ent);
        char path[PC_FILE + 20];
        if (pm_len(n) != 8 || !pm_ieq_n(n, "podcasts", 8)) continue;
        memcpy(path, PM_ROOT "/", sizeof(PM_ROOT "/"));
        if (pm_cat(path, sizeof path, n) && pm_is_dir(path)) memcpy(out, path, pm_len(path) + 1), found = 1;
    }
    closedir(d);
    return found;
}

/* The path of a show's file: root/dir/name into out. */
static int pm_join(char *out, unsigned size, const char *root, const char *dir, const char *name) {
    pm_cpy(out, size, root);
    return pm_cat(out, size, "/") && pm_cat(out, size, dir) &&
           (!name || (pm_cat(out, size, "/") && pm_cat(out, size, name)));
}

/* Up to cap bytes of a file into a heap buffer (NUL after the data); NULL when it cannot be read or is empty. *n is the length. */
static char *pm_slurp(const char *path, unsigned cap, unsigned *n) {
    char *buf;
    int fd = open(path, O_RDONLY, 0), got = 0, r;
    if (fd < 0) return (char *)0;
    buf = calloc(cap + 1, 1);
    while (buf && (unsigned)got < cap && (r = read(fd, buf + got, cap - (unsigned)got)) > 0) got += r;
    close(fd);
    if (!buf || got <= 0) {
        free(buf);
        return (char *)0;
    }
    *n = (unsigned)got;
    return buf;
}

/* ---------------------------------------------------------------------------
 * The text formats
 */

/* The line [p, stop) of buf up to a newline: sets *end to the newline (or stop) and returns the line's length without a trailing CR. */
static unsigned pm_line(const char *p, const char *stop, const char **next) {
    const char *q = p;
    unsigned n;
    while (q < stop && *q != '\n') ++q;
    n = (unsigned)(q - p);
    *next = q < stop ? q + 1 : q;
    if (n && p[n - 1] == '\r') --n;
    return n;
}

static int pm_header(const char *buf, unsigned n, const char *magic, const char **after) {
    const char *stop = buf + n, *next;
    unsigned m = pm_len(magic), len = pm_line(buf, stop, &next);
    if (len != m || !pm_ieq_n(buf, magic, m)) return 0;
    *after = next;
    return 1;
}

int pc_parse_eps(const char *buf, unsigned n, pc_ep_t *out, int max) {
    const char *p, *stop = buf + n, *next;
    int count = 0;
    if (!pm_header(buf, n, "M1PLUS-EPISODES 1", &p)) return 0;
    for (; p < stop && count < max; p = next) {
        unsigned len = pm_line(p, stop, &next), at = 0;
        pc_ep_t *e = &out[count];
        int any = 0;
        if (!len || p[0] == '#' || len > PM_LINE_MAX) continue;
        memset(e, 0, sizeof *e);
        e->state = PC_REMOTE;
        while (
            at <
            len) { /* tab separated key=value fields: g guid, p pubDate, d duration, l enclosure length, f file, t title (u url and x description are the subscribe phase's) */
            const char *f = p + at;
            unsigned flen = 0;
            while (at + flen < len && f[flen] != '\t') ++flen;
            if (flen >= 2 && f[1] == '=') {
                const char *v = f + 2;
                unsigned vlen = flen - 2;
                switch (f[0]) {
                case 'g':
                    e->guid = vlen ? pm_fnv_n(v, vlen) : 0, any |= vlen != 0;
                    break;
                case 'p':
                    e->pub = pm_num(v, vlen);
                    break;
                case 'd':
                    e->dur = pm_num(v, vlen);
                    break;
                case 'l':
                    e->length = pm_num(v, vlen);
                    break;
                case 'f':
                    if (vlen && vlen < PC_FILE) pm_cpy_n(e->file, PC_FILE, v, (int)vlen), any = 1;
                    break;
                case 't':
                    pm_cpy_n(e->title, PC_TITLE, v, (int)vlen), any |= vlen != 0;
                    break;
                case 'u':
                    any |= vlen != 0;
                    break;
                case 'x':
                    pm_cpy_n(e->desc, PC_DESC, v, (int)vlen);
                    break;
                default:
                    break;
                }
            }
            at += flen + 1;
        }
        if (any) ++count;
    }
    return count;
}

int pc_parse_show(const char *buf, unsigned n, pc_show_t *show) {
    const char *p, *stop = buf + n, *next;
    if (!pm_header(buf, n, "M1PLUS-SHOW 1", &p)) return 0;
    for (; p < stop; p = next) {
        unsigned len = pm_line(p, stop, &next);
        if (len >= 6 && pm_ieq_n(p, "title=", 6))
            pm_cpy_n(show->title, PC_TITLE, p + 6, (int)len - 6);
        else if (len >= 5 && pm_ieq_n(p, "feed=", 5))
            pm_cpy_n(show->feed, PC_URL, p + 5, (int)len - 5);
        else if (len >= 6 && pm_ieq_n(p, "image=", 6))
            pm_cpy_n(show->image, PC_URL, p + 6, (int)len - 6);
        else if (len >= 8 && pm_ieq_n(p, "checked=", 8))
            show->checked = pm_num(p + 8, len - 8);
        else if (len >= 7 && pm_ieq_n(p, "author=", 7))
            pm_cpy_n(show->author, PC_AUTHOR, p + 7, (int)len - 7);
        else if (len >= 9 && pm_ieq_n(p, "category=", 9))
            pm_cpy_n(show->category, PC_CAT, p + 9, (int)len - 9);
        else if (len >= 5 && pm_ieq_n(p, "desc=", 5))
            pm_cpy_n(show->desc, PC_DESC, p + 5, (int)len - 5);
    }
    return 1;
}

/* ---------------------------------------------------------------------------
 * The shows
 */

/* A cover picture's name: the rank of the best (0 is best), or -1. */
static int pm_cover_rank(const char *name) {
    static const char *const names[] = {"cover.jpg",  "cover.png",  "cover.jpeg",
                                        "folder.jpg", "folder.png", "folder.jpeg"};
    unsigned i, n = pm_len(name);
    for (i = 0; i < sizeof names / sizeof *names; ++i)
        if (pm_len(names[i]) == n && pm_ieq_n(name, names[i], n)) return (int)i;
    return -1;
}

static pc_show_t *pm_sort_shows __attribute__((section(".scratch")));

/* The Shows page's order: the most recently updated first (newest episode, remote or local), ties by title. */
static int pm_show_cmp(unsigned a, unsigned b) {
    const pc_show_t *x = &pm_sort_shows[a], *y = &pm_sort_shows[b];
    int d;
    if (x->newest != y->newest) return x->newest > y->newest ? -1 : 1;
    d = cc_name_cmp(x->title, y->title);
    return d ? d : a < b ? -1 : a > b;
}

/* The largest p= (publication date) of the entries of a .episodes buffer: only a line that is an entry counts (as pc_parse_eps reads it: one of g, f, t, u has a value), at most
 * PC_MAX_EPS entries (the newest come first in the file the refresh writes). 0 when there is none. */
static unsigned pm_newest_pub(const char *buf, unsigned n) {
    const char *p, *stop = buf + n, *next;
    unsigned best = 0;
    int entries = 0;
    if (!pm_header(buf, n, "M1PLUS-EPISODES 1", &p)) return 0;
    for (; p < stop && entries < PC_MAX_EPS; p = next) {
        unsigned len = pm_line(p, stop, &next), at = 0, pub = 0;
        int any = 0;
        if (!len || p[0] == '#' || len > PM_LINE_MAX) continue;
        while (at < len) {
            const char *f = p + at;
            unsigned flen = 0;
            while (at + flen < len && f[flen] != '\t') ++flen;
            if (flen >= 2 && f[1] == '=') {
                unsigned vlen = flen - 2;
                if (f[0] == 'p')
                    pub = pm_num(f + 2, vlen);
                else if (f[0] == 'f')
                    any |= vlen && vlen < PC_FILE;
                else if (f[0] == 'g' || f[0] == 't' || f[0] == 'u')
                    any |= vlen != 0;
            }
            at += flen + 1;
        }
        if (any) {
            ++entries;
            if (pub > best) best = pub;
        }
    }
    return best;
}

/* One show folder's summary into *s: its audio files (and how many are new), the best cover, the show file, the newest episode's date. 1 when it is a show (it has an audio file or a metadata file). */
static int pm_summary(const char *root, pc_show_t *s) {
    char path[PM_PATH];
    void *d;
    char *ent;
    int best = 99, meta = 0, has_eps = 0;
    char *buf;
    unsigned n, file_newest = 0;
    s->count = s->fresh = s->newest = 0;
    s->cover[0] = 0;
    s->hash = pc_hash(s->dir);
    pm_cpy(s->title, PC_TITLE, s->dir);
    if (pm_join(path, sizeof path, root, s->dir, ".episodes") && (buf = pm_slurp(path, PM_META_MAX, &n)) != (char *)0) {
        s->newest = pm_newest_pub(
            buf, n); /* the entries' dates: a downloaded file's own date is the download's, not the episode's */
        has_eps = s->newest != 0; /* (entries with no date: the files' dates, as the merge takes them) */
        free(buf);
    }
    if (!pm_join(path, sizeof path, root, s->dir, (const char *)0) || !(d = opendir(path))) return 0;
    while ((ent = readdir(d)) != (char *)0) {
        const char *name = pm_name(ent);
        char full[PM_PATH];
        int rank;
        if (!*name) continue;
        if (name[0] == '.') { /* the metadata files; any other dot file is not ours */
            if (pm_eq(name, ".episodes") || pm_eq(name, ".show")) meta = 1;
            continue;
        }
        if (pm_len(name) >= PC_FILE) continue;
        rank = pm_cover_rank(name);
        if (rank >= 0 && rank < best) best = rank, pm_cpy(s->cover, PC_FILE, name);
        if (!pm_audio(name)) continue;
        ++s->count;
        if (pm_join(full, sizeof full, root, s->dir, name)) {
            unsigned pos, len;
            if (pc_state(pc_hash(full), &pos, &len) == PC_NEW) ++s->fresh;
            if (!has_eps) { /* no metadata: the episodes are the files, dated by them (one stat each) */
                unsigned st[40];
                memset(st, 0, sizeof st);
                if (__xstat(3, full, st) == 0 && st[0x40 / 4] > file_newest) file_newest = st[0x40 / 4];
            }
        }
    }
    closedir(d);
    if (!has_eps) s->newest = file_newest;
    if (pm_join(path, sizeof path, root, s->dir, ".show") && (buf = pm_slurp(path, 4096, &n)) != (char *)0) {
        pc_parse_show(buf, n, s);
        free(buf);
    }
    return s->count > 0 || meta;
}

int pc_scan_shows(pc_show_t *out, int max) {
    char root[PC_FILE + 20];
    void *d;
    char *ent;
    unsigned *order;
    int count = 0, i;
    if (!pc_root(root) || !(d = opendir(root))) return 0;
    while (count < max && (ent = readdir(d)) != (char *)0) {
        const char *name = pm_name(ent);
        char path[PM_PATH];
        pc_show_t *s = &out[count];
        if (!*name || name[0] == '.' || pm_len(name) >= PC_FILE) continue;
        if (!pm_join(path, sizeof path, root, name, (const char *)0) || !pm_is_dir(path)) continue;
        memset(s, 0, sizeof *s);
        pm_cpy(s->dir, PC_FILE, name);
        if (pm_summary(root, s)) ++count;
    }
    closedir(d);
    order = count > 1 ? calloc((unsigned)count, sizeof *order) : (unsigned *)0;
    if (order) { /* sorted by title, a leading "The " aside; without memory the folders stay in the card's order */
        pc_show_t *copy = calloc((unsigned)count, sizeof *copy);
        if (copy) {
            memcpy(copy, out, (unsigned)count * sizeof *copy);
            for (i = 0; i < count; ++i) order[i] = (unsigned)i;
            pm_sort_shows = copy;
            cc_heapsort(order, (unsigned)count, pm_show_cmp);
            for (i = 0; i < count; ++i) memcpy(&out[i], &copy[order[i]], sizeof *copy);
            free(copy);
        }
        free(order);
    }
    return count;
}

/* ---------------------------------------------------------------------------
 * The episodes: files on the card merged with the metadata, newest first
 */
typedef struct {
    char name[PC_FILE];
    unsigned mtime;
} pm_file_t;

static pc_ep_t *pm_sort_eps __attribute__((section(".scratch")));

/* Newest first: the date, then the file name (the later name first: a numbered series reads from its last), the entry order last. */
static int pm_ep_cmp(unsigned a, unsigned b) {
    const pc_ep_t *x = &pm_sort_eps[a], *y = &pm_sort_eps[b];
    int d;
    if (x->pub != y->pub) return x->pub > y->pub ? -1 : 1;
    d = cc_nocase(y->file, x->file);
    if (d) return d;
    return a < b ? -1 : a > b;
}

/* A title from a file name: the name without its extension. */
static void pm_title_of(char *out, const char *name) {
    unsigned n = pm_len(name);
    char tmp[PC_FILE];
    pm_cpy(tmp, sizeof tmp, name);
    while (n && tmp[n - 1] != '.') --n;
    if (n > 1) tmp[n - 1] = 0;
    pm_cpy(out, PC_TITLE, tmp);
}

static int pm_find(const pm_file_t *files, int nf, const char *name) {
    int i;
    for (i = 0; i < nf; ++i)
        if (pm_eq(files[i].name, name)) return i;
    return -1;
}

/* The merge (the one place a metadata entry and a file meet): eps[0..nm) are the metadata entries, files the folder's audio and .part files. A file with an
 * entry gives it PC_LOCAL (its file name matches the entry's f); an entry whose file is missing is PC_PART when name.part is there, else PC_REMOTE; a file with no entry is
 * a new PC_LOCAL episode (title from the name, date from the file). Returns the count (at most cap). */
static int pm_merge(pc_ep_t *eps, int nm, int cap, const pm_file_t *files, int nf, const char *root, const char *dir) {
    unsigned char *used = calloc((unsigned)(nf ? nf : 1), 1);
    int i, n = nm;
    char path[PM_PATH], part[PC_FILE + 8];
    for (i = 0; i < nm; ++i) {
        pc_ep_t *e = &eps[i];
        int j = e->file[0] ? pm_find(files, nf, e->file) : -1;
        if (j >= 0) {
            e->state = PC_LOCAL;
            if (used) used[j] = 1;
            if (!e->title[0]) pm_title_of(e->title, e->file);
            if (!e->pub) e->pub = files[j].mtime;
            if (pm_join(path, sizeof path, root, dir, e->file)) e->hash = pc_hash(path);
        } else {
            e->state = PC_REMOTE;
            if (e->file[0]) {
                pm_cpy(part, sizeof part, e->file);
                if (pm_cat(part, sizeof part, ".part") && pm_find(files, nf, part) >= 0) e->state = PC_PART;
            }
            e->hash = 0;
        }
    }
    for (i = 0; i < nf && n < cap; ++i) {
        pc_ep_t *e = &eps[n];
        if (!pm_audio(files[i].name) || (used && used[i])) continue;
        memset(e, 0, sizeof *e);
        pm_cpy(e->file, PC_FILE, files[i].name);
        pm_title_of(e->title, e->file);
        e->pub = files[i].mtime;
        e->state = PC_LOCAL;
        if (pm_join(path, sizeof path, root, dir, e->file)) e->hash = pc_hash(path);
        ++n;
    }
    free(used);
    return n;
}

/* The folder's files with their modification times: audio and .part files, at most max. */
static int pm_files(const char *root, const char *dir, pm_file_t *files, int max) {
    char path[PM_PATH];
    unsigned st[40]; /* struct stat (MIPS o32, 144 bytes): st_mtime at +0x40 */
    void *d;
    char *ent;
    int n = 0;
    if (!pm_join(path, sizeof path, root, dir, (const char *)0) || !(d = opendir(path))) return 0;
    while (n < max && (ent = readdir(d)) != (char *)0) {
        const char *name = pm_name(ent);
        char full[PM_PATH];
        if (!*name || name[0] == '.' || pm_len(name) >= PC_FILE || !(pm_audio(name) || pm_part(name))) continue;
        pm_cpy(files[n].name, PC_FILE, name);
        files[n].mtime = 0;
        memset(st, 0, sizeof st);
        if (pm_join(full, sizeof full, root, dir, name) && __xstat(3, full, st) == 0) files[n].mtime = st[0x40 / 4];
        ++n;
    }
    closedir(d);
    return n;
}

/* One file of a show folder: its modification time and its size in KB (struct stat, MIPS o32: st_size at +0x30, st_mtime at +0x40). 1 when it exists. */
int pc_stat(const char *root, const char *dir, const char *file, unsigned *mtime, unsigned *kb) {
    char full[PM_PATH];
    unsigned st[40];
    memset(st, 0, sizeof st);
    *mtime = *kb = 0;
    if (!pm_join(full, sizeof full, root, dir, file) || __xstat(3, full, st) != 0) return 0;
    *mtime = st[0x40 / 4];
    *kb = st[0x30 / 4] >> 10;
    return 1;
}

/* The audio files and .part files of a show folder, one callback each (the name, the audio's or .part's size in KB, 1 for a .part): the Shows page's totals. No .episodes is read. At most PM_MAX_FILES files. */
int pc_walk(const char *root, const char *dir, void (*cb)(void *ctx, const char *name, unsigned kb, int part),
            void *ctx) {
    char path[PM_PATH];
    unsigned st[40];
    void *d;
    char *ent;
    int n = 0;
    if (!pm_join(path, sizeof path, root, dir, (const char *)0) || !(d = opendir(path))) return 0;
    while (n < PM_MAX_FILES && (ent = readdir(d)) != (char *)0) {
        const char *name = pm_name(ent);
        char full[PM_PATH];
        int part;
        if (!*name || name[0] == '.' || pm_len(name) >= PC_FILE) continue;
        part = pm_part(name);
        if (!part && !pm_audio(name)) continue;
        memset(st, 0, sizeof st);
        if (pm_join(full, sizeof full, root, dir, name)) __xstat(3, full, st);
        cb(ctx, name, st[0x30 / 4] >> 10, part);
        ++n;
    }
    closedir(d);
    return n;
}

int pc_load_show(const pc_show_t *show, pc_ep_t *out, int max) {
    char root[PC_FILE + 20], path[PM_PATH];
    pm_file_t *files;
    pc_ep_t *work;
    unsigned *order, got;
    char *buf;
    int nf, nm = 0, n, i;
    if (!pc_root(root) || max <= 0) return 0;
    files = calloc(PM_MAX_FILES, sizeof *files);
    work = calloc((unsigned)(PC_MAX_EPS + PM_MAX_FILES), sizeof *work);
    if (!files || !work) {
        free(files);
        free(work);
        return 0;
    }
    nf = pm_files(root, show->dir, files, PM_MAX_FILES);
    if (pm_join(path, sizeof path, root, show->dir, ".episodes") &&
        (buf = pm_slurp(path, PM_META_MAX, &got)) != (char *)0) {
        nm = pc_parse_eps(buf, got, work, PC_MAX_EPS);
        free(buf);
    }
    n = pm_merge(work, nm, PC_MAX_EPS + PM_MAX_FILES, files, nf, root, show->dir);
    order = calloc((unsigned)(n ? n : 1), sizeof *order);
    if (order) {
        for (i = 0; i < n; ++i) order[i] = (unsigned)i;
        pm_sort_eps = work;
        cc_heapsort(order, (unsigned)n, pm_ep_cmp);
        if (n > max) n = max;
        for (i = 0; i < n; ++i) memcpy(&out[i], &work[order[i]], sizeof *out);
    } else {
        if (n > max) n = max;
        memcpy(out, work, (unsigned)n * sizeof *out); /* no memory to sort in: the entries in file order */
    }
    free(order);
    free(files);
    free(work);
    return n;
}

/* ---------------------------------------------------------------------------
 * Paths, the cover picture
 */
int pc_is_path(const char *path) {
    static const char prefix[] = PM_ROOT "/podcasts/";
    const char *p;
    if (!pm_ieq_n(path, prefix, sizeof prefix - 1)) return 0;
    p = path + sizeof prefix - 1;
    while (*p && *p != '/') ++p;
    return *p == '/' && p[1] != 0 && p > path + sizeof prefix - 1;
}

unsigned pc_show_of(const char *path) {
    static const char prefix[] = PM_ROOT "/podcasts/";
    const char *p;
    char name[PC_FILE];
    if (!pc_is_path(path)) return 0;
    p = path + sizeof prefix - 1;
    {
        unsigned n = 0;
        while (p[n] != '/') ++n;
        pm_cpy_n(name, sizeof name, p, (int)n);
    }
    return pc_hash(name);
}

static unsigned pm_be16(const unsigned char *b) { return (unsigned)b[0] << 8 | b[1]; }
static unsigned pm_be32(const unsigned char *b) {
    return (unsigned)b[0] << 24 | (unsigned)b[1] << 16 | (unsigned)b[2] << 8 | b[3];
}

int pc_pic_info(const char *path, unsigned *pw, unsigned *ph, unsigned *psof) {
    unsigned char b[32];
    unsigned w = 0, h = 0, sofm = 0;
    int kind = 0, steps = 0;
    void *f = fopen(path, "rb");
    *pw = *ph = *psof = 0;
    if (!f) return 0;
    if (fread(b, 1, 24, f) != 24) {
        fclose(f);
        return 0;
    }
    if (b[0] == 0x89 && b[1] == 'P' && b[2] == 'N' && b[3] == 'G') { /* PNG: IHDR's width and height at 16 and 20 */
        w = pm_be32(b + 16), h = pm_be32(b + 20), kind = 2;
    } else if (b[0] == 0xff && b[1] == 0xd8) { /* JPEG: the segments up to a start-of-frame */
        long at = 2;
        kind = 1;
        while (steps++ < 64) {
            unsigned len, marker;
            if (fseek(f, at, 0) || fread(b, 1, 4, f) != 4) break;
            if (b[0] != 0xff) break;
            marker = b[1];
            if (marker == 0xff) { /* fill byte */
                ++at;
                continue;
            }
            if (marker == 0xd8 || marker == 0x01 || (marker >= 0xd0 && marker <= 0xd7)) {
                at += 2;
                continue;
            }
            len = pm_be16(b + 2);
            if (marker == 0xd9 || marker == 0xda || len < 2) break;
            if (marker >= 0xc0 && marker <= 0xcf && marker != 0xc4 && marker != 0xc8 && marker != 0xcc) {
                unsigned char sof[5];
                if (fseek(f, at + 5, 0) || fread(sof, 1, 4, f) != 4) break;
                h = pm_be16(sof), w = pm_be16(sof + 2), sofm = marker;
                break;
            }
            at += 2 + len;
        }
    }
    fclose(f);
    *pw = w, *ph = h, *psof = sofm;
    return kind;
}

int pc_cover_ok(const char *path) {
    unsigned w, h, sof;
    pc_pic_info(path, &w, &h, &sof);
    return w && h && w <= 8192 && h <= 8192 && w * h <= PC_COVER_MAX_PX;
}

/* ---------------------------------------------------------------------------
 * The ring of places, on the card: PM_RING_FILE is "PCR1", the slot count (a word), then the slots, most recent first
 */
typedef struct {
    unsigned hash, pos, len, flags; /* flags: 1 = played */
} slot_t;

static struct {
    slot_t *s;
    unsigned n;
    int loaded, dirty;
    unsigned rev;
    unsigned sp[2 + PC_SPEED_SLOTS * 2]; /* the speeds: "PCS1", count, then (show hash, mode) pairs */
    int sp_loaded;
} pm __attribute__((section(".scratch")));

static struct {
    unsigned cur; /* ring key of the episode the player is on (0: not a podcast) */
    int pos, len; /* what the last look saw */
    int pend; /* a jump to pend_pos is due */
    unsigned pend_pos, pend_ms, hold_ms;
    unsigned save_ms;
    unsigned
        apply_ms; /* when the page last set the speed for an episode about to start (the music of before is seen playing until it does) */
    int speed_on, orig; /* we changed playspeed_mode; the mode it was */
} pcs __attribute__((section(".scratch")));

static int pm_save(const char *path, const char *tmp, const void *head, unsigned hn, const void *body, unsigned bn) {
    int fd, ok;
    if (!pod_card_mounted()) return -1;
    mkdir(CARD_DIR, 0755);
    mkdir(PM_STATE_DIR, 0755);
    fd = open(tmp, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) return -1;
    ok = write(fd, head, hn) == (int)hn && (!bn || write(fd, body, bn) == (int)bn) && fsync(fd) == 0;
    ok = (close(fd) == 0) && ok;
    if (!ok || rename(tmp, path) != 0) {
        unlink(tmp);
        return -1;
    }
    return 0;
}

static void pm_ring_load(void) {
    unsigned head[2];
    int fd;
    if (pm.loaded) return;
    pm.loaded = 1;
    pm.s = calloc(PC_RING_SLOTS, sizeof *pm.s);
    if (!pm.s) return;
    fd = open(PM_RING_FILE, O_RDONLY, 0);
    if (fd < 0) return;
    if (read(fd, head, 8) == 8 && head[0] == 0x31524350u && head[1] <= PC_RING_SLOTS && /* "PCR1" */
        read(fd, pm.s, head[1] * sizeof *pm.s) == (int)(head[1] * sizeof *pm.s))
        pm.n = head[1];
    close(fd);
}

void pc_flush(void) {
    unsigned head[2];
    if (!pm.dirty || !pm.s) return;
    head[0] = 0x31524350u, head[1] = pm.n;
    if (pm_save(PM_RING_FILE, PM_RING_TMP, head, 8, pm.s, pm.n * (unsigned)sizeof *pm.s) == 0)
        pm.dirty = 0; /* a failed write is tried again with the next change */
    pcs.save_ms = time_now_ms();
}

static int pm_find_slot(unsigned hash) {
    unsigned i;
    for (i = 0; i < pm.n; ++i)
        if (pm.s[i].hash == hash) return (int)i;
    return -1;
}

/* The slot of hash at the front of the ring (made if it is not there: the oldest goes when the ring is full). */
static slot_t *pm_front(unsigned hash, int create) {
    int at = pm_find_slot(hash);
    slot_t keep;
    if (at < 0 && !create) return (slot_t *)0;
    if (at < 0) {
        memset(&keep, 0, sizeof keep);
        keep.hash = hash;
        if (pm.n < PC_RING_SLOTS) ++pm.n;
        at = (int)pm.n - 1;
    } else
        memcpy(&keep, &pm.s[at], sizeof keep);
    if (at > 0) memmove(&pm.s[1], &pm.s[0], (unsigned)at * sizeof *pm.s);
    memcpy(&pm.s[0], &keep, sizeof keep);
    return &pm.s[0];
}

int pc_state(unsigned hash, unsigned *pos, unsigned *len) {
    int at;
    pm_ring_load();
    at = pm.s ? pm_find_slot(hash) : -1;
    *pos = *len = 0;
    if (at < 0) return PC_NEW;
    *pos = pm.s[at].pos, *len = pm.s[at].len;
    if (pm.s[at].flags & 1) return PC_DONE;
    return pm.s[at].pos ? PC_PROGRESS : PC_NEW;
}

unsigned pc_rev(void) { return pm.rev; }

/* The place of an episode seen at pos of len seconds: near its end it is played, near its start nothing is kept, else the place. */
static void pm_set(unsigned hash, unsigned pos, unsigned len) {
    slot_t *s;
    pm_ring_load();
    if (!pm.s) return;
    if (len && (pos + PC_EDGE_S >= len || pos * 100u >= len * 95u)) { /* played */
        s = pm_front(hash, 1);
        if (s->flags == 1 && !s->pos && s->len == len) return;
        s->pos = 0, s->flags = 1, s->len = len;
    } else if (
        pos <
        PC_EDGE_S) { /* the first seconds are not a place: nothing is saved (one saved before stays: a jump to it may be due, or the episode was only restarted) */
        return;
    } else {
        s = pm_front(hash, 1);
        if (s->pos == pos && s->len == len && !s->flags) return;
        s->pos = pos, s->len = len, s->flags = 0;
    }
    pm.dirty = 1;
    ++pm.rev;
}

void pc_mark(unsigned hash, int played) {
    int at;
    pm_ring_load();
    if (!pm.s) return;
    at = pm_find_slot(hash);
    if (played) {
        slot_t *s = pm_front(hash, 1);
        s->pos = 0, s->flags = 1;
    } else if (at >= 0) { /* new again: the slot goes */
        memmove(&pm.s[at], &pm.s[at + 1], (pm.n - (unsigned)at - 1) * sizeof *pm.s);
        --pm.n;
    } else
        return;
    pm.dirty = 1;
    ++pm.rev;
    pc_flush();
}

void pc_restart(unsigned hash) {
    int at;
    pm_ring_load();
    at = pm.s ? pm_find_slot(hash) : -1;
    if (at >= 0 && (pm.s[at].flags & 1)) pc_mark(hash, 0);
}

/* The episodes partly played, the most recently played first (the ring is kept in that order: every place noted moves its slot to the front): the Shows page's Continue Listening. The first PM_CONT_SCAN
 * places that are in progress (a place, not played) are looked for among the shows' files, one pc_load_show per show with a file, stopping when every candidate is found; one that is on no show
 * (its file is gone) is skipped. At most max items go to out. */
#define PM_CONT_SCAN 12
int pc_continue(const pc_show_t *shows, int nshows, pc_cont_t *out, int max) {
    pc_cont_t cand[PM_CONT_SCAN];
    char got[PM_CONT_SCAN];
    unsigned i, nc = 0, left;
    int s, k, n = 0;
    pc_ep_t *all;
    pm_ring_load();
    for (i = 0; pm.s && i < pm.n && nc < PM_CONT_SCAN; ++i) {
        const slot_t *t = &pm.s[i];
        if ((t->flags & 1) || !t->pos) continue;
        memset(&cand[nc], 0, sizeof cand[nc]);
        cand[nc].hash = t->hash, cand[nc].pos = t->pos, cand[nc].len = t->len;
        got[nc++] = 0;
    }
    if (!nc || max <= 0 || !(all = calloc(PC_MAX_EPS, sizeof *all))) return 0;
    left = nc;
    for (s = 0; s < nshows && left; ++s) {
        int cnt;
        if (!shows[s].count) continue;
        cnt = pc_load_show(&shows[s], all, PC_MAX_EPS);
        for (k = 0; k < cnt && left; ++k) {
            if (all[k].state != PC_LOCAL || !all[k].hash) continue;
            for (i = 0; i < nc; ++i)
                if (!got[i] && cand[i].hash == all[k].hash) {
                    got[i] = 1, --left;
                    cand[i].show = s;
                    pm_cpy(cand[i].file, PC_FILE, all[k].file);
                    pm_cpy(cand[i].title, PC_TITLE, all[k].title);
                }
        }
    }
    free(all);
    for (i = 0; i < nc && n < max; ++i)
        if (got[i]) memcpy(&out[n++], &cand[i], sizeof *out);
    return n;
}

/* ---------------------------------------------------------------------------
 * Speed per show
 */
static void pm_speed_load(void) {
    int fd;
    if (pm.sp_loaded) return;
    pm.sp_loaded = 1;
    fd = open(PM_SPEED_FILE, O_RDONLY, 0);
    if (fd < 0) return;
    {
        unsigned head[2];
        if (read(fd, head, 8) == 8 && head[0] == 0x31534350u && head[1] <= PC_SPEED_SLOTS && /* "PCS1" */
            read(fd, pm.sp + 2, head[1] * 8) == (int)(head[1] * 8)) {
            pm.sp[0] = head[0], pm.sp[1] = head[1];
        }
    }
    close(fd);
}

int pc_speed_get(unsigned show) {
    unsigned i;
    pm_speed_load();
    if (pm.sp[0] != 0x31534350u) return 0;
    for (i = 0; i < pm.sp[1]; ++i)
        if (pm.sp[2 + 2 * i] == show) return pm.sp[3 + 2 * i] < PC_SPEEDS ? (int)pm.sp[3 + 2 * i] : 0;
    return 0;
}

int pc_speed_set(unsigned show, int mode) {
    unsigned i, at;
    unsigned saved[2 + PC_SPEED_SLOTS * 2];
    if (mode < 0 || mode >= PC_SPEEDS || !show) return 0;
    pm_speed_load();
    memcpy(saved, pm.sp, sizeof saved);
    if (pm.sp[0] != 0x31534350u) pm.sp[0] = 0x31534350u, pm.sp[1] = 0;
    for (at = 0; at < pm.sp[1] && pm.sp[2 + 2 * at] != show; ++at) {
    }
    if (at == pm.sp[1]) { /* a new show: the oldest goes when the table is full */
        if (pm.sp[1] < PC_SPEED_SLOTS)
            ++pm.sp[1];
        else
            for (i = 1; i < pm.sp[1]; ++i)
                pm.sp[2 + 2 * (i - 1)] = pm.sp[2 + 2 * i], pm.sp[3 + 2 * (i - 1)] = pm.sp[3 + 2 * i];
        at = pm.sp[1] - 1;
    }
    pm.sp[2 + 2 * at] = show, pm.sp[3 + 2 * at] = (unsigned)mode;
    if (pm_save(PM_SPEED_FILE, PM_SPEED_TMP, pm.sp, 8, pm.sp + 2, pm.sp[1] * 8) == 0) return 1;
    memcpy(pm.sp, saved, sizeof saved); /* not saved: the old table stays */
    return 0;
}

void pc_speed_apply(unsigned show) {
    int mode = pc_speed_get(show), cur = *(volatile int *)PLAYSPEED_MODE;
    if (!pcs.speed_on) pcs.orig = cur;
    if (mode != cur) {
        *(volatile int *)PLAYSPEED_MODE =
            mode; /* what the stock Multiple Speed page shows and config_mplayer sends at the next player set-up */
        mclSetPlaySpeed(mode);
    }
    pcs.speed_on = mode != pcs.orig;
    pcs.apply_ms = time_now_ms();
}

static void pm_speed_back(void) {
    if (!pcs.speed_on) return;
    pcs.speed_on = 0;
    *(volatile int *)PLAYSPEED_MODE = pcs.orig;
    mclSetPlaySpeed(pcs.orig);
}

/* ---------------------------------------------------------------------------
 * The tag reader's hook (the one hook of Podcasts; docs/modules/podcasts.md "Tags"). Stock get_id3info (0x4dfd58) fills playsong_id3info (0xa0d88c: album +0x404, artist
 * +0x504, title +0x684) from the FILE'S TAGS (toolsGetMusicInfo 0x5ec6a8, taglib; the record's own strings are used only when the CUE flag is set), then copies the parsed path
 * into the struct's cache key (`jalr strcpy` at 0x4dff4c) and, after it, builds song_name / song_artist from the struct: an empty title becomes the file name, an empty
 * artist "Unknown". Every fresh parse passes that strcpy. It is replaced by `jal pc_id3_path` (q2-pod's ID3_PATH, tools/build.py, ringnav_id3_path): the delay slot still loads
 * a1 = the record's path, a0 = the struct, s0 = the record. The function does exactly stock's strcpy and then, for a path under /mnt/mmc/Podcasts/ only, puts the episode and the
 * show where the tags were; stock's own code after the site copies them to song_name / song_artist, Now Playing and the mini bar show them.
 * Reachable at boot (Memory Playback starts a track): so a plain path costs the copy and one prefix test, and the kill switch is looked at only for a podcast path.
 */
static int pm_empty_or_unknown(const char *s) { return !*s || pm_eq(s, "Unknown"); }

__attribute__((noinline)) char *pc_id3_path(char *info, const char *path) {
    char *title = info + 0x684, *artist = info + 0x504, *album = info + 0x404, show[PC_FILE];
    void *rec;
    const char *s, *p;
    unsigned n = 0;
    while (n < 0x3ff && path[n])
        info[n] = path[n], ++n; /* stock: strcpy(info, path); the field is 0x400 bytes (the CUE start follows it) */
    info[n] = 0;
    if (!pc_is_path(path) || home_off()) return info;
    p = path + sizeof PM_ROOT "/podcasts/" - 1;
    for (n = 0; p[n] != '/'; ++n) {
    }
    pm_cpy_n(show, sizeof show, p, (int)n);
    rec = cc_playing();
    if (rec && !pm_eq(cc_str(rec, REC_PATH), path))
        rec = (void *)0; /* (the record get_id3info read is the playing one; anything else is not trusted) */
    s = rec ? cc_str(rec, REC_ARTIST) : "";
    if (rec && *cc_str(rec, REC_TITLE) &&
        !pm_empty_or_unknown(s)) { /* our own record: the episode title from .episodes (else the file name), the show */
        pm_cpy(title, 0x200, cc_str(rec, REC_TITLE));
        pm_cpy(artist, 0x100, s);
        s = cc_str(rec, REC_ALBUM);
        pm_cpy(album, 0x100, *s ? s : artist);
        return info;
    }
    if (pm_empty_or_unknown(artist))
        pm_cpy(artist, 0x100, show); /* the tags as stock had them, the show for what they lack */
    if (!*album) pm_cpy(album, 0x100, artist);
    return info;
}

/* ---------------------------------------------------------------------------
 * The timer hook
 */

/* The episode that was playing is over (the track changed or stopped): what was last seen is its place; near the end it is played. */
static void pm_leave(void) {
    if (pcs.len > 0 && !pcs.pend) pm_set(pcs.cur, (unsigned)pcs.pos, (unsigned)pcs.len);
    pc_flush();
}

void pc_note(void *t) {
    const char *path = t ? cc_str(t, REC_PATH) : "";
    unsigned h = pc_is_path(path) ? pc_hash(path) : 0, now;
    int pos = 0, len = 0;
    if (!h && !pcs.cur && !pcs.speed_on) return; /* music, as before: nothing to look at */
    now = time_now_ms();
    if (h != pcs.cur) {
        if (pcs.cur) pm_leave();
        pcs.cur = h, pcs.pos = pcs.len = 0, pcs.pend = 0;
        if (h) {
            unsigned p, l;
            pc_speed_apply(pc_show_of(path));
            if (pc_state(h, &p, &l) == PC_PROGRESS && p >= PC_EDGE_S) pcs.pend = 1, pcs.pend_pos = p, pcs.pend_ms = now;
        }
    }
    if (!h) { /* music again: the speed we changed goes back, unless the page has just set one for an episode that has not started yet */
        if (pcs.speed_on && now - pcs.apply_ms > PC_SEEK_WAIT_MS) pm_speed_back();
        return;
    }
    if (get_playtimeandlength(&pos, &len) != 1 || len <= 0 || pos < 0) return;
    if (pcs.pend) { /* the saved place: jump to it once, while the episode has just started and plays; meanwhile nothing is recorded (the first seconds would forget it) */
        if (now - pcs.pend_ms > PC_SEEK_WAIT_MS || (unsigned)pos >= pcs.pend_pos)
            pcs.pend = 0;
        else if (pos >= 1 && pos < PC_SEEK_MAX && mclGetPlayStatus() == MB_PLAYING) {
            seek_time((int)pcs.pend_pos);
            pcs.pend = 0;
            pcs.hold_ms = now + 2000;
        }
        if (pcs.pend) return;
    }
    if (pcs.hold_ms && (int)(now - pcs.hold_ms) < 0)
        return; /* just jumped: the player's second may still be the old one */
    pcs.hold_ms = 0;
    pcs.pos = pos, pcs.len = len;
    pm_set(h, (unsigned)pos, (unsigned)len);
    if (pm.dirty && (now - pcs.save_ms >= PC_SAVE_MS || mclGetPlayStatus() != MB_PLAYING)) pc_flush();
}

/* ---------------------------------------------------------------------------
 * Shuffle: a queue without the podcast files
 */
void *pc_strip(void *queue, int *idx) {
    unsigned n = queue ? deque_size(queue) : 0, i, any = 0;
    void *out;
    int at = -1;
    for (i = 0; i < n; ++i) any += pc_is_path(cc_str(deque_at(queue, i), REC_PATH));
    if (!any) return queue;
    out = _create_deque("stSongInfo");
    if (out) {
        deque_init(out);
        for (i = 0; i < n; ++i) {
            void *r = deque_at(queue, i);
            if (pc_is_path(cc_str(r, REC_PATH))) continue;
            if (at < 0 && (int)i >= *idx) at = (int)deque_size(out);
            _deque_push_back(out, r);
        }
        if (at < 0 && deque_size(out)) at = 0;
    }
    deque_destroy(queue);
    if (out && at < 0) {
        deque_destroy(out);
        out = (void *)0;
    }
    *idx = at < 0 ? 0 : at;
    return out;
}

/* ---------------------------------------------------------------------------
 * The Library query filter (docs/modules/payload.md hook 6). Every Library list (Songs, Albums, Artists, Genres, Composers, Hi-Res, Recently Added, the search, an album's and an
 * artist's songs, Cover Flow's source, Memory Playback's queue) is a `select ... from songtable ...` that stock formats with sprintf and runs through toolsQueryDbTable (0x5ee77c) or
 * toolsQueryDbTableAndSort (0x5ee9ac, the Songs title sorts). Both prologues are hooked (q2-pod's dbquery / sorted_query, ringnav_library_query); the table is replaced by a
 * filtered subquery BEFORE stock's grouping, so an album shared by music and an episode keeps the music row (its artwork) and untagged episodes add no Unknown rows. The filter is
 * on for every such query (q2-pod scopes it with a flag because its Cover Flow and Folders also read songtable; here nothing needs the episodes: our Podcasts pages and Folder play
 * list directories, the other tables (myfav, the recents, the playlists) are not songtable, and the scan's duplicate check is its own sqlite3_exec). The path test is SQLite's LIKE (case
 * insensitive for ASCII), bounded by the slash: '/mnt/mmc/Podcasts Extra/' and '/mnt/mmc/Music/Podcasts/' stay. Anything that is not a plain songtable select, or does not fit, goes to stock
 * untouched; no file I/O, no allocation, a 1 KB buffer on the caller's stack. The subquery is also ordered so an album is its first track (below).
 */
#define PQ_BUF 1024
static const char pq_head[] =
    " from (select * from songtable where ifnull(fileurl,'') not like '" PM_ROOT "/podcasts/%'";
/* An album is its first track: lowest track number, an untagged one (NULL or <= 0) after the tagged, then the lowest path. */
static const char pq_first[] = " order by (ifnull(track,0)<=0), ifnull(track,0), fileurl)";
/* The same order reversed, for `group by album`: SQLite 3.19.3 (the device's) gives a GROUP BY's bare columns (id, songer, fileurl) the LAST row of the group in the
 * order its input arrives (verified with the 3.19.3 amalgamation; SQLite 3.54's sorter takes the first, so this is implementation behaviour, pinned by the device's SQLite). */
static const char pq_last[] = " order by (ifnull(track,0)<=0) desc, ifnull(track,0) desc, fileurl desc)";

/* The Favourites list (getAllFav, 0x4ec45c: exactly "select * from myfav") is music only; the Saved page (patch/podcasts.c) asks for the same statement with pc_saved_scope set around its
 * loadLocalClassList(0xf00a) and gets the episodes only, the last saved first. Stock's own star adds and removes the episodes (myfav), so Saved is a view of that table. */
unsigned char pc_saved_scope __attribute__((section(".scratch")));
static const char pq_fav_sql[] = "select * from myfav";
static const char pq_fav_music[] = "select * from myfav where ifnull(fileurl,'') not like '" PM_ROOT "/podcasts/%'";
static const char pq_fav_saved[] =
    "select * from myfav where ifnull(fileurl,'') like '" PM_ROOT "/podcasts/%' order by id desc";

/* The end of the first pat in sql when the next character is not an s (albumsonger is not album); 0 when there is none */
static const char *pq_find(const char *sql, const char *pat) {
    unsigned i, n;
    for (n = 0; sql[n]; ++n) {
        for (i = 0; pat[i] && sql[n + i] == pat[i]; ++i) {
        }
        if (!pat[i] && sql[n + i] != 's') return sql + n + i;
    }
    return 0;
}

/* sql with " from songtable" replaced by the filtered subquery, in out; 0 when sql is not such a select or does not fit. An album list (`group by album`) gets the subquery
 * ordered so the row SQLite keeps per album is its first track; an album's own tracks (`where album ...`) come in track order, so the first is the album's first track. The Favourites statement is
 * replaced whole (above). */
static char *pq_filter(char *out, const char *sql) {
    static const char tbl[] = " from songtable", sel[] = "select ";
    unsigned i, n, m = sizeof pq_head - 1, t, len;
    const char *tail, *rest;
    if (!sql) return 0;
    for (i = 0; i < sizeof pq_fav_sql && sql[i] == pq_fav_sql[i]; ++i) {
    }
    if (i == sizeof pq_fav_sql) {
        if (pc_saved_scope)
            memcpy(out, pq_fav_saved, sizeof pq_fav_saved);
        else
            memcpy(out, pq_fav_music, sizeof pq_fav_music);
        return out;
    }
    for (i = 0; i < sizeof sel - 1; ++i)
        if (sql[i] != sel[i]) return 0;
    for (n = 0; sql[n]; ++n) {
        for (i = 0; i < sizeof tbl - 1 && sql[n + i] == tbl[i]; ++i) {
        }
        if (i == sizeof tbl - 1 && (sql[n + i] == 0 || sql[n + i] == ' ' || sql[n + i] == ';')) break;
    }
    if (!sql[n]) return 0;
    len = pm_len(sql);
    if (len - (sizeof tbl - 1) + m + sizeof pq_last > PQ_BUF)
        return 0; /* fits with the longest tail (its size counts the NUL) */
    rest = sql + n + sizeof tbl - 1;
    tail = pq_find(rest, "group by album") ? pq_last : pq_find(rest, " where album") ? pq_first : ")";
    t = pm_len(tail);
    memcpy(out, sql, n);
    memcpy(out + n, pq_head, m);
    memcpy(out + n + m, tail, t);
    memcpy(out + n + m + t, sql + n + sizeof tbl - 1, len - n - (sizeof tbl - 1) + 1);
    return out;
}

__attribute__((noinline)) int pc_library_query(const char *db, const char *sql, void *row, int sort) {
    char buf[PQ_BUF];
    const char *s = pq_filter(buf, sql);
    return stock_dbquery_trampoline(db, s ? s : sql, row, sort);
}

__attribute__((noinline)) int pc_sorted_query(const char *db, const char *sql, void *row, int sort) {
    char buf[PQ_BUF];
    const char *s = pq_filter(buf, sql);
    return stock_sorted_query_trampoline(db, s ? s : sql, row, sort);
}
