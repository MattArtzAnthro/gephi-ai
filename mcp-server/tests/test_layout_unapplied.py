"""A layout setting Gephi does not recognise must reach the caller, not vanish.

The plugin reports keys that matched no layout property as unapplied_params with a warning.
A synchronous run adds its own status to that response; the warning has to survive it.
"""

import json

import gephi_mcp


async def test_a_sync_layout_run_keeps_the_unapplied_settings_warning(monkeypatch):
    responses = [
        {"success": True, "layout": "ForceAtlas 2", "status": "running",
         "unapplied_params": ["barnesHutOptimize"],
         "warning": "These settings match no property of ForceAtlas 2 and were NOT applied"},
        {"success": True, "running": False},
    ]

    async def fake(method, endpoint, params=None, json_data=None, timeout=None):
        if endpoint in ("/layout/run", "/layout/status"):
            return responses.pop(0)
        return {"success": True, "nodes": []}

    async def no_sleep(_):
        return None

    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    monkeypatch.setattr(gephi_mcp.asyncio, "sleep", no_sleep)

    out = json.loads(await gephi_mcp.gephi_run_layout(
        "ForceAtlas 2", iterations=10, properties={"barnesHutOptimize": True}, sync=True))

    assert out["status"] == "completed"
    assert out["unapplied_params"] == ["barnesHutOptimize"]
    assert "NOT applied" in out["warning"]
