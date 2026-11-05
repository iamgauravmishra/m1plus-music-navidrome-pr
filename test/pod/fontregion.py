"""Regional CJK forms (patch/fontregion.c): the UI language points the live stb font at default.ttf's regional cmap
(tools/mod_font.py REGIONS), on the built font; the cache is emptied only on a change; every mismatch leaves the font
alone; a language or theme change applies it again from one timer; the boot guard's ready path is the only caller."""
import os, struct
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import mod_font

FM, KILL = 0x24000000, '/mnt/mmc/m1plus-off'
LOCALES = {('zh', 'CN'): 25, ('zh', 'HK'): 2, ('zh', 'TW'): 2, ('ja', 'JP'): 1, ('en', 'US'): None, ('ko', 'KR'): None, ('de', 'DE'): None}


def font_machine(font, lang='zh', country='CN', index_map=None, stb=True):
    """A machine with the font manager, a font_stb_t over the built ttf (data in emulated memory) and the locale."""
    m = Machine()
    m.fm = FM
    data = m.malloc(len(font)); m.u.mem_write(data, font)
    f = m.malloc(0xd4); m.u.mem_write(f, bytes(0xd4))
    m.setword(f + O['FONT_MATCH'], O['STB_MATCH'] if stb else 0x650000)
    m.setword(f + O['FONT_GET_GLYPH'], O['STB_GET_GLYPH'])
    m.setword(f + O['FONT_DATA'], data); m.setword(f + O['FONT_START'], 0)
    m.setword(f + O['FONT_INDEX_MAP'], mod_font.cmap_subtable(font) if index_map is None else index_map)   # as stbtt_InitFont left it
    m.font = f
    m.locale = m.alloc(8); m.u.mem_write(m.locale, country.encode().ljust(3, b'\0') + lang.encode().ljust(3, b'\0'))
    return m


