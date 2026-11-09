# Benchmark

`benchmark.py` times the server's own tool functions in-process, so each timing includes what an
agent experiences: the tool lock, the HTTP round trip to Gephi, and the server's own work.

## Use a separate Gephi

The benchmark creates and deletes workspaces. Never point it at the Gephi you work in. It
refuses when `GEPHI_API_URL` is unset or names port 8080 (override with `--allow-port-8080`).

Start a second Gephi with its own settings folder and port, as described in the docstring of
`tests/live_smoke_test.py`, with the built plugin copied into that folder:

```bash
/Applications/Gephi.app/Contents/Resources/gephi/bin/gephi --userdir /tmp/gephi-test \
    --cachedir /tmp/gephi-test-cache -J-Dgephi.mcp.port=8091
```

## Run

From `mcp-server/`:

```bash
GEPHI_API_URL=http://127.0.0.1:8091 PYTHONPATH=. python bench/benchmark.py
GEPHI_API_URL=http://127.0.0.1:8091 PYTHONPATH=. python bench/benchmark.py --sizes 1000 --repeats 5
```

| Option | Default | Meaning |
|---|---|---|
| `--sizes` | `1000,10000,100000` | Node counts, one fresh graph per repeat |
| `--repeats` | `3` | Runs of the whole sequence per size |
| `--out` | `bench-results/<timestamp>.json` | Result file |
| `--allow-port-8080` | off | Allow the Gephi you work in (not advised) |

Each repeat generates a graph, then runs: graph stats, degree, modularity (resolution 1.0),
PageRank, betweenness, ForceAtlas 2 (100 iterations, Barnes-Hut on), a GEXF export and a PNG
export to a temporary folder that is deleted afterwards, and then deletes its workspace.
Betweenness is listed as skipped at 10,000 and 100,000 nodes (the `SKIPS` table in the script).

The graph is preferential attachment (Barabasi-Albert) with 3 links per new node and seed 42: about
3 edges per node, an average degree near 6, and a few hubs, like many sparse real networks.

The result file records the date, server, plugin and Gephi versions, the machine, the settings,
and every step's timings in milliseconds (median, min, max, and any errors). A markdown table is
printed. Unless `GEPHI_AI_TIMING_LOG` is already set, the run writes the per-call log beside the
result as `<result>.timing.jsonl`.

## Compare two runs

```bash
python bench/benchmark.py --compare bench-results/old.json bench-results/new.json
```

For each size and step it prints the change in median, in milliseconds and percent. A change is
called real only when it is larger than the spread (max minus min) of both runs; otherwise it is
"within noise". A run with fewer than two timings for a step cannot be judged, so use at least 3
repeats when you intend to compare. Compare runs from the same machine and the same Gephi.

Each run starts with one untimed pass at the smallest size, kept out of the timing log, because
the first run on a freshly started Gephi is slower while the JVM compiles its code. `--no-warmup`
skips it. Compare only runs made the same way.
