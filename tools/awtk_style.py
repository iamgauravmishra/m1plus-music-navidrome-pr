#!/usr/bin/env python3
"""Parse / serialize AWTK binary theme files (styles/*.bin, magic fd fc fb fa).

Format, as shipped on the Shanling X2000 firmware (AWTK 1.x theme_gen output); every stock
styles/*.bin under assets/default and assets/theme1 round-trips byte-exact through this module:

  header   u32 magic 0xfafbfcfd, u32 version (0), u32 nr
  items    nr x { u32 offset; char state[32]; char style[32]; char widget_type[32] }   (100 bytes)
           offset = file offset of the item's style block; stock items are sorted by offset and
           every block is used by exactly one item, laid out back to back after the item table
  block    u32 nr_props; nr_props x { u8 type; u8 key_size; u16 value_size;
                                     char key[key_size] (NUL included); u8 value[value_size] }
  type     AWTK value_type_t: 6 = int32, 7 = uint32, 14 = string (NUL-terminated, NUL counted)

A style is looked up by (widget_type, style name, state): a widget whose `style` property is
"foo" in state "pressed" gets item (its type, "foo", "pressed"). Colours are uint32 holding the
bytes r, g, b, a (AWTK color_t), i.e. little-endian 0xAABBGGRR; this module shows and takes them
as '#RRGGBBAA'. Keys are kept verbatim, including the odd stock ones with embedded whitespace
("i\\n    font_size"): theme_gen copied them from Shanling's XML and AWTK never matches them.

Python use (tools/mod_theme.py):
  th = awtk_style.parse(data); assert awtk_style.serialize(th) == data
  for it in th.find(widget='list_item', style='list_item_style'): it.set_color('bg_color', '#000000FF')
  awtk_style.serialize(th)          # re-lays every block and recomputes the offsets

Usage:
  awtk_style.py dump FILE.bin [STYLE...]      print the items (all, or only these style names)
  awtk_style.py roundtrip FILE.bin...         verify parse -> serialize reproduces the bytes
"""
import struct, sys

MAGIC = 0xfafbfcfd
ITEM = 100                     # u32 offset + 3 x char[32]
NAME = 32
T_INT32, T_UINT32, T_STRING = 6, 7, 14
COLOR_KEYS = ('color',)        # a uint32 key ending in one of these is a colour

def is_color_key(key): return key.endswith(COLOR_KEYS)

def color_to_str(v):
    """uint32 0xAABBGGRR -> '#RRGGBBAA'."""
    return '#' + struct.pack('<I', v).hex().upper()

def color_from_str(s):
    """'#RRGGBB' or '#RRGGBBAA' -> uint32 0xAABBGGRR (alpha defaults to FF)."""
    h = s.lstrip('#')
    if len(h) == 6: h += 'FF'
    assert len(h) == 8, f'bad colour {s!r}'
    return struct.unpack('<I', bytes.fromhex(h))[0]

class Item:
    """One (widget_type, style, state) entry and its ordered properties [(key, type, value)]."""
    __slots__ = ('widget', 'style', 'state', 'props')
    def __init__(self, widget, style, state, props=None):
        self.widget, self.style, self.state = widget, style, state
        self.props = props if props is not None else []
    def get(self, key, default=None):
        for k, t, v in self.props:
            if k == key: return v
        return default
    def has(self, key): return any(k == key for k, _, _ in self.props)
    def set(self, key, value, type=None):
        """Replace a property's value in place (keeping its type unless given), else append."""
        for i, (k, t, _) in enumerate(self.props):
            if k == key:
                self.props[i] = (key, t if type is None else type, value); return
        if type is None: type = T_STRING if isinstance(value, str) else T_UINT32
        self.props.append((key, type, value))
    def remove(self, key): self.props = [p for p in self.props if p[0] != key]
    def color(self, key):
        v = self.get(key)
        return None if v is None else color_to_str(v)
    def set_color(self, key, rgba): self.set(key, color_from_str(rgba), T_UINT32)
    def __repr__(self): return f'<{self.widget}/{self.style}/{self.state} {len(self.props)} props>'

