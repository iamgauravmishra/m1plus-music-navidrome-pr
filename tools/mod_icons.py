#!/usr/bin/env python3
"""Icon set for the Shanling M1 Plus UI: Tabler Icons (MIT) in the Minimal look. Asset-only.
Description, mapping table, substitutes and what stays stock: docs/ui.md.

Replaces, in the default theme's images/xx (same file names, same pixel size, RGBA PNG, same
file mode):
  46 settings icons    40x40, white Tabler glyph (stroke 2) on the #777777 disc
  18 Home icons        66x66 (+ 17 pressed `_down`), white glyph on the #777777 disc (#555555 pressed)
  pull-down tiles      50x50, one ring style for every tile (docs/ui.md): #777777 ring + glyph = off,
                       white disc + dark glyph = on, #444444 = disabled; Tabler glyphs, custom gain bars,
                       "PO"/"LO" in Inter; backlight sun icons 20x20
  status bar           play/pause (filled), volume 0-4, Wi-Fi 0-4 (unlit arcs #666666), Bluetooth,
                       digital out; stroke 1.5 px at 14-16 px, 2 px at 20 px
  list placeholders    6 folder/playlist/artist/genre/composer/album discs, albumcover s/m/info tiles
  round 2 (docs/ui.md "Icon audit"): navbar actions, chevrons, selection marks, dialog actions as plain white
                       glyphs at the stock size (pressed #777777); Folders file/SD/USB rows, Playlists page
                       and CD-ripper discs; equaliser preset art recoloured white; speed badges, the Play all
                       pill, secured Wi-Fi rows; the Now Playing np_* glyphs (mod_nowplaying.py copies them)
Stays stock: brand art and text badges (codec badges, SyncLink, DAC/DSD/A-B), theme1
(its own image files), the battery (tools/battery_art.py draws it for mod_battery/mod_lockscreen).

Build time only copies the committed PNGs (assets/icons/tabler/png/); builds stay deterministic and
need no rasteriser. The PNGs are generated from the committed SVG sources
(assets/icons/tabler/svg/, @tabler/icons 3.49.0, MIT) by --generate (needs rsvg-convert and Pillow).

Usage: mod_icons.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place; a build.py step)
       mod_icons.py --generate                  rebuild assets/icons/tabler/png from svg/
       mod_icons.py --fetch TGZ                 copy the used SVGs + LICENSE out of an @tabler/icons tarball
                                                (SHA-256 pinned; parsed as data, nothing is executed)
       mod_icons.py --check [WORKDIR]           verify the asset PNGs (+ a work tree) against the stock pins
"""
import argparse, hashlib, io, os, re, shutil, stat, subprocess, sys, tarfile
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths
from modlib import clone_workdir, edit_ui, write_keep_mode
import pod_i18n

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSET = os.path.join(ROOT, 'assets', 'icons', 'tabler')
SVG, PNG = os.path.join(ASSET, 'svg'), os.path.join(ASSET, 'png')
IMG = 'rootfs/release/assets/default/raw/images/xx'
TGZ_SHA = 'aa3042907eb0bdb079fd70733e2d75f785683d4726279128a0ca2343099f7074'   # @tabler/icons 3.49.0
WHITE, DISC, DISC_DOWN, OFF = (255, 255, 255), (0x77,) * 3, (0x55,) * 3, (0x66,) * 3

# ---------------------------------------------------------------- mapping (stock image -> Tabler glyph)
# glyph: a Tabler name; '+name' = custom SVG in assets/icons/custom/ drawn in Tabler's style (no Tabler
# match); None = stock image kept (text badge or a fitting stock art; Minimal-recoloured already).
HOME = [  # Home ids 1..17 in English order, HiFi (id 0, zh_CN only) last
    ('tidal', 'TIDAL (online only)', 'brand-tidal'), ('sset_updatemusic', 'Update Library', 'refresh'),
    ('mymusic', 'All Songs', 'music'), ('folder', 'Folders', 'folder'), ('album', 'Albums', 'vinyl'),
    ('songer', 'Artists', 'microphone-2'), ('genre', 'Genres', '+guitar'), ('composer', 'Composers', 'feather'),
    ('hr', 'Hi-Res', '+badge-hr'), ('fav', 'Favorites', 'heart'), ('many', 'Most Played', 'flame'),
    ('recent', 'Recently Played', 'history'), ('recentadd', 'Recently Added', 'clock-plus'),
    ('playlist', 'Playlists', 'playlist'), ('cdripper', 'CD Ripper', 'disc'), ('playset', 'Play Settings', 'adjustments'),
    ('sysset', 'System Settings', 'settings'), ('hifimusic', 'HiFi Store (zh_CN)', 'building-store'),
]
SETTINGS = [  # the 46 40x40 settings icons
    ('playset_foldercover', 'Folder cover', 'photo'), ('pset_balance', 'Balance', 'scale'),
    ('pset_bootvol', 'Boot volume', 'volume-2'), ('pset_covermode', 'Cover mode', 'maximize'),
    ('pset_dac', 'DAC', None), ('pset_digital', 'Digital output', 'plug-connected'),
    ('pset_dsdoutput', 'DSD output', None), ('pset_eq', 'Equalizer', 'adjustments-alt'),
    ('pset_filter', 'Digital filter', 'wave-sine'), ('pset_gain', 'Gain', 'gauge'),
    ('pset_gapless', 'Gapless', 'infinity'), ('pset_jumpfolder', 'Jump folder', 'folder-symlink'),
    ('pset_maxvol', 'Max volume', 'volume'), ('pset_memplay', 'Resume play', 'bookmark'),
    ('pset_playmode', 'Play mode', 'repeat'), ('pset_replaygain', 'ReplayGain', None),
    ('pset_usbaudiovol', 'USB audio volume', 'usb'), ('screensaver_info', 'Show info', 'info-circle'),
    ('screensaver_timeshow', 'Show time', 'clock'), ('sset_about', 'About', 'info-circle'),
    ('sset_atmosphereled', 'LED light', 'bulb'), ('sset_carmode', 'Car mode', 'car'),
    ('sset_covermode', 'Cover mode', 'maximize'), ('sset_display', 'Display', 'sun'),
    ('sset_doublewake', 'Double-tap wake', 'hand-click'), ('sset_dsdoutput', 'DSD output', None),
    ('sset_keylock', 'Key lock', 'lock'), ('sset_lighttime', 'Backlight time', 'stopwatch'),
    ('sset_netservice', 'Network services', 'world'), ('sset_outputway', 'Output', 'headphones'),
    ('sset_powermanager', 'Power', 'power'), ('sset_prove', 'Certification', 'certificate'),
    ('sset_screenlock', 'Screen lock', 'lock-square'), ('sset_system', 'System update', 'circle-arrow-up'),
    ('sset_theme', 'Theme', 'palette'), ('sset_tswake', 'Touch wake', 'hand-finger'),
    ('sset_usbaudiovol', 'USB audio volume', 'usb'), ('sset_usbmode', 'USB mode', 'usb'),
    ('sset_wifiset', 'Wi-Fi', 'wifi'), ('system_formatcard', 'Format card', 'device-sd-card'),
    ('system_language', 'Language', 'language'), ('system_reset', 'Reset', 'rotate'),
    ('system_scrotate', 'Screen rotation', 'device-mobile-rotated'), ('system_time', 'Date & time', 'calendar'),
    ('system_update', 'Firmware update', 'download'), ('usb_chargeswitch', 'USB charging', 'battery-charging'),
]
PULLDOWN = {  # glyph per tile
    'drop_wifi': 'wifi', 'drop_bt': 'bluetooth', 'drop_keylock': 'lock', 'drop_eq': 'adjustments-alt',
    'drop_usbaudio': 'usb', 'drop_usbdac': '+dac', 'drop_usbstorage': 'device-usb',
    'drop_playset': 'adjustments', 'drop_sysset': 'settings',
    'drop_lighticon0': 'sun-low', 'drop_lighticon1': 'sun-high',
}
STATUS = {'bar_play': 'player-play', 'bar_pause': 'player-pause', 'bar_vol0': 'volume-4', 'bar_vol1': 'volume-2',
          'bar_vol2': 'volume', 'bar_vol3': '+volume-3waves', 'bar_vol4': 'volume-3', 'bar_wifi': 'wifi',
          'bar_bt': 'bluetooth', 'bar_digital': 'plug-connected'}
