/* M1+ Music Shuffle: Shuffle Songs, Shuffle Albums and Shuffle Folders from the M1+ Music menu.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * After q2-pod's Shuffle page (patch/navigation.c shuffle_play / shuffle_songs / shuffle_groups,
 * patch/playback.c rand_below / shuffle / make_order), Copyright (c) 2026 Diamond Bond, MIT
 * (https://github.com/DiamondBond/q2-pod); see NOTICE. The xorshift32 generator and its seeding,
 * the Fisher-Yates shuffle of the groups, the group orders (an album's disc, then track, then
 * path; a folder's path) and the user-facing messages follow q2-pod. q2-pod keeps the groups
 * together at play time with hooks in the stock player (mclNextSong, mclLoadPlayList, ...); this
 * file installs none: Shuffle Albums/Folders build the whole queue up front, in its play order,
 * and hand it to the stock player in a sequential mode (docs/architecture.md).
 *
 * No stock function is hooked. Everything here runs from a tap on a row of the M1+ Music menu
 * (patch/m1plus.c on_row), once, on the UI thread, and returns: no timer, no thread, no state kept
 * between taps except the random generator's word.
 *
 * The stock path is the Songs page's: loadLocalClassList(0xf001) (getAllMusic into
 * *pdeq_showlist), loadSongList(queue, name, cue, 0xf001) (the queue, as the page's row handler
 * builds it @0x5258a0, and the memory-playback record), navigator_to_with_context("playing_page",
 * {queue, index, 0xf001, 2}) (start_player: mclLoadPlayList + mclStartPlayer), and the play mode
 * as the Play settings page sets it (@0x49fc78).
 */
#include "offsets.inc"
#include "stock.h"
#include "i18n.h"

#define P(r, off) (*(char **)((char *)(r) + (off)))
#define I(r, off) (*(int *)((char *)(r) + (off)))

enum { SHUFFLE_SONGS = 0, SHUFFLE_ALBUMS = 1, SHUFFLE_FOLDERS = 2 }; /* tools/pod_pages.py */

static unsigned rng __attribute__((section(".scratch")));
static int by_folder __attribute__((section(".scratch"))); /* the group key of the sort in progress */

/* xorshift32, seeded once from stock's generator and the tick clock (q2-pod playback.c
 * rand_below): stock's toolsRandnum reseeds from time() on every call, so two taps in the same
 * second would repeat. */
static unsigned rand_below(unsigned n) {
    if (!rng) rng = ((unsigned)toolsRandnum(0x7fffffff) ^ time_now_ms() * 2654435761u) | 1;
    rng ^= rng << 13;
    rng ^= rng >> 17;
    rng ^= rng << 5;
    return rng % n;
}

static const char *str(void *r, int field) {
    const char *s = r ? P(r, field) : (const char *)0;
    return s ? s : "";
}

/* The stock one-line message box, as the Songs page shows "file not found" (@0x5259dc). */
static void toast(const char *text) {
    struct {
        int kind, ms;
        char text[MSGINFO_TEXT], text2[MSGINFO_TEXT];
    } info;
    unsigned i;
    memset(&info, 0, sizeof info);
    info.kind = MSGINFO_KIND;
    info.ms = MSGINFO_MS;
    for (i = 0; text[i] && i < sizeof info.text - 1; ++i) info.text[i] = text[i];
    navigator_to_with_context("dialog/msginfo_dialog", &info);
}

/* The stock play mode, changed the way the Play settings page changes it (@0x49fc78): the player,
 * the SyncLink and DLNA remotes, and [PLAYSET] PLAYMODE in /mnt/data/config.ini. Nothing is
 * written when the mode is already the one wanted. */
static void set_mode(int mode) {
    if (mclGetPlayMode() == mode) return;
    mclSetPlayMode(mode);
    notifyPlayMode();
    dmrSendPlayMode(mode);
    write_int_config(mode, "PLAYSET", "PLAYMODE");
}

/* A mode that plays a queue in order: List play or Repeat all are kept, Shuffle and Repeat one become List play. */
static void set_in_order(void) {
    int mode = mclGetPlayMode();
    set_mode(mode == MODE_SHUFFLE || mode == MODE_REPEAT_ONE ? MODE_ORDER : mode);
}

/* ---------------------------------------------------------------------------
 * Album and folder order. One index entry per queued song; a heapsort (no libc callback into the
 * payload) groups them, the groups get a random rank, a second sort puts them in play order, and
 * the queue's own records are then permuted in place, so no second copy of the library is made.
 */
