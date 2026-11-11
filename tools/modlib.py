"""Helpers shared by the asset steps (tools/mod_*.py)."""
import hashlib, io, os, shutil, stat, struct, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui

def sha256(b):
    """Hex SHA-256 of bytes."""
    return hashlib.sha256(b).hexdigest()

def file_sha256(p):
    """Hex SHA-256 of a file's bytes."""
    with open(p, 'rb') as f: return sha256(f.read())

def png_bytes(im):
    """A PIL image as PNG bytes (optimised, no metadata chunks, no timestamp)."""
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True); return b.getvalue()

def check_pins(buf, pins, fileoff):
    """Every (address, word, what) of `pins` must be the little-endian word at fileoff(buf, address); ValueError otherwise."""
    for a, old, what in pins:
        got = struct.unpack_from('<I', buf, fileoff(buf, a))[0]
        if got != old: raise ValueError(f'{a:#x} ({what}): {got:#010x} != pinned {old:#010x}')

def load_pins(path):
    """{name: sha256} from a pins file ('<sha256>  <name>' lines, '#' comments)."""
    pins = {}
    for line in open(path):
        if line.strip() and not line.startswith('#'):
            h, n = line.split(); pins[n] = h
    return pins

def stock_img_dir(img):
    """The unpacked stock tree's IMG directory (exits when no stock tree is unpacked)."""
    import paths
    stock = paths.find_stock(paths.ZIP)
    if not stock: sys.exit('no unpacked stock tree found (run tools/build.py once)')
    return os.path.join(stock, img)

def write_pins(path, header, d, names):
    """Write a pins file: the header line, then the SHA-256 of d/<name>.png for each name."""
    with open(path, 'w') as o:
        o.write(header)
        for n in names: o.write(f'{file_sha256(os.path.join(d, n + ".png"))}  {n}\n')

def write_keep_mode(p, data):
    """Overwrite p, preserving permissions and deterministic timestamps of added files."""
    original = os.stat(p)
    mode = stat.S_IMODE(original.st_mode)
    os.chmod(p, mode | 0o200)
    with open(p, 'wb') as f: f.write(data)
    os.chmod(p, mode)
    os.utime(p, ns=(original.st_atime_ns, original.st_mtime_ns))

def clone_workdir(src, out):
    """Fresh copy of an unpacked workdir in OUT (APFS clone when possible). OUT == SRC edits in place."""
    if os.path.abspath(src) == os.path.abspath(out): return
    if os.path.exists(out): shutil.rmtree(out)
    # APFS clone (fast, no extra space); fall back to a plain copy elsewhere
    r = subprocess.run(['cp', '-Rc', src, out], capture_output=True)
    if r.returncode: shutil.copytree(src, out, symlinks=True)
    shutil.rmtree(os.path.join(out, 'build'), ignore_errors=True)

def edit_ui(path, edit):
    """Parse a ui/*.bin, require a byte-exact untouched round trip, apply edit(root), write it back
    with the file's permission bits unchanged. Returns (old_bytes, new_bytes, root)."""
    old = open(path, 'rb').read()
    root = awtk_ui.parse(old)
    assert awtk_ui.serialize(root) == old, f'{path}: parse/serialize round trip is not byte-exact'
    edit(root)
    new = awtk_ui.serialize(root)
    write_keep_mode(path, new)
    return old, new, root
