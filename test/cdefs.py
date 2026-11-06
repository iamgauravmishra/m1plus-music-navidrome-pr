#!/usr/bin/env python3
"""tools/cdefs.py: the shared #define reader (continuations, comments, literals, expressions, missing names) and its
agreement with the constants test/pod/harness.py reads from patch/offsets.inc.

  uv run python -I test/cdefs.py
"""
import os, sys, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'tools')); sys.path.insert(0, os.path.join(ROOT, 'test', 'pod'))
import cdefs   # noqa: E402

ok = fail = 0


def expect(name, cond):
    global ok, fail
    if cond: ok += 1
    else: fail += 1; print(f'FAIL {name}')


def raises(fn, *args):
    try: fn(*args)
    except cdefs.CDefError as e: return str(e)
    return None


def main():
    d = cdefs.parse('#define FO_STAT_MAX \\\n    (3 + \\\n     1)\n#define AFTER 5\n')
    expect('backslash continuation joins a split define', d == {'FO_STAT_MAX': 4, 'AFTER': 5})

    d = cdefs.parse('/* a comment\n#define HIDDEN 9\n */\n#define SHOWN 2 /* a\n  two-line comment */\n')
    expect('multi-line comment hides its defines and is dropped after a value', d == {'SHOWN': 2})

    d = cdefs.parse('#define A 0x10u // the trailing comment\n#define B 7L /* block */\n#define C 3 // a\\\n#define D 4\n')
    expect('trailing // and /* */ comments are dropped', d['A'] == 16 and d['B'] == 7)
    expect('a // comment ending in a backslash continues like C', 'D' not in d and d['C'] == 3)

    d = cdefs.parse('#define H 0xFFFFFFFFu\n#define L 10UL\n#define N -0x10\n#define O 010\n#define P -  5\n')
    expect('hex, u/U/l/L suffixes, negative, octal', d == {'H': 0xFFFFFFFF, 'L': 10, 'N': -16, 'O': 8, 'P': -5})

    d = cdefs.parse('#define A 4\n#define B ((A << 2) | 1) + 3\n#define C (-7 / 2) * 10 + (-7 % 3)\n#define D ~A & 0xff\n')
    expect('expression of earlier names, C truncating / and %', d == {'A': 4, 'B': 20, 'C': -31, 'D': 0xfb})

    d = cdefs.parse('#define M (~0u >> 24)\n#define W (0u - 1)\n#define S (-1 >> 4)\n#define H (0xffffffff >> 28)\n'
                    '#define K (M << 28)\n#define B (1 << 31)\n#define LL 1ull\n#define D 3000000000\n')
    expect('int and unsigned int wrap at 32 bits; a hex literal past INT_MAX is unsigned; ll and over-long decimals are skipped',
           d == {'M': 255, 'W': 0xffffffff, 'S': -1, 'H': 15, 'K': 0xf0000000, 'B': -(1 << 31)})

    d = cdefs.parse('#define N 0x12\\\n34\n#define P "/mnt/\\\nmmc"\n', strings=True)
    expect('a backslash-newline splices with nothing in between', d == {'N': 0x1234, 'P': '/mnt/mmc'})

    expect('a later name is not visible to an earlier define', 'Y' not in cdefs.parse('#define Y X\n#define X 1\n'))

    d = cdefs.parse('#define F(x) ((x) + 1)\n#define S "text"\n#define T (uint32_t)4\n#define U MISSING + 1\n#define E\n#define Z 1 / 0\n#define OK 2\n')
    expect('function-like, string, cast, unknown-name, empty and divide-by-zero defines are skipped silently', d == {'OK': 2})

    d = cdefs.parse('#define A 1\n#define B 2\n', names=['B', 'A'])
    expect('names selects, in the order given', list(d.items()) == [('B', 2), ('A', 1)])

    msg = raises(cdefs.parse, '#define A 1\n', ['A', 'MISSING', 'ALSO'], 'patch/x.inc')
    expect('a missing name raises CDefError naming the source and the names',
           msg == 'patch/x.inc: no integer #define for MISSING, ALSO')

    d = cdefs.parse('#define ROW POD_ROW_H /* a seed */\n#define ICON_Y ((ROW - 24) / 2)\n', known={'POD_ROW_H': 52})
    expect('known seeds feed expressions and are not returned', d == {'ROW': 52, 'ICON_Y': 14})

    d = cdefs.parse('#define PATH "/mnt/x.dat" /* "1" */\n#define BIG \\\n    "/a/b"\n#define N 3\n#define W "a" "b"\n', strings=True)
    expect('strings=True returns the text of one string literal, joined across continuations', d == {'PATH': '/mnt/x.dat', 'BIG': '/a/b', 'N': 3})
    expect('strings are skipped by default', 'PATH' not in cdefs.parse('#define PATH "/x"\n'))
    msg = raises(cdefs.parse, '#define PATH "/x"\n', ['PATH'], 'patch/x.h', None, True)
    expect('a string name with strings=True is found', msg is None)

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, 'c.inc')
        with open(path, 'w', encoding='utf-8') as f: f.write('#define K 0x20\n#define S "no"\n')
        expect('defines() reads a file', cdefs.defines(path) == {'K': 0x20})
        msg = raises(cdefs.defines, path, ['S'])
        expect('defines() names the file for a non-integer name', msg is not None and path in msg and 'S' in msg)

    import harness   # noqa: E402  (harness.O: the offsets the mocks use, read by the regex this reader replaces)
    got = cdefs.defines(os.path.join(ROOT, 'patch', 'offsets.inc'))
    diff = [k for k, v in harness.O.items() if got.get(k) != v]
    expect(f'every harness.O key has the same value ({len(harness.O)} keys; differs: {diff[:5]})', not diff)
    print(f'info: cdefs finds {len(got)} integer defines in offsets.inc; harness.O has {len(harness.O)}')

    print(f'{ok} passed, {fail} failed')
    sys.exit(1 if fail else 0)


if __name__ == '__main__':
    main()
