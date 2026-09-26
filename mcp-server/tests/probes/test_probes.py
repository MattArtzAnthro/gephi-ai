"""Probes: do the defects in the caveat register still happen on THIS Gephi?

The register would otherwise be a reading of the tracker. Most of its entries were reported against
Gephi 0.9.2 or 0.10.1 and gephi-ai targets 0.11.1+, and an open issue is evidence that nobody
closed it, not proof the bug survives. `gephi_health_check` reports the plugin version but not the
Gephi Desktop version, so the register cannot version-gate itself either.

Each probe reproduces one defect against the running Gephi and reports `reproduced` or
`not_reproduced`. An entry only becomes an assertion once its probe confirms it, and an entry whose
probe fails to reproduce stops being surfaced at all.

Two rules govern every probe here.

A probe that could not measure produces NO verdict. It calls `note_failure`, and the register keeps
saying "unverified", which is the truth. Not looking is never the same as finding nothing.

Every probe decides by comparing Gephi against itself, never against a second implementation.
Comparing to an independent implementation of, say, closeness would risk reporting "not reproduced"
because the two use different conventions, which would be a false all-clear in a suite whose whole
purpose is not giving false assurance.

Run them with a Gephi Desktop up and the plugin installed:

    GEPHI_PROBE=1 PYTHONPATH=. uv run pytest tests/probes -v -s

then write the verdicts into the register with:

    GEPHI_PROBE=1 PYTHONPATH=. uv run python tests/probes/record.py
"""

import json
import os

import pytest

import gephi_mcp
from probe_verdicts import Verdicts

pytestmark = pytest.mark.skipif(
    not os.environ.get("GEPHI_PROBE"),
    reason="needs a running Gephi Desktop; set GEPHI_PROBE=1 to run",
)

VERDICTS = Verdicts()


async def call(tool, **kwargs):
    """Run a tool and return its parsed result, or None if Gephi refused."""
    result = json.loads(await tool(**kwargs))
    return result if result.get("success", True) else None


async def community_count(resolution: float):
    """How many communities Gephi found, counted from the partition it wrote.

    The modularity response carries no community count of its own: the number appears only inside
    an HTML report blob. Counting distinct values on the nodes is both simpler and less brittle
    than parsing that.
    """
    from gephi_mcp import _partition_value
    from gephi_mcp_viewer import parse_gexf

    if await call(gephi_mcp.gephi_compute_modularity, resolution=resolution) is None:
        return None
    exported = await call(gephi_mcp.gephi_export_gexf)
    if exported is None or not exported.get("content"):
        return None
    graph = parse_gexf(exported["content"], max_nodes=10**9)
    values = {v for n in graph["nodes"]
              if (v := _partition_value(n.get("attributes", {}))) is not None}
    return len(values) or None


async def ring_of_cliques(groups: int = 8, size: int = 4):
    """A ring of small cliques: structure at more than one scale.

    Unlike two cliques, this has a genuine hierarchy, so the number of communities responds to the
    resolution parameter. A probe about resolution needs a graph where resolution does something.
    """
    nodes, edges = [], []
    for g in range(groups):
        members = [f"g{g}n{i}" for i in range(size)]
        nodes += members
        for i, a in enumerate(members):
            for b in members[i + 1:]:
                edges.append({"source": a, "target": b, "weight": 1.0})
        edges.append({"source": f"g{g}n0",
                      "target": f"g{(g + 1) % groups}n0", "weight": 1.0})
    steps = [
        await call(gephi_mcp.gephi_clear_graph),
        await call(gephi_mcp.gephi_add_nodes, nodes=[{"id": n} for n in nodes]),
        await call(gephi_mcp.gephi_add_edges, edges=edges),
    ]
    return all(s is not None for s in steps)


async def two_cliques():
    """Two 5-cliques joined by a single edge: an unambiguous two-community graph.

    Returns False if any step failed, so a probe can decline to give a verdict rather than
    measuring an empty or half-built graph.
    """
    left = [f"L{i}" for i in range(5)]
    right = [f"R{i}" for i in range(5)]
    edges = []
    for group in (left, right):
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                edges.append({"source": a, "target": b, "weight": 1.0})
    edges.append({"source": "L0", "target": "R0", "weight": 1.0})

    steps = [
        await call(gephi_mcp.gephi_clear_graph),
        await call(gephi_mcp.gephi_add_nodes, nodes=[{"id": n} for n in left + right]),
        await call(gephi_mcp.gephi_add_edges, edges=edges),
    ]
    return all(s is not None for s in steps)


