/* Navidrome downloads (docs/modules/subsonic.md "Data and cache", "File split"): ONE detached download worker, a queue whose rows wait on the card (dlq.idx), the manifest dl.idx of finished downloads and the
 * target files in SBA_MUSIC_DIR. The pages never block here: sba_dl_add queues a track and returns, the worker writes the file (sbn_download: a .part file, a Range resume, the PR's
 * stall limit of 512 B/s for 45 s and the 32 MB free-space floor), appends the manifest row, and the page's timer reads sba_dl_gen / sba_dl_state.
 * The worker never calls AWTK; the stock functions it calls are the library scan of a finished album's folder (scanSpecFolder, as the PR does after a DSD file) and, through sba_guard at the start of a download, get_wifisignal (the Wi-Fi check; sba_configured reads the saved login).
 *
 * The manifest holds the track's whole row (title, artist, album, suffix, ...) plus the file name, so Downloaded works offline and with the server gone. It is a text file, one
 * track a line of tab-separated key=value fields (the keys are in sbd_row_text), replaced whole and atomically; a torn or odd line is skipped. A copy of (id, file, size, DSD)
 * stays in memory after the first use so that painting a row's state never touches the card; a file that was deleted by hand is found out (and dropped) when the path or the
 * list is asked for.
 *
 * Locks: sbd.lock guards the memory (queue, index) and is held for a few instructions only, never across a call; sbd.mf serialises the writers of dl.idx (it is held across the
 * file work, and a waiting UI thread sleeps 1 ms at a time). Order: mf, then lock.
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "curlopts.h"
#include "sbapi.h"
#include "sbnet.h"
#include "fnv.h"

extern int pn_free_kb(const char *path, unsigned *kb);

#define SBD_IDX SBA_DIR "/dl.idx"
#define SBD_IDX_TMP SBA_DIR "/dl.idx.tmp"
#define SBD_HEAD "M1PLUS-DL 1\n"
#define SBD_Q \
    SBA_DIR "/dlq.idx" /* the waiting downloads: a manifest line a track (no file name yet), appended by an add */
#define SBD_Q_TMP SBA_DIR "/dlq.idx.tmp"
#define SBD_FILE 288 /* a file's path under SBA_MUSIC_DIR (artist/album/name), the NUL included */
#define SBD_PATH 336 /* a full path, the ".part" included */
#define SBD_PART 64 /* bytes of an artist or album folder name */
#define SBD_LINE 1600 /* a manifest line (the longest is about 1100 bytes) */
#define SBD_IDX_MAX (4u << 20) /* a manifest larger than this is read as empty rather than loaded */
#define SBD_ROWS 8000 /* entries kept in memory */
#define SBD_FAIL_FRESH_S 30 /* a failure older than this is not announced */
#define SBD_TITLE 100 /* bytes of the title in a file name */

typedef struct {
    char id[SBA_ID];
    char file[SBD_FILE];
    unsigned size;
    unsigned char dsd;
} sbd_ent_t;

typedef struct {
    char id[SBA_ID];
    unsigned char state; /* 0 free, else SBA_DL_WAIT / ACTIVE / FAILED */
    int code;
    unsigned seq;
} sbd_slot_t; /* (the track's row waits in dlq.idx: the worker reads it when its turn comes) */

/* Writable state lives in .scratch (the payload has no .bss). */
static struct {
    volatile int lock, mf, qf;
    int busy, loaded, qloaded, stop,
        again; /* again: the active track's cancel was withdrawn by an add (sba_dl_add); if the transfer had obeyed the cancel already, the worker puts the track back in line */
    int qbad; /* dlq.idx was there and could not be read whole: no queue is loaded, the next use reads again */
    int status; /* the HTTP status of the last failed transfer (the worker writes it before it reports the failure) */
    int fail_code, fail_status; /* the newest failure nobody has been told of (0 none) */
    long fail_at; /* when it happened (time(), seconds) */
    unsigned seq, gen, got, total, step;
    sbn_sink_t *sink; /* the active transfer's sink: sba_dl_xfer answers only for it */
    sbd_slot_t *q; /* SBA_DLMAX slots, made at the first use (NULL: no memory, nothing queues) */
    sbd_ent_t *ix;
    int nix, capix;
    char al_id[SBA_ID], al_artist[SBA_TEXT]; /* the worker's last album artist lookup */
} sbd __attribute__((section(".scratch")));

static void sbd_lock(void) {
    while (__sync_lock_test_and_set(&sbd.lock, 1)) {
    }
}
static void sbd_unlock(void) { __sync_lock_release(&sbd.lock); }
static void sbd_mf_lock(void) {
    while (__sync_lock_test_and_set(&sbd.mf, 1)) usleep(1000);
}
static void sbd_mf_unlock(void) { __sync_lock_release(&sbd.mf); }
static void sbd_qf_lock(void) {
    while (__sync_lock_test_and_set(&sbd.qf, 1)) usleep(1000);
}
static void sbd_qf_unlock(void) { __sync_lock_release(&sbd.qf); }
static void sbd_bump(void) {
    __sync_synchronize();
    __sync_add_and_fetch(&sbd.gen, 1);
}

/* ---- small string helpers (the payload has no libc string set beyond the few stock.h declares) ---- */

static unsigned sbd_len(const char *s) { return sbn_len(s); }

static int sbd_same(const char *a, const char *b) { return strcmp(a, b) == 0; }

/* Two file names that are one file on the card: exFAT and FAT fold the case, so "03 Song One.flac" and "03 SONG ONE.flac" are the same file. The ASCII letters only: this is the cheap
 * first answer; the card folds every script, and sbd_shared asks the card itself before a file is adopted. */
static int sbd_same_file(const char *a, const char *b) {
    for (;; ++a, ++b) {
        unsigned x = (unsigned char)*a, y = (unsigned char)*b;
        if (x >= 'A' && x <= 'Z') x += 32;
        if (y >= 'A' && y <= 'Z') y += 32;
        if (x != y) return 0;
        if (!x) return 1;
    }
}

static void sbd_set(char *dst, unsigned cap, const char *src) {
    unsigned n = sbd_len(src);
    if (n >= cap) n = cap - 1;
    memcpy(dst, src, n);
    dst[n] = 0;
}

/* ---- manifest rows ---- */

/* Append "<key>=<value>" to line at *n (a tab first unless it is the first field). */
static void sbd_put_s(char *line, unsigned cap, unsigned *n, char key, const char *v) {
    unsigned i = 0;
    if (*n + 4 >= cap) return;
    if (*n) line[(*n)++] = '\t';
    line[(*n)++] = key;
    line[(*n)++] = '=';
    while (v[i] && *n + 2 < cap) {
        unsigned char c = (unsigned char)v[i++];
        line[(*n)++] = c < 32 ? ' ' : (char)c;
    }
    line[*n] = 0;
}

static void sbd_put_u(char *line, unsigned cap, unsigned *n, char key, unsigned v) {
    char d[12];
    unsigned k = 0;
    if (!v) d[k++] = '0';
    while (v) d[k++] = (char)('0' + v % 10), v /= 10;
    {
        char out[12];
        unsigned i;
        for (i = 0; i < k; ++i) out[i] = d[k - 1 - i];
        out[k] = 0;
        sbd_put_s(line, cap, n, key, out);
    }
}

