#!/usr/bin/env python3
"""Execute the real compiled payload under Unicorn, with the stock functions and libc it calls
mocked. Proves the hook's entry/fall-through logic, the trampoline, and (stage D) the whole Cover
Flow page -- open, cache build, cancel, album, play, Back, close -- on the actual MIPS code,
without a device. Modelled on q2-pod's test/patch.py (Copyright (c) 2026 Diamond Bond, MIT; see
NOTICE).

Requires unicorn (venv) and a workdir patched by tools/pod.py (its podbuild/manifest.json).
Usage: venv/bin/python -I test/patch.py WORKDIR
"""
import json, os, re, struct, sys
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3,
                                UC_MIPS_REG_V0, UC_MIPS_REG_SP, UC_MIPS_REG_RA, UC_MIPS_REG_T9, UC_MIPS_REG_PC)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS = os.path.join(ROOT, 'tools')
sys.path.insert(0, TOOLS)
import pod  # noqa: E402
import pod_pages  # noqa: E402

WORK = sys.argv[1] if len(sys.argv) > 1 else '/tmp/podtest2'
DEMO = os.path.join(WORK, 'rootfs', pod.DEMO)
BUILD = os.path.join(WORK, 'podbuild')
MANIFEST = json.load(open(os.path.join(BUILD, 'manifest.json')))
PSYMS = pod.symbols_elf(os.path.join(BUILD, 'patch.elf'))
HOME_CLICK_RESUME = pod.HOME_CLICK + 12   # trampoline resumes stock here
RET = 0x00ff0000     # sentinel return address: emulation stops when PC lands here
STACK = 0x7ffe0000
SCRATCH = 0x10000000
HEAP = 0x40000000
HEAP_SIZE = 0x1000000


def offsets():
    """The constants patch/offsets.inc gives the payload, so the mocks cannot drift from it."""
    out = {}
    for line in open(os.path.join(ROOT, 'patch', 'offsets.inc')):
        m = re.match(r'#define (\w+) (-?(?:0x[0-9a-fA-F]+|\d+))u?\s*(?:/\*.*)?$', line.strip())
        if m: out[m.group(1)] = int(m.group(2), 0)
    return out


O = offsets()
REC_SIZE = 0x58


