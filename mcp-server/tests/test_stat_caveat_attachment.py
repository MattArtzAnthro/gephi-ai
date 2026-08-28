"""The caveat register wired into the statistics tools.

A caveat is only useful if it travels with the number. These tests pin the three properties that
make the attachment safe: it fires when the defect applies, it stays silent and byte-identical
when it does not, and it can never fail a measurement that would otherwise have succeeded.
"""

import json

import pytest

import gephi_mcp
from stats_integrity import GraphFacts, mutates_graph, needs_graph_facts


class Recorder:
    """Async stand-in for GephiClient.request that records calls."""

    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])

    async def __call__(self, method, endpoint, params=None, json_data=None, timeout=None):
        self.calls.append({"method": method, "endpoint": endpoint, "json": json_data})
        if self.responses:
            return self.responses.pop(0)
        return {"success": True}

    def endpoints(self):
        return [c["endpoint"] for c in self.calls]


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    monkeypatch.setattr(gephi_mcp.gephi, "request", r)
    return r


@pytest.fixture(autouse=True)
def clear_facts_cache():
    gephi_mcp.invalidate_graph_facts()
    yield
    gephi_mcp.invalidate_graph_facts()


# ── It fires when the defect applies ──

async def test_modularity_at_a_non_default_resolution_carries_the_reciprocal_caveat(rec):
    rec.responses = [{"success": True, "modularity": 0.42, "communities": 7}]

    out = json.loads(await gephi_mcp.gephi_compute_modularity(resolution=1.5))

    assert "gephi-2034" in {c["id"] for c in out["caveats"]}
    assert out["modularity"] == 0.42, "the underlying result must survive intact"


async def test_modularity_at_the_default_resolution_omits_the_reciprocal_caveat(rec):
    """Whatever else fires, the resolution caveat must not: at 1.0 there is nothing to warn about."""
    rec.responses = [{"success": True, "modularity": 0.42, "communities": 7}]

    out = json.loads(await gephi_mcp.gephi_compute_modularity())

    assert "gephi-2034" not in {c["id"] for c in out.get("caveats", [])}


# ── It stays silent, and identical, when it does not apply ──

async def test_degree_is_untouched_because_no_defect_is_filed_against_it(rec):
    rec.responses = [{"success": True, "average_degree": 3.2}]

    out = json.loads(await gephi_mcp.gephi_compute_degree())

    assert out == {"success": True, "average_degree": 3.2}
    assert "caveats" not in out


async def test_a_metric_needing_no_graph_facts_makes_no_extra_call(rec):
    """The integrity layer must not add a round trip to a call that cannot need one."""
    rec.responses = [{"success": True, "average_degree": 3.2}]

    await gephi_mcp.gephi_compute_degree()

    assert rec.endpoints() == ["/statistics/degree"]


async def test_modularity_makes_no_extra_call_because_its_caveats_need_no_facts(rec):
    rec.responses = [{"success": True, "modularity": 0.42}]

    await gephi_mcp.gephi_compute_modularity(resolution=2.0)

    assert rec.endpoints() == ["/statistics/modularity"]


# ── Facts are fetched only for the metrics that need them ──

async def test_pagerank_on_an_undirected_graph_warns(rec):
    rec.responses = [
        {"success": True, "pagerank": "done"},
        {"success": True, "graph_type": "undirected", "nodes": 10, "edges": 12},
    ]

    out = json.loads(await gephi_mcp.gephi_compute_pagerank())

    assert "/graph/stats" in rec.endpoints(), "pagerank's caveat is directedness-conditional"
    assert "gephi-2191" in {c["id"] for c in out["caveats"]}


async def test_pagerank_on_a_directed_graph_stays_quiet(rec):
    rec.responses = [
        {"success": True, "pagerank": "done"},
        {"success": True, "graph_type": "directed", "nodes": 10, "edges": 12},
    ]

    out = json.loads(await gephi_mcp.gephi_compute_pagerank())

    assert "caveats" not in out


async def test_graph_facts_are_fetched_once_and_reused(rec):
    rec.responses = [
        {"success": True, "pagerank": "done"},
        {"success": True, "graph_type": "undirected"},
        {"success": True, "pagerank": "done"},
    ]

    await gephi_mcp.gephi_compute_pagerank()
    await gephi_mcp.gephi_compute_pagerank()

    assert rec.endpoints().count("/graph/stats") == 1


async def test_a_destructive_tool_invalidates_the_cached_facts(rec):
    """Facts describe the graph. Change the graph and they must be re-established."""
    rec.responses = [
        {"success": True, "pagerank": "done"},
        {"success": True, "graph_type": "undirected"},
    ]
    await gephi_mcp.gephi_compute_pagerank()

    gephi_mcp.invalidate_graph_facts()
    rec.responses = [
        {"success": True, "pagerank": "done"},
        {"success": True, "graph_type": "directed"},
    ]
    out = json.loads(await gephi_mcp.gephi_compute_pagerank())

    assert "caveats" not in out, "the graph is directed now, so the caveat must stop firing"


# ── It can never break a measurement ──

async def test_a_failing_statistic_is_returned_untouched(rec):
    rec.responses = [{"success": False, "error": "Gephi is busy"}]

    out = json.loads(await gephi_mcp.gephi_compute_modularity())

    assert out["success"] is False
    assert "caveats" not in out, "a failed call has no number to caveat"