/* One manifest line (no newline) for track t stored in file with fsize bytes. Returns its length. */
static unsigned sbd_row_text(char *line, unsigned cap, const sba_track_t *t, const char *file, unsigned fsize) {
    unsigned n = 0;
    line[0] = 0;
    sbd_put_s(line, cap, &n, 'i', t->id);
    sbd_put_s(line, cap, &n, 't', t->title);
    sbd_put_s(line, cap, &n, 'a', t->artist);
    sbd_put_s(line, cap, &n, 'l', t->album);
    sbd_put_s(line, cap, &n, 'b', t->album_id);
    sbd_put_s(line, cap, &n, 'c', t->cover);
    sbd_put_s(line, cap, &n, 'x', t->suffix);
    sbd_put_u(line, cap, &n, 's', t->seconds);
    sbd_put_u(line, cap, &n, 'n', t->track);
    sbd_put_u(line, cap, &n, 'd', t->disc);
    sbd_put_u(line, cap, &n, 'y', t->year);
    sbd_put_u(line, cap, &n, 'z', t->size);
    sbd_put_u(line, cap, &n, 'r', t->bitrate);
    sbd_put_u(line, cap, &n, 'h', t->sample_rate);
    sbd_put_u(line, cap, &n, 'q', t->bit_depth);
    sbd_put_u(line, cap, &n, 'm', t->created);
    sbd_put_u(line, cap, &n, 'f', t->starred);
    sbd_put_u(line, cap, &n, 'w', fsize);
    sbd_put_s(line, cap, &n, 'p', file);
    return n;
}

/* The value of field key in the line [p, end): copied to out (cap), 1 when present. */
static int sbd_field(const char *p, const char *end, char key, char *out, unsigned cap) {
    const char *f = p;
    while (f < end) {
        const char *e = f;
        while (e < end && *e != '\t') ++e;
        if (e - f >= 2 && f[0] == key && f[1] == '=') {
            unsigned n = (unsigned)(e - f - 2);
            if (n >= cap) n = cap - 1;
            memcpy(out, f + 2, n);
            out[n] = 0;
            return 1;
        }
        f = e + 1;
    }
    out[0] = 0;
    return 0;
}

static unsigned sbd_num(const char *p, const char *end, char key) {
    char v[16];
    unsigned r = 0, i;
    sbd_field(p, end, key, v, sizeof v);
    for (i = 0; v[i] >= '0' && v[i] <= '9'; ++i) r = r * 10 + (unsigned)(v[i] - '0');
    return r;
}

/* Parse a line into t / file / fsize; 0 when it has no id. file is "" for a row of the waiting queue (the manifest's readers check it). */
static int sbd_parse_row(const char *p, const char *end, sba_track_t *t, char *file, unsigned fcap, unsigned *fsize) {
    memset(t, 0, sizeof *t);
    if (!sbd_field(p, end, 'i', t->id, sizeof t->id) || !t->id[0]) return 0;
    sbd_field(p, end, 'p', file, fcap);
    sbd_field(p, end, 't', t->title, sizeof t->title);
    sbd_field(p, end, 'a', t->artist, sizeof t->artist);
    sbd_field(p, end, 'l', t->album, sizeof t->album);
    sbd_field(p, end, 'b', t->album_id, sizeof t->album_id);
    sbd_field(p, end, 'c', t->cover, sizeof t->cover);
    sbd_field(p, end, 'x', t->suffix, sizeof t->suffix);
    t->seconds = sbd_num(p, end, 's');
    t->track = sbd_num(p, end, 'n');
    t->disc = sbd_num(p, end, 'd');
    t->year = sbd_num(p, end, 'y');
    t->size = sbd_num(p, end, 'z');
    t->bitrate = sbd_num(p, end, 'r');
    t->sample_rate = sbd_num(p, end, 'h');
    t->bit_depth = sbd_num(p, end, 'q');
    t->created = sbd_num(p, end, 'm');
    t->starred = (unsigned char)(sbd_num(p, end, 'f') != 0);
    *fsize = sbd_num(p, end, 'w');
    return 1;
}

/* A file is a path inside SBA_MUSIC_DIR: plain names joined by '/', none empty and none starting with a dot (the manifest is a file on the card: never follow a path out of the folder). */
static int sbd_file_ok(const char *f) {
    unsigned i;
    if (!f[0]) return 0;
    for (i = 0; f[i]; ++i) {
        if (f[i] == '\\') return 0;
        if ((!i || f[i - 1] == '/') && (f[i] == '.' || f[i] == '/')) return 0;
    }
    return f[i - 1] != '/';
}

static int sbd_path(char *out, unsigned cap, const char *file) {
    int k = snprintf(out, cap, "%s/%s", SBA_MUSIC_DIR, file);
    return k > 0 && (unsigned)k < cap;
}

/* The folder a file is in (SBA_MUSIC_DIR itself for a name with no folder). */
static int sbd_dir(char *out, unsigned cap, const char *file) {
    const char *cut = strrchr(file, '/');
    int k = cut ? snprintf(out, cap, "%s/%s", SBA_MUSIC_DIR, file) : snprintf(out, cap, "%s", SBA_MUSIC_DIR);
    if (k <= 0 || (unsigned)k >= cap) return 0;
    if (cut) out[sizeof SBA_MUSIC_DIR + (unsigned)(cut - file)] = 0;
    return 1;
}

/* Make the folders of a file (an existing one is fine; a failure shows when the file is opened). */
static void sbd_mkdirs(const char *file) {
    char path[SBD_PATH];
    unsigned i, base = sizeof SBA_MUSIC_DIR; /* the index after "SBA_MUSIC_DIR/" */
    mkdir("/mnt/mmc/.m1plus", 0755);
    mkdir(SBA_MUSIC_DIR, 0775);
    if (!sbd_path(path, sizeof path, file)) return;
    for (i = base; path[i]; ++i)
        if (path[i] == '/') {
            path[i] = 0;
            mkdir(path, 0775);
            path[i] = '/';
        }
}

/* After a delete: the album and artist folders go when they are empty (rmdir refuses a folder with files). */
static void sbd_rmdirs(const char *file) {
    char path[SBD_PATH];
    unsigned n, base = sizeof SBA_MUSIC_DIR;
    if (!sbd_path(path, sizeof path, file)) return;
    for (n = sbd_len(path); n > base; --n)
        if (path[n] == '/') {
            path[n] = 0;
            if (rmdir(path) != 0) return;
        }
}

static int sbd_exists(const char *file) {
    char path[SBD_PATH];
    return sbd_file_ok(file) && sbd_path(path, sizeof path, file) && access(path, 0) == 0;
}

/* ---- reading and writing dl.idx ---- */

/* The whole file in a heap buffer (NUL terminated); NULL when it is missing, empty or too large. */
/* A whole file as text (NULL for none, an empty or an oversized one). *bad, when asked for, is 1 when the file is there and was not read whole (it would not open, no memory, a read that
 * failed or came short): what was read is then no word on what the file holds. */
static char *sbd_slurp_st(const char *path, unsigned *n, int *bad) {
    int fd = open(path, O_RDONLY, 0);
    long size;
    char *buf;
    unsigned got = 0;
    *n = 0;
    if (bad) *bad = 0;
    if (fd < 0) {
        if (bad) *bad = access(path, 0) == 0;
        return (char *)0;
    }
    size = lseek(fd, 0, 2);
    if (size <= 0 || (unsigned long)size > SBD_IDX_MAX || lseek(fd, 0, 0) < 0 ||
        !(buf = (char *)calloc((unsigned)size + 1, 1))) {
        if (bad) *bad = size < 0 || (size > 0 && (unsigned long)size <= SBD_IDX_MAX);
        close(fd);
        return (char *)0;
    }
    while (got < (unsigned)size) {
        int r = read(fd, buf + got, (unsigned)size - got);
        if (r <= 0) break;
        got += (unsigned)r;
    }
    close(fd);
    if (bad) *bad = got < (unsigned)size;
    buf[got] = 0;
    *n = got;
    return buf;
}

static char *sbd_slurp(const char *path, unsigned *n) { return sbd_slurp_st(path, n, (int *)0); }

/* 1 when the file exists and is larger than SBD_IDX_MAX (sbd_slurp reads it as empty). */
static int sbd_oversized(const char *path) {
    int fd = open(path, O_RDONLY, 0);
    long size;
    if (fd < 0) return 0;
    size = lseek(fd, 0, 2);
    close(fd);
    return size > 0 && (unsigned long)size > SBD_IDX_MAX;
}

