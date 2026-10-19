#!/usr/bin/env python3
"""Parse / serialize AWTK binary UI files (ui/*.bin, magic 0x11221212).

Format (as shipped on Shanling X2000 firmware, AWTK 1.x):
  u32 magic
  widget := char type[32]; i32 x, y, w, h; (key\0 value\0)* \0  children*  \0
A leading zero byte where a widget would start closes the current widget.

Usage:
  awtk_ui.py dump FILE.bin            print the widget tree
  awtk_ui.py roundtrip FILE.bin...    verify parse->serialize reproduces bytes
"""
import struct, sys, json

MAGIC = 0x11221212

class Widget:
    __slots__ = ('type', 'x', 'y', 'w', 'h', 'props', 'children')
    def __init__(self, type, x=0, y=0, w=0, h=0, props=None, children=None):
        self.type, self.x, self.y, self.w, self.h = type, x, y, w, h
        self.props = props if props is not None else []   # list of (key, value), ordered
        self.children = children if children is not None else []
    def get(self, key, default=None):
        for k, v in self.props:
            if k == key: return v
        return default
    def set(self, key, value):
        """Replace an existing prop in place, else append."""
        for i, (k, _) in enumerate(self.props):
            if k == key:
                self.props[i] = (key, value); return
        self.props.append((key, value))
    def remove(self, key):
        self.props = [(k, v) for k, v in self.props if k != key]
    @property
    def name(self): return self.get('name', '')
    def find(self, name):
        if self.name == name: return self
        for c in self.children:
            r = c.find(name)
            if r: return r
        return None
    def walk(self):
        yield self
        for c in self.children: yield from c.walk()
    def to_dict(self):
        return {'type': self.type, 'x': self.x, 'y': self.y, 'w': self.w, 'h': self.h,
                'props': self.props, 'children': [c.to_dict() for c in self.children]}

def _read_str(d, pos):
    e = d.index(b'\0', pos)
    return d[pos:e].decode('utf-8'), e + 1

def parse(d):
    assert len(d) >= 4 and struct.unpack('<I', d[:4])[0] == MAGIC, 'bad magic'
    pos, stack, root = 4, [], None
    while pos < len(d):
        if d[pos] == 0:
            pos += 1
            if stack: stack.pop()
            continue
        t = d[pos:pos + 32].split(b'\0')[0].decode()
        x, y, w, h = struct.unpack('<iiii', d[pos + 32:pos + 48]); pos += 48
        props = []
        while True:
            k, pos = _read_str(d, pos)
            if k == '': break
            v, pos = _read_str(d, pos)
            props.append((k, v))
        node = Widget(t, x, y, w, h, props)
        if stack: stack[-1].children.append(node)
        elif root is None: root = node
        else: raise ValueError('multiple roots')
        stack.append(node)
    assert root is not None, 'empty ui file'
    return root

def _ser(wd, out):
    t = wd.type.encode()
    assert len(t) < 32
    out += t + b'\0' * (32 - len(t)) + struct.pack('<iiii', wd.x, wd.y, wd.w, wd.h)
    for k, v in wd.props:
        out += k.encode() + b'\0' + v.encode() + b'\0'
    out += b'\0'
    for c in wd.children: _ser(c, out)
    out += b'\0'

def serialize(root):
    out = bytearray(struct.pack('<I', MAGIC)); _ser(root, out); return bytes(out)

def dump(wd, ind=0):
    print(f"{'  '*ind}{wd.type} name={wd.name!r} xywh=({wd.x},{wd.y},{wd.w},{wd.h})")
    for k, v in wd.props:
        if k != 'name': print(f"{'  '*ind}    {k} = {v!r}")
    for c in wd.children: dump(c, ind + 1)

if __name__ == '__main__':
    cmd, files = sys.argv[1], sys.argv[2:]
    if cmd == 'dump':
        dump(parse(open(files[0], 'rb').read()))
    elif cmd == 'roundtrip':
        bad = 0
        for f in files:
            d = open(f, 'rb').read()
            try: ok = serialize(parse(d)) == d
            except Exception as e: ok = False; print(f, 'ERROR', e)
            bad += not ok
            if not ok: print('MISMATCH', f)
        print(f'{len(files) - bad}/{len(files)} files round-trip byte-exact')
        sys.exit(1 if bad else 0)