async def test_a_broken_register_does_not_fail_the_statistic(rec, monkeypatch):
    def explode(*_args, **_kwargs):
        raise RuntimeError("register is corrupt")

    monkeypatch.setattr(gephi_mcp, "caveats_for", explode)
    rec.responses = [{"success": True, "modularity": 0.42}]

    out = json.loads(await gephi_mcp.gephi_compute_modularity())

    assert out["modularity"] == 0.42


async def test_an_unreachable_graph_stats_call_does_not_fail_the_statistic(rec):
    rec.responses = [
        {"success": True, "pagerank": "done"},
        {"success": False, "error": "Cannot connect to Gephi"},
    ]

    out = json.loads(await gephi_mcp.gephi_compute_pagerank())

    assert out["pagerank"] == "done"
    assert "caveats" not in out, "unknown directedness must not produce a guessed warning"


# ── The predicate that decides whether a fetch is needed ──

def test_needs_graph_facts_is_false_for_a_metric_with_no_caveats():
    assert needs_graph_facts("degree") is False


def test_needs_graph_facts_is_false_when_caveats_depend_only_on_params():
    assert needs_graph_facts("modularity") is False


def test_needs_graph_facts_is_true_when_a_caveat_depends_on_the_graph():
    assert needs_graph_facts("pagerank") is True


# ── The facts cache must follow the graph ──
#
# These are deliberately NOT written against a patched `gephi.request`: the invalidation lives
# inside the real client, so patching it away would test a seam that is never deployed. The
# decision is tested as a pure predicate, and one test drives the genuine client with only the
# network stubbed.



@pytest.mark.parametrize("method,endpoint", [
    ("POST", "/graph/node/add"),
    ("POST", "/graph/edge/remove"),
    ("POST", "/graph/clear"),
    ("POST", "/filter/degree"),
    ("POST", "/filter/giant-component"),
    ("POST", "/datalab/merge-nodes"),
    ("POST", "/workspace/new"),
    ("DELETE", "/workspace/delete"),
    ("POST", "/project/open"),
    ("POST", "/import/gexf"),
])
def test_these_calls_change_which_graph_we_are_looking_at(method, endpoint):
    assert mutates_graph(method, endpoint) is True


@pytest.mark.parametrize("method,endpoint", [
    ("GET", "/graph/stats"),
    ("GET", "/graph/type"),
    ("POST", "/statistics/pagerank"),
    ("POST", "/statistics/modularity"),
    ("POST", "/export/gexf"),
    ("POST", "/export/png"),
    ("POST", "/appearance/node/color"),
    ("POST", "/layout/run"),
    ("POST", "/preview/settings"),
    ("POST", "/datalab/frequencies"),
])
def test_these_calls_leave_the_graph_facts_valid(method, endpoint):
    assert mutates_graph(method, endpoint) is False


def test_an_unrecognised_write_is_assumed_to_change_the_graph():
    """Fail safe. A stale caveat is a wrong answer; an extra cheap GET is not."""
    assert mutates_graph("POST", "/some/endpoint/added/later") is True


async def test_the_real_client_invalidates_the_cache_on_a_graph_edit(monkeypatch):
    """Drives GephiClient.request itself, with only the network stubbed."""
    import gephi_mcp as g

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"success": True}

    class FakeAsyncClient:
        def __init__(self, *_a, **_k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_a):
            return False

        async def request(self, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(g.httpx, "AsyncClient", FakeAsyncClient)

    g._graph_facts = GraphFacts(directed=False)
    await g.gephi.request("POST", "/statistics/pagerank")
    assert g._graph_facts is not None, "a statistic must not invalidate the facts"

    await g.gephi.request("POST", "/graph/node/add")
    assert g._graph_facts is None, "a graph edit must invalidate the facts"


async def test_profiling_the_graph_teaches_the_caveat_layer_about_weights(rec):
    """The edge-weight caveat is the most decisively confirmed one, and it needs a fact.

    `weights_vary` is too expensive to fetch on the statistics path, so it is never established
    there and the caveat can never fire. But gephi_profile_graph already computes exactly that
    fact on its way past. Not keeping it means a confirmed defect stays permanently invisible.
    """
    gexf = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<gexf xmlns="http://gexf.net/1.3" version="1.3">'
        '<graph defaultedgetype="undirected"><nodes>'
        '<node id="a"/><node id="b"/><node id="c"/></nodes><edges>'
        '<edge id="0" source="a" target="b" weight="1.0"/>'
        '<edge id="1" source="b" target="c" weight="99.0"/>'
        "</edges></graph></gexf>")
    rec.responses = [
        {"success": True, "content": gexf},   # /export/gexf for the profile
        {"success": True},                    # modularity
        {"success": True},                    # clustering
    ]
    await gephi_mcp.gephi_profile_graph()

    rec.responses = [{"success": True, "betweenness": "done"}]
    out = json.loads(await gephi_mcp.gephi_compute_betweenness())

    assert "gephi-557" in {c["id"] for c in out.get("caveats", [])}, (
        "profiling established that weights vary, so the weight caveat must now fire")
