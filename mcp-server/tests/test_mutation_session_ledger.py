"""Pins on session_ledger behaviour that mutation testing showed nothing else checked."""

import logging

from session_ledger import Ledger


def test_colour_partition_is_the_column_of_the_latest_node_colouring_when_categorical():
    """The latest node-colour operation decides: a partition gives its column, a ranking gives None."""
    ledger = Ledger()
    assert ledger.colour_partition() is None
    ledger.record("color_by_partition", column="modularity_class")
    assert ledger.colour_partition() == "modularity_class"
    ledger.record("color_by_ranking", column="Degree")
    assert ledger.colour_partition() is None
    ledger.record("color_by_partition", column="region")
    assert ledger.colour_partition() == "region"


def test_colour_partition_ignores_other_operations_after_the_colouring():
    """Layout, size and edge operations after the colouring do not hide it."""
    ledger = Ledger()
    ledger.record("color_by_partition", column="group")
    ledger.record("size_by_ranking", column="Degree")
    ledger.record("color_edges_by_partition", column="other")
    ledger.record("run_layout", name="x")
    assert ledger.colour_partition() == "group"


def test_legend_item_carries_every_detail_of_its_mapping():
    """A mapping's groups, palette, size range and cap are all reported for the legend."""
    ledger = Ledger()
    ledger.record("size_by_ranking", column="Degree", min_size=5, max_size=40, cap=0)
    ledger.record("color_by_partition", column="grp", groups=3, palette="Set2")
    assert ledger.legend_items() == [
        {"channel": "node size", "column": "Degree", "range": [5, 40], "cap": 0},
        {"channel": "node colour", "column": "grp", "groups": 3, "palette": "Set2"},
    ]


def test_legend_range_appears_when_only_one_bound_is_given():
    """A size range with just a minimum or just a maximum is still reported, the other side None."""
    ledger = Ledger()
    ledger.record("size_by_ranking", column="Degree", min_size=5)
    assert ledger.legend_items()[0]["range"] == [5, None]
    other = Ledger()
    other.record("size_by_ranking", column="Degree", max_size=9)
    assert other.legend_items()[0]["range"] == [None, 9]


def test_legend_omits_details_that_were_not_given():
    """Without groups, palette, range or cap the item is just channel and column."""
    ledger = Ledger()
    ledger.record("color_by_ranking", column="Degree")
    assert ledger.legend_items() == [{"channel": "node colour", "column": "Degree"}]


def test_legend_items_uses_the_entries_it_is_given_and_skips_non_legend_ones():
    """Explicit entries replace the live ones, and a non-legend entry does not end the scan."""
    ledger = Ledger()
    ledger.record("color_by_partition", column="live")
    given = [{"operation": "run_layout"},
             {"operation": "color_by_partition", "column": "given"},
             {"operation": "statistic", "metric": "degree"},
             {"operation": "size_by_ranking", "column": "Degree"}]
    assert ledger.legend_items(given) == [
        {"channel": "node colour", "column": "given"},
        {"channel": "node size", "column": "Degree"},
    ]
    assert ledger.legend_items([]) == []


def test_summary_defaults_statistic_params_to_an_empty_dict_and_keeps_the_legend():
    """A statistic run without parameters reports {} and the summary names its legend."""
    ledger = Ledger()
    ledger.record("statistic", metric="degree")
    ledger.record("color_by_partition", column="grp")
    summary = ledger._summary(ledger.entries)
    assert summary["statistics"] == [{"metric": "degree", "params": {}}]
    assert summary["legend"] == [{"channel": "node colour", "column": "grp"}]
    assert ledger.receipt()["legend"] == summary["legend"]


def test_summary_builds_its_legend_from_the_entries_it_is_given():
    """A summary of other entries describes those entries, not the live ones."""
    ledger = Ledger()
    ledger.record("color_by_partition", column="live")
    other = [{"operation": "size_by_ranking", "column": "Degree"}]
    assert ledger._summary(other)["legend"] == [{"channel": "node size", "column": "Degree"}]


def test_a_failed_record_is_logged_with_the_operation_name(caplog):
    """When recording fails the warning names the operation and nothing is raised."""
    ledger = Ledger()
    ledger.entries = None  # appending now fails
    with caplog.at_level(logging.WARNING, logger="gephi_mcp.ledger"):
        ledger.record("run_layout", name="x")
    assert len(caplog.records) == 1
    assert "run_layout" in caplog.records[0].getMessage()
