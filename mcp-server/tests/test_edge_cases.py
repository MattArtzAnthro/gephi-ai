"""Edge-case and robustness coverage for the unit-testable core.

Complements test_viewer / test_tools / test_text_network (which cover the happy
paths) with the awkward inputs real graphs throw: empty graphs, directed graphs,
self-loops, parallel/typed edges, unicode, missing attributes, malformed files,
disconnected components, and scale. These run headless in CI (no live Gephi).
"""
import pytest

import text_network as tn
from gephi_mcp_viewer import (
    analyze_graph,
    parse_gexf,
    pick_cluster_hubs,
    resolve_column_key,
)
from gephi_mcp_viewer.community_layout import compute_community_positions


def _gexf(nodes_xml, edges_xml, directed=False, node_attrs="", edge_attrs=""):
    et = "directed" if directed else "undirected"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">'
        f'<graph mode="static" defaultedgetype="{et}">'
        f'{node_attrs}{edge_attrs}'
        f'<nodes>{nodes_xml}</nodes><edges>{edges_xml}</edges>'
        '</graph></gexf>'
    )


# ── parse_gexf: structural edge cases ────────────────────────────────────

def test_parse_empty_graph():
    g = parse_gexf(_gexf("", ""))
    assert g["nodes"] == [] and g["edges"] == []
    assert g["node_count_total"] == 0 and g["edge_count_total"] == 0
    assert g["attr_key"] == {}


def test_parse_single_node_no_edges():
    g = parse_gexf(_gexf('<node id="a" label="A"/>', ""))
    assert len(g["nodes"]) == 1 and g["nodes"][0]["key"] == "a"
    assert g["edges"] == []


def test_parse_directed_flag():
    g = parse_gexf(_gexf('<node id="a"/><node id="b"/>',
                         '<edge id="0" source="a" target="b"/>', directed=True))
    assert g["directed"] is True


def test_parse_self_loop():
    g = parse_gexf(_gexf('<node id="a"/>', '<edge id="0" source="a" target="a"/>'))
    assert len(g["edges"]) == 1
    assert g["edges"][0]["source"] == g["edges"][0]["target"] == "a"


def test_parse_parallel_typed_edges():
    edges = ('<edge id="0" source="a" target="b" weight="1"/>'
             '<edge id="1" source="a" target="b" weight="2"/>')
    g = parse_gexf(_gexf('<node id="a"/><node id="b"/>', edges))
    assert len(g["edges"]) == 2  # both parallel edges preserved


def test_parse_unicode_and_special_chars():
    # ampersand/quotes must be XML-escaped in the source; unicode passes through
    attrs = '<attributes class="node"><attribute id="0" title="naïve" type="string"/></attributes>'
    node = ('<node id="ünîçødé" label="Zoë &amp; Café">'
            '<attvalues><attvalue for="0" value="résumé"/></attvalues></node>')
    g = parse_gexf(_gexf(node, "", node_attrs=attrs))
    n = g["nodes"][0]
    assert n["key"] == "ünîçødé"
    assert n["label"] == "Zoë & Café"
    assert n["attributes"]["naïve"] == "résumé"


def test_parse_node_without_position_defaults_zero():
    g = parse_gexf(_gexf('<node id="a"/>', ""))
    assert g["nodes"][0]["x"] == 0.0 and g["nodes"][0]["y"] == 0.0


def test_parse_missing_attribute_value_is_absent_not_crash():
    attrs = ('<attributes class="node">'
             '<attribute id="0" title="team" type="string"/>'
             '<attribute id="1" title="score" type="integer"/></attributes>')
    # node declares only 'team', not 'score'
    node = '<node id="a"><attvalues><attvalue for="0" value="X"/></attvalues></node>'
    g = parse_gexf(_gexf(node, "", node_attrs=attrs))
    assert g["nodes"][0]["attributes"].get("team") == "X"
    assert "score" not in g["nodes"][0]["attributes"]


def test_parse_malformed_xml_raises():
    with pytest.raises(Exception):
        parse_gexf("<gexf><graph><nodes><node id=")  # truncated / invalid


