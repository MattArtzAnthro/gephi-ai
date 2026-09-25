"""An undo snapshot copies the workspace; the graph on screen is unchanged, so the methods
record must survive it. The fake sits under GephiClient.request (at httpx), because the reset
that caused the bug lives inside GephiClient.request itself."""
import asyncio
import json
import time

import anyio
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


def install_fake_gephi(monkeypatch, faults=None, gates=None):
    """Fake Gephi at the httpx layer. `faults` maps an endpoint path to the JSON body it
    should answer with instead, or to an exception it should raise. A list is a queue of
    one-shot answers for successive calls, where None means answer normally, and a callable is
    called for the answer. `gates` maps a
    path to a coroutine function awaited before that call is answered, so a test can hold a
    call open while another task runs. Every call yields to the event loop first, as a real
    request does. Every call is kept in state["calls"], and the id of every deleted workspace
    in state["deleted"]. state["duplicate"]() performs a duplicate, for faults that complete
    it in Gephi and then fail on the client side."""
    faults = {} if faults is None else faults
    gates = gates or {}
    state = {"ws": [{"id": 1, "name": "W", "current": True, "node_count": 5}], "next_id": 2,
             "calls": [], "deleted": []}

    def duplicate(switch=True, index=None):
        # Named as Gephi names a copy ("Copy of <name>"), with the source's node count. The
        # source is the workspace at `index`, or the current one.
        source = (state["ws"][index] if index is not None
                  else next((w for w in state["ws"] if w["current"]), state["ws"][0]))
        if switch:
            for w in state["ws"]:
                w["current"] = False
        wid = state["next_id"]
        state["next_id"] += 1
        state["ws"].append({"id": wid, "name": f"Copy of {source['name']}", "current": switch,
                            "node_count": source.get("node_count")})
        return {"success": True, "workspace_id": wid}

    state["duplicate"] = duplicate

    def answer(method, path, params, body):
        if path in faults:
            fault = faults[path]
            if isinstance(fault, list):
                fault = fault.pop(0) if fault else None
            if isinstance(fault, BaseException):
                raise fault
            if callable(fault):
                fault = fault()
            if fault is not None:
                return fault
        if path == "/workspace/list":
            return {"success": True, "workspaces": [dict(w) for w in state["ws"]]}
        if path == "/workspace/duplicate":
            return duplicate(index=body.get("index"))
        if path == "/workspace/rename":
            state["ws"][body["index"]]["name"] = body["name"]
            return {"success": True}
        if path == "/workspace/switch":
            for i, w in enumerate(state["ws"]):
                w["current"] = i == body["index"]
            return {"success": True}
        if path == "/workspace/delete":
            state["deleted"].append(state["ws"][int(params["index"])].get("id"))
            del state["ws"][int(params["index"])]
            return {"success": True}
        if path == "/export/gexf":
            return {"success": True, "content": GEXF}
        return {"success": True, "removed": 1}

    async def fake_request(self, method, url, params=None, json=None, **kwargs):
        await asyncio.sleep(0)
        path = httpx.URL(url).path
        state["calls"].append((method, path, dict(params or {}), dict(json or {})))
        if path in gates:
            await gates[path]()
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


async def test_a_snapshot_keeps_every_ledger_attribute(monkeypatch):
    # A ledger attribute that a reset clears, standing in for any field added after `entries`.
    def reset(self):
        self.entries = []
        self.extra = None

    monkeypatch.setattr(Ledger, "reset", reset)
    monkeypatch.setattr(gephi_mcp.LEDGER, "extra", None, raising=False)
    install_fake_gephi(monkeypatch)
    _record_layout()
    gephi_mcp.LEDGER.extra = {"a": 1}
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is True
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"
    assert gephi_mcp.LEDGER.extra == {"a": 1}, "the snapshot kept entries but not the rest"