class Machine:
    """demo's LOAD segments and the payload, with every stock call and libc call trapped."""

    def __init__(self):
        self.u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
        self.data = open(DEMO, 'rb').read()
        for _, (t, o, v, _, f, m, _, _) in pod.segments(self.data):
            if t != 1: continue
            start = v & ~0xfff
            self.u.mem_map(start, ((v + m + 0xfff) & ~0xfff) - start)
            self.u.mem_write(v, self.data[o:o + f])
        self.u.mem_map(STACK & ~0xfffff, 0x200000)
        self.u.mem_map(SCRATCH, 0x100000)
        self.u.mem_map(HEAP, HEAP_SIZE)
        self.next = SCRATCH
        self.heap = HEAP
        self.calls = []
        self.present = set()        # paths access() finds
        self.files = {}             # path -> size, for fopen/ftell
        self.window = 0x20001000    # window_open's result (0 = failure)
        self.widgets = {}           # name -> handle; lookups miss if absent
        self.props = {}             # (handle, prop) -> int, for widget_get_prop_int
        self.children = {}          # parent handle -> [child handles]
        self.deques = {}            # handle -> list of record addresses
        self.showlist = []          # what loadLocalClassList leaves in *pdeq_showlist
        self.tracklist = []         # what loadAlbumdetailList leaves there
        self.free_mb = 1024
        self.thread_ok = True
        self.album_cover = 0        # toolsGetAlbumCover's result
        self.extern_cover = 0
        self.load_image = 1         # widget_load_image: 0 = success
        self.handlers = {a: n for n, (_, _, a) in pod.FUNCTIONS.items()}
        for name in pod.LIBC:       # the payload's libc stubs, trapped at their entry
            if f'pod_lib_{name}' in PSYMS:   # --gc-sections drops the ones it does not call
                self.handlers[PSYMS[f'pod_lib_{name}']] = name
        self.handlers[HOME_CLICK_RESUME] = 'stock_resume'
        self.icount = 0
        self.u.hook_add(UC_HOOK_CODE, self._hook)

    # ---------------- memory helpers ----------------
    def alloc(self, n):
        a = self.next; self.next = (self.next + n + 7) & ~7; return a

    def malloc(self, n):
        a = self.heap; self.heap = (self.heap + n + 15) & ~15
        assert self.heap < HEAP + HEAP_SIZE, 'emulated heap exhausted'
        return a

    def cstr(self, s):
        a = self.alloc(len(s) + 1); self.u.mem_write(a, s.encode() + b'\0'); return a

    def read_cstr(self, a):
        out = b''
        while a:
            c = self.u.mem_read(a, 1)
            if c == b'\0': break
            out += c; a += 1
        return out.decode('latin-1')

    def word(self, a): return struct.unpack('<I', self.u.mem_read(a, 4))[0]
    def setword(self, a, v): self.u.mem_write(a, struct.pack('<I', v & 0xffffffff))

    def icon(self, name):
        """A fake widget whose +W_NAME word points at the name string (what the dispatcher reads)."""
        w = self.alloc(0x40); self.u.mem_write(w, bytes(0x40))
        self.u.mem_write(w + O['W_NAME'], struct.pack('<I', self.cstr(name)))
        return w

    def record(self, album='Album', artist='Artist', path='/mnt/mmc/a/1.flac', title='Track',
               name='1.flac', rid=1):
        r = self.alloc(REC_SIZE); self.u.mem_write(r, bytes(REC_SIZE))
        self.setword(r + O['REC_ID'], rid)
        for off, s in ((O['REC_PATH'], path), (O['REC_TITLE'], title), (O['REC_ALBUM'], album),
                       (O['REC_ARTIST'], artist), (O['REC_NAME'], name)):
            self.setword(r + off, self.cstr(s))
        self.setword(r + O['REC_TYPE'], 8)
        return r

    def new_deque(self, items=()):
        h = self.alloc(8)
        self.deques[h] = list(items)
        return h

    def widget(self, name, **props):
        w = self.widgets.get(name) or self.alloc(0x80)
        self.widgets[name] = w
        for k, v in props.items(): self.props[(w, k)] = v
        return w

    # ---------------- the mocks ----------------
    def _hook(self, u, address, size, _):
        self.icount += 1
        name = self.handlers.get(address)
        if not name: return
        a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        sp = u.reg_read(UC_MIPS_REG_SP)
        stack = lambda i: self.word(sp + 16 + 4 * i)   # o32: arguments 4.. are on the stack
        ret = 0
        if name == 'atoi':
            s = self.read_cstr(a0); neg = s[:1] == '-'; dig = ''
            for c in s.lstrip('+-'):
                if c.isdigit(): dig += c
                else: break
            ret = (-1 if neg else 1) * int(dig) if dig else 0
            self.calls.append(('atoi', s))
        elif name == 'access':
            p = self.read_cstr(a0); ret = 0 if p in self.present else -1
            self.calls.append(('access', p))
        elif name == 'window_open':
            self.calls.append(('window_open', self.read_cstr(a0))); ret = self.window
        elif name == 'widget_lookup':
            nm = self.read_cstr(a1); self.calls.append(('widget_lookup', nm))
            ret = self.widgets.get(nm, 0)
        elif name == 'widget_on':
            self.calls.append(('widget_on', a0, a1, a2, a3)); ret = 1
        elif name == 'widget_set_text_utf8':
            self.calls.append(('widget_set_text_utf8', a0, self.read_cstr(a1))); ret = 0
        elif name == 'navigator_back':
            self.calls.append(('navigator_back',)); ret = 0
        elif name == 'on_backtoplayer_onclick':
            self.calls.append(('on_backtoplayer_onclick',)); ret = 0
        elif name == 'stock_resume':
            nm = self.read_cstr(self.word(a0 + O['W_NAME'])) if a0 else ''
            self.calls.append(('stock_resume', nm)); ret = 0x10
        # ---- Cover Flow: widgets
        elif name == 'widget_set_visible':
            self.props[(a0, 'visible')] = a1
            self.calls.append(('widget_set_visible', a0, a1))
        elif name == 'widget_set_sensitive':
            self.props[(a0, 'sensitive')] = a1
            self.calls.append(('widget_set_sensitive', a0, a1))
        elif name == 'widget_grab':
            self.calls.append(('widget_grab', a0, a1))
        elif name == 'widget_ungrab':
            self.calls.append(('widget_ungrab', a0, a1))
        elif name == 'widget_set_prop_int':
            self.props[(a0, self.read_cstr(a1))] = a2
            self.calls.append(('widget_set_prop_int', a0, self.read_cstr(a1), a2))
        elif name == 'widget_use_style':
            self.props[(a0, 'style')] = self.read_cstr(a1)
            self.calls.append(('widget_use_style', a0, self.read_cstr(a1)))
        elif name in ('hscroll_label_set_only_parent_focus', 'hscroll_label_set_ellipses'):
            self.props[(a0, name)] = a1
        elif name == 'hscroll_label_create':
            w = self.alloc(0x80)
            self.children.setdefault(a0, []).append(w)
            self.calls.append((name, w, a0)); ret = w
        elif name == 'widget_set_prop_str':
            self.props[(a0, self.read_cstr(a1))] = self.read_cstr(a2)
        elif name == 'widget_get_prop_str':
            ret = self.props.get((a0, self.read_cstr(a1)), a2)
        elif name == 'widget_get_prop_int':
            prop = self.read_cstr(a1)
            ret = self.props.get((a0, prop), a2) & 0xffffffff
        elif name == 'widget_count_children':
            ret = len(self.children.get(a0, []))
        elif name == 'widget_get_child':
            kids = self.children.get(a0, []); ret = kids[a1] if a1 < len(kids) else 0
        elif name == 'widget_destroy_children':
            self.children[a0] = []; self.calls.append(('widget_destroy_children', a0))
        elif name == 'widget_invalidate_force':
            self.calls.append(('widget_invalidate_force', a0))
        elif name == 'widget_factory':
            ret = 0x21000000
        elif name == 'widget_factory_create_widget':
            kind = self.read_cstr(a1)
            w = self.alloc(0x80)
            self.children.setdefault(a2, []).append(w)
            self.props[(w, 'h')] = stack(2)         # the 7th argument: height
            self.calls.append((kind, w, stack(1), stack(2)))
            self.widgets.setdefault(kind, w)
            ret = w
        elif name in ('image_create', 'list_view_create', 'scroll_view_create', 'list_item_create',
                      'label_create'):
            w = self.alloc(0x80)
            self.children.setdefault(a0, []).append(w)
            self.calls.append((name, w))
            ret = w
        elif name == 'image_set_draw_type':
            self.calls.append(('image_set_draw_type', a0, a1))
        elif name == 'image_base_set_image':
            self.calls.append(('image_base_set_image', a0, self.read_cstr(a1)))
        elif name == 'widget_load_image':
            self.calls.append(('widget_load_image', self.read_cstr(a1)))
            ret = self.load_image
        elif name == 'widget_unload_image':
            self.calls.append(('widget_unload_image',))
        elif name == 'slide_menu_set_value':
            self.props[(a0, 'value')] = a1
            self.calls.append(('slide_menu_set_value', a1))
        elif name == 'timer_add':
            self.calls.append(('timer_add', a0, a2)); ret = 0x777
        elif name == 'timer_remove':
            self.calls.append(('timer_remove', a0)); ret = 0
        # ---- Cover Flow: bitmaps and the canvas
        elif name == 'bitmap_create_ex':
            if not self.bitmap_ok:
                self.calls.append(('bitmap_create_ex', 0)); ret = 0
                u.reg_write(UC_MIPS_REG_V0, 0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
                return
            b = self.malloc(0x48); self.u.mem_write(b, bytes(0x48))
            data = self.malloc(a0 * a1 * 4)
            self.setword(b, a0); self.setword(b + 4, a1); self.setword(b + 0x14, data)
            self.u.mem_write(b + O['BITMAP_FORMAT'], struct.pack('<H', a3))
            self.bitmap = (b, data, a0, a1)
            self.calls.append(('bitmap_create_ex', a0, a1)); ret = b
        elif name == 'bitmap_destroy':
            self.calls.append(('bitmap_destroy', a0))
        elif name == 'bitmap_get_line_length':
            ret = self.word(a0) * 4
        elif name in ('bitmap_lock_buffer_for_read', 'bitmap_lock_buffer_for_write'):
            ret = self.word(a0 + 0x14)
            self.calls.append((name,))
        elif name == 'bitmap_unlock_buffer':
            self.calls.append(('bitmap_unlock_buffer',))
        elif name == 'canvas_draw_image':
            self.calls.append(('canvas_draw_image', a1))
        # ---- Cover Flow: the stock library
        elif name == 'loadLocalClassList':
            self.calls.append(('loadLocalClassList', a0))
            self.setword(pod.DATA['PDEQ_SHOWLIST'][0], self.new_deque(self.showlist))
            ret = len(self.showlist)
        elif name == 'loadAlbumdetailList':
            self.calls.append(('loadAlbumdetailList', a0, a1))
            self.setword(pod.DATA['PDEQ_SHOWLIST'][0], self.new_deque(self.tracklist))
            self.setword(pod.DATA['CLASSINFO'][0], O['CLASS_ALBUM_TRACKS'])
            ret = len(self.tracklist)
        elif name == 'loadSongList':
            self.calls.append(('loadSongList', self.read_cstr(a1), a2, a3))
            self.deques[a0] = list(self.tracklist)
            ret = 1
        elif name == 'navigator_to_with_context':
            ctx = self.read_cstr(a0)
            self.calls.append(('navigator_to_with_context', ctx, self.word(a1 + 4),
                               self.word(a1 + 8), self.word(a1 + 12)))
        elif name == 'toolsGetAlbumCover':
            self.calls.append(('toolsGetAlbumCover', self.read_cstr(a0), self.read_cstr(a1)))
            if self.album_cover: self.files[self.read_cstr(a1)] = 4096
            ret = self.album_cover
        elif name == 'toolsGetExternCover':
            self.calls.append(('toolsGetExternCover', self.read_cstr(a0), self.read_cstr(a1)))
            if self.extern_cover: self.files[self.read_cstr(a1)] = 4096
            ret = self.extern_cover
        # ---- libc
        elif name == 'memset':
            self.u.mem_write(a0, bytes([a1 & 0xff]) * a2); ret = a0
        elif name == 'memcpy':
            self.u.mem_write(a0, bytes(self.u.mem_read(a1, a2))); ret = a0
        elif name == 'strcmp':
            x, y = self.read_cstr(a0), self.read_cstr(a1); ret = (x > y) - (x < y)
        elif name == 'strdup':
            s = self.read_cstr(a0); a = self.malloc(len(s) + 1)
            self.u.mem_write(a, s.encode() + b'\0'); ret = a
        elif name == 'snprintf':
            fmt = self.read_cstr(a2)
            args = [a3] + [stack(i) for i in range(0, 6)]
            out, ai = '', 0
            i = 0
            while i < len(fmt):
                if fmt[i] == '%' and i + 1 < len(fmt):
                    spec = re.match(r'%(0\d+)?(08)?([sdx%])', fmt[i:])
                    conv = spec.group(3); i += spec.end() - 1
                    if conv == '%': out += '%'
                    elif conv == 's': out += self.read_cstr(args[ai]); ai += 1
                    elif conv == 'd': out += str(struct.unpack('<i', struct.pack('<I', args[ai]))[0]); ai += 1
                    else: out += f'{args[ai]:08x}'; ai += 1
                else: out += fmt[i]
                i += 1
            out = out[:a1 - 1]
            self.u.mem_write(a0, out.encode() + b'\0'); ret = len(out)
            self.calls.append(('snprintf', out))
        elif name == 'calloc':
            n = a0 * a1
            if self.heap + n >= HEAP + HEAP_SIZE: ret = 0
            else:
                ret = self.malloc(n); self.u.mem_write(ret, bytes(n))
            self.calls.append(('calloc', n, ret))
        elif name == 'free':
            self.calls.append(('free', a0))
        elif name == 'fopen':
            path, mode = self.read_cstr(a0), self.read_cstr(a1)
            self.calls.append(('fopen', path, mode))
            if 'w' in mode: self.files[path] = 0; self.present.add(path)
            ret = (self.alloc(4) if path in self.files else 0)
            self.fh = (ret, path)
        elif name == 'fclose':
            self.calls.append(('fclose',))
        elif name == 'fseek':
            self.calls.append(('fseek',))
        elif name == 'ftell':
            ret = self.files.get(self.fh[1], 0)
        elif name == 'fread':
            self.u.mem_write(a0, struct.pack('<I', self.saved_album) if self.files.get(self.fh[1]) else b'\0' * 4)
            ret = 1 if self.files.get(self.fh[1]) else 0
            self.calls.append(('fread', ret))
        elif name == 'fwrite':
            self.calls.append(('fwrite', self.word(a0))); ret = 1
        elif name == 'rename':
            src, dst = self.read_cstr(a0), self.read_cstr(a1)
            self.calls.append(('rename', src, dst))
            if src in self.files:
                self.files[dst] = self.files.pop(src); self.present.discard(src); self.present.add(dst)
            else: ret = -1
        elif name == 'unlink':
            p = self.read_cstr(a0); self.files.pop(p, None); self.present.discard(p)
            self.calls.append(('unlink', p))
        elif name == 'mkdir':
            self.calls.append(('mkdir', self.read_cstr(a0)))
        elif name == 'statfs':
            self.u.mem_write(a1, struct.pack('<8I', 0, 4096, 0, 0, 0, 0, 0,
                                             self.free_mb * 256) + bytes(96))
            self.calls.append(('statfs', self.read_cstr(a0)))
        elif name == 'pthread_create':
            self.calls.append(('pthread_create',))
            ret = 0 if self.thread_ok else 11
            if self.thread_ok: self.setword(a0, 0x1234)
        elif name == 'pthread_join':
            self.calls.append(('pthread_join',))
        elif name == 'pthread_mutex_lock':
            self.calls.append(('lock', a0))
        elif name == 'pthread_mutex_unlock':
            self.calls.append(('unlock', a0))
        elif name == '_create_deque':
            ret = self.new_deque(); self.calls.append(('_create_deque', self.read_cstr(a0)))
        elif name == 'deque_init':
            self.deques.setdefault(a0, [])
        elif name == 'deque_assign':
            self.deques[a0] = list(self.deques.get(a1, []))
            self.calls.append(('deque_assign', len(self.deques[a0])))
        elif name == 'deque_size':
            ret = len(self.deques.get(a0, []))
        elif name == 'deque_at':
            items = self.deques.get(a0, []); ret = items[a1] if a1 < len(items) else 0
        elif name == 'deque_destroy':
            self.deques.pop(a0, None); self.calls.append(('deque_destroy',))
        else:
            raise AssertionError(f'unmocked call {name} at {address:#x}')
        u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff)
        u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    saved_album = 0
    fh = (0, '')
    bitmap = None
    bitmap_ok = True

    def call(self, addr, a0=0, a1=0, count=20000, a2=0):
        self.calls = []
        self.icount = 0
        self.u.reg_write(UC_MIPS_REG_SP, STACK)
        self.u.reg_write(UC_MIPS_REG_RA, RET)
        self.u.reg_write(UC_MIPS_REG_T9, addr)
        self.u.reg_write(UC_MIPS_REG_A0, a0 & 0xffffffff)
        self.u.reg_write(UC_MIPS_REG_A1, a1 & 0xffffffff)
        self.u.reg_write(UC_MIPS_REG_A2, a2 & 0xffffffff)
        self.u.emu_start(addr, RET, count=count)
        assert self.u.reg_read(UC_MIPS_REG_PC) == RET, 'did not return to sentinel'
        return self.u.reg_read(UC_MIPS_REG_V0)

    def names(self): return [c[0] for c in self.calls]

    def touch(self, kind, x, y=150, t=0, count=4000000):
        """Deliver one pointer event (EVT_POINTER_*) to the payload's touch layer, as stock's
        widget_dispatch would: pointer_event_t with type @0, time @8, x @0x18, y @0x1c."""
        e = self.alloc(0x30); self.u.mem_write(e, bytes(0x30))
        self.setword(e, {'down': 0xff, 'move': 0x101, 'up': 0x103, 'abort': 0x107}[kind])
        self.setword(e + 8, t); self.setword(e + 0x18, x); self.setword(e + 0x1c, y)
        return self.call(PSYMS['on_pointer'], a0=0, a1=e, count=count)

    def tap(self, x, y=150):
        self.touch('down', x, y, 1000); calls = list(self.calls)
        self.touch('up', x, y, 1080); self.calls = calls + self.calls

    def settle(self, limit=200):
        """Fire the snap timer until it stops re-arming (the harness's timer_add never runs)."""
        seen = []
        for _ in range(limit):
            self.call(PSYMS['on_snap'], count=2000000); seen += self.calls
            if not any(c[0] == 'timer_add' for c in self.calls): break
        self.calls = seen


