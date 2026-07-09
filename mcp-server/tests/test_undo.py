"""
Tests for snapshot/undo: gephi_snapshot, gephi_undo, and the rolling
auto-snapshot taken before destructive tools.

Undo is workspace-copy based (duplicate -> rename copy -> switch back), so these
tests assert the exact HTTP call sequences against a Recorder, including the
fresh /workspace/list re-resolution between steps (indices shift after deletes;
gephi_duplicate_workspace switches the current workspace to the copy).
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
    return json.loads(await tool(**kwargs))


def ws(id, name, current=False, nodes=10, edges=10):
    return {"id": id, "name": name, "current": current,
            "node_count": nodes, "edge_count": edges}


def ws_list(*workspaces):
    return {"success": True, "workspaces": list(workspaces)}


def endpoints(rec):
    return [c["endpoint"] for c in rec.calls]


# ── gephi_snapshot ───────────────────────────────────────────────────────

async def test_snapshot_duplicates_renames_switches_back(rec):
    rec.responses = [
        ws_list(ws(1, "Alpha", current=True), ws(2, "Beta")),
        {"success": True, "workspace_id": 3},                      # duplicate
        ws_list(ws(1, "Alpha"), ws(2, "Beta"), ws(3, "Alpha", current=True)),
        {"success": True},                                          # rename
        {"success": True},                                          # switch back
    ]
    out = await out_of(gephi_mcp.gephi_snapshot, label="checkpoint")

    assert endpoints(rec) == ["/workspace/list", "/workspace/duplicate",
                              "/workspace/list", "/workspace/rename",
                              "/workspace/switch"]
    assert rec.calls[1]["json"] == {"index": 0}                     # duplicate Alpha
    assert rec.calls[3]["json"] == {"index": 2,
                                    "name": "[undo] Alpha (before checkpoint)"}
    assert rec.calls[4]["json"] == {"index": 0}                     # back to Alpha
    assert out["success"] is True
    assert out["snapshot"] == "[undo] Alpha (before checkpoint)"


async def test_snapshot_rolls_previous_snapshot_first(rec):
    rec.responses = [
        ws_list(ws(9, "[undo] Alpha (before clear_graph)"),
                ws(1, "Alpha", current=True)),
        {"success": True},                                          # delete old snapshot
        ws_list(ws(1, "Alpha", current=True)),                      # fresh list, shifted
        {"success": True, "workspace_id": 10},                      # duplicate
        ws_list(ws(1, "Alpha"), ws(10, "Alpha", current=True)),
        {"success": True},                                          # rename
        {"success": True},                                          # switch back
    ]
    out = await out_of(gephi_mcp.gephi_snapshot, label="second try")

    assert endpoints(rec) == ["/workspace/list", "/workspace/delete",
                              "/workspace/list", "/workspace/duplicate",
                              "/workspace/list", "/workspace/rename",
                              "/workspace/switch"]
    assert rec.calls[1]["params"] == {"index": "0"}                 # old snapshot's index
    assert rec.calls[3]["json"] == {"index": 0}                     # Alpha re-resolved
    assert out["success"] is True


async def test_snapshot_refuses_when_current_is_a_snapshot(rec):
    rec.responses = [
        ws_list(ws(9, "[undo] Alpha (before clear_graph)", current=True),
                ws(1, "Alpha")),
    ]
    out = await out_of(gephi_mcp.gephi_snapshot)
    assert out["success"] is False
    assert len(rec.calls) == 1                                      # nothing mutated


async def test_manual_snapshot_ignores_auto_node_cap(rec, monkeypatch):
    monkeypatch.setattr(gephi_mcp, "SNAPSHOT_MAX_NODES", 5)
    rec.responses = [
        ws_list(ws(1, "Big", current=True, nodes=1000)),
        {"success": True, "workspace_id": 2},
        ws_list(ws(1, "Big"), ws(2, "Big", current=True, nodes=1000)),
        {"success": True},
        {"success": True},
    ]
    out = await out_of(gephi_mcp.gephi_snapshot)
    assert out["success"] is True                                   # cap is auto-only


# ── gephi_undo ───────────────────────────────────────────────────────────

async def test_undo_switches_deletes_damaged_and_restores_name(rec):
    rec.responses = [
        ws_list(ws(1, "Alpha", current=True, nodes=2),              # damaged
                ws(9, "[undo] Alpha (before clear_graph)", nodes=50)),
        {"success": True},                                          # switch to snapshot
        ws_list(ws(1, "Alpha"), ws(9, "[undo] Alpha (before clear_graph)",
                                   current=True, nodes=50)),
        {"success": True},                                          # delete damaged
        ws_list(ws(9, "[undo] Alpha (before clear_graph)", current=True, nodes=50)),
        {"success": True},                                          # rename back
    ]
    out = await out_of(gephi_mcp.gephi_undo)

    assert endpoints(rec) == ["/workspace/list", "/workspace/switch",
                              "/workspace/list", "/workspace/delete",
                              "/workspace/list", "/workspace/rename"]
    assert rec.calls[1]["json"] == {"index": 1}                     # snapshot's index
    assert rec.calls[3]["params"] == {"index": "0"}                 # damaged, fresh index
    assert rec.calls[5]["json"] == {"index": 0, "name": "Alpha"}
    assert out["success"] is True
    assert out["restored"] == "Alpha"
    assert out["node_count"] == 50


async def test_undo_with_nothing_to_undo(rec):
    rec.responses = [ws_list(ws(1, "Alpha", current=True))]
    out = await out_of(gephi_mcp.gephi_undo)
    assert out["success"] is False
    assert "undo" in out["error"].lower()
    assert len(rec.calls) == 1


async def test_undo_when_already_on_snapshot_only_renames(rec):
    rec.responses = [
        ws_list(ws(9, "[undo] Alpha (before merge_nodes)", current=True, nodes=50)),
        {"success": True},                                          # rename back
    ]
    out = await out_of(gephi_mcp.gephi_undo)
    assert endpoints(rec) == ["/workspace/list", "/workspace/rename"]
    assert rec.calls[1]["json"] == {"index": 0, "name": "Alpha"}
    assert out["success"] is True


# ── auto-snapshot on destructive tools ───────────────────────────────────

SNAP_OK = [
    ws_list(ws(1, "Alpha", current=True)),
    {"success": True, "workspace_id": 2},
    ws_list(ws(1, "Alpha"), ws(2, "Alpha", current=True)),
    {"success": True},
    {"success": True},
]


async def test_clear_graph_takes_auto_snapshot(rec):
    rec.responses = SNAP_OK + [{"success": True, "message": "Graph cleared"}]
    out = await out_of(gephi_mcp.gephi_clear_graph)

    assert endpoints(rec)[0] == "/workspace/list"
    assert rec.last["endpoint"] == "/graph/clear"
    assert rec.calls[3]["json"]["name"] == "[undo] Alpha (before clear_graph)"
    assert out["success"] is True
    assert out["undo_available"] is True


async def test_auto_snapshot_optout_env(rec, monkeypatch):
    monkeypatch.setattr(gephi_mcp, "AUTO_SNAPSHOT", False)
    out = await out_of(gephi_mcp.gephi_clear_graph)
    assert endpoints(rec) == ["/graph/clear"]                       # straight through
    assert out["undo_available"] is False


async def test_auto_snapshot_skips_above_node_cap(rec, monkeypatch):
    monkeypatch.setattr(gephi_mcp, "SNAPSHOT_MAX_NODES", 100)
    rec.responses = [
        ws_list(ws(1, "Huge", current=True, nodes=200000)),
        {"success": True, "message": "Graph cleared"},
    ]
    out = await out_of(gephi_mcp.gephi_clear_graph)
    assert endpoints(rec) == ["/workspace/list", "/graph/clear"]    # no duplicate
    assert out["undo_available"] is False


async def test_auto_snapshot_failure_never_blocks_the_op(rec):
    rec.responses = [
        {"success": False, "error": "boom"},                        # list fails
        {"success": True, "message": "Graph cleared"},
    ]
    out = await out_of(gephi_mcp.gephi_clear_graph)
    assert rec.last["endpoint"] == "/graph/clear"
    assert out["success"] is True
    assert out["undo_available"] is False


async def test_filter_dry_run_skips_snapshot(rec):
    rec.responses = [{"success": True, "would_remove": 5}]
    out = await out_of(gephi_mcp.gephi_filter_by_degree, min=2, dry_run=True)
    assert endpoints(rec) == ["/filter/degree"]
    assert "undo_available" not in out                              # nothing destroyed


async def test_filter_real_run_takes_snapshot(rec):
    rec.responses = SNAP_OK + [{"success": True, "removed": 5}]
    out = await out_of(gephi_mcp.gephi_filter_by_degree, min=2)
    assert endpoints(rec)[-1] == "/filter/degree"
    assert rec.calls[3]["json"]["name"] == "[undo] Alpha (before filter_by_degree)"
    assert out["undo_available"] is True


async def test_text_to_network_snapshots_only_when_clearing(rec):
    out = await out_of(gephi_mcp.gephi_text_to_network,
                       text="alpha beta gamma alpha beta")
    assert "/workspace/list" not in endpoints(rec)                  # additive: no snapshot
    assert "undo_available" not in out

    rec.calls.clear()
    rec.responses = SNAP_OK + [{"success": True},                   # clear
                               {"success": True}, {"success": True}]  # nodes, edges
    out = await out_of(gephi_mcp.gephi_text_to_network,
                       text="alpha beta gamma alpha beta", clear_existing=True)
    assert endpoints(rec)[0] == "/workspace/list"
    assert "/graph/clear" in endpoints(rec)
    assert out["undo_available"] is True


DESTRUCTIVE_SIMPLE = [
    (lambda: gephi_mcp.gephi_remove_isolates(), "/filter/remove-isolates", "remove_isolates"),
    (lambda: gephi_mcp.gephi_extract_giant_component(), "/filter/giant-component",
     "extract_giant_component"),
    (lambda: gephi_mcp.gephi_extract_ego_network(node_id="a"), "/filter/ego-network",
     "extract_ego_network"),
    (lambda: gephi_mcp.gephi_filter_by_edge_weight(min=1.0), "/filter/edge-weight",
     "filter_by_edge_weight"),
    (lambda: gephi_mcp.gephi_merge_nodes(ids=["a", "b"]), "/datalab/merge-nodes",
     "merge_nodes"),
    (lambda: gephi_mcp.gephi_bulk_remove_nodes(ids=["a"]), "/graph/nodes/remove",
     "bulk_remove_nodes"),
]


@pytest.mark.parametrize("call,endpoint,op", DESTRUCTIVE_SIMPLE,
                         ids=[d[2] for d in DESTRUCTIVE_SIMPLE])
async def test_destructive_tools_take_auto_snapshot(rec, call, endpoint, op):
    rec.responses = SNAP_OK + [{"success": True}]
    out = json.loads(await call())
    assert rec.last["endpoint"] == endpoint
    assert rec.calls[3]["json"]["name"] == f"[undo] Alpha (before {op})"
    assert out["undo_available"] is True


async def test_extract_backbone_snapshots_before_removal(rec):
    edges = [{"source": "a", "target": "b", "weight": 10.0},
             {"source": "a", "target": "c", "weight": 10.0},
             {"source": "a", "target": "d", "weight": 0.001},
             {"source": "b", "target": "c", "weight": 10.0}]
    rec.responses = [{"success": True, "edges": edges}] + SNAP_OK  # fetch, then snapshot
    out = await out_of(gephi_mcp.gephi_extract_backbone, alpha=0.5)
    assert endpoints(rec)[0] == "/graph/edges"
    assert "undo_available" in out


async def test_remove_node_stays_snapshot_free(rec):
    """Single-node removal is deliberately not auto-snapshotted (too chatty)."""
    await out_of(gephi_mcp.gephi_remove_node, id="n1")
    assert endpoints(rec) == ["/graph/node/n1"]
