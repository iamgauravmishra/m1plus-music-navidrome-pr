/* The own Wi-Fi page's supplicant side: the control protocol, the escaped SSIDs, the security of a network and the split of the saved configuration (docs/modules/wifi.md).
 *
 * Copyright (c) 2026 Xin. MIT licence (see LICENSE).
 *
 * Nothing here touches a widget or a stock page. The control protocol is wpa_ctrl's, the one the stock player's own client and wpa_cli speak: a datagram socket bound to a private
 * path under /tmp, connected to /var/run/wpa_supplicant/wlan0, one command and its reply. The supplicant prints an SSID with printf escapes (\xNN, \\, \" ...): wf_unescape turns the
 * text into the bytes, which the page shows as UTF-8 (wf_utf8) and sends back as hex (SET_NETWORK id ssid <hex>), so any name survives (the stock page sent the escaped text raw).
 * Only plain C: no stock calls but libc, so the same functions run in test/pod/wifipage.py.
 */
#include "offsets.inc"
#include "stock.h"
#include "wifictl.h"

static int wf_hexv(int c) {
    return c >= '0' && c <= '9'   ? c - '0'
           : c >= 'a' && c <= 'f' ? c - 'a' + 10
           : c >= 'A' && c <= 'F' ? c - 'A' + 10
                                  : -1;
}

int wf_unescape(const char *s, unsigned n, unsigned char *out, unsigned max) {
    unsigned i = 0, o = 0;
    while (i < n && s[i] && o < max) {
        unsigned char c = (unsigned char)s[i++];
        if (c != '\\') {
            out[o++] = c;
            continue;
        }
        if (i >= n || !s[i]) break; /* a lone backslash at the end */
        c = (unsigned char)s[i++];
        if (c == 'n')
            out[o++] = '\n';
        else if (c == 'r')
            out[o++] = '\r';
        else if (c == 't')
            out[o++] = '\t';
        else if (c == 'e')
            out[o++] = 27;
        else if (c == '\\' || c == '"')
            out[o++] = c;
        else if (c == 'x') {
            int h = i < n ? wf_hexv(s[i]) : -1, l;
            if (h < 0) continue; /* hostap's printf_decode drops an escape it cannot read */
            i++;
            l = i < n ? wf_hexv(s[i]) : -1;
            if (l >= 0) h = h * 16 + l, i++;
            out[o++] = (unsigned char)h;
        } else if (c >= '0' && c <= '7') {
            int v = c - '0', k;
            for (k = 0; k < 2 && i < n && s[i] >= '0' && s[i] <= '7'; k++) v = v * 8 + (s[i++] - '0');
            out[o++] = (unsigned char)v;
        } else
            i--; /* any other escape loses its backslash and keeps the character, as printf_decode does */
    }
    return (int)o;
}

void wf_hex(const unsigned char *b, unsigned n, char *out) {
    static const char d[] = "0123456789abcdef";
    unsigned i;
    for (i = 0; i < n; i++) out[2 * i] = d[b[i] >> 4], out[2 * i + 1] = d[b[i] & 15];
    out[2 * n] = 0;
}

/* The length of the well formed UTF-8 sequence at b (at most n bytes left), 0 when it is not one. */
static unsigned wf_seq(const unsigned char *b, unsigned n) {
    unsigned char c = b[0];
    if (c < 0x80) return 1;
    if (c >= 0xc2 && c <= 0xdf) return n >= 2 && (b[1] & 0xc0) == 0x80 ? 2 : 0;
    if (c >= 0xe0 && c <= 0xef) {
        if (n < 3 || (b[1] & 0xc0) != 0x80 || (b[2] & 0xc0) != 0x80) return 0;
        if (c == 0xe0 && b[1] < 0xa0) return 0; /* overlong */
        if (c == 0xed && b[1] > 0x9f) return 0; /* a surrogate */
        return 3;
    }
    if (c >= 0xf0 && c <= 0xf4) {
        if (n < 4 || (b[1] & 0xc0) != 0x80 || (b[2] & 0xc0) != 0x80 || (b[3] & 0xc0) != 0x80) return 0;
        if (c == 0xf0 && b[1] < 0x90) return 0;
        if (c == 0xf4 && b[1] > 0x8f) return 0;
        return 4;
    }
    return 0;
}

