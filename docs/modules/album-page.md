# The album page

**Sources:** `patch/albuminfo.c`, test `test/pod/albuminfo.py`.

There is one album view: the stock `albuminfo_page` (an album's tracks), restyled. It opens from the
stock Albums list, from the Albums grid (section 5a), from Cover Flow (main and per artist), from Artists through Cover Flow, from the
All albums card and from Now Playing's More sheet (Look up album, `patch/playmore.c`: it closes the sheet and any open album page, sets `songerinfoflag`
and opens the playing album's row), always through `navigator_to_with_context("albuminfo_page", class | row << 16)` with
`*pdeq_showlist` holding the album list the row came from (section 3: the stock Albums handler's
sequence; Cover Flow and the card repeat it, `coverflow.c open_album`). The stock page loads the
tracks itself (`loadAlbumdetailList`: class `0xf003` -> `0xff10`, an artist's album and the All songs
row `0xff01` -> `0xff11`), builds the 64 px track rows (q2-pod rows, section 6) and the header item.
The payload has no album code of its own except the one hook below (and Cover Flow's one extra call, below).

```
y   0  (back)                (search|multi|play)   header item 310 wide, 344 high (stock: 100); x is screen x, centre 160; the list starts at window row 0
    5   floating glass controls, 42 px high (band 4..48, see Floating controls)       and the header's first 44 rows are padding
   50      +-----------+                 cover 160x160 at x 80, corners rounded 10 px (painted, see Rounded cover)
           |   cover   |
  210      +-----------+
  224        Kind of Blue                 22 px white   srlabel_ahtitle_style  (stock label, x 17 w 286 h 22, centred)
  247        Miles Davis                  18 px #AAAAAA srlabel_ahartist_style (stock label, h 18, centred)
  267        1959 . 8 tracks              15 px #9C9C9C srlabel_ahmeta_style   (new label, h 15, centred)
  292   (shuf)  [ > Play all       ]      Shuffle 44x44 touch at x 42 (38 px disc), Play all 180x44 touch at x 95 (180x40 pill); drawn 12 px apart
  344   1  So What                        stock track rows, 64 px

**Vertical rhythm** (`tools/ah_ink.py`, measured on the shipped font's ink with the stb rasterizer; test `albuminfo`): a gap runs from the
capitals' / digits' top to the line above's baseline (descenders not counted). Cap heights 14 / 11 / 9 px at 22 / 18 / 15 px. Cover bottom to title
capitals **16**, title baseline to artist capitals **9**, artist baseline to year digits **9**, year baseline to the pill's top **16** (outer gaps equal,
text gaps equal); the touch rectangles end 8 px above the first row. The label rects are their font size high (the line box centred in them).
Variants rendered in `out/preview/album-header-variants.png` (`tools/preview_album_header.py`): A tighter (14 / 7 / 7 / 14, header 292) and B
airier (16 / 9 / 9 / 16, header 300); B shipped (A crowded the title's descenders against the artist line). Before: 11 / 14 / 12 / 11.
```

**Floating controls (no navbar bar).** The navbar is a band of glass discs over the page: `ui/albuminfo_page.bin` makes `navigationbar_view` a 320 x 50 band at the
window's origin, LAST in the window (it paints and hit-tests over the list; every widget keeps its name), and the list / scroll view / scroll bar start at row 0 and
are 450 high. The header carries 44 px of top padding (`AH_NAV_TOP`; every `AH_*` y is 44 greater: cover row 50, header 344), so at rest the page looks as before
under the controls and the rows scroll under them; `AH_TINT_ROWS` is `AH_HDR_H`, the cover's corner row is `AH_ART_Y - yoffset + row`. **No builder is pinned for this
page**: the page has TWO stock navbar builders and both are shared with stock pages, so their geometry is main's (`docs/modules/navbar.md`): `0x526a3c` (the multi-select
toggles' handlers; also `allmusic_page`) makes Back (3, 80 x 44), search (168, 46; not class `0xff09`), multi-select (214, 46), Now Playing (262, 60), and in select mode
unselect (0, 50), add / delete / cancel (116 / 191 / 268, 60 wide); `0x524e4c` (a fresh page: `albumdeinfo_listitem_layout`'s row loop `0x5265f4` and the to-foreground
handler `0x5267f0`; also `album_page_init`, an artist's albums) makes the same without search, 50 px high (Back at x 0), and none of multi-select / Now Playing when
`songerinfoflag` (`0xa04737`) is set. The page theme (`mod_ipodrows.NAV_STYLES`, both themes; a page theme only, so the artist's albums page keeps its look) overrides the
nine navbar button styles: each state shows ONE glass piece (`mod_icons.AH_NAV_PIECES`, 42 high), centred in the real button, so the glyph centres are the Pod navbar's
191 / 237 / 290, select mode's add / delete 146 / 221 and cancel 290, the unselect toggle 29; Back keeps its stock rule (`icon_at` left in a button-high square) with
`x_offset` +4, so the 42 px disc is at x 8 .. 50 from either builder. The search style's opaque black fill is gone on this page. `test/pod/albuminfo.py` `nav_tests` runs
both builders in the emulator for every select state, `songerinfoflag` and class and checks every button against these numbers; the hit-test tests use the built asset and
the emulated buttons.
**The capsule.** Multi-select and Now Playing are ONE glass capsule, x 216 .. 311 (`mod_icons.AH_CAPSULE`, the Artists page's columns), as the right-hand actions on our
own pages (`navbar.md`); search, which only the toggle builder makes (after a select cycle), is a lone disc beside it (170 .. 212, the usual 4 px gap); the select mode's
buttons are discs (the stock buttons are 75 px apart). It is images only, no builder changes: both builders make multi-select and Now Playing together or neither, so they
are always the left and right cap, whichever builder ran. The builders leave 2 px between them (multi-select 214 .. 260, Now Playing 262 .. 322): multi-select's image is
50 px, 4 wider than its button, and AWTK draws an icon at its own size on the rect's centre (`canvas_draw_icon_in_rect` `0x648f90` takes only the centre, then
`canvas_draw_icon`; no scaling, no clip), so it spans 212 .. 262 (its first 4 columns transparent) and its glass meets Now Playing's at 262. A press repaints only its
button's rect, which holds the whole round highlight (`navbar.md`), so the 2 px outside it never change. Pressed: the lone discs are the lighter glass, the caps the round
highlight. (An earlier design, V2.1nWC, made a capsule of all three by pinning both builders to a 44 px pitch, which changed stock pages that share them.)
Known quirks inherited from main: a fresh page's buttons are 50 high and the toggle builder's 44, so the discs sit 3 px higher after a select cycle; the stock title label (147
wide, not pinned) lies over the first 15 px of search's slot. **Dissolve:** none (glass over sharp rows). **Fallback** (kill switch or an unrecognised header): the controls
are data and stay; the stock 100 px header leaves Play all (y 62 ..) and the rows clear of the band (tested).

**The hook** (`m1plus_albuminfo_header`, section 2): `albuminfo_listitem0_layout` `0x526264` builds the
header, called only from the page's list builder (init and the to-foreground rebuild), so a rebuilt page is
restyled again. The hook runs the stock function first (a 100 px `list_item` with, in this order, the
`img_albumcover_m` image, the title and artist `hscroll_label`s and the Play all `button`), then, unless the
kill switch `/mnt/mmc/m1plus-off` exists or the item is not exactly that shape (four children of those
types), creates the two new widgets first (the year line `hscroll_label`, the Shuffle `button`); if any fails it destroys the ones it made and leaves stock; otherwise it moves and resizes the stock
widgets to the numbers above (`AH_*` in `offsets.inc`), gives the title, artist and Play all their page styles
and the Play all the text "Play all" (stock draws an orange image with its text baked in; the stock style
`btn_imgplayall_style` is left in the page theme, so a header the hook skips is the stock one), keeps its stock
handler (`0x525d48`, bound to the item) and resizes the item to 298. Nothing is renamed or removed
(`img_albumcover_m` is looked up by name by the cover refresh `0x525a38`). The year line
is insensitive (a drag over it scrolls the list); both buttons
are 44 px high touch rectangles (Shuffle 44 wide, Play all 180) with the 38 px disc and the 180x40 pill drawn centred in them. **Centring:** the list item starts at screen x 0 and is 310
wide (the 10 px scroll bar is the list's right edge), so the content is placed in item coordinates around
x 160 (screen centre) rather than the item's 155; nothing is widened and everything lies inside the 310 px
(rightmost edge 303). A long title or artist keeps the stock label's flags (`ellipses`, scrolling): an
`hscroll_label` shows its text centred while it fits and scrolls it, ending in an ellipsis, when it does not.

**Rounded cover.** AWTK cannot clip an image, so the four 10 px corners are painted over the cover in the colour the
window has behind them, from the cover widget's own `EVT_AFTER_PAINT` (`ah_on_art_paint`, `pod_corners` in `patch/common.c`,
the 8x8-sampled coverage table Now Playing's corners use, `pod_corner_fill`; at most 4 x 100 `canvas_fill_rect` calls, only when the cover
repaints). The colour is the page's: black, or the tint's gradient value on each cover row (below), with the list's scroll offset
(`yoffset` of the scroll view) taken into account. Nothing static is left over the cover (the old `ah_corner_*` mask images are gone).
`test/pod/albuminfo.py` replays the fills over a cover and checks every corner pixel against the model. A cover
smaller than the box (a small embedded image: the thread never upscales) sits centred in the 160 px box and
keeps its square corners (the corners are then painted on the page colour); the placeholder (`albumcover_info`, also what the
page shows until the thread has rendered the file) is a 160 px tile, rounded like a real cover.

**Cover tint.** A page showing a real cover is tinted like Now Playing: the window's `bg_color` is `pod_tone` (Now Playing's
`np_tone`, moved to `patch/common.c`; `NP_V_MIN/MAX`, white text keeps 4.5:1) of the cover's average colour, under `ah_tint.png`
(320x450, black, alpha 64 on window row 0 rising to **200** on row 343, the end of the header, and held at 200 below; the window's first
child `img_ah_tint`, insensitive), so the header fades from the tone to a **deep tint** (78 % dark) and the list below shows a deep version of the
cover colour (the track rows and the scroll bar strip are transparent over it). The asset makes the list view and its scroll view transparent and the header item takes the transparent style
`list_item_ahhead_style`. **Track rows:** the page theme (`styles/albuminfo_page.bin`, both asset themes, `mod_ipodrows.py` `ROW_*`) overrides `list_item_style`
for this page only: every state transparent, the pressed state `#FFFFFF33` (20 % white), the bottom border 1 px `#FFFFFF22` (13 % white; AWTK blends a 1 px
line's alpha like a fill: `test/awtk_fill.py` draws `canvas_draw_hline/vline` with it on the demo's own code). On a black page (placeholder disc, All albums card, kill switch: a black window under the
black overlay) that is exactly today's `#333333` pressed band and `#222222` hairline, so black pages look as before. Contrast (white title >= 4.5, track number `#AAAAAA` >= 3) over the
whole tone range at the held alpha 200: title 14.5:1, number 6.26:1 at rest; on the pressed row title 7.69:1, number 3.31:1 (the floor that fixed the alpha: at 190 it is 3.02:1; 20 % pressed, 4.5:1 for the number would need alpha 220+).
The gradient is fixed in the window: scrolled, text passes over lighter rows. The header at rest (ramp 64 to 200) keeps, over every tone: title 8.59:1, artist 4.06:1,
year line 3.78:1 (the controls' glyphs sit on glass: 8.0 / 15.9:1 over white / black, test `glassbtn`). A track row scrolled up to the window's top (window row 0, the brightest ramp row;
it passes under the controls) keeps at worst 3.23:1 for the title and
1.39:1 for the grey number over the brightest grey tone: a transient, only while it passes (it does not rest there; the tests report it and floor the title at 3:1).
The state is page-scoped (`ah`, one page): `ah_tint_start` (from the header hook) gets the window with `widget_get_window`, registers
`EVT_DESTROY` on it (`ah_on_destroy` removes the timer and clears the state) and starts a `AH_TICK_MS` 300 timer (`ah_tick`) that waits for
the cover thread: when the cover widget's (looked up by name each tick: a rebuilt header made a new one) `image` property is a `file://`
url (stock's refresh timer `0x5261d8` sets it) that exists, `cc_decode` box-averages it, `ah_set_color` sets the colour and the timer ends.
A tick works only while the page is in front (`ah.fg`) and the screen is lit (`pod_screen_lit`); otherwise it only repeats (no lookup,
no decode, no try counted), so a cover that resolves under another page tints it, and the bar, on the first tick back in front. The poll
gives up (`ah_spent`: the timer ends, the page stays black, a rebuilt header starts no new one) after `AH_TICK_MAX` 100 working ticks (30 s
in front without a cover) or `AH_DECODE_MAX` 3 cover files that do not decode.
The placeholder disc, an album without art, the All albums card (never a timer) and a refused timer or decode leave the page black; a page with
no window gets no tint but the painted corners; the kill switch skips the hook. A header built again for the same page keeps the colour
and starts no timer.

**Status bar.** A tinted page tints the status bar like Now Playing (`pod_bar_tint` / `pod_bar_black`, `patch/common.c`; the full story is in `nowplaying.md`, section
"The status bar"): the bar takes the page's window row 0, the tone under the overlay's first alpha (64), darkened (`pod_bar_color`, `NP_BAR_LUM_MAX`) until the bar's
white clock and glyphs keep 4.5:1. That colour is constant: the overlay is a child of the window, not of the list, so it does not
scroll (the list now reaches window row 0, but the bar is above the window and rows never reach it); the colour does not depend on the list's yoffset (tested at 0, 150, 300). `ah_set_color` applies it when the page is in front
(`ah.fg`), `ah_on_background` / `ah_on_foreground` (EVT_WINDOW_TO_BG / TO_FG on the window, registered with the destroy handler in `ah_tint_start`; the bar is never touched unless
both registered, `ah.barok`) black / re-tint it, `ah_stop` (destroy, or a new page over a live one) restores black first; `ah.bar` records that the bar is ours.
Black pages (the placeholder disc, an album without art, the All albums card, the kill switch, a page without a window) never tint it. A style call that fails
leaves the bar as it was and owes nothing. **Hand-over:** the bar has one owner (the window that last tinted it) and only the owner can restore black, so Play all /
Shuffle (this page backgrounds, Now Playing takes the bar in any order of the two events) and Back (Now Playing destroys, this page's TO_FG tints in any order)
never fight. Seam: for the tones the bar equals row 0 (155 of 217 tones in the test grid); for bright, high-luminance tones (greens, cyans, yellows) it is darker: a bright
cover (240, 225, 150) is 8 levels, the worst grid tone (131, 192, 192) is 34 levels in a channel. Easing it would take a deeper row 0 for everyone (alpha about 100 instead of 64).

**Tone cache (the tint at once).** `pod_tone_get` / `pod_tone_put` (`patch/common.c`): 64 entries of `{album key, tone word, use stamp}` (12 bytes, 768 bytes of
`.scratch`, no malloc), least recently used out, RAM only (nothing is written to the card), shared with Now Playing. The key is `cc_album_key`'s
(`cc_key_of(artist, album)`, FNV-1a of artist then album, the Cover Flow cache file's name) made from the names the stock header itself shows:
`classinfo + 0xd` (title) and `classinfo + 0x10d` (artist; `+0x20d` when `g_class_type` is `0xff14`, `0x524b00`). An empty album name has no key.
At the header build, `ah_cached` (before the poll would start, never for the All albums card): 1. a **hit** sets the tint there and then (no timer, no decode);
2. a **miss** with `/mnt/mmc/.m1plus/covers/<key>-168.jpg` decodes that one file (168 px, a few ms), sets the tint and inserts; 3. the file there but **empty**
(Cover Flow's "no art" marker): the page stays black, no timer; 4. no file (or one that does not decode): today's poll of the stock cover file
(`ah_tick`), which inserts when it resolves. For an artist's album the key is the artist-page artist rather than the album row's own artist, so a compilation
may miss the file (it then polls; never a wrong tone, only a miss). **Consistency:** both pages take `pod_tone` of the `cc_box` average of the centred square
whichever source resolved first, and the cache then serves every later page. Measured (synthetic 900 px covers and the boot logo, JPEG q85 full size
against the same square at 160, 168 and 264 px, JPEG q80): the averages differ by at most 1 of 255 in a channel, a tone difference of at most 1 level;
the one real difference would be a source with letterbox bars, which a bar-padded stock file (not seen) would average darker. The Cover Flow file is
preferred on the album page because it exists before the stock thread has rendered anything. `test/pod/albuminfo.py` `tone_cache_tests` (hit, miss with the file,
poll and insert, marker, All albums, kill switch, class `0xff14`, LRU and bounds, no write-like call in any of them) and `test/pod/nowplaying.py`.

**Styles** are the page theme's (`styles/albuminfo_page.bin`, both asset themes, `tools/mod_ipodrows.py`):
`srlabel_ahtitle_style` / `srlabel_ahartist_style` / `srlabel_ahmeta_style` (the stock white and grey lines
centred at 22 / 18 / 15 px, `#FFFFFF` / `#AAAAAA` / `#9C9C9C`: the design's `#8C8C8C` is 3.8:1 on the page's
pressed row and `mod_theme --scan` wants 4.5), `btn_ahplay_style` (`bg_image` `ah_pill` / `ah_pill_down`, 180x40 stadium images drawn centred, 18 px
`#141414` text, icon `ah_play`, `#BEBEBE` pressed) and `btn_ahshuf_style` (no fill, the icon is the disc itself:
`ah_shuffle`, `ah_shuffle_down`, 38 px images with the Lucide shuffle glyph; so the circle is anti-aliased
whether or not this AWTK rounds fills). `ah_play` has no padding: the style's `icon_at` left centres it in a 44 px square,
the text is drawn left aligned beside it, and the hook sets the pill's `margin_left` inline from `widget_measure_text` (`0x66c7e0`)
and `widget_get_text` (`0x667ea4`) through `widget_set_style` (`ah_centre_pill`; docs/ui.md). The same file makes the navbar title labels' (`navbar_*label_white`) text transparent on this page
(Back and Now Playing only; the label stays). Images: `tools/mod_icons.py` (`ALBUM`, `RESIZED`).

**Record fields.** `getMusicByAlbum` / `getMusicByAlbumAnd[Album]Songer` (`select * from songtable`)
fill an `stSongInfo` per row via the callback `0x4e908c`; schema: `id, filename, fileurl, album, songer,
style, name, composer, albumsonger, year, track, cd_num, time, time_end, time_create, Initial,
bitdepth, samprate`. `year` is `atoi`'d to `+0x30`; the scanner (`toolsLoadAllFile` -> insert
`0x5edfc4`) writes it from `taglib_tag_year` (`toolsGetMusicInfo` `0x5ec6a8`, `+0x680` of its out
buffer). Shown: year (first track with 1000..2999; the All albums card, `classinfo[8]` set, shows none),
the track count. **No duration**: there is no duration column; `time`/`time_end` are CUE offsets, 0 for
ordinary files, and `toolsGetMusicInfo` reads only the sample rate and an MQA flag, never a length. The
line reads "year . N tracks" or "N tracks" ("1 track").

**Play all and Shuffle** (`ah_play`; `ah_on_play`, `ah_on_shuffle`) run the stock Play all handler's sequence
(`0x525d48`) and then open Now Playing the way a track row's tap does. Play all takes the page's first track,
Shuffle a random one (`pod_rand`, the Shuffle page's generator); `access` check on that track (missing: the
toast "Storage unavailable", the page stays), `loadSongList(queue, name, cue, g_class_type)` (class `0xff10`, or
`0xff11` for an artist's album and the card); Shuffle sets the stock Shuffle mode first (`pod_set_mode`:
`mclSetPlayMode`, `notifyPlayMode`, `dmrSendPlayMode`, `write_int_config`; nothing is written when already
Shuffle; the queue is this album alone so stock Shuffle shuffles exactly the album, and the mode stays Shuffle
afterwards); Play all sets an in-order mode (`pod_set_in_order`: Shuffle and Repeat one become List play, List play and Repeat all are kept, nothing written when unchanged), so after a Shuffle, Play all plays the album in order and Now Playing shows it. A queue that does not resolve starts nothing, changes nothing and
is freed. **Opening Now Playing** (`ah_open_player`) is the tail of the stock row handler `0x52569c` (a track
tap, `0x5258c8..0x525970`): if `songerinfoflag` (`0xa04737`) is set and `navigator_window_is_exist("playing_page")`,
the loop `0x525904..0x5259d8` pops with `navigator_back` every window above the topmost `playing_page` and
`window_close`s that old Now Playing (it also stops at `home_page`); then
`navigator_to_with_context("playing_page", {queue, index, class, 2})`, whose init (`start_player`) starts the player
(the handlers no longer call `start_player` or set `force_refreshflag`). The stock loop trusts every `navigator_back`
to change the top window at once (a close animation would spin it: `docs/modules/boot.md`); no library, Cover Flow, menu
or Now Playing page has one (only the settings windows, the keyboard and the lock screen slide), and the payload's copy is
bounded (`AH_POP_MAX` 16 pops, then it opens over what is left). With the flag clear (or no Now Playing in the stack) the page
simply opens over the album page, exactly as a track tap does, so Back from Now Playing returns to it. The stock Play all
handler `0x525d48` (bound by the stock builder with the item as context) is removed with `widget_off_by_func` and ours bound
in its place. `test/pod/albuminfo.py` runs the handlers against a window stack (`StackMachine`: demo's own
`window_manager_get_top_window` over a window manager laid out in emulated memory, the rest of the stack calls modelled,
including a window that stays after `navigator_back`). `pod_rand`, `pod_toast`, `pod_set_mode`, `pod_set_in_order` are four exports at the end of
`patch/shuffle.c`.

**The cover.** The stock header cover is `/tmp/abp/<md5>1.jpg`, rendered by the cover thread
(`parse_albumcovertask_thd`) at 100 px, fitted inside, aspect kept, never upscaled, and drawn into a
100x100 scale-auto image: 1:1 for a square cover. The release renders it at 160 (`rows.json`, one
immediate at `0x4dd670`, `0x24130064` -> `0x241300a0`; this page is the only reader of the `1.jpg` files,
tmpfs; 160, not Cover Flow's 168, because that cache is a different file this page never reads, so nothing
is shared, and 160 keeps the header 8 px shorter) and the hook makes the image widget 160x160 with draw type
`center` (stock: scale-auto), so the file, or the 160 px placeholder tile before the cover task is done and
for an album without art, is always drawn at its own size and never scaled (AWTK's scaling is nearest
neighbour, `test/awtk_fill.py`); a cover under 160 px (a small embedded image, a non-square one) sits centred
in the 160 px box. With the kill switch the stock 100 px scale-auto widget shows the 160 px file scaled down.

**The cover thread's state.** The thread
(`0x4dd450`) sleeps 50 ms while `albumcover_taskstate` (`0xa05a18`) is 2. `albumcoverinfo_init` (`0x4dcf9c`)
sets it to 2 (and clears `albumcover_finishflag` `0xa05a5b`); the batch queuers (`batchadd_albumcover_task`
`0x4dccac` -> `local_albumsmallcover_task` `0x4dcbb4`, `local_songercover_task` `0x4dccc8`) end by setting it
to 1; `add_albumcover_task` (`0x4dca38`, the one `albuminfo_page_init` calls) only clears the task list and
pushes `{row, 0, flag}`. The stock Albums list always runs the batch queuer right after the init
(`album_page_init` `0x5248d0`/`0x52496c`), so the state is 1 by the time albuminfo_page opens; Cover Flow ran
only the init, the thread stayed parked and the page's cover task (and its 500 ms refresh timer, `0x5261d8`,
which picks the `/tmp/abp/<md5>1.jpg` file up when it appears) waited for nothing. Cover Flow now calls
`batchadd_albumcover_task(0, 0)` after the init: no task, state := 1; the page queues its own. The header
shows the placeholder disc until the thread has rendered the file, as from the Albums list.

Not done: a duration, a current-track marker in the track rows (the stock page marks nothing).

## The album page and the other stock pages (assets; the code half is `docs/modules/album-page.md`)

`tools/preview_stock.py WORKDIR OUT.png`: the Albums list and the album
page it opens, Cover Flow on an artist and the same page opened by the All albums card, a playlist's
songs, the queue. Approximate mock-ups, as above.

- **One album page.** The stock `albuminfo_page` opens from Albums, Cover Flow, Artists (through Cover
  Flow) and the All albums card; the header is restyled to the design in `docs/modules/album-page.md`
  (an Apple Music style detail page: a centred 160 px cover rendered 1:1 with 10 px rounded corners, then
  centred on the screen a 22 px white title, an 18 px `#AAAAAA` artist, a 15 px `#9C9C9C` "year . N tracks"
  line, and a row of a round 38 px dark grey Shuffle disc with the Lucide glyph and a 180x40 white Play all pill with a dark
  16 px play glyph and 18 px text (both in 44 px high touch rectangles; solid, not glass); no "..." button; the navbar is the floating glass controls of `docs/modules/album-page.md`: a Back disc, a search disc (after a select cycle) and a capsule of multi-select and Now Playing; its title is transparent). The cover's corners are painted in the
  page's colour from the cover's after-paint (black, or the cover tint of the Cover tint paragraph); a cover smaller than the box (a small embedded image) sits
  centred with square corners. The sizes and positions are in code (the hook
  moves the stock widgets, `AH_*`); the look is the page theme `styles/albuminfo_page.bin`
  (`btn_ahplay_style`, `btn_ahshuf_style`, `srlabel_ah{title,artist,meta}_style`, `tools/mod_ipodrows.py`), new names, so the stock
  `btn_imgplayall_style` (an orange pill image) remains for a header the hook leaves alone. **The pill's glyph and text:**
  AWTK draws a button's style icon and text in `widget_draw_icon_text` (`0x67235c`, reads `spacer`, `margin*`, `icon_at`);
  `icon_at` auto (0) is top when icon height + font size < the height inside the margins (16 + 18 < 44; 18 + 20 in V2.1nI, so V2.1mY stacked
  them). The pill's style says `icon_at` left (1; 2 right, 3 top, 4 bottom, 5 centre): `widget_calc_icon_text_rect`
  (`0x666f04`) puts the icon centred in a square as high as the rect (44 px, so the 16 px glyph has 14 px of padding on each
  side) and the text in the rect from the square's end plus `spacer` to the right edge. **Device finding (V2.1nF screenshot,
  `Screenshot` feature):** the text is drawn LEFT aligned at the start of that rect, not centred in it (`widget_draw_icon_text`
  reads `text_align_h` with default 2 = left at `0x672588`, then `canvas_set_text_align`; V2.1nC assumed centred, so its
  `spacer` -15 pulled the text onto the glyph: measured on the screenshot, glyph columns 136..151, "P" from 153, the text 52 px
  of ink (55 px advance), the rect starting at pill x 61 = 91 + 61 = 152, the pair left heavy). Now (V2.1nI): `text_align_h` left (2, explicit),
  `spacer` -6 (gap 8 less the glyph's 14 px padding; negative on purpose), `margin_right` 0, and the album header hook
  (`ah_centre_pill`) measures the translated "Play all" with `widget_measure_text` (`0x66c7e0`, the pill's own font) and
  sets `margin_left = (180 - (16 + 8 + text)) / 2 - 14` as an inline style for every state (`widget_set_style`, `"state:margin_left"`).
  Glyph, 8 px gap, text: centred for every language (test/pod/albuminfo.py runs the hook in all 13: gap 8 +-1, centre +-2). If
  the text cannot be measured (0, or too wide for the pill) nothing is set and the style's `margin_left` 43 (English centred) stays.
  `tools/preview_album.py` draws it with `mod_ipodrows.pill_layout` (the same rules) and writes a per-language strip. From Cover Flow the cover appears a moment
  after the page opens, as from the Albums list (the cover thread renders it; `docs/modules/album-page.md`). The track
  rows are the q2-pod rows (64 px pitch, hairline) with the track number secondary, Apple Music style: a 19 px `#AAAAAA`
  number (`srlabel_tracknum_style`, 5.44:1 on the `#333333` pressed row) right aligned in a 22 px column at x 12 (32 px for a
  100+ track album; every digit is 10 px at 19 px), then the 19 px white title from x 42 (8 px spacing) to 298 with its ellipsis
  (the title label is 256 px wide). Multi-select puts the 50 px tick first, then number and title. The playing row's gold
  title is unchanged (its number stays grey). Panel: `tools/preview_album.py`.
- **Artists, Genres, Composers** (stock `localclass_page`): the per-page placeholder disc (`icon_artist` / `icon_genre` /
  `icon_composer`, the same on every row) is hidden, so the name starts at the 12 px margin and runs to the chevron (265 px,
  was 217). The artist or genre that is playing shows the wave marker before the chevron (name 217 px). Panel: `tools/preview_album.py`.
- **A playlist's songs** (the stock `allmusic_page`, class `0xff13`, the playlist's name as the navbar title):
  the same 64 px rows and navbar as every library list, no header and no Play all button. The Pod's Playlists
  page no longer opens it (it opens our Songs page with the large title and Play / Shuffle, no hook:
  `docs/modules/songs.md` "The other lists"); it is reached from the stock Playlists page and as that page's
  fallback.
- **The queue drawer** (`ui/dialog/playqueue_dialog.bin`, no preview): the 240x450
  panel that slides in from the right over Now Playing (opened by name from `playerjumpinfo_page_init` `0x53b17c` and
  `0x4d126c`; `dialog_playqueue_dialog_init` `0x47a7cc`). Its rows are cloned from a template (`queue_table_row`) by the stock table code, `row_height` read
  from the file, and bound by `0x47a19c`: the song name in `scrlabel_name` with `srlabel_item_gold20_style` for the
  playing row, `srlabel_item_white_style` for the rest. The minimal theme made both white, so nothing marked the
  playing row. Now (asset and page theme `styles/playqueue_dialog.bin`, `mod_lists.py` recipe `queue` and
  `edit_playqueue`): rows 44 px (button 40, a 4 px gap), the other rows muted `#9C9C9C` 18 px, the playing row
  white 20 px; the list's own row colours; a `#3A3A3A` hairline under the 64 px play-mode header (the mode
  glyph and name the app sets) and a `#3A3A3A` left border; the bottom button in the dark button colours
  (`#1E1E1E`, pressed `#333333`, 20 px). No widget is renamed or moved except the row template's height; no code.
  Not done: a play marker image on the playing row and a count in the header (the row bind and the header are
  code), icons on the bottom button (it has none).
- **The queue** (the Now Playing list page, `playerjumpinfo_page`): the playing track's row carries the
  stock red `icon_playing` disc in place of its icon (set by the row bind `0x539244`, `is_playing` `0x4d9d64`; now the wave
  marker at the right end, as in Songs, and no disc at the left on any row), the rows are the
  q2-pod rows (white title, grey artist), and the navbar title (the queue's name, a `srlabel_leftwhite22_style`
  `hscroll_label` the page builds) is 20 px like every other navbar title of ours (page theme, `mod_lists.py`
  recipe `navtitle`; the other code-built library titles stay 22 px). The track count and numbers would need
  code; not done.
