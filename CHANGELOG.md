# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[semantic](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0]

First release.

### Added

- `dbt-multidocs build` — merges any number of independent dbt manifests into
  one self-contained HTML lineage page. Zero runtime dependencies; reads
  `target/` artifacts only, never invoking dbt or opening a warehouse connection.
- **Cross-project edge inference.** Projects linked only by `source()` over a
  shared warehouse — separate repos, separate manifests, no cross-project
  `ref()` — are stitched together by matching normalized
  `(database, schema, identifier)` relation keys. Ambiguous matches warn and
  produce no edge rather than guessing.
- **Manifest merging with an ownership rule.** A node belongs to the project
  whose `project_name` matches its `package_name`, so overlapping manifests
  (dbt Mesh, shared installed packages) collapse to one node per definition
  instead of one per manifest. Unclaimed nodes fall back to `package_name`, so a
  single merged manifest or a `--static` bundle still splits into per-package
  lanes.
- `dbt-multidocs discover` — lists projects and artifact status, exiting non-zero
  when a manifest is missing, for use as a CI precondition.
- **Project location independence.** `--project` accepts a project directory, a
  `target/` directory, a `manifest.json`, or a `dbt docs generate --static`
  `index.html`; `--search-root` sweeps for `dbt_project.yml` at a configurable
  depth. Nothing is derived from a common parent, the working directory, or the
  install location.
- **Config file** (`dbt-multidocs.yml` or JSON) for titles, project labels and
  ids, swimlane ordering regexes, and manual `links:` that add or suppress edges
  after inference.
- `--no-stitch`, `--stitch-scope`, `--strict`, `--json`, `--template`, `--title`.
- HTML page carried over from the `dbt-lineage-multi-project` prototype:
  swimlanes, search across names/descriptions/tags/columns, project rollup map,
  cross-project dependency report, detail panel with columns, types, test
  coverage and Source/Compiled SQL, deep links, PNG/SVG export, light and dark
  themes. Inferred edges render dotted with their own legend entry so a guessed
  link is never mistaken for a declared one.

[Unreleased]: https://github.com/raghuramsirigiri/dbt-docs-repo/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/raghuramsirigiri/dbt-docs-repo/releases/tag/v0.1.0
