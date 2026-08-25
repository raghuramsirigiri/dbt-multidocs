# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[semantic](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Viewport culling.** Only the slice of the graph inside the viewport is built
  into the DOM, so pan, zoom, hover, click and filtering cost the same at 6000
  nodes as at 400. On a 5750-node graph the DOM drops from ~77,700 SVG elements
  to ~1,600 and a drag frame from 479 ms to under 1 ms.
- **Compressed payloads.** Above ~1 MB of JSON the embedded payload is stored
  gzipped and base64'd and decoded in the page with `DecompressionStream` — a
  3000-model graph goes from a 9.0 MB file to 552 KB. Still one self-contained
  file with no network and no dependencies. `--compress {auto,always,never}`;
  smaller pages stay plain JSON so they open in any browser.
- **Fluid view transform.** Flicks carry their release velocity into a momentum
  glide whose resting point is projected from that velocity; dragging past the
  edges rubber-bands with progressive resistance instead of hard-stopping.
  Programmatic moves (Fit, centring on a selection or deep link) use a
  critically damped spring that starts from the current on-screen value and is
  cancelled by pointer-down, so an animation in flight can always be grabbed.
  All of it collapses to instant positioning under `prefers-reduced-motion`.
- `tools/bench_graph.py`, which generates synthetic projects at any size for
  re-measuring the above.

### Changed

- Search no longer waits on a 140 ms debounce; it renders on the next frame.
- Nodes highlight on pointer-down rather than on click.
- The "filter down for smooth interaction" banner is gone — it is no longer true.

### Fixed

- A config file's `out:` now resolves against the config file's directory, as
  `projects[].path` already did and as the docs already claimed. It was
  resolving against the working directory, so a checked-in config wrote to a
  different place depending on where you ran it from.
- The canvas rect is cached instead of measured inside the per-frame cull check,
  where `getBoundingClientRect()` forced a synchronous layout costing 13 ms.

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

[Unreleased]: https://github.com/raghuramsirigiri/dbt-multidocs/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/raghuramsirigiri/dbt-multidocs/releases/tag/v0.1.0
