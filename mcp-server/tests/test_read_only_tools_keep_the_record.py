"""A tool annotated read-only must leave the methods record as it found it.

gephi_compare_workspaces once wiped the record because its internal workspace switch counted as a
new graph. This runs every read-only tool against the fake Gephi (at httpx, because the record
reset lives inside GephiClient.request) and checks the receipt still shows the same layout and
statistics and no earlier section."""
import json

import pytest
from test_ledger_survives_snapshot import install_fake_gephi

import gephi_mcp
from session_ledger import Ledger

# Minimal valid arguments for the read-only tools that take required ones.
ARGS = {
    "gephi_column_value_frequencies": {"column": "label"},
    "gephi_compare_nodes": {"id_a": "a", "id_b": "b", "metric": "degree"},
    "gephi_compare_partitions": {"column": "modularity_class", "against": "site"},
    "gephi_detect_duplicates": {"column": "label"},
    "gephi_get_layout_properties": {"algorithm": "ForceAtlas 2"},
    "gephi_get_node": {"id": "a"},
    "gephi_whatif": {"edits": [{"op": "remove_node", "id": "a"}]},
}

# Tools that cannot run against the fake, each with its reason. Keep this short.
SKIP = {
    "gephi_health_check": "fetches latest.json from GitHub; the network is off limits to tests",
    "gephi_view_graph": "Gephi writes the GEXF to a file path; the fake only answers over httpx",
}
MAX_SKIPPED = 3

# Tools that fail the check today. strict, so fixing one turns the xfail into a failure to remove.
KNOWN_FAILURES: dict[str, str] = {}

READ_ONLY = sorted(gephi_mcp._READ_ONLY)


def test_the_skip_list_stays_small_and_names_real_tools():
    assert len(SKIP) <= MAX_SKIPPED
    assert set(SKIP) <= set(READ_ONLY)
    assert set(KNOWN_FAILURES) <= set(READ_ONLY)
    assert set(ARGS) <= set(READ_ONLY)


def _params(name):
    for tool in gephi_mcp.mcp._tool_manager.list_tools():
        if tool.name == name:
            return tool
    raise AssertionError(name)


@pytest.mark.parametrize("name", [
    pytest.param(n, marks=pytest.mark.xfail(strict=True, reason=KNOWN_FAILURES[n]))
    if n in KNOWN_FAILURES else n
    for n in READ_ONLY if n not in SKIP])
async def test_a_read_only_tool_leaves_the_record_unchanged(monkeypatch, name):
    monkeypatch.setattr(gephi_mcp, "LEDGER", Ledger())
    state = install_fake_gephi(monkeypatch)
    state["duplicate"](switch=False)
    gephi_mcp.LEDGER.record("run_layout", algorithm="ForceAtlas 2", iterations=100)
    gephi_mcp.LEDGER.record("statistic", metric="modularity", params={"resolution": 1.0})
    before = gephi_mcp.LEDGER.receipt()

    await getattr(gephi_mcp, name)(**ARGS.get(name, {}))

    receipt = json.loads(await gephi_mcp.gephi_session_receipt())
    assert receipt["layout"] == before["layout"], f"{name} changed the layout record"
    assert receipt["statistics"] == before["statistics"], f"{name} changed the statistics record"
    assert receipt["earlier"] == [], f"{name} ended the record of the graph on screen"


def test_the_check_can_fail():
    # compare_workspaces is not annotated read-only, but it switches workspaces like the bug did;
    # with the bookkeeping guard removed, the same assertions must catch a wiped record.
    import asyncio

    async def run():
        mp = pytest.MonkeyPatch()
        try:
            mp.setattr(gephi_mcp, "LEDGER", Ledger())
            state = install_fake_gephi(mp)
            state["duplicate"](switch=False)
            gephi_mcp.LEDGER.record("run_layout", algorithm="ForceAtlas 2", iterations=100)
            await gephi_mcp.gephi.request("POST", "/graph/clear")  # a real replacement
            return gephi_mcp.LEDGER.receipt()
        finally:
            mp.undo()

    receipt = asyncio.run(run())
    assert receipt["layout"] is None and receipt["earlier"], "the assertions would not notice a wipe"
