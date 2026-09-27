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

    async def __call__(self, method, endpoint, params=None, json_data=None, timeout=None):
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
    # the trailing /export/gexf is the finite-positions guard
    assert [c["endpoint"] for c in rec.calls] == [
        "/layout/run", "/layout/status", "/layout/status", "/export/gexf"]
    assert out["status"] == "completed"


async def test_import_file(rec):
    await out_of(gephi_mcp.gephi_import_file, file="/tmp/graph.gexf")
    assert rec.last["method"] == "POST"
    assert rec.last["endpoint"] == "/import/file"
    assert rec.last["json"] == {"file": "/tmp/graph.gexf"}


async def test_export_screenshot_sends_body(rec):
    await out_of(gephi_mcp.gephi_export_screenshot, file="/tmp/shot.png")
    assert rec.last["method"] == "POST"
    assert rec.last["endpoint"] == "/export/screenshot"
    assert rec.last["json"] == {
        "file": "/tmp/shot.png", "scale": 2, "transparent_background": False,
    }


async def test_export_screenshot_overrides(rec):
    await out_of(
        gephi_mcp.gephi_export_screenshot,
        file="/tmp/shot.png", scale=3, transparent_background=True,
    )
    assert rec.last["json"] == {
        "file": "/tmp/shot.png", "scale": 3, "transparent_background": True,
    }


