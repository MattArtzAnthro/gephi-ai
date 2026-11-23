"""Guards the formal models in formal/tla rest on: each test fails without its guard.

Workspace.tla: gephi_undo removes only the workspace its snapshot was copied from; a compare
that cannot switch back ends the methods record; no change runs when a failed snapshot left
another workspace on screen. Layout.tla: a stopped layout is recorded as stopped, and a sync run
does not decide while a stop request is unanswered.
"""

import asyncio
import json

import pytest
from test_undo import Recorder, endpoints, out_of, ws, ws_list

import gephi_mcp

GEXF = ('<?xml version="1.0" encoding="UTF-8"?><gexf xmlns="http://gexf.net/1.3" version="1.3">'
        '<graph defaultedgetype="undirected"><nodes><node id="a" label="a"/></nodes>'
        '<edges></edges></graph></gexf>')


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    monkeypatch.setattr(gephi_mcp.gephi, "request", r)
    monkeypatch.setattr(gephi_mcp, "_undo_source", None)
    monkeypatch.setattr(gephi_mcp, "_open_layout", None)
    gephi_mcp.LEDGER.reset()
    gephi_mcp.LEDGER.earlier = []
    return r


async def take_snapshot(rec, source_id=1, copy_id=3):
    """A snapshot of workspace `source_id` ("A"), beside an unrelated workspace 2 ("B")."""
    rec.responses = [
        ws_list(ws(source_id, "A", current=True), ws(2, "B")),
        {"success": True, "workspace_id": copy_id},
        ws_list(ws(source_id, "A"), ws(2, "B"), ws(copy_id, "Copy of A", current=True)),
        {"success": True},
        {"success": True},
    ]
    assert (await out_of(gephi_mcp.gephi_snapshot))["success"]
    rec.calls.clear()


def deleted(rec):
    return [c["params"]["index"] for c in rec.calls if c["endpoint"] == "/workspace/delete"]


async def test_undo_after_a_switch_removes_the_snapshots_source_not_the_workspace_on_screen(rec):
    await take_snapshot(rec)
    listed = ws_list(ws(1, "A"), ws(2, "B", current=True), ws(3, "[undo] A (before snapshot)"))
    after = ws_list(ws(2, "B"), ws(3, "[undo] A (before snapshot)", current=True))
    rec.responses = [listed, {"success": True}, listed, {"success": True}, after, {"success": True}]
    result = await out_of(gephi_mcp.gephi_undo)
    assert result["success"] and result["restored"] == "A"
    assert deleted(rec) == ["0"], "the changed workspace A goes; B, on screen, is not the source"
    assert "B" in result["note"]


async def test_undo_with_no_memory_of_the_source_keeps_a_workspace_of_another_name(rec):
    """After a server restart the source is unknown. The workspace on screen is removed only
    when it carries the name the snapshot was taken under."""
    listed = ws_list(ws(1, "A"), ws(2, "B", current=True), ws(3, "[undo] A (before filter)"))
    after = ws_list(ws(1, "A"), ws(2, "B"), ws(3, "[undo] A (before filter)", current=True))
    rec.responses = [listed, {"success": True}, after, {"success": True}]
    result = await out_of(gephi_mcp.gephi_undo)
    assert result["success"]
    assert deleted(rec) == []
    assert "was kept" in result["note"]


async def test_undo_with_no_memory_still_removes_the_changed_workspace_on_screen(rec):
    listed = ws_list(ws(1, "A", current=True), ws(3, "[undo] A (before filter)"))
    after = ws_list(ws(3, "[undo] A (before filter)", current=True))
    rec.responses = [listed, {"success": True}, listed, {"success": True}, after, {"success": True}]
    result = await out_of(gephi_mcp.gephi_undo)
    assert result["success"] and deleted(rec) == ["0"] and "note" not in result


async def test_undo_forgets_the_source_once_used(rec):
    await take_snapshot(rec)
    listed = ws_list(ws(1, "A", current=True), ws(3, "[undo] A (before snapshot)"))
    after = ws_list(ws(3, "[undo] A (before snapshot)", current=True))
    rec.responses = [listed, {"success": True}, listed, {"success": True}, after, {"success": True}]
    assert (await out_of(gephi_mcp.gephi_undo))["success"]
    assert gephi_mcp._undo_source is None


