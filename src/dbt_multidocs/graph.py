"""Turn a merged node universe into the payload the lineage page renders.

Ported from the reference build_lineage.py `build()`, with `pkg` re-pointed at
the merged project id rather than `package_name`, stats aggregated across N
manifests, and stitched edges carried through as a separate list so the page
can draw an inferred link differently from a declared `ref()`.
"""
from __future__ import annotations

from typing import Dict, List, Sequence

from . import layout
from .sql_format import format_sql

SQL_LIMIT = 40000


def _collect_tests(tests: Sequence[dict], nodes: Dict[str, dict]):
    """Group tests by the node they cover. Returns (per-node, per-column, table-level)."""
    per_node: Dict[str, Dict[str, int]] = {}
    per_column: Dict[str, Dict[str, list]] = {}
    table_level: Dict[str, list] = {}
    for v in tests:
        name = (v.get("test_metadata") or {}).get("name", "custom")
        column = v.get("column_name")
        # a test belongs to the model it is attached to; depends_on also lists
        # the models a `relationships` test points *at*, which must not count
        owner = v.get("attached_node")
        targets = [owner] if owner in nodes else [
            d for d in (v.get("depends_on") or {}).get("nodes", []) if d in nodes
        ]
        for dep in targets:
            per_node.setdefault(dep, {})
            per_node[dep][name] = per_node[dep].get(name, 0) + 1
            if column:
                per_column.setdefault(dep, {}).setdefault(column, []).append(name)
            else:
                table_level.setdefault(dep, []).append(name)
    return per_node, per_column, table_level


def _longest_depths(parents: Dict[str, list]) -> Dict[str, int]:
    """depth = length of the longest path from a root, for every key in `parents`.

    Iterative (Kahn) rather than recursive: depth is bounded by the longest
    ancestor chain, and a mesh deep enough to exceed the interpreter's recursion
    limit is a graph we should still be able to draw. A node on a cycle takes its
    depth from whichever parents resolve outside the cycle, and 0 if none do.
    """
    children: Dict[str, list] = {u: [] for u in parents}
    indegree: Dict[str, int] = {u: 0 for u in parents}
    for uid, ps in parents.items():
        for p in ps:
            if p in children:
                children[p].append(uid)
                indegree[uid] += 1

    depth: Dict[str, int] = {}
    queue = [u for u in parents if not indegree[u]]
    head = 0
    # only ever moves forward, so breaking cycles stays linear overall
    cycle_scan = iter(parents)

    while len(depth) < len(parents):
        if head == len(queue):
            # everything left sits on a cycle; cut it at the first unresolved node
            for stuck in cycle_scan:
                if stuck not in depth:
                    queue.append(stuck)
                    break
            else:  # pragma: no cover - len(depth) < len(parents) guarantees one
                break
        uid = queue[head]
        head += 1
        if uid in depth:
            continue
        depth[uid] = max((depth[p] + 1 for p in parents[uid] if p in depth), default=0)
        for c in children[uid]:
            indegree[c] -= 1
            if not indegree[c]:
                queue.append(c)
    return depth


def _sql(text) -> str:
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) > SQL_LIMIT:
        text = text[:SQL_LIMIT] + "\n-- …truncated…"
    return format_sql(text)


