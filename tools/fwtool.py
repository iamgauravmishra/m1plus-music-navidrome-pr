#!/usr/bin/env python3
"""Shanling (Ingenic X2000 / Buildroot) firmware pack tool for update.bin / update.tar.

  fwtool.py info    UPDATE            show tar members, .info, squashfs superblock
  fwtool.py unpack  UPDATE  WORKDIR   extract tar, verify md5, unsquashfs rootfs, save metadata
  fwtool.py repack  WORKDIR OUT  --version TAG [--tailends] [--allow-removed PATH ...]
                                      mksquashfs WORKDIR/rootfs with stock params, regenerate .info,
                                      rebuild tar with stock member metadata
  fwtool.py verify  UPDATE            md5-check an update file
  fwtool.py diff    A B               list squashfs entries that differ in metadata or content between two updates

Requires squashfs-tools >= 4.5 (unsquashfs -pf) on PATH.
"""
import argparse, hashlib, io, json, os, re, shutil, struct, subprocess, sys, tarfile, tempfile

INFO_NAME = 'firmware_v20.info'
SQ_COMP = {1: 'gzip', 2: 'lzma', 3: 'lzo', 4: 'xz', 5: 'lz4', 6: 'zstd'}

def md5(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''): h.update(chunk)
    return h.hexdigest()

def sq_superblock(path):
    with open(path, 'rb') as f: s = f.read(96)
    f = struct.unpack('<4sIIIIHHHHHHQQQQQQQQ', s)
    assert f[0] == b'hsqs', 'not a squashfs'
    return {'inodes': f[1], 'mkfs_time': f[2], 'block_size': f[3], 'fragments': f[4],
            'compression': SQ_COMP.get(f[5], f[5]), 'flags': f[7], 'ids': f[8],
            'version': f'{f[9]}.{f[10]}', 'bytes_used': f[13]}

def parse_info(text):
    lines = text.rstrip('\n').split('\n')
    sums = {}
    for l in lines[2:]:
        m = re.match(r'^([0-9a-f]{32})  (.+)$', l)
        if m: sums[m.group(2)] = m.group(1)
    return {'model': lines[0], 'version': lines[1], 'md5': sums}

def make_info(model, version, sums):
    return f'{model}\n{version}\n' + ''.join(f'{h}  {n}\n' for n, h in sums)

def run(cmd, **kw):
    print('+', ' '.join(cmd), file=sys.stderr)
    return subprocess.run(cmd, check=True, **kw)

def cmd_info(a):
    with tarfile.open(a.update) as t:
        for m in t.getmembers():
            print(f'{m.name:40s} type={m.type.decode()} mode={m.mode:o} {m.uname}({m.uid})/{m.gname}({m.gid}) size={m.size} mtime={m.mtime}')
        info = t.extractfile(INFO_NAME).read().decode()
    print('--- ' + INFO_NAME + ' ---'); print(info, end='')
    with tempfile.TemporaryDirectory() as td:
        with tarfile.open(a.update) as t:
            for n in [m for m in t.getnames() if m.endswith('.squashfs')]:
                t.extract(n, td, filter='data')
                print('--- squashfs', n, '---'); print(json.dumps(sq_superblock(os.path.join(td, n)), indent=1))

MODEL = 'Shanling M1 Plus'
PAYLOAD = ('recovery-update/xImage', 'recovery-update/rootfs.squashfs')   # the only files an update carries
MEMBERS = {INFO_NAME, 'recovery-update', *PAYLOAD}

