"""Community-anchored radial layout: one radial fan per community, packed as discs.

Force-directed layouts cannot separate communities in tree-like networks
(replies, retweets, citations from a seed): communities there are stars fanning
out from hubs, and interleaved star-arms have no ties pulling them together.
This layout takes a detected partition and draws each community as its own
radial fan (hub at center, members ringed by graph distance from the hub,
branch angles sized by subtree), then packs the fans as non-overlapping discs.

Reading rule that MUST travel with the result: grouping and within-disc
distances come from the data; disc placement relative to other discs is
arranged for legibility and means nothing.

Pure stdlib — no numpy needed.
"""

from __future__ import annotations

import math
import random
import statistics


def _radial_fan(members, adj, indeg, size_of):
    """Radial BFS tree around the community hub.

    Returns ({id: (x, y)} relative to the fan center, disc_radius).
    """
    mset = set(members)
    root = max(members, key=lambda k: (indeg.get(k, 0), size_of.get(k, 0)))
    depth, order, parent = {root: 0}, [root], {root: None}
    i = 0
    while i < len(order):
        u = order[i]
        i += 1
        for v in sorted(adj.get(u, ()), key=lambda k: -indeg.get(k, 0)):
            if v in mset and v not in depth:
                depth[v] = depth[u] + 1
                parent[v] = u
                order.append(v)
    for m in members:  # safety net; a community should be internally connected
        if m not in depth:
            depth[m] = 1
            parent[m] = root
            # Must join `order` too. Every structure below (kids, leaves, by_depth) is built
            # by iterating it, and three sites index leaves[] directly. On a directed graph
            # the BFS routinely fails to reach every member, so this branch is the norm, not
            # the exception, and omitting the append raised KeyError.
            order.append(m)

    kids = {}
    for v, p in parent.items():
        if p is not None:
            kids.setdefault(p, []).append(v)
    leaves = {}
    for v in reversed(order):
        leaves[v] = max(1, sum(leaves.get(c, 1) for c in kids.get(v, ())))

    # Angular slices proportional to subtree size keep branches from colliding.
    ang = {root: (0.0, 2 * math.pi)}
    for v in order:
        a0, a1 = ang.get(v, (0.0, 2 * math.pi))
        cur = a0
        tot = sum(leaves[c] for c in kids.get(v, ())) or 1
        for c in kids.get(v, ()):
            w = (a1 - a0) * leaves[c] / tot
            ang[c] = (cur, cur + w)
            cur += w

    # Ring gap scales with the hub's rendered size and with ring crowding, so
    # a hub with hundreds of direct children still has label-able rings.
    by_depth = {}
    for v in order:
        by_depth.setdefault(depth[v], []).append(v)
    base_gap = 46 + size_of.get(root, 12) * 0.55
    mean_size = statistics.mean(size_of.get(k, 12) for k in members) if members else 12

    pos, rmax = {}, 0.0
    ring_r = {0: 0.0}
    for d in sorted(by_depth):
        if d == 0:
            continue
        crowd = len(by_depth[d]) * (mean_size + 6) / (2 * math.pi)
        ring_r[d] = max(ring_r[d - 1] + base_gap, crowd)
    for v in order:
        d = depth[v]
        if d == 0:
            pos[v] = (0.0, 0.0)
            continue
        a = (ang[v][0] + ang[v][1]) / 2
        r = ring_r[d]
        pos[v] = (r * math.cos(a), r * math.sin(a))
        rmax = max(rmax, r)
    return pos, rmax + 30


