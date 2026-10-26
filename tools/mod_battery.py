#!/usr/bin/env python3
"""The battery icon of the status bar and the pull-down (asset-only, no binary patch).

Stock firmware looks up the widgets "img_battery" (icon: bar_power / bar_charge / bar_lowpower) and
"pgbar_battery" (an AWTK progress_bar used as the icon's fill) in ui/system_bar.bin and calls
progress_bar_set_value(pgbar_battery, capacity) on every refresh (demo: dropdown_showface; the
system bar has a twin at 0x545168). So the three state images become an outline (a 16x11 body with
a 2 px nub: white, green with a bolt while charging, red at 0; tools/battery_art.py, shared with the
lock screen) and pgbar_battery the horizontal 12x7 fill inside it, drawn under the image (stock child
order). No number. Applied to the status bar and to the pull-down's own bar, in both themes.

Usage: mod_battery.py STOCK_WORKDIR OUT_WORKDIR
  (STOCK_WORKDIR is what fwtool.py unpack produced; OUT_WORKDIR is cloned from it and modified.)
"""
import hashlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui, battery_art
from modlib import clone_workdir, edit_ui, write_keep_mode

UI = 'rootfs/release/assets/default/raw/ui/system_bar.bin'
DROPDOWN = 'rootfs/release/assets/{theme}/raw/ui/dialog/dropdown_dialog.bin'
IMAGES = 'rootfs/release/assets/{theme}/raw/images/xx/{name}.png'
ICON_THEMES = ('default', 'theme1')
BODY_W, BODY_H, NUB_W = 16, 11, 2                    # q2-pod BATT_BODY_W/H, BATT_NUB_W
ICON_W = BODY_W + NUB_W                              # 18 x 11 canvas
# the state images the app swaps between; the stock 14x20 files, pinned (default and theme1 carry the same bytes)
STATE = {'bar_power': 'normal', 'bar_charge': 'charge', 'bar_lowpower': 'low'}
STOCK_ICONS = {'bar_power': 'fc28dc349da0', 'bar_charge': 'fceb7082b5cc', 'bar_lowpower': '1b2410d4038f'}

def icon_gauge(root):
    """img_battery -> the 18x11 outline at the stock icon's right edge, vertically centred in the
    30 px bar; pgbar_battery -> its 12x7 interior, horizontal, white on transparent, no text.
    Returns the icon's x."""
    pg, img = root.find('pgbar_battery'), root.find('img_battery')
    assert (pg.x, pg.y, pg.w, pg.h) == (296, 8, 14, 17) and (img.x, img.y, img.w, img.h) == (296, 5, 14, 20), 'not the stock battery'
    assert pg.get('vertical') == 'true' and pg.get('show_text') == 'false' and img.get('image') == 'bar_power'
    edge = img.x + img.w                                                 # 310, as stock
    img.x, img.y, img.w, img.h = edge - ICON_W, (30 + 1 - BODY_H) // 2, ICON_W, BODY_H   # 292, 10
    img.set('draw_type', 'default')                                      # 1:1
    pg.x, pg.y, pg.w, pg.h = img.x + 2, img.y + 2, BODY_W - 4, BODY_H - 4  # 294, 12, 12 x 7
    pg.set('vertical', 'false')
    for k, v in (('border_width', '0'), ('round_radius', '0'), ('bg_color', '#00000000'), ('fg_color', '#FFFFFF')):
        pg.set(f'style:normal:{k}', v)
    return img.x

def apply_icon_files(out):
    """The three state images (default and theme1) and the pull-down's own battery (both themes)."""
    done = []
    for theme in ICON_THEMES:
        for name, state in STATE.items():
            p = os.path.join(out, IMAGES.format(theme=theme, name=name))
            old = open(p, 'rb').read()
            assert hashlib.sha256(old).hexdigest()[:12] == STOCK_ICONS[name], f'{p}: not the stock icon'
            new = battery_art.png(battery_art.STATUS, state); write_keep_mode(p, new); done.append((p, len(old), len(new)))
        p = os.path.join(out, DROPDOWN.format(theme=theme))
        def edit(root):
            right = root.find('view_bar_right'); assert right is not None
            x = icon_gauge(root); right.x = x - 4 - right.w
        o, n, _ = edit_ui(p, edit); done.append((p, len(o), len(n)))
    return done

def apply(root):
    right = root.find('view_bar_right')
    assert right is not None, 'unexpected system_bar layout'
    x = icon_gauge(root)
    right.x = x - 4 - right.w       # keep the right-aligned Bluetooth/SyncLink/Wi-Fi group clear of the icon
    return root

def main():
    if len(sys.argv) != 3: sys.exit(__doc__)
    stock_dir, out = sys.argv[1:]
    clone_workdir(stock_dir, out)
    stock, new, root = edit_ui(os.path.join(out, UI), apply)
    print(f'{UI} {len(stock)} -> {len(new)} bytes')
    for p, o, n in apply_icon_files(out): print(f'{os.path.relpath(p, out)} {o} -> {n} bytes')
    awtk_ui.dump(root.find('view_bar_right')); awtk_ui.dump(root.find('pgbar_battery')); awtk_ui.dump(root.find('img_battery'))

if __name__ == '__main__': main()
