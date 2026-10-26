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
           ext, Hangul syllables) gets Source Han Sans SC Regular 2.005R's glyph: the CFF outline is
           scaled 0.256 (1000 -> 256 units/em), shifted CJK_DY units, converted to quadratic curves
           (cu2qu, max error 1 unit) and written over the stock glyph; advance round(adv * 0.256).
           SHS is read from the pinned release zip in fonts/ (mod_font.py --fetch), not committed.
  strip    hinting (fpgm, prep, cvt, glyph programs), gasp, DSIG and glyph names (post 3.0) dropped:
           stb_truetype reads none of them.
  pulldown the pull-down's own status bar (ui/dialog/dropdown_dialog.bin, default and theme1) shows the
           volume at 20 px in a 30 px label; "100" no longer fits it with the new font (Inter: 33 px as
           AWTK lays it out, awtk_text.StbText), so label_volume grows to that width and its row's
           spacing (children_layout s) shrinks by as much, so img_digital, the clock and everything
           right of the label stay where they are. Skipped if "100" fits (the stock font: 30 px).
  kept     unitsPerEm, hhea ascender/descender/lineGap, OS/2, head dates, GDEF/GPOS/GSUB (pruned
           to the remaining glyphs), every other stock glyph (symbols, CJK punctuation, fullwidth
           forms, Thai, Arabic, ...). The name table's copyright line gains the Inter and Source Han
           Sans notices (both SIL OFL 1.1; the merged font is not called "Source", a Reserved Font Name).

