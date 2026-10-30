#!/usr/bin/env python3
"""Run demo's own AWTK drawing code under Unicorn on a bgr565 framebuffer (docs/ui.md).

Answers three questions about this AWTK build with its real code, not with assumptions:
  1. canvas_fill_rect with a colour whose alpha is 0xA6 blends it over what is already there
     (a view's bg_color "#RRGGBBAA" with round_radius 0 is drawn this way: widget_fill_rect);
  2. canvas_fill_rounded_rect_ex (the round_radius path of widget_fill_rect, the same 0x64d028 code
     canvas_fill_rounded_rect_gradient_ex runs) does too: every pixel a pixel inside the rounded
     edge is the blend, every pixel a pixel outside is untouched, no seams where the corner spans
     meet the body; the edge pixels lie between the two (anti-aliased);
  3. canvas_draw_image_ex with draw_type scale_auto scales by nearest neighbour (a 1 px black /
     white column pattern drawn 280 -> 216 has only black and white pixels), so a cover drawn at
     another size than it was written at is resampled without filtering;
  and, for the iPod page's cover pane (docs/modules/ipod.md): canvas_draw_image of a source window into a destination of the same size copies
  it pixel for pixel (no resampling), at any offset.

libc and libm are mocked (malloc, memset, memcpy, sqrtf, sinf, operator new ...); system_info()
gets a zeroed block; the lcd is lcd_mem_bgr565_create_single_fb (the device's pixel format).
Usage: venv/bin/python -I test/awtk_fill.py WORKDIR [OUT.png]     (any tree: stock or modded demo)
"""
import math, os, struct, sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_MIPS, UC_MODE_MIPS32, UC_MODE_LITTLE_ENDIAN, UC_HOOK_CODE
from unicorn.mips_const import (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3, UC_MIPS_REG_V0,
                                UC_MIPS_REG_SP, UC_MIPS_REG_RA, UC_MIPS_REG_T9, UC_MIPS_REG_F0, UC_MIPS_REG_F12,
                                UC_MIPS_REG_CP0_STATUS)

DEMO = os.path.join(sys.argv[1], 'rootfs', 'release', 'bin', 'demo')
SYSTEM_INFO_PTR = 0xa0bec0          # system_info() returns *(0xa10000 - 0x4140) (0x65adf8)
TRAP, HEAP, STACK, RET = 0x0f000000, 0x40000000, 0x7ff00000, 0x00ff0000
W, H = 320, 200
CARD = (0x00, 0x00, 0x00, 0xA6)     # the card colour of --layout card


