"""An undo snapshot copies the workspace; the graph on screen is unchanged, so the methods
record must survive it. The fake sits under GephiClient.request (at httpx), because the reset
that caused the bug lives inside GephiClient.request itself."""
import asyncio
import json

import httpx
import pytest

import gephi_mcp
from session_ledger import Ledger

# A three-node path, enough for the structural profile whatif computes before and after.
GEXF = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<gexf xmlns="http://gexf.net/1.3" version="1.3">'
    '<graph defaultedgetype="undirected"><nodes>'
    '<node id="a" label="a"/><node id="b" label="b"/><node id="c" label="c"/>'
    '</nodes><edges>'
    '<edge id="0" source="a" target="b"/><edge id="1" source="b" target="c"/>'
    '</edges></graph></gexf>'
)


def install_fake_gephi(monkeypatch, faults=None):
    """Fake Gephi at the httpx layer. `faults` maps an endpoint path to the JSON body it
    should answer with instead, or to an exception it should raise."""
    faults = faults or {}
    state = {"ws": [{"id": 1, "name": "W", "current": True, "node_count": 5}], "next_id": 2}

    def answer(method, path, params, body):
        if path in faults:
            fault = faults[path]
            if isinstance(fault, BaseException):
                raise fault
            return fault
        if path == "/workspace/list":
            return {"success": True, "workspaces": [dict(w) for w in state["ws"]]}
        if path == "/workspace/duplicate":
            for w in state["ws"]:
                w["current"] = False
            wid = state["next_id"]
            state["next_id"] += 1
            state["ws"].append({"id": wid, "name": "W copy", "current": True, "node_count": 5})
            return {"success": True, "workspace_id": wid}
        if path == "/workspace/rename":
            state["ws"][body["index"]]["name"] = body["name"]
            return {"success": True}
        if path == "/workspace/switch":
            for i, w in enumerate(state["ws"]):
                w["current"] = i == body["index"]
            return {"success": True}
        if path == "/workspace/delete":
            del state["ws"][int(params["index"])]
            return {"success": True}
        if path == "/export/gexf":
            return {"success": True, "content": GEXF}
        return {"success": True, "removed": 1}

    async def fake_request(self, method, url, params=None, json=None, **kwargs):
        path = httpx.URL(url).path
        return httpx.Response(200, json=answer(method, path, params or {}, json or {}),
                              request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)
    return state


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


def _record_layout():
    gephi_mcp.LEDGER.reset()
    gephi_mcp.LEDGER.record("run_layout", algorithm="ForceAtlas 2", iterations=100)


async def test_whatif_keeps_the_record_when_the_duplicate_fails(monkeypatch):
    install_fake_gephi(monkeypatch, faults={
        "/workspace/duplicate": {"success": False, "error": "timeout"}})
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]))
    assert out["success"] is False  # nothing was copied, so nothing was measured
    assert gephi_mcp.LEDGER.receipt()["layout"] is not None, "a failed duplicate wiped the record"
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


async def test_whatif_drops_the_record_when_it_cannot_switch_back(monkeypatch):
    install_fake_gephi(monkeypatch, faults={
        "/workspace/switch": {"success": False, "error": "switch refused"}})
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]))
    assert out["success"] is True  # the run itself completed; only the switch back failed
    assert out["cleanup"]["returned_to_workspace_id"] is None  # left on the edited copy
    # The record describes the original graph, which is not the one on screen any more.
    assert gephi_mcp.LEDGER.receipt()["layout"] is None


async def test_a_manual_snapshot_keeps_the_record(monkeypatch):
    install_fake_gephi(monkeypatch)
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is True
    assert out["snapshot"] == "[undo] W (before x)"
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


async def test_whatif_keeps_every_ledger_attribute(monkeypatch):
    # A ledger attribute that a reset clears, standing in for any field added after `entries`.
    def reset(self):
        self.entries = []
        self.extra = None

    monkeypatch.setattr(Ledger, "reset", reset)
    monkeypatch.setattr(gephi_mcp.LEDGER, "extra", None, raising=False)
    install_fake_gephi(monkeypatch)
    _record_layout()
    gephi_mcp.LEDGER.extra = {"a": 1}
    out = json.loads(await gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]))
    assert out["success"] is True
    assert out["cleanup"]["returned_to_workspace_id"] == 1
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"
    assert gephi_mcp.LEDGER.extra == {"a": 1}, "whatif restored entries but not the rest"


async def test_a_snapshot_that_fails_midway_keeps_the_record(monkeypatch):
    # GephiClient.request turns a connection error into an error dict. /workspace/duplicate has
    # already reset the record by the time the rename fails.
    state = install_fake_gephi(monkeypatch, faults={
        "/workspace/rename": httpx.ConnectError("connection refused")})
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    # An unnamed copy is not an undo point gephi_undo can find, so no undo is claimed.
    assert out["success"] is False
    assert "could not name the undo copy" in out["error"]
    # The unnamed copy is removed and the person is back on their own workspace.
    assert [(w["id"], w["current"]) for w in state["ws"]] == [(1, True)]
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


async def test_a_destructive_tool_reports_no_undo_when_the_rename_fails(monkeypatch):
    install_fake_gephi(monkeypatch, faults={
        "/workspace/rename": {"success": False, "error": "rename refused"}})
    monkeypatch.setattr(gephi_mcp, "AUTO_SNAPSHOT", True)
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_filter_by_degree(min=2))
    assert out["undo_available"] is False


async def test_a_snapshot_interrupted_midway_keeps_the_record(monkeypatch):
    # A cancellation is not caught by GephiClient.request, so it escapes the snapshot after
    # /workspace/duplicate has reset the record. The restore still has to run.
    install_fake_gephi(monkeypatch, faults={"/workspace/rename": asyncio.CancelledError()})
    _record_layout()
    with pytest.raises(asyncio.CancelledError):
        await gephi_mcp.gephi_snapshot(label="x")
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


async def test_whatif_drops_the_record_when_the_workspace_has_no_id(monkeypatch):
    # Without an id the switch back cannot be confirmed, so the record is not put back.
    state = install_fake_gephi(monkeypatch, faults={
        "/workspace/switch": {"success": False, "error": "switch refused"}})
    del state["ws"][0]["id"]
    _record_layout()
    await gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}])
    assert gephi_mcp.LEDGER.receipt()["layout"] is None
