#!/usr/bin/env python3
"""The Podcasts Show page's line breaking, in Python (patch/pcwrap.c is the same algorithm; test/pod/pcshow.py compares the two on a corpus, the preview uses this one).

wrap(text, adv, room, maxl, ellw) takes the string, the advance AWTK charges for each character (the glyph's width plus its 1 px: tools/awtk_text.py StbText) and the line room, and
returns the lines as strings: a latin line breaks after (or before) a space, a CJK line between any two characters, a word longer than the line anywhere; closing punctuation never
starts a line and an opening quote or bracket never ends one (kinsoku: the break moves back); when text is left after the last line, that line is cut with an ellipsis.
"""

ELLIPSIS = '…'
NO_START = '，。、！？；：）”’》」』】…—,.!?;:)'      # no line starts with these
NO_END = '“‘（《「『【('                              # no line ends with these


def is_cjk(c):
    o = ord(c)
    return 0x2e80 <= o <= 0x9fff or 0xff00 <= o <= 0xffef or o in (0x201c, 0x201d)


def brk(s, o):
    return s[o - 1] == ' ' or s[o] == ' ' or is_cjk(s[o - 1]) or is_cjk(s[o])


def wrap_spans(s, adv, room, maxl, ellw):
    """[(start, length)] of the lines of s and `cut`: the last line ends in an ellipsis in place of s[start + length - 1]."""
    n, p, out = len(s), 0, []
    while len(out) < maxl:
        while p < n and s[p] == ' ': p += 1
        if p >= n: break
        i, w = p, 0
        while i < n and w + adv[i] <= room: w += adv[i]; i += 1
        if i >= n:
            e = n
            while e > p and s[e - 1] == ' ': e -= 1
            out.append((p, e - p)); return out, False
        if len(out) == maxl - 1:
            k, w = p, 0
            while k < n and w + adv[k] + ellw <= room: w += adv[k]; k += 1
            while k > p and (s[k - 1] == ' ' or s[k - 1] in NO_END): k -= 1
            out.append((p, k - p + 1)); return out, True
        q = i
        for o in range(i, p, -1):
            if brk(s, o): q = o; break
        if q <= p: q = p + 1
        while q > p + 1 and (s[q] in NO_START or s[q - 1] in NO_END): q -= 1
        e = q
        while e > p and s[e - 1] == ' ': e -= 1
        out.append((p, e - p)); p = q
    return out, False


def wrap(text, adv, room, maxl, ellw):
    """The lines of text (strings). adv: the advance of each character of text; ellw: the ellipsis' advance."""
    spans, cut = wrap_spans(text, adv, room, maxl, ellw)
    lines = [text[a:a + n] for a, n in spans]
    if cut: lines[-1] = lines[-1][:-1] + ELLIPSIS
    return lines


def wrap_font(font, text, px, room, maxl):
    """wrap() with the advances of tools/awtk_text.py StbText `font` (an object with width(text, px) of the stb model: the sum of the glyphs' advance + 1)."""
    adv = [font.width(c, px) for c in text]
    return wrap(text, adv, room, maxl, font.width(ELLIPSIS, px))
