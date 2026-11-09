"""The opt-in per-call timing log: GEPHI_AI_TIMING_LOG names a file and every tool call appends
one JSON line to it. Tests run against the fake Gephi (never a real one)."""

from __future__ import annotations

import json
import logging

import httpx
import pytest
from test_ledger_survives_snapshot import install_fake_gephi

import gephi_mcp

BUSY = ("Graph is busy (another task, such as a running statistic, holds the lock); please "
        "retry (1 read holds, write lock free, 1 threads waiting)")


@pytest.fixture
def log(monkeypatch, tmp_path):
    path = tmp_path / "timing.jsonl"
    monkeypatch.setenv("GEPHI_AI_TIMING_LOG", str(path))
    monkeypatch.setattr(gephi_mcp, "_graph_size", None)
    return path


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


async def test_one_line_per_call_with_the_documented_fields(monkeypatch, log):
    install_fake_gephi(monkeypatch, faults={
        "/graph/stats": {"success": True, "node_count": 5, "edge_count": 7}})
    await gephi_mcp.gephi_get_graph_stats()
    (rec,) = lines(log)
    assert set(rec) == {"ts", "tool", "ms", "outcome", "error", "nodes", "edges", "busy", "http"}
    assert rec["tool"] == "gephi_get_graph_stats"
    assert rec["outcome"] == "ok"
    assert rec["error"] is None and rec["busy"] is None
    assert (rec["nodes"], rec["edges"]) == (5, 7)
    assert isinstance(rec["ms"], (int, float)) and rec["ms"] >= 0
    assert rec["ts"].endswith("+00:00") and rec["ts"].startswith("20")


async def test_http_requests_are_listed_with_endpoint_status_and_ms(monkeypatch, log):
    install_fake_gephi(monkeypatch)
    await gephi_mcp.gephi_delete_workspace(index=0)
    (rec,) = lines(log)
    assert [h["endpoint"] for h in rec["http"]] == ["/workspace/list", "/workspace/delete"]
    for h in rec["http"]:
        assert h["status"] == 200
        assert isinstance(h["ms"], (int, float)) and h["ms"] >= 0


async def test_a_failed_http_request_is_listed_with_its_error(monkeypatch, log):
    install_fake_gephi(monkeypatch, faults={"/graph/stats": httpx.ConnectError("no")})
    out = await gephi_mcp.gephi_get_graph_stats()
    assert "Cannot connect" in out
    (rec,) = lines(log)
    assert rec["outcome"] == "error"
    assert "Cannot connect" in rec["error"]
    assert rec["http"][0]["status"] is None
    assert "Cannot connect" in rec["http"][0]["error"]


async def test_an_error_result_is_recorded_as_error_with_its_message(monkeypatch, log):
    install_fake_gephi(monkeypatch, faults={
        "/statistics/degree": {"success": False, "error": "no graph loaded"}})
    out = await gephi_mcp.gephi_compute_degree()
    assert "no graph loaded" in out
    (rec,) = lines(log)
    assert rec["outcome"] == "error" and rec["error"] == "no graph loaded"