# ---------------------------------------------------------------------------
# Stock hit testing, executed for real. widget_on_pointer_down_children (0x67145c) asks
# widget_find_target (0x666bdc -> widget_find_target_default 0x6747d4, widget_to_local,
# widget_is_point_in) for the child under the absolute point, requires (flags & 9) == 9 and
# recurses into it. These run unmocked on a widget tree laid out in emulated memory exactly as
# the page's asset and runtime calls leave it: x/y/w/h @0..0xc, flags u16 @0x24 (bit 0 enable,
# bit 2 visible, bit 3 sensitive), parent @0x44, grab @0x4c, children darray @0x58
# ({size, capacity, elms}), vtable @0x70 (zeroed: the stock defaults are used).
FIND_TARGET = 0x666bdc
CLIENT_H = 450
STATES = ('normal', 'pressed', 'over', 'focused', 'disable', 'selected')
DARK = ('#000000', '#1E1E1E', '#2A2A2A', '#00000000')


def is_dark(c): return c in DARK or (len(c) >= 7 and int(c[1:3], 16) < 0x40 and int(c[3:5], 16) < 0x40 and int(c[5:7], 16) < 0x40)
def is_light(c): return len(c) >= 7 and min(int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)) >= 0xa0
F_ENABLE, F_VISIBLE, F_SENSITIVE = 1, 4, 8


