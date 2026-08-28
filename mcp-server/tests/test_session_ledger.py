"""The session ledger: what the assistant applied to this graph, in order.

Two things need this record and neither can be reconstructed afterwards. A legend has to say what
the colours mean, and the meaning lives in the decision that produced them rather than in the
resulting pixels. A methods paragraph has to say which layout ran with which settings, and Gephi
does not keep that either.

The ledger only knows what came through these tools. Styling applied by hand in the Gephi window
is invisible to it, which is a limit the record has to state rather than paper over.
"""

import pytest

from session_ledger import Ledger


def test_a_fresh_ledger_has_nothing_to_say():
    ledger = Ledger()

    assert ledger.entries == []
    assert ledger.legend_items() == []


def test_it_records_a_colour_mapping_as_a_legend_item():
    ledger = Ledger()

    ledger.record("color_by_partition", column="Modularity Class",
                  groups={"0": "#e15759", "1": "#4e79a7"})

    item = ledger.legend_items()[0]
    assert item["channel"] == "node colour"
    assert item["column"] == "Modularity Class"
    assert item["groups"] == {"0": "#e15759", "1": "#4e79a7"}


def test_it_records_a_size_mapping_as_a_legend_item():
    ledger = Ledger()

    ledger.record("size_by_ranking", column="Degree", min_size=10, max_size=50)

    item = ledger.legend_items()[0]
    assert item["channel"] == "node size"
    assert item["column"] == "Degree"
    assert item["range"] == [10, 50]


def test_restyling_a_channel_replaces_the_earlier_mapping():
    """A legend describes what the map currently shows, not everything ever tried."""
    ledger = Ledger()

    ledger.record("color_by_partition", column="Modularity Class", groups={"0": "#111111"})
    ledger.record("color_by_ranking", column="Degree", palette=["#eeeeee", "#111111"])

    items = ledger.legend_items()
    assert len(items) == 1
    assert items[0]["column"] == "Degree"


def test_node_colour_and_node_size_are_separate_channels():
    ledger = Ledger()

    ledger.record("color_by_partition", column="Modularity Class", groups={"0": "#111111"})
    ledger.record("size_by_ranking", column="Degree", min_size=10, max_size=50)

    assert {i["channel"] for i in ledger.legend_items()} == {"node colour", "node size"}


def test_a_layout_is_recorded_but_is_not_a_legend_item():
    """A layout belongs in the methods record. It encodes no variable, so it explains no colour."""
    ledger = Ledger()

    ledger.record("run_layout", algorithm="ForceAtlas2", iterations=500)

    assert ledger.legend_items() == []
    assert ledger.receipt()["layout"] == {"algorithm": "ForceAtlas2", "iterations": 500}


def test_the_receipt_lists_the_statistics_that_were_run_with_their_settings():
    ledger = Ledger()

    ledger.record("statistic", metric="modularity", params={"resolution": 1.5})
    ledger.record("statistic", metric="betweenness", params={})

    assert ledger.receipt()["statistics"] == [
        {"metric": "modularity", "params": {"resolution": 1.5}},
        {"metric": "betweenness", "params": {}},
    ]


def test_the_same_statistic_run_twice_is_recorded_once_with_the_settings_that_stuck():
    """The columns on the graph hold the last run, so that is what the methods record must say."""
    ledger = Ledger()

    ledger.record("statistic", metric="modularity", params={"resolution": 0.5})
    ledger.record("statistic", metric="modularity", params={"resolution": 2.0})

    assert ledger.receipt()["statistics"] == [
        {"metric": "modularity", "params": {"resolution": 2.0}}]


def test_the_receipt_states_that_manual_styling_is_invisible_to_it():
    """The limit has to be on the record. A reader must not take silence for completeness."""
    ledger = Ledger()
    ledger.record("color_by_partition", column="Modularity Class", groups={"0": "#111111"})

    assert "by hand" in ledger.receipt()["scope"].lower()


def test_the_ledger_forgets_everything_when_the_graph_changes():
    """It describes one graph. A new workspace or a cleared graph is a different one."""
    ledger = Ledger()
    ledger.record("color_by_partition", column="Modularity Class", groups={"0": "#111111"})

    ledger.reset()

    assert ledger.legend_items() == []


def test_an_unrecognised_operation_is_ignored_rather_than_raising():
    """The ledger sits on the path of ordinary styling calls and must never break one."""
    ledger = Ledger()

    ledger.record("something_new_we_do_not_model", column="x")

    assert ledger.legend_items() == []


@pytest.mark.parametrize("bad", [None, {}, {"column": None}])
def test_a_mapping_without_a_column_is_not_a_legend_item(bad):
    """A legend entry with nothing to name explains nothing, and an empty key is worse than none."""
    ledger = Ledger()

    ledger.record("color_by_partition", **(bad or {}))

    assert ledger.legend_items() == []