int wf_utf8(const unsigned char *b, unsigned n, char *out, unsigned max) {
    unsigned i = 0, o = 0, k, s;
    if (!max) return 0;
    while (i < n && o + 1 < max) {
        s = wf_seq(b + i, n - i);
        if (s == 1 && (b[i] < 0x20 || b[i] == 0x7f)) s = 0; /* a control character */
        if (!s) {
            out[o++] = '?';
            i++;
        } else {
            if (o + s >= max) break;
            for (k = 0; k < s; k++) out[o++] = (char)b[i + k];
            i += s;
        }
    }
    out[o] = 0;
    return (int)o;
}

static int wf_has(const char *s, const char *w) {
    unsigned i, k;
    for (i = 0; s[i]; i++) {
        for (k = 0; w[k] && s[i + k] == w[k]; k++) {
        }
        if (!w[k]) return 1;
    }
    return 0;
}

int wf_security(const char *flags) {
    if (wf_has(flags, "EAP")) return WF_EAP;
    if (wf_has(flags, "OWE")) return WF_OWE;
    if (wf_has(flags, "SAE")) return wf_has(flags, "PSK") ? WF_TRANS : WF_SAE;
    if (wf_has(flags, "PSK") || wf_has(flags, "WPA") || wf_has(flags, "RSN")) return WF_PSK;
    if (wf_has(flags, "WEP")) return WF_WEP;
    return WF_OPEN;
}

int wf_security_keymgmt(const char *km) {
    if (wf_has(km, "EAP") || wf_has(km, "IEEE8021X")) return WF_EAP;
    if (wf_has(km, "OWE")) return WF_OWE;
    if (wf_has(km, "SAE")) return wf_has(km, "WPA-PSK") ? WF_TRANS : WF_SAE;
    if (wf_has(km, "WPA-PSK")) return WF_PSK;
    return WF_OPEN;
}

const char *wf_sec_label(int sec) {
    switch (sec) {
    case WF_OWE:
        return "Enhanced Open";
    case WF_WEP:
        return "WEP";
    case WF_PSK:
        return "WPA/WPA2";
    case WF_TRANS:
        return "WPA2/WPA3";
    case WF_SAE:
        return "WPA3";
    case WF_EAP:
        return "Enterprise";
    default:
        return "Open";
    }
}

static int wf_level(int dbm) { return dbm >= -65 ? 4 : dbm >= -75 ? 3 : dbm >= -80 ? 2 : 1; }

static void wf_copy(wf_net *d, const wf_net *s) { memcpy(d, s, sizeof *d); }

static int wf_same(const wf_net *a, const wf_net *b) {
    unsigned i;
    if (a->len != b->len) return 0;
    for (i = 0; i < a->len; i++)
        if (a->ssid[i] != b->ssid[i]) return 0;
    return 1;
}

static const char *wf_eol(const char *p) {
    while (*p && *p != '\n') p++;
    return p;
}

/* The tab separated fields of the line [t, e): their starts in f (at most k), how many there are. */
static int wf_fields(const char *t, const char *e, const char **f, int k) {
    int nf = 0;
    const char *p = t;
    f[nf++] = p;
    for (; p < e && nf < k; p++)
        if (*p == '\t') f[nf++] = p + 1;
    return nf;
}

static int wf_int(const char *p, const char *e) {
    int v = 0, neg = 0;
    if (p < e && *p == '-') neg = 1, p++;
    for (; p < e && *p >= '0' && *p <= '9'; p++) v = v * 10 + (*p - '0');
    return neg ? -v : v;
}

static int wf_prefix(const char *p, const char *k) {
    while (*k && *p == *k) p++, k++;
    return !*k;
}

static void wf_clear(wf_net *w) {
    memset(w, 0, sizeof *w);
    w->id = -1;
}

