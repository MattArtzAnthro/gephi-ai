"""Known defects in Gephi's own statistics, attached to the numbers they affect.

Gephi's tracker carries long-open defects that the interface never surfaces: a resolution
parameter applied as the reciprocal of the convention it cites, a closeness measure normalised
whatever the checkbox said, centrality measures that ignore edge weights. A user reads the number
off the screen and has no way to know. gephi-ai reports those numbers into research claims, so a
tool that repeats Gephi's errors with more fluency is worse than no tool at all.

Two rules govern this module.

An entry is only asserted as live once a probe has reproduced it against a running Gephi. Until
then its status is "unverified" and its own text says so, because asserting an untested defect is
the same class of error the register exists to prevent. An entry a probe could not reproduce is
never returned at all.

A caveat that fires when it does not apply is noise, and noise gets skipped. So the register is
conditioned on what is actually true of the graph and the call: the PageRank caveat fires only on
undirected graphs, the edge-weight caveats only when weights actually vary, and the resolution
caveat only when a non-default resolution was passed, because at the default the reciprocal is the
same number.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REGISTER_PATH = Path(__file__).with_name("caveats.json")

#: Probe verdicts live beside the register, never inside it. A verdict is a statement about one
#: install: baked into the distributed package it would be published as a claim about every
#: install, silencing caveats for users whose Gephi was never tested and telling them a defect was
#: "reproduced on this Gephi" when theirs was never touched. The register therefore ships pristine
#: and a probe run writes here.
OVERLAY_NAME = "caveats.local.json"


def local_overlay_path() -> Path:
    """Where this machine's probe verdicts are recorded. Not part of the package."""
    return REGISTER_PATH.with_name(OVERLAY_NAME)

#: Statuses a register entry's verification block may carry.
#:
#: "not_probeable" is not a lesser "unverified". It means the defect cannot be reproduced through
#: the API we have at all, so no probe run will ever change it: gephi#1784 would need a second
#: implementation to compare against, and gephi#1872 needs a normalisation toggle the statistics
#: endpoint does not expose. Such an entry still fires, because the issue is filed and open, but
#: it says plainly that it cannot be confirmed here rather than implying a probe is pending.
VERIFIED_STATUSES = frozenset({"unverified", "reproduced", "not_reproduced", "not_probeable"})

#: A status that means a probe ran and the defect did not appear. Never surfaced.
_SUPPRESSED = "not_reproduced"

_register_cache: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class GraphFacts:
    """What is cheaply knowable about the graph a statistic just ran on.

    `None` means "not established", which is deliberately distinct from False. An unknown fact
    never satisfies a predicate: silence beats a warning we cannot stand behind.
    """

    directed: bool | None = None
    weights_vary: bool | None = None


def load_register(path: Path | None = None) -> list[dict[str, Any]]:
    """Return the caveat entries. Cached, since the file does not change within a process."""
    global _register_cache
    if path is not None:
        return json.loads(path.read_text(encoding="utf-8"))["caveats"]
    if _register_cache is None:
        entries = json.loads(REGISTER_PATH.read_text(encoding="utf-8"))["caveats"]
        _register_cache = _apply_overlay(entries)
    return _register_cache


