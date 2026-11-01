#!/usr/bin/env python3
"""UI font: Inter for Latin/Greek/Cyrillic, Source Han Sans SC for CJK/kana/Hangul (asset-only). docs/ui.md

The whole UI draws with one file, release/assets/default/raw/fonts/default.ttf ("微软雅黑+Arial",
256 units/em, hhea ascender 230 / descender -69), through AWTK's stb_truetype backend: no hinting, no
kerning, no OpenType features, no fallback to another file, font_size px = ascender - descender.
This step rewrites that file by code point and keeps everything the layout depends on:

  inter    every code point of the committed subset assets/fonts/Inter-m1plus.ttf (tools/font_inter.py:
           Inter 4.1, INTER_RANGES, tabular digits baked into the cmap, outlines already at INTER_EM
           units per em) gets Inter's glyph; glyphs are added, stock ones nothing maps to any more are
           pruned. Code points Inter adds that stock lacked are mapped too. Tracking: every advance
           loses INTER_TRACKING units, outlines move left half of that (demo adds 1 px per glyph,
           so Inter as designed reads ~3 % wider than the stock Arial; tightened it averages Arial).
  cjk      every stock code point in CJK_RANGES (CJK Unified + Ext A, Hiragana, Katakana + phonetic
           ext, Hangul syllables and compatibility jamo, radicals, strokes, Bopomofo, CJK punctuation,
           fullwidth and halfwidth forms, vertical and small forms, enclosed and squared CJK) gets
           Source Han Sans SC Medium 2.005R's glyph (SHS_WEIGHT), so the punctuation in Chinese text matches the
           ideographs (SC placement: comma and full stop in the lower left): the CFF outline is
           scaled 0.256 (1000 -> 256 units/em), shifted CJK_DY units, converted to quadratic curves
           (cu2qu, max error 1 unit) and written over the stock glyph; advance round(adv * 0.256).
           SHS is read from the pinned release zip in fonts/ (mod_font.py --fetch), not committed.
  strip    hinting (fpgm, prep, cvt, glyph programs), gasp, DSIG and glyph names (post 3.0) dropped:
           stb_truetype reads none of them.
  kept     unitsPerEm, hhea ascender/descender/lineGap, OS/2, head dates, GDEF/GPOS/GSUB (pruned
           to the remaining glyphs), every other stock glyph (symbols, arrows, conjoining Hangul jamo
           and halfwidth Hangul, Thai, Arabic, ...). The name table's copyright line gains the Inter and Source Han
           Sans notices (both SIL OFL 1.1; the merged font is not called "Source", a Reserved Font Name).

Checks: the tree's font is the stock V2.1 file (SHA-256); the inputs are pinned; on the result,
mod_boot.stb_lookup (a port of stb_truetype's format-4 lookup) gives a glyph with ink for every
code point that had ink in stock (no tofu), the replaced code points get the new glyphs, all others
keep their stock outline, and the vertical metrics are stock.

Usage: mod_font.py SRC_WORKDIR OUT_WORKDIR
       mod_font.py --fetch            download the pinned Source Han Sans TTC zip into fonts/
Needs fontTools (uv sync). OUT_WORKDIR == SRC_WORKDIR edits in place.
"""
import argparse, hashlib, io, os, struct, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir, write_keep_mode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = 'rootfs/release/assets/default/raw/fonts/default.ttf'
FONT_SHA = '9a16af0aead992a2ad64f86d0de8d38bea60d6f605d42ffd0501684666161872'      # stock V2.1 (= mod_boot.FONT_SHA)

LYRIC_FONT = 'rootfs/release/assets/default/raw/fonts/lyrics.ttf'   # the lyrics' bold face (a second file; AWTK name "lyrics")
LYRIC_ASSET = 'assets/fonts/Inter-Bold-m1plus.ttf'
LYRIC_SHA = '25127500c201a6b5c0495549bd0ec65070495fa73363c7daac2ed4566f65d67c'   # tools/font_inter.py --weight Bold output
LYRIC_TRACKING = 16               # tighter than the UI face's 8: bold display text at 30 px, Apple's tight set; 'Be what you want to be' fits one 264 px row
INTER_ASSET = 'assets/fonts/Inter-m1plus.ttf'
INTER_SHA = 'a9909568a98305254788e3927126a6d4bf1b0d62079344aa5496f1c07ebb7bec'   # tools/font_inter.py output
INTER_WEIGHT, INTER_EM = 'Medium', 252
INTER_TRACKING = 8               # units cut from every Inter advance (track(); --tracking, 0 = Inter as designed):
                                 # English UI strings and titles then average Arial's width at 16/18/21 px
