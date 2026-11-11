#!/usr/bin/env python3
"""out/peek/vinyl-themes/: mocks of Vinyl Mode's colour themes (plinth: Graphite, White; record: black, smoke, red, clear, tinted from the cover), drawn by
tools/vinyl_art.py `design` with a theme (`use`) and a record style. Mock only: the installed pictures stay the Graphite look. Writes one PNG a frame, themes.png
(3 plinths x playing / paused), records.png (the record colours side by side) and prints the PNG size of each theme's base layer and the cover tints.

  preview_vinyl_themes.py [WORKDIR [OUTDIR]]
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw
import build, paths, preview_icons as PI, vinyl_art as V
from preview_vinyl import J


def green_cover(n=300):
    """A synthetic forest-green cover: a deep gradient, a pale moon and two layered hills."""
    im = V.stops((n, n), [(0x0A, 0x2A, 0x1E), (0x2E, 0x7A, 0x4E), (0x0C, 0x24, 0x1A)])
    d = ImageDraw.Draw(im)
    d.ellipse((n * 0.58, n * 0.14, n * 0.80, n * 0.36), fill=(0xE8, 0xF2, 0xC8))
    for k, (y, c) in enumerate(((0.62, (0x14, 0x4A, 0x34)), (0.76, (0x0A, 0x2C, 0x20)))):
        pts = [(x * n / 20, n * (y + 0.05 * ((x * 7 + k * 5) % 5 - 2) / 2)) for x in range(21)]
        d.polygon(pts + [(n, n), (0, n)], fill=c)
    return im


def red_cover(n=300):
    """A bold red cover with a cream disc and a black bar (a poster look)."""
    im = Image.new('RGB', (n, n), (0xC8, 0x2A, 0x24)); d = ImageDraw.Draw(im)
    d.ellipse((n * 0.22, n * 0.22, n * 0.78, n * 0.78), fill=(0xF2, 0xE6, 0xD0)); d.rectangle((0, n * 0.84, n, n * 0.92), fill=(0x16, 0x10, 0x10))
    return im


COVERS = [('blue', V.cover('blue')), ('sunset', V.cover('sunset')), ('green', green_cover())]
STATE = dict(J, cover='sunset')


def frame(s, theme, playing=True, rec=None, cover='sunset'):
    V.use(theme)
    return V.design(s, dict(STATE, playing=playing, rec=rec, cover=cover))


def labelled(items, cols, scale=1.0, pad=12, lab=22):
    """A contact sheet of (label, image) in `cols` columns."""
    w, h = items[0][1].size; rows = -(-len(items) // cols)
    sheet = Image.new('RGB', (pad + cols * (w + pad), pad + rows * (h + lab + pad)), (0x24,) * 3); d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(items):
        x, y = pad + (i % cols) * (w + pad), pad + (i // cols) * (h + lab + pad)
        d.text((x, y + 2), t, fill=(0xCC,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, y + lab))
    if scale != 1.0: sheet = sheet.resize((int(sheet.width * scale), int(sheet.height * scale)), Image.LANCZOS)
    return sheet


def tinted(cv):
    t = V.cover_tint(cv)
    return (V.tint_style(t), t) if t else (None, None)


def main():
    work = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else next(p for p in (os.path.join(paths.WORK, 'mod-release'), os.path.join(paths.MAIN, 'work', 'mod-release')) if os.path.isdir(p))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'peek', 'vinyl-themes')
    os.makedirs(out, exist_ok=True)
    s = PI.Side(work, True)

    def save(name, im): im.convert('RGB').save(os.path.join(out, name + '.png'), optimize=True)

    themes = []
    for th in V.THEME_NAMES:
        for playing in (True, False):
            im = frame(s, th, playing); n = '%s-%s' % (th, 'playing' if playing else 'paused'); save(n, im); themes.append((n, im))
    save('themes', labelled(themes[0::2] + themes[1::2], 3))

    records = []
    plan = [('graphite', 'black', None)]
    for name, cv in COVERS + [('red', red_cover())]:
        st, t = tinted(cv)
        print('tint', name, '#%02X%02X%02X' % t if t else None)
        if st: plan.append(('graphite', 'tint-' + name, (st, cv)))
    plan += [('white', 'black', None), ('white', 'tint-blue', 'tint-blue')]
    cov = dict(COVERS, red=red_cover())
    for th, name, spec in plan:
        if isinstance(spec, tuple): style, cv = spec
        elif spec and spec.startswith('tint-'): cv = cov[spec[5:]]; style = V.tint_style(V.cover_tint(cv))
        else: style, cv = None, cov['sunset']
        n = '%s-rec-%s' % (th, name); im = frame(s, th, True, style, cv); save(n, im); records.append((n, im))
        if n == 'graphite-rec-tint-blue':
            tm = V.LAST_T[0].resize((V.W, V.H), Image.BOX).crop((0, V.REC_C[1] - V.REC_R, V.REC_C[0] + V.REC_R, V.REC_C[1] + V.REC_R)); tm.save(os.path.join(out, 'record-map.png'), optimize=True)
            print('record map', tm.size, len(_png(tm)), 'bytes')
    save('records', labelled(records, 5))

    for th in V.THEME_NAMES:
        V.use(th); ims = V.images()
        print(th, 'PNG bytes', {k: len(_png(v)) for k, v in ims.items() if k in ('vinyl_base', 'vinyl_keys', 'vinyl_arm', 'vinyl_armsh', 'vinyl_cap')})
    V.use('graphite')


def _png(im):
    import io
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True); return b.getvalue()


if __name__ == '__main__':
    main()
