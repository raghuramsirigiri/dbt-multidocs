import json

import pytest

from dbt_multidocs import artifacts, discovery, graph, merge, render, stitch

from conftest import manifest, model, source, write_project


def _loaded(pid, doc, catalog=None):
    return artifacts.Loaded(pid, doc, catalog or {"nodes": {}, "sources": {}}, None, None, [])


def test_owner_wins_over_first_sighting():
    """A node imported as a package must be attributed to the project that defines it."""
    shared = model("up", "dim_customers", "main_core")
    downstream = manifest("down", nodes=[shared, model("down", "rpt", "main_rpt")])
    upstream = manifest("up", nodes=[shared])

    # downstream is loaded first and carries a copy of upstream's node
    merged = merge.merge([_loaded("down", downstream), _loaded("up", upstream)])
    assert merged.owner["model.up.dim_customers"] == "up"
    assert merged.owner["model.down.rpt"] == "down"
    assert len(merged.nodes) == 2                     # deduped, not doubled
    assert merged.orphans == []
    assert any("reassigned" in c for c in merged.conflicts)


def test_unclaimed_node_becomes_an_orphan():
    doc = manifest("down", nodes=[model("other", "x", "s")])
    merged = merge.merge([_loaded("down", doc)])
    assert merged.orphans == ["model.other.x"]
    # no loaded project owns it, so it keeps its package_name as its lane
    assert merged.owner["model.other.x"] == "other"


def test_tests_attach_to_their_own_model_not_the_relationship_target():
    doc = manifest("p", nodes=[model("p", "a", "s"), model("p", "b", "s")])
    doc["nodes"]["test.p.rel"] = {
        "unique_id": "test.p.rel",
        "resource_type": "test",
        "package_name": "p",
        "test_metadata": {"name": "relationships"},
        "column_name": "id",
        "attached_node": "model.p.a",
        # depends_on names the model the test points *at* as well
        "depends_on": {"nodes": ["model.p.a", "model.p.b"]},
    }
    payload = graph.build(merge.merge([_loaded("p", doc)]))
    by_id = {n["id"]: n for n in payload["nodes"]}
    assert by_id["model.p.a"]["test_count"] == 1
    assert by_id["model.p.b"]["test_count"] == 0


def test_depth_is_cycle_safe():
    """A cyclic graph must terminate with finite depths rather than recursing forever."""
    a = model("p", "a", "s", depends=["model.p.b"])
    b = model("p", "b", "s", depends=["model.p.a"])
    payload = graph.build(merge.merge([_loaded("p", manifest("p", nodes=[a, b]))]))
    depths = [n["depth"] for n in payload["nodes"]]
    assert len(depths) == 2
    assert all(isinstance(d, int) and 0 <= d < len(depths) + 1 for d in depths)


def test_a_deep_chain_does_not_hit_the_recursion_limit():
    """Depth is bounded by the longest chain, which can exceed Python's stack.

    The manifest order matters: dbt does not emit nodes parents-first, and a
    chain listed leaves-first is what used to recurse once per link.
    """
    chain = [model("p", "m{}".format(i), "s",
                   depends=["model.p.m{}".format(i - 1)] if i else [])
             for i in reversed(range(2000))]
    payload = graph.build(merge.merge([_loaded("p", manifest("p", nodes=chain))]))
    assert max(n["depth"] for n in payload["nodes"]) == 1999


def test_undeclared_column_from_a_test_is_flagged():
    m = model("p", "a", "s")
    m["columns"] = {"declared": {"description": "d"}}
    doc = manifest("p", nodes=[m])
    doc["nodes"]["test.p.t"] = {
        "unique_id": "test.p.t", "resource_type": "test", "package_name": "p",
        "test_metadata": {"name": "not_null"}, "column_name": "ghost",
        "attached_node": "model.p.a", "depends_on": {"nodes": ["model.p.a"]},
    }
    payload = graph.build(merge.merge([_loaded("p", doc)]))
    cols = {c["name"]: c for c in payload["nodes"][0]["columns"]}
    assert cols["ghost"]["undeclared"] is True
    assert "undeclared" not in cols["declared"]


def test_missing_catalog_degrades_to_blank_types(tmp_path):
    doc = manifest("p", nodes=[model("p", "a", "s")])
    root = write_project(tmp_path / "p", "p", doc, catalog=None)
    project = discovery.from_path(root)
    loaded = artifacts.load(project)
    assert loaded.catalog_path is None
    assert any("no catalog.json" in w for w in loaded.warnings)


def test_missing_manifest_is_a_clear_error(tmp_path):
    root = tmp_path / "p"
    root.mkdir()
    (root / "dbt_project.yml").write_text("name: p\n", encoding="utf8")
    with pytest.raises(artifacts.ArtifactError) as exc:
        artifacts.load(discovery.from_path(root))
    assert "dbt docs generate" in str(exc.value)


def test_inferred_edges_are_kept_separate_and_counted(two_repos):
    projects = [discovery.from_path(p) for p in two_repos]
    merged = merge.merge([artifacts.load(p) for p in projects])
    inferred = stitch.stitch(merged).edges
    payload = graph.build(merged, stitched_edges=inferred)
    assert payload["inferred_edges"] == [
        ["model.up.dim_customers", "source.down.core.dim_customers"]
    ]
    assert payload["stats"]["inferred"] == 1
    assert payload["stats"]["cross_edges"] == 1
    assert [p["name"] for p in payload["packages"]] == ["up", "down"] or \
           {p["name"] for p in payload["packages"]} == {"up", "down"}
    # the project rollup shows the chain
    assert payload["project_edges"] == [{"from": "up", "to": "down", "weight": 1}]


def test_payload_cannot_close_the_host_script_tag():
    m = model("p", "a", "s")
    m["raw_code"] = "select 1 -- </script><script>alert(1)</script>"
    html, _, _, _ = render.render(
        graph.build(merge.merge([_loaded("p", manifest("p", nodes=[m]))])), "T")
    body = html.split('id="graph-data"', 1)[1].split("</script>", 1)[0]
    assert "</script" not in body
    assert "<\\/script" in body
    assert json.loads(body.split(">", 1)[1].replace("<\\/", "</"))["nodes"]
