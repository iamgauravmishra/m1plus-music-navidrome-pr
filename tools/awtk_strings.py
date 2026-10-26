#!/usr/bin/env python3
"""Read / write AWTK string tables (assets/default/raw/strings/<lang>_<COUNTRY>.bin).

Format (as shipped on Shanling X2000 firmware; locale_info_tr 0x658db4 -> str_table_lookup 0x658cd8):
  u16 0, u16 count                      (little endian)
  count x { u32 key offset, u32 value offset }    offsets from the start of the file; the entries are
                                        sorted by key (strcmp, a binary search) so a table must stay sorted
  u32 0, u32 0                          (eight zero bytes before the first string)
  the strings: key\\0 value\\0 in entry order, UTF-8, nothing after the last NUL

Usage:
  awtk_strings.py dump FILE.bin             key = value lines
  awtk_strings.py roundtrip FILE.bin...     verify parse -> serialize reproduces the bytes
"""
import struct, sys


def parse(d):
    """[(key, value)] in file order; refuses anything serialize() would not reproduce byte for byte."""
    zero, n = struct.unpack_from('<HH', d, 0)
    assert zero == 0, 'unexpected header'
    offs = struct.unpack_from(f'<{2 * n}I', d, 4)
    assert d[4 + 8 * n:4 + 8 * n + 8] == bytes(8), 'unexpected padding'
    def s(o): return d[o:d.index(b'\0', o)].decode('utf-8')
    items = [(s(offs[2 * i]), s(offs[2 * i + 1])) for i in range(n)]
    assert serialize(items) == d, 'table does not round-trip byte-exact'
    return items


def serialize(items):
    n = len(items)
    assert n < 0x10000
    keys = [k.encode('utf-8') for k, _ in items]
    assert keys == sorted(keys), 'keys must be sorted (binary search by strcmp)'
    assert len(set(keys)) == n, 'duplicate key'
    pos = 4 + 8 * n + 8
    head, body = bytearray(struct.pack('<HH', 0, n)), bytearray()
    for k, (_, v) in zip(keys, items):
        v = v.encode('utf-8')
        assert b'\0' not in k + v
        head += struct.pack('<II', pos + len(body), pos + len(body) + len(k) + 1)
        body += k + b'\0' + v + b'\0'
    return bytes(head) + bytes(8) + bytes(body)


def load(path):
    with open(path, 'rb') as f: return parse(f.read())


def main():
    cmd, files = sys.argv[1], sys.argv[2:]
    if cmd == 'dump':
        for k, v in load(files[0]): print(f'{k} = {v}')
    elif cmd == 'roundtrip':
        bad = 0
        for f in files:
            try: parse(open(f, 'rb').read())
            except AssertionError as e: bad += 1; print('MISMATCH', f, e)
        print(f'{len(files) - bad}/{len(files)} tables round-trip byte-exact'); sys.exit(1 if bad else 0)
    else: sys.exit(__doc__)


if __name__ == '__main__': main()
