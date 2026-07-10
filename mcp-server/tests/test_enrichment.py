"""Tests for the profile/QA enrichment release: weight stats, degree Gini,
assortativity, expected clustering, robust extent + outliers, separation in
visual QA, and the run_layout finite-positions guard."""

import json
import math
import textwrap

import pytest

import gephi_mcp
from gephi_mcp_viewer import analyze_graph
from gephi_mcp_viewer.profile import structural_profile


def make_graph(nodes, edges, directed=False):
    """Build a graph dict in parse_gexf's shape from compact specs.

    nodes: list of (key, x, y) or (key, x, y, {attrs})
    edges: list of (source, target) or (source, target, weight)
    """
    ns = []
    for spec in nodes:
        key, x, y = spec[0], spec[1], spec[2]
        attrs = spec[3] if len(spec) > 3 else {}
        ns.append({"key": key, "label": key, "x": float(x), "y": float(y),
                   "size": 10.0, "color": "rgb(42,120,214)", "attributes": attrs})
    es = []
    for spec in edges:
        s, t = spec[0], spec[1]
        w = float(spec[2]) if len(spec) > 2 else 1.0
        es.append({"source": s, "target": t, "size": w, "color": None,
                   "spells": None})
    return {"nodes": ns, "edges": es, "directed": directed,
            "node_count_total": len(ns), "edge_count_total": len(es),
            "truncated": False}


# ─── weight detection (bug fix) ──────────────────────────────

def test_weighted_true_when_edge_weights_vary():
    g = make_graph([("a", 0, 0), ("b", 1, 0), ("c", 2, 0)],
                   [("a", "b", 1.0), ("b", "c", 3.0)])
    assert structural_profile(g)["weighted"] is True


def test_weighted_false_when_weights_uniform():
    g = make_graph([("a", 0, 0), ("b", 1, 0), ("c", 2, 0)],
                   [("a", "b"), ("b", "c")])
    assert structural_profile(g)["weighted"] is False


# ─── weight distribution stats + heavy-tail flag ─────────────

def test_weight_stats_reported_for_weighted_graph():
    g = make_graph([("a", 0, 0), ("b", 1, 0), ("c", 2, 0), ("d", 3, 0)],
                   [("a", "b", 1.0), ("b", "c", 2.0), ("c", "d", 3.0)])
    w = structural_profile(g)["weights"]
    assert w["min"] == 1.0 and w["max"] == 3.0 and w["median"] == 2.0
    assert w["heavy_tailed"] is False


def test_heavy_tailed_weights_raise_log_transform_flag():
    g = make_graph([("a", 0, 0), ("b", 1, 0), ("c", 2, 0), ("d", 3, 0)],
                   [("a", "b", 1.0), ("b", "c", 1.0), ("c", "d", 200.0)])
    p = structural_profile(g)
    assert p["weights"]["heavy_tailed"] is True
    assert any("log-transform" in f for f in p["flags"])


def test_mild_weights_raise_no_weight_flag():
    g = make_graph([("a", 0, 0), ("b", 1, 0), ("c", 2, 0), ("d", 3, 0)],
                   [("a", "b", 1.0), ("b", "c", 2.0), ("c", "d", 3.0)])
    assert not any("log-transform" in f for f in structural_profile(g)["flags"])


def test_unweighted_graph_has_no_weights_block():
    g = make_graph([("a", 0, 0), ("b", 1, 0)], [("a", "b")])
    assert "weights" not in structural_profile(g)


# ─── degree Gini ─────────────────────────────────────────────

