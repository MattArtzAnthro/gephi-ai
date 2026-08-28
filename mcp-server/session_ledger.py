"""What the assistant applied to this graph, kept so the map can explain itself.

Two things need this record, and neither can be recovered from the graph afterwards.

A legend has to say what the colours mean. The meaning lives in the decision that produced them,
not in the resulting pixels, and Gephi keeps only the pixels. An assistant that made the decision
still knows which column it partitioned on and which palette it used, so a legend becomes a record
of choices already made rather than an inference from appearance.

A methods paragraph has to say which layout ran with which settings and which statistics produced
which columns. Gephi does not retain that either, so six months later a figure cannot be explained
or reproduced.

The ledger sees only what came through these tools. Styling applied by hand in the Gephi window is
invisible to it, and the receipt says so rather than letting silence read as completeness.
"""

from __future__ import annotations

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

SCOPE_NOTE = (
    "This record covers the operations applied through gephi-ai. Anything styled by hand in the "
    "Gephi window is not visible to it and is not described here."
)


class Ledger:
    """An ordered record of the operations applied to the current graph."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def reset(self) -> None:
        """Forget everything. The ledger describes one graph; a different graph is a new record."""
        self.entries = []

    def record(self, operation: str, **detail: Any) -> None:
        """Note an operation. Never raises: this sits on the path of ordinary styling calls."""
        try:
            if operation in _LEGEND_CHANNELS and not detail.get("column"):
                return  # A mapping with no column names nothing and would explain nothing.
            if operation in _LEGEND_CHANNELS or operation in ("run_layout", "statistic"):
                self.entries.append({"operation": operation, **detail})
        except Exception:
            pass

    def legend_items(self) -> list[dict[str, Any]]:
        """The visual mappings currently in force, one per channel, in the order first set."""
        by_channel: dict[str, dict[str, Any]] = {}
        for entry in self.entries:
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
            by_channel[channel] = item
        return list(by_channel.values())

    def receipt(self) -> dict[str, Any]:
        """Everything needed to say how a figure was made, in the shape of a methods note."""
        statistics: dict[str, dict[str, Any]] = {}
        layout: dict[str, Any] | None = None
        for entry in self.entries:
            if entry["operation"] == "statistic":
                # The columns on the graph hold the last run, so that is the run to report.
                statistics[entry["metric"]] = {"metric": entry["metric"],
                                               "params": entry.get("params", {})}
            elif entry["operation"] == "run_layout":
                layout = {k: v for k, v in entry.items() if k != "operation"}
        return {
            "legend": self.legend_items(),
            "statistics": list(statistics.values()),
            "layout": layout,
            "scope": SCOPE_NOTE,
        }
