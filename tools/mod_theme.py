#!/usr/bin/env python3
"""Global look: a Minimal (q2-pod "Theme: Minimal") neutral theme for the Shanling M1 Plus.
Asset-only: styles/default.bin, ui/system_bar.bin, ui/home_page.bin and some images/xx PNGs.
Full description, colours, the style -> page table and the device checklist: docs/ui.md.

What it does (default assets only; assets/theme1, the stock "Theme" setting's alternative, is
left stock on purpose, so System settings -> Theme -> the second theme is the stock look):
  1. styles/default.bin (pinned by SHA-256; every edit is pinned by its old value and state count)
     - list rows (list_item_style, list_item_notpress_style, list_itemsort_style and the code-built
       table rows' btn_tablerow_style): stock #131313 cards with 4 px black gaps become black rows
       with a 1 px #222222 hairline; the reddish pressed tint #362221 becomes neutral #333333
       (also on the keyboard keys kb_btn1/2_style)
     - the accent (stock orange #FE7E40 / salmon #FA7268) goes neutral: text that is the accent on
       its own (playing title, centred notes, the text selector's current value) turns white; where
       the accent marks one item against white partners (lyric line, lyric tab, A-Z tabs) the
       accent turns white and the partner style turns muted #8C8C8C, so the hierarchy survives
     - nothing else: AWTK's light default widget styles (window/dialog/list_view/label "default")
       stay as they are, so no page that relies on them changes colour
  2. images/xx: the 40x40 settings icons' coloured discs turn #777777 grey with white glyphs
     (q2-pod's Minimal mapping by saturation, done at build time instead of at load); the grey
     ones are re-levelled to the same disc; status bar play/pause/Wi-Fi/Bluetooth glyphs are
     redrawn anti-aliased with one stroke weight (q2-pod status_icon), same canvas sizes
  3. ui/system_bar.bin (must already carry mod_battery.py's icon layout): one 16 px
     size for the volume number and the percentage, an 18 px clock nudged left so a 12 h "12:59 PM"
     clears the right-hand icons, 4 px icon spacing, a 10 px edge margin on both sides
  4. ui/home_page.bin: cosmetic only: black now-playing strip with a hairline, grey artist line,
     neutral page dots. The icon grid is built in code and untouched

Every widget keeps its name; only geometry and style properties change.

Usage: mod_theme.py SRC_WORKDIR OUT_WORKDIR       (OUT == SRC edits in place)
       mod_theme.py --scan FINISHED_TREE STOCK_TREE
  --scan checks a finished tree (all looks applied, window themes included) against stock and fails
  on any text that drops below 4.5:1 and got worse; build.py runs it after the steps.
"""
import argparse, hashlib, os, stat, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_style, awtk_ui, statusbar
from awtk_style import T_INT32, T_UINT32
from modlib import clone_workdir, edit_ui

from awtk_ui import RAW
STYLE = f'{RAW}/styles/default.bin'
BAR = f'{RAW}/ui/system_bar.bin'
HOME = f'{RAW}/ui/home_page.bin'
IMG = f'{RAW}/images/xx'
STYLE_SHA = '24a8f765f315d836afa85731ca923512a506138930398683242ffaaa831b00c9'   # stock V2.1

# Palette (docs/ui.md). Rows/pressed after q2-pod's pinned style edits; MUTED = q2-pod
# SUDO_MUTED; DISC = q2-pod MINIMAL_CHEVRON (the Minimal settings disc grey).
BLACK, LINE, PRESSED = '#000000FF', '#222222FF', '#333334FF'   # PRESSED: palette.ROLE_PRESS_ROW (one blue level off #333333, so only a pressed row has it: the accent maps it)
WHITE, MUTED, DISC = '#FFFFFFFF', '#8C8C8CFF', 0x77
ORANGE, SALMON, STOCK_ROW, STOCK_PRESSED = '#FE7E40FF', '#FA7268FF', '#131313FF', '#362221FF'

