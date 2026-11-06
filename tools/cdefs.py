#!/usr/bin/env python3
"""Integer #define constants of a C file, for the Python tools and tests (patch/offsets.inc, patch/folders.c, ...).

  defines(path, names=None, known=None, strings=False) -> {name: int}
  parse(text, names=None, source, known=None, strings=False)   the same for text already read

Continuation lines (a trailing backslash) are spliced first, as the C preprocessor does; /* */ comments (also
across lines) and // comments are dropped. A value is an integer expression: decimal, hex and octal literals with
u/l suffixes, parentheses, unary - + ~, binary * / % + - << >> & | and names of earlier defines, evaluated with an
ast walker (no eval) under C's rules for the 32-bit MIPS target: division truncates toward zero, an unsigned operand
makes the result unsigned int, which wraps at 32 bits (~0u >> 24 is 255). Function-like macros, conditionals, ll
literals and anything else that is not such an expression are skipped silently. A name given in names that is not such a define raises CDefError naming
the file and the names.

known: {name: int} of defines made elsewhere (another header or the tool) that the file's expressions use; they are
not returned. strings=True also returns a define that is one C string literal, as its text between the quotes (no
escapes are decoded); the default skips them.
"""
import ast, operator, re

COMMENT = re.compile(r'"(?:\\.|[^"\\\n])*"|/\*.*?\*/|//[^\n]*', re.S)   # strings are kept, comments become a space
LITERAL = re.compile(r'\b(0[xX][0-9a-fA-F]+|\d+)([uUlL]*)\b')
DEFINE = re.compile(r'^[ \t]*#[ \t]*define[ \t]+(\w+)([^\n]*)$', re.M)
STRING = re.compile(r'"[^"]*"')


class CDefError(Exception):
    pass


class _Skip(Exception):
    """The value is not an integer expression of earlier defines."""


def _cdiv(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def _cmod(a, b):
    return a - b * _cdiv(a, b)


BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: _cdiv, ast.Mod: _cmod,
          ast.LShift: operator.lshift, ast.RShift: operator.rshift, ast.BitOr: operator.or_, ast.BitAnd: operator.and_}
UNARY = {ast.USub: operator.neg, ast.UAdd: operator.pos, ast.Invert: operator.invert}
INT_MAX, UINT_MAX = 0x7fffffff, 0xffffffff   # MIPS o32: int and long are 32 bits


def _literal(m):
    """A literal as a name the ast walker types: __U<n> for unsigned int, __I<n> for int (C's rules for a 32-bit target)."""
    s, suffix = m.group(1), m.group(2).lower()
    if 'll' in suffix: raise _Skip   # long long: not modelled
    n = int(s, 16) if s[:2].lower() == '0x' else int(s, 8) if len(s) > 1 and s[0] == '0' else int(s)
    if 'u' in suffix or (n > INT_MAX and s[0] == '0'):   # a hex or octal literal past INT_MAX is unsigned
        if n > UINT_MAX: raise _Skip
        return f'__U{n}'
    if n > INT_MAX: raise _Skip   # a decimal past INT_MAX is long long
    return f'__I{n}'


def _int(v, unsigned):
    """v as the 32-bit C int (two's complement, as gcc wraps) or unsigned int it is."""
    v &= UINT_MAX
    return (v, True) if unsigned else (v - (v > INT_MAX) * (UINT_MAX + 1), False)


def _eval(node, env):
    """(value, unsigned) of an expression: an unsigned operand makes a pair unsigned, a shift keeps its left
    operand's type."""
    if isinstance(node, ast.Name):
        if node.id in env: return env[node.id]
        if node.id[:3] in ('__U', '__I') and node.id[3:].isdigit(): return int(node.id[3:]), node.id[2] == 'U'
    elif isinstance(node, ast.BinOp) and type(node.op) in BINARY:
        (a, ua), (b, ub) = _eval(node.left, env), _eval(node.right, env)
        shift = isinstance(node.op, (ast.LShift, ast.RShift))
        u = ua if shift else ua or ub
        if u and not shift: b &= UINT_MAX
        return _int(BINARY[type(node.op)](a & UINT_MAX if u else a, b), u)
    elif isinstance(node, ast.UnaryOp) and type(node.op) in UNARY:
        v, u = _eval(node.operand, env)
        return _int(UNARY[type(node.op)](v), u)
    raise _Skip


def _value(text, env):
    """(value, unsigned) of a define's text, or None if it is not an integer expression (a string, a call ...)."""
    try:
        return _eval(ast.parse(LITERAL.sub(_literal, text.strip()), mode='eval').body, env)
    except (SyntaxError, _Skip, ValueError, ZeroDivisionError):
        return None


def parse(text, names=None, source='<text>', known=None, strings=False):
    """The integer defines of C source text (see the module doc). With names, only those, in that order."""
    text = COMMENT.sub(lambda m: m.group(0) if m.group(0)[0] == '"' else ' ', re.sub(r'\\[ \t]*\r?\n', '', text))
    env = {k: (v, v > INT_MAX) for k, v in (known or {}).items()}
    found = {}
    for m in DEFINE.finditer(text):
        if m.group(2).startswith('('): continue   # function-like macro: "#define F(x)" has no space before "("
        body = m.group(2).strip()
        if strings and STRING.fullmatch(body):
            found[m.group(1)] = body[1:-1]
            continue
        value = _value(body, env) if body else None
        if value is not None:
            env[m.group(1)] = value
            found[m.group(1)] = value[0]
    if names is None: return found
    missing = [n for n in names if n not in found]
    if missing: raise CDefError(f'{source}: no {"integer or string" if strings else "integer"} #define for {", ".join(missing)}')
    return {n: found[n] for n in names}


def defines(path, names=None, known=None, strings=False):
    """The integer defines of a C file (see the module doc); names, if given, must all be among them."""
    with open(path, encoding='utf-8') as f:
        return parse(f.read(), names, source=path, known=known, strings=strings)
