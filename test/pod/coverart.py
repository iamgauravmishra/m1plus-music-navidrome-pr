"""Album cover extraction with our own resize (patch/covercache.c art_embedded / art_folder, patch/pccover.c pv_cover; docs/modules/coverflow.md "Cover resampling"): the cache worker takes the
embedded picture (taglib_album_picture, as stock's toolsGetAlbumCover does) or the folder image (stock's choice, reproduced), decodes it at libjpeg's DCT scale (or through the streaming PNG
decoder) and writes the output size stock's resize would, by an exact area average. The compiled payload runs under Unicorn; libjpeg is the PIL mock of test/pod/pcnet.py, which decodes at the
scale it is asked and records it. Every failure must hand the same album to the stock call."""
import importlib.util, io, os, struct, sys, zlib
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

HERE = os.path.dirname(os.path.abspath(__file__))


def sibling(name):
    mod = sys.modules.get(f'podtest_{name}')
    if mod is None:
        spec = importlib.util.spec_from_file_location(f'podtest_{name}', os.path.join(HERE, name + '.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f'podtest_{name}'] = mod
        spec.loader.exec_module(mod)
    return mod


PCN = sibling('pcnet')
ART = O['ART_SIZE']
TMP = '/tmp/.tmp_picture'
DIR = '/mnt/mmc/Music/Album'
TRACK = f'{DIR}/song.flac'
KEY = 0x1234abcd


class CM(PCN.NM):
    """The card machine with what the extraction reads that the podcast one does not mock: d_type in readdir (files 8, folders 4) and ftell over the file's bytes."""
    def _hook(self, u, address, size, _):
        name = self.handlers.get(address, '')
        a0 = u.reg_read(UC_MIPS_REG_A0)
        ret = None
        if name == 'readdir' and a0 in self.dh:
            d = self.dh[a0]
            if d[1] < len(d[0]):
                nm = d[0][d[1]]; d[1] += 1
                files = {p.rsplit('/', 1)[1] for p in self.fs}
                self.u.mem_write(self.dent, bytes(300)); self.u.mem_write(self.dent + 10, bytes([8 if nm in files else 4]) + nm.encode('latin-1') + b'\0'); ret = self.dent
            else: ret = 0
        elif name == 'ftell' and a0 in self.fp:
            ret = self.fp[a0][1]
        elif name == 'fopen' and 'w' in self.read_cstr(u.reg_read(UC_MIPS_REG_A1)) and self.read_cstr(a0).startswith('/tmp/'):   # the pane's file in RAM, written like the card's
            path = self.read_cstr(a0); self.calls.append(('fopen', path, 'wb')); self.fs[path] = b''; ret = self.alloc(4); self.fp[ret] = [path, 0]
        if ret is not None:
            u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff); u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))
            return
        return super()._hook(u, address, size, _)


def machine():
    m = CM()
    m.dirs.update({'/mnt/mmc/.m1plus', '/tmp'})
    m.folder(DIR)
    m.put(TRACK, b'x')
    return m


def f32(v): return struct.unpack('<f', struct.pack('<f', v))[0]


def fit(w, h, t):
    """Stock's fit (0x5e00bc) in single precision: None when the picture is kept as it is."""
    if w >= h:
        if t < w: return t, max(1, int(f32(h / f32(f32(w) / f32(t)))))
        return (t, t) if w == t else None
    if t < h: return max(1, int(f32(w / f32(f32(h) / f32(t))))), t
    return (t, t) if h == t else None


