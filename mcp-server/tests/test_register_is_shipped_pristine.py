"""The shipped register must carry no verdicts, and verdicts must not travel in the package.

A probe verdict is a statement about one install. Baking one into the distributed package asserts
it about every install: a caveat marked not_reproduced is silenced for users whose Gephi was never
tested, and a caveat whose text reads "Reproduced on this Gephi" is false for everyone but the
machine that ran the probe.

So the register ships pristine and a probe run writes a local overlay beside it, which
load_register merges when present.
"""

import json

from stats_integrity import REGISTER_PATH, load_register, local_overlay_path


def test_the_shipped_register_records_no_verdicts():
    """This is the tripwire. A verdict here would be published as a claim about every install."""
    shipped = json.loads(REGISTER_PATH.read_text())

    stamped = [e["id"] for e in shipped["caveats"]
               if e["verification"].get("checked_on")
               or e["verification"]["status"] in {"reproduced", "not_reproduced"}]

    assert not stamped, (
        f"{stamped} carry a probe verdict in the shipped register. Verdicts belong in the local "
        f"overlay ({local_overlay_path().name}), never in the package.")


def test_the_shipped_register_never_claims_a_defect_was_reproduced_here():
    shipped = REGISTER_PATH.read_text().lower()

    assert "reproduced on this gephi" not in shipped


def test_an_overlay_supplies_the_verdict_for_the_install_it_was_run_on(tmp_path, monkeypatch):
    overlay = tmp_path / "caveats.local.json"
    overlay.write_text(json.dumps({"gephi-2034": {
        "status": "reproduced", "checked_on": "2026-01-01", "evidence": "8 -> 4"}}))
    monkeypatch.setattr("stats_integrity.local_overlay_path", lambda: overlay)
    monkeypatch.setattr("stats_integrity._register_cache", None)

    entry = next(e for e in load_register() if e["id"] == "gephi-2034")

    assert entry["verification"]["status"] == "reproduced"
    assert entry["verification"]["evidence"] == "8 -> 4"


def test_an_overlay_can_silence_a_caveat_the_probe_did_not_reproduce(tmp_path, monkeypatch):
    from stats_integrity import GraphFacts, caveats_for

    overlay = tmp_path / "caveats.local.json"
    overlay.write_text(json.dumps({"gephi-2034": {"status": "not_reproduced"}}))
    monkeypatch.setattr("stats_integrity.local_overlay_path", lambda: overlay)
    monkeypatch.setattr("stats_integrity._register_cache", None)

    found = caveats_for("modularity", params={"resolution": 2.0}, facts=GraphFacts())

    assert "gephi-2034" not in {c["id"] for c in found}


def test_no_overlay_means_the_register_reads_exactly_as_shipped(tmp_path, monkeypatch):
    monkeypatch.setattr("stats_integrity.local_overlay_path", lambda: tmp_path / "absent.json")
    monkeypatch.setattr("stats_integrity._register_cache", None)

    assert all(e["verification"]["status"] in {"unverified", "not_probeable"}
               for e in load_register())


def test_a_corrupt_overlay_is_ignored_rather_than_breaking_every_statistic(tmp_path, monkeypatch):
    overlay = tmp_path / "caveats.local.json"
    overlay.write_text("{ this is not json")
    monkeypatch.setattr("stats_integrity.local_overlay_path", lambda: overlay)
    monkeypatch.setattr("stats_integrity._register_cache", None)

    assert len(load_register()) > 0
