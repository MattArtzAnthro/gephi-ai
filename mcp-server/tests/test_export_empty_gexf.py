"""An inline GEXF export that comes back empty is a failure, and says why.

Gephi's GEXF exporter throws on an attribute column that holds a set of times
(``TimestampSet`` or ``IntervalSet``), logs the error, and writes nothing. A CSV
edge list with a date column imports as exactly that. The plugin then answers
``success: true`` with empty ``content``, and every tool that reads the graph
through ``_export_gexf_inline`` went on to parse an empty string, which
``parse_gexf`` takes for a file path: the person saw ``FileNotFoundError: ''``.

These tests pin the client half: empty content is reported as a failed export
that names the columns responsible and what to do about them.
"""

import inspect
import json
import re

import pytest

import gephi_mcp
from gephi_mcp_viewer import parse_gexf

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _col(col_id, type_, prop):
    return {"id": col_id, "title": col_id, "type": type_, "property": prop}


EDGE_COLUMNS = [
    _col("id", "String", True),
    _col("timeset", "TimestampSet", True),
    _col("weight", "Double", True),
    _col("date", "TimestampSet", False),
]
NODE_COLUMNS = [_col("id", "String", True), _col("timeset", "TimestampSet", True)]


def _fake_gephi(monkeypatch, content, columns_ok=True):
    """Stand in for Gephi: an export reply with the given content, plus column listings."""
    calls = []

    async def fake(method, endpoint, **kwargs):
        calls.append((method, endpoint, kwargs))
        if endpoint == "/export/gexf":
            return {"success": True, "message": "GEXF exported inline", "view": "visible",
                    "filter_active": False, "content": content}
        if endpoint == "/graph/columns":
            if not columns_ok:
                return {"success": False, "error": "no workspace"}
            target = kwargs["params"]["target"]
            return {"success": True, "target": target,
                    "columns": EDGE_COLUMNS if target == "edge" else NODE_COLUMNS}
        return {"success": True}

    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    return calls


@pytest.mark.parametrize("content", ["", "   \n"])
async def test_empty_export_is_a_failure_naming_the_time_column(monkeypatch, content):
    _fake_gephi(monkeypatch, content)
    out = await gephi_mcp._export_gexf_inline()
    assert out["success"] is False
    assert "content" not in out
    assert out["blocking_columns"] == [
        {"table": "edge", "column": "date", "type": "TimestampSet"}
    ]
    assert "date" in out["error"]
    assert "gephi_edit_column" in out["error"]


async def test_gephis_own_time_column_is_not_blamed(monkeypatch):
    # "timeset" is a property column; the exporter writes it without trouble.
    _fake_gephi(monkeypatch, "")
    out = await gephi_mcp._export_gexf_inline()
    assert all(c["column"] != "timeset" for c in out["blocking_columns"])


async def test_empty_export_still_fails_when_columns_cannot_be_read(monkeypatch):
    _fake_gephi(monkeypatch, "", columns_ok=False)
    out = await gephi_mcp._export_gexf_inline()
    assert out["success"] is False
    assert out["blocking_columns"] == []
    assert "empty" in out["error"]


async def test_a_real_export_is_left_alone_and_asks_nothing_more(monkeypatch):
    calls = _fake_gephi(monkeypatch, "<gexf/>")
    out = await gephi_mcp._export_gexf_inline()
    assert out["success"] is True
    assert out["content"] == "<gexf/>"
    assert [c[1] for c in calls] == ["/export/gexf"]


async def test_a_reply_without_a_content_field_is_not_called_empty(monkeypatch):
    # An older plugin answers an inline request without "content"; that is not this failure.
    async def fake(method, endpoint, **kwargs):
        return {"success": True, "message": "GEXF exported"}

    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    assert await gephi_mcp._export_gexf_inline() == {"success": True, "message": "GEXF exported"}


async def test_profile_graph_reports_the_failure_instead_of_raising(monkeypatch):
    _fake_gephi(monkeypatch, "")
    out = json.loads(await gephi_mcp.gephi_profile_graph())
    assert out["success"] is False
    assert "date" in out["error"]


def test_parse_gexf_refuses_empty_input():
    # An empty string is not a path. Without this it surfaced as FileNotFoundError: ''.
    with pytest.raises(ValueError, match="empty"):
        parse_gexf("")


def _fake_file_export(monkeypatch, text):
    """Stand in for Gephi writing `text` to the file it was asked for."""
    async def fake(method, endpoint, **kwargs):
        if endpoint == "/export/gexf":
            with open(kwargs["json_data"]["file"], "w", encoding="utf-8") as fh:
                fh.write(text)
            return {"success": True, "message": "GEXF exported"}
        target = kwargs["params"]["target"]
        return {"success": True, "columns": EDGE_COLUMNS if target == "edge" else NODE_COLUMNS}

    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)


async def test_an_empty_exported_file_is_a_failure_too(monkeypatch, tmp_path):
    _fake_file_export(monkeypatch, "")
    out = await gephi_mcp._export_gexf_to_file(str(tmp_path / "g.gexf"))
    assert out["success"] is False
    assert out["blocking_columns"][0]["column"] == "date"


async def test_a_written_file_is_left_alone(monkeypatch, tmp_path):
    _fake_file_export(monkeypatch, "<gexf/>")
    out = await gephi_mcp._export_gexf_to_file(str(tmp_path / "g.gexf"))
    assert out == {"success": True, "message": "GEXF exported"}


