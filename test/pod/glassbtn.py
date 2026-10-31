"""Glass pieces (mod_icons.glass_image, the Home mini bar's pane): the shared glass stays as it was, and the navbar glass buttons are the generator's output. (The album page's
Play all pill and Shuffle disc and Now Playing's star and More discs are solid or flat, not glass: test/pod/albuminfo.py, test/pod/nowplaying.py.)"""
import os
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import awtk_style, mod_icons
from PIL import Image


def run(ctx):
    expect = ctx.expect
    assets = os.path.join(WORK, 'rootfs', 'release', 'assets')
    def shipped(n): return open(asset_path(n), 'rb').read()
    G = mod_icons.glass_image
    def over(im, x, y, bg):
        p = im.getpixel((x, y)); return tuple(round((p[3] * c + (255 - p[3]) * bg) / 255) for c in p[:3])

    # the shared glass is untouched: the mini bar and the lock card are still the generator's output with the same arguments
    for n, im in (('mb_glass', G(*mod_icons.GLASS, False)), ('mb_glass_down', G(*mod_icons.GLASS, True)), ('lk_card', G(*mod_icons.GLASS_CARD, fill=mod_icons.GLASS_CARD_FILL))):
        expect(shipped(n) == png_of(im), f'{n}.png is still glass_image output, byte for byte')

    # ---- the navbar's glass buttons (mod_icons.ah_nav_images; docs/modules/navbar.md): every image as wide as the real button it sits in
    import mod_ipodrows
    N, H_, GL = mod_icons.AH_NAV_NAMES, mod_icons.GLASS_H, mod_icons.GLASS_GLYPH
    gen = mod_icons.ah_nav_images()
    expect(H_ == 42 and sorted(gen) == sorted(N) and len(N) == 2 * (len(mod_icons.AH_NAV_PIECES) + 1) + 1 and all(shipped(n) == png_of(gen[n]) for n in N),
           f'the {len(N)} ah_nav_* PNGs are the generator\'s output byte for byte')
    # independent of mod_icons.glass_piece: (width, glass columns, glyph centre) of every image, and its capsule (image columns) when it is a slice: the Pod
    # pages' right cap of the 141 px capsule; the album page's multi-select (a 50 px image centred on its 46 px button at 214: x 212 .. 262) and Now Playing
    # (60 at 262), the two caps of one 95 px capsule 216 .. 311
    want = {'ah_nav_back': (42, 0, 42, 21), 'ah_nav_close': (42, 0, 42, 21), 'ah_nav_np': (60, 9, 51, 30), 'ah_nav_search': (46, 2, 44, 23),
            'ah_nav_multi': (50, 4, 50, 25, (4, 99)), 'ah_nav_npa': (60, 0, 49, 28, (-46, 49)),
            'ah_nav_add': (60, 9, 51, 30), 'ah_nav_del': (60, 9, 51, 30), 'ah_nav_cancel': (60, 1, 43, 22), 'ah_nav_unsel': (50, 8, 50, 29), 'ah_nav_sel': (50, 8, 50, 29),
            'ah_nav_play': (60, 0, 51, 30, (-90, 51))}
    PD = 36   # a pressed slice: the rest glass and a white disc of PD px, 14 % opaque, on the glyph's centre (3 px of glass above and below)
    def highlight(out, cx):
        d = mod_icons.disc(PD, (255, 255, 255)); d.putalpha(d.getchannel('A').point(lambda v: round(v * 0.14)))
        out.alpha_composite(d, (cx - PD // 2, (H_ - PD) // 2)); return out
    def ref_of(n, pressed):
        w, x0, x1, cx, *cap = want[n]
        out = Image.new('RGBA', (w, H_), (0, 0, 0, 0))
        if cap:
            (c0, c1), = cap
            out.alpha_composite(G(c1 - c0, H_, 21, False).crop((x0 - c0, 0, x1 - c0, H_)), (x0, 0))
            return highlight(out, cx) if pressed else out
        out.alpha_composite(G(x1 - x0, H_, 21, pressed), (x0, 0)); return out
    expect((mod_icons.NAV_PRESS_D, mod_icons.NAV_PRESS_ALPHA) == (PD, 0.14) and mod_icons.AH_CAPSULE == (216, 311) and 212 + 4 == 216 and 212 + 50 == 262 == 311 - 49
           and 216 + 21 == 237 and 290 + 21 == 311 and 237 - 212 == 25 and 290 - 262 == 28,
           'the album capsule: multi-select\'s 50 px image on its button 214 + 46 / 2 - 25 = 212 meets Now Playing\'s at 262; glass 216 .. 311, 21 px past each glyph (237, 290)')
    bad = []
    for n in N:
        base = n[:-5] if n.endswith('_down') else n
        im, r = asset_image(n), ref_of(base, n.endswith('_down'))
        glyph = [(x, y) for y in range(im.height) for x in range(im.width) if im.getpixel((x, y)) != r.getpixel((x, y))]
        gx0, gx1, gy0, gy1 = min(p[0] for p in glyph), max(p[0] for p in glyph), min(p[1] for p in glyph), max(p[1] for p in glyph)
        ok = (im.size == r.size and gx1 - gx0 + 1 <= GL and gy1 - gy0 + 1 <= GL
              and abs((gx0 + gx1) / 2 - want[base][3]) <= 1.5 and abs((gy0 + gy1) / 2 - H_ / 2) <= 1.5)
        if not ok: bad.append(n)
    expect(not bad, f'every ah_nav_* image is its glass (a disc, or a cap of a capsule, pressed with the round highlight) at its columns with a glyph of at most {GL} px centred on its column, otherwise the glass byte for byte ({bad})')
    # the Pod pages' capsule pieces (pod_nav_*) glue into ONE capsule: Cover Flow / "..." (46 at x 168), toggle (46 at 214), Now Playing (60 at 260): glass 170 .. 311
    plain = lambda pos, pressed=False: mod_icons.capsule_piece(pos, None, pressed)
    glued = Image.new('RGBA', (152, H_), (0, 0, 0, 0))
    for p, x in (('left', 0), ('middle', 46), ('right', 92)): glued.paste(plain(p), (x, 0))
    full = Image.new('RGBA', (152, H_), (0, 0, 0, 0)); full.alpha_composite(G(141, H_, 21), (2, 0))
    expect(list(full.getdata()) == list(glued.getdata()), f'Cover Flow | toggle | Now Playing: the three pieces of main\'s 46 / 46 / 60 px slots glue into the 141 x {H_} capsule (x 170 .. 311) exactly, no seam')
    # the Songs page's capsule starts at the 122 slot: Search (left), Sort and Select (middle), Now Playing (right), one 187 px capsule, glass 124 .. 311 (the same pieces)
    glued = Image.new('RGBA', (198, H_), (0, 0, 0, 0))
    for p, x in (('left', 0), ('middle', 46), ('middle', 92), ('right', 138)): glued.paste(plain(p), (x, 0))
    full = Image.new('RGBA', (198, H_), (0, 0, 0, 0)); full.alpha_composite(G(187, H_, 21), (2, 0))
    expect(list(full.getdata()) == list(glued.getdata()), f'Search | Sort | Select | Now Playing: the four pieces of the slots 122 / 168 / 214 / 260 glue into the 187 x {H_} capsule (x 124 .. 311) exactly, no seam')
    # a genre's songs have no Search (the stock navbar leaves it out for class 0xff09): Select as the left cap (pod_nav_selectl, runtime icon of btn_select at 214) and Now Playing, a 95 px capsule, glass 216 .. 311
    glued = Image.new('RGBA', (106, H_), (0, 0, 0, 0))
    for p, x in (('left', 0), ('right', 46)): glued.paste(plain(p), (x, 0))
    full = Image.new('RGBA', (106, H_), (0, 0, 0, 0)); full.alpha_composite(G(95, H_, 21), (2, 0))
    expect(list(full.getdata()) == list(glued.getdata()), f'Select (left cap) | Now Playing: the two pieces of the slots 214 / 260 glue into the 95 x {H_} capsule (x 216 .. 311) exactly, no seam')
    expect(mod_icons.NAV_VIEW_POS['pod_nav_selectl'] == 'left' and mod_icons.NAV_VIEW['pod_nav_selectl'] == mod_icons.NAV_VIEW['pod_nav_select'],
           'pod_nav_selectl is the left-cap piece of the same list-checks glyph as pod_nav_select')
    # the Extras page's Settings button: the same left cap (so Settings | Now Playing glues as the two-piece capsule above), with the Lucide sliders-horizontal glyph the Settings row's icon uses
    expect(mod_icons.NAV_VIEW_POS['pod_nav_settings'] == 'left' and mod_icons.NAV_VIEW['pod_nav_settings'] == 'sliders-horizontal'
           and mod_icons.POD_ROWS['Settings'][1] == 'sliders-horizontal' and mod_icons.capsule_piece('left', 'sliders-horizontal', False).size == (46, H_)
           and list(mod_icons.capsule_piece('left', 'sliders-horizontal', True).getdata()) != list(mod_icons.capsule_piece('left', 'sliders-horizontal', False).getdata()),
           'pod_nav_settings is the left-cap piece of sliders-horizontal, the Settings row\'s glyph; its _down differs (the round highlight)')
    # Cover Flow's artist page: Songs (left cap at 214) | Now Playing (ah_nav_play, set at run time): the same two pieces as the Artists page's switch, one 95 px capsule
    expect(mod_icons.NAV_VIEW_POS['pod_nav_songs'] == 'left' and 'pod_nav_allalbums' not in mod_icons.NAV_VIEW and 'pod_nav_allalbums' not in mod_icons.NAV_VIEW_POS
           and mod_icons.NAV_VIEW_POS['pod_nav_artist'] == 'left' and O['NAV_VIEW_X'] + O['NAV_VIEW_W'] == 260,
           'Cover Flow\'s artist page: Songs is a left cap at 214 and Now Playing (ah_nav_play) the right cap at 260 (glued exactly as Select | Now Playing above, glass 216 .. 311); no All albums disc')
    # the album page's two caps, drawn where AWTK centres them (multi-select's 50 px image at 214 + 23 - 25 = 212, Now Playing's at 262), glue into one 95 px capsule
    def gl(n, pressed=False):
        w, x0, x1, cx, _g, cap = mod_icons.AH_NAV_PIECES[n]; return mod_icons.glass_piece(w, x0, x1, None, cx, pressed, cap)
    glued = Image.new('RGBA', (110, H_), (0, 0, 0, 0)); glued.paste(gl('ah_nav_multi'), (0, 0)); glued.paste(gl('ah_nav_npa'), (50, 0))
    full = Image.new('RGBA', (110, H_), (0, 0, 0, 0)); full.alpha_composite(G(95, H_, 21), (4, 0))
    expect(list(full.getdata()) == list(glued.getdata()), f'the album page: multi-select (x 212 .. 262) | Now Playing (262 .. 322) glue into the 95 x {H_} capsule (x 216 .. 311) exactly, no seam')
    # a pressed slice is the rest slice but for a round highlight on its glyph, inside its button and its glass: the capsule keeps one pane, no lit block
    slices = [(f'pod {p}', plain(p), plain(p, True), mod_icons.CAPSULE_PIECES[p][3], mod_icons.CAPSULE_PIECES[p][1:3], mod_icons.NAV_SLOT_W if p != 'right' else 60)
              for p in ('left', 'middle', 'right')]
    slices += [(n, gl(n), gl(n, True), mod_icons.AH_NAV_PIECES[n][3], mod_icons.AH_NAV_PIECES[n][1:3], bw) for n, bw in (('ah_nav_multi', 46), ('ah_nav_npa', 60))]
    bad = []
    for n, rest, down, cx, (x0, x1), bw in slices:
        diff = [(x, y) for y in range(H_) for x in range(rest.width) if rest.getpixel((x, y)) != down.getpixel((x, y))]
        lo = (rest.width - bw) // 2   # the button's first image column
        inside = all((x + 0.5 - cx) ** 2 + (y + 0.5 - H_ / 2) ** 2 <= (PD / 2 + 1) ** 2 for x, y in diff)   # its anti-aliased edge
        lit = sum(down.getpixel((cx, 6))[:3]) > sum(rest.getpixel((cx, 6))[:3]) and down.getpixel((cx, 2)) == rest.getpixel((cx, 2))
        if not (diff and inside and lit and x0 <= cx - PD // 2 and cx + PD // 2 <= x1 and lo <= cx - PD // 2 and cx + PD // 2 <= lo + bw): bad.append(n)
    expect(not bad, f'a pressed capsule piece differs from its rest piece only in a {PD} px disc on its glyph (lighter; the rim untouched), inside its glass and its button ({bad})')
    expect(122 + 46 + 46 + 46 == 260 and 124 + 187 == 311 and O['NAV_SEARCH_X'] == 122, 'the Songs capsule: slots 122 + 46 + 46 + 46 = Now Playing at 260 (main\'s), glass 124 .. 311')
    expect(mod_icons.NAV_SLOT_W + mod_icons.NAV_SLOT_W + mod_icons.NAV_PLAY_W == 152 and 170 + 141 == 311 == 290 + 21,
           'the capsule ends 21 px (the cap radius) right of Now Playing\'s glyph column 290; its slots are 168 + 46 + 46 = 260, Now Playing at 260 (main\'s)')
    for n, pos in mod_icons.NAV_VIEW_POS.items():
        for sfx, pressed in (('', False), ('_down', True)):
            im, r = asset_image(n + sfx), plain(pos, pressed)
            glyph = [(x, y) for y in range(im.height) for x in range(im.width) if im.getpixel((x, y)) != r.getpixel((x, y))]
            cx = 23
            expect(im.size == r.size and glyph and abs((min(p[0] for p in glyph) + max(p[0] for p in glyph)) / 2 - cx) <= 1.5 and max(p[1] for p in glyph) - min(p[1] for p in glyph) + 1 <= GL,
                   f'{n}{sfx}: the {pos} piece with its glyph on the slot\'s centre column ({cx})')
    # contrast of the white glyphs over the glass over pure white / black
    rep = []
    for pressed in (False, True):
        for bgv in (255, 0):
            worst_ = 99
            for n in [*N, *(k + s for k in mod_icons.NAV_VIEW_POS for s in ('', '_down'))]:
                if n.endswith('_down') != pressed: continue
                base = n[:-5] if n.endswith('_down') else n
                im = asset_image(n)
                r = ref_of(base, pressed) if base in want else plain(mod_icons.NAV_VIEW_POS[base], pressed)
                pts = [(x, y) for y in range(im.height) for x in range(im.width) if im.getpixel((x, y)) != r.getpixel((x, y)) and im.getpixel((x, y))[3] >= 250]
                worst_ = min(worst_, min(contrast((255, 255, 255), over(r, x, y, bgv)) for x, y in pts))
            rep.append(f'{"pressed" if pressed else "rest"}/{"white" if bgv else "black"}: {worst_:.2f}')
            expect(worst_ >= 4.5, f'the white glyphs of the navbar buttons over glass over pure {"white" if bgv else "black"}, {"pressed" if pressed else "rest"}: {worst_:.2f}:1 (>= 4.5)')
    print('  navbar buttons glyph contrast: ' + '; '.join(rep))
    for theme in ('default', 'theme1'):
        th = awtk_style.parse(open(os.path.join(assets, theme, 'raw/styles/albuminfo_page.bin'), 'rb').read())
        bad = []
        for style, (rest, down, icon_at, off) in mod_ipodrows.NAV_STYLES.items():
            items = {i.state: i for i in th.items if (i.widget, i.style) == ('button', style)}
            if sorted(items) != ['disable', 'focused', 'normal', 'over', 'pressed']: bad.append((style, 'states')); continue
            for s, i in items.items():
                w_ = down if s == 'pressed' and down else rest
                if not (i.get('icon') == w_ and i.color('bg_color') == '#00000000' and i.get('icon_at') == icon_at and (i.get('x_offset') or 0) == off and w_ in N and not i.has('bg_image')): bad.append((style, s))
        expect(not bad and len(mod_ipodrows.NAV_STYLES) == 9, f'{theme}: the navbar buttons\' styles (Back, search, multi-select, Now Playing, the select mode\'s five) show their glass disc, pressed one lighter, on no fill ({bad[:3]})')
        base = awtk_style.parse(open(os.path.join(assets, theme, 'raw/styles/default.bin'), 'rb').read())
        kinds = {s: sorted({i.widget for i in base.items if i.style == s}) for s in mod_ipodrows.NAV_STYLES}
        expect(all(k == ['button'] for k in kinds.values()), f'{theme}: the stock navbar styles the page overrides are button styles ({kinds})')

