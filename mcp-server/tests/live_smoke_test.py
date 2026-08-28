"""Live integration smoke test — exercises ALL MCP tools against a running Gephi.

NOT a unit test (no `test_` prefix, so pytest does not auto-collect it): it needs
Gephi Desktop running with the Gephi MCP plugin on 127.0.0.1:8080. Run it by hand
as part of the release checklist.

    PYTHONPATH=. uv run --with mcp --with httpx --with pydantic \
        python tests/live_smoke_test.py

Standard: ALWAYS test at scale — ~1000 nodes and many edges, never a toy graph.
Small graphs hide real bugs (e.g. the visual_qa title-vs-id partition bug was
invisible at 8 nodes) and say nothing about performance. This harness builds a
1000-node / ~4300-edge stochastic-block graph with 8 communities, hubs, and
typed+weighted edges, then runs every tool in dependency order (reads and computes
first, mutations and destructive ops last) with per-tool timing.
"""

import asyncio
import json
import random
import time

from mcp.types import CallToolResult

import gephi_mcp as g

GEXF = "/tmp/gephi_smoke_big.gexf"

# KNOWN BUG (tracked, see RELEASING.md): visual_qa / label_clusters /
# community_layout resolve a partition column by its TITLE, while
# color_by_partition / color_edges_by_partition / color_by_ranking resolve by
# its ID. Gephi's modularity column is id="modularity_class" /
# title="Modularity Class", so no single string works for both families. This
# harness passes each tool the form it currently accepts; the consistency check
# at the end fails until the id-or-title fix lands.


