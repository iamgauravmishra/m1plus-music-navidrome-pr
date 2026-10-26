#!/usr/bin/env python3
"""Make assets/fonts/Inter-m1plus.ttf, the Inter subset that tools/mod_font.py merges into default.ttf.
docs/ui.md. Offline tool (needs fontTools); the build only reads its committed output.

Input: the official Inter 4.1 release zip (pinned by SHA-256, read in memory, nothing extracted):
  https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip
Steps, all with fontTools:
  1. take the static TTF of the chosen weight (extras/ttf/Inter-<Weight>.ttf, pinned too)
  2. keep the code points of mod_font.INTER_RANGES that Inter has; bake the tnum feature into the cmap
     for the digits (0-9 -> zero.tf ... nine.tf), since AWTK applies no OpenType features
  3. drop hinting and every layout table (AWTK uses neither), decompose composites (stb_truetype
     mis-scales scaled components and asserts on point-matched ones), prune unused glyphs
  4. scale the outlines to EM units per em (mod_font.INTER_EM, in the stock font's 256-unit grid)
  5. one Unicode format-4 cmap (0/3 and 3/1), as the stock font; timestamps kept (deterministic)

Usage: font_inter.py INTER_ZIP [--weight Regular|Medium] [--em N] [--out assets/fonts/Inter-m1plus.ttf]
"""
import argparse, hashlib, io, os, sys, zipfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mod_font

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP_URL = 'https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip'
ZIP_SHA = '9883fdd4a49d4fb66bd8177ba6625ef9a64aa45899767dde3d36aa425756b11e'
MEMBERS = {'Regular': '40d692fce188e4471e2b3cba937be967878f631ad3ebbbdcd587687c7ebe0c82',
           'Medium': '97ad806f526e41546d46365bb3a393145f75b7b1568913db74549ad8b8dba872'}
LICENSE_SHA = '262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a'   # LICENSE.txt in the zip
TNUM = {c: n + '.tf' for c, n in zip(range(0x30, 0x3A), ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'))}

def sha256(b): return hashlib.sha256(b).hexdigest()

def member(z, name, want):
    b = z.read(name)
    if sha256(b) != want: raise SystemExit(f'{name}: SHA-256 mismatch')
    return b

def build(ttf, em):
    from fontTools.ttLib import TTFont
    from fontTools.ttLib.scaleUpem import scale_upem
    from fontTools import subset
    from fontTools.pens.recordingPen import DecomposingRecordingPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib.tables._c_m_a_p import cmap_format_4

    f = TTFont(io.BytesIO(ttf), recalcTimestamp=False)
    best = f.getBestCmap()
    cps = sorted(c for c in best if mod_font.in_ranges(c, mod_font.INTER_RANGES))
    names = set(f.getGlyphOrder())
    cmap = {c: best[c] for c in cps}
    for c, g in TNUM.items():
        assert g in names, f'no {g}'
        cmap[c] = g
    # one Unicode cmap, as the stock font (BMP only)
    tabs = []
    for pid, eid in ((0, 3), (3, 1)):
        t = cmap_format_4(4); t.platformID, t.platEncID, t.language = pid, eid, 0; t.cmap = dict(cmap); tabs.append(t)
    f['cmap'].tables = tabs

    def prune(font):
        o = subset.Options()
        o.layout_features = []; o.hinting = False; o.glyph_names = True; o.notdef_outline = True
        o.name_IDs = ['*']; o.name_languages = ['*']; o.name_legacy = True; o.recalc_bounds = True
        o.prune_unicode_ranges = False; o.legacy_kern = False
        o.drop_tables += ['GDEF', 'GPOS', 'GSUB', 'STAT', 'gasp', 'DSIG', 'meta', 'kern']
        s = subset.Subsetter(o); s.populate(unicodes=cps); s.subset(font)

    prune(f)
    glyf, gs = f['glyf'], f.getGlyphSet()
    flat = {}
    for name in f.getGlyphOrder():
        if glyf[name].isComposite():
            rp = DecomposingRecordingPen(gs); gs[name].draw(rp)
            pen = TTGlyphPen(None); rp.replay(pen); flat[name] = pen.glyph()
    for name, g in flat.items(): glyf[name] = g
    prune(f)                                     # drop components nothing maps to any more
    scale_upem(f, em)
    for name in f.getGlyphOrder():
        g = f['glyf'][name]; assert not g.isComposite(), name
    out = io.BytesIO(); f.save(out)
    return out.getvalue(), len(cps), len(f.getGlyphOrder()), len(flat)

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('zip'); ap.add_argument('--weight', default=mod_font.INTER_WEIGHT, choices=sorted(MEMBERS))
    ap.add_argument('--em', type=int, default=mod_font.INTER_EM, help=f'Inter em in stock font units (default {mod_font.INTER_EM})')
    ap.add_argument('--out', default=os.path.join(ROOT, mod_font.INTER_ASSET))
    ap.add_argument('--license-out', help='also write the zip\'s LICENSE.txt (the OFL) here')
    a = ap.parse_args()
    if sha256(open(a.zip, 'rb').read()) != ZIP_SHA: raise SystemExit(f'{a.zip}: not the pinned Inter 4.1 release ({ZIP_URL})')
    with zipfile.ZipFile(a.zip) as z:
        ttf = member(z, f'extras/ttf/Inter-{a.weight}.ttf', MEMBERS[a.weight])
        lic = member(z, 'LICENSE.txt', LICENSE_SHA)
    data, ncp, ng, ndec = build(ttf, a.em)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    open(a.out, 'wb').write(data)
    if a.license_out: open(a.license_out, 'wb').write(lic)
    print(f'{a.out}: Inter {a.weight} 4.1, em {a.em}/256, {ncp} code points, {ng} glyphs ({ndec} decomposed), '
          f'{len(data)} bytes, sha256 {sha256(data)}')

if __name__ == '__main__': main()