async def test_a_graph_replaced_during_a_snapshot_still_resets_the_record(monkeypatch):
    # Tool calls run concurrently. A genuine graph replacement that lands while a snapshot is
    # between its workspace calls must leave the record reset: it describes the old graph.
    duplicate_started = asyncio.Event()
    clear_done = asyncio.Event()

    async def hold_duplicate():
        duplicate_started.set()
        await clear_done.wait()

    install_fake_gephi(monkeypatch, gates={"/workspace/duplicate": hold_duplicate})
    _record_layout()

    async def clear_mid_snapshot():
        await duplicate_started.wait()
        await gephi_mcp.gephi.request("POST", "/graph/clear")
        clear_done.set()

    # Bounded, so a regression that deadlocks the two tasks fails instead of hanging.
    snap, _ = await asyncio.wait_for(
        asyncio.gather(gephi_mcp.gephi_snapshot(label="x"), clear_mid_snapshot()), 5)
    assert json.loads(snap)["success"] is True
    assert gephi_mcp.LEDGER.receipt()["layout"] is None, "the snapshot restored a stale record"


async def test_a_graph_replaced_during_whatif_still_resets_the_record(monkeypatch):
    duplicate_started = asyncio.Event()
    clear_done = asyncio.Event()

    async def hold_duplicate():
        duplicate_started.set()
        await clear_done.wait()

    install_fake_gephi(monkeypatch, gates={"/workspace/duplicate": hold_duplicate})
    _record_layout()

    async def clear_mid_whatif():
        await duplicate_started.wait()
        await gephi_mcp.gephi.request("POST", "/graph/clear")
        clear_done.set()

    out, _ = await asyncio.wait_for(asyncio.gather(
        gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]), clear_mid_whatif()), 5)
    assert json.loads(out)["cleanup"]["returned_to_workspace_id"] == 1
    assert gephi_mcp.LEDGER.receipt()["layout"] is None, "whatif restored a stale record"


async def test_bookkeeping_still_retires_cached_graph_facts(monkeypatch):
    # Only the record reset is skipped during a snapshot; cached graph facts still go.
    install_fake_gephi(monkeypatch)
    _record_layout()
    monkeypatch.setattr(gephi_mcp, "_graph_facts", gephi_mcp.GraphFacts())
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is True
    assert gephi_mcp._graph_facts is None


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
    assert gephi_mcp.LEDGER.extra == {"a": 1}, "whatif kept entries but not the rest"


async def test_a_snapshot_that_fails_midway_keeps_the_record(monkeypatch):
    # GephiClient.request turns a connection error into an error dict. The snapshot has already
    # made its /workspace/duplicate call by the time the rename fails.
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
    # /workspace/duplicate has run. The bookkeeping mark must still be cleared on the way out.
    install_fake_gephi(monkeypatch, faults={"/workspace/rename": asyncio.CancelledError()})
    _record_layout()
    with pytest.raises(asyncio.CancelledError):
        await gephi_mcp.gephi_snapshot(label="x")
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"
    assert gephi_mcp._WORKSPACE_BOOKKEEPING.get() is False


async def test_whatif_drops_the_record_when_the_workspace_has_no_id(monkeypatch):
    # Without an id the switch back cannot be confirmed, so the record is not put back.
    state = install_fake_gephi(monkeypatch, faults={
        "/workspace/switch": {"success": False, "error": "switch refused"}})
    del state["ws"][0]["id"]
    _record_layout()
    await gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}])
    assert gephi_mcp.LEDGER.receipt()["layout"] is None


# ── A snapshot step that fails after the duplicate leaves no stray copy ──────


def _assert_back_on_the_original_with_no_copy(state):
    assert [(w["id"], w["current"]) for w in state["ws"]] == [(1, True)]
    assert state["deleted"] == [2], "the copy was not removed by its id"
    assert 1 not in state["deleted"], "the original workspace was deleted"


async def test_a_snapshot_whose_switch_back_fails_removes_the_copy(monkeypatch):
    state = install_fake_gephi(monkeypatch, faults={
        "/workspace/switch": [{"success": False, "error": "switch refused"}]})
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert "could not switch back to the original workspace" in out["error"]
    _assert_back_on_the_original_with_no_copy(state)


async def test_a_snapshot_whose_list_after_the_duplicate_fails_removes_the_copy(monkeypatch):
    # The list before the duplicate works, the one after fails, and the single retry works.
    state = install_fake_gephi(monkeypatch, faults={
        "/workspace/list": [None, {"success": False, "error": "busy"}]})
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert "workspace list unavailable after duplicate" in out["error"]
    _assert_back_on_the_original_with_no_copy(state)


