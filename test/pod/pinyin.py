"""Stock's Google Pinyin engine under emulation (docs/modules/keyboard.md "Pinyin engine"): the facts the keyboard's Chinese layer (patch/keyboard.c) is built on, and the `Engine` machine
test/pod/keyboard.py runs the payload on.

engine_tests: demo's own ime_pinyin code (im_open_decoder, im_search, im_get_candidate, im_choose and everything under them: MatrixSearch, DictTrie, SpellingTrie, NGram, the user
dictionary) runs for real under Unicorn with the real dictionary assets/default/raw/data/gpinyin.dat; only libc is Python (a heap, files in memory, qsort with the stock comparison
routines, libgcc's 64 bit division, libm's log). It answers: does the engine open that file, is the candidate list of "nihao" headed by 你好, are the candidates UTF-16, what state does
stock's own init leave (the dictionary it asks for, /usr/dict_pinyin.dat, is not in the rootfs), may our open replace that state, how smart is the matching (abbreviations, partial
syllables, sentences, fuzzy initials), what choose() does, and whether a user dictionary re-ranks within a session.
Also: the pinyin of a hanzi string (zhou jie lun) from the dictionary's own tables, for a future library search where "zjl" finds 周杰伦."""
import functools, math, os, struct
from unicorn import UcError
from unicorn.mips_const import UC_MIPS_REG_F12, UC_MIPS_REG_F0, UC_MIPS_REG_CP0_STATUS as STATUS
from harness import *   # noqa: F401,F403  (test/patch.py initialises the harness before loading a module)

DICT = os.path.join(WORK, 'rootfs', 'release', 'assets', 'default', 'raw', 'data', 'gpinyin.dat')
DEFS = {}
for _line in open(os.path.join(ROOT, 'patch', 'keyboard.h')):
    _m = re.match(r'#define (\w+) ("[^"]*"|\w+)\s*(?:/\*.*)?$', _line.strip())
    if _m: DEFS[_m.group(1)] = _m.group(2).strip('"') if _m.group(2).startswith('"') else int(_m.group(2), 0)
SYS_PATH, USER_PATH, CAND_LEN = (DEFS[k] for k in ('PINYIN_DICT', 'PINYIN_USER', 'KB_CAND_U16'))
CANDS = 8   # candidates read per input by the research tests
ENGINE_PTR = pod.DATA['PY_ENGINE'][0]          # the global MatrixSearch*
IM = {n: pod.FUNCTIONS[n][2] for n in pod.FUNCTIONS if n.startswith('im_')}
WORDS = ('nihao', 'zhongguo', 'bokesou', 'yinyue', 'shanling')   # the whole-word inputs
PREDICTS = pod.FUNCTIONS['_ZN10ime_pinyin12MatrixSearch12get_predictsEPKtPA8_tj'][2]   # MatrixSearch::get_predicts(this, history, out[][8], n)
SPLIDS_FOR_HANZI, SPELLING_STR, LEMMA_ID = 0x5bffd4, 0x5c922c, 0x5c01a4   # DictList::get_splids_for_hanzi(this, hanzi, half_splid, splids, max), SpellingTrie::get_spelling_str(this, splid), DictList::get_lemma_id(this, str, len): research only, the payload calls none
FAKE = SCRATCH + 0x80000    # fake libc entry points (a GOT slot each)
O_CREAT, O_TRUNC = 0x100, 0x200   # MIPS Linux

LIBC = ('malloc calloc realloc free _Znwj _Znaj _ZdlPvj _ZdaPv memcpy memmove memset memcmp strlen strcmp strcpy strdup '
        'bsearch fopen fread fwrite fseek ftell fclose feof ferror fdopen open read write lseek close ftruncate unlink access time gettimeofday qsort log '
        'pthread_mutex_init pthread_mutex_lock pthread_mutex_unlock pthread_mutex_trylock printf puts snprintf sprintf '
        '__udivdi3 __divdi3 __moddi3 usleep sleep').split()


