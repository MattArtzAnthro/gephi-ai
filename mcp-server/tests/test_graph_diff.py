"""Comparing the same network measured twice.

gephi/gephi#2013 asked for this in 2018 and specified it precisely: given an older network and a
newer one, show the difference, with colour saying whether a node grew, shrank, arrived, or left.
It has never been built, and today the only way to answer it is to export both and compare by hand.

The comparison turns on node identity, which is the part that can quietly go wrong. Two workspaces
only diff meaningfully if the same id means the same thing in both, so the result says how many
nodes it could match rather than silently treating an unmatched node as new.
"""

import pytest

from graph_diff import LIST_CAP, diff_graphs


def graph(nodes, edges=()):
    return {"nodes": [{"key": k, "attributes": a} for k, a in nodes.items()],
            "edges": [{"source": s, "target": t} for s, t in edges]}


BEFORE = graph({"a": {"Degree": "3"}, "b": {"Degree": "1"}, "c": {"Degree": "2"}},
               [("a", "b"), ("a", "c")])
AFTER = graph({"a": {"Degree": "5"}, "b": {"Degree": "1"}, "d": {"Degree": "1"}},
              [("a", "b"), ("a", "d")])


def test_it_names_the_nodes_that_arrived():
    assert diff_graphs(BEFORE, AFTER)["nodes"]["added"] == ["d"]


def test_it_names_the_nodes_that_left():
    assert diff_graphs(BEFORE, AFTER)["nodes"]["removed"] == ["c"]


def test_it_names_the_nodes_present_in_both():
    assert diff_graphs(BEFORE, AFTER)["nodes"]["shared"] == 2


def test_it_names_the_edges_that_arrived_and_left():
    result = diff_graphs(BEFORE, AFTER)

    assert result["edges"]["added"] == [["a", "d"]]
    assert result["edges"]["removed"] == [["a", "c"]]


def test_an_edge_is_the_same_edge_whichever_way_round_it_is_written():
    """An undirected tie recorded as b-a is the tie a-b, and must not read as one leaving and
    another arriving."""
    result = diff_graphs(graph({"a": {}, "b": {}}, [("a", "b")]),
                         graph({"a": {}, "b": {}}, [("b", "a")]),
                         directed=False)

    assert result["edges"]["added"] == []
    assert result["edges"]["removed"] == []


def test_a_directed_comparison_keeps_the_direction():
    result = diff_graphs(graph({"a": {}, "b": {}}, [("a", "b")]),
                         graph({"a": {}, "b": {}}, [("b", "a")]),
                         directed=True)

    assert result["edges"]["added"] == [["b", "a"]]
    assert result["edges"]["removed"] == [["a", "b"]]


# ── Attribute movement, which is what gephi#2013 wanted colour to encode ──

def test_it_reports_which_shared_nodes_grew():
    result = diff_graphs(BEFORE, AFTER, compare="Degree")

    assert result["changed"]["grew"] == [{"node": "a", "before": 3.0, "after": 5.0}]


def test_it_reports_which_shared_nodes_held_still():
    result = diff_graphs(BEFORE, AFTER, compare="Degree")

    assert result["changed"]["unchanged"] == ["b"]


def test_a_shrinking_node_is_reported_as_shrinking():
    result = diff_graphs(graph({"a": {"Degree": "9"}}), graph({"a": {"Degree": "2"}}),
                         compare="Degree")

    assert result["changed"]["shrank"] == [{"node": "a", "before": 9.0, "after": 2.0}]


def test_asking_to_compare_a_column_nobody_has_is_reported_not_silently_empty():
    """Silence here reads as "nothing changed", which is a different and much stronger claim."""
    result = diff_graphs(BEFORE, AFTER, compare="Nonexistent")

    assert result["changed"]["comparable"] == 0
    assert "Nonexistent" in result["changed"]["warning"]


def test_a_non_numeric_value_is_skipped_rather_than_crashing_the_comparison():
    result = diff_graphs(graph({"a": {"Label": "cat"}}), graph({"a": {"Label": "dog"}}),
                         compare="Label")

    assert result["changed"]["comparable"] == 0


def test_no_comparison_column_means_no_change_section_is_claimed():
    assert diff_graphs(BEFORE, AFTER)["changed"] is None


# ── Identity, the part that quietly goes wrong ──

def test_two_graphs_that_share_no_ids_are_flagged_rather_than_reported_as_total_turnover():
    """Every node added and every node removed is far more often a mismatched key than real
    change, so it must be surfaced as a caveat rather than presented as a finding."""
    result = diff_graphs(graph({"a": {}, "b": {}}), graph({"x": {}, "y": {}}))

    assert result["nodes"]["shared"] == 0
    assert "no nodes in common" in result["warning"].lower()


def test_graphs_that_do_overlap_carry_no_such_warning():
    assert diff_graphs(BEFORE, AFTER).get("warning") is None


@pytest.mark.parametrize("empty", [{"nodes": [], "edges": []}])
def test_comparing_against_an_empty_graph_reports_it_rather_than_raising(empty):
    result = diff_graphs(BEFORE, empty)

    assert result["nodes"]["removed"] == ["a", "b", "c"]
    assert result["nodes"]["added"] == []


