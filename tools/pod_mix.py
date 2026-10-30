#!/usr/bin/env python3
"""The Daily Mix model (docs/modules/dailymix.md): the day's mix of songs, its files, and the helpers the card needs. The reference that
patch/dailymix.c mirrors line by line (integers only; test/pod/dailymix.py runs the compiled code against it on random libraries) and the
reader / writer of the two files the card is made from, as tools/pod_recent.py models patch/recent.c. Every number is in patch/offsets.inc (MIX_*, DM_*).

A song is a dict: path, artist, album (str), plays (the Most Played count, 0 if none), recpos (its place in Recently Played, 0 = the last one played, None
when it is not among the last 100), fav (a favourite).

  score    MIX_W_PLAYS * lg(plays) + MIX_W_ARTIST * lg(the artist's plays over the whole library) + novelty + favourite - recent + jitter(seed, path)
  select   nothing under MIX_MIN_LIB songs; else MIX_SONGS songs, best score first, at most MIX_PER_ARTIST of one artist and MIX_PER_ALBUM of one album
           (loosened to MIX_PER_ARTIST2 / MIX_PER_ALBUM2, then no limit, while the mix is short; an untagged artist or album is the song's folder); then a
           seeded shuffle and a pass that pulls apart two songs of one artist side by side
"""
import os, re, struct

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
M = 0xFFFFFFFF
FNV_SEED = 2166136261


def _offsets():
    out = {}
    for line in open(os.path.join(ROOT, 'patch', 'offsets.inc')):
        m = re.match(r'#define (\w+) (-?(?:0x[0-9a-fA-F]+|\d+))u?\s*(?:/\*.*)?$', line.strip())
        if m: out[m.group(1)] = int(m.group(2), 0)
    return out


O = _offsets()
SONGS, MIN_SONGS, PER_ARTIST, PER_ALBUM = O['MIX_SONGS'], O['MIX_MIN_SONGS'], O['MIX_PER_ARTIST'], O['MIX_PER_ALBUM']
MIN_LIB = O['MIX_MIN_LIB']
CAPS = ((PER_ARTIST, PER_ALBUM), (O['MIX_PER_ARTIST2'], O['MIX_PER_ALBUM2']), (255, 255))   # the limits, loosened a step while the mix is short
W_PLAYS, W_ARTIST, NOVEL0, NOVEL1, W_FAV, W_RECENT = (O[k] for k in ('MIX_W_PLAYS', 'MIX_W_ARTIST', 'MIX_NOVEL0', 'MIX_NOVEL1', 'MIX_W_FAV', 'MIX_W_RECENT'))
JITTER, PLAYS_CAP, ARTIST_CAP, ALBUMS = O['MIX_JITTER'], O['MIX_PLAYS_CAP'], O['MIX_ARTIST_CAP'], O['MIX_ALBUMS']
MAX_NAMES, NAME, FILE_MAX, ART_HEAD, PATH = O['DM_MAX_NAMES'], O['DM_NAME'], O['DM_FILE_MAX'], O['DM_ART_HEAD'], O['DM_PATH']
W, H = O['DM_W'], O['DM_H']
PALETTE = ((70, 110, 190), (190, 90, 120), (60, 140, 150), (150, 120, 70))     # the tones a mix without covers gets (patch/dailymix.c dm_palette)
MIX_MAGIC, ART_MAGIC = b'M1X2\n', b'M1XA'


# ---- hashes and the generator (patch/covercache.c cc_fnv, patch/dailymix.c) ------------------------------------------------------------------
def b(s): return s if isinstance(s, bytes) else s.encode('utf-8')


def cc_fnv(s, h=FNV_SEED):
    """patch/covercache.c cc_fnv: FNV-1a over the bytes, then one more multiply."""
    for c in b(s): h = ((h ^ c) * 16777619) & M
    return (h * 16777619) & M


def fold_hash(s):
    """The identity of an artist or an album: FNV-1a with ASCII letters folded to lower case (what the stock album list groups by), never 0."""
    h = FNV_SEED
    for c in b(s): h = ((h ^ (c + 32 if 65 <= c <= 90 else c)) * 16777619) & M
    return h or 1


