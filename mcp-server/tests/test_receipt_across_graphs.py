"""The methods record across a session that moves between graphs.

When the graph on screen changes, the record so far is kept as an earlier section, labelled with
what ended it, rather than wiped; a record is never re-attached to a graph. The fake sits at httpx
(from test_ledger_survives_snapshot), because the change of record happens inside
GephiClient.request."""
import asyncio

import pytest
from test_ledger_survives_snapshot import install_fake_gephi

import gephi_mcp
from session_ledger import Ledger


@pytest.fixture(autouse=True)
def fresh_ledger(monkeypatch):
    monkeypatch.setattr(gephi_mcp, "LEDGER", Ledger())


def _record_layout(algorithm="ForceAtlas 2"):
    gephi_mcp.LEDGER.record("run_layout", algorithm=algorithm, iterations=100)


def _receipt():
    return gephi_mcp.LEDGER.receipt()


async def test_switching_workspace_keeps_the_record_as_an_earlier_section(monkeypatch):
    state = install_fake_gephi(monkeypatch)
    state["duplicate"](switch=False)
    _record_layout()

    await gephi_mcp.gephi_switch_workspace(index=1)

    assert _receipt()["layout"] is None, "the record must not describe the other workspace"
    [earlier] = _receipt()["earlier"]
    assert earlier["layout"]["algorithm"] == "ForceAtlas 2"
    assert earlier["ended_by"] == "another workspace was opened"


async def test_switching_back_does_not_reattach_an_old_record(monkeypatch):
    # Gephi numbers workspaces per project and can reuse them, so a record found by workspace id
    # could describe a different graph. The receipt keeps both sections instead.
    state = install_fake_gephi(monkeypatch)
    state["duplicate"](switch=False)
    _record_layout("first")
    await gephi_mcp.gephi_switch_workspace(index=1)
    _record_layout("second")

    await gephi_mcp.gephi_switch_workspace(index=0)

    assert _receipt()["layout"] is None
    assert [e["layout"]["algorithm"] for e in _receipt()["earlier"]] == ["first", "second"]


async def test_a_time_slice_ends_the_record_of_the_full_network(monkeypatch):
    install_fake_gephi(monkeypatch)
    _record_layout()

    await gephi_mcp.gephi.request("POST", "/time/slice", json_data={"start": 1, "end": 2})

    assert _receipt()["layout"] is None
    assert _receipt()["earlier"][0]["ended_by"] == "a time slice was taken"


async def test_a_cancelled_switch_still_leaves_no_stale_record(monkeypatch):
    # Gephi may have switched before the cancellation reached it.
    install_fake_gephi(monkeypatch, faults={"/workspace/switch": asyncio.CancelledError()})
    _record_layout()

    with pytest.raises(asyncio.CancelledError):
        await gephi_mcp.gephi_switch_workspace(index=0)

    assert _receipt()["layout"] is None
    assert _receipt()["earlier"][0]["layout"]["algorithm"] == "ForceAtlas 2"


async def test_renaming_or_saving_keeps_the_record(monkeypatch):
    install_fake_gephi(monkeypatch)
    _record_layout()

    await gephi_mcp.gephi_rename_workspace(index=0, name="Field sites")
    await gephi_mcp.gephi.request("POST", "/project/save", json_data={"file": "/x.gephi"})

    assert _receipt()["layout"]["algorithm"] == "ForceAtlas 2"
    assert _receipt()["earlier"] == []


async def test_an_empty_record_leaves_no_earlier_section(monkeypatch):
    install_fake_gephi(monkeypatch)

    await gephi_mcp.gephi.request("POST", "/graph/clear")

    assert _receipt()["earlier"] == []


def test_only_the_most_recent_earlier_sections_are_kept():
    # Imported here so the file still loads on code without the limit, where the other tests
    # must fail by assertion.
    from session_ledger import EARLIER_KEPT

    ledger = Ledger()
    for i in range(EARLIER_KEPT + 5):
        ledger.record("run_layout", algorithm=f"run {i}")
        ledger.start_new_graph("a file was imported")

    kept = ledger.receipt()["earlier"]
    assert len(kept) == EARLIER_KEPT
    assert kept[-1]["layout"]["algorithm"] == f"run {EARLIER_KEPT + 4}"


async def test_compare_partitions_is_in_the_receipt(monkeypatch):
    nodes = [{"key": str(i), "attributes": {"modularity_class": i % 2, "site": "ab"[i % 2]}}
             for i in range(10)]

    async def read_graph():
        return {"nodes": nodes, "edges": []}

    monkeypatch.setattr(gephi_mcp, "_read_graph", read_graph)

    await gephi_mcp.gephi_compare_partitions(column="modularity_class", against="site")

    [entry] = _receipt()["analyses"]
    assert entry["operation"] == "compare_partitions"
    assert (entry["column"], entry["against"]) == ("modularity_class", "site")
    assert entry["adjusted_rand"] == 1.0
    assert entry["compared"] == 10