# The character co-appearance network of Les Miserables (Knuth 1993, The Stanford GraphBase),
# unweighted. Gephi's default eigenvector run ranks Valjean first on it; the converged eigenvector
# ranks Gavroche first.
LES_MISERABLES = [
    ("Napoleon", "Myriel"), ("Myriel", "MlleBaptistine"), ("Myriel", "MmeMagloire"), ("Myriel",
    "CountessDeLo"), ("Myriel", "Geborand"), ("Myriel", "Champtercier"), ("Myriel", "Cravatte"),
    ("Myriel", "Count"), ("Myriel", "OldMan"), ("Myriel", "Valjean"), ("MlleBaptistine",
    "MmeMagloire"), ("MlleBaptistine", "Valjean"), ("MmeMagloire", "Valjean"), ("Valjean",
    "Labarre"), ("Valjean", "Marguerite"), ("Valjean", "MmeDeR"), ("Valjean", "Isabeau"),
    ("Valjean", "Gervais"), ("Valjean", "Fantine"), ("Valjean", "MmeThenardier"), ("Valjean",
    "Thenardier"), ("Valjean", "Cosette"), ("Valjean", "Javert"), ("Valjean", "Fauchelevent"),
    ("Valjean", "Bamatabois"), ("Valjean", "Simplice"), ("Valjean", "Scaufflaire"), ("Valjean",
    "Woman1"), ("Valjean", "Judge"), ("Valjean", "Champmathieu"), ("Valjean", "Brevet"), ("Valjean",
    "Chenildieu"), ("Valjean", "Cochepaille"), ("Valjean", "Woman2"), ("Valjean", "MotherInnocent"),
    ("Valjean", "Gavroche"), ("Valjean", "Gillenormand"), ("Valjean", "MlleGillenormand"),
    ("Valjean", "Marius"), ("Valjean", "Enjolras"), ("Valjean", "Bossuet"), ("Valjean",
    "Gueulemer"), ("Valjean", "Babet"), ("Valjean", "Claquesous"), ("Valjean", "Montparnasse"),
    ("Valjean", "Toussaint"), ("Marguerite", "Fantine"), ("Listolier", "Tholomyes"), ("Listolier",
    "Fameuil"), ("Listolier", "Blacheville"), ("Listolier", "Favourite"), ("Listolier", "Dahlia"),
    ("Listolier", "Zephine"), ("Listolier", "Fantine"), ("Tholomyes", "Fameuil"), ("Tholomyes",
    "Blacheville"), ("Tholomyes", "Favourite"), ("Tholomyes", "Dahlia"), ("Tholomyes", "Zephine"),
    ("Tholomyes", "Fantine"), ("Tholomyes", "Cosette"), ("Tholomyes", "Marius"), ("Fameuil",
    "Blacheville"), ("Fameuil", "Favourite"), ("Fameuil", "Dahlia"), ("Fameuil", "Zephine"),
    ("Fameuil", "Fantine"), ("Blacheville", "Favourite"), ("Blacheville", "Dahlia"), ("Blacheville",
    "Zephine"), ("Blacheville", "Fantine"), ("Favourite", "Dahlia"), ("Favourite", "Zephine"),
    ("Favourite", "Fantine"), ("Dahlia", "Zephine"), ("Dahlia", "Fantine"), ("Zephine", "Fantine"),
    ("Fantine", "MmeThenardier"), ("Fantine", "Thenardier"), ("Fantine", "Javert"), ("Fantine",
    "Bamatabois"), ("Fantine", "Perpetue"), ("Fantine", "Simplice"), ("MmeThenardier",
    "Thenardier"), ("MmeThenardier", "Cosette"), ("MmeThenardier", "Javert"), ("MmeThenardier",
    "Eponine"), ("MmeThenardier", "Anzelma"), ("MmeThenardier", "Magnon"), ("MmeThenardier",
    "Gueulemer"), ("MmeThenardier", "Babet"), ("MmeThenardier", "Claquesous"), ("Thenardier",
    "Cosette"), ("Thenardier", "Javert"), ("Thenardier", "Pontmercy"), ("Thenardier",
    "Boulatruelle"), ("Thenardier", "Eponine"), ("Thenardier", "Anzelma"), ("Thenardier",
    "Gavroche"), ("Thenardier", "Marius"), ("Thenardier", "Gueulemer"), ("Thenardier", "Babet"),
    ("Thenardier", "Claquesous"), ("Thenardier", "Montparnasse"), ("Thenardier", "Brujon"),
    ("Cosette", "Javert"), ("Cosette", "Woman2"), ("Cosette", "Gillenormand"), ("Cosette",
    "MlleGillenormand"), ("Cosette", "LtGillenormand"), ("Cosette", "Marius"), ("Cosette",
    "Toussaint"), ("Javert", "Fauchelevent"), ("Javert", "Bamatabois"), ("Javert", "Simplice"),
    ("Javert", "Woman1"), ("Javert", "Woman2"), ("Javert", "Gavroche"), ("Javert", "Enjolras"),
    ("Javert", "Gueulemer"), ("Javert", "Babet"), ("Javert", "Claquesous"), ("Javert",
    "Montparnasse"), ("Javert", "Toussaint"), ("Fauchelevent", "MotherInnocent"), ("Fauchelevent",
    "Gribier"), ("Bamatabois", "Judge"), ("Bamatabois", "Champmathieu"), ("Bamatabois", "Brevet"),
    ("Bamatabois", "Chenildieu"), ("Bamatabois", "Cochepaille"), ("Perpetue", "Simplice"), ("Judge",
    "Champmathieu"), ("Judge", "Brevet"), ("Judge", "Chenildieu"), ("Judge", "Cochepaille"),
    ("Champmathieu", "Brevet"), ("Champmathieu", "Chenildieu"), ("Champmathieu", "Cochepaille"),
    ("Brevet", "Chenildieu"), ("Brevet", "Cochepaille"), ("Chenildieu", "Cochepaille"),
    ("Pontmercy", "MmePontmercy"), ("Pontmercy", "Marius"), ("Eponine", "Anzelma"), ("Eponine",
    "Marius"), ("Eponine", "Mabeuf"), ("Eponine", "Courfeyrac"), ("Eponine", "Gueulemer"),
    ("Eponine", "Babet"), ("Eponine", "Claquesous"), ("Eponine", "Montparnasse"), ("Eponine",
    "Brujon"), ("MmeBurgon", "Jondrette"), ("MmeBurgon", "Gavroche"), ("Gavroche", "Marius"),
    ("Gavroche", "Mabeuf"), ("Gavroche", "Enjolras"), ("Gavroche", "Combeferre"), ("Gavroche",
    "Prouvaire"), ("Gavroche", "Feuilly"), ("Gavroche", "Courfeyrac"), ("Gavroche", "Bahorel"),
    ("Gavroche", "Bossuet"), ("Gavroche", "Joly"), ("Gavroche", "Grantaire"), ("Gavroche",
    "Gueulemer"), ("Gavroche", "Babet"), ("Gavroche", "Montparnasse"), ("Gavroche", "Child1"),
    ("Gavroche", "Child2"), ("Gavroche", "Brujon"), ("Gavroche", "MmeHucheloup"), ("Gillenormand",
    "Magnon"), ("Gillenormand", "MlleGillenormand"), ("Gillenormand", "LtGillenormand"),
    ("Gillenormand", "Marius"), ("Gillenormand", "BaronessT"), ("MlleGillenormand", "MmePontmercy"),
    ("MlleGillenormand", "MlleVaubois"), ("MlleGillenormand", "LtGillenormand"),
    ("MlleGillenormand", "Marius"), ("LtGillenormand", "Marius"), ("Marius", "BaronessT"),
    ("Marius", "Mabeuf"), ("Marius", "Enjolras"), ("Marius", "Combeferre"), ("Marius", "Feuilly"),
    ("Marius", "Courfeyrac"), ("Marius", "Bahorel"), ("Marius", "Bossuet"), ("Marius", "Joly"),
    ("Mabeuf", "Enjolras"), ("Mabeuf", "Combeferre"), ("Mabeuf", "Feuilly"), ("Mabeuf",
    "Courfeyrac"), ("Mabeuf", "Bahorel"), ("Mabeuf", "Bossuet"), ("Mabeuf", "Joly"), ("Mabeuf",
    "MotherPlutarch"), ("Enjolras", "Combeferre"), ("Enjolras", "Prouvaire"), ("Enjolras",
    "Feuilly"), ("Enjolras", "Courfeyrac"), ("Enjolras", "Bahorel"), ("Enjolras", "Bossuet"),
    ("Enjolras", "Joly"), ("Enjolras", "Grantaire"), ("Enjolras", "Claquesous"), ("Enjolras",
    "MmeHucheloup"), ("Combeferre", "Prouvaire"), ("Combeferre", "Feuilly"), ("Combeferre",
    "Courfeyrac"), ("Combeferre", "Bahorel"), ("Combeferre", "Bossuet"), ("Combeferre", "Joly"),
    ("Combeferre", "Grantaire"), ("Prouvaire", "Feuilly"), ("Prouvaire", "Courfeyrac"),
    ("Prouvaire", "Bahorel"), ("Prouvaire", "Bossuet"), ("Prouvaire", "Joly"), ("Prouvaire",
    "Grantaire"), ("Feuilly", "Courfeyrac"), ("Feuilly", "Bahorel"), ("Feuilly", "Bossuet"),
    ("Feuilly", "Joly"), ("Feuilly", "Grantaire"), ("Courfeyrac", "Bahorel"), ("Courfeyrac",
    "Bossuet"), ("Courfeyrac", "Joly"), ("Courfeyrac", "Grantaire"), ("Courfeyrac", "MmeHucheloup"),
    ("Bahorel", "Bossuet"), ("Bahorel", "Joly"), ("Bahorel", "Grantaire"), ("Bahorel",
    "MmeHucheloup"), ("Bossuet", "Joly"), ("Bossuet", "Grantaire"), ("Bossuet", "MmeHucheloup"),
    ("Joly", "Grantaire"), ("Joly", "MmeHucheloup"), ("Grantaire", "MmeHucheloup"), ("Gueulemer",
    "Babet"), ("Gueulemer", "Claquesous"), ("Gueulemer", "Montparnasse"), ("Gueulemer", "Brujon"),
    ("Babet", "Claquesous"), ("Babet", "Montparnasse"), ("Babet", "Brujon"), ("Claquesous",
    "Montparnasse"), ("Claquesous", "Brujon"), ("Montparnasse", "Brujon"), ("Child1", "Child2")
]


