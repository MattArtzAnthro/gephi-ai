"""Structural profile of a parsed graph: the cheap, always-computable facts.

Complements the Gephi-side statistics (modularity, clustering coefficient,
path lengths) with everything derivable directly from nodes and edges, so a
single profiling call can hand the model a compact quantitative picture.
"""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Sequence
from typing import Any


def _gini(values: Sequence[float]) -> float:
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


def freeman_degree_centralization(degrees: Sequence[float], n: int) -> float | None:
    """How concentrated degree is, against the most concentrated arrangement on n nodes.

    Freeman's measure: the observed total departure from the maximum degree, over the departure
    a star on the same number of nodes would give. 1.0 is a star, 0.0 is any graph where every
    node has the same degree.

    Returns None below three nodes, where the denominator is zero and the measure has no meaning.
    Undefined is not the same as zero, and reporting 0.0 there would be a claim we cannot make.

    Answers gephi#984, open since 2014.
    """
    if n < 3 or not degrees:
        return None
    d_max = max(degrees)
    return sum(d_max - d for d in degrees) / ((n - 1) * (n - 2))


# Below this many nodes a network with no odd cycle is too small to say anything about modes.
_TWO_MODE_MIN_NODES = 10
_MUTUAL_MIN_TIES = 10


def _two_sets(nodes: Sequence[str], pairs: set[tuple[str, str]]) -> dict[str, int] | None:
    """Split the nodes into two sets with every tie running between them, or None.

    `pairs` are the distinct ties without self-loops. Isolated nodes are left out of the split.
    """
    neighbours: dict[str, list[str]] = {}
    for a, b in pairs:
        neighbours.setdefault(a, []).append(b)
        neighbours.setdefault(b, []).append(a)
    side: dict[str, int] = {}
    for start in nodes:
        if start in side or start not in neighbours:
            continue
        side[start] = 0
        stack = [start]
        while stack:
            current = stack.pop()
            for other in neighbours[current]:
                if other not in side:
                    side[other] = 1 - side[current]
                    stack.append(other)
                elif side[other] == side[current]:
                    return None
    return side


