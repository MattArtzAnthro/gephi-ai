"""The two computed layouts end to end: community discs and similarity, plus the projection ladder.

Gephi is replaced at its HTTP boundary by a stand-in that serves a known graph as inline GEXF and
records what the tool pushes back.
"""

from __future__ import annotations

import json
import sys
import types

import numpy as np
import pytest

import gephi_mcp
from gephi_mcp_viewer.similarity import _project, compute_similarity_positions


def two_stars_gexf(leaves=12, with_edges=True):
    """Two hubs joined to each other, each with its own leaves; a community column says which."""
    nodes, edges = [], []
    for c, hub in enumerate(("h0", "h1")):
        nodes.append((hub, c))
        for i in range(leaves):
            leaf = f"{hub}l{i}"
            nodes.append((leaf, c))
            edges.append((hub, leaf))
    edges.append(("h0", "h1"))
    body = "".join(
        f'<node id="{n}" label="{n}"><attvalues><attvalue for="mc" value="{c}"/></attvalues>'
        f'<viz:position x="{(i * 37) % 101}" y="{(i * 53) % 97}" z="0"/></node>'
        for i, (n, c) in enumerate(nodes))
    links = "".join(f'<edge id="e{i}" source="{s}" target="{t}"/>' for i, (s, t) in enumerate(edges)
                    if with_edges)
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<gexf xmlns="http://gexf.net/1.3" xmlns:viz="http://gexf.net/1.3/viz" version="1.3">'
            '<graph defaultedgetype="undirected"><attributes class="node">'
            '<attribute id="mc" title="Modularity Class" type="integer"/></attributes>'
            f'<nodes>{body}</nodes><edges>{links}</edges></graph></gexf>')


class FakeGephi:
    def __init__(self, gexf, push_ok=True, export_ok=True):
        self.gexf = gexf
        self.push_ok = push_ok
        self.export_ok = export_ok
        self.calls = []
        self.status_polls = 0

    async def __call__(self, method, endpoint, params=None, json_data=None, timeout=None):
        self.calls.append((endpoint, json_data))
        if endpoint == "/export/gexf":
            if not self.export_ok:
                return {"success": False, "error": "No project open"}
            return {"success": True, "content": self.gexf}
        if endpoint == "/graph/nodes/positions":
            return {"success": True} if self.push_ok else {"success": False, "error": "busy"}
        if endpoint == "/layout/status":
            self.status_polls += 1
            return {"success": True, "running": self.status_polls < 2}
        return {"success": True}

    def endpoints(self):
        return [e for e, _ in self.calls]


@pytest.fixture
def fast_sleep(monkeypatch):
    async def no_wait(_):
        return None
    monkeypatch.setattr(gephi_mcp.asyncio, "sleep", no_wait)


# ─── Community discs ─────────────────────────────────────────────

async def test_community_layout_pushes_discs_waits_for_noverlap_and_reports_separation(
        monkeypatch, fast_sleep):
    fake = FakeGephi(two_stars_gexf())
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)

    out = json.loads(await gephi_mcp.gephi_community_layout(partition_column="Modularity Class"))

    assert out["success"], out
    assert out["discs"] == 2
    assert out["nodes_positioned"] == 26
    assert out["separation_after"] < out["separation_before"]
    assert "means nothing" in out["reading_note"]
    pushed = next(j for e, j in fake.calls if e == "/graph/nodes/positions")
    assert len(pushed["positions"]) == 26
    assert fake.status_polls == 2, "the tool stopped waiting while Noverlap still ran"
    assert fake.endpoints()[-1] == "/view/focus"


async def test_community_layout_without_the_partition_says_so_and_moves_nothing(monkeypatch):
    fake = FakeGephi(two_stars_gexf())
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)

    out = json.loads(await gephi_mcp.gephi_community_layout(partition_column="team"))

    assert out["success"] is False
    assert "/graph/nodes/positions" not in fake.endpoints()


async def test_community_layout_passes_on_a_failed_export_or_push(monkeypatch):
    fake = FakeGephi(two_stars_gexf(), export_ok=False)
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    out = json.loads(await gephi_mcp.gephi_community_layout())
    assert out == {"success": False, "error": "No project open"}

    fake = FakeGephi(two_stars_gexf(), push_ok=False)
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    out = json.loads(await gephi_mcp.gephi_community_layout(partition_column="Modularity Class"))
    assert out == {"success": False, "error": "busy"}
    assert "/layout/run" not in fake.endpoints()


# ─── Similarity layout ──────────────────────────────────────────