# (widget, style, key, old, new, states that must hold old). Colours as '#RRGGBBAA', ints as int.
STYLE_EDITS = [
    # list rows: black, hairline, neutral pressed
    ('list_item', 'list_item_style', 'bg_color', STOCK_ROW, BLACK, 4),
    ('list_item', 'list_item_style', 'bg_color', STOCK_PRESSED, PRESSED, 1),
    ('list_item', 'list_item_style', 'border_color', '#000000FF', LINE, 5),
    ('list_item', 'list_item_style', 'border_width', 4, 1, 5),
    ('list_item', 'list_item_notpress_style', 'bg_color', STOCK_ROW, BLACK, 5),
    ('list_item', 'list_item_notpress_style', 'border_color', '#000000FF', LINE, 5),
    ('list_item', 'list_item_notpress_style', 'border_width', 4, 1, 5),
    ('list_item', 'list_itemsort_style', 'bg_color', STOCK_PRESSED, PRESSED, 1),
    ('list_item', 'list_itemsort_style', 'border_color', '#333333FF', LINE, 5),
    ('button', 'btn_tablerow_style', 'bg_color', STOCK_ROW, BLACK, 4),
    ('button', 'btn_tablerow_style', 'bg_color', STOCK_PRESSED, PRESSED, 1),
    ('button', 'btn_tablerow_style', 'border_color', '#00000000', LINE, 5),
    ('button', 'kb_btn1_style', 'bg_color', STOCK_PRESSED, PRESSED, 1),
    ('button', 'kb_btn2_style', 'bg_color', STOCK_PRESSED, PRESSED, 1),
    # the accent on its own -> white (the playing row also carries the icon_playing glyph)
    ('hscroll_label', 'srlabel_item_gold18_style', 'text_color', ORANGE, WHITE, 3),
    ('hscroll_label', 'srlabel_item_gold20_style', 'text_color', ORANGE, WHITE, 3),
    ('label', 'label_centergold22_style', 'text_color', ORANGE, WHITE, 3),
    ('text_selector', 'text_gold22_style', 'highlight_text_color', ORANGE, WHITE, 3),   # text stays #AAAAAA
    # accent vs white partner -> white vs muted
    ('button', 'btn_selcolor_style', 'text_color', ORANGE, WHITE, 1),
    ('button', 'btn_selcolor_style', 'text_color', SALMON, WHITE, 4),
    ('button', 'btn_unselcolor_style', 'text_color', WHITE, MUTED, 5),
    ('label', 'navbar_lyric_style', 'text_color', ORANGE, WHITE, 5),
    ('label', 'navbar_sellyric_style', 'text_color', WHITE, MUTED, 5),
    ('list_item', 'listitem_sellyric_style', 'text_color', ORANGE, WHITE, 5),
    ('list_item', 'listitem_lyric_style', 'text_color', WHITE, MUTED, 5),
]
# (widget, style, key, type, value, states): new properties. The table rows get the list rows'
# hairline: border 8 (= bottom, as list_item_style's own value) and 1 px.
STYLE_ADDS = [
    ('button', 'btn_tablerow_style', 'border', T_INT32, 8, 5),
    ('button', 'btn_tablerow_style', 'border_width', T_UINT32, 1, 5),
]
ROW_STYLES = [('list_item', 'list_item_style'), ('list_item', 'list_item_notpress_style'),
              ('list_item', 'list_itemsort_style'), ('button', 'btn_tablerow_style')]