class Engine(Machine):
    """demo's engine code for real. The payload's own libc stubs keep the base machine's mocks; the engine's imports (demo's GOT slots, each pointed at a `jr ra` stub) are these.
    Files live in memory: `blobs` (path -> bytearray) are what exists; a path can be created only under a prefix of `writable`."""
    COUNT = True

    def __init__(self, blobs=None, writable=()):
        super().__init__()
        self.blobs = {k: bytearray(v) for k, v in (blobs or {}).items()}
        self.writable = tuple(writable)
        self.streams = {}               # FILE* or fd -> [the file's bytearray, position, path]
        self.opened = []                # every path the engine tried to fopen or open
        for a in list(IM.values()) + [PREDICTS]: self.handlers.pop(a, None)    # not mocked: stock's own code
        slots = pod.got_slots(DEMO, set(LIBC))
        self.fake = {}
        for i, n in enumerate(sorted(slots)):
            a = FAKE + 16 * i
            self.fake[a] = n
            self.setword(slots[n], a)
            self.u.mem_write(a, struct.pack('<II', 0x03e00008, 0))   # jr ra; nop: the block ends at the trap
            self.handlers[a] = n
        self.u.reg_write(STATUS, self.u.reg_read(STATUS) | 1 << 29 | 1 << 26)   # CU1 and FR: demo's float code is -mfp64 (odd double registers)
        self.next_fd = 100

    def _file(self, path, mode):
        """The in-memory file of fopen / open: None when it does not exist and cannot be created."""
        make = ('w' in mode) if isinstance(mode, str) else bool(mode & O_CREAT)
        trunc = ('w' in mode) if isinstance(mode, str) else bool(mode & O_TRUNC)
        if path not in self.blobs:
            if not (make and path.startswith(self.writable) and self.writable): return None
            self.blobs[path] = bytearray()
        if trunc: self.blobs[path][:] = b''
        return self.blobs[path]

    def _hook(self, u, address, size, _):
        n = self.fake.get(address)
        if n is None: return super()._hook(u, address, size, _)
        a0, a1, a2, a3 = (u.reg_read(r) for r in (UC_MIPS_REG_A0, UC_MIPS_REG_A1, UC_MIPS_REG_A2, UC_MIPS_REG_A3))
        sp = u.reg_read(UC_MIPS_REG_SP)
        ret, v1 = 0, None
        sint = lambda v: struct.unpack('<i', struct.pack('<I', v & 0xffffffff))[0]
        mem = lambda a, k: bytes(u.mem_read(a, k)) if k else b''
        if n in ('malloc', '_Znwj', '_Znaj'): ret = self.malloc(a0 or 1)
        elif n == 'calloc': ret = self.malloc(a0 * a1 or 1)
        elif n == 'realloc':
            ret = self.malloc(a1 or 1)
            if a0: u.mem_write(ret, mem(a0, a1))   # (the old block's size is not kept: a copy of a1 bytes from the old one is always inside the heap)
        elif n in ('free', '_ZdlPvj', '_ZdaPv'): pass
        elif n in ('memcpy', 'memmove'):
            u.mem_write(a0, mem(a1, a2)); ret = a0
        elif n == 'memset':
            u.mem_write(a0, bytes([a1 & 255]) * a2); ret = a0
        elif n == 'memcmp':
            x, y = mem(a0, a2), mem(a1, a2); ret = (x > y) - (x < y)
        elif n == 'strlen': ret = len(self.read_cstr(a0).encode('latin-1'))
        elif n == 'strcmp':
            x, y = self.read_cstr(a0), self.read_cstr(a1); ret = (x > y) - (x < y)
        elif n == 'strcpy':
            u.mem_write(a0, self.read_cstr(a1).encode('latin-1') + b'\0'); ret = a0
        elif n == 'strdup':
            s = self.read_cstr(a0).encode('latin-1') + b'\0'; ret = self.malloc(len(s)); u.mem_write(ret, s)
        elif n in ('fopen', 'open'):
            p = self.read_cstr(a0); self.opened.append(p)
            f = self._file(p, self.read_cstr(a1) if n == 'fopen' else a1)
            if f is None: ret = 0 if n == 'fopen' else 0xffffffff
            elif n == 'fopen': ret = self.alloc(16); self.streams[ret] = [f, len(f) if 'a' in self.read_cstr(a1) else 0, p]
            else: ret = self.next_fd; self.next_fd += 1; self.streams[ret] = [f, 0, p]
        elif n == 'fdopen':
            s = self.streams[a0]; ret = self.alloc(16); self.streams[ret] = [s[0], s[1], s[2]]
        elif n in ('fread', 'read'):
            s = self.streams[a3 if n == 'fread' else a0]
            dst, per, cnt = (a0, a1, a2) if n == 'fread' else (a1, 1, a2)
            k = min(per * cnt, len(s[0]) - s[1])
            u.mem_write(dst, bytes(s[0][s[1]:s[1] + k])) if k else None; s[1] += k; ret = k // per if per else 0
        elif n in ('fwrite', 'write'):
            s = self.streams[a3 if n == 'fwrite' else a0]
            src, per, cnt = (a0, a1, a2) if n == 'fwrite' else (a1, 1, a2)
            data = mem(src, per * cnt)
            s[0][s[1]:s[1] + len(data)] = data; s[1] += len(data); ret = cnt
        elif n in ('fseek', 'lseek'):
            s = self.streams[a0]; off = sint(a1)
            s[1] = {0: off, 1: s[1] + off, 2: len(s[0]) + off}[a2]; ret = 0 if n == 'fseek' else s[1]
        elif n == 'ftell': ret = self.streams[a0][1]
        elif n == 'ftruncate':
            f = self.streams[a0][0]; del f[a1:]; f.extend(bytes(a1 - len(f)))
        elif n == 'feof': ret = int(self.streams[a0][1] >= len(self.streams[a0][0]))
        elif n in ('fclose', 'close'): self.streams.pop(a0, None)
        elif n == 'unlink': self.blobs.pop(self.read_cstr(a0), None)
        elif n == 'access': ret = 0 if self.read_cstr(a0) in self.blobs else 0xffffffff
        elif n == 'qsort':
            size = a2
            items = [mem(a0 + i * size, size) for i in range(a1)]
            ta, tb = self.alloc(size), self.alloc(size)
            def cmp(x, y):
                u.mem_write(ta, x); u.mem_write(tb, y)
                r = self.nested(a3, ta, tb); return r - (1 << 32) if r >= 1 << 31 else r
            for i, it in enumerate(sorted(items, key=functools.cmp_to_key(cmp))): u.mem_write(a0 + i * size, it)
        elif n == 'bsearch':   # (key, base, n, size, cmp): the binary search, the comparison being stock's own routine
            size, lo, hi, cmp = a3, 0, a2, self.word(sp + 16)
            while lo < hi:
                mid = (lo + hi) // 2
                r = self.nested(cmp, a0, a1 + mid * size); r = r - (1 << 32) if r >= 1 << 31 else r
                if r == 0: ret = a1 + mid * size; break
                lo, hi = (mid + 1, hi) if r > 0 else (lo, mid)
        elif n == 'log':
            x = struct.unpack('<d', struct.pack('<Q', u.reg_read(UC_MIPS_REG_F12)))[0]
            u.reg_write(UC_MIPS_REG_F0, struct.unpack('<Q', struct.pack('<d', math.log(x)))[0])
        elif n in ('__udivdi3', '__divdi3', '__moddi3'):
            x, y = a0 | a1 << 32, a2 | a3 << 32
            if n == '__udivdi3': r = x // y
            else:
                x, y = (v - (1 << 64) if v >= 1 << 63 else v for v in (x, y))
                q = abs(x) // abs(y); q = q if (x < 0) == (y < 0) else -q
                r = q if n == '__divdi3' else x - q * y
            r &= (1 << 64) - 1; ret, v1 = r & 0xffffffff, r >> 32
        elif n == 'time': ret = self.wall
        elif n == 'snprintf':   # the engine formats one thing: snprintf(buf, size, "%s", text), the text of a spelling
            if a1 and self.read_cstr(a2) == '%s': u.mem_write(a0, self.read_cstr(a3).encode('latin-1')[:a1 - 1] + b'\0')
            elif a1: u.mem_write(a0, b'\0')
        elif n in ('pthread_mutex_init', 'pthread_mutex_lock', 'pthread_mutex_unlock', 'pthread_mutex_trylock', 'printf', 'puts', 'sprintf', 'usleep', 'sleep', 'gettimeofday'): pass
        else: raise AssertionError(f'unmocked libc call {n} at {address:#x} from {u.reg_read(UC_MIPS_REG_RA):#x}')
        u.reg_write(UC_MIPS_REG_V0, ret & 0xffffffff)
        if v1 is not None: u.reg_write(UC_MIPS_REG_V0 + 1, v1)
        u.reg_write(UC_MIPS_REG_PC, u.reg_read(UC_MIPS_REG_RA))

    def run(self, fn, *args, count=2000000000):
        a = list(args) + [0] * (4 - len(args))
        try: return self.call(fn, a0=a[0], a1=a[1], a2=a[2], a3=a[3], count=count)
        except UcError as e:
            raise AssertionError(f'{e} at pc {self.u.reg_read(UC_MIPS_REG_PC):#x}, ra {self.u.reg_read(UC_MIPS_REG_RA):#x}') from None

    def utf16(self, a):
        """The char16 string at a: its code units and the text."""
        raw = bytes(self.u.mem_read(a, 2 * (CAND_LEN + 1)))
        units = []
        for i in range(0, len(raw), 2):
            c = raw[i] | raw[i + 1] << 8
            if not c: break
            units.append(c)
        return units, ''.join(map(chr, units))

    def open_engine(self, user=USER_PATH):
        return self.run(IM['im_open_decoder'], self.cstr(SYS_PATH), self.cstr(user))

    def search(self, word):
        """im_search(word): the count. The input is the pinyin string (letters and apostrophes) without a terminator."""
        return self.run(IM['im_search'], self.cstr(word), len(word))

    def read(self, n, limit=CANDS):
        """The first `limit` candidates (texts) of the current search, n of them in all."""
        out, got = self.alloc(2 * (CAND_LEN + 1)), []
        for i in range(min(n, limit)):
            self.u.mem_write(out, bytes(2 * (CAND_LEN + 1)))
            if not self.run(IM['im_get_candidate'], i, out, CAND_LEN): break
            got.append(self.utf16(out)[1])
        return got

    def candidates(self, word, limit=CANDS):
        """im_search(word), then im_get_candidate for the first `limit`: (the count, [the text of each])."""
        n = self.search(word)
        return n, self.read(n, limit)

    def choose(self, i):
        """im_choose(i): the candidates left, after which im_get_fixed_len counts the characters fixed so far."""
        return self.run(IM['im_choose'], i)

    def spl(self):
        """im_get_spl_start_pos: (the syllables decoded, [their start offsets in the input string, one more than that: the end])."""
        slot = self.alloc(4)
        n = self.run(IM['im_get_spl_start_pos'], slot)
        at = self.word(slot)
        return n, [struct.unpack('<H', bytes(self.u.mem_read(at + 2 * i, 2)))[0] for i in range(n + 1)]

    def hanzi_spellings(self, ch):
        """The spellings (pinyin, lowercase) the dictionary knows for one character: get_splids_for_hanzi on the DictList (the DictTrie at MatrixSearch +0xc, its +4), then the text of each spelling id."""
        trie = self.word(self.word(ENGINE_PTR) + 0xc)
        dl, spt = self.word(trie + 4), self.word(trie + 8)
        s = self.alloc(4)
        self.u.mem_write(s, ch.encode('utf-16-le') + b'\0\0')
        if not self.run(LEMMA_ID, dl, s, 1): return None   # get_splids_for_hanzi dereferences what its binary search returns, NULL for a character that is not in the dictionary: it must not be called for one
        out = self.alloc(32)
        self.setword(STACK + 16, 8)
        n = self.run(SPLIDS_FOR_HANZI, dl, ord(ch), 0, out)
        ids = struct.unpack('<%dH' % n, bytes(self.u.mem_read(out, 2 * n))) if n else ()
        return [self.read_cstr(self.run(SPELLING_STR, spt, i)).lower() for i in ids]   # the table is upper case ("ZhOU")

    def predicts(self, history, limit=CANDS):
        """MatrixSearch::get_predicts(history): the words that usually follow (1..7 characters of history)."""
        fixed, out = self.alloc(64), self.alloc(16 * limit)
        self.u.mem_write(fixed, history.encode('utf-16-le') + b'\0\0')
        k = self.run(PREDICTS, self.word(ENGINE_PTR), fixed, out, limit)
        return [bytes(self.u.mem_read(out + 16 * i, 16)).decode('utf-16-le').split('\0')[0] for i in range(k)]

    def engine(self):
        """(the object, its inited_ byte) behind the global."""
        eng = self.word(ENGINE_PTR)
        return eng, (self.u.mem_read(eng, 1)[0] if eng else None)