int wf_parse_scan(const char *text, wf_net *out, int max) {
    int n = 0;
    const char *t = text, *e;
    while (*t) {
        const char *f[5];
        e = wf_eol(t);
        if (wf_fields(t, e, f, 5) == 5) {
            wf_net w;
            char flags[96];
            unsigned fl = (unsigned)(f[4] - 1 - f[3]), i, nz = 0;
            wf_clear(&w);
            w.dbm = wf_int(f[2], f[3] - 1);
            if (fl >= sizeof flags) fl = sizeof flags - 1;
            for (i = 0; i < fl; i++) flags[i] = f[3][i];
            flags[fl] = 0;
            w.len = (unsigned char)wf_unescape(f[4], (unsigned)(e - f[4]), w.ssid, WF_SSID_MAX);
            for (i = 0; i < w.len; i++) nz += w.ssid[i] != 0;
            if (nz) { /* a hidden network (no name, or only NULs) is not listed */
                int j, pos;
                w.sec = (unsigned char)wf_security(flags);
                w.level = (unsigned char)wf_level(w.dbm);
                for (j = 0; j < n && !wf_same(&out[j], &w); j++) {
                }
                if (j < n) { /* the same name on another access point: the stronger one counts */
                    if (w.dbm > out[j].dbm) {
                        out[j].dbm = w.dbm, out[j].sec = w.sec, out[j].level = w.level;
                        while (j > 0 && out[j - 1].dbm < out[j].dbm) { /* its place moves up */
                            wf_net tmp;
                            wf_copy(&tmp, &out[j - 1]), wf_copy(&out[j - 1], &out[j]), wf_copy(&out[j], &tmp);
                            j--;
                        }
                    }
                } else {
                    if (n < max)
                        n++;
                    else if (out[n - 1].dbm >= w.dbm)
                        goto next; /* full, and weaker than the last */
                    pos = n - 1;
                    while (pos > 0 && out[pos - 1].dbm < w.dbm) wf_copy(&out[pos], &out[pos - 1]), pos--;
                    wf_copy(&out[pos], &w);
                }
            }
        }
    next:
        t = *e ? e + 1 : e;
    }
    return n;
}

int wf_parse_list(const char *text, wf_net *out, int max) {
    int n = 0;
    const char *t = text, *e;
    while (*t && n < max) {
        const char *f[4];
        e = wf_eol(t);
        if (wf_fields(t, e, f, 4) == 4 && f[0][0] >= '0' && f[0][0] <= '9') {
            wf_net *w = &out[n];
            const char *fe = f[3], *p;
            wf_clear(w);
            w->id = wf_int(f[0], f[1] - 1);
            w->len = (unsigned char)wf_unescape(f[1], (unsigned)(f[2] - 1 - f[1]), w->ssid, WF_SSID_MAX);
            w->known = 1;
            w->sec = WF_PSK;
            for (p = fe; p < e; p++) {
                if (wf_prefix(p, "[CURRENT]")) w->current = 1;
                if (wf_prefix(p, "[TEMP-DISABLED]")) w->bad = 1;
                if (wf_prefix(p, "[DISABLED]")) w->off = 1;
            }
            if (w->len) n++;
        }
        t = *e ? e + 1 : e;
    }
    return n;
}

void wf_parse_status(const char *text, wf_status *st) {
    const char *t = text, *e;
    memset(st, 0, sizeof *st);
    st->id = -1;
    while (*t) {
        e = wf_eol(t);
        if (wf_prefix(t, "wpa_state=")) {
            const char *v = t + 10;
            if (wf_prefix(v, "COMPLETED"))
                st->state = WF_ST_CONNECTED;
            else if (wf_prefix(v, "SCANNING"))
                st->state = WF_ST_SCANNING;
            else if (wf_prefix(v, "AUTHENTICATING") || wf_prefix(v, "ASSOCIATING") || wf_prefix(v, "ASSOCIATED") ||
                     wf_prefix(v, "4WAY_HANDSHAKE") || wf_prefix(v, "GROUP_HANDSHAKE"))
                st->state = WF_ST_CONNECTING;
        } else if (wf_prefix(t, "ssid="))
            st->len = (unsigned char)wf_unescape(t + 5, (unsigned)(e - t - 5), st->ssid, WF_SSID_MAX);
        else if (wf_prefix(t, "id=") && t[3] >= '0' && t[3] <= '9')
            st->id = wf_int(t + 3, e);
        else if (wf_prefix(t, "ip_address=") && e > t + 11) {
            unsigned i;
            st->ip = 1;
            for (i = 0; i + 1 < sizeof st->ipaddr && t + 11 + i < e; i++) st->ipaddr[i] = t[11 + i];
            st->ipaddr[i] = 0;
        }
        t = *e ? e + 1 : e;
    }
}

