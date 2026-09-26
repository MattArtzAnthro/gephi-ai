"""Hosts send tool calls in parallel against one Gephi. Tools that change the graph, and
gephi_whatif, run one at a time, so a change never lands on a copy that bookkeeping is about to
delete. Read-only tools do not wait. The fake Gephi sits at the httpx layer."""
import asyncio
import inspect
import json

import pytest
from mcp.server import MCPServer
from test_ledger_survives_snapshot import install_fake_gephi

import gephi_mcp

REMOVE_A = [{"op": "remove_node", "id": "a"}]


async def _spin(times=50):
    """Give every ready task many turns. A call that is not held back sends its request within
    two or three of these, so a request still missing after fifty was held back."""
    for _ in range(times):
        await asyncio.sleep(0)


def _paths(state):
    return [path for _, path, _, _ in state["calls"]]


def _held(started, release):
    async def gate():
        started.set()
        await release.wait()
    return gate


async def test_a_graph_change_during_a_whatif_waits_until_it_has_switched_back(monkeypatch):
    editing, release = asyncio.Event(), asyncio.Event()
    landed_on = []
    state = {}

    async def note_current():
        landed_on.extend(w["id"] for w in state["ws"] if w["current"])

    state.update(install_fake_gephi(monkeypatch, gates={
        "/graph/node/a": _held(editing, release), "/appearance/node/color": note_current}))

    async def run():
        whatif = asyncio.ensure_future(gephi_mcp.gephi_whatif(edits=REMOVE_A))
        await editing.wait()
        color = asyncio.ensure_future(gephi_mcp.gephi_set_node_color(id="b", r=1, g=2, b=3))
        await _spin()
        sent_early = "/appearance/node/color" in _paths(state)
        release.set()
        return sent_early, await whatif, await color

    try:
        sent_early, whatif_out, color_out = await asyncio.wait_for(run(), 5)
    finally:
        release.set()
    assert not sent_early, "the styling call reached Gephi while the what-if was on its copy"
    paths = _paths(state)
    color_at = paths.index("/appearance/node/color")
    last_switch = max(i for i, p in enumerate(paths) if p == "/workspace/switch")
    last_delete = max(i for i, p in enumerate(paths) if p == "/workspace/delete")
    assert color_at > last_switch and color_at > last_delete
    assert json.loads(whatif_out)["cleanup"]["scratch_deleted"] is True
    assert json.loads(color_out)["success"] is True
    # The change landed on the person's own workspace, which is still there.
    assert landed_on == [1]
    assert [w["id"] for w in state["ws"]] == [1]


async def test_a_read_during_a_whatif_waits_and_reads_the_original(monkeypatch):
    editing, release = asyncio.Event(), asyncio.Event()
    state = install_fake_gephi(monkeypatch, gates={"/graph/node/a": _held(editing, release)})

    async def run():
        whatif = asyncio.ensure_future(gephi_mcp.gephi_whatif(edits=REMOVE_A))
        await editing.wait()
        read = asyncio.ensure_future(gephi_mcp.gephi_get_graph_stats())
        await _spin()
        read_early = "/graph/stats" in _paths(state)
        release.set()
        return read_early, await whatif, await read

    try:
        read_early, _, stats = await asyncio.wait_for(run(), 5)
    finally:
        release.set()
    assert not read_early, "the read reached Gephi while the what-if was on its scratch copy"
    paths = _paths(state)
    read_at = max(i for i, p in enumerate(paths) if p == "/graph/stats")
    assert read_at > max(i for i, p in enumerate(paths) if p == "/workspace/delete")
    assert json.loads(stats)["workspace_id"] == 1


