"""`dbt docs generate --static` inlines both artifacts into one index.html.

Pulling them back out means finding where each JSON object ends, which is why
artifacts.py scans braces while tracking string state instead of matching a
regex: model SQL is full of braces, and jinja and quoted literals put plenty of
unbalanced ones inside strings.
"""
import json

import pytest

from dbt_multidocs import artifacts, discovery

from conftest import manifest, model

CATALOG = {
    "metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/catalog/v1.json"},
    "nodes": {"model.p.a": {"columns": {"id": {"type": "bigint"}}}},
    "sources": {},
}


def _static_page(doc, catalog=CATALOG, var="var o="):
    """The shape dbt emits: one script assigning {manifest:..., catalog:...}."""
    body = "{}{{manifest:{},catalog:{}}};".format(
        var, json.dumps(doc), json.dumps(catalog) if catalog is not None else "null"
    )
    return "<html><head><script>{}</script></head><body></body></html>".format(body)


def _write(tmp_path, html, name="index.html"):
    path = tmp_path / name
    path.write_text(html, encoding="utf8")
    return path


def test_manifest_and_catalog_come_back_out(tmp_path):
    doc = manifest("p", nodes=[model("p", "a", "s")])
    manifest_out, catalog_out = artifacts.from_static_docs(_write(tmp_path, _static_page(doc)))
    assert manifest_out == doc
    assert catalog_out["nodes"]["model.p.a"]["columns"]["id"]["type"] == "bigint"


def test_braces_inside_model_sql_do_not_end_the_scan(tmp_path):
    """The reason this is a scanner and not a regex."""
    m = model("p", "a", "s")
    # jinja, a lone brace in a string literal, and an escaped quote before one
    m["raw_code"] = (
        "select {{ ref('up') }} , '}' as brace, "
        "'a \\' } quote' as tricky, \"col}\" from t where x = '{'"
    )
    doc = manifest("p", nodes=[m])
    manifest_out, catalog_out = artifacts.from_static_docs(_write(tmp_path, _static_page(doc)))
    assert manifest_out["nodes"]["model.p.a"]["raw_code"] == m["raw_code"]
    # the scan stopped in the right place, so the catalog after it is intact too
    assert catalog_out == CATALOG


def test_a_page_with_no_inlined_manifest_says_so(tmp_path):
    path = _write(tmp_path, "<html><body>just a page</body></html>")
    with pytest.raises(artifacts.ArtifactError) as exc:
        artifacts.from_static_docs(path)
    assert "--static" in str(exc.value)


def test_an_unterminated_object_is_an_error(tmp_path):
    doc = manifest("p", nodes=[model("p", "a", "s")])
    truncated = _static_page(doc)[:-40]          # lop off the closing braces
    with pytest.raises(artifacts.ArtifactError) as exc:
        artifacts.from_static_docs(_write(tmp_path, truncated))
    assert "unbalanced" in str(exc.value)


def test_loading_a_static_page_end_to_end(tmp_path):
    """discovery points at the html, and load() treats it as both artifacts."""
    doc = manifest("p", nodes=[model("p", "a", "s")])
    root = tmp_path / "proj"
    (root / "docs").mkdir(parents=True)
    (root / "dbt_project.yml").write_text("name: p\n", encoding="utf8")
    (root / "docs" / "index.html").write_text(_static_page(doc), encoding="utf8")

    project = discovery.from_path(root)
    assert project.manifest_path.name == "index.html"

    loaded = artifacts.load(project)
    assert loaded.manifest == doc
    assert loaded.catalog_path == project.manifest_path      # the page holds both
    assert loaded.warnings == []                             # so no "missing catalog"


def test_a_static_page_without_a_catalog_still_loads(tmp_path):
    doc = manifest("p", nodes=[model("p", "a", "s")])
    page = "<html><script>var o={{manifest:{}}};</script></html>".format(json.dumps(doc))
    manifest_out, catalog_out = artifacts.from_static_docs(_write(tmp_path, page))
    assert manifest_out == doc
    assert catalog_out == {"nodes": {}, "sources": {}}