class Demo:
    def __init__(self, path):
        data = open(path, 'rb').read(); elf = ELFFile(open(path, 'rb'))
        u = self.u = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
        u.reg_write(UC_MIPS_REG_CP0_STATUS, u.reg_read(UC_MIPS_REG_CP0_STATUS) | 0x24000000)   # CU1, FR (-mfp64)
        for seg in elf.iter_segments():
            if seg['p_type'] != 'PT_LOAD': continue
            v, f, m, o = seg['p_vaddr'], seg['p_filesz'], seg['p_memsz'], seg['p_offset']
            u.mem_map(v & ~0xfff, ((v + m + 0xfff) & ~0xfff) - (v & ~0xfff)); u.mem_write(v, data[o:o + f])
        self.syms = {}
        for name in ('.dynsym', '.symtab'):
            sec = elf.get_section_by_name(name)
            for s in (sec.iter_symbols() if sec else ()):
                if s['st_value'] and s.name: self.syms.setdefault(s.name, s['st_value'])
        # every undefined dynamic symbol's GOT slot -> a trap stub (jr ra; nop), handled in _hook
        dyn = elf.get_section_by_name('.dynamic'); got = elf.get_section_by_name('.got'); dynsym = elf.get_section_by_name('.dynsym')
        tags = {t.entry.d_tag: t.entry.d_val for t in dyn.iter_tags()}
        local, gotsym = tags['DT_MIPS_LOCAL_GOTNO'], tags['DT_MIPS_GOTSYM']
        u.mem_map(TRAP, 0x100000); self.traps = {}
        for i in range(gotsym, dynsym.num_symbols()):
            s = dynsym.get_symbol(i)
            if s['st_shndx'] == 'SHN_UNDEF':
                a = TRAP + 8 * len(self.traps); self.traps[a] = s.name
                u.mem_write(a, struct.pack('<II', 0x03e00008, 0)); u.mem_write(got['sh_addr'] + 4 * (local + i - gotsym), struct.pack('<I', a))
        u.mem_map(HEAP, 0x4000000); self.heap = HEAP
        u.mem_map(STACK - 0x100000, 0x200000); u.mem_map(RET & ~0xfff, 0x1000)
        self.unknown = set()
        u.hook_add(UC_HOOK_CODE, self._hook, begin=TRAP, end=TRAP + 0x100000)
        si = self.malloc(0x200); u.mem_write(si, bytes(0x200)); u.mem_write(SYSTEM_INFO_PTR, struct.pack('<I', si))

    def malloc(self, n):
        a = self.heap; self.heap = (self.heap + n + 15) & ~15; return a

    def _hook(self, u, addr, size, _):
        name = self.traps.get(addr)
        if not name: return
        a0, a1, a2 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2))
        ret = 0
        if name in ('malloc', '_Znwj', '_Znaj'): ret = self.malloc(a0)
        elif name == 'calloc': ret = self.malloc(a0 * a1); u.mem_write(ret, bytes(a0 * a1))
        elif name in ('free', '_ZdlPv', '_ZdaPv', 'printf', 'puts', 'fflush'): pass
        elif name == 'memset': u.mem_write(a0, bytes([a1 & 0xff]) * a2); ret = a0
        elif name in ('memcpy', 'memmove'): u.mem_write(a0, bytes(u.mem_read(a1, a2))); ret = a0
        elif name in ('sqrtf', 'sinf', 'cosf'):            # o32 hard float: $f12 -> $f0 (single)
            x = struct.unpack('<f', struct.pack('<I', u.reg_read(UC_MIPS_REG_F12) & 0xffffffff))[0]
            y = {'sqrtf': math.sqrt, 'sinf': math.sin, 'cosf': math.cos}[name](x)
            u.reg_write(UC_MIPS_REG_F0, struct.unpack('<I', struct.pack('<f', y))[0])
        else: self.unknown.add(name)
        u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff)

    def call(self, fn, *args):
        u, addr, sp = self.u, self.syms[fn], STACK - 0x1000
        for i, a in enumerate(args[4:]): u.mem_write(sp + 16 + 4 * i, struct.pack('<I', a & 0xffffffff))
        for r, a in zip((UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3), args): u.reg_write(r, a & 0xffffffff)
        u.reg_write(UC_MIPS_REG_SP, sp); u.reg_write(UC_MIPS_REG_RA, RET); u.reg_write(UC_MIPS_REG_T9, addr)
        u.emu_start(addr, RET, count=100_000_000)
        assert not self.unknown, f'{fn}: unmocked libc {sorted(self.unknown)}'
        return u.reg_read(UC_MIPS_REG_V0)

    def rect(self, x, y, w, h):
        a = self.malloc(16); self.u.mem_write(a, struct.pack('<iiii', x, y, w, h)); return a