/* The next line of [*p, end): its bounds without the newline; moves *p past it. 0 at the end. */
static int sbd_next(const char **p, const char *end, const char **ls, const char **le) {
    const char *s = *p, *e;
    if (s >= end) return 0;
    e = s;
    while (e < end && *e != '\n') ++e;
    *ls = s;
    *le = e;
    *p = e < end ? e + 1 : e;
    return 1;
}

/* Build an in-memory index from manifest text and swap it in. The caller holds mf. */
static void sbd_ix_set(const char *text, unsigned n) {
    sbd_ent_t *ix = (sbd_ent_t *)0, *old;
    int cnt = 0, cap = 0;
    const char *p = text, *end = text + n, *ls, *le;
    sba_track_t *t = (sba_track_t *)calloc(1, sizeof *t);
    if (t && n) {
        unsigned lines = 0, i;
        for (i = 0; i < n; ++i) lines += text[i] == '\n';
        cap = (int)(lines + 1 > SBD_ROWS ? SBD_ROWS : lines + 1);
        ix = (sbd_ent_t *)calloc((unsigned)cap, sizeof *ix);
        if (!ix) cap = 0;
        while (ix && sbd_next(&p, end, &ls, &le)) {
            char file[SBD_FILE];
            unsigned fsize;
            if (le - ls < 4 || ls[0] != 'i' || ls[1] != '=' || !sbd_parse_row(ls, le, t, file, sizeof file, &fsize) ||
                !sbd_file_ok(file))
                continue;
            if (cnt >= cap) break;
            sbd_set(ix[cnt].id, sizeof ix[cnt].id, t->id);
            sbd_set(ix[cnt].file, sizeof ix[cnt].file, file);
            ix[cnt].size = fsize;
            ix[cnt].dsd = (unsigned char)sba_is_dsd(t->suffix);
            ++cnt;
        }
    }
    free(t);
    sbd_lock();
    old = sbd.ix;
    sbd.ix = ix;
    sbd.nix = cnt;
    sbd.capix = cap;
    sbd.loaded = 1;
    sbd_unlock();
    free(old);
    sbd_bump();
}

static void sbd_load_locked(void) {
    unsigned n = 0;
    char *text = sbd_slurp(SBD_IDX, &n);
    sbd_ix_set(text ? text : "", text ? n : 0);
    free(text);
}

/* The index is loaded on first use. */
static void sbd_q_load(void);
static void sbd_ensure(void) {
    if (sbd.loaded && sbd.qloaded) return;
    sbd_mf_lock();
    if (!sbd.loaded) sbd_load_locked();
    if (!sbd.qloaded && m1_card_mounted())
        sbd_q_load(); /* (after the index: a waiting row of a downloaded track is not queued again; not while the card is out, when the queue would read as empty for the whole run) */
    sbd_mf_unlock();
}

/* Rewrite dl.idx without the rows of remove_id and with row (a manifest line; NULL for none) added. 1 on success. Takes mf. */
static int sbd_edit(const char *remove_id, const char *row) {
    unsigned n = 0, out = 0, rn = row ? sbd_len(row) : 0;
    char *text, *buf, row_id[SBA_ID];
    const char *p, *end, *ls, *le;
    int ok;
    row_id[0] = 0;
    if (row) sbd_field(row, row + rn, 'i', row_id, sizeof row_id);
    sbd_mf_lock();
    if (sbd_oversized(SBD_IDX)) { /* never overwrite a manifest that cannot be read back */
        sbd_mf_unlock();
        return 0;
    }
    text = sbd_slurp(SBD_IDX, &n);
    buf = (char *)calloc(n + rn + sizeof SBD_HEAD + 4, 1);
    if (!buf) {
        free(text);
        sbd_mf_unlock();
        return 0;
    }
    memcpy(buf, SBD_HEAD, sizeof SBD_HEAD - 1);
    out = sizeof SBD_HEAD - 1;
    p = text ? text : "";
    end = p + n;
    while (sbd_next(&p, end, &ls, &le)) {
        char id[SBA_ID];
        if (le - ls < 4 || ls[0] != 'i' || ls[1] != '=') continue; /* the head line, blank or odd lines go */
        if (remove_id && sbd_field(ls, le, 'i', id, sizeof id) && sbd_same(id, remove_id)) continue;
        if (row_id[0] && sbd_field(ls, le, 'i', id, sizeof id) && sbd_same(id, row_id))
            continue; /* the row being added replaces an older one of the same track */
        memcpy(buf + out, ls, (unsigned)(le - ls));
        out += (unsigned)(le - ls);
        buf[out++] = '\n';
    }
    if (row) {
        memcpy(buf + out, row, rn);
        out += rn;
        buf[out++] = '\n';
    }
    ok = m1_card_write(SBA_DIR, SBD_IDX, SBD_IDX_TMP, buf, out, (const void *)0, 0) == 0;
    if (ok) sbd_ix_set(buf, out);
    free(buf);
    free(text);
    sbd_mf_unlock();
    return ok;
}

/* The index entry of a track, copied out (the array can move). 1 found. */
static int sbd_find(const char *id, sbd_ent_t *out) {
    int i, r = 0;
    sbd_ensure();
    sbd_lock();
    for (i = 0; i < sbd.nix; ++i)
        if (sbd_same(sbd.ix[i].id, id)) {
            memcpy(
                out, &sbd.ix[i],
                sizeof *out); /* (no struct assignment: the compiler would call a memcpy the payload does not have) */
            r = 1;
            break;
        }
    sbd_unlock();
    return r;
}

/* The index entry that owns a file name (a name collision between two tracks), compared as the card compares names. */
static int sbd_owner(const char *file, char *id, unsigned cap) {
    int i, r = 0;
    sbd_lock();
    for (i = 0; i < sbd.nix; ++i)
        if (sbd_same_file(sbd.ix[i].file, file)) {
            sbd_set(id, cap, sbd.ix[i].id);
            r = 1;
            break;
        }
    sbd_unlock();
    return r;
}

/* The card's own word on which file a path is (st_dev, st_ino; struct stat of this ABI has them at 0 and 0x10). */
static int sbd_ident(const char *path, unsigned *dev, unsigned *ino) {
    unsigned s[40];
    memset(s, 0, sizeof s);
    if (__xstat(3, path, s) != 0) return 0;
    *dev = s[0], *ino = s[0x10 / 4];
    return 1;
}

/* 1 when the file at `final` is the file of another track of the manifest, by the card and not by the names: exFAT and FAT fold the case of every script with a table of the card's own
 * ("Café.flac" and "CAFÉ.flac" are one file), so two names prove nothing; one inode does. The file is held open meanwhile, so its inode keeps its number. A file that cannot be told
 * (it will not open or stat) counts as shared: it is not adopted. Worker. */
static int sbd_shared(const char *final, const char *id) {
    int fd = open(final, O_RDONLY, 0), i, r = 0;
    unsigned d0, i0, d, k;
    char rel[SBD_FILE], full[SBD_PATH];
    if (fd < 0) return 1;
    if (!sbd_ident(final, &d0, &i0)) r = 1;
    for (i = 0; !r; ++i) {
        int have, other = 0;
        sbd_lock();
        have = i < sbd.nix;
        if (have) {
            other = !sbd_same(sbd.ix[i].id, id);
            sbd_set(rel, sizeof rel, sbd.ix[i].file);
        }
        sbd_unlock();
        if (!have) break;
        if (other && sbd_path(full, sizeof full, rel) && sbd_ident(full, &d, &k) && d == d0 && k == i0) r = 1;
    }
    close(fd);
    return r;
}

/* ---- the file of a track: <artist>/<album>/<nn> <title>.<suffix> under SBA_MUSIC_DIR ---- */

/* A folder or file name from tag text: at most max bytes (cut at a character), control characters and the ones FAT refuses as '_', no leading dot, no leading or trailing space, no
 * trailing dot; `empty` when nothing is left. out holds max + 1 bytes and no less than empty. */
