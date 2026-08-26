"""Fold N independent manifests into one node universe.

Ownership rule: a node belongs to the project whose manifest metadata
`project_name` matches the node's `package_name`. Independent repos never
collide, but if a user points the tool at projects that import each other (or
share an installed package) the duplicate copies collapse onto the owning
project instead of appearing once per manifest.
"""
from __future__ import annotations

import dataclasses
from typing import Dict, List

GRAPH_TYPES = {"model", "seed", "snapshot"}


@dataclasses.dataclass
class Merged:
    nodes: Dict[str, dict]           # unique_id -> node (sources get resource_type "source")
    owner: Dict[str, str]            # unique_id -> project id
    tests: List[dict]                # every test node, across all manifests
    catalogs: Dict[str, dict]        # unique_id -> catalog entry
    project_ids: List[str]
    metadata: Dict[str, dict]        # project id -> manifest metadata
    conflicts: List[str]
    orphans: List[str]               # nodes no manifest claimed by project_name


def merge(loaded_list) -> Merged:
    nodes: Dict[str, dict] = {}
    owner: Dict[str, str] = {}
    claimed: Dict[str, bool] = {}          # True once the owning project supplied it
    tests: List[dict] = []
    catalogs: Dict[str, dict] = {}
    metadata: Dict[str, dict] = {}
    conflicts: List[str] = []
    seen_tests = set()

    for loaded in loaded_list:
        pid = loaded.project_id
        project_name = loaded.project_name
        metadata[pid] = loaded.manifest.get("metadata") or {}

        candidates = []
        for uid, v in (loaded.manifest.get("nodes") or {}).items():
            rt = v.get("resource_type")
            if rt == "test":
                if uid not in seen_tests:
                    seen_tests.add(uid)
                    tests.append(v)
                continue
            if rt in GRAPH_TYPES:
                candidates.append((uid, v))
        for uid, v in (loaded.manifest.get("sources") or {}).items():
            candidates.append((uid, dict(v, resource_type="source")))

        for uid, v in candidates:
            is_owner = v.get("package_name") == project_name
            if uid not in nodes:
                nodes[uid] = v
                owner[uid] = pid
                claimed[uid] = is_owner
            elif is_owner and not claimed.get(uid):
                # a later manifest turns out to be the real owner - prefer its copy
                conflicts.append("{}: reassigned from {} to {}".format(uid, owner[uid], pid))
                nodes[uid] = v
                owner[uid] = pid
                claimed[uid] = True
            elif is_owner and claimed.get(uid) and owner[uid] != pid:
                conflicts.append(
                    "{}: claimed by both {} and {}; kept {}".format(
                        uid, owner[uid], pid, owner[uid])
                )

        for uid, entry in (loaded.catalog.get("nodes") or {}).items():
            catalogs.setdefault(uid, entry)
        for uid, entry in (loaded.catalog.get("sources") or {}).items():
            catalogs.setdefault(uid, entry)

    # Nodes no loaded project claimed as its own - typically a single manifest that
    # already carries imported packages (a `--static` bundle, or local dependencies).
    # Attributing them all to the manifest's project would flatten them into one lane,
    # so fall back to their package_name, which is the only project identity they have.
    orphans = sorted(uid for uid, ok in claimed.items() if not ok)
    for uid in orphans:
        pkg = nodes[uid].get("package_name")
        if pkg and pkg not in metadata:
            owner[uid] = pkg

    return Merged(
        nodes=nodes,
        owner=owner,
        tests=tests,
        catalogs=catalogs,
        project_ids=[ld.project_id for ld in loaded_list],
        metadata=metadata,
        conflicts=conflicts,
        orphans=orphans,
    )