def build(merged, stitched_edges=(), title_layers=None, project_labels=None) -> dict:
    nodes = merged.nodes
    owner = merged.owner
    labels = project_labels or {}

    tests, col_tests, model_tests = _collect_tests(merged.tests, nodes)
    test_total = len(merged.tests)

    # ---- edges: declared depends_on, then the inferred cross-project links --- #
    edges: List[list] = []
    inferred: List[list] = []
    parents: Dict[str, list] = {k: [] for k in nodes}
    children: Dict[str, list] = {k: [] for k in nodes}
    seen = set()

    def add(a: str, b: str, is_inferred: bool):
        if a not in nodes or b not in nodes or a == b or (a, b) in seen:
            return
        seen.add((a, b))
        (inferred if is_inferred else edges).append([a, b])
        parents[b].append(a)
        children[a].append(b)

    for uid, v in nodes.items():
        for dep in dict.fromkeys((v.get("depends_on") or {}).get("nodes", [])):
            add(dep, uid, False)
    for a, b in stitched_edges:
        add(a, b, True)

    all_edges = edges + inferred

    # ---- depth (longest path from a root), cycle-safe ---------------------- #
    depth = _longest_depths(parents)

    # ---- projects / lanes -------------------------------------------------- #
    pids = layout.order_projects(sorted({owner[u] for u in nodes}), title_layers)
    packages = [
        {
            "name": pid,
            "label": labels.get(pid) or layout.pretty(pid),
            "color": layout.color_for(i),
            "rank": layout.layer_rank(pid, title_layers),
        }
        for i, pid in enumerate(pids)
    ]
    color_of = {p["name"]: p["color"] for p in packages}

    # ---- node payload ------------------------------------------------------ #
    out_nodes = []
    cross_edges = 0
    for uid, v in nodes.items():
        pid = owner[uid]
        cat_cols = (merged.catalogs.get(uid) or {}).get("columns") or {}
        declared = v.get("columns") or {}
        mine_col_tests = col_tests.get(uid, {})
        cols = []
        for cname in dict.fromkeys(list(declared) + list(cat_cols)):
            cols.append({
                "name": cname,
                "type": (cat_cols.get(cname) or {}).get("type", ""),
                "desc": (declared.get(cname) or {}).get("description", ""),
                "tests": sorted(mine_col_tests.get(cname, [])),
            })
        # a test can name a column that was never declared in the YAML
        for cname, tnames in mine_col_tests.items():
            if not any(c["name"] == cname for c in cols):
                cols.append({"name": cname, "type": "", "desc": "",
                             "tests": sorted(tnames), "undeclared": True})

        xp_in = sum(1 for p in parents[uid] if owner[p] != pid)
        xp_out = sum(1 for c in children[uid] if owner[c] != pid)
        cross_edges += xp_out
        node_tests = tests.get(uid, {})

        sql_source = _sql(v.get("raw_code"))
        sql_compiled = _sql(v.get("compiled_code"))
        out_nodes.append({
            "id": uid,
            "name": v.get("name", ""),
            "pkg": pid,
            "color": color_of[pid],
            "type": v["resource_type"],
            "mat": (v.get("config") or {}).get("materialized", v["resource_type"]),
            "schema": v.get("schema", ""),
            "alias": v.get("alias") or v.get("identifier") or v.get("name", ""),
            "path": v.get("original_file_path", ""),
            "desc": (v.get("description") or "").strip(),
            "tags": list(v.get("tags") or []),
            "depth": depth[uid],
            "parents": parents[uid],
            "children": children[uid],
            "columns": cols,
            "col_count": len(cols),
            "tests": node_tests,
            "test_count": sum(node_tests.values()),
            "xp_in": xp_in,
            "xp_out": xp_out,
            "sql_source": sql_source,
            "sql_compiled": sql_compiled if sql_compiled != sql_source else "",
            "col_tests": sum(1 for c in cols if c["tests"]),
            "model_tests": sorted(model_tests.get(uid, [])),
        })

    rank_of = {p["name"]: p["rank"] for p in packages}
    out_nodes.sort(key=lambda n: (rank_of[n["pkg"]], n["pkg"], n["depth"], n["name"]))

    # ---- project-level rollup: the "how do the projects connect" DAG -------- #
    pkg_edges: Dict[tuple, int] = {}
    for a, b in all_edges:
        pa, pb = owner[a], owner[b]
        if pa != pb:
            pkg_edges[(pa, pb)] = pkg_edges.get((pa, pb), 0) + 1
    pkg_parents = {p["name"]: [] for p in packages}
    for (pa, pb) in pkg_edges:
        pkg_parents[pb].append(pa)
    pkg_depth = _longest_depths(pkg_parents)
    node_counts: Dict[str, int] = {}
    for n in out_nodes:
        node_counts[n["pkg"]] = node_counts.get(n["pkg"], 0) + 1
    for p in packages:
        p["depth"] = pkg_depth[p["name"]]
        p["count"] = node_counts.get(p["name"], 0)
    project_edges = [{"from": a, "to": b, "weight": w}
                     for (a, b), w in sorted(pkg_edges.items(), key=lambda kv: -kv[1])]

    counts: Dict[str, int] = {}
    for n in out_nodes:
        counts[n["type"]] = counts.get(n["type"], 0) + 1

    return {
        "packages": packages,
        "nodes": out_nodes,
        "edges": all_edges,
        "inferred_edges": inferred,
        "project_edges": project_edges,
        "stats": {
            "models": counts.get("model", 0),
            "seeds": counts.get("seed", 0),
            "sources": counts.get("source", 0),
            "tests": test_total,
            "cross_edges": cross_edges,
            "inferred": len(inferred),
            "projects": len(packages),
            "generated_at": _newest(merged),
            "subtitle": _subtitle(merged, len(packages)),
        },
    }


def _newest(merged) -> str:
    stamps = [(m or {}).get("generated_at", "") for m in merged.metadata.values()]
    return max([s for s in stamps if s], default="")


def _subtitle(merged, n_projects: int) -> str:
    versions = sorted({(m or {}).get("dbt_version", "") for m in merged.metadata.values()} - {""})
    adapters = sorted({(m or {}).get("adapter_type", "") for m in merged.metadata.values()} - {""})
    stamp = (_newest(merged) or "")[:16].replace("T", " ")
    return "{} project{} · dbt {} · {} · generated {} UTC".format(
        n_projects,
        "" if n_projects == 1 else "s",
        "/".join(versions) or "?",
        "/".join(adapters) or "?",
        stamp,
    )