# 40x40 RGBA settings-row icons (names set by demo's settings code), pinned by stock SHA-256.
SETTINGS_ICONS = {
    'playset_foldercover.png': '95a2776f7511146c7005235f139452f9206b952a946e97a869f938cb52ecab46',
    'pset_balance.png': '7bbe7bdcf861dac336a43194bbbf05df5b1daeb407269a6272eb852b2afd100a',
    'pset_bootvol.png': '03ec478edf28276eb586f07d581862dd01e04cabbd55b674c995fac77050eaad',
    'pset_covermode.png': '58780b0189987a8d5b6e8459fbe37dfb6d3b3d85015c06321bc5c7c7f8580970',
    'pset_dac.png': '383dc3571427bb4658967dccce6925f775a5482ec6feaeb768becc4f70e9a0e5',
    'pset_digital.png': '4753aa3ad8747d6b840b365f9a923b5f08dfdb1e93e317596e522d5bf4bbb3ab',
    'pset_dsdoutput.png': '3ec104f3a5189c6d2ca0d910865b5042cf360276d438547e288ae08901f991f9',   # grey disc
    'pset_eq.png': '096157c0c6d61c2aaf6f38fbdc3fc64750a2981a3f899dd15907309b50de2101',          # grey disc
    'pset_filter.png': '5a86dd1c100a95cc253c696f7bbe7c01eee4abdd5c1df98a62fdce1f5c2fbaf7',
    'pset_gain.png': '4c495d3fcbc7e8b1f96edcc903eeb671e3618877e66e022fd57ceec7fd28fcb0',
    'pset_gapless.png': 'f0602be2654418436723df2cbcd9458edafafbf20dce826dea8c594b34f3e973',
    'pset_jumpfolder.png': '45898bce92a450675d65b89c526e3f0cde295041c21f59bbf3c107f38ea2f9ad',
    'pset_maxvol.png': 'd6caa10d675b6eef1558c7d73ca319b8f3ce19450635a028a2652add3bf6b696',
    'pset_memplay.png': 'd1057dd9308ab4cafe82f1cbbeac48eff3ca956b1e8f30f31ab8c9d27991da53',
    'pset_playmode.png': '4e3137221cd7c13ba71a41d84f31d7fd2ad57f578719d119b35b191b04e6bfa5',
    'pset_replaygain.png': '996b405550c034a4f220a12c3f9254a260a20f117d609fa24a769ab13da4a15f',
    'pset_usbaudiovol.png': 'b6f9a31f859338898259a3bd3d37b9b3bcbe6347b36652504c13d35a27f93ddb',
    'screensaver_info.png': 'cc091e1cd721b264f03e723417b7afee02324cff122dd75cb009ca797d54118e',
    'screensaver_timeshow.png': 'a0dc08ae532bf776bb50fa3068b8836cab8c7111fdc0c22348bfa332e8578088',
    'sset_about.png': 'cc091e1cd721b264f03e723417b7afee02324cff122dd75cb009ca797d54118e',
    'sset_atmosphereled.png': 'af6a291db4dcfc72df6c43e08326d1723f9340e5754f170357c3b8e86ef1fda3',
    'sset_carmode.png': 'db864f0c393712d8c8e63ba57f02ac659f7cea137c11092bf8b4e3220cc0015f',
    'sset_covermode.png': '58780b0189987a8d5b6e8459fbe37dfb6d3b3d85015c06321bc5c7c7f8580970',
    'sset_display.png': '396139ceace8128997a8ded0ab7007c7ece467d3cf3032c0d8165513dd48393e',
    'sset_doublewake.png': '9a33b86f084a49ab10407ea0d467e4efb82f2937405332373f758b091852e217',
    'sset_dsdoutput.png': '3ec104f3a5189c6d2ca0d910865b5042cf360276d438547e288ae08901f991f9',   # grey disc
    'sset_theme.png': 'e45bdfbcc430fe425af1ee7da71b70e6060fe1238de077004990ddf4f9010b45',       # grey disc
    'sset_keylock.png': 'dd92bc084ecdfa030b767fbda826d24c30410a6bd3271a7a6ea5b4de18aeb687',
    'sset_lighttime.png': '17ac8b6db639ff6b41e05e3b34f0a1db42d5bca678dcd342d5613dea91487e57',
    'sset_netservice.png': '1928dca5b209068fd738fee0a2edcaa2895c21d5483f4b247b39286dadea0f56',
    'sset_outputway.png': '7c47c1a8a704f6ffdd28404511d0f4ac01f786bceed5468230f0d3a223b6f9bb',
    'sset_powermanager.png': '2e16cc4036b89ae8fa63d94ab5a91efeefbb8966d9daaf5de4010fd5cbab16e3',
    'sset_prove.png': 'f677c84e47ff4187db589217afa80753bae7f8fcc67329fa86502f2adec2259a',
    'sset_screenlock.png': '8241b189b84584c50eff830879afd5df4fc12cc13f9eb017cebb572b2695b3a5',
    'sset_system.png': '35c443cb8a9576403c6ef5cee2be13f52d36d7a761bb1aa2f69e6c6f444cc8c6',
    'sset_tswake.png': '9a33b86f084a49ab10407ea0d467e4efb82f2937405332373f758b091852e217',
    'sset_usbaudiovol.png': 'b6f9a31f859338898259a3bd3d37b9b3bcbe6347b36652504c13d35a27f93ddb',
    'sset_usbmode.png': 'cc8885b9831f07084fee4674182615e2abf82c3e4931cdbd2bddec3a1d6590cb',
    'sset_wifiset.png': 'af3a62b20130ba305c8c6f47b16227080a530151e314b2cf23118792b18e3277',
    'system_formatcard.png': 'ed467f1d8fe0a0fa0e4a3a7c85d6b9a73c4e74b3f954268d6881236f1c1072ef',
    'system_language.png': 'aa61f0bec17152f95bf31c9b031cc51d64859aec6da5a6507d60d4940f3b8c63',
    'system_reset.png': '63d023692d31b6d0f52f99eb1a5f188d3dae4a17fc7c35f89570a5a1cf0c8d3a',
    'system_scrotate.png': '0e2cd7cd499cb4b28f5e846377cfb14864e2d8a8400fa7108d537c416dc97627',
    'system_time.png': 'c1d67adaea5e33384a1fc998bfa094fd9a44adfb1ef94c8adec59f86e6a1f53b',
    'system_update.png': '35c443cb8a9576403c6ef5cee2be13f52d36d7a761bb1aa2f69e6c6f444cc8c6',
    'usb_chargeswitch.png': 'b6f9a31f859338898259a3bd3d37b9b3bcbe6347b36652504c13d35a27f93ddb',
}
STATUS_ICONS = {   # redrawn on the same canvas; stock bytes pinned
    'bar_play.png': '9b65bea60768a6433eb5ebec7b2285290bd323ca826462126fce27ab73a9db65',
    'bar_pause.png': 'c88c59b79a6a1971883ad5aceb04c889891c74d4bf4b5ddc5bbd24ca636edfc7',
    'bar_bt.png': 'c14288c2d869c6f4d92e3a662b5a8ac3eed835c0c9a2f331c5c4da6aeb51fd9d',
    'bar_btcon.png': 'a00eb3eab090ba96c3ccff5f60a1d0db422dd74bf90c9b164886772b8eeea7de',
    'bar_wifi0.png': 'aefe45a64936dcc7ecd00349afd8ab9eb89d234c89573354cfdba77459bde123',
    'bar_wifi1.png': '5db1e3c746b5a350b1b1721cdd8663beaa79452fbc94afb8412b3b02a6e5988f',
    'bar_wifi2.png': '5faaaa65204ed5995acbb5b8afffa05a9f31c1b3450ed1954b48b56b6597451c',
    'bar_wifi3.png': 'e4b52af512a0d9a93d7773dbb91a74793c24dfce7e2b9d309765bf61072d193e',
    'bar_wifi4.png': '4197d12d8f0972b4df801044ff03491b227243a82947f41f5e350b4fbd5073d8',
}
GLYPH_ON, GLYPH_OFF = (255, 255, 255), (0x66, 0x66, 0x66)   # q2-pod status_icon: white / #666666

