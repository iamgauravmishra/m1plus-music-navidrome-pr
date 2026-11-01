# The updater's version compare (official firmware over the mod)

The TF-card updater refuses a package whose line-2 version `strcmp`-equals the built-in literal
`"V2.1"` (`demo` `.rodata` `0x74773c`, error -14). Shanling's official V2.1 package carries exactly
that, so an unpatched `demo` would refuse it once the mod is installed.

## Readers of the literal

| Reader | What it does with it | Patched |
|---|---|---|
| `update_firmware` `0x4e1124` (the `addiu a1` after `lw a1, GOT page 0x740000`) | `strcmp(package version, literal)`: equal -> `delete_updateremain`, error -14 | **yes** |
| `check_otginfo` `0x4d92ac` (online check, `parse_version` of the server reply) | equal -> -14 ("already the latest") | no |
| `systemset_fwdownload_page_init` `0x4a7028` (online update page) | equal -> back out; else the update message | no |
| About row `Firmware` `0x4a14cc` (stock page and our About card) | prints the literal | no |

The literal is 4 characters plus NUL, followed by padding to `0x747740`, and is not merged with any
other string (the four references above are all of them).

## The change

One pinned word, `UPDATE_SITE` in `tools/pod.py`: `0x24a5773c` (`addiu a1,a1,0x773c`) becomes
`0x24a5772c`, so `update_firmware` compares the package version with the string `"about_version"`
(`0x74772c`, an AWTK widget key; no package tag can equal it, and a tag must contain `V`). The
literal is untouched, so:

- official V2.1, `V2.1R`, our releases (`V2.1-x.y.z`) and dev tags (`V2.1z...`) all install over the
  mod; package tags stay as they are;
- the online check still compares against `"V2.1"`: a server reply of V2.1 reads as "latest" as in
  stock, any other server version is offered as before (its download then passes the same compare);
- About keeps showing `V2.1`, our About card the build tag (`docs/modules/settings.md` "About").

`UPDATE_PINS` pin the compare's neighbouring words, the literal and the replacement string; the build
refuses on any mismatch. `test/demo_diff.py` checks the word, that the literal bytes are unchanged and
that nothing else in `.text` changed. `update_firmware` is not reachable from boot (`tools/reach.py`).

Device-tested (2026-11-01): the official V2.1 package installs over the mod and restores stock.
