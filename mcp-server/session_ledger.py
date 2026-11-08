"""What the assistant applied to this graph, kept so the map can explain itself.

Two things need this record, and neither can be recovered from the graph afterwards.

A legend has to say what the colours mean. The meaning lives in the decision that produced them,
not in the resulting pixels, and Gephi keeps only the pixels. An assistant that made the decision
still knows which column it partitioned on and which palette it used, so a legend becomes a record
of choices already made rather than an inference from appearance.

A methods paragraph has to say which layout ran with which settings and which statistics produced
which columns. Gephi does not retain that either, so six months later a figure cannot be explained
or reproduced.

When the graph on screen changes (an import, a workspace switch, a time slice), the record so far
is kept as an earlier section, labelled with what ended it, and a new record starts. A record is
never re-attached to a graph: Gephi cannot say reliably which graph is which across workspaces and
restarts, and a methods note that credits one graph's settings to another is worse than none.

The ledger sees only what came through these tools. Styling applied by hand in the Gephi window is
invisible to it, and the receipt says so rather than letting silence read as completeness.
"""

from __future__ import annotations

import logging
from typing import Any

#: Operations that encode a variable in a visual channel, and so belong in a legend.
#: One mapping per channel: restyling replaces, because a legend describes what the map shows now.
_LEGEND_CHANNELS: dict[str, str] = {
    "color_by_partition": "node colour",
    "color_by_ranking": "node colour",
    "size_by_ranking": "node size",
    "color_edges_by_partition": "edge colour",
    "edge_thickness_by_weight": "edge width",
}

#: Analyses whose results a methods note reports, each run kept (two comparisons are two findings).
_ANALYSES = ("compare_partitions", "community_stability")

#: Earlier sections kept, so a long session does not grow without bound.
EARLIER_KEPT = 20

_log = logging.getLogger("gephi_mcp.ledger")

SCOPE_NOTE = (
    "This record covers the operations applied through gephi-ai. Anything styled by hand in the "
    "Gephi window is not visible to it and is not described here."
)


class Ledger:
    """An ordered record of the operations applied to the current graph."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []
        #: Records of graphs no longer on screen, oldest first, each with what ended it.
        self.earlier: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Forget everything. The ledger describes one graph; a different graph is a new record."""
        self.entries = []

    def start_new_graph(self, ended_by: str) -> None:
        """The graph on screen changed: keep the record so far as an earlier section, then start
        a new one. Never raises: this sits on the path of every graph-replacing call."""
        try:
            if self.entries:
                self.earlier.append({"ended_by": ended_by, **self._summary(self.entries)})
                self.earlier = self.earlier[-EARLIER_KEPT:]
        except Exception:
            _log.warning("could not keep the record of the previous graph", exc_info=True)
        self.reset()

    def record(self, operation: str, **detail: Any) -> None:
        """Note an operation. Never raises: this sits on the path of ordinary styling calls."""
        try:
            if operation in _LEGEND_CHANNELS and not detail.get("column"):
                return  # A mapping with no column names nothing and would explain nothing.
            if (operation in _LEGEND_CHANNELS or operation in _ANALYSES
                    or operation in ("run_layout", "statistic")):
                self.entries.append({"operation": operation, **detail})
        except Exception:
            _log.warning("could not record %s in the session receipt", operation, exc_info=True)

    def mark_layout_stopped(self) -> None:
        """The last layout was stopped before it finished, so the iteration count recorded for it
        is what was asked for, not what ran."""
        for entry in reversed(self.entries):
            if entry["operation"] == "run_layout":
                if "iterations" in entry:
                    entry["iterations_requested"] = entry.pop("iterations")
                entry["stopped_before_finishing"] = True
                return

    def forget_channel(self, channel: str) -> None:
        """A reset undid the mapping on this channel, so the legend must stop describing it."""
        self.entries = [e for e in self.entries if _LEGEND_CHANNELS.get(e["operation"]) != channel]

    def colour_partition(self) -> str | None:
        """The column node colours were last set from, if that was a partition (categories)."""
        for entry in reversed(self.entries):
            if entry["operation"] in ("color_by_partition", "color_by_ranking"):
                return entry.get("column") if entry["operation"] == "color_by_partition" else None
        return None

    def legend_items(self, entries: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        """The visual mappings currently in force, one per channel, in the order first set."""
        by_channel: dict[str, dict[str, Any]] = {}
        for entry in self.entries if entries is None else entries:
            channel = _LEGEND_CHANNELS.get(entry["operation"])
            if not channel:
                continue
            item: dict[str, Any] = {"channel": channel, "column": entry.get("column")}
            if entry.get("groups"):
                item["groups"] = entry["groups"]
            if entry.get("palette"):
                item["palette"] = entry["palette"]
            if entry.get("min_size") is not None or entry.get("max_size") is not None:
                item["range"] = [entry.get("min_size"), entry.get("max_size")]
            if entry.get("cap") is not None:
                item["cap"] = entry["cap"]
            by_channel[channel] = item
        return list(by_channel.values())

    def receipt(self) -> dict[str, Any]:
        """Everything needed to say how a figure was made, in the shape of a methods note.

        `earlier` holds the records of graphs that were on screen before, so work done on them
        in this session is not lost; they do not describe the graph on screen now.
        """
        return {**self._summary(self.entries), "earlier": list(self.earlier), "scope": SCOPE_NOTE}

    def _summary(self, entries: list[dict[str, Any]]) -> dict[str, Any]:
        statistics: dict[str, dict[str, Any]] = {}
        layout: dict[str, Any] | None = None
        for entry in entries:
            if entry["operation"] == "statistic":
                # The columns on the graph hold the last run, so that is the run to report.
                statistics[entry["metric"]] = {"metric": entry["metric"],
                                               "params": entry.get("params", {})}
            elif entry["operation"] == "run_layout":
                layout = {k: v for k, v in entry.items() if k != "operation"}
        return {
            "legend": self.legend_items(entries),
            "statistics": list(statistics.values()),
            "layout": layout,
            "analyses": [e for e in entries if e["operation"] in _ANALYSES],
        }