INTER_RANGES = [(0x0020, 0x007E), (0x00A0, 0x024F),     # Basic Latin, Latin-1, Latin Extended-A/B
                (0x02B0, 0x036F),                       # spacing modifiers, combining marks (NFD tags)
                (0x0370, 0x03FF), (0x0400, 0x052F),     # Greek, Cyrillic + supplement
                (0x1E00, 0x1EFF),                       # Latin Extended Additional (Vietnamese)
                (0x2000, 0x206F), (0x2070, 0x209F), (0x20A0, 0x20CF),   # punctuation, super/subscripts, currency
                (0x2116, 0x2116), (0x2122, 0x2122)]     # numero, trade mark

SHS_URL = 'https://github.com/adobe-fonts/source-han-sans/releases/download/2.005R/01_SourceHanSans.ttc.zip'
SHS_ZIP = 'fonts/01_SourceHanSans.ttc.zip'
import paths   # tools/paths.py: the zip may live in the main checkout's fonts/ (worktrees)
SHS_ZIP_SHA = 'a024cf1759494847cd47aae4379bcb3dc530017c709f3f503ee0ed918dd92952'
SHS_MEMBER, SHS_SHA = 'SourceHanSans.ttc', '1382ea173f57af2ef9de32b41ce24d9c33fe69b8f4f2eae7cf05e64a4efd8aef'
SHS_FACES = {'Regular': (15, 17, 18), 'Medium': (25, 27, 28)}   # TTC faces (JP, SC, TC); one CFF per weight,
                                                                # so a glyph two regions share has one glyph name
SHS_WEIGHT = 'Medium'            # the CJK weight: Regular's stems read thin at 16-22 px (preview_cjk.py sheet),
                                 # Medium matches the Inter Medium beside it
CJK_RANGES = [(0x3040, 0x309F), (0x30A0, 0x30FF), (0x31F0, 0x31FF),   # Hiragana, Katakana, phonetic ext
              (0x3400, 0x4DBF), (0x4E00, 0x9FFF),                     # CJK Ext A, CJK Unified
              (0xAC00, 0xD7A3), (0x3130, 0x318F),                     # Hangul syllables, compatibility jamo
              (0x2E80, 0x2EFF), (0x2F00, 0x2FDF), (0x31C0, 0x31EF),   # radicals supplement, Kangxi, strokes
              (0x3000, 0x303F), (0x3100, 0x312F), (0x3190, 0x319F),   # CJK punctuation, Bopomofo, Kanbun
              (0x3200, 0x32FF), (0x3300, 0x33FF),                     # enclosed CJK, CJK compatibility
              (0xFE10, 0xFE1F), (0xFE30, 0xFE4F), (0xFE50, 0xFE6F),   # vertical, CJK compat, small forms
              (0xFF01, 0xFF60), (0xFF61, 0xFF9F),                     # fullwidth forms, halfwidth kana
              (0xFFE0, 0xFFE6), (0xFFE8, 0xFFEE)]                     # fullwidth signs, halfwidth forms
              # left stock: conjoining jamo U+1100-11FF and halfwidth Hangul U+FFA0-FFDC (SHS sets them
              # 236 units wide, stock 256 and 128); U+2014 / 2026 / quotes stay Inter's (shared with Latin)
CJK_SCALE, CJK_DY, CJK_ERR = 0.256, -7, 1.0

def _encoded(c, codec, lo, hi):
    try: b = chr(c).encode(codec)
    except UnicodeEncodeError: return False
    return len(b) == 2 and lo <= int.from_bytes(b, 'big') <= hi
def _ideograph(c): return 0x3400 <= c <= 0x9FFF
# Regional cmaps: Mac-platform format-4 subtables stb_truetype never picks (it takes platform 0 and 3/1, 3/10),
# each the default (3, 1) map with that region's glyphs where they differ from SC; the payload points stb's
# index_map at one by UI language (patch/fontregion.c). Encoding IDs are the Mac script codes. Ideographs only
# in the region's common set (space: rootfs headroom); every non-ideograph that differs (punctuation, kana).
REGIONS = {'sc': (25, lambda c: True),                                                   # zh_CN
           'jp': (1, lambda c: not _ideograph(c) or _encoded(c, 'shift_jis', 0x889F, 0x9872)),  # ja_JP: JIS level 1
           'tc': (2, lambda c: not _ideograph(c) or _encoded(c, 'big5', 0xA440, 0xC67E))}       # zh_HK: Big5 common
