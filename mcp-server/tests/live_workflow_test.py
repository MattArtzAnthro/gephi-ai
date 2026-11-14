"""Live workflow test: the properties a session depends on, checked across tool calls.

NOT a unit test (no `test_` prefix, so pytest does not collect it). The unit suite replaces
`gephi.request` with a recorder, so it never runs `GephiClient.request`, which is where cached
graph facts are dropped and the session record is reset. The live smoke test calls every tool
once and checks that each answers. Neither checks what holds ACROSS calls, and that is where
three defects hid in 1.23.0: a partition overwritten by the stability check, a receipt that
named the wrong layout, and an edge-weight caveat that went silent after a profile.

This drives the real tools, through the real client, against a running Gephi, on several kinds
of network, and checks each property after the calls that could break it:

    partition_survives     modularity_class is unchanged by profile, stability and whatif
    stability_randomized   stability runs are randomized, and say so if Gephi refuses
    weight_caveat          on a weighted graph, betweenness after profile + stability carries
                           the edge-weight caveat (gephi#557)
    param_caveat           modularity at a non-default resolution carries gephi#2034
    receipt_layout         the receipt names the layout that placed the nodes
    weight_caveat_after_layout  the edge-weight caveat still fires after a computed layout
    receipt_resolution     after stability puts the partition back, the receipt gives the
                           resolution of the partition in the column, not the stability run's
    receipt_survives       a whatif leaves the receipt's legend and statistics in place
    partition_fit          visual_qa reads a known grouping and gives a separation
    claim_receipts         a claim with live values verifies; one with a wrong value does not
    compare_missing        comparing on a metric not yet computed is an error, not a number
    undo_restores          snapshot, a destructive filter, then undo restores the node count
    two_mode_tools         (two-mode networks) bipartite layout is in the receipt; projection runs
    timeline               (timestamped networks) Gephi reads the network as dynamic, over its range
    time_slice             (timestamped networks) a slice holds the nodes present in its window
    components_read        the profile counts components and isolates as networkx does, and
                           flags them by its own rules
    event_log_read         (the dated event log, imported as CSV) a profile either reads the
                           graph or fails naming the time column Gephi's GEXF exporter cannot
                           write; after that column is converted to text, the profile reads it

Every network gets its own project, so this DISCARDS the project open in that Gephi. Run it
against a second Gephi on its own port (see live_smoke_test.py for the command); GEPHI_API_URL
must be set, so it never reaches a Gephi on the default port by accident:

    GEPHI_API_URL=http://127.0.0.1:8091 PYTHONPATH=. uv run --with networkx \\
        python tests/live_workflow_test.py

Generated networks run everywhere. Set GEPHI_TEST_NETWORKS to a folder of networks, one
sub-folder each holding nodes.csv (id,label) and edges.csv (source,target), to add them; the
label column becomes the known grouping. Exit status is 1 when any property fails.
"""

import asyncio
import csv
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import gephi_mcp as g

if TYPE_CHECKING:
    import networkx as nx


def tool(t: Any) -> Any:
    return getattr(t, "fn", t)


async def call(t: Any, **kw: Any) -> dict[str, Any]:
    out = await tool(t)(**kw)
    structured = getattr(out, "structured_content", None) or getattr(out, "structuredContent", None)
    if structured is not None:
        return dict(structured)
    texts = [c.text for c in getattr(out, "content", []) if hasattr(c, "text")] or [out]
    for text in texts:
        try:
            return dict(json.loads(text))
        except (TypeError, ValueError):
            continue
    raise ValueError(f"{getattr(t, 'name', t)} returned no JSON: {str(texts[0])[:120]}")


# ── Networks ──────────────────────────────────────────────────────────────────────────────


