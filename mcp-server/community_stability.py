"""Consensus analysis over repeated community detection.

Gephi runs community detection once and reports a partition as though it were the answer. It is
one draw. The same graph run again can give a different partition (gephi#2002), and the result
changes with the order the tables were imported (gephi#2888) and even after a layout has run
(gephi#2735), which should not touch a partition at all.

gephi#2968 asked Gephi for exactly this analysis and was closed as not planned, so nothing in this
ecosystem can currently answer the first question anyone should ask of a community result: are
these groups real, or are they an artefact of one run?

The measure used here is co-assignment. Across N runs, every pair of nodes has a rate at which the
two landed in the same community. A node's stability is the chance that a node grouped with it in
one run is grouped with it in a different run. For each node j, with m runs containing both and t
of them grouping them, that is t(t-1) / (m(m-1)) of the ordered pairs of distinct runs, weighed
against t/m, the share of runs grouping them at all. 1.0 means its community-mates never change;
0.5 means half of them change from run to run. Nodes it is never grouped with do not count. On a
large graph almost every other node is such a stranger, and scoring those pairs as "decisive" made
every node look stable.

Only distinct runs are compared. The plain co-assignment form, sum(p^2) / sum(p), also compares
each run with itself, which always agrees, so it overstates stability by up to 1/runs: with two
runs whose groups share nothing it reported 0.5 instead of 0. A pair seen together in fewer than
two runs offers no pair of runs to compare and does not count towards stability.

Two partitions are derived. Stable cores keep the pairs grouped together in at least 90% of runs:
the groups that genuinely hold. The consensus keeps the pairs that agreed more often than not,
which leaves a node that agrees with nobody standing on its own; on a large graph those pairs can
chain into one group that spans nodes rarely together, and the result says so when they do.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

Partition = dict[str, Any]

#: Pairs grouped together in at least this share of runs form a stable core.
STABLE_CORE = 0.9


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


def _label_matrix(runs: list[Partition]) -> tuple[np.ndarray, list[str]]:
    """Runs as a (runs x nodes) array of community ids, -1 where a node is absent from a run.

    Labels are renumbered per run, so any hashable community label works.
    """
    nodes = sorted({n for run in runs for n in run})
    index = {n: i for i, n in enumerate(nodes)}
    labels = np.full((len(runs), len(nodes)), -1, dtype=np.int32)
    for r, run in enumerate(runs):
        ids: dict[Any, int] = {}
        for node, community in run.items():
            labels[r, index[node]] = ids.setdefault(community, len(ids))
    return labels, nodes


def _pair_rates(labels: np.ndarray, rows: slice) -> tuple[np.ndarray, np.ndarray]:
    """For a block of nodes against every node: runs containing both, and runs grouping them."""
    block = labels[:, rows]
    present = labels >= 0
    shared = np.zeros((block.shape[1], labels.shape[1]), dtype=np.int32)
    together = np.zeros_like(shared)
    for r in range(labels.shape[0]):
        both = (block[r] >= 0)[:, None] & present[r][None, :]
        shared += both
        together += both & (block[r][:, None] == labels[r][None, :])
    return shared, together


def _components(n: int, pairs: list[tuple[np.ndarray, np.ndarray]]) -> np.ndarray:
    """Each node's connected component over the given pairs."""
    rows = np.concatenate([r for r, _ in pairs]) if pairs else np.zeros(0, int)
    cols = np.concatenate([c for _, c in pairs]) if pairs else np.zeros(0, int)
    graph = coo_matrix((np.ones(len(rows), dtype=np.int8), (rows, cols)), shape=(n, n))
    return connected_components(graph, directed=False)[1]


def _forest(n: int, pairs: list[tuple[np.ndarray, np.ndarray]]) -> list[tuple[np.ndarray, np.ndarray]]:
    """The same groups as `pairs` in n pairs: each node joined to its group's first member.

    Pairs inside a community grow with the square of its size, so keeping every block's pairs
    ran a 112,000-node graph out of memory; folding each block in keeps memory at O(n).
    """
    component = _components(n, pairs)
    _, first = np.unique(component, return_index=True)
    return [(np.arange(n), first[component])]


