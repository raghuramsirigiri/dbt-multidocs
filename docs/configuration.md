# Configuration

A config file is optional. It earns its place when you want stable labels, a
particular lane order, manual links, or a build that is reproducible without a
long command line.

```bash
dbt-multidocs build --config dbt-multidocs.yml
```

## Full example

```yaml
title: Enterprise dbt Lineage

projects:
  - path: ../dbt_staging
    label: Staging
  - path: ../dbt_core
    label: Core
  - path: D:\repos\dbt_analytics
    label: Analytics
    id: analytics_eu               # optional; overrides the dbt project name

layers:
  - "raw|seed|landing"
  - "staging|stg"
  - "core|int|intermediate"
  - "mart|warehouse"
  - "analytic|dashboard|report|bi"

links:
  - from: model.dbt_core.dim_customers
    to:   source.dbt_analytics.core.dim_customers
  - from: model.legacy.orders
    to:   source.dbt_analytics.core.orders
    remove: true
```

JSON works too — pass a `.json` file and the same keys apply.

## Keys

### `title`

The page heading. `--title` overrides it.

### `projects`

A list of entries, each `path` plus optional `label` and `id`.

**Relative paths resolve against the config file's own directory**, not the
current working directory, so a config file checked into a repo works from
anywhere.

A bare string is shorthand for `{path: ...}`:

```yaml
projects:
  - ../dbt_staging
  - ../dbt_core
```

`--project` paths on the command line are added *before* config entries; both
sets are used. To build a subset without editing the file, use `--project` and
leave `--config` off.

### `layers`

An ordered list of regexes matched (case-insensitively) against each project's
id. The first match sets its swimlane row, so lanes read top to bottom in
pipeline order. Projects matching nothing sort last, alphabetically.

The default handles the common vocabularies:

```yaml
layers:
  - "raw|seed|landing|source"
  - "staging|stg"
  - "core|int|intermediate|conform"
  - "mart|warehouse|dim|fact"
  - "analytic|dashboard|report|bi|expos|serving"
```

Override it when your naming is different — `bronze|silver|gold`, for instance.
A pattern that isn't valid regex is treated as a plain substring rather than
failing the build.

### `links`

Manual edges, applied **after** inference so they always win. See
[How linking works](linking.md) for when you need them.

```yaml
links:
  - from: model.dbt_core.dim_customers          # add an edge inference missed
    to:   source.dbt_analytics.core.dim_customers
  - from: model.a.x                             # suppress one it got wrong
    to:   source.b.y
    remove: true
```

`remove: true` drops an edge (`suppress: true` is accepted as a synonym).

`from` and `to` accept a full `unique_id`, the id without its `model.` / `source.`
prefix, or a bare node name when that name is unique across every project. A
reference that resolves to nothing — or to more than one node — is reported as
`config link unresolved` rather than silently ignored.

Direction is always producer → consumer: `from` the model that builds the table,
`to` the source that reads it.

### `out`

Default output path, equivalent to `--out`. The flag wins.

## Precedence

For every setting: **command-line flag > config file > built-in default**.

## Mistakes in the file

The keys above are the only ones read, so an unrecognised one is reported
rather than ignored — a singular `project:` parses fine and builds an empty
page, which otherwise looks like a bug in the tool:

```
warning  : config: unknown key 'project' (ignored); did you mean 'projects'?
```

Unknown keys are warnings: the rest of the file still applies, and `--strict`
counts them. A malformed *shape* is an error and stops the build, because there
is nothing sensible to do with it:

```
error: config: 'projects' must be a list, found str
```

## YAML support

The package has no runtime dependencies, so it ships a small YAML reader
covering the subset used here: nested mappings, lists of scalars, lists of
mappings, quoted and unquoted scalars, and `#` comments. If PyYAML happens to be
installed in the same environment it is used instead, and the full language is
available. Anchors, flow style and multi-line scalars only work in that case —
or use a `.json` config, which is always parsed in full.
