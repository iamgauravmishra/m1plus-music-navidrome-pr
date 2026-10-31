"""The Podcasts page's episode rows without the dot column (patch/podcasts.c, docs/modules/podcasts.md): the rows' x positions and widths, title brightness (unplayed bright, played and not on the card grey), the grey lines (Played, the size of an episode that is not on the card) and select mode sliding the rows right by the mark column. The compiled payload runs under Unicorn; the card is a dict of paths."""
import importlib.util, os, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

HERE = os.path.dirname(os.path.abspath(__file__))


def sibling(name):
    mod = sys.modules.get(f'podtest_{name}')
    if mod is None:
        spec = importlib.util.spec_from_file_location(f'podtest_{name}', os.path.join(HERE, name + '.py'))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f'podtest_{name}'] = mod
        spec.loader.exec_module(mod)
    return mod


SEL = sibling('pcsel')
DL, PF, PCN, PCP = SEL.DL, SEL.PF, SEL.PCN, SEL.PCP
RP, ROW, HDR, NOW, PN = DL.RP, DL.ROW, DL.HDR, DL.NOW, DL.PN
pn_at, poke_slot, poke_fail, key_of = DL.pn_at, DL.poke_slot, DL.poke_fail, DL.key_of
flags, toasts, title, lines, marks = SEL.flags, SEL.toasts, SEL.title, SEL.lines, SEL.marks
MB = 1048576


def rows_card(m):
    """Show with every kind of row: u.mp3 (on the card, unplayed), p.mp3 (on the card, played), r.mp3 (not on the card, 48 MB), n.mp3 (not on the card, no size)."""
    PCP.page_card(m)
    m.put(f'{RP}/Mix/.episodes', (PCP.EPS_HEAD + ''.join(f'g={f}\tp={NOW - 86400 * (10 + i)}\td=1200\tl={l}\tf={f}.mp3\tt=Ep {f.upper()}\tu=https://e.example/{f}.mp3\n'
                                                       for i, (f, l) in enumerate((('u', 1000), ('p', 1000), ('r', 48 * MB), ('n', 0))))).encode())
    for f in 'up': m.put(f'{RP}/Mix/{f}.mp3', b'audio')
    m.images.update({'unselect': (26, 26, struct.pack('<I', 0xff111111) * 676), 'selected': (26, 26, struct.pack('<I', 0xff2222ee) * 676)})
    m.wall = NOW


def style_of_rows(m):
    """{title: (style, x, w)} of the episode rows of the Show level in a frame."""
    _, texts, styles, _ = PCP.paint(m)
    return {t: (s, r[0], r[2]) for (t, r), s in zip(texts, styles) if s in ('label_row_title', 'label_row_dim') and r[1] >= HDR}


def row_tests(ctx):
    expect = ctx.expect
    m = PCP.opened(rows_card, PCN.NM)
    m.call(PSYMS['pc_mark'], a0=PCP.pc_hash(f'{RP}/Mix/p.mp3'), a1=1, count=2000000)
    PCN_names = [s['dir'] for s in m.shows()[0]]
    # the Mix show has a feed-less .episodes: the Shows level lists it (it has files); open it from Feeds so the remote rows show
    m.fs[f'{RP}/Mix/.show'] = b'M1PLUS-SHOW 1\ntitle=Mix\nfeed=https://f.example/mix\nimage=\nchecked=0\n'
    PCP.click(m, 'btn_feeds')
    names = [t for _, t, _ in lines(m)]
    PCP.tap(m, 150, names.index('Mix') * ROW + 10)
    expect(title(m) == 'Mix' and PCN_names, 'the Mix show opens from Feeds (its remote episodes are listed)')
    st = style_of_rows(m)
    expect(st == {'Ep U': ('label_row_title', 16, 292), 'Ep P': ('label_row_dim', 16, 292), 'Ep R': ('label_row_dim', 16, 292), 'Ep N': ('label_row_dim', 16, 292)},
           f'no dot column: every title starts at x 16 and is 292 px wide; unplayed is the bright title style, played and not-on-the-card the grey one ({st})')
    bl, texts, styles, fills = PCP.paint(m)
    expect(not [b for b in bl if tuple(b[2][2:]) != (O['PC_HDR_ART'], O['PC_HDR_ART'])], 'no dot bitmap or any mark is drawn')
    greys = [t for (t, r), s in zip(texts, styles) if s == 'label_row_sub' and r[1] >= HDR]
    expect(greys[0].endswith('20 min') and greys[0].count('\u00b7') == 1, f'an episode on the card: the date and its length ({greys})')
    expect(greys[1].endswith('Played'), f'a played one ends with Played ({greys})')
    expect(greys[2].endswith('20 min \u00b7 48 MB'), f'a remote one ends with its size, which tells it from a played one ({greys})')
    expect('MB' not in greys[3] and 'Played' not in greys[3], f'a remote one with no size from the feed has no size ({greys})')
    hair = [f for f in fills if f[0] == O['LIST_HAIR']]
    expect(all(f[1] == 16 for f in hair), 'the hairlines start at the text margin')
    # select mode: the rows slide right by the mark column, off again afterwards
    PCP.click(m, 'btn_select')
    st = style_of_rows(m)
    expect(set(v[1] for v in st.values()) == {16 + O['SG_SEL_COL']} and set(v[2] for v in st.values()) == {292 - O['SG_SEL_COL']}, f'select mode: the texts slide right by the mark column (SG_SEL_COL) and narrow by it ({st})')
    mk = marks(m)
    expect([x for x, _, _ in mk] == [16 + (O['SG_SEL_COL'] - 6 - O['SG_MARK']) // 2] * 2 and len(mk) == 2, f'a mark in that column on the two rows on the card, none on the remote ones ({mk})')
    PCP.click(m, 'btn_return')
    st = style_of_rows(m)
    expect(set(v[1] for v in st.values()) == {16}, 'out of select mode: no column')


SECTIONS = [row_tests]


def run(ctx):
    for f in SECTIONS: f(ctx)
