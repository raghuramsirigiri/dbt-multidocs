"""The YAML reader, under both parsers.

`_yaml` uses PyYAML when it is importable and its own parser when it is not.
Which branch runs is a property of the user's environment, not of the code, so
every case here is checked against both - and the fallback is additionally
checked against PyYAML itself, which is the only definition of "correct" that
does not just re-state the implementation.
"""
import textwrap

import pytest

from dbt_multidocs import _yaml

pytestmark = pytest.mark.usefixtures("yaml_parser")

# What this tool actually has to read: its own config, and dbt_project.yml.
REAL_WORLD = {
    "config": """
        title: Enterprise dbt Lineage
        out: docs/lineage.html
        projects:
          - path: ../dbt_staging
            label: Staging
          - path: ../dbt_core
            id: core
          - ../bare_string_project
        layers:
          - raw|seed
          - staging|stg
        links:
          - from: model.up.dim_customers
            to: source.down.core.dim_customers
          - from: a.y
            to: b.z
            remove: true
    """,
    "dbt_project": """
        name: 'my_project'
        version: '1.0.0'
        profile: my_profile
        model-paths: ["models"]
        models:
          my_project:
            +materialized: view
            staging:
              +schema: stg
    """,
    "comments_and_quotes": """
        title: "A: colon inside the value"    # trailing comment
        # a whole-line comment
        out: "docs/#anchor.html"
        projects:
          - path: './relative/path'   # '#' above is data, this one is not
    """,
}


def _load(name):
    return _yaml.loads(textwrap.dedent(REAL_WORLD[name]).strip() + "\n")


def test_config_round_trips():
    data = _load("config")
    assert data["title"] == "Enterprise dbt Lineage"
    assert data["out"] == "docs/lineage.html"
    assert data["projects"][0] == {"path": "../dbt_staging", "label": "Staging"}
    assert data["projects"][1] == {"path": "../dbt_core", "id": "core"}
    assert data["projects"][2] == "../bare_string_project"     # bare string entry
    assert data["layers"] == ["raw|seed", "staging|stg"]
    assert data["links"][1] == {"from": "a.y", "to": "b.z", "remove": True}


def test_dbt_project_name_is_readable():
    """discovery reads `name:` out of dbt_project.yml to key the whole graph."""
    data = _load("dbt_project")
    assert data["name"] == "my_project"
    assert data["models"]["my_project"]["staging"]["+schema"] == "stg"


def test_comments_are_stripped_but_not_inside_quotes():
    data = _load("comments_and_quotes")
    assert data["title"] == "A: colon inside the value"
    # a '#' inside a quoted scalar is data, not the start of a comment
    assert data["out"] == "docs/#anchor.html"
    assert data["projects"] == [{"path": "./relative/path"}]


def test_scalars_are_typed():
    data = _yaml.loads("a: 1\nb: 2.5\nc: true\nd: false\ne: null\nf: text\n")
    assert data == {"a": 1, "b": 2.5, "c": True, "d": False, "e": None, "f": "text"}


def test_empty_and_garbage_do_not_raise():
    assert _yaml.loads("") in ({}, None)
    assert isinstance(_yaml.loads("# only a comment\n"), (dict, type(None)))


@pytest.mark.parametrize("name", sorted(REAL_WORLD))
def test_the_fallback_agrees_with_pyyaml(name):
    """The no-dependency parser must not quietly disagree with the real one."""
    pyyaml = pytest.importorskip("yaml", reason="nothing to compare against")
    text = textwrap.dedent(REAL_WORLD[name]).strip() + "\n"

    _yaml._pyyaml = None
    try:
        mine = _yaml.loads(text)
    finally:
        _yaml._pyyaml = pyyaml
    assert mine == pyyaml.safe_load(text)