CJK_DASHES = {0x2014: ('fwid', 12), 0x2026: (None, 0)}   # in every regional map: SHS's full-width dash (its
    # fwid form) and centred ellipsis, so —— and …… run on; Latin UIs keep Inter's. The dash's ink is stretched to
    # 12 units past both edges of its advance: demo's +1 px per glyph and truncated advance would leave a 1 px gap

NOTICE = (' Latin, Greek and Cyrillic: Inter, Copyright 2016 The Inter Project Authors (https://github.com/rsms/inter).'
          ' CJK, kana and Hangul: Source Han Sans, Copyright 2014-2025 Adobe (http://www.adobe.com/).'
          ' Both under the SIL Open Font License 1.1.')

def in_ranges(c, ranges): return any(a <= c <= b for a, b in ranges)
def sha256(b): return hashlib.sha256(b).hexdigest()
def check(ok, msg):
    if not ok: raise SystemExit(f'mod_font: {msg}')

def fetch(path=os.path.join(ROOT, SHS_ZIP)):
    import urllib.request
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        print(f'downloading {SHS_URL}')
        tmp = path + '.part'
        urllib.request.urlretrieve(SHS_URL, tmp); os.replace(tmp, path)
    check(sha256(open(path, 'rb').read()) == SHS_ZIP_SHA, f'{path}: SHA-256 mismatch (want the 2.005R release zip)')
    print(f'{path}: OK')

def shs_faces(path, weight=SHS_WEIGHT):
    """{'jp', 'sc', 'tc'}: the weight's three faces of the pinned Source Han Sans TTC (lazy TTFonts)."""
    from fontTools.ttLib import TTCollection
    check(os.path.exists(path), f'missing {path}: run `python3 -I tools/mod_font.py --fetch` (or download {SHS_URL} there)')
    check(sha256(open(path, 'rb').read()) == SHS_ZIP_SHA, f'{path}: SHA-256 mismatch')
    with zipfile.ZipFile(path) as z: b = z.read(SHS_MEMBER)
    check(sha256(b) == SHS_SHA, f'{SHS_MEMBER}: SHA-256 mismatch')
    ttc = TTCollection(io.BytesIO(b), lazy=True)
    faces = {}
    for r, i in zip(('jp', 'sc', 'tc'), SHS_FACES[weight]):
        want = ' '.join(['Source Han Sans'] + ([r.upper()] if r != 'jp' else []) + ([weight] if weight != 'Regular' else []))
        check(ttc.fonts[i]['name'].getDebugName(4) == want, f'{SHS_MEMBER} face {i} is not {want}')
        faces[r] = ttc.fonts[i]
    return faces

def fwid(face):
    """glyph -> full-width glyph, from the face's GSUB 'fwid' single substitutions."""
    gsub, m = face['GSUB'].table, {}
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag != 'fwid': continue
        for li in fr.Feature.LookupListIndex:
            for st in gsub.LookupList.Lookup[li].SubTable:
                st = getattr(st, 'ExtSubTable', st)
                m.update(getattr(st, 'mapping', {}))
    return m

