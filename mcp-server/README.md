# gephi-ai

MCP server that bridges any [Model Context Protocol](https://modelcontextprotocol.io) client
to a running [Gephi Desktop](https://gephi.org) instance, exposing **121 tools** for graph
construction, statistics, community detection, layout, styling, filtering, and
publication-ready export.

It translates MCP tool calls into HTTP requests against the Gephi AI plugin's local API
(`http://127.0.0.1:8080`). Each tool has a typed signature, so clients receive a precise
per-field JSON schema rather than an opaque blob.

This is the **MCP server** component of [gephi-ai](https://github.com/MattArtzAnthro/gephi-ai);
see the top-level repository for the Gephi plugin, the Claude Code plugin, and full docs.

## Install

No install needed with [uv](https://docs.astral.sh/uv/) — point your MCP client at:

```bash
uvx gephi-ai
```

`uvx` fetches [`gephi-ai` from PyPI](https://pypi.org/project/gephi-ai/) on first run
and caches it. For a persistent `gephi-ai` command on your `PATH` instead, use
`pipx install gephi-ai` (or `pipx install .` from this directory). Avoid plain
`pip install -e .` inside a virtual environment: the command is then only visible on
that venv's `PATH`, and MCP clients launched outside your shell won't find it.

## Use

The Gephi AI plugin must be installed and Gephi Desktop running first. Then point any MCP
client at the `gephi-ai` command, e.g. for Claude Desktop:

```json
{ "mcpServers": { "gephi-ai": { "command": "uvx", "args": ["gephi-ai"] } } }
```

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `GEPHI_API_URL` | `http://127.0.0.1:8080` | Gephi plugin HTTP API base URL |
| `GEPHI_REQUEST_TIMEOUT` | `60.0` | Per-request timeout (seconds) |
| `GEPHI_DUPLICATE_GRACE` | `30` | Seconds to keep checking for a workspace copy after a duplicate timed out, so a copy Gephi makes late is still removed |

Graph-changing tools run one at a time within one server process, so parallel tool calls from a host cannot interleave their changes. `gephi_profile_graph` waits in that same queue, because it writes statistic columns, and so do the exports and `gephi_visual_qa`, so an image never comes from a workspace copy. Read-only tools do not wait for graph changes, and `gephi_session_receipt` and `gephi_claim_record` behave like read-only tools. Read-only tools wait until a what-if finishes, then read the original graph; this includes any time the what-if spends on slow metrics or waiting for a late copy. `gephi_compare_workspaces` also holds back reads while it runs, because it switches between the two workspaces. A what-if or a compare waits for reads already in progress before it starts. After a workspace duplicate times out, the server may keep checking for the late copy for up to `GEPHI_DUPLICATE_GRACE` seconds before it answers.

## Timing and benchmarks

Set `GEPHI_AI_TIMING_LOG` to a file path and the server appends one JSON line per tool call. Unset,
nothing is written. A failure to write logs one warning to stderr and never changes a tool's result.

| Field | Meaning |
|---|---|
| `ts` | Start of the call, ISO 8601, UTC |
| `tool` | Tool name |
| `ms` | Wall time in milliseconds, including any wait for the tool lock |
| `outcome` | `ok` or `error` |
| `error` | The error message, or null |
| `nodes`, `edges` | The graph's size when this server has seen it in a result, else null |
| `busy` | The plugin's busy text, with its lock state, when the result carries one |
| `http` | The requests the call made to the plugin: `endpoint`, `status`, `ms`, and `error` on failure |

```json
{"ts": "2026-11-08T14:03:21.512+00:00", "tool": "gephi_compute_degree", "ms": 842.6, "outcome": "ok", "error": null, "nodes": 10000, "edges": 29994, "busy": null, "http": [{"endpoint": "/statistics/degree", "status": 200, "ms": 838.1}]}
```

The gap between `ms` and the sum of the `http` times is time spent in this server. The size is never
fetched for the log; it comes from the last result that carried node and edge counts, and is
forgotten when a call may have changed the graph.

`bench/benchmark.py` runs a fixed sequence of tools at several graph sizes against a separate Gephi
and compares runs. See [bench/README.md](bench/README.md).

## Development

```bash
pip install -e ".[dev]"
ruff check .
mypy ./*.py gephi_mcp_viewer
python -m pytest -q --cov   # fails below the coverage floor in pyproject.toml
```

## License

Apache-2.0 — see the [repository LICENSE](https://github.com/MattArtzAnthro/gephi-ai/blob/main/LICENSE).