async def test_compare_that_cannot_switch_back_ends_the_record_and_says_so(rec, monkeypatch):
    async def export():
        return {"success": True, "content": GEXF}
    monkeypatch.setattr(gephi_mcp, "_export_gexf_inline", export)
    gephi_mcp.LEDGER.record("color_by_partition", column="group")
    listed = ws_list(ws(1, "A", current=True), ws(2, "B"))
    rec.responses = [listed, {"success": True}, {"success": False, "error": "busy"},
                     listed, {"success": True}, {"success": True}]
    result = await out_of(gephi_mcp.gephi_compare_workspaces, before=1, after=0)
    assert gephi_mcp.LEDGER.entries == [], "the record described workspace A; B is on screen"
    assert "could not" in result["workspace_warning"]


async def test_compare_that_switches_back_keeps_the_record(rec, monkeypatch):
    async def export():
        return {"success": True, "content": GEXF}
    monkeypatch.setattr(gephi_mcp, "_export_gexf_inline", export)
    gephi_mcp.LEDGER.record("color_by_partition", column="group")
    listed = ws_list(ws(1, "A", current=True), ws(2, "B"))
    rec.responses = [listed, {"success": True}, {"success": True},
                     listed, {"success": True}, {"success": True}]
    result = await out_of(gephi_mcp.gephi_compare_workspaces, before=1, after=0)
    assert len(gephi_mcp.LEDGER.entries) == 1 and "workspace_warning" not in result


async def test_no_change_runs_when_a_failed_snapshot_left_another_workspace_on_screen(rec):
    """The duplicate worked, but neither the switch back nor the cleanup's switch did, so the
    copy is on screen. Clearing now would clear a workspace nobody chose."""
    before = ws_list(ws(1, "A", current=True))
    on_copy = ws_list(ws(1, "A"), ws(3, "Copy of A", current=True))
    rec.responses = [
        before, {"success": True, "workspace_id": 3}, on_copy,
        {"success": True},                        # rename
        {"success": False, "error": "busy"},      # switch back
        on_copy,                                  # cleanup: list
        on_copy, {"success": False, "error": "busy"},   # switch to the original fails
        on_copy, {"success": False, "error": "busy"},   # delete fails
    ]
    result = await out_of(gephi_mcp.gephi_clear_graph)
    assert result["success"] is False and "was not run" in result["error"]
    assert "/graph/clear" not in endpoints(rec)


async def test_a_failed_snapshot_that_got_back_to_the_original_lets_the_change_run(rec):
    before = ws_list(ws(1, "A", current=True))
    rec.responses = [before, {"success": False, "error": "no memory"}, before]
    result = await out_of(gephi_mcp.gephi_clear_graph)
    assert "/graph/clear" in endpoints(rec) and result["undo_available"] is False


async def test_stopping_a_background_layout_marks_it_stopped_in_the_record(rec):
    rec.responses = [{"success": True, "status": "running"},
                     {"success": True, "message": "Layout stopped"}]
    await gephi_mcp.gephi_run_layout("ForceAtlas 2", iterations=5000)
    await gephi_mcp.gephi_stop_layout()
    layout = gephi_mcp.LEDGER.receipt()["layout"]
    assert layout["stopped_before_finishing"] is True
    assert layout["iterations_requested"] == 5000 and "iterations" not in layout


async def test_a_stop_with_no_layout_running_marks_nothing(rec):
    rec.responses = [{"success": True, "status": "running"},
                     {"success": True, "message": "No layout running"}]
    await gephi_mcp.gephi_run_layout("ForceAtlas 2", iterations=5000)
    await gephi_mcp.gephi_stop_layout()
    assert gephi_mcp.LEDGER.receipt()["layout"]["iterations"] == 5000


async def test_a_sync_run_waits_for_an_unanswered_stop_before_it_decides(monkeypatch):
    """Gephi has stopped the layout, but the stop's answer has not arrived when the poll sees
    no layout running. Deciding then reported a stopped layout as completed."""
    gephi_mcp.LEDGER.reset()
    answered = asyncio.Event()
    polled = asyncio.Event()

    async def request(method, endpoint, params=None, json_data=None, timeout=None):
        if endpoint == "/layout/run":
            return {"success": True, "status": "running"}
        if endpoint == "/layout/stop":
            await answered.wait()
            return {"success": True, "message": "Layout stopped"}
        if endpoint == "/layout/status":
            polled.set()
            return {"success": True, "running": False}
        return {"success": False}

    real_sleep = asyncio.sleep

    async def short_sleep(_seconds):
        await real_sleep(0)

    monkeypatch.setattr(gephi_mcp.gephi, "request", request)
    monkeypatch.setattr(gephi_mcp.asyncio, "sleep", short_sleep)
    run = asyncio.ensure_future(gephi_mcp.gephi_run_layout("ForceAtlas 2", sync=True))
    stop = asyncio.ensure_future(gephi_mcp.gephi_stop_layout())
    await polled.wait()
    for _ in range(5):
        await real_sleep(0)
    answered.set()
    result = json.loads(await run)
    await stop
    assert result["status"] == "stopped"


