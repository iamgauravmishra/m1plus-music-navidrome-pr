"""Build cache for tools/build.py (work/cache/build/, per checkout).

Every stage of the release tree is a deterministic function of (the tree before it, the code of the
stage, the repo's data inputs). A stage is keyed by the hash of exactly that:

  key = H(previous key, code closure of the stage's tool modules, args, assets/ tree, tool versions)

so a change to one step's code (or to assets/) re-runs that step and every later one, and nothing
before it. The first stage ("base": mod_battery + mod_font + mod_space, from the pinned zip) is stored
as a whole tree (copy-on-write clone where the file system has it); the steps are stored as deltas
(the files they added or changed, the ones they removed). pod.py (the payload) always runs; the hash
of what it wrote starts the chain for the steps after it. A hit applies the stored bytes, so the
result is byte-identical to a run (tools/check.py compares the package to the golden hash).
Disable with M1_NO_CACHE=1 or build.py --no-cache.
"""
import ast, functools, hashlib, importlib.metadata as md, json, os, shutil, subprocess, sys, tempfile

import paths, workflow

TOOLS = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(paths.ROOT, 'work', 'cache', 'build')
KEEP_BASES = 2
ENABLED = not os.environ.get('M1_NO_CACHE')

def H(*parts):
    h = hashlib.sha256()
    for p in parts:
        b = p if isinstance(p, bytes) else str(p).encode()
        h.update(len(b).to_bytes(8, 'little')); h.update(b)
    return h.hexdigest()

file_sha = workflow.sha

def dir_sha(root):
    """Content hash of a directory tree (relative paths and bytes)."""
    parts = []
    for d, dirs, files in os.walk(root):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(d, f)
            parts += [os.path.relpath(p, root), file_sha(p)]
    return H(*parts)