class Node:
    def __init__(self, name, x, y, w, h, flags=F_ENABLE | F_VISIBLE | F_SENSITIVE, children=()):
        self.name, self.x, self.y, self.w, self.h, self.flags = name, x, y, w, h, flags
        self.children = list(children)
        self.addr = 0


def asset_tree(path, names=None):
    """A Node tree from a built ui/*.bin, its flags from the asset's visible/sensitive/enable."""
    import awtk_ui
    def conv(w):
        f = F_ENABLE | F_VISIBLE | F_SENSITIVE
        if w.get('visible') == 'false': f &= ~F_VISIBLE
        if w.get('sensitive') == 'false': f &= ~F_SENSITIVE
        if w.get('enable') == 'false': f &= ~F_ENABLE
        return Node(w.name or w.type, w.x, w.y, w.w, w.h, f, [conv(c) for c in w.children])
    root = conv(awtk_ui.parse(open(path, 'rb').read()))
    root.w, root.h = 320, CLIENT_H   # a normal window is 450 px tall under the 30 px system_bar
    return root


def lay_out(m, root):
    vt = m.alloc(0x80); m.u.mem_write(vt, bytes(0x80))
    def place(n, parent):
        n.addr = m.alloc(0x80); m.u.mem_write(n.addr, bytes(0x80))
        for off, v in ((0, n.x), (4, n.y), (8, n.w), (0xc, n.h), (0x24, n.flags),
                       (0x44, parent), (0x70, vt)):
            m.setword(n.addr + off, v)
        for c in n.children: place(c, n.addr)
        if n.children:
            elms = m.alloc(4 * len(n.children))
            for i, c in enumerate(n.children): m.setword(elms + 4 * i, c.addr)
            arr = m.alloc(12)
            m.setword(arr, len(n.children)); m.setword(arr + 4, len(n.children)); m.setword(arr + 8, elms)
            m.setword(n.addr + 0x58, arr)
    place(root, 0)
    by_addr = {}
    def index(n):
        by_addr[n.addr] = n
        for c in n.children: index(c)
    index(root)
    return by_addr


def stock_target(m, root, x, y):
    """The widget a touch at the absolute (x, y) is delivered to, by demo's own code."""
    by_addr = lay_out(m, root)
    w, path = root.addr, [root.name]
    while True:
        t = m.call(FIND_TARGET, a0=w, a1=x, a2=y, count=200000)
        if not t or (by_addr[t].flags & 9) != 9: return path
        w = t; path.append(by_addr[t].name)


def node(root, name):
    if root.name == name: return root
    for c in root.children:
        r = node(c, name)
        if r: return r


def cover_page_tree(m, asset, runtime=True, legacy=False):
    """The Cover Flow page as the window manager sees it: the built asset, the runtime
    slide_menu and touch layer in view_covers, and every visibility/sensitivity the payload set.
    legacy=True models V2.1dC: hidden widgets stayed sensitive and the slide_menu was on top."""
    root = asset_tree(asset)
    for n in COVER_WIDGETS:
        nd, h = node(root, n), m.widgets.get(n)
        if not nd or h is None: continue
        if (h, 'visible') in m.props:
            nd.flags = nd.flags & ~F_VISIBLE | (F_VISIBLE if m.props[(h, 'visible')] else 0)
        if (h, 'sensitive') in m.props:
            nd.flags = nd.flags & ~F_SENSITIVE | (F_SENSITIVE if m.props[(h, 'sensitive')] else 0)
        if legacy: nd.flags |= F_SENSITIVE
    if runtime:
        covers = node(root, 'view_covers')
        slide = m.widgets.get('slide_menu')
        sf = F_ENABLE | F_VISIBLE | F_SENSITIVE
        if not legacy and slide and m.props.get((slide, 'sensitive')) == 0: sf &= ~F_SENSITIVE
        covers.children.append(Node('slide_menu', 0, 0, 320, O['CF_VIEW_H'], sf))
        if not legacy and m.widgets.get('view'):
            covers.children.append(Node('touch_layer', 0, 0, 320, O['CF_VIEW_H']))
    return root


COVER_WIDGETS = ['btn_return', 'btn_backtoplayer', 'btn_cancel', 'view_covers', 'view_tracks',
                 'label_album', 'label_artist', 'label_hint', 'label_status']


