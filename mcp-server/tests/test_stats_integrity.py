"""Tests for the statistics integrity layer: the caveat register and its conditioning.

The register's job is to attach a known Gephi defect to the number it affects, and — just as
important — to stay quiet when the defect does not apply. A register that fires on every call
becomes noise the reader learns to skip, which is the failure this feature exists to prevent.
"""

import json
import pathlib

import pytest

import stats_integrity
from stats_integrity import (
    VERIFIED_STATUSES,
    GraphFacts,
    caveats_for,
    load_register,
    needs_graph_facts,
)

UNKNOWN = GraphFacts(directed=None, weights_vary=None)
UNDIRECTED_UNWEIGHTED = GraphFacts(directed=False, weights_vary=False)
DIRECTED_WEIGHTED = GraphFacts(directed=True, weights_vary=True)


def ids(caveats):
    return {c["id"] for c in caveats}


# ── The resolution reciprocal: conditional on the parameter actually being passed ──

def test_modularity_at_non_default_resolution_warns_about_the_reciprocal():
    """gephi#2034: the resolution parameter is the reciprocal of the literature convention."""
    found = caveats_for("modularity", params={"resolution": 1.5}, facts=UNKNOWN)

    assert "gephi-2034" in ids(found)


def test_modularity_at_default_resolution_says_nothing_about_the_reciprocal():
    """At resolution 1.0 the reciprocal is 1.0, so there is nothing to warn about."""
    found = caveats_for("modularity", params={"resolution": 1.0}, facts=UNKNOWN)

    assert "gephi-2034" not in ids(found)


def test_modularity_with_no_resolution_given_says_nothing_about_the_reciprocal():
    """An omitted parameter means the Gephi default, which is the harmless case."""
    found = caveats_for("modularity", params={}, facts=UNKNOWN)

    assert "gephi-2034" not in ids(found)


# ── Directedness conditioning ──

def test_pagerank_on_an_undirected_graph_warns():
    """gephi#2191: PageRank is reported wrong for undirected graphs."""
    found = caveats_for("pagerank", params={}, facts=UNDIRECTED_UNWEIGHTED)

    assert "gephi-2191" in ids(found)


def test_pagerank_on_a_directed_graph_stays_quiet():
    found = caveats_for("pagerank", params={}, facts=DIRECTED_WEIGHTED)

    assert "gephi-2191" not in ids(found)


def test_pagerank_stays_quiet_when_directedness_is_unknown():
    """An unknown fact must not be treated as a confirmed one. Silence beats a false warning."""
    found = caveats_for("pagerank", params={}, facts=UNKNOWN)

    assert "gephi-2191" not in ids(found)


# ── Edge-weight conditioning ──

def test_betweenness_on_a_weighted_graph_warns_that_weights_are_ignored():
    """gephi#557 / gephi#1817: edge weight is not used by the centrality measures."""
    found = caveats_for("betweenness", params={}, facts=DIRECTED_WEIGHTED)

    assert "gephi-557" in ids(found)


def test_betweenness_on_an_unweighted_graph_stays_quiet_about_weights():
    """If every edge weighs the same, ignoring weight changes nothing."""
    found = caveats_for("betweenness", params={}, facts=UNDIRECTED_UNWEIGHTED)

    assert "gephi-557" not in ids(found)


# ── Unconditional caveats ──

def test_closeness_always_warns_that_it_is_normalised():
    """gephi#1872: closeness is normalised whatever the checkbox said."""
    found = caveats_for("closeness", params={}, facts=UNKNOWN)

    assert "gephi-1872" in ids(found)