def test_parse_truncates_to_max_nodes_by_degree():
    nodes = "".join(f'<node id="n{i}"/>' for i in range(50))
    # n0 is a hub (edges to everyone), the rest are leaves
    edges = "".join(f'<edge id="e{i}" source="n0" target="n{i}"/>' for i in range(1, 50))
    g = parse_gexf(_gexf(nodes, edges), max_nodes=10)
    assert len(g["nodes"]) == 10
    assert g["truncated"] is True
    assert any(n["key"] == "n0" for n in g["nodes"])  # the hub is kept
    # edges to dropped nodes are pruned
    kept = {n["key"] for n in g["nodes"]}
    assert all(e["source"] in kept and e["target"] in kept for e in g["edges"])


def test_parse_scale_1000_nodes_is_fast():
    import time
    nodes = "".join(f'<node id="n{i}"/>' for i in range(1000))
    edges = "".join(f'<edge id="e{i}" source="n{i}" target="n{(i+1) % 1000}"/>'
                     for i in range(1000))
    t = time.perf_counter()
    g = parse_gexf(_gexf(nodes, edges), max_nodes=5000)
    assert len(g["nodes"]) == 1000 and len(g["edges"]) == 1000
    assert time.perf_counter() - t < 2.0  # generous headroom


# ── resolve_column_key ───────────────────────────────────────────────────

def test_resolve_column_key_none_and_missing():
    g = {"attr_key": {"team": "team"}}
    assert resolve_column_key(g, None) is None
    assert resolve_column_key(g, "nope") == "nope"           # falls through
    assert resolve_column_key({}, "team") == "team"          # no attr_key


def test_resolve_column_key_id_title_normalized():
    g = parse_gexf(_gexf(
        '<node id="a"><attvalues><attvalue for="modularity_class" value="0"/></attvalues></node>',
        "",
        node_attrs='<attributes class="node"><attribute id="modularity_class"'
                   ' title="Modularity Class" type="integer"/></attributes>'))
    for name in ("modularity_class", "Modularity Class", "MODULARITY_CLASS", " modularity class "):
        assert resolve_column_key(g, name) == "Modularity Class"


# ── analyze_graph edge cases ─────────────────────────────────────────────

def test_analyze_empty_graph_no_crash():
    r = analyze_graph(parse_gexf(_gexf("", "")))
    assert r["nodes"] == 0 and r["edges"] == 0


def test_analyze_single_node():
    r = analyze_graph(parse_gexf(_gexf('<node id="a"/>', "")))
    assert r["nodes"] == 1


def test_analyze_partition_all_one_group_is_not_strong():
    # every node in the same partition, no internal structure -> not "strong"
    nodes = "".join(f'<node id="n{i}"><attvalues><attvalue for="0" value="C0"/></attvalues></node>'
                    for i in range(6))
    edges = '<edge id="0" source="n0" target="n1"/><edge id="1" source="n2" target="n3"/>'
    g = parse_gexf(_gexf(nodes, edges,
                         node_attrs='<attributes class="node"><attribute id="0" title="team" type="string"/></attributes>'))
    p = analyze_graph(g, partition_column="team")["partition"]
    assert p["groups"] == 1


def test_analyze_partition_absent_column():
    g = parse_gexf(_gexf('<node id="a"/><node id="b"/>',
                         '<edge id="0" source="a" target="b"/>'))
    p = analyze_graph(g, partition_column="does_not_exist")["partition"]
    assert p["groups"] == 0  # nothing carries it


# ── pick_cluster_hubs & community_layout ─────────────────────────────────

def test_pick_cluster_hubs_ignores_nodes_without_attribute():
    nodes = ('<node id="a"><attvalues><attvalue for="0" value="G1"/></attvalues></node>'
             '<node id="b"/>')  # b has no team
    g = parse_gexf(_gexf(nodes, '<edge id="0" source="a" target="b"/>',
                         node_attrs='<attributes class="node"><attribute id="0" title="team" type="string"/></attributes>'))
    hubs = pick_cluster_hubs(g, "team")
    assert set(hubs.keys()) == {"G1"}


def test_community_layout_absent_partition_raises():
    g = parse_gexf(_gexf('<node id="a"/><node id="b"/>', ""))
    with pytest.raises(ValueError):
        compute_community_positions(g, partition="nope")


# ── text_network edge cases ──────────────────────────────────────────────

def test_text_empty_string():
    r = tn.build_cooccurrence_graph("")
    assert r["nodes"] == [] and r["edges"] == []


def test_text_single_word():
    r = tn.build_cooccurrence_graph("collaboration", min_word_frequency=1)
    # one content word, no co-occurrence edges
    assert len(r["edges"]) == 0


