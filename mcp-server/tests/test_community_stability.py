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
    """For 'a': with b always (1.0), with x half the time (0.5), never with c or d.

    Stability is the chance that a node grouped with 'a' in one run is grouped with it in another:
    sum(p^2) / sum(p) over the nodes it was ever grouped with -> (1 + 0.25) / (1 + 0.5) = 0.8333.
    Nodes it is never grouped with do not count; they would make every node look decisive.
    """
    runs = [
        {"a": 1, "b": 1, "x": 1, "c": 2, "d": 2},
        {"a": 1, "b": 1, "x": 2, "c": 2, "d": 2},
    ]

    result = consensus(runs)

    assert result["node_stability"]["a"] == pytest.approx(1.25 / 1.5, abs=1e-4)


def test_strangers_do_not_make_a_node_look_stable():
    """Every node's partner changes between the two runs. On a large graph almost every other node
    is a stranger it is never grouped with; counting those as 'decisive' reported 0.97 here."""
    n = 200
    run1 = {i: i // 2 for i in range(n)}              # (0,1) (2,3) ...
    run2 = {i: (i + 1) // 2 for i in range(n)}        # (0) (1,2) (3,4) ...

    result = consensus([run1, run2])

    assert result["mean_stability"] == pytest.approx(0.5, abs=0.01)


def test_groups_that_hold_in_nearly_every_run_are_reported_as_stable_cores():
    runs = [
        {"a": 1, "b": 1, "x": 1, "c": 2, "d": 2},
        {"a": 1, "b": 1, "x": 2, "c": 2, "d": 2},
    ]

    result = consensus(runs)
    cores = {frozenset(g) for g in result["stable_core_groups"]}

    assert cores == {frozenset({"a", "b"}), frozenset({"c", "d"})}, "x belongs to no stable core"
    assert result["stable_cores"]["cores"] == 2
    assert result["stable_cores"]["share_of_nodes"] == pytest.approx(0.8)


def test_a_consensus_that_chains_most_nodes_together_is_flagged():
    """Pairs that agree more often than not can link into one group spanning nodes that are rarely
    together. The consensus then looks like one community when it is a chain of loose pairs."""
    pairs_a = {i: i // 2 for i in range(10)}               # (0,1) (2,3) ...
    pairs_b = {i: (i + 1) // 2 for i in range(10)}         # (0) (1,2) (3,4) ...
    together = {i: 0 for i in range(10)}

    result = consensus([pairs_a, pairs_b, together])

    assert len(result["consensus_groups"][0]) == 10
    assert "consensus_warning" in result


def test_one_community_that_really_is_one_community_is_not_flagged():
    result = consensus([{"a": 1, "b": 1, "c": 1}] * 3)

    assert "consensus_warning" not in result


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


def _reference(runs):
    """The pair-by-pair definition, written out directly. Slow, and only for small inputs."""
    from itertools import combinations
    nodes = sorted({n for r in runs for n in r})
    rates = {}
    for a, b in combinations(nodes, 2):
        shared = [r for r in runs if a in r and b in r]
        if shared:
            rates[(a, b)] = sum(r[a] == r[b] for r in shared) / len(shared)
    stability = {}
    for n in nodes:
        ps = [p for (a, b), p in rates.items() if n in (a, b)]
        stability[n] = round(sum(p * p for p in ps) / sum(ps), 4) if sum(ps) else 1.0
    return stability, {pair for pair, p in rates.items() if p > 0.5}


@pytest.mark.parametrize("seed", range(25))
def test_scores_and_groups_match_the_pair_by_pair_definition(seed):
    """Random runs over a few nodes, some missing from some runs, some nodes in no shared run."""
    import random
    rng = random.Random(seed)
    nodes = [f"n{i}" for i in range(rng.randint(2, 12))]
    runs = []
    for _ in range(rng.randint(2, 6)):
        present = [n for n in nodes if rng.random() > 0.15] or nodes[:1]
        runs.append({n: rng.randint(0, 3) for n in present})

    result = consensus(runs)
    stability, agreed = _reference(runs)

    assert result["node_stability"] == pytest.approx(stability, abs=1e-4)
    for a, b in agreed:
        assert any(a in g and b in g for g in result["consensus_groups"])
    group_of = {n: i for i, g in enumerate(result["consensus_groups"]) for n in g}
    for g in result["consensus_groups"]:
        if len(g) > 1:
            # every member is linked to the rest through agreed pairs, never merged by accident
            linked = {g[0]}
            grew = True
            while grew:
                grew = False
                for a, b in agreed:
                    if (a in linked) != (b in linked) and group_of[a] == group_of[b]:
                        linked |= {a, b}
                        grew = True
            assert linked == set(g)


def test_a_network_of_three_thousand_nodes_finishes_quickly():
    """2,919 accounts over 20 runs never finished before, because every node rescanned every pair."""
    import random
    import time
    rng = random.Random(0)
    base = {f"n{i}": i % 30 for i in range(3000)}
    runs = [{n: (c if rng.random() > 0.1 else rng.randint(0, 29)) for n, c in base.items()}
            for _ in range(20)]

    started = time.monotonic()
    result = consensus(runs)

    assert time.monotonic() - started < 15
    assert result["runs"] == 20 and len(result["node_stability"]) == 3000