def metric_values(payload, *names):
    """Each node's value for a metric, read by column id or by the title Gephi shows.

    Nodes come back with attributes keyed by title ("Betweenness Centrality"), so a probe that
    looks only for the id reads nothing, and two empty readings compare equal. None when any node
    lacks the value: a probe must then give no verdict rather than compare nothing with nothing.
    """
    values = {}
    for node in payload.get("nodes", []):
        attrs = node.get("attributes", {})
        value = next((attrs[n] for n in names if attrs.get(n) is not None), None)
        if value is None:
            return None
        values[node["id"]] = value
    return values or None


@pytest.fixture(autouse=True)
async def require_gephi():
    health = json.loads(await gephi_mcp.gephi_health_check())
    if not health.get("success"):
        pytest.skip("Gephi is not reachable, so nothing here can be established")


async def test_probe_gephi_2034_resolution_is_the_reciprocal_of_the_convention():
    """In the literature a HIGHER resolution yields MORE, smaller communities.

    Gephi is compared against itself at two resolutions, so no reference implementation and no
    convention question. If the count falls as resolution rises, the parameter is inverted.
    """
    probe = "probe_gephi_2034"
    # The graph has to be one where resolution actually changes the answer. Two cliques yield two
    # communities at every resolution, so they would report "not reproduced" from a measurement
    # with no sensitivity to the thing being measured. A ring of eight small cliques can merge into
    # a few coarse groups or split into eight fine ones, so the count genuinely responds.
    if not await ring_of_cliques(groups=8, size=4):
        return VERDICTS.note_failure(probe, "could not build the test graph")

    counts = {r: await community_count(resolution=r) for r in (0.25, 0.5, 1.0, 2.0, 4.0)}
    if any(v is None for v in counts.values()):
        return VERDICTS.note_failure(probe, "could not count communities at every resolution")
    if len(set(counts.values())) == 1:
        return VERDICTS.note_failure(
            probe, f"the community count did not move across resolutions {counts}, so this graph "
                   "cannot decide the question either way")

    low, high = counts[0.25], counts[4.0]
    VERDICTS.record(
        probe, reproduced=high < low, measured=True,
        detail=f"communities by resolution: {counts}; the convention expects the count to RISE "
               f"with resolution, and here it goes {low} -> {high}")


