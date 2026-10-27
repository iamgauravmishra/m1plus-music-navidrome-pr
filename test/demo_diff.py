#!/usr/bin/env python3
"""Check that a built demo differs from the stock demo only where the mods say.

usage: python3 -I test/demo_diff.py <stock demo> <built demo>

Allowed differences: the zeroed .pdr section (space step), the program headers (the payload PT_LOAD),
the 8-byte Home-icon hook at 0x533b80, the 8-byte boot guard hook at home_page_init 0x534cd4, the 8-byte
album header hook at albuminfo_listitem0_layout 0x526264, the 8-byte Now Playing hook at playing_page_init
0x53d1e4, the 8-byte More dialog hook at dialog_playmore_dialog_init 0x479cc4, the one data word g_scroll_view_vtable + 0x98 (0x97a330, patch/scroll.c), the words listed in patch/rows.json, the four cover-size immediates of the lock screen (each must be
stock | 264), the five A-B marker immediates of Now Playing (tools/mod_nowplaying.py marker_edits) and bytes
appended after the stock file. Anything else is an error. Exit status 0 = clean.
"""
import json, os, struct, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(os.path.join(ROOT, 'tools'))
import mod_nowplaying as mn
HOOK = (0x533b80, 8)
HOME_INIT = (0x534cd4, 8)   # home_page_init: the boot guard's hook (docs/architecture.md)
ALBUMINFO = (0x526264, 8)   # albuminfo_listitem0_layout: the album header hook (patch/albuminfo.c)
PLAYING = (0x53d1e4, 8)     # playing_page_init: the Now Playing hook (patch/nowplaying.c)
PLAYMORE = (0x479cc4, 8)    # dialog_playmore_dialog_init: the More menu hook (patch/playmore.c)
SCROLL_SLOT = (0x97a330, 4) # g_scroll_view_vtable.on_event_before_children: 0 in stock, the payload's m1pod_scroll_event (patch/scroll.c)
COVER = 264                 # the cover size demo writes (tools/mod_lockscreen.py, Now Playing's art)
COVER_IMM = (0x4df1dc, 0x4df1e0, 0x4df21c, 0x4df220)

def segs(b):
    phoff = struct.unpack_from('<I', b, 28)[0]; size, num = struct.unpack_from('<HH', b, 42)
    return phoff, size, num, [struct.unpack_from('<8I', b, phoff + i * size) for i in range(num)]

def va_to_off(b, va):
    for t, o, v, _, f, m, fl, al in segs(b)[3]:
        if t == 1 and v <= va < v + f: return o + va - v
    raise ValueError(hex(va))

def sections(b):
    shoff = struct.unpack_from('<I', b, 32)[0]; shsize, shnum, shstr = struct.unpack_from('<HHH', b, 46)
    sh = [struct.unpack_from('<10I', b, shoff + i * shsize) for i in range(shnum)]
    names = sh[shstr][4]
    out = {}
    for s in sh:
        n = b[names + s[0]:b.index(b'\0', names + s[0])].decode()
        out[n] = (s[4], s[5])       # offset, size
    return out

def rows_words():
    """address -> stock word for every [addr, word, ...] entry in rows.json (the 'pinned' ones included)."""
    found = {}
    def walk(x):
        if isinstance(x, list):
            if len(x) >= 2 and isinstance(x[0], str) and isinstance(x[1], str) and x[0].startswith('0x') and x[1].startswith('0x'):
                found[int(x[0], 16)] = int(x[1], 16)
            else:
                for y in x: walk(y)
        elif isinstance(x, dict):
            for y in x.values(): walk(y)
    walk(json.load(open(os.path.join(ROOT, 'patch', 'rows.json'))))
    return found