def tag_hash(tag, path):
    """patch/dailymix.c dm_tag: the identity of a song's artist or album, or for an untagged song its folder (the path up to the last '/')."""
    if b(tag): return fold_hash(tag)
    p = b(path)
    return fold_hash(p[:max(p.rfind(b'/'), 0)])


def xorshift32(x):
    x &= M
    x ^= (x << 13) & M; x ^= x >> 17; x ^= (x << 5) & M
    return x


def lg16(n):
    """16 * log2(1 + n), integer: the octave and four bits of the mantissa."""
    v = n + 1
    e = v.bit_length() - 1
    return 16 * e + (((v << (31 - e)) & M) >> 27 & 15)


def seed_for(day, regen):
    """The mix's seed: the day number, and how often the mix of that day was made again (Customize > Home Screen > Regenerate Daily Mix)."""
    return (((day * 2654435761) & M) ^ ((regen * 0x85EBCA6B) & M)) or 1


def art_seed(seed, first_path):
    return (seed ^ cc_fnv(first_path)) & M


def jitter(seed, path_hash):
    return xorshift32(xorshift32((path_hash ^ seed) | 1)) & (JITTER - 1)


# ---- the mix ---------------------------------------------------------------------------------------------------------------------------------
def score(s, artist_total, seed):
    plays = min(s['plays'], 65535)
    v = W_PLAYS * lg16(min(plays, PLAYS_CAP)) + W_ARTIST * lg16(min(artist_total, ARTIST_CAP))
    if plays == 0: v += NOVEL0
    elif plays == 1: v += NOVEL1
    if s['fav']: v += W_FAV
    if s['recpos'] is not None: v -= W_RECENT * (100 - s['recpos']) // 100
    return v + jitter(seed, cc_fnv(s['path']))


def select(songs, seed):
    """The indices of the mix's songs in play order: none for a library under MIN_LIB songs, else SONGS (the limits loosen while the mix is short)."""
    n = len(songs)
    if n < MIN_LIB: return []
    art = [tag_hash(s['artist'], s['path']) for s in songs]
    alb = [tag_hash(s['album'], s['path']) for s in songs]
    total = {}
    for s, a in zip(songs, art): total[a] = min(65535, total.get(a, 0) + min(s['plays'], 65535))
    sc = [score(s, total[a], seed) for s, a in zip(songs, art)]
    ca, cb, used, picks, lvl = [0] * n, [0] * n, [False] * n, [], 0
    while len(picks) < SONGS:
        best = -1
        for i in range(n):
            if used[i] or ca[i] >= CAPS[lvl][0] or cb[i] >= CAPS[lvl][1]: continue
            if best < 0 or sc[i] > sc[best]: best = i
        if best < 0:
            if lvl == len(CAPS) - 1: break
            lvl += 1
            continue
        used[best] = True; picks.append(best)
        for i in range(n):
            if art[i] == art[best]: ca[i] += 1
            if alb[i] == alb[best]: cb[i] += 1
    k = len(picks)
    r = xorshift32(seed | 1)
    for i in range(k - 1, 0, -1):
        r = xorshift32(r)
        j = r % (i + 1)
        picks[i], picks[j] = picks[j], picks[i]
    bad = lambda t: 0 < t < k and art[picks[t]] == art[picks[t - 1]]
    for i in range(1, k):
        if not bad(i): continue
        for j in range(i + 1, k):
            picks[i], picks[j] = picks[j], picks[i]
            if not any(bad(t) for t in (i, i + 1, j, j + 1)): break
            picks[i], picks[j] = picks[j], picks[i]
    return picks


def ranked(items, key):
    """items (strings) by how often their key occurs, the most first, ties by first appearance: [(representative string, count)]."""
    order, count, first = [], {}, {}
    for s in items:
        k = key(s)
        if k not in count: order.append(k); count[k] = 0; first[k] = s
        count[k] += 1
    order.sort(key=lambda k: -count[k])      # (sorted is stable: equal counts keep their first appearance)
    return [(first[k], count[k]) for k in order]


def top_artists(songs, picks):
    return [a for a, _ in ranked([songs[i]['artist'] for i in picks], fold_hash)][:MAX_NAMES]