# The stock orange #FE7E40 left in images, recoloured neutral at build time (V2.1lA, docs/ui.md "Accents"):
# name -> (stock SHA-256, target colour, knob circle (cx, cy, r) or None). Alpha is kept bit for bit.
FILL, THUMB, TILE = (0xEE, 0xEE, 0xEC), (0x77, 0x77, 0x77), (0x33, 0x33, 0x33)   # slider fill / thumb disc / cover tile
KNOB = (42.5, 14, 15)        # the toggles' round knob (right edge of the "on" images)
ACCENT_ART = {
    'pset_dual.png': ('1af1fd22fd00ba42a33bbe4dc1d8f96f160d6afd3708d6387a4fd5fb7d19ca5a', FILL, KNOB),
    'pset_high.png': ('90d0718c13aaaadc45a9c92c395cbaf82d877c11f9d043807b8dbd08fe678d0e', FILL, KNOB),
    'vol_progress.png': ('c76fa2f01c16481819b8857f3bb73a1fa4c0c329cc7f0197db315690408a75ae', FILL, None),
    'volume_fg.png': ('b96519372917f4e96d36d70066a81d2a810c9843eae231ba0a57f9d18c00ca1d', FILL, None),
    'drop_fg.png': ('fb5a48820bc9d4deec246e07f505a84b8eeddbd6f279424500be4515493eaf2e', FILL, None),
    'eq_plan.png': ('d6265a58b756b8d50d527ce1441d5eecda0c044a21f687693caa0e586eeeeb91', FILL, None),
    'other_progress.png': ('946a53aea72b80e4c089ca2bc73e229f3614731ae5148f27b5257b87cf73dd54', FILL, None),
    'cdprogress_bar.png': ('71426218829be81778e7d9d503f795ece73d5c06098e6347b4cf586a8e658304', FILL, None),
    'datetime_back.png': ('e9716de7a2999e2a465cca901d551e34acb8e6a39353244422aa9087808bf2d3', FILL, None),
    'balance_dot.png': ('96b58613949673255e18c014565a9fe980c8ad1ceb00d8aeaf7d6158f30968a4', THUMB, None),
    'light_dot.png': ('5e7e6f1c3d9265d9601bcedaca8cb7b7eb7a9e92b38b93a30786e6cde40f8fc9', THUMB, None),
    'screensaver_defaulticon.png': ('29b5a855eb50e2b27da493bcc4a329f8c50f66f6d7555914ca3c960a4423cbb0', THUMB, None),
    'defaultcover.png': ('8c4f7c9e81c953d0d49c74dba8a9e28d31e099d3665854e6e15a3b6c01c7e10b', TILE, None),
    'scover_default.png': ('ef940f9ff070036976fff9bb7fd3128ce5ebb072603098125424ae547c8febeb', TILE, None),
}

# The on/off switch (sset_on / sset_off, 57x28, used by the stock settings rows, the pull-down-free pages and our own rows):
# redrawn without text, a 46x24 pill track right-aligned in the canvas and a round 18 px knob 3 px in, 8x supersampled. on = the slider-fill off-white track
# with a dark knob (the pull-down's white disc with a dark glyph), off = the edge grey track with the muted grey knob.
# name -> (stock SHA-256, on); theme1 shares sset_off with the default theme (it has no file of its own).
TOGGLE_W, TOGGLE_H = 57, 28                  # the image canvas
PILL_W, PILL_H, TOGGLE_KNOB, TOGGLE_INSET = 46, 24, 18, 3     # the pill, right-aligned in the canvas (x 11, y 2), and its knob
TOGGLE_COLOURS = {True: ((0xEE, 0xEE, 0xEC), (0x14, 0x14, 0x14)), False: ((0x3A, 0x3A, 0x3A), (0x8C, 0x8C, 0x8C))}   # track, knob
TOGGLES = {
    'assets/default/raw/images/xx/sset_on.png': ('d3b8d22e033c3cac37f2939ef469d4852f32cf845f5293bf5c2ad126cd1cdd56', True),
    'assets/default/raw/images/xx/sset_off.png': ('f0bb8014368a088b6523dc627e43d44f36a444735ba8dff169b086619254fa33', False),
    'assets/theme1/raw/images/xx/sset_on.png': ('384730f95a849cfc7524431a9e332f2e3ff7c6e7b5393bad4dc8a18fcb9a303f', True),
}

def toggle_image(on, ss=8):
    """The pill switch: alpha masks drawn at ss x and box-reduced, the knob composited over the track."""
    from PIL import Image, ImageDraw
    w, h, k, m = TOGGLE_W, TOGGLE_H, TOGGLE_KNOB, TOGGLE_INSET
    pw, ph = PILL_W, PILL_H; ox, oy = w - pw, (h - ph) // 2
    track_rgb, knob_rgb = TOGGLE_COLOURS[on]
    def mask(box, radius):
        big = Image.new('L', (w * ss, h * ss), 0)
        ImageDraw.Draw(big).rounded_rectangle([round(v * ss) for v in box[:2]] + [round(v * ss) - 1 for v in box[2:]], radius=round(radius * ss), fill=255)
        return big.resize((w, h), Image.BOX)
    kx = ox + pw - m - k if on else ox + m
    out = Image.new('RGBA', (w, h), track_rgb + (0,)); out.putalpha(mask((ox, oy, ox + pw, oy + ph), ph / 2))
    knob = Image.new('RGBA', (w, h), knob_rgb + (0,)); knob.putalpha(mask((kx, oy + (ph - k) / 2, kx + k, oy + (ph + k) / 2), k / 2))
    out.alpha_composite(knob); return out

def apply_toggles(root):
    from PIL import Image
    import io
    changed = []
    for rel, (pin, on) in sorted(TOGGLES.items()):
        p = os.path.join(root, 'rootfs/release', rel); data = open(p, 'rb').read()
        assert sha256(data) == pin, f'{rel}: not the audited stock image'
        old = Image.open(io.BytesIO(data)); assert old.size == (TOGGLE_W, TOGGLE_H) and old.mode == 'RGBA', f'{rel}: {old.size} {old.mode}'
        out = png_bytes(toggle_image(on))
        assert Image.open(io.BytesIO(out)).size == old.size
        write_keep_mode(p, out); changed.append((rel, len(data), len(out)))
    return changed

def sha256(b): return hashlib.sha256(b).hexdigest()

def write_keep_mode(path, data):
    mode = stat.S_IMODE(os.stat(path).st_mode)
    os.chmod(path, mode | 0o200)
    with open(path, 'wb') as f: f.write(data)
    os.chmod(path, mode)

def _val(key, v): return awtk_style.color_from_str(v) if isinstance(v, str) else v