static int wf_rank(const wf_net *w) { return w->current ? 0 : w->known && w->level ? 1 : w->level ? 2 : 3; }

void wf_merge(wf_net *nets, int *n, int max, const wf_net *known, int nk, int cur) {
    int i, j, k;
    for (k = 0; k < nk; k++) {
        for (j = 0; j < *n && !wf_same(&nets[j], &known[k]); j++) {
        }
        if (j < *n) {
            nets[j].known = 1, nets[j].id = known[k].id, nets[j].off = known[k].off;
        } else {
            wf_copy(&nets[*n], &known[k]);
            nets[*n].level = 0, nets[*n].dbm = 0;
            (*n)++;
        }
    }
    for (j = 0; j < *n; j++) nets[j].current = (unsigned char)(cur >= 0 && nets[j].known && nets[j].id == cur);
    for (i = 1; i < *n; i++) { /* a stable insertion sort by rank, the signal inside the ranks in range */
        wf_net w;
        wf_copy(&w, &nets[i]);
        for (j = i; j > 0; j--) {
            int a = wf_rank(&nets[j - 1]), b = wf_rank(&w);
            if (a < b || (a == b && (a == 3 || nets[j - 1].dbm >= w.dbm))) break;
            wf_copy(&nets[j], &nets[j - 1]);
        }
        wf_copy(&nets[j], &w);
    }
    while (
        *n >
        max) { /* too many: the weakest network that is not saved goes (the rank 2 ones are last but the saved ones out of range), else the end */
        for (j = *n - 1; j >= 0 && wf_rank(&nets[j]) != 2; j--) {
        }
        if (j < 0) j = *n - 1;
        for (; j + 1 < *n; j++) wf_copy(&nets[j], &nets[j + 1]);
        (*n)--;
    }
}

int wf_list_off(char *r, unsigned size, unsigned char *map) {
    int pages = 0, last = -1;
    char cmd[32];
    memset(map, 0, WF_OFF_IDS / 8);
    while (pages < 64) {
        int len, more;
        const char *t, *e;
        if (last < 0)
            len = wf_cmd("LIST_NETWORKS", r, size);
        else {
            snprintf(cmd, sizeof cmd, "LIST_NETWORKS LAST_ID=%d", last);
            len = wf_cmd(cmd, r, size);
        }
        if (len < 0) return pages ? pages : -1;
        pages++;
        more = last;
        for (t = r; *t; t = *e ? e + 1 : e) {
            e = wf_eol(t);
            if (*t >= '0' && *t <= '9') {
                const char *f = t;
                int id = wf_int(t, e), tabs = 0;
                for (; f < e && tabs < 3; f++)
                    tabs += *f == '\t'; /* (the flags are the fourth field; a tab inside an SSID is escaped) */
                more = id;
                for (; f < e; f++)
                    if (wf_prefix(f, "[DISABLED]") && id < WF_OFF_IDS) map[id >> 3] |= (unsigned char)(1 << (id & 7));
            }
        }
        if (more == last || (unsigned)len + 256 < size) break; /* no line, or the reply was not near the cut */
        last = more;
    }
    return pages;
}

