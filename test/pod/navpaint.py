"""Glass capsule joins under stock AWTK child culling and clipped icon painting."""
from harness import *   # noqa: F401,F403
from PIL import Image
from unicorn.mips_const import UC_MIPS_REG_V1


def run(ctx):
    # Reuse the framebuffer harness; its main() does not run when imported.
    spec = importlib.util.spec_from_file_location('awtk_fill', os.path.join(ROOT, 'test/awtk_fill.py'))
    renderer = importlib.util.module_from_spec(spec); spec.loader.exec_module(renderer)
    class PaintDemo(renderer.Demo):
        def cstr(self, a):
            b = bytearray()
            while self.u.mem_read(a + len(b), 1)[0]: b += self.u.mem_read(a + len(b), 1)
            return bytes(b)

        def _hook(self, u, addr, size, data):
            name = self.traps.get(addr)
            if name == 'strcmp':
                a, b = (self.cstr(u.reg_read(r)) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1))
                u.reg_write(UC_MIPS_REG_V0, ((a > b) - (a < b)) & 0xffffffff)
            elif name == 'clock_gettime':
                u.mem_write(u.reg_read(UC_MIPS_REG_A1), bytes(8)); u.reg_write(UC_MIPS_REG_V0, 0)
            elif name == '__udivdi3':
                a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
                q = (a0 | a1 << 32) // (a2 | a3 << 32)
                u.reg_write(UC_MIPS_REG_V0, q & 0xffffffff); u.reg_write(UC_MIPS_REG_V1, q >> 32)
            else: super()._hook(u, addr, size, data)

    d = PaintDemo(DEMO)
    screen = renderer.Screen(d)
    canvas, width, height = screen.canvas, renderer.W, renderer.H
    raw = os.path.join(WORK, 'rootfs/release/assets/default/raw/ui')
    tree = awtk_ui.parse(open(os.path.join(raw, 'm1plus_albums.bin'), 'rb').read())
    nav = next(c for c in tree.children if c.name == 'navigationbar_view')
    buttons = [c for c in nav.children if c.name in ('btn_coverflow', 'btn_albumview', 'btn_backtoplayer')]
    ctx.expect(pod_ui.NAV_ICON_OVERFLOW == 7, 'navbar icons extend 7 px beyond their 46 px touch slots')
    # Hidden controls can be shown/moved later (Songs, Cover Flow and Podcasts).
    bad = []
    for page in pod_pages.PAGES:
        root = awtk_ui.parse(open(os.path.join(raw, page.key + '.bin'), 'rb').read())
        for w in root.walk():
            if w.type == 'button' and w.h == 50 and w.w == 46 and w.get('style') == 'img_btn_style':
                if w.get('dirty_rect_tolerance') != '7': bad.append((page.key, w.name))
    ctx.expect(not bad, f'every shifted navbar icon, including hidden and album-page buttons, declares its paint overflow: {bad}')

    def alloc(n):
        a = d.malloc(n); d.u.mem_write(a, bytes(n)); return a
    def word(a, v): d.u.mem_write(a, struct.pack('<I', v))
    def bitmap(im):
        b = d.call('bitmap_create_ex', im.width, im.height, 0, 1)
        buf = d.call('bitmap_lock_buffer_for_write', b)
        d.u.mem_write(buf, im.tobytes()); d.call('bitmap_unlock_buffer', b)
        return b
    vt, parent = alloc(0x80), alloc(0x80)
    prop = alloc(32); d.u.mem_write(prop, b'dirty_rect_tolerance\0')
    children, tolerances = [], []
    for b in buttons:
        a = alloc(0x80)
        for off, val in ((0, b.x), (4, b.y), (8, b.w), (12, b.h), (0x24, 4), (0x70, vt)):
            word(a + off, val)
        declared = int(b.get('dirty_rect_tolerance') or '0')
        ret = d.call('widget_set_prop_int', a, prop, declared)
        stored, = struct.unpack('<H', d.u.mem_read(a + 0x36, 2))
        ctx.expect(ret == 0 and stored == declared,
                   f'{b.name}: stock setter recognizes dirty_rect_tolerance and stores {declared} at widget +0x36')
        children.append(a)
        tolerances.append(stored)
    elms, arr = alloc(4 * len(children)), alloc(12)
    for i, a in enumerate(children): word(elms + 4 * i, a)
    for off, val in ((0, len(children)), (4, len(children)), (8, elms)): word(arr + off, val)
    word(parent + 0x58, arr)
    selected = []
    def select(u, addr, size, data):
        # Let the real parent choose children; draw those icons below with the real canvas.
        selected.append(u.reg_read(UC_MIPS_REG_A0))
        u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
    hook = d.u.hook_add(UC_HOOK_CODE, select, begin=d.syms['widget_paint'], end=d.syms['widget_paint'])
    out = os.path.join(ROOT, 'out/preview'); os.makedirs(out, exist_ok=True)
    try:
        for mode in ('list', 'grid'):
            for pressed in (False, True):
                pane = Image.new('RGBA', (width, 50))
                pieces = []
                for b in buttons:
                    name = f'pod_nav_{mode}' if b.name == 'btn_albumview' else b.get('style:normal:icon')
                    if pressed and b.name == 'btn_albumview': name += '_down'
                    im = asset_image(name)
                    pane.alpha_composite(im, (b.x + (b.w - im.width) // 2, b.y + (b.h - im.height) // 2))
                    pieces.append(bitmap(im))
                d.call('canvas_set_clip_rect', canvas, d.rect(0, 0, width, height))
                d.u.mem_write(screen.fb, bytes(width * height * 2))
                d.call('canvas_draw_icon_in_rect', canvas, bitmap(pane), d.rect(0, 0, width, 50))
                reference = bytes(d.u.mem_read(screen.fb, width * height * 2))
                for tolerance in (0, 7):
                    for a, declared in zip(children, tolerances):
                        d.u.mem_write(a + 0x36, struct.pack('<H', declared if tolerance else 0))
                    # Narrow repaint strips at each join: top through one third of the pill.
                    # The old culling drops the left image, whose seven-pixel overhang supplies them.
                    d.u.mem_write(screen.fb, reference)
                    for edge in (214, 260):
                        for x in range(edge + 1, edge + 7):
                            for y in range(4, 18): d.u.mem_write(screen.fb + 2 * (y * width + x), b'\0\0')
                            d.call('canvas_set_clip_rect', canvas, d.rect(x, 4, 1, 14))
                            selected.clear()
                            d.call('widget_on_paint_children_default', parent, canvas)
                            for a, b, bmp in zip(children, buttons, pieces):
                                if a in selected:
                                    d.call('canvas_draw_icon_in_rect', canvas, bmp, d.rect(b.x, b.y, b.w, b.h))
                    got = bytes(d.u.mem_read(screen.fb, width * height * 2))
                    ctx.expect((got == reference) == bool(tolerance),
                               f'Albums {mode}, {"pressed" if pressed else "rest"}: clipped stock painting {"preserves both joins" if tolerance else "reproduces black seams without overflow tolerance"}')
                    if mode == 'list' and not pressed:
                        im = Image.new('RGB', (width, height)); im.putdata([c for row in screen.read() for c in row])
                        im.crop((168, 0, 320, 50)).save(os.path.join(out, f'albums-navbar-{"after" if tolerance else "before"}.png'))
    finally:
        d.u.hook_del(hook)
