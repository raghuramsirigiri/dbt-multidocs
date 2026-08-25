## What this changes

<!-- One or two sentences. Link the issue if there is one. -->

## Why

<!-- The behaviour that was wrong or missing. -->

## Checklist

- [ ] `pytest` passes
- [ ] New behaviour has a test using synthetic manifests in `tests/conftest.py`
      (no real `manifest.json` files committed - they are large and leak schema names)
- [ ] If graph output changed: `--json` payload shape is documented in `docs/architecture.md`
- [ ] If the HTML template changed: the page still opens from `file://` with no
      console errors and no network requests
- [ ] No new runtime dependencies (stdlib only is a deliberate constraint)
