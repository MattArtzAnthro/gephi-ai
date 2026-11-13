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
        self.health = None  # answers GET /health when set, outside the response queue
        # Answers GET /graph/nodes, outside the queue: the partition the graph held before the
        # tool ran. Empty by default, a graph on which modularity has never run.
        self.nodes = {"success": True, "nodes": []}

    async def __call__(self, method, endpoint, params=None, json_data=None, timeout=None):
        self.calls.append({"method": method, "endpoint": endpoint, "json": json_data})
        if self.health is not None and endpoint == "/health":
            return self.health
        if method == "GET" and endpoint == "/graph/nodes":
            return self.nodes
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


STOPPED = {"success": False, "stopped": True,
           "error": "Modularity did not finish within 45 s and was stopped; its column was not updated."}


async def test_every_detection_run_carries_a_deadline_for_gephi(rec):
    rec.responses = plan([STABLE] * 2)

    await gephi_mcp.gephi_community_stability(runs=2)

    sent = [c["json"] for c in rec.calls if c["endpoint"] == "/statistics/modularity"]
    assert sent and all(j.get("timeout_ms", 0) > 0 for j in sent)


# What /health reports. Gephi 0.11.3 can loop forever in modularity (gephi#1630); 0.11.4 fixes it.
# Plugins before 1.5.0 do not report Gephi's version at all.
HEALTH_0113 = {"status": "ok", "gephi_version": "0.11.3"}
HEALTH_0114 = {"status": "ok", "gephi_version": "0.11.4"}
HEALTH_NO_VERSION = {"status": "ok"}


async def test_on_gephi_0113_a_stopped_run_is_repeated_and_the_stale_column_is_never_read(rec):
    """A stopped run leaves the previous partition in the column (gephi#1630). Reading it back
    would count one partition twice and overstate stability, so the run is repeated instead."""
    rec.health = HEALTH_0113
    rec.responses = ([plan([STABLE])[0], plan([STABLE])[1], STOPPED]
                     + plan([{"a": 1, "b": 2, "c": 2, "d": 2}]))

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    assert out["success"] is True
    assert out["runs"] == 2
    assert out["distinct_partitions"] == 2
    assert out["reruns_after_nonconvergence"] == 1
    assert rec.endpoints().count("/statistics/modularity") == 3


async def test_on_gephi_0113_a_run_that_never_converges_stops_the_analysis(rec):
    rec.health = HEALTH_0113
    rec.responses = [STOPPED, STOPPED]

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    assert out["success"] is False
    assert out["stopped"] is True
    assert str(gephi_mcp.MODULARITY_ATTEMPTS) in out["error"], "the error should say how many attempts ran"
    assert "0.11.4" in out["error"], "the error should say that Gephi 0.11.4 fixes this"


async def test_on_gephi_0113_compute_modularity_repeats_a_stopped_run_and_says_so(rec):
    rec.health = HEALTH_0113
    rec.responses = [STOPPED, {"success": True, "modularity": 0.41, "communities": 5}]

    out = json.loads(await gephi_mcp.gephi_compute_modularity())

    assert out["modularity"] == 0.41
    assert out["reruns_after_nonconvergence"] == 1


async def test_a_plugin_that_does_not_report_gephi_version_still_gets_the_rerun(rec):
    rec.health = HEALTH_NO_VERSION
    rec.responses = [STOPPED, {"success": True, "modularity": 0.41}]

    out = json.loads(await gephi_mcp.gephi_compute_modularity())

    assert out["reruns_after_nonconvergence"] == 1


async def test_when_health_fails_after_a_stop_the_run_is_repeated_as_on_older_gephi(rec):
    """Without a version to go on, the safe assumption is a Gephi that can loop: one more run."""
    rec.health = {"success": False, "error": "Gephi did not answer"}
    rec.responses = [STOPPED, {"success": True, "modularity": 0.41}]

    out = json.loads(await gephi_mcp.gephi_compute_modularity())

    assert out["reruns_after_nonconvergence"] == 1


async def test_on_gephi_0114_a_stopped_run_is_reported_not_repeated(rec):
    """Gephi 0.11.4 fixes the run that never finished, so a stop means the deadline was too
    short for the graph. Repeating it would only wait out the deadline a second time."""
    rec.health = HEALTH_0114
    rec.responses = [STOPPED]

    out = json.loads(await gephi_mcp.gephi_compute_modularity())

    assert out["success"] is False
    assert out["stopped"] is True
    assert rec.endpoints().count("/statistics/modularity") == 1
    assert "GEPHI_MODULARITY_DEADLINE" in out["error"]
    assert "1630" not in out["error"]
    assert "reruns_after_nonconvergence" not in out


