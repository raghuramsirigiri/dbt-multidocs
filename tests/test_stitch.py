from dbt_multidocs import artifacts, discovery, merge, stitch

from conftest import manifest, model, source


def _merged(*pairs):
    """pairs: (project_id, manifest dict)"""
    loaded = [
        artifacts.Loaded(pid, doc, {"nodes": {}, "sources": {}}, None, None, [])
        for pid, doc in pairs
    ]
    return merge.merge(loaded)


def test_relation_key_normalizes_quotes_and_case():
    key = stitch.relation_key({"relation_name": '"Analytics"."Main_Core"."Dim_Customers"'})
    assert key == ("analytics", "main_core", "dim_customers")
    assert stitch.relation_key({"relation_name": "[db].[dbo].[Fact]"}) == ("db", "dbo", "fact")


def test_relation_key_falls_back_to_fields():
    node = {"database": "DB", "schema": "Sch", "alias": "Tbl"}
    assert stitch.relation_key(node) == ("db", "sch", "tbl")
    assert stitch.relation_key({"name": "x"}) is None


def test_two_part_relation():
    assert stitch.relation_key({"relation_name": '"main"."t"'}) == ("", "main", "t")


def test_cross_project_edge_is_inferred(two_repos):
    projects = [discovery.from_path(p) for p in two_repos]
    merged = merge.merge([artifacts.load(p) for p in projects])
    result = stitch.stitch(merged)
    assert result.edges == [("model.up.dim_customers", "source.down.core.dim_customers")]
    assert result.cross == 1
    assert result.warnings == []


def test_same_project_match_skipped_in_cross_scope():
    doc = manifest(
        "solo",
        nodes=[model("solo", "raw_orders", "main_raw")],
        sources=[source("solo", "raw", "raw_orders", "main_raw")],
    )
    merged = _merged(("solo", doc))
    assert stitch.stitch(merged, scope="all").edges == [
        ("model.solo.raw_orders", "source.solo.raw.raw_orders")
    ]
    assert stitch.stitch(merged, scope="cross").edges == []


def test_ambiguous_relation_is_skipped_with_a_warning():
    a = manifest("a", nodes=[model("a", "dupe", "main_core")])
    b = manifest("b", nodes=[model("b", "dupe", "main_core")],
                 sources=[source("b", "core", "dupe", "main_core")])
    merged = _merged(("a", a), ("b", b))
    result = stitch.stitch(merged)
    assert result.edges == []
    assert len(result.warnings) == 1
    assert "produced by 2 models" in result.warnings[0]


def test_config_links_add_and_suppress():
    a = manifest("a", nodes=[model("a", "orders", "custom_schema")])
    b = manifest("b", sources=[source("b", "up", "orders", "other_schema")])
    merged = _merged(("a", a), ("b", b))
    assert stitch.stitch(merged).edges == []          # schemas differ, nothing inferred

    edges, unresolved = stitch.apply_links(
        merged, [], [{"from": "model.a.orders", "to": "source.b.up.orders"}]
    )
    assert edges == [("model.a.orders", "source.b.up.orders")]
    assert unresolved == []

    edges, _ = stitch.apply_links(
        merged, edges,
        [{"from": "model.a.orders", "to": "source.b.up.orders", "remove": True}],
    )
    assert edges == []


def test_unresolvable_link_is_reported():
    merged = _merged(("a", manifest("a", nodes=[model("a", "x", "s")])))
    edges, unresolved = stitch.apply_links(merged, [], [{"from": "a.x", "to": "nope.nope"}])
    assert edges == []
    assert unresolved == ["a.x -> nope.nope"]