static void sbd_clean(char *out, const char *s, unsigned max, const char *empty) {
    unsigned i, n = 0;
    while (*s == ' ') ++s;
    for (i = 0; s[i] && n < max; ++i) {
        unsigned c = (unsigned char)s[i];
        out[n++] = (c < 32 || c == '/' || c == '\\' || c == ':' || c == '*' || c == '?' || c == '"' || c == '<' ||
                    c == '>' || c == '|')
                       ? '_'
                       : (char)c;
    }
    while (n && ((unsigned char)s[n] & 0xc0) == 0x80) --n; /* the cut fell inside a character: drop it */
    while (n && (out[n - 1] == ' ' || out[n - 1] == '.')) --n;
    if (n && out[0] == '.') out[0] = '_';
    if (!n) {
        n = sbd_len(empty);
        memcpy(out, empty, n);
    }
    out[n] = 0;
}

/* The artist folder of a track: its album's artist (albums.idx, one lookup an album), so the tracks of a compilation share a folder; the track's own artist when the cache does not
 * have the album. Worker only. */
static const char *sbd_artist(const sba_track_t *t) {
    if (!t->album_id[0]) return t->artist;
    if (!sbd_same(sbd.al_id, t->album_id)) {
        sbd_set(sbd.al_id, sizeof sbd.al_id, t->album_id);
        if (!sba_album_artist(t->album_id, sbd.al_artist, sizeof sbd.al_artist)) sbd.al_artist[0] = 0;
    }
    return sbd.al_artist[0] ? sbd.al_artist : t->artist;
}

/* variant 0: "<artist>/<album>/<nn> <title>.<ext>" (a second disc "<disc>-<nn> ...", no number when the track has none); n > 0: "... <title> (n+1).<ext>". 1 on success. */
static int sbd_file_name(const sba_track_t *t, const char *artist, int variant, char *out, unsigned cap) {
    char ar[SBD_PART + 16], al[SBD_PART + 16], title[SBD_TITLE + 8], ext[SBA_SUFFIX], num[24], var[12];
    unsigned i, k;
    sbd_clean(ar, artist, SBD_PART, "Unknown Artist");
    sbd_clean(al, t->album, SBD_PART, "Unknown Album");
    sbd_clean(title, t->title, SBD_TITLE, "Track");
    for (i = 0, k = 0; t->suffix[i] && k + 1 < sizeof ext; ++i) {
        unsigned c = (unsigned char)t->suffix[i];
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) ext[k++] = (char)c;
    }
    if (!k) {
        memcpy(ext, "audio", 5);
        k = 5;
    }
    ext[k] = 0;
    num[0] = var[0] = 0;
    if (t->track && t->disc > 1)
        snprintf(num, sizeof num, "%d-%02d ", (int)(t->disc % 100), (int)(t->track % 1000));
    else if (t->track)
        snprintf(num, sizeof num, "%02d ", (int)(t->track % 1000));
    if (variant > 0) snprintf(var, sizeof var, " (%d)", variant + 1);
    k = (unsigned)snprintf(out, cap, "%s/%s/%s%s%s.%s", ar, al, num, title, var, ext);
    return (int)k > 0 && k < cap;
}

/* ---- the queue: SBA_DLMAX slots of (id, state) in memory, the tracks' rows in dlq.idx on the card ----
 * An add appends the track's row to dlq.idx (one write, no sync: a lost line is a download asked for again) and the worker reads it back when the slot's turn comes, so a queue of
 * hundreds costs no memory and outlives a reboot: the first use reads the file and every row whose track is not downloaded waits again (the worker starts with sba_dl_resume or
 * the next add). Rows of finished, cancelled and given-up tracks are dropped when the queue drains or a waiting one is cancelled (sbd_q_compact). qf serialises the file's writers
 * and the worker's read; order: qf, then lock. */

/* The slot of an id (any state), -1 none. The caller holds lock. */
static int sbd_slot(const char *id) {
    int i;
    if (!sbd.q) return -1;
    for (i = 0; i < SBA_DLMAX; ++i)
        if (sbd.q[i].state && sbd_same(sbd.q[i].id, id)) return i;
    return -1;
}

static void sbd_slot_free(sbd_slot_t *s) { memset(s, 0, sizeof *s); }

/* A failure that says nothing about the track (no Wi-Fi, the server, the login, the card): the worker stops there and the rest of the queue waits for the next start. */
static int sbd_later(int code) {
    return code == SBA_NOCONF || code == SBA_NOWIFI || code == SBA_NOCLOCK || code == SBA_NOCERT || code == SBA_CERT ||
           code == SBA_NET || code == SBA_AUTH || code == SBA_STORAGE || code == SBA_MEM || code == SBA_CARDFULL;
}

static int sbd_q_line(const char *ls, const char *le, char *id, unsigned cap) {
    return le - ls >= 4 && ls[0] == 'i' && ls[1] == '=' && sbd_field(ls, le, 'i', id, cap) && id[0];
}

/* A line that takes a track out of the queue: "-=<id>" (sbd_q_cancelled). */
static int sbd_q_gone(const char *ls, const char *le, char *id, unsigned cap) {
    return le - ls >= 3 && ls[0] == '-' && ls[1] == '=' && sbd_field(ls, le, '-', id, cap) && id[0];
}

/* The slots, and the queue the card remembers. Once; the caller holds mf (so the index does not move). */
static void sbd_q_load(void) {
    unsigned n = 0, seq = 0;
    int cnt = 0, i, bad = 0;
    sbd_slot_t *q = (sbd_slot_t *)calloc(SBA_DLMAX, sizeof *q);
    char *text;
    const char *p, *end, *ls, *le;
    if (!q) return;
    text = sbd_slurp_st(SBD_Q, &n, &bad);
    sbd.qbad = bad;
    if (bad) { /* not read whole: not the queue. Nothing is loaded and the next use reads again (a queue taken as empty here would be removed by the next compaction) */
        free(text);
        free(q);
        return;
    }
    p = text ? text : "";
    end = p + n;
    while (sbd_next(&p, end, &ls, &le)) {
        char id[SBA_ID];
        if (sbd_q_gone(
                ls, le, id,
                sizeof id)) { /* cancelled after its row was written (sbd_q_cancelled): the rows before this line are not the queue's */
            for (i = 0; i < cnt && !sbd_same(q[i].id, id); ++i) {
            }
            if (i < cnt) {
                memmove(&q[i], &q[i + 1], (unsigned)(cnt - i - 1) * sizeof *q);
                memset(&q[--cnt], 0, sizeof *q);
            }
            continue;
        }
        if (cnt >= SBA_DLMAX || !sbd_q_line(ls, le, id, sizeof id)) continue;
        for (i = 0; i < sbd.nix && !sbd_same(sbd.ix[i].id, id); ++i) {
        }
        if (i < sbd.nix) continue; /* downloaded since */
        for (i = 0; i < cnt && !sbd_same(q[i].id, id); ++i) {
        }
        if (i < cnt) continue;
        sbd_set(q[cnt].id, sizeof q[cnt].id, id);
        q[cnt].state = SBA_DL_WAIT;
        q[cnt].seq = ++seq;
        ++cnt;
    }
    free(text);
    sbd_lock();
    sbd.q = q;
    sbd.seq = seq;
    sbd.qloaded = 1;
    sbd_unlock();
}

/* The row of a waiting track, from dlq.idx. 1 found; 0 the file was read and has no such row; -1 the file could not be read (the card's trouble, not the row's: the track waits). Worker. */
static int sbd_q_row(const char *id, sba_track_t *t) {
    unsigned n = 0, fsize;
    int r = 0, bad = 0;
    char *text, rid[SBA_ID], file[8];
    const char *p, *end, *ls, *le;
    sbd_qf_lock();
    text = sbd_slurp_st(SBD_Q, &n, &bad);
    sbd_qf_unlock();
    if (bad || (!text && !m1_card_mounted())) {
        free(text);
        return -1;
    }
    p = text ? text : "";
    end = p + n;
    while (sbd_next(
        &p, end, &ls,
        &le)) { /* the last row of the track: an add after a cancel appends a new one, and that is the one asked for; a cancel's line after it leaves none */
        if (sbd_q_line(ls, le, rid, sizeof rid) && sbd_same(rid, id))
            r = sbd_parse_row(ls, le, t, file, sizeof file, &fsize);
        else if (sbd_q_gone(ls, le, rid, sizeof rid) && sbd_same(rid, id))
            r = 0;
    }
    free(text);
    return r;
}

