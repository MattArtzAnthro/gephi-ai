"""Best-effort bookkeeping never fails the call it rides on, but its failures are logged, not
dropped: a statistic that silently loses its caveats is the misreading caveats exist to prevent."""
import logging

import gephi_mcp
from session_ledger import Ledger


class BrokenList(list):
    """A record list that refuses entries, standing in for any unexpected failure inside record."""

    def append(self, item):
        raise RuntimeError("boom")


def test_a_failing_record_is_logged_and_does_not_raise(caplog):
    ledger = Ledger()
    ledger.entries = BrokenList()
    caplog.set_level(logging.WARNING)

    ledger.record("run_layout", algorithm="ForceAtlas 2")

    assert "boom" in caplog.text


def test_a_failing_new_graph_section_is_logged_and_still_resets(caplog, monkeypatch):
    ledger = Ledger()
    ledger.record("run_layout", algorithm="ForceAtlas 2")
    monkeypatch.setattr(ledger, "_summary", lambda entries: (_ for _ in ()).throw(RuntimeError("boom")))
    caplog.set_level(logging.WARNING)

    ledger.start_new_graph("a file was imported")

    assert "boom" in caplog.text
    assert ledger.entries == []


async def test_a_failing_caveat_lookup_is_logged_and_the_result_still_returns(caplog, monkeypatch):
    async def ok(*args, **kwargs):
        return {"success": True}

    def fails(*args, **kwargs):
        raise RuntimeError("caveats boom")

    monkeypatch.setattr(gephi_mcp.gephi, "request", ok)
    monkeypatch.setattr(gephi_mcp, "caveats_for", fails)
    caplog.set_level(logging.WARNING)

    out = await gephi_mcp.gephi_compute_degree()

    assert '"success": true' in out
    assert "caveats boom" in caplog.text
