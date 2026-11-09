"""Repeatable timing benchmark for the Gephi AI MCP server.

It calls the server's own tool functions in-process, so the timings include what an agent
experiences (the tool lock, the read gate, the HTTP round trip and the server's own work), against
the Gephi at GEPHI_API_URL. Use a separate Gephi, never your own: see README.md in this folder.

    GEPHI_API_URL=http://127.0.0.1:8091 PYTHONPATH=. python bench/benchmark.py
    python bench/benchmark.py --compare bench-results/old.json bench-results/new.json
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import platform
import statistics
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_SIZES = (1000, 10000, 100000)
SEED = 42

#: A sparse, heavy-tailed model graph: preferential attachment (Barabasi-Albert) with 3 new links
#: per node, so about 3 edges per node and an average degree near 6, the density of many real
#: social and citation networks. The seed fixes the structure, so every run times the same graph.
GENERATOR = {"model": "preferential_attachment", "edges_per_node": 3, "seed": SEED}

#: ForceAtlas 2 for a fixed number of iterations, with Barnes-Hut on so large sizes finish.
LAYOUT = {"algorithm": "ForceAtlas 2", "iterations": 100,
          "properties": {"barnesHutOptimization": True}}

#: Louvain at Gephi's default resolution. The tool takes no seed.
MODULARITY_RESOLUTION = 1.0

#: Steps left out at a size, with the reason, so nothing is dropped silently.
SKIPS: dict[int, dict[str, str]] = {
    10000: {"betweenness": "all-pairs shortest paths, about a minute at 10,000 nodes"},
    100000: {"betweenness": "all-pairs shortest paths, hours at 100,000 nodes"},
}

Step = Callable[[Any, "Context"], Awaitable[str]]


class Context:
    def __init__(self, size: int, folder: Path):
        self.size = size
        self.folder = folder


async def _generate(g: Any, ctx: Context) -> str:
    return await g.gephi_generate_graph(nodes=ctx.size, **GENERATOR)


async def _stats(g: Any, ctx: Context) -> str:
    return await g.gephi_get_graph_stats()


async def _degree(g: Any, ctx: Context) -> str:
    return await g.gephi_compute_degree()


async def _modularity(g: Any, ctx: Context) -> str:
    return await g.gephi_compute_modularity(resolution=MODULARITY_RESOLUTION)


async def _pagerank(g: Any, ctx: Context) -> str:
    return await g.gephi_compute_pagerank()


async def _betweenness(g: Any, ctx: Context) -> str:
    return await g.gephi_compute_betweenness()


async def _layout(g: Any, ctx: Context) -> str:
    return await g.gephi_run_layout(**LAYOUT, sync=True)


async def _export_gexf(g: Any, ctx: Context) -> str:
    return await g.gephi_export_gexf(file=str(ctx.folder / "bench.gexf"))


async def _export_png(g: Any, ctx: Context) -> str:
    return await g.gephi_export_png(file=str(ctx.folder / "bench.png"))


#: The fixed sequence, in order. Each repeat runs all of it on a fresh graph.
STEPS: list[tuple[str, Step]] = [
    ("generate", _generate), ("graph_stats", _stats), ("degree", _degree),
    ("modularity", _modularity), ("pagerank", _pagerank), ("betweenness", _betweenness),
    ("layout", _layout), ("export_gexf", _export_gexf), ("export_png", _export_png),
]


def refusal(url: str | None, allow_8080: bool) -> str | None:
    """Why the benchmark must not run against this URL, or None."""
    if not url:
        return ("GEPHI_API_URL is not set. Point it at a separate Gephi (see bench/README.md); "
                "the benchmark will not guess.")
    if urlparse(url).port == 8080 and not allow_8080:
        return (f"GEPHI_API_URL is {url}: port 8080 is the Gephi you work in, and the benchmark "
                "creates and deletes workspaces. Start a separate Gephi on another port, or pass "
                "--allow-port-8080 if you really mean it.")
    return None


def _failure(text: str) -> str | None:
    """The error message when a tool's result text reports a failure, else None."""
    try:
        body = json.loads(text)
    except (TypeError, ValueError):
        return None
    if isinstance(body, dict) and (body.get("success") is False
                                   or ("success" not in body and body.get("error"))):
        return str(body.get("error") or body.get("message") or "failed")
    return None


