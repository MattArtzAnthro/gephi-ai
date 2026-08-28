"""Recording what a probe run established, and refusing to record what it did not.

A verdict must be earned. A probe that did not complete a measurement produces no verdict at all,
and the register goes on saying the entry is unverified, which is the truth.

The rule matters because the failure it prevents is silent and inverted. A probe that cannot reach
Gephi, or reaches it and gets nothing back, falls through to a falsy comparison and reports the
defect as absent. That silences a live warning on the strength of no evidence, which is a worse
outcome than having no register at all: it converts "the check did not run" into "there is nothing
there".
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

VALID_VERDICTS = frozenset({"reproduced", "not_reproduced"})

UNVERIFIED_SUFFIX = (
    " Not verified against your Gephi: run the probe suite to confirm it still holds."
)


class Verdicts:
    """What a probe run found, and what it failed to find out."""

    def __init__(self) -> None:
        self.results: dict[str, str] = {}
        self.failures: dict[str, str] = {}
        self.evidence: dict[str, str] = {}

    def record(self, probe: str, *, reproduced: bool, detail: str, measured: bool) -> None:
        """Record a verdict. `measured` must be True: a probe has to have actually measured.

        The flag is not ceremony. Without it, a probe whose Gephi call quietly failed falls
        through to a falsy comparison and reports the defect as absent.
        """
        if not measured:
            raise ValueError(
                f"{probe} did not complete a measurement, so it has no verdict to give. "
                "Call note_failure instead: not looking is not the same as finding nothing.")
        self.results[probe] = "reproduced" if reproduced else "not_reproduced"
        self.evidence[probe] = detail
        print(f"  {probe}: {self.results[probe]} — {detail}")

    def note_failure(self, probe: str, why: str) -> None:
        """The probe could not measure. No verdict is produced and the register stays as it was."""
        self.failures[probe] = why
        print(f"  {probe}: NO VERDICT — {why}")


def write_overlay(overlay_path: Path, verdicts: dict[str, str],
                  today: str | None = None,
                  evidence: dict[str, str] | None = None) -> list[str]:
    """Record this machine's verdicts beside the register, never inside it.

    A verdict describes one install. Written into the shipped register it becomes a claim about
    every install: a silenced caveat for users whose Gephi was never tested, and a defect reported
    as "reproduced on this Gephi" on machines nobody probed.
    """
    today = today or date.today().isoformat()
    for probe, verdict in verdicts.items():
        if verdict not in VALID_VERDICTS:
            raise ValueError(
                f"{verdict!r} is not a verdict for {probe}; expected one of "
                f"{sorted(VALID_VERDICTS)}")
    try:
        existing = json.loads(overlay_path.read_text(encoding="utf-8"))
    except Exception:
        existing = {}
    changes = []
    for caveat_id, verdict in verdicts.items():
        was = existing.get(caveat_id, {}).get("status")
        existing[caveat_id] = {"status": verdict, "checked_on": today}
        if (evidence or {}).get(caveat_id):
            existing[caveat_id]["evidence"] = evidence[caveat_id]
        if was != verdict:
            changes.append(f"  {caveat_id}: {was or 'unverified'} -> {verdict}")
    overlay_path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return changes


def apply_verdicts(register_path: Path, verdicts: dict[str, str],
                   today: str | None = None,
                   evidence: dict[str, str] | None = None) -> list[str]:
    """Write verdicts into the register. Returns the human-readable list of changes.

    Only entries naming a probe that reported are touched. A "not_probeable" entry is never
    altered: no run can decide it, so no run may claim to have.
    """
    today = today or date.today().isoformat()

    for probe, verdict in verdicts.items():
        if verdict not in VALID_VERDICTS:
            raise ValueError(
                f"{verdict!r} is not a verdict for {probe}; expected one of {sorted(VALID_VERDICTS)}")

    data = json.loads(register_path.read_text(encoding="utf-8"))
    known = {e["verification"].get("probe") for e in data["caveats"]}
    for probe in verdicts:
        if probe not in known:
            raise ValueError(
                f"{probe} reported a verdict but no register entry names it; the probe suite and "
                "the register have drifted apart")

    changes: list[str] = []
    for entry in data["caveats"]:
        verification = entry["verification"]
        probe = verification.get("probe")
        if not probe or probe not in verdicts:
            continue
        was, now = verification.get("status"), verdicts[probe]
        verification["status"] = now
        verification["checked_on"] = today
        if (evidence or {}).get(probe):
            verification["evidence"] = evidence[probe]
        if now == "reproduced":
            entry["says"] = (entry["says"].replace(UNVERIFIED_SUFFIX, "").rstrip()
                             + f" Reproduced on this Gephi on {today}.")
        if was != now:
            changes.append(f"  {entry['id']}: {was} -> {now}")

    if changes or any(e["verification"].get("probe") in verdicts for e in data["caveats"]):
        register_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changes