async def test_a_snapshot_whose_list_fails_twice_says_a_copy_may_remain(monkeypatch):
    state = install_fake_gephi(monkeypatch, faults={
        "/workspace/list": [None, {"success": False, "error": "busy"},
                            {"success": False, "error": "busy"}]})
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert '"Copy of W"' in out["error"] and "close it by hand" in out["error"]
    # Without a list the copy cannot be told apart from the original, so nothing is deleted.
    assert state["deleted"] == []
    assert not any(m == "DELETE" for m, *_ in state["calls"])


def _duplicate_without_switching(state):
    """A duplicate that adds the copy but leaves the original current."""
    def fault():
        wid = state["next_id"]
        state["next_id"] += 1
        state["ws"].append({"id": wid, "name": "Copy of W", "current": False, "node_count": 5})
        return {"success": True}  # no workspace_id, so the copy must be found in the list
    return fault


async def test_a_snapshot_whose_copy_cannot_be_identified_removes_the_copy(monkeypatch):
    faults = {}
    state = install_fake_gephi(monkeypatch, faults=faults)
    faults["/workspace/duplicate"] = _duplicate_without_switching(state)
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert "duplicate did not switch to the copy" in out["error"]
    _assert_back_on_the_original_with_no_copy(state)


async def test_a_snapshot_never_deletes_when_no_new_workspace_appears(monkeypatch):
    # The duplicate claims success but nothing new is in the list: there is no copy to remove,
    # and nothing else may be deleted in its place.
    state = install_fake_gephi(monkeypatch, faults={
        "/workspace/duplicate": {"success": True}})
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert state["deleted"] == []
    assert [(w["id"], w["current"]) for w in state["ws"]] == [(1, True)]


# ── Cancellation and client-side failures leave no copy and no stale record ──
# The MCP SDK cancels a tool call through an anyio cancel scope. That cancellation is
# level-triggered: every later await in the scope is cancelled too, unless it is shielded.


def _hang_and_cancel(holder):
    async def gate():
        holder["cancelled_at"] = time.monotonic()
        holder["scope"].cancel()
        await asyncio.Event().wait()
    return gate


async def _run_cancellable(holder, coro_fn):
    async def run():
        with anyio.CancelScope() as scope:
            holder["scope"] = scope
            await coro_fn()
        return scope.cancelled_caught
    return await asyncio.wait_for(run(), 5)


async def test_whatif_cancelled_mid_edit_returns_to_the_original_and_removes_the_copy(
        monkeypatch):
    holder = {}
    state = install_fake_gephi(monkeypatch, gates={"/graph/node/a": _hang_and_cancel(holder)})
    _record_layout()
    caught = await _run_cancellable(
        holder, lambda: gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]))
    assert caught is True
    _assert_back_on_the_original_with_no_copy(state)
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


async def test_whatif_cancelled_when_cleanup_cannot_finish_resets_the_record(monkeypatch):
    holder = {}

    async def hang():
        await asyncio.Event().wait()

    # No raising=False: a renamed constant must fail here, not quietly set a new attribute.
    monkeypatch.setattr(gephi_mcp, "CLEANUP_TIMEOUT", 0.05)
    install_fake_gephi(monkeypatch, gates={"/graph/node/a": _hang_and_cancel(holder),
                                           "/workspace/switch": hang})
    _record_layout()
    caught = await _run_cancellable(
        holder, lambda: gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]))
    elapsed = time.monotonic() - holder["cancelled_at"]
    assert caught is True
    # The cleanup bound, not the 5 s limit in _run_cancellable, is what ended the hung switch,
    # so the time from the cancel stays well under half of that limit.
    assert elapsed < 2.5, f"the cleanup ran {elapsed:.2f} s after the cancel, past CLEANUP_TIMEOUT"
    # The person may still be on the edited copy, so the record cannot be trusted.
    assert gephi_mcp.LEDGER.receipt()["layout"] is None


async def test_a_snapshot_cancelled_midway_returns_to_the_original_and_removes_the_copy(
        monkeypatch):
    holder = {}
    state = install_fake_gephi(monkeypatch, gates={"/workspace/rename": _hang_and_cancel(holder)})
    _record_layout()
    caught = await _run_cancellable(holder, lambda: gephi_mcp.gephi_snapshot(label="x"))
    assert caught is True
    _assert_back_on_the_original_with_no_copy(state)
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


async def _hang():
    await asyncio.Event().wait()