WIFI_LEVELS = [None, 'wifi-0', 'wifi-1', 'wifi-2', 'wifi']     # index = bar_wifi0..4
LISTS = [('icon_folder', 'folder', 'folder'), ('icon_playlist', 'playlist', 'playlist'),
         ('icon_artist', 'artist', 'microphone-2'), ('icon_genre', 'genre', '+guitar'),
         ('icon_composer', 'composer', 'feather'), ('icon_cdalbum', 'album', 'vinyl')]
COVERS = ['albumcover_s', 'albumcover_m', 'albumcover_info']   # the "no cover" placeholder, 60/90/100 px
COVER_GLYPH = 'vinyl'
# M1 Pod menu and Shuffle page rows: label -> (added image, glyph). 40 px #777777 disc, left of the title.
# '@shanling' = the brand mark cut out of a stock image (shanling_mark below), not a glyph.
POD_ROWS = {'Now Playing': ('pod_ic_nowplaying', '+audio-lines'), 'Cover Flow': ('pod_ic_coverflow', 'carousel-horizontal'),   # audio-lines: Lucide, the wave of the navbar's Now Playing button
            'Shuffle': ('pod_ic_shuffle', 'arrows-shuffle'), 'Songs': ('pod_ic_songs', 'music'),
            'Albums': ('pod_ic_albums', 'vinyl'), 'Artists': ('pod_ic_artists', 'microphone-2'),
            'Genres': ('pod_ic_genres', '+guitar'), 'Folders': ('pod_ic_folders', 'folder'),
            'Playlists': ('pod_ic_playlists', 'playlist'), 'Settings': ('pod_ic_settings', 'settings'), 'Extras': ('pod_ic_extras', 'dots'),
            'Shuffle Songs': ('pod_ic_shufsongs', 'music'), 'Shuffle Albums': ('pod_ic_shufalbums', 'vinyl'),
            'Shuffle Folders': ('pod_ic_shuffolders', 'folder'),
            # the Settings page's rows: the launcher's two, the customise page and the Cover Flow switch
            'Shanling Home': ('pod_ic_shanling', '@shanling'), 'Start in M1 Pod': ('pod_ic_startup', 'home'),
            'Main Menu': ('pod_ic_mainmenu', 'list-check'),
            # Settings > Cover Flow (the Settings page's Cover Flow row uses the menu's carousel disc)
            'Landscape': ('pod_ic_landscape', 'rotate-clockwise'), 'Sort': ('pod_ic_sort', 'sort-descending'),
            # the Extras page (the stock Home tiles the menu does not repeat; glyphs as the Home grid's)
            'Favorites': ('pod_ic_fav', 'heart'), 'Recently Added': ('pod_ic_recentadd', 'clock-plus'),
            'Recently Played': ('pod_ic_recent', 'history'), 'Most Played': ('pod_ic_most', 'flame'),
            'Composers': ('pod_ic_composers', 'feather'), 'Hi-Res': ('pod_ic_hires', '+badge-hr'),
            'Update Library': ('pod_ic_update', 'refresh'), 'Tidal': ('pod_ic_tidal', 'brand-tidal'),
            'CD Ripper': ('pod_ic_cdripper', 'disc'),
            # the Settings page (the menu's Settings row opens it)
            'System Settings': ('pod_ic_settings', 'settings'), 'Playback': ('pod_ic_playset', 'adjustments')}
# The "M1 Pod" icon patch/home.c adds to the stock Home grid (id 99): 66x66 like the stock Home icons
# (white click-wheel glyph on the #777777 disc, #555555 pressed), style home_m1pod_style in home_page.bin.
POD_HOME = ('m1pod', 'm1pod_down')
POD_HOME_GLYPH, POD_HOME_STYLE = '+click-wheel', 'home_m1pod_style'
POD_UI = ['m1pod_menu', 'm1pod_shuffle', 'm1pod_settings', 'm1pod_extras', 'm1pod_mainmenu', 'm1pod_cfset']
# The navbar toggles (tools/pod_ui.py NAV_VIEW_ICON, patch/albums.c, patch/artists.c): the glyph of the view a tap switches to, a plain
# 24 px white glyph like the navbar's others (pressed #777777), added to the images.
NAV_VIEW = {'pod_nav_grid': 'layout-grid', 'pod_nav_list': 'list',
            'pod_nav_artist': 'microphone-2', 'pod_nav_albumartist': 'user-star'}   # the Artists page's Artist / Album Artist switch
NAV_PX = 24
POD_ICON_X, POD_ICON = 12, 40          # the disc: x 12..52 in the 52 px row (y 6); the title starts at 64
POD_TEXT_X = 64

