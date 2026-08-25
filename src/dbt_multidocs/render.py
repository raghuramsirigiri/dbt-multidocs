"""Inline the graph payload into the packaged HTML template.

Large graphs are stored gzipped and base64'd rather than as raw JSON: model SQL
and column metadata compress extremely well, and a 3000-model graph drops from
8.8MB to 0.46MB, which is the difference between a file you can email and one
you cannot. The page decodes it with DecompressionStream, so this still costs no
dependencies and no network.
"""
from __future__ import annotations

import base64
import gzip
import json
import pathlib

TEMPLATE_NAME = "lineage.html"

# Below this, raw JSON is smaller after base64's 33% overhead is priced in, and
# a plain-JSON page works in any browser. Above it, compression is a clear win.
COMPRESS_THRESHOLD = 1_000_000

PLAIN_TYPE = "application/json"
GZIP_TYPE = "application/gzip-base64"


def default_template() -> pathlib.Path:
    try:
        from importlib.resources import files
        return pathlib.Path(str(files("dbt_multidocs") / "templates" / TEMPLATE_NAME))
    except Exception:  # pragma: no cover - very old importlib
        return pathlib.Path(__file__).resolve().parent / "templates" / TEMPLATE_NAME


def encode(graph: dict, compress: str = "auto"):
    """Return (payload_text, script_type, raw_bytes, stored_bytes)."""
    raw = json.dumps(graph, separators=(",", ":"), ensure_ascii=False)
    raw_bytes = len(raw.encode("utf8"))

    use_gzip = compress == "always" or (compress == "auto" and raw_bytes > COMPRESS_THRESHOLD)
    if not use_gzip:
        # keep the JSON from terminating the host <script> block
        return raw.replace("</", "<\\/"), PLAIN_TYPE, raw_bytes, raw_bytes

    blob = base64.b64encode(gzip.compress(raw.encode("utf8"), 9)).decode("ascii")
    # base64 contains no '<', so it cannot close the script tag
    return blob, GZIP_TYPE, raw_bytes, len(blob)


def render(graph: dict, title: str, template: pathlib.Path = None, compress: str = "auto"):
    """Return (html, raw_bytes, stored_bytes, script_type)."""
    tpl = pathlib.Path(template) if template else default_template()
    html = tpl.read_text(encoding="utf8")
    payload, script_type, raw_bytes, stored = encode(graph, compress)
    html = (html.replace("__TITLE__", title)
                .replace("__DATA_TYPE__", script_type)
                .replace("__GRAPH_DATA__", payload))
    return html, raw_bytes, stored, script_type


def write(graph: dict, out: pathlib.Path, title: str, template=None, compress: str = "auto"):
    out = pathlib.Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    html, raw_bytes, stored, script_type = render(graph, title, template, compress)
    out.write_text(html, encoding="utf8")
    return {"path": out, "raw_bytes": raw_bytes, "stored_bytes": stored,
            "compressed": script_type == GZIP_TYPE}
