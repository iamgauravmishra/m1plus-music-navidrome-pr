"""The overlay screens (tools/mod_overlays.py, docs/modules/overlays.md): the message / confirm dialogs and the power-off splash."""
import os
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import mod_overlays as mo
from PIL import Image


def run(ctx):
    expect = ctx.expect
    raw = lambda theme: os.path.join(WORK, 'rootfs', 'release', 'assets', theme, 'raw')
    def img(n, theme='default'): return Image.open(os.path.join(raw(theme), 'images/xx', n + '.png'))
    def shipped(n, theme='default'): return open(os.path.join(raw(theme), 'images/xx', n + '.png'), 'rb').read()
    pins = mo.load_pins()
    expect(sorted(pins) == sorted(mo.NAMES) and len(mo.NAMES) == 3, 'every replaced image is pinned')
    for n in mo.NAMES:
        expect(shipped(n) == open(os.path.join(mo.ASSET, n + '.png'), 'rb').read(), f'{n}: the built file is the committed asset')
    for n in mo.BOTH_THEMES:
        expect(shipped(n, 'theme1') == shipped(n), f'{n}: theme1 gets the same file')
    expect(sorted(os.listdir(mo.ASSET)) == sorted(n + '.png' for n in mo.NAMES), 'the committed art is exactly the three files')

    # the art that was reverted stays the stock bytes: scan, charging, battery and USB images are not touched by the step
    stock = mo.stock_dir()
    for n in ['scan1', 'scan12', 'charging0', 'charging18', 'charge_big', 'chargebg', 'usb_dac', 'usb_storage', 'dac_charge']:
        expect(shipped(n) == open(os.path.join(stock, n + '.png'), 'rb').read(), f'{n} is stock')

    sizes = {'msginfo_bg': (260, 180), 'confirminfo_bg': (260, 180), 'shutdown': (320, 480)}
    expect(all(img(n).size == s for n, s in sizes.items()), 'every image keeps its stock pixel size')

    # dialogs: glass (translucent, rounded corners), divider only on the confirm card
    msg, con = img('msginfo_bg').convert('RGBA'), img('confirminfo_bg').convert('RGBA')
    expect(msg.getpixel((0, 0))[3] == 0 and 200 < msg.getpixel((130, 90))[3] < 255, 'message card: transparent corner, glass body')
    expect(con.getpixel((60, mo.DIVIDER_Y))[3] > msg.getpixel((60, mo.DIVIDER_Y))[3] and con.getpixel((60, 160)) == msg.getpixel((60, 160)), 'confirm card: the horizontal divider, no vertical line in the image')
    expect(mo.dialog(False).tobytes() == msg.tobytes() and mo.dialog(True).tobytes() == con.tobytes(), 'dialog art is the generator output')
    expect(img('shutdown').size == (320, 480) and img('shutdown').convert('RGB').getpixel((5, 5)) == (0, 0, 0), 'the splash is the black boot logo')

    # the resolved styles of every message-like 260 x 180 dialog agree with the confirm box's: the same card (bg_image / bg_color / border / radius in the states the dialogs use),
    # no grey border; the message box (msginfo) and the confirm box differ only in the card picture's divider
    dlg = os.path.join(raw('default'), 'ui', 'dialog')
    def card(rel):
        t = awtk_ui.parse(open(os.path.join(dlg, rel), 'rb').read())
        return {(st, k): t.get(f'style:{st}:{k}') for st in mo.CARD_STATES for k in ('bg_color', 'border_color', 'round_radius')}, {t.get(f'style:{st}:bg_image') for st in mo.CARD_STATES} - {None}, (t.w, t.h)
    ref, _, ref_size = card('confirminfo_dialog.bin')
    for rel in ('msginfo_dialog.bin', 'rippercompleted_dialog.bin', *[k.split('/')[1] for k in mo.CARD_DIALOGS]):
        st, images, size = card(rel)
        expect(size == ref_size and all(st[k] == ref[k] for k in ref if k[1] != 'round_radius' or st[k] is not None) and st[('normal', 'round_radius')] in ('12', None) and len(images) == 1,
               f'{rel}: the confirm box\'s card styles (transparent fill and border, one picture) ({st})')
    for rel, image in {'msginfo_dialog.bin': 'msginfo_bg', 'confirminfo_dialog.bin': 'confirminfo_bg', **{k.split('/')[1]: v for k, v in mo.CARD_DIALOGS.items()}}.items():
        expect(card(rel)[1] == {image}, f'{rel}: bg_image {image}')
    t = awtk_ui.parse(open(os.path.join(dlg, 'dialog_autoshutdown.bin'), 'rb').read()); b = t.find('btn_cancel')
    expect(b.get('style:normal:bg_color') == '#00000000' and b.get('style:normal:border_color') == '#00000000', 'the sleep countdown\'s button has no black fill or grey border')
    # ui edits
    ui = os.path.join(raw('default'), 'ui')
    for rel in ('dialog/confirminfo_dialog.bin', 'dialog/rippercompleted_dialog.bin'):
        t = awtk_ui.parse(open(os.path.join(ui, rel), 'rb').read())
        btns = [b for b in (t.find('btn_cancel'), t.find('btn_enter')) if b is not None]
        expect(btns and all(b.get('style:normal:bg_color') == '#00000000' for b in btns), f'{rel}: buttons transparent so the card shows')
    t = awtk_ui.parse(open(os.path.join(ui, 'dialog/confirminfo_dialog.bin'), 'rb').read())
    c, e = t.find('btn_cancel'), t.find('btn_enter')
    expect((c.x, c.y, c.w, c.h) == (1, 131, 128, 48) and (e.x, e.y, e.w, e.h) == (131, 131, 128, 48), 'confirm buttons keep their geometry')
    expect(c.get('style:normal:border') == 'right' and c.get('style:normal:border_color') == mo.BTN_BORDER, 'Cancel draws the vertical divider as its right border')
    p = open(os.path.join(ui, 'poweroff_page.bin'), 'rb').read()
    q = open(os.path.join(stock, '..', '..', 'ui', 'poweroff_page.bin'), 'rb').read()
    expect(p == q, 'poweroff_page.bin is stock (only shutdown.png changed)')