async def test_a_snapshot_cancelled_when_its_cleanup_cannot_return_resets_the_record(
        monkeypatch):
    holder = {}
    monkeypatch.setattr(gephi_mcp, "CLEANUP_TIMEOUT", 0.05)
    install_fake_gephi(monkeypatch, gates={"/workspace/rename": _hang_and_cancel(holder),
                                           "/workspace/switch": _hang})
    _record_layout()
    caught = await _run_cancellable(holder, lambda: gephi_mcp.gephi_snapshot(label="x"))
    assert caught is True
    # The switch back never answered, so the person may still be on the copy.
    assert gephi_mcp.LEDGER.receipt()["layout"] is None


async def test_a_snapshot_cancelled_when_its_switch_back_fails_resets_the_record(monkeypatch):
    holder = {}
    state = install_fake_gephi(
        monkeypatch, faults={"/workspace/switch": {"success": False, "error": "switch refused"}},
        gates={"/workspace/rename": _hang_and_cancel(holder)})
    _record_layout()
    caught = await _run_cancellable(holder, lambda: gephi_mcp.gephi_snapshot(label="x"))
    assert caught is True
    assert state["deleted"] == [2]  # the copy is still removed by its id
    assert gephi_mcp.LEDGER.receipt()["layout"] is None


def _duplicate_then_cancel(holder):
    """A duplicate that completes in Gephi, after which the call is cancelled and never
    answers, so whatif does not learn the copy's id."""
    async def gate():
        holder["state"]["duplicate"]()
        holder["scope"].cancel()
        await asyncio.Event().wait()
    return gate


async def test_whatif_cancelled_during_the_duplicate_removes_the_copy(monkeypatch):
    holder = {}
    holder["state"] = state = install_fake_gephi(
        monkeypatch, gates={"/workspace/duplicate": _duplicate_then_cancel(holder)})
    _record_layout()
    caught = await _run_cancellable(
        holder, lambda: gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]))
    assert caught is True
    _assert_back_on_the_original_with_no_copy(state)
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


async def test_whatif_cancelled_during_the_duplicate_without_a_return_resets_the_record(
        monkeypatch):
    holder = {}
    monkeypatch.setattr(gephi_mcp, "CLEANUP_TIMEOUT", 0.05)
    holder["state"] = install_fake_gephi(
        monkeypatch, gates={"/workspace/duplicate": _duplicate_then_cancel(holder),
                            "/workspace/switch": _hang})
    _record_layout()
    caught = await _run_cancellable(
        holder, lambda: gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]))
    assert caught is True
    # The duplicate left the person on the copy and the switch back never answered.
    assert gephi_mcp.LEDGER.receipt()["layout"] is None


def _duplicate_then_time_out(state, copies=1):
    """A duplicate that completes in Gephi but times out on the client side."""
    def fault():
        for _ in range(copies):
            state["duplicate"]()
        raise httpx.ReadTimeout("timed out")
    return fault


async def test_a_snapshot_whose_duplicate_times_out_but_completes_removes_the_copy(monkeypatch):
    faults = {}
    state = install_fake_gephi(monkeypatch, faults=faults)
    faults["/workspace/duplicate"] = _duplicate_then_time_out(state)
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert "timed out" in out["error"]
    _assert_back_on_the_original_with_no_copy(state)


async def test_a_snapshot_whose_duplicate_times_out_leaves_several_copies_and_says_so(
        monkeypatch):
    faults = {}
    state = install_fake_gephi(monkeypatch, faults=faults)
    faults["/workspace/duplicate"] = _duplicate_then_time_out(state, copies=2)
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert "2 new workspaces appeared" in out["error"]
    assert state["deleted"] == []


async def test_a_snapshot_whose_duplicate_times_out_and_list_fails_says_so(monkeypatch):
    # The list answers before the duplicate, then keeps failing through the whole grace period.
    faults = {"/workspace/list": [None] + [{"success": False, "error": "busy"}] * 1000}
    state = install_fake_gephi(monkeypatch, faults=faults)
    faults["/workspace/duplicate"] = _duplicate_then_time_out(state)
    _fast_polls(monkeypatch, grace=0.05)
    _record_layout()
    out = json.loads(await asyncio.wait_for(gephi_mcp.gephi_snapshot(label="x"), 2))
    assert out["success"] is False
    assert "may still appear" in out["error"] and "close it by hand" in out["error"]
    assert state["deleted"] == []


