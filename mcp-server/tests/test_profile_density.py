"""Density in the structural profile counts pairs the way the graph's direction does.

A directed tie fills one of n(n-1) ordered pairs, as Gephi's Density statistic counts them; an
undirected tie fills one of n(n-1)/2. The profile used the undirected formula for both, so a
directed graph read twice as dense as it is.
"""

from gephi_mcp_viewer.profile import structural_profile


def _graph(directed: bool) -> dict:
    ties = [("p", "q"), ("q", "p"), ("q", "r")]
    return {"directed": directed,
            "nodes": [{"key": k} for k in ("p", "q", "r", "s")],
            "edges": [{"source": s, "target": t} for s, t in ties]}


def test_directed_density_counts_ordered_pairs():
    assert structural_profile(_graph(directed=True))["density"] == 3 / (4 * 3)


def test_undirected_density_counts_unordered_pairs():
    assert structural_profile(_graph(directed=False))["density"] == 2 * 3 / (4 * 3)