# ---------------------------------------------------------------- styles/default.bin
def apply_styles(th):
    for widget, style, key, old, new, n in STYLE_EDITS:
        items = th.find(widget, style)
        assert items, f'{widget}/{style}: missing'
        hits = [it for it in items if it.get(key) == _val(key, old)]
        assert len(hits) == n, f'{widget}/{style}.{key}: expected {n} states holding {old}, found {len(hits)}'
        for it in hits: it.set(key, _val(key, new))
    for widget, style, key, typ, value, n in STYLE_ADDS:
        items = th.find(widget, style)
        assert len(items) == n and not any(it.has(key) for it in items), f'{widget}/{style}: unexpected {key}'
        for it in items: it.set(key, value, typ)

# ---------------------------------------------------------------- contrast audit
def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def luminance(rgb): return 0.2126 * _lin(rgb[0]) + 0.7152 * _lin(rgb[1]) + 0.0722 * _lin(rgb[2])
def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)
def over(rgba, under=(0, 0, 0)):
    """'#RRGGBBAA' composited over an opaque colour (rows sit on black windows)."""
    h = rgba.lstrip('#'); r, g, b, a = (int(h[i:i + 2], 16) for i in (0, 2, 4, 6))
    return tuple(round(c * a / 255 + u * (255 - a) / 255) for c, u in zip((r, g, b), under))

def text_styles(th):
    """(widget/style, '#RRGGBBAA') normal-state text colours of label-like styles, opaque ones."""
    out = []
    for it in th.find(state='normal'):
        # row labels: every hscroll_label/label style except the navbar's (titles, lyric tabs)
        if it.widget in ('hscroll_label', 'label') and it.style != 'default' and not it.style.startswith('navbar_'):
            c = it.color('text_color')
            if c and int(c[-2:], 16) > 0x80: out.append((f'{it.widget}/{it.style}', c))
    return out

def audit(th):
    """Every row surface state against every label style a row can hold. Returns the worst
    (contrast, row state, text style) for the rest states and for the pressed state."""
    worst = {'rest': (99, None, None), 'pressed': (99, None, None)}
    texts = text_styles(th)
    for widget, style in ROW_STYLES:
        for it in th.find(widget, style):
            bg = over(it.color('bg_color') or '#00000000')
            assert luminance(bg) < 0.05, f'{widget}/{style}/{it.state}: light row surface {bg}'
            kind = 'pressed' if it.state == 'pressed' else 'rest'
            for name, col in texts:
                if col in (ORANGE, SALMON, '#FF0000FF'): continue   # accent/warning marks, audited apart
                c = contrast(bg, over(col, bg))
                if c < worst[kind][0]: worst[kind] = (c, f'{style}/{it.state} {bg}', f'{name} {col}')
    return worst

def _style_color(w, th, state, key):
    """A widget's colour for key in state: inline style:<state>:key, else its theme style's
    (its `style` or "default", that state, else normal). th is one Theme or a lookup chain
    [window theme, default theme] (searched in that order per state). '#RRGGBBAA' or None."""
    v = w.get(f'style:{state}:{key}')
    if v is not None:
        h = v.lstrip('#'); return '#' + (h + 'FF' if len(h) == 6 else h).upper()
    name = w.get('style', 'default')
    for st in (state, 'normal'):
        for t in (th if isinstance(th, (list, tuple)) else [th]):
            items = t.find(w.type, name, st)
            if items and items[0].has(key): return items[0].color(key)
    return None

PRESSABLE = ('button', 'list_item')
TEXT_TYPES = ('label', 'hscroll_label', 'digit_clock', 'rich_text', 'text_selector', 'edit', 'mledit')

def _ui_contrasts(root, th):
    """{(path, type, name, state): contrast or None} for every text-drawing widget of one ui tree."""
    out = {}
    def visit(w, chain, path):
        chain = chain + [w]; path = f'{path}/{w.type}:{w.name}'
        draws_text = w.type in TEXT_TYPES or (w.get('text') or w.get('tr_text'))
        for state in ('normal', 'pressed') if draws_text else ():
            # "pressed" = a pressed row: buttons and list items take the state, labels inside
            # them and every other ancestor (windows, views) stay normal
            st = lambda x: state if x.type in PRESSABLE else 'normal'
            col = _style_color(w, th, st(w), 'text_color')
            if col is None or int(col[-2:], 16) < 0x80: out[(path, w.type, w.name, state)] = None; continue
            bg = (0, 0, 0)
            for a in chain:          # nearest opaque ancestor wins (bottom-up)
                c = _style_color(a, th, st(a), 'bg_color')
                if c and int(c[-2:], 16) >= 0x80: bg = over(c)
            out[(path, w.type, w.name, state)] = contrast(bg, over(col, bg))
        for i, c in enumerate(w.children): visit(c, chain, f'{path}[{i}]')
    visit(root, [], '')
    return out

def _worse(rel, before, after, threshold):
    """Pairs below threshold that got worse than before (a widget new to the page counts as 21:1 before)."""
    bad = []
    for k, c in after.items():
        b = before.get(k, 21.0)
        if c is not None and b is not None and c < threshold and c < b - 0.01:
            bad.append(f'{rel} {k[1]} {k[2]!r} {k[3]}: {b:.2f} -> {c:.2f}')
    return bad

