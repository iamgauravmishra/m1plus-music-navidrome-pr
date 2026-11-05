#pragma once
/* patch/textgamma.c: the text coverage gamma of the default font (docs/modules/fonts.md "Coverage gamma"). */
int tg_get_glyph(unsigned char *f, unsigned ch, unsigned size, unsigned char *out);
int tg_stb_slot(const unsigned char *f);
void tg_apply(void *fm, unsigned char *f);
