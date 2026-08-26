import json
import os
import pathlib

import pytest

from dbt_multidocs import cli, discovery

from conftest import manifest, model, write_project


def test_discover_finds_projects_under_a_search_root(two_repos, capsys):
    common = two_repos[0].parents[1]
    assert cli.main(["discover", "--search-root", str(common)]) == 0
    out = capsys.readouterr().out
    assert "2 project(s)" in out and "up" in out and "down" in out


def test_build_end_to_end_from_unrelated_dirs(two_repos, tmp_path, capsys):
    out = tmp_path / "site" / "lineage.html"
    payload = tmp_path / "graph.json"
    rc = cli.main([
        "build",
        "--project", str(two_repos[0]),
        "--project", str(two_repos[1]),
        "--out", str(out), "--json", str(payload),
    ])
    assert rc == 0
    assert out.exists() and out.stat().st_size > 50_000
    g = json.loads(payload.read_text(encoding="utf8"))
    assert g["stats"]["projects"] == 2
    assert g["stats"]["inferred"] == 1
    assert "written" in capsys.readouterr().out


def test_no_stitch_leaves_the_projects_disconnected(two_repos, tmp_path):
    payload = tmp_path / "g.json"
    cli.main(["build", "--project", str(two_repos[0]), "--project", str(two_repos[1]),
              "--out", str(tmp_path / "l.html"), "--json", str(payload), "--no-stitch"])
    g = json.loads(payload.read_text(encoding="utf8"))
    assert g["project_edges"] == []
    assert g["stats"]["cross_edges"] == 0


def test_result_does_not_depend_on_cwd_or_path_style(two_repos, tmp_path, monkeypatch):
    def run(cwd, paths, dest):
        monkeypatch.chdir(cwd)
        cli.main(["build", "--project", paths[0], "--project", paths[1],
                  "--out", str(tmp_path / "x.html"), "--json", str(dest)])
        g = json.loads(pathlib.Path(dest).read_text(encoding="utf8"))
        g["stats"].pop("generated_at", None)
        return g

    absolute = run(tmp_path, [str(two_repos[0]), str(two_repos[1])], tmp_path / "a.json")

    # same projects, reached by relative paths from a different working directory
    elsewhere = two_repos[0].parents[1]
    rel = [os.path.relpath(p, elsewhere) for p in two_repos]
    relative = run(elsewhere, rel, tmp_path / "b.json")

    assert absolute == relative


def test_missing_manifest_fails_with_guidance(tmp_path, capsys):
    root = tmp_path / "broken"
    root.mkdir()
    (root / "dbt_project.yml").write_text("name: broken\n", encoding="utf8")
    with pytest.raises(SystemExit) as exc:
        cli.main(["build", "--project", str(root), "--out", str(tmp_path / "o.html")])
    assert "dbt docs generate" in str(exc.value)


def test_strict_turns_warnings_into_a_failure(tmp_path):
    doc = manifest("p", nodes=[model("p", "a", "s")])
    root = write_project(tmp_path / "p", "p", doc, catalog=None)   # no catalog -> warns
    args = ["build", "--project", str(root), "--out", str(tmp_path / "o.html")]
    assert cli.main(args) == 0
    assert cli.main(args + ["--strict"]) == 2


def test_no_projects_found_explains_how_to_point_at_them(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc:
        cli.main(["build"])
    assert "--project" in str(exc.value)


def test_duplicate_project_names_get_distinct_ids(tmp_path):
    doc = manifest("same", nodes=[model("same", "a", "s")])
    a = write_project(tmp_path / "one" / "same", "same", doc, {"nodes": {}, "sources": {}})
    b = write_project(tmp_path / "two" / "same", "same", doc, {"nodes": {}, "sources": {}})
    ids = [p.id for p in discovery.resolve(paths=[a, b])]
    assert len(set(ids)) == 2


def test_manifest_path_accepted_directly(two_repos):
    direct = two_repos[0] / "target" / "manifest.json"
    project = discovery.from_path(direct)
    assert project.has_manifest and project.has_catalog


def test_target_dir_accepted_directly(two_repos):
    project = discovery.from_path(two_repos[0] / "target")
    assert project.project_name == "up"


def test_version_reports_what_a_bug_report_needs(capsys):
    """--version is the one line the issue template asks people to paste."""
    import dbt_multidocs

    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert dbt_multidocs.__version__ in out
    assert "dbt-multidocs" in out and "Python" in out


def test_the_packaged_version_matches_the_module():
    """pyproject reads __version__ dynamically; this catches that wiring breaking."""
    metadata = pytest.importorskip("importlib.metadata")
    import dbt_multidocs

    try:
        installed = metadata.version("dbt-multidocs")
    except metadata.PackageNotFoundError:            # running from a source tree
        pytest.skip("dbt-multidocs is not installed in this environment")
    assert installed == dbt_multidocs.__version__
