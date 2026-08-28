"""The rules that stop a probe run from recording more than it verified.

A verdict is something a probe has to earn. Absence of evidence never becomes evidence of absence,
and only a probe that positively measured something is allowed to speak.

Without that rule the failure is silent and inverted: a runner that cannot reach Gephi marks live
caveats "not_reproduced" and stamps them as checked, silencing real warnings on no evidence.
"""

import json

import pytest

from probe_verdicts import Verdicts


def test_a_verdict_requires_a_measurement():
    v = Verdicts()

    with pytest.raises(ValueError, match="measurement"):
        v.record("probe_x", reproduced=False, detail="...", measured=False)


def test_a_probe_that_measured_nothing_leaves_no_verdict():
    v = Verdicts()

    v.note_failure("probe_x", "Gephi was unreachable")

    assert v.results == {}
    assert "probe_x" in v.failures


def test_a_probe_that_measured_and_found_the_defect_says_reproduced():
    v = Verdicts()

    v.record("probe_x", reproduced=True, detail="saw it", measured=True)

    assert v.results == {"probe_x": "reproduced"}


def test_a_probe_that_measured_and_did_not_find_the_defect_says_not_reproduced():
    """This is the only route to silencing a caveat, and it requires a real measurement."""
    v = Verdicts()

    v.record("probe_x", reproduced=False, detail="gone", measured=True)

    assert v.results == {"probe_x": "not_reproduced"}


# ── Applying verdicts to the register ──

def register_fixture(tmp_path, status="unverified"):
    path = tmp_path / "caveats.json"
    path.write_text(json.dumps({"schema": 1, "caveats": [
        {"id": "c1", "metrics": ["m"], "issues": ["x"], "severity": "wrong",
         "says": "A defect. Not verified against your Gephi: run the probe suite to confirm it "
                 "still holds.",
         "applies_when": {"always": True},
         "verification": {"status": status, "probe": "probe_x"}},
        {"id": "c2", "metrics": ["m"], "issues": ["y"], "severity": "reporting",
         "says": "Cannot be checked from here.",
         "applies_when": {"always": True},
         "verification": {"status": "not_probeable", "why": "needs another tool"}},
    ]}, indent=2))
    return path


def test_applying_no_verdicts_changes_nothing(tmp_path):
    from probe_verdicts import apply_verdicts

    path = register_fixture(tmp_path)
    before = path.read_text()

    apply_verdicts(path, {}, today="2026-01-01")

    assert path.read_text() == before, "a run that verified nothing must not touch the register"


def test_a_reproduced_verdict_is_recorded_and_the_hedge_is_dropped(tmp_path):
    from probe_verdicts import apply_verdicts

    path = register_fixture(tmp_path)

    apply_verdicts(path, {"probe_x": "reproduced"}, today="2026-01-01")

    entry = json.loads(path.read_text())["caveats"][0]
    assert entry["verification"]["status"] == "reproduced"
    assert entry["verification"]["checked_on"] == "2026-01-01"
    assert "not verified" not in entry["says"].lower()
    assert "2026-01-01" in entry["says"]


def test_a_not_reproduced_verdict_silences_the_caveat(tmp_path):
    from probe_verdicts import apply_verdicts

    path = register_fixture(tmp_path)

    apply_verdicts(path, {"probe_x": "not_reproduced"}, today="2026-01-01")

    entry = json.loads(path.read_text())["caveats"][0]
    assert entry["verification"]["status"] == "not_reproduced"


def test_a_not_probeable_entry_is_never_touched_by_a_run(tmp_path):
    from probe_verdicts import apply_verdicts

    path = register_fixture(tmp_path)

    apply_verdicts(path, {"probe_x": "reproduced"}, today="2026-01-01")

    entry = json.loads(path.read_text())["caveats"][1]
    assert entry["verification"] == {"status": "not_probeable", "why": "needs another tool"}


def test_a_verdict_for_an_unknown_probe_is_refused(tmp_path):
    """A verdict that matches no entry means the register and the suite have drifted apart."""
    from probe_verdicts import apply_verdicts

    path = register_fixture(tmp_path)

    with pytest.raises(ValueError, match="probe_nobody_knows"):
        apply_verdicts(path, {"probe_nobody_knows": "reproduced"}, today="2026-01-01")


def test_an_invalid_verdict_value_is_refused(tmp_path):
    from probe_verdicts import apply_verdicts

    path = register_fixture(tmp_path)

    with pytest.raises(ValueError, match="probably"):
        apply_verdicts(path, {"probe_x": "probably"}, today="2026-01-01")


def test_the_register_records_what_the_probe_actually_measured(tmp_path):
    """A verdict without its evidence is unauditable, and 'not_reproduced' silences a warning.

    Anyone reading the register later must be able to see what was tested, because a probe can
    clear a caveat on partial evidence: the modularity entry merges three separate issues and the
    probe covers two of them.
    """
    from probe_verdicts import apply_verdicts

    path = register_fixture(tmp_path)

    apply_verdicts(path, {"probe_x": "not_reproduced"}, today="2026-01-01",
                   evidence={"probe_x": "10 runs identical; layout did not change it"})

    v = json.loads(path.read_text())["caveats"][0]["verification"]
    assert v["evidence"] == "10 runs identical; layout did not change it"
