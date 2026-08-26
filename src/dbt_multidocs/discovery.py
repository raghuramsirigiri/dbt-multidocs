"""Locate dbt projects, wherever they live.

Projects are assumed to be *independent repositories* with no common parent, so
nothing here is derived from the current working directory or from the location
of this package. Every path is resolved to an absolute one up front.
"""
from __future__ import annotations

import dataclasses
import os
import pathlib
import re
from typing import Iterable, List, Optional

from . import _yaml

SKIP_DIRS = {
    "dbt_packages", "target", "logs", ".git", ".venv", "venv", "env",
    "node_modules", "__pycache__", ".tox", "site-packages",
}

DEFAULT_DEPTH = 5


@dataclasses.dataclass
class Project:
    id: str                              # stable key used across the graph
    label: str                           # human label shown in the UI
    root: Optional[pathlib.Path]         # project dir, if we found one
    manifest_path: Optional[pathlib.Path]
    catalog_path: Optional[pathlib.Path]
    project_name: Optional[str]          # `name:` from dbt_project.yml
    origin: str                          # how it was found, for diagnostics

    @property
    def has_manifest(self) -> bool:
        return self.manifest_path is not None and self.manifest_path.exists()

    @property
    def has_catalog(self) -> bool:
        return self.catalog_path is not None and self.catalog_path.exists()


def _read_project_name(root: pathlib.Path) -> Optional[str]:
    cfg = root / "dbt_project.yml"
    if not cfg.exists():
        return None
    try:
        data = _yaml.load_file(cfg)
    except Exception:
        data = {}
    name = data.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    # last resort: the file is malformed for our reader but the key is simple
    m = re.search(r"^\s*name\s*:\s*['\"]?([A-Za-z0-9_]+)", cfg.read_text(encoding="utf8"), re.M)
    return m.group(1) if m else None


def _pretty_label(name: str) -> str:
    s = re.sub(r"^(proj|project|dbt)[_-]", "", name) or name
    return s.replace("_", " ").replace("-", " ").strip() or name


def from_path(path, label: Optional[str] = None,
              origin: str = "--project") -> Project:
    """Accept a project root, a `target/` dir, a manifest.json, or a static index.html."""
    p = pathlib.Path(path).expanduser().resolve()
    root = manifest = catalog = None

    if p.is_file():
        manifest = p
        if p.suffix == ".json":
            sibling = p.with_name("catalog.json")
            catalog = sibling if sibling.exists() else None
        if p.parent.name == "target":
            root = p.parent.parent
    elif p.is_dir():
        if p.name == "target":
            root, target = p.parent, p
        else:
            root, target = p, p / "target"
        for candidate in (target / "manifest.json", root / "manifest.json"):
            if candidate.exists():
                manifest = candidate
                break
        else:
            static = root / "docs" / "index.html"
            manifest = static if static.exists() else target / "manifest.json"
        cand = (manifest.with_name("catalog.json") if manifest else None)
        catalog = cand if cand and cand.exists() else None
    else:
        raise FileNotFoundError(f"no such path: {p}")

    name = _read_project_name(root) if root else None
    pid = name or (root.name if root else p.stem)
    return Project(
        id=pid,
        label=label or _pretty_label(pid),
        root=root,
        manifest_path=manifest,
        catalog_path=catalog,
        project_name=name,
        origin=origin,
    )


def search(root, depth: int = DEFAULT_DEPTH) -> List[Project]:
    """Walk `root` up to `depth` levels looking for dbt_project.yml files."""
    base = pathlib.Path(root).expanduser().resolve()
    found: List[Project] = []
    if not base.is_dir():
        return found
    base_depth = len(base.parts)
    for dirpath, dirnames, filenames in os.walk(base):
        here = pathlib.Path(dirpath)
        level = len(here.parts) - base_depth
        if level >= depth:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if "dbt_project.yml" in filenames:
            found.append(from_path(here, origin=f"--search-root {base}"))
            dirnames[:] = []          # a dbt project does not nest another
    found.sort(key=lambda p: p.id)
    return found


def _dedupe(projects: Iterable[Project]) -> List[Project]:
    seen, out = set(), []
    for p in projects:
        key = str(p.manifest_path or p.root or p.id)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def resolve(paths=(), search_roots=(), depth: int = DEFAULT_DEPTH,
            config: Optional[dict] = None, config_dir=None) -> List[Project]:
    """Build the project list from CLI paths, a config file, then a search sweep."""
    projects: List[Project] = []

    for path in paths or ():
        projects.append(from_path(path))

    for entry in ((config or {}).get("projects") or []):
        if isinstance(entry, str):
            entry = {"path": entry}
        raw = pathlib.Path(str(entry.get("path", "")))
        if not raw.is_absolute() and config_dir:
            raw = pathlib.Path(config_dir) / raw
        proj = from_path(raw, label=entry.get("label"), origin="config")
        if entry.get("id"):
            proj.id = str(entry["id"])
        projects.append(proj)

    for r in search_roots or ():
        projects.extend(search(r, depth))

    if not projects:
        projects.extend(search(pathlib.Path.cwd(), depth))

    projects = _dedupe(projects)

    # ids must be unique - two unrelated repos can share a dbt project name
    counts: dict = {}
    for p in projects:
        counts[p.id] = counts.get(p.id, 0) + 1
    dupes = {k for k, v in counts.items() if v > 1}
    for p in projects:
        if p.id in dupes and p.root is not None:
            p.id = f"{p.id}@{p.root.parent.name}"
            p.label = f"{p.label} ({p.root.parent.name})"
    return projects
