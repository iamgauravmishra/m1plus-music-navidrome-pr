#!/usr/bin/env python3
"""out/preview/vinyl-final.png (+ vinyl-final-j1.png, -j2.png): the approved Vinyl Mode design (docs/modules/vinyl.md), playing and paused, drawn by
tools/vinyl_art.py `design` (the code the build's pictures and test/pod/vinyl.py use) with the tree's own font (preview_icons.Side, StbFont). Sample data and a
generated sample cover. The emulated device frames are test/pod/vinyl.py's out/preview/vinyl-emu-*.png.

  preview_vinyl.py [WORKDIR [OUT.png]]
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw
import build, paths, preview_icons as PI, vinyl_art

# the chosen look: grey 46 plinth, background grain 6, a dark record (sheen 0.22), round keys; the sample track
J = dict(cover='sunset', title='Midnight City', artist='M83', album='Hurry Up', len=243, pos=200, angle=120, fmt='FLAC', batt=80, charging=False, vol=42, clock='21:07')
FRAMES = [('J1  Playing', dict(J, playing=True)), ('J2  Paused', dict(J, playing=False))]


def main():
    work = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else next(p for p in (os.path.join(paths.WORK, 'mod-release'), os.path.join(paths.MAIN, 'work', 'mod-release')) if os.path.isdir(p))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'vinyl-final.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    s = PI.Side(work, True)
    base = os.path.splitext(out)[0]
    frames = []
    for title, f in FRAMES:
        im = vinyl_art.design(s, f); frames.append((title, im))
        im.convert('RGB').save('%s-%s.png' % (base, title.split()[0].lower()), optimize=True)
    pad, lab = 12, 22
    sheet = Image.new('RGB', (pad + len(frames) * (vinyl_art.W + pad), pad + lab + vinyl_art.H + pad), (0x2A,) * 3); d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(frames):
        x = pad + i * (vinyl_art.W + pad)
        d.text((x, pad), t, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, pad + lab))
    sheet.save(out, optimize=True); print('wrote', out, sheet.size)


if __name__ == '__main__':
    main()
