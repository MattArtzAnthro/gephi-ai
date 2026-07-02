"""Tests for the sigma.js viewer helpers."""
import textwrap

import pytest
from mcp.types import EmbeddedResource, TextContent

import gephi_mcp
from gephi_mcp_viewer import parse_gexf

GEXF = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <gexf xmlns="http://gexf.net/1.3" xmlns:viz="http://gexf.net/1.3/viz" version="1.3">
      <graph defaultedgetype="directed">
        <attributes class="node">
          <attribute id="0" title="modularity_class" type="integer"/>
        </attributes>
        <nodes>
          <node id="a" label="Alice">
            <attvalues><attvalue for="0" value="1"/></attvalues>
            <viz:position x="10.5" y="20.0" z="0.0"/>
            <viz:color r="255" g="0" b="0"/>
            <viz:size value="7.5"/>
          </node>
          <node id="b" label="Bob">
            <viz:position x="-3.0" y="4.0" z="0.0"/>
          </node>
          <node id="c" label="Carol">
            <viz:position x="0.0" y="0.0" z="0.0"/>
          </node>
        </nodes>
        <edges>
          <edge id="0" source="a" target="b" weight="2.0"/>
          <edge id="1" source="b" target="c"/>
        </edges>
      </graph>
    </gexf>
""")


@pytest.fixture
def gexf_file(tmp_path):
    p = tmp_path / "g.gexf"
    p.write_text(GEXF, encoding="utf-8")
    return str(p)


def test_parse_gexf_nodes(gexf_file):
    g = parse_gexf(gexf_file)
    assert g["node_count_total"] == 3 and g["edge_count_total"] == 2
    assert g["directed"] is True and g["truncated"] is False
    alice = next(n for n in g["nodes"] if n["key"] == "a")
    assert alice["label"] == "Alice"
    assert alice["x"] == 10.5 and alice["y"] == 20.0  # y passes through (both y-up)
    assert alice["color"] == "rgb(255,0,0)" and alice["size"] == 7.5
    assert alice["attributes"] == {"modularity_class": "1"}


def test_parse_gexf_defaults(gexf_file):
    bob = next(n for n in parse_gexf(gexf_file)["nodes"] if n["key"] == "b")
    assert bob["color"] == "#999999" and bob["size"] == 5.0


def test_parse_gexf_edges(gexf_file):
    edges = parse_gexf(gexf_file)["edges"]
    assert {"source": "a", "target": "b", "size": 2.0, "color": None} in edges


def test_parse_gexf_truncates_by_degree(gexf_file):
    g = parse_gexf(gexf_file, max_nodes=2)
    assert g["truncated"] is True
    keys = {n["key"] for n in g["nodes"]}
    assert "b" in keys  # b has degree 2, always kept
    assert len(keys) == 2
    for e in g["edges"]:
        assert e["source"] in keys and e["target"] in keys


def test_build_html_is_self_contained(gexf_file):
    from gephi_mcp_viewer import build_html
    html = build_html(parse_gexf(gexf_file), title="My graph")
    assert html.startswith("<!DOCTYPE html>")
    assert "My graph" in html
    assert '"Alice"' in html                      # graph data inlined
    assert "__GRAPH_DATA__" not in html and "__TITLE__" not in html
    assert "__GRAPHOLOGY_JS__" not in html and "__SIGMA_JS__" not in html
    assert "__META__" not in html
    assert len(html) > 100_000                     # vendored libs actually inlined


def test_build_html_escapes_title(gexf_file):
    from gephi_mcp_viewer import build_html
    html = build_html(parse_gexf(gexf_file), title="<script>alert(1)</script>")
    assert "<script>alert(1)</script>" not in html


# No async markers needed: pyproject sets asyncio_mode = "auto".
async def test_view_graph_returns_ui_resource(gexf_file, monkeypatch):
    async def fake_request(method, endpoint, params=None, json_data=None):
        assert endpoint == "/export/gexf"
        import shutil
        shutil.copy(gexf_file, json_data["file"])
        return {"success": True}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)

    blocks = await gephi_mcp.gephi_view_graph()
    resource = blocks[0]
    assert isinstance(resource, EmbeddedResource)
    assert str(resource.resource.uri).startswith("ui://gephi/graph-view")
    assert resource.resource.mimeType == "text/html"
    assert '"Alice"' in resource.resource.text
    summary = blocks[1]
    assert isinstance(summary, TextContent)
    assert "3 nodes" in summary.text


async def test_view_graph_export_failure_returns_error(monkeypatch):
    async def fake_request(method, endpoint, params=None, json_data=None):
        return {"success": False, "error": "no workspace"}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)
    blocks = await gephi_mcp.gephi_view_graph()
    assert len(blocks) == 1 and isinstance(blocks[0], TextContent)
    assert "no workspace" in blocks[0].text


def test_build_html_escapes_script_breakout_in_data(gexf_file, tmp_path):
    malicious = GEXF.replace('label="Alice"', 'label="&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;"')
    p = tmp_path / "evil.gexf"
    p.write_text(malicious, encoding="utf-8")
    from gephi_mcp_viewer import build_html
    html = build_html(parse_gexf(str(p)))
    assert "</script><script>alert(1)" not in html
