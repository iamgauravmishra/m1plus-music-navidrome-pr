# About row and polish

## About (`tools/mod_about.py`)

System Settings > About keeps its seven stock rows. FW. Version is the literal `V2.1` in demo's `.rodata`
(0x74773c, set by `systemset_about_page_init` 0x4a170c's widget walk), which this tree never patches, so it
already shows the stock firmware version; the package tag in `firmware_v20.info` is not shown. One more
`list_item` (`listitem7` > `hscroll_label scrlabel7`, a clone of the FW. Version row, the stock walk ignores
names it does not know) is inserted right below it with the fixed text `M1+ Music:<TAG>` (`TAG` from
`tools/build.py`, passed to the step). The brand is not translated; the format is the stock `label:value`. No
hook, nothing at run time. Product name: the user sees "M1+ Music"; internal names (`m1plus-*` files, `m1plus_*.bin`,
widget and C identifiers) are `m1plus`.
## Polish (`tools/mod_polish.py`)

- navbar title size 22 -> 20 px (`navbar_label_white`, `navbar_centerlabel_white`, all states, both
  themes; `leftlabel`/`rightlabel` were 20); box (y 14, h 22) and middle alignment unchanged;
  `TITLE_NEW` in the tool.
- the pod pages' `label_title` is the stock 200 px wide (248 would run under the bars icon), so a
  long artist name on the Artists Cover Flow is cut where every stock title is. The Home instance of the
  menu hides its whole navbar at run time (below); the menu the grid icon opens keeps it.
- With the grid hidden by the payload (`docs/modules/home-guard.md`) the window under the menu is plain black, so no stock grid flashes at boot or on Back.
- **Consistency audit, every item decided** (the pull-down and the toggle / slider art, stock and release: `controls()` in the release sheet):
  - secondary greys: *applied*. The secondary text grey is `#AAAAAA` (Home artist line, Now Playing times, artist
    and album lines, album page artist line; the album page's 13 px year line is `#9C9C9C`, the least that passes the
    4.5:1 scan on the pressed row); `#8C8C8C` stays as the muted partner / pressed glyph grey. Now Playing's
    `#CCCCCC` / `#BBBBBB` and the album page's `#9C9C9C` became `#AAAAAA`. *Rejected:* the lock screen's `#DDDDDD`
    artist line (it sits on a wallpaper, not on black) and the queue's stock muted rows (derived from the stock style).
  - pressed colours: *applied*. Pressed surfaces are `#333333` (rows, keys, the queue
    drawer's bottom button). `#3A3A3A` stays as the edge colour (hairline borders,
    the index letter), `#555555` is the pressed disc and the inactive dot.
  - disc greys (`#777777` / `#555555` / `#666666` / `#444444`): *rejected*, each has one job (disc, pressed disc,
    unlit glyph, disabled tile).
  - glyph stroke scaling (Home discs 3.2 px, 40 px discs 2.2 px, tiles 2.3 px, status 1.5 px): *rejected*, the
    strokes are 2 px on the icon sets' 24 grid scaled to the glyph size, so the weight on screen is the same ratio.
  - font size ladder (22/20 titles, 21 rows, 18 second lines, 16 captions, 15/16 meta), row heights (52, 60/64,
    56, 50, 44) and margins 12 vs 16: *rejected*, they are code-built geometry (`docs/architecture.md`) or stock
    dialogs; changing one needs a patch and moves hit targets.
  - theme1's stock pull-down art: *rejected*, theme1 stays stock on purpose.
