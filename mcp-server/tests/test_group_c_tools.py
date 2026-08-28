"""The workspace comparison and bipartite tools, against the endpoint contracts they call.

Two of these pin contract details that are easy to get wrong and silent when wrong: the workspace
API switches by zero-based INDEX while the workspace list reports an ID, and renaming needs the
index as well as the name.
"""

import json
import textwrap

import pytest

import gephi_mcp


def gexf(nodes, edges=()):
    ns = "".join(
        f'<node id="{k}"><attvalues><attvalue for="0" value="{v}"/></attvalues></node>'
        for k, v in nodes.items())
    es = "".join(f'<edge id="{i}" source="{s}" target="{t}"/>'
                 for i, (s, t) in enumerate(edges))
    return textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <gexf xmlns="http://gexf.net/1.3" version="1.3"><graph defaultedgetype="undirected">
        <attributes class="node"><attribute id="0" title="kind" type="string"/></attributes>
        <nodes>%s</nodes><edges>%s</edges></graph></gexf>
        """) % (ns, es)


class Recorder:
    def __init__(self):
        self.calls = []
        self.responses = []

    async def __call__(self, method, endpoint, params=None, json_data=None, timeout=None):
        self.calls.append({"method": method, "endpoint": endpoint, "json": json_data})
        if self.responses:
            return self.responses.pop(0)
        return {"success": True}

    def sent_to(self, endpoint):
        return [c["json"] for c in self.calls if c["endpoint"] == endpoint]


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    monkeypatch.setattr(gephi_mcp.gephi, "request", r)
    gephi_mcp.LEDGER.reset()
    return r


# The list reports an id; switch takes a zero-based index. They are not the same number.
WORKSPACES = {"success": True, "workspaces": [
    {"id": 1, "name": "Workspace 1", "current": False},
    {"id": 2, "name": "Workspace 2", "current": True},
]}


async def test_comparing_workspaces_switches_by_index_not_by_id(rec):
    """Switching by the reported id would land on the wrong workspace, or none at all."""
    rec.responses = [
        WORKSPACES,
        {"success": True},
        {"success": True, "content": gexf({"a": "person"})},
        {"success": True},
        WORKSPACES,
        {"success": True},
        {"success": True, "content": gexf({"a": "person", "b": "person"})},
        {"success": True},
    ]

    await gephi_mcp.gephi_compare_workspaces(before=0, after=1)

    switches = rec.sent_to("/workspace/switch")
    assert {"index": 0} in switches, "must switch to the requested index"
    assert all(0 <= s["index"] <= 1 for s in switches), (
        f"every switch must use a zero-based index, got {switches}")


async def test_comparing_workspaces_returns_to_where_it_started(rec):
    rec.responses = [
        WORKSPACES, {"success": True},
        {"success": True, "content": gexf({"a": "person"})}, {"success": True},
        WORKSPACES, {"success": True},
        {"success": True, "content": gexf({"a": "person"})}, {"success": True},
    ]

    await gephi_mcp.gephi_compare_workspaces(before=0, after=1)

    assert rec.sent_to("/workspace/switch")[-1] == {"index": 1}, (
        "the workspace that was current before the comparison must be current after it")


async def test_a_projection_names_its_new_workspace_with_the_index_rename_requires(rec):
    rec.responses = [
        {"success": True, "content": gexf(
            {"ann": "person", "e1": "event"}, [("ann", "e1")])},
        {"success": True},
        WORKSPACES,
    ]

    await gephi_mcp.gephi_bipartite_projection(
        mode_column="kind", keep="person", workspace_name="people")

    sent = rec.sent_to("/workspace/rename")
    assert sent, "the rename must actually be attempted"
    assert "index" in sent[0], f"rename requires an index, sent {sent[0]}"
    assert sent[0]["name"] == "people"


async def test_a_projection_without_a_name_does_not_call_rename(rec):
    rec.responses = [{"success": True, "content": gexf(
        {"ann": "person", "e1": "event"}, [("ann", "e1")])}]

    await gephi_mcp.gephi_bipartite_projection(mode_column="kind", keep="person")

    assert rec.sent_to("/workspace/rename") == []


async def test_an_unreadable_workspace_is_reported_rather_than_compared_as_empty(rec):
    """An unreadable side would otherwise look like a network that lost every node."""
    rec.responses = [WORKSPACES, {"success": True}, {"success": False, "error": "busy"}]

    out = json.loads(await gephi_mcp.gephi_compare_workspaces(before=0, after=1))

    assert out["success"] is False
    assert "workspace 0" in out["error"].lower()