def closure(module):
    """tools/<module>.py and every tools/*.py it imports, transitively (static imports)."""
    seen, todo = {}, [module]
    while todo:
        m = todo.pop()
        if m in seen: continue
        p = os.path.join(TOOLS, m + '.py')
        if not os.path.exists(p): continue
        seen[m] = p
        for n in ast.walk(ast.parse(open(p).read())):
            if isinstance(n, ast.Import): todo += [a.name.split('.')[0] for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level: todo.append(n.module.split('.')[0])
    return seen

def code_sha(*modules):
    files = {}
    for m in modules: files.update(closure(m))
    return H(*[x for m in sorted(files) for x in (m, file_sha(files[m]))])

FORMAT = 4

@functools.cache
def versions():
    """What a cached step depends on besides its inputs: the Python packages and the native toolchain (clang, lld, objcopy: the steps that compile; workflow.environment)."""
    out = [f'format {FORMAT}', sys.version, json.dumps(workflow.environment(), sort_keys=True)]
    for d in ('pillow', 'fonttools', 'pyelftools', 'capstone', 'unicorn'):
        try: out.append(f'{d}={md.version(d)}')
        except md.PackageNotFoundError: out.append(f'{d}=none')
    return H(*out)

@functools.cache  # once per build: no stage writes into assets/, patch/ or tools/
def data_sha():
    """The repo's data inputs: assets/, patch/ and the non-Python files in tools/ (coarse on purpose)."""
    extra = [x for f in sorted(os.listdir(TOOLS)) if os.path.isfile(os.path.join(TOOLS, f)) and not f.endswith('.py')
             for x in (f, file_sha(os.path.join(TOOLS, f)))]
    return H(dir_sha(os.path.join(paths.ROOT, 'assets')), dir_sha(os.path.join(paths.ROOT, 'patch')), *extra)

def base_key(zip_sha, *modules):
    # Battery art and space recovery use only Python code and stock. The font stage
    # additionally reads assets/fonts. A payload edit must not rebuild the font.
    return H('base', zip_sha, code_sha(*modules), dir_sha(os.path.join(paths.ROOT, 'assets/fonts')), versions())

def step_key(prev, module, args):
    return H('step', prev, code_sha(module), json.dumps(args), data_sha(), versions())

# ---------------------------------------------------------------- trees and deltas
def snap(root):
    """rel path -> (kind, size/target, ctime_ns, mode, inode) of every file and symlink under root, and
    ('d', ...) for every real directory (so a step that removes one is seen)."""
    out = {}
    for d, dirs, files in os.walk(root):
        for x in dirs:
            if not os.path.islink(os.path.join(d, x)): out[os.path.relpath(os.path.join(d, x), root)] = ('d', 0, 0, 0, 0)
        for f in files + [x for x in dirs if os.path.islink(os.path.join(d, x))]:
            p = os.path.join(d, f); st = os.lstat(p); rel = os.path.relpath(p, root)
            # ctime, not mtime: the steps set mtimes on purpose (os.utime), but ctime moves on every write
            out[rel] = ('l', os.readlink(p), 0, 0, 0) if os.path.islink(p) else ('f', st.st_size, st.st_ctime_ns, st.st_mode, st.st_ino)
    return out

def clone(src, dst):
    cmd = ['cp', '-cRp', src, dst] if sys.platform == 'darwin' else ['cp', '-a', '--reflink=auto', src, dst]
    if subprocess.run(cmd, capture_output=True).returncode:
        shutil.rmtree(dst, ignore_errors=True); shutil.copytree(src, dst, symlinks=True)

def delta_since(before, root):
    after = snap(root)
    return [r for r in after if after[r][0] != 'd' and before.get(r) != after[r]], [r for r in before if r not in after], after

def delta_sha(root, changed, removed):
    return H(*[x for r in sorted(changed) for x in (r, file_sha(os.path.join(root, r)) if not os.path.islink(os.path.join(root, r)) else os.readlink(os.path.join(root, r)))],
             'removed', *sorted(removed))

def _write_atomic(entry, fill):
    os.makedirs(os.path.dirname(entry), exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='.tmp-', dir=os.path.dirname(entry))
    try:
        fill(tmp)
        if not os.path.exists(entry):
            try: os.rename(tmp, entry)
            except OSError:
                if not os.path.isdir(entry): raise
    finally: shutil.rmtree(tmp, ignore_errors=True)

def store_delta(key, root, changed, removed):
    def fill(tmp):
        os.makedirs(os.path.join(tmp, 'files'))
        links = {}
        for r in changed:
            p = os.path.join(root, r)
            if os.path.islink(p): links[r] = os.readlink(p); continue
            os.makedirs(os.path.dirname(os.path.join(tmp, 'files', r)), exist_ok=True)
            shutil.copy2(p, os.path.join(tmp, 'files', r))
        json.dump({'removed': removed, 'links': links}, open(os.path.join(tmp, 'meta.json'), 'w'))
    _write_atomic(os.path.join(CACHE, 'steps', key), fill)

def apply_delta(key, root):
    entry = os.path.join(CACHE, 'steps', key)
    meta = json.load(open(os.path.join(entry, 'meta.json')))
    for r in meta['removed']:      # files, links and directories (a removed directory's contents are listed too)
        p = os.path.join(root, r)
        if os.path.isdir(p) and not os.path.islink(p): shutil.rmtree(p, ignore_errors=True)
        else:
            try: os.remove(p)
            except FileNotFoundError: pass
    for r, t in meta['links'].items():
        p = os.path.join(root, r); os.makedirs(os.path.dirname(p), exist_ok=True)
        if os.path.lexists(p): os.remove(p)
        os.symlink(t, p)
    fdir = os.path.join(entry, 'files')
    for d, _, files in os.walk(fdir):
        for f in files:
            src = os.path.join(d, f); dst = os.path.join(root, os.path.relpath(src, fdir))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            if os.path.lexists(dst): os.remove(dst)
            shutil.copy2(src, dst)

def have_step(key): return ENABLED and os.path.exists(os.path.join(CACHE, 'steps', key, 'meta.json'))

def restore_base(key, mod):
    entry = os.path.join(CACHE, 'base', key, 'tree')
    if not (ENABLED and os.path.isdir(entry)): return False
    shutil.rmtree(mod, ignore_errors=True); clone(entry, mod); os.utime(os.path.dirname(entry))
    return True

def store_base(key, mod):
    if not ENABLED: return
    root = os.path.join(CACHE, 'base')
    _write_atomic(os.path.join(root, key), lambda tmp: clone(mod, os.path.join(tmp, 'tree')))
    olds = sorted((os.path.getmtime(os.path.join(root, d)), d) for d in os.listdir(root) if not d.startswith('.tmp-'))
    for _, d in olds[:-KEEP_BASES]: shutil.rmtree(os.path.join(root, d), ignore_errors=True)
