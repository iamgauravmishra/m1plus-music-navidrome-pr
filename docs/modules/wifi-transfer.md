# Wi-Fi Transfer: web server side

Stock runs `thttpd -C /etc/thttpd.conf` when Wi-Fi Transfer is on (port 8888, `dir=/usr/share/web`,
`cgipat=**.cgi`, `user=root`). The mod leaves the player binary, thttpd and its configuration alone and
replaces what thttpd serves: one CGI, `/cgi-bin/api.cgi`, and a page. No hook, no payload change, nothing at
boot or paint. The page is one hand-written vanilla-JS file, `assets/webapp/index.html` (see "The page").

## Stock web app (removed)

A Chinese GCDWebUploader port: jQuery 1.7.2 + Bootstrap 3 (about 330 KB of css/js/fonts) and five cgic CGIs
(`cgi-bin/{list,upload,download,delete,create}.cgi`, symlinked at the web root). Known faults, all fixed by
`api.cgi`: `list.cgi` shows only a built-in extension whitelist; names are not JSON-escaped (one `"` or `\`
breaks a folder); delete, create and upload run `system("rm -rf \"%s\"")`, `mkdir "%s"` and `mv "%s" "%s" -f`
after only a `/mnt/mmc` prefix check (shell injection, `../` escape); upload buffers the whole multipart body in
`/mnt/mmc/cgicXXXXXX`.

## The page

`assets/webapp/index.html` (about 68 KB, installed by `mod_webapp` as `usr/share/web/index.html`): HTML, CSS and
JS in one file, no libraries, no external requests, no fonts. Title "M1 Plus", subtitle "Wi-Fi Transfer".
Light or dark by `prefers-color-scheme` unless the user picked one; black/white/grey. List view only (no thumbnails or previews: the
player's CPU serves every byte).

- Folder path in the URL hash (`#/Music/Album`), so Back/Forward work; breadcrumbs (root included) are links.
  Listings come from `list`, sorted in the page by name/date/size (folders first); a filter box narrows the
  current folder. Storage bar from `df`, refreshed after uploads and deletes.
- Tap a folder: opens it. Tap a file: selects it only. Double-click a file, the "..." menu and the selection bar
  download. With a selection, the selection bar replaces the crumbs and tools row (phones: only the tools row)
  at fixed heights, so nothing shifts. Esc clears, Cmd/Ctrl+A selects all, Delete deletes, "/" focuses the filter.
  Dragging rows onto a folder or crumb moves them.
- One file downloads with `op=download` (a link); a folder or several items with `op=tar`, a hidden form POST
  into a hidden iframe (paths in the body; a refusal shows as a toast).
- New Folder, Rename, Move (a folder-tree picker that lists one level at a time, starting with the root and the
  chain to the current folder) and Delete confirm dialogs. Move/delete/tar send their paths in a POST body.
  Every mutating request is a POST with `Content-Type: application/octet-stream`.
- Upload: Upload Files, Upload Folder or drop anywhere (folders keep their tree: each parent is created with
  `mkdir`, parents first, once per batch; dot files such as `.DS_Store` and `._*` are skipped). One file at a
  time, one XHR each: a file below 2 GiB is a single request, from 2 GiB on 1 GiB chunks (`offset`, `last`). The
  free space is checked against `df` before queueing. A name clash (409 with `conflict=fail`) asks Replace / Skip
  / Keep Both with "Apply to all remaining" (Escape or a click outside counts as Skip, so the queue goes on), then resends with `replace` or `keep`. The queue panel shows overall
  progress, size left and ETA (measured upload rate), per-file progress, cancel (aborts the request; the server
  deletes the `.part`) and retry. A cancelled or failed chunked upload leaves its hidden `.part` (nothing can
  delete it unless Show Hidden Files is on; the next upload of the name truncates it). Empty folders in a dropped tree are not
  created. The listing refreshes at most every 5 s while uploading and at the end.
- Names with exFAT-illegal characters are refused in the dialogs and in the queue before anything is sent; the
  server's own `{"error"}` text shows in a toast otherwise.
- Show Hidden Files (header eye button, `localStorage` `wt-hidden`, default off): every request then carries `hidden=1`; dot names are listed dimmed, and turning it off inside a dot folder goes up to the first visible parent. `.m1plus` and everything below it is read-only: New Folder, Upload, Rename, Move, Delete and dropping files are disabled there (the move picker leaves it out).
- Header controls (top right): a language `<select>` (Auto + the 13 native names, `localStorage` `wt-lang`; a change
  re-renders labels, crumbs, listing, space and the queue panel without a reload; an open dialog keeps its
  language until closed) and a theme button cycling Auto, Light, Dark (`wt-theme`). A script in `<head>` sets
  `data-theme` on `<html>` before first paint; the dark variables apply for `:root[data-theme=dark]` and, in
  Auto (no attribute), under the `prefers-color-scheme` query; `color-scheme` follows. Phones show both as icons.
  Storage access is wrapped in try/catch (private mode keeps the choice for the page's life only).
- Strings: the browser language (`navigator.languages`), English fallback; the mod's 13 languages (codes `en zh
  zh-HK ja ko fr de es it th pl ru uk`, Traditional Chinese for `zh-HK/TW/MO/Hant`). The table is the `STR` JSON
  object in the page (generated once from a Python table; nine words reuse `tools/pod_i18n.py` translations).

## Build and packaging

`tools/mod_webapp.py` (step `mod_webapp` in `tools/build.py`, after `mod_cacerts`):

- removes all 23 stock files below `usr/share/web` except `favicon.ico` (each pinned by SHA-256), the five
  symlinks (pinned by target) and the `css`, `js`, `fonts` directories; `removed_rels()` is the build's
  `--allow-removed` list (`pack_args`), `added_rels()` the `--allow-added` one;
- replaces `index.html` (pinned stock hash) with `assets/webapp/index.html`;
- builds `patch/webapi.c` and installs it as `usr/share/web/cgi-bin/api.cgi`, mode 755, stock mtime.

Build cache: `tools/buildcache.py` records the directories a step removes (the stock `css`, `js`, `fonts`) with its removed files and replays them, so a cached build has the same tree as a fresh one.

Freed: 686,625 bytes of files (web root 695,898 -> 27,232 bytes in the tree); the squashfs size is in the dev
build log (`rootfs.squashfs: N bytes (stock M)`; fwtool fails above stock).

### The executable

`api.cgi` is a static, libc-free MIPS32r2 o32 executable (about 24 KB): `clang --target=mipsel-linux-gnu
-march=mips32r2 -mabi=32 -msoft-float -mnan=2008 -mno-abicalls -fno-pic -G0 -ffreestanding -fno-builtin -Os`,
`ld.lld -m elf32ltsmip -static -nostdlib -e __start --gc-sections -s`, then `llvm-objcopy` drops `.pdr`,
`.mdebug.abi32`, `.comment`. Its own `__start` and a `rawsys` stub issue the Linux system calls (o32 numbers
`4000 + n`: open, read, write, close, unlink, rename, mkdir, rmdir, fsync, statfs, getdents64, statx, exit_group),
so it needs no `ld-linux-mipsn8.so.1`, no `libc.so.6` and no headers. `e_flags` are `0x70001401` (stock
binaries: `0x70001405`, which adds only CPIC): mips32r2, o32, NaN 2008 (as stock; the kernel checks the
NaN mode against the CPU), soft-float ABI, no FP64. The same source compiles for the host with `-DWEBAPI_HOST`
(`-DWEBAPI_ROOT="<dir>"` moves the root off `/mnt/mmc`): libc replaces the raw calls behind the same `os_*` layer.
Errors are mapped to portable codes; MIPS errno numbers differ (`ENOTEMPTY` 93, `ENAMETOOLONG` 78).

Types and layouts assumed on the device: `struct statx` (arch independent, 256 bytes; kernel 5.10),
`linux_dirent64`, and o32 `struct statfs` (eight 32-bit words: type, bsize, frsize, blocks, bfree, files, ffree,
bavail). `df` rejects an implausible statfs answer (block size outside 512..16 MiB, free above total) with a 500.
Files open with `O_LARGEFILE` (a 32-bit task otherwise gets `EOVERFLOW` above 2 GiB).

## API contract

`/cgi-bin/api.cgi?op=<op>&...`. Parameters come from the query string and, for POSTs other than `upload`, from
a `application/x-www-form-urlencoded`-formatted body (query first; up to 256 KiB, 4096 parameters; a parameter without `=` has an empty value), so a
selection of any size travels in the body. Paths are card paths: `/` is `/mnt/mmc`, `/Music/Album`; repeated
`path` parameters name several items. Every op takes an optional `hidden=1` (query or form body; see Path rules). Read ops accept GET or POST; `mkdir`, `rename`, `move`, `delete`, `upload`
accept POST only (405 otherwise, `Allow` header).

**Mutating requests must send `Content-Type: application/octet-stream`** (403 otherwise). A cross-site page
cannot send that type without a CORS preflight, thttpd answers `OPTIONS` with 501, and a plain `<form>` posts
only form types, so another site cannot trigger a delete from the user's browser (the server has no login).
The form-encoded body of `move`/`delete` is sent with this type too.

Errors: `Status: <code> <text>` and `{"error":"<message>"}` (`application/json; charset=utf-8`):
400 bad request/name/path/length, 403 hidden name (without `hidden=1`), `.m1plus` read-only, symbolic link, root, wrong content type, 404 missing,
405 method, 409 exists/offset mismatch, 500 card or write failure, 507 card full.

| op | parameters | answer |
|---|---|---|
| `list` | `path` (folder, default `/`) | `{"path":"/Music","entries":[{"name","dir":bool,"size","mtime","items"?}]}`; every file and folder, unsorted; `size` 0 for folders; `mtime` seconds; `items` = entries in a folder, hidden names skipped unless `hidden=1`, capped at 9999, for the first 3000 folders of a listing; symlinks and special files are skipped |
| `df` | none | `{"total":bytes,"free":bytes}` (`free` = available to the user) |
| `download` | `path` (file) | the file: `Content-Length`, `Content-Type: application/octet-stream`, `Content-Disposition: attachment; filename="<ASCII fallback>"; filename*=UTF-8''<percent-encoded>`; no ranges. A folder is 400 |
| `tar` | one or more `path` (files or folders, not `/`), optional `name` | a GNU tar stream (`application/x-tar`, no `Content-Length`): members named from each item's own name (`Album/01.flac`), folders recursed, hidden names (unless `hidden=1`) and non-regular files left out, uid/gid 0, mode 644/755, mtime kept, names over 100 bytes in `././@LongLink` records, sizes from 8 GiB in base-256. Archive name `name`, else the item's name, else `M1 Plus`, plus `.tar`. A file that shrinks while read is zero-filled to its announced size. A dry run (stat/readdir/open only) precedes the first header: a selection with anything below 40 folder levels under an item, a path over 4096 bytes or an unreadable entry is a 400/500 JSON error, never a truncated archive; a read error once streaming has begun ends the response without the end-of-archive blocks |
| `mkdir` | `path` (parent), `name` | `{"name":"<name>"}`; 409 if it exists |
| `rename` | `path` (item), `name` (new name, same folder) | `{"name":...}`; 409 if the target exists (a case-only change is allowed: the card ignores case); the same name is a no-op |
| `move` | `path` (items, repeatable), `to` (folder), `conflict=fail` (default) or `keep` | `{"moved":[{"from","to"}]}` (final names; `keep` picks `name 2.ext`); `fail` answers 409 for any clash before anything moves; items already in `to` are skipped; a folder into itself or below is 400 |
| `delete` | `path` (items, repeatable) | `{"deleted":N}`; recursive, never follows symlinks, every path checked before the first deletion |
| `upload` | `path` (folder), `name`, `conflict=fail` (default) `\|replace\|keep`, optional `offset`, `last` | the raw file as the body (not multipart); `{"name":"<final name>","size":N}` |

**Upload**: `Content-Length` is required. The body streams in 64 KiB reads into `<folder>/.<name>.part`
(created or truncated, a stale one is replaced), is `fsync`ed, then renamed. `fail`: 409 if the name exists
(checked before the body is read; a refusal first swallows up to 4 MiB of the body so a small file's client
still sees the answer); `replace`: rename over a file (409 over a folder); `keep`: first free `name 2.ext`,
`name 3.ext`, ... (split at the last dot). Free space below `Content-Length` is 507 up front. A short body,
client abort or write error deletes the `.part` (a replaced file is untouched until the rename). The page
creates parent folders first with `mkdir`; folder trees are plain sequences of `mkdir` and `upload`.
Chunked form (needed above 2 GiB - 1, thttpd's limit below): `offset=0` starts, each later request sends
`offset=<bytes stored so far>` (409 if the `.part` size differs) and the last adds `last=1`; non-final answers are
`{"size":N}`, the final one the name. Conflict policy is applied at the first chunk (`fail`) and again at the end.

### Path rules

Every path is walked component by component below `/mnt/mmc`: `.` or `..` is 400, any component starting with
`.` is 403 (macOS `._` files, `/.m1plus`, upload `.part` files) unless the request has `hidden=1`, which makes list, item counts, tar, download, delete, move and rename (as the source) accept and include dot names; a symbolic link anywhere is 403 (stricter than
`realpath` and equivalent on the card's FAT/exFAT, which has none), `%00` is 400. The card root is refused for
`delete`, `rename`, `move` and `tar`. Names the API creates: one component, 1..240 bytes, no control characters,
`/` or leading dot (400, also with `hidden=1`: mkdir, upload and rename targets never start with a dot). `/.m1plus` (any case, the player's data folder) and everything below it is read-only even with `hidden=1`: `mkdir`, `upload`, `rename`, `move` (source or destination) and `delete` answer 403 ".m1plus is read-only"; list, download and tar work. `mkdir`, `rename` and `upload` also refuse, with 400 and a message, what exFAT rejects
or strips: `" * : < > ? \ |` and a trailing dot or space; the check runs before any upload body is read. Nothing calls a shell: `system`, `popen`, `exec` and libc do not exist in the binary.
`rename(2)` replaces files silently, so `rename` and `move` look first (check-then-rename; one user, no lock).
exFAT keeps the old case when a rename only changes case (`Small.bin` to `small.bin` answered 200 and changed
nothing), so `rename` of a case-only change goes through a hidden temporary name (`.rename0.tmp`, the next digit
if taken) in the same folder and renames it back to the old name if the second step fails. `move` keeps the
file's name, so it has no case-only case.

## thttpd findings (static: strings and disassembly of `usr/bin/thttpd`, version 2.29 23May2018; never executed)

- Methods: `GET`, `HEAD`, `POST` (the string table has these three and "Not Implemented"); anything else, `PUT`
  and `OPTIONS` included, is 501. Hence POST uploads.
- Request line plus headers must fit 5000 bytes (the read buffer grows by 1000 up to that, `0x402ae8`): keep the
  query short and put item lists in the POST body. `Accept` and `Accept-Encoding` values are capped at 5000 each.
- POST bodies: thttpd parses `Content-Length` with `strtol` (`0x4083dc`, a 32-bit value at connection offset
  `0x13c`), so a request body is at most 2^31 - 1 bytes; a larger length clamps. `CONTENT_LENGTH` is passed
  from that value. thttpd forks a copy process (`cgi_interpose_input`, `0x40a5e4`) that reads the socket in
  1 KiB pieces and writes them to the CGI's stdin pipe until the length is reached: bodies are streamed, never
  buffered, but throughput is bounded by 1 KiB read/write pairs (the mockup assumes ~6 MB/s; unmeasured).
  Larger files use the chunked upload.
- CGI output: a second process (`0x40a71c`) reads the CGI's stdout in 1 KiB pieces, parses the headers and
  forwards. `Status: NNN` sets the code; the reason text is thttpd's own table (409, 507 and others read
  "Something"). `Content-Length` and `Content-Disposition` pass through; without `Content-Length` the connection
  close ends the body, so a truncated tar is detected by its missing end blocks, not by HTTP.
- Time limit: none. The binary imports no `kill`, and the `killing indefinitely running CGI` strings are absent,
  so `CGI_TIMELIMIT` is not compiled in; `alarm` belongs to the main loop's watchdog. The idle read/send timeouts
  (`connection timed out reading/sending`) apply to connections thttpd itself serves, not to the forked
  copy/CGI processes. Multi-GB uploads and tar downloads are not cut off by thttpd (device behaviour unverified).
- A CGI's working directory is its own folder; it runs as root (`user=root`).

## Validation

`test/webapi.py` (module `webapi` in `tools/check.py`; `make test TEST=webapi`):

- The host build (AddressSanitizer + UBSan, root in a temporary directory) runs every op as CGI: path rules,
  hidden names, symlinks (list, download, mkdir, upload, delete leave outside files alone), JSON escaping,
  UTF-8 names, tar read back with `tarfile` (long names, empty files and folders, 512-byte boundaries, 3 MB),
  conflict names, chunked and interrupted uploads, content-type and method checks, 300-item bodies; `hidden=1` (list, counts, download, tar, delete of `._` and `.part` files, rename source, dot targets refused, `.m1plus` readable and never writable).
- The real MIPS `api.cgi` runs in Unicorn with its system calls answered from a temporary directory; 19 scripted
  requests (list, df, download, tar, mkdir, rename, upload with all conflict modes and chunks, move, delete) must
  answer like the host build, and leave the same files.
- Names: every exFAT-illegal character, control characters, trailing dot/space are 400 for mkdir, rename and
  upload (no `.part` left); a case-only rename runs in Unicorn and its `rename(2)` calls are checked
  (`Small.bin` to a temporary name to `small.bin`); the host file system may not reproduce exFAT's case behaviour.
- Page: self-contained (no external URL), every string key in every language with matching placeholders, no CJK
  or Cyrillic in the English table, shared words equal `pod_i18n`, every `t("key")` exists and is used, only
  known ops are called. No browser is run (none is a repo dependency).
- Tree: the page is the built asset; the executable is in the rootfs, equals a fresh build of `patch/webapi.c`, is a static MIPS32 LE ELF
  (no `PT_INTERP`, no `PT_DYNAMIC`, o32, NaN 2008), the stock files, links and directories are gone, `thttpd`,
  `thttpd.conf` and `favicon.ico` are unchanged.

Device results (V2.1zNUUVAAAC, real exFAT card): the CGI starts; `df`, `list`, upload (about 4.9 MB/s), 409,
keep, download (about 5.9 MB/s, byte-identical), rename, tar (about 6.2 MB/s) and delete work; a missing
Content-Type is 403 and `/../etc` is 400. Found there and fixed since: a case-only rename was a silent no-op, and a
name with `"` failed only after part of the body was read.

Seen on the device (2026-11-06): the page loads and lists the card in Safari on an iPad mini, dark theme. Not
verified: other browsers and the operations below (no browser or headless test runs the page), the two-step case-only rename and the early 400 on illegal names, thttpd's
behaviour above 2 GiB and the chunked upload, drag-and-drop and folder upload in each browser, the tar download
of a large selection through the form POST, `rename` over an existing file, and the base-256 tar size field
(needs an 8 GiB file).