/* A track leaves the queue by the user's word (a cancel, an add that could not start): one line "-=<id>" appended to dlq.idx, before the file is compacted. The compaction needs the
 * whole file read back and may not get it (then it leaves the file alone); this line needs no read, and with it the row does not wait again after a restart. A later add of the same
 * track appends its row after the line and counts. 1 when the card has it (or has no queue file). Takes qf. */
static int sbd_q_cancelled(const char *id) {
    char line[SBA_ID + 4];
    int fd, n, ok = 0;
    if (!m1_card_mounted()) return 0;
    n = snprintf(line, sizeof line, "-=%s\n", id);
    if (n <= 0 || n >= (int)sizeof line) return 0;
    sbd_qf_lock();
    if (access(SBD_Q, 0) != 0)
        ok = 1; /* no queue file: nothing of the track is on the card */
    else {
        fd = open(SBD_Q, O_WRONLY | O_APPEND, 0644);
        if (fd >= 0) {
            ok = write(fd, line, (unsigned)n) == n;
            ok = close(fd) == 0 && ok;
        }
    }
    sbd_qf_unlock();
    return ok;
}

/* Append a track's row to dlq.idx. 1 written. The caller holds qf. */
static int sbd_q_append(const sba_track_t *t) {
    char *row = (char *)calloc(SBD_LINE, 1);
    unsigned n;
    int fd, ok = 0;
    if (!row) return 0;
    n = sbd_row_text(row, SBD_LINE - 1, t, "", 0);
    row[n++] = '\n';
    mkdir("/mnt/mmc/.m1plus", 0755);
    mkdir(SBA_DIR, 0755);
    fd = open(SBD_Q, O_WRONLY | O_APPEND | O_CREAT, 0644);
    if (fd >= 0) {
        ok = write(fd, row, n) == (int)n;
        ok = close(fd) == 0 && ok;
    }
    free(row);
    return ok;
}

/* dlq.idx keeps only the rows of tracks that still wait, run, or failed for a reason a later start may cure (one row a track); with none the file goes. */
static int sbd_q_compact(void) {
    unsigned n = 0, out = 0;
    int bad = 0, ok = 0, pass;
    char *text, *buf;
    const char **last; /* per slot: the start of the last row of its track */
    const char *p, *end, *ls, *le;
    if (!m1_card_mounted()) return 0;
    sbd_qf_lock();
    text = sbd_slurp_st(SBD_Q, &n, &bad);
    if (bad) { /* not read whole: the file stays as it is (rewritten from a part, the rows not read would be lost; the rows of finished tracks cost nothing until the next time) */
        free(text);
        text = (char *)0;
    } else if (!text)
        ok = 1; /* no file (or an empty one): nothing to drop */
    buf = text ? (char *)calloc(n + 2, 1) : (char *)0;
    last = (const char **)calloc(SBA_DLMAX, sizeof *last);
    if (text && buf && last) {
        for (pass = 0; pass < 2;
             ++pass) { /* 0: where the last row of each track that stays is; 1: those rows, in the file's order */
            p = text;
            end = p + n;
            while (sbd_next(&p, end, &ls, &le)) {
                char id[SBA_ID];
                int i, keep = 0;
                if (!sbd_q_line(ls, le, id, sizeof id)) continue;
                sbd_lock();
                i = sbd_slot(id);
                if (i >= 0 && (sbd.q[i].state == SBA_DL_WAIT || (sbd.q[i].state == SBA_DL_ACTIVE && !sbd.stop) ||
                               (sbd.q[i].state == SBA_DL_FAILED && sbd_later(sbd.q[i].code))))
                    keep = 1;
                sbd_unlock();
                if (!keep) continue;
                if (!pass)
                    last[i] = ls;
                else if (last[i] == ls) {
                    memcpy(buf + out, ls, (unsigned)(le - ls));
                    out += (unsigned)(le - ls);
                    buf[out++] = '\n';
                }
            }
        }
        if (!out)
            ok = unlink(SBD_Q) == 0 || access(SBD_Q, 0) != 0;
        else if (out != n)
            ok = m1_card_write(SBA_DIR, SBD_Q, SBD_Q_TMP, buf, out, (const void *)0, 0) == 0;
        else
            ok = 1;
    }
    free(last);
    free(buf);
    free(text);
    sbd_qf_unlock();
    return ok;
}

/* ---- progress ---- */

/* The transfer-info hook for the download sink (sbapi.c's hook gives every sink to this first). Non-zero aborts. */
int sba_dl_xfer(void *ctx, long long total, long long now, long long up_total, long long up_now) {
    sbn_sink_t *s = (sbn_sink_t *)ctx;
    long long resume, got;
    unsigned g, t, step;
    (void)up_total;
    (void)up_now;
    if (!s || s != sbd.sink) return 0;
    if (sbd.stop) return 1;
    if (now < 0) return 0;
    resume = s->resume_offset;
    got = now + (resume > 0 ? resume : 0);
    if (resume > 0) { /* only a 206 for exactly our range tells the whole size */
        if (!s->range_seen || s->range_start != resume || s->range_total <= 0)
            total = 0;
        else
            total = s->range_total;
    }
    if (total < got) total = 0;
    g = got > 0xffffffffLL ? 0xffffffffu : (unsigned)got;
    t = total > 0xffffffffLL ? 0xffffffffu : (unsigned)total;
    sbd.got = g;
    sbd.total = t;
    step = t ? (g >> 10) * 50 / ((t >> 10) ? (t >> 10) : 1)
             : 1000 + (g >> 20); /* every 2 % of the file, a MB when its size is not known */
    if (step != sbd.step) {
        sbd.step = step;
        sbd_bump();
    }
    return 0;
}

/* ---- the worker ---- */

static int sbd_http_code(const sbn_sink_t *s, unsigned free_kb_known, unsigned free_kb) {
    long st = s->http_status;
    int rc = s->curl_result;
    if (rc == CURLE_SSL_CACERT || rc == CURLE_SSL_CONNECT_ERROR || rc == CURLE_PEER_FAILED_VERIFICATION ||
        rc == CURLE_SSL_CERTPROBLEM || rc == CURLE_SSL_CIPHER || rc == CURLE_SSL_ISSUER_ERROR)
        return SBA_CERT;
    if (rc == CURLE_SSL_CACERT_BADFILE) return SBA_NOCERT;
    switch (s->werr) { /* what the card side said (sbnet.h SBN_W_*), before what the network said */
    case SBN_W_SPACE:
        return SBA_CARDFULL;
    case SBN_W_CARD:
        return SBA_STORAGE;
    case SBN_W_IO:
        return SBA_WRITE;
    case SBN_W_RESPONSE: /* the headers were not those of the audio file asked for (a page, a JSON error, a resume the server answered differently): nothing was written */
        if (st >= 200 && st < 300) return SBA_NOTAUDIO;
        break;
    }
    if (rc == CURLE_WRITE_ERROR && free_kb_known && free_kb <= SBA_RESERVE_KB) return SBA_CARDFULL;
    if (rc == 0 && st == 0)
        return SBA_STORAGE; /* sbn_download stopped before it sent anything: the .part file could not be opened */
    if (rc == 0) return SBA_NOTAUDIO; /* the answer was 2xx but not the whole audio file */
    if (st == 401 || st == 403) return SBA_AUTH;
    if (st == 404 || st == 410) return SBA_NOTFOUND;
    if (st >= 400) return SBA_HTTP;
    if (rc == CURLE_WRITE_ERROR) return SBA_WRITE;
    return SBA_NET;
}