Checks: the tree's font is the stock V2.1 file (SHA-256); the inputs are pinned; on the result,
mod_boot.stb_lookup (a port of stb_truetype's format-4 lookup) gives a glyph with ink for every
code point that had ink in stock (no tofu), the replaced code points get the new glyphs, all others
keep their stock outline, and the vertical metrics are stock.

Usage: mod_font.py SRC_WORKDIR OUT_WORKDIR
       mod_font.py --fetch            download the pinned Source Han Sans SC zip into fonts/
Needs fontTools (requirements.txt). OUT_WORKDIR == SRC_WORKDIR edits in place.
"""
import argparse, hashlib, io, os, struct, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir, edit_ui, write_keep_mode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = 'rootfs/release/assets/default/raw/fonts/default.ttf'
FONT_SHA = '9a16af0aead992a2ad64f86d0de8d38bea60d6f605d42ffd0501684666161872'      # stock V2.1 (= mod_boot.FONT_SHA)

INTER_ASSET = 'assets/fonts/Inter-m1plus.ttf'
INTER_SHA = '3c9bfd5ffd477bd0e6ff3c8102e7bc7fc64913406b25a9282f9ae9069ca006e7'   # tools/font_inter.py output
INTER_WEIGHT, INTER_EM = 'Regular', 252
INTER_TRACKING = 8               # units cut from every Inter advance (track(); --tracking, 0 = Inter as designed):
                                 # English UI strings and titles then average Arial's width at 16/18/21 px
INTER_RANGES = [(0x0020, 0x007E), (0x00A0, 0x024F),     # Basic Latin, Latin-1, Latin Extended-A/B
                (0x02B0, 0x036F),                       # spacing modifiers, combining marks (NFD tags)
                (0x0370, 0x03FF), (0x0400, 0x052F),     # Greek, Cyrillic + supplement
                (0x1E00, 0x1EFF),                       # Latin Extended Additional (Vietnamese)
                (0x2000, 0x206F), (0x2070, 0x209F), (0x20A0, 0x20CF),   # punctuation, super/subscripts, currency
                (0x2116, 0x2116), (0x2122, 0x2122)]     # numero, trade mark

SHS_URL = 'https://github.com/adobe-fonts/source-han-sans/releases/download/2.005R/09_SourceHanSansSC.zip'
SHS_ZIP = 'fonts/09_SourceHanSansSC.zip'
import paths   # tools/paths.py: the zip may live in the main checkout's fonts/ (worktrees)
SHS_ZIP_SHA = 'ef7364f7ac2564be1ae9c1d74276de2653fe38b73449070398c4fc0b7e032ff1'
SHS_MEMBER = 'OTF/SimplifiedChinese/SourceHanSansSC-Regular.otf'
SHS_SHA = 'f1d8611151880c6c336aabeac4640ef434fa13cbfbf1ffe82d0a71b2a5637256'
CJK_RANGES = [(0x3040, 0x309F), (0x30A0, 0x30FF), (0x31F0, 0x31FF),   # Hiragana, Katakana, phonetic ext
              (0x3400, 0x4DBF), (0x4E00, 0x9FFF),                     # CJK Ext A, CJK Unified
              (0xAC00, 0xD7A3)]                                       # Hangul syllables
CJK_SCALE, CJK_DY, CJK_ERR = 0.256, -7, 1.0

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

def shs_font(path):
    check(os.path.exists(path), f'missing {path}: run `python3 -I tools/mod_font.py --fetch` (or download {SHS_URL} there)')
    check(sha256(open(path, 'rb').read()) == SHS_ZIP_SHA, f'{path}: SHA-256 mismatch')
    with zipfile.ZipFile(path) as z: b = z.read(SHS_MEMBER)
    check(sha256(b) == SHS_SHA, f'{SHS_MEMBER}: SHA-256 mismatch')
    return b

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

def merge(stock, inter=None, shs=None, log=print):
    """stock default.ttf bytes (+ Inter subset bytes, + SHS SC Regular OTF bytes) -> new font bytes, report."""
    from fontTools.ttLib import TTFont
    from fontTools import subset
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.transformPen import TransformPen

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

    if shs:
        s = TTFont(io.BytesIO(shs), lazy=True)
        scm, sgs, shm = s.getBestCmap(), s.getGlyphSet(), s['hmtx']
        k = CJK_SCALE
        cps = [c for c in sorted(best) if in_ranges(c, CJK_RANGES)]
        for c in cps:
            sg = scm.get(c)
            check(sg is not None, f'Source Han Sans SC has no U+{c:04X}')
            tt = TTGlyphPen(None)
            sgs[sg].draw(TransformPen(Cu2QuPen(tt, CJK_ERR, reverse_direction=True), (k, 0, 0, k, 0, CJK_DY)))
            g = tt.glyph(dropImpliedOnCurves=False); g.recalcBounds(glyf)
            name = best[c]
            if len(users[name]) > 1:                    # shared stock glyph: give this code point its own
                name = f'cjk.{c:04X}'; order.append(name); setmap(c, name); rep['cjk_new_glyphs'] += 1
            glyf[name] = g
            hmtx[name] = (round(shm[sg][0] * k), g.xMin if g.numberOfContours else 0)
            rep['cjk'].append(c)
        log(f'cjk: {len(cps)} code points from Source Han Sans SC Regular (x{k}, dy {CJK_DY}, cu2qu {CJK_ERR}), '
            f'{rep["cjk_new_glyphs"]} on a glyph of their own')

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
    sub.populate(unicodes=sorted(set().union(*(t.cmap for t in uni))))
    sub.subset(f)
    for n in f['name'].names:
        if n.nameID == 0: n.string = n.toUnicode() + NOTICE
    out = io.BytesIO(); f.save(out)
    return out.getvalue(), rep

# ---- checks (pure Python: the stb_truetype view of the file) -------------------------------------

def stb_map(d):
    """code point -> glyph for every BMP code point, through stb_truetype's own cmap choice and lookup."""
    from mod_boot import tables, stb_lookup
    t = tables(d); c = t[b'cmap'][2]; sub = None
    for k in range(struct.unpack_from('>H', d, c + 2)[0]):
        pid, eid, off = struct.unpack_from('>HHI', d, c + 4 + 8 * k)
        if pid == 0 or (pid == 3 and eid in (1, 10)): sub = c + off      # stbtt_InitFont: the last match wins
    check(sub is not None and struct.unpack_from('>H', d, sub)[0] == 4, 'no Unicode format-4 cmap for stb_truetype')
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
    return dict(stock_cps=len(sm), new_cps=len(nm), replaced=len(replaced & set(sm)), added=len(added), unchanged=len(same))

PULLDOWNS = [f'rootfs/release/assets/{t}/raw/ui/dialog/dropdown_dialog.bin' for t in ('default', 'theme1')]
VOLUME_MAX = '100'

def fit_pulldown(work):
    """Widen the pull-down's label_volume to the AWTK width of "100" in the tree's font, taking the
    pixels from the spacing of its row (view_bar_left, children_layout default(r=1,c=0,x=14,s=4)), so
    the row's last child (img_digital) does not move. Returns [(rel, old w, new w, old s, new s)]."""
    import re
    from awtk_text import Ttf, awtk_width
    ttf = Ttf(os.path.join(work, FONT)); done = []
    for rel in PULLDOWNS:
        path = os.path.join(work, rel)
        if not os.path.exists(path): continue
        def edit(root):
            bar, lab = root.find('view_bar_left'), root.find('label_volume')
            check(bar is not None and lab is not None and lab in bar.children, f'{rel}: unexpected pull-down layout')
            sizes = {lab.get(f'style:{st}:font_size') for st in ('normal', 'disable', 'focused')}
            check(len(sizes) == 1 and None not in sizes, f'{rel}: label_volume font sizes {sizes}')
            need = awtk_width(ttf, VOLUME_MAX, int(sizes.pop()))
            if need <= lab.w: return
            lay = bar.get('children_layout'); m = re.fullmatch(r'default\(r=1,c=0,x=(\d+),s=(\d+)\)', lay or '')
            check(m is not None, f'{rel}: view_bar_left children_layout {lay!r}')
            x0, sp = int(m.group(1)), int(m.group(2))
            gaps = len(bar.children) - 1
            cut = -(-(need - lab.w) // gaps)                  # spacing taken from each gap, rounded up
            check(sp - cut >= 1, f'{rel}: "{VOLUME_MAX}" needs {need} px, the row cannot give that much')
            row = lambda ws, s_: x0 + sum(ws) + s_ * gaps     # where the row ends (fixed children widths)
            ws = [c.w for c in bar.children]
            old_end = row(ws, sp)
            done.append((rel, lab.w, need, sp, sp - cut))
            lab.w = need
            bar.set('children_layout', f'default(r=1,c=0,x={x0},s={sp - cut})')
            new_end = row([c.w for c in bar.children], sp - cut)
            check(new_end <= old_end <= bar.w, f'{rel}: the row now ends at {new_end}, past {old_end}')
        edit_ui(path, edit)
    return done

def apply(work, shs_zip=paths.SHS_ZIP):
    p = os.path.join(work, FONT)
    stock = open(p, 'rb').read()
    check(sha256(stock) == FONT_SHA, f'{FONT} is not the stock V2.1 font (the font step must run first)')
    ib = open(os.path.join(ROOT, INTER_ASSET), 'rb').read()
    check(INTER_SHA is None or sha256(ib) == INTER_SHA, f'{INTER_ASSET}: SHA-256 mismatch (regenerate with tools/font_inter.py)')
    ib = track(ib, INTER_TRACKING)
    print(f'inter: tracking -{INTER_TRACKING} units per glyph (outlines moved left {INTER_TRACKING // 2})')
    new, rep = merge(stock, ib, shs_font(shs_zip))
    r = verify(stock, new, rep)
    write_keep_mode(p, new)
    for rel, w0, w1, s0, s1 in fit_pulldown(work):
        print(f'pulldown: {rel}: label_volume {w0} -> {w1} px ("{VOLUME_MAX}" as AWTK lays it out), row spacing {s0} -> {s1}')
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