def engine_tests(ctx):
    expect = ctx.expect
    data = open(DICT, 'rb').read()
    stock = open(os.path.join(paths.find_stock(paths.ZIP), 'rootfs', 'release/assets/default/raw/data/gpinyin.dat'), 'rb').read()
    expect(data == stock and len(data) == 1068442 and SYS_PATH == '/release/assets/default/raw/data/gpinyin.dat',
           'the dictionary the keyboard opens is the stock asset, unchanged in the build (1068442 bytes), at the path stock reads its other assets from')

    # 1. the real dictionary
    m = Engine({SYS_PATH: data})
    expect(m.word(ENGINE_PTR) == 0, 'the engine pointer (0xa0a360) is NULL before anything opens the engine (static data)')
    expect(m.open_engine() == 1 and SYS_PATH in m.opened and USER_PATH in m.opened, 'im_open_decoder(dictionary, user path) returns 1, having tried both files')
    eng, inited = m.engine()
    expect(eng and inited == 1, 'it leaves an object whose first byte (inited_) is 1')
    got = {w: m.candidates(w) for w in WORDS}
    expect(got['nihao'][1][:3] == ['你好', '你', '拟'] and got['nihao'][0] == 62, f'"nihao" -> 你好 first of 62 candidates: {got["nihao"]}')
    expect(got['zhongguo'][1][0] == '中国' and got['bokesou'][1][0] == '博客搜' and got['yinyue'][1][0] == '音乐' and got['shanling'][1][0] == '山岭',
           f'"zhongguo" -> 中国, "bokesou" -> 博客搜, "yinyue" -> 音乐, "shanling" -> 山岭: {[got[w][1][:2] for w in WORDS[1:]]}')
    expect('播客' in got['bokesou'][1] and '隐约' in got['yinyue'][1], 'whole-word candidates (播客, 隐约) come among the first eight')
    out = m.alloc(2 * (CAND_LEN + 1))
    m.search('nihao'); m.run(IM['im_get_candidate'], 0, out, CAND_LEN)
    expect(m.utf16(out)[0] == [0x4f60, 0x597d], 'candidates are UTF-16 (char16): 你好 is the code units 0x4f60 0x597d and a zero')
    expect(m.run(IM['im_get_candidate'], 5000, out, CAND_LEN) == 0, 'a candidate number past the list returns NULL')
    m.run(IM['im_reset_search'])
    expect(m.candidates('nihao')[1][0] == '你好', 'after im_reset_search a new search starts clean')

    # 1b. how smart the matching is (the table of docs/modules/keyboard.md)
    top = lambda w, k=3: m.candidates(w, k)[1]
    expect(top('nh') == ['你好', '女孩', '您好'] and top('zg')[:2] == ['这个', '中国'] and top('bjdx')[0] == '北京大学', 'abbreviations (jianpin, the initials only) are matched: nh 你好, zg 这个 中国, bjdx 北京大学')
    expect(top('zhongg')[:2] == ['中国', '中共'] and top('nihaom')[:2] == ['你好吗', '你好'], 'a full syllable followed by an initial is matched: zhongg 中国, nihaom 你好吗')
    expect(top('woxihuantingboke')[0] == '我喜欢听博客' and top('zhongguoren')[0] == '中国人' and top('zhongguorenmin')[0] == '中国人民' and top('beijingdaxue')[0] == '北京大学',
           'a whole sentence of syllables with no separators is one candidate, first: woxihuantingboke 我喜欢听博客 (not 播客), zhongguoren 中国人, beijingdaxue 北京大学')
    expect(top('yinyu')[0] == '阴雨' and top("xi'an")[0] == '西安' and top('xian')[0] == '先', 'a partial last syllable completes (yinyu is yin + yu: 阴雨), an apostrophe splits (xi\'an 西安, xian 先)')
    expect(top('NIHAO') == top('nihao') and top('nihaoo')[0] == '你好哦', 'capitals are read as lowercase; a trailing letter extends the sentence')
    expect('中国' not in m.candidates('zongguo', 8)[1] and top('zongguo')[0] == '总过' and '你好' not in m.candidates('lihao', 8)[1] and top('lihao')[0] == '利好' and top('sanling')[0] == '三菱',
           'no fuzzy matching: z for zh (zongguo) and n for l (lihao) are taken literally (总过, 利好), 中国 and 你好 are not offered')
    # choose(): the first call fixes a prefix, candidate 0 is then the best whole text and the others the rest
    m.search('nihao')
    expect(m.choose(0) == 1 and m.run(IM["im_get_fixed_len"]) == 2 and m.read(1) == ['你好'], 'choosing the whole-input candidate leaves one candidate (the text) and 2 characters fixed')
    m.run(IM['im_reset_search']); m.search('nihao')
    expect(m.choose(2) == 41 and m.run(IM["im_get_fixed_len"]) == 1 and m.read(41, 4) == ['拟好', '号', '浩', '豪'], 'choosing 拟 of nihao fixes 1 character; the list is now 拟好 (the whole text), then the candidates for hao')
    m.run(IM['im_reset_search']); m.search('woxihuantingboke')
    expect(m.choose(1) == 208 and m.run(IM["im_get_fixed_len"]) == 1 and m.read(208, 4) == ['我喜欢听博客', '喜欢', '喜欢听', '系'] and m.choose(0) == 1 and m.run(IM["im_get_fixed_len"]) == 6,
           'a long input can be chosen in steps (我, then the rest as one) until every character is fixed')
    m.run(IM['im_reset_search'])
    # the engine's segmentation of the input (im_get_spl_start_pos): the start of each syllable in the input string, one more for the end. The keyboard shows the pinyin with it and,
    # when a candidate of n characters is taken, keeps the input from sp[n] on
    seg = lambda w: (m.search(w), m.spl())[1]
    expect(seg('nihao') == (2, [0, 2, 5]) and seg('woxihuantingboke') == (6, [0, 2, 4, 8, 12, 14, 16]) and seg('nh') == (2, [0, 1, 2]) and seg('bjdx') == (4, [0, 1, 2, 3, 4]) and seg('zhongg') == (2, [0, 5, 6])
           and seg('nihaom') == (3, [0, 2, 5, 6]) and seg('yinyu') == (2, [0, 3, 5]), 'the segmentation: ni|hao, wo|xi|huan|ting|bo|ke, one syllable per initial (nh, bjdx), zhong|g, a half syllable counts (nihaom), yin|yu')
    expect(seg("xi'an") == (2, [0, 3, 5]) and seg('xian') == (1, [0, 4]) and seg('nihaov') == (2, [0, 2, 5]) and seg('vvv') == (0, [0]) and m.search('vvv') == 0,
           'an apostrophe sits before the next syllable (xi\'an: 2, the second starts at 3), what cannot be read is left out (nihaov: v is past the last syllable), an unreadable input has none and no candidate')
    for w, i, chars in (('nihao', 2, 1), ('woxihuantingboke', 1, 1), ('bjdx', 0, 4), ('woxihuantingboke', 0, 6)):
        m.search(w); n_sp, sp = m.spl(); m.choose(i)
        expect(m.run(IM['im_get_fixed_len']) == chars and m.spl() == (n_sp, sp), f'{w}: choosing candidate {i} fixes {chars} characters and the segmentation stays, so those characters cover the first {chars} syllables (to sp[{chars}] = {sp[chars]})')
        m.run(IM['im_reset_search'])

    # the pinyin of a hanzi (for a library search where "zjl" finds 周杰伦): DictList::get_splids_for_hanzi gives a character's spelling ids, SpellingTrie::get_spelling_str the text of one
    dl, spt = m.word(m.word(m.word(ENGINE_PTR) + 0xc) + 4), m.word(m.word(m.word(ENGINE_PTR) + 0xc) + 8)
    expect(m.word(m.word(m.word(ENGINE_PTR) + 0xc)) == 0x978e74 + 8 and m.word(dl) == 1 and m.word(dl + 4) == spt and m.word(0xa0a370) == spt,
           'the objects are where the code puts them: MatrixSearch +0xc the DictTrie (its vtable), its +4 the DictList (initialised, pointing at the SpellingTrie), +8 the SpellingTrie, which is also the global at 0xa0a370')
    py = lambda s: [[m.hanzi_spellings(c) for c in s]][0]
    expect(py('周杰伦') == [['zhou'], ['jie'], ['lun']], f'周杰伦 is zhou jie lun: {py("周杰伦")}')
    expect(py('你好') == [['ni'], ['hao']] and py('北京大学') == [['bei'], ['jing'], ['da', 'dai'], ['xue']] and py('林俊杰') == [['lin'], ['jun'], ['jie']], f'and 你好, 北京大学 (大: da, dai), 林俊杰 likewise ({py("你好")} {py("北京大学")} {py("林俊杰")})')
    expect(py('行') == [['hang', 'heng', 'xing']], f'a character with several readings gives all of them ({py("行")}; 大 gives da and dai): a search matches a name against any')
    expect(all(m.hanzi_spellings(c) is None for c in 'a㐀鿿ａ') and m.hanzi_spellings('龘') == ['da'] and m.hanzi_spellings('〇') == ['ling'], 'DictList::get_lemma_id says whether a character is in the dictionary (0: not), the check to make before get_splids_for_hanzi, which crashes on one that is not (a Latin letter, a fullwidth letter, a rare Ext A character, an unassigned one)')
    expect(all(s[0] for s in py('周杰伦')) and ''.join(s[0][0] for s in py('周杰伦')) == 'zjl' and ''.join(s[0][0] for s in py('王力宏')) == 'wlh', 'the initials of 周杰伦 are zjl (王力宏: wlh)')

    # predictions after what was typed: MatrixSearch::get_predicts, a member function with no C entry point
    expect(m.predicts('你好')[:3] == ['啊', '吗', '像'] and m.predicts('中国')[:4] == ['人', '队', '特色', '政府'] and m.predicts('我')[:3] == ['们', '的', '国']
           and m.predicts('博客')[:3] == ['圈', '网', '首页'] and m.predicts('北京')[:3] == ['市', '大学', '时间'] and len(m.predicts('你好', 3)) == 3,
           'predictions after 你好 / 中国 / 我 / 博客 / 北京 are the usual next words (啊 吗, 人 队 特色, 们 的, 圈 网, 市 大学); the count is capped by the caller')
    expect(m.predicts('') == [] and m.predicts('一二三四五六七八') == [], 'an empty history, or one longer than 7 characters, predicts nothing')

    # 2. closing, and opening again
    m.run(IM['im_close_decoder'])
    expect(m.word(ENGINE_PTR) == 0, 'im_close_decoder clears the global')
    expect(m.search('nihao') == 0 and m.run(IM['im_get_candidate'], 0, out, CAND_LEN) == 0, 'with no engine im_search returns 0 and im_get_candidate NULL (no crash)')
    expect(m.open_engine() == 1 and m.candidates('nihao')[1][0] == '你好', 'opening again after a close works')
    expect(m.open_engine() == 1 and m.candidates('nihao')[1][0] == '你好', 'opening over an open engine replaces it (stock\'s object is destroyed first)')

    # 3. stock's own state: its init asks for /usr/dict_pinyin.dat, which the rootfs does not have
    rootfs = os.path.join(paths.find_stock(paths.ZIP), 'rootfs')
    expect(not os.path.exists(os.path.join(rootfs, 'usr/dict_pinyin.dat')) and not os.path.exists(os.path.join(rootfs, 'usr/dict')), 'the stock rootfs has neither /usr/dict_pinyin.dat nor /usr/dict')
    m2 = Engine({})
    expect(m2.run(IM['im_open_decoder'], m2.cstr('/usr/dict_pinyin.dat'), m2.cstr('/usr/dict/dict_pinyin_user.dat')) == 0, 'stock\'s open (the missing dictionary) returns 0')
    eng2, inited2 = m2.engine()
    expect(eng2 and inited2 == 0, 'it still leaves an object, never initialised: pointer set, inited_ 0 (what the engine is after stock\'s keyboard was opened)')
    expect(m2.candidates('nihao') == (0, []), 'searching it returns 0 candidates, no crash')
    m2.blobs[SYS_PATH] = bytearray(data)
    expect(m2.open_engine() == 1 and m2.engine()[1] == 1 and m2.candidates('nihao')[1][0] == '你好', 'our open replaces that dead object and works')
    m2.run(IM['im_close_decoder'])
    expect(m2.engine() == (0, None), 'and a close leaves the pointer NULL, as at boot (stock\'s keyboard init opens anew whenever it runs)')

    # 3b. learning: stock's user dictionary path (/usr/dict/dict_pinyin_user.dat) does not exist and cannot be created, so there is none; with a path that can be created the engine makes
    # the file (a 40 byte header) and picking candidates, again and again, still changes no order in this session or after a reopen (try_add_cand0_to_userdict runs, add_lma_to_userdict is never reached)
    m5 = Engine({SYS_PATH: data}, writable=('/tmp/py/',))
    expect(m5.open_engine('/tmp/py/user.dat') == 1 and len(m5.blobs['/tmp/py/user.dat']) == 40 and m5.word(m5.word(ENGINE_PTR) + 0x10) != 0, 'with a creatable user dictionary path the engine makes the file (40 bytes) and keeps a user dictionary object')
    before = m5.candidates('nihao')[1]
    for _ in range(4):
        m5.search('nihao'); m5.choose(2); m5.choose(0); m5.run(IM['im_reset_search'])
    m5.run(0x5c75dc)   # im_flush_cache
    expect(m5.candidates('nihao')[1] == before and len(m5.blobs['/tmp/py/user.dat']) == 40, 'four picks of 拟好 do not re-rank anything and write nothing to the user dictionary file')
    m5.run(IM['im_close_decoder']); m5.open_engine('/tmp/py/user.dat')
    expect(m5.candidates('nihao')[1] == before, 'nor after closing and opening again')
    expect(m.engine()[0] and m.word(m.word(ENGINE_PTR) + 0x10) == 0, 'with the keyboard\'s unreadable user path the engine has no user dictionary object at all (nothing to learn into)')

    # 4. stock's own wrapper (inputmethod_module): init ignores its path argument and opens /usr/dict_pinyin.dat; it returns UTF-8
    this = 0xa10000 - 0x7d44
    m3 = Engine({'/usr/dict_pinyin.dat': data})
    m3.run(0x5bf2d0, this)
    expect(m3.run(0x5bf460, this, m3.cstr('ignored'), 9, 12) == 1 and '/usr/dict_pinyin.dat' in m3.opened and 'ignored' not in m3.opened,
           'inputmethod_module::init(this, path, 9, 12) opens /usr/dict_pinyin.dat and /usr/dict/dict_pinyin_user.dat, whatever path it is given')
    expect(m3.run(0x5bf32c, this, m3.cstr('nihao')) == 42 and m3.word(this + 0x10) == 42, 'the wrapper\'s search keeps at most 42 of the 62 candidates (its max lengths 9 and 12)')
    a = m3.run(0x5bf768, this, 0)
    expect(m3.read_cstr(a).encode('latin-1').decode('utf-8') == '你好', 'the wrapper\'s get_candidate returns the candidate as malloc\'d UTF-8')

    # 5. the work it takes (instruction counts; the device is ~1.2 GHz, a search is a few milliseconds)
    from unicorn import UC_HOOK_CODE
    m4 = Engine({SYS_PATH: data}); cnt = [0]
    m4.u.hook_add(UC_HOOK_CODE, lambda u, a, s, d: cnt.__setitem__(0, cnt[0] + 1))
    m4.open_engine(); opening = cnt[0]
    cnt[0] = 0; m4.search('zhongguo'); searching = cnt[0]
    expect(opening < 300000 and searching < 1000000, f'opening takes {opening} instructions and the heaviest of the searches {searching}: no worker thread is needed')


SECTIONS = [engine_tests]   # tools/check.py runs each as its own task


def run(ctx):
    for s in SECTIONS: s(ctx)