/* One track to the card. Returns SBA_OK, SBA_CANCELLED or the failure; *size the file's bytes. */
static int sbd_run(const sba_track_t *t, char *file, unsigned *size) {
    sbn_server_t srv;
    char base[SBA_URL], user[SBA_TEXT], auth[SBA_TEXT], url[SBA_URL + 128], part[SBD_PATH + 8], final[SBD_PATH],
        dir[SBD_PATH], owner[SBA_ID], identity[SBN_IDENTITY];
    const char *artist;
    unsigned kb = 0, need;
    int free_ok;
    int v, g, ok, resumable = -1, rc, code;
    sbn_sink_t *sink;
    g = sba_guard();
    if (g) return g;
    if (sba_net_open(base, sizeof base, user, sizeof user, auth, sizeof auth) != SBA_OK) return SBA_NOCONF;
    if (!m1_card_mounted() || !pn_free_kb("/mnt/mmc", &kb)) return SBA_STORAGE;
    artist = sbd_artist(t);
    /* the name: a free one, or the one an earlier download of this track left (the file is never overwritten) */
    for (v = 0, ok = 0; v < 9; ++v) {
        if (!sbd_file_name(t, artist, v, file, SBD_FILE) || !sbd_path(final, sizeof final, file)) return SBA_STORAGE;
        owner[0] = 0;
        if (sbd_owner(file, owner, sizeof owner) && !sbd_same(owner, t->id))
            continue; /* another track's name (whatever the card says of the file, and in any letter case): the next one */
        if (access(final, 0) != 0) {
            ok = 1;
            break;
        }
        if (!owner[0] && sbd_shared(final, t->id))
            continue; /* no name of the manifest, and yet another track's file (the card folds more than ASCII): the next one */
        ok = 2; /* ours, or a file the manifest does not know: it stays as it is, the track is done */
        break;
    }
    if (!ok) return SBA_STORAGE;
    if (ok == 2) { /* adopt: the file is on the card */
        int fd = open(final, O_RDONLY, 0);
        long len = fd >= 0 ? lseek(fd, 0, 2) : 0;
        if (fd >= 0) close(fd);
        *size = len > 0 ? (unsigned)len : 0;
        sbd.got = sbd.total = *size;
        return SBA_OK;
    }
    if (snprintf(part, sizeof part, "%s.part", final) >= (int)sizeof part || !sbd_dir(dir, sizeof dir, file))
        return SBA_STORAGE;
    sbd_mkdirs(file);
    need = t->size >> 10;
    if (kb <= SBA_RESERVE_KB || (need && kb - SBA_RESERVE_KB < need)) return SBA_CARDFULL;
    srv.base = base, srv.user = user, srv.auth = auth;
    if (sbn_url(url, sizeof url, srv, "download", t->id, (const char *)0)) return SBA_STORAGE;
    sink = (sbn_sink_t *)calloc(1, sizeof *sink);
    if (!sink) return SBA_MEM;
    sbn_sink_reset(sink);
    sbd.sink = sink;
    /* who the .part file is for: a resume record of another server, user or track is not followed */
    identity[0] = 0;
    if (snprintf(identity, sizeof identity, "%s\n%s\n%s", base, user, t->id) >= (int)sizeof identity) identity[0] = 0;
    rc = sbn_download(url, part, final, dir, identity[0] ? identity : (const char *)0, sink, &resumable);
    sbd.sink = (sbn_sink_t *)0;
    if (rc == 1) {
        *size = (unsigned)(sink->resume_offset + sink->written);
        sbd.got = sbd.total = *size;
        sbn_sink_free(sink);
        free(sink);
        return SBA_OK;
    }
    free_ok = pn_free_kb("/mnt/mmc", &kb);
    code = sbd_http_code(sink, free_ok, kb);
    sbd.status = (int)sink->http_status;
    if (sbd.stop || sink->curl_result == CURLE_ABORTED_BY_CALLBACK) code = SBA_CANCELLED;
    sbn_sink_free(sink);
    free(sink);
    return code;
}

/* Stock's library learns the files of a folder (scanSpecFolder, as the PR does after a DSD file): once a folder, when the worker moves on to another album or stops. */
static void sbd_scan(char *dir) {
    if (dir[0] && m1_card_mounted()) scanSpecFolder(dir, 0);
    dir[0] = 0;
}

static void *sbd_main(void *arg) {
    char scan[SBD_PATH], dir[SBD_PATH], file[SBD_FILE], id[SBA_ID];
    sba_track_t *t = (sba_track_t *)calloc(1, sizeof *t);
    int tidy = 0;
    (void)arg;
    scan[0] = 0;
    for (;;) {
        int i, best = -1, code, pause;
        unsigned size = 0;
        sbd_lock();
        for (i = 0; sbd.q && i < SBA_DLMAX; ++i)
            if (sbd.q[i].state == SBA_DL_WAIT && (best < 0 || (int)(sbd.q[i].seq - sbd.q[best].seq) < 0)) best = i;
        if (best < 0 &&
            tidy) { /* the queue is drained: the last folder's scan and the queue file, before the worker ends (another may start the moment it does) */
            sbd_unlock();
            sbd_scan(scan);
            sbd_q_compact();
            tidy = 0;
            continue;
        }
        if (best < 0) { /* nothing left: the worker ends under the lock, so an add that follows starts a new one */
            sbd.busy = 0;
            sbd_unlock();
            sbd_bump();
            free(t);
            return (void *)0;
        }
        sbd.q[best].state = SBA_DL_ACTIVE;
        sbd.q[best].code = 0;
        sbd.stop = sbd.again = 0;
        sbd.got = sbd.total = 0;
        sbd.step = ~0u;
        sbd_set(id, sizeof id, sbd.q[best].id);
        sbd_unlock();
        sbd_bump();
        tidy = 1;
        file[0] = 0;
        if (!t)
            code = SBA_MEM;
        else {
            int row = sbd_q_row(id, t);
            code = row < 0 ? SBA_STORAGE
                   : !row  ? SBA_PARSE
                           : sbd_run(t, file, &size); /* (SBA_STORAGE stops the worker and keeps the row: sbd_later) */
        }
        if (code == SBA_OK) {
            char *row = (char *)calloc(SBD_LINE, 1);
            if (!row)
                code = SBA_MEM;
            else {
                sbd_row_text(row, SBD_LINE, t, file, size);
                if (!sbd_edit((const char *)0, row))
                    code = SBA_STORAGE; /* the file is on the card; the next add finds and adopts it */
                free(row);
            }
        }
        if (code == SBA_OK && sbd_dir(dir, sizeof dir, file) && !sbd_same(dir, scan)) {
            sbd_scan(scan); /* the album before this one is complete */
            sbd_set(scan, sizeof scan, dir);
        }
        pause = code != SBA_OK && code != SBA_CANCELLED && sbd_later(code);
        if (pause) sbd_scan(scan); /* (before the worker is seen to have ended) */
        sbd_lock();
        if (sbd.stop && code != SBA_OK)
            code = SBA_CANCELLED,
            pause =
                0; /* cancelled after the transfer had ended with a fault of its own (the cancel was told yes): the track leaves the queue, it is not kept as failed for sba_dl_resume */
        if (code == SBA_CANCELLED && sbd.again)
            sbd.q[best].state =
                SBA_DL_WAIT; /* the transfer stopped for a cancel that an add took back before this point: the add was told yes and its row is on the card, so the track is fetched again (its place in line is kept) */
        else if (code == SBA_OK || code == SBA_CANCELLED)
            sbd_slot_free(&sbd.q[best]);
        else {
            sbd.q[best].state = SBA_DL_FAILED;
            sbd.q[best].code = code;
            sbd.fail_code = code;
            sbd.fail_status = code == SBA_HTTP ? sbd.status : 0;
            sbd.fail_at = time((long *)0);
            if (pause) sbd.busy = 0; /* the rest keeps waiting: sba_dl_resume or the next add starts a worker again */
        }
        sbd_unlock();
        if (code == SBA_CANCELLED && !pause) sbd_q_compact(); /* its row goes now, not at the next start */
        sbd_bump();
        if (pause) {
            free(t);
            return (void *)0;
        }
    }
}