async def test_whatif_whose_duplicate_times_out_but_completes_removes_the_copy(monkeypatch):
    faults = {}
    state = install_fake_gephi(monkeypatch, faults=faults)
    faults["/workspace/duplicate"] = _duplicate_then_time_out(state)
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]))
    assert out["success"] is False
    _assert_back_on_the_original_with_no_copy(state)
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


async def test_whatif_whose_duplicate_times_out_leaves_several_copies_and_says_so(monkeypatch):
    faults = {}
    state = install_fake_gephi(monkeypatch, faults=faults)
    faults["/workspace/duplicate"] = _duplicate_then_time_out(state, copies=2)
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]))
    assert out["success"] is False
    assert "2 new workspaces appeared" in out["error"]
    assert state["deleted"] == []
    # The duplicate left the person on a copy, so the record no longer describes the screen.
    assert gephi_mcp.LEDGER.receipt()["layout"] is None


async def test_whatif_resets_the_record_when_its_cleanup_raises(monkeypatch):
    # The reset is the default: a cleanup that raises part way cannot confirm the return.
    install_fake_gephi(monkeypatch, faults={"/workspace/switch": asyncio.CancelledError()})
    _record_layout()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(
            gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]), 5)
    assert gephi_mcp.LEDGER.receipt()["layout"] is None



# ── The snapshot copy is the workspace whose id Gephi reports ────────────────


def _renamed(state):
    return [c for c in state["calls"] if c[1] == "/workspace/rename"]


async def test_a_snapshot_never_renames_a_workspace_other_than_the_reported_copy(monkeypatch):
    # The duplicate reports copy 2, but workspace 3 is the one that became current.
    faults = {}
    state = install_fake_gephi(monkeypatch, faults=faults)

    def duplicate():
        reply = state["duplicate"]()
        state["duplicate"]()
        return reply

    faults["/workspace/duplicate"] = duplicate
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert _renamed(state) == [], "a workspace other than the reported copy was renamed"
    assert state["deleted"] == [2]  # the reported copy, by its id
    assert "1 other new workspace" in out["error"]


async def test_a_snapshot_whose_reported_copy_is_missing_touches_nothing(monkeypatch):
    faults = {}
    state = install_fake_gephi(monkeypatch, faults=faults)

    def duplicate():
        state["duplicate"]()
        return {"success": True, "workspace_id": 99}

    faults["/workspace/duplicate"] = duplicate
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert _renamed(state) == []
    assert state["deleted"] == []
    assert "1 new workspace appeared" in out["error"]


# ── The failure message says what is known ───────────────────────────────────


async def test_a_removed_copy_with_an_unconfirmed_switch_back_says_so(monkeypatch):
    state = install_fake_gephi(monkeypatch, faults={"/workspace/switch": [
        {"success": False, "error": "switch refused"}, {"success": False, "error": "again"}]})
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert state["deleted"] == [2]
    assert "the copy was removed" in out["error"]
    assert "which workspace is now current could not be confirmed" in out["error"]
    assert "still the current workspace" not in out["error"]
    # Not confirmed back on the original, so the record is not trusted.
    assert gephi_mcp.LEDGER.receipt()["layout"] is None


async def test_a_copy_that_could_not_be_deleted_is_reported_as_left(monkeypatch):
    state = install_fake_gephi(monkeypatch, faults={
        "/workspace/rename": {"success": False, "error": "rename refused"},
        "/workspace/delete": {"success": False, "error": "delete refused"}})
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert "a copy of the workspace was left in Gephi's tab bar" in out["error"]
    assert "could not be confirmed" not in out["error"]
    assert [(w["id"], w["current"]) for w in state["ws"]] == [(1, True), (2, False)]
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


async def test_a_snapshot_never_treats_a_pre_existing_workspace_as_the_copy(monkeypatch):
    # The duplicate reports the id of a workspace that was there before it, and that workspace
    # is now current. It is not the copy, so nothing may be renamed or deleted.
    faults = {}
    state = install_fake_gephi(monkeypatch, faults=faults)
    state["ws"].append({"id": 5, "name": "Other", "current": False, "node_count": 5})

    def duplicate():
        state["duplicate"]()
        for w in state["ws"]:
            w["current"] = w["id"] == 5
        return {"success": True, "workspace_id": 5}

    faults["/workspace/duplicate"] = duplicate
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_snapshot(label="x"))
    assert out["success"] is False
    assert _renamed(state) == []
    assert state["deleted"] == []


