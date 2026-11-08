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

from collections import Counter
from typing import Any

Graph = dict[str, Any]


def _nodes(graph: Graph) -> dict[str, dict[str, Any]]:
    return {n["key"]: (n.get("attributes") or {}) for n in (graph or {}).get("nodes", [])}


def _labels(graph: Graph) -> Counter[str]:
    """How many nodes carry each label, falling back to the id as Gephi shows a node without
    one."""
    return Counter(str(n.get("label") or n["key"]) for n in (graph or {}).get("nodes", []))


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


# How many entries a long list keeps; the total goes in a *_count beside it. The two graphs
# sharing no node at all always get the counts.
DISJOINT_EXAMPLES = 5
# Graphs that overlap are the normal before/after case, so their lists stay whole up to this
# many entries; only a longer list is cut to this many plus its *_count.
LIST_CAP = 200


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

    disjoint = bool(a and b and not shared)
    # A list longer than its cap becomes its first entries plus a count whatever the overlap: a
    # single shared id used to bring back every other node and edge in full, thousands of ids.
    shortened = False
    for section in (result["nodes"], result["edges"]):
        for side in ("added", "removed"):
            keep = DISJOINT_EXAMPLES if disjoint else LIST_CAP
            if disjoint or len(section[side]) > keep:
                shortened = shortened or len(section[side]) > keep
                section[side + "_count"] = len(section[side])
                section[side] = section[side][:keep]
    if shortened:
        result["note"] = ("Long lists show their first entries only; the *_count beside each "
                          "gives the total.")

    if disjoint:
        # The next question is whether the same nodes sit under different ids. Labels are the
        # usual second key, but only a label held by exactly one node on each side can say which
        # node is which; a name shared by several nodes cannot.
        left, right = _labels(before), _labels(after)
        common = sorted(set(left) & set(right))
        unique = [label for label in common if left[label] == 1 and right[label] == 1]
        result["nodes"]["label_overlap"] = {"count": len(common),
                                            "unique_on_both_sides": len(unique),
                                            "examples": common[:DISJOINT_EXAMPLES]}
        if unique:
            labels_say = (f"{len(common)} labels do appear on both sides and {len(unique)} are "
                          "unique on both, so the same nodes may sit under different ids: "
                          "those labels are a candidate key.")
        elif common:
            labels_say = (f"{len(common)} labels appear on both sides but none is unique on "
                          "both, so a label cannot say which node is which.")
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