async def test_on_gephi_0114_a_stopped_run_ends_the_stability_analysis_unread(rec):
    rec.health = HEALTH_0114
    # What a repeated run would read, so code that repeats it fails on the result, not on the queue.
    rec.responses = [plan([STABLE])[0], plan([STABLE])[1], STOPPED] + plan([STABLE])

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    assert out["success"] is False
    assert out["stopped"] is True
    after_stop = rec.endpoints()[rec.endpoints().index("/health"):]
    assert after_stop == ["/health"], f"nothing may be read after the stopped run: {after_stop}"


async def test_stable_cores_are_written_to_their_own_column_with_minus_one_for_none(rec):
    wander = [{"a": 1, "b": 1, "x": 1, "c": 2, "d": 2}, {"a": 1, "b": 1, "x": 2, "c": 2, "d": 2}]
    rec.responses = plan(wander)

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    added = [c["json"]["name"] for c in rec.calls if c["endpoint"] == "/graph/columns/add"]
    assert "stable_core" in added
    written = {u["id"]: u["attributes"]["stable_core"]
               for c in rec.calls if c["endpoint"] == "/graph/nodes/attributes"
               for u in c["json"]["updates"]}
    assert written["x"] == -1
    assert written["a"] == written["b"] != written["c"] == written["d"] != -1
    assert out["core_column"] == "stable_core"
    assert out["stable_cores"]["cores"] == 2
    assert "stable_core_groups" not in out, "the member lists are written to the graph, not returned"


async def test_a_second_run_on_the_same_graph_overwrites_its_columns(rec):
    """Gephi refuses to add a column that exists. The first run creates them; a second run must
    write over them instead of reporting that the consensus could not be written."""
    exists = {"success": False, "error": "Column already exists: consensus_community"}
    rec.responses = plan([STABLE] * 2) + [exists, exists, exists, {"success": True}]

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    assert out["consensus_column"] == "consensus_community"
    assert "consensus_write_failed" not in out


async def test_a_large_graph_returns_summaries_and_writes_per_node_values_to_the_graph(rec):
    """Every node's score and every group's members ran to 141,000 characters on 2,919 nodes."""
    big = {f"n{i}": i % 7 for i in range(400)}
    rec.responses = plan([big] * 2)

    raw = await gephi_mcp.gephi_community_stability(runs=2)
    out = json.loads(raw)

    assert len(raw) < 4_000
    assert "node_stability" not in out and "consensus_groups" not in out
    assert out["consensus_group_sizes"][:1] == [58]
    written = [u["attributes"] for c in rec.calls if c["endpoint"] == "/graph/nodes/attributes"
               for u in c["json"]["updates"]]
    assert len(written) == 400 and all(a["community_stability"] == 1.0 for a in written)


async def test_a_small_graph_still_lists_every_node(rec):
    rec.responses = plan([STABLE] * 2)

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    assert set(out["node_stability"]) == set(STABLE)
    assert out["consensus_groups"]


async def test_after_one_run_finishes_the_rest_get_a_deadline_scaled_to_it(rec):
    """Healthy runs take a fraction of a second; a non-converging one otherwise costs the full
    deadline. Once a run has finished, later runs are stopped much sooner."""
    rec.responses = plan([STABLE] * 3)

    await gephi_mcp.gephi_community_stability(runs=3)

    sent = [c["json"]["timeout_ms"] for c in rec.calls if c["endpoint"] == "/statistics/modularity"]
    assert sent[0] == int(gephi_mcp.MODULARITY_DEADLINE * 1000)
    assert all(t == int(gephi_mcp.MODULARITY_MIN_DEADLINE * 1000) for t in sent[1:])


# ─── The partition the person already had (gephi#2590) ─────────────────────────────────

def held(assignments):
    """GET /graph/nodes for a graph that already holds a partition. Gephi keys node attributes by
    column title, so the column reads "Modularity Class" here, as it does live."""
    return {"success": True, "nodes": [
        {"id": n, "label": n, "attributes": {"Modularity Class": c}}
        for n, c in assignments.items()]}


HAD = {"a": 7, "b": 7, "c": 8, "d": 8}


def partition_writes(calls):
    """Every value written to modularity_class, in order, as (node, value) pairs."""
    return [(u["id"], u["attributes"]["modularity_class"])
            for c in calls if c["endpoint"] == "/graph/nodes/attributes"
            for u in c["json"]["updates"] if "modularity_class" in u["attributes"]]


def after_last_run(rec):
    last = max(i for i, c in enumerate(rec.calls) if c["endpoint"] == "/statistics/modularity")
    return rec.calls[last + 1:]


