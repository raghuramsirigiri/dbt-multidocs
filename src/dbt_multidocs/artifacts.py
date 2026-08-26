"""Load dbt artifacts for a project: target/manifest.json (+ optional catalog).

Also accepts an `index.html` produced by `dbt docs generate --static`, which
inlines both artifacts. The brace scanner used for that is ported from the
reference build_lineage.py: it tracks string state, so it survives braces that
appear inside SQL strings where a regex would not.
"""
from __future__ import annotations

import dataclasses
import json
import pathlib
import re
from typing import Dict, List, Optional

EMPTY_CATALOG: Dict[str, dict] = {"nodes": {}, "sources": {}}

SUPPORTED_MANIFEST = "v12"
SUPPORTED_CATALOG = "v1"


class ArtifactError(RuntimeError):
    pass


@dataclasses.dataclass
class Loaded:
    project_id: str
    manifest: dict
    catalog: dict
    manifest_path: pathlib.Path
    catalog_path: Optional[pathlib.Path]
    warnings: List[str]

    @property
    def project_name(self) -> str:
        return (self.manifest.get("metadata") or {}).get("project_name") or self.project_id


def _scan_object(s: str, start: int) -> int:
    """Return the index of the '}' closing the JSON object starting at `start`."""
    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(s)):
        ch = s[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
    raise ArtifactError("unbalanced JSON object while scanning static docs")


def from_static_docs(path: pathlib.Path):
    """Pull the manifest/catalog inlined by `dbt docs generate --static`."""
    src = path.read_text(encoding="utf8")
    m = re.search(r"var \w+=\{manifest:", src)
    if not m:
        raise ArtifactError(f"{path} has no inlined manifest (was it built with --static?)")
    mstart = src.index("{", m.end() - 1)
    mend = _scan_object(src, mstart)
    manifest = json.loads(src[mstart:mend + 1])

    catalog = dict(EMPTY_CATALOG)
    c = src.find("catalog:{", mend)
    if c != -1:
        cstart = c + len("catalog:")
        catalog = json.loads(src[cstart:_scan_object(src, cstart) + 1])
    return manifest, catalog


def _schema_version(doc: dict) -> str:
    raw = (doc.get("metadata") or {}).get("dbt_schema_version") or ""
    m = re.search(r"/(v\d+)\.json$", raw)
    return m.group(1) if m else raw


def load(project) -> Loaded:
    """Read the artifacts for a discovery.Project. Raises if the manifest is missing."""
    warnings: List[str] = []
    path = project.manifest_path
    if path is None or not path.exists():
        where = path or (project.root / "target" / "manifest.json" if project.root else "?")
        raise ArtifactError(
            f"{project.id}: no manifest at {where}\n"
            f"  run `dbt docs generate` in {project.root or '<project dir>'} first"
        )

    catalog_path = project.catalog_path
    if path.suffix.lower() in (".html", ".htm"):
        manifest, catalog = from_static_docs(path)
        catalog_path = path
    else:
        manifest = json.loads(path.read_text(encoding="utf8"))
        if catalog_path and catalog_path.exists():
            catalog = json.loads(catalog_path.read_text(encoding="utf8"))
        else:
            catalog = dict(EMPTY_CATALOG)
            catalog_path = None
            warnings.append(
                f"{project.id}: no catalog.json next to {path.name}; "
                f"column data types will be blank"
            )

    mv = _schema_version(manifest)
    if mv and mv != SUPPORTED_MANIFEST:
        warnings.append(
            f"{project.id}: manifest schema {mv} (built and tested against "
            f"{SUPPORTED_MANIFEST}); parsing anyway"
        )
    cv = _schema_version(catalog) if catalog_path else ""
    if cv and cv != SUPPORTED_CATALOG:
        warnings.append(f"{project.id}: catalog schema {cv} (expected {SUPPORTED_CATALOG})")

    return Loaded(
        project_id=project.id,
        manifest=manifest,
        catalog=catalog,
        manifest_path=path,
        catalog_path=catalog_path,
        warnings=warnings,
    )
