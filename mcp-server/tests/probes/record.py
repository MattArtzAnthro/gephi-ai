"""Run the probes against a live Gephi and write their verdicts into the caveat register.

The register ships with every probeable entry marked "unverified", because gephi-ai cannot see
which Gephi Desktop version it is talking to and an open issue is not proof of a live defect. This
script is what turns those entries into claims about the install in front of you.

    GEPHI_PROBE=1 PYTHONPATH=. uv run python tests/probes/record.py

Verdicts are written to caveats.local.json beside the register, never into it: a
verdict describes one install and must not travel in the package.

An entry a probe reproduces becomes "reproduced" and is asserted. An entry a probe positively
fails to reproduce becomes "not_reproduced" and stops being surfaced, which is how the suite tells
you the day Gephi fixes one. A probe that could not measure at all changes nothing: it produces no
verdict and the entry keeps saying it is unverified.

That last rule is the point of this script. It refuses to start without a healthy Gephi, and
`probe_verdicts` refuses to turn a probe that measured nothing into a verdict, because a run that
could not check must never be recorded as a run that found nothing wrong.

Nothing here edits the meaning of a caveat. It records what happened.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVER_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

REGISTER = SERVER_ROOT / "caveats.json"


def _known_probes():
    import json
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    return [e["verification"]["probe"] for e in data["caveats"]
            if e["verification"].get("probe")]


KNOWN_PROBES = _known_probes()


async def run_probes():
    import json

    import test_probes as probes

    import gephi_mcp
    from probe_verdicts import Verdicts
    health = json.loads(await gephi_mcp.gephi_health_check())
    if not health.get("success"):
        raise SystemExit(
            "Gephi is not reachable, so nothing can be verified. Start Gephi Desktop with the "
            "plugin installed and try again. The register is left untouched.")
    print(f"Gephi plugin {health.get('version')}, server {health.get('server_version')}\n")

    probes.VERDICTS = Verdicts()
    names = sorted(n for n in dir(probes) if n.startswith("test_probe_"))
    for name in names:
        print(f"{name}")
        try:
            await getattr(probes, name)()
        except Exception as exc:
            # An errored probe measured nothing. It must not become a verdict.
            # Map the test function back to the probe id the register names.
            probe_id = next((pid for pid in KNOWN_PROBES if pid in name), name)
            probes.VERDICTS.note_failure(probe_id, f"raised {type(exc).__name__}: {exc}")
    return probes.VERDICTS


if __name__ == "__main__":
    if not os.environ.get("GEPHI_PROBE"):
        raise SystemExit("Set GEPHI_PROBE=1 to confirm you want to drive a live Gephi.")

    import json as _json

    from probe_verdicts import write_overlay
    from stats_integrity import local_overlay_path

    verdicts = asyncio.run(run_probes())

    # The overlay is keyed by caveat id, not probe name, since that is what load_register merges.
    by_caveat, evidence = {}, {}
    register = _json.loads(REGISTER.read_text(encoding="utf-8"))["caveats"]
    for entry in register:
        probe = entry["verification"].get("probe")
        if probe and probe in verdicts.results:
            by_caveat[entry["id"]] = verdicts.results[probe]
            if probe in verdicts.evidence:
                evidence[entry["id"]] = verdicts.evidence[probe]
    changes = write_overlay(local_overlay_path(), by_caveat, evidence=evidence)

    print("\n" + "-" * 60)
    print(f"{len(verdicts.results)} verdict(s), {len(verdicts.failures)} probe(s) with no verdict")
    if verdicts.failures:
        print("\nno verdict (register left as it was):")
        for probe, why in verdicts.failures.items():
            print(f"  {probe}: {why}")
    print("\nregister changes:" if changes else "\nregister unchanged")
    print("\n".join(changes))
