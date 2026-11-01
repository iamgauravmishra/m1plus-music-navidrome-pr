/* The show's .notes file: the long plain-text descriptions of its kept episodes (patch/pcnotes.c; docs/modules/podcasts.md "The notes file").
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * `.notes` is `M1PLUS-NOTES 1`, then one line per kept item that has a long description: `g=<guid>\t<text>`, the text with its backslash written `\\` and each paragraph break `\n`
 * (two characters), no raw tab or newline. The refresh writes it with .episodes, from the 20 kept items only (the parser's pf_render_note), so a note leaves with its item. The
 * episode page reads one line, by the hash of the guid, with a bounded scan: never the whole file.
 */
#pragma once

#define PNO_FILE_MAX (256 * 1024) /* bytes of the file a scan looks at (20 lines of PF_NOTE_LINE are about 170 KB) */

struct pf_parser;

/* The notes of the parser's kept items into path, atomically (tmp: written, fsynced, renamed over path; a failure leaves no temp file). With no note to write an old file is removed (its notes are
 * of items that are gone). Returns 1 when the file is as asked, 0 when it could not be written. */
int pno_save(const char *path, const char *tmp, const struct pf_parser *p);

/* The note of the episode whose guid hashes to `guid` (pc_guid_hash) into out (cap bytes with the NUL): its paragraphs separated by '\n', cut on a UTF-8 boundary when it does not fit.
 * Reads the file 1 KB at a time (the stack holds the chunk) and stops at the line it wants; at most PNO_FILE_MAX bytes. Returns the length, 0 when there is no file, no such line or no text. */
unsigned pno_read(const char *path, unsigned guid, char *out, unsigned cap);