/* ---- the API ---- */

/* A worker when none runs. SBA_OK (started, or one is running), SBA_MEM for no thread. */
static int sbd_start(void) {
    unsigned long th = 0;
    int start = 0;
    sbd_lock();
    if (!sbd.busy) sbd.busy = 1, start = 1;
    sbd_unlock();
    if (!start) return SBA_OK;
    if (pthread_create(&th, (const void *)0, sbd_main, (void *)0) != 0) {
        sbd_lock();
        sbd.busy = 0;
        sbd_unlock();
        return SBA_MEM;
    }
    pthread_detach(th);
    return SBA_OK;
}

int sba_dl_add(const sba_track_t *t) {
    sbd_ent_t e;
    int i, slot = -1, g, known = 0, again;
    unsigned kb = 0;
    if (!t || !t->id[0]) return SBA_PARSE;
    if (sbd_find(t->id, &e)) {
        if (sbd_exists(e.file)) return SBA_OK; /* on the card already */
        sbd_edit(t->id, (const char *)0); /* deleted by hand: the row goes and the track downloads again */
    }
    sbd_lock();
    i = sbd_slot(t->id);
    again = i >= 0 && sbd.q[i].state == SBA_DL_ACTIVE && sbd.stop;
    if (i >= 0 && sbd.q[i].state != SBA_DL_FAILED) known = 1; /* waiting or running: asked twice is once */
    sbd_unlock();
    if (again) { /* a cancel the worker has not seen yet is withdrawn: its line is on the card, so the track's row is written again after it first (else a restart would drop the track) */
        int ok;
        sbd_qf_lock();
        ok = sbd_q_append(t);
        sbd_qf_unlock();
        if (!ok) return SBA_STORAGE; /* (the cancel stands) */
        sbd_lock();
        i = sbd_slot(t->id);
        if (i >= 0 && sbd.q[i].state == SBA_DL_ACTIVE && sbd.stop)
            sbd.stop = 0,
            sbd.again =
                1; /* (the transfer goes on if it has not looked yet; if it has, the worker queues the track again) */
        else if (i < 0)
            known =
                0; /* the worker ended it meanwhile: a plain add from here (one more row of the track; the last one counts) */
        sbd_unlock();
    }
    g = sba_guard();
    if (g) return known && sbd.busy ? SBA_OK : g;
    if (known) return sbd_start(); /* (a queue that stopped or came back from the card starts here) */
    if (!m1_card_mounted() || !pn_free_kb("/mnt/mmc", &kb)) return SBA_STORAGE;
    if (!sbd.q)
        return sbd.qbad
                   ? SBA_STORAGE
                   : SBA_MEM; /* (the queue on the card would not read: nothing is added on top of rows not seen) */
    if (kb <= SBA_RESERVE_KB || (t->size >> 10) > kb - SBA_RESERVE_KB) return SBA_CARDFULL;
    sbd_qf_lock();
    sbd_lock();
    i = sbd_slot(t->id); /* (the same id is now a failed slot, or nothing) */
    if (i >= 0) slot = i;
    for (i = 0; slot < 0 && i < SBA_DLMAX; ++i)
        if (!sbd.q[i].state) slot = i;
    if (slot < 0) /* the oldest failed one gives way */
        for (i = 0; i < SBA_DLMAX; ++i)
            if (sbd.q[i].state == SBA_DL_FAILED && (slot < 0 || (int)(sbd.q[i].seq - sbd.q[slot].seq) < 0)) slot = i;
    if (slot < 0) {
        sbd_unlock();
        sbd_qf_unlock();
        return SBA_QFULL;
    }
    sbd_slot_free(&sbd.q[slot]);
    sbd_set(sbd.q[slot].id, sizeof sbd.q[slot].id, t->id);
    sbd.q[slot].seq = ++sbd.seq;
    sbd.q[slot].state = SBA_DL_WAIT;
    sbd_unlock();
    g = sbd_q_append(t) ? SBA_OK : SBA_STORAGE; /* (the worker reads the row under qf: never before it is there) */
    sbd_qf_unlock();
    if (g == SBA_OK) g = sbd_start();
    if (g != SBA_OK) {
        sbd_lock();
        if (sbd.q[slot].state == SBA_DL_WAIT && sbd_same(sbd.q[slot].id, t->id)) sbd_slot_free(&sbd.q[slot]);
        sbd_unlock();
        sbd_q_cancelled(t->id);
        sbd_q_compact(); /* (a row written for a worker that could not be started does not wait on the card) */
    }
    sbd_bump();
    return g;
}

int sba_dl_resume(void) {
    int i, n = 0;
    sbd_ensure();
    if (!sbd.q || sbd.busy || !m1_card_mounted() || sba_guard()) return 0;
    sbd_lock();
    for (i = 0; i < SBA_DLMAX; ++i) {
        if (sbd.q[i].state == SBA_DL_FAILED &&
            sbd_later(sbd.q[i].code)) { /* the one the worker stopped at: again, behind the others */
            sbd.q[i].state = SBA_DL_WAIT;
            sbd.q[i].code = 0;
            sbd.q[i].seq = ++sbd.seq;
        }
        n += sbd.q[i].state == SBA_DL_WAIT;
    }
    sbd_unlock();
    if (!n || sbd_start() != SBA_OK) return 0;
    sbd_bump();
    return n;
}

static void sbd_cancel_locked(int i) {
    if (sbd.q[i].state == SBA_DL_ACTIVE)
        sbd.stop = 1, sbd.again = 0;
    else
        sbd_slot_free(&sbd.q[i]); /* waiting or failed */
}

int sba_dl_cancel(const char *id) {
    int i, waited = 0, kept = 1;
    if (!id) return SBA_OK;
    sbd_ensure();
    sbd_lock();
    i = sbd_slot(id);
    if (i >= 0) {
        waited = sbd.q[i].state != SBA_DL_ACTIVE;
        sbd_cancel_locked(i);
    }
    sbd_unlock();
    if (i >= 0)
        kept = sbd_q_cancelled(id); /* (first, and whatever the compaction can do: the cancel outlives a restart) */
    if (waited && sbd_q_compact()) kept = 1; /* (the worker drops the row of the one it was on) */
    sbd_bump();
    return kept
               ? SBA_OK
               : SBA_STORAGE; /* (stopped for this run either way; SBA_STORAGE: the card did not take it, so the track waits again after a restart) */
}

void sba_dl_cancel_all(void) {
    int i;
    sbd_lock();
    for (i = 0; sbd.q && i < SBA_DLMAX; ++i)
        if (sbd.q[i].state) sbd_cancel_locked(i);
    sbd_unlock();
    if (m1_card_mounted()) { /* nothing waits on the card either (also when the queue was never read this run) */
        sbd_qf_lock();
        unlink(SBD_Q);
        sbd_qf_unlock();
    }
    sbd_bump();
}

int sba_dl_failure(int *status) {
    int code;
    sbd_lock();
    code = sbd.fail_code;
    if (status) *status = sbd.fail_status;
    if (code && (long)time((long *)0) - sbd.fail_at > SBD_FAIL_FRESH_S)
        code = 0; /* nobody was looking: too old to be news */
    sbd.fail_code = sbd.fail_status = 0;
    sbd_unlock();
    return code;
}

int sba_dl_state(const char *id, int *code, unsigned *got, unsigned *total) {
    int i, r = SBA_DL_NONE;
    sbd_ent_t e;
    unsigned g = 0, tt = 0;
    if (!id || !id[0]) return SBA_DL_NONE;
    sbd_ensure();
    sbd_lock();
    i = sbd_slot(id);
    if (i >= 0) {
        r = sbd.q[i].state;
        if (r == SBA_DL_FAILED && code) *code = sbd.q[i].code;
        if (r == SBA_DL_ACTIVE) {
            if (sbd.stop)
                r = SBA_DL_NONE; /* cancelled: the worker is about to drop it */
            else
                g = sbd.got, tt = sbd.total;
        }
    }
    sbd_unlock();
    if (r == SBA_DL_NONE &&
        sbd_find(id,
                 &e)) { /* (memory only: a file deleted by hand shows until sba_dl_path or sba_downloaded finds out) */
        r = SBA_DL_DONE;
        g = tt = e.size;
    }
    if (got) *got = g;
    if (total) *total = tt < g ? 0 : tt;
    return r;
}

