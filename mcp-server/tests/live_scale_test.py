"""Live scale / performance harness — runs the core pipeline at 1k / 5k / 10k.

NOT a unit test (needs a live Gephi on :8080; not pytest-collected). Run by hand
when performance matters or before a release that touches statistics/layout:

    PYTHONPATH=. uv run --with mcp --with httpx --with pydantic \
        python tests/live_scale_test.py

Why it exists: 1000-node correctness is the everyday standard, but scale exposes
different failure modes — an O(n*m) statistic, a lock held too long, a client
timeout. This harness measured the baseline below and guards the one real cliff it
found: betweenness/avg-path-length are O(n*m) and run past the default 60s HTTP
timeout on large graphs, so those tools use SLOW_REQUEST_TIMEOUT. The assertion at
the end fails if betweenness ever stops completing at 10k.

Baseline (Gephi 1.2.15, 2026-07-08), per-op wall clock:
    op                    1000n    5000n    10000n
    import                0.09s    0.11s    0.24s
    compute_modularity    0.03s    0.10s    0.18s
    compute_pagerank      0.04s    0.12s    0.14s
    profile_graph(fast)   0.13s    0.44s    0.91s
    color / size          <0.03s   <0.03s   <0.03s
    layout FA2 x100 (BH)  1.06s    1.04s    2.05s
    visual_qa             0.07s    0.27s    0.53s
    export_gexf           0.03s    0.05s    0.07s
    betweenness (O(n*m))  0.54s    15.7s    ~77s   <- the expensive one
"""
import asyncio
import json
import random
import time

import gephi_mcp as g

SCALES = (1000, 5000, 10000)


def gen(n: int, path: str) -> tuple[int, int]:
    k = max(4, n // 125)
    random.seed(1)
    per = n // k
    comm = {i: i // per for i in range(n)}
    hubs = {c: [c * per + j for j in range(3)] for c in range(k)}
    edges: dict[tuple[int, int], int] = {}

    def add(u, v, w):
        if u != v:
            edges.setdefault((min(u, v), max(u, v)), w)

    for i in range(n):
        c = comm[i]
        lo, hi = c * per, min(c * per + per, n)
        for _ in range(random.randint(3, 6)):
            v = random.choice(hubs[c]) if random.random() < 0.55 else random.randint(lo, hi - 1)
            add(i, v, random.randint(2, 6))
    for _ in range(n // 2):
        ca, cb = random.sample(range(k), 2)
        add(random.choice(hubs[ca]), random.choice(hubs[cb]), 1)
    with open(path, "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>'
                '<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">'
                '<graph mode="static" defaultedgetype="undirected">'
                '<attributes class="node"><attribute id="team" title="team" type="string"/></attributes>'
                '<nodes>')
        for i in range(n):
            f.write(f'<node id="n{i}"><attvalues><attvalue for="team" value="C{comm[i]}"/></attvalues></node>')
        f.write('</nodes><edges>')
        for e, ((u, v), w) in enumerate(edges.items()):
            f.write(f'<edge id="e{e}" source="n{u}" target="n{v}" weight="{w}"/>')
        f.write('</edges></graph></gexf>')
    return n, len(edges)


async def timed(coro):
    t = time.perf_counter()
    try:
        r = await coro
        ok = json.loads(r).get("success") is not False if isinstance(r, str) else True
    except Exception as e:  # noqa: BLE001
        return time.perf_counter() - t, f"ERR {type(e).__name__}"
    return time.perf_counter() - t, "ok" if ok else "FAIL"


async def main():
    rows: dict[str, dict[int, tuple]] = {}
    betweenness_ok = {}
    for n in SCALES:
        path = f"/tmp/scale_{n}.gexf"
        _, ee = gen(n, path)
        await g.gephi_create_project(f"scale{n}")
        pipeline = [
            ("import", g.gephi_import_gexf(path)),
            ("compute_degree", g.gephi_compute_degree()),
            ("compute_modularity", g.gephi_compute_modularity(1.0)),
            ("compute_pagerank", g.gephi_compute_pagerank()),
            ("profile_graph(fast)", g.gephi_profile_graph()),
            ("color_by_partition", g.gephi_color_by_partition("modularity_class")),
            ("size_by_ranking", g.gephi_size_by_ranking("Degree")),
            ("layout FA2 x100 (BH)", g.gephi_run_layout(
                "ForceAtlas 2", iterations=100, sync=True,
                properties={"barnesHutOptimization": True, "linLogMode": True, "gravity": 0.0})),
            ("visual_qa", g.gephi_visual_qa("modularity_class")),
            ("export_gexf", g.gephi_export_gexf(f"/tmp/scale_out_{n}.gexf")),
            ("betweenness (O(n*m))", g.gephi_compute_betweenness()),
        ]
        for name, coro in pipeline:
            dt, st = await timed(coro)
            rows.setdefault(name, {})[n] = (dt, st)
            if name.startswith("betweenness"):
                betweenness_ok[n] = st == "ok"
        print(f"  ...{n} nodes / {ee} edges done", flush=True)

    print(f"\n{'op':<26}" + "".join(f"{f'{s}n':>12}" for s in SCALES))
    print("-" * (26 + 12 * len(SCALES)))
    for name, row in rows.items():
        line = f"{name:<26}"
        for s in SCALES:
            dt, st = row.get(s, (0, "-"))
            line += f"{(f'{dt:.2f}s' if st == 'ok' else st):>12}"
        print(line)

    # Regression guard for the SLOW_REQUEST_TIMEOUT fix: betweenness must complete
    # at every scale (it timed out at 10k under the old 60s default).
    print()
    if all(betweenness_ok.get(s) for s in SCALES):
        print(f"PASS  betweenness completes at all scales {SCALES}")
    else:
        failed = [s for s in SCALES if not betweenness_ok.get(s)]
        print(f"FAIL  betweenness did NOT complete at: {failed} (timeout regression?)")


if __name__ == "__main__":
    asyncio.run(main())
