"""Glass buttons (mod_icons.glass_image, the Home mini bar's pane): the album page's Play all pill and Shuffle disc, Now Playing's star and More discs.

Their images are the generator's output byte for byte, round and transparent outside, the styles name them, and every glyph and label keeps its contrast
on the glass at rest and pressed, with the glass over pure white and pure black (the worst backgrounds). The shared glass PNGs stay as they were."""
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

    # ---- the album page: the pill (180 x 40, r 20) and the disc (38, r 19), normal and pressed
    W, H = mod_icons.AH_PILL_PX; D = mod_icons.AH_DISC_PX
    expect((W, H, D) == (O['AH_PLAY_W'], O['AH_PILL_H'], O['AH_DISC']), 'the glass sizes are the payload\'s (AH_PLAY_W x AH_PILL_H, AH_DISC)')
    for n, pressed in (('ah_pill', False), ('ah_pill_down', True)):
        im = asset_image(n)
        expect(shipped(n) == png_of(G(W, H, H // 2, pressed)) and im.size == (W, H), f'{n}.png is glass_image({W}, {H}, {H // 2}, pressed={pressed}) byte for byte')
        expect(all(im.getpixel(p)[3] == 0 for p in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1))) and 150 <= im.getpixel((W // 2, H // 2))[3] <= 235
               and im.getpixel((W // 2, 0))[3] > 0 and im.getpixel((0, H // 2))[3] > 0,
               f'{n}: a stadium (transparent corners, round ends touching the box), translucent in the middle')
    for n, pressed in (('ah_shuffle', False), ('ah_shuffle_down', True)):
        im, ref = asset_image(n), G(D, D, D // 2, pressed)
        ring = [(x, y) for y in range(D) for x in range(D) if (x - D / 2 + .5) ** 2 + (y - D / 2 + .5) ** 2 > 12 ** 2]
        expect(im.size == (D, D) and all(im.getpixel(p) == ref.getpixel(p) for p in ring) and im.getpixel((0, 0))[3] == 0 and (255, 255, 255, 255) in im.getdata(),
               f'{n}: the glass disc ({D} px, r {D // 2}) outside the glyph, the white glyph opaque in the middle')
        expect(shipped(n) != png_of(ref), f'{n} carries the shuffle glyph')
    pg = asset_image('ah_play'); ink = [pg.getpixel((x, y)) for y in range(pg.height) for x in range(pg.width) if pg.getpixel((x, y))[3] > 200]
    expect(ink and all(p[:3] == (255, 255, 255) for p in ink), 'the play glyph is white (on the glass)')

    for theme in ('default', 'theme1'):
        th = awtk_style.parse(open(os.path.join(assets, theme, 'raw/styles/albuminfo_page.bin'), 'rb').read())
        play = [i for i in th.items if (i.widget, i.style) == ('button', 'btn_ahplay_style')]
        expect(len(play) == 5 and all(i.get('bg_image') == ('ah_pill_down' if i.state == 'pressed' else 'ah_pill') and i.color('bg_color') == '#00000000'
                                      and i.color('text_color') == '#FFFFFFFF' and i.get('icon') == 'ah_play' for i in play),
               f'{theme}: Play all is the glass pill image (pressed one lighter) on no fill with white text and glyph, in every state')

    # ---- Now Playing: star (filled, outline) and More are 32 px glass discs with the off-white glyph
    for n, down in (('np_fav', None), ('np_unfav', 'np_unfav_down'), ('np_more', 'np_more_down')):
        for name, pressed in ((n, False), (down, True)):
            if not name: continue
            im, ref = asset_image(name), G(32, 32, 16, pressed)
            bad = [(x, y) for y in range(44) for x in range(44)
                   if not (6 <= x < 38 and 6 <= y < 38 and (x - 21.5) ** 2 + (y - 21.5) ** 2 <= 16.6 ** 2) and im.getpixel((x, y))[3] != 0]
            far = [(x, y) for y in range(32) for x in range(32) if (x - 15.5) ** 2 + (y - 15.5) ** 2 > 12 ** 2]
            expect(im.size == (44, 44) and not bad and all(im.getpixel((x + 6, y + 6)) == ref.getpixel((x, y)) or im.getpixel((x + 6, y + 6))[3] == ref.getpixel((x, y))[3] == 0 for x, y in far),
                   f'{name}: the 32 px glass disc (pressed={pressed}) in its 44 px target, transparent outside it, the glyph inside ({bad[:2]})')

    # ---- contrast on the glass: white / off-white glyphs and labels, glass over pure white and pure black, rest and pressed
    rep = []
    def worst(fg, im, pts, bg): return min(contrast(fg, over(im, x, y, bg)) for x, y in pts)
    box = [(x, y) for y in range(6, H - 6) for x in range(24, W - 24)]
    for pressed in (False, True):
        pill = G(W, H, H // 2, pressed); disc_ = G(D, D, D // 2, pressed); np_ = G(32, 32, 16, pressed)
        disc_pts = [(x, y) for y in range(D) for x in range(D) if (x - D / 2 + .5) ** 2 + (y - D / 2 + .5) ** 2 <= 11 ** 2]
        np_pts = [(x, y) for y in range(32) for x in range(32) if (x - 15.5) ** 2 + (y - 15.5) ** 2 <= 11 ** 2]
        for bg in (255, 0):
            a, b, c = worst((255, 255, 255), pill, box, bg), worst((255, 255, 255), disc_, disc_pts, bg), worst(mod_icons.NP_FG, np_, np_pts, bg)
            rep.append(f'{"pressed" if pressed else "rest"}/{"white" if bg else "black"}: Play all {a:.2f}, Shuffle {b:.2f}, star/More {c:.2f}')
            expect(a >= 7 and b >= 7 and c >= 4.5, f'{"pressed" if pressed else "rest"} over {"white" if bg else "black"}: Play all label/glyph {a:.2f}:1 and Shuffle glyph {b:.2f}:1 (>= 7), star/More glyph {c:.2f}:1 (>= 4.5)')
    print('  glass buttons contrast: ' + '; '.join(rep))

    # ---- the navbar's glass buttons (mod_icons.ah_nav_images; docs/modules/navbar.md): every image as wide as the real button it sits in
    import mod_ipodrows
    N, H_, GL = mod_icons.AH_NAV_NAMES, mod_icons.GLASS_H, mod_icons.GLASS_GLYPH
    gen = mod_icons.ah_nav_images()
    expect(H_ == 42 and sorted(gen) == sorted(N) and len(N) == 2 * (len(mod_icons.AH_NAV_PIECES) + 1) + 1 and all(shipped(n) == png_of(gen[n]) for n in N),
           f'the {len(N)} ah_nav_* PNGs are the generator\'s output byte for byte')
    # independent of mod_icons.glass_piece: (width, glass columns, glyph centre) of every image, and its capsule when it is a slice (columns of a 141 px capsule)
    want = {'ah_nav_back': (42, 0, 42, 21), 'ah_nav_np': (60, 9, 51, 30), 'ah_nav_search': (46, 2, 44, 23), 'ah_nav_multi': (46, 2, 44, 23), 'ah_nav_npa': (60, 7, 49, 28),
            'ah_nav_add': (60, 9, 51, 30), 'ah_nav_del': (60, 9, 51, 30), 'ah_nav_cancel': (60, 1, 43, 22), 'ah_nav_unsel': (50, 8, 50, 29), 'ah_nav_sel': (50, 8, 50, 29),
            'ah_nav_play': (60, 0, 51, 30)}
    def ref_of(n, pressed):
        w, x0, x1, cx = want[n]
        out = Image.new('RGBA', (w, H_), (0, 0, 0, 0))
        pane = G(141, H_, 21, pressed).crop((90, 0, 141, H_)) if n == 'ah_nav_play' else G(x1 - x0, H_, 21, pressed)
        out.alpha_composite(pane, (x0, 0)); return out
    bad = []
    for n in N:
        base = n[:-5] if n.endswith('_down') else n
        im, r = asset_image(n), ref_of(base, n.endswith('_down'))
        glyph = [(x, y) for y in range(im.height) for x in range(im.width) if im.getpixel((x, y)) != r.getpixel((x, y))]
        gx0, gx1, gy0, gy1 = min(p[0] for p in glyph), max(p[0] for p in glyph), min(p[1] for p in glyph), max(p[1] for p in glyph)
        ok = (im.size == r.size and gx1 - gx0 + 1 <= GL and gy1 - gy0 + 1 <= GL
              and abs((gx0 + gx1) / 2 - want[base][3]) <= 1.5 and abs((gy0 + gy1) / 2 - H_ / 2) <= 1.5)
        if not ok: bad.append(n)
    expect(not bad, f'every ah_nav_* image is its glass (a disc, or the right cap of the capsule) at its columns with a glyph of at most {GL} px centred on its column, otherwise the glass byte for byte ({bad})')
    # the Pod pages' capsule pieces (pod_nav_*) glue into ONE capsule: Cover Flow / "..." (46 at x 168), toggle (46 at 214), Now Playing (60 at 260): glass 170 .. 311
    plain = lambda pos, pressed=False: mod_icons.capsule_piece(pos, None, pressed)
    for pressed in (False, True):
        glued = Image.new('RGBA', (152, H_), (0, 0, 0, 0))
        for p, x in (('left', 0), ('middle', 46), ('right', 92)): glued.paste(plain(p, pressed), (x, 0))
        full = Image.new('RGBA', (152, H_), (0, 0, 0, 0)); full.alpha_composite(G(141, H_, 21, pressed), (2, 0))
        expect(list(full.getdata()) == list(glued.getdata()), f'Cover Flow | toggle | Now Playing (pressed={pressed}): the three pieces of main\'s 46 / 46 / 60 px slots glue into the 141 x {H_} capsule (x 170 .. 311) exactly, no seam')
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

