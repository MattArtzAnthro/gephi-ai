"""Comparing the same network measured twice.

gephi/gephi#2013 asked for this in 2018 and specified it precisely: given an older network and a
newer one, show the difference, with colour saying whether a node grew, shrank, arrived, or left.
It has never been built, and today the only way to answer it is to export both and compare by hand.

The comparison turns on node identity, which is the part that can quietly go wrong. Two workspaces
only diff meaningfully if the same id means the same thing in both, so the result says how many
nodes it could match rather than silently treating an unmatched node as new.
"""

import pytest

from graph_diff import diff_graphs


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
