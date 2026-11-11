/* M1+ Music Podcasts, the notes file: the writer (from the parser's kept items) and the bounded reader of one episode's note (patch/pcnotes.h).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 */
#include "offsets.inc"
#include "stock.h"
#include "podcasts.h"
#include "pcfeed.h"
#include "pcnotes.h"
#include "common.h"
#include "fnv.h"

#define PNO_CHUNK 1024
static const char pno_head[] = "M1PLUS-NOTES 1\n";

int pno_save(const char *path, const char *tmp, const struct pf_parser *pp) {
    const pf_parser_t *p = (const pf_parser_t *)pp;
    char *line = calloc(PF_NOTE_LINE + 1, 1);
    int i, n = pf_items(p), any = 0, ok = 1, fd = -1;
    if (!line) return 0;
    for (i = 0; i < n; ++i)
        if (pf_note(p, i)[0]) any = 1;
    if (!any) { /* nothing to say: an old file's notes belong to items that are gone */
        unlink(path);
        free(line);
        return 1;
    }
    fd = open(tmp, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    ok = fd >= 0 && write(fd, pno_head, sizeof pno_head - 1) == (int)(sizeof pno_head - 1);
    for (i = 0; ok && i < n; ++i) {
        unsigned len = pf_render_note(p, i, line, PF_NOTE_LINE + 1), at = 0;
        while (ok && at < len) {
            int w = write(fd, line + at, len - at);
            if (w <= 0)
                ok = 0;
            else
                at += (unsigned)w;
        }
    }
    ok = fd >= 0 && m1_commit(fd, ok, tmp, path);
    free(line);
    return ok;
}

enum { S_HEAD, S_START, S_GUID, S_TEXT, S_SKIP };

unsigned pno_read(const char *path, unsigned guid, char *out, unsigned cap) {
    char buf[PNO_CHUNK];
    int fd = open(path, O_RDONLY, 0), r, state = S_HEAD, esc = 0, cut = 0;
    unsigned total = 0, at = 0, h = 0, o = 0, k;
    if (cap) out[0] = 0;
    if (fd < 0 || cap < 2) {
        if (fd >= 0) close(fd);
        return 0;
    }
    while (total < PNO_FILE_MAX && (r = read(fd, buf, PNO_CHUNK)) > 0) {
        for (k = 0; k < (unsigned)r; ++k) {
            unsigned char c = (unsigned char)buf[k];
            switch (state) {
            case S_HEAD: /* the first line must be the header */
                if (c != (unsigned char)pno_head[at]) goto done;
                if (++at == sizeof pno_head - 1) state = S_START, at = 0;
                break;
            case S_START: /* "g=" at the start of a line, else the line is not one of ours */
                if (at == 0 && c == 'g')
                    at = 1;
                else if (at == 1 && c == '=')
                    state = S_GUID, h = pc_guid_hash("", 0), at = 0;
                else
                    state = c == '\n' ? S_START : S_SKIP, at = 0;
                break;
            case S_GUID: /* FNV-1a over the guid, as the model hashes g= (pc_guid_hash, byte by byte through the seed) */
                if (c == '\t') {
                    if ((h | !h) == guid)
                        state = S_TEXT, esc = 0, o = 0;
                    else
                        state = S_SKIP;
                } else if (c == '\n')
                    state = S_START, at = 0;
                else
                    h = (h ^ c) * FNV_PRIME;
                break;
            case S_TEXT:
                if (c == '\n' && !esc) goto done;
                if (!esc && c == '\\') {
                    esc = 1;
                    break;
                }
                if (esc) c = c == 'n' ? '\n' : c, esc = 0;
                if (o + 1 < cap)
                    out[o++] = (char)c;
                else
                    cut = 1;
                break;
            default: /* S_SKIP */
                if (c == '\n') state = S_START, at = 0;
            }
        }
        total += (unsigned)r;
    }
done:
    close(fd);
    if (state != S_TEXT) return 0;
    out[o] = 0;
    if (cut) { /* it did not fit: never end inside a character */
        unsigned j = o, need, lead;
        while (j && ((unsigned char)out[j - 1] & 0xc0) == 0x80) --j;
        if (j) {
            lead = (unsigned char)out[j - 1];
            need = lead >= 0xf0 ? 4u : lead >= 0xe0 ? 3u : lead >= 0xc0 ? 2u : 1u;
            if (o - (j - 1) < need) o = j - 1;
        }
        out[o] = 0;
    }
    return o;
}
