"""Shared by the payload tests (test/pod/*.py): the Unicorn machine that runs the real compiled
payload with the stock functions and libc it calls mocked, the widget-tree hit testing that runs
demo's own widget_find_target, the machine factories and the host render of the depth renderer.
Modelled on q2-pod's test/patch.py (Copyright (c) 2026 Diamond Bond, MIT; see NOTICE).

Requires unicorn (venv) and a workdir patched by tools/pod.py (its podbuild/manifest.json).
test/patch.py calls init(WORKDIR) first, then loads the feature modules, which star-import this one.
"""
import json, os, re, struct, sys
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3,
                                UC_MIPS_REG_V0, UC_MIPS_REG_SP, UC_MIPS_REG_RA, UC_MIPS_REG_T9, UC_MIPS_REG_PC, UC_MIPS_REG_GP)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOOLS = os.path.join(ROOT, 'tools')
sys.path.insert(0, TOOLS)
import paths  # noqa: E402
import pod  # noqa: E402
import pod_pages  # noqa: E402
import pod_ui  # noqa: E402
import awtk_ui  # noqa: E402

WORK = DEMO = BUILD = MANIFEST = PSYMS = None   # set by init()
HOME_CLICK_RESUME = pod.HOME_CLICK + 12   # trampoline resumes stock here
RET = 0x00ff0000     # sentinel return address: emulation stops when PC lands here
STACK = 0x7ffe0000
SCRATCH = 0x10000000
HEAP = 0x40000000
HEAP_SIZE = 0x1000000


def init(work):
    """Point the harness at a built tree (the payload's manifest and symbols)."""
    global WORK, DEMO, BUILD, MANIFEST, PSYMS
    WORK = work
    DEMO = os.path.join(WORK, 'rootfs', pod.DEMO)
    BUILD = os.path.join(WORK, 'podbuild')
    MANIFEST = json.load(open(os.path.join(BUILD, 'manifest.json')))
    PSYMS = pod.symbols_elf(os.path.join(BUILD, 'patch.elf'))


class Ctx:
    """What a feature module's run(ctx) gets: the entry page, the built cover asset, and expect()."""
    def __init__(self, work):
        self.work, self.page = work, pod_pages.PAGES[0]
        self.cover_asset = os.path.join(work, 'rootfs', 'release/assets/default/raw/ui/m1pod_cover.bin')
        self.passed = self.failed = 0

    def expect(self, cond, msg):
        if cond: self.passed += 1
        else: self.failed += 1; print('  FAIL:', msg)


def offsets():
    """The constants patch/offsets.inc gives the payload, so the mocks cannot drift from it."""
    out = {}
    for line in open(os.path.join(ROOT, 'patch', 'offsets.inc')):
        m = re.match(r'#define (\w+) (-?(?:0x[0-9a-fA-F]+|\d+))u?\s*(?:/\*.*)?$', line.strip())
        if m: out[m.group(1)] = int(m.group(2), 0)
    return out


O = offsets()
# Cover Flow's page layout as tools/pod_ui.py builds ui/m1pod_cover.bin
CF_FRAME_Y, CF_ALBUM_Y, CF_ALBUM_H, CF_ARTIST_Y, CF_ARTIST_H = pod_ui.cover_layout()


