"""
Tests for gephi_claim_record: the structured, graph-checked receipt behind a
verified claim. The tool re-reads every cited node from Gephi and confirms the
cited numbers match the live values, so a record cannot restate numbers the
graph does not hold.
"""

import json

import pytest
from mcp.types import CallToolResult

import gephi_mcp

NODES = {
    "maria": {"id": "maria", "label": "Maria", "attributes": {"Betweenness Centrality": 0.41}},
    "tom": {"id": "tom", "label": "Tom", "attributes": {"Betweenness Centrality": 0.12}},
}


@pytest.fixture
def graph(monkeypatch):
    async def fake_request(method, endpoint, params=None, json_data=None, timeout=None):
        assert method == "GET" and endpoint.startswith("/graph/node/get/")
        nid = endpoint.rsplit("/", 1)[1]
        if nid in NODES:
            return {"success": True, "node": NODES[nid]}
        return {"success": False, "error": f"node {nid} not found"}
    monkeypatch.setattr(gephi_mcp.gephi, "request", fake_request)


async def test_record_verifies_nodes_and_values(graph):
    result = await gephi_mcp.gephi_claim_record(
        claim="Maria is more central than Tom",
        classification="comparison",
        verdict="confirmed",
        metric="Betweenness Centrality",
        nodes=["maria", "tom"],
        values={"maria": 0.41, "tom": 0.12},
        caveat="Betweenness on the full graph; the network is small.",
    )
    assert isinstance(result, CallToolResult)
    assert result.is_error is False
    rec = result.structured_content
    assert rec["verified"] is True
    assert rec["verdict"] == "confirmed"
    assert rec["checks"]["nodes_missing"] == []
    assert rec["checks"]["value_mismatches"] == []
    assert {n["id"]: n["label"] for n in rec["evidence"]["nodes"]} == {"maria": "Maria", "tom": "Tom"}
    assert "confirmed" in rec["caption"] and "0.41" in rec["caption"] and "0.12" in rec["caption"]
    assert ".." not in rec["caption"]
    assert "confirmed" in result.content[0].text


async def test_record_flags_missing_node(graph):
    result = await gephi_mcp.gephi_claim_record(
        claim="Maria is more central than Zed",
        classification="comparison",
        verdict="confirmed",
        metric="Betweenness Centrality",
        nodes=["maria", "zed"],
        values={"maria": 0.41, "zed": 0.05},
        caveat="",
    )
    rec = result.structured_content
    assert result.is_error is False
    assert rec["verified"] is False
    assert rec["checks"]["nodes_missing"] == ["zed"]
    assert "zed" in result.content[0].text


async def test_record_flags_value_mismatch(graph):
    result = await gephi_mcp.gephi_claim_record(
        claim="Maria is more central than Tom",
        classification="comparison",
        verdict="confirmed",
        metric="Betweenness Centrality",
        nodes=["maria", "tom"],
        values={"maria": 0.9, "tom": 0.12},
        caveat="",
    )
    rec = result.structured_content
    assert rec["verified"] is False
    mm = rec["checks"]["value_mismatches"]
    assert len(mm) == 1
    assert mm[0]["id"] == "maria" and mm[0]["cited"] == 0.9 and mm[0]["live"] == 0.41


async def test_record_rejects_unknown_verdict(graph):
    result = await gephi_mcp.gephi_claim_record(
        claim="x", classification="comparison", verdict="probably",
        metric=None, nodes=[], values=None, caveat="",
    )
    assert result.is_error is True
    assert "verdict" in result.content[0].text


async def test_record_without_metric_checks_nodes_only(graph):
    result = await gephi_mcp.gephi_claim_record(
        claim="Maria and Tom are in different communities",
        classification="connectivity",
        verdict="cant_tell",
        metric=None,
        nodes=["maria", "tom"],
        values=None,
        numbers={"within_fraction": 0.34, "random_baseline": 0.31},
        caveat="No community column computed; grouping came from a label prefix.",
    )
    rec = result.structured_content
    assert rec["verified"] is True
    assert rec["numbers"] == {"within_fraction": 0.34, "random_baseline": 0.31}
    assert "cannot tell" in rec["caption"]


async def test_record_exports_bundle(graph, tmp_path):
    path = tmp_path / "claim.json"
    result = await gephi_mcp.gephi_claim_record(
        claim="Maria is more central than Tom",
        classification="comparison",
        verdict="confirmed",
        metric="Betweenness Centrality",
        nodes=["maria", "tom"],
        values={"maria": 0.41, "tom": 0.12},
        caveat="",
        export=str(path),
    )
    assert result.structured_content["export"] == str(path)
    saved = json.loads(path.read_text())
    assert saved["claim"] == "Maria is more central than Tom"
    assert saved["verified"] is True
    assert saved["caption"] == result.structured_content["caption"]


async def test_claim_record_annotation_admits_the_file_write():
    """It never changes the graph, but `export` writes a file, so it must not
    advertise itself as read-only (a host may skip confirmation on that hint).
    Same classification as the export tools."""
    from gephi_mcp import _annotations_for
    ann = _annotations_for("gephi_claim_record")
    assert ann.read_only_hint is False and ann.destructive_hint is False
