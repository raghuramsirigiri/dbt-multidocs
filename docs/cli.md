# CLI reference

```
dbt-multidocs build     [options]     # write the combined lineage page
dbt-multidocs discover  [options]     # list projects and their artifact status
```

Also runnable as `python -m dbt_multidocs`.

## Locating projects

These options are shared by both commands.

### `--project PATH` (repeatable)

The primary interface. Accepts any of:

| | |
|---|---|
| a project directory | the one holding `dbt_project.yml`; artifacts are read from its `target/` |
| a `target/` directory | for artifacts kept apart from the source tree |
| a `manifest.json` | `catalog.json` is picked up if it sits beside it |
| a `--static` `index.html` | `dbt docs generate --static` inlines both artifacts |

Paths may be absolute or relative, on any drive, with no common parent.

### `--search-root DIR` (repeatable), `--depth N`

Walks `DIR` for `dbt_project.yml`, defaulting to 5 levels. Skips
`dbt_packages/`, `target/`, `logs/`, `.git/`, `.venv/`, `venv/`, `env/`,
`node_modules/`, `__pycache__/` and dot-directories, and does not descend into a
project once found.

### `--config FILE`

`dbt-multidocs.yml` or a `.json` equivalent. See [Configuration](configuration.md).

### Precedence

`--project` paths first, then `projects:` from the config, then `--search-root`
sweeps. With none of the three, the current directory is swept. Duplicates are
collapsed; two projects sharing a dbt name get distinct ids suffixed with their
parent directory.

### `--verbose` / `-v`

On `discover`, prints resolved manifest and catalog paths and how each project
was found.

## `build`

| Flag | Default | |
|---|---|---|
| `--out FILE`, `-o` | `dbt-docs/lineage.html` | parent directories are created |
| `--title TEXT` | `Multi-Project dbt Lineage` | page heading; config `title:` also sets it |
| `--template FILE` | packaged template | replace the HTML shell entirely |
| `--no-stitch` | off | declared `ref()` edges only, no inference |
| `--stitch-scope {all,cross}` | `all` | `cross` skips same-project seed/source links |
| `--strict` | off | exit 2 if anything warned |
| `--json FILE` | — | also dump the graph payload |

### Output

```
  dbt_staging                12 nodes   /repos/dbt_staging/target/manifest.json
  dbt_core                    7 nodes   /repos/dbt_core/target/manifest.json
  dbt_analytics               6 nodes   /repos/dbt_analytics/target/manifest.json
written  : /repos/docs/lineage.html  (143 KB)
graph    : 25 nodes / 30 edges across 3 projects
           10 models, 4 seeds, 11 sources, 61 tests
           7 cross-project edges (11 inferred from source() relations)
```

Per-project node counts are **owned** nodes, so a node that appears in several
manifests is counted once, against the project that defines it. Warnings go to
stderr; everything else to stdout.

### Exit codes

| | |
|---|---|
| `0` | page written |
| `1` | no projects found, or bad arguments |
| `2` | `--strict` and at least one warning |
| — | a missing manifest raises an error naming the project and the fix |

## `discover`

Prints each project, its artifact status, and its root. Exits `1` if any project
is missing a manifest, which makes it a usable CI precondition:

```bash
dbt-multidocs discover --search-root . || { echo "run dbt docs generate"; exit 1; }
```

## Examples

Three unrelated repos:

```bash
dbt-multidocs build \
  --project /repos/staging --project ~/work/core --project D:\data\analytics \
  --out site/lineage.html
```

Everything under a monorepo, strict:

```bash
dbt-multidocs build --search-root . --depth 4 --strict --out site/lineage.html
```

Reproducible config-driven build:

```bash
dbt-multidocs build --config dbt-multidocs.yml
```

Inspect the graph without opening a browser:

```bash
dbt-multidocs build --search-root . --out /tmp/l.html --json /tmp/graph.json
jq '.stats' /tmp/graph.json
```

Before/after, to see what inference contributed:

```bash
dbt-multidocs build --search-root . --out /tmp/with.html    --json /tmp/with.json
dbt-multidocs build --search-root . --out /tmp/without.html --json /tmp/without.json --no-stitch
jq '.stats.cross_edges' /tmp/with.json /tmp/without.json
```
