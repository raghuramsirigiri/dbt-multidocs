"""Inline the graph payload into the packaged HTML template."""
from __future__ import annotations

import json
import pathlib

TEMPLATE_NAME = "lineage.html"


def default_template() -> pathlib.Path:
    try:
        from importlib.resources import files
        return pathlib.Path(str(files("dbt_multidocs") / "templates" / TEMPLATE_NAME))
    except Exception:  # pragma: no cover - very old importlib
        return pathlib.Path(__file__).resolve().parent / "templates" / TEMPLATE_NAME


def render(graph: dict, title: str, template: pathlib.Path = None) -> str:
    tpl = pathlib.Path(template) if template else default_template()
    html = tpl.read_text(encoding="utf8")
    payload = json.dumps(graph, separators=(",", ":"), ensure_ascii=False)
    # keep the JSON from terminating the host <script> block
    payload = payload.replace("</", "<\\/")
    return html.replace("__TITLE__", title).replace("__GRAPH_DATA__", payload)


def write(graph: dict, out: pathlib.Path, title: str, template=None) -> pathlib.Path:
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(graph, title, template), encoding="utf8")
    return out