def verify_package(path):
    """Strict check of an update file without extracting it: exactly the expected members (regular files,
    the one directory, no duplicates or other paths), a well-formed manifest (model, version, exactly one
    md5 line per payload file) and matching md5s. Returns (problems, lines to print)."""
    bad, out = [], []
    try: t = tarfile.open(path)
    except (tarfile.TarError, OSError) as e: return [f'not a readable tar: {e}'], out
    with t:
        names = t.getnames()
        for n in sorted({n for n in names if names.count(n) > 1}): bad.append(f'duplicate member {n}')
        for n in sorted(set(names) - MEMBERS): bad.append(f'unexpected member {n}')
        for n in sorted(MEMBERS - set(names)): bad.append(f'missing member {n}')
        for m in t.getmembers():
            if m.name in MEMBERS and m.type != (tarfile.DIRTYPE if m.name == 'recovery-update' else tarfile.REGTYPE):
                bad.append(f'{m.name}: wrong member type {m.type!r}')
        try: lines = t.extractfile(INFO_NAME).read().decode().rstrip('\n').split('\n')
        except (KeyError, AttributeError, UnicodeDecodeError): return bad + [f'{INFO_NAME} unreadable'], out
        sums = {}
        if len(lines) < 2 or lines[0] != MODEL: bad.append(f'model {lines[0]!r} is not {MODEL!r}')
        if len(lines) < 2 or not lines[1].strip(): bad.append('empty version line')
        for l in lines[2:]:
            m = re.match(r'^([0-9a-f]{32})  (.+)$', l)
            if not m: bad.append(f'malformed manifest line {l!r}')
            elif m.group(2) in sums: bad.append(f'duplicate manifest entry {m.group(2)}')
            else: sums[m.group(2)] = m.group(1)
        if sorted(sums) != sorted(PAYLOAD): bad.append(f'manifest lists {sorted(sums)}, expected {sorted(PAYLOAD)}')
        for n in PAYLOAD:
            f = t.extractfile(n) if n in names and n in sums else None
            if f is None: continue
            h = hashlib.md5()
            for c in iter(lambda: f.read(1 << 20), b''): h.update(c)
            good = h.hexdigest() == sums[n]
            out.append(f'{n}: {"OK" if good else "MISMATCH"} ({h.hexdigest()})')
            if not good: bad.append(f'{n}: md5 mismatch')
        out.append(f'model={lines[0]!r} version={lines[1] if len(lines) > 1 else None!r}')
    return bad, out

def cmd_verify(a):
    bad, out = verify_package(a.update)
    for l in out: print(l)
    for b in bad: print('PROBLEM:', b)
    return 1 if bad else 0

def cmd_unpack(a):
    os.makedirs(a.workdir, exist_ok=True)
    members = []
    with tarfile.open(a.update) as t:
        for m in t.getmembers():
            members.append({'name': m.name, 'type': m.type.decode(), 'mode': m.mode, 'uid': m.uid, 'gid': m.gid,
                            'uname': m.uname, 'gname': m.gname, 'mtime': m.mtime, 'size': m.size})
        t.extractall(a.workdir, filter='data')
    info = parse_info(open(os.path.join(a.workdir, INFO_NAME)).read())
    for n, h in info['md5'].items():
        got = md5(os.path.join(a.workdir, n))
        if got != h: sys.exit(f'md5 mismatch for {n}: {got} != {h}')
        print(f'md5 OK  {n}')
    sq = [n for n in info['md5'] if n.endswith('.squashfs')][0]
    sqpath = os.path.join(a.workdir, sq)
    sb = sq_superblock(sqpath)
    rootfs = os.path.join(a.workdir, 'rootfs')
    if os.path.exists(rootfs): shutil.rmtree(rootfs)
    run(['unsquashfs', '-q', '-no-xattrs', '-d', rootfs, sqpath], stdout=subprocess.DEVNULL)
    run(['unsquashfs', '-no-xattrs', '-pf', os.path.join(a.workdir, 'stock.pseudo'), sqpath], stdout=subprocess.DEVNULL)
    run(['unsquashfs', '-no-xattrs', '-lln', '-d', '', sqpath], stdout=open(os.path.join(a.workdir, 'stock.lln'), 'w'))
    meta = {'source': os.path.abspath(a.update), 'members': members, 'info': info, 'squashfs': sq,
            'squashfs_size': os.path.getsize(sqpath), 'superblock': sb}
    json.dump(meta, open(os.path.join(a.workdir, 'meta.json'), 'w'), indent=1)
    print(f'unpacked to {a.workdir}: rootfs/ ({sb["inodes"]} inodes, {sb["compression"]} {sb["block_size"]}B blocks, {meta["squashfs_size"]} bytes)')

def stock_meta(pseudo_path, rootfs):
    """Parse inode metadata (type, mtime, mode, uid, gid) out of an `unsquashfs -pf` dump.
    The dump interleaves binary file data, so match definition lines by regex and keep only
    paths that exist in the extracted tree."""
    d = open(pseudo_path, 'rb').read()
    pat = re.compile(rb'(?m)^("(?:[^"\n]*)"|[^\s"][^\s]*) ([DRSBCIL]) ([^\n]*)$')
    ents = {}
    for m in pat.finditer(d):
        path = m.group(1).decode('utf-8', 'surrogateescape').strip('"'); t = m.group(2).decode()
        f = m.group(3).decode('utf-8', 'surrogateescape').split(' ')
        full = rootfs if path == '/' else os.path.join(rootfs, path)
        if not os.path.lexists(full): continue
        if t in 'DRSBCI':
            try: ents[path] = (t, int(f[0]), f[1], int(f[2]), int(f[3]))
            except (ValueError, IndexError): pass
    return ents