def picture(w, h, mode='RGB', fmt='JPEG', **kw):
    """A test picture with bands, a chequer and a ring (mid frequencies: the JPEG round trip and PIL's box resize stay close to an exact area average)."""
    from PIL import Image, ImageDraw
    im = Image.new('RGB', (w, h))
    dr = ImageDraw.Draw(im)
    for x in range(0, w, 40): dr.rectangle([x, 0, x + 19, h], fill=(x * 255 // w, 255 - x * 255 // w, 128))
    for y in range(0, h, 30):
        for x in range(0, w, 30):
            if (x // 30 + y // 30) % 2: dr.rectangle([x, y, x + 14, y + 14], fill=(250, 250, 40))
    dr.ellipse([w // 4, h // 4, w * 3 // 4, h * 3 // 4], outline=(0, 0, 0), width=max(6, w // 40))
    b = io.BytesIO()
    im.convert(mode).save(b, fmt, **kw)
    return b.getvalue(), decoded(b.getvalue()).convert('RGB')   # (the reference is what the file holds, not the picture before its lossy save)


def build(m, track=TRACK, key=KEY):
    """The cache worker on one job, as the shared builder runs it; the cache file's bytes or None."""
    m.thread = None
    assert m.call(PSYMS['cc_build_open'], a0=4, a1=0, count=1 << 40) == 1
    assert m.call(PSYMS['cc_build_add'], a0=m.cstr(track), a1=key, count=1 << 40) == 1
    assert m.call(PSYMS['cc_build_start'], count=1 << 40) == 1
    try:
        m.call(m.thread[0], a0=m.thread[1], count=1 << 40)
    except Exception:
        print('PC', hex(m.u.reg_read(UC_MIPS_REG_PC)), 'RA', hex(m.u.reg_read(UC_MIPS_REG_RA)), sorted((v, k) for k, v in PSYMS.items() if v <= m.u.reg_read(UC_MIPS_REG_RA))[-2:]); raise
    calls = m.calls   # (every call() starts the log again: the worker's is the one that counts)
    m.call(PSYMS['cc_build_stop'], count=1 << 40)
    m.calls = calls
    return m.fs.get(art_file(key))


def decoded(data):
    from PIL import Image
    im = Image.open(io.BytesIO(data)); im.load()
    return im


def close_to(got, ref_im, tol=3.0):
    """The cover against PIL's box resize of the original to the same size: the mean absolute difference."""
    from PIL import ImageChops
    from PIL import Image
    ref = ref_im.resize(got.size, Image.BOX)
    small = (max(1, got.size[0] // 6), max(1, got.size[1] // 6))   # compared after a 6 : 1 reduction: hard edges move by a pixel with the DCT scale and the JPEG round trip, tones do not
    got, ref = got.convert('RGB').resize(small, Image.BOX), ref.resize(small, Image.BOX)
    px = [v for p in ImageChops.difference(got.convert('RGB'), ref).getdata() for v in p]
    return sum(px) / len(px) <= tol, f'mean {sum(px) / len(px):.2f}'


def stock_calls(m): return [c[0] for c in m.calls if c[0] in ('toolsGetAlbumCover', 'toolsGetExternCover')]


def run(ctx):
    expect = ctx.expect
    lock = pod.DATA['PARSE_COVER_MUTEX'][0]

    # 1. An embedded JPEG: taglib asked as stock asks it, the picture read from /tmp/.tmp_picture (and removed), decoded at the smallest DCT scale that keeps both sides, written at stock's size
    #    and quality under parse_cover_mutex; no stock art call; the file named for the new sampling (r), the old name never written.
    data, im = picture(1500, 1000)
    m = machine(); m.taglib_kind, m.taglib_data = 2, data
    out = build(m)
    expect(out is not None and decoded(out).size == fit(750, 500, ART) == (ART, 112), f'a 1500 x 1000 cover is written at stock\'s size (168 x 112): {decoded(out).size if out else None}')
    expect(('scale', 8, (188, 125)) in m.jlog and ('encoded', (ART, 112), 90) in m.jlog, f'decoded at 1/8 (188 x 125 still has both sides), encoded at quality 90 ({[e for e in m.jlog if isinstance(e, tuple)]})')
    expect(('taglib_album_picture', TRACK, art_file(KEY) + '.tmp', 0x100000, 0x600000) in m.calls, 'taglib_album_picture is called as toolsGetAlbumCover calls it')
    expect(not stock_calls(m), 'no stock art call when ours succeeds')
    seq = [c[0] for c in m.calls if c[0] in ('lock', 'taglib_album_picture', 'unlink', 'rename', 'unlock')]
    expect(seq[:4] == ['lock', 'taglib_album_picture', 'unlink', 'unlock'] and ('lock', lock) in m.calls and seq[-1] == 'rename',
           f'taglib, the decode and the removal of /tmp/.tmp_picture all happen under parse_cover_mutex ({seq})')
    expect(TMP not in m.fs and art_file(KEY) in m.fs and art_file(KEY).replace('/r', '/') not in m.fs, 'the temporary picture is gone; the file has the r name, the old name is not written')
    ok, why = close_to(decoded(out), im, 6.0)
    expect(ok, f'the cover is the area average of the picture, near PIL\'s box resize ({why})')
    expect(m.jlog.count('create_decompress') == m.jlog.count('destroy_decompress') == 1 and m.jlog.count('create_compress') == m.jlog.count('destroy_compress') == 1, 'every libjpeg object is destroyed')

    # 2. The other shapes: portrait, square (the scale keeps both sides), a gray one (stock always takes its scaled path), a picture over 4096 on a side, progressive.
    for w, h, kw, den, what in ((800, 1200, {}, 4, 'portrait'), (600, 600, {}, 2, 'square 600'), (1024, 1024, {}, 4, '1024 square (stock decodes it whole)'), (3000, 2000, {}, 8, '3000 x 2000'),
                                (1500, 1500, {'progressive': True}, 8, 'progressive')):
        data, im = picture(w, h, **kw)
        m = machine(); m.taglib_kind, m.taglib_data = 2, data
        out = build(m)
        sw, sh = ((w + 1) // 2, (h + 1) // 2) if max(w, h) > 1024 and max(w, h) <= 2048 else (w, h)
        sw, sh = ((w + 3) // 4, (h + 3) // 4) if 2048 < max(w, h) <= 4096 else (sw, sh)
        want = fit(sw, sh, ART)
        expect(out is not None and decoded(out).size == want, f'{what}: written at stock\'s size {want} ({decoded(out).size if out else None})')
        expect([e for e in m.jlog if isinstance(e, tuple) and e[0] == 'scale'][0][1] == den, f'{what}: DCT scale 1/{den} ({[e for e in m.jlog if isinstance(e, tuple) and e[0] == "scale"]})')
        if out: ok, why = close_to(decoded(out), im, 6.0); expect(ok, f'{what}: close to the box resize ({why})')
    data, im = picture(900, 700, mode='L')
    m = machine(); m.taglib_kind, m.taglib_data = 2, data
    out = build(m)
    expect(out is not None and decoded(out).size == fit(450, 350, ART) and decoded(out).mode == 'RGB', f'a gray JPEG: stock\'s size from its 1/2 decode, written as colour ({decoded(out).size if out else None})')

    # 3. Stock's quirk: a picture exactly as wide as the request and shorter is stretched to a square; one smaller than the request is not touched (stock copies it): the stock call runs.
    data, im = picture(ART, 100)
    m = machine(); m.taglib_kind, m.taglib_data = 2, data
    out = build(m)
    expect(out is not None and decoded(out).size == (ART, ART) and not stock_calls(m), 'a picture exactly 168 wide and 100 tall is stretched to 168 x 168, as stock does')
    for w, h in ((150, 150), (100, 167), (167, 100)):
        data, im = picture(w, h)
        m = machine(); m.taglib_kind, m.taglib_data, m.album_cover = 2, data, 1
        build(m)
        expect(stock_calls(m) == ['toolsGetAlbumCover'] and 'create_compress' not in m.jlog, f'a {w} x {h} picture is stock\'s (it keeps it as it is): the stock call, no encoder of ours')

    # 4. PNG: embedded (kind 1), the streaming decoder, the same size rule; an interlaced PNG is stock's
    data, im = picture(420, 300, fmt='PNG')
    m = machine(); m.taglib_kind, m.taglib_data = 1, data
    out = build(m)
    expect(out is not None and decoded(out).size == fit(420, 300, ART) and 'create_decompress' not in m.jlog and not stock_calls(m), f'an embedded PNG is shrunk through the streaming decoder ({decoded(out).size if out else None})')
    if out: ok, why = close_to(decoded(out), im, 6.0); expect(ok, f'the PNG cover is close to the box resize ({why})')
    from PIL import Image
    il = io.BytesIO(); Image.new('RGB', (300, 300), (9, 9, 9)).save(il, 'PNG'); il = bytearray(il.getvalue())
    il[28] = 1   # IHDR interlace method: Adam7 (the data is then not decodable in one pass, whatever it holds; the CRC is not checked first)
    il[29:33] = struct.pack('>I', zlib.crc32(bytes(il[12:29])))
    m = machine(); m.taglib_kind, m.taglib_data, m.album_cover = 1, bytes(il), 1
    build(m)
    expect(stock_calls(m) == ['toolsGetAlbumCover'], 'an interlaced PNG is stock\'s')

    # 5. Every failure is stock's: a truncated JPEG, libjpeg failing at a stage, the output file refused, a picture taglib reports but did not save.
    data, im = picture(1200, 800)
    cases = (('a truncated JPEG', dict(data=data[:6000]), {}), ('libjpeg failing at the header', dict(), {'jfail': {'read_header'}}), ('libjpeg failing at a row', dict(), {'jfail': {'read:20'}}),
             ('a refused output file', dict(), {'refuse': True}), ('a write error', dict(), {'jfail': {'write:5'}}), ('no saved picture', dict(data=None), {}), ('garbage', dict(data=b'\xff\xd8\xff\xe0' + b'\0' * 100), {}))
    for what, over, opt in cases:
        m = machine(); m.taglib_kind, m.album_cover = 2, 1
        m.taglib_data = over.get('data', data) if 'data' in over else data
        m.jinit(); m.jfail = opt.get('jfail', set())
        if opt.get('refuse'): m.fail.add(('fopen', art_file(KEY) + '.tmp'))
        out = build(m)
        expect(stock_calls(m)[:1] == ['toolsGetAlbumCover'] and m.jlog.count('create_decompress') == m.jlog.count('destroy_decompress') and m.jlog.count('create_compress') == m.jlog.count('destroy_compress'),
               f'{what}: the stock call is made, every libjpeg object destroyed ({stock_calls(m)})')
        expect(TMP not in m.fs and not [p for p in m.fs if p.endswith('.tmp')] or what == 'a refused output file', f'{what}: no temporary file left behind')

    # 6. No embedded picture: taglib says 0, stock's embedded call is not made (it would ask taglib again); the folder is looked at.
    data, im = picture(900, 900)
    m = machine(); m.taglib_kind = 0; m.extern_cover = 1
    build(m)
    expect(stock_calls(m) == ['toolsGetExternCover'] and any(c[0] == 'opendir' and c[1] == DIR for c in m.calls), 'no embedded art: the folder is scanned, stock\'s folder call follows an empty folder, stock\'s embedded call is skipped')
    sq, sq_im = picture(800, 800)        # (168, 168)
    wd, wd_im = picture(700, 500)        # (168, 120)
    tl, tl_im = picture(500, 700)        # (120, 168)
    pn, pn_im = picture(640, 480, fmt='PNG')   # (168, 126)
    sizes = {'sq': fit(800, 800, ART), 'wd': fit(700, 500, ART), 'tl': fit(500, 700, ART), 'pn': fit(640, 480, ART)}

    def folder(files, **kw):
        m = machine(); m.taglib_kind = 0
        for k, v in kw.items(): setattr(m, k, v)
        for name, data in files.items(): m.put(f'{DIR}/{name}', data)
        out = build(m)
        return m, (decoded(out).size if out else None)

    # stock's order: <track>.jpeg, .jpg, .png, cover.jpeg, .jpg, .png, folder.jpeg, .jpg, .png (the later of its nine names goes to the front last), then the rest in readdir order
    m, got = folder({'cover.jpg': sq, 'folder.jpg': wd})
    expect(got == sizes['sq'] and not stock_calls(m), f'cover.jpg before folder.jpg ({got})')
    m, got = folder({'folder.jpg': wd, 'folder.png': pn})
    expect(got == sizes['wd'], f'folder.jpg before folder.png ({got})')
    m, got = folder({'cover.png': pn, 'folder.jpeg': tl})
    expect(got == sizes['pn'], f'cover.png before folder.jpeg ({got})')
    m, got = folder({'song.jpg': tl, 'cover.jpg': sq, 'folder.jpg': wd})
    expect(got == sizes['tl'], f'a picture named for the track (song.jpg) comes first ({got})')
    m, got = folder({'SONG.JPEG': wd, 'song.png': tl})
    expect(got == sizes['wd'], f'.jpeg of the track name before its .png, any case ({got})')
    m, got = folder({'Cover.JPG': wd, 'back.jpg': sq})
    expect(got == sizes['wd'], f'names match in any case ({got})')
    m, got = folder({'zzz.jpg': sq, 'aaa.png': pn})
    expect(got == sizes['pn'], f'no known name: readdir order ({got})')
    m, got = folder({'notes.txt': b'x', 'cover.jpg.bak': sq, 'thumb.gif': sq, 'a.jpg': tl})
    expect(got == sizes['tl'], f'only .jpg, .jpeg and .png files count ({got})')
    m = machine(); m.taglib_kind = 0; m.put(f'{DIR}/cover.jpg/inner', b'x'); m.put(f'{DIR}/folder.jpg', wd)
    out = build(m)
    expect(out is not None and decoded(out).size == sizes['wd'], 'a folder named cover.jpg is not a picture (d_type)')
    # stock's file size limits (0x5eb760, 0x5eb7bc): a JPEG over 6 MiB and a PNG over 1 MiB are skipped; the next one is used
    big = sq + b'\0' * (0x600001 - len(sq)); bigpng = pn + b'\0' * (0x100001 - len(pn))
    m, got = folder({'cover.jpg': big, 'folder.jpg': wd})
    expect(got == sizes['wd'], f'a JPEG file over 6 MiB is skipped like stock does ({got})')
    m, got = folder({'cover.png': bigpng, 'folder.jpg': wd})
    expect(got == sizes['wd'], f'a PNG file over 1 MiB is skipped like stock does ({got})')
    m, got = folder({'cover.jpg': big}, extern_cover=1)
    expect(got is None and stock_calls(m) == ['toolsGetExternCover'], 'nothing usable: stock\'s folder call')
    m, got = folder({'cover.jpg': b'\xff\xd8\xff\xe0garbage' * 20, 'folder.jpg': wd})
    expect(got == sizes['wd'] and not stock_calls(m), f'a file that is not a picture (no frame header) is passed over, as stock does ({got})')
    m, got = folder({'cover.jpg': sq[:3000], 'folder.jpg': wd})
    expect(stock_calls(m) == ['toolsGetExternCover'], 'a candidate whose header reads but does not decode: stock\'s folder call walks the folder itself')
    m, got = folder({'cover.jpg': picture(120, 90)[0]}, extern_cover=1)
    expect(stock_calls(m) == ['toolsGetExternCover'] and 'create_compress' not in m.jlog, 'a folder picture smaller than the cover is stock\'s (it keeps it as it is)')

    # 7. Both art kinds in one album: the embedded picture wins, the folder is not looked at.
    m = machine(); m.taglib_kind, m.taglib_data = 2, picture(900, 900)[0]; m.put(f'{DIR}/cover.jpg', wd)
    out = build(m)
    expect(decoded(out).size == (ART, ART) and not [c for c in m.calls if c[0] == 'opendir'], 'an album with embedded art does not look at its folder')

    # 8. The transient extraction of the Pod's cover pane (cc_build_add_file, 264 px): the same path at the larger size, kept only when the picture reaches it.
    dst = '/tmp/m1plus-pane.jpg'

    def pane(w, h):
        m = machine(); m.taglib_kind, m.taglib_data = 2, picture(w, h)[0]
        m.thread = None
        assert m.call(PSYMS['cc_build_open'], a0=1, a1=0, count=1 << 40) == 1
        assert m.call(PSYMS['cc_build_add_file'], a0=m.cstr(TRACK), a1=m.cstr(dst), a2=264, count=1 << 40) == 1
        assert m.call(PSYMS['cc_build_start'], count=1 << 40) == 1
        m.call(m.thread[0], a0=m.thread[1], count=1 << 40); calls = m.calls; m.call(PSYMS['cc_build_stop'], count=1 << 40); m.calls = calls
        return m
    m = pane(1000, 700)
    expect(dst in m.fs and decoded(m.fs[dst]).size == fit(1000, 700, 264) and ('encoded', fit(1000, 700, 264), 90) in m.jlog, f'the pane\'s picture is 264 px by the same path ({decoded(m.fs[dst]).size if dst in m.fs else None})')
    m = pane(200, 200)
    expect(dst not in m.fs, 'a source under 264 px is not kept')