async def test_probe_gephi_557_edge_weight_is_ignored_by_centrality():
    """Change only the weights, never the structure, and see whether betweenness moves.

    Identical numbers on a graph whose weights now differ by a factor of a thousand mean the
    measure did not read them.
    """
    probe = "probe_gephi_557"
    if not await two_cliques():
        return VERDICTS.note_failure(probe, "could not build the test graph")

    if await call(gephi_mcp.gephi_compute_betweenness) is None:
        return VERDICTS.note_failure(probe, "the first betweenness run failed")
    before = await call(gephi_mcp.gephi_query_nodes, limit=100)

    if await call(gephi_mcp.gephi_set_edge_weight,
                  source="L0", target="R0", weight=1000.0) is None:
        return VERDICTS.note_failure(probe, "could not change the edge weight")
    if await call(gephi_mcp.gephi_compute_betweenness) is None:
        return VERDICTS.note_failure(probe, "the second betweenness run failed")
    after = await call(gephi_mcp.gephi_query_nodes, limit=100)

    names = ("betweenesscentrality", "Betweenness Centrality")
    first = metric_values(before or {}, *names)
    second = metric_values(after or {}, *names)
    if first is None or second is None:
        return VERDICTS.note_failure(probe, "could not read the betweenness values back")

    unchanged = first == second
    VERDICTS.record(
        probe, reproduced=unchanged, measured=True,
        detail=("betweenness was identical after a 1000x weight change on the bridge"
                if unchanged else "betweenness responded to the weight change"))


