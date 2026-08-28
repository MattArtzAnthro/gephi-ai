"""Two-mode networks: people by events, authors by concepts, informants by sites.

Gephi draws a two-mode network as though every node were the same kind of thing, which
misrepresents the data at a glance. gephi/gephi#3131 asked for a bipartite layout in 2026 and
notes that the only plugin that offered one was removed from the current release;
gephi-plugins#130 asked for multimode support in 2016. Projection — collapsing a two-mode network
to a one-mode one — does not exist in Gephi at all.

Both are computed here and pushed as positions and as a new graph, so neither needs a Gephi layout
plugin. The mode is whatever column the researcher says it is, since Gephi has no concept of one.
"""

import pytest

from bipartite import bipartite_positions, project_bipartite, split_modes


def graph(nodes, edges=()):
    return {"nodes": [{"key": k, "attributes": {"kind": v}} for k, v in nodes.items()],
            "edges": [{"source": s, "target": t} for s, t in edges]}


# Two people, two events. Ann attends both; Bo attends only the second.
PEOPLE_EVENTS = graph(
    {"ann": "person", "bo": "person", "e1": "event", "e2": "event"},
    [("ann", "e1"), ("ann", "e2"), ("bo", "e2")])


# ── Telling the modes apart ──

def test_it_splits_nodes_by_the_column_it_is_told_to_use():
    left, right = split_modes(PEOPLE_EVENTS, "kind")

    assert set(left) == {"ann", "bo"}
    assert set(right) == {"e1", "e2"}


def test_a_column_with_more_than_two_values_is_refused():
    """Bipartite means two modes. Three is a different problem and must not be guessed at."""
    three = graph({"a": "person", "b": "event", "c": "place"})

    with pytest.raises(ValueError, match="two"):
        split_modes(three, "kind")


def test_a_column_nobody_has_is_refused():
    with pytest.raises(ValueError, match="nonexistent"):
        split_modes(PEOPLE_EVENTS, "nonexistent")


# ── Projection ──

def test_projecting_onto_people_links_those_who_share_an_event():
    result = project_bipartite(PEOPLE_EVENTS, "kind", keep="person")

    assert result["nodes"] == ["ann", "bo"]
    assert result["edges"] == [{"source": "ann", "target": "bo", "weight": 1}]


def test_the_projected_weight_counts_how_many_partners_two_nodes_share():
    both = graph({"ann": "person", "bo": "person", "e1": "event", "e2": "event"},
                 [("ann", "e1"), ("ann", "e2"), ("bo", "e1"), ("bo", "e2")])

    result = project_bipartite(both, "kind", keep="person")

    assert result["edges"] == [{"source": "ann", "target": "bo", "weight": 2}]


def test_projecting_onto_events_links_events_that_share_an_attendee():
    result = project_bipartite(PEOPLE_EVENTS, "kind", keep="event")

    assert result["edges"] == [{"source": "e1", "target": "e2", "weight": 1}]


def test_a_node_sharing_nothing_survives_the_projection_with_no_edges():
    """Dropping isolates would silently delete people, which is a different graph."""
    lonely = graph({"ann": "person", "zed": "person", "e1": "event", "e2": "event"},
                   [("ann", "e1"), ("zed", "e2")])

    result = project_bipartite(lonely, "kind", keep="person")

    assert result["nodes"] == ["ann", "zed"]
    assert result["edges"] == []


def test_projecting_onto_a_mode_that_is_not_there_is_refused():
    with pytest.raises(ValueError, match="student"):
        project_bipartite(PEOPLE_EVENTS, "kind", keep="student")


def test_an_edge_inside_one_mode_is_reported_because_the_graph_is_not_really_bipartite():
    """A person-to-person tie means the data is not two-mode, and projecting it would be wrong."""
    impure = graph({"ann": "person", "bo": "person", "e1": "event"},
                   [("ann", "bo"), ("ann", "e1")])

    result = project_bipartite(impure, "kind", keep="person")

    assert result["within_mode_edges"] == 1
    assert "not bipartite" in result["warning"].lower()


def test_a_clean_two_mode_graph_carries_no_such_warning():
    assert project_bipartite(PEOPLE_EVENTS, "kind", keep="person").get("warning") is None


# ── Layout ──

def test_the_two_modes_are_laid_out_in_two_separate_columns():
    positions = bipartite_positions(PEOPLE_EVENTS, "kind")
    by_id = {p["id"]: p for p in positions}

    assert by_id["ann"]["x"] == by_id["bo"]["x"]
    assert by_id["e1"]["x"] == by_id["e2"]["x"]
    assert by_id["ann"]["x"] != by_id["e1"]["x"]


def test_every_node_is_given_a_position():
    positions = bipartite_positions(PEOPLE_EVENTS, "kind")

    assert {p["id"] for p in positions} == {"ann", "bo", "e1", "e2"}


def test_nodes_in_a_column_are_spread_rather_than_stacked_on_one_point():
    positions = bipartite_positions(PEOPLE_EVENTS, "kind")
    people_y = [p["y"] for p in positions if p["id"] in ("ann", "bo")]

    assert len(set(people_y)) == 2


def test_a_single_node_in_a_mode_does_not_divide_by_zero():
    lone = graph({"ann": "person", "e1": "event"}, [("ann", "e1")])

    positions = bipartite_positions(lone, "kind")

    assert len(positions) == 2
    assert all(isinstance(p["y"], float) for p in positions)
