import json

from dbt_multidocs import cli

from conftest import manifest, model


def test_bare_manifest_takes_its_name_from_the_metadata(tmp_path):
    """Pointed at a manifest with no dbt_project.yml, the filename is a poor id."""
    doc = manifest("proj_dashboards", nodes=[model("proj_dashboards", "a", "s")])
    bare = tmp_path / "index.json"
    bare.write_text(json.dumps(doc), encoding="utf8")

    payload = tmp_path / "g.json"
    cli.main(["build", "--project", str(bare),
              "--out", str(tmp_path / "o.html"), "--json", str(payload)])
    g = json.loads(payload.read_text(encoding="utf8"))
    assert [p["name"] for p in g["packages"]] == ["proj_dashboards"]
    assert g["packages"][0]["label"] == "dashboards"
