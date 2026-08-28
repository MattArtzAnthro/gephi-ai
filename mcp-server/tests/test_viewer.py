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


def test_parse_gexf_accepts_content_string():
    g = parse_gexf(GEXF)
    assert g["node_count_total"] == 3 and g["edge_count_total"] == 2


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
    assert {"source": "a", "target": "b", "size": 2.0, "color": None, "spells": None} in edges


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
        if endpoint == "/preview/settings":
            return {"success": False}
        assert endpoint == "/export/gexf"
        import shutil
        shutil.copy(gexf_file, json_data["file"])
        return {"success": True}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)

    result = await gephi_mcp.gephi_view_graph(title="My net")
    from mcp.types import CallToolResult
    assert isinstance(result, CallToolResult)
    assert result.is_error is False
    assert "3 nodes" in result.content[0].text
    sc = result.structured_content
    assert sc["title"] == "My net"
    assert {n["key"] for n in sc["nodes"]} == {"a", "b", "c"}


async def test_view_graph_export_failure_is_error(monkeypatch):
    async def fake_request(method, endpoint, params=None, json_data=None):
        return {"success": False, "error": "no workspace"}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)
    result = await gephi_mcp.gephi_view_graph()
    from mcp.types import CallToolResult
    assert isinstance(result, CallToolResult)
    assert result.is_error is True
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


# ── cluster labeling ─────────────────────────────────────────────

def test_pick_cluster_hubs(qa_graph):
    from gephi_mcp_viewer import pick_cluster_hubs
    hubs = pick_cluster_hubs(qa_graph, "team")
    assert hubs == {"A": "a1", "B": "b1"}   # highest degree in each group


async def test_label_clusters(gexf_file, monkeypatch, tmp_path):
    qa_path = tmp_path / "qa2.gexf"
    qa_path.write_text(QA_GEXF, encoding="utf-8")
    calls = []

    async def fake_request(method, endpoint, params=None, json_data=None):
        calls.append({"endpoint": endpoint, "json": json_data})
        if endpoint == "/export/gexf":
            import shutil
            shutil.copy(str(qa_path), json_data["file"])
        return {"success": True, "properties_set": 5}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)

    import json as _json
    out = _json.loads(await gephi_mcp.gephi_label_clusters(
        partition_column="team", names={"A": "Alpha Team", "B": "Beta Team"}))

    backup = next(c for c in calls if c["endpoint"] == "/graph/nodes/attributes")
    assert len(backup["json"]["updates"]) == 6
    assert all("label_backup" in u["attributes"] for u in backup["json"]["updates"])

    label_calls = {c["json"]["id"]: c["json"]["label"]
                   for c in calls if c["endpoint"] == "/graph/node/label"}
    assert label_calls["a1"] == "Alpha Team" and label_calls["b1"] == "Beta Team"
    assert label_calls["a2"] == "" and label_calls["b3"] == ""

    preview = next(c for c in calls if c["endpoint"] == "/preview/settings")
    assert preview["json"]["node.label.show"] is True
    # caption font scales with layout extent (small fixture -> floor of 12)
    assert preview["json"]["node.label.font"] == "Arial 12 Bold"
    assert preview["json"]["node.label.proportinalSize"] is True
    assert out["labeled"] == {"A": {"node": "a1", "label": "Alpha Team"},
                              "B": {"node": "b1", "label": "Beta Team"}}
    assert out["blanked"] == 4 and out["caption_font"] == 12


async def test_label_clusters_restore(monkeypatch, tmp_path):
    restore_gexf = QA_GEXF.replace(
        '<attribute id="0" title="team" type="string"/>',
        '<attribute id="0" title="team" type="string"/><attribute id="9" title="label_backup" type="string"/>'
    ).replace(
        '<attvalues><attvalue for="0" value="A"/></attvalues>',
        '<attvalues><attvalue for="0" value="A"/><attvalue for="9" value="OrigA"/></attvalues>', 1)
    p = tmp_path / "restore.gexf"
    p.write_text(restore_gexf, encoding="utf-8")
    calls = []

    async def fake_request(method, endpoint, params=None, json_data=None):
        calls.append({"endpoint": endpoint, "json": json_data})
        if endpoint == "/export/gexf":
            import shutil
            shutil.copy(str(p), json_data["file"])
        return {"success": True, "properties_set": 1}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)

    import json as _json
    out = _json.loads(await gephi_mcp.gephi_label_clusters(partition_column="team", restore=True))
    label_calls = {c["json"]["id"]: c["json"]["label"]
                   for c in calls if c["endpoint"] == "/graph/node/label"}
    assert label_calls == {"a1": "OrigA"}   # only nodes with a backup are restored
    preview = next(c for c in calls if c["endpoint"] == "/preview/settings")
    assert preview["json"]["node.label.show"] is False
    assert out["restored"] == 1


