"""Pins on graph_diff behaviour that mutation testing showed nothing else checked."""

import pytest

from graph_diff import _number, diff_graphs


def graph(nodes, edges=()):
    return {"nodes": [{"key": k, "attributes": a} for k, a in nodes.items()],
            "edges": [{"source": s, "target": t} for s, t in edges]}


def test_graphs_missing_nodes_or_edges_keys_count_as_empty():
    """A graph with no 'nodes' or no 'edges' entry is read as having none."""
    result = diff_graphs({"edges": []}, {"nodes": [{"key": "a"}]})
    assert result["nodes"]["added"] == ["a"]
    assert result["edges"]["added"] == []
    result = diff_graphs({"nodes": [{"key": "a"}]}, {})
    assert result["nodes"]["removed"] == ["a"]
    assert result["edges"]["removed"] == []


def test_result_has_exactly_the_documented_sections_and_counts():
    """The result carries nodes/edges/changed with before, after, and shared counts."""
    before = graph({"a": {}, "b": {}, "c": {}}, [("a", "b"), ("b", "c")])
    after = graph({"a": {}, "b": {}}, [("a", "b")])
    result = diff_graphs(before, after)
    assert set(result) == {"nodes", "edges", "changed"}
    assert result["nodes"] == {"added": [], "removed": ["c"], "shared": 2, "before": 3, "after": 2}
    assert result["edges"] == {"added": [], "removed": [["b", "c"]], "shared": 1, "directed": False}
    assert result["changed"] is None


def test_edges_are_undirected_by_default():
    """Without directed=True, an edge reversed between versions is the same edge."""
    before = graph({"a": {}, "b": {}}, [("a", "b")])
    after = graph({"a": {}, "b": {}}, [("b", "a")])
    edges = diff_graphs(before, after)["edges"]
    assert edges["added"] == [] and edges["removed"] == [] and edges["shared"] == 1
    assert edges["directed"] is False


def test_directed_edges_keep_their_direction():
    """With directed=True, a reversed edge is one removed and one added."""
    before = graph({"a": {}, "b": {}}, [("a", "b")])
    after = graph({"a": {}, "b": {}}, [("b", "a")])
    edges = diff_graphs(before, after, directed=True)["edges"]
    assert edges["added"] == [["b", "a"]]
    assert edges["removed"] == [["a", "b"]]
    assert edges["shared"] == 0
    assert edges["directed"] is True


@pytest.mark.parametrize("column, key", [
    ("in_degree", "In Degree"), ("In Degree", "in_degree"), ("indegree", "in_degree"),
    ("indegree", "in degree"), ("in_degree", "indegree"), ("in degree", "indegree"),
    ("IN_DEGREE", "In Degree"),
])
def test_number_matches_column_names_ignoring_case_underscores_and_spaces(column, key):
    """A column is found however the export spelled it."""
    assert _number({key: "4"}, column) == 4.0


def test_number_is_none_for_absent_or_non_numeric_values():
    """No matching column, or a value that is not a number, gives None."""
    assert _number({"Degree": "x"}, "degree") is None
    assert _number({"Degree": None}, "degree") is None
    assert _number({"Other": "1"}, "degree") is None


def test_change_counts_every_comparable_node_and_names_the_column():
    """comparable counts each shared node with numbers on both sides, one at a time."""
    nodes = {"a": {"Degree": "1"}, "b": {"Degree": "2"}, "c": {"Degree": "3"}}
    after = {"a": {"Degree": "2"}, "b": {"Degree": "2"}, "c": {"Degree": "1"}}
    change = diff_graphs(graph(nodes), graph(after), compare="Degree")["changed"]
    assert change["column"] == "Degree"
    assert change["comparable"] == 3
    assert change["grew"] == [{"node": "a", "before": 1.0, "after": 2.0}]
    assert change["shrank"] == [{"node": "c", "before": 3.0, "after": 1.0}]
    assert change["unchanged"] == ["b"]
    assert "warning" not in change


def test_a_node_with_a_number_on_only_one_side_is_skipped_not_compared():
    """A value missing on either side drops that node; the others are still compared."""
    before = graph({"a": {"Degree": "x"}, "b": {"Degree": "1"}, "c": {"Degree": "5"}})
    after = graph({"a": {"Degree": "3"}, "b": {"Degree": "2"}, "c": {"Degree": "y"}})
    change = diff_graphs(before, after, compare="Degree")["changed"]
    assert change["comparable"] == 1
    assert change["grew"] == [{"node": "b", "before": 1.0, "after": 2.0}]


def test_nothing_comparable_warns_instead_of_claiming_no_change():
    """When no shared node has a number on both sides the change section carries a warning."""
    before = graph({"a": {"Degree": "x"}})
    after = graph({"a": {"Degree": "1"}})
    change = diff_graphs(before, after, compare="Degree")["changed"]
    assert change["comparable"] == 0
    assert change["unchanged"] == []
    assert "warning" in change


def test_disjoint_graphs_carry_a_warning_but_overlapping_ones_do_not():
    """No shared node ids is flagged; a single shared id is not."""
    assert "warning" in diff_graphs(graph({"a": {}}), graph({"b": {}}))
    assert "warning" not in diff_graphs(graph({"a": {}}), graph({"a": {}, "b": {}}))
    assert "warning" not in diff_graphs(graph({}), graph({"b": {}}))


def test_directed_flag_applies_to_the_earlier_graph_too():
    """With directed=True an edge present, same way round, in both versions is shared."""
    both = graph({"a": {}, "b": {}}, [("b", "a")])
    edges = diff_graphs(both, both, directed=True)["edges"]
    assert edges["shared"] == 1
    assert edges["added"] == [] and edges["removed"] == []
