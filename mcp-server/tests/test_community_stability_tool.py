"""gephi_community_stability: the tool that answers "are these communities real?".

Gephi reports one partition as though it were the answer. This runs detection repeatedly and
reports which groups survive. gephi#2968 asked Gephi for this and was closed as not planned.
"""

import json
import textwrap

import pytest

import gephi_mcp


def gexf(assignments):
    """A GEXF document shaped like a REAL Gephi export.

    Gephi titles the column "Modularity Class", not "modularity_class". A fixture using the
    latter is a graph Gephi never produces, and a test built on it passes while production
    reads nothing back.
    """
    nodes = "\n".join(
        f'      <node id="{n}" label="{n}">'
        f'<attvalues><attvalue for="0" value="{c}"/></attvalues></node>'
        for n, c in assignments.items())
    return textwrap.dedent("""\
        <?xml version="1.0" encoding="UTF-8"?>
        <gexf xmlns="http://gexf.net/1.3" version="1.3">
          <graph defaultedgetype="undirected">
            <attributes class="node">
              <attribute id="0" title="Modularity Class" type="integer"/>
            </attributes>
            <nodes>
        %s
            </nodes>
            <edges/>
          </graph>
        </gexf>
        """) % nodes


class Recorder:
    def __init__(self):
        self.calls = []
        self.responses = []

    async def __call__(self, method, endpoint, params=None, json_data=None, timeout=None):
        self.calls.append({"method": method, "endpoint": endpoint, "json": json_data})
        if self.responses:
            return self.responses.pop(0)
        return {"success": True}

    def endpoints(self):
        return [c["endpoint"] for c in self.calls]


def plan(partitions):
    """The response queue for one run per partition: modularity, then the read-back."""
    out = []
    for p in partitions:
        out.append({"success": True, "modularity": 0.4, "communities": len(set(p.values()))})
        out.append({"success": True, "content": gexf(p)})
    return out


@pytest.fixture
def rec(monkeypatch):
    r = Recorder()
    monkeypatch.setattr(gephi_mcp.gephi, "request", r)
    gephi_mcp.invalidate_graph_facts()
    return r


STABLE = {"a": 1, "b": 1, "c": 2, "d": 2}


async def test_it_runs_detection_once_per_requested_run(rec):
    rec.responses = plan([STABLE] * 3)

    await gephi_mcp.gephi_community_stability(runs=3)

    assert rec.endpoints().count("/statistics/modularity") == 3


async def test_stable_communities_are_reported_as_stable(rec):
    rec.responses = plan([STABLE] * 3)

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=3))

    assert out["mean_stability"] == pytest.approx(1.0)
    assert out["distinct_partitions"] == 1


async def test_a_wandering_node_is_named(rec):
    rec.responses = plan([
        {"a": 1, "b": 1, "x": 1, "c": 2, "d": 2},
        {"a": 1, "b": 1, "x": 2, "c": 2, "d": 2},
        {"a": 1, "b": 1, "x": 1, "c": 2, "d": 2},
        {"a": 1, "b": 1, "x": 2, "c": 2, "d": 2},
    ])

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=4))

    assert out["unstable_nodes"][0]["node"] == "x"
    assert out["distinct_partitions"] == 2


async def test_the_result_goes_through_the_caveat_layer(rec):
    """Whatever the register holds for modularity must reach this result too.

    Asserted through the layer rather than against a fixed caveat id, because the register's
    contents depend on what the probes last found on this machine, and a test that moves with
    the environment is testing the environment.
    """
    rec.responses = plan([STABLE] * 2)

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2, resolution=3.0))

    assert "gephi-2034" in {c["id"] for c in out["caveats"]}, (
        "a non-default resolution must still surface the reciprocal caveat")




async def test_the_consensus_partition_is_written_to_its_own_column(rec):
    """gephi#2590: a re-run must not silently overwrite the previous partition."""
    rec.responses = plan([STABLE] * 2)

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    writes = [c for c in rec.calls if c["endpoint"] == "/graph/nodes/attributes"]
    assert writes, "the consensus partition must be written back"
    written = writes[0]["json"]["updates"]
    assert all("consensus_community" in u["attributes"] for u in written)
    assert out["consensus_column"] == "consensus_community"


async def test_the_consensus_column_is_created_before_it_is_written(rec):
    rec.responses = plan([STABLE] * 2)

    await gephi_mcp.gephi_community_stability(runs=2)

    order = rec.endpoints()
    assert order.index("/graph/columns/add") < order.index("/graph/nodes/attributes")


async def test_one_run_is_refused_because_it_cannot_establish_anything(rec):
    out = json.loads(await gephi_mcp.gephi_community_stability(runs=1))

    assert out["success"] is False
    assert "at least 2" in out["error"]
    assert rec.endpoints() == [], "it must not touch the graph before refusing"


async def test_a_failed_detection_run_stops_the_analysis_rather_than_reporting_on_less(rec):
    rec.responses = [
        {"success": True, "modularity": 0.4},
        {"success": True, "content": gexf(STABLE)},
        {"success": False, "error": "Gephi is busy"},
    ]

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=3))

    assert out["success"] is False
    assert "busy" in out["error"]


async def test_an_unreadable_partition_is_an_error_not_an_empty_result(rec):
    """An empty read-back looks exactly like a perfectly stable one. It must never pass silently.

    Zero partitions means the column was not found, not that the graph held still. Treating the
    two the same records "nothing was measured" as "the partition is stable".
    """
    no_partition_column = gexf(STABLE).replace("Modularity Class", "Something Else")
    rec.responses = [
        {"success": True, "modularity": 0.4},
        {"success": True, "content": no_partition_column},
    ]

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    assert out["success"] is False
    assert "could not read any partition back" in out["error"]