def art_file(key):
    """The thumbnail cache file of an album key: <key>-168.jpg (the size is in the name)."""
    return f'/mnt/mmc/.coverflow/{key:08x}-{O["ART_SIZE"]}.jpg'
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
        self.types = {}             # handle -> widget type string (widget_get_type)
        self.deques = {}            # handle -> list of record addresses
        self.showlist = []          # what loadLocalClassList leaves in *pdeq_showlist
        self.class_lists = {}       # ... per class, where a test sets one (0xf004: the artists)
        self.tracklist = []         # what loadAlbumdetailList leaves there
        self.artist_albums = {}     # artist name -> its album rows (loadAlbumList 0xf004)
        self.artist_tracks = {}     # (artist, album) -> tracks; (artist, None) the All songs row's
        self.free_mb = 1024
        self.thread_ok = True
        self.album_cover = 0        # toolsGetAlbumCover's result
        self.extern_cover = 0
        self.load_image = 1         # widget_load_image: 0 = success
        self.images = {}            # url -> (w, h, RGBA bytes) widget_load_image decodes when it succeeds
        self.parent = {}            # widget handle -> parent handle
        self.handlers = {a: n for n, (_, _, a) in pod.FUNCTIONS.items()}
        for name in pod.LIBC:       # the payload's libc stubs, trapped at their entry
            if f'pod_lib_{name}' in PSYMS:   # --gc-sections drops the ones it does not call
                self.handlers[PSYMS[f'pod_lib_{name}']] = name
        self.handlers[HOME_CLICK_RESUME] = 'stock_resume'
        self.handlers[pod.HOME_INIT + 12] = 'stock_init_resume'
        # the Home guard's world (patch/home.c): flash/SD files, file descriptors, the window stack
        self.fs, self.fds, self.next_fd, self.fail = {}, {}, 3, set()
        self.dirs = {'/mnt/data'}
        self.timers = []            # (callback, ms) of every timer_add
        self.timer_fail = False
        self.create_fail = set()    # widget constructors (view_create, ..) that return 0
        self.wm, self.top_main, self.home_opened, self.init_ret = 0x22000000, 0, 1, 0
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

    def all_songs(self, artist):
        r = self.record(album='All songs', artist=artist, path='', title='All songs', name='', rid=O['ID_ALL_SONGS'])
        self.setword(r + O['REC_PATH'], 0); self.setword(r + O['REC_TYPE'], 4)
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
            p = self.read_cstr(a0); ret = 0 if p in self.present or p in self.fs else -1
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
            self.rect(w, a1, a2, a3, stack(0))
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
        elif name == 'widget_get_type':
            ret = self.cstr(self.types.get(a0, 'widget'))
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
            self.rect(w, a3, stack(0), stack(1), stack(2))
            self.parent[w] = a2
            if kind == 'slide_menu' and self.slide_starts_at_1: self.props[(w, 'value')] = 1   # the stock constructor (@0x613970)
            self.calls.append((kind, w, stack(1), stack(2)))
            self.widgets.setdefault(kind, w)
            ret = w
        elif name in ('image_create', 'list_view_create', 'scroll_view_create', 'list_item_create',
                      'label_create', 'view_create'):
            if name in self.create_fail:
                self.calls.append((name, 0)); ret = 0
                u.reg_write(UC_MIPS_REG_V0, 0); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
                return
            w = self.alloc(0x80)
            self.types[w] = {'image_create': 'image', 'label_create': 'label', 'view_create': 'view'}.get(name, name[:-7])
            self.children.setdefault(a0, []).append(w)
            self.rect(w, a1, a2, a3, stack(0))
            self.parent[w] = a0
            self.calls.append((name, w))
            ret = w
        elif name == 'widget_set_prop_bool':
            self.props[(a0, self.read_cstr(a1))] = a2
            self.calls.append(('widget_set_prop_bool', a0, self.read_cstr(a1), a2))
        elif name == 'widget_set_name':
            nm = self.read_cstr(a1)
            self.props[(a0, 'name')] = nm; self.widgets[nm] = a0
            self.setword(a0 + O['W_NAME'], self.cstr(nm))
            self.calls.append(('widget_set_name', a0, nm))
        elif name == 'label_set_line_wrap':
            self.calls.append(('label_set_line_wrap', a0, a1))
        elif name == 'slide_indicator_set_max':
            self.calls.append(('slide_indicator_set_max', a0, a1))
        elif name == 'widget_destroy':
            self.calls.append(('widget_destroy', a0))
            for kids in self.children.values():
                if a0 in kids: kids.remove(a0)
        elif name == 'window_close':
            self.calls.append(('window_close', a0))
        elif name == 'widget_move':
            self.props[(a0, 'x')], self.props[(a0, 'y')] = a1, a2
            self.calls.append(('widget_move', a0, a1, a2))
        elif name == 'widget_resize':
            self.props[(a0, 'w')], self.props[(a0, 'h')] = a1, a2
            self.calls.append(('widget_resize', a0, a1, a2))
        elif name == 'image_set_draw_type':
            self.calls.append(('image_set_draw_type', a0, a1))
        elif name == 'image_base_set_image':
            self.calls.append(('image_base_set_image', a0, self.read_cstr(a1)))
        elif name == 'widget_load_image':
            url = self.read_cstr(a1)
            self.calls.append(('widget_load_image', url))
            ret = self.load_image
            img = self.images.get(url)
            if img and not ret:   # decode: bitmap_t w, h, format, data (RGBA8888, tightly packed)
                iw, ih, pix = img
                data = self.malloc(len(pix)); self.u.mem_write(data, pix)
                self.setword(a2, iw); self.setword(a2 + 4, ih); self.setword(a2 + 0x14, data)
                self.u.mem_write(a2 + O['BITMAP_FORMAT'], struct.pack('<H', O['BITMAP_RGBA8888']))
        elif name == 'widget_unload_image':
            self.calls.append(('widget_unload_image',))
        elif name == 'slide_menu_set_value':
            self.props[(a0, 'value')] = a1
            self.calls.append(('slide_menu_set_value', a1))
        elif name == 'timer_add':
            self.calls.append(('timer_add', a0, a2)); ret = 0 if self.timer_fail else 0x777
            if ret: self.timers.append((a0, a2))
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
            items = self.class_lists.get(a0, self.showlist)
            self.setword(pod.DATA['PDEQ_SHOWLIST'][0], self.new_deque(items))
            ret = len(items)
        elif name == 'loadAlbumList':
            # loadAlbumList(0xf004, artist row): the artist's albums, then the "All songs" row
            # (id -2, type 4, the artist at REC_ARTIST) getAlbumByArtist always appends; class 0xff01
            artist = self.read_cstr(self.word(a1 + O['REC_TITLE'])) if a1 else ''
            self.calls.append(('loadAlbumList', a0, a1, artist))
            if a0 == O['CLASS_ALBUMS']:   # the stock Albums page: every album (class 0xf003), no artist
                items = self.class_lists.get(a0, self.showlist)
                self.setword(pod.DATA['PDEQ_SHOWLIST'][0], self.new_deque(items))
                self.setword(pod.DATA['CLASSINFO'][0], a0)
                u.reg_write(UC_MIPS_REG_V0, len(items)); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
                return
            items = list(self.artist_albums.get(artist, []))
            if artist in self.artist_albums: items.append(self.all_songs(artist))
            self.setword(pod.DATA['PDEQ_SHOWLIST'][0], self.new_deque(items))
            self.setword(pod.DATA['CLASSINFO'][0], O['CLASS_ARTIST_ALBUMS'])
            self.classinfo_artist = artist
            ret = len(items)
        elif name == 'loadAlbumdetailList':
            self.calls.append(('loadAlbumdetailList', a0, a1))
            items, cls = self.tracklist, O['CLASS_ALBUM_TRACKS']
            if a0 == O['CLASS_ARTIST_ALBUMS']:   # 0xff11: the album by the artist in classinfo
                rid = struct.unpack('<i', self.u.mem_read(a1 + O['REC_ID'], 4))[0]
                album = None if rid == O['ID_ALL_SONGS'] else self.read_cstr(self.word(a1 + O['REC_ALBUM']))
                items, cls = self.artist_tracks.get((self.classinfo_artist, album), []), 0xff11
            self.setword(pod.DATA['PDEQ_SHOWLIST'][0], self.new_deque(items))
            self.setword(pod.DATA['CLASSINFO'][0], cls)
            ret = len(items)
        elif name == 'loadSongList':
            self.calls.append(('loadSongList', self.read_cstr(a1), a2, a3))
            if self.stock_songlist:   # as stock does (@0x4e2ce0): the shown list's songs, class set,
                ret, out = -1, []    # the first song with this file name and CUE start
                key = (self.read_cstr(a1), a2)
                for r in self.deques.get(self.word(pod.DATA['PDEQ_SHOWLIST'][0]), []):
                    if self.word(r + O['REC_TYPE']) != 8: continue
                    self.setword(r + O['REC_CLASS'], a3)
                    out.append(r)
                    if ret < 0 and (self.read_cstr(self.word(r + O['REC_NAME'])), self.word(r + O['REC_CUE_START'])) == key:
                        ret = len(out) - 1
                self.deques[a0] = out
            else:
                self.deques[a0] = list(self.tracklist)
                ret = 1
        elif name == 'navigator_to_with_context':
            ctx = self.read_cstr(a0)
            if ctx == 'albuminfo_page':   # the context is a value, not a pointer: class | row << 16 (@0x523d94)
                self.calls.append(('navigator_to_with_context', ctx, a1 & 0xffff, a1 >> 16))
                self.opened_album = (a1 & 0xffff, a1 >> 16, self.word(pod.DATA['PDEQ_SHOWLIST'][0]))
                ret = 0
                u.reg_write(UC_MIPS_REG_V0, ret); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
                return
            self.calls.append(('navigator_to_with_context', ctx, self.word(a1 + 4),
                               self.word(a1 + 8), self.word(a1 + 12)))
            if ctx == 'playing_page':   # the queue as start_player copies it, and the class of its songs
                q = list(self.deques.get(self.word(a1), []))
                self.played = (q, self.word(a1 + 4))
            elif ctx == 'dialog/msginfo_dialog':
                self.calls.append(('toast', self.read_cstr(a1 + 8), self.word(a1), self.word(a1 + 4)))
        elif name == 'albumcoverinfo_init':
            self.calls.append(('albumcoverinfo_init', a0))
        elif name == 'batchadd_albumcover_task':
            self.calls.append(('batchadd_albumcover_task', a0, a1))
        elif name == 'start_player':   # the stock Play all / Shuffle start: the queue as copied, index, class, mode
            self.calls.append(('start_player', a1, a2, a3))
            self.played = (list(self.deques.get(a0, [])), a1)
        elif name == 'widget_destroy':
            self.calls.append(('widget_destroy', a0))
        # ---- Shuffle: the stock play mode, the seed
        elif name == 'mclGetPlayMode':
            ret = self.mode
        elif name == 'mclSetPlayMode':
            self.mode = a0; self.calls.append(('mclSetPlayMode', a0))
        elif name == 'notifyPlayMode':
            self.calls.append(('notifyPlayMode',))
        elif name == 'dmrSendPlayMode':
            self.calls.append(('dmrSendPlayMode', a0))
        elif name == 'write_int_config':
            self.calls.append(('write_int_config', a0, self.read_cstr(a1), self.read_cstr(a2)))
        elif name == 'toolsRandnum':
            ret = self.seed % a0 if a0 else 0
        elif name == 'time_now_ms':
            ret = self.clock; u.reg_write(UC_MIPS_REG_A3, 0)
        elif name == 'toolsGetAlbumCover':
            self.cover_size = (a2, a3)   # the thumbnail's requested size
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
        elif name == 'strcasecmp':
            x, y = self.read_cstr(a0).lower(), self.read_cstr(a1).lower(); ret = (x > y) - (x < y)
        elif name == '_deque_push_back':
            self.deques.setdefault(a0, []).append(a1); self.calls.append(('_deque_push_back', a0, a1))
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
            self.u.mem_write(a0, out.encode('latin-1') + b'\0'); ret = len(out)   # bytes as read_cstr shows them
            self.calls.append(('snprintf', out))
        elif name == 'calloc':
            n = a0 * a1
            if self.heap + n >= HEAP + HEAP_SIZE or self.calloc_fail: ret = 0
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
            if src in self.fs and ('rename', dst) not in self.fail:
                self.fs[dst] = self.fs.pop(src)
            elif src in self.fs: ret = -1
            elif src in self.files:
                self.files[dst] = self.files.pop(src); self.present.discard(src); self.present.add(dst)
            else: ret = -1
        elif name == 'unlink':
            p = self.read_cstr(a0); self.files.pop(p, None); self.present.discard(p)
            ret = 0 if self.fs.pop(p, None) is not None else ret
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
        # ---- Home guard: files, descriptors, the window stack
        elif name == 'open':
            p, fl = self.read_cstr(a0), a1
            self.calls.append(('open', p, fl))
            if ('open', p) in self.fail: ret = -1
            elif p in self.dirs: ret = self.next_fd; self.fds[ret] = [p, fl, 0]; self.next_fd += 1
            elif p in self.fs or fl & 0x100:
                if fl & 0x200 or p not in self.fs: self.fs[p] = b''
                ret = self.next_fd; self.fds[ret] = [p, fl, 0]; self.next_fd += 1
            else: ret = -1
        elif name == 'read':
            p, _, pos = self.fds[a0]
            data = self.fs.get(p, b'')[pos:pos + a2]
            self.u.mem_write(a1, data) if data else None
            self.fds[a0][2] += len(data); ret = len(data)
            self.calls.append(('read', p))
        elif name == 'write':
            p = self.fds[a0][0]; data = bytes(self.u.mem_read(a1, a2))
            self.calls.append(('write', p, data))
            if ('write', p) in self.fail: ret = -1
            else: self.fs[p] = self.fs.get(p, b'') + data; ret = a2
        elif name == 'fsync':
            p = self.fds[a0][0]; self.calls.append(('fsync', p))
            ret = -1 if ('fsync', p) in self.fail else 0
        elif name == 'close':
            self.calls.append(('close', self.fds.pop(a0)[0]))
        elif name == 'window_manager':
            ret = self.wm
        elif name == 'window_manager_get_top_main_window':
            self.calls.append(('get_top_main_window', a0)); ret = self.top_main
        elif name == 'widget_is_window_opened':
            ret = self.home_opened
        elif name == 'stock_init_resume':
            self.calls.append(('stock_init_resume', a0, a1)); ret = self.init_ret
        else:
            raise AssertionError(f'unmocked call {name} at {address:#x}')
        u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff)
        u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    def rect(self, w, x, y, cw, ch):
        for k, v in (('x', x), ('y', y), ('w', cw), ('h', ch)): self.props[(w, k)] = v

    saved_album = 0
    slide_starts_at_1 = True   # the stock slide_menu constructor stores value = 1 (the payload sets the value itself)
    classinfo_artist = ''
    fh = (0, '')
    stock_songlist = False   # loadSongList: stock's copy of the shown list (Shuffle) or the album mock
    mode = 0                 # mclGetPlayMode
    seed = 12345             # toolsRandnum
    clock = 1                # time_now_ms
    calloc_fail = False
    played = None            # (queue records, index) handed to playing_page
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

    def tap(self, x, y=150, count=4000000):
        self.touch('down', x, y, 1000, count=count); calls = list(self.calls)
        self.touch('up', x, y, 1080, count=count); self.calls = calls + self.calls

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