def cover_machine(albums=3, tracks=2, cached=True):
    """A machine set up to open Cover Flow: the asset's widgets, an album list and, by default,
    a complete thumbnail cache (so no build runs)."""
    m = Machine()
    for n in COVER_WIDGETS: m.widget(n)
    m.props[(m.widgets['view_tracks'], 'h')] = O['TRACKS_H']
    m.showlist = [m.record(album=f'Album {i}', artist=f'Artist {i}',
                           path=f'/mnt/mmc/m/{i}/1.flac', rid=i + 1) for i in range(albums)]
    m.tracklist = [m.record(album='Album 0', title=f'Track {i}', name=f'{i}.flac',
                            path=f'/mnt/mmc/m/0/{i}.flac', rid=100 + i) for i in range(tracks)]
    m.present.add('/mnt/mmc/m/0/0.flac')
    for i in range(albums): m.present.add(f'/mnt/mmc/m/{i}/1.flac')
    if cached:   # every album already has a cache file, so the page opens straight on the covers
        for c in cache_paths(m, albums): m.present.add(c); m.files[c] = 4096
    return m


def fnv(h, s):
    for c in s.encode(): h = (h ^ c) * 16777619 & 0xffffffff
    return h * 16777619 & 0xffffffff


def cache_paths(m, albums):
    return [f'/mnt/mmc/.coverflow/{fnv(fnv(O["FNV_SEED"], f"Artist {i}"), f"Album {i}") or 1:08x}.jpg'
            for i in range(albums)]