int wf_parse_route(const char *text, char *out, unsigned size) {
    const char *t = text, *e;
    out[0] = 0;
    while (*t) {
        const char *f[4];
        e = wf_eol(t);
        if (wf_fields(t, e, f, 4) == 4 && wf_prefix(t, "wlan0\t")) {
            unsigned v[2], fl = 0, k;
            int ok = 1;
            for (k = 0; k < 3; k++) { /* destination, gateway, flags: hex words */
                const char *p = f[k + 1], *q = k < 2 ? f[k + 2] - 1 : e;
                unsigned x = 0, n = 0;
                for (; p < q && wf_hexv(*p) >= 0 && n < 8; p++, n++) x = x << 4 | (unsigned)wf_hexv(*p);
                if (!n) ok = 0;
                if (k < 2)
                    v[k] = x;
                else
                    fl = x;
            }
            if (ok && v[0] == 0 && v[1] != 0 && (fl & 3) == 3 && size >= 16) { /* default route, up and via a gateway */
                unsigned o = 0, b;
                for (b = 0; b < 4; b++) {
                    unsigned x = v[1] >> (8 * b) & 255;
                    if (x >= 100) out[o++] = (char)('0' + x / 100);
                    if (x >= 10) out[o++] = (char)('0' + x / 10 % 10);
                    out[o++] = (char)('0' + x % 10);
                    out[o++] = b < 3 ? '.' : 0;
                }
                return 1;
            }
        }
        t = *e ? e + 1 : e;
    }
    return 0;
}

int wf_pass_hex(const char *pass) {
    unsigned n = 0;
    for (; pass[n]; n++)
        if (wf_hexv(pass[n]) < 0) return 0;
    return n == 64;
}

int wf_pass_ok(const char *pass, int sec) {
    unsigned n = 0, hex = 1;
    for (; pass[n]; n++) {
        if ((unsigned char)pass[n] < 32 || (unsigned char)pass[n] > 126) return 0;
        if (wf_hexv(pass[n]) < 0) hex = 0;
    }
    if (sec == WF_SAE) return n >= 1 && n <= WF_SAE_MAX;
    return (n >= WF_PASS_MIN && n <= WF_PASS_MAX) || (n == 64 && hex);
}

/* The keys of a network block that a stock 2.9 supplicant reads (every key its networkAddSsid / wifiSet* calls set, and the ones the supplicant itself saves with them). */
static const char *const wf_stock_keys[] = {"ssid",     "scan_ssid",     "bssid",     "psk",      "key_mgmt",
                                            "priority", "disabled",      "id_str",    "proto",    "pairwise",
                                            "group",    "auth_alg",      "wep_key0",  "wep_key1", "wep_key2",
                                            "wep_key3", "wep_tx_keyidx", "frequency", "mode"};

static int wf_stock_key(const char *k, unsigned n) {
    unsigned i, j;
    for (i = 0; i < sizeof wf_stock_keys / sizeof *wf_stock_keys; i++) {
        for (j = 0; j < n && wf_stock_keys[i][j] == k[j]; j++) {
        }
        if (j == n && !wf_stock_keys[i][j]) return 1;
    }
    return 0;
}

/* key_mgmt's value (v, n bytes): only NONE and WPA-PSK. */
static int wf_stock_keymgmt(const char *v, unsigned n) {
    unsigned i = 0;
    int any = 0;
    while (i < n) {
        unsigned s = i, l;
        while (i < n && v[i] != ' ' && v[i] != '\t') i++;
        l = i - s;
        if (l) {
            any = 1;
            if (!((l == 4 && wf_prefix(v + s, "NONE")) || (l == 7 && wf_prefix(v + s, "WPA-PSK")))) return 0;
        }
        while (i < n && (v[i] == ' ' || v[i] == '\t')) i++;
    }
    return any;
}