# ── whatif validates the reported copy before editing or deleting it ────────


async def test_whatif_never_treats_the_original_as_the_copy(monkeypatch):
    # The duplicate reports the ORIGINAL's id as the copy. If whatif trusted that, it would
    # edit and then delete the person's own workspace.
    faults = {}
    state = install_fake_gephi(monkeypatch, faults=faults)

    def duplicate():
        state["duplicate"]()  # a real copy (id 2) is made and made current
        return {"success": True, "workspace_id": 1}  # but the original's id is reported

    faults["/workspace/duplicate"] = duplicate
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]))
    assert out["success"] is False
    assert state["deleted"] == [], "nothing may be deleted when the copy cannot be identified"
    assert any(w["id"] == 1 for w in state["ws"]), "the original workspace was deleted"


async def test_whatif_never_treats_a_pre_existing_workspace_as_the_copy(monkeypatch):
    # The duplicate reports the id of an unrelated workspace that existed before it ran.
    faults = {}
    state = install_fake_gephi(monkeypatch, faults=faults)
    state["ws"].append({"id": 5, "name": "Other", "current": False, "node_count": 5})

    def duplicate():
        state["duplicate"]()  # a real copy (id 2) is made and made current
        return {"success": True, "workspace_id": 5}  # but a pre-existing id is reported

    faults["/workspace/duplicate"] = duplicate
    _record_layout()
    out = json.loads(await gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]))
    assert out["success"] is False
    assert state["deleted"] == [], "nothing may be deleted when the copy cannot be identified"
    assert any(w["id"] == 1 for w in state["ws"]), "the original workspace was deleted"
    assert any(w["id"] == 5 for w in state["ws"]), "an unrelated pre-existing workspace was deleted"


# ── A duplicate that timed out can still finish in Gephi later ──
# After a timeout the workspace list is polled for a while; a copy that appears is removed by
# its id. Every other failure is checked once, as before.

WHATIF_ENTRY = "whatif"
ENTRIES = {
    "snapshot": lambda: gephi_mcp.gephi_snapshot(label="x"),
    WHATIF_ENTRY: lambda: gephi_mcp.gephi_whatif(edits=[{"op": "remove_node", "id": "a"}]),
}


def _fast_polls(monkeypatch, grace):
    # No raising=False: a renamed constant must fail here, not quietly set a new attribute.
    monkeypatch.setattr(gephi_mcp, "DUPLICATE_POLL_INTERVAL", 0.001)
    monkeypatch.setattr(gephi_mcp, "DUPLICATE_GRACE", grace)


def _late_copy(monkeypatch, on_poll=None, copies=1, appears=None):
    """A duplicate that times out on the client side and makes nothing at first. On list call
    number `on_poll` after the timeout, `copies` copies appear in Gephi, or, when `appears` is
    given, that workspace appears instead. track["polls"] counts the list calls made after the
    timeout."""
    track = {"timed_out": False, "polls": 0}
    faults = {}

    def duplicate():
        track["timed_out"] = True
        raise httpx.ReadTimeout("timed out")

    def listing():
        if track["timed_out"]:
            track["polls"] += 1
            if track["polls"] == on_poll and appears is not None:
                state["ws"].append(dict(appears))
            elif track["polls"] == on_poll:
                for _ in range(copies):
                    state["duplicate"]()
        return None

    state = install_fake_gephi(monkeypatch, faults=faults)
    faults.update({"/workspace/duplicate": duplicate, "/workspace/list": listing})
    return state, track


@pytest.mark.parametrize("entry", ENTRIES)
async def test_a_copy_that_appears_after_the_timeout_is_removed(monkeypatch, entry):
    state, track = _late_copy(monkeypatch, on_poll=3)
    _fast_polls(monkeypatch, grace=5)
    _record_layout()
    out = json.loads(await asyncio.wait_for(ENTRIES[entry](), 2))
    assert out["success"] is False
    assert "its copy was removed" in out["error"]
    _assert_back_on_the_original_with_no_copy(state)
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


@pytest.mark.parametrize("entry", ENTRIES)
async def test_a_copy_that_never_appears_is_reported_and_nothing_is_deleted(monkeypatch, entry):
    state, track = _late_copy(monkeypatch, on_poll=None)
    _fast_polls(monkeypatch, grace=0.05)
    _record_layout()
    # Bounded: polling that ignored the grace period would never return.
    out = json.loads(await asyncio.wait_for(ENTRIES[entry](), 2))
    assert out["success"] is False
    assert "may still appear" in out["error"] and "close it by hand" in out["error"]
    assert track["polls"] > 1, "the list was checked once, not polled"
    assert state["deleted"] == []
    assert [(w["id"], w["current"]) for w in state["ws"]] == [(1, True)]
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


