"""Library rows: the pinned demo edits and the restyled stock row builders."""
import json, os, re, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)


# Library rows (patch/rows.c, patch/rows.json). The real stock row
# constructors run (their widget-creation calls mocked into a widget model in emulated memory:
# x/y/w/h @0..0xc, flags @0x24, children layout @0x64), so the retargeted `jal
# compact_set_row_layout` is exercised as patched; the installed layouter is then run for real,
# with the stock default layout (0x63a444, r=1,c=0: each visible child keeps its width, gets
# y = y_margin, h = h - 2 * y_margin, x advancing by width + spacing) modelled in Python.
ROW_BUILDERS = {'music_create_tablerow': 0x528560, 'folder_create_tablerow': 0x5331fc,
                'localclass_create_tablerow': 0x5368ac, 'album_listitem_layout': 0x524228,
                'albumdeinfo_listitem_layout': 0x526394, 'playlist_listitem_layout': 0x53e44c,
                'search_albums_row': 0x542630}
CREATE = ('table_row_create', 'button_create', 'image_create', 'view_create', 'hscroll_label_create',
          'list_item_create', 'label_create')
ROW_STUBS = ('memset', 'snprintf', 'strcpy', 'deque_at')          # libc / libcstl through demo's stubs
ROW_PLAIN = ('widget_set_name', 'widget_use_style', 'image_base_set_image', 'image_set_draw_type',
             'hscroll_label_set_ellipses', 'hscroll_label_set_speed', 'get_indexrecord', 'is_playing',
             'is_otherplaying', 'getFormatString', 'toolsTrimLeft', 'toolsTrimRight', 'tk_snprintf',
             'widget_set_text_utf8', 'widget_on')


PLAYLIST_DEQ = 0xa045d0
SEARCH_DEQ = 0xa045b8


def bind_normal(m, row):
    """What a row's bind does outside multi-select before AWTK lays it out: no check box, no badge."""
    for n in ('img_choice', 'img_mqa'):
        w = m.find(row, n)
        if w: m.set_visible(w, 0)


