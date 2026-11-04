#!/usr/bin/env python3
"""Copy a package to the player's TF card as update.bin, with the checks that have been skipped before.

  make flash [BUILD=latest] [VOLUME=/Volumes/Music] [DRY_RUN=1]
  uv run python -I tools/flash_sd.py PACKAGE [--dry-run] [--no-eject]

Refuses unless
  - `fwtool verify` passes on PACKAGE, and
  - PACKAGE's SHA-256 is in test/golden.sha256, or --build selects a complete, matching dev test receipt;
  - the volume is a card: `diskutil info` Protocol is Secure Digital or USB, it holds the player's
    .downpic or Music folder, and it is not the SanDisk Extreme USB SSD.
Then shows the update.bin already on the card (version = firmware_v20.info line 2, SHA-256), copies
with `cp -X` (no AppleDouble), removes ._update.bin, syncs, re-hashes and compares, prints the
version found on the card, and ejects (--no-eject to keep it mounted). macOS only.
"""
import argparse, os, subprocess, sys, tarfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import workflow

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, 'test', 'golden.sha256')
FORBIDDEN = ('sandisk extreme',)          # the USB SSD, never a flash target
PROTOCOLS = ('secure digital', 'usb')

sha256 = workflow.sha

def version(p):
    with tarfile.open(p) as t: return t.extractfile('firmware_v20.info').read().decode().split('\n')[1]

def golden_for(sha):
    if os.path.exists(GOLDEN):
        for line in open(GOLDEN):
            f = line.split()
            if len(f) >= 3 and f[0] == sha: return f[1], f[2]
    return None

def diskutil(vol):
    r = subprocess.run(['diskutil', 'info', vol], capture_output=True, text=True)
    if r.returncode: sys.exit(f'diskutil info {vol} failed: {r.stderr.strip()}')
    return {k.strip().lower(): v.strip() for k, v in (l.split(':', 1) for l in r.stdout.splitlines() if ':' in l)}

def check_volume(vol):
    if not os.path.ismount(vol): sys.exit(f'{vol} is not a mounted volume')
    info = diskutil(vol)
    blob = ' '.join(info.values()).lower()
    if any(f in blob for f in FORBIDDEN): sys.exit(f'{vol} is the USB SSD ({FORBIDDEN[0]}): never a flash target')
    proto = info.get('protocol', '').lower()
    if proto not in PROTOCOLS: sys.exit(f'{vol}: protocol {info.get("protocol")!r}, want Secure Digital or USB')
    if not any(os.path.exists(os.path.join(vol, n)) for n in ('.downpic', 'Music')):
        sys.exit(f'{vol} has no .downpic or Music folder: not the player\'s card')
    print(f'card: {vol}  {info.get("device / media name", "?")}  protocol {info.get("protocol")}  '
          f'{info.get("volume name", "")}  {info.get("file system personality", "")}')

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    source = ap.add_mutually_exclusive_group(required=True)
    source.add_argument('package', nargs='?', help='an accepted release/restore package')
    source.add_argument('--build', help='a fully tested dev build directory, or latest')
    ap.add_argument('--volume', default='/Volumes/Music')
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--no-eject', action='store_true')
    a = ap.parse_args()
    receipt = None
    if a.build:
        pkg, receipt = workflow.tested_package(a.build)
        pkg = str(pkg)
        print(f'dev build: {os.path.dirname(pkg)} ({receipt["tag"]})')
    else: pkg = os.path.abspath(a.package)
    if not os.path.exists(pkg): sys.exit(f'missing {pkg}')
    r = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'tools', 'fwtool.py'), 'verify', pkg], capture_output=True, text=True)
    if r.returncode: sys.exit(f'fwtool verify FAILED:\n{r.stdout}{r.stderr}')
    sha, ver = sha256(pkg), version(pkg)
    g = golden_for(sha)
    print(f'package: {os.path.basename(pkg)}\n  version {ver}  sha256 {sha}\n  fwtool verify: OK')
    if g: print(f'  golden: MATCH ({g[1]}, {g[0]})')
    elif receipt and ver == receipt['tag']: print('  full dev test receipt: MATCH')
    else: sys.exit('refusing: no matching release golden. For development use make dev, then make flash.')
    check_volume(a.volume)
    dst = os.path.join(a.volume, 'update.bin')
    if os.path.exists(dst):
        try: print(f'on the card now: update.bin version {version(dst)}  sha256 {sha256(dst)}')
        except (tarfile.TarError, KeyError, OSError) as e: print(f'on the card now: update.bin (unreadable: {e})')
    else: print('on the card now: no update.bin')
    if a.dry_run: print(f'dry run: would cp -X to {dst}, remove ._update.bin, sync, compare, {"leave mounted" if a.no_eject else "eject"}'); return
    subprocess.run(['cp', '-X', pkg, dst], check=True)
    junk = os.path.join(a.volume, '._update.bin')
    if os.path.exists(junk): os.remove(junk)
    subprocess.run(['sync'], check=True)
    got = sha256(dst)
    if got != sha: sys.exit(f'COPY MISMATCH: card has {got}, wanted {sha}. Do not flash; copy again.')
    print(f'copied and verified: update.bin on the card is {version(dst)} ({got[:16]}…)')
    if a.no_eject: print('left mounted (--no-eject)')
    else:
        subprocess.run(['diskutil', 'eject', a.volume], check=True)
    print('Next: System settings -> System Update -> TF card update.')

if __name__ == '__main__': main()