def test_gini_zero_for_equal_degrees():
    # 4-cycle: every node degree 2
    g = make_graph([("a", 0, 0), ("b", 1, 0), ("c", 1, 1), ("d", 0, 1)],
                   [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")])
    assert structural_profile(g)["degree"]["gini"] == pytest.approx(0.0, abs=1e-9)


def test_gini_high_for_star():
    # star: hub degree 10, leaves degree 1 -> strong inequality
    nodes = [("hub", 0, 0)] + [(f"n{i}", i, 1) for i in range(10)]
    edges = [("hub", f"n{i}") for i in range(10)]
    gini = structural_profile(make_graph(nodes, edges))["degree"]["gini"]
    assert gini > 0.35


# ─── degree assortativity ────────────────────────────────────

def test_assortativity_negative_one_for_star():
    nodes = [("hub", 0, 0)] + [(f"n{i}", i, 1) for i in range(5)]
    edges = [("hub", f"n{i}") for i in range(5)]
    r = structural_profile(make_graph(nodes, edges))["degree"]["assortativity"]
    assert r == pytest.approx(-1.0, abs=1e-6)


def test_assortativity_positive_one_for_disjoint_cliques():
    # K3 + K5 disjoint: every edge joins equal-degree nodes of two classes
    nodes = [(f"a{i}", i, 0) for i in range(3)] + [(f"b{i}", i, 1) for i in range(5)]
    edges = ([(f"a{i}", f"a{j}") for i in range(3) for j in range(i + 1, 3)] +
             [(f"b{i}", f"b{j}") for i in range(5) for j in range(i + 1, 5)])
    r = structural_profile(make_graph(nodes, edges))["degree"]["assortativity"]
    assert r == pytest.approx(1.0, abs=1e-6)


def test_assortativity_none_for_regular_graph():
    # 4-cycle: all degrees equal, correlation undefined
    g = make_graph([("a", 0, 0), ("b", 1, 0), ("c", 1, 1), ("d", 0, 1)],
                   [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")])
    assert structural_profile(g)["degree"]["assortativity"] is None


def test_disassortative_hub_graph_raises_dissuade_hubs_flag():
    # big disassortative star (n >= 50 gate)
    nodes = [("hub", 0, 0)] + [(f"n{i}", i, 1) for i in range(60)]
    edges = [("hub", f"n{i}") for i in range(60)]
    p = structural_profile(make_graph(nodes, edges))
    assert any("distributedAttraction" in f for f in p["flags"])


# ─── expected clustering baseline ────────────────────────────

def test_expected_clustering_matches_hand_computation():
    # star K1,4: n=5, degrees [4,1,1,1,1]
    # <k>=1.6, <k^2>=4 -> ((4-1.6)^2)/(5*1.6^3) = 0.28125
    nodes = [("hub", 0, 0)] + [(f"n{i}", i, 1) for i in range(4)]
    edges = [("hub", f"n{i}") for i in range(4)]
    p = structural_profile(make_graph(nodes, edges))
    assert p["clustering_expected_random"] == pytest.approx(0.28125, rel=1e-6)


# ─── visual QA: robust extent + outliers ─────────────────────

def grid_nodes(n_side=6, spacing=20.0, group=None):
    nodes = []
    for i in range(n_side):
        for j in range(n_side):
            attrs = {"group": group} if group is not None else {}
            nodes.append((f"g{i}_{j}", i * spacing, j * spacing, attrs))
    return nodes


def test_position_outlier_flagged_and_export_uses_robust_extent():
    nodes = grid_nodes() + [("far", 100000.0, 0.0)]
    g = make_graph(nodes, [("g0_0", "g0_1"), ("g0_0", "far")])
    result = analyze_graph(g)
    out = result["extent"]["outliers"]
    assert out["count"] == 1 and "far" in out["nodes"]
    # suggested export follows the robust (near-square) cloud, not the blowout
    sug = result["extent"]["suggested_export"]
    assert max(sug["width"], sug["height"]) / min(sug["width"], sug["height"]) < 3
    assert any("outside the main cloud" in w for w in result["warnings"])


def test_no_outliers_on_compact_layout():
    g = make_graph(grid_nodes(), [("g0_0", "g0_1")])
    assert analyze_graph(g)["extent"]["outliers"]["count"] == 0


def test_non_finite_positions_warn_without_crashing():
    nodes = [("a", 0, 0), ("b", 10, 0), ("c", float("inf"), 0),
             ("d", float("nan"), 5)]
    g = make_graph(nodes, [("a", "b")])
    result = analyze_graph(g)
    assert any("non-finite" in w for w in result["warnings"])
    assert math.isfinite(result["extent"]["width"])


# ─── visual QA: separation score with partition ──────────────

def two_cluster_graph(separated=True):
    nodes, edges = [], []
    for i in range(12):
        nodes.append((f"a{i}", i, 0, {"group": "A"}))
        bx = 1000 + i if separated else i + 0.5
        nodes.append((f"b{i}", bx, 0, {"group": "B"}))
    for i in range(11):
        edges.append((f"a{i}", f"a{i+1}"))
        edges.append((f"b{i}", f"b{i+1}"))
    return make_graph(nodes, edges)


def test_separation_reported_and_low_when_clusters_apart():
    result = analyze_graph(two_cluster_graph(separated=True),
                           partition_column="group")
    sep = result["partition"]["separation"]
    assert sep is not None and sep < 0.5


def test_separation_near_one_when_clusters_interleaved():
    result = analyze_graph(two_cluster_graph(separated=False),
                           partition_column="group")
    sep = result["partition"]["separation"]
    assert sep is not None and 0.6 < sep < 1.5


# ─── profile tool: clustering_vs_random ratio ────────────────

GEXF_STAR = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <gexf xmlns="http://gexf.net/1.3" xmlns:viz="http://gexf.net/1.3/viz" version="1.3">
      <graph defaultedgetype="undirected">
        <nodes>
          <node id="hub" label="hub"/>
          <node id="n0" label="n0"/><node id="n1" label="n1"/>
          <node id="n2" label="n2"/><node id="n3" label="n3"/>
        </nodes>
        <edges>
          <edge id="0" source="hub" target="n0"/>
          <edge id="1" source="hub" target="n1"/>
          <edge id="2" source="hub" target="n2"/>
          <edge id="3" source="hub" target="n3"/>
        </edges>
      </graph>
    </gexf>
""")


async def test_profile_reports_clustering_vs_random_ratio(rec):
    rec.responses = [
        {"success": True, "content": GEXF_STAR},              # /export/gexf
        {"success": True, "modularity": 0.4, "communities": 2},
        {"success": True, "average_clustering_coefficient": 0.5625},
    ]
    out = json.loads(await gephi_mcp.gephi_profile_graph())
    # star K1,4 expectation is 0.28125; observed 0.5625 -> ratio 2.0
    assert out["clustering_expected_random"] == pytest.approx(0.28125, rel=1e-4)
    assert out["clustering_vs_random"] == pytest.approx(2.0, rel=1e-3)


# ─── run_layout finite-positions guard ───────────────────────

GEXF_TEMPLATE = textwrap.dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <gexf xmlns="http://gexf.net/1.3" xmlns:viz="http://gexf.net/1.3/viz" version="1.3">
      <graph defaultedgetype="undirected">
        <nodes>
          <node id="a" label="a"><viz:position x="{ax}" y="0.0" z="0.0"/></node>
          <node id="b" label="b"><viz:position x="5.0" y="5.0" z="0.0"/></node>
        </nodes>
        <edges><edge id="0" source="a" target="b"/></edges>
      </graph>
    </gexf>
""")


class Recorder:
    def __init__(self):
        self.calls = []
        self.responses = []

    async def __call__(self, method, endpoint, params=None, json_data=None,
                       timeout=None):
        self.calls.append({"method": method, "endpoint": endpoint,
                           "params": params, "json": json_data})
        if self.responses:
            return self.responses.pop(0)
        return {"success": True}


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    monkeypatch.setattr(gephi_mcp.gephi, "request", r)

    async def no_sleep(_):
        return None

    monkeypatch.setattr(gephi_mcp.asyncio, "sleep", no_sleep)
    return r


async def test_sync_layout_reports_explosion_on_non_finite_positions(rec):
    rec.responses = [
        {"success": True},                       # POST /layout/run
        {"running": False},                      # GET /layout/status
        {"success": True,                        # POST /export/gexf (guard)
         "content": GEXF_TEMPLATE.format(ax="NaN")},
    ]
    out = json.loads(await gephi_mcp.gephi_run_layout(
        "ForceAtlas 2", iterations=10, sync=True))
    assert out["layout_exploded"]["non_finite_nodes"] == 1
    assert "a" in out["layout_exploded"]["sample"]
    assert "Random Layout" in out["layout_exploded"]["fix"]


async def test_sync_layout_flags_absurd_but_finite_coordinates(rec):
    rec.responses = [
        {"success": True},
        {"running": False},
        {"success": True, "content": GEXF_TEMPLATE.format(ax="1e37")},
    ]
    out = json.loads(await gephi_mcp.gephi_run_layout(
        "ForceAtlas 2", iterations=10, sync=True))
    assert out["layout_exploded"]["non_finite_nodes"] == 1


async def test_sync_layout_clean_positions_add_no_explosion_block(rec):
    rec.responses = [
        {"success": True},
        {"running": False},
        {"success": True, "content": GEXF_TEMPLATE.format(ax="3.0")},
    ]
    out = json.loads(await gephi_mcp.gephi_run_layout(
        "ForceAtlas 2", iterations=10, sync=True))
    assert "layout_exploded" not in out
    assert out["status"] == "completed"