def from_folder(folder: Path) -> "nx.Graph | None":
    import networkx as nx

    nodes, edges = folder / "nodes.csv", folder / "edges.csv"
    if not (nodes.exists() and edges.exists()):
        return None
    graph = nx.Graph()
    with nodes.open(newline="") as f:
        for row in csv.DictReader(f):
            graph.add_node(str(row["id"]), group=str(row.get("label") or "none"))
    with edges.open(newline="") as f:
        for row in csv.DictReader(f):
            graph.add_edge(str(row["source"]), str(row["target"]))
    return graph


def networks() -> dict[str, "nx.Graph"]:
    from network_types import generated

    nets = generated()
    root = os.environ.get("GEPHI_TEST_NETWORKS")
    if root:
        for sub in sorted(Path(root).iterdir()):
            if sub.is_dir() and (graph := from_folder(sub)) is not None:
                nets[sub.name] = graph
    return nets


# ── Properties ────────────────────────────────────────────────────────────────────────────


async def partition() -> dict[str, Any]:
    read = await g._current_partition()
    return read.get("partition", {}) if isinstance(read, dict) else {}


async def check(name: str, graph: "nx.Graph", workdir: Path) -> list[tuple[str, bool, str]]:
    import networkx as nx

    results: list[tuple[str, bool, str]] = []

    def record(prop: str, ok: Any, detail: str = "") -> None:
        results.append((prop, bool(ok), detail))

    weighted = len({d.get("weight", 1.0) for _, _, d in graph.edges(data=True)}) > 1
    has_group = any("group" in d for _, d in graph.nodes(data=True))
    path = workdir / f"{abs(hash(name))}.gexf"
    nx.write_gexf(graph, path)

    await call(g.gephi_create_project, name=name)
    imported = await call(g.gephi_import_file, file=str(path))
    if not imported.get("success"):
        record("import", False, str(imported)[:200])
        return results

    # The person's partition, which every later analysis must leave alone.
    await call(g.gephi_compute_modularity)
    mine = await partition()

    await call(g.gephi_profile_graph)
    after_profile = await partition()
    stab = await call(g.gephi_community_stability, runs=5)
    after_stability = await partition()
    record("partition_survives", bool(mine) and mine == after_profile == after_stability,
           f"{len(mine)} nodes; profile {'kept' if mine == after_profile else 'CHANGED'}, "
           f"stability {'kept' if mine == after_stability else 'CHANGED'}")
    record("stability_randomized", stab.get("success") and "randomize_warning" not in stab,
           f"{stab.get('distinct_partitions')} partitions in 5 runs, "
           f"mean {stab.get('mean_stability')}")

    btw = await call(g.gephi_compute_betweenness)
    ids = {c["id"] for c in btw.get("caveats", [])}
    if weighted:
        record("weight_caveat", "gephi-557" in ids, f"caveats {sorted(ids)}")
    else:
        record("weight_caveat", "gephi-557" not in ids, f"unweighted; caveats {sorted(ids)}")

    mod2 = await call(g.gephi_compute_modularity, resolution=2.0)
    record("param_caveat", "gephi-2034" in {c["id"] for c in mod2.get("caveats", [])})
    await call(g.gephi_compute_modularity)
    mine = await partition()

    await call(g.gephi_compute_degree)
    await call(g.gephi_size_by_ranking, column="degree")
    await call(g.gephi_run_layout, algorithm="ForceAtlas 2", iterations=200, sync=True)
    await call(g.gephi_community_layout, partition_column="modularity_class")
    receipt = await call(g.gephi_session_receipt)
    layout = (receipt.get("layout") or {}).get("algorithm")
    record("receipt_layout", layout == "gephi_community_layout", f"receipt layout: {layout}")

    btw2 = await call(g.gephi_compute_betweenness)
    ids2 = {c["id"] for c in btw2.get("caveats", [])}
    record("weight_caveat_after_layout", ("gephi-557" in ids2) == weighted,
           f"{'weighted' if weighted else 'unweighted'}; caveats after layout {sorted(ids2)}")

    # The receipt must describe the partition in the column: a stability run at another
    # resolution puts the person's partition back, so its own resolution is not that partition's.
    await call(g.gephi_compute_modularity, resolution=0.5)
    await call(g.gephi_community_stability, runs=2, resolution=2.0)
    stats = (await call(g.gephi_session_receipt)).get("statistics", [])
    said = [st.get("params", {}).get("resolution") for st in stats if st.get("metric") == "modularity"]
    record("receipt_resolution", said[-1:] == [0.5], f"receipt says resolution {said[-1:]}")
    await call(g.gephi_compute_modularity)
    mine = await partition()

    top = max(graph.degree, key=lambda kv: kv[1])[0]
    before = await call(g.gephi_session_receipt)
    whatif = await call(g.gephi_whatif, edits=[{"op": "remove_node", "id": str(top)}])
    after = await call(g.gephi_session_receipt)
    record("receipt_survives",
           whatif.get("success") and after.get("legend") == before.get("legend")
           and after.get("statistics") == before.get("statistics")
           and await partition() == mine,
           f"legend {len(before.get('legend', []))}->{len(after.get('legend', []))}, "
           f"statistics {len(before.get('statistics', []))}->{len(after.get('statistics', []))}")

    if has_group:
        qa = await call(g.gephi_visual_qa, partition_column="group")
        part = qa.get("partition") or {}
        record("partition_fit", part.get("separation") is not None and part.get("groups", 0) > 1,
               f"{part.get('groups')} groups, verdict {part.get('verdict')}, "
               f"separation {part.get('separation')}")

    modes = {d.get("mode") for _, d in graph.nodes(data=True)} - {None}
    if modes == {"person", "event"}:
        laid = await call(g.gephi_bipartite_layout, mode_column="mode")
        layout = ((await call(g.gephi_session_receipt)).get("layout") or {}).get("algorithm")
        projected = await call(g.gephi_bipartite_projection, mode_column="mode", keep="person")
        record("two_mode_tools", laid.get("success") and layout == "gephi_bipartite_layout"
               and projected.get("success"),
               f"layout ok={laid.get('success')}, receipt {layout}, "
               f"projection ok={projected.get('success')}")
        await call(g.gephi_switch_workspace, index=0)
    if graph.graph.get("mode") == "dynamic":
        timeline = await call(g.gephi_get_timeline)
        first, last = (min(d["start"] for _, d in graph.nodes(data=True)),
                       max(d["start"] for _, d in graph.nodes(data=True)))
        record("timeline", timeline.get("graph_is_dynamic") is True
               and timeline.get("time_min") == first and timeline.get("time_max") == last,
               f"dynamic={timeline.get('graph_is_dynamic')}, "
               f"{timeline.get('time_min')} to {timeline.get('time_max')}")
        sliced = await call(g.gephi_time_slice, start=float(first), end=float(first + 2))
        present = sum(1 for _, d in graph.nodes(data=True) if d["start"] <= first + 2)
        record("time_slice", sliced.get("success") and sliced.get("node_count") == present,
               f"slice holds {sliced.get('node_count')} nodes, expected {present}")
        await call(g.gephi_switch_workspace, index=0)
    # The profile's own rules: an isolates flag whenever there are isolates, a fragmentation flag
    # when the largest component holds under 90% of nodes. Its counts must match networkx's.
    undirected = graph.to_undirected()
    comps = [len(c) for c in nx.connected_components(undirected)]
    isolates = sum(1 for _, k in undirected.degree if k == 0)
    giant = max(comps) / graph.number_of_nodes()
    prof = await call(g.gephi_profile_graph)
    flags = " ".join(prof.get("flags", []))
    record("components_read",
           prof.get("components", {}).get("count") == len(comps)
           and prof.get("isolates") == isolates
           and ("fragmented" in flags) == (len(comps) > 1 and giant < 0.9)
           and ("isolated" in flags) == (isolates > 0),
           f"{len(comps)} components (profile {prof.get('components', {}).get('count')}), "
           f"{isolates} isolates (profile {prof.get('isolates')}), largest {giant:.0%}")

    node = (await call(g.gephi_get_node, id=str(top))).get("node", {})
    live = (node.get("attributes") or {}).get("Betweenness Centrality")
    good = await call(g.gephi_claim_record, claim="hub brokers", classification="centrality",
                      verdict="confirmed", metric="Betweenness Centrality", nodes=[str(top)],
                      values={str(top): live})
    bad = await call(g.gephi_claim_record, claim="hub brokers", classification="centrality",
                     verdict="confirmed", metric="Betweenness Centrality", nodes=[str(top)],
                     values={str(top): (live or 0) + 1000.0})
    record("claim_receipts", good.get("verified") is True and bad.get("verified") is False,
           f"live value {live}: verified={good.get('verified')}; "
           f"wrong value verified={bad.get('verified')}")

    other = next(n for n in graph.nodes if n != top)
    cmp = await call(g.gephi_compare_nodes, id_a=str(top), id_b=str(other), metric="pageranks")
    record("compare_missing", cmp.get("success") is False, str(cmp.get("error", ""))[:80])

    count = (await call(g.gephi_get_graph_stats)).get("node_count")
    await call(g.gephi_snapshot, label="live workflow")
    await call(g.gephi_filter_by_degree, min=3)
    undone = await call(g.gephi_undo)
    restored = (await call(g.gephi_get_graph_stats)).get("node_count")
    record("undo_restores", undone.get("success") and restored == count, f"{count} -> {restored}")
    return results


