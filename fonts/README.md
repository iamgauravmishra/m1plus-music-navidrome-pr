Font sources that are not part of the repo (too large to commit), used by `tools/mod_font.py`
(the `look-all-inter` variant, `docs/font-inter.md`):

- `09_SourceHanSansSC.zip`: Source Han Sans 2.005R, Simplified Chinese OTFs (95 MB, SIL OFL 1.1),
  https://github.com/adobe-fonts/source-han-sans/releases/download/2.005R/09_SourceHanSansSC.zip
  SHA-256 `ef7364f7ac2564be1ae9c1d74276de2653fe38b73449070398c4fc0b7e032ff1`.
  `python3 -I tools/mod_font.py --fetch` downloads and checks it.

The Inter subset is committed (`assets/fonts/Inter-m1plus.ttf`, made by `tools/font_inter.py`).