async def test_similarity_layout_asked_for_a_missing_projection_names_the_fallback(monkeypatch):
    monkeypatch.setitem(sys.modules, "umap", None)
    fake = FakeGephi(two_stars_gexf())
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)

    out = json.loads(await gephi_mcp.gephi_similarity_layout(projection="umap"))

    assert out["success"] is False
    assert "projection='spectral'" in out["error"]
    assert "/graph/nodes/positions" not in fake.endpoints()


async def test_similarity_layout_auto_says_when_it_fell_back_to_spectral(monkeypatch):
    # "auto" promises the best available projection; without umap-learn and scikit-learn
    # that is spectral, and the result must say so and how to get the others.
    monkeypatch.setitem(sys.modules, "umap", None)
    monkeypatch.setitem(sys.modules, "sklearn.manifold", None)
    monkeypatch.setattr(gephi_mcp.gephi, "request", FakeGephi(two_stars_gexf()))

    out = json.loads(await gephi_mcp.gephi_similarity_layout(projection="auto", finish_noverlap=False))

    assert out["projection_used"] == "spectral"
    assert "umap-learn" in out["projection_note"] and "scikit-learn" in out["projection_note"]


async def test_similarity_layout_asked_for_spectral_carries_no_fallback_note(monkeypatch):
    monkeypatch.setattr(gephi_mcp.gephi, "request", FakeGephi(two_stars_gexf()))

    out = json.loads(await gephi_mcp.gephi_similarity_layout(projection="spectral", finish_noverlap=False))

    assert "projection_note" not in out


async def test_similarity_layout_reading_note_does_not_promise_roles(monkeypatch):
    # Laplacian eigenmaps place closely linked nodes together, so map neighbours are often
    # directly connected: proximity is closeness, not role.
    monkeypatch.setattr(gephi_mcp.gephi, "request", FakeGephi(two_stars_gexf()))

    out = json.loads(await gephi_mcp.gephi_similarity_layout(projection="spectral", finish_noverlap=False))

    assert "directly connected" in out["reading_note"]
    assert "not a role" in out["reading_note"]


async def test_similarity_layout_on_a_graph_without_edges_is_refused(monkeypatch):
    fake = FakeGephi(two_stars_gexf(with_edges=False))
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)

    out = json.loads(await gephi_mcp.gephi_similarity_layout(projection="spectral"))

    assert out["success"] is False
    assert "needs edges" in out["error"]


async def test_similarity_layout_passes_on_a_failed_push(monkeypatch):
    fake = FakeGephi(two_stars_gexf(), push_ok=False)
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)

    out = json.loads(await gephi_mcp.gephi_similarity_layout(projection="spectral"))

    assert out == {"success": False, "error": "busy"}


# ─── The projection ladder ──────────────────────────────────────

def _emb(n=12):
    rng = np.random.default_rng(3)
    return rng.normal(size=(n, 4))


def test_auto_falls_back_to_spectral_when_neither_package_is_installed(monkeypatch):
    monkeypatch.setitem(sys.modules, "umap", None)
    monkeypatch.setitem(sys.modules, "sklearn", None)
    monkeypatch.setitem(sys.modules, "sklearn.manifold", None)

    xy, method = _project(_emb(), "auto")

    assert method == "spectral"
    assert xy.shape == (12, 2)
    assert np.allclose(xy.mean(axis=0), 0)


@pytest.mark.parametrize("projection, module", [("umap", "umap"), ("tsne", "sklearn.manifold")])
def test_a_projection_asked_for_by_name_raises_when_its_package_is_missing(
        monkeypatch, projection, module):
    monkeypatch.setitem(sys.modules, module, None)
    if module == "sklearn.manifold":
        monkeypatch.setitem(sys.modules, "sklearn", None)

    with pytest.raises(ImportError):
        _project(_emb(), projection)


def test_umap_is_used_first_when_installed(monkeypatch):
    used = {}

    class UMAP:
        def __init__(self, **kwargs):
            used.update(kwargs)

        def fit_transform(self, emb):
            return emb[:, :2] * 2

    monkeypatch.setitem(sys.modules, "umap", types.SimpleNamespace(UMAP=UMAP))

    xy, method = _project(_emb(), "auto")

    assert method == "umap"
    assert used["n_neighbors"] == 11, "neighbours are capped below the node count"


def test_tsne_is_used_when_umap_is_missing(monkeypatch):
    used = {}

    class TSNE:
        def __init__(self, **kwargs):
            used.update(kwargs)

        def fit_transform(self, emb):
            return emb[:, :2]

    monkeypatch.setitem(sys.modules, "umap", None)
    monkeypatch.setitem(sys.modules, "sklearn", types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, "sklearn.manifold", types.SimpleNamespace(TSNE=TSNE))

    xy, method = _project(_emb(), "auto")

    assert method == "tsne"
    assert used["perplexity"] < 12, "perplexity must stay below the node count"


