/* M1+ Music Presets page: Download from AutoEq, then the card's preset files (docs/modules/peq.md "Presets page").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Opened by the Equalizer page's Presets card (patch/peq_ui.c, through peqlib_open and patch/m1plus.c open_page, which calls peqlib_opened).
 * A cards page: the download row, then a header AutoEq over the files with an AutoEq stamp (their first line, "# AutoEq: Source/Kind/Name",
 * patch/autoeq.c) and a header On Card over the others. Each file is a 60 px row: its name without .txt, a grey line ("Source · Kind" for an
 * AutoEq file, "On card" for the rest) and a chevron; a tap opens its Preset page (patch/peqpage.c). The rows are slots in the asset (AutoEq
 * slots first, then On Card's): the payload shows as many as there are, sets their pieces and hairlines, hides a header whose section is empty
 * and sets the column's height from the model (pod.py POD_LIB_*). Back in front the card is read again (a download may have added a file).
 */
#include "offsets.inc"
#include "stock.h"
#include "common.h"
#include "i18n.h"
#include "peq.h"
#include "autoeq.h"
#include "peqpage.h"
#include "peqlib.h"

extern int pod_open_peqlib(void); /* patch/m1plus.c: open_page(POD_PEQLIB_PAGE) */

#define LB_SLOTS \
    (2 * \
     PQ_ROWS) /* the rows after the download row: PQ_ROWS AutoEq slots, then PQ_ROWS On Card slots (row = slot + 1) */
#define LB_PATH (sizeof(PEQ_DIR) + PEQ_NAME + 1)
#define LB_STAMP 10 /* "# AutoEq: " */
#define LB_READ 270 /* the stamp's line: the index path is at most 200 bytes (patch/autoeq.c AE_PATH) */

static struct {
    void *win, *sv, *sec[2], *row[LB_SLOTS + 1], *label[LB_SLOTS + 1], *sub[LB_SLOTS + 1], *hair[LB_SLOTS + 1];
    char piece[LB_SLOTS + 1]; /* the card piece a row shows (peq_piece_set's cache) */
    char name[PQ_ROWS][PEQ_NAME]; /* the card's preset files, sorted */
    char file
        [LB_SLOTS]
        [PEQ_NAME]; /* the file of each slot: AutoEq ones from 0, the others from PQ_ROWS; "" for a slot that is not used */
} lb __attribute__((section(".scratch")));

/* A file's AutoEq stamp: its first line is "# AutoEq: Source/Kind/Name" (patch/autoeq.c ae_stamp). Returns 1 with the grey line in sub
 * ("Source · Over-ear": the kind's word when the directory ends with one, else the source alone); 0 for a file of the user's. */
static int lb_stamp(const char *file, char *sub, unsigned size) {
    static const char *const word[3] = {"over-ear", "in-ear", "earbud"};
    static const char *const shown[3] = {"Over-ear", "In-ear", "Earbud"};
    static const unsigned kinds[3] = {8, 6, 6}; /* the words' lengths */
    char path[LB_PATH], buf[LB_READ + 1];
    const char *p;
    unsigned n, a, b, dn, o = 0, k;
    int fd, got, i;
    snprintf(path, sizeof path, "%s/%s", PEQ_DIR, file);
    fd = open(path, O_RDONLY, 0);
    if (fd < 0) return 0;
    got = read(fd, buf, LB_READ);
    close(fd);
    if (got < LB_STAMP + 3) return 0;
    buf[got] = 0;
    for (i = 0; i < 17 && buf[i] == "# AutoEq edited: "[i]; i++) {
    }
    if (i == 17)
        p = buf + 17;
    else {
        for (i = 0; i < LB_STAMP && buf[i] == "# AutoEq: "[i]; i++) {
        }
        if (i < LB_STAMP) return 0;
        p = buf + LB_STAMP;
    }
    for (n = 0; p[n] && p[n] != '\r' && p[n] != '\n'; ++n) {
    }
    for (a = 0; a < n && p[a] != '/'; ++a) {
    }
    for (b = a + 1; b < n && p[b] != '/'; ++b) {
    }
    if (a == 0 || b >= n || b == a + 1) return 0; /* "Source/Kind/Name" */
    dn = b - a - 1;
    for (i = 0; i < 3; i++) {
        unsigned kn = kinds[i], j;
        for (j = 0; j < kn && dn >= kn && p[b - kn + j] == word[i][j]; j++) {
        }
        if (dn >= kn && j == kn) break;
    }
    /* the stamp keeps the source percent-encoded (it is the file's identity); only the grey line shows it decoded, cut back to a whole character */
    o = m1_url_decode(sub, size, p, a);
    for (k = o; k > 0 && ((unsigned char)sub[k - 1] & 0xc0) == 0x80; k--) {
    }
    if (k > 0) {
        unsigned char lead = (unsigned char)sub[k - 1];
        unsigned need = lead >= 0xf0 ? 4 : lead >= 0xe0 ? 3 : lead >= 0xc0 ? 2 : 1;
        if (need > o - (k - 1)) o = k - 1;
    }
    if (i < 3) {
        const char *w = TR(shown[i]);
        for (k = 0; k < 4 && o + 1 < size; k++) sub[o++] = " \xc2\xb7 "[k];
        for (k = 0; w[k] && o + 1 < size; k++) sub[o++] = w[k];
    }
    sub[o] = 0;
    return 1;
}

