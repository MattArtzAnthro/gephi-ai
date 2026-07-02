"""Tests for the sigma.js viewer helpers."""
import textwrap

import pytest

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


def test_build_app_html_is_self_contained():
    from gephi_mcp_viewer import build_app_html
    html = build_app_html()
    assert html.startswith("<!DOCTYPE html>")
    assert "__GRAPHOLOGY_JS__" not in html and "__SIGMA_JS__" not in html
    assert "__GRAPH_DATA__" not in html          # data must NOT be inlined anymore
    assert len(html) > 100_000                    # vendored libs actually inlined
    # the MCP Apps handshake must be present
    assert "ui/initialize" in html
    assert "ui/notifications/initialized" in html
    assert "ui/notifications/tool-result" in html


def test_build_app_html_is_static():
    from gephi_mcp_viewer import build_app_html
    assert build_app_html() == build_app_html()


# No async markers needed: pyproject sets asyncio_mode = "auto".
async def test_view_graph_returns_structured_result(gexf_file, monkeypatch):
    async def fake_request(method, endpoint, params=None, json_data=None):
        assert endpoint == "/export/gexf"
        import shutil
        shutil.copy(gexf_file, json_data["file"])
        return {"success": True}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)

    result = await gephi_mcp.gephi_view_graph(title="My net")
    from mcp.types import CallToolResult
    assert isinstance(result, CallToolResult)
    assert result.isError is False
    assert "3 nodes" in result.content[0].text
    sc = result.structuredContent
    assert sc["title"] == "My net"
    assert {n["key"] for n in sc["nodes"]} == {"a", "b", "c"}


async def test_view_graph_export_failure_is_error(monkeypatch):
    async def fake_request(method, endpoint, params=None, json_data=None):
        return {"success": False, "error": "no workspace"}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)
    result = await gephi_mcp.gephi_view_graph()
    from mcp.types import CallToolResult
    assert isinstance(result, CallToolResult)
    assert result.isError is True
    assert "no workspace" in result.content[0].text


async def test_view_graph_tool_declares_app():
    tools = await gephi_mcp.mcp.list_tools()
    tool = next(t for t in tools if t.name == "gephi_view_graph")
    assert tool.meta == {"ui": {"resourceUri": "ui://gephi/graph-view"}}


async def test_app_resource_registered():
    contents = await gephi_mcp.mcp.read_resource("ui://gephi/graph-view")
    item = list(contents)[0]
    assert item.mime_type == "text/html;profile=mcp-app"
    assert "ui/initialize" in item.content