def test_pick_cluster_hubs_prefer_size():
    from gephi_mcp_viewer import pick_cluster_hubs
    graph = {
        "nodes": [
            {"key": "hi-deg", "label": "", "x": 0, "y": 0, "size": 10, "color": "#333", "attributes": {"g": "1"}},
            {"key": "big", "label": "", "x": 1, "y": 1, "size": 30, "color": "#333", "attributes": {"g": "1"}},
            {"key": "other", "label": "", "x": 2, "y": 0, "size": 5, "color": "#333", "attributes": {"g": "1"}},
        ],
        "edges": [
            {"source": "hi-deg", "target": "other", "size": 1, "color": None},
            {"source": "hi-deg", "target": "big", "size": 1, "color": None},
        ],
        "directed": False, "node_count_total": 3, "edge_count_total": 2, "truncated": False,
    }
    assert pick_cluster_hubs(graph, "g") == {"1": "hi-deg"}
    assert pick_cluster_hubs(graph, "g", prefer="size") == {"1": "big"}


# ── GEXF spec conformance (gephi/gexf) ───────────────────────────

def test_parse_gexf_attribute_defaults_and_alpha(tmp_path):
    gexf = """<?xml version="1.0" encoding="UTF-8"?>
    <gexf xmlns="http://gexf.net/1.3" xmlns:viz="http://gexf.net/1.3/viz" version="1.3">
      <graph defaultedgetype="undirected">
        <attributes class="node">
          <attribute id="0" title="team" type="string"><default>Unassigned</default></attribute>
        </attributes>
        <nodes>
          <node id="x" label="X">
            <attvalues><attvalue for="0" value="A"/></attvalues>
            <viz:position x="0" y="0" z="0"/>
            <viz:color r="255" g="0" b="0" a="0.5"/>
            <viz:size value="10"/>
          </node>
          <node id="y" label="Y">
            <viz:position x="1" y="1" z="0"/>
            <viz:color r="10" g="20" b="30"/>
            <viz:size value="10"/>
          </node>
        </nodes>
        <edges><edge id="0" source="x" target="y"/></edges>
      </graph>
    </gexf>"""
    p = tmp_path / "defaults.gexf"
    p.write_text(gexf, encoding="utf-8")
    g = parse_gexf(str(p))
    x = next(n for n in g["nodes"] if n["key"] == "x")
    y = next(n for n in g["nodes"] if n["key"] == "y")
    assert x["attributes"]["team"] == "A"
    assert y["attributes"]["team"] == "Unassigned"   # spec: default applies
    assert x["color"] == "rgba(255,0,0,0.5)"           # alpha preserved
    assert y["color"] == "rgb(10,20,30)"               # no alpha -> rgb


def test_analyze_flags_overspread_layout():
    from gephi_mcp_viewer import analyze_graph
    # nodes sized 10-20 scattered over a 10,000-unit extent: specks in whitespace
    graph = {
        "nodes": [
            {"key": f"n{i}", "label": "", "x": float(i * 1000), "y": 0.0,
             "size": 15.0, "color": "#333333", "attributes": {}}
            for i in range(11)
        ],
        "edges": [], "directed": False,
        "node_count_total": 11, "edge_count_total": 0, "truncated": False,
    }
    d = analyze_graph(graph)
    assert any("over-spread" in w for w in d["warnings"])
    # a proportionate layout must NOT warn
    for n in graph["nodes"]:
        n["x"] /= 10.0
    d2 = analyze_graph(graph)
    assert not any("over-spread" in w for w in d2["warnings"])


# ── dynamic GEXF (time) ──────────────────────────────────────────

