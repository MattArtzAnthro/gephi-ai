"""Pins on partition_match behaviour that mutation testing showed nothing else checked."""

import pytest

from partition_match import _adjusted_rand, _nmi, compare_partitions


def test_groups_are_ordered_by_size_then_name():
    """Groups run largest first; equal sizes fall back to name, not to first appearance."""
    pairs = [("b", "x"), ("a", "y"), ("c", "x"), ("c", "x"), ("c", "y")]
    groups = compare_partitions(pairs)["groups"]
    assert [g["group"] for g in groups] == ["c", "a", "b"]
    assert [g["size"] for g in groups] == [3, 1, 1]


def test_tied_known_values_resolve_to_the_last_by_name():
    """When two known values tie in a group, the later name is reported as 'mostly'."""
    groups = compare_partitions([("g", "x"), ("g", "y")])["groups"]
    assert groups == [{"group": "g", "size": 2, "mostly": "y", "share": 0.5}]


def test_group_entries_report_size_and_share_of_the_modal_value():
    """Each group entry carries its size and the share held by its most common value."""
    pairs = [("a", "x"), ("a", "x"), ("a", "y"), ("b", "y")]
    groups = compare_partitions(pairs)["groups"]
    assert groups[0] == {"group": "a", "size": 3, "mostly": "x", "share": 2 / 3}
    assert groups[1] == {"group": "b", "size": 1, "mostly": "y", "share": 1.0}


def test_a_single_node_is_perfect_agreement():
    """With one node there are no pairs, and the adjusted Rand index is 1.0."""
    result = compare_partitions([("a", "x")])
    assert result["adjusted_rand"] == 1.0
    assert result["normalized_mutual_information"] == 1.0


def test_two_nodes_split_on_one_side_only_score_zero():
    """One side splits two nodes and the other joins them: ARI 0.0, not the n<2 shortcut."""
    result = compare_partitions([("a", "x"), ("b", "x")])
    assert result["adjusted_rand"] == 0.0
    assert result["normalized_mutual_information"] == 0.0


def test_both_sides_one_group_is_perfect_agreement():
    """Everything in one group on both sides is identical groupings: both scores are 1.0."""
    result = compare_partitions([("a", "x")] * 3)
    assert result["adjusted_rand"] == 1.0
    assert result["normalized_mutual_information"] == 1.0


def test_nmi_is_zero_when_one_side_is_a_single_group_and_the_other_is_not():
    """One uninformative side tells you nothing about the other: NMI 0, not 1."""
    result = compare_partitions([("a", "x"), ("a", "y"), ("a", "x"), ("a", "y")])
    assert result["normalized_mutual_information"] == 0.0
    result = compare_partitions([("a", "x"), ("b", "x"), ("c", "x")])
    assert result["normalized_mutual_information"] == 0.0


def test_nmi_known_value_for_a_half_overlap():
    """NMI of [aabb] vs [abbb]-style table matches the hand-computed value."""
    from math import log
    pairs = [("a", "x"), ("a", "x"), ("b", "y"), ("b", "x")]
    # rows: a=2,b=2 -> H=ln2; cols: x=3,y=1 -> H=-(.75ln.75+.25ln.25)
    h_r = log(2)
    h_c = -(0.75 * log(0.75) + 0.25 * log(0.25))
    mi = (0.5 * log(2 * 4 / (2 * 3)) + 0.25 * log(1 * 4 / (2 * 1)) + 0.25 * log(1 * 4 / (2 * 3)))
    assert compare_partitions(pairs)["normalized_mutual_information"] == pytest.approx(
        mi / ((h_r + h_c) / 2))


def test_private_scores_on_degenerate_tables():
    """The helpers return exactly 1.0 for identical single-group tables."""
    from collections import Counter
    cells = Counter({("a", "x"): 3})
    rows, cols = Counter({"a": 3}), Counter({"x": 3})
    assert _adjusted_rand(cells, rows, cols, 3) == 1.0
    assert _nmi(cells, rows, cols, 3) == 1.0
    assert _adjusted_rand(Counter({("a", "x"): 1}), Counter({"a": 1}), Counter({"x": 1}), 1) == 1.0