def bgr565(rgb): r, g, b = rgb; return ((b >> 3) << 11) | ((g >> 2) << 5) | (r >> 3)
def rgb565(p): return ((p & 31) << 3, ((p >> 5) & 63) << 2, (p >> 11) << 3)
def wallpaper(x, y): return ((40 + x) % 256, (60 + 2 * y) % 256, (230 - x // 2) % 256)
def color_t(r, g, b, a): return r | g << 8 | b << 16 | a << 24


class Screen:
    def __init__(self, d):
        self.d = d; self.fb = d.malloc(W * H * 2)
        self.lcd = d.call('lcd_mem_bgr565_create_single_fb', W, H, self.fb)
        self.canvas = d.malloc(0x400); d.u.mem_write(self.canvas, bytes(0x400))
        fm = d.malloc(0x100); d.u.mem_write(fm, bytes(0x100))
        d.call('canvas_init', self.canvas, self.lcd, fm)
        d.call('canvas_set_clip_rect', self.canvas, d.rect(0, 0, W, H))
    def wall(self):
        self.d.u.mem_write(self.fb, b''.join(struct.pack('<H', bgr565(wallpaper(x, y))) for y in range(H) for x in range(W)))
    def read(self):
        raw = bytes(self.d.u.mem_read(self.fb, W * H * 2))
        return [[rgb565(struct.unpack_from('<H', raw, 2 * (y * W + x))[0]) for x in range(W)] for y in range(H)]


def inside_dist(x, y, rx, ry, rw, rh, rad):
    """Signed distance of pixel centre (x+.5, y+.5) to a rounded rect's edge, positive inside."""
    px, py = x + .5, y + .5
    cx = min(max(px, rx + rad), rx + rw - rad); cy = min(max(py, ry + rad), ry + rh - rad)
    if (cx, cy) == (px, py): return min(px - rx, rx + rw - px, py - ry, ry + rh - py)
    return rad - math.hypot(px - cx, py - cy)


TOL = 12      # one 565 step (8 / 4 / 8) plus demo's truncating blend (>> 8) and pixel truncation

def check_fill(px, rect, rad, col, label):
    rx, ry, rw, rh = rect; a = col[3]; worst = 0; bad = []
    for y in range(H):
        for x in range(W):
            wq = rgb565(bgr565(wallpaper(x, y)))
            blend = tuple((c * a + w * (255 - a)) / 255 for c, w in zip(col[:3], wq))
            d = inside_dist(x, y, rx, ry, rw, rh, rad) if rad else \
                (1 if rx <= x < rx + rw and ry <= y < ry + rh else -1)
            got = px[y][x]
            if d >= 1:
                err = max(abs(g - b) for g, b in zip(got, blend)); worst = max(worst, err)
                if err > TOL: bad.append(('inside', x, y, got, blend))
            elif d <= -1:
                if got != wq: bad.append(('outside', x, y, got, wq))
            elif not all(min(b, w) - TOL <= g <= max(b, w) + TOL for g, b, w in zip(got, blend, wq)):
                bad.append(('edge', x, y, got, blend, wq))
    print(f'  {label}: inside = the blend within {worst:.1f} (one 565 step + truncation: {TOL}), outside untouched, '
          f'edge between: {"ok" if not bad else "FAIL " + str(bad[:4])}')
    return not bad


def main():
    d = Demo(DEMO); s = Screen(d); ok = True; shots = []
    print(f'demo {DEMO}: drawing with its canvas_fill_rect / canvas_fill_rounded_rect_ex / canvas_draw_image_ex')
    col = color_t(*CARD); cptr = d.malloc(4); d.u.mem_write(cptr, struct.pack('<I', col))
    for label, rad in (('canvas_fill_rect, #000000A6', 0), ('canvas_fill_rounded_rect_ex, #000000A6, radius 18', 18)):
        s.wall(); d.call('canvas_set_fill_color', s.canvas, col)
        rect = (16, 20, 288, 160)
        if rad: d.call('canvas_fill_rounded_rect_ex', s.canvas, d.rect(*rect), d.rect(*rect), cptr, rad, rad, rad, rad)
        else: d.call('canvas_fill_rect', s.canvas, *rect)
        px = s.read(); shots.append(px); ok &= check_fill(px, rect, rad, CARD, label)
    # 3. scale_auto: 280 x 280 of 1 px black / white columns into 216 x 216
    s.wall(); src, dst = 280, 216
    bmp = d.call('bitmap_create_ex', src, src, 0, 1)                  # BITMAP_FMT_RGBA8888
    buf = d.call('bitmap_lock_buffer_for_write', bmp)
    d.u.mem_write(buf, (bytes((255, 255, 255, 255, 0, 0, 0, 255)) * (src // 2)) * src)
    d.call('bitmap_unlock_buffer', bmp)
    d.call('canvas_draw_image_ex', s.canvas, bmp, 4, d.rect(0, 0, dst, dst))   # IMAGE_DRAW_SCALE_AUTO
    px = s.read(); vals = {px[y][x] for y in range(min(dst, H)) for x in range(dst)}
    nn = vals <= {(0, 0, 0), (248, 252, 248)}
    print(f'  canvas_draw_image_ex scale_auto {src} -> {dst}: {len(vals)} distinct colours {sorted(vals)[:4]} -> '
          f'{"nearest neighbour (no filtering)" if nn else "filtered"}')
    ok &= nn
    # 4. a 1 px border line (the row separator of a list_item style: canvas_draw_hline / canvas_draw_vline with the style's
    #    border_color as the stroke colour) with an alpha blends it over what is there, like a fill (docs/modules/album-page.md)
    s.wall(); line = color_t(255, 255, 255, 0x14)
    d.call('canvas_set_stroke_color', s.canvas, line); d.call('canvas_draw_hline', s.canvas, 20, 50, 200)
    d.call('canvas_draw_vline', s.canvas, 300, 20, 100)
    px = s.read(); bad = []
    for label, pts in (('hline', [(x, 50) for x in (20, 100, 219)]), ('vline', [(300, y) for y in (20, 60, 119)])):
        for x, y in pts:
            wq = rgb565(bgr565(wallpaper(x, y))); want = tuple((255 * 0x14 + w * (255 - 0x14)) / 255 for w in wq)
            if max(abs(g - b) for g, b in zip(px[y][x], want)) > TOL or px[y][x] == wq: bad.append((label, x, y, px[y][x], want))
    out_ok = all(px[y][x] == rgb565(bgr565(wallpaper(x, y))) for x, y in ((19, 50), (220, 50), (100, 49), (100, 51), (300, 19), (300, 120), (299, 60)))
    print(f'  canvas_draw_hline / canvas_draw_vline, stroke #FFFFFF14: the blend on the line, nothing beside it: {"ok" if not bad and out_ok else "FAIL " + str(bad[:3])}')
    ok &= not bad and out_ok
    # 5. the glass pill image (mb_glass.png, an RGBA bitmap with a translucent fill and an anti-aliased edge) drawn with canvas_draw_image_ex over the
    #    wallpaper: every pixel is the straight-alpha blend of the image over the 565 pixel under it (a fully transparent one leaves it)
    from PIL import Image
    gimg = Image.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'icons', 'png', 'mb_glass.png')).convert('RGBA')
    gw, gh = gimg.size; s.wall()
    bmp = d.call('bitmap_create_ex', gw, gh, 0, 1)
    buf = d.call('bitmap_lock_buffer_for_write', bmp)
    d.u.mem_write(buf, gimg.tobytes()); d.call('bitmap_unlock_buffer', bmp)
    gx, gy = 8, 20
    d.call('canvas_draw_image_ex', s.canvas, bmp, 0, d.rect(gx, gy, gw, gh))     # IMAGE_DRAW_DEFAULT: 1:1
    px = s.read(); worst = 0; bad = []; blended = 0
    for y in range(gh):
        for x in range(gw):
            r, g, b, a = gimg.getpixel((x, y)); wq = rgb565(bgr565(wallpaper(gx + x, gy + y))); got = px[gy + y][gx + x]
            want = tuple((c * a + w * (255 - a)) / 255 for c, w in zip((r, g, b), wq))
            err = max(abs(gc - wc) for gc, wc in zip(got, want)); worst = max(worst, err)
            blended += 0 < a < 255 and got != wq
            if err > TOL + 4: bad.append((x, y, a, got, want))
    outside = all(px[gy - 1][gx + x] == rgb565(bgr565(wallpaper(gx + x, gy - 1))) and px[gy + gh][gx + x] == rgb565(bgr565(wallpaper(gx + x, gy + gh))) for x in range(0, gw, 7))
    print(f'  canvas_draw_image_ex of mb_glass.png {gw}x{gh} over the wallpaper: every pixel the alpha blend within {worst:.1f} '
          f'({blended} translucent pixels blended), nothing outside: {"ok" if not bad and outside and blended > 5000 else "FAIL " + str(bad[:3])}')
    ok &= not bad and outside and blended > 5000
    shots.append(px)
    # 6. the iPod page's cover pane (patch/ipod.c, docs/modules/ipod.md "The cover pane"): canvas_draw_image of a SOURCE WINDOW of a bitmap into a destination of the
    #    same size is a copy (every pixel the source's, no resampling), whatever the window's offset: the pan moves the window a whole pixel at a time and nothing shimmers
    s.wall(); sz = 238
    bmp = d.call('bitmap_create_ex', sz, sz, 0, 1)
    buf = d.call('bitmap_lock_buffer_for_write', bmp)
    pat = lambda x, y: ((x * 8) & 0xf8, (y * 4) & 0xfc, ((x + y) * 8) & 0xf8)      # (r, g, b), exact in bgr565
    d.u.mem_write(buf, b''.join(bytes((b, g, r, 255)) for y in range(sz) for x in range(sz) for r, g, b in (pat(x, y),)))
    d.call('bitmap_unlock_buffer', bmp)
    ww, wh, dx, dy = 139, 180, 10, 10
    ok6 = True
    for sx, sy in ((43, 7), (44, 7), (60, 22)):
        s.wall()
        d.call('canvas_draw_image', s.canvas, bmp, d.rect(sx, sy, ww, wh), d.rect(dx, dy, ww, wh))
        px = s.read()
        same = all(px[dy + y][dx + x] == pat(sx + x, sy + y) for y in range(0, wh, 3) for x in range(ww))
        out = px[dy - 1][dx + 5] == rgb565(bgr565(wallpaper(dx + 5, dy - 1))) and px[dy + 5][dx + ww] == rgb565(bgr565(wallpaper(dx + ww, dy + 5)))
        ok6 &= same and out
    print(f'  canvas_draw_image of a {ww}x{wh} source window at offsets (43, 7), (44, 7), (60, 22) into {ww}x{wh}: every pixel the source\'s, nothing outside: '
          f'{"ok" if ok6 else "FAIL"}')
    ok &= ok6
    shots.append(px)
    if len(sys.argv) > 2:
        from PIL import Image
        out = Image.new('RGB', (W, len(shots) * (H + 4)), (40, 40, 40))
        for i, p in enumerate(shots):
            im = Image.new('RGB', (W, H)); im.putdata([c for row in p for c in row]); out.paste(im, (0, i * (H + 4)))
        out.save(sys.argv[2]); print('wrote', sys.argv[2])
    print('awtk_fill:', 'ok' if ok else 'FAILED')
    sys.exit(0 if ok else 1)


if __name__ == '__main__': main()
