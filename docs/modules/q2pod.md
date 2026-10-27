# How this maps to q2-pod

Split out of docs/architecture.md. A "section N" in the text is an old section number of `docs/architecture.md` (or of `docs/ui.md` in the asset notes); the "Old §" columns of those two index files map them to module files.

## 12. How this maps to q2-pod

| q2-pod | here |
|---|---|
| `tools/build.py` `append_payload`, `HOOKS`, `patch_word`, `fileoff`, prologue checks | `tools/pod.py` |
| `tools/peq.py` `compile_common` (GOT stubs, FLAGS, trampoline) | `tools/pod.py` `gen_asm` / `compile_payload` |
| `patch/link.ld`, `patch/offsets.inc` | `patch/link.ld`, `patch/offsets.inc`, `tools/pod_pages.py` |
| `patch/navigation.c` | `patch/m1pod.c`, `shuffle.c`, `artists.c` |
| `patch/coverflow.c` (wheel-driven) | `patch/coverflow.c` (renderer and cache design, touch-driven, this model's queries) |
| `patch/ipod.json`, `compact_row_layout` | `patch/rows.json`, `patch/rows.c` |
| `test/coverflow.py`, `test/patch.py` | `test/coverflow.py`, `test/patch.py` + `test/pod/` |

q2-pod hooks dozens of sites for a full scroll-wheel reskin; M1+ Pod hooks one user-initiated site, one
guarded start-up site, the album page's header builder and Now Playing's init (reached only while those pages build), and adds pages.
