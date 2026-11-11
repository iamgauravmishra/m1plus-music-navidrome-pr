#!/usr/bin/env python3
"""out/preview/tape-mock.png (+ tape-1.png .. tape-4.png, tape-1-portrait.png): the "Tape" page's design mock, a full-screen cassette
Now Playing page in the manner of Sony's cassette screensaver and FiiO's Tape mode. LANDSCAPE: the player is held sideways, the page
is 480 x 320. Approximate PIL mock-up, not AWTK; sample data; four frames (three themes, the control strip of frame 4 is not built).
The page itself is patch/tape.c; docs/modules/tape.md. **The drawing code is tools/tape_art.py**, shared with the build (it makes the
installed pictures from the same functions), so the mock and the device show the same cassette; this file only adds the text, the frames and
the sheet. The device's own frames (the payload run under the emulator) are written by test/pod/tape.py to out/preview/tape-emu-*.png.

The look is a THEME (Normal, Chrome, Metal; the first build ships Normal), the same for every track. Geometry, material and the tape packs
are described in tools/tape_art.py and docs/modules/tape.md. Text is drawn 1:1 with the tree's own font (preview_icons.Side, StbFont).
tape-1-portrait.png is frame 1 rotated 90 degrees clockwise: the 320 x 480 framebuffer image (the landscape top edge becomes the portrait's right
edge: the player is held with its right edge up).

  preview_tape.py [WORKDIR [OUT.png]]   (unpacked release work tree, only its font is read; venv python;
                                          default: the built tree, else the main checkout's; out/preview/tape-mock.png)
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))
from PIL import Image, ImageDraw
import build, paths, preview_icons as PI
from tape_art import *   # the drawing code, shared with the build (tools/tape_art.py)

def strip(im):
    """The control strip a tap fades in (frame 4): a dark translucent overlay across the bottom, REW, pause / play, FF, drawn at 1x."""
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    d.rectangle((0, 256, W, H), fill=(0, 0, 0, 185)); d.line((0, 256, W, 256), fill=(255, 255, 255, 70))
    c = (255, 255, 255, 235); y = 288
    for x in (150, 330):   # REW at 150, FF at 330
        s = -1 if x < 240 else 1
        for dx in (-9, 9): d.polygon([(x + dx - s * 8, y - 12), (x + dx - s * 8, y + 12), (x + dx + s * 8, y)], fill=c)
    d.rectangle((226, y - 12, 233, y + 12), fill=c); d.rectangle((247, y - 12, 254, y + 12), fill=c)   # pause: shown while playing
    im.alpha_composite(ov)

# ---- the frame ---------------------------------------------------------------------------------------------------------------
def bold(s, im, x, y, text, px, rgb, anchor='l'):
    s.text(im, x, y, text, px, rgb, anchor); s.text(im, x + 1, y, text, px, rgb, anchor)

def frame(s, f):
    t = THEMES[f['theme']]
    im = compose(f, t)
    ink, sub = t['ink'], t['sub']
    # written on the index lines
    s.text(im, 40, 49, s.clip(f["title"], 22, 388), 22, ink)
    s.text(im, 40, 70, s.clip(f["artist"], 16, 262), 16, ink)
    s.text(im, 428, 70, t['spec'], 11, t['print'], 'r')   # the tape's bias and equalisation
    if f.get('badge'):   # the sticker on the shell: 1 HI-RES, 2 DSD
        im.alpha_composite(badge_image().transpose(Image.ROTATE_90), BADGE_AT)
        bold(s, im, TEXT['badge']['x'], TEXT['badge']['y'], BADGE_TEXT[f['badge']], 11, BADGE_INK, 'm')
    s.text(im, 40, 89, s.clip(f['album'], 13, 190), 13, sub)
    s.text(im, 428, 89, times_text(f['pos'], f['len']), 12, sub, 'r')
    # the band and the strip below
    bold(s, im, 58, 146, 'A', 54, t['band_ink'], 'm')
    s.text(im, 40, 206, t['model'], 12, t['print'])
    status, px = status_line(s.font, f)
    s.text(im, 428, 206, status, px, sub, 'r')
    if f.get('strip'): strip(im)
    return im

FRAMES = [   # title, artist, album, length s, position s, theme, repeat, playing, cover colour, reel angles
    ('1 Normal theme, near the start, playing', dict(title='So What', artist='Miles Davis', album='Kind of Blue', len=562, pos=14,
        theme='normal', repeat=False, playing=True, cover=(70, 110, 190), ang_s=10, ang_t=35, batt=100, charging=False, vol=42, fmt='MP3 320', clock='21:07')),
    ('2 Chrome theme, mid-track, repeat on', dict(title='Teardrop', artist='Massive Attack', album='Mezzanine', len=330, pos=150,
        theme='chrome', repeat=True, playing=True, cover=(190, 90, 120), ang_s=25, ang_t=50, batt=60, charging=False, vol=30, fmt='FLAC 16/44.1', clock='21:12')),
    ('3 Metal theme, near the end, paused', dict(title='Weightless', artist='Marconi Union', album='Weightless (Hi-Res)', len=480, pos=452,
        theme='metal', repeat=False, playing=False, cover=(60, 140, 150), ang_s=40, ang_t=15, batt=20, charging=True, vol=18, fmt='FLAC 24/96', badge=1, clock='22:48')),
    ('4 Chrome theme with the tap control strip', dict(title='Orinoco Flow', artist='Enya', album='Watermark', len=266, pos=60,
        theme='chrome', repeat=False, playing=True, cover=(120, 110, 180), ang_s=30, ang_t=5, strip=True, batt=80, charging=False, vol=55, fmt='WAV 16/44.1', clock='08:30')),
]

def main():
    work = sys.argv[1] if len(sys.argv) > 1 else next(p for p in (os.path.join(paths.WORK, 'mod-release'), os.path.join(paths.MAIN, 'work', 'mod-release')) if os.path.isdir(p))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(build.ROOT, 'out', 'preview', 'tape-mock.png')
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    s = PI.Side(work, True)
    frames = [(t, frame(s, dict(f))) for t, f in FRAMES]
    base = os.path.splitext(out)[0].replace('-mock', '')
    for i, (_, im) in enumerate(frames, 1): im.convert('RGB').save('%s-%d.png' % (base, i), optimize=True)
    frames[0][1].convert('RGB').rotate(-90, expand=True).save(base + '-1-portrait.png', optimize=True)   # the 320 x 480 framebuffer, 90 degrees clockwise
    pad, lab, cols = 12, 22, 2
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new('RGB', (pad + cols * (W + pad), pad + rows * (lab + H + pad)), (0x2A,) * 3); d = ImageDraw.Draw(sheet)
    for i, (t, im) in enumerate(frames):
        x = pad + (i % cols) * (W + pad); y = pad + (i // cols) * (lab + H + pad)
        d.text((x, y), t, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, y + lab))
    sheet.save(out, optimize=True); print('wrote', out, sheet.size)

if __name__ == '__main__':
    main()