async def check_event_log(workdir: Path) -> list[tuple[str, bool, str]]:
    """A dated edge list imported as CSV: Gephi makes `date` a column holding a set of times."""
    from network_types import event_log_rows

    path = workdir / "event_log.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "target", "date"])
        writer.writerows(event_log_rows())
    await call(g.gephi_create_project, name="dated event log")
    imported = await call(g.gephi_import_file, file=str(path))
    if not imported.get("success"):
        return [("import", False, str(imported)[:200])]
    first = await call(g.gephi_profile_graph)
    if first.get("success", True):
        return [("event_log_read", first.get("nodes") == 60, f"read: {first.get('nodes')} nodes")]
    blocking = [c["column"] for c in first.get("blocking_columns", [])]
    for column in blocking:
        await call(g.gephi_edit_column, column=column, action="convert", target="edge",
                   type="string")
    second = await call(g.gephi_profile_graph)
    ok = blocking == ["date"] and second.get("success", True) and second.get("nodes") == 60
    return [("event_log_read", ok, f"export refused on {blocking}; after converting, "
                                   f"{second.get('nodes')} nodes read")]


async def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        print("\n== dated event log (CSV): 1500 rows")
        for prop, ok, detail in await check_event_log(Path(tmp)):
            failures += not ok
            print(f"  {'PASS' if ok else 'FAIL'}  {prop:22s} {detail}")
        for name, graph in networks().items():
            kind = "directed" if graph.is_directed() else "undirected"
            print(f"\n== {name}: {graph.number_of_nodes()} nodes, "
                  f"{graph.number_of_edges()} edges, {kind}")
            try:
                rows = await check(name, graph, Path(tmp))
            except Exception as exc:  # a crash is a failure of the run, reported, not hidden
                import traceback
                where = [f for f in traceback.extract_tb(exc.__traceback__)
                         if f.filename.endswith("live_workflow_test.py")][-1]
                rows = [("run", False, f"{type(exc).__name__}: {exc} (line {where.lineno}: "
                                       f"{where.line})")]
            for prop, ok, detail in rows:
                failures += not ok
                print(f"  {'PASS' if ok else 'FAIL'}  {prop:22s} {detail}")
    print(f"\n{'FAILED' if failures else 'ALL PASSED'}: {failures} failing propert"
          f"{'y' if failures == 1 else 'ies'}")
    return 1 if failures else 0


if __name__ == "__main__":
    if not os.environ.get("GEPHI_API_URL"):
        sys.exit("Set GEPHI_API_URL to a Gephi you can discard work in (e.g. a second Gephi "
                 "on 8091).")
    sys.exit(asyncio.run(main()))
