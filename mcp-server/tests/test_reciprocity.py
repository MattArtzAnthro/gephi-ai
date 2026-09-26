"""Reciprocity in the structural profile: how many directed ties are returned.

Reply, mention and citation networks are mostly one-way. Reading one as a conversation, with
hubs as partners in an exchange, is wrong when the hubs never answer.
"""

import pytest

from gephi_mcp_viewer.profile import structural_profile


def directed(edges, n=None):
    keys = sorted({x for e in edges for x in e} | {f"n{i}" for i in range(n or 0)})
    return {"directed": True, "nodes": [{"key": k} for k in keys],
            "edges": [{"source": s, "target": t} for s, t in edges]}


def test_half_the_ties_returned():
    profile = structural_profile(directed([("a", "b"), ("b", "a"), ("a", "c"), ("c", "d")]))

    # a->b and b->a are returned; a->c and c->d are not: 2 of 4 directed ties
    assert profile["reciprocity"] == pytest.approx(0.5)


def test_duplicate_ties_and_self_loops_do_not_count():
    profile = structural_profile(directed([("a", "b"), ("a", "b"), ("b", "a"), ("c", "c")]))

    assert profile["reciprocity"] == pytest.approx(1.0)


def test_undirected_graphs_have_no_reciprocity():
    graph = directed([("a", "b"), ("b", "c")])
    graph["directed"] = False

    assert "reciprocity" not in structural_profile(graph)


def test_a_mostly_one_way_network_is_flagged():
    edges = [(f"n{i}", "hub") for i in range(1, 60)] + [("hub", "n1"), ("n1", "hub")]

    flags = structural_profile(directed(edges))["flags"]

    assert any("one-way" in f for f in flags)


def test_a_conversation_is_not_flagged():
    edges = [(f"n{i}", f"n{i+1}") for i in range(60)] + [(f"n{i+1}", f"n{i}") for i in range(60)]

    flags = structural_profile(directed(edges))["flags"]

    assert not any("one-way" in f for f in flags)