# ---- round 2 (docs/ui.md "Icon audit"): the stock images the pages and dialogs still showed.
# Plain glyph images at the stock size: white (pressed `_down`: #777777), no disc. 'name:filled' = Tabler's
# filled style. (stock image, glyph, pressed image or None); each file keeps its own size.
GLYPHS = [
    # navbar actions and list affordances
    ('add', 'plus', 'add_down'), ('back_to_player', '+audio-lines', 'back_to_player_down'),   # Lucide (ISC), assets/icons/lucide/
     ('cancel', 'x', 'cancel_down'), ('delete', 'trash', 'delete_down'),
    ('mulselect', 'list-check', 'mulselect_down'), ('songsort', 'sort-descending', 'songsort_down'),
    ('tidal_sort', 'sort-descending', 'tidal_sort_down'), ('search', 'search', 'search_down'),
    ('return', 'chevron-left', 'return_down'), ('right_arrow', 'chevron-right', 'right_arrow_down'),
    ('list_more', 'dots', 'list_moredown'), ('p_more', 'dots', 'p_moredown'),
    ('dac_set', 'settings', 'dac_setdown'), ('rippersystem', 'settings', 'rippersystem_down'),
    ('expansion', 'chevron-down', 'expansion_down'), ('expansion_2', 'chevron-up', 'expansion_2_down'),
    ('albumsinger', 'vinyl', None), ('songsinger', 'music', None),
    ('p_random', 'arrows-shuffle', None), ('p_cycle', 'repeat', None), ('p_cycle1', 'repeat-once', None),    # the queue dialog's mode
    ('p_order', 'repeat-off', None),
    ('mulselected', 'circle-check:filled', None), ('selected', 'circle-check:filled', None),
    ('screensaver_selected', 'circle-check:filled', None), ('unselect', 'circle', None),
    ('screensaver_unselect', 'circle', None), ('cdselected', 'square', None), ('selecting', 'square-check', None),
    # transport glyphs of the pages without the Now Playing look (Bluetooth receiver, USB DAC, AirPlay)
    ('play', 'player-play:filled', None), ('pause', 'player-pause:filled', None),
    ('next', 'player-skip-forward:filled', 'next_down'), ('prev', 'player-skip-back:filled', 'prev_down'),
    # actions in dialogs and pages
    ('rename', 'pencil', None), ('bt_del', 'trash', None), ('bt_scan', 'refresh', None), ('datetime', 'calendar', None),
    ('wifi_add', 'circle-plus', None), ('kb_visible', 'eye', None), ('kb_invisible', 'eye-off', None),
    ('p_abrepeat', 'a-b', None), ('p_add', 'playlist-add', None), ('p_delete', 'trash', None),
    ('p_multiple', 'multiplier-1x', None), ('p_onlinesearch', 'world-search', None),
    ('player_albuminfo', 'vinyl', None), ('player_songerinfo', 'microphone-2', None),
    ('batchadd_fav', 'heart', None), ('batchadd_playlist', 'playlist-add', None),
]
GREY_GLYPHS = {'kb_visible': 0x8C, 'kb_invisible': 0x8C}     # the password eye was grey in stock
# 40 px #777777 discs (Folders rows, Playlists page, the CD ripper's track dialog)
FORMATS = ['aac', 'aiff', 'alac', 'ape', 'dff', 'dsf', 'dts', 'flac', 'iso', 'm4a', 'mp2', 'mp3', 'ogg', 'opus', 'wav', 'wma']
DISCS = [('icon_' + f, 'file-music') for f in FORMATS] + [
    ('icon_tf', 'device-sd-card'), ('icon_otg', 'device-usb'), ('icon_cdgenres', '+guitar'), ('icon_cdsonger', 'microphone-2'),
    ('icon_cdyears', 'calendar'), ('playlist_add', 'playlist-add'), ('playlist_import', 'file-import'),
    ('playlist_export', 'file-export')]
# stock line art kept (instruments, text) and only recoloured white: the orange of the equaliser preset icons
RECOLOUR = ['eq_blues', 'eq_classical', 'eq_custom', 'eq_dance', 'eq_jazz', 'eq_metal', 'eq_pop', 'eq_rock', 'eq_vocal']
# playback-speed badges (36x20 text): grey outline, white when selected
SPEEDS = {'p_1': ('1.0X', 0), 'p_1_sel': ('1.0X', 1), 'p_1_25': ('1.25X', 0), 'p_1_25_sel': ('1.25X', 1),
          'p_1_5': ('1.5X', 0), 'p_1_5_sel': ('1.5X', 1), 'p_2': ('2.0X', 0), 'p_2_sel': ('2.0X', 1)}
PLAYALL = {'playall': 0, 'Play_all': 0, 'playall_down': 1, 'Play_all_down': 1}      # 90x28 "Play all" pills
WIFI_LOCK = {f'wifi_{i}': i for i in range(1, 5)}                                    # secured network, level 1..4
# Now Playing (mod_nowplaying.py copies these): name -> (glyph, canvas px or (w, h), max ink px, tone, pressed name or None
# [, disc px]). 'pil:NAME' = the solid glyph drawn with PIL (g_play ... below; the transport glyphs, which read better than
# Tabler's filled ones); a disc px puts a translucent white disc of that diameter behind the glyph (heart and More).
NP = {'np_play': ('pil:play', 44, 0, 'fg', 'np_play_down'), 'np_pause': ('pil:pause', 44, 0, 'fg', 'np_pause_down'),
      'np_next': ('pil:next', 36, 0, 'fg', 'np_next_down'), 'np_prev': ('pil:prev', 36, 0, 'fg', 'np_prev_down'),
      'np_grabber': ('pil:grabber', (120, 44), 0, 'ghost', 'np_grabber_down'),
      'np_random': ('arrows-shuffle', 30, 22, 'mid', None), 'np_cycle': ('repeat', 30, 22, 'mid', None),
      'np_cycle1': ('repeat-once', 30, 22, 'mid', None), 'np_order': ('repeat-off', 30, 22, 'off', None),
      'np_fav': ('heart:filled', 44, 20, 'fg', None, 36), 'np_unfav': ('heart', 44, 20, 'fg', 'np_unfav_down', 36),
      'np_more': ('dots', 44, 20, 'fg', 'np_more_down', 36), 'np_playqueue': ('playlist', 30, 22, 'mid', 'np_playqueue_down')}
NP_FG, NP_DIM = (0xEE, 0xEE, 0xEC), (0x8C,) * 3        # q2-pod's off-white and its muted pressed grey
NP_MID, NP_OFF = (0xAA,) * 3, (0x6E,) * 3               # the mode and queue glyphs (the secondary grey); repeat-off
NP_TONES = {'fg': (NP_FG, 255), 'mid': (NP_MID, 255), 'off': (NP_OFF, 255), 'ghost': ((255, 255, 255), 110)}   # rgb, alpha
NP_PRESSED = {'ghost': ((255, 255, 255), 190)}            # every other tone presses to NP_DIM
NP_DISC_ALPHA, NP_DISC_ALPHA_DOWN = 26, 51                # #FFFFFF1A, pressed #FFFFFF33

SHANLING = '@shanling'

def gname(g): return g.lstrip('+').split(':')[0]
def is_custom(g): return g.startswith('+')
def is_filled(g): return g.endswith(':filled')

def used_glyphs():
    gl = [e[2] for e in HOME + SETTINGS + LISTS] + list(PULLDOWN.values()) + list(STATUS.values()) + \
        [g for g in WIFI_LEVELS if g] + [COVER_GLYPH, POD_HOME_GLYPH] + list(NAV_VIEW.values()) + [v[1] for v in POD_ROWS.values() if v[1] != SHANLING] + \
        [g for _, g, _ in GLYPHS] + [g for _, g in DISCS] + [v[0] for v in NP.values() if not v[0].startswith('pil:')] + ['lock:filled']
    return sorted({gname(g) for g in gl if g and not is_custom(g)})

# Tabler has a "filled" style for these (the "on" tiles and play/pause); anything else stays outline
def filled_available(name): return os.path.isfile(os.path.join(SVG, 'filled', name + '.svg'))

# ---------------------------------------------------------------- SVG -> RGBA (generation only)
TAGS = {'path', 'circle', 'rect', 'line', 'polyline', 'polygon', 'ellipse'}
ATTRS = {'d', 'cx', 'cy', 'r', 'rx', 'ry', 'x', 'y', 'width', 'height', 'x1', 'y1', 'x2', 'y2', 'points',
         'fill-rule', 'clip-rule', 'transform'}
SAFE = re.compile(r'^[0-9A-Za-z.,\-+ ()#%]*$')

def parse_svg(path):
    """Shapes of a Tabler SVG as data: [(tag, attrs)]; only whitelisted tags/attributes survive."""
    els = []
    for e in ET.parse(path).getroot().iter():
        tag = e.tag.split('}')[-1]
        if tag not in TAGS: continue
        a = {k.split('}')[-1]: v for k, v in e.attrib.items()}
        if a.get('stroke') == 'none' and a.get('fill') == 'none': continue      # the 24x24 bounding box
        els.append((tag, {k: v for k, v in a.items() if k in ATTRS and SAFE.match(v) and 'url' not in v.lower()}))
    return els

