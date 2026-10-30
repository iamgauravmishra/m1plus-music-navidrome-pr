# Customize and launcher

Sources: `patch/m1plus.c`, `patch/home.c`, `patch/covercache.c`, `patch/tape.c` and
`tools/pod_pages.py`. User instructions are in the [guide](../guide.md#customize).

Customize is item 18 (`j`), hidden from the main menu by default. The Extras navbar always
provides access, and it cannot be turned off. Its rows open Main Menu, Extras, Home Screen,
Cover Flow, Cassette Mode, Playback, System Settings and Developer. The two stock settings
pages use Home dispatcher IDs 16 and 17; Developer contains Screenshot and Network Probe ([probe](probe.md)).

## Persisted choices

Switches and value rows save before updating their image/label. A failed atomic save leaves
the file and displayed state unchanged. Reading settings never writes them.

| Setting | File under `/mnt/data/` | Values/default |
|---|---|---|
| Boot to M1+ Music | `m1plus-start` | `0` stock Home; missing/other enables M1+ Music |
| Recent Albums | `m1plus-shelf` | `0` off; missing/other on |
| Daily Mix | `m1plus-daily` | `0` off; missing/other on |
| Landscape | `m1plus-landscape` | `1` landscape; default portrait |
| Album sort | `m1plus-cfsort` | `0` or `0\n` Album; missing/other Artist |
| Cassette Theme | `m1plus-tapetheme` | `1` Chrome, `2` Metal, optional newline; missing/other Normal |

Home Screen also has Regenerate Daily Mix and Shanling Home. Regenerate is an action without
a chevron: it requests a new seed, and the Home page rebuilds when next foregrounded. Shelf
and mix visibility are reread when returning to Home. The separate Recent Albums translation
fits switch rows where Recently Played would overflow.

Cassette Theme cycles Normal → Chrome → Metal. `tape_theme` reads it when the Tape page opens;
a change affects the next open. Value labels use translation keys, not fixed English text.

## Rebuild Covers

`ACT_REBUILD` calls `rebuild_ask`, which opens stock `dialog/confirminfo_dialog` through
`navigator_to_with_context`. The context is `{kind, ms, text[0x200], text2[0x200]}`; text starts
at +8. Kind 5 gives wrapped 20 px text in a 260 × 80 box at y 25. Kind 1 scrolls one line and
must not be used for this message. Evidence: `dialog_confirminfo_dialog_init` `0x472cec`,
branch `0x472e1c`; stock equalizer reset `on_eqreset_onclick` `0x49dd6c` uses the same dialog.

Only `CONFIRM_YES` (`0xa`, `btn_enter`) starts `coverflow_rebuild`; No or a failed dialog does
nothing. The translated message is checked in all 16 tables. Rebuild opens Preparing and
regenerates covers, including no-art markers; Cancel/Back retains completed cache entries.
The kind-5 appearance still needs device confirmation.

## Album ordering and initial selection

`cc_album_order` keeps the stock deque unchanged and creates an `order[]` of stock row numbers:

- **Album:** stock title order, ASCII case-insensitive.
- **Artist:** representative track's `songer`, then album title; ASCII case-folded with a
  leading `The ` removed, ties resolved by stock position. There is no album-artist fallback
  because the query does not fetch that field. Unknown Album (ID -1) goes last.

The permutation uses heapsort; access goes through `cc_row`, and stock album opens receive
`order[i]`. Albums and main Cover Flow share it. Per-artist Cover Flow retains its stock album
title order. Cache keys remain artist + album title.

At open, `find_playing` checks `cc_playing`: `mclGetPlayPos` `0x5d4290` and `PLAY_QUEUE`
`0xa0394c`, bounded by `deque_size`. It matches the album by `cc_album_key` (FNV of artist/title),
then title ignoring ASCII case for compilations. Selection priority is playing album, saved
`LAST_ALBUM`, then first album. This is a one-time lookup, not polling.

## Shanling Home and startup

Shanling Home sets the session's `grid` flag, shows the stock grid and closes the recorded menu,
Extras and Customize windows by handle before navigating back from Home Screen. It does not
issue repeated `navigator_back` calls against a closing window. Destroy handlers forget the
recorded handles.

When startup is enabled and the guard is armed, tapping grid icon 99 clears `grid` and opens
the Home menu instance; a failed open restores the prior state. With startup disabled, it opens
the normal instance. The Home instance hides the navbar (invisible and insensitive) and uses
`HOME_PAD` 10 with a 430 px list. The normal instance retains Back, title and Now Playing.
Missing widgets leave the stock layout. See [boot guard](home-guard.md) for startup safety.