def root_attrs(pseudo_path, rootfs):
    e = stock_meta(pseudo_path, rootfs).get('/')
    return {'time': str(e[1]), 'mode': e[2], 'uid': str(e[3]), 'gid': str(e[4])} if e else None

def modify_pseudo(ents):
    """'M' lines re-applying stock mtime/mode/uid/gid to every stock inode still present
    (fixes what macOS cannot preserve on extraction: symlink modes, setuid bits, ownership)."""
    out = []
    for path, (t, time, mode, uid, gid) in sorted(ents.items()):
        if path == '/': continue
        q = f'"{path}"' if ' ' in path else path
        out.append(f'{q} M {time} {mode} {uid} {gid}')
    return out

def cmd_repack(a):
    meta = json.load(open(os.path.join(a.workdir, 'meta.json')))
    sb = meta['superblock']; sq = meta['squashfs']
    rootfs = os.path.join(a.workdir, 'rootfs')
    pseudo = os.path.join(a.workdir, 'stock.pseudo')
    build = a.build_dir or os.path.join(a.workdir, 'build'); os.makedirs(build, exist_ok=True)
    out_sq = os.path.join(build, os.path.basename(sq))
    if os.path.exists(out_sq): os.remove(out_sq)
    if a.reuse_squashfs:   # ship the untouched stock image (e.g. a restore package with a new version tag)
        shutil.copyfile(os.path.join(a.workdir, sq), out_sq); print('reusing stock squashfs unchanged')
    ents = stock_meta(pseudo, rootfs)
    pf = os.path.join(build, 'meta.pseudo')
    with open(pf, 'w') as f: f.write('\n'.join(modify_pseudo(ents)) + '\n')
    ra = root_attrs(pseudo, rootfs) or {'time': str(sb['mkfs_time']), 'mode': '755', 'uid': '0', 'gid': '0'}
    print(f'{len(ents)} stock inodes matched; applying stock metadata via {pf}')
    cmd = ['true'] if a.reuse_squashfs else ['mksquashfs', rootfs, out_sq, '-noappend', '-no-xattrs', '-all-root', '-pseudo-override', '-pf', pf,
           '-comp', sb['compression'], '-b', str(sb['block_size']), '-mkfs-time', str(sb['mkfs_time']),
           '-root-time', ra['time'], '-root-mode', ra['mode'], '-root-uid', ra['uid'], '-root-gid', ra['gid'],
           '-no-progress', '-quiet']   # every core: mksquashfs 4.4+ writes the same image at any thread count (the golden hash checks it)
    if sb['compression'] == 'lzo' and not a.reuse_squashfs: cmd += ['-Xcompression-level', '9']
    if a.tailends and not a.reuse_squashfs: cmd += ['-tailends']   # pack file tails into fragments too (data layout only)
    run(cmd)
    size, stock = os.path.getsize(out_sq), meta['squashfs_size']
    print(f'rootfs.squashfs: {size} bytes (stock {stock})')
    if size > stock: sys.exit(f'ERROR: rebuilt squashfs ({size}) exceeds stock ({stock})')
    # metadata check against stock listing (mode, owner, size, name); ignore files the user changed in size
    run(['unsquashfs', '-no-xattrs', '-lln', '-d', '', out_sq], stdout=open(os.path.join(build, 'new.lln'), 'w'))
    def listing(p):
        d = {}
        for l in open(p, encoding='utf-8', errors='surrogateescape'):
            f = l.rstrip('\n').split(None, 5)
            if len(f) == 6 and f[0][0] in 'dlcbps-': d[f[5]] = (f[0], f[1])   # name -> (mode, uid/gid)
        return d
    s_l, n_l = listing(os.path.join(a.workdir, 'stock.lln')), listing(os.path.join(build, 'new.lln'))
    # --allow-removed: exactly these stock entries may be absent (each must exist in stock and be gone)
    removed = {'/' + p.lstrip('/') for p in a.allow_removed}
    for k in sorted(removed):
        if k not in s_l or k in n_l: sys.exit(f'ERROR: --allow-removed {k}: not a stock entry, or still present')
        print(f'REMOVED {k} (allowed)')
    # --allow-added: exactly these entries may be new (absent in stock, present now); for mod assets
    added = {'/' + p.lstrip('/') for p in a.allow_added}
    for k in sorted(added):
        if k in s_l or k not in n_l: sys.exit(f'ERROR: --allow-added {k}: already a stock entry, or not present')
        print(f'ADDED {k} (allowed)')
    skip = removed | added
    bad = [(k, s_l.get(k), n_l.get(k)) for k in sorted(set(s_l) | set(n_l)) if s_l.get(k) != n_l.get(k) and k not in skip]
    for k, s, n in bad: print(f'META DIFF {k}: stock={s} new={n}')
    print(f'metadata: {len(bad)} entries differ from stock (mode/owner/presence)')
    if bad: sys.exit('ERROR: metadata differs from stock')
    # info + tar
    sums = []
    for n in meta['info']['md5']:
        p = out_sq if n == sq else os.path.join(a.workdir, n)
        sums.append((n, md5(p)))
    info = make_info(meta['info']['model'], a.version, sums).encode()
    with tarfile.open(a.out, 'w', format=tarfile.GNU_FORMAT) as t:
        for m in meta['members']:
            ti = tarfile.TarInfo(m['name']); ti.type = m['type'].encode(); ti.mode = m['mode']
            ti.uid, ti.gid, ti.uname, ti.gname, ti.mtime = m['uid'], m['gid'], m['uname'], m['gname'], m['mtime']
            if ti.type == tarfile.DIRTYPE: t.addfile(ti); continue
            if m['name'] == INFO_NAME: ti.size = len(info); t.addfile(ti, io.BytesIO(info)); continue
            p = out_sq if m['name'] == sq else os.path.join(a.workdir, m['name'])
            ti.size = os.path.getsize(p)
            with open(p, 'rb') as f: t.addfile(ti, f)
    print(f'wrote {a.out} ({os.path.getsize(a.out)} bytes), version {a.version!r}')
    print(info.decode(), end='')

