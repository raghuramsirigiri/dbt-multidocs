# How linking works

This is the part of the tool worth understanding. Everything else is plumbing.

## Two kinds of edge

**Declared edges** come from each node's `depends_on.nodes` in the manifest.
They exist whenever dbt itself knew about the dependency: models within a
project, and cross-project `ref('project', 'model')` in a dbt Mesh setup where
the projects share a manifest. Nothing is inferred here; the graph is dbt's own.

**Inferred edges** are the ones dbt could not record. Three separate repos, three
separate `dbt docs generate` runs, three manifests that have never seen each
other. Downstream declares a source:

```yaml
# dbt_analytics/models/analytics/_sources.yml
sources:
  - name: core
    schema: main_core
    tables:
      - name: dim_customers
```

and upstream builds exactly that table:

```
model.dbt_core.dim_customers  ->  "analytics"."main_core"."dim_customers"
```

Two unrelated nodes in two unrelated manifests that happen to name the same
warehouse relation. Matching on that is what turns islands into a graph.

## The matching rule

For every model, seed and snapshot, and for every source, compute a
**relation key**:

```
(database, schema, identifier)
```

taken from `relation_name` when the manifest has one — `"analytics"."main_core"."dim_customers"`
— and otherwise assembled from the `database` / `schema` / `alias` (or
`identifier`) fields. Every part is lowercased and stripped of `"`, `'`, backticks
and `[ ]`, so `"Analytics"."Main_Core"."Dim_Customers"` and
`[analytics].[main_core].[dim_customers]` are the same key.

When a source's key matches exactly one producer, an edge is emitted from the
producer to the source:

```
model.dbt_core.dim_customers  ->  source.dbt_analytics.core.dim_customers
```

The source node stays visible. It is the seam between the two projects, and
showing it is honest: downstream's view of the table is a separate declaration
that can drift from what upstream actually builds.

## What is deliberately not matched

- **Nothing is guessed by name.** Two models called `customers` in different
  schemas are unrelated. Only the full three-part relation counts.
- **Ambiguity is refused.** If two models write the same relation, the tool
  warns and emits no edge rather than picking one. That situation is a real
  problem in your warehouse and the page shouldn't paper over it.
- **Column-level lineage is out of scope.** Columns, types and tests are shown
  per node; there are no column-to-column edges.

## Same-project seed/source pairs

A project often seeds `raw_orders` into `main_raw` *and* declares a source
pointing at `main_raw.raw_orders`. Both nodes exist, both describe the same
table, and without a link the seeds float unattached at the left edge.

The default `--stitch-scope all` links them. `--stitch-scope cross` restricts
inference to edges that actually cross a project boundary, leaving those seeds
detached — use it when you only care about the inter-project picture.

Either way, the `cross-project edges` count in the CLI summary counts only
boundary-crossing edges; the `inferred` count includes both.

## When inference finds nothing

`0 cross-project edges` means no source key matched a model key. Usually one of:

**The projects write to different databases.** Upstream builds
`prod.main_core.dim_customers`; downstream's source omits `database:` and
resolves to `analytics.main_core.dim_customers`. The keys differ in the first
part. Fix the source declaration, or add a manual link.

**The source points at a schema no model in scope builds.** You may simply not
have passed the upstream project — check the project list at the top of the
build output.

**Stale artifacts.** A source added last week against a manifest generated last
month. Re-run `dbt docs generate` on both sides.

**Custom schema or alias macros.** If a project overrides `generate_schema_name`
the manifest still records the resolved `relation_name`, so this normally works —
but only if the artifacts were generated with the same target as the run that
built the tables.

To see what the keys actually are:

```bash
dbt-multidocs build --search-root . --out /tmp/l.html --json /tmp/g.json
python - <<'PY'
import json
g = json.load(open('/tmp/g.json'))
for n in g['nodes']:
    print(n['type'], n['pkg'], n['schema'], n['alias'])
PY
```

Compare the `schema`/`alias` of the model against the source that should have
matched it.

## Forcing or suppressing a link

When inference can't work — a database name that genuinely differs across
environments, say — declare the edge yourself:

```yaml
links:
  - from: model.dbt_core.dim_customers
    to:   source.dbt_analytics.core.dim_customers
  - from: model.a.x                    # or remove one that was inferred wrongly
    to:   source.b.y
    remove: true
```

Manual links are applied after inference, so they always win. See
[Configuration](configuration.md).

## Turning inference off

`--no-stitch` uses declared `ref()` edges only. Two reasons to want it:

- Your projects are dbt Mesh and already share a manifest — inference has
  nothing to add.
- You want to see the honest before/after. Build twice, with and without, and
  the difference is exactly what the stitcher contributed.

## Reading the page

Inferred edges are drawn **dotted**, with a legend row saying so, and their
tooltip reads `inferred from matching relation`. Declared cross-project edges are
dashed and coloured by target project; edges within a project are solid. You can
always tell which links the tool guessed.
