"""An import says in plain words what Gephi decided on the person's behalf.

Gephi merges repeated rows into one weighted tie and reads an edge list as directed, and reports
the first only as "Parallel edges detected". Both change what later numbers mean, so the import
reply states them.
"""

import json

import pytest

import gephi_mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _gephi_replies(monkeypatch, **reply):
    async def fake(method, endpoint, **kwargs):
        return {"success": True, "node_count": 3, "edge_count": 2, **reply}

    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)


PARALLEL = [{"level": "INFO",
             "message": "Parallel edges detected, remember to choose a merge strategy"}]


@pytest.mark.parametrize("tool", ["gephi_import_file", "gephi_import_csv"])
async def test_merged_rows_are_explained(monkeypatch, tool):
    _gephi_replies(monkeypatch, import_issues=PARALLEL)
    out = json.loads(await getattr(gephi_mcp, tool)(file="/data/edges.csv"))
    assert "merged" in out["merged_rows_note"] and "weight" in out["merged_rows_note"]


async def test_no_merge_note_without_the_notice(monkeypatch):
    _gephi_replies(monkeypatch, import_issues=[{"level": "INFO", "message": "something else"}])
    out = json.loads(await gephi_mcp.gephi_import_file(file="/data/edges.csv"))
    assert "merged_rows_note" not in out


@pytest.mark.parametrize("name", ["/data/edges.csv", "/data/EDGES.TSV"])
async def test_a_spreadsheet_import_says_direction_is_gephis_default(monkeypatch, name):
    _gephi_replies(monkeypatch)
    out = json.loads(await gephi_mcp.gephi_import_file(file=name))
    assert "directed" in out["direction_note"]


async def test_a_graph_file_gets_no_direction_note(monkeypatch):
    # GEXF and GraphML state their own direction.
    _gephi_replies(monkeypatch)
    out = json.loads(await gephi_mcp.gephi_import_file(file="/data/graph.gexf"))
    assert "direction_note" not in out


async def test_a_failed_import_gets_no_notes(monkeypatch):
    async def fake(method, endpoint, **kwargs):
        return {"success": False, "error": "no such file", "import_issues": PARALLEL}

    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    out = json.loads(await gephi_mcp.gephi_import_file(file="/data/edges.csv"))
    assert "merged_rows_note" not in out and "direction_note" not in out
