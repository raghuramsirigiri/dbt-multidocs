# Getting started

## Install

Python 3.9 or newer. No other runtime requirements.

```bash
git clone https://github.com/raghuramsirigiri/dbt-docs-repo.git
cd dbt-docs-repo
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows: .venv\Scripts\pip install -e ".[dev]"
```

The `[dev]` extra adds `pytest` and nothing else. For a plain install, drop it.

## Generate the artifacts first

`dbt-multidocs` never runs dbt. In each project:

```bash
dbt docs generate
```

That writes `target/manifest.json` (required) and `target/catalog.json`
(optional — without it, column data types come up blank).

If your CI already runs `dbt docs generate`, keep the `target/` directories as
build artifacts and point `dbt-multidocs` at them; nothing else is needed.

## Find your projects

```bash
dbt-multidocs discover --search-root /repos
```

```
3 project(s):
  dbt_analytics    manifest + catalog    /repos/dbt_analytics
  dbt_core         manifest + catalog    /repos/dbt_core
  dbt_staging      manifest + catalog    /repos/dbt_staging
```

`discover` exits non-zero if any project is missing its manifest, so it also
works as a CI precondition check. Add `-v` for the resolved artifact paths.

## Build the page

```bash
dbt-multidocs build \
  --project /repos/dbt_staging \
  --project /repos/dbt_core \
  --project /repos/dbt_analytics \
  --out docs/lineage.html
```

```
  dbt_staging                12 nodes   /repos/dbt_staging/target/manifest.json
  dbt_core                    7 nodes   /repos/dbt_core/target/manifest.json
  dbt_analytics               6 nodes   /repos/dbt_analytics/target/manifest.json
written  : /repos/docs/lineage.html  (143 KB)
graph    : 25 nodes / 30 edges across 3 projects
           10 models, 4 seeds, 11 sources, 61 tests
           7 cross-project edges (11 inferred from source() relations)
```

The last line is the one to read. `7 cross-project edges` means the projects are
actually connected; `0` means they came out as islands, and
[How linking works](linking.md) explains why that happens.

Projects can live anywhere — different drives, different repos, no common
parent. `--project` also accepts a `target/` directory, a `manifest.json` path
directly, or a `dbt docs generate --static` `index.html`.

## Open it

```bash
open docs/lineage.html          # macOS
start docs\lineage.html         # Windows
xdg-open docs/lineage.html      # Linux
```

It is a single file with no external requests, so `file://` works, as does
serving it from GitHub Pages, S3, or any static host.

What's on the page: a swimlane per project against dependency depth; search
across names, descriptions, tags and column names; per-project and per-tag
filters; a project-level rollup map; a cross-project dependency report; a detail
panel with columns, types, test coverage and Source/Compiled SQL; deep links
that survive a reload; PNG and SVG export; light and dark themes.

## Put it in CI

```yaml
- run: pip install dbt-multidocs
- run: dbt-multidocs discover --search-root .          # fails if a manifest is missing
- run: |
    dbt-multidocs build --search-root . \
      --out site/lineage.html --strict
- uses: actions/upload-pages-artifact@v3
  with:
    path: site
```

`--strict` turns any warning into exit code 2, which is what you want in CI:
a missing catalog or an ambiguous relation match becomes a build failure rather
than a quietly degraded page.

## Next

- Projects showed up disconnected? → [How linking works](linking.md)
- Want labels, lane ordering, or manual links? → [Configuration](configuration.md)
- Hit a warning you don't recognize? → [Troubleshooting](troubleshooting.md)