def test_a_large_graph_takes_the_sparse_eigensolver_path():
    n = 1600
    edges = [{"source": f"n{i}", "target": f"n{(i + 1) % n}"} for i in range(n)]
    edges += [{"source": f"n{i}", "target": f"n{(i + 7) % n}"} for i in range(0, n, 3)]
    edges += [{"source": "n1", "target": "n1"}, {"source": "n1", "target": "ghost"}]
    graph = {"nodes": [{"key": f"n{i}"} for i in range(n)], "edges": edges}

    positions, method = compute_similarity_positions(graph, dims=4, projection="spectral")

    assert method == "spectral"
    assert len(positions) == n
    assert all(np.isfinite([p["x"], p["y"]]).all() for p in positions)


# ─── Node order, pieces, isolates ───────────────────────────────

def pieces_graph():
    """Three irregular pieces (40, 25, 12 nodes), a 3-node path and an isolated node.

    Random chords keep eigenvalues distinct, so any dependence on node order comes from the
    layout code, not from symmetry in the graph.
    """
    rng = np.random.default_rng(3)
    nodes, edges = [], []
    for p, size in enumerate((40, 25, 12)):
        names = [f"p{p}n{i}" for i in range(size)]
        nodes += names
        edges += [(names[i], names[i + 1]) for i in range(size - 1)]
        for _ in range(size):
            a, b = rng.choice(size, 2, replace=False)
            edges.append((names[a], names[b]))
    nodes += ["t0", "t1", "t2", "alone"]
    edges += [("t0", "t1"), ("t1", "t2")]
    return {"nodes": [{"key": n} for n in nodes],
            "edges": [{"source": s, "target": t} for s, t in edges]}


def _distances(positions, order):
    xy = {p["id"]: (p["x"], p["y"]) for p in positions}
    pts = np.array([xy[k] for k in order])
    return np.linalg.norm(pts[:, None] - pts[None], axis=2)[np.triu_indices(len(order), 1)]


def test_the_layout_does_not_depend_on_node_order():
    # Gephi exports nodes in whatever order it holds them. On a graph in several pieces the
    # spectral basis used to return unrelated layouts for two orders of the same graph (on this
    # graph, a distance correlation of 0.24), because each piece adds a zero eigenvalue and the
    # extra ones came back in an arbitrary mix.
    graph = pieces_graph()
    shuffled = dict(graph, nodes=[graph["nodes"][i]
                                  for i in np.random.default_rng(5).permutation(len(graph["nodes"]))])
    order = [n["key"] for n in graph["nodes"]]

    a, _ = compute_similarity_positions(graph, projection="spectral")
    b, _ = compute_similarity_positions(shuffled, projection="spectral")

    assert np.corrcoef(_distances(a, order), _distances(b, order))[0, 1] > 0.999


def test_spectral_basis_lays_out_each_piece_in_its_own_area():
    graph = pieces_graph()

    positions, _ = compute_similarity_positions(graph, projection="spectral")

    xy = {p["id"]: (p["x"], p["y"]) for p in positions}
    boxes = []
    for prefix in ("p0", "p1", "p2", "t"):
        pts = np.array([v for k, v in xy.items() if k.startswith(prefix)])
        boxes.append((pts.min(axis=0), pts.max(axis=0)))
        assert np.ptp(pts, axis=0).max() > 0, f"piece {prefix} collapsed to a point"
    for i, (lo1, hi1) in enumerate(boxes):
        for lo2, hi2 in boxes[i + 1:]:
            assert (hi1 < lo2).any() or (hi2 < lo1).any(), "two pieces overlap"
    assert all(np.isfinite(v).all() for v in xy.values())


def test_small_pieces_sit_together_in_a_compact_block():
    # Found on a 1,490-node network with 266 isolated nodes: the isolates were laid end to end
    # in a row several times wider than the main piece.
    rng = np.random.default_rng(4)
    names = [f"m{i}" for i in range(60)]
    edges = [(names[i], names[i + 1]) for i in range(59)]
    edges += [(names[a], names[b]) for a, b in rng.choice(60, (30, 2)) if a != b]
    alone = [f"a{i}" for i in range(250)]
    graph = {"nodes": [{"key": n} for n in names + alone],
             "edges": [{"source": s, "target": t} for s, t in edges]}

    positions, _ = compute_similarity_positions(graph, projection="spectral")

    xy = {p["id"]: np.array([p["x"], p["y"]]) for p in positions}
    small = np.array([xy[k] for k in alone])
    main = np.array([xy[k] for k in names])
    w, h = np.ptp(small, axis=0)
    assert max(w, h) <= 2 * min(w, h), "the small pieces should form a block, not a row"
    assert max(w, h) <= np.ptp(main, axis=0).max(), "the block should not outsize the main piece"
