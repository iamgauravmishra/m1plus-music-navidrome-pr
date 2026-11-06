"""The newer Wi-Fi supplicant (tools/mod_wpa.py, docs/modules/wifi.md): the built hostap binary, its ELF facts against the stock
supplicant and libraries, the untouched stock programs, and wifi_connect.sh's choice between ours and stock's."""
import os, re, stat, subprocess, tempfile
from unittest import mock
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)
import mod_wpa as mw


def run(ctx):
    expect = ctx.expect
    root = os.path.join(WORK, 'rootfs')
    stock = mw.stock_root()
    ours = os.path.join(root, mw.REL_BIN)
    read = lambda p: open(p, 'rb').read()

    # ---- pins ----
    expect(mw.HOSTAP_VERSION == '2.12' and mw.HOSTAP[0].endswith('wpa_supplicant-2.12.tar.gz') and re.fullmatch('[0-9a-f]{64}', mw.HOSTAP[1]),
           'the hostap source is the pinned release tarball')
    expect(sorted(re.sub(r'_[0-9a-z.+-]+_mipsel.deb', '', os.path.basename(n)) for n, _ in mw.DEBS)
           == ['libc6-dev', 'libnl-3-dev', 'libnl-genl-3-dev', 'libssl-dev', 'linux-libc-dev']
           and all(re.fullmatch('[0-9a-f]{64}', s) for _, s in mw.DEBS) and '2.28' in mw.DEBS[0][0] and 'deb10' in mw.DEBS[2][0],
           'the headers are five pinned Debian 10 mipsel packages (glibc 2.28, OpenSSL 1.1.1, libnl 3.4)')
    expect(mw.sha256(read(os.path.join(stock, mw.SCRIPT))) == mw.SCRIPT_SHA, 'wifi_connect.sh is pinned by the stock SHA-256')
    cfg = dict(l.split('=') for l in open(os.path.join(mw.ASSETS, 'config')).read().splitlines() if re.match('CONFIG_[A-Z0-9_]+=', l))
    for k in ('DRIVER_NL80211', 'CTRL_IFACE', 'SAE', 'OWE', 'EAP_PEAP', 'EAP_TTLS', 'EAP_TLS', 'EAP_MSCHAPV2', 'EAP_GTC', 'EAP_MD5', 'WPS',
              'IEEE8021X_EAPOL', 'LIBNL32', 'SUITEB192'):
        expect(cfg.get('CONFIG_' + k) == 'y', f'config builds CONFIG_{k}')
    expect(cfg.get('CONFIG_TLS') == 'openssl' and 'CONFIG_CTRL_IFACE_DBUS_NEW' not in cfg and 'CONFIG_DEBUG_FILE' not in cfg,
           'TLS is OpenSSL, no dbus, no debug file')

    # ---- the files in the tree ----
    expect(mw.added_rels() == ['usr/lib/m1plus', 'usr/lib/m1plus/wpa_supplicant'], 'the step adds a directory and the binary')
    expect(os.path.isdir(os.path.join(root, mw.REL_DIR)) and not os.path.exists(os.path.join(stock, mw.REL_DIR)), 'the directory is new')
    expect(os.path.isfile(ours) and stat.S_IMODE(os.stat(ours).st_mode) == 0o755 and os.path.basename(ours) == 'wpa_supplicant',
           'ours is an executable named wpa_supplicant (the player kills it by that name)')
    for rel in ('usr/sbin/wpa_supplicant', 'usr/sbin/wpa_cli', 'usr/lib/libwpa_client.so', 'etc/wpa_supplicant.conf'):
        expect(read(os.path.join(root, rel)) == read(os.path.join(stock, rel)), f'/{rel} is the stock file')
    expect(sorted(os.listdir(os.path.join(root, mw.REL_DIR))) == ['wpa_supplicant'], 'nothing else in the directory')

    # ---- the ELF ----
    data = read(ours)
    new, old = mw.elf_info(ours), mw.elf_info(os.path.join(stock, mw.STOCK_BIN))
    expect(new['type'] == old['type'] == 'ET_EXEC', 'an executable of the same type as stock (not PIE)')
    expect(new['flags'] == old['flags'] and new['flags'] & 0x400 and new['flags'] & 0x1000 and new['flags'] & 0x70000000 == 0x70000000,
           f'e_flags {new["flags"]:#x} equal stock\'s: NaN2008, o32, mips32r2')
    expect(new['interp'] == '/lib/ld-linux-mipsn8.so.1', 'the NaN2008 loader')
    expect(new['stack'] is not None and not new['stack'] & 1, 'a non-executable stack')
    expect(set(new['needed']) <= set(mw.LIBS) and {'libssl.so.1.1', 'libcrypto.so.1.1', 'libnl-3.so.200', 'libnl-genl-3.so.200', 'libc.so.6'} <= set(new['needed']),
           f'NEEDED are stock libraries: {new["needed"]}')
    expect(all(os.path.exists(os.path.join(stock, mw.LIBS[n])) for n in new['needed']), 'each NEEDED library is on the stock rootfs')
    try: mw.verify(ours, stock); ok = True
    except SystemExit as e: ok = False; print(e)
    expect(ok, 'every imported symbol and version is exported by the stock libraries (glibc <= 2.28, OpenSSL 1.1, libnl 3)')
    glibc = {v for _, lib, v, _ in new['imports'] if v and v.startswith('GLIBC_')}
    expect(glibc and max(tuple(int(x) for x in v[6:].split('.')) for v in glibc) <= (2, 28), f'glibc versions {sorted(glibc)}')
    expect(not re.search(rb'\.(pdr|mdebug)', data[-3000:]) and len(data) < 1000000, f'stripped, {len(data)} bytes (stock 900792)')
    expect(b'wpa_supplicant v2.12' in data, 'it reports hostap 2.12')
    for m in (b'PEAP', b'TTLS', b'TLS', b'MSCHAPV2', b'GTC', b'MD5', b'PWD', b'WSC'):
        expect(b'\0' + m + b'\0' in data, f'EAP-{m.decode()} is compiled in')
    for s in (b'SAE', b'OWE', b'WPA-EAP-SUITE-B-192', b'FT-SAE', b'ieee80211w', b'domain_suffix_match', b'ca_cert', b'sae_password',
              b'CTRL-EVENT-EAP-TLS-CERT-ERROR', b'nl80211'):
        expect(b'\0' + s in data or s + b'\0' in data, f'{s.decode()} is compiled in')
    stock_data = read(os.path.join(stock, mw.STOCK_BIN))
    expect(all(b'\0' + m + b'\0' not in stock_data for m in (b'SAE', b'PEAP', b'TTLS', b'MSCHAPV2', b'TLS')), 'stock 2.9 has none of these methods (the reason for the step)')

    # ---- verify() refuses what would not load ----
    def refused(info_edit, why):
        real = mw.elf_info
        def patched(p):
            i = real(p)
            if p == ours: info_edit(i)
            return i
        with mock.patch.object(mw, 'elf_info', patched):
            try: mw.verify(ours, stock); expect(False, f'verify accepts {why}')
            except SystemExit: expect(True, '')
    refused(lambda i: i.update(flags=i['flags'] & ~0x400), 'a legacy-NaN binary')
    refused(lambda i: i.update(interp='/lib/ld.so.1'), 'another interpreter')
    refused(lambda i: i.update(needed=i['needed'] + ['libfoo.so.1']), 'a library the rootfs lacks')
    refused(lambda i: i['imports'].append(('memcpy', 'libc.so.6', 'GLIBC_2.29', 'STB_GLOBAL')), 'glibc 2.29')
    refused(lambda i: i['imports'].append(('no_such_function', 'libc.so.6', 'GLIBC_2.0', 'STB_GLOBAL')), 'a symbol the stock libc lacks')
    refused(lambda i: i['imports'].append(('no_such_function', None, None, 'STB_GLOBAL')), 'an unversioned symbol no library has')
    with tempfile.TemporaryDirectory() as t:
        bad = os.path.join(t, 'x'); open(bad, 'wb').write(b'not an elf')
        try: mw.verify(bad, stock); expect(False, 'verify accepts a non-ELF')
        except (SystemExit, AssertionError): expect(True, '')

    # ---- wifi_connect.sh ----
    built = read(os.path.join(root, mw.SCRIPT))
    orig = read(os.path.join(stock, mw.SCRIPT))
    expect(built == mw.rewrite_script(orig) and built != orig, 'the script is stock\'s with the supplicant start replaced')
    for line in (b'killall udhcpc > /dev/null\n', b'killall wpa_supplicant > /dev/null\n', b'WPA_CONF=/mnt/data/wpa_supplicant.conf\n',
                 b'\tifconfig $INTERFACE up\n', b'\ttouch /tmp/wpasupplicant_initsuccess\n', b'exit 0\n'):
        expect(line in built, f'stock line kept: {line.strip().decode()}')
    expect(b'\t"$WPA" -Dnl80211 -i$INTERFACE -c$CONF -B\n' in built and b'\tCONF=$WPA_CONF\n' in built and b'WPA=wpa_supplicant\n' in built,
           'stock\'s command line, and stock\'s program unless ours is chosen')
    expect(b'[ ! -e /mnt/mmc/m1plus-off ]' in built and b'"$NEWWPA" -v' in built, 'ours needs no kill switch and a working -v')
    try: mw.rewrite_script(orig.replace(b'killall', b'killal')); expect(False, 'rewrite_script accepts another script')
    except SystemExit: expect(True, '')
    try: mw.rewrite_script(built); expect(False, 'rewrite_script accepts its own output')
    except SystemExit: expect(True, '')

    # run it under the host shell with stub programs and its fixed paths pointed into a scratch directory
    rec_conf = lambda p: open(p).read() if os.path.exists(p) else None
    def script_run(new_ok=True, new_exists=True, kill=False, card=True, noconf=False, nets=None, start_rc=0, stale=False):
        with tempfile.TemporaryDirectory() as t:
            bindir, mmc, data_dir = (os.path.join(t, d) for d in ('bin', 'mmc', 'data'))
            for d in (bindir, mmc, data_dir): os.mkdir(d)
            conf, init = os.path.join(data_dir, 'wpa_supplicant.conf'), os.path.join(t, 'initsuccess')
            if not noconf: open(conf, 'w').write('ctrl_interface=/var/run/wpa_supplicant\n')
            record = os.path.join(t, 'record')
            def stub(path, body):
                open(path, 'w').write('#!/bin/sh\n' + body); os.chmod(path, 0o755)
            for n in ('killall', 'udhcpc', 'ifconfig', 'sync'): stub(os.path.join(bindir, n), 'exit 0\n')
            stub(os.path.join(bindir, 'wpa_supplicant'), f'[ "$1" = -v ] && {{ echo "wpa_supplicant v2.9"; exit 0; }}; echo "stock $@" >> {record}\n')
            newwpa = os.path.join(t, 'new')
            if new_exists:
                stub(newwpa, f'[ "$1" = -v ] && {{ echo "wpa_supplicant v2.12"; exit {0 if new_ok else 3}; }}; echo "new $@" >> {record}; exit {start_rc}\n')
            if kill: open(os.path.join(mmc, 'm1plus-off'), 'w').close()
            netfile = os.path.join(data_dir, 'wifi-networks')
            if nets is not None: open(netfile, 'w').write(nets)
            combined = os.path.join(t, 'combined.conf')
            if stale: open(combined, 'w').write('a copy left by the last start\n')
            text = built.decode()
            for a, b in (('/usr/lib/m1plus/wpa_supplicant', newwpa), ('/mnt/mmc', mmc if card else os.path.join(t, 'nocard')),
                         ('/mnt/data/wpa_supplicant.conf', conf), ('/mnt/data/m1plus/wifi-networks', netfile), ('/tmp/wpasupplicant_initsuccess', init), ('/tmp/m1plus-wpa.conf', combined)):
                text = text.replace(a, b)
            script = os.path.join(t, 'wifi_connect.sh'); open(script, 'w').write(text)
            env = {'PATH': bindir + ':/usr/bin:/bin'}
            syntax = subprocess.run(['sh', '-n', script], capture_output=True)
            r = subprocess.run(['sh', script], env=env, capture_output=True, timeout=30)
            return (syntax.returncode, r.returncode, os.path.exists(init), open(record).read() if os.path.exists(record) else '', r.stdout, rec_conf(combined))
    arg = '-Dnl80211 -iwlan0 -c'
    sy, rc, init, rec, _, comb = script_run()
    expect(sy == 0 and rc == 0 and init and rec.startswith('new ' + arg) and rec.endswith('combined.conf -B\n') and comb == 'ctrl_interface=/var/run/wpa_supplicant\n\n',
           f'ours starts with stock\'s arguments on a copy of the real configuration: {rec!r} {comb!r}')
    for case, kw in (('the kill switch exists', dict(kill=True)), ('our -v fails', dict(new_ok=False)), ('ours is missing', dict(new_exists=False))):
        sy, rc, init, rec, _, _ = script_run(**kw)
        expect(sy == 0 and rc == 0 and init and rec.startswith('stock ' + arg) and rec.endswith('wpa_supplicant.conf -B\n'),
               f'{case}: stock\'s supplicant starts, as before: {rec!r}')
    sy, rc, init, rec, _, comb = script_run(kill=True, nets='network={\n}\n', stale=True)
    expect(rec.startswith('stock ') and rec.endswith('data/wpa_supplicant.conf -B\n') and comb is None, 'off: the networks only ours reads are never used, and the copy of the last start is gone')
    sy, rc, init, rec, _, _ = script_run(card=False, new_ok=False)
    expect(rc == 0 and init and rec.startswith('stock '), 'our -v failing without a card: stock')
    sy, rc, init, rec, _, _ = script_run(card=False)
    expect(rc == 0 and init and rec.startswith('new '), 'no card: Wi-Fi unaffected')
    sy, rc, init, rec, out, _ = script_run(noconf=True)     # the early exit for a missing config stays
    expect(rc == 0 and not init and rec == '' and b'No configuration file' in out, 'without a config the script still exits early')
    nets = 'network={\n\tssid="WPA3"\n\tkey_mgmt=SAE\n}\n'
    sy, rc, init, rec, _, comb = script_run(nets=nets, stale=True)     # the networks only ours reads (the Wi-Fi page's wifi-networks)
    expect(rec.startswith('new ' + arg) and rec.endswith('combined.conf -B\n') and comb == 'ctrl_interface=/var/run/wpa_supplicant\n\n' + nets,
           f'the stock configuration, a blank line and wifi-networks are the copy ours reads (the copy of the last start replaced): {rec!r} {comb!r}')
    for case, kw in (('the kill switch exists', dict(kill=True)), ('our -v fails', dict(new_ok=False)), ('ours is missing', dict(new_exists=False))):
        sy, rc, init, rec, _, comb = script_run(nets=nets, stale=True, **kw)
        expect(rec.startswith('stock ' + arg) and rec.endswith('data/wpa_supplicant.conf -B\n') and comb is None,
               f'{case}: stock reads the real config, never wifi-networks, and no copy is left: {rec!r}')
    sy, rc, init, rec, _, comb = script_run(nets=nets, start_rc=1)     # ours cannot read the configuration (a saved WEP network): stock's supplicant starts instead, on the real file
    lines = rec.splitlines()
    expect(rc == 0 and init and len(lines) == 2 and lines[0].startswith('new ' + arg) and lines[0].endswith('combined.conf -B') and lines[1].startswith('stock ' + arg)
           and lines[1].endswith('data/wpa_supplicant.conf -B') and comb is None,
           f'ours failing to start hands over to stock on the real file: {rec!r}')
    sy, rc, init, rec, _, comb = script_run(nets=nets, start_rc=1, kill=True)
    expect(rec.splitlines() == [l for l in rec.splitlines() if l.startswith('stock ')] and len(rec.splitlines()) == 1, 'no second start when stock was the first')
    expect(b'm1plus-wpa-extra' not in built, 'the probe card file of extra networks is gone: the Wi-Fi page adds networks')