def run(ctx):
    expect = ctx.expect
    font = open(os.path.join(ctx.work, 'rootfs', mod_font.FONT.removeprefix('rootfs/')), 'rb').read()
    default = mod_font.cmap_subtable(font)
    sub = {e: mod_font.cmap_subtable(font, (1, e)) for e in (1, 2, 25)}
    BOOT = PSYMS['fr_boot']

    # 1. The layout the payload writes is the one stb reads: index_map is fontinfo +0x2c (stbtt_FindGlyphIndex lw 0x2c(a0),
    #    a0 = font + 0x38), data +4; the pins in tools/pod.py FONT_PINS prove the stores; the regional maps are in the font.
    expect(O['FONT_INDEX_MAP'] == 0x38 + 0x2c and O['FONT_DATA'] == 0x38 + 4 and O['FONT_START'] == 0x38 + 8,
           'FONT_DATA, FONT_START and FONT_INDEX_MAP are stbtt_fontinfo data, fontstart and index_map at the font object +0x38')
    expect(all(any(a == p for a, _, _ in pod.FONT_PINS) for p in (0x67c3c4, 0x67f758, 0x67f030)), 'the stores and the per-lookup read are pinned')
    expect({e: mod_font.REGIONS[r][0] for r, e in (('jp', 1), ('tc', 2), ('sc', 25))} == {1: 1, 2: 2, 25: 25} and len(set(sub.values()) | {default}) == 4,
           'the built font has the default and the three regional subtables, distinct (JP 1, TC 2, SC 25)')

    # 2. Each language picks its map; the glyph cache is emptied and the screen repainted only when it changes.
    for (lang, country), enc in LOCALES.items():
        m = font_machine(font, lang, country)
        m.call(BOOT, count=200000)
        want = sub[enc] if enc else default
        got = m.word(m.font + O['FONT_INDEX_MAP'])
        expect(got == want, f'{lang}_{country}: index_map {got:#x} is the {enc or "default"} subtable {want:#x}')
        # (the machine starts with stock's glyph slot: the coverage gamma's install (patch/textgamma.c) empties the cache and repaints once)
        shrunk = ('font_manager_shrink_cache', FM, 0) in m.calls
        expect(shrunk and ('widget_invalidate_force', m.wm) in m.calls,
               f'{lang}_{country}: the glyph cache is emptied (keep 0) and the window manager repainted by the first apply')
        m.call(BOOT, count=200000)
        expect(not any(c[0] in ('font_manager_shrink_cache', 'widget_invalidate_force') for c in m.calls),
               f'{lang}_{country}: a second apply on the same language changes nothing (no cache clear, no repaint)')
        expect(('font_manager_get_font', FM, 'default', 0) in m.calls, f'{lang}_{country}: the font is the stock "default", any size')

    # 3. Back to the default map: a regional font and an English UI, or the kill switch.
    m = font_machine(font, 'en', 'US', index_map=sub[25]); m.call(BOOT, count=200000)
    expect(m.word(m.font + O['FONT_INDEX_MAP']) == default and ('font_manager_shrink_cache', FM, 0) in m.calls, 'English again: the default map, cache emptied')
    m = font_machine(font, 'ja', 'JP', index_map=sub[1]); m.present.add(KILL); m.call(BOOT, count=200000)
    expect(m.word(m.font + O['FONT_INDEX_MAP']) == default, 'the kill switch: the default map, whatever the language')

    # 4. Mismatches leave the font alone: not an stb font, no data, no font manager, no such subtable.
    m = font_machine(font, 'ja', 'JP', stb=False); m.call(BOOT, count=200000)
    expect(m.word(m.font + O['FONT_INDEX_MAP']) == default and not any(c[0] == 'font_manager_shrink_cache' for c in m.calls), 'not an stb font: untouched')
    m = font_machine(font, 'ja', 'JP'); m.setword(m.font + O['FONT_DATA'], 0); m.call(BOOT, count=200000)
    expect(m.word(m.font + O['FONT_INDEX_MAP']) == default, 'no font data: untouched')
    m = font_machine(font, 'ja', 'JP'); m.fm = 0; m.call(BOOT, count=200000)
    expect(not any(c[0] == 'font_manager_get_font' for c in m.calls), 'no font manager: no font is asked for')
    from mod_boot import tables
    plain, cm = bytearray(font), tables(font)[b'cmap'][2]
    for k in range(struct.unpack_from('>H', font, cm + 2)[0]):   # the regional records moved to platform 2 (ISO): no (1, enc) left
        if struct.unpack_from('>H', font, cm + 4 + 8 * k)[0] == 1: struct.pack_into('>H', plain, cm + 4 + 8 * k, 2)
    m = font_machine(bytes(plain), 'ja', 'JP'); m.call(BOOT, count=200000)
    expect(m.word(m.font + O['FONT_INDEX_MAP']) == default and m.word(m.font + O['FONT_GET_GLYPH']) == PSYMS['tg_get_glyph'],
           'a font without the regional record: the index map is untouched (the coverage gamma still applies)')

    # 5. A language or theme change: one timer (not two for two events), which applies the new language.
    m = font_machine(font, 'zh', 'CN'); m.call(BOOT, count=200000)
    on = [c for c in m.calls if c[0] == 'locale_info_on']
    th = [c for c in m.calls if c[0] == 'widget_on']
    expect(len(on) == 1 and on[0][1] == m.locale and on[0][2] == O['EVT_LOCALE_CHANGED'], 'locale_info_on(locale_info(), EVT_LOCALE_CHANGED, ..)')
    expect(len(th) == 1 and th[0][1:3] == (m.wm, O['EVT_THEME_CHANGED']) and th[0][3] == on[0][3], 'widget_on(window_manager(), EVT_THEME_CHANGED) with the same handler')
    cb = on[0][3]; m.timers.clear()
    m.u.mem_write(m.locale, b'HK\0zh\0')
    m.call(cb, count=20000); m.call(cb, count=20000)
    expect(len(m.timers) == 1 and m.timers[0][1] == 10, f'two events, one 10 ms timer ({m.timers})')
    expect(m.word(m.font + O['FONT_INDEX_MAP']) == sub[25], 'nothing is applied from the event itself (the font is being replaced)')
    r = m.call(m.timers[0][0], count=200000)
    expect(r == 0 and m.word(m.font + O['FONT_INDEX_MAP']) == sub[2], 'the timer applies zh_HK (TC) and returns RET_OK (one-shot)')
    m.timers.clear(); m.call(cb, count=20000)
    expect(len(m.timers) == 1, 'after it ran, the next change schedules again')

    # 6. A re-created Home (home_page_init again) applies it again but registers no second handler.
    m = font_machine(font, 'zh', 'CN'); m.call(BOOT, count=200000)
    m.u.mem_write(m.locale, b'JP\0ja\0'); n = len(m.calls); m.call(BOOT, count=200000)
    expect(m.word(m.font + O['FONT_INDEX_MAP']) == sub[1], 'the second call applies the language (ja: JP)')
    expect(not [c for c in m.calls[n:] if c[0] in ('locale_info_on', 'widget_on')], 'and registers nothing again')

    # 7. The only caller is the boot guard's ready path (patch/home.c home_boot, after the marker): the kill switch
    #    stops the guard before it, so a killed boot never touches the font (test/pod/home.py checks the ready path).
    src = open(os.path.join(ROOT, 'patch', 'home.c')).read()
    expect(src.count('fr_boot();') == 1 and src.index('fr_boot();') > src.index('if (hm_ready()) {', src.index('void home_boot')),
           'fr_boot is called once, inside home_boot\'s hm_ready() block')
