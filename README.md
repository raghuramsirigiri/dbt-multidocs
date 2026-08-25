# dbt-multidocs

[![CI](https://github.com/raghuramsirigiri/dbt-multidocs/actions/workflows/ci.yml/badge.svg)](https://github.com/raghuramsirigiri/dbt-multidocs/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/runtime%20deps-none-brightgreen)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**dbt-multidocs is a command-line tool that merges several independent dbt
projects into a single, self-contained data-lineage page.** Point it at any
number of dbt projects — in unrelated directories, on unrelated repos — and it
produces one HTML file with the whole graph: no network calls, no JavaScript
dependencies, no dbt installation, and no warehouse connection.

It is built for the case dbt itself does not cover: **cross-project lineage when
the projects do not share a manifest.** If your dbt projects live in separate
repositories and are linked only by `source()` over a shared warehouse,
`dbt docs generate` shows them as disconnected islands. dbt-multidocs
reconnects them.

```bash
dbt-multidocs build \
  --project /repos/dbt_staging \
  --project /repos/dbt_core \
  --project D:\other\dbt_analytics \
  --out docs/lineage.html
```

```
  dbt_staging                12 nodes   .../dbt_staging/target/manifest.json
  dbt_core                    7 nodes   .../dbt_core/target/manifest.json
  dbt_analytics               6 nodes   .../dbt_analytics/target/manifest.json
written  : .../docs/lineage.html  (143 KB)
graph    : 25 nodes / 30 edges across 3 projects
           10 models, 4 seeds, 11 sources, 61 tests
           7 cross-project edges (11 inferred from source() relations)
```

## How do you get lineage across multiple dbt projects?

dbt gives you cross-project lineage only when the projects share a manifest —
dbt Mesh with `dependencies.yml` and two-argument `ref()`. Plenty of real setups
aren't like that: separate repos, separate `dbt docs generate` runs, separate
manifests, linked only by a downstream project's `source()` pointing at a table
an upstream project builds. Those show up as disconnected islands.

`dbt-multidocs` merges N independent manifests and **infers the missing edges**
by matching normalized warehouse relations — `(database, schema, identifier)` —
between one project's models and another's sources. Declared `ref()` edges are
still used where they exist, so dbt Mesh projects work too.

Inferred links are drawn dotted and labelled in the legend, so you can always
tell a link the tool guessed from one dbt declared.

### How it compares

| | `dbt docs generate` | dbt Mesh (`ref()` across projects) | dbt-multidocs |
|---|---|---|---|
| Projects per page | one | many | many |
| Needs a shared manifest | — | yes | **no** |
| Needs `dependencies.yml` | — | yes | **no** |
| Links projects joined only by `source()` | no | no | **yes** |
| Needs a warehouse connection | yes | yes | **no** |
| Needs dbt installed | yes | yes | **no** |
| Output | multi-file site | multi-file site | **one HTML file** |
| Runtime dependencies | several | several | **none** |

dbt-multidocs does not replace `dbt docs generate` — it reads the artifacts that
command produces. Run dbt docs first, then point dbt-multidocs at the results.

### When you should not use this

- **One dbt project only.** `dbt docs generate` already does this well; there is
  nothing for dbt-multidocs to merge.
- **You want column-level lineage.** Columns, types and test coverage are shown
  per model, but there are no column-to-column edges.
- **You want a live catalog with freshness, run history or ownership
  workflows.** This is a static page built from artifacts. Look at DataHub,
  OpenMetadata, Atlan or dbt Cloud instead.

## How do you install dbt-multidocs?

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"    # Windows: .venv\Scripts\pip
```

No runtime dependencies. Python 3.9+.

## What input does it need?

Artifacts only — `target/manifest.json` plus, optionally, `target/catalog.json`.
Run `dbt docs generate` in each project first. Nothing here runs dbt, opens a
connection, or reads `profiles.yml`.

`--project` accepts a project directory, its `target/` directory, a
`manifest.json` path, or a `dbt docs generate --static` `index.html`.

A missing catalog is a warning (column data types come up blank); a missing
manifest is an error that names the project and the command to fix it.

## How do you point it at your dbt projects?

```bash
dbt-multidocs discover --search-root /repos          # what's out there?
dbt-multidocs discover --search-root /repos -v       # + resolved artifact paths
```

`--search-root` walks for `dbt_project.yml` (5 levels by default, `--depth` to
change), skipping `dbt_packages/`, `target/`, `.venv/`, `node_modules/` and the
like. Repeat it for several unrelated roots. Explicit `--project` paths always
win. With neither, the current directory is swept.

## How do you configure it?

Only needed for labels, lane ordering, or manual links.

```yaml
title: Enterprise dbt Lineage
projects:
  - path: ../dbt_staging
    label: Staging
  - path: ../dbt_core
  - path: D:\repos\dbt_analytics
layers: ["raw|seed", "staging|stg", "core|int", "mart", "analytic|dashboard"]
links:
  - from: model.dbt_core.dim_customers          # force a link inference missed
    to:   source.dbt_analytics.core.dim_customers
  - from: model.a.x                             # or suppress one it got wrong
    to:   source.b.y
    remove: true
```

Relative paths resolve against the config file's own directory. `layers` is an
ordered list of regexes matched against project names; the first hit sets the
swimlane row. JSON config files work too.

## Flags

| Flag | |
|---|---|
| `--project PATH` | repeatable; project dir, `target/`, or a manifest |
| `--search-root DIR` / `--depth N` | repeatable sweep, default depth 5 |
| `--config FILE` | `dbt-multidocs.yml` or `.json` |
| `--out FILE` | default `dbt-docs/lineage.html` |
| `--title TEXT` | page heading |
| `--template FILE` | replace the packaged HTML template |
| `--no-stitch` | declared `ref()` edges only, no inference |
| `--stitch-scope cross` | don't link a project's own seeds to its own sources |
| `--strict` | exit 2 if anything warned |
| `--compress auto\|always\|never` | gzip the embedded payload (default: auto, above ~1 MB) |
| `--json FILE` | also dump the graph payload |

## What does the generated page look like?

Swimlane per project × dependency depth, plus: search across names, descriptions,
tags and column names; per-project and per-tag filters; a project-level rollup
map; a cross-project dependency report; a detail panel with columns, types, test
coverage and Source/Compiled SQL; deep links; PNG/SVG export; light and dark
themes. All of it offline, from `file://`.

**It stays interactive at size.** Only the slice of the graph inside the
viewport is ever in the DOM, so a 6000-node graph pans, zooms and filters as
cheaply as a small one. Flicks carry momentum and rubber-band at the edges;
programmatic moves (Fit, jumping to a selection) spring from wherever the canvas
currently is and can be grabbed mid-flight. `prefers-reduced-motion` is
honoured.

## Frequently asked questions

### Does dbt-multidocs require dbt Mesh?

No. dbt Mesh projects work — declared cross-project `ref()` edges are used where
they exist — but dbt-multidocs is specifically built for projects that are *not*
on Mesh and share no manifest. It needs no `dependencies.yml` and no
two-argument `ref()`.

### Does it connect to my data warehouse?

No. It reads `target/manifest.json` and `target/catalog.json` only. It never runs
dbt, never opens a database connection, and never reads `profiles.yml`. That
makes it safe to run in CI and on machines with no warehouse credentials.

### How does it know two projects are connected?

It matches normalized warehouse relations. Every model, seed and snapshot is
indexed by `(database, schema, identifier)`, and every `source()` is resolved to
the same key. When a downstream project's source names the exact relation an
upstream project builds, that is an edge. Ambiguous matches — one relation
produced by two models — are reported and skipped rather than guessed at.

### Which data warehouses does it support?

All of them. It reads dbt artifacts rather than the warehouse, so Snowflake,
BigQuery, Databricks, Redshift, Postgres and DuckDB all work identically.

### How many dbt models can it handle?

Tested to 3,000 models across 12 projects (5,750 nodes, 9,700 edges). Only the
part of the graph inside the viewport is rendered, so panning and filtering cost
the same at 6,000 nodes as at 400. Large graphs are gzipped inside the page: that
5,750-node example is a 552 KB file.

### Can I host the output on GitHub Pages?

Yes. The output is one self-contained HTML file with no external requests, so
GitHub Pages, S3, Netlify or any static host serves it as-is. It also opens
directly from `file://`.

### Is it free and open source?

Yes — MIT licensed, with no runtime dependencies and no paid tier.

## Documentation

| | |
|---|---|
| [Getting started](docs/getting-started.md) | install, first build, CI setup |
| [How linking works](docs/linking.md) | declared vs inferred edges, and when inference fails |
| [CLI reference](docs/cli.md) | every command and flag |
| [Configuration](docs/configuration.md) | `dbt-multidocs.yml` |
| [Architecture](docs/architecture.md) | the pipeline, the payload shape, library use |
| [Troubleshooting](docs/troubleshooting.md) | every warning, and what to do about it |

A rendered example page — a real build of three independent dbt projects — is at
[docs/lineage.html](docs/lineage.html).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). The short version:

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest
```

Tests use synthetic manifests only — no dbt, no warehouse, no multi-megabyte
fixtures in the repository. The suite runs in under a second.

Changes are held to the design constraints above; the ones most likely to catch
you out are **no runtime dependencies** and **nothing derived from a common
parent directory or the working directory**.

## License

MIT — see [LICENSE](LICENSE). The generated lineage page embeds this project's
HTML template, so pages you produce carry no obligations of their own.

## Maintainer

Built and maintained by [Raghuram Sirigiri](https://github.com/raghuramsirigiri).
Issues and pull requests are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

The page's HTML/JS and the SQL pretty-printer are carried over from the
`dbt-lineage-multi-project` prototype; this package generalizes the data layer
around them to N independent projects.
