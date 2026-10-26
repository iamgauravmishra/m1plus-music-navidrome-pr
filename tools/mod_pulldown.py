#!/usr/bin/env python3
"""The pull-down control centre's text one step smaller (V2.1gB, docs/ui.md).

ui/dialog/dropdown_dialog.bin (default and theme1; the dialog has no page theme, styles/ has no
dropdown_dialog.bin) carries three kinds of text, all with inline font sizes:

  label_volume   the volume number in the pull-down's own status bar       20 -> 18 (all three states)
  bar_dclock     its clock                                                  20 -> 18
  label_*        the eight tile captions (Wi-Fi, Bluetooth, Buttons lock, gain, USB mode, output,
                 Playback / System Setting), word-wrapped in 57 x 40 boxes  18 -> 16 (normal),
                                                                            16 -> 14 (disable, focused)

pgbar_battery shows no number there (show_text false, stock), the slider and the icons have no text.
Nothing moves: every box keeps its geometry and vertical alignment (stock: middle, or AWTK's
default, which centres too), so the smaller text stays centred in it. The tool measures what it
sets with the shared text model (awtk_text.StbText: truncated advances + 1 px per glyph) in the
tree's own font, so it must run after the font step:

  - "100" (the widest volume) must fit label_volume; when it fits the stock 30 px box, the font
    step's widening (tools/mod_font.py fit_pulldown: 30 -> 33 px, the row's spacing 4 -> 3) is
    undone, so the row is back to stock geometry;
  - "12:59 PM" (the widest clock) must fit bar_dclock;
  - every tile caption in English and Simplified Chinese (strings/en_US.bin, zh_CN.bin, the keys
    demo sets @0x4743c8..) must wrap into the 40 px box (lines x font size), greedy word wrap as
    AWTK breaks lines; the other languages are reported (several overflow already in stock).

Usage: mod_pulldown.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import argparse, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir, edit_ui
from awtk_text import Ttf, awtk_width

RAW = 'rootfs/release/assets/{theme}/raw'
THEMES = ('default', 'theme1')
DIALOG = 'ui/dialog/dropdown_dialog.bin'
FONT = 'rootfs/release/assets/default/raw/fonts/default.ttf'
STATES = ('normal', 'disable', 'focused')
# old -> new inline font sizes
VOLUME = {20: 18}
CLOCK = {20: 18}
TILE = {18: 16, 16: 14}
TILES = ('label_wifi', 'label_bt', 'label_lock', 'label_gain', 'label_usbmode', 'label_outputway',
         'label_playset', 'label_sysset')
# the tile captions' string keys (demo @0x4743c8..0x474b70: widget_set_tr_text on the labels above)
TILE_KEYS = ('wifiset_wifi', 'wifiset_bt', 'system_keylock', 'gain_high', 'gain_low', 'sset_outputway',
             'playset', 'sysset', 'usbmode_audio', 'usbmode_dac', 'usbmode_storge')
MUST_FIT = ('en_US', 'zh_CN')
VOLUME_MAX, CLOCK_MAX = '100', '12:59 PM'
STOCK_VOLUME_W, STOCK_SPACING = 30, 4        # stock label_volume width and view_bar_left spacing


def check(ok, msg):
    if not ok: raise SystemExit(f'mod_pulldown: {msg}')


def strings(path, keys):
    """key -> text from an AWTK strings/*.bin (a table of NUL-terminated key, value pairs)."""
    d = open(path, 'rb').read(); out = {}
    for k in keys:
        i = d.find(b'\0' + k.encode() + b'\0')
        if i < 0: continue
        j = i + len(k) + 2
        out[k] = d[j:d.index(b'\0', j)].decode('utf-8')
    return out


def wrap(ttf, text, px, width):
    """Lines of a word-wrapped label: break after spaces, before and after CJK characters, and
    inside a word that is wider than the box on its own (AWTK's line breaker does the same)."""
    toks, cur = [], ''
    for ch in text:
        if ch == ' ': toks.append(cur + ' '); cur = ''
        elif ord(ch) >= 0x2e80:
            if cur: toks.append(cur); cur = ''
            toks.append(ch)
        else: cur += ch
    if cur: toks.append(cur)
    lines, line = [], ''
    for t in toks:
        if awtk_width(ttf, (line + t).rstrip(), px) <= width: line += t; continue
        if line.strip(): lines.append(line.rstrip())
        line = ''
        while awtk_width(ttf, t.rstrip(), px) > width:
            k = len(t)
            while k > 1 and awtk_width(ttf, t[:k], px) > width: k -= 1
            lines.append(t[:k]); t = t[k:]
        line = t
    if line.strip(): lines.append(line.rstrip())
    return lines


def resize(w, table, states=STATES):
    """Every state that sets a font size gets the table's smaller one; returns {old: new}."""
    done = {}
    for st in states:
        v = w.get(f'style:{st}:font_size')
        if v is None: continue
        check(int(v) in table, f'{w.name}: unexpected {st} font size {v}')
        w.set(f'style:{st}:font_size', str(table[int(v)])); done[int(v)] = table[int(v)]
    check(done, f'{w.name}: no inline font size')
    return done


def edit(root, ttf, texts, report):
    shape = [(w.type, w.name, w.x, w.y, w.w, w.h) for w in root.walk()]
    bar, vol, clock = root.find('view_bar_left'), root.find('label_volume'), root.find('bar_dclock')
    check(bar is not None and vol in bar.children and clock is not None, 'unexpected pull-down layout')
    report.append(f'label_volume {resize(vol, VOLUME)}')
    px = int(vol.get('style:normal:font_size'))
    need = awtk_width(ttf, VOLUME_MAX, px)
    m = re.fullmatch(r'default\(r=1,c=0,x=(\d+),s=(\d+)\)', bar.get('children_layout') or '')
    check(m, f'view_bar_left children_layout {bar.get("children_layout")!r}')
    x0, sp = int(m.group(1)), int(m.group(2))
    if need <= STOCK_VOLUME_W and (vol.w, sp) != (STOCK_VOLUME_W, STOCK_SPACING):
        gaps = len(bar.children) - 1
        end = lambda: x0 + sum(c.w for c in bar.children) + gaps * int(re.search(r's=(\d+)', bar.get('children_layout')).group(1))
        before = end()
        report.append(f'label_volume {vol.w} -> {STOCK_VOLUME_W} px, spacing {sp} -> {STOCK_SPACING} (stock: "{VOLUME_MAX}" is {need} px at {px})')
        vol.w = STOCK_VOLUME_W
        bar.set('children_layout', f'default(r=1,c=0,x={x0},s={STOCK_SPACING})')
        check(end() == before, 'the row end moved')
    check(need <= vol.w, f'"{VOLUME_MAX}" needs {need} px at {px}, label_volume is {vol.w}')
    report.append(f'bar_dclock {resize(clock, CLOCK, ("normal",))}')
    cpx = int(clock.get('style:normal:font_size')); cw = awtk_width(ttf, CLOCK_MAX, cpx)
    check(cw <= clock.w, f'"{CLOCK_MAX}" needs {cw} px at {cpx}, the clock box is {clock.w}')
    report.append(f'"{VOLUME_MAX}" {need}/{vol.w} px, "{CLOCK_MAX}" {cw}/{clock.w} px')
    for name in TILES:
        w = root.find(name); check(w is not None and w.type == 'label', f'{name} missing')
        spx = int(w.get('style:normal:font_size'))
        changed = resize(w, TILE)
        tpx = int(w.get('style:normal:font_size'))
        fits = lambda t, px: len(wrap(ttf, t, px, w.w)) * px <= w.h
        for lang in MUST_FIT:
            for k, t in texts[lang].items():
                check(fits(t, tpx), f'{lang} {k} {t!r} does not fit {w.w}x{w.h} at {tpx}: {wrap(ttf, t, tpx, w.w)}')
        if name == TILES[0]:   # the boxes are all 57 x 40: count once
            over = lambda px: sorted(f'{l}:{k}' for l, kv in texts.items() for k, t in kv.items() if not fits(t, px))
            report.append(f'tile captions over 40 px: {len(over(spx))} at {spx} px (stock), {len(over(tpx))} at {tpx} px '
                          f'(none in {"/".join(MUST_FIT)}); still over: {", ".join(over(tpx))}')
    report.append(f'tiles {changed}')
    after = [(w.type, w.name, w.x, w.y, w.w, w.h) for w in root.walk()]
    moved = [a for a, b in zip(shape, after) if a != b and a[1] != 'label_volume']   # its width is the only one
    check(len(shape) == len(after) and not moved, f'widgets moved: {moved}')


def apply(work):
    ttf = Ttf(os.path.join(work, FONT))
    langs = os.path.join(work, RAW.format(theme='default'), 'strings')
    texts = {f[:-4]: strings(os.path.join(langs, f), TILE_KEYS) for f in sorted(os.listdir(langs)) if f.endswith('.bin')}
    check(all(len(texts[l]) == len(TILE_KEYS) for l in MUST_FIT), 'tile caption strings missing')
    out = []
    for theme in THEMES:
        path = os.path.join(work, RAW.format(theme=theme), DIALOG)
        report = []
        old, new, _ = edit_ui(path, lambda root: edit(root, ttf, texts, report))
        out.append(f'{os.path.relpath(path, work)}: {len(old)} -> {len(new)} bytes')
        out += [f'  {r}' for r in report]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('out')
    a = ap.parse_args()
    clone_workdir(a.src, a.out)
    for line in apply(a.out): print('pulldown:', line)


if __name__ == '__main__': main()
