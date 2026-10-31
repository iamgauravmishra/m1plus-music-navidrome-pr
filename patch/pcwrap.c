/* Line breaking for the Podcasts Show page (patch/pcwrap.h): greedy, latin at spaces, CJK anywhere, with the kinsoku rules.
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#include "pcwrap.h"

#define PW_ELLIPSIS 0x2026u

/* Characters that may break anywhere: CJK ideographs, kana and symbols (U+2E80 .. U+9FFF), the fullwidth forms (U+FF00 .. U+FFEF) and the curly double quotes. */
static int pw_cjk(unsigned c) {
    return (c >= 0x2e80 && c <= 0x9fff) || (c >= 0xff00 && c <= 0xffef) || c == 0x201c || c == 0x201d;
}

/* No line starts with these: closing punctuation, the ellipsis and the dash (tools/pod_wrap.py NO_START). */
static int pw_no_start(unsigned c) {
    static const unsigned short set[] = {0xff0c, 0x3002, 0x3001, 0xff01, 0xff1f, 0xff1b, 0xff1a, 0xff09,
                                         0x201d, 0x2019, 0x300b, 0x300d, 0x300f, 0x3011, 0x2026, 0x2014,
                                         ',',    '.',    '!',    '?',    ';',    ':',    ')'};
    unsigned i;
    for (i = 0; i < sizeof set / sizeof *set; ++i)
        if (c == set[i]) return 1;
    return 0;
}

/* No line ends with these: opening quotes and brackets (tools/pod_wrap.py NO_END). */
static int pw_no_end(unsigned c) {
    static const unsigned short set[] = {0x201c, 0x2018, 0xff08, 0x300a, 0x300c, 0x300e, 0x3010, '('};
    unsigned i;
    for (i = 0; i < sizeof set / sizeof *set; ++i)
        if (c == set[i]) return 1;
    return 0;
}

/* A line may start at s[o] (0 < o < n): after a space, before one, or next to a CJK character. */
static int pw_brk(const unsigned *s, int o) {
    return s[o - 1] == ' ' || s[o] == ' ' || pw_cjk(s[o - 1]) || pw_cjk(s[o]);
}

int pw_wrap(unsigned *s, int n, const unsigned short *adv, int room, int maxl, int ellw, pw_line_t *out) {
    int p = 0, l = 0;
    while (l < maxl) {
        int i, w = 0, q, e, o;
        while (p < n && s[p] == ' ') ++p;
        if (p >= n) break;
        for (i = p; i < n && w + adv[i] <= room; ++i)
            w += adv[i]; /* i: the first char that does not fit, n when all do */
        if (i >= n) { /* the rest fits */
            e = n;
            while (e > p && s[e - 1] == ' ') --e;
            out[l].start = (short)p, out[l].len = (short)(e - p);
            return l + 1;
        }
        if (l ==
            maxl - 1) { /* the last line and text is left: the longest prefix that fits with the ellipsis after it */
            int k = p;
            w = 0;
            while (k < n && w + adv[k] + ellw <= room) w += adv[k], ++k;
            while (k > p && (s[k - 1] == ' ' || pw_no_end(s[k - 1]))) --k;
            s[k] = PW_ELLIPSIS; /* k <= i < n */
            out[l].start = (short)p, out[l].len = (short)(k - p + 1);
            return l + 1;
        }
        q = i; /* no opportunity: break before the char that does not fit */
        for (o = i; o > p; --o)
            if (pw_brk(s, o)) {
                q = o;
                break;
            }
        if (q <= p) q = p + 1; /* a glyph wider than the line: it alone */
        while (q > p + 1 && (pw_no_start(s[q]) || pw_no_end(s[q - 1]))) --q;
        e = q;
        while (e > p && s[e - 1] == ' ') --e;
        out[l].start = (short)p, out[l].len = (short)(e - p);
        ++l;
        p = q;
    }
    return l;
}
