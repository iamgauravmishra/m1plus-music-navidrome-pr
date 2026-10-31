# Overlay screens (`tools/mod_overlays.py`, `tools/preview_overlays.py`, `test/pod/overlays.py`)

Two stock-looking screens restyled with assets only (no code, no new or renamed widget): the message and confirm dialogs and the power-off splash. The step runs after `mod_polish`
in `tools/build.py`. It copies PNGs committed in `assets/overlays/` (`mod_overlays.py --generate` redraws them: Pillow, `rsvg-convert` for the splash), refuses any file that is not
the pinned stock one (`tools/mod_overlays_pins.txt`, SHA-256, `--pins`), keeps the file mode and the stock pixel sizes. Preview: `uv run python -I tools/preview_overlays.py work/mod-release out/preview/overlays.png`
(not tracked). The Update Library spinner, the charging screen and the USB DAC / storage page stay stock on purpose (another branch works on them).

- **Message and confirm dialogs** (`msginfo_bg`, `confirminfo_bg`, 260 x 180, default and theme1: the same stock bytes). A glass card, `mod_icons.glass_image(260, 180, 12, fill=DIALOG_FILL)`
  (the More sheet's pane, alpha 0.94: the text sits on it with the page dimmed behind by the dialogs' own `highlight` alpha 100); the confirm card also has the
  13 % white horizontal divider at y 130 (stock y 130). The stock buttons were opaque black over the image: `confirminfo_dialog` (`btn_cancel`, `btn_enter`) and `rippercompleted_dialog` (one
  `btn_enter`, which shares `confirminfo_bg`) get `bg_color` transparent in the non-pressed states and the pressed corner radii 11 (the card's, minus its 1 px inset); the pressed fill is
  mod_lists' neutral row colour as before. The vertical divider is `btn_cancel`'s right border (`border=right`, `#FFFFFF22`), not in the image, because the ripper dialog has no second
  button. Widget names and rectangles unchanged. The contrast scan (`mod_theme --scan`) passes. The card is translucent: a dialog opened over the More sheet would show it through
  (`docs/modules/playmore.md` "Dialogs over the sheet": the sheet closes first).
- **Message box vs confirm box** (device report: the message screen did not look like the confirmation box). Checked statically: `msginfo_dialog.bin` and `confirminfo_dialog.bin` resolve to the same card (transparent fill and border, radius 12, one picture, the two pictures differ only by the divider, both themes: theme1 has neither ui file), neither has a page theme that matters (`styles/confirminfo_dialog.bin` only holds check-box styles), the stock msginfo init (`0x478610`) only creates labels (`srlabel_msgwhite_style` 20 px white, `srlabel_msggray_style` 18 px, `navbar_centerlabel_white` for the A-B toast, as the confirm's labels) and a timer, and calls no resize, move or style on the dialog; so no difference was found in msginfo itself. What did differ: the other message-like 260 x 180 stock dialogs, still black with a grey `#666666` border: `cardupdate_dialog` (card update), `formatcard_dialog` (formatting) and `dialog_autoshutdown` (the sleep countdown, one full-width button). They now get the same card (`CARD_DIALOGS`: msginfo_bg for the first two, confirminfo_bg and a transparent button for the countdown); `btscan_dialog` (Bluetooth) is left. `test/pod/overlays.py` compares the dialogs' resolved card styles with the confirm box's. If the message box still looks different on the device, a screenshot is needed.
- **Power-off splash** (`shutdown`, 320 x 480, `ui/poweroff_page.bin` `img_shutdown`; the page itself is stock): the boot splash raster (`assets/boot-logo.svg`, `docs/modules/boot.md`).

## Tests (`test/pod/overlays.py`)

Pins cover the three names; built files are the committed assets; theme1 gets the same two dialog images; the scan, charging, battery and USB images and `poweroff_page.bin` are stock bytes; sizes;
glass and divider; the ui edits (transparent buttons, Cancel's border, geometry unchanged). `test/pod/navbars.py` exempts the replaced files (`mod_overlays.NAMES`, `OVERLAY_UI`).

## Device check

Delete a song (confirm card: rounded glass, divider, No / Yes legible, pressed halves follow the card's corners without poking out, the vertical divider present, no sheet behind it); a message dialog;
the CD ripper's completed dialog (one button, no vertical line); power off (the M1+ splash).