def _apply_overlay(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge this machine's probe verdicts over the shipped register.

    A malformed or unreadable overlay is ignored rather than raised: it sits on the path of every
    statistic, and a bad local file must not be able to break measurement.
    """
    try:
        overlay = json.loads(local_overlay_path().read_text(encoding="utf-8"))
    except Exception:
        return entries
    if not isinstance(overlay, dict):
        return entries
    merged = []
    for entry in entries:
        verdict = overlay.get(entry["id"])
        if isinstance(verdict, dict):
            entry = {**entry, "verification": {**entry["verification"], **verdict}}
            if verdict.get("status") == "reproduced" and verdict.get("checked_on"):
                entry["says"] = (entry["says"].replace(UNVERIFIED_SUFFIX, "").rstrip()
                                 + f" Reproduced on this Gephi on {verdict['checked_on']}.")
        merged.append(entry)
    return merged


UNVERIFIED_SUFFIX = (
    " Not verified against your Gephi: run the probe suite to confirm it still holds."
)


def _param_not_default(spec: dict[str, Any], params: dict[str, Any]) -> bool:
    """True when the caller actually passed a value other than Gephi's default.

    An omitted parameter means the default applies, which for the resolution caveat is the
    harmless case: the reciprocal of 1.0 is 1.0.
    """
    given = params.get(spec["name"])
    if given is None:
        return False
    try:
        return float(given) != float(spec["default"])
    except (TypeError, ValueError):
        return given != spec["default"]


def _applies(predicate: dict[str, Any], params: dict[str, Any], facts: GraphFacts) -> bool:
    """Evaluate one `applies_when` block. An unrecognised predicate stays quiet."""
    if not predicate:
        return False
    for key, spec in predicate.items():
        if key == "always":
            ok = bool(spec)
        elif key == "undirected":
            ok = facts.directed is False
        elif key == "directed":
            ok = facts.directed is True
        elif key == "weights_vary":
            ok = facts.weights_vary is True
        elif key == "param_not_default":
            ok = _param_not_default(spec, params)
        elif key == "all_of":
            ok = all(_applies(sub, params, facts) for sub in spec)
        else:
            # An unknown predicate is a register we do not understand. Fail closed.
            ok = False
        if not ok:
            return False
    return True


#: Non-GET endpoints that compute or render without changing the graph the facts describe.
#: Statistics add columns, exports read, appearance and layout move pixels: none of them alter
#: the node set or the directedness, so cached facts survive them.
_NON_STRUCTURAL = (
    "/statistics/",
    "/export/",
    "/appearance/",
    "/layout/",
    "/preview/",
    "/datalab/frequencies",
    "/datalab/duplicates",
    "/selection",
    "/health",
)


def mutates_graph(method: str, endpoint: str) -> bool:
    """Whether this call could change which graph we are looking at, or its shape.

    Fails safe: an endpoint added later that this list has never seen is assumed to mutate. A
    stale caveat is a wrong answer given confidently; an unnecessary cheap GET is not.
    """
    if str(method or "").upper() == "GET":
        return False
    path = str(endpoint or "")
    return not any(path.startswith(prefix) for prefix in _NON_STRUCTURAL)


#: Endpoints that replace the graph rather than editing it. A styling record survives an ordinary
#: edit — adding a node leaves a colour mapping meaningful — but not a change of graph.
_REPLACES_GRAPH = (
    "/graph/clear",
    "/workspace/",
    "/project/",
    "/import/",
)


def replaces_graph(method: str, endpoint: str) -> bool:
    """Whether this call swaps in a different graph, making a styling record obsolete."""
    if str(method or "").upper() == "GET":
        return False
    path = str(endpoint or "")
    return any(path.startswith(prefix) for prefix in _REPLACES_GRAPH)


#: Predicates whose truth depends on the graph rather than on the call's arguments.
_FACT_PREDICATES = frozenset({"undirected", "directed", "weights_vary"})


def _uses_facts(predicate: dict[str, Any]) -> bool:
    for key, spec in (predicate or {}).items():
        if key in _FACT_PREDICATES:
            return True
        if key == "all_of" and any(_uses_facts(sub) for sub in spec):
            return True
    return False


def needs_graph_facts(metric: str, register: list[dict[str, Any]] | None = None) -> bool:
    """Whether answering for this metric requires knowing anything about the graph.

    Most metrics do not: their caveats are unconditional, or turn only on an argument the caller
    already passed. Checking first means the integrity layer adds no round trip to a call that
    could not have needed one.
    """
    try:
        entries = load_register() if register is None else register
        wanted = str(metric or "").strip().lower()
        return any(
            _uses_facts(e.get("applies_when", {}))
            for e in entries
            if wanted in {m.lower() for m in e.get("metrics", ())}
            and e.get("verification", {}).get("status") != _SUPPRESSED
        )
    except Exception:
        return False


def caveats_for(
    metric: str,
    params: dict[str, Any] | None = None,
    facts: GraphFacts | None = None,
    register: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Known defects that apply to this metric, on this graph, for this call.

    Never raises. This layer sits on the path of every statistic gephi-ai runs, and a bug in it
    must not be able to fail a measurement that would otherwise have succeeded.
    """
    try:
        params = params or {}
        facts = facts or GraphFacts()
        entries = load_register() if register is None else register
        wanted = str(metric or "").strip().lower()
        found = []
        for entry in entries:
            if entry.get("verification", {}).get("status") == _SUPPRESSED:
                continue
            if wanted not in {m.lower() for m in entry.get("metrics", ())}:
                continue
            if not _applies(entry.get("applies_when", {}), params, facts):
                continue
            found.append(entry)
        return found
    except Exception:
        return []
