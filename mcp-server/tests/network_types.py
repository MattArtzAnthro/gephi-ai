"""Network types the tests run through, generated in code so they need no data files.

Each type exercises code the others do not: weights, direction, fragments, two modes, repeated
ties and self-loops, awkward ids, density, a dominant hub, timestamps, scale, and the trivial
case. `live_workflow_test.py` runs every one against a live Gephi; `test_network_types.py` runs
the profile's reading of every one offline. Add a type here and both pick it up.
"""

import random

import networkx as nx


def generated() -> dict[str, nx.Graph]:
    rng = random.Random(7)
    les = nx.les_miserables_graph()
    karate = nx.karate_club_graph()
    for n, d in karate.nodes(data=True):
        d["group"] = d.pop("club")
    for _, _, d in karate.edges(data=True):
        d.pop("weight", None)
    heavy = nx.relabel_nodes(nx.powerlaw_cluster_graph(400, 2, 0.3, seed=7), str)
    for _, _, d in heavy.edges(data=True):
        d["weight"] = float(min(500, int(rng.paretovariate(1.2))))
    tree = nx.relabel_nodes(nx.gn_graph(600, seed=7), str)  # a directed tree: tree-like, one-way
    sbm = nx.stochastic_block_model([120, 100, 80, 60], [[0.08, 0.004, 0.004, 0.004],
                                                         [0.004, 0.09, 0.004, 0.004],
                                                         [0.004, 0.004, 0.1, 0.004],
                                                         [0.004, 0.004, 0.004, 0.12]], seed=7)
    for n, d in sbm.nodes(data=True):
        d["group"] = str(d.pop("block"))
    sbm = nx.relabel_nodes(sbm, str)
    # Directed, with weights from repeated ties: the shape of a reply or citation network.
    multi = nx.scale_free_graph(500, seed=7)
    replies = nx.DiGraph()
    for u, v in multi.edges():
        if u != v:
            w = replies.get_edge_data(str(u), str(v), {}).get("weight", 0.0)
            replies.add_edge(str(u), str(v), weight=w + 1.0)
    # Several components and isolated nodes: fragmentation, isolates, the giant component.
    islands = nx.disjoint_union_all([nx.relabel_nodes(nx.karate_club_graph(), str),
                                     nx.path_graph(12), nx.cycle_graph(9)])
    islands.add_nodes_from(range(1000, 1006))
    islands = nx.relabel_nodes(islands, str)
    for _, _, d in islands.edges(data=True):
        d.pop("weight", None)
    # Two-mode: people and the events they attend.
    two_mode = nx.bipartite.random_graph(60, 25, 0.12, seed=7)
    for n, d in two_mode.nodes(data=True):
        d["mode"] = "person" if d.pop("bipartite") == 0 else "event"
    two_mode = nx.relabel_nodes(two_mode, lambda n: f"p{n}" if n < 60 else f"e{n}")
    # Repeated ties and self-loops, collapsed to a weight the way an edge list is.
    loops = nx.Graph()
    for u, v in nx.gnm_random_graph(150, 600, seed=7, directed=False).edges():
        loops.add_edge(str(u), str(v), weight=float(rng.choice([1, 1, 1, 2, 3, 8])))
    for n in list(loops.nodes)[:10]:
        loops.add_edge(n, n, weight=2.0)
    # Ids and labels that have broken things before: accents, spaces, integer ids.
    names = ["Zoë", "José Martí", "Ægir", "Łódź", "São Paulo", "naïve café", "Øresund",
             "Ñandú", "Gödel", "Ćevapi", "Ångström", "Dvořák"]
    awkward = nx.relabel_nodes(nx.karate_club_graph(), {i: n for i, n in enumerate(names)})
    for n, d in awkward.nodes(data=True):
        d["group"] = d.pop("club")
        d["label"] = str(n)
    for _, _, d in awkward.edges(data=True):
        d.pop("weight", None)
    dense = nx.relabel_nodes(nx.gnp_random_graph(60, 0.85, seed=7), str)
    star = nx.relabel_nodes(nx.star_graph(300), str)
    for i in range(1, 300, 7):
        star.add_edge(str(i), str(i + 1))
    # Timestamped: each node and tie has a start, so the timeline and time slices have work.
    timed = nx.relabel_nodes(nx.barabasi_albert_graph(200, 2, seed=7), str)
    for n, d in timed.nodes(data=True):
        d["start"] = int(n) // 20
    for u, v, d in timed.edges(data=True):
        d["start"] = max(int(u), int(v)) // 20
    timed.graph["mode"] = "dynamic"
    big = nx.relabel_nodes(nx.powerlaw_cluster_graph(12000, 2, 0.1, seed=7), str)
    tiny = nx.Graph([("a", "b")])
    return {"several components + isolates": islands, "two-mode (people, events)": two_mode,
            "repeated ties + self-loops": loops, "accented and spaced ids": awkward,
            "dense (p=0.85)": dense, "star hub": star, "timestamped": timed,
            "large (12k nodes)": big, "tiny (two nodes)": tiny,
            "directed weighted replies": replies,
            "les-miserables (weighted)": les, "karate (two clubs)": karate,
            "heavy-tailed weights": heavy, "directed tree-like": tree,
            "four planted blocks": sbm}
