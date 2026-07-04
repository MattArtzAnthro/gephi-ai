# gephi-ai

AI-powered network analysis through [Gephi](https://gephi.org) and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Build, analyze, style, and export publication-ready network visualizations by talking to your AI assistant.

Built for researchers working across network science and AI.

> **Status: public beta.** APIs may change between minor versions.

## What you get

**Your AI assistant drives Gephi.** Say what you want in plain language and the assistant builds, analyzes, styles, and exports publication-ready network maps.

**It's a conversation, not a command line.** The assistant explains what it's doing, checks its own maps before showing them, and teaches you to read what you're seeing. You can point back: select nodes in the Gephi window and ask "what did I select?"

**Any data, any MCP client.** Network files import directly; spreadsheets and other data become networks conversationally. Works with Claude Code, Claude Desktop, or any MCP-compatible assistant.

<details>
<summary>Full feature list</summary>

- 86 tools covering the whole workflow: build, analyze, style, lay out, filter, and export
- Interactive network view inside the chat (pan, zoom, hover, click a node to ask about it)
- Slash commands for common jobs: `/analyze-network`, `/community-detection`, `/centrality`, `/visualize`, `/import-and-explore`, `/beautify`, `/teach`
- Two extra layouts beyond Gephi's own: by role played in the network, and by community (best for reply and retweet networks)
- Reads your selection in the Gephi window, so "what did I select?" just works
- Drives any layout or metric plugin installed from the Gephi plugin portal
- Imports GEXF, GraphML, GML, CSV, DOT, and Pajek; turns spreadsheets and other files into networks conversationally

</details>

## Architecture

Three components connect your AI assistant to Gephi Desktop:

```
Claude / AI Assistant
        │
   MCP Protocol (stdio)
        │
   MCP Server (Python)          ← Translates MCP tool calls to HTTP
        │
   HTTP API (localhost:8080)
        │
   Gephi Plugin (Java)          ← Runs inside Gephi Desktop
        │
   Gephi Desktop                ← Must be running first
```

| Component | Directory | What it does |
|-----------|-----------|-------------|
| Gephi Plugin | `gephi-mcp-plugin/` | Java module that adds an HTTP API to Gephi Desktop |
| MCP Server | `mcp-server/` | Python server that exposes 86 Gephi tools via MCP |
| Claude Plugin | `claude-plugin/` | Skills, commands, agent, and hooks for Claude Code |

Install the Gephi plugin plus your AI client's connection — the Claude Code plugin bundles the MCP server, so most users install just two things. Gephi Desktop must be running before using any tools.

> **Security note:** the plugin's HTTP API binds to `127.0.0.1` only, validates the
> request `Host` header (DNS-rebinding defense), and sends no CORS headers — it is
> reachable only by local processes such as the MCP server, never by a web page.
> It is not authenticated, so do not expose port 8080 beyond localhost.

> **macOS note:** older plugin versions could wedge Gephi during sustained writes
> against a large rendered graph (calls hang; only `gephi_health_check` answers).
> Plugin 1.2.0 fixes the two causes on our side: writes now pause the renderer via
> Gephi's own viz-engine API, and a read-lock leak in the query endpoints (the main
> culprit) is closed. All lock waits are bounded, so a genuinely wedged Gephi returns
> an immediate "fully quit and reopen Gephi" error instead of hanging, and
> `gephi_health_check` exposes lock probes (`graph_lock`, `graph_lock_stats`) that
> detect the condition. If you ever see persistent "Graph is busy" errors, restart
> Gephi — and make sure you are on plugin 1.2.2 or newer.

## Setup

### Prerequisites