async def test_probe_modularity_unstable_across_runs():
    """The instability caveat merges three claims, so the probe has to test more than one.

    gephi#2002 says repeated runs differ, gephi#2735 says the partition changes after a LAYOUT
    has run, and gephi#2888 says it changes with import order. Repeated runs alone cannot clear
    the entry: Gephi ships with Randomize off, so identical runs are expected and prove nothing
    about the other two. The first version of this probe silenced the caveat on exactly that
    partial evidence.
    """
    probe = "probe_modularity_unstable"
    if not await two_cliques():
        return VERDICTS.note_failure(probe, "could not build the test graph")

    repeated = await call(gephi_mcp.gephi_community_stability, runs=10)
    if repeated is None or repeated.get("distinct_partitions", 0) < 1:
        return VERDICTS.note_failure(
            probe, "the stability run did not produce a partition, so nothing was measured")
    across_runs = repeated["distinct_partitions"] > 1

    # gephi#2735: a layout must not change a partition.
    before = await community_count(resolution=1.0)
    if before is None:
        return VERDICTS.note_failure(probe, "could not count communities before the layout")
    if await call(gephi_mcp.gephi_run_layout,
                  algorithm="Fruchterman Reingold", iterations=50) is None:
        return VERDICTS.note_failure(probe, "could not run a layout, so gephi#2735 is untested")
    after = await community_count(resolution=1.0)
    if after is None:
        return VERDICTS.note_failure(probe, "could not count communities after the layout")
    layout_changed_it = before != after

    VERDICTS.record(
        probe, reproduced=across_runs or layout_changed_it, measured=True,
        detail=(f"{repeated['distinct_partitions']} distinct partitions across 10 runs "
                f"(Randomize defaults to Off, so identical runs are expected); "
                f"communities before a layout = {before}, after = {after}"))