def _groups(nodes: list[str], pairs: list[tuple[np.ndarray, np.ndarray]]) -> list[list[str]]:
    """Connected groups over the given pairs, largest first; unpaired nodes stand alone."""
    component = _components(len(nodes), pairs)
    members: dict[int, list[str]] = {}
    for i, c in enumerate(component):
        members.setdefault(int(c), []).append(nodes[i])
    return sorted((sorted(g) for g in members.values()), key=lambda g: (-len(g), g[0]))


def consensus(runs: list[Partition]) -> dict[str, Any]:
    """Summarise how reproducible a set of community-detection runs was.

    Returns the number of genuinely distinct partitions seen, a stability score per node and
    pooled over all pairs, the least stable nodes, stable cores (pairs together in at least 90% of
    runs), and a consensus partition built from the pairs that agreed more often than not, with a
    warning when that consensus is a chain rather than a community.

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

    labels, nodes = _label_matrix(runs)
    n = len(nodes)
    # Pairs are scored in blocks of rows so memory stays proportional to one block, not n x n.
    block = max(1, min(n, 4_000_000 // max(n, 1)))
    stability: dict[str, float] = {}
    agreed: list[tuple[np.ndarray, np.ndarray]] = []
    held: list[tuple[np.ndarray, np.ndarray]] = []
    pooled_sq = pooled = 0.0
    for start in range(0, n, block):
        rows = slice(start, min(n, start + block))
        shared, together = _pair_rates(labels, rows)
        own = np.arange(rows.start, rows.stop)
        shared[np.arange(len(own)), own] = 0  # a node is not paired with itself
        rate = np.divide(together, shared, out=np.zeros(shared.shape), where=shared > 0)
        # Stability compares distinct runs only, so it needs a pair seen in at least two runs.
        comparable = shared > 1
        mass = np.where(comparable, rate, 0.0).sum(axis=1)
        pairs_of_runs = shared.astype(np.float64) * (shared - 1)
        repeated = together.astype(np.float64) * (together - 1)
        mass_sq = np.divide(repeated, pairs_of_runs, out=np.zeros(shared.shape),
                            where=comparable).sum(axis=1)
        pooled += float(mass.sum())
        pooled_sq += float(mass_sq.sum())
        for i, node_index in enumerate(own):
            # A node grouped with nobody, ever, has nothing that could change: it is stable.
            stability[nodes[node_index]] = (round(float(mass_sq[i] / mass[i]), 4)
                                            if mass[i] else 1.0)
        r, c = np.nonzero(rate > 0.5)
        agreed = _forest(n, agreed + [(own[r], c)])
        r, c = np.nonzero(rate >= STABLE_CORE)
        held = _forest(n, held + [(own[r], c)])

    groups = _groups(nodes, agreed)
    cores = _groups(nodes, held)
    in_core = sum(len(g) for g in cores if len(g) > 1)

    ranked = sorted(stability.items(), key=lambda kv: (kv[1], kv[0]))
    multi_cores = [g for g in cores if len(g) > 1]
    result = {
        "runs": len(runs),
        "distinct_partitions": distinct,
        "node_stability": stability,
        # Pooled over every pair: the chance that two nodes grouped together in one run are
        # grouped together in a different run.
        "mean_stability": round(pooled_sq / pooled, 4) if pooled else 1.0,
        "unstable_nodes": [{"node": n, "stability": s} for n, s in ranked[:10]],
        "consensus_groups": groups,
        "stable_core_groups": multi_cores,
        "stable_cores": {"threshold": STABLE_CORE, "cores": len(multi_cores),
                         "share_of_nodes": round(in_core / n, 4) if n else 0.0,
                         "largest": [len(g) for g in multi_cores[:10]]},
    }
    largest = len(groups[0]) if groups else 0
    largest_core = len(multi_cores[0]) if multi_cores else 1
    if largest > n / 2 and largest > 2 * largest_core:
        result["consensus_warning"] = (
            f"One consensus group holds {largest} of {n} nodes. Pairs that agreed more often than "
            f"not chain together into it, so it is not one community; the largest group that "
            f"held in {STABLE_CORE:.0%} of runs has {largest_core} nodes. The communities are loose.")
    return result
