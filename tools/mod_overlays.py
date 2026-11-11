#!/usr/bin/env python3
"""Two stock-looking screens restyled, asset-only (docs/modules/overlays.md): the message and confirm dialogs and the power-off splash.

Replaces (same file names, same pixel sizes, PNG, same file mode), each pinned by the SHA-256 of the stock file:
  msginfo_bg, confirminfo_bg   260 x 180 glass card (mod_icons.glass_image, r 12), the confirm one with its horizontal divider; the vertical
                               divider is the Cancel button's own right border (the rippercompleted dialog shares the image and has one button)
  shutdown                     320 x 480 the boot splash (assets/boot-logo.svg, mod_boot.py)
Styles edited (no widget renamed, moved or removed): ui/dialog/confirminfo_dialog.bin and rippercompleted_dialog.bin (the buttons' black
fill becomes transparent so the card shows, the pressed corner radius follows the card's).

Build time only copies the committed PNGs (assets/overlays/); --generate redraws them (Pillow, rsvg-convert for the splash).

Usage: mod_overlays.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place; a build.py step)
       mod_overlays.py --generate                  redraw assets/overlays/
       mod_overlays.py --pins                      rewrite tools/mod_overlays_pins.txt from the stock tree
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir, edit_ui, write_keep_mode, sha256, png_bytes, load_pins as _load_pins, stock_img_dir, write_pins

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = os.path.join(ROOT, 'assets', 'overlays')
PINS = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mod_overlays_pins.txt')
IMG = 'rootfs/release/assets/default/raw/images/xx'
UI = 'rootfs/release/assets/default/raw/ui'

WHITE = (255, 255, 255)
DIALOG_FILL = ((0x2A, 0x2A, 0x2C), (0x1E, 0x1E, 0x20), 0.94)   # the More sheet's glass (mod_icons.GLASS_SHEET_FILL), denser: the card has text on both halves
DIALOG_W, DIALOG_H, DIALOG_R = 260, 180, 12                    # the stock dialogs' size and corner radius
DIVIDER_Y, DIVIDER_ALPHA = 130, 0x22 / 255                     # the confirm card's horizontal line (stock: y 130) and the 13 % white hairline of the playmore rows
BTN_BORDER = '#FFFFFF22'                                       # the Cancel button's right border: the vertical divider
BTN_RADIUS = DIALOG_R - 1                                      # the buttons sit 1 px inside the card


# ---------------------------------------------------------------- the art
_png = png_bytes

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


# ---------------------------------------------------------------- the style edits
def _states(w, key, value, states=('normal', 'pressed', 'over', 'disable', 'focused')):
    for st in states: w.set(f'style:{st}:{key}', value)

def edit_confirm(root):
    """The dialog's two buttons (confirm: Cancel left, Enter right; ripper completed: one Enter button): no black fill over the card, the pressed corner
    follows the card's radius, and the Cancel button's right edge is the vertical divider."""
    two = root.find('btn_cancel') is not None
    assert root.get('highlight') == 'default(alpha=100)', f'{root.name}: not the stock highlighter'
    root.set('highlight', CONFIRM_DIM)   # the dialog highlighter dims the window below as our popups' scrim does (the stock alpha 100 left the page's buttons at nearly full brightness)
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


# The confirm dialog's message (kind 5: a word-wrapped label created by the dialog's init, 260 x 80 at y 25, @0x472e1c) takes its look from the style label_centerwhite20_style, which no other widget uses:
# a 12 px margin each side there is the text's padding (AWTK's label paints and wraps inside its margins), for every page that asks in kind 5 (Screenshot, Rebuild Covers, Clear Cover Cache, the Podcasts questions,
# Software Update, stock's Bluetooth / Wi-Fi switch-on questions). Widget geometry and names are untouched.
CONFIRM_DIM = 'default(alpha=130)'   # = tools/pod_ui.py PL_DIM (0x82) and the More sheet's highlighter
CONFIRM_LABEL_STYLE, CONFIRM_PAD = 'label_centerwhite20_style', 12
STYLES = 'rootfs/release/assets/default/raw/styles/default.bin'

def edit_confirm_label(out):
    import awtk_style, stat
    path = os.path.join(out, STYLES)
    old = open(path, 'rb').read(); th = awtk_style.parse(old)
    assert awtk_style.serialize(th) == old, f'{path}: style round trip is not byte-exact'
    items = th.find('label', CONFIRM_LABEL_STYLE)
    assert items, 'default.bin has no confirm label style'
    assert len(items) == 3 and all(not it.has('margin_left') and not it.has('margin_right') for it in items), f'{path}: not the stock style'
    for it in items: it.set('margin_left', CONFIRM_PAD, awtk_style.T_INT32); it.set('margin_right', CONFIRM_PAD, awtk_style.T_INT32)
    mode = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, mode | 0o200); open(path, 'wb').write(awtk_style.serialize(th)); os.chmod(path, mode)

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
    return _load_pins(PINS)

def stock_dir():
    return stock_img_dir(IMG)

def cmd_pins():
    write_pins(PINS, '# SHA-256 of the stock V2.1 images/xx files tools/mod_overlays.py replaces (tools/mod_overlays.py --pins)\n', stock_dir(), NAMES)

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
    for n in NAMES:
        p = os.path.join(out, IMG, n + '.png')
        data = open(p, 'rb').read()
        assert sha256(data) == pins[n], f'{p}: not the pinned stock file'
        fresh = open(os.path.join(ASSET, n + '.png'), 'rb').read()
        write_keep_mode(p, fresh); old += len(data); new += len(fresh)
    for rel in ('dialog/confirminfo_dialog.bin', 'dialog/rippercompleted_dialog.bin'):
        edit_ui(os.path.join(out, UI, rel), edit_confirm)
    for rel, image in CARD_DIALOGS.items():
        edit_ui(os.path.join(out, UI, rel), edit_card(image))
    edit_confirm_label(out)
    print(f'overlays: {len(NAMES)} images, {old} -> {new} bytes ({new - old:+d}); dialog buttons restyled')

def main():
    if len(sys.argv) == 2 and sys.argv[1] == '--generate': return cmd_generate()
    if len(sys.argv) == 2 and sys.argv[1] == '--pins': return cmd_pins()
    if len(sys.argv) != 3: sys.exit(__doc__)
    apply(sys.argv[1], sys.argv[2])

if __name__ == '__main__': main()