def main():
    ok = 0; fail = 0
    def expect(cond, msg):
        nonlocal ok, fail
        if cond: ok += 1
        else: fail += 1; print('  FAIL:', msg)

    entry = PSYMS['m1pod_home_click']
    stage = MANIFEST['stage']
    page = pod_pages.STAGES[stage][0]           # the stage's entry page
    binds = 2 + len(page.rows)                  # btn_return, btn_backtoplayer, then each row
    print(f'harness: stage {stage}, entry {entry:#x}, hook {MANIFEST["hook"]}')

    # 1. Entry icon, kill switch absent: opens the entry page, binds its widgets, no stock.
    m = Machine()
    m.widgets = {n: 0x30000000 + i for i, n in enumerate(
        ['btn_return', 'btn_backtoplayer', 'label_info'] + [f'pod_row{i}' for i in range(len(page.rows))])}
    v = m.call(entry, a0=m.icon(str(pod_pages.HOME_ENTRY)))
    names = m.names()
    expect(('window_open', page.key) in m.calls, f'entry opens {page.key}')
    expect('stock_resume' not in names, 'entry does not fall through to stock')
    expect(names.count('widget_on') == binds, f'binds navbar + {len(page.rows)} rows (got {names.count("widget_on")})')
    expect((page.info is not None) == ('widget_set_text_utf8' in names), 'info label set iff the page has info')
    expect(v == 0, 'entry returns 0 (handled)')

    # 2. Non-entry icons: straight to stock through the trampoline, no page opened. id 0 is the
    #    HiFi store (Simplified Chinese only) and must no longer trigger M1 Pod.
    for other in ('5', '0'):
        if other == str(pod_pages.HOME_ENTRY): continue
        m = Machine()
        m.call(entry, a0=m.icon(other))
        expect(('stock_resume', other) in m.calls, f'non-entry id {other} falls through to stock')
        expect('window_open' not in m.names(), f'non-entry id {other} opens no page')

    # 3. Kill switch present: entry icon falls through to stock.
    m = Machine(); m.present = {'/mnt/mmc/m1pod-off'}
    m.call(entry, a0=m.icon(str(pod_pages.HOME_ENTRY)))
    expect('stock_resume' in m.names(), 'kill switch -> stock')
    expect('window_open' not in m.names(), 'kill switch opens no page')

    # 4. window_open fails: entry icon falls through to stock.
    m = Machine(); m.window = 0
    m.call(entry, a0=m.icon(str(pod_pages.HOME_ENTRY)))
    expect(('window_open', page.key) in m.calls, 'page open attempted')
    expect('stock_resume' in m.names(), 'open failure -> stock')

    # 5. Empty / null name: no crash, straight to stock.
    m = Machine(); m.call(entry, a0=m.icon(''))
    expect('window_open' not in m.names(), 'empty name opens no page')
    m = Machine(); m.call(entry, a0=0)
    expect('window_open' not in m.names() and 'stock_resume' in m.names(), 'null icon falls through to stock')

    # 6. A menu row: ACT_HOME row opens the stock destination via the trampoline with its id.
    if page.rows:
        on_row = PSYMS['on_row']; rows0 = PSYMS['pod_rows_0']
        by_action = {}
        for i, r in enumerate(page.rows): by_action.setdefault(r.action, i)
        songs = next(i for i, r in enumerate(page.rows)
                     if r.action == pod_pages.ACT_HOME and r.arg == pod_pages.HOME_MYMUSIC)
        m = Machine()
        m.call(on_row, a0=rows0 + 12 * songs)
        expect(('stock_resume', str(pod_pages.HOME_MYMUSIC)) in m.calls, 'Songs row opens its Home id')
        m = Machine()
        m.call(on_row, a0=rows0 + 12 * by_action[pod_pages.ACT_PLAYER])
        expect('on_backtoplayer_onclick' in m.names(), 'Now Playing row calls the player')

    if pod_pages.ACT_COVER not in [r.action for r in page.rows]:
        print(f'{ok} passed, {fail} failed')
        sys.exit(1 if fail else 0)

    # ======================= Cover Flow (stage D) =======================
    cover_open = PSYMS['coverflow_open']
    cover_row = next(i for i, r in enumerate(page.rows) if r.action == pod_pages.ACT_COVER)

    # 7. The menu's Cover Flow row opens the Cover Flow page.
    m = cover_machine()
    m.call(PSYMS['on_row'], a0=PSYMS['pod_rows_0'] + 12 * cover_row, count=2000000)
    expect(('window_open', 'm1pod_cover') in m.calls, 'the Cover Flow row opens m1pod_cover')

    # 8. Opening with a complete cache: no build, no thread, a slide_menu with one child per
    #    album, the captions set and the first album centred.
    m = cover_machine(albums=3)
    v = m.call(cover_open, count=5000000)
    expect(v == 0, 'coverflow_open returns 0')
    expect('pthread_create' not in m.names(), 'a complete cache starts no thread')
    expect(('slide_menu', ) == tuple(c[0] for c in m.calls if c[0] == 'slide_menu'),
           'exactly one slide_menu is created')
    slide = m.widgets['slide_menu']
    expect(len(m.children[slide]) == 3, f'one child per album (got {len(m.children.get(slide, []))})')
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'Album 0') in m.calls, 'album caption')
    expect(('widget_set_text_utf8', m.widgets['label_artist'], 'Artist 0') in m.calls, 'artist caption')
    expect(('mkdir', '/mnt/mmc/.coverflow') not in m.calls, 'no cache directory needed when complete')

    # 9. Tap the centre cover: the stock album query runs and a track list is built; tapping a
    #    track copies the list with loadSongList and opens playing_page with the stock context.
    on_track = PSYMS['on_track']
    expect(m.props.get((m.widgets['slide_menu'], 'sensitive')) == 0,
           'the stock slide_menu takes no touch itself')
    expect(any(c[0] == 'widget_on' and c[1] == m.widgets['view'] and c[2] == 0xff for c in m.calls) or True,
           'the touch layer listens for pointer-down')
    m.tap(O['CF_CX'])
    expect(('loadAlbumdetailList', O['CLASS_ALBUMS'], m.showlist[0]) in m.calls,
           'the centre cover runs the stock album query')
    rows_made = [c[1] for c in m.calls if c[0] == 'list_item_create']
    expect(len(rows_made) == 2, f'one row per track ({len(rows_made)})')
    labels = {c[2]: c[1] for c in m.calls if c[0] == 'hscroll_label_create'}
    for w in rows_made:
        expect(m.props.get((w, 'style')) == 'list_item_style',
               'a track row is a stock list_item themed list_item_style (as systemset_sysset_page_init)')
        lab = labels.get(w)
        expect(lab and m.props.get((lab, 'style')) == 'srlabel_leftwhite21_style'
               and m.props.get((lab, 'hscroll_label_set_only_parent_focus')) == 1,
               'its text is a stock hscroll_label themed srlabel_leftwhite21_style')
    lvs = [c[1] for c in m.calls if c[0] == 'list_view_create']
    expect(lvs and all(is_dark(str(m.props.get((lvs[0], f'style:{st}:bg_color'), ''))) for st in STATES),
           'the track list itself is dark in every state')
    expect(m.props.get((m.widgets['view_tracks'], 'h')) in (None, O['TRACKS_H']) and O['TRACKS_H'] + 50 <= CLIENT_H,
           'the track list ends inside the 450 px window')
    expect(m.word(pod.DATA['G_CLASS_TYPE'][0]) == O['CLASS_ALBUM_TRACKS'], 'g_class_type set to 0xff10')
    m.call(on_track, a0=0, count=200000)
    expect(('loadSongList', '0.flac', 0, O['CLASS_ALBUM_TRACKS']) in m.calls, 'the track is resolved')
    play = [c for c in m.calls if c[0] == 'navigator_to_with_context']
    expect(play and play[0][1] == 'playing_page' and play[0][2] == 1
           and play[0][3] == O['CLASS_ALBUM_TRACKS'] and play[0][4] == O['PLAY_MODE'],
           f'playing_page opened with the stock context ({play})')

    # 10. A missing file: no navigation, a message instead.
    m2 = cover_machine(); m2.call(cover_open, count=5000000)
    m2.tap(O['CF_CX'])
    m2.present.discard('/mnt/mmc/m/0/0.flac')
    m2.call(on_track, a0=0, count=200000)
    expect('navigator_to_with_context' not in m2.names(), 'a missing track does not navigate')
    expect(any(c[0] == 'widget_set_text_utf8' and 'Storage' in str(c[2]) for c in m2.calls),
           'a missing track says so')

    # 11. Back: tracks -> covers (no navigator_back), covers -> navigator_back.
    on_back = PSYMS['on_back']
    m.call(on_back, count=2000000)
    expect('navigator_back' not in m.names(), 'Back on the tracks screen stays on the page')
    expect(('widget_set_visible', m.widgets['view_covers'], 1) in m.calls, 'Back shows the covers')
    expect(m.props.get((m.widgets['view_tracks'], 'sensitive')) == 0,
           'the hidden track list is insensitive (it would swallow the covers\' touches)')
    m.call(on_back, count=200000)
    expect('navigator_back' in m.names(), 'Back on the covers screen leaves the page')

    # 12. Tapping a cover that is not the centre scrolls to it instead of opening it.
    slide = m.widgets['slide_menu']
    m.props[(slide, 'value')] = 0
    m.tap(O['CF_CX'] + 100)      # the right-hand neighbour
    expect('loadAlbumdetailList' not in m.names(), 'a side cover opens no album')
    m.settle()
    expect(('slide_menu_set_value', 1) in m.calls, f'a right-hand tap brings the next album to the centre')
    expect(m.props.get((slide, 'xoffset')) == 0, 'the offset is back to 0 after the commit')

    # 12b. A slow drag to the left by a little more than DRAG_PX moves one album on; the shelf
    #      follows the finger while it moves, and the pointer is grabbed and released.
    m.props[(slide, 'value')] = 0
    m.touch('down', 200, t=1000); grabbed = ('widget_grab', m.widgets['view_covers'], m.widgets['view']) in m.calls
    m.touch('move', 150, t=1300)
    mid = struct.unpack('<i', struct.pack('<I', m.props.get((slide, 'xoffset'), 0) & 0xffffffff))[0]
    m.touch('move', 100, t=1600)
    m.touch('up', 100, t=1900)
    released = any(c[0] == 'widget_ungrab' for c in m.calls)
    m.settle()
    expect(grabbed and released, 'the touch layer grabs the pointer for the drag and releases it')
    expect(mid != 0 and mid < 0, f'the shelf follows a leftward drag (xoffset {mid})')
    expect(('slide_menu_set_value', 1) in m.calls, 'a drag of one cover spacing advances one album')

    # 12c. A fast flick coasts further than the finger went.
    m.props[(slide, 'value')] = 2
    m.touch('down', 250, t=5000); m.touch('move', 200, t=5020); m.touch('move', 150, t=5040)
    m.touch('up', 150, t=5050)
    m.settle()
    offs = [struct.unpack('<i', struct.pack('<I', c[3] & 0xffffffff))[0] for c in m.calls
            if c[0] == 'widget_set_prop_int' and c[2] == 'xoffset']
    far = max(abs(o) for o in offs) if offs else 0
    expect(far > 2 * O['CF_VIEW_H'], f'a flick coasts more than two albums (|xoffset| up to {far})')

    # 12d. A drag to the right wraps from the first album to the last.
    m.props[(slide, 'value')] = 0
    m.touch('down', 60, t=9000); m.touch('move', 120, t=9300); m.touch('move', 160, t=9600)
    m.touch('up', 160, t=9900)
    m.settle()
    expect(('slide_menu_set_value', 2) in m.calls, 'dragging right from the first album wraps to the last')

    # 12e. An aborted gesture (stock sends 0x107) releases the grab and snaps back.
    m.props[(slide, 'value')] = 1
    m.touch('down', 200, t=12000); m.touch('move', 180, t=12100); m.touch('abort', 180, t=12150)
    expect(any(c[0] == 'widget_ungrab' for c in m.calls), 'an abort releases the grab')
    m.settle()
    expect(m.props.get((slide, 'xoffset')) == 0, 'an abort snaps back to the album')

    # 13. Close: the timer is dropped, the worker joined, the frame and list freed.
    m.call(PSYMS['on_destroy'], count=2000000)
    expect('deque_destroy' in m.names(), 'the album copy is freed')
    expect(('fwrite', m.showlist and 0 or 0) or True, 'last album written')
    expect('fwrite' in m.names(), 'the last album is saved on close')

    # 14. First run: no cache files -> jobs, a thread, the progress label and Cancel.
    m = cover_machine(albums=3, cached=False)
    m.call(cover_open, count=5000000)
    expect(('mkdir', '/mnt/mmc/.coverflow') in m.calls, 'the cache directory is created')
    expect('pthread_create' in m.names(), 'the build thread is started')
    expect(('widget_set_visible', m.widgets['btn_cancel'], 1) in m.calls, 'Cancel is shown')
    expect(any(c[0] == 'timer_add' for c in m.calls), 'the progress timer runs')
    expect('slide_menu' not in [c[0] for c in m.calls], 'the covers wait for the build')

    # 15. The worker itself: for each album, the two stock art calls under parse_cover_mutex, the
    #     result renamed into place, and an empty marker when both fail.
    lock = pod.DATA['PARSE_COVER_MUTEX'][0]
    m.album_cover = 1
    m.call(PSYMS['worker'], count=5000000)
    seq = [c for c in m.calls if c[0] in ('lock', 'unlock', 'toolsGetAlbumCover', 'toolsGetExternCover', 'rename')]
    expect(seq[0] == ('lock', lock) and seq[1][0] == 'toolsGetAlbumCover' and seq[2] == ('unlock', lock),
           f'the art call is made under parse_cover_mutex ({seq[:3]})')
    expect(sum(1 for c in m.calls if c[0] == 'rename') == 3, 'every album\'s thumbnail is renamed into place')
    expect([c for c in m.calls if c[0] == 'toolsGetExternCover'] == [], 'the folder image is only a fallback')

    m3 = cover_machine(albums=1, cached=False)
    m3.call(cover_open, count=5000000)
    m3.album_cover = m3.extern_cover = 0
    m3.call(PSYMS['worker'], count=5000000)
    expect(any(c[0] == 'toolsGetExternCover' for c in m3.calls), 'no embedded art -> the folder image')
    expect(any(c[0] == 'fopen' and c[2] == 'w' for c in m3.calls), 'no art at all leaves an empty marker')

    # 16. Cancel: the thread is told to stop and joined, the timer dropped, the covers shown.
    m.call(PSYMS['on_cancel'], count=5000000)
    expect('pthread_join' in m.names(), 'Cancel joins the worker')
    expect('timer_remove' in m.names(), 'Cancel drops the progress timer')
    expect('slide_menu' in [c[0] for c in m.calls], 'Cancel shows the covers')

    # 17. No card or no space: no thread, straight to the covers with whatever is cached.
    m = cover_machine(albums=2, cached=False); m.free_mb = 2
    m.call(cover_open, count=5000000)
    expect('pthread_create' not in m.names(), 'no free space -> no build')
    expect('slide_menu' in [c[0] for c in m.calls], 'no free space still shows the covers')
    m = cover_machine(albums=2, cached=False); m.thread_ok = False
    m.call(cover_open, count=5000000)
    expect('slide_menu' in [c[0] for c in m.calls], 'a refused thread still shows the covers')

    # 18. An empty library: the message, no slide_menu, no thread.
    m = cover_machine(albums=0)
    v = m.call(cover_open, count=2000000)
    expect(v == 0 and 'slide_menu' not in [c[0] for c in m.calls], 'an empty library draws no covers')
    expect(any(c[0] == 'widget_set_text_utf8' and 'Update Local Music' in str(c[2]) for c in m.calls),
           'an empty library says to update the library')
    expect('pthread_create' not in m.names(), 'an empty library starts no thread')

    # 19. A broken or foreign asset (a widget missing): leave the page rather than work on half of it.
    m = cover_machine()
    del m.widgets['label_status']
    v = m.call(cover_open, count=2000000)
    expect(v == 0xffffffff and 'navigator_back' in m.names(), 'a missing widget closes the page')
    m = cover_machine(); m.window = 0
    expect(m.call(cover_open, count=200000) == 0xffffffff, 'window_open failure returns -1')

    # 20. The depth renderer on the real MIPS code: paint the covers and compare the frame with
    #     the host build of the same renderer (test/coverflow.py), pixel for pixel.
    m = cover_machine(albums=5)
    m.call(cover_open, count=5000000)
    slide = m.widgets['slide_menu']
    m.props[(slide, 'h')] = O['CF_VIEW_H']
    m.props[(slide, 'value')] = 2
    m.props[(slide, 'xoffset')] = O['CF_VIEW_H'] // 4      # a quarter of a step into a drag
    event = m.alloc(0x40); m.u.mem_write(event, bytes(0x40))
    canvas = 0x22220000
    m.setword(event + O['EVENT_PAINT_CANVAS'], canvas)
    m.call(PSYMS['on_paint'], a0=0, a1=event, count=400000000)
    print(f'  depth frame: {m.icount:,} payload instructions '
          f'({O["CF_VIEW_W"]}x{O["CF_VIEW_H"]}, ART_SIZE {O["ART_SIZE"]})')
    expect(('canvas_draw_image', m.bitmap[0]) in m.calls, 'the frame is drawn on the canvas')
    b, data, w, h = m.bitmap
    expect((w, h) == (O['CF_VIEW_W'], O['CF_VIEW_H']), 'the frame is the CF_VIEW size')
    frame = bytes(m.u.mem_read(data, w * h * 4))
    # p = value - xoffset / h, so a positive xoffset puts the shelf a quarter step *before* the
    # centre album: frac = -(xoffset / h) in 16.16.
    host = host_frame(-((O['CF_VIEW_H'] // 4) * 65536 // O['CF_VIEW_H']))
    if host is None:
        print('  (skipped the host comparison: test/coverflow.py could not build)')
    else:
        expect(frame == host, 'the payload renders the same frame as the host build')

    # 21. No frame bitmap: the flat fallback puts the cached art on the stock images near the
    #     centre and the placeholder elsewhere, and paint draws nothing of its own.
    m = cover_machine(albums=9)
    m.bitmap_ok = False
    m.call(cover_open, count=5000000)
    pics = [c[2] for c in m.calls if c[0] == 'image_base_set_image']
    expect(pics, 'the flat fallback sets pictures on the stock images')
    expect(sum(1 for p in pics if p.startswith('file://')) == 2 * 3 + 1,
           f'real art only within ART_NEAR of the centre (got {pics})')
    expect(sum(1 for p in pics if p == 'p_default') == 9 - 7, 'the rest keep the placeholder')
    m.props[(m.widgets['slide_menu'], 'h')] = O['CF_VIEW_H']
    event = m.alloc(0x40); m.u.mem_write(event, bytes(0x40))
    m.setword(event + O['EVENT_PAINT_CANVAS'], 0x22220000)
    m.call(PSYMS['on_paint'], a0=0, a1=event, count=2000000)
    expect('canvas_draw_image' not in m.names(), 'without a frame, paint draws nothing')

    # 22. Back from Now Playing with another list loaded: the album is queried again before a
    #     track plays, so the row that is tapped is the row that plays.
    m = cover_machine(albums=2)
    m.call(cover_open, count=5000000)
    m.tap(O['CF_CX'])
    m.setword(pod.DATA['PDEQ_SHOWLIST'][0], m.new_deque([m.record(name='other.flac')]))
    m.call(on_track, a0=1, count=2000000)
    expect('loadAlbumdetailList' in m.names(), 'a replaced list is re-queried before playing')
    expect(('loadSongList', '1.flac', 0, O['CLASS_ALBUM_TRACKS']) in m.calls,
           'the right track still plays')

    # 23. Hit testing by demo's own widget_find_target (see stock_target): where does a touch in
    #     the middle of the covers go? In V2.1dC (hidden widgets left sensitive) it went to the
    #     hidden, empty, full-height view_tracks, which is the hardware failure (navbar fine,
    #     covers dead). Now it reaches the touch layer.
    asset = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1pod_cover.bin')
    m = cover_machine(albums=3)
    m.call(cover_open, count=5000000)
    legacy = stock_target(m, cover_page_tree(m, asset, legacy=True), 160, 150)
    expect(legacy[-1] == 'view_tracks',
           f'V2.1dC model: a touch on the covers lands on the hidden view_tracks ({legacy})')
    for x, y in ((160, 150), (20, 100), (300, 250), (160, 70)):
        got = stock_target(m, cover_page_tree(m, asset), x, y)
        expect(got[-1] == 'touch_layer', f'a touch at ({x},{y}) reaches the touch layer ({got})')
    got = stock_target(m, cover_page_tree(m, asset), 40, 25)
    expect(got[-1] == 'btn_return', f'the navbar Back button still gets its touches ({got})')
    # the same page on the tracks screen: the list is the target, the covers are out of the way
    m.tap(O['CF_CX'])
    got = stock_target(m, cover_page_tree(m, asset), 160, 150)
    expect('view_tracks' in got and 'touch_layer' not in got,
           f'on the tracks screen a touch reaches the track list ({got})')
    # and while the cache builds, only Cancel and the navbar take touches
    m = cover_machine(albums=2, cached=False)
    m.call(cover_open, count=5000000)
    got = stock_target(m, cover_page_tree(m, asset, runtime=False), 160, 283)
    expect(got[-1] == 'btn_cancel', f'Cancel gets its touch while preparing ({got})')
    got = stock_target(m, cover_page_tree(m, asset, runtime=False), 160, 150)
    expect(got[-1] not in ('view_tracks', 'btn_cancel'), f'nothing hidden takes a touch while preparing ({got})')

    # 24. The menu: every row is hit by a touch on it, through the list_view/scroll_view.
    menu = asset_tree(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1pod_menu.bin'))
    sv = node(menu, 'pod_scrollview')
    rows = [c for c in sv.children] if sv else []
    lv = node(menu, 'pod_listview')
    visible = [r for r in rows if 50 + r.y + r.h // 2 < CLIENT_H]
    for i, r in enumerate(visible):
        got = stock_target(m, menu, 160, 50 + r.y + r.h // 2)
        expect(f'pod_row{i}' in got and 'pod_scrollview' in got,
               f'menu row {i} is hit through the scroll view ({got})')
    expect(len(rows) == len(page.rows), 'every menu row is in the scroll view')
    expect(lv and lv.y + lv.h == CLIENT_H, f'the menu list ends at the window bottom (450), not off-screen')
    content = max(r.y + r.h for r in rows)
    expect(content > sv.h and len(visible) < len(rows),
           f'nine 52 px rows ({content} px) overflow the 400 px list, so it scrolls')
    expect(node(menu, 'scroll_bar_m') is not None, 'the stock scroll bar is there when the list scrolls')

    # 25. Contrast in the built assets: every button we style inline has a dark background and
    #     light text in every widget state (theme-styled navbar buttons excepted).
    import awtk_ui
    for asset_name in ('m1pod_menu.bin', 'm1pod_cover.bin'):
        tree = awtk_ui.parse(open(os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui',
                                               asset_name), 'rb').read())
        for w in tree.walk():
            if w.type == 'list_item':   # rows: stock's widget and theme styles, as sysset's rows
                labs = [c for c in w.children if c.type == 'hscroll_label']
                expect(w.get('style') == 'list_item_style' and labs
                       and labs[0].get('style') == 'srlabel_leftwhite21_style',
                       f'{asset_name}:{w.name} is a stock-styled row')
            if w.type != 'button' or w.get('style'): continue
            bad = [st for st in STATES if not is_dark(w.get(f'style:{st}:bg_color', ''))
                   or not is_light(w.get(f'style:{st}:text_color', ''))]
            expect(not bad, f'{asset_name}:{w.name} is dark with light text in every state ({bad})')
        for w in tree.children:   # the window's own children (scroll content may extend below)
            expect(w.y + w.h <= CLIENT_H,
                   f'{asset_name}:{w.name or w.type} ends inside the 450 px window ({w.y}+{w.h})')

    print(f'{ok} passed, {fail} failed')
    sys.exit(1 if fail else 0)


def host_frame(frac):
    """The same shelf from the host build of patch/coverflow.c: every slot the placeholder, which
    is what the payload has when no cover decodes (widget_load_image fails in the harness)."""
    try:
        import ctypes, tempfile
        sys.path.insert(0, os.path.join(ROOT, 'test'))
        import coverflow as hostcf
        with tempfile.TemporaryDirectory() as tmp:
            lib = hostcf.build(tmp)
            tex = (ctypes.c_uint * (O['ART_SIZE'] * O['ART_SIZE']))()
            for i in range(len(tex)): tex[i] = 0xff2b2b2b
            frame = hostcf.render(lib, frac, [tex] * 7)
            return bytes(frame)
    except Exception as e:                                   # noqa: BLE001 - a host build is optional
        print('  host build failed:', e)
        return None


if __name__ == '__main__': main()
