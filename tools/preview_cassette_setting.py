#!/usr/bin/env python3
"""out/preview/cassette-setting.png: Customize (with its new Cassette Mode row) and the Cassette Mode page with the Cassette Theme row in its three states (Normal, Chrome,
Metal), drawn from a finished tree's own ui files, strings and font (docs/modules/settings.md). Approximate (PIL, not AWTK).

Usage: venv/bin/python -I tools/preview_cassette_setting.py WORKDIR [OUT.png]     (en_US; default out/preview/cassette-setting.png)
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw
import build, paths, preview_icons as PI, pod_pages as P


def main():
    if len(sys.argv) < 2: sys.exit(__doc__)
    work = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'cassette-setting.png')
    s = PI.Side(work, True, 'en_US'); s.mark = lambda *a: None
    panels = [('Customize (8 rows, scrolls)', PI.pod_page(s, 'm1plus_customize', 8).convert('RGB'))]
    for v in P.CTHEME_VALUES:
        panels.append((f'Cassette Mode > Cassette Theme: {v}', PI.pod_page(s, 'm1plus_tapeset', 1, values={'pod_value0': v}).convert('RGB')))
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
