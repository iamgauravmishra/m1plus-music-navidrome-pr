"""The overlay screens (tools/mod_overlays.py, docs/modules/overlays.md): the message / confirm dialogs and the power-off splash."""
import os
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import mod_overlays as mo
from PIL import Image


def run(ctx):
    expect = ctx.expect
    raw = os.path.join(WORK, 'rootfs', 'release', 'assets', 'default', 'raw')
    def img(n): return Image.open(os.path.join(raw, 'images/xx', n + '.png'))
    def shipped(n): return open(os.path.join(raw, 'images/xx', n + '.png'), 'rb').read()
    pins = mo.load_pins()
    expect(sorted(pins) == sorted(mo.NAMES) and len(mo.NAMES) == 3, 'every replaced image is pinned')
    for n in mo.NAMES:
        expect(shipped(n) == open(os.path.join(mo.ASSET, n + '.png'), 'rb').read(), f'{n}: the built file is the committed asset')
    expect(sorted(os.listdir(mo.ASSET)) == sorted(n + '.png' for n in mo.NAMES), 'the committed art is exactly the three files')

    # the charging and battery art stays the stock bytes (the scan spinner, chargebg and the USB pages are tools/mod_icons.py's, docs/modules/icons.md)
    stock = mo.stock_dir()
    for n in ['charging0', 'charging18', 'charge_big', 'dac_charge']:
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
    dlg = os.path.join(raw, 'ui', 'dialog')
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
    ui = os.path.join(raw, 'ui')
    for rel in ('dialog/confirminfo_dialog.bin', 'dialog/rippercompleted_dialog.bin'):
        t = awtk_ui.parse(open(os.path.join(ui, rel), 'rb').read())
        btns = [b for b in (t.find('btn_cancel'), t.find('btn_enter')) if b is not None]
        expect(btns and all(b.get('style:normal:bg_color') == '#00000000' for b in btns), f'{rel}: buttons transparent so the card shows')
    t = awtk_ui.parse(open(os.path.join(ui, 'dialog/confirminfo_dialog.bin'), 'rb').read())
    c, e = t.find('btn_cancel'), t.find('btn_enter')
    expect((c.x, c.y, c.w, c.h) == (1, 131, 128, 48) and (e.x, e.y, e.w, e.h) == (131, 131, 128, 48), 'confirm buttons keep their geometry')
    expect(t.get('highlight') == mo.CONFIRM_DIM == 'default(alpha=130)', 'the confirm dialog dims the window below like our popups\' scrim (the highlighter\'s alpha 130)')
    expect(c.get('style:normal:border') == 'right' and c.get('style:normal:border_color') == mo.BTN_BORDER, 'Cancel draws the vertical divider as its right border')
    p = open(os.path.join(ui, 'poweroff_page.bin'), 'rb').read()
    q = open(os.path.join(stock, '..', '..', 'ui', 'poweroff_page.bin'), 'rb').read()
    expect(p == q, 'poweroff_page.bin is stock (only shutdown.png changed)')
    scrim_tests(ctx)


def scrim_tests(ctx):
    """The confirm dialog over the page (docs/modules/overlays.md): while the modal dialog is up, a full-window view of #00000082 is the top main window's last child,
    insensitive; it is hidden, made insensitive and destroyed when the call returns, Yes or No. Nothing is touched when the page closed meanwhile or the view failed."""
    expect = ctx.expect
    DIM = 0x82000000   # #00000082 as the uint32 value_t holds
    CONFIRM = 'Delete all measured track durations? They will be measured again on Home.'

    def page(m, w=320, h=450):
        win = m.alloc(0x80); m.u.mem_write(win, bytes(0x80))
        m.setword(win + O['W_W'], w); m.setword(win + O['W_H'], h)
        m.top_main = win; m.children[m.wm] = [win]
        return win

    def at(m, pred): return [i for i, c in enumerate(m.calls) if pred(c)]

    m = Machine(); win = page(m); snap = []
    m.on_confirm = lambda mm: snap.append(list(mm.children.get(win, [])))
    for yes in (False, True):
        m.confirm_yes = yes; snap.clear(); n0 = len(getattr(m, 'styled', []))
        m.call(PSYMS['durations_clear_ask'], count=3000000)
        made = [c[1] for c in m.calls if c[0] == 'view_create']
        scrim = made[0] if len(made) == 1 else 0
        dim = [s for s in getattr(m, 'styled', [])[n0:] if s[0] == scrim and s[1] == 'normal:bg_color']
        ask, shown = at(m, lambda c: c[0] == 'confirm'), at(m, lambda c: c[0] == 'widget_destroy' and c[1] == scrim)
        expect(scrim and [c[1] for c in m.calls if c[0] == 'confirm'] == [CONFIRM], f'Yes={yes}: one scrim view is made for the confirm ({made})')
        expect(snap and snap[0][-1] == scrim and m.props.get((scrim, 'w')) == 320 and m.props.get((scrim, 'h')) == 450 and m.props.get((scrim, 'x')) == 0,
               f'Yes={yes}: while the dialog is up the scrim is the window\'s last child, the window\'s size ({snap})')
        expect(dim and dim[-1][2] == DIM, f'Yes={yes}: the scrim is #00000082 ({dim})')
        expect(at(m, lambda c: c == ('widget_set_sensitive', scrim, 0)) and at(m, lambda c: c == ('widget_set_sensitive', scrim, 0))[0] < ask[0],
               f'Yes={yes}: the scrim takes no input, from before the dialog')
        hid = at(m, lambda c: c == ('widget_set_visible', scrim, 0))
        expect(hid and shown and hid[0] < shown[0] and shown[0] > ask[0],
               f'Yes={yes}: hidden, insensitive and destroyed after the dialog returned')
        expect(scrim not in m.children.get(win, []), f'Yes={yes}: no scrim is left on the page')
    expect(sum(1 for c in m.calls if c[0] == 'widget_destroy') == 1, 'the last call destroys the scrim and nothing else')

    # the page closed while the dialog is up: the window manager no longer holds it, so the scrim (freed with it) is never touched
    m = Machine(); win = page(m)
    m.on_confirm = lambda mm: mm.children.__setitem__(mm.wm, [])
    m.confirm_yes = True
    m.call(PSYMS['durations_clear_ask'], count=3000000)
    scrim = [c[1] for c in m.calls if c[0] == 'view_create']
    expect(scrim and not [c for c in m.calls if c[0] in ('widget_destroy', 'widget_set_visible') and c[1] == scrim[0]] and [c for c in m.calls if c[0] == 'confirm'],
           'the page closed under the dialog: nothing is done to the scrim after the call')

    # no top main window: no scrim, the dialog still opens; a view that cannot be made: the dialog opens without one
    m = Machine(); m.top_main = 0; m.confirm_yes = True
    m.call(PSYMS['durations_clear_ask'], count=3000000)
    expect(not [c for c in m.calls if c[0] == 'view_create'] and [c for c in m.calls if c[0] == 'confirm'], 'no page to dim: the confirm still opens, no view is made')
    m = Machine(); page(m); m.create_fail.add('view_create'); m.confirm_yes = True
    m.call(PSYMS['durations_clear_ask'], count=3000000)
    expect([c for c in m.calls if c[0] == 'confirm'] and not [c for c in m.calls if c[0] == 'widget_destroy'], 'a view that cannot be made: the confirm still opens, nothing is destroyed')
