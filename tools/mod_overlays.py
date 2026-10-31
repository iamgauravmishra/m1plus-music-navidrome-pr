#!/usr/bin/env python3
"""Two stock-looking screens restyled, asset-only (docs/modules/overlays.md): the message and confirm dialogs and the power-off splash.

Replaces (same file names, same pixel sizes, PNG, same file mode), each pinned by the SHA-256 of the stock file:
  msginfo_bg, confirminfo_bg   260 x 180 glass card (mod_icons.glass_image, r 12), the confirm one with its horizontal divider; the vertical
                               divider is the Cancel button's own right border (the rippercompleted dialog shares the image and has one button)
                               (default and theme1: the same stock bytes)
  shutdown                     320 x 480 the boot splash (assets/boot-logo.svg, mod_boot.py)
Styles edited (no widget renamed, moved or removed): ui/dialog/confirminfo_dialog.bin and rippercompleted_dialog.bin (the buttons' black
fill becomes transparent so the card shows, the pressed corner radius follows the card's).

Build time only copies the committed PNGs (assets/overlays/); --generate redraws them (Pillow, rsvg-convert for the splash).

Usage: mod_overlays.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place; a build.py step)
       mod_overlays.py --generate                  redraw assets/overlays/
       mod_overlays.py --pins                      rewrite tools/mod_overlays_pins.txt from the stock tree
"""
import hashlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
from modlib import clone_workdir, edit_ui, write_keep_mode

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = os.path.join(ROOT, 'assets', 'overlays')
PINS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mod_overlays_pins.txt')
THEMES = ('default', 'theme1')
IMG = 'rootfs/release/assets/{theme}/raw/images/xx'
UI = 'rootfs/release/assets/default/raw/ui'

WHITE = (255, 255, 255)
DIALOG_FILL = ((0x2A, 0x2A, 0x2C), (0x1E, 0x1E, 0x20), 0.94)   # the More sheet's glass (mod_icons.GLASS_SHEET_FILL), denser: the card has text on both halves
DIALOG_W, DIALOG_H, DIALOG_R = 260, 180, 12                    # the stock dialogs' size and corner radius
DIVIDER_Y, DIVIDER_ALPHA = 130, 0x22 / 255                     # the confirm card's horizontal line (stock: y 130) and the 13 % white hairline of the playmore rows
BTN_BORDER = '#FFFFFF22'                                       # the Cancel button's right border: the vertical divider
BTN_RADIUS = DIALOG_R - 1                                      # the buttons sit 1 px inside the card


# ---------------------------------------------------------------- the art
def _png(im):
    import io
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True); return b.getvalue()

def dialog(confirm):
    """The 260 x 180 card: glass, and for the confirm one the horizontal divider above the buttons."""
    import mod_icons
    im = mod_icons.glass_image(DIALOG_W, DIALOG_H, DIALOG_R, fill=DIALOG_FILL)
    if confirm:
        from PIL import Image
        line = Image.new('RGBA', (DIALOG_W - 2, 1), WHITE + (round(255 * DIVIDER_ALPHA),))
        im.alpha_composite(line, (1, DIVIDER_Y))
    return im

def splash():
    """The boot splash (assets/boot-logo.svg) as a PNG: the same 320 x 480 raster tools/boot_logo.py encodes into logo.jpg."""
    import boot_logo
    return boot_logo.render()

def images():
    """name -> PIL image of every file the step writes."""
    return {'msginfo_bg': dialog(False), 'confirminfo_bg': dialog(True), 'shutdown': splash()}

NAMES = ['msginfo_bg', 'confirminfo_bg', 'shutdown']
BOTH_THEMES = ('msginfo_bg', 'confirminfo_bg')      # theme1 has its own copies of these two (the same stock bytes); the rest is the default theme's


# ---------------------------------------------------------------- the style edits
def sha256(b): return hashlib.sha256(b).hexdigest()

def _states(w, key, value, states=('normal', 'pressed', 'over', 'disable', 'focused')):
    for st in states: w.set(f'style:{st}:{key}', value)

def edit_confirm(root):
    """The dialog's two buttons (confirm: Cancel left, Enter right; ripper completed: one Enter button): no black fill over the card, the pressed corner
    follows the card's radius, and the Cancel button's right edge is the vertical divider."""
    two = root.find('btn_cancel') is not None
    for n in ('btn_cancel', 'btn_enter'):
        b = root.find(n)
        if b is None: continue
        assert b.get('style:normal:bg_color') == '#000000', f'{n}: not the stock button'
        _states(b, 'bg_color', '#00000000', ('normal', 'over', 'disable', 'focused'))
        if two and n == 'btn_cancel':
            _states(b, 'round_radius_bottom_left', str(BTN_RADIUS)); _states(b, 'border', 'right'); _states(b, 'border_color', BTN_BORDER)
        elif two:
            _states(b, 'round_radius_bottom_right', str(BTN_RADIUS))
        else:   # the ripper dialog's one button spans the card
            _states(b, 'round_radius_bottom_left', str(BTN_RADIUS)); _states(b, 'round_radius_bottom_right', str(BTN_RADIUS))