unsigned sba_dl_gen(void) { return sbd.gen; }

int sba_dl_busy(void) { return sbd.busy; }

int sba_dl_pending(void) {
    int i, n = 0;
    sbd_ensure();
    if (!sbd.q) return 0;
    sbd_lock();
    for (i = 0; i < SBA_DLMAX; ++i)
        if (sbd.q[i].state == SBA_DL_WAIT || sbd.q[i].state == SBA_DL_ACTIVE ||
            (sbd.q[i].state == SBA_DL_FAILED && sbd_later(sbd.q[i].code)))
            ++n;
    sbd_unlock();
    return n;
}

int sba_dl_path(const char *id, char *path, unsigned cap) {
    sbd_ent_t e;
    char full[SBD_PATH];
    if (!id || !sbd_find(id, &e)) return 0;
    if (!sbd_path(full, sizeof full, e.file) || !sbd_file_ok(e.file)) return 0;
    if (access(full, 0) != 0) {
        if (m1_card_mounted())
            sbd_edit(
                id,
                (const char
                     *)0); /* gone: the row goes (never while the card is out: it would look like all files are gone) */
        return 0;
    }
    if (path) {
        unsigned n = sbd_len(full);
        if (n >= cap) return 0;
        memcpy(path, full, n + 1);
    }
    return 1;
}

int sba_dl_delete(const char *id) {
    sbd_ent_t e;
    char full[SBD_PATH], part[SBD_PATH + 16];
    int r = 0;
    if (!id || !id[0]) return 0;
    sba_dl_cancel(id);
    if (!sbd_find(id, &e)) return 0;
    if (sbd_file_ok(e.file) && sbd_path(full, sizeof full, e.file)) {
        if (unlink(full) != 0 && access(full, 0) == 0) return -1;
        if (snprintf(part, sizeof part, "%s.part", full) < (int)sizeof part) unlink(part);
        if (snprintf(part, sizeof part, "%s.part.etag", full) < (int)sizeof part) unlink(part);
        sbd_rmdirs(e.file);
    }
    if (!sbd_edit(id, (const char *)0)) r = -1;
    sbd_bump();
    return r;
}

int sba_downloaded(sba_tracks_t *out) {
    unsigned n = 0, lines = 0, i, cnt = 0, fsize, ngone = 0;
    char *text;
    const char *p, *end, *ls, *le;
    sba_track_t *v, *t;
    char file[SBD_FILE], gone[8][SBA_ID];
    out->n = 0;
    out->v = (sba_track_t *)0;
    sbd_ensure();
    text = sbd_slurp(SBD_IDX, &n);
    if (!text) return 0;
    for (i = 0; i < n; ++i) lines += text[i] == '\n';
    v = (sba_track_t *)calloc(lines + 1, sizeof *v);
    t = (sba_track_t *)calloc(1, sizeof *t);
    if (!v || !t) {
        free(v);
        free(t);
        free(text);
        return -1;
    }
    p = text;
    end = text + n;
    while (sbd_next(&p, end, &ls, &le)) {
        if (le - ls < 4 || ls[0] != 'i' || ls[1] != '=' || !sbd_parse_row(ls, le, t, file, sizeof file, &fsize) ||
            !sbd_file_ok(file))
            continue;
        if (!sbd_exists(
                file)) { /* deleted by hand: dropped below (some at a time; never while the card is out, when every file looks gone) */
            if (ngone < 8 && m1_card_mounted()) sbd_set(gone[ngone++], SBA_ID, t->id);
            continue;
        }
        memcpy(&v[cnt++], t, sizeof *t);
    }
    free(t);
    free(text);
    for (i = 0; i < ngone; ++i) sbd_edit(gone[i], (const char *)0);
    out->n = (int)cnt;
    if (cnt)
        out->v = v;
    else
        free(v);
    return (int)cnt;
}

/* ---- the queue as a list (the Downloaded page's "Downloading" section) ---- */

/* Whether slot i still has a download to come: waiting, running (and not cancelled), or stopped at a fault a later start may cure. The caller holds lock. */
static int sbd_pending_locked(int i) {
    return sbd.q[i].state == SBA_DL_WAIT || (sbd.q[i].state == SBA_DL_ACTIVE && !sbd.stop) ||
           (sbd.q[i].state == SBA_DL_FAILED && sbd_later(sbd.q[i].code));
}

unsigned sba_dl_rows(void) {
    unsigned sig;
    int i;
    sbd_ensure();
    sbd_lock();
    sig = (unsigned)sbd.nix * 0x9e3779b1u;
    for (i = 0; sbd.q && i < SBA_DLMAX; ++i)
        if (sbd_pending_locked(i)) sig += (sbd.q[i].seq + 1u) * 2654435761u;
    sbd_unlock();
    return sig;
}

int sba_dl_queue(sba_tracks_t *out) {
    typedef struct {
        char id[SBA_ID];
        unsigned seq;
        unsigned char run, have;
    } ent_t;
    ent_t *e, tmp;
    sba_track_t *v = (sba_track_t *)0, *t = (sba_track_t *)0;
    unsigned n = 0, fsize;
    int cnt = 0, i, j, k, bad = 0, got = 0;
    char *text = (char *)0, rid[SBA_ID], file[8];
    const char *p, *end, *ls, *le;
    out->n = 0;
    out->v = (sba_track_t *)0;
    sbd_ensure();
    if (!sbd.q) return 0;
    e = (ent_t *)calloc(SBA_DLMAX, sizeof *e);
    if (!e) return -1;
    sbd_lock();
    for (i = 0; i < SBA_DLMAX; ++i)
        if (sbd_pending_locked(i)) {
            sbd_set(e[cnt].id, sizeof e[cnt].id, sbd.q[i].id);
            e[cnt].seq = sbd.q[i].seq;
            e[cnt].run = sbd.q[i].state == SBA_DL_ACTIVE;
            ++cnt;
        }
    sbd_unlock();
    for (i = 1; i < cnt; ++i) { /* the running one first, then the order the worker takes them in (seq) */
        tmp = e[i];
        for (j = i; j > 0 && (tmp.run > e[j - 1].run || (tmp.run == e[j - 1].run && (int)(tmp.seq - e[j - 1].seq) < 0));
             --j)
            e[j] = e[j - 1];
        e[j] = tmp;
    }
    if (cnt) {
        v = (sba_track_t *)calloc((unsigned)cnt, sizeof *v);
        t = (sba_track_t *)calloc(1, sizeof *t);
        sbd_qf_lock();
        text = sbd_slurp_st(SBD_Q, &n, &bad);
        sbd_qf_unlock();
    }
    if (v && t && text && !bad) {
        p = text;
        end = p + n;
        while (sbd_next(
            &p, end, &ls,
            &le)) { /* the last row of a track is the track's; a cancel's line after it leaves none (sbd_q_row) */
            int row = sbd_q_line(ls, le, rid, sizeof rid), gone = !row && sbd_q_gone(ls, le, rid, sizeof rid);
            if (!row && !gone) continue;
            for (k = 0; k < cnt && !sbd_same(e[k].id, rid); ++k) {
            }
            if (k == cnt) continue;
            e[k].have = (unsigned char)(row && sbd_parse_row(ls, le, t, file, sizeof file, &fsize));
            if (e[k].have) memcpy(&v[k], t, sizeof *t);
        }
        for (k = 0; k < cnt; ++k)
            if (e[k].have) {
                if (got != k) memcpy(&v[got], &v[k], sizeof *v);
                ++got;
            }
    }
    free(text);
    free(t);
    free(e);
    if (got)
        out->v = v, out->n = got;
    else
        free(v);
    return got;
}