def test_all_120_tools_registered():
    """Regression guard: every tool stays registered with its expected name."""
    names = {t.name for t in gephi_mcp.mcp._tool_manager.list_tools()}
    assert len(names) == 120, f"expected 120 tools, found {len(names)}"
    for expected in (
        "gephi_health_check", "gephi_get_node", "gephi_duplicate_workspace",
        "gephi_rename_workspace", "gephi_export_csv", "gephi_compute_modularity",
        "gephi_color_by_ranking", "gephi_filter_by_degree", "gephi_view_graph",
        "gephi_visual_qa", "gephi_label_clusters", "gephi_focus_view",
        "gephi_extract_backbone", "gephi_whatif", "gephi_compare_nodes",
        "gephi_set_selection_mode", "gephi_get_perspective", "gephi_switch_perspective",
        "gephi_list_filters", "gephi_apply_filter", "gephi_column_value_frequencies",
        "gephi_detect_duplicates", "gephi_merge_nodes", "gephi_create_regex_column",
        "gephi_color_edges_by_partition", "gephi_export",
        "gephi_get_timeline", "gephi_snapshot", "gephi_undo",
        "gephi_export_screenshot", "gephi_community_stability", "gephi_export_legend", "gephi_session_receipt", "gephi_compare_workspaces", "gephi_compare_partitions", "gephi_bipartite_layout", "gephi_bipartite_projection",
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


async def test_profile_graph_flow(rec, monkeypatch):
    ring = """<?xml version='1.0'?><gexf xmlns="http://gexf.net/1.3"><graph defaultedgetype="undirected">
    <nodes>""" + "".join(f'<node id="n{i}" label="n{i}"/>' for i in range(8)) + "</nodes><edges>" + \
        "".join(f'<edge id="e{i}" source="n{i}" target="n{(i+1) % 8}"/>' for i in range(8)) + \
        "</edges></graph></gexf>"
    async def fake(method, endpoint, params=None, json_data=None, timeout=None):
        if endpoint == "/export/gexf":
            return {"success": True, "content": ring}
        if endpoint == "/statistics/modularity":
            return {"success": True, "modularity": 0.41, "communities": 3}
        return {"success": True, "average_clustering_coefficient": 0.0}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    out = await gephi_mcp.gephi_profile_graph()
    assert '"nodes": 8' in out and '"modularity": 0.41' in out
    assert '"giant_share": 1.0' in out


async def test_similarity_layout_flow(rec, monkeypatch):
    ring = """<?xml version='1.0'?><gexf xmlns="http://gexf.net/1.3"><graph defaultedgetype="undirected">
    <nodes>""" + "".join(f'<node id="n{i}" label="n{i}"/>' for i in range(8)) + "</nodes><edges>" + \
        "".join(f'<edge id="e{i}" source="n{i}" target="n{(i+1) % 8}"/>' for i in range(8)) + \
        "</edges></graph></gexf>"
    calls = []
    async def fake(method, endpoint, params=None, json_data=None, timeout=None):
        calls.append((endpoint, json_data))
        if endpoint == "/export/gexf":
            return {"success": True, "content": ring}
        if endpoint == "/layout/status":
            return {"success": True, "running": False}
        return {"success": True}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    out = await gephi_mcp.gephi_similarity_layout(projection="spectral")
    assert '"success": true' in out and '"projection_used": "spectral"' in out
    pushed = next(j for e, j in calls if e == "/graph/nodes/positions")
    assert len(pushed["positions"]) == 8
    assert any(e == "/view/focus" for e, _ in calls)


async def test_statistics_passthrough(rec):
    await out_of(gephi_mcp.gephi_list_statistics)
    assert rec.last["endpoint"] == "/statistics/available"
    await out_of(gephi_mcp.gephi_run_statistic, name="Leiden")
    assert rec.last["endpoint"] == "/statistics/run"
    assert rec.last["json"] == {"name": "Leiden"}
    await out_of(gephi_mcp.gephi_run_statistic, name="PageRank", params={"epsilon": 0.001})
    assert rec.last["json"] == {"name": "PageRank", "params": {"epsilon": 0.001}}


async def test_export_gexf_inline_and_file(rec):
    await out_of(gephi_mcp.gephi_export_gexf)
    assert rec.last["endpoint"] == "/export/gexf"
    assert rec.last["json"] == {"inline": True}
    await out_of(gephi_mcp.gephi_export_gexf, file="/tmp/g.gexf")
    assert rec.last["json"] == {"file": "/tmp/g.gexf"}


async def test_focus_view_modes(rec):
    await out_of(gephi_mcp.gephi_focus_view, mode="node", id="n5")
    assert rec.last["endpoint"] == "/view/focus"
    assert rec.last["json"] == {"mode": "node", "id": "n5"}
    await out_of(gephi_mcp.gephi_focus_view, mode="region", x=0, y=0, w=100, h=80, zoom=1.5)
    assert rec.last["json"] == {"mode": "region", "x": 0, "y": 0, "w": 100, "h": 80, "zoom": 1.5}
    await out_of(gephi_mcp.gephi_focus_view, select=["a", "b"])
    assert rec.last["json"] == {"mode": "graph", "select": ["a", "b"]}


async def test_text_to_network_adds_nodes_then_edges(rec):
    out = await out_of(gephi_mcp.gephi_text_to_network, text="the dog chased the cat")
    assert rec.calls[0]["endpoint"] == "/graph/nodes/add"
    assert rec.calls[1]["endpoint"] == "/graph/edges/add"
    node_ids = {n["id"] for n in rec.calls[0]["json"]["nodes"]}
    # "chased" lemmatizes to "chase" when NLTK's data is available locally;
    # accept either so this test doesn't depend on that being installed.
    assert node_ids in ({"dog", "chased", "cat"}, {"dog", "chase", "cat"})
    assert out["success"] is True
    assert out["stats"]["unique_words"] == 3


async def test_text_to_network_clears_graph_first_when_requested(rec):
    await out_of(gephi_mcp.gephi_text_to_network, text="dog cat", clear_existing=True)
    # clear_existing triggers an undo-snapshot attempt first (just a
    # /workspace/list probe here — the canned response has no workspaces).
    assert rec.calls[0]["endpoint"] == "/workspace/list"
    assert rec.calls[1]["endpoint"] == "/graph/clear"
    assert rec.calls[2]["endpoint"] == "/graph/nodes/add"
    assert rec.calls[3]["endpoint"] == "/graph/edges/add"


async def test_text_to_network_stops_if_clear_fails(rec):
    rec.responses.append({"success": False, "error": "no workspaces"})   # snapshot probe
    rec.responses.append({"success": False, "error": "not connected"})   # clear fails
    out = await out_of(gephi_mcp.gephi_text_to_network, text="dog cat", clear_existing=True)
    assert len(rec.calls) == 2  # never reached nodes/add
    assert out["success"] is False


async def test_text_to_network_rejects_all_stopword_text(rec):
    out = await out_of(gephi_mcp.gephi_text_to_network, text="the a an")
    assert out["success"] is False
    assert rec.calls == []  # never called Gephi at all


async def test_text_to_network_passes_through_pos_filter_and_min_frequency(rec):
    out = await out_of(
        gephi_mcp.gephi_text_to_network,
        text=["dog cat dog", "dog bird"],
        pos_filter=None,
        min_word_frequency=2,
    )
    node_ids = {n["id"] for n in rec.calls[0]["json"]["nodes"]}
    assert node_ids == {"dog"}  # cat and bird each occur once, below the floor
    assert out["stats"]["document_count"] == 2


async def test_text_to_network_passes_through_merge_phrases(rec):
    out = await out_of(
        gephi_mcp.gephi_text_to_network,
        text="dog cat bird",
        merge_phrases=False,
    )
    assert out["stats"]["phrases_detected"] == 0


async def test_extract_backbone_fetches_edges_prunes_and_reports_stats(rec):
    rec.responses.append({
        "success": True,
        "edges": [
            {"source": "a", "target": "b", "weight": 10.0},
            {"source": "a", "target": "d", "weight": 1.0},
        ],
    })
    out = await out_of(gephi_mcp.gephi_extract_backbone, alpha=0.05)
    assert rec.calls[0]["method"] == "GET"
    assert rec.calls[0]["endpoint"] == "/graph/edges"
    assert out["success"] is True
    # both edges are each some node's only edge (degree 1 on b and d), so
    # both survive the disparity filter — nothing to remove here.
    assert out["stats"]["edges_removed"] == 0
    assert out["edges_removed_from_graph"] == 0


async def test_extract_backbone_reports_failure_with_no_edges(rec):
    rec.responses.append({"success": True, "edges": []})
    out = await out_of(gephi_mcp.gephi_extract_backbone)
    assert out["success"] is False


# ─── gephi_whatif + gephi_compare_nodes ───────────────────────────────

class RoutingClient:
    """Stateful fake for the workspace lifecycle whatif drives.

    Simulates the project's workspace list: duplicate appends a new current
    workspace, switch moves the current flag by index, delete removes by index.
    Records every call so tests can assert edit dispatch. Everything else
    (edit endpoints) returns success. This models real index-shifting so the
    id-correlated cleanup is exercised for real, not stubbed."""

    def __init__(self, workspaces):
        self.workspaces = workspaces  # list of {id, current}
        self.calls = []
        self.next_id = max((w["id"] for w in workspaces), default=0) + 1

    async def __call__(self, method, endpoint, params=None, json_data=None, timeout=None):
        self.calls.append({"method": method, "endpoint": endpoint, "params": params, "json": json_data})
        if endpoint == "/workspace/list":
            return {"success": True, "workspaces": [dict(w) for w in self.workspaces]}
        if endpoint == "/workspace/duplicate":
            for w in self.workspaces:
                w["current"] = False
            wid = self.next_id
            self.next_id += 1
            self.workspaces.append({"id": wid, "name": f"ws{wid}", "current": True})
            return {"success": True, "workspace_id": wid}
        if endpoint == "/workspace/switch":
            idx = json_data["index"]
            for i, w in enumerate(self.workspaces):
                w["current"] = (i == idx)
            return {"success": True}
        if endpoint == "/workspace/delete":
            del self.workspaces[int(params["index"])]
            return {"success": True}
        return {"success": True}


def _fake_profiles(monkeypatch, *profiles):
    """Make _compute_profile return the given dicts in order (no real GEXF)."""
    queue = list(profiles)

    async def fake(include_slow=False):
        return queue.pop(0)

    monkeypatch.setattr(gephi_mcp, "_compute_profile", fake)


async def test_whatif_happy_path_diffs_and_cleans_up(monkeypatch):
    client = RoutingClient([{"id": 1, "name": "Workspace 1", "current": True}])
    monkeypatch.setattr(gephi_mcp.gephi, "request", client)
    _fake_profiles(
        monkeypatch,
        {"nodes": 10, "edges": 20, "components": {"count": 1}},
        {"nodes": 9, "edges": 18, "components": {"count": 2}},
    )
    out = await out_of(gephi_mcp.gephi_whatif, edits=[{"op": "remove_node", "id": "X"}])
    assert out["success"] is True
    diff = {d["metric"]: d for d in out["diff"]}
    assert diff["nodes"] == {"metric": "nodes", "before": 10, "after": 9, "delta": -1}
    assert diff["edges"]["delta"] == -2
    assert diff["components"]["before"] == 1 and diff["components"]["after"] == 2
    # scratch removed, original restored as current
    assert client.workspaces == [{"id": 1, "name": "Workspace 1", "current": True}]
    assert out["cleanup"]["scratch_deleted"] is True
    assert out["cleanup"]["returned_to_workspace_id"] == 1
    # the edit was dispatched to the scratch copy
    assert any(c["method"] == "DELETE" and c["endpoint"] == "/graph/node/X" for c in client.calls)


async def test_whatif_dispatches_each_edit_op(monkeypatch):
    client = RoutingClient([{"id": 1, "current": True}])
    monkeypatch.setattr(gephi_mcp.gephi, "request", client)
    _fake_profiles(monkeypatch, {"nodes": 5}, {"nodes": 5})
    await out_of(gephi_mcp.gephi_whatif, edits=[
        {"op": "remove_node", "id": "n1"},
        {"op": "remove_nodes", "ids": ["n2", "n3"]},
        {"op": "add_edge", "source": "a", "target": "b", "weight": 2.0, "directed": True},
        {"op": "remove_edge", "source": "c", "target": "d"},
    ])
    eps = [(c["method"], c["endpoint"], c["json"]) for c in client.calls]
    assert ("DELETE", "/graph/node/n1", None) in eps
    assert ("POST", "/graph/nodes/remove", {"ids": ["n2", "n3"]}) in eps
    assert ("POST", "/graph/edges/add", {"edges": [{"source": "a", "target": "b", "weight": 2.0, "directed": True}]}) in eps
    assert ("POST", "/graph/edge/remove", {"source": "c", "target": "d"}) in eps


async def test_whatif_cleans_up_when_edit_fails(monkeypatch):
    client = RoutingClient([{"id": 1, "current": True}])
    monkeypatch.setattr(gephi_mcp.gephi, "request", client)
    _fake_profiles(monkeypatch, {"nodes": 5}, {"nodes": 5})
    out = await out_of(gephi_mcp.gephi_whatif, edits=[{"op": "teleport", "id": "z"}])
    assert out["success"] is False
    assert out["stage"] == "edit"
    # even on failure, scratch is gone and original is current again
    assert client.workspaces == [{"id": 1, "current": True}]
    assert out["cleanup"]["scratch_deleted"] is True


async def test_whatif_errors_when_no_current_workspace(monkeypatch):
    client = RoutingClient([{"id": 1, "current": False}])
    monkeypatch.setattr(gephi_mcp.gephi, "request", client)
    out = await out_of(gephi_mcp.gephi_whatif, edits=[{"op": "remove_node", "id": "X"}])
    assert out["success"] is False
    # never duplicated anything
    assert not any(c["endpoint"] == "/workspace/duplicate" for c in client.calls)


async def test_compare_nodes_reads_attribute_metric(rec):
    rec.responses.append({"success": True, "node": {"id": "a", "attributes": {"Betweenness Centrality": 22012.7}}})
    rec.responses.append({"success": True, "node": {"id": "b", "attributes": {"Betweenness Centrality": 15.0}}})
    out = await out_of(gephi_mcp.gephi_compare_nodes, id_a="a", id_b="b", metric="Betweenness Centrality")
    assert out["a"] == 22012.7
    assert out["b"] == 15.0
    assert out["higher"] == "a"
    assert out["difference"] == 22012.7 - 15.0


async def test_compare_nodes_falls_back_to_top_level_field(rec):
    rec.responses.append({"success": True, "node": {"id": "a", "size": 45.0, "attributes": {}}})
    rec.responses.append({"success": True, "node": {"id": "b", "size": 12.0, "attributes": {}}})
    out = await out_of(gephi_mcp.gephi_compare_nodes, id_a="a", id_b="b", metric="size")
    assert out["higher"] == "a"


async def test_compare_nodes_handles_tie(rec):
    rec.responses.append({"success": True, "node": {"id": "a", "attributes": {"degree": 5}}})
    rec.responses.append({"success": True, "node": {"id": "b", "attributes": {"degree": 5}}})
    out = await out_of(gephi_mcp.gephi_compare_nodes, id_a="a", id_b="b", metric="degree")
    assert out["higher"] is None
    assert out["difference"] == 0


async def test_compare_nodes_errors_when_metric_absent(rec):
    rec.responses.append({"success": True, "node": {"id": "a", "attributes": {"degree": 5}}})
    rec.responses.append({"success": True, "node": {"id": "b", "attributes": {"degree": 3}}})
    out = await out_of(gephi_mcp.gephi_compare_nodes, id_a="a", id_b="b", metric="pageranks")
    assert out["success"] is False
    assert "pageranks" in out["error"]


# ─── Group B: selection mode + perspective ────────────────────────────

async def test_set_selection_mode_defaults_to_rectangle(rec):
    await out_of(gephi_mcp.gephi_set_selection_mode)
    assert rec.last["method"] == "POST"
    assert rec.last["endpoint"] == "/view/selection"
    assert rec.last["json"] == {"mode": "rectangle"}


async def test_set_selection_mode_forwards_mode(rec):
    await out_of(gephi_mcp.gephi_set_selection_mode, mode="direct")
    assert rec.last["json"] == {"mode": "direct"}


async def test_get_perspective_is_a_get(rec):
    await out_of(gephi_mcp.gephi_get_perspective)
    assert rec.last["method"] == "GET"
    assert rec.last["endpoint"] == "/perspective"


async def test_switch_perspective_sends_name(rec):
    await out_of(gephi_mcp.gephi_switch_perspective, name="Data Laboratory")
    assert rec.last["method"] == "POST"
    assert rec.last["endpoint"] == "/perspective/switch"
    assert rec.last["json"] == {"name": "Data Laboratory"}


# ─── Group C: filters ─────────────────────────────────────────────────

async def test_list_filters_is_a_get(rec):
    await out_of(gephi_mcp.gephi_list_filters)
    assert rec.last["method"] == "GET"
    assert rec.last["endpoint"] == "/filter/list"


async def test_apply_filter_defaults_action_select(rec):
    await out_of(gephi_mcp.gephi_apply_filter, name="Degree Range", params={"Degree Range": [2, 10]})
    assert rec.last["method"] == "POST"
    assert rec.last["endpoint"] == "/filter/apply"
    assert rec.last["json"] == {"name": "Degree Range", "params": {"Degree Range": [2, 10]}, "action": "select"}


async def test_apply_filter_new_workspace_action(rec):
    await out_of(gephi_mcp.gephi_apply_filter, name="K-core", params={"k": 3}, action="new_workspace")
    assert rec.last["json"]["action"] == "new_workspace"


async def test_apply_filter_column_action_includes_column(rec):
    await out_of(gephi_mcp.gephi_apply_filter, name="Giant Component", action="column", column="in_giant")
    assert rec.last["json"] == {"name": "Giant Component", "action": "column", "column": "in_giant"}


# ─── Group D: data laboratory ─────────────────────────────────────────

async def test_column_value_frequencies_body(rec):
    await out_of(gephi_mcp.gephi_column_value_frequencies, column="team")
    assert rec.last["method"] == "POST"
    assert rec.last["endpoint"] == "/datalab/frequencies"
    assert rec.last["json"] == {"target": "node", "column": "team"}


async def test_detect_duplicates_forwards_case_flag(rec):
    await out_of(gephi_mcp.gephi_detect_duplicates, column="email", case_sensitive=True)
    assert rec.last["endpoint"] == "/datalab/duplicates"
    assert rec.last["json"] == {"target": "node", "column": "email", "case_sensitive": True}


async def test_merge_nodes_sends_ids_and_into(rec):
    await out_of(gephi_mcp.gephi_merge_nodes, ids=["a", "b", "c"], into="a")
    assert rec.last["endpoint"] == "/datalab/merge-nodes"
    assert rec.last["json"] == {"ids": ["a", "b", "c"], "into": "a"}


async def test_create_regex_column_body(rec):
    await out_of(gephi_mcp.gephi_create_regex_column,
                 column="label", new_column="is_dept", regex="^Dept-")
    assert rec.last["endpoint"] == "/datalab/regex-column"
    assert rec.last["json"] == {"target": "node", "column": "label",
                                "new_column": "is_dept", "regex": "^Dept-"}


# ─── Group E: edge appearance + export formats ────────────────────────

async def test_color_edges_by_partition_default(rec):
    await out_of(gephi_mcp.gephi_color_edges_by_partition, column="rel_type")
    assert rec.last["method"] == "POST"
    assert rec.last["endpoint"] == "/appearance/edge/partition-color"
    assert rec.last["json"] == {"column": "rel_type"}


async def test_color_edges_by_partition_with_colors(rec):
    await out_of(gephi_mcp.gephi_color_edges_by_partition, column="rel_type",
                 colors={"cites": [255, 0, 0], "coauthor": [0, 0, 255]})
    assert rec.last["json"]["colors"] == {"cites": [255, 0, 0], "coauthor": [0, 0, 255]}


async def test_export_format_body(rec):
    await out_of(gephi_mcp.gephi_export, file="/tmp/g.vna", format="vna")
    assert rec.last["method"] == "POST"
    assert rec.last["endpoint"] == "/export/format"
    assert rec.last["json"] == {"file": "/tmp/g.vna", "format": "vna"}


# ─── Group F: typed parallel edges ────────────────────────────────────

async def test_add_edge_without_type_omits_edge_type(rec):
    await out_of(gephi_mcp.gephi_add_edge, source="a", target="b")
    assert rec.last["endpoint"] == "/graph/edge/add"
    assert "edge_type" not in rec.last["json"]
    assert rec.last["json"] == {"source": "a", "target": "b", "weight": 1.0, "directed": True}


async def test_add_edge_forwards_edge_type(rec):
    await out_of(gephi_mcp.gephi_add_edge, source="a", target="b", edge_type="cites")
    assert rec.last["json"]["edge_type"] == "cites"


async def test_add_edges_forwards_edge_type_in_dicts(rec):
    edges = [{"source": "a", "target": "b", "edge_type": "coauthor"}]
    await out_of(gephi_mcp.gephi_add_edges, edges=edges)
    assert rec.last["json"]["edges"][0]["edge_type"] == "coauthor"


# ─── Group G: timeline ────────────────────────────────────────────────

async def test_get_timeline_is_a_get(rec):
    await out_of(gephi_mcp.gephi_get_timeline)
    assert rec.last["method"] == "GET"
    assert rec.last["endpoint"] == "/timeline"


def test_server_reports_package_version():
    """serverInfo.version on the wire must be the installed package version, not empty."""
    import importlib.metadata
    assert gephi_mcp.mcp.version == importlib.metadata.version("gephi-ai")
    assert gephi_mcp.mcp.version != ""


async def test_import_file_mode_and_cap(rec):
    await out_of(gephi_mcp.gephi_import_file, file="/tmp/g.gexf", mode="append", max_node_size=30)
    assert rec.last["json"] == {"file": "/tmp/g.gexf", "mode": "append", "max_node_size": 30}


async def test_import_gexf_passes_mode(rec):
    await out_of(gephi_mcp.gephi_import_gexf, file="/tmp/g.gexf", mode="append")
    assert rec.last["endpoint"] == "/import/gexf"
    assert rec.last["json"] == {"file": "/tmp/g.gexf", "mode": "append"}


async def test_query_nodes_value_search(rec):
    await out_of(gephi_mcp.gephi_query_nodes, column="Country", value="Peru", min=1.0, limit=5)
    assert rec.last["params"] == {"limit": 5, "offset": 0, "column": "Country", "value": "Peru",
                                  "min": 1.0}


async def test_apply_filters_body(rec):
    specs = [{"name": "Degree Range", "params": {"range": [2, 9]}},
             {"name": "Equal: group String (Node)", "params": {"pattern": "a"}, "exclude": True}]
    await out_of(gephi_mcp.gephi_apply_filters, filters=specs, combine="any", dry_run=True)
    assert rec.last["endpoint"] == "/filter/combine"
    assert rec.last["json"] == {"filters": specs, "combine": "any", "action": "select",
                                "dry_run": True}


async def test_apply_filter_dry_run_only_counts(rec, monkeypatch):
    async def no_snapshot(op):
        raise AssertionError("a dry run must not take an undo snapshot")
    monkeypatch.setattr(gephi_mcp, "_auto_snapshot", no_snapshot)
    await out_of(gephi_mcp.gephi_apply_filter, name="Degree Range", params={"range": [2, 9]},
                 dry_run=True)
    assert rec.last["endpoint"] == "/filter/combine"
    assert rec.last["json"]["dry_run"] is True
    assert rec.last["json"]["filters"] == [{"name": "Degree Range", "params": {"range": [2, 9]}}]


async def test_time_slice_body(rec):
    await out_of(gephi_mcp.gephi_time_slice, start=1990, end=1995)
    assert rec.last["endpoint"] == "/time/slice"
    assert rec.last["json"] == {"start": 1990, "end": 1995}


async def test_shortest_path_body(rec):
    await out_of(gephi_mcp.gephi_find_shortest_path, source="a", target="b", weighting="strength",
                 follow_direction=False, mark_column="on_path")
    assert rec.last["endpoint"] == "/graph/shortest-path"
    assert rec.last["json"] == {"source": "a", "target": "b", "weighting": "strength",
                                "follow_direction": False, "mark_column": "on_path"}


async def test_stop_statistic_endpoint(rec):
    await out_of(gephi_mcp.gephi_stop_statistic)
    assert (rec.last["method"], rec.last["endpoint"]) == ("POST", "/statistics/stop")


async def test_a_refused_edit_takes_no_snapshot(rec, monkeypatch):
    snapshots = []

    async def snapshot(op):
        snapshots.append(op)
        return True
    monkeypatch.setattr(gephi_mcp, "_auto_snapshot", snapshot)
    rec.responses = [{"success": False, "error": "Gephi keeps the 'Label' column"}]

    out = await out_of(gephi_mcp.gephi_edit_column, column="Label", action="delete")

    assert out["success"] is False
    assert snapshots == [], "a refused edit replaced the undo point"
    assert rec.calls[-1]["json"]["check_only"] is True
    assert len(rec.calls) == 1


async def test_an_accepted_edit_is_checked_then_snapshotted_then_made(rec, monkeypatch):
    order = []

    async def snapshot(op):
        order.append("snapshot")
        return True
    monkeypatch.setattr(gephi_mcp, "_auto_snapshot", snapshot)

    out = await out_of(gephi_mcp.gephi_set_time_from_columns, start="year")

    assert [c["json"].get("check_only", False) for c in rec.calls] == [True, False]
    assert order == ["snapshot"]
    assert out["undo_available"] is True


async def test_size_by_ranking_sends_a_cap_only_when_given(rec):
    await out_of(gephi_mcp.gephi_size_by_ranking, column="degree")
    assert "cap" not in rec.last["json"]
    await out_of(gephi_mcp.gephi_size_by_ranking, column="degree", cap=30)
    assert rec.last["json"]["cap"] == 30


async def test_a_capped_size_mapping_reaches_the_legend(rec):
    gephi_mcp.LEDGER.reset()
    await out_of(gephi_mcp.gephi_size_by_ranking, column="degree", cap=30)
    item = gephi_mcp.LEDGER.legend_items()[-1]
    assert item["channel"] == "node size" and item["cap"] == 30


async def test_eigenvector_runs_long_enough_to_converge_by_default(rec):
    """Gephi's default of 100 iterations stops early: on Les Miserables it ranks Valjean first,
    where the converged eigenvector ranks Gavroche first. 1,000 iterations recovers the order."""
    await out_of(gephi_mcp.gephi_compute_eigenvector)
    call = next(c for c in rec.calls if c["endpoint"] == "/statistics/run")
    assert call["json"] == {"name": "Eigenvector Centrality", "params": {"numRuns": 1000}}
    await out_of(gephi_mcp.gephi_compute_eigenvector, iterations=5000)
    call = [c for c in rec.calls if c["endpoint"] == "/statistics/run"][-1]
    assert call["json"]["params"] == {"numRuns": 5000}


async def test_query_nodes_can_sort_and_trim_columns(rec):
    await out_of(gephi_mcp.gephi_query_nodes, limit=10, sort_by="pageranks",
                 columns=["pageranks", "Degree"])
    params = rec.last["params"]
    assert params["sort_by"] == "pageranks" and params["descending"] == "true"
    assert params["columns"] == "pageranks,Degree"
    await out_of(gephi_mcp.gephi_query_nodes, sort_by="degree", descending=False)
    assert rec.last["params"]["descending"] == "false"
    await out_of(gephi_mcp.gephi_query_nodes)
    assert "sort_by" not in rec.last["params"] and "columns" not in rec.last["params"]


async def test_remove_isolates_dry_run_counts_without_a_snapshot(rec):
    await out_of(gephi_mcp.gephi_remove_isolates, dry_run=True)
    assert [c["endpoint"] for c in rec.calls] == ["/filter/remove-isolates"]
    assert rec.last["json"] == {"dry_run": True}
