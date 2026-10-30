#!/usr/bin/env python3
"""System Settings > About: a row with this build's tag under the stock FW. Version row (asset-only).

Stock's About page (systemset_about_page_init 0x4a170c, ui/systemset/about_page.bin) is seven list_item rows
(listitem0..6, one hscroll_label scrlabel0..6 each). The init walks the page with widget_foreach and sets each
label by name to `<translated key>:<value>` ("%s:%s"); FW. Version (scrlabel1) is the literal "V2.1" at 0x74773c
in demo's .rodata, which this tree never patches, so About already shows the stock firmware version and the
package tag (firmware_v20.info) never reaches it. A name the walk does not know is left alone, so one more
row in the asset needs no code and no hook: `M1+ Music:<TAG>`, the brand (never translated, as pod_i18n.BRANDS)
and the release tag from tools/build.py (passed as the argument), shaped like the stock rows and placed
right below FW. Version (listitem1). The row is a clone of listitem1 (stock styles, 260 px label that scrolls
on focus when long); the text is fixed at build time, so nothing runs when the page opens.

Usage: mod_about.py SRC_WORKDIR OUT_WORKDIR TAG     (OUT == SRC edits in place)
"""
import copy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir, edit_ui

UI = 'rootfs/release/assets/default/raw/ui/systemset/about_page.bin'
BRAND = 'M1+ Music'
ROW, LABEL = 'listitem7', 'scrlabel7'        # names no stock row has; the stock walk ignores them
AFTER = 'listitem1'                          # FW. Version
STOCK_ROWS = ['listitem0', 'listitem1', 'listitem2', 'listitem3', 'listitem4', 'listitem6', 'listitem5']


def row_text(tag):
    return f'{BRAND}:{tag}'


def edit_with(tag):
    def edit(root):
        view = root.find('about_scrollview')
        assert view is not None and [c.name for c in view.children] == STOCK_ROWS, 'unexpected About page'
        src = view.find(AFTER)
        assert [(c.type, c.name, c.x, c.y, c.w, c.h) for c in src.children] == [('hscroll_label', 'scrlabel1', 12, 20, 260, 21)], 'unexpected FW. Version row'
        row = copy.deepcopy(src)
        row.set('name', ROW)
        row.children[0].set('name', LABEL)
        row.children[0].set('text', row_text(tag))
        view.children.insert(view.children.index(src) + 1, row)
    return edit


def apply(out, tag):
    edit_ui(os.path.join(out, UI), edit_with(tag))
    print(f'about: row "{row_text(tag)}" below FW. Version')


if __name__ == '__main__':
    clone_workdir(sys.argv[1], sys.argv[2]); apply(sys.argv[2], sys.argv[3])