def build_big_gexf(path: str, n: int = 1000, k: int = 8) -> tuple[int, int]:
    random.seed(42)
    per = n // k
    comm = {i: i // per for i in range(n)}
    hubs = {c: [c * per + j for j in range(3)] for c in range(k)}
    edges: dict[tuple[int, int], tuple[str, int]] = {}

    def add(u, v, rel, w):
        if u == v:
            return
        key = (min(u, v), max(u, v))
        edges.setdefault(key, (rel, w))

    for i in range(n):
        c = comm[i]
        lo, hi = c * per, c * per + per
        for _ in range(random.randint(3, 6)):
            v = random.choice(hubs[c]) if random.random() < 0.55 else random.randint(lo, hi - 1)
            add(i, v, "intra", random.randint(2, 6))
    for _ in range(700):
        ca, cb = random.sample(range(k), 2)
        u = random.choice(hubs[ca]) if random.random() < 0.6 else random.randint(ca * per, ca * per + per - 1)
        v = random.choice(hubs[cb]) if random.random() < 0.6 else random.randint(cb * per, cb * per + per - 1)
        add(u, v, "cross", 1)

    with open(path, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">'
                '<graph mode="static" defaultedgetype="undirected">\n')
        f.write('<attributes class="node"><attribute id="team" title="team" type="string"/></attributes>\n')
        f.write('<attributes class="edge"><attribute id="rel" title="rel" type="string"/></attributes>\n')
        f.write("<nodes>\n")
        for i in range(n):
            f.write(f'<node id="n{i}" label="n{i}"><attvalues>'
                    f'<attvalue for="team" value="C{comm[i]}"/></attvalues></node>\n')
        f.write("</nodes>\n<edges>\n")
        for eid, ((u, v), (rel, w)) in enumerate(edges.items()):
            f.write(f'<edge id="e{eid}" source="n{u}" target="n{v}" weight="{w}"><attvalues>'
                    f'<attvalue for="rel" value="{rel}"/></attvalues></edge>\n')
        f.write("</edges>\n</graph></gexf>\n")
    return n, len(edges)


class Runner:
    def __init__(self):
        self.results: list[tuple[str, str, float, str]] = []

    async def run(self, label, coro):
        t = time.perf_counter()
        try:
            r = await coro
            dt = time.perf_counter() - t
            if isinstance(r, CallToolResult):  # MCP App tools (view_graph) return this
                self.results.append(("PASS", label, dt, "CallToolResult (MCP App resource)"))
                return
            s = r if isinstance(r, str) else json.dumps(r)
            try:
                obj = json.loads(s)
                bad = isinstance(obj, dict) and (obj.get("success") is False or "error" in obj)
            except Exception:
                bad = False
            status = "FAIL" if bad else "PASS"
            self.results.append((status, label, dt, s[:120].replace("\n", " ")))
        except Exception as e:  # noqa: BLE001
            self.results.append(("ERR", label, time.perf_counter() - t, str(e)[:120]))

    def report(self):
        print(f"\n{'STATUS':6} {'TIME':>7}  TOOL")
        print("-" * 78)
        for status, label, dt, msg in self.results:
            print(f"{status:6} {dt:6.2f}s  {label}")
            if status != "PASS":
                print(f"                 └─ {msg}")
        p = sum(1 for r in self.results if r[0] == "PASS")
        f = sum(1 for r in self.results if r[0] == "FAIL")
        e = sum(1 for r in self.results if r[0] == "ERR")
        print("-" * 78)
        print(f"TOTAL {len(self.results)} tools   PASS {p}   FAIL {f}   ERR {e}")


async def main():
    n, m = build_big_gexf(GEXF)
    print(f"Built {GEXF}: {n} nodes / {m} edges (avg degree {2 * m / n:.1f})")
    R = Runner()

    # ---- setup ----
    await R.run("health_check", g.gephi_health_check())
    await R.run("create_project", g.gephi_create_project("smoke"))
    await R.run("import_gexf", g.gephi_import_gexf(GEXF))

    # ---- statistics / compute ----
    for label, coro in [
        ("compute_degree", g.gephi_compute_degree()),
        ("compute_betweenness", g.gephi_compute_betweenness()),
        ("compute_pagerank", g.gephi_compute_pagerank()),
        ("compute_connected_components", g.gephi_compute_connected_components()),
        ("compute_clustering_coefficient", g.gephi_compute_clustering_coefficient()),
        ("compute_avg_path_length", g.gephi_compute_avg_path_length()),
        ("compute_hits", g.gephi_compute_hits()),
        ("compute_eigenvector", g.gephi_compute_eigenvector()),
        ("compute_modularity", g.gephi_compute_modularity(1.0)),
        ("profile_graph", g.gephi_profile_graph(include_slow=False)),
        ("list_statistics", g.gephi_list_statistics()),
    ]:
        await R.run(label, coro)
    await R.run("run_statistic(Degree)", g.gephi_run_statistic("Degree"))

    # ---- reads ----
    for label, coro in [
        ("get_project_info", g.gephi_get_project_info()),
        ("get_graph_stats", g.gephi_get_graph_stats()),
        ("get_graph_type", g.gephi_get_graph_type()),
        ("get_columns", g.gephi_get_columns("node")),
        ("query_nodes", g.gephi_query_nodes(limit=5)),
        ("get_node(n0)", g.gephi_get_node("n0")),
        ("query_edges", g.gephi_query_edges(limit=5)),
        ("get_timeline", g.gephi_get_timeline()),
        ("column_value_frequencies(team)", g.gephi_column_value_frequencies("team")),
        ("detect_duplicates(team)", g.gephi_detect_duplicates("team")),
        ("compare_nodes(n0,n999,Degree)", g.gephi_compare_nodes("n0", "n999", "Degree")),
        ("get_selection", g.gephi_get_selection()),
        ("get_perspective", g.gephi_get_perspective()),
        ("get_preview_settings", g.gephi_get_preview_settings()),
        ("get_available_layouts", g.gephi_get_available_layouts()),
        ("get_layout_status", g.gephi_get_layout_status()),
        ("get_layout_properties(ForceAtlas2)", g.gephi_get_layout_properties("ForceAtlas2")),
        ("list_workspaces", g.gephi_list_workspaces()),
        ("list_filters", g.gephi_list_filters()),
    ]:
        await R.run(label, coro)

    # ---- appearance / style ----
    for label, coro in [
        ("color_by_partition(modularity_class)", g.gephi_color_by_partition("modularity_class")),
        ("color_edges_by_partition(rel)", g.gephi_color_edges_by_partition("rel")),
        ("color_by_ranking(Degree)", g.gephi_color_by_ranking("Degree")),
        ("size_by_ranking(Degree)", g.gephi_size_by_ranking("Degree")),
        ("edge_thickness_by_weight", g.gephi_edge_thickness_by_weight()),
        ("set_preview_settings", g.gephi_set_preview_settings({"edge.opacity": 40})),
        ("label_clusters(Modularity Class)", g.gephi_label_clusters("Modularity Class")),
        ("set_node_color(n0)", g.gephi_set_node_color("n0", 200, 30, 30)),
        ("set_node_size(n0)", g.gephi_set_node_size("n0", 40)),
        ("batch_set_node_colors", g.gephi_batch_set_node_colors(
            [{"id": "n1", "r": 10, "g": 10, "b": 200}])),
        ("visual_qa(Modularity Class)", g.gephi_visual_qa("Modularity Class")),
        ("reset_appearance", g.gephi_reset_appearance()),
    ]:
        await R.run(label, coro)

    # ---- layouts ---- (poll-stop any leftover layout so run_layout is clean)
    for _ in range(10):
        await g.gephi_stop_layout()
        st = json.loads(await g.gephi_get_layout_status())
        if not st.get("running"):
            break
        await asyncio.sleep(0.5)
    await R.run("set_layout_properties(FA2)", g.gephi_set_layout_properties(
        "ForceAtlas2", {"scalingRatio": 5.0}))
    await R.run("run_layout(ForceAtlas2,100)", g.gephi_run_layout("ForceAtlas2", iterations=100))
    await asyncio.sleep(2)
    await R.run("stop_layout", g.gephi_stop_layout())
    await R.run("similarity_layout", g.gephi_similarity_layout())
    await R.run("community_layout", g.gephi_community_layout(partition_column="Modularity Class"))
    await R.run("focus_view(graph)", g.gephi_focus_view("graph"))
    await R.run("set_selection_mode(rectangle)", g.gephi_set_selection_mode("rectangle"))

    # ---- view / narrative ----
    await R.run("view_graph", g.gephi_view_graph(max_nodes=300))

    # ---- exports (to /tmp) ----
    for label, coro in [
        ("export_gexf", g.gephi_export_gexf("/tmp/smoke.gexf")),
        ("export_graphml", g.gephi_export_graphml("/tmp/smoke.graphml")),
        ("export_csv", g.gephi_export_csv("/tmp/smoke.csv")),
        ("export(gdf)", g.gephi_export("/tmp/smoke.gdf", "gdf")),
        ("export_png", g.gephi_export_png("/tmp/smoke.png", 1200, 900)),
        ("export_screenshot", g.gephi_export_screenshot("/tmp/smoke_screenshot.png", scale=2)),
        ("export_pdf", g.gephi_export_pdf("/tmp/smoke.pdf")),
        ("export_svg", g.gephi_export_svg("/tmp/smoke.svg")),
    ]:
        await R.run(label, coro)

    # ---- filters / extraction (mutate visible/workspaces) ----
    await R.run("filter_by_degree(dry_run)", g.gephi_filter_by_degree(min=10, dry_run=True))
    await R.run("filter_by_edge_weight(dry_run)", g.gephi_filter_by_edge_weight(min=3, dry_run=True))
    await R.run("apply_filter(Degree Range,select)",
                g.gephi_apply_filter("Degree Range", {"range": [5, 999]}, "select"))
    await R.run("reset_filters", g.gephi_reset_filters())
    await R.run("extract_ego_network(n0)", g.gephi_extract_ego_network("n0", depth=1))
    await R.run("extract_backbone", g.gephi_extract_backbone())

    # re-import a clean full graph for the mutation phase
    await R.run("create_project#2", g.gephi_create_project("smoke-mutate"))
    await R.run("import_gexf#2", g.gephi_import_gexf(GEXF))
    await R.run("extract_giant_component", g.gephi_extract_giant_component())
    await R.run("remove_isolates", g.gephi_remove_isolates())

    # ---- data-lab / mutations ----
    await R.run("add_column(note,string)", g.gephi_add_column("note", "string", "node"))
    await R.run("add_node(z1)", g.gephi_add_node("z1", "z1"))
    await R.run("add_nodes(z2,z3)", g.gephi_add_nodes([{"id": "z2"}, {"id": "z3"}]))
    await R.run("set_node_label(z1)", g.gephi_set_node_label("z1", "zed1"))
    await R.run("set_node_position(z1)", g.gephi_set_node_position("z1", 5.0, 5.0))
    await R.run("batch_set_positions", g.gephi_batch_set_positions(
        [{"id": "z2", "x": 1.0, "y": 1.0}]))
    await R.run("set_node_attributes(z1)", g.gephi_set_node_attributes("z1", {"note": "hi"}))
    await R.run("batch_set_node_attributes", g.gephi_batch_set_node_attributes(
        [{"id": "z2", "attributes": {"note": "yo"}}]))
    await R.run("add_edge(z1,z2)", g.gephi_add_edge("z1", "z2", weight=2.0, directed=False))
    await R.run("add_edges(z1-z3)", g.gephi_add_edges(
        [{"source": "z1", "target": "z3", "weight": 1.0}]))
    await R.run("set_edge_weight(z1,z2)", g.gephi_set_edge_weight("z1", "z2", 3.0))
    await R.run("set_edge_label(z1,z2)", g.gephi_set_edge_label("z1", "z2", "link"))
    await R.run("set_edge_color(z1,z2)", g.gephi_set_edge_color("z1", "z2", 10, 200, 10))
    await R.run("set_edge_attributes(z1,z2)", g.gephi_set_edge_attributes("z1", "z2", {"rel": "test"}))
    await R.run("add_column(edge:tag)", g.gephi_add_column("tag", "string", "edge"))
    await R.run("create_regex_column(team)", g.gephi_create_regex_column("team", "isC0", "C0"))
    await R.run("remove_edge(z1,z2)", g.gephi_remove_edge("z1", "z2"))  # clean, before merge
    await R.run("merge_nodes(z2,z3)", g.gephi_merge_nodes(["z2", "z3"], into="z2"))
    await R.run("remove_node(z1)", g.gephi_remove_node("z1"))
    await R.run("bulk_remove_nodes", g.gephi_bulk_remove_nodes(["z2"]))
    await R.run("whatif(remove n0)", g.gephi_whatif([{"op": "remove_node", "id": "n0"}]))

    # ---- workspace ops ----
    await R.run("new_workspace", g.gephi_new_workspace())
    await R.run("rename_workspace", g.gephi_rename_workspace(1, "renamed"))
    await R.run("duplicate_workspace", g.gephi_duplicate_workspace(0))
    await R.run("switch_workspace(0)", g.gephi_switch_workspace(0))

    # ---- project save/open round-trip ----
    await R.run("save_project", g.gephi_save_project("/tmp/smoke.gephi"))
    await R.run("open_project", g.gephi_open_project("/tmp/smoke.gephi"))

    # ---- import round-trips (fresh projects) ----
    await R.run("create_project#gml", g.gephi_create_project("gml"))
    await R.run("import_graphml", g.gephi_import_graphml("/tmp/smoke.graphml"))
    await R.run("create_project#file", g.gephi_create_project("file"))
    await R.run("import_file(gexf)", g.gephi_import_file(GEXF))
    await R.run("create_project#csv", g.gephi_create_project("csv"))
    await R.run("import_csv", g.gephi_import_csv("/tmp/smoke.csv"))

    # ---- text network (own workspace) ----
    await R.run("create_project#text", g.gephi_create_project("text"))
    await R.run("text_to_network", g.gephi_text_to_network(
        "teams that trust the tools adopt them faster and build more trust", clear_existing=True))

    # ---- perspective ----
    await R.run("switch_perspective(Overview)", g.gephi_switch_perspective("Overview"))

    # ---- id/title consistency probe (documents the known bug) ----
    # A single canonical column string ('modularity_class', the id the skill uses)
    # should satisfy BOTH the coloring family and the qa/label/community family.
    # It does not today: the qa/label/community family matches by title. This
    # probe FAILS until the id-or-title fix lands, then flips to PASS.
    await R.run("create_project#probe", g.gephi_create_project("probe"))
    await R.run("import_gexf#probe", g.gephi_import_gexf(GEXF))
    await R.run("compute_modularity#probe", g.gephi_compute_modularity(1.0))
    # explicit assertion: with a known 8-community graph, BOTH tools given the
    # SAME id string must resolve it. color resolves by id (ok); visual_qa
    # resolves by title so groups==0 here — a real defect the report surfaces.
    col_ok = "success\": true" in json.dumps(
        json.loads(await g.gephi_color_by_partition("modularity_class")))
    qa = json.loads(await g.gephi_visual_qa("modularity_class"))
    groups = (qa.get("partition") or {}).get("groups", 0)
    both = col_ok and groups > 0
    R.results.append(("PASS" if both else "FAIL",
                      "[consistency] modularity_class works for color AND visual_qa",
                      0.0, f"color_ok={col_ok} visual_qa_groups={groups} (expect 8)"))

    # ---- integrity probes: catch silent success (tool returns ok but did nothing) ----
    # These assert the EFFECT, not just success. open_project in particular used to
    # report success on an empty workspace when a project was already open.
    async def stats_nodes():
        return json.loads(await g.gephi_get_graph_stats()).get("node_count", 0)
    await g.gephi_create_project("integrity")
    await g.gephi_import_gexf(GEXF)
    imp = await stats_nodes()
    R.results.append(("PASS" if imp == 1000 else "FAIL",
                      "[integrity] import loaded the full graph", 0.0,
                      f"node_count={imp} (expect 1000)"))
    # save/open round-trip WITH a project already open (the exact failure condition)
    await g.gephi_save_project("/tmp/smoke_integrity.gephi")
    await g.gephi_create_project("integrity-2")  # a DIFFERENT project is now current
    await g.gephi_import_gexf(GEXF)
    op = json.loads(await g.gephi_open_project("/tmp/smoke_integrity.gephi"))
    restored = op.get("node_count", 0)
    R.results.append(("PASS" if restored == 1000 else "FAIL",
                      "[integrity] open_project restores the graph over an open project",
                      0.0, f"node_count={restored} (expect 1000); warning={op.get('warning')}"))
    # GEXF round-trip restore (the reliable snapshot path)
    await g.gephi_export_gexf("/tmp/smoke_integrity.gexf")
    await g.gephi_clear_graph()
    await g.gephi_import_file("/tmp/smoke_integrity.gexf")
    gexf_restored = await stats_nodes()
    R.results.append(("PASS" if gexf_restored == 1000 else "FAIL",
                      "[integrity] export_gexf + import_file round-trips", 0.0,
                      f"node_count={gexf_restored} (expect 1000)"))
    # duplicate-workspace undo: destructive op on a copy leaves the original intact
    await g.gephi_create_project("integrity-undo")
    await g.gephi_import_gexf(GEXF)
    await g.gephi_duplicate_workspace(0)
    await g.gephi_filter_by_degree(min=50)  # destroys the copy
    await g.gephi_switch_workspace(0)
    undo_nodes = await stats_nodes()
    R.results.append(("PASS" if undo_nodes == 1000 else "FAIL",
                      "[integrity] duplicate_workspace gives a clean undo", 0.0,
                      f"original after undo={undo_nodes} (expect 1000)"))

    # one-level undo: a destructive tool auto-snapshots, gephi_undo restores at 1000n
    await g.gephi_create_project("integrity-auto-undo")
    await g.gephi_import_gexf(GEXF)
    t0 = time.perf_counter()
    fil = json.loads(await g.gephi_filter_by_degree(min=50))  # auto-snapshot + destroy
    filter_dt = time.perf_counter() - t0
    after_filter = await stats_nodes()
    t0 = time.perf_counter()
    und = json.loads(await g.gephi_undo())
    undo_dt = time.perf_counter() - t0
    restored_nodes = await stats_nodes()
    auto_ok = (fil.get("undo_available") is True and after_filter < 1000
               and und.get("success") is True and restored_nodes == 1000)
    R.results.append(("PASS" if auto_ok else "FAIL",
                      "[integrity] auto-snapshot + gephi_undo restores the graph",
                      filter_dt + undo_dt,
                      f"undo_available={fil.get('undo_available')} "
                      f"after_filter={after_filter} restored={restored_nodes} "
                      f"(expect 1000); filter+snap {filter_dt:.2f}s undo {undo_dt:.2f}s"))
    # rolling snapshot: two manual snapshots leave exactly one [undo] workspace
    await R.run("snapshot(first)", g.gephi_snapshot("first"))
    await R.run("snapshot(second, rolls first)", g.gephi_snapshot("second"))
    wss = json.loads(await g.gephi_list_workspaces()).get("workspaces", [])
    snap_count = sum(1 for w in wss if str(w.get("name", "")).startswith("[undo] "))
    R.results.append(("PASS" if snap_count == 1 else "FAIL",
                      "[integrity] rolling snapshot keeps exactly one undo point",
                      0.0, f"snapshot workspaces={snap_count} (expect 1)"))
    # undo consumes the snapshot; a second undo must error cleanly, not crash
    await R.run("undo", g.gephi_undo())
    second = json.loads(await g.gephi_undo())
    R.results.append(("PASS" if second.get("success") is False else "FAIL",
                      "[integrity] second undo reports nothing-to-undo", 0.0,
                      str(second.get("error", ""))[:100]))

    # ---- edge-case scenarios: directed + empty graphs must not crash the tools ----
    # Directed graph: in/out degree, directional pagerank, layout, export.
    await g.gephi_create_project("directed")
    await g.gephi_add_nodes([{"id": "d1"}, {"id": "d2"}, {"id": "d3"}])
    await g.gephi_add_edge("d1", "d2", 1.0, True)
    await g.gephi_add_edge("d2", "d3", 1.0, True)
    await g.gephi_add_edge("d3", "d1", 1.0, True)
    gtype = json.loads(await g.gephi_get_graph_type())
    dir_ok = True
    for coro in (g.gephi_compute_degree(), g.gephi_compute_pagerank(),
                 g.gephi_run_layout("ForceAtlas 2", iterations=30, sync=True),
                 g.gephi_export_gexf("/tmp/directed.gexf")):
        if json.loads(await coro).get("success") is False:
            dir_ok = False
    R.results.append(("PASS" if dir_ok else "FAIL",
                      "[edge-case] directed graph: degree/pagerank/layout/export",
                      0.0, f"is_directed={gtype.get('is_directed', gtype.get('directed'))}"))

    # Empty graph: read/compute tools must degrade gracefully, not throw.
    await g.gephi_create_project("empty")
    empty_ok = True
    for label, coro in (("stats", g.gephi_get_graph_stats()),
                        ("profile", g.gephi_profile_graph()),
                        ("visual_qa", g.gephi_visual_qa()),
                        ("query_nodes", g.gephi_query_nodes(limit=5)),
                        ("compute_degree", g.gephi_compute_degree())):
        try:
            json.loads(await coro)  # any valid JSON (success or a clean error) is fine
        except Exception:
            empty_ok = False
    R.results.append(("PASS" if empty_ok else "FAIL",
                      "[edge-case] empty graph: read/compute tools degrade gracefully",
                      0.0, "no exceptions on a 0-node graph"))

    # ---- DESTRUCTIVE LAST ----
    await R.run("clear_graph", g.gephi_clear_graph())
    await R.run("delete_workspace(0)", g.gephi_delete_workspace(0))

    R.report()


if __name__ == "__main__":
    asyncio.run(main())