def top_albums(songs, picks):
    return [a for a, _ in ranked([songs[i]['album'] for i in picks], fold_hash)][:ALBUMS]


def fill_tones(found, seed):
    """The tones the art gets: those of the covers found (up to 3); fewer than two are completed from the fixed palette, starting at seed % 4."""
    found = list(found)
    if len(found) >= 2: return found
    return found + [PALETTE[(seed % 4 + k) % 4] for k in range(3 - len(found))]


# ---- the two files ---------------------------------------------------------------------------------------------------------------------------
def _clean(s):
    return b(s) and all(c >= 0x20 and c != 0x7f for c in b(s)) and len(b(s)) < NAME


def dump_mix(day, seed, aseed, regen, tones, names, paths):
    """The mix file: M1X2, day / seed / art seed / regeneration count / songs, 2..4 tones (6 hex each), 1..3 names, then the songs' paths in play order, one a line (count of them).
    No stock playlist holds the mix: this file is the whole of it. It lives on the card, in /mnt/mmc/.m1plus/daily-mix/tracks (each card carries its own mix), under a name that is not .m3u / .m3u8 (the stock Import reads only the card's _explaylist_data)."""
    head = '%d\t%08x\t%08x\t%d\t%d\n' % (day, seed, aseed, regen, len(paths))
    return (MIX_MAGIC + head.encode() + ' '.join('%02x%02x%02x' % tuple(t) for t in tones).encode() + b'\n' + b'\t'.join(b(n) for n in names) + b'\n'
            + b''.join(b(p) + b'\n' for p in paths))


def parse_mix(data):
    """The strict reader (patch/dailymix.c dm_load): (day, seed, artseed, regen, count, tones, names, paths) or None. Names and paths are bytes."""
    if isinstance(data, str): data = data.encode('latin-1')
    if not data.startswith(MIX_MAGIC) or len(data) > FILE_MAX or not data.endswith(b'\n'): return None
    lines = data[len(MIX_MAGIC):-1].split(b'\n')
    f = lines[0].split(b'\t')
    if len(f) != 5: return None
    dec, hx = re.compile(rb'(0|[1-9][0-9]{0,8})\Z'), re.compile(rb'[0-9a-f]{8}\Z')
    if not (dec.match(f[0]) and hx.match(f[1]) and hx.match(f[2]) and dec.match(f[3]) and dec.match(f[4])): return None
    day, seed, aseed, regen, count = int(f[0]), int(f[1], 16), int(f[2], 16), int(f[3]), int(f[4])
    if not (day >= 1 and seed and regen <= 255 and MIN_SONGS <= count <= SONGS and len(lines) == 3 + count): return None
    ts = lines[1].split(b' ')
    if not (2 <= len(ts) <= 4 and all(re.match(rb'[0-9a-f]{6}\Z', t) for t in ts)): return None
    tones = [tuple(int(t[i:i + 2], 16) for i in (0, 2, 4)) for t in ts]
    names = lines[2].split(b'\t')
    if not (1 <= len(names) <= MAX_NAMES and all(_clean(n) for n in names)): return None
    paths = lines[3:]
    if not all(0 < len(p) < PATH and all(c >= 0x20 and c != 0x7f for c in p) for p in paths): return None
    return day, seed, aseed, regen, count, tones, names, paths


def fnv1a(data):
    h = FNV_SEED
    for c in data: h = ((h ^ c) * 16777619) & M
    return h


def dump_art(px565, aseed):
    """The art file: M1XA, width, height (u16), the art seed (u32), the FNV-1a of the pixels (u32), then W x H RGB565 words (little endian)."""
    body = struct.pack('<%dH' % len(px565), *px565)
    return ART_MAGIC + struct.pack('<HHII', W, H, aseed, fnv1a(body)) + body


def parse_art(data, aseed):
    """The pixels (a list of RGB565 words) when the file is whole and made for this art seed, else None."""
    if len(data) != ART_HEAD + W * H * 2 or data[:4] != ART_MAGIC: return None
    w, h, s, ck = struct.unpack_from('<HHII', data, 4)
    if (w, h) != (W, H) or s != aseed or ck != fnv1a(data[ART_HEAD:]): return None
    return list(struct.unpack_from('<%dH' % (W * H), data, ART_HEAD))
