"""A single manifest that already carries several packages (dbt Mesh, or a
`--static` docs bundle) must still split into one lane per package."""
from dbt_multidocs import artifacts, graph, merge

from conftest import manifest, model


def _loaded(pid, doc):
    return artifacts.Loaded(pid, doc, {"nodes": {}, "sources": {}}, None, None, [])


def test_merged_manifest_splits_by_package_name():
    up = model("upstream", "stg_orders", "raw")
    mid = model("midstream", "int_orders", "int", depends=[up["unique_id"]])
    down = model("downstream", "fct_orders", "marts", depends=[mid["unique_id"]])
    doc = manifest("downstream", nodes=[up, mid, down])

    merged = merge.merge([_loaded("downstream", doc)])
    assert merged.owner[up["unique_id"]] == "upstream"
    assert merged.owner[mid["unique_id"]] == "midstream"
    assert merged.owner[down["unique_id"]] == "downstream"

    payload = graph.build(merged)
    assert payload["stats"]["projects"] == 3
    assert payload["stats"]["cross_edges"] == 2
    assert payload["project_edges"] == [
        {"from": "upstream", "to": "midstream", "weight": 1},
        {"from": "midstream", "to": "downstream", "weight": 1},
    ]


def test_declared_refs_need_no_stitching():
    """dbt Mesh style: edges come from depends_on, nothing is inferred."""
    up = model("a", "x", "s")
    down = model("b", "y", "s", depends=[up["unique_id"]])
    payload = graph.build(merge.merge([_loaded("b", manifest("b", nodes=[up, down]))]))
    assert payload["inferred_edges"] == []
    assert payload["stats"]["cross_edges"] == 1