typedef struct {
    void *rec;      /* the song's record inside the queue */
    unsigned group; /* pass 2: the group's random rank; while permuting, ~0 once placed */
    unsigned idx;   /* its position in the queue as loadSongList built it */
    unsigned dir;   /* Shuffle Folders: the length of its path's folder (dir_len), computed once */
} entry;
typedef int (*cmp_fn)(const entry *, const entry *);

static void sift(entry *v, unsigned i, unsigned n, cmp_fn cmp) {
    for (;;) {
        unsigned c = 2 * i + 1;
        entry t;
        if (c >= n) return;
        if (c + 1 < n && cmp(&v[c], &v[c + 1]) < 0) ++c;
        if (cmp(&v[i], &v[c]) >= 0) return;
        t = v[i], v[i] = v[c], v[c] = t;
        i = c;
    }
}

static void sort(entry *v, unsigned n, cmp_fn cmp) {
    unsigned i;
    entry t;
    for (i = n / 2; i-- > 0;) sift(v, i, n, cmp);
    for (i = n; i-- > 1;) {
        t = v[0], v[0] = v[i], v[i] = t;
        sift(v, 0, i, cmp);
    }
}

/* SQLite's NOCASE, which the stock Albums list groups by (getAllAlbum: "group by album COLLATE
 * NOCASE"): ASCII letters fold, nothing else does. */
static int fold(int c) { return c >= 'A' && c <= 'Z' ? c + 32 : c; }
static int nocase(const char *a, const char *b) {
    while (*a && fold((unsigned char)*a) == fold((unsigned char)*b)) ++a, ++b;
    return fold((unsigned char)*a) - fold((unsigned char)*b);
}

/* The folder of a path: everything before its last '/'. */
static unsigned dir_len(const char *p) {
    unsigned i, n = 0;
    for (i = 0; p[i]; ++i)
        if (p[i] == '/') n = i;
    return n;
}
static int dir_cmp(const char *a, unsigned la, const char *b, unsigned lb) {
    unsigned i;
    for (i = 0; i < la && i < lb; ++i)
        if (a[i] != b[i]) return (unsigned char)a[i] - (unsigned char)b[i];
    return (int)la - (int)lb;
}

static int key_cmp(const entry *a, const entry *b) {
    return by_folder ? dir_cmp(str(a->rec, REC_PATH), a->dir, str(b->rec, REC_PATH), b->dir)
                     : nocase(str(a->rec, REC_ALBUM), str(b->rec, REC_ALBUM));
}

static int by_index(const entry *a, const entry *b) { return a->idx < b->idx ? -1 : a->idx != b->idx; }

/* Pass 1: groups together, each in queue order. */
static int group_cmp(const entry *a, const entry *b) {
    int d = key_cmp(a, b);
    return d ? d : by_index(a, b);
}

/* Pass 2: the groups in their random order; an album as the stock album page orders it (disc,
 * then track: getMusicByAlbum's sort @0x4e9020), then by path, so an untagged album keeps its
 * file-name order (q2-pod album_before); a folder by path; a CUE image's tracks by start. */
static int play_cmp(const entry *a, const entry *b) {
    void *ra = a->rec, *rb = b->rec;
    int d;
    if (a->group != b->group) return a->group < b->group ? -1 : 1;
    if (!by_folder) {
        d = I(ra, REC_DISC) - I(rb, REC_DISC);
        if (!d) d = I(ra, REC_TRACK) - I(rb, REC_TRACK);
        if (d) return d;
    }
    d = strcmp(str(ra, REC_PATH), str(rb, REC_PATH));
    if (!d) d = I(ra, REC_CUE_START) - I(rb, REC_CUE_START);
    return d ? d : by_index(a, b);
}

/* Reorder queue (n songs) into albums or folders in random order, each in its own order. 0 when
 * the index could not be allocated (the queue is then untouched). */