def cmd_diff(a):
    with tempfile.TemporaryDirectory() as td:
        ls, roots = [], []
        for i, u in enumerate((a.a, a.b)):
            d = os.path.join(td, str(i)); os.makedirs(d)
            with tarfile.open(u) as t: t.extractall(d, filter='data')
            sq = os.path.join(d, 'recovery-update', [n for n in os.listdir(os.path.join(d, 'recovery-update')) if n.endswith('.squashfs')][0])
            r = run(['unsquashfs', '-no-xattrs', '-lls', '-d', '', sq], capture_output=True, text=True)
            name = lambda l: (l.split(None, 5) + ['/'])[5].split(' -> ')[0]   # root lists with an empty name
            ls.append({name(l): l for l in r.stdout.splitlines() if l[:1] in 'dlcbps-'})
            roots.append(os.path.join(d, 'root'))
            run(['unsquashfs', '-q', '-no-xattrs', '-d', roots[-1], sq], stdout=subprocess.DEVNULL)
        # a directory's listed size is its squashfs directory-table length, which follows the inode
        # layout (e.g. -tailends, removed files); report those apart from real entry changes
        dirsize = lambda l: l and l[0] == 'd' and l.split(None, 3)[3]
        layout = 0
        for k in sorted(set(ls[0]) | set(ls[1])):
            x, y = ls[0].get(k), ls[1].get(k)
            if x == y:   # same metadata: still compare regular file contents
                if x[0] == '-' and md5(os.path.join(roots[0], k[1:])) != md5(os.path.join(roots[1], k[1:])): print(f'~ {y}  (content)')
                continue
            if dirsize(x) and dirsize(x) == dirsize(y): layout += 1; continue
            print(f'- {x}\n+ {y}')
        if layout: print(f'({layout} directories differ only in listed size: directory-table layout, same name/mode/owner/time)')

if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('info'); p.add_argument('update'); p.set_defaults(f=cmd_info)
    p = sp.add_parser('verify'); p.add_argument('update'); p.set_defaults(f=cmd_verify)
    p = sp.add_parser('unpack'); p.add_argument('update'); p.add_argument('workdir'); p.set_defaults(f=cmd_unpack)
    p = sp.add_parser('repack'); p.add_argument('workdir'); p.add_argument('out'); p.add_argument('--version', required=True)
    p.add_argument('--tailends', action='store_true', help='mksquashfs -tailends: smaller image, same metadata')
    p.add_argument('--allow-removed', action='append', default=[], metavar='PATH', help='stock file deliberately removed (repeatable)')
    p.add_argument('--allow-added', action='append', default=[], metavar='PATH', help='file deliberately added that is not in stock (repeatable)')
    p.add_argument('--build-dir', help='scratch dir (default WORKDIR/build)')
    p.add_argument('--reuse-squashfs', action='store_true', help='do not rebuild; reuse the stock squashfs bytes'); p.set_defaults(f=cmd_repack)
    p = sp.add_parser('diff'); p.add_argument('a'); p.add_argument('b'); p.set_defaults(f=cmd_diff)
    a = ap.parse_args(); sys.exit(a.f(a) or 0)