def page_audit(ui_dir, th_stock, th_mod, threshold=4.5):
    """Every text-bearing widget of every ui/*.bin, in the normal and pressed states: its text
    colour against the nearest opaque background up its ancestors (else the black window),
    with the stock theme and with the mod's. Lists the pairs that drop below threshold and
    got worse. Code-built widgets are covered by audit() instead."""
    import glob
    worse = []
    for f in sorted(glob.glob(os.path.join(ui_dir, '**', '*.bin'), recursive=True)):
        root = awtk_ui.parse(open(f, 'rb').read())
        worse += _worse(os.path.relpath(f, ui_dir), _ui_contrasts(root, th_stock), _ui_contrasts(root, th_mod), threshold)
    return worse

# ---------------------------------------------------------------- whole-tree scan (stacked looks)
# page_audit() runs inside the theme step, on the tree as the theme finds it. Later looks add
# window themes (styles/<window>.bin, searched before default.bin: mod_lists, mod_nowplaying) and
# edit ui files, so build.py re-runs a scan on the finished tree against stock: every ui file
# resolved the way the app loads it (assets/<theme> first, then default), with its window theme in
# front of that asset theme's default.bin, plus audit() of the code-built rows under every window
# theme. Failure = a text/background pair below 4.5:1 that is worse than in the stock tree.
ASSET_THEMES = ('default', 'theme1')

def _load(path): return awtk_style.parse(open(path, 'rb').read()) if path and os.path.exists(path) else None

def _asset(work, theme, kind, rel):
    """assets/<theme>/raw/<kind>/<rel>, falling back to default's (the app's asset lookup)."""
    for t in dict.fromkeys((theme, 'default')):
        p = os.path.join(work, 'rootfs/release/assets', t, 'raw', kind, rel)
        if os.path.exists(p): return p
    return None

def _chain(work, theme, window):
    """[window theme (if any), the asset theme's default.bin] as Theme objects."""
    win = _load(_asset(work, theme, 'styles', window + '.bin')) if window else None
    return [t for t in (win, _load(_asset(work, theme, 'styles', 'default.bin'))) if t]

def _merged(chain):
    """One Theme: the window theme's items, then default's for (widget, style, state) it lacks."""
    seen, items = set(), []
    for t in chain:
        for it in t.items:
            k = (it.widget, it.style, it.state)
            if k not in seen: seen.add(k); items.append(it)
    return awtk_style.Theme(items)

def tree_scan(work, stock, threshold=4.5):
    """Contrast scan of a finished tree against stock: (report lines, failures)."""
    import glob
    report, bad = [], []
    for theme in ASSET_THEMES:
        dirs = lambda kind: [os.path.join(work, 'rootfs/release/assets', t, 'raw', kind) for t in dict.fromkeys((theme, 'default'))]
        rels = sorted({os.path.relpath(f, d) for d in dirs('ui') for f in glob.glob(os.path.join(d, '**', '*.bin'), recursive=True)})
        for rel in rels:
            f_mod, f_stock = _asset(work, theme, 'ui', rel), _asset(stock, theme, 'ui', rel)
            root = awtk_ui.parse(open(f_mod, 'rb').read())
            window = root.get('theme') or root.name or os.path.splitext(os.path.basename(rel))[0]
            after = _ui_contrasts(root, _chain(work, theme, window))
            before = _ui_contrasts(awtk_ui.parse(open(f_stock, 'rb').read()), _chain(stock, theme, window)) if f_stock else {}
            bad += [f'{theme}: {x}' for x in _worse(rel, before, after, threshold)]
        report.append(f'{theme}: {len(rels)} ui files, text vs background (window theme, then default.bin)')
        # code-built rows (audit()): under default.bin alone and under every window theme
        windows = sorted({os.path.splitext(os.path.basename(p))[0] for d in dirs('styles') for p in glob.glob(os.path.join(d, '*.bin'))} - {'default'})
        for window in [None] + windows:
            got, ref = audit(_merged(_chain(work, theme, window))), audit(_merged(_chain(stock, theme, window)))
            for k in ('rest', 'pressed'):
                c, row, text = got[k]
                if row is not None and c < threshold and c < ref[k][0] - 0.01:
                    bad.append(f'{theme}: rows under {window or "default.bin"} ({k}): {c:.2f} ({text} on {row}), stock {ref[k][0]:.2f}')
        worst = {k: min((audit(_merged(_chain(work, theme, w)))[k][0], w or 'default.bin') for w in [None] + windows) for k in ('rest', 'pressed')}
        report.append(f'{theme}: code-built rows under default.bin and {len(windows)} window themes: worst rest '
                      f'{worst["rest"][0]:.2f} ({worst["rest"][1]}), pressed {worst["pressed"][0]:.2f} ({worst["pressed"][1]})')
    return report, bad

# ---------------------------------------------------------------- icons
def recolour_disc(im):
    """q2-pod ringnav_image_add, Minimal 'icon' branch, at build time: each pixel's saturation
    against the icon's most saturated (the disc's) says how far it blends from the disc grey to
    the white glyph; alpha kept. Icons whose disc is already grey are re-levelled so their disc
    lands on the same grey (luma map disc -> DISC, white -> 255)."""
    px = im.load(); w, h = im.size
    ink = [px[x, y] for y in range(h) for x in range(w) if px[x, y][3]]
    disc = max(max(p[:3]) - min(p[:3]) for p in ink)
    if disc:
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if not a: continue
                sat = min(max(r, g, b) - min(r, g, b), disc)
                v = 255 - (255 - DISC) * sat // disc
                px[x, y] = (v, v, v, a)
    else:   # grey disc: the most common opaque value is the disc
        vals = {}
        for p in ink:
            if p[3] == 255: vals[p[0]] = vals.get(p[0], 0) + 1
        dv = max(vals, key=vals.get)
        assert dv < 200, 'grey icon without a disc?'
        for y in range(h):
            for x in range(w):
                r, g, b, a = px[x, y]
                if not a: continue
                v = DISC + (r - dv) * (255 - DISC) // (255 - dv) if r >= dv else r * DISC // dv
                px[x, y] = (v, v, v, a)
    return im

