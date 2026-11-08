"""Pins on stats_integrity behaviour that mutation testing showed nothing else checked."""

import json

import pytest

import stats_integrity as si
from stats_integrity import GraphFacts


def _entry(id_="e1", says="It is wrong.", status="unverified", metrics=("pagerank",), applies=None):
    return {"id": id_, "metrics": list(metrics), "says": says,
            "applies_when": applies if applies is not None else {"always": True},
            "verification": {"status": status, "note": "kept"}}


def _overlay(monkeypatch, tmp_path, content):
    path = tmp_path / "caveats.local.json"
    path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
    monkeypatch.setattr(si, "local_overlay_path", lambda: path)


# ── _apply_overlay ──

def test_overlay_verdict_merges_into_verification_and_keeps_other_fields(monkeypatch, tmp_path):
    """A verdict replaces the fields it names in `verification` and leaves the rest of the entry."""
    _overlay(monkeypatch, tmp_path, {"e1": {"status": "not_reproduced"}})
    [out] = si._apply_overlay([_entry()])
    assert out["verification"] == {"status": "not_reproduced", "note": "kept"}
    assert out["id"] == "e1" and out["metrics"] == ["pagerank"]
    assert out["says"] == "It is wrong."


def test_overlay_reproduced_with_date_rewrites_says(monkeypatch, tmp_path):
    """A reproduced verdict with a date drops the unverified suffix and states the date."""
    _overlay(monkeypatch, tmp_path,
             {"e1": {"status": "reproduced", "checked_on": "2026-01-02"}})
    [out] = si._apply_overlay([_entry(says="It is wrong." + si.UNVERIFIED_SUFFIX)])
    assert out["says"] == "It is wrong. Reproduced on this Gephi on 2026-01-02."
    assert out["verification"]["status"] == "reproduced"


def test_overlay_reproduced_without_date_leaves_says(monkeypatch, tmp_path):
    """Reproduced but undated is not enough to claim a date, so the text is untouched."""
    _overlay(monkeypatch, tmp_path, {"e1": {"status": "reproduced"}})
    text = "It is wrong." + si.UNVERIFIED_SUFFIX
    [out] = si._apply_overlay([_entry(says=text)])
    assert out["says"] == text


def test_overlay_dated_but_not_reproduced_leaves_says(monkeypatch, tmp_path):
    """A date alone, without a reproduced status, does not rewrite the text."""
    _overlay(monkeypatch, tmp_path, {"e1": {"status": "not_reproduced", "checked_on": "2026-01-02"}})
    [out] = si._apply_overlay([_entry(says="Plain.")])
    assert out["says"] == "Plain."


def test_overlay_says_rewrite_strips_trailing_space_only_on_the_right(monkeypatch, tmp_path):
    """The text before the suffix is right-stripped; leading whitespace is kept."""
    _overlay(monkeypatch, tmp_path, {"e1": {"status": "reproduced", "checked_on": "D"}})
    [out] = si._apply_overlay([_entry(says="  Lead.   " + si.UNVERIFIED_SUFFIX)])
    assert out["says"] == "  Lead. Reproduced on this Gephi on D."


def test_overlay_does_not_mutate_the_shipped_entries(monkeypatch, tmp_path):
    """Merging builds new entries; the register passed in is left as shipped."""
    _overlay(monkeypatch, tmp_path, {"e1": {"status": "reproduced", "checked_on": "D"}})
    original = _entry(says="A." + si.UNVERIFIED_SUFFIX)
    si._apply_overlay([original])
    assert original["says"] == "A." + si.UNVERIFIED_SUFFIX
    assert original["verification"]["status"] == "unverified"


def test_overlay_keeps_every_entry_in_order_including_unmentioned_ones(monkeypatch, tmp_path):
    """Entries without a verdict, and entries given a non-dict verdict, pass through in order."""
    _overlay(monkeypatch, tmp_path, {"b": {"status": "not_reproduced"}, "c": "garbage"})
    out = si._apply_overlay([_entry("a"), _entry("b"), _entry("c")])
    assert [e["id"] for e in out] == ["a", "b", "c"]
    assert [e["verification"]["status"] for e in out] == ["unverified", "not_reproduced", "unverified"]


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '"text"'])
def test_overlay_unreadable_or_not_an_object_is_ignored(monkeypatch, tmp_path, content):
    """A malformed or non-object overlay leaves the entries exactly as shipped."""
    _overlay(monkeypatch, tmp_path, content)
    entries = [_entry()]
    assert si._apply_overlay(entries) == entries