# The other stock 260 x 180 message-like dialogs (cardupdate: card update, formatcard: formatting, dialog_autoshutdown: the sleep countdown) were black with a grey
# border, unlike the message box: the same card as msginfo / confirminfo (autoshutdown has the one full-width button under the confirm card's divider).
CARD_DIALOGS = {'dialog/cardupdate_dialog.bin': 'msginfo_bg', 'dialog/formatcard_dialog.bin': 'msginfo_bg', 'dialog/dialog_autoshutdown.bin': 'confirminfo_bg'}
CARD_STATES = ('normal', 'disable', 'focused')

def edit_card(image):
    def edit(root):
        assert (root.w, root.h) == (DIALOG_W, DIALOG_H) and root.get('style:normal:bg_color') == '#000000', f'{root.name}: not the stock dialog'
        _states(root, 'bg_color', '#00000000', CARD_STATES); _states(root, 'border_color', '#00000000', CARD_STATES)
        _states(root, 'bg_image', image, CARD_STATES)
        b = root.find('btn_cancel')
        if b is not None:   # autoshutdown's one button
            assert b.get('style:normal:bg_color') == '#000000'
            _states(b, 'bg_color', '#00000000', ('normal', 'over', 'disable', 'focused')); _states(b, 'border_color', '#00000000')
            _states(b, 'round_radius_bottom_left', str(BTN_RADIUS)); _states(b, 'round_radius_bottom_right', str(BTN_RADIUS))
    return edit


# ---------------------------------------------------------------- pins, generate, apply
def load_pins():
    return {n: h for h, n in (l.split() for l in open(PINS) if l.strip() and not l.startswith('#'))}

def stock_dir(theme='default'):
    stock = paths.find_stock(paths.ZIP)
    if not stock: sys.exit('no unpacked stock tree found (run tools/build.py once)')
    return os.path.join(stock, IMG.format(theme=theme))

def cmd_pins():
    with open(PINS, 'w') as o:
        o.write('# SHA-256 of the stock V2.1 images/xx files tools/mod_overlays.py replaces (tools/mod_overlays.py --pins); theme1 carries the same bytes for its two\n')
        for n in NAMES: o.write(f'{sha256(open(os.path.join(stock_dir(), n + ".png"), "rb").read())}  {n}\n')
        for n in BOTH_THEMES:
            assert sha256(open(os.path.join(stock_dir('theme1'), n + '.png'), 'rb').read()) == sha256(open(os.path.join(stock_dir(), n + '.png'), 'rb').read())

def cmd_generate():
    from PIL import Image
    os.makedirs(ASSET, exist_ok=True)
    for n, im in images().items():
        stock = Image.open(os.path.join(stock_dir(), n + '.png'))
        assert im.size == stock.size, (n, im.size, stock.size)
        open(os.path.join(ASSET, n + '.png'), 'wb').write(_png(im))
    print('->', ASSET, sum(os.path.getsize(os.path.join(ASSET, f)) for f in os.listdir(ASSET)), 'bytes')

def apply(src, out):
    clone_workdir(src, out)
    pins = load_pins(); old = new = 0
    for theme in THEMES:
        for n in (NAMES if theme == 'default' else BOTH_THEMES):
            p = os.path.join(out, IMG.format(theme=theme), n + '.png')
            data = open(p, 'rb').read()
            assert sha256(data) == pins[n], f'{p}: not the pinned stock file'
            fresh = open(os.path.join(ASSET, n + '.png'), 'rb').read()
            write_keep_mode(p, fresh); old += len(data); new += len(fresh)
    for rel in ('dialog/confirminfo_dialog.bin', 'dialog/rippercompleted_dialog.bin'):
        edit_ui(os.path.join(out, UI, rel), edit_confirm)
    for rel, image in CARD_DIALOGS.items():
        edit_ui(os.path.join(out, UI, rel), edit_card(image))
    print(f'overlays: {len(NAMES)} images (+{len(BOTH_THEMES)} for theme1), {old} -> {new} bytes ({new - old:+d}); dialog buttons restyled')

def main():
    if len(sys.argv) == 2 and sys.argv[1] == '--generate': return cmd_generate()
    if len(sys.argv) == 2 and sys.argv[1] == '--pins': return cmd_pins()
    if len(sys.argv) != 3: sys.exit(__doc__)
    apply(sys.argv[1], sys.argv[2])

if __name__ == '__main__': main()
