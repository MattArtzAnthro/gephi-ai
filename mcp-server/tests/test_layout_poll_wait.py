"""A sync layout waits for Gephi to finish by polling /layout/status. The benchmark showed a fixed
one-second wait before every poll set the floor for small graphs (about 1 s of a 1.1 s layout of
1,000 nodes was waiting), so the wait starts short and grows, within the same overall limit."""
from __future__ import annotations

import json

import pytest

import gephi_mcp


class StatusFake:
    """Gephi at its HTTP boundary: the layout reports running for `running_polls` polls."""

    def __init__(self, running_polls):
        self.running_polls = running_polls
        self.polls = 0

    async def __call__(self, method, endpoint, params=None, json_data=None, timeout=None):
        if endpoint == "/layout/status":
            self.polls += 1
            return {"success": True, "running": self.polls <= self.running_polls}
        if endpoint == "/export/gexf":
            return {"success": False, "error": "not needed here"}
        return {"success": True}


@pytest.fixture
def waits(monkeypatch):
    recorded: list[float] = []

    async def record(delay, *args, **kwargs):
        recorded.append(delay)

    monkeypatch.setattr(gephi_mcp.asyncio, "sleep", record)
    return recorded


async def run(monkeypatch, fake):
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    return json.loads(await gephi_mcp.gephi_run_layout(algorithm="ForceAtlas 2", iterations=100, sync=True))


async def test_a_layout_that_finishes_at_once_is_noticed_within_a_tenth_of_a_second(monkeypatch, waits):
    result = await run(monkeypatch, StatusFake(running_polls=0))
    assert result["status"] == "completed"
    assert sum(waits) <= 0.1, f"waited {sum(waits)} s for a layout that had already finished"


async def test_the_wait_between_polls_grows_and_stops_at_a_quarter_second(monkeypatch, waits):
    # A cap of one second cost a 10,000-node layout about half a second in the benchmark: it
    # finished just after the poll at 0.75 s and the next came at 1.55 s.
    await run(monkeypatch, StatusFake(running_polls=12))
    assert waits[0] <= 0.1
    assert all(b >= a for a, b in zip(waits, waits[1:])), waits
    assert max(waits) == pytest.approx(0.25), waits


async def test_a_layout_that_never_finishes_still_gives_up_after_about_five_minutes(monkeypatch, waits):
    result = await run(monkeypatch, StatusFake(running_polls=10**9))
    assert result["status"] == "timeout"
    assert 295 <= sum(waits) <= 305, sum(waits)
