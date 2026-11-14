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


# ─── What the file itself says ───────────────────────────────

def _edge_csv(tmp_path, text, name="edges.csv"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return str(path)


async def test_a_file_that_states_direction_gets_no_direction_note(monkeypatch, tmp_path):
    # Gephi reads a Type column (Directed / Undirected), so the direction is the file's own.
    _gephi_replies(monkeypatch)
    path = _edge_csv(tmp_path, "Source,Target,Type\na,b,Undirected\nb,c,Undirected\n")
    out = json.loads(await gephi_mcp.gephi_import_file(file=path))
    assert "direction_note" not in out


async def test_a_file_without_a_type_column_still_gets_the_direction_note(monkeypatch, tmp_path):
    _gephi_replies(monkeypatch)
    path = _edge_csv(tmp_path, "source,target\na,b\nb,c\n")
    out = json.loads(await gephi_mcp.gephi_import_file(file=path))
    assert "directed" in out["direction_note"]


@pytest.mark.parametrize("name,sep", [("edges.csv", ","), ("edges.csv", ";"), ("edges.tsv", "\t")])
async def test_merged_rows_are_counted(monkeypatch, tmp_path, name, sep):
    # Five rows, two ties after Gephi merged the repeats: three rows were merged away.
    _gephi_replies(monkeypatch, import_issues=PARALLEL)
    rows = ["source,target,date", "a,b,1", "a,b,2", "a,b,3", "b,c,1", "b,c,2", ""]
    path = _edge_csv(tmp_path, "\n".join(rows).replace(",", sep), name)
    out = json.loads(await gephi_mcp.gephi_import_file(file=path))
    assert out["merged_rows"] == {"rows": 5, "ties": 2, "merged": 3}
    assert "5 rows" in out["merged_rows_note"] and "2 ties" in out["merged_rows_note"]


async def test_rows_without_both_ends_are_not_counted(monkeypatch, tmp_path):
    _gephi_replies(monkeypatch, import_issues=PARALLEL)
    path = _edge_csv(tmp_path, "source,target\na,b\na,b\na,b\n,c\nd,\n")
    out = json.loads(await gephi_mcp.gephi_import_file(file=path))
    assert out["merged_rows"]["rows"] == 3


async def test_no_count_when_appending_to_a_graph_already_there(monkeypatch, tmp_path):
    # edge_count is then the whole graph's, so rows minus ties would be wrong.
    _gephi_replies(monkeypatch, import_issues=PARALLEL)
    path = _edge_csv(tmp_path, "source,target\na,b\na,b\na,b\n")
    out = json.loads(await gephi_mcp.gephi_import_file(file=path, mode="append"))
    assert "merged_rows" not in out and "merged" in out["merged_rows_note"]


@pytest.mark.parametrize("text", ["id,label\na,A\nb,B\n", "", "source,target\na,b\n"])
async def test_no_count_when_the_file_gives_none(monkeypatch, tmp_path, text):
    # A node table, an empty file, and a file with fewer rows than ties: say nothing numeric.
    _gephi_replies(monkeypatch, import_issues=PARALLEL)
    out = json.loads(await gephi_mcp.gephi_import_file(file=_edge_csv(tmp_path, text)))
    assert "merged_rows" not in out and "merged_rows_note" in out


async def test_a_file_that_is_not_text_keeps_the_plain_notes(monkeypatch, tmp_path):
    _gephi_replies(monkeypatch, import_issues=PARALLEL)
    path = tmp_path / "edges.csv"
    path.write_bytes(b"\xff\xfe\x00\x81source,target\n")
    out = json.loads(await gephi_mcp.gephi_import_file(file=str(path)))
    assert "merged_rows" not in out and "direction_note" in out