class RowMachine(Machine):
    def __init__(self):
        super().__init__()
        syms = pod.dynsym(DEMO)
        self.rows_names = set()
        for n in CREATE + ROW_PLAIN + ('widget_set_visible',):
            if n in syms: self.handlers[syms[n]] = 'row:' + n
        got = pod.got_slots(DEMO, ROW_STUBS)
        for n, slot in got.items(): self.handlers[self.word(slot)] = 'row:' + n
        for n in ('widget_count_children', 'widget_get_child', 'widget_get_type', 'widget_get_visible',
                  'widget_resize', 'widget_move', 'hscroll_label_set_only_focus', 'widget_set_children_layout'):
            self.handlers[pod.FUNCTIONS[n][2]] = 'row:' + n
        self.handlers[O['DEFAULT_LAYOUT_FN']] = 'row:stock_layout'
        self.handlers[pod.FUNCTIONS['widget_set_tr_text'][2]] = 'row:widget_set_tr_text'
        self.wtype, self.wname, self.style, self.focus, self.texts = {}, {}, {}, {}, {}
        self.types = {}
        self.layout_ret = 0
        self.layout_vt = O['DEFAULT_LAYOUT_VTABLE']   # what widget_set_children_layout creates
        self.stock_layouts = 0
        self.resizes = []

    def new_widget(self, kind, parent, x, y, w, h):
        a = self.alloc(0x80); self.u.mem_write(a, bytes(0x80))
        for off, v in ((0, x), (4, y), (8, w), (0xc, h), (0x24, F_ENABLE | F_VISIBLE | F_SENSITIVE), (0x44, parent)):
            self.setword(a + off, v)
        self.wtype[a] = kind
        if parent: self.children.setdefault(parent, []).append(a)
        return a

    def geo(self, w): return tuple(self.word(w + o) - (1 << 32 if self.word(w + o) >> 31 else 0) for o in (0, 4, 8, 12))
    def visible(self, w): return bool(self.word(w + 0x24) & F_VISIBLE)
    def set_visible(self, w, v):
        f = self.word(w + 0x24); self.setword(w + 0x24, f | F_VISIBLE if v else f & ~F_VISIBLE)
    def kids(self, w): return self.children.get(w, [])
    def find(self, root, name):
        if self.wname.get(root) == name: return root
        for c in self.kids(root):
            r = self.find(c, name)
            if r: return r

    def default_layout(self, layout, row):
        if not layout or not row: return 0x10
        self.stock_layouts += 1
        xm, ym, sp = (self.u.mem_read(layout + 0x14, 3))
        x, (_, _, _, h) = xm, self.geo(row)
        for c in [c for c in self.kids(row) if self.visible(c)]:
            cw = self.geo(c)[2]
            self.setword(c, x); self.setword(c + 4, ym); self.setword(c + 0xc, h - 2 * ym)
            x += cw + sp
        for c in self.kids(row): self.layout_children(c)
        return 0

    def layout_children(self, w):
        """widget_layout_children: the widget's layouter, else each child's own children in turn."""
        inner = self.word(w + O['W_CHILDREN_LAYOUT'])
        if inner: self.default_layout(inner, w)
        else:
            for c in self.kids(w): self.layout_children(c)

    def _hook(self, u, address, size, _):
        name = self.handlers.get(address)
        if not name or not name.startswith('row:'):
            return super()._hook(u, address, size, _)
        name = name[4:]
        a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        sp = u.reg_read(UC_MIPS_REG_SP)
        stack = lambda i: self.word(sp + 16 + 4 * i)
        sx = lambda v: v - (1 << 32) if v >> 31 else v
        ret = 0
        if name in CREATE:
            kind = name[:-len('_create')]
            ret = self.new_widget(kind, a0, sx(a1), sx(a2), sx(a3), sx(stack(0)))
            self.calls.append(('create', kind, ret, a0))
        elif name == 'widget_set_name': self.wname[a0] = self.read_cstr(a1)
        elif name == 'widget_use_style': self.style[a0] = self.read_cstr(a1)
        elif name == 'widget_set_text_utf8': self.texts[a0] = self.read_cstr(a1)
        elif name == 'widget_set_tr_text': self.texts[a0] = self.tr(self.read_cstr(a1)); self.calls.append(('widget_set_tr_text', a0, self.read_cstr(a1)))
        elif name == 'widget_set_visible':
            self.set_visible(a0, a1); self.calls.append(('widget_set_visible', a0, a1))
        elif name == 'widget_count_children': ret = len(self.kids(a0))
        elif name == 'widget_get_child':
            k = self.kids(a0); ret = k[a1] if a1 < len(k) else 0
        elif name == 'widget_get_type':
            t = self.wtype.get(a0)
            if t and t not in self.types: self.types[t] = self.cstr(t)
            ret = self.types.get(t, 0)
        elif name == 'widget_get_visible': ret = int(self.visible(a0))
        elif name == 'widget_resize':   # stock returns early on an unchanged size (@0x66d198)
            if self.geo(a0)[2:] != (sx(a1), sx(a2)): self.resizes.append((a0, sx(a1), sx(a2)))
            self.setword(a0 + 8, a1); self.setword(a0 + 0xc, a2)
        elif name == 'widget_move':
            self.setword(a0, a1); self.setword(a0 + 4, a2); self.calls.append(('widget_move', a0, sx(a1), sx(a2)))
        elif name == 'hscroll_label_set_only_focus': self.focus[a0] = a1
        elif name == 'widget_set_children_layout':
            params = self.read_cstr(a1)
            self.calls.append(('widget_set_children_layout', a0, params))
            ret = self.layout_ret if a0 else 0x10
            if not ret:
                lay = self.alloc(0x20); self.u.mem_write(lay, bytes(0x20))
                self.setword(lay + O['LAYOUT_VTABLE'], self.layout_vt)
                vals = dict(re.findall(r'([xys])=(\d+)', params))
                self.u.mem_write(lay + 0x14, bytes([int(vals.get('x', 0)), int(vals.get('y', 0)), int(vals.get('s', 0))]))
                self.setword(a0 + O['W_CHILDREN_LAYOUT'], lay)
        elif name == 'stock_layout': ret = self.default_layout(a0, a1)
        elif name == 'memset': self.u.mem_write(a0, bytes([a1 & 0xff]) * a2); ret = a0
        elif name in ('snprintf', 'tk_snprintf'):
            if a0 and a1: self.u.mem_write(a0, b'x\0')
            ret = 1
        elif name == 'strcpy':
            self.u.mem_write(a0, self.read_cstr(a1).encode('latin-1') + b'\0'); ret = a0
        elif name == 'deque_at':
            items = self.deques.get(a0, []); ret = items[a1] if a1 < len(items) else 0
        elif name == 'getFormatString':
            self.u.mem_write(a1, self.read_cstr(a0).encode('latin-1') + b'\0'); ret = a1
        # get_indexrecord, is_playing, is_otherplaying, trims, image calls, widget_on: 0, recorded
        else: self.calls.append((name, a0, a1))
        u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff)
        u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    def layout(self, row):
        """Run the row's installed layouter the way AWTK does: vtable slot 2 (layouter, row)."""
        lay = self.word(row + O['W_CHILDREN_LAYOUT'])
        fn = self.word(self.word(lay + O['LAYOUT_VTABLE']) + 4 * O['LAYOUT_SLOT'])
        self.resizes = []
        return self.call(fn, a0=lay, a1=row, count=400000)


