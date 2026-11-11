"""The colour roles of the page builders (tools/pod_ui.py and its siblings; docs/modules/ui-rules.md "Text and colour roles"): one name for each value that more than one page uses. The three
near-black rest fill (SURFACE_RGB: cards, fields, flat pills, tiles) is one value; a per-page constant names the role it takes, never repeats the literal."""
INK_RGB = '#FFFFFF'           # the ink of every label on black, the keyboard's text
SUB_RGB = '#AAAAAA'           # the secondary text grey of every page: sub lines, footers, values, keys, credits, headers
HINT_RGB = SUB_RGB            # a page's empty-state hint (label_status): one line 20 px, a wrapped caption 18 px
RED_RGB = '#FF6B6B'           # the one red: a destructive row's label and glyph
PLACEHOLDER_RGB = '#8E8E93'   # a field's placeholder and its unit
CHEV_RGB = '#8A8A8A'          # the list chevron's grey
THUMB_RGB = '#2B2B2B'         # a thumbnail's placeholder grey
RAISED_RGB = '#2C2C2E'        # a raised dark surface: a pressed row, an off mode button, a rule, an input well
SURFACE_RGB = '#1C1C1E'       # the one near-black rest fill: Settings cards, the cache pill, keyboard and search fields, flat pills, a dialog button, the Library tiles' square, the dark ink on a light pill
CAPTION_PX = 18               # a group caption (the Settings, Wi-Fi, Search and Extras pages): 18 px SUB_RGB in a CAPTION_H strip, the label CAPTION_LABEL_H high CAPTION_LABEL_Y down it; a different role from the section title
CAPTION_H, CAPTION_LABEL_Y, CAPTION_LABEL_H = 40, 14, 22
SECTION_PX = 20               # a content section title (Songs' letters, the Podcasts sections, the Recently Played / Made for You shelf headings): 20 px INK_RGB
LINE_RGB = '#333333'          # a card's hairline, a flat pill pressed
