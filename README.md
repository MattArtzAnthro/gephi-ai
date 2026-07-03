# gephi-ai

AI-powered network analysis through [Gephi](https://gephi.org) and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io). Build, analyze, style, and export publication-ready network visualizations by talking to your AI assistant.

Built for researchers working across network science and AI.

> **Status: public beta.** APIs may change between minor versions.

## What you get

**80 MCP tools** for controlling Gephi Desktop — graph construction, community detection, centrality analysis, layout algorithms, filtering, styling, and publication-ready export.

**Interactive in-chat visualization** — `gephi_view_graph` renders your network as a pannable, zoomable [MCP App](https://modelcontextprotocol.io/extensions/apps/overview) directly inside Claude and Claude Desktop: hover for labels, click a node to highlight its connections or ask Claude about it, float cluster captions over communities, refresh from Gephi in place, and scrub a time slider on dynamic networks.

**Claude Code plugin** with slash commands (`/analyze-network`, `/community-detection`, `/centrality`, `/visualize`, `/import-and-explore`, `/beautify`, `/teach`), a specialized network analyst agent, and workflow skills that teach Claude network science best practices.

**Works with any MCP client** — Claude Code, Claude Desktop, or any MCP-compatible assistant.

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
| MCP Server | `mcp-server/` | Python server that exposes 80 Gephi tools via MCP |
| Claude Plugin | `claude-plugin/` | Skills, commands, agent, and hooks for Claude Code |

Install the Gephi plugin plus your AI client's connection — the Claude Code plugin bundles the MCP server, so most users install just two things. Gephi Desktop must be running before using any tools.

> **Security note:** the plugin's HTTP API binds to `127.0.0.1` only, validates the
> request `Host` header (DNS-rebinding defense), and sends no CORS headers — it is
> reachable only by local processes such as the MCP server, never by a web page.
> It is not authenticated, so do not expose port 8080 beyond localhost.

> **macOS note:** Gephi's OpenGL graph view holds the graph's read lock almost
> continuously while rendering, so a burst of API *writes* against a large, actively
> rendered graph can deadlock Gephi (calls time out; only `gephi_health_check` answers).
> The plugin hardens its own locking so a single focused pass works, but the renderer is
> Gephi-core. Best practice: do **build/import → compute → style → layout → export** as one
> sequence; if a write call ever hangs, fully quit and reopen Gephi to recover.

## Setup

### Prerequisites

- [Gephi Desktop](https://gephi.org/users/download/) 0.11.1+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (runs the MCP server; one-line install, manages Python for you)
- [Claude Code](https://claude.ai/code) or [Claude Desktop](https://claude.ai/download) (for AI interaction)
- [Java JDK 11+](https://adoptium.net/) and [Maven](https://maven.apache.org/) — only if you want to build the Gephi plugin from source

### Step 1: Install the Gephi plugin

This adds the HTTP API server inside Gephi Desktop. No build tools needed — download the pre-built plugin:

1. Download `gephi-mcp-1.2.0.nbm` from the [Releases page](https://github.com/MattArtzAnthro/gephi-ai/releases) (also available at the root of this repository).
2. In Gephi: **Tools → Plugins → Downloaded → Add Plugins** — select the `.nbm` file, then click **Install**.
3. Restart Gephi. The plugin starts automatically and listens on `http://127.0.0.1:8080`.

**Verify:** Open a browser to `http://127.0.0.1:8080/health` — you should see `{"success": true}`.

<details>
<summary>Alternative: build the plugin from source</summary>

Requires JDK 11+ and Maven:

```bash
cd gephi-mcp-plugin
mvn clean package
```

The built plugin is at `gephi-mcp-plugin/target/gephi-mcp-1.2.0.nbm`. Install it in Gephi as described above.

</details>

### Step 2: Connect your AI assistant

#### Claude Code (full plugin — recommended)

```bash
claude plugin marketplace add MattArtzAnthro/gephi-ai
claude plugin install gephi-network-analysis@gephi-ai
```

(Or run the same two commands as `/plugin marketplace add …` and `/plugin install …` inside a Claude Code session.)

That's it — the plugin bundles and runs the MCP server itself (via uv), and adds slash commands, the network analyst agent, skills, and a health-check hook. No separate server install.

#### Claude Code (MCP tools only)

If you just want the 80 tools without skills and commands:

```bash
claude mcp add gephi-mcp -- uvx gephi-mcp
```

#### Claude Desktop (one-click bundle — easiest)

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

#### Other MCP clients

Point your client at `uvx gephi-mcp` using stdio transport. `uvx` fetches the
[`gephi-mcp` package from PyPI](https://pypi.org/project/gephi-mcp/) on first run and
caches it. If you prefer a persistent named command on your `PATH` instead, install it
with `pipx install gephi-mcp` and use `gephi-mcp` as the command.

> **If you install with pip instead:** avoid a project virtual environment. Inside an
> activated `.venv` the `gephi-mcp` command only exists on that venv's `PATH`, and MCP
> clients launch servers outside your shell — the server fails with "Executable not
> found in $PATH" even though `which gephi-mcp` succeeds. Use `uvx`/`pipx`, or point
> your MCP config at the venv executable's absolute path.

### Step 3: Verify

First confirm the MCP server actually connected. In Claude Code, run `/mcp` — `gephi-mcp` should be listed as **connected**. (In Claude Desktop, check that the tools appear in the tools menu.) If it shows a failure like "Executable not found in $PATH", the launcher (`uv`/`uvx` or `gephi-mcp`) isn't on the global `PATH` — see the notes in Step 2.

Then, with Gephi running, ask your assistant:

> "Check if Gephi is running"

It should call `gephi_health_check` and confirm the connection. In Claude Code, try:

```
/gephi-network-analysis:import-and-explore path/to/your/graph.gexf
```

## What the Claude Code plugin adds

The plugin (`claude-plugin/`) goes beyond raw MCP tools:

| Component | What it does |
|-----------|-------------|
| **Slash commands** | `/analyze-network`, `/community-detection`, `/centrality`, `/visualize`, `/import-and-explore`, `/beautify`, `/teach` |
| **Network analyst agent** | Specialized subagent for deep structural analysis, metric comparison, and network classification |
| **Gephi skill** | Teaches Claude network science workflows, visualization best practices, and known Gephi gotchas |
| **Health-check hook** | Automatically verifies Gephi is running before graph-modifying operations |
| **Reference guides** | Tool reference, layout guide, and statistics interpretation guide |

## Tools (80)

| Category | Count | Examples |
|----------|-------|---------|
| Project & Workspace | 10 | `gephi_create_project`, `gephi_save_project`, `gephi_duplicate_workspace`, `gephi_rename_workspace` |
| Graph Construction | 18 | `gephi_add_nodes`, `gephi_add_edges`, `gephi_query_nodes`, `gephi_get_node` |
| Statistics | 9 | `gephi_compute_modularity`, `gephi_compute_pagerank` |
| Layout | 6 | `gephi_run_layout`, `gephi_get_layout_properties` |
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
- **references/tool-reference.md** — Complete API reference for all 80 tools
- **references/layout-guide.md** — Layout algorithm selection and parameter tuning
- **references/statistics-guide.md** — Statistics interpretation guide

## Tech stack

- **Gephi Plugin**: Java 11, NetBeans Platform, NanoHTTPD, Gson
- **MCP Server**: Python 3.10+, MCP SDK (FastMCP), httpx, Pydantic, defusedxml; vendored sigma.js + graphology for the in-chat viewer
- **Target**: Gephi 0.11.1, NetBeans RELEASE290

## Attribution

If you use or adapt this project in your work, please credit:

> Built with gephi-ai (Matt Artz, 2025–2026) — https://github.com/MattArtzAnthro/gephi-ai

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Author

**Matt Artz** — [mattartz.me](https://www.mattartz.me) | [ORCID](https://orcid.org/0000-0002-3822-1429)