def test_parse_gexf_dynamics(tmp_path):
    gexf = """<?xml version="1.0" encoding="UTF-8"?>
    <gexf xmlns="http://gexf.net/1.3" xmlns:viz="http://gexf.net/1.3/viz" version="1.3">
      <graph defaultedgetype="undirected" mode="dynamic" timeformat="double">
        <nodes>
          <node id="a" label="A" start="1.0" end="5.0">
            <viz:position x="0" y="0" z="0"/><viz:size value="10"/>
          </node>
          <node id="b" label="B">
            <spells><spell start="2.0" end="3.0"/><spell start="4.0"/></spells>
            <viz:position x="1" y="1" z="0"/><viz:size value="10"/>
          </node>
          <node id="c" label="C">
            <viz:position x="2" y="0" z="0"/><viz:size value="10"/>
          </node>
        </nodes>
        <edges><edge id="0" source="a" target="b" start="2.5"/></edges>
      </graph>
    </gexf>"""
    p = tmp_path / "dyn.gexf"
    p.write_text(gexf, encoding="utf-8")
    g = parse_gexf(str(p))
    a = next(n for n in g["nodes"] if n["key"] == "a")
    b = next(n for n in g["nodes"] if n["key"] == "b")
    c = next(n for n in g["nodes"] if n["key"] == "c")
    assert a["spells"] == [[1.0, 5.0]]
    assert b["spells"] == [[2.0, 3.0], [4.0, None]]
    assert c["spells"] is None                      # static node: always visible
    assert g["edges"][0]["spells"] == [[2.5, None]]
    assert g["dynamic"] is True
    assert g["time_min"] == 1.0 and g["time_max"] == 5.0


def test_parse_gexf_static_has_no_dynamics(gexf_file):
    g = parse_gexf(gexf_file)
    assert g["dynamic"] is False
    assert all(n["spells"] is None for n in g["nodes"])


async def test_view_graph_captions_param(gexf_file, monkeypatch):
    async def fake_request(method, endpoint, params=None, json_data=None):
        if endpoint == "/preview/settings":
            return {"success": False}
        import shutil
        shutil.copy(gexf_file, json_data["file"])
        return {"success": True}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)
    result = await gephi_mcp.gephi_view_graph(
        caption_column="team", caption_names={"A": "Alpha"})
    sc = result.structured_content
    assert sc["captions"] == {"column": "team", "names": {"A": "Alpha"}}
    result2 = await gephi_mcp.gephi_view_graph()
    assert "captions" not in result2.structured_content


def test_app_html_has_interactive_features():
    from gephi_mcp_viewer import build_app_html
    html = build_app_html()
    for marker in ("tools/call", "ui/message", "btn-refresh", "btn-ego", "btn-ask",
                   "captions", "timeslider", "inSpells", "graphToViewport"):
        assert marker in html, f"missing {marker}"
    assert "__GRAPH_DATA__" not in html and len(html) > 100_000


# ─── similarity layout ────────────────────────────────────────

def _ring_graph(n=12):
    nodes = [{"key": f"n{i}", "attributes": {}} for i in range(n)]
    edges = [{"source": f"n{i}", "target": f"n{(i+1) % n}", "weight": 1.0} for i in range(n)]
    return {"nodes": nodes, "edges": edges}


def test_similarity_positions_spectral():
    from gephi_mcp_viewer.similarity import compute_similarity_positions
    positions, method = compute_similarity_positions(_ring_graph(), projection="spectral")
    assert method == "spectral"
    assert len(positions) == 12
    xs = [p["x"] for p in positions]
    assert max(xs) > min(xs)  # actually spread out
    assert all(set(p) == {"id", "x", "y"} for p in positions)


def test_similarity_positions_rejects_tiny_and_edgeless():
    import pytest

    from gephi_mcp_viewer.similarity import compute_similarity_positions
    with pytest.raises(ValueError):
        compute_similarity_positions({"nodes": [{"key": "a"}], "edges": []})
    with pytest.raises(ValueError):
        compute_similarity_positions(
            {"nodes": [{"key": f"n{i}"} for i in range(6)], "edges": []})


def test_similarity_ring_geometry_is_meaningful():
    # in a ring, immediate neighbors should sit closer than antipodes
    import math

    from gephi_mcp_viewer.similarity import compute_similarity_positions
    positions, _ = compute_similarity_positions(_ring_graph(12), projection="spectral")
    pos = {p["id"]: (p["x"], p["y"]) for p in positions}
    d = lambda a, b: math.dist(pos[a], pos[b])
    assert d("n0", "n1") < d("n0", "n6")


# ─── structural profile ───────────────────────────────────────

