"""Command line entry point: `dbt-multidocs build` / `dbt-multidocs discover`."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from . import _yaml, artifacts, discovery, render, stitch
from . import graph as graph_mod
from . import merge as merge_mod

DEFAULT_OUT = pathlib.Path("dbt-docs") / "lineage.html"


def _load_config(path):
    if not path:
        return {}, None
    p = pathlib.Path(path).expanduser().resolve()
    if not p.exists():
        raise SystemExit("config not found: {}".format(p))
    if p.suffix.lower() == ".json":
        return json.loads(p.read_text(encoding="utf8")), p.parent
    return _yaml.load_file(p), p.parent


def _common(ap):
    ap.add_argument("--project", action="append", default=[], metavar="PATH",
                    help="a dbt project dir, its target/ dir, or a manifest.json (repeatable)")
    ap.add_argument("--search-root", action="append", default=[], metavar="DIR",
                    help="walk DIR for dbt_project.yml files (repeatable)")
    ap.add_argument("--depth", type=int, default=discovery.DEFAULT_DEPTH,
                    help="how many levels --search-root descends (default: %(default)s)")
    ap.add_argument("--config", metavar="FILE", help="dbt-multidocs.yml (or .json)")
    ap.add_argument("--verbose", "-v", action="store_true")


def _resolve(args, config, config_dir):
    projects = discovery.resolve(
        paths=args.project,
        search_roots=args.search_root,
        depth=args.depth,
        config=config,
        config_dir=config_dir,
    )
    if not projects:
        raise SystemExit(
            "No dbt projects found.\n"
            "  point at them explicitly:  dbt-multidocs build --project PATH --project PATH\n"
            "  or sweep a directory:      dbt-multidocs build --search-root DIR"
        )
    return projects


def cmd_discover(args) -> int:
    config, config_dir = _load_config(args.config)
    projects = _resolve(args, config, config_dir)
    print("{} project(s):".format(len(projects)))
    missing = 0
    for p in projects:
        if p.has_manifest:
            state = "manifest + catalog" if p.has_catalog else "manifest only (no catalog)"
        else:
            state = "NO MANIFEST - run `dbt docs generate`"
            missing += 1
        print("  {:<24} {:<32} {}".format(p.id, state, p.root or p.manifest_path))
        if args.verbose:
            print("      manifest: {}".format(p.manifest_path))
            print("      catalog : {}".format(p.catalog_path))
            print("      origin  : {}".format(p.origin))
    return 1 if missing else 0


def cmd_build(args) -> int:
    config, config_dir = _load_config(args.config)
    projects = _resolve(args, config, config_dir)

    loaded, warnings = [], []
    for p in projects:
        try:
            art = artifacts.load(p)
        except artifacts.ArtifactError as exc:
            raise SystemExit("error: {}".format(exc)) from exc
        if not p.project_name and art.manifest.get("metadata", {}).get("project_name"):
            # pointed straight at a manifest with no dbt_project.yml beside it -
            # the manifest knows its own name better than the filename does
            taken = {q.id for q in projects if q is not p}
            named = art.manifest["metadata"]["project_name"]
            if named not in taken:
                if p.label == discovery._pretty_label(p.id):
                    p.label = discovery._pretty_label(named)
                p.id = art.project_id = named
        loaded.append(art)
        warnings.extend(art.warnings)

    merged = merge_mod.merge(loaded)

    inferred = []
    if not args.no_stitch:
        result = stitch.stitch(merged, scope=args.stitch_scope)
        inferred = result.edges
        warnings.extend(result.warnings)
    inferred, unresolved = stitch.apply_links(merged, inferred, config.get("links"))
    warnings.extend("config link unresolved: {}".format(u) for u in unresolved)
    if merged.orphans:
        warnings.append(
            "{} node(s) not claimed by any project's own manifest "
            "(imported packages?); grouped by package_name instead".format(len(merged.orphans))
        )
    warnings.extend(merged.conflicts)

    labels = {p.id: p.label for p in projects}
    payload = graph_mod.build(
        merged,
        stitched_edges=inferred,
        title_layers=config.get("layers"),
        project_labels=labels,
    )

    title = args.title or config.get("title") or "Multi-Project dbt Lineage"
    if args.out:
        out = pathlib.Path(args.out)                      # a flag is relative to the CWD
    elif config.get("out"):
        # like projects[].path, a config path is relative to the config file itself,
        # so a checked-in config writes to the same place from any directory
        out = pathlib.Path(config["out"])
        if not out.is_absolute() and config_dir:
            out = pathlib.Path(config_dir) / out
    else:
        out = DEFAULT_OUT
    out = out.expanduser().resolve()
    template = pathlib.Path(args.template).expanduser().resolve() if args.template else None
    written = render.write(payload, out, title, template, compress=args.compress)

    if args.json:
        jp = pathlib.Path(args.json).expanduser().resolve()
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf8")

    s = payload["stats"]
    for p, art in zip(projects, loaded):
        own = sum(1 for uid, o in merged.owner.items() if o == p.id)
        print("  {:<24} {:>4} nodes   {}".format(p.id, own, art.manifest_path))
    size_kb = out.stat().st_size / 1024
    if written["compressed"]:
        print("written  : {}  ({:.0f} KB, payload gzipped {:.1f} MB -> {:.0f} KB)".format(
            out, size_kb, written["raw_bytes"] / 1048576, written["stored_bytes"] / 1024))
    else:
        print("written  : {}  ({:.0f} KB)".format(out, size_kb))
    print("graph    : {} nodes / {} edges across {} projects".format(
        len(payload["nodes"]), len(payload["edges"]), s["projects"]))
    print("           {} models, {} seeds, {} sources, {} tests".format(
        s["models"], s["seeds"], s["sources"], s["tests"]))
    print("           {} cross-project edges ({} inferred from source() relations)".format(
        s["cross_edges"], s["inferred"]))
    if args.json:
        print("payload  : {}".format(args.json))

    for w in warnings:
        print("warning  : {}".format(w), file=sys.stderr)
    if warnings and args.strict:
        print("error: --strict and {} warning(s)".format(len(warnings)), file=sys.stderr)
        return 2
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="dbt-multidocs",
        description="Combine several independent dbt projects into one lineage page.",
    )
    sub = ap.add_subparsers(dest="cmd")

    b = sub.add_parser("build", help="write the combined lineage page")
    _common(b)
    b.add_argument("--out", "-o", metavar="FILE", help="default: dbt-docs/lineage.html")
    b.add_argument("--title")
    b.add_argument("--template", metavar="FILE", help="override the packaged HTML template")
    b.add_argument("--no-stitch", action="store_true",
                   help="use only declared ref() edges; do not infer cross-project links")
    b.add_argument("--stitch-scope", choices=("all", "cross"), default="all",
                   help="'all' also links a project's own seeds to its sources")
    b.add_argument("--strict", action="store_true", help="exit non-zero if anything warned")
    b.add_argument("--json", metavar="FILE", help="also dump the graph payload")
    b.add_argument("--compress", choices=("auto", "always", "never"), default="auto",
                   help="store the payload gzipped+base64 (default: auto, above ~1MB). "
                        "'never' keeps plain JSON for browsers without DecompressionStream")
    b.set_defaults(func=cmd_build)

    d = sub.add_parser("discover", help="list the projects and their artifact status")
    _common(d)
    d.set_defaults(func=cmd_discover)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