def row_machine(albums=1):
    m = RowMachine()
    recs = [m.record(album=f'A long album title number {i}', artist='Artist', title=f'Track {i}') for i in range(albums)]
    dq = m.new_deque(recs)
    m.setword(pod.DATA['PDEQ_SHOWLIST'][0], dq)   # what the album rows read
    m.setword(PLAYLIST_DEQ, dq)                   # playlist_listitem_layout: lw $a0, 0($v0 = 0xa045d0) @0x53e5f0
    m.setword(SEARCH_DEQ, dq)                     # the search album rows: lw $a0, 0($v0 = 0xa045b8) @0x542720
    return m


def rows_tests(expect):
    import json
    edits = MANIFEST.get('row_edits', [])
    J = json.load(open(os.path.join(ROOT, 'patch', 'rows.json')))
    target = PSYMS['compact_set_row_layout']
    # 37. Pins: every edit as rows.json says, on the stock word, in the built demo; nothing else.
    stock_demo = open(os.path.join(paths.find_stock() or os.path.join(os.path.dirname(WORK), 'stock'), 'rootfs', pod.DEMO), 'rb').read()
    built = open(DEMO, 'rb').read()
    w = lambda b, a: struct.unpack_from('<I', b, pod.fileoff(b, a))[0]
    kinds = {k: sum(e[3] == k for e in edits) for k in ('immediate', 'call', 'nop')}
    expect(kinds == {'immediate': sum(len(g['sites']) for g in J['immediates']),
                     'call': len(J['row_layout_calls']['sites']), 'nop': len(J['nops']['sites'])},
           f'the manifest lists every rows.json edit ({kinds})')
    expect(all(w(stock_demo, int(a, 16)) == int(old, 16) and w(built, int(a, 16)) == int(new, 16) for a, old, new, _ in edits),
           f'all {len(edits)} edits: stock word before, the patched word in the built demo')
    expect(all(int(new, 16) == 0x0c000000 | (target >> 2) for a, old, new, k in edits if k == 'call'),
           'each row-layout call is jal compact_set_row_layout')
    expect(all(int(new, 16) == (int(old, 16) & 0xffff0000) | g['value'] for g in J['immediates']
               for a, old, *_ in g['sites'] for e in edits if e[0] == hex(int(a, 16)) for new in (e[2],)),
           'each immediate keeps its instruction and register, only the 16-bit value changes')
    pins = [s for g in J['pinned'] for s in g['sites']]
    expect(all(w(built, int(a, 16)) == int(old, 16) for a, old, *_ in pins), f'the {len(pins)} pinned words are untouched')
    # inside the stock file length only .pdr, PH[10], the hook and these words differ from stock
    changed = {i * 4 for i in range(len(stock_demo) // 4) if built[4 * i:4 * i + 4] != stock_demo[4 * i:4 * i + 4]}
    phoff = struct.unpack_from('<I', built, 28)[0]
    allowed = set(range(phoff + 10 * 32, phoff + 11 * 32, 4)) | {pod.fileoff(built, pod.HOME_CLICK), pod.fileoff(built, pod.HOME_CLICK) + 4}
    allowed |= {pod.fileoff(built, int(a, 16)) for a, *_ in edits}
    # the boot guard's hook on home_page_init, the same two words
    allowed |= {pod.fileoff(built, pod.HOME_INIT), pod.fileoff(built, pod.HOME_INIT) + 4}
    allowed |= {pod.fileoff(built, pod.ALBUMINFO_HEADER), pod.fileoff(built, pod.ALBUMINFO_HEADER) + 4}   # the album header hook
    allowed |= {pod.fileoff(built, pod.PLAYING_INIT), pod.fileoff(built, pod.PLAYING_INIT) + 4}           # the Now Playing init hook
    import mod_nowplaying   # the A-B marker immediates (five pinned words, disjoint from the row edits)
    expect(not {hex(a) for a in mod_nowplaying.MARKER_WORDS} & {e[0] for e in edits}, 'the 5 A-B marker sites are not among the row edits')
    allowed |= {pod.fileoff(built, a) for a in mod_nowplaying.MARKER_WORDS}
    # the lock screen also sets the cover file size in four `addiu a3/a2, zero, 0xfe` words
    # (mod_lockscreen.COVER_IMM); they must be disjoint from the row edits and only change the 16-bit value
    cover_sites = (0x4df1dc, 0x4df1e0, 0x4df21c, 0x4df220)
    expect(not {hex(c) for c in cover_sites} & {e[0] for e in edits}, 'the 4 cover-size sites are not among the row edits')
    for c in cover_sites:
        o, n = w(stock_demo, c), w(built, c)
        if o != n:
            expect(o in (0x240700fe, 0x240600fe) and (n & 0xffff0000) == (o & 0xffff0000) and 66 <= (n & 0xffff) < 0x8000,
                   f'cover-size word {c:#x}: addiu immediate only ({o:#010x} -> {n:#010x})')
            allowed.add(pod.fileoff(built, c))
    from elftools.elf.elffile import ELFFile
    pdr = [s for s in ELFFile(open(DEMO, 'rb')).iter_sections() if s.name == '.pdr']
    if pdr: allowed |= set(range(pdr[0]['sh_offset'] // 4 * 4, pdr[0]['sh_offset'] + pdr[0]['sh_size'] + 4, 4))
    extra = sorted(changed - allowed)
    expect(not extra, f'demo differs from stock only in .pdr, PH[10], the hook and the row edits ({[hex(x) for x in extra[:6]]})')
    hook_words = {pod.fileoff(built, h + 4 * k) for h in (pod.HOME_CLICK, pod.HOME_INIT, pod.ALBUMINFO_HEADER) for k in range(3)}
    expect(not any(pod.fileoff(built, int(a, 16)) in hook_words for a, *_ in edits), 'no row edit touches a hook')

    # 38. Songs: the real music_create_tablerow builds a 64 px row with a 60 px button; its layout
    #     call reaches compact_set_row_layout, which installs the row fit.
    m = row_machine()
    table = m.new_widget('table_client', 0, 0, 0, 310, 400)
    m.call(ROW_BUILDERS['music_create_tablerow'], a0=table, count=400000)
    row = m.kids(table)[0]; btn = m.kids(row)[0]
    lay = m.word(btn + O['W_CHILDREN_LAYOUT'])
    vt = m.word(lay + O['LAYOUT_VTABLE'])
    expect(m.geo(row)[3] == 64 and m.geo(btn)[3] == 60 and m.wname.get(btn) == 'btn_table_row',
           f'Songs: table_row 310x{m.geo(row)[3]}, btn_table_row 310x{m.geo(btn)[3]} (PITCH 64, BODY 60)')
    expect(('widget_set_children_layout', btn, 'default(r=1,c=0,x=12,s=8)') in m.calls,
           'the constructor\'s own layout call reaches the stock widget_set_children_layout through the payload')
    expect(vt == PSYMS['row_vtable'] and m.word(vt + 4 * O['LAYOUT_SLOT']) == PSYMS['compact_row_layout'] and
           all(m.word(vt + 4 * k) == m.word(O['DEFAULT_LAYOUT_VTABLE'] + 4 * k) for k in range(O['LAYOUT_VTABLE_WORDS'])
               if k != O['LAYOUT_SLOT']),
           'the row\'s layouter now uses the default vtable with compact_row_layout in the layout slot')
    bind_normal(m, row); m.set_visible(m.find(row, 'img_mqa'), 1)
    m.layout(btn)
    g = lambda n: m.geo(m.find(row, n))
    name, info, artist = m.find(row, 'scrlabel_name'), m.find(row, 'view_info'), m.find(row, 'scrlabel_artist')
    va = [c for c in m.kids(info) if m.wtype[c] == 'view'][0]
    expect(g('img_icon')[:2] == (12, 0) and g('view_info') == (60, 0, 238, 60),
           f'Songs: icon at 12, text container x 60 w 238 (to 298) ({g("img_icon")}, {g("view_info")})')
    expect(g('scrlabel_name') == (0, 7, 238, 24) and m.geo(va) == (0, 33, 238, 20),
           f'Songs: title (0, 7, 238, 24), second line (0, 33, 238, 20) ({g("scrlabel_name")}, {m.geo(va)})')
    mqa = g('img_mqa')
    expect(g('scrlabel_artist')[0] == 25 and g('scrlabel_artist')[2] == 213 and mqa[2] == 20,
           f'Songs: with the MQA badge the artist runs 25 .. 238 ({g("scrlabel_artist")})')
    m.set_visible(m.find(row, 'img_mqa'), 0); m.layout(btn)
    expect(g('scrlabel_artist')[:3] == (0, 0, 238), f'without it the artist takes the whole line ({g("scrlabel_artist")})')
    expect(m.focus.get(name) == 1 and m.focus.get(artist) == 1, 'Songs: title and artist scroll only while focused')
    m.set_visible(m.find(row, 'img_choice'), 1); m.layout(btn)
    expect(g('view_info')[0] == 94 and g('view_info')[2] == 204 and g('scrlabel_name')[2] == 204,
           f'Songs multi-select: the check box takes 34 px, the text 94 .. 298 ({g("view_info")})')
    m.set_visible(m.find(row, 'img_choice'), 0); m.layout(btn); before = [m.geo(c) for c in m.kids(btn)]
    m.layout(btn)
    expect(not m.resizes and [m.geo(c) for c in m.kids(btn)] == before,
           'a second layout pass changes nothing (no relayout loop)')

    # 39. Folders and Artists/Genres: one 21 px line, x 60, 217 with the chevron, 238 without.
    for key in ('folder_create_tablerow', 'localclass_create_tablerow'):
        m = row_machine()
        table = m.new_widget('table_client', 0, 0, 0, 310, 400)
        m.call(ROW_BUILDERS[key], a0=table, count=400000)
        row = m.kids(table)[0]; btn = m.kids(row)[0]
        bind_normal(m, row)
        m.layout(btn)
        lab, chev = m.find(row, 'scrlabel_name'), m.kids(btn)[-1]
        expect(m.geo(row)[3] == 64 and m.geo(btn)[3] == 60 and m.geo(lab)[0] == 60 and m.geo(lab)[2] == 217 and
               m.geo(chev)[0] == 285 and m.geo(chev)[2] == 13,
               f'{key}: row 64 / button 60, title x 60 w 217, chevron 285 .. 298 ({m.geo(lab)}, {m.geo(chev)})')
        m.set_visible(chev, 0); m.layout(btn)
        expect(m.geo(lab)[2] == 238 and m.focus.get(lab) == 1,
               f'{key}: no chevron (a song file): the title runs to 298, scrolls only focused ({m.geo(lab)})')

    # 40. Albums (x=0 list_item rows): 52 px cover drawn 1:1 at (4, 4) within the 60 px body,
    #     title and artist x 60 w 217, chevron 285 .. 298; the row keeps its 64 px.
    m = row_machine()
    item = m.new_widget('list_item', 0, 0, 0, 310, 64)
    m.call(ROW_BUILDERS['album_listitem_layout'], a0=item, a1=0, count=600000)
    expect(('widget_set_children_layout', item, 'default(r=1,c=0,x=0,s=8)') in m.calls and
           m.word(m.word(item + O['W_CHILDREN_LAYOUT']) + O['LAYOUT_VTABLE']) == PSYMS['row_vtable'],
           'Albums: the row layout call installs the row fit')
    m.layout(item)
    kids = m.kids(item)
    choice, cover, text, chev = kids[0], kids[1], kids[2], kids[3]
    t_title, t_artist = m.kids(text)[:2]
    expect(m.geo(cover) == (4, 0, 52, 60) and m.geo(item)[3] == 64,
           f'Albums: cover 52 x 60 at x 4 (a 52 px thumbnail centres 1:1: 4 px inset), row still 64 ({m.geo(cover)})')
    expect(m.geo(text) == (60, 0, 217, 60) and m.geo(t_title) == (0, 7, 217, 24) and m.geo(t_artist) == (0, 33, 217, 20),
           f'Albums: text x 60 w 217, title (0, 7), artist (0, 33) ({m.geo(text)}, {m.geo(t_title)}, {m.geo(t_artist)})')
    expect(m.geo(chev)[0] == 285 and m.geo(chev)[2:] == (13, 60) and all(m.geo(c)[3] == 60 for c in kids if m.visible(c)),
           f'Albums: chevron 285 .. 298; every child on the 60 px body above the separator ({m.geo(chev)})')
    m.set_visible(choice, 1); m.layout(item)
    expect(m.geo(text)[2] == 159 and m.geo(cover)[0] == 58 and m.geo(choice)[0] == 0,
           f'Albums multi-select: the 50 px check box first, the cover after it, text 159 ({m.geo(choice)}, {m.geo(cover)}, {m.geo(text)})')

    # 41. Album tracks and Playlists (x=12 list_item rows): one stretched label.
    m = row_machine()
    item = m.new_widget('list_item', 0, 0, 0, 310, 64)
    m.call(ROW_BUILDERS['albumdeinfo_listitem_layout'], a0=item, a1=0, count=600000)
    m.layout(item)
    lab = [c for c in m.kids(item) if m.wtype[c] == 'hscroll_label'][0]
    expect(m.geo(lab) == (12, 0, 286, 60) and m.focus.get(lab) == 1,
           f'album tracks: "N title" x 12 w 286 on the 60 px body, scrolls only focused ({m.geo(lab)})')
    m = row_machine(albums=3)
    item = m.new_widget('list_item', 0, 0, 0, 310, 64)
    m.call(ROW_BUILDERS['playlist_listitem_layout'], a0=item, a1=0, count=600000)
    m.layout(item)
    lab = [c for c in m.kids(item) if m.wtype[c] == 'hscroll_label'][0]
    arrow = m.kids(item)[-1]
    expect(m.geo(lab)[0] == 60 and m.geo(lab)[2] == 217 and m.geo(arrow)[0] == 285 and m.geo(arrow)[3] == 60,
           f'Playlists: name x 60 w 217, the arrow at 285 ({m.geo(lab)}, {m.geo(arrow)})')

    # 42. Search albums: the M1-only search row builder, its own call retargeted too.
    m = row_machine()
    item = m.new_widget('list_item', 0, 0, 0, 310, 64)
    m.call(ROW_BUILDERS['search_albums_row'], a0=item, a1=0, count=600000)
    m.layout(item)
    cover, text = m.kids(item)[0], m.kids(item)[1]
    expect(m.geo(cover) == (4, 0, 52, 60) and m.geo(text)[0] == 60 and m.geo(text)[2] == 238 and
           [m.geo(c)[1:] for c in m.kids(text)[:2]] == [(7, 238, 24), (33, 238, 20)],
           f'Search albums: cover at 4, text x 60 w 238 (no chevron), title 7 / artist 33 ({m.geo(cover)}, {m.geo(text)})')

    # 43. Fallbacks: the stock layout always runs; anything unexpected is left to it alone.
    m = row_machine()
    table = m.new_widget('table_client', 0, 0, 0, 310, 400)
    m.present.add('/mnt/mmc/m1pod-off')
    m.call(ROW_BUILDERS['music_create_tablerow'], a0=table, count=400000)
    btn = m.kids(m.kids(table)[0])[0]
    expect(m.word(m.word(btn + O['W_CHILDREN_LAYOUT']) + O['LAYOUT_VTABLE']) == O['DEFAULT_LAYOUT_VTABLE'],
           'kill switch: the row keeps the stock layouter (stock widths)')
    m = row_machine(); m.layout_ret = 0x10
    table = m.new_widget('table_client', 0, 0, 0, 310, 400)
    m.call(ROW_BUILDERS['music_create_tablerow'], a0=table, count=400000)
    btn = m.kids(m.kids(table)[0])[0]
    expect(m.word(btn + O['W_CHILDREN_LAYOUT']) == 0, 'a failed widget_set_children_layout: nothing installed')
    m = RowMachine()
    v = m.call(PSYMS['compact_set_row_layout'], a0=0, a1=m.cstr('default(r=1,c=0,x=12,s=8)'))
    expect(v == 0x10, 'a null row: the stock error, nothing else')
    m = RowMachine(); m.layout_vt = 0x00904000   # e.g. a list / grid layouter: another vtable
    r = m.new_widget('button', 0, 0, 0, 310, 60)
    m.call(PSYMS['compact_set_row_layout'], a0=r, a1=m.cstr('default(r=1,c=0,x=12,s=8)'))
    expect(m.word(m.word(r + O['W_CHILDREN_LAYOUT']) + O['LAYOUT_VTABLE']) == 0x00904000,
           'a layouter that is not the stock default one is left alone')
    m = RowMachine()
    expect(m.call(PSYMS['compact_row_layout'], a0=0, a1=0) == 0x10 and m.stock_layouts == 0,
           'a null layouter or row: straight to the stock layout (its own error)')
    lay = m.alloc(0x20); m.u.mem_write(lay, bytes(0x20)); m.u.mem_write(lay + 0x14, bytes([12, 0, 8]))
    r = m.new_widget('button', 0, 0, 0, 310, 60)
    img = m.new_widget('image', r, 0, 0, 40, 60); lbl = m.new_widget('label', r, 0, 0, 200, 60)
    m.resizes = []
    m.call(PSYMS['compact_row_layout'], a0=lay, a1=r, count=200000)
    expect(m.stock_layouts == 1 and not m.resizes and not m.focus,
           'a row without an hscroll_label: the stock layout alone, nothing resized')
    m.stock_layouts = 0
    lbl2 = m.new_widget('hscroll_label', r, 0, 0, 100, 60); m.set_visible(lbl2, 0)
    m.call(PSYMS['compact_row_layout'], a0=lay, a1=r, count=200000)
    expect(m.stock_layouts == 1 and not m.resizes, 'a hidden title: nothing resized, the stock layout runs')
    big = m.new_widget('button', 0, 0, 0, 310, 60)
    for k in range(O['ROW_MAX_CHILDREN'] + 1): m.new_widget('hscroll_label', big, 0, 0, 10, 60)
    m.stock_layouts = 0
    m.call(PSYMS['compact_row_layout'], a0=lay, a1=big, count=400000)
    expect(m.stock_layouts == 1 and not m.resizes, f'more than {O["ROW_MAX_CHILDREN"]} children: the stock layout alone')
    tiny = m.new_widget('button', 0, 0, 0, 30, 60)
    t1 = m.new_widget('image', tiny, 0, 0, 40, 60); t2 = m.new_widget('hscroll_label', tiny, 0, 0, 100, 60)
    m.call(PSYMS['compact_row_layout'], a0=lay, a1=tiny, count=200000)
    expect(m.geo(t2)[2] == 0, 'a row too narrow for its text: width 0, not negative')


def run(ctx):
    rows_tests(ctx.expect)
