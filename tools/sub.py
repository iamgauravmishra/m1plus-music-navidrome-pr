#!/usr/bin/env python3
"""Checked find-and-replace in one file, for changes too mechanical for an editor round trip.

  sub.py FILE OLD NEW [--count N | --all] [--dry-run] [--regex]
  sub.py FILE --old-file OLD.txt --new-file NEW.txt ...      (multi-line text from files)

OLD must occur exactly N times (default 1; --count N), or any number of times >= 1 with --all.
Otherwise nothing is written and the exit status is 1: not found, or ambiguous (the line numbers of
the occurrences are printed). On success a unified diff of the change is printed. OLD and NEW are
literal text ("\\n" and "\\t" are NOT interpreted; use the files for multi-line text), unless --regex
(re.sub semantics, backslash groups in NEW). Bytes outside the replaced text are untouched.
"""
import argparse, difflib, re, sys

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('file'); ap.add_argument('old', nargs='?'); ap.add_argument('new', nargs='?')
    ap.add_argument('--old-file'); ap.add_argument('--new-file')
    g = ap.add_mutually_exclusive_group(); g.add_argument('--count', type=int, default=1); g.add_argument('--all', action='store_true')
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--regex', action='store_true')
    a = ap.parse_args()
    old = open(a.old_file).read() if a.old_file else a.old
    new = open(a.new_file).read() if a.new_file else a.new
    if old is None or new is None: ap.error('give OLD and NEW (or --old-file/--new-file)')
    if not old: ap.error('OLD is empty')
    text = open(a.file, newline='').read()
    spans = [m.span() for m in re.finditer(old if a.regex else re.escape(old), text)]
    n = len(spans)
    if n == 0: sys.exit(f'{a.file}: OLD not found')
    if (not a.all and n != a.count) or (a.all and n < 1):
        lines = [text.count('\n', 0, s) + 1 for s, _ in spans]
        sys.exit(f'{a.file}: OLD occurs {n} times (want {"at least 1" if a.all else a.count}) at lines {lines}; make OLD longer or pass --count/--all')
    out = re.sub(old, new, text) if a.regex else text.replace(old, new)
    diff = ''.join(difflib.unified_diff(text.splitlines(True), out.splitlines(True), f'a/{a.file}', f'b/{a.file}', n=2))
    sys.stdout.write(diff or '(no change)\n')
    if not a.dry_run and out != text:
        with open(a.file, 'w', newline='') as f: f.write(out)
    print(f'{n} replacement(s){" (dry run)" if a.dry_run else ""}')

if __name__ == '__main__': main()
