"""The profile's reading of every network type, offline.

`network_types.generated()` holds one network per kind the tools have to handle. Each is written
to GEXF the way an export is, read back with the parser the server uses, and profiled, so a type
that breaks the parser or the profile fails here on every run, without a Gephi. What a running
Gephi does with each type is `live_workflow_test.py`'s job.
"""

import networkx as nx
import pytest
from network_types import event_log_rows, generated

from gephi_mcp_viewer import parse_gexf
from gephi_mcp_viewer.profile import structural_profile

NETWORKS = generated()


def profile_of(graph: nx.Graph, tmp_path) -> tuple[dict, dict]:
    path = tmp_path / "g.gexf"
    nx.write_gexf(graph, path)
    parsed = parse_gexf(path.read_text(encoding="utf-8"), max_nodes=10**9)
    return parsed, structural_profile(parsed)


def flags(profile: dict) -> str:
    return " ".join(profile.get("flags", []))


@pytest.mark.parametrize("name", sorted(NETWORKS))
def test_every_type_parses_and_profiles_with_its_counts(name, tmp_path):
    graph = NETWORKS[name]
    parsed, profile = profile_of(graph, tmp_path)
    assert profile["nodes"] == graph.number_of_nodes()
    assert profile["directed"] is graph.is_directed()
    assert {n["key"] for n in parsed["nodes"]} == {str(n) for n in graph.nodes}


def test_accented_and_spaced_ids_come_back_unchanged(tmp_path):
    parsed, _ = profile_of(NETWORKS["accented and spaced ids"], tmp_path)
    keys = {n["key"] for n in parsed["nodes"]}
    assert {"Zoë", "José Martí", "Łódź", "Dvořák"} <= keys


def test_a_fragmented_graph_is_flagged_with_its_isolates(tmp_path):
    _, profile = profile_of(NETWORKS["several components + isolates"], tmp_path)
    assert profile["components"]["count"] == 9
    assert profile["isolates"] == 6
    assert "fragmented" in flags(profile) and "isolated" in flags(profile)


def test_a_dominant_hub_is_flagged(tmp_path):
    _, profile = profile_of(NETWORKS["star hub"], tmp_path)
    assert "hub-dominated" in flags(profile)


def test_a_dense_graph_is_flagged(tmp_path):
    _, profile = profile_of(NETWORKS["dense (p=0.85)"], tmp_path)
    assert "very dense" in flags(profile)


def test_heavy_tailed_weights_are_flagged_and_even_ones_are_not(tmp_path):
    _, heavy = profile_of(NETWORKS["heavy-tailed weights"], tmp_path)
    _, les = profile_of(NETWORKS["les-miserables (weighted)"], tmp_path)
    assert heavy["weights"]["heavy_tailed"] is True and "heavy-tailed" in flags(heavy)
    assert les["weights"]["heavy_tailed"] is False


def test_a_one_way_directed_network_is_flagged(tmp_path):
    _, profile = profile_of(NETWORKS["directed weighted replies"], tmp_path)
    assert profile["reciprocity"] < 0.1
    assert "mostly one-way" in flags(profile)


def test_a_directed_tree_is_flagged_tree_like(tmp_path):
    _, profile = profile_of(NETWORKS["directed tree-like"], tmp_path)
    assert "tree-like" in flags(profile)


@pytest.mark.parametrize("name", ["les-miserables (weighted)", "karate (two clubs)",
                                  "four planted blocks", "tiny (two nodes)"])
def test_well_formed_graphs_raise_no_flags(name, tmp_path):
    _, profile = profile_of(NETWORKS[name], tmp_path)
    assert profile.get("flags", []) == []


def test_self_loops_and_repeated_ties_profile_without_error(tmp_path):
    graph = NETWORKS["repeated ties + self-loops"]
    _, profile = profile_of(graph, tmp_path)
    assert profile["weights"]["max"] == max(d["weight"] for _, _, d in graph.edges(data=True))


# The types below carry no column saying what they are. These pin that each one is what its
# name says, so a reading of the type has a known answer to be checked against.


def test_the_unlabelled_two_mode_network_has_two_modes_and_no_column_naming_them():
    graph = NETWORKS["two-mode, unlabelled (numeric ids)"]
    assert nx.is_bipartite(graph)
    assert all(not d for _, d in graph.nodes(data=True))


def test_mutual_ties_stored_directed_are_all_returned(tmp_path):
    graph = NETWORKS["mutual ties stored directed"]
    _, profile = profile_of(graph, tmp_path)
    assert profile["directed"] is True
    assert profile["reciprocity"] == 1.0


def test_signed_weights_reach_the_profile_as_negative_numbers(tmp_path):
    _, profile = profile_of(NETWORKS["signed weights"], tmp_path)
    assert profile["weights"]["min"] == -3.0
    assert profile["weights"]["max"] == 3.0


def test_distance_weights_are_ordinary_positive_weights_to_the_profile(tmp_path):
    # Nothing in the numbers says a larger weight means a weaker tie; that has to be asked.
    _, profile = profile_of(NETWORKS["weight is a distance"], tmp_path)
    assert profile["weighted"] is True
    assert profile["weights"]["min"] > 0


def test_the_event_log_repeats_its_pairs_and_dates_every_row():
    rows = event_log_rows()
    assert len(rows) == 1500
    assert len({(a, b) for a, b, _ in rows}) == 220
    assert all(len(date) == 10 and date.startswith("2025-") for _, _, date in rows)


# ── What kind of network this is: signals with evidence and a question, never a verdict ──


def signals(profile: dict) -> dict:
    return {s["type"]: s for s in profile["type_signals"]}


