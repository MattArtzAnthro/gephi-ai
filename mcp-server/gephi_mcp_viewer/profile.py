"""Structural profile of a parsed graph: the cheap, always-computable facts.

Complements the Gephi-side statistics (modularity, clustering coefficient,
path lengths) with everything derivable directly from nodes and edges, so a
single profiling call can hand the model a compact quantitative picture.
"""

from __future__ import annotations

import statistics
from collections import Counter


def _gini(values: list[float]) -> float:
    """Gini coefficient of a value distribution (0 = equal, 1 = one node has all)."""
    xs = sorted(values)
    n = len(xs)
    total = sum(xs)
    if n == 0 or total == 0:
        return 0.0
    weighted = sum(i * x for i, x in enumerate(xs, start=1))
    return (2 * weighted) / (n * total) - (n + 1) / n


def _assortativity(edge_degree_pairs: list[tuple[int, int]]) -> float | None:
    """Degree assortativity: Pearson correlation of degrees at edge endpoints.

    Each edge contributes both orientations so the result is symmetric for
    undirected graphs. Returns None when degrees carry no variance (regular
    graphs) or there are no usable edges.
    """
    pairs = edge_degree_pairs + [(k, j) for j, k in edge_degree_pairs]
    if not pairs:
        return None
    mean = sum(j for j, _ in pairs) / len(pairs)
    var = sum((j - mean) ** 2 for j, _ in pairs)
    if var == 0:
        return None
    cov = sum((j - mean) * (k - mean) for j, k in pairs)
    return cov / var


def structural_profile(graph: dict) -> dict:
    """Degree, connectivity, and weight facts from a parse_gexf graph dict."""
    nodes = [n["key"] for n in graph["nodes"]]
    n = len(nodes)
    edges = graph["edges"]
    m = len(edges)

    deg: Counter = Counter()
    weights = []
    parent = {k: k for k in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    seen_pairs = 0
    seen_edges = []
    for e in edges:
        s, t = e["source"], e["target"]
        if s not in parent or t not in parent:
            continue
        seen_pairs += 1
        seen_edges.append((s, t))
        deg[s] += 1
        deg[t] += 1
        # parse_gexf stores GEXF edge weight under "size" (default 1.0)
        w = e.get("size")
        if w is not None:
            weights.append(float(w))
        rs, rt = find(s), find(t)
        if rs != rt:
            parent[rs] = rt

    components = Counter(find(k) for k in nodes)
    comp_sizes = sorted(components.values(), reverse=True)
    degrees = sorted((deg.get(k, 0) for k in nodes), reverse=True)
    isolates = sum(1 for d in degrees if d == 0)
    top_share = (sum(degrees[: max(1, n // 20)]) / (2 * seen_pairs)) if seen_pairs else 0.0

    assortativity = _assortativity([(deg[s], deg[t]) for s, t in seen_edges])
    k_mean = (2 * seen_pairs / n) if n else 0.0
    k2_mean = (sum(d * d for d in degrees) / n) if n else 0.0
    # Configuration-model expectation: what clustering a random graph with
    # this exact degree sequence would show. The observed/expected ratio is
    # the verdict; the raw coefficient alone is trivia.
    expected_clustering = (
        ((k2_mean - k_mean) ** 2) / (n * k_mean ** 3) if n and k_mean > 0 else 0.0
    )

    profile = {
        "nodes": n,
        "edges": m,
        "directed": bool(graph.get("directed")),
        "density": (2 * m / (n * (n - 1))) if n > 1 else 0.0,
        "degree": {
            "min": degrees[-1] if degrees else 0,
            "median": degrees[n // 2] if degrees else 0,
            "max": degrees[0] if degrees else 0,
            "top_5pct_edge_share": round(top_share, 3),
            "gini": round(_gini(degrees), 3),
            "assortativity": (round(assortativity, 3)
                              if assortativity is not None else None),
        },
        "components": {
            "count": len(comp_sizes),
            "giant_share": round(comp_sizes[0] / n, 3) if n else 0.0,
        },
        "isolates": isolates,
        "weighted": bool(weights) and len(set(weights)) > 1,
        "clustering_expected_random": round(expected_clustering, 6),
    }

    if profile["weighted"]:
        w_median = statistics.median(weights)
        w_max = max(weights)
        heavy = w_median > 0 and (w_max / w_median) >= 50
        profile["weights"] = {
            "min": min(weights),
            "median": w_median,
            "max": w_max,
            "heavy_tailed": heavy,
        }

    flags = []
    if isolates:
        flags.append(f"{isolates} isolated node(s) — expected, or a data issue?")
    if len(comp_sizes) > 1 and profile["components"]["giant_share"] < 0.9:
        flags.append(
            f"graph is fragmented: {len(comp_sizes)} components, largest holds "
            f"{profile['components']['giant_share']:.0%} of nodes"
        )
    if top_share > 0.4 and n >= 20:
        flags.append(
            f"hub-dominated: the top 5% of nodes touch {top_share:.0%} of all ties"
        )
    if profile.get("weights", {}).get("heavy_tailed"):
        flags.append(
            f"edge weights are heavy-tailed (median "
            f"{profile['weights']['median']:g}, max {profile['weights']['max']:g}): "
            "the strongest ties will dominate any force layout — log-transform "
            "weights before laying out, or set edgeWeightInfluence below 1"
        )
    if (assortativity is not None and assortativity <= -0.3 and n >= 50):
        flags.append(
            f"strongly disassortative (assortativity {assortativity:.2f}): "
            "hub-and-spoke wiring — in ForceAtlas 2 enable distributedAttraction "
            "(dissuade hubs) so hubs don't collapse their neighborhoods"
        )
    if profile["density"] > 0.3 and n >= 20:
        flags.append("very dense — force layouts will hairball; consider filtering weak ties")
    if n >= 200 and degrees and degrees[n // 2] <= 1:
        flags.append(
            "leaf-majority: most nodes have a single tie, so full renders will look "
            "like a dandelion — for a readable map, filter to degree >= 2 (the "
            "conversational skeleton) and keep the full graph for statistics"
        )
    if n >= 100 and 0 < seen_pairs <= 2.0 * n:
        flags.append(
            "tree-like: barely more ties than nodes, so communities are star/branch "
            "structures with no ties pulling them together — force layouts will NOT "
            "separate them no matter how long they run; after community detection "
            "use gephi_community_layout instead"
        )
    profile["flags"] = flags
    return profile