def _type_signals(nodes: Sequence[str], edges: list[tuple[str, str]], weights: list[float],
                  directed: bool, weighted: bool, components: int,
                  times: dict | None) -> list[dict]:
    """What structure can show about the kind of network, each as evidence plus a question.

    Structure shows what a network could be, never what it is: a grid has no odd cycle and is
    not two-mode. So nothing here is a verdict, and each signal ends in a question for the
    person who knows the data.
    """
    out: list[dict] = []

    def signal(kind: str, evidence: dict, reading: str, question: str) -> None:
        out.append({"type": kind, "evidence": evidence, "reading": reading, "question": question})

    loops = sum(1 for s, t in edges if s == t)
    ties = {(s, t) for s, t in edges if s != t}
    pairs = {(s, t) if s <= t else (t, s) for s, t in ties}
    touched = {k for pair in pairs for k in pair}

    sources = {s for s, _ in ties}
    targets = {t for _, t in ties}
    never = directed and len(sources) > 1 and len(targets) > 1 and not (sources & targets)
    # A forest has exactly nodes - components ties, and every forest splits in two, so only a
    # network with a cycle is evidence of two modes.
    has_cycle = len(pairs) > len(nodes) - components
    if len(touched) >= _TWO_MODE_MIN_NODES and (never or has_cycle):
        side = {k: 0 for k in sources} | {k: 1 for k in targets} if never else _two_sets(nodes, pairs)
        if side is not None:
            evidence: dict[str, Any] = {"odd_cycles": 0, "clustering": 0.0}
            if never:
                evidence["sources_never_targets"] = True
            if never or components - (len(nodes) - len(touched)) == 1:
                evidence["set_sizes"] = [sum(1 for v in side.values() if v == 0),
                                         sum(1 for v in side.values() if v == 1)]
            signal("two_mode", evidence,
                   "The nodes split into two sets with every tie running between the sets and "
                   "none inside either. That is the shape of a two-mode network, such as people "
                   "and the events they attend, though a one-mode network can have it too. If "
                   "it is two-mode, centrality and community detection do not apply as they "
                   "stand: use gephi_bipartite_layout or gephi_bipartite_projection.",
                   "Are these two different kinds of thing, such as people and events?")

    if directed and len(ties) >= _MUTUAL_MIN_TIES and all((t, s) in ties for s, t in ties):
        signal("all_ties_returned", {"reciprocity": 1.0, "directed_ties": len(ties)},
               "Every directed tie has its reverse. Data like this is usually undirected ties "
               "written once in each direction, in which case direction carries no information "
               "and in- and out-degree are the same number.",
               "Do these ties have a direction, or is each one mutual?")

    negative = sum(1 for w in weights if w < 0)
    if negative:
        signal("negative_weights",
               {"negative": negative, "edges": len(weights), "min": min(weights)},
               "Some edge weights are negative. Modularity, weighted statistics and force "
               "layouts assume weights of zero or more, so their results on this graph are not "
               "meaningful as they stand. Negative ties are usually analysed apart from "
               "positive ones.",
               "Do negative weights mean opposition, such as rivalry against alliance?")

    if loops:
        signal("self_loops", {"self_loops": loops},
               "Some nodes are tied to themselves. Self-loops add to degree and to weighted "
               "statistics.",
               "Are ties from a node to itself meaningful here, or left over from the data?")

    if times is not None:
        on_timeline = times["nodes_with_times"] or times["edges_with_times"]
        signal("time", {"dynamic": True, **times},
               "Nodes or ties carry times, so this network changes over time. A single map and "
               "a single set of statistics describe every period at once."
               if on_timeline else
               "Gephi read this network as one that changes over time, but no node or tie has "
               "a time on the timeline now. The times may sit as text in an ordinary column; "
               "gephi_set_time_from_columns puts a start and an end column on the timeline.",
               "Should this be read as one network, or period by period?")

    if weighted:
        signal("weight_meaning", {"min": min(weights), "max": max(weights)},
               "The ties carry weights. Layouts, weighted statistics and weak-tie filters all "
               "treat a larger weight as a stronger tie, which is backwards when the weight is "
               "a distance, a cost or a time apart.",
               "Does a larger weight mean a stronger tie, or a greater distance?")
    return out


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

    directed = bool(graph.get("directed"))
    profile: dict[str, Any] = {
        "nodes": n,
        "edges": m,
        "directed": directed,
        # A directed tie fills one of n(n-1) ordered pairs (Gephi's Density statistic), an
        # undirected one one of n(n-1)/2.
        "density": ((m if directed else 2 * m) / (n * (n - 1))) if n > 1 else 0.0,
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
        "centralization": {
            "degree": (round(dc, 3) if (dc := freeman_degree_centralization(degrees, n))
                       is not None else None),
        },
        "isolates": isolates,
        "weighted": bool(weights) and len(set(weights)) > 1,
        "clustering_expected_random": round(expected_clustering, 6),
    }

    if profile["directed"]:
        # Share of distinct directed ties whose reverse is also present.
        ties = {(s, t) for s, t in seen_edges if s != t}
        if ties:
            profile["reciprocity"] = round(sum((t, s) in ties for s, t in ties) / len(ties), 3)

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

    profile["type_signals"] = _type_signals(
        nodes, seen_edges, weights, directed, profile["weighted"], len(comp_sizes),
        {"nodes_with_times": sum(1 for item in graph["nodes"] if item.get("spells")),
         "edges_with_times": sum(1 for item in graph["edges"] if item.get("spells"))}
        if graph.get("dynamic") or graph.get("mode") == "dynamic" else None)
    two_mode = any(s["type"] == "two_mode" for s in profile["type_signals"])

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
    # In a two-mode network the hubs of one mode tie only to the other mode, which reads as
    # disassortative whatever the wiring; the two-mode signal is the explanation there.
    if (assortativity is not None and assortativity <= -0.3 and n >= 50 and not two_mode):
        flags.append(
            f"strongly disassortative (assortativity {assortativity:.2f}): "
            "hub-and-spoke wiring — each hub sits in a halo of its own neighbours, which "
            "the layout produces and is not a finding; leave distributedAttraction "
            "(dissuade hubs) off, since it only acts on directed networks and costs "
            "cluster separation"
        )
    if "reciprocity" in profile and profile["reciprocity"] < 0.1 and n >= 50 and not two_mode:
        flags.append(
            f"mostly one-way: only {profile['reciprocity']:.0%} of directed ties are returned — "
            "describe hubs as accounts others address, not as partners in a conversation. "
            "Gephi reads an edge list as directed by default, so confirm the direction is in "
            "the data before reading it"
        )
    if profile["density"] > 0.3 and n >= 20:
        flags.append(
            "very dense — force layouts will hairball; consider filtering weak ties"
            + (", once it is confirmed that a larger weight means a stronger tie"
               if profile["weighted"] else ""))
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