async def test_a_stop_marks_the_run_that_was_left_running_not_a_later_computed_layout(rec):
    """A background run, then a computed layout that records its own entry. The stop reached
    the background run, so that is the entry marked; the computed layout ran in full."""
    rec.responses = [{"success": True, "status": "running"},
                     {"success": True, "message": "Layout stopped"}]
    await gephi_mcp.gephi_run_layout("ForceAtlas 2", iterations=5000)
    gephi_mcp.LEDGER.record("run_layout", algorithm="gephi_community_layout")
    await gephi_mcp.gephi_stop_layout()
    first, second = [e for e in gephi_mcp.LEDGER.entries if e["operation"] == "run_layout"]
    assert first.get("stopped_before_finishing") is True
    assert "stopped_before_finishing" not in second


async def test_a_run_seen_to_finish_is_not_marked_by_a_later_stop(rec):
    """The status call saw the background run end. A layout started by hand in Gephi and
    stopped afterwards is not that run."""
    rec.responses = [{"success": True, "status": "running"},
                     {"success": True, "running": False},
                     {"success": True, "message": "Layout stopped"}]
    await gephi_mcp.gephi_run_layout("ForceAtlas 2", iterations=5000)
    await gephi_mcp.gephi_get_layout_status()
    await gephi_mcp.gephi_stop_layout()
    assert gephi_mcp.LEDGER.receipt()["layout"]["iterations"] == 5000


async def test_a_stop_after_the_graph_changed_marks_nothing(rec):
    rec.responses = [{"success": True, "status": "running"},
                     {"success": True, "message": "Layout stopped"}]
    await gephi_mcp.gephi_run_layout("ForceAtlas 2", iterations=5000)
    gephi_mcp.LEDGER.start_new_graph("a file was imported")
    gephi_mcp.LEDGER.record("run_layout", algorithm="gephi_community_layout")
    await gephi_mcp.gephi_stop_layout()
    assert "stopped_before_finishing" not in gephi_mcp.LEDGER.receipt()["layout"]
    assert "stopped_before_finishing" not in gephi_mcp.LEDGER.receipt()["earlier"][0]["layout"]


async def test_a_snapshot_that_fails_by_exception_off_the_original_also_refuses(rec):
    """The duplicate worked, then naming the copy raised, and the cleanup could not switch
    back. An exception must not turn into "no undo, go ahead" with the copy on screen."""
    before = ws_list(ws(1, "A", current=True))
    on_copy = ws_list(ws(1, "A"), ws(3, "Copy of A", current=True))
    rec.responses = [before, {"success": True, "workspace_id": 3}, on_copy,
                     "not a reply",                                   # rename: malformed
                     on_copy, on_copy, {"success": False, "error": "busy"},
                     on_copy, {"success": False, "error": "busy"}]
    result = await out_of(gephi_mcp.gephi_clear_graph)
    assert result["success"] is False and "was not run" in result["error"]
    assert "/graph/clear" not in endpoints(rec)


async def test_a_snapshot_that_fails_by_exception_back_on_the_original_lets_the_change_run(rec):
    before = ws_list(ws(1, "A", current=True))
    on_copy = ws_list(ws(1, "A"), ws(3, "Copy of A", current=True))
    rec.responses = [before, {"success": True, "workspace_id": 3}, on_copy,
                     "not a reply",                                   # rename: malformed
                     on_copy, on_copy, {"success": True}, on_copy, {"success": True}]
    result = await out_of(gephi_mcp.gephi_clear_graph)
    assert "/graph/clear" in endpoints(rec) and result["undo_available"] is False