/* The card's rows: the files in order, AutoEq first. Rows of a section that is empty are hidden, and its header with them; the pieces are the
 * section's (a top, the middle ones, a bottom; a single one alone) and a hairline under every row but the section's last. */
static void lb_layout(void) {
    int i, n, na = 0, nc = 0, s, vh, max;
    char sub[96];
    n = peq_list(lb.name, PQ_ROWS, (int *)0);
    memset(lb.file, 0, sizeof lb.file);
    for (i = 0; i < n; i++) {
        if (lb_stamp(lb.name[i], sub, sizeof sub))
            memcpy(lb.file[na++], lb.name[i], PEQ_NAME);
        else
            memcpy(lb.file[PQ_ROWS + nc++], lb.name[i], PEQ_NAME);
    }
    for (s = 0; s < LB_SLOTS; s++) {
        int ae = s < PQ_ROWS, j = ae ? s : s - PQ_ROWS, count = ae ? na : nc, row = s + 1, p;
        int on = j < count;
        m1_show(lb.row[row], on);
        if (!on) continue;
        {
            char shown[PEQ_NAME];
            peq_shown(shown, sizeof shown, lb.file[s]);
            widget_set_text_utf8(lb.label[row], shown);
        }
        if (!ae || !lb_stamp(lb.file[s], sub, sizeof sub)) snprintf(sub, sizeof sub, "%s", TR("On card"));
        widget_set_text_utf8(lb.sub[row], sub);
        p = count == 1 ? 0 : j == 0 ? 1 : j == count - 1 ? 3 : 2;
        peq_piece_set(lb.row[row], &lb.piece[row], p, 1);
        if (lb.hair[row]) widget_set_visible(lb.hair[row], j < count - 1, 0);
    }
    m1_show(lb.sec[0], na != 0);
    m1_show(lb.sec[1], nc != 0);
    /* the column's height as the layouter makes it (the download row, the two spacers and the visible headers and rows): set now, so that a list
     * that got shorter is not left scrolled past its end */
    vh = POD_LIB_BASE + (na ? POD_LIB_HDR + na * POD_LIB_ROW : 0) + (nc ? POD_LIB_HDR + nc * POD_LIB_ROW : 0);
    widget_set_prop_int(lb.sv, "virtual_h", vh);
    max = vh - widget_get_prop_int(lb.sv, "h", 0);
    if (max < 0) max = 0;
    if (widget_get_prop_int(lb.sv, "yoffset", 0) > max) widget_set_prop_int(lb.sv, "yoffset", max);
}

static int lb_on_download(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    autoeq_open();
    return RET_OK;
}

/* A tap on a file's row opens its Preset page (patch/peqpage.c: the file is parsed there first). */
static int lb_on_file(void *ctx, void *e) {
    int s = (int)(long)ctx;
    (void)e;
    if (s < 0 || s >= LB_SLOTS || !lb.file[s][0]) return RET_OK;
    peqpage_show(lb.file[s]);
    return RET_OK;
}

static int lb_on_fg(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    if (lb.win) lb_layout();
    return RET_OK;
}

static int lb_on_destroy(void *ctx, void *e) {
    (void)ctx;
    (void)e;
    memset(&lb, 0, sizeof lb);
    return RET_OK;
}

int peqlib_open(void) { return pod_open_peqlib() == 0; }

/* The Presets page is up (patch/m1plus.c open_page): find its rows, read the card, bind. A page that is not our asset is left as it is. */
void peqlib_opened(void *win) {
    int i;
    char name[24];
    memset(&lb, 0, sizeof lb);
    for (i = 0; i <= LB_SLOTS; i++) {
        snprintf(name, sizeof name, "pod_row%d", i);
        lb.row[i] = widget_lookup(win, name, 1);
        if (!lb.row[i]) goto bad;
        if (i) {
            snprintf(name, sizeof name, "pod_label%d", i);
            lb.label[i] = widget_lookup(win, name, 1);
            snprintf(name, sizeof name, "pod_sub%d", i);
            lb.sub[i] = widget_lookup(win, name, 1);
            if (!lb.label[i] || !lb.sub[i]) goto bad;
        }
        lb.hair[i] = widget_lookup(lb.row[i], "pod_hair", 1); /* the asset's last row of a section has none */
    }
    lb.sec[0] = widget_lookup(win, "pod_sec0", 1);
    lb.sec[1] = widget_lookup(win, "pod_sec1", 1);
    lb.sv = widget_lookup(win, "pod_scrollview", 1);
    if (!lb.sec[0] || !lb.sec[1] || !lb.sv) goto bad;
    lb.win = win;
    lb_layout();
    widget_on(lb.row[0], EVT_CLICK, lb_on_download, (void *)0);
    for (i = 1; i <= LB_SLOTS; i++) widget_on(lb.row[i], EVT_CLICK, lb_on_file, (void *)(long)(i - 1));
    widget_on(win, EVT_WINDOW_TO_FG, lb_on_fg, (void *)0);
    widget_on(win, EVT_DESTROY, lb_on_destroy, (void *)0);
    return;
bad: /* an asset that is not ours */
    memset(&lb, 0, sizeof lb);
}