async def test_a_read_during_a_graph_change_is_not_held_back(monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    install_fake_gephi(monkeypatch, gates={"/appearance/node/color": _held(started, release)})
    change = asyncio.ensure_future(gephi_mcp.gephi_set_node_color(id="a", r=1, g=2, b=3))
    try:
        await asyncio.wait_for(started.wait(), 5)
        # The change is held open until this read returns, so a read that waited for it would
        # never return; the bound turns that into a failure, not a hang.
        stats = await asyncio.wait_for(gephi_mcp.gephi_get_graph_stats(), 1)
    finally:
        release.set()
        await asyncio.wait_for(change, 5)
    assert json.loads(stats)["workspace_id"] == 1


async def test_two_reads_run_together(monkeypatch):
    # Each read's request is held until both reads have sent theirs, so reads that ran one at a
    # time would never finish.
    both_in = asyncio.Event()
    arrived = []

    async def wait_for_the_other():
        arrived.append(1)
        if len(arrived) == 2:
            both_in.set()
        await both_in.wait()

    install_fake_gephi(monkeypatch, gates={"/graph/stats": wait_for_the_other})
    a, b = await asyncio.wait_for(asyncio.gather(
        gephi_mcp.gephi_get_graph_stats(), gephi_mcp.gephi_get_graph_stats()), 1)
    assert json.loads(a)["success"] is True and json.loads(b)["success"] is True


async def test_a_read_tool_called_inside_a_whatif_does_not_wait_on_the_gate(monkeypatch):
    # Stand-ins registered under the real names, so _tool gives them the real wrappers.
    server = MCPServer("nested-read")
    monkeypatch.setattr(gephi_mcp, "mcp", server)

    @gephi_mcp._tool(name="gephi_get_graph_stats")
    async def read() -> str:
        return "read"

    @gephi_mcp._tool(name="gephi_whatif")
    async def whatif() -> str:
        assert not gephi_mcp._read_gate().open.is_set(), "the what-if did not close the gate"
        return "whatif+" + await read()

    result = await asyncio.wait_for(server.call_tool("gephi_whatif", {}), 1)
    assert result.content[0].text == "whatif+read"
    assert gephi_mcp._read_gate().open.is_set()


async def test_a_whatif_cancelled_while_waiting_for_reads_reopens_the_gate(monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    state = install_fake_gephi(monkeypatch, gates={"/graph/stats": _held(started, release)})
    first = asyncio.ensure_future(gephi_mcp.gephi_get_graph_stats())
    try:
        await asyncio.wait_for(started.wait(), 5)
        whatif = asyncio.ensure_future(gephi_mcp.gephi_whatif(edits=REMOVE_A))
        await _spin()
        assert "/workspace/list" not in _paths(state), "the what-if did not wait for the read"
        whatif.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(whatif, 5)
        # A later read is not held back by a gate the cancelled what-if left closed.
        await asyncio.wait_for(gephi_mcp.gephi_get_node(id="a"), 1)
    finally:
        release.set()
        await asyncio.wait_for(first, 5)


async def test_profile_graph_waits_for_a_graph_change(monkeypatch):
    # It writes statistics columns, so it runs alone although it is annotated read-only.
    started, release = asyncio.Event(), asyncio.Event()
    state = install_fake_gephi(monkeypatch, gates={"/appearance/node/color": _held(started, release)})

    async def run():
        change = asyncio.ensure_future(gephi_mcp.gephi_set_node_color(id="a", r=1, g=2, b=3))
        await started.wait()
        sent = len(state["calls"])
        profile = asyncio.ensure_future(gephi_mcp.gephi_profile_graph())
        await _spin()
        sent_early = len(state["calls"]) > sent
        release.set()
        await change
        await profile
        return sent_early

    try:
        sent_early = await asyncio.wait_for(run(), 5)
    finally:
        release.set()
    assert not sent_early, "gephi_profile_graph reached Gephi while a graph change was running"


async def _two_changes_one_after_another(monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    state = install_fake_gephi(monkeypatch, gates={"/appearance/node/color": _held(started, release)})

    async def run():
        first = asyncio.ensure_future(gephi_mcp.gephi_set_node_color(id="a", r=1, g=2, b=3))
        await started.wait()
        second = asyncio.ensure_future(gephi_mcp.gephi_set_node_size(id="a", size=4))
        await _spin()
        sent_early = "/appearance/node/size" in _paths(state)
        release.set()
        return sent_early, await first, await second

    try:
        sent_early, first, second = await asyncio.wait_for(run(), 5)
    finally:
        release.set()
    assert not sent_early, "the second change reached Gephi before the first had finished"
    paths = _paths(state)
    assert paths.index("/appearance/node/size") > paths.index("/appearance/node/color")
    assert json.loads(first)["success"] is True and json.loads(second)["success"] is True


async def test_two_graph_changes_run_one_after_another(monkeypatch):
    await _two_changes_one_after_another(monkeypatch)


def test_the_lock_works_in_each_new_event_loop(monkeypatch):
    # Each test, and each asyncio.run, has its own event loop. A lock made in one loop cannot be
    # waited on in another, so both runs contend for it.
    for _ in range(2):
        asyncio.run(_two_changes_one_after_another(monkeypatch))


async def test_a_tool_that_calls_another_tool_does_not_wait_on_itself(monkeypatch):
    # No shipped tool calls another tool function, so two stand-in tools are registered on a
    # separate server through the same _tool helper.
    server = MCPServer("nested")
    monkeypatch.setattr(gephi_mcp, "mcp", server)
    held_by_inner = []

    @gephi_mcp._tool(name="gephi_test_inner")
    async def inner() -> str:
        held_by_inner.append(gephi_mcp._tool_lock().locked())
        return "inner"

    @gephi_mcp._tool(name="gephi_test_outer")
    async def outer() -> str:
        return "outer+" + await inner()

    result = await asyncio.wait_for(server.call_tool("gephi_test_outer", {}), 1)
    assert result.content[0].text == "outer+inner"
    assert held_by_inner == [True], "the outer call did not hold the lock, so this proved nothing"
    assert not gephi_mcp._tool_lock().locked()


async def test_cancelled_calls_leave_the_lock_free(monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    state = install_fake_gephi(monkeypatch, gates={"/appearance/node/color": _held(started, release)})
    try:
        holder = asyncio.ensure_future(gephi_mcp.gephi_set_node_color(id="a", r=1, g=2, b=3))
        await asyncio.wait_for(started.wait(), 5)
        waiter = asyncio.ensure_future(gephi_mcp.gephi_set_node_size(id="a", size=4))
        await _spin()
        # Cancelled while waiting for the lock.
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(waiter, 5)
        # Cancelled while holding it.
        holder.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(holder, 5)
        assert "/appearance/node/size" not in _paths(state)
        out = await asyncio.wait_for(gephi_mcp.gephi_set_node_size(id="a", size=5), 1)
    finally:
        release.set()
    assert json.loads(out)["success"] is True
    assert not gephi_mcp._tool_lock().locked()


async def test_serializing_keeps_every_tool_listing_as_it_was():
    # The listing each tool would have without the wrapper, built from the unwrapped functions
    # on a separate server, must equal what the server lists.
    registered = gephi_mcp.mcp._tool_manager.list_tools()
    assert len(registered) == 119
    before = MCPServer("before")
    wrapped = set()
    for t in registered:
        original = inspect.unwrap(t.fn)
        if original is not t.fn:
            wrapped.add(t.name)
        before.add_tool(original, name=t.name, title=t.title, annotations=t.annotations,
                        icons=t.icons, meta=t.meta)
    assert wrapped == {t.name for t in registered} - {"gephi_stop_layout", "gephi_stop_statistic"}
    alone = {t.name for t in registered if gephi_mcp._runs_alone(t.name)}
    assert {"gephi_whatif", "gephi_profile_graph", "gephi_set_node_color"} <= alone
    assert "gephi_get_graph_stats" not in alone
    listed = {t.name: t.model_dump(mode="json", by_alias=True)
              for t in await gephi_mcp.mcp.list_tools()}
    expected = {t.name: t.model_dump(mode="json", by_alias=True)
                for t in await before.list_tools()}
    assert listed == expected


async def test_stop_layout_reaches_gephi_while_a_sync_layout_holds_the_lock(monkeypatch):
    waiting, release = asyncio.Event(), asyncio.Event()
    stopped = []

    async def layout_running():
        waiting.set()
        await release.wait()

    state = install_fake_gephi(monkeypatch, faults={"/layout/status": {"success": True,
                                                                       "running": False}},
                               gates={"/layout/status": layout_running})
    layout = asyncio.ensure_future(gephi_mcp.gephi_run_layout(algorithm="ForceAtlas 2", sync=True))
    try:
        await asyncio.wait_for(waiting.wait(), 5)
        # The layout is held until released, so a stop that waited for the lock would never
        # return; the bound turns that into a failure, not a hang.
        out = await asyncio.wait_for(gephi_mcp.gephi_stop_layout(), 1)
        stopped.append(layout.done())
    finally:
        release.set()
        await asyncio.wait_for(layout, 5)
    assert json.loads(out)["success"] is True
    # The stop reached Gephi while the layout's status wait was still held open.
    assert stopped == [False], "the layout call had already ended"
    assert "/layout/stop" in _paths(state)


async def test_stop_statistic_reaches_gephi_while_a_statistic_holds_the_lock(monkeypatch):
    waiting, release = asyncio.Event(), asyncio.Event()

    async def statistic_running():
        waiting.set()
        await release.wait()

    state = install_fake_gephi(monkeypatch, faults={"/statistics/stop": {"success": True,
                                                                         "stopped": ["Betweenness"]}},
                               gates={"/statistics/betweenness": statistic_running})
    run = asyncio.ensure_future(gephi_mcp.gephi_compute_betweenness())
    try:
        await asyncio.wait_for(waiting.wait(), 5)
        out = await asyncio.wait_for(gephi_mcp.gephi_stop_statistic(), 1)
        still_running = not run.done()
    finally:
        release.set()
        await asyncio.wait_for(run, 5)
    assert json.loads(out)["success"] is True
    assert still_running, "the statistic call had already ended"
    assert "/statistics/stop" in _paths(state)


async def test_a_statistic_stopped_from_the_chat_is_stopped_in_gephi(monkeypatch):
    waiting = asyncio.Event()

    async def statistic_running():
        waiting.set()
        await asyncio.Event().wait()

    state = install_fake_gephi(monkeypatch, faults={"/statistics/stop": {"success": True}},
                               gates={"/statistics/run": statistic_running})
    run = asyncio.ensure_future(gephi_mcp.gephi_run_statistic(name="Eccentricity"))
    await asyncio.wait_for(waiting.wait(), 5)
    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run
    await asyncio.wait_for(asyncio.gather(*gephi_mcp._BACKGROUND), 5)
    assert "/statistics/stop" in _paths(state)


async def test_a_cancelled_read_sends_no_stop(monkeypatch):
    waiting = asyncio.Event()

    async def slow_read():
        waiting.set()
        await asyncio.Event().wait()

    state = install_fake_gephi(monkeypatch, gates={"/graph/stats": slow_read})
    run = asyncio.ensure_future(gephi_mcp.gephi.request("GET", "/graph/stats"))
    await asyncio.wait_for(waiting.wait(), 5)
    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run
    await asyncio.sleep(0)
    assert "/statistics/stop" not in _paths(state)


async def test_a_locked_tool_awaited_directly_leaves_the_lock_marker_clear(monkeypatch):
    # Awaited in this task, the wrapper sets the marker in this task's own context, so a reset
    # that did not happen would show here, and every task started from here would skip the lock.
    install_fake_gephi(monkeypatch)
    await asyncio.wait_for(gephi_mcp.gephi_set_node_color(id="a", r=1, g=2, b=3), 5)
    assert gephi_mcp._HOLDS_TOOL_LOCK.get() is False
    await _two_changes_one_after_another(monkeypatch)


async def test_a_read_during_compare_workspaces_waits_and_reads_the_original(monkeypatch):
    # gephi_compare_workspaces switches Gephi to each workspace it reads and back again, so a
    # read sent meanwhile could see the other workspace.
    on_other, release = asyncio.Event(), asyncio.Event()
    state = {}

    async def hold_while_on_the_other():
        if any(w["current"] and w["id"] == 7 for w in state["ws"]):
            on_other.set()
            await release.wait()

    state.update(install_fake_gephi(monkeypatch, gates={"/export/gexf": hold_while_on_the_other}))
    state["ws"].append({"id": 7, "name": "Other", "current": False, "node_count": 5})

    async def run():
        compare = asyncio.ensure_future(gephi_mcp.gephi_compare_workspaces(before=0, after=1))
        await on_other.wait()
        read = asyncio.ensure_future(gephi_mcp.gephi_get_graph_stats())
        await _spin()
        read_early = "/graph/stats" in _paths(state)
        release.set()
        return read_early, await compare, await read

    try:
        read_early, _, stats = await asyncio.wait_for(run(), 5)
    finally:
        release.set()
    assert not read_early, "the read reached Gephi while the compare was on the other workspace"
    assert json.loads(stats)["workspace_id"] == 1


RECEIPTS = {
    "gephi_session_receipt": (lambda: gephi_mcp.gephi_session_receipt(), "/health"),
    "gephi_claim_record": (lambda: gephi_mcp.gephi_claim_record(
        claim="a is central", classification="centrality", verdict="confirmed",
        nodes=["a"]), "/graph/node/get/a"),
}


@pytest.mark.parametrize("tool", RECEIPTS)
async def test_a_receipt_is_not_held_back_by_a_graph_change(monkeypatch, tool):
    # These only read from Gephi, so a long layout or statistic must not queue them.
    started, release = asyncio.Event(), asyncio.Event()
    state = install_fake_gephi(monkeypatch,
                               gates={"/appearance/node/color": _held(started, release)})
    call, path = RECEIPTS[tool]
    change = asyncio.ensure_future(gephi_mcp.gephi_set_node_color(id="a", r=1, g=2, b=3))
    try:
        await asyncio.wait_for(started.wait(), 5)
        await asyncio.wait_for(call(), 1)
    finally:
        release.set()
        await asyncio.wait_for(change, 5)
    assert path in _paths(state)


@pytest.mark.parametrize("tool", RECEIPTS)
async def test_a_receipt_waits_during_a_whatif(monkeypatch, tool):
    editing, release = asyncio.Event(), asyncio.Event()
    state = install_fake_gephi(monkeypatch, gates={"/graph/node/a": _held(editing, release)})
    call, path = RECEIPTS[tool]

    async def run():
        whatif = asyncio.ensure_future(gephi_mcp.gephi_whatif(edits=REMOVE_A))
        await editing.wait()
        receipt = asyncio.ensure_future(call())
        await _spin()
        sent_early = path in _paths(state)
        release.set()
        await whatif
        await receipt
        return sent_early

    try:
        sent_early = await asyncio.wait_for(run(), 5)
    finally:
        release.set()
    assert not sent_early, "the receipt read Gephi while the what-if was on its scratch copy"
    assert _paths(state).index(path) > max(
        i for i, p in enumerate(_paths(state)) if p == "/workspace/delete")


def _no_poll_wait(monkeypatch):
    # The sync layout polls once a second; the fake answers at once, so the wait is dropped.
    real_sleep = asyncio.sleep
    monkeypatch.setattr(asyncio, "sleep", lambda delay, *a, **k: real_sleep(0))


@pytest.mark.parametrize("stop_answer, stopped", [
    ({"success": True, "message": "Layout stopped"}, True),
    ({"success": True, "message": "No layout running"}, False),
], ids=["stopped-a-layout", "nothing-to-stop"])
async def test_a_sync_layout_says_when_it_was_stopped(monkeypatch, stop_answer, stopped):
    # /layout/status only says whether a layout runs, so the layout call learns of the stop
    # from gephi_stop_layout. A stop that found nothing running stopped nothing.
    polling, release = asyncio.Event(), asyncio.Event()
    state = install_fake_gephi(monkeypatch, faults={
        "/layout/status": {"success": True, "running": False}, "/layout/stop": stop_answer},
        gates={"/layout/status": _held(polling, release)})
    _no_poll_wait(monkeypatch)
    gephi_mcp.LEDGER.reset()
    layout = asyncio.ensure_future(
        gephi_mcp.gephi_run_layout(algorithm="ForceAtlas 2", iterations=1000, sync=True))
    try:
        await asyncio.wait_for(polling.wait(), 5)
        await asyncio.wait_for(gephi_mcp.gephi_stop_layout(), 1)
    finally:
        release.set()
    out = json.loads(await asyncio.wait_for(layout, 5))
    assert out["success"] is True
    recorded = gephi_mcp.LEDGER.receipt()["layout"]
    if stopped:
        assert out["status"] == "stopped"
        assert "stopped on request before it finished" in out["message"]
        assert recorded["stopped_before_finishing"] is True
        assert recorded["iterations_requested"] == 1000 and "iterations" not in recorded
    else:
        assert out["status"] == "completed"
        assert out["message"] == "Layout finished after polling"
        assert recorded == {"algorithm": "ForceAtlas 2", "iterations": 1000}
    assert "/layout/stop" in _paths(state)


async def test_a_sync_layout_that_reaches_its_count_is_reported_as_finished(monkeypatch):
    install_fake_gephi(monkeypatch, faults={"/layout/status": {"success": True, "running": False}})
    _no_poll_wait(monkeypatch)
    gephi_mcp.LEDGER.reset()
    out = json.loads(await asyncio.wait_for(
        gephi_mcp.gephi_run_layout(algorithm="ForceAtlas 2", iterations=1000, sync=True), 5))
    assert out["status"] == "completed"
    assert out["message"] == "Layout finished after polling"
    assert gephi_mcp.LEDGER.receipt()["layout"] == {"algorithm": "ForceAtlas 2", "iterations": 1000}