def cover_page_tree(m, asset, runtime=True):
    """The Cover Flow page as the window manager sees it: the built asset, the runtime
    slide_menu and touch layer in view_covers, and every visibility/sensitivity the payload set."""
    root = asset_tree(asset)
    for n in COVER_WIDGETS:
        nd, h = node(root, n), m.widgets.get(n)
        if not nd or h is None: continue
        if (h, 'visible') in m.props:
            nd.flags = nd.flags & ~F_VISIBLE | (F_VISIBLE if m.props[(h, 'visible')] else 0)
        if (h, 'sensitive') in m.props:
            nd.flags = nd.flags & ~F_SENSITIVE | (F_SENSITIVE if m.props[(h, 'sensitive')] else 0)
    if runtime:
        covers = node(root, 'view_covers')
        slide = m.widgets.get('slide_menu')
        sf = F_ENABLE | F_VISIBLE | F_SENSITIVE
        if slide and m.props.get((slide, 'sensitive')) == 0: sf &= ~F_SENSITIVE
        covers.children.append(Node('slide_menu', 0, 0, 320, O['CF_VIEW_H'], sf))
        if m.widgets.get('view'):
            covers.children.append(Node('touch_layer', 0, 0, 320, O['CF_VIEW_H']))
    return root


COVER_WIDGETS = ['btn_return', 'btn_backtoplayer', 'btn_cancel', 'view_covers',
                 'label_album', 'label_artist', 'label_status', 'label_title']


