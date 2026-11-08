"""A layout request that Gephi answers with "UI thread is unresponsive" may still start later.

The plugin gives up waiting for Gephi's UI thread after 15 seconds, but the queued layout can run
once the thread frees. Retrying at once would start a second layout on top of it, so the server
adds the guidance to the error.
"""
import json

import gephi_mcp

UI_BUSY = {"success": False,
           "error": "Gephi's UI thread is unresponsive for more than 15 s; the app is likely wedged"}


def _stub(monkeypatch, answer):
    calls = []

    async def request(method, endpoint, params=None, json_data=None, timeout=None):
        calls.append(endpoint)
        return dict(answer) if endpoint == "/layout/run" else {"success": True}

    monkeypatch.setattr(gephi_mcp.gephi, "request", request)
    return calls


async def test_an_unresponsive_ui_thread_error_says_the_layout_may_still_start(monkeypatch):
    _stub(monkeypatch, UI_BUSY)

    out = json.loads(await gephi_mcp.gephi_run_layout(algorithm="ForceAtlas 2"))

    assert out["success"] is False
    assert "UI thread is unresponsive" in out["error"], "the original error must stay"
    guidance = out["guidance"]
    assert "may still start" in guidance
    assert "gephi_get_layout_status" in guidance
    assert "do not retry" in guidance.lower()


async def test_the_guidance_also_comes_with_a_synchronous_run(monkeypatch):
    calls = _stub(monkeypatch, UI_BUSY)

    out = json.loads(await gephi_mcp.gephi_run_layout(algorithm="ForceAtlas 2", sync=True))

    assert "gephi_get_layout_status" in out["guidance"]
    assert "/layout/status" not in calls, "a failed start is not polled"


async def test_a_failed_run_is_not_recorded_in_the_methods_record(monkeypatch):
    _stub(monkeypatch, UI_BUSY)
    monkeypatch.setattr(gephi_mcp, "LEDGER", gephi_mcp.Ledger())

    await gephi_mcp.gephi_run_layout(algorithm="ForceAtlas 2")

    assert gephi_mcp.LEDGER.receipt()["layout"] is None


async def test_other_layout_errors_carry_no_such_guidance(monkeypatch):
    _stub(monkeypatch, {"success": False, "error": "Unknown layout: Nope"})

    out = json.loads(await gephi_mcp.gephi_run_layout(algorithm="Nope"))

    assert "guidance" not in out