CUSTOM = os.path.join(ROOT, 'assets', 'icons', 'custom')
LUCIDE = os.path.join(ROOT, 'assets', 'icons', 'lucide')    # lucide-static 1.61.0 (ISC), npm tarball SHA-256 62773cd2ee411ad2e37c1973d1e4c4b49f9a6c57da6b5d5d0abca08756ba75f1
def svg_path(name, style='outline'):
    for d in (CUSTOM, LUCIDE):
        c = os.path.join(d, name + '.svg')
        if os.path.isfile(c): return c
    return os.path.join(SVG, style, name + '.svg')

def build_svg(name, style, px, sw, solid, dx=0.0, dy=0.0):
    els = parse_svg(svg_path(name, style))
    col = '#FFFFFF'
    if style == 'filled': g = f'fill="{col}"'
    else: g = (f'fill="{col if solid else "none"}" stroke="{col}" stroke-width="{sw}" '
               'stroke-linecap="round" stroke-linejoin="round"')
    body = ''.join('<%s %s/>' % (t, ' '.join(f'{k}="{v}"' for k, v in a.items())) for t, a in els)
    tx, ty = dx * 24 / px, dy * 24 / px
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 24 24">'
            f'<g transform="translate({tx:.4f} {ty:.4f})" {g}>{body}</g></svg>')

def _rsvg(svg, px):
    from PIL import Image
    r = subprocess.run(['rsvg-convert', '-w', str(px), '-h', str(px), '-f', 'png'], input=svg.encode(),
                       capture_output=True, check=True)
    return Image.open(io.BytesIO(r.stdout)).convert('RGBA')

def _crisp(im):
    a = im.getchannel('A').tobytes(); tot = sum(a) or 1
    return sum(v * v for v in a) / (255.0 * tot)       # 1.0 = every inked pixel fully opaque

_rc = {}
def render(name, px, style='outline', sw=2, solid=False):
    """White glyph px x px; sub-pixel offset (<= 0.5 px) chosen for the crispest edges, no hinting."""
    k = (name, px, style, sw, solid)
    if k not in _rc:
        steps = (0, 0.25, 0.5, -0.25) if px <= 24 else (0, 0.5)
        best = None
        for dx in steps:
            for dy in steps:
                im = _rsvg(build_svg(name, style, px, sw, solid, dx, dy), px)
                c = _crisp(im) - 0.002 * (abs(dx) + abs(dy))      # tie-break toward the centre
                if best is None or c > best[0]: best = (c, im)
        _rc[k] = best[1]
    return _rc[k]

def tint(im, rgb):
    from PIL import Image
    out = Image.new('RGBA', im.size, rgb + (0,)); out.putalpha(im.getchannel('A')); return out

def glyph(g, px, ctx, rgb=WHITE):
    """ctx: 'disc'/'home'/'pull'/'cover' stroke 2 outline; 'on'/'solid' Tabler filled where it exists
    (solid falls back to a filled outline); 'small' 1.5 px absolute at <= 16 px, 2 px above."""
    n = gname(g)
    if ctx in ('on', 'solid') and filled_available(n): im = render(n, px, 'filled')
    elif ctx == 'solid': im = render(n, px, 'outline', 1.5 * 24 / px if px <= 16 else 2, True)
    elif ctx == 'small': im = render(n, px, 'outline', 1.5 * 24 / px if px <= 16 else 2)
    else: im = render(n, px, 'outline', 2)
    return tint(im, rgb) if rgb != WHITE else im

def ink_crop(im):
    bb = im.getchannel('A').getbbox(); return im.crop(bb) if bb else im

