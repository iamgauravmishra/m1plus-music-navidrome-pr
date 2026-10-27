"""Where the repo's gitignored inputs live, in the main checkout or in a git worktree.

firmware/ (the official zip), venv/, fonts/ and work/stock are not in git, so a fresh worktree has
none of them. Each is looked up in this checkout first, then in the main checkout (the parent of
`git rev-parse --git-common-dir`). work/ (apart from reading the shared stock tree) and out/ stay
per checkout; the two can be redirected with M1_WORK / M1_OUT (tools/check.py gives every build its
own). In the main checkout everything resolves to the local paths, as before.

  paths.ROOT        this checkout        paths.MAIN     the main checkout (== ROOT there)
  paths.ZIP         firmware zip         paths.VENV_PY  python with the requirements installed
  paths.SHS_ZIP     Source Han Sans zip  paths.WORK / paths.OUT   per-checkout output dirs
  paths.find_stock(zip_path)   an unpacked stock tree (read-only!) matching the zip, or None
CLI: python3 -I tools/paths.py   prints the resolution.
"""
import os, subprocess, sys, zipfile, zlib, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _main_checkout():
    try:
        r = subprocess.run(['git', '-C', ROOT, 'rev-parse', '--path-format=absolute', '--git-common-dir'],
                           capture_output=True, text=True, timeout=10)
        common = r.stdout.strip()
        if r.returncode == 0 and common and os.path.basename(common) == '.git':
            return os.path.dirname(common)
    except (OSError, subprocess.SubprocessError): pass
    return ROOT

MAIN = _main_checkout()

def resolve(rel):
    """rel under this checkout if it exists there, else under the main checkout if it exists
    there, else the local path (so error messages name the local file)."""
    for base in (ROOT, MAIN):
        p = os.path.join(base, rel)
        if os.path.exists(p): return p
    return os.path.join(ROOT, rel)

ZIP = resolve('firmware/M1 Plus Firmware V2.1.zip')
SHS_ZIP = resolve('fonts/09_SourceHanSansSC.zip')
VENV_PY = next((p for base in (ROOT, MAIN) for d in ('venv', '.venv')
                for p in (os.path.join(base, d, 'bin', 'python'),) if os.path.exists(p)), sys.executable)
WORK = os.path.abspath(os.environ.get('M1_WORK') or os.path.join(ROOT, 'work'))
OUT = os.path.abspath(os.environ.get('M1_OUT') or os.path.join(ROOT, 'out'))

def _zip_member(zip_path):
    z = zipfile.ZipFile(zip_path)
    return z.getinfo([n for n in z.namelist() if n.endswith('update.bin')][0])

def _crc(path):
    c = 0
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): c = zlib.crc32(b, c)
    return c

def stock_matches(stock, zip_path):
    """True if the unpacked tree `stock` came from this zip: its meta.json names the update.bin it
    was unpacked from, and that file's CRC-32 equals the zip member's."""
    try:
        src = json.load(open(os.path.join(stock, 'meta.json')))['source']
        return os.path.exists(os.path.join(stock, 'rootfs')) and os.path.exists(src) \
            and _crc(src) == _zip_member(zip_path).CRC
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, IndexError): return False

def find_stock(zip_path=ZIP):
    """The local work/stock if it is unpacked, else the main checkout's if it matches the zip.
    Callers must treat the result as read-only. None: unpack one locally."""
    local = os.path.join(WORK, 'stock')
    if os.path.exists(os.path.join(local, 'meta.json')): return local
    shared = os.path.join(MAIN, 'work', 'stock')
    if MAIN != ROOT and stock_matches(shared, zip_path): return shared
    return None

if __name__ == '__main__':
    # every path absolute, so it can be pasted into a command from any directory
    for k in ('ROOT', 'MAIN', 'ZIP', 'SHS_ZIP', 'VENV_PY', 'WORK', 'OUT'): print(f'{k:8} {os.path.abspath(globals()[k])}')
    stock = find_stock() if os.path.exists(ZIP) else None
    print(f'{"STOCK":8} {os.path.abspath(stock) if stock else None}')
    print(f'{"DEMO":8} {os.path.join(os.path.abspath(stock), "rootfs", "release", "bin", "demo") if stock else None}')
    print(f'{"TREE":8} {os.path.join(WORK, "mod-release")}   (the built release tree, after build.py)')