class Theme:
    __slots__ = ('version', 'items')
    def __init__(self, items=None, version=0):
        self.version, self.items = version, items if items is not None else []
    def find(self, widget=None, style=None, state=None):
        return [it for it in self.items if (widget is None or it.widget == widget)
                and (style is None or it.style == style) and (state is None or it.state == state)]
    def styles(self):
        """Ordered unique (widget_type, style) pairs."""
        seen = {}
        for it in self.items: seen.setdefault((it.widget, it.style), None)
        return list(seen)

def _name(b): return b.split(b'\0')[0].decode('utf-8')

def _value(t, raw):
    if t == T_INT32: assert len(raw) == 4; return struct.unpack('<i', raw)[0]
    if t == T_UINT32: assert len(raw) == 4; return struct.unpack('<I', raw)[0]
    if t == T_STRING: assert raw[-1:] == b'\0' and b'\0' not in raw[:-1], raw; return raw[:-1].decode('utf-8')
    raise ValueError(f'unsupported value type {t}')

def _raw(t, v):
    if t == T_INT32: return struct.pack('<i', v)
    if t == T_UINT32: return struct.pack('<I', v)
    if t == T_STRING: return v.encode('utf-8') + b'\0'
    raise ValueError(f'unsupported value type {t}')

def parse(d):
    magic, version, nr = struct.unpack_from('<3I', d)
    assert magic == MAGIC, 'bad style magic'
    items, pos = [], 12 + ITEM * nr
    for i in range(nr):
        off, state, style, widget = struct.unpack_from('<I32s32s32s', d, 12 + ITEM * i)
        # strict layout: blocks back to back in item order, so serialize() can reproduce the bytes
        assert off == pos, f'item {i}: block at {off}, expected {pos} (shared or padded blocks are not supported)'
        n = struct.unpack_from('<I', d, pos)[0]; pos += 4
        props = []
        for _ in range(n):
            t, ks, vs = struct.unpack_from('<BBH', d, pos); pos += 4
            key = d[pos:pos + ks]; pos += ks
            assert ks and key[-1] == 0 and b'\0' not in key[:-1], f'bad key {key!r}'
            props.append((key[:-1].decode('utf-8'), t, _value(t, d[pos:pos + vs]))); pos += vs
        items.append(Item(_name(widget), _name(style), _name(state), props))
    assert pos == len(d), f'{len(d) - pos} trailing bytes'
    return Theme(items, version)

def _fixed(s):
    b = s.encode('utf-8'); assert len(b) < NAME, f'name too long: {s!r}'
    return b + b'\0' * (NAME - len(b))

def serialize(th):
    blocks = []
    for it in th.items:
        b = bytearray(struct.pack('<I', len(it.props)))
        for k, t, v in it.props:
            kb, vb = k.encode('utf-8') + b'\0', _raw(t, v)
            assert len(kb) < 256 and len(vb) < 65536
            b += struct.pack('<BBH', t, len(kb), len(vb)) + kb + vb
        blocks.append(bytes(b))
    out = bytearray(struct.pack('<3I', MAGIC, th.version, len(th.items)))
    off = 12 + ITEM * len(th.items)
    for it, b in zip(th.items, blocks):
        out += struct.pack('<I', off) + _fixed(it.state) + _fixed(it.style) + _fixed(it.widget); off += len(b)
    for b in blocks: out += b
    return bytes(out)

def fmt_value(k, t, v):
    if t == T_UINT32 and is_color_key(k): return color_to_str(v)
    return repr(v) if t == T_STRING else str(v)

def dump(th, styles=None):
    for it in th.items:
        if styles and it.style not in styles: continue
        print(f'{it.widget}/{it.style}/{it.state}: ' + ', '.join(f'{k!r}={fmt_value(k, t, v)}' for k, t, v in it.props))

if __name__ == '__main__':
    cmd, files = sys.argv[1], sys.argv[2:]
    if cmd == 'dump':
        dump(parse(open(files[0], 'rb').read()), set(files[1:]))
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
    else: sys.exit(__doc__)