def cover_machine(albums=3, tracks=2, cached=True):
    """A machine set up to open Cover Flow: the asset's widgets, an album list and, by default,
    a complete thumbnail cache (so no build runs)."""
    m = Machine()
    for n in COVER_WIDGETS: m.widget(n)
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
    return [art_file(fnv(fnv(O["FNV_SEED"], f"Artist {i}"), f"Album {i}") or 1)
            for i in range(albums)]


def artists_row(page):
    return next((i for i, r in enumerate(page.rows) if r.action == pod_pages.ACT_ARTISTS), None)


def artist_rec(m, name, rid):
    """An Artists row as getAllArtist / GetAllAlbumArtist leave it: the name in REC_TITLE."""
    return m.record(album='', artist=name, path='', title=name, name='', rid=rid)


def artists_machine(artists=('Miles Davis', 'Nina Simone', 'Unknown Artist')):
    """A machine with the Artists page's widgets, the stock artist list (class 0xf004), each
    artist's albums (loadAlbumList) and the library album list (getAllAlbum). Miles Davis has
    three albums, one of them (Jazz Hits) filed under Various Artists in the library list; Nina
    Simone has one; Unknown Artist none. Every library album is cached under its library key."""
    m = cover_machine(albums=0)
    for n in ('pod_listview', 'pod_scrollview'): m.widget(n)
    m.props[(m.widgets['pod_scrollview'], 'w')] = 310
    m.class_lists[O['CLASS_ARTISTS']] = [artist_rec(m, a, -1 if a == 'Unknown Artist' else i + 1)
                                         for i, a in enumerate(artists)]
    albums = {'Miles Davis': ['Kind of Blue', 'Jazz Hits', 'Bitches Brew'], 'Nina Simone': ['Pastel Blues'],
              'Unknown Artist': []}
    library = []   # getAllAlbum's rows: one per album name
    for artist, names in albums.items():
        if artist not in artists: continue
        m.artist_albums[artist] = []
        for album in names:
            path = f'/mnt/mmc/{artist}/{album}/1.flac'
            m.artist_albums[artist].append(m.record(album=album, artist=artist, path=path, rid=100 + len(library)))
            lib_artist = 'Various Artists' if album == 'Jazz Hits' else artist
            library.append(m.record(album=album, artist=lib_artist, path=path, rid=len(library) + 1))
            c = art_file(fnv(fnv(O["FNV_SEED"], lib_artist), album) or 1)
            m.present.update((path, c)); m.files[c] = 4096
            m.artist_tracks[(artist, album)] = [
                m.record(album=album, artist=artist, title=f'{album} {t}', name=f'{album}{t}.flac',
                         path=f'/mnt/mmc/{artist}/{album}/{t}.flac', rid=500 + t) for t in range(2)]
        m.artist_tracks[(artist, None)] = [t for a in names for t in m.artist_tracks[(artist, a)]]
    for tracks in m.artist_tracks.values():
        for t in tracks: m.present.add(m.read_cstr(m.word(t + O['REC_PATH'])))
    m.class_lists[O['CLASS_ALBUMS']] = library
    m.showlist = library
    return m


def paint(m):
    """One EVT_AFTER_PAINT on the touch layer, as stock's widget_paint dispatches it."""
    m.props[(m.widgets['slide_menu'], 'h')] = O['CF_VIEW_H']
    event = m.alloc(0x40); m.u.mem_write(event, bytes(0x40))
    m.setword(event + O['EVENT_PAINT_CANVAS'], 0x22220000)
    m.call(PSYMS['on_paint'], a0=0, a1=event, count=400000000)


def host_frame(frac, ring=None):
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
            frame = hostcf.render(lib, frac, [tex if r else None for r in ring] if ring else [tex] * 7)
            return bytes(frame)
    except Exception as e:                                   # noqa: BLE001 - a host build is optional
        print('  host build failed:', e)
        return None