- [Gephi Desktop](https://gephi.org/users/download/) 0.11.1+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (runs the MCP server; one-line install, manages Python for you)
- [Claude Code](https://claude.ai/code) or [Claude Desktop](https://claude.ai/download) (for AI interaction)

### Step 1: Install the Gephi plugin

This adds the HTTP API server inside Gephi Desktop. No build tools needed — download the pre-built plugin:

1. Download `gephi-mcp-1.2.5.nbm` from the [Releases page](https://github.com/MattArtzAnthro/gephi-ai/releases) (also available at the root of this repository).
2. In Gephi: **Tools → Plugins → Downloaded → Add Plugins** — select the `.nbm` file, then click **Install**.
3. Restart Gephi. The plugin starts automatically and listens on `http://127.0.0.1:8080`.

**Verify:** Open a browser to `http://127.0.0.1:8080/health` — you should see `{"success": true}`.

### Step 2: Connect your AI assistant

#### Claude Desktop (fastest start)

Download `gephi-ai-<version>.mcpb` from the [Releases page](https://github.com/MattArtzAnthro/gephi-ai/releases) and double-click it — Claude Desktop installs the server with all dependencies bundled. No terminal, no config file. (Requires Python 3.10+ on your system, which modern macOS provides.)

<details>
<summary>Alternative: Claude Desktop via config file</summary>

Add to your MCP configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "gephi-mcp": {
      "command": "uvx",
      "args": ["gephi-mcp"]
    }
  }
}
```

</details>

#### Claude Code (most capable)

```bash
claude plugin marketplace add MattArtzAnthro/gephi-ai
claude plugin install gephi-network-analysis@gephi-ai
```

(Or run the same two commands as `/plugin marketplace add …` and `/plugin install …` inside a Claude Code session.)

The plugin bundles and runs the MCP server itself (via uv), and adds the slash commands, the network analyst agent, and the skills that teach Claude network science best practices. If you use Claude Code, this is the recommended setup.

<details>
<summary>Claude Code with MCP tools only (no skills or commands)</summary>

```bash
claude mcp add gephi-mcp -- uvx gephi-mcp
```

</details>

#### Other MCP clients

Point your client at `uvx gephi-mcp` using stdio transport. `uvx` fetches the
[`gephi-mcp` package from PyPI](https://pypi.org/project/gephi-mcp/) on first run and
caches it. For a persistent named command, `pipx install gephi-mcp` also works.

<details>
<summary>Troubleshooting: "Executable not found in $PATH"</summary>

Avoid installing with pip inside a project virtual environment. Inside an
activated `.venv` the `gephi-mcp` command only exists on that venv's `PATH`, and MCP
clients launch servers outside your shell — the server fails with "Executable not
found in $PATH" even though `which gephi-mcp` succeeds. Use `uvx`/`pipx`, or point
your MCP config at the venv executable's absolute path.

</details>

### Step 3: Verify

First confirm the MCP server actually connected. In Claude Code, run `/mcp` — `gephi-mcp` should be listed as **connected**. (In Claude Desktop, check that the tools appear in the tools menu.) If it shows a failure like "Executable not found in $PATH", the launcher (`uv`/`uvx` or `gephi-mcp`) isn't on the global `PATH` — see the notes in Step 2.

Then, with Gephi running, ask your assistant:

> "Check if Gephi is running"

It should call `gephi_health_check` and confirm the connection. In Claude Code, try:

```
/gephi-network-analysis:import-and-explore path/to/your/graph.gexf
```

## Updating

- **Claude Code:** `claude plugin update gephi-network-analysis@gephi-ai`, then start a new session.
- **Claude Desktop (one-click bundle):** download the newest `.mcpb` from Releases and double-click it again.
- **Cowork:** Cowork keeps its own copy of plugins, separate from Claude Code — updating one does not update the other. If Cowork's commands look older than this README (for example, no `/teach`), ask Cowork itself to update the gephi-network-analysis plugin, then fully quit and reopen the app.
- **Gephi plugin:** install the newest `.nbm` from Releases via Tools > Plugins > Downloaded and restart Gephi. `gephi_health_check` reports the installed version.

## What the Claude Code plugin adds

The plugin (`claude-plugin/`) goes beyond raw MCP tools:

| Component | What it does |
|-----------|-------------|
| **Slash commands** | `/analyze-network`, `/community-detection`, `/centrality`, `/visualize`, `/import-and-explore`, `/beautify`, `/teach` |
| **Network analyst agent** | Specialized subagent for deep structural analysis, metric comparison, and network classification |
| **Gephi skill** | Teaches Claude network science workflows, visualization best practices, and known Gephi gotchas |
| **Health-check hook** | Automatically verifies Gephi is running before graph-modifying operations |
| **Reference guides** | Tool reference, layout guide, and statistics interpretation guide |

## Tools (84)

| Category | Count | Examples |
|----------|-------|---------|
| Project & Workspace | 10 | `gephi_create_project`, `gephi_save_project`, `gephi_duplicate_workspace`, `gephi_rename_workspace` |
| Graph Construction | 18 | `gephi_add_nodes`, `gephi_add_edges`, `gephi_query_nodes`, `gephi_get_node` |
| Statistics | 12 | `gephi_compute_modularity`, `gephi_run_statistic` (any installed metric, by name) |
| Layout | 7 | `gephi_run_layout`, `gephi_get_layout_properties` |
| Appearance | 10 | `gephi_color_by_partition`, `gephi_size_by_ranking`, `gephi_label_clusters` |
| Filtering | 6 | `gephi_filter_by_degree`, `gephi_extract_giant_component` |
| Attributes | 5 | `gephi_get_columns`, `gephi_set_node_attributes` |
| Preview & Export | 9 | `gephi_export_png`, `gephi_export_gexf`, `gephi_view_graph` |
| Import | 4 | `gephi_import_file`, `gephi_import_gexf` |
| Health & Diagnostics | 2 | `gephi_health_check`, `gephi_visual_qa` |
| View / Camera | 1 | `gephi_focus_view` |

## Example workflows

### Community detection

```
1. gephi_create_project
2. gephi_import_file                  (your GEXF, GraphML, or CSV)
3. gephi_compute_degree
4. gephi_compute_modularity           (resolution: 1.0)
5. gephi_color_by_partition           (column: modularity_class)
6. gephi_size_by_ranking              (column: degree)
7. gephi_run_layout                   (ForceAtlas 2, 1000 iterations)
8. gephi_export_png                   (3840x2160 for publication)
```

### Centrality analysis

```
1. Import or build graph
2. gephi_compute_betweenness
3. gephi_compute_pagerank
4. gephi_run_layout                   (ForceAtlas 2)
5. gephi_color_by_ranking             (column: betweenesscentrality)
6. gephi_size_by_ranking              (column: pageranks)
7. gephi_query_nodes                  (find top-ranked nodes)
```

## Documentation

Reference guides are in `claude-plugin/skills/gephi/`:

- **SKILL.md** — Workflow patterns, best practices, and critical gotchas
- **references/tool-reference.md** — Complete API reference for all 86 tools
- **references/layout-guide.md** — Layout algorithm selection and parameter tuning
- **references/statistics-guide.md** — Statistics interpretation guide

## Tech stack

- **Gephi Plugin**: Java 11, NetBeans Platform, NanoHTTPD, Gson
- **MCP Server**: Python 3.10+, MCP SDK (FastMCP), httpx, Pydantic, defusedxml; vendored sigma.js + graphology for the in-chat viewer
- **Target**: Gephi 0.11.1, NetBeans RELEASE290

## Development

Building the Gephi plugin from source requires JDK 11+ and Maven:

```bash
cd gephi-mcp-plugin
mvn clean package    # output: target/gephi-mcp-<version>.nbm
```

The MCP server is a standard Python package under `mcp-server/` (`pytest` for tests,
`ruff` for linting).

## Attribution

If you use or adapt this project in your work, please credit:

> Built with gephi-ai (Matt Artz, 2025–2026) — https://github.com/MattArtzAnthro/gephi-ai


## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Author

**Matt Artz** — [mattartz.me](https://www.mattartz.me) | [ORCID](https://orcid.org/0000-0002-3822-1429)