def test_overlay_missing_file_is_ignored(monkeypatch, tmp_path):
    """No overlay file means the shipped entries come back unchanged."""
    monkeypatch.setattr(si, "local_overlay_path", lambda: tmp_path / "nope.json")
    entries = [_entry()]
    assert si._apply_overlay(entries) == entries


# ── _param_not_default / _applies ──

def test_param_equal_to_default_numerically_is_not_a_departure():
    """A string that parses to the default value is the default, not a custom setting."""
    spec = {"name": "resolution", "default": 1.0}
    assert si._param_not_default(spec, {"resolution": "1.0"}) is False
    assert si._param_not_default(spec, {"resolution": 1}) is False
    assert si._param_not_default(spec, {"resolution": "2"}) is True
    assert si._param_not_default(spec, {}) is False


def test_all_of_passes_the_call_params_to_each_sub_predicate():
    """all_of evaluates parameter predicates against the real params, not an empty set."""
    predicate = {"all_of": [{"param_not_default": {"name": "r", "default": 1.0}},
                            {"undirected": True}]}
    assert si._applies(predicate, {"r": 2}, GraphFacts(directed=False)) is True
    assert si._applies(predicate, {"r": 1}, GraphFacts(directed=False)) is False
    assert si._applies(predicate, {"r": 2}, GraphFacts(directed=True)) is False


# ── replaces_graph ──

@pytest.mark.parametrize("method", ["GET", "get", "Get"])
def test_a_get_never_replaces_the_graph(method):
    """Reading an endpoint that would replace the graph, via GET, replaces nothing."""
    assert si.replaces_graph(method, "/workspace/switch") is False
    assert si.replaces_graph(method, "/graph/clear") is False


def test_a_missing_method_is_not_a_get_and_can_replace():
    """With no method named the call is treated as a write."""
    assert si.replaces_graph(None, "/graph/clear") is True
    assert si.replaces_graph("POST", "/graph/clear") is True
    assert si.replaces_graph("post", "/import/file") is True


# ── _uses_facts ──

def test_only_fact_predicates_count_as_using_facts():
    """Argument-only and unconditional predicates need no graph facts, even nested specs."""
    assert si._uses_facts({"always": True}) is False
    assert si._uses_facts({"param_not_default": {"name": "r", "default": 1.0}}) is False
    assert si._uses_facts({"all_of": [{"always": True}]}) is False
    assert si._uses_facts({"all_of": [{"always": True}, {"weights_vary": True}]}) is True
    assert si._uses_facts({}) is False


# ── needs_graph_facts / caveats_for tolerate sparse entries ──

def test_needs_graph_facts_skips_entries_without_metrics_or_verification():
    """A malformed entry is passed over; it does not hide a well-formed one after it."""
    register = [{"applies_when": {"undirected": True}},  # no metrics at all
                {"metrics": ["pagerank"], "applies_when": {"undirected": True}}]  # no verification
    assert si.needs_graph_facts("pagerank", register) is True


def test_needs_graph_facts_ignores_suppressed_entries():
    """An entry a probe could not reproduce does not make the call fetch graph facts."""
    register = [_entry(applies={"undirected": True}, status="not_reproduced")]
    assert si.needs_graph_facts("pagerank", register) is False


def test_caveats_for_returns_entries_that_lack_a_verification_block():
    """An entry with no verification block is not suppressed and is returned."""
    entry = {"id": "x", "metrics": ["pagerank"], "applies_when": {"always": True}}
    assert si.caveats_for("pagerank", register=[entry]) == [entry]


def test_caveats_for_passes_over_malformed_and_suppressed_entries():
    """A suppressed or metric-less entry before a good one does not stop the scan."""
    good = _entry("good")
    register = [_entry("hidden", status="not_reproduced"),
                {"id": "nometrics", "verification": {}, "applies_when": {"always": True}},
                _entry("other", metrics=("degree",)),
                _entry("quiet", applies={"undirected": True}),
                good]
    assert si.caveats_for("PageRank ", register=register) == [good]
