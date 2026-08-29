"""The filter-state disclosure on the inline GEXF read path.

Every tool that reads the graph goes through ``_export_gexf_inline``, and that
path exports the VISIBLE graph. With a filter active in Gephi it therefore hands
back a subgraph while ``/graph/stats`` reports the full one, so a tool could
compute communities over 200 nodes and present them as the whole 5,000-node
network. The plugin now declares ``view``, ``filter_active``, and both counts;
these tests pin the client half, which turns that declaration into a warning the
caller actually sees.
"""


import pytest

import gephi_mcp

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _reply(**overrides):
    base = {"success": True, "content": "<gexf/>"}
    base.update(overrides)
    return base


async def _with_reply(monkeypatch, reply):
    async def fake(method, endpoint, **kwargs):
        return reply

    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    return await gephi_mcp._export_gexf_inline()


async def test_no_filter_active_adds_no_warning(monkeypatch):
    out = await _with_reply(monkeypatch, _reply(view="visible", filter_active=False))
    assert "filter_warning" not in out


async def test_filter_active_but_nothing_hidden_adds_no_warning(monkeypatch):
    # A filter can legitimately keep every node. That is not a discrepancy, and
    # warning about it would train the reader to ignore the warning.
    out = await _with_reply(
        monkeypatch,
        _reply(view="visible", filter_active=True, full_node_count=12, visible_node_count=12),
    )
    assert "filter_warning" not in out


async def test_filter_hiding_nodes_warns_with_both_counts(monkeypatch):
    out = await _with_reply(
        monkeypatch,
        _reply(view="visible", filter_active=True, full_node_count=5000, visible_node_count=200),
    )
    warning = out["filter_warning"]
    assert "200" in warning and "5000" in warning
    assert "filter is active" in warning.lower()


async def test_a_full_view_export_is_never_warned_about(monkeypatch):
    # If the export declares it used the full graph, there is nothing to disclose
    # even when a filter exists in the UI.
    out = await _with_reply(
        monkeypatch,
        _reply(view="full", filter_active=True, full_node_count=5000, visible_node_count=200),
    )
    assert "filter_warning" not in out


async def test_missing_counts_do_not_fabricate_a_warning(monkeypatch):
    # An older plugin returns no counts. Say nothing rather than guess.
    out = await _with_reply(monkeypatch, _reply(view="visible", filter_active=True))
    assert "filter_warning" not in out


async def test_a_non_dict_reply_passes_through_untouched(monkeypatch):
    async def fake(method, endpoint, **kwargs):
        return "not a dict"

    monkeypatch.setattr(gephi_mcp.gephi, "request", fake)
    assert await gephi_mcp._export_gexf_inline() == "not a dict"


def test_carry_lifts_the_warning_onto_a_tools_own_result():
    source = {"filter_warning": "careful"}
    result = gephi_mcp._carry_filter_warning(source, {"success": True})
    assert result["filter_warning"] == "careful"


def test_carry_never_overwrites_a_warning_the_tool_set_itself():
    source = {"filter_warning": "from the export"}
    result = gephi_mcp._carry_filter_warning(source, {"filter_warning": "the tool's own"})
    assert result["filter_warning"] == "the tool's own"


def test_carry_is_a_no_op_without_a_warning():
    assert gephi_mcp._carry_filter_warning({"success": True}, {"a": 1}) == {"a": 1}
    assert gephi_mcp._carry_filter_warning(None, {"a": 1}) == {"a": 1}
    assert gephi_mcp._carry_filter_warning({"filter_warning": "x"}, None) is None


# ─── Version resolution ──────────────────────────────────────────────────────
# importlib.metadata.version() can RETURN None instead of raising when site-packages
# holds more than one dist-info for the package. That happened here: two orphaned
# dist-info directories with their METADATA files missing made the session receipt
# carry "server": null. A receipt is provenance, destined for a methods section, so a
# null version is worse than a stated unknown.


def test_the_receipt_never_reports_a_null_server_version(monkeypatch):
    monkeypatch.setattr(gephi_mcp, "__version__", None)
    assert (gephi_mcp.__version__ or "unknown (not an installed distribution)").strip()


def test_package_version_falls_back_when_metadata_returns_none(monkeypatch):
    import importlib.metadata

    monkeypatch.setattr(importlib.metadata, "version", lambda name: None)
    assert gephi_mcp._package_version() == "0.0.0"


def test_package_version_falls_back_when_the_package_is_not_installed(monkeypatch):
    import importlib.metadata

    def raise_not_found(name):
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", raise_not_found)
    assert gephi_mcp._package_version() == "0.0.0"


def test_package_version_passes_a_real_version_through(monkeypatch):
    import importlib.metadata

    monkeypatch.setattr(importlib.metadata, "version", lambda name: "1.17.0")
    assert gephi_mcp._package_version() == "1.17.0"