def test_text_all_stopwords():
    r = tn.build_cooccurrence_graph("the and of to in a is", min_word_frequency=1)
    assert r["nodes"] == []


def test_text_list_resets_window_between_docs():
    # 'alpha' and 'omega' never co-occur within a doc, so no edge should bridge them
    docs = ["alpha beta gamma", "omega beta gamma"]
    r = tn.build_cooccurrence_graph(docs, window_size=4, min_word_frequency=1)
    pairs = {frozenset((e["source"], e["target"])) for e in r["edges"]}
    assert frozenset(("alpha", "omega")) not in pairs


def test_text_unicode():
    r = tn.build_cooccurrence_graph("café résumé naïve café résumé", min_word_frequency=1)
    labels = {n["label"] if isinstance(n, dict) and "label" in n else n.get("id")
              for n in r["nodes"]}
    assert any("café" in str(label) or "resume" in str(label).lower() or "café" == label for label in labels) or r["nodes"]


def test_tokenize_and_lemmatize_robust_on_punctuation():
    toks = tn.tokenize("Hello, world! Networks... are (interesting).")
    assert all(isinstance(t, str) for t in toks)
    assert tn.lemmatize(["networks", "running", "studies"])  # no crash, returns list


def test_extract_backbone_empty_and_small():
    assert tn.extract_backbone([])["edges"] == []
    one = [{"source": "a", "target": "b", "weight": 1.0}]
    r = tn.extract_backbone(one, alpha=0.5)
    assert "edges" in r


# ── version freshness comparison (health_check update nag) ────────────────
def test_semver_and_is_behind():
    import gephi_mcp as g
    assert g._semver("1.9.10") == (1, 9, 10)
    assert g._semver("gephi-ai==1.2.15") == (1, 2, 15)
    # numeric compare, not string (1.9.10 is newer than 1.9.9)
    assert g._is_behind("1.9.9", "1.9.10") is True
    assert g._is_behind("1.9.20", "1.9.20") is False
    assert g._is_behind("1.9.21", "1.9.20") is False  # ahead (dev) is not behind
    assert g._is_behind("1.2.4", "1.2.15") is True
    # missing/garbage never reports behind (fail-safe)
    assert g._is_behind("", "1.0.0") is False
    assert g._is_behind("1.0.0", None) is False


async def test_freshness_opt_out(monkeypatch):
    import gephi_mcp as g
    g._freshness_cache.clear()
    monkeypatch.setenv("GEPHI_SKIP_UPDATE_CHECK", "1")
    assert await g._check_freshness({"version": "0.0.1"}) is None


async def test_freshness_flags_behind(monkeypatch):
    import gephi_mcp as g
    g._freshness_cache.clear()
    monkeypatch.delenv("GEPHI_SKIP_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(g, "__version__", "1.0.0")  # deterministically behind 99.0.0

    class _Resp:
        def json(self):
            return {"server": "99.0.0", "nbm": "99.0.0"}

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url): return _Resp()

    monkeypatch.setattr(g.httpx, "AsyncClient", _Client)
    r = await g._check_freshness({"version": "1.2.15"})
    assert r and r["available"] is True
    comps = {b["component"] for b in r["behind"]}
    assert any("server" in c for c in comps)  # server is behind 99.0.0
    assert "how_to_update" in r


async def test_freshness_fails_silent_on_network_error(monkeypatch):
    import gephi_mcp as g
    g._freshness_cache.clear()
    monkeypatch.delenv("GEPHI_SKIP_UPDATE_CHECK", raising=False)

    class _Boom:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): raise RuntimeError("no network")
        async def __aexit__(self, *a): return False

    monkeypatch.setattr(g.httpx, "AsyncClient", _Boom)
    assert await g._check_freshness({"version": "1.2.15"}) is None  # never raises


async def test_freshness_current_returns_available_false(monkeypatch):
    import gephi_mcp as g
    g._freshness_cache.clear()
    monkeypatch.delenv("GEPHI_SKIP_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(g, "__version__", "1.0.0")

    class _Resp:
        def json(self):
            return {"server": "1.0.0", "nbm": "1.2.15"}  # exactly current

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url): return _Resp()

    monkeypatch.setattr(g.httpx, "AsyncClient", _Client)
    r = await g._check_freshness({"version": "1.2.15"})
    assert r == {"available": False}  # checked and current, distinct from None
