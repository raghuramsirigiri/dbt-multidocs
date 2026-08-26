"""Paths inside a config file resolve against the config file, not the CWD."""
import json

import pytest

from dbt_multidocs import cli

from conftest import manifest, model, write_project

# the config is read by whichever YAML parser the environment supplies
pytestmark = pytest.mark.usefixtures("yaml_parser")


def _project(tmp_path, name="p"):
    doc = manifest(name, nodes=[model(name, "a", "s")])
    return write_project(tmp_path / "repos" / name, name, doc, {"nodes": {}, "sources": {}})


def test_config_out_is_relative_to_the_config_file(tmp_path, monkeypatch):
    _project(tmp_path)
    cfg_dir = tmp_path / "conf"
    cfg_dir.mkdir()
    (cfg_dir / "dbt-multidocs.yml").write_text(
        "out: site/lineage.html\nprojects:\n  - path: ../repos/p\n", encoding="utf8"
    )

    elsewhere = tmp_path / "somewhere_else"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert cli.main(["build", "--config", str(cfg_dir / "dbt-multidocs.yml")]) == 0

    assert (cfg_dir / "site" / "lineage.html").exists()
    assert not (elsewhere / "site").exists()


def test_out_flag_beats_config_and_is_relative_to_cwd(tmp_path, monkeypatch):
    _project(tmp_path)
    cfg = tmp_path / "c.yml"
    cfg.write_text("out: from_config.html\nprojects:\n  - path: repos/p\n", encoding="utf8")

    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    assert cli.main(["build", "--config", str(cfg), "--out", "from_flag.html"]) == 0

    assert (work / "from_flag.html").exists()
    assert not (tmp_path / "from_config.html").exists()


def test_config_project_paths_are_relative_to_the_config_file(tmp_path, monkeypatch):
    _project(tmp_path)
    cfg = tmp_path / "conf" / "c.yml"
    cfg.parent.mkdir()
    cfg.write_text("projects:\n  - path: ../repos/p\n", encoding="utf8")

    monkeypatch.chdir(tmp_path / "repos")           # a directory the path is NOT relative to
    payload = tmp_path / "g.json"
    assert cli.main(["build", "--config", str(cfg),
                     "--out", str(tmp_path / "o.html"), "--json", str(payload)]) == 0
    g = json.loads(payload.read_text(encoding="utf8"))
    assert [p["name"] for p in g["packages"]] == ["p"]