async def test_a_file_that_cannot_be_checked_keeps_gephis_answer(monkeypatch, tmp_path):
    async def fake(method, endpoint, **kwargs):
        return {"success": True, "message": "GEXF exported"}  # and writes no file

    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    out = await gephi_mcp._export_gexf_to_file(str(tmp_path / "missing.gexf"))
    assert out["success"] is True


async def test_visual_qa_reports_the_failure_instead_of_a_parse_error(monkeypatch):
    _fake_file_export(monkeypatch, "")
    out = json.loads(await gephi_mcp.gephi_visual_qa())
    assert out["success"] is False
    assert "date" in out["error"]


@pytest.mark.parametrize("to_file", [False, True])
async def test_export_gexf_tool_reports_the_failure(monkeypatch, tmp_path, to_file):
    if to_file:
        _fake_file_export(monkeypatch, "")
        out = json.loads(await gephi_mcp.gephi_export_gexf(file=str(tmp_path / "g.gexf")))
    else:
        _fake_gephi(monkeypatch, "")
        out = json.loads(await gephi_mcp.gephi_export_gexf())
    assert out["success"] is False
    assert "date" in out["error"]


def test_every_gexf_export_goes_through_a_guarded_helper():
    # The guards live in _export_gexf_inline and _export_gexf_to_file. A tool that posts
    # to /export/gexf on its own would skip them and meet the empty export unprotected.
    source = inspect.getsource(gephi_mcp)
    assert len(re.findall(r'"/export/gexf"', source)) == 2


# ─── The time signal names its columns ───────────────────────

DYNAMIC_GEXF = (
    '<gexf xmlns="http://gexf.net/1.3" version="1.3"><graph mode="dynamic" '
    'defaultedgetype="undirected"><nodes><node id="a"/><node id="b"/><node id="c"/></nodes>'
    '<edges><edge id="0" source="a" target="b" start="1" end="2"/>'
    '<edge id="1" source="b" target="c" start="2" end="3"/></edges></graph></gexf>'
)
STATIC_GEXF = DYNAMIC_GEXF.replace(' mode="dynamic"', "").replace(' start="1" end="2"', "") \
                          .replace(' start="2" end="3"', "")


def _fake_profile_run(monkeypatch, content, edge_columns):
    calls = []

    async def fake(method, endpoint, **kwargs):
        calls.append(endpoint)
        if endpoint == "/export/gexf":
            return {"success": True, "content": content}
        if endpoint == "/graph/columns":
            target = kwargs["params"]["target"]
            return {"success": True, "columns": edge_columns if target == "edge" else NODE_COLUMNS}
        return {"success": False}

    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    return calls


async def test_the_time_signal_names_the_columns_that_hold_times(monkeypatch):
    columns = EDGE_COLUMNS[:3] + [_col("score", "TimestampDoubleMap", False)]
    _fake_profile_run(monkeypatch, DYNAMIC_GEXF, columns)
    out = json.loads(await gephi_mcp.gephi_profile_graph())
    time_signal = next(s for s in out["type_signals"] if s["type"] == "time")
    # The ties carry times, the nodes do not: the node table's empty time column is not named.
    assert time_signal["evidence"]["columns"] == [
        {"table": "edge", "column": "timeset", "type": "TimestampSet"},
        {"table": "edge", "column": "score", "type": "TimestampDoubleMap"},
    ]


async def test_a_static_graph_asks_for_no_columns(monkeypatch):
    calls = _fake_profile_run(monkeypatch, STATIC_GEXF, EDGE_COLUMNS[:3])
    out = json.loads(await gephi_mcp.gephi_profile_graph())
    assert all(s["type"] != "time" for s in out["type_signals"])
    assert "/graph/columns" not in calls


async def test_the_time_signal_stands_when_columns_cannot_be_read(monkeypatch):
    async def fake(method, endpoint, **kwargs):
        if endpoint == "/export/gexf":
            return {"success": True, "content": DYNAMIC_GEXF}
        return {"success": False, "error": "no workspace"}

    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    out = json.loads(await gephi_mcp.gephi_profile_graph())
    time_signal = next(s for s in out["type_signals"] if s["type"] == "time")
    assert "columns" not in time_signal["evidence"]


def test_a_timed_graph_with_nothing_on_the_timeline_says_so():
    # What is left after a date column is converted to text: Gephi still calls the graph
    # dynamic, and no node or tie has a time. The reading must not promise a timeline.
    from gephi_mcp_viewer.profile import structural_profile

    empty = DYNAMIC_GEXF.replace(' start="1" end="2"', "").replace(' start="2" end="3"', "")
    profile = structural_profile(parse_gexf(empty, max_nodes=10**9))
    time_signal = next(s for s in profile["type_signals"] if s["type"] == "time")
    assert time_signal["evidence"] == {"dynamic": True, "nodes_with_times": 0,
                                       "edges_with_times": 0}
    assert "gephi_set_time_from_columns" in time_signal["reading"]

    full = structural_profile(parse_gexf(DYNAMIC_GEXF, max_nodes=10**9))
    reading = next(s for s in full["type_signals"] if s["type"] == "time")["reading"]
    assert "gephi_set_time_from_columns" not in reading
