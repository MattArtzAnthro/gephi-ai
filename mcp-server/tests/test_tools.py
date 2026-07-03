"""
Tests for the Gephi MCP server's tool -> HTTP request mapping.

These exercise the translation layer (MCP tool call -> Gephi HTTP API request)
without needing a running Gephi: gephi_mcp.gephi.request is replaced with a
recorder that captures the method/endpoint/params/body and returns canned JSON.
"""

import json

import pytest

import gephi_mcp


class Recorder:
    """Async stand-in for GephiClient.request that records calls."""

    def __init__(self):
        self.calls = []
        self.responses = []  # optional queue of responses, FIFO

    async def __call__(self, method, endpoint, params=None, json_data=None):
        self.calls.append(
            {"method": method, "endpoint": endpoint, "params": params, "json": json_data}
        )
        if self.responses:
            return self.responses.pop(0)
        return {"success": True}

    @property
    def last(self):
        return self.calls[-1]


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    monkeypatch.setattr(gephi_mcp.gephi, "request", r)
    return r


async def out_of(tool, **kwargs):
    """Invoke a tool with typed kwargs and parse its JSON string result."""
    return json.loads(await tool(**kwargs))


async def test_health_check(rec):
    out = await out_of(gephi_mcp.gephi_health_check)
    assert rec.last["method"] == "GET"
    assert rec.last["endpoint"] == "/health"
    assert out["success"] is True


async def test_create_project_sends_body(rec):
    await out_of(gephi_mcp.gephi_create_project, name="My Graph")
    assert rec.last["method"] == "POST"
    assert rec.last["endpoint"] == "/project/new"
    assert rec.last["json"] == {"name": "My Graph"}


async def test_create_project_default_name(rec):
    await out_of(gephi_mcp.gephi_create_project)
    assert rec.last["json"] == {"name": "New Project"}


async def test_delete_workspace_uses_query_param(rec):
    await out_of(gephi_mcp.gephi_delete_workspace, index=2)
    assert rec.last["method"] == "DELETE"
    assert rec.last["endpoint"] == "/workspace/delete"
    assert rec.last["params"] == {"index": "2"}


async def test_remove_node_embeds_id_in_path(rec):
    await out_of(gephi_mcp.gephi_remove_node, id="n42")
    assert rec.last["method"] == "DELETE"
    assert rec.last["endpoint"] == "/graph/node/n42"


async def test_get_node_embeds_id_in_path(rec):
    await out_of(gephi_mcp.gephi_get_node, id="abc")
    assert rec.last["endpoint"] == "/graph/node/get/abc"


async def test_query_nodes_pagination_defaults(rec):
    await out_of(gephi_mcp.gephi_query_nodes)
    assert rec.last["params"] == {"limit": 100, "offset": 0}


async def test_query_nodes_pagination_overrides(rec):
    await out_of(gephi_mcp.gephi_query_nodes, limit=10, offset=50)
    assert rec.last["params"] == {"limit": 10, "offset": 50}


async def test_get_columns_target(rec):
    await out_of(gephi_mcp.gephi_get_columns, target="edge")
    assert rec.last["endpoint"] == "/graph/columns"
    assert rec.last["params"] == {"target": "edge"}


async def test_add_node_with_attributes(rec):
    await out_of(gephi_mcp.gephi_add_node, id="a", label="A", attributes={"team": "red"})
    assert rec.last["endpoint"] == "/graph/node/add"
    assert rec.last["json"] == {"id": "a", "label": "A", "attributes": {"team": "red"}}


async def test_add_node_drops_omitted_optionals(rec):
    # _body must drop None label/attributes so the plugin's defaults apply
    await out_of(gephi_mcp.gephi_add_node, id="a")
    assert rec.last["json"] == {"id": "a"}


async def test_add_edges_forwards_full_edge_dicts(rec):
    edges = [{"source": "a", "target": "b", "directed": False, "label": "x"}]
    await out_of(gephi_mcp.gephi_add_edges, edges=edges)
    assert rec.last["endpoint"] == "/graph/edges/add"
    assert rec.last["json"]["edges"] == edges


async def test_export_pdf_drops_omitted_dimensions(rec):
    await out_of(gephi_mcp.gephi_export_pdf, file="/tmp/g.pdf")
    assert rec.last["json"] == {"file": "/tmp/g.pdf"}


async def test_run_layout_async_returns_immediately(rec):
    rec.responses = [{"success": True, "status": "running"}]
    out = await out_of(gephi_mcp.gephi_run_layout, algorithm="ForceAtlas2", iterations=100)
    assert [c["endpoint"] for c in rec.calls] == ["/layout/run"]
    assert out["status"] == "running"
    # `sync` must not be forwarded to the plugin.
    assert "sync" not in rec.last["json"]
    assert rec.last["json"] == {"algorithm": "ForceAtlas2", "iterations": 100}


async def test_run_layout_sync_polls_until_done(rec, monkeypatch):
    async def no_sleep(_):
        return None

    monkeypatch.setattr(gephi_mcp.asyncio, "sleep", no_sleep)
    rec.responses = [
        {"success": True, "status": "running"},   # /layout/run
        {"running": True},                          # first poll
        {"running": False},                         # second poll -> done
    ]
    out = await out_of(
        gephi_mcp.gephi_run_layout, algorithm="ForceAtlas2", iterations=50, sync=True
    )
    assert [c["endpoint"] for c in rec.calls] == ["/layout/run", "/layout/status", "/layout/status"]
    assert out["status"] == "completed"


async def test_import_file(rec):
    await out_of(gephi_mcp.gephi_import_file, file="/tmp/graph.gexf")
    assert rec.last["method"] == "POST"
    assert rec.last["endpoint"] == "/import/file"
    assert rec.last["json"] == {"file": "/tmp/graph.gexf"}


def test_all_78_tools_registered():
    """Regression guard: every tool stays registered with its expected name."""
    names = {t.name for t in gephi_mcp.mcp._tool_manager.list_tools()}
    assert len(names) == 78, f"expected 78 tools, found {len(names)}"
    for expected in (
        "gephi_health_check", "gephi_get_node", "gephi_duplicate_workspace",
        "gephi_rename_workspace", "gephi_export_csv", "gephi_compute_modularity",
        "gephi_color_by_ranking", "gephi_filter_by_degree", "gephi_view_graph",
        "gephi_visual_qa",
    ):
        assert expected in names, f"{expected} not registered"


async def test_color_by_ranking_forwards_full_gradient(rec):
    await out_of(
        gephi_mcp.gephi_color_by_ranking, column="degree",
        r_min=0, g_min=0, b_min=0, r_max=255, g_max=255, b_max=255,
    )
    assert rec.last["endpoint"] == "/appearance/ranking/color"
    assert rec.last["json"] == {
        "column": "degree",
        "r_min": 0, "g_min": 0, "b_min": 0,
        "r_max": 255, "g_max": 255, "b_max": 255,
    }


async def test_filter_by_degree_body(rec):
    await out_of(gephi_mcp.gephi_filter_by_degree, min=2, max=10, dry_run=True)
    assert rec.last["endpoint"] == "/filter/degree"
    assert rec.last["json"] == {"min": 2, "max": 10, "dry_run": True}
