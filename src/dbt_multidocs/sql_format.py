"""A small, conservative SQL pretty-printer.

The models in this repo are written as one-liners, so the docs need to break
them up. This is deliberately not a parser: it tokenises, then inserts newlines
in front of the clause keywords that are at paren depth 0, indents the bodies,
and leaves everything else — identifiers, casing, jinja tags, literals —
byte-for-byte alone. If anything looks off, the caller keeps the original.
"""
from __future__ import annotations

import re

# clause keywords that start a new line at depth 0
CLAUSE = [
    "select distinct", "select", "from", "where", "group by", "order by",
    "having", "limit", "offset", "qualify", "window",
    "union all", "union", "intersect", "except",
    "inner join", "left outer join", "right outer join", "full outer join",
    "left join", "right join", "full join", "cross join", "lateral join", "join",
]
# keywords that start a new *indented* line at depth 0
SUBCLAUSE = ["on", "and", "or", "when", "else", "using"]

TOKEN = re.compile(
    r"""
      (?P<jinja>\{\{.*?\}\}|\{%.*?%\}|\{\#.*?\#\})   # jinja first: it may contain anything
    | (?P<comment>--[^\n]*|/\*.*?\*/)
    | (?P<string>'(?:[^']|'')*'|"(?:[^"]|"")*"|`[^`]*`)
    | (?P<word>[A-Za-z_][A-Za-z_0-9$]*)
    | (?P<ws>\s+)
    | (?P<other>.)
    """,
    re.X | re.S,
)

MAX_INLINE = 72          # keep short SELECT lists on one line
INDENT = "    "


def _tokenise(sql: str):
    for m in TOKEN.finditer(sql):
        yield m.lastgroup, m.group()


def format_sql(sql: str) -> str:
    """Return `sql` broken across lines. Falls back to the input on any doubt."""
    if not sql or not sql.strip():
        return sql or ""
    if "\n" in sql.strip():
        return sql.strip()          # already formatted by hand — respect it

    try:
        toks = [(k, t) for k, t in _tokenise(sql.strip()) if k != "ws" or t]
    except Exception:
        return sql

    # collapse whitespace tokens to a single space
    toks = [(k, " " if k == "ws" else t) for k, t in toks]

    out: list[str] = []       # finished lines
    cur: list[str] = []       # current line pieces
    depth = 0
    indent = 0
    i = 0

    def flush():
        nonlocal cur
        line = "".join(cur).strip()
        if line:
            out.append(INDENT * indent + line)
        cur = []

    def peek_phrase(idx: int, phrase: str) -> int:
        """If the token stream at idx spells `phrase`, return the token count."""
        want = phrase.split()
        j, seen = idx, 0
        while j < len(toks) and seen < len(want):
            k, t = toks[j]
            if k == "ws":
                j += 1
                continue
            if k != "word" or t.lower() != want[seen]:
                return 0
            seen += 1
            j += 1
        return j - idx if seen == len(want) else 0

    while i < len(toks):
        kind, tok = toks[i]

        if kind == "other":
            if tok in "([":
                depth += 1
            elif tok in ")]":
                depth -= 1
            elif tok == "," and depth == 0:
                # break select/group lists, but only if the line has grown
                cur.append(tok)
                if len("".join(cur)) > MAX_INLINE:
                    flush()
                    i += 1
                    continue
                i += 1
                continue
            cur.append(tok)
            i += 1
            continue

        if kind == "word" and depth == 0:
            low = tok.lower()
            hit = next((c for c in CLAUSE if c.split()[0] == low and peek_phrase(i, c)), None)
            if hit:
                n = peek_phrase(i, hit)
                flush()
                indent = 0
                out.append(" ".join(t for k, t in toks[i:i + n] if k != "ws"))
                indent = 1
                i += n
                continue
            sub = next((c for c in SUBCLAUSE if c == low), None)
            if sub and out:
                flush()
                cur.append(tok)
                i += 1
                continue

        cur.append(tok)
        i += 1

    flush()
    text = "\n".join(l.rstrip() for l in out if l.strip())
    # a clause keyword line followed by its body reads better joined when short
    text = re.sub(r"\n +", lambda m: "\n" + m.group()[1:], text)
    return text if text.strip() else sql
