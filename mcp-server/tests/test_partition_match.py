"""Do the detected groups match a grouping the researcher already has?

"Does community detection recover the real factions / departments / field sites?" is one of the
first questions asked of a partition. Answering it takes a cross-table and an agreement score;
without them the question gets answered by eye.
"""

import pytest

from partition_match import compare_partitions


def test_identical_groupings_agree_completely_even_under_other_names():
    result = compare_partitions([("0", "A"), ("0", "A"), ("1", "B"), ("1", "B")])

    assert result["adjusted_rand"] == pytest.approx(1.0)
    assert result["normalized_mutual_information"] == pytest.approx(1.0)


def test_crossed_groupings_score_below_chance_on_rand_and_zero_on_information():
    result = compare_partitions([("0", "A"), ("0", "B"), ("1", "A"), ("1", "B")])

    assert result["adjusted_rand"] == pytest.approx(-0.5)
    assert result["normalized_mutual_information"] == pytest.approx(0.0)


def test_the_cross_table_counts_every_combination():
    result = compare_partitions([("0", "A"), ("0", "A"), ("0", "B"), ("1", "B")])

    assert result["table"] == {"0": {"A": 2, "B": 1}, "1": {"B": 1}}


def test_each_group_names_the_value_most_of_its_members_share():
    result = compare_partitions([("0", "A"), ("0", "A"), ("0", "B"), ("1", "B")])

    best = {g["group"]: (g["mostly"], g["share"]) for g in result["groups"]}
    assert best["0"] == ("A", pytest.approx(2 / 3))
    assert best["1"] == ("B", pytest.approx(1.0))


def test_nodes_missing_either_value_are_left_out_and_counted():
    result = compare_partitions([("0", "A"), ("0", None), (None, "B"), ("1", "B")])

    assert result["compared"] == 2 and result["left_out"] == 2


def test_nothing_to_compare_is_refused():
    with pytest.raises(ValueError):
        compare_partitions([("0", None), (None, "B")])