def fit(fn, cw, ch, start, align='c'):
    """fn(px) -> glyph; the largest px <= start whose ink fits cw x ch, placed in a cw x ch canvas."""
    from PIL import Image
    px = start
    while True:
        g = ink_crop(fn(px))
        if (g.width <= cw and g.height <= ch) or px <= 8: break
        px -= 1
    c = Image.new('RGBA', (cw, ch), (0, 0, 0, 0))
    x = cw - g.width if align == 'r' else (0 if align == 'l' else (cw - g.width) // 2)
    c.alpha_composite(g, (x, (ch - g.height) // 2)); return c

# The Shanling mark for the "Shanling Home" row: the brand's own swoosh from the stock shutdown screen
# (images/xx/shutdown.png, white on a blue shape above the SHANLING wordmark), isolated by whiteness (min of r, g, b:
# the blue shape is far from white) and scaled to fit the disc, white on transparent. The stock file is pinned.
SHUTDOWN_SHA = 'b5133684f5f6100415161b5722b63cab1c0123538f3de440e2725e3c5f3dbc6e'
SHUTDOWN_CROP = (92, 144, 228, 216)     # the mark, without the wordmark below it (starts at y 217)
MARK_W, MARK_H = 32, 24                 # largest ink on the 40 px disc

def shanling_mark():
    from PIL import Image, ImageChops, ImageFilter
    path = os.path.join(find_stock_img(), 'shutdown.png')
    assert sha256(open(path, 'rb').read()) == SHUTDOWN_SHA, 'shutdown.png is not the pinned stock file'
    rgb = Image.open(path).convert('RGB').crop(SHUTDOWN_CROP)
    big = rgb.resize((rgb.width * 4, rgb.height * 4), Image.LANCZOS)
    r, g, bl = big.split()
    mask = ImageChops.darker(ImageChops.darker(r, g), bl).point(lambda v: max(0, min(255, (v - 110) * 255 // 110)))
    mask = mask.filter(ImageFilter.MaxFilter(5))     # the swoosh's hairline strokes are under 1 px at disc size: thicken by about 1 px
    im = Image.new('RGBA', big.size, WHITE + (0,)); im.putalpha(mask)
    im = ink_crop(im)
    k = min(MARK_W / im.width, MARK_H / im.height)
    return im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)

def disc(size, rgb, ss=4):
    from PIL import Image, ImageDraw
    big = Image.new('L', (size * ss, size * ss), 0)
    ImageDraw.Draw(big).ellipse((0, 0, size * ss - 1, size * ss - 1), fill=255)
    im = Image.new('RGBA', (size, size), rgb + (0,)); im.putalpha(big.resize((size, size), Image.LANCZOS)); return im

def on_disc(g, size, rgb):
    d = disc(size, rgb); d.alpha_composite(g, ((size - g.width) // 2, (size - g.height) // 2)); return d

# glyph size on the disc: Tabler's 24 grid has 2 px padding, so 24 px reads a little small on a 40 px disc
DISC_GLYPH, HOME_GLYPH = 26, 38

# ---- round 2: plain glyph images (no disc) at an exact canvas size
STROKE_PX = {'dots': 3.0}          # Tabler draws a dot as a zero-length stroke, so its px width is the dot
def glyph_fit(g, cw, ch, rgb=WHITE, pad=1):
    """Tabler glyph g ('name' or 'name:filled') as the largest glyph whose ink fits (cw - 2 pad) x (ch - 2 pad),
    absolute stroke 2 px (1.5 px on canvases under 22 px), centred in a transparent cw x ch canvas."""
    from PIL import Image
    n, filled = gname(g), is_filled(g)
    style = 'filled' if filled else 'outline'
    sw_px = STROKE_PX.get(n, 2.0 if min(cw, ch) >= 22 else 1.5)
    def at(px, probe=False):
        sw = sw_px * 24 / px
        if probe: return _rsvg(build_svg(n, style, px, sw, False), px)
        return render(n, px, style, sw)
    lo, hi = 8, 120 if n != 'dots' else min(cw, ch)
    while lo < hi:                                  # largest px whose ink fits
        mid = (lo + hi + 1) // 2; bb = at(mid, True).getchannel('A').getbbox()
        if bb and bb[2] - bb[0] <= cw - 2 * pad and bb[3] - bb[1] <= ch - 2 * pad: lo = mid
        else: hi = mid - 1
    ink = ink_crop(at(lo))
    c = Image.new('RGBA', (cw, ch), (0, 0, 0, 0)); c.alpha_composite(ink, ((cw - ink.width) // 2, (ch - ink.height) // 2))
    return tint(c, rgb) if rgb != WHITE else c

def recolour_white(path):
    """A stock image's alpha as a white glyph: the line art kept, the orange gone."""
    from PIL import Image
    a = Image.open(path).convert('RGBA').getchannel('A')
    im = Image.new('RGBA', a.size, (255, 255, 255, 0)); im.putalpha(a); return im

def speed_badge(label, selected, size=(36, 20), ss=4):
    from PIL import Image, ImageDraw, ImageFont
    w, h = size; col = WHITE if selected else (0x77,) * 3
    big = Image.new('L', (w * ss, h * ss), 0); d = ImageDraw.Draw(big)
    d.rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), radius=4 * ss, fill=255)
    d.rounded_rectangle((ss, ss, (w - 1) * ss - 1, (h - 1) * ss - 1), radius=3 * ss, fill=0)
    px = 12
    while True:                                     # the largest text that clears the 1 px outline by 3 px
        f = ImageFont.truetype(TILE_FONT, px * ss); bb = f.getbbox(label)
        if bb[2] - bb[0] <= (w - 8) * ss or px <= 8: break
        px -= 1
    d.text(((w * ss - (bb[2] - bb[0])) // 2 - bb[0], (h * ss - (bb[3] - bb[1])) // 2 - bb[1]), label, font=f, fill=255)
    im = Image.new('RGBA', size, col + (0,)); im.putalpha(big.resize(size, Image.LANCZOS)); return im

def play_all_pill(pressed, size=(90, 28), ss=4):
    """The Play all button: off-white pill, dark text and play glyph (pressed: #8C8C8C). q2-pod's pill, Inter text."""
    from PIL import Image, ImageDraw, ImageFont
    w, h = size; bg = NP_DIM if pressed else NP_FG; ink = (0x14,) * 3
    big = Image.new('L', (w * ss, h * ss), 0); ImageDraw.Draw(big).rounded_rectangle((0, 0, w * ss - 1, h * ss - 1), radius=h * ss // 2, fill=255)
    im = Image.new('RGBA', size, bg + (0,)); im.putalpha(big.resize(size, Image.LANCZOS))
    play = glyph_fit('player-play:filled', 12, 12, ink, 0)
    f = ImageFont.truetype(TILE_FONT, 14); bb = f.getbbox('Play all'); tw = bb[2] - bb[0]
    x0 = (w - (play.width + 6 + tw)) // 2
    im.alpha_composite(play, (x0, (h - play.height) // 2))
    m = Image.new('L', size, 0); ImageDraw.Draw(m).text((x0 + play.width + 6 - bb[0], (h - (bb[3] - bb[1])) // 2 - bb[1]), 'Play all', font=f, fill=255)
    t = Image.new('RGBA', size, ink + (0,)); t.putalpha(m); im.alpha_composite(t); return im

def wifi_lock(level, size=(30, 21)):
    """Secured network, signal 1..4: the Wi-Fi fan (unlit arcs #666666, lit arcs white) and a small lock."""
    from PIL import Image
    def fan(p):
        full = glyph('wifi', p, 'small', OFF).copy(); full.alpha_composite(glyph(WIFI_LEVELS[level], p, 'small')); return full
    c = Image.new('RGBA', size, (0, 0, 0, 0)); f = fit(fan, 21, 17, 22, 'l')
    c.alpha_composite(f, (0, (size[1] - f.height) // 2))
    lock = glyph_fit('lock:filled', 9, 11, WHITE, 0); c.alpha_composite(lock, (size[0] - lock.width, size[1] - lock.height))
    return c

def generate_all(sizes):
    """sizes: {file name: (w, h)} of the stock files -> {file name: RGBA image}."""
    from PIL import Image
    f = {}
    for n, _, g in SETTINGS:
        if g: f[n] = on_disc(glyph(g, DISC_GLYPH, 'disc'), 40, DISC)
    for n, _, g in LISTS: f[n] = on_disc(glyph(g, DISC_GLYPH, 'disc'), 40, DISC)
    for n, _, g in HOME:
        if not g: continue
        f[n] = on_disc(glyph(g, HOME_GLYPH, 'home'), 66, DISC)
        f[n + '_down'] = on_disc(glyph(g, HOME_GLYPH, 'home'), 66, DISC_DOWN)
    f[POD_HOME[0]] = on_disc(glyph(POD_HOME_GLYPH, HOME_GLYPH, 'home'), 66, DISC)
    f[POD_HOME[1]] = on_disc(glyph(POD_HOME_GLYPH, HOME_GLYPH, 'home'), 66, DISC_DOWN)
    # pull-down tiles: one ring style, off / on / disabled (docs/ui.md)
    for n, (g, st) in TILES.items(): f[n] = ring_tile(g, st)
    for n in ('drop_lighticon0', 'drop_lighticon1'):
        f[n] = fit(lambda p, g=PULLDOWN[n]: glyph(g, p, 'small'), 20, 20, 20)
    # status bar
    f['bar_play'] = fit(lambda p: glyph(STATUS['bar_play'], p, 'solid'), 14, 18, 16)
    f['bar_pause'] = fit(lambda p: glyph(STATUS['bar_pause'], p, 'solid'), 14, 18, 16)
    for i in range(5):
        f[f'bar_vol{i}'] = fit(lambda p, i=i: glyph(STATUS[f'bar_vol{i}'], p, 'small'), 24, 18, 22, 'l')
    def wifi(level, p):
        full = glyph(STATUS['bar_wifi'], p, 'small', OFF).copy()
        if level: full.alpha_composite(glyph(WIFI_LEVELS[level], p, 'small'))
        return full
    for i in range(5): f[f'bar_wifi{i}'] = fit(lambda p, i=i: wifi(i, p), 24, 16, 22)
    f['bar_bt'] = fit(lambda p: glyph(STATUS['bar_bt'], p, 'small', OFF), 47, 20, 22, 'r')
    f['bar_btcon'] = fit(lambda p: glyph(STATUS['bar_bt'], p, 'small'), 47, 20, 22, 'r')
    f['bar_digital'] = fit(lambda p: glyph(STATUS['bar_digital'], p, 'small'), 18, 18, 20)
    # "no cover" tiles: the stock tile colour, a muted glyph at 60 % of the tile
    for n in COVERS:
        w = sizes[n][0]; bg = sizes[n + ':bg']
        t = Image.new('RGBA', (w, w), bg + (255,))
        g = glyph(COVER_GLYPH, round(w * 0.6), 'cover', (0x8C,) * 3)
        t.alpha_composite(g, ((w - g.width) // 2, (w - g.height) // 2))
        f[n] = t if sizes[n + ':mode'] == 'RGBA' else t.convert('RGB')
    for n, g in POD_ROWS.values(): f[n] = on_disc(shanling_mark() if g == SHANLING else glyph(g, DISC_GLYPH, 'disc'), POD_ICON, DISC)
    for n, g in NAV_VIEW.items():
        f[n] = glyph_fit(g, NAV_PX, NAV_PX)
        f[n + '_down'] = glyph_fit(g, NAV_PX, NAV_PX, (0x77,) * 3)
    # round 2: glyph images at the stock size, discs, recoloured line art, badges, pills
    for n, g, down in GLYPHS:
        grey = (GREY_GLYPHS[n],) * 3 if n in GREY_GLYPHS else WHITE
        f[n] = glyph_fit(g, *sizes[n], grey, 6 if min(sizes[n]) >= 48 else 1)
        if down: f[down] = glyph_fit(g, *sizes[down], (0x77,) * 3)
    for n, g in DISCS: f[n] = on_disc(glyph(g, DISC_GLYPH, 'disc'), 40, DISC)
    for n in RECOLOUR: f[n] = recolour_white(os.path.join(find_stock_img(), n + '.png'))
    for n, (label, sel) in SPEEDS.items(): f[n] = speed_badge(label, sel)
    for n, pressed in PLAYALL.items(): f[n] = play_all_pill(pressed)
    for n, level in WIFI_LOCK.items(): f[n] = wifi_lock(level)
    return f

def _aa(size, draw, scale=8):
    """Draw at scale x with draw(ImageDraw, s) in white on transparent, downsample (anti-aliased mask)."""
    from PIL import Image, ImageDraw
    big = Image.new('L', (size[0] * scale, size[1] * scale), 0)
    draw(ImageDraw.Draw(big), scale)
    return big.resize(size, Image.LANCZOS)

# the solid shapes, drawn at s x on a w x h canvas (white mask)
PLAY_TRI, PAUSE_BAR, SKIP_TRI, GRABBER = (27, 32), (8, 10, 32), (16, 18), (36, 5, 11)   # w x h; bar w, gap, h; w x h; w, h, y

def g_play(d, s, w, h):
    # right-pointing triangle, shifted right 1.5 px for optical centring
    tw, th = PLAY_TRI
    x0, y0 = (w - tw) / 2 + 1.5, (h - th) / 2
    d.polygon([(x0 * s, y0 * s), ((x0 + tw) * s, (y0 + th / 2) * s), (x0 * s, (y0 + th) * s)], fill=255)

def g_pause(d, s, w, h):
    bw, gap, ph = PAUSE_BAR
    x0, y0 = (w - (2 * bw + gap)) / 2, (h - ph) / 2
    for x in (x0, x0 + bw + gap):
        d.rounded_rectangle([x * s, y0 * s, (x + bw) * s - 1, (y0 + ph) * s - 1], radius=2 * s, fill=255)

def g_skip(d, s, w, h, forward=True):
    # two triangles touching: >> (or << mirrored)
    tw, th = SKIP_TRI
    x0, y0 = (w - 2 * tw) / 2, (h - th) / 2
    for i in range(2):
        a = x0 + i * tw
        pts = [(a, y0), (a + tw, y0 + th / 2), (a, y0 + th)] if forward else [(a + tw, y0), (a, y0 + th / 2), (a + tw, y0 + th)]
        d.polygon([(x * s, y * s) for x, y in pts], fill=255)

def g_grabber(d, s, w, h):
    # the sheet handle: a pill centred in the button's width, y px from its top
    pw, ph, y = GRABBER
    d.rounded_rectangle([(w - pw) / 2 * s, y * s, (w + pw) / 2 * s - 1, (y + ph) * s - 1], radius=ph / 2 * s, fill=255)

def pil_glyph(kind, size, rgb, alpha=255):
    """The solid glyph `kind` (play, pause, next, prev, grabber) on a size (px or (w, h)) canvas, in rgb at alpha."""
    from PIL import Image
    w, h = size if isinstance(size, tuple) else (size, size)
    fn = {'play': g_play, 'pause': g_pause, 'next': lambda d, s, w, h: g_skip(d, s, w, h, True),
          'prev': lambda d, s, w, h: g_skip(d, s, w, h, False), 'grabber': g_grabber}[kind]
    mask = _aa((w, h), lambda d, s: fn(d, s, w, h))
    if alpha != 255: mask = mask.point(lambda v: v * alpha // 255)
    im = Image.new('RGBA', mask.size, rgb); im.putalpha(mask); return im

def np_disc(size, disc_px, alpha, g, ink, rgb):
    """A size x size canvas: a white disc of disc_px at `alpha` centred, the Tabler glyph g (ink px) over it."""
    from PIL import Image
    d = disc(disc_px, (255, 255, 255)); d.putalpha(d.getchannel('A').point(lambda v: v * alpha // 255))
    c = Image.new('RGBA', (size, size), (255, 255, 255, 0)); o = (size - disc_px) // 2
    c.alpha_composite(d, (o, o)); c.alpha_composite(glyph_fit(g, size, size, rgb, (size - ink) // 2)); return c

def np_images():
    """The Now Playing glyphs (mod_nowplaying.py): the tones of NP_TONES, pressed #8C8C8C (the grabber: brighter); the
    transport glyphs are the solid PIL-drawn shapes, heart and More sit on a translucent disc, the rest Tabler."""
    out = {}
    for n, (g, px, ink, tone, down, *rest) in NP.items():
        for name, pressed in ((n, False), (down, True)):
            if not name: continue
            rgb, alpha = (NP_PRESSED.get(tone) or (NP_DIM, 255)) if pressed else NP_TONES[tone]
            if g.startswith('pil:'): out[name] = pil_glyph(g[4:], px, rgb, alpha)
            elif rest: out[name] = np_disc(px, rest[0], NP_DISC_ALPHA_DOWN if pressed else NP_DISC_ALPHA, g, ink, rgb)
            else: out[name] = glyph_fit(g, px, px, rgb, (px - ink) // 2)
    return out

# ---------------------------------------------------------------- one ring style for every pull-down tile (docs/ui.md)
RING_OFF, RING_DIS, RING_ON_GLYPH = (0x77,) * 3, (0x44,) * 3, (0x14,) * 3
TILE_GLYPH = 28      # Tabler glyph px (24 grid, stroke 2) inside the 50 px ring
TILE_FONT = os.path.join(ROOT, 'assets', 'fonts', 'Inter-m1plus.ttf')
# tile image -> (glyph or 'text:XX', state); the stock geometry: 50 x 50, the circle touching the bounds
TILES = {
    'drop_wifi': ('wifi', 'off'), 'drop_wifiopen': ('wifi', 'on'), 'drop_bt': ('bluetooth', 'off'),
    'drop_btopen': ('bluetooth', 'on'), 'drop_keylock': ('lock', 'off'), 'drop_keylockopen': ('lock', 'on'),
    'drop_eq': ('adjustments-alt', 'off'), 'drop_eqopen': ('adjustments-alt', 'on'),
    'drop_usbaudio': ('usb', 'on'), 'drop_usbdac': ('+dac', 'on'), 'drop_usbstorage': ('device-usb', 'on'),
    'drop_playset': ('adjustments', 'off'), 'drop_playsetdown': ('adjustments', 'on'),
    'drop_sysset': ('settings', 'off'), 'drop_syssetdown': ('settings', 'on'),
    'drop_lowgain': ('+gain-low', 'off'), 'drop_highgain': ('+gain-high', 'on'),
    'drop_lowgaindisable': ('+gain-low', 'dis'), 'drop_highgaindisable': ('+gain-high', 'dis'),
    'drop_po': ('text:PO', 'off'), 'drop_lo': ('text:LO', 'on')}
TILES_NEW = ['drop_lowgain', 'drop_highgain', 'drop_lowgaindisable', 'drop_highgaindisable', 'drop_po', 'drop_lo']

def ring_tile(g, state, on_style='disc'):
    """50 x 50 tile: off = grey ring + grey glyph, dis = dark-grey, on = white filled disc + dark glyph
    ('disc') or white ring + white glyph ('ring', the alternative documented in docs/ui.md)."""
    from PIL import Image, ImageDraw, ImageFont
    ss, N, sw = 4, 50, 2
    big = Image.new('L', (N * ss, N * ss), 0); dr = ImageDraw.Draw(big)
    filled = state == 'on' and on_style == 'disc'
    if filled: dr.ellipse((0, 0, N * ss - 1, N * ss - 1), fill=255)
    else:
        dr.ellipse((0, 0, N * ss - 1, N * ss - 1), fill=255); dr.ellipse((sw * ss, sw * ss, (N - sw) * ss - 1, (N - sw) * ss - 1), fill=0)
    col = {'off': RING_OFF, 'dis': RING_DIS, 'on': WHITE}[state]
    gcol = RING_ON_GLYPH if filled else col
    t = Image.new('RGBA', (N, N), col + (0,)); t.putalpha(big.resize((N, N), Image.LANCZOS))
    if g.startswith('text:'):
        f = ImageFont.truetype(TILE_FONT, 20); bb = f.getbbox(g[5:])
        ti = Image.new('RGBA', (bb[2] - bb[0] + 2, bb[3] - bb[1] + 2), gcol + (0,))
        m = Image.new('L', ti.size, 0); ImageDraw.Draw(m).text((1 - bb[0], 1 - bb[1]), g[5:], font=f, fill=255)
        ti.putalpha(m); gi = ti
    else: gi = ink_crop(glyph(g, TILE_GLYPH, 'disc', gcol))
    t.alpha_composite(gi, ((N - gi.width) // 2, (N - gi.height) // 2)); return t


# ---------------------------------------------------------------- stock pins
# SHA-256 of each file this step replaces, in the stock V2.1 images/xx (the tree the other steps start from)
_PIN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mod_icons_pins.txt')

def replaced_names():
    return sorted(set(TILES_NEW) | set(
        [n for n, _, g in SETTINGS + LISTS if g] + [n for n, _, g in HOME if g] + [n + '_down' for n, _, g in HOME if g] +
        ['drop_wifi', 'drop_wifiopen', 'drop_bt', 'drop_btopen', 'drop_keylock', 'drop_keylockopen', 'drop_eq',
         'drop_eqopen', 'drop_usbaudio', 'drop_usbdac', 'drop_usbstorage', 'drop_playset', 'drop_sysset',
         'drop_playsetdown', 'drop_syssetdown', 'drop_lighticon0', 'drop_lighticon1',
         'bar_play', 'bar_pause', 'bar_bt', 'bar_btcon', 'bar_digital'] + [f'bar_vol{i}' for i in range(5)] +
        [f'bar_wifi{i}' for i in range(5)] + COVERS +
        [n for n, _, _ in GLYPHS] + [d for _, _, d in GLYPHS if d] + [n for n, _ in DISCS] + RECOLOUR +
        list(SPEEDS) + list(PLAYALL) + list(WIFI_LOCK)))

def pod_row_names(): return sorted({n for n, _ in POD_ROWS.values()})
def nav_names(): return sorted(set(NAV_VIEW) | {n + '_down' for n in NAV_VIEW})
def pod_names(): return sorted(set(pod_row_names()) | set(POD_HOME) | set(nav_names()))
def np_names(): return sorted(set(NP) | {v[4] for v in NP.values() if v[4]})

def added_rels(stock_rootfs=None, *args):
    """Rootfs-relative paths of the files this step adds (fwtool --allow-added): the M1 Pod row icons."""
    return [f'{IMG.removeprefix("rootfs/")}/{n}.png' for n in pod_names()]

def sha256(b): return hashlib.sha256(b).hexdigest()

def load_pins():
    pins = {}
    for line in open(_PIN_FILE):
        if line.strip() and not line.startswith('#'):
            h, n = line.split(); pins[n] = h
    return pins

def read_png(path):
    from PIL import Image
    im = Image.open(path); im.load(); return im

def find_stock_img():
    stock = paths.find_stock(paths.ZIP)
    if not stock: sys.exit('no unpacked stock tree found (run tools/build.py once)')
    return os.path.join(stock, IMG)

# ---------------------------------------------------------------- commands
def cmd_pins():
    d = find_stock_img()
    with open(_PIN_FILE, 'w') as o:
        o.write('# SHA-256 of the stock V2.1 images/xx files tools/mod_icons.py replaces (tools/mod_icons.py --pins)\n')
        for n in replaced_names(): o.write(f'{sha256(open(os.path.join(d, n + ".png"), "rb").read())}  {n}\n')

def cmd_generate():
    d = find_stock_img(); sizes = {}
    for n in replaced_names():
        im = read_png(os.path.join(d, n + '.png')); sizes[n] = im.size
        if n in COVERS:
            sizes[n + ':mode'] = im.mode; sizes[n + ':bg'] = im.convert('RGB').getpixel((2, 2))
    files = generate_all(sizes)
    assert sorted(files) == sorted(replaced_names() + pod_names()), set(files) ^ set(replaced_names() + pod_names())
    nps = np_images(); assert sorted(nps) == np_names(), set(nps) ^ set(np_names())
    files.update(nps)
    shutil.rmtree(PNG, ignore_errors=True); os.makedirs(PNG)
    for n, im in sorted(files.items()):
        assert n in pod_names() + np_names() or im.size == sizes[n], (n, im.size, sizes.get(n))
        im.save(os.path.join(PNG, n + '.png'), optimize=True)
    print(f'{len(files)} PNGs, {sum(os.path.getsize(os.path.join(PNG, f)) for f in os.listdir(PNG))} bytes -> {PNG}')

def cmd_fetch(tgz):
    data = open(tgz, 'rb').read()
    if sha256(data) != TGZ_SHA: sys.exit('tarball SHA-256 mismatch (pinned: @tabler/icons 3.49.0)')
    names = used_glyphs()
    shutil.rmtree(SVG, ignore_errors=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as t:
        for style in ('outline', 'filled'):
            os.makedirs(os.path.join(SVG, style), exist_ok=True)
            for n in names:
                try: m = t.getmember(f'package/icons/{style}/{n}.svg')
                except KeyError:
                    assert style == 'filled', f'missing outline glyph {n}'; continue
                os.makedirs(os.path.join(SVG, style), exist_ok=True)
                open(os.path.join(SVG, style, n + '.svg'), 'wb').write(t.extractfile(m).read())
        open(os.path.join(ASSET, 'LICENSE'), 'wb').write(t.extractfile('package/LICENSE').read())
    print('svg sources:', {s: len(os.listdir(os.path.join(SVG, s))) for s in ('outline', 'filled')})

def check_assets(stock_dir, work_dir=None):
    """Asset PNGs against the stock files: same size and mode; pins match; optional work tree check."""
    pins = load_pins(); n_ok = 0
    assert sorted(pins) == replaced_names(), 'pin file out of date (mod_icons.py --pins)'
    for n in replaced_names():
        sp = os.path.join(stock_dir, n + '.png')
        assert sha256(open(sp, 'rb').read()) == pins[n], f'{n}.png: stock file does not match the pin'
        s, a = read_png(sp), read_png(os.path.join(PNG, n + '.png'))
        assert (a.size, a.mode, a.format) == (s.size, s.mode, 'PNG') and s.format == 'PNG', f'{n}.png: {a.size} {a.mode} vs {s.size} {s.mode}'
        if work_dir:
            w = read_png(os.path.join(work_dir, n + '.png'))
            assert (w.size, w.mode) == (s.size, s.mode), f'{n}.png in the work tree has an unexpected format'
        n_ok += 1
    return n_ok

def apply(src, out):
    clone_workdir(src, out)
    d = os.path.join(out, IMG)
    n_ok = check_assets(find_stock_img(), d)
    total_old = total_new = 0
    for n in replaced_names():
        p = os.path.join(d, n + '.png'); new = open(os.path.join(PNG, n + '.png'), 'rb').read()
        total_old += os.path.getsize(p); mode = os.stat(p).st_mode
        write_keep_mode(p, new); total_new += len(new)
        im = read_png(p); assert im.size == read_png(os.path.join(PNG, n + '.png')).size    # round trip
        assert stat.S_IMODE(os.stat(p).st_mode) == stat.S_IMODE(mode)
    n_rows = apply_pod_rows(out, POD_ROWS)
    add_home_icon(out)
    add_nav_icons(out)
    print(f'icons: {n_ok} images replaced, {total_old} -> {total_new} bytes ({total_new - total_old:+d}); {n_rows} M1 Pod row icons '
          f'and the Home grid icon ({POD_HOME_STYLE}) added')

IMG_MODE, IMG_MTIME = 0o755, 1750924035     # as the other added images (mod_nowplaying.py)
UI_DIR = 'rootfs/release/assets/default/raw/ui'

def apply_pod_rows(out, rows):
    """Icon discs on the M1 Pod menu / Shuffle page rows: an insensitive image at the row's left, the
    title shifted right (row height, chevrons, names and the payload's row table untouched)."""
    from awtk_ui import Widget
    if not any(os.path.exists(os.path.join(out, UI_DIR, k + '.bin')) for k in POD_UI): return 0
    used = {}
    def edit(root):
        for row in [w for w in root.walk() if w.type == 'list_item' and w.name.startswith('pod_row')]:
            lab = next(c for c in row.children if c.type == 'hscroll_label')
            assert not any(c.name == 'pod_icon' for c in row.children), 'already has icons'
            text = pod_i18n.shown_english(lab); assert text in rows, f'no icon for the row {text!r}'
            img = rows[text][0]; used[img] = 1
            right = min([c.x for c in row.children if c.type in ('image', 'button') or c.name.startswith('pod_value')] or [row.w - 12])   # the chevron, switch, up arrow or value
            lab.x, lab.w = POD_TEXT_X, right - POD_TEXT_X
            ic = Widget('image', POD_ICON_X, (row.h - POD_ICON) // 2, POD_ICON, POD_ICON,
                        [('name', 'pod_icon'), ('image', img), ('draw_type', 'icon'), ('sensitive', 'false')])
            row.children.insert(0, ic)
    for k in POD_UI:
        p = os.path.join(out, UI_DIR, k + '.bin')
        if os.path.exists(p):
            edit_ui(p, edit); os.utime(p, (IMG_MTIME, IMG_MTIME))   # an added file: keep the build deterministic
    d = os.path.join(out, IMG)
    for n in used:
        p = os.path.join(d, n + '.png'); assert not os.path.exists(p), f'{n}.png already in the tree'
        shutil.copyfile(os.path.join(PNG, n + '.png'), p); os.chmod(p, IMG_MODE); os.utime(p, (IMG_MTIME, IMG_MTIME))
    return len(used)

HOME_STYLES = 'rootfs/release/assets/default/raw/styles/home_page.bin'

def add_home_icon(out):
    """The Home grid's "M1 Pod" icon (patch/home.c builds the widget at run time): its two images and the image
    style home_m1pod_style, a copy of home_tidal_style (normal/disable/focused/pressed/selected) pointing at them,
    inserted in the stock sort order (widget type, style name) among the other home_*_style items."""
    import awtk_style
    p = os.path.join(out, HOME_STYLES)
    old = open(p, 'rb').read(); th = awtk_style.parse(old)
    assert awtk_style.serialize(th) == old, 'home_page.bin does not round-trip'
    assert not th.find('image', POD_HOME_STYLE), 'home_m1pod_style already in the tree'
    src = th.find('image', 'home_tidal_style'); assert len(src) == 5, 'unexpected home_tidal_style'
    new = []
    for it in src:
        props = [(k, t, (POD_HOME[1] if it.state == 'pressed' else POD_HOME[0]) if k == 'bg_image' else v) for k, t, v in it.props]
        new.append(awtk_style.Item('image', POD_HOME_STYLE, it.state, props))
    at = next((i for i, it in enumerate(th.items) if it.widget == 'image' and it.style > POD_HOME_STYLE),
              max(i for i, it in enumerate(th.items) if it.widget == 'image') + 1)
    th.items[at:at] = new
    write_keep_mode(p, awtk_style.serialize(th))
    d = os.path.join(out, IMG)
    for n in POD_HOME:
        q = os.path.join(d, n + '.png'); assert not os.path.exists(q), f'{n}.png already in the tree'
        shutil.copyfile(os.path.join(PNG, n + '.png'), q); os.chmod(q, IMG_MODE); os.utime(q, (IMG_MTIME, IMG_MTIME))

def add_nav_icons(out):
    """The Albums view toggle's four images (used by ui/m1pod_albums.bin, which swaps the glyph at run time with its mode)."""
    d = os.path.join(out, IMG)
    for n in nav_names():
        q = os.path.join(d, n + '.png'); assert not os.path.exists(q), f'{n}.png already in the tree'
        shutil.copyfile(os.path.join(PNG, n + '.png'), q); os.chmod(q, IMG_MODE); os.utime(q, (IMG_MTIME, IMG_MTIME))

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('src', nargs='?'); ap.add_argument('out', nargs='?')
    ap.add_argument('--generate', action='store_true'); ap.add_argument('--pins', action='store_true')
    ap.add_argument('--fetch', metavar='TGZ'); ap.add_argument('--check', action='store_true')
    a = ap.parse_args()
    if a.pins: cmd_pins()
    elif a.generate: cmd_generate()
    elif a.fetch: cmd_fetch(a.fetch)
    elif a.check:
        print(check_assets(find_stock_img(), os.path.join(a.src, IMG) if a.src else None), 'files OK')
    elif a.src and a.out: apply(a.src, a.out)
    else: ap.error('SRC and OUT workdirs, or a command')

if __name__ == '__main__': main()
