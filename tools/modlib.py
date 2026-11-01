"""Helpers shared by the asset steps (tools/mod_*.py)."""
import os, shutil, stat, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import awtk_ui

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
