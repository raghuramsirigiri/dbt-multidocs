"""Synthetic manifests. No dbt install and no warehouse are needed to run these."""
from __future__ import annotations

import json
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))


def relation(db, schema, ident):
    return '"{}"."{}"."{}"'.format(db, schema, ident)


def model(project, name, schema, depends=(), database="analytics", alias=None):
    ident = alias or name
    return {
        "unique_id": "model.{}.{}".format(project, name),
        "name": name,
        "alias": ident,
        "resource_type": "model",
        "package_name": project,
        "database": database,
        "schema": schema,
        "relation_name": relation(database, schema, ident),
        "depends_on": {"nodes": list(depends)},
        "config": {"materialized": "table"},
        "columns": {},
        "tags": [],
        "raw_code": "select 1 as id",
        "original_file_path": "models/{}.sql".format(name),
        "description": "",
    }


def source(project, source_name, table, schema, database="analytics"):
    return {
        "unique_id": "source.{}.{}.{}".format(project, source_name, table),
        "name": table,
        "identifier": table,
        "source_name": source_name,
        "resource_type": "source",
        "package_name": project,
        "database": database,
        "schema": schema,
        "relation_name": relation(database, schema, table),
        "columns": {},
        "tags": [],
        "description": "",
    }


def manifest(project, nodes=(), sources=()):
    return {
        "metadata": {
            "project_name": project,
            "dbt_version": "1.12.3",
            "adapter_type": "duckdb",
            "generated_at": "2026-01-01T00:00:00Z",
            "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json",
        },
        "nodes": {n["unique_id"]: n for n in nodes},
        "sources": {s["unique_id"]: s for s in sources},
    }


def write_project(root: pathlib.Path, project: str, doc: dict, catalog: dict = None):
    """Lay out a project on disk the way dbt does, so discovery can find it."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "dbt_project.yml").write_text(
        "name: {}\nversion: '1.0.0'\nprofile: {}\n".format(project, project), encoding="utf8"
    )
    target = root / "target"
    target.mkdir(exist_ok=True)
    (target / "manifest.json").write_text(json.dumps(doc), encoding="utf8")
    if catalog is not None:
        (target / "catalog.json").write_text(json.dumps(catalog), encoding="utf8")
    return root


def loaded(pid, doc, catalog=None):
    """An artifacts.Loaded built straight from a synthetic manifest."""
    from dbt_multidocs import artifacts

    return artifacts.Loaded(pid, doc, catalog or artifacts.empty_catalog(), None, None, [])


@pytest.fixture
def two_repos(tmp_path):
    """Two *unrelated* directories: upstream produces what downstream sources."""
    up = manifest("up", nodes=[model("up", "dim_customers", "main_core")])
    down = manifest(
        "down",
        nodes=[model("down", "rpt_customers", "main_rpt",
                     depends=["source.down.core.dim_customers"])],
        sources=[source("down", "core", "dim_customers", "main_core")],
    )
    a = write_project(tmp_path / "somewhere" / "repo_up", "up", up, {"nodes": {}, "sources": {}})
    b = write_project(tmp_path / "elsewhere" / "repo_down", "down", down,
                      {"nodes": {}, "sources": {}})
    return a, b


@pytest.fixture(params=["fallback", "pyyaml"])
def yaml_parser(request, monkeypatch):
    """Run a test against both YAML readers.

    The package has no runtime dependencies, so it reads YAML with its own
    parser whenever PyYAML is not importable - but dbt-core depends on PyYAML,
    so most real users are on the *other* branch. Neither is hypothetical, and
    a test that only covers whichever one happens to be installed proves half
    of what it looks like it proves.
    """
    from dbt_multidocs import _yaml

    if request.param == "fallback":
        monkeypatch.setattr(_yaml, "_pyyaml", None)
    else:
        pyyaml = pytest.importorskip("yaml", reason="PyYAML is not installed")
        monkeypatch.setattr(_yaml, "_pyyaml", pyyaml)
    return request.param