async def _timed(step: Step, g: Any, ctx: Context) -> tuple[float, str | None]:
    clock = time.perf_counter()
    try:
        error = _failure(await step(g, ctx))
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return (time.perf_counter() - clock) * 1000, error


def _summary(entry: dict[str, Any]) -> None:
    ms = entry["ms"]
    entry["median"] = round(statistics.median(ms), 1) if ms else None
    entry["min"] = round(min(ms), 1) if ms else None
    entry["max"] = round(max(ms), 1) if ms else None


async def _current_index(g: Any) -> tuple[int, int | None]:
    """(workspace count, index of the one on screen), asked of the plugin directly so this
    bookkeeping stays out of the timing log. With no project open the plugin answers an error,
    which means no workspaces."""
    try:
        listed = await g.gephi.request("GET", "/workspace/list")
    except Exception:
        return 0, None
    spaces = listed.get("workspaces", []) if isinstance(listed, dict) and listed.get("success") else []
    current = next((i for i, w in enumerate(spaces) if w.get("current")), None)
    return len(spaces), current


async def run_size(g: Any, size: int, repeats: int) -> dict[str, Any]:
    skips = SKIPS.get(size, {})
    results: dict[str, Any] = {
        name: {"ms": [], "errors": [], "skipped": skips.get(name)} for name, _ in STEPS}
    for repeat in range(1, repeats + 1):
        before, _ = await _current_index(g)
        with tempfile.TemporaryDirectory(prefix="gephi-bench-") as folder:
            ctx = Context(size, Path(folder))
            for name, step in STEPS:
                if name in skips:
                    continue
                ms, error = await _timed(step, g, ctx)
                if error:
                    results[name]["errors"].append({"repeat": repeat, "error": error})
                else:
                    results[name]["ms"].append(round(ms, 1))
        # Remove only the workspace this repeat made, never one that was already there.
        after, current = await _current_index(g)
        if after > before and current is not None:
            await g.gephi_delete_workspace(index=current)
    for entry in results.values():
        _summary(entry)
    return results


def _cell(entry: dict[str, Any]) -> str:
    if entry.get("skipped"):
        return "skipped"
    if entry["median"] is None:
        return "error" if entry["errors"] else "-"
    text = f"{entry['median']:.0f} ({entry['min']:.0f}-{entry['max']:.0f})"
    return f"{text}, {len(entry['errors'])} error(s)" if entry["errors"] else text


def table(data: dict[str, Any]) -> str:
    sizes = data["sizes"]
    lines = ["| Step | " + " | ".join(f"{s} nodes" for s in sizes) + " |",
             "|---|" + "---|" * len(sizes)]
    for name, _ in STEPS:
        cells = [_cell(data["results"][str(s)][name]) for s in sizes]
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines.append("")
    lines.append(f"Median ms (min-max) over {data['repeats']} repeat(s).")
    return "\n".join(lines)