async def test_the_partition_you_had_is_back_in_modularity_class_afterwards(rec):
    """Every run rewrites modularity_class. The docstring promises the partition you had survives,
    so once the runs are over that column must hold yours again, not the last run's."""
    rec.nodes = held(HAD)
    rec.responses = plan([STABLE, {"a": 1, "b": 2, "c": 2, "d": 2}])

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    assert dict(partition_writes(after_last_run(rec))) == HAD
    assert out["success"] is True
    assert "restored" in out["modularity_class"]
    assert "modularity_class_restore_failed" not in out


async def test_a_restore_that_fails_is_reported_not_claimed(rec):
    rec.nodes = held(HAD)
    rec.responses = plan([STABLE] * 2) + [{"success": False, "error": "Gephi is busy"}]

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    assert "could not be put back" in out["modularity_class_restore_failed"]
    assert out["modularity_class_restore_detail"]["error"] == "Gephi is busy"
    assert "modularity_class" not in out, "a failed restore must not also be reported as done"


async def test_a_restore_that_misses_nodes_is_not_a_restore(rec):
    rec.nodes = held(HAD)
    rec.responses = plan([STABLE] * 2) + [{"success": True, "set": 3, "not_found": 1}]

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    assert "modularity_class_restore_failed" in out


async def test_the_partition_is_put_back_when_a_run_fails_partway(rec):
    rec.nodes = held(HAD)
    rec.responses = plan([STABLE]) + [{"success": False, "error": "Gephi is busy"}]

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=3))

    assert out["success"] is False and "busy" in out["error"]
    assert dict(partition_writes(after_last_run(rec))) == HAD


async def test_with_no_partition_before_the_last_run_is_left_and_the_reply_says_so(rec):
    rec.responses = plan([STABLE] * 2)

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    assert partition_writes(rec.calls) == []
    assert "last" in out["modularity_class"]


async def test_when_the_partition_cannot_be_read_first_nothing_is_run(rec):
    """Running without knowing what was there would overwrite a partition with no way back."""
    rec.nodes = {"success": False, "error": "Gephi did not answer"}

    out = json.loads(await gephi_mcp.gephi_community_stability(runs=2))

    assert out["success"] is False
    assert "/statistics/modularity" not in rec.endpoints()


def profile_route(rec, before, restore=None):
    """gephi_profile_graph's calls, answered by endpoint: it runs modularity on the live graph."""
    async def route(method, endpoint, params=None, json_data=None, timeout=None):
        rec.calls.append({"method": method, "endpoint": endpoint, "json": json_data})
        if endpoint == "/export/gexf":
            return {"success": True, "content": gexf(before)}
        if endpoint == "/statistics/modularity":
            return {"success": True, "modularity": 0.4, "communities": 2}
        if endpoint == "/graph/nodes/attributes":
            return restore or {"success": True, "set": len(before), "not_found": 0}
        return {"success": True, "average_clustering_coefficient": 0.5}
    return route


async def test_profiling_leaves_the_partition_you_had_in_place(rec, monkeypatch):
    monkeypatch.setattr(gephi_mcp.gephi, "request", profile_route(rec, HAD))

    out = json.loads(await gephi_mcp.gephi_profile_graph())

    assert dict(partition_writes(after_last_run(rec))) == {k: str(v) for k, v in HAD.items()}
    assert "restored" in out["modularity_class"]


async def test_a_profile_whose_restore_fails_says_so(rec, monkeypatch):
    failed = {"success": False, "error": "Gephi is busy"}
    monkeypatch.setattr(gephi_mcp.gephi, "request", profile_route(rec, HAD, failed))

    out = json.loads(await gephi_mcp.gephi_profile_graph())

    assert "could not be put back" in out["modularity_class_restore_failed"]
    assert "modularity_class" not in out


async def test_profiling_a_graph_with_no_partition_writes_none(rec, monkeypatch):
    no_partition = gexf(STABLE).replace("Modularity Class", "Something Else")

    async def route(method, endpoint, params=None, json_data=None, timeout=None):
        rec.calls.append({"method": method, "endpoint": endpoint, "json": json_data})
        if endpoint == "/export/gexf":
            return {"success": True, "content": no_partition}
        return {"success": True, "modularity": 0.4}
    monkeypatch.setattr(gephi_mcp.gephi, "request", route)

    out = json.loads(await gephi_mcp.gephi_profile_graph())

    assert "/graph/nodes/attributes" not in rec.endpoints()
    assert "modularity_class" not in out and "modularity_class_restore_failed" not in out
