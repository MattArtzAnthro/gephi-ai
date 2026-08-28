"""Consensus analysis over repeated community detection.

Gephi runs community detection once and reports a partition as though it were the answer. It is
one draw. The same graph run again can give a different partition (gephi#2002), and the result
changes with the order the tables were imported (gephi#2888) and even after a layout has run
(gephi#2735), which should not touch a partition at all.

gephi#2968 asked Gephi for exactly this analysis and was closed as not planned, so nothing in this
ecosystem can currently answer the first question anyone should ask of a community result: are
these groups real, or are they an artefact of one run?

The measure used here is co-assignment. Across N runs, every pair of nodes has a rate at which the
two landed in the same community. A rate of 1.0 or 0.0 is decisive; 0.5 is a coin flip. A node's
stability is the average decisiveness of its relations with every other node, so 1.0 means every
relation came out the same way every time, and 0.5 means the node's membership is undetermined.

The consensus partition keeps the pairs that agreed more often than not, which leaves a node that
agrees with nobody standing on its own rather than being forced into a group it only half joined.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

Partition = dict[str, Any]


def _canonical(partition: Partition) -> frozenset[frozenset[str]]:
    """A partition as its set of groups, so arbitrary community labels stop mattering.

    Gephi numbers communities differently between runs. {a,b}|{c,d} is the same partition whether
    the groups are called 1 and 2 or 7 and 3, and counting relabellings as different outcomes
    would report instability that is not there.
    """
    groups: dict[Any, set[str]] = {}
    for node, community in partition.items():
        groups.setdefault(community, set()).add(node)
    return frozenset(frozenset(g) for g in groups.values())


def _co_assignment(runs: list[Partition]) -> tuple[dict[tuple[str, str], float], list[str]]:
    """For every pair of nodes, the fraction of the runs containing both that grouped them."""
    nodes = sorted({n for run in runs for n in run})
    rates: dict[tuple[str, str], float] = {}
    for a, b in combinations(nodes, 2):
        shared = [r for r in runs if a in r and b in r]
        if not shared:
            continue
        together = sum(1 for r in shared if r[a] == r[b])
        rates[(a, b)] = together / len(shared)
    return rates, nodes


def _components(nodes: list[str], edges: set[tuple[str, str]]) -> list[list[str]]:
    parent = {n: n for n in nodes}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in edges:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    groups: dict[str, list[str]] = {}
    for n in nodes:
        groups.setdefault(find(n), []).append(n)
    return [sorted(g) for g in groups.values()]


def consensus(runs: list[Partition]) -> dict[str, Any]:
    """Summarise how reproducible a set of community-detection runs was.

    Returns the number of genuinely distinct partitions seen, a stability score per node, the
    least stable nodes, and a consensus partition built from the pairs that agreed more often
    than not.

    A single run returns `mean_stability: None` and a warning rather than a score. One draw
    carries no information about reproducibility, and reporting 1.0 there would assert exactly
    the thing the caller asked us to check.
    """
    runs = [r for r in (runs or []) if r]
    if not runs:
        return {"runs": 0, "distinct_partitions": 0, "node_stability": {},
                "mean_stability": None, "unstable_nodes": [], "consensus_groups": [],
                "warning": "No runs were recorded, so nothing can be said about stability."}

    distinct = len({_canonical(r) for r in runs})

    if len(runs) == 1:
        return {"runs": 1, "distinct_partitions": distinct, "node_stability": {},
                "mean_stability": None, "unstable_nodes": [],
                "consensus_groups": [sorted(g) for g in _canonical(runs[0])],
                "warning": ("Only one run was recorded. One draw says nothing about whether the "
                            "partition is reproducible; run it several times to find out.")}

    rates, nodes = _co_assignment(runs)

    stability: dict[str, float] = {}
    for node in nodes:
        decisiveness = [max(p, 1.0 - p)
                        for (a, b), p in rates.items() if node in (a, b)]
        stability[node] = round(sum(decisiveness) / len(decisiveness), 4) if decisiveness else 1.0

    agreed = {pair for pair, p in rates.items() if p > 0.5}
    groups = _components(nodes, agreed)

    ranked = sorted(stability.items(), key=lambda kv: (kv[1], kv[0]))
    return {
        "runs": len(runs),
        "distinct_partitions": distinct,
        "node_stability": stability,
        "mean_stability": round(sum(stability.values()) / len(stability), 4),
        "unstable_nodes": [{"node": n, "stability": s} for n, s in ranked[:10]],
        "consensus_groups": sorted(groups, key=lambda g: (-len(g), g[0])),
    }