def main():
    a = sys.argv[1:]
    s, m = open(a[0], 'rb').read(), open(a[1], 'rb').read()
    allowed = {}                      # byte offset -> reason
    def allow(off, n, why):
        for k in range(off, off + n): allowed[k] = why
    phoff, size, num, _ = segs(s)
    allow(phoff, size * num, 'phdrs')
    pdr = sections(s)['.pdr']; allow(pdr[0], pdr[1], 'pdr')
    allow(va_to_off(s, HOOK[0]), HOOK[1], 'hook')
    allow(va_to_off(s, HOME_INIT[0]), HOME_INIT[1], 'home-init hook')
    allow(va_to_off(s, ALBUMINFO[0]), ALBUMINFO[1], 'album header hook')
    allow(va_to_off(s, PLAYING[0]), PLAYING[1], 'playing init hook')
    allow(va_to_off(s, PLAYMORE[0]), PLAYMORE[1], 'more dialog init hook')
    allow(va_to_off(s, SCROLL_SLOT[0]), SCROLL_SLOT[1], 'scroll vtable slot')
    markers = mn.marker_edits()
    for va in markers: allow(va_to_off(s, va), 4, 'markers')
    rows = rows_words()
    for va in rows: allow(va_to_off(s, va), 4, 'rows')
    for va in COVER_IMM: allow(va_to_off(s, va), 4, 'cover')
    diff = [k for k in range(len(s)) if s[k] != m[k]]
    bad = [k for k in diff if k not in allowed]
    count = {}
    for k in diff: count[allowed.get(k)] = count.get(allowed.get(k), 0) + 1
    print(f'stock {len(s)} bytes, built {len(m)} bytes (appended {len(m) - len(s)}); differing bytes by region: {count}')
    ok = not bad and len(m) >= len(s)
    if bad: print('UNEXPECTED differing bytes at file offsets', [hex(k) for k in bad[:20]], '...' if len(bad) > 20 else '')
    # words: how many of the rows.json words changed, and what the cover words are
    changed = [va for va in rows if s[va_to_off(s, va):va_to_off(s, va) + 4] != m[va_to_off(m, va):va_to_off(m, va) + 4]]
    print(f'rows.json: {len(rows)} entries, {len(changed)} changed words')
    # the cover sites must not be among rows.json's words
    over = [hex(v) for v in COVER_IMM if v in rows]
    print('cover sites overlapping rows.json:', over or 'none')
    ok = ok and not over
    for va in COVER_IMM:
        o = va_to_off(s, va); sw = struct.unpack_from('<I', s, o)[0]; mw = struct.unpack_from('<I', m, o)[0]
        good = mw == (sw & 0xffff0000) | COVER
        print(f'cover {va:#x}: {sw:#010x} -> {mw:#010x}', 'ok' if good else 'WRONG')
        ok = ok and good
    h = HOOK[0]; o = va_to_off(s, h)
    print(f'hook {h:#x}: {s[o:o + 8].hex()} -> {m[o:o + 8].hex()}', 'changed' if s[o:o + 8] != m[o:o + 8] else 'unchanged')
    h = HOME_INIT[0]; o = va_to_off(s, h)
    print(f'home-init hook {h:#x}: {s[o:o + 8].hex()} -> {m[o:o + 8].hex()}', 'changed' if s[o:o + 8] != m[o:o + 8] else 'UNCHANGED')
    ok = ok and s[o:o + 8] != m[o:o + 8] and s[o + 8:o + 16] == m[va_to_off(m, h) + 8:va_to_off(m, h) + 16]
    h = ALBUMINFO[0]; o = va_to_off(s, h)
    print(f'album header hook {h:#x}: {s[o:o + 8].hex()} -> {m[o:o + 8].hex()}', 'changed' if s[o:o + 8] != m[o:o + 8] else 'UNCHANGED')
    ok = ok and s[o:o + 8] != m[o:o + 8] and s[o + 8:o + 16] == m[va_to_off(m, h) + 8:va_to_off(m, h) + 16]
    h = PLAYING[0]; o = va_to_off(s, h)
    print(f'Now Playing hook {h:#x}: {s[o:o + 8].hex()} -> {m[o:o + 8].hex()}', 'changed' if s[o:o + 8] != m[o:o + 8] else 'UNCHANGED')
    ok = ok and s[o:o + 8] != m[o:o + 8] and s[o + 8:o + 16] == m[va_to_off(m, h) + 8:va_to_off(m, h) + 16]
    h = PLAYMORE[0]; o = va_to_off(s, h)
    print(f'More dialog hook {h:#x}: {s[o:o + 8].hex()} -> {m[o:o + 8].hex()}', 'changed' if s[o:o + 8] != m[o:o + 8] else 'UNCHANGED')
    ok = ok and s[o:o + 8] != m[o:o + 8] and s[o + 8:o + 16] == m[va_to_off(m, h) + 8:va_to_off(m, h) + 16]
    o = va_to_off(s, SCROLL_SLOT[0]); sw = struct.unpack_from('<I', s, o)[0]; mw = struct.unpack_from('<I', m, o)[0]
    good = sw == 0 and 0xb00000 <= mw < 0xb00000 + (len(m) - len(s)) and mw % 4 == 0   # an empty slot, now a word inside the payload
    print(f'scroll_view before-children slot {SCROLL_SLOT[0]:#x}: {sw:#010x} -> {mw:#010x}', 'ok' if good else 'WRONG')
    ok = ok and good
    for va, (old, new) in markers.items():   # the A-B markers: the stock word in stock, the new one in the build
        o = va_to_off(s, va); sw = struct.unpack_from('<I', s, o)[0]; mw = struct.unpack_from('<I', m, o)[0]
        good = (sw, mw) == (old, new)
        print(f'marker {va:#x}: {sw:#010x} -> {mw:#010x}', 'ok' if good else 'WRONG')
        ok = ok and good
    print('OK (1 passed, 0 failed)' if ok else 'FAIL (0 passed, 1 failed)')
    return 0 if ok else 1

if __name__ == '__main__':
    sys.exit(main())
