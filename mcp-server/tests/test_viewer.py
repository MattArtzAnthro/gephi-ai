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


# ── visual QA diagnostics ────────────────────────────────────────

QA_GEXF = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <gexf xmlns="http://gexf.net/1.3" xmlns:viz="http://gexf.net/1.3/viz" version="1.3">
      <graph defaultedgetype="undirected">
        <attributes class="node">
          <attribute id="0" title="team" type="string"/>
        </attributes>
        <nodes>
          <node id="a1" label="a1"><attvalues><attvalue for="0" value="A"/></attvalues><viz:position x="0" y="0" z="0"/><viz:color r="42" g="120" b="214"/><viz:size value="20"/></node>
          <node id="a2" label="a2"><attvalues><attvalue for="0" value="A"/></attvalues><viz:position x="10" y="5" z="0"/><viz:color r="42" g="120" b="214"/><viz:size value="12"/></node>
          <node id="a3" label="a3"><attvalues><attvalue for="0" value="A"/></attvalues><viz:position x="5" y="10" z="0"/><viz:color r="42" g="120" b="214"/><viz:size value="12"/></node>
          <node id="b1" label="b1"><attvalues><attvalue for="0" value="B"/></attvalues><viz:position x="100" y="0" z="0"/><viz:color r="227" g="73" b="72"/><viz:size value="20"/></node>
          <node id="b2" label="b2"><attvalues><attvalue for="0" value="B"/></attvalues><viz:position x="110" y="5" z="0"/><viz:color r="227" g="73" b="72"/><viz:size value="12"/></node>
          <node id="b3" label="b3"><attvalues><attvalue for="0" value="B"/></attvalues><viz:position x="105" y="10" z="0"/><viz:color r="255" g="245" b="240"/><viz:size value="3"/></node>
        </nodes>
        <edges>
          <edge id="0" source="a1" target="a2"/>
          <edge id="1" source="a1" target="a3"/>
          <edge id="2" source="a2" target="a3"/>
          <edge id="3" source="b1" target="b2"/>
          <edge id="4" source="b1" target="b3"/>
          <edge id="5" source="a1" target="b1"/>
        </edges>
      </graph>
    </gexf>
""")


@pytest.fixture
def qa_graph(tmp_path):
    p = tmp_path / "qa.gexf"
    p.write_text(QA_GEXF, encoding="utf-8")
    return parse_gexf(str(p), max_nodes=10000)


def test_analyze_partition_strength(qa_graph):
    from gephi_mcp_viewer import analyze_graph
    d = analyze_graph(qa_graph, partition_column="team")
    part = d["partition"]
    assert part["column"] == "team"
    assert abs(part["within_fraction"] - 5 / 6) < 0.01
    assert abs(part["random_baseline"] - 0.5) < 0.01   # two equal groups
    assert part["verdict"] == "strong"


def test_analyze_flags_visual_problems(qa_graph):
    from gephi_mcp_viewer import analyze_graph
    d = analyze_graph(qa_graph)
    assert d["nodes"] == 6 and d["edges"] == 6
    assert d["sizes"]["min"] == 3.0 and d["sizes"]["max"] == 20.0
    # b3 is size 3 (invisible) and near-white — both must be flagged
    warns = " ".join(d["warnings"])
    assert "size" in warns.lower()
    assert "near-white" in warns.lower() or "contrast" in warns.lower()
    # extent/aspect and a suggested export size are present
    assert d["extent"]["aspect"] > 0
    assert d["extent"]["suggested_export"]["width"] > 0


def test_analyze_fake_partition():
    # 4 nodes, 2 groups, ALL edges between groups: within fraction 0 -> fake
    graph = {
        "nodes": [
            {"key": "x1", "label": "x1", "x": 0, "y": 0, "size": 10, "color": "#333333", "attributes": {"g": "1"}},
            {"key": "x2", "label": "x2", "x": 1, "y": 1, "size": 10, "color": "#333333", "attributes": {"g": "1"}},
            {"key": "y1", "label": "y1", "x": 2, "y": 0, "size": 10, "color": "#444444", "attributes": {"g": "2"}},
            {"key": "y2", "label": "y2", "x": 3, "y": 1, "size": 10, "color": "#444444", "attributes": {"g": "2"}},
        ],
        "edges": [
            {"source": "x1", "target": "y1", "size": 1, "color": None},
            {"source": "x2", "target": "y2", "size": 1, "color": None},
            {"source": "x1", "target": "y2", "size": 1, "color": None},
        ],
        "directed": False, "node_count_total": 4, "edge_count_total": 3, "truncated": False,
    }
    from gephi_mcp_viewer import analyze_graph as ag
    d = ag(graph, partition_column="g")
    assert d["partition"]["verdict"] == "none"
    assert any("misleading" in w for w in d["warnings"])


async def test_visual_qa_tool(gexf_file, monkeypatch):
    async def fake_request(method, endpoint, params=None, json_data=None):
        assert endpoint == "/export/gexf"
        import shutil
        shutil.copy(gexf_file, json_data["file"])
        return {"success": True}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)
    import json as _json
    out = _json.loads(await gephi_mcp.gephi_visual_qa(partition_column="modularity_class"))
    assert out["nodes"] == 3
    assert "partition" in out and "warnings" in out