def test_structural_profile_facts():
    from gephi_mcp_viewer.profile import structural_profile
    g = _ring_graph(10)
    g["nodes"].append({"key": "lonely", "attributes": {}})  # isolate
    p = structural_profile(g)
    assert p["nodes"] == 11 and p["edges"] == 10
    assert p["isolates"] == 1
    assert p["components"]["count"] == 2
    assert p["degree"]["max"] == 2 and p["degree"]["min"] == 0
    assert any("isolated" in f for f in p["flags"])


def test_structural_profile_hub_flag():
    from gephi_mcp_viewer.profile import structural_profile
    # star graph: one hub touching everyone
    n = 40
    g = {"nodes": [{"key": f"n{i}"} for i in range(n)],
         "edges": [{"source": "n0", "target": f"n{i}"} for i in range(1, n)]}
    p = structural_profile(g)
    assert p["degree"]["max"] == n - 1
    assert any("hub-dominated" in f for f in p["flags"])


def test_structural_profile_leaf_majority_flag():
    from gephi_mcp_viewer.profile import structural_profile
    n = 300
    g = {"nodes": [{"key": f"n{i}"} for i in range(n)],
         "edges": [{"source": "n0", "target": f"n{i}"} for i in range(1, n)]}
    p = structural_profile(g)
    assert any("leaf-majority" in f for f in p["flags"])


# ── Regression: partition column resolves by id OR title (2026-07-08) ──
# Gephi's modularity column is id="modularity_class" / title="Modularity Class".
# color_by_partition (Java) resolves by id; visual_qa/label_clusters/community_layout
# (Python) used to resolve by title only, so the canonical "modularity_class" made
# them see zero groups. parse_gexf now exposes attr_key and resolve_column_key.
_ID_TITLE_GEXF = """\
<?xml version="1.0" encoding="UTF-8"?>
<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">
  <graph defaultedgetype="undirected">
    <attributes class="node">
      <attribute id="modularity_class" title="Modularity Class" type="integer"/>
    </attributes>
    <nodes>
      <node id="a"><attvalues><attvalue for="modularity_class" value="0"/></attvalues></node>
      <node id="b"><attvalues><attvalue for="modularity_class" value="0"/></attvalues></node>
      <node id="c"><attvalues><attvalue for="modularity_class" value="1"/></attvalues></node>
      <node id="d"><attvalues><attvalue for="modularity_class" value="1"/></attvalues></node>
    </nodes>
    <edges>
      <edge id="0" source="a" target="b"/>
      <edge id="1" source="c" target="d"/>
    </edges>
  </graph>
</gexf>"""


def test_attr_key_maps_id_title_and_normalized():
    from gephi_mcp_viewer import resolve_column_key
    g = parse_gexf(_ID_TITLE_GEXF)
    # node attributes are keyed by title
    assert g["nodes"][0]["attributes"]["Modularity Class"] == "0"
    # resolve_column_key accepts id, title, and normalized variants
    for name in ("modularity_class", "Modularity Class", "MODULARITY_CLASS", " modularity class "):
        assert resolve_column_key(g, name) == "Modularity Class"
    # a genuinely absent column falls through unchanged
    assert resolve_column_key(g, "nope") == "nope"


def test_analyze_graph_partition_accepts_id():
    from gephi_mcp_viewer import analyze_graph
    g = parse_gexf(_ID_TITLE_GEXF)
    # both the id and the title must find the 2 real groups (not zero)
    for name in ("modularity_class", "Modularity Class"):
        p = analyze_graph(g, partition_column=name)["partition"]
        assert p["groups"] == 2, f"{name!r} -> {p}"
        assert p["verdict"] == "strong"


def test_pick_cluster_hubs_accepts_id():
    from gephi_mcp_viewer import pick_cluster_hubs
    g = parse_gexf(_ID_TITLE_GEXF)
    hubs = pick_cluster_hubs(g, "modularity_class")
    assert set(hubs.keys()) == {"0", "1"}


