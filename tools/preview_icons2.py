#!/usr/bin/env python3
"""docs/icons2-preview.png: the round-2 icons (docs/ui.md "Icon audit") before and after, per place they are used.

  preview_icons2.py BEFORE_TREE AFTER_TREE OUT.png        (unpacked work trees; venv python)

Each item shows the stock image above and the release image below, at 2x when small. Markers on the "after"
image: blue C = custom Tabler-style SVG, orange K = stock image kept (the audit decided it is decent or not an
icon), green R = stock line art recoloured. Approximate (PIL), device pixels scaled with nearest neighbour.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
import mod_icons as M
from stb_raster import StbFont

RAW = 'rootfs/release/assets/default/raw'
W, PAD, ROW_GAP = 660, 12, 10
ANN = ImageFont.load_default(12); ANN_B = ImageFont.load_default(15)
KIND = {'icon_genre': 'C', 'icon_cdgenres': 'C', 'icon_playing': 'K', 'sset_on': 'K', 'other_progress': 'K',
        'vol_add': 'K', 'airplay': 'K', 'dlna': 'K', 'p_mqa': 'K', 'mqa_icon': 'K', 'introduction': 'K', 'led_select': 'K'}
KIND.update({n: 'R' for n in M.RECOLOUR})
# (section, [(label, image name, pressed name or None)]); a name with no change in the release is a kept stock image
SECTIONS = [
    ('Navbar actions on the stock pages (normal | pressed)', [
        ('add', 'add', 'add_down'), ('cancel', 'cancel', 'cancel_down'), ('delete', 'delete', 'delete_down'),
        ('multi-select', 'mulselect', 'mulselect_down'), ('sort / order', 'songsort', 'songsort_down'), ('search', 'search', 'search_down'),
        ('back', 'return', 'return_down'), ('chevron', 'right_arrow', 'right_arrow_down'), ('more', 'list_more', 'list_moredown'),
        ('settings', 'dac_set', 'dac_setdown'), ('to player (Lucide)', 'back_to_player', 'back_to_player_down')]),
    ('List affordances: selection marks, expanders, mode glyphs', [
        ('not selected', 'unselect', None), ('selected', 'mulselected', None), ('radio on', 'selected', None),
        ('check off', 'cdselected', None), ('check on', 'selecting', None), ('expand', 'expansion', None), ('collapse', 'expansion_2', None),
        ('artist albums', 'albumsinger', None), ('artist songs', 'songsinger', None), ('shuffle', 'p_random', None),
        ('repeat', 'p_cycle', None), ('repeat one', 'p_cycle1', None), ('in order', 'p_order', None)]),
    ('Folders rows: SD / USB / folder / file (one glyph for every audio format) / playing', [
        ('folder', 'icon_folder', None), ('SD card', 'icon_tf', None), ('USB', 'icon_otg', None), ('FLAC', 'icon_flac', None),
        ('MP3', 'icon_mp3', None), ('DSF', 'icon_dsf', None), ('playing (kept)', 'icon_playing', None)]),
    ('Playlists page: New playlist / Import / Export / each playlist and Favourites', [
        ('new playlist', 'playlist_add', None), ('import', 'playlist_import', None), ('export', 'playlist_export', None),
        ('a playlist', 'icon_playlist', None)]),
    ('Other submenus: Artists / Genres / Composers / Albums rows, search result rows, CD track dialog', [
        ('artist', 'icon_artist', None), ('genre', 'icon_genre', None), ('composer', 'icon_composer', None), ('album', 'icon_cdalbum', None),
        ('genre (CD)', 'icon_cdgenres', None), ('artist (CD)', 'icon_cdsonger', None), ('year (CD)', 'icon_cdyears', None)]),
    ('Dialogs: Now Playing more, batch add, rename / delete, speed, Wi-Fi, keyboard, Play all', [
        ('A-B repeat', 'p_abrepeat', None), ('add', 'p_add', None), ('delete', 'p_delete', None), ('multi', 'p_multiple', None),
        ('online search', 'p_onlinesearch', None), ('album info', 'player_albuminfo', None), ('artist info', 'player_songerinfo', None),
        ('add to fav', 'batchadd_fav', None), ('add to list', 'batchadd_playlist', None), ('rename', 'rename', None),
        ('delete net', 'bt_del', None), ('scan', 'bt_scan', None), ('date', 'datetime', None), ('add net', 'wifi_add', None),
        ('show', 'kb_visible', None), ('hide', 'kb_invisible', None), ('1.0x', 'p_1', None), ('1.0x on', 'p_1_sel', None),
        ('1.25x', 'p_1_25', None), ('2.0x on', 'p_2_sel', None), ('Wi-Fi 1', 'wifi_1', None), ('Wi-Fi 4', 'wifi_4', None),
        ('Play all', 'playall', 'playall_down'), ('EQ custom', 'eq_custom', None), ('EQ blues', 'eq_blues', None), ('EQ vocal', 'eq_vocal', None),
        ('play', 'play', None), ('pause', 'pause', None), ('next', 'next', 'next_down'), ('prev', 'prev', 'prev_down')]),
]

def load(tree, n):
    return Image.open(os.path.join(tree, RAW, 'images/xx', n + '.png')).convert('RGBA')

def cell(tree, n, scale):
    im = load(tree, n)
    if scale > 1: im = im.resize((im.width * scale, im.height * scale), Image.NEAREST)
    bg = Image.new('RGBA', im.size, (0, 0, 0, 255)); bg.alpha_composite(im); return bg

def main():
    before, after, out = sys.argv[1:4]
    items = []
    for title, row in SECTIONS:
        items.append(title)
        for label, n, down in row:
            names = [n] + ([down] if down else [])
            scale = 2 if all(max(load(after, k).size) <= 40 and max(load(before, k).size) <= 40 for k in names) else 1
            items.append((label, names, scale))
    # layout: flow items left to right, wrap at W
    pos, x, y, rowh, flows = [], PAD, 26, 0, []
    for it in items:
        if isinstance(it, str):
            if rowh: y += rowh + ROW_GAP; x, rowh = PAD, 0
            pos.append((it, PAD, y)); y += 20; continue
        label, names, scale = it
        sizes = [max(load(before, k).size[0], load(after, k).size[0]) * scale for k in names]
        ch = max(max(load(before, k).size[1], load(after, k).size[1]) * scale for k in names)
        cw = max(sum(sizes) + 6 * (len(names) - 1), 74)
        if x + cw > W - PAD: y += rowh + ROW_GAP; x, rowh = PAD, 0
        pos.append((it, x, y)); x += cw + 12; rowh = max(rowh, 2 * ch + 22)
        flows.append(ch)
    H = y + rowh + 24
    sh = Image.new('RGBA', (W, H), (0x2A, 0x2A, 0x2A, 255)); d = ImageDraw.Draw(sh)
    d.text((PAD, 6), 'Round 2 icons: stock above, release below (2x when small). C custom SVG, K stock kept, R stock art recoloured.', fill=(255, 255, 255), font=ANN)
    for it, x, y in pos:
        if isinstance(it, str): d.text((x, y), it, fill=(0xAA,) * 3, font=ANN_B); continue
        label, names, scale = it
        ch = max(max(load(before, k).size[1], load(after, k).size[1]) * scale for k in names)
        for row, tree in enumerate((before, after)):
            cx = x
            for k in names:
                c = cell(tree, k, scale); sh.alpha_composite(c, (cx, y + row * (ch + 4))); cx += c.width + 6
                if row == 1 and KIND.get(k):
                    d.text((cx - 6 - 9, y + ch + 4 + 1), KIND[k], font=ANN, fill={'C': (90, 170, 255), 'K': (255, 150, 40), 'R': (110, 220, 120)}[KIND[k]])
        d.text((x, y + 2 * ch + 8), label, fill=(0xCC,) * 3, font=ANN)
    sh.convert('RGB').save(out, optimize=True); print('wrote', out)

if __name__ == '__main__': main()