@pytest.mark.parametrize("entry", ENTRIES)
async def test_two_copies_that_appear_after_the_timeout_are_both_left(monkeypatch, entry):
    state, track = _late_copy(monkeypatch, on_poll=2, copies=2)
    _fast_polls(monkeypatch, grace=5)
    _record_layout()
    out = json.loads(await asyncio.wait_for(ENTRIES[entry](), 2))
    assert out["success"] is False
    assert "2 new workspaces appeared" in out["error"] and "none was removed" in out["error"]
    assert state["deleted"] == []


@pytest.mark.parametrize("entry", ENTRIES)
async def test_a_duplicate_that_fails_without_a_timeout_is_checked_once(monkeypatch, entry):
    track = {"failed": False, "lists_after": 0}

    def duplicate():
        track["failed"] = True
        return {"success": False, "error": "duplicate refused"}

    def listing():
        track["lists_after"] += track["failed"]
        return None

    install_fake_gephi(monkeypatch, faults={"/workspace/duplicate": duplicate,
                                            "/workspace/list": listing})
    _fast_polls(monkeypatch, grace=0.05)
    out = json.loads(await asyncio.wait_for(ENTRIES[entry](), 2))
    assert out["success"] is False
    assert track["lists_after"] == 1


@pytest.mark.parametrize("entry", ENTRIES)
async def test_a_call_cancelled_while_polling_stops_and_removes_the_copy(monkeypatch, entry):
    holder = {}
    track = {"timed_out": False, "lists_after": 0}
    cancel = _hang_and_cancel(holder)

    def duplicate():
        track["timed_out"] = True
        raise httpx.ReadTimeout("timed out")

    async def list_gate():
        if track["timed_out"]:
            track["lists_after"] += 1
            if track["lists_after"] == 2:
                # The copy lands in Gephi while the second poll is out, and the call is
                # cancelled before that poll answers.
                state["duplicate"]()
                await cancel()

    state = install_fake_gephi(monkeypatch, faults={"/workspace/duplicate": duplicate},
                               gates={"/workspace/list": list_gate})
    _fast_polls(monkeypatch, grace=5)
    # The cleanup is shielded from cancellation, so this bound, not the one in
    # _run_cancellable, is what ends a cleanup that hangs.
    monkeypatch.setattr(gephi_mcp, "CLEANUP_TIMEOUT", 1)
    _record_layout()
    caught = await _run_cancellable(holder, ENTRIES[entry])
    assert caught is True
    _assert_back_on_the_original_with_no_copy(state)
    # No poll followed the cancelled one. The cleanup ran once: one list to find the copy, two
    # in the switch-and-delete, and one delete.
    assert track["lists_after"] == 2 + 3
    assert [p for _, p, _, _ in state["calls"]].count("/workspace/delete") == 1
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"


@pytest.mark.parametrize("entry", ENTRIES)
@pytest.mark.parametrize("workspace", [
    {"id": 9, "name": "My new study", "current": False, "node_count": 0},
    {"id": 9, "name": "My new study", "current": False, "node_count": 5},
    {"id": 9, "name": "Copy of W", "current": False, "node_count": 0},
], ids=["empty", "other-name", "other-node-count"])
async def test_a_workspace_made_by_hand_after_the_timeout_is_left(monkeypatch, entry, workspace):
    # A person made a workspace while the server waited for the copy. It is the one new
    # workspace, but it does not look like the copy, so it is not deleted.
    state, track = _late_copy(monkeypatch, on_poll=2, appears=workspace)
    _fast_polls(monkeypatch, grace=5)
    _record_layout()
    out = json.loads(await asyncio.wait_for(ENTRIES[entry](), 2))
    assert out["success"] is False
    assert "does not look like the copy; it was left" in out["error"]
    assert state["deleted"] == []
    assert [(w["id"], w["current"]) for w in state["ws"]] == [(1, True), (9, False)]
    assert gephi_mcp.LEDGER.receipt()["layout"]["algorithm"] == "ForceAtlas 2"

