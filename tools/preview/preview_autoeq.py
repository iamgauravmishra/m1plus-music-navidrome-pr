#!/usr/bin/env python3
"""Approximate PIL mock-up of the AutoEq download page (patch/autoeq.c, docs/modules/peq.md "AutoEq download"): its own window (ui/m1plus_autoeq.bin) with Radio's search level's top (the glass
Back and Now Playing's disc on the bar, the title, the field at y 56 under it, the page's width, no round X), the list from y 98 (Radio's search list top under the bar), results with a
"Source · Kind · Target" and a download glyph, a ring and "Downloading…", a check and "Saved to EQ · Tap to use". Not pixel-exact AWTK (the payload draws the glyphs itself; here they
are the tree's Lucide images of the same shapes).

  preview_autoeq.py WORKDIR OUT.png [--lang CODE]

Panels: typing "hd 6" (keyboard up), one result downloading, one saved and one in use, the list coming (first open), a failure of the list ("Try Again"). Each panel is also written as <stem>-<name>.png.
"""
import argparse, os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pod_keyboard as PK
import pod_search as PS
import preview_icons as PI
import preview_keyboard as PKV
import preview_radio as PR
import preview_search as PSR

W, H, SS, BAR, D = PKV.W, PKV.H, PKV.SS, PKV.BAR, PS.D
NAV = PR.NAV                       # the glass bar (50)
LIST_Y = 98                        # AE_LIST_Y of patch/autoeq.c: the bar and Radio's search list top (48) below it
TITLE_X, TITLE_END = 58, 260       # the navbar's title: from the disc, to Now Playing's button
ICON_GREY = (0xAA,) * 3
ROW_H, TEXT_X, TITLE_Y, SUB_Y = 52, 16, 3, 29   # AE_ROW_H, AE_TEXT_X, AE_TITLE_Y, AE_SUB_Y of patch/autoeq.c
# (title, source, kind, state): state 0 not saved, 1 downloading, 2 saved, 3 in use
ROWS = [('Sennheiser HD 600', 'oratory1990 · Over-ear', 0), ('Sennheiser HD 600', 'Rtings · Over-ear · Bruel & Kjaer 5128', 0), ('Sennheiser HD 650', 'oratory1990 · Over-ear', 0),
        ('Sennheiser HD 6XX', 'oratory1990 · Over-ear', 0), ('Sennheiser HD 660S', 'oratory1990 · Over-ear', 0)]


def tinted(im, rgb):
    out = Image.new('RGBA', im.size, rgb + (255,)); out.putalpha(im.getchannel('A')); return out


