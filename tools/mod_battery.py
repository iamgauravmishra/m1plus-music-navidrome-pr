#!/usr/bin/env python3
"""Battery-percentage mod for the Shanling M1 Plus status bar (asset-only, no binary patch).

Stock firmware looks up the widgets "img_battery" (icon: bar_power / bar_charge / bar_lowpower) and
"pgbar_battery" (an AWTK progress_bar used as the icon's fill) in ui/system_bar.bin and calls
progress_bar_set_value(pgbar_battery, capacity) on every refresh (demo: dropdown_showface).
AWTK progress bars can render their value as text (show_text + format), so re-styling that widget
turns the stock value feed into a percentage readout with zero code changes.

Variants:
  percent      hide the icon, show "86%" where the icon was
  icon+percent keep the state icon (normal/charging/low), show "86%" to its left

Usage: mod_battery.py STOCK_WORKDIR OUT_WORKDIR --variant percent|icon+percent
  (STOCK_WORKDIR is what `fwtool.py unpack` produced; OUT_WORKDIR is cloned from it and modified.)
"""
import argparse, os, shutil, stat, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui

UI = 'rootfs/release/assets/default/raw/ui/system_bar.bin'
SCREEN_W, RIGHT_MARGIN = 320, 6       # icon sits at x 296..310 on a 320 px wide bar
FONT = 16                              # status bar uses 20 for the volume number; 16 keeps "100%" ~34 px

def style_as_text(pg, x, w, font, y=0, h=30, align='right', states=('normal',)):
    """Turn an AWTK progress_bar into a transparent "%d%%" text readout of its value.
    Also used by mod_lockscreen.py (lock screen pgbar_battery, all three style states)."""
    pg.x, pg.y, pg.w, pg.h = x, y, w, h
    pg.set('vertical', 'false')
    def each(prop, value):
        for st in states: pg.set(f'style:{st}:{prop}', value)
    each('border_width', '0')
    each('bg_color', '#00000000')   # transparent: no gauge box
    each('fg_color', '#00000000')   # transparent: no fill, text only
    pg.set('show_text', 'true')
    pg.set('format', '%d%%')
    each('text_color', '#FFFFFF')
    each('font_size', str(font))
    each('text_align_h', align)
    each('text_align_v', 'middle')

def apply(root, variant):
    pg, img, right = root.find('pgbar_battery'), root.find('img_battery'), root.find('view_bar_right')
    assert pg and img and right, 'unexpected system_bar layout'
    assert pg.type == 'progress_bar' and img.type == 'image'
    if variant == 'percent':
        img.set('visible', 'false')
        img.x = -100          # belt and braces: also park the icon off-screen (stock re-sets only its image name)
        text_w, font = 42, FONT                           # "100%" at 16 px is ~40 px wide
        x = SCREEN_W - RIGHT_MARGIN - text_w              # 272..314
        style_as_text(pg, x, text_w, font)
    elif variant == 'icon+percent':
        text_w, font = 40, FONT - 1                       # a touch smaller so Bluetooth + Wi-Fi still clear the clock
        x = img.x - 4 - text_w                            # 252..292, icon stays at 296
        style_as_text(pg, x, text_w, font)
    else: raise SystemExit('unknown variant')
    # keep the right-aligned Bluetooth/SyncLink/Wi-Fi group clear of the new text
    right.x = x - 4 - right.w
    return root

def clone_workdir(src, out):
    """Fresh copy of an unpacked workdir in OUT (APFS clone when possible). OUT == SRC edits in place."""
    if os.path.abspath(src) == os.path.abspath(out): return
    if os.path.exists(out): shutil.rmtree(out)
    # APFS clone (fast, no extra space); fall back to a plain copy elsewhere
    r = subprocess.run(['cp', '-Rc', src, out], capture_output=True)
    if r.returncode: shutil.copytree(src, out, symlinks=True)
    shutil.rmtree(os.path.join(out, 'build'), ignore_errors=True)

def edit_ui(path, edit):
    """Parse a ui/*.bin, require a byte-exact untouched round trip, apply edit(root), write it back
    with the file's permission bits unchanged. Returns (old_bytes, new_bytes, root)."""
    old = open(path, 'rb').read()
    root = awtk_ui.parse(old)
    assert awtk_ui.serialize(root) == old, f'{path}: parse/serialize round trip is not byte-exact'
    edit(root)
    new = awtk_ui.serialize(root)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, mode | 0o200); open(path, 'wb').write(new); os.chmod(path, mode)
    return old, new, root

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('stock'); ap.add_argument('out'); ap.add_argument('--variant', required=True, choices=['percent', 'icon+percent'])
    a = ap.parse_args()
    clone_workdir(a.stock, a.out)
    stock, new, root = edit_ui(os.path.join(a.out, UI), lambda root: apply(root, a.variant))
    print(f'{a.variant}: {UI} {len(stock)} -> {len(new)} bytes')
    awtk_ui.dump(root.find('view_bar_right')); awtk_ui.dump(root.find('pgbar_battery')); awtk_ui.dump(root.find('img_battery'))

if __name__ == '__main__': main()