/* One network block [b, e) (e just after its closing line): 1 when a stock supplicant can read it. */
static int wf_block_stock(const char *b, const char *e) {
    const char *p = wf_eol(b);
    if (*p) p++; /* past the "network={" line */
    while (p < e) {
        const char *le = wf_eol(p), *q = p, *k;
        while (q < le && (*q == ' ' || *q == '\t')) q++;
        if (q < le && *q != '#' && *q != '}') {
            for (k = q; k < le && *k != '='; k++) {
            }
            if (k == le || !wf_stock_key(q, (unsigned)(k - q))) return 0;
            if (k - q == 8 && wf_prefix(q, "key_mgmt") && !wf_stock_keymgmt(k + 1, (unsigned)(le - k - 1))) return 0;
        }
        p = *le ? le + 1 : le;
    }
    return 1;
}

static int wf_put(char *out, unsigned *len, unsigned cap, const char *s, unsigned n) {
    unsigned i;
    if (*len + n + 1 > cap) return -1;
    for (i = 0; i < n; i++) out[*len + i] = s[i];
    *len += n;
    out[*len] = 0;
    return 0;
}

int wf_split(const char *in, unsigned n, char *stock, unsigned *ns, char *ours, unsigned *no, unsigned cap) {
    const char *p = in, *end = in + n, *b = 0;
    *ns = *no = 0;
    if (cap) stock[0] = ours[0] = 0;
    while (p < end && *p) {
        const char *le = p, *q = p;
        while (le < end && *le && *le != '\n') le++;
        while (q < le && (*q == ' ' || *q == '\t')) q++;
        {
            const char *next = le < end && *le ? le + 1 : le;
            unsigned ll = (unsigned)(next - p);
            if (!b && le - q >= 9 && wf_prefix(q, "network={"))
                b = p;
            else if (b && q < le && *q == '}') {
                int st = wf_block_stock(b, next);
                if (wf_put(st ? stock : ours, st ? ns : no, cap, b, (unsigned)(next - b)) != 0) return -1;
                if (!st && wf_put(ours, no, cap, "\n", 1) != 0) return -1;
                b = 0;
            } else if (!b && wf_put(stock, ns, cap, p, ll) != 0)
                return -1;
            p = next;
        }
    }
    return 0;
}

struct wf_sun {
    unsigned short family;
    char path[108];
};

#define WF_AF_UNIX 1
#define WF_SOCK_DGRAM 1 /* MIPS: SOCK_DGRAM is 1 and SOCK_STREAM 2 */

static void wf_path(struct wf_sun *a, const char *p) {
    unsigned i;
    memset(a, 0, sizeof *a);
    a->family = WF_AF_UNIX;
    for (i = 0; p[i] && i < sizeof a->path - 1; i++) a->path[i] = p[i];
}

int wf_cmd(const char *cmd, char *reply, unsigned size) {
    struct wf_sun lo, rm;
    char local[40];
    unsigned fds[32], cl = 0;
    int tv[2], fd, r = -1, n, ll;
    if (!size) return -1;
    reply[0] = 0;
    fd = socket(WF_AF_UNIX, WF_SOCK_DGRAM, 0);
    if (fd < 0 || fd >= 1024) {
        if (fd >= 0) close(fd);
        return -1;
    }
    ll = snprintf(local, sizeof local, "/tmp/m1plus-wc-%d", getpid());
    wf_path(&lo, local);
    wf_path(&rm, WF_CTRL_DIR "/wlan0");
    unlink(local);
    if (bind(fd, &lo, 2 + (unsigned)ll + 1) == 0 && connect(fd, &rm, 2 + sizeof(WF_CTRL_DIR "/wlan0")) == 0) {
        while (cmd[cl]) cl++;
        if (send(fd, cmd, cl, 0) == (int)cl) {
            memset(fds, 0, sizeof fds);
            fds[fd >> 5] |= 1u << (fd & 31);
            tv[0] = 1, tv[1] = 500000;
            if (select(fd + 1, fds, 0, 0, tv) > 0 && (n = recv(fd, reply, size - 1, 0)) >= 0) {
                reply[n] = 0;
                r = n;
            }
        }
    }
    close(fd);
    unlink(local);
    return r;
}

int wf_ok(const char *cmd) {
    char r[32];
    return wf_cmd(cmd, r, sizeof r) >= 2 && r[0] == 'O' && r[1] == 'K';
}