def compute_community_positions(graph, partition="Modularity Class",
                                min_disc=6, pad=55):
    """Compute community-anchored positions for a parse_gexf graph dict.

    partition: node attribute naming the community (any hashable values).
    min_disc: communities smaller than this scatter on the outer rim instead
    of getting their own disc.

    Returns (positions list of {"id", "x", "y"}, info dict).
    Raises ValueError when the partition attribute is absent.
    """
    from gephi_mcp_viewer import resolve_column_key
    partition = resolve_column_key(graph, partition)
    nodes = {n["key"]: n for n in graph["nodes"]}
    comm = {}
    for k, n in nodes.items():
        c = n["attributes"].get(partition)
        if c is not None:
            comm.setdefault(str(c), []).append(k)
    if not comm:
        raise ValueError(
            f"no nodes carry the partition attribute '{partition}' — run a "
            "community statistic first (e.g. modularity)")
    unassigned = [k for k, n in nodes.items()
                  if n["attributes"].get(partition) is None]

    adj = {}
    for e in graph["edges"]:
        s, t = e["source"], e["target"]
        if s in nodes and t in nodes:
            adj.setdefault(s, set()).add(t)
            adj.setdefault(t, set()).add(s)
    indeg = {k: len(adj.get(k, ())) for k in nodes}
    size_of = {k: float(nodes[k].get("size") or 12) for k in nodes}

    fans = {c: _radial_fan(ms, adj, indeg, size_of) for c, ms in comm.items()}

    # Pack discs: largest community at the origin, the rest spiral in around
    # it greedily (communities are few, so the O(n^2) collision check is fine).
    placed, centers = [], {}

    def place(r):
        if not placed:
            placed.append((0.0, 0.0, r))
            return 0.0, 0.0
        step, a = 0.35, 0.0
        R = placed[0][2] + r + pad
        while True:
            x, y = R * math.cos(a), R * math.sin(a)
            if all(math.dist((x, y), (px, py)) > pr + r + pad
                   for px, py, pr in placed):
                placed.append((x, y, r))
                return x, y
            a += step
            R += 6

    ordered = sorted(comm, key=lambda c: -len(comm[c]))
    disc_count = 0
    for c in ordered:
        if len(comm[c]) < min_disc:
            continue
        centers[c] = place(fans[c][1])
        disc_count += 1

    rim = (max(math.hypot(x, y) + r for x, y, r in placed) + 220) if placed else 400
    tiny = [c for c in ordered if len(comm[c]) < min_disc]
    for j, c in enumerate(tiny):
        a = 2 * math.pi * j / max(1, len(tiny))
        centers[c] = (rim * math.cos(a), rim * math.sin(a))
    rng = random.Random(11)
    positions = []
    for c, ms in comm.items():
        cx, cy = centers[c]
        pos = fans[c][0]
        for m in ms:
            x, y = pos[m]
            positions.append({"id": m, "x": cx + x, "y": cy + y})
    for j, k in enumerate(unassigned):
        a = 2 * math.pi * (j + 0.5) / max(1, len(unassigned))
        rr = rim + 120 + rng.uniform(0, 80)
        positions.append({"id": k, "x": rr * math.cos(a), "y": rr * math.sin(a)})

    info = {"communities": len(comm), "discs": disc_count,
            "rim_communities": len(tiny), "unassigned_nodes": len(unassigned)}
    return positions, info


def separation_score(graph, positions, partition="Modularity Class",
                     min_members=10, samples=300, seed=7):
    """How spatially mixed the partition is: mean intra-community pair distance
    over mean random pair distance. 1.0 = fully mixed, near 0 = tight discs.

    positions: {id: (x, y)} or a list of {"id", "x", "y"} dicts.
    Returns None when fewer than two communities have min_members members.
    """
    from gephi_mcp_viewer import resolve_column_key
    partition = resolve_column_key(graph, partition)
    if isinstance(positions, list):
        positions = {p["id"]: (p["x"], p["y"]) for p in positions}
    groups = {}
    for n in graph["nodes"]:
        c = n["attributes"].get(partition)
        if c is not None and n["key"] in positions:
            groups.setdefault(str(c), []).append(n["key"])
    big = [ids for ids in groups.values() if len(ids) >= min_members]
    if len(big) < 2:
        return None
    rng = random.Random(seed)
    intra = []
    for ids in big:
        intra.extend((rng.choice(ids), rng.choice(ids)) for _ in range(samples))
    intra = [(a, b) for a, b in intra if a != b]
    allids = list(positions)
    rand = [(rng.choice(allids), rng.choice(allids)) for _ in range(2000)]
    rand = [(a, b) for a, b in rand if a != b]

    def meand(pairs):
        return statistics.mean(math.dist(positions[a], positions[b])
                               for a, b in pairs)

    base = meand(rand)
    if base == 0:
        return None
    return round(meand(intra) / base, 3)
