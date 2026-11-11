"""Text coverage gamma (patch/textgamma.c, docs/modules/fonts.md "Coverage gamma").

AWTK's stb_truetype backend blends each glyph's 8-bit coverage straight into sRGB, so light text on black reads
thin. Every freshly rasterized mask is mapped once through a' = round(255 * (a / 255) ** (1 / G)). GAMMA is the
build's G; a 1.25 build is this one line. lut() is the table tools/pod.py writes into stock.h as TEXT_GAMMA_LUT,
and tools/preview/preview_aa.py draws its sheet with it, so the preview and the device agree.
"""

GAMMA = 1.45


def lut(gamma=GAMMA):
    """The 256-entry coverage map of one gamma."""
    return [round(255 * (a / 255) ** (1 / gamma)) for a in range(256)]
