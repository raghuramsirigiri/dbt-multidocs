# dbt-multidocs

[![CI](https://github.com/raghuramsirigiri/dbt-docs-repo/actions/workflows/ci.yml/badge.svg)](https://github.com/raghuramsirigiri/dbt-docs-repo/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Dependencies](https://img.shields.io/badge/runtime%20deps-none-brightgreen)

Point it at any number of dbt projects — in unrelated directories, on unrelated
repos — and get **one self-contained lineage page**: a single HTML file, no
network calls, no JS dependencies, no dbt install, no warehouse connection.

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

## What it solves

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

## Install

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev]"    # Windows: .venv\Scripts\pip
```

No runtime dependencies. Python 3.9+.

## Input

Artifacts only — `target/manifest.json` plus, optionally, `target/catalog.json`.
Run `dbt docs generate` in each project first. Nothing here runs dbt, opens a
connection, or reads `profiles.yml`.

`--project` accepts a project directory, its `target/` directory, a
`manifest.json` path, or a `dbt docs generate --static` `index.html`.

A missing catalog is a warning (column data types come up blank); a missing
manifest is an error that names the project and the command to fix it.

## Finding projects

```bash
dbt-multidocs discover --search-root /repos          # what's out there?
dbt-multidocs discover --search-root /repos -v       # + resolved artifact paths
```

`--search-root` walks for `dbt_project.yml` (5 levels by default, `--depth` to
change), skipping `dbt_packages/`, `target/`, `.venv/`, `node_modules/` and the
like. Repeat it for several unrelated roots. Explicit `--project` paths always
win. With neither, the current directory is swept.

## Config file

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
| `--json FILE` | also dump the graph payload |

## The page

Swimlane per project × dependency depth, plus: search across names, descriptions,
tags and column names; per-project and per-tag filters; a project-level rollup
map; a cross-project dependency report; a detail panel with columns, types, test
coverage and Source/Compiled SQL; deep links; PNG/SVG export; light and dark
themes. All of it offline, from `file://`.

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

## Credits

The page's HTML/JS and the SQL pretty-printer are carried over from the
`dbt-lineage-multi-project` prototype; this package generalizes the data layer
around them to N independent projects.
