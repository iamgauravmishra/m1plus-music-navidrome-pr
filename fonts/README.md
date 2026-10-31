Font sources that are not part of the repo (too large to commit), used by `tools/mod_font.py`
(the release build, `docs/ui.md`):

- `01_SourceHanSans.ttc.zip`: Source Han Sans 2.005R, every weight and region in one TTC (96 MB, SIL OFL 1.1),
  https://github.com/adobe-fonts/source-han-sans/releases/download/2.005R/01_SourceHanSans.ttc.zip
  SHA-256 `a024cf1759494847cd47aae4379bcb3dc530017c709f3f503ee0ed918dd92952`.
  `python3 -I tools/mod_font.py --fetch` downloads and checks it.

The Inter subset is committed (`assets/fonts/Inter-m1plus.ttf`, made by `tools/font_inter.py`).
