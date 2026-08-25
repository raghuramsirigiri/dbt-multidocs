# Architecture

The pipeline is linear and every stage is a separate module you can call on its
own. Nothing runs dbt; nothing opens a warehouse connection.

```
discovery  ->  artifacts  ->  merge  ->  stitch  ->  graph  ->  render
  find         read           one       infer       lay out    inline
  projects     manifests      node      missing     lanes,     JSON into
               + catalogs     universe  edges       depth      the template
```

## Modules

### `discovery.py`

Turns paths, config entries and search sweeps into `Project` records
(`id`, `label`, `root`, `manifest_path`, `catalog_path`, `project_name`,
`origin`). Every path is resolved absolute immediately. Nothing is derived from
the current working directory or from where the package is installed, because
the projects are assumed to be unrelated repositories.

Ids must be unique: two repos with the same dbt project name are disambiguated
by their parent directory.

### `artifacts.py`

Reads `manifest.json` and, when present, `catalog.json`. Also handles a
`dbt docs generate --static` `index.html`, which inlines both — extracted with a
brace scanner that tracks string state, so braces inside model SQL don't derail
it the way a regex would.

A missing catalog is a warning; a missing manifest raises `ArtifactError` naming
the project and the command that fixes it. Unexpected schema versions warn but
still parse (built against manifest v12 / catalog v1).

### `merge.py`

Folds N manifests into one `{unique_id: node}` map plus `owner[unique_id]`.
Sources are carried in with `resource_type: "source"`; tests are collected
separately; catalog entries are indexed by node.

**Ownership rule:** a node belongs to the project whose manifest metadata
`project_name` equals the node's `package_name`. This matters when manifests
overlap — a dbt Mesh project's manifest contains its dependencies' nodes too, so
naive merging would duplicate them once per manifest. The rule collapses those
copies onto the project that actually defines each node.

**Fallback:** nodes no loaded project claims — a single merged manifest, or a
`--static` bundle carrying several packages — keep their `package_name` as their
project. Without this they would all flatten into one lane.

### `stitch.py`

Infers the cross-project edges `depends_on` cannot express, by matching
normalized `(database, schema, identifier)` relation keys between producers and
sources. Ambiguous matches are refused with a warning. `apply_links` then
applies manual config links on top. See [How linking works](linking.md).

### `graph.py`

Builds the render payload: declared edges from `depends_on`, then inferred edges;
cycle-safe longest-path depth; swimlane assignment; per-node columns, tests and
SQL; and the project-level rollup DAG.

Three details that look like quirks but are deliberate:

- **Test attribution** uses `attached_node` first. A `relationships` test's
  `depends_on` also names the model it points *at*, which must not be counted as
  that model's own test coverage.
- **Depth resolution** carries a `seen` frozenset, so a cyclic graph terminates
  with finite depths instead of recursing forever.
- **`sql_compiled` is dropped** when identical to `sql_source`, and SQL over
  40 KB is truncated before pretty-printing — both keep the page small.

### `layout.py`

Lane ordering (regex list, configurable), the 12-hue palette, and label
prettifying (`proj_marts_finance` → `marts · finance`).

### `render.py`

Inlines the payload as JSON into the packaged template, escaping `</` as `<\/`
so the data cannot terminate its own `<script>` block. The template is loaded
through `importlib.resources`, so it works from a wheel or an editable install.

### `templates/lineage.html`

The page itself: hand-written vanilla JS building SVG, its own layout, pan/zoom
and SQL highlighter. No libraries, no CDN, no network requests of any kind.

### `sql_format.py`

A conservative tokenizing SQL pretty-printer, carried over from the prototype
this package generalizes.

## Payload shape

`--json FILE` dumps exactly what the page receives.

```jsonc
{
  "packages": [
    {"name": "dbt_core", "label": "core", "color": "#34d399",
     "rank": 2, "depth": 1, "count": 7}
  ],
  "nodes": [
    {
      "id": "model.dbt_core.dim_customers",
      "name": "dim_customers",
      "pkg": "dbt_core",              // project id, not package_name
      "color": "#34d399",
      "type": "model",                // model | seed | snapshot | source
      "mat": "table",
      "schema": "main_core",
      "alias": "dim_customers",
      "path": "models/core/dim_customers.sql",
      "desc": "...",
      "tags": [],
      "depth": 2,                     // longest path from a root
      "parents": ["..."],
      "children": ["..."],
      "columns": [
        {"name": "customer_id", "type": "VARCHAR", "desc": "...",
         "tests": ["not_null", "unique"], "undeclared": true}
      ],
      "col_count": 8,
      "tests": {"not_null": 2, "unique": 1},
      "test_count": 3,
      "xp_in": 1,                     // cross-project parents
      "xp_out": 3,                    // cross-project children
      "sql_source": "...",
      "sql_compiled": "",             // empty when identical to source
      "col_tests": 4,                 // columns carrying at least one test
      "model_tests": ["..."]          // table-level test types
    }
  ],
  "edges": [["from_id", "to_id"]],          // declared, then inferred
  "inferred_edges": [["from_id", "to_id"]], // the inferred subset
  "project_edges": [{"from": "a", "to": "b", "weight": 4}],
  "stats": {
    "models": 10, "seeds": 4, "sources": 11, "tests": 61,
    "cross_edges": 7,      // edges crossing a project boundary
    "inferred": 11,        // edges inference produced (incl. same-project)
    "projects": 3,
    "generated_at": "...", // newest across the manifests
    "subtitle": "3 projects · dbt 1.12.3 · duckdb · generated ... UTC"
  }
}
```

`columns[].undeclared` marks a column a test names that the YAML never declared.
`inferred_edges` is a subset of `edges`, not additional to it.

## Using it as a library

```python
from dbt_multidocs import artifacts, discovery, graph, merge, render, stitch

projects = discovery.resolve(paths=["/repos/a", "/repos/b"])
merged   = merge.merge([artifacts.load(p) for p in projects])
inferred = stitch.stitch(merged).edges
payload  = graph.build(merged, stitched_edges=inferred)

render.write(payload, "site/lineage.html", "My Lineage")
```

`payload` is plain JSON-serializable data — feed it to your own template, or
diff two builds to see what a PR changed about your lineage.

## Tests

`tests/conftest.py` builds synthetic manifests in memory and on disk, so the
suite runs in well under a second with no dbt, no warehouse, and no large
fixtures in the repository. Please add tests the same way — see
[CONTRIBUTING](../CONTRIBUTING.md).
