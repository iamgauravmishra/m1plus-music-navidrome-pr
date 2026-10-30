#!/usr/bin/env python3
"""The Recently Played list file of the menu's shelf (patch/recent.c, docs/modules/recent.md): the model the tests compare the payload with.

/mnt/data/m1plus-recent:

    M1R2\\n
    <id: 8 hex>\\t<cover key: 8 hex>\\t<0|1>\\t<album>\\t<artist>\\t<path of a track of the album>\\n        (one line per album, the most recent first)

The id is the album's identity: FNV-1a of its title with ASCII letters folded to lower case (identity()). The stock album list groups albums by title alone,
NOCASE (getAllAlbum: "group by album COLLATE NOCASE"), so a compilation's tracks, whatever their artists, are one album. The cover key is the Cover Flow
cache key (cc_album_key: FNV of artist then album) of the album's cover: the playing track's until the stock album row has been looked up (flag 0), the row's after
(flag 1; the artist is then the row's too). The album is never empty. Read strictly: the first line exactly the magic (an M1R1 file is not read: it reads as empty), at
most MAX lines of exactly six fields, non-zero ids and cover keys (no id twice), the flag 0 or 1, a non-empty album, no control byte (below 0x20, or 0x7f) in a field,
every line ended by a newline, names under STR bytes and paths under PATH, the whole file at most FILE_MAX bytes. Anything else is an empty list. Written only when the
most recent album changes (and once more when a cover key is resolved).
"""
MAGIC = b'M1R2\n'
MAX = 6            # patch/offsets.inc RC_MAX
STR = 96           # RC_STR: bytes of a name with its NUL
PATH = 256         # RC_PATH
FILE_MAX = 3072    # RC_FILE_MAX
FNV_SEED = 2166136261


def identity(album):
    """rc_id: the album title (str or UTF-8 bytes) folded to lower case ASCII, FNV-1a, never 0."""
    b = album.encode('utf-8') if isinstance(album, str) else album
    h = FNV_SEED
    for c in b: h = (h ^ (c + 32 if 65 <= c <= 90 else c)) * 16777619 & 0xffffffff
    return h or 1


def _clean(b):
    return not any(c < 0x20 or c == 0x7f for c in b)


def _hex8(b):
    return len(b) == 8 and all(c in b'0123456789abcdef' for c in b)


def parse(data):
    """The entries [(id, cover key, resolved, album, artist, path)] (strings keep the file's bytes decoded as latin-1), or [] when anything is malformed."""
    if not isinstance(data, bytes) or len(data) > FILE_MAX or not data.startswith(MAGIC):
        return []
    body = data[len(MAGIC):]
    out, seen = [], set()
    if body and not body.endswith(b'\n'):
        return []
    for line in body.split(b'\n')[:-1] if body else []:
        f = line.split(b'\t')
        if len(f) != 6 or len(out) >= MAX: return []
        key, ckey, res, album, artist, path = f
        if not _hex8(key) or not _hex8(ckey) or res not in (b'0', b'1'): return []
        k, ck = int(key, 16), int(ckey, 16)
        if not k or not ck or k in seen: return []
        if not album or len(album) >= STR or len(artist) >= STR or len(path) >= PATH: return []
        if not all(_clean(x) for x in (album, artist, path)): return []
        seen.add(k)
        out.append((k, ck, int(res), album.decode('latin-1'), artist.decode('latin-1'), path.decode('latin-1')))
    return out


def dump(entries):
    """The file for entries [(id, cover key, resolved, album, artist, path)] (latin-1 strings as parse gives them)."""
    return MAGIC + b''.join(b'%08x\t%08x\t%d\t%s\t%s\t%s\n' % (k, c, r, a.encode('latin-1'), ar.encode('latin-1'), p.encode('latin-1'))
                            for k, c, r, a, ar, p in entries)


def field(s, size):
    """What the payload stores of a name or path (rc_copy): control bytes as spaces, cut below `size` bytes without splitting a UTF-8 sequence.
    s is UTF-8 bytes; the result is bytes."""
    n = len(s)
    if n >= size:
        n = size - 1
        while n and (s[n] & 0xc0) == 0x80: n -= 1
    return bytes(32 if (c < 0x20 or c == 0x7f) else c for c in s[:n])


def note(entries, entry):
    """The list after a track of this album played: the album first (an album already in the list keeps its stored entry), no album twice, at most MAX."""
    old = next((e for e in entries if e[0] == entry[0]), None)
    return [old or entry] + [e for e in entries if e[0] != entry[0]][:MAX - 1]
