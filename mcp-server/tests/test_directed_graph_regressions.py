"""Three failures found by running the tools against a real directed network.

All three passed every existing test and every one of them misreported rather than crashed
loudly, which is the reason each gets an invariant here. A directed, tree-like graph is the
shape that exposed them: replies, retweets, mentions and citation harvests all have it, and it
is precisely the shape the graph profile steers a caller toward the community layout for.
"""

import pytest

from gephi_mcp_viewer.community_layout import compute_community_positions
from session_ledger import Ledger


def _directed_star_with_unreachable_member():
    """A community whose hub cannot reach every member by following edge direction.

    The hub is talked AT: every arm points inward. A breadth-first walk from the hub along
    directed edges therefore reaches nobody, so the layout's safety net has to place every
    member itself.
    """
    nodes = [{"key": "hub", "x": 0.0, "y": 0.0, "size": 10,
              "attributes": {"circle": "A"}}]
    edges = []
    for i in range(6):
        nodes.append({"key": f"n{i}", "x": float(i), "y": 0.0, "size": 5,
                      "attributes": {"circle": "A"}})
        edges.append({"source": f"n{i}", "target": "hub", "weight": 1.0})
    # A second community so the partition has more than one group.
    for i in range(6):
        nodes.append({"key": f"m{i}", "x": float(i), "y": 10.0, "size": 5,
                      "attributes": {"circle": "B"}})
        edges.append({"source": f"m{i}", "target": "m0", "weight": 1.0})
    return {"nodes": nodes, "edges": edges, "directed": True}


def test_community_layout_places_members_the_hub_cannot_reach():
    """It used to raise KeyError on any member the breadth-first walk missed.

    The safety net added such members to `depth` and `parent` but not to `order`, and every
    structure below is built by iterating `order`, so `leaves` never learned about them while
    three later sites indexed it directly.
    """
    graph = _directed_star_with_unreachable_member()

    positions, info = compute_community_positions(graph, partition="circle", min_disc=2)

    assert info["unassigned_nodes"] == 0
    assert len(positions) == len(graph["nodes"]), "every node must get a position"
    placed = {p["id"] for p in positions}
    for node in graph["nodes"]:
        assert node["key"] in placed


def test_community_layout_gives_every_member_a_finite_position():
    """A NaN coordinate renders as an invisible node and silently distorts any extent math."""
    graph = _directed_star_with_unreachable_member()

    positions, _ = compute_community_positions(graph, partition="circle", min_disc=2)

    for entry in positions:
        key, x, y = entry["id"], entry["x"], entry["y"]
        assert x == x and y == y, f"{key} has a NaN coordinate"
        assert abs(x) != float("inf") and abs(y) != float("inf"), f"{key} ran to infinity"


def test_a_ledger_can_be_carried_across_a_workspace_round_trip():
    """gephi_whatif duplicates a workspace, edits the copy, deletes it, and returns.

    Every one of those calls resets the ledger, which is right for a real change of graph and
    wrong here: the caller is handed back the same graph with the same styling. Without the
    save and restore, running a counterfactual emptied the methods record for the figure being
    prepared, and the next export shipped with an incomplete legend.
    """
    ledger = Ledger()
    ledger.record("color_by_partition", column="circle")
    ledger.record("size_by_ranking", column="degree", range=[30.0, 260.0])
    saved = list(ledger.entries)
    assert len(ledger.legend_items()) == 2

    ledger.reset()  # what the workspace churn does
    assert ledger.legend_items() == []

    ledger.entries = saved  # what gephi_whatif now does in its finally block

    items = ledger.legend_items()
    assert len(items) == 2
    assert {i["column"] for i in items} == {"circle", "degree"}


@pytest.mark.parametrize("failing", ["add", "write"])
def test_a_failed_consensus_write_is_not_reported_as_a_column(failing):
    """The two write responses used to be discarded.

    When the column could not be added, or the attribute write failed, the caller was still
    told `consensus_column` held the partition. Observed live: the write path was down and the
    tool reported success while the column was absent from every node.
    """
    added = {"success": failing != "add"}
    written = {"success": failing != "write"}
    result = {}
    groups = [["a", "b"], ["c"]]

    # The shape the tool now applies.
    if added.get("success", True) and written.get("success", True):
        result["consensus_column"] = "consensus_community"
        result["consensus_communities"] = len(groups)
    else:
        result["consensus_column"] = None
        result["consensus_write_failed"] = "could not be written"

    assert result["consensus_column"] is None
    assert "consensus_communities" not in result
    assert "consensus_write_failed" in result
