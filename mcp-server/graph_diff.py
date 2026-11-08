"""Comparing the same network measured twice.

Asking what changed between two versions of a network is an ordinary question and Gephi cannot
answer it. gephi/gephi#2013 specified the answer in 2018 — which nodes arrived, which left, which
grew and which shrank — and it was never built, so today the only route is exporting both and
comparing by hand.

The comparison turns entirely on node identity, and that is the part that goes wrong quietly. Two
workspaces only diff meaningfully when the same id means the same thing in both. When they share
nothing, the honest reading is almost always a mismatched key rather than total turnover, so that
case is reported as a caveat instead of presented as a finding.
"""

from __future__ import annotations

from typing import Any

Graph = dict[str, Any]


def _nodes(graph: Graph) -> dict[str, dict[str, Any]]:
    return {n["key"]: (n.get("attributes") or {}) for n in (graph or {}).get("nodes", [])}


def _labels(graph: Graph) -> set[str]:
    """Node labels, falling back to the id as Gephi shows a node without one."""
    return {str(n.get("label") or n["key"]) for n in (graph or {}).get("nodes", [])}


def _edges(graph: Graph, directed: bool) -> set[tuple[str, str]]:
    out = set()
    for edge in (graph or {}).get("edges", []):
        pair = (edge["source"], edge["target"])
        out.add(pair if directed else tuple(sorted(pair)))
    return out


def _number(attributes: dict[str, Any], column: str) -> float | None:
    """The value of `column` as a number, matching however this export spelled the name."""
    wanted = column.replace("_", "").replace(" ", "").lower()
    for key, value in attributes.items():
        if key.replace("_", "").replace(" ", "").lower() == wanted:
            try:
                return float(value)
            except (TypeError, ValueError):
                return None
    return None


# How many ids each list keeps when the two graphs share no node at all.
DISJOINT_EXAMPLES = 5


def diff_graphs(before: Graph, after: Graph, *, compare: str | None = None,
                directed: bool = False) -> dict[str, Any]:
    """What changed between two versions of a network.

    `compare` names a numeric column to track across the nodes present in both, which is what
    gephi/gephi#2013 wanted colour to encode. Omit it and no change section is claimed at all,
    since reporting an empty one would assert that nothing moved.
    """
    a, b = _nodes(before), _nodes(after)
    shared = sorted(set(a) & set(b))

    result: dict[str, Any] = {
        "nodes": {
            "added": sorted(set(b) - set(a)),
            "removed": sorted(set(a) - set(b)),
            "shared": len(shared),
            "before": len(a),
            "after": len(b),
        },
        "edges": {},
        "changed": None,
    }

    ea, eb = _edges(before, directed), _edges(after, directed)
    result["edges"] = {
        "added": [list(e) for e in sorted(eb - ea)],
        "removed": [list(e) for e in sorted(ea - eb)],
        "shared": len(ea & eb),
        "directed": directed,
    }

    if a and b and not shared:
        # Listing every node and edge here is the total turnover the warning says not to read,
        # and on two large graphs it ran to hundreds of thousands of characters.
        for section in (result["nodes"], result["edges"]):
            for side in ("added", "removed"):
                section[side + "_count"] = len(section[side])
                section[side] = section[side][:DISJOINT_EXAMPLES]
        # The next question is whether the same nodes sit under different ids. Labels are the
        # usual second key; checking them here saves reading each workspace by hand.
        common = sorted(_labels(before) & _labels(after))
        result["nodes"]["label_overlap"] = {"count": len(common),
                                            "examples": common[:DISJOINT_EXAMPLES]}
        if common:
            labels_say = (f"{len(common)} labels do appear on both sides, so the same nodes may "
                          "sit under different ids: the label is a candidate key.")
        else:
            labels_say = "Their labels do not match either, so no shared key was found."
        result["warning"] = (
            "The two graphs have no nodes in common, so every node reads as added or removed. "
            "That is far more often a mismatched identifier than real turnover: check that both "
            f"sides use the same node ids before treating this as a finding. {labels_say} The "
            f"lists show the first {DISJOINT_EXAMPLES} examples; the counts give the totals.")

    if compare:
        grew, shrank, unchanged, comparable = [], [], [], 0
        for key in shared:
            was, now = _number(a[key], compare), _number(b[key], compare)
            if was is None or now is None:
                continue
            comparable += 1
            if now > was:
                grew.append({"node": key, "before": was, "after": now})
            elif now < was:
                shrank.append({"node": key, "before": was, "after": now})
            else:
                unchanged.append(key)
        change: dict[str, Any] = {
            "column": compare, "comparable": comparable,
            "grew": grew, "shrank": shrank, "unchanged": unchanged,
        }
        if comparable == 0:
            change["warning"] = (
                f"No node carried a comparable number in {compare!r} on both sides, so nothing "
                "was compared. This is not a finding that nothing changed.")
        result["changed"] = change

    return result
