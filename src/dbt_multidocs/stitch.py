"""Infer the cross-project edges that `depends_on` cannot express.

Independent dbt projects have no shared manifest, so a downstream project's
`source()` and the upstream project's model are two unrelated nodes that happen
to name the same warehouse relation. Matching on that normalized relation key
is what turns N islands into one graph.
"""
from __future__ import annotations

import dataclasses
from typing import Dict, List, Tuple

PRODUCER_TYPES = {"model", "seed", "snapshot"}
_QUOTES = "\"'`[]"
_OPENERS = "\"'`"


@dataclasses.dataclass
class Stitched:
    edges: List[Tuple[str, str]]     # (producer uid, source uid)
    cross: int                       # how many of those cross a project boundary
    warnings: List[str]


def _clean(part: str) -> str:
    return part.strip().strip(_QUOTES).strip().lower()


def _split_relation(relation: str) -> List[str]:
    """Split `"db"."schema"."table"` while ignoring dots inside quotes/brackets."""
    parts: List[str] = []
    buf: List[str] = []
    closer = ""
    for ch in relation:
        if closer:
            if ch == closer:
                closer = ""
            else:
                buf.append(ch)
        elif ch in _OPENERS:
            closer = ch
        elif ch == "[":
            closer = "]"
        elif ch == ".":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    parts.append("".join(buf))
    return [_clean(p) for p in parts if p.strip()]


def relation_key(node: dict):
    """Normalized (database, schema, identifier) for a manifest node."""
    rel = node.get("relation_name")
    if rel:
        parts = _split_relation(rel)
        if len(parts) >= 3:
            return tuple(parts[-3:])
        if len(parts) == 2:
            return ("", parts[0], parts[1])
    ident = node.get("alias") or node.get("identifier") or node.get("name")
    if not ident or not node.get("schema"):
        return None
    return (_clean(node.get("database") or ""), _clean(node["schema"]), _clean(ident))


def stitch(merged, scope: str = "all") -> Stitched:
    """scope "all" also links same-project seed/source pairs; "cross" only crosses projects."""
    producers: Dict[tuple, List[str]] = {}
    for uid, v in merged.nodes.items():
        if v.get("resource_type") not in PRODUCER_TYPES:
            continue
        key = relation_key(v)
        if key:
            producers.setdefault(key, []).append(uid)

    edges: List[Tuple[str, str]] = []
    warnings: List[str] = []
    cross = 0
    for uid, v in sorted(merged.nodes.items()):
        if v.get("resource_type") != "source":
            continue
        key = relation_key(v)
        if not key:
            continue
        hits = producers.get(key)
        if not hits:
            continue
        if len(hits) > 1:
            warnings.append(
                "{}: relation {} is produced by {} models ({}); skipped".format(
                    uid, ".".join(key), len(hits), ", ".join(sorted(hits))
                )
            )
            continue
        producer = hits[0]
        is_cross = merged.owner.get(producer) != merged.owner.get(uid)
        if scope == "cross" and not is_cross:
            continue
        edges.append((producer, uid))
        if is_cross:
            cross += 1
    return Stitched(edges=edges, cross=cross, warnings=warnings)


def _resolve_ref(merged, ref: str):
    """Accept a full unique_id, or `project.name` / `project.source.src.table`."""
    if ref in merged.nodes:
        return ref
    for prefix in ("model.", "seed.", "snapshot.", "source."):
        if (prefix + ref) in merged.nodes:
            return prefix + ref
    tail = ref.split(".")[-1]
    hits = [uid for uid, v in merged.nodes.items() if v.get("name") == tail]
    return hits[0] if len(hits) == 1 else None


def apply_links(merged, edges, links):
    """Apply manual `links:` entries from the config file, after inference."""
    out = list(edges)
    unresolved: List[str] = []
    for link in links or []:
        src, dst = link.get("from"), link.get("to")
        if not src or not dst:
            continue
        a, b = _resolve_ref(merged, str(src)), _resolve_ref(merged, str(dst))
        if not a or not b:
            unresolved.append("{} -> {}".format(src, dst))
            continue
        pair = (a, b)
        if link.get("remove") or link.get("suppress"):
            out = [e for e in out if e != pair]
        elif pair not in out:
            out.append(pair)
    return out, unresolved
