#!/usr/bin/env python3
"""out/preview/peq.png: Settings (its EQ row showing the preset that plays) and the Equalizer page (patch/peq_ui.c, docs/modules/peq.md): the switch on with presets on the card and
one playing and the bottom card under it (the 10-Band EQ link with its curve name, the Presets link with its count), the empty state (the switch off, 10-Band EQ checked, the hint), and the Presets page (Download from AutoEq, the AutoEq files, On Card). Drawn from a finished tree's own ui files, strings and font. Approximate (PIL, not AWTK).

Usage: uv run python -I tools/preview/preview_peq.py WORKDIR [OUT.png]     (en_US; default out/preview/peq.png)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image, ImageDraw
import awtk_ui, build, preview_icons as PI, preview_settings as PS, pod_pages as P

RAW = os.path.join('rootfs', 'release', 'assets', 'default', 'raw')
PRESETS = ['AKG K371.txt', 'Sennheiser HD 600.txt', 'Sony WH-1000XM4 (ANC on).txt', 'Moondrop Blessing 2.txt']
# The Presets page's files: (name, grey line, stamped by AutoEq) as patch/peqlib.c lists them (AutoEq files first, each section sorted by name)
LIB = [('Moondrop Blessing 2', 'Rtings · In-ear', True), ('Sennheiser HD 600', 'oratory1990 · Over-ear', True), ('Sony WH-1000XM4 (ANC on)', 'oratory1990 · Over-ear', True),
       ('AKG K371', 'On card', False), ('My Own Curve', 'On card', False)]


def peq_page(s, presets, playing, on, total=None, curve='Rock'):
    """The page as patch/peq_ui.c leaves it: the asset's tree with the preset rows the card has shown and named, each shown row of the picker card on the piece
    pod_settings.peq_pieces(n) says (the last one without its hairline), the check on the row that plays (1 10-Band EQ with its grey curve name, 2.. the presets) and the hint when there is none."""
    root = awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', P.PEQ_PAGE.key + '.bin'), 'rb').read())
    n = len(presets)
    for i in range(1, 2 + n):
        row = root.find(f'pod_row{i}')
        if i >= 2:
            row.set('visible', 'true'); root.find(f'pod_label{i}').set('text', presets[i - 2][:-4])   # shown without the .txt
        piece = PS.ST.peq_pieces(n)[i - 1]
        for st in ('normal', 'over', 'focused', 'disable'): row.set(f'style:{st}:bg_image', f'pod_cd_{piece}')
        row.set('style:pressed:bg_image', f'pod_cd_{piece}_down')
        if piece in ('single', 'bot'): row.children = [c for c in row.children if c.name != 'pod_hair']
    if not n: root.find('pod_note1').set('visible', 'true'); root.find('pod_gap0').set('visible', 'false')   # (the hint is the space before the bottom card)
    count = f'pod_value{P.PEQ_ROWS + 3}'   # the Presets row's grey count: every .txt file on the card (the 10-Band EQ link row is the one before it)
    st = {'switches': {'pod_switch0': on}, 'shown': {f'pod_check{playing}'}, 'values': {count: str(n if total is None else total), 'pod_value1': curve, f'pod_value{P.PEQ_ROWS + 2}': curve}}
    return PS.draw_page(s, P.PEQ_PAGE.key, state=st, root=root).convert('RGB')


def peqlib_page(s, files):
    """The Presets page as patch/peqlib.c leaves it: the AutoEq files in the first slots under their header, the others in the On Card slots under theirs, the rows named, with their grey lines, on the
    section's tall pieces (single / top / mid / bot) and a hairline under every row but the section's last; a section with no file has no header."""
    root = awtk_ui.parse(open(os.path.join(s.tree, RAW, 'ui', P.PEQLIB_PAGE.key + '.bin'), 'rb').read())
    for sec, first, mine in (('pod_sec0', 1, [f for f in files if f[2]]), ('pod_sec1', P.PEQ_ROWS + 1, [f for f in files if not f[2]])):
        if mine: root.find(sec).set('visible', 'true')
        for j, (name, sub, _) in enumerate(mine):
            row = root.find(f'pod_row{first + j}')
            row.set('visible', 'true'); root.find(f'pod_label{first + j}').set('text', name); root.find(f'pod_sub{first + j}').set('text', sub)
            piece = 'single' if len(mine) == 1 else 'top' if j == 0 else 'bot' if j == len(mine) - 1 else 'mid'
            for st in ('normal', 'over', 'focused', 'disable'): row.set(f'style:{st}:bg_image', f'pod_cdl_{piece}')
            row.set('style:pressed:bg_image', f'pod_cdl_{piece}_down')
            if piece in ('single', 'bot'): row.children = [c for c in row.children if c.name != 'pod_hair']
    return PS.draw_page(s, P.PEQLIB_PAGE.key, state={}, root=root, full=True).convert('RGB')


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    work = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'peq.png')
    s = PI.Side(work, True, 'en_US'); s.mark = lambda *a: None
    eq = next(i for i, r in enumerate(P.SETTINGS_PAGE.rows) if r.action == P.ACT_PEQ)
    st = {'values': dict(PS.STATE['m1plus_settings']['values'], **{f'pod_value{eq}': PRESETS[1][:-4]})}
    panels = [('Settings: EQ shows the preset that plays', PS.draw_page(s, 'm1plus_settings', full=True, state=st).convert('RGB')),
              ('Equalizer: a preset playing', peq_page(s, PRESETS, 3, True)),
              ('Equalizer: no presets on the card', peq_page(s, [], 1, False)),
              ('Presets: the card\'s files', peqlib_page(s, LIB))]
    pad = 12
    wid = sum(im.width for _, im in panels) + pad * (len(panels) + 1)
    hei = max(im.height for _, im in panels) + 44 + pad
    out = Image.new('RGB', (wid, hei), (0x2A,) * 3); d = ImageDraw.Draw(out)
    x = pad
    for title, im in panels:
        d.text((x, 24), title, fill=(0xAA,) * 3, font=PI.ANN); out.paste(im, (x, 44)); x += im.width + pad
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    out.save(out_path, optimize=True); print('wrote', out_path, out.size)


if __name__ == '__main__':
    main()
