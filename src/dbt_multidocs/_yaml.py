"""Tiny YAML-subset reader.

The package has no runtime dependencies, so if PyYAML is not importable we fall
back to a parser that understands the slice of YAML this tool actually reads:
nested mappings, lists of scalars, lists of mappings, quoted/unquoted scalars
and `#` comments. That covers `dbt_project.yml`'s top-level keys and our own
config file. Anything fancier (anchors, flow style, multi-line scalars) is only
supported when PyYAML happens to be installed.
"""
from __future__ import annotations

import json
import re

try:  # pragma: no cover - depends on the host environment
    import yaml as _pyyaml
except Exception:  # pragma: no cover
    _pyyaml = None


def _scalar(raw: str):
    s = raw.strip()
    if not s:
        return ""
    if s[0] in "\"'" and len(s) > 1 and s[-1] == s[0]:
        return s[1:-1]
    low = s.lower()
    if low in ("true", "yes"):
        return True
    if low in ("false", "no"):
        return False
    if low in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    if s.startswith("[") and s.endswith("]"):
        try:
            return json.loads(s)
        except ValueError:
            inner = s[1:-1].strip()
            return [_scalar(p) for p in inner.split(",")] if inner else []
    return s


def _strip_comment(line: str) -> str:
    out, in_str, quote = [], False, ""
    for ch in line:
        if in_str:
            out.append(ch)
            if ch == quote:
                in_str = False
        elif ch in "\"'":
            in_str = True
            quote = ch
            out.append(ch)
        elif ch == "#":
            break
        else:
            out.append(ch)
    return "".join(out).rstrip()


def _lines(text: str):
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        body = _strip_comment(raw)
        if body.strip():
            yield len(body) - len(body.lstrip(" ")), body.strip()


def _parse_block(rows, i: int, indent: int):
    """Parse rows[i:] belonging to `indent`; return (value, next_index)."""
    if i >= len(rows):
        return None, i
    if rows[i][1].startswith("- "):
        items = []
        while i < len(rows) and rows[i][0] == indent and rows[i][1].startswith("- "):
            rest = rows[i][1][2:].strip()
            i += 1
            if ":" in rest and not rest.startswith(("\"", "'")):
                # list of mappings: first pair sits on the dash line
                sub = [(indent + 2, rest)]
                while i < len(rows) and rows[i][0] > indent:
                    sub.append((indent + 2, rows[i][1]) if rows[i][0] > indent else rows[i])
                    i += 1
                val, _ = _parse_block(sub, 0, indent + 2)
                items.append(val)
            elif rest:
                items.append(_scalar(rest))
            else:
                val, i = _parse_block(rows, i, rows[i][0]) if i < len(rows) else (None, i)
                items.append(val)
        return items, i

    mapping = {}
    while i < len(rows) and rows[i][0] == indent:
        line = rows[i][1]
        if line.startswith("- "):
            break
        if ":" not in line:
            i += 1
            continue
        key, _, rest = line.partition(":")
        key, rest = key.strip(), rest.strip()
        i += 1
        if rest:
            mapping[key] = _scalar(rest)
        elif i < len(rows) and rows[i][0] > indent:
            mapping[key], i = _parse_block(rows, i, rows[i][0])
        else:
            mapping[key] = None
    return mapping, i


def loads(text: str):
    if _pyyaml is not None:
        return _pyyaml.safe_load(text)
    rows = list(_lines(text))
    if not rows:
        return {}
    value, _ = _parse_block(rows, 0, rows[0][0])
    return value


def load_file(path) -> dict:
    data = loads(path.read_text(encoding="utf8"))
    return data if isinstance(data, dict) else {}
