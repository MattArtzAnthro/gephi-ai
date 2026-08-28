"""Tests for the statistics integrity layer: the caveat register and its conditioning.

The register's job is to attach a known Gephi defect to the number it affects, and — just as
important — to stay quiet when the defect does not apply. A register that fires on every call
becomes noise the reader learns to skip, which is the failure this feature exists to prevent.
"""

import pathlib

import pytest

from stats_integrity import (
    VERIFIED_STATUSES,
    GraphFacts,
    caveats_for,
    load_register,
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
def test_conditioning_never_raises_on_missing_facts(bad_facts):
    caveats_for("betweenness", params={}, facts=bad_facts)


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