def draw_status(name, size):
    """q2-pod status_icon redrawn with PIL: one stroke weight, round caps, rendered at 4x."""
    from PIL import Image, ImageDraw
    S = 4; w, h = size
    im = Image.new('RGBA', (w * S, h * S), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    P = lambda pts: [(x * S, y * S) for x, y in pts]
    def line(pts, col, width):
        d.line(P(pts), fill=col + (255,), width=round(width * S), joint='curve')
        for x, y in pts:   # round caps
            r = width * S / 2; d.ellipse((x * S - r, y * S - r, x * S + r, y * S + r), fill=col + (255,))
    if name == 'bar_play.png':          # 14x18: a filled triangle with softened corners
        tri = [(3, 3), (12.5, 9), (3, 15)]
        d.polygon(P(tri), fill=GLYPH_ON + (255,)); line(tri + [tri[0]], GLYPH_ON, 1.4)
    elif name == 'bar_pause.png':       # 14x18: two rounded bars
        line([(4.2, 3.8), (4.2, 14.2)], GLYPH_ON, 3.0); line([(9.8, 3.8), (9.8, 14.2)], GLYPH_ON, 3.0)
    elif name.startswith('bar_wifi'):   # 24x16: concentric arcs round a dot, lit per level 0..4
        import math
        level = int(name[8]); cx, cy = 12, 13.4
        for i, r in enumerate((11.4, 7.8, 4.2)):         # outer arc lit at 4, middle at 3, inner at 2
            col = GLYPH_ON if level >= 4 - i else GLYPH_OFF
            pts = [(cx + r * math.sin(math.radians(a)), cy - r * math.cos(math.radians(a))) for a in range(-44, 45, 4)]
            line(pts, col, 1.9)
        col = GLYPH_ON if level else GLYPH_OFF
        r = 1.7; d.ellipse(((cx - r) * S, (cy - r) * S, (cx + r) * S, (cy + r) * S), fill=col + (255,))
    elif name in ('bar_bt.png', 'bar_btcon.png'):   # 47x20, glyph at the right end like stock (ink 35..47)
        col = GLYPH_ON if name == 'bar_btcon.png' else GLYPH_OFF
        line([(36.5, 6.5), (45.5, 13.8), (41, 17.8), (41, 2.2), (45.5, 6.2), (36.5, 13.5)], col, 1.7)
    else: raise ValueError(name)
    return im.resize((w, h), Image.LANCZOS)

def png_bytes(im):
    import io
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True); return b.getvalue()   # no metadata chunks

def accent_to(im, target, knob=None):
    """The orange of a stock image to `target`: per pixel the HSV saturation against the accent's says
    how far it is orange (t), its value how bright (shading and dark text on the orange keep their
    relative depth); the grey part (min channel) is kept. A `knob` circle (the toggles) is turned dark
    grey by luma, so on = dark knob on a white track (the pull-down's white disc with a dark glyph).
    Alpha is untouched."""
    import colorsys
    px = im.load(); sat_a = (254 - 64) / 254
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = px[x, y]
            if not a: continue
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            t = min(1.0, s / sat_a) if h <= 0.12 else 0.0
            if knob and t < 0.5 and (x - knob[0]) ** 2 + (y - knob[1]) ** 2 <= knob[2] ** 2:
                n = max(0, min(255, round(0x20 + ((r * 299 + g * 587 + b * 114) / 1000 - 150) * 0.25)))
                px[x, y] = (n, n, n, a); continue
            m = min(r, g, b); k = (v * 255 / 254) ** 1.5
            px[x, y] = (*(round(m * (1 - t) + t * min(255, c * k)) for c in target), a)
    return im

def apply_accents(root):
    from PIL import Image
    import io
    changed = []
    for name, (pin, target, knob) in sorted(ACCENT_ART.items()):
        p = os.path.join(root, IMG, name); data = open(p, 'rb').read()
        assert sha256(data) == pin, f'{name}: not the audited stock image'
        im = Image.open(io.BytesIO(data)); assert im.mode == 'RGBA', f'{name}: {im.mode}'
        out = png_bytes(accent_to(im.copy(), target, knob))
        o = Image.open(io.BytesIO(out)); assert o.size == im.size and o.mode == 'RGBA'
        assert o.getchannel('A').tobytes() == im.getchannel('A').tobytes(), f'{name}: alpha changed'
        write_keep_mode(p, out); changed.append((name, len(data), len(out)))
    return changed

def apply_icons(root):
    from PIL import Image
    import io
    changed = []
    for name, pin in sorted(SETTINGS_ICONS.items()):
        p = os.path.join(root, IMG, name); data = open(p, 'rb').read()
        assert sha256(data) == pin, f'{name}: not the audited stock icon'
        im = Image.open(io.BytesIO(data)); assert im.size == (40, 40) and im.mode == 'RGBA', f'{name}: {im.size} {im.mode}'
        out = png_bytes(recolour_disc(im.copy()))
        o = Image.open(io.BytesIO(out)); assert o.size == (40, 40) and o.mode == 'RGBA'
        assert o.getchannel('A').tobytes() == im.getchannel('A').tobytes(), f'{name}: alpha changed'
        write_keep_mode(p, out); changed.append((name, len(data), len(out)))
    for name, pin in sorted(STATUS_ICONS.items()):
        p = os.path.join(root, IMG, name); data = open(p, 'rb').read()
        assert sha256(data) == pin, f'{name}: not the audited stock icon'
        im = Image.open(io.BytesIO(data)); assert im.mode == 'RGBA'
        out = png_bytes(draw_status(name, im.size))
        assert Image.open(io.BytesIO(out)).size == im.size
        write_keep_mode(p, out); changed.append((name, len(data), len(out)))
    return changed