static int group_order(void *queue, unsigned n, int folders) {
    entry *v = calloc(n, sizeof *v);
    unsigned *rank, groups = 0, i, j, k;
    char tmp[REC_SIZE];
    if (!v) return 0;
    by_folder = folders;
    for (i = 0; i < n; ++i) {
        v[i].rec = deque_at(queue, i), v[i].idx = i;
        if (folders) v[i].dir = dir_len(str(v[i].rec, REC_PATH)); /* once per song, not on every comparison */
    }
    sort(v, n, group_cmp);
    for (i = 0; i < n; ++i) { /* number the groups, in sorted order */
        if (i && key_cmp(&v[i - 1], &v[i])) ++groups;
        v[i].group = groups;
    }
    ++groups;
    rank = calloc(groups, sizeof *rank);
    if (!rank) {
        free(v);
        return 0;
    }
    for (i = 0; i < groups; ++i) rank[i] = i;
    for (i = groups; i > 1; --i) { /* Fisher-Yates (q2-pod make_order's group ranks) */
        unsigned t;
        j = rand_below(i);
        t = rank[i - 1], rank[i - 1] = rank[j], rank[j] = t;
    }
    for (i = 0; i < n; ++i) v[i].group = rank[v[i].group];
    free(rank);
    sort(v, n, play_cmp);
    /* new[i] = old[v[i].idx]: follow each cycle with one record of temporary storage. A record's
     * strings stay owned by exactly one slot, so the deque frees them as usual. */
    for (i = 0; i < n; ++i) {
        if (v[i].group == ~0u) continue;
        if (v[i].idx == i) {
            v[i].group = ~0u;
            continue;
        }
        memcpy(tmp, deque_at(queue, i), REC_SIZE);
        for (j = i;; j = k) {
            k = v[j].idx;
            v[j].group = ~0u;
            if (k == i) break;
            memcpy(deque_at(queue, j), deque_at(queue, k), REC_SIZE);
        }
        memcpy(deque_at(queue, j), tmp, REC_SIZE);
    }
    free(v);
    return 1;
}

/* ---------------------------------------------------------------------------
 * The rows. 0 once Now Playing is opened, -1 with a message otherwise (nothing changed then: the
 * play mode is only set once the queue is ready and its first track is on the card).
 */
int shuffle_play(int kind) {
    void *list, *queue, *pick, *first;
    unsigned n, at = 0, idx = 0;
    int found;
    struct {
        void *dq;
        int idx, cls, mode;
    } context;
    if (kind < SHUFFLE_SONGS || kind > SHUFFLE_FOLDERS) return -1;
    /* the library, exactly as the Songs page loads it */
    list = loadLocalClassList(CLASS_ALL_SONGS) > 0 ? *(void **)PDEQ_SHOWLIST : (void *)0;
    n = list ? deque_size(list) : 0;
    if (!n) {
        toast(TR("Update Local Music first"));
        return -1;
    }
    if (kind != SHUFFLE_SONGS && n > SHUFFLE_MAX) {
        toast(TR("Too many songs to shuffle"));
        return -1;
    }
    if (kind == SHUFFLE_SONGS) at = rand_below(n);
    pick = deque_at(list, at);
    queue = _create_deque("stSongInfo");
    if (!queue) return -1;
    deque_init(queue);
    /* the Songs page's row handler: the queue of the list's songs and the memory-playback record */
    found = loadSongList(queue, str(pick, REC_NAME), I(pick, REC_CUE_START), CLASS_ALL_SONGS);
    n = deque_size(queue);
    if (kind == SHUFFLE_SONGS && n) {
        /* loadSongList finds a song by file name and CUE start, so a duplicate name (01.flac in
         * every album) would always start at the first; the drawn row's own index wins when it is
         * the same song */
        if (at < n && !strcmp(str(deque_at(queue, at), REC_PATH), str(pick, REC_PATH))) idx = at;
        else if (found >= 0 && (unsigned)found < n) idx = (unsigned)found;
    } else if (n && !group_order(queue, n, kind == SHUFFLE_FOLDERS)) {
        deque_destroy(queue);
        toast(TR("Not enough memory"));
        return -1;
    }
    first = n ? deque_at(queue, idx) : (void *)0;
    if (!first || access(str(first, REC_PATH), F_OK)) {
        deque_destroy(queue);
        toast(TR(n ? "Storage unavailable" : "Update Local Music first"));
        return -1;
    }
    /* Shuffle Songs is stock Shuffle over the whole library: it draws every next song from the
     * songs not played yet and starts again when they are all played. Albums and folders play
     * the queue in order. */
    if (kind == SHUFFLE_SONGS) set_mode(MODE_SHUFFLE);
    else set_in_order();
    *(int *)G_CLASS_TYPE = CLASS_ALL_SONGS; /* as allmusic_page_init leaves it (@0x5289e8) */
    context.dq = queue, context.idx = (int)idx, context.cls = CLASS_ALL_SONGS, context.mode = PLAY_MODE;
    navigator_to_with_context("playing_page", &context); /* start_player copies the queue */
    deque_destroy(queue);
    return 0;
}

/* The album page's and the Songs page's Play and Shuffle buttons (patch/albuminfo.c, patch/songs.c)
 * use the same generator, message box and play-mode setters as the rows above: Shuffle sets stock
 * Shuffle, Play the in-order mode, so Now Playing plays what was asked for. */
unsigned pod_rand(unsigned n) { return rand_below(n); }
void pod_toast(const char *text) { toast(text); }
void pod_set_mode(int mode) { set_mode(mode); }
void pod_set_in_order(void) { set_in_order(); }