async def test_a_raised_exception_is_recorded_and_still_raised(monkeypatch, log):
    async def boom(*args, **kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(gephi_mcp.gephi, "request", boom)
    with pytest.raises(RuntimeError):
        await gephi_mcp.gephi_get_graph_stats()
    (rec,) = lines(log)
    assert rec["outcome"] == "error" and "kaboom" in rec["error"]


@pytest.mark.parametrize("message", [
    BUSY, "modularity is already running; wait for it to finish",
    "Gephi's UI thread is unresponsive"])
async def test_busy_and_lock_text_is_captured(monkeypatch, log, message):
    install_fake_gephi(monkeypatch, faults={
        "/statistics/degree": {"success": False, "error": message}})
    await gephi_mcp.gephi_compute_degree()
    (rec,) = lines(log)
    assert rec["busy"] == message
    if message == BUSY:
        assert rec["busy"].endswith("(1 read holds, write lock free, 1 threads waiting)")


async def test_graph_size_is_remembered_without_another_request(monkeypatch, log):
    state = install_fake_gephi(monkeypatch, faults={
        "/graph/stats": {"success": True, "node_count": 12, "edge_count": 30}})
    await gephi_mcp.gephi_get_graph_stats()
    before = len(state["calls"])
    await gephi_mcp.gephi_get_graph_type()  # a read that carries no counts of its own
    assert len(state["calls"]) == before + 1  # its own request only, none to learn the size
    first, second = lines(log)
    assert (second["nodes"], second["edges"]) == (12, 30)
    assert first["nodes"] == 12


async def test_size_is_null_when_unknown_and_forgotten_when_the_graph_changes(monkeypatch, log):
    install_fake_gephi(monkeypatch, faults={
        "/graph/stats": {"success": True, "node_count": 12, "edge_count": 30}})
    await gephi_mcp.gephi_get_graph_type()
    await gephi_mcp.gephi_get_graph_stats()
    await gephi_mcp.gephi_clear_graph()
    await gephi_mcp.gephi_get_graph_type()
    unknown, known, _, forgotten = lines(log)
    assert unknown["nodes"] is None and unknown["edges"] is None
    assert known["nodes"] == 12
    assert forgotten["nodes"] is None


async def test_nothing_is_written_when_the_variable_is_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("GEPHI_AI_TIMING_LOG", raising=False)
    monkeypatch.chdir(tmp_path)
    install_fake_gephi(monkeypatch)
    await gephi_mcp.gephi_get_graph_stats()
    assert list(tmp_path.iterdir()) == []


async def test_an_unwritable_path_warns_once_and_never_changes_the_result(
        monkeypatch, tmp_path, caplog, capsys):
    install_fake_gephi(monkeypatch)
    plain = await _result_without_log(monkeypatch)
    monkeypatch.setenv("GEPHI_AI_TIMING_LOG", str(tmp_path / "missing-dir" / "t.jsonl"))
    monkeypatch.setattr(gephi_mcp, "_timing_warned", set())
    caplog.set_level(logging.WARNING)
    out1 = await gephi_mcp.gephi_get_graph_stats()
    out2 = await gephi_mcp.gephi_get_graph_stats()
    assert out1 == out2 == plain
    warnings = [r for r in caplog.records if "timing log" in r.getMessage()]
    assert len(warnings) == 1
    assert capsys.readouterr().out == ""


async def _result_without_log(monkeypatch):
    monkeypatch.delenv("GEPHI_AI_TIMING_LOG", raising=False)
    return await gephi_mcp.gephi_get_graph_stats()


async def test_a_tool_called_inside_another_is_not_logged_twice(monkeypatch, log):
    async def inner():
        return "{}"

    async def outer():
        return await gephi_mcp._timed("inner", inner)()

    await gephi_mcp._timed("outer", outer)()
    assert [r["tool"] for r in lines(log)] == ["outer"]


# A failed call's message can quote the user's data (node labels, column names, file paths), so the
# log keeps only its start, as it already did for plugin request errors.
LONG = "Node 'Participant " + "x" * 400 + "' not found"


async def test_a_long_error_result_is_cut_to_200_characters(monkeypatch, log):
    install_fake_gephi(monkeypatch, faults={"/statistics/degree": {"success": False, "error": LONG}})
    out = await gephi_mcp.gephi_compute_degree()
    assert LONG in out, "the tool's own result is never shortened"
    (rec,) = lines(log)
    assert rec["outcome"] == "error" and len(rec["error"]) <= 200
    assert rec["error"].startswith("Node 'Participant")


async def test_a_long_raised_exception_is_cut_to_200_characters(monkeypatch, log):
    async def boom(*args, **kwargs):
        raise RuntimeError(LONG)

    monkeypatch.setattr(gephi_mcp.gephi, "request", boom)
    with pytest.raises(RuntimeError, match="Participant"):
        await gephi_mcp.gephi_get_graph_stats()
    (rec,) = lines(log)
    assert rec["outcome"] == "error" and len(rec["error"]) <= 200
