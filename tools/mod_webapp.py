#!/usr/bin/env python3
"""Wi-Fi Transfer's web root (docs/modules/wifi-transfer.md): the stock web app out, ours in.

Stock's thttpd serves /usr/share/web (jQuery + Bootstrap page, five cgic CGIs and their symlinks). This step
deletes all of it except favicon.ico, installs patch/webapi.c as /usr/share/web/cgi-bin/api.cgi (a static MIPS
executable over raw system calls: no libc, no interpreter) and replaces index.html with assets/webapp/index.html.
The player binary and thttpd's configuration are untouched.

Every stock file is pinned by SHA-256 and every link by target; a mismatch fails the build. The removed entries
(files, links and the css, js and fonts directories) are the build's --allow-removed list (removed_rels).

Usage: mod_webapp.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir, write_keep_mode, file_sha256 as sha256

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'patch', 'webapi.c')
INDEX_SRC = os.path.join(ROOT, 'assets', 'webapp', 'index.html')
WEB = 'usr/share/web'
CGI = WEB + '/cgi-bin/api.cgi'
INDEX = WEB + '/index.html'
MODE, MTIME = 0o755, 1750924035   # an executable like the stock CGIs; a stock mtime, so the build is deterministic

# Stock V2.1 files below WEB (relative to it) -> SHA-256. favicon.ico stays; index.html is replaced, not removed.
STOCK_FILES = {
    'cgi-bin/create.cgi': '49e1ab3de6a0d4688cf584e1579f34b9a4c83b4e9d9f12f4429d5c156f40e2e1',
    'cgi-bin/delete.cgi': 'd37b0fdfdb229943384aecb4e5c66850f2304311d4412b416ce03a9536d4ffec',
    'cgi-bin/download.cgi': '99d215ebe30afaa203838c10cfc23d9e04e6168af12b85c80a2ea5fd4d927088',
    'cgi-bin/list.cgi': '027e7c38c44fc6c36d7f6dfb873565109ceaab480a288c1f9923ba35efc56e31',
    'cgi-bin/upload.cgi': 'b598e569c9077c0459629d122f90864e57c82d9a04695828e4b9a2e9f835f058',
    'css/bootstrap-theme.css': '382a4120b748eaf656e422f2f27c8778d311fabb97a644db97011ec176c130bf',
    'css/bootstrap.css': 'e9336219e7189159b1d0680e0f183245f71d880ebf8c5e76f44cca7d50701777',
    'css/index.css': 'b69a50eb0c148ad9b34d619f28b52ce5fe77e1b2e7159d79c4909f4126edba99',
    'css/jquery.fileupload.css': '8e49019c2903d7a88be4d6748ad01511cd70bdebe4587eb3eff79d28d4522f65',
    'fonts/glyphicons-halflings-regular.eot': 'f495f34e4f177cf0115af995bbbfeb3fcabc88502876e76fc51a4ab439bc8431',
    'fonts/glyphicons-halflings-regular.svg': 'd168d50a88c730b4e6830dc0da2a2b51dae4658a77d9619943c27b8ecfc19d1a',
    'fonts/glyphicons-halflings-regular.ttf': 'bd18efd3efd70fec8ad09611a20cdbf99440b2c1d40085c29be036f891d65358',
    'fonts/glyphicons-halflings-regular.woff': 'fc969dc1c6ff531abcf368089dcbaf5775133b0626ff56b52301a059fc0f9e1e',
    'js/bootstrap.min.js': '898d05a17f2cfc5120ddcdba47a885c378c0b466f30f0700e502757e24b403a1',
    'js/html5shiv.min.js': '8c7a9c0470563367ab00307b4fb9bb3052d0a27f0b94e63b9dc0bb8c369449cb',
    'js/index.js': '2ead273bfb64734bfc85d774ee9cbd8a71099db9ff04fdaeb3db41117babd255',
    'js/jquery-1.7.2.min.js': '47b68dce8cb6805ad5b3ea4d27af92a241f4e29a5c12a274c852e4346a0500b4',
    'js/jquery.fileupload.js': '6af5c569f113d2eaa027c3c39a7f32bfdb23de6de4994ef6af61c17607505bda',
    'js/jquery.iframe-transport.js': 'e127082f8c4e76952f5a8e1e9a0c2731372ca3f7d800fa9a5ec1bed0a516c2a9',
    'js/jquery.jeditable.js': '882892a2c0ecb30e180f4305c2e04d7f8f24968681473ee8f9e48aad45c36587',
    'js/jquery.ui.widget.js': '30e522d238f9e84ad8289ab5b43ee396ffbd1e96c8eab77157fbc6fa30edaacd',
    'js/respond.min.js': '83a8807ef669fa70d0d9375347f5552897f76c6ae8e2e6f97ef592595462d8d1',
    'js/tmpl.min.js': '8e882ad3513da790ead8b75161f03780a134a0dde5cbbae7ded807915bc23aa9',
}
STOCK_INDEX = 'cfa27f019a8c5f433c5d90e63494df6189666ebb151e3368aa8cc16206fdcab9'
STOCK_LINKS = {n: f'cgi-bin/{n}.cgi' for n in ('create', 'delete', 'download', 'list', 'upload')}
STOCK_DIRS = ('css', 'fonts', 'js')

# The executable: 32-bit little-endian MIPS32r2 o32, soft float, NaN 2008 like the stock binaries, no libc.
LLVM = os.environ.get('LLVM_BIN', '/opt/homebrew/opt/llvm/bin')
LLD = os.environ.get('LLD_BIN', '/opt/homebrew/opt/lld/bin')
CFLAGS = ['--target=mipsel-linux-gnu', '-march=mips32r2', '-mabi=32', '-msoft-float', '-mnan=2008', '-mno-abicalls',
          '-fno-pic', '-G0', '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-fno-unwind-tables',
          '-fno-asynchronous-unwind-tables', '-Os', '-Wall', '-Wextra', '-Werror', '-ffunction-sections', '-fdata-sections']
LDFLAGS = ['-m', 'elf32ltsmip', '-static', '-nostdlib', '-e', '__start', '--gc-sections', '--build-id=none', '-z', 'norelro', '-s']


def removed_rels(stock_rootfs=None):
    """The stock entries this step removes (files, links, directories), relative to the rootfs; a link is listed
    as unsquashfs prints it, with ' -> target' (fwtool --allow-removed compares those listing names)."""
    return sorted([f'{WEB}/{n}' for n in (*STOCK_FILES, *STOCK_DIRS)] + [f'{WEB}/{n} -> {t}' for n, t in STOCK_LINKS.items()])


def added_rels(stock_rootfs=None):
    return [CGI]


def build_cgi():
    """patch/webapi.c compiled and linked as a static MIPS executable; returns its bytes."""
    with tempfile.TemporaryDirectory() as td:
        obj, exe = os.path.join(td, 'api.o'), os.path.join(td, 'api.cgi')
        subprocess.run([os.path.join(LLVM, 'clang'), *CFLAGS, '-c', SRC, '-o', obj], check=True)
        subprocess.run([os.path.join(LLD, 'ld.lld'), *LDFLAGS, '-o', exe, obj], check=True)
        subprocess.run([os.path.join(LLVM, 'llvm-objcopy'), '-R', '.pdr', '-R', '.mdebug.abi32', '-R', '.comment', exe], check=True)
        return open(exe, 'rb').read()




def apply(out):
    web = os.path.join(out, 'rootfs', WEB)
    freed = 0
    for rel, h in STOCK_FILES.items():
        p = os.path.join(web, rel)
        assert os.path.isfile(p) and not os.path.islink(p) and sha256(p) == h, f'{WEB}/{rel}: not the stock file'
        freed += os.path.getsize(p)
        os.remove(p)
    for name, target in STOCK_LINKS.items():
        p = os.path.join(web, name)
        assert os.path.islink(p) and os.readlink(p) == target, f'{WEB}/{name}: not the stock link'
        os.remove(p)
    for d in STOCK_DIRS:
        os.rmdir(os.path.join(web, d))   # empty by now, or the stock tree has files this step does not know
    index = os.path.join(web, 'index.html')
    assert sha256(index) == STOCK_INDEX, f'{INDEX}: not the stock file'
    page = open(INDEX_SRC, 'rb').read()
    write_keep_mode(index, page)
    cgi = build_cgi()
    path = os.path.join(out, 'rootfs', CGI)
    assert not os.path.exists(path), path
    with open(path, 'wb') as f: f.write(cgi)
    os.chmod(path, MODE); os.utime(path, (MTIME, MTIME))
    print(f'webapp: removed {len(STOCK_FILES) + len(STOCK_LINKS)} stock entries ({freed} bytes), '
          f'/{CGI} {len(cgi)} bytes, /{INDEX} {len(page)} bytes')


if __name__ == '__main__':
    clone_workdir(sys.argv[1], sys.argv[2]); apply(sys.argv[2])
