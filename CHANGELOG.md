# Changelog

All notable changes to this project are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning is
[semantic](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-08-26

### Fixed

- **Deep graphs no longer crash.** Node depth and the project rollup were
  computed recursively, so the recursion depth was the length of the longest
  ancestor chain — and whether it overflowed also depended on manifest order,
  since dbt does not emit nodes in topological order. A large enough mesh raised
  `RecursionError` instead of rendering. Both now use an iterative pass, with
  identical depths on every acyclic graph.
- **The page title is escaped.** It was substituted into `<title>` and the
  header verbatim, so a project name containing `<` truncated the page and a
  crafted `--title` could inject markup. The three template placeholders are
  also filled in one pass now; previously each substitution rescanned text the
  last one inserted, so a title of `__GRAPH_DATA__` swallowed the payload.
- **`py.typed` is shipped.** The package advertised `Typing :: Typed` but
  included no marker, so type checkers silently fell back to `Any` for every
  signature. Five public parameters that took an implicit `Optional` were
  corrected along with it.
- Every project loaded without a `catalog.json` shared one empty catalog
  instance — and the module-level constant behind it. Nothing wrote to a catalog,
  so this never surfaced; it is a factory function now.

### Added

- **`--version`**, printing the package, Python and platform versions in the one
  line the bug report template asks for. The version is now written in one place
  only, `__version__`, which `pyproject.toml` reads.
- **Config files report what they ignore.** Every key was fetched with `.get()`,
  so a near miss like `project:` for `projects:` parsed, ran, and produced an
  empty page. Unknown keys are now warned about with a suggested correction and
  counted by `--strict`; a malformed shape is an error that stops the build,
  rather than — in the case of `projects:` given a string — being iterated one
  character at a time into a traceback.
- Tagging `vX.Y.Z` now publishes: the release workflow checks the tag against
  `__version__` and the changelog, verifies the built wheel installs and runs on
  its own, publishes to PyPI via Trusted Publishing, and opens a GitHub release
  from the changelog section.

### Internal

- CI enforces ruff, mypy and 90% coverage, and runs the suite both with and
  without PyYAML installed. Only one of those two parsers was ever exercised
  before, and since dbt-core depends on PyYAML it was the one most users are
  *not* on. Coverage also found the `dbt docs generate --static` reader
  completely untested; it is now at 98%.
- The ignored scratch directory `test/` was renamed `scratch/`, one keystroke
  having been all that separated it from the tracked `tests/`.

## [0.1.3] - 2026-08-25

Documentation only. No code changes.

### Added

- A screenshot of the generated lineage page, captured from the live published
  example, at the top of the README and the documentation index. It shows three
  independent dbt projects in separate swimlanes joined by inferred edges, which
  is the point of the tool in one picture.

## [0.1.2] - 2026-08-25

Packaging metadata only. No code changes.

### Fixed

- The `Documentation` link on the PyPI page pointed at the GitHub folder listing
  of `docs/`, which is a file browser rather than the documentation. It now
  points at the published documentation site, and a `Demo` link goes straight to
  the live example lineage page.

## [0.1.1] - 2026-08-25

Documentation only. No code changes: the installed package behaves exactly as
0.1.0.

### Changed

- README and docs now install with `pip install dbt-multidocs` rather than a
  source checkout, and link the published documentation and the live example
  lineage page.
- Corrected the install instructions, which had no clone step and so could not
  work as written, and a quickstart that mixed a Windows path into a
  backslash-continued bash block.
- Scoped two overstated claims: warehouse support is "any adapter should work,
  DuckDB is what has been tested", and `dbt docs generate` needs the warehouse
  for the catalog specifically.

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

## [0.1.0] - 2026-08-25

First release, published to PyPI as
[`dbt-multidocs`](https://pypi.org/project/dbt-multidocs/).

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

[Unreleased]: https://github.com/raghuramsirigiri/dbt-multidocs/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/raghuramsirigiri/dbt-multidocs/compare/v0.1.3...v0.2.0
[0.1.3]: https://github.com/raghuramsirigiri/dbt-multidocs/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/raghuramsirigiri/dbt-multidocs/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/raghuramsirigiri/dbt-multidocs/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/raghuramsirigiri/dbt-multidocs/releases/tag/v0.1.0