ORDINARY = ["karate (two clubs)", "four planted blocks", "tiny (two nodes)",
            "les-miserables (weighted)", "dense (p=0.85)", "several components + isolates"]


@pytest.mark.parametrize("name", sorted(NETWORKS))
def test_every_signal_carries_evidence_a_reading_and_a_question(name, tmp_path):
    _, profile = profile_of(NETWORKS[name], tmp_path)
    for signal in profile["type_signals"]:
        assert set(signal) == {"type", "evidence", "reading", "question"}
        assert signal["evidence"] and signal["question"].endswith("?")
        assert not any(word in signal["reading"].lower()
                       for word in ("clearly", "confirms", "this is a", "definitely"))


@pytest.mark.parametrize("name", ["two-mode (people, events)",
                                  "two-mode, unlabelled (numeric ids)"])
def test_two_modes_are_signalled_with_or_without_a_column_naming_them(name, tmp_path):
    graph = NETWORKS[name]
    _, profile = profile_of(graph, tmp_path)
    assert "two_mode" in signals(profile)
    assert "hub-and-spoke" not in flags(profile)


def test_two_mode_set_sizes_are_reported_for_a_connected_network(tmp_path):
    graph = nx.complete_bipartite_graph(4, 9)
    _, profile = profile_of(nx.relabel_nodes(graph, str), tmp_path)
    assert sorted(signals(profile)["two_mode"]["evidence"]["set_sizes"]) == [4, 9]


def test_a_directed_edge_list_whose_sources_are_never_targets_signals_two_modes(tmp_path):
    graph = nx.DiGraph()
    rows = [(f"m{i}", f"g{(i * j) % 7}") for i in range(30) for j in (1, 2)]
    graph.add_edges_from(rows)
    _, profile = profile_of(graph, tmp_path)
    evidence = signals(profile)["two_mode"]["evidence"]
    assert evidence["sources_never_targets"] is True
    assert sorted(evidence["set_sizes"]) == [7, 30]


@pytest.mark.parametrize("name", ["directed tree-like", "star hub", *ORDINARY])
def test_trees_and_ordinary_networks_do_not_signal_two_modes(name, tmp_path):
    # Every tree can be split into two sets, so a tree is not evidence of two modes.
    _, profile = profile_of(NETWORKS[name], tmp_path)
    assert "two_mode" not in signals(profile)


def test_a_small_even_ring_is_below_the_two_mode_floor(tmp_path):
    _, profile = profile_of(nx.relabel_nodes(nx.cycle_graph(6), str), tmp_path)
    assert "two_mode" not in signals(profile)


def test_mutual_ties_stored_directed_are_signalled(tmp_path):
    _, profile = profile_of(NETWORKS["mutual ties stored directed"], tmp_path)
    assert signals(profile)["all_ties_returned"]["evidence"] == {"reciprocity": 1.0,
                                                                 "directed_ties": 480}


def test_a_directed_network_with_one_tie_unreturned_is_not_called_mutual(tmp_path):
    graph = NETWORKS["mutual ties stored directed"].copy()
    graph.remove_edge(*next(iter(graph.edges)))
    _, profile = profile_of(graph, tmp_path)
    assert "all_ties_returned" not in signals(profile)


def test_negative_weights_are_counted(tmp_path):
    graph = NETWORKS["signed weights"]
    _, profile = profile_of(graph, tmp_path)
    negative = sum(d["weight"] < 0 for _, _, d in graph.edges(data=True))
    assert signals(profile)["negative_weights"]["evidence"] == {"negative": negative,
                                                                "edges": 180, "min": -3.0}


def test_self_loops_are_counted(tmp_path):
    _, profile = profile_of(NETWORKS["repeated ties + self-loops"], tmp_path)
    assert signals(profile)["self_loops"]["evidence"] == {"self_loops": 10}


def test_a_timestamped_network_signals_its_time_dimension(tmp_path):
    _, profile = profile_of(NETWORKS["timestamped"], tmp_path)
    assert "time" in signals(profile)


@pytest.mark.parametrize("name", ["weight is a distance", "les-miserables (weighted)"])
def test_any_weighted_network_asks_what_a_larger_weight_means(name, tmp_path):
    # Distance and strength look the same in the numbers, so the question is always asked.
    _, profile = profile_of(NETWORKS[name], tmp_path)
    assert "stronger" in signals(profile)["weight_meaning"]["question"]


def test_the_dense_flag_ties_its_filtering_advice_to_what_the_weight_means(tmp_path):
    _, profile = profile_of(NETWORKS["weight is a distance"], tmp_path)
    assert "very dense" in flags(profile)
    assert "larger weight means a stronger tie" in flags(profile)


def test_the_one_way_flag_says_direction_may_be_an_import_default(tmp_path):
    _, profile = profile_of(NETWORKS["directed weighted replies"], tmp_path)
    assert "mostly one-way" in flags(profile)
    assert "directed by default" in flags(profile)


@pytest.mark.parametrize("name", ORDINARY)
def test_ordinary_networks_raise_no_signal_but_the_weight_question(name, tmp_path):
    _, profile = profile_of(NETWORKS[name], tmp_path)
    assert set(signals(profile)) <= {"weight_meaning"}
    assert ("weight_meaning" in signals(profile)) is profile["weighted"]


def test_two_modes_stored_directed_are_not_also_called_one_way(tmp_path):
    # Ties from one mode to the other are never returned by construction.
    graph = nx.DiGraph((f"m{i}", f"g{(i * j) % 7}") for i in range(60) for j in (1, 2))
    _, profile = profile_of(graph, tmp_path)
    assert profile["reciprocity"] == 0.0
    assert "two_mode" in signals(profile) and "mostly one-way" not in flags(profile)