def test_graphs_that_share_no_ids_report_counts_and_examples_not_every_node():
    """With nothing in common, listing every node and edge as added and removed is the total
    turnover the warning says not to read: on two 1,000-node graphs it ran to 300,000 characters.
    The reply keeps the counts and a few examples so the mismatch can still be seen."""
    before = graph({f"n{i}": {} for i in range(50)}, [(f"n{i}", f"n{i + 1}") for i in range(49)])
    after = graph({f"d{i}": {} for i in range(40)}, [(f"d{i}", f"d{i + 1}") for i in range(39)])

    result = diff_graphs(before, after)

    assert result["nodes"]["removed_count"] == 50
    assert result["nodes"]["added_count"] == 40
    assert result["nodes"]["removed"] == ["n0", "n1", "n10", "n11", "n12"]
    assert len(result["nodes"]["added"]) == 5
    assert result["edges"]["removed_count"] == 49
    assert result["edges"]["added_count"] == 39
    assert len(result["edges"]["added"]) == len(result["edges"]["removed"]) == 5
    assert "examples" in result["warning"]


def labelled(nodes, edges=()):
    """nodes: {id: label}."""
    return {"nodes": [{"key": k, "label": lab, "attributes": {}} for k, lab in nodes.items()],
            "edges": [{"source": s, "target": t} for s, t in edges]}


def test_graphs_sharing_no_ids_are_checked_by_label_and_say_when_labels_differ_too():
    """Agents comparing two disjoint workspaces switched to each one and sampled labels by hand
    (2 to 4 extra calls) to rule out the same nodes under different ids. The diff answers it."""
    result = diff_graphs(labelled({"n0": "n0", "n1": "n1"}), labelled({"d0": "d0", "d1": "d1"}))

    assert result["nodes"]["label_overlap"] == {"count": 0, "unique_on_both_sides": 0,
                                                "examples": []}
    assert "labels" in result["warning"] and "either" in result["warning"]


def test_graphs_sharing_no_ids_but_sharing_labels_point_at_the_label_as_the_key():
    before = labelled({"1": "Ana", "2": "Ben", "3": "Cy"})
    after = labelled({"p1": "Ana", "p2": "Ben", "p9": "Dee"})

    result = diff_graphs(before, after)

    assert result["nodes"]["label_overlap"] == {"count": 2, "unique_on_both_sides": 2,
                                                "examples": ["Ana", "Ben"]}
    assert "2 labels" in result["warning"]
    assert "candidate key" in result["warning"]


def test_graphs_that_share_ids_get_no_label_check():
    assert "label_overlap" not in diff_graphs(BEFORE, AFTER)["nodes"]


def test_a_label_shared_by_several_nodes_is_not_called_a_candidate_key():
    """Three nodes named "Smith" on each side are one overlapping label, not three matches, and
    the label cannot say which Smith is which. Only labels held by exactly one node on each side
    can serve as a key."""
    before = labelled({"1": "Smith", "2": "Smith", "3": "Smith", "4": "Ana"})
    after = labelled({"p1": "Smith", "p2": "Smith", "p3": "Smith", "p4": "Ana"})

    overlap = diff_graphs(before, after)["nodes"]["label_overlap"]

    assert overlap["count"] == 2
    assert overlap["unique_on_both_sides"] == 1


def test_labels_that_overlap_but_are_never_unique_are_not_offered_as_a_key():
    before = labelled({"1": "Smith", "2": "Smith"})
    after = labelled({"p1": "Smith", "p2": "Smith"})

    result = diff_graphs(before, after)

    assert result["nodes"]["label_overlap"]["unique_on_both_sides"] == 0
    assert "candidate key" not in result["warning"]
    assert "none is unique" in result["warning"]


def test_a_label_unique_on_one_side_only_is_not_unique_on_both():
    before = labelled({"1": "Ana", "2": "Ben"})
    after = labelled({"p1": "Ana", "p2": "Ana", "p3": "Ben"})

    overlap = diff_graphs(before, after)["nodes"]["label_overlap"]

    assert (overlap["count"], overlap["unique_on_both_sides"]) == (2, 1)


def test_one_shared_id_does_not_bring_back_the_full_lists():
    """The counts-and-examples reply used to apply only when the graphs shared no id at all, so
    a single coincidental shared id sent every other node and edge back in full."""
    big = LIST_CAP + 50
    before = graph({"x": {}, **{f"n{i}": {} for i in range(big)}},
                   [(f"n{i}", f"n{i + 1}") for i in range(big - 1)])
    after = graph({"x": {}, **{f"d{i}": {} for i in range(big - 10)}},
                  [(f"d{i}", f"d{i + 1}") for i in range(big - 11)])

    result = diff_graphs(before, after)

    assert result["nodes"]["shared"] == 1
    assert result["nodes"]["removed_count"] == big
    assert result["nodes"]["added_count"] == big - 10
    assert len(result["nodes"]["removed"]) == len(result["nodes"]["added"]) == LIST_CAP
    assert result["edges"]["removed_count"] == big - 1
    assert len(result["edges"]["added"]) == len(result["edges"]["removed"]) == LIST_CAP
    assert "total" in result["note"]


def test_short_lists_stay_in_full_whatever_the_overlap():
    result = diff_graphs(BEFORE, AFTER)

    assert result["nodes"]["added"] == ["d"]
    assert "added_count" not in result["nodes"]
    assert "note" not in result


def test_an_ordinary_change_lists_every_added_node():
    """Overlapping graphs are the normal before/after case: a dozen added nodes must all be
    listed, since the agent has no other way to get them. Only very long lists are cut."""
    before = graph({f"n{i}": {} for i in range(30)}, [])
    after = graph({**{f"n{i}": {} for i in range(30)}, **{f"new{i}": {} for i in range(12)}}, [])

    result = diff_graphs(before, after)

    assert len(result["nodes"]["added"]) == 12
    assert "added_count" not in result["nodes"]