async def test_compare_warns_when_the_first_read_stranded_and_the_second_failed(rec, monkeypatch):
    async def export():
        return {"success": True, "content": GEXF}
    monkeypatch.setattr(gephi_mcp, "_export_gexf_inline", export)
    listed = ws_list(ws(1, "A", current=True), ws(2, "B"))
    rec.responses = [listed, {"success": True}, {"success": False, "error": "busy"},
                     {"success": False, "error": "busy"}]
    result = await out_of(gephi_mcp.gephi_compare_workspaces, before=1, after=0)
    assert result["success"] is False and "could not" in result["workspace_warning"]


async def test_compare_warns_when_a_read_failed_and_could_not_switch_back(rec, monkeypatch):
    async def export():
        return {"success": False, "error": "export failed"}
    monkeypatch.setattr(gephi_mcp, "_export_gexf_inline", export)
    gephi_mcp.LEDGER.record("color_by_partition", column="group")
    listed = ws_list(ws(1, "A", current=True), ws(2, "B"))
    rec.responses = [listed, {"success": True}, {"success": False, "error": "busy"}]
    result = await out_of(gephi_mcp.gephi_compare_workspaces, before=1, after=0)
    assert result["success"] is False and "could not" in result["workspace_warning"]
    assert gephi_mcp.LEDGER.entries == []


async def test_a_read_that_fails_but_switches_back_carries_no_workspace_warning(rec, monkeypatch):
    async def export():
        return {"success": False, "error": "export failed"}
    monkeypatch.setattr(gephi_mcp, "_export_gexf_inline", export)
    listed = ws_list(ws(1, "A", current=True), ws(2, "B"))
    rec.responses = [listed, {"success": True}, {"success": True}]
    result = await out_of(gephi_mcp.gephi_compare_workspaces, before=1, after=0)
    assert result["success"] is False and "workspace_warning" not in result


async def test_an_undo_that_could_not_switch_still_knows_the_source_on_retry(rec):
    await take_snapshot(rec)
    listed = ws_list(ws(1, "A"), ws(2, "B", current=True), ws(3, "[undo] A (before snapshot)"))
    rec.responses = [listed, {"success": False, "error": "busy"}]
    assert (await out_of(gephi_mcp.gephi_undo))["success"] is False
    rec.calls.clear()
    after = ws_list(ws(2, "B"), ws(3, "[undo] A (before snapshot)", current=True))
    rec.responses = [listed, {"success": True}, listed, {"success": True}, after, {"success": True}]
    assert (await out_of(gephi_mcp.gephi_undo))["success"]
    assert deleted(rec) == ["0"]


async def test_undo_from_the_snapshot_itself_removes_the_remembered_source(rec):
    """The person opened the "[undo]" workspace by hand. Undo still means the changed
    workspace goes; with no memory of the source nothing is removed."""
    await take_snapshot(rec)
    listed = ws_list(ws(1, "A"), ws(3, "[undo] A (before snapshot)", current=True))
    rec.responses = [listed, {"success": True}, listed, {"success": True}]
    result = await out_of(gephi_mcp.gephi_undo)
    assert result["success"] and deleted(rec) == ["0"]
    assert gephi_mcp._undo_source is None


async def test_undo_from_the_snapshot_itself_with_no_memory_removes_nothing(rec):
    listed = ws_list(ws(1, "A"), ws(3, "[undo] A (before filter)", current=True))
    rec.responses = [listed, {"success": True}]
    result = await out_of(gephi_mcp.gephi_undo)
    assert result["success"] and deleted(rec) == []
    assert "was not removed" in result["note"]


@pytest.mark.parametrize("tool, kwargs", [
    (gephi_mcp.gephi_create_project, {}),
    (gephi_mcp.gephi_open_project, {"file": "/tmp/x.gephi"}),
])
async def test_a_new_project_forgets_the_snapshots_source(rec, tool, kwargs):
    """Workspace ids are per project, so a remembered pair could name an unrelated workspace."""
    await take_snapshot(rec)
    await tool(**kwargs)
    assert gephi_mcp._undo_source is None


async def test_any_status_read_that_sees_no_layout_running_closes_the_open_run(rec):
    """The computed layouts poll the status too. A run they saw end is not stopped later."""
    rec.responses = [{"success": True, "status": "running"}, {"success": True, "running": False}]
    await gephi_mcp.gephi_run_layout("ForceAtlas 2", iterations=5000)
    assert gephi_mcp._open_layout is not None
    await gephi_mcp._layout_status()
    assert gephi_mcp._open_layout is None


def test_every_layout_status_read_goes_through_the_one_helper():
    import inspect
    source = inspect.getsource(gephi_mcp)
    assert source.count('"/layout/status"') == 1