def track(inter, k):
    """The Inter subset with every non-zero advance cut by k units and each outline moved left by k // 2,
    so both sidebearings lose about k / 2 (digits stay tabular: they all lose the same k)."""
    if not k: return inter
    from fontTools.ttLib import TTFont
    f = TTFont(io.BytesIO(inter), recalcTimestamp=False)
    glyf, hmtx = f['glyf'], f['hmtx']
    for n in f.getGlyphOrder():
        adv, lsb = hmtx[n]
        if adv <= k: continue                            # combining marks (0) and anything too narrow to cut
        g = glyf[n]
        if g.numberOfContours > 0:
            g.coordinates.translate((-(k // 2), 0)); g.recalcBounds(glyf); lsb = g.xMin
        hmtx[n] = (adv - k, lsb)
    out = io.BytesIO(); f.save(out)
    return out.getvalue()

def lyric_face(inter, stock, k=0):
    """The lyrics' second font file: the Inter subset of a heavy weight (tools/font_inter.py --weight), tracked k units,
    as a stand-alone 256 unit font with default.ttf's vertical metrics (hhea, OS/2), so a font size means the same
    pixels and rows sit on the same baseline as the default font's. Its outlines stay on the 252 grid as in merge()."""
    from fontTools.ttLib import TTFont
    f = TTFont(io.BytesIO(track(inter, k)), recalcTimestamp=False)
    s = TTFont(io.BytesIO(stock), recalcTimestamp=False)
    f['head'].unitsPerEm = s['head'].unitsPerEm
    for t, names in (('hhea', ('ascent', 'descent', 'lineGap')),
                     ('OS/2', ('sTypoAscender', 'sTypoDescender', 'sTypoLineGap', 'usWinAscent', 'usWinDescent'))):
        for n in names: setattr(f[t], n, getattr(s[t], n))
    out = io.BytesIO(); f.save(out)
    return out.getvalue()

def merge(stock, inter=None, shs=None, log=print, ranges=CJK_RANGES, regions=REGIONS):
    """stock default.ttf bytes (+ Inter subset bytes, + shs_faces()) -> new font bytes, report.
    ranges: the code points SHS replaces (tools/preview_cjk.py draws the font before the punctuation step);
    regions: the regional cmaps to add (REGIONS or a part of it)."""
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable
    from fontTools import subset
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.transformPen import TransformPen

    def outline(gs, g):
        tt = TTGlyphPen(None)
        gs[g].draw(TransformPen(Cu2QuPen(tt, CJK_ERR, reverse_direction=True), (CJK_SCALE, 0, 0, CJK_SCALE, 0, CJK_DY)))
        g = tt.glyph(dropImpliedOnCurves=False); g.recalcBounds(glyf)
        return g

    f = TTFont(io.BytesIO(stock), recalcTimestamp=False)
    best = dict(f.getBestCmap())                        # a copy: setmap() edits the tables
    uni = [t for t in f['cmap'].tables if t.isUnicode()]
    f['cmap'].tables = uni                              # the Mac Roman subtable: stb never reads it
    order = list(f.getGlyphOrder())
    glyf, hmtx = f['glyf'], f['hmtx']
    users = {}
    for c, g in best.items(): users.setdefault(g, []).append(c)
    rep = {'cjk': [], 'inter': [], 'cjk_new_glyphs': 0}

    def setmap(c, g):
        for t in uni: t.cmap[c] = g

    regional = {}                                       # region -> {code point: glyph name}
    if shs:
        k = CJK_SCALE
        scm, sgs, shm = shs['sc'].getBestCmap(), shs['sc'].getGlyphSet(), shs['sc']['hmtx']
        cps = [c for c in sorted(best) if in_ranges(c, ranges)]
        for c in cps:
            sg = scm.get(c)
            check(sg is not None, f'Source Han Sans SC has no U+{c:04X}')
            g = outline(sgs, sg)
            name = best[c]
            if len(users[name]) > 1:                    # shared stock glyph: give this code point its own
                name = f'cjk.{c:04X}'; order.append(name); setmap(c, name); rep['cjk_new_glyphs'] += 1
            glyf[name] = g
            hmtx[name] = (round(shm[sg][0] * k), g.xMin if g.numberOfContours else 0)
            rep['cjk'].append(c)
        log(f'cjk: {len(cps)} code points from Source Han Sans SC {SHS_WEIGHT} (x{k}, dy {CJK_DY}, cu2qu {CJK_ERR}), '
            f'{rep["cjk_new_glyphs"]} on a glyph of their own')

        def shs_glyph(g, hm, run=0):                    # one glyph per SHS glyph, shared by the regions
            name = 'shs.' + g + ('.run' if run else '')
            if name not in glyf:
                glyf[name] = o = outline(sgs, g); order.append(name)
                if run:                                 # ink from -run to advance + run
                    x0, x1, a = o.xMin, o.xMax, round(hm[g][0] * k)
                    sx = (a + 2 * run) / (x1 - x0)
                    o.coordinates.transform(((sx, 0), (0, 1)))
                    o.coordinates.translate((-run - x0 * sx, 0))
                    o.coordinates.toInt(); o.recalcBounds(glyf)
                hmtx[name] = (round(hm[g][0] * k), o.xMin if o.numberOfContours else 0)
            return name
        for r, (_, pick) in regions.items():
            rcm, rhm, m = shs[r].getBestCmap(), shs[r]['hmtx'], {}
            for c in cps:
                g = rcm.get(c)
                if g is not None and g != scm[c] and pick(c): m[c] = shs_glyph(g, rhm)
            wide = fwid(shs[r])
            for c, (feat, run) in CJK_DASHES.items():
                if c in best: m[c] = shs_glyph(wide[rcm[c]] if feat else rcm[c], rhm, run)
            regional[r] = m
        if regional:
            log('regional cmaps: ' + ', '.join(f'{r} {len(m)} code points' for r, m in regional.items()) +
                f'; {len([n for n in order if n.startswith("shs.")])} glyphs added')

    if inter:
        i = TTFont(io.BytesIO(inter), lazy=False)
        icm, ig, ih = i.getBestCmap(), i['glyf'], i['hmtx']
        check(all(in_ranges(c, INTER_RANGES) for c in icm), 'Inter subset maps code points outside INTER_RANGES')
        added = {}
        for c in sorted(icm):
            n = icm[c]
            if n not in added:
                added[n] = 'inter.' + n; order.append(added[n])
                glyf[added[n]] = ig[n]; hmtx[added[n]] = ih[n]
            setmap(c, added[n]); rep['inter'].append(c)
        log(f'inter: {len(icm)} code points, {len(added)} glyphs ({len([c for c in icm if c in best])} replace stock, '
            f'{len([c for c in icm if c not in best])} new)')

    f.setGlyphOrder(order)
    f['maxp'].numGlyphs = len(order)
    # prune glyphs nothing maps to, drop hinting, gasp, DSIG and glyph names (post 3.0)
    o = subset.Options()
    o.layout_features = ['*']; o.hinting = False; o.glyph_names = False; o.notdef_outline = True
    o.name_IDs = ['*']; o.name_languages = ['*']; o.name_legacy = True; o.legacy_kern = True
    o.recalc_bounds = True; o.prune_unicode_ranges = False; o.recommended_glyphs = False
    o.drop_tables += ['DSIG', 'gasp']
    sub = subset.Subsetter(o)
    sub.populate(unicodes=sorted(set().union(*(t.cmap for t in uni))),
                 glyphs=sorted({n for m in regional.values() for n in m.values()}))
    sub.subset(f)
    base = next(t for t in f['cmap'].tables if (t.platformID, t.platEncID) == (3, 1)).cmap
    for r, m in regional.items():                       # added after the subset pass, which drops Mac subtables
        t = CmapSubtable.newSubtable(4); t.platformID, t.platEncID, t.language = 1, regions[r][0], 0
        t.cmap = {**base, **m}; f['cmap'].tables.append(t)
    f['cmap'].tables.sort(key=lambda t: (t.platformID, t.platEncID, t.language))
    rep['regional'] = regional
    for n in f['name'].names:
        if n.nameID == 0: n.string = n.toUnicode() + NOTICE
    out = io.BytesIO(); f.save(out)
    return out.getvalue(), rep

# ---- checks (pure Python: the stb_truetype view of the file) -------------------------------------

def cmap_subtable(d, record=None):
    """File offset of the format-4 subtable stb_truetype picks, or of encoding record (platform, encoding)
    (a regional map, as the payload points stb's index_map at it)."""
    from mod_boot import tables
    t = tables(d); c = t[b'cmap'][2]; sub = None
    for k in range(struct.unpack_from('>H', d, c + 2)[0]):
        pid, eid, off = struct.unpack_from('>HHI', d, c + 4 + 8 * k)
        stb = pid == 0 or (pid == 3 and eid in (1, 10))                 # stbtt_InitFont: the last match wins
        if (pid, eid) == record if record else stb: sub = c + off
    check(sub is not None and struct.unpack_from('>H', d, sub)[0] == 4, f'no format-4 cmap {record or "for stb_truetype"}')
    return sub

def stb_map(d, record=None):
    """code point -> glyph for every BMP code point, through stb_truetype's lookup on cmap_subtable(d, record)."""
    from mod_boot import stb_lookup
    sub = cmap_subtable(d, record)
    return {cp: g for cp in range(0x10000) if (g := stb_lookup(d, sub, cp))}

def verify(stock, new, rep):
    from stb_raster import StbFont
    sf, nf = StbFont(stock), StbFont(new)
    check((sf.asc, sf.desc) == (nf.asc, nf.desc), 'hhea ascender/descender changed')
    upem = lambda d, o: struct.unpack_from('>H', d, o + 18)[0]
    check(upem(stock, sf.t['head']) == upem(new, nf.t['head']) == 256, 'unitsPerEm changed')
    check(struct.unpack_from('>h', stock, sf.t['hhea'] + 8) == struct.unpack_from('>h', new, nf.t['hhea'] + 8), 'lineGap changed')
    sm, nm = stb_map(stock), stb_map(new)
    replaced = set(rep['cjk']) | set(rep['inter'])
    lost = [c for c in sm if c not in nm]
    check(not lost, f'{len(lost)} code points lost, e.g. ' + ' '.join(f'U+{c:04X}' for c in lost[:10]))
    inked = lambda f, g: bool(f.shape(g))
    tofu = [c for c in sm if inked(sf, sm[c]) and not inked(nf, nm[c])]
    check(not tofu, f'{len(tofu)} code points lost their ink, e.g. ' + ' '.join(f'U+{c:04X}' for c in tofu[:10]))
    same = [c for c in sm if c not in replaced]
    moved = [c for c in same if sf.shape(sm[c]) != nf.shape(nm[c]) or sf.advance(sm[c]) != nf.advance(nm[c])]
    check(not moved, f'{len(moved)} code points outside the replaced set changed, e.g. ' + ' '.join(f'U+{c:04X}' for c in moved[:10]))
    added = sorted(c for c in nm if c not in sm)
    check(all(c in rep['inter'] for c in added), 'unexpected new code points')
    for r, m in rep.get('regional', {}).items():
        rm = stb_map(new, (1, REGIONS[r][0]))
        check(set(rm) == set(nm), f'regional cmap {r}: code points differ from the default map')
        bad = [c for c in nm if (rm[c] != nm[c]) != (c in m) or (c in m and not inked(nf, rm[c]))]
        check(not bad, f'regional cmap {r}: {len(bad)} wrong mappings, e.g. ' + ' '.join(f'U+{c:04X}' for c in bad[:10]))
    return dict(stock_cps=len(sm), new_cps=len(nm), replaced=len(replaced & set(sm)), added=len(added), unchanged=len(same))

def added_rels(stock_rootfs=None):
    """The file this step adds (fwtool --allow-added)."""
    return [LYRIC_FONT.removeprefix('rootfs/')]

def apply(work, shs_zip=paths.SHS_ZIP):
    p = os.path.join(work, FONT)
    stock = open(p, 'rb').read()
    check(sha256(stock) == FONT_SHA, f'{FONT} is not the stock V2.1 font (the font step must run first)')
    ib = open(os.path.join(ROOT, INTER_ASSET), 'rb').read()
    check(INTER_SHA is None or sha256(ib) == INTER_SHA, f'{INTER_ASSET}: SHA-256 mismatch (regenerate with tools/font_inter.py)')
    ib = track(ib, INTER_TRACKING)
    print(f'inter: tracking -{INTER_TRACKING} units per glyph (outlines moved left {INTER_TRACKING // 2})')
    new, rep = merge(stock, ib, shs_faces(shs_zip))
    r = verify(stock, new, rep)
    write_keep_mode(p, new)
    lb = open(os.path.join(ROOT, LYRIC_ASSET), 'rb').read()
    check(LYRIC_SHA is None or sha256(lb) == LYRIC_SHA, f'{LYRIC_ASSET}: SHA-256 mismatch (regenerate with tools/font_inter.py --weight Bold)')
    lyric = lyric_face(lb, stock, LYRIC_TRACKING)
    lp = os.path.join(work, LYRIC_FONT)
    with open(lp, 'wb') as fh: fh.write(lyric)
    os.chmod(lp, os.stat(p).st_mode & 0o7777)           # the permission bits of default.ttf
    print(f'font: {LYRIC_FONT} {len(lyric)} bytes (Inter Bold, tracking -{LYRIC_TRACKING}), sha256 {sha256(lyric)}')
    print(f'font: {FONT} {len(stock)} -> {len(new)} bytes, sha256 {sha256(new)}; {r["stock_cps"]} stock code points all '
          f'kept with ink, {r["replaced"]} replaced, {r["added"]} added, {r["unchanged"]} unchanged; vertical metrics stock')
    return rep, r

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src', nargs='?'); ap.add_argument('out', nargs='?')
    ap.add_argument('--fetch', action='store_true', help='download and verify the pinned Source Han Sans SC zip, then exit')
    a = ap.parse_args()
    if a.fetch: return fetch(paths.SHS_ZIP)
    if not (a.src and a.out): ap.error('SRC_WORKDIR and OUT_WORKDIR are required')
    clone_workdir(a.src, a.out)
    apply(a.out)

if __name__ == '__main__': main()
