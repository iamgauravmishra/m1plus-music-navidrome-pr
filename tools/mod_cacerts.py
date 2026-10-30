#!/usr/bin/env python3
"""The CA bundle the Podcasts feed worker verifies with: /etc/m1plus-cacert.pem (patch/pcnet.h PN_CA).

Stock libcurl has no CA bundle (/etc/ssl/certs is empty), and a feed or its redirects can be on any host, so the
file is all of Mozilla's roots as curl extracts them (https://curl.se/docs/caextract.html, MPL-2.0), committed as
assets/cacert.pem and pinned here. A file of its own name: stock programs that look in /etc/ssl stay as they were.
To update: download https://curl.se/ca/cacert.pem, check it against https://curl.se/ca/cacert.pem.sha256, replace
assets/cacert.pem and SHA below.

Usage: mod_cacerts.py SRC_WORKDIR OUT_WORKDIR     (OUT == SRC edits in place)
"""
import hashlib, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modlib import clone_workdir

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'assets', 'cacert.pem')
SHA = '796f1389bfea13c0ed78f663b765baaff54a508e5483786bd6ece73c5e3e3cbe'   # curl's extract of 2026-10-20 (Mozilla's store)
REL = 'etc/m1plus-cacert.pem'
MODE, MTIME = 0o644, 1750924035   # stock /etc file mode; a stock mtime, so the build is deterministic


def added_rels(stock_rootfs=None):
    return [REL]


def apply(out):
    data = open(SRC, 'rb').read()
    assert hashlib.sha256(data).hexdigest() == SHA, f'{SRC}: not the pinned bundle'
    path = os.path.join(out, 'rootfs', REL)
    assert not os.path.exists(path), path
    with open(path, 'wb') as f: f.write(data)
    os.chmod(path, MODE); os.utime(path, (MTIME, MTIME))
    print(f'cacerts: /{REL} ({len(data)} bytes, {data.count(b"BEGIN CERTIFICATE")} roots)')


if __name__ == '__main__':
    clone_workdir(sys.argv[1], sys.argv[2]); apply(sys.argv[2])
