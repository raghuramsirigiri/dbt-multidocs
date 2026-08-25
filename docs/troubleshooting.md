# Troubleshooting

Every message the tool can print, and what to do about it. Warnings go to
stderr; `--strict` turns any of them into exit code 2.

## Errors (the build stops)

### `no manifest at ... / run 'dbt docs generate' in ... first`

The project has no `target/manifest.json`. Run `dbt docs generate` there, or
point `--project` at wherever you keep the artifact — it also accepts a
`target/` directory or a `manifest.json` path directly.

In CI, `dbt-multidocs discover` exits non-zero for exactly this case, so run it
as a precondition and get a clearer failure earlier.

### `No dbt projects found.`

Neither `--project`, nor config `projects:`, nor a sweep turned anything up. The
sweep skips `dbt_packages/`, `target/`, `.venv/`, `node_modules/` and
dot-directories, and defaults to 5 levels — raise `--depth`, or name the
projects explicitly with `--project`.

### `... has no inlined manifest (was it built with --static?)`

You pointed at an `index.html` from a plain `dbt docs generate`. That file loads
`manifest.json` at runtime rather than inlining it, so point at the
`manifest.json` beside it instead, or regenerate with `dbt docs generate --static`.

### `config not found: ...`

`--config` path doesn't exist. Note that paths *inside* the config resolve
against the config file's own directory, not your working directory.

## Warnings

### `no catalog.json next to manifest.json; column data types will be blank`

`dbt docs generate` writes the catalog; `dbt parse` and `dbt compile` do not.
Everything works without it — you lose column data types, and the detail panel
shows only columns declared in YAML. Run `dbt docs generate` if you want types.

### `relation X is produced by N models (...); skipped`

Two or more models write the same `database.schema.table`, so a source matching
that relation is genuinely ambiguous. The tool refuses to guess and emits no
edge.

This is usually a real problem rather than a tool limitation: two models
materializing to one relation means one overwrites the other. If it is
intentional (different targets, say), declare the edge yourself with a
[`links:`](configuration.md#links) entry.

### `N node(s) not claimed by any project's own manifest (imported packages?); grouped by package_name instead`

Some nodes' `package_name` doesn't match any loaded project's name — normal when
a manifest carries imported packages, or when you point at a single merged
manifest or a `--static` bundle. Those nodes are grouped into lanes by their
`package_name`, which is the right outcome; the warning exists so the lane names
aren't a surprise. Pass the upstream projects explicitly if you want their real
labels and their own artifacts used.

### `... reassigned from A to B` / `claimed by both A and B; kept A`

The same `unique_id` appeared in more than one manifest. The copy from the
project that defines it wins. Expected with dbt Mesh, where a downstream
manifest contains its dependencies. Nothing to do.

### `config link unresolved: X -> Y`

A [`links:`](configuration.md#links) entry names a node that doesn't exist, or a
bare name that matches several nodes. Use the full `unique_id` — find it in a
`--json` dump.

### `manifest schema vN (built and tested against v12); parsing anyway`

Your dbt version writes a manifest schema this release hasn't been tested
against. It usually still works, since the fields used here are stable. If the
graph looks wrong, please open an issue with your dbt version.

## Wrong-looking output

### The projects came out as separate islands

`0 cross-project edges` in the summary. This is the common one and it has its
own section: [How linking works → When inference finds nothing](linking.md#when-inference-finds-nothing).

Quickest check — is anything being inferred at all?

```bash
dbt-multidocs build --search-root . --out /tmp/l.html --json /tmp/g.json
jq '.stats | {cross_edges, inferred}' /tmp/g.json
```

### Seeds float unattached at the left edge

Expected under `--stitch-scope cross`, which only infers boundary-crossing
edges. The default `all` links a project's seeds to its own sources.

### Lanes are in the wrong order

Lane order comes from regexes matched against project names. If yours are
`bronze`/`silver`/`gold` or similar, set [`layers:`](configuration.md#layers) in
the config.

### A project's node count looks too low

Per-project counts are **owned** nodes. A node appearing in several manifests is
counted once, against the project that defines it — so a downstream project that
imports 30 nodes reports only the ones it actually owns. The `graph :` line
gives the true total.

### The page is large

Model SQL dominates. It is embedded so the page works offline with no requests.
143 KB for 25 nodes is typical; a few hundred models will run into the megabytes,
which is still fine for a static file. SQL over 40 KB per node is truncated.

### The page is slow to interact with

Above a few hundred visible nodes the page shows a hint to filter down. Use the
project and tag filters, the search box, or **Cross-project only** to cut the
graph to what you're looking at.

## Getting help

Open an issue with the command you ran and the full output including warnings.
For a stitching problem, the `relation_name` of the model and of the source that
should have matched is the single most useful detail. Please don't attach real
manifests — they contain your model SQL and schema names.