async def test_probe_gephi_858_average_clustering_coefficient():
    """An UNDIRECTED triangle has clustering coefficient 1.0 under every definition there is.

    The directedness is load-bearing. A DIRECTED triangle legitimately scores 0.5 under Gephi's
    directed interpretation, so reading that as a defect would ship a warning about correct
    behaviour. The probe therefore builds the graph undirected and declines to give a verdict
    unless Gephi confirms that it is.
    """
    probe = "probe_gephi_858"
    # Clearing a graph does not reset its directedness, so a fresh workspace is required: the
    # type is fixed by the first edges added to it.
    if await call(gephi_mcp.gephi_new_workspace) is None:
        return VERDICTS.note_failure(probe, "could not open a fresh workspace")
    if await call(gephi_mcp.gephi_add_nodes,
                  nodes=[{"id": "a"}, {"id": "b"}, {"id": "c"}]) is None:
        return VERDICTS.note_failure(probe, "could not add the nodes")
    for source, target in (("a", "b"), ("b", "c"), ("c", "a")):
        if await call(gephi_mcp.gephi_add_edge,
                      source=source, target=target, directed=False) is None:
            return VERDICTS.note_failure(probe, "could not add an undirected edge")

    graph_type = await call(gephi_mcp.gephi_get_graph_type)
    if graph_type is None or not graph_type.get("undirected"):
        return VERDICTS.note_failure(
            probe, "the graph is not undirected, and 1.0 is only universal for an undirected "
                   "triangle; declining rather than testing the wrong claim")

    result = await call(gephi_mcp.gephi_compute_clustering_coefficient)
    if result is None:
        return VERDICTS.note_failure(probe, "the clustering run failed")

    value = next((result[k] for k in
                  ("average_clustering_coefficient", "clustering_coefficient", "average")
                  if k in result), None)
    if value is None:
        return VERDICTS.note_failure(probe, "Gephi reported no clustering value")

    wrong = abs(float(value) - 1.0) > 1e-6
    VERDICTS.record(probe, reproduced=wrong, measured=True,
                    detail=f"an undirected triangle reported {value}; every definition gives 1.0")


async def test_probe_gephi_2145_eigenvector_stops_before_it_converges():
    """Compare Gephi's eigenvector centrality, as the tool runs it, with the exact one.

    Both are scaled so the largest value is 1, which is Gephi's convention, so a difference in
    scaling cannot pass for a defect. The defect is live when Gephi puts a different node first or
    any value is off by more than 0.05.
    """
    import numpy as np

    probe = "probe_gephi_2145"
    ids = sorted({n for edge in LES_MISERABLES for n in edge})
    steps = [
        await call(gephi_mcp.gephi_clear_graph),
        await call(gephi_mcp.gephi_add_nodes, nodes=[{"id": n} for n in ids]),
        await call(gephi_mcp.gephi_add_edges,
                   edges=[{"source": a, "target": b, "directed": False} for a, b in LES_MISERABLES]),
    ]
    if not all(s is not None for s in steps):
        return VERDICTS.note_failure(probe, "could not build the test graph")
    if await call(gephi_mcp.gephi_compute_eigenvector) is None:
        return VERDICTS.note_failure(probe, "the eigenvector run failed")
    read = await call(gephi_mcp.gephi_query_nodes, limit=len(ids))
    gephi = metric_values(read or {}, "eigencentrality", "Eigenvector Centrality")
    if gephi is None or len(gephi) != len(ids):
        return VERDICTS.note_failure(probe, "could not read the eigenvector values back")

    index = {n: i for i, n in enumerate(ids)}
    adjacency = np.zeros((len(ids), len(ids)))
    for a, b in LES_MISERABLES:
        adjacency[index[a], index[b]] = adjacency[index[b], index[a]] = 1
    exact = np.abs(np.linalg.eigh(adjacency)[1][:, -1])
    exact /= exact.max()

    worst = max(abs(gephi[n] - exact[index[n]]) for n in ids)
    top_gephi = max(ids, key=gephi.get)
    top_exact = ids[int(exact.argmax())]
    wrong = top_gephi != top_exact or worst > 0.05
    VERDICTS.record(
        probe, reproduced=wrong, measured=True,
        detail=f"first node {top_gephi} (exact {top_exact}), largest difference {worst:.3f}")
