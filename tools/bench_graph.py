"""Generate N synthetic dbt projects with M models each, as real manifests on disk.

For measuring where the lineage page stops being interactive. The projects it
writes are ordinary dbt artifacts, so `dbt-multidocs` reads them the same way it
reads real ones - including the source()-to-model stitching between projects.

    python tools/bench_graph.py /tmp/big 12 250
    dbt-multidocs build --search-root /tmp/big --out /tmp/big.html

12 x 250 gives 5750 nodes / 9700 edges, which is the graph the numbers in
docs/architecture.md were measured on. Each project is five depth tiers wide
rather than one long chain, because real dbt graphs are wide.
"""
import json
import pathlib
import sys

SQL = """with source as (
    select * from {{ ref('upstream') }}
),
renamed as (
    select
        id,
        customer_id,
        order_date,
        status,
        amount * 1.0 as amount_usd,
        case when status = 'completed' then 1 else 0 end as is_complete
    from source
    where order_date >= '2020-01-01'
)
select * from renamed
"""


def build(outdir, n_projects, n_models):
    root = pathlib.Path(outdir)
    layers = ["raw", "staging", "intermediate", "core", "marts", "analytics"]
    projects = []
    for i in range(n_projects):
        layer = layers[min(i * len(layers) // n_projects, len(layers) - 1)]
        projects.append(f"dbt_{layer}_{i:02d}")

    for i, proj in enumerate(projects):
        schema = f"main_{proj}"
        nodes, sources, cat = {}, {}, {}
        for m in range(n_models):
            uid = f"model.{proj}.mdl_{m:04d}"
            depends = []
            if i > 0:
                # each model reads one source from the previous project
                up = projects[i - 1]
                src_uid = f"source.{proj}.{up}.mdl_{m:04d}"
                sources[src_uid] = {
                    "unique_id": src_uid, "name": f"mdl_{m:04d}", "identifier": f"mdl_{m:04d}",
                    "source_name": up, "resource_type": "source", "package_name": proj,
                    "database": "analytics", "schema": f"main_{up}",
                    "relation_name": f'"analytics"."main_{up}"."mdl_{m:04d}"',
                    "columns": {}, "tags": [], "description": f"Upstream {m} from {up}",
                }
                depends.append(src_uid)
            # 5 depth tiers per project: wide graphs, not one long chain
            tier, per_tier = m * 5 // n_models, max(1, n_models // 5)
            if tier > 0:
                for k in (1, 2):
                    up_i = (m - per_tier * k) % n_models
                    if up_i * 5 // n_models < tier:
                        depends.append(f"model.{proj}.mdl_{up_i:04d}")
            cols = {f"col_{c}": {"description": f"Column {c} of model {m}"} for c in range(12)}
            nodes[uid] = {
                "unique_id": uid, "name": f"mdl_{m:04d}", "alias": f"mdl_{m:04d}",
                "resource_type": "model", "package_name": proj,
                "database": "analytics", "schema": schema,
                "relation_name": f'"analytics"."{schema}"."mdl_{m:04d}"',
                "depends_on": {"nodes": depends},
                "config": {"materialized": "table" if m % 3 else "view"},
                "columns": cols, "tags": ["nightly"] if m % 4 == 0 else [],
                "raw_code": SQL,
                "compiled_code": SQL.replace("{{ ref('upstream') }}", "analytics.main.up"),
                "original_file_path": f"models/mdl_{m:04d}.sql",
                "description": f"Model {m} in {proj}. " * 3,
            }
            for c in range(12):
                if m % 2 == 0 and c < 3:
                    tid = f"test.{proj}.nn_{m}_{c}"
                    nodes[tid] = {
                        "unique_id": tid, "resource_type": "test", "package_name": proj,
                        "test_metadata": {"name": "not_null"}, "column_name": f"col_{c}",
                        "attached_node": uid, "depends_on": {"nodes": [uid]},
                    }
            cat[uid] = {"columns": {f"col_{c}": {"type": "VARCHAR", "index": c} for c in range(12)}}

        manifest = {
            "metadata": {
                "project_name": proj, "dbt_version": "1.12.3", "adapter_type": "duckdb",
                "generated_at": "2026-08-25T00:00:00Z",
                "dbt_schema_version": "https://schemas.getdbt.com/dbt/manifest/v12.json",
            },
            "nodes": nodes, "sources": sources,
        }
        d = root / proj
        (d / "target").mkdir(parents=True, exist_ok=True)
        (d / "dbt_project.yml").write_text(f"name: {proj}\nversion: '1.0.0'\n", encoding="utf8")
        (d / "target" / "manifest.json").write_text(json.dumps(manifest), encoding="utf8")
        (d / "target" / "catalog.json").write_text(json.dumps(
            {"metadata": {"dbt_schema_version": "https://schemas.getdbt.com/dbt/catalog/v1.json"},
             "nodes": cat, "sources": {}}), encoding="utf8")
    print(f"{n_projects} projects x {n_models} models -> {root}")


if __name__ == "__main__":
    build(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]))
