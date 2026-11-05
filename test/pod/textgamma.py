"""Text coverage gamma (patch/textgamma.c, docs/modules/fonts.md "Coverage gamma"): the table is tools/textgamma.py's;
tg_apply swaps the default stb font's get_glyph slot; a freshly rasterized glyph's coverage is mapped once; a cache
hit returns the mapped mask untouched; a glyph without a bitmap is left alone; a mono font, a font that is not an stb
font, a foreign slot and the kill switch leave stock. The stock rasterizer and glyph cache are mocked (harness.py
font_stb_get_glyph and glyph_cache_lookup), so the wrapper runs for real on the emulated payload."""
import os, re, struct
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import textgamma

FM, KILL = 0x24000000, '/mnt/mmc/m1plus-off'
STB, TG = O['STB_GET_GLYPH'], None   # TG: the wrapper's address (a payload symbol), set in run()


def font_machine(stb=True, mono=0):
    """The default font object as font_stb_create leaves it (match, get_glyph, mono flag), with an empty glyph cache."""
    m = Machine()
    m.fm = FM
    f = m.malloc(0xd4); m.u.mem_write(f, bytes(0xd4))
    m.setword(f + O['FONT_MATCH'], O['STB_MATCH'] if stb else 0x650000)
    m.setword(f + O['FONT_GET_GLYPH'], STB)
    m.u.mem_write(f + O['FONT_MONO'], bytes([mono]))
    m.font = f; m.glyph_cache = {}; m.glyph_raw = {}
    return m


def apply(m, kill=False):
    if kill: m.present.add(KILL)
    m.call(PSYMS['tg_apply'], a0=FM, a1=m.font)


def slot(m): return m.word(m.font + O['FONT_GET_GLYPH'])


def draw(m, ch, size=18):
    """One font_get_glyph through the font's slot: (status, the mask the caller reads, the stock calls it made)."""
    out = m.malloc(16)
    rc = m.call(slot(m), a0=m.font, a1=ch, a2=size, a3=out, count=200000)
    hdr = bytes(m.u.mem_read(out, 16))
    w, h = struct.unpack_from('<HH', hdr, 4); data = struct.unpack_from('<I', hdr, 12)[0]
    pix = bytes(m.u.mem_read(data, w * h)) if data else b''
    return rc, pix, list(m.calls)


def run(ctx):
    global TG
    expect = ctx.expect
    TG = PSYMS['tg_get_glyph']
    lut = textgamma.lut()
    stock_h = open(os.path.join(BUILD, 'stock.h')).read()

    # 1. The table the payload uses is tools/textgamma.py's (the preview's formula), 256 monotone values, 0 and 255 fixed.
    table = [int(v) for v in re.search(r'#define TEXT_GAMMA_LUT \{([^}]*)\}', stock_h).group(1).split(',')]
    expect(table == lut and len(lut) == 256 and lut[0] == 0 and lut[255] == 255 and all(a <= b for a, b in zip(lut, lut[1:])),
           'stock.h TEXT_GAMMA_LUT is tools/textgamma.py lut(): 256 monotone values, 0 and 255 fixed')
    expect(lut[64] > 64 and lut[128] > 128 and textgamma.lut(1.0) == list(range(256)),
           'the curve lifts the coverage; gamma 1.0 is the identity (today\'s device)')

    # 2. Install: the slot becomes the wrapper; the cache is emptied (keep 0) and the window repainted.
    m = font_machine(); apply(m)
    expect(slot(m) == TG, 'tg_apply: the default stb font\'s get_glyph slot is tg_get_glyph')
    expect(('font_manager_shrink_cache', FM, 0) in m.calls and ('widget_invalidate_force', m.wm) in m.calls,
           'the install empties the glyph cache (keep 0) and repaints the window')

    # 3. A fresh glyph: each coverage a is drawn as lut[a], and stock rasterizes it once.
    rc, pix, calls = draw(m, 0x41)
    raw = m.glyph_raw[(0x41, 18)]
    expect(rc == 0 and pix == bytes(lut[v] for v in raw), 'a fresh glyph: each coverage is mapped through the table')
    expect(calls.count(('font_stb_get_glyph', 0x41, 18)) == 1, 'a fresh glyph is rasterized by stock once')

    # 4. A cache hit: stock's copy, already mapped; nothing is rasterized and the mask is not mapped again.
    rc2, pix2, calls2 = draw(m, 0x41)
    expect(rc2 == 0 and pix2 == pix and ('glyph_cache_lookup', 0x41, 18) in calls2 and not any(c[0] == 'font_stb_get_glyph' for c in calls2),
           'a cache hit returns the mapped mask untouched (no second mapping, no rasterizing)')
    expect(bytes(lut[v] for v in pix) != pix, 'the second draw would differ had it been mapped again (the check has teeth)')

    # 5. A glyph with no bitmap (a space): stock's result, untouched.
    rc3, pix3, _ = draw(m, 0x20)
    expect(rc3 == 0 and pix3 == b'', 'a glyph with no bitmap is returned as stock gave it')

    # 6. Left alone: a mono font, a font that is not an stb font, a foreign slot, and the kill switch at install.
    m = font_machine(mono=1); apply(m)
    expect(slot(m) == STB and not any(c[0] == 'font_manager_shrink_cache' for c in m.calls), 'a mono font: stock slot, cache not touched')
    m = font_machine(stb=False); apply(m)
    expect(slot(m) == STB and not m.calls, 'not an stb font: nothing touched')
    m = font_machine(); m.setword(m.font + O['FONT_GET_GLYPH'], 0x650000); apply(m)
    expect(slot(m) == 0x650000 and not any(c[0] == 'font_manager_shrink_cache' for c in m.calls), 'a foreign get_glyph: untouched')
    m = font_machine(); apply(m, kill=True)
    expect(slot(m) == STB and not any(c[0] == 'font_manager_shrink_cache' for c in m.calls), 'the kill switch at install: stock, nothing touched')

    # 7. The kill switch on a later apply restores stock and empties the cache (the mapped masks go); an installed apply is a no-op.
    m = font_machine(); apply(m); apply(m, kill=True)
    expect(slot(m) == STB and ('font_manager_shrink_cache', FM, 0) in m.calls, 'the kill switch at the next apply: stock slot, cache emptied')
    m = font_machine(); apply(m); apply(m)
    expect(slot(m) == TG and not any(c[0] == 'font_manager_shrink_cache' for c in m.calls), 'an apply on the installed wrapper changes nothing')
