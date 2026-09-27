"""Two-mode networks: people by events, authors by concepts, informants by sites.

Gephi draws a two-mode network as though every node were the same kind of thing, which
misrepresents the data at a glance and has no fix in the application: gephi/gephi#3131 asked for a
bipartite layout and notes the only plugin offering one was removed from the current release, and
gephi-plugins#130 asked for multimode support in 2016. Projection, the operation that collapses a
two-mode network into a one-mode one, does not exist in Gephi at all.

Both are computed here in Python. The layout is pushed as coordinates and the projection as a new
graph, so neither needs a Gephi layout plugin or any change to the Java side.

Gephi has no concept of a node's mode, so the mode is whatever column the researcher names. That
is a convention rather than a property of the data, which is why a column carrying more than two
values is refused rather than guessed at.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

Graph = dict[str, Any]


def column_value(attributes: dict[str, Any], column: str) -> Any:
    """A node's value in a column named by id or title, ignoring case, spaces and underscores."""
    wanted = column.replace("_", "").replace(" ", "").lower()
    for key, value in (attributes or {}).items():
        if key.replace("_", "").replace(" ", "").lower() == wanted:
            return value
    return None


def split_modes(graph: Graph, column: str) -> tuple[list[str], list[str]]:
    """The two groups of nodes named by `column`, in the order the values first appear."""
    seen: dict[Any, list[str]] = {}
    for node in graph.get("nodes", []):
        value = column_value(node.get("attributes"), column)
        if value is None:
            continue
        seen.setdefault(value, []).append(node["key"])
    if not seen:
        raise ValueError(
            f"No node carries a value in {column!r}, so the two modes cannot be told apart.")
    if len(seen) != 2:
        raise ValueError(
            f"{column!r} holds {len(seen)} distinct values ({sorted(map(str, seen))}). A bipartite "
            "graph has exactly two modes; name a column that separates them.")
    left, right = seen.values()
    return left, right


WEIGHTINGS = ("shared", "jaccard", "newman")


def project_bipartite(graph: Graph, column: str, keep: str,
                      weighting: str = "shared") -> dict[str, Any]:
    """Collapse a two-mode network onto one mode, joining nodes that share a partner.

    Two people who attended the same event become connected. `weighting` sets the tie strength:
    "shared" counts the events they shared; "jaccard" divides that by all the events either
    attended, so frequent attendees do not dominate; "newman" counts each shared event as
    1/(attendees - 1), so a small meeting ties people more closely than a large gathering
    (Newman 2001). Nodes sharing nothing are kept with no edges: dropping them would silently
    delete people from the network, which is a different graph rather than a tidier one.
    """
    if weighting not in WEIGHTINGS:
        raise ValueError(f"Unknown weighting {weighting!r}; use one of {', '.join(WEIGHTINGS)}.")
    left, right = split_modes(graph, column)
    modes = {}
    for node in graph.get("nodes", []):
        modes[node["key"]] = column_value(node.get("attributes"), column)

    kept = [k for k in (left + right) if str(modes.get(k)) == str(keep)]
    if not kept:
        raise ValueError(
            f"No node has {column}={keep!r}. Present values: "
            f"{sorted({str(v) for v in modes.values() if v is not None})}.")

    partners: dict[str, set[str]] = {k: set() for k in kept}
    within = 0
    for edge in graph.get("edges", []):
        s, t = edge["source"], edge["target"]
        if modes.get(s) == modes.get(t):
            within += 1
            continue
        for node, other in ((s, t), (t, s)):
            if node in partners:
                partners[node].add(other)

    attendees: dict[str, int] = {}
    for mine in partners.values():
        for other in mine:
            attendees[other] = attendees.get(other, 0) + 1

    edges = []
    for a, b in combinations(sorted(kept), 2):
        common = partners[a] & partners[b]
        if not common:
            continue
        if weighting == "jaccard":
            weight: float = len(common) / len(partners[a] | partners[b])
        elif weighting == "newman":
            weight = sum(1 / (attendees[p] - 1) for p in common)
        else:
            weight = len(common)
        edges.append({"source": a, "target": b, "weight": weight})

    result: dict[str, Any] = {
        "nodes": sorted(kept),
        "edges": edges,
        "kept_mode": keep,
        "weighting": weighting,
        "within_mode_edges": within,
    }
    if within:
        result["warning"] = (
            f"{within} edge(s) join two nodes of the same mode, so this graph is not bipartite. "
            "Those edges were ignored in the projection; check the mode column before relying on "
            "the result.")
    return result


def bipartite_positions(graph: Graph, column: str, *,
                        separation: float = 600.0, spacing: float = 60.0) -> list[dict[str, Any]]:
    """Coordinates placing each mode in its own column, which is what makes the shape legible.

    Returned in the shape gephi_batch_set_positions accepts, so the layout is pushed rather than
    implemented as a Gephi layout plugin.
    """
    left, right = split_modes(graph, column)
    positions = []
    for index, members in enumerate((left, right)):
        x = -separation / 2 if index == 0 else separation / 2
        span = (len(members) - 1) * spacing
        for row, key in enumerate(members):
            positions.append({"id": key, "x": float(x),
                              "y": float(row * spacing - span / 2)})
    return positions
