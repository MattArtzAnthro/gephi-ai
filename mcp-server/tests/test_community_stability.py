"""Consensus analysis over repeated community detection.

gephi#2968 asked Gephi for this and was closed as not planned. Gephi runs community detection once
and reports a partition as though it were the answer. Run it again and you may get a different one
(gephi#2002), and it changes with import order (gephi#2888) and even after a layout (gephi#2735).

So the question "are these communities real?" is currently unanswerable in this ecosystem. These
tests pin the maths that answers it.

The stability of a node is the average decisiveness of its co-membership relations across runs:
for every other node, how far that pair's co-assignment rate sits from a coin flip. 1.0 means every
relation came out the same way every time. 0.5 means maximally undecided.
"""

import pytest

from community_stability import consensus

TWO_CLEAN_COMMUNITIES = {"a": 1, "b": 1, "c": 2, "d": 2}


def test_identical_runs_are_perfectly_stable():
    result = consensus([TWO_CLEAN_COMMUNITIES] * 5)

    assert result["mean_stability"] == pytest.approx(1.0)
    assert all(s == pytest.approx(1.0) for s in result["node_stability"].values())


def test_identical_runs_are_recognised_as_one_partition():
    result = consensus([TWO_CLEAN_COMMUNITIES] * 5)

    assert result["distinct_partitions"] == 1
    assert result["runs"] == 5


def test_relabelled_runs_are_the_same_partition():
    """Community labels are arbitrary. {a,b} vs {c,d} is one partition however it is numbered."""
    result = consensus([
        {"a": 1, "b": 1, "c": 2, "d": 2},
        {"a": 7, "b": 7, "c": 3, "d": 3},
        {"a": "x", "b": "x", "c": "y", "d": "y"},
    ])

    assert result["distinct_partitions"] == 1
    assert result["mean_stability"] == pytest.approx(1.0)


def test_a_node_that_bounces_between_communities_is_the_least_stable():
    """'x' lands with {a,b} half the time and with {c,d} the other half.

    Its co-assignment with every other node is exactly 0.5, the least decisive value possible,
    so its stability is 0.5 while the four settled nodes score higher.
    """
    runs = [
        {"a": 1, "b": 1, "x": 1, "c": 2, "d": 2},
        {"a": 1, "b": 1, "x": 2, "c": 2, "d": 2},
        {"a": 1, "b": 1, "x": 1, "c": 2, "d": 2},
        {"a": 1, "b": 1, "x": 2, "c": 2, "d": 2},
    ]

    result = consensus(runs)

    assert result["node_stability"]["x"] == pytest.approx(0.5)
    assert result["unstable_nodes"][0]["node"] == "x"
    for settled in ("a", "b", "c", "d"):
        assert result["node_stability"][settled] > result["node_stability"]["x"]


def test_the_settled_nodes_keep_their_exact_hand_computed_stability():
    """For 'a': with b always (1.0), with x half the time (0.5), never with c or d (both 1.0).

    decisiveness = max(p, 1-p) per pair -> (1.0 + 0.5 + 1.0 + 1.0) / 4 = 0.875
    """
    runs = [
        {"a": 1, "b": 1, "x": 1, "c": 2, "d": 2},
        {"a": 1, "b": 1, "x": 2, "c": 2, "d": 2},
    ]

    result = consensus(runs)

    assert result["node_stability"]["a"] == pytest.approx(0.875)


def test_the_consensus_partition_keeps_pairs_that_agree_more_often_than_not():
    runs = [
        {"a": 1, "b": 1, "x": 1, "c": 2, "d": 2},
        {"a": 1, "b": 1, "x": 2, "c": 2, "d": 2},
    ]

    result = consensus(runs)
    groups = {frozenset(g) for g in result["consensus_groups"]}

    assert frozenset({"a", "b"}) in groups
    assert frozenset({"c", "d"}) in groups
    assert frozenset({"x"}) in groups, "a node that agrees with nobody stands alone"


def test_distinct_partitions_counts_genuinely_different_outcomes():
    runs = [
        {"a": 1, "b": 1, "c": 2, "d": 2},
        {"a": 1, "b": 1, "c": 2, "d": 2},
        {"a": 1, "b": 2, "c": 2, "d": 2},
    ]

    assert consensus(runs)["distinct_partitions"] == 2


def test_a_single_run_cannot_establish_stability():
    """One draw says nothing about reproducibility, and must not be reported as though it did."""
    result = consensus([TWO_CLEAN_COMMUNITIES])

    assert result["mean_stability"] is None
    assert "one run" in result["warning"].lower()


def test_no_runs_at_all_is_reported_rather_than_crashing():
    result = consensus([])

    assert result["runs"] == 0
    assert result["mean_stability"] is None


def test_a_node_missing_from_some_runs_is_scored_only_where_both_appeared():
    """Nodes can vanish between runs if the graph was filtered. Pairs are scored on shared runs."""
    runs = [
        {"a": 1, "b": 1, "c": 2},
        {"a": 1, "b": 1},
        {"a": 1, "b": 1, "c": 2},
    ]

    result = consensus(runs)

    assert result["node_stability"]["c"] == pytest.approx(1.0)


def test_everything_in_one_community_every_time_is_stable():
    result = consensus([{"a": 1, "b": 1, "c": 1}] * 3)

    assert result["mean_stability"] == pytest.approx(1.0)
    assert len(result["consensus_groups"]) == 1
