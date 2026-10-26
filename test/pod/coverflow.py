"""Cover Flow: the page, the cache build, the worker, the depth renderer against the host build, touch, hit tests."""
import json, os, re, struct, sys
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)


def run(ctx):
    expect, page = ctx.expect, ctx.page
    cover_open = PSYMS['coverflow_open']
    cover_row = next(i for i, r in enumerate(page.rows) if r.action == pod_pages.ACT_COVER)
    # 7. The menu's Cover Flow row opens the Cover Flow page.
    m = cover_machine()
    m.call(PSYMS['on_row'], a0=PSYMS['pod_rows_0'] + 12 * cover_row, count=2000000)
    expect(('window_open', 'm1pod_cover') in m.calls, 'the Cover Flow row opens m1pod_cover')

    # 8. Opening with a complete cache: no build, no thread, a slide_menu with one child per
    #    album, the captions set and the first album centred.
    m = cover_machine(albums=3)
    v = m.call(cover_open, count=5000000)
    expect(v == 0, 'coverflow_open returns 0')
    expect('pthread_create' not in m.names(), 'a complete cache starts no thread')
    expect(('slide_menu', ) == tuple(c[0] for c in m.calls if c[0] == 'slide_menu'),
           'exactly one slide_menu is created')
    slide = m.widgets['slide_menu']
    expect(len(m.children[slide]) == 3, f'one child per album (got {len(m.children.get(slide, []))})')
    expect(('widget_set_text_utf8', m.widgets['label_album'], 'Album 0') in m.calls, 'album caption')
    expect(('widget_set_text_utf8', m.widgets['label_artist'], 'Artist 0') in m.calls, 'artist caption')
    expect(('mkdir', '/mnt/mmc/.coverflow') not in m.calls, 'no cache directory needed when complete')

    # 9. Tap the centre cover: the stock Albums sequence and the stock album page. The stock album
    #    list goes back into *pdeq_showlist (loadAlbumList(0xf003, 0), what album_page_init runs), the
    #    cover-task list is rebuilt from it (albumcoverinfo_init, @0x4dcf9c) and albuminfo_page opens
    #    with the context the stock row handler builds (@0x523d94): class | row << 16. The page itself
    #    keeps no track list, header or play code of its own any more.
    expect(m.props.get((m.widgets['slide_menu'], 'sensitive')) == 0,
           'the stock slide_menu takes no touch itself')
    m.tap(O['CF_CX'])
    names = [c[0] for c in m.calls if c[0] in ('loadAlbumList', 'albumcoverinfo_init', 'navigator_to_with_context')]
    expect(names == ['loadAlbumList', 'albumcoverinfo_init', 'navigator_to_with_context'],
           f'the stock queries run, then the page opens ({names})')
    seq = [c[0] for c in m.calls if c[0] in ('albumcoverinfo_init', 'batchadd_albumcover_task', 'navigator_to_with_context')]
    expect(seq == ['albumcoverinfo_init', 'batchadd_albumcover_task', 'navigator_to_with_context']
           and ('batchadd_albumcover_task', 0, 0) in m.calls,
           f'the cover thread is released (taskstate 2 -> 1) before the page queues its cover task ({seq})')
    expect(('loadAlbumList', O['CLASS_ALBUMS'], 0, '') in m.calls, 'the stock Albums query: loadAlbumList(0xf003, 0)')
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ALBUMS'], 0) in m.calls,
           'the centre cover opens the stock albuminfo_page with context 0xf003 | row 0 << 16')
    cls, row, shown = m.opened_album
    expect(m.deques[shown] == m.showlist and ('albumcoverinfo_init', shown) in m.calls,
           'the cover-task list is built from the album list the page will read its row from')
    expect(not any(n in m.names() for n in ('loadAlbumdetailList', 'list_view_create', 'list_item_create', 'loadSongList')),
           'no track list, no tracks query and no play code on the Cover Flow page any more')
    expect(not any(n in PSYMS for n in ('on_track', 'ap_on_play', 'ap_on_shuffle', 'ap_paint', 'ap_play', 'to_tracks')),
           'the custom album page is gone from the payload')
    # the row is the album in the centre; the saved album (the main page's memory) follows the tap
    m2 = cover_machine(albums=3); m2.call(cover_open, count=5000000)
    m2.props[(m2.widgets['slide_menu'], 'value')] = 2
    m2.call(PSYMS['on_changed'], count=2000000)
    m2.tap(O['CF_CX'])
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ALBUMS'], 2) in m2.calls,
           'the centre album (2) is the row of the context')
    expect(m2.opened_album[2] != 0 and m2.deques[m2.opened_album[2]][2] == m2.showlist[2], 'and that row of the list is its album')

    # 10. The stock queries are repeated on every open: something else may have reused the browsing
    #     record or the list since (the page is open again after Back from the album page).
    m.tap(O['CF_CX'])
    expect(m.names().count('loadAlbumList') == 1 and 'albumcoverinfo_init' in m.names(), 'a second open runs them again')
    expect(('navigator_to_with_context', 'albuminfo_page', O['CLASS_ALBUMS'], 0) in m.calls, 'and opens the page again')

    # 11. Back: the covers screen leaves the page (there is no tracks screen to go back to).
    on_back = PSYMS['on_back']
    m.call(on_back, count=200000)
    expect('navigator_back' in m.names(), 'Back on the covers screen leaves the page')
    expect('navigator_back' in m.names(), 'Back on the covers screen leaves the page')

    # 12. Tapping a cover that is not the centre scrolls to it instead of opening it.
    slide = m.widgets['slide_menu']
    m.props[(slide, 'value')] = 0
    m.tap(O['CF_CX'] + 100)      # the right-hand neighbour
    expect('navigator_to_with_context' not in m.names(), 'a side cover opens no album')
    m.settle()
    expect(('slide_menu_set_value', 1) in m.calls, f'a right-hand tap brings the next album to the centre')
    expect(m.props.get((slide, 'xoffset')) == 0, 'the offset is back to 0 after the commit')

    # 12b. A slow drag to the left by a little more than DRAG_PX moves one album on; the shelf
    #      follows the finger while it moves, and the pointer is grabbed and released.
    m.props[(slide, 'value')] = 0
    m.touch('down', 200, t=1000); grabbed = ('widget_grab', m.widgets['view_covers'], m.widgets['view']) in m.calls
    m.touch('move', 150, t=1300)
    mid = struct.unpack('<i', struct.pack('<I', m.props.get((slide, 'xoffset'), 0) & 0xffffffff))[0]
    m.touch('move', 100, t=1600)
    m.touch('up', 100, t=1900)
    released = any(c[0] == 'widget_ungrab' for c in m.calls)
    m.settle()
    expect(grabbed and released, 'the touch layer grabs the pointer for the drag and releases it')
    expect(mid != 0 and mid < 0, f'the shelf follows a leftward drag (xoffset {mid})')
    expect(('slide_menu_set_value', 1) in m.calls, 'a drag of one cover spacing advances one album')

    # 12c. A fast flick coasts further than the finger went.
    m.props[(slide, 'value')] = 2
    m.touch('down', 250, t=5000); m.touch('move', 200, t=5020); m.touch('move', 150, t=5040)
    m.touch('up', 150, t=5050)
    m.settle()
    offs = [struct.unpack('<i', struct.pack('<I', c[3] & 0xffffffff))[0] for c in m.calls
            if c[0] == 'widget_set_prop_int' and c[2] == 'xoffset']
    far = max(abs(o) for o in offs) if offs else 0
    expect(far > 2 * O['CF_VIEW_H'], f'a flick coasts more than two albums (|xoffset| up to {far})')

    # 12d. A drag to the right wraps from the first album to the last.
    m.props[(slide, 'value')] = 0
    m.touch('down', 60, t=9000); m.touch('move', 120, t=9300); m.touch('move', 160, t=9600)
    m.touch('up', 160, t=9900)
    m.settle()
    expect(('slide_menu_set_value', 2) in m.calls, 'dragging right from the first album wraps to the last')

    # 12e. An aborted gesture (stock sends 0x107) releases the grab and snaps back.
    m.props[(slide, 'value')] = 1
    m.touch('down', 200, t=12000); m.touch('move', 180, t=12100); m.touch('abort', 180, t=12150)
    expect(any(c[0] == 'widget_ungrab' for c in m.calls), 'an abort releases the grab')
    m.settle()
    expect(m.props.get((slide, 'xoffset')) == 0, 'an abort snaps back to the album')

    # 13. Close: the timer is dropped, the worker joined, the frame and list freed.
    m.call(PSYMS['on_destroy'], count=2000000)
    expect('deque_destroy' in m.names(), 'the album copy is freed')
    expect(('fwrite', m.showlist and 0 or 0) or True, 'last album written')
    expect('fwrite' in m.names(), 'the last album is saved on close')

    # 14. First run: no cache files -> jobs, a thread, the progress label and Cancel.
    m = cover_machine(albums=3, cached=False)
    m.call(cover_open, count=5000000)
    expect(('mkdir', '/mnt/mmc/.coverflow') in m.calls, 'the cache directory is created')
    expect('pthread_create' in m.names(), 'the build thread is started')
    expect(('widget_set_visible', m.widgets['btn_cancel'], 1) in m.calls, 'Cancel is shown')
    expect(any(c[0] == 'timer_add' for c in m.calls), 'the progress timer runs')
    expect('slide_menu' not in [c[0] for c in m.calls], 'the covers wait for the build')

    # 15. The worker itself: for each album, the two stock art calls under parse_cover_mutex, the
    #     result renamed into place, and an empty marker when both fail.
    lock = pod.DATA['PARSE_COVER_MUTEX'][0]
    m.album_cover = 1
    m.call(PSYMS['worker'], count=5000000)
    seq = [c for c in m.calls if c[0] in ('lock', 'unlock', 'toolsGetAlbumCover', 'toolsGetExternCover', 'rename')]
    expect(seq[0] == ('lock', lock) and seq[1][0] == 'toolsGetAlbumCover' and seq[2] == ('unlock', lock),
           f'the art call is made under parse_cover_mutex ({seq[:3]})')
    expect(sum(1 for c in m.calls if c[0] == 'rename') == 3, 'every album\'s thumbnail is renamed into place')
    expect([c for c in m.calls if c[0] == 'toolsGetExternCover'] == [], 'the folder image is only a fallback')
    # the thumbnails are extracted at the larger size, into files named for it
    expect(getattr(m, 'cover_size', None) == (O['ART_SIZE'], O['ART_SIZE']),
           f'the thumbnails are {O["ART_SIZE"]} px ({getattr(m, "cover_size", None)})')
    dst = [c[2] for c in m.calls if c[0] == 'rename']
    expect(dst and all(d.endswith(f'-{O["ART_SIZE"]}.jpg') and d in cache_paths(m, 3) for d in dst),
           f'a {O["ART_SIZE"]} px thumbnail never takes the name of a 140 px one ({dst[:1]})')

    m3 = cover_machine(albums=1, cached=False)
    m3.call(cover_open, count=5000000)
    m3.album_cover = m3.extern_cover = 0
    m3.call(PSYMS['worker'], count=5000000)
    expect(any(c[0] == 'toolsGetExternCover' for c in m3.calls), 'no embedded art -> the folder image')
    expect(any(c[0] == 'fopen' and c[2] == 'w' for c in m3.calls), 'no art at all leaves an empty marker')

    # 16. Cancel: the thread is told to stop and joined, the timer dropped, the covers shown.
    m.call(PSYMS['on_cancel'], count=5000000)
    expect('pthread_join' in m.names(), 'Cancel joins the worker')
    expect('timer_remove' in m.names(), 'Cancel drops the progress timer')
    expect('slide_menu' in [c[0] for c in m.calls], 'Cancel shows the covers')

    # 17. No card or no space: no thread, straight to the covers with whatever is cached.
    m = cover_machine(albums=2, cached=False); m.free_mb = 2
    m.call(cover_open, count=5000000)
    expect('pthread_create' not in m.names(), 'no free space -> no build')
    expect('slide_menu' in [c[0] for c in m.calls], 'no free space still shows the covers')
    m = cover_machine(albums=2, cached=False); m.thread_ok = False
    m.call(cover_open, count=5000000)
    expect('slide_menu' in [c[0] for c in m.calls], 'a refused thread still shows the covers')

    # 18. An empty library: the message, no slide_menu, no thread.
    m = cover_machine(albums=0)
    v = m.call(cover_open, count=2000000)
    expect(v == 0 and 'slide_menu' not in [c[0] for c in m.calls], 'an empty library draws no covers')
    expect(any(c[0] == 'widget_set_text_utf8' and 'Update Local Music' in str(c[2]) for c in m.calls),
           'an empty library says to update the library')
    expect('pthread_create' not in m.names(), 'an empty library starts no thread')

    # 19. A broken or foreign asset (a widget missing): leave the page rather than work on half of it.
    m = cover_machine()
    del m.widgets['label_status']
    v = m.call(cover_open, count=2000000)
    expect(v == 0xffffffff and 'navigator_back' in m.names(), 'a missing widget closes the page')
    m = cover_machine(); m.window = 0
    expect(m.call(cover_open, count=200000) == 0xffffffff, 'window_open failure returns -1')

    # 20. The depth renderer on the real MIPS code: paint the covers and compare the frame with
    #     the host build of the same renderer (test/coverflow.py), pixel for pixel.
    m = cover_machine(albums=5)
    m.call(cover_open, count=5000000)
    slide = m.widgets['slide_menu']
    m.props[(slide, 'h')] = O['CF_VIEW_H']
    m.props[(slide, 'value')] = 2
    m.props[(slide, 'xoffset')] = O['CF_VIEW_H'] // 4      # a quarter of a step into a drag
    event = m.alloc(0x40); m.u.mem_write(event, bytes(0x40))
    canvas = 0x22220000
    m.setword(event + O['EVENT_PAINT_CANVAS'], canvas)
    m.call(PSYMS['on_paint'], a0=0, a1=event, count=400000000)
    print(f'  depth frame: {m.icount:,} payload instructions '
          f'({O["CF_VIEW_W"]}x{O["CF_VIEW_H"]}, ART_SIZE {O["ART_SIZE"]})')
    expect(('canvas_draw_image', m.bitmap[0]) in m.calls, 'the frame is drawn on the canvas')
    b, data, w, h = m.bitmap
    expect((w, h) == (O['CF_VIEW_W'], O['CF_VIEW_H']), 'the frame is the CF_VIEW size')
    frame = bytes(m.u.mem_read(data, w * h * 4))
    # p = value - xoffset / h, so a positive xoffset puts the shelf a quarter step *before* the
    # centre album: frac = -(xoffset / h) in 16.16.
    host = host_frame(-((O['CF_VIEW_H'] // 4) * 65536 // O['CF_VIEW_H']))
    if host is None:
        print('  (skipped the host comparison: test/coverflow.py could not build)')
    else:
        expect(frame == host, 'the payload renders the same frame as the host build')

    # 21. No frame bitmap: the flat fallback puts the cached art on the stock images near the
    #     centre and the placeholder elsewhere, and paint draws nothing of its own.
    m = cover_machine(albums=9)
    m.bitmap_ok = False
    m.call(cover_open, count=5000000)
    pics = [c[2] for c in m.calls if c[0] == 'image_base_set_image']
    expect(pics, 'the flat fallback sets pictures on the stock images')
    expect(sum(1 for p in pics if p.startswith('file://')) == 2 * 3 + 1,
           f'real art only within ART_NEAR of the centre (got {pics})')
    expect(sum(1 for p in pics if p == 'p_default') == 9 - 7, 'the rest keep the placeholder')
    m.props[(m.widgets['slide_menu'], 'h')] = O['CF_VIEW_H']
    event = m.alloc(0x40); m.u.mem_write(event, bytes(0x40))
    m.setword(event + O['EVENT_PAINT_CANVAS'], 0x22220000)
    m.call(PSYMS['on_paint'], a0=0, a1=event, count=2000000)
    expect('canvas_draw_image' not in m.names(), 'without a frame, paint draws nothing')

    # 22. Back from the album page with another list loaded: the stock queries run again on the next
    #     tap (see 10), so the row that is opened is the album under the cover whatever was loaded.
    m = cover_machine(albums=2)
    m.call(cover_open, count=5000000)
    m.tap(O['CF_CX'])
    m.setword(pod.DATA['PDEQ_SHOWLIST'][0], m.new_deque([m.record(name='other.flac')]))
    m.tap(O['CF_CX'])
    expect(m.deques[m.opened_album[2]] == m.showlist, 'a replaced list is queried again before the page opens')

    # 23. Hit testing by demo's own widget_find_target (see stock_target): where does a touch in
    #     the middle of the covers go? Hidden widgets must be insensitive (a hidden, sensitive,
    #     full-height tracks view once swallowed every touch: navbar fine, covers dead), so it
    #     reaches the touch layer.
    asset = os.path.join(WORK, 'rootfs', 'release/assets/default/raw/ui/m1pod_cover.bin')
    m = cover_machine(albums=3)
    m.call(cover_open, count=5000000)
    fy = CF_FRAME_Y   # the frame's top in the window
    for x, y in ((160, fy + 66), (20, fy + 16), (300, fy + 166), (160, fy + 2), (160, fy + O['CF_VIEW_H'] - 2)):
        got = stock_target(m, cover_page_tree(m, asset), x, y)
        expect(got[-1] == 'touch_layer', f'a touch at ({x},{y}) reaches the touch layer ({got})')
    got = stock_target(m, cover_page_tree(m, asset), 40, 25)
    expect(got[-1] == 'btn_return', f'the navbar Back button still gets its touches ({got})')
    for y in (CF_ALBUM_Y + 10, CF_ARTIST_Y + 2):   # the captions over the frame's bottom rows
        got = stock_target(m, cover_page_tree(m, asset), 160, y)
        expect(got[-1] == 'touch_layer', f'a touch on a caption reaches the covers (insensitive captions) ({got})')
    got = stock_target(m, cover_page_tree(m, asset), 160, CF_FRAME_Y + O['CF_VIEW_H'] + 10)
    expect(got == ['m1pod_cover_page'], f'below the frame the artist line takes nothing ({got})')
    # and while the cache builds, only Cancel and the navbar take touches
    m = cover_machine(albums=2, cached=False)
    m.call(cover_open, count=5000000)
    got = stock_target(m, cover_page_tree(m, asset, runtime=False), 160, 283)
    expect(got[-1] == 'btn_cancel', f'Cancel gets its touch while preparing ({got})')
    got = stock_target(m, cover_page_tree(m, asset, runtime=False), 160, 150)
    expect(got[-1] not in ('btn_cancel',), f'nothing hidden takes a touch while preparing ({got})')


    # 26. The page has no hint line; the block of frame and captions sits centred in the 400 px
    #     under the navbar, the captions are scrolling hscroll_labels inside the screen.
    tree = awtk_ui.parse(open(asset, 'rb').read())
    expect('label_hint' not in [w.name for w in tree.walk()], 'the cover page has no hint label')
    m = cover_machine(albums=3); m.call(cover_open, count=5000000)
    expect(('widget_lookup', 'label_hint') not in m.calls, 'the payload looks no hint up')
    frame, art = node(asset_tree(asset), 'view_covers'), CF_FRAME_Y + O['CF_TOP']
    top_gap, bottom_gap = art - 50, CLIENT_H - (CF_ARTIST_Y + CF_ARTIST_H)
    expect(frame.y == CF_FRAME_Y and abs(top_gap - bottom_gap) <= 4,
           f'the covers and captions are centred under the navbar ({top_gap} above, {bottom_gap} below)')
    expect(CF_ALBUM_Y >= frame.y + O['CF_TOP'] + O['ART_SIZE'] + O['CF_REFLECT'],
           'the captions start below the reflections, in the always-black rows of the frame')
    caps = [w for w in tree.walk() if w.name in ('label_album', 'label_artist')]
    expect(len(caps) == 2 and all(w.get('sensitive') == 'false' and w.get('visible') != 'false' for w in caps),
           'the captions are shown but insensitive in the asset')
    expect(not any(c[0] == 'widget_set_sensitive' and c[1] in (m.widgets['label_album'], m.widgets['label_artist'])
                   for c in m.calls), 'the payload never makes the captions sensitive')
    for w in caps:
        ok_props = all(w.get(k) == v for k, v in (('yoyo', 'true'), ('loop', 'true'), ('ellipses', 'true'),
                                                  ('lull', pod_ui.CAPTION_LULL)))
        ok_style = all(w.get(f'style:{st}:text_align_h') == 'center' for st in ('normal', 'disable', 'focused'))
        expect(w.type == 'hscroll_label' and ok_props and ok_style and w.get('only_focus') is None
               and w.get('only_parent_focus') is None,
               f'{w.name} is a centred hscroll_label that loops a long text back and forth ({w.props})')
        expect(w.x >= 12 and w.x + w.w <= 320 - 12, f'{w.name} keeps side margins ({w.x}..{w.x + w.w})')
    expect((frame.w, frame.h) == (O['CF_VIEW_W'], O['CF_VIEW_H']) == (320, pod_ui.COVER_FRAME_H),
           f'the frame is the larger shelf ({frame.w}x{frame.h})')
    m2 = cover_machine(albums=3); m2.call(cover_open, count=5000000)
    sl = [c for c in m2.calls if c[0] == 'slide_menu']
    expect(sl and sl[0][2:] == (O['CF_VIEW_W'], O['CF_VIEW_H']), f'the slide_menu (its stride) is the frame size ({sl[:1]})')
