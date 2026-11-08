"""Pins on the community_stability helpers that mutation testing showed nothing else checked."""

import numpy as np

from community_stability import _groups, _label_matrix


def test_label_matrix_marks_absent_nodes_minus_one_and_renumbers_per_run():
    """Absent nodes are -1 and each run's labels are renumbered from 0 in order of appearance."""
    runs = [{"a": "p", "b": "q", "c": "p"}, {"b": 9, "c": 4}]
    labels, nodes = _label_matrix(runs)
    assert nodes == ["a", "b", "c"]
    assert labels.tolist() == [[0, 1, 0], [-1, 0, 1]]


def test_groups_with_no_pairs_leaves_every_node_alone():
    """With no pairs at all each node is its own group, ordered by name."""
    assert _groups(["c", "a", "b"], []) == [["a"], ["b"], ["c"]]


def test_groups_orders_largest_first_then_by_first_member():
    """Groups come largest first; equal sizes order by their first node."""
    nodes = ["a", "b", "c", "d", "e"]
    pairs = [(np.array([1, 3]), np.array([2, 4]))]  # b-c and d-e
    assert _groups(nodes, pairs) == [["b", "c"], ["d", "e"], ["a"]]
    pairs = [(np.array([2, 3]), np.array([3, 4]))]  # c-d-e chain
    assert _groups(nodes, pairs) == [["c", "d", "e"], ["a"], ["b"]]


def test_groups_joins_nodes_connected_in_either_direction():
    """A pair given only one way (row to column) still joins both nodes, through a chain."""
    nodes = ["a", "b", "c"]
    pairs = [(np.array([0]), np.array([1])), (np.array([2]), np.array([1]))]
    assert _groups(nodes, pairs) == [["a", "b", "c"]]
