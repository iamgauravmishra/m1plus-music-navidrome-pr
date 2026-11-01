#!/usr/bin/env python3
"""Checked find-and-replace, for changes too mechanical for an editor round trip.

  sub.py FILE OLD NEW [--count N | --all] [--dry-run] [--regex] [--stat]
  sub.py FILE --old-file OLD.txt --new-file NEW.txt ...      (multi-line text from files)
  sub.py FILE [FILE ...] --pairs PAIRS.json [--dry-run] [--regex] [--stat]

OLD must occur exactly N times (default 1; --count N), or any number of times >= 1 with --all.
Otherwise nothing is written and the exit status is 1: not found, or ambiguous (the line numbers of
the occurrences are printed). On success a unified diff of the change is printed (--stat: only the
counts). OLD and NEW are literal text ("\\n" and "\\t" are NOT interpreted; use the files for
multi-line text), unless --regex (re.sub semantics, backslash groups in NEW). Bytes outside the
replaced text are untouched.

Batch: PAIRS.json is a list of {"old": ..., "new": ..., "count": N | "all": true} (count 1 by
default), applied in order to every FILE. A pair must match in each file with its count, except
with "all", which also accepts 0 in a file as long as some file matches. Every file and pair is
checked before anything is written: one failure writes nothing.
"""
import argparse, difflib, json, re, sys

def apply(name, text, old, new, count, every, regex):
    spans = [m.span() for m in re.finditer(old if regex else re.escape(old), text)]
    n = len(spans)
    if every and n == 0: return text, 0
    if n == 0: sys.exit(f'{name}: OLD not found: {old[:60]!r}')
    if not every and n != count:
        lines = [text.count('\n', 0, s) + 1 for s, _ in spans]
        sys.exit(f'{name}: OLD {old[:60]!r} occurs {n} times (want {count}) at lines {lines}; make OLD longer or pass --count/--all')
    return (re.sub(old, new, text) if regex else text.replace(old, new)), n

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('args', nargs='+', metavar='FILE [OLD NEW]')
    ap.add_argument('--old-file'); ap.add_argument('--new-file'); ap.add_argument('--pairs')
    g = ap.add_mutually_exclusive_group(); g.add_argument('--count', type=int, default=1); g.add_argument('--all', action='store_true')
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--regex', action='store_true')
    ap.add_argument('--stat', action='store_true', help='print replacement counts, not the diff')
    a = ap.parse_args()
    if a.pairs:
        files = a.args
        pairs = [(p['old'], p['new'], p.get('count', 1), p.get('all', False)) for p in json.load(open(a.pairs))]
    else:
        files = a.args[:1]; rest = a.args[1:]
        if (a.old_file and a.new_file and not rest) or (not a.old_file and not a.new_file and len(rest) == 2):
            old, new = (open(a.old_file).read(), open(a.new_file).read()) if a.old_file else rest
        else: ap.error('give FILE OLD NEW (or FILE --old-file/--new-file, or FILE... --pairs)')
        pairs = [(old, new, a.count, a.all)]
    if any(not old for old, *_ in pairs): ap.error('OLD is empty')
    texts = {f: open(f, newline='').read() for f in files}
    outs = dict(texts); hits = {}
    for f in files:
        for i, (old, new, count, every) in enumerate(pairs):
            outs[f], n = apply(f, outs[f], old, new, count, every, a.regex)
            hits[i] = hits.get(i, 0) + n
    for i, n in hits.items():
        if n == 0: sys.exit(f'OLD not found in any file: {pairs[i][0][:60]!r}')
    for f in files:
        if a.stat: continue
        diff = ''.join(difflib.unified_diff(texts[f].splitlines(True), outs[f].splitlines(True), f'a/{f}', f'b/{f}', n=2))
        sys.stdout.write(diff or f'{f}: (no change)\n')
    for f in files:
        if not a.dry_run and outs[f] != texts[f]:
            with open(f, 'w', newline='') as fh: fh.write(outs[f])
    total = sum(hits.values()); changed = sum(outs[f] != texts[f] for f in files)
    print(f'{total} replacement(s) in {changed} file(s){" (dry run)" if a.dry_run else ""}')

if __name__ == '__main__': main()