def navbar(s, page, title):
    """Radio's search level's bar: Back (7, 44 wide) and Now Playing's disc (260, 60 wide), the title from x 58 to 260, centred on the bar."""
    for name, bx, bw in (('ah_nav_back', 7, 44), ('ah_nav_np', 260, 60)):
        g = s.img(name); page.alpha_composite(g, (bx + (bw - g.width) // 2, (NAV - g.height) // 2))
    tpx = PI.title_px(s.tree)
    s.text(page, TITLE_X, NAV / 2, s.clip(title, tpx, TITLE_END - TITLE_X), tpx, (255, 255, 255))


def draw_rows(s, page, rows, bottom, strings):
    down = tinted(s.img('pod_ci_download'), ICON_GREY)
    check = s.img('pod_check')
    for i, (title, sub, state) in enumerate(rows):
        y = LIST_Y + i * ROW_H
        if y + ROW_H > bottom: break
        def paint(d, k, y=y):
            d.line(k(TEXT_X, y + ROW_H - 1, D['SE_SEP_END'], y + ROW_H - 1), fill=(0x22, 0x22, 0x22, 255), width=SS)
            if state == 1:   # the ring: a faint track and an arc of three quarters
                cx, cy, r = 295, y + ROW_H / 2, 9
                d.ellipse(k(cx - r, cy - r, cx + r, cy + r), outline=(0xAA, 0xAA, 0xAA, 70), width=2 * SS)
                d.arc(k(cx - r, cy - r, cx + r, cy + r), start=-60, end=210, fill=ICON_GREY + (255,), width=2 * SS)
        page.alpha_composite(PKV.layer(paint))
        if state == 0: page.alpha_composite(down, (284 - 1, int(y + ROW_H / 2 - 12)))
        if state >= 2: page.alpha_composite(check, (284, int(y + ROW_H / 2 - 10)))
        text = {1: strings['Downloading…'], 2: strings['Saved to EQ · Tap to use'], 3: strings['In use']}.get(state, sub)
        end = 276
        s.text(page, TEXT_X, y + TITLE_Y + 12, s.clip(title, 21, end - TEXT_X), 21)
        s.text(page, TEXT_X, y + SUB_Y + 10, s.clip(text, 18, end - TEXT_X), 18, PSR.rgb(PS.SUB_RGB))


def screen(s, root, kb, text, rows, keyboard, strings, status=None, hint=False):
    im = Image.new('RGBA', (W, H), (0, 0, 0, 255))
    PI.status_bar(s, im)
    page = Image.new('RGBA', (W, H - BAR), (0, 0, 0, 255))   # the window: from the bar down
    navbar(s, page, strings['AutoEq'])
    PR.draw_field(s, page, root, 0, text, caret=keyboard, hint=strings['Search'])
    draw_rows(s, page, rows, H - BAR - (PK.KB_H if keyboard else 0), strings)
    if status: s.text(page, W / 2, 165, status, 20, anchor='m')
    if hint: s.text(page, W / 2, LIST_Y + 96 + 10, strings['Try Again'], 18, PSR.rgb(PS.SUB_RGB), anchor='m')
    im.alpha_composite(page, (0, BAR))
    if keyboard: PKV.keyboard(kb, im, 'abc', None)
    return im


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('workdir'); ap.add_argument('out'); ap.add_argument('--lang', default='en_US')
    a = ap.parse_args()
    s = PI.Side(a.workdir, True, a.lang)
    root, kb = PR.field_tree(s, 'm1plus_autoeq'), PKV.Page(s)
    keys = ('AutoEq', 'Search', 'Downloading…', 'Saved to EQ · Tap to use', 'In use', 'Try Again', 'Downloading List…', 'No Wi-Fi')
    strings = {k: s.strings.get(k, k) for k in keys}
    saved = [(r[0], r[1], 2 if i == 0 else r[2]) for i, r in enumerate(ROWS)]
    busy = [(r[0], r[1], 1 if i == 0 else r[2]) for i, r in enumerate(ROWS)]
    using = [(r[0], r[1], 3 if i == 0 else 2 if i == 1 else r[2]) for i, r in enumerate(ROWS)]
    panels = [('typing', 'Typing "hd 6"', screen(s, root, kb, 'hd 6', ROWS, True, strings)),
              ('downloading', 'A result downloading', screen(s, root, kb, 'hd 6', busy, False, strings)),
              ('saved', 'Saved to EQ', screen(s, root, kb, 'hd 6', saved, False, strings)),
              ('inuse', 'In use, another saved', screen(s, root, kb, 'hd 6', using, False, strings)),
              ('list', 'First open: the list', screen(s, root, kb, '', [], False, strings, status=strings['Downloading List…'])),
              ('failed', 'The list failed', screen(s, root, kb, '', [], False, strings, status=strings['No Wi-Fi'], hint=True))]
    base, ext = os.path.splitext(a.out)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    pad, lab = 12, 20
    sheet = Image.new('RGB', (len(panels) * (W + pad) + pad, H + lab + 2 * pad), (0x2A, 0x2A, 0x2A)); d = ImageDraw.Draw(sheet)
    for i, (name, title, im) in enumerate(panels):
        x = pad + i * (W + pad)
        d.text((x, pad), title, fill=(0xAA,) * 3, font=PI.ANN); sheet.paste(im.convert('RGB'), (x, pad + lab))
        PI.save_compact(im.convert('RGB'), f'{base}-{name}{ext}', colors=256)
        print('wrote', f'{base}-{name}{ext}')
    PI.save_compact(sheet, a.out, colors=256)
    print('wrote', a.out, sheet.size)


if __name__ == '__main__': main()
