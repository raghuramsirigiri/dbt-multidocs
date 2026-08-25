# Contributing

Thanks for taking a look. This is a small, deliberately constrained package —
reading [docs/architecture.md](docs/architecture.md) first will save you time.

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"      # Windows: .venv\Scripts\pip install -e ".[dev]"
.venv/bin/pytest
```

The suite runs in under a second and needs no dbt install, no warehouse, and no
network.

## Constraints that PRs are held to

These are design decisions, not oversights. If a change needs to break one,
raise an issue first so we can talk about it.

**No runtime dependencies.** Stdlib only, so the package installs in CI, in
air-gapped environments, and next to any dbt version without resolver conflicts.
That is also why there is a small YAML reader in `_yaml.py` instead of a PyYAML
dependency. `[dev]` is `pytest` and nothing else.

**Artifacts only.** The tool reads `manifest.json` and `catalog.json`. It never
invokes dbt, opens a warehouse connection, or reads `profiles.yml`. Anything
needing a live connection belongs in a different tool.

**One self-contained output file.** No CDN links, no external stylesheets, no
runtime fetches. The page must open from `file://` with the network disabled.

**No assumed layout.** Projects are unrelated repositories. Nothing may be
derived from a common parent directory, from the current working directory, or
from where the package is installed. `tests/test_cli.py` enforces this by
building the same projects from different working directories with both absolute
and relative paths and asserting identical output.

**Inference stays visible.** An edge the tool guessed must remain visually
distinct from one dbt declared. If you add another inference strategy, it needs a
legend entry and a `stats` counter.

**Never guess between candidates.** Ambiguity warns and produces no edge. A
wrong lineage edge is worse than a missing one — people make schema decisions
from these graphs.

## Tests

Use the synthetic manifest builders in `tests/conftest.py`:

```python
from conftest import manifest, model, source, write_project

def test_something():
    doc = manifest("proj", nodes=[model("proj", "orders", "main_core")])
    ...
```

`model()` / `source()` produce nodes with a realistic `relation_name`;
`write_project()` lays a project out on disk the way dbt does, for tests that go
through discovery. Please don't commit real `manifest.json` files — they are
large and carry your model SQL and schema names.

Bug fixes want a test that fails before the change. Behaviour changes want the
relevant docs page updated in the same PR.

## Style

Match the surrounding code: standard library only, type hints on public
functions, dataclasses for records, and comments reserved for the *why* — the
non-obvious invariants (test attribution via `attached_node`, the cycle-safe
depth walk, the ownership rule) rather than restating the code.

## Changing the HTML template

`src/dbt_multidocs/templates/lineage.html` is vanilla JS with no build step —
edit it directly. Before opening the PR, build a page and check that it opens
from `file://` with no console errors and no network requests, in both light and
dark themes.

If you change the payload shape, update the schema block in
[docs/architecture.md](docs/architecture.md) too; that block is the contract
between `graph.py` and the template.

## Releasing

1. Update `CHANGELOG.md`.
2. Bump `version` in `pyproject.toml` and `__version__` in
   `src/dbt_multidocs/__init__.py` — they must match.
3. Tag `vX.Y.Z`. CI builds the wheel and checks the template is inside it.
