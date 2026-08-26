"""Payload encoding: plain JSON by default, gzip+base64 once it gets large."""
import base64
import gzip
import json

from dbt_multidocs import graph, merge, render

from conftest import manifest, model
from test_merge_graph import _loaded


def _payload(n_models=1, sql=""):
    nodes = []
    for i in range(n_models):
        m = model("p", "m{}".format(i), "s")
        m["raw_code"] = sql or "select 1"
        nodes.append(m)
    return graph.build(merge.merge([_loaded("p", manifest("p", nodes=nodes))]))


def _extract(html):
    head, _, rest = html.partition('id="graph-data"')
    attrs, _, body = rest.partition(">")
    return attrs, body.split("</script>", 1)[0]


def test_small_payload_stays_plain_json():
    html, raw, stored, kind = render.render(_payload(), "T")
    assert kind == render.PLAIN_TYPE
    assert raw == stored
    attrs, body = _extract(html)
    assert "application/json" in attrs
    assert json.loads(body.replace("<\\/", "</"))["nodes"]


def test_large_payload_is_compressed_and_round_trips():
    big = _payload(n_models=40, sql="select " + ", ".join(
        "col_{0} as c{0}".format(i) for i in range(400)))
    html, raw, stored, kind = render.render(big, "T", compress="always")
    assert kind == render.GZIP_TYPE
    assert stored < raw                       # the whole point
    attrs, body = _extract(html)
    assert render.GZIP_TYPE in attrs
    back = json.loads(gzip.decompress(base64.b64decode(body.strip())).decode("utf8"))
    assert back == big                        # nothing lost in the round trip


def test_compressed_payload_cannot_close_the_script_tag():
    m = model("p", "a", "s")
    m["raw_code"] = "select 1 -- </script><script>alert(1)</script>"
    payload = graph.build(merge.merge([_loaded("p", manifest("p", nodes=[m]))]))
    html, _, _, _ = render.render(payload, "T", compress="always")
    _, body = _extract(html)
    assert "<" not in body                    # base64 has no '<' at all
    back = json.loads(gzip.decompress(base64.b64decode(body.strip())).decode("utf8"))
    assert "</script>" in back["nodes"][0]["sql_source"]   # preserved, just inert


def test_never_forces_plain_json_for_old_browsers():
    big = _payload(n_models=40, sql="select " + "x, " * 5000)
    _, _, _, kind = render.render(big, "T", compress="never")
    assert kind == render.PLAIN_TYPE


def test_auto_switches_on_size():
    small_payload = _payload()
    small_json, small_kind, small_raw, _ = render.encode(small_payload, "auto")
    assert small_raw < render.COMPRESS_THRESHOLD
    assert small_kind == render.PLAIN_TYPE

    # comfortably over the threshold, whatever it is set to
    per_model = render.COMPRESS_THRESHOLD // 20
    big_payload = _payload(n_models=40, sql="select " + "y, " * (per_model // 3))
    _, big_kind, big_raw, big_stored = render.encode(big_payload, "auto")
    assert big_raw > render.COMPRESS_THRESHOLD
    assert big_kind == render.GZIP_TYPE
    assert big_stored < big_raw


def test_template_has_no_unreplaced_placeholders():
    html, _, _, _ = render.render(_payload(), "My Title")
    for token in ("__TITLE__", "__GRAPH_DATA__", "__DATA_TYPE__"):
        assert token not in html
    assert "My Title" in html


def test_title_cannot_inject_markup():
    """The title reaches <title> and the header as text, so it must be escaped."""
    html, _, _, _ = render.render(_payload(), "</title><script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in html
    assert "&lt;/title&gt;&lt;script&gt;" in html
    # the real <title> element is still intact and still the only one
    assert html.count("<title>") == 1


def test_a_title_that_names_a_placeholder_does_not_eat_the_payload():
    """Placeholders are filled in one pass, so substituted text is never rescanned."""
    payload = _payload()
    html, _, _, _ = render.render(payload, "__GRAPH_DATA__")
    assert html.count(json.dumps(payload["nodes"][0]["id"])) == 1
    assert "<title>__GRAPH_DATA__</title>" in html
