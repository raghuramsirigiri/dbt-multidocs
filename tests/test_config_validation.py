"""A key the tool does not read must say so.

Every key here is one the tool acts on, so a near miss - `project:` for
`projects:` - produces a config that parses, runs, and does nothing. That is
the failure mode this guards: it is indistinguishable from a bug until someone
reads the file character by character.
"""
import pytest

from dbt_multidocs import cli

from conftest import manifest, model, write_project

pytestmark = pytest.mark.usefixtures("yaml_parser")


def _write(tmp_path, text, name="dbt-multidocs.yml"):
    path = tmp_path / name
    path.write_text(text, encoding="utf8")
    return path


def test_a_valid_config_says_nothing():
    config = {
        "title": "T",
        "out": "docs/lineage.html",
        "projects": ["../a", {"path": "../b", "label": "B", "id": "b"}],
        "layers": ["raw", "staging"],
        "links": [{"from": "model.a.x", "to": "source.b.y", "remove": True}],
    }
    assert cli.check_config(config) == ([], [])


@pytest.mark.parametrize("typo, meant", [
    ("titel", "title"),
    ("project", "projects"),
    ("layer", "layers"),
    ("link", "links"),
])
def test_a_near_miss_key_is_named_and_corrected(typo, meant):
    errors, warnings = cli.check_config({typo: "x"})
    assert errors == []
    assert len(warnings) == 1
    assert typo in warnings[0]
    assert "did you mean '{}'".format(meant) in warnings[0]


def test_an_unrecognisable_key_is_still_reported():
    _, warnings = cli.check_config({"zzzz": 1})
    assert "unknown key 'zzzz'" in warnings[0]
    assert "did you mean" not in warnings[0]      # no bad guess


def test_unknown_keys_inside_entries_are_found():
    _, warnings = cli.check_config({
        "projects": [{"path": "../a", "labl": "A"}],
        "links": [{"form": "a", "to": "b"}],
    })
    assert any("projects[0]: unknown key 'labl'" in w and "'label'" in w for w in warnings)
    assert any("links[0]: unknown key 'form'" in w and "'from'" in w for w in warnings)


@pytest.mark.parametrize("config, expected", [
    ({"projects": "../a"}, "'projects' must be a list"),
    ({"layers": "raw"}, "'layers' must be a list"),
    ({"projects": [{"label": "no path here"}]}, "projects[0]: no 'path'"),
    ({"projects": [42]}, "projects[0]: expected a path or a mapping"),
    ({"links": ["model.a.x -> source.b.y"]}, "links[0]: expected a mapping"),
])
def test_a_malformed_shape_is_an_error_not_a_warning(config, expected):
    """These cannot be worked around, so the build must stop rather than guess."""
    errors, _ = cli.check_config(config)
    assert any(expected in e for e in errors), errors


def test_a_top_level_list_is_an_error():
    errors, _ = cli.check_config(["a", "b"])
    assert "expected a mapping" in errors[0]


def test_an_incomplete_link_warns_but_builds(tmp_path, capsys):
    """apply_links skips it, so the build is still usable - but say so."""
    write_project(tmp_path / "p", "p", manifest("p", nodes=[model("p", "a", "s")]),
                  {"nodes": {}, "sources": {}})
    cfg = _write(tmp_path, "projects:\n  - path: p\nlinks:\n  - from: model.p.a\n")
    rc = cli.main(["build", "--config", str(cfg), "--out", str(tmp_path / "o.html")])
    assert rc == 0
    assert "links[0]: no 'to'" in capsys.readouterr().err


def test_the_build_stops_on_a_malformed_config(tmp_path):
    cfg = _write(tmp_path, "projects: just_a_string\n")
    with pytest.raises(SystemExit) as exc:
        cli.main(["build", "--config", str(cfg)])
    assert "must be a list" in str(exc.value)


def test_a_typo_is_reported_before_the_failure_it_causes(tmp_path, capsys):
    """`project:` yields no projects; the warning has to precede that error."""
    cfg = _write(tmp_path, "project:\n  - path: p\n")
    with pytest.raises(SystemExit) as exc:
        cli.main(["build", "--config", str(cfg)])
    assert "No dbt projects found" in str(exc.value)
    err = capsys.readouterr().err
    assert "unknown key 'project'" in err and "did you mean 'projects'" in err


def test_strict_counts_config_warnings(tmp_path):
    write_project(tmp_path / "p", "p", manifest("p", nodes=[model("p", "a", "s")]),
                  {"nodes": {}, "sources": {}})
    cfg = _write(tmp_path, "titel: oops\nprojects:\n  - path: p\n")
    args = ["build", "--config", str(cfg), "--out", str(tmp_path / "o.html")]
    assert cli.main(args) == 0
    assert cli.main(args + ["--strict"]) == 2


def test_discover_reports_them_too(tmp_path, capsys):
    write_project(tmp_path / "p", "p", manifest("p", nodes=[model("p", "a", "s")]),
                  {"nodes": {}, "sources": {}})
    cfg = _write(tmp_path, "titel: oops\nprojects:\n  - path: p\n")
    assert cli.main(["discover", "--config", str(cfg)]) == 0
    assert "unknown key 'titel'" in capsys.readouterr().err
