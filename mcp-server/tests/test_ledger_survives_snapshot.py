"""An undo snapshot copies the workspace; the graph on screen is unchanged, so the methods
record must survive it. The fake sits under GephiClient.request (at httpx), because the reset
that caused the bug lives inside GephiClient.request itself."""
import json

import httpx

import gephi_mcp
from session_ledger import Ledger


def install_fake_gephi(monkeypatch):
    state = {"ws": [{"id": 1, "name": "W", "current": True, "node_count": 5}]}

    def answer(method, path, body):
        if path == "/workspace/list":
            return {"success": True, "workspaces": [dict(w) for w in state["ws"]]}
        if path == "/workspace/duplicate":
            for w in state["ws"]:
                w["current"] = False
            state["ws"].append({"id": 2, "name": "W copy", "current": True, "node_count": 5})
            return {"success": True}
        if path == "/workspace/rename":
            state["ws"][body["index"]]["name"] = body["name"]
            return {"success": True}
        if path == "/workspace/switch":
            for i, w in enumerate(state["ws"]):
                w["current"] = i == body["index"]
            return {"success": True}
        return {"success": True, "removed": 1}

    async def fake_request(self, method, url, params=None, json=None, **kwargs):
        path = httpx.URL(url).path
        return httpx.Response(200, json=answer(method, path, json or {}),
                              request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)


async def test_layout_survives_the_auto_snapshot_before_a_filter(monkeypatch):
    install_fake_gephi(monkeypatch)
    monkeypatch.setattr(gephi_mcp, "AUTO_SNAPSHOT", True)
    gephi_mcp.LEDGER.reset()
    gephi_mcp.LEDGER.record("run_layout", algorithm="ForceAtlas 2", iterations=100)
    out = json.loads(await gephi_mcp.gephi_filter_by_degree(min=2))
    assert out["undo_available"] is True  # the fake produced a real snapshot sequence
    assert gephi_mcp.LEDGER.receipt()["layout"] is not None, "the undo snapshot wiped the record"
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


async def test_a_real_graph_change_still_resets(monkeypatch):
    install_fake_gephi(monkeypatch)
    gephi_mcp.LEDGER.reset()
    gephi_mcp.LEDGER.record("run_layout", algorithm="ForceAtlas 2", iterations=100)
    await gephi_mcp.gephi.request("POST", "/graph/clear")
    assert gephi_mcp.LEDGER.receipt()["layout"] is None


def test_state_round_trips_every_attribute():
    led = Ledger()
    led.record("run_layout", algorithm="X", iterations=1)
    led.extra = {"a": 1}
    saved = led.state()
    led.reset()
    led.extra = None
    led.restore(saved)
    assert led.receipt()["layout"]["algorithm"] == "X"
    assert led.extra == {"a": 1}