def test_an_instability_caveat_points_at_the_tool_that_quantifies_it():
    """An "unstable" caveat is useless as a warning alone; it has to say what to do about it.

    Written against an explicit register rather than the shipped one, because the shipped one
    changes with whatever the probes last found on this machine, and a test that moves with it
    is testing the environment rather than the code.
    """
    register = [{
        "id": "unstable-thing", "metrics": ["modularity"], "issues": ["x"],
        "severity": "unstable", "applies_when": {"always": True},
        "says": "One draw, not the answer. Call gephi_community_stability to find out.",
        "verification": {"status": "reproduced"},
    }]

    found = caveats_for("modularity", params={}, facts=UNKNOWN, register=register)

    assert [c["severity"] for c in found] == ["unstable"]
    assert "gephi_community_stability" in found[0]["says"]


# ── A metric nobody has filed a defect against ──

def test_a_metric_with_no_known_defects_returns_nothing():
    found = caveats_for("degree", params={}, facts=DIRECTED_WEIGHTED)

    assert found == []


def test_an_unrecognised_metric_returns_nothing_rather_than_raising():
    """The integrity layer must never be able to fail a statistic that would otherwise succeed."""
    found = caveats_for("some_plugin_metric_we_have_never_seen", params={}, facts=UNKNOWN)

    assert found == []


# ── The register itself ──

def test_every_register_entry_has_the_fields_the_conditioner_needs():
    for entry in load_register():
        assert entry["id"], "every entry needs an id"
        assert entry["metrics"], f"{entry['id']} names no metrics"
        assert entry["severity"] in {"reporting", "wrong", "unstable"}, entry["id"]
        assert entry["says"].strip(), f"{entry['id']} says nothing"
        assert entry["issues"], f"{entry['id']} cites no issue"


def test_no_register_entry_is_asserted_before_a_probe_has_reproduced_it():
    """The governing decision of this design: the register is empirical, not bibliographic.

    An entry may only claim the defect is live once a probe has reproduced it against a running
    Gephi. Until then it must say so, because asserting an untested defect is the same class of
    error the register exists to prevent.
    """
    for entry in load_register():
        status = entry["verification"]["status"]
        assert status in VERIFIED_STATUSES, entry["id"]
        if status == "unverified":
            assert "not verified" in entry["says"].lower(), (
                f"{entry['id']} is unverified, so its text must say so")


def test_entries_a_probe_could_not_reproduce_are_never_returned():
    """If a probe run says the defect is gone, the caveat must stop firing."""
    register = [{
        "id": "gone", "metrics": ["degree"], "issues": ["x"], "severity": "wrong",
        "says": "...", "applies_when": {"always": True},
        "verification": {"status": "not_reproduced"},
    }]

    found = caveats_for("degree", params={}, facts=UNKNOWN, register=register)

    assert found == []


@pytest.mark.parametrize("bad_facts", [None, GraphFacts(directed=None, weights_vary=None)])
def test_conditioning_returns_only_unconditional_caveats_when_facts_are_missing(bad_facts):
    """Unknown is not False. With nothing established, only the always-on entries may fire."""
    found = caveats_for("betweenness", params={}, facts=bad_facts)

    assert "gephi-557" not in ids(found), "a weight caveat needs weights to be known to vary"
    assert all(c["applies_when"].get("always") for c in found)


# ── Defects that cannot be probed through the API we have ──

def test_a_not_probeable_entry_still_fires_because_the_issue_is_real():
    """Some defects cannot be reproduced through the tools we have: gephi#1784 would need NodeXL.

    Silence would be the wrong answer. The defect is filed and open; we simply cannot confirm it
    here, and the entry must say exactly that rather than either asserting or hiding it.
    """
    register = [{
        "id": "untestable", "metrics": ["betweenness"], "issues": ["x"], "severity": "reporting",
        "says": "...", "applies_when": {"always": True},
        "verification": {"status": "not_probeable", "why": "needs a second implementation"},
    }]

    found = caveats_for("betweenness", params={}, facts=UNKNOWN, register=register)

    assert [c["id"] for c in found] == ["untestable"]


def test_not_probeable_is_an_accepted_status():
    assert "not_probeable" in VERIFIED_STATUSES