# ---------------------------------------------------------------- ui/system_bar.bin
def apply_bar(root):
    """The real bar; tools/statusbar.py holds the table (the pull-down's copy of the bar is laid out from it too)."""
    left, right, clock = root.find('view_bar_left'), root.find('view_bar_right'), root.find('bar_dclock')
    vol, pg, img = root.find('label_volume'), root.find('pgbar_battery'), root.find('img_battery')
    assert all(w is not None for w in (left, right, clock, vol, pg, img)), 'unexpected system_bar layout'
    # stacks on mod_battery.py (the 22x12 outline over a horizontal fill, no number)
    assert (pg.get('show_text') == 'false' and pg.get('vertical') == 'false' and img.get('visible') != 'false'
            and (img.w, img.h) == (22, 12) and pg.x == img.x + 2), 'system_bar.bin is not the mod_battery.py layout (run it first)'
    assert left.get('children_layout') == 'default(r=1,c=0,x=14,s=4)'
    assert right.get('children_layout') == 'default(r=1,c=0,a=right,s=5)'
    assert clock.get('self_layout') == 'default(x=108,y=0,w=90,h=100%)'
    assert all(vol.get(f'style:{st}:font_size') == '20' for st in statusbar.STATES)
    statusbar.apply(root)

# ---------------------------------------------------------------- ui/home_page.bin
def apply_home(root):
    strip, artist, dots = root.find('home_bottomview'), root.find('home_scrlabel_artist'), root.find('home_sindicator')
    assert strip and artist and dots and root.find('home_sview') and root.find('home_img_icon'), 'unexpected home_page layout'
    assert strip.get('style:normal:bg_color') == '#131313'
    strip.set('style:normal:bg_color', '#000000')
    strip.set('style:normal:border', 'top')               # string form, as stock pages write it
    strip.set('style:normal:border_color', '#222222')
    strip.set('style:normal:border_width', '1')
    assert artist.get('style:normal:text_color') == '#FFFFFF'
    artist.set('style:normal:text_color', '#AAAAAA')       # stock secondary grey, as the M1+ Music pages
    assert dots.get('style:normal:selected_fg_color') == '#FFFFFF' and dots.get('style:normal:fg_color') == '#666666'
    dots.set('style:normal:selected_fg_color', '#EEEEEE')  # q2-pod's page dots
    dots.set('style:normal:fg_color', '#555555')

# ---------------------------------------------------------------- main
def apply(out):
    p = os.path.join(out, STYLE); old = open(p, 'rb').read()
    assert sha256(old) == STYLE_SHA, f'{STYLE}: not the audited stock theme ({sha256(old)})'
    th = awtk_style.parse(old); th_stock = awtk_style.parse(old)
    assert awtk_style.serialize(th) == old, 'styles/default.bin round trip is not byte-exact'
    before = audit(th)
    apply_styles(th)
    after = audit(th)
    assert after['rest'][0] >= 4.5 and after['pressed'][0] >= 4.5, f'contrast too low: {after}'
    worse = page_audit(os.path.join(out, RAW, 'ui'), th_stock, th)
    for line in worse: print('  page contrast:', line)
    assert not worse, 'a ui page lost contrast below 4.5:1'
    new = awtk_style.serialize(th)
    assert awtk_style.serialize(awtk_style.parse(new)) == new
    write_keep_mode(p, new)
    print(f'theme: {STYLE} {len(old)} -> {len(new)} bytes, {len(STYLE_EDITS)} edits + {len(STYLE_ADDS)} additions')
    for k in ('rest', 'pressed'):
        print(f'  worst row/text contrast ({k}): stock {before[k][0]:.2f} ({before[k][2]} on {before[k][1]}), '
              f'mod {after[k][0]:.2f} ({after[k][2]} on {after[k][1]})')
    icons = apply_icons(out)
    print(f'theme: {len(icons)} images, {sum(a for _, a, _ in icons)} -> {sum(b for _, _, b in icons)} bytes')
    acc = apply_accents(out)
    print(f'theme: {len(acc)} accent images neutral, {sum(a for _, a, _ in acc)} -> {sum(b for _, _, b in acc)} bytes')
    tg = apply_toggles(out)
    print(f'theme: {len(tg)} switch images redrawn, {sum(a for _, a, _ in tg)} -> {sum(b for _, _, b in tg)} bytes')
    o, n, _ = edit_ui(os.path.join(out, BAR), apply_bar); print(f'theme: {BAR} {len(o)} -> {len(n)} bytes')
    o, n, _ = edit_ui(os.path.join(out, HOME), apply_home); print(f'theme: {HOME} {len(o)} -> {len(n)} bytes')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--scan', action='store_true', help='SRC = finished tree, OUT = stock tree: contrast scan only')
    a = ap.parse_args()
    if a.scan:
        report, bad = tree_scan(a.src, a.out)
        for line in report: print('scan:', line)
        for line in bad: print('scan: FAIL', line)
        if bad: sys.exit('mod_theme --scan: text lost contrast below 4.5:1')
        print('scan: ok, no text below 4.5:1 that got worse than stock'); return
    clone_workdir(a.src, a.out)
    apply(a.out)

if __name__ == '__main__': main()