async def benchmark(sizes: list[int], repeats: int, warmup: bool = True) -> dict[str, Any]:
    import gephi_mcp as g

    try:
        health = json.loads(await g.gephi_health_check())
    except ValueError:
        health = {}
    data: dict[str, Any] = {
        "date": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "api_url": os.environ.get("GEPHI_API_URL"),
        "server_version": health.get("server_version") or g.__version__,
        "plugin_version": health.get("version"),
        "gephi_version": health.get("gephi_version"),
        "machine": {"platform": platform.platform(), "processor": platform.machine(),
                    "cpu_count": os.cpu_count(), "python": platform.python_version()},
        "sizes": sizes, "repeats": repeats, "seed": SEED, "generator": GENERATOR,
        "layout": LAYOUT, "modularity_resolution": MODULARITY_RESOLUTION, "results": {},
        "warmup": {"size": min(sizes), "repeats": 1} if warmup else None,
    }
    if warmup:
        # The first run on a freshly started Gephi is slower while the JVM compiles its code, which
        # made later runs look faster at steps nothing had changed. One pass at the smallest size,
        # not timed and kept out of the timing log, settles it.
        log = os.environ.pop(g.TIMING_LOG_ENV, None)
        try:
            await run_size(g, min(sizes), 1)
        finally:
            if log is not None:
                os.environ[g.TIMING_LOG_ENV] = log
    for size in sizes:
        data["results"][str(size)] = await run_size(g, size, repeats)
    return data


def compare(old: dict[str, Any], new: dict[str, Any]) -> str:
    """Median change per size and step. A change is real only when it is larger than the spread
    (max minus min) of both runs; with fewer than two timings in a run there is no spread to
    judge it by."""
    lines = ["| Size | Step | Old ms | New ms | Change ms | Change % | Verdict |",
             "|---|---|---|---|---|---|---|"]
    for size in new["sizes"]:
        for name, n in new["results"].get(str(size), {}).items():
            o = old["results"].get(str(size), {}).get(name)
            if o is None or o.get("median") is None or n.get("median") is None:
                continue
            delta = n["median"] - o["median"]
            pct = f"{delta / o['median'] * 100:+.1f}%" if o["median"] else "n/a"
            if len(o["ms"]) < 2 or len(n["ms"]) < 2:
                verdict = "not enough repeats"
            elif abs(delta) > max(o["max"] - o["min"], n["max"] - n["min"]):
                verdict = "real: " + ("slower" if delta > 0 else "faster")
            else:
                verdict = "within noise"
            lines.append(f"| {size} | {name} | {o['median']:.1f} | {n['median']:.1f} | "
                         f"{delta:+.1f} | {pct} | {verdict} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sizes", default=",".join(map(str, DEFAULT_SIZES)),
                        help="comma-separated node counts (default %(default)s)")
    parser.add_argument("--repeats", type=int, default=3, help="repeats per size (default 3)")
    parser.add_argument("--out", help="result file (default bench-results/<timestamp>.json)")
    parser.add_argument("--allow-port-8080", action="store_true",
                        help="allow GEPHI_API_URL on port 8080, the Gephi you work in")
    parser.add_argument("--no-warmup", action="store_true",
                        help="skip the untimed warm-up pass at the smallest size")
    parser.add_argument("--compare", nargs=2, metavar=("OLD", "NEW"),
                        help="compare two result files instead of running")
    args = parser.parse_args(argv)
    # One INFO line per HTTP request drowns the table; the timing log keeps every request.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if args.compare:
        old, new = (json.loads(Path(p).read_text()) for p in args.compare)
        print(compare(old, new))
        return 0

    problem = refusal(os.environ.get("GEPHI_API_URL"), args.allow_port_8080)
    if problem:
        print(problem, file=sys.stderr)
        return 2
    try:
        sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    except ValueError:
        print(f"--sizes must be whole numbers separated by commas, not {args.sizes!r}",
              file=sys.stderr)
        return 2

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(args.out) if args.out else Path("bench-results") / f"{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Keep the per-call log with the result, and keep the timings free of the update check.
    os.environ.setdefault("GEPHI_AI_TIMING_LOG", str(out.with_suffix(".timing.jsonl")))
    os.environ.setdefault("GEPHI_SKIP_UPDATE_CHECK", "1")

    data = asyncio.run(benchmark(sizes, args.repeats, warmup=not args.no_warmup))
    out.write_text(json.dumps(data, indent=2) + "\n")
    print(table(data))
    print(f"\nResult: {out}\nPer-call log: {os.environ['GEPHI_AI_TIMING_LOG']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
