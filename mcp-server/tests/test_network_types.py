"""The profile's reading of every network type, offline.

`network_types.generated()` holds one network per kind the tools have to handle. Each is written
to GEXF the way an export is, read back with the parser the server uses, and profiled, so a type
that breaks the parser or the profile fails here on every run, without a Gephi. What a running
Gephi does with each type is `live_workflow_test.py`'s job.
"""

import networkx as nx
import pytest
from network_types import generated

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