def test_every_entry_declares_how_it_can_be_checked():
    """An entry must either name the probe that tests it, or say why it cannot be tested."""
    for entry in load_register():
        v = entry["verification"]
        assert v.get("probe") or v.get("why"), (
            f"{entry['id']} names neither a probe nor a reason it cannot be probed")


def test_every_probe_named_in_the_register_actually_exists():
    """A register that names a probe nobody wrote is a promise of verification that never comes."""
    probes = (pathlib.Path(__file__).parent / "probes" / "test_probes.py").read_text()

    for entry in load_register():
        probe = entry["verification"].get("probe")
        if probe:
            assert f"def test_{probe}" in probes or f"def {probe}" in probes, (
                f"{entry['id']} names probe {probe!r}, which is not defined in the probe suite")


# ── The guards: the layer stays quiet rather than wrong, and never breaks a measurement ──

def _entry(applies_when, metrics=("degree",), status="unverified"):
    return {"id": "x", "metrics": list(metrics), "says": "...", "applies_when": applies_when,
            "verification": {"status": status, "why": "test"}}


@pytest.mark.parametrize("applies_when, facts, fires", [
    ({}, UNKNOWN, False),
    ({"undirected": True}, UNDIRECTED_UNWEIGHTED, True),
    ({"undirected": True}, UNKNOWN, False),
    ({"directed": True}, DIRECTED_WEIGHTED, True),
    ({"directed": True}, UNDIRECTED_UNWEIGHTED, False),
    ({"weights_vary": True}, DIRECTED_WEIGHTED, True),
    ({"weights_vary": True}, UNKNOWN, False),
    ({"all_of": [{"directed": True}, {"weights_vary": True}]}, DIRECTED_WEIGHTED, True),
    ({"all_of": [{"directed": True}, {"weights_vary": True}]}, UNKNOWN, False),
    ({"some_new_predicate": True}, DIRECTED_WEIGHTED, False),
])
def test_each_predicate_fires_only_on_an_established_fact(applies_when, facts, fires):
    found = caveats_for("degree", facts=facts, register=[_entry(applies_when)])

    assert bool(found) is fires


def test_a_parameter_given_as_text_is_compared_as_given():
    entry = _entry({"param_not_default": {"name": "mode", "default": "fast"}})

    assert caveats_for("degree", params={"mode": "exact"}, register=[entry])
    assert not caveats_for("degree", params={"mode": "fast"}, register=[entry])


def test_needing_graph_facts_follows_the_predicates_of_live_entries():
    nested = _entry({"all_of": [{"always": True}, {"weights_vary": True}]})
    argument_only = _entry({"param_not_default": {"name": "r", "default": 1.0}})
    silenced = _entry({"directed": True}, status="not_reproduced")

    assert needs_graph_facts("degree", register=[nested])
    assert not needs_graph_facts("degree", register=[argument_only])
    assert not needs_graph_facts("degree", register=[silenced])
    assert not needs_graph_facts("pagerank", register=[nested])


def test_a_malformed_register_never_breaks_a_measurement():
    broken = [{"id": "x", "metrics": None, "applies_when": {"always": True}, "verification": {}}]

    assert caveats_for("degree", register=broken) == []
    assert needs_graph_facts("degree", register=broken) is False


def test_an_explicit_register_path_is_read_without_the_overlay(tmp_path):
    register = tmp_path / "caveats.json"
    register.write_text(json.dumps({"caveats": [_entry({"always": True})]}))

    assert [e["id"] for e in load_register(register)] == ["x"]


def test_an_overlay_that_is_not_an_object_is_ignored(tmp_path, monkeypatch):
    overlay = tmp_path / "caveats.local.json"
    overlay.write_text("[]")
    monkeypatch.setattr(stats_integrity, "local_overlay_path", lambda: overlay)
    monkeypatch.setattr(stats_integrity, "_register_cache", None)

    assert load_register() == json.loads(stats_integrity.REGISTER_PATH.read_text())["caveats"]