def test_visual_qa_flags_untouched_graph():
    """A graph straight after loading (uniform size, one color) gets the
    'looks untouched' warning; a styled one does not."""
    from gephi_mcp_viewer import analyze_graph
    untouched = {"directed": False,
                 "nodes": [{"key": str(i), "label": str(i), "x": float(i), "y": 0.0,
                            "size": 10.0, "color": "#999999", "attributes": {}}
                           for i in range(6)],
                 "edges": []}
    d = analyze_graph(untouched)
    assert any(w.startswith("looks untouched") for w in d["warnings"])
    styled = {"directed": False,
              "nodes": [{"key": str(i), "label": str(i), "x": float(i), "y": 0.0,
                         "size": 10.0 + i, "color": "#2a78d6" if i % 2 else "#1baf7a",
                         "attributes": {}} for i in range(6)],
              "edges": []}
    d = analyze_graph(styled)
    assert not any(w.startswith("looks untouched") for w in d["warnings"])


TITLED_GEXF = """<?xml version="1.0" encoding="UTF-8"?>
<gexf xmlns="http://www.gexf.net/1.2draft" xmlns:viz="http://www.gexf.net/1.2draft/viz" version="1.2">
  <graph defaultedgetype="undirected">
    <attributes class="node">
      <attribute id="modularity_class" title="Modularity Class" type="integer"/>
    </attributes>
    <nodes>
      <node id="a" label="A"><attvalues><attvalue for="modularity_class" value="0"/></attvalues></node>
      <node id="b" label="B"><attvalues><attvalue for="modularity_class" value="1"/></attvalues></node>
    </nodes>
    <edges><edge id="e" source="a" target="b"/></edges>
  </graph>
</gexf>"""

PREVIEW = {"success": True, "settings": {
    "edge.opacity": 25.0, "edge.curved": True, "edge.color": "source", "edge.thickness": 2.0,
    "node.border.width": 0.3, "node.opacity": 100.0, "node.label.show": False, "arrow.size": 0.0}}


def _titled_host(tmp_path, monkeypatch, preview_ok=True):
    p = tmp_path / "t.gexf"
    p.write_text(TITLED_GEXF, encoding="utf-8")

    async def fake_request(method, endpoint, params=None, json_data=None, timeout=None):
        if endpoint == "/export/gexf":
            import shutil
            shutil.copy(str(p), json_data["file"])
            return {"success": True}
        if endpoint == "/preview/settings":
            return PREVIEW if preview_ok else {"success": False, "error": "no workspace"}
        raise AssertionError(endpoint)
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)


async def test_view_graph_resolves_caption_column_by_id(tmp_path, monkeypatch):
    """Callers pass the column id (modularity_class); node attributes are keyed by
    title (Modularity Class). The app must receive the key that is actually there,
    or captions silently never render."""
    _titled_host(tmp_path, monkeypatch)
    r = await gephi_mcp.gephi_view_graph(caption_column="modularity_class")
    sc = r.structured_content
    assert sc["captions"]["column"] == "Modularity Class"
    assert all("Modularity Class" in n["attributes"] for n in sc["nodes"])


async def test_view_graph_carries_preview_settings(tmp_path, monkeypatch):
    """The in-chat view should draw the way Gephi's own export would: the tool
    passes the preview settings the user set, normalized for the app."""
    _titled_host(tmp_path, monkeypatch)
    r = await gephi_mcp.gephi_view_graph()
    pv = r.structured_content["preview"]
    assert pv == {"edge_opacity": 0.25, "edge_curved": True, "edge_color": "source",
                  "edge_thickness": 2.0, "node_border_width": 0.3, "node_opacity": 1.0,
                  "label_show": False, "arrow_size": 0.0}


async def test_view_graph_without_preview_settings_still_renders(tmp_path, monkeypatch):
    _titled_host(tmp_path, monkeypatch, preview_ok=False)
    r = await gephi_mcp.gephi_view_graph()
    assert r.is_error is False
    assert "preview" not in r.structured_content


def test_app_html_declares_its_host_contract():
    """Tripwire for the MCP Apps surface the page depends on. If a rename drops
    one of these, the host silently stops receiving that message."""
    from gephi_mcp_viewer import build_app_html
    html = build_app_html()
    for method in ("ui/initialize", "ui/notifications/initialized", "ui/notifications/tool-result",
                   "ui/notifications/host-context-changed", "ui/request-display-mode",
                   "ui/update-model-context", "ui/message", "tools/call"):
        assert method in html, method
    # The page must be self-contained: vendored libraries inlined, no placeholders left.
    assert "__SIGMA_JS__" not in html and "__GRAPHOLOGY_JS__" not in html
    assert "gephi_focus_view" in html and "gephi_view_graph" in html
